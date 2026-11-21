#!/usr/bin/env python3
"""Shaun Wright-Phillips: raw/ -> wrightphillips.json + src/data/swp.js (판정 근거는 judgments.md)

  python3 players/wrightphillips/build_wrightphillips.py            # 파일 쓰기
  python3 players/wrightphillips/build_wrightphillips.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/wrightphillips/build_wrightphillips.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/wrightphillips/build_wrightphillips.py --fm       # FotMob 골 대조
  python3 players/wrightphillips/build_wrightphillips.py --root=<스크래치 복사본>   # 그 복사본의 src/data·elo 사용(검증용)

애슐리 영(build_ashleyyoung.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전·현지 날짜), raw/tm_events.csv(골·도움,
Transfermarkt 경기 리포트), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트, 2010-11부터),
raw/ranks.txt(순위표), <root>/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), <root>/src/data/*.js(같은 경기 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, glob, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "swp.js")
OUT_JSON = os.path.join(HERE, "wrightphillips.json")
ME = "숀 라이트필립스"
GAP = "2014-08-01"   # 이 날짜 전 도움은 Transfermarkt 단독 허용(클로제·인시녜 선례), 뒤는 TM+FotMob 또는 다른 출처 2곳

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES_ALL = rd("tm_games.csv")
# Transfermarkt가 숀에게 잘못 붙인 출전(실제로는 동생 브래들리) — judgments.md 3절
EXCL_GAMES = {"28551": "2005.3.7 볼턴전(프리미어리그) 68분 교체 투입 22분: 실제 출전자는 동생 브래들리 라이트필립스(BBC 경기 기사 선수 명단, 맨시티 팬 경기 기록 rtfract, foot-direct·StatMuse 경기 기록), 숀은 결장"}
GAMES = [g for g in GAMES_ALL if g["gameId"] not in EXCL_GAMES]
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

US_CLUBS = {"623", "33414"}   # 뉴욕 레드불스·피닉스 라이징: 달력 연도 시즌, 미국 현지 날짜

# ---------------------------------------------------------------- 판정 표
MIN_FIX = {}   # 출전 분 고침 없음(TM playedMinutes 그대로)
EXCL_A = {}    # 일반 규칙(PK 유도·'Shot on goal'·자책골) 밖의 개별 도움 제외 — 없음
# 2014.8.1 이후 FotMob 경기 이벤트가 없거나 도움이 없는데 다른 출처 2곳 이상이 확인해 넣은 도움(USL 2017: FotMob에 경기 자료 없음)
ADD_CONFIRMED = {
    "2820448|57": "피닉스 라이징 공식 경기 기사·득점 요약(Drogba (29-Shaun Wright-Phillips), 상대 실책 뒤 공을 잡아 드로그바에게 연결) · 스포르팅 캔자스시티(상대 구단) 경기 기사 득점 요약(Didier Drogba 2 (Shaun Wright-Phillips 1) 57')",
    "2823657|10": "USL 공식 경기 기사(uslsoccer.com 827295, 라이트필립스의 왼쪽 코너킥을 코르테스가 헤더) · SoccerNation 경기 기사(코너킥을 코르테스 머리에) · Sports360AZ 경기 기사(코너킥 크로스)",
    "2824420|82": "USL 공식 경기 기사(uslsoccer.com 838262, 빠른 프리킥으로 존슨에게 패스, 득점 요약 Jason Johnson (Shaun Wright-Phillips)) · 포틀랜드 팀버스(상대 구단) 경기 기사 득점 요약(Johnson (Wright-Phillips, 82))",
}
# FotMob에만 있는 도움(2014.8 전, Transfermarkt 리포트는 같은 골에 도움 없음) — Transfermarkt 기준으로 넣지 않음
FM_ONLY_DECIDED = {
    "1131572": "2012.2.1 애스턴 빌라전 12분 시세 골: FotMob만 라이트필립스 도움, Transfermarkt 리포트 도움 없음 — 2014년 전은 Transfermarkt 기준",
    "1131619": "2012.3.10 볼턴전 48분 시세 골: FotMob만 라이트필립스 도움, Transfermarkt 리포트 도움 없음 — 2014년 전은 Transfermarkt 기준",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "GB2", "EFD2", "MLS1", "USL"}
CUP = {"FAC", "CGB", "MLSP"}   # MLSP = US 오픈컵(이 두 클럽의 TM 'MLSP')

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth") or r.startswith("6th"): return "dk"
        return "dc"   # FA컵 3~5라운드(재경기 포함)·리그컵 1~4라운드·US 오픈컵 3·4라운드
    if cid == "GBCS": return "df"      # 커뮤니티 실드 = 국내컵 결승 비중
    if cid in ("UEQ", "ELQ"): return "elq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        return "elk"   # 2라운드(2003-04)·3라운드(32강)·16강·8강
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"   # 2라운드(32강)·16강
    if cid == "POUS":   # MLS컵 플레이오프: 콘퍼런스 준결승 = mlp, 콘퍼런스 결승 = mlpsf
        if r.startswith("semi"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
        return "mlp"
    if cid == "CCL":
        if r.startswith("group"): return "ccc"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def ldate(g):
    # Transfermarkt API 시각을 클럽 현지 시간으로 바꾼 날짜(수집본 date_local_computed). 시각이 없는 1999~2004 경기는 중부 유럽 날짜 = TM 리포트 날짜
    return g["date_local_computed"]

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = ldate(g)
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
    if cid in ("CL", "EL", "ELQ", "UEFA", "UEQ"):
        ag, et = 1, 1
    elif cid == "CGB":   # 리그컵 1라운드(1999)·2라운드(2000) 두 경기, 준결승: 2017-18까지 원정 다득점·연장
        ag = et = 1
    elif cid == "POUS":  # MLS 플레이오프 두 경기 라운드: 원정 다득점·연장
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
MANUAL_ALIAS = {"fc timisoara": "politehnica timisoara"}   # 같은 클럽(2010.8.26 실바 자료 표기)
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

def season_of(d, us=False):
    if us: return d[:4]
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        lg = p[0].split("#")[0]
        if p[0] == "USL#group1": continue   # 동부 콘퍼런스(피닉스 상대는 모두 서부)
        RANKS[(lg, p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 잉글랜드 2부: 다른 선수 자료의 순위별 값(시즌 무관; 래시포드·애슐리 영 표와 같음) — judgments.md 7절
GB2_KNOWN = {1: 1761, 2: 1717, 3: 1689, 4: 1669, 5: 1656, 6: 1648, 7: 1642, 8: 1635, 9: 1626, 10: 1617, 11: 1607, 12: 1600,
             13: 1594, 14: 1589, 15: 1584, 16: 1580, 17: 1578, 18: 1572, 19: 1564, 20: 1555, 21: 1547, 22: 1542, 23: 1537, 24: 1527}
GB3_KNOWN = {3: 1555, 4: 1539, 5: 1530, 6: 1522, 7: 1518, 8: 1513, 9: 1506, 10: 1498, 11: 1491, 12: 1489, 13: 1481, 14: 1477, 15: 1473,
             16: 1469, 17: 1467, 18: 1461, 19: 1457, 20: 1450, 22: 1440, 23: 1436, 24: 1428}
GB4_KNOWN = {2: 1460, 4: 1433, 6: 1406, 7: 1403, 8: 1396, 12: 1368, 13: 1367, 16: 1363, 19: 1340, 22: 1335}
LGNAME = {"GB2": "챔피언십", "EFD2": "잉글랜드 2부", "GB3": "리그 원(3부)", "ENSD": "잉글랜드 3부", "GB4": "리그 투(4부)", "USL": "USL 서부"}
# USL(미국 2부) 2017: 드록바 자료 모형(평균 1353 + 2부 흩어짐 51.24 × 순위 곡선, 서부 콘퍼런스 15팀). 4위 1386·8위 1342 등 기존 값 재현
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
def model(lg, season, r, n):
    if lg == "USL":
        return int(1353 + 51.24 * curve(r, n) + 0.5), f"USL 서부 {season} {r}위"
    t = {"GB2": GB2_KNOWN, "EFD2": GB2_KNOWN, "GB3": GB3_KNOWN, "ENSD": GB3_KNOWN, "GB4": GB4_KNOWN}.get(lg)
    if t and r in t:
        return t[r], f"{LGNAME[lg]} {season} {r}위"
    return None
RANK_LG = ["GB2", "EFD2", "GB3", "ENSD", "GB4", "USL"]

# 순위표·모형으로 안 되는 상대(직접 추정) — judgments.md 7절
MAN = {
    (key("Total Network Solutions"), "2003-04"): (1200, "웨일스 2003-04 2위 (추정, 다른 선수 자료 TNS 2004-05 1위 1200과 같음)"),
    (key("Queens Park Rangers"), "2003-04"): (1583, "잉글랜드 3부 2003-04 2위 (추정, 다른 선수 자료 1위 1611·3위 1555의 가운데, 리그 원 2016-17 2위 1583과 같음)"),
    (key("Omonia Nicosia"), "2008-09"): (1482, "키프로스 1부 2008-09 2위 (리그 수준 추정)"),
}
ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid, us):
    k = key(opp)
    s0 = season_of(d, us)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [s0]
    if cid in ("CL", "EL", "ELQ", "UEFA", "UEQ"):
        seasons += [str(int(s0[:4])), str(int(s0[:4]) + 1)]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, s0) in MAN:
        e, lv = MAN[(k, s0)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, s0))
        if t and k in t:
            r, n = t[k]
            res = model(lg, s0, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                return res
    return None

# ---------------------------------------------------------------- 출전
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
        if r["swp_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
TM_ONLY_PRE = []   # 2014.8 전 Transfermarkt 단독 도움(FotMob 이벤트가 있는 경기에서 FotMob 도움 없음)
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, us, et=0):
    res = opp_elo(opp, d, cid, us)
    if res is None:
        missing_elo.add((opp, season_of(d, us), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["swp_scorer"] == "1", e["swp_assist_other"] == "1"
    if e["swp_self_assist"] == "1":
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
    cid = g["competitionId"]; us = g["club_id"] in US_CLUBS
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = int(ko == 1 and tie is None and "+" not in e["minute"] and mi > 90)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, us, et)
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
        hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - mi) <= 3 or abs(t - int(e["minute"].split("+")[0])) <= 3]
        if d >= GAP and tag not in ADD_CONFIRMED:
            if not hit:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
        if hit: used_fm[gid] += 1
        elif d < GAP and FM_EV.get(gid) and any(r["time"] for r in FM_EV[gid]):
            TM_ONLY_PRE.append((d, opp, e["minute"], e["scorer"], e["assist_type"]))
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, us, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")):
        FM_ONLY.append((gid, ldate(G[gid]), G[gid]["opponent"], ts))

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u)
for f in FM_ONLY:
    if f[0] not in FM_ONLY_DECIDED: print("FotMob 도움 미반영:", f)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
if (UNDECIDED or missing_elo or any(f[0] not in FM_ONLY_DECIDED for f in FM_ONLY)) and "--force" not in sys.argv:
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, EXCL_CNT)
    for k, v in EXCL_LIST.items(): print(k, v)
    print("2014년 전 TM 단독:", TM_ONLY_PRE)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["swp_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, ldate(G[gid]))); continue
    fg = [r for r in FM_EV[gid] if r["swp_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["swp_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, ldate(G[gid]) if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "swp.js"): continue
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const ([A-Z0-9]+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const ([A-Z0-9]+)_M=(\[.*?\]);\n", s, re.S)
    if m: OTHERS[b] = (json.loads(m.group(2)), json.loads(mm.group(2)) if mm else [])
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
# 라이트필립스(숀). 동생 브래들리(Bradley)는 다른 사람이라 'shaun'이 있어야 함
IS_ME = lambda s: "shaun" in norm(s or "") or norm(s or "") in ("s wright phillips", "wright phillips s")
MYDATES = {m[0] for m in M}
for fn, (ent, mrows) in OTHERS.items():
    for x in ent:
        if x[9] not in MYDATES: continue
        mine_m = [m for m in M if m[0] == x[9] and (key(m[1]) == key(x[1]) or _sub(key(m[1]), key(x[1])))]
        if not mine_m: continue   # 같은 날 다른 경기
        if x[0] == "a" and IS_ME(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn + " 도움→라이트필립스 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        elif x[0] == "g":
            mine = [r for r in E if r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            tm = [e for e in EVENTS if e["swp_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if mine:
                CROSS.append(("라이트필립스 도움→" + fn + " 골", x[9], x[4], cmp_rows(mine[0], x) or "같음"))
            elif tm:
                CROSS.append(("TM 라이트필립스 도움을 이 계산기에서 뺀 " + fn + " 골(참고)", x[9], x[4], tm[0]["assist_type"]))
        if x[0] == "a" and not IS_ME(x[13]):
            mine = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            if mine:
                CROSS.append((fn + " 도움(" + str(x[13]) + ")→라이트필립스 골?", x[9], x[4], cmp_rows(mine[0], x) or "같음"))
        for r in E:   # 같은 경기 Elo·lv·대회
            if r[9] == x[9]:
                d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                if d: CROSS.append(("같은 경기 다름", fn, r[9], r[1], d))
                break
    for o in mrows:
        mine_m = [m for m in M if m[0] == o[0] and (key(m[1]) == key(o[1]) or _sub(key(m[1]), key(o[1])))]
        if mine_m and mine_m[0][2] != o[2]: CROSS.append(("같은 경기 대회 코드 다름", fn, o[0], o[1], mine_m[0][2], o[2]))
# 내 골에 대해 다른 선수 파일이 도움 행을 갖고 있는지(TM 리포트 도움자가 수록 선수인 경우)
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("mcisw", "2005-07-18"), ("chesw", "2008-08-28"), ("mcisw", "2011-08-31"), ("qprsw", "2015-07-27"),
         ("nyrsw", "2017-02-24"), ("phxsw", None)]
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
CLUB_KO = collections.OrderedDict([("mcisw", "맨체스터 시티"), ("chesw", "첼시"), ("qprsw", "퀸스 파크 레인저스"),
                                   ("nyrsw", "뉴욕 레드불스"), ("phxsw", "피닉스 라이징")])
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CLUB_KO)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TMC = {"281": "mcisw", "631": "chesw", "1039": "qprsw", "623": "nyrsw", "33414": "phxsw"}
for g in GAMES:
    if club_of(ldate(g)) != TMC[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
# 맨시티 두 시기 분리(설명용)
MCI2 = [0, 0, 0, 0]
for m in M:
    if club_of(m[0]) == "mcisw" and m[0] >= "2008-08-28": MCI2[0] += 1; MCI2[3] += m[3]
for r in E:
    if club_of(r[9]) == "mcisw" and r[9] >= "2008-08-28": MCI2[1 if r[0] == "g" else 2] += 1

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_wrightphillips import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["swp_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC, MCI2=MCI2, TM_ONLY_PRE=TM_ONLY_PRE))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const SWP_E={J(E)};\nconst SWP_M={J(M)};\nconst SWP_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_assists_not_used": FM_ONLY, "tm_only_assists_before_2014": TM_ONLY_PRE,
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("  맨시티 2기", MCI2)
