#!/usr/bin/env python3
"""혼다 게이스케 (Keisuke Honda, Transfermarkt 66521): raw/ -> honda.json + players/honda/hnd.js (판정 근거는 judgments.md)

  python3 players/honda/build_honda.py [--out <data 폴더>]   # 파일 쓰기(기본 players/honda/hnd.js; 스크래치 복사본 검증 때 --out <복사본>/src/data)
  python3 players/honda/build_honda.py --debug               # Elo 출처 로그만 출력
  python3 players/honda/build_honda.py --stat                # 요약·판정·동료 대조

아즈문 build 스크립트(같은 수집 형식)를 바탕으로 함. 순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의
parse()/value()로 라벨에서 계산(v1.226 규칙). 같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이
elo/opponent_elo_by_team_season.csv에 있으면 그 값(스크래치 복사본에서 src/data로 새로 만든 표: SOC_ROOT=<복사본>).
TM 목록에 'not in squad'로 적힌 2024.10.20 부탄 리그 팀푸 시티전(파로 FC)은 경기 자료 3곳(FIFA+ 하이라이트 설명,
부탄 축구협회 기사, sporteden 경기 기록)과 일본어 위키백과 시즌 합계로 출전·2골을 확인해 추가(출전 90분 추정).
부탄 리그는 tools/league_rank_apply.py 나라 목록에 없어 같은 식(Opta 리그 수준 → Elo + 흩어짐 60 × 순위 곡선)으로 직접 계산.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "hnd.js")
OUT_JSON = os.path.join(HERE, "honda.json")
ME = "66521"
ME_KO = "혼다 게이스케"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]   # 성인 클럽 공식 경기 510(유소년·2군 경기 없음)
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# ---- TM이 'not in squad'로 적은 경기 추가: 2024.10.20 부탄 프리미어리그 최종 라운드 팀푸 시티 2-2 파로 FC(창리미탕 경기장, TM 4600538)
# 골 순서(FIFA+ 하이라이트 설명): 팀푸 시티 선제골 → 혼다 동점골(파로 데뷔골) → 팀푸 시티 막판 PK → 혼다 추가시간 동점골.
# 혼다 골 시각 34분·90+2분(sporteden 경기 기록), 전반 1-1(planetsport). 팀푸 시티 골 시각은 자료 없음(순서만 씀).
XG = "4600538"
GAMES.append({"gameId": XG, "date_local_tz_conv": "2024-10-20", "date_local_schedule": "2024-10-20", "competitionId": "BH1L", "round": "4",
              "club_id": "71982", "club": "Paro FC", "opponent": "Thimphu City FC", "opponent_id": "45989", "gameState": "regularly_terminated",
              "playedMinutes": "90", "goals": "2", "assists": "0", "penGoals": "0", "level": "senior", "season_tm": "2024"})
MI[XG] = {"gameId": XG, "round_report": "4", "home": "Thimphu City FC", "home_id": "45989", "away": "Paro FC", "away_id": "71982", "final": "2:2",
          "other_leg_id": "", "other_leg_score": ""}
def _ev(mi, side, scorer, sid, desc="", pen="0"):
    return {"gameId": XG, "minute": mi, "side": side, "scorer": scorer, "scorer_id": sid, "goal_desc": desc, "assist_player": "", "assist_id": "",
            "assist_type": "", "penalty": pen, "own_goal": "0"}
EVS[XG] = [_ev("20", "home", "(Thimphu City, minute unknown)", "x1"), _ev("34", "away", "Keisuke Honda", ME),
           _ev("85", "home", "(Thimphu City penalty, minute unknown)", "x2", "Penalty", "1"), _ev("90+2", "away", "Keisuke Honda", ME)]
EST_MIN = {XG}   # 출전 분 90분 추정
G = {g["gameId"]: g for g in GAMES}
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["status"] == "OK"}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 날짜
# 모든 경기: TM API 경기 시각(UTC)을 경기장 시간대로 바꾼 현지 날짜(raw/tm_games.csv date_local_tz_conv).
# 북중미·남미 저녁 경기(파추카·보타포구)는 TM 일정(중부 유럽 시간)보다 하루 앞(raw/tm_date_disagreements.csv).
DATE_FIX = {}
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
LEAGUE = {"JAP1", "NL1", "NL2", "RU1", "IT1", "MEXA", "MEX1", "AUS1", "BRA1", "AZ1", "LI1", "BH1L", "SIN1", "PON2"}
# PON2: 2008 에레디비시 승강 플레이오프 2라운드(ADO 덴하흐, 두 경기 + 재경기) = 리그 비중(판니스텔로이·바스토스 선례). 골·도움 없음
CUPS = {"JAPC", "JEMP", "NLP", "RUP", "CIT", "MXCA", "BRC", "BRCR"}
# J리그컵·일왕배·KNVB컵·러시아컵·코파 이탈리아·코파 MX·코파 두 브라질 = 국내컵(미토마·박지성·지냐크·아드리아누 선례),
# 캄페오나투 카리오카(주 선수권) = 국내컵 하위 라운드 비중(아드리아누·네이마르 선례; 준결승도 같은 낮은 비중)
SUPER = {"RUSS"}   # 러시아 슈퍼컵 = 국내컵 결승 비중

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "df"
    if cid == "BRCR": return "dc"
    if cid in CUPS:   # 16강까지 국내컵(러시아컵 6라운드 = 32강), 8강 dk, 준결승 dsf, 결승 df
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        sys.exit("CL 단계 " + rnd)
    if cid == "ELQ": return "elq"   # 2010·2012 유로파 플레이오프 라운드
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"   # 16강
    if cid == "KLUB": return "cwc"
    if cid == "AUSF": return "mlp"   # A리그 파이널 시리즈 = MLS 플레이오프 비중(델 피에로·아두리스 선례), 엘리미네이션 파이널·준결승 모두 단판
    if cid == "AFCL": return "acl"   # AFC 챔스 2019 조별
    if cid == "ACHQ": return "ac2"   # AFC 챌린지 리그 예선(AFC 3부 대륙 대회, 계산기에 코드 없음 → 가장 가까운 AFC 챔스 투 비중, 골·도움 없음)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g):
    return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r): return 0   # 챔스·유로파·ACL·J리그컵·카리오카·코파 MX 조별 = 리그식
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "EL", "ELQ"): return (int(d < "2021-07-01"), 1)   # UEFA: 2020-21까지 원정 다득점
    if cid == "CIT": return (1, 1)    # 코파 이탈리아 준결승 2015-16: 원정 다득점·연장(2021-22까지)
    if cid == "BRC": return (0, 0)    # 코파 두 브라질: 원정 다득점·연장 없음(골·도움 없음)
    if cid == "PON2": return (0, 0)   # 승강 플레이오프(골·도움 없음, M 행만)
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
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])] + ([1] if g["gameId"] in EST_MIN else []))

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

def a_key(gid, minute): return f"{gid}|{minute}"
# 2014.8 이후 TM 도움 중 FotMob 경기 이벤트가 혼다를 도움으로 적지 않은 것: TM 외 독립 출처 2곳으로 판정(근거는 judgments.md)
FT = "FussballTransfers 경기 기록(Webedia, footmercato.net과 같은 자료)"
A_CHECK = {
 "2611218|28": (True, "FourFourTwo 경기 기사('혼다의 패스')·Forza Italian Football 경기 평('혼다의 스루 패스')"),
 "2642627|90+3": (True, "FourFourTwo 경기 기사(94분 바카, 혼다가 만들어 줌)·Sportsmole 경기 기사('혼다가 박스 안의 바카를 찾아 줌')"),
 "2647470|14": (True, FT + "(도움 혼다)·Eurosport 기사(혼다의 스루 패스)·AP 기사(Fox Sports 게재, 혼다의 패스)"),
 "2604230|44": (False, "AP·Corriere dello Sport 등 기사: 혼다 크로스가 쿨리발리 머리에 맞고 굴절돼 보나벤투라에게 감(굴절). FotMob·ESPN·" + FT + " 모두 도움 없음"),
 "2656852|20": (True, FT + "(도움 혼다)·Sportsmole·FourFourTwo 경기 기사(혼다가 띄워 준 공을 메네즈가 가슴으로 받아 마무리)"),
 "2969715|68": (False, "ESPN 경기 기록에 혼다 도움 없음, 다른 경기 기사에서 확인 못 함"),
 "2986784|47": (True, "ESPN 경기 기록(도움 혼다)·" + FT + "(도움 혼다)·Quadratín 기사(혼다 코너킥)"),
 "2986793|10": (True, "ESPN 경기 기록·" + FT + "(둘 다 도움 혼다)"),
 "2986793|40": (True, "ESPN 경기 기록·" + FT + "(둘 다 도움 혼다)"),
 "3007803|34": (True, "ESPN 경기 기록·" + FT + "(둘 다 도움 혼다)"),
 "3012298|53": (True, "ESPN 경기 기록·" + FT + "(둘 다 도움 혼다)"),
 "3016576|36": (True, "ESPN 경기 기록·" + FT + "(둘 다 도움 혼다)"),
 "3028027|30": (True, "ESPN 경기 기록·" + FT + "(둘 다 도움 혼다)"),
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

A_STATUS = []
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
    if fa and k not in A_CHECK:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if pm and pm > fm_confirmed(gid) and k not in A_CHECK:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], f"TM+FotMob 선수 경기 목록(도움 {pm})")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else ("굴절" if "굴절" in why else "2014.8 이후 단일 출처(확인 못 함)")
    A_STATUS.append((d, gid, e["minute"], e["scorer"], f"판정 없음 FMpm={pm}"))
    return "2014.8 이후 단일 출처(판정 없음)"

MIN_FIX = {}
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "hnd.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
# 이번 회차에 함께 판정하는 선수(읽기만): 같은 경기면 같은 Elo/lv
for pth in sorted(glob.glob(os.path.join(os.path.dirname(HERE), "*", "*.js"))):
    slug, fn = pth.split(os.sep)[-2:]
    if slug not in ("okazaki", "minamino", "cahill", "szoboszlai") or "src/data/" + fn in TRACKED: continue
    try: P, oe, om = load_js(pth)
    except Exception: continue
    OTHERS["players/" + slug + "/" + fn] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "moskau", "paulista", "paulo", "ca", "cs", "deportivo", "deportes", "universidad", "san", "santa", "fk", "vfl", "bv",
        "racing", "arsenal", "juniors", "plate", "river", "nacional", "independiente", "estudiantes", "union", "boca", "gimnasia", "esgrima", "lorenzo", "almagro", "hotspur", "palace", "villa", "ham", "manchester", "verona", "sheffield", "bristol", "birmingham", "nottingham", "queens", "park", "west", "aston",
        "new", "york", "los", "angeles", "toronto", "vitoria", "guimaraes", "setubal", "borussia", "werder", "bayer", "eintracht", "hertha", "olympiacos", "panathinaikos",
        "rio", "ave", "al", "qatar", "rayyan", "mexico", "cruz", "azul", "guadalajara", "once", "caldas", "medellin", "bogota", "leon", "minnesota",
        "melbourne", "sydney", "victory", "spartak", "dinamo", "dynamo", "lokomotiv", "zenit", "krylya", "sovetov", "eindhoven", "rotterdam", "osaka", "tokyo", "fortuna", "sittard", "excelsior", "omniworld", "emmen"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
SA_DOM = {"BRA1", "BRC", "BRCR", "MEX1", "MEXA", "MXCA", "KLUB", "AUS1", "AUSF", "JAP1", "JAPC", "JEMP", "AFCL", "RU1", "RUP", "RUSS", "NL1", "NL2", "NLP", "IT1", "CIT"}
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
# 라벨 나라 이름이 도구 목록(KO)에 없는 리그: 도구의 value()를 영어 나라 키로 직접 부름(Opta 1부 수준 → Elo, 흩어짐 60)
EXTRA_KO = {"부탄": "Bhutan"}
sys.path.insert(0, os.path.join(ROOT, "tools"))
import league_points as PTS   # v1.288·v1.290 승점·득실 모형(league_rank_apply --apply와 같은 계산)
MAPNEED = []   # 승점 표가 있는 리그·시즌인데 표 map에 이 자료의 팀 이름이 없는 것(오케스트레이터가 map 추가)
def lv_value(lv, d, o=None):
    m_ = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? (\d+)위/(\d+)팀", lv)
    if m_ and m_.group(1) in EXTRA_KO:
        cal = m_.group(4) is None; y = int(m_.group(3)) + (0 if cal else 1)
        v = _LRA["value"](EXTRA_KO[m_.group(1)], int(m_.group(2)), y, cal, int(m_.group(5)), int(m_.group(6)))
        if v is None: sys.exit("라벨 값 없음 " + lv)
        return v
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
        if len(p) < 5 or p[0] in ("league",) or p[0].startswith("#"): continue
        se = p[1].split(" ")[0]
        RANKS[(p[0], se)][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1])

EU_LG = {"FR1": "리그1", "ES1": "라리가", "L1": "분데스리가", "GB1": "프리미어리그", "PO1": "포르투갈 1부", "IT1": "세리에A", "NL1": "에레디비시"}
OTH = {  # TM 리그 코드 → (라벨 머리, 괄호 안 리그 이름 또는 None)
 "JAP1": ("J1리그", "J.League Division 1"), "RU1": ("러시아 1부", "Russian Premier League"),
 "RU2": ("러시아 2부", "Russian Football National League, 리그 수준 추정"),
 "IT2": ("세리에B", None), "IT3A": ("이탈리아 3부", "Lega Pro Girone A, 리그 수준 추정"),
 "AUS1": ("호주 A리그", None), "BRA1": ("브라질 세리에 A", None),
 "AZ1": ("아제르바이잔 1부", "Azerbaijan Premier League"), "LI1": ("리투아니아 1부", "A Lyga"),
 "SE1": ("스웨덴 1부", "Allsvenskan"), "TS1": ("체코 1부", "Czech First League"),
}
def make_label(lg, season, v):
    r, n, nm, sraw = v
    if lg in EU_LG:
        pre = EU_LG[lg]; n0 = _LRA["ERA"]["teams"](pre, int(season[:4]) + 1)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    if lg == "NL2":
        return f"에이르스터 디비시(네덜란드 2부) {season} {r}위/{n}팀 (Eerste Divisie)"
    if lg == "MEXA": return f"리가MX 아페르투라 {season[:4]} {r}위/{n}팀"
    if lg == "MEX1": return f"리가MX 클라우수라 {int(season[:4]) + 1} {r}위/{n}팀"
    if lg in OTH:
        head, desc = OTH[lg]
        if lg == "RU1" and season == "2011-12": desc += ", 플레이오프·스플릿 뒤 최종 순위"
        return f"{head} {season} {r}위/{n}팀" + (f" ({desc})" if desc else "")
    return None

def eu(d, cut="08-01"):
    y = int(d[:4]); s_ = y if d[5:] >= cut else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
def ru_season(d):   # 러시아 리그: 2010 달력 연도, 2011.3~2012.5 전환 시즌 2011-12, 이후 7월 개막 가을~봄
    if d < "2011-03-01": return "2010"
    if d < "2012-07-01": return "2011-12"
    return eu(d, "07-01")
def mx_stage(d): return f"{d[:4]}/Apertura" if d[5:] >= "07-01" else f"{d[:4]}/Clausura"
SEASON_OVR = {}
def seasons_for(cid, d, o, g):
    if g["gameId"] in SEASON_OVR: return SEASON_OVR[g["gameId"]]
    if cid in ("CL", "EL", "ELQ"): return [eu(d), d[:4]]
    if cid in ("JAP1", "JAPC", "JEMP", "AFCL", "BRA1", "BRCR", "BRC", "LI1", "BH1L", "ACHQ"): return [d[:4]]
    if cid in ("RU1", "RUP", "RUSS"): return [ru_season(d)]
    if cid in ("MEXA", "MEX1"): return [mx_stage(d)]
    if cid == "MXCA": return [mx_stage(d)]
    return [eu(d)]
def lg_cands(cid, d, o, g):
    ss = seasons_for(cid, d, o, g)
    if cid in ("CL", "EL", "ELQ"): doms = ["ES1", "GB1", "IT1", "L1", "TS1", "PO1", "C1", "SE1", "ZYP1"]
    elif cid in ("RU1", "RUP", "RUSS"): doms = ["RU1", "RU2"]
    elif cid in ("NL1", "NL2", "NLP"): doms = ["NL1", "NL2"]
    elif cid in ("IT1", "CIT"): doms = ["IT1", "IT2", "IT3A"]
    elif cid in ("JAP1", "JAPC", "JEMP", "AFCL"): doms = ["JAP1"]
    elif cid in ("MEXA", "MEX1", "MXCA"):
        dd = "MEXA" if d[5:] >= "07-01" else "MEX1"
        return [(dd, eu(d))]
    elif cid in ("AUS1", "AUSF"): doms = ["AUS1"]
    elif cid in ("BRA1", "BRC", "BRCR"): doms = ["BRA1", "BRA2"]
    elif cid == "AZ1": doms = ["AZ1"]
    elif cid == "LI1": doms = ["LI1"]
    else: doms = []
    out = []
    for lg in doms:
        for s_ in ss:
            out.append((lg, s_))
            if re.match(r"^\d{4}$", s_) is None and lg in ("SE1",): out.append((lg, d[:4]))
    if cid in ("CL", "EL", "ELQ"): out += [("SE1", d[:4])]
    return out

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산)
def man(o, s, lv): MAN[(key(o), s)] = lv
# 부탄 프리미어리그 2024 최종 3위/10팀(영어 위키백과 시즌 문서; TM 순위표는 2위로 적었으나 FIFA+ 하이라이트 설명이 이 경기 무승부로 팀푸 시티가 준우승을 놓쳤다고 적음)
man("Thimphu City FC", "2024", "부탄 1부 2024 3위/10팀 (Bhutan Premier League, 리그 수준 추정)")
# 캄페오나투 카리오카 2020 방구: 같은 해 브라질 세리에 D(4부) 64팀 중 조별 탈락(A7조 6위), 조별 탈락 팀 승점·승수·골득실 순 전체 42위(영어 위키백과 2020 Série D 조별 표로 계산)
man("Bangu Atlético Clube (RJ)", "2020", "브라질 4부 2020 42위/64팀 (Campeonato Brasileiro Série D, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)")
# 코파 MX 2017 아페르투라 16강 사카테펙(2부 아센소 MX): 기존 자료(같은 팀·시즌 2017-18 연간 합산 순위) 값 그대로
SEASON_OVR["2969722"] = ["2017-18"]
# 러시아컵 2012-13 16강 FC 튜멘: 3부(PFL 우랄-볼가 지역) 2012-13 최종 2위/15팀(futbol24 순위표, Sportbox 시즌 기록: 가조비크 69점·튜멘 66점; 아카데미야 톨리야티 시즌 중 기권 포함 15팀)
man("FC Tyumen", "2012-13", "러시아 3부 2012-13 2위/15팀 (Russian Professional Football League Ural-Povolzhye, 리그 수준 추정)")
# 러시아 1부 2011-12: TM 순위표는 크라스노다르 8위·쿠반 9위로 적었으나 공식 최종 순위(영어 위키백과 챔피언십 그룹·강등 그룹 표)는 쿠반 8위(챔피언십 그룹), 크라스노다르 9위(강등 그룹 1위)
man("FC Krasnodar", "2011-12", "러시아 1부 2011-12 9위/16팀 (Russian Premier League, 플레이오프·스플릿 뒤 최종 순위)")
# 에이르스터 디비시 2008-09 감점 시즌: 에인트호번·페인담 승점 3점 감점을 되돌린 경기장 성적 순위는 포르투나 42·에인트호번 41·로센달 40·텔스타 39 → RBC 로센달 17위(공식 16위)
man("RBC Roosendaal", "2008-09", "에이르스터 디비시(네덜란드 2부) 2008-09 17위/20팀 (감점 전 순위; Eerste Divisie)")
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
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d, o); ELO_SRC["직접 라벨(순위표 밖)"] += 1
            ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
            p = _LRA["parse"](lv, d)
            if p and _LRA["value"](*p) not in (None, e): TABLE_DIFF.append((o, s, e, lv, _LRA["value"](*p)))
            return e, lv
    for lg, s in lg_cands(cid, d, o, g):
        t = RANKS.get((lg, s), {})
        if k in t:
            lv = make_label(lg, s, t[k])
            if lv:
                e = lv_value(lv, d, o); ELO_SRC["순위표 → 라벨"] += 1
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
    print("MAPNEED", sorted(set(MAPNEED)))
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010 이후)
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
JRE = re.compile(r"Honda|혼다")
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and JRE.search(str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(혼다 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("혼다 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) if G_BYDATE.get(r[9], "BRA1") in SA_DOM else same_team(x[1], r[1])):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and key(mm[1]) == key(m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 혼다 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("nagkh", "2008-01-16"), ("vvvkh", "2010-01-01"), ("cskkh", "2014-01-03"), ("milkh", "2017-07-14"), ("packh", "2018-08-06"),
         ("mvkh", "2019-11-06"), ("vitkh", "2020-01-31"), ("botkh", "2021-03-15"), ("nefkh", "2021-09-14"), ("sudkh", "2024-07-29"),
         ("parkh", "2026-07-01"), ("jurkh", None)]
TM_CLUB = {"1066": "nagkh", "1426": "vvvkh", "2410": "cskkh", "5": "milkh", "4035": "packh", "7006": "mvkh", "499": "vitkh", "537": "botkh",
           "8031": "nefkh", "8047": "sudkh", "71982": "parkh", "23472": "jurkh"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
def season_of(d, club):   # 계산기 시즌 구분과 같게(나고야·보타포구·수두바·파로 달력 연도, CSKA는 2010 / 2011-12 / 7월 1일 기준)
    if club in ("nagkh", "botkh", "sudkh", "parkh"): return d[:4]
    if club == "cskkh":
        if d < "2011-01-01": return "2010"
        if d < "2012-07-01": return "2011-12"
        return eu(d, "07-01")
    return eu(d)
KO_CLUB = {"nagkh": "나고야 그램퍼스", "vvvkh": "VVV-펜로", "cskkh": "CSKA 모스크바", "milkh": "AC 밀란", "packh": "파추카", "mvkh": "멜버른 빅토리",
           "vitkh": "비테서", "botkh": "보타포구", "nefkh": "네프치 바쿠", "sudkh": "수두바", "parkh": "파로 FC", "jurkh": "FC 주롱"}
ST = collections.OrderedDict((KO_CLUB[k], [0, 0, 0, 0]) for k, u in CLUBS)
for m in M: ST[KO_CLUB[club_of(m[0])]][0] += 1; ST[KO_CLUB[club_of(m[0])]][3] += m[3]
for r in E: ST[KO_CLUB[club_of(r[9])]][1 if r[0] == "g" else 2] += 1
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
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("dates changed", len(DATE_LOG))
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_honda.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl", "mlp", "lcg", "lck", "ac2"]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const HND_E={J(E)};\nconst HND_M={J(M)};\nconst HND_NOTE={J(NOTE)};\n")
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
