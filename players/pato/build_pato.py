#!/usr/bin/env python3
"""알레샨드리 파투 (Alexandre Pato, Transfermarkt 37579): raw/ -> pato.json + players/pato/pat.js (판정 근거는 judgments.md)

  python3 players/pato/build_pato.py [--out <data 폴더>]   # 파일 쓰기(기본 players/pato/pat.js; 스크래치 복사본 검증 때 --out <복사본>/src/data)
  python3 players/pato/build_pato.py --debug               # Elo 출처 로그만 출력
  python3 players/pato/build_pato.py --stat                # 요약·판정·동료 대조
  python3 players/pato/build_pato.py --ties                # 합산 행

호비뉴 build 스크립트(players/robinho, 같은 수집 형식)를 바탕으로 함. 순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의
parse()/value()로 라벨에서 계산(v1.226 규칙, 직접 숫자를 넣지 않음). 입력: raw/tm_games.csv(출전·분·날짜 후보), raw/tm_events.csv(리포트 골 목록),
raw/tm_match_info.csv(리포트 머리·다른 차전), raw/fotmob_tm_map.csv(FotMob 경기 시각), raw/fotmob_events.csv·fotmob_playerMatches.csv(도움 대조),
raw/espn_pato_check.csv(ESPN 도움 대조), raw/ranks.txt(순위표), elo/opponent_elo_by_team_season.csv + aliases.csv,
src/data/*.js(git에 올라간 다른 선수 자료) + 같은 차례 판정이 끝난 players/{montella,quaresma,kanoute,morientes}/*.js(같은 경기 값 맞춤, 읽기만).
보조: assist_checks.py(2014.8 이후 도움 웹 확인), man_elo.py(순위표 밖 상대 라벨). 스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime, io, contextlib
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "pat.js")
OUT_JSON = os.path.join(HERE, "pato.json")
ME = "37579"
ME_KO = "알레샨드리 파투"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["status"] == "OK"}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}
ESPN = collections.defaultdict(list)
for r in rd("espn_pato_check.csv"): ESPN[r["gameId"]].append(r)

# ---------------------------------------------------------------- 날짜
# 브라질(인테르나시오나우·코린치안스·상파울루)·올랜도: TM 리포트·일정 날짜는 중부 유럽 날짜라 저녁 경기가 하루 밀림 → 경기 시각(UTC)을
#   경기장 시간대로 바꾼 날짜. FotMob 경기 시각이 있으면(2010 이후) 그것, 없으면 TM API 시각. TM 시각이 12:00/13:00/22:00 UTC 정각이면
#   시각 미상 자리값 → 일정 날짜(호비뉴·테베스 선례). 인테르나시오나우 2006~2007은 ESPN 경기 시각(scoreboard API, 2026-11-20 조회)으로 확인한 날짜.
# 유럽·중국 경기: TM 일정 날짜와 바꾼 날짜가 모두 같음(빌드에서 확인).
DATE_FIX = {
    "73327": "2007-05-13",   # 브라질 세리에 A 2007 1라운드 인테르나시오나우 2-3 보타포구: TM 5.3(시각 자리값) → ESPN 경기(event 216829) 2007-05-13 19:00Z, mundobotafogo 경기 기록 13.05.2007
}
INTER_ESPN = {   # ESPN 경기 시각 → 브라질(남부) 현지 날짜(원정은 경기장 시간대). TM 날짜와 같은 것도 확인 기록으로 둠
    "2533990": "2006-11-26", "3298402": "2007-02-28", "3298404": "2007-03-14", "3298406": "2007-03-28", "3298408": "2007-04-10",
    "3298410": "2007-04-19", "73334": "2007-05-19", "73344": "2007-05-26", "73362": "2007-06-10", "73506": "2007-07-14",
    "73425": "2007-07-18", "73514": "2007-07-21", "73537": "2007-07-25", "80739": "2007-08-01",
}
AMERICAS = ("6600", "199", "585", "45604")
DATE_LOG = []
def _conv(utc, tz):
    return datetime.datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(ZoneInfo(tz)).date().isoformat()
def _ldate(g):
    gid = g["gameId"]
    if gid in DATE_FIX: return DATE_FIX[gid], "fix"
    sched = g["date_local_schedule"]
    if g["club_id"] not in AMERICAS:
        conv = _conv(g["date_utc"], g["tz_used"])
        if conv != sched: sys.exit("유럽·중국 날짜 불일치 " + gid)
        return sched, "tm"
    if gid in INTER_ESPN: return INTER_ESPN[gid], "espn"
    if gid in FMMAP: return _conv(FMMAP[gid]["fotmob_utc"], g["tz_used"]), "fm"
    u = datetime.datetime.fromisoformat(g["date_utc"])
    if (u.hour, u.minute) in ((12, 0), (13, 0), (22, 0)) and g["club_id"] == "6600": return sched, "sched"
    if (u.hour, u.minute) in ((12, 0), (13, 0)): return sched, "sched"
    return g["date_local_tz_conv"], "conv"
LD = {}
for gid, g in G.items():
    LD[gid], how = _ldate(g)
    if LD[gid] != g["date_local_schedule"]: DATE_LOG.append((gid, g["date_local_schedule"], LD[gid], how, g["opponent"]))
def ldate(g): return LD[g["gameId"]]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BRA1", "ES1", "GB1", "IT1", "CSL", "MLS1"}
STATE = {"BCP1", "BCPF", "BRRS"}   # 파울리스타(1단계·결선)·가우슈: 국내컵 낮은 비중(호비뉴·디에구 코스타·네이마르 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid in ("CDR", "BRC", "CIT", "CHFA", "MLSP"):   # MLSP = US 오픈컵(TM 코드)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SCI", "RECO"): return "df"   # 수페르코파 이탈리아나·레코파 수다메리카나 = 국내컵 결승 비중(디에구·리켈메 선례)
    if cid == "KLUB": return "cwc"
    if cid == "POUS": return "mlp"   # MLS 컵 플레이오프(TM 코드 POUS) 1라운드
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "CLQ": return "clq"
    if cid == "UEFA":   # UEFA컵 2008-09: 1라운드 = 유로파 예선, 조별 = 유로파 조별, 32강(TM '3rd round') = 유로파 토너먼트(호비뉴·디에구 선례)
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        return "elk"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid in ("AFCL", "ACLQ"):   # AFC 챔스: 조별·16강·예선 플레이오프 = 리그 단계 비중, 8강 이후 높은 비중(bzm·aou 선례)
        if r.startswith("quarter"): return "aclk"
        if r.startswith("semi"): return "aclsf"
        if r.startswith("final"): return "aclf"
        return "acl"
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"
    if cid == "CS":
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g):
    return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    r = rnd.lower()
    if cid in ("CL", "UEFA", "EL", "CLQ", "CDR", "CIT"): return (1, 1)
    if cid in ("AFCL", "CHFA"): return (1, 1)          # AFC 대회 2022 시즌까지 원정 다득점·연장(docs 3절), 중국 FA컵 같게(엘샤라위 els.js 선례)
    if cid in ("CLI", "CS"):
        if d >= "2022-01-01": return (0, 0)             # 2022부터 원정 다득점 폐지, 연장 없이 승부차기(루카스 2023 선례)
        if cid == "CLI" and r.startswith("final") and d >= "2008-01-01": return (0, 1)
        return (1, 0)
    if cid == "BRC": return (1, 0) if d < "2018-01-01" else (0, 0)   # 코파 두 브라질 2017까지 원정 다득점(호비뉴·디에구 코스타 선례)
    if cid == "BCPF": return (0, 0)                     # 주 선수권 결선: 원정 다득점·연장 없음(네이마르 선례)
    if cid == "RECO": return (0, 1)                     # 레코파: 리켈메·팔레르모 2008 선례(원정 다득점 없이 연장, 규정 미확인 추정)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; oid = m["other_leg_id"]; club = G[gid]["club_id"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split(":"))
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    return (oh, oa) if side_of(gid) == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    oid = MI[gid]["other_leg_id"]
    if oid in G and G[oid]["gameState"] == "penalty_shootout": sys.exit("다른 차전이 승부차기 " + gid)
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
# TM played인데 출전 분 빈칸: 2007.3.21 가우슈 글로리아전(4703212, isStarting False, 리포트에 파투 교체 기록 있는지는 judgments 2절)
MIN_EST = {"4703212": 41}   # 리포트: 크리스치앙과 교체 투입(시각 미기록) → 인테르나시오나우 교체 출전 3경기 평균 41분(카카 kak.js 선례)
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    if g["gameId"] in MIN_EST: M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), MIN_EST[g["gameId"]], 1]); continue
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

A_CHECK = {}
def a_key(gid, minute): return f"{gid}|{minute}"
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())   # A_CHECK 채움(근거 포함)
# 골 판정(TM 골을 빼는 것): gid|분 -> 이유
G_EXCL = {}
exec(open(os.path.join(HERE, "goal_checks.py"), encoding="utf-8").read())

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["pato_assist"] == "1" and fm_min_match(f, e["minute"]): return True
    return False
def fm_pm_assists(gid):
    m = FMMAP.get(gid)
    if m and m["fotmob_matchId"] in FMPM: return int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
    return None
def espn_assist(gid, e):
    for r in ESPN.get(gid, []):
        if r["role"] != "goal" and r["minute_tm"] == e["minute"] and r["espn_names_pato"] == "1": return True
    return False

def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

A_STATUS = []   # 2014.8 이후 도움 판정 기록
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    k = a_key(gid, e["minute"])
    if d < GAP:
        if k in A_CHECK and not A_CHECK[k][0]: return A_CHECK[k][1]
        return None
    fa, pm, es = fm_assist(gid, e), fm_pm_assists(gid), espn_assist(gid, e)
    if fa:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if pm and pm >= 1 and k not in A_CHECK:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], f"TM+FotMob 선수 경기 목록(도움 {pm})")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "2014.8 이후 단일 출처(확인 못 함)"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], f"판정 없음 ESPN={es} FMpm={pm}"))
    return "2014.8 이후 단일 출처(판정 없음)"

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e): sys.exit("파투 자책골 " + gid)
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e, ldate(g), gid)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            k = a_key(gid, e["minute"])
            if k in G_EXCL:
                judg.append(("골 제외", ldate(g), opp(g), e["minute"], G_EXCL[k])); continue
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk and e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
            if e["goal_desc"] == "Penalty rebound": judg.append(("PK 리바운드 골(PK 아님)", ldate(g), opp(g), e["minute"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

# FotMob 전용 도움(TM 도움 없음): 판정 기록만
FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["pato_assist"] == "1" and f["pen_shootout_event"] != "True":
            mi = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(e["assist_id"] == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, mi, f["scorer"]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    excl = sum(1 for k in G_EXCL if k.split("|")[0] == gid)
    if cnt_[(gid, "g")] + excl != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if (h, a) != (fh, fa) and G[gid]["gameState"] != "penalty_shootout": SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))

# ---------------------------------------------------------------- 이름·기존 자료
ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
MANUAL_ALIAS = {"inter milan": "inter"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if ME_KO in r["선수"].split("·"): continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
if not TRACKED:
    TRACKED = set(subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "clubcolors.js", "finals.js", "pat.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
# 같은 차례에 판정이 끝난 선수(아직 src에 없음): 같은 경기 값을 맞추려고 읽기만
SAME_ROUND = ["montella/mnt.js", "quaresma/qua.js", "kanoute/knt.js", "morientes/mor.js"]
for rel in SAME_ROUND:
    fn = os.path.join("/home/user/soc/players", rel)
    if os.path.exists(fn) and os.path.basename(fn) not in OTHERS:
        P, oe, om = load_js(fn); OTHERS[os.path.basename(fn)] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "paulista", "paulo", "ca", "cs", "deportivo", "deportes", "universidad", "san", "santa", "fk", "vfl", "bv",
        "racing", "arsenal", "juniors", "plate", "river", "nacional", "independiente", "estudiantes", "union", "boca", "gimnasia", "esgrima", "lorenzo", "almagro", "hotspur", "palace", "villa", "ham", "manchester", "verona", "sheffield", "bristol", "birmingham", "nottingham", "queens", "park", "west", "aston",
        "shanghai", "beijing", "guangzhou", "tianjin", "shandong", "jiangsu", "henan", "hebei", "chongqing", "changchun", "guizhou", "dalian", "new", "york", "los", "angeles", "toronto", "sporting"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
SA_DOM = {"CLI", "CS", "BRA1", "BCP1", "BCPF", "BRRS", "BRC", "CSL", "KLUB", "RECO", "CHFA", "AFCL", "ACLQ", "MLS1", "MLSP", "POUS"}
def same_match(o, d, cid):
    if cid in SA_DOM:   # 남미·중국·미국 대회는 같은 이름 다른 팀이 많아 정확한 이름(별칭) 일치만
        cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    else:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)] or [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위 라벨 → Elo (tools/league_rank_apply.py)
_LRA = {"__file__": os.path.join(ROOT, "tools", "league_rank_apply.py"), "__name__": "lra"}
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA["__file__"], encoding="utf-8").read().split("if __name__ == '__main__':")[0], "lra", "exec"), _LRA)
sys.argv = _argv
# 브라질 주 리그만 하는 팀(전국 리그 A~D 밖, '브라질 5부 YYYY 순위 없음'): v1.226에서도 순위 없이 남은 범주(docs 0절 v1.226 '순위 없음 192개 —
# 지역 아마추어·브라질 주 리그 전용 팀'). 같은 해 기존 자료 값(2007 제 호베르투 1197, 2013 네이마르·호나우지뉴·제 호베르투 1278)을 쓰고,
# 기존 값이 없는 2014는 호비뉴 자료의 방식(1200 + 그해 브라질 리그 이동 64)으로 1264.
BRA5_NORANK = {"2007": 1197, "2013": 1278, "2014": 1264}
def lv_value(lv, d):
    m_ = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv)
    if m_ and m_.group(1) == "브라질" and m_.group(2) == "5" and m_.group(3) in BRA5_NORANK:
        return BRA5_NORANK[m_.group(3)]   # 브라질 주 리그 전용 팀: 같은 해 기존 '순위 없음' 라벨 값(judgments 6절)
    if m_:   # 순위를 못 찾은 상대: 그 나라·단계 기준점(tools/league_rank_apply.py base())
        cal = m_.group(4) is None; y = int(m_.group(3)) + (0 if cal else 1)
        return int(round(_LRA["base"](_LRA["KO"][m_.group(1)], int(m_.group(2)), y, cal)))
    m2 = re.match(r"^필리핀 1부 (\d{4}) (\d+)위/(\d+)팀", lv)
    if m2:   # 필리핀: 도구의 나라 이름 표에 없어 같은 식으로 직접(Opta 'PFL|Philippines' 58.23)
        return _LRA["value"]("Philippines", 1, int(m2.group(1)), True, int(m2.group(2)), int(m2.group(3)))
    p = _LRA["parse"](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA["value"](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    return v

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1])

EU_LG = {"ES1": "라리가", "IT1": "세리에A", "GB1": "프리미어리그"}
def make_label(lg, season, v):
    r, n, nm, sraw = v
    if lg == "BRA1": return f"브라질 세리에 A {season} {r}위/{n}팀"
    if lg == "BRA2": return f"브라질 세리에 B {season} {r}위/{n}팀"
    if lg == "CSL": return f"중국 슈퍼리그 {season} {r}위/{n}팀"
    if lg in EU_LG:
        pre = EU_LG[lg]; n0 = _LRA["ERA"]["teams"](pre, int(season[:4]) + 1)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

CAL = {"BRA1", "BCP1", "BCPF", "BRRS", "BRC", "CSL", "CLI", "CS", "KLUB", "RECO", "CHFA", "AFCL", "ACLQ", "MLS1", "MLSP", "POUS"}
def seasons_for(cid, d, o):
    if cid == "ACLQ": return [str(int(d[:4]) - 1), d[:4]]   # 1~2월 예선: 막 끝난 시즌(필리핀 2017)
    if cid in ("CLI", "CS", "RECO", "KLUB", "AFCL", "ACLQ"):   # 분할 시즌 리그 상대는 시즌 키도(단계 표시 키 포함: 통합표가 라벨의 단계를 붙임)
        return [d[:4], eu(d)] + [x + st_ for x in (d[:4], eu(d)) for st_ in ("/Apertura", "/Clausura")]
    if cid in CAL: return [d[:4]]
    return [eu(d), d[:4]]

def lg_cands(cid, d, o):
    if cid in ("BRA1", "BCP1", "BCPF", "BRRS", "BRC", "CLI", "CS", "RECO"): return [("BRA1", d[:4]), ("BRA2", d[:4])]
    if cid in ("CSL", "CHFA", "AFCL", "ACLQ"): return [("CSL", d[:4])]
    s = eu(d)
    return [("ES1", s), ("IT1", s), ("GB1", s)]

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산)
def man(o, s, lv): MAN[(key(o), s)] = lv
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []

def opp_elo(o, d, cid):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    seasons = seasons_for(cid, d, o)
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
            p = _LRA["parse"](lv, d)
            if p and _LRA["value"](*p) not in (None, e): TABLE_DIFF.append((o, s, e, lv, _LRA["value"](*p)))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d); ELO_SRC["직접 라벨(순위표 밖)"] += 1
            ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    for lg, s in lg_cands(cid, d, o):
        t = RANKS.get((lg, s), {})
        if k in t:
            lv = make_label(lg, s, t[k])
            if lv:
                e = lv_value(lv, d); ELO_SRC["순위표 → 라벨"] += 1
                ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())   # 순위표 밖 상대 라벨(MAN)

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)

E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)
if "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    print("TABLE_DIFF", TABLE_DIFF)
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["pato_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "penalty" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))
FM_N = sum(1 for gid in EVS if gid in G and gid in FME and any(e["scorer_id"] == ME for e in EVS[gid]))
FM_G = sum(1 for gid in EVS if gid in G and gid in FME for e in EVS[gid] if e["scorer_id"] == ME and not is_og(e))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None): d.append(f"단판/합산 {a[7]}{a[14] if len(a) > 14 else ''}/{b[7]}{b[14] if len(b) > 14 else ''}")
    if a[10] != b[10]: d.append("연장")
    return d
G_BYDATE = {ldate(g): g["competitionId"] for g in GAMES}
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"\bPato\b", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(파투 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("파투 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) if G_BYDATE.get(r[9], "BRA1") in SA_DOM else same_team(x[1], r[1])):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm[1], m[1]) and mm[2] != m[2] and (key(mm[1]) == key(m[1]) or G_BYDATE.get(m[0], "BRA1") not in SA_DOM):
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 파투 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("intpt", "2007-08-02", "인테르나시오나우", "인테르나시오나우", "2006~2007"), ("acmpt", "2013-01-03", "AC 밀란", "밀란", "2007~2013"),
         ("corpt", "2014-02-14", "코린치안스", "코린치안스", "2013~2014"), ("saopt", "2016-01-29", "상파울루", "상파울루", "2014~2015"),
         ("chept", "2016-07-26", "첼시", "첼시", "2016"), ("vilpt", "2017-01-30", "비야레알", "비야레알", "2016~2017"),
         ("tqjpt", "2019-03-27", "톈진 취안젠", "톈진", "2017~2018"), ("saopt", "2021-02-13", "상파울루", "상파울루", "2019~2020"),
         ("orlpt", "2023-05-26", "올랜도 시티", "올랜도", "2021~2022"), ("saopt", None, "상파울루", "상파울루", "2023")]
TM_CLUB = {"6600": "intpt", "5": "acmpt", "199": "corpt", "585": "saopt", "631": "chept", "1050": "vilpt", "33714": "tqjpt", "45604": "orlpt"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
SCAL = ("intpt", "corpt", "saopt", "tqjpt", "orlpt")
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in SCAL: return str(y)
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("인테르나시오나우", "2007-08-02"), ("AC 밀란", "2013-01-03"), ("코린치안스", "2014-02-14"), ("상파울루(2014~2015 임대)", "2016-01-29"),
          ("첼시(임대)", "2016-07-26"), ("비야레알", "2017-01-30"), ("톈진 취안젠", "2019-03-27"), ("상파울루(2019~2020)", "2021-02-13"),
          ("올랜도 시티", "2023-05-26"), ("상파울루(2023)", "9999")]
def stint(d):
    for n, u in STINTS:
        if d < u: return n
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for n, u in STINTS)
for m in M: ST[stint(m[0])][0] += 1; ST[stint(m[0])][3] += m[3]
for r in E: ST[stint(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
def d_(x): y, m, d = x.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EXJ = [j for j in judg if j[0] == "도움 제외"]
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8] and r[1] in G and ldate(G[r[1]]) < GAP)
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A, UNTYPED)
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    print("FM only", FM_ONLY)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G, FM_CMP)
    print("SCORE_MISMATCH", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("dates changed", len(DATE_LOG), collections.Counter(x[3] for x in DATE_LOG))
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_pato.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl", "mlp"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6], r[13])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
mdates = collections.Counter(m[0] for m in M)
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
for d, rs in by.items():
    if d not in mdates: problems.append(("E 날짜가 M에 없음", d))
    gl = sorted([r for r in rs if r[0] == "g"], key=lambda r: r[4])
    for a, b in zip(gl, gl[1:]):
        if b[5] < a[5] + 1 and b[4] > a[4] and (b[5], b[6]) <= (a[5], a[6]): problems.append(("스코어 역순", d, a[4], b[4]))
for r in E:
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if not r[2] or r[12] == "?": problems.append(("Elo 없음", r))
mm_ = {m[0]: m for m in M}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const PAT_E={J(E)};\nconst PAT_M={J(M)};\nconst PAT_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "table_label_diffs": TABLE_DIFF, "date_changes": DATE_LOG, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
