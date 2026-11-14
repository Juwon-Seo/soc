#!/usr/bin/env python3
"""André-Pierre Gignac: raw/ -> gignac.json + src/data/gnc.js (판정 근거는 judgments.md)

  python3 players/gignac/build_gignac.py

입력: raw/tm_games.csv(출전·분), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·경기장·다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(대조), raw/fotmob/leagues/230_*.json.gz(리가MX 순위표),
      raw/ranks.txt(Transfermarkt 순위표), elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(같은 경기 다른 선수 자료).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, gzip
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "gnc.js")
OUT_JSON = os.path.join(HERE, "gignac.json")
JP = "43907"
GAP = "2014-08-01"   # 이 날짜 전 도움은 Transfermarkt 리포트, 뒤는 Transfermarkt ∩ FotMob(+ 다른 출처 2곳)
PAU = "3166"         # 포 FC 임대 2005-06(프랑스 3부 National, 프로 리그 아님) → 제외

try:
    TRACKED = set(os.path.basename(p) for p in subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
except Exception:
    TRACKED = None

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 판정 표
# 2014.8 이후 Transfermarkt 단일 출처 도움(FotMob 경기 이벤트·선수 경기 목록 모두 도움 없음): gameId|분 -> 근거(넣음) / None(뺌)
POST_GAP = {
    "2640621|85": None,   # 2015.11.25 리길야 8강 치아파스전 알바레스: 기사(Mediotiempo·Bolavip)는 혼자 따낸 공을 감아 찬 골로 적음
    "2642186|82": None,   # 2015.12.6 리길야 준결승 톨루카전 알바레스: 도움자 적은 기사 없음
    "2653762|84": None,   # 2016.2.27 아메리카전 소비스: Mediotiempo 문자중계 한 곳만
    "2675369|14": None,   # 2016.5.7 크루스 아술전 소비스: 도움자 적은 기사 없음
    "2690428|26": None,   # 2016.5.14 리길야 8강 몬테레이전 소비스: 도움자 적은 기사 없음
    "2728220|63": "ESPN 경기 기사('Gignac tocó al argentino naturalizado para que definiera')·worldfootball 득점 목록(도움 지냑)",
    "2728277|22": "LiveSoccerTV 경기 기록(Assist: A. Gignac)·Mediotiempo 문자중계(도움 지냑)",
    "2789775|8": None,    # 2016.11.23 리길야 8강 푸마스전 소사: ESPN 기사 한 곳만
    "2817310|1": "Milenio·Mediotiempo 문자중계('Asistencia de André-Pierre Gignac')·worldfootball 득점 목록(도움 지냑)",
    "2826752|76": "ESPN 경기 기사(지냑 패스를 키뇨네스가 헤더)·La República 문자중계(지냑 크로스)",
    "2849312|42": None,   # 2017.4.29 티후아나전 셀라라얀: worldfootball 한 곳만
    "2856808|64": None,   # 2017.5.21 리길야 준결승 티후아나전 아키노: 도움자 적은 기사 없음
    "2856808|90": "ESPN 경기 기록(도움 지냑)·El Financiero 기사(지냑 패스 뒤 담 마무리)",
    "2894344|58": "Mediotiempo 문자중계('Assist by André-Pierre Gignac')·worldfootball 득점 목록(도움 지냑)",
    "2904455|84": "Milenio 문자중계(도움 지냑)·worldfootball 득점 목록(도움 지냑)",
    "2904473|57": None,   # 2017.9.15 모렐리아전 아키노: worldfootball 한 곳만
    "2976500|71": "Mediotiempo 문자중계(도움 지냑)·La Razón 기사('Gignac asistió a Valencia')",
    "3028026|78": None,   # 2018.4.14 크루스 아술전 바르가스: Mediotiempo 문자중계 한 곳만
    "3075909|29": None,   # 2018.4.21 네캑사전 바르가스: 도움자 적은 기사 없음
    "3075924|18": None,   # 2018.4.28 몬테레이전 발렌시아: TUDN 기사 한 곳만
    "3130898|62": "BBVA(리가 방코메르) 경기 기사(지냑 터치를 바르가스가 마무리)·El Diario NY 기사(바르가스·지냑 합작)",
    "3291796|10": "Primicias 기사(지냑이 오른쪽에서 내준 패스)·Diario de México 기사(지냑 크로스를 발렌시아가 밀어 넣음)",
}
# FotMob 선수 경기 목록에 도움 1이 있어 FotMob 확인으로 본 경기(경기 이벤트의 도움 칸은 빔)
FM_PM_OK = {"3328962"}

# ---------------------------------------------------------------- 날짜·경기장
STADIUM_TZ = {'Estadio Caliente': 'America/Tijuana', 'El Encanto': 'America/Mazatlan', 'Estadio Olímpico Benito Juárez': 'America/Ciudad_Juarez',
    'America First Field': 'America/Denver', 'BC Place': 'America/Vancouver', 'Starlight Stadium': 'America/Vancouver', 'BMO Field': 'America/Toronto',
    'Tim Hortons Field': 'America/Toronto', 'BMO Stadium': 'America/Los_Angeles', 'Dignity Health Sports Park': 'America/Los_Angeles',
    'PayPal Park': 'America/Los_Angeles', 'Snapdragon Stadium': 'America/Los_Angeles', 'Sam Boyd Stadium': 'America/Los_Angeles',
    'Chase Stadium': 'America/New_York', 'Inter.co Stadium': 'America/New_York', 'ScottsMiracle-Gro Field': 'America/New_York',
    'Sports Illustrated Stadium': 'America/New_York', 'TQL Stadium': 'America/New_York', 'GEODIS Park': 'America/Chicago', 'NRG Stadium': 'America/Chicago',
    'Q2 Stadium': 'America/Chicago', 'Shell Energy Stadium': 'America/Chicago', 'Estadio Cuscatlán': 'America/El_Salvador',
    'Estadio Olímpico Metropolitano': 'America/Tegucigalpa', 'Estádio Beira-Rio': 'America/Sao_Paulo', 'Estadio Monumental': 'America/Argentina/Buenos_Aires',
    'Ahmad bin Ali Stadium': 'Asia/Qatar', 'Education City Stadium': 'Asia/Qatar'}
OPP_TZ = {'Club Tijuana': 'America/Tijuana', 'Mazatlán FC': 'America/Mazatlan', 'FC Juárez': 'America/Ciudad_Juarez', 'Dorados de Sinaloa': 'America/Mazatlan'}
DATE_FIX = {"2642186": ("2015-12-06", "Transfermarkt 일정·리포트가 2015.11.6로 적은 리길야 준결승 2차전 톨루카전. 1차전(12.3) 뒤 경기이고 El Universal·ESPN 기사가 2015.12.6(일)로 적음")}

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"FR1", "FR2", "MEXA", "MEX1"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid in ("FRC", "FRL"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "MXCA": return "dc"                       # 코파 MX 조별
    if cid in ("MXSC", "MESC", "CAMC"): return "df"     # 캄페온 데 캄페오네스·수페르코파 MX·캄페오네스컵 = 국내컵 결승 비중
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        return "clk"
    if cid == "CLQ": return "clq"
    if cid == "ELQ": return "elq"
    if cid == "UEFA": return "elg" if r.startswith("group") else "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
    if cid == "EL": return "elg"
    if cid in ("POMX", "POME"):      # 멕시코 리길야 = MLS 플레이오프 비중(카모라네시·메네즈 선례)
        if r.startswith("semi"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
        return "mlp"                  # 8강·리길야 진출전(repechaje·play-in)·2026 클라우수라 8강(Transfermarkt 'Matchday' 표기)
    if cid == "CCL":
        if r.startswith("quarter"): return "ccck"
        if r.startswith("semi"): return "cccsf"
        if r.startswith("final"): return "cccf"
        return "ccc"                  # 조별(2015-16)·1라운드·16강
    if cid == "USMX": return "lcg" if r.startswith("group") else "lck"
    if cid == "CLI": return "libf" if r.startswith("final") else "libsf"
    if cid == "KLUB": return "cwc"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE_IDS: return 0
    if cid == "MXCA" or (cid in ("CL", "EL", "UEFA", "CCL") and r.startswith("group")): return 0
    if cid in ("POMX", "POME") and "matchday" in r: return 0   # 2026 클라우수라 8강 두 경기(Transfermarkt가 'Matchday'로 적음)
    return 1          # 리그스컵 조별도 무승부면 승부차기(메시·인시녜 선례)

# ---------------------------------------------------------------- 입력
games_all = rd("tm_games.csv")
games = [g for g in games_all if g["level"] == "senior" and g["club_id"] != PAU]
PAU_G = [g for g in games_all if g["club_id"] == PAU]
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

def stadium(gid):
    return MI.get(gid, {}).get("extra", "").split("|")[0].split(" Referee")[0].split(" - Behind")[0].strip()

DATE_LOG = []
def ldate(g):
    gid = g["gameId"]
    if gid in DATE_FIX: return DATE_FIX[gid][0]
    if g["club_id"] != "7055": return g["date_local"]          # 유럽: 리포트 날짜(현지)
    tz = STADIUM_TZ.get(stadium(gid)) or (OPP_TZ.get(g["opponent"]) if g["venue"] != "H" else None) or "America/Monterrey"
    u = g["date_utc"]
    if g["utc_time_is_0000"] == "1" and g["fotmob_utc"]: u = g["fotmob_utc"].replace("Z", "+00:00")   # 00:00 자리표시 → FotMob 시각
    return datetime.fromisoformat(u).astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d")
for g in games:
    if ldate(g) != g["date_local"]: DATE_LOG.append((g["gameId"], g["date_local"], ldate(g), g["opponent"]))
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    r = rnd.lower()
    if cid in ("CL", "CLQ", "ELQ", "UEFA", "EL"): return (1, 1)
    if cid == "CLI": return (0, 1) if r.startswith("final") else (1, 0)   # 리베르타도레스 2015 준결승: 원정 다득점, 연장 없이 승부차기
    if cid == "CCL": return (1, 0) if d < "2024-01-01" else (1, 1)          # 챔피언스컵(2024~): 원정 다득점 뒤 연장·승부차기
    if cid in ("POMX", "POME"): return (0, 1) if r.startswith("final") else (0, 0)   # 리길야: 8강·4강 동률은 정규리그 상위 팀 진출(모형 밖), 결승은 연장·승부차기
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid); oid = m["other_leg_id"]
    if oid in G:
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), g["round"])
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

# 리포트 골 목록 순서가 잘못된 경기: FotMob 순서로 바로잡은 (분, 골 뒤 스코어 홈-원정)
EV_FIX = {
    # 2022.2.6 티그레스 4-3 마사틀란: Transfermarkt 목록 맨 앞의 곤살레스 골(121분 표기)은 FotMob 기준 78분 4-2 골
    "3729488": {"Carlos González": ("78", "4-2"), "Juan Pablo Vigón|11": ("11", "1-0"), "Juan Pablo Vigón|23": ("23", "2-0"),
                "Brian Rubio": ("46", "2-1"), "Nicolás Benedetti": ("64", "2-2"), "André-Pierre Gignac": ("76", "3-2"), "Miguel Sansores": ("90+3", "4-3")},
    # 2024.4.13 몬테레이 3-3 티그레스: 45+2분 고리아란 골(1-2)이 46분 브루네타 골(1-3)보다 먼저
    "4249508": {"Fernando Gorriarán": ("45+2", "1-2"), "Juan Brunetta|46": ("46", "1-3")},
}
def events(gid):
    evs = [dict(e) for e in EVS[gid]]
    fx = EV_FIX.get(gid)
    if fx:
        for e in evs:
            k = e["scorer"] + "|" + e["minute"]
            v = fx.get(k) or fx.get(e["scorer"])
            if v: e["minute"], e["score_home_away_after"] = v
        evs.sort(key=lambda e: sum(map(int, e["score_home_away_after"].split("-"))))
    return evs

def fm_ev(gid, after_ha):
    for f in FME.get(gid, []):
        if f["newScore_home_away"] == after_ha and f["pen_shootout_event"] != "True": return f
    return None

def assist_reason(e):
    t = e["assist_type"]
    if e["scorer_id"] == JP: return "본인 PK 골에 본인 도움"
    if e["own_goal"] == "1": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

raw_rows, judg, post_gap_log, min_fix = [], [], [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid)
    prev = (0, 0)
    for e in events(gid):
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == JP and e["own_goal"] != "1"
        is_a = e["assist_id"] == JP
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        f = fm_ev(gid, e["score_home_away_after"])
        if dm == 0 and mi in (45, 90) and f and f["overloadTime"] and int(f["time"]) == mi and int(f["overloadTime"]) > 0:
            dm = f"{mi}+{int(f['overloadTime'])}"; min_fix.append((gid, ldate(g), opp(g), e["minute"], dm)); mi = mi + int(f["overloadTime"])
        d = ldate(g); tag = f"{gid}|{e['minute']}"
        if is_a:
            why = assist_reason(e)
            fm_ok = bool(f and f["gignac_assist"] == "1") or gid in FM_PM_OK
            if why:
                judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], why))
            elif d >= GAP and not fm_ok:
                v = POST_GAP.get(tag, "미판정")
                post_gap_log.append((gid, d, opp(g), e["minute"], e["scorer"], e["assist_type"], v))
                if v == "미판정": sys.exit("[판정 필요] 2014.8 이후 Transfermarkt 단일 도움 " + tag)
                if v: raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
                else: judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], "2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)"))
            else:
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            raw_rows.append(("g", gid, mi, dm, gf, ga, 1 if e["penalty"] == "1" else 0, 0))

fm_only_seen = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        tm = [e for e in events(gid) if e["score_home_away_after"] == f["newScore_home_away"]]
        if f["gignac_assist"] == "1" and not any(e["assist_id"] == JP for e in tm):
            fm_only_seen.append((gid, ldate(G[gid]), opp(G[gid]), f["time"], f["scorer"]))
        if f["gignac_scorer"] == "1" and f["pen_shootout_event"] != "True" and not any(e["scorer_id"] == JP for e in tm):
            sys.exit("[판정 필요] FotMob 전용 골 " + gid)
for gid, g in G.items():   # FotMob 선수 경기 목록에만 있는 도움
    pm = FPM.get(g["fotmobMatchId"])
    if pm and int(pm["assists"] or 0) > int(g["assists"] or 0):
        fm_only_seen.append((gid, ldate(g), opp(g), "선수 경기 목록", pm["assists"]))
fm_goal_diff = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["gignac_scorer"] != "1" or f["pen_shootout_event"] == "True": continue
        tm = [e for e in events(gid) if e["score_home_away_after"] == f["newScore_home_away"] and e["scorer_id"] == JP]
        fpen = f["goalDescriptionKey"] == "penalty"
        if tm and (tm[0]["penalty"] == "1") != fpen: fm_goal_diff.append((gid, ldate(G[gid]), opp(G[gid]), f["time"], "PK 표기 다름 TM=" + tm[0]["penalty"]))

# ---------------------------------------------------------------- 상대 Elo
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())
ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
def key(n):
    k = norm(n); return ALIAS.get(k, k)
TABLE = {}
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if "지냑" in r["선수"]: continue
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "gnc.js") or (TRACKED is not None and b not in TRACKED): continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)

LGPTS = collections.defaultdict(dict)
for b, (oe, om) in OTHERS.items():
    for x in oe:
        lv = str(x[12])
        if "추정" in lv: continue
        m = re.match(r"(리그1|리그2) (\d{4}-\d\d) (\d+)위$", lv)
        if m: LGPTS[(m.group(1), m.group(2))][int(m.group(3))] = x[2]

def fill(known, n):
    out = {}; ks = sorted(known)
    for r in range(1, n + 1):
        if r in known: out[r] = known[r]; continue
        lo = max([k for k in ks if k < r], default=None); hi = min([k for k in ks if k > r], default=None)
        out[r] = round(known[lo] + (known[hi] - known[lo]) * (r - lo) / (hi - lo))
    return out
L1_STD = dict(LGPTS[("리그1", "2016-17")])
L2_STD = fill({1: 1669, 2: 1624, 4: 1582, 6: 1567, 7: 1559, 8: 1550, 10: 1532, 11: 1526, 12: 1521, 13: 1516, 14: 1513, 15: 1508,
               17: 1490, 19: 1480, 20: 1470}, 20)
# 리가MX 18팀 순위값: 기존 자료(호나우지뉴·카모라네시·로이스) 값 + 빈 순위는 가운데값(메네즈 자료와 같은 표)
MX = fill({1: 1789, 3: 1683, 5: 1648, 6: 1637, 7: 1623, 9: 1594, 10: 1584, 11: 1576, 13: 1563, 14: 1553, 17: 1519, 18: 1503}, 18)
def mx_val(r, n):
    if n == 18: return MX[r]
    p = 1 + (r - 1) * 17 / (n - 1); i = min(int(p), 17); t = p - i       # 19팀 시즌(2019-20)은 18팀 값 사이 보간
    return round(MX[i] + (MX[i + 1] - MX[i]) * t)

# 리가MX 아페르투라·클라우수라 정규리그 표(FotMob)를 합친 시즌 누적 순위(승점 → 득실차 → 다득점)
FMN = {"Monterrey": "CF Monterrey", "León": "Club León FC", "CF América": "CF America", "Pumas": "UNAM Pumas", "Toluca": "Deportivo Toluca",
       "Pachuca": "CF Pachuca", "Atlético Morelia": "Monarcas Morelia", "Chivas": "Deportivo Guadalajara", "Puebla": "Puebla FC",
       "Santos Laguna": "Santos Laguna", "Cruz Azul": "CD Cruz Azul", "Querétaro FC": "Querétaro FC", "Jaguares Chiapas": "Chiapas FC",
       "Veracruz": "Tiburones Rojos de Veracruz", "Tijuana": "Club Tijuana", "Atlas": "Atlas Guadalajara", "Dorados": "Dorados de Sinaloa",
       "Necaxa": "Club Necaxa", "Lobos de la BUAP": "Lobos BUAP", "Atlético de San Luis": "Atlético de San Luis", "FC Juárez": "FC Juárez",
       "Mazatlán FC": "Mazatlán FC", "Tigres": "Tigres UANL"}
MXCUM = {}
for y in range(2015, 2026):
    d = json.load(gzip.open(os.path.join(RAW, "fotmob", "leagues", f"230_{y}-{y + 1}-Apertura.json.gz")))
    agg = collections.defaultdict(lambda: [0, 0, 0])
    for t in d["table"][0]["data"]["tables"]:
        for r in t["table"]["all"]:
            gf_, ga_ = map(int, r["scoresStr"].split("-")); a = agg[r["name"]]
            a[0] += r["pts"]; a[1] += gf_ - ga_; a[2] += gf_
    rk = sorted(agg.items(), key=lambda kv: (-kv[1][0], -kv[1][1], -kv[1][2]))
    s = f"{y}-{str(y + 1)[2:]}"
    for i, (n, v) in enumerate(rk):
        MXCUM[(key(FMN[n]), s)] = (i + 1, len(rk))

BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio",
        "atletico", "ca", "us", "as", "ss", "ssc", "hsc", "osc", "acf", "olympique", "stade", "fk", "sv", "saint", "paris", "cd", "deportivo"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, {(x[2], x[12]) for b, x in cand}

MEX_COMP = ("MEX1", "MEXA", "POME", "POMX", "MXCA", "MXSC", "MESC", "CCL", "USMX", "CAMC")
MAN = {}            # (상대, 시즌) -> (Elo, lv)  — 아래 Elo 절에서 채움
OVR = {}            # 통합표 충돌을 피하려고 기존 값을 쓰는 팀-시즌: (key, 시즌) -> (Elo, lv)

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def mex_season(d):    # 리가MX 시즌(7월 1일 기준)
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand}))
        return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    ms = mex_season(d)
    if (key(o), ms) in OVR:
        e, lv = OVR[(key(o), ms)]; ELO_SRC["기존 팀×시즌 값(통합표 맞춤)"] += 1; ELO_LOG[(o, d)] = ("ovr", e, lv); return e, lv
    if (key(o), ms) in MXCUM:
        r, n = MXCUM[(key(o), ms)]
        e, lv = mx_val(r, n), f"리가MX {ms} 누적 {r}위"
        ELO_SRC["리가MX 누적 순위+순위값"] += 1; ELO_LOG[(o, d)] = ("mxcum", e, lv); return e, lv
    seasons = [eu(d), d[:4]]
    for s in seasons:
        if (key(o), s) in TABLE:
            e, lv = TABLE[(key(o), s)]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv)
            return e, lv
    tab = RANKS.get(("FR1", f"{eu(d)[2:4]}/{eu(d)[5:7]}"), {})
    if key(o) in tab and cid in ("FR1", "FRC", "FRL"):
        r, n, _ = tab[key(o)]; v = LGPTS.get(("리그1", eu(d)), {}).get(r, L1_STD[r])
        ELO_SRC["순위표+리그 순위값"] += 1; ELO_LOG[(o, d)] = ("model", v, f"리그1 {eu(d)} {r}위"); return v, f"리그1 {eu(d)} {r}위"
    tab = RANKS.get(("FR2", f"{eu(d)[2:4]}/{eu(d)[5:7]}"), {})
    if key(o) in tab:
        r, n, _ = tab[key(o)]; v = LGPTS.get(("리그2", eu(d)), {}).get(r, L2_STD[r])
        ELO_SRC["순위표+리그 순위값"] += 1; ELO_LOG[(o, d)] = ("model", v, f"리그2 {eu(d)} {r}위"); return v, f"리그2 {eu(d)} {r}위"
    for s in seasons:
        if (o, s) in MAN:
            e, lv = MAN[(o, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv)
            return e, lv
    MISS.append((o, d, cid)); return 0, "?"

exec(open(os.path.join(HERE, "elo_gignac.py"), encoding="utf-8").read())   # MAN·OVR 표(판정 기록 7절)

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and ko) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))
if MISS:
    for x in sorted(set(MISS), key=lambda t: t[1]): print("MISS", x)
    sys.exit("상대 Elo 없음 %d" % len(MISS))

exec(open(os.path.join(HERE, "out_gignac.py"), encoding="utf-8").read())   # 동료 대조·설명·점검·출력
