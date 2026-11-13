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

# 출전 분 보정: Transfermarkt 교체 기록이 골 시각과 모순(교체 아웃 뒤 골) -> 90분(judgments.md 2절)
MIN_M_FIX = {"3434689": 90,   # 1989.10.3 요크전: TM 45분(시어러↔도드 교체로 적음), 위키백과 시어러 76분 골·11v11은 도드가 레이 월리스와 교체
             "998071": 90}    # 2002.12.26 볼턴전: TM 73분(루아루아와 교체)인데 같은 리포트에 시어러 79분 골, 다른 기록(스포츠몰) 89분 시어러 경고
M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), MIN_M_FIX.get(g["gameId"], int(g["playedMinutes"]))])
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

# ---------------------------------------------------------------- 요약
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
BOUND = [("1992-07-01", "souas"), ("1996-07-01", "blbas"), ("9999-12-31", "newas")]
def club_of(d):
    for u, k in BOUND:
        if d < u: return k
PER = collections.OrderedDict((k, [0, 0, 0, 0]) for _, k in BOUND)
for g in GAMES:
    if CLUB_KEY[g["club_id"]] != club_of(ldate(g)): sys.exit("클럽 경계 불일치 " + g["gameId"])
for m in M: PER[club_of(m[0])][0] += 1; PER[club_of(m[0])][3] += m[3]
for r in E: PER[club_of(r[9])][1 if r[0] == "g" else 2] += 1
if __name__ == "__main__" and "--stat" in sys.argv:
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(PER))
    for j in judg: print(j)
    print("단판", sorted(collections.Counter((r[3], r[7]) for r in E).items()))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
CLUBN = {"180": "Southampton", "164": "Blackburn Rovers", "762": "Newcastle United"}
OTHER_ROWS = collections.defaultdict(list)
for fn in sorted(os.listdir(os.path.join(ROOT, "src", "data"))):
    if not fn.endswith(".js") or fn in ("shr.js", "hon.js"): continue
    tx = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    mm = re.search(r"const (\w+)_E=(\[.*?\]);\n", tx, re.S)
    if mm:
        for r in json.loads(mm.group(2)): OTHER_ROWS[r[9]].append((mm.group(1), r))
CROSS = []
GD = {ldate(g): g for g in GAMES}
for d, g in GD.items():
    ck = key(CLUBN[g["club_id"]])
    oth = [(p, r) for p, r in OTHER_ROWS.get(d, []) if key(r[1]) == ck]
    for dd in (str(Date.fromordinal(Date.fromisoformat(d).toordinal() + k)) for k in (-1, 1)):
        for p, r in OTHER_ROWS.get(dd, []):
            if key(r[1]) == ck: CROSS.append(("날짜 하루 차이", d, dd, p, r[1]))
    if not oth: continue
    comp = comp_of(g["competitionId"], g["round"])
    for p, r in oth:
        if r[3] != comp or r[7] != ko_of(g): CROSS.append(("대회/단판 다름", d, p, r[3], comp, r[7], ko_of(g)))
        if len(r) > 14:
            mine = tie_of(g)
            exp = [mine[0], 1 - mine[1], mine[3], mine[2], mine[4], mine[5]] if mine else None
            if r[14] != exp: CROSS.append(("합산 다름", d, p, r[14], exp))
    ev = [(r[4], r[5], r[6]) for r in E if r[9] == d] + [(r[4], r[6], r[5]) for p, r in oth]
    ev.sort()
    if not all(b[1] >= a[1] and b[2] >= a[2] for a, b in zip(ev, ev[1:])): CROSS.append(("스코어 순서 어긋남", d, ev))
    CROSS.append(("같은 경기", d, g["opponent"], sorted({p for p, _ in oth})))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[0] != "같은 경기": print(c)
    print(collections.Counter(c[0] for c in CROSS), len([c for c in CROSS if c[0] == "같은 경기"]))

# ---------------------------------------------------------------- 설명(NOTE)
SRC = ELO_SRC
P = PER
NOTE_LINES = [
    f"앨런 시어러(사우샘프턴·블랙번 로버스·뉴캐슬 유나이티드)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 첼시전 ~ {d_(M[-1][0])} 선덜랜드전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·잉글랜드 대표팀 경기 제외. 2006년 은퇴",
    f"클럽별 경기·골·도움: 사우샘프턴(1988~1992) {P['souas'][0]}·{P['souas'][1]}·{P['souas'][2]}, 블랙번 로버스(1992~1996) {P['blbas'][0]}·{P['blbas'][1]}·{P['blbas'][2]}, 뉴캐슬 유나이티드(1996~2006) {P['newas'][0]}·{P['newas'][1]}·{P['newas'][2]}. 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분(연장·교체 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있거나 리그 밖 대회인 409경기 리포트를 확인, 리포트 골·도움 수가 선수 경기 성적과 모든 경기에서 같음). FotMob에는 2010-11 이전 경기 기록이 없어 대조하지 못함. 출전 분이 없어 90분으로 추정한 경기는 없음",
    "경기 수·골은 영어 위키백과 클럽·시즌·대회별 기록과 같음(블랙번 171경기 130골, 뉴캐슬 405경기 206골). 사우샘프턴은 위키백과 158경기 43골과 달리 150경기 38골: 위키백과 '기타' 칸의 풀 멤버스컵(제니스 데이터 시스템스컵) 8경기 5골(1990-91 2경기 2골, 1991-92 6경기 3골)은 Transfermarkt에 경기가 없고, 위키백과 시즌 페이지 경기 상자에도 시어러 출전 여부가 경기마다 나오지 않아(시즌 합계만 있음) 넣지 않음(경기별 출전 근거가 없음)",
    "골: 자책골 없음. PK 골 67개는 Transfermarkt 골 유형 'Penalty'(선수 경기 성적 PK 골 수와 같음). PK가 막힌 뒤 리바운드로 넣은 골 2개(1994.12.10 사우샘프턴전 13분, 2004.3.20 찰턴전 77분)는 PK 골이 아님. 1991.1.26 코번트리전(FA컵 4라운드) 50분 골은 위키백과 경기 상자·코번트리 텔레그래프 득점 목록이 PK로 적었지만 같은 기사 본문은 'PK를 옆으로 찼다'고 적고 Transfermarkt도 PK 골이 아니라고 적어 일반 골로 셈",
    "골 시각 보충: 1989~1996년 컵 경기 29개는 Transfermarkt 리포트에 골 시각이 없고 골 목록이 팀별로 묶여 순서도 실제와 다름(예: 1990.11.27 크리스털 팰리스전, 1991.1.23 맨유전). 이 가운데 시어러 골이 있는 15경기 21골은 다른 출처로 분·골 전 스코어를 정함: 사우샘프턴 10경기 13골은 영어 위키백과 시즌 페이지 경기 상자(1989.10.3 요크 10·76분, 1990.9.25 로치데일 46·75분, 1990.11.27 크리스털 팰리스 59분, 1991.1.16 맨유 71분, 1991.1.23 맨유 52·87분 PK, 1991.9.24 스카버러 17·27분, 1991.10.30 셰필드 웬즈데이 81분, 1992.2.26 볼턴 28분), 1991.1.5 입스위치전 35분 동점골(0-1에서)은 Soccer America 결과표·사우샘프턴 팬 사이트 경기 기록, 1991.1.26 코번트리전 50분(0-1에서)은 코번트리 텔레그래프 기록",
    "블랙번 리그컵 5경기 8골(1992.9.23 허더즈필드 원정 1골, 1992.10.6 허더즈필드 홈 2골, 1992.10.28 노리치 1골, 1992.12.9 왓퍼드 2골, 1993.9.21 본머스 1골)은 골 시각을 확인한 출처가 없어 45분으로 추정하고, 골 전 스코어는 Transfermarkt 골 목록 순서(시어러 골이 먼저)로 둠(추정). 본머스전은 유일한 골이라 0-0이 확실함. 1992.10.6 허더즈필드전은 연장까지 간 경기지만 시어러 골은 정규시간 골로 둠",
    "1998.2.4 스티버니지전(FA컵 4라운드 재경기 2-1)은 Transfermarkt 리포트에 스티버니지 골이 빠져 있어 뉴캐슬 구단 경기 기록(nufc.com)·BBC 기사로 확인: 스티버니지 크로쇼 74분 골이 시어러 16·65분 골 뒤라 골 전 스코어는 0-0·1-0",
    "골 시각이 위키백과 경기 상자와 1~4분 다른 사우샘프턴 리그 경기(1988.4.9 아스널전 34분/33분, 1991.4.13 선덜랜드전 85/83분, 1992.4.4 QPR전 68/64분 등)와 1991.9.7 QPR전(Transfermarkt 45분, 위키백과 1분)은 Transfermarkt 시각을 씀(어느 쪽이든 골 전 스코어 같음). 2002.12.26 볼턴전(3-4 패)은 Transfermarkt가 시어러 8·79분·아메오비 71분, 스포츠몰 경기 기록이 아메오비 8분·시어러 71·80분으로 갈려 Transfermarkt 기록을 씀(첫 골 전 스코어 0-1, 둘째 골 2-4)",
    f"도움: 모두 2014년 8월 이전이라 Transfermarkt 경기 리포트 단일 출처(클로제·인시녜·긱스 선례). Transfermarkt 도움 94개에서 상대 자책골에 준 도움 1개(2005.5.15 첼시전 33분 제레미 자책골, 유형 'Shot on goal')를 빼 {NA}개. 시어러 본인 PK 골에 본인 도움으로 적힌 7개(PK 유도 표기)는 원래 94개에 들어 있지 않음. PK 유도·슈팅 리바운드로 적힌 다른 도움은 없음. 도움 유형 칸이 빈 21개는 일반 도움으로 셈. 1992년 이전 사우샘프턴 도움은 Transfermarkt에 3개뿐이라 실제보다 적을 수 있음. 프리미어리그 공식 집계(검색 요약)는 리그 도움 64개, Transfermarkt 리그 도움 68개",
    "출전 분: Transfermarkt 그대로(아래 두 경기만 고침). 1989.10.3 요크전(리그컵)은 Transfermarkt가 45분 교체로 적었지만 위키백과 경기 상자에 시어러 76분 골이 있고 11v11은 그 교체를 다른 선수(레이 월리스)로 적어 90분, 2002.12.26 볼턴전은 Transfermarkt가 73분 교체로 적었지만 같은 리포트에 시어러 79분 골이 있어 90분으로 둠. 연장까지 뛴 경기 10개(120분), 승부차기로 끝난 경기 3개(1992.2.5 맨유전 FA컵 재경기, 1998.11.11 블랙번전 리그컵, 2003.8.27 파르티잔전 챔스 예선)는 Transfermarkt 출전 분 그대로",
    "날짜: Transfermarkt 일정·리포트 날짜(현지)를 씀. 선수 경기 성적(API)의 UTC 날짜는 726경기 중 354경기가 하루 앞서므로 쓰지 않음. 위키백과 사우샘프턴 시즌 페이지는 1992.2.5 맨유전·1992.2.26 볼턴전 FA컵 재경기를 하루 앞 날짜로 적었지만 Transfermarkt·FA컵 시즌 페이지·11v11 날짜를 따름",
    f"상대 Elo(기록 {len(E)}개: 같은 팀·시즌 통합표 {SRC['팀×시즌 통합표']}, 순위표+기존 순위값·모형 {SRC['순위표+리그 모형']}, 직접 추정 {SRC['직접 추정']}): 같은 팀·시즌 다른 선수 자료 값 → 직접 추정 → 그 시즌 최종 순위를 기존 리그 순위값에 넣은 값 순으로 씀. 같은 경기 다른 선수 자료(긱스·판니스텔로이·루니·베컴·램파드·제라드·앙리 등 36경기)는 모두 상대 팀 쪽 기록이라 상대 Elo는 겹치지 않음",
    "순위: 잉글랜드 1부 1989-90~1991-92와 2~4부 1989-90~1995-96·2000-01·2001-02는 영어 위키백과 최종 순위표(공식 순위; Transfermarkt 표는 이 시기 동률 순서가 달라 2부에서만 50팀 가까이 다름), 나머지는 Transfermarkt 순위표. 셰필드 유나이티드 1997-98 2부는 Transfermarkt 7위가 아니라 6위(승격 플레이오프 6번 시드), 파르티잔 1998-99는 Transfermarkt 2위가 아니라 우승(나토 공습으로 24라운드에서 중단, 1위로 확정)",
    "잉글랜드 1부 1987-88~1996-97은 리그 수준 추정(lv에 '리그 수준 추정'): 같은 시즌 기존 순위값이 있으면 그 사이 직선(한 칸이면 가운데), 없는 순위·시즌은 긱스 판정의 모형(2000-01 프리미어리그 순위값을 곡선으로, 1996-97 기존 값에서 구한 보정 −80, 21·22팀 시즌은 위치 비례 보간)을 씀(1987-88 아스널 6위 1707, 1989-90 QPR 11위·루턴 17위, 1990-91 7개 순위, 1993-94·1995-96 1위 맨유 1898). 1997-98 이후 1부는 기존 순위값(빈 순위는 앞뒤 가운데). 2부는 챔피언십 고정 순위값, 3부는 리그 원 고정 순위값, 4부는 리그 투 고정 순위값(빈 순위는 앞뒤 사이 직선), 5부 컨퍼런스(스티버니지 1997-98 15위)는 1300(추정)",
    "직접 추정(모두 lv에 '추정'): 스윈던 1995-96 3부 1위 1611, 트렐레보리 1994 10위 1350, 페렌츠바로시 1996-97 3위 1430, 파르티잔 1998-99 1위 1520, CSKA 소피아 1999-00 2위 1480, 취리히 1999-00 1450, 젤레즈니차르 2002-03 보스니아 2위 1400, 발레렝아 2003 12위 1410, 디나모 트빌리시 2004-05 조지아 1위 1400, 브네이 사흐닌 2004-05 10위 1400, 두브니차 2005-06 슬로바키아 8위 1330. 순위표로 확인해 기존 순위값을 쓴 것: 헤이렌베인 2004-05 5위 1624, 스포르팅 2004-05 3위 1716",
    "대회 비중: 커뮤니티 실드(1994·1996)는 국내컵 결승 비중. FA컵·리그컵은 16강(FA컵 5라운드·리그컵 4라운드)까지 낮은 비중, 8강 이후(FA컵 6라운드·리그컵 5라운드부터)와 준결승·결승, 재경기는 해당 라운드 비중. 챔스 조별(1997-98, 2002-03 1·2차 조별), 챔스 예선 3라운드, UEFA컵 1라운드와 인터토토컵(2005, 3라운드·준결승)은 유로파 예선, UEFA컵 조별(2004-05)은 유로파 조별, UEFA컵 2·3라운드·32강·16강·8강과 컵위너스컵 1998-99 1라운드는 유로파 토너먼트, UEFA컵 준결승(2003-04)은 준결승 비중",
    f"두 경기 합산(UEFA 대회·인터토토컵·리그컵 2라운드) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음). 2차전 기록의 1차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 사우샘프턴·블랙번은 기본 8월 1일 기준, 뉴캐슬은 7월 10일 기준(2005.7.17·7.23·7.27 인터토토컵이 2005-06). 클럽 구분: 1992.7.1 전 사우샘프턴, 1996.7.1 전 블랙번 로버스, 이후 뉴캐슬(마지막 경기 1992.5.2·1996.4.17, 첫 경기 1992.8.15·1996.8.11)",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 프리미어리그 1994-95(블랙번), 올해의 선수 1994, 프리미어리그 올해의 선수 5회(1994-95·1996-97·1998-99·1999-00·2002-03, Transfermarkt 표기), 득점왕(프리미어리그 1994-95 34골·1995-96 31골·1996-97 25골, UEFA컵 2003-04 6골·2004-05 11골). 유로 1996 득점왕은 대표팀 기록이라 뺌. FA컵 준우승(1998·1999)은 Transfermarkt 페이지에 없어 넣지 않음",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM "]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE):
        sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6], r[13])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mdates = collections.Counter(m[0] for m in M)
for d, rs in by.items():
    gs = sorted({(r[5], r[6], r[4]) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
    for a, b in zip(gs, gs[1:]):
        if b[0] < a[0] or b[1] < a[1] or b[2] < a[2]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[0] == "a" and r[13] in ME_TM: problems.append(("본인 도움", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if r[4] > 90 and not r[11] and not r[10]: problems.append(("정규시간 90분 초과인데 연장 표시 없음", r))
    if len(r) > 14 and r[7] != 0: problems.append(("합산인데 단판", r))
mm = {m[0]: m for m in M}
GBYDATE = {ldate(g): g for g in GAMES}
for r in E:
    m = mm.get(r[9])
    if m and m[1] != r[1]: problems.append(("상대 이름 다름", r[9], r[1], m[1]))
    if m and m[2] != r[3]: problems.append(("대회 다름", r[9], r[3], m[2]))
    gm = GBYDATE.get(r[9])
    if gm and gm["gameId"] not in MIN_M_FIX and r[4] <= 90 and int(gm["playedMinutes"]) < 90 and gm["gameState"] == "regularly_terminated":
        pm = int(gm["playedMinutes"])
        if gm["isStarting"] == "True" and r[4] > pm + 2: problems.append(("선발인데 골·도움 분이 교체 아웃 뒤", r, pm))
        if gm["isStarting"] != "True" and r[4] < 90 - pm - 2: problems.append(("교체 투입 전 골·도움", r, pm))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const SHR_E={J(E)};\nconst SHR_M={J(M)};\nconst SHR_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "rank_source_diffs": [[list(k), v] for k, v in RANK_DIFF], "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)} · 클럽 {dict(PER)}")
