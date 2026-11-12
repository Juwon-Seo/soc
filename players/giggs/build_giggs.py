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
MISSING_GOAL = {"3288630": "찰턴 골 누락(리포트 3골, 최종 3-1)"}

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
