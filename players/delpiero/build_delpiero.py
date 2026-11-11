#!/usr/bin/env python3
"""Alessandro Del Piero: raw/ -> delpiero.json + src/data/del.js (판정 근거는 judgments.md)

  python3 players/delpiero/build_delpiero.py            # 파일 쓰기
  python3 players/delpiero/build_delpiero.py --debug    # Elo 출처 목록
  python3 players/delpiero/build_delpiero.py --fm       # FotMob 골 대조
  python3 players/delpiero/build_delpiero.py --cross    # 동료(이브라히모비치) 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/ibr.js.
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "del.js")
OUT_JSON = os.path.join(HERE, "delpiero.json")
ME = "알레산드로 델 피에로"
GAP = "2014-08-01"   # 도움 출처 기준일(이전 Transfermarkt, 이후 Transfermarkt∩FotMob 또는 다른 출처 2곳)

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
# 골 분 수정(Transfermarkt 리포트의 분이 틀리거나 순서가 꼬인 것): gameId|TM 분|골 뒤 스코어 -> (분, 표시 분)
GOAL_MIN_FIX = {
    # 2006.8.27 코파 이탈리아 3라운드 나폴리-유벤투스(3-3, 승부차기 8-7): TM은 연장 두 골을 모두 120분으로 적음.
    # ESPN 경기 기록: 델 피에로 78·115분, 파올로 칸나바로 116분 → 델 피에로 2-3 골은 115분(골 전 2-2)
    "2372462|120|2-3": (115, 0),
}
# 골 제외(Transfermarkt 리포트 골이지만 넣지 않음)
EXCL_G = {}

# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    "1019587|34": "슈팅 리바운드(Shot on goal, 몬테로)",
    "1022539|34": "슈팅 리바운드(Shot on goal, 트레제게)",
    "1022554|11": "슈팅 리바운드(Shot on goal, 트레제게)",
    "2427383|21": "슈팅 리바운드(Shot on goal, 무투)",
    "2816089|23": "슈팅 리바운드(Shot on goal, 비알리)",
    "985125|45": "슈팅 리바운드(Shot on goal, 트레제게)",
    "2215294|67": "PK 유도(라바넬리 PK)",
    "84283|15": "PK 유도(트레제게 PK)",
    "1133326|48": "상대 자책골(모로)",
    "1133553|78": "상대 자책골(차모)",
    "2214565|45+2": "상대 자책골(잉게손, 유형 Shot on goal)",
    "2214565|90": "상대 자책골(가르치아)",
    "2215375|63": "상대 자책골(부치)",
    "65611|22": "상대 자책골(콜롬보; 리포트 스코어 표기도 틀림)",
    # 2014.8.1 이후 TM 단독(FotMob 도움 없음), 다른 출처가 엇갈림 → 넣지 않음
    "2504590|74": "2014.8 이후 Transfermarkt 단독. PTI 기사는 '델 피에로 크로스 뒤 23야드 슛'이라 적었으나 Kridangan 기사는 쇼우비크 크로스가 걷어내진 뒤의 발리라 적어 확인 안 됨",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {}
# FotMob에만 있는 도움(넣지 않음)
FM_ONLY = ["2011.4.23 카타니아전 38분 델 피에로 골의 반대 방향이 아니라, 같은 경기 38분 골(델 피에로)에 FotMob이 크라시치 도움을 적은 것 — 델 피에로 자신의 도움이 아님"]

# 몰수 경기: 경기 중 스코어로 계산(드록바 2013.9.22 베식타시전 선례)
FORFEIT = {"1169715": "1994.9.13 UEFA컵 1라운드 1차전 CSKA 소피아-유벤투스: 경기장에서는 3-2 CSKA 승, 출전 자격 없는 선수(미흐타르스키) 출전으로 UEFA가 0-3 유벤투스 승으로 바꿈"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "AUS1", "IND1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "AUSF": return "mlp"     # A리그 파이널 시리즈(플레이오프) = MLS 플레이오프와 같은 코드(USL 플레이오프 선례)
    if cid == "CIT":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SCI", "USC"): return "df"
    if cid == "WEPO": return "cwc"
    if cid == "UI": return "elq"       # 인터토토컵 = 유로파 예선(램파드·비야 선례, 결승 포함)
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 1999-2003 2차 조별(Group 4 등)도 조별
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # UEFA컵 2·3라운드·16강·8강, 유로파 32강(Second Round)·16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

# 리포트 라운드 이름에 'leg'가 없지만 두 경기 합산인 경기: gameId -> 차전
LEG_FIX = {"2428398": 1, "2428399": 2}   # 1996-97 코파 이탈리아 16강 노체리나(0-0 원정, 2-1 홈; TM은 2차전을 'Replay'로 표기, 리포트에 1차전 링크)

def leg_of(g):
    if g["gameId"] in LEG_FIX: return LEG_FIX[g["gameId"]]
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def other_leg_id(gid):
    if gid == "2428399": return "2428398"
    return TIES_RAW[gid]["other_leg_id"]

# 몰수 경기의 다른 차전: 합산은 공식 결과(0-3)로 진출이 정해졌으므로 공식 결과를 씀
OTHER_LEG_SCORE = {"1169715": None}

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[other_leg_id(gid)]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    # 원정 다득점: UEFA 대회(2020-21까지)·코파 이탈리아(2021-22까지) 모두 해당 기간, 연장 있음
    return [leg, home, fu, ft, 1, 1]

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
    "inter milan": "inter", "ac parma": "parma calcio 1913", "parma ac": "parma calcio 1913",
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

# 순위표(Transfermarkt): (리그, 시즌) -> {key: (순위, 팀 수)}
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 세리에A 20팀 순위값(기존 자료) → 표준 곡선
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

# 세리에A 18팀(1988-89~2003-04): 기존 자료의 순위값(1997-98~2003-04 lv에서 모음, 시즌 간 같은 값) + 빈 순위는 곡선
SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 8: 1743, 10: 1713, 11: 1704, 13: 1690, 14: 1676, 15: 1657, 17: 1633, 18: 1614}
for _r in range(1, 19):
    SA18.setdefault(_r, int(round(1739 + 91.3 * curve(_r, 18))))
SB_MEAN, SB_SD = 1577.78, 51.24   # 세리에B(문서 4절, 기존 선수 값으로 검증된 평균·흩어짐)
C1_MEAN = 1417                    # 세리에C1(레가 프로 1부) 평균(인시녜 선례), 흩어짐은 세리에B와 같은 2부 곡선

def model(lg, season, r, n):
    """(Elo, lv) — 순위표 + 리그 모형"""
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        if n == 18: return SA18[r], f"세리에A {season} {r}위"
        assert n == 20, (season, n)
        return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "IT2":
        m = ents_map("세리에B", season)
        if r in m: return m[r], f"세리에B {season} {r}위"
        if n == 22:   # 기존 22팀 시즌(2011-12 등)의 순위값
            m = ents_map("세리에B", "2011-12")
            if r in m: return m[r], f"세리에B {season} {r}위"
        return int(round(SB_MEAN + SB_SD * curve(r, n))), f"세리에B {season} {r}위"
    if lg in ("IT3A", "IT3B"):
        grp = "A" if lg == "IT3A" else "B"
        return int(round(C1_MEAN + SB_SD * curve(r, n))), f"세리에C1 {grp}조 {season} {r}위/{n}팀 (추정)"
    if lg == "AUS1":
        # 비야 자료(호주 A리그 2014-15)와 같은 추정: 1위 1450 ~ 꼴찌 1350 직선
        return int(round(1450 - (r - 1) * 100 / (n - 1))), f"호주 A리그 {season} {r}위 (추정: 1위 1450~꼴찌 1350 직선)"
    if lg == "IND1":
        # 새 추정: 1위 1300 ~ 꼴찌 1200 직선(평균 1250 = 다른 선수 자료의 인도 팀 FC 고아 2025 값)
        return int(round(1300 - (r - 1) * 100 / (n - 1))), f"인도 슈퍼리그 {season} {r}위 (추정: 1위 1300~꼴찌 1200 직선)"
    if lg == "L1":   # 분데스리가: 기존 자료 2000-01~2006-07의 18팀 순위값(1996-97 11위 1713도 같음)
        return BL[r], f"분데스리가 {season} {r}위" + ("" if season >= "1996-97" else " (2000-01 순위값 사용)")
    if lg == "GB1":   # 프리미어리그 1996-97·1997-98: 같은 시즌 기존 순위값 + 리그 모형 흩어짐(98.3)으로 이웃 순위에서 옮김
        m = ents_map("프리미어리그", season)
        if r in m: return m[r], f"프리미어리그 {season} {r}위"
        b = min(m, key=lambda x: abs(x - r))
        return int(round(m[b] + 98.3 * (curve(r, n) - curve(b, n)))), f"프리미어리그 {season} {r}위"
    if lg == "FR1":   # 리그1: 평균 1714·흩어짐 95.6(기존 자료 1996-97·1997-98·1999-00 순위값 재현)
        m = ents_map("리그1", season)
        if r in m: return m[r], f"리그1 {season} {r}위"
        return int(round(1714 + 95.6 * curve(r, n))), f"리그1 {season} {r}위"
    if lg == "NL1":   # 에레디비시: 기존 자료 순위값(시즌 간 같음)
        return ERE[r], f"에레디비시 {season} {r}위"
    if lg == "PO1":
        return {1: 1912, 2: 1795, 3: 1716}[r], f"포르투갈 1부 {season} {r}위"
    if lg == "ES1":
        v, note = laliga(season, r, n)
        return v, f"라리가 {season} {r}위" + note
    return None

RANK_LG = ["IT1", "IT2", "IT3A", "IT3B", "AUS1", "IND1", "L1", "GB1", "FR1", "NL1", "PO1", "ES1"]

BL = {1: 2006, 2: 1912, 3: 1860, 4: 1828, 5: 1812, 6: 1797, 7: 1777, 8: 1756, 9: 1737, 10: 1723, 11: 1713, 12: 1705,
      13: 1697, 14: 1682, 15: 1663, 16: 1644, 17: 1634, 18: 1613}
ERE = {1: 1837, 2: 1735, 3: 1677, 4: 1642}
# 라리가: 기존 자료 2003-04 순위값(14위는 2004-05 − 1, 에투 자료와 같음) + 같은 시즌 기존 값과의 차(중앙값)
LL_BASE = ents_map("라리가", "2003-04"); LL_BASE[14] = 1661
def laliga(season, r, n):
    m = ents_map("라리가", season)
    if r in m and n == 20: return m[r], ""
    ref = season if m else "1999-00"
    m = ents_map("라리가", ref)
    diffs = sorted(v - LL_BASE[k] for k, v in m.items())
    sh = diffs[len(diffs) // 2] if len(diffs) % 2 else (diffs[len(diffs) // 2 - 1] + diffs[len(diffs) // 2]) / 2
    if n == 20: return int(round(LL_BASE[r] + sh)), ""
    p = 1 + (r - 1) / (n - 1) * 19; i = int(p); t = p - i   # 22팀 순위를 20칸 값에 보간
    v = LL_BASE[i] + (LL_BASE[min(i + 1, 20)] - LL_BASE[i]) * t
    return int(round(v + sh)), f" (추정: {ref} 리그 수준, {n}팀 순위 보간)"

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {
    (key("CSKA Sofia"), "1994-95"): (1450, "불가리아 1994-95 5위 (추정, 다른 선수 자료의 CSKA 소피아 2010 1450·레프스키 2001 1480 수준)"),
    (key("Steaua Bucharest"), "1995-96"): (1500, "루마니아 1위 (추정, 다른 선수 자료의 스테아우아 2006·2007 1500과 같음)"),
    (key("Rangers FC"), "1995-96"): (1620, "스코틀랜드 1995-96 1위 (추정, 다른 선수 자료의 레인저스 값 1620과 같음)"),
    (key("Rapid Vienna"), "1996-97"): (1530, "오스트리아 1996-97 2위 (추정, 다른 선수 자료의 라피트 빈 2001 1530과 같음)"),
    (key("CA River Plate"), "1996-97"): (1742, "아르헨티나 1부 아페르투라 1996 1위 (추정: 다른 선수 자료의 아르헨티나 1부 모형, 1996 리베르타도레스 우승팀)"),
    (key("1.FC Kosice (1951 - 2004)"), "1997-98"): (1400, "슬로바키아 1위 (추정, 다른 선수 자료의 질리나 1위 1400과 같음)"),
    (key("Dynamo Kyiv"), "1997-98"): (1640, "우크라이나 1997-98 1위 (추정, 다른 선수 자료의 디나모 키이우 값 1600~1660 사이)"),
    (key("Galatasaray"), "1998-99"): (1680, "튀르키예 1998-99 1위 (추정, 다른 선수 자료의 갈라타사라이 1위 값과 같음)"),
    (key("Omonia Nicosia"), "1999-00"): (1400, "키프로스 (추정, 다른 선수 자료의 키프로스 팀 1400~1450 수준)"),
    (key("Rostselmash Rostov"), "1999-00"): (1450, "러시아 1999 7위 (추정)"),
    (key("Olympiacos Piraeus"), "1999-00"): (1690, "그리스 1999-00 1위 (추정, 다른 선수 자료의 올림피아코스 1위 1690과 같음)"),
    (key("Celtic FC"), "2001-02"): (1620, "스코틀랜드 2001-02 1위 (추정, 다른 선수 자료의 셀틱 1위 값 1600~1640 사이)"),
    (key("Rosenborg BK"), "2001-02"): (1530, "노르웨이 2001 1위 (추정, 다른 선수 자료의 로센보리 2002 1530과 같음)"),
    (key("FC Basel 1893"), "2002-03"): (1600, "스위스 2002-03 2위 (추정, 다른 선수 자료의 바젤 2005 1600과 같음)"),
    (key("Dynamo Kyiv"), "2002-03"): (1620, "우크라이나 2002-03 1위 (추정, 다른 선수 자료의 디나모 키이우 2003 1620과 같음)"),
    (key("Galatasaray"), "2003-04"): (1620, "튀르키예 2003-04 6위 (추정, 다른 선수 자료의 갈라타사라이 6위 값과 같음)"),
    (key("Olympiacos Piraeus"), "2003-04"): (1640, "그리스 2003-04 2위 (추정, 다른 선수 자료의 올림피아코스 2위 1640과 같음)"),
    (key("Maccabi Tel Aviv"), "2004-05"): (1450, "이스라엘 2004-05 8위 (추정)"),
    (key("Djurgårdens IF"), "2004-05"): (1450, "스웨덴 2004 4위 (추정, 다른 선수 자료의 스웨덴 팀 1450과 같음)"),
    (key("Club Brugge KV"), "2005-06"): (1600, "벨기에 2005-06 3위 (추정, 다른 선수 자료의 브뤼허 2003 1620보다 조금 낮게)"),
    (key("FC Artmedia Petrzalka"), "2008-09"): (1400, "슬로바키아 2008-09 6위 (추정, 2007-08 우승팀, 다른 선수 자료의 슬로바키아 1위 1400과 같음)"),
    (key("Shamrock Rovers"), "2010-11"): (1350, "아일랜드 2010 1위 (추정, 다른 선수 자료의 섐록 로버스 2011 1350과 같음)"),
    (key("SK Sturm Graz"), "2010-11"): (1747, "오스트리아 분데스리가 2010-11 1위 (추정, 같은 시즌 라피트 빈 5위 1440과 같은 리그 수준·흩어짐 119)"),
}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def season_label(d, cid):
    if cid == "IND1": return d[:4]
    return season_eu(d)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_label(d, cid)
    # 1) 같은 경기 다른 선수 자료(날짜 ±1)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or (_sub(key(x["opp"]), k) and "jets" not in (key(x["opp"]) + " " + k).split()))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    euro = cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "UI", "WEPO", "USC")
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if euro else [eu]
    # 2) 같은 팀·같은 시즌 기존 값(팀×시즌 통합표)
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    # 3) 직접 추정
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    # 4) 순위표 + 리그 모형
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
def ldate(g):
    return g["date_local_tm_report"]

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
        if r["dp_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_label(d, cid), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, 0, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["dp_scorer"] == "1", e["dp_assist_other"] == "1", e["dp_self_assist"] == "1"
    if iss: judg.append(("본인 골의 본인 도움(도움 아님)", g["date_local_tm_report"], e["minute"]))
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
    fx = GOAL_MIN_FIX.get(f"{gid}|{e['minute']}|{e['score_home_away_after']}")
    if fx: mi, dm = fx
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP and tag not in ADD_CONFIRMED:
            if not any(abs(t - mi) <= 2 for t in FM_ASSIST.get(gid, [])):
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["dp_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV: continue
    fg = [r for r in FM_EV[gid] if r["dp_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_tm_report"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1" and t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty")
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local_tm_report"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Zlatan Ibrahimović": ("ibr.js", "IBR", "2004-08-01", "2006-08-01")}
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    return diffs
for nm, (fn, P, lo, hi) in MATES.items():
    ent = load_js(fn, P)
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("델 피에로 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and x[13] == "Alessandro Del Piero":
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→델 피에로 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    # TM 리포트가 델 피에로 도움으로 적었지만 이 자료에서 뺀 동료 골, 동료 도움이 빠진 델 피에로 골(참고)
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["dp_assist_other"] == "1" and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 델 피에로 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:
        if e["dp_scorer"] == "1" and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움이 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("paddp", "1993-07-01", "파도바", "1991~1993"), ("juvdp", "2012-07-01", "유벤투스", "1993~2012"),
         ("syddp", "2014-07-01", "시드니 FC", "2012~2014"), ("deldp", None, "델리 다이너모스", "2014")]
TM_CLUB = {"3037": "paddp", "506": "juvdp", "8054": "syddp", "45080": "deldp"}
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ORDER = [k for k, *_ in CLUBS]
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in ORDER)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
JUL = [m for m in M if club_of(m[0]) == "juvdp" and "07-10" <= m[0][5:] < "08-01"]   # 7월 10일 기준 근거
