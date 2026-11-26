#!/usr/bin/env python3
"""Filip Kostić: raw/ -> kostic.json + src/data/kos.js (판정 근거는 judgments.md)

  python3 players/kostic/build_kostic.py            # 파일 쓰기
  python3 players/kostic/build_kostic.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/kostic/build_kostic.py --cross    # 동료 자료 대조
  python3 players/kostic/build_kostic.py --fm       # FotMob 골 대조
  python3 players/kostic/build_kostic.py --root=<스크래치 복사본>   # 그 복사본의 src/data에 쓰기(검증용)

찰하노을루(build_calhanoglu.py) 빌드를 바탕으로 함. 접두어 KOS(kos.js), 프리셋 id kostic.
입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
/home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):   # 스크래치 복사본에 쓰기(검증용)
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(os.path.dirname(os.path.dirname(HERE)), "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "kos.js")
OUT_JSON = os.path.join(HERE, "kostic.json")
ME = "필립 코스티치"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트, 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
OTHER = {r["gameId"]: r["other_leg_id"] for r in rd("tm_two_leg_ties.csv")}
for gid, r in INFO.items():
    if r["other_leg_id"]:
        OTHER.setdefault(gid, r["other_leg_id"]); OTHER.setdefault(r["other_leg_id"], gid)
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
# 출전 분 고침: gameId -> (분, 근거)  (없음: Transfermarkt 출전 분 그대로)
MIN_FIX = {}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'·자책골은 일반 규칙)
EXCL_A = {
    "2460706|84": "2014.10.25 프랑크푸르트전 84분 겐트너 골(5:4 결승골): FotMob 도움 없음, Sports Mole 경기 기사는 프리킥이 문전에서 흐른 공을 겐트너가 밀어 넣었다고 적음(흐른 공), 코스티치 도움을 적은 다른 출처 없음",
    "3058470|46": "2018.10.7 호펜하임전 46분 요비치 골: FotMob 도움 없음, 코스티치 도움으로 적은 곳은 mondefootball(worldfootball 계열) 1곳뿐",
    "3195531|82": "2019.8.11 발트호프 만하임전(DFB-포칼) 82분 레비치 골: FotMob 도움 없음, 코스티치 도움으로 적은 곳은 Fox Sports 경기 기록 1곳뿐(80분 표기)",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳 이상이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2754874|8": "DFB 데이터센터 경기 기록(8분 우드 오른발, 코스티치) · Vavel 경기 기사(코스티치가 라소가와 2:1 패스 뒤 우드에게 내줌)",
    "3825617|4": "교도통신 기사(nippon.com 게재: 코스티치 크로스를 가마다가 마무리) · 로이터 기사(Malay Mail 게재) · SportsBrief 경기 기사(코스티치가 왼쪽을 돌파해 가마다에게 크로스)",
}
# FotMob에만 있는 도움(넣지 않음) — judgments.md 4절
FM_ONLY_DECIDED = {}

# ---------------------------------------------------------------- 대회 코드
# PONL(에레디비시 유럽 대항전 플레이오프)은 리그 비중 + 두 경기 합산(수아레스·메르턴스·스네이더르·마카이·외데고르 선례)
LEAGUE = {"SER1", "SER2", "NL1", "L1", "IT1", "TR1", "PONL"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("DFB", "CIT", "SERP", "NLP", "TRP"):   # 국내컵: 16강까지 dc / 8강 dk / 준결승 dsf / 결승 df (튀르키예컵 조별도 dc)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "ELQ": return "elq"
    if cid == "CL":
        if r.startswith("group"): return "clg"          # 조별·2024-25부터 리그 단계
        if r.startswith("intermediate"): return "cl16"  # 2025-26 챔스 녹아웃 플레이오프 = 16강(docs 3절)
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # intermediate stage(32강)·16강·8강
    if cid == "KLUB": return "cwc"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 튀르키예컵 조별·클럽 월드컵 2025 조별은 리그식
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local_computed"]
    leg = 1 if "1st" in g["round"].lower() else 2
    o = INFO[OTHER[gid]]
    if (o["date_report"] < inf["date_report"]) != (leg == 2): sys.exit("차전 순서 이상 " + gid)
    home = int(inf["home_id"] == g["club_id"])
    if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    fu = ft = 0
    if leg == 2:
        oh, oa = map(int, re.match(r"(\d+):(\d+)", o["final"]).groups())
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "EL", "ELQ"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CIT":   # 코파 이탈리아 준결승: 원정 다득점 2021-22까지, 2차전 연장
        ag = int(d < "2022-07-01"); et = 1
    elif cid == "PONL":   # 네덜란드 유럽 플레이오프: 원정 다득점·연장(docs 3절)
        ag, et = 1, 1
    else:
        sys.exit("합산 규칙 없음 " + cid)
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
MANUAL_ALIAS = {}
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
    if d[:7] in ("2020-07", "2020-08"): s = 2019   # 코로나로 늦게 끝난 2019-20 시즌
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

def mid(tab, r):
    """기존 순위값에 없는 순위는 앞뒤 기존 값의 단순 중간값(병렬 판정과 맞추기 위한 규칙)"""
    if r in tab: return tab[r], False
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return int((tab[lo] + tab[hi]) / 2 + 0.5), (lo, hi)

def known(prefix, season):
    """기존 선수 자료 lv '<prefix> <season> N위'의 순위별 값(가장 많이 쓴 값)"""
    t = {}
    for x in ENTS:
        m = re.fullmatch(re.escape(prefix) + " " + season + r" (\d+)위", x["lv"])
        if m: t.setdefault(int(m.group(1)), collections.Counter())[x["elo"]] += 1
    return {k: v.most_common(1)[0][0] for k, v in t.items()}

# 2. 분데스리가: 기존 선수 자료의 순위값(시즌 무관 같은 값)
L2_KNOWN = {1: 1697, 2: 1667, 3: 1636, 4: 1622, 5: 1615, 6: 1609, 7: 1600, 8: 1592, 9: 1584, 10: 1579,
            11: 1574, 12: 1570, 13: 1568, 14: 1561, 15: 1544, 16: 1545, 17: 1541, 18: 1532}
# 3. 리가: 기존 선수 자료의 순위값(시즌 무관; 찰하노을루 자료와 같은 표)
L3_KNOWN = {1: 1557, 2: 1513, 4: 1479, 5: 1462, 6: 1456, 7: 1448, 8: 1437, 9: 1429, 10: 1422, 11: 1418,
            12: 1414, 13: 1409, 14: 1406, 15: 1403, 17: 1379, 18: 1374, 19: 1369}
# 에레디비시 18팀: 기존 선수 자료의 순위값(2012-13 전 순위가 있고 다른 시즌도 같은 값)
NL18 = {1: 1837, 2: 1735, 3: 1677, 4: 1642, 5: 1624, 6: 1608, 7: 1587, 8: 1563, 9: 1542, 10: 1528,
        11: 1516, 12: 1504, 13: 1499, 14: 1482, 15: 1459, 16: 1441, 17: 1430, 18: 1406}
# 세르비아 수페르리가 2011-12(16팀) — 모형·순위값 없음, 기존 선수 자료의 세르비아 값에 맞춘 직접 추정(근거 약함):
#   1위 1520(파르티잔 2010-11·2011-12), 2위 1500(츠르베나 즈베즈다 2007-08 2위), 4위 1450(파르티잔 2022-23 4위),
#   7위 1400(OFK 베오그라드 2010-11 7위/16팀) → 3위는 2·4위의 중간, 5·6위는 4·7위 사이 직선(보이보디나 2024-25 5위 1433 선례),
#   8위 이하는 4→7위 기울기(순위당 50/3)를 그대로 이어 16위 1250까지(기존 '세르비아 중위권 1300'은 13위 수준).
SRB1_ANCHOR = {1: 1520, 2: 1500, 4: 1450, 7: 1400}
def srb1(r):
    if r in SRB1_ANCHOR: return SRB1_ANCHOR[r], "same"
    if r == 3: return 1475, "mid"
    return int(1450 - (r - 4) * 50 / 3 + 0.5), "line"
SRB1_MEAN = sum(srb1(r)[0] for r in range(1, 17)) / 16
# 세르비아 2부(프르바 리가) 2010-11(18팀): 1부 위 추정 평균에서 (독일 1·2부 평균 차 약 162)를 뺀 평평한 추정(튀르키예 2부 선례, 근거 약함)
SRB2 = int(SRB1_MEAN - 162 + 0.5)
# 쉬페르리그 2021-22(20팀): 외질·제르비뉴 자료와 같은 회귀(계수 2020 3.1·2021 6.7·2022 11.8), 흩어짐 119, 21칸 순위 곡선
_SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
_CV = [(v - 1739) / 91.3 for v in _SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return _CV[i] + (_CV[i + 1] - _CV[i]) * t
TR_COEF = {2020: 3.1, 2021: 6.7, 2022: 11.8}
def tr_mean(start):
    c = sum(TR_COEF[y] for y in (start - 1, start, start + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)

def model(lg, season, r, n):
    if lg == "L2":
        v, how = mid(L2_KNOWN, r)
        return v, f"2. 분데스리가 {season} {r}위" + (f" (추정, 다른 선수 자료 2부 {how[0]}위 {L2_KNOWN[how[0]]}·{how[1]}위 {L2_KNOWN[how[1]]}의 중간)" if how else "")
    if lg == "L3":
        v, how = mid(L3_KNOWN, r)
        return v, f"3. 리가 {season} {r}위" + (f" (추정, 다른 선수 자료 3. 리가 {how[0]}위 {L3_KNOWN[how[0]]}·{how[1]}위 {L3_KNOWN[how[1]]}의 중간)" if how else "")
    if lg == "NL1":
        return NL18[r], f"에레디비시 {season} {r}위"
    if lg == "SER1":
        v, how = srb1(r)
        return v, f"세르비아 {season} {r}위/{n}팀 (추정, 다른 선수 자료 세르비아 1위 1520·2위 1500·4위 1450·7위 1400에 맞춘 순위값)"
    if lg == "SER2":
        return SRB2, f"세르비아 2부(프르바 리가) {season} {r}위/{n}팀 (추정, 세르비아 1부 추정 평균 {SRB1_MEAN:.0f}에서 1·2부 차 162를 뺀 값)"
    if lg == "TR1" and season == "2021-22":
        return round(tr_mean(2021) + 119 * curve(r, n)), f"쉬페르리그 {season} {r}위"
    if lg in ("510", "511"):   # 네덜란드 톱클라서(3부 아마추어)
        return 1150, f"네덜란드 3부(톱클라서) {season} {r}위 (추정, 다른 선수 자료 네덜란드 3부 이하 아마추어 1150과 같음)"
    if lg == "C2":
        return 1250, f"스위스 2부(챌린지 리그) {season} {r}위 (추정, 다른 선수 자료 스위스 2부 1250과 같음)"
    return None
RANK_LG = ["SER1", "SER2", "NL1", "L2", "L3", "TR1", "510", "511", "C2"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정') — judgments.md 7절
MAN = {
    (key("Royal Antwerp FC"), "2021-22"): (1579, "벨기에 1부 2021-22 4위 (추정, 다른 선수 자료 벨기에 1부 2024-25 4위 1579와 같음)"),
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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]",
                        sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL", "CLQ", "ELQ") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    for s in [eu, str(int(eu[:4]))]:
        for lg in RANK_LG:
            t = RANKS.get((lg, s))
            if t and k in t:
                r, n = t[k]
                res = model(lg, eu, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                    return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_computed"]   # Transfermarkt 리포트 날짜(독일·이탈리아 시간)와 모두 같음

M = []
for g in GAMES:
    mins = MIN_FIX[g["gameId"]][0] if g["gameId"] in MIN_FIX else int(g["playedMinutes"])
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), mins])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["kostic_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
PRE_GAP_TM_ONLY = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et=0):
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
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["kostic_scorer"] == "1", e["kostic_assist_other"] == "1"
    if e["kostic_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag, ldate(g))); EXCL_CNT["본인 도움"] += 1
        EXCL_LIST["본인 도움"].append((ldate(g), g["opponent"], e["minute"], e["scorer"], e["assist_type"]))
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = int(ko == 1 and tie is None and int(e["minute"].split("+")[0]) > 90)   # 연장 골(120+2 포함), 90+x는 정규시간
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            k = why if tag not in EXCL_A else "개별 판정"
            EXCL_CNT[k] += 1; EXCL_LIST[k].append((d, opp, e["minute"], e["scorer"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
        if d >= GAP and tag not in ADD_CONFIRMED:
            if not hit:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
            used_fm[gid] += 1
        elif d < GAP and not hit:
            PRE_GAP_TM_ONLY.append((d, opp, e["minute"], e["scorer"], e["assist_type"]))
        elif d < GAP:
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local_computed"] >= GAP and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")):
        FM_ONLY.append((gid, G[gid]["date_local_computed"], ts))

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u)
for f in FM_ONLY:
    if f[0] not in FM_ONLY_DECIDED: print("판정 필요(FotMob 단독 도움):", f)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
if UNDECIDED or missing_elo or any(f[0] not in FM_ONLY_DECIDED for f in FM_ONLY):
    if "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY, EXCL_CNT)
    for k, v in EXCL_LIST.items(): print(k, v)
    print("2014.8 전 Transfermarkt 단독 도움", len(PRE_GAP_TM_ONLY))
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["kostic_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local_computed"])); continue
    fg = [r for r in FM_EV[gid] if r["kostic_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Timo Werner": ("wer.js", "WER", "2014-08-09", "2016-07-25"),
         "Mario Götze": ("got.js", "GOT", "2022-07-01", "2022-08-12"),
         "Ángel Di María": ("dim.js", "DIM", "2022-08-12", "2023-07-01"),
         "Juan Cuadrado": ("cua.js", "CUA", "2022-08-12", "2023-07-01"),
         "Federico Chiesa": ("chi.js", "CHI", "2022-08-12", "2024-09-09"),
         "Edin Dzeko": ("dze.js", "DZE", "2024-09-09", "2025-06-10"),
         "Jonathan David": ("jdv.js", "JDV", "2025-07-01", "2026-08-06"),
         "Ivan Perišić": ("per.js", "PER", "2026-08-06", "2026-12-31")}
def same_name(a, b):
    """동료 이름 대조: 이름 토큰이 모두 들어 있거나, 성이 같고 이름 첫 글자가 같음(Dzeko/Džeko, Juan Guillermo Cuadrado 등)"""
    A, B = norm(a).split(), norm(b).split()
    return set(A) <= set(B) or (A[-1] == B[-1] and A[0][0] == B[0][0])
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items()}
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb:
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
FK = lambda s: "kostic" in norm(s or "")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and same_name(nm, r[13]):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("코스티치 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and FK(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→코스티치 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:   # Transfermarkt 코스티치 도움을 이 계산기에서 뺀 동료 골(참고)
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["kostic_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 코스티치 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # TM 동료 도움 → 코스티치 골인데 동료 파일에 없음(참고)
        if e["kostic_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and same_name(nm, e["assist_player"]):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 코스티치 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
# 같은 날·같은 상대 다른 선수 기록(모든 선수)과 대회·Elo·lv·합산 대조
SAME_GAME = []
for r in E:
    for x in ENTS:
        if x["date"] == r[9] and (key(x["opp"]) == key(r[1]) or _sub(key(x["opp"]), key(r[1]))):
            if x.get("comp") and x["comp"] != r[3]: SAME_GAME.append(("대회 다름", r[9], r[1], x["p"], x["comp"], r[3]))
            if x["elo"] != r[2] or x["lv"] != r[12]: SAME_GAME.append(("Elo/lv 다름", r[9], r[1], x["p"], x["elo"], x["lv"], r[2], r[12]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
    for s in sorted(set(SAME_GAME)): print(s)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("radfk", "2012-07-01", "라드니치키 크라구예바츠", "2010~2012"), ("grofk", "2014-08-09", "FC 흐로닝언", "2012~2014"),
         ("vfbfk", "2016-07-25", "VfB 슈투트가르트", "2014~2016"), ("hsvfk", "2018-08-20", "함부르크 SV", "2016~2018"),
         ("sgefk", "2022-08-12", "아인트라흐트 프랑크푸르트", "2018~2022"), ("juvfk", "2024-09-09", "유벤투스", "2022~2024, 2025~2026"),
         ("fenfk", "2025-06-10", "페네르바흐체", "2024~2025"), ("juvfk", "2026-08-06", "유벤투스", "2022~2024, 2025~2026"),
         ("psvfk", None, "PSV 에인트호번", "2026~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)   # 유벤투스는 키 하나(두 번째 항목은 같은 키)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"4645": "radfk", "202": "grofk", "79": "vfbfk", "41": "hsvfk", "24": "sgefk", "506": "juvfk", "36": "fenfk", "383": "psvfk"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_kostic import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["kostic_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC, PRE=PRE_GAP_TM_ONLY))
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
mmin = {m[0]: m[3] for m in M}
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const KOS_E={J(E)};\nconst KOS_M={J(M)};\nconst KOS_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game_diffs": sorted(set(SAME_GAME)), "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY,
               "pre_2014_tm_only_assists": PRE_GAP_TM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
