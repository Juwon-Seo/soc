#!/usr/bin/env python3
"""Mesut Özil: raw/ -> ozil.json + src/data/ozi.js (판정 근거는 judgments.md)

  python3 players/ozil/build_ozil.py            # 파일 쓰기
  python3 players/ozil/build_ozil.py --debug    # Elo 출처 로그
  python3 players/ozil/build_ozil.py --cross    # 동료 자료 대조
  python3 players/ozil/build_ozil.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/{ron,bzm,hig,kak,dim,lac,aub}.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "ozi.js")
OUT_JSON = os.path.join(HERE, "ozil.json")
ME = "메수트 외질"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트, 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

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
# 득점자 고침(Transfermarkt 리포트와 다른 출처가 다른 골): gameId|분 -> (새 득점자, 근거)
# 2009.8.20 악퇴베전 28분: TM은 피사로 골(외질 프리킥 도움), 베르더 브레멘 구단 경기 기사·RSSSF·ESPN·영어 위키백과(2009-10 유럽 2골)는 외질 골
SCORER_FIX = {
    "966510|28": ("Mesut Özil", "베르더 구단 기사·RSSSF·ESPN 경기 기록 모두 외질 골(2:1), 영어 위키백과 2009-10 유럽 대회 2골과 맞음"),
}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'·상대 자책골은 아래에서 일반 규칙으로 뺌)
EXCL_A = {
    "2698261|37": "Transfermarkt 단독(유형 빈칸). FourFourTwo·Sky Sports 등: 외질의 헤더가 마우손 맞고 흐른 공을 지루가 밀어 넣음 → 굴절·리바운드라 도움 아님",
    "2988477|12": "FotMob·경기 기사(Eurosport 등): 몬레알 헤더가 알론소·뤼디거 맞고 들어가 뤼디거 자책골로 기록됨 → 상대 자책골에 준 도움",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2549820|39": "Eurosport 'a lovely ball from Ozil' · 잉글랜드 축구협회(FA) 경기 기사 'Ozil picked out Sanchez'",
    "2549820|105+1": "AP 'took another pass from Ozil' · Reuters 'Ozil fed Sanchez down the left'",
    "3427192|90+3": "Hürriyet 'Mesut Özil'in ara pasıyla … Papiss Cisse' · Fox Sports 경기 기록 'assisted by M. Ozil'",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "ES1", "GB1", "TR1"}
CUP = {"DFB", "CDR", "FAC", "CGB", "TRP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round"): return "dk"   # FA컵 6라운드 = 8강
        return "dc"
    if cid == "LPO":   # DFB-리가포칼: 첫 경기(8강 격) dk, 준결승 dsf (클로제·리베리 선례)
        if r.startswith("semi"): return "dsf"
        if r.startswith("intermediate"): return "dk"
    if cid in ("SUC", "GBCS"): return "df"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid == "UEFA" and r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
    if cid in ("EL", "UEFA"):
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 3라운드·2라운드(32강)·intermediate stage·16강·8강
    if cid == "ECLQ": return "ecq"
    if cid == "UCOL" and r.startswith("group"): return "ecg"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local"]
    leg = 1 if "1st" in g["round"].lower() else 2
    o = INFO[TIES_RAW[gid]["other_leg_id"]]
    if (o["date_report"] < inf["date_report"]) != (leg == 2): sys.exit("차전 순서 이상 " + gid)
    home = int(inf["home_id"] == g["club_id"])
    if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    fu = ft = 0
    if leg == 2:
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "ECLQ"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid in ("CDR", "SUC"):   # 스페인 국내 대회: 원정 다득점(2018-19까지)·연장
        ag, et = int(d < "2019-07-01"), 1
    elif cid == "CGB":   # 잉글랜드 리그컵 준결승: 2017-18까지 원정 다득점·연장
        ag = et = int(d < "2018-07-01")
    else:
        sys.exit("합산 규칙 없음 " + cid)
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
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 리그 모형(기존 선수 자료의 같은 리그 값과 같은 방식)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
# 분데스리가: 2025-26 기준값에서 시즌별로 같은 폭을 뺀 값(클로제 자료와 같은 방식, 기존 시즌 값 그대로 재현)
BL_BASE = [2006, 1912, 1860, 1828, 1812, 1797, 1777, 1756, 1737, 1723, 1713, 1702, 1697, 1682, 1661, 1644, 1634, 1613]
BL_SHIFT = {"2007-08": -65.46, "2008-09": -34, "2009-10": -33}
# 2. 분데스리가: 시즌 조정 없는 고정값(기존 선수 자료 값)
L2_FIX = {1: 1697, 3: 1636, 4: 1622, 5: 1615, 6: 1609, 7: 1600, 8: 1592, 9: 1584, 10: 1579, 11: 1574, 12: 1570, 13: 1568, 14: 1561}
# 챔피언십(잉글랜드 2부) 고정값(기존 선수 자료), 리그 원(잉글랜드 3부) 기존 값 + 빠진 순위는 이웃 순위 값 사이 직선 보간
GB2_FIX = {19: 1564}
GB3_KNOWN = {4: 1539, 6: 1522, 7: 1518, 9: 1506, 14: 1477, 19: 1457, 23: 1436}
def interp(tab, r):
    if r in tab: return tab[r]
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return round(tab[lo] + (tab[hi] - tab[lo]) * (r - lo) / (hi - lo))
# 튀르키예 1부 평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 흩어짐 119 (팔카오·메르턴스 자료와 같은 계수)
TR_COEF = {2020: 3.1, 2021: 6.7, 2022: 11.8}
def tr_mean(start):
    c = sum(TR_COEF[y] for y in (start - 1, start, start + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)
DE3_MEAN, SD2 = 1428, 51.24   # 독일 3. 리가: 기존 값(2014-15 6위 1456·2017-18 2위 1513·19위 1369·2022-23 9위 1429)과 맞는 평균

def model(lg, season, r, n):
    if lg == "L1" and season in BL_SHIFT:
        return int(BL_BASE[r - 1] + BL_SHIFT[season] + 0.5), f"분데스리가 {season} {r}위"
    if lg == "L2" and r in L2_FIX:
        return L2_FIX[r], f"2. 분데스리가 {season} {r}위"
    if lg == "L3":
        return round(DE3_MEAN + SD2 * curve(r, n)), f"3. 리가 {season} {r}위"
    if lg == "GB2" and r in GB2_FIX:
        return GB2_FIX[r], f"챔피언십 {season} {r}위"
    if lg == "GB3":
        return interp(GB3_KNOWN, r), f"리그 원 {season} {r}위"
    if lg == "TR1" and season == "2021-22":
        return round(tr_mean(2021) + 119 * curve(r, n)), f"쉬페르리그 {season} {r}위"
    return None
RANK_LG = ["L1", "L2", "L3", "GB2", "GB3", "TR1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정')
MAN = {
    (key("SV Eintracht Trier 05"), "2007-08"): (1300, "독일 4부(오버리가 남서부) 2007-08 4위 (추정, 다른 선수 자료 독일 4부 1300과 같음)"),
    (key("FC Aktobe"), "2009-10"): (1350, "카자흐스탄 2009 3위 (추정, 다른 선수 자료 카이라트 2025 1위 1400보다 낮게)"),
    (key("Austria Vienna"), "2009-10"): (1556, "오스트리아 2009-10 2위 (추정, 다른 선수 자료 오스트리아 2위 1556과 같음)"),
    (key("Lincoln City"), "2016-17"): (1300, "잉글랜드 5부(내셔널리그) 2016-17 1위 (추정, 다른 선수 자료 잉글랜드 5부 1300과 같음)"),
    (key("Östersunds FK"), "2017-18"): (1450, "스웨덴 2017 6위 (추정, 다른 선수 자료 스웨덴 중상위권 1450과 같음)"),
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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]",
                        sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "ECLQ", "UCOL") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    for s in [eu, str(int(eu[:4]))]:
        for lg in RANK_LG:
            t = RANKS.get((lg, s))
            if t and k in t:
                r, n = t[k]
                res = model(lg, eu, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                    return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local"]   # Transfermarkt 리포트 날짜(유럽 현지)

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
        if r["ozil_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, 0, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["ozil_scorer"] == "1", e["ozil_assist_other"] == "1"
    if tag in SCORER_FIX:
        isg, isa = True, False
        judg.append(("득점자 고침", tag, e["scorer"], SCORER_FIX[tag][1]))
    if e["ozil_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag)); EXCL_CNT["본인 도움"] += 1
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
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            EXCL_CNT[why if tag not in EXCL_A else "개별 판정"] += 1
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - mi) <= 2]
            if not hit:
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

# 2014.8 이후 FotMob에만 있는 도움(넣지 않음) 확인
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local"] >= GAP and len(ts) > used_fm.get(gid, 0):
        FM_ONLY.append((gid, G[gid]["date_local"], ts))

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY, EXCL_CNT)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["ozil_scorer"] == "1" and e["gameId"] in G and G[e["gameId"]]["date_local"] >= "2010-08-01":
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["ozil_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Cristiano Ronaldo": ("ron.js", "RON", "2010-08-17", "2013-09-02"),
         "Karim Benzema": ("bzm.js", "BZM", "2010-08-17", "2013-09-02"),
         "Gonzalo Higuaín": ("hig.js", "HIG", "2010-08-17", "2013-09-02"),
         "Kaká": ("kak.js", "KAK", "2010-08-17", "2013-09-02"),
         "Ángel Di María": ("dim.js", "DIM", "2010-08-17", "2013-09-02"),
         "Alexandre Lacazette": ("lac.js", "LAC", "2017-07-01", "2021-01-25"),
         "Pierre-Emerick Aubameyang": ("aub.js", "AUB", "2018-01-31", "2021-01-25")}
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items()}
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
    if a[7] != b[7] or ta != tb:
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
OZ = lambda s: norm(s or "") in ("mesut ozil", "ozil")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("외질 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and OZ(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→외질 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    # Transfermarkt 외질 도움을 이 계산기에서 뺀 동료 골(참고)
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["ozil_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 외질 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    # 동료 파일에서 외질 골의 도움으로 적혔어야 할 것(TM 리포트 기준, 참고)
    for e in EVENTS:
        if e["ozil_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 외질 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("s04oz", "2008-01-31", "샬케 04", "2006~2008"), ("svwoz", "2010-08-17", "베르더 브레멘", "2008~2010"),
         ("rmaoz", "2013-09-02", "레알 마드리드", "2010~2013"), ("arsoz", "2021-01-25", "아스널", "2013~2021"),
         ("fenoz", "2022-07-14", "페네르바체", "2021~2022"), ("ibfoz", None, "이스탄불 바샥셰히르", "2022~2023")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"33": "s04oz", "86": "svwoz", "418": "rmaoz", "11": "arsoz", "36": "fenoz", "6890": "ibfoz"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["ozil_assist_other"] == "1")
N_PKW = sum(1 for e in EVENTS if e["gameId"] in G and e["ozil_assist_other"] == "1" and e["assist_type"] == "Penalty: Fouled player")
N_SOG = sum(1 for e in EVENTS if e["gameId"] in G and e["ozil_assist_other"] == "1" and e["assist_type"] == "Shot on goal" and e["own_goal"] != "1")
N_OGA = sum(1 for e in EVENTS if e["gameId"] in G and e["ozil_assist_other"] == "1" and e["own_goal"] == "1")
PK_DATES = ", ".join(d_(r[9]) + " " + {"FC Aktobe": "악퇴베", "Eintracht Frankfurt": "프랑크푸르트"}.get(r[1], r[1]) for r in E if r[8])
NOTE_LINES = [
    f"메수트 외질(샬케 04·베르더 브레멘·레알 마드리드·아스널·페네르바체·이스탄불 바샥셰히르)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 레버쿠젠전 ~ {d_(M[-1][0])} 카이세리스포르전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·독일 대표팀·유소년(로트바이스 에센 U19·샬케 U19)·샬케 2군·바샥셰히르 2군 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(출전한 {NG}경기 전부), 2010-11부터는 FotMob 경기 이벤트와 대조함(FotMob에는 샬케·브레멘 시절 경기 자료가 없고, 레알 마드리드 2010-11 13경기는 FotMob 경기 자료가 비어 있음)",
    "경기 수는 영어 위키백과 클럽·시즌별 기록과 모든 시즌에서 같음(위키백과 통산 605경기는 샬케 2군 1경기 포함). 골은 브레멘 2009-10 유럽 대회만 Transfermarkt 1골·위키백과 2골로 달랐음 — 아래 악퇴베전 골",
    f"골 고침 1개: 2009.8.20 악퇴베전(유로파 예선) 28분 2:1 골은 Transfermarkt가 피사로 골(외질 프리킥 도움)로 적었으나 베르더 브레멘 구단 경기 기사·RSSSF·ESPN이 모두 외질 골로 적어 외질 골로 넣고 그 도움은 뺌. 그래서 골은 Transfermarkt 97골보다 1개 많은 {NGo}골",
    "골: 2010-11 이후 골은 Transfermarkt와 FotMob이 수·스코어·PK 여부가 같음(FotMob 자료가 빈 경기 제외). 분은 Transfermarkt 추가시간 표기를 씀. PK 골: " + PK_DATES,
    f"도움: 2014년 8월 전은 Transfermarkt 리포트 도움(FotMob 도움 기록이 이 시기에 거의 비어 있음), 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것 + 다른 출처 2곳이 확인한 것. 도움 {NA} = Transfermarkt 리포트 {N_TM_A} − PK 유도 {N_PKW} − 'Shot on goal'(슈팅 리바운드) {N_SOG} − 상대 자책골에 준 도움 {N_OGA}(2008.12.13 볼프스부르크전 조쉬에, 2011.10.18 리옹전 요리스, 2016.11.6 토트넘전 비머) − 악퇴베전 28분(외질 골로 고침) 1 − 개별 판정 2",
    "개별 판정으로 뺀 도움 2개: 2017.1.14 스완지전 37분 지루 골(Transfermarkt 단독, 경기 기사: 외질 헤더가 수비 맞고 흐른 공을 지루가 밀어 넣음), 2018.1.24 첼시전(리그컵 준결승) 12분(Transfermarkt는 몬레알 골, FotMob·경기 기사는 뤼디거 자책골). 2009.8.8 프랑크푸르트전 13분 외질 PK 골에 Transfermarkt 리포트가 외질 본인을 도움으로 적은 것도 셈하지 않음",
    "FotMob에 없지만 다른 출처 2곳이 외질 도움으로 적어 넣은 3개: 2015.4.18 레딩전(FA컵 준결승) 39분·105+1분 알렉시스 산체스 골(Eurosport·잉글랜드 축구협회 기사, AP·로이터), 2021.5.11 시바스스포르전 90+3분 시세 골(Hürriyet·Fox Sports 경기 기록). 2014년 8월 이후 FotMob에만 있는 도움은 없음(FotMob 경기 자료는 외질의 Transfermarkt 골·도움 경기와 2017년 2월 이후 출전 경기만 받음)",
    "2014년 8월 전 도움은 Transfermarkt 한 곳 기준이라 하나하나 다른 출처와 대조하지는 않음. 2013.5.17 코파 델 레이 결승 14분 호날두 골 도움은 Transfermarkt·FotMob 모두 외질(중립 경기장이라 두 자료의 홈·원정 표기만 다름)",
    f"도움 합계 비교: Transfermarkt {N_TM_A}·튀르키예어 위키백과 220·FotMob 경력(샬케·브레멘 포함) 약 179·이 계산기 {NA}",
    "날짜는 현지 날짜(Transfermarkt 리포트 날짜, 모든 경기가 유럽)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(호날두·벤제마·이과인·카카·디 마리아·라카제트·오바메양·클로제·리베리·뮐러 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 리그 모형에 넣은 값, 직접 추정 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "리그 모형: 분데스리가 2007-08·2008-09는 다른 선수 자료와 같이 그 시즌 다른 순위 값과 같은 폭으로 내린 값, 2. 분데스리가·챔피언십은 다른 선수 자료의 순위별 값, 리그 원(잉글랜드 3부) 2013-14 18위는 다른 선수 자료의 14위·19위 값 사이 보간, 3. 리가 2010-11은 다른 선수 자료와 같은 3부 모형, 쉬페르리그 2021-22는 다른 선수 자료와 같은 튀르키예 회귀식(앞뒤 3시즌 UEFA 국가 계수 평균, 평균 약 1470)",
    "직접 추정(모두 '추정'): 트리어 2007-08(독일 4부) 1300, 악퇴베 2009(카자흐스탄 3위) 1350, 아우스트리아 빈 2009-10(오스트리아 2위) 1556, 링컨 시티 2016-17(잉글랜드 5부 1위) 1300, 외스테르순드 2017(스웨덴 6위) 1450",
    "대회 비중: DFB-포칼·코파 델 레이·FA컵·리그컵·튀르키예컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중; FA컵 6라운드는 8강), DFB-리가포칼(시즌 전 리그컵)은 첫 경기(8강 격)·준결승을 국내컵 8강·준결승으로, 수페르코파(두 경기)·커뮤니티 실드는 국내컵 결승으로 계산함. UEFA컵 1라운드는 유로파 예선, UEFA컵 3라운드 이후·유로파 32강(2라운드)은 유로파 토너먼트, 컨퍼런스리그 예선·조별은 컨퍼런스로 계산함",
    f"두 경기 합산(챔스·유로파·UEFA컵 토너먼트와 예선, 코파 델 레이 32강~준결승, 수페르코파, 리그컵 준결승) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회 2020-21까지, 스페인 국내 대회 2018-19까지, 리그컵 준결승 2017-18까지(모두 연장 있음). 외질이 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 샬케는 7월 10일 기준(2006.7.29 DFB-리가포칼 레버쿠젠전 = 2006-07), 나머지 클럽은 8월 1일 기준. 클럽 구분은 2008.1.31 전 샬케, 2010.8.17 전 브레멘(2010.8.14 DFB-포칼 로트바이스 알렌전까지), 2013.9.2 전 레알 마드리드, 2021.1.25 전 아스널, 2022.7.14 전 페네르바체, 이후 바샥셰히르. 아스널 2020-21 전반기(2020.3.7 웨스트햄전 이후)와 2020 FA컵 결승·커뮤니티 실드에는 출전 없음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 라리가 2011-12, 코파 델 레이 2010-11, 수페르코파 2012, DFB-포칼 2008-09, FA컵 4회(2014·2015·2017·2020), 커뮤니티 실드 2회(2014·2015), 준우승 UEFA컵 2008-09·DFB-포칼 2009-10·유로파리그 2018-19, 도움 1위 3회(Transfermarkt 'Best assist provider' 2009-10 브레멘·2010-11·2011-12 레알 마드리드, 대회 표기 없음). 월드컵 우승 등 대표팀·유소년 기록과 리그 준우승은 뺌",
    "은퇴(2023.3.22 발표). 마지막 경기 2023.2.2 카이세리스포르전",
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
        if b[0] < a[0] or b[1] < a[1]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const OZI_E={J(E)};\nconst OZI_M={J(M)};\nconst OZI_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
