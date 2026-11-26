#!/usr/bin/env python3
"""두샨 타디치 (Dušan Tadić, Transfermarkt 36139, FotMob 94267): raw/ -> tadic.json + players/tadic/dta.js (판정 근거는 judgments.md)

  python3 players/tadic/build_tadic.py [--out <data 폴더>]   # 기본 players/tadic/dta.js; 스크래치 검증 때 SOC_ROOT=<복사본> … --out <복사본>/src/data
  python3 players/tadic/build_tadic.py --debug               # Elo 출처 로그
  python3 players/tadic/build_tadic.py --stat                # 요약·판정·동료 대조

모라타 build 스크립트(같은 수집 형식)를 타디치의 리그·대회(세르비아 1부·에레디비시·프리미어리그·쉬페르리그·UAE 프로리그)에 맞춰 고친 것.
순위 라벨 행의 Elo는 tools/league_rank_apply.py parse()/value()(+ tools/league_points.py 승점 모형)로 라벨에서 계산.
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib, gzip

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "dta.js")
OUT_JSON = os.path.join(HERE, "tadic.json")
ME = "36139"
ME_KO = "두샨 타디치"
CUTOFF = "2026-11-25"
GAP = "2014-08-01"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["team_level"] == "senior"]   # 828경기, 2군·유스 경기 없음
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
XL = {r["gameId"]: r for r in rd("tm_two_leg_ties_extra.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["fotmob_matchId"]}
# ESPN 경기 기록(keyEvents·문자 중계 'Assisted by Dušan Tadić')이 같은 골에 타디치 도움을 적은 경우(TM과 다른 독립 출처)
ESPN_A = {(r["gameId"], r["minute_tm"]) for r in rd("espn_tadic_check.csv") if r["role"] == "assist" and (r["espn_names_tadic"] == "1" or r["espn_commentary_names_tadic"] == "1")}

# ---------------------------------------------------------------- 날짜·출전 분·이벤트 고침
# 2023.5.14 흐로닝언-아약스(TM 3852782): 경기 중 중단, 5.16 나머지 시간 재개(FotMob은 재개일). 시작일 기준(니코 윌리엄스·바렐라 선례) → TM 날짜 그대로
DATE_FIX = {}
MIN_FIX = {"1173773": 90}   # 2006.8.12 보라츠전: TM 출전 분 없음, 경기 기록상 0분 교체 투입(사실상 선발) → 90분 추정
EV_MIN_FIX = {}
# 2025.11.30 UAE 리그컵 8강 2차전 호르파칸-알와흐다(TM 4768270): TM 이벤트가 17분 호르파칸 골을 두 번 적음(최종 1-2와 모순).
# FotMob·UAE 프로리그 공식 기사(17분 로우렌시 1-0, 82분 디아라 1-1(타디치와 2대1 패스), 90+3분 디아라 1-2) → 두 번째 17분 행 버림
EV_DROP = {("4768270", "17", "2-0")}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local"])
def opp(g):
    return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
def rnd_of(g): return g["round"] or ""

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"SER1", "NL1", "GB1", "TR1", "UAE1", "PONL"}   # PONL = 에레디비시 유럽 대항전 플레이오프(리그 비중, 훈텔라르·코스티치 선례)
CUPS = {"NLP", "FAC", "CGB", "TRP", "SERP", "UAEP", "UALC"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "NLSC": return "df"   # 요한 크라위프 실드 = 국내컵 결승 비중
    if cid in CUPS:   # 16강까지 국내컵, 8강(FA컵 6라운드) 이후 단계별, 튀르키예컵 조별 = 국내컵
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or (cid == "FAC" and r.startswith("sixth")): return "dk"
        return "dc"
    if cid in ("UEQ", "ELQ"): return "elq"
    if cid == "CLQ": return "clq"
    if cid == "ECLQ": return "ecq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"   # 2026-27 리그 페이즈(TM 'Group Stage') 포함
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 녹아웃 플레이오프(intermediate stage)·16강·8강
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"
        if r.startswith("semi"): return "ecsf"
        if r.startswith("final"): return "ecf"
        return "eck"
    if cid == "ACLE": return "acl"   # AFC 챔스 엘리트 리그 스테이지·16강(단판)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

def tie_rule(cid, d, rnd):
    if cid in ("CL", "EL", "UCOL", "CLQ", "ELQ", "ECLQ", "UEQ"): return (int(d < "2021-07-01"), 1)
    if cid == "PONL": return (1, 1)    # 에레디비시 플레이오프 원정 다득점·연장(훈텔라르·코스티치 자료와 같음)
    if cid == "CGB": return (1, 1)     # 리그컵 준결승 2016-17 원정 다득점·연장(모라타 자료와 같음)
    if cid == "UALC": return (0, 0)    # UAE 리그컵: 원정 다득점·연장 없이 승부차기(페키르 자료와 같음)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["clubId"]: return "h"
    if m["away_id"] == g["clubId"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; club = G[gid]["clubId"]
    oid = m["other_leg_id"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, re.match(r"(\d+)-(\d+)", o["final"]).groups())
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    if gid in XL:
        a, b = map(int, XL[gid]["other_leg_score_club_opp"].split("-")); return (a, b)
    sys.exit("다른 차전 없음 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if ("1st" in rnd or "first leg" in rnd) else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    row = [ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), MIN_FIX.get(g["gameId"], int(g["playedMinutes"] or 0))]
    if g["gameId"] in MIN_FIX: row.append(1)
    M.append(row)

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0
def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())
def same_scorer(a, b):
    ta, tb = norm(a).split(), norm(b).split()
    return bool(ta and tb and ta[-1] == tb[-1])
def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["tadic_assist"] == "1" and f["pen_shootout_event"] != "True" and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])): return True
    return False

# 2014.8 이후 TM 도움 중 FotMob 경기 이벤트가 확인하지 않은 일반 유형: 다른 출처로 판정(judgments.md 4절)
# 'FotMob 선수 경기 목록' = 그 경기 FotMob 선수별 도움 수가 TM과 같음(이벤트에 도움자 없음; 아즈문·미토마 선례)
A_CHECK = {
 "2485815|53": (True, "2014.8.26 리그컵 밀월 원정 53분 코크 골: Sky Sports('headed in Dusan Tadic's corner')·Sports Mole('headed in from a Dusan Tadic corner')·ESPN(PA, 'nod Tadic's cross')"),
 "3141139|63": (True, "2019.3.10 포르튀나 시타르트전 63분 네레스 골: FotMob 선수 경기 목록 도움 1(그 경기 FotMob 이벤트상 타디치 도움일 수 있는 골은 63분뿐)·Voetbalkrant 경기 기록('Doelpunt van David Neres Campos (Dusan Tadic)' 63분). NH Nieuws는 지예흐 패스로 서술(출처 엇갈림, 사용자 확인 후보)"),
 "3216187|63": (False, "2019.12.22 ADO 덴하흐전 63분 트라오레 골: 아약스 공식 기사만 타디치 패스 → 헤더, FotMob 선수 경기 목록 도움 1은 39분 흐라펜베르흐 골(이벤트 일치), 다른 기사는 타디치 슈팅이 막힌 뒤 리바운드로 서술 — 출처 엇갈려 뺌"),
 "3450725|70": (True, "2021.4.22 위트레흐트전 70분 알바레스 골: NOS('rondde de assist van Tadic af')·NH Nieuws('uit een voorzet van Tadic')"),
 "4708046|65": (True, "2025.8.17 아지만 원정 65분 흐리빈 골: FotMob 선수 경기 목록 도움 1·UAE 프로리그 공식 기사(타디치가 컷인 뒤 흐리빈에게 내줌)"),
 "4727956|37": (True, "2025.9.19 알다프라전 37분 크루스프스키 골: FotMob 선수 경기 목록 도움 2(TM 1)·경기 문자 중계(mykhel, 'Assisted by Dusan Tadic')"),
 "4727977|45+2": (True, "2025.10.30 알나스르전 45+2분 크루스프스키 골: FotMob 선수 경기 목록 도움 1"),
 "4763349|12": (True, "2026.1.6 바니야스전 12분 흐리빈 골: FotMob 선수 경기 목록 도움 3·UAE 프로리그 공식 기사(전반 도움 3개)"),
 "4763349|18": (True, "2026.1.6 바니야스전 18분 흐리빈 골: FotMob 선수 경기 목록 도움 3·UAE 프로리그 공식 기사"),
 "4763349|45+4": (True, "2026.1.6 바니야스전 45+4분 흐리빈 골: FotMob 선수 경기 목록 도움 3·UAE 프로리그 공식 기사(리그 기사는 49분으로 적음)"),
 "4763357|69": (True, "2026.1.17 알아인 원정 69분 흐리빈 골: FotMob 선수 경기 목록 도움 1·UAE 프로리그 공식 기사(타디치의 스루패스)"),
 "4768474|74": (False, "2026.2.1 UAE 대통령컵 8강 유나이티드 FC전 74분 흐리빈 골: FotMob 경기 자료 없음, Sharjah24 등 기사에 도움자 없음 — 확인 안 됨"),
 "4807974|67": (True, "2026.2.25 아지만전 67분 흐리빈 골: FotMob 선수 경기 목록 도움 1·UAE 프로리그 공식 기사(타디치 크로스를 헤더)·mykhel 문자 중계"),
 "4857470|18": (True, "2026.4.23 샤르자 원정 18분 카이우 카네두 골: FotMob 선수 경기 목록 도움 2·Tigerscores 경기 기록"),
 "4857470|90+2": (True, "2026.4.23 샤르자 원정 90+2분 간디푸르 골: FotMob 선수 경기 목록 도움 2·Tigerscores 경기 기록"),
 "4869486|35": (True, "2026.5.6 알와슬전 35분 크루스프스키 골: FotMob 선수 경기 목록 도움 1"),
}
# FotMob만 적은 도움(TM 도움자 없음): 다른 출처 2곳이 확인한 것만 넣음
ADD_A = [
 ("3528475", 20, 0, 0, 0, "David Neres"),    # 2021.3.18 유로파 16강 2차전 영보이스 원정 20분 네레스 골: FotMob 이벤트·NOS('op aangeven van Dusan Tadic')·Fox Sports 경기 기록(타디치 1골 1도움). 분은 TM(FotMob 21분)
 ("4718308", 12, 0, 0, 0, "Arnau Pradas"),   # 2025.8.31 UAE 리그컵 16강 1차전 아지만전 12분 프라다스 골: FotMob 이벤트·UAE 프로리그 공식 기사('a precise through ball from Dusan Tadic')
]
A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도('Penalty: Fouled player')"
    if t == "Handball (opponent)": return "상대 핸드볼 반칙 PK를 도움으로 적은 행"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    k = f"{gid}|{e['minute']}"
    if d < GAP:
        return None
    if fm_assist(gid, e):
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if (gid, e["minute"]) in ESPN_A and k not in A_CHECK:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+ESPN 경기 기록")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else why
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음"))
    return "2014.8 이후 단일 출처(판정 없음)"

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        if (gid, e["minute"], e["score_home_away_after"]) in EV_DROP: continue
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and is_og(e): judg.append(("본인 자책골(골 아님)", ldate(g), opp(g), e["minute"]))
        if e["scorer_id"] == ME and e["assist_id"] == ME: judg.append(("본인 PK 자기 도움(도움 아님)", ldate(g), opp(g), e["minute"]))
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(EV_MIN_FIX.get((gid, e["minute"]), e["minute"]))
        if is_a:
            why = assist_reason(e, ldate(g), gid)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if sd != side: sys.exit("도움 편 이상 " + gid)
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))
for gid, mi, dm, gf, ga, scorer in ADD_A:
    raw_rows.append(("a", gid, mi, dm, gf, ga, 0, scorer))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["tadic_assist"] == "1" and f["pen_shootout_event"] != "True":
            if not any(e["assist_id"] == ME and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, int(f["time"]) + int(f["overloadTime"] or 0), f["scorer"]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

# ---------------------------------------------------------------- 이름·기존 자료
ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
MANUAL_ALIAS = {"fk hajduk 1912": "fk hajduk kula", "fk borac 1926 cacak": "fk borac cacak"}   # TM 경기 이름 ↔ TM 순위표 이름(같은 팀)
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue   # 이 선수만 쓴 팀-시즌만 건너뜀
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "dta.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
PAR = {}   # 이번 회차 병렬 판정(읽기만)
for slug in ("firmino", "hulk", "nkunku", "defoe"):
    for pth in glob.glob(os.path.join(os.path.dirname(HERE), slug, "*.js")):
        try: P, oe, om = load_js(pth)
        except Exception: continue
        PAR["players/" + slug + "/" + os.path.basename(pth)] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss", "us", "vfl", "vfb", "tsg",
        "real", "madrid", "borussia", "bayer", "eintracht", "hamburger", "olympique", "atletico", "athletic", "fk", "sk", "bv", "1899", "1909", "1907", "1913", "1846", "05", "04", "96", "1919",
        "united", "city", "al"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d, cid):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    if not cand:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if toks(x[1]) and toks(x[1]) == toks(o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위 라벨 → Elo (tools/league_rank_apply.py)
_LRA = {"__file__": os.path.join(ROOT, "tools", "league_rank_apply.py"), "__name__": "lra"}
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA["__file__"], encoding="utf-8").read().split("if __name__ == '__main__':")[0], "lra", "exec"), _LRA)
sys.argv = _argv
sys.path.insert(0, os.path.join(ROOT, "tools"))
import league_points as PTS
MAPNEED = []
def lv_value(lv, d, o=None):
    p = _LRA["parse"](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA["value"](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    if o is not None:
        b = _LRA["base"](p[0], p[1], p[2], p[3]); sdv = _LRA["sd"](p[0], p[1])
        if p[1] == 1 and p[0] in _LRA["BIG"]:
            vp = PTS.value(lv, o, b, sdv, _LRA["cv"])
        else:
            vp = PTS.value_other(lv, o, p[0], p[1], b, sdv, _LRA["cv"])
            hd = re.match(r"^(.*?) \d+위", lv.split(" (")[0])
            ent = PTS.O["seasons"].get(hd.group(1)) if hd else None
            if vp is None and ent and "skip" not in ent and not ent.get("ongoing"):
                MAPNEED.append((hd.group(1), o, lv))
        if vp is not None: v = vp
    return v

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

PEN = json.load(open(os.path.join(ELO, "penalty_seasons.json"), encoding="utf-8"))
NOW = "2026년 11월 25일 현재 순위"
def make_label(lg, season, v):
    r, n, nm = v
    if lg == "SER1": return f"세르비아 1부 {season} {r}위/{n}팀 (Serbian SuperLiga)"
    if lg == "NL1":
        if season == "2026-27": return f"에레디비시 2026-27 {r}위/{n}팀 ({NOW})"
        return f"에레디비시 {season} {r}위"
    if lg == "NL2": return f"에이르스터 디비시(네덜란드 2부) {season} {r}위/{n}팀 (Eerste Divisie)"
    if lg == "GB1": return f"프리미어리그 {season} {r}위"
    if lg == "GB2": return f"챔피언십 {season} {r}위/{n}팀"
    if lg == "GB3": return f"잉글랜드 3부 {season} {r}위/{n}팀 (EFL League One)"
    if lg == "TR1": return f"쉬페르리그 {season} {r}위/{n}팀"
    if lg == "UAE1": return f"UAE 프로리그 {season} {r}위/{n}팀 (UAE Pro League)"
    if lg == "UAE2": return f"UAE 2부 {season} {r}위/{n}팀 (UAE First Division League, 리그 수준 추정)"
    if lg == "SL1": return f"슬로베니아 1부 {season} {r}위/{n}팀 (Slovenian PrvaLiga)"
    if lg == "TS1": return f"체코 1부 {season} {r}위/{n}팀 (Czech First League)"
    if lg == "ZYP1" and season == "2026-27": return f"키프로스 1부 2026-27 {r}위/{n}팀 (Cypriot First Division, {NOW})"
    if lg == "FI1": return f"핀란드 1부 {season} {r}위/{n}팀 (Veikkausliiga)"
    if lg == "SE1": return f"스웨덴 1부 {season} {r}위/{n}팀 (Allsvenskan)"
    return None

def eu(d):
    y = int(d[:4]); m = int(d[5:7]); s_ = y if m >= 8 else y - 1
    if y == 2020 and m == 8: s_ = 2019
    return f"{s_}-{str(s_ + 1)[2:]}"
# 7~8월 예선 상대의 리그 시즌: 그 리그 새 시즌이 아직 시작 전이면 끝난 시즌(몰도바 2023-24는 2023.8.5 개막, 그리스 2026-27은 2026.8.22 개막 — 영어 위키백과 시즌 문서)
QSEASON = {("FC Zimbru Chisinau", "2023-08-01"): "2022-23", ("Olympiacos Piraeus", "2026-08-11"): "2025-26"}
def seasons_for(cid, d, o=None):
    if (o, d) in QSEASON: return [QSEASON[(o, d)]]
    return [eu(d), d[:4]]
CAL_LG = {"FI1", "SE1"}

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv
def man(o, s, lv): MAN[(key(o), s)] = lv
# 안도라 2011-12(7월 예선 = 끝난 시즌): 영어 위키백과 시즌 문서 챔피언십 라운드 최종 3위/8팀(1위 루지타노스·2위 FC 산타콜로마)
man("UE Santa Coloma", "2011-12", "안도라 1부 2011-12 3위/8팀 (Primera Divisió)")
# 네덜란드 3부(트베이더 디비시) 2019-20: 코로나로 중단, 중단 시점 7위/18팀(영어 위키백과 시즌 문서), 세미프로 리그
man("SV Spakenburg", "2019-20", "네덜란드 3부 2019-20 7위/18팀 (Tweede Divisie, 코로나로 중단된 시즌의 중단 시점 순위, 리그 수준 추정)")
# 세르비아 1부 2007-08: TM 표는 스메데레보 9위지만 OFK 베오그라드와 승점 36 동률에 상대 전적으로 10위(RSSSF·영어 위키백과 최종 순위)
man("FK Smederevo 1924", "2007-08", "세르비아 1부 2007-08 10위/12팀 (Serbian SuperLiga)")
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def opp_elo(o, d, cid, g):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    for s in seasons_for(cid, d, o):
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d, o); ELO_SRC["직접 라벨(순위표 밖)"] += 1
            ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
            p = _LRA["parse"](lv, d)
            if p and lv_value(lv, d, o) != e: TABLE_DIFF.append((o, s, e, lv, lv_value(lv, d, o)))
            return e, lv
    for lg in ("SER1", "NL1", "NL2", "GB1", "GB2", "GB3", "TR1", "UAE1", "UAE2", "SL1", "TS1", "ZYP1", "FI1", "SE1"):
        s = d[:4] if lg in CAL_LG else eu(d)
        t = RANKS.get((lg, s), {})
        if k in t:
            lv = make_label(lg, s, t[k])
            if lv is None: continue
            pen = PEN["changes"].get(lv.split(" (")[0].rsplit(" ", 1)[0]) if isinstance(PEN.get("changes"), dict) else None
            e = lv_value(lv, d, o); ELO_SRC["순위표 → 라벨"] += 1
            ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    MISS.append((o, d, cid, eu(d))); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, g)
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
    print("MAPNEED", sorted(set(MAPNEED)))
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14 or r[7]: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14] if len(r) > 14 else "")
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["tadic_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "1")]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "pen" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 0): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
FM_N = sum(1 for gid in EVS if gid in G and gid in FME and any(e["scorer_id"] == ME and not is_og(e) for e in EVS[gid]))
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
def same_team(a, b, d):
    if key(a) == key(b): return True
    return bool(toks(a)) and toks(a) == toks(b)
CROSS = []
VRE = re.compile(r"Tadi[cć]|타디치")
G_DATES = {ldate(g) for g in GAMES}
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for x in oe:
        if x[0] == "a" and VRE.search(str(x[13] or "")) and x[9] in G_DATES:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(타디치 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1], r[9])]
            if hit: CROSS.append(("타디치 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x[1], r[1], r[9]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], x[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and key(mm[1]) == key(m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[2], m[2]))
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2], x[9]):
                    CROSS.append(("TM 타디치 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
SHARED = collections.Counter()
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for m in M:
        if any(mm[0] == m[0] and (key(mm[1]) == key(m[1]) or same_team(mm[1], m[1], m[0])) for mm in om): SHARED[b] += 1

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("vojdta", "2010-07-01"), ("grodta", "2012-07-01"), ("twedta", "2014-07-08"), ("soudta", "2018-07-03"), ("ajxdta", "2023-07-16"),
         ("fendta", "2025-08-08"), ("wahdta", "2026-07-27"), ("necdta", None)]
TM_CLUB = {"448": "vojdta", "202": "grodta", "317": "twedta", "180": "soudta", "610": "ajxdta", "36": "fendta", "161": "wahdta", "467": "necdta"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["clubId"])
PERIODS = [("보이보디나", "2006~2010", None, "2010-07-01"), ("흐로닝언", "2010~2012", "2010-07-01", "2012-07-01"),
           ("트벤테", "2012~2014", "2012-07-01", "2014-07-08"), ("사우샘프턴", "2014~2018", "2014-07-08", "2018-07-03"),
           ("아약스", "2018~2023", "2018-07-03", "2023-07-16"), ("페네르바흐체", "2023~2025", "2023-07-16", "2025-08-08"),
           ("알와흐다", "2025~2026", "2025-08-08", "2026-07-27"), ("NEC", "2026~", "2026-07-27", None)]
def per(lo, hi):
    inr = lambda d: (lo is None or d >= lo) and (hi is None or d < hi)
    return [sum(1 for m in M if inr(m[0])), sum(1 for r in E if r[0] == "g" and inr(r[9])),
            sum(1 for r in E if r[0] == "a" and inr(r[9])), sum(m[3] for m in M if inr(m[0]))]
ST = [(n, y, per(lo, hi)) for n, y, lo, hi in PERIODS]
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
def d_(x): y, m, d = x.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
if "--stat" in sys.argv:
    for v in ST: print(v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), "TM_A", TM_A)
    for j in judg: print(j)
    for a in A_STATUS:
        if a[4] != "TM+FotMob 이벤트": print(a)
    print("TM+FotMob", sum(1 for a in A_STATUS if a[4] == "TM+FotMob 이벤트"))
    print("FM only", FM_ONLY)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G, FM_CMP)
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF); print("MAPNEED", sorted(set(MAPNEED))); print("SHARED", SHARED.most_common())
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_tadic.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "elk", "cwc", "clg", "cl16", "ecq", "elq", "clq"]:
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
    gl = sorted(rs, key=lambda r: (r[4], r[5] + r[6]))
    for a, b in zip(gl, gl[1:]):
        if b[5] < a[5] or b[6] < a[6]: problems.append(("스코어 역순", d, a[4], b[4]))
for r in E:
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if not r[2] or r[12] == "?": problems.append(("Elo 없음", r))
    if r[9] > CUTOFF: problems.append(("기준일 뒤", r))
mm_ = {m[0]: m for m in M}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const DTA_E={J(E)};\nconst DTA_M={J(M)};\nconst DTA_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()}, "map_need": sorted(set(MAPNEED)),
               "table_label_diffs": TABLE_DIFF, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for v in ST: print(" ", v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
