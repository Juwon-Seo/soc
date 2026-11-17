#!/usr/bin/env python3
"""Jonathan David: raw/ -> david.json + src/data/jdv.js (판정 근거는 judgments.md)

  python3 players/david/build_david.py            # 파일 쓰기
  python3 players/david/build_david.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/david/build_david.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/david/build_david.py --fm       # FotMob 골 대조
  python3 players/david/build_david.py --root=<스크래치 복사본>   # 그 복사본의 src/data에 쓰기(검증용)

아우아르(build_aouar.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/fotmob_tm_map.csv(FotMob 선수 경기 목록),
raw/ranks.txt(순위표), /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
src/data/cab.js(레미 카벨라, 릴 2022~24 같은 경기 대조).
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
OUT_JS = os.path.join(ROOT, "src", "data", "jdv.js")
OUT_JSON = os.path.join(HERE, "david.json")
ME = "조너선 데이비드"
GAP = "2014-08-01"   # 도움 출처 기준일(이 선수는 모든 경기가 이후): Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
OTHER = {}
for r in rd("tm_two_leg_ties.csv"):
    OTHER[r["gameId"]] = r["other_leg_id"]
for gid, r in INFO.items():
    if r["other_leg_id"]:
        OTHER.setdefault(gid, r["other_leg_id"]); OTHER.setdefault(r["other_leg_id"], gid)
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)
FM_PM = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv")}   # FotMob 선수 경기 목록(경기별 골·도움 수)

# ---------------------------------------------------------------- 판정 표
# 출전 분 고침: gameId -> (분, 근거)  (없음: Transfermarkt 출전 분 그대로)
MIN_FIX = {}
# PK 여부 고침: gameId|분 -> (pk, 근거)
PK_FIX = {"4094770|49": (0, "2024.2.17 르아브르전 49분: PK가 막힌 뒤 리바운드 골(Transfermarkt 'Penalty rebound'), FotMob은 일반 골 → PK 골 아님")}
# 골 뒤 스코어 고침(리포트 순서 오류): gameId|분 -> 'h-a'
SCORE_FIX = {"4445123|45+4": "2-1", "4445123|47": "2-2"}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'은 일반 규칙)
EXCL_A = {}
# FotMob 경기 이벤트에는 도움 정보가 없지만 FotMob 선수 경기 목록(경기별 도움 수)이 Transfermarkt와 같아 넣은 도움(쿠프 드 프랑스)
ADD_FM_PM = {
    "4240656|33": "2024.1.6 골든 라이언전 33분 제그로바 골: FotMob 선수 경기 목록 도움 3 = Transfermarkt 패스 도움 3(PK 유도 1개는 별도)",
    "4240656|41": "2024.1.6 골든 라이언전 41분 제그로바 골: 위와 같음",
    "4240656|45": "2024.1.6 골든 라이언전 45분 야즈즈 골: 위와 같음",
    "4502423|22": "2024.12.20 루앙전 22분 이스마일리 골(릴의 유일한 골): FotMob 선수 경기 목록 도움 1",
    "4515303|68": "2025.1.14 마르세유전(쿠프 드 프랑스) 68분 하랄드손 골(릴의 유일한 골): FotMob 선수 경기 목록 도움 1",
}
# 2014.8.1 이후 FotMob에 없지만 다른 출처 2곳 이상이 확인해 넣은 도움
ADD_CONFIRMED = {}
# FotMob에만 있는 도움(넣지 않음) — judgments.md 4절
FM_ONLY_DECIDED = {
    "3117177": "2018.12.21 세르클러 브뤼허전(4:1): FotMob 선수 경기 목록만 데이비드 도움 1, FotMob 경기 이벤트·Transfermarkt 리포트에는 데이비드 도움 없음(헨트 골 4개의 도움자는 두 출처가 같음) → 넣지 않음",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BE1", "EJPL", "FR1", "IT1", "ES1"}
CUP = {"CCB", "FRC", "CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 16강까지(벨기에컵 6라운드=32강·쿠프 드 프랑스 5·6라운드 포함)
    if cid == "FRCH": return "df"   # 트로페 데 샹피옹(단판 슈퍼컵) = 국내컵 결승 비중
    if cid == "ELQ": return "elq"
    if cid == "CLQ": return "clq"
    if cid == "ECLQ": return "ecq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("intermediate") or r.startswith("last 16"): return "cl16"   # 녹아웃 플레이오프 = 16강
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # intermediate stage(32강)·16강·8강
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"
        if r.startswith("semi"): return "ecsf"
        if r.startswith("final"): return "ecf"
        return "eck"   # 16강·8강
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
    if cid in ("CL", "EL", "ELQ", "CLQ", "ECLQ", "UCOL"):
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
# 통합표와 이름 표기가 다른 같은 팀(Transfermarkt 표기 → 통합표 표기)
MANUAL_ALIAS = {"royal antwerp fc": "royal antwerp", "kv oostende": "oostende", "parma calcio 1913": "parma fc"}
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
# 벨기에 1부 2018-19 최종 순위 = 챔피언십 플레이오프(EJPL) 1~6위 + 정규 시즌 7~16위(데 브라위너 선례, 영어 위키백과 시즌 문서로 확인)
for k, (r, n) in RANKS[("EJPL", "2018-19")].items():
    RANKS[("BE1", "2018-19")][k] = (r, 16)
# 엑스트라클라사 2018-19: Transfermarkt 챔피언십 그룹 표는 야기엘로니아 4위·크라코비아 5위지만 공식 최종 순위(영어 위키백과)는 크라코비아 4위·야기엘로니아 5위
RANK_FIX = {(key("Jagiellonia Bialystok"), "2018-19"): ("PL1", 5, 16)}

def interp(tab, r):
    """기존 순위값 사이는 앞뒤 값의 직선 보간(빈 순위 하나면 가운데)"""
    if r in tab: return tab[r]
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return int(tab[lo] + (tab[hi] - tab[lo]) * (r - lo) / (hi - lo) + 0.5)

_SA20 = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
_CV = [(v - 1739) / 91.3 for v in _SA20]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return _CV[i] + (_CV[i + 1] - _CV[i]) * t

# 벨기에 1부: 데 브라위너 자료와 같은 국가 계수 회귀(리그 평균 = a + b × 앞뒤 3시즌 UEFA 국가 계수 평균), 흩어짐 119, 16팀 순위 곡선.
# a·b는 데 브라위너 자료의 2009-10 1440·2010-11 1484·2011-12 1467(계수 평균 5.933·7.800·7.067)에 맞춘 직선(최소제곱).
# 벨기에 시즌 계수(kassiesa.net UEFA 국가 계수 표): 2017-18 2.600, 2018-19 7.800, 2019-20 7.600, 2020-21 6.000
_BX = [(4.5 + 8.7 + 4.6) / 3, (8.7 + 4.6 + 10.1) / 3, (4.6 + 10.1 + 6.5) / 3]; _BY = [1440, 1484, 1467]
_mx, _my = sum(_BX) / 3, sum(_BY) / 3
BE_B = sum((x - _mx) * (y - _my) for x, y in zip(_BX, _BY)) / sum((x - _mx) ** 2 for x in _BX)
BE_A = _my - BE_B * _mx
BE_COEF = {2017: 2.6, 2018: 7.8, 2019: 7.6, 2020: 6.0}
def be_mean(season):
    y = int(season[:4])
    return BE_A + BE_B * (BE_COEF[y - 1] + BE_COEF[y] + BE_COEF[y + 1]) / 3

# 엑스트라클라사 2018-19: 다른 선수 자료(브와슈치코프스키)의 같은 시즌 순위값
PL1_1819 = {2: 1453, 4: 1400, 6: 1378, 10: 1332, 12: 1320}
# 리그2(프랑스 2부): 기존 선수 자료의 순위값
FR2_KNOWN = {1: 1669, 2: 1624, 4: 1582, 6: 1567, 7: 1559, 8: 1550, 10: 1532, 13: 1516, 14: 1513, 15: 1508, 17: 1490, 19: 1480}
# 프랑스 3부(나시오날): 다른 선수 자료의 순위값(2위 1350·5위 1344·9위 1304·11위 1291·17팀 중 15위 1267)
FR3_KNOWN = {2: 1350, 5: 1344, 9: 1304, 11: 1291, 15: 1267}
# 크로아티아 1부: 다른 선수 자료의 순위값(1위 1610~1620, 3위 1460) — 2위는 그 가운데
HR_KNOWN = {1: 1610, 3: 1460}
# 오스트리아 2023-24: 다른 선수 자료(잘츠부르크 2위 1604·LASK 3위 1539)와 같은 리그 모형(평균 약 1450, 흩어짐 119, 12팀)
AT_2324 = 1604 - 119 * curve(2, 12)

def model(lg, season, r, n):
    if lg == "BE1" and season in ("2018-19", "2019-20"):
        return int(be_mean(season) + 119 * curve(r, n) + 0.5), f"벨기에 1부 {season} {r}위 (리그 모형값)"
    if lg == "PL1" and season == "2018-19":
        return interp(PL1_1819, r), f"엑스트라클라사 {season} {r}위 (추정, 다른 선수 자료 같은 시즌 4위 1400·6위 1378의 가운데)"
    if lg == "FR2":
        return interp(FR2_KNOWN, r), f"리그2 {season} {r}위"
    if lg == "FR3":
        return interp(FR3_KNOWN, r), f"프랑스 3부(나시오날) {season} {r}위/{n}팀 (추정, 다른 선수 자료 나시오날 9위 1304·11위 1291의 가운데)"
    if lg == "KR1":
        return interp(HR_KNOWN, r), f"크로아티아 1부 {season} {r}위 (추정, 다른 선수 자료 크로아티아 1위 1610·3위 1460의 가운데)"
    if lg == "A1#group1" and season == "2023-24":
        return int(AT_2324 + 119 * curve(r, 12) + 0.5), f"오스트리아 분데스리가 {season} {r}위 (리그 모형값)"
    return None
RANK_LG = ["BE1", "FR2", "FR3", "KR1", "A1#group1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정')
MAN = {
    (key("FC Viitorul Constanta"), "2019-20"): (1440, "루마니아 1부 2019-20 7위 (추정, 다른 선수 자료 루마니아 7위 1440과 같음)"),
    (key("AEK Larnaca"), "2019-20"): (1400, "키프로스 1부 2019-20 5위 (추정, 다른 선수 자료 아에크 라르나카 2018-19 1400과 같음; 코로나로 시즌 취소된 시점 순위)"),
    (key("Golden Lion FC"), "2023-24"): (1100, "마르티니크 지역 1부 리그(프랑스 해외 지역 리그) (추정, 다른 선수 자료 프랑스 6부 지역 리그 1100과 같은 수준)"),
    (key("FK Bodø/Glimt"), "2025-26"): (1740, "노르웨이 2025 2위 (추정, 다른 선수 자료 보되/글림트 2026 1740과 같음)"),
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
    seasons = [eu, d[:4]] if cid in ("CL", "EL", "ELQ", "CLQ", "ECLQ", "UCOL") else [eu]   # 달력 연도 리그 상대는 경기 연도
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    if (k, eu) in RANK_FIX:
        lg, r, n = RANK_FIX[(k, eu)]
        res = model(lg, eu, r, n)
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg + " fix", []))
        return res
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
    return g["date_local_computed"]   # Transfermarkt 리포트 날짜와 모두 같음(브뤼셀·파리·로마·마드리드 시간)

M = []
for g in GAMES:
    if g["date_local_computed"] != g["date_local_tm_report"] and g["date_local_tm_report"]:
        sys.exit("날짜 불일치 " + g["gameId"])
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
        if r["david_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
ADDED_PM = []
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
    isg, isa = e["david_scorer"] == "1", e["david_assist_other"] == "1"
    if e["david_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag, ldate(g))); EXCL_CNT["본인 도움"] += 1
        EXCL_LIST["본인 도움"].append((ldate(g), g["opponent"], e["minute"], e["scorer"], e["assist_type"]))
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, SCORE_FIX.get(tag, e["score_home_away_after"]).split("-"))
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
        pk = int(e["penalty"] == "1")
        if tag in PK_FIX: pk = PK_FIX[tag][0]
        add_row("g", mi, dm, gf, ga, pk, 0, tie, comp, ko, d, opp, cid, et)
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
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
            if hit:
                used_fm[gid] += 1
            elif tag in ADD_FM_PM:
                ADDED_PM.append((d, opp, e["minute"], e["scorer"]))
            else:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local_computed"] >= GAP and len(ts) > used_fm.get(gid, 0):
        FM_ONLY.append((gid, G[gid]["date_local_computed"], ts))
# FotMob 선수 경기 목록 도움 수가 이 계산기 도움보다 많은 경기
PM_MORE = []
for gid, r in FM_PM.items():
    if gid not in G: continue
    n_here = sum(1 for x in rows if x[0] == "a" and x[9] == ldate(G[gid]))
    if r["fm_assists"] and int(r["fm_assists"]) > n_here:
        PM_MORE.append((gid, ldate(G[gid]), G[gid]["opponent"], int(r["fm_assists"]), n_here))

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u)
for f in FM_ONLY:
    if f[0] not in FM_ONLY_DECIDED: print("판정 필요(FotMob 단독 도움):", f)
for f in PM_MORE:
    if f[0] not in FM_ONLY_DECIDED: print("판정 필요(FotMob 선수 경기 목록 도움이 더 많음):", f)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
if UNDECIDED or missing_elo or any(f[0] not in FM_ONLY_DECIDED for f in FM_ONLY) or any(f[0] not in FM_ONLY_DECIDED for f in PM_MORE):
    if "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY, EXCL_CNT, "선수 경기 목록으로 넣은 도움:", ADDED_PM)
    print("BE 회귀", BE_A, BE_B, {s: be_mean(s) for s in ("2018-19", "2019-20")}, "AT", AT_2324)
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
    if e["david_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local_computed"])); continue
    fg = [r for r in FM_EV[gid] if r["david_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["david_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local_computed"] if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Rémy Cabella": ("cab.js", "CAB", "2022-07-10", "2025-07-01")}
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
FK = lambda s: norm(s or "") in ("jonathan david", "david")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("데이비드 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and FK(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→데이비드 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    for x in ent:   # Transfermarkt 데이비드 도움을 이 계산기에서 뺀 동료 골(참고)
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["david_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 데이비드 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # TM 동료 도움 → 데이비드 골인데 동료 파일에 없음(참고)
        if e["david_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 데이비드 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
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
CLUBS = [("genjd", "2020-08-11", "KAA 헨트", "2018~2020"), ("liljd", "2025-07-04", "LOSC 릴", "2020~2025"),
         ("juvjd", "2026-09-01", "유벤투스", "2025~2026"), ("atmjd", None, "아틀레티코 마드리드", "2026~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"157": "genjd", "1082": "liljd", "506": "juvjd", "13": "atmjd"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_david import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["david_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC,
                      BE={s: be_mean(s) for s in ("2018-19", "2019-20")}))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const JDV_E={J(E)};\nconst JDV_M={J(M)};\nconst JDV_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
