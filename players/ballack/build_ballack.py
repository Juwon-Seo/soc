#!/usr/bin/env python3
"""Michael Ballack - build script for the club SOC calculator.

Reads players/ballack/raw/ (Transfermarkt API + reports, FotMob events, ranks) and
writes players/ballack/ballack.json (final rows) and src/data/blk.js (BLK_E, BLK_M, BLK_NOTE).

Run: python3 players/ballack/build_ballack.py        (from the repo root or anywhere)

Scope: senior official first-team matches of Chemnitzer FC (2. Bundesliga 1995-96, Regionalliga Nordost 1996-97),
1. FC Kaiserslautern, Bayer Leverkusen (two spells), FC Bayern Munich, Chelsea. Excluded: 1. FC Kaiserslautern II and
Chemnitzer FC II (reserve teams), friendlies, national team. Rules: docs/HANDOFF-클럽SOC계산기.md 2-4, 6, 17 and the
Klose precedent (players/klose). All judgment calls are listed in players/ballack/judgments.md.
"""
import csv, json, os, re, unicodedata
from collections import Counter
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_JS = os.path.join(ROOT, "src", "data", "blk.js")
OUT_JSON = os.path.join(HERE, "ballack.json")
ME = "Michael Ballack"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

games_all = rd("tm_games.csv")
games = [g for g in games_all if g["level"] == "senior"]          # Kaiserslautern II (club 151) = reserve -> excluded
reserve = [g for g in games_all if g["level"] != "senior"]
events = rd("tm_events.csv")
meta = {r["gameId"]: r for r in rd("tm_match_info.csv")}
gbyid = {g["gameId"]: g for g in games}

# ---------------------------------------------------------------- dates (TM report date = local date)
def local_date(g):
    return g["date_local_tm_report"]       # 990077: API UTC 2000-09-19 22:00 = local 2000-09-20 (report date)

# ---------------------------------------------------------------- competition code
def rnd_of(g):
    return g["round"].lower()

def comp_code(g):
    c = g["competitionId"]; rnd = rnd_of(g); gid = g["gameId"]
    if c in ("L1", "L2", "RNO", "GB1"):
        return "lg"
    if c == "DFB":
        if rnd.startswith("final"): return "df"
        if "semi" in rnd: return "dsf"
        if "quarter" in rnd: return "dk"
        return "dc"                                  # first/second round, round of 16
    if c == "LPO":   # DFB-Ligapokal: first match ('intermediate stage', QF level) = dk, semi = dsf, final = df (Klose)
        if "semi" in rnd: return "dsf"
        if rnd.startswith("final"): return "df"
        return "dk"
    if c == "FAC":   # FA Cup: 3rd-5th round (+ replays) = dc, 6th round / QF (+ replay) = dk
        if rnd.startswith("final"): return "df"
        if "semi" in rnd: return "dsf"
        if "sixth" in rnd or "6th" in rnd or "quarter" in rnd: return "dk"
        return "dc"
    if c == "CGB":   # League Cup: 3rd round, round of 16 (4th) = dc, QF (5th) = dk, two-legged SF = dsf
        if rnd.startswith("final"): return "df"
        if "semi" in rnd: return "dsf"
        if "quarter" in rnd: return "dk"
        return "dc"
    if c == "GBCS": return "df"                     # Community Shield = domestic cup final
    if c == "CLQ": return "clq"
    if c == "CL":
        if "group" in rnd: return "clg"              # incl. 2001-02 second group stage (Group 4 / D)
        if "last 16" in rnd: return "cl16"
        if "quarter" in rnd: return "clk"
        if "semi" in rnd: return "clsf"
        if rnd.startswith("final"): return "clf"
        raise ValueError(("CL round", gid, rnd))
    if c == "ELQ": return "elq"
    if c in ("UEFA", "EL"):
        if "first round" in rnd: return "elq"
        if "group" in rnd: return "elg"
        if "semi" in rnd: return "elsf"
        if rnd.startswith("final"): return "elf"
        return "elk"   # UEFA Cup 3rd round 1999-2000, EL round of 32 ('Second Round') and last 16
    raise ValueError(("comp", gid, c))

TWO_LEG_COMPS = {"UEFA", "EL", "ELQ", "CL", "CLQ", "CGB"}   # FA Cup replays are single matches
def is_two_leg(g):
    return g["competitionId"] in TWO_LEG_COMPS and "leg" in rnd_of(g)

# ---------------------------------------------------------------- appearances
M = sorted([[local_date(g), g["opponent"], comp_code(g), int(g["playedMinutes"])] for g in games], key=lambda r: r[0])

def parse_min(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

# ---------------------------------------------------------------- goal / assist decisions
EXCL_TYPES = {"Penalty: Fouled player": "PK 유도", "Shot on goal": "슈팅 리바운드"}
# score sequence fixes (judgments.md 3): (gameId, minute, scorer) -> score after (home-away)
SCORE_FIX = {
    ("990077", "65", "Carsten Ramelow"): "1-1", ("990077", "72", "Thomas Brdaric"): "2-1",
    ("990077", "77", "Oliver Neuville"): "3-1", ("990077", "79", "Ricardo Sá Pinto"): "3-2",
    ("21622", "17", "Roy Makaay"): "0-1",
}

E, dropped_assists, dropped_goals, self_assists = [], [], [], []
for r in events:
    g = gbyid.get(r["gameId"])
    if not g:
        continue
    kg, ka, ks = r["ballack_scorer"] == "1", r["ballack_assist_other"] == "1", r["ballack_self_assist"] == "1"
    if not (kg or ka):
        continue
    gid = r["gameId"]; m = meta[gid]
    our_home = (m["home_id"] == g["club_id"])
    sc = SCORE_FIX.get((gid, r["minute"], r["scorer"]), r["score_home_away_after"])
    h, a = map(int, sc.split("-"))
    side_home = r["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours_scored = (side_home == our_home)
    gf, ga = (h, a) if our_home else (a, h)
    mn, dm = parse_min(r["minute"])
    base = dict(gid=gid, date=local_date(g), opp=g["opponent"], comp=comp_code(g), min=mn, dm=dm, gf=gf, ga=ga,
                minute_txt=r["minute"], tm_comp=g["competitionId"], game_state=g["gameState"])
    if kg:
        if r["own_goal"] == "1" or not ours_scored:
            dropped_goals.append((gid, base["date"], r["minute"], "자책골"))
        else:
            E.append(dict(base, type="g", pk=int(r["penalty"] == "1"), note=0, atype=r["assist_type"]))
            if ks:
                self_assists.append((gid, base["date"], r["minute"], r["assist_type"]))
    if ka:
        at = r["assist_type"]; reason = None
        if r["own_goal"] == "1" or not ours_scored:
            reason = "상대 자책골에 준 도움"
        elif at in EXCL_TYPES:
            reason = EXCL_TYPES[at]
        elif r["penalty"] == "1":
            reason = "PK 유도"        # assist on a penalty goal with empty type = penalty won (1999.12.4, 2001.1.28)
        if reason:
            dropped_assists.append((gid, base["date"], r["minute"], r["scorer"], at, reason))
        else:
            E.append(dict(base, type="a", pk=0, note=r["scorer"], atype=at))

# ---------------------------------------------------------------- ko / tie / et
def tie_info(g):
    m = meta[g["gameId"]]; rnd = rnd_of(g)
    leg = 1 if "1st" in rnd else 2
    home = int(m["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        hh, aa = map(int, m["other_leg_score"].split(":"))   # report shows the other leg as <this leg's home>:<this leg's away>
        fu, ft = (hh, aa) if home else (aa, hh)
    return [leg, home, fu, ft, 1, 1]   # away goals (UEFA <= 2020-21, League Cup SF <= 2017-18), extra time in 2nd leg

for e in E:
    g = gbyid[e["gid"]]
    e["tie"] = tie_info(g) if is_two_leg(g) else None
    e["ko"] = int(e["comp"] in ("dc", "dk", "dsf", "df", "clf", "elf") and not e["tie"])
    e["et"] = int(g["gameState"] in ("extra_time", "penalty_shootout") and 90 < e["min"] <= 95 and not e["dm"])
E.sort(key=lambda e: (e["date"], e["min"], 0 if e["type"] == "g" else 1))
dropped_assists.sort(key=lambda d: (d[1], int(d[2].split("+")[0])))

# ---------------------------------------------------------------- opponent Elo
STOP = set(("fc cf afc ac as sc cd ud rcd ssc ss us sv vfl vfb tsg fk sk jk bk if club de da do del la le l e y "
  "calcio futebol clube sfc the sl sad ca kv rc fsv bsc nk gnk rsc krc sm ea sco hsc fco ogc "
  "cfc bc uc hotspur balompie oc lb").split())
TOK_ALIAS = dict(man="manchester", utd="united", munich="munchen", dep="deportivo", bor="borussia",
  gladbach="monchengladbach", mgladbach="monchengladbach", athletico="atletico", internazionale="inter",
  moskau="moscow", moskva="moscow", wien="vienna", praha="prague", st="saint", cologne="koln",
  lisboa="lisbon", bucuresti="bucharest", kyiv="kiev", kiew="kiev", piraeus="piraeus", olympiakos="olympiacos")
def norm(s):
    t = unicodedata.normalize("NFKD", s)
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    t = t.replace("ø", "o").replace("ß", "ss").replace("ł", "l").replace("æ", "ae")
    t = re.sub(r"\(\s*-\s*\d{4}\s*\)", " ", t).replace("m'gladbach", "monchengladbach")
    t = re.sub(r"[^a-z0-9()]+", " ", t)
    w = [TOK_ALIAS.get(x, x) for x in t.split()]
    w = [x for x in w if x not in STOP and not re.fullmatch(r"\d{1,2}", x) and not re.fullmatch(r"(18|19|20)\d\d", x)]
    return " ".join(w) or t.strip()

with open(os.path.join(ROOT, "elo", "ents.json"), encoding="utf-8") as f:
    ENTS = [x for x in json.load(f) if x["p"] != "미하엘 발라크"]

TABLE = {}
with open(os.path.join(ROOT, "elo", "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        for v in r["이름 표기"].split(" / ") + [r["팀"]]:
            TABLE.setdefault((norm(v), r["시즌"]), r)

RANKS = {}
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    next(f)
    for line in f:
        lg, se, rk, n, team = line.rstrip("\n").split("|")
        RANKS[(team, se.split(" ")[0])] = (lg, int(rk), int(n))

def season_label(d):
    y, m = int(d[:4]), int(d[5:7]); s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# Bundesliga: 1998-99..2006-07 = 2025-26 rank values (same as all existing data), 2007-08..2009-10 the same minus
# the season shift found in existing data (Klose), 2010-11 / 2011-12 = complete rank tables in existing data
BL_BASE = [2006, 1912, 1860, 1828, 1812, 1797, 1777, 1756, 1737, 1723, 1713, 1702, 1697, 1682, 1661, 1644, 1634, 1613]
BL_SHIFT = {"2007-08": -65.46, "2008-09": -34, "2009-10": -33}
BL_FULL = {"2010-11": [1983, 1890, 1837, 1805, 1789, 1774, 1754, 1733, 1714, 1700, 1690, 1679, 1674, 1659, 1638, 1621, 1611, 1590],
           "2011-12": [1983, 1889, 1837, 1804, 1788, 1774, 1754, 1732, 1713, 1700, 1689, 1678, 1673, 1658, 1637, 1621, 1611, 1589]}
# 2. Bundesliga rank values used in existing data (no seasonal shift)
L2_VAL = {1: 1697, 3: 1636, 4: 1622, 5: 1615, 6: 1609, 8: 1592, 9: 1584, 10: 1579, 11: 1574, 12: 1570, 13: 1568, 14: 1561,
          17: 1541, 18: 1532}

def model(lg, se, rk):
    if lg == "L1":
        if se in BL_FULL: return BL_FULL[se][rk - 1], f"분데스리가 {se} {rk}위"
        return int(BL_BASE[rk - 1] + BL_SHIFT.get(se, 0) + 0.5), f"분데스리가 {se} {rk}위"
    if lg == "L2" and rk in L2_VAL:
        return L2_VAL[rk], f"2. 분데스리가 {se} {rk}위"
    if lg in ("RNO", "RWS", "RN"):
        name = {"RNO": "북동부", "RWS": "서부·남서부", "RN": "북부"}[lg]
        return 1450, f"독일 3부 레기오날리가 {name} {se} {rk}위 (추정)"
    if lg == "IT1" and se == "1999-00" and rk == 8:     # 18-team Serie A: 8th = 1743 (2002-03, 2003-04 in existing data)
        return 1743, f"세리에A {se} {rk}위"
    if lg == "ES1" and se == "2000-01" and rk == 1:     # 2000-01 values = 2003-04 values + 31 (2nd 1909, 4th 1826 in existing data)
        return 1996, f"라리가 {se} {rk}위"
    if lg == "ES1" and se == "2001-02" and rk == 4:     # 2001-02 values = 2003-04 values + 16 (2nd 1894, 3rd 1845)
        return 1811, f"라리가 {se} {rk}위"
    if lg == "PO1" and se == "2000-01" and rk == 3:     # Portuguese 3rd = 1716 (2005-06), 4th 1690 constant
        return 1716, f"포르투갈 1부 {se} {rk}위"
    if lg == "NL1" and rk == 2:                          # Eredivisie values constant across seasons
        return 1735, f"에레디비시 {se} {rk}위"
    if lg == "L2" and rk == 7:
        return 1600, f"2. 분데스리가 {se} {rk}위 (추정, 다른 선수 자료의 2부 6위 1609·8위 1592 사이)"
    if lg == "OL8":
        return 1300, f"독일 4부 오버리가 남서부 {se} {rk}위 (추정)"
    return None

# direct estimates (all '추정'); key = (TM opponent name, season)
MAN = {
    ("1.FC Kaiserslautern II", "1997-98"): (1450, "독일 3부 레기오날리가 서부·남서부 1997-98 (추정, 카이저슬라우테른 2군)"),
    ("SV Werder Bremen Reserve", "2002-03"): (1450, "독일 3부 레기오날리가 북부 2002-03 (추정, 브레멘 2군)"),
    ("SC Tavriya Simferopol (-2022)", "2010-11"): (1440, "우크라이나 2010-11 7위 (추정, 다른 선수 자료의 보르스클라 1440·카르파티 1450과 같은 수준)"),
    ("Metalist Kharkiv", "2010-11"): (1560, "우크라이나 2010-11 3위 (추정, 다른 선수 자료의 드니프로 2014-15 3위 1600보다 조금 낮게)"),
    ("Red Star Belgrade", "2001-02"): (1500, "유고슬라비아 2001-02 2위 (추정, 다른 선수 자료의 츠르베나 즈베즈다 2007-08 2위 값과 같음)"),
    ("Fenerbahce", "2001-02"): (1772, "쉬페르리그 2001-02 2위 (추정, 다른 선수 자료의 페네르바체 2004-05·2005-06 값과 같음)"),
    ("Maccabi Tel Aviv", "2004-05"): (1400, "이스라엘 2004-05 8위 (추정, 다른 선수 자료의 이스라엘 상위권 1450~1520보다 낮게)"),
}
SAME_MATCH_ALIAS = {}

def _dd(a, b):
    return abs((Date.fromisoformat(a) - Date.fromisoformat(b)).days)
def _sub(a, b):
    A, B = set(a.split()), set(b.split()); return A <= B or B <= A

def resolve_elo(e):
    k = norm(SAME_MATCH_ALIAS.get(e["opp"], e["opp"]))
    same = [x for x in ENTS if _dd(x["date"], e["date"]) <= 1 and _sub(norm(x["opp"]), k)]
    if same:
        (elo, lv), _ = Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        return elo, lv, "같은 경기 다른 선수 자료(" + "·".join(sorted({x["p"] for x in same})) + ")"
    se = season_label(e["date"])
    t = TABLE.get((k, se))
    if t:
        return int(t["Elo"]), t["수준 라벨(lv)"], "팀×시즌 통합표(" + t["선수"] + ")"
    if (e["opp"], se) in MAN:
        v, lv = MAN[(e["opp"], se)]
        return v, lv, "직접 추정"
    r = RANKS.get((e["opp"], se))
    if r:
        mm = model(r[0], se, r[1])
        if mm:
            return mm[0], mm[1], "순위표+리그 모델"
    raise KeyError(("no elo", e["date"], e["opp"], se, r))

UNRESOLVED = []
for e in E:
    try:
        e["elo"], e["lv"], e["elo_src"] = resolve_elo(e)
    except KeyError as ex:
        UNRESOLVED.append(ex.args[0]); e["elo"], e["lv"], e["elo_src"] = 0, "", "?"

# ---------------------------------------------------------------- clubs
CLUBS = [("chmbk", "1997-07-01"), ("fckbk", "1999-07-01"), ("levbk", "2002-07-01"), ("baybk", "2006-07-01"),
         ("chebk", "2010-07-01"), ("levbk", None)]
def club_of(d):
    for k, until in CLUBS:
        if until is None or d < until:
            return k
CLUB_KO = {"chmbk": "켐니처 FC(1995~1997)", "fckbk": "카이저슬라우테른(1997~1999)", "levbk": "레버쿠젠(1999~2002, 2010~2012)",
           "baybk": "바이에른 뮌헨(2002~2006)", "chebk": "첼시(2006~2010)"}
CLUB_ORDER = ["chmbk", "fckbk", "levbk", "baybk", "chebk"]

def kdate(d):
    y, m, dd = d.split("-"); return f"{int(y)}.{int(m)}.{int(dd)}"

OPP_KO = {"VfB Leipzig": "VfB 라이프치히", "1.FC Nuremberg": "뉘른베르크", "SpVgg Unterhaching": "운터하힝", "Hertha BSC": "헤르타",
          "VfL Wolfsburg": "볼프스부르크", "SV Werder Bremen": "브레멘", "1.FC Kaiserslautern": "카이저슬라우테른",
          "FC Hansa Rostock": "로스토크", "Hamburger SV": "함부르크", "Borussia Neunkirchen": "노인키르헨", "Chelsea FC": "첼시",
          "Fulham FC": "풀럼", "Manchester United": "맨유", "SC Tavriya Simferopol (-2022)": "타브리야", "VfB Stuttgart": "슈투트가르트",
          "Borussia Mönchengladbach": "묀헨글라트바흐", "1.FC Köln": "쾰른", "Hannover 96": "하노버", "SC Freiburg": "프라이부르크",
          "TSV 1860 Munich": "1860 뮌헨", "1.FSV Mainz 05": "마인츠", "Charlton Athletic": "찰턴", "Tottenham Hotspur": "토트넘",
          "Liverpool FC": "리버풀", "Portsmouth FC": "포츠머스", "Aston Villa": "애스턴 빌라", "FC Bayern Munich": "바이에른",
          "Hertha BSC ": "헤르타", "Bayer 04 Leverkusen": "레버쿠젠", "FC Energie Cottbus": "코트부스", "Arminia Bielefeld": "빌레펠트"}

def stats():
    out = {k: [0, 0, 0, 0] for k in CLUB_ORDER}
    for m in M:
        k = club_of(m[0]); out[k][0] += 1; out[k][3] += m[3]
    for e in E:
        out[club_of(e["date"])][1 if e["type"] == "g" else 2] += 1
    return out

def spell(a, b):
    mm = [m for m in M if club_of(m[0]) == "levbk" and a <= m[0] < b]
    ee = [e for e in E if club_of(e["date"]) == "levbk" and a <= e["date"] < b]
    return len(mm), sum(e["type"] == "g" for e in ee), sum(e["type"] == "a" for e in ee)

def build_note():
    st = stats()
    G = sum(e["type"] == "g" for e in E); A = sum(e["type"] == "a" for e in E)
    PK = [e for e in E if e["type"] == "g" and e["pk"]]
    mins = sum(m[3] for m in M)
    first, last = M[0], M[-1]
    l1, l2 = spell("1999", "2003"), spell("2010", "2013")
    da = dropped_assists
    def lst(reason): return [d for d in da if d[5] == reason]
    pk, sh, og = lst("PK 유도"), lst("슈팅 리바운드"), lst("상대 자책골에 준 도움")
    tm_total = A + len(da)
    blank = [e for e in E if e["type"] == "a" and e["atype"] == ""]
    def dl(L2): return ", ".join(f"{kdate(d[1])} {OPP_KO.get(gbyid[d[0]]['opponent'], gbyid[d[0]]['opponent'])}전 {d[2]}분" for d in L2)
    L = []
    L.append(f"미하엘 발라크(켐니처 FC·카이저슬라우테른·레버쿠젠·바이에른 뮌헨·첼시)의 클럽 공식 경기 {len(M)}경기"
             f"({kdate(first[0])} {OPP_KO[first[1]]}전 ~ {kdate(last[0])} {OPP_KO[last[1]]}전)에서 나온 {G}골 {A}도움(PK 골 {len(PK)}개), 친선경기·2군·독일 대표팀 제외")
    L.append("클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {st[k][0]}·{st[k][1]}·{st[k][2]}" for k in CLUB_ORDER)
             + f"(레버쿠젠 1기 {l1[0]}·{l1[1]}·{l1[2]}, 2기 {l2[0]}·{l2[1]}·{l2[2]}). 출전 분 합계 {mins:,}분("
             + ", ".join(f"{CLUB_KO[k].split('(')[0]} {st[k][3]:,}분" for k in CLUB_ORDER) + ")")
    L.append("출처: 경기 목록·출전 분(연장·퇴장 반영)·선발/교체는 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(출전한 경기 전부). 2010-11 이후 레버쿠젠 경기는 FotMob 경기 이벤트와 대조. 출전 분이 없어 90분으로 추정한 경기는 없음")
    L.append("경기 수·골은 영어 위키백과 클럽·시즌·대회별 기록과 모두 같음(켐니처 51·10, 카이저슬라우테른 57·4, 레버쿠젠 110·37과 45·5, 바이에른 157·62, 첼시 167·26). 독일어 위키백과는 첼시 166경기 25골(2006-07 리그 4골, 2007-08 29경기)로 영어 위키백과·Transfermarkt보다 1경기·1골 적음")
    L.append("뺀 기록: 카이저슬라우테른 2군(1997-98 레기오날리가 서부·남서부 17경기 8골, Transfermarkt에만 있음)은 2군 경기라 넣지 않음. 켐니처 FC 2군(위키백과 1994-95·1995-96 오버리가 18경기 5골)은 Transfermarkt에 경기 기록이 없고 2군이라 넣지 않음. 켐니처 1군의 1995-96 2. 분데스리가 15경기·1996-97 레기오날리가 북동부(당시 3부) 34경기·DFB-포칼 2경기는 1군 공식 경기라 넣음")
    L.append("Transfermarkt 선수 경기 성적에서 '다른 팀으로 출전'으로 표시된 1997-98 카이저슬라우테른 2군 리그 경기 7개는 출전으로 세지 않음")
    L.append(f"골: Transfermarkt 경기 리포트의 발라크 골에서 자책골 2개(2000.5.20 운터하힝전 20분, 2003.5.10 헤르타전 5분)를 뺀 {G}골. "
             f"PK 골 {len(PK)}개는 0.8점: " + ", ".join(kdate(e['date']) + " " + OPP_KO.get(e['opp'], e['opp']) + ("(" + (e['dm'] or str(e['min'])) + "분)" if e['date'] == "2003-07-22" else "") for e in PK))
    L.append("2010-11 이후 골 5개 중 4개는 FotMob 경기 이벤트와 골 뒤 스코어·PK가 같음(2010.8.19 타브리야전·2011.9.28 헹크전 90+2분 골은 FotMob이 90분으로 적어 Transfermarkt 분을 씀). 2011.2.24 메탈리스트전 70분 골은 FotMob 경기 자료가 없어(Data not found) Transfermarkt만 근거")
    L.append("2010.8.19 타브리야전 90+2분 PK 골은 Transfermarkt 리포트에 키슬링이 도움(유형 빈칸)으로 적혀 있으나 PK 골이라 PK 유도로 보고, FotMob도 도움이 없음. 발라크 기록은 PK 골 그대로")
    L.append(f"도움: 2014.8.1 이전 규칙대로 Transfermarkt 경기 리포트 도움에서 아래를 뺀 것을 씀. 도움 {A} = Transfermarkt 리포트 {tm_total} − PK 유도 {len(pk)} − 슈팅 리바운드(Shot on goal) {len(sh)} − 상대 자책골에 준 도움 {len(og)}")
    L.append(f"뺀 PK 유도 {len(pk)}: {dl(pk)}. 이 가운데 1999.12.4 브레멘전 47분·2001.1.28 슈투트가르트전 66분(둘 다 키르스텐 PK 골)은 리포트 유형이 비어 있으나 PK 골에 붙은 도움이라 PK 유도로 봄")
    L.append(f"뺀 슈팅 리바운드 {len(sh)}: {dl(sh)}. 뺀 상대 자책골 도움 {len(og)}: {dl(og)}")
    L.append("본인 골에 본인이 도움으로 적힌 리포트 4개(2005.3.19 로스토크전 87분 PK, 2005.4.6 첼시전 90+3분 PK, 2006.12.17 에버턴전 49분 프리킥, 2008.1.1 풀럼전 60분 PK)는 골만 세고 도움으로 세지 않음(Transfermarkt 선수 경기 성적 도움 수에도 없음)")
    L.append(f"Transfermarkt 리포트에 도움 유형이 비어 있는 {len(blank)}개(대부분 2003년 이전 경기, 그 뒤 2003~2010년 {sum(e['date'] >= '2003-07-01' for e in blank)}개)는 일반 도움으로 셈. 유형이 없어 PK 유도·슈팅 리바운드인지 가려낼 수 없고, 1995~2010년 도움은 다른 출처로 대조하지 못함(위키백과에 도움 자료 없음)")
    L.append("2010-11 이후 도움 4개: 2011.10.19·2011.11.1 발렌시아전 2개는 FotMob도 발라크 도움. 2011.3.20 샬케전 19분 데르디요크 골은 FotMob 경기 자료가 없고, 2011.10.15 묀헨글라트바흐전 20분 라이나르츠 골은 Transfermarkt 'Header', FotMob 도움 없음 — 둘 다 2014.8.1 이전이라 Transfermarkt를 따라 넣음")
    L.append("골 뒤 스코어를 고친 경기: 2000.9.20 스포르팅전은 리포트의 레버쿠젠 골 스코어가 한 골씩 적게 적혀(끝이 2:2, 실제 3:2) 독일축구협회 기록대로 72분 2:1, 77분 노이빌레 골(발라크 도움) 3:1로 고침(직전 2:1). 이 경기 날짜는 리포트의 현지 날짜 2000.9.20(선수 경기 성적은 협정 세계시 9.19 22시). 2005.5.7 마인츠전은 리포트가 17분 아우어 골과 17분 마카이 골(발라크 도움)을 둘 다 1:1로 적었으나 다른 기록은 아우어 골이 35분이라 마카이 골 직전을 0:0으로 씀")
    L.append("연장전: 2007.4.15 블랙번전(FA컵 준결승) 109분 골은 연장 시간으로 계산. 2003.7.22 함부르크전(리가포칼 준결승) 90분 PK 골은 3:3 동점 골, 승부차기로 짐")
    L.append("상대 Elo: 분데스리가 1998-99~2006-07은 다른 선수 자료와 같은 순위별 값, 2007-08~2009-10은 그 값에서 시즌별로 같은 폭을 내린 값, 2010-11·2011-12는 다른 선수 자료의 같은 시즌 순위별 값. 같은 경기·같은 상대를 다른 선수(램파드·드록바·로번) 자료가 이미 계산했으면 그 값을 씀. 프리미어리그·챔스 상대 등은 팀×시즌 통합표 값")
    L.append("상대 Elo(순위표+다른 선수 자료의 순위별 값): 우디네세 1999-00 8위 1743(18팀 세리에A), 레알 마드리드 2000-01 1위 1996·바르셀로나 2001-02 4위 1811(같은 시즌 다른 순위 값과 같은 폭), 스포르팅 2000-01 3위 1716(포르투갈 1부), 아약스 2004-05 2위 1735(에레디비시), 하노버 2001-02 2부 1위 1697·아헨 2003-04 2부 6위 1609")
    L.append("상대 Elo(추정): 독일 3부 레기오날리가 1450(켐니처 1996-97 레기오날리가 북동부 상대 전부, 카이저슬라우테른 2군 1997, 브레멘 2군 2002), 독일 4부 노인키르헨 2003 1300, 2부 7위 아우에 2005-06 1600, 츠르베나 즈베즈다 2001 1500, 페네르바체 2001-02 1772, 마카비 텔아비브 2004-05 1400, 타브리야 2010-11 1440, 메탈리스트 2010-11 1560")
    L.append("대회 비중: DFB-포칼·FA컵·리그컵은 16강까지·8강·준결승·결승으로 나눔(FA컵 3~5라운드와 재경기는 16강까지, 6라운드와 재경기는 8강, 리그컵 3라운드·4라운드는 16강까지, 5라운드는 8강). DFB-리가포칼(시즌 전 리그컵)은 첫 경기(2001.7.12 헤르타전, 8강 격)·준결승·결승을 국내컵 8강·준결승·결승으로, 커뮤니티 실드는 국내컵 결승으로 계산함. 챔스 2001-02 2차 조별리그는 조별, UEFA컵 1999-2000 3라운드와 유로파 2010-11 32강·16강은 유로파 토너먼트, 유로파 플레이오프(타브리야전)는 유로파 예선")
    L.append("두 경기 합산: UEFA 대회 토너먼트·예선과 리그컵 준결승은 합산 S로 계산함(원정 다득점·2차전 연장 있음). FA컵 재경기는 단판. 발라크가 뛰지 않은 1차전 스코어는 Transfermarkt 경기 리포트로 채움(2001.8.8 츠르베나 즈베즈다 원정 0:0, 2011.2.17 메탈리스트 원정 4:0 승)")
    L.append("시즌 구분: 카이저슬라우테른·레버쿠젠·바이에른은 7월 10일 기준(7월 리가포칼·포칼 1라운드가 새 시즌), 켐니처·첼시는 8월 1일 기준. 클럽 구분은 1997.7.1 전 켐니처, 1999.7.1 전 카이저슬라우테른, 2002.7.1 전 레버쿠젠, 2006.7.1 전 바이에른, 2010.7.1 전 첼시, 이후 레버쿠젠(두 시기를 한 클럽으로 묶음)")
    L.append("수상 기록은 Transfermarkt 업적 페이지 기준: 분데스리가 4회(1997-98 카이저슬라우테른, 2002-03·2004-05·2005-06 바이에른), 프리미어리그 2009-10, DFB-포칼 3회(2002-03·2004-05·2005-06), FA컵 3회(2007·2009·2010), 리그컵 2007, DFB-리가포칼 2005(Transfermarkt 표기, 2004.8.2 결승), 커뮤니티 실드 2009-10, 챔스 준우승 2회(2001-02 레버쿠젠·2007-08 첼시, 결승 출전 경기로 확인). 개인: 독일 올해의 선수 3회(2002·2003·2005). 작센컵(1996-97 켐니처, 지역 컵)과 대표팀 기록은 뺌")
    return "\n".join(L)


if __name__ == "__main__":
    if UNRESOLVED:
        for u in UNRESOLVED: print("UNRESOLVED", u)
        raise SystemExit(1)
    note = build_note()
    def row(e):
        r = [e["type"], e["opp"], e["elo"], e["comp"], e["min"], e["gf"], e["ga"], e["ko"], e["pk"], e["date"],
             e["et"], e["dm"] or 0, e["lv"], e["note"] or 0]
        if e["tie"]: r.append(e["tie"])
        return r
    js = lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"E": [{k: e[k] for k in ("type", "opp", "elo", "lv", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm",
                                             "note", "tie", "elo_src", "gid", "minute_txt", "atype")} for e in E],
                   "M": M, "dropped_assists": dropped_assists, "dropped_goals": dropped_goals, "self_assists": self_assists},
                  f, ensure_ascii=False, indent=1)
    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write("const BLK_E=" + js([row(e) for e in E]) + ";\n")
        f.write("const BLK_M=" + js(M) + ";\n")
        f.write("const BLK_NOTE=" + js(note) + ";\n")
    print("wrote", OUT_JS, len(E), "rows,", len(M), "games")
    print(note)
