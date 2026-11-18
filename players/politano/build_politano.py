#!/usr/bin/env python3
"""Matteo Politano: raw/ -> politano.json + src/data/pol.js (판정 근거는 judgments.md)

  python3 players/politano/build_politano.py            # 파일 쓰기
  python3 players/politano/build_politano.py --debug    # Elo 출처 목록
  python3 players/politano/build_politano.py --fm       # FotMob 골 대조(2013-14 이후)

입력: raw/tm_games.csv(출전 581경기), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(Transfermarkt 순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다. 베라르디 빌드 스크립트와 같은 구조.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "pol.js")
OUT_JSON = os.path.join(HERE, "politano.json")
ME = "마테오 폴리타노"
GAP = "2014-08-01"   # 도움 출처 기준일(이전 Transfermarkt, 이후 Transfermarkt∩FotMob 또는 다른 출처 2곳)
CUTOFF = "2026-11-18"
CLUBS = {"839": "페루자", "2921": "페스카라", "6574": "사수올로", "46": "인테르", "6195": "나폴리"}

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
EXCL_G = {}

# 도움 제외(Transfermarkt 리포트·선수 경기 성적이 도움으로 셌지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    # 상대 자책골에 준 도움
    "2359800|49": "상대 자책골(2014.1.25 유베 스타비아전 기링헬리 자책골, 크로스)",
    "3462349|41": "상대 자책골(2020.11.26 리예카전 아나스타시오 자책골 — 폴리타노 슈팅이 수비 맞고 들어감, 'Shot on goal'; FotMob은 폴리타노 골로 적었으나 UEFA 정정·Sky Sports·ESPN·Sky Sport Italia 모두 아나스타시오 자책골)",
    "3433408|75": "상대 자책골(2021.2.21 아탈란타전 고젠스 자책골, 크로스)",
    "4171249|9": "상대 자책골(2023.12.12 브라가전 사아트치 자책골, 패스)",
    # PK 유도(동료 PK 골)
    "2359735|49": "PK 유도(2013.11.30 카르피전 마니에로 PK 골, 'Penalty: Fouled player')",
    "2569553|74": "PK 유도(2015.5.26 승격 플레이오프 페루자전 비아르드나손 PK 골)",
    "3660443|75": "PK 유도(2021.11.4 레기아전 메르턴스 PK 골)",
    "4103490|16": "PK 유도(2023.8.27 사수올로전 오시멘 PK 골)",
    "4373977|63": "PK 유도(2024.10.20 엠폴리전 크바라츠헬리아 PK 골)",
    # 슈팅 리바운드('Shot on goal')
    "2740236|17": "슈팅 리바운드(2016.8.18 유로파 예선 츠르베나 즈베즈다전 베라르디 골, 'Shot on goal' — 폴리타노 슈팅을 막은 공을 베라르디가 밀어 넣음)",
    "2765908|83": "슈팅 리바운드(2016.11.24 유로파 조별 빌바오전 라구사 골, 'Shot on goal'; FotMob은 도움으로 적었으나 슈팅 리바운드는 도움 아님 규칙)",
    # 2014.8.1 이후 Transfermarkt 단독(FotMob 세리에B 2014-15·코파 이탈리아 도움 자료 없음), 다른 출처 2곳이 확인하지 못함
    "2484403|3": "2014.8 이후 Transfermarkt 단독(2014.8.17 코파 이탈리아 레나테전 카프라리 3분 골, 도움 유형 빈칸). FourFourTwo는 카프라리 골만 적고 도움자 없음, ESPN 자료 없음",
    "2482934|8": "2014.8 이후 Transfermarkt 단독(2014.9.23 라티나전 멜키오리 8분 골). latinapress.it 1곳만 '폴리타노 도움', 두 번째 출처 못 찾음",
    "2483054|84": "2014.8 이후 Transfermarkt 단독(2014.12.6 프로 베르첼리전 빅토르 84분 골). 경기 기사에 도움자 없음",
    "2483164|62": "2014.8 이후 Transfermarkt 단독(2015.2.28 엔텔라전 산소비니 62분 골). Forza Italian Football 1곳만 '폴리타노의 스루패스', Blitz quotidiano(LaPresse) 기사는 도움자 없음",
    "2483193|64": "2014.8 이후 Transfermarkt 단독(2015.3.14 카르피전 비아르드나손 64분 골, 프리킥). Forza Italian Football은 '오른쪽 프리킥이 모두를 지나 비아르드나손'만 적고 키커 없음",
    "2483220|4": "2014.8 이후 Transfermarkt 단독(2015.4.2 브레시아전 메무샤이 4분 골). 경기 기사에 도움자 없음",
}
ADD_CONFIRMED = {}   # 2014.8 이후 FotMob에 없지만 다른 출처 2곳이 확인한 도움 — 없음
ADD_FM = {}          # FotMob 단독 도움 중 다른 출처 2곳이 확인한 것 — 없음
# FotMob 단독 도움(Transfermarkt 없음)으로 넣지 않은 것: tm gameId -> 이유
FM_ONLY_EXCL = {
    "2726510": "2016.9.18 제노아전 66분 드프렐 골: FotMob·LaPresse('폴리타노 크로스')는 폴리타노, ESPN(Opta) 문자 중계는 '페루소 크로스 도움' → 출처가 갈려 독립 출처 2곳 없음",
    "2726835": "2017.5.21 칼리아리전 7분 마냐넬리 골: FotMob만 폴리타노, Transfermarkt·ESPN(Opta)은 베라르디 코너킥 도움 → 반대 출처",
    "3081403": "2019.5.26 엠폴리전 51분 케이타 골: FotMob·ESPN(Opta) 같은 계열 자료만 폴리타노 도움, 인테르 공식 경기 기사는 '이카르디의 움직임을 이용한 케이타 중거리'로 폴리타노를 적지 않음 → 독립 출처 2곳 없음",
}
# FotMob만 폴리타노 골로 적은 것(넣지 않음)
FM_ONLY_GOAL_EXCL = {"3462349": "2020.11.26 리예카전 41분: Transfermarkt·UEFA 정정·Sky Sports·ESPN = 아나스타시오 자책골"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "IT3B", "IT3P", "POSB"}   # 레가 프로·세리에B 승격 플레이오프는 리그 비중(브루노·카소를라 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("CIT", "SCI"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 1~4라운드·16강
    if cid == "CILP": return "dc"   # 코파 이탈리아 레가 프로 조별(인시녜 선례)
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 32강(intermediate stage)·16강
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 조별·리그 페이즈
        if r.startswith("last 16") or r.startswith("intermediate"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE and g["competitionId"] != "POSB": return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스·유로파 조별/리그 페이즈, 레가 프로 컵 조별
    return 1   # 코파 이탈리아·수페르코파 단판, 세리에B 플레이오프 예비 라운드 단판

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = ldate(g)
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    if cid in ("CL", "EL", "ELQ"):
        ag, et = int(d < "2021-07-01"), 1   # UEFA: 2021-22부터 원정 다득점 없음
    elif cid == "CIT":
        ag, et = int(d < "2022-07-01"), 1
    else:
        sys.exit("합산 규칙 없음 " + cid + " " + gid)
    return [leg, home, fu, ft, ag, et]

# ---------------------------------------------------------------- 이름 정규화·상대 Elo
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
MANUAL_ALIAS = {"inter milan": "inter", "ac parma": "parma calcio 1913", "parma ac": "parma calcio 1913",
                "cesena fc": "ac cesena"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

with open(os.path.join(ELO, "ents.json"), encoding="utf-8") as f:
    ENTS = [x for x in json.load(f) if x["p"] != ME]

def season_eu(d):
    """상대 Elo 시즌: 7월 이후는 새 시즌, 다만 코로나로 미뤄진 2020년 7~8월 경기는 2019-20"""
    if "2020-07-01" <= d < "2020-09-01": return "2019-20"
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))

# 세리에A 20팀 순위값(기존 자료) → 표준 곡선(디 나탈레·베라르디 스크립트와 같음)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

def ents_map(prefix, season, suffix=""):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위" + re.escape(suffix) + "$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

SB_MEAN, SB_SD = 1577.78, 51.24   # 세리에B(문서 4절)
C1_MEAN = 1416.56                 # 세리에C(레가 프로 1, 3부): 인시녜·디 나탈레 자료와 같은 모형
C2_MEAN = 1255.34                 # 레가 프로 2(4부): 인시녜·디 나탈레 자료와 같은 모형

def model(lg, season, r, n):
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        assert n == 20, (season, n)
        return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "IT2":
        m = ents_map("세리에B", season)
        if r in m: return m[r], f"세리에B {season} {r}위"
        return int(round(SB_MEAN + SB_SD * curve(r, n))), f"세리에B {season} {r}위"
    if lg in ("IT3A", "IT3B"):
        grp = lg[-1]
        return int(round(C1_MEAN + SB_SD * curve(r, n))), f"세리에C(레가 프로 1) {grp}조 {season} {r}위/{n}팀 (추정)"
    if lg == "IT4Y":
        return int(round(C2_MEAN + SB_SD * curve(r, n))), f"레가 프로 2(4부) B조 {season} {r}위/{n}팀 (추정)"
    return None

RANK_LG = ["IT1", "IT2", "IT3B", "IT3A", "IT4Y"]
# 직접 지정(모두 '추정'): 같은 리그·시즌 다른 선수 자료(일리치치 레가 프로 1 A조 2012-13 7위/17팀 = 18팀 조 7위 값)와 같은 방식
MAN = {
    (key("US Lecce"), "2012-13"): (1498, "세리에C(레가 프로 1) A조 2012-13 2위/17팀 (추정, 다른 선수 자료 레가 프로 1 18팀 조 2위 1498과 같음)"),
}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    for s in (eu, d[:4]):   # 달력 연도 리그(노르웨이)는 연도 키
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
        return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, eu))
        if t and k in t:
            r, n = t[k]
            res = model(lg, eu, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg))
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_tm_report"] or g["date_local_computed"]
for g in GAMES:
    if g["date_local_tm_report"] and g["date_local_tm_report"] != g["date_local_computed"]:
        sys.exit("리포트 날짜와 계산 날짜 다름 " + g["gameId"])
    if not g["playedMinutes"]: sys.exit("출전 분 없음 " + g["gameId"])
    if g["club_id"] not in CLUBS: sys.exit("모르는 클럽 " + g["gameId"])

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["politano_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, 0, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

def before(g, side_home, score_after):
    our_home = g["venue"] == "H"
    if g["gameId"] in INFO and (INFO[g["gameId"]]["home_id"] == g["club_id"]) != our_home: sys.exit("홈·원정 불일치 " + g["gameId"])
    h, a = map(int, score_after.split("-"))
    if side_home: h -= 1
    else: a -= 1
    return (h, a) if our_home else (a, h), side_home == our_home

used_excl = set()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["politano_scorer"] == "1", e["politano_assist_other"] == "1", e["politano_self_assist"] == "1"
    if iss: judg.append(("본인 PK 골의 본인 도움(도움 아님)", ldate(g), e["minute"]))
    if not (isg or isa): continue
    (gf, ga), ours = before(g, e["side"] == "home", e["score_home_away_after"])
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        if tag in EXCL_A:
            used_excl.add(tag)
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal") or e["assist_type"].startswith("Handball"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP and tag not in ADD_CONFIRMED:
            if not any(abs(t - mi) <= 3 for t in FM_ASSIST.get(gid, [])):
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)
if set(EXCL_A) - used_excl: sys.exit("쓰이지 않은 도움 제외 " + str(set(EXCL_A) - used_excl))

# FotMob 단독 도움·골이 판정 목록 밖에 없는지
for gid, evs in FM_EV.items():
    if gid not in G: continue
    for r in evs:
        t = int(r["time"]) + int(r["overloadTime"] or 0)
        if r["politano_assist"] == "1":
            tm = [e for e in EVENTS if e["gameId"] == gid and e["politano_assist_other"] == "1" and abs(minute(e["minute"])[0] - t) <= 3]
            if not tm and gid not in FM_ONLY_EXCL and gid not in ADD_FM:
                sys.exit(f"FotMob 단독 도움 판정 누락 {gid} {t}")
        if r["politano_scorer"] == "1" and r["pen_shootout_event"] != "True":
            tm = [e for e in EVENTS if e["gameId"] == gid and e["politano_scorer"] == "1" and abs(minute(e["minute"])[0] - t) <= 3]
            if not tm and gid not in FM_ONLY_GOAL_EXCL:
                sys.exit(f"FotMob 단독 골 판정 누락 {gid} {t}")

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

def sk(r):
    return (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1)
rows.sort(key=sk)
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["politano_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV: continue
    fg = [r for r in FM_EV[gid] if r["politano_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty")
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], t["score_home_away_after"], f["newScore_home_away"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 시즌·클럽별
def season_calc(d, club):
    """계산기 시즌 구분(사수올로 7월 10일 기준, 그 밖은 8월 1일 기준·2020년 8월은 2019-20)"""
    y = int(d[:4])
    if club == "6574":
        s = y if d[5:] >= "07-10" else y - 1
    else:
        if "2020-08-01" <= d < "2020-09-01": return "2019-20"
        s = y if d[5:] >= "08-01" else y - 1
    return f"{s}-{str(s + 1)[2:]}"
CLUB_OF = {ldate(g): g["club_id"] for g in GAMES}
SEASONS = collections.OrderedDict()
for m in M:
    s = season_calc(m[0], CLUB_OF[m[0]]); SEASONS.setdefault(s, [0, 0, 0, 0]); SEASONS[s][0] += 1; SEASONS[s][3] += m[3]
for r in E:
    SEASONS[season_calc(r[9], CLUB_OF[r[9]])][1 if r[0] == "g" else 2] += 1
BYCLUB = collections.OrderedDict((c, [0, 0, 0, 0]) for c in CLUBS)
for m in M: BYCLUB[CLUB_OF[m[0]]][0] += 1; BYCLUB[CLUB_OF[m[0]]][3] += m[3]
for r in E: BYCLUB[CLUB_OF[r[9]]][1 if r[0] == "g" else 2] += 1

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
POST_A = NA - PRE_A
SRC = ELO_SRC
TM_API_A = sum(int(g["assists"] or 0) for g in GAMES)
last = M[-1]
bc = lambda c: "·".join(str(x) for x in BYCLUB[c][:3])
NOTE_LINES = [
    f"마테오 폴리타노(페루자·페스카라·사수올로·인테르·나폴리)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 바를레타전 ~ {d_(last[0])} 라치오전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·대표팀(이탈리아·청소년 대표)·유스(로마 프리마베라) 경기 제외",
    f"클럽별 경기·골·도움: 페루자 {bc('839')}, 페스카라 {bc('2921')}, 사수올로 {bc('6574')}, 인테르 {bc('46')}, 나폴리 {bc('6195')}. 출전 분 합계 {MIN_TOT:,}분",
    "페루자(2012-13 임대)는 레가 프로 프리마 디비시오네 B조(3부, 이탈리아 프로 리그)라 셈: 리그 28경기·코파 이탈리아 3경기·코파 이탈리아 레가 프로 조별 2경기·승격 플레이오프 4강 피사전 2경기. 페스카라 2013-15는 세리에B(2014-15 승격 플레이오프 5경기 포함). 로마 유스(프리마베라) 경기는 빼고, 로마 1군 공식 경기는 없음. 인테르(2018.7 임대 뒤 완전 이적)·나폴리(2020.1 임대 뒤 2021.7 완전 이적)는 임대·완전 이적을 한 클럽으로 셈",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(출전 분이 빈 경기 없음, 90분으로 추정한 경기 없음), 골 시각·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부), 2013-14 이후 골·도움은 FotMob 경기 이벤트와 대조함(FotMob은 2012-13 레가 프로 리그 경기 자료가 없고, 2013-15 세리에B는 도움 자료가 없음). 위키백과(영어·이탈리아어) 클럽별 경기·골(581경기 91골)과 같음",
    "날짜는 현지(이탈리아) 날짜. 원정 유럽 대항전도 같은 날짜",
    "2016.8.28 사수올로-페스카라전(세리에A 2라운드)은 2-1로 끝났으나 사수올로가 등록 전 선수(라구사)를 내보내 0-3 몰수패 처리됨. 폴리타노는 선발 64분을 뛰고 골·도움이 없어 출전만 셈(같은 팀 다른 선수 자료와 같음)",
    f"골: Transfermarkt 리포트 골 {NGo}개를 그대로 씀(선수 경기 성적·위키백과와 같은 수). PK 골 {NPK}개는 골 유형 'Penalty' 기준(FotMob도 같은 {NPK}개). 2020.11.26 유로파리그 리예카전 41분 골은 FotMob이 폴리타노 골로 적었으나 UEFA가 아나스타시오 자책골로 정정했고 Transfermarkt·Sky Sports·ESPN·Sky Sport Italia도 자책골이라 골로 세지 않음(폴리타노 슈팅이 수비 맞고 들어간 것이라 도움도 아님). 실축 PK 4개(모두 골키퍼 선방)는 기록에 넣지 않음",
    "골 시각은 Transfermarkt 리포트 분(FotMob과 1분 안팎 차이뿐, 골 뒤 스코어는 모두 같음)",
    f"도움: 2014.8.1 이전은 Transfermarkt 경기 리포트 도움, 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것만 씀. 도움 {NA} = Transfermarkt {TM_API_A} − 상대 자책골에 준 도움 4(2014.1.25 유베 스타비아전 기링헬리, 2020.11.26 리예카전 아나스타시오, 2021.2.21 아탈란타전 고젠스, 2023.12.12 브라가전 사아트치) − PK 유도 5(2013.11.30 카르피전 마니에로, 2015.5.26 승격 플레이오프 페루자전 비아르드나손, 2021.11.4 레기아전 메르턴스, 2023.8.27 사수올로전 오시멘, 2024.10.20 엠폴리전 크바라츠헬리아) − 슈팅 리바운드 2(2016.8.18 유로파 예선 츠르베나 즈베즈다전 베라르디, 2016.11.24 유로파 빌바오전 라구사) − 2014.8 이후 Transfermarkt 단독으로 다른 출처 2곳이 확인하지 못한 6",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(페루자 2012-13 레가 프로 4개는 FotMob 자료가 없고, 2014.3.8 체세나전 주파리치 골 코너킥 도움은 FotMob 세리에B 도움 자료가 없음)",
    "다른 출처 2곳이 확인하지 못해 뺀 2014.8 이후 Transfermarkt 단독 도움 6개(모두 페스카라, FotMob은 그 시즌 세리에B·코파 이탈리아 도움 자료가 없음): 2014.8.17 코파 이탈리아 레나테전 3분 카프라리(기사에 도움자 없음), 2014.9.23 라티나전 8분 멜키오리(라티나 지역 매체 1곳만 폴리타노 도움), 2014.12.6 프로 베르첼리전 84분 빅토르, 2015.2.28 엔텔라전 62분 산소비니(Forza Italian Football 1곳만), 2015.3.14 카르피전 64분 비아르드나손(프리킥, 기사에 키커 없음), 2015.4.2 브레시아전 4분 메무샤이",
    "FotMob에만 있는 도움 3개는 넣지 않음: 2016.9.18 제노아전 66분 드프렐(LaPresse는 폴리타노 크로스, Opta 문자 중계는 페루소 크로스로 갈림), 2017.5.21 칼리아리전 7분 마냐넬리(Transfermarkt·Opta는 베라르디 코너킥), 2019.5.26 엠폴리전 51분 케이타(Opta 계열 자료만 폴리타노, 인테르 공식 기사에 없음)",
    f"상대 Elo는 같은 경기 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 기존 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']})",
    "순위는 Transfermarkt 최종 순위표. 세리에B는 다른 선수 자료와 같은 리그 모형(평균 약 1578), 레가 프로 1(3부, 2012-13 B조 16팀·A조 17팀)은 다른 선수 자료와 같은 추정 모형(평균 약 1417), 레가 프로 2(4부, 2012-13 B조 아프릴리아 3위/18팀)는 한 단계 더 내린 추정 모형(평균 약 1255)으로 모두 '추정'(근거 약함). 세리에A 2026-27은 진행 중이라 다른 선수 자료의 현재 순위값",
    "대회 비중: 코파 이탈리아는 국내컵(1~4라운드·16강은 낮은 비중, 8강 이후 높은 비중), 수페르코파 이탈리아나 4강·결승은 국내컵 4강·결승, 코파 이탈리아 레가 프로 조별은 국내컵 낮은 비중의 리그식(무승부 1점). 레가 프로·세리에B 승격 플레이오프는 리그 비중(2015.5.26 세리에B 예비 라운드 페루자 원정은 단판). 챔스 조별·리그 페이즈, 16강, 8강과 유로파 예선·조별·32강·16강은 각 단계 비중",
    f"두 경기 합산(유럽 대항전 토너먼트·예선, 코파 이탈리아 4강, 승격 플레이오프) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(UEFA 대회는 2021-22부터 원정 다득점 없음). 폴리타노가 뛰지 않은 2022.2.17 바르셀로나 원정 1차전 스코어(1-1)는 Transfermarkt 리포트로 채움. 승부차기 경기는 승부차기 골을 스코어에 넣지 않음(폴리타노 골·도움 없음)",
    "시즌 구분: 사수올로는 7월 10일 기준(2016.7.28 유로파리그 예선 루체른 원정은 2016-17), 그 밖은 8월 1일 기준, 코로나로 미뤄진 2020년 8월 경기는 2019-20",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 세리에A 우승 2022-23·2024-25, 코파 이탈리아 우승 2019-20, 수페르코파 이탈리아나 우승 2025-26(모두 나폴리). 로마 프리마베라 우승(유스)·대표팀 기록은 뺌. AIC(선수협회) 세리에A 올해의 팀·올해의 선수 명단에는 없음",
    f"2026.11.18 기준 현역(나폴리). 마지막 반영 경기 {d_(last[0])} 라치오전(세리에A, 교체 {last[3]}분, 2026.11.18 수집)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM "]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE):
        sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mdates = collections.Counter(m[0] for m in M)
for d, rs in by.items():
    gs = sorted({(r[5], r[6], r[4]) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
    for a, b in zip(gs, gs[1:]):
        if b[0] < a[0] or b[1] < a[1] or b[2] < a[2]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
    if len({(r[1], r[3]) for r in rs}) > 1: problems.append(("같은 날 상대·대회 다름", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
mm = {m[0]: m for m in M}
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r))
for m in M:
    if m[3] < 1 or m[3] > 125: problems.append(("출전 분 범위", m))
    if m[0] > CUTOFF: problems.append(("기준일 뒤", m))
api_g = collections.Counter(); api_a = collections.Counter()
for g in GAMES:
    api_g[ldate(g)] += int(g["goals"] or 0); api_a[ldate(g)] += int(g["assists"] or 0)
gcount = collections.Counter(r[9] for r in E if r[0] == "g")
for d in set(api_g) | set(gcount):
    if api_g[d] != gcount[d]: problems.append(("골 수 API와 다름", d, api_g[d], gcount[d]))
api_pk = sum(int(g["penGoals"] or 0) for g in GAMES)
if api_pk != NPK: problems.append(("PK 골 수 API와 다름", api_pk, NPK))
acount = collections.Counter(r[9] for r in E if r[0] == "a")
A_DIFF = sorted((d, api_a[d], acount[d]) for d in set(api_a) | set(acount) if api_a[d] != acount[d])
if len(A_DIFF) != len(EXCL_A): problems.append(("도움 차이 날짜 수", len(A_DIFF), len(EXCL_A)))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const POL_E={J(E)};\nconst POL_M={J(M)};\nconst POL_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg,
               "excluded_assists": EXCL_A, "fotmob_only_assists_excluded": FM_ONLY_EXCL, "fotmob_only_goal_excluded": FM_ONLY_GOAL_EXCL,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG, "seasons": SEASONS,
               "by_club": {CLUBS[c]: v for c, v in BYCLUB.items()}, "assist_count_vs_api": A_DIFF},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for c, v in BYCLUB.items(): print(" ", CLUBS[c], v)
    for k, v in SEASONS.items(): print(" ", k, v)
    print("도움 수 API와 다른 날:", A_DIFF)
