#!/usr/bin/env python3
"""팀 케이힐 (Tim Cahill, Transfermarkt 13556): raw/ -> cahill.json + players/cahill/cah.js (판정 근거는 judgments.md)

  python3 players/cahill/build_cahill.py [--out <data 폴더>]   # 파일 쓰기(기본 players/cahill/cah.js; 스크래치 복사본 검증 때 --out <복사본>/src/data)
  python3 players/cahill/build_cahill.py --debug               # Elo 출처 로그만 출력
  python3 players/cahill/build_cahill.py --stat                # 요약·판정·동료 대조

아즈문·오카자키 build 스크립트(같은 수집 형식)를 바탕으로 함. 순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의
parse()/value()(+ tools/league_points.py 승점·득실 모형)로 라벨에서 계산(v1.226·v1.290 규칙, 직접 숫자를 넣지 않음).
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 라벨.
시드니 유나이티드 1997(NSW 주 리그, 세미프로)은 경기 자료도 없고 프로 리그가 아니라 제외.
TM 경기 목록에 없는 밀월·멜버른 시티 경기 9개는 경기 단위 출처(라인업·경기 기사·위키백과 경기 상자)로 확인한 것만 추가(EXTRA).
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "cah.js")
OUT_JSON = os.path.join(HERE, "cahill.json")
ME = "13556"
ME_KO = "팀 케이힐"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]   # 성인 클럽 경기 689(유소년·2군 없음)
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# ---------------------------------------------------------------- TM 목록에 없는 공식 경기(경기 단위 출처로 확인한 것만)
MIL, MCY = ("1028", "Millwall FC"), ("25580", "Melbourne City FC")
EXTRA = [
 # (id, 날짜, 대회, 라운드, 클럽, 상대, 상대 id, 홈/원정, 최종 스코어(홈:원정), 출전 분, 추정 여부, 골 이벤트[(분, 'home'|'away', 득점자, 득점자 id, PK)], 근거)
 ("X20000513", "2000-05-13", "POSD", "Semi-Finals 1st Leg", MIL, "Wigan Athletic", "1071", "H", "0:0", 90, 0, [],
  "2부 디비전(3부) 승격 플레이오프 준결승 1차전. Wigan Athletic Heritage 라인업(wiganathleticheritage.co.uk/lineups/2213): 케이힐 선발, 교체 없음"),
 ("X20000517", "2000-05-17", "POSD", "Semi-Finals 2nd Leg", MIL, "Wigan Athletic", "1071", "A", "1:0", 90, 0, [],
  "같은 플레이오프 2차전. Wigan Athletic Heritage 라인업(lineups/2214): 케이힐 선발, 교체 없음(밀월 교체는 라이언·이필)"),
 ("X20000919", "2000-09-19", "CGB", "Second Round 1st leg", MIL, "Ipswich Town", "677", "H", "2:0", 90, 1,
  [("36", "home", "Paul Ifill", "x1", 0), ("79", "home", "Tim Cahill", ME, 0)],
  "리그컵 2라운드 1차전. 영어 위키백과 '2000–01 Ipswich Town F.C. season' 경기 상자(이필 36분, 케이힐 79분; BBC 보도 링크)·'2000–01 Millwall F.C. season'(득점 이필·케이힐)·TWTD 경기 기사(이필 선제골 뒤 후반 막판 케이힐 추가골). 출전 분 자료 없음 → 90분 추정"),
 ("X20000926", "2000-09-26", "CGB", "Second Round 2nd leg", MIL, "Ipswich Town", "677", "A", "5:0", 90, 1, [],
  "리그컵 2라운드 2차전(연장 5-0, 합계 2-5). TWTD 경기 기사에 케이힐 슈팅 장면(출전 확인), 교체 여부 자료 없음 → 90분 추정"),
 ("X20020428", "2002-04-28", "POFD", "Semi-Finals 1st Leg", MIL, "Birmingham City", "337", "A", "1:1", 90, 0, [],
  "1부 디비전(2부) 승격 플레이오프 준결승 1차전. ESPN 경기 자료(event 48339) 라인업: 케이힐 선발, 교체 아웃 없음"),
 ("X20020502", "2002-05-02", "POFD", "Semi-Finals 2nd Leg", MIL, "Birmingham City", "337", "H", "0:1", 90, 0, [],
  "같은 플레이오프 2차전. ESPN 경기 자료(event 48383) 라인업: 케이힐 선발, 교체 아웃 없음"),
 ("X20160824", "2016-08-24", "FFAC", "Round of 16", MCY, "Brisbane Strikers", "x", "A", "1:2", 26, 0, [],
  "FFA컵 16강. ESPN 기사·FTBL 기사: 64분 카세레스 대신 교체 투입(멜버른 시티 첫 공식 경기) → 26분"),
 ("X20160921", "2016-09-21", "FFAC", "Quarter-Finals", MCY, "Western Sydney Wanderers", "x", "H", "4:1", 90, 1,
  [("2", "home", "Michael Jakobsen", "x2", 0), ("32", "home", "Bruno Fornaroli", "x3", 0), ("45", "home", "Tim Cahill", ME, 1),
   ("65", "home", "Fernando Brandán", "x4", 0), ("73", "away", "Dimas Delgado", "x5", 0)],
  "FFA컵 8강. 호주컵 공식 기사(australiacup.com.au 'Cahill scores as City storm into FFA Cup semis': 선발, 전반 끝 무렵 PK 골)·영어 위키백과 '2016 FFA Cup'(Cahill 45' pen.)·FotMob 경기 이벤트(45분 케이힐). 출전 분 자료 없음 → 90분 추정"),
 ("X20161025", "2016-10-25", "FFAC", "Semi-Finals", MCY, "Melbourne Victory", "x", "A", "0:2", 69, 0, [],
  "FFA컵 준결승(멜버른 더비). 멜버른 시티 구단 경기 기록(69분 레트레와 교체)·호주컵 공식 기사(선제골 때 케이힐이 골키퍼 시야를 가렸다는 항의)"),
]
EST_MIN = set()
for (xid, d, cid, rnd, club, o, oid, ha, fin, mn, est, evs, why) in EXTRA:
    GAMES.append({"gameId": xid, "date_local_tz_conv": d, "date_local_schedule": d, "competitionId": cid, "round": rnd, "club_id": club[0], "club": club[1],
                  "opponent": o, "opponent_id": oid, "venue": ha, "gameState": "extra_time" if xid == "X20000926" else "regularly_terminated",
                  "playedMinutes": str(mn), "goals": str(sum(1 for e in evs if e[3] == ME)), "assists": "0", "penGoals": str(sum(e[4] for e in evs if e[3] == ME)),
                  "level": "senior", "season_tm": ""})
    hn, an = (club[1], o) if ha == "H" else (o, club[1]); hi, ai = (club[0], oid) if ha == "H" else (oid, club[0])
    MI[xid] = {"gameId": xid, "round_report": rnd, "home": hn, "home_id": hi, "away": an, "away_id": ai, "final": fin, "other_leg_id": "", "other_leg_score": ""}
    EVS[xid] = [{"gameId": xid, "minute": m_, "side": sd, "scorer": nm, "scorer_id": sid, "goal_desc": "Penalty" if pk else "", "assist_player": "",
                 "assist_id": "", "assist_type": "", "penalty": str(pk), "own_goal": "0"} for (m_, sd, nm, sid, pk) in evs]
    if est: EST_MIN.add(xid)
# 리그컵 2000-01 2라운드: 다른 차전 스코어(위 두 경기)
MI["X20000919"]["other_leg_id"] = "X20000926"; MI["X20000926"]["other_leg_id"] = "X20000919"
MI["X20000513"]["other_leg_id"] = "X20000517"; MI["X20000517"]["other_leg_id"] = "X20000513"
MI["X20020428"]["other_leg_id"] = "X20020502"; MI["X20020502"]["other_leg_id"] = "X20020428"
G = {g["gameId"]: g for g in GAMES}
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["status"] == "OK"}

# ---------------------------------------------------------------- 날짜
# TM API 경기 시각(UTC)을 경기장 시간대로 바꾼 현지 날짜(raw/tm_games.csv date_local_tz_conv). 1998~2004 밀월 경기 101개는 TM '시각 모름'(00:00 CET)
# 자리 표시라 TM 일정 날짜(=중부 유럽 날짜, 모두 일치). MLS 저녁 경기 47개는 현지(미국) 날짜(TM 일정·리포트는 다음 날).
# 고침: 2510777 2014 MLS 플레이오프 동부 준결승 2차전 D.C. 유나이티드 원정 — TM UTC 2014-11-07 23:00(자리 표시로 보임) → 2014.11.8(토).
#       FotMob 킥오프(2014-11-08)·앙리 자료(같은 경기 2014-11-08)와 맞춤.
DATE_FIX = {"2510777": "2014-11-08"}
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
# 리그: 잉글랜드 2부 디비전(3부, ENSD)·1부 디비전(2부, EFD2)·프리미어리그·챔피언십·MLS·중국 슈퍼리그·A리그·인도 슈퍼리그
# + 잉글랜드 승격 플레이오프(POSD 2000·POFD 2002, TM에 없어 추가) = 리그 비중(애슐리 영 2006 왓퍼드 선례)
LEAGUE = {"GB1", "GB2", "ENSD", "EFD2", "MLS1", "CSL", "AUS1", "IND1", "POSD", "POFD"}
# FA컵·리그컵·풋볼 리그 트로피(1군 경기, 왓킨스 선례)·중국 FA컵·FFA컵 = 국내컵
CUPS = {"FAC", "CGB", "GBFL", "CHFA", "FFAC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:   # 16강까지 국내컵, 8강(리그컵 5라운드·FA컵 6라운드 포함) 이후 단계별(docs 3절)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"   # 풋볼 리그 트로피 '남부 지역 결승'(TM 'Semi-Finals') = 전체 준결승
        if r.startswith(("quarter", "sixth", "6th")): return "dk"
        return "dc"
    if cid == "CLQ": return "clq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선(docs 3절)
        if r.startswith("group"): return "elg"
        return "elk"                                    # 2007-08 3라운드(32강)·16강
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"                                    # 2009-10 32강(Second Round)
    if cid == "CCL":
        if r.startswith("group"): return "ccc"
    if cid == "POUS":   # MLS 컵 플레이오프(베컴·앙리 선례): 녹아웃 라운드·콘퍼런스 준결승 mlp, 콘퍼런스 결승 mlpsf
        if r.startswith("final"): return "mlpf"
        if r.startswith("semi"): return "mlpsf"
        return "mlp"
    if cid == "AUSF": return "mlp"   # A리그 파이널 시리즈 = MLS 플레이오프 비중(델 피에로·아두리스 선례), 엘리미네이션 파이널 단판
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
    if cid in ("CLQ", "UEFA", "EL", "ELQ"): return (1, 1)   # UEFA 2020-21까지 원정 다득점·연장
    if cid == "CGB": return (1, 1)                         # 리그컵 두 경기(1998~2001 1·2라운드, 2008 준결승): 원정 다득점·연장(2017-18까지)
    if cid == "GBFL": return (1, 1)                        # 풋볼 리그 트로피 1999 남부 지역 결승: 리그컵과 같게 둠(규정 문서 미확인, 추정)
    if cid == "CHFA": return (1, 1)                        # 중국 FA컵 2015 준결승·결승: 원정 다득점·연장(엘샤라위·파투·테베스 선례)
    if cid == "POUS": return (int(d >= "2014-01-01"), 1)   # MLS 플레이오프: 2012·2013 원정 다득점 없음, 2014부터 있음, 연장(앙리 자료와 같음)
    if cid in ("POSD", "POFD"): return (0, 1)              # 잉글랜드 승격 플레이오프 준결승: 원정 다득점 없음, 연장(애슐리 영 선례)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; oid = m["other_leg_id"]; club = G[gid]["club_id"]
    if not oid:
        g = G[gid]; c = [x for x in GAMES if x["competitionId"] == g["competitionId"] and x["opponent_id"] == g["opponent_id"] and "1st" in rnd_of(x).lower() and x["gameId"] != gid
                         and abs(int(ldate(x)[:4]) - int(ldate(g)[:4])) <= 1]
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
        if f["sq_assist"] == "1" and f["pen_shootout_event"] != "True" and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])): return True
    return False

def a_key(gid, minute): return f"{gid}|{minute}"
# 2014.8 이후 TM 도움 중 FotMob 경기 이벤트가 같이 적지 않은 것: TM 외 독립 출처 2곳으로 확인한 것만 넣음(근거는 judgments.md)
A_CHECK = {
 # 2014.8.26 북중미 챔스 조별 FAS전 11분 세네: ESPN 경기 이벤트(도움 케이힐)·SBI 경기 기사('케이힐이 머리로 세네 앞에 떨궈 줌')·FourFourTwo 경기 정리(케이힐 도움)
 "2483866|11": (True, "ESPN 경기 이벤트(도움 케이힐)·SBI Soccer 경기 기사(케이힐이 머리로 떨궈 준 공을 세네가 넣음)·FourFourTwo 북중미 챔스 정리(케이힐 도움)"),
 # 2015.3.8 상하이 선신전 39분: TM 득점 유형 'Own-goal'(임유환 자책골) → 상대 자책골 유도(규칙상 도움 아님, 아래 is_og에서 먼저 걸림)
 # 2015 중국 경기 TM 단독 도움 4개: FotMob 이벤트에 도움자 없음, ESPN에 경기 없음, 영어·중국어 기사 검색으로 두 번째 출처 못 찾음 → 뺌
 "2544172|58": (False, "FotMob 이벤트에 도움자 없음·ESPN 경기 없음, 다른 출처 못 찾음(TM 단독)"),
 "2544179|82": (False, "FotMob 이벤트에 도움자 없음·ESPN 경기 없음, 다른 출처 못 찾음(TM 단독)"),
 "2544384|36": (False, "FotMob 이벤트에 도움자 없음·ESPN 경기 없음, 다른 출처 못 찾음(TM 단독)"),
 "2614383|28": (False, "FotMob 경기 자료 없음(중국 FA컵)·ESPN 경기 없음, 다른 출처 못 찾음(TM 단독)"),
 # 2016.10.21 A리그 퍼스 글로리전 60분 브란단: ESPN 경기 이벤트(도움 케이힐)·멜버른 시티 구단 경기 기사('케이힐의 절묘한 패스로 브란단이 골키퍼와 맞섬')
 "2763511|60": (True, "ESPN 경기 이벤트(도움 케이힐)·멜버른 시티 구단 경기 기사(케이힐의 스루패스를 브란단이 마무리)"),
}
ADD_A = []   # FotMob 단독 도움 추가 없음(2011.9.17 위건전 33분 자기엘카는 두 번째 출처 없음)

A_STATUS = []
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
    if fm_assist(gid, e):
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "2014.8 이후 TM 단독(확인 못 함): " + why
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음"))
    return "2014.8 이후 단일 출처(판정 없음)"

MIN_FIX = {}   # 골·도움 시각은 모두 Transfermarkt(추가 경기는 위 출처) 그대로
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
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["sq_assist"] == "1" and f["pen_shootout_event"] != "True":
            mi = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(e["assist_id"] == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, mi, f["scorer"]))
                judg.append(("FotMob 단독 도움(넣지 않음)", ldate(G[gid]), opp(G[gid]), str(mi), f["scorer"], "TM·ESPN 모두 도움자 다름/없음, 다른 출처 못 찾음"))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G or (gid.startswith("X") and not evs): continue
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "cah.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
for pth in sorted(glob.glob(os.path.join(os.path.dirname(HERE), "*", "*.js"))):
    slug, fn = pth.split(os.sep)[-2:]
    if slug not in ("okazaki", "minamino", "honda", "szoboszlai") or "src/data/" + fn in TRACKED: continue
    try: P, oe, om = load_js(pth)
    except Exception: continue
    OTHERS["players/" + slug + "/" + fn] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "athletic", "wanderers", "rangers", "town",
        "county", "albion", "rovers", "hotspur", "palace", "villa", "ham", "manchester", "sheffield", "bristol", "birmingham", "nottingham", "queens", "park",
        "west", "aston", "new", "york", "los", "angeles", "toronto", "sd", "cd", "fk", "sk", "melbourne", "sydney", "shanghai", "beijing", "jiangsu", "guangzhou",
        "shandong", "tianjin", "henan", "chongqing", "hangzhou", "dalian", "united", "athletic", "north", "end", "orient", "argyle", "alexandra", "dons", "stanley"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
EXACT_DOM = {"MLS1", "POUS", "CCL", "AUS1", "AUSF", "FFAC", "CSL", "CHFA", "IND1"}
def same_match(o, d, cid):
    if cid in EXACT_DOM:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    else:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)] or [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위 라벨 → Elo (tools/league_rank_apply.py + tools/league_points.py)
_LRA = {"__file__": os.path.join(ROOT, "tools", "league_rank_apply.py"), "__name__": "lra"}
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA["__file__"], encoding="utf-8").read().split("if __name__ == '__main__':")[0], "lra", "exec"), _LRA)
sys.argv = _argv
sys.path.insert(0, os.path.join(ROOT, "tools"))
import league_points as PTS
# 승점 표(elo/league_points_other.json)의 map에 없는 이 선수 상대 이름: 같은 순위 행·이름 확인 뒤 메모리에서만 더함(오케스트레이터가 표에 추가, judgments.md 목록)
MAP_ADD = {}
def pts_head(lv):
    h = lv.split(" (")[0]; mm = re.match(r"^(.*?) \d+위", h)
    return mm.group(1) if mm and mm.group(1) in PTS.O["seasons"] else None
def ensure_map(lv, o):
    head = pts_head(lv)
    if not head: return
    E_ = PTS.O["seasons"][head]
    if "skip" in E_ or E_.get("ongoing"): return
    if PTS.other_score(lv, o): return
    rk = int(re.search(r"(\d+)위", lv.split(" (")[0]).group(1))
    hits = []
    for ti, T in enumerate(E_["tables"]):
        if rk - 1 < len(T["rows"]): hits.append((PTS.sim(o, T["rows"][rk - 1][0]), ti, rk - 1, T["rows"][rk - 1][0]))
    hits.sort(reverse=True)
    if not hits or hits[0][0] < 0.5: sys.exit(f"승점 표 행 연결 실패 {lv} {o} {hits}")
    s_, ti, ri, nm = hits[0]
    E_.setdefault("map", {})[o] = [ti, ri]; PTS._OS.clear()
    MAP_ADD[(head, o)] = (nm, ti, ri)
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
            ensure_map(lv, o)
            vp = PTS.value_other(lv, o, p[0], p[1], _LRA["base"](p[0], p[1], p[2], p[3]), _LRA["sd"](p[0], p[1]), _LRA["cv"])
        if vp is not None: v = vp
    return v

# 순위표: TM 표(raw/ranks.txt) + 위키백과 표(raw/ranks_wiki.txt: 잉글랜드 4부 1998-99·1999-2000·2001-02, 5부 2003-04, 중국 2부 2015, 인도 2018-19)
#         + 저장소 승점 표(raw/ranks_elo_tables.txt = elo/league_points_other.json 사본: MLS 2012~2014 전체 순위, A리그 2016-17, 중국 2015·2016 등)
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] in ("league",) or p[0].startswith("#"): continue
        se = p[1].split(" ")[0]
        if p[0] == "MLS1" and "group" in p[1]: continue   # MLS 2014·2015 TM 표는 콘퍼런스 표 → 승점 표(전체 순위)를 씀
        RANKS[(p[0], se)][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1])
WIKI_LG = {"Football_League_Third_Division": "W4", "Football_Conference": "W5", "China_League_One": "CHN2", "Indian_Super_League_season": "IND1W"}
with open(os.path.join(RAW, "ranks_wiki.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 6 or p[0].startswith("#"): continue
        mm = re.match(r"^(\d{4})(?:–(\d{2,4}))?_(.*)$", p[0])
        lg = WIKI_LG.get(mm.group(3))
        if not lg: continue
        se = mm.group(1) if not mm.group(2) else f"{mm.group(1)}-{mm.group(2)[-2:]}"
        nm = re.sub(r"\s*\([A-Z, ]+\)$", "", p[5]).strip()
        RANKS[(lg, se)][key(nm)] = (int(p[3]), int(p[4]), nm, p[0])
PTSKEY = {"MLS": "MLSP", "호주 A리그": "AUSP", "중국 슈퍼리그": "CSLP"}
with open(os.path.join(RAW, "ranks_elo_tables.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0].startswith("#"): continue
        mm = re.match(r"^(MLS|호주 A리그|중국 슈퍼리그) (\d{4}(?:-\d{2})?)$", p[0])
        if not mm: continue
        RANKS[(PTSKEY[mm.group(1)], mm.group(2))][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[0] + " 승점 표")
# 순위 고침(TM 표의 동률 순서가 공식 순위와 다른 것)
#  그리스 1부 2007-08: 파니오니오스·AEL(라리사) 45점 동률, 영어 위키백과 시즌 순위표(저장소 승점 표 '그리스 1부 2007-08')는 파니오니오스 5위·AEL 6위(상대 전적) → TM 5위를 6위로
RANK_FIX = {("GR1", "2007-08", "AE Larisa"): 6}
for (lg_, se_, nm_), rk_ in RANK_FIX.items():
    v_ = RANKS[(lg_, se_)][key(nm_)]; RANKS[(lg_, se_)][key(nm_)] = (rk_,) + v_[1:]
# 감점 시즌(elo/penalty_seasons.json): 경기장 순위로 바꿈
PEN = json.load(open(os.path.join(ELO, "penalty_seasons.json"), encoding="utf-8"))["changes"]

EU_LG = {"FR1": "리그1", "ES1": "라리가", "L1": "분데스리가", "GB1": "프리미어리그", "PO1": "포르투갈 1부", "IT1": "세리에A", "NL1": "에레디비시"}
OTH = {"RU1": ("러시아 1부", "Russian Premier League"), "GR1": ("그리스 1부", "Super League Greece"), "RO1": ("루마니아 1부", "Liga I"),
       "NO1": ("노르웨이 1부", "Eliteserien"), "BE1": ("벨기에 1부", "Belgian First Division"), "TS1": ("체코 1부", "Czech First League"),
       "UKR1": ("우크라이나 1부", "Ukrainian Premier League")}
def make_label(lg, season, v):
    r, n, nm, sraw = v
    if lg in ("ENSD",): return f"잉글랜드 3부 {season} {r}위/{n}팀 (Football League Second Division, 리그 수준 추정)"
    if lg in ("EFD2", "GB2"): return f"챔피언십 {season} {r}위/{n}팀"
    if lg == "GB3": return f"잉글랜드 3부 {season} {r}위/{n}팀 (Football League One, 리그 수준 추정)"
    if lg == "GB4": return f"잉글랜드 4부 {season} {r}위/{n}팀 (Football League Two, 리그 수준 추정)"
    if lg == "W4": return f"잉글랜드 4부 {season} {r}위/{n}팀 (Football League Third Division, 리그 수준 추정)"
    if lg == "W5": return f"잉글랜드 5부 {season} {r}위/{n}팀 (Football Conference, 리그 수준 추정)"
    if lg == "MLSP": return f"MLS {season} {r}위/{n}팀"
    if lg == "CSLP": return f"중국 슈퍼리그 {season} {r}위/{n}팀"
    if lg == "CHN2": return f"중국 2부 {season} {r}위/{n}팀 (China League One, 리그 수준 추정)"
    if lg == "AUSP": return f"호주 A리그 {season} {r}위/{n}팀"   # 기존 자료(오스카 웨스턴 시드니 2016-17) 형식
    if lg in ("IND1", "IND1W"): return f"인도 슈퍼리그 {season} {r}위/{n}팀 (Indian Super League, 정규 리그 최종 순위)"
    if lg in EU_LG:
        pre = EU_LG[lg]; n0 = _LRA["ERA"]["teams"](pre, int(season[:4]) + 1)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    if lg in OTH:
        head, desc = OTH[lg]
        if lg == "BE1": sys.exit("벨기에 표는 플레이오프 뒤 순위 확인 필요 " + nm)
        return f"{head} {season} {r}위/{n}팀 ({desc})"
    return None
def penalty_fix(lv, o):
    """감점 시즌이면 경기장 순위로."""
    head = lv.split(" (")[0]; mm = re.match(r"^(.*?) (\d+)위(/(\d+)팀)?", head)
    if not mm: return lv
    for c in PEN:
        line = re.sub(r"\s*\[\d+팀\]$", "", c["line"])
        if line == mm.group(1) and (key(c["team"]) == key(o) or same_team(c["team"], o)) and int(mm.group(2)) == c["official"]:
            new = f"{mm.group(1)} {c['onfield']}위" + (mm.group(3) or "")
            rest = lv[len(head):]
            if rest.startswith(" ("): return new + " (감점 전 순위; " + rest[2:]
            return new + " (감점 전 순위)"
    return lv

def eu(d, cut="08-01"):
    y = int(d[:4]); s_ = y if d[5:] >= cut else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
CAL_CLUBS = {"623", "3183", "17276"}   # 뉴욕 레드불스·상하이 선화·항저우 뤼청: 달력 연도
def cal_season(d):   # 달력 연도 리그 상대가 유럽 대회에 나온 경우: 4월 전(새 시즌 개막 전)이면 끝난 앞 해
    y, m = int(d[:4]), int(d[5:7])
    return str(y if m >= 4 else y - 1)
SEASON_OVR = {}
def seasons_for(cid, d, o, g):
    if g["gameId"] in SEASON_OVR: return [SEASON_OVR[g["gameId"]]]
    if cid in ("CLQ", "UEFA", "EL", "ELQ"): return [eu(d), cal_season(d)]
    if g["club_id"] in CAL_CLUBS and cid != "CCL": return [d[:4]]
    return [eu(d)]
DOM = {"1028": ["GB1", "EFD2", "GB2", "ENSD", "GB3", "W4", "GB4", "W5"], "29": ["GB1", "GB2", "GB3", "GB4", "W4", "W5"],
       "623": ["MLSP"], "3183": ["CSLP", "CHN2"], "17276": ["CSLP", "CHN2"], "25580": ["AUSP", "AUS1"], "60816": ["IND1", "IND1W"]}
def lg_cands(cid, d, o, g):
    ss = seasons_for(cid, d, o, g)
    doms = DOM[g["club_id"]] if cid not in ("CLQ", "UEFA", "EL", "ELQ") else list(EU_LG) + list(OTH)
    return [(lg, s_) for lg in doms for s_ in ss]

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv
def man(o, s, lv): MAN[(key(o), s)] = lv
# 2014.8.26 북중미 챔스 조별 CD FAS: 엘살바도르 1부 2014-15 아페르투라(2014.7~12, 경기 날짜에 진행 중이던 단계) 최종 3위/10팀(FotMob 표 '2014/2015 - Apertura')
SEASON_OVR["2483866"] = "2014-15"
man("CD FAS", "2014-15", "엘살바도르 1부 2014-15 3위/10팀 (Primera División de El Salvador, 경기 날짜에 진행 중이던 아페르투라 2014 최종 순위, 리그 수준 추정)")
# 2008.2.21 UEFA컵 32강 브란: 노르웨이 2008 시즌 개막(4월) 전 경기 → 끝난 2007 시즌 최종 1위/14팀(우승; TM 표 NO1 2007)
SEASON_OVR["88955"] = "2007"; SEASON_OVR["88410"] = "2007"
FORCE = {}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []; RECALC = []
def opp_elo(o, d, cid, g):
    e, lv = opp_elo0(o, d, cid, g)
    if lv != "?":
        lv2 = penalty_fix(lv, o)
        if lv2 != lv: PENFIX.append((d, o, lv, lv2)); lv = lv2
        if _LRA["parse"](lv, d) or re.search(" 순위 없음", lv):
            v = lv_value(lv, d, o)
            if v != e: RECALC.append((d, o, e, v, lv))
            e = v
    return e, lv
PENFIX = []
def opp_elo0(o, d, cid, g):
    if g["gameId"] in FORCE:
        lv = FORCE[g["gameId"]]; e = lv_value(lv, d); ELO_SRC["직접 라벨"] += 1
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
            lv = MAN[(k, s)]; e = lv_value(lv, d); ELO_SRC["직접 라벨(순위표 밖)"] += 1
            ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
            return e, lv
    for lg, s in lg_cands(cid, d, o, g):
        t = RANKS.get((lg, s), {})
        hit = t.get(k)
        if not hit:
            c = [v for kk, v in t.items() if toks(kk) and toks(kk) & toks(o)]
            if len(c) == 1: hit = c[0]
        if hit:
            lv = make_label(lg, s, hit)
            if lv:
                e = lv_value(lv, d); ELO_SRC["순위표 → 라벨"] += 1
                ELO_LOG[(o, d)] = ("model", e, lv, hit[2]); NEW_TS[(o, s)] = (e, lv); return e, lv
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
    print("RECALC"); [print("  ", x, ELO_LOG.get((x[1], x[0]), ("?",))[0]) for x in RECALC]; print("PENFIX", PENFIX); print("MAP_ADD", MAP_ADD)
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME or gid.startswith("X"): continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["sq_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "penalty" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))
FM_N = sum(1 for gid in EVS if gid in G and gid in FME and any(e["scorer_id"] == ME for e in EVS[gid]))

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
JRE = re.compile(r"Cahill|케이힐")
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Tim Cahill|케이힐", str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(케이힐 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("케이힐 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) if G_BYDATE.get(r[9]) in EXACT_DOM else same_team(x[1], r[1])):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm[1], m[1]) and mm[2] != m[2] and (key(mm[1]) == key(m[1]) or G_BYDATE.get(m[0]) not in EXACT_DOM):
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 케이힐 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
# 뉴욕 레드불스 동료(앙리·주니뉴) 출전 날짜 대조: 같은 상대와 하루 차이 날짜가 있으면 표시
for b in ("hen.js", "jun.js"):
    if b not in OTHERS: continue
    od = {(mm[0], key(mm[1])) for mm in OTHERS[b][1]}
    for m in M:
        if m[0] >= "2012-07" and m[0] < "2015":
            import datetime as _dt
            dd = _dt.date.fromisoformat(m[0])
            for k_ in (-1, 1):
                if ((dd + _dt.timedelta(days=k_)).isoformat(), key(m[1])) in od and (m[0], key(m[1])) not in od:
                    CROSS.append(("동료 출전 날짜 하루 차이", b, m[0], m[1]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("milct", "2004-07-23", "밀월", "밀월", "1997~2004"), ("evect", "2012-07-26", "에버턴", "에버턴", "2004~2012"),
         ("nyct", "2015-02-03", "뉴욕 레드불스", "뉴욕 RB", "2012~2014"), ("shsct", "2016-02-21", "상하이 선화", "상하이 선화", "2015"),
         ("hzct", "2016-08-11", "항저우 뤼청", "항저우", "2016"), ("mcct", "2018-01-29", "멜버른 시티", "멜버른 시티", "2016~2017"),
         ("milct", "2018-08-31", "밀월", "밀월", "2018"), ("jmct", None, "잠셰드푸르 FC", "잠셰드푸르", "2018~2019")]
TM_CLUB = {"1028": "milct", "29": "evect", "623": "nyct", "3183": "shsct", "17276": "hzct", "25580": "mcct", "60816": "jmct"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
def season_of(d, club):
    if club in ("nyct", "shsct", "hzct"): return d[:4]
    return eu(d)
STINTS = [("밀월(1997~2004)", "2004-07-23"), ("에버턴", "2012-07-26"), ("뉴욕 레드불스", "2015-02-03"), ("상하이 선화", "2016-02-21"),
          ("항저우 뤼청", "2016-08-11"), ("멜버른 시티", "2018-01-29"), ("밀월(2018)", "2018-08-31"), ("잠셰드푸르", "9999")]
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
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A)
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    print("FM only", FM_ONLY)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_CMP)
    print("SCORE_MISMATCH", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("dates changed", len(DATE_LOG))
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("RECALC", len(RECALC)); print("PENFIX", PENFIX); print("MAP_ADD", MAP_ADD)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_cahill.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl", "mlp", "lcg", "lck", "ccc"]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const CAH_E={J(E)};\nconst CAH_M={J(M)};\nconst CAH_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "points_map_add": {f"{h}|{o}": v for (h, o), v in MAP_ADD.items()}, "penalty_label_fix": PENFIX,
               "date_changes": DATE_LOG, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
