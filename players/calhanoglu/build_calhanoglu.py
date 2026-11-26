#!/usr/bin/env python3
"""Hakan Çalhanoğlu: raw/ -> calhanoglu.json + src/data/chl.js (판정 근거는 judgments.md)

  python3 players/calhanoglu/build_calhanoglu.py            # 파일 쓰기
  python3 players/calhanoglu/build_calhanoglu.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/calhanoglu/build_calhanoglu.py --cross    # 동료 자료 대조
  python3 players/calhanoglu/build_calhanoglu.py --fm       # FotMob 골 대조
  python3 players/calhanoglu/build_calhanoglu.py --root=<스크래치 복사본>   # 그 복사본의 src/data에 쓰기(검증용)

아우아르(build_aouar.py) 빌드를 바탕으로 함. 접두어 CAL은 카예혼(cal.js)이 쓰고 있어 CHL(chl.js).
입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
/home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):   # 스크래치 복사본에 쓰기(검증용)
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(os.path.dirname(os.path.dirname(HERE)), "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "chl.js")
OUT_JSON = os.path.join(HERE, "calhanoglu.json")
ME = "하칸 찰하노을루"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트, 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

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

# ---------------------------------------------------------------- 판정 표
# 출전 분 고침: gameId -> (분, 근거)  (없음: Transfermarkt 출전 분 그대로)
MIN_FIX = {}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'·자책골은 일반 규칙)
EXCL_A = {
    "2460735|26": "2014.11.29 쾰른전 26분 벨라라비 골: 찰하노을루의 직접 프리킥을 골키퍼 호른이 놓친 공을 벨라라비가 밀어 넣음(Sky Sports·Sports Mole 경기 기사) — 슈팅 리바운드라 도움 아님, FotMob 도움 없음",
    "2754222|9": "2016.9.14 CSKA 모스크바전 9분 메흐메디 골: FotMob·Vavel 경기 기사·경기 기록 사이트는 헨리크스 도움 — Transfermarkt만 찰하노을루",
    "2904757|28": "2017.8.17 슈켄디야전 28분 안드레 시우바 골: FotMob 도움 없음, 찰하노을루 크로스라는 것은 팬 블로그 1곳뿐(코리에레 델로 스포르트 문자 중계는 문전 리바운드 골로 적음)",
    "2897290|54": "2018.1.6 크로토네전 54분 보누치 골: 찰하노을루 코너킥을 골키퍼 코르다츠가 쳐낸 공이 보누치 등에 맞고 들어감(ESPN 등) — 골키퍼 터치 뒤 굴절, FotMob 도움 없음",
    "2897381|82": "2018.3.18 키에보전 82분 안드레 시우바 골: 코너킥이 수비(야로신스키)에 맞고 흐른 공을 시우바가 넣음(경기 기사) — 흐른 공, FotMob 도움 없음",
    "3098802|72": "2018.12.13 올림피아코스전 72분 사파타 골: FotMob 도움 없음, 코너킥 헤더라는 AP 기사 1곳 외에는 굴절·자책골성으로 적은 기록이 많고 찰하노을루 코너킥 확인 안 됨",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳 이상이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2618543|4": "UEFA 경기 리포트(찰하노을루가 내준 공을 메흐메디가 오른발 바깥으로 마무리) · Sky Sports 경기 기록(4분 찰하노을루 도움)",
    "2618579|19": "로이터 경기 기사(Himalayan Times 게재: 찰하노을루의 정확한 패스) · Fox Sports 경기 기사(찰하노을루가 로마 수비를 가름) · ESPN 경기 리포트(찰하노을루 스루패스)",
}
# FotMob에만 있는 도움(넣지 않음) — judgments.md 4절
FM_ONLY_DECIDED = {
    "2897185": "2017.9.10 라치오전 56분(57분) 몬톨리보 골: FotMob 이벤트는 찰하노을루 도움, Transfermarkt는 'Shot on goal'(슈팅이 막힌 뒤 리바운드 골) — 리바운드라 넣지 않음",
    "2897540": "2018.5.20 피오렌티나전 76분 보나벤투라 골(5:1): FotMob·StatMuse·Sports Mole(같은 Opta 계열 자료)만 찰하노을루 도움, Transfermarkt 도움 없음, 경기 기사(calciodangolo)는 도움 2개(쿠트로네 두 골)로 적음 → 넣지 않음",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "L2", "L3", "IT1", "L1PO", "L2PO"}   # 승강 플레이오프는 리그 비중(docs 3절)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("DFB", "CIT"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 1·2라운드·16강
    if cid == "SCI":   # 수페르코파 이탈리아나: 결승 df, 4팀 준결승(2023-24~) dsf
        return "df" if r.startswith("final") else "dsf"
    if cid == "CLQ": return "clq"
    if cid == "ELQ": return "elq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # intermediate stage(32강)·16강·8강
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
    if cid in ("CL", "EL", "CLQ", "ELQ"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CIT":   # 코파 이탈리아 준결승: 원정 다득점 2021-22까지, 2차전 연장(2019-20 재개 경기만 연장 없이 승부차기)
        ag = int(d < "2022-07-01"); et = 0 if "2020-02-01" <= d < "2020-07-01" else 1
    elif cid in ("L1PO", "L2PO"):   # 승강 플레이오프: 원정 다득점·연장
        ag, et = 1, 1
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
    s = y if m >= 7 else y - 1
    if d[:7] in ("2020-07", "2020-08"): s = 2019   # 코로나로 늦게 끝난 2019-20 시즌
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

def mid(tab, r):
    """기존 순위값에 없는 순위는 앞뒤 기존 값의 단순 중간값(병렬 판정과 맞추기 위한 규칙)"""
    if r in tab: return tab[r], False
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return int((tab[lo] + tab[hi]) / 2 + 0.5), (lo, hi)

# 2. 분데스리가: 기존 선수 자료의 순위값(시즌 무관 같은 값)
L2_KNOWN = {1: 1697, 2: 1667, 3: 1636, 4: 1622, 5: 1615, 6: 1609, 7: 1600, 8: 1592, 9: 1584, 10: 1579,
            11: 1574, 12: 1570, 13: 1568, 14: 1561, 15: 1544, 16: 1545, 17: 1541, 18: 1532}
# 3. 리가: 기존 선수 자료의 순위값(시즌 무관; 8위는 1437(2010-11·2021-22·2023-24)과 1439(2014-15)가 있어 1437)
L3_KNOWN = {1: 1557, 2: 1513, 4: 1479, 5: 1462, 6: 1456, 7: 1448, 8: 1437, 9: 1429, 10: 1422, 11: 1418,
            12: 1414, 13: 1409, 14: 1406, 15: 1403, 17: 1379, 18: 1374, 19: 1369}
# 세리에A 20팀: 기존 순위값(시즌 무관 같은 값)
_SA20 = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
NOW = "(11월 17일 현재)"

def bl_known(season):
    """분데스리가 그 시즌 순위값: 기존 선수 자료 lv '분데스리가 <시즌> N위'"""
    t = {}
    for x in ENTS:
        m = re.fullmatch(r"분데스리가 " + season + r" (\d+)위", x["lv"])
        if m: t.setdefault(int(m.group(1)), collections.Counter())[x["elo"]] += 1
    return {k: v.most_common(1)[0][0] for k, v in t.items()}

def model(lg, season, r, n):
    if lg == "L2":
        v, how = mid(L2_KNOWN, r)
        return v, f"2. 분데스리가 {season} {r}위" + (f" (추정, 다른 선수 자료 2부 {how[0]}위 {L2_KNOWN[how[0]]}·{how[1]}위 {L2_KNOWN[how[1]]}의 중간)" if how else "")
    if lg == "L3":
        if r == 20:   # 기존 값 범위 밖: 19위 1369에서 18→19위 차이(5)만큼 낮춤
            return 1364, f"3. 리가 {season} 20위 (추정, 다른 선수 자료 3. 리가 19위 1369보다 18·19위 차이만큼 낮게)"
        v, how = mid(L3_KNOWN, r)
        return v, f"3. 리가 {season} {r}위" + (f" (추정, 다른 선수 자료 3. 리가 {how[0]}위 {L3_KNOWN[how[0]]}·{how[1]}위 {L3_KNOWN[how[1]]}의 중간)" if how else "")
    if lg == "L1":
        t = bl_known(season)
        v, how = mid(t, r)
        return v, f"분데스리가 {season} {r}위" + (f" (추정, 다른 선수 자료 {how[0]}위 {t[how[0]]}·{how[1]}위 {t[how[1]]}의 중간)" if how else "")
    if lg == "IT1":
        cur = " " + NOW if season == "2026-27" else ""
        return _SA20[r - 1], f"세리에A {season}{cur} {r}위"
    if lg == "PO1":   # 포르투갈 1부 18팀: 다른 선수 자료의 순위값(2016-17~2024-25 같은 값)
        return {16: 1461}[r], f"포르투갈 1부 {season} {r}위"
    if lg == "RLN4":
        return 1300, f"독일 4부(레기오날리가 북동부) {season} {r}위 (추정, 다른 선수 자료 독일 4부 1300과 같음)"
    if lg == "RLW3":
        return 1300, f"독일 4부(레기오날리가 서부) {season} {r}위 (추정, 다른 선수 자료 독일 4부 1300과 같음)"
    return None
RANK_LG = ["L2", "L3", "L1", "IT1", "PO1", "RLN4", "RLW3"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정') — judgments.md 7절
MAN = {
    (key("Austria Vienna"), "2017-18"): (1480, "오스트리아 2017-18 7위/10팀 (추정, 다른 선수 자료 오스트리아 1480과 같음)"),
    (key("Ludogorets Razgrad"), "2017-18"): (1520, "불가리아 2017-18 1위 (추정, 다른 선수 자료 루도고레츠 2019-20·2020-21 1위 1520과 같음)"),
    (key("FK Bodø/Glimt"), "2020-21"): (1560, "노르웨이 2020 1위 (추정, 다른 선수 자료 보되/글림트 2022 1560과 같음)"),
    (key("Celtic FC"), "2020-21"): (1620, "스코틀랜드 2020-21 2위 (추정, 다른 선수 자료 셀틱 2019-20 1620과 같음)"),
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
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL", "CLQ", "ELQ") else [eu]
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
    return g["date_local_computed"]   # Transfermarkt 리포트 날짜(독일·이탈리아 시간)와 모두 같음

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
        if r["calha_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
PRE_GAP_TM_ONLY = []
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
    isg, isa = e["calha_scorer"] == "1", e["calha_assist_other"] == "1"
    if e["calha_self_assist"] == "1":
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
    et = int(ko == 1 and tie is None and int(e["minute"].split("+")[0]) > 90)   # 연장 골(120+2 포함), 90+x는 정규시간
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
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
        hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
        if d >= GAP and tag not in ADD_CONFIRMED:
            if not hit:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
            used_fm[gid] += 1
        elif d < GAP and not hit:
            PRE_GAP_TM_ONLY.append((d, opp, e["minute"], e["scorer"], e["assist_type"]))
        elif d < GAP:
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local_computed"] >= GAP and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")):
        FM_ONLY.append((gid, G[gid]["date_local_computed"], ts))

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
    print("2014.8 전 Transfermarkt 단독 도움", len(PRE_GAP_TM_ONLY))
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["calha_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local_computed"])); continue
    fg = [r for r in FM_EV[gid] if r["calha_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Rafael van der Vaart": ("vdv.js", "VDV", "2013-07-01", "2014-07-01"),
         "Heung-min Son": ("son.js", "SON", "2014-07-01", "2015-08-28"),
         "Karim Bellarabi": ("blr.js", "BLR", "2014-07-01", "2017-07-01"),
         "Gonzalo Higuaín": ("hig.js", "HIG", "2018-08-01", "2019-02-01"),
         "Rafael Leão": ("lea.js", "LEA", "2019-08-01", "2021-07-01"),
         "Zlatan Ibrahimović": ("ibr.js", "IBR", "2020-01-01", "2021-07-01"),
         "Edin Dzeko": ("dze.js", "DZE", "2021-08-01", "2023-07-01"),
         "Ivan Perišić": ("per.js", "PER", "2021-08-01", "2022-07-01"),
         "Lautaro Martínez": ("lau.js", "LAU", "2021-08-01", "2026-12-31")}
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
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb:
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
FK = lambda s: "calhanoglu" in norm(s or "")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("찰하노을루 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and FK(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→찰하노을루 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:   # Transfermarkt 찰하노을루 도움을 이 계산기에서 뺀 동료 골(참고)
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["calha_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 찰하노을루 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # TM 동료 도움 → 찰하노을루 골인데 동료 파일에 없음(참고)
        if e["calha_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 찰하노을루 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
# 같은 날·같은 상대 다른 선수 기록(모든 선수)과 대회·Elo·lv·합산 대조
SAME_GAME = []
for r in E:
    for x in ENTS:
        if x["date"] == r[9] and (key(x["opp"]) == key(r[1]) or _sub(key(x["opp"]), key(r[1]))):
            if x.get("comp") and x["comp"] != r[3]: SAME_GAME.append(("대회 다름", r[9], r[1], x["p"], x["comp"], r[3]))
            if x["elo"] != r[2] or x["lv"] != r[12]: SAME_GAME.append(("Elo/lv 다름", r[9], r[1], x["p"], x["elo"], x["lv"], r[2], r[12]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
    for s in sorted(set(SAME_GAME)): print(s)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("kscca", "2013-07-01", "카를스루에 SC", "2012~2013"), ("hsvca", "2014-07-01", "함부르크 SV", "2013~2014"),
         ("levca", "2017-07-01", "바이어 레버쿠젠", "2014~2017"), ("milca", "2021-07-01", "AC 밀란", "2017~2021"),
         ("intca", None, "인테르", "2021~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"48": "kscca", "41": "hsvca", "15": "levca", "5": "milca", "46": "intca"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_calhanoglu import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["calha_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC, PRE=PRE_GAP_TM_ONLY))
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
mmin = {m[0]: m[3] for m in M}
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const CHL_E={J(E)};\nconst CHL_M={J(M)};\nconst CHL_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game_diffs": sorted(set(SAME_GAME)), "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY,
               "pre_2014_tm_only_assists": PRE_GAP_TM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
