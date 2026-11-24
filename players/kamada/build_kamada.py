#!/usr/bin/env python3
"""가마다 다이치 (鎌田大地, Daichi Kamada, Transfermarkt 356141): raw/ -> kamada.json + players/kamada/kmd.js (판정 근거는 judgments.md)

  python3 players/kamada/build_kamada.py [--out <data 폴더>]   # 파일 쓰기(기본 players/kamada/kmd.js; 스크래치 복사본 검증 때 --out <복사본>/src/data)
  python3 players/kamada/build_kamada.py --debug               # Elo 출처 로그만 출력
  python3 players/kamada/build_kamada.py --stat                # 요약·판정·동료 대조

오카자키 build 스크립트(미토마와 같은 수집 형식)를 바탕으로 함. 순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의
parse()/value()(+ tools/league_points.py 승점·득실 모형)로 라벨에서 계산(v1.226·v1.290 규칙, 직접 숫자를 넣지 않음).
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
J리그 U-22 선발(J3에 참가한 연령별 선발 팀) 2경기는 경기 목록에서 제외(설명에 기록). 스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "kmd.js")
OUT_JSON = os.path.join(HERE, "kamada.json")
ME = "356141"
ME_KO = "가마다 다이치"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

AMATEUR = {"42631"}   # J리그 U-22 선발(J1·J2 클럽 22세 이하 선수로 꾸린 선발 팀, 2015 J3 참가) — 클럽이 아닌 선발 팀이라 2군·선발 팀 규칙으로 제외
ALLG = rd("tm_games.csv")   # 클럽 경기 441개(U-22 선발 2 포함)
EXCL = [g for g in ALLG if g["club_id"] in AMATEUR]
GAMES = [g for g in ALLG if g["club_id"] not in AMATEUR]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
MISSING_OG = []   # TM 골 목록에서 빠진 골 없음(중간 스코어 점검 SCORE_MISMATCH 0)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["status"] == "OK"}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 날짜
# 모든 경기: TM API 경기 시각(UTC)을 경기장 시간대로 바꾼 현지 날짜(raw/tm_games.csv date_local_tz_conv). 일본 경기 = 도쿄,
# 유럽 원정 = 개최지 시간대, 중립 경기(2022 UEFA 슈퍼컵 헬싱키, 2026 컨퍼런스리그 결승 라이프치히) = 개최지.
# TM 일정·리포트·FotMob 날짜와 다른 경기 0(raw/tm_date_disagreements.csv).
DATE_FIX = {}
DATE_LOG = []
LD = {}
for gid, g in G.items():
    LD[gid] = DATE_FIX.get(gid, g["date_local_tz_conv"])
    if LD[gid] != g["date_local_schedule"]: DATE_LOG.append((gid, g["date_local_schedule"], LD[gid], g["club"], g["opponent"]))
def ldate(g): return LD[g["gameId"]]
OPP_NAME = {}
def opp(g): return OPP_NAME.get(g["gameId"]) or g["opponent"].strip()   # TM 표기 그대로('(-2022)' 같은 해체 표시 포함: 승점 표 map·다른 선수 자료와 같은 이름)

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
# J1(2015·2016 1·2스테이지 JL11·JL12, 2017 JAP1)·분데스리가·세리에A·PL·벨기에 1부 + 벨기에 유로파 플레이오프(POBE, 오카자키·트로사르 선례) = 리그
LEAGUE = {"JAP1", "JL11", "JL12", "L1", "IT1", "GB1", "BE1", "POBE"}
# 일왕배·J리그컵(나비스코컵/르방컵)·벨기에컵·DFB 포칼·코파 이탈리아·FA컵·리그컵 = 국내컵(오카자키·미토마 선례)
CUPS = {"JEMP", "JAPC", "CCB", "DFB", "CIT", "FAC", "CGB"}
SUPER = {"GBCS", "USC"}                        # 커뮤니티 실드·UEFA 슈퍼컵 = 국내컵 결승 비중(docs 3절)

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
    if cid == "EL":   # 조별(2026-27 리그 단계 'Group Stage' 포함)·32강(intermediate stage)·16강·8강·준결승·결승
        if r.startswith("group"): return "elg"
        if r.startswith(("intermediate stage", "last 16", "quarter")): return "elk"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        sys.exit("EL 단계 " + rnd)
    if cid == "ELQ": return "elq"
    if cid == "ECLQ": return "ecq"
    if cid == "UCOL":   # 컨퍼런스리그 2025-26: 리그 단계·녹아웃 플레이오프(intermediate stage)·16강·8강·준결승·결승
        if r.startswith("group"): return "ecg"
        if r.startswith(("intermediate stage", "last 16", "quarter")): return "eck"
        if r.startswith("semi"): return "ecsf"
        if r.startswith("final"): return "ecf"
        sys.exit("UCOL 단계 " + rnd)
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
    if cid in ("EL", "ELQ", "CL", "UCOL", "ECLQ"):
        return (1, 1) if d < "2021-07-01" else (0, 1)   # UEFA: 2021-07 전 원정 다득점·연장, 뒤 원정 다득점 없음·연장
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
 "2562756|90+4": (True, "사가 신문 사진 설명(후반 로스타임 도요타의 결승골을 부른 패스를 내주는 가마다)·J리그 공식 사이트 특집 '街の誇りを世界へ'(85분 투입된 가마다가 경기 끝 무렵 스루패스로 도요타 결승골을 연출); FotMob은 기쿠치 도움으로 적음"),
 "2659568|30": (False, "J리그 공식 경기 전평·문자 중계: 가마다의 패스가 상대 오타니에게 맞고 굴절돼 수비 뒤로 흐른 공을 도요타가 넣음 — 굴절이라 도움 아님"),
 "2662378|38": (True, "J리그 공식 경기 전평(도미야마의 컷백을 가마다가 원터치로 왼쪽에 흘려 백성동이 슈팅)·J리그 공식 문자 중계(같은 장면)"),
 "2659697|32": (True, "J리그 공식 경기 전평(오른쪽 박스 옆에서 가마다가 올린 크로스를 김민우가 헤더, 김민우 '다이치의 공이 좋았다')·J리그 공식 문자 중계(가마다 크로스 → 김민우 헤더)"),
 "2659734|20": (False, "J리그 공식 경기 전평·문자 중계: 가마다의 헤더가 크로스바를 맞고 나온 공을 도요타가 밀어 넣음 — 슈팅 리바운드라 도움 아님"),
 "2754665|62": (False, "일왕배 2회전 류큐전 오카다 골: JFA·J리그 대회 기사·류큐 신보는 득점자만 적고 도움자를 적지 않아 다른 출처 2곳을 찾지 못함"),
 "2659842|51": (True, "J리그 공식 경기 전평(가마다가 긴 거리를 드리블한 뒤 나란히 달린 도미야마에게 패스, 도미야마 슈팅이 수비 맞고 들어감)·J리그 공식 문자 중계(같은 장면)"),
 "3117096|59": (True, "Sporza 경기 기사('Op aangeven van Kamada joeg De Norre de bal ... 1-0')·Voetbalkrant 경기 기록·문자 중계('Doelpunt van Casper De Norre (Daichi Kamada)', 가마다의 준비 작업)"),
 "3135302|90": (False, "Sporza 문자 중계만 가마다 도움(보리 골)으로 적음 — Voetbalkrant는 도움자 없음, FotMob·ESPN 도움자 없음: 다른 출처 2곳을 찾지 못함"),
 "3169855|28": (False, "기노시타 골: FotMob 경기 이벤트·선수 경기 목록(도움 0)·ESPN·Sports Mole 모두 도움자 없음, 다른 출처를 찾지 못함"),
 "3839104|32": (False, "콜로 무아니 골: FotMob 경기 이벤트(도움자 없음)·선수 경기 목록(이 경기 도움 1 = 48분 소우 골)·ESPN 도움자 없음, Transfermarkt 공식 도움 칸도 1 — 다른 출처 2곳을 찾지 못함"),
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
MANUAL_ALIAS = {"hokkaido consadole sapporo": "consadole sapporo"}   # 순위표 표기에 맞춤(TM 2017 표기 → 위키·통합표 표기)
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "kmd.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
# 이번 회차에 함께 판정한 선수(판정 끝남, 읽기만): 같은 경기면 같은 Elo/lv
for pth in sorted(glob.glob(os.path.join(os.path.dirname(HERE), "*", "*.js"))):
    slug, fn = pth.split(os.sep)[-2:]
    if slug not in ("leejaesung", "nakamura", "scholes", "yayatoure") or "src/data/" + fn in TRACKED: continue
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
SA_DOM = {"JAP1", "JL11", "JL12", "JAPC", "JEMP", "BE1", "POBE", "CCB", "ARG1", "ARGC", "CLI", "CS", "BRA1", "BCP1", "BCPF", "MEX1", "MEXA", "POME", "USMX", "MLS1", "MLSP", "COL1", "COPO", "QSL", "QEC1", "KLUB"}
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
# J1 2015·2016(1·2스테이지 + 챔피언십): TM에는 스테이지 표뿐이라 영어 위키백과 시즌 문서의 연간 순위표('Overall table', raw/ranks_wiki.txt 표 7).
# 기존 자료(가시마 2016 'J1리그 2016 연간 3위/18팀')와 같이 연간 승점 순위를 '연간'으로 표시. 2017은 TM 표(단일 리그).
WIKI_T = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks_wiki.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 6 or p[0] == "file": continue
        nm = re.sub(r"\s*\([A-Z, ]+\)$", "", p[5]).strip()
        WIKI_T[(p[0], p[1])][key(nm)] = (int(p[3]), int(p[4]), nm, p[0])
for yy in ("2015", "2016"):
    RANKS[("J1Y", yy)] = WIKI_T[(f"en_{yy}_J1_League.html", "7")]
    if len(RANKS[("J1Y", yy)]) != 18: sys.exit("J1 연간 표 " + yy)
RANKS[("J3", "2016")] = WIKI_T[("en_2016_J3_League.html", "3")]
RANKS[("J2", "2016")] = WIKI_T[("en_2016_J2_League.html", "4")]
J1_CHECK = []
# 벨기에 1부 2018-19 최종 순위(FotMob 표): 챔피언 플레이오프 1~6, 나머지 7~16은 정규 시즌 순서(유럽 플레이오프 A·B조는 섞인 조라 정규 시즌 순)
FMBE = collections.defaultdict(list)
with open(os.path.join(RAW, "ranks_fotmob.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or not p[0].startswith("40 "): continue
        FMBE[p[0].split(" / ")[-1]].append((int(p[2]), p[4]))
FM2TM = {"club brugge": "club brugge kv", "anderlecht": "rsc anderlecht", "royal antwerp": "royal antwerp fc", "antwerp": "royal antwerp fc",
         "gent": "kaa gent", "genk": "krc genk", "sporting charleroi": "royal charleroi sc", "charleroi": "royal charleroi sc", "st truiden": "sint truidense vv",
         "oostende": "kv oostende", "kortrijk": "kv kortrijk", "eupen": "kas eupen", "standard liege": "standard liege", "cercle brugge": "cercle brugge",
         "zulte waregem": "zulte waregem", "kv mechelen": "kv mechelen", "excel mouscron": "royal excel mouscron", "mouscron": "royal excel mouscron",
         "lokeren": "ksc lokeren", "waasland beveren": "kvrs waasland sk beveren"}
reg = RANKS[("BE1", "2018-19")]
regk = {norm(v[2]): k for k, v in reg.items()}
def tmk(nm):
    t = FM2TM.get(norm(nm), norm(nm))
    hit = [k for nn, k in regk.items() if nn.startswith(t) or (" " + t) in (" " + nn)]
    if not hit: hit = [k for nn, k in regk.items() if t.split()[-1] in nn.split()]
    if len(hit) != 1: sys.exit(f"벨기에 표 이름 연결 실패 {nm} {hit}")
    return hit[0]
order_reg = [tmk(nm) for r, nm in sorted(FMBE["First Division A"])]
po1 = [tmk(nm) for r, nm in sorted(FMBE["Playoff Championship Group"])]
if set(po1) != set(order_reg[:6]) or set(order_reg) != set(reg): sys.exit("벨기에 플레이오프 팀 다름")
for i_, k in enumerate(po1 + order_reg[6:]): reg[k] = (i_ + 1, 16, reg[k][2], "2018-19 플레이오프 뒤")

EU_LG = {"FR1": "리그1", "ES1": "라리가", "L1": "분데스리가", "GB1": "프리미어리그", "PO1": "포르투갈 1부", "IT1": "세리에A", "NL1": "에레디비시"}
def make_label(lg, season, v):
    lv = make_label0(lg, season, v)
    if lv and season == "2026-27":   # 진행 중 시즌: Transfermarkt 표(2026.11.24 받음)의 현재 순위, 팀 수 표시
        h = lv.split(" (")[0]
        if "팀" not in h: h += f"/{v[1]}팀"
        lv = h + " (2026년 11월 24일 현재 순위" + (", " + lv.split(" (", 1)[1] if " (" in lv else ")")
    return lv
def make_label0(lg, season, v):
    r, n, nm, sraw = v
    if lg == "J1": return f"J1리그 {season} {r}위/{n}팀"
    if lg == "J1Y": return f"J1리그 {season} 연간 {r}위/{n}팀 (1·2스테이지 합산 연간 순위표)"
    if lg == "J2": return f"J2리그 {season} {r}위/{n}팀"
    if lg == "J3": return f"일본 3부 {season} {r}위/{n}팀 (J3 League, 리그 수준 추정)"
    if lg == "BE1": return f"벨기에 1부 {season} {r}위/{n}팀 (Belgian First Division A, 플레이오프 뒤 최종 순위)"
    if lg == "BE2": return f"벨기에 2부 {season} {r}위/{n}팀 (First Division B, 리그 수준 추정)"
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

# 시즌: 사간 도스 경기는 달력 연도(J리그; 1월 경기 없음). 그 밖은 8월 1일 기준(7월 유럽 예선은 끝난 시즌 순위).
def seasons_for(cid, d, o, g):
    y, m = int(d[:4]), int(d[5:7])
    if g["club_id"] == "22177": return [str(y)]
    s_ = y if m >= 8 else y - 1
    return [f"{s_}-{str(s_ + 1)[2:]}"]
DOM = {"22177": ["J1Y", "J1", "J2", "J3"], "24": ["L1", "L2", "L3"], "475": ["BE1", "BE2"], "398": ["IT1"], "873": ["GB1", "GB2", "GB3", "GB4"]}
def lg_cands(cid, d, o, g):
    ss = seasons_for(cid, d, o, g)
    doms = DOM[g["club_id"]] if cid not in ("EL", "ELQ", "CL", "UCOL", "ECLQ") else list(EU_LG)
    return [(lg, s_) for lg in doms for s_ in ss]

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산)
def man(o, s, lv): MAN[(key(o), s)] = lv
# 2018.12.5 벨기에컵 16강 KFC 만덜 유나이티드: 2018-19 벨기에 4부(Second Amateur Division A, 16팀) 2위 — 영어 위키백과 시즌 문서 순위표(raw/ranks_wiki.txt)
man("KFC Mandel United", "2018-19", "벨기에 4부 2018-19 2위/16팀 (Belgian Second Amateur Division A, 리그 수준 추정)")
# 2021.10.21·11.4 유로파 조별 올림피아코스: 그리스 슈퍼리그 2021-22 최종 1위/14팀(TM 표·위키 최종 순위표 모두 우승)
man("Olympiacos Piraeus", "2021-22", "그리스 1부 2021-22 1위/14팀 (Super League Greece, 플레이오프·스플릿 뒤 최종 순위)")
# 2025.12.11 컨퍼런스리그 리그 단계 셸본: 아일랜드 프리미어 디비전 2025(달력 연도, 11월 끝남) 최종 3위/10팀(TM 표)
man("Shelbourne FC", "2025-26", "아일랜드 1부 2025 3위/10팀 (League of Ireland Premier Division)")
# 2026.3.19 컨퍼런스리그 16강 2차전 AEK 라르나카: 키프로스 1부 2025-26 최종 2위/14팀(챔피언십 라운드 뒤, TM 표·승점 표)
man("AEK Larnaca", "2025-26", "키프로스 1부 2025-26 2위/14팀 (Cypriot First Division, 플레이오프·스플릿 뒤 최종 순위)")
# 2026.4.30 컨퍼런스리그 준결승 1차전 샤흐타르: 우크라이나 1부 2025-26 최종 1위/16팀(TM 표·승점 표)
man("Shakhtar Donetsk", "2025-26", "우크라이나 1부 2025-26 1위/16팀 (Ukrainian Premier League)")
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
JRE = re.compile(r"Kamada|가마다")
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and JRE.search(str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(가마다 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("가마다 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 가마다 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("tosdk", "2017-07-01", "사간 도스", "사간 도스", "2015~2017"), ("sgedk", "2018-08-31", "아인트라흐트 프랑크푸르트", "프랑크푸르트", "2017~2023"),
         ("stvdk", "2019-07-01", "신트트라위던 VV", "신트트라위던", "2018~2019"), ("sgedk", "2023-08-04", "아인트라흐트 프랑크푸르트", "프랑크푸르트", "2017~2023"),
         ("lazdk", "2024-07-01", "SS 라치오", "라치오", "2023~2024"), ("cpldk", None, "크리스털 팰리스", "크리스털 팰리스", "2024~")]
TM_CLUB = {"22177": "tosdk", "24": "sgedk", "475": "stvdk", "398": "lazdk", "873": "cpldk"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
SCAL = ("tosdk",)   # J리그 달력 연도(사간 도스 1월 경기 없음)
SJUL10 = ("sgedk", "stvdk")   # 7월 10일 기준(프랑크푸르트 2019.7.25 유로파 예선이 새 시즌, 신트트라위던은 가가와·오카자키 선례)
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in SCAL: return str(y)
    if club == "sgedk" and "2020-07-01" <= d < "2020-09-01": return "2019-20"   # 2020.8.6 유로파 16강 2차전 바젤(코로나로 미뤄진 2019-20 시즌, 코스티치 sgefk 선례)
    if club in SJUL10:
        s_ = y if d[5:] >= "07-10" else y - 1
        return f"{s_}-{str(s_ + 1)[2:]}"
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("사간 도스", "2017-07-01"), ("프랑크푸르트 2017-18", "2018-08-31"), ("신트트라위던(임대)", "2019-07-01"), ("프랑크푸르트 2019~2023", "2023-08-04"),
          ("라치오", "2024-07-01"), ("크리스털 팰리스", "9999")]
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
exec(open(os.path.join(HERE, "note_kamada.py"), encoding="utf-8").read())   # NOTE_LINES
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const KMD_E={J(E)};\nconst KMD_M={J(M)};\nconst KMD_NOTE={J(NOTE)};\n")
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
