#!/usr/bin/env python3
"""라이언 긱스: raw/ -> giggs.json + src/data/gig.js (판정 근거는 judgments.md)

  python3 players/giggs/build_giggs.py          # 쓰기
  python3 players/giggs/build_giggs.py --debug  # Elo 출처(통합표 외)
  python3 players/giggs/build_giggs.py --fm     # FotMob 대조(2010-11~)
  python3 players/giggs/build_giggs.py --cross  # 동료(호날두·루니·판니스텔로이·판 페르시) 자료 대조
  python3 players/giggs/build_giggs.py --stat   # 요약

입력: raw/tm_games.csv(출전, date_local_schedule = 현지 날짜), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
      raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv, raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/{ron,roo,nis,van}.js(같은 경기 동료 자료 대조), 아래 표(직접 판정).
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "gig.js")
OUT_JSON = os.path.join(HERE, "giggs.json")
ME = "라이언 긱스"
ME_TM = {"Ryan Giggs"}
CLUB = "mungg"

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
GAP = "2014-08-01"   # 긱스 은퇴(2014-05) 이후라 해당 도움 없음
AUTO_EXCL_TYPES = {"Penalty: Fouled player": "PK 유도", "Shot on goal": "슈팅 리바운드(Shot on goal)"}
# 골 분 보정: 리포트 시계 판독 오류. 키 "gameId|리포트분" -> 표시 분
MIN_FIX = {}
# 골 순서 보정(Transfermarkt 리포트 골 목록에 빠진 골): gameId -> 설명 (judgments.md)
# API isStarting=False인데 리포트 골 시각(15·41분)과 출전 42분이 선발·전반 교체 아웃을 보여줌 (2003.2.25 유벤투스전)
API_START_WRONG = {"1019613"}
MISSING_GOAL = {"3288630": "찰턴 골 누락(리포트 3골, 최종 3-1)"}
# 리포트가 상대 자책골로 적었지만 프리미어리그 의혹 골 위원회(2006.5.23 회람)가 긱스 골로 확정한 골: "gameId|리포트분"
OG_AS_GIGGS_GOAL = {"38040|3": "2006.3.26 버밍엄전 3분 프리킥 골(골키퍼 테일러 자책골로 기록됐다가 프리미어리그 의혹 골 위원회가 긱스 골로 확정)"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"EFD1", "GB1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("GBCS", "USC"): return "df"            # 커뮤니티 실드·UEFA 슈퍼컵 = 국내컵 결승 비중
    if cid in ("WEPO", "KLUB"): return "cwc"          # 인터콘티넨털컵 1999·클럽 월드 챔피언십 2000·클럽 월드컵 2008
    if cid in ("FAC", "CGB"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        if r.startswith("6th round") or r.startswith("sixth round"): return "dk"   # FA컵 6라운드 = 8강
        if cid == "CGB" and r.startswith("fifth round"): return "dk"                # 리그컵 5라운드 = 8강
        return "dc"                                    # 3~5라운드·16강·재경기
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"        # 1999-2003 2차 조별(Group 1·2·4) 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
        if r.startswith("first round") or r.startswith("second round"): return "clq"   # 1993-94 본선 1·2라운드(조별 전 토너먼트) = 챔스 예선 비중(내 판단)
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"  # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        return "elk"
    if cid == "EPP": return "elk"                      # 컵위너스컵 1991-92 16강(라울 판정 선례: 유로파 비중)
    if cid == "EL":
        return "elk"                                   # 2011-12 16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스 조별, 클럽 월드 챔피언십 2000 조별(리그식)
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]
    leg = 1 if "1st" in g["round"].lower() else 2
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    return [leg, home, fu, ft, 1, 1]   # UEFA 대회·리그컵 모두 원정 다득점·연장 적용(2020-21·2017-18까지)

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
MANUAL_ALIAS = {"inter milan": "inter", "wimbledon fc": "afc wimbledon", "torpedo moskau": "torpedo moscow",
                "bröndby if": "brondby if", "kispest honved fc": "budapest honved"}
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
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))
# 추가 순위표(영어 위키백과 확인분, raw에 없음): judgments.md 7절
EXTRA_RANKS = {}

def half_up(x): return int(x + 0.5)

def ents_map(prefix, season=None):
    """기존 선수 자료의 '<prefix> <season> N위' 값(추정 표시 없는 값, 다수값). season=None이면 시즌 무관(고정 순위값 리그)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + (re.escape(season) if season else r"\d{4}-\d\d") + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

def mid(tab, r):
    """빈 순위: 앞뒤 기존 순위값의 가운데(한 칸 이상 비면 그 사이 직선, 0.5 올림). 끝이면 None"""
    if r in tab: return tab[r], False
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up(tab[a] + (tab[b] - tab[a]) * (r - a) / (b - a)), True

# 잉글랜드 1부 모형 ---------------------------------------------------------
# 기존 값은 시즌마다 같은 곡선에 시즌 보정(상수)을 더한 꼴: 2000-01 순위값(1~20위 모두 있음)을 기준 곡선으로 삼는다.
PL_BASE = ents_map("프리미어리그", "2000-01")
assert len(PL_BASE) == 20
def pl_curve(r, n):
    """n팀(20·22) 시즌의 r위 -> 20팀 기준 곡선 값(22팀은 위치 비례로 선형 보간)"""
    if n == 20: return PL_BASE[r]
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return PL_BASE[i + 1] + (PL_BASE[i + 2] - PL_BASE[i + 1]) * t
def pl_offset(season):
    """그 시즌 기존 값들의 (값 - 2000-01 같은 순위 값) 평균(0.5 올림)"""
    m = ents_map("프리미어리그", season)
    if not m: return None
    d = [v - PL_BASE[r] for r, v in m.items()]
    return half_up(sum(d) / len(d))
PL_OFF_FIRST = pl_offset("1996-97")   # 가장 이른 기존 시즌(1·2위 값)의 보정: 1991-92~1995-96에도 그대로(계수 자료 없음, 추정)
PL_USED = collections.OrderedDict()
def model_pl(season, r, n, first_div):
    name = "퍼스트 디비전" if first_div else "프리미어리그"
    m = ents_map("프리미어리그", season)
    if m and int(season[:4]) >= 1997:
        v, it = mid(m, r)
        if v is None:   # 끝 순위: 가장 가까운 기존 값 + 기준 곡선 차이
            k = min(m, key=lambda x: abs(x - r))
            v = half_up(m[k] + PL_BASE[r] - PL_BASE[k]) if n == 20 else None
            PL_USED[(season, r)] = ("끝", v)
            return v, f"{name} {season} {r}위 (추정, 이웃 순위값에 기준 곡선 차이)"
        if it: PL_USED[(season, r)] = ("가운데", v)
        return v, f"{name} {season} {r}위"
    if m and r in m: return m[r], f"{name} {season} {r}위"
    off = PL_OFF_FIRST if int(season[:4]) <= 1996 else pl_offset(season)
    v = half_up(pl_curve(r, n) + off)
    PL_USED[(season, r)] = ("곡선", v)
    return v, f"{name} {season} {r}위 (리그 수준 추정)"

# 잉글랜드 2·3부(고정 순위값) -----------------------------------------------
CH_FLAT = ents_map("챔피언십")          # 1~24위 모두 있음, 시즌 무관 같은 값
L1_FLAT = ents_map("리그 원")           # 4·6·7·9·14·18·19·23위
def model_l(tab, label, season, r):
    v, it = mid(tab, r)
    if v is None: return None
    return v, f"{label} {season} {r}위"

def model(lg, season, r, n):
    """(Elo, lv) — 순위표 + 기존 순위값/리그 모형"""
    if lg == "EFD1": return model_pl(season, r, n, True)
    if lg == "GB1": return model_pl(season, r, n, False)
    if lg == "EFD2": return model_l(CH_FLAT, "챔피언십(2부)", season, r)
    if lg == "EFD3": return model_l(L1_FLAT, "리그 원(3부)", season, r)
    return None

RANK_LG = ["GB1", "EFD1", "EFD2", "EFD3"]

# 직접 추정/별도 확인(모두 설명에 근거): (key, 시즌) -> (Elo, lv)
def _k(n): return key(n)
MAN = {
    # 잉글랜드 3부(당시 서드 디비전 → 1992-93부터 세컨드 디비전): 기존 리그 원 순위값(고정), 순위는 judgments.md 7절 출처
    (_k("Brighton & Hove Albion"), "1992-93"): (1506, "리그 원(잉글랜드 3부) 1992-93 9위"),
    (_k("Wrexham AFC"), "1994-95"): (1495, "리그 원(잉글랜드 3부) 중위권 (추정, 순위표 미확인)"),
    (_k("York City"), "1995-96"): (1450, "리그 원(잉글랜드 3부) 1995-96 20위"),
    (_k("Southampton FC"), "2010-11"): (1583, "리그 원(3부) 2010-11 2위 (추정, 3위 1555에 챔피언십 2·3위 간격 28을 더함)"),
    (_k("Burton Albion"), "2005-06"): (1300, "잉글랜드 5부(컨퍼런스 내셔널) 2005-06 9위 (추정, 다른 선수 자료 잉글랜드 5부 1300과 같음)"),
    # 유럽 대회 상대: 순위(raw/ranks.txt 또는 judgments.md 7절 출처) + 그 리그의 기존 순위값, 없으면 추정
    (_k("Kispest–Honvéd FC"), "1993-94"): (1450, "헝가리 1993-94 2위 (추정, 다른 선수 자료 헝가리 2위 1450과 같음)"),
    (_k("IFK Göteborg"), "1994-95"): (1555, "스웨덴 1994 1위 (추정, 다른 선수 자료 알스벤스칸 1위 1555와 같음)"),
    (_k("Rotor Volgograd"), "1995-96"): (1450, "러시아 1995 7위 (추정, 다른 선수 자료 러시아 7위 1450과 같음)"),
    (_k("FC Porto"), "1996-97"): (1912, "포르투갈 1부 1996-97 1위"),
    (_k("Bröndby IF"), "1998-99"): (1520, "덴마크 1998-99 2위 (추정, 다른 선수 자료의 브뢴뷔 1995-96·1997-98 1위 1520과 같음)"),
    (_k("LKS Lodz"), "1998-99"): (1332, "엑스트라클라사 1998-99 12위"),
    (_k("Sociedade Esportiva Palmeiras"), "1999-00"): (1599, "브라질 세리에 A 1999 9위/22팀 (추정, 20팀 시즌 8위 1610·10위 1588의 가운데)"),
    (_k("FC Girondins Bordeaux"), "1999-00"): (1792, "리그1 1999-00 4위"),
    (_k("PSV Eindhoven"), "2000-01"): (1837, "에레디비시 2000-01 1위"),
    (_k("SK Sturm Graz"), "2000-01"): (1473, "오스트리아 2000-01 4위/10팀 (추정, 다른 선수 자료 오스트리아 분데스리가 4위 1473과 같음)"),
    (_k("RSC Anderlecht"), "2000-01"): (1764, "벨기에 1부 2000-01 1위"),
    (_k("Olympiacos Piraeus"), "2002-03"): (1690, "그리스 2002-03 1위 (추정, 다른 선수 자료 올림피아코스 1위 1690과 같음)"),
    (_k("Panathinaikos"), "2003-04"): (1690, "그리스 2003-04 1위 (추정, 다른 선수 자료 그리스 1위 1690과 같음)"),
    (_k("FC Dinamo 1948"), "2004-05"): (1500, "루마니아 2004-05 2위 (추정, 다른 선수 자료 루마니아 2위 1500과 같음)"),
}
FIXED = {}

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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    if cid in ("CL", "CLQ", "EL", "UEFA", "EPP", "USC", "WEPO", "KLUB"):
        seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)]
    else:
        seasons = [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    for s in seasons:
        if (k, s) in FIXED:
            e, lv = FIXED[(k, s)]; ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, e, lv, "fixed"))
            return e, lv
    for s in seasons:
        for lg in RANK_LG:
            t = RANKS.get((lg, s)) or EXTRA_RANKS.get((lg, s))
            if t and k in t:
                r, n = t[k]
                res = model(lg, s, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model"))
                    return res
    return None

# ---------------------------------------------------------------- 출전
def opp_name(g):
    return g["opponent"].strip()

def ldate(g):
    return g["date_local_schedule"]   # 현지 날짜(Transfermarkt 일정·리포트 날짜; API UTC는 쓰지 않음)

M = []
for g in GAMES:
    M.append([ldate(g), opp_name(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

BEFORE = {}
EV_BY = collections.defaultdict(list)
for i, e in enumerate(EVENTS): EV_BY[e["gameId"]].append(i)
for gid, idx in EV_BY.items():
    h = a = 0
    for i in idx:
        BEFORE[i] = (h, a)
        if EVENTS[i]["side"] == "home": h += 1
        else: a += 1
    if gid in INFO and INFO[gid]["final"] and gid in G:
        fh, fa = map(int, INFO[gid]["final"].split(":"))
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

for i, e in enumerate(EVENTS):
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa = e["giggs_scorer"] == "1", e["giggs_assist_other"] == "1"
    if not (isg or isa): continue
    inf = INFO[gid]
    ogtag = f"{gid}|{e['minute']}"
    our_home = inf["home_id"] == g["club_id"]
    side_home = e["side"] == "home"
    h, a = BEFORE[i]
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    tag = f"{gid}|{e['minute']}"
    mi, dm = minute(MIN_FIX.get(tag, e["minute"]))
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
    d = ldate(g); opp = opp_name(g)
    if ogtag in OG_AS_GIGGS_GOAL:
        judg.append(("자책골 표기를 긱스 골로 바꿈", d, opp, e["minute"], OG_AS_GIGGS_GOAL[ogtag]))
        add_row("g", mi, dm, gf, ga, 0, 0, tie, comp, ko, d, opp, cid, et); continue
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골(상대 득점으로 기록)")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        if e["own_goal"] == "1" or not ours:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "상대 자책골 유도")); continue
        if e["assist_type"] in AUTO_EXCL_TYPES:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], AUTO_EXCL_TYPES[e["assist_type"]])); continue
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k)
        if not x[4].startswith("table") and not x[4].startswith("same"): print(x)
    print("PL 모형 사용:", sorted(PL_USED.items()))
if __name__ == "__main__" and "--table" in sys.argv:
    seen = set()
    for x in ELO_LOG:
        if (x[4].startswith("table") or x[4].startswith("same")) and (x[1], x[2]) not in seen:
            seen.add((x[1], x[2])); print(x)

# ---------------------------------------------------------------- 요약
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
if __name__ == "__main__" and "--stat" in sys.argv:
    print(NG, NGo, NA, NPK, MIN_TOT, len(E))
    for j in judg: print(j)
    print("합산", sum(1 for r in E if len(r) > 14), len({r[9] for r in E if len(r) > 14}), "연장", [r[9:12] for r in E if r[10]])
    print("단판", sorted(collections.Counter((r[3], r[7]) for r in E).items()))
    print(sorted(collections.Counter(m[0][:4] + ("-07" if m[0][5:7] == "07" else "") for m in M).items()))
    print([m for m in M if m[0][5:7] in ("06", "07")][:20])
    print(M[0], M[-1])

# ---------------------------------------------------------------- FotMob 대조(2010-11~)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["giggs_scorer"] == "1" and e["own_goal"] != "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
FM_GAMES = 0
for gid, evs in TMG.items():
    if gid not in FM_EV or not FM_EV[gid]: continue
    FM_GAMES += 1
    fg = [r for r in FM_EV[gid] if r["cal_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower() or "penalty" in (f["goalDescription"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        h, a = map(int, t["score_home_away_after"].split("-")); fh, fa = map(int, f["newScore_home_away"].split("-"))
        if tpk != fpk or abs(tm_min - fm_min) > 1 or (h, a) != (fh, fa):
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], t["score_home_away_after"], f["time"], f["overloadTime"], f["newScore_home_away"], f["goalDescriptionKey"], f["suffix"]))
FM_A = collections.defaultdict(list)
for gid, lst in FM_EV.items():
    for r in lst:
        if r["cal_assist"] == "1" and gid in G: FM_A[gid].append(r)
TM_A_LATE = {}   # 2010-08~ TM 도움 (경기 id -> [(분, 득점자)])
for e in EVENTS:
    if e["giggs_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) >= "2010-08-01" and e["own_goal"] != "1":
        TM_A_LATE.setdefault(e["gameId"], []).append((e["minute"], e["scorer"], e["assist_type"]))
FM_A_DIFF = []
for gid, lst in TM_A_LATE.items():
    if gid not in FM_EV or not FM_EV[gid]:
        FM_A_DIFF.append(("FotMob 경기 자료 없음", gid, ldate(G[gid]), lst)); continue
    fm = [(r["time"], r["scorer"]) for r in FM_A.get(gid, [])]
    if len(fm) != len(lst): FM_A_DIFF.append(("도움 수 다름", gid, ldate(G[gid]), G[gid]["opponent"], lst, fm))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)
    print("FotMob 골 대조 경기", FM_GAMES)
    for x in FM_A_DIFF: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    t = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", t, re.S)
    return json.loads(m.group(1))
MATES = {"Ruud van Nistelrooy": ("nis.js", "NIS", "2001-07-01", "2006-07-28"), "Cristiano Ronaldo": ("ron.js", "RON", "2003-08-01", "2009-07-01"),
         "Wayne Rooney": ("roo.js", "ROO", "2004-08-01", "2014-05-31"), "Robin van Persie": ("van.js", "VAN", "2012-08-01", "2014-05-31")}
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items()}
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    if a[1] != b[1]: diffs.append(f"상대 이름 {a[1]}/{b[1]}")
    return diffs
def nm_eq(a, b): return norm(a) == norm(b)
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:   # 긱스 도움 → 동료 골
        if r[0] == "a" and nm_eq(r[13], nm) and lo <= r[9] < hi:
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("긱스 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:  # 동료 도움 → 긱스 골
        if x[0] == "a" and x[13] in ME_TM and lo <= x[9] < hi:
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→긱스 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:  # 같은 경기 Elo/lv/대회
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "연장"))]
                    if dd: CROSS.append(("같은 경기 다름", nm, r[9], r[1], dd))
                    break
    for x in ent:  # 동료 골에 TM 긱스 도움이 있는데 이 파일에 도움 행이 없음
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["giggs_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 긱스 도움을 뺀 동료 골(규칙대로 제외)", nm, x[9], x[4], tm[0]["assist_type"] or "유형 없음", tm[0]["own_goal"]))
    for e in EVENTS:  # TM 동료 도움 → 긱스 골이 동료 파일에 없음
        if e["giggs_scorer"] == "1" and e["gameId"] in G and nm_eq(e["assist_player"], nm):
            d = ldate(G[e["gameId"]])
            if lo <= d < hi and not any(x[0] == "a" and x[9] == d and abs(x[4] - minute(e["minute"])[0]) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움이 동료 파일에 없음", nm, d, e["minute"], e["assist_type"], e["goal_desc"]))
# 모든 기존 선수와 같은 경기(±1일) Elo·lv·대회 일치 점검(긱스 행 기준)
ENT_BY_DATE = collections.defaultdict(list)
for x in ENTS: ENT_BY_DATE[x["date"]].append(x)
for r in E:
    for dd_ in (r[9],):
        for x in ENT_BY_DATE.get(dd_, []):
            if key(x["opp"]) == key(r[1]) or _sub(key(x["opp"]), key(r[1])):
                if x["elo"] != r[2] or x["lv"] != r[12] or x["comp"] != r[3]:
                    CROSS.append(("같은 경기 다른 선수와 다름", x["p"], r[9], r[1], (x["elo"], x["lv"], x["comp"]), (r[2], r[12], r[3])))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] for c in CROSS if c[-1] == "같음"), collections.Counter(c[0] for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [(CLUB, None, "맨체스터 유나이티드", "1991~2014")]
for g in GAMES:
    if g["club_id"] != "985": sys.exit("클럽 id 이상 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_UNTYPED = sum(1 for e in EVENTS if e["giggs_assist_other"] == "1" and e["assist_type"] == "" and e["gameId"] in G and e["own_goal"] != "1")
SRC = ELO_SRC
NOTE_LINES = [
    f"라이언 긱스(맨체스터 유나이티드)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 에버턴전 ~ {d_(M[-1][0])} 헐 시티전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·웨일스 대표팀·영국 올림픽 대표팀 경기 제외. 2014년 5월 은퇴(5.19 발표)",
    f"클럽별 경기·골·도움: 맨체스터 유나이티드 {NG}·{NGo}·{NA}. 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분(연장·퇴장·교체 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있거나 리그 밖 대회인 모든 경기 리포트를 확인, 리포트 골·도움 수가 선수 경기 성적과 모든 경기에서 같음. 골·도움이 없는 리그 경기 435경기는 리포트 없이 출전 분만 사용). FotMob은 2010-11 이전 경기 기록이 없어 2010-11 이후 골·도움이 있는 36경기 중 경기 자료가 있는 24경기만 대조함",
    f"경기 수는 영어 위키백과 시즌·대회별 기록(963경기)과 모두 같음. 골은 위키백과 168골과 달리 {NGo}골: 아래 두 경기를 판정한 결과 위키백과와 한 골씩 반대로 나뉨(합계는 위키백과 168 + 1)",
    "골 판정 ① 2002.10.1 올림피아코스전 67분(챔스 조별, 3-0 앞선 골): Transfermarkt·ESPN·UEFA 경기 기사(제목 '긱스 2골')는 긱스 골로 적고 mufcinfo·영어 위키백과(2002-03 유럽 4골)는 상대 자책골로 처리해 갈림. Transfermarkt 기록(굴절된 슛)을 따라 긱스 골로 넣음(판단 근거가 갈리는 경기). ② 2006.3.26 버밍엄전 3분 프리킥 골: 경기 기록에는 골키퍼 테일러 자책골(긱스 도움)이었으나 프리미어리그 의혹 골 위원회(2006.5.23 회람)가 긱스 골로 확정(11v11 경기 기록·mufcinfo·영어 위키백과 리그 3골이 같음) → 자책골 도움이 아니라 긱스 골로 넣음. 이 골 때문에 2005-06 리그 골은 Transfermarkt 2골이 아니라 3골",
    "골: 자책골은 뺌(2014.1.7 선덜랜드전 리그컵 준결승 1차전 전반 추가시간의 긱스 자책골은 상대 득점). PK 골 5개(2010.4.24 블랙번전 2골, 2011.1.9 리버풀전 2분, 2012.10.31 첼시전 연장 120분, 2013.1.26 풀럼전 3분)는 Transfermarkt 골 유형 'Penalty'(경기 성적 PK 골 수와 같음). 1994.3.12 FA컵 8강 찰턴전은 Transfermarkt 골 목록에 찰턴 골이 빠져 있어(최종 3-1) 영어 위키백과 미러 한 곳의 기록(찰턴 레이번 77분 골, 칸첼스키스 72·76분 표기)으로 순서를 확인함: Transfermarkt 칸첼스키스 71·75분 표기와 분이 1분 다르지만 어느 쪽이든 찰턴 골이 뒤라, 긱스 도움이 된 칸첼스키스 75분 골은 2-0에서 나온 골이라 골 전 스코어 2-0",
    f"도움: 2014년 8월 이전 도움은 Transfermarkt 경기 리포트 단일 출처(클로제·인시녜·판니스텔로이 선례; 긱스는 2014.5 은퇴라 이후 도움 없음). Transfermarkt 도움 272개에서 PK 유도 5개(1995.10.1 리버풀전 칸토나, 2000.9.13 안더레흐트전 어윈, 2002.2.2 선덜랜드전·2004.5.22 밀월전 판니스텔로이, 2006.9.13 셀틱전 사하), 슈팅 리바운드('Shot on goal') 4개(1999.1.10 웨스트햄전·1999.5.26 바이에른 뮌헨전 솔샤르/셰링엄, 2002.2.10 찰턴전 솔샤르, 2007.10.6 위건전 호날두), 상대 자책골에 준 도움 2개(1993.10.20 갈라타사라이전 쉬퀴르, 1995.1.28 렉섬전 험스), 버밍엄 3분 골(위 ②, 긱스 골로 바뀜) 1개를 빼 {NA}개. 도움 유형 칸이 빈 {N_UNTYPED}개는 일반 도움으로 셈. 본인 PK 골의 본인 도움 표기는 없음",
    "도움 출처 차이: FotMob 경기 이벤트가 있는 2010-11 이후 경기 중 3개는 Transfermarkt 도움이 FotMob에 없음(2012.11.7 브라가전 80분 판 페르시 골은 FotMob이 안데르송 도움으로 적음, 2013.1.5 웨스트햄전 90+1분 판 페르시 골·2013.1.26 풀럼전 66분 에르난데스 골은 도움 칸 빈칸). 2014.8 이전이라 Transfermarkt 기준으로 넣음. 2011.1~5 12경기는 FotMob에 경기 자료가 없어 Transfermarkt 도움만 있음. FotMob 경력의 시즌별 도움(2003-04 이전은 '미기록')과 위키백과에는 도움 열이 없어 쓰지 않음. 1990년대 Transfermarkt 리포트는 도움 표기가 빠진 골이 있어 실제보다 적을 수 있음",
    "골 시각: Transfermarkt 리포트 시계 판독. FotMob 대조 경기에서 2012.2.26 노리치전 골만 다름(Transfermarkt 90+2분, FotMob 90분 → 추가시간 표기 사용). 연장 골 3개: 1992.3.11 미들즈브러전 리그컵 8강 재경기 106분, 1999.4.14 FA컵 준결승 재경기 아스널전 109분(결승골 솔로 질주), 2012.10.31 첼시전 리그컵 120분 PK. 1992.3.11 경기 리포트에서 미들즈브러 골 분이 121로 읽혀 골 순서(스코어)만 사용",
    "출전 분: Transfermarkt 그대로(추정 없음). 연장 경기(1992.3.11 미들즈브러전 리그컵 8강 재경기, 1994.4.10 올덤전·1999.4.11과 4.14 아스널전 FA컵 준결승, 1995.4.9 크리스털 팰리스전 FA컵 준결승 재경기, 2007.5.19 첼시전 FA컵 결승, 2012.10.31 첼시전 리그컵)과 승부차기로 끝난 경기(커뮤니티 실드 1993·1997·2003·2007·2008·2009, 챔스 결승 2008, 리그컵 결승 2009, FA컵 결승 2005 등)는 Transfermarkt 출전 분 그대로",
    "날짜: Transfermarkt 일정 페이지 날짜(현지)를 씀. 선수 경기 성적(API)의 UTC 날짜는 963경기 중 278경기가 하루 앞서므로 쓰지 않음(1990년대 경기가 대부분). 1999.11.30 인터콘티넨털컵(도쿄)·2000.1.6/1.8 클럽 월드 챔피언십(브라질)·2008.12.17 클럽 월드컵(요코하마)은 개최지 현지 날짜",
    f"상대 Elo(기록 {len(E)}개: 같은 경기 다른 선수 자료 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 통합표 {SRC['팀×시즌 통합표']}, 순위표+순위값·모형 {SRC['순위표+리그 모형']}, 직접 추정 {SRC['직접 추정']}): 같은 경기를 다룬 다른 선수 자료(호날두·루니·판니스텔로이·판 페르시·앙리 등) 값 → 같은 팀·시즌 다른 선수 자료 값 → 직접 추정 → 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 순위값에 넣은 값 순으로 씀",
    "잉글랜드 1부 1991-92~1996-97은 기존 자료가 거의 없어 리그 수준을 추정함(lv에 '리그 수준 추정'): 기존 순위값은 시즌마다 같은 곡선에 시즌 보정을 더한 꼴이라 2000-01 순위값(1~20위 모두 있음)을 곡선으로 삼고, 1996-97 기존 값(1위 맨유 1898·2위 뉴캐슬 1813 = 곡선 −80)의 보정 −80을 1991-92~1996-97 전체에 같이 적용(그 이전 시즌 보정 자료가 없어 같은 값으로 둠). 22팀 시즌(1991-92~1994-95)은 22개 순위를 20칸 곡선에 위치 비례 보간. 1997-98~1999-00처럼 기존 값이 일부만 있는 시즌은 앞뒤 기존 순위값의 가운데(여러 칸이면 직선), 끝 순위(1997-98 1위 아스널 1920)는 가장 가까운 기존 값에 곡선 차이를 더함. 1991-92 이전(1990-91) 퍼스트 디비전도 같은 모형. 영국 2부는 챔피언십 고정 순위값(1~24위), 3부는 리그 원 고정 순위값(1992-93 브라이턴 9위·1995-96 요크 20위 위키백과/검색 확인, 1994-95 렉섬은 순위 미확인이라 중위권 1495 추정), 5부 컨퍼런스 내셔널(번턴 앨비언 2005-06) 1300(추정)",
    "그 밖의 직접 추정(모두 lv에 '추정'): 켓스페스트-혼베드 1993-94 2위 1450, IFK 예테보리 1994 1위 1555, 로토르 볼고그라드 1995 7위 1450, 브뢴뷔 1998-99 2위 1520, 팔메이라스 1999 9위/22팀 1599, 슈투름 그라츠 2000-01 4위 1473, 올림피아코스 2002-03 1위 1690, 파나티나이코스 2003-04 1위 1690, 디나모 부쿠레슈티(FC Dinamo 1948) 2004-05 2위 1500, 사우샘프턴 2010-11 리그 원 2위 1583. 순위표로 확인해 기존 순위값을 쓴 것: 포르투 1996-97 1위 1912, 보르도 1999-00 4위 1792, PSV 2000-01 1위 1837, 안더레흐트 2000-01 1위 1764, 웃치 1998-99 12위 1332",
    "대회 비중: 커뮤니티 실드·UEFA 슈퍼컵은 국내컵 결승 비중. 인터콘티넨털컵(1999)·클럽 월드 챔피언십 2000(조별 B조 2경기, 리그식)·클럽 월드컵 2008 준결승은 클럽 월드컵 비중(조별은 리그식). FA컵·리그컵은 16강(4라운드)까지 낮은 비중, 8강 이후(FA컵 6라운드·리그컵 5라운드부터) 높은 비중, 재경기는 해당 라운드 비중. 챔스 1993-94 본선 1·2라운드(조별 전 토너먼트)는 예선 비중(판단), 조별(1999-2003 2차 조별 포함)·16강·8강·준결승·결승, 예선, UEFA컵 1라운드(1995-96)는 유로파 예선, 컵위너스컵 1991-92 16강(골·도움 없음)은 유로파 토너먼트 비중(라울 판정 선례)",
    f"두 경기 합산(챔스·예선·UEFA컵·컵위너스컵, 리그컵 준결승·2라운드) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 적용). 2차전 기록의 1차전 스코어는 Transfermarkt 경기 리포트로 채움. 긱스가 뛰지 않은 1차전이 쓰인 기록: 2005.1.26 첼시전 리그컵 준결승 2차전(1차전 0-0), 2005.8.24 데브레첸전 챔스 예선 2차전(1차전 3-0), 2011.3.15 마르세유전 챔스 16강 2차전(1차전 0-0)",
    "시즌 구분: 기본 8월 1일 기준(긱스 경기 중 6~7월 경기 없음. 맨유의 같은 경기는 호날두·루니·판니스텔로이·판 페르시 자료와 같은 시즌). 클럽은 맨체스터 유나이티드 하나",
    "같은 경기 동료 자료: 판니스텔로이(긱스 도움 20·판니스텔로이 도움 4)·루니(긱스 도움 17·루니 도움 6)·호날두(긱스 도움 4)·판 페르시(긱스 도움 5·판 페르시 도움 1)와 주고받은 골·도움은 날짜·분·골 전 스코어·대회·상대 Elo·수준 설명·합산 정보가 모두 같음(호날두 파일은 상대 이름을 짧은 표기로 적음). 호날두 파일에 없는 긱스 골의 호날두 도움 3개(2006.9.9 프리킥 도움·2007.12.8 패스 도움·2008.11.5 도움 유형 빈칸)는 호날두 파일 쪽에 도움 행이 없음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 프리미어리그 13회(1992-93·1993-94·1995-96·1996-97·1998-99·1999-00·2000-01·2002-03·2006-07·2007-08·2008-09·2010-11·2012-13), 챔스 2회(1998-99·2007-08), UEFA 슈퍼컵 1991, 인터콘티넨털컵 1999, 클럽 월드컵 2008(Transfermarkt는 2009로 표기), FA컵 4회(1994·1996·1999·2004), 리그컵 4회(1992·2006·2009·2010), 커뮤니티 실드 9회(1993·1994·1996·1997·2003·2007·2008·2010·2013), 올해의 선수(Footballer of the Year) 1996·2006. 준우승·개인 득점왕 기록은 Transfermarkt 페이지에 없어 넣지 않음",
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
mm = {m[0]: m for m in M}
GBYDATE = {ldate(g): g for g in GAMES}
for r in E:
    m = mm.get(r[9])
    if m and m[1] != r[1]: problems.append(("상대 이름 다름", r[9], r[1], m[1]))
    if m and m[2] != r[3]: problems.append(("대회 다름", r[9], r[3], m[2]))
    gm0 = GBYDATE.get(r[9])
    if m and r[4] > 90 and m[3] < 100 and not r[11] and gm0 and gm0["isStarting"] == "True": problems.append(("연장 분인데 출전 짧음", r))
    gm = GBYDATE.get(r[9])
    if gm and r[4] <= 90 and gm["gameDuration"] in ("", "90") and int(gm["playedMinutes"]) < 90:
        pm = int(gm["playedMinutes"])
        if gm["isStarting"] == "True" and r[4] > pm + 2: problems.append(("선발인데 골·도움 분이 교체 아웃 뒤", r, pm))
        if gm["isStarting"] != "True" and gm["gameId"] not in API_START_WRONG and r[4] < 90 - pm - 2: problems.append(("교체 투입 전 골·도움", r, pm))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const GIG_E={J(E)};\nconst GIG_M={J(M)};\nconst GIG_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_assist_diffs": FM_A_DIFF, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
