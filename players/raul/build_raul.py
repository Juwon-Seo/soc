#!/usr/bin/env python3
"""Raúl González: raw/ -> raul.json + src/data/rau.js (판정 근거는 judgments.md)

  python3 players/raul/build_raul.py          # 쓰기
  python3 players/raul/build_raul.py --debug  # Elo 출처(통합표 외)
  python3 players/raul/build_raul.py --fm     # FotMob 골 대조(샬케 2010-12)
  python3 players/raul/build_raul.py --cross  # 동료(판니스텔로이·이과인·로번·호날두·벤제마·카카) 자료 대조
  python3 players/raul/build_raul.py --stat   # 요약

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv, raw/ranks.txt(순위표), raw/tables/tm_NASC_2014.html·tm_NAFC_2014.html(NASL 2015 승점),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/{nis,hig,rob,ron,bzm,kak}.js(같은 경기 동료 자료 대조).
카타르 국내 컵 2경기(Transfermarkt·FotMob에 없음)는 아래 QATAR_CUP 표(경기 기사 근거, judgments.md 3절).
"""
import csv, json, os, re, sys, unicodedata, collections, html as HTML
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "rau.js")
OUT_JSON = os.path.join(HERE, "raul.json")
ME = "라울 곤살레스"
CLUB_ID = {"418": "rmrau", "33": "s04rau", "656": "sadrau", "4835": "cosrau"}

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
EXCL_G = {}     # 골 제외 없음(라울 자책골 0)
EXCL_A = {}     # 상대 자책골 도움 3개는 자동 판정(득점 팀이 상대) — judgments.md 5절
PK_FIX = {}
MIN_FIX = {"78849|91": "90+1"}   # 2007.10.7 레크레아티보전: 리포트 시계 판독 91 → 90+1(이과인 자료와 같음)
AUTO_EXCL_TYPES = {"Penalty: Fouled player": "PK 유도", "Shot on goal": "슈팅 리바운드(Shot on goal)"}
GAP = "2014-08-01"   # 이후 도움은 Transfermarkt 단독 불가(코스모스 2015)
# 코스모스 2015 도움 3개: Transfermarkt 리포트 + 다른 출처 2곳 확인 여부(judgments.md 5절)
COSMOS_A_OK = {
    "2583750|45+2": "인디 일레븐 구단 경기 기사(라울 패스 → 레스트레포) + 미드필드 프레스 경기 요약",
    "2607222|43": "코스모스 구단 경기 기사(라울 패스 뒤 페르난드스 탭인) + 사우스 플로리다 스포츠 블로그(라울 패스)",
}

# 카타르 국내 컵(Transfermarkt·FotMob에 경기 없음). 경기 기사로 출전·골이 확인된 경기만:
# [날짜, 상대, 대회, 단계(ko), 골 분, 골 전 우리, 골 전 상대, PK, 근거]
QATAR_CUP = [
    ["2012-08-04", "Al-Mesaimeer SC", "dc", 0, 90, 1, 0, 1,
     "셰이크 자심컵 조별(2-0 승, 데뷔전): 걸프 타임스 2012.8.5 'Raul fires Al Sadd into semis'(골·출전), 스페인어 위키백과(90분 PK), 경기 블로그(정규시간 마지막 분 PK)"],
    ["2014-05-17", "Al-Sailiya SC", "df", 1, 33, 0, 0, 0,
     "에미르컵 결승(3-0 승): 페닌슐라 2014.5.18 'Clinical Al Sadd clinch Emir Cup'(33분 선제골), 걸프 타임스 'Sadd are Emir Cup champs'(라울 골·출전), 영어 위키백과 시즌 문서 32분"],
]

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES1", "L1", "QSL", "NASC", "NAFC"}
CUP = {"CDR", "DFB"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SUC", "USC", "DFL"): return "df"      # 슈퍼컵류 = 국내컵 결승
    if cid in ("WEPO", "KLUB"): return "cwc"          # 인터콘티넨털컵·클럽 월드 챔피언십 2000
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"        # 1999-2003 2차 조별(Group 1~4·A~D) 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"                     # 유로파 2011-12 플레이오프(HJK)
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 32강('Second Round')·16강·8강
    if cid == "AFCL":
        return "acl"   # 조별·16강
    if cid == "NAPL":
        if r.startswith("final"): return "mlpf"       # 사커볼(NASL 결승) = MLS컵 결승 코드(USL 플레이오프 선례)
        return "mlpsf"                                # NASL 준결승 = 콘퍼런스 결승 코드
    if cid == "MLSP": return "dc"                     # US 오픈컵 4·5라운드(32강·16강)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스·유로파·AFC 조별, 클럽 월드 챔피언십 2000 조별(리그식)
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]
    leg = 1 if "1st" in g["round"].lower() else 2
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    ag = 0 if g["competitionId"] == "AFCL" else 1   # AFC 대회 원정 다득점 없음(3절)
    return [leg, home, fu, ft, ag, 1]

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
MANUAL_ALIAS = {"inter milan": "inter"}
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
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))

def half_up(x): return int(x + 0.5)

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(추정 표시 없는 값, 다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

def mid(tab, r):
    """빈 순위: 앞뒤 기존 순위값의 가운데(한 칸 이상 비면 그 사이 직선, 0.5 올림)"""
    if r in tab: return tab[r], False
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up(tab[a] + (tab[b] - tab[a]) * (r - a) / (b - a)), True

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
# 라리가 1994-95~1998-99: 기존 자료가 거의 없음 → 호나우두 판정(1996-97)과 같은 모형:
# 2003-04 순위값 ≈ 1712.7 + 100.16 × 곡선, 평균을 1995-96·1998-99 기존 값 차이 평균(+13.5)만큼 올림(추정)
LL_OLD_MEAN = 1712.7 + 13.5
LL_SD = 100.16
SEG = [1753, 1712, 1687, 1674, 1660, 1654, 1647, 1640, 1632, 1623, 1615, 1610, 1606, 1601, 1598, 1595, 1589, 1580, 1572, 1567, 1560, 1553]  # 세군다 22팀(기존 고정값)
# 카타르 스타스리그: 마레즈·에투 자료와 같은 모형(평균 1460, 흩어짐 45 × 곡선, 추정)
QSL_MEAN, QSL_SD = 1460, 45
# 분데스리가 2003-04 이전: 기존 자료 고정 순위값(시즌마다 같음)
BL_OLD = {}
for e in ENTS:
    m = re.match(r"^분데스리가 (199\d|200[0-3])-\d\d (\d+)위$", e["lv"] or "")
    if m: BL_OLD.setdefault(int(m.group(2)), collections.Counter())[e["elo"]] += 1
BL_OLD = {r: c.most_common(1)[0][0] for r, c in BL_OLD.items()}

def edge(tab, r, n, sd):
    """끝 순위(앞이나 뒤에 기존 값이 없음): 가장 가까운 기존 순위값 + 흩어짐 × 순위 곡선 차이"""
    k = min(tab, key=lambda x: abs(x - r))
    return half_up(tab[k] + sd * (curve(r, n) - curve(k, n)))
# NASL(미국 2부) 2015: USL(미국 2부) 선례 평균 1353, 흩어짐 SD2(추정). 순위는 봄·가을 시즌 합산 승점(동률은 골득실)
NASL_MEAN = 1353

def nasl_combined():
    tot = collections.defaultdict(lambda: [0, 0, 0])
    for fn in ("tm_NASC_2014.html", "tm_NAFC_2014.html"):
        t = open(os.path.join(RAW, "tables", fn), encoding="utf-8", errors="ignore").read()
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
            c = [HTML.unescape(re.sub("<[^>]+>", "", x)).replace("\xa0", "").strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
            c = [x for x in c if x]
            if len(c) == 9 and c[0].isdigit():
                gfga = c[6].split(":")
                tot[c[1]][0] += int(c[8]); tot[c[1]][1] += int(gfga[0]) - int(gfga[1]); tot[c[1]][2] += int(gfga[0])
    order = sorted(tot, key=lambda k: (-tot[k][0], -tot[k][1], -tot[k][2]))
    return {k: (i + 1, tot[k]) for i, k in enumerate(order)}
NASL_SHORT = {"NY Cosmos": "New York Cosmos", "TB Rowdies": "Tampa Bay Rowdies", "RailHawks": "Carolina RailHawks FC",
              "Minnesota NASL": "Minnesota United FC (NASL)", "Indy Eleven": "Indy Eleven", "J'ville Armada": "Jacksonville Armada FC",
              "San Antonio": "San Antonio Scorpions FC", "Fort Lauderdale": "Fort Lauderdale Strikers", "Ottawa Fury": "Ottawa Fury FC",
              "FC Edmonton": "FC Edmonton", "Silverbacks": "Atlanta Silverbacks FC"}
NASL15 = {key(NASL_SHORT[k]): v for k, v in nasl_combined().items()}
assert len(NASL15) == 11

LL_INTERP = set()
def model(lg, season, r, n):
    """(Elo, lv) — 순위표 + 기존 순위값/리그 모형"""
    if lg == "ES1":
        m = ents_map("라리가", season)
        if int(season[:4]) <= 1998:
            if r in m: return m[r], f"라리가 {season} {r}위"
            return half_up(LL_OLD_MEAN + LL_SD * curve(r, n)), f"라리가 {season} {r}위 (리그 수준 추정)"
        v, it = mid(m, r)
        if v is None:
            v = edge(m, r, n, LL_SD); LL_INTERP.add((season, r, v, "끝"))
            return v, f"라리가 {season} {r}위 (추정, 이웃 순위값에 순위 곡선 차이)"
        if it: LL_INTERP.add((season, r, v))
        return v, f"라리가 {season} {r}위"
    if lg == "L1" and int(season[:4]) <= 2003:
        v, it = mid(BL_OLD, r)
        return v, f"분데스리가 {season} {r}위"
    if lg == "L2":
        m = ents_map("2. 분데스리가", season)
        v, it = mid(m, r)
        if v is None:
            return edge(m, r, n, SD2), f"2. 분데스리가 {season} {r}위 (추정, 이웃 순위값에 순위 곡선 차이)"
        return v, f"2. 분데스리가 {season} {r}위"
    if lg == "ES2":
        if n == 22: return SEG[r - 1], f"세군다(2부) {season} {r}위"
        return half_up(1624 + SD2 * curve(r, n)), f"세군다(2부) {season} {r}위"
    if lg == "QSL":
        return half_up(QSL_MEAN + QSL_SD * curve(r, n)), f"카타르 {season} {r}위 (추정, 마레즈 자료와 같은 리그 수준)"
    return None

RANK_LG = ["ES1", "ES2", "L1", "L2", "QSL"]

# 직접 추정(모두 '추정'): (key, 시즌) -> (Elo, lv)
def _k(n): return key(n)
MAN = {
    (_k("Ferencvárosi TC"), "1995-96"): (1450, "헝가리 1995-96 1위 (추정, 다른 선수 자료 잘라에게르세그 2002-03 4위 1420보다 조금 높게)"),
    (_k("Grasshopper Club Zurich"), "1995-96"): (1600, "스위스 1995-96 1위 (추정, 다른 선수 자료 그라스호퍼 2013-14 2위 1609와 비슷하게)"),
    (_k("Rosenborg BK"), "1997-98"): (1500, "노르웨이 1997 1위 (추정, 다른 선수 자료 로센보리 2004·2010 1위 1500과 같음)"),
    (_k("Rosenborg BK"), "1999-00"): (1500, "노르웨이 1999 1위 (추정, 다른 선수 자료 로센보리 2004·2010 1위 1500과 같음)"),
    (_k("Olympiacos Piraeus"), "1997-98"): (1690, "그리스 1997-98 1위 (추정, 다른 선수 자료 올림피아코스 1위 1690과 같음)"),
    (_k("Olympiacos Piraeus"), "2005-06"): (1690, "그리스 2005-06 1위 (추정, 다른 선수 자료 올림피아코스 1위 1690과 같음)"),
    (_k("SK Sturm Graz"), "1998-99"): (1720, "오스트리아 1998-99 1위 (추정, 다른 선수 자료 슈투름 그라츠 1위 2010-11 1747·2022-23 1713 사이)"),
    (_k("Spartak Moscow"), "1998-99"): (1600, "러시아 1998 1위 (추정, 다른 선수 자료 스파르타크 모스크바 2000-01 1위 1600과 같음)"),
    (_k("Club Necaxa"), "1999-00"): (1560, "멕시코 1부 상위권 (추정, 다른 선수 자료 클루브 아메리카·아틀란테 1560과 같음)"),
    (_k("Al-Nassr FC"), "1999-00"): (1500, "사우디 1999-00 4위 (추정, 다른 선수 자료 AFC 챔스 우승팀 1560보다 낮게)"),
    (_k("Dynamo Kyiv"), "1999-00"): (1640, "우크라이나 1999-00 1위 (추정, 다른 선수 자료 디나모 키이우 1997-98 1위 1640과 같음)"),
    (_k("Dynamo Kyiv"), "2004-05"): (1600, "우크라이나 2004-05 2위 (추정, 다른 선수 자료 디나모 키이우 2001-02 2위 1600과 같음)"),
    (_k("Galatasaray"), "2000-01"): (1660, "튀르키예 2000-01 2위 (추정, 2000 UEFA컵 우승팀, 다른 선수 자료 갈라타사라이 1위 1680보다 조금 낮게)"),
    (_k("RSC Anderlecht"), "2001-02"): (1597, "벨기에 1부 2001-02 3위 (추정, 다른 선수 자료 안더레흐트 2010-11 3위 1597과 같음)"),
    (_k("Lokomotiv Moskau"), "2002-03"): (1600, "러시아 2002 1위 (추정, 다른 선수 자료 로코모티프 모스크바 2001 1580·2017-18 1위 1640 사이)"),
    (_k("AEK Athens"), "2002-03"): (1550, "그리스 2002-03 3위 (추정, 다른 선수 자료 AEK 2003-04 상위권 1550과 같음)"),
    (_k("KRC Genk"), "2002-03"): (1550, "벨기에 2002-03 6위·전 시즌 우승팀 (추정, 다른 선수 자료 겡크 2009-10 1550과 같음)"),
    (_k("UD San Sebastián de los Reyes"), "2003-04"): (1350, "스페인 3부 (추정, 다른 선수 자료 스페인 3부 1350과 같음)"),
    (_k("FC Teningen"), "2011-12"): (1150, "독일 6부 이하 (추정, 다른 선수 자료 리엘라싱겐 1150과 같음)"),
    (_k("Steaua Bucharest"), "2011-12"): (1500, "루마니아 2011-12 3위 (추정, 다른 선수 자료 슈테아우아 2위 1500과 같음)"),
    (_k("HJK Helsinki"), "2011-12"): (1400, "핀란드 2011 1위 (추정, 다른 선수 자료 HJK 2022 1위 1400과 같음)"),
    (_k("Al-Mesaimeer SC"), "2012-13"): (1300, "카타르 2부 2012-13 (추정, 카타르 1부 평균 1460 − 독일 1·2부 평균 차)"),
}
FIXED = {
    (_k("Juventus FC"), "1995-96"): (1884, "세리에A 1995-96 2위"),     # 세리에A 18팀 순위 고정값(호나우두·토티·델 피에로 자료)
    (_k("FC Porto"), "1997-98"): (1912, "포르투갈 1부 1997-98 1위"),  # 포르투갈 1부 1위 기존 값
    (_k("FC Porto"), "1999-00"): (1795, "포르투갈 1부 1999-00 2위"),  # 포르투갈 1부 18팀 2위 기존 값
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
    if cid in ("NASC", "NAFC", "NAPL", "MLSP"):
        seasons = [d[:4]]
    elif cid in ("CL", "CLQ", "EL", "ELQ", "USC", "WEPO", "KLUB", "AFCL"):
        seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)]
    else:
        seasons = [eu]
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
    if cid in ("NASC", "NAFC", "NAPL") and k in NASL15:
        r = NASL15[k][0]
        e = half_up(NASL_MEAN + SD2 * curve(r, 11))
        lv = f"NASL(미국 2부) 2015 합산 {r}위 (리그 수준 추정)"
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, e, lv, "model"))
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
    return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

def ldate(g):
    return g["date_local"]   # 유럽·카타르 = Transfermarkt 날짜, 코스모스 = 뉴욕 현지

M = []
for g in GAMES:
    M.append([ldate(g), opp_name(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
for q in QATAR_CUP:
    M.append([q[0], q[1], q[2], 90, 1])   # 출전 분 자료 없음 → 90분 추정
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

# 골 전 스코어: 리포트 골 순서대로 득점 팀별로 셈(2193875 자책골 표시 오류를 피함)
BEFORE = {}
EV_BY = collections.defaultdict(list)
for i, e in enumerate(EVENTS): EV_BY[e["gameId"]].append(i)
for gid, idx in EV_BY.items():
    h = a = 0
    for i in idx:
        BEFORE[i] = (h, a)
        if EVENTS[i]["side"] == "home": h += 1
        else: a += 1
    if gid in INFO and INFO[gid]["final"] and gid in G:
        fh, fa = map(int, INFO[gid]["final"].split(":"))
        if (h, a) != (fh, fa) and G[gid]["gameState"] != "penalty_shootout" and gid not in ("1128250",):
            print("리포트 골 수와 최종 스코어 다름:", gid, (h, a), (fh, fa))

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

LATE_A = []
for i, e in enumerate(EVENTS):
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa = e["raul_scorer"] == "1", e["raul_assist_other"] == "1"
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    side_home = e["side"] == "home"
    h, a = BEFORE[i]
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    tag = f"{gid}|{e['minute']}"
    mi, dm = minute(MIN_FIX.get(tag, e["minute"]))
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout", "golden_goal")) else 0
    d = ldate(g); opp = opp_name(g)
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        if e["raul_self_assist"] == "1":
            judg.append(("도움 아님(본인 PK 골의 본인 도움)", d, opp, e["minute"], e["assist_type"]))
        add_row("g", mi, dm, gf, ga, int((e["penalty"] == "1" and e["goal_desc"] == "Penalty") or tag in PK_FIX), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        if e["own_goal"] == "1" or not ours:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "상대 자책골 유도")); continue
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["assist_type"] in AUTO_EXCL_TYPES:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], AUTO_EXCL_TYPES[e["assist_type"]])); continue
        if d >= GAP and tag not in COSMOS_A_OK:
            LATE_A.append((d, opp, e["minute"], e["scorer"], e["assist_type"], tag))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "2014-08 이후 단일 출처(다른 출처 2곳 확인 못 함)")); continue
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

for q in QATAR_CUP:
    add_row("g", q[4], 0, q[5], q[6], q[7], 0, None, q[2], q[3], q[0], q[1], "QCUP", 0)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k)
        if not x[4].startswith("table") and not x[4].startswith("same"): print(x)
    print("라리가 가운데값:", sorted(LL_INTERP))
if __name__ == "__main__" and "--table" in sys.argv:
    seen = set()
    for x in ELO_LOG:
        if (x[4].startswith("table") or x[4].startswith("same")) and (x[1], x[2]) not in seen:
            seen.add((x[1], x[2])); print(x)

# ---------------------------------------------------------------- FotMob 골 대조(샬케 2010-12; 카타르 리그는 FotMob 골 기록 없음)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["raul_scorer"] == "1" and e["own_goal"] != "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
FM_GAMES = 0
for gid, evs in TMG.items():
    if gid not in FM_EV or not FM_EV[gid]: continue
    FM_GAMES += 1
    fg = [r for r in FM_EV[gid] if r["raul_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        h, a = map(int, t["score_home_away_after"].split("-")); fh, fa = map(int, f["newScore_home_away"].split("-"))
        if tpk != fpk or abs(tm_min - fm_min) > 1 or (h, a) != (fh, fa):
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], t["score_home_away_after"], f["time"], f["overloadTime"], f["newScore_home_away"], f["goalDescriptionKey"], f["suffix"]))
# FotMob 도움(라울) 대조
FM_A = collections.defaultdict(list)
for gid, lst in FM_EV.items():
    for r in lst:
        if r["raul_assist"] == "1" and gid in G: FM_A[gid].append(r)
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)
    print("FotMob 골 대조 경기", FM_GAMES)
    for gid, lst in FM_A.items():
        for r in lst: print("FotMob 라울 도움", gid, ldate(G[gid]), r["time"], r["scorer"])

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    t = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", t, re.S)
    return json.loads(m.group(1))
ME_TM = {"Raúl", "Raúl González"}
MATES = {"Ruud van Nistelrooy": ("nis.js", "NIS", "2006-07-28", "2010-01-24"), "Gonzalo Higuaín": ("hig.js", "HIG", "2007-01-01", "2010-07-28"),
         "Arjen Robben": ("rob.js", "ROB", "2007-08-22", "2009-08-29"), "Cristiano Ronaldo": ("ron.js", "RON", "2009-07-01", "2010-07-28"),
         "Karim Benzema": ("bzm.js", "BZM", "2009-07-01", "2010-07-28"), "Kaká": ("kak.js", "KAK", "2009-07-01", "2010-07-28")}
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items()}
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
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    return diffs
def nm_eq(a, b): return norm(a) == norm(b)
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:   # 라울 도움 → 동료 골
        if r[0] == "a" and nm_eq(r[13], nm) and lo <= r[9] < hi:
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("라울 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:  # 동료 도움 → 라울 골
        if x[0] == "a" and x[13] in ME_TM and lo <= x[9] < hi:
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→라울 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:  # 같은 경기 Elo/lv/대회
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "연장"))]
                    if dd: CROSS.append(("같은 경기 다름", nm, r[9], r[1], dd))
                    break
    for x in ent:  # 동료 골에 TM 라울 도움이 있는데 이 파일에 도움 행이 없음
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["raul_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 라울 도움을 뺀 동료 골(규칙대로 제외)", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:  # TM 동료 도움 → 라울 골이 동료 파일에 없음
        if e["raul_scorer"] == "1" and e["gameId"] in G and nm_eq(e["assist_player"], nm):
            d = ldate(G[e["gameId"]])
            if lo <= d < hi and not any(x[0] == "a" and x[9] == d and abs(x[4] - minute(e["minute"])[0]) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움이 동료 파일에 없음", nm, d, e["minute"], e["assist_type"], e["goal_desc"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] for c in CROSS if c[-1] == "같음"), collections.Counter(c[0] for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("rmrau", "2010-07-28", "레알 마드리드", "1994~2010"), ("s04rau", "2012-07-01", "샬케 04", "2010~2012"),
         ("sadrau", "2014-10-30", "알사드", "2012~2014"), ("cosrau", None, "뉴욕 코스모스", "2014~2015")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != CLUB_ID[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club == "cosrau": return str(y)
    if club == "s04rau": s = y if d[5:] >= "07-10" else y - 1
    else: s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
if __name__ == "__main__" and "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E), sum(r[8] for r in E), sum(m[3] for m in M), len(E))
    for j in judg: print(j)
    print("합산", sum(1 for r in E if len(r) > 14), len({r[9] for r in E if len(r) > 14}), "연장", [r for r in E if r[10]])
    print("단판", collections.Counter((r[3], r[7]) for r in E))
    ss = collections.Counter(season_of(m[0], club_of(m[0])) for m in M); print(sorted(ss.items()))

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_UNTYPED = sum(1 for e in EVENTS if e["raul_assist_other"] == "1" and e["assist_type"] == "" and e["gameId"] in G)
SRC = ELO_SRC
NOTE_LINES = [
    f"라울 곤살레스(레알 마드리드·샬케 04·알사드·뉴욕 코스모스)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 레알 사라고사전 ~ {d_(M[-1][0])} 오타와 퓨리전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·스페인 대표팀·레알 마드리드 C·B(2군) 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분(연장·퇴장·교체 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있거나 리그 밖 대회인 모든 경기, 리포트 골·도움이 선수 경기 성적과 모든 경기에서 같음). FotMob은 2010-11 이전 경기 기록이 없고 카타르 리그·NASL 경기에는 골 기록이 없어 샬케 2010-12 골만 대조함(골 시각·스코어·PK 같음, 2010.11.20 베르더 브레멘전 전반 추가시간 골은 FotMob이 45분으로만 적어 Transfermarkt 45+2분을 씀)",
    "경기·골은 영어 위키백과 클럽·시즌별 기록과 레알 마드리드 741경기 323골·샬케 98경기 40골·코스모스 32경기 9골 모두 같음(샬케 2011.7.23 DFL-슈퍼컵·2011.7.31 DFB 포칼 1라운드는 이 계산에서 2011-12 시즌). 레알 마드리드 C(3부, 9경기 16골)·카스티야(2부, 1경기)는 2군이라 뺌. 1994-95 UEFA컵 4경기는 Transfermarkt에서 명단 제외·다른 팀(C팀) 경기로만 적혀 있어 출전 아님",
    "알사드: Transfermarkt·FotMob은 리그 39경기 11골·AFC 챔피언스리그 5경기만 있고, 위키백과는 국내 컵 17경기 5골(셰이크 자심컵 5경기 3골·스타스컵 4경기·에미르컵 6경기 2골·왕세자컵 2경기)을 더 적음. 경기 기사로 날짜·상대·출전·골 시각을 확인한 2경기만 넣음: 2012.8.4 셰이크 자심컵 조별 알메사이미르전 2-0 승 90분 PK 골(걸프 타임스 2012.8.5 기사·스페인어 위키백과·경기 블로그; 영어 위키백과는 연장 PK로 적음), 2014.5.17 에미르컵 결승 알사일리야전 3-0 승 33분 선제골(페닌슐라 2014.5.18 기사 33분·걸프 타임스 기사·영어 위키백과 시즌 문서 32분 — Transfermarkt는 이 경기에 라울을 '명단 제외'로 적었으나 두 신문 기사가 출전·골을 적어 기사를 따름). 두 경기 출전 분은 자료가 없어 90분으로 추정. 나머지 15경기 3골(2012 셰이크 자심컵 4강 알아라비전 3-0 골 등)은 골 시각이나 출전 기록을 찾지 못해 넣지 않음. 2012.8.4 경기의 벨하지 골 도움(걸프 타임스 기사만)은 출처가 하나라 넣지 않음",
    f"도움: 2014년 8월 이전 도움은 Transfermarkt 경기 리포트 단일 출처(선례). Transfermarkt 도움 161개에서 PK 유도 12개, 슈팅 리바운드('Shot on goal') 13개, 상대 자책골에 준 도움 3개(1999.10.20 포르투전 페이시, 2000.9.12 스포르팅전 후이 조르즈, 2001.12.15 레알 소시에다드전 크바르메)를 빼 {NA}개. 도움 유형 칸이 빈 {N_UNTYPED}개는 일반 도움으로 셈. 코스모스 2015 도움 2개(7.25 인디 일레븐전 45+2분 레스트레포, 8.2 포트로더데일전 43분 페르난드스)는 Transfermarkt 외에 구단·현지 매체 경기 기사 두 곳씩으로 확인했고, 8.14 샌안토니오전 45분 페르난드스 골은 'Shot on goal'이라 뺌. 본인 PK 골의 본인 도움 표기는 없음",
    "도움 출처 차이: 스페인어 위키백과 시즌별 도움 합계(레알 마드리드 115·샬케 15·알사드 13·코스모스 3)와 FotMob 경력 합계(샬케 12, 알사드·코스모스 0)는 Transfermarkt와 시즌마다 위아래로 달라 쓰지 않음. 알사드 도움 0은 Transfermarkt 카타르 리포트에 라울 도움 표기가 없기 때문(스페인어 위키백과 13개는 경기별 근거가 없음). 1990년대 Transfermarkt 리포트는 도움 표기가 빠진 골이 있어 실제보다 적을 수 있음",
    "골: 자책골·제외한 골 없음. PK 골은 Transfermarkt 골 유형 'Penalty' 12개(선수 경기 성적 PK 골 수와 같음) + 알사드 컵 1개. 1999.3.21 엑스트레마두라전은 리포트가 52분 상대 자책골 뒤 스코어를 1-1로 잘못 적었으나 라울 골(29분 선제골)은 영향 없음(골 순서대로 다시 셈)",
    "출전 분: Transfermarkt 그대로. 2011.4.1 장크트파울리전은 관중 난입으로 88분에 중단된 경기(88분). 연장: 2000.8.25 UEFA 슈퍼컵 갈라타사라이전(골든골 패, 102분), 2003.12.18 코파 델 레이 레가네스전(120분, 110분 골), 2004.3.17 코파 델 레이 결승 사라고사전, 2011.1.25 DFB 포칼 뉘른베르크전, 2012.2.23 유로파리그 플젠전(120분). 승부차기만 한 2000.1.14 클럽 월드 챔피언십 3위 결정전 네카사전(66분 출전)·2011.7.23 DFL-슈퍼컵 도르트문트전·2015.6.17 US 오픈컵 뉴욕 시티전은 연장 없음",
    "날짜: 유럽·카타르 경기는 Transfermarkt 날짜(현지). 코스모스 경기는 Transfermarkt 날짜가 저녁 경기마다 하루 뒤(UTC 기준)라 뉴욕 현지 날짜로 바꿈",
    "상대 Elo는 같은 경기를 다룬 다른 선수 자료(판니스텔로이·이과인·로번·호날두·벤제마·카카·에투·앙리 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 순위값·리그 모형에 넣은 값 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+순위값·모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "라리가 1994-95~1998-99는 다른 선수 자료가 거의 없어 리그 수준을 추정함(설명에 '리그 수준 추정'): 2003-04 순위별 값과 같은 흩어짐(약 100)에 평균을 1995-96·1998-99 기존 값과의 차이만큼(+13.5) 올려 순위 곡선으로 계산(20팀 1위 1979 ~ 20위 1589, 22팀 시즌도 같은 방식; 호나우두 자료 1996-97과 같은 방식). 라리가 1999-00~2002-03의 기존 자료에 없는 순위는 앞뒤 순위값의 가운데, 맨 끝 순위(1999-00 20위 세비야 1587, 2000-01 19·20위 라싱·누만시아 1626·1606, 2001-02 1위 발렌시아 1981·20위 사라고사 1592)는 가장 가까운 기존 순위값에 순위 곡선 차이를 더한 추정",
    "그 밖의 순위값: 세군다(2부) 22팀은 기존 고정값, 20팀 시즌은 2부 모형(평균 1624). 분데스리가 2003-04 이전은 기존 순위별 고정값(레버쿠젠 2000-01 4위 1828), 2. 분데스리가 2010-11 2위 아우크스부르크는 3위 기존 값에 순위 곡선 차이를 더한 추정 1661. 세리에A 1995-96 2위 유벤투스 1884(18팀 고정값), 포르투갈 1부 1997-98 1위 포르투 1912·1999-00 2위 1795(기존 같은 순위 값). 카타르 리그는 마레즈·에투 자료와 같은 모형(평균 1460·흩어짐 45 × 순위 곡선, 추정), 카타르 2부 알메사이미르 1300(에투 자료와 같은 방식). NASL(미국 2부) 2015는 USL(미국 2부) 선례와 같은 평균 1353·2부 흩어짐에 봄·가을 시즌 합산 순위(승점, 동률은 골득실)를 넣은 추정(1위 코스모스, 3위 미네소타 1388 ~ 11위 잭슨빌 1283)",
    "직접 추정(모두 '추정'): 페렌츠바로시 1995-96 1450, 그라스호퍼 1995-96 1600, 로센보리 1997·1999 1500, 올림피아코스 1997-98·2005-06 1690, 슈투름 그라츠 1998-99 1720, 스파르타크 모스크바 1998 1600, 네카사 1999-00(멕시코) 1560, 알나스르 1999-00(사우디) 1500, 디나모 키이우 1999-00 1640·2004-05 1600, 갈라타사라이 2000-01 1660, 안더레흐트 2001-02 1597, 로코모티프 모스크바 2002 1600, AEK 아테네 2002-03 1550, 겡크 2002-03 1550, 산세바스티안 데 로스 레예스 2003-04(스페인 3부) 1350, 테닝겐 2011-12(독일 6부 이하) 1150, 슈테아우아 2011-12 1500, HJK 2011 1400 — 모두 다른 선수 자료의 같은 팀·같은 리그 비슷한 순위 값에 맞춤",
    "대회 비중: 코파 델 레이·DFB 포칼·US 오픈컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), 수페르코파·UEFA 슈퍼컵·DFL-슈퍼컵은 국내컵 결승 비중. 인터콘티넨털컵(1998·2000·2002)과 2000년 FIFA 클럽 월드 챔피언십은 클럽 월드컵 비중(챔피언십 조별리그 3경기는 리그식, 3위 결정전은 단판). 챔스 1999-2003 2차 조별리그는 챔스 조별, 유로파리그 2011-12 플레이오프(HJK)는 유로파 예선, 32강·16강·8강은 유로파 토너먼트. AFC 챔피언스리그(골·도움 없음)는 AFC 챔스. 카타르 셰이크 자심컵 조별은 국내컵 리그식, 에미르컵 결승은 국내컵 결승. NASL 봄·가을 시즌은 리그, NASL 플레이오프 준결승·사커볼(결승)은 USL 플레이오프 선례대로 MLS 플레이오프 준결승·결승 비중",
    f"두 경기 합산(코파 델 레이 1990~2000년대 두 경기 라운드, 수페르코파, 챔스 예선·토너먼트, 유로파 토너먼트) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 적용). 2차전 기록의 1차전 스코어는 Transfermarkt 경기 리포트로 채움. 라울이 뛰지 않은 1차전이 쓰인 기록: 2003.5.14 유벤투스전(1차전 홈 2-1), 2005.1.18 바야돌리드전(1차전 원정 0-0), 2008.11.11 레알 우니온전 3골(1차전 원정 2-3, 원정 다득점으로 탈락), 2011.8.25 HJK전(1차전 원정 0-2)",
    "시즌 구분: 레알 마드리드·알사드는 8월 1일 기준(레알 마드리드의 같은 경기는 판니스텔로이·이과인·로번·호날두·벤제마·카카 자료와 같은 시즌), 샬케는 7월 10일 기준(2011.7.23 DFL-슈퍼컵·7.31 DFB 포칼 1라운드는 2011-12), 코스모스는 달력 연도(2015). 클럽 구분: 2010.7.28 전 레알 마드리드, 2012.7.1 전 샬케, 2014.10.30 전 알사드, 이후 코스모스",
    "같은 경기 동료 자료: 판니스텔로이(라울 도움 6·판니스텔로이 도움 6)·이과인(라울 도움 5·이과인 도움 6)·로번(라울 도움 1)·호날두(호날두 도움 1)와 주고받은 골·도움은 날짜·분·골 전 스코어·대회·상대 Elo·수준 설명·합산 정보가 모두 같음. 규칙대로 양쪽에서 빠진 것: 2008.8.31 데포르티보전 47분 판니스텔로이 골(라울 슈팅 리바운드), 2009.8.29 데포르티보전 35분 호날두 PK(라울 PK 유도), 동료들의 슈팅 리바운드 도움 6개(2006.10.17 판니스텔로이, 2008.9.24 로번, 2009.1.31·2.15 이과인, 2009.8.29 벤제마, 2009.10.21 카카)",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 라리가 6회(1994-95·1996-97·2000-01·2002-03·2006-07·2007-08), 챔스 3회(1997-98·1999-00·2001-02), 인터콘티넨털컵 2회(1998·2002), UEFA 슈퍼컵 2002, 수페르코파 4회(1997·2001·2003·2008), DFB 포칼 2011·DFL-슈퍼컵 2011(샬케), 카타르 리그 2012-13·에미르컵 2014(알사드), NASL 사커볼 2015·정규시즌 우승(코스모스). 준우승은 인터콘티넨털컵 2000(보카 주니어스; Transfermarkt는 99/00으로 적음)만 넣음 — Transfermarkt의 '클럽 월드컵 준우승 99/00'은 2000년 챔피언십 3위 결정전 패배(4위)라 뺌. 개인: 스페인 올해의 선수 5회(1997·1999·2000·2001·2002), 득점왕 6회(라리가 1998-99 25골·2000-01 24골, 챔스 1999-00 10골, 코파 델 레이 2001-02·2003-04 6골, 수페르코파 1997-98 3골). U-21 유럽선수권 득점왕은 대표팀 기록이라 뺌",
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
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[0] == "a" and r[13] in ME_TM: problems.append(("본인 도움", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
mm = {m[0]: m for m in M}
for r in E:
    m = mm.get(r[9])
    if m and m[1] != r[1]: problems.append(("상대 이름 다름", r[9], r[1], m[1]))
    if m and m[2] != r[3]: problems.append(("대회 다름", r[9], r[3], m[2]))
    if m and r[4] > 90 and m[3] < 100 and not r[11]: problems.append(("연장 분인데 출전 짧음", r))
    if m and r[4] > m[3] + 5 and m[3] < 90: pass
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const RAU_E={J(E)};\nconst RAU_M={J(M)};\nconst RAU_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG, "qatar_cup_added": QATAR_CUP,
               "cosmos_assists_confirmed": COSMOS_A_OK},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
