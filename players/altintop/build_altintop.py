#!/usr/bin/env python3
"""Hamit Altıntop: raw/ -> altintop.json + src/data/alt.js (판정 근거는 judgments.md)

  python3 players/altintop/build_altintop.py            # 파일 쓰기
  python3 players/altintop/build_altintop.py --debug    # Elo 출처 로그
  python3 players/altintop/build_altintop.py --cross    # 동료 자료 대조
  python3 players/altintop/build_altintop.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료; ents.json은 `npm run elo`로 만듦),
      src/data/{rib,klo,mul,rob,gom,pod,ozi,ron,bzm,hig,kak,dim,cal,sne,dro}.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "alt.js")
OUT_JSON = os.path.join(HERE, "altintop.json")
ME = "하미트 알틴톱"
GAP = "2014-08-01"   # 도움 출처 기준일(이 선수의 도움은 모두 2013.8 이전이라 Transfermarkt 리포트 기준)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 범위
# SG 바텐샤이트 09(Transfermarkt 클럽 97) 2000-01~2002-03: 레기오날리가 노르트(당시 독일 3부, 프로 리그 아님) → 리그 75경기 12골 0도움 전부 제외(사용자 프로 리그 기준).
# 샬케 2군(2003.11.2 레기오날리가 노르트)·바이에른 2군(2008.12.6 3. 리가)은 2군이라 제외(tm_games.csv에 없음, youth_reserve_games.csv).
EXCL_CLUB = {"97": "SG 바텐샤이트 09"}
ALL_GAMES = rd("tm_games.csv")
EXCLUDED = [g for g in ALL_GAMES if g["club_id"] in EXCL_CLUB]
GAMES = [g for g in ALL_GAMES if g["club_id"] not in EXCL_CLUB]
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
OTHER = {g: r["other_leg_id"] for g, r in TIES_RAW.items()}
for gid, r in INFO.items():
    if r["other_leg_id"]:
        OTHER.setdefault(gid, r["other_leg_id"]); OTHER.setdefault(r["other_leg_id"], gid)
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
# 날짜: Transfermarkt 리포트 날짜(유럽 현지). 2005.8.20 브레머하펜전(35297)은 API UTC가 8.19 22:00(현지 자정)라 리포트 날짜 8.20.
# 도움 제외: PK 유도·'Shot on goal'·상대 자책골은 아래 일반 규칙으로 뺌(개별 제외 없음)
EXCL_A = {}
ADD_CONFIRMED = {}
# PK 리바운드 골: 2008.2.14 애버딘전 55분(Transfermarkt 'Penalty rebound', API penMissed 1) → PK 골 아님(리포트 penalty=0 그대로)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "L2", "ES1", "TR1"}
CUP = {"DFB", "CDR", "TRP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 1·2·3라운드·16강·코파 델 레이 4라운드(32강)·튀르키예컵 조별
    if cid == "LPO":   # DFB-리가포칼: 첫 경기(8강 격) dk, 준결승 dsf, 결승 df (클로제·외질 선례)
        if r.startswith("semi"): return "dsf"
        if r.startswith("intermediate"): return "dk"
        if r.startswith("final"): return "df"
    if cid in ("DFL", "TRS"): return "df"   # DFL-슈퍼컵·튀르키예 슈퍼컵 = 국내컵 결승
    if cid == "UI": return "elq"            # 인터토토컵 = 유로파 예선(선례)
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA" and r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
    if cid == "UEFA":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 2라운드(2003-04)·3라운드·intermediate stage(32강)·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스·UEFA컵 조별, 튀르키예컵 조별(리그식)
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local"]
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
    if cid in ("CL", "UEFA", "UI"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CDR":   # 스페인 국내 대회: 원정 다득점(2018-19까지)·연장
        ag, et = int(d < "2019-07-01"), 1
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
# 분데스리가: 2025-26 기준값(2000-01~2006-07은 그대로, 2007-08~2009-10은 시즌 폭만큼 뺌 — 클로제·외질 자료와 같은 방식)
BL_BASE = [2006, 1912, 1860, 1828, 1812, 1797, 1777, 1756, 1737, 1723, 1713, 1702, 1697, 1682, 1661, 1644, 1634, 1613]
BL_SHIFT = {"2003-04": 0, "2004-05": 0, "2005-06": 0, "2006-07": 0, "2007-08": -65.46, "2008-09": -34, "2009-10": -33}
# 2. 분데스리가: 시즌 조정 없는 고정값(기존 선수 자료 값)
L2_FIX = {1: 1697, 3: 1636, 4: 1622, 5: 1615, 6: 1609, 7: 1600, 8: 1592, 9: 1584, 10: 1579, 11: 1574, 12: 1570, 13: 1568, 14: 1561, 15: 1544}

def model(lg, season, r, n):
    if lg == "L1" and season in BL_SHIFT:
        return int(BL_BASE[r - 1] + BL_SHIFT[season] + 0.5), f"분데스리가 {season} {r}위"
    if lg == "L2" and r in L2_FIX:
        return L2_FIX[r], f"2. 분데스리가 {season} {r}위"
    return None
RANK_LG = ["L1", "L2"]

# 순위표·모형·다른 선수 자료로 안 되는 상대(직접 추정, 모두 '추정') — 아래에서 채움
MAN = {
    (key("FC Pasching"), "2003-04"): (1475, "오스트리아 2003-04 3위 (추정, 다른 선수 자료 그라츠 2003-04 1480·오스트리아 4위 1473 사이)"),
    (key("Vardar Skopje"), "2004-05"): (1300, "북마케도니아 2004-05 (추정, 다른 선수 자료 라보트니치키 2011 1300과 같음)"),
    (key("Esbjerg fB"), "2004-05"): (1460, "덴마크 2004-05 5위 (추정, 다른 선수 자료 오덴세 2003-04 4위 1480보다 낮게)"),
    (key("Hertha BSC II"), "2004-05"): (1450, "독일 3부 레기오날리가 북부 2004-05 13위 (추정)"),
    (key("Liepajas Metalurgs"), "2004-05"): (1280, "라트비아 2004 2위 (추정, 다른 선수 자료 리투아니아 1위 카우나스 2005 1300보다 낮게)"),
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
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "UEFA", "UI") else [eu]
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
    return g["date_local"]   # Transfermarkt 리포트 날짜(유럽 현지; 리포트 없는 리그 경기는 일정 페이지 날짜)

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
        if r["altintop_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
EXCL_CNT = collections.Counter()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid, d)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, 0, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["hamit_scorer"] == "1", e["hamit_assist_other"] == "1"
    if e["hamit_self_assist"] == "1":
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
            sys.exit("2014.8 이후 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[3]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, EXCL_CNT)
    for x in ELO_LOG: print(x)
    for j in judg: print(j)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["hamit_scorer"] == "1" and e["gameId"] in G and G[e["gameId"]]["date_local"] >= "2010-08-01":
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid) or not any(r["scorer"] for r in FM_EV[gid]):
        FM_CMP.append(("FotMob 자료 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["altintop_scorer"] == "1" and r["pen_shootout_event"] != "True"]
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
BAY = ("2007-07-01", "2011-07-01"); RMA = ("2011-07-01", "2012-07-19"); GAL = ("2012-07-19", "2017-01-31"); S04 = ("2003-07-01", "2007-07-01")
MATES = {"Franck Ribéry": ("rib.js", "RIB") + BAY, "Miroslav Klose": ("klo.js", "KLO") + BAY,
         "Thomas Müller": ("mul.js", "MUL") + BAY, "Arjen Robben": ("rob.js", "ROB") + BAY,
         "Mario Gómez": ("gom.js", "GOM") + BAY, "Lukas Podolski": ("pod.js", "POD", "2007-07-01", "2017-01-31"),
         "Mesut Özil": ("ozi.js", "OZI", "2003-07-01", "2012-07-19"),
         "Cristiano Ronaldo": ("ron.js", "RON") + RMA, "Karim Benzema": ("bzm.js", "BZM") + RMA,
         "Gonzalo Higuaín": ("hig.js", "HIG") + RMA, "Kaká": ("kak.js", "KAK") + RMA,
         "Ángel Di María": ("dim.js", "DIM") + RMA, "José Callejón": ("cal.js", "CAL") + RMA,
         "Wesley Sneijder": ("sne.js", "SNE") + GAL, "Didier Drogba": ("dro.js", "DRO") + GAL}
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
HA = lambda s: norm(s or "") == norm("Hamit Altıntop")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("알틴톱 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and HA(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→알틴톱 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    for x in ent:   # Transfermarkt 알틴톱 도움을 이 계산기에서 뺀 동료 골(참고)
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["hamit_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 알틴톱 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # 동료 파일에서 알틴톱 골의 도움으로 적혔어야 할 것(TM 리포트 기준, 참고)
        if e["hamit_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 알틴톱 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
# 동료 M(출전) 대조: 같은 날 같은 상대의 대회 코드
MATE_M = {}
for nm, v in MATES.items():
    s = open(os.path.join(ROOT, "src", "data", v[0]), encoding="utf-8").read()
    MATE_M[nm] = json.loads(re.search(r"const " + v[1] + r"_M=(\[.*?\]);\n", s, re.S).group(1))
for nm, mm in MATE_M.items():
    for x in mm:
        for m in M:
            if m[0] == x[0] and key(m[1]) == key(x[1]) and m[2] != x[2]:
                CROSS.append(("같은 경기 대회 코드 다름(출전)", nm, m[0], m[1], m[2], x[2]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("s04ha", "2007-07-01", "샬케 04", "2003~2007"), ("bayha", "2011-07-01", "바이에른 뮌헨", "2007~2011"),
         ("rmaha", "2012-07-19", "레알 마드리드", "2011~2012"), ("galha", "2017-01-31", "갈라타사라이", "2012~2017"),
         ("d98ha", None, "다름슈타트 98", "2017")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"33": "s04ha", "27": "bayha", "418": "rmaha", "141": "galha", "105": "d98ha"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
N_TM_G = sum(1 for e in EVENTS if e["gameId"] in G and e["hamit_scorer"] == "1")
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["hamit_assist_other"] == "1")
N_SOG = sum(1 for e in EVENTS if e["gameId"] in G and e["hamit_assist_other"] == "1" and e["assist_type"] == "Shot on goal" and e["own_goal"] != "1")
N_OGA = sum(1 for e in EVENTS if e["gameId"] in G and e["hamit_assist_other"] == "1" and e["own_goal"] == "1")
EXG, EXGo, EXA = len(EXCLUDED), sum(int(g["goals"]) for g in EXCLUDED), sum(int(g["assists"]) for g in EXCLUDED)
NOTE_LINES = [
    f"하미트 알틴톱(샬케 04·바이에른 뮌헨·레알 마드리드·갈라타사라이·다름슈타트 98)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 다치아 키시너우전 ~ {d_(M[-1][0])} 그로이터 퓌르트전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·튀르키예 대표팀·샬케 2군·바이에른 2군·바텐샤이트(프로 리그 아님, 아래 줄) 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분("
    + ", ".join(f"{CLUB_KO[k]} {v[3]:,}분" for k, v in ST.items()) + ")",
    f"뺀 기록: SG 바텐샤이트 09(2001.3.10 작센 라이프치히전 ~ 2003.6.1 브레멘 2군전) {EXG}경기 {EXGo}골 {EXA}도움은 팀이 레기오날리가 노르트(당시 독일 3부, 프로 리그 아님)에 있던 2000-01~2002-03 시즌이라 넣지 않음(사용자 기준: 소속 팀이 공식 프로 리그에 있던 시즌만 셈). 샬케 2군 1경기(2003.11.2 레기오날리가)·바이에른 2군 1경기(2008.12.6 3. 리가)는 2군이라 넣지 않음",
    f"출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 나온 경기와 리그 밖 경기 전부). 2010-11 이후 골·도움 경기는 FotMob 경기 이벤트와 대조함(2003~2010 경기는 FotMob 경기 자료가 없음). 출전 분이 없어 90분으로 추정한 경기는 없음",
    "경기 수·골은 영어 위키백과 클럽·시즌별 기록과 같음(바이에른 109·13, 레알 마드리드 12·1, 갈라타사라이 89·4, 다름슈타트 34·1). 샬케만 위키백과 148경기 10골로, Transfermarkt에 있는 인터토토컵 2003·2004 12경기 4골이 위키백과 표에 없음(이 계산기는 넣음). 위키백과 갈라타사라이 2012-13 '기타' 칸 11경기는 같은 줄 합계(40)와 맞지 않는 오기로 보고 Transfermarkt 1경기(튀르키예 슈퍼컵)를 씀",
    "골: 2008.2.14 애버딘전(UEFA컵 32강 1차전) 55분 골은 막힌 PK의 리바운드 골이라 PK가 아님. PK 골은 2014.12.16 발초바전(튀르키예컵 조별) 1개. 2010-11 이후 골은 FotMob과 수·분이 같음(2011.2.5 쾰른전은 FotMob 자료가 비어 있음, 2010.12.11 장크트파울리전 Transfermarkt 16분·FotMob 17분, 2017.12.17 그로이터 퓌르트전은 FotMob이 90분으로만 적어 Transfermarkt 90+4분을 씀)",
    f"도움: 모두 2014년 8월 전이라 Transfermarkt 리포트 도움 기준. 도움 {NA} = Transfermarkt {N_TM_A} − 'Shot on goal'(슈팅 리바운드) {N_SOG}(2007.9.23 카를스루에전 클로제, 2009.8.29 볼프스부르크전 고메스, 2013.1.18 카슴파샤전 엘만데르) − 상대 자책골에 준 도움 {N_OGA}(2007.4.21 코트부스전 로스트, 2010.2.10 그로이터 퓌르트전 알라기). 2003~2010 도움은 Transfermarkt 한 곳 기준이라 하나하나 다른 출처와 대조하지는 않음",
    "FotMob 대조: 2010-11 이후 넣은 Transfermarkt 도움 14개 중 9개는 FotMob도 알틴톱 도움, 4개(2010.8.16 빈데크전 고메스, 2011.1.22 카이저슬라우테른전 고메스·뮐러, 2012.11.16 카라뷕스포르전 부라크 일마즈)는 FotMob 득점 이벤트에 도움 이름이 비어 있고, 1개(2011.3.12 함부르크전 뮐러)는 FotMob 경기 자료가 비어 있음(모두 2014년 8월 전 기준대로 넣음). FotMob 시즌 기록의 라리가 2011-12 도움 1개는 경기 이벤트에서 찾지 못해 넣지 않음",
    "날짜는 현지 날짜(Transfermarkt 리포트 날짜, 모든 경기가 유럽·튀르키예). 2005.8.20 브레머하펜전(DFB-포칼 1회전)은 Transfermarkt 선수 경기 성적이 8.19로 적지만 리포트·worldfootball 모두 8.20",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(리베리·클로제·뮐러·로번·고메스·포돌스키·호날두·벤제마·디 마리아·카예혼·드록바 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위를 리그 모형에 넣은 값 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 직접 추정 {SRC['직접 추정']}, 순위표+모형 {SRC['순위표+리그 모형']})",
    "리그 모형: 볼프스부르크 2003-04 분데스리가 10위 1723(다른 선수 자료와 같은 분데스리가 순위값), 그로이터 퓌르트 2017-18 2. 분데스리가 15위 1544(다른 선수 자료의 2부 15위 값)",
    "직접 추정(모두 '추정'): 파싱 2003-04(오스트리아 3위) 1475, 바르다르 스코페 2004(북마케도니아) 1300, 에스비에르 2004-05(덴마크 5위) 1460, 헤르타 2군 2004-05(독일 3부 레기오날리가 북부 13위) 1450, 리에파야스 메탈루르그스 2004(라트비아 2위) 1280",
    "대회 비중: DFB-포칼·코파 델 레이·튀르키예컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중; 튀르키예컵 조별은 무승부 1점 리그식), DFB-리가포칼(시즌 전 리그컵)은 첫 경기(8강 격)·준결승·결승을 국내컵 8강·준결승·결승으로, DFL-슈퍼컵·튀르키예 슈퍼컵은 국내컵 결승으로 계산함. 인터토토컵과 UEFA컵 1라운드는 유로파 예선, UEFA컵 2라운드(2003-04)·32강(3라운드·intermediate stage)·16강·8강은 유로파 토너먼트, UEFA컵 조별은 유로파 조별로 계산함",
    f"두 경기 합산(챔스·UEFA컵·인터토토컵 토너먼트, 코파 델 레이 32강·8강) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점·연장 있음. 알틴톱이 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "승부차기 경기(2003.11.27 브뢴뷔전, 2004.9.22 카이저슬라우테른전, 2005.4.19 브레멘전, 2006.7.29 레버쿠젠전, 2006.8.2 바이에른전, 2007.8.6 부르크하우젠전)는 골·도움이 없어 출전 분만 Transfermarkt 그대로 씀. 튀르키예 슈퍼컵 2012·2013(중립 경기장)은 Transfermarkt 선수 경기 성적과 리포트의 홈·원정 표기가 반대이나 출전 기록만 있어 영향 없음",
    "시즌 구분: 샬케·바이에른·다름슈타트는 7월 10일 기준(7월 인터토토컵·DFB-리가포칼·2017.7.29 2. 분데스리가 개막전이 새 시즌), 레알 마드리드·갈라타사라이는 8월 1일 기준. 클럽 구분은 2007.7.1 전 샬케, 2011.7.1 전 바이에른, 2012.7.19 전 레알 마드리드, 2017.1.31 전 갈라타사라이, 이후 다름슈타트. 갈라타사라이 2015-16은 출전 없음(부상)",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 분데스리가 2회(2007-08·2009-10), 라리가 2011-12, 쉬페르리그 2회(2012-13·2014-15), DFB-포칼 2회(2007-08·2009-10), 튀르키예컵 2회(2013-14·2014-15), DFB-리가포칼 2회(Transfermarkt 표기 2006 샬케 = 2005.8.2 결승, 2008 바이에른 = 2007.7.28 결승), DFL-슈퍼컵 2010, 튀르키예 슈퍼컵 3회(2012·2013·2016, 2016은 출전 없음 — Transfermarkt 그대로), 준우승 챔스 2009-10(결승 출전)·DFB-포칼 2004-05(결승 출전), 인터토토컵 2회(2003·2004 샬케). 푸스카스상 2010(대표팀 경기 골)·리그 준우승·대표팀 기록은 뺌",
    "은퇴. 마지막 경기 2017.12.17 그로이터 퓌르트전(2018.1.4 다름슈타트와 계약 해지)",
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const ALT_E={J(E)};\nconst ALT_M={J(M)};\nconst ALT_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "excluded_wattenscheid": [[g["date_local"], g["opponent"], g["playedMinutes"], g["goals"]] for g in EXCLUDED],
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
