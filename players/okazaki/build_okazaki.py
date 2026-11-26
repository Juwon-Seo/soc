#!/usr/bin/env python3
"""오카자키 신지 (岡崎慎司, Shinji Okazaki, Transfermarkt 79642): raw/ -> okazaki.json + players/okazaki/okz.js (판정 근거는 judgments.md)

  python3 players/okazaki/build_okazaki.py [--out <data 폴더>]   # 파일 쓰기(기본 players/okazaki/okz.js; 스크래치 복사본 검증 때 --out <복사본>/src/data)
  python3 players/okazaki/build_okazaki.py --debug               # Elo 출처 로그만 출력
  python3 players/okazaki/build_okazaki.py --stat                # 요약·판정·동료 대조

미토마 build 스크립트(같은 수집 형식)를 바탕으로 함. 순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의
parse()/value()(+ tools/league_points.py 승점·득실 모형)로 라벨에서 계산(v1.226·v1.290 규칙, 직접 숫자를 넣지 않음).
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
레스터 U21(2군) 1경기는 경기 목록에서 제외(설명에 기록). 스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "okz.js")
OUT_JSON = os.path.join(HERE, "okazaki.json")
ME = "79642"
ME_KO = "오카자키 신지"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

AMATEUR = {"39341"}   # 레스터 시티 U21(2군, 2018.9.16 첼시 U21전 1골) — 2군 경기 제외(프로젝트 선례)
ALLG = rd("tm_games.csv")   # 클럽 경기 587개(레스터 U21 1 포함)
EXCL = [g for g in ALLG if g["club_id"] in AMATEUR]
GAMES = [g for g in ALLG if g["club_id"] not in AMATEUR]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
# TM 골 목록에서 빠진 상대 자책골(골 전 스코어 계산용, 오카자키 기록 아님): 
#  1021817 2009.7.29 J리그컵 8강 2차전 우라와전 3-0 — 영어·일본어 위키백과 대회 문서(아베 유키 자책골, 오카자키 44분, 아오야마 62분; 전반 2-0) → 오카자키 골 전 1-0
#  1027169 2008.11.29 J1 33라운드 지바전 3-2 — ESPN 경기 기록(39분 시모무라 자책골), TM 리포트 중간 스코어(오카자키 76분 뒤 3-1)·전반 2-1 → 오카자키 골 전 2-1
MISSING_OG = [("1021817", "1", "home"), ("1027169", "39", "home")]
for gid_, mn_, sd_ in MISSING_OG:
    row = {k: "" for k in EVS[gid_][0]}; row.update(gameId=gid_, minute=mn_, side=sd_, scorer="(상대 자책골)", scorer_id="", own_goal="1", goal_desc="Own-goal")
    EVS[gid_].append(row); EVS[gid_].sort(key=lambda e: (int(e["minute"].split("+")[0]), int(e["minute"].split("+")[1]) if "+" in e["minute"] else 0))
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["status"] == "OK"}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 날짜
# 모든 경기: TM API 경기 시각(UTC)을 경기장 시간대로 바꾼 현지 날짜(raw/tm_games.csv date_local_tz_conv). 일본 경기 = 도쿄,
# AFC 챔피언스리그 2021 조별(타슈켄트 집중 개최) = 타슈켄트 현지 날짜(2021.6.26·7.8 대구전은 21:00 타슈켄트 = 도쿄 다음 날 01:00).
# TM 일정·리포트·FotMob 날짜와 다른 경기 0(raw/tm_date_disagreements.csv).
DATE_FIX = {}
DATE_LOG = []
LD = {}
for gid, g in G.items():
    LD[gid] = DATE_FIX.get(gid, g["date_local_tz_conv"])
    if LD[gid] != g["date_local_schedule"]: DATE_LOG.append((gid, g["date_local_schedule"], LD[gid], g["club"], g["opponent"]))
def ldate(g): return LD[g["gameId"]]
OPP_NAME = {"2479065": "Asteras Tripolis", "2480867": "Asteras Tripolis"}   # TM 스폰서 이름(Asteras Aktor) → 다른 선수 자료 표기
def opp(g): return OPP_NAME.get(g["gameId"]) or re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
# J1·분데스리가·PL·라리가·세군다·벨기에 1부 + 벨기에 유로파 플레이오프(POBE, 오시멘·트로사르 선례) = 리그
LEAGUE = {"JAP1", "L1", "GB1", "ES1", "ES2", "BE1", "POBE"}
# 일왕배·J리그컵(나비스코컵)·DFB 포칼·FA컵·리그컵·코파 델 레이·벨기에컵 = 국내컵(가가와·박지성·미토마 선례)
CUPS = {"JEMP", "JAPC", "DFB", "FAC", "CGB", "CDR", "CCB"}
SUPER = {"GBCS"}                               # 커뮤니티 실드 = 국내컵 결승 비중

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "df"
    if cid in CUPS:   # 16강까지 국내컵, 8강(리그컵 5라운드·FA컵 6라운드) 이후 단계별(docs 3절)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or (cid == "FAC" and r.startswith("sixth")) or (cid == "CGB" and r.startswith("fifth")): return "dk"
        return "dc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        sys.exit("CL 단계 " + rnd)
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith(("second round", "intermediate stage", "last 16")): return "elk"   # 2010-11 32강(Second Round)·2012-13 32강(intermediate stage)·16강
        sys.exit("EL 단계 " + rnd)
    if cid == "ELQ": return "elq"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g):
    return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r): return 0   # J리그컵 조별·AFC 조별·유로파 조별 = 리그식
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid == "JAPC": return (1, 1)   # J리그컵 8강·준결승(2005·2008·2009·2010): 원정 다득점·연장(미토마·이니에스타·포를란 선례)
    if cid in ("EL", "ELQ", "CL") and d < "2021-07-01": return (1, 1)   # UEFA 2021-07 전: 원정 다득점·연장
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
# 2014.8 이후 TM 도움 중 FotMob(경기 이벤트·선수 경기 목록)이 같이 적지 않은 것: TM 외 독립 출처 2곳으로 확인한 것만 넣음(근거는 judgments.md)
A_CHECK = {
 "2916170|78": (True, "ESPN 경기 기록('Assisted by Shinji Okazaki')·Eurosport 경기 기사(오카자키가 오른쪽에서 빠져나와 슬리마니에게 내줌, 슬리마니 25야드 슈팅)·다른 경기 기사(오카자키의 내준 공 'lay-off')"),
 "2460728|88": (False, "Sky Sports는 오카자키 크로스 → 벨 골, Sports Mole은 오카자키 크로스가 골라인에서 걷어내진 뒤 벨이 헤더 — 출처끼리 다르고 FotMob·ESPN도 도움자 없음"),
 "3851126|45": (False, "Sporza 경기 기사: 오카자키가 프리킥을 헤더로 넣은 공을 코나테가 골라인 앞에서 한 번 더 밀어 넣음 — 오카자키 슈팅을 코나테가 마무리한 것이라 도움 아님(공식 기록·TM 공식 도움·FotMob 선수 기록 0), 골도 공식 기록상 코나테"),
}
ADD_A = []

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
MANUAL_ALIAS = {"hokkaido consadole sapporo": "consadole sapporo"}   # 순위표 표기에 맞춤
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "okz.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
# 이번 회차에 함께 판정한 선수(판정 끝남, 읽기만): 같은 경기면 같은 Elo/lv
for pth in sorted(glob.glob(os.path.join(os.path.dirname(HERE), "*", "*.js"))):
    slug, fn = pth.split(os.sep)[-2:]
    if slug not in ("minamino", "honda", "cahill", "szoboszlai") or "src/data/" + fn in TRACKED: continue
    try: P, oe, om = load_js(pth)
    except Exception: continue
    OTHERS["players/" + slug + "/" + fn] = (oe, om)
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
SA_DOM = {"JAP1", "JAPC", "JEMP", "ARG1", "ARGC", "CLI", "CS", "BRA1", "BCP1", "BCPF", "MEX1", "MEXA", "POME", "USMX", "MLS1", "MLSP", "COL1", "COPO", "QSL", "QEC1", "KLUB"}
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
sys.path.insert(0, os.path.join(ROOT, "tools"))
import league_points as PTS
def lv_value(lv, d, o=None):
    """tools/league_rank_apply.py 와 같은 계산(5대 리그·다른 리그 승점·득실 모형 포함). o = 데이터의 상대 이름."""
    m_ = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv)
    if m_:
        cal = m_.group(4) is None; y = int(m_.group(3)) + (0 if cal else 1)
        return int(round(_LRA["base"](_LRA["KO"][m_.group(1)], int(m_.group(2)), y, cal)))
    p = _LRA["parse"](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA["value"](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    if o is not None:
        if p[1] == 1 and p[0] in _LRA["BIG"]:
            vp = PTS.value(lv, o, _LRA["base"](p[0], 1, p[2], p[3]), _LRA["sd"](p[0], 1), _LRA["cv"])
        else:
            vp = PTS.value_other(lv, o, p[0], p[1], _LRA["base"](p[0], p[1], p[2], p[3]), _LRA["sd"](p[0], p[1]), _LRA["cv"])
        if vp is not None: v = vp
    return v
def pts_head(lv):
    """라벨 앞부분이 다른 리그 승점 표(elo/league_points_other.json)에 있으면 그 키."""
    h = lv.split(" (")[0]; mm = re.match(r"^(.*?) \d+위", h)
    return mm.group(1) if mm and mm.group(1) in PTS.O["seasons"] else None

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] in ("league",) or p[0].startswith("#"): continue
        se = p[1].split(" ")[0]
        lg = "J1" if p[0] == "JAP1" else p[0]
        RANKS[(lg, se)][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1])
# J1 2009: TM 표를 받지 못해 영어 위키백과 '2009 J.League Division 1' 순위표(raw/ranks_wiki.txt). 2005~2008·2010은 TM 표와 위키 표가 같은지 확인.
WIKI_J1 = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks_wiki.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 6 or not re.match(r"en_\d{4}_J1\.html", p[0]): continue
        yy = p[0][3:7]; nm = re.sub(r"\s*\([A-Z, ]+\)$", "", p[5]).strip()
        WIKI_J1[yy][key(nm)] = (int(p[3]), int(p[4]), nm, yy + " wiki")
J1_CHECK = []
for yy, t in WIKI_J1.items():
    if (("J1", yy)) in RANKS:
        tm = {v[0]: k for k, v in RANKS[("J1", yy)].items()}; wk = {v[0]: k for k, v in t.items()}
        J1_CHECK.append((yy, sum(1 for r in tm if wk.get(r) == tm[r]), len(tm)))
    for k_, v in t.items(): RANKS[("J1", yy)].setdefault(k_, v)
# 벨기에 1부 최종 순위(FotMob 표): 2022-23 챔피언 플레이오프 1~4, 유럽 플레이오프 5~8, 정규 시즌 9~18
#                                2023-24 챔피언 플레이오프 1~6, 유럽 플레이오프 7~12, 강등 플레이오프 13~16(코르트레이크 14위는 2부 3위와 승강전에서 잔류)
FMBE = collections.defaultdict(list)
with open(os.path.join(RAW, "ranks_fotmob.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or not p[0].startswith("40 "): continue
        FMBE[(p[0].split(" / ")[-1], p[1][:5] + p[1][7:9])].append((int(p[2]), p[4]))
FM2TM = {"union st gilloise": "union saint gilloise", "club brugge": "club brugge kv", "anderlecht": "rsc anderlecht", "royal antwerp": "royal antwerp fc",
         "gent": "kaa gent", "genk": "krc genk", "sporting charleroi": "royal charleroi sc", "st truiden": "sint truidense vv", "oh leuven": "oud heverlee leuven",
         "oostende": "kv oostende", "kortrijk": "kv kortrijk", "eupen": "kas eupen", "rfc seraing": "rfc seraing", "rwdm brussels": "rwd molenbeek",
         "standard liege": "standard liege", "westerlo": "kvc westerlo", "cercle brugge": "cercle brugge", "zulte waregem": "zulte waregem", "kv mechelen": "kv mechelen"}
for se in ("2022-23", "2023-24"):
    reg = RANKS[("BE1", se)]
    regk = {norm(v[2]): k for k, v in reg.items()}
    def tmk(nm):
        t = FM2TM.get(norm(nm), norm(nm))
        hit = [k for nn, k in regk.items() if nn.startswith(t) or (" " + t) in (" " + nn)]
        if not hit: hit = [k for nn, k in regk.items() if t.split()[-1] in nn.split()]
        if len(hit) != 1: sys.exit(f"벨기에 표 이름 연결 실패 {se} {nm} {hit}")
        return hit[0]
    order_reg = [tmk(nm) for r, nm in sorted(FMBE[("Belgian Pro League", se)])]
    po1 = [tmk(nm) for r, nm in sorted(FMBE[("Belgian Pro League Playoff Championship Group", se)])]
    po2 = [tmk(nm) for r, nm in sorted(FMBE[("Belgian Pro League Playoff ECL Group", se)])]
    po3 = [tmk(nm) for r, nm in sorted(FMBE[("Belgian Pro League Playoff Relegation Group", se)])]
    n1, n2 = len(po1), len(po2)
    if set(po1) != set(order_reg[:n1]) or set(po2) != set(order_reg[n1:n1 + n2]) or set(order_reg) != set(reg): sys.exit("벨기에 플레이오프 팀 다름 " + se)
    if po3 and set(po3) != set(order_reg[n1 + n2:]): sys.exit("벨기에 강등 플레이오프 팀 다름 " + se)
    fin = po1 + po2 + (po3 or order_reg[n1 + n2:])
    for i, k in enumerate(fin): reg[k] = (i + 1, len(fin), reg[k][2], se + " 플레이오프 뒤")

EU_LG = {"FR1": "리그1", "ES1": "라리가", "L1": "분데스리가", "GB1": "프리미어리그", "PO1": "포르투갈 1부", "IT1": "세리에A", "NL1": "에레디비시"}
def make_label(lg, season, v):
    r, n, nm, sraw = v
    if lg == "J1":
        if season == "2008": return f"일본 1부 2008 {r}위/{n}팀 (J.League Division 1)"   # 기존 자료(감바 오사카 2008)와 같은 라벨 형식 — 승점 표 키 '일본 1부 2008'
        return f"J1리그 {season} {r}위/{n}팀"
    if lg == "BE1": return f"벨기에 1부 {season} {r}위/{n}팀 (Belgian Pro League, 플레이오프 뒤 최종 순위)"
    if lg == "BE2": return f"벨기에 2부 {season} {r}위/{n}팀 (Challenger Pro League, 리그 수준 추정)"
    if lg == "ES2": return f"세군다 {season} {r}위/{n}팀"
    if lg == "L2": return f"2. 분데스리가 {season} {r}위/{n}팀"
    if lg == "L3": return f"독일 3부 {season} {r}위/{n}팀 (3. Liga, 리그 수준 추정)"
    if lg == "GB2": return f"챔피언십 {season} {r}위/{n}팀"
    if lg == "GB3": return f"잉글랜드 3부 {season} {r}위/{n}팀 (EFL League One, 리그 수준 추정)"
    if lg == "GB4": return f"잉글랜드 4부 {season} {r}위/{n}팀 (EFL League Two, 리그 수준 추정)"
    if lg == "RU1": return f"러시아 {season} {r}위/{n}팀"
    if lg in EU_LG:
        pre = EU_LG[lg]; n0 = _LRA["ERA"]["teams"](pre, int(season[:4]) + 1)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    return None

# 시즌: 시미즈 경기는 달력 연도(J리그), 1월 1일 일왕배 결승(앞 해 대회)은 끝난 앞 해 시즌 순위. 그 밖은 8월 1일 기준
# (7월 유럽 예선은 끝난 시즌 순위: 2014.7.31 아스테라스).
def seasons_for(cid, d, o, g):
    y, m = int(d[:4]), int(d[5:7])
    if g["club_id"] == "1062": return [str(y - 1 if m == 1 else y)]
    s_ = y if m >= 8 else y - 1
    return [f"{s_}-{str(s_ + 1)[2:]}"]
DOM = {"1062": ["J1"], "79": ["L1", "L2", "L3"], "39": ["L1", "L2", "L3"], "1003": ["GB1", "GB2", "GB3", "GB4"], "5358": ["ES2", "ES1"], "7077": ["ES2", "ES1"], "475": ["BE1", "BE2"]}
def lg_cands(cid, d, o, g):
    ss = seasons_for(cid, d, o, g)
    doms = DOM[g["club_id"]] if cid not in ("EL", "ELQ", "CL") else list(EU_LG) + ["RU1"]
    return [(lg, s_) for lg in doms for s_ in ss]

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산)
def man(o, s, lv): MAN[(key(o), s)] = lv
# 2012.8.18 DFB 포칼 1라운드 팔켄제핀켄크루크: 브란덴부르크리가(독일 6부) 2012-13 최종 3위/17팀 — 독일어 위키백과 'Fußball-Brandenburgliga 2012/13' 순위표·구단 문서 시즌 표
man("SV Falkensee/Finkenkrug", "2012-13", "독일 6부 2012-13 3위/17팀 (Brandenburg-Liga, 리그 수준 추정)")
# 2014.7.31 유로파 예선 3라운드 아스테라스 트리폴리스: 7월 예선 → 끝난 2013-14 시즌. 그리스 슈퍼리그 2013-14 최종 5위/18팀(영어 위키백과 시즌 문서 순위표; 플레이오프는 유럽 대회 배정용이라 순위표 그대로)
man("Asteras Tripolis", "2013-14", "그리스 1부 2013-14 5위/18팀 (Super League Greece)")
FORCE = {}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def opp_elo(o, d, cid, g):
    e, lv = opp_elo0(o, d, cid, g)
    if lv != "?" and (_LRA["parse"](lv, d) or re.search(" 순위 없음", lv)):
        v = lv_value(lv, d, o)
        if v != e: RECALC.append((d, o, e, v, lv))
        e = v
    return e, lv
RECALC = []
def opp_elo0(o, d, cid, g):
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
    for x in RECALC: print("RECALC", x)
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
JRE = re.compile(r"Okazaki|오카자키")
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and JRE.search(str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(오카자키 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("오카자키 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 오카자키 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("shiok", "2011-01-30", "시미즈 S펄스", "시미즈", "2005~2010"), ("vfbok", "2013-07-01", "VfB 슈투트가르트", "슈투트가르트", "2011~2013"),
         ("m05ok", "2015-07-01", "1. FSV 마인츠 05", "마인츠", "2013~2015"), ("leiok", "2019-07-30", "레스터 시티", "레스터", "2015~2019"),
         ("hueok", "2021-08-31", "SD 우에스카", "우에스카", "2019~2021"), ("carok", "2022-08-19", "FC 카르타헤나", "카르타헤나", "2021~2022"),
         ("stvok", None, "신트트라위던 VV", "신트트라위던", "2022~2024")]
TM_CLUB = {"1062": "shiok", "79": "vfbok", "39": "m05ok", "1003": "leiok", "5358": "hueok", "7077": "carok", "475": "stvok"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
SCAL = ("shiok",)   # J리그 달력 연도(1월 1일 일왕배 결승은 앞 해 대회 → 앞 시즌)
SJUL10 = ("m05ok", "stvok")   # 7월 10일 기준(마인츠 2014.7.31 유로파 예선, 신트트라위던 2023.7.30 리그 개막이 새 시즌)
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in SCAL: return str(y - 1 if m == 1 else y)
    if club in SJUL10:
        s_ = y if d[5:] >= "07-10" else y - 1
        return f"{s_}-{str(s_ + 1)[2:]}"
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("시미즈 S펄스", "2011-01-30"), ("VfB 슈투트가르트", "2013-07-01"), ("마인츠 05", "2015-07-01"), ("레스터 시티", "2019-07-30"),
          ("SD 우에스카", "2021-08-31"), ("FC 카르타헤나", "2022-08-19"), ("신트트라위던", "9999")]
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
EX_G = sum(int(g["goals"]) for g in EXCL); EX_A = sum(int(g["assists"]) for g in EXCL); EX_MIN = sum(int(g["playedMinutes"]) for g in EXCL)
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A, "excl", len(EXCL), EX_G, EX_A, EX_MIN)
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
exec(open(os.path.join(HERE, "note_okazaki.py"), encoding="utf-8").read())   # NOTE_LINES
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const OKZ_E={J(E)};\nconst OKZ_M={J(M)};\nconst OKZ_NOTE={J(NOTE)};\n")
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
