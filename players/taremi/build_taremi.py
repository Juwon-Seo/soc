#!/usr/bin/env python3
"""메흐디 타레미 (Mehdi Taremi, Transfermarkt 307058): raw/ -> taremi.json + players/taremi/tar.js (판정 근거는 judgments.md)

  python3 players/taremi/build_taremi.py [--out <data 폴더>]   # 파일 쓰기(기본 players/taremi/tar.js; 스크래치 복사본 검증 때 --out <복사본>/src/data)
  python3 players/taremi/build_taremi.py --debug               # Elo 출처 로그만 출력
  python3 players/taremi/build_taremi.py --stat                # 요약·판정·동료 대조

미토마 build 스크립트(같은 수집 형식)를 바탕으로 함. 순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의
parse()/value()로 라벨에서 계산(v1.226 규칙). 같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이
elo/opponent_elo_by_team_season.csv에 있으면 그 값. 스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.environ.get("SOC_ELO") or os.path.join(ROOT, "elo")   # 새로 만든 통합표 폴더를 쓰려면 SOC_ELO=<폴더>
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "tar.js")
OUT_JSON = os.path.join(HERE, "taremi.json")
ME = "307058"
ME_KO = "메흐디 타레미"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")   # 클럽 공식 경기 496개(Transfermarkt played)
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
FME_BYM = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FME[r["tm_gameId"]].append(r); FME_BYM[r["fotmob_matchId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["status"] == "OK"}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- Transfermarkt에 없는 경기(다른 출처 2곳으로 확인)
# (가짜 gameId, 날짜, 대회 id, 라운드, 클럽 id, 클럽, 상대, 상대 id, 홈/원정, 출전 분, gameState)
EXTRA = [
    # 카타르컵(왕세자컵) 2018 준결승 알두하일 6-1 알가라파: 카타르 스타스 리그 공식 경기 보고서(Analyticom COMET PDF, 선발 9번 Mehdi Alireza Taremi,
    # 교체 없음, 90+1분 PK 골 6:1) + Gulf Times·QSL 기사. Transfermarkt는 'not in squad'(4092016)로 적음. 영어·페르시아어 위키백과 2017-18 '기타 1경기 1골'.
    ("x4092016", "2018-04-22", "QUC1", "Semi-Finals", "6297", "Al-Gharafa SC", "Al-Duhail SC", "26091", "A", 90, "regularly_terminated"),
    # UAE 리그컵(ADIB Cup) 2026-27 리그 단계: FotMob(경기·선수 기록)에만 있고 Transfermarkt 선수 경기 성적에 없음
    ("x1000020525", "2026-09-19", "UAELC", "1. Matchday", "16214", "Al-Wasl SC", "Al-Ain FC", "1121", "H", 77, "regularly_terminated"),
    ("x1000020534", "2026-10-02", "UAELC", "2. Matchday", "16214", "Al-Wasl SC", "Kalba FC", "38040", "H", 9, "regularly_terminated"),
    ("x1000021970", "2026-10-08", "UAELC", "3. Matchday", "16214", "Al-Wasl SC", "Khor Fakkan SSC", "0", "A", 90, "regularly_terminated"),
    ("x1000022720", "2026-11-14", "UAELC", "4. Matchday", "16214", "Al-Wasl SC", "Al-Nasr SC (UAE)", "0", "H", 85, "regularly_terminated"),
]
for gid, d, cid, rnd, clid, club, op, opid, ven, mins_, gs in EXTRA:
    G[gid] = {"gameId": gid, "date_local_tz_conv": d, "competitionId": cid, "round": rnd, "club_id": clid, "club": club, "opponent": op,
              "opponent_id": opid, "venue": ven, "playedMinutes": str(mins_), "gameState": gs, "goals": "0", "penGoals": "0", "date_local_schedule": d}
    MI[gid] = {"home_id": clid if ven == "H" else opid, "away_id": opid if ven == "H" else clid, "final": "", "other_leg_id": "", "other_leg_score": "", "round_report": rnd}
GAMES = list(G.values())

# ---------------------------------------------------------------- 날짜
# TM API 경기 시각(UTC)을 경기장 시간대로 바꾼 현지 날짜. 세 경기는 다른 출처로 고침:
DATE_FIX = {
    "2895736": "2017-09-07",   # 고스타레시 풀라드-페르세폴리스(5라운드): TM 2017-08-25, FotMob·영어 위키백과(2017-18 페르세폴리스 시즌, iranleague.ir 경기 13405)·Tasnim '목요일' = 2017.9.7
    "2536240": "2015-04-26",   # 사이파-페르세폴리스(27라운드): TM 4.25, FotMob 4.26 13:00 UTC, 결과 데이터베이스 4.26 (영어 위키백과는 4.27)
    "2636059": "2015-11-30",   # 나프트 테헤란-페르세폴리스: TM 11.29, FotMob·영어 위키백과(2015-16 페르세폴리스 시즌) 11.30
}
DATE_LOG = []
LD = {}
for gid, g in G.items():
    LD[gid] = DATE_FIX.get(gid, g["date_local_tz_conv"])
    if LD[gid] != g["date_local_tz_conv"]: DATE_LOG.append((gid, g["date_local_tz_conv"], LD[gid], g["club"], g["opponent"]))
def ldate(g): return LD[g["gameId"]]
OPP_NAME = {"2328099": None}
def opp(g):
    return re.sub(r"\s*\(\s*-\s*\d{4}\)|\s*\(\d{4}-\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IRN1", "IRN2", "QSL", "PO1", "IT1", "GR1", "POGR", "UAE1"}
CUPS = {"IRNP", "QEC1", "QUC1", "POPO", "POCP", "CIT", "GRP", "UAEP", "UAELC"}
SUPER = {"IRSC", "POSU", "GRSC"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "df"
    if cid == "SCI": return "df" if r.startswith("final") else "dsf"   # 수페르코파 이탈리아나 4팀(2024-25): 준결승 dsf, 결승 df
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("AFCL", "ACLE", "ACLQ"):
        if r.startswith("quarter"): return "aclk"
        if r.startswith("semi"): return "aclsf"
        return "acl"   # 조별·리그 단계·16강, 예선 플레이오프(스네이더르 같은 경기 선례 'acl')
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16") or r.startswith("intermediate"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g):
    return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r): return 0   # 조별·리그 단계(챔스 리그 페이즈, ACL 엘리트 리그 단계, 타사 다 리가 조별, 그리스컵 리그 단계, UAE 리그컵 리그 단계)
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid == "AFCL": return (1, 1)                       # AFC 대회 2022 시즌까지 원정 다득점·연장
    if cid in ("CL", "EL"): return (1 if d < "2021-07-01" else 0, 1)
    if cid == "POPO": return (1 if d < "2021-07-01" else 0, 1)   # 타사 드 포르투갈 준결승: 2020-21까지 원정 다득점(브루누 페르난드스·팔카오 선례), 그 뒤 없음(교케레스 선례)
    if cid == "CIT": return (0, 1)                        # 코파 이탈리아 2022-23부터 원정 다득점 없음, 2차전 연장
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
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"
def a_key(gid, minute): return f"{gid}|{minute}"
# 2014.8 이후 TM 도움 중 FotMob(경기 이벤트·선수 경기 목록)이 같이 적지 않은 것: 다른 독립 출처 2곳이 확인한 것만 넣음(근거는 judgments.md)
A_CHECK = {
 "4195834|34": (True, "A Bola 경기 기사(34분 타레미가 대각선으로 움직여 페페와 연결)·Lusa 기사(DN 게재: 타레미의 가슴 패스 도움으로 페페가 박스 밖 슈팅)"),
 "3621465|34": (False, "경기 기사(Lusa·Observador 등)에 도움자 언급 없음 — 스로인 뒤 흐른 공이라는 서술만"),
 "3500048|88": (False, "Record 중계·기사에 에바닐송 동점골 도움자 없음"),
 "4665078|59": (False, "집계 사이트 1곳(sporticos)만 타레미 도움, 기사 확인 못 함"),
 "2823337|4": (False, "ESPN 1곳만 타레미 도움(IANS/신화 기사는 도움자 없음)"),
 "3126032|52": (False, "카타르 스타스 리그 공식 기사 1곳만('스네이더르 골은 타레미 도움'); 다른 독립 출처 못 찾음(스네이더르 자료와 같은 기준)"),
 "2513015|72": (False, "영어 위키백과·Tasnim 기사에 도움자 없음"),
}
# 그 밖의 2014.8 이후 TM 단독 도움(이란·카타르·AFC 대회 등 FotMob에 도움자 자료가 없는 경기)은 경기 기사를 찾지 못해 모두 뺌(기본값)
DEFAULT_REJECT = "2014.8 이후 Transfermarkt 단독(FotMob 경기 이벤트에 도움자 자료 없음, 다른 출처 2곳 못 찾음)"
ADD_A = []
# Transfermarkt에 없는 골(다른 출처 2곳): (gid, 분, 표시 분, gf, ga, pk, 근거)
ADD_G = [
    ("3076512", 87, 0, 0, 2, 0, "FotMob 경기 이벤트 87분(1-2) + 카타르 스타스 리그 공식 기사·The Peninsula('87분 타레미 만회 골, 바이스 크로스'); Transfermarkt 리포트는 4골 중 2골만 적음"),
    ("3677053", 79, 0, 4, 2, 0, "Eurosport/TNT Sports 경기 기록 79분, The Peninsula·카타르축구협회 기사('다섯 번째 골', Peninsula는 추가시간으로 적음); Transfermarkt는 선수 경기 성적에 1골 1도움만 있고 경기 리포트 없음. 앞선 골: 하템 27·가네히 31·60·알라엘딘 45+7, 알코르 바제라 38·65(Eurosport) → 골 전 4-2"),
    ("x4092016", 91, "90+1", 0, 6, 1, "카타르 스타스 리그 공식 경기 보고서(득점 순서 1:0…6:0, 6:1 9번 90+1 PK)·Gulf Times·위키백과 2018 카타르컵"),
    ("x1000020525", 41, 0, 0, 2, 1, "FotMob 경기 이벤트 41분 PK(0-2 → 1-2) + Al Bayan 기사(39분 PK, 0-2에서 만회); 분은 FotMob"),
    ("x1000021970", 77, 0, 0, 1, 0, "FotMob 경기 이벤트 77분(1-1) + Gulf Today 기사(77분 헤더 동점골)"),
]
A_STATUS = []
def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())
def same_scorer(a, b):
    ta, tb = norm(a).split(), norm(b).split()
    return bool(ta and tb and ta[-1] == tb[-1])
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["sq_assist"] == "1" and f["pen_shootout_event"] != "True" and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])): return True
    return False
def fm_pm_assists(gid):
    m = FMMAP.get(gid)
    if m and m["fotmob_matchId"] in FMPM: return int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
    return None
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
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "뺌: " + DEFAULT_REJECT))
    return "2014.8 이후 단일 출처(확인 못 함)"

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
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("본인 자책골(골 아님)", ldate(g), opp(g), e["minute"])); continue
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
            if e["goal_desc"] == "Penalty rebound": judg.append(("PK 리바운드 골(PK 아님)", ldate(g), opp(g), e["minute"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))
for gid, mi, dm, gf, ga, pk, why in ADD_G:
    raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, "added"))
    judg.append(("골 추가(Transfermarkt 리포트에 없음)", ldate(G[gid]), opp(G[gid]), mi, why))
# 3677053 아미르컵 알코르전: TM 선수 경기 성적 도움 1(경기 리포트 없음, 득점자 모름) → 2014.8 이후 단일 출처라 뺌
judg.append(("도움 제외", "2019-04-26", "Al-Khor SC", "?", "?", "Transfermarkt 선수 경기 성적 도움 1, 경기 리포트·다른 출처 없음(득점자·시각 모름)"))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["sq_assist"] == "1" and f["pen_shootout_event"] != "True":
            mi = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(e["assist_id"] == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, mi, f["scorer"]))
# FotMob 단독 도움 1개(3212646 2020.6.30 브라가전 35분 누누 산투스): Observador 경기 기사는 이 골 도움을 젤송 달라로 적음 → 넣지 않음
PM_ONLY = []
for gid, m in FMMAP.items():
    if gid in G and m["fotmob_matchId"] in FMPM:
        pm = int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
        tm = sum(1 for e in EVS.get(gid, []) if e["assist_id"] == ME and e["scorer_id"] != ME)
        if pm > tm: PM_ONLY.append((ldate(G[gid]), gid, opp(G[gid]), pm, tm))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
ADDG_IDS = {x[0] for x in ADD_G}
for gid, g in G.items():
    exp = (int(g["goals"] or 0) if gid in EVS else 0) + sum(1 for x in ADD_G if x[0] == gid)   # 3677053은 TM 리포트 없음(선수 성적 1골 = 추가한 1골)
    if cnt_[(gid, "g")] != exp: sys.exit("골 수 불일치 " + gid)
    if gid not in ADDG_IDS and int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

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
        if ME_KO in r["선수"].split("·") and r["선수"] == ME_KO: continue   # 이 선수만 쓴 팀-시즌만 건너뜀(오스카 빌드 수정과 같음)
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "tar.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "ec", "foot", "ball", "atletico", "calcio", "sport", "cd", "ud", "sv", "as", "ss", "fk", "bv", "athletic", "milan", "inter", "madrid",
        "nacional", "vitoria", "guimaraes", "setubal", "bayer", "olympiacos", "panathinaikos", "rio", "ave", "al", "qatar", "rayyan", "esfahan",
        "tehran", "naft", "foolad", "esteghlal", "khuzestan", "persepolis", "hormozgan", "tabriz", "sazi", "ahli", "sfc", "saudi", "uae", "athens", "sad", "saint", "red", "star"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
ASIA = {"IRN1", "IRN2", "IRNP", "IRSC", "QSL", "QEC1", "QUC1", "AFCL", "ACLQ", "ACLE", "UAE1", "UAEP", "UAELC"}
def same_match(o, d, cid):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    if not cand and cid not in ASIA:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
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

# 순위표: (리그, 시즌) -> {팀 key: (순위, 팀 수, 표 이름, 출처)}
RANKS = collections.defaultdict(dict)
def addr(lg, se, r, n, nm, src):
    RANKS[(lg, se)].setdefault(key(nm), (int(r), int(n), nm, src))
FM_LG = {"523 Persian Gulf": "IRN1", "535 Qatar Stars League": "QSL", "538 Pro League": "UAE1", "536 Saudi Pro League": "SA1", "540 Superliga": "UZ1",
         "61 Liga Portugal": "PO1", "55 Serie A": "IT1", "524 Stars League": "IRQ1", "225 Premier League": "KAZ1"}
with open(os.path.join(RAW, "ranks_fotmob.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] not in FM_LG: continue
        se = p[1] if "-" not in p[1] else p[1][:5] + p[1][7:9]
        addr(FM_LG[p[0]], se, p[2], p[3], p[4], "FotMob")
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        se = p[1].split(" ")[0]
        if p[0] == "QSL" and se == "2017-18": continue   # TM 표는 4·5위 순서가 틀림(QSL 공식 기사: 알가라파 4위, 움 살랄 5위) — 기존 표 값 사용
        addr(p[0], se, p[2], p[3], p[4], "TM")
WIKI_LG = {"Azadegan_League": "IRN2", "Iran_Pro_League": "IRN1", "Persian_Gulf_Pro_League": "IRN1", "Persian_Gulf_Cup": "IRN1", "Qatar_Stars_League": "QSL", "Campeonato_de_Portugal": "PT3"}
with open(os.path.join(RAW, "ranks_wiki.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 6 or p[0] == "file": continue
        m_ = re.match(r"en_(\d{4}-\d{2})_(.*)\.html", p[0])
        lg = WIKI_LG.get(m_.group(2))
        if not lg: continue
        nm = re.sub(r"\s*\((?:[A-Z, ]+)\)\s*$", "", p[5]).strip()
        grp = p[2].split(">")[-1].strip()
        se = m_.group(1)
        if lg in ("IRN2", "PT3"):
            RANKS[(lg, se)].setdefault(key(nm), (int(p[3]), int(p[4]), nm, "en.wiki " + grp))
        else:
            addr(lg, se, p[3], p[4], nm, "en.wiki")
# 그리스 1부 2025-26 최종 순위(플레이오프 뒤): 챔피언십 그룹 1~4, 컨퍼런스리그 그룹 5~8, 강등 그룹 9~14(FotMob 135)
GRP_ORDER = {"Championship Group": 0, "Conference League Group": 4, "Relegation Group": 8}
RANKS[("GR1", "2025-26")].clear()   # TM 표(정규 시즌 순서)는 쓰지 않음
with open(os.path.join(RAW, "ranks_fotmob.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) >= 5 and p[0].startswith("135 Super League 1 / ") and p[0].split(" / ")[1] in GRP_ORDER:
            RANKS[("GR1", "2025-26")][key(p[4])] = (GRP_ORDER[p[0].split(" / ")[1]] + int(p[2]), 14, p[4], "FotMob 플레이오프 뒤")

# TM 이름 → 순위표 이름(이름 표기만 다른 것; raw/ranks_name_candidates.csv)
RNAME = {"Naft Novin Tehran": ["Naft Tehran"], "Sabaye Qom": ["Saba Qom"], "Zob Ahan Esfahan": ["Zob Ahan"], "Siah Jamegan Khorasan FC": ["Siah Jamegan"],
         "Machine Sazi Tabriz": ["Machine Sazi FC"], "Malavan Bandar Anzali": ["Malavan"], "Yazd Louleh FC": ["Yazd Loleh"], "Esteghlal FC": ["Esteghlal"],
         "Esteghlal Khuzestan": ["Esteghlal Khuzestan"], "Esteghlal Ahvaz": ["Esteghlal Ahvaz"], "Foolad FC": ["Foolad Khuzestan", "Foolad"], "Sepahan FC": ["Sepahan"],
         "Saipa FC": ["Saipa"], "Rah Ahan FC": ["Rah Ahan"], "Tractor FC": ["Tractor", "Tractor Sazi FC"], "Paykan FC": ["Paykan"], "Sanat Naft FC": ["Sanat Naft Abadan", "Sanat Naft FC"],
         "Gostaresh Foolad FC": ["Gostaresh Foolad FC"], "Shahr Khodrou FC": ["Shahr Khodrou FC"], "Persepolis Shomal": ["Persepolis Shomal"], "Parseh Tehran FC": ["Parseh Tehran"],
         "Aluminium Hormozgan": ["Aluminium Hormozgan"], "Mes Rafsanjan": ["Mes Rafsanjan"], "Naft va Gaz Gachsaran": ["Naft va Gaz Gachsaran"],
         "Badr Hormozgan FC": ["Albadr Bandar Kong"], "Damash Gilan FC": ["Damash"],
         "Al-Kharaitiyat SC": ["Al-Khuraitiat", "Al Kharaitiyat"], "Al-Shahania SC": ["Al-Shahaniya"], "Al-Sadd SC": ["Al-Sadd"], "Al-Rayyan SC": ["Al-Rayyan"], "Al-Arabi SC": ["Al-Arabi"],
         "Al-Ahli SC": ["Al-Ahli"], "Al-Khor SC": ["Al-Khor"], "Al-Sailiya SC": ["Al-Sailiya"], "Al-Duhail SC": ["Al-Duhail SC", "Al Duhail", "Lekhwiya"], "FC Alverca": ["Alverca"], "GD Fabril Barreiro": ["Fabril Barreiro"], "Umm Salal SC": ["Umm Salal"],
         "Al-Ain FC": ["Al-Ain"], "FC Baniyas": ["Baniyas"], "Hatta Club": ["Hatta"], "Kalba FC": ["Kalba FC", "Kalba"], "Khor Fakkan SSC": ["Khorfakkan"], "Al-Nasr SC (UAE)": ["Al-Nasr SC", "Al Nasr"],
         "Al-Quwa Al-Jawiya": ["Al Quwa Al Jawiya"], "Kairat Almaty": ["Kairat Almaty"], "Pakhtakor Tashkent": ["Pakhtakor"], "Al-Ahli SFC": ["Al-Ahli"], "Al-Nassr FC": ["Al-Nassr"],
         "Al-Hilal SFC": ["Al-Hilal"], "Al-Wahda FC": ["Al-Wahda"], "Al-Jazira Club": ["Al-Jazira"],
         "Atromitos Athens": ["Atromitos"], "Asteras Aktor": ["Asteras Tripolis"], "Kifisia FC": ["Kifisia FC"], "Panserraikos": ["Panserraikos FC"], "OFI Crete": ["OFI Crete"],
         "Aris Thessaloniki": ["Aris Thessaloniki"], "AEK Athens": ["AEK Athens"], "Panathinaikos": ["Panathinaikos"]}

IRN_NAME = {"IRN1": "Persian Gulf Pro League"}
EU_LG = {"FR1": "리그1", "ES1": "라리가", "L1": "분데스리가", "GB1": "프리미어리그", "PO1": "포르투갈 1부", "IT1": "세리에A", "NL1": "에레디비시"}
def make_label(lg, season, v):
    r, n, nm, src = v
    if lg == "IRN1": return f"이란 1부 {season} {r}위/{n}팀 (Persian Gulf Pro League)"
    if lg == "IRN2":
        grp = re.search(r"Group ([AB])", src)
        return f"이란 2부 {season} {r}위/{n}팀 (Azadegan League" + (f" {grp.group(1)}조(두 조 리그)" if grp else "") + ", 리그 수준 추정)"
    if lg == "QSL": return f"카타르 1부 {season} {r}위/{n}팀 (Qatar Stars League)"
    if lg == "UAE1": return f"UAE 1부 {season} {r}위/{n}팀 (UAE Pro League" + (", 2026년 11월 현재 순위)" if season == "2026-27" else ")")
    if lg == "SA1": return f"사우디 1부 {season} {r}위/{n}팀 (Saudi Pro League)"
    if lg == "UZ1": return f"우즈베키스탄 1부 {season} {r}위/{n}팀 (Uzbekistan Super League)"
    if lg == "IRQ1": return f"이라크 1부 {season} {r}위/{n}팀 (Iraq Stars League, 2026년 11월 현재 순위)"
    if lg == "KAZ1": return f"카자흐스탄 1부 {season} {r}위/{n}팀 (Kazakhstan Premier League)"
    if lg == "GR1": return f"그리스 1부 {season} {r}위/{n}팀 (Super League Greece, 플레이오프 뒤 최종 순위)"
    if lg == "PO2": return f"포르투갈 2부 {season} {r}위/{n}팀 (Liga Portugal 2)"
    if lg == "PT3": return f"포르투갈 3부 {season} {r}위/{n}팀 (Campeonato de Portugal Série {src.split()[-1]}, 리그 수준 추정)"
    if lg in EU_LG:
        pre = EU_LG[lg]; n0 = _LRA["ERA"]["teams"](pre, int(season[:4]) + 1)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    return None

# 시즌(상대 순위용): 클럽 시즌 구분과 같음(페르세폴리스·포르투 7월 10일, 나머지 8월 1일). 달력 연도 리그(우즈베키스탄·카자흐스탄)는 연도.
def club_season(d, clid):
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    if clid in ("6079", "720"): s_ = y if (m, dd) >= (7, 10) else y - 1
    else: s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
LGS = {"6079": ["IRN1"], "17575": ["IRN1"], "42187": ["IRN2", "IRN1"], "6297": ["QSL"], "2425": ["PO1", "PO2", "PT3"], "720": ["PO1", "PO2", "PT3"],
       "46": ["IT1"], "683": ["GR1"], "16214": ["UAE1"]}
CONT_LG = ["SA1", "UAE1", "QSL", "IRN1", "UZ1", "IRQ1", "KAZ1"] + list(EU_LG)
SEASON_OVR = {"3887195": "2021-22"}   # 2022.7.30 수페르타사 톤델라: 2022-23 2부 리그 개막(8월) 전 경기 → 끝난 2021-22 시즌(1부 17위, 강등)
def seasons_for(cid, d, o, g):
    if g["gameId"] in SEASON_OVR: return [SEASON_OVR[g["gameId"]]]
    return [club_season(d, g["club_id"])]
def lg_cands(cid, d, o, g):
    ss = seasons_for(cid, d, o, g)
    doms = CONT_LG if cid in ("AFCL", "ACLQ", "ACLE", "CL", "EL") else LGS[g["club_id"]]
    out = [(lg, s_) for lg in doms for s_ in ss]
    if cid in ("AFCL", "ACLQ", "ACLE", "CL"): out += [(lg, d[:4]) for lg in ("UZ1", "KAZ1")]
    return out

MAN = {}
def man(o, s, lv): MAN[(key(o), s)] = lv
exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())   # 순위표 밖 상대 라벨(man(...) 호출)
FORCE = {}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def opp_elo(o, d, cid, g):
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
    names = [k] + [key(x) for x in RNAME.get(o, [])]
    for lg, s in lg_cands(cid, d, o, g):
        t = RANKS.get((lg, s), {})
        for nk in names:
            if nk in t:
                lv = make_label(lg, s, t[nk])
                if lv:
                    e = lv_value(lv, d); ELO_SRC["순위표 → 라벨"] += 1
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
JRE = re.compile(r"Taremi|타레미")
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and JRE.search(str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(타레미 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("타레미 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and key(x[1]) == key(r[1]) or (x[9] == r[9] and G_BYDATE.get(r[9]) not in ASIA and same_team(x[1], r[1])):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or (G_BYDATE.get(m[0]) not in ASIA and same_team(mm[1], m[1]))) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[3] != "?" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and key(x[1]) == key(j[2]):
                    CROSS.append(("TM 타레미 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("ijvta", "2010-07-01", "이란자반 부셰르", "이란자반", "2009~2010"), ("shbta", "2012-02-01", "샤힌 부셰르", "샤힌", "2010~2012"),
         ("ijvta", "2014-07-01", "이란자반 부셰르", "이란자반", "2013~2014"), ("perta", "2018-01-12", "페르세폴리스", "페르세폴리스", "2014~2018"),
         ("ghata", "2019-07-23", "알가라파", "알가라파", "2018~2019"), ("riota", "2020-08-31", "히우 아브", "히우 아브", "2019~2020"),
         ("porta", "2024-07-13", "포르투", "포르투", "2020~2024"), ("intta", "2025-08-31", "인테르나치오날레", "인테르", "2024~2025"),
         ("olyta", "2026-08-22", "올림피아코스", "올림피아코스", "2025~2026"), ("wasta", None, "알와슬", "알와슬", "2026~")]
TM_CLUB = {"42187": "ijvta", "17575": "shbta", "6079": "perta", "6297": "ghata", "2425": "riota", "720": "porta", "46": "intta", "683": "olyta", "16214": "wasta"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
SJUL10 = ("perta", "porta")
def season_of(d, club):
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    if club in SJUL10: s_ = y if (m, dd) >= (7, 10) else y - 1
    else: s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("이란자반", "2010-07-01"), ("샤힌 부셰르", "2012-02-01"), ("이란자반(복귀)", "2014-07-01"), ("페르세폴리스", "2018-01-12"), ("알가라파", "2019-07-23"),
          ("히우 아브", "2020-08-31"), ("포르투", "2024-07-13"), ("인테르", "2025-08-31"), ("올림피아코스", "2026-08-22"), ("알와슬", "9999")]
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
    print("FM only", FM_ONLY); print("PM only", PM_ONLY)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G, FM_CMP)
    print("SCORE_MISMATCH", SCORE_MISMATCH)
    print(sorted(collections.Counter(season_of(m[0], club_of(m[0])) for m in M).items()))
    print("dates changed", DATE_LOG)
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_taremi.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl", "mlp", "lcg", "lck", "clg", "cl16"]:
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
    if m and r[4] > m[3] + 0 and False: pass
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const TAR_E={J(E)};\nconst TAR_M={J(M)};\nconst TAR_NOTE={J(NOTE)};\n")
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
