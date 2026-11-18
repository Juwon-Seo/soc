#!/usr/bin/env python3
"""Aílton (Transfermarkt 516): raw/ -> ailton.json + src/data/ail.js (판정 근거는 judgments.md)

  python3 players/ailton/build_ailton.py            # 파일 쓰기
  python3 players/ailton/build_ailton.py --debug    # Elo 출처·도움 판정 로그
  python3 players/ailton/build_ailton.py --cross    # 같은 경기 다른 선수 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/ranks.txt, raw/tables/tm_MEX1_1997.html, extra/tm_MEXA_1997.html(인비에르노 1997 표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv, src/data/*.js(동료·상대 대조).
FotMob에는 이 선수 자료가 없음(raw/README.md). 판정 표는 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, glob, html, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "ail.js")
OUT_JSON = os.path.join(HERE, "ailton.json")
ME = "아일톤"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 범위
# 프로 리그가 아닌 팀-시즌(사용자 기준 v1.159): KFC 위르딩겐 2009-10(오버리가 니더라인, 5부)·FC 오버노일란트 2010-11(레기오날리가 노르트, 4부; DFB-포칼 1경기 포함)
EXCL_CLUB = {"95": "KFC 위르딩겐 05", "115": "FC 오버노일란트"}
ALL_GAMES = rd("tm_games.csv")
EXCLUDED = [g for g in ALL_GAMES if g["club_id"] in EXCL_CLUB]
GAMES = [g for g in ALL_GAMES if g["club_id"] not in EXCL_CLUB]
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
OTHER = {}
for r in rd("tm_two_leg_ties.csv"):
    OTHER[r["gameId"]] = r["other_leg_id"]

CLUB_KEY = {"6600": "intail", "1755": "guaail", "7055": "tigail", "86": "svwail", "33": "s04ail", "114": "besail",
            "41": "hsvail", "159": "crvail", "504": "gcail", "52": "msvail", "2783": "metail", "3551": "altail", "1326": "chqail"}
CLUBS = [("intail", "1996-07-01", "인테르나시오나우", "인테르나시오나우", "1995"),
         ("guaail", "1998-01-01", "과라니", "과라니", "1996~1997"),
         ("tigail", "1998-10-15", "티그레스 UANL", "티그레스", "1998"),
         ("svwail", "2004-07-01", "베르더 브레멘", "브레멘", "1998~2004"),
         ("s04ail", "2005-07-21", "샬케 04", "샬케", "2004~2005"),
         ("besail", "2006-01-24", "베식타시", "베식타시", "2005~2006"),
         ("hsvail", "2006-08-31", "함부르크 SV", "함부르크", "2006"),
         ("crvail", "2007-02-14", "츠르베나 즈베즈다", "츠르베나 즈베즈다", "2006~2007"),
         ("gcail", "2007-07-01", "그라스호퍼", "그라스호퍼", "2007"),
         ("msvail", "2008-02-25", "MSV 뒤스부르크", "뒤스부르크", "2007~2008"),
         ("metail", "2008-08-31", "메탈루르흐 도네츠크", "메탈루르흐", "2008"),
         ("altail", "2009-01-01", "SCR 알타흐", "알타흐", "2008"),
         ("chqail", None, "충칭 리판", "충칭", "2009")]
def club_of(d):
    for k, u, *_ in CLUBS:
        if u is None or d < u: return k

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BRA1", "MEX1", "MEXA", "L1", "TR1", "C1", "SER1", "UKR1", "A1", "CSL"}
CUP = {"DFB", "SCC", "UKRP"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"   # 브라질 1996 결승 단계(TM 숫자 라운드)도 리그(제 호베르투·주니뉴 선례)
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 1·2·3라운드·16강
    if cid == "LPO":   # DFB-리가포칼: 첫 경기 dk, 준결승 dsf, 결승 df(클로제·외질·엘베르·알틴톱 선례)
        if r.startswith("semi"): return "dsf"
        if r.startswith("intermediate"): return "dk"
        if r.startswith("final"): return "df"
    if cid in ("UI", "UEQ"): return "elq"   # 인터토토컵·UEFA컵 예선 = 유로파 예선
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전)
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 2·3라운드·16강·8강·intermediate stage(32강)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g): return "leg" in g["round"].lower()
def ko_of(g):
    if is_leg(g) or g["competitionId"] in LEAGUE or g["round"].lower().startswith("group"): return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]
    leg = 1 if "1st" in g["round"].lower() else 2
    o = INFO[OTHER[gid]]
    if (o["date_report"] < inf["date_report"]) != (leg == 2): sys.exit("차전 순서 이상 " + gid)
    home = int(inf["home_id"] == g["club_id"])
    if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    fu = ft = 0
    if leg == 2:
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("UEFA", "UI", "UEQ"): return [leg, home, fu, ft, 1, 1]   # UEFA 대회 2021 전: 원정 다득점·연장
    if cid == "UKRP": return [leg, home, fu, ft, 1, 1]
    sys.exit("합산 규칙 없음 " + cid)

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
def key(n):
    k = norm(n)
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
    y, m = int(d[:4]), int(d[5:7]); s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# ---------------------------------------------------------------- 리그 모형
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
def half_up(x): return int(x + 0.5)
SD2 = 51.24

# 분데스리가 순위값(기존 자료 1998-99~2006-07 고정값, 2007-08은 기존 자료 값)
BL = [2006, 1912, 1860, 1828, 1812, 1797, 1777, 1756, 1737, 1723, 1713, 1702, 1697, 1682, 1661, 1644, 1634, 1613]
BL0708 = {2: 1847, 3: 1795, 4: 1762, 5: 1746, 6: 1732, 7: 1712, 8: 1691, 9: 1672, 10: 1658, 11: 1647, 12: 1636, 13: 1632, 14: 1616, 15: 1595, 16: 1579, 17: 1569}
# 2. 분데스리가 순위값(기존 자료의 순위별 값)
L2 = {1: 1697, 2: 1667, 3: 1636, 4: 1622, 5: 1615, 6: 1609, 7: 1600, 8: 1592, 9: 1584, 10: 1579, 11: 1574, 12: 1570, 13: 1568, 14: 1561, 15: 1544, 16: 1545, 17: 1541, 18: 1532}

# 브라질 세리에 A 공식 최종 순위(en/pt.wikipedia 시즌 문서 'Final standings'/'Classificação geral'; TM 표는 1단계 순서라 쓰지 않음)
BRA_RANK = {
    "1995": (24, {"Sociedade Esportiva Palmeiras": 5, "Guarani Futebol Clube (SP)": 18}),
    "1996": (24, {"CR Flamengo": 13, "Fluminense Football Club": 23, "São Paulo Futebol Clube": 11, "Goiás EC": 4,
                  "Botafogo de Futebol e Regatas": 17, "Clube de Regatas Vasco da Gama": 18}),
    "1997": (26, {"Criciúma EC": 24, "Sport Club Corinthians Paulista": 17, "CA Bragantino": 22,
                  "Esporte Clube Vitória": 9, "Goiás EC": 19, "América de Natal": 16, "Sport Club do Recife": 11}),
}
BRA_NAME = {"América FC": "아메리카(RN)"}

# 멕시코 1부 1997-98 누적 순위(인비에르노 1997 + 베라노 1998 TM 조별 표 합산, 승점→득실차→다득점; 카모라네시 선례)
MX_MEAN, MX_SD = 1604.25, 73.41
MX_NAME = {"León": "Club León FC", "Puebla FC": "Puebla FC", "Toros Neza": "Toros Neza FC", "Morelia": "Club Atlético Morelia",
           "América": "CF América"}
def mex_cum():
    acc = collections.defaultdict(lambda: [0, 0, 0, 0])
    for fn in [os.path.join(HERE, "extra", "tm_MEXA_1997.html"), os.path.join(RAW, "tables", "tm_MEX1_1997.html")]:
        s = open(fn, encoding="utf-8").read()
        n = 0
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
            t = [html.unescape(re.sub("<[^>]+>", "", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
            if len(t) >= 10 and re.match(r"^\d+:\d+$", t[7]):
                gf, ga = map(int, t[7].split(":"))
                a = acc[t[2]]; a[0] += int(t[9]); a[1] += gf - ga; a[2] += gf; a[3] += int(t[3]); n += 1
        if n != 18: sys.exit("멕시코 표 이상 " + fn)
    if len(acc) != 18 or any(v[3] != 34 for v in acc.values()): sys.exit("멕시코 누적 이상")
    order = sorted(acc, key=lambda k: (-acc[k][0], -acc[k][1], -acc[k][2]))
    return {MX_NAME.get(k, k): (i + 1, acc[k]) for i, k in enumerate(order)}
MEX9798 = mex_cum()

# 쉬페르리그: 튀르키예 회귀(평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 흩어짐 119; 아르다 투란 build 방식)
TR_COEF = {1999: 7.750, 2000: 7.750, 2001: 5.625}   # kassiesa.net 국가 시즌 계수
EX_TR = collections.defaultdict(dict)
for x in ENTS:
    m = re.match(r"쉬페르리그 (\d{4}-\d\d) (\d+)위$", x["lv"])
    if m: EX_TR[m.group(1)][int(m.group(2))] = x["elo"]
def tr_mean(season):
    if 1 in EX_TR.get(season, {}): return EX_TR[season][1] - 119 * curve(1, 18)
    s = int(season[:4]); c = sum(TR_COEF[y] for y in (s - 1, s, s + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)
def tr_model(season, r, n=18):
    t = EX_TR.get(season, {})
    if r in t: return t[r], f"쉬페르리그 {season} {r}위"
    lo = [k for k in t if k < r]; hi = [k for k in t if k > r]
    if lo and hi:
        a, b = max(lo), min(hi)
        return round(t[a] + (t[b] - t[a]) * (r - a) / (b - a)), f"쉬페르리그 {season} {r}위 (추정, 다른 선수 자료 {a}위 {t[a]}·{b}위 {t[b]} 사이)"
    return round(tr_mean(season) + 119 * curve(r, n)), f"쉬페르리그 {season} {r}위 (추정, 튀르키예 리그 수준 회귀)"

# 우크라이나 1부: 셰브첸코 build 회귀 + 보정 −73(문서 4절), 계수는 kassiesa.net
UA_COEF = {2001: 3.625, 2002: 4.250, 2003: 4.875, 2006: 6.500, 2007: 4.875, 2008: 16.625}
def ua_model(season, r, n=16):
    s = int(season[:4]); c = sum(UA_COEF[y] for y in (s - 1, s, s + 1)) / 3
    return round(1473 + 23.33 * (c - 7.3333) - 73 + 119 * curve(r, n)), f"우크라이나 1부 {season} {r}위 (추정)"
# 오스트리아 분데스리가: 같은 회귀(흩어짐 119), 2008-09 계수 2007 3.200·2008 2.250·2009 9.375(kassiesa.net)
def at_model(season, r, n=10):
    c = (3.200 + 2.250 + 9.375) / 3
    return round(1473 + 23.33 * (c - 7.3333) + 119 * curve(r, n)), f"오스트리아 분데스리가 {season} {r}위 (추정, 리그 수준 회귀)"
# 스위스 슈퍼리그 순위별 값(다른 선수 자료 값: 1·2위 1600, 3위 1520, 4~10위 2012-13 슈퍼리그 순위값; 엘베르 선례)
CH = {1: 1600, 2: 1600, 3: 1520, 4: 1507, 5: 1461, 6: 1430, 7: 1406, 8: 1382, 9: 1342, 10: 1306}
# 중국 슈퍼리그: 2012 모형(평균 1484, 흩어짐 63, 문서 4절)을 2009에 적용(추정)
def cn_model(season, r, n=16):
    return half_up(1484 + 63 * curve(r, n)), f"중국 슈퍼리그 {season} {r}위 (추정, 2012 리그 수준 사용)"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] in ("league",) or p[0].startswith("#"): continue
        RANKS[(p[0], p[1])][p[4]] = (int(p[2]), int(p[3]))

def model(cid, d, opp):
    eu = season_eu(d); y = d[:4]
    if cid == "BRA1":
        n, t = BRA_RANK[y]
        if opp in t:
            r = t[opp]; return half_up(1598 + 63 * curve(r, n)), f"브라질 세리에 A {y} {r}위"
    if cid == "MEX1" and opp in MEX9798:
        r = MEX9798[opp][0]
        return half_up(MX_MEAN + MX_SD * curve(r, 18)), f"멕시코 1부 1997-98 누적 {r}위 (추정, 인비에르노·베라노 조별 순위표를 합친 승점 순위에 리가MX 모형)"
    for lg in ("L1", "L2", "TR1", "C1", "A1", "UKR1", "CSL"):
        s = y if lg == "CSL" else eu
        t = RANKS.get((lg, s), {})
        if opp not in t: continue
        r, n = t[opp]
        if lg == "L1":
            if eu == "2007-08": return BL0708[r], f"분데스리가 {eu} {r}위"
            return BL[r - 1], f"분데스리가 {eu} {r}위"
        if lg == "L2": return L2[r], f"2. 분데스리가 {eu} {r}위"
        if lg == "TR1": return tr_model(eu, r, n)
        if lg == "C1": return CH[r], f"스위스 슈퍼리그 {eu} {r}위 (추정, 다른 선수 자료의 스위스 {r}위 값과 같음)"
        if lg == "A1": return at_model(eu, r, n)
        if lg == "UKR1": return ua_model(eu, r, n)
        if lg == "CSL": return cn_model(s, r, n)
    return None

# 직접 추정(모두 lv에 '추정') — judgments.md 6절
MAN = {
    ("FC Slovan Liberec", "2004-05"): (1457, "체코 2004-05 5위 (추정, 다른 선수 자료 체코 2004-05 1위 1520·7위 1425 사이 직선)"),
    ("Ferencvárosi TC", "2004-05"): (1440, "헝가리 2004-05 2위 (추정, 다른 선수 자료 헝가리 1위 1450·3위 1430 사이)"),
    ("KAA Gent", "2001-02"): (1571, "벨기에 1부 2001-02 4위 (추정, 다른 선수 자료 같은 시즌 3위 1597·5위 1545의 가운데)"),
    ("Metalurg Donetsk", "2002-03"): ua_model("2002-03", 3),
    ("Antalyaspor", "2000-01"): tr_model("2000-01", 15),
    ("FC Vaduz", "2005-06"): (1250, "스위스 2부(챌린지 리그) 2005-06 8위 (추정, 다른 선수 자료 스위스 2부 1250과 같음)"),
    ("VfB Lübeck", "2001-02"): (1450, "독일 3부(레기오날리가 북부) 2001-02 1위 (추정, 다른 선수 자료 독일 3부 레기오날리가 1450과 같음)"),
    ("KFC Uerdingen 05", "2001-02"): (1450, "독일 3부(레기오날리가 북부) 2001-02 5위 (추정, 다른 선수 자료 독일 3부 레기오날리가 1450과 같음)"),
    ("Ludwigsfelder FC", "2003-04"): (1180, "독일 5부(페어반츠리가 브란덴부르크) 2003-04 1위 (추정, 다른 선수 자료 독일 5부 1180과 같음)"),
}
MAN = {(key(k[0]), k[1]): v for k, v in MAN.items()}

ELO_SRC = collections.Counter(); ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)
CAL = {"BRA1", "CSL"}
def opp_elo(opp, d, cid):
    k = key(opp); eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    if cid in CAL: seasons = [d[:4]]
    elif cid in ("UEFA", "UI", "UEQ"): seasons = [eu, eu[:4], str(int(eu[:4]) + 1)]
    else: seasons = [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    res = model(cid, d, opp)
    if res:
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model", [])); return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g): return g["date_local_computed"]
# 이름 구분: Transfermarkt 'América FC'(1751)는 1997 세리에 A의 아메리카(RN, 나탈). 통합표 별칭이 멕시코 CF América로 묶으므로 이름을 바꿈
OPP_RENAME = {"América FC": "América de Natal"}
for g in GAMES: g["opponent"] = OPP_RENAME.get(g["opponent"].strip(), g["opponent"].strip())
M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])
for g in GAMES:
    if club_of(ldate(g)) != CLUB_KEY[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0
rows, judg = [], []; missing = set(); EXCL_CNT = collections.Counter()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None: missing.add((opp, season_eu(d), cid, d)); res = (0, "?")
    row = [typ, opp, res[0], comp, mi, gf, ga, ko, pk, d, 0, dm, res[1], note]
    if tie: row.append(tie)
    rows.append(row)
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    if e["ail_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", ldate(g), g["opponent"], e["minute"], e["assist_type"] or "유형 없음")); EXCL_CNT["본인 PK 골 본인 도움"] += 1
    isg, isa = e["ail_scorer"] == "1", e["ail_assist_other"] == "1"
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
    cid = g["competitionId"]; comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if e["own_goal"] == "1" or not ours: judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        if why:
            EXCL_CNT[why] += 1; judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= "2014-08-01": sys.exit("2014.8 이후 도움 " + gid)
        if not e["assist_type"]: EXCL_CNT["유형 없음(넣음)"] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)
if missing:
    for x in sorted(missing, key=lambda x: x[3]): print("Elo 없음:", x)
    sys.exit(1)
rows.sort(key=lambda r: (r[9], r[4], 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, EXCL_CNT)
    for x in ELO_LOG: print(x)
    for j in judg: print(j)
    print(sorted(MEX9798.items(), key=lambda x: x[1][0]))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
def load_all():
    out = {}
    for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
        b = os.path.basename(fn)
        if b in ("ail.js", "hon.js"): continue
        s = open(fn, encoding="utf-8").read()
        me = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S); mm = re.search(r"const (\w+)_M=(\[.*?\]);\n", s, re.S)
        if me and mm: out[b] = (json.loads(me.group(2)), json.loads(mm.group(2)))
    return out
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
OUR_NAMES = {"svwail": ["SV Werder Bremen", "Werder Bremen"], "s04ail": ["FC Schalke 04", "Schalke 04"], "besail": ["Beşiktaş JK", "Besiktas"],
             "hsvail": ["Hamburger SV"], "crvail": ["Red Star Belgrade", "Crvena Zvezda"], "gcail": ["Grasshopper Club Zurich"],
             "msvail": ["MSV Duisburg"], "metail": ["Metalurg Donetsk"], "altail": ["SCR Altach", "Altach"], "chqail": ["Chongqing Lifan"],
             "intail": ["Sport Club Internacional"], "guaail": ["Guarani Futebol Clube (SP)"], "tigail": ["Tigres UANL"]}
IS_AIL = lambda s: isinstance(s, str) and norm(s) == "ailton"
if __name__ == "__main__" and "--cross" in sys.argv:
    ALL = load_all()
    mdates = {m[0] for m in M}
    for fn, (ent, mm) in ALL.items():
        for r in E:   # 아일톤 도움 → 그 선수 골(같은 팀): 득점자 이름 대조는 행 단위
            for x in ent:
                if x[9] == r[9] and key(x[1]) == key(r[1]):
                    if r[0] == "a" and x[0] == "g" and abs(x[4] - r[4]) <= 2:
                        CROSS.append(("아일톤 도움↔" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, x) or "같음"))
                    if r[0] == "g" and x[0] == "a" and IS_AIL(x[13]) and abs(x[4] - r[4]) <= 2:
                        CROSS.append((fn + " 도움→아일톤 골", r[9], r[4], cmp_rows(r, x) or "같음"))
        for x in ent:
            if x[0] == "a" and IS_AIL(x[13]) and not any(r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append((fn + " 도움→아일톤 골인데 내 자료에 없음", x[9], x[4]))
        # 같은 경기(같은 날 같은 상대: 같은 팀 동료) — Elo·lv·대회
        for x in ent:
            if x[9] in mdates:
                for r in E:
                    if r[9] == x[9] and key(r[1]) == key(x[1]):
                        dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                        if dd: CROSS.append(("같은 경기 다름", fn, r[9], r[1], dd))
                        break
        # 같은 경기 상대편(그 선수 상대가 아일톤 팀): 날짜·골 순서
        for x in ent:
            for r in E:
                if r[9] == x[9] and key(x[1]) in {key(c) for c in OUR_NAMES.get(club_of(r[9]), [])}:
                    CROSS.append(("상대편 같은 경기", fn, r[9], r[0], r[4], f"{r[5]}-{r[6]}", "|", x[0], x[4], f"{x[5]}-{x[6]}", x[3], r[3]))
                    break
        for x in mm:
            for m in M:
                if m[0] == x[0] and key(m[1]) == key(x[1]) and m[2] != x[2]:
                    CROSS.append(("같은 경기 대회 코드 다름(출전)", fn, m[0], m[1], m[2], x[2]))
            for m in M:   # 상대편 출전 행
                if m[0] == x[0] and key(x[1]) in {key(c) for c in OUR_NAMES.get(club_of(m[0]), [])} and m[2] != x[2]:
                    CROSS.append(("상대편 출전 대회 코드 다름", fn, m[0], m[1], m[2], x[2]))
    for c in CROSS: print(c)

# ---------------------------------------------------------------- 클럽별 합계
CLUB_KO = {k: n for k, u, n, s, y in CLUBS}
CLUB_Y = {k: y for k, u, n, s, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E); MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
def exc(cid):
    gs = [g for g in EXCLUDED if g["club_id"] == cid]
    return len(gs), sum(int(g["goals"]) for g in gs), sum(int(g["assists"]) for g in gs), min(g["date_local_computed"] for g in gs), max(g["date_local_computed"] for g in gs)
EU, EO = exc("95"), exc("115")
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["ail_assist_other"] == "1")
N_BLANK = EXCL_CNT["유형 없음(넣음)"]
SRC = ELO_SRC
NOTE_LINES = [
    f"아일톤(인테르나시오나우·과라니·티그레스 UANL·베르더 브레멘·샬케 04·베식타시·함부르크 SV·츠르베나 즈베즈다·그라스호퍼·MSV 뒤스부르크·메탈루르흐 도네츠크·SCR 알타흐·충칭 리판)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 바이아전 ~ {d_(M[-1][0])} 장쑤 순톈전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·프로 리그가 아닌 팀-시즌(아래 줄)·경기별 자료가 없는 클럽 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분("
    + ", ".join(f"{CLUB_KO[k]} {v[3]:,}분" for k, v in ST.items()) + ")",
    f"뺀 기록: KFC 위르딩겐 05(2009-10, 오버리가 니더라인 = 독일 5부 아마추어) {EU[0]}경기 {EU[1]}골 {EU[2]}도움({d_(EU[3])}~{d_(EU[4])}), FC 오버노일란트(2010-11, 레기오날리가 노르트 = 독일 4부) {EO[0]}경기 {EO[1]}골 {EO[2]}도움({d_(EO[3])} DFB-포칼 프라이부르크전 포함, ~{d_(EO[4])})은 팀이 공식 프로 리그에 있지 않던 시즌이라 넣지 않음(사용자 기준). 위르딩겐은 위키백과 13경기 4골로 Transfermarkt(10경기 3골)보다 많음",
    "경기별 자료가 없어 넣지 않은 클럽(Transfermarkt에 출전 경기가 없고 위키백과 합계만 있음): 이피랑가(1993~94, 위키백과 12경기 2골·포르투갈어판 39경기 18골), 모지 미링(1994~95 임대, 28경기 8골), 산타크루스(1995~96, 위키백과 21경기 7골 — Transfermarkt 이적 기록은 같은 시기를 스포르트 헤시피로 적음), 캄피넨시(2009, 1경기 1골), 히우 브랑쿠(2011 상파울루 주 2부, 2~4경기 1골), 하시아 빙겐(2012~13 아마추어, 21경기 19골), TSV 바숨 3군(2023, 독일어판 1경기 1골)",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 나온 경기와 리그 밖 경기 전부). FotMob에는 이 선수 자료가 없어(검색 결과 없음, 2010년 이전 경기도 없음) Transfermarkt가 경기별 유일한 출처이고, 경기 수·골은 영어·독일어·포르투갈어 위키백과 클럽·시즌별 기록과 대조함. 출전 분이 없어 90분으로 추정한 경기는 없음",
    "출처 간 차이: 브레멘 214경기 106골·샬케 44·20·베식타시 18·7·함부르크 13·3·그라스호퍼 14·8·뒤스부르크 8·1·알타흐 12·7·충칭 5·0은 영어 위키백과와 같음. 과라니는 위키백과 43경기 20골(1996 13골)로 Transfermarkt 19골(1996 12골)보다 1골 많으나 경기별 근거가 없어 Transfermarkt를 따름. 티그레스는 위키백과 16경기 5골(1998 베라노만)이고 Transfermarkt는 인비에르노 1998 6경기를 더해 22경기 5골. 츠르베나 즈베즈다는 위키백과 13경기 4골(리그 11경기 3골)이나 Transfermarkt에는 3경기 1골(리그 1·UEFA컵 2)만 있어 나머지 10경기 3골은 넣지 못함. 메탈루르흐는 Transfermarkt에 우크라이나컵 준결승 1차전(13분)이 더 있음(위키백과 2경기 1골). 인테르나시오나우 1995(19경기 3골)는 Transfermarkt 이적 기록(1995.7.1 스포르트 헤시피 이적)과 맞지 않지만 경기 리포트가 있는 인테르나시오나우 경기라 넣음(위키백과는 인테르나시오나우 21경기 4골)",
    "골: 상대 자책골 없음. PK 골은 Transfermarkt 골 유형 'Penalty' 기준. 승부차기 골은 셈하지 않고, 골 뒤 스코어는 연장까지의 실제 점수(1999.10.12 카이저슬라우테른전·2001.11.27 위르딩겐전·2005.4.19 브레멘전). 2005.4.19 브레멘전(DFB-포칼 준결승) 96분 골은 연장 골",
    f"도움: 모두 2014년 8월 전이라 Transfermarkt 리포트 도움 기준(다른 출처 없음). 도움 {NA} = Transfermarkt {N_TM_A}(오버노일란트 3개 제외) − PK 유도 {EXCL_CNT['PK 유도']}(2001.8.18 1860 뮌헨전 헤어초크, 2005.5.28 DFB-포칼 결승 바이에른전 링컨) − 'Shot on goal'(슈팅 리바운드) {EXCL_CNT[chr(39) + 'Shot on goal' + chr(39) + '(슈팅 리바운드)']}(2005.3.5 보훔전 링컨). 본인 PK 골에 본인이 도움으로 적힌 3개(2000.12.17 코트부스전, 2003.8.30 루트비히스펠데전, 2004.2.15 카이저슬라우테른전)는 처음부터 도움으로 세지 않음. 넣은 도움 중 {N_BLANK}개(대부분 1999~2002)는 Transfermarkt에 도움 유형이 비어 있어 PK 유도·리바운드 여부를 확인할 수 없음(일반 도움으로 넣음 — 다른 선수 선례). 1990년대 브라질·멕시코 경기는 Transfermarkt에 도움 기록이 없어 도움이 실제보다 적을 수 있음",
    "날짜는 현지 날짜(브라질·멕시코·중국은 Transfermarkt 시각을 현지 시간으로 바꿈, 유럽은 Transfermarkt 리포트 날짜)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(피사로·알틴톱 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위를 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 직접 추정 {SRC['직접 추정']}, 순위표+모형 {SRC['순위표+리그 모형']})",
    "리그 모형: 분데스리가·2. 분데스리가는 다른 선수 자료의 순위값. 브라질 세리에 A 1995~1997은 공식 최종 순위(영어·포르투갈어 위키백과; Transfermarkt 표는 1단계 순서라 쓰지 않음)를 평균 1598 모형에 넣음(1996 결승 단계 8강 고이아스전 두 경기는 Transfermarkt가 리그 라운드로 적어 리그로 계산). 멕시코 1부 1997-98은 Transfermarkt 인비에르노 1997·베라노 1998 조별 표를 합친 승점 순위(공식 통합표 아님)를 리가MX 모형에 넣은 추정(레온 8위·푸에블라 16위·토로스 네사 10위·모렐리아 7위·아메리카 2위)",
    "직접·모형 추정(모두 '추정'): 쉬페르리그 2005-06 겐칠레르비를리이 6위 1528·카이세리 에르지예스스포르 10위 1406(다른 선수 자료 같은 시즌 1위·13위 값 사이 직선), 삼순스포르 17위 1243·안탈리아스포르 2000-01 15위 1359(튀르키예 리그 수준 회귀), 스위스 슈퍼리그 2006-07(장크트갈렌 5위 1461·루체른 8위 1382·아라우 9위 1342·샤프하우젠 10위 1306, 다른 선수 자료 스위스 순위별 값), 오스트리아 분데스리가 2008-09(잘츠부르크 1위 1717·라피트 2위 1551·LASK 7위 1358·카펜베르크 8위 1329·마터스부르크 9위 1290, UEFA 국가 계수 회귀), 우크라이나 1부(메탈루르흐 도네츠크 2002-03 3위 1445·나프토비크 2007-08 15위 1310, 국가 계수 회귀), 중국 슈퍼리그 2009(베이징 궈안 1위 1643·칭다오 13위 1433, 2012 리그 수준), 헨트 2001-02 1571, 슬로반 리베레츠 2004-05 1457, 페렌츠바로시 2004-05 1440, 파두츠 2005-06(스위스 2부) 1250, 뤼베크 2001-02·위르딩겐 2001-02(독일 3부) 1450, 루트비히스펠데 2003-04(독일 5부) 1180",
    "대회 비중: DFB-포칼·스위스컵·우크라이나컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), DFB-리가포칼은 첫 경기·준결승·결승을 국내컵 8강·준결승·결승으로 계산함. 인터토토컵·UEFA컵 예선·UEFA컵 1라운드는 유로파 예선, UEFA컵 2·3라운드·16강·8강·32강은 유로파 토너먼트, UEFA컵 조별은 유로파 조별로 계산함",
    f"두 경기 합산(UEFA 대회) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음). 아일톤이 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 인테르나시오나우·과라니·충칭은 달력 연도, 브레멘·샬케는 7월 10일 기준(7월 리가포칼·인터토토컵·2001.7.28 리그 개막전이 새 시즌), 나머지는 8월 1일 기준(티그레스 베라노 1998 = 1997-98, 인비에르노 1998 = 1998-99). 클럽 구분은 1996.7.1 전 인테르나시오나우, 1998.1.1 전 과라니, 1998.10.15 전 티그레스, 2004.7.1 전 브레멘, 2005.7.21 전 샬케, 2006.1.24 전 베식타시, 2006.8.31 전 함부르크(임대), 2007.2.14 전 츠르베나 즈베즈다, 2007.7.1 전 그라스호퍼(임대), 2008.2.25 전 뒤스부르크, 2008.8.31 전 메탈루르흐, 2009.1.1 전 알타흐(임대), 이후 충칭",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 분데스리가 2003-04(브레멘), 세르비아 리그 2006-07(츠르베나 즈베즈다, 리그 출전 1경기 — Transfermarkt 그대로), DFB-포칼 2회(2003-04, 1998-99 — 1998-99 결승은 명단에만 들고 출전 안 함), 준우승 DFB-포칼 2회(2004-05 샬케·1999-00 브레멘, 둘 다 결승 출전), 인터토토컵 2004(샬케), 독일 올해의 선수 2004, 득점왕 2003-04 분데스리가 28골·DFB-포칼 6골. 분데스리가 준우승 2004-05는 뺌",
    "은퇴. 프로 리그 마지막 경기 2009.9.27 장쑤 순톈전(충칭)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM "]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []; seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6], r[13])
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
mmap = {m[0]: m for m in M}
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    m = mmap[r[9]]
    if key(m[1]) != key(r[1]) or m[2] != r[3]: problems.append(("상대/대회 M 불일치", r[9], m, r[1], r[3]))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const AIL_E={J(E)};\nconst AIL_M={J(M)};\nconst AIL_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg,
               "excluded": [[g["club"], g["date_local_computed"], g["opponent"], g["competitionId"], g["playedMinutes"], g["goals"], g["assists"]] for g in EXCLUDED],
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG, "club_totals": ST},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}/{NTIEG} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
