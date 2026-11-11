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

if __name__ == "__main__":
    if UNRESOLVED:
        for u in UNRESOLVED: print("UNRESOLVED", u)
        raise SystemExit(1)
    from note_ballack import build_note
    note = build_note(globals())
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
