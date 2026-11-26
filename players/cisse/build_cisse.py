#!/usr/bin/env python3
"""지브릴 시세 (Djibril Cissé, Transfermarkt 3966): raw/ -> cisse.json + players/cisse/cis.js (판정 근거는 judgments.md)

  python3 players/cisse/build_cisse.py [--out <data 폴더>]   # 파일 쓰기(기본 players/cisse/cis.js; 스크래치 복사본 검증 때 --out <복사본>/src/data)
  python3 players/cisse/build_cisse.py --debug               # Elo 출처 로그만 출력
  python3 players/cisse/build_cisse.py --stat                # 요약·판정·동료 대조
  python3 players/cisse/build_cisse.py --ties                # 합산 행

사미르 나스리 build 스크립트(players/nasri, 같은 수집 형식: date_local_computed)를 바탕으로 함.
순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의 parse()/value()로 라벨에서 계산(직접 숫자를 넣지 않음).
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
보조: assist_checks.py(2014.8 이후 단일 출처 도움 웹 확인), man_elo.py(순위표 밖 상대 라벨), note_cisse.py(설명).
입력: raw/tm_games.csv(출전·분·날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
raw/fotmob_*.csv(골·도움 대조), raw/ranks.txt(순위표), elo/ 통합표 + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료, 읽기만).
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "cis.js")
OUT_JSON = os.path.join(HERE, "cisse.json")
ME = "3966"
ME_KO = "지브릴 시세"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# 이베르동 스포르트(스위스 3부 프로모션 리그, 세미프로 2017-18, Transfermarkt 29경기 24골)는 프로 리그 규칙으로 뺌
EXCL_CLUB = {"322"}
ALLG = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
EXCLUDED = [g for g in ALLG if g["club_id"] in EXCL_CLUB]
GAMES = [g for g in ALLG if g["club_id"] not in EXCL_CLUB]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["fotmob_matchId"]}
FMPM = {}   # FotMob 선수 경기 목록(playerMatches)은 시세에게 빈 목록

# ---------------------------------------------------------------- 날짜
# 모든 경기: TM API 경기 시각(UTC)을 클럽 시간대(파리·런던·마드리드·이스탄불·브뤼셀)로 바꾼 현지 날짜(raw/tm_games.csv date_local_computed).
# 리포트가 있는 경기는 모두 TM 리포트 날짜와 같음(차이 0). 쿠프 드 프랑스 5경기는 TM 킥오프 시각이 없어(00:00) 리포트·일정 날짜.
DATE_LOG = []
LD = {}
for gid, g in G.items():
    LD[gid] = g["date_local_computed"]
    if g["date_local_tm_report"] and LD[gid] != g["date_local_tm_report"]: DATE_LOG.append((gid, g["date_local_tm_report"], LD[gid], g["club"], g["opponent"]))
# 2005.12.15 클럽 월드 챔피언십 준결승 사프리사전(요코하마): Transfermarkt 시각(UTC 12.14 23:00)이 맞지 않아 일본 현지 날짜(제라드 자료와 같음)
LD["1023411"] = "2005-12-15"   # 리포트 날짜도 12.15
def ldate(g): return LD[g["gameId"]]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "GB1", "GR1", "POGR", "IT1", "RU1", "QSL"}   # POGR = 그리스 슈퍼리그 2010-11 플레이오프(리그, 선례)
CUPS = {"FAC", "CGB", "FRC", "FRL", "CIT", "GRP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or (cid == "FAC" and r.startswith("sixth round")): return "dk"   # FA컵 6라운드 = 8강(쿠프 드 프랑스 'Sixth Round'는 32강: dc)
        return "dc"
    if cid in ("FRCH", "USC"): return "df"            # 트로페 데 샹피옹·UEFA 슈퍼컵 = 국내컵 결승 비중(docs 3절)
    if cid == "KLUB": return "cwc"                    # 2005 FIFA 클럽 월드 챔피언십 준결승
    if cid == "AFCL":                                 # AFC 챔스 2013 조별·16강
        if r.startswith("group") or r.startswith("last 16"): return "acl"
        sys.exit("AFC 라운드 " + rnd)
    if cid == "CLQ": return "clq"
    if cid in ("UI", "UEQ", "ELQ"): return "elq"      # 인터토토컵(모든 라운드)·UEFA컵 예선·유로파 예선(플레이오프 포함) = 유로파 예선 비중
    if cid == "UEFA":                                 # UEFA컵(2009년 이전): 1라운드 = 예선(docs 3절), 조별 = elg, 32강(intermediate stage·3rd round)·16강 = elk
        if r.startswith("first round"): return "elq"   # 2라운드(2003-04 위트레흐트)는 유로파 토너먼트(선례)
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
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
    if cid in ("CL", "EL", "CLQ", "ELQ", "UEFA", "UEQ", "UI"): return (1, 1)   # UEFA 대회(2020-21까지): 원정 다득점·연장(인터토토도 같음)
    if cid == "GRP": return (1, 1)                   # 그리스컵 2009-10 준결승·2010-11 8강 두 경기: 원정 다득점·연장(영어 위키백과 시즌 문서 규정)
    if cid == "AFCL": return (1, 1)                  # AFC 챔스 2013 16강: 원정 다득점·연장(2022년까지, docs 3절)
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

A_CHECK = {}; ADD_A = []; PM_EXTRA = {}
def a_key(gid, minute): return f"{gid}|{minute}"
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())   # A_CHECK 채움(근거 포함)

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["cisse_assist"] == "1" and fm_min_match(f, e["minute"]): return True
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

A_STATUS = []   # 2014.8 이후 도움 판정 기록
def fm_confirmed(gid):
    return sum(1 for e in EVS.get(gid, []) if e["assist_id"] == ME and e["scorer_id"] != ME and fm_assist(gid, e))
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t.startswith("Handball"): return "상대 골(핸드볼)"
    if t == "Deflected": return "굴절"
    k = a_key(gid, e["minute"])
    if d < GAP:
        if k in A_CHECK and not A_CHECK[k][0]: return A_CHECK[k][1]
        return None
    fa, pm = fm_assist(gid, e), fm_pm_assists(gid)
    if fa:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if pm and pm > fm_confirmed(gid) and k not in A_CHECK:
        if k not in PM_EXTRA: sys.exit("FotMob 선수 경기 목록만 있는 도움에 세 번째 출처 없음 " + k)
        A_STATUS.append((d, gid, e["minute"], e["scorer"], f"TM+FotMob 선수 경기 목록(도움 {pm})+" + PM_EXTRA[k])); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "2014.8 이후 단일 출처(확인 못 함)"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], f"판정 없음 FMpm={pm}"))
    return "2014.8 이후 단일 출처(판정 없음)"

# TM 리포트가 상대 골을 빠뜨린 경기: 2007.1.6 쿠프 드 프랑스 캉브레 1-4 마르세유(연장) — TM 리포트·API 모두 마르세유 골 4개뿐.
# Maxifoot 경기 요약('Cambrai (CFA2) 1-4 (1-1) Marseille … Bailleul … coup franc lointain (80')')·리베리 자료(rib.js, v1.270 고침):
# 정규 시간 1-1 → 107분 골 전 1-1, 111분 골 전 2-1(우리 팀 기준). 분은 리베리 자료처럼 Transfermarkt(18·107·111분).
SCORE_FIX = {"2852016|107": (1, 1), "2852016|111": (2, 1)}
raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME and sd == side
        if e["assist_id"] == ME and sd != side:
            judg.append(("도움 아님(상대 골 도움 칸에 시세 핸드볼 표기)", ldate(g), opp(g), e["minute"], e["scorer"], e["assist_type"]))
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e):   # 2010.12.7 코펜하겐전 73분 시세 자책골(상대 골) — 골 아님
            if sd == side: sys.exit("자책골 편 " + gid)
            judg.append(("본인 자책골(상대 골, 골 아님)", ldate(g), opp(g), e["minute"])); continue
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        if a_key(gid, e["minute"]) in SCORE_FIX:   # TM 리포트에 상대 골이 빠진 경기(judgments 3절)
            judg.append(("골 전 스코어 고침(TM 리포트에 상대 골 빠짐)", ldate(g), opp(g), e["minute"], (gf, ga), SCORE_FIX[a_key(gid, e["minute"])]))
            gf, ga = SCORE_FIX[a_key(gid, e["minute"])]
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
        if f["cisse_assist"] == "1" and f["pen_shootout_event"] != "True":
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
MANUAL_ALIAS = {}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue   # 시세만 쓴 팀×시즌(스크래치에서 다시 만든 표)은 기존 값이 아님
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "cis.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "stade", "olympique", "fc", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "paulista", "paulo", "ca", "cs", "deportivo", "deportes", "universidad", "san", "santa", "fk", "vfl", "bv",
        "racing", "arsenal", "juniors", "plate", "river", "nacional", "independiente", "estudiantes", "union", "boca", "gimnasia", "esgrima", "lorenzo", "almagro", "hotspur", "palace", "villa", "ham", "manchester", "verona", "sheffield", "bristol", "birmingham", "nottingham", "queens", "park", "west", "aston",
        "new", "york", "los", "angeles", "toronto", "vitoria", "guimaraes", "setubal", "borussia", "werder", "bayer", "eintracht", "hertha", "olympiacos", "panathinaikos",
        "rio", "ave", "al", "sc", "qatar", "rayyan", "atletico", "mexico", "cruz", "azul", "guadalajara", "deportivo", "once", "caldas", "medellin", "bogota", "leon", "minnesota"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
SA_DOM = set()
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
        if len(p) < 5 or p[0] in ("league",) or p[0].startswith("#") or p[0].startswith("FOTMOB"): continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1])

EU_LG = {"FR1": "리그1", "ES1": "라리가", "GB1": "프리미어리그", "IT1": "세리에A", "NL1": "에레디비시"}
def make_label(lg, season, v):
    r, n, nm, sraw = v
    if lg in EU_LG:
        pre = EU_LG[lg]; n0 = _LRA["ERA"]["teams"](pre, int(season[:4]) + 1)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    if lg == "FR2": return f"리그2 {season} {r}위/{n}팀"
    if lg == "GB2": return f"챔피언십 {season} {r}위/{n}팀"
    if lg == "TR1": return f"튀르키예 1부 {season} {r}위/{n}팀 (Süper Lig)"
    if lg == "BE1": return f"벨기에 1부 {season} {r}위/{n}팀 (" + ("Jupiler League" if season < "2008" else "Belgian First Division A, 코로나로 조기 종료된 시즌 최종 순위") + ")"
    if lg == "BE2": return f"벨기에 2부 {season} {r}위/{n}팀 (First Division B, 리그 수준 추정)"
    if lg == "GB3": return f"잉글랜드 3부 {season} {r}위/{n}팀 (Football League One, 리그 수준 추정)"
    if lg == "C1": return f"스위스 1부 {season} {r}위/{n}팀 (Swiss Super League)"
    if lg == "BU1": return f"불가리아 1부 {season} {r}위/{n}팀 (A PFG)"
    if lg == "UKR1": return f"우크라이나 1부 {season} {r}위/{n}팀 (Vyshcha Liha)"
    if lg == "GR1": return f"그리스 1부 {season} {r}위/{n}팀 (Super League Greece)"
    if lg == "RU1": return f"러시아 1부 {season} {r}위/{n}팀 (Russian Premier League)"
    if lg == "RO1": return f"루마니아 1부 {season} {r}위/{n}팀 (Liga I)"
    if lg == "TS1": return f"체코 1부 {season} {r}위/{n}팀 (Czech First League)"
    if lg == "A1": return f"오스트리아 1부 {season} {r}위/{n}팀 (Austrian Bundesliga)"
    if lg == "SC1": return f"스코틀랜드 1부 {season} {r}위/{n}팀 (Scottish Premiership)"
    if lg == "SA1": return f"사우디 1부 {season} {r}위/{n}팀 (Saudi Professional League)"
    if lg == "IRN1": return f"이란 1부 {season} {r}위/{n}팀 (Iran Pro League)"
    if lg == "UAE1": return f"UAE 1부 {season} {r}위/{n}팀 (UAE Pro League)"
    if lg == "QSL": return f"카타르 {season} {r}위/{n}팀 (추정, 마레즈 자료와 같은 리그 수준)"
    if lg == "FR3": return f"프랑스 3부 {season} {r}위/{n}팀 (Championnat National, 리그 수준 추정)"
    if lg == "FR4A": return f"프랑스 4부 {season} {r}위/{n}팀 (CFA Groupe A, 리그 수준 추정)"
    if lg == "GR2": return f"그리스 2부 {season} {r}위/{n}팀 (Football League, 리그 수준 추정)"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

CAL = set()
def seasons_for(cid, d, o, g):
    return [eu(d), d[:4]]

def lg_cands(cid, d, o, g):
    s = eu(d)
    return [(lg, s) for lg in ("FR1", "GB1", "IT1", "GR1", "RU1", "QSL", "NL1", "FR2", "GB2", "FR3", "FR4A", "GR2", "C1", "A1", "SC1", "RO1", "TS1", "SA1", "IRN1", "UAE1")]

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산; val을 주면 그 값 — 주 리그 전용 팀의 같은 해 기존 값 선례)
MANV = {}
def man(o, s, lv, val=None):
    MAN[(key(o), s)] = lv
    if val is not None: MANV[(key(o), s)] = val
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
            lv = MAN[(k, s)]; e = MANV.get((k, s)) or lv_value(lv, d); ELO_SRC["직접 라벨(순위표 밖)"] += 1
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

# 알가라파 카타르 국내 컵(Transfermarkt에 없음): 카타르축구협회 경기 페이지(raw/qatar/qfa)와 페닌슐라 기사로 골 또는 출전이 확인된 경기만(주니뉴·라울·스네이더르 선례).
#   2013.2.4 QNB 스타스컵 조별 알사일리야 2-0(하프타임 1-0, 협회 득점 순서 카르발류 1-0·시세 2-0 → 후반 유일한 골, 시각 자료 없음 → 후반 가운데 68분 추정)
#   2013.3.19 QNB 스타스컵 준결승 알아라비 2-1 알가라파(페닌슐라 3.20: 시세 전반 슈팅 2개·90분 헤더 크로스바 → 출전, 골·도움 없음)
#   2013.5.8 에미르컵 8강 알가라파 2-4 레크위야(협회 득점 순서 첫 골 시세 1-0, 페닌슐라 5.9 'Djibril Cisse (1)' → 1분)
#   2013.5.5 에미르컵 알카라이티야트전(협회 페이지에 시세 이름 없음, 출전 자료 없음)은 넣지 않음. 출전 분은 모두 90분 추정, 도움 자료 없음, PK 자료 없음.
QAT_M = [["2013-02-04", "Al-Sailiya SC", "dc", 90, 1], ["2013-03-19", "Al-Arabi SC", "dsf", 90, 1], ["2013-05-08", "Lekhwiya SC", "dk", 90, 1]]
QAT_E = [("g", "Al-Sailiya SC", "dc", 68, 1, 0, 0, "2013-02-04"), ("g", "Lekhwiya SC", "dk", 1, 0, 0, 1, "2013-05-08")]
for m in QAT_M: M.append(m)
M.sort(key=lambda m: m[0])
for typ, o, comp, mi, gf, ga, ko, d in QAT_E:
    elo, lv = opp_elo(o, d, "QATCUP", {"gameId": "qfa-" + d})
    E.append([typ, o, elo, comp, mi, gf, ga, ko, 0, d, 0, 0, lv, 0])
    judg.append(("카타르 컵 골 추가(협회 경기 페이지·기사)", d, o, mi))

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
    fm = [r for r in FME[gid] if r["cisse_scorer"] == "1" and r["pen_shootout_event"] != "True"]
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
JRE = re.compile(r"Ciss[eé]|시세")
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and JRE.search(str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(시세 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("시세 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 시세 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("auxcis", "2004-07-01", "AJ 오세르", "오세르", "1999~2004"), ("livcis", "2006-07-01", "리버풀", "리버풀", "2004~2006"),
         ("omcis", "2008-08-21", "올랭피크 마르세유", "마르세유", "2006~2008"), ("suncis", "2009-07-01", "선덜랜드(임대)", "선덜랜드", "2008~2009"),
         ("paocis", "2011-07-12", "파나티나이코스", "파나티나이코스", "2009~2011"), ("lazcis", "2012-01-31", "라치오", "라치오", "2011~2012"),
         ("qprcis", "2013-01-20", "퀸스 파크 레인저스", "QPR", "2012~2013"), ("ghacis", "2013-07-04", "알가라파(임대)", "알가라파", "2013"),
         ("kubcis", "2014-01-01", "쿠반 크라스노다르", "쿠반", "2013"), ("bascis", None, "SC 바스티아", "바스티아", "2014~2015")]
TM_CLUB = {"290": "auxcis", "31": "livcis", "244": "omcis", "289": "suncis", "265": "paocis", "398": "lazcis", "1039": "qprcis",
           "6297": "ghacis", "2439": "kubcis", "595": "bascis"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
JUL1 = ("auxcis",)                       # 오세르 2000.7.1 인터토토컵 2라운드 = 2000-01 시즌
JUL10 = ("livcis", "paocis", "kubcis")   # 리버풀 2005.7.13 챔스 1차 예선·파나티나이코스 2009.7.28 챔스 3차 예선·쿠반 2013.7.20 러시아 리그 = 새 시즌
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in JUL10: s_ = y if (m > 7 or (m == 7 and int(d[8:]) >= 10)) else y - 1
    elif club in JUL1: s_ = y if m >= 7 else y - 1
    else: s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [(n, u or "9999") for k, u, n, sh, y in CLUBS]
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
    for (o, s_), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s_, e, lv)
    print("TABLE_DIFF", TABLE_DIFF)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_cisse.py"), encoding="utf-8").read())   # NOTE_LINES
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const CIS_E={J(E)};\nconst CIS_M={J(M)};\nconst CIS_NOTE={J(NOTE)};\n")
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
