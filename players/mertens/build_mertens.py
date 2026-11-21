#!/usr/bin/env python3
"""Dries Mertens: raw/ -> mertens.json + src/data/mer.js (판정 근거는 judgments.md)

  python3 players/mertens/build_mertens.py

입력: raw/tm_games.csv(출전), raw/mertens_goal_assist_events.csv(골·도움, TM 리포트 + FotMob 이벤트),
      raw/fotmob_playerMatches.csv(FotMob 선수 경기 목록), raw/tm_two_leg_ties.csv(두 경기 합산),
      raw/ranks_opponent_map.csv(상대 순위), /home/user/soc/elo/opponent_elo_by_team_season.csv + aliases.csv,
      src/data/{ins,hig}.js(같은 경기 동료 자료).
"""
import csv, json, os, re, sys, unicodedata, collections

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "mer.js")
OUT_JSON = os.path.join(HERE, "mertens.json")

GAP = "2014-08-01"   # 이 날짜 전 도움은 Transfermarkt 단일 출처(FotMob 이벤트에 도움 이름이 거의 없음)

# 날짜 고침: TM은 원래 일정(2010.12.19)으로 적었으나 경기는 2011.1.19에 열림(FotMob·fcupdate.nl)
DATE_FIX = {"1039256": "2011-01-19"}

# ---------------------------------------------------------------- 판정 표
# Transfermarkt 도움 중 넣지 않는 것(유형 규칙 밖): gameId|분 -> 이유
EXCL_A = {
    "4129455|7": "2014.8 이후 Transfermarkt 단일 출처 - FotMob 이벤트·선수 경기 목록 모두 이 골 도움 없음, Sporting Life(Opta) 도움 없음",
    "4513788|51": "2014.8 이후 Transfermarkt 단일 출처 - FotMob 선수 경기 목록 도움 0, 기사는 프리킥이 머리에 맞고 굴절돼 들어갔다고 서술",
}
# 2014.8 이후 Transfermarkt 도움인데 FotMob 이벤트에 도움 이름이 없고, FotMob 선수 경기 목록 도움 수가 Transfermarkt와 같아 넣은 것
PM_CONFIRMED = {"3229315|69", "3433500|12", "4445386|43", "4573310|26", "4573310|55", "4573310|90+1"}
# 2014.8 이후 Transfermarkt 단일 출처지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2492491|16": "Sports Mole 경기 기사(메르턴스 프리킥을 함식이 방향만 바꿈)·ESPN 경기 기사(메르턴스 크로스) - FotMob·football-italia는 굴람 도움",
}
# FotMob에만 있는 도움 중 다른 출처로 확인해 넣은 것: gameId -> (분, 득점자, 골 직전 스코어 우리-상대, 근거)
FM_ADD = {
    "3081218": ("15", "Arkadiusz Milik", (0, 0), "FotMob 경기 이벤트·선수 경기 목록 + Transfermarkt 공식 도움 기록(assistsOfficial 1) + 경기 기록 사이트(sporteden·ANWP)"),
}
FM_ONLY_NOT = [
    "2017.5.14 토리노전 76분 카예혼 골(FotMob만 메르턴스 도움, Transfermarkt는 굴람 크로스)",
    "2022.1.13 코파 이탈리아 피오렌티나전(FotMob 선수 경기 목록·Transfermarkt 공식 도움 기록에 1개, 경기 이벤트에는 메르턴스 도움 골 없음)",
    "2011.9.18 아약스전 2분 마타우시 골(FotMob만 메르턴스 도움, Transfermarkt는 피터르스 - 2014.8 이전이라 Transfermarkt 기준)",
]

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"NL1", "NL2", "IT1", "TR1", "PONL"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("NLP", "CIT", "TRP"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("NLSC", "SCI", "TRS"): return "df"
    if cid == "CLQ": return "clq"
    if cid == "ELQ": return "elq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        sys.exit("CL 라운드 " + rnd)
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        return "elk"     # Second Round(32강)·intermediate stage·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0     # 챔스·유로파 조별, 튀르키예컵 2024-25 조별(리그식)
    return 1

# ---------------------------------------------------------------- 두 경기 합산
TIES = {}
for t in csv.DictReader(open(os.path.join(RAW, "tm_two_leg_ties.csv"), encoding="utf-8")):
    for leg in (1, 2):
        gid = t[f"leg{leg}_gameId"]
        home = 1 if t[f"leg{leg}_venue"] == "H" else 0
        f1, f2 = map(int, t["leg1_score_club_opp"].split("-"))
        d = "20" + t[f"leg{leg}_date"].split("/")[2][-2:] + "-" + t[f"leg{leg}_date"].split("/")[1] + "-" + t[f"leg{leg}_date"].split("/")[0][-2:]
        cid = t["comp"]
        if cid in ("EL", "ELQ", "CL", "CLQ"):
            ag, et = int(d < "2021-07-01"), 1
        elif cid == "CIT":
            ag, et = int(d < "2022-07-01"), 1
            if d.startswith("2020-06"): et = 0          # 2019-20 준결승 2차전(재개 후)은 연장 없이 승부차기
        elif cid == "PONL":
            ag, et = 1, 1
        else:
            sys.exit("합산 규칙 없음 " + cid)
        TIES[gid] = [leg, home, f1 if leg == 2 else 0, f2 if leg == 2 else 0, ag, et]
OTHER_LEG_USED = []
for t in csv.DictReader(open(os.path.join(RAW, "tm_two_leg_ties.csv"), encoding="utf-8")):
    if t["mertens_played"] == "2nd only":
        OTHER_LEG_USED.append((t["leg2_date"], t["opponent"], t["leg1_score_club_opp"]))

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
MANUAL_ALIAS = {"dinamo moscow": "dynamo moscow", "zalgiris vilnius": "fk zalgiris vilnius"}

def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        TABLE[(key(r["팀"]), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

# 순위(조사 에이전트가 경기별로 붙인 표): (gameId) -> (표, 순위, 팀 수)
RANKMAP = {}
for r in csv.DictReader(open(os.path.join(RAW, "ranks_opponent_map.csv"), encoding="utf-8")):
    RANKMAP.setdefault(r["tmGameId"], []).append((r["table"], int(r["rank"]), int(r["teams"])))

# 순위표 전체(경기별 표에 없는 컵 대회 상대용): (표 이름, 시즌) -> {key: (순위, 팀 수)}
RANKS = collections.defaultdict(dict)
for line in open(os.path.join(RAW, "ranks.txt"), encoding="utf-8"):
    p = line.rstrip("\n").split("|")
    if len(p) < 5 or p[0] == "league": continue
    RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))

# 세리에A 고정 순위값을 표준화한 곡선(인시녜·팔카오 자료와 같음)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
# 에레디비시 18팀 순위값(기존 선수 자료, 빠진 순위 없음)
NL1 = [1837, 1735, 1677, 1642, 1624, 1608, 1587, 1563, 1542, 1528, 1516, 1504, 1499, 1482, 1459, 1441, 1430, 1406]
# 튀르키예 1부 평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 계수 평균 − 7.333), 흩어짐 119 (팔카오·임모빌레 자료 계수)
TR_COEF = {2021: 6.7, 2022: 11.8, 2023: 12.0, 2024: 10.3, 2025: 11.075}
def tr_mean(start):
    c = sum(TR_COEF[y] for y in (start - 1, start, start + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)

def rank_model(table, r, n):
    m = re.match(r"(.*) \[TM (\w+)\] (\S+)$", table)
    code, s = m.group(2), m.group(3)
    if code == "NL1":
        return NL1[r - 1], f"에레디비시 {s} {r}위"
    if code == "NL2":
        return round(1331 + SD2 * curve(r, n)), f"에이르스터 디비시 {s} {r}위"
    if code == "TR1":
        return round(tr_mean(int(s[:4])) + 119 * curve(r, n)), f"쉬페르리그 {s} {r}위"
    return None

# 순위표·기존 자료에 없는 상대(모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {
    ("HHC Hardenberg", "2007-08"): (1150, "네덜란드 아마추어 3부 (추정, 판페르시 자료의 네덜란드 3부 이하 아마추어 1150과 같음)"),
    ("FC Lisse", "2011-12"): (1150, "네덜란드 아마추어 4부 (추정, 판페르시 자료의 네덜란드 3부 이하 아마추어 1150과 같음)"),
    ("KF Tirana", "2009-10"): (1300, "알바니아 2009-10 3위 (추정)"),
    ("FC Luzern", "2010-11"): (1399, "스위스 슈퍼리그 2010-11 6위 (추정, 같은 시즌 바젤 1위 1738과 같은 리그 수준·흩어짐 119)"),
    ("Celtic FC", "2010-11"): (1620, "스코틀랜드 2010-11 2위 (추정, 다른 선수 자료의 셀틱 2009-10·2011-12 값과 같음)"),
    ("SV Ried", "2011-12"): (1370, "오스트리아 분데스리가 2011-12 6위 (추정, 국가 계수 회귀 평균 약 1409)"),
    ("Legia Warszawa", "2011-12"): (1480, "폴란드 2011-12 3위 (추정)"),
    ("Rapid Bucharest", "2011-12"): (1480, "루마니아 2011-12 4위 (추정)"),
    ("Hapoel Tel Aviv", "2011-12"): (1500, "이스라엘 2011-12 2위 (추정, 다른 선수 자료의 2010-11 2위 1500과 같음)"),
    ("FK Zeta Golubovci", "2012-13"): (1250, "몬테네그로 1부 (추정)"),
    ("Dynamo Kyiv", "2016-17"): (1620, "우크라이나 2016-17 2위 (추정, 다른 선수 자료의 디나모 키이우 2위권 1620과 같음)"),
    ("Dynamo Kyiv", "2024-25"): (1560, "우크라이나 2024-25 1위 (추정)"),
    ("Red Bull Salzburg", "2018-19"): (1771, "오스트리아 분데스리가 2018-19 1위 (추정, 국가 계수 회귀 평균 1471·흩어짐 119)"),
    ("FK Zalgiris Vilnius", "2023-24"): (1300, "리투아니아 2023 2위 (추정, 다른 선수 자료의 잘기리스 2013-14 1300과 같음)"),
    ("NK Olimpija Ljubljana", "2023-24"): (1360, "슬로베니아 2023-24 3위 (추정, 다른 선수 자료의 무라 2021 1위 1360과 같은 수준)"),
    ("FC RFS", "2024-25"): (1350, "라트비아 2024 1위 (추정)"),
    ("IF Elfsborg", "2024-25"): (1450, "스웨덴 알스벤스칸 2024 7위 (추정)"),
    ("Malmö FF", "2024-25"): (1555, "스웨덴 알스벤스칸 2024 1위 (추정, 다른 선수 자료의 말뫼 1위 1555와 같음)"),
}
MAN = {(key(k), s): v for (k, s), v in MAN.items()}

def season_eu(d, club=None):
    y, m = int(d[:4]), int(d[5:7])
    if d.startswith("2020-08"): return "2019-20"
    s = y if (m >= 8 or (m == 7 and club in ("utrme", "galme") and int(d[8:10]) >= 10)) else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 경기별로 상대 시즌 표 고르기(7월 예선: 위트레흐트 2010.7 티라나는 직전 시즌 순위, 루체른은 두 경기 모두 2010-11)
ELO_SEASON = {"1032251": "2009-10", "1035840": "2009-10", "1041193": "2010-11", "1041557": "2010-11"}

def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Lorenzo Insigne": load_js("ins.js", "INS"), "Gonzalo Higuaín": load_js("hig.js", "HIG")}
SAME_MATCH = {}
for nm, ent in MATES.items():
    for x in ent:
        SAME_MATCH.setdefault((x[9], key(x[1])), (x[2], x[12], nm))

ELO_SRC = collections.Counter()
def opp_elo(gid, opp, date, club):
    k = key(opp)
    if (date, k) in SAME_MATCH:
        e, lv, nm = SAME_MATCH[(date, k)]
        ELO_SRC["같은 경기 동료 자료"] += 1
        return e, lv
    s = ELO_SEASON.get(gid, season_eu(date, club))
    cands = [s, str(int(s[:4])), str(int(s[:4]) + 1)]
    for ss in cands:     # 달력 연도 리그(스웨덴 AIK 2012 등)는 연도 키
        if (k, ss) in TABLE:
            e, lv = collections.Counter(TABLE[(k, ss)]).most_common(1)[0][0]
            ELO_SRC["기존 팀×시즌 값"] += 1
            return e, lv
    if (k, s) in MAN:
        ELO_SRC["직접 추정"] += 1
        return MAN[(k, s)]
    for table, r, n in RANKMAP.get(gid, []):
        if table.endswith(s):
            res = rank_model(table, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1
                return res
    for (lg, ss), tab in RANKS.items():
        if ss == s and k in tab and ("[TM NL" in lg or "[TM TR1]" in lg):
            res = rank_model(f"{lg} {ss}", *tab[k])
            if res:
                ELO_SRC["순위표+리그 모형"] += 1
                return res
    sys.exit(f"상대 Elo 없음: {gid} {opp} {s} {RANKMAP.get(gid)}")

# ---------------------------------------------------------------- 클럽
CLUBS = [("2009-07-01", "agome", "AGOVV"), ("2011-07-01", "utrme", "위트레흐트"), ("2013-07-01", "psvme", "PSV"),
         ("2022-07-01", "napme", "나폴리"), ("9999-12-31", "galme", "갈라타사라이")]
def club_of(d):
    for u, k, n in CLUBS:
        if d < u: return k

# ---------------------------------------------------------------- 출전
games = list(csv.DictReader(open(os.path.join(RAW, "tm_games.csv"), encoding="utf-8")))
G = {g["gameId"]: g for g in games}
def gdate(g): return DATE_FIX.get(g["gameId"], g["date"])
M = []
for g in sorted(games, key=lambda g: (gdate(g), g["gameId"])):
    M.append([gdate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
ev = list(csv.DictReader(open(os.path.join(RAW, "mertens_goal_assist_events.csv"), encoding="utf-8")))
PM = {}
for r in csv.DictReader(open(os.path.join(RAW, "fotmob_playerMatches.csv"), encoding="utf-8")):
    PM[r["utc"][:10]] = r

def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], collections.defaultdict(list)
def add_row(role, gid, mstr, before_hw, side, pk, scorer):
    g = G[gid]; d = gdate(g)
    mi, dm = minute(mstr)
    bh, ba = before_hw
    gf, ga = (bh, ba) if side == "home" else (ba, bh)
    cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    club = club_of(d)
    elo, lv = opp_elo(gid, g["opponent"].strip(), d, club)
    et = 1 if mi > 95 and ko == 1 else 0
    row = [role, g["opponent"].strip(), elo, comp, mi, gf, ga, ko, pk, d, et, dm if not et else 0, lv, 0 if role == "g" else scorer]
    tie = TIES.get(gid)
    if ("leg" in rnd.lower()) != bool(tie): sys.exit("합산 표 누락: " + gid + " " + rnd)
    if tie: row.append(list(tie))
    rows.append(row)

for e in ev:
    gid, mstr = e["tmGameId"], e["minute_tm"]
    tag = f"{gid}|{mstr}"
    d = gdate(G[gid])
    bh, ba = map(int, e["score_before_home_away"].split("-"))
    if e["role"] == "scorer":
        if e["own_goal"] == "1":
            judg["자책골 제외"].append((d, e["opponent"], mstr)); continue
        pk = 1 if e["penalty"] == "1" else 0
        if e["penaltyRebound"] == "1": pk = 0
        add_row("g", gid, mstr, (bh, ba), e["scoring_side"], pk, None)
        continue
    # 도움
    t = e["assist_type_tm"]
    if e["own_goal"] == "1":
        judg["상대 자책골 유도"].append((d, e["opponent"], mstr, e["scorer"])); continue
    if t == "Penalty: Fouled player":
        judg["PK 유도"].append((d, e["opponent"], mstr, e["scorer"])); continue
    if t == "Shot on goal":
        judg["Shot on goal"].append((d, e["opponent"], mstr, e["scorer"], "FotMob 도움" if "Mertens" in e["fm_assist"] else "")); continue
    if tag in EXCL_A:
        judg["단일 출처 미확인"].append((d, e["opponent"], mstr, e["scorer"], EXCL_A[tag])); continue
    if d >= GAP:
        if "Dries Mertens" in e["fm_assist"]:
            judg["TM+FotMob 이벤트"].append(tag)
        elif tag in PM_CONFIRMED:
            judg["TM+FotMob 선수 경기 목록"].append((d, e["opponent"], mstr, e["scorer"]))
        elif tag in ADD_CONFIRMED:
            judg["TM+기사 2곳"].append((d, e["opponent"], mstr, e["scorer"], ADD_CONFIRMED[tag]))
        else:
            sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락: " + tag + " " + e["scorer"])
    else:
        judg["2014.8 이전 Transfermarkt"].append(tag)
        if t == "": judg["2014.8 이전 유형 빈칸"].append((d, e["opponent"], mstr, e["scorer"]))
    add_row("a", gid, mstr, (bh, ba), e["scoring_side"], 0, e["scorer"])

for gid, (mstr, scorer, (gf, ga), why) in FM_ADD.items():
    g = G[gid]
    side = "home" if g["venue"] == "H" else "away"
    hw = (gf, ga) if side == "home" else (ga, gf)
    add_row("a", gid, mstr, hw, side, 0, scorer)
    judg["FotMob+다른 출처"].append((gdate(g), g["opponent"], mstr, scorer, why))

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))
E = rows

# FotMob 선수 경기 목록과 도움 수 대조(2017.2 이후)
pm_diff = []
for d, r in PM.items():
    if r["league"] in ("Club Friendlies", "Audi Cup"): continue
    n = sum(1 for x in E if x[9] == d and x[0] == "a")
    if int(r["assists"]) != n: pm_diff.append((d, r["opponent"], "FotMob", r["assists"], "여기", n))

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조
cross = []
for r in E:
    if r[0] == "a" and r[13] in MATES:
        hit = [x for x in MATES[r[13]] if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
        cross.append(("메르턴스 도움→동료 골", r[9], r[13], r[4], "있음" if hit else "없음",
                      [hit[0][2], hit[0][12], hit[0][5], hit[0][6], hit[0][3]] if hit else None, [r[2], r[12], r[5], r[6], r[3]]))
for nm, ent in MATES.items():
    for x in ent:
        if x[0] == "a" and x[13] == "Dries Mertens":
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            cross.append(("동료 도움→메르턴스 골", x[9], nm, x[4], "있음" if hit else "없음",
                          [x[2], x[12], x[5], x[6], x[3]], [hit[0][2], hit[0][12], hit[0][5], hit[0][6], hit[0][3]] if hit else None))
        for r in E:
            if r[9] == x[9] and key(x[1]) == key(r[1]) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3]):
                cross.append(("Elo/lv/대회 다름", r[9], nm, r[1], (x[2], x[12], x[3]), (r[2], r[12], r[3])))

# ---------------------------------------------------------------- 합계
ST = collections.OrderedDict((k, [0, 0, 0]) for _, k, _ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
MIN_TOT = sum(m[3] for m in M)
PRE = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v))
NJ = {k: len(v) for k, v in judg.items()}
TM_A = 225

NOTE_LINES = [
    f"드리스 메르턴스(AGOVV 아펠도른·위트레흐트·PSV·나폴리·갈라타사라이)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 캄뷔르전 ~ {d_(M[-1][0])} 바샥셰히르전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    f"클럽별 경기·골·도움: AGOVV 아펠도른 {c3(ST['agome'])}, 위트레흐트 {c3(ST['utrme'])}, PSV {c3(ST['psvme'])}, 나폴리 {c3(ST['napme'])}, 갈라타사라이 {c3(ST['galme'])}",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(API, 출전 {NG}경기·{MIN_TOT}분)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음",
    "클럽별 경기·골은 영어 위키백과와 같음(위키백과는 위트레흐트 2009-10 에레디비시 유럽 대항전 플레이오프 4경기를 리그에 넣고, AGOVV 2006-07·2007-08 KNVB컵 3경기 1골이 빠져 있음). FotMob 경력 합계는 나폴리 397경기 148골·갈라타사라이 136경기 25골로 같음",
    "2005-06 에인드라흐트 알스트 임대(벨기에 3부, 위키백과 14경기 4골)는 Transfermarkt·FotMob에 경기 기록이 없어 넣지 않음. 벨기에 대표팀 경기와 친선경기는 뺌",
    "2010-11 에레디비시 VVV-펜로 원정(2-1 승)은 Transfermarkt가 원래 일정인 2010.12.19로 적었으나 실제 경기일 2011.1.19(FotMob·fcupdate.nl)로 씀",
    "2024.4.7 튀르키예 슈퍼컵 결승 페네르바체전(페네르바체가 2분 만에 경기를 포기해 3-0 몰수)과 2025.2.9 아다나 데미르스포르전(30분경 상대가 경기를 포기, 법원 판정 3-0)은 Transfermarkt대로 출전(2분·30분)으로 넣음. 아다나전 모라타 PK 골의 메르턴스 도움은 PK 유도라 세지 않음",
    f"PK 골 {NPK}개는 Transfermarkt 골 유형 기준(FotMob과 같음). 2017.3.7 챔스 16강 2차전 레알 마드리드전 57분 자책골은 메르턴스 골이 아니라 뺌",
    "PK 골 3개(2012.2.12 더 흐라프스합전·2012.2.23 유로파 트라브존스포르전·2016.12.18 토리노전)는 Transfermarkt 리포트에 본인 도움으로도 적혀 있으나 도움으로 세지 않음",
    "2007.12.14 MVV전 90분 결승 골은 Transfermarkt 리포트가 상대 티바우트 PK 골(90분) 다음에 적어 골 직전 스코어를 2-2로 봄(두 골 순서를 확인한 다른 출처는 못 찾음)",
    "도움은 2014.8.1 이전은 Transfermarkt 도움을 쓰고(다른 출처와 대조 못 함), 그 뒤는 FotMob 경기 이벤트 또는 FotMob 선수 경기 목록과 Transfermarkt가 같이 적은 도움을 기준으로 함",
    f"도움 {NA}개 = Transfermarkt 도움 {TM_A}개 − PK 유도 {NJ.get('PK 유도', 0)}개 − 'Shot on goal' 리바운드 {NJ.get('Shot on goal', 0)}개(그중 2012.8.18 로다·2016.9.13 디나모 키이우·2024.10.23 엘프스보리전 3개는 FotMob이 도움으로 셈) − 상대 자책골 유도 {NJ.get('상대 자책골 유도', 0)}개 − 2014.8 이후 다른 출처로 확인 못 한 단일 출처 {NJ.get('단일 출처 미확인', 0)}개 + FotMob 도움을 다른 출처로 확인해 더한 1개",
    "상대 자책골 유도로 뺀 도움: 2010.5.6 흐로닝언전 90분 그란크비스트, 2010.10.24 비테서전 3분 라이코비치, 2015.2.8 우디네세전 59분 테로, 2024.8.31 아다나 데미르스포르전 18분 세미흐 귈레르",
    "2014.8 이후 Transfermarkt에만 있어 뺀 도움: 2023.9.16 삼순스포르전 7분 아크튀르크올루 골(FotMob·Sporting Life 도움 없음, 터키 기사는 메르턴스가 공을 박스로 보냈다고만 서술), 2025.1.8 튀르키예컵 바샥셰히르전 51분 다빈손 산체스 골(FotMob 도움 없음, 기사는 프리킥이 다른 선수 머리에 맞고 들어갔다고 서술)",
    "2014.12.11 유로파 슬로반 브라티슬라바전 16분 함식 골 도움은 FotMob·football-italia가 굴람으로 적었으나 Transfermarkt·Sports Mole·ESPN 경기 기사가 메르턴스로 적어 넣음",
    "2018.12.29 볼로냐전 15분 밀리크 골 도움은 Transfermarkt 리포트에 없지만 FotMob(경기 이벤트·선수 경기 목록)·Transfermarkt 공식 도움 기록·경기 기록 사이트가 메르턴스로 적어 넣음",
    "FotMob 경기 이벤트에 도움 이름이 없지만 FotMob 선수 경기 목록 도움 수가 Transfermarkt와 같아 넣은 도움 6개: 2019.12.7 우디네세전 69분, 2021.4.22 라치오전 12분, 2024.11.28 유로파 AZ전 43분, 2025.4.22 튀르키예컵 준결승 코니아스포르전 26·55·90+1분",
    "넣지 않은 FotMob 단독 도움: " + "; ".join(FM_ONLY_NOT),
    f"2014.8.1 이전 도움 {PRE}개는 Transfermarkt 단일 출처이고, 유형 칸이 빈 {NJ.get('2014.8 이전 유형 빈칸', 0)}개도 도움으로 셈",
    "날짜는 경기 현지 날짜(모든 경기가 유럽 경기라 Transfermarkt 날짜와 같음)",
    "상대 Elo는 같은 경기 동료 자료(인시녜·이과인) 값 → 기존 선수 자료의 같은 팀·같은 시즌 값 → 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 모형에 넣은 값 순으로 씀",
    "에이르스터 디비시(네덜란드 2부)는 수아레스 자료의 평균 1331에 2부 흩어짐 곡선(2006-07 17위 1281·2009-10 5위 1364와 같은 방식), 에레디비시는 기존 순위값(1위 1837 … 18위 1406)",
    "쉬페르리그 2022-23~2024-25는 기존 튀르키예 회귀식(앞뒤 3시즌 UEFA 국가 계수 평균, 계수 6.7·11.8·12.0·10.3·11.075)으로 평균 약 1539·1567·1562, 흩어짐 119. 2024-25는 임모빌레 자료에 같은 순위 값이 있으면 그 값(갈라타사라이 1위 1859 등). 2022-23·2024-25는 19팀, 2023-24는 20팀 순위표",
    "리그 표가 없는 상대는 당시 수준을 추정함(모두 '추정'): HHC 하르덴베르흐 2007-08·FC 리서 2011-12 1150(네덜란드 아마추어), 티라나 2009-10 1300, 루체른 2010-11 1399, 셀틱 2010-11 1620, 리트 2011-12 1370, 레기아 2011-12 1480, 라피드 부쿠레슈티 2011-12 1480, 하포엘 텔아비브 2011-12 1500, 제타 골루보브치 2012-13 1250, 디나모 키이우 2016-17 1620·2024-25 1560, 잘츠부르크 2018-19 1771, 잘기리스 2023 1300, 올림피야 류블랴나 2023-24 1360, RFS 2024 1350, 엘프스보리 2024 1450, 말뫼 2024 1555",
    "Transfermarkt 순위표 중 달력 연도 리그(리투아니아·라트비아·스웨덴)는 한 해 뒤 시즌 표였으므로 순위는 경기 해의 최종 순위(RSSSF·위키백과 기준: 잘기리스 2023 2위, RFS 2024 1위, 말뫼 2024 1위, 엘프스보리 2024 7위)를 씀",
    "7월 예선 상대: 티라나(2010.7)는 직전 시즌 순위, 루체른(2010.7.29·8.5)은 두 경기 모두 2010-11 순위로 계산함",
    "KNVB컵·코파 이탈리아·튀르키예컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중, 준결승·결승 가중), 요한 크라위프 실드·수페르코파 이탈리아나·튀르키예 슈퍼컵은 국내컵 결승으로 계산함. 2024-25 튀르키예컵 조별리그는 리그식(무승부 1점)",
    "에레디비시 유럽 대항전 플레이오프(2010.5, 흐로닝언·로다 JC 4경기)는 리그 비중으로, 원정 다득점·연장이 있는 두 경기 합산으로 계산함(수아레스 자료와 같음)",
    f"두 경기 합산(유로파·챔스 예선과 토너먼트, 코파 이탈리아 준결승, 에레디비시 플레이오프) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회 2020-21시즌까지·코파 이탈리아 2021-22시즌까지 적용. 2020.6.13 코파 이탈리아 준결승 2차전 인테르전은 연장 없이 승부차기 규정",
    "못 뛴 1차전 스코어는 Transfermarkt 일정으로 채움: 2019.2.21 유로파 32강 2차전 취리히전(1차전 3-1). 1차전만 뛴 2012-13 제타 골루보브치, 2차전만 뛴 2017-18 라이프치히·2020-21 그라나다는 골·도움이 없어 계산에 쓰이지 않음",
    "2011.12.22 KNVB컵 16강 트벤테전 101분 마타우시 골 도움은 연장 시간 기록으로 계산함. 연장·승부차기 경기의 출전 분은 Transfermarkt 값 그대로",
    "시즌은 나폴리·PSV·AGOVV 8월 1일 기준(2020년 7~8월 나폴리 경기는 2019-20), 위트레흐트와 갈라타사라이는 7월 10일 기준(2010.7 유로파 예선 = 2010-11, 2023.7.25 챔스 예선 잘기리스전 = 2023-24)",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 벨기에 대표팀 기록과 AGOVV 2009 '최우수 신인'은 표 항목이 없어 뺌. 네덜란드 슈퍼컵(Transfermarkt 표기 2013)은 2012.8.5 요한 크라위프 실드라 2012-13으로 적음",
    "2025.7.1 은퇴(Transfermarkt), 마지막 공식 경기 2025.5.30 바샥셰히르전",
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
mdates = {m[0] for m in M}
for d, rs in by.items():
    prev = None
    for r in rs:
        if prev and (r[5] < prev[0] or r[6] < prev[1]): problems.append(("스코어 역순", d, r[4]))
        prev = (r[5], r[6])
    if d not in mdates: problems.append(("출전 없음", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
for m in M:
    if m[3] < 1 or m[3] > 125: problems.append(("출전 분 범위", m))
for p in problems: print("점검:", p)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
open(OUT_JS, "w", encoding="utf-8").write(f"const MER_E={J(E)};\nconst MER_M={J(M)};\nconst MER_NOTE={J(NOTE)};\n")
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "cross_check": cross, "judgments": judg,
           "pm_diff": pm_diff, "elo_sources": ELO_SRC}, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}({NTIEG}경기) · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print({k: len(v) for k, v in judg.items()})
print("FotMob 선수 경기 목록 도움 차이", pm_diff)
for c in cross:
    if c[4] != "있음" or c[0].startswith("Elo") or (c[5] and c[6] and c[5] != c[6]): print("대조:", c)
print("동료 대조", len(cross), "점검 문제", len(problems))
