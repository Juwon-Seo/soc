#!/usr/bin/env python3
"""Andriy Shevchenko: raw/ -> shevchenko.json + src/data/she.js (판정 근거는 judgments.md)

  python3 players/shevchenko/build_shevchenko.py            # 파일 쓰기
  python3 players/shevchenko/build_shevchenko.py --debug    # Elo 출처 목록
  python3 players/shevchenko/build_shevchenko.py --fm       # FotMob 골 대조
  python3 players/shevchenko/build_shevchenko.py --cross    # 동료(카카·드록바·램파드·로번·발라크·호나우지뉴) 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/{kak,dro,lam,rob,blk,rdg}.js.
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "she.js")
OUT_JSON = os.path.join(HERE, "shevchenko.json")
ME = "안드리 셰브첸코"
SHEV = "Andriy Shevchenko"

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
EXCL_G = {}

# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    # PK 유도
    "1021492|81": "PK 유도(포흘레바예프 PK)",
    "3794605|51": "PK 유도(포흘레바예프 PK)",
    "3799041|30": "PK 유도(레브로프 PK)",
    "3851727|16": "PK 유도(레브로프 PK)",
    "3763261|27": "PK 유도(상대 핸드볼, 'Handball by Andriy Shevchenko' — 레브로프 PK)",
    "66775|51": "PK 유도(램파드 PK)",
    "1072380|24": "PK 유도(구세우 PK)",
    # 슈팅 리바운드
    "3798074|23": "슈팅 리바운드(Shot on goal, 카르다시)",
    "3426370|71": "슈팅 리바운드(Shot on goal, 벵글린스키)",
    "3763261|42": "슈팅 리바운드(Shot on goal, 레브로프)",
    "16|67": "슈팅 리바운드(Shot on goal, 인자기)",
    "53424|88": "슈팅 리바운드(Shot on goal, 인자기)",
    "923760|45+1": "슈팅 리바운드(Shot on goal, 얀쿨로프스키 굴절 슛)",
    "960839|70": "슈팅 리바운드(Shot on goal, 부코예비치)",
    "960890|62": "슈팅 리바운드(Shot on goal, 마그랑)",
    # 상대 자책골
    "3099787|88": "상대 자책골(스파르타 가브리엘, 유형 Shot on goal)",
}

# 몰수 경기: 경기 중 스코어로 계산(드록바 2013.9.22 베식타시, 카카 같은 경기 선례)
FORFEIT = {"31091": "2005.4.12 챔스 8강 2차전 인테르-밀란: 셰브첸코 30분 골 뒤 0-1에서 관중 난입(홍염)으로 중단, UEFA가 0-3 밀란 승으로 정함"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"UKR1", "IT1", "GB1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("UKRP", "CIT", "FAC", "CGB"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        if cid == "FAC" and (r.startswith("sixth") or r.startswith("6th")): return "dk"   # FA컵 6라운드 = 8강(재경기 포함)
        return "dc"
    if cid in ("SCI", "USC", "GBCS"): return "df"
    if cid == "WEPO": return "cwc"
    if cid == "CLQ": return "clq"   # 예선 3라운드·플레이오프('Qualifying Round')
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 1999-2003 2차 조별(Group 2·3)도 조별
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # UEFA컵 2·3라운드·16강, 유로파 32강(Second Round)·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    # 원정 다득점·연장: UEFA 대회(2020-21까지), 코파 이탈리아(2021-22까지), 잉글랜드 리그컵 준결승(2017-18까지),
    # 우크라이나컵 두 경기 라운드(1990년대, 원정 다득점·연장 있는 것으로 둠 — 추정)
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
    "tavriya simferopol": "sc tavriya simferopol", "zorya mals lugansk": "zorya lugansk",
    "zirka nibas kirovograd": "zirka kirovograd", "cska borysfen kyiv": "cska kyiv",
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

# 표준 순위 곡선(세리에A 20팀 기존 값을 표준화, 다른 선수 자료와 같음)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24   # 2부 흩어짐(세리에B·튀르키예 2부 선례)

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

# 세리에A 18팀(1988-89~2003-04): 기존 자료의 순위값, 7·9·12·16위는 앞뒤 값의 가운데(토티·델 피에로 자료와 같음)
SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 7: 1762, 8: 1743, 9: 1728, 10: 1713, 11: 1704, 12: 1697, 13: 1690, 14: 1676, 15: 1657, 16: 1645, 17: 1633, 18: 1614}

# 우크라이나 1부: 튀르키예·오스트리아·벨기에·스위스·스웨덴과 같은 회귀(리그 평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333)),
# 흩어짐 119. 계수(시즌 시작 연도, kassiesa.net 국가별 시즌 계수: 1993-94는 옛 방식(method1), 1994-95~1999-00은 method2, 2008-09 이후 method4)
UA_COEF = {1993: 3.333, 1994: 2.500, 1995: 3.333, 1996: 1.500, 1997: 5.625, 1998: 7.333, 1999: 5.375,
           2008: 16.625, 2009: 5.800, 2010: 10.083, 2011: 7.750, 2012: 9.500}
def ua_reg(start):
    c = sum(UA_COEF[y] for y in (start - 1, start, start + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)
# 보정 K: 셰브첸코 2기(2009-10~2011-12) 시즌에 이미 다른 선수 자료가 쓴 우크라이나 팀 값(순위표 순위 확인)과 회귀 모형 값의 평균 차
UA_CAL = []
for (k, s), vals in list(TABLE.items()):
    if s in ("2009-10", "2010-11", "2011-12"):
        t = RANKS.get(("UKR1", s))
        if t and k in t:
            r, n = t[k]
            (e, _), _ = collections.Counter(vals).most_common(1)[0]
            UA_CAL.append((k, s, r, e, round(ua_reg(int(s[:4])) + 119 * curve(r, n))))
UA_K = round(sum(e - m for *_, e, m in UA_CAL) / len(UA_CAL))
def ua_mean(start): return ua_reg(start) + UA_K

def model(lg, season, r, n):
    """(Elo, lv) — 순위표 + 리그 모형"""
    st = int(season[:4])
    if lg == "UKR1":
        return int(round(ua_mean(st) + 119 * curve(r, n))), f"우크라이나 1부 {season} {r}위 (추정)"
    if lg == "UKR2":
        return int(round(ua_mean(st) - 162 + SD2 * curve(r, n))), f"우크라이나 2부 {season} {r}위/{n}팀 (추정)"
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        if n == 18: return SA18[r], f"세리에A {season} {r}위"
        assert n == 20, (season, n)
        return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "GB1":
        m = ents_map("프리미어리그", season)
        if r in m: return m[r], f"프리미어리그 {season} {r}위"
        lo = [k for k in m if k < r]; hi = [k for k in m if k > r]
        if lo and hi:   # 앞뒤 순위 값의 가운데(직선 보간)
            a, b = max(lo), min(hi)
            return int(round(m[a] + (m[b] - m[a]) * (r - a) / (b - a))), f"프리미어리그 {season} {r}위"
        return None
    for lg2, lab in (("L1", "분데스리가"), ("ES1", "라리가"), ("FR1", "리그1"), ("NL1", "에레디비시"), ("PO1", "포르투갈 1부")):
        if lg == lg2:
            m = ents_map(lab, season)
            if r in m: return m[r], f"{lab} {season} {r}위"
            # 같은 리그 다른 시즌의 같은 순위 값(기존 자료에서 시즌 간 같은 값을 쓰는 리그)
            vals = collections.Counter()
            for e in ENTS:
                mm = re.match("^" + re.escape(lab) + r" (\d{4}-\d\d) (\d+)위$", e["lv"] or "")
                if mm and int(mm.group(2)) == r: vals[e["elo"]] += 1
            if vals:
                return vals.most_common(1)[0][0], f"{lab} {season} {r}위"
            return None
    return None

RANK_LG = ["UKR1", "UKR2", "IT1", "GB1", "L1", "ES1", "FR1", "NL1", "PO1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {
    (key("Aalborg BK"), "1995-96"): (1480, "덴마크 1995-96 4위 (추정, 다른 선수 자료의 브뢴뷔 1995-96 1위 1520보다 낮게)"),
    (key("Bröndby IF"), "1997-98"): (1520, "덴마크 1997-98 1위 (추정, 다른 선수 자료의 브뢴뷔 1995-96 1위 1520과 같음)"),
    (key("Barry Town"), "1998-99"): (1200, "웨일스 1998-99 1위 (추정, 다른 선수 자료의 웨일스 1위 TNS 2004-05 1200과 같음)"),
    (key("Galatasaray"), "1999-00"): (1680, "튀르키예 1999-00 1위 (추정, 다른 선수 자료의 갈라타사라이 1998-99 1위 1680과 같음)"),
    (key("Galatasaray"), "2000-01"): (1660, "튀르키예 2000-01 2위 (추정, 다른 선수 자료의 갈라타사라이 1위 1680·6위 1620 사이)"),
    (key("Beşiktaş JK"), "2000-01"): (1620, "튀르키예 2000-01 4위 (추정, 다른 선수 자료의 갈라타사라이 2003-04 6위 1620과 같은 수준)"),
    (key("GNK Dinamo Zagreb"), "2000-01"): (1500, "크로아티아 상위권 (추정, 다른 선수 자료의 디나모 자그레브 1위 1500~1520 수준)"),
    (key("CSKA Sofia"), "2001-02"): (1450, "불가리아 2001-02 3위 (추정, 다른 선수 자료의 CSKA 소피아 2010-11 3위 1450과 같음)"),
    (key("BATE Borisov"), "2001"): (1450, "벨라루스 2001 상위권 (추정, 다른 선수 자료의 BATE 1위 1500~1520보다 낮게)"),
}
# 세리에B(문서 4절 평균·흩어짐, 델 피에로 자료와 같음): 순위는 위키백과 시즌 문서
SB_MEAN = 1577.78
SB_RANK = {(key("Atalanta BC"), "1999-00"): (3, 20)}
# 우크라이나 3부(드루하 리하): 같은 시즌 1부 평균 − 2단계(독일 1부−2부 평균 차 약 162 × 2, 튀르키예 3부 선례), 순위 없이 평균값
UA3 = {(key("Dynamo Kyiv III"), "1997-98"), (key("SK Odessa"), "1998-99")}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    # 1) 같은 경기 다른 선수 자료(날짜 ±1)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    euro = cid in ("CL", "CLQ", "EL", "UEFA", "WEPO", "USC")
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
    if (k, eu) in SB_RANK:
        r, n = SB_RANK[(k, eu)]
        m = ents_map("세리에B", eu)
        e = m[r] if r in m else int(round(SB_MEAN + SD2 * curve(r, n)))
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, e, f"세리에B {eu} {r}위", "model IT2"))
        return e, f"세리에B {eu} {r}위"
    if (k, eu) in UA3:
        e = int(round(ua_mean(int(eu[:4])) - 324)); lv = f"우크라이나 3부 {eu} (추정)"
        ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "ua3"))
        return e, lv
    # 4) 순위표 + 리그 모형
    for s in seasons:
        for lg in RANK_LG:
            t = RANKS.get((lg, s))
            if t and k in t:
                r, n = t[k]
                res = model(lg, s, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg))
                    return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_tm_report"] or g["date_local"]

# 상대 이름 바꿈: 'Dynamo-3 Kyiv'는 상대 Elo 통합표의 이름 정규화(한 자리 숫자 토큰을 버림)에서 1군 'Dynamo Kyiv'와 같은 팀이 되어 충돌함
OPP_RENAME = {"Dynamo-3 Kyiv": "Dynamo Kyiv III"}
for g in GAMES:
    g["opponent"] = OPP_RENAME.get(g["opponent"].strip(), g["opponent"].strip())

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

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

TM_A_TYPES = collections.Counter()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["shev_scorer"] == "1", e["shev_assist_other"] == "1", e["shev_self_assist"] == "1"
    if iss: judg.append(("본인 PK 골의 본인 도움(도움 아님)", ldate(g), e["minute"]))
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
    d = ldate(g); opp = g["opponent"].strip()
    et = 0
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        TM_A_TYPES[e["assist_type"]] += 1
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal") or e["assist_type"].startswith("Handball"):
            sys.exit("도움 유형 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print("UA_K", UA_K, UA_CAL)
    for s in range(1994, 1999): print(s, round(ua_reg(s)), round(ua_mean(s)))
    for s in range(2009, 2012): print(s, round(ua_reg(s)), round(ua_mean(s)))
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["shev_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
FM_SEEN = 0
for gid, evs in TMG.items():
    if gid not in FM_EV: continue
    fg = [r for r in FM_EV[gid] if r["shev_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if not fg and not any(r["scorer"] for r in FM_EV[gid]): continue
    FM_SEEN += len(evs)
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        if tpk != fpk or tm_min != fm_min:
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    print("FotMob과 대조한 골", FM_SEEN)
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
# 이름: (파일, 접두어, 함께 뛴 기간들)
MATES = {
    "Kaká": ("kak.js", "KAK", [("2003-08-01", "2006-07-01"), ("2008-08-23", "2009-07-01")]),
    "Didier Drogba": ("dro.js", "DRO", [("2006-07-01", "2008-08-23"), ("2009-07-01", "2009-08-29")]),
    "Frank Lampard": ("lam.js", "LAM", [("2006-07-01", "2008-08-23"), ("2009-07-01", "2009-08-29")]),
    "Arjen Robben": ("rob.js", "ROB", [("2006-07-01", "2007-08-01")]),
    "Michael Ballack": ("blk.js", "BLK", [("2006-07-01", "2008-08-23"), ("2009-07-01", "2009-08-29")]),
    "Ronaldinho": ("rdg.js", "RDG", [("2008-08-23", "2009-07-01")]),
}
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
def inper(d, pers): return any(lo <= d < hi for lo, hi in pers)
TMEV = [(e, ldate(G[e["gameId"]]), minute(e["minute"])[0]) for e in EVENTS if e["gameId"] in G]
for nm, (fn, P, pers) in MATES.items():
    ent = load_js(fn, P)
    # 1) 셰브첸코 도움 → 동료 골
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("셰브첸코 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    # 2) 동료 도움 → 셰브첸코 골 (TM 리포트의 도움 선수로 찾음: 로번 자료는 도움 행 끝 칸이 득점자 대신 도움 유형)
    for e, d, mi in TMEV:
        if e["shev_scorer"] == "1" and norm(e["assist_player"]) == norm(nm):
            mine = [r for r in E if r[0] == "g" and r[9] == d and r[4] == mi]
            hit = sorted([x for x in ent if x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 3], key=lambda x: abs(x[4] - mi))
            CROSS.append((nm + " 도움→셰브첸코 골", d, mi, e["assist_type"] or "-", "동료 파일에 없음" if not hit else (cmp_rows(mine[0], hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and "Shevchenko" in str(x[13]):
            if not any(e["shev_scorer"] == "1" and norm(e["assist_player"]) == norm(nm) and d == x[9] and abs(mi - x[4]) <= 3 for e, d, mi in TMEV):
                CROSS.append(("동료 파일의 셰브첸코 골 도움이 TM 리포트와 다름", nm, x[9], x[4]))
    # 3) TM 리포트에 셰브첸코 도움인 동료 골 중 이 자료에서 뺀 것
    for e, d, mi in TMEV:
        if e["shev_assist_other"] == "1" and norm(e["scorer"]) == norm(nm) and not any(r[0] == "a" and r[9] == d and r[4] == mi for r in E):
            has = any(x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 3 for x in ent)
            CROSS.append(("TM 셰브첸코 도움을 뺀 동료 골", nm, d, e["minute"], e["assist_type"], "동료 골 행 있음" if has else "동료 골 행 없음"))
    # 4) 같은 경기의 상대 Elo·lv·대회
    for x in ent:
        if not inper(x[9], pers): continue
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회"))]
                if dd: CROSS.append(("같은 경기 다름", nm, r[9], r[1], dd))
                break
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] + ("" if c[-1] != "같음" else " (같음)") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("dynsh", "1999-07-01", "디나모 키이우", "1994~1999"), ("acmsh", "2006-07-01", "AC 밀란", "1999~2006"),
         ("chesh", "2008-08-23", "첼시", "2006~2008"), ("acmsh", "2009-07-01", "AC 밀란", "2008~2009"),
         ("chesh", "2009-08-29", "첼시", "2009"), ("dynsh", None, "디나모 키이우", "2009~2012")]
TM_CLUB = {"338": "dynsh", "5": "acmsh", "631": "chesh"}
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
def stint_of(d):
    for i, (k, u, _, _) in enumerate(CLUBS):
        if u is None or d < u: return i
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((i, [0, 0, 0, 0]) for i in range(len(CLUBS)))
for m in M: ST[stint_of(m[0])][0] += 1; ST[stint_of(m[0])][3] += m[3]
for r in E: ST[stint_of(r[9])][1 if r[0] == "g" else 2] += 1
STK = collections.OrderedDict()
for i, v in ST.items():
    k = CLUBS[i][0]; STK.setdefault(k, [0, 0, 0, 0])
    for j in range(4): STK[k][j] += v[j]
def season_of(d, k):   # 계산기 시즌 구분(디나모 키이우 7월 1일, 나머지 기본 8월 1일)
    y, m = int(d[:4]), int(d[5:7])
    s = (y if m >= 7 else y - 1) if k == "dynsh" else (y if m >= 8 else y - 1)
    return f"{s}-{str(s + 1)[2:]}"
SEASON_TM = collections.Counter()
for g in GAMES:
    SEASON_TM[(club_of(ldate(g)), season_of(ldate(g), club_of(ldate(g))), g["season_tm"])] += 1

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
PKD = [d_(r[9]) for r in E if r[0] == "g" and r[8]]
EX_PK = [x for x in judg if x[0] == "도움 제외" and x[5].startswith("PK")]
EX_SH = [x for x in judg if x[0] == "도움 제외" and x[5].startswith("슈팅")]
EX_OG = [x for x in judg if x[0] == "도움 제외" and x[5].startswith("상대 자책골")]
def ex_list(xs): return ", ".join(f"{d_(x[1])} {x[3]}분" for x in sorted(xs, key=lambda x: (x[1], minute(x[3])[0])))
NTMA = sum(TM_A_TYPES.values())
UNTYPED = sorted((ldate(G[e["gameId"]]), e["minute"]) for e in EVENTS if e["gameId"] in G and e["shev_assist_other"] == "1" and e["assist_type"] == "")
NAME = {"dynsh": "디나모 키이우", "acmsh": "AC 밀란", "chesh": "첼시"}
NOTE_LINES = [
    f"안드리 셰브첸코(디나모 키이우·AC 밀란·첼시)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 가조비크 코마르노전 ~ {d_(M[-1][0])} 타브리야 심페로폴전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·디나모 키이우 2군·우크라이나 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUBS[i][2]}({CLUBS[i][3]}) {c3(v)}" for i, v in ST.items())
    + f" (디나모 키이우 합계 {c3(STK['dynsh'])}, AC 밀란 합계 {c3(STK['acmsh'])}, 첼시 합계 {c3(STK['chesh'])}). 출전 분 합계 {MIN_TOT:,}분(디나모 키이우 {STK['dynsh'][3]:,}분, AC 밀란 {STK['acmsh'][3]:,}분, 첼시 {STK['chesh'][3]:,}분)",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 나온 경기와 리그 밖 경기 전부). 출전 분이 없어 90분으로 추정한 경기는 없음. 경기 수·골은 영어·우크라이나어 위키백과 클럽·시즌별 기록과 같음(디나모 키이우 249·124, 밀란 322·175, 첼시 77·22). 2010-11 이후 골은 FotMob 경기 이벤트와 대조함(FotMob은 그 전 경기 자료가 없고, 셰브첸코 도움은 어느 경기에도 적혀 있지 않음)",
    "뺀 기록: 디나모 키이우 2군(디나모-2, 1992-93~1996-97 우크라이나 2부·우크라이나컵 56경기 21골)은 2군 경기라 넣지 않음. Transfermarkt가 1994년 8~11월 디나모 키이우 1군 경기 15개(리그 10·챔스 3·챔스 예선 2)에 '다른 팀으로 출전'(그때 2군 소속)으로 적은 것은 1군 출전으로 세지 않음",
    "시즌 표기: 영어 위키백과는 2003.12.14 인터콘티넨털컵(보카 주니어스전)을 2003-04에 넣고 Transfermarkt는 따로 2003 시즌으로 적음. 이 계산기는 경기 날짜로 2003-04에 셈. 밀란 임대(2008-09) 뒤 첼시로 돌아와 뛴 2009.8.18 1경기는 첼시 기록",
    f"골: Transfermarkt 리포트 골 {NGo}개를 모두 씀. PK 골 {NPK}개는 Transfermarkt 골 유형 'Penalty' 기준이고, PK가 막힌 뒤 리바운드로 넣은 골은 일반 골로 셈. 2010-11 이후 골 중 FotMob 이벤트가 있는 {FM_SEEN}개는 골 뒤 스코어·PK가 같고 분이 1~3분 다른 6개는 Transfermarkt 분을 씀. FotMob 자료가 '없음'으로 나오는 경기(2011년 유로파 베식타시·맨시티전, 리그 자포리자·아르세날 키이우·샤흐타르·마리우폴전, 우크라이나컵 아르세날 키이우전)는 Transfermarkt만 근거",
    "2005.4.12 챔스 8강 2차전 인테르전은 셰브첸코 30분 골(0-1, 카카 도움) 뒤 관중이 던진 홍염으로 중단돼 UEFA가 0-3 밀란 승으로 정한 경기. 골은 경기 중에 나온 것이라 넣고, 골 전 스코어는 경기 중 스코어 0-0(같은 경기 카카 자료와 같음)과 1차전 2-0 합산으로 계산함. 출전 분은 Transfermarkt대로 90분(카카 자료와 같음)",
    "승부차기: 2003.5.28 챔스 결승 유벤투스전(0-0, 셰브첸코가 마지막 키커로 성공해 우승), 2005.5.25 챔스 결승 리버풀전(3-3, 셰브첸코 실축), 1998.8.26 챔스 예선 스파르타 프라하전(셰브첸코 실축), 2003.8.3 수페르코파 이탈리아나 유벤투스전, 2003.12.14 인터콘티넨털컵 보카 주니어스전. Transfermarkt 최종 스코어에는 승부차기가 들어 있지만 승부차기 킥은 골·도움으로 세지 않고 골 뒤 스코어는 연장까지의 스코어로 셈",
    f"도움: 모두 2014.8.1 이전이라 Transfermarkt 경기 리포트 도움(단일 출처)을 씀. 도움 {NA} = 리포트에서 셰브첸코가 동료 골에 준 도움 {NTMA} − PK 유도 {len(EX_PK)}({ex_list(EX_PK)}) − 슈팅 리바운드('Shot on goal') {len(EX_SH)}({ex_list(EX_SH)}) − 상대 자책골에 준 도움 {len(EX_OG)}({ex_list(EX_OG)})",
    "1998.6.8 타브리야전 27분 레브로프 PK 골은 리포트 도움 칸에 셰브첸코가 유형 'Handball by Andriy Shevchenko'로 적힌 PK 골이라 PK 유도와 같이 보고 뺌(패스로 만든 골이 아님). 2000.3.24 유벤투스전 84분 셰브첸코 PK 골에 본인 도움으로 적힌 것은 도움이 아님. Transfermarkt 선수 경기 성적의 도움 합계 100(디나모 키이우 41·밀란 46·첼시 13)과 리포트 101의 차이는 1998.6.8 경기(성적 1, 리포트 2: PK 유도와 슈팅 리바운드, 둘 다 뺌)",
    f"Transfermarkt 리포트에 도움 유형이 비어 있는 {len(UNTYPED)}개({', '.join(d_(d) + ' ' + m + '분' for d, m in UNTYPED)})는 일반 도움으로 셈. 2014.8.1 이전 도움은 다른 출처로 경기마다 대조하지 못함(FotMob 2010-12 경기 이벤트에도 셰브첸코 골·동료 골 어느 쪽에도 도움이 비어 있음)",
    "동료 자료 대조: 카카 도움 셰브첸코 골 16개·셰브첸코 도움 카카 골 7개, 드록바 도움 3·드록바 골 도움 4, 램파드 도움 3·램파드 골 도움 2, 로번 도움 2, 발라크 골 도움 1, 호나우지뉴 도움 1(2008.10.2 UEFA컵 취리히전)은 날짜·분·스코어·대회·상대 Elo·합산 정보가 다른 선수 자료와 모두 같음. 2007.1.6 맥클스필드전 51분 램파드 PK 골의 셰브첸코 도움(Transfermarkt 'Penalty: Fouled player')은 PK 유도라 뺌(램파드 자료의 골 행은 그대로)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표)를 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    f"우크라이나 1부(모두 '추정'): 튀르키예·오스트리아·벨기에·스위스 리그와 같은 회귀(리그 평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 흩어짐 119, 순위 곡선은 다른 리그와 같음)에 우크라이나 보정 {UA_K}점을 더함. 보정값은 2009-10~2011-12 시즌에 다른 선수 자료가 이미 쓴 우크라이나 팀 값 8개(샤흐타르·디나모 키이우·메탈리스트·카르파티·타브리야·보르스클라)와 회귀 값의 평균 차(우크라이나 계수가 두 클럽에 몰려 리그 평균이 계수보다 낮다고 봄). 보정 뒤 리그 평균: 1994-95 {round(ua_mean(1994))}, 1995-96 {round(ua_mean(1995))}, 1996-97 {round(ua_mean(1996))}, 1997-98 {round(ua_mean(1997))}, 1998-99 {round(ua_mean(1998))}, 2009-10 {round(ua_mean(2009))}, 2010-11 {round(ua_mean(2010))}, 2011-12 {round(ua_mean(2011))}(1997-98 1위 값 {round(ua_mean(1997) + 119 * curve(1, 16))}은 다른 선수 자료의 디나모 키이우 1997-98 1640과 거의 같음). 국가 계수는 kassiesa.net 시즌별 값(1993-94 3.333, 1994-95 2.5, 1995-96 3.333, 1996-97 1.5, 1997-98 5.625, 1998-99 7.333, 1999-00 5.375, 2008-09 16.625, 2009-10 5.8, 2010-11 10.083, 2011-12 7.75, 2012-13 9.5). 다른 선수 자료에 같은 팀·시즌 값이 있으면(샤흐타르 2009-10 1690·2010-11 1720, 메탈리스트 2010-11 1560, 타브리야 2010-11 1440, 보르스클라 2009-10 1440) 그 값을 씀. 근거 약함",
    f"우크라이나 3부(우크라이나컵 상대 디나모-3 키이우 1997-98(기록 표 이름 Dynamo Kyiv III)·SK 오데사 1998-99)는 같은 시즌 1부 평균에서 두 단계(독일 1부−2부 평균 차 약 162 × 2, 튀르키예 3부 선례) 내린 값({round(ua_mean(1997) - 324)}·{round(ua_mean(1998) - 324)}, 근거 약함)",
    "세리에A 18팀 시즌(1999-00~2003-04)은 다른 선수 자료의 18팀 순위값(1위 1969 ~ 18위 1614, 7·9·12·16위는 앞뒤 값의 가운데)을 쓰고, 세리에B 1999-00 아탈란타(코파 이탈리아 상대)는 3위(위키백과)로 평균 1578·2부 흩어짐 모형. 분데스리가·라리가·리그1·프리미어리그 1990년대 상대는 같은 시즌·같은 리그의 다른 선수 자료 순위값",
    "직접 추정(모두 '추정'): 올보르 1995-96 1480, 브뢴뷔 1997-98 1520, 배리 타운 1998-99 1200, 갈라타사라이 1999-00 1680·2000-01 1660, 베식타시 2000-01 1620, 디나모 자그레브 2000-01 1500, CSKA 소피아 2001-02 1450, BATE 2001 1450. 다른 선수 자료의 같은 팀·나라 값을 기준으로 둠",
    "대회 비중: 우크라이나컵·코파 이탈리아·FA컵·잉글랜드 리그컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중; FA컵 6라운드와 재경기는 8강, 코파 이탈리아 2003 두 경기 결승은 두 경기 모두 결승), 수페르코파 이탈리아나·UEFA 슈퍼컵·커뮤니티 실드는 국내컵 결승, 인터콘티넨털컵(2003)은 클럽 월드컵, 챔스 2차 조별(1999-00~2002-03)은 조별, 챔스 예선 3라운드·플레이오프는 챔스 예선, UEFA컵 1라운드는 유로파 예선, UEFA컵 2·3라운드·16강과 유로파 32강·16강·8강은 유로파 토너먼트, UEFA컵 2008-09 조별은 유로파 조별로 계산함",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(UEFA 대회·코파 이탈리아·잉글랜드 리그컵 준결승은 원정 다득점·연장 있음). 1990년대 우크라이나컵 두 경기 라운드도 원정 다득점·연장이 있는 것으로 둠(추정). 셰브첸코가 뛰지 않은 1차전 스코어는 Transfermarkt 경기 리포트로 채움: 1998.11.8 SK 오데사 원정 4-2(우크라이나컵 16강), 2007.1.10 위컴 원정 1-1(리그컵 준결승)",
    "시즌 구분: 디나모 키이우는 7월 1일 기준(우크라이나 리그가 7월 초에 개막: 1998.7.7 카르파티전·2010.7.9 오볼론전이 새 시즌, 1998.6.12 경기는 1997-98; Transfermarkt 시즌 표기와 모두 같음), 밀란·첼시는 기본 8월 1일(1999.8.21·2004.8.21 수페르코파와 2006.8.13 커뮤니티 실드는 새 시즌). 클럽 구분은 1999.7.1 전 디나모 키이우, 2006.7.1 전 밀란, 2008.8.23 전 첼시, 2009.7.1 전 밀란(임대), 2009.8.29 전 첼시, 이후 디나모 키이우",
]
NOTE_LINES.append("수상 기록은 Transfermarkt 업적 페이지 기준: 챔스 2002-03, 세리에A 2003-04, 코파 이탈리아 2002-03, 수페르코파 이탈리아나 2004, UEFA 슈퍼컵 2003, FA컵·리그컵 2007, 우크라이나 리그 5회(1994-95~1998-99), 우크라이나컵 3회(1995-96·1997-98·1998-99). 준우승은 챔스 결승 2회(2004-05·2007-08)와 인터콘티넨털컵 2003만 넣음. 개인: 발롱도르 2004, 우크라이나 올해의 선수 6회, 세리에A 외국인 최우수 선수 2000, 득점왕(세리에A 1999-00·2003-04 24골, 챔스 1998-99 8골·2000-01 9골·2005-06 9골, 우크라이나 1부 1998-99 18골, 우크라이나컵 1997-98 8골·1994-95 6골 — 1994-95 우크라이나컵 6골은 2군 경기 5골을 포함한 Transfermarkt 값이라 이 계산기 기록(1골)과 다름). 월드컵 예선 득점왕·대표팀 기록은 뺌")
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "UA_K"]:
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
    if r[0] == "g" and r[13] != 0: problems.append(("골 note", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r))
    if len(r) > 14 and r[7]: problems.append(("합산인데 단판", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const SHE_E={J(E)};\nconst SHE_M={J(M)};\nconst SHE_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG, "ua_calibration": UA_CAL,
               "season_vs_tm": [list(k) + [v] for k, v in sorted(SEASON_TM.items())]},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for i, v in ST.items(): print(" ", CLUBS[i][0], CLUBS[i][3], v)
