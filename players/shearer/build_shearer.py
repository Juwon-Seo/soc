#!/usr/bin/env python3
"""앨런 시어러: raw/ -> shearer.json + src/data/shr.js (판정 근거는 judgments.md)

  python3 players/shearer/build_shearer.py          # 쓰기
  python3 players/shearer/build_shearer.py --debug  # Elo 출처(통합표·같은 경기 외)
  python3 players/shearer/build_shearer.py --cross  # 같은 경기 다른 선수 자료 대조
  python3 players/shearer/build_shearer.py --stat   # 요약
  python3 players/shearer/build_shearer.py --wiki   # 위키백과 사우샘프턴 시즌 페이지 골 분 대조

입력: raw/tm_games.csv(출전, date_local_schedule = 현지 날짜), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
      raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/ranks.txt(순위표), raw/wiki/saints_*.html(골 분 보충),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), 아래 표(직접 판정).
"""
import csv, json, os, re, sys, html, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "shr.js")
OUT_JSON = os.path.join(HERE, "shearer.json")
ME = "앨런 시어러"
ME_TM = {"Alan Shearer"}
CLUB_KEY = {"180": "souas", "164": "blbas", "762": "newas"}

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 판정 표
AUTO_EXCL_TYPES = {"Penalty: Fouled player": "PK 유도", "Shot on goal": "슈팅 리바운드(Shot on goal)"}
# Transfermarkt 리포트 골 시계가 비어 '121'로 읽히는 1989~1996 컵 경기(29경기): 골 목록이 팀별로 묶여 순서도 믿을 수 없음.
# 시어러 골의 분·골 전 스코어(우리-상대)를 다른 출처로 정함. 키 gameId -> [(분, 우리, 상대, 출처), ...] (리포트 시어러 골 순서)
NO_CLOCK = {
    "3434689": [(10, 0, 0, "W"), (76, 1, 0, "W")],          # 1989.10.3 요크(홈) 리그컵 2R 2차전 2-0: 위키백과 시즌 페이지 10·76분
    "3417097": [(46, 0, 0, "W"), (75, 1, 0, "W")],          # 1990.9.25 로치데일(원정) 0-5: 시어러 46·75, 혼 82·월리스 83·러덕 87
    "3416904": [(59, 1, 0, "W")],                           # 1990.11.27 크리스털 팰리스 2-0: 르티시에 42, 시어러 59
    "2635910": [(35, 0, 1, "SA")],                          # 1991.1.5 입스위치 FA컵 3-2: 도젤 12(0-1) 뒤 시어러 35 동점골(Soccer America 결과표·팬 사이트 '동점 헤딩골')
    "3416894": [(71, 0, 0, "W")],                           # 1991.1.16 맨유(홈) 리그컵 8강 1-1: 시어러 71, 휴스 77
    "3416890": [(52, 0, 1, "W"), (87, 1, 3, "W")],          # 1991.1.23 맨유(원정) 재경기 3-2: 휴스 51·61·77, 시어러 52·87(PK)
    "2635963": [(50, 0, 1, "CT")],                          # 1991.1.26 코번트리(원정) FA컵 1-1: 킬클라인 44, 시어러 50(코번트리 텔레그래프 기록)
    "3406123": [(17, 0, 1, "W"), (27, 1, 1, "W")],          # 1991.9.24 스카버러(원정) 1-3: 무니 3, 시어러 17·27, 코커릴 77
    "3322800": [(81, 0, 1, "W")],                           # 1991.10.30 셰필드 웬즈데이(원정) 1-1: 허스트 38, 시어러 81
    "3428997": [(28, 0, 0, "W")],                           # 1992.2.26 볼턴(홈) FA컵 5R 재경기 3-2(연장): 시어러 28 선제골
    # 블랙번 리그컵 5경기 8골: 분을 확인한 출처 없음 -> 45분 추정, 골 전 스코어는 Transfermarkt 골 목록 순서(추정)
    "3309775": [(45, 0, 0, "EST")],                         # 1992.9.23 허더즈필드(원정) 1-1
    "3309042": [(45, 0, 0, "EST"), (45, 1, 0, "EST")],      # 1992.10.6 허더즈필드(홈) 4-3 연장
    "3307764": [(45, 0, 0, "EST")],                         # 1992.10.28 노리치 2-0
    "3306021": [(45, 0, 0, "EST"), (45, 1, 0, "EST")],      # 1992.12.9 왓퍼드 6-1
    "3305869": [(45, 0, 0, "EST")],                         # 1993.9.21 본머스 1-0 (유일한 골이라 0-0 확정)
}
# 리포트 골 목록에 빠진 상대 골: 3553730 1998.2.4 스티버니지(FA컵 4R 재경기 2-1) — nufc.com 경기 기록·BBC: 크로쇼 74분(2-1), 시어러 16·65분 뒤
MISSING_GOAL = {"3553730": "스티버니지 크로쇼 74분 골 누락(시어러 골 뒤)"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"EFD1", "GB1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "GBCS": return "df"                      # 커뮤니티 실드 = 국내컵 결승 비중
    if cid in ("FAC", "CGB"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"         # 8강·8강 재경기('Quarter-Finals Deciders')
        if r.startswith("6th round") or r.startswith("sixth round"): return "dk"   # FA컵 6라운드(재경기 포함) = 8강
        if cid == "CGB" and r.startswith("fifth round"): return "dk"
        return "dc"                                      # 2~5라운드·16강·재경기
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"          # 1997-98 조별, 2002-03 1·2차 조별
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        sys.exit("모르는 챔스 라운드 " + rnd)
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"    # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"          # 2004-05 조별
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 2·3라운드·32강('intermediate stage')·16강·8강
    if cid == "EPP":                                     # 컵위너스컵 1998-99 1라운드: 호나우두·인자기·피구 선례(유로파 토너먼트)
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "UI": return "elq"                         # 인터토토컵: 램파드·델 피에로·인자기 선례(전 라운드 유로파 예선)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def score_pair(s):
    a, b = s.split(":")
    return int(a), int(b)

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]
    leg = 1 if "1st" in g["round"].lower() else 2
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]          # 다른 차전 리포트(홈 팀 기준 스코어)
        oh, oa = score_pair(o["final"])
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    # UEFA 대회(2020-21까지)·인터토토컵(램파드 선례)·리그컵 2라운드(긱스 선례): 원정 다득점·연장
    return [leg, home, fu, ft, 1, 1]

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
    return f"{s}-{str(s + 1)[2:]}"

STRIP = {"fc", "afc", "cf"}
def core(n):
    """순위표 이름 맞춤용(‘Scarborough FC (- 2007)’ = ‘Scarborough’, ‘Stevenage Borough FC’ = ‘Stevenage Borough’)"""
    return " ".join(w for w in key(n).split() if w not in STRIP)

# 순위표: 리그 코드 -> 잉글랜드 단계(1~5부) 또는 외국 리그
TIER = {"EFD1": 1, "GB1": 1, "EFD2": 2, "GB2": 2, "GB3": 3, "GB4": 4}
RANKS = collections.defaultdict(dict)      # (tier, season) -> {key: (rank, n, label)}
RANKS_SRC = collections.defaultdict(dict)  # 같은 팀·시즌의 출처별 순위(대조용)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        lg, season = p[0], p[1].split(" ")[0]
        m = re.match(r"wiki-Football(League|Conference)-?(\w*)\(tier(\d)\)", lg)
        if m: tier = int(m.group(3)); src = "wiki"
        elif lg in TIER: tier = TIER[lg]; src = "tm"
        else: continue
        k = core(p[4])
        RANKS_SRC[(tier, season, k)][src] = (int(p[2]), int(p[3]))
        if src == "wiki" or k not in RANKS[(tier, season)]:   # 영어 위키백과(공식 최종 순위) 우선, 없으면 Transfermarkt
            RANKS[(tier, season)][k] = (int(p[2]), int(p[3]))
# 순위 출처 불일치(Transfermarkt 표 vs 영어 위키백과 표)
# 공식 최종 순위로 고친 것(Transfermarkt 표 오류; judgments.md 6절): (단계, 시즌, 이름) -> 순위
RANK_FIX = {(2, "1997-98", "Sheffield United"): 6}   # 1997-98 1부(2단계) 6위 = 승격 플레이오프 6번 시드(위키백과 플레이오프 표), TM 7위
for (tier, s, n), r in RANK_FIX.items():
    RANKS[(tier, s)][core(n)] = (r, RANKS[(tier, s)][core(n)][1])
RANK_DIFF = [(k, v) for k, v in RANKS_SRC.items() if len(v) > 1 and len({x[0] for x in v.values()}) > 1]

def half_up(x): return int(x + 0.5)

def ents_map(prefix, season=None):
    """기존 선수 자료의 '<prefix> <season> N위' 값(괄호 표시 허용), 다수값. season=None이면 시즌 무관"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + r"(\([^)]*\))? " + (re.escape(season) if season else r"\d{4}-\d\d") + r" (\d+)위( \(리그 수준 추정\))?$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(2))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

def mid(tab, r):
    """빈 순위: 앞뒤 기존 순위값 사이 직선(한 칸이면 가운데, 0.5 올림). 끝이면 None"""
    if r in tab: return tab[r], False
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up(tab[a] + (tab[b] - tab[a]) * (r - a) / (b - a)), True

# 잉글랜드 1부: 긱스 판정의 모형(2000-01 순위값 곡선 + 1996-97 보정 −80, 22팀은 위치 비례 보간)을 그대로 씀.
PL_BASE = ents_map("프리미어리그", "2000-01")
assert len(PL_BASE) == 20, PL_BASE
def pl_curve(r, n):
    if n == 20: return PL_BASE[r]
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return PL_BASE[i + 1] + (PL_BASE[i + 2] - PL_BASE[i + 1]) * t
def pl_offset(season):
    m = ents_map("프리미어리그", season)
    m = {r: v for r, v in m.items() if r in PL_BASE}
    if not m: return None
    d = [v - PL_BASE[r] for r, v in m.items()]
    return half_up(sum(d) / len(d))
PL_OFF_FIRST = -80     # 긱스 판정(1996-97 1·2위 기존 값 = 곡선 −80)
PL_USED = collections.OrderedDict()
def model_pl(season, r, n):
    first_div = int(season[:4]) <= 1991
    name = "퍼스트 디비전" if first_div else "프리미어리그"
    m = ents_map(name, season)
    if m:
        v, it = mid(m, r)
        if v is not None:
            est = int(season[:4]) <= 1996
            lab = f"{name} {season} {r}위" + (" (리그 수준 추정)" if est else "")
            if it: PL_USED[(season, r)] = ("사이값", v)
            return v, lab
    if int(season[:4]) <= 1996:
        v = half_up(pl_curve(r, n) + PL_OFF_FIRST)
        PL_USED[(season, r)] = ("곡선", v)
        return v, f"{name} {season} {r}위 (리그 수준 추정)"
    # 1997-98 이후 끝 순위: 가장 가까운 기존 값 + 기준 곡선 차이(긱스 선례)
    k = min(m, key=lambda x: abs(x - r))
    v = half_up(m[k] + PL_BASE[r] - PL_BASE[k])
    PL_USED[(season, r)] = ("끝", v)
    return v, f"{name} {season} {r}위 (추정, 이웃 순위값에 기준 곡선 차이)"

CH_FLAT = ents_map("챔피언십")          # 잉글랜드 2부 고정 순위값(시즌 무관)
L1_FLAT = ents_map("리그 원")           # 3부
L2_FLAT = ents_map("리그 투")           # 4부
def model_flat(tab, label, season, r):
    v, it = mid(tab, r)
    if v is None: return None
    return v, f"{label} {season} {r}위"

def model(tier, season, r, n):
    if tier == 1: return model_pl(season, r, n)
    if tier == 2: return model_flat(CH_FLAT, "챔피언십(2부)", season, r)
    if tier == 3: return model_flat(L1_FLAT, "리그 원(3부)", season, r)
    if tier == 4: return model_flat(L2_FLAT, "리그 투(4부)", season, r)
    if tier == 5: return 1300, f"잉글랜드 5부(컨퍼런스) {season} {r}위 (추정, 다른 선수 자료 잉글랜드 5부 1300과 같음)"
    return None

# 직접 추정/별도 확인(모두 judgments.md 6절 근거): (key, 시즌) -> (Elo, lv)
def _k(n): return key(n)
MAN = {
    (_k("SC Heerenveen"), "2004-05"): (1624, "에레디비시 2004-05 5위"),
    (_k("Sporting CP"), "2004-05"): (1716, "포르투갈 1부 2004-05 3위"),
    (_k("Vålerenga Fotball Elite"), "2003"): (1410, "노르웨이 2003 12위/14팀 (추정, 다른 선수 자료 노르웨이 1999 9위 1430과 하위권 1400 사이)"),
    (_k("FK Zeljeznicar Sarajevo"), "2002-03"): (1400, "보스니아 2002-03 2위 (추정, 다른 선수 자료 크로아티아 2012-13 4위 1430보다 낮게)"),
    (_k("Dinamo Tbilisi"), "2004-05"): (1400, "조지아 2004-05 1위 (추정, 다른 선수 자료 조지아 2022 3위 1369·4위 1350보다 높게)"),
    (_k("Ihud Bnei Sakhnin"), "2004-05"): (1400, "이스라엘 2004-05 10위/12팀 (추정, 다른 선수 자료 이스라엘 8위 1425보다 낮게)"),
    (_k("Trelleborgs FF"), "1994"): (1350, "스웨덴 1994 10위/14팀 (추정, 다른 선수 자료 할름스타드 1994 7위 1390보다 낮게)"),
    (_k("Ferencvárosi TC"), "1996-97"): (1430, "헝가리 1996-97 3위 (추정, 다른 선수 자료 헝가리 1·2위 1450보다 조금 낮게)"),
    (_k("FK Partizan Belgrade"), "1998-99"): (1520, "유고슬라비아 1998-99 1위 (추정, 다른 선수 자료 파르티잔 2008-09·2010-11 1위 1520과 같음)"),
    (_k("CSKA Sofia"), "1999-00"): (1480, "불가리아 1999-00 2위 (추정, 다른 선수 자료 불가리아 2위 1480과 같음)"),
    (_k("FC Zürich"), "1999-00"): (1450, "스위스 1999-00 (추정, 다른 선수 자료 취리히 1998-99 1450과 같음)"),
    (_k("Swindon Town"), "1995-96"): (1611, "리그 원(3부) 1995-96 1위 (추정, 다른 선수 자료 잉글랜드 3부 1999-00 1위 1611과 같음)"),
    (_k("MFK Dubnica"), "2005-06"): (1330, "슬로바키아 2005-06 8위/10팀 (추정, 다른 선수 자료 슬로바키아 1부 하위권 1330과 같음)"),
}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

EURO = ("CL", "CLQ", "UEFA", "EPP", "UI")
def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in EURO else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    ck = core(opp)
    for tier in (1, 2, 3, 4, 5):
        t = RANKS.get((tier, eu))
        if t and ck in t:
            r, n = t[ck]
            res = model(tier, eu, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], f"model t{tier}"))
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_schedule"]   # 현지 날짜(Transfermarkt 일정·리포트 날짜; API UTC는 쓰지 않음)

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

BEFORE = {}
EV_BY = collections.defaultdict(list)
for i, e in enumerate(EVENTS): EV_BY[e["gameId"]].append(i)
ORDER_PROB = []
for gid, idx in EV_BY.items():
    h = a = 0
    for i in idx:
        BEFORE[i] = (h, a)
        sh, sa = map(int, EVENTS[i]["score_home_away_after"].split("-"))
        if (sh, sa) != (h + (EVENTS[i]["side"] == "home"), a + (EVENTS[i]["side"] != "home")): ORDER_PROB.append(gid)
        if EVENTS[i]["side"] == "home": h += 1
        else: a += 1
    mins = [minute(EVENTS[i]["minute"])[0] for i in idx]
    if gid not in NO_CLOCK and gid in G and mins != sorted(mins) and not any(EVENTS[i]["minute"] == "121" for i in idx):
        ORDER_PROB.append(("분 순서", gid))
    if gid in INFO and INFO[gid]["final"] and gid in G:
        fh, fa = score_pair(INFO[gid]["final"])
        if (h, a) != (fh, fa) and G[gid]["gameState"] != "penalty_shootout" and gid not in MISSING_GOAL:
            print("리포트 골 수와 최종 스코어 다름:", gid, (h, a), (fh, fa))

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

NC_USED = collections.Counter()
for i, e in enumerate(EVENTS):
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa = e["shearer_scorer"] == "1", e["shearer_assist_other"] == "1"
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    ours = (e["side"] == "home") == our_home
    h, a = BEFORE[i]
    gf, ga = (h, a) if our_home else (a, h)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    if e["minute"] == "121":
        if not isg: sys.exit("시계 없는 도움 " + gid)
        k = NC_USED[gid]; NC_USED[gid] += 1
        mi, gf, ga, src = NO_CLOCK[gid][k]; dm = 0
        judg.append(("골 분 보충", d, opp, mi, f"{gf}-{ga}", src))
    else:
        mi, dm = minute(e["minute"])
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        pk = int(e["goal_desc"] == "Penalty")
        if gid == "3416890" and mi == 87: pk = 1      # 1991.1.23 맨유전 87분: 리포트 'Penalty'(시계 없음) = 위키백과 PK
        add_row("g", mi, dm, gf, ga, pk, 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        if e["own_goal"] == "1" or not ours:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "상대 자책골 유도(" + (e["assist_type"] or "유형 없음") + ")")); continue
        if e["assist_type"] in AUTO_EXCL_TYPES:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], AUTO_EXCL_TYPES[e["assist_type"]])); continue
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)
for gid, lst in NO_CLOCK.items():
    if NC_USED[gid] != len(lst): sys.exit("시계 없는 경기 골 수 불일치 " + gid)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[5] + r[6], 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3])
        if k in seen: continue
        seen.add(k)
        if not x[4].startswith("table") and not x[4].startswith("same"): print(x)
    print("PL 모형:", sorted(PL_USED.items()))
    print("순위 출처 불일치:", RANK_DIFF)
    print("골 순서 문제:", ORDER_PROB)
