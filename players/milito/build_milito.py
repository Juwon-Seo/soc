#!/usr/bin/env python3
"""Diego Milito: raw/ -> milito.json + src/data/mlt.js (판정 근거는 judgments.md)

  python3 players/milito/build_milito.py            # 파일 쓰기
  python3 players/milito/build_milito.py --debug    # Elo 출처 목록
  python3 players/milito/build_milito.py --cross    # 같은 경기 다른 선수 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/ranks.txt·raw/tables/*.html(순위표), raw/milito_goal_assist_events.csv(FotMob·ESPN 대조),
      <ROOT>/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(동료 대조).
크레스포 build 스크립트를 바탕으로 함(아르헨티나 모형은 리켈메·포를란 스크립트).
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "mlt.js")
OUT_JSON = os.path.join(HERE, "milito.json")
ME = "디에고 밀리토"
NEW_JUDGES = ("alx", "lku", "ldz", "tvz", "alexis", "lukaku", "luisdiaz", "tevez")   # 같은 회차 다른 판정 파일은 읽지 않음

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]   # 인테르 프리마베라(유스) 2경기 제외
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
XCHK = rd("milito_goal_assist_events.csv")

# ---------------------------------------------------------------- 판정 표
MIN_FIX = {}
EXCL_G = {}
# 도움 제외: gameId|분 -> 이유 (judgments.md 4절)
EXCL_A = {
    "3771794|51": "슈팅 리바운드(Shot on goal, 에스테베스)",
    "972427|89": "슈팅 리바운드(Shot on goal, 스네이더르)",
    "1141937|51": "슈팅 리바운드(Shot on goal, 캄비아소)",
    "3792986|55": "PK 유도(Penalty: Fouled player, 베도야)",
    "964275|56": "PK 유도(Penalty: Fouled player, 에투)",
}
GAP = "2014-08-01"
# 2014.8 이후 도움 확인(judgments.md 4절): gameId|분 -> 근거. FotMob 경기 이벤트가 같은 도움이면 자동 통과.
# FotMob 도움 자료가 없는 경기(리베르타도레스 2015·2016, 2016 리그)는 ESPN 경기 이벤트 + 경기 기사 1곳 이상.
CONF_A = {
    "2536141|69": "ESPN + 디아리오 데 쿠요 2015.2.18(카마초→밀리토→보우, '또 하나의 밀리토 도움')",
    "2560733|16": "ESPN + 몬테비데오 포털·eju.tv(밀리토 오른쪽 크로스 → 카마초)",
    "2669698|6": "ESPN + 로스 안데스 2016.3.7(밀리토가 노이르에게 패스)",
    "2669702|44": "ESPN + 디아리오 데 쿠요 2016.3.12(밀리토가 왼쪽에서 로메로에게 패스)",
    "2673068|38": "ESPN + 라 카피탈(마르델플라타) 2016.4.8(밀리토 왼쪽 크로스 → 로메로 헤딩)",
}
REJ_A = {   # 확인 못 한 2014.8 이후 단일 출처 도움(Transfermarkt + ESPN뿐)
    "2536141|40": "기사(디아리오 데 쿠요)는 보우·밀리토·카마초의 연결만 적고 마지막 패스를 밝히지 않음",
    "2537949|44": "ABC 콜로르·디아리오 데 쿠요는 보우의 역습 단독 슈팅으로 적고 밀리토 언급 없음",
    "2669743|90+2": "ESPN 경기 기사·라 카피탈은 밀리토 패스를 받은 리산드로 로페스가 띄워 준 공을 노이르가 넣었다고 적음(엘론세만 밀리토 패스)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "ES1", "ARGC", "ARG1", "AR1N"}
CUPS = {"CIT", "CDR", "ARCA", "ALPL"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "ALPL": return "dc"     # 리길야 프레 리베르타도레스 2015(리베르타도레스 진출 플레이오프): 국내컵 비중(카바니 선례)
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SCI", "USC"): return "df"
    if cid == "KLUB": return "cwc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"     # 'intermediate stage' = 유로파 32강
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"
        return "elk"
    if cid == "CLI":
        if r.startswith("group") or r.startswith("last 16") or r.startswith("qualifying"): return "lib"
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
    if cid == "CS":
        if r.startswith("quarter"): return "csak"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_rule(g):
    cid, y = g["competitionId"], int(g["date_utc"][:4])
    if cid == "CS": return (0, 0)                       # 수다메리카나 2002: 원정 다득점 없음(합산 3-3, 원정골 앞선 라싱이 승부차기)
    if cid == "CLI": return (0, 0) if y <= 2004 else (1, 0)   # 리베르타도레스 2004년까지 (0,0), 2005~ 결승 외 (1,0)(리켈메 선례)
    return (1, 1)                                       # UEFA 대회·코파 이탈리아·코파 델 레이

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
        if o["result_flag"]: sys.exit("1차전 승부차기 표기 " + gid)
    ag, et = tie_rule(g)
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
# 2016 아르헨티나 1부 2조(라싱 조, 15팀): Transfermarkt 표에는 1조만 있어 영어 위키백과 '2016 Argentine Primera División' 2조 표(최종)
ZONE2_2016 = ["CA Lanús", "Club Estudiantes de La Plata", "Club Atlético Tucumán", "Defensa y Justicia", "CA Huracán",
              "Racing Club", "CA San Martín (San Juan)", "CA Unión (Santa Fe)", "Club Atlético Tigre", "CA Boca Juniors",
              "CA Aldosivi", "CA Newell's Old Boys", "CA Temperley", "AA Argentinos Juniors", "Atlético de Rafaela"]
for i, nm in enumerate(ZONE2_2016, 1):
    RANKS[("AR1N", "2016Z2")][key(nm)] = (i, 15)
RANK_FIX = {}

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
def half_up(x): return int(x + 0.5)
SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 7: 1762, 8: 1743, 9: 1728, 10: 1713, 11: 1704, 12: 1697,
        13: 1690, 14: 1676, 15: 1657, 16: 1645, 17: 1633, 18: 1614}

def mid_fill(m, r):
    lo = max([k for k in m if k < r], default=None); hi = min([k for k in m if k > r], default=None)
    if lo is None or hi is None: return None
    return half_up(m[lo] + (m[hi] - m[lo]) * (r - lo) / (hi - lo))

def arg_val(r, n): return half_up(1583 + 63 * curve(r, n))   # 아르헨티나 1부 모형(리켈메·포를란·라우타로 선례)

def model(lg, season, r, n):
    """(Elo, lv)  season: 유럽식 'YYYY-YY' 또는 아르헨티나 표 키"""
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        if n == 18: return SA18[r], f"세리에A {season} {r}위"
        v = mid_fill(m, r)
        return (v if v else SA[r - 1]), f"세리에A {season} {r}위"
    if lg == "ES1":
        m = ents_map("라리가", season)
        if r in m: return m[r], f"라리가 {season} {r}위"
        v = mid_fill(m, r)
        return (v, f"라리가 {season} {r}위") if v else None
    if lg == "IT2":   # 세리에B 모형(비에리·인자기·크레스포·시모네 페페 선례)
        m = ents_map("세리에B", season)
        if r in m: return m[r], f"세리에B {season} {r}위"
        return half_up(1577.78 + 51.24 * curve(r, n)), f"세리에B {season} {r}위"
    if lg == "ES2":
        m = ents_map("세군다(2부)", season)
        if r in m: return m[r], f"세군다(2부) {season} {r}위"
        v = mid_fill(m, r)
        return (v, f"세군다(2부) {season} {r}위") if v else None
    if lg in ("ARG1", "ARGC"):   # 반시즌 표(TM 시즌 id Y = 아페르투라 Y, 클라우수라 Y+1)
        y0 = int(season[:4])
        if lg == "ARG1" and y0 == 2014: return arg_val(r, n), f"아르헨티나 1부 트란시시온 2014 {r}위"
        t, y = ("아페르투라", y0) if lg == "ARG1" else ("클라우수라", y0 + 1)
        return arg_val(r, n), f"아르헨티나 1부 {t} {y} {r}위"
    if lg == "AR1N":
        if season == "2016Z2": return arg_val(r, n), f"아르헨티나 1부 2016 2조 {r}위/15팀"
        if season == "2016": return arg_val(r, n), f"아르헨티나 1부 2016 1조 {r}위/15팀"
        return arg_val(r, n), f"아르헨티나 1부 {season} {r}위"
    return None

# 직접 추정(모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
man("Club Nacional", "2003", 1600, "우루과이 1부 2002 우승 팀 (추정, 다른 선수 자료 나시오날 우루과이 상위 팀 1600과 같음)")
man("Pontevedra CF", "2007-08", 1350, "스페인 3부(세군다 B) 2007-08 (추정, 다른 선수 자료 스페인 3부 1350과 같음)")
man("Deportivo Táchira", "2015", 1400, "베네수엘라 1부 2014-15 상위 팀 (추정, 다른 선수 자료 베네수엘라 상위 팀 1400과 같음)")
man("Club Guaraní", "2015", 1450, "파라과이 1부 2015 아페르투라·클라우수라 합산 2위/12팀 (추정, 다른 선수 자료 파라과이 1부 팀 1450과 같음)")
man("Club Sporting Cristal", "2015", 1400, "페루 1부 2015 상위 팀 (추정, 2014 우승 팀; 다른 선수 자료 페루 상위 팀 1400과 같음)")
man("Montevideo Wanderers", "2015", half_up(1540 + 63 * curve(11, 16)),
    "우루과이 1부 2014-15 연간 11위/16팀 (추정, 아페르투라·클라우수라 승점 합산; 다른 선수 자료의 우루과이 모형)")
man("Seongnam Ilhwa Chunma", "2010", 1560, "K리그 2010 5위·AFC 챔스 2010 우승팀 (추정, 다른 선수 자료 울산 2020 AFC 챔스 우승팀 1560과 같음)")
man("Deportivo Cali", "2016", half_up(1580 + 63 * curve(5, 20)),
    "콜롬비아 1부 2016 아페르투라·피날리사시온 합산 5위/20팀 (리그 수준 추정, 다른 선수 자료의 콜롬비아 모형)")

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

SA_COMP = {"CLI", "CS", "ARG1", "ARGC", "AR1N", "ARCA", "ALPL"}
def arg_tables(d):
    """대륙 대회·컵의 아르헨티나 상대: 그때 진행 중인 리그 표"""
    y, mo = int(d[:4]), int(d[5:7])
    if y == 2002 or y == 2003:
        return [("ARGC", f"{y-1}-{str(y)[2:]}")] if mo <= 7 else [("ARG1", f"{y}-{str(y+1)[2:]}")]
    return []

def arg_key(g):
    """아르헨티나 리그 경기 -> (표, 시즌 키, 연도)"""
    cid, sid = g["competitionId"], int(g["seasonId"])
    if cid == "ARG1": return ("ARG1", f"{sid}-{str(sid+1)[2:]}", sid)
    if cid == "ARGC": return ("ARGC", f"{sid}-{str(sid+1)[2:]}", sid + 1)
    if cid == "AR1N":
        if sid == 2014: return ("AR1N", "2015", 2015)
        if sid == 2015: return ("AR1N", "2016Z2", 2016)
    sys.exit("아르헨티나 리그 키 " + g["gameId"])

def base_elo(opp, d, cid, g):
    """같은 경기 → 통합표 → MAN → 순위표+모형"""
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or (cid not in SA_COMP and _sub(key(x["opp"]), k)))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        return e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))
    if cid in SA_COMP:
        seasons = [d[:4]]
        if cid in LEAGUE: seasons = [str(arg_key(g)[2])]
    else:
        euro = cid in ("CL", "UEFA", "EL", "ELQ", "USC", "KLUB")
        seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if euro else [eu]
        if cid == "KLUB": seasons = [d[:4]] + seasons
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            return e, lv, "table " + s
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]
            return e, lv, "man"
    if cid in LEAGUE and cid not in ("IT1", "IT2", "ES1"):
        cands = [arg_key(g)[:2]]
    elif cid in SA_COMP:
        cands = arg_tables(d)
    elif cid in ("IT1", "IT2", "ES1"):
        cands = [(cid, eu)]
    else:
        cands = [(lg, eu) for lg in ("IT1", "ES1", "IT2", "ES2")]
    for lg, s in cands:
        t = RANKS.get((lg, s))
        if t and k in t:
            r, n = t[k]
            res = model(lg, s, r, n)
            if res: return res[0], res[1], "model " + lg
    return None

# 아르헨티나 상대가 한 해(lv 연도 키)에 두 반시즌 값으로 나오면 두 값 평균(리켈메 선례)
def year_of_lv(lv):
    t = re.sub(r"\([^()]*\)", " ", lv)
    m = re.search(r"((?:19|20)\d\d)\s*[-–/]\s*(\d{2})(?!\d)", t)
    if m and int(m.group(2)) == (int(m.group(1)) + 1) % 100: return m.group(1) + "-" + m.group(2)
    m = re.search(r"(?:^|[^\d])((?:19|20)\d\d)(?![\d-])", t)
    return m.group(1) if m else None

# ---------------------------------------------------------------- 날짜
def sched_date(s):
    return datetime.strptime(s.split(" ")[1], "%d/%m/%Y").strftime("%Y-%m-%d") if s else ""
PLACEHOLDER = {"12:00", "13:00"}   # 수다메리카나 2002·리베르타도레스 2003 경기 시각 자리값(날짜만 있음, RSSSF copa03 날짜와 같음)
ESPN_T = {}
for gid, v in json.load(open(os.path.join(RAW, "espn", "index.json"), encoding="utf-8"))["found"]:
    if not v[3].endswith("T07:00Z"): ESPN_T[gid] = v[3]   # ESPN 07:00Z = 날짜만 있는 자리값
DATE_FIX = {}
def ldate(g):
    """라싱: 경기 시각(UTC)을 아르헨티나 시간(UTC−3) 날짜로(ESPN 시각이 있으면 ESPN). 유럽 클럽: TM 리포트·일정 날짜"""
    if g["gameId"] in DATE_FIX: return DATE_FIX[g["gameId"]]
    if g["club_id"] == "1444":
        u = ESPN_T.get(g["gameId"])
        if u is None and g["date_utc"][11:16] in PLACEHOLDER:
            return sched_date(g["date_tm_schedule"]) or g["date_local_tm_report"]
        u = u or g["date_utc"]
        dt = datetime.fromisoformat(u.replace("Z", "+00:00")) - timedelta(hours=3)
        return dt.strftime("%Y-%m-%d")
    return g["date_local_tm_report"] or sched_date(g["date_tm_schedule"])

# ---------------------------------------------------------------- 출전
def opp_name(g): return g["opponent"].strip()
M = []
for g in GAMES:
    M.append([ldate(g), opp_name(g), comp_of(g["competitionId"], g["round"]), MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

XC = {}
for x in XCHK:
    XC[(x["gameId"], x["event"], x["minute_tm"])] = x

pending, judg = [], []
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["milito_scorer"] == "1", e["milito_assist_other"] == "1", e["milito_self_assist"] == "1"
    if iss: judg.append(("본인 PK 골의 본인 도움(도움 아님)", ldate(g), e["minute"]))
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
    et = int(mi > 90 and (not dm or int(str(dm).split("+")[0]) >= 105))
    if et and g["gameState"] == "regularly_terminated": sys.exit("연장 판정 이상 " + gid)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = opp_name(g)
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        pending.append(["g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et, g])
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal", "Deflected"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP:
            x = XC.get((gid, "A", e["minute"]))
            fm = x and x["fm_confirms"] == "1"
            if tag in REJ_A:
                judg.append(("도움 제외(확인 못 함)", d, opp, e["minute"], e["scorer"], REJ_A[tag])); continue
            if not fm and tag not in CONF_A:
                sys.exit("2014.8 이후 도움 확인 필요 " + tag)
            judg.append(("2014.8 이후 도움", d, opp, e["minute"], e["scorer"], "FotMob 일치" if fm else CONF_A[tag]))
        pending.append(["a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et, g])

# Elo: 기본값을 구한 뒤 아르헨티나 연도 키 충돌(한 팀·한 해 두 값)을 평균으로 맞춤
base = {}
missing = set()
for p in pending:
    opp, d, cid, g = p[11], p[10], p[12], p[14]
    if (opp, d) in base: continue
    r = base_elo(opp, d, cid, g)
    if r is None: missing.add((opp, d, cid)); r = (0, "?", "none")
    base[(opp, d)] = r
if missing:
    for x in sorted(missing, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)
grp = collections.defaultdict(set)
for (opp, d), (e, lv, src) in base.items():
    if src.startswith("model ARG") and year_of_lv(lv):
        grp[(key(opp), year_of_lv(lv))].add((e, lv))
# 같은 경기 lv('러시아 2009 2위 …')를 그대로 쓰면 팀×시즌 통합표가 CSKA 날짜 기준 시즌을 달력 연도로 바꿔 다른 선수끼리 충돌(2015)이 생김
# → 같은 값 1604의 연도 없는 표기(나니·나바스·발렌시아 자료와 같은 문구)를 씀
LV_FIX = {("CSKA Moscow", "2010-03-31"): "러시아 2위 (추정, 다른 선수 자료 CSKA 모스크바 2009 2위 값 1604와 같음)"}
AVG = {}
for (k, y), vals in grp.items():
    if len(vals) > 1:
        vs = sorted(vals, key=lambda v: ("아페르투라" not in v[1], v[1]))
        parts = [re.sub(r"^아르헨티나 1부 ", "", v[1]) for v in vs]
        AVG[(k, y)] = (half_up(sum(v[0] for v in vs) / len(vs)),
                       f"아르헨티나 1부 {y} (추정, " + "·".join(parts) + " 값 평균)")
rows = []
for p in pending:
    typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et, g = p
    e, lv, src = base[(opp, d)]
    if src.startswith("model ARG") and (key(opp), year_of_lv(lv)) in AVG:
        e, lv = AVG[(key(opp), year_of_lv(lv))]; src = "avg"
    ELO_SRC[{"same": "같은 경기 다른 선수 자료", "table": "팀×시즌 통합표", "man": "직접 추정", "model": "순위표+리그 모형",
             "avg": "순위표+리그 모형"}[src.split(":")[0].split(" ")[0]]] += 1
    ELO_LOG.append((d, opp, e, lv, src))
    if (opp, d) in LV_FIX: lv = LV_FIX[(opp, d)]
    row = [typ, opp, e, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

def sort_min(r):
    return r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5
rows.sort(key=lambda r: (r[9], sort_min(r), 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s_ = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s_, re.S)
    mm_ = re.search(r"const " + P + r"_M=(\[.*?\]);\n", s_, re.S)
    return json.loads(m.group(1)), (json.loads(mm_.group(1)) if mm_ else [])
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    return diffs
CROSS, SAMEGAME, MDATE = [], [], []
OTHERS = {}
for fn in sorted(os.listdir(os.path.join(ROOT, "src", "data"))):
    if not fn.endswith(".js") or fn in ("hon.js", "mlt.js") or fn[:-3] in NEW_JUDGES: continue
    P = fn[:-3].upper()
    try: OTHERS[fn] = load_js(fn, P)
    except Exception: continue
for fn, (ent, mrows) in OTHERS.items():
    for r in E:
        if r[0] != "a": continue
        hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1])]
        if hit: CROSS.append(("밀리토 도움→" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:
        if x[0] == "a" and norm(str(x[13])) == norm("Diego Milito"):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn + " 도움→밀리토 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                SAMEGAME.append((fn, r[9], r[1], tuple(d) or "같음"))
                break
    # 라싱 상대 선수의 출전 행 날짜(같은 상대 = 라싱, ±1일)
    for m in mrows:
        if key(m[1]) == key("Racing Club") and m[0] >= "1999-12" and m[0] <= "2003-12-31" or (key(m[1]) == key("Racing Club") and m[0] >= "2014-07"):
            near = [x for x in M if abs((Date.fromisoformat(x[0]) - Date.fromisoformat(m[0])).days) <= 1]
            if near and all(x[0] != m[0] for x in near):
                MDATE.append((fn, m[0], m[1], [x[0] + " " + x[1] for x in near]))
SAMEGAME = sorted(set(SAMEGAME))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s_ in SAMEGAME:
        if s_[-1] != "같음": print("같은 경기 차이", s_)
    print("같은 경기", collections.Counter((s_[0], s_[-1] == "같음") for s_ in SAMEGAME))
    for x in MDATE: print("출전 날짜 차이", x)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("racml", "2004-01-01", "라싱 클럽", "1999~2003"), ("genml", "2005-09-01", "제노아", "2004~2005"),
         ("zarml", "2008-08-01", "레알 사라고사", "2005~2008"), ("genml", "2009-07-01", "제노아", "2008~2009"),
         ("intml", "2014-07-01", "인테르", "2009~2014"), ("racml", None, "라싱 클럽", "2014~2016")]
TM_CLUB = {"1444": "racml", "252": "genml", "142": "zarml", "46": "intml"}
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
    if g["club_id"] != "1444" and season_eu(ldate(g))[:4] != g["seasonId"]: sys.exit("시즌 불일치 " + g["gameId"])
    if g["club_id"] != "1444" and ldate(g)[5:7] == "07": sys.exit("유럽 7월 경기 " + g["gameId"])
PERIODS = [(n, y, (None if i == 0 else CLUBS[i - 1][1]), u) for i, (k, u, n, y) in enumerate(CLUBS)]
def per(lo, hi):
    inr = lambda d: (lo is None or d >= lo) and (hi is None or d < hi)
    return [sum(1 for m in M if inr(m[0])), sum(1 for r in E if r[0] == "g" and inr(r[9])),
            sum(1 for r in E if r[0] == "a" and inr(r[9])), sum(m[3] for m in M if inr(m[0]))]
ST = [(n, y, per(lo, hi)) for n, y, lo, hi in PERIODS]

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NOTE_LINES = [
    f"디에고 밀리토(라싱 클럽·제노아·레알 사라고사·인테르)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 우니온 산타페전 ~ {d_(M[-1][0])} 템페를레이전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·아르헨티나 대표팀·인테르 프리마베라(유스) 2경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n}({y}) {v[0]}·{v[1]}·{v[2]}" for n, y, v in ST)
    + f". 출전 분 합계 {MIN_TOT:,}분(90분으로 추정한 경기 없음)",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 대회 경기 전부; 밀리토 골 수는 선수 경기 성적과 경기마다 같음). 2010-11 이후 인테르·라싱 골은 FotMob 경기 기록, 2000년대 라싱·사라고사·제노아·인테르 골의 상당수는 ESPN 경기 기록과 대조함(골 순서·스코어 같음, 분 차이 1~3분은 Transfermarkt 분을 씀). 세리에B 제노아 2003-05 골은 Transfermarkt만 근거",
    "경기 수·골은 영어·이탈리아어 위키백과 클럽별 합계와 거의 같음(라싱 1999~2003 148경기 37골, 제노아 2003-05 62경기 34골, 제노아 2008-09 32경기 26골, 인테르 171경기 75골, 라싱 2014~16 72경기 22골 모두 같음). 사라고사만 위키백과 125경기 61골(라리가 53골) vs Transfermarkt 126경기 59골(라리가 51골): 2005-06·2006-07 라리가 1골씩 차이인데 경기별 근거가 없어 Transfermarkt 기준",
    "골: Transfermarkt 리포트 골 253개(PK 49개). 2010.9.14 챔스 트벤테전 30분 자책골(밀리토가 자기 골문에 넣음)은 골이 아님",
    f"도움: 2014.8 전은 Transfermarkt 경기 리포트 도움(단일 출처 허용, 클로제·크레스포 선례), 뒤는 FotMob 경기 기록과 같은 것 또는 다른 출처 2곳(ESPN 경기 기록 + 경기 기사)이 확인한 것만 셈. 도움 {NA} = Transfermarkt 66 − 슈팅 리바운드('Shot on goal') 3(2002.7.28 우라칸전 에스테베스, 2009.11.4 챔스 디나모 키이우전 스네이더르, 2011.12.7 챔스 CSKA전 캄비아소) − PK 유도 2(2002.9.29 산로렌소전 베도야, 2009.8.23 바리전 에투) − 확인 못 한 2014.8 이후 도움 3(아래). 유형 칸이 빈 도움(2008.9.14 밀란전 스쿨리, 2011.1.19 체세나전 에투, 2014.9.25 보카전·2015.2.24 과라니전 보우)은 일반 도움으로 봄",
    "2014.8 이후 도움 12개 중 4개(2014년 보카·벨레스·올림포·반필드전)는 FotMob 경기 기록과 같음. FotMob에 도움 자료가 없는 리베르타도레스 2015·2016과 2016 리그 경기 8개는 ESPN 경기 기록과 경기 기사로 대조해 5개를 넣음(2015.2.17 타치라전 69분 보우, 2015.5.14 원더러스전 16분 카마초, 2016.3.6 우니온전 6분 노이르, 2016.3.11 라누스전 44분 로메로, 2016.4.7 칼리전 38분 로메로). 뺀 3개: 2015.2.17 타치라전 40분 보우(기사가 연결 플레이만 적고 마지막 패스를 밝히지 않음), 2015.2.24 과라니전 44분 보우(기사는 보우의 역습 단독 슈팅), 2016.4.2 티그레전 90+2분 노이르(ESPN 경기 기사·라 카피탈은 밀리토의 패스를 받은 리산드로 로페스가 띄워 준 공을 노이르가 넣었다고 적음)",
    "본인 PK 골에 본인이 PK 유도 도움으로 적힌 8개(Transfermarkt 리포트)는 도움이 아님. FotMob에만 있는 2015.3.29 산마르틴전 8분 보우 골 도움(Transfermarkt·ESPN은 아쿠냐 도움)과 ESPN 선수 통계에만 있는 2005-07 사라고사 도움 3개·2010 클럽 월드컵 성남전 두 번째 도움은 넣지 않음. 스페인어 위키백과의 시즌 도움 합계(제노아 2003-05 7, 사라고사 11)는 경기별 기록이 없어 쓰지 않음",
    "날짜: 라싱 경기는 경기 시각(UTC, ESPN 시각이 있으면 ESPN)을 아르헨티나 시간으로 바꾼 현지 날짜(Transfermarkt 리포트·일정은 중부 유럽 날짜라 저녁 경기가 하루 늦음). 수다메리카나 2002·리베르타도레스 2003은 시각 기록이 없어 Transfermarkt 일정 날짜(RSSSF 날짜와 같음). 유럽 클럽은 Transfermarkt 리포트·일정 날짜",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위를 기존 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "리그 수준: 아르헨티나 1부는 반시즌(아페르투라·클라우수라·2014 트란시시온) 최종 순위, 2015년은 30팀 순위, 2016년은 15팀 조 순위(라싱 조는 영어 위키백과 최종 표)를 다른 선수 자료와 같은 모형(평균 1583·흩어짐 63)에 넣음. 한 해에 두 반시즌 순위로 만난 팀(2002 보카·차카리타, 2003 벨레스·누에바 시카고·인데펜디엔테)은 두 값의 평균(추정), 다른 선수 자료에 같은 팀·같은 해 값이 있으면 그 값을 씀. 수다메리카나 2002 산로렌소는 그때 진행 중인 아페르투라 2002 순위. 세리에B 2003-04(24팀)·2004-05(22팀)는 다른 선수 자료와 같은 세리에B 모형, 세리에A·라리가는 기존 순위값",
    "직접 추정(모두 '추정'): 나시오날(우루과이) 2003 1600, 아메리카 데 칼리 2003은 다른 선수 자료 값 1450, 폰테베드라 2007-08(스페인 3부) 1350, 성남 일화 2010 1560(K리그 5위·AFC 챔스 우승팀), 데포르티보 타치라 2015 1400(베네수엘라 상위 팀), 과라니 2015 1450(파라과이), 스포르팅 크리스탈 2015 1400(페루 상위 팀), 몬테비데오 원더러스 2014-15(우루과이 연간 11위, 우루과이 모형), 데포르티보 칼리 2016(콜롬비아 아페르투라·피날리사시온 합산 5위, 콜롬비아 모형)",
    "대회 비중: 리베르타도레스 예선·조별·16강은 리베르타도레스 조별, 8강은 리베르타도레스 토너먼트, 수다메리카나 2002 2라운드는 수다메리카나, 8강은 수다메리카나 8강, 코파 아르헨티나·코파 델 레이·코파 이탈리아는 국내컵(8강·준결승·결승 가중), 리길야 프레 리베르타도레스 2015(리베르타도레스 진출 플레이오프)는 국내컵, 수페르코파 이탈리아나·UEFA 슈퍼컵은 국내컵 결승, 클럽 월드컵 2010은 클럽 월드컵, UEFA컵 1라운드와 유로파 예선·플레이오프는 유로파 예선, 유로파 32강은 유로파 토너먼트, 2004 코파 이탈리아 조별은 조별(무승부 1점)",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·코파 델 레이·코파 이탈리아는 원정 다득점·연장 있음, 리베르타도레스 2003과 수다메리카나 2002는 원정 다득점·연장 없이 승부차기(2002 수다메리카나 8강은 합산 3-3에서 원정골이 많은 라싱이 승부차기로 탈락), 리베르타도레스 2015·2016(결승 전)은 원정 다득점 있고 연장 없음",
    "시즌 구분: 라싱은 달력 연도(다른 선수 자료의 아르헨티나 클럽과 같음), 유럽 클럽은 8월 1일 기준(7월 경기 없음). 클럽 구분은 2004.1.1 전 라싱, 2005.9.1 전 제노아(세리에B 2003-04 후반기·2004-05, 프로 리그), 2008.8.1 전 레알 사라고사(2005-06 임대), 2009.7.1 전 제노아, 2014.7.1 전 인테르, 이후 라싱(라싱·제노아 두 시기는 각각 한 클럽으로 묶음)",
    "우승·수상은 Transfermarkt 업적 페이지 기준: 챔스 2009-10, 클럽 월드컵 2010, 세리에A 2009-10, 코파 이탈리아 2009-10·2010-11, 수페르코파 이탈리아나 2010(인테르), 아르헨티나 1부 아페르투라 2001·트란시시온 2014(라싱). 개인: UEFA 올해의 클럽 선수 2009-10, 세리에A 올해의 선수 2009-10(AIC 오스카 델 칼초 최우수 선수). Transfermarkt의 08/09 세리에A 올해의 선수·2010 올해의 선수(국가별)·챔스 올해의 선수 09/10·올해의 공격수·최우수 외국인 선수는 선수협회 명단과 맞지 않거나 같은 상과 겹치거나 분류 밖이라 뺌. 대표팀 기록 제외",
    "은퇴: 2016년(마지막 클럽 경기 2016.5.21 템페를레이전)",
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
    gs = sorted({(r[5], r[6], sort_min(r)) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
    for a, b in zip(gs, gs[1:]):
        if b[0] < a[0] or b[1] < a[1] or b[2] < a[2]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
    if len({(r[1], r[3]) for r in rs}) > 1: problems.append(("같은 날 상대·대회 다름", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
mm = {m[0]: m for m in M}
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r, mm[r[9]]))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p_ in problems: print("점검:", p_)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const MLT_E={J(E)};\nconst MLT_M={J(M)};\nconst MLT_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game": SAMEGAME, "m_date_diff": MDATE, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for n, y, v in ST: print(" ", n, y, v)
