#!/usr/bin/env python3
"""Steven Gerrard: raw/ -> gerrard.json + src/data/ger.js (판정 근거는 judgments.md)

  python3 players/gerrard/build_gerrard.py          # 쓰기
  python3 players/gerrard/build_gerrard.py --debug  # Elo 출처
  python3 players/gerrard/build_gerrard.py --fm     # FotMob 골 대조
  python3 players/gerrard/build_gerrard.py --cross  # 동료(토레스·수아레스·스털링) 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/{tor,sua,ste}.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "ger.js")
OUT_JSON = os.path.join(HERE, "gerrard.json")
ME = "스티븐 제라드"
GAP = "2014-08-01"   # 도움 출처 기준일(이전 Transfermarkt, 이후 Transfermarkt∩FotMob)
LIV, LAG = "31", "1061"

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
# 골 제외(Transfermarkt 리포트 골이지만 넣지 않음): gameId|분 -> 이유
EXCL_G = {
    "2225498|68": "상대 자책골(FotMob·ESPN·worldfootball: 레온 바넷 자책골, 11v11: 프리미어리그 '의심 골 위원회'가 자책골로 판정. Transfermarkt만 제라드 'Deflected shot on goal')",
}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·슈팅 리바운드는 유형으로 자동 제외)
EXCL_A = {
    "991716|45+1": "상대 자책골(라이언 버트런드)",
}
# PK 수정: Transfermarkt 리포트·API에 PK 표시가 없지만 FotMob·경기 기사가 PK로 적은 골
PK_FIX = {"1041566|40": "FotMob 'Penalty', ESPN·BBC 경기 기록 'Gerrard (pen) 40'"}
# 분 수정: Transfermarkt 리포트 분이 추가시간을 빠뜨린 골
MIN_FIX = {"945554|90": "90+1"}   # 2006 FA컵 결승 동점골: 영어 위키백과 결승 문서·경기 기록 'Gerrard 54′, 90+1′'(한 곳은 추가시간 2분째)
AUTO_EXCL_TYPES = {"Penalty: Fouled player": "PK 유도", "Shot on goal": "슈팅 리바운드(Shot on goal)"}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {}
# FotMob에만 있는 도움(넣지 않음)
FM_ONLY = [
    "2012.12.9 웨스트햄전 11분 글렌 존슨 골(Transfermarkt 도움 없음)",
    "2014.5.5 크리스털 팰리스전 53분 스터리지 골(Transfermarkt 도움 없음)",
]

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "MLS1"}
CUP = {"FAC", "CGB", "MLSP"}   # MLSP = US 오픈컵(Transfermarkt 대회 id, 그리즈만 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth"): return "dk"   # FA컵 6라운드 = 8강
        return "dc"
    if cid in ("GBCS", "USC"): return "df"
    if cid == "KLUB": return "cwc"
    if cid == "POUS":
        if r.startswith("semi") or r.startswith("conference final"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
        return "mlp"
    if cid == "CCL":
        if r.startswith("semi"): return "cccsf"
        if r.startswith("final"): return "cccf"
        if r.startswith("quarter"): return "ccck"
        return "ccc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2001-02 2차 조별(Group 2) 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid in ("UEFA", "EL"):
        if cid == "UEFA" and r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # UEFA컵 2·3라운드·16강·8강, 유로파 32강(TM 'Second Round'·'intermediate stage')·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

OTHER_LEG = {}

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]
    leg = 1 if "1st" in g["round"].lower() else 2
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[OTHER_LEG.get(gid) or TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    ag, et = 1, 1
    if cid == "CCL": et = 0          # 북중미 챔스: 원정 다득점 있고 연장 없이 승부차기
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
MANUAL_ALIAS = {
    "inter milan": "inter", "fc copenhagen": "fc kobenhavn",
}
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
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0].split("(")[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

def median(xs):
    xs = sorted(xs); n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

# 프리미어리그: 기존 자료 시즌별 순위값(2002-03~2014-15 완전). 빈 순위(1998-99~2001-02 일부)는 2003-04 순위별 값에
# 같은 시즌 기존 값과의 차이(중앙값)를 더함(에투 라리가와 같은 방식)
PL_BASE = ents_map("프리미어리그", "2003-04")
assert len(PL_BASE) == 20
def premier(season, r):
    m = ents_map("프리미어리그", season)
    if r in m: return m[r], False
    sh = median([v - PL_BASE[k] for k, v in m.items()])
    return int(round(PL_BASE[r] + sh)), True
# 챔피언십(24팀): 기존 자료의 고정 순위값(2004-05~2015-16 모두 같음, '챔피언십'·'챔피언십(2부)' 라벨)
CH = {1: 1761, 2: 1717, 3: 1689, 4: 1669, 5: 1656, 6: 1648, 7: 1642, 8: 1635, 9: 1626, 10: 1617, 11: 1607, 12: 1600,
      13: 1594, 14: 1589, 15: 1584, 16: 1580, 17: 1578, 18: 1572, 19: 1564, 20: 1555, 21: 1547, 22: 1542, 23: 1537, 24: 1527}
# 리그 원(24팀): 기존 자료 순위값(다수값), 빈 순위(13·16위 등)는 앞뒤 순위값 사이 선형 보간(추정)
L1 = {3: 1555, 4: 1539, 6: 1522, 7: 1518, 8: 1513, 9: 1506, 11: 1491, 12: 1485, 14: 1477, 15: 1473, 18: 1464, 19: 1457,
      20: 1450, 22: 1440, 23: 1436, 24: 1428}
# 리그 투(24팀): 기존 자료 순위값(다수값), 빈 순위는 보간(추정)
L2 = {2: 1460, 6: 1406, 7: 1403, 8: 1396, 12: 1368, 19: 1359, 22: 1335}
def interp(tab, r):
    if r in tab: return tab[r], False
    ks = sorted(tab)
    lo = max([k for k in ks if k < r], default=None); hi = min([k for k in ks if k > r], default=None)
    if lo is None: lo, hi = ks[0], ks[1]
    if hi is None: lo, hi = ks[-2], ks[-1]
    return int(round(tab[lo] + (tab[hi] - tab[lo]) * (r - lo) / (hi - lo))), True
# MLS(20팀): 기존 자료 고정 순위값(2015·2016 같음; 전체 순위)
MLS = {}
for s in ("2015", "2016"):
    for r, v in ents_map("MLS", s).items(): MLS.setdefault(r, v)

def model(lg, season, r, n):
    """(Elo, lv) — 순위표 + 리그 모형"""
    if lg == "GB1":
        v, it = premier(season, r)
        return v, f"프리미어리그 {season} {r}위"
    if lg == "GB2":
        assert n == 24
        return CH[r], f"챔피언십 {season} {r}위"
    if lg == "GB3":
        v, it = interp(L1, r)
        return v, f"리그 원(3부) {season} {r}위" + (" (추정, 앞뒤 순위값 사이 보간)" if it else "")
    if lg == "GB4":
        v, it = interp(L2, r)
        return v, f"리그 투(4부) {season} {r}위" + (" (추정, 앞뒤 순위값 사이 보간)" if it else "")
    if lg == "MLS1-overall":
        return MLS[r], f"MLS {season} {r}위"
    return None

RANK_LG = ["GB1", "GB2", "GB3", "GB4", "MLS1-overall"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {
    (key("Olympiacos Piraeus"), "2000-01"): (1690, "그리스 2000-01 1위 (추정, 다른 선수 자료 올림피아코스 2006-07·2007-08 1690과 같음)"),
    (key("Olympiacos Piraeus"), "2004-05"): (1690, "그리스 2004-05 1위 (추정, 다른 선수 자료 올림피아코스 2006-07·2007-08 1690과 같음)"),
    (key("Dynamo Kyiv"), "2001-02"): (1600, "우크라이나 2001-02 2위 (추정, 다른 선수 자료 디나모 키이우 2006-07 1600과 같음)"),
    (key("FC Haka"), "2001"): (1350, "핀란드 2001 3위 (추정, 다른 선수 자료 인터 투르쿠 1350과 같게)"),
    (key("Steaua Bucharest"), "2003-04"): (1500, "루마니아 2003-04 2위 (추정, 다른 선수 자료 슈테아우아 2006-07·2007-08 1500과 같음)"),
    (key("Levski Sofia"), "2003-04"): (1480, "불가리아 2003-04 2위 (추정, 다른 선수 자료 레프스키 2001-02 1480과 같음)"),
    (key("Grazer AK"), "2004-05"): (1480, "오스트리아 2004-05 2위 (추정, 다른 선수 자료 그라츠 2003-04 1480과 같음)"),
    (key("Total Network Solutions"), "2005-06"): (1200, "웨일스 2004-05 1위 (추정, 리투아니아 1위 1300보다 낮게)"),
    (key("FBK Kaunas (- 2012)"), "2005"): (1300, "리투아니아 2005 1위 (추정, 다른 선수 자료 잘기리스 리투아니아 1위 1300과 같음)"),
    (key("CSKA Sofia"), "2005-06"): (1480, "불가리아 2005-06 2위 (추정, 다른 선수 자료 레프스키 2001-02 1480과 같은 수준)"),
    (key("Deportivo Saprissa"), "2005-06"): (1480, "코스타리카·북중미 챔피언 2005 (추정, 다른 선수 자료 알라후엘렌세 1480과 같음)"),
    (key("Beşiktaş JK"), "2007-08"): (1660, "쉬페르리그 2007-08 3위 (추정, 다른 선수 자료 페네르바흐체 2007-08 1680·2008-09 4위 1640 사이)"),
    (key("Havant & Waterlooville FC"), "2007-08"): (1200, "잉글랜드 6부(콘퍼런스 사우스) 2007-08 (추정, 다른 선수 자료 잉글랜드 5부 1300보다 낮게)"),
    (key("Unirea Urziceni ( - 2011)"), "2009-10"): (1500, "루마니아 2009-10 2위 (추정, 다른 선수 자료 루마니아 상위권 1500과 같음)"),
    (key("Rabotnicki Skopje"), "2010-11"): (1300, "북마케도니아 2010-11 4위 (추정, 다른 선수 자료 라보트니치키 2011-12 1300과 같음)"),
}
# 순위가 확인된 상대를 기존 리그 순위값(시즌 조정 없는 리그·고정 순위값)으로: (key, 시즌) -> (Elo, lv)
FIXED = {
    (key("FC Porto"), "2000-01"): (1795, "포르투갈 1부 2000-01 2위"),            # 18팀 시즌 2위 값(2004-05 등)
    (key("Olympique Marseille"), "2003-04"): (1750, "리그1 2003-04 7위"),        # 리그1 7위 다수값
    (key("AS Monaco"), "2004-05"): (1825, "리그1 2004-05 3위"),                  # 리그1 3위(2003-04 값)
    (key("PSV Eindhoven"), "2006-07"): (1837, "에레디비시 2006-07 1위"),
    (key("Birmingham City"), "2001-02"): (CH[5], "챔피언십 2001-02 5위"),        # 2부 5위(영어 위키백과 2002 플레이오프 문서)
    (key("Reading FC"), "2009-10"): (CH[9], "챔피언십 2009-10 9위"),             # 2부 9위
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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    y = int(d[:4])
    if cid in ("MLS1", "POUS", "MLSP", "CCL"): seasons = [str(y)]
    elif cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "KLUB", "USC"): seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)]
    else: seasons = [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    for s in seasons:
        if (k, s) in FIXED:
            e, lv = FIXED[(k, s)]; ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, e, lv, "fixed"))
            return e, lv
    for s in seasons:
        for lg in RANK_LG:
            t = RANKS.get((lg, s))
            if t and k in t:
                r, n = t[k]
                res = model(lg, s, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model"))
                    return res
    return None

# ---------------------------------------------------------------- 출전
def opp_name(g):
    return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()   # Transfermarkt 해체 연도 꼬리표 제거

def ldate(g):
    # 리버풀: Transfermarkt 리포트 날짜(현지). LA 갤럭시: API UTC를 미국 태평양 시간으로 바꾼 날짜(리포트 날짜는 하루 늦음)
    return g["date_local"]

M = []
for g in GAMES:
    M.append([ldate(g), opp_name(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["gerrard_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa = e["gerrard_scorer"] == "1", e["gerrard_assist_other"] == "1"
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    tag = f"{gid}|{e['minute']}"
    mi, dm = minute(MIN_FIX.get(tag, e["minute"]))
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout", "golden_goal") and not tie) else 0
    d = ldate(g); opp = opp_name(g)
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int((e["penalty"] == "1" and e["goal_desc"] == "Penalty") or tag in PK_FIX), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["assist_type"] in AUTO_EXCL_TYPES:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], AUTO_EXCL_TYPES[e["assist_type"]])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if d >= GAP and tag not in ADD_CONFIRMED:
            if not any(abs(t - mi) <= 2 or abs(t - int(e["minute"].split("+")[0])) <= 2 for t in FM_ASSIST.get(gid, [])):
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k)
        if not x[4].startswith("table"): print(x)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["gerrard_scorer"] == "1" and e["own_goal"] != "1" and e["gameId"] in G and f"{e['gameId']}|{e['minute']}" not in EXCL_G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV or not FM_EV[gid]: continue
    fg = [r for r in FM_EV[gid] if r["gerrard_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)
    print("FotMob 대조 경기", sum(1 for gid in TMG if FM_EV.get(gid)))

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    t = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", t, re.S)
    return json.loads(m.group(1))
MATES = {"Fernando Torres": ("tor.js", "TOR"), "Luis Suárez": ("sua.js", "SUA"), "Raheem Sterling": ("ste.js", "STE")}
MATE_E = {nm: load_js(*v) for nm, v in MATES.items()}
CLUB_SPANS = {"Fernando Torres": ("2007-07-04", "2011-01-31"), "Luis Suárez": ("2011-01-31", "2014-07-11"),
              "Raheem Sterling": ("2012-03-24", "2015-07-01")}
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    return diffs
def nm_eq(a, b): return norm(a) == norm(b)
for nm, ent in MATE_E.items():
    lo, hi = CLUB_SPANS[nm]
    for r in E:   # 제라드 도움 → 동료 골
        if r[0] == "a" and nm_eq(r[13], nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("제라드 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:  # 동료 도움 → 제라드 골
        if x[0] == "a" and x[13] == "Steven Gerrard":
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→제라드 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:  # 같은 경기 Elo/lv/대회
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어"))]
                    if dd: CROSS.append(("같은 경기 다름", nm, r[9], r[1], dd))
                    break
    # 동료 골에 Transfermarkt 제라드 도움이 있지만 제라드 파일에 도움이 없는 경우 / 동료 골인데 제라드 도움 행이 있고 동료 파일에 골이 없는 경우
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["gerrard_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 제라드 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    # 동료 출전 기간 중 TM 동료 도움 → 제라드 골이 동료 파일에 없는 경우
    for e in EVENTS:
        if e["gerrard_scorer"] == "1" and e["gameId"] in G and nm_eq(e["assist_player"], nm):
            d = ldate(G[e["gameId"]])
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - minute(e["minute"])[0]) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움이 동료 파일에 없음", nm, d, e["minute"], e["assist_type"], e["goal_desc"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("livsg", "2015-07-01", "리버풀", "1998~2015"), ("lagsg", None, "LA 갤럭시", "2015~2016")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != {LIV: "livsg", LAG: "lagsg"}[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
POST_A = NA - PRE_A
N_UNTYPED = sum(1 for e in EVENTS if e["gerrard_assist_other"] == "1" and e["assist_type"] == "" and e["gameId"] in G
                and f"{e['gameId']}|{e['minute']}" not in EXCL_A)
SRC = ELO_SRC
NOTE_LINES = [
    f"스티븐 제라드(리버풀·LA 갤럭시)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 블랙번 로버스전 ~ {d_(M[-1][0])} 콜로라도 래피즈전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·잉글랜드 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(출전한 749경기 전부), 2010-11 이후 골·도움은 FotMob 경기 이벤트와 대조함. 유스·2군 경기는 어느 출처에도 없음",
    "경기 수는 영어·스페인어 위키백과 클럽·시즌별 기록(749경기)과 같음. 골은 영어 위키백과 통산 190골과 같고 Transfermarkt(191골)보다 1골 적음(아래 노리치전). 영어 위키백과는 2011-12 FA컵을 2골로 적었으나 Transfermarkt·FotMob·스페인어 위키백과는 1골(2012.1.6 올덤전 PK)이고 다른 골의 경기별 근거가 없어 1골로 둠. 스페인어 위키백과 2003-04 5골·2012-13 12골은 다른 출처와 달라 쓰지 않음",
    "골: 2012.9.29 노리치전 68분 골은 Transfermarkt만 제라드 골('굴절 슈팅')로 적고 FotMob·ESPN·worldfootball은 레온 바넷 자책골, 11v11은 프리미어리그 의심 골 위원회가 자책골로 판정했다고 적어 넣지 않음(영어 위키백과 2012-13 리그 9골과도 맞음). Transfermarkt 리포트의 제라드 자책골 3개(2005.2.27 리그컵 결승, 2012.12.9 웨스트햄전, 2014.10.19 QPR전)는 상대 골이라 당연히 뺌",
    f"PK 골 {NPK}개 = Transfermarkt 골 유형 'Penalty' 46 + 2010.8.5 라보트니치키전 40분 골(Transfermarkt는 유형 없음, FotMob·ESPN·BBC 경기 기록은 PK). 'Penalty rebound'(PK가 막힌 뒤 리바운드 골) 3개(2006.12.9 풀럼전 54분, 2007.12.11 마르세유전 4분, 2009.5.9 웨스트햄전 37분)는 일반 골로 셈(선수 경기 성적의 PK 골 수와도 같음). 2010-11 이후 골은 FotMob과 스코어·PK가 모두 같음(FotMob 경기 기록이 없는 2011년 1~3월 5경기는 Transfermarkt만 근거)",
    f"도움: 2014.8.1 이전은 Transfermarkt 경기 리포트 도움, 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것만 씀. 도움 {NA} = Transfermarkt 171 − PK 유도 6(2004.4.24 머피, 2006.8.19·2007.2.24 파울러, 2007.10.20 카위트 PK와 LA 갤럭시 2015.7.18·2016.9.25 킨 PK) − 슈팅 리바운드 2(2003.12.13 헤스키, 2010.3.18 토레스, 'Shot on goal') − 상대 자책골에 준 도움 1(2010.1.13 레딩전 45+1분 버트런드 자책골)",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(2010-11 이전은 FotMob 경기 기록이 없음). 도움 유형 칸이 빈 {N_UNTYPED}개도 일반 도움으로 셈. 2010-11~2013-14에 Transfermarkt에만 있는 도움(2011.1.1 볼턴전 90+2분 조 콜, 2011.2.6 첼시전 69분 메이렐레스, 2012.10.31 스완지전, 2012.11.22 영 보이스전, 2013.8.27 노츠 카운티전)도 이 기준으로 넣음",
    f"2014.8.1 이후 도움 {POST_A}개는 모두 FotMob도 제라드 도움으로 적음. FotMob 경력 합계의 LA 갤럭시 12도움은 경기 이벤트 합계와 다름",
    "Transfermarkt 리포트가 본인 PK 골에 본인 도움으로 적은 2개(2005.7.26 카우나스전 54분, 2009.3.14 맨유전 43분)는 도움이 아님 — 선수 경기 성적 수치와 리포트 수치가 다른 두 경기가 이 둘이며 선수 경기 성적 쪽(도움 아님)과 같음",
    "FotMob에만 있는 도움 2개는 넣지 않음: " + "; ".join(FM_ONLY),
    "날짜는 현지 날짜. 리버풀 경기는 Transfermarkt 리포트 날짜(선수 경기 성적의 옛 시각 49경기는 하루 앞서 있어 쓰지 않음), 2005.12 클럽 월드컵(요코하마)도 현지 날짜. LA 갤럭시 경기는 경기 시각을 미국 태평양 시간으로 바꾼 날짜(Transfermarkt 리포트는 저녁 경기를 하루 늦게 적음; 원정 경기도 현지 날짜와 같음)",
    "골 시각은 Transfermarkt 리포트 기준. 2006.5.13 FA컵 결승 웨스트햄전 동점골은 Transfermarkt가 90분으로 적었으나 경기 기록(영어 위키백과 결승 문서 등)이 추가시간 90+1분으로 적어 90+1분으로 둠(FotMob 경기 기록 없음)",
    "출전 분: Transfermarkt 그대로(퇴장 4경기 포함). 2001.5.16 UEFA컵 결승(알라베스, 연장 골든골 5-4)은 117분, 2005.5.25 챔스 결승(밀란, 3-3 뒤 승부차기)은 120분",
    "상대 Elo는 같은 경기를 다룬 다른 선수 자료(토레스·수아레스·스털링 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 순위값에 넣은 값 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+기존 순위값 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "프리미어리그는 다른 선수 자료의 시즌별 순위값(2002-03 이후 완전). 1998-99~2001-02의 빈 순위(2000-01 2위 아스널·15위 웨스트햄)는 2003-04 순위별 값에 같은 시즌 다른 순위 값과의 차이(중앙값)를 더함. 챔피언십(2부)·리그 원(3부)·리그 투(4부)는 다른 선수 자료의 순위별 고정값을 쓰고, 그 값이 없는 순위(리그 원 2000-01 13위 위컴·2011-12 16위 올덤, 리그 투 2014-15 15위 AFC 윔블던)는 앞뒤 순위값 사이 보간(추정). 버밍엄 2001-02(2부 5위)·레딩 2009-10(2부 9위) 순위는 Transfermarkt 순위표를 받지 못해 영어 위키백과·구단 기록 사이트로 확인",
    "MLS는 다른 선수 자료의 2015·2016 전체 순위별 값(동·서부 콘퍼런스 표를 승점·승수·득실차·다득점으로 합친 순위). 리그1·에레디비시·포르투갈 1부 상대(마르세유 2003-04 7위, 모나코 2004-05 3위, PSV 2006-07 1위, 포르투 2000-01 2위)는 다른 선수 자료의 같은 순위 값",
    "직접 추정(모두 '추정'): 올림피아코스 2000-01·2004-05(그리스 1위) 1690, 디나모 키이우 2001-02(우크라이나 2위) 1600, 하카 2001(핀란드 3위) 1350, 슈테아우아 부쿠레슈티 2003-04(루마니아 2위) 1500, 레프스키 소피아 2003-04(불가리아 2위) 1480, 그라츠 AK 2004-05(오스트리아 2위) 1480, 토털 네트워크 솔루션스 2005(웨일스 1위) 1200, 카우나스 2005(리투아니아 1위) 1300, CSKA 소피아 2005(불가리아 2위) 1480, 사프리사 2005(코스타리카·북중미 챔피언) 1480, 베식타시 2007-08(튀르키예 3위) 1660, 해번트 앤드 워털루빌 2007-08(잉글랜드 6부) 1200, 우니레아 우르지체니 2009-10(루마니아 2위) 1500, 라보트니치키 2010(북마케도니아 4위) 1300 — 모두 다른 선수 자료의 같은 리그 비슷한 순위 값에 맞춤",
    "대회 비중: FA컵·리그컵·US 오픈컵은 국내컵(FA컵 5라운드·리그컵 16강까지 낮은 비중, FA컵 6라운드·리그컵 8강 이후 높은 비중, 재경기도 같은 라운드), 커뮤니티 실드·UEFA 슈퍼컵은 국내컵 결승, 2005 FIFA 클럽 월드 챔피언십은 클럽 월드컵, UEFA컵 1라운드는 유로파 예선, UEFA컵 2·3라운드·16강·8강과 유로파 32강·16강·8강은 유로파 토너먼트, 챔스 2001-02 2차 조별리그는 챔스 조별, MLS 컵 플레이오프는 MLS 플레이오프, 북중미 챔스 8강은 북중미 챔스 8강 이후로 계산함. 2001 UEFA컵 결승(골든골 연장)은 다른 단판 연장 경기와 같이 계산(골든골 규칙은 반영하지 않음)",
    f"두 경기 합산(UEFA 대회 예선·토너먼트, 리그컵 준결승) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회·리그컵 준결승(2017-18까지 규칙)에 적용, 연장 있음. 2003.1.21 셰필드 유나이티드전 107분 오언 골 도움은 2차전 연장 기록",
    "2차전 기록의 1차전 스코어는 Transfermarkt 경기 리포트로 채움. 제라드가 뛰지 않은 1차전은 2005.2.22 레버쿠젠전(3-1)·2010.7.29 라보트니치키전(2-0)",
    "시즌 구분: 리버풀은 7월 10일 기준(2005.7.13~7.26 챔스 1·2차 예선 TNS·카우나스전이 2005-06 시즌), LA 갤럭시는 달력 연도. 리버풀의 다른 7월 공식 경기는 없어 토레스·수아레스·스털링 자료와 같은 경기는 모두 같은 시즌으로 잡힘. 클럽 구분은 2015.7.1 전 리버풀, 이후 LA 갤럭시",
    "같은 경기 동료 자료: 토레스(제라드 도움 13·토레스 도움 7)·수아레스(제라드 도움 8·수아레스 도움 4)와 주고받은 골·도움은 날짜·분·골 전 스코어·대회·상대 Elo·수준 설명·합산 정보가 모두 같음. 스털링과 주고받은 골·도움은 없음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 챔스 2004-05, UEFA컵 2000-01, UEFA 슈퍼컵 2회(2001·2005), FA컵 2회(2001·2006), 리그컵 3회(2001·2003·2012), 커뮤니티 실드 2회(2001·2006). 준우승: 챔스 2006-07, 리그컵 2004-05. 개인: UEFA 올해의 클럽 선수 2005, FWA 올해의 선수 2009, PFA 올해의 선수 2005-06. 잉글랜드 대표팀 기록은 뺌",
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
        if b[0] < a[0] or b[1] < a[1]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
mm = {m[0]: m for m in M}
for r in E:
    m = mm.get(r[9])
    if m and m[1] != r[1]: problems.append(("상대 이름 다름", r[9], r[1], m[1]))
    if m and m[2] != r[3]: problems.append(("대회 다름", r[9], r[3], m[2]))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const GER_E={J(E)};\nconst GER_M={J(M)};\nconst GER_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
