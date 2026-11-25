#!/usr/bin/env python3
"""아르투로 비달 (Arturo Vidal, Transfermarkt 37666, FotMob 49939): raw/ -> vidal.json + players/vidal/avd.js (판정 근거는 judgments.md)

  python3 players/vidal/build_vidal.py [--out <data 폴더>]   # 파일 쓰기(기본 players/vidal/avd.js; 스크래치 복사본 검증 때 --out <복사본>/src/data)
  python3 players/vidal/build_vidal.py --debug               # Elo 출처 로그
  python3 players/vidal/build_vidal.py --stat                # 요약·판정·동료 대조

혼다 build 스크립트(같은 판정 방식)를 바탕으로 함. 순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의
parse()/value()(+ tools/league_points.py 승점 모형)로 라벨에서 계산(v1.226·v1.290 규칙). 같은 경기가 다른 선수 자료에 있으면 그 값,
같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값. 칠레 2005~2007 순위는 알렉시스 산체스 자료와 같은
방식(es.wiki 연간 합산표, 2007은 아페르투라 표; 같은 팀-시즌 값을 맞추려고 동료 자료 형식을 따름).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "avd.js")
OUT_JSON = os.path.join(HERE, "vidal.json")
ME = "37666"
ME_KO = "아르투로 비달"
CUTOFF = "2026-11-25"
GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["fotmob_matchId"]}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 날짜·출전 분
# 날짜: TM API 경기 시각(UTC)을 경기장 시간대로 바꾼 현지 날짜(date_local_computed). 남미 저녁 경기 59경기는 TM 리포트 날짜(중부 유럽 시간)보다 하루 앞.
DATE_FIX = {}
# 2024 수페르코파(우아치파토전, TM 4253591): 2024.2.11 78분에 관중 소요로 중단, 남은 12분은 2024.11.13 랑카과 무관중 재개(es.wiki·라 테르세라·ESPN).
#   비달은 2.11 78분까지 뛰고 재개 경기에는 없음(ESPN·메가노티시아스 기사: 비달은 대표팀 소집으로 빠짐; FotMob 라인업 78분 교체 아웃) → 날짜는 시작일, 출전 78분(TM 90분은 틀림).
MIN_FIX = {"4253591": 78}
# 골 시각 고침: 2012 수페르코파 나폴리전 비달 PK 골 TM 67분 → 74분(FotMob 74분·ESPN 73분·영어·이탈리아어 위키백과 74분, '후반 30분쯤' 기사)
EV_MIN_FIX = {("2218677", "67"): "74"}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local_computed"])
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
def rnd_of(g): return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"CHLA", "CHL1", "L1", "IT1", "ES1", "BRA1", "CLPD"}
CUPS = {"DFB", "CIT", "CDR", "BRC", "CH1C"}        # 국내컵: 16강까지 dc, 8강 dk, 준결승 dsf, 결승 df (조별은 리그식 dc)
STATE = {"BRCG", "BRCF"}                            # 캄페오나투 카리오카(조별·결선): 국내컵 낮은 비중(쿠티뉴·데쿠·주니뉴 선례)
SUPER = {"DFL", "SCI", "CSUC", "SCBR", "RECO"}      # 슈퍼컵류(DFL-슈퍼컵·수페르코파 이탈리아나·칠레 수페르코파·수페르코파 두 브라질·레코파) = 국내컵 결승 비중
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid == "CLLC": return "dc"                   # 칠레 코파 데 라 리가 2026 조별(1부 팀 리그 컵) = 국내컵 조별(판단)
    if cid in SUPER: return "df"
    if cid == "SUC": return "dsf" if r.startswith("semi") else "df"   # 수페르코파 2020.1은 4팀(준결승 dsf)
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("CHLP", "CHPL"):                     # 칠레 플레이오프 = 멕시코 리길야 선례(알렉시스 자료와 같음)
        if r.startswith("final"): return "mlpf"
        if r.startswith("semi"): return "mlpsf"
        return "mlp"
    if cid == "KLUB": return "cwc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid in ("EL", "UEFA"):
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                # UEFA컵 3라운드·16강·8강, 유로파 2라운드(32강)·16강·8강
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"                                # 예선 2·3라운드도 lib(데파이·바스투스 선례), 조별·16강
    if cid == "CS":
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+\.?$", r): return 0
    return 1

def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    r = rnd.lower()
    if cid in ("CL", "EL", "ELQ", "UEFA"): return (int(d < "2021-07-01"), 1)
    if cid == "CDR": return (1, 1)                  # 코파 델 레이 2018-19까지 원정 다득점·연장
    if cid == "CIT": return (int(d < "2022-07-01"), 1)
    if cid in ("CHLP", "CHPL"): return (0, 0)       # 칠레 플레이오프: 알렉시스 자료와 같음(추정)
    if cid in ("CLI", "CS", "RECO"):                # CONMEBOL: 2005~2021 원정 다득점(2008부터 결승은 연장), 2022~ 없음(디에구 선례)
        if d >= "2022-01-01": return (0, 0)
        if r.startswith("final"): return (0, 1) if d >= "2008-01-01" else (1, 0)
        return (1, 0)
    if cid in ("BRC", "BRCF"): return (0, 0)        # 코파 두 브라질 2018~·카리오카 결선: 원정 다득점·연장 없음
    if cid == "CH1C": return (0, 0)                 # 코파 칠레: 합계 동률이면 바로 승부차기(추정)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; club = G[gid]["club_id"]
    oid = m["other_leg_id"] or (TIES[gid]["other_leg_id"] if gid in TIES else "")
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, re.match(r"(\d+):(\d+)", o["final"]).groups())
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    sys.exit("다른 차전 없음 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])

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
        if f["vidal_assist"] == "1" and f["pen_shootout_event"] != "True" and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])): return True
    return False
def fm_pm_assists(gid):
    m = FMMAP.get(gid)
    if m and m["fotmob_matchId"] in FMPM: return int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
    return None

# 2014.8 이후 TM 도움 중 FotMob이 비달 도움으로 적지 않은 것: 다른 독립 출처 2곳으로 판정(근거는 judgments.md 4절)
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())   # A_CHECK = {"gid|minute": (넣음?, 근거)}
A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도('Penalty: Fouled player')"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    k = f"{gid}|{e['minute']}"
    if d < GAP:
        if k in A_CHECK and not A_CHECK[k][0]: return A_CHECK[k][1]
        return None
    if fm_assist(gid, e) and k not in A_CHECK:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    pm = fm_pm_assists(gid)
    conf = sum(1 for x in EVS.get(gid, []) if x["assist_id"] == ME and x["scorer_id"] != ME and fm_assist(gid, x))
    if pm and pm > conf and k not in A_CHECK:   # FotMob 선수 경기 목록 도움 수가 이벤트로 확인된 것보다 많음(혼다 선례)
        A_STATUS.append((d, gid, e["minute"], e["scorer"], f"TM+FotMob 선수 경기 목록(도움 {pm})")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else ("슈팅 리바운드(크로스바에 맞고 나온 공)" if why.startswith("슈팅 리바운드") else "2014.8 이후 TM 단일 출처, 다른 출처 2곳 확인 못 함")
    A_STATUS.append((d, gid, e["minute"], e["scorer"], f"판정 없음 FMpm={pm}"))
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
        if e["scorer_id"] == ME and is_og(e): judg.append(("본인 자책골(골 아님)", ldate(g), opp(g), e["minute"]))
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(EV_MIN_FIX.get((gid, e["minute"]), e["minute"]))
        if is_a:
            why = assist_reason(e, ldate(g), gid)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk and e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
            if e["goal_desc"] == "Penalty rebound": judg.append(("PK 리바운드 골(PK 아님)", ldate(g), opp(g), e["minute"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))
# FotMob 단독 도움(TM 없음): 다른 출처 2곳이 확인하면 ADD_A로 넣음(assist_checks.py)
for gid, mi, dm, gf, ga, scorer in ADD_A:
    raw_rows.append(("a", gid, mi, dm, gf, ga, 0, scorer))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["vidal_assist"] == "1" and f["pen_shootout_event"] != "True":
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
MANUAL_ALIAS = {"inter milan": "inter"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue   # 이 선수만 쓴 팀-시즌만 건너뜀(오스카 빌드 수정과 같음)
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "avd.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
# 이번 회차 병렬 판정(읽기만): 귄도안·라키티치·포그바·크로스
PAR = {}
for slug in ("gundogan", "rakitic", "pogba", "kroos"):
    for pth in glob.glob(os.path.join(os.path.dirname(HERE), slug, "*.js")):
        try: P, oe, om = load_js(pth)
        except Exception: continue
        PAR["players/" + slug + "/" + os.path.basename(pth)] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss", "us", "vfl", "vfb", "tsg",
        "real", "borussia", "bayer", "eintracht", "hamburger", "olympique", "atletico", "athletic", "fk", "sk", "bv", "1899", "1909", "1907", "1913", "1846", "05", "04", "96"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
SA_DOM = {"CHLA", "CHL1", "CHLP", "CHPL", "CS", "CLI", "BRA1", "BRC", "BRCG", "BRCF", "RECO", "SCBR", "CLPD", "CH1C", "CLLC", "CSUC", "KLUB"}
def same_match(o, d, cid):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    if not cand and cid not in SA_DOM:
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
    if not p:
        if "순위 없음" in lv:   # 순위 없는 하부 리그: 그 단계 기준점(base)
            m_ = re.match(r"^(\S+) (\d)부 (\d{4})", lv)
            return int(round(_LRA["base"](_LRA["KO"][m_.group(1)], int(m_.group(2)), int(m_.group(3)), True)))
        sys.exit("라벨 해석 실패 " + lv)
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
        if len(p) < 5 or p[0] == "league" or "[TM table" in p[1]: continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

# 칠레 2005~2007(알렉시스 build와 같은 계산): es.wiki 연간 합산(2006 연간표 36경기, 2005 아페르투라+클라우수라 합, 2007 아페르투라 표)
def wiki_tables():
    T = collections.defaultdict(list)
    for line in open(os.path.join(RAW, "wiki_es_standings.txt"), encoding="utf-8"):
        if line.startswith("#"): continue
        f, ti, row = line.rstrip("\n").split("|", 2)
        c = [x.strip() for x in row.split(";")]
        if c[0] == "Pos": continue
        T[(f, int(ti))].append(c)
    return T
WT = wiki_tables()
def _rows(f, ti): return [(re.sub(r"\[.*?\]", "", c[1]).strip(), int(c[2]), int(c[3]), int(c[7]), int(c[8])) for c in WT[(f, ti)]]
def annual(year):
    if year == 2006:
        rows = [(n, p, gf - ga, gf) for n, p, pj, gf, ga in _rows("es_Torneo_Clausura_2006_(Chile).html", 8)]
    elif year == 2005:
        agg = collections.defaultdict(lambda: [0, 0, 0])
        for f in ("es_Torneo_Apertura_2005_(Chile).html", "es_Torneo_Clausura_2005_(Chile).html"):
            for n, p, pj, gf, ga in _rows(f, 7):
                a = agg[n]; a[0] += p; a[1] += gf - ga; a[2] += gf
        rows = [(n, *v) for n, v in agg.items()]
    elif year == 2007:
        rows = [(n, p, gf - ga, gf) for n, p, pj, gf, ga in _rows("es_Torneo_Apertura_2007_(Chile).html", 3)]
    else:
        return {}
    out = {}
    for n, p, dg, gf in rows:
        r = 1 + sum(1 for x in rows if (x[1], x[2], x[3]) > (p, dg, gf))
        out[key(n)] = (r, len(rows))
    return out
CHL_RANK = {y: annual(y) for y in (2005, 2006, 2007)}
CHL_LABEL = {2005: "아페르투라·클라우수라 합산", 2006: "연간 합산", 2007: "아페르투라"}
def chl_old(o, year):
    t = CHL_RANK.get(year) or {}
    GEN = {"cd", "csd", "club", "fc", "deportes", "de"}
    tk = lambda x: set(x.split()) - GEN
    k = key(o)
    cand = [kk for kk in t if tk(kk) and tk(k) and (tk(kk) <= tk(k) or tk(k) <= tk(kk))]
    cand = [c for c in cand if ("universidad" in c.split()) == ("universidad" in k.split())]
    if len(cand) != 1: return None
    r, n = t[cand[0]]
    return f"칠레 1부 {year} {CHL_LABEL[year]} {r}위/{n}팀 (리그 수준 추정)"

def make_label(lg, season, v):
    r, n, nm = v
    if lg == "CLPD":
        if season == "2026": return f"칠레 1부 2026 {r}위/{n}팀 (2026년 11월 25일 현재 순위)"
        return f"칠레 1부 {season} {r}위/{n}팀"
    if lg == "BRA1": return f"브라질 세리에 A {season} {r}위/{n}팀"
    return None

def eu(d):
    y = int(d[:4]); m = int(d[5:7]); s_ = y if m >= 8 else y - 1
    if y == 2020 and m == 8: s_ = 2019
    return f"{s_}-{str(s_ + 1)[2:]}"
CAL = SA_DOM
def seasons_for(cid, d):
    if cid in CAL: return [d[:4]]   # 남미·칠레 대회는 달력 연도만(유럽식 시즌 키로 같은 이름 유럽 팀(에버턴)과 섞이지 않게)
    return [eu(d), d[:4]]
def lg_cands(cid, d):
    y = d[:4]
    if cid in ("CLPD", "CH1C", "CLLC", "CSUC", "CLI"): return [("CLPD", y), ("BRA1", y)]
    if cid in ("BRA1", "BRC", "BRCG", "BRCF", "RECO", "SCBR"): return [("BRA1", y)]
    return []

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산)
def man(o, s, lv): MAN[(key(o), s)] = lv
exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())
FORCE = {}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def opp_elo(o, d, cid, g):
    if g["gameId"] in FORCE:
        lv = FORCE[g["gameId"]]; e = lv_value(lv, d, o); ELO_SRC["직접 라벨"] += 1
        ELO_LOG[(o, d)] = ("force", e, lv); return e, lv
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    seasons = seasons_for(cid, d)
    for s in seasons:
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d, o); ELO_SRC["직접 라벨(순위표 밖)"] += 1
            ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
            p = _LRA["parse"](lv, d)
            if p and lv_value(lv, d, o) != e: TABLE_DIFF.append((o, s, e, lv, lv_value(lv, d, o)))
            return e, lv
    if cid in ("CHLA", "CHL1", "CHLP", "CHPL", "CS") and d < "2008-01-01":
        lv = chl_old(o, int(d[:4]))
        if lv:
            e = lv_value(lv, d, o); ELO_SRC["칠레 2005~07 순위표"] += 1
            ELO_LOG[(o, d)] = ("chl", e, lv); NEW_TS[(o, d[:4])] = (e, lv); return e, lv
    for lg, s in lg_cands(cid, d):
        t = RANKS.get((lg, s), {})
        if k in t:
            lv = make_label(lg, s, t[k])
            if lv:
                e = lv_value(lv, d, o); ELO_SRC["순위표 → 라벨"] += 1
                ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

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

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["vidal_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "1")]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "pen" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
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
G_BYDATE = {ldate(g): g["competitionId"] for g in GAMES}
def same_team(a, b, d):
    if key(a) == key(b): return True
    return G_BYDATE.get(d, "BRA1") not in SA_DOM and bool(toks(a)) and toks(a) == toks(b)
CROSS = []
VRE = re.compile(r"Vidal|비달")
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for x in oe:
        if x[0] == "a" and VRE.search(str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(비달 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1], r[9])]
            if hit: CROSS.append(("비달 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 비달 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
SHARED_PAR = collections.Counter()
for b, (oe, om) in PAR.items():
    for m in M:
        if any(mm[0] == m[0] and key(mm[1]) == key(m[1]) for mm in om): SHARED_PAR[b] += 1

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("ccav", "2007-07-01"), ("levav", "2011-07-21"), ("juvav", "2015-07-28"), ("bayav", "2018-08-06"), ("fcbav", "2020-09-22"),
         ("intav", "2022-07-18"), ("flaav", "2023-07-14"), ("capav", "2024-01-23"), ("ccav", None)]
TM_CLUB = {"2433": "ccav", "15": "levav", "506": "juvav", "27": "bayav", "131": "fcbav", "46": "intav", "614": "flaav", "679": "capav"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
    if g["club_id"] in ("15", "506", "27", "131", "46") and eu(ldate(g))[:4] != g["seasonId"]: sys.exit("시즌 불일치 " + g["gameId"])
PERIODS = [("콜로콜로", "2005~2007", None, "2007-07-01"), ("바이어 레버쿠젠", "2007~2011", "2007-07-01", "2011-07-21"),
           ("유벤투스", "2011~2015", "2011-07-21", "2015-07-28"), ("바이에른 뮌헨", "2015~2018", "2015-07-28", "2018-08-06"),
           ("바르셀로나", "2018~2020", "2018-08-06", "2020-09-22"), ("인테르", "2020~2022", "2020-09-22", "2022-07-18"),
           ("플라멩구", "2022~2023", "2022-07-18", "2023-07-14"), ("아틀레치쿠 파라나엔시", "2023", "2023-07-14", "2024-01-23"),
           ("콜로콜로", "2024~", "2024-01-23", None)]
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
    for a in A_STATUS: print(a)
    print("FM only", FM_ONLY)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G, FM_CMP)
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF); print("MAPNEED", sorted(set(MAPNEED))); print("SHARED_PAR", SHARED_PAR)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_vidal.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "mlp", "lcg", "clg"]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const AVD_E={J(E)};\nconst AVD_M={J(M)};\nconst AVD_NOTE={J(NOTE)};\n")
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
