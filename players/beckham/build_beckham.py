#!/usr/bin/env python3
"""데이비드 베컴 (Transfermarkt 3139): raw/ -> beckham.json + src/data/bec.js (판정 근거는 judgments.md)

  python3 players/beckham/build_beckham.py            # 파일 쓰기
  python3 players/beckham/build_beckham.py --debug    # Elo 출처 로그만 출력
  python3 players/beckham/build_beckham.py --stat     # 요약·동료 대조·FotMob 대조

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리),
      raw/tm_two_leg_ties.csv(다른 차전), raw/fotmob_events.csv(2010~13 골 대조), raw/ranks.txt(순위표),
      raw/fotmob/leagues/130_<연도>.json.gz(MLS 2010~12 서포터스 실드 순위), mls_ranks.txt(MLS 2007~09 전체 순위, 위키백과),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, gzip, html as HTML
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "bec.js")
OUT_JSON = os.path.join(HERE, "beckham.json")
ME = "3139"
ME_KO = "데이비드 베컴"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

def ldate(g): return g["date_local"]   # 유럽 클럽 = Transfermarkt 날짜(현지), LA 갤럭시 = API UTC → 미국 태평양 시간
def opp(g):
    n = HTML.unescape(g["opponent"])
    return re.sub(r"\s*\(\s*(\d{4})?\s*-\s*(\d{4})?\s*\)", "", n).strip()

# ---------------------------------------------------------------- 판정 표
# 2009.11.22 MLS컵 결승(레알 솔트레이크전): 1-1 뒤 연장, 승부차기 패. TM API는 90분이나 영어 위키백과 'MLS Cup 2009'
# 경기 상자에 베컴 교체 표시 없음(연장 포함 풀타임) → 120분.
MIN_FIX = {"983160": 120}
GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용(선수 활동 기간이 모두 이전)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "ES1", "IT1", "FR1", "MLS1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("FAC", "CGB", "CDR", "FRC"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"       # FA컵 6라운드(재경기 포함)·리그컵 5라운드·코파 델 레이·쿠프 드 프랑스 8강
        return "dc"
    if cid in ("GBCS", "USC", "SUC"): return "df"     # 커뮤니티 실드·UEFA 슈퍼컵·수페르코파 = 국내컵 결승
    if cid in ("WEPO", "KLUB"): return "cwc"          # 인터콘티넨털컵 1999·클럽 월드 챔피언십 2000
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"        # 1999-2003 2차 조별(Group 1~4) 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"  # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        return "elk"                                  # 2008-09 3라운드(32강)
    if cid == "CCL":
        if r.startswith("group"): return "ccc"
        if r.startswith("quarter"): return "ccck"
        if r.startswith("semi"): return "cccsf"
        if r.startswith("final"): return "cccf"
    if cid == "POUS":
        if r.startswith("final"): return "mlpf"       # MLS컵 결승
        if r.startswith("semi"): return "mlpsf"       # 콘퍼런스 결승(2009~11 단판, 2012 두 경기)
        return "mlp"                                  # 콘퍼런스 준결승(두 경기)·2012 녹아웃 라운드(단판)
    if cid == "SL": return "lck"                      # 북미 슈퍼리가 2007 준결승·결승 = 리그스컵 토너먼트(메시 2023 리그스컵 준결승·결승 선례)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g): return "leg" in g["round"].lower()
def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스·북중미 챔스 조별, 클럽 월드 챔피언십 2000 조별(리그식)
    return 1

def tie_rule(cid):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "CLQ", "UEFA"): return (1, 1)     # UEFA 대회 2020-21까지
    if cid == "CGB": return (1, 1)                     # 리그컵 두 경기(2017-18까지)
    if cid in ("CDR", "SUC"): return (1, 1)            # 스페인 국내 대회 2018-19까지
    if cid == "POUS": return (0, 1)                    # MLS 플레이오프 2009~2012: 합산, 원정 다득점 없음(2014년부터), 연장 뒤 승부차기
    if cid == "CCL": return (1, 0)                     # 북중미 챔스: 원정 다득점, 연장 없이 승부차기
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def tie_of(gid):
    g = G[gid]
    if not is_leg(g): return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"])
    leg = 1 if "1st" in g["round"].lower() else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    oid = TIES_RAW[gid]["other_leg_id"]
    if oid in G:
        ours, theirs = map(int, G[oid]["score_club_opp"].split("-"))
        if G[oid]["venue"] == G[gid]["venue"]: sys.exit("합산 홈 판정 이상 " + gid)
    else:
        o = MI[oid]; oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: ours, theirs = oh, oa
        elif o["away_id"] == g["club_id"]: ours, theirs = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == (s == "h"): sys.exit("합산 홈 판정 이상 " + gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    gid = g["gameId"]
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), MIN_FIX.get(gid, int(g["playedMinutes"] or 0))])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

def assist_reason(e):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

raw_rows, judg = [], []
api_a = collections.Counter()
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1           # 리포트 골 순서대로 득점 팀별로 셈(자책골은 득점 인정 팀 기준)
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("골 아님(베컴 자책골, 상대 득점으로 기록)", ldate(g), opp(g), e["minute"], e["goal_desc"])); continue
        if e["assist_id"] == ME and e["assist_type"].startswith("Handball"):
            judg.append(("도움 아님(베컴 핸드볼 반칙으로 내준 상대 PK, 도움 칸 표기)", ldate(g), opp(g), e["minute"], e["scorer"])); continue
        is_g = e["scorer_id"] == ME
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        if is_a:
            api_a[gid] += 1
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if api_a[gid] != int(g["assists"] or 0): sys.exit("도움 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))

# ---------------------------------------------------------------- 이름·기존 자료
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
MANUAL_ALIAS = {"inter milan": "inter", "wimbledon fc": "afc wimbledon", "real salt lake city": "real salt lake",
                "kansas city wizards": "sporting kansas city", "cd chivas usa": "chivas usa"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "bec.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)
def same_team(a, b):
    ka, kb = key(a), key(b)
    return ka == kb or _sub(ka, kb)
def near_dates(d):
    D = Date.fromisoformat(d)
    return [str(Date.fromordinal(D.toordinal() + k)) for k in (0, -1, 1)]
def same_match(o, d):
    cand = [(b, x) for dd in near_dates(d) for b, x in BYDATE.get(dd, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
def half_up(x): return int(x + 0.5)

def ents_map(prefix, season=None):
    """기존 선수 자료의 '<prefix> <season> N위' 값(추정 표시 없는 값, 다수값). season=None이면 시즌 무관"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + (re.escape(season) if season else r"\d{4}(-\d\d)?") + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e[12] or "")
        if m: c[int(m.group(m.lastindex))][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
def mid(tab, r):
    if r in tab: return tab[r], False
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up(tab[a] + (tab[b] - tab[a]) * (r - a) / (b - a)), True
def edge(tab, r, n, sd):
    k = min(tab, key=lambda x: abs(x - r))
    return half_up(tab[k] + sd * (curve(r, n) - curve(k, n)))

RANKS = collections.defaultdict(dict)
def add_rank(lg, season, r, n, team):
    RANKS[(lg, season)][key(team)] = (r, n, team)
LBL = {"GB1": "GB1", "FR1": "FR1", "WIKI-EN Football League First Division (tier 2)": "EFD2", "WIKI-EN Football League Second Division (tier 3)": "EFD3"}
def tm_season(lbl):
    m = re.search(r"(\d\d)/(\d\d)$", lbl)
    if m:
        a = int(m.group(1)); a = a + (1900 if a > 50 else 2000)
        return f"{a}-{m.group(2)}"
    return lbl
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[0] not in LBL: continue
        add_rank(LBL[p[0]], tm_season(p[1]), int(p[2]), int(p[3]), p[4])
with open(os.path.join(HERE, "mls_ranks.txt"), encoding="utf-8") as f:
    for line in f:
        if line.startswith("#") or not line.strip(): continue
        p = line.rstrip("\n").split("|")
        add_rank("MLS1", p[1], int(p[2]), int(p[3]), p[4])
FM_MLS_NAME = {"Red Bull New York": "New York Red Bulls", "Sporting Kansas City": "Sporting Kansas City", "DC United": "D.C. United",
               "Houston Dynamo FC": "Houston Dynamo", "Chicago Fire FC": "Chicago Fire", "Real Salt Lake": "Real Salt Lake City",
               "CF Montréal": "Montreal Impact", "Vancouver Whitecaps": "Vancouver Whitecaps FC"}
for y in ("2010", "2011", "2012"):
    d = json.load(gzip.open(os.path.join(RAW, "fotmob", "leagues", f"130_{y}.json.gz")))
    if str(d["details"]["selectedSeason"]) != y: sys.exit("FotMob MLS 시즌 다름 " + y)
    t = [x for x in d["table"][0]["data"]["tables"] if x["leagueName"] == "Supporters Shield"][0]["table"]["all"]
    t = [x for x in t if x["played"] > 0]     # 2012 표 끝의 0경기 줄(II팀 등) 3개 제외
    for x in t: add_rank("MLS1", y, x["idx"], len(t), FM_MLS_NAME.get(x["name"], x["name"]))

# 잉글랜드 1부(긱스 판정과 같은 모형): 2000-01 순위값을 기준 곡선으로, 시즌 보정은 그 시즌 기존 값 평균 차
PL_BASE = ents_map("프리미어리그", "2000-01")
assert len(PL_BASE) == 20
def pl_curve(r, n):
    if n == 20: return PL_BASE[r]
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return PL_BASE[i + 1] + (PL_BASE[i + 2] - PL_BASE[i + 1]) * t
def pl_offset(season):
    m = ents_map("프리미어리그", season)
    if not m: return None
    d = [v - PL_BASE[r] for r, v in m.items()]
    return half_up(sum(d) / len(d))
PL_OFF_FIRST = pl_offset("1996-97")
INTERP_USED = set()
def rank_model(lg, season, r, n):
    if lg == "GB1":
        m = ents_map("프리미어리그", season)
        if m and int(season[:4]) >= 1997:
            v, it = mid(m, r)
            if v is None:
                k = min(m, key=lambda x: abs(x - r)); v = half_up(m[k] + PL_BASE[r] - PL_BASE[k])
                INTERP_USED.add(("프리미어리그", season, r, v, "끝"))
                return v, f"프리미어리그 {season} {r}위 (추정, 이웃 순위값에 기준 곡선 차이)"
            if it: INTERP_USED.add(("프리미어리그", season, r, v))
            return v, f"프리미어리그 {season} {r}위"
        if m and r in m: return m[r], f"프리미어리그 {season} {r}위"
        off = PL_OFF_FIRST if int(season[:4]) <= 1996 else pl_offset(season)
        v = half_up(pl_curve(r, n) + off); INTERP_USED.add(("프리미어리그", season, r, v, "곡선"))
        return v, f"프리미어리그 {season} {r}위 (리그 수준 추정)"
    if lg == "EFD2":
        v, it = mid(ents_map("챔피언십"), r)
        return v, f"챔피언십(2부) {season} {r}위"
    if lg == "EFD3":
        v, it = mid(ents_map("리그 원"), r)
        if v is None: return None
        return v, f"리그 원(3부) {season} {r}위"
    if lg == "MLS1":
        m = ents_map("MLS", season); v, it = mid(m, r)
        if v is None:
            v = half_up(1581 + 58 * curve(r, n))   # 기존 MLS 순위값과 같은 식(평균 1581, 흩어짐 58, 2010·2011 값과 일치)
            INTERP_USED.add(("MLS", season, r, v, "모형"))
        elif it: INTERP_USED.add(("MLS", season, r, v))
        return v, f"MLS {season} {r}위"
    for pre, lab, sd in (("ES1", "라리가", 100.16), ("IT1", "세리에A", 91.3), ("FR1", "리그1", 100.16)):
        if lg == pre:
            m = ents_map(lab, season); v, it = mid(m, r)
            if v is None:
                v = edge(m, r, n, sd); INTERP_USED.add((lab, season, r, v, "끝"))
                return v, f"{lab} {season} {r}위 (추정, 이웃 순위값에 순위 곡선 차이)"
            if it: INTERP_USED.add((lab, season, r, v))
            return v, f"{lab} {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
# 직접 추정·별도 확인(모두 judgments.md 6절) — 아래에서 채움
exec(open(os.path.join(HERE, "man_beckham.py"), encoding="utf-8").read()) if os.path.exists(os.path.join(HERE, "man_beckham.py")) else None

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid, lgcid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1:
        (e, lv), _ = collections.Counter((x[2], x[12]) for b, x in cand).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same-multi", e, lv, sorted(vals)); return e, lv
    k = key(o); y = d[:4]
    if cid in ("MLS1", "POUS", "SL", "CCL"):
        seasons = [y]
    elif cid in ("CL", "CLQ", "UEFA", "USC", "WEPO", "KLUB"):
        s = eu(d); seasons = [s, s[:4], str(int(s[:4]) + 1)]
    else:
        seasons = [eu(d)]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    lgs = {"GB1": ["GB1", "EFD2", "EFD3"], "ES1": ["ES1"], "IT1": ["IT1"], "FR1": ["FR1"], "MLS1": ["MLS1"]}[lgcid]
    if cid in ("CL", "CLQ", "UEFA", "USC", "WEPO", "KLUB"): lgs = ["GB1", "FR1"]   # 유럽 대회 상대: raw 순위표에 있는 리그
    for lg in lgs:
        for s in seasons:
            t = RANKS.get((lg, s), {})
            if k in t:
                r, n, _ = t[k]
                res = rank_model(lg, s, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

CLUB_LG = {"985": "GB1", "418": "ES1", "1061": "MLS1", "5": "IT1", "583": "FR1"}
E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(g)
    elo, lv = opp_elo(opp(g), d, cid, CLUB_LG[g["club_id"]])
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)
if "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    print("보간·모형:", sorted(INTERP_USED))
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010~13)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["beckham_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "penalty" in (f["goalDescriptionKey"] or "").lower() or "pen" in (f["suffix"] or "").lower()
        a = mins(t["minute"])[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
        FM_CMP.append(("같음" if (tp == fp and abs(a - b) <= 1) else "다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["newScore_home_away"]))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None): d.append(f"단판/합산 {a[7]}{a[14] if len(a)>14 else ''}/{b[7]}{b[14] if len(b)>14 else ''}")
    if a[10] != b[10]: d.append("연장")
    if a[9] != b[9]: d.append(f"날짜 {a[9]}/{b[9]}")
    return d
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Beckham", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] in near_dates(x[9]) and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움→베컴 골", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] in near_dates(r[9]) and abs(x[4] - r[4]) <= 3 and same_team(x[1], r[1])]
            if hit: CROSS.append(("베컴 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] in near_dates(r[9]) and same_team(x[1], r[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "날짜", "단판"))]
                if dd: CROSS.append(("같은 경기 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm[1], m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
# 베컴 이름이 도움으로 적힌 다른 선수 골이 E에 도움으로 없는 경우(규칙으로 뺀 것 포함)
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 베컴 도움을 규칙대로 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("munbk", "2003-07-01", "맨체스터 유나이티드", "1992~2003"), ("rmbk", "2007-07-01", "레알 마드리드", "2003~2007"),
         ("lagbk", "2009-01-07", "LA 갤럭시", "2007~2008"), ("acmbk", "2009-06-30", "AC 밀란(임대)", "2009"),
         ("lagbk", "2010-01-02", "LA 갤럭시", "2009"), ("acmbk", "2010-06-30", "AC 밀란(임대)", "2010"),
         ("lagbk", "2013-01-31", "LA 갤럭시", "2010~2012"), ("psgbk", None, "파리 생제르맹", "2013")]
TM_CLUB = {"985": "munbk", "418": "rmbk", "1061": "lagbk", "5": "acmbk", "583": "psgbk"}
def club_of(d):
    for k, u, n, y in CLUBS:
        if u is None or d < u: return k
CN = {}
for k, u, n, y in CLUBS: CN.setdefault(k, n)
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CN)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({(r[9]) for r in E if len(r) > 14})
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club == "lagbk": return str(y)
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
EX = [j for j in judg if j[0] == "도움 제외"]
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])

if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), "untyped", UNTYPED)
    for j in judg: print("판정", j)
    print("스코어 불일치", SCORE_MISMATCH)
    for c in FM_CMP: print("FM", c)
    for c in CROSS: print("CROSS", c)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    for r in E:
        if len(r) > 14 or r[10] or r[4] > 90: print("합산/연장", r)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_beckham.py"), encoding="utf-8").read())

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
    gl = sorted([r for r in rs if r[0] == "g"], key=lambda r: (r[5] + r[6], r[4]))
    for a, b in zip(gl, gl[1:]):
        if b[5] < a[5] + 1 or b[6] < a[6]: problems.append(("스코어 역순", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
mm_ = {m[0]: m for m in M}
Gstart = {ldate(g): g["isStarting"] in ("True", "1") for g in GAMES}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > m[3] + 3 and not r[10] and Gstart[r[9]]: problems.append(("출전 분보다 늦은 기록", r, m))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const BEC_E={J(E)};\nconst BEC_M={J(M)};\nconst BEC_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_cmp": FM_CMP, "elo_sources": ELO_SRC, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
