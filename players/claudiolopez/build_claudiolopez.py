#!/usr/bin/env python3
"""클라우디오 로페스 (Claudio Javier López "El Piojo", Transfermarkt 3418): raw/ -> claudiolopez.json + clo.js (판정 근거는 judgments.md)

  python3 players/claudiolopez/build_claudiolopez.py            # 파일 쓰기(players/claudiolopez/clo.js, SOC_ROOT 지정 시 <SOC_ROOT>/src/data/clo.js 도)
  python3 players/claudiolopez/build_claudiolopez.py --debug    # Elo 출처 로그
  python3 players/claudiolopez/build_claudiolopez.py --stat     # 요약·판정·동료 대조
  python3 players/claudiolopez/build_claudiolopez.py --ties     # 합산 행

사비올라 build(players/saviola)를 바탕으로 함(수집기 형식이 같음). 1990년대 라싱 공백 보충은 크레스포 build(RSSSF 경기 줄) 선례.
상대 Elo는 v1.226 규칙: 같은 경기 다른 선수 자료 → Elo 통합표(같은 팀·시즌) → 출처로 확인한 순위로 라벨을 만들고
tools/league_rank_apply.py 의 value()로 값을 정함(직접 숫자를 넣지 않음). 스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib, datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_LOCAL = os.path.join(HERE, "clo.js")
OUT_JS = os.path.join(ROOT, "src", "data", "clo.js") if os.environ.get("SOC_ROOT") else None
OUT_JSON = os.path.join(HERE, "claudiolopez.json")
ME = "3418"
ME_KO = "클라우디오 로페스"
PFX = "CLO"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
ALLG = rd("tm_games_all.csv")
ESPN = json.load(__import__("gzip").open(os.path.join(RAW, "espn", "index.json.gz")))
ESPN_IDX = {k: v for k, v in ESPN["found"]}

# ---------------------------------------------------------------- 날짜
# 유럽 클럽: TM 리포트·일정 날짜(없으면 TM 시각을 현지 시각으로 바꾼 날짜 = 같은 날짜).
# 아메리카 클럽(라싱·아메리카·캔자스시티·콜로라도): TM 시각이
#   ① 중부 유럽 자정 자리값(UTC 22:00 여름/23:00 겨울 정각) → TM 날짜(= UTC 날짜 + 1, 일정 표 날짜와 같음; 리켈메·사비올라 선례)
#   ② 12:00·13:00 UTC 정각(날짜만 있는 자리값) → UTC 날짜(= TM 날짜)
#   ③ 그 밖(실제 킥오프 시각) → 경기 장소 시간대로 바꾼 현지 날짜(raw tz_used)
# ESPN 경기 시각(현지 변환)이 있는 경기는 모두 대조(judgments.md 2절).
AMER = {"1444", "3631", "4284", "1247"}
def _lastsun(y, m):
    x = datetime.date(y, m, 31)
    while x.weekday() != 6: x -= datetime.timedelta(1)
    return x
def _cet_mid_utc_hour(d):   # d 날짜 00:00(중부 유럽)이 UTC 몇 시인가(그 전날)
    return 22 if _lastsun(d.year, 3) < d <= _lastsun(d.year, 10) else 23
# 일정 표 날짜가 없는 경기 중 중부 유럽 자정 모양의 시각: 클럽 월드컵 2006 두 경기는 자리값(영어 위키백과 2006 FIFA Club World Cup:
# 12.11 전북전·12.17 알아흘리전), 아메리카 아페르투라 2006 세 경기(톨루카·테코스·아틀란테)는 ESPN 경기 시각(2006-09-03T22:00Z·10-29T23:00Z·11-04T23:00Z)과
# 같은 실제 킥오프라 멕시코시티 현지 날짜(9.3·10.29·11.4).
CWC_PH = {"991940", "991943"}
# TM 시각 자체가 하루 어긋난 MLS 2경기(영어 위키백과 2009 캔자스시티 시즌 문서 경기 상자 + MLS 경기 기록 주소의 날짜):
# 944090 뉴욕전 2009.4.23(목, ESPN 중계, mlsnet ymd=20090423, ESPN 2009-04-24T00:00Z = 4.23 19:00 CDT) — TM 2009-04-23T00:00Z(4.22 저녁)
# 953359 휴스턴전 2009.7.4(독립기념일 20:00 현지, match=07042009_HOUKC) — TM 2009-07-06T01:00Z
DATE_FIX = {"944090": "2009-04-23", "953359": "2009-07-04"}
DATE_LOG = []
def _ldate(g):
    if g["gameId"] in DATE_FIX:
        DATE_LOG.append((g["gameId"], "고침", g["date_utc"][:16], DATE_FIX[g["gameId"]], "")); return DATE_FIX[g["gameId"]]
    u = datetime.datetime.fromisoformat(g["date_utc"])
    sched = g["date_local_tm_report"] or g["date_local_schedule"]
    if g["club_id"] not in AMER:
        loc = u.astimezone(ZoneInfo(g["tz_used"])).date().isoformat()
        if sched and sched != loc: DATE_LOG.append((g["gameId"], "유럽 일정≠변환", sched, loc))
        return sched or loc
    nd = (u + datetime.timedelta(days=1)).date()
    if u.minute == 0 and u.hour == _cet_mid_utc_hour(nd) and (sched or g["gameId"] in CWC_PH): d = nd.isoformat(); kind = "자리값(자정)"
    elif (u.hour, u.minute) in ((12, 0), (13, 0)): d = u.date().isoformat(); kind = "자리값(정오)"
    else: d = u.astimezone(ZoneInfo(g["tz_used"])).date().isoformat(); kind = "현지 변환"
    if d != u.date().isoformat() or (sched and d != sched): DATE_LOG.append((g["gameId"], kind, g["date_utc"][:16], d, sched))
    return d
LD = {gid: _ldate(g) for gid, g in G.items()}
def ldate(g): return LD[g["gameId"]]
ESPN_CMP = []
for gid, (lg, ev, nm, dt) in ESPN_IDX.items():
    if gid not in G: continue
    u = datetime.datetime.fromisoformat(dt.replace("Z", "+00:00"))
    loc = u.astimezone(ZoneInfo(G[gid]["tz_used"])).date().isoformat()
    ESPN_CMP.append((gid, LD[gid], loc, "같음" if loc == LD[gid] else "다름"))

def opp(g):
    return re.sub(r"\s*\(\s*-?\s*\d{4}\s*-?\s*(\d{4})?\s*\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용(로페스 경력 전부)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES1", "IT1", "ARG1", "ARGC", "MEXA", "MEX1", "MLS1"}
CUPS = {"CDR", "CIT", "MLSP", "ARC1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                                      # 코파 델 레이 2·3라운드·16강, US 오픈컵 3라운드·16강, 코파 센테나리오
    if cid in ("SUC", "SCI"): return "df"                # 수페르코파·수페르코파 이탈리아나 = 국내컵 결승
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2000-01·2001-02 2차 조별('Group 2·4') 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "UI": return "elq"                         # 인터토토컵 = 유로파 예선(리켈메·소니 앤더슨 선례)
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 2라운드·16강·8강
    if cid in ("CS", "SCSA"):                            # 코파 수다메리카나·수페르코파 수다메리카나(크레스포·바티스투타 선례) = 수다메리카나 비중
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    if cid == "CCL":                                     # 북중미 챔피언스컵 2006
        if r.startswith("quarter"): return "ccck"
        if r.startswith("semi"): return "cccsf"
        if r.startswith("final"): return "cccf"
        return "ccc"
    if cid == "KLUB": return "cwc"                       # 2006 FIFA 클럽 월드컵(단판)
    if cid in ("POME", "POMX", "POUS"):                  # 리길야·MLS 플레이오프 = MLS 플레이오프 비중(치차리토·카모라네시·베컴 선례)
        if r.startswith("semi"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
        return "mlp"
    if cid == "SL": return "lcg"                         # 북중미 슈퍼리가 조별 = 리그스컵 비중(치차리토 선례)
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
    r = rnd.lower()
    if cid in ("CL", "CLQ", "UEFA", "UI"): return (1, 1)            # UEFA 2020-21까지
    if cid in ("CDR", "SUC", "CIT"): return (1, 1)                  # 코파 델 레이·수페르코파·코파 이탈리아
    if cid == "SCSA": return (0, 0)                                 # 수페르코파 수다메리카나(크레스포·바티스투타 선례)
    if cid == "CS": return (1, 0)                                   # 수다메리카나(치차리토·주니뉴 선례)
    if cid == "CCL": return (1, 0)                                  # 북중미 챔스(베컴 선례)
    if cid in ("POME", "POMX"): return (0, 1) if r.startswith("final") else (0, 0)   # 리길야(지냑 선례)
    if cid == "POUS": return (0, 1)                                 # MLS 플레이오프 2008~2012(베컴 선례)
    if cid == "ARC1": return (0, 1)                                 # 코파 센테나리오 1993 1라운드(RSSSF: 보카-리버 2차전 연장 골든골)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; oid = m["other_leg_id"]; club = G[gid]["club_id"]
    if oid in MI and MI[oid]["final"]:
        o = MI[oid]; fh, fa = map(int, o["final"].split(":"))
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    if m["other_leg_score"]:
        oh, oa = map(int, m["other_leg_score"].split(":"))
        return (oh, oa) if side_of(gid) == "h" else (oa, oh)
    # API 경기에 다른 차전 id가 없는 경우: 같은 대회·두 팀이 홈·원정을 바꾼 1차전을 MI 또는 TM 경기 목록(모든 참가 상태)에서 찾음
    r0 = rnd_of(G[gid]).lower().replace("2nd", "1st")
    for oid, o in MI.items():
        if oid != gid and o["home_id"] == m["away_id"] and o["away_id"] == m["home_id"] and (o["round_report"] or o["api_round"]).lower() == r0:
            fh, fa = map(int, o["final"].split(":"))
            return (fh, fa) if o["home_id"] == club else (fa, fh)
    for o in ALLG:
        if o["gameId"] != gid and o["clubId"] == club and o["opponentId"] == G[gid]["opponent_id"] and o["competitionId"] == G[gid]["competitionId"] \
           and o["venue"] != G[gid]["venue"] and abs((datetime.date.fromisoformat(o["date"]) - datetime.date.fromisoformat(ldate(G[gid]))).days) <= 21:
            return (int(o["score_club"]), int(o["score_opp"]))
    sys.exit("다른 차전 없음 " + gid)

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
    if not g["playedMinutes"]: sys.exit("출전 분 없음 " + g["gameId"])
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    if d >= GAP: sys.exit("2014.8 이후 도움 " + gid)
    A_STATUS.append((d, gid, e["minute"], e["scorer"], t or "(유형 빈칸)"))
    return None

def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

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
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"] or "(유형 빈칸)", e["goal_desc"] or "(설명 빈칸)"))
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
            if e["goal_desc"] == "Deflected shot on goal": judg.append(("굴절 슈팅 골(본인 골로 셈)", ldate(g), opp(g), e["minute"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))
cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G or not MI[gid]["final"]: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":"))
    if MI[gid]["result_flag"] == "pens" and h == a: continue
    if (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))

# ---------------------------------------------------------------- RSSSF로 보충한 라싱 1993~1996 경기(Transfermarkt 'not in squad' 자리 표시 행)
# 크레스포 v1.213 선례: 경기 단위 출처(RSSSF 경기 줄)가 확인하는 경기만. 득점 경기는 출전 분 기록이 없어 90분 추정(est 1).
# 코파 센테나리오 1993은 RSSSF 상세 페이지에 선발 명단·교체가 있어 90분(교체 없음, 추정 아님).
# (날짜, 상대(TM 이름), TM 대회, 라운드, 편 h/a/n, 분, 추정, [(분, PK, 골 전 우리, 골 전 상대)], 합산[leg, home, f1, f2] 또는 None, TM 자리 표시 gameId, 근거)
ADD = [
 ("1993-06-25", "CA Independiente", "ARC1", "Round 1 1st leg", "a", 90, 0, [(58, 1, 1, 0)], [1, 0, 0, 0], "4825574", "RSSSF arg-centenario93det(선발, 58분 PK)"),
 ("1993-07-02", "CA Independiente", "ARC1", "Round 1 2nd leg", "h", 90, 0, [], [2, 1, 2, 1], "4825583", "RSSSF arg-centenario93det(선발, 교체 없음)"),
 ("1993-07-11", "CA Vélez Sarsfield", "ARC1", "Winners Round 1", "n", 90, 0, [(29, 0, 0, 0), (72, 0, 1, 2), (78, 0, 2, 2)], None, "4825595", "RSSSF arg-centenario93det(선발, 29·72·78분, 페로 경기장)"),
 ("1993-08-01", "Club Atlético Belgrano", "ARC1", "Winners Round 3", "n", 90, 0, [], None, "4825607", "RSSSF arg-centenario93det(선발, 교체 없음)"),
 ("1995-09-09", "CA Rosario Central", "ARG1", "", "a", 90, 1, [(44, 0, 0, 1)], None, "4973210", "RSSSF arg96 아페르투라 6라운드"),
 ("1995-10-10", "Club Estudiantes de La Plata", "ARG1", "", "a", 90, 1, [(55, 0, 1, 1)], None, "4973248", "RSSSF arg96 아페르투라 9라운드"),
 ("1995-10-21", "Club Atlético Gimnasia y Esgrima (Jujuy)", "ARG1", "", "a", 90, 1, [(24, 0, 0, 0)], None, "4973260", "RSSSF arg96 아페르투라 11라운드"),
 ("1995-11-19", "CA Lanús", "ARG1", "", "a", 90, 1, [(57, 0, 2, 0)], None, "4973307", "RSSSF arg96 아페르투라 15라운드"),
 ("1995-11-26", "CA Newell's Old Boys", "ARG1", "", "h", 90, 1, [(26, 0, 1, 0)], None, "4973317", "RSSSF arg96 아페르투라 16라운드"),
 ("1995-12-03", "CA Boca Juniors", "ARG1", "", "a", 90, 1, [(12, 0, 2, 0), (86, 0, 5, 3)], None, "4973327", "RSSSF arg96 아페르투라 17라운드 + 영어 위키백과 1995-96 보카 시즌(14·86분)"),
 ("1995-12-17", "CA Colón", "ARG1", "", "a", 90, 1, [(16, 0, 0, 0)], None, "4973341", "RSSSF arg96 아페르투라 19라운드"),
 ("1996-03-10", "AA Argentinos Juniors", "ARGC", "", "a", 90, 1, [(90, 0, 2, 1)], None, "4939408", "RSSSF arg96 클라우수라 1라운드"),
 ("1996-03-24", "Club Atlético Belgrano", "ARGC", "", "a", 90, 1, [(23, 0, 0, 0)], None, "4954394", "RSSSF arg96 클라우수라 3라운드"),
 ("1996-04-28", "CA River Plate", "ARGC", "", "a", 90, 1, [(33, 0, 0, 0)], None, "4939753", "RSSSF arg96 클라우수라 7라운드(크레스포 자료 같은 경기)"),
 ("1996-06-09", "CA Huracán", "ARGC", "", "a", 90, 1, [(19, 0, 0, 0)], None, "4968019", "RSSSF arg96 클라우수라 12라운드"),
 ("1996-06-23", "Club Ferro Carril Oeste", "ARGC", "", "a", 90, 1, [(27, 0, 0, 0), (54, 0, 2, 0)], None, "4970861", "RSSSF arg96 클라우수라 14라운드"),
 ("1996-08-07", "CA Boca Juniors", "ARGC", "", "h", 90, 1, [(82, 0, 0, 0)], None, "", "RSSSF arg96 클라우수라 17라운드 + 영어 위키백과 1995-96 보카 시즌(82분)"),
]
ADD_IDS = {a[9] for a in ADD if a[9]}

# ---------------------------------------------------------------- 이름·기존 자료
ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
def key(n):
    k = norm(n)
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "clo.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "cp", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "atletico", "calcio", "sport", "deportivo", "fk", "bv", "ca", "racing", "juniors", "gimnasia", "esgrima", "plata", "central", "union",
        "santa", "nacional", "river", "plate", "san", "old", "boys", "rosario", "newell", "newells", "estudiantes", "independiente", "madrid", "milan",
        "inter", "valencia", "barcelona", "sociedad", "celta", "vigo", "las", "palmas", "revolution", "new", "york", "red", "bulls", "galaxy", "los",
        "angeles", "kansas", "wizards", "colorado", "rapids", "fire", "crew", "dynamo", "toronto", "dallas", "salt", "lake", "jose", "earthquakes",
        "chivas", "usa", "seattle", "sounders", "guadalajara", "america", "tigres", "uanl", "toluca", "pumas", "unam", "cruz", "azul", "santos", "laguna",
        "atlas", "monterrey", "morelia", "necaxa", "pachuca", "veracruz", "atlante", "chiapas", "jaguares", "tecos", "uag", "luis", "dorados", "sinaloa",
        "lazio", "roma", "juventus", "parma", "verona", "hellas", "bologna", "udinese", "torino", "chievo", "lecce", "brescia", "piacenza", "perugia",
        "reggina", "modena", "empoli", "como", "ancona", "sampdoria", "atalanta", "fiorentina", "napoli", "venezia", "vicenza", "bari"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d):
    exact = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    cand = exact or [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위 → 라벨 → 값(tools/league_rank_apply.py)
_LRA = {'__file__': os.path.join(ROOT, 'tools', 'league_rank_apply.py'), '__name__': 'lra'}
_argv = sys.argv; sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA['__file__'], encoding='utf-8').read().split("if __name__ == '__main__':")[0], 'lra', 'exec'), _LRA)
sys.argv = _argv
def lv_value(lv, d):
    m_ = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv)
    if m_:
        cal = m_.group(4) is None; y = int(m_.group(3)) + (0 if cal else 1)
        return int(round(_LRA['base'](_LRA['KO'][m_.group(1)], int(m_.group(2)), y, cal)))
    p = _LRA['parse'](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA['value'](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    return v

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 아르헨티나: 경기 날짜에 진행 중이던 단계(리그 경기는 그 경기 대회; 코파 센테나리오 1993.6~7월은 직전 끝난 클라우수라 1993)
def arg_stage(d, cid):
    y = int(d[:4])
    if cid == "ARG1": return ("Apertura", y if int(d[5:7]) >= 7 else y - 1)
    if cid == "ARGC": return ("Clausura", y)
    if cid == "ARC1": return ("Clausura", 1993)
    return ("Apertura", y) if int(d[5:7]) >= 8 else ("Clausura", y)
# 멕시코: 경기 날짜에 진행 중이던 토너먼트(리길야는 그 토너먼트, 1~5월 = 클라우수라, 7~12월 = 아페르투라)
def mex_stage(d):
    y, mo = int(d[:4]), int(d[5:7])
    return ("Apertura", y) if mo >= 7 else ("Clausura", y)
MAN = {}   # (key, 시즌 키) -> lv  (값은 라벨에서 계산)
def man(o, s, lv): MAN[(key(o), s)] = lv
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []

def season_keys(o, d, cid):
    k = key(o)
    if cid in ("ARG1", "ARGC", "ARC1") or (cid in ("SCSA",) and False):
        st_, y = arg_stage(d, cid); return [f"{y}/{st_}"]
    if cid in ("MEXA", "MEX1", "POME", "POMX", "CCL"):
        st_, y = mex_stage(d); s = f"{y}-{str(y + 1)[2:]}" if st_ == "Apertura" else f"{y - 1}-{str(y)[2:]}"
        return [f"{s}/{st_}", s]
    if cid == "SL":   # 슈퍼리가 2009(6~7월) 멕시코 상대 = 직전 끝난 클라우수라 2009, MLS 상대 = MLS 2009
        st_, y = mex_stage(d)
        return [d[:4], f"{y - 1}-{str(y)[2:]}/{st_}"]
    if cid in ("MLS1", "POUS", "MLSP"):
        return [d[:4]]
    if cid in ("CS", "SCSA"): return [d[:4], eu(d)]
    if cid == "KLUB": return [eu(d), d[:4]]
    return [eu(d), d[:4]]

def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o); seasons = season_keys(o, d, cid)
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            p = _LRA['parse'](lv, d)
            if p and _LRA['value'](*p) != e: TABLE_DIFF.append((o, s, e, lv, _LRA['value'](*p)))
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for s in seasons:
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d)
            ELO_SRC["순위 라벨(출처 확인)"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
# RSSSF 보충 경기
for (d, o, cid, rnd, ven, mn, est, goals, tie, tmid, why) in ADD:
    comp = comp_of(cid, rnd); ko = 0 if (cid in LEAGUE or tie) else 1
    M.append([d, o, comp, mn] + ([1] if est else []))
    for (mi, pk, gf, ga) in goals:
        elo, lv = opp_elo(o, d, cid)
        row = ["g", o, elo, comp, mi, gf, ga, ko, pk, d, 0, 0, lv, 0]
        if tie:
            ag, et_ = tie_rule(cid, d, rnd); row.append([tie[0], tie[1], tie[2], tie[3], ag, et_])
        E.append(row)
M.sort(key=lambda m: m[0])

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
    for x in sorted(NEW_TS.items()): print("NEW", x)
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    sys.exit(0)

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
CROSS = []
LOPEZ_RE = r"Claudio L[oó]pez|C\. L[oó]pez|Piojo"
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(LOPEZ_RE, x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(로페스 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("로페스 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("타인 도움 행이 로페스 골과 같은 시각", b, r[9], r[4], hit[0][13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x[1], r[1]):
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
                    CROSS.append(("TM 로페스 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
# 같은 상대와의 경기가 다른 선수 자료에 ±1일로 적힌 경우(날짜 차이 점검)
DATE_X = []
MYCLUB_NAMES = {"1444": "Racing Club", "1049": "Valencia", "398": "Lazio", "3631": "América", "4284": "Kansas City", "1247": "Colorado"}
for g in GAMES:
    d = ldate(g); dd = datetime.date.fromisoformat(d)
    for b, (oe, om) in OTHERS.items():
        for mm in om:
            if MYCLUB_NAMES[g["club_id"]] in mm[1] and mm[0] != d and abs((datetime.date.fromisoformat(mm[0]) - dd).days) == 1:
                # 상대가 그 선수의 팀인지 확인할 수 없으므로 후보로만 기록
                DATE_X.append((b, mm[0], mm[1], d, opp(g)))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("racclo", "1996-08-08"), ("valclo", "2000-07-01"), ("lazclo", "2004-07-30"), ("ameclo", "2007-01-17"), ("racclo", "2008-03-10"),
         ("kcclo", "2010-01-01"), ("colclo", None)]
TM_CLUB = {"1444": "racclo", "1049": "valclo", "398": "lazclo", "3631": "ameclo", "4284": "kcclo", "1247": "colclo"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
def season_of(d, club):
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    if club in ("racclo", "kcclo", "colclo"): return str(y)
    if club == "valclo": s_ = y if (m, dd) >= (7, 10) else y - 1
    elif club == "ameclo": s_ = y if m >= 7 else y - 1
    else: s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("라싱 클루브 1992~1996", "1996-08-08"), ("발렌시아", "2000-07-01"), ("라치오", "2004-07-30"), ("클루브 아메리카", "2007-01-17"),
          ("라싱 클루브 2007", "2008-03-10"), ("캔자스시티 위저즈", "2010-01-01"), ("콜로라도 래피즈", "9999")]
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
NADD = len(ADD); NADDG = sum(len(a[7]) for a in ADD); NEST = sum(1 for a in ADD if a[6])
def d_(x): y, m, d = x.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EXJ = [j for j in judg if j[0] == "도움 제외"]
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A, UNTYPED)
    for j in judg: print(j)
    for c in CROSS: print(c)
    print("score mismatch", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("dates", len(DATE_LOG)); [print(" ", x) for x in DATE_LOG]
    print("ESPN", collections.Counter(x[3] for x in ESPN_CMP), [x for x in ESPN_CMP if x[3] != "같음"])
    print("TABLE_DIFF", TABLE_DIFF)
    for x in DATE_X: print("DATE_X", x)
    for x in sorted(NEW_TS.items()): print("NEW", x)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_claudiolopez.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl", "df", "clg", "cl16", "mlp", "lcg", "ccc"]:
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
        if b[4] > a[4] and (b[5], b[6]) <= (a[5], a[6]) and b[5] < a[5] + 1: problems.append(("스코어 역순", d, a[4], b[4]))
for r in E:
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if not r[2] or r[12] == "?": problems.append(("Elo 없음", r))
mm_ = {m[0]: m for m in M}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > 90 and not r[10] and not r[11] and not (r[4] == 90): problems.append(("90분 넘는 정규 시간 골", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    js = f"const {PFX}_E={J(E)};\nconst {PFX}_M={J(M)};\nconst {PFX}_NOTE={J(NOTE)};\n"
    open(OUT_LOCAL, "w", encoding="utf-8").write(js)
    if OUT_JS: open(OUT_JS, "w", encoding="utf-8").write(js)
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "cross_check": CROSS, "elo_sources": ELO_SRC, "date_changes": DATE_LOG, "espn_dates": ESPN_CMP,
               "rsssf_added": ADD, "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_LOCAL}" + (f" + {OUT_JS}" if OUT_JS else ""))
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
