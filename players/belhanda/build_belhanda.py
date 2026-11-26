#!/usr/bin/env python3
"""유네스 벨한다 (Transfermarkt 118022): raw/ -> belhanda.json + src/data/blh.js (판정 근거는 judgments.md)

  python3 players/belhanda/build_belhanda.py                 # 파일 쓰기
  python3 players/belhanda/build_belhanda.py --debug         # Elo 출처 로그
  python3 players/belhanda/build_belhanda.py --stat          # 요약·동료 대조·FotMob 대조
  python3 players/belhanda/build_belhanda.py --ties          # 합산 행·판정
  python3 players/belhanda/build_belhanda.py --root=<복사본>  # 그 복사본의 src/data·elo 사용(검증용)

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv·fotmob_tm_map.csv(FotMob), raw/ranks.txt(Transfermarkt 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
뼈대는 니앙 build_niang.py(합산·튀르키예·카타르)와 사바니에 build_savanier.py(FotMob 도움 대조).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
GITROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "blh.js")
OUT_JSON = os.path.join(HERE, "belhanda.json")
ME = "118022"
ME_KO = "유네스 벨한다"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FM_MAP = {r["tm_gameId"]: r["fotmob_matchId"] for r in rd("fotmob_tm_map.csv")}
FM_PM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 날짜
DATE_FIX = {
    # 쿠프 드 라 리그 2010-11 8강 몽펠리에–릴: Transfermarkt 2010.10.10(일)은 16강(10.26)보다 앞이라 맞지 않음.
    # FotMob 경기(939194) 2010.11.10 17:45 UTC, 8강 일정 2010.11.9~10(수), 프랑스어 위키백과 '수요일 11월 27일'의 요일도 수요일 = 11.10 → 2010-11-10
    "1062291": "2010-11-10",
}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local_computed"])
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 판정 표
MIN_FIX, MIN_EST = {}, {}       # 출전 분은 Transfermarkt 그대로(빈칸 0경기)
GAP = "2014-08-01"              # 이 날짜 전 도움은 Transfermarkt 리포트 단일 출처 허용(클로제·인시녜·니앙 선례)
# 2014-08-01 뒤 Transfermarkt 도움 가운데 FotMob 경기 이벤트에 도움자가 없지만 FotMob 선수 경기 목록(playerMatches)의
# 그 경기 벨한다 도움 수가 Transfermarkt와 같은 경기(TM∩FotMob, 호드리구·사바니에 선례)
FM_PM_OK = {"4705906", "4793107", "4793152", "4793143", "4793116", "4793156"}
# 2014-08-01 뒤 Transfermarkt 단독 도움 가운데 다른 출처 2곳으로 확인한 것: (gameId, 분 표기) -> 근거
ADD_CONFIRMED = {
    ("2477953", "14"): "2014.8.2 메탈리스트전 14분 크라베츠 골: sports.ru 문자중계(베주스 패스를 받은 벨한다가 골키퍼를 끌어내고 크라베츠에게 내줌, 이벤트 '크라베츠 (0-1) 벨한다')·TSN 문자중계('유네스는 직접 찰 수 있었지만 크라베츠에게 내줌')",
    ("2490087", "18"): "2014.9.22 볼린전 18분 야르몰렌코 골: sports.ru 이벤트·문자중계(야르몰렌코–벨한다–야르몰렌코 2대1)·디나모 구단 경기 기사(Yarmolenko and Belhanda played one-two)",
    ("2504268", "28"): "2014.11.2 드니프로전 28분 렌스 헤더: sports.ru(벨한다 크로스)·디나모 구단 경기 페이지('Lens (28, assist – Belhanda)')",
    ("2504281", "61"): "2014.11.23 메탈루르흐 자포리자전 61분 미겔 벨로주 골: sports.ru 이벤트('벨로주 (1-3) 벨한다')·디나모 구단 경기 기사(Belhanda found Miguel inside the penalty area)",
    ("2598543", "43"): "2015.9.20 볼린전 43분 크라베츠 골: sports.ru 이벤트·문자중계(벨한다가 페널티 지역 선으로 내준 공)·디나모 구단 경기 페이지('Kravets (43, assist – Belhanda)')",
    ("3179990", "90+4"): "2019.5.15 튀르키예컵 결승 아키사르스포르전 90+4분 디아녜 헤더: A Spor 문자중계('Golde asisti yapan oyuncu Younes Belhanda')·VI(벨한다 프리킥)·Fanatik 칼럼(벨한다 크로스, 디아녜 헤더)",
    ("3310330", "85"): "2020.2.12 튀르키예컵 8강 2차전 알라니아스포르전 85분 아뎀 뷔이윅 골: 휘리예트 경기 기사(벨한다 오른쪽 크로스를 먼 포스트에서)·A Spor 문자중계('Gol pasını veren isim Younes Belhanda')",
}
# 2014-08-01 뒤 Transfermarkt 단독 도움 가운데 다른 출처 2곳을 찾지 못해 뺀 것: (gameId, 분 표기) -> 찾은 것
UNCONFIRMED = {
    ("2504268", "40"): "2014.11.2 드니프로전 40분 야르몰렌코 골: sports.ru·디나모 구단 경기 페이지 모두 렌스 도움으로 적음",
    ("2551465", "37"): "2015.5.20 우크라이나컵 준결승 2차전 올림피크 도네츠크전 37분 야르몰렌코 골: 디나모 구단 경기 페이지 1곳뿐(다른 기사는 득점자만)",
    ("2619440", "73"): "2015.9.23 우크라이나컵 16강 1차전 오볼론전 73분 주니오르 모라에스 골: 디나모 구단 경기 페이지는 곤살레스 도움으로 적음",
    ("3069853", "69"): "2018.12.23 시바스스포르전 69분 오녜쿠루 골: FotMob은 데르디요크 도움, 기사마다 과정 설명이 다름(마리아누 크로스·수비 맞고 흐른 공)",
    ("4148244", "16"): "2023.8.10 컨퍼런스 예선 오시예크전 16분 유수프 사르 골: FotMob 도움 없음, AA 기사 1곳만 벨한다 패스(사르 첫 슛이 골키퍼 맞고 나온 뒤 재차 슛)",
    ("4175716", "12"): "2024.3.5 움살랄전 12분 고메스 골: QSL 공식 기사(같은 글을 걸프 타임스가 실음) 1곳",
    ("4175716", "53"): "2024.3.5 움살랄전 53분 고메스 골: QSL 공식 기사 1곳",
    ("4175700", "68"): "2024.3.11 알마르키야전 68분 아자디 골(유형 빈칸): QSL·QNA 기사에 도움자 없음",
    ("4175700", "84"): "2024.3.11 알마르키야전 84분 고메스 골: QSL·QNA 기사에 도움자 없음",
    ("4175725", "31"): "2024.3.29 알아흘리전 31분 오마르 무함마드 골: 다른 출처 2곳 못 찾음",
    ("4400931", "31"): "2024.8.10 알사드전 31분 부네자 골: 다른 출처 2곳 못 찾음",
    ("4446305", "86"): "2024.10.5 QSL컵 알코르전 86분 하가나 골: 다른 출처 2곳 못 찾음",
    ("4400974", "73"): "2024.11.1 알두하일전 73분 부네자 골: 다른 출처 2곳 못 찾음",
    ("4446314", "85"): "2024.11.11 QSL컵 알와크라전 85분 오마르 무함마드 골: 다른 출처 2곳 못 찾음",
    ("4401046", "2"): "2025.4.5 알두하일전 2분 오마르 무함마드 골: 다른 출처 2곳 못 찾음",
    ("4401054", "34"): "2025.4.11 알라이얀전 34분 슬리티 골: 다른 출처 2곳 못 찾음",
}
# 개별 판정으로 뺀 도움: (gameId, 분 표기) -> 이유
EXCL_A = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "UKR1", "L1", "TR1", "QSL"}
CUPS = {"FRC", "FRL", "UKRP", "TRP", "QEC1", "QSCP"}
SUPER = {"UKRS", "TRS"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "df"                              # 우크라이나·튀르키예 슈퍼컵 = 국내컵 결승 비중(문서 3절)
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                                           # 16강까지(쿠프 드 라 리그 4라운드·16강, 우크라이나컵 2·3라운드·16강, 튀르키예컵 3·5라운드·16강, QSL컵 조별, 에미르컵 16강)
    if cid == "ELQ": return "elq"                             # 유로파 예선 2·3라운드·플레이오프
    if cid == "ECLQ": return "ecq"                            # 컨퍼런스 예선 2·3라운드·플레이오프
    if cid == "CL":
        if r.startswith("group"): return "clg"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                          # 32강(2014 'Second Round', 'intermediate stage')·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0                         # 챔스·유로파 조별, QSL컵 조별(리그식, 루이스 알베르토·드락슬러 선례)
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "EL", "ELQ", "ECLQ"):
        return (1, 1) if d < "2021-07-01" else (0, 1)         # UEFA 원정 다득점 2020-21까지
    if cid == "TRP":
        return (1, 1) if d < "2021-07-01" else (0, 1)         # 튀르키예컵 2020-21까지 원정 다득점(문서 3절)
    if cid == "UKRP": return (1, 1)                           # 우크라이나컵 2014-15: 영어 위키백과 시즌 문서(메탈리스트 원정 다득점 진출, 초르노모레츠 연장 뒤 승부차기)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

TIES = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
def other_leg(gid):
    t = TIES[gid]; s = side_of(gid)
    oid = t["other_leg_id"]
    if oid in G and G[oid]["gameState"] != "penalty_shootout":
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, t["other_leg_final"].split(":"))      # 다른 차전의 홈 팀 기준 표기
    home_is_us = t["other_leg_home"] == G[gid]["club"] or (s == "a")   # 다른 차전은 홈·원정이 바뀜
    return (oh, oa) if home_is_us else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), g["round"])
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    gid = g["gameId"]
    row = [ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), MIN_FIX.get(gid, MIN_EST.get(gid, int(g["playedMinutes"] or 0)))]
    if gid in MIN_EST: row.append(1)
    M.append(row)

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
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t.startswith("Deflect"): return "굴절"
    return None

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FME.items():
    for r in evs:
        if r["belhanda_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))
def pm_assists(gid):
    p = FM_PM.get(FM_MAP.get(gid, ""))
    return int(p["assists"]) if p and p["assists"] not in ("", None) else None

raw_rows, judg = [], []
SRC_A = collections.Counter()
UNDECIDED = []
USED_FM = collections.Counter()
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
        if is_a and sd != side and not is_og(e):
            sys.exit("상대 골 도움 칸에 벨한다 " + gid)
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        k = (gid, e["minute"])
        if is_a:
            why = assist_reason(e) or EXCL_A.get(k)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why, e["assist_type"])); continue
            if ldate(g) >= GAP:
                base = int(e["minute"].split("+")[0])
                hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - mi) <= 3 or abs(t - base) <= 3]
                if hit and USED_FM[gid] < len(FM_ASSIST[gid]):
                    USED_FM[gid] += 1; src = "TM∩FotMob 경기 이벤트"
                elif gid in FM_PM_OK and pm_assists(gid) == sum(1 for x in EVS[gid] if x["assist_id"] == ME and x["scorer_id"] != ME):
                    src = "TM∩FotMob 선수 경기 목록"
                elif k in ADD_CONFIRMED:
                    src = "TM + 다른 출처 2곳"
                elif k in UNCONFIRMED:
                    judg.append(("도움 제외(단일 출처 미확인)", ldate(g), opp(g), e["minute"], e["scorer"], UNCONFIRMED[k], e["assist_type"])); continue
                else:
                    UNDECIDED.append((gid, ldate(g), opp(g), e["minute"], e["scorer"], e["assist_type"], FM_ASSIST.get(gid), pm_assists(gid))); continue
            else:
                src = "2014.8 전 Transfermarkt"
            SRC_A[src] += 1
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk:
                if e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
                judg.append(("PK 아님(PK가 막힌 뒤 리바운드 골)", ldate(g), opp(g), e["minute"], e["goal_desc"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

for t in list(ADD_CONFIRMED) + list(UNCONFIRMED) + list(EXCL_A):
    if not any(x["minute"] == t[1] and x["assist_id"] == ME for x in EVS.get(t[0], [])): sys.exit("판정 표 키가 TM 도움과 맞지 않음 " + str(t))

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
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
GA_GAMES = {r[1] for r in raw_rows}
if [x for x in SCORE_MISMATCH if x[0] in GA_GAMES]: sys.exit("골·도움 경기 리포트 불완전 " + str(SCORE_MISMATCH))

# ---------------------------------------------------------------- 이름·기존 자료
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

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
        if r["선수"] == ME_KO: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", GITROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "blh.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "foot", "ball",
        "atletico", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss", "olympique", "milan", "inter", "madrid", "fk", "if",
        "deportivo", "san", "santa", "saint", "us", "ogc", "losc", "stade", "racing", "athletic", "union", "sportive", "vfb", "vfl",
        "al", "spor", "jk", "sk", "cska", "moscow", "sofia", "kyiv", "dynamo", "metalurg", "nk", "krc", "hnk", "pfk", "bk", "aalborg"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, collections.Counter((x[2], x[12]) for b, x in cand)

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
# 카타르 스타스리그 2025-26 공식 최종 순위(루이스 알베르토 자료와 같음: 2026.4.3 카타르 SC–알와크라 몰수 판정 반영)
for _nm, _r in (("Qatar SC", 6), ("Al-Arabi SC", 7), ("Al-Wakrah SC", 8)):
    RANKS[("QSL", "2025-26")][key(_nm)] = (_r, 12, _nm)
RANK_FIX = {}

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
def half_up(x): return int(x + 0.5)

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e[12] or "")
        if m: c[int(m.group(1))][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
def mid(tab, r):
    if r in tab: return tab[r], False
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up(tab[a] + (tab[b] - tab[a]) * (r - a) / (b - a)), True
INTERP_USED = set()

# 쉬페르리그: 튀르키예 회귀(평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 흩어짐 119; 투란·팔카오·메르턴스 build 값)
TR_COEF = {2016: 6.8, 2017: 6.8, 2018: 5.5, 2019: 5.0, 2020: 3.1, 2021: 6.7, 2022: 11.8, 2023: 12.0, 2024: 10.3}
def tr_mean(season):
    s = int(season[:4]); c = sum(TR_COEF[y] for y in (s - 1, s, s + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)
# 우크라이나 1부: 셰브첸코 모형(1473 + 23.33 × (앞뒤 3시즌 계수 평균 − 7.333) − 73, 흩어짐 119; 고메스 자료 2013-14 같은 식)
UA_COEF = {2012: 9.500, 2013: 7.833, 2014: 10.000, 2015: 9.800, 2016: 5.500}   # kassiesa.net method4 ccoef(시즌 끝 연도) 2013~2017 페이지
def ua_mean(season):
    s = int(season[:4]); c = sum(UA_COEF[y] for y in (s - 1, s, s + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333) - 73
QA_KNOWN = {1: 1573, 2: 1518, 3: 1493, 4: 1482, 5: 1470, 6: 1456, 7: 1446, 8: 1439, 9: 1433, 10: 1420, 11: 1410, 12: 1398}
NOW = "11월 18일 현재 순위"

def rank_model(lg, season, r, n):
    if lg in ("FR1", "L1"):
        pre = "리그1" if lg == "FR1" else "분데스리가"
        m = ents_map(pre, season)
        v, it = mid(m, r)
        if v is None: return None
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"{pre} {season} {r}위"
    if lg == "FR2":
        m = ents_map("리그2", season)
        v, it = mid(m, r)
        if v is None:
            v = half_up(1540 + SD2 * curve(r, n)); INTERP_USED.add((lg, season, r, v, "모형"))
            return v, f"리그2 {season} {r}위 (추정, 프랑스 2부 평균 1540 모형)"
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"리그2 {season} {r}위"
    if lg == "TR1":
        m = ents_map("쉬페르리그", season)
        if r in m: return m[r], f"쉬페르리그 {season} {r}위"
        lo = [k for k in m if k < r]; hi = [k for k in m if k > r]
        if lo and hi:
            a, b = max(lo), min(hi); v = half_up(m[a] + (m[b] - m[a]) * (r - a) / (b - a))
            INTERP_USED.add((lg, season, r, v))
            return v, f"쉬페르리그 {season} {r}위 (추정, 다른 선수 자료 {a}위 {m[a]}·{b}위 {m[b]} 사이)"
        v = round(tr_mean(season) + 119 * curve(r, n)); INTERP_USED.add((lg, season, r, v, "모형"))
        return v, f"쉬페르리그 {season} {r}위 (추정, 튀르키예 리그 수준 회귀)"
    if lg == "TR2":
        return half_up(tr_mean(season) - 162 + SD2 * curve(r, n)), f"튀르키예 2부 {season} {r}위 (추정, 쉬페르리그 평균 − 독일 1·2부 평균 차)"
    if lg == "TR3B":
        return half_up(tr_mean(season) - 324 + SD2 * curve(r, n)), f"튀르키예 3부 {season} 적색조 {r}위/{n}팀 (추정, 쉬페르리그 평균 − 2×독일 1·2부 평균 차)"
    if lg == "UKR1":
        return half_up(ua_mean(season) + 119 * curve(r, n)), f"우크라이나 1부 {season} {r}위 (추정)"
    if lg == "UKR2":
        return half_up(ua_mean(season) - 162 + SD2 * curve(r, n)), f"우크라이나 2부 {season} {r}위/{n}팀 (추정)"
    if lg == "QSL":
        if season == "2026-27": return QA_KNOWN[r], f"카타르 {season} {r}위 (추정, {NOW})"
        return QA_KNOWN[r], f"카타르 {season} {r}위 (추정, 마레즈 자료와 같은 리그 수준)"
    return None
RANK_LG = ["FR1", "FR2", "UKR1", "UKR2", "L1", "TR1", "TR2", "TR3B", "QSL"]

def eu(d):
    if "2020-07-01" <= d < "2020-09-01": return "2019-20"     # 코로나로 7월까지 이어진 쉬페르리그 2019-20
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}; MAN_NOTE = {}
def man2(o, s, e, lv, why): MAN[(key(o), s)] = (e, lv); MAN_NOTE[(key(o), s)] = why

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; SAME_MULTI = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if vals:
        if len(vals) > 1: SAME_MULTI.append((o, d, dict(vals)))
        (e, lv), _ = vals.most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    k = key(o); s0 = eu(d)
    if (k, s0) in MAN:
        e, lv = MAN[(k, s0)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    if (k, s0) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, s0)]).most_common(1)[0]
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s0); return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, s0), {})
        if k in t:
            r, n, _ = t[k]
            r = RANK_FIX.get((lg, s0, k), r)
            res = rank_model(lg, s0, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], (lg, s0, r, n)); return res
    MISS.append((o, d, cid, s0)); return 0, "?"

exec(open(os.path.join(HERE, "man_belhanda.py"), encoding="utf-8").read()) if os.path.exists(os.path.join(HERE, "man_belhanda.py")) else None

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(2014-08 뒤 TM 단독 도움):", u)
if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
if (UNDECIDED or MISS) and "--force" not in sys.argv: sys.exit(1)

if "--debug" in sys.argv:
    print(ELO_SRC)
    for x in SAME_MULTI: print("같은 경기 값 여럿", x)
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]): print(d, o, v)
    print("보간", sorted(INTERP_USED)); sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    for j in judg: print(j)
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []; FM_N = 0
for gid in GA_GAMES:
    tm = [e for e in EVS[gid] if e["scorer_id"] == ME and not is_og(e)]
    if not tm: continue
    fm_all = [r for r in FME.get(gid, []) if r["pen_shootout_event"] != "True"]
    if not any(r["scorer"] for r in fm_all): continue
    fm = [r for r in fm_all if (r["belhanda_scorer"] == "1" or "Belhanda" in r["scorer"]) and r["ownGoal"] not in ("1", "True") and (r["goalDescriptionKey"] or "") != "owngoal"]
    FM_N += 1
    if len(tm) != len(fm): FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        a = mins(t["minute"])[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
        if abs(a - b) > 1 and not (t["minute"].startswith(("90+", "45+")) and int(f["time"]) in (45, 90)): FM_CMP.append(("분 다름", gid, ldate(G[gid]), t["minute"], f["time"], f["overloadTime"]))
        fpk = (f["suffix"] or "").lower().startswith("pen") or "pen" in (f["goalDescriptionKey"] or "").lower()
        if (t["goal_desc"] == "Penalty") != fpk: FM_CMP.append(("PK 표기 다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["suffix"], f["goalDescriptionKey"]))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or ((a[14] if len(a) > 14 else 0) or 0) != ((b[14] if len(b) > 14 else 0) or 0): d.append(f"단판/합산 {a[7]}{a[14] if len(a) > 14 else ''}/{b[7]}{b[14] if len(b) > 14 else ''}")
    if a[10] != b[10]: d.append("연장")
    return d
def same_opp(x, r): return key(x[1]) == key(r[1]) or bool(toks(x[1]) & toks(r[1]))
CROSS = []
TEAMN = {"969": "Montpellier HSC", "338": "Dynamo Kyiv", "33": "FC Schalke 04", "417": "OGC Nice", "141": "Galatasaray",
         "3840": "Adana Demirspor", "10775": "Al-Shamal SC", "4630": "Al-Sailiya SC"}
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Belhanda", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움→벨한다 골", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_opp(x, r)]
            if hit: CROSS.append(("벨한다 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_opp(x, r):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회/합산 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
    for r in E:
        g = [x for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
        for x in oe:
            if x[9] == r[9] and toks(x[1]) & toks(TEAMN[g["club_id"]]):
                CROSS.append(("상대 팀 선수 같은 경기 기록", b, r[9], x[0], x[4], x[5], x[6], "벨한다 행", r[0], r[4], r[5], r[6]))
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0].startswith("도움 제외") and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_opp(x, [0, j[2]]):
                    CROSS.append(("TM 벨한다 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("mtpbh", "2013-07-01", "몽펠리에 HSC", "2009~2013"), ("dynbh", "2016-01-06", "디나모 키이우", "2013~2016"),
         ("s04bh", "2016-08-31", "샬케 04", "2016"), ("nicbh", "2017-07-03", "OGC 니스", "2016~2017"),
         ("galbh", "2021-07-01", "갈라타사라이", "2017~2021"), ("adabh", "2024-01-26", "아다나 데미르스포르", "2021~2023"),
         ("shabh", "2026-01-14", "알샤말", "2024~2026"), ("salbh", None, "알사일리야", "2026~")]
TM_CLUB = {"969": "mtpbh", "338": "dynbh", "33": "s04bh", "417": "nicbh", "141": "galbh", "3840": "adabh", "10775": "shabh", "4630": "salbh"}
def club_of(d):
    for k, u, n, y in CLUBS:
        if u is None or d < u: return k
CN = {k: n for k, u, n, y in CLUBS}
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
def season_of(d, club):
    y = int(d[:4])
    if club == "galbh" and "2020-07-01" <= d < "2020-09-01": return "2019-20"
    if club in ("mtpbh", "dynbh", "adabh", "galbh"): s = y if d[5:] >= "07-10" else y - 1
    else: s = y if int(d[5:7]) >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CN)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for es in EVS.values() for e in es if e["gameId"] in G and e["assist_id"] == ME and e["scorer_id"] != ME)
SEASONS = collections.Counter(season_of(m[0], club_of(m[0])) for m in M)
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), dict(SRC_A), N_TM_A)
    print("FotMob 골 대조", FM_N, FM_CMP)
    for c in CROSS: print(c)
    print(sorted(SEASONS.items()))
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_belhanda import make_note
NOTE = make_note(globals())
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elk", "elq", "ecq", "lg", "MAN", "clg", "elg"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6], r[13])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mdates = collections.Counter(m[0] for m in M)
for d, rs in by.items():
    ar = sorted(rs, key=lambda r: r[4])
    for a, b in zip(ar, ar[1:]):
        if b[5] < a[5] or b[6] < a[6]: problems.append(("시간순 스코어 역순", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
    if r[4] > 90 and not r[10] and not r[11]: problems.append(("90분 넘는데 표기 없음", r))
    g = [x for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
    m = [x for x in M if x[0] == r[9] and x[1] == r[1]][0]
    if m[2] != r[3]: problems.append(("대회 다름", r[9], r[1], m[2], r[3]))
    dur = int(g["gameDuration"])
    if g["isStarting"] == "True": lo, hi = 0, m[3] + 8
    else: lo, hi = dur - m[3] - 8, dur + 10
    if r[11] and str(r[11]).startswith("90+") and g["isStarting"] == "True" and m[3] >= 85: hi = max(hi, r[4])   # 2026.9.10 알사드전 90+10분(FotMob 90+10 같음)
    if not (lo <= r[4] <= hi): problems.append(("출전 구간 밖 기록", r[9], r[4], g["isStarting"], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const BLH_E={J(E)};\nconst BLH_M={J(M)};\nconst BLH_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "assist_sources": SRC_A,
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}, "man_notes": {f"{k[0]}|{k[1]}": v for k, v in MAN_NOTE.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} · 도움 {dict(SRC_A)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
