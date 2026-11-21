#!/usr/bin/env python3
"""Miroslav Klose - build script for the club SOC calculator.

Reads players/klose/raw/ (Transfermarkt API + reports, FotMob events, ranks) and
writes players/klose/klose.json (final rows) and src/data/klo.js (KLO_E, KLO_M, KLO_NOTE).

Run: python3 players/klose/build_klose.py        (from the repo root or anywhere)

Scope: senior official first-team matches of FC 08 Homburg (Regionalliga West/Suedwest 1998-99),
1. FC Kaiserslautern, SV Werder Bremen, FC Bayern Munich, SS Lazio. Excluded: 1. FC Kaiserslautern II
(reserve team, club id 151), friendlies, national team. Rules: docs/HANDOFF-클럽SOC계산기.md 2-4, 6, 17.
All judgment calls are listed in players/klose/judgments.md.
"""
import csv, json, os, re, sys
from datetime import datetime, timedelta, date as Date
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_JS = os.path.join(ROOT, "src", "data", "klo.js")
OUT_JSON = os.path.join(HERE, "klose.json")
NOTE_FILE = os.path.join(HERE, "klose_note.txt")

RESERVE_CLUB_IDS = {"151"}          # 1.FC Kaiserslautern II: reserve team -> excluded (precedent: all players)
GAP = "2014-08-01"                  # assist source switch (docs 3): before = Transfermarkt, after = TM & FotMob

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

games = rd("tm_games.csv")
events = rd("tm_events.csv")
meta = {r["gameId"]: r for r in rd("tm_report_meta.csv")}
fm_events = rd("fotmob_events.csv")
fm_map = {r["tm_gameId"]: r for r in rd("fotmob_match_map.csv")}

# ---------------------------------------------------------------- dates
BERLIN = ZoneInfo("Europe/Berlin")
def local_date(g):
    if g["date_local_tm_report"]:
        return g["date_local_tm_report"]
    dt = datetime.fromisoformat(g["date_utc"]).astimezone(BERLIN)
    return dt.strftime("%Y-%m-%d")

# ---------------------------------------------------------------- competition code
def round_of(gid):
    m = meta.get(gid)
    return m["round"] if m else ""

def comp_code(g):
    c = g["competitionId"]; rnd = round_of(g["gameId"]).lower(); gid = g["gameId"]
    if c in ("RWS", "L1", "IT1"):
        return "lg"
    if c in ("DFB", "CIT"):
        # rounds: report round name where a report exists, else API gameDay (DFB: 1,2,3=R16,4=QF,5=SF,6=F;
        # CIT: 3,4,5=R16,6=QF,7/8=SF,9=F)
        gd = int(g["gameDay"])
        if rnd:
            if "final" == rnd.strip() or rnd.startswith("final"):
                return "df"
            if "semi" in rnd: return "dsf"
            if "quarter" in rnd: return "dk"
            return "dc"
        if c == "DFB":
            return {1: "dc", 2: "dc", 3: "dc", 4: "dk", 5: "dsf", 6: "df"}[gd]
        return {3: "dc", 4: "dc", 5: "dc", 6: "dk", 7: "dsf", 8: "dsf", 9: "df"}[gd]
    if c == "LPO":   # DFB-Ligapokal (pre-season league cup): quarter/intermediate = dk, semi = dsf, final = df
        if "semi" in rnd: return "dsf"
        if rnd.startswith("final"): return "df"
        return "dk"
    if c in ("DFL", "SCI"):  # super cups = domestic cup final
        return "df"
    if c == "CLQ": return "clq"
    if c == "CL":
        if "group" in rnd: return "clg"
        if "last 16" in rnd: return "cl16"
        if "quarter" in rnd: return "clk"
        if "semi" in rnd: return "clsf"
        if rnd.startswith("final"): return "clf"
        raise ValueError(("CL round", gid, rnd))
    if c == "ELQ": return "elq"
    if c in ("UEFA", "EL"):
        if "first round" in rnd: return "elq"            # UEFA Cup 1st round (pre-2009) = EL qualifying
        if "group" in rnd: return "elg"
        if "semi" in rnd: return "elsf"
        if rnd.startswith("final"): return "elf"
        return "elk"   # UEFA Cup 2nd/3rd round, last 16, QF; EL round of 32 ('intermediate stage', 'Second Round')
    raise ValueError(("comp", gid, c))

TWO_LEG_COMPS = {"UEFA", "EL", "ELQ", "CL", "CLQ", "CIT"}
def is_two_leg(g):
    return g["competitionId"] in TWO_LEG_COMPS and "leg" in round_of(g["gameId"]).lower()

# ---------------------------------------------------------------- appearances
CLUB_NAME = {"459": "FC 08 Homburg", "2": "1.FC Kaiserslautern", "86": "SV Werder Bremen",
             "27": "FC Bayern Munich", "398": "SS Lazio"}
played = [g for g in games if g["club_id"] not in RESERVE_CLUB_IDS]
excluded_reserve = [g for g in games if g["club_id"] in RESERVE_CLUB_IDS]
gbyid = {g["gameId"]: g for g in games}

M = []
for g in played:
    M.append([local_date(g), g["opponent"], comp_code(g), int(g["playedMinutes"])])
M.sort(key=lambda r: (r[0]))

# ---------------------------------------------------------------- minute parsing
def parse_min(s):
    """'45+2' -> (47,'45+2'); '90+4' -> (94,'90+4'); '120+2' -> (122,'120+2'); '102' -> (102,0)"""
    s = s.strip()
    if "+" in s:
        a, b = s.split("+")
        return int(a) + int(b), s
    return int(s), 0

# ---------------------------------------------------------------- goal / assist decisions
# assist types excluded everywhere (docs 3): penalty won, rebound after own shot ('Shot on goal'),
# assists to an opponent's own goal, own assist to own penalty.
EXCL_TYPES = {"Penalty: Fouled player": "PK 유도", "Shot on goal": "슈팅 리바운드"}
# post-GAP Transfermarkt-only assists need two further sources; none could be confirmed (judgments.md)
POST_GAP_TM_ONLY_DROP = {("2478880", "53")}   # 2015.4.12 Empoli 53' Felipe Anderson (TM 'Cross', FotMob none)
# FotMob-only assists after GAP are not added (judgments.md): 2015.3.1 Sassuolo 77' Parolo
fm_klose_assists = {(r["tm_gameId"], r["time"]) for r in fm_events if r["klose_assist"] == "1"}

def fm_has_assist(gid, minute):
    base = int(minute.split("+")[0]); full = parse_min(minute)[0]
    for (fg, t) in fm_klose_assists:
        if fg == gid and (abs(int(t) - base) <= 2 or abs(int(t) - full) <= 2):
            return True
    return False

ev_by_game = {}
for r in events:
    ev_by_game.setdefault(r["gameId"], []).append(r)

E = []                # final rows (dicts)
dropped_assists = []  # (gid, date, minute, scorer, reason)
dropped_goals = []
for gid, evs in ev_by_game.items():
    g = gbyid.get(gid)
    if not g or g["participationState"] != "played" or g["club_id"] in RESERVE_CLUB_IDS:
        continue
    m = meta[gid]
    our_home = (m["home_id"] == g["club_id"])
    for r in evs:
        kg, ka = r["klose_scorer"] == "1", r["klose_assist"] == "1"
        if not (kg or ka):
            continue
        h, a = map(int, r["score_after_home_away"].split("-"))
        side_home = r["scoring_side"] == "home"
        if side_home: h -= 1
        else: a -= 1
        ours_scored = (side_home == our_home)
        gf, ga = (h, a) if our_home else (a, h)
        mn, dm = parse_min(r["minute"])
        base = dict(gid=gid, date=local_date(g), opp=g["opponent"], comp=comp_code(g), min=mn,
                    dm=dm, gf=gf, ga=ga, minute_txt=r["minute"], tm_comp=g["competitionId"])
        if kg:
            if r["own_goal"] == "1" or not ours_scored:
                dropped_goals.append((gid, base["date"], r["minute"], "자책골"))
                continue
            E.append(dict(base, type="g", pk=int(r["penalty"] == "1"), note=0, atype=""))
        if ka:
            at = r["assist_type_text"]
            reason = None
            if r["own_goal"] == "1" or not ours_scored:
                reason = "상대 자책골에 준 도움"
            elif at in EXCL_TYPES:
                reason = EXCL_TYPES[at]
            elif r["scorer"] == "Miroslav Klose":
                reason = "본인 골 본인 도움"
            elif base["date"] >= GAP:
                if (gid, r["minute"]) in POST_GAP_TM_ONLY_DROP:
                    reason = "2014.8.1 이후 Transfermarkt 단일 출처(확인 못 함)"
                elif not fm_has_assist(gid, r["minute"]):
                    reason = "2014.8.1 이후 FotMob 없음"
            if reason:
                dropped_assists.append((gid, base["date"], r["minute"], r["scorer"], at, reason))
                continue
            E.append(dict(base, type="a", pk=0, note=r["scorer"], atype=at))

# ---------------------------------------------------------------- ko / tie / et
def tie_info(g):
    """[leg, home, firstLegOurs, firstLegTheirs, awayGoals, extraTime] for two-legged ties"""
    gid = g["gameId"]; m = meta[gid]; rnd = m["round"].lower()
    leg = 1 if "1st" in rnd else 2
    home = int(m["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = meta[m["other_leg_id"]]
        hh, aa = map(int, o["final_score"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = hh, aa
        else: fu, ft = aa, hh
    ag = 1    # UEFA through 2020-21, Coppa Italia through 2021-22
    et = 1    # extra time in the 2nd leg (UEFA; Coppa Italia semi-final 2nd leg)
    return [leg, home, fu, ft, ag, et]

for e in E:
    g = gbyid[e["gid"]]
    e["tie"] = tie_info(g) if is_two_leg(g) else None
    single_ko = e["comp"] in ("dc", "dk", "dsf", "df", "clf", "elf") and not e["tie"]
    e["ko"] = int(single_ko)
    # extra-time flag only needed where the minute alone does not show it (ET minute <= 95)
    e["et"] = 0
    if g["gameState"] in ("extra_time", "penalty_shootout") and e["min"] > 90 and e["min"] <= 95 and not e["dm"]:
        e["et"] = 1

E.sort(key=lambda e: (e["date"], e["min"], 0 if e["type"] == "g" else 1))

# ---------------------------------------------------------------- opponent Elo
import unicodedata
STOP = set(("fc cf afc ac as sc cd ud rcd ssc ss us sv vfl vfb tsg fk sk jk bk if club de da do del la le l e y "
  "calcio futebol clube sfc the sl sad ca kv rc fsv bsc nk gnk rsc krc sm ea sco hsc fco ogc "
  "cfc bc uc hotspur balompie oc lb").split())
TOK_ALIAS = dict(man="manchester", utd="united", munich="munchen", dep="deportivo", bor="borussia",
  gladbach="monchengladbach", mgladbach="monchengladbach", athletico="atletico", internazionale="inter",
  moskau="moscow", moskva="moscow", wien="vienna", praha="prague", st="saint", cologne="koln",
  lisboa="lisbon", bucuresti="bucharest", kyiv="kiev", kiew="kiev")
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
    ENTS = [x for x in json.load(f) if x["p"] != "미로슬라프 클로제"]

TABLE = {}
with open(os.path.join(ROOT, "elo", "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        for v in r["이름 표기"].split(" / ") + [r["팀"]]:
            TABLE.setdefault((norm(v), r["시즌"]), r)

RANKS = {}
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        lg, se, rk, n, team = line.strip().split("|")
        RANKS[(team, se)] = (lg, int(rk), int(n))

def season_label(d):
    y, m = int(d[:4]), int(d[5:7]); s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# league models (same values as the existing calculator data, see judgments.md)
BL_BASE = [2006, 1912, 1860, 1828, 1812, 1797, 1777, 1756, 1737, 1723, 1713, 1702, 1697, 1682, 1661, 1644, 1634, 1613]
BL_SHIFT = {"2007-08": -65.46, "2008-09": -34, "2009-10": -33, "2010-11": None}   # 2000-01..2006-07: no shift
IT_FIXED = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
L2_FIT = {1: 1697, 4: 1622, 9: 1584}         # 2. Bundesliga: fitted from existing values (judgments.md)
def model(lg, se, rk):
    if lg == "L1":
        sh = BL_SHIFT.get(se, 0)
        if sh is None:
            return None
        return int(BL_BASE[rk - 1] + sh + 0.5), f"분데스리가 {se} {rk}위"
    if lg == "IT1":
        return IT_FIXED[rk - 1], f"세리에A {se} {rk}위"
    if lg == "L2" and rk in L2_FIT:
        return L2_FIT[rk], f"2. 분데스리가 {se} {rk}위"
    if lg == "NL1" and se == "2006-07" and rk == 3:
        return 1677, "에레디비시 2006-07 3위"
    return None

# direct estimates (all '추정'); key = (TM opponent name, opponent-league season)
MAN = {
    ("Wuppertaler SV", "1998-99"): (1450, "독일 3부 레기오날리가 서부·남서부 1998-99 8위 (추정)"),
    ("USC Paloma Hamburg", "2002-03"): (1300, "독일 4부 오버리가 함부르크 2002-03 5위 (추정)"),
    ("Eintracht Braunschweig", "2003-04"): (1450, "독일 3부 레기오날리가 북부 2003-04 6위 (추정)"),
    ("FC Bayern Munich II", "2004-05"): (1450, "독일 3부 레기오날리가 남부 2004-05 6위 (추정)"),
    ("FC St. Pauli", "2005-06"): (1450, "독일 3부 레기오날리가 북부 2005-06 6위 (추정)"),
    ("Rot-Weiß Erfurt", "2008-09"): (1422, "독일 3부 리가 2008-09 10위 (추정, 다른 선수 자료의 3부 리가 9위 1429·13위 1409 사이)"),
    ("Bohemian Football Club", "2000-01"): (1300, "아일랜드 2000-01 4위 (추정, 다른 선수 자료의 아일랜드 1위 1350보다 낮게)"),
    ("Iraklis Thessaloniki", "2000-01"): (1480, "그리스 2000-01 5위 (추정, 다른 선수 자료의 아리스 1480과 같은 수준)"),
    ("Rangers FC", "2000-01"): (1620, "스코틀랜드 2000-01 2위 (추정, 다른 선수 자료의 레인저스 2007 2위 값과 같음)"),
    ("SK Slavia Prague", "2000-01"): (1500, "체코 2000-01 2위 (추정, 다른 선수 자료의 슬라비아 2007·2008 값과 같음)"),
    ("FK Teplice", "2003-04"): (1400, "체코 2003-04 9위 (추정, 체코 상위권 1500~1520보다 낮게)"),
    ("RSC Anderlecht", "2004-05"): (1596, "벨기에 1부 2004-05 2위 (추정, 다른 선수 자료의 2007-08 2위 값과 같음)"),
    ("FC Basel 1893", "2005-06"): (1600, "스위스 2005-06 2위 (추정, 다른 선수 자료의 바젤 2008 값과 같음)"),
    ("Red Star Belgrade", "2007-08"): (1500, "세르비아 2007-08 2위 (추정, 다른 선수 자료의 2006-07 1위 1520보다 낮게)"),
    ("SC Braga", "2007-08"): (1606, "포르투갈 1부 2007-08 7위 (추정: 모형값)"),
    ("Aberdeen FC", "2007-08"): (1500, "스코틀랜드 2007-08 4위 (추정, 다른 선수 자료의 히버니언 4위권 값과 같음)"),
    ("Rabotnicki Skopje", "2011-12"): (1300, "북마케도니아 2011-12 8위 (추정)"),
    ("NS Mura", "2012-13"): (1300, "슬로베니아 2012-13 9위 (추정, 다른 선수 자료의 무라 2021 1위 1360보다 낮게)"),
    ("FC Bassano", "2014-15"): (1490, "세리에C 2014-15 조 A 2위 (추정, 다른 선수 자료의 라벤나 2008-09 3위 1480보다 조금 높게)"),
}
SAME_MATCH_ALIAS = {"FCSB": "Steaua Bucharest"}

def _dd(a, b):
    return abs((Date.fromisoformat(a) - Date.fromisoformat(b)).days)
def _sub(a, b):
    A, B = set(a.split()), set(b.split()); return A <= B or B <= A

def resolve_elo(e):
    """returns (elo, lv, source)"""
    k = norm(SAME_MATCH_ALIAS.get(e["opp"], e["opp"]))
    same = [x for x in ENTS if _dd(x["date"], e["date"]) <= 1 and _sub(norm(x["opp"]), k)]
    if same:
        from collections import Counter
        (elo, lv), _ = Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ps = sorted({x["p"] for x in same})
        return elo, lv, "같은 경기 다른 선수 자료(" + "·".join(ps) + ")"
    se = season_label(e["date"])
    t = TABLE.get((k, se))
    if t:
        return int(t["Elo"]), t["수준 라벨(lv)"], "팀×시즌 통합표(" + t["선수"] + ")"
    if (e["opp"], se) in MAN:
        v, lv = MAN[(e["opp"], se)]
        return v, lv, "직접 추정"
    r = RANKS.get((e["opp"], se))
    if r:
        m = model(r[0], se, r[1])
        if m:
            return m[0], m[1], "순위표+리그 모델"
    raise KeyError(("no elo", e["date"], e["opp"], se, r))

for e in E:
    e["elo"], e["lv"], e["elo_src"] = resolve_elo(e)

# ---------------------------------------------------------------- clubs / stats for the description
CLUBS = [("homkl", "1999-07-01"), ("fckkl", "2004-07-01"), ("svwkl", "2007-07-01"), ("baykl", "2011-07-01"), ("lazkl", None)]
def club_of(d):
    for k, until in CLUBS:
        if until is None or d < until:
            return k
CLUB_KO = {"homkl": "FC 08 홈부르크(1998~1999)", "fckkl": "카이저슬라우테른(2000~2004)", "svwkl": "베르더 브레멘(2004~2007)",
           "baykl": "바이에른 뮌헨(2007~2011)", "lazkl": "라치오(2011~2016)"}

def kdate(d):
    y, m, dd = d.split("-"); return f"{int(y)}.{int(m)}.{int(dd)}"

OPP_KO = {"Preußen Münster": "프로이센 뮌스터", "ACF Fiorentina": "피오렌티나", "SC Freiburg": "프라이부르크",
          "Borussia Mönchengladbach": "묀헨글라트바흐", "1.FC Nuremberg": "뉘른베르크", "SV Werder Bremen": "브레멘",
          "Hamburger SV": "함부르크", "Eintracht Frankfurt": "프랑크푸르트", "Hertha BSC": "헤르타", "Sporting CP": "스포르팅"}

def stats():
    out = {}
    for k, _ in CLUBS:
        mm = [m for m in M if club_of(m[0]) == k]
        ee = [e for e in E if club_of(e["date"]) == k]
        out[k] = (len(mm), sum(1 for e in ee if e["type"] == "g"), sum(1 for e in ee if e["type"] == "a"), sum(m[3] for m in mm))
    return out

def fmt_list(items):
    return ", ".join(items)

def build_note():
    st = stats()
    G = sum(1 for e in E if e["type"] == "g"); A = sum(1 for e in E if e["type"] == "a")
    PK = [e for e in E if e["type"] == "g" and e["pk"]]
    mins = sum(m[3] for m in M)
    first, last = M[0], M[-1]
    L = []
    L.append(f"미로슬라프 클로제(FC 08 홈부르크·카이저슬라우테른·베르더 브레멘·바이에른 뮌헨·라치오)의 클럽 공식 경기 {len(M)}경기"
             f"({kdate(first[0])} {OPP_KO[first[1]]}전 ~ {kdate(last[0])} {OPP_KO[last[1]]}전)에서 나온 {G}골 {A}도움(PK 골 {len(PK)}개), 친선경기·카이저슬라우테른 2군·독일 대표팀 제외")
    L.append("클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {v[0]}·{v[1]}·{v[2]}" for k, v in st.items())
             + f". 출전 분 합계 {mins:,}분(" + ", ".join(f"{CLUB_KO[k].split('(')[0]} {v[3]:,}분" for k, v in st.items()) + ")")
    L.append("출처: 경기 목록·출전 분(연장·퇴장 반영)·선발/교체는 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 나온 경기 전부). 출전 분이 없어 90분으로 추정한 경기는 없음")
    L.append("경기 수·골은 영어 위키백과 클럽·시즌별 기록과 같음(홈부르크 18·1, 카이저슬라우테른 147·52, 브레멘 132·63, 바이에른 150·53, 라치오 171·63). 영어 위키백과는 라치오 170경기(2015-16 유럽 대회 1경기 차이, 아래 줄)이고, 바이에른 합계 칸은 149로 적혀 있으나 시즌별 칸의 합은 150임")
    L.append("라치오 2015-16 유럽 대회는 Transfermarkt 5경기(챔스 예선 2015.8.18 레버쿠젠전 45분 교체 투입 포함)·위키백과 4경기로 1경기 다름. 다섯 경기 모두 Transfermarkt 경기 리포트 교체 기록에 클로제가 있어 5경기를 씀(골·도움 없는 경기라 출전 분에만 영향)")
    L.append("뺀 기록: 카이저슬라우테른 2군(1999-2000 레기오날리가 36경기 11골, 2000-01 오버리가 남서부 14경기 15골, 합계 50경기 26골)은 2군 경기라 넣지 않음. 홈부르크 아마추어팀(독일어 위키백과 15경기 10골)은 Transfermarkt에 경기 기록이 없고 2군이라 넣지 않음. 홈부르크 1군의 1998-99 레기오날리가 서부·남서부(당시 3부) 18경기는 1군 공식 경기라 넣음")
    L.append("Transfermarkt 선수 경기 성적에서 '다른 팀으로 출전'으로 표시된 2000년 5~9월 경기 5개(1군·2군 경기가 겹친 날)는 이 클럽 출전으로 세지 않음")
    L.append(f"골: Transfermarkt 경기 리포트 {G}골. 2002.11.17 브레멘전 61분 골은 리포트에 클로제의 자책골로 적혀 있어 빼고, 같은 경기 18분 PK 유도도 도움이 아님. "
             f"PK 골 {len(PK)}개는 0.8점: " + ", ".join(kdate(e['date']) + " " + OPP_KO[e['opp']] for e in PK))
    L.append("2010-11 이후 골 69개는 FotMob 경기 이벤트와 골 뒤 스코어·PK가 모두 같고, 분이 1~3분 다른 11개(추가시간을 FotMob이 90분으로 적은 2개 포함)는 Transfermarkt 분을 씀. FotMob 이벤트가 없는 경기: 2010.8.7 DFL-슈퍼컵 샬케전, 2011.1.29 브레멘전(Transfermarkt만 근거)")
    da = dropped_assists
    def lst(reason):
        return [d for d in da if d[5] == reason]
    pk = lst("PK 유도"); sh = lst("슈팅 리바운드"); og = lst("상대 자책골에 준 도움")
    tm_total = sum(1 for r in events if r["klose_assist"] == "1" and gbyid.get(r["gameId"], {}).get("club_id") not in RESERVE_CLUB_IDS)
    blank = sum(1 for e in E if e["type"] == "a" and e["atype"] == "")
    L.append(f"도움: 2014.8.1 이전은 Transfermarkt 경기 리포트 도움에서 아래를 뺀 것을 쓰고, 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것만 씀. 도움 {A} = Transfermarkt 리포트 {tm_total} − PK 유도 {len(pk)} − 슈팅 리바운드(Shot on goal) {len(sh)} − 상대 자책골에 준 도움 {len(og)} − 2014.8.1 이후 Transfermarkt 단일 출처 1")
    def dl(L2): return ", ".join(f"{kdate(d[1])} {d[2]}분" for d in L2)
    L.append(f"뺀 PK 유도 {len(pk)}: {dl(pk)}")
    L.append(f"뺀 슈팅 리바운드 {len(sh)}: {dl(sh)}. 뺀 상대 자책골 도움 {len(og)}: {dl(og)}")
    L.append("Transfermarkt 선수 경기 성적과 경기 리포트의 도움 수가 다른 경기 4개: 2002.11.17·2003.10.19·2006.4.1은 리포트에만 있는 PK 유도라 어느 쪽이든 뺌. 2009.3.10 스포르팅전은 리포트에 74분(판 봄멜 골, 유형 없음)과 82분(PK 유도) 두 개, 성적 표는 1개라 74분만 넣음")
    L.append(f"Transfermarkt 리포트에 도움 유형이 비어 있는 {blank}개(2000~2007년 경기와 2009.3.10·2014.11.3)는 일반 도움으로 셈. 2014.11.3 칼리아리전 7분 마우리 골은 FotMob도 클로제 도움으로 적음")
    L.append("2014.8.1 이후 뺀 Transfermarkt 단일 출처 도움 1: 2015.4.12 엠폴리전 53분 펠리프 안데르송 골(Transfermarkt 'Cross', FotMob 도움 없음, 기사들은 클로제의 낮은 크로스를 골키퍼가 쳐낸 뒤 밀어 넣은 골로 서술해 도움으로 보기 어려움)")
    L.append("FotMob에만 있는 도움 2개는 넣지 않음: 2014.12.21 인테르전 37분 펠리프 안데르송 골(기사들은 안데르송의 단독 돌파로 서술), 2015.3.1 사수올로전 77분 파롤로 골(Transfermarkt는 마우리시우의 슈팅 뒤 리바운드로, worldfootball은 카탈디 도움으로 적음)")
    L.append("2011.8.18 라보트니치키전 도움은 Transfermarkt 3개(마우리·시세·로키)를 씀. 영어 위키백과 본문은 4도움, FotMob 이벤트는 도움 0으로 서로 다름")
    L.append("연장전: 2003.2.5 보훔전(포칼 8강) 102분 도움, 2005.10.25 볼프스부르크전(포칼 2라운드) 105분 골은 연장 시간으로 계산. 승부차기 경기의 골 뒤 스코어는 연장까지의 스코어 기준")
    L.append("상대 Elo: 분데스리가 2000-01~2006-07은 다른 선수 자료와 같은 순위별 값(2025-26 기준값), 2007-08~2010-11은 다른 선수 자료의 같은 시즌 값(그 시즌 다른 순위 값과 같은 폭으로 내린 값: 2007-08 7위 1712, 2008-09 11위 1679·14위 1648, 2009-10 11위 1680), 세리에A는 순위별 고정값. 같은 경기·같은 상대를 다른 선수(리베리·뮐러) 자료가 이미 계산했으면 그 값을 씀. 2. 분데스리가 1위 1697·4위 1622·9위 1584는 다른 선수 자료의 2부 값으로 맞춘 리그 곡선 값")
    L.append("상대 Elo(추정): 독일 3부 레기오날리가 1450(부퍼탈 1998-99·브라운슈바이크 2003-04·바이에른 2군 2004-05·장크트파울리 2005-06), 같은 경기 다른 선수 자료가 있는 부르크하우젠 2007·부퍼탈 2008은 그 값 1420, 독일 4부 파로마 함부르크 2002 1300, 3부 리가 에르푸르트 2008-09 10위 1422, 빈데크 2010 1180(다른 선수 자료와 같음), "
             "보헤미안 2000 1300, 이라클리스 2000 1480, 레인저스 2000 1620, 슬라비아 프라하 2001 1500, 테플리체 2003 1400, 안더레흐트 2004 1596, 바젤 2005 1600, 츠르베나 즈베즈다 2007 1500, 브라가 2007-08 7위 1606(포르투갈 리그 곡선 값), 애버딘 2008 1500, 라보트니치키 2011 1300, 무라 2012 1300, 바사노 2014 1490(세리에C)")
    L.append("대회 비중: DFB-포칼·코파 이탈리아는 16강까지·8강·준결승·결승으로 나누고, DFB-리가포칼(시즌 전 리그컵)은 첫 경기(8강 격)·준결승·결승을 국내컵 8강·준결승·결승으로, DFL-슈퍼컵·수페르코파 이탈리아나는 국내컵 결승으로 계산함. UEFA컵 1라운드는 유로파 예선, 2라운드 이후 토너먼트는 유로파 토너먼트, 2007-08 UEFA컵 조별은 유로파 조별, 유로파 32강(2라운드)은 유로파 토너먼트")
    L.append("두 경기 합산: UEFA 대회 토너먼트·예선과 코파 이탈리아 준결승은 합산 S로 계산함(원정 다득점·2차전 연장 있음). 클로제가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움(2007.3.14 셀타 2차전, 2010.4.7 맨유 2차전, 2010.4.21 리옹 1차전, 2011.8.25 라보트니치키 2차전, 2012.2.23 아틀레티코 2차전, 2012.8.30 무라 2차전, 2013.1.22 유벤투스 1차전, 2015.8.26 레버쿠젠 2차전, 2016.3.10 스파르타 1차전)")
    L.append("시즌 구분: 카이저슬라우테른·브레멘·바이에른은 7월 10일 기준(7월 리가포칼이 새 시즌), 홈부르크·라치오는 8월 1일 기준. 클럽 구분은 1999.7.1 전 홈부르크, 2004.7.1 전 카이저슬라우테른, 2007.7.1 전 브레멘, 2011.7.1 전 바이에른, 이후 라치오")
    L.append("수상 기록은 Transfermarkt 업적 페이지 기준: 분데스리가 2회(2007-08·2009-10 바이에른), DFB-포칼 2회(2007-08·2009-10), 코파 이탈리아 2012-13(라치오), DFL-슈퍼컵 2010, DFB-리가포칼 2회(Transfermarkt 표기 2007 브레멘·2008 바이에른), 챔스 준우승 2009-10. 개인: 분데스리가 득점왕 2005-06(25골), 독일 올해의 선수 2006, 분데스리가 올해의 선수 2005-06, VDV 올해의 선수 2005-06. 월드컵 우승·득점왕 등 대표팀 기록은 뺌")
    return "\n".join(L)

# ---------------------------------------------------------------- output
def row(e):
    r = [e["type"], e["opp"], e["elo"], e["comp"], e["min"], e["gf"], e["ga"], e["ko"], e["pk"], e["date"],
         e["et"], e["dm"] or 0, e["lv"], e["note"] or 0]
    if e["tie"]:
        r.append(e["tie"])
    return r

def js(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))

if __name__ == "__main__":
    note = build_note()
    rowsE = [row(e) for e in E]
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"E": [{k: e[k] for k in ("type", "opp", "elo", "lv", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "note", "tie", "elo_src", "gid", "minute_txt", "atype")} for e in E],
                   "M": M, "dropped_assists": dropped_assists, "dropped_goals": dropped_goals}, f, ensure_ascii=False, indent=1)
    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write("const KLO_E=" + js(rowsE) + ";\n")
        f.write("const KLO_M=" + js(M) + ";\n")
        f.write("const KLO_NOTE=" + js(note) + ";\n")
    print("wrote", OUT_JS, len(rowsE), "rows,", len(M), "games")
    print(note)
