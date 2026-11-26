#!/usr/bin/env python3
"""바스티안 슈바인슈타이거 (Bastian Schweinsteiger, Transfermarkt 2514): raw/ -> schweinsteiger.json + players/schweinsteiger/bsw.js (판정 근거는 judgments.md)

  python3 players/schweinsteiger/build_schweinsteiger.py [--out <data 폴더>]   # 파일 쓰기(기본 players/schweinsteiger/bsw.js; 스크래치 검증 때 --out <복사본>/src/data)
  python3 players/schweinsteiger/build_schweinsteiger.py --debug               # Elo 출처 로그
  python3 players/schweinsteiger/build_schweinsteiger.py --stat                # 요약·판정·동료 대조
  python3 players/schweinsteiger/build_schweinsteiger.py --ties                # 합산 행

슈바인슈타이거 build 스크립트(같은 수집 형식)를 바탕으로 함. 순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의 parse()/value()(승점 모형 포함)로
라벨에서 계산. 같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀-시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값(스크래치 복사본에서는 SOC_ROOT=<복사본>).
바이에른 II(레기오날리가 쥐트, 2군)·U19·U17 경기는 tm_games.csv level이 senior가 아님 → 제외.
보조: assist_checks.py(도움 판정 근거), man_elo.py(순위표 밖 상대 라벨), note_schweinsteiger.py(설명).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "bsw.js")
OUT_JSON = os.path.join(HERE, "schweinsteiger.json")
ME = "2514"
ME_KO = "바스티안 슈바인슈타이거"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

ALLG = rd("tm_games.csv")
EXCL = [g for g in ALLG if g["level"] != "senior"]          # 바이에른 II 37경기·U19 3경기·U17 3경기
GAMES = [g for g in ALLG if g["level"] == "senior"]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["status"] == "OK"}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}
TWO = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# 날짜: TM API 경기 시각(UTC)을 클럽 시간대(베를린·런던·시카고)로 바꾼 현지 날짜(date_local). 시카고 저녁 경기는 UTC 다음 날 → 현지 날짜.
def ldate(g): return g["date_local"]
def opp(g): return re.sub(r"\s*\(\s*-?\s*\d{4}\s*-?\s*\d{0,4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용(정상 유형)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "GB1", "MLS1"}
CUPS = {"DFB", "FAC", "CGB", "MLSP"}   # DFB-포칼·FA컵·EFL컵·US 오픈컵(TM 코드 MLSP)
SUPER = {"DFL"}   # DFL-슈퍼컵 = 국내컵 결승 비중(다른 바이에른 선수 자료 같은 경기)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "dsf" if r.startswith("semi") else "df"
    if cid == "LPO":   # DFL-리가포칼: 첫 경기(intermediate stage, 8강급) dk, 준결승 dsf, 결승 df(클로제·알틴톱 선례)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        return "dk"
    if cid == "POUS": return "mlp"   # MLS컵 플레이오프 2017 녹아웃 라운드(단판) = MLS 플레이오프(메시·손흥민·밤바 선례)
    if cid == "USMX": return "lck"   # 리그스컵 2019 8강(단판) = 리그스컵 토너먼트(같은 대회 다른 선수 자료 선례)
    if cid in CUPS:   # 16강까지 국내컵, 8강 이후 단계별
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or (cid == "FAC" and r.startswith("sixth")): return "dk"
        return "dc"
    if cid == "CLQ": return "clq"
    if cid == "UEFA":   # UEFA컵 2007-08: 1라운드 = 유로파 예선 비중, 조별 elg, 32강('3rd round')·16강·8강 elk, 준결승 elsf(클로제·리베리·토니 등 같은 경기)
        if r.startswith("group"): return "elg"
        if r.startswith("first round"): return "elq"
        if r.startswith("semi"): return "elsf"
        return "elk"
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
        return "elk"   # 32강(2010-11·2013-14 'Second Round', 2021-22부터 'intermediate stage' 녹아웃 PO)·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or r == "": return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "EL", "CLQ", "UEFA"): return (1, 1)   # UEFA 대회 2020-21까지 원정 다득점(연장 포함)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["clubId"]: return "h"
    if m["away_id"] == g["clubId"]: return "a"
    sys.exit("편 판정 실패 " + gid)

LEG_PAIR = {}   # TM이 다른 차전을 잇지 않은 경기(2012-13 코파 델 레이 32강 에스파뇰전): 같은 대회·같은 두 팀·'1st leg'·200일 안
def find_first_leg(gid):
    m = MI[gid]; teams = {m["home_id"], m["away_id"]}
    c = [k for k, x in MI.items() if k != gid and x["comp"] == m["comp"] and {x["home_id"], x["away_id"]} == teams
         and "1st leg" in x["round"].lower() and 0 < (int(m["date_utc"][:4]) * 400 + int(m["date_utc"][5:7]) * 31 + int(m["date_utc"][8:10])) - (int(x["date_utc"][:4]) * 400 + int(x["date_utc"][5:7]) * 31 + int(x["date_utc"][8:10])) < 200]
    if len(c) != 1: sys.exit("다른 차전 못 찾음 " + gid)
    LEG_PAIR[gid] = c[0]; return c[0]
def other_leg(gid):
    t = TWO.get(gid) or {"other_leg_id": find_first_leg(gid), "other_leg_score": ""}; club = G[gid]["clubId"]
    o = MI.get(t["other_leg_id"])
    fh, fa = map(int, (o["final"] if o else t["other_leg_score"]).split("-"))
    if o:
        if o["addition"] == "n.E.":   # 승부차기 포함 스코어면 다른 차전 스코어는 쓰지 않음(1차전 승부차기 없음)
            sys.exit("다른 차전 승부차기 " + gid)
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    return (fa, fh) if side_of(gid) == "h" else (fh, fa)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
    if "1st" in rnd: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

A_CHECK = {}; ADD_A = []; GOAL_FIX = {}
def a_key(gid, minute): return f"{gid}|{minute}"
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["schweinsteiger_assist"] == "1" and f["pen_shootout_event"] != "True" and fm_min_match(f, e["minute"]): return True
    return False
def fm_pm_assists(gid):
    m = FMMAP.get(gid)
    if m and m["fotmob_matchId"] in FMPM: return int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
    return None

def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    k = a_key(gid, e["minute"])
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    if d < GAP:
        if k in A_CHECK and not A_CHECK[k][0]: return A_CHECK[k][1]
        return None
    fa, pm = fm_assist(gid, e), fm_pm_assists(gid)
    if fa:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "2014.8 이후 단일 출처(확인 못 함)"
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
        fix = (gid, e["minute"]) in GOAL_FIX
        is_g = (e["scorer_id"] == ME and not is_og(e)) or fix
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME and not fix
        if fix: judg.append(("골로 고침(TM 상대 자책골)", ldate(g), opp(g), e["minute"], GOAL_FIX[(gid, e["minute"])]))
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("슈바인슈타이거 자책골(골 아님)", ldate(g), opp(g), e["minute"], ""))
            continue
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
            pk = 1 if e["goal_desc"] == "Penalty" and not fix else 0
            if e["penalty"] == "1" and not pk and e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

for gid, mi, gf, ga, pk, scorer, why in ADD_A:
    raw_rows.append(("a", gid, mi, 0, gf, ga, 0, scorer, "added"))
    judg.append(("도움 추가(FotMob 단독 + 다른 출처 2곳)", ldate(G[gid]), opp(G[gid]), str(mi), scorer, why))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["schweinsteiger_assist"] == "1" and f["pen_shootout_event"] != "True":
            mi = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(e["assist_id"] == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, mi, f["scorer"]))
PM_DIFF = []
for gid, m in FMMAP.items():
    if gid in G and m["fotmob_matchId"] in FMPM:
        pm = int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
        ours = sum(1 for r in raw_rows if r[1] == gid and r[0] == "a")
        if pm != ours: PM_DIFF.append((ldate(G[gid]), gid, opp(G[gid]), pm, ours))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
GOAL_FIX_GIDS = {k[0] for k in GOAL_FIX}
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0) + (1 if gid in GOAL_FIX_GIDS else 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split("-"))
    if (h, a) != (fh, fa) and G[gid]["gameState"] != "penalty_shootout": SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))

# ---------------------------------------------------------------- 이름·기존 자료
ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
MANUAL_ALIAS = {}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue   # 내 자료만 쓴 팀×시즌은 건너뜀(다른 선수와 같이 쓴 행은 그대로, 오스카 선례)
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())   # 다른 심판의 새 파일(추적 안 됨)은 비교에서 뺌
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "clubcolors.js", "finals.js", "bsw.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "paulista", "paulo", "ca", "cs", "deportivo", "deportes", "universidad", "san", "santa", "fk", "vfl", "bv",
        "racing", "arsenal", "juniors", "plate", "river", "nacional", "independiente", "estudiantes", "union", "boca", "gimnasia", "esgrima", "lorenzo", "almagro", "hotspur", "palace", "villa", "ham", "manchester", "verona", "sheffield", "bristol", "birmingham", "nottingham", "queens", "park", "west", "aston",
        "new", "york", "los", "angeles", "toronto", "vitoria", "guimaraes", "setubal", "borussia", "werder", "bayer", "eintracht", "hertha", "olympiacos", "panathinaikos",
        "rio", "ave", "al", "qatar", "rayyan", "mexico", "cruz", "azul", "guadalajara", "once", "caldas", "medellin", "bogota", "leon", "minnesota",
        "kyiv", "donetsk", "dynamo", "brugge", "royal", "metalurh", "metalurg", "kv", "kfc", "ksk", "krc", "kaa", "raa", "stade", "bromwich", "crystal", "norwich", "swansea", "southampton", "stoke", "hull", "chang",
        "hnk", "nk", "gnk", "zagreb", "balompie", "vigo", "fsv", "tsv", "bsc", "munich", "barcelona", "sevilla", "basel", "schalke", "hajduk", "split"}
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
        lg_ = "MLSO" if p[0].startswith("MLS overall") else p[0]   # MLS 전체 순위(en.wikipedia 시즌 문서 Overall table)
        RANKS[(lg_, p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1])

EU_LG = {"L1": "분데스리가", "GB1": "프리미어리그"}
def make_label(lg, season, v):
    r, n, nm, sraw = v
    if lg == "MLSO": return f"MLS {season} {r}위/{n}팀"
    if lg == "L2": return f"2. 분데스리가 {season} {r}위/{n}팀"
    if lg == "GB2": return f"챔피언십 {season} {r}위/{n}팀"
    if lg == "RU1": return f"러시아 1부 {season} {r}위/{n}팀 (Russian Premier League)"
    if lg == "WER1": return f"벨라루스 1부 {season} {r}위/{n}팀 (Belarusian Premier League)"
    if lg == "USL": return f"USL 동부 {season} {r}위/{n}팀 (USL Eastern Conference)" if "group1" in sraw else f"USL 서부 {season} {r}위/{n}팀 (USL Western Conference)"
    if lg in EU_LG:
        pre = EU_LG[lg]; n0 = _LRA["ERA"]["teams"](pre, int(season[:4]) + 1)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    return None

# 상대 시즌: 바이에른은 7월 10일 기준(DFL-리가포칼·DFL-슈퍼컵 7월 경기 = 새 시즌, 크로스·클로제 등 다른 바이에른 선수 자료와 같음),
# 맨유는 8월 1일 기준, 시카고 파이어(MLS)는 달력 연도. 달력 연도 리그 상대(러시아·벨라루스)는 경기 연도.
JUL10 = {"27"}
def season_of(d, club_id):
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    if club_id == "432": return d[:4]
    if club_id in JUL10: s_ = y if (m > 7 or (m == 7 and dd >= 10)) else y - 1
    else: s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
def seasons_for(cid, d, o, g):
    s = season_of(d, g["clubId"])
    return [s] if s == d[:4] else [s, d[:4]]
GER = ["L1", "L2"]; ENG = ["GB1", "GB2"]; USA = ["MLSO", "USL"]
EUR = ["L1", "GB1", "RU1", "WER1"]
def lg_cands(cid, d, o, g):
    ss = seasons_for(cid, d, o, g)
    if cid in ("MLS1", "MLSP", "POUS"): return [(lg, ss[0]) for lg in USA]
    if cid in ("L1", "DFB", "DFL", "LPO"): return [(lg, ss[0]) for lg in GER]
    if cid in ("GB1", "FAC", "CGB"): return [(lg, ss[0]) for lg in ENG]
    return [(lg, s) for s in ss for lg in EUR]

MAN = {}
def man(o, s, lv): MAN[(key(o), s)] = lv
FORCE = {}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []

def opp_elo(o, d, cid, g):
    if g["gameId"] in FORCE:
        lv = FORCE[g["gameId"]]; e = lv_value(lv, d, o); ELO_SRC["직접 라벨(이름 겹침)"] += 1
        ELO_LOG[(o, d)] = ("force", e, lv); return e, lv
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
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
    for s in seasons:
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d, o); map_check(lv, o); ELO_SRC["직접 라벨(순위표 밖)"] += 1
            ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    for lg, s in lg_cands(cid, d, o, g):
        t = RANKS.get((lg, s), {})
        if k in t:
            lv = make_label(lg, s, t[k])
            if lv:
                e = lv_value(lv, d, o); map_check(lv, o); ELO_SRC["순위표 → 라벨"] += 1
                ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, seasons[0])] = (e, lv); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
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
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]): print(d, o, v)
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
    tm = [e for e in evs if (e["scorer_id"] == ME and not is_og(e)) or (gid, e["minute"]) in GOAL_FIX]
    fm = [r for r in FME[gid] if r["schweinsteiger_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "1", "true")]
    if not FME[gid] or all(not r["time"] for r in FME[gid]): continue
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "penalty" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))
FM_N = sum(1 for gid in EVS if gid in G and gid in FME and any(r["schweinsteiger_scorer"] == "1" for r in FME[gid]))
FM_G = sum(1 for gid in EVS if gid in G and gid in FME for r in FME[gid] if r["schweinsteiger_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "1", "true"))

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
JRE = re.compile(r"Schweinsteiger|슈바인슈타이거", re.I)
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and JRE.search(str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(슈바인슈타이거 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("슈바인슈타이거 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 슈바인슈타이거 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
SHARED = collections.defaultdict(set)   # 같은 경기 출전(다른 선수 M) — 공유 경기 목록
for b, (oe, om) in OTHERS.items():
    od = {mm[0]: mm for mm in om}
    for m in M:
        mm = od.get(m[0])
        if mm and same_team(mm[1], m[1]): SHARED[b].add(m[0])

# ---------------------------------------------------------------- 클럽·시즌
# 클럽 구분: Transfermarkt 이적일(맨유 2015.7.13, 시카고 파이어 2017.3.21)
STINTS = [("바이에른 뮌헨", "2015-07-13"), ("맨체스터 유나이티드", "2017-03-21"), ("시카고 파이어", "9999")]
TM_CLUB = {"27": "바이에른 뮌헨", "985": "맨체스터 유나이티드", "432": "시카고 파이어"}
def stint(d):
    for n, u in STINTS:
        if d < u: return n
for g in GAMES:
    if stint(ldate(g)) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ORDER = ["바이에른 뮌헨", "맨체스터 유나이티드", "시카고 파이어"]
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for n in ORDER)
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
TM_G = sum(int(g["goals"] or 0) for g in GAMES)
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), "TM_A", TM_A, "TM_G", TM_G)
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    print("FM only", FM_ONLY); print("PM diff", PM_DIFF)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G, FM_CMP)
    print("SCORE_MISMATCH", SCORE_MISMATCH)
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF)
    for k, v in sorted(MAP_NEED.items()): print("MAP_NEED", k, v)
    print("SHARED", {b: len(v) for b, v in sorted(SHARED.items(), key=lambda kv: -len(kv[1]))})
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_schweinsteiger.py"), encoding="utf-8").read())
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl", "mlp", "lcg", "lck"]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const BSW_E={J(E)};\nconst BSW_M={J(M)};\nconst BSW_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "fotmob_playermatches_diff": PM_DIFF, "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "table_label_diffs": TABLE_DIFF, "points_map_needed": [f"{k[0]} | {k[1]} | {v[0]} | {v[1]}" for k, v in sorted(MAP_NEED.items())],
               "shared_games": {b: sorted(v) for b, v in SHARED.items()},
               "excluded_games": [[g["date_local"], g["club"], g["opponent"], g["competitionId"], g["playedMinutes"], g["goals"]] for g in EXCL],
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
