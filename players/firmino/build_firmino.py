#!/usr/bin/env python3
"""호베르투 피르미누 (Roberto Firmino, Transfermarkt 131789): raw/ -> firmino.json + players/firmino/rfm.js (판정 근거는 judgments.md)

  python3 players/firmino/build_firmino.py [--out <data 폴더>]   # 파일 쓰기(기본 players/firmino/rfm.js; 스크래치 검증 때 --out <복사본>/src/data)
  python3 players/firmino/build_firmino.py --debug               # Elo 출처 로그
  python3 players/firmino/build_firmino.py --stat                # 요약·판정·동료 대조

사비(xavi) build 스크립트를 바탕으로 마르셀루 수집 형식(raw/)에 맞춤. 순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의
parse()/value()(승점 모형 포함)로 라벨에서 계산. 같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이
elo/opponent_elo_by_team_season.csv에 있으면 그 값(스크래치 복사본에서는 SOC_ROOT=<복사본>).
보조: firmino_manual.py(추가 경기·도움 판정), note_firmino.py(설명).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "rfm.js")
OUT_JSON = os.path.join(HERE, "firmino.json")
ME = "131789"
ME_KO = "호베르투 피르미누"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    r["sq_assist"] = r["firmino_assist"]; r["sq_scorer"] = "1" if r["firmino_scorer"] == "1" and r["ownGoal"] not in ("True", "1", "true") else "0"
    FME[r["tm_gameId"]].append(r)
TIESX = {r["gameId"]: r for r in rd("tm_two_leg_ties_extra.csv")}

def ldate(g): return g["date_local"]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용(정상 유형)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BRA2", "L1", "GB1", "SA1", "QSL", "L1PO"}   # 분데스리가 강등 플레이오프 = 리그(판 더 파르트·찰하노을루 선례)
CUPS = {"DFB", "FAC", "CGB", "SAKC", "QEC1", "QUC1", "QSCP"}
SUPER = {"GBCS", "USC", "SASS", "QUSS"}   # 커뮤니티 실드·UEFA 슈퍼컵·사우디 슈퍼컵·카타르-UAE 슈퍼 실드 = 국내컵 결승 비중(준결승은 준결승)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "dsf" if r.startswith("semi") else "df"
    if cid == "KLUB": return "cwc"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 32강(intermediate stage)·16강·8강
    if cid == "ACLE":   # 리그 단계·16강 acl, 8강 aclk, 준결승 aclsf, 결승 aclf(마레즈 같은 경기)
        if r.startswith("quarter"): return "aclk"
        if r.startswith("semi"): return "aclsf"
        if r.startswith("final"): return "aclf"
        return "acl"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g): return g["round"] or MI.get(g["gameId"], {}).get("round", "")

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "EL", "CLQ"): return (1, 1) if d < "2021-08-01" else (0, 1)
    if cid == "L1PO": return (1, 1)
    if cid == "CGB": return (1, 1) if d < "2018-08-01" else (0, 0)   # EFL컵 준결승: 2017-18까지 원정 다득점·연장, 2018-19부터 바로 승부차기
    if cid == "ACLE": return (0, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):   # 경기 JSON의 홈·원정(선수 경기 목록 venue와 다른 경기 1: 2024.8.13 사우디 슈퍼컵, 중립 경기장)
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["clubId"]: return "h"
    if m["away_id"] == g["clubId"]: return "a"
    sys.exit("편 판정 실패 " + gid)
VENUE_DIFF = [gid for gid in G if (G[gid]["venue"] == "H") != (MI[gid]["home_id"] == G[gid]["clubId"])]

def other_leg(gid):
    g = G[gid]; m = MI[gid]; oid = m["other_leg_id"]; club = g["clubId"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split("-"))
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    if gid in TIESX:
        a, b = map(int, TIESX[gid]["other_leg_score_club_opp"].split("-")); return (a, b)
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

exec(open(os.path.join(HERE, "firmino_manual.py"), encoding="utf-8").read())

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])])
for a in ADD_GAMES:
    M.append([a["date"], a["opp"], comp_of(a["cid"], a["round"]), a["min"]] + ([1] if a["est"] else []))
M.sort(key=lambda m: m[0])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"
def a_key(gid, minute): return f"{gid}|{minute}"

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["sq_assist"] == "1" and f["pen_shootout_event"] != "True" and fm_min_match(f, e["minute"]): return True
    return False

def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]; k = a_key(gid, e["minute"])
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    if k in A_CHECK and not A_CHECK[k][0]:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "뺌: " + A_CHECK[k][1])); return A_CHECK[k][1]
    if d < GAP:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "2014.8 전 TM" + (" + FotMob" if fm_assist(gid, e) else ""))); return None
    if fm_assist(gid, e):
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if k in A_CHECK:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "넣음: " + A_CHECK[k][1])); return None
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음"))
    return "2014.8 이후 단일 출처(판정 없음)"

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"]); cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e): sys.exit("자책골 " + gid)
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
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk and e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["sq_assist"] == "1" and f["pen_shootout_event"] != "True":
            mi = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(e["assist_id"] == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, mi, f["scorer"]))

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
    k = norm(n); return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue   # 내 자료만 쓴 팀×시즌은 건너뜀(오스카 선례)
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "clubcolors.js", "finals.js", "rfm.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
PEERS = ("defoe/jdf.js", "hulk/hlk.js", "tadic/dta.js", "nkunku/cnk.js")
for b in PEERS:   # 같은 라운드 다른 심판 자료(아직 src/data에 없음): 대조만
    fn = os.path.join(os.path.dirname(HERE), b)
    if os.path.exists(fn) and "--no-peers" not in sys.argv:
        P, oe, om = load_js(fn); OTHERS["peer:" + b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    if b.startswith("peer:"): continue
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "fk", "vfl", "bv", "vfb", "tsv", "fsv", "spvgg",
        "hotspur", "palace", "villa", "ham", "manchester", "sheffield", "bristol", "birmingham", "nottingham", "queens", "park", "west", "aston",
        "borussia", "werder", "bayer", "eintracht", "hertha", "al", "sfc", "ahli", "shabab", "ittihad", "hilal", "nassr", "qatar", "crystal", "norwich", "swansea", "southampton", "stoke", "hull",
        "wahda", "sadd", "rayyan", "arabi", "duhail", "gharafa", "shamal", "wakrah", "sailiya", "shahania", "dubai", "saudi", "doha", "jeddah", "riyadh",
        "frankfurt", "munich", "munchen", "berlin", "hamburg", "stuttgart", "kickers", "1899", "1860", "04", "05", "07", "09",
        "mg", "sp", "go", "df", "rj", "rs", "pr", "sc", "ba", "ce"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d, cid):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)] or [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위 라벨 → Elo (tools/league_rank_apply.py)
_LRA = {"__file__": os.path.join(ROOT, "tools", "league_rank_apply.py"), "__name__": "lra"}
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA["__file__"], encoding="utf-8").read().split("if __name__ == '__main__':")[0], "lra", "exec"), _LRA)
sys.argv = _argv
sys.path.insert(0, os.path.join(ROOT, "tools")); import league_points as PTS
def lv_value(lv, d, o=None):
    m_ = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv)
    if m_:
        cal = m_.group(4) is None; y = int(m_.group(3)) + (0 if cal else 1)
        return int(round(_LRA["base"](_LRA["KO"][m_.group(1)], int(m_.group(2)), y, cal)))
    p = _LRA["parse"](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA["value"](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    if o is not None:
        b_, sd_ = _LRA["base"](p[0], p[1], p[2], p[3]), _LRA["sd"](p[0], p[1])
        if p[1] == 1 and p[0] in _LRA["BIG"]:
            vp = PTS.value(lv, o, b_, sd_, _LRA["cv"])
        else:
            vp = PTS.value_other(lv, o, p[0], p[1], b_, sd_, _LRA["cv"])
        if vp is not None: v = vp
    return v
MAP_NEED = {}
def map_check(lv, o):
    head = lv.split(" (")[0]; mm = re.match(r"^(.*?) (\d+)위", head)
    if not mm: return
    E_ = PTS.O["seasons"].get(mm.group(1))
    if not E_ or "skip" in E_ or E_.get("ongoing") or "tables" not in E_: return
    if PTS.other_score(lv, o) is not None: return
    rk = int(mm.group(2)); R = E_["tables"][0]["rows"]
    MAP_NEED[(mm.group(1), o)] = (R[rk - 1][0] if rk <= len(R) else "?", rk - 1)

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[0].startswith("#"): continue
        lg = p[0].split(" ")[0]
        RANKS[(lg, p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1], p[0])
for nm, r in QSL_NOW.items():
    RANKS[("QSL", "2026-27")][key(nm)] = (r, 12, nm, "2026-27", "QSL")

DE_LOW = {"DE4": (4, "Regionalliga Nordost"), "DE5": (5, "Bremen-Liga"), "DE6": (6, "Mittelrheinliga")}
def make_label(lg, season, v):
    r, n, nm, sraw, full = v
    if lg == "BRA2": return f"브라질 세리에 B {season} {r}위/{n}팀"
    if lg == "L2": return f"2. 분데스리가 {season} {r}위/{n}팀"
    if lg in DE_LOW: return f"독일 {DE_LOW[lg][0]}부 {season} {r}위/{n}팀 ({DE_LOW[lg][1]}, 리그 수준 추정)"
    if lg == "GB3": return f"잉글랜드 3부 {season} {r}위/{n}팀 (EFL League One, 리그 수준 추정)"
    if lg == "RU1": return f"러시아 1부 {season} {r}위/{n}팀"
    if lg == "C1": return f"스위스 1부 {season} {r}위/{n}팀"
    if lg == "QSL":
        if season == "2026-27": return f"카타르 1부 {season} {r}위/{n}팀 (Qatar Stars League, 2026년 11월 25일 현재 순위)"
        return f"카타르 1부 {season} {r}위/{n}팀 (Qatar Stars League)"
    if lg == "IRN1": return f"이란 1부 {season} {r}위/{n}팀 (Persian Gulf Pro League)"
    if lg == "UAE1": return f"UAE 프로리그 {season} {r}위/{n}팀 (UAE Pro League)"
    if lg == "SA2L": return f"사우디 2부 {season} {r}위/{n}팀"
    return None

def season_of(d):
    y, m = int(d[:4]), int(d[5:7])
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
CONT = {"CL", "CLQ", "EL", "USC", "KLUB", "ACLE", "QUSS"}
def seasons_for(cid, d, o, g):
    if g.get("clubId") == "4064": return [d[:4]]   # 피게이렌시(브라질 달력 연도)
    eu = season_of(d)
    if cid in CONT: return [eu, d[:4]]
    return [eu]
DOM = {"4064": ["BRA2"], "533": ["L2", "DE4", "DE5", "DE6"], "31": ["GB3"], "18487": ["SA2L"], "656": ["QSL"]}
ALL_LG = sorted({k[0] for k in RANKS})
def lg_cands(cid, d, o, g):
    ss = seasons_for(cid, d, o, g)
    lgs = DOM[g["clubId"]] if cid not in CONT else ALL_LG
    return [(lg, s) for s in ss for lg in lgs]

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def opp_elo(o, d, cid, g):
    if g["gameId"] in FORCE:
        lv = FORCE[g["gameId"]]; e = lv_value(lv, d, o); map_check(lv, o); ELO_SRC["직접 라벨"] += 1
        ELO_LOG[(o, d)] = ("force", e, lv); NEW_TS[(o, d[:4])] = (e, lv); return e, lv
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand}), sorted({x[1] for _, x in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    seasons = seasons_for(cid, d, o, g)
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
            p = _LRA["parse"](lv, d)
            if p and lv_value(lv, d, o) != e: TABLE_DIFF.append((o, s, e, lv, lv_value(lv, d, o)))
            map_check(lv, o)
            return e, lv
    for lg, s in lg_cands(cid, d, o, g):
        t = RANKS.get((lg, s), {})
        if k in t:
            lv = make_label(lg, s, t[k])
            if lv:
                e = lv_value(lv, d, o); map_check(lv, o); ELO_SRC["순위표 → 라벨"] += 1
                ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, g)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
for a in ADD_E:
    pg = {"gameId": "add:" + a["date"], "clubId": "656"}
    elo, lv = opp_elo(a["opp"], a["date"], a["cid"], pg)
    mi, dm = mins(a["minute"])
    E.append([a["type"], a["opp"], elo, comp_of(a["cid"], a["round"]), mi, a["gf"], a["ga"], ko_of(a["cid"], a["round"]), a["pk"], a["date"], 0, dm, lv, 0])
    judg.append(("골 추가(TM에 없는 경기, 경기 기사 2곳)", a["date"], a["opp"], a["minute"], a["why"]))

E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)
if "--debug" in sys.argv:
    print(ELO_SRC)
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]): print(d, o, v)
    print("TABLE_DIFF", TABLE_DIFF)
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["sq_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "penalty" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))

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
G_BYDATE = {m[0] for m in M}
CROSS = []
JRE = re.compile(r"Firmino|피르미누", re.I)
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and JRE.search(str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(피르미누 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("피르미누 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x[1], r[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm[1], m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 피르미누 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
SHARED = collections.defaultdict(set)
for b, (oe, om) in OTHERS.items():
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm[1], m[1]): SHARED[b].add(m[0]); break

# ---------------------------------------------------------------- 클럽·시즌
STINTS = [("피게이렌시", "2011-01-01"), ("호펜하임", "2015-07-01"), ("리버풀", "2023-07-04"), ("알아흘리", "2025-07-23"), ("알사드", "9999")]
TM_CLUB = {"4064": "피게이렌시", "533": "호펜하임", "31": "리버풀", "18487": "알아흘리", "656": "알사드"}
def stint(d):
    for n, u in STINTS:
        if d < u: return n
for g in GAMES:
    if stint(ldate(g)) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for n, _ in STINTS)
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
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A)
    for j in judg: print(j)
    for a in A_STATUS:
        if not a[4].startswith(("2014.8 전", "TM+FotMob")): print(a)
    print("A_STATUS", collections.Counter(a[4].split(":")[0] for a in A_STATUS))
    print("FM only", FM_ONLY)
    for c in CROSS: print(c)
    print("FM_CMP", FM_CMP)
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF)
    for k, v in sorted(MAP_NEED.items()): print("MAP_NEED", k, v)
    print("SHARED", {b: len(v) for b, v in sorted(SHARED.items(), key=lambda kv: -len(kv[1]))})
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_firmino.py"), encoding="utf-8").read())
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "csa", "lib", "elk", "elq", "cwc", "acl", "aclk", "mlp", "lcg", "lck"]:
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
    gl = [r for r in rs if r[0] == "g"]   # E 정렬 순서(전반 추가시간 45+x는 46분 앞)
    for a, b in zip(gl, gl[1:]):
        if (b[5], b[6]) <= (a[5], a[6]): problems.append(("스코어 역순", d, a[4], b[4]))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const RFM_E={J(E)};\nconst RFM_M={J(M)};\nconst RFM_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "table_label_diffs": TABLE_DIFF, "points_map_needed": [f"{k[0]} | {k[1]} | {v[0]} | {v[1]}" for k, v in sorted(MAP_NEED.items())],
               "shared_games": {b: sorted(v) for b, v in SHARED.items()}, "added_games": ADD_GAMES,
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
