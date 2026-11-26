#!/usr/bin/env python3
"""나카무라 슌스케 (中村俊輔, Shunsuke Nakamura, Transfermarkt 6069): raw/ + jleague_official.json -> nakamura.json + players/nakamura/nks.js
(판정 근거는 judgments.md)

  SOC_ROOT=<스크래치 복사본> python3 players/nakamura/build_nakamura.py [--out <data 폴더>]   # 파일 쓰기(기본 players/nakamura/nks.js)
  python3 players/nakamura/build_nakamura.py --debug               # Elo 출처 로그
  python3 players/nakamura/build_nakamura.py --stat                # 요약·판정·동료 대조

오카자키 build 스크립트(같은 수집 형식)를 바탕으로 함. 순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의
parse()/value()(+ tools/league_points.py 승점·득실 모형)로 라벨에서 계산(직접 숫자를 넣지 않음).
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
1997~2002 마리노스 리그·J리그컵·챔피언십 경기는 J리그 공식 기록(data.j-league.or.jp, jleague_official.json)과 대조해
출전 분(V골 연장 4경기)·날짜(2경기)·골 시각/순서(1경기)를 공식 기록으로 고침.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "nks.js")
OUT_JSON = os.path.join(HERE, "nakamura.json")
ME = "6069"
ME_KO = "나카무라 슌스케"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")   # TM 클럽 공식 경기 765개(2군·유소년 없음)
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["status"] == "OK"}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- J리그 공식 기록(1997~2002.7 마리노스, 206경기)
JLO = json.load(open(os.path.join(HERE, "jleague_official.json"), encoding="utf-8"))
# TM 날짜가 공식 기록과 다른 경기(TM 일정·API 모두 같은 틀린 날짜, 리포트 없음): 공식 기록 날짜
DATE_FIX = {"2919268": "1999-03-27",   # J1 1st 4절 아비스파 후쿠오카 원정(TM 1999-03-17)
            "2919454": "1999-09-23"}   # J1 2nd 10절 벨마레 히라쓰카 원정(TM 1999-09-22)
LD = {gid: DATE_FIX.get(gid, g["date_local_tz_conv"]) for gid, g in G.items()}
def ldate(g): return LD[g["gameId"]]
DATE_LOG = [(gid, G[gid]["date_local_tz_conv"], d) for gid, d in DATE_FIX.items()]

# ---------------------------------------------------------------- TM에 없는 경기(경기별 출처로 출전 확인)
# 셀틱 스코틀랜드컵: TM '명단 외'/경기 없음, ESPN 경기 기록(선발·교체)·위키백과 시즌 출전 수(2006-07 5경기, 2007-08 4경기)
ADD_GAMES = [
    # gameId(가상), 날짜, 대회, 라운드, 장소, 상대, 우리-상대, 출전 분, 근거
    ("x211981", "2007-01-06", "SFA", "Third Round", "H", "Dumbarton FC", "4-0", 45,
     "ESPN 경기 기록 211981(선발, 45분 리오던과 교체); TM '명단 외'"),
    ("x212868", "2007-02-04", "SFA", "Fourth Round", "A", "Livingston FC", "4-1", 90,
     "ESPN 경기 기록 212868(선발, 교체 없음)·셀틱 위키 경기 문서 날짜 2007.2.4(TM은 2.3 '명단 외')"),
    ("x215175", "2007-04-14", "SFA", "Semi-Finals", "A", "St. Johnstone FC", "2-1", 78,
     "ESPN 경기 기록 215175(선발, 78분 그라베센과 교체); TM '명단 외'"),
    ("x232189", "2008-01-12", "SFA", "Fourth Round", "H", "Stirling Albion FC", "3-0", 75,
     "ESPN 경기 기록 232189(선발, 75분 골 뒤 오브라이언과 교체)·RSSSF 2007-08 스코틀랜드컵·RTÉ·Japan Times 경기 기사; TM 경기 목록에 없음"),
]
for gid, d, cid, rnd, ven, o, sc, mn, why in ADD_GAMES:
    G[gid] = {"gameId": gid, "date_local_tz_conv": d, "competitionId": cid, "round": rnd, "venue": ven, "opponent": o, "opponent_id": "",
              "score_club_opp": sc, "gameState": "regularly_terminated", "playedMinutes": str(mn), "goals": "1" if gid == "x232189" else "0",
              "assists": "0", "penGoals": "0", "club_id": "371", "club": "Celtic FC"}
    LD[gid] = d
    h, a = map(int, sc.split("-"))
    MI[gid] = {"home_id": "371" if ven == "H" else "", "away_id": "371" if ven == "A" else "", "final": f"{h}:{a}" if ven == "H" else f"{a}:{h}",
               "other_leg_id": "", "round_report": rnd}
# 2008.1.12 스털링 앨비언전 골(ESPN·RSSSF: 37분 페너호르 오브 헤셀링크, 70분 맥도널드, 75분 나카무라)
EVS["x232189"] = [
    {"gameId": "x232189", "minute": "37", "side": "home", "scorer": "Jan Vennegoor of Hesselink", "scorer_id": "4362", "goal_desc": "", "assist_id": "", "assist_type": "", "own_goal": "0", "penalty": "0"},
    {"gameId": "x232189", "minute": "70", "side": "home", "scorer": "Scott McDonald", "scorer_id": "13799", "goal_desc": "", "assist_id": "", "assist_type": "", "own_goal": "0", "penalty": "0"},
    {"gameId": "x232189", "minute": "75", "side": "home", "scorer": "Shunsuke Nakamura", "scorer_id": ME, "goal_desc": "", "assist_id": "", "assist_type": "", "own_goal": "0", "penalty": "0"}]
# 1999.4.3 J1 1st 5절 시미즈 원정 2-3: TM 리포트 골 목록(마쓰다 56·나카무라 59·마쓰다 66)이 공식 기록(조 쇼지 16·이토 44·나카무라 50·사와노보리 57·조 82)과 다름
#  → 공식 기록 순서·시각 사용(나카무라 50분, 골 전 1-1)
EV_FIX = {"2919276": [("16", "away", "Shoji Jo", ""), ("44", "home", "Teruyoshi Ito", ""), ("50", "away", "Shunsuke Nakamura", ME),
                      ("57", "home", "Masaaki Sawanobori", ""), ("82", "away", "Shoji Jo", "")]}
for gid, lst in EV_FIX.items():
    EVS[gid] = [{"gameId": gid, "minute": m, "side": sd, "scorer": nm, "scorer_id": sid, "goal_desc": "", "assist_id": "", "assist_type": "",
                 "own_goal": "0", "penalty": "0"} for m, sd, nm, sid in lst]

def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
# 리그: J1(1997~2002·2015~2016 스테이지 JL11/JL12 포함)·J2·세리에A·SPL·라리가 + 세리에A 잔류 플레이오프(ITPO)·J1 승강 플레이오프(J1PO)
LEAGUE = {"JAP1", "JL11", "JL12", "JAP2", "IT1", "SC1", "ES1", "ITPO", "J1PO"}
CUPS = {"JEMP", "JAPC", "CIT", "SFA", "SCP", "CDR"}   # 일왕배·J리그컵·코파 이탈리아·스코틀랜드컵·스코틀랜드 리그컵·코파 델 레이
SUPER = {"JASP"}                                      # 후지 제록스 슈퍼컵 = 국내컵 결승 비중

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "df"
    if cid == "SUNC": return "mlpf"   # J리그 챔피언십(산토리 챔피언십 2000 결승, 두 경기) = 리그 우승 결정전(멕시코 리길야·MLS 플레이오프 선례)
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        sys.exit("CL 단계 " + rnd)
    if cid == "CLQ": return "clq"
    if cid == "AFCL":
        if r.startswith("group"): return "acl"
        sys.exit("ACL 단계 " + rnd)
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
    if cid == "JAPC": return (1, 1)   # J리그컵 두 경기 라운드: 원정 다득점·연장(오카자키·미토마 선례)
    if cid in ("CL", "CLQ") and d < "2021-07-01": return (1, 1)
    if cid == "CIT" and d < "2022-07-01": return (1, 1)
    if cid == "CDR" and d < "2019-07-01": return (1, 1)
    if cid in ("SUNC", "ITPO"): return (0, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; oid = m["other_leg_id"]; club = G[gid]["club_id"]
    if not oid: sys.exit("다른 차전 없음 " + gid)
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

# ---------------------------------------------------------------- 출전(J리그 공식 기록 대조)
def jmin(s):
    s = s.replace("'", "").strip()
    if "+" in s: a, b = s.split("+"); return int(a) + int(b)
    return int(s) if s else None
def jdate(o):
    y, m, d = o[3][:8].split("/"); return f"{1900 + int(y) if int(y) > 50 else 2000 + int(y)}-{m}-{d}"
JL_BY_DATE = {}
for r in JLO:
    d = jdate(r["list"]); end = 120 if r["et"] else 90
    gm = [jmin(x[2]) for x in r["goals"] if jmin(x[2]) and jmin(x[2]) > 90]
    if r["et"] and gm: end = max(gm)   # V골(골든골)로 경기 종료
    mins = None
    if r["start"]:
        o = [e for e in r["ev"] if e[0] == "▽"]; mins = jmin(o[0][2]) if o else end
    elif r["ev"]:
        i = [e for e in r["ev"] if e[0] == "▲"]; o = [e for e in r["ev"] if e[0] == "▽"]
        mins = (jmin(o[0][2]) if o else end) - jmin(i[0][2])
    JL_BY_DATE[d] = dict(r, mins=mins, my=[jmin(x[2]) for x in r["goals"] if x[1] == "中村 俊輔"])
MIN_FIX = {}; JL_CHECK = collections.Counter(); JL_DIFF = []
for gid, g in G.items():
    d = ldate(g)
    if d >= "2002-08-01" or g["club_id"] != "3828": continue
    o = JL_BY_DATE.get(d)
    if not o:
        if g["competitionId"] != "JEMP": JL_DIFF.append(("공식 기록 없음", gid, d));
        continue
    if o["mins"] is None: sys.exit("공식 기록 출전 없음 " + gid)
    JL_CHECK["대조"] += 1
    tm = int(g["playedMinutes"])
    if abs(o["mins"] - tm) > 2:
        MIN_FIX[gid] = o["mins"]; JL_DIFF.append(("출전 분", gid, d, opp(g), tm, o["mins"], o["url"]))
    if len(o["my"]) != int(g["goals"]): sys.exit("공식 기록 골 수 다름 " + gid)
for d, o in JL_BY_DATE.items():
    if o["mins"] and not any(ldate(g) == d for g in G.values()): sys.exit("공식 기록에만 출전 " + d)
M = []
for g in sorted(G.values(), key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e.get("own_goal") == "1" or e.get("goal_desc") == "Own-goal"

def a_key(gid, minute): return f"{gid}|{minute}"
# 2014.8 이후 TM 도움 중 FotMob이 같이 적지 않은 것: TM 밖 독립 출처 2곳으로 확인한 것만 넣음(근거는 judgments.md)
A_CHECK = {
 "2818773|34": (False, "Goal.com 일본판 기사: 나카무라 코너킥의 '흘러나온 공(こぼれ球)'을 오이가 넣음 — 루즈볼이라 도움 아님(TM 공식 도움 칸 0, FotMob 도움자 없음)"),
 "2616156|88": (False, "J리그 공식 사진 설명('中村が決勝ゴールを見事にアシスト') 1곳뿐, FotMob 도움자 없음 — 다른 출처 2곳 미달(두 번째 출처가 나오면 넣을 후보)"),
 "2616136|64": (False, "사커킹 경기 기사: '64분 왼쪽 CK에 파비오 헤더'(키커 이름 없음), FotMob 도움자 없음 — 확인 못 함"),
}
ADD_A = []

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n); n = re.sub(r"[^a-z0-9 ]", " ", n)
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
    return sum(1 for e in EVS.get(gid, []) if e.get("assist_id") == ME and e["scorer_id"] != ME and fm_assist(gid, e))

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
    fa, pm = fm_assist(gid, e), fm_pm_assists(gid)
    if fa:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if pm and pm > fm_confirmed(gid) and k not in A_CHECK:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], f"TM+FotMob 선수 경기 목록(도움 {pm})")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "2014.8 이후 단일 출처(확인 못 함)"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], f"뺌: FotMob 도움자 없음(FotMob 선수 경기 목록 {pm}), 경기 기사 검색으로 다른 출처 2곳 못 찾음"))
    return "2014.8 이후 단일 출처(확인 못 함)"

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    evs = sorted(EVS[gid], key=lambda e: (int(e["minute"].split("+")[0]), int(e["minute"].split("+")[1]) if "+" in e["minute"] else 0)) if gid in EV_FIX else EVS[gid]
    for e in evs:
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e.get("assist_id") == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e.get("assist_id") == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
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
            if not any(e.get("assist_id") == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, f["time"], f["scorer"]))
PM_ONLY = []
for gid, m in FMMAP.items():
    if gid in G and m["fotmob_matchId"] in FMPM:
        pm = int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
        tm = sum(1 for e in EVS.get(gid, []) if e.get("assist_id") == ME and e["scorer_id"] != ME)
        if pm > tm: PM_ONLY.append((ldate(G[gid]), gid, opp(G[gid]), pm, tm))

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
MANUAL_ALIAS = {"hokkaido consadole sapporo": "consadole sapporo"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"].split("·") == [ME_KO]: continue   # 이 선수만 쓰는 행만 건너뜀(다른 선수와 같이 쓰는 팀-시즌 값은 유지)
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "nks.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
# 이번 회차에 함께 판정한 선수(있으면 읽기만): 같은 경기면 같은 Elo/lv
for pth in sorted(glob.glob(os.path.join(os.path.dirname(HERE), "*", "*.js"))):
    slug, fn = pth.split(os.sep)[-2:]
    if slug not in ("scholes", "yayatoure", "kamada", "leejaesung") or "src/data/" + fn in TRACKED: continue
    try: P, oe, om = load_js(pth)
    except Exception: continue
    OTHERS["players/" + slug + "/" + fn] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "fk", "vfl", "bv", "hotspur",
        "manchester", "west", "new", "borussia", "osaka", "tokyo", "yokohama", "kawasaki", "saint", "st", "dundee", "hearts", "heart", "midlothian", "sl", "bk", "mirren"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
SA_DOM = {"JAP1", "JL11", "JL12", "JAP2", "JAPC", "JEMP", "SUNC", "JASP", "J1PO", "SC1", "SFA", "SCP"}   # 이름 겹침 많은 리그: 이름 일치만
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
    h = lv.split(" (")[0]; mm = re.match(r"^(.*?) \d+위", h)
    return mm.group(1) if mm and mm.group(1) in PTS.O["seasons"] else None

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[0].startswith("#"): continue
        se = p[1].split(" ")[0]
        lg = {"JAP1": "J1", "JAP2": "J2"}.get(p[0], p[0])
        RANKS[(lg, se)][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1])
# 영어 위키백과 시즌 문서 순위표(raw/ranks_wiki.txt): J1 2015·2016은 연간 승점 순위표('Overall table'), J1 2010~2021 단일 시즌표,
# JFL·J3(일왕배 하부 리그 상대). TM 표와 겹치는 시즌은 같은지 확인.
WIKI = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks_wiki.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 6 or p[0] == "file": continue
        nm = re.sub(r"\s*\[.*?\]", "", p[5]); nm = re.sub(r"\s*\([A-Z, ]+\)$", "", nm).strip()
        WIKI[(p[0], p[1])][key(nm)] = (int(p[3]), int(p[4]), nm, p[0] + " " + p[2])
def wiki(fn, idx): return WIKI[(fn, idx)]
WIKI_CHECK = []
for yy in range(2010, 2022):
    if yy in (2015, 2016): continue
    fn = f"{yy}_J.League_Division_1.html" if yy <= 2014 else f"{yy}_J1_League.html"
    w = [v for (a, b), v in WIKI.items() if a == fn]
    if not w: continue
    w = w[0]; t = RANKS.get(("J1", str(yy)), {})
    if t:
        same = sum(1 for k, v in t.items() if k in w and w[k][0] == v[0])
        WIKI_CHECK.append((yy, same, len(t)))
    else:
        RANKS[("J1", str(yy))] = dict(w)
for yy, idx in ((2015, "7"), (2016, "7")):
    RANKS[("J1Y", str(yy))] = dict(wiki(f"{yy}_J1_League.html", idx))
for fn, idx, lg, se in (("2011_Japan_Football_League.html", "1", "JFL", "2011"), ("2012_Japan_Football_League.html", "2", "JFL", "2012"),
                        ("2013_Japan_Football_League.html", "2", "JFL", "2013"), ("2021_J3_League.html", "5", "J3", "2021"),
                        ("2014_K_League_Classic.html", "5", "KOR", "2014")):
    RANKS[(lg, se)] = dict(wiki(fn, idx))
for se, fn, idx in (("2005-06", "2005–06_Scottish_Premier_League.html", "4"), ("2006-07", "2006–07_Scottish_Premier_League.html", "5"),
                    ("2007-08", "2007–08_Scottish_Premier_League.html", "4"), ("2008-09", "2008–09_Scottish_Premier_League.html", "4")):
    # TM SPL 표는 스플릿(33라운드 뒤 상·하위 6팀 분리)을 반영하지 않은 승점순이라 영어 위키백과 최종 순위표(스플릿 뒤)를 씀
    w = wiki(fn, idx); t = RANKS[("SC1", se)]
    nw = {}
    for kt, v in t.items():
        hit = [x for x in w.values() if norm(x[2]).replace(" fc", "") == norm(v[2]).replace(" fc", "") or norm(v[2]).startswith(norm(x[2]))]
        if len(hit) != 1: sys.exit(f"SPL 이름 연결 실패 {se} {v[2]} {hit}")
        nw[kt] = (hit[0][0], hit[0][1], v[2], se + " 영어 위키백과(스플릿 뒤)")
    WIKI_CHECK.append(("SPL " + se + " TM과 같은 순위", sum(1 for k in t if t[k][0] == nw[k][0]), len(t)))
    RANKS[("SC1", se)] = nw
# J1 1997~2002 연간 종합 순위(일본어 위키백과 'YYYY年のJリーグ(ディビジョン1)' 年間総合順位; 1·2위는 챔피언십 결과,
# 2002는 두 스테이지 모두 이와타라 챔피언십 없이 연간 승점 2위가 2위). 박지성 자료(J1 2000·2002 연간)와 같은 기준.
JY = {
 "1997": ["Júbilo Iwata", "Kashima Antlers", "Yokohama F. Marinos", "Gamba Osaka", "Shimizu S-Pulse", "Yokohama Flügels", "Kashiwa Reysol", "Bellmare Hiratsuka",
          "Nagoya Grampus", "Urawa Red Diamonds", "Cerezo Osaka", "Sanfrecce Hiroshima", "JEF United Ichihara", "Kyoto Purple Sanga", "Verdy Kawasaki", "Vissel Kobe", "Avispa Fukuoka"],
 "1998": ["Kashima Antlers", "Júbilo Iwata", "Shimizu S-Pulse", "Yokohama F. Marinos", "Nagoya Grampus", "Urawa Red Diamonds", "Yokohama Flügels", "Kashiwa Reysol",
          "Cerezo Osaka", "Sanfrecce Hiroshima", "Bellmare Hiratsuka", "Verdy Kawasaki", "Kyoto Purple Sanga", "Consadole Sapporo", "Gamba Osaka", "JEF United Ichihara", "Vissel Kobe", "Avispa Fukuoka"],
 "1999": ["Júbilo Iwata", "Shimizu S-Pulse", "Kashiwa Reysol", "Nagoya Grampus", "Yokohama F. Marinos", "Cerezo Osaka", "Verdy Kawasaki", "Sanfrecce Hiroshima",
          "Kashima Antlers", "Vissel Kobe", "Gamba Osaka", "Kyoto Purple Sanga", "JEF United Ichihara", "Avispa Fukuoka", "Urawa Red Diamonds", "Bellmare Hiratsuka"],
 "2000": ["Kashima Antlers", "Yokohama F. Marinos", "Kashiwa Reysol", "Júbilo Iwata", "Cerezo Osaka", "Gamba Osaka", "FC Tokyo", "Shimizu S-Pulse",
          "Nagoya Grampus", "Verdy Kawasaki", "Sanfrecce Hiroshima", "Avispa Fukuoka", "Vissel Kobe", "JEF United Ichihara", "Kyoto Purple Sanga", "Kawasaki Frontale"],
 "2001": ["Kashima Antlers", "Júbilo Iwata", "JEF United Ichihara", "Shimizu S-Pulse", "Nagoya Grampus", "Kashiwa Reysol", "Gamba Osaka", "FC Tokyo",
          "Sanfrecce Hiroshima", "Urawa Red Diamonds", "Consadole Sapporo", "Vissel Kobe", "Yokohama F. Marinos", "Tokyo Verdy 1969", "Avispa Fukuoka", "Cerezo Osaka"],
 "2002": ["Júbilo Iwata", "Yokohama F. Marinos", "Gamba Osaka", "Kashima Antlers", "Kyoto Purple Sanga", "Nagoya Grampus", "JEF United Ichihara", "Shimizu S-Pulse",
          "FC Tokyo", "Tokyo Verdy 1969", "Urawa Red Diamonds", "Kashiwa Reysol", "Vegalta Sendai", "Vissel Kobe", "Sanfrecce Hiroshima", "Consadole Sapporo"],
}
for yy, lst in JY.items():
    RANKS[("J1Y", yy)] = {key(n): (i + 1, len(lst), n, yy + " 일본어 위키백과 年間総合順位") for i, n in enumerate(lst)}

EU_LG = {"ES1": "라리가", "IT1": "세리에A"}
def make_label(lg, season, v):
    r, n, nm, sraw = v
    if lg == "J1": return f"J1리그 {season} {r}위/{n}팀"
    if lg == "J1Y": return f"J1리그 {season} 연간 {r}위/{n}팀"
    if lg == "J2": return f"J2리그 {season} {r}위/{n}팀"
    if lg == "JFL": return f"일본 3부 {season} {r}위/{n}팀 (Japan Football League, 리그 수준 추정)"
    if lg == "J3": return f"일본 3부 {season} {r}위/{n}팀 (J3 League, 리그 수준 추정)"
    if lg == "KOR": return f"K리그1 {season} {r}위/{n}팀"
    if lg == "SC1": return f"스코틀랜드 1부 {season} {r}위/{n}팀 (Scottish Premier League, 플레이오프·스플릿 뒤 최종 순위)"
    if lg == "SC2": return f"스코틀랜드 2부 {season} {r}위/{n}팀 (Scottish First Division, 리그 수준 추정)"
    if lg == "IT2": return f"세리에B {season} {r}위/{n}팀"
    if lg in EU_LG:
        pre = EU_LG[lg]; n0 = _LRA["ERA"]["teams"](pre, int(season[:4]) + 1)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    return None

JCLUBS = {"3828", "937", "943"}
def seasons_for(cid, d, o, g):
    y, m = int(d[:4]), int(d[5:7])
    if g["club_id"] in JCLUBS: return [str(y - 1 if m == 1 else y)]   # 달력 연도, 1월 1일 일왕배 결승은 앞 해 대회
    s_ = y if m >= 8 else y - 1
    if g["club_id"] == "371" and d[5:] >= "07-10": s_ = y   # 셀틱: 7월 말 리그 개막이 새 시즌
    return [f"{s_}-{str(s_ + 1)[2:]}"]
def lg_cands(cid, d, o, g):
    ss = seasons_for(cid, d, o, g); y = int(ss[0][:4])
    if g["club_id"] in JCLUBS:
        if cid == "AFCL": doms = ["KOR"]
        elif y <= 2002 or y in (2015, 2016): doms = ["J1Y", "J2"]
        else: doms = ["J1", "J2", "JFL", "J3"]
    elif g["club_id"] == "371": doms = ["SC1", "SC2"]
    elif g["club_id"] == "1386": doms = ["IT1", "IT2"]
    else: doms = ["ES1", "ES2"]
    if cid in ("CL", "CLQ"): doms = list(EU_LG) + ["GB1", "RU1"]
    return [(lg, s_) for lg in doms for s_ in ss]

MAN = {}
def man(o, s, lv): MAN[(key(o), s)] = lv
FORCE = {}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []; RECALC = []
def opp_elo(o, d, cid, g):
    e, lv = opp_elo0(o, d, cid, g)
    if lv != "?" and (_LRA["parse"](lv, d) or re.search(" 순위 없음", lv)):
        v = lv_value(lv, d, o)
        if v != e: RECALC.append((d, o, e, v, lv))
        e = v
    return e, lv
def opp_elo0(o, d, cid, g):
    if g["gameId"] in FORCE:
        lv = FORCE[g["gameId"]]; e = lv_value(lv, d); ELO_SRC["직접 라벨"] += 1
        ELO_LOG[(o, d)] = ("force", e, lv); return e, lv
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o); seasons = seasons_for(cid, d, o, g)
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
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

# 승점 표 map 확인: 라벨 앞부분이 elo/league_points_other.json에 있는데 우리 상대 이름이 map에 없으면 기록
MAP_NEED = []
for r in E:
    h = pts_head(r[12])
    if h:
        s = PTS.O["seasons"][h]
        if r[1] not in s.get("map", {}) and key(r[1]) not in {key(x) for x in s.get("map", {})}:
            rows = s["tables"][0]["rows"]; mm = re.search(r" (\d+)위", r[12]); rk = int(mm.group(1))
            hit = [i for i, x in enumerate(rows) if key(x[0]) == key(r[1]) or norm(r[1]).replace(" fc", "").replace("st ", "saint ") == norm(x[0]).replace("st ", "saint ") or (toks(x[0]) and toks(x[0]) == toks(r[1]))]
            if not hit: hit = [i for i, x in enumerate(rows) if same_team(x[0], r[1])]
            MAP_NEED.append((h, r[1], rows[hit[0]][0] if hit else "?", hit[0] if hit else "?", rk - 1))
MAP_NEED = sorted(set(MAP_NEED))

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
    for x in RECALC: print("RECALC", x)
    for x in MAP_NEED: print("MAP", x)
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010-)
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
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None): d.append("단판/합산")
    if a[10] != b[10]: d.append("연장")
    return d
G_BYDATE = {ldate(g): g["competitionId"] for g in G.values()}
CROSS = []
JRE = re.compile(r"Nakamura|나카무라")
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and JRE.search(str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(나카무라 골?)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("나카무라 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) if G_BYDATE.get(r[9], "JAP1") in SA_DOM else same_team(x[1], r[1])):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and key(mm[1]) == key(m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[2], m[2]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
SHARED = sorted({(b, m[0], m[1]) for b, (oe, om) in OTHERS.items() for m in M for mm in om if mm[0] == m[0] and key(mm[1]) == key(m[1])})

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("yfmnk", "2002-08-01", "요코하마 F. 마리노스", "요코하마 FM", "1997~2002"), ("regnk", "2005-07-29", "레지나 칼초", "레지나", "2002~2005"),
         ("celnk", "2009-07-01", "셀틱", "셀틱", "2005~2009"), ("espnk", "2010-03-01", "RCD 에스파뇰", "에스파뇰", "2009~2010"),
         ("yfmnk", "2017-01-10", "요코하마 F. 마리노스", "요코하마 FM", "2010~2016"), ("jubnk", "2019-07-25", "주빌로 이와타", "이와타", "2017~2019"),
         ("yfcnk", None, "요코하마 FC", "요코하마 FC", "2019~2022")]
TM_CLUB = {"3828": "yfmnk", "1386": "regnk", "371": "celnk", "714": "espnk", "937": "jubnk", "943": "yfcnk"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in G.values():
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
SCAL = ("yfmnk", "jubnk", "yfcnk"); SJUL10 = ("celnk",)
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in SCAL: return str(y - 1 if (m == 1 and club == "yfmnk") else y)
    if club in SJUL10:
        s_ = y if d[5:] >= "07-10" else y - 1
        return f"{s_}-{str(s_ + 1)[2:]}"
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("요코하마 F. 마리노스(1997~2002)", "2002-08-01"), ("레지나", "2005-07-29"), ("셀틱", "2009-07-01"), ("에스파뇰", "2010-03-01"),
          ("요코하마 F. 마리노스(2010~2016)", "2017-01-10"), ("주빌로 이와타", "2019-07-25"), ("요코하마 FC", "9999")]
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
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e.get("assist_id") == ME and e["scorer_id"] != ME)
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), "TM_A", TM_A)
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    print("FM only", FM_ONLY); print("PM only", PM_ONLY)
    for c in CROSS: print(c)
    print("SHARED", len(SHARED)); [print(" ", s) for s in SHARED]
    print("FM", FM_N, FM_G, FM_CMP)
    print("JL", JL_CHECK, JL_DIFF); print("WIKI_CHECK", WIKI_CHECK)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    for x in MAP_NEED: print("MAP", x)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_nakamura.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "acl", "mlpf", "clq", "clg"]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const NKS_E={J(E)};\nconst NKS_M={J(M)};\nconst NKS_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "fotmob_playermatches_only": PM_ONLY, "cross_check": CROSS, "shared_matches": SHARED, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "jleague_official_diffs": JL_DIFF, "added_games": ADD_GAMES, "points_map_needed": MAP_NEED,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()}, "date_changes": DATE_LOG,
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
