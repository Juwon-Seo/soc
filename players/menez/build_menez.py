#!/usr/bin/env python3
"""Jérémy Ménez: raw/ -> menez.json + src/data/men.js (판정 근거는 judgments.md)

  python3 players/menez/build_menez.py

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv(대조), raw/ranks.txt(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값), src/data/*.js(같은 경기 다른 선수 자료 대조·재사용).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "men.js")
OUT_JSON = os.path.join(HERE, "menez.json")
JP = "16993"
GAP = "2014-08-01"           # 이 날짜 전 도움은 Transfermarkt 리포트, 뒤는 Transfermarkt ∩ FotMob(+ 다른 출처 2곳)

# 같은 회차에 다른 판정 에이전트가 쓰는 파일(git에 없는 data 파일)은 대조·재사용에서 뺌
try:
    TRACKED = set(os.path.basename(p) for p in subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
except Exception:
    TRACKED = None

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 판정 표
# 2014.8 이후 Transfermarkt 단일 출처 도움(FotMob 경기 이벤트에 Ménez 도움 없음): gameId|분 -> 근거(넣음) / None(뺌)
POST_GAP = {
    "2814020|90+2": None,   # 2017.1.31 쿠프 드 프랑스 디종전 라보르드 결승골: ESPN·worldfootball·footmercato 모두 도움자 없음, 기사에서 메네즈 언급 확인 못 함
    "3007822|5": None,      # 2018.2.13 모렐리아전 도밍게스 골: ESPN(Opta 문자중계)만 메네즈 크로스, Quadratín 기사는 도움자 없음 → 출처 1곳
    "3016577|2": None,      # 2018.3.17 톨루카전 이바라 골: ESPN 기사·문자중계(같은 매체 1곳)만 메네즈 패스
    "3043595|38": None,     # 2018.5.2 리길야 8강 1차전 우리베 골: 기사는 스로인 뒤 중거리 슛으로만 적음, FotMob 도움 없음
    "3043599|4": "TUDN 경기 기사('contragolpe que comandó y terminó Mateus Uribe, con la asistencia de Jérémy Ménez')·Vanguardia 기사(우리베와 메네즈의 합작 플레이). FotMob 경기 기록은 이 골 도움 칸이 빔",
    "3043605|23": "ESPN 경기 기사·문자중계(메네즈 코너킥 크로스를 발데스가 헤더)·Mediotiempo 계열 기사('tras un tiro de esquina al 22’ cobrado por Jérémy Ménez'). FotMob 경기 기록은 도움 칸이 빔",
}
# FotMob에만 있는 Ménez 도움(Transfermarkt 리포트엔 없음): 모두 뺌
FM_ONLY = {
    "2836503|61": "2017.2.28 쿠프 드 프랑스 로리앙전 61분 라보르드 동점골: FotMob만 메네즈 도움(Transfermarkt는 탭인, 도움 없음). 같은 경기 72분 라보르드 골은 두 출처 모두 메네즈 도움",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"FR1", "FR2", "IT1", "IT2", "TR1", "MEX1", "MEXA"}
CUPS = {"CIT", "FRC", "FRL", "TRP", "MXCC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "ELQ": return "elq"
    if cid in ("EL", "UEFA"):
        if r.startswith("group"): return "elg"
        return "elk"            # 2009-10 유로파 32강('Second Round')·2004-05 UEFA컵 32강('intermediate stage')
    if cid in ("SCI", "MXSC"): return "df"   # 수페르코파 이탈리아나·캄페온 데 캄페오네스 = 국내컵 결승 비중
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"     # 1~7라운드·16강·튀르키예컵 5라운드
    if cid == "POME":       # 멕시코 리길야 = MLS 플레이오프 비중(카모라네시 선례)
        if r.startswith("semi"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
        return "mlp"
    if cid == "CCL": return "ccc"     # 북중미 챔스 16강
    if cid == "USMX": return "lck"    # 리그스컵 2019 8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE_IDS: return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 입력
games_all = rd("tm_games.csv")
games = [g for g in games_all if g["level"] == "senior"]       # 클루브 아메리카 U20 1경기(2019.7.27) 제외
YOUTH = [g for g in games_all if g["level"] != "senior"]
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

def ldate(g): return g["date_local_tz_conv"]
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round_report"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    if cid in ("CL", "EL", "ELQ", "UEFA"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid == "CIT": return (1, 1)    # 코파 이탈리아 준결승: 2021-22까지 원정 다득점, 2차전 연장
    if cid == "POME": return (0, 0)   # 리길야: 원정 다득점·연장 없음(동률이면 정규리그 상위 팀 진출, 카모라네시 선례)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G:
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round_report"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
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

def fm_ev(gid, after_ha):
    for f in FME.get(gid, []):
        if f["newScore_home_away"] == after_ha and f["pen_shootout_event"] != "True": return f
    return None

def assist_reason(e):
    t = e["assist_type"]
    if e["scorer_id"] == JP: return "본인 PK 골에 본인 도움(PK 유도)"
    if e["own_goal"] == "1": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

raw_rows, judg, post_gap_log, min_fix = [], [], [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid)
    prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == JP and e["own_goal"] != "1"
        is_a = e["assist_id"] == JP
        if not (is_g or is_a): continue
        if e["side"][0] != side and not (is_a and assist_reason(e)):
            sys.exit("득점 편 이상 " + gid)
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        f = fm_ev(gid, e["score_home_away_after"])
        if dm == 0 and mi in (45, 90) and f and f["overloadTime"] and int(f["time"]) == mi and int(f["overloadTime"]) > 0:
            dm = f"{mi}+{int(f['overloadTime'])}"; min_fix.append((gid, ldate(g), opp(g), e["minute"], dm)); mi = mi + int(f["overloadTime"])
        d = ldate(g); tag = f"{gid}|{e['minute']}"
        if is_a:
            why = assist_reason(e)
            fm_ok = bool(f and "Menez" in (f["assistStr"] or "") or (f and "Ménez" in (f["assistStr"] or "")))
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
        tm = [e for e in EVS.get(gid, []) if e["score_home_away_after"] == f["newScore_home_away"]]
        if f["menez_assist"] == "1" and not any(e["assist_id"] == JP for e in tm):
            k = f"{gid}|{f['time']}"
            fm_only_seen.append(("a", k, ldate(G[gid]), f["scorer"]))
            if k not in FM_ONLY: sys.exit("[판정 필요] FotMob 전용 도움 " + k)
        if f["menez_scorer"] == "1" and not any(e["scorer_id"] == JP for e in tm):
            sys.exit("[판정 필요] FotMob 전용 골 " + gid)
# Transfermarkt 골·PK와 FotMob 대조(보고용)
fm_goal_diff = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["menez_scorer"] != "1": continue
        tm = [e for e in EVS.get(gid, []) if e["score_home_away_after"] == f["newScore_home_away"] and e["scorer_id"] == JP]
        fpen = f["goalDescriptionKey"] == "penalty"
        if tm and (tm[0]["penalty"] == "1") != fpen: fm_goal_diff.append((gid, f["time"], "PK 표기 다름"))

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
        if "제레미 메네즈" in r["선수"]: continue
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
    if b in ("hon.js", "men.js") or (TRACKED is not None and b not in TRACKED): continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)

# 기존 자료의 순위값(lv '리그 시즌 N위', 추정 아님): 리그별·시즌별
LGPTS = collections.defaultdict(dict)
for b, (oe, om) in OTHERS.items():
    for x in oe:
        lv = str(x[12])
        if "추정" in lv: continue
        m = re.match(r"(리그1|세리에A|세리에B|리그2) (\d{4}-\d\d) (\d+)위$", lv)
        if m: LGPTS[(m.group(1), m.group(2))][int(m.group(3))] = x[2]

def fill(known, n):
    """알려진 순위값 사이 빈 순위는 이웃 값의 단순 보간(가운데값)"""
    out = {}
    ks = sorted(known)
    for r in range(1, n + 1):
        if r in known: out[r] = known[r]; continue
        lo = max([k for k in ks if k < r], default=None); hi = min([k for k in ks if k > r], default=None)
        out[r] = round(known[lo] + (known[hi] - known[lo]) * (r - lo) / (hi - lo))
    return out

# 리그1·세리에A 20팀 순위값은 2008-09 이후 시즌 공통(기존 자료)
L1_STD = dict(LGPTS[("리그1", "2016-17")]); SA_STD = dict(LGPTS[("세리에A", "2016-17")])
# 세리에B 20팀(2019-20~): 기존 자료의 20팀 시즌 값(1993-96·2019-20·2022-23·2023-24·2025-26). 같은 순위 값이 시즌마다 1 다른 곳은 그 시즌 값 우선
SB20 = fill({1: 1707, 2: 1663, 3: 1637, 4: 1620, 5: 1611, 6: 1605, 7: 1597, 8: 1588, 9: 1579, 10: 1570, 11: 1564, 12: 1559,
             13: 1554, 14: 1551, 15: 1546, 16: 1538, 17: 1528, 18: 1522, 19: 1518, 20: 1508}, 20)
# 세리에B 22팀(2009-10): 기존 자료 2011-12·2006-07 22팀 값
SB22 = fill({1: 1707, 10: 1577, **LGPTS[("세리에B", "2006-07")], **LGPTS[("세리에B", "2011-12")]}, 22)
# 리그2 20팀: 기존 자료 값(2000년대·2010년대 공통값), 빈 순위는 가운데값
L2_STD = fill({1: 1669, 2: 1624, 4: 1582, 6: 1567, 7: 1559, 8: 1550, 10: 1532, 11: 1526, 12: 1521, 13: 1516, 14: 1513, 15: 1508,
               17: 1490, 19: 1480, 20: 1470}, 20)   # 20위는 기존 자료 리그2 20위 1470(추정)과 같게
# 리가MX 18팀: 기존 자료(호나우지뉴 아페르투라 2014·로이스 2025-26·카모라네시 누적) 값, 빈 순위(2·4·8·12·15·16위)는 가운데값
MX = fill({1: 1789, 3: 1683, 5: 1648, 6: 1637, 7: 1623, 9: 1594, 10: 1584, 11: 1576, 13: 1563, 14: 1553, 17: 1519, 18: 1503}, 18)
# 세리에C 18팀 조: 기존 자료(인시녜·인자기·네드베드) 값, 빈 순위는 가운데값
SC18 = fill({1: 1546, 3: 1472, 6: 1439, 7: 1429, 9: 1409, 10: 1402, 13: 1388, 15: 1371, 16: 1362, 17: 1357, 18: 1346}, 18)
# 오스트리아 2011-12: 다른 선수 자료(리트 6위 1370, '국가 계수 회귀 평균 약 1409')와 같은 방식, 흩어짐 119
SA_LIST = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA_LIST]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

def rank_model(lg, season, r, n):
    if lg == "FR1":
        v = LGPTS.get(("리그1", season), {}).get(r, L1_STD[r]); return v, f"리그1 {season} {r}위"
    if lg == "IT1":
        v = LGPTS.get(("세리에A", season), {}).get(r, SA_STD[r]); return v, f"세리에A {season} {r}위"
    if lg == "IT2":
        base = SB22 if n == 22 else SB20
        v = LGPTS.get(("세리에B", season), {}).get(r, base[r]); return v, f"세리에B {season} {r}위"
    if lg == "FR2":
        v = LGPTS.get(("리그2", season), {}).get(r, L2_STD[r]); return v, f"리그2 {season} {r}위"
    if lg == "MEX1":   # TM 'MEX1 2017-18' = 클라우수라 2018 정규리그 표
        return MX[r], f"리가MX 클라우수라 {int(season[:4]) + 1} {r}위"
    if lg == "IT3A":
        return SC18[r], f"세리에C(레가 프로) A조 {season} {r}위/18팀 (추정, 다른 선수 자료의 세리에C 18팀 조 순위값)"
    if lg == "A1":
        return round(1409 + 119 * curve(r, n)), f"오스트리아 분데스리가 {season} {r}위 (추정, 다른 선수 자료 리트 2011-12 6위 1370과 같은 국가 계수 회귀 평균 약 1409·흩어짐 119)"
    return None

USE_LEAGUES = ["FR1", "IT1", "IT2", "FR2", "MEX1", "IT3A", "A1"]

BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio",
        "atletico", "ca", "us", "as", "ss", "ssc", "hsc", "osc", "acf", "olympique", "stade", "fk", "sv", "saint", "paris"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, {(x[2], x[12]) for b, x in cand}

# 순위표·기존 자료에 없는 상대(직접 추정, 모두 '추정')
MAN = {
    ("CMS Oissel", "2005-06"): (1150, "프랑스 5부(CFA2) 2005-06 D조 8위 (추정, 다른 선수 자료의 프랑스 5부 팀과 같은 수준)"),
    ("Sablé-sur-Sarthe FC", "2011-12"): (1150, "프랑스 5부(CFA2) 2011-12 B조 7위 (추정, 다른 선수 자료의 프랑스 5부 팀과 같은 수준)"),
}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand}))
        return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    mex = cid in ("MEX1", "MEXA", "POME", "MXCC", "MXSC", "CCL", "USMX")
    seasons = [d[:4]] if mex else [eu(d)]
    for s in seasons:
        if (key(o), s) in TABLE:
            e, lv = TABLE[(key(o), s)]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv)
            return e, lv
    for lg in USE_LEAGUES:
        tab = RANKS.get((lg, eu(d)), {})
        if key(o) in tab:
            r, n, _ = tab[key(o)]
            res = rank_model(lg, eu(d), r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    for s in [eu(d)]:
        if (o, s) in MAN:
            e, lv = MAN[(o, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv)
            return e, lv
    MISS.append((o, d, cid)); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round_report"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (g["gameState"] == "extra_time" and mi > 90 and ko) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(수정 없음, 보고용)
MATE_NAME = {"tot.js": "Francesco Totti", "ibr.js": "Zlatan Ibrahimović", "pas.js": "Javier Pastore", "cav.js": "Edinson Cavani",
             "luc.js": "Lucas Moura"}
ALT = {"Francesco Totti": ("Totti",), "Zlatan Ibrahimović": ("Ibrahimovi",), "Javier Pastore": ("Pastore",),
       "Edinson Cavani": ("Cavani",), "Lucas Moura": ("Lucas",)}
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and ("Ménez" in str(x[13]) or "Menez" in str(x[13])):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7], hit[0][14:]) == (x[5], x[6], x[2], x[12], x[3], x[7], x[14:])
            cross.append(("동료 도움→메네즈 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "메네즈 골 없음"), x[2:8], hit[0][2:8] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and any(t in r[13] for t in ALT[nm]):
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7], hit[0][14:]) == (r[5], r[6], r[2], r[12], r[3], r[7], r[14:])
                has_m = any(m[0] == r[9] for m in om)
                cross.append(("메네즈 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else ("동료 골 없음" + ("" if has_m else "(출전 행도 없음)"))), r[2:8], hit[0][2:8] if hit else None))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[12], x[3]), (r[2], r[12], r[3])))
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                cross.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[2], m[2]))
for gid, evs in EVS.items():
    if gid not in G: continue
    for e in evs:
        if e["scorer_id"] == JP and e["assist_id"] and not e["assist_type"].startswith("Penalty"):
            for b, nm in MATE_NAME.items():
                if b in OTHERS and any(t in e["assist_player"] for t in ALT[nm]):
                    d = ldate(G[gid]); oe, om = OTHERS[b]
                    if not any(x[0] == "a" and x[9] == d and ("Ménez" in str(x[13]) or "Menez" in str(x[13])) for x in oe):
                        cross.append(("Transfermarkt 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"] or "(유형 빈칸)",
                                      "출전 행 있음" if any(m[0] == d for m in om) else "출전 행도 없음"))
DUP = set()
cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 클럽별 합계
CLUBS = [("2006-07-01", "소쇼"), ("2008-08-27", "AS 모나코"), ("2011-07-25", "AS 로마"), ("2014-07-01", "파리 생제르맹"),
         ("2016-08-01", "AC 밀란"), ("2017-07-01", "보르도"), ("2018-01-09", "안탈리아스포르"), ("2019-08-29", "클루브 아메리카"),
         ("2020-07-01", "파리 FC"), ("2023-07-01", "레지나"), ("9999-12-31", "바리")]
TMCLUB = {"750": "소쇼", "162": "AS 모나코", "12": "AS 로마", "583": "파리 생제르맹", "5": "AC 밀란", "40": "보르도",
          "589": "안탈리아스포르", "3631": "클루브 아메리카", "10004": "파리 FC", "1386": "레지나", "332": "바리"}
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
for g in games:
    if club_of(ldate(g)) != TMCLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for _, n in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
TM_A_ALL = sum(1 for gid, evs in EVS.items() if gid in G for e in evs if e["assist_id"] == JP and e["scorer_id"] != JP)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
SHOT = "슈팅 리바운드('Shot on goal')"
def jl(reason):
    return ", ".join(f"{d_(j[1])} {j[2]} {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
EST_MODEL = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "model" and "추정" in v[2]}, key=lambda t: t[0])
MX_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "model" and "리가MX" in v[2]}, key=lambda t: t[1], reverse=True)
SAME_N = ELO_SRC["같은 경기 다른 선수 자료"]

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
NOTE_LINES = [
    f"제레미 메네즈(소쇼·AS 모나코·AS 로마·파리 생제르맹·AC 밀란·보르도·안탈리아스포르·클루브 아메리카·파리 FC·레지나·바리)의 클럽 공식 경기 {NG}경기({d_(first[0])} 아작시오전 ~ {d_(last[0])} 카탄차로전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n} {c3(v)}" for n, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(출전 {NG}경기)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음",
    "클럽별 경기·골·도움은 프랑스어 위키백과 클럽 표와 소쇼(도움 4)·로마(119경기 23도움)·PSG(대표팀 포함 합계라 비교 불가)를 빼고 같음. 영어 위키백과는 소쇼 63·7, 모나코 62·14, 로마 112·12, 레지나 67·13으로 2~5경기 적음(컵 경기 일부 누락). FotMob 경력 합계는 PSG 110·19, 밀란 46·20, 보르도 31·3, 아메리카 23·5, 파리 FC 18·5, 레지나 69·13, 바리 10·0으로 같음",
    "레지나(세리에B 2020-21~2022-23)·바리(세리에B 2023-24)·파리 FC(리그2 2019-20)는 프로 2부 리그라 넣음. 클루브 아메리카 U20 경기(2019.7.27 레온 U20전 84분)와 프랑스 대표·연령별 대표 경기는 뺌",
    "Transfermarkt는 2025.12.31 은퇴(마지막 소속 'CT United'로 적지만 그 팀 공식 경기 기록은 없음)로 적음. 마지막 공식 경기는 2024.2.27 바리 카탄차로전",
    f"골 {NGo}개 중 PK {NPK}개. PK 여부는 Transfermarkt와 FotMob 경기 기록이 모두 같음. 2010-11 이후 골은 FotMob 경기 기록과 수·스코어가 같음(FotMob 기록이 없는 로마 2010-11 일부 경기 제외). FotMob에는 2010년 이전 경기 기록이 없어 소쇼·모나코·로마 2008-10의 골·도움은 Transfermarkt 리포트만 씀",
    "도움은 2014.8.1 이전은 Transfermarkt 리포트 도움을 쓰고, 그 뒤는 Transfermarkt와 FotMob 경기 기록이 같이 적은 도움을 기준으로 함. 한쪽에만 있는 도움은 다른 출처 2곳(경기 기사·문자중계)이 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 리포트 도움 {TM_A_ALL}개 − PK 유도 {EX['PK 유도']}개 − 슈팅 리바운드 {EX[SHOT]}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 − 2014.8 이후 Transfermarkt에만 있고 확인되지 않은 {EX['2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)']}개. 본인 PK 골에 본인 도움으로 적힌 3개(2014.8.31 라치오전·2014.9.14 파르마전·2015.1.10 토리노전)는 처음부터 도움으로 세지 않음",
    "PK 유도로 뺀 도움: " + jl("PK 유도"),
    "슈팅 리바운드로 뺀 도움: " + jl("슈팅 리바운드('Shot on goal')") + ". 상대 자책골 유도로 뺀 도움: " + jl("상대 자책골 유도"),
    "2014.8 이후 Transfermarkt에만 있어 뺀 도움: 2017.1.31 쿠프 드 프랑스 디종전 90+2분 라보르드 골(다른 기록·기사에 도움자 없음), 2018.2.13 모렐리아전 5분 도밍게스 골·2018.3.17 톨루카전 2분 이바라 골(ESPN 한 곳만 메네즈 도움), 2018.5.2 리길야 8강 1차전 푸마스전 38분 우리베 골(기사는 스로인 뒤 중거리 슛으로만 적음). FotMob은 2018년 클루브 아메리카 경기의 도움 칸이 모두 빔",
    "2014.8 이후 FotMob 경기 기록에 도움이 없지만 다른 출처 2곳으로 확인해 넣은 도움: 2018.5.5 리길야 8강 2차전 푸마스전 4분 우리베 골(TUDN·Vanguardia: 메네즈와 만든 역습), 2018.5.13 리길야 준결승 2차전 산토스전 23분 발데스 헤더(ESPN·Mediotiempo: 메네즈 코너킥)",
    "FotMob에만 있는 도움 1개는 넣지 않음: 2017.2.28 쿠프 드 프랑스 로리앙전 61분 라보르드 골(Transfermarkt는 도움 없는 탭인)",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처. FotMob 경기 기록은 2011-12~2013-14 도움 칸이 거의 비어 있어 대조하지 못했고, 2010-11은 FotMob과 같음",
    "날짜는 경기 현지 날짜. 클루브 아메리카의 멕시코·북중미 저녁 경기(14경기)는 Transfermarkt 리포트 날짜보다 하루 앞",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(토티·즐라탄·파스토레·카바니·루카스 모우라 등) 값을 먼저 쓰고({SAME_N}개 기록), 없으면 기존 선수 자료의 같은 팀·같은 시즌 값, 그다음 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 순위값에 넣음(리그2·세리에B·리가MX의 빈 순위는 이웃 순위값의 가운데값)",
    "리가MX 상대는 클라우수라 2018 정규리그 순위(Transfermarkt 순위표, 1위 톨루카)를 기존 리가MX 순위값(호나우지뉴·카모라네시 자료)에 넣음: " + ", ".join(f"{o} {e}" for o, e, lv in MX_USED),
    "순위표에 없거나 하위 리그인 상대는 당시 수준을 추정함(모두 '추정'): " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED + EST_MODEL),
    "대회 비중: 코파 이탈리아·쿠프 드 프랑스·쿠프 드 라 리그·코파 MX·튀르키예컵은 16강까지·8강·준결승·결승, 수페르코파 이탈리아나와 멕시코 캄페온 데 캄페오네스는 국내컵 결승, 멕시코 리길야(8강·준결승)는 MLS 플레이오프, 북중미 챔스 16강, 2019 리그스컵 8강은 리그스컵 토너먼트, UEFA컵 2004-05 32강·유로파 2009-10 32강은 유로파 토너먼트, 유로파 예선(2009 헨트·코시체, 2011 디페르당주)은 유로파 예선으로 계산함",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(UEFA 대회와 코파 이탈리아 준결승: 원정 다득점·연장 적용. 멕시코 리길야: 원정 다득점·연장 없음 — 실제 규정은 합산 동률이면 정규리그 상위 팀 진출)",
    "시즌은 소쇼는 7월 10일 기준(2005.7.30 리그1 개막전 툴루즈전 = 2005-06), 클루브 아메리카도 7월 10일 기준(2018년 1~5월 클라우수라 = 2017-18, 2019년 7월 캄페온 데 캄페오네스·아페르투라 2019 개막전·리그스컵 = 2019-20, Transfermarkt 시즌 구분과 같음. 영어 위키백과는 2019년 7월 경기를 2018-19에 넣음), 나머지 클럽은 8월 1일 기준",
    "우승 기록은 Transfermarkt 업적 페이지 기준(PSG 리그1 2회·쿠프 드 라 리그 1회, 클루브 아메리카 코파 MX 클라우수라 2019·캄페온 데 캄페오네스 2019). 업적 페이지는 쿠프 드 라 리그 2014-15도 적지만 그 대회 전에 PSG를 떠나 넣지 않음",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elq", "lg", "mlp"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE):
        sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6], r[13])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mdates = collections.Counter(m[0] for m in M)
for d, rs in by.items():
    gl = sorted([r for r in rs if r[0] == "g"], key=lambda r: (r[5] + r[6], r[4]))
    for a, b in zip(gl, gl[1:]):
        if b[5] < a[5] + 1 or b[6] < a[6]: problems.append(("스코어 역순", d, a[4], b[4]))
    allr = sorted(rs, key=lambda r: r[4])
    for a, b in zip(allr, allr[1:]):
        if b[5] < a[5] or b[6] < a[6]: problems.append(("시간순 스코어 역행", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
    if mdates[d] > 1: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if MISS: sys.exit("상대 Elo 없음: " + str(MISS))
js = f"const MEN_E={J(E)};\nconst MEN_M={J(M)};\nconst MEN_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg,
           "post_gap_tm_only": post_gap_log, "post_gap_verdicts": POST_GAP, "fm_only_assists": FM_ONLY, "fm_only_seen": fm_only_seen,
           "fm_goal_diff": fm_goal_diff, "youth_excluded": [[g["date_local_tz_conv"], g["opponent"], g["playedMinutes"]] for g in YOUTH],
           "minute_fixes": min_fix, "cross_check": cross, "elo_sources": ELO_SRC,
           "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("분 고침", min_fix)
print("FotMob PK 차이", fm_goal_diff)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if len(c) > 4 and c[4] != "일치": print("  대조:", c)
print("대조 요약", collections.Counter((c[0], c[4] if len(c) > 4 and c[0].endswith("골") else "") for c in cross))
