#!/usr/bin/env python3
"""레안드로 트로사르 (Leandro Trossard, Transfermarkt 144028): raw/ -> trossard.json + players/trossard/tro.js (판정 근거는 judgments.md)

  python3 players/trossard/build_trossard.py [--out <data 폴더>]   # 파일 쓰기(기본 players/trossard/tro.js; 스크래치 복사본 검증 때 --out <복사본>/src/data)
  python3 players/trossard/build_trossard.py --debug               # Elo 출처 로그만 출력
  python3 players/trossard/build_trossard.py --stat                # 요약·판정·동료 대조
  python3 players/trossard/build_trossard.py --ties                # 합산 행

황희찬 build 스크립트(같은 수집 형식)를 바탕으로 함. 순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의
parse()/value()로 라벨에서 계산(v1.226 규칙, 직접 숫자를 넣지 않음). 같은 경기가 다른 선수 자료(이번 회차 마타·나스리·큐얼 판정 결과 포함)에
있으면 그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
보조: assist_checks.py(2014.8 이후 단일 출처 도움 웹 확인), man_elo.py(순위표 밖 상대 라벨), note_trossard.py(설명),
mls_overall_ranks.txt(MLS 서포터스 실드 전체 순위, 베르나르데스키·인시녜 원자료와 같음).
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "tro.js")
OUT_JSON = os.path.join(HERE, "trossard.json")
ME = "144028"
ME_KO = "레안드로 트로사르"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")   # 1군 클럽 공식 경기 577개(바젤 U21·U18은 raw/youth_reserve_games.csv에 따로 있음)
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["status"] == "OK"}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 날짜
# 모든 경기: TM API 경기 시각(UTC)을 경기장 시간대로 바꾼 현지 날짜(raw/tm_games.csv date_local_tz_conv; 북미 저녁 경기는
# TM 일정·리포트가 UTC 날짜라 하루 늦음 → 현지 날짜, FotMob 시각 변환과 같음). 예외 두 경기:
#  3994090 2023 MLS 세인트루이스전: TM API UTC 2023-05-12 22:00이지만 TM 일정·리포트·FotMob·ESPN 모두 2023-05-13(토) → 5.13
#  3291619 2019 클럽 월드컵 준결승 몬테레이전(도하): 도하 현지 2019-12-18 20:30(TM·위키백과 12.18, FotMob 시각 변환만 12.17) → 12.18(변환값 그대로)
DATE_FIX = {}   # TM UTC 변환·TM 일정·리포트·FotMob 날짜가 모두 같음(raw/tm_date_disagreements.csv 0건)
DATE_LOG = []
LD = {}
for gid, g in G.items():
    LD[gid] = DATE_FIX.get(gid, g["date_local_tz_conv"])
    if LD[gid] != g["date_local_schedule"]: DATE_LOG.append((gid, g["date_local_schedule"], LD[gid], g["club"], g["opponent"]))
def ldate(g): return LD[g["gameId"]]
OPP_NAME = {}
def opp(g): return OPP_NAME.get(g["gameId"]) or re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
# 벨기에 1부·2부·PL·쉬페르리그 + 벨기에 챔피언 플레이오프(EJPL)·유로파 플레이오프(POBE)·유로파 결정전(ESJP)·2부 승격 결선 라운드(EBEL) = 리그
LEAGUE = {"BE1", "BE2", "GB1", "TR1", "EJPL", "POBE", "ESJP", "EBEL"}
CUPS = {"CCB", "FAC", "CGB"}   # 벨기에컵·FA컵·리그컵
SUPER = {"GBCS"}               # 커뮤니티 실드 = 국내컵 결승 비중

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "df"
    if cid in CUPS:   # 16강까지 국내컵, 8강(리그컵 5라운드·FA컵 6라운드) 이후 단계별(docs 3절)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or (cid == "FAC" and r.startswith("sixth")) or (cid == "CGB" and r.startswith("fifth")): return "dk"
        return "dc"
    if cid == "KLUB": return "cwc"
    if cid == "USMX": return "lcg" if r.startswith("group") else "lck"
    if cid == "CLQ": return "clq"
    if cid == "ELQ": return "elq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"   # 2025-26 리그 페이즈('Group Stage') 포함
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 2010-11 32강('Second Round')·2014-15 32강(intermediate stage)·16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g):
    return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if cid == "USMX": return 1   # 리그스컵 2023 조별: 무승부면 승부차기로 승점을 가림 → 단판(기존 자료 2023·2024 조별 행과 같음)
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "EL", "CLQ", "ELQ"): return (1, 1) if d < "2021-08-01" else (0, 1)   # UEFA 2020-21까지 원정 다득점(연장 포함)
    if cid == "CCB": return (1, 1)   # 벨기에컵 두 경기 합산(2013-14 8강·2016-17 4강): 원정 다득점·연장(기존 선수 자료 같은 대회 행과 같음)
    if cid == "CGB": return (0, 0)   # 리그컵 준결승(2024-25·2025-26): 원정 다득점·연장 없이 바로 승부차기
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; oid = m["other_leg_id"]; club = G[gid]["club_id"]
    if not oid:   # 리포트에 다른 차전 링크가 없는 2차전(2009 KR 레이캬비크·FC 바쿠, 2025 코펜하겐): 같은 대회·상대의 1차전(TM 경기 목록)
        g = G[gid]; c = [x for x in GAMES if x["competitionId"] == g["competitionId"] and x["opponent_id"] == g["opponent_id"] and "1st" in rnd_of(x).lower() and x["gameId"] != gid]
        if len(c) != 1: sys.exit("다른 차전 없음 " + gid)
        oid = c[0]["gameId"]
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
MIN_EST = {}   # 모든 경기에 TM 출전 분 있음
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
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())   # A_CHECK 채움(근거 포함)

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["sq_assist"] == "1" and f["pen_shootout_event"] != "True" and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])): return True
    return False
def same_scorer(a, b):
    ta, tb = norm(a).split(), norm(b).split()
    return bool(ta and tb and ta[-1] == tb[-1])
def fm_pm_assists(gid):
    m = FMMAP.get(gid)
    if m and m["fotmob_matchId"] in FMPM: return int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
    return None

def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

A_STATUS = []   # 2014.8 이후 도움 판정 기록
def fm_confirmed(gid):
    return sum(1 for e in EVS.get(gid, []) if e["assist_id"] == ME and e["scorer_id"] != ME and fm_assist(gid, e))
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

MIN_FIX = {}   # 골·도움 시각은 모두 Transfermarkt 그대로
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
            if e["goal_desc"] == "Penalty rebound": judg.append(("PK 리바운드 골(PK 아님)", ldate(g), opp(g), e["minute"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

# FotMob에만 있는 도움 중 다른 출처 2곳으로 확인한 것(assist_checks.py ADD_A): (gid, 분, 원정 여부 무관 우리 팀 기준 gf, ga, pk, 득점자, 근거)
for gid, mi, gf, ga, pk, scorer, why in ADD_A:
    raw_rows.append(("a", gid, mi, 0, gf, ga, 0, scorer, "added"))
    judg.append(("도움 추가(FotMob 단독 + 다른 출처 2곳)", ldate(G[gid]), opp(G[gid]), str(mi), scorer, why))
    A_STATUS.append((ldate(G[gid]), gid, str(mi), scorer, "넣음(FotMob 단독): " + why))

# FotMob 전용 도움(TM 도움 없음): 판정 기록만(A_CHECK에 있으면 넣음)
FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["sq_assist"] == "1" and f["pen_shootout_event"] != "True":
            mi = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(e["assist_id"] == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, mi, f["scorer"]))
# FotMob 선수 경기 목록에만 있는 도움(이벤트·TM 없음): 3889048 2022.10.22 파네톨리코스전(FotMob 선수 목록 도움 1, TM·FotMob 이벤트 없음)
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
MANUAL_ALIAS = {}   # 통합표 표기에 맞춤(필요하면 추가)
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "tro.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
# 이번 회차에 함께 판정한 선수(판정 끝남, 읽기만): 같은 경기면 같은 Elo/lv
for slug, fn in (("palmer", "pal.js"), ("guirassy", "gui.js"), ("quagliarella", "qua.js"), ("aduriz", "adu.js")):
    pth = os.path.join(os.path.dirname(HERE), slug, fn)
    if os.path.exists(pth):
        P, oe, om = load_js(pth); OTHERS["players/" + slug + "/" + fn] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "paulista", "paulo", "ca", "cs", "deportivo", "deportes", "universidad", "san", "santa", "fk", "vfl", "bv",
        "racing", "arsenal", "juniors", "plate", "river", "nacional", "independiente", "estudiantes", "union", "boca", "gimnasia", "esgrima", "lorenzo", "almagro", "hotspur", "palace", "villa", "ham", "manchester", "verona", "sheffield", "bristol", "birmingham", "nottingham", "queens", "park", "west", "aston",
        "new", "york", "los", "angeles", "toronto", "vitoria", "guimaraes", "setubal", "borussia", "werder", "bayer", "eintracht", "hertha", "olympiacos", "panathinaikos",
        "rio", "ave", "al", "sc", "qatar", "rayyan", "atletico", "mexico", "cruz", "azul", "guadalajara", "deportivo", "once", "caldas", "medellin", "bogota", "leon", "minnesota"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
SA_DOM = {"ARG1", "ARGC", "CLI", "CS", "BRA1", "BCP1", "BCPF", "MEX1", "MEXA", "POME", "USMX", "MLS1", "MLSP", "COL1", "COPO", "QSL", "QEC1", "KLUB"}
def same_match(o, d, cid):
    if cid in SA_DOM:
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
def lv_value(lv, d):
    m_ = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv)
    if m_:
        cal = m_.group(4) is None; y = int(m_.group(3)) + (0 if cal else 1)
        return int(round(_LRA["base"](_LRA["KO"][m_.group(1)], int(m_.group(2)), y, cal)))
    p = _LRA["parse"](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA["value"](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    return v

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] in ("league",) or p[0].startswith("#"): continue
        r, n = int(p[2]), int(p[3])
        se = p[1].split(" ")[0]
        if p[0] == "PL1" and p[1].endswith("group2"): r, n = r + 8, 16   # 폴란드 2018-19: 강등 그룹 1~8위 = 최종 9~16위
        elif p[0] == "PL1" and p[1].endswith("group1"): n = 16
        RANKS[(p[0], se)][key(p[4])] = (r, n, p[4], p[1])
# 벨기에 2부 2012-13: 승점 33 동률 FC 브뤼셀·비제는 승수 우선(공식 규칙)으로 브뤼셀 14위·비제 15위 — 영어 위키백과 '2012–13 Belgian Second Division'·FotMob 순서
# (Transfermarkt 표만 골득실로 비제 14위·브뤼셀 15위)
for nm_, r_ in (("FC Brüssel", 14), ("CS Visé (-2015)", 15)):
    k_ = key(nm_); v_ = RANKS[("BE2", "2012-13")][k_]; RANKS[("BE2", "2012-13")][k_] = (r_, v_[1], v_[2], v_[3] + " 위키백과 순서")
# 벨기에 1부 최종 순위(기존 선수 자료와 같은 방식): 챔피언 플레이오프(플레이오프 1) 최종 1~6위, 나머지는 정규 시즌 순서,
# 강등 플레이오프(2014-15까지 15·16위 팀 대결) 승자 15위·패자 16위. 표는 FotMob 리그 자료(raw/ranks_fotmob.txt) — 정규 시즌 승점 동률 순서가
# Transfermarkt 표와 다른 시즌(2012-13·2013-14·2015-16)은 FotMob·공식 순서(승수 우선)이고 기존 선수 자료 값도 FotMob 순서와 같음. 팀 이름은 TM 표(raw/ranks.txt)로 연결.
FM2TM = {"st truiden": "sint truidense vv", "sporting charleroi": "royal charleroi sc", "royal excel mouscron": "mouscron", "sk beveren": "kvrs waasland",
         "mons": "raec mons", "oh leuven": "oud heverlee leuven", "eupen": "kas eupen", "lokeren": "ksc lokeren", "kortrijk": "kv kortrijk",
         "oostende": "kv oostende", "anderlecht": "rsc anderlecht", "gent": "kaa gent", "genk": "krc genk", "westerlo": "kvc westerlo",
         "club brugge": "club brugge kv", "lierse": "lierse sk", "royal antwerp": "royal antwerp fc"}
FMBE = collections.defaultdict(lambda: collections.defaultdict(list))
with open(os.path.join(RAW, "ranks_fotmob.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or not p[0].startswith("40 "): continue
        se = p[1][:5] + p[1][7:9]
        kind = "po1" if "Championship Group" in p[0] else "rel" if "Relegation" in p[0] else "po2" if "EL" in p[0] else "reg"
        FMBE[se][kind].append((int(p[2]), p[4]))
for se, tabs in FMBE.items():
    reg = RANKS.get(("BE1", se))
    if not reg: continue
    regk = {norm(v[2]): k for k, v in reg.items()}
    def tmk(nm):
        t = FM2TM.get(norm(nm), norm(nm))
        hit = [k for nn, k in regk.items() if nn.startswith(t) or (" " + t) in (" " + nn)]
        if len(hit) != 1: sys.exit(f"벨기에 표 이름 연결 실패 {se} {nm} {hit}")
        return hit[0]
    n = len(reg); order = [tmk(nm) for r, nm in sorted(tabs["reg"])]
    if len(order) != n or set(order) != set(reg): sys.exit("벨기에 정규 시즌 표 팀 다름 " + se)
    tag = {k: "정규 시즌" for k in order}
    top = [tmk(nm) for r, nm in sorted(tabs["po1"])]
    if set(top) != set(order[:6]): sys.exit("플레이오프 팀이 정규 시즌 1~6위와 다름 " + se)
    order = top + order[6:]
    for k in top: tag[k] = "플레이오프 뒤"
    if tabs["rel"]:
        rel = [tmk(nm) for r, nm in sorted(tabs["rel"])]
        if set(rel) != set(order[-2:]): sys.exit("강등 플레이오프 팀 다름 " + se)
        order = order[:-2] + rel
        for k in rel: tag[k] = "플레이오프 뒤"
    for i, k in enumerate(order): reg[k] = (i + 1, n, reg[k][2], se + " " + tag[k])
# 다른 FotMob 표(TM 표가 없거나 진행 중인 2026-27): 체코 2026-27, 리투아니아 2026, 스코틀랜드 2026-27(TM 받기 실패), 몬테네그로
FM_LG = {"122 1. Liga": ("CZ1", None), "228 Toplyga": ("LIT1", None), "64 Premiership": ("SC1", None), "232 1. CFL": ("MNE1F", None)}
with open(os.path.join(RAW, "ranks_fotmob.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] not in FM_LG: continue
        se = p[1][:5] + p[1][7:9] if "-" in p[1] else p[1]
        RANKS[(FM_LG[p[0]][0], se)][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1] + " FotMob")

EU_LG = {"FR1": "리그1", "ES1": "라리가", "L1": "분데스리가", "GB1": "프리미어리그", "PO1": "포르투갈 1부", "IT1": "세리에A", "NL1": "에레디비시"}
OTHER1 = {"DK1": ("덴마크", "Superliga, 챔피언십 라운드 뒤 최종 순위"), "LUX1": ("룩셈부르크", "BGL Ligue"), "MNE1": ("몬테네그로", "Prva CFL"), "MNE1F": ("몬테네그로", "Prva CFL"),
          "NO1": ("노르웨이", "Eliteserien"), "SE1": ("스웨덴", "Allsvenskan"), "KR1": ("크로아티아", "HNL"), "IR1": ("아일랜드", "League of Ireland Premier Division"),
          "LI1": ("리투아니아", "A Lyga"), "LIT1": ("리투아니아", "A Lyga"), "CZ1": ("체코", "Fortuna Liga"), "SC1": ("스코틀랜드", "Scottish Premiership"),
          "TR1": ("튀르키예", "Süper Lig"), "RO1": ("루마니아", "Liga I"), "PL1": ("폴란드", "Ekstraklasa, 스플릿 뒤 최종 순위")}
def make_label(lg, season, v):
    r, n, nm, sraw = v
    cur = "2026년 11월 21일 현재 순위" if season in ("2026-27", "2026") else ""
    if lg == "BE1":
        ex = ", ".join(x for x in ("플레이오프·스플릿 뒤 최종 순위", cur) if x)
        lgn = "Belgian First Division A" if season >= "2016-17" else "Belgian Pro League"
        return f"벨기에 1부 {season} {r}위/{n}팀 ({lgn}" + (f", {ex}" if ex else "") + ")"
    if lg == "BE2":
        nm2 = "First Division B" if season >= "2016-17" else "Tweede Klasse"
        return f"벨기에 2부 {season} {r}위/{n}팀 ({nm2}, 리그 수준 추정)"
    if lg == "GB2": return f"챔피언십 {season} {r}위/{n}팀"
    if lg == "GB3": return f"잉글랜드 3부 {season} {r}위/{n}팀 (EFL League One, 리그 수준 추정)"
    if lg == "GB4": return f"잉글랜드 4부 {season} {r}위/{n}팀 (EFL League Two, 리그 수준 추정)"
    if lg in OTHER1:
        ko, en = OTHER1[lg]
        return f"{ko} 1부 {season} {r}위/{n}팀 ({en}" + (f", {cur}" if cur else "") + ")"
    if lg in EU_LG:
        pre = EU_LG[lg]; n0 = _LRA["ERA"]["teams"](pre, int(season[:4]) + 1)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "") + (f" ({cur})" if cur else "")
    return None

# 시즌: 기본 8월 1일 기준. 헹크·OH 뢰번 경기는 7월 10일 기준(벨기에 리그 7월 하순 개막·7월 유로파 예선 = 새 시즌, 시즌 구분과 같음).
# 달력 연도 리그(아일랜드·노르웨이·스웨덴·리투아니아)의 유로파 상대 = 경기 연도.
SEASON_OVR = {"3076988": "2017-18"}   # 2018.7.26 유로파 예선 2라운드 1차전 폴라 에슈: 룩셈부르크 2018-19는 8.5 개막(영어 위키백과) → 끝난 2017-18 시즌 순위
CAL_LG = {"IR1", "NO1", "SE1", "LI1", "LIT1"}
def seasons_for(cid, d, o, g):
    if g["gameId"] in SEASON_OVR: return [SEASON_OVR[g["gameId"]]]
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    if g["club_id"] in ("1184", "2727"): s_ = y if (m > 7 or (m == 7 and dd >= 10)) else y - 1   # 헹크·OH 뢰번: 7월 10일 기준
    else: s_ = y if m >= 8 else y - 1
    out = [f"{s_}-{str(s_ + 1)[2:]}"]
    if cid in ("EL", "ELQ", "CL"): out.append(str(y))
    return out
BEL = ["BE1", "BE2"]; ENG = ["GB1", "GB2", "GB3", "GB4"]
EUR = ["BE1", "FR1", "ES1", "IT1", "PO1", "L1", "GB1", "NL1", "DK1", "LUX1", "MNE1", "MNE1F", "NO1", "SE1", "KR1", "IR1", "LI1", "LIT1", "CZ1", "SC1", "TR1", "RO1", "PL1"]
def lg_cands(cid, d, o, g):
    ss = seasons_for(cid, d, o, g)
    doms = BEL if cid in ("BE1", "BE2", "CCB", "EJPL", "POBE", "ESJP", "EBEL") else ENG if cid in ("GB1", "FAC", "CGB", "GBCS") else ["TR1"] if cid == "TR1" else EUR
    out = []
    for lg in doms:
        for s_ in ss:
            if (lg in CAL_LG) == ("-" not in s_): out.append((lg, s_))
    return out

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산)
def man(o, s, lv): MAN[(key(o), s)] = lv
FORCE = {}   # gameId -> lv (이름이 겹쳐 통합표 값을 잘못 집는 경기: 라벨을 직접 지정, 값은 라벨에서 계산)
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []

def opp_elo(o, d, cid, g):
    if g["gameId"] in FORCE:
        lv = FORCE[g["gameId"]]; e = lv_value(lv, d); ELO_SRC["직접 라벨(이름 겹침)"] += 1
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
            if p and _LRA["value"](*p) not in (None, e): TABLE_DIFF.append((o, s, e, lv, _LRA["value"](*p)))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d); ELO_SRC["직접 라벨(순위표 밖)"] += 1
            ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    for lg, s in lg_cands(cid, d, o, g):
        t = RANKS.get((lg, s), {})
        if k in t:
            lv = make_label(lg, s, t[k])
            if lv:
                e = lv_value(lv, d); ELO_SRC["순위표 → 라벨"] += 1
                ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, seasons[0])] = (e, lv); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())   # 순위표 밖 상대 라벨(MAN)

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
JRE = re.compile(r"Trossard|트로사르")
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and JRE.search(str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(트로사르 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("트로사르 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 트로사르 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("gnktr", "2013-01-29", "KRC 헹크", "헹크", "2012~2013"), ("lomtr", "2013-07-01", "로멀 유나이티드", "로멀", "2013"),
         ("wsttr", "2014-07-01", "KVC 베스터를로", "베스터를로", "2013~2014"), ("lomtr", "2015-07-06", "로멀 유나이티드", "로멀", "2014~2015"),
         ("ohltr", "2016-06-30", "OH 뢰번", "뢰번", "2015~2016"), ("gnktr", "2019-07-01", "KRC 헹크", "헹크", "2016~2019"),
         ("brhtr", "2023-01-20", "브라이턴 앤드 호브 앨비언", "브라이턴", "2019~2023"), ("arstr", "2026-07-15", "아스널", "아스널", "2023~2026"),
         ("bjktr", None, "베식타시", "베식타시", "2026~")]
TM_CLUB = {"1184": "gnktr", "5026": "lomtr", "968": "wsttr", "2727": "ohltr", "1237": "brhtr", "11": "arstr", "114": "bjktr"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
SJUL10 = ("gnktr", "ohltr")   # 벨기에 리그 7월 하순 개막·7월 유로파 예선(헹크 gnk 선례)
SCAL = ()
def season_of(d, club):
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    if club in SCAL: return str(y)
    if club in SJUL10: s_ = y if (m > 7 or (m == 7 and dd >= 10)) else y - 1
    else: s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("KRC 헹크(2012~2013)", "2013-01-29"), ("로멀 유나이티드(2013)", "2013-07-01"), ("KVC 베스터를로", "2014-07-01"), ("로멀 유나이티드(2014~2015)", "2015-07-06"),
          ("OH 뢰번", "2016-06-30"), ("KRC 헹크(2016~2019)", "2019-07-01"), ("브라이턴", "2023-01-20"), ("아스널", "2026-07-15"), ("베식타시", "9999")]
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
    print("FM only", FM_ONLY); print("PM only", PM_ONLY)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G, FM_CMP)
    print("SCORE_MISMATCH", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("dates changed", len(DATE_LOG))
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_trossard.py"), encoding="utf-8").read())   # NOTE_LINES
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const TRO_E={J(E)};\nconst TRO_M={J(M)};\nconst TRO_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "fotmob_playermatches_only": PM_ONLY, "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "table_label_diffs": TABLE_DIFF, "date_changes": DATE_LOG, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
