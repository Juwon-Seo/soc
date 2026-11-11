#!/usr/bin/env python3
"""Steven Gerrard: raw/ -> gerrard.json + src/data/ger.js (판정 근거는 judgments.md)

  python3 players/gerrard/build_gerrard.py          # 쓰기
  python3 players/gerrard/build_gerrard.py --debug  # Elo 출처
  python3 players/gerrard/build_gerrard.py --fm     # FotMob 골 대조
  python3 players/gerrard/build_gerrard.py --cross  # 동료(토레스·수아레스·스털링) 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/{tor,sua,ste}.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "ger.js")
OUT_JSON = os.path.join(HERE, "gerrard.json")
ME = "스티븐 제라드"
GAP = "2014-08-01"   # 도움 출처 기준일(이전 Transfermarkt, 이후 Transfermarkt∩FotMob)
LIV, LAG = "31", "1061"

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
EXCL_G = {
    "2225498|68": "상대 자책골(FotMob·ESPN·worldfootball: 레온 바넷 자책골, 11v11: 프리미어리그 '의심 골 위원회'가 자책골로 판정. Transfermarkt만 제라드 'Deflected shot on goal')",
}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·슈팅 리바운드는 유형으로 자동 제외)
EXCL_A = {
    "991716|45+1": "상대 자책골(라이언 버트런드)",
}
AUTO_EXCL_TYPES = {"Penalty: Fouled player": "PK 유도", "Shot on goal": "슈팅 리바운드(Shot on goal)"}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {}
# FotMob에만 있는 도움(넣지 않음)
FM_ONLY = [
    "2012.12.9 웨스트햄전 11분 글렌 존슨 골(Transfermarkt 도움 없음)",
    "2014.5.5 크리스털 팰리스전 53분 수아레스 골(Transfermarkt 도움은 스터리지)",
]

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "MLS1"}
CUP = {"FAC", "CGB", "MLSP"}   # MLSP = US 오픈컵(Transfermarkt 대회 id, 그리즈만 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth"): return "dk"   # FA컵 6라운드 = 8강
        return "dc"
    if cid in ("GBCS", "USC"): return "df"
    if cid == "KLUB": return "cwc"
    if cid == "POUS":
        if r.startswith("semi") or r.startswith("conference final"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
        return "mlp"
    if cid == "CCL":
        if r.startswith("semi"): return "cccsf"
        if r.startswith("final"): return "cccf"
        if r.startswith("quarter"): return "ccck"
        return "ccc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2001-02 2차 조별(Group 2) 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid in ("UEFA", "EL"):
        if cid == "UEFA" and r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # UEFA컵 2·3라운드·16강·8강, 유로파 32강(TM 'Second Round'·'intermediate stage')·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

OTHER_LEG = {}

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]
    leg = 1 if "1st" in g["round"].lower() else 2
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[OTHER_LEG.get(gid) or TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    ag, et = 1, 1
    if cid == "CCL": et = 0          # 북중미 챔스: 원정 다득점 있고 연장 없이 승부차기
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
MANUAL_ALIAS = {
    "inter milan": "inter", "fc copenhagen": "fc kobenhavn",
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

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0].split("(")[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

def median(xs):
    xs = sorted(xs); n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

# 프리미어리그: 기존 자료 시즌별 순위값(2002-03~2014-15 완전). 빈 순위(1998-99~2001-02 일부)는 2003-04 순위별 값에
# 같은 시즌 기존 값과의 차이(중앙값)를 더함(에투 라리가와 같은 방식)
PL_BASE = ents_map("프리미어리그", "2003-04")
assert len(PL_BASE) == 20
def premier(season, r):
    m = ents_map("프리미어리그", season)
    if r in m: return m[r], False
    sh = median([v - PL_BASE[k] for k, v in m.items()])
    return int(round(PL_BASE[r] + sh)), True
# 챔피언십(24팀): 기존 자료의 고정 순위값(2004-05~2015-16 모두 같음). 6·15·19위는 기존 자료에 없어 앞뒤 순위 평균
CH = {1: 1761, 2: 1717, 3: 1689, 4: 1669, 5: 1656, 7: 1642, 8: 1635, 9: 1626, 10: 1617, 11: 1607, 12: 1600, 13: 1594,
      14: 1589, 16: 1580, 17: 1578, 18: 1572, 20: 1555, 21: 1547, 22: 1542, 23: 1537, 24: 1527}
for r in (6, 15, 19): CH[r] = int(round((CH[r - 1] + CH[r + 1]) / 2 + 0.01))
# 리그 원(24팀): 기존 자료 값(4위 1539·6위 1522·7위 1518·19위 1457·23위 1436), 빈 순위는 선형 보간(추정)
L1 = {4: 1539, 6: 1522, 7: 1518, 19: 1457, 23: 1436}
# 리그 투(24팀): 기존 자료 값(2위 1460·12위 1368), 빈 순위는 선형 보간·외삽(추정)
L2 = {2: 1460, 12: 1368}
def interp(tab, r):
    if r in tab: return tab[r], False
    ks = sorted(tab)
    lo = max([k for k in ks if k < r], default=None); hi = min([k for k in ks if k > r], default=None)
    if lo is None: lo, hi = ks[0], ks[1]
    if hi is None: lo, hi = ks[-2], ks[-1]
    return int(round(tab[lo] + (tab[hi] - tab[lo]) * (r - lo) / (hi - lo))), True
# MLS(20팀): 기존 자료 고정 순위값(2015·2016 같음; 전체 순위)
MLS = {}
for s in ("2015", "2016"):
    for r, v in ents_map("MLS", s).items(): MLS.setdefault(r, v)

def model(lg, season, r, n):
    """(Elo, lv) — 순위표 + 리그 모형"""
    if lg == "GB1":
        v, it = premier(season, r)
        return v, f"프리미어리그 {season} {r}위"
    if lg == "GB2":
        assert n == 24
        return CH[r], f"챔피언십 {season} {r}위"
    if lg == "GB3":
        v, it = interp(L1, r)
        return v, f"리그 원 {season} {r}위" + (" (추정, 다른 선수 자료 순위값 사이 보간)" if it else "")
    if lg == "GB4":
        v, it = interp(L2, r)
        return v, f"리그 투 {season} {r}위" + (" (추정, 다른 선수 자료 순위값 사이 보간)" if it else "")
    if lg == "MLS1-overall":
        return MLS[r], f"MLS {season} {r}위"
    return None

RANK_LG = ["GB1", "GB2", "GB3", "GB4", "MLS1-overall"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {}

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
    y = int(d[:4])
    if cid in ("MLS1", "POUS", "MLSP", "CCL"): seasons = [str(y)]
    elif cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "KLUB", "USC"): seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)]
    else: seasons = [eu]
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
    # 리버풀: Transfermarkt 리포트 날짜(현지). LA 갤럭시: API UTC를 미국 태평양 시간으로 바꾼 날짜(리포트 날짜는 하루 늦음)
    return g["date_local"]

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
        if r["gerrard_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))

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

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa = e["gerrard_scorer"] == "1", e["gerrard_assist_other"] == "1"
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
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout", "golden_goal") and not tie) else 0
    d = ldate(g); opp = g["opponent"].strip()
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["assist_type"] in AUTO_EXCL_TYPES:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], AUTO_EXCL_TYPES[e["assist_type"]])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if d >= GAP and tag not in ADD_CONFIRMED:
            if not any(abs(t - mi) <= 2 or abs(t - int(e["minute"].split("+")[0])) <= 2 for t in FM_ASSIST.get(gid, [])):
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows
print(len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E))
