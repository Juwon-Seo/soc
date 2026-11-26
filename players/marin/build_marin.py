#!/usr/bin/env python3
"""Marko Marin (마르코 마린, Transfermarkt 35251): raw/ -> marin.json + src/data/mrn.js (판정 근거는 judgments.md)

  python3 players/marin/build_marin.py            # 파일 쓰기
  python3 players/marin/build_marin.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/marin/build_marin.py --cross    # 동료·같은 경기 자료 대조
  python3 players/marin/build_marin.py --fm       # FotMob 골 대조
  python3 players/marin/build_marin.py --root=<스크래치 복사본>   # 그 복사본의 src/data·elo 사용(검증용)

베일리 빌드(build_bailey.py, 같은 원자료 형식)를 바탕으로 함. 세르비아·2. 분데스리가 순위값은 코스티치 빌드, 그리스 회귀는 발부에나 빌드,
사우디 순위값은 기존 자료(16팀 시즌) 그대로. 판정 표는 decisions_marin.py, 설명 문장은 note_marin.py.
"""
import csv, json, os, re, sys, unicodedata, collections, subprocess, glob
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
REPO = os.path.dirname(os.path.dirname(HERE))
ROOT = REPO
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "mrn.js")
OUT_JSON = os.path.join(HERE, "marin.json")
ME = "마르코 마린"
GAP = "2014-08-01"

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
FM_MAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv")}
for g in GAMES:
    if g["date_local_tm_report"] and g["date_local_tm_report"] != g["date_local_computed"]: sys.exit("날짜 불일치 " + g["gameId"])
    if g["gameId"] in INFO and INFO[g["gameId"]]["date_report"] != g["date_local_computed"]: sys.exit("리포트 날짜 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "L2", "GB1", "ES1", "BE1", "TR1", "GR1", "SER1", "SA1", "UNG1"}
CUP = {"DFB", "FAC", "CGB", "CCB", "TRP", "GRP", "SERP", "SAKC", "UNGP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:   # 국내컵: 16강까지 dc / 8강 dk / 준결승 dsf / 결승 df (FA컵 5라운드=16강, 리그컵 3라운드, 조별리그는 dc)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "KLUB": return "cwc"
    if cid in ("CLQ",): return "clq"
    if cid == "ELQ": return "elq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        sys.exit("CL 단계 " + rnd)
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 32강(2라운드·intermediate stage)·16강·8강
    if cid in ("AFCL", "ACLQ"):   # AFC 챔스: 예선 플레이오프·조별·16강 acl, 8강 aclk
        if r.startswith("quarter"): return "aclk"
        return "acl"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g): return "leg" in g["round"].lower()
def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_rule(cid, d):
    if cid in ("CL", "CLQ", "EL", "ELQ"): return int(d < "2021-07-01"), 1
    if cid == "CGB": return 1, 1                     # 리그컵 준결승 2017-18까지 원정 다득점·연장
    if cid == "CCB": return 1, 1                     # 벨기에컵 준결승(토르강 아자르·베일리 선례)
    if cid == "GRP": return 1, 1                     # 그리스컵 두 경기 라운드(발부에나 선례)
    if cid == "SERP": return 1, 1                    # 세르비아컵 준결승 두 경기(가정)
    sys.exit("합산 규칙 없음 " + cid)

def tie_of(g):
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local_computed"]
    leg = 1 if "1st" in g["round"].lower() else 2
    o = INFO[OTHER[gid]]
    if (o["date_report"] < inf["date_report"]) != (leg == 2): sys.exit("차전 순서 이상 " + gid)
    home = int(inf["home_id"] == g["club_id"])
    if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    fu = ft = 0
    if leg == 2:
        oh, oa = map(int, o["final"].split(":")[:2])
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if OTHER[gid] in G and G[OTHER[gid]]["gameState"] == "regularly_terminated" and not G[OTHER[gid]]["result_flag_report"]:
            a, b = map(int, G[OTHER[gid]]["score_club_opp"].split("-"))
            if (a, b) != (fu, ft): sys.exit("다른 차전 스코어 불일치 " + gid)
    ag, et = tie_rule(cid, d)
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
def key(n):
    k = norm(n)
    return ALIAS.get(k, k)

exec(open(os.path.join(HERE, "decisions_marin.py"), encoding="utf-8").read())   # EXCL_A·ADD_CONFIRMED·FM_PM_OK·FM_ONLY_DECIDED·MAN·SCORE_FIX

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if ME in r["선수"].split("·"): continue
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
        if p[0] == "league" or len(p) < 5: continue
        lg = p[0]; r = int(p[2]); n = int(p[3]) if p[3] else 0
        if lg.startswith("SER1#group"):   # 세르비아 2단계 리그: 챔피언 그룹 1~8위, 강등 그룹 9~16위
            lg, r, n = "SER1", r + (8 if lg.endswith("2") else 0), 16
        RANKS[(lg, p[1].split(" ")[0])][key(p[4])] = (r, n)

# 공식 최종 순위로 고침(영어 위키백과 시즌 문서 wikitext, 2026-11-18): Transfermarkt 표와 다른 것만
FINAL_FIX = {
    # 2. 분데스리가 2007-08: 코블렌츠 승점 6 삭감(라이선스) → 베헨 8·장크트파울리 9·코블렌츠 10위
    ("L2", "2007-08"): {"SV Wehen Wiesbaden": 8, "FC St. Pauli": 9, "TuS Koblenz": 10},
    # 세르비아 2018-19: 강등 그룹 최종 순위(스파르타크 9·라드니크 10·보주도바츠 11·마치바 12·바치카 13·라드 14·디나모 브라녜 15·제문 16)
    ("SER1", "2018-19"): {"FK Spartak Subotica": 9, "FK Radnik Surdulica": 10, "FK Vozdovac": 11, "FK Macva Sabac": 12,
                          "OFK Backa": 13, "FK Rad": 14, "FK Dinamo Vranje (1947 - 2022)": 15, "FK Zemun": 16},
    # 그리스 2016-17: 이라클리스 승점 삭감 → 아스테라스 12·라리사 13·레바디아코스 14·이라클리스 15위
    ("GR1", "2016-17"): {"Asteras Tripolis": 12, "AE Larisa": 13, "Levadiakos": 14, "Iraklis Thessaloniki": 15},
}
for (lg, s), fx in FINAL_FIX.items():
    for t, r in fx.items():
        if key(t) not in RANKS[(lg, s)]: sys.exit("순위 고침 팀 없음 " + t)
        RANKS[(lg, s)][key(t)] = (r, RANKS[(lg, s)][key(t)][1])
    if sorted(v[0] for v in RANKS[(lg, s)].values()) != list(range(1, len(RANKS[(lg, s)]) + 1)): sys.exit("순위 중복 " + lg + s)

def mid(tab, r):
    if r in tab: return tab[r], False
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return int((tab[lo] + tab[hi]) / 2 + 0.5), (lo, hi)

_SA20 = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
_CV = [(v - 1739) / 91.3 for v in _SA20]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return _CV[i] + (_CV[i + 1] - _CV[i]) * t
def half_up(x): return int(x + 0.5)
SD2 = 51.24

# 2. 분데스리가: 기존 선수 자료의 순위값(시즌 무관 같은 값, 코스티치 빌드와 같은 표)
L2_KNOWN = {1: 1697, 2: 1667, 3: 1636, 4: 1622, 5: 1615, 6: 1609, 7: 1600, 8: 1592, 9: 1584, 10: 1579,
            11: 1574, 12: 1570, 13: 1568, 14: 1561, 15: 1544, 16: 1545, 17: 1541, 18: 1532}
# 세르비아 수페르리가(16팀): 코스티치 판정 순위값(1위 1520·2위 1500·4위 1450·7위 1400 고정, 3위 중간, 4위부터 순위당 50/3)
SRB1_ANCHOR = {1: 1520, 2: 1500, 4: 1450, 7: 1400}
def srb1(r):
    if r in SRB1_ANCHOR: return SRB1_ANCHOR[r]
    if r == 3: return 1475
    return int(1450 - (r - 4) * 50 / 3 + 0.5)
# 그리스 1부: 발부에나 빌드의 회귀(앞뒤 3시즌 UEFA 국가 계수 평균) + 그리스 보정 GR_K(같은 기준 값 3개로 계산)
#   계수 2015-16 5.4·2016-17 5.8·2017-18 5.2·2018-19 5.1(영어 위키백과 'Greek football clubs in European competitions' 시즌별 점수표,
#   2015·2016은 kassiesa.net method4 ccoef2016·2017과 같음)
GR_COEF = {2015: 5.4, 2016: 5.8, 2017: 5.2, 2018: 5.1, 2019: 4.9, 2020: 5.1, 2021: 8.0, 2022: 2.125, 2023: 11.4, 2024: 12.688}
def reg_mean(coefs): return 1473 + 23.33 * (sum(coefs) / len(coefs) - 7.3333)
def gr_reg(start): return reg_mean([GR_COEF[y] for y in (start - 1, start, start + 1)])
GR_ANCH = [(2019, 1, 1680), (2020, 1, 1690), (2021, 2, 1590)]
GR_K = sum(v - (gr_reg(y) + 119 * curve(r, 14)) for y, r, v in GR_ANCH) / len(GR_ANCH)
def gr_mean(season): return gr_reg(int(season[:4])) + GR_K
# 쉬페르리그 2015-16: 기존 선수 자료의 순위값(6위만 5·7위 중간)
TR15 = {1: 1773, 2: 1663, 3: 1602, 4: 1563, 5: 1543, 7: 1505, 8: 1478, 9: 1457, 10: 1442, 11: 1429, 12: 1416,
        13: 1411, 14: 1393, 15: 1369, 16: 1349, 17: 1337, 18: 1312}
# 사우디 프로리그 16팀 시즌(2018-19~2022-23): 기존 선수 자료의 순위값
SA16 = {1: 1813, 2: 1695, 3: 1629, 4: 1594, 5: 1576, 6: 1552, 7: 1525, 8: 1498, 9: 1480, 10: 1466,
        11: 1454, 12: 1443, 13: 1418, 14: 1398, 15: 1378, 16: 1352}
# 헝가리 NB I(12팀): 기존 선수 자료의 헝가리 값(1위 1560 페렌츠바로시 2020-21·2021-22, 2위 1450, 3위 1420, 5·8·9위 1380)
HU = {1: 1560, 2: 1450, 3: 1420, 5: 1380, 8: 1380, 9: 1380}

def model(lg, season, r, n):
    if lg == "L2":
        v, how = mid(L2_KNOWN, r)
        return v, f"2. 분데스리가 {season} {r}위" + (f" (추정, 다른 선수 자료 2부 {how[0]}위·{how[1]}위의 중간)" if how else "")
    if lg == "SER1":
        return srb1(r), f"세르비아 {season} {r}위/{n}팀 (추정, 다른 선수 자료 세르비아 1위 1520·2위 1500·4위 1450·7위 1400에 맞춘 순위값)"
    if lg == "GR1":
        return half_up(gr_mean(season) + 119 * curve(r, n)), f"그리스 슈퍼리그 {season} {r}위 (리그 수준 추정)"
    if lg == "GR2":
        return half_up(gr_mean(season) - 162 + SD2 * curve(r, n)), f"그리스 2부(풋볼 리그) {season} {r}위 (리그 수준 추정)"
    if lg == "TR1" and season == "2015-16":
        v, how = mid(TR15, r)
        return v, f"쉬페르리그 {season} {r}위" + (" (추정, 다른 선수 자료 5위·7위의 중간)" if how else "")
    if lg == "SA1" and n == 16:
        return SA16[r], f"사우디 프로리그 {season} {r}위"
    if lg == "UNG1" and r in HU:
        return HU[r], f"헝가리 {season} {r}위 (추정, 다른 선수 자료 헝가리 {r}위 {HU[r]}과 같음)"
    return None
RANK_LG = ["L2", "SER1", "GR1", "GR2", "TR1", "SA1", "UNG1"]

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

CONT = ("CL", "CLQ", "EL", "ELQ", "AFCL", "ACLQ", "KLUB")
def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in CONT else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, eu))
        if t and k in t:
            r, n = t[k]
            res = model(lg, eu, r, n)
            if res:
                ELO_SRC["순위표+순위값·리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g): return g["date_local_computed"]
# 같은 이름의 다른 팀과 구분(고미스 자료 표기): 사우디 알아인(UAE 알아인 FC와 다른 팀)
OPP_RENAME = {"Al-Ain SFC": "Al-Ain SFC (KSA)"}
for g in GAMES: g["opponent"] = OPP_RENAME.get(g["opponent"].strip(), g["opponent"].strip())
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
        if r["mar_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]))
def pm_assists(gid):
    p = FM_MAP.get(gid)
    return int(p["fm_assists"]) if p and p["map_source"] == "playerMatches" and p["fm_assists"] not in ("", None) else None

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
PM_USED = []
PRE_TM_ONLY = []
TM_A_ALL = []
USED = collections.Counter()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et=0):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

def ctx(e, g):
    inf = INFO[e["gameId"]]
    our_home = inf["home_id"] == g["club_id"]
    sc = SCORE_FIX.get(f"{e['gameId']}|{e['minute']}", e["score_home_away_after"])
    h, a = map(int, sc.split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    return ours, gf, ga

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["mar_scorer"] == "1", e["mar_assist_other"] == "1"
    if e["mar_self_assist"] == "1":
        judg.append(("본인 골의 본인 도움 제외", tag, ldate(g))); EXCL_CNT["본인 PK 골의 본인 도움"] += 1
    if not (isg or isa): continue
    ours, gf, ga = ctx(e, g)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = int(ko == 1 and tie is None and int(e["minute"].split("+")[0]) > 90)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if not ours or e["own_goal"] == "1":
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        TM_A_ALL.append((d, opp, e["minute"], e["scorer"], e["assist_type"], gid))
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player" or e["penalty"] == "1": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            k = why if tag not in EXCL_A else "개별 판정(2014.8 이후 단일 출처, 다른 출처 2곳 확인 못 함)"
            EXCL_CNT[k] += 1; EXCL_LIST[k].append((d, opp, e["minute"], e["scorer"], e["assist_type"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
        if d < GAP:
            if hit: used_fm[gid] += 1
            else: PRE_TM_ONLY.append((d, opp, e["minute"], e["scorer"], e["assist_type"]))
        elif tag in ADD_CONFIRMED:
            USED["ADD_CONFIRMED"] += 1
        elif hit:
            used_fm[gid] += 1
        elif tag in FM_PM_OK:
            if (pm_assists(gid) or 0) < 1: sys.exit("FotMob 선수 기록 도움 없음 " + tag)
            PM_USED.append((d, opp, e["minute"], e["scorer"])); USED["FM_PM_OK"] += 1
        else:
            UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"], "FotMob 선수 기록 도움 " + str(pm_assists(gid)))); continue
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")) + sum(1 for k in FM_PM_OK if k.startswith(gid + "|")):
        FM_ONLY.append((gid, G[gid]["date_local_computed"], ts))

for nm_, tab, n in (("ADD_CONFIRMED", ADD_CONFIRMED, USED["ADD_CONFIRMED"]), ("FM_PM_OK", FM_PM_OK, USED["FM_PM_OK"])):
    if len(tab) != n: sys.exit(f"판정 표 {nm_} 사용 수 불일치 {len(tab)} vs {n}")
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
    print("FotMob 선수 기록으로 확인한 도움", PM_USED)
    print("GR_K", GR_K, {s: round(gr_mean(s)) for s in ("2016-17", "2017-18")})
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["mar_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local_computed"])); continue
    fg = [r for r in FM_EV[gid] if r["mar_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "1")]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], t["score_home_away_after"], t["goal_desc"], f["time"], f["overloadTime"], f["newScore_home_away"], f["goalDescriptionKey"]))
for gid, evs in FM_EV.items():
    if gid in G and gid not in TMG and any(r["mar_scorer"] == "1" and r["pen_shootout_event"] != "True" for r in evs):
        FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local_computed"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
TRACKED = set(subprocess.run(["git", "-C", REPO, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(REPO, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "mrn.js") or "src/data/" + b not in TRACKED: continue
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    OTHERS[b] = json.loads(m.group(2))
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
ISK = lambda s: bool(re.search(r"\bmarin\b", norm(str(s or ""))))
def same_team(x, r): return key(x[1]) == key(r[1]) or _sub(key(x[1]), key(r[1]))
CROSS = []
for b, oe in OTHERS.items():
    for x in oe:
        if x[0] == "a" and ISK(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((b + " 도움→마린 골", x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and same_team(x, r)]
            if hit: CROSS.append(("마린 도움→" + b + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            for x in oe:
                if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x, r) and not ISK(x[13]):
                    CROSS.append(("마린 골에 다른 도움자(" + b + ")", r[9], r[4], x[13]))
            for x in oe:
                if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 1 and same_team(x, r):
                    CROSS.append(("같은 시각 동료 골(" + b + ")", r[9], r[4], x[4]))
    for (d, opp, mn, sc, ty, gid) in TM_A_ALL:
        mi = minute(mn)[0]
        mine = any(r[0] == "a" and r[9] == d and abs(r[4] - mi) <= 2 for r in E)
        for x in oe:
            if x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 2 and same_team(x, [0, opp]):
                CROSS.append(("TM 마린 도움 " + ("넣음" if mine else "뺌") + " — " + b + " 골(참고)", d, mn, sc, ty))
SAME_GAME = []
for r in E:
    for x in ENTS:
        if x["date"] == r[9] and (key(x["opp"]) == key(r[1]) or _sub(key(x["opp"]), key(r[1]))):
            if x.get("comp") and x["comp"] != r[3]: SAME_GAME.append(("대회 다름", r[9], r[1], x["p"], x["comp"], r[3]))
            if x["elo"] != r[2] or x["lv"] != r[12]: SAME_GAME.append(("Elo/lv 다름", r[9], r[1], x["p"], x["elo"], x["lv"], r[2], r[12]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s in sorted(set(SAME_GAME)): print(s)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("bmgmm", "2009-07-01", "보루시아 묀헨글라트바흐", "2006~2009", "18"), ("svwmm", "2012-07-01", "베르더 브레멘", "2009~2012", "86"),
         ("chemm", "2013-07-01", "첼시", "2012~2013", "631"), ("sevmm", "2014-08-18", "세비야", "2013~2014", "368"),
         ("fiomm", "2015-01-20", "피오렌티나", "2014", "430"), ("andmm", "2015-08-25", "안데를레흐트", "2015", "58"),
         ("trbmm", "2016-08-23", "트라브존스포르", "2015~2016", "449"), ("olymm", "2018-08-31", "올림피아코스", "2016~2018", "683"),
         ("crvmm", "2020-01-05", "츠르베나 즈베즈다", "2018~2019", "159"), ("ahlmm", "2021-02-07", "알아흘리", "2020~2021", "18487"),
         ("raemm", "2021-09-18", "알라에드", "2021", "22381"), ("fermm", None, "페렌츠바로시", "2021~2022", "279")]
def club_of(d):
    for k, u, *_ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {c[0]: c[2] for c in CLUBS}
ST = collections.OrderedDict((c[0], [0, 0, 0, 0]) for c in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TMID = {c[4]: c[0] for c in CLUBS}
for g in GAMES:
    if club_of(ldate(g)) != TMID[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_marin import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=len(TM_A_ALL), EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC, PM_USED=PM_USED, PRE=PRE_TM_ONLY,
                      GR={s: gr_mean(s) for s in ("2016-17", "2017-18")}, GR_K=GR_K))
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "TM "]:
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
mm_ = {m[0]: m for m in M}
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
    if r[2] < 900: problems.append(("Elo 이상", r))
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    if "--force" not in sys.argv: sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const MRN_E={J(E)};\nconst MRN_M={J(M)};\nconst MRN_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game_diffs": sorted(set(SAME_GAME)), "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY,
               "fotmob_playermatches_assists": PM_USED, "excluded_assists": EXCL_LIST, "pre2014_tm_only_assists": PRE_TM_ONLY,
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
