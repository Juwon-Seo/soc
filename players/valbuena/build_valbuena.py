#!/usr/bin/env python3
"""마티외 발부에나 (Transfermarkt 40687, FotMob 40060): raw/ -> valbuena.json + src/data/vab.js (판정 근거는 judgments.md)

  python3 players/valbuena/build_valbuena.py            # 파일 쓰기
  python3 players/valbuena/build_valbuena.py --debug    # Elo 출처 로그
  python3 players/valbuena/build_valbuena.py --stat     # 요약·동료 대조·FotMob 대조

입력: raw/tm_games.csv(출전·분·현지 날짜, 성인 클럽 802경기; 올림피아코스 B는 raw/youth_reserve_games.csv라 읽지 않음),
      raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전), raw/fotmob_events.csv·fotmob_playerMatches.csv(2014-08 이후 도움 대조),
      raw/ranks.txt(Transfermarkt 순위표), elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "vab.js")
OUT_JSON = os.path.join(HERE, "valbuena.json")
ME = "40687"
ME_KO = "마티외 발부에나"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

def ldate(g): return g["date_local"]
def opp(g): return re.sub(r"\s*\(\s*\d{4}\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"     # 이 전 도움은 TM 단일 출처 허용(클로제·인시녜 선례), 이후는 TM+FotMob 일치 또는 다른 출처 2곳

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR3", "FR1", "RU1", "TR1", "GR1", "POGR", "S1PO", "ZYP1", "ZYPA", "MAL2"}   # 그리스 플레이오프·플레이아웃, 키프로스 2단계도 리그(벨기에 플레이오프 선례)
CUPS = {"FRC", "FRL", "TRP", "GRP", "CPO1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "FRCH": return "df"                      # 트로페 데 샹피옹 = 슈퍼컵 = 국내컵 결승
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "UI": return "elq"                       # 인터토토컵 = 유로파 예선(램파드·비야·델 피에로·지단 선례)
    if cid in ("CLQ",): return "clq"
    if cid in ("ELQ",): return "elq"                   # 유로파 예선 2·3라운드·플레이오프
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "UEFA":                                  # 2007-08·2008-09 UEFA컵 3라운드(32강)·16강·8강 (벤 아르파 선례)
        return "elk"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                   # 32강('Second Round'·'intermediate stage')·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "UI"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid == "TRP": return (1, 1) if d < "2021-07-01" else (0, 1)     # 튀르키예컵: 2020-21까지 원정 다득점·연장(문서 3절, v1.152)
    if cid == "GRP": return (1, 1)     # 그리스컵 2019-20~2022-23: 원정 다득점(연장 원정골 포함)·연장 — judgments.md 5절 출처
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G and G[oid]["gameState"] == "regularly_terminated":
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    sc = re.sub(r"[^0-9:]", "", m["other_leg_score"])
    oh, oa = map(int, sc.split(":"))                   # 이 경기 홈:원정 방향
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

def assist_reason(e):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty") or t.startswith("Handball"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

def fm_rows(gid): return [f for f in FME.get(gid, []) if f["pen_shootout_event"] != "True"]
def fm_has_vb_assist(gid, after_ha):
    return any(f["vb_assist"] == "1" and f["newScore_home_away"] == after_ha for f in fm_rows(gid))

# 2014-08-01 이후 TM 도움 중 FotMob 경기 이벤트에 발부에나 도움이 없는 것: 다른 출처 2곳(경기 기사·구단 기사 등)으로 확인되면 넣음(judgments.md 4절)
#   (gameId, TM 분) -> (판정, 근거 요약)
POST_GAP = {}
def post(gid, mn, ok, why): POST_GAP[(gid, mn)] = (ok, why)
# FotMob에만 있는 도움(TM 없음): 다른 출처 2곳이 확인한 것만 더함 — 확인된 것 없음(judgments.md 4절)
ADD_A = []

raw_rows, judg, unconf = [], [], []
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
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if ldate(g) >= GAP and not fm_has_vb_assist(gid, e["score_home_away_after"]):
                ok, src = POST_GAP.get((gid, e["minute"]), (None, "판정 없음"))
                if ok is None: sys.exit(f"2014-08 이후 TM 단독 도움 판정 필요: {gid} {ldate(g)} {opp(g)} {e['minute']} {e['scorer']}")
                judg.append(("2014-08 이후 TM 단독 도움 " + ("넣음" if ok else "뺌(확인 못 함)"), ldate(g), opp(g), e["minute"], e["scorer"], src))
                if not ok:
                    unconf.append((ldate(g), opp(g), e["minute"], e["scorer"], src)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

# FotMob 경기 이벤트에만 있는 발부에나 도움(2014-08 이후) — 기록하고 넣지 않음(ADD_A 확인분만)
FM_ONLY = []
for gid, fl in FME.items():
    if gid not in G or ldate(G[gid]) < GAP: continue
    tmafter = {e["score_home_away_after"] for e in EVS.get(gid, []) if e["assist_id"] == ME}
    for f in fl:
        if f["vb_assist"] == "1" and f["pen_shootout_event"] != "True" and f["newScore_home_away"] not in tmafter:
            FM_ONLY.append((gid, ldate(G[gid]), opp(G[gid]), f["time"], f["newScore_home_away"], f["scorer"]))

# 리포트 골 = API 경기별 골 수 점검
cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, re.sub(r"[^0-9:]", "", MI[gid]["final"]).split(":")) if MI[gid]["final"] else (h, a)
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
