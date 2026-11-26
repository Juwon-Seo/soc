#!/usr/bin/env python3
"""Mason Greenwood: raw/ -> greenwood.json + src/data/grw.js (판정 근거는 judgments.md)

  python3 players/greenwood/build_greenwood.py            # 파일 쓰기
  python3 players/greenwood/build_greenwood.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/greenwood/build_greenwood.py --cross    # 동료 자료 대조
  python3 players/greenwood/build_greenwood.py --fm       # FotMob 골 대조
  python3 players/greenwood/build_greenwood.py --root=<스크래치 복사본>   # 그 복사본의 src/data·elo 사용(검증용)

래시포드(build_rashford.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트),
raw/ranks.txt(순위표), <root>/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
src/data/{ras,brf,cav,ron,sch,aub}.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "grw.js")
OUT_JSON = os.path.join(HERE, "greenwood.json")
ME = "메이슨 그린우드"
GAP = "2014-08-01"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
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
MIN_FIX = {}   # 출전 분 고침 없음
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음, PK 유도·'Shot on goal'·자책골은 일반 규칙): gameId|분 -> 이유
EXCL_A = {
    "3252507|33": "2019.11.7 파르티잔전 33분 마르시알 골: 상대 수비 걷어내기를 그린우드가 몸으로 막아 튄 공을 마르시알이 잡아 넣음(Sky Sports·NBC Sports·FourFourTwo 경기 기사) — 굴절·흘러나온 공이라 도움 아님. FotMob 경기 이벤트도 도움 없음(FotMob 선수 경기 목록만 1)",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처로 확인해 넣은 도움
ADD_CONFIRMED = {
    "4788532|55": "FotMob 선수 경기 목록 도움 2(이 경기 FotMob 경기 이벤트는 9골 모두 도움 칸이 비어 있음) · Sky Sports 경기 기록('Assisted by Mason Greenwood with a cross') · Goal.com·maxifoot 경기 기사(그린우드 해트트릭·2도움)",
    "4788532|80": "FotMob 선수 경기 목록 도움 2 · Sky Sports 경기 기록('Assisted by Mason Greenwood with a cross following a corner') · maxifoot 경기 기사(그린우드 코너킥을 에간라일리가 머리로)",
}
FM_ONLY_DECIDED = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "ES1", "FR1", "TR1"}
CUP = {"FAC", "CGB", "CDR", "FRC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth") or r.startswith("6th"): return "dk"
        return "dc"   # FA컵 3~5라운드·리그컵 3·4라운드·코파 델 레이 32강·16강
    if cid == "FRCH": return "df"   # 트로페 데 샹피옹 = 국내컵 결승 비중
    if cid == "CLQ": return "clq"   # 챔스 2차·3차 예선·플레이오프(TM 'Qualifying Round')
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 조별·리그 단계(TM 'Group Stage')
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
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
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local_computed"]
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
    if cid in ("CL", "EL"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CGB":   # 리그컵 준결승: 2017-18까지 원정 다득점·연장, 2018-19부터 둘 다 없이 승부차기
        ag = et = int(d < "2018-07-01")
    elif cid == "CLQ":   # 챔스 예선(2026-27): 원정 다득점 없음, 연장 있음
        ag, et = int(d < "2021-07-01"), 1
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
MANUAL_ALIAS = {}
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
    s = y if m >= 8 else y - 1
    if d[:7] == "2020-08": s = 2019
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 순위 고침: 리그 원 2019-20은 코로나로 경기당 승점(PPG)으로 최종 순위를 정함. Transfermarkt 표(승점 순)는 로치데일 19위,
# 공식 최종 순위(영어 위키백과 '2019–20 EFL League One' 표, EFL 출처, ranking ppgpts)는 18위. 트랜미어는 두 기준 모두 21위(강등).
RANKS[("GB3", "2019-20")][key("Rochdale AFC")] = (18, 23)
# 잉글랜드 3부: 다른 선수 자료의 순위별 값(시즌 무관, '추정' 아닌 값 중 가장 많이 쓰인 값; 래시포드 자료와 같은 표) — judgments.md 7절
GB3_KNOWN = {3: 1555, 4: 1539, 5: 1530, 6: 1522, 7: 1518, 8: 1513, 9: 1506, 10: 1498, 11: 1491, 12: 1489, 14: 1477, 15: 1473,
             16: 1469, 17: 1467, 18: 1461, 19: 1457, 20: 1450, 22: 1440, 23: 1436, 24: 1428}
GB3_KNOWN[21] = (GB3_KNOWN[20] + GB3_KNOWN[22]) // 2   # 기존 값 없음: 앞뒤 순위 값의 가운데(1445)
# 리그1(18팀): 다른 선수 자료의 순위별 값(시즌 무관, 2023-24~2026-27 모두 같은 값)
FR1_KNOWN = {1: 1955, 2: 1866, 3: 1817, 4: 1786, 5: 1771, 6: 1757, 7: 1738, 8: 1718, 9: 1700, 10: 1687,
             11: 1677, 12: 1667, 13: 1662, 14: 1647, 15: 1628, 16: 1612, 17: 1603, 18: 1582}
# 쉬페르리그 2025-26 이후(18팀): 리그 평균 1567·흩어짐 119(살라 자료의 튀르키예 회귀) 순위값 — 자네 자료(build_sane.py TR_18)와 같은 표
TR_18 = {1: 1865, 2: 1755, 3: 1695, 4: 1656, 5: 1633, 6: 1614, 7: 1595, 8: 1570, 9: 1547, 10: 1533,
         11: 1520, 12: 1509, 13: 1502, 14: 1484, 15: 1461, 16: 1445, 17: 1429, 18: 1409}
CUR = {"2026-27": " (11월 17일 현재)"}   # 진행 중 시즌: 수집일 순위
def model(lg, season, r, n):
    cur = CUR.get(season, "")
    if lg == "GB3" and r in GB3_KNOWN:
        return GB3_KNOWN[r], f"리그 원(3부) {season} {r}위" + (" (추정, 기존 20위 1450·22위 1440의 가운데)" if r == 21 else "")
    if lg == "FR1" and n == 18:
        return FR1_KNOWN[r], f"리그1 {season}{cur} {r}위"
    if lg == "TR1" and n == 18 and season >= "2025-26":
        return TR_18[r], f"쉬페르리그 {season}{cur} {r}위"
    return None
RANK_LG = ["GB3", "FR1", "TR1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정')
MAN = {
    (key("FC Astana"), "2019-20"): (1400, "카자흐스탄 2019 1위 (추정, 다른 선수 자료 아스타나 2015·2017 1위 1400과 같음)"),
    (key("AZ Alkmaar"), "2019-20"): (1735, "에레디비시 2019-20 2위 (시즌 중단·우승 팀 없음, 중단 시점 순위)"),
    (key("CF Tardienta"), "2023-24"): (1050, "스페인 6부(아라곤 지역 리그) 2023-24 (추정, 다른 선수 자료 스페인 6부 1050과 같음)"),
    (key("Football Bourg-en-Bresse Péronnas 01"), "2025-26"): (1267, "프랑스 3부(내셔널) 2025-26 15위/17팀 (추정, 다른 선수 자료 프랑스 3부 15위/17팀 1267과 같음)"),
    (key("Bayeux FC"), "2025-26"): (1050, "프랑스 6부(레지오날 1) 2025-26 (추정, 다른 선수 자료 프랑스 6부 1050과 같음)"),
    (key("SK Sturm Graz"), "2026-27"): (1472, "오스트리아 분데스리가 2026-27 (11월 17일 현재) 5위 (추정, 다른 선수 자료 오스트리아 5위 1472와 같음)"),
    (key("SK Slavia Prague"), "2026-27"): (1600, "체코 2026-27 (11월 17일 현재) 1위 (추정, 다른 선수 자료 슬라비아 프라하 1위 1600과 같음)"),
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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL", "USC") else [eu]
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
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_computed"]

M = []
for g in GAMES:
    mins = MIN_FIX[g["gameId"]][0] if g["gameId"] in MIN_FIX else int(g["playedMinutes"])
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), mins])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["greenwood_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et=0):
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
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["greenwood_scorer"] == "1", e["greenwood_assist_other"] == "1"
    if e["greenwood_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag, ldate(g))); EXCL_CNT["본인 도움"] += 1
        EXCL_LIST["본인 도움"].append((ldate(g), g["opponent"], e["minute"], e["scorer"], e["assist_type"]))
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
    et = int(ko == 1 and tie is None and "+" not in e["minute"] and mi > 90)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] != "Penalty rebound"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            k = why if tag not in EXCL_A else "개별 판정"
            EXCL_CNT[k] += 1; EXCL_LIST[k].append((d, opp, e["minute"], e["scorer"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - mi) <= 3 or abs(t - int(e["minute"].split("+")[0])) <= 3]
            if not hit:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

# FotMob 도움인데 이 계산기에 들어가지 않은 것(규칙상 제외된 'Shot on goal' 포함) — 목록만
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")):
        FM_ONLY.append((gid, G[gid]["date_local_computed"], G[gid]["opponent"], ts))

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u)
for f in FM_ONLY:
    if f[0] not in FM_ONLY_DECIDED: print("FotMob 도움 미반영:", f)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
if UNDECIDED or missing_elo:
    if "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, EXCL_CNT)
    for k, v in EXCL_LIST.items(): print(k, v)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["greenwood_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local_computed"])); continue
    fg = [r for r in FM_EV[gid] if r["greenwood_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1" and t["goal_desc"] != "Penalty rebound"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["greenwood_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local_computed"] if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P, what="E"):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + "_" + what + r"=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Marcus Rashford": ("ras.js", "RAS", "2019-03-01", "2022-07-01"),
         "Bruno Fernandes": ("brf.js", "BRF", "2020-01-30", "2022-07-01"),
         "Edinson Cavani": ("cav.js", "CAV", "2020-10-01", "2022-07-01"),
         "Cristiano Ronaldo": ("ron.js", "RON", "2021-08-27", "2022-07-01"),
         "Jadon Sancho": ("sch.js", "SCH", "2021-07-01", "2022-07-01"),
         "Pierre-Emerick Aubameyang": ("aub.js", "AUB", "2024-07-18", "2026-07-14")}
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items()}
MATE_M = {nm: load_js(v[0], v[1], "M") for nm, v in MATES.items()}
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb:
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
FK = lambda s: norm(s or "") in ("mason greenwood", "greenwood")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("그린우드 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and FK(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→그린우드 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    mm = {(m[0], key(m[1])): m for m in MATE_M[nm] if lo <= m[0] < hi}
    for m in M:
        o = mm.get((m[0], key(m[1])))
        if o and o[2] != m[2]: CROSS.append(("같은 경기 대회 코드 다름", nm, m[0], m[1], m[2], o[2]))
    for x in ent:   # Transfermarkt 그린우드 도움을 이 계산기에서 뺀 동료 골(참고)
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["greenwood_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 그린우드 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # TM 동료 도움 → 그린우드 골인데 동료 파일에 없음(참고)
        if e["greenwood_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 그린우드 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
SAME_GAME = []
for r in E:
    for x in ENTS:
        if x["date"] == r[9] and (key(x["opp"]) == key(r[1]) or _sub(key(x["opp"]), key(r[1]))):
            if x.get("comp") and x["comp"] != r[3]:
                SAME_GAME.append(("대회 다름", r[9], r[1], x["p"], x["comp"], r[3]))
            break
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
    for s in SAME_GAME: print(s)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("mungw", "2023-09-01", "맨체스터 유나이티드", "2019~2022"), ("getgw", "2024-07-18", "헤타페 (임대)", "2023~2024"),
         ("omgw", "2026-07-14", "마르세유", "2024~2026"), ("fengw", None, "페네르바체", "2026~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {"mungw": "맨체스터 유나이티드", "getgw": "헤타페", "omgw": "마르세유", "fengw": "페네르바체"}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CLUB_KO)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"985": "mungw", "3709": "getgw", "244": "omgw", "36": "fengw"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_greenwood import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["greenwood_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const GRW_E={J(E)};\nconst GRW_M={J(M)};\nconst GRW_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_assists_not_used": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
