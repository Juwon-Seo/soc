#!/usr/bin/env python3
"""Gabriel Martinelli(가브리엘 마르티넬리): raw/ -> martinelli.json + src/data/mrt.js (판정 근거는 judgments.md)

  python3 players/martinelli/build_martinelli.py                    # 파일 쓰기
  python3 players/martinelli/build_martinelli.py --debug            # Elo 출처 로그·도움 제외 목록
  python3 players/martinelli/build_martinelli.py --cross            # 다른 선수 자료 대조(같은 경기·서로 도움)
  python3 players/martinelli/build_martinelli.py --fm               # FotMob 골 대조
  python3 players/martinelli/build_martinelli.py --root=<복사본> ... # 그 복사본의 src/data·elo를 씀(검증용)

외데고르(build_odegaard.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
<root>/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), <root>/src/data/*.js(같은 경기 대조).
"""
import csv, json, os, re, sys, unicodedata, collections, glob
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "mrt.js")
OUT_JSON = os.path.join(HERE, "martinelli.json")
ME = "가브리엘 마르티넬리"
GAP = "2014-08-01"   # 모든 경기가 이 뒤 → Transfermarkt 단독 도움은 다른 출처 2곳 필요

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
for g in GAMES: g["opponent"] = g["opponent"].strip()
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

# ---------------------------------------------------------------- 판정 표 (judgments.md)
MIN_FIX = {}
# 개별 도움 제외: gameId|분 -> 이유 (PK 유도·'Shot on goal'·자책골 도움은 일반 규칙)
EXCL_A = {}
# FotMob 경기 이벤트가 없거나 FotMob에 없지만 다른 출처 2곳 이상이 확인해 넣은 Transfermarkt 도움
ADD_CONFIRMED = {
    "4320134|55": "2019.1.28 상벤투전 55분 클라우지뉴 골: ESPN 경기 중계 기록('Assisted by Gabriel Martinelli') · Gazeta Esportiva 경기 기사(마르티넬리가 낮게 크로스, 알레망이 흘리고 클라우지뉴 마무리)",
    "4321257|45+2": "2019.2.3 산투스전 45+2분 모라투 골: ESPN 경기 중계 기록('Assisted by Gabriel Martinelli with a cross') · Gazeta Esportiva 경기 기사(46분 마르티넬리가 왼쪽에서 빅토르 페하스를 제치고 크로스, 모라투 마무리)",
}
# Transfermarkt에 없고 FotMob 이벤트에만 있는 도움: 다른 출처 2곳이 확인한 것만 넣음 (gameId -> (분, 득점자, 근거))
ADD_FM_ONLY = {
    "3252448": (57, "Dani Ceballos", "2019.10.3 스탕다르 리에주전 57분 세바요스 골: ESPN 경기 기사('poke in a short floated cross from Martinelli') · Bleacher Report 경기 기사('providing a chipped cross for Ceballos to flick home')"),
}
# FotMob에만 있는 도움 중 넣지 않은 것
FM_ONLY_DECIDED = {
    "4171233": "2023.11.29 랑스전 23분 사카 골: FotMob 이벤트만 마르티넬리 도움(FotMob 선수 경기 기록은 0), Transfermarkt 도움 없음 — 경기 기사(Yahoo Sport/Standard 등)는 마르티넬리 슛을 삼바가 쳐낸 리바운드를 사카가 밀어 넣음 → 규칙상 도움 아님",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "SA1"}
CUP = {"FAC", "CGB"}
PAULISTA = {"BCP1", "BCP2", "BCPF"}   # 캄페오나투 파울리스타(조별·트로페우 두 인테리오르·8강): 네이마르·호드리구 선례대로 단계 무관 국내컵 하위 라운드 비중

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in PAULISTA: return "dc"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"   # 리그컵 5라운드·FA컵 6라운드 = 8강
        return "dc"                                # FA컵 5라운드('Fifth Round'·'Round of 16')는 16강
    if cid == "GBCS": return "df"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 2024-25부터 리그 단계(TM 'Group Stage')
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "ACLE":
        if r.startswith("group"): return "acl"   # AFC 챔피언스리그 엘리트 리그 단계
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g): return "leg" in g["round"].lower()
def ko_of(g):
    if is_leg(g) or g["competitionId"] in LEAGUE or g["competitionId"] in ("BCP1", "BCP2") or g["round"].lower().startswith("group"): return 0
    return 1

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
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "EL"): ag, et = int(d < "2021-07-01"), 1
    elif cid == "CGB": ag, et = (1, 1) if d < "2018-07-01" else (0, 0)   # 리그컵 준결승 2018-19부터 승부차기
    elif cid == "BCPF": ag, et = 0, 0                                      # 파울리스타 토너먼트: 원정 다득점·연장 없이 승부차기
    else: sys.exit("합산 규칙 없음 " + cid)
    return [leg, home, fu, ft, ag, et]

# ---------------------------------------------------------------- 이름·Elo
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n); n = re.sub(r"[^a-z0-9 ]", " ", n)
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
    y, m = int(d[:4]), int(d[5:7]); s = y if m >= 8 else y - 1
    if d[:7] in ("2020-07", "2020-08"): s = 2019   # 코로나로 늦게 끝난 2019-20 시즌
    return f"{s}-{str(s + 1)[2:]}"
def season_of(g):   # 이투아누(브라질) 경기는 달력 연도
    return g["date_local_computed"][:4] if g["club_id"] == "4773" else season_eu(g["date_local_computed"])

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league" or p[0].startswith("INVALID") or not p[2].isdigit(): continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 순위별 값: 모두 기존 선수 자료의 값(judgments.md 7절). 빈 순위는 이웃 기존 순위값의 단순 중간.
BRA1_KNOWN = {1: 1757, 2: 1702, 3: 1671, 4: 1650, 5: 1639, 6: 1631, 7: 1622, 8: 1611, 9: 1599, 10: 1588,
              11: 1581, 12: 1575, 13: 1569, 14: 1566, 15: 1559, 16: 1549, 17: 1537, 18: 1530, 19: 1524, 20: 1512}
BRA2_KNOWN = {1: 1499, 3: 1429, 5: 1403, 6: 1397, 7: 1390, 8: 1380, 9: 1371, 10: 1362, 11: 1356, 12: 1351, 13: 1346,
              15: 1338, 16: 1330, 17: 1321, 18: 1314, 19: 1310, 20: 1300}
GB2_KNOWN = {1: 1761, 2: 1717, 3: 1689, 4: 1669, 5: 1656, 6: 1648, 7: 1642, 8: 1635, 9: 1626, 10: 1617, 11: 1607, 12: 1600,
             13: 1594, 14: 1589, 15: 1584, 16: 1580, 17: 1578, 18: 1572, 19: 1564, 20: 1555, 21: 1547, 22: 1542, 23: 1537, 24: 1527}
GB3_KNOWN = {1: 1611, 2: 1583, 3: 1555, 4: 1537, 5: 1530, 6: 1522, 7: 1518, 8: 1513, 9: 1506, 10: 1498, 11: 1491, 12: 1489,
             13: 1481, 14: 1477, 15: 1473, 16: 1469, 17: 1467, 18: 1461, 19: 1457, 20: 1450, 21: 1445, 22: 1440, 23: 1436, 24: 1428}
SA1_KNOWN = {1: 1813, 2: 1703, 3: 1641, 4: 1604, 5: 1585, 6: 1568, 7: 1544, 8: 1519, 9: 1497, 10: 1481, 11: 1469, 12: 1456,
             13: 1450, 14: 1432, 15: 1408, 16: 1389, 17: 1377, 18: 1352}
NOW = "(11월 중순 현재)"
def model(lg, season, r, n):
    if lg == "BRA1": return BRA1_KNOWN[r], f"브라질 세리에 A {season} {r}위"
    if lg == "BRA2": return BRA2_KNOWN[r], f"브라질 세리에 B {season} {r}위"
    if lg == "GB2": return GB2_KNOWN[r], f"챔피언십 {season} {r}위"
    if lg == "GB3": return GB3_KNOWN[r], f"리그 원 {season} {r}위"
    if lg == "SA1" and season == "2026-27": return SA1_KNOWN[r], f"사우디 프로리그 2026-27 {NOW} {r}위"
    return None
RANK_LG = ["BRA1", "BRA2", "GB2", "GB3", "SA1"]

MAN = {
    (key("Red Bull Brasil (SP)"), "2019"): (1200, "브라질 4부 이하 2019 (추정, 파울리스타 팀, 세리에 A~D 참가 팀 아님; 다른 선수 자료 4부 이하 1200과 같음)"),
}
ELO_SRC = collections.Counter(); ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid, season):
    k = key(opp)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [season, str(int(season[:4])), str(int(season[:4]) + 1)] if cid in ("CL", "EL") else [season]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, season) in MAN:
        e, lv = MAN[(k, season)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, season))
        if t and k in t:
            res = model(lg, season, *t[k])
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g): return g["date_local_computed"]
M = []
for g in GAMES:
    mins = MIN_FIX[g["gameId"]][0] if g["gameId"] in MIN_FIX else int(g["playedMinutes"])
    M.append([ldate(g), g["opponent"], comp_of(g["competitionId"], g["round"]), mins])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["martinelli_assist"] == "1": FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set(); used_fm = collections.Counter()
EXCL_CNT = collections.Counter(); EXCL_LIST = collections.defaultdict(list); UNDECIDED = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, g, et=0):
    d = ldate(g); opp = g["opponent"]
    res = opp_elo(opp, d, g["competitionId"], season_of(g))
    if res is None: missing_elo.add((opp, season_of(g), g["competitionId"])); res = (0, "?")
    row = [typ, opp, res[0], comp, mi, gf, ga, ko, pk, d, et, dm, res[1], note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["martinelli_scorer"] == "1", e["martinelli_assist_other"] == "1"
    if e["martinelli_self_assist"] == "1":
        EXCL_CNT["본인 도움"] += 1; EXCL_LIST["본인 도움"].append((ldate(g), g["opponent"], e["minute"]))
    if not (isg or isa): continue
    inf = INFO[gid]; our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]; comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = int(ko == 1 and tie is None and "+" not in e["minute"] and mi > 90)
    d = ldate(g); opp = g["opponent"]
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, g, et)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = "개별 판정"
        if why:
            EXCL_CNT[why] += 1; EXCL_LIST[why].append((d, opp, e["minute"], e["scorer"], e["assist_type"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why, EXCL_A.get(tag, ""))); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
            if not hit:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, g, et)

# FotMob에만 있는 도움 중 다른 출처 2곳으로 확인한 것(ADD_FM_ONLY): 분·스코어는 FotMob 이벤트
for gid, (t, scorer, why) in ADD_FM_ONLY.items():
    g = G[gid]; ev = [r for r in FM_EV[gid] if r["martinelli_assist"] == "1" and int(r["time"]) == t]
    if len(ev) != 1: sys.exit("FotMob 도움 이벤트 없음 " + gid)
    r = ev[0]; nh, na = map(int, r["newScore_home_away"].split("-"))
    inf = INFO[gid]; our_home = inf["home_id"] == g["club_id"]
    if r["isHome"] == "True": nh -= 1
    else: na -= 1
    gf, ga = (nh, na) if our_home else (na, nh)
    add_row("a", t, 0, gf, ga, 0, scorer, tie_of(g), comp_of(g["competitionId"], g["round"]), ko_of(g), g)
    used_fm[gid] += 1

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local_computed"] >= GAP:
        n_used = used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|"))
        n_excl = sum(1 for k in EXCL_A if k.startswith(gid + "|"))
        n_tm_excl = sum(1 for e in EVENTS if e["gameId"] == gid and e["martinelli_assist_other"] == "1" and e["assist_type"] in ("Shot on goal", "Penalty: Fouled player"))
        if len(ts) > n_used + n_excl + n_tm_excl:
            FM_ONLY.append((gid, G[gid]["date_local_computed"], ts))
bad = False
for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u); bad = True
for f in FM_ONLY:
    if f[0] not in FM_ONLY_DECIDED: print("판정 필요(FotMob 단독 도움):", f); bad = True
for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x); bad = True
if bad and "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4], 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY, EXCL_CNT)
    for k, v in EXCL_LIST.items(): print(k, v)
    seen = set()
    for x in ELO_LOG:
        kk = (x[1], x[2], x[3], x[4][:5])
        if kk in seen: continue
        seen.add(kk); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["martinelli_scorer"] == "1" and e["gameId"] in G: TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if G[gid]["club_id"] == "4773": continue   # 이투아누 경기는 FotMob 경기 자료 없음
    fg = [r for r in FM_EV.get(gid, []) if r["martinelli_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == int(t["minute"].split("+")[0])):
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], tpk, f["time"], f["overloadTime"], fpk))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 다른 선수 자료 대조(다른 파일은 고치지 않음)
def load_all():
    out = {}
    import subprocess   # git이 관리하는 파일만(병렬로 만들어지는 다른 새 선수 파일은 보지 않음)
    tracked = set(subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
    for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
        if os.path.relpath(fn, ROOT) not in tracked: continue
        if os.path.basename(fn) in ("hon.js", "mrt.js"): continue
        s = open(fn, encoding="utf-8").read()
        m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
        if m: out[os.path.basename(fn)] = json.loads(m.group(2))
    return out
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
ISME = lambda s: "gabriel martinelli" in norm(s or "")
CROSS = []
if "--cross" in sys.argv or (__name__ == "__main__" and len(sys.argv) == 1):
    ALLF = load_all()
    for fn, ent in ALLF.items():
        for x in ent:   # 다른 선수 도움 → 마르티넬리 골
            if x[0] == "a" and ISME(x[13]):
                hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3]
                CROSS.append((fn + " 도움→마르티넬리 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        for r in E:   # 같은 날 같은 상대 기록(같은 경기)
            same = [x for x in ent if x[9] == r[9] and (key(x[1]) == key(r[1]) or _sub(key(x[1]), key(r[1])))]
            if not same: continue
            x = same[0]
            d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
            CROSS.append(("같은 경기", fn, r[9], r[1], r[0], r[4], d or "같음"))
            if r[0] == "a":   # 마르티넬리 도움 → 그 선수 골
                g2 = [x for x in same if x[0] == "g" and abs(x[4] - r[4]) <= 2]
                if g2: CROSS.append(("마르티넬리 도움→" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, g2[0]) or "같음"))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("itugm", "2019-07-02", "이투아누", "2018~2019"), ("arsgm", "2026-09-03", "아스널", "2019~2026"),
         ("hilgm", None, "알힐랄", "2026~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TMC = {"4773": "itugm", "11": "arsgm", "1114": "hilgm"}
for g in GAMES:
    if club_of(ldate(g)) != TMC[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_martinelli import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E); MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["martinelli_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC))
for badw in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM "]:
    if re.search(r"(?<![A-Za-z])" + re.escape(badw) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + badw)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []; seen = set()
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const MRT_E={J(E)};\nconst MRT_M={J(M)};\nconst MRT_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
