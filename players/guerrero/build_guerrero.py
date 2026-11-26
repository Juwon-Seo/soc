#!/usr/bin/env python3
"""파올로 게레로 (Paolo Guerrero, Transfermarkt 2989, FotMob 33101): raw/ -> guerrero.json + players/guerrero/pgu.js (판정 근거는 judgments.md)

  python3 players/guerrero/build_guerrero.py [--out <data 폴더>]   # 기본 players/guerrero/pgu.js; 스크래치 복사본 검증 때 SOC_ROOT=<복사본> … --out <복사본>/src/data
  python3 players/guerrero/build_guerrero.py --debug               # Elo 출처 로그
  python3 players/guerrero/build_guerrero.py --stat                # 요약·판정·동료 대조

게레로 build 스크립트(같은 수집기 계열)를 게레로 raw와 독일·브라질(주 선수권 포함)·아르헨티나·에콰도르·페루 대회에 맞춰 고친 것.
순위 라벨 행의 Elo는 tools/league_rank_apply.py parse()/value()(+ tools/league_points.py 승점 모형)로 라벨에서 계산.
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌(통합표 키)이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "pgu.js")
OUT_JSON = os.path.join(HERE, "guerrero.json")
ME = "2989"
ME_KO = "파올로 게레로"
CUTOFF = "2026-11-25"
GAP = "2014-08-01"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["team_level"] == "senior"]   # 바이에른 2군(레지오날리가 쥐트·DFB-포칼 2004-05) 69경기 제외 → 667경기
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 날짜·출전 분
# TM 경기 시각(UTC)이 하루 이른 경기: FotMob 일정 날짜가 맞음(2014.5.28 크루제이루전 — ESPN·가제타 에스포르치바 '수요일 28일',
# 2019 코파 두 브라질 16강~결승 — 결승 2차전 2019.9.18 베이라히우(위키백과·가제타 에스포르치바), 2019년 11~12월 리그 6경기 같은 묶음)
DATE_FIX = {"2454384": "2014-05-28", "4115281": "2019-05-23", "4115283": "2019-05-29", "4115284": "2019-07-10", "4115285": "2019-07-17",
            "4115286": "2019-08-07", "4115287": "2019-09-04", "4115288": "2019-09-11", "4115289": "2019-09-18",
            "3272426": "2019-11-07", "3273304": "2019-11-10", "3277735": "2019-11-17", "3277779": "2019-11-27", "3277806": "2019-11-30",
            "3285721": "2019-12-04", "4049119": "2020-01-26"}
MIN_FIX = {}
EV_MIN_FIX = {}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local"])
def opp(g): return re.sub(r"\s*\(\s*-?\s*\d{4}\s*(-\s*\d{4})?\s*\)", "", g["opponent"]).strip()
# 코파 두 브라질 2014 2라운드 나시오나우(AM) 원정 3-0: 2골 차 이상 원정승이라 2차전 없이 끝난 1차전(파투 선례처럼 1차전으로 둠)
RND_FIX = {"4285346": "Second Round 1st leg"}
# 코파 두 브라질 2015 3라운드 나우치쿠 1차전(게레로 등록 전, 마라카낭 1-1): 위키백과 2015 Copa do Brasil Third Round·가제타 에스포르치바
OTHER_LEG_FIX = {"4253882": (1, 1)}
def rnd_of(g): return RND_FIX.get(g["gameId"], g["round"] or "")

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "BRA1", "AR1N", "EL1S", "TDeA", "TDeC"}
STATE = {"BCP1", "BCPF", "BRCG", "BRCR", "BRCF", "BRC2", "BRRS", "BRga", "RS2f"}   # 주 선수권(파울리스타·카리오카·가우슈)·프리메이라 리가: 국내컵(디에구·네이마르·비니시우스 선례)
CUP = {"DFB", "BRC", "ARCA"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "LPO":                         # DFL-리가포칼: 첫 경기(intermediate stage) dk, 준결승 dsf(클로제·발라크 선례)
        if r.startswith("semi"): return "dsf"
        if r.startswith("final"): return "df"
        return "dk"
    if cid == "RECO": return "df"            # 레코파 = 국내컵 결승 비중(디에구·더글라스 코스타 선례)
    if cid == "KLUB": return "cwc"
    if cid in ("LPPL", "PERF"):              # 에콰도르 결승·페루 플레이오프 = MLS 플레이오프 비중(칠레·콜롬비아 플레이오프·리길야 선례)
        if r.startswith("final"): return "mlpf"
        if r.startswith("semi"): return "mlpsf"
        return "mlp"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
    if cid == "CLQ": return "clq"
    if cid in ("ELQ", "UEQ"): return "elq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        return "elk"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        return "elk"
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"                         # 예선 1~3라운드·조별·16강
    if cid == "CS":
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd, gid):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if cid in STATE and (r == "" or r.startswith("group")): return 0   # 주 선수권 1단계(조별·리그식)
    if r.startswith("group"): return 0
    return 1

def tie_rule(cid, d, rnd):
    r = rnd.lower()
    if cid in ("CL", "EL", "ELQ", "CLQ", "UEFA", "UEQ"): return (1, 1)
    if cid in STATE or cid in ("LPPL", "PERF"): return (0, 0)    # 주 선수권 결선·에콰도르 결승·페루 플레이오프: 원정 다득점·연장 없이 승부차기
    if cid == "BRC":
        if r.startswith("final"): return (0, 0)
        return (1, 0) if d < "2018-01-01" else (0, 0)   # 원정 다득점 2017년까지, 연장 없음(디에구 선례)
    if cid in ("CLI", "CS", "RECO"):
        if d < "2005-01-01" or d >= "2022-01-01": return (0, 0)
        if r.startswith("final"): return (0, 1)
        return (1, 0)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["clubId"]: return "h"
    if m["away_id"] == g["clubId"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    if gid in OTHER_LEG_FIX: return OTHER_LEG_FIX[gid]
    g = G[gid]; club = g["clubId"]; rnd = rnd_of(g).lower()
    base = re.sub(r"\s*(1st|2nd) leg", "", rnd)
    cand = [x for x in GAMES if x["gameId"] != gid and x["competitionId"] == g["competitionId"] and x["opponentId"] == g["opponentId"]
            and re.sub(r"\s*(1st|2nd) leg", "", rnd_of(x).lower()) == base and "1st" in rnd_of(x).lower()]
    if len(cand) == 1:
        a, b = map(int, cand[0]["score_club_opp"].split("-")); return (a, b)
    m = MI[gid]; oid = m["other_leg_id"]
    if not oid:   # 게레로이 안 뛴 다른 차전(match_info에만 있음)
        c2 = [k for k, o in MI.items() if k != gid and o["comp"] == m["comp"] and {o["home_id"], o["away_id"]} == {m["home_id"], m["away_id"]}
              and re.sub(r"\s*(1st|2nd) leg", "", (o["round"] or "").lower()) == base]
        if len(c2) == 1: oid = c2[0]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split("-"))
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
    if m["other_leg_score"]:   # 다른 차전 스코어(그 경기 홈-원정; 다른 차전 홈 = 이 경기 원정 팀)
        oh, oa = map(int, re.split(r"[-:]", m["other_leg_score"]))
        return (oh, oa) if side_of(gid) == "a" else (oa, oh)
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
        if f["guerrero_assist"] == "1" and f["pen_shootout_event"] != "True" and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])): return True
    return False

# 2014.8 이후 Transfermarkt에만 있는 일반 유형 도움: 다른 출처 2곳으로 판정(judgments.md 4절)
A_CHECK = {}
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())   # A_CHECK 채움
A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도('Penalty: Fouled player')"
    if t == "Handball (opponent)": return "상대 핸드볼 PK"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    k = f"{gid}|{e['minute']}"
    if d < GAP:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "2014.8 이전 Transfermarkt 일반 유형(" + (t or "유형 없음") + ")" + (" + FotMob" if fm_assist(gid, e) else "")))
        return None
    if fm_assist(gid, e):
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else why
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음"))
    if "--dev" not in sys.argv: sys.exit("2014.8 이후 단일 출처 도움 판정 누락 " + k + " " + d)
    return None

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
        if e["scorer_id"] == ME and is_og(e): judg.append(("본인 자책골(골 아님)", ldate(g), opp(g), e["minute"]))
        if e["scorer_id"] == ME and e["assist_id"] == ME: judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], "본인 PK 골의 본인 도움(PK 유도)"))
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
            pk = 1 if e["penalty"] == "1" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["guerrero_assist"] == "1" and f["pen_shootout_event"] != "True":
            if not any(e["assist_id"] == ME and e["scorer_id"] != ME and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])) for e in EVS.get(gid, [])):
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
def key(n):
    k = norm(n)
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "pgu.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
PAR = {}   # 이번 회차 병렬 판정(읽기만)
for slug in ("wood", "slimani"):
    for pth in glob.glob(os.path.join(os.path.dirname(HERE), slug, "*.js")):
        try: P, oe, om = load_js(pth)
        except Exception: continue
        PAR["players/" + slug + "/" + os.path.basename(pth)] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss", "us", "vfl", "vfb", "tsg",
        "real", "borussia", "bayer", "eintracht", "hamburger", "olympique", "atletico", "athletic", "fk", "sk", "bv", "1899", "1909", "1907", "1913", "1846", "05", "04", "96", "1919"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
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
    if "순위 없음" in lv.split(" (")[0]:   # 순위 없는 행: 그 단계 기준점(tools/league_rank_apply.py base())
        p = _LRA["parse"](lv.split(" (")[0].replace(" 순위 없음", " 1위/20팀"), d)
        return int(round(_LRA["base"](*p[:4])))
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

NAME_ALIAS = {}
def nm_cands(o): return [o] + ([NAME_ALIAS[o]] if o in NAME_ALIAS else [])

WIKI = collections.defaultdict(dict)
for r in rd("ranks_wiki_tables.csv"):
    WIKI[(r["file"], r["headings"])][key(r["team"])] = (int(r["rank"]), int(r["teams"]), r["team"])
def wiki_rank(fn, hd, o, extra=()):
    t = WIKI[(fn, hd)]
    for nm in nm_cands(o) + list(extra):
        k = key(nm)
        if k in t: return t[k][:2]
        for kk, v in t.items():
            if toks(kk) and toks(kk) <= toks(nm) | {"fc"}: return v[:2]
    return None

def stage_key(lv):   # tools/elo_table.js lvSeason()과 같은 시즌 키
    t = lv
    for _ in range(3): t = re.sub(r"\([^()]*\)", " ", t)
    s = None
    for m in re.finditer(r"((?:19|20)\d\d)\s*[-–/]\s*(\d{2}|\d{4})(?!\d)", t):
        a, b = int(m.group(1)), int(m.group(2))
        if b == (a + 1) % 100 or b == a + 1: s = f"{a}-{str(a + 1)[2:]}"; break
    if not s:
        m = re.search(r"(?:^|[^\d])((?:19|20)\d\d)(?![\d-])", t); s = m.group(1) if m else None
    g = re.search(r"(Apertura|Clausura|Inicial|Torneo Final|Torneo I{1,2}\b|Copa de la Liga|아페르투라|클라우수라)", lv)
    return s + "/" + g.group(1).replace("아페르투라", "Apertura").replace("클라우수라", "Clausura") if s and g else s

def eu(d):
    y = int(d[:4]); m = int(d[5:7]); s_ = y if m >= 8 else y - 1
    if y == 2020 and m in (7, 8): s_ = 2019
    return f"{s_}-{str(s_ + 1)[2:]}"

MAN = []   # 직접 정한 상대 라벨: (key, 날짜 시작, 날짜 끝, lv)
def man(o, d, lv, d2=None): MAN.append((key(o), d, d2 or d, lv))
def man_get(o, d):
    for k_, a_, b_, lv_ in MAN:
        if k_ == key(o) and a_ <= d <= b_: return lv_
    return None
exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())   # man(...) 라벨 목록

EUROPE = {"L1", "DFB", "LPO", "CL", "CLQ", "UEFA", "UEQ", "EL", "ELQ"}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def seasons_for(d, cid):
    if cid in EUROPE: return [eu(d)]
    if cid == "KLUB": return [eu(d), d[:4]]
    return [d[:4]]
def table_hit(o, ks):
    for nm in nm_cands(o):
        for s in ks:
            if (key(nm), s) in TABLE:
                return collections.Counter(TABLE[(key(nm), s)]).most_common(1)[0][0], s
    return None
def opp_elo(o, d, cid, g):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    lv = man_get(o, d)
    if lv:
        h = table_hit(o, [stage_key(lv)])
        if h:
            (e, lv2), s = h; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv2, s)
            if lv2 != lv: TABLE_DIFF.append((o, s, lv, lv2))
            return e, lv2
        e = lv_value(lv, d, o); ELO_SRC["직접 라벨"] += 1
        ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, d)] = (e, lv); return e, lv
    if cid in ("TDeA", "TDeC", "PERF"):   # 페루 단계 리그(man_elo.py pe_label)
        lv = pe_label(o, d)
        if not lv: MISS.append((o, d, cid, "stage")); return 0, "?"
        h = table_hit(o, [stage_key(lv)])
        if h:
            (e, lv2), s = h; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv2, s)
            if lv2 != lv: TABLE_DIFF.append((o, s, lv, lv2))
            return e, lv2
        e = lv_value(lv, d, o); ELO_SRC["단계 순위 라벨"] += 1
        ELO_LOG[(o, d)] = ("stage", e, lv); NEW_TS[(o, d)] = (e, lv); return e, lv
    if cid in ("BRA1", "BRC") or cid in STATE:
        lv = br_label(o, d[:4])
        if lv:
            h = table_hit(o, [d[:4]])
            if h:
                (e, lv2), s = h; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv2, s)
                if lv2 != lv: TABLE_DIFF.append((o, s, lv, lv2))
                return e, lv2
            e = lv_value(lv, d, o); ELO_SRC["브라질 순위표 → 라벨"] += 1
            ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, d)] = (e, lv); return e, lv
    h = table_hit(o, seasons_for(d, cid))
    if h:
        (e, lv), s = h
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
        p = _LRA["parse"](lv, d)
        if p and lv_value(lv, d, o) != e: TABLE_DIFF.append((o, s, e, lv, lv_value(lv, d, o)))
        return e, lv
    MISS.append((o, d, cid, seasons_for(d, cid)[0])); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd, gid)
    elo, lv = opp_elo(opp(g), d, cid, g)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

# ---------------------------------------------------------------- 승점 표 map 줄(elo/league_points_other.json) 계산
def tnorm(x): return norm(re.sub(r"\(.*?\)", " ", x))
def row_of(rows, o, rk):
    def sc1(nm, t):
        a, b = set(tnorm(nm).split()), set(tnorm(t).split())
        if b and b <= a: return 1.0
        x, y = tnorm(nm).split(), tnorm(t).split()
        if x and y and x[0] == y[0] and len(x[0]) >= 4: return 0.8
        return PTS.sim(tnorm(nm), tnorm(t))
    def sc(i): return max(sc1(nm, rows[i][0]) for nm in nm_cands(o) + [re.sub(r"^(CA|CD|CF|FC|Club Atlético|Club|AA|GFK|FK) ", "", o)])
    if 0 < rk <= len(rows) and sc(rk - 1) >= 0.5: return sc(rk - 1), rk - 1
    return max((sc(i), i) for i in range(len(rows)))
MAP_LINES = {}
for r in E:
    lv, o = r[12], r[1]
    head = lv.split(" (")[0]; mm = re.match(r"^(.*?) (\d+)위", head)
    if not mm: continue
    ent = PTS.O["seasons"].get(mm.group(1))
    if not ent or "skip" in ent or ent.get("ongoing"): continue
    rk = int(mm.group(2)); tabs = ent["tables"]
    ti = 0
    st = "Apertura" if ("아페르투라" in lv or "Apertura" in lv) else "Clausura" if ("클라우수라" in lv or "Clausura" in lv) else None
    mp = ent.get("map", {})
    alias_pos = next((mp[a] for a in nm_cands(o)[1:] if a in mp), None)
    if len(tabs) > 1:
        cand = [i for i, t in enumerate(tabs) if st and st in t["name"]]
        if mm.group(1) == "중국 슈퍼리그 2020" or same_tabs: cand = [0]   # 2020 1단계 A조(다롄·장쑤·산둥·상하이 선화·선전·허난 모두 A조)
        if len(cand) != 1 and not alias_pos: continue
        ti = cand[0] if len(cand) == 1 else alias_pos[0]
    tname = tabs[ti]["name"]
    tst = "Apertura" if "Apertura" in tname else "Clausura" if "Clausura" in tname else "Aggregate" if "Aggregate" in tname else None
    lst = st or ("Aggregate" if "연간" in lv or "합산" in lv or "통합" in lv else None)
    if tst in ("Apertura", "Clausura") and lst != tst: continue   # 단계 표와 다른 단계 라벨(페루 클라우수라·연간)은 순위 곡선
    cur = mp.get(f"{rk}={o}") or mp.get(f"{o}@{rk}") or mp.get(o)
    res = PTS.other_score(lv, o)
    src = ELO_LOG.get((o, r[9]), ("?",))[0]
    same_tabs = all(sorted(map(tuple, t["rows"])) == sorted(map(tuple, tabs[0]["rows"])) for t in tabs)
    if src in ("table", "same"):   # 기존 라벨 재사용: 기존 선수 값이 바뀌지 않게, 내 이름이 표에서 안 찾힐 때만 이름 줄 추가
        if res is not None: continue
    elif res is not None and (len(tabs) == 1 or same_tabs or (cur and cur[0] == ti)): continue
    if alias_pos and PTS.other_score(lv, o) is None:
        MAP_LINES[(mm.group(1), o)] = (tabs[alias_pos[0]]["rows"][alias_pos[1]][0], alias_pos, rk, 1.0, "기존 다른 표기와 같은 행"); continue
    sc_, ri = row_of(tabs[ti]["rows"], o, rk)
    kname = o if (o not in mp and (len(tabs) == 1 or same_tabs)) else f"{o}@{rk}"
    if tst in ("Apertura", "Clausura"): kname = f"{rk}={o}"   # 같은 해 다른 단계 라벨에 안 쓰이게 순위 붙은 키
    MAP_LINES[(mm.group(1), kname)] = (tabs[ti]["rows"][ri][0], [ti, ri], rk, round(sc_, 2), "표 순위 다름" if ri + 1 != rk else "")
if "--map" in sys.argv:
    for (h, k), v in sorted(MAP_LINES.items()): print(f"{h} | {k} | {v[0]} | {v[1]} {v[4]} sim={v[3]}")
    sys.exit(0)
if "--applymap" in sys.argv:   # 스크래치 복사본 전용: SOC_ROOT의 elo/league_points_other.json에 map 줄 추가
    if os.path.realpath(ROOT) == "/home/user/soc": sys.exit("정본에는 쓰지 않음")
    fp = os.path.join(ELO, "league_points_other.json"); O_ = json.load(open(fp, encoding="utf-8"))
    for (h, k), v in MAP_LINES.items(): O_["seasons"][h].setdefault("map", {})[k] = v[1]
    json.dump(O_, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); print("map 줄", len(MAP_LINES)); sys.exit(0)

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
    fm = [r for r in FME[gid] if r["guerrero_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "1")]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["penalty"] == "1"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "pen" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 0): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["penalty"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
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
VRE = re.compile(r"Guerrero|게레로")
G_DATES = {ldate(g) for g in GAMES}
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for x in oe:
        if x[0] == "a" and VRE.search(str(x[13] or "")) and x[9] in G_DATES:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(게레로 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1], r[9])]
            if hit: CROSS.append(("게레로 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 게레로 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
SHARED = collections.Counter()
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for m in M:
        if any(mm[0] == m[0] and key(mm[1]) == key(m[1]) for mm in om): SHARED[b] += 1

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("baypgu", "2006-07-01"), ("hsvpgu", "2012-07-15"), ("corpgu", "2015-06-16"), ("flapgu", "2018-08-12"), ("intpgu", "2022-07-21"),
         ("avapgu", "2023-01-25"), ("racpgu", "2023-07-14"), ("ldupgu", "2024-02-02"), ("ucvpgu", "2024-08-31"), ("alipgu", None)]
TM_CLUB = {"27": "baypgu", "41": "hsvpgu", "199": "corpgu", "614": "flapgu", "6600": "intpgu", "2035": "avapgu", "1444": "racpgu",
           "9855": "ldupgu", "6889": "ucvpgu", "184": "alipgu"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["clubId"])
PERIODS = [("바이에른 뮌헨", "2003~2006", None, "2006-07-01"), ("함부르크", "2006~2012", "2006-07-01", "2012-07-15"),
           ("코린치안스", "2012~2015", "2012-07-15", "2015-06-16"), ("플라멩구", "2015~2018", "2015-06-16", "2018-08-12"),
           ("인테르나시오나우", "2018~2021", "2018-08-12", "2022-07-21"), ("아바이", "2022", "2022-07-21", "2023-01-25"),
           ("라싱", "2023", "2023-01-25", "2023-07-14"), ("LDU 키토", "2023", "2023-07-14", "2024-02-02"),
           ("세사르 바예호", "2024", "2024-02-02", "2024-08-31"), ("알리안사 리마", "2024~", "2024-08-31", None)]
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
exec(open(os.path.join(HERE, "note_guerrero.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "elk", "elq", "cwc", "clg", "cl16", "mlp", "ccc"]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const PGU_E={J(E)};\nconst PGU_M={J(M)};\nconst PGU_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()}, "map_need": sorted(set(MAPNEED)),
               "table_label_diffs": TABLE_DIFF, "map_lines": [[h, k, v[0], v[1]] for (h, k), v in sorted(MAP_LINES.items())], "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for v in ST: print(" ", v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
