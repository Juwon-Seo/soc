#!/usr/bin/env python3
"""루카 모드리치 (Luka Modrić, Transfermarkt 27992): raw/ -> modric.json + players/modric/mod.js (판정 근거는 judgments.md)

  python3 players/modric/build_modric.py [--out <data 폴더>]   # 파일 쓰기(기본 players/modric/mod.js; 스크래치 검증 때 --out <복사본>/src/data)
  python3 players/modric/build_modric.py --debug               # Elo 출처 로그
  python3 players/modric/build_modric.py --stat                # 요약·판정·동료 대조
  python3 players/modric/build_modric.py --ties                # 합산 행

크로스(build_kroos.py) 스크립트를 바탕으로 모드리치 수집 형식(tm_games/tm_events/tm_match_info 열 이름)에 맞춤.
순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의 parse()/value()(승점 모형 포함)로 라벨에서 계산(직접 숫자를 넣지 않음).
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값(스크래치 복사본에서는 SOC_ROOT=<복사본>).
보조: assist_checks.py(도움 판정 근거), man_elo.py(순위표 밖 상대 라벨), note_modric.py(설명).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "mod.js")
OUT_JSON = os.path.join(HERE, "modric.json")
ME = "27992"
ME_KO = "루카 모드리치"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {}
for r in rd("tm_match_info.csv"):
    r["final"] = f'{r["final_home"]}:{r["final_away"]}' if r["final_home"] != "" else ""
    r["round_report"] = r["report_round"]
    MI[r["gameId"]] = r
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"):
    e["side"] = "h" if e["side"] == "home" else "a"
    e["assist_type"] = e["html_assist_type"] if e["html_assist_type"] != "Without assist" else ""
    e["goal_desc"] = e["html_goal_desc"]
    EVS[e["gameId"]].append(e)
for k in EVS: EVS[k].sort(key=lambda e: int(e["idx"]))
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    r["sq_assist"] = r["modric_assist"]; r["sq_scorer"] = r["modric_scorer"] if r["ownGoal"] not in ("True", "1", "true") else "0"
    FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["fotmob_matchId"]}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 날짜
# TM API 경기 시각(UTC)을 클럽 연고지 시간대로 바꾼 날짜(date_local). 같은 경기 다른 선수 자료(M) 날짜와 대조해 다르면 보고(아래 DATE_CMP).
LD = {gid: g["date_local"] for gid, g in G.items()}
def ldate(g): return LD[g["gameId"]]
OPP_NAME = {}
RENAME = {"NK Inker": "NK Inter Zapresic"}   # TM 옛 이름 표기 → 다른 선수 자료와 같은 이름
def opp(g):
    n = OPP_NAME.get(g["gameId"]) or re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
    return RENAME.get(n, n)

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용(정상 유형)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"KR1", "BOS1", "GB1", "ES1", "IT1"}
CUPS = {"KRC", "FAC", "CGB", "CDR", "CIT"}
SUPER = {"HRSC", "SUC", "USC", "SCI"}   # 슈퍼컵류 = 국내컵 결승 비중, 4팀 수페르코파·수페르코파 이탈리아나 준결승은 국내컵 준결승(다른 레알·밀란 선수 자료 같은 경기)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "dsf" if r.startswith("semi") else "df"
    if cid in ("KLUB", "FIC1"): return "cwc"   # 클럽 월드컵·FIFA 인터콘티넨털컵(벨링엄·비니시우스 자료 같은 경기)
    if cid == "UEFA":   # UEFA컵 1라운드(조별 전 두 경기) = 유로파 예선 비중, 조별, 32강 이후
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid in CUPS:   # 16강까지 국내컵, 8강 이후 단계별(FA컵 6라운드 = 8강, 재경기 포함)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or (cid == "FAC" and r.startswith("sixth")): return "dk"
        return "dc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 2024-25부터 리그 페이즈(TM 'Group Stage')도 조별과 같은 비중
        if r.startswith("intermediate"): return "cl16"   # 녹아웃 플레이오프 = 16강 비중
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
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
    if cid in ("CL", "UEFA", "CLQ", "EL"): return (1, 1) if d < "2021-08-01" else (0, 1)   # UEFA 2020-21까지 원정 다득점(연장 포함)
    if cid == "CDR": return (1, 1) if d < "2019-08-01" else (0, 1)
    if cid == "SUC": return (1, 1)   # 두 경기 수페르코파(2012·2014·2017): 원정 다득점·연장(호날두·크로스 자료와 같음)
    if cid == "KRC": return (1, 0)   # 크로아티아컵: 원정 다득점, 연장 없이 승부차기(만주키치 자료와 같음)
    if cid == "CGB": return (1, 1)   # 리그컵 준결승(베일 자료 2009.1 번리전과 같음)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

TIES2 = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
def other_leg(gid):
    t = TIES2.get(gid); club = G[gid]["club_id"]
    oid = t["other_leg_gameId"] if t else (MI[gid]["report_other_leg_id"])
    if oid in MI and MI[oid]["final"]:
        o = MI[oid]; fh, fa = map(int, o["final"].split(":"))
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    oh, oa = map(int, re.split("[-:]", t["other_leg_final_home_away"]))
    return (oa, oh) if side_of(gid) == "h" else (oh, oa)   # 다른 차전은 홈·원정이 바뀜

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
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

A_CHECK = {}; ADD_A = []
def a_key(gid, minute): return f"{gid}|{minute}"
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["sq_assist"] == "1" and f["pen_shootout_event"] != "True" and fm_min_match(f, e["minute"]): return True
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
def fm_confirmed(gid):
    return sum(1 for e in EVS.get(gid, []) if e["assist_id"] == ME and e["scorer_id"] != ME and fm_assist(gid, e))
def assist_reason(e, d, gid):
    t = e["assist_type"]
    k = a_key(gid, e["minute"])
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return A_CHECK[k][1] if k in A_CHECK else "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    if d < GAP:
        if k in A_CHECK and not A_CHECK[k][0]: return A_CHECK[k][1]
        return None
    fa, pm = fm_assist(gid, e), fm_pm_assists(gid)
    if fa:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if pm and pm > fm_confirmed(gid) and k not in A_CHECK:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], f"TM+FotMob 선수 경기 목록(도움 {pm})")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "2014.8 이후 단일 출처(확인 못 함)"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], f"판정 없음 FMpm={pm}"))
    return "2014.8 이후 단일 출처(판정 없음)"

MIN_FIX = {}
raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        sd = e["side"]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e): sys.exit("자책골 " + gid)
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(MIN_FIX.get((gid, e["minute"]), e["minute"]))
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

for gid, mi, gf, ga, pk, scorer, why in ADD_A:
    raw_rows.append(("a", gid, mi, 0, gf, ga, 0, scorer, "added"))
    judg.append(("도움 추가(FotMob 단독 + 다른 출처 2곳)", ldate(G[gid]), opp(G[gid]), str(mi), scorer, why))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["sq_assist"] == "1" and f["pen_shootout_event"] != "True":
            mi = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(e["assist_id"] == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, mi, f["scorer"]))
PM_ONLY = []
for gid, m in FMMAP.items():
    if gid in G and m["fotmob_matchId"] in FMPM:
        pm = int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
        tm = sum(1 for e in EVS.get(gid, []) if e["assist_id"] == ME and e["scorer_id"] != ME)
        if pm > tm: PM_ONLY.append((ldate(G[gid]), gid, opp(G[gid]), pm, tm))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"] == "h"); a = sum(1 for e in evs if e["side"] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
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
MANUAL_ALIAS.update({norm("NK Inker"): key("NK Inter Zapresic"), norm("NK Varteks Varazdin"): key("NK Varaždin (1931–2015)"),
                     norm("NK Pula Staro Cesko"): key("NK Istra 1961"), norm("NK Istra Pula"): key("NK Istra 1961"), norm("NK Pula 1856"): key("NK Istra 1961"),
                     norm("NK Medjimurje Cakovec"): key("NK Međimurje"), norm("NK Kamen Ingrad Velika"): key("NK Kamen Ingrad"),
                     norm("HNK Cibalia Vinkovci"): key("HNK Cibalia"), norm("HNK Zadar"): key("NK Zadar"), norm("Slaven Belupo Koprivnica"): key("NK Slaven Belupo")})

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
    if b in ("hon.js", "clubcolors.js", "finals.js", "mod.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
PEERS = ("schweinsteiger/bsw.js", "xavi/xav.js", "pirlo/apl.js", "vieira/pvi.js")
for b in PEERS:   # 같은 라운드 다른 심판 자료(아직 src/data에 없음): 대조만(Elo 값은 가져오지 않음)
    fn = os.path.join(os.path.dirname(HERE), b)
    if os.path.exists(fn) and "--no-peers" not in sys.argv:
        P, oe, om = load_js(fn); OTHERS["peer:" + b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    if b.startswith("peer:"): continue
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "paulista", "paulo", "ca", "cs", "deportivo", "deportes", "universidad", "san", "santa", "fk", "vfl", "bv",
        "racing", "arsenal", "juniors", "plate", "river", "nacional", "independiente", "estudiantes", "union", "boca", "gimnasia", "esgrima", "lorenzo", "almagro", "hotspur", "palace", "villa", "ham", "manchester", "verona", "sheffield", "bristol", "birmingham", "nottingham", "queens", "park", "west", "aston",
        "new", "york", "los", "angeles", "toronto", "vitoria", "guimaraes", "setubal", "borussia", "werder", "bayer", "eintracht", "hertha", "olympiacos", "panathinaikos",
        "rio", "ave", "al", "qatar", "rayyan", "mexico", "cruz", "azul", "guadalajara", "once", "caldas", "medellin", "bogota", "leon", "minnesota",
        "kyiv", "donetsk", "dynamo", "brugge", "royal", "metalurh", "metalurg", "kv", "kfc", "ksk", "krc", "kaa", "raa", "stade", "bromwich", "crystal", "norwich", "swansea", "southampton", "stoke", "hull", "chang",
        "nk", "hnk", "gnk", "zagreb", "sarajevo", "split"}
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

# 순위표: TM 표(raw/ranks.txt) + 위키백과 표(raw/ranks_wiki.txt, 크로아티아 2004-05·2005-06은 스플릿 뒤 최종 순위 = 챔피언십/강등 그룹 순위)
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[0].startswith("#"): continue
        if p[0] == "KR1" and p[1] in ("04/05", "05/06"): continue   # TM 표는 챔피언십 6팀만 → 위키백과 표 사용
        s = p[1]
        if "/" in s: s = "20" + s[:2] + "-" + s[3:]
        RANKS[(p[0], s)][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1])
WIKI_LG = {"Premier_League_of_Bosnia": "BOS1", "Croatian_First_Football_League": "KR1"}
_wk = collections.defaultdict(list)
with open(os.path.join(RAW, "ranks_wiki.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "file" or p[0].startswith("#"): continue
        lg = next((v for k, v in WIKI_LG.items() if k in p[0]), None)
        if not lg or p[1] == "First stage": continue
        _wk[(lg, p[0][:7])].append((int(p[2]), p[3], p[4]))
for (lg, s), rows in _wk.items():
    n = len(rows)
    for r, nm, disp in rows:
        for x in (nm, disp): RANKS[(lg, s)][key(x)] = (r, n, nm, s)
CUR = "2026-27"   # 진행 중 시즌(2026년 11월 25일 현재 순위)
EU_LG = {"ES1": "라리가", "GB1": "프리미어리그", "IT1": "세리에A"}
def make_label(lg, season, v):
    r, n, nm, sraw = v
    cur = " (2026년 11월 25일 현재 순위)" if season == CUR else ""
    if lg == "KR1": return f"크로아티아 1부 {season} {r}위/{n}팀" + (" (Prva HNL, 스플릿 뒤 최종 순위)" if season in ("2004-05", "2005-06") else " (Prva HNL)")
    if lg == "BOS1": return f"보스니아 헤르체고비나 1부 {season} {r}위/{n}팀 (Premier League of Bosnia and Herzegovina)"
    if lg in EU_LG:
        pre = EU_LG[lg]; n0 = _LRA["ERA"]["teams"](pre, int(season[:4]) + 1)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 or cur else "") + cur
    return None

# 상대 시즌: 크로아티아·보스니아 클럽은 7월 1일 기준(디나모 자그레브 2006.7.19 슈퍼컵 = 2006-07, 만주키치 자료와 같음), 나머지는 8월 1일 기준.
CRO = {"6808", "918", "419"}
def season_of(d, club_id):
    y, m = int(d[:4]), int(d[5:7])
    if club_id in CRO: s_ = y if m >= 7 else y - 1
    elif d.startswith("2020-08"): s_ = 2019
    else: s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
def seasons_for(cid, d, o, g):
    return [season_of(d, g["club_id"])]
DOM = {"KR1": ["KR1"], "KRC": ["KR1"], "HRSC": ["KR1"], "BOS1": ["BOS1"], "GB1": ["GB1"], "FAC": ["GB1"], "CGB": ["GB1"],
       "ES1": ["ES1"], "CDR": ["ES1"], "SUC": ["ES1"], "IT1": ["IT1"], "CIT": ["IT1"], "SCI": ["IT1"]}
def lg_cands(cid, d, o, g):
    s = seasons_for(cid, d, o, g)[0]
    return [(lg, s) for lg in DOM.get(cid, ["ES1", "GB1", "IT1"])]

MAN = {}
def man(o, s, lv): MAN[(key(o), s)] = lv
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
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["sq_scorer"] == "1" and r["pen_shootout_event"] != "True"]
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
JRE = re.compile(r"Modri|모드리치", re.I)
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and JRE.search(str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(모드리치 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("모드리치 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 모드리치 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
# 날짜 대조: 같은 상대·±1일인 다른 선수 출전 행이 있는데 같은 날짜 행이 없으면 보고
DATE_CMP = []
from datetime import date as _dt, timedelta as _td
OM_BY = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for mm in om: OM_BY[mm[0]].append((b, mm))
for m in M:
    same = [x for x in OM_BY.get(m[0], []) if same_team(x[1][1], m[1]) and x[1][2] == m[2]]
    if same: continue
    y, mo, dd = map(int, m[0].split("-"))
    for dlt in (-1, 1):
        d2 = str(_dt(y, mo, dd) + _td(days=dlt))
        near = [x for x in OM_BY.get(d2, []) if key(x[1][1]) == key(m[1]) and x[1][2] == m[2]]
        if near: DATE_CMP.append((m[0], m[1], m[2], d2, sorted({x[0] for x in near})))

# ---------------------------------------------------------------- 클럽·시즌
# 클럽 구분: 즈린스키 임대 2003-04, 인테르 자프레시치 임대 2004년 하반기, 디나모 자그레브 2005년 1월~, 토트넘 2008.7.1, 레알 2012.8.27, 밀란 2025.7.14
STINTS = [("즈린스키 모스타르", "2004-07-01"), ("인테르 자프레시치", "2005-01-01"), ("디나모 자그레브", "2008-07-01"),
          ("토트넘 홋스퍼", "2012-08-27"), ("레알 마드리드", "2025-07-14"), ("AC 밀란", "9999")]
TM_CLUB = {"6808": "즈린스키 모스타르", "918": "인테르 자프레시치", "419": "디나모 자그레브", "148": "토트넘 홋스퍼", "418": "레알 마드리드", "5": "AC 밀란"}
def stint(d):
    for n, u in STINTS:
        if d < u: return n
for g in GAMES:
    if stint(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ORDER = [s[0] for s in STINTS]
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
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A)
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    print("FM only", FM_ONLY); print("PM only", PM_ONLY)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G, FM_CMP)
    print("SCORE_MISMATCH", SCORE_MISMATCH)
    for x in DATE_CMP: print("DATE?", x)
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF)
    for k, v in sorted(MAP_NEED.items()): print("MAP_NEED", k, v)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_modric.py"), encoding="utf-8").read())
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const MOD_E={J(E)};\nconst MOD_M={J(M)};\nconst MOD_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "fotmob_playermatches_only": PM_ONLY, "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "table_label_diffs": TABLE_DIFF, "points_map_needed": [f"{k[0]} | {k[1]} | {v[0]} | {v[1]}" for k, v in sorted(MAP_NEED.items())],
               "date_checks": DATE_CMP, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
