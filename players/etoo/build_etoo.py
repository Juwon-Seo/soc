#!/usr/bin/env python3
"""Samuel Eto'o: raw/ -> etoo.json + src/data/eto.js (판정 근거는 judgments.md)

  python3 players/etoo/build_etoo.py

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv·fotmob_tm_map.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/{mes,rdg,ini,hen,haz,lam,tor}.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "eto.js")
OUT_JSON = os.path.join(HERE, "etoo.json")
ME = "사무엘 에투"
GAP = "2014-08-01"   # 도움 출처 기준일(이전 Transfermarkt, 이후 Transfermarkt∩FotMob)

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
# 날짜 수정: Transfermarkt 리포트 날짜가 현지 날짜와 다른 경기
DATE_FIX = {"2222736": "2012-12-10"}   # 제니트-안지: 스포르트-엑스프레스·sports.ru 경기 페이지 2012.12.10 20:00(상트페테르부르크)

# Transfermarkt에 출전이 없지만 경기 기사로 출전·골이 확인된 경기(카타르 QSL컵 = 카타르 리그컵, 조별리그)
#   (날짜, 상대, 대회, 출전 분(추정), 홈 여부, 최종 스코어(우리-상대), [(분, 골 전 우리, 골 전 상대)])
ADD_GAMES = [
    ("2018-09-08", "Al-Gharafa SC", "dc", 90, 1, (1, 1), [(35, 0, 0)]),
    #   Gulf Times 2018.9.8 'Duhail, Umm Salal win QSL Cup opener, Al Gharafa held': 에투 35분 선제골, 89분 PK로 1-1
    ("2018-12-21", "Al-Kharaitiyat SC", "dc", 90, 0, (4, 0), [(27, 0, 0), (40, 2, 0)]),
    #   QSL 공식 'QSL Cup Round 4, Group A Friday Reports': 에투 27·40분, 파들 오마르 36분, 알리 68분 / The Peninsula 2018.12.22
]
# Transfermarkt 리포트에 골 목록이 없는 경기의 골(선수 경기 성적 API 1골)
ADD_GOALS = {"3677051": [(81, 0, 0, 0)]}   # 2019.4.21 에미르컵 무아이테르전 81분(The Peninsula 2019.4.22), 1-0 유일한 골

# 골 제외(Transfermarkt 리포트 골이지만 넣지 않음)
EXCL_G = {"2323729|79": "상대 자책골(FotMob: 두리차 자책골, Sports.ru 문자중계: 에투 슈팅이 두리차 발에 맞고 들어간 자책골)"}

# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    "27991|77": "PK 유도",
    "938294|55": "슈팅 리바운드(Shot on goal)",
    "28110|2": "상대 자책골(델리오 톨레도)",
    "36071|19": "상대 자책골(다니 하르케)",
    "964637|13": "상대 자책골(만토바니)",
    "2208071|25": "상대 자책골(부를라크)",
    "2367104|44": "상대 자책골(게오르기에프스키)",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "3126018|45+1": "QSL 공식 경기 기사('Eto'o became provider to Syrian striker Omari')·Football Qatar(스포르트-엑스프레스 인용, 'then created the second just before the break')",
}
# FotMob에만 있는 도움(넣지 않음)
FM_ONLY = ["2015.5.31 파르마전 79분 데 실베스트리 골(FotMob은 에투 도움, Transfermarkt는 코레아 도움)"]

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES1", "ES2", "IT1", "GB1", "RU1", "TR1", "QSL", "QSLR"}
CUP = {"CDR", "CIT", "FAC", "CGB", "RUP", "TRP", "QEC1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SUC", "SCI", "USC"): return "df"
    if cid == "KLUB": return "cwc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # UEFA컵 2·3라운드·16강, 유로파 32강(intermediate stage)·16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

OTHER_LEG = {"1160470": "1160459"}   # 하이두크 챔스 예선 2차전: 리포트에 다른 차전 링크 없음(1차전 리포트 1160459)

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
    ag = 1
    if cid == "TRP": ag = 0          # 튀르키예컵: 판페르시 선례(원정 다득점 없음으로 둠, 연장 있음)
    et = 1
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
    "inter milan": "inter", "lokomotiv moskau": "lokomotiv moscow", "dinamo moscow": "dynamo moscow",
    "fc copenhagen": "fc kobenhavn", "kispest honved fc": "budapest honved fc",
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

# 순위표(Transfermarkt): (리그, 시즌) -> {key: (순위, 팀 수)}
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 세리에A 고정 순위값(기존 자료) → 표준 곡선(인시녜 자료와 같은 방식, 기존 리그 값 ±2 재현)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

# 라리가: 기존 자료 2003-04 값(14위는 2004-05 값 − 1)을 기준으로 시즌별 이동값(같은 시즌 기존 자료와의 차)
LL_BASE = ents_map("라리가", "2003-04"); LL_BASE[14] = 1661
assert len(LL_BASE) == 20, LL_BASE
def laliga(season, r):
    m = ents_map("라리가", season)
    if r in m: return m[r], False
    diffs = [v - LL_BASE[k] for k, v in m.items()]
    if not diffs: sys.exit("라리가 시즌 값 없음 " + season)
    sh = sorted(diffs)[len(diffs) // 2] if len(diffs) % 2 else sum(sorted(diffs)[len(diffs) // 2 - 1:len(diffs) // 2 + 1]) / 2
    return int(round(LL_BASE[r] + sh)), True
# 세군다(22팀): 기존 자료의 고정 순위값(2001-02~2025-26 모두 같음)
SEG = [1753, 1712, 1687, 1674, 1660, 1654, 1647, 1640, 1632, 1623, 1615, 1610, 1606, 1601, 1598, 1595, 1589, 1580, 1572, 1567, 1560, 1553]

def model(lg, season, r, n):
    """(Elo, lv) — 순위표 + 리그 모형"""
    if lg == "ES1":
        v, interp = laliga(season, r)
        return v, f"라리가 {season} {r}위"
    if lg == "ES2":
        assert n == 22
        return SEG[r - 1], f"세군다(2부) {season} {r}위"
    if lg == "IT1":
        return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "GB1":
        return ents_map("프리미어리그", season)[r], f"프리미어리그 {season} {r}위"
    if lg == "TR1":
        if season in ("2015-16", "2016-17"):
            m = ents_map("쉬페르리그", season)
            if r in m: return m[r], f"쉬페르리그 {season} {r}위"
            mean = 1473 if season == "2015-16" else 1479
            return int(round(mean + 119 * curve(r, n))), f"쉬페르리그 {season} {r}위"
        # 2017-18: 튀르키예 리그 평균을 2016-17과 같게 둠(추정)
        return int(round(1479 + 119 * curve(r, n))), f"쉬페르리그 {season} {r}위 (추정, 2016-17 리그 수준 사용)"
    if lg == "RU1":
        return int(round(1520 + 55 * curve(r, n))), f"러시아 프리미어리그 {season} {r}위 (리그 수준 추정)"
    if lg == "QSL":
        return int(round(1460 + 45 * curve(r, n))), f"카타르 {season} {r}위 (추정, 마레즈 자료와 같은 리그 수준)"
    return None

RANK_LG = ["ES1", "ES2", "IT1", "GB1", "TR1", "RU1", "QSL"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {
    (key("Xerez CD"), "2000-01"): (1350, "스페인 3부(세군다 B) 2000-01 (추정, 다른 선수 자료 스페인 3부 1350과 같음)"),
    (key("FC Slovan Liberec"), "2001-02"): (1500, "체코 2001-02 1위 (추정, 다른 선수 자료 슬라비아 프라하 2000-01 2위 1500과 같은 수준)"),
    (key("HNK Hajduk Split"), "2001-02"): (1480, "크로아티아 2000-01 1위 (추정, 다른 선수 자료 크로아티아 1위 1500~1520보다 조금 낮게)"),
    (key("APOEL Nicosia"), "2003-04"): (1420, "키프로스 2003-04 1위 (추정, 다른 선수 자료 아포엘 2009 1450보다 낮게)"),
    (key("TP Mazembe"), "2010-11"): (1450, "콩고민주공화국·아프리카 챔피언 2010 (추정)"),
    (key("Vitesse Arnhem"), "2012-13"): (1642, "에레디비시 2012-13 4위"),
    (key("AZ Alkmaar"), "2012-13"): (1528, "에레디비시 2012-13 10위"),
    (key("BSC Young Boys"), "2012-13"): (1406, "스위스 슈퍼리그 2012-13 7위 (추정, 다른 선수 자료 6위 1430·8위 1382 사이)"),
    (key("Kispest–Honvéd FC"), "2012-13"): (1420, "헝가리 2012-13 3위 (추정, 다른 선수 자료 비디오톤 2012 2위 1450보다 낮게)"),
    (key("Spartak Moscow"), "2003-04"): (1520, "러시아 2003 10위 (추정, 다른 선수 자료 스파르타크 모스크바 2006 1600보다 낮게)"),
    (key("Muaither SC"), "2018-19"): (1300, "카타르 2부 2018-19 (추정, 카타르 1부 평균 1460 − 독일 1·2부 평균 차)"),
}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    # 1) 같은 경기 다른 선수 자료(날짜 ±1)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "KLUB", "USC") else [eu]
    # 2) 같은 팀·같은 시즌 기존 값(팀×시즌 통합표)
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    # 3) 직접 추정
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    # 4) 순위표 + 리그 모형
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
    return DATE_FIX.get(g["gameId"], g["date_local_tm_report"])

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
for (d, opp, comp, mins, home, fin, goals) in ADD_GAMES:
    M.append([d, opp, comp, mins, 1])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["etoo_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
def add_row(typ, g_like, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
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
    isg, isa = e["etoo_scorer"] == "1", e["etoo_assist_other"] == "1"
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
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", g, mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP and tag not in ADD_CONFIRMED:
            if not any(abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - mi) <= 2 for t in FM_ASSIST.get(gid, [])):
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
        add_row("a", g, mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

for gid, gl in ADD_GOALS.items():
    g = G[gid]
    for (mi, gf, ga, pk) in gl:
        add_row("g", g, mi, 0, gf, ga, pk, 0, tie_of(g), comp_of(g["competitionId"], g["round"]), ko_of(g), ldate(g), g["opponent"].strip(), g["competitionId"])
for (d, opp, comp, mins, home, fin, goals) in ADD_GAMES:
    for (mi, gf, ga) in goals:
        add_row("g", None, mi, 0, gf, ga, 0, 0, None, comp, 0, d, opp, "QSCP")

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["etoo_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV: continue
    fg = [r for r in FM_EV[gid] if r["etoo_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_tm_report"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local_tm_report"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Lionel Messi": ("mes.js", "MES"), "Ronaldinho": ("rdg.js", "RDG"), "Andrés Iniesta": ("ini.js", "INI"),
         "Thierry Henry": ("hen.js", "HEN"), "Eden Hazard": ("haz.js", "HAZ"), "Frank Lampard": ("lam.js", "LAM"),
         "Fernando Torres": ("tor.js", "TOR")}
MATE_E = {nm: load_js(*v) for nm, v in MATES.items()}
CLUB_SPANS = {"Lionel Messi": ("2004-08-26", "2009-07-27"), "Ronaldinho": ("2004-08-26", "2009-07-27"),
              "Andrés Iniesta": ("2004-08-26", "2009-07-27"), "Thierry Henry": ("2004-08-26", "2009-07-27"),
              "Eden Hazard": ("2013-08-29", "2014-08-26"), "Frank Lampard": ("2013-08-29", "2014-08-26"),
              "Fernando Torres": ("2013-08-29", "2014-08-26")}
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[7] != b[7] or ((a[14] if len(a) > 14 else 0) or 0) != ((b[14] if len(b) > 14 else 0) or 0):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    return diffs
for nm, ent in MATE_E.items():
    lo, hi = CLUB_SPANS[nm]
    # 에투 도움 → 동료 골
    for r in E:
        if r[0] == "a" and r[13] == nm:
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("에투 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    # 동료 도움 → 에투 골
    for x in ent:
        if x[0] == "a" and x[13] == "Samuel Eto'o":
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→에투 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    # 같은 경기·같은 상대 Elo/lv/대회
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d)); break
    # 동료 골에 대한 Transfermarkt 에투 도움이 동료 파일에 '도움 없음'으로 빠진 경우(참고)
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["etoo_assist_other"] == "1" and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 에투 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("legeto", "1998-07-01", "레가네스(임대)", "1997~1998"), ("rmeto", "1999-01-01", "레알 마드리드", "1998"),
         ("espeto", "1999-07-01", "에스파뇰(임대)", "1999"), ("rmeto", "2000-01-16", "레알 마드리드", "1999~2000"),
         ("maleto", "2004-08-26", "마요르카", "2000~2004"), ("fcbeto", "2009-07-27", "바르셀로나", "2004~2009"),
         ("inteto", "2011-08-24", "인테르", "2009~2011"), ("anzeto", "2013-08-29", "안지 마하치칼라", "2011~2013"),
         ("cheeto", "2014-08-26", "첼시", "2013~2014"), ("eveeto", "2015-01-27", "에버턴", "2014~2015"),
         ("sampeto", "2015-07-01", "삼프도리아", "2015"), ("antaeto", "2018-01-31", "안탈리아스포르", "2015~2018"),
         ("konyeto", "2018-08-14", "코니아스포르(임대)", "2018"), ("qateto", None, "카타르 SC", "2018~2019")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {}
for k, u, n, y in CLUBS: CLUB_KO.setdefault(k, n.replace("(임대)", "").strip())
ORDER = list(dict.fromkeys(k for k, *_ in CLUBS))
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in ORDER)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
# 출전 행이 그 날짜 클럽 대회와 맞는지(예: 1998.12.5 에스파뇰전은 레알 마드리드 소속 경기)
for g in GAMES:
    tm_club = {"1244": "legeto", "418": "rmeto", "714": "espeto", "237": "maleto", "131": "fcbeto", "46": "inteto", "2700": "anzeto",
               "631": "cheeto", "29": "eveeto", "1038": "sampeto", "589": "antaeto", "2293": "konyeto", "965": "qateto"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + ldate(g))

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
POST_A = NA - PRE_A
SRC = ELO_SRC
NOTE_LINES = [
    f"사무엘 에투(레가네스·레알 마드리드·에스파뇰·마요르카·바르셀로나·인테르·안지 마하치칼라·첼시·에버턴·삼프도리아·안탈리아스포르·코니아스포르·카타르 SC)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 에이바르전 ~ {d_(M[-1][0])} 무아이테르전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·카메룬 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items())
    + f". 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(출전한 754경기 전부), 2010-11 이후 골은 FotMob 경기 이벤트와 대조함",
    "경기 수·골은 영어 위키백과 클럽·시즌별 기록과 대부분 같음(764경기 371골). 다른 곳: 레가네스 1997-98 리그 위키백과 28경기·Transfermarkt 25경기, 마요르카 코파 델 레이 위키백과 3경기 더 많음(2000-01·2002-03·2003-04 각 1경기), 카타르 SC 2018-19 위키백과 23경기 10골·Transfermarkt 19경기 7골. 레가네스·마요르카의 빠진 6경기는 경기별 자료(날짜·상대)를 찾지 못해 넣지 않음",
    "카타르 SC: Transfermarkt에 없는 QSL컵(카타르 리그컵) 조별 2경기를 경기 기사로 확인해 넣음 — 2018.9.8 알가라파전 35분 선제골(1-1, Gulf Times), 2018.12.21 알카라이티야트전 27·40분 골(4-0, QSL 공식 경기 기사·The Peninsula). 두 경기 출전 분은 자료가 없어 90분으로 추정. 위키백과의 나머지 카타르 컵 경기(골 없는 1~2경기)는 경기별 자료를 찾지 못해 넣지 않음",
    "2019.4.21 에미르컵 무아이테르전 골은 Transfermarkt 리포트에 골 목록이 없어 The Peninsula 기사(81분 결승골, 1-0)로 분과 스코어를 넣음",
    "1998.12.5 에스파뇰-레알 마드리드 리그 경기(23분)는 Transfermarkt 이적 기록상 에스파뇰 임대(1998.12.1) 뒤지만 경기 리포트에는 레알 마드리드 교체 선수로 나오고 스페인어 위키백과도 레알 마드리드 데뷔전으로 적어 레알 마드리드 경기로 셈(임대는 1999년 1월부터로 봄). 레알 마드리드 2군(카스티야) 경기는 어느 출처에도 없음",
    "날짜는 현지 날짜. 2012.12.10 제니트전은 Transfermarkt가 12.9로 적었으나 스포르트-엑스프레스·sports.ru 경기 페이지(상트페테르부르크 20:00)대로 고침",
    f"골: Transfermarkt 리포트 골에서 2013.7.14 로코모티프 모스크바전 79분 골(FotMob은 두리차 자책골, sports.ru 문자중계도 에투 슈팅이 두리차 발에 맞고 들어간 자책골로 적음)을 빼고 위 3경기 4골을 더함. 위키백과·Transfermarkt 합계보다 1골 적음",
    "2018.9.14 알샤하니아전은 Transfermarkt 리포트에 골이 하나 빠져 있고 FotMob은 90분 골도 에투로 적었으나, QSL 공식 경기 기사는 52분 에투·90+1분 알쿠바이시로 적어 1골만 넣음(위키백과 리그 6골과도 맞음)",
    f"PK 골 {NPK}개는 Transfermarkt 골 유형 'Penalty' 기준(FotMob과 같음). 'Penalty rebound'(PK가 막힌 뒤 리바운드 골) 4개(2009.2.14 베티스전 45+3분, 2010.9.11 우디네세전 67분, 2016.3.14 부르사스포르전 88분, 2017.1.28 알라니아스포르전 44분)는 일반 골로 셈. Transfermarkt 리포트가 본인 PK 골에 본인 도움으로 적은 6개는 도움으로 세지 않음",
    "2010-11 이후 골은 FotMob 경기 이벤트와 스코어·PK가 같음. 분이 2분 다른 2011.11.5 크릴리아 소베토프전 PK 골(Transfermarkt 68분·FotMob 66분)은 Transfermarkt 분을 씀. FotMob 경기 기록이 없는 경기(2010.8.21 수페르코파·2010-11 세리에A 9경기·코파 이탈리아 2경기·2011.3.15 바이에른전)는 Transfermarkt만 근거",
    f"도움: 2014.8.1 이전은 Transfermarkt 경기 리포트 도움, 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것만 씀. 도움 {NA} = Transfermarkt 리포트 121 − PK 유도 1(2004.11.20 레알 마드리드전 77분 호나우지뉴 PK) − 슈팅 리바운드 1(2009.5.13 코파 델 레이 결승 55분 메시 골, 'Shot on goal') − 상대 자책골에 준 도움 5(2005.2.12 사라고사전 2분, 2006.5.7 에스파뇰전 19분, 2010.5.9 키에보전 13분, 2012.4.28 로코모티프전 25분, 2013.10.1 슈테아우아전 44분)",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(러시아 리그 2011~13은 FotMob에 도움 자료가 없음). 도움 유형 칸이 빈 2000.4.9 카레라스·2010.4.24 키부·2010.5.9 밀리토·2010.9.29 스네이더르 골 도움도 일반 도움으로 셈",
    f"2014.8.1 이후 도움 {POST_A}개 중 {POST_A - 1}개는 FotMob도 에투 도움으로 적음. 2018.10.5 알카라이티야트전 45+1분 오마리 골은 FotMob에 도움이 없지만 QSL 공식 경기 기사와 Football Qatar 영상 글이 에투가 만든 골로 적어 넣음. 2014.11.22 웨스트햄전 73분 오스먼 골 도움은 Transfermarkt 유형 칸이 비었으나 FotMob도 에투 도움",
    "FotMob에만 있는 도움 1개는 넣지 않음: " + "; ".join(FM_ONLY),
    "출처 간 도움 차이: 스페인어 위키백과의 시즌 도움 합계(144)는 Transfermarkt보다 많음(레가네스 5·0, 마요르카 2003-04 11·7, 첼시 7·4 등)이나 경기별 근거가 없어 쓰지 않음. FotMob 경력 합계는 안지 8·첼시 3·삼프도리아 3·안탈리아스포르 15로 Transfermarkt와 다름",
    "상대 Elo는 같은 경기를 다룬 다른 선수 자료(메시·호나우지뉴·이니에스타·앙리·아자르 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 모형에 넣은 값, 직접 추정 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "라리가 순위 값은 다른 선수 자료의 같은 시즌 값을 쓰고, 그 시즌에 없는 순위는 2003-04 순위별 값에 같은 시즌 다른 순위 값과의 차이를 더함(1999-00 +11, 2000-01 +31, 2001-02 +16, 2002-03 +10 안팎). 세군다(2부, 레가네스·코파 델 레이 상대)는 다른 선수 자료와 같은 22팀 순위별 값",
    "러시아 프리미어리그 2011-12~2013-14는 기존 리그 모형이 없어 평균 1520·흩어짐 55로 추정함(리그 수준 추정, 근거 약함; 다른 선수 자료의 CSKA·제니트·스파르타크·루빈 값이 있는 팀-시즌은 그 값). 2011-12는 44라운드 두 단계 시즌의 최종 순위(Transfermarkt)",
    "쉬페르리그 2015-16·2016-17은 다른 선수 자료의 순위별 값(없는 순위는 같은 리그 공식 값), 2017-18은 리그 평균을 2016-17과 같게 둔 추정. 카타르 2018-19는 마레즈 자료와 같은 리그 수준(평균 1460·흩어짐 45)에 Transfermarkt 최종 순위",
    "직접 추정(모두 '추정'): 헤레스(스페인 3부) 2000 1350, 슬로반 리베레츠 2001 1500, 하이두크 스플리트 2001 1480, 아포엘 2003 1420, 스파르타크 모스크바 2003(러시아 10위) 1520, TP 마젬베 2010 1450, 영 보이스 2012-13(스위스 7위) 1406, 키슈페스트 혼베드 2012 1420, 무아이테르(카타르 2부) 2019 1300. 비테세(4위 1642)·AZ(10위 1528) 2012-13은 다른 선수 자료의 에레디비시 순위별 값",
    "대회 비중: 코파 델 레이·코파 이탈리아·FA컵·리그컵·러시아컵·튀르키예컵·에미르컵·QSL컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), 수페르코파·수페르코파 이탈리아나·UEFA 슈퍼컵은 국내컵 결승, FIFA 클럽 월드컵(2000·2010)은 클럽 월드컵, UEFA컵 1라운드는 유로파 예선, 2·3라운드와 16강은 유로파 토너먼트, 유로파 32강은 유로파 토너먼트로 계산함. QSL컵 조별은 리그식(무승부 1점), 카타르 리그 잔류 플레이오프는 리그 경기로 둠",
    f"두 경기 합산(챔스·유로파 예선과 토너먼트, 코파 델 레이 두 경기 라운드, 수페르코파, 코파 이탈리아 준결승, 튀르키예컵 8강) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회·스페인 국내 대회·코파 이탈리아에 적용, 튀르키예컵은 판페르시 자료처럼 원정 다득점 없음·연장 있음으로 둠",
    "에투가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움: 2001.1.17 테네리페 2차전, 2001.12.12 코르도바 1차전, 2010.2.3 피오렌티나 1차전, 2011.4.19 로마 1차전, 2018.2.1 갈라타사라이 1차전(코니아스포르 입단 전)",
    "연장전: 2013.4.17 러시아컵 8강 디나모 모스크바전 99분 골은 연장 시간으로 계산. 2001.8.21 하이두크전(연장)·2000.1.14 클럽 월드 챔피언십 3위전 네카사전(승부차기)·2011.1.26 나폴리전·2013.6.1 러시아컵 결승(연장 뒤 승부차기)의 출전 분은 Transfermarkt 그대로",
    "시즌 구분: 안지는 7월 10일 기준(2012.7·2013.7 러시아 리그·유로파 예선이 새 시즌), 나머지 클럽은 8월 1일 기준. 클럽 구분은 1998.7.1 전 레가네스, 1999.1.1 전 레알 마드리드, 1999.7.1 전 에스파뇰, 2000.1.16 전 레알 마드리드, 2004.8.26 전 마요르카, 2009.7.27 전 바르셀로나, 2011.8.24 전 인테르, 2013.8.29 전 안지, 2014.8.26 전 첼시, 2015.1.27 전 에버턴, 2015.7.1 전 삼프도리아, 2018.1.31 전 안탈리아스포르, 2018.8.14 전 코니아스포르, 이후 카타르 SC",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 챔스 4회(1999-00 레알 마드리드, 2005-06·2008-09 바르셀로나, 2009-10 인테르), 라리가 3회, 세리에A 2009-10, 코파 델 레이 2회(2002-03 마요르카·2008-09 바르셀로나), 코파 이탈리아 2회, 수페르코파 2회, 수페르코파 이탈리아나 2010, 클럽 월드컵 2010(Transfermarkt 표기 2011). 개인: 아프리카 올해의 선수 4회, 라리가 득점왕 2005-06(26골), 코파 이탈리아 득점왕 2010-11(5골). 네이션스컵·올림픽 등 대표팀 기록은 뺌",
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
mm = {m[0]: m for m in M}
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const ETO_E={J(E)};\nconst ETO_M={J(M)};\nconst ETO_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
