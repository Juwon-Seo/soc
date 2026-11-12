#!/usr/bin/env python3
"""Luís Figo: raw/ -> figo.json + src/data/fig.js (판정 근거는 judgments.md)

  python3 players/figo/build_figo.py            # 파일 쓰기
  python3 players/figo/build_figo.py --debug    # Elo 출처 로그
  python3 players/figo/build_figo.py --cross    # 동료(라울·지단·호나우두·이브라히모비치 등) 자료 대조

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골·도움), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv,
      raw/ranks.txt(순위표), elo/opponent_elo_by_team_season.csv·aliases.csv, src/data/*.js(git 추적 파일: 같은 경기 다른 선수 자료).
호나우두(rno.js)·지단(zid.js)·라울(rau.js) 빌드 스크립트를 바탕으로 함.
"""
import csv, json, os, re, sys, unicodedata, collections, subprocess
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "fig.js")
OUT_JSON = os.path.join(HERE, "figo.json")
ME = "3446"            # Transfermarkt 선수 id
ME_KO = "루이스 피구"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# ---------------------------------------------------------------- 판정 표
def ldate(g): return g["date_local_tm_report"]       # TM 경기 리포트(현지) 날짜. API date_utc는 328경기에서 하루 앞섬
def opp(g): return g["opponent"].strip()

# 리포트 골 목록이 불완전한 경기: 피구 골·도움이 있을 때만 영향(judgments.md 5절)
INCOMPLETE = {"2422591": "2000.1.20 코파 델 레이 16강 1차전 오렌세전(1-2): 홈 골 시각 없음",
              "4849793": "1993.1.16 타사 데 포르투갈 16강 파티마전(3-2): 파티마 둘째 골 시각 없음",
              "2422603": "2000.4.26 코파 델 레이 준결승 2차전 아틀레티코전: 몰수패 0-3, 골 목록 없음(피구 미출전)"}

# 승부차기 경기: API 점수는 승부차기 점수(6-5·8-7)라 골 전 스코어는 골 목록에서 구함
SHOOTOUT = {"2422282": "1998.4.29 코파 델 레이 결승 마요르카전(1-1 연장, 승부차기 5-4/6-5)", "923350": "2008.8.24 수페르코파 이탈리아나 로마전(2-2 연장, 승부차기 8-7)"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"PO1", "ES1", "IT1"}
CUPS = {"POPO", "CDR", "CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SCI", "SUC", "USC"): return "df"
    if cid == "WEPO": return "cwc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "EPP":                      # 컵위너스컵 1996-97: 호나우두 선례(유로파 비중)
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

def tie_rule(cid, d):
    """(원정 다득점, 연장)"""
    if cid in ("UEFA", "CL", "CLQ", "EPP", "USC"): return (1, 1)
    if cid in ("CDR", "SUC"): return (1, 1)
    if cid == "CIT": return (1, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"] or TIES_RAW[gid]["other_leg_id"]
    o = MI[oid]
    oh, oa = map(int, o["final"].split(":"))                # 다른 차전 리포트의 (홈, 원정)
    if o["home_id"] == G[gid]["club_id"]: return (oh, oa)
    if o["away_id"] == G[gid]["club_id"]: return (oa, oh)
    sys.exit("다른 차전 팀 불일치 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

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
SEQ_DIFF = []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        # 골 전 스코어: 득점 편에서 1을 뺀 값(리포트 순서가 틀려도 안전) — 직전 골 목록 스코어와 다르면 기록
        bh, ba = (h - 1, a) if e["side"] == "home" else (h, a - 1)
        if (bh, ba) != prev: SEQ_DIFF.append((gid, ldate(g), e["minute"], (bh, ba), prev))
        prev = (h, a)
        is_g = e["figo_scorer"] == "1" and not is_og(e)
        is_a = e["figo_assist_other"] == "1"
        if e["figo_self_assist"] == "1":
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if not (is_g or is_a): continue
        gf, ga = (bh, ba) if side == "h" else (ba, bh)
        if not ((e["side"] == "home") == (side == "h")) and not (is_a and is_og(e)):
            sys.exit("득점 편 이상 " + gid + " " + e["minute"])
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk:
                if e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
                judg.append(("PK 아님(PK가 막힌 뒤 리바운드 골)", ldate(g), opp(g), e["minute"], e["goal_desc"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

cnt = collections.Counter()
for r in raw_rows: cnt[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt[(gid, "g")] != int(g["goals"]): sys.exit("골 수 불일치 " + gid)

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
MANUAL_ALIAS = {"inter milan": "inter"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

def tracked_data():
    try:
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True, check=True).stdout.split()
        return [os.path.join(ROOT, x) for x in out if x.endswith(".js")]
    except Exception:
        import glob
        return sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js")))

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in tracked_data():
    b = os.path.basename(fn)
    if b in ("hon.js", "fig.js"): continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (P, oe, om)
BYDATE = collections.defaultdict(list)
for b, (P, oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "atletico", "calcio",
        "sport", "cd", "ud", "rcd", "sv", "as", "ss", "milan", "inter", "madrid", "ca", "fk", "sk", "ssc", "us"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = []
    for dd in (d,):
        for b, x in BYDATE.get(dd, []):
            if key(x[1]) == key(o) or toks(x[1]) & toks(o): cand.append((b, x))
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANK_NAME = {   # 위키백과·TM 표기가 TM 경기 상대 이름과 다른 팀(README: 이름 불일치)
    "FC Dinamo 1948": "Dinamo Bucuresti", "Leça FC": "Leca", "Académica Coimbra": "Académica",
    "Red Star Belgrade": "Red Star", "Skonto Riga (- 2016)": "Skonto", "FC Artmedia Bratislava": "Artmedia",
}
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
def half_up(x): return int(x + 0.5)

SA18 = [1969, 1884, 1837, 1808, 1793, 1780, 1762, 1743, 1728, 1713, 1704, 1697, 1690, 1676, 1657, 1645, 1633, 1614]
SEG = [1753, 1712, 1687, 1674, 1660, 1654, 1647, 1640, 1632, 1623, 1615, 1610, 1606, 1601, 1598, 1595, 1589, 1580, 1572, 1567, 1560, 1553]
# 포르투갈 1부 18팀: 기존 자료의 순위값(2002-03·2016-17~2024-25 등 시즌과 상관없이 같은 값)
PO18 = [1912, 1795, 1730, 1690, 1670, 1652, 1627, 1600, 1576, 1560, 1546, 1533, 1527, 1507, 1482, 1461, 1448, 1421]
ERE = [1837, 1735, 1677, 1642, 1624, 1608, 1587, 1563, 1542, 1528, 1516, 1504, 1499, 1482, 1459, 1441, 1430, 1406]

LL = collections.defaultdict(dict)
_tmp = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
for (k, s), vals in TABLE.items():
    for e, lv in vals:
        m = re.match(r"라리가 (\d{4}-\d\d) (\d+)위$", lv)
        if m: _tmp[m.group(1)][int(m.group(2))][e] += 1
LL = {s: {r: c.most_common(1)[0][0] for r, c in d.items()} for s, d in _tmp.items()}
def mid(pts, r):
    if r in pts: return pts[r], False
    lo = [k for k in pts if k < r]; hi = [k for k in pts if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up(pts[a] + (pts[b] - pts[a]) * (r - a) / (b - a)), True
def edge(tab, r, n, sd):
    k = min(tab, key=lambda x: abs(x - r))
    return half_up(tab[k] + sd * (curve(r, n) - curve(k, n)))
# 라리가 1994-95~1998-99 모형(라울·호나우두 판정과 같음): 1712.7 + 13.5 + 100.16 × 곡선
LL_OLD_MEAN = 1712.7 + 13.5
LL_SD = 100.16
INTERP = set()

def rank_model(lg, season, r, n):
    if lg == "ES1":
        m = LL.get(season, {})
        if int(season[:4]) <= 1998:
            if r in m: return m[r], f"라리가 {season} {r}위"
            return half_up(LL_OLD_MEAN + LL_SD * curve(r, n)), f"라리가 {season} {r}위 (리그 수준 추정)"
        v, it = mid(m, r)
        if v is None:
            v = edge(m, r, n, LL_SD); INTERP.add((season, r, v, "끝"))
            return v, f"라리가 {season} {r}위 (추정, 이웃 순위값에 순위 곡선 차이)"
        if it: INTERP.add((season, r, v))
        return v, f"라리가 {season} {r}위"
    if lg == "ES2":
        if n == 22: return SEG[r - 1], f"세군다(2부) {season} {r}위"
        return half_up(1624 + SD2 * curve(r, n)), f"세군다(2부) {season} {r}위"
    if lg == "PO1":
        if n == 18: return PO18[r - 1], f"포르투갈 1부 {season} {r}위"
        return None
    if lg == "PO2H":
        return half_up(1367 + SD2 * curve(r, n)), f"포르투갈 2부 {season} {r}위 (추정)"
    if lg == "IT1":
        if n == 18: return SA18[r - 1], f"세리에A {season} {r}위"
        return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "NL1":
        assert n == 18; return ERE[r - 1], f"에레디비시 {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANK_LG = ["ES1", "ES2", "PO1", "PO2H-wiki", "IT1", "NL1"]
def rank_lookup(k, s):
    for lg in RANK_LG:
        t = RANKS.get((lg, s))
        if t and k in t:
            r, n, _ = t[k]
            res = rank_model(lg.replace("-wiki", ""), s, r, n)
            if res: return res
    return None

# 순위표·기존 자료에 없는 상대(직접 추정, 모두 '추정') — judgments.md 6절
MAN = {
    ("CD Olivais e Moscavide", "1994-95"): (1250, "포르투갈 3부 1994-95 (세군다 지비상 남부 7위/18팀, 추정: 프랑스 4부 평탄값 1250과 같은 수준)"),
    ("Hapoel Beer Sheva", "1995-96"): (1425, "이스라엘 1995-96 10위/16팀 (추정, 다른 선수 자료의 이스라엘 8위 1425와 같은 수준)"),
    ("CD Numancia", "1995-96"): (1350, "스페인 3부 (추정, 스페인 3부 1350과 같음)"),
    ("Red Star Belgrade", "1996-97"): (1500, "유고슬라비아 1996-97 2위 (추정, 다른 선수 자료의 츠르베나 즈베즈다 2001-02 2위 1500과 같음)"),
    ("Skonto Riga (- 2016)", "1997-98"): (1350, "라트비아 1997 1위 (추정, 다른 선수 자료의 라트비아 1위 1350과 같음)"),
    ("Bröndby IF", "1998-99"): (1500, "덴마크 1998-99 2위/12팀 (추정, 다른 선수 자료의 1위 1520과 3위 1480의 가운데)"),
    ("Benidorm CD", "1998-99"): (1350, "스페인 3부 (추정, 스페인 3부 1350과 같음)"),
    ("Arsenal FC", "1999-00"): (1896, "프리미어리그 1999-00 2위 (추정: 같은 시즌 1위 1962와 3위 1830의 가운데)"),
    ("AC Sparta Praha", "1999-00"): (1520, "체코 1999-00 1위 (추정, 다른 선수 자료 스파르타 프라하 2001-02·2003-04 1520과 같음)"),
    ("RSC Anderlecht", "2000-01"): (1620, "벨기에 2000-01 1위 (추정, 다른 선수 자료 안더레흐트 2006-07 1위 1620과 같음)"),
    ("UD Lanzarote", "2001-02"): (1350, "스페인 3부 (추정, 스페인 3부 1350과 같음)"),
    ("FC Artmedia Bratislava", "2005-06"): (1400, "슬로바키아 2005-06 2위 (추정, 다른 선수 자료의 슬로바키아 1위 1400과 같음)"),
}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1:
        print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(RANK_NAME.get(o, o)) if o in RANK_NAME and False else key(o)
    euro = cid in ("CL", "CLQ", "UEFA", "EPP", "WEPO", "USC")
    s0 = eu(d)
    seasons = [s0, str(int(s0[:4])), str(int(s0[:4]) + 1)] if euro else [s0]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for s in seasons:
        if (o, s) in MAN:
            e, lv = MAN[(o, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for s in seasons:
        kk = key(RANK_NAME.get(o, o))
        res = rank_lookup(kk, s)
        if res:
            ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

# ---------------------------------------------------------------- 기록 행
E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (g["gameState"] != "regularly_terminated" and mi > 90 and dm == 0) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    for m in MISS: print("Elo 없음:", m)
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda x: x[0][1]):
        if v[0] != "table": print(d, o, v)
    print("SEQ_DIFF", SEQ_DIFF)
    print("judg", len(judg))

# ---------------------------------------------------------------- 클럽·시즌 (7월 경기가 없어 시즌은 기본 8월 1일)
CLUBS = [("spfg", "1995-07-01", "스포르팅 CP", "1989~1995", "Sporting CP"), ("fcbfg", "2000-07-01", "바르셀로나", "1995~2000", "Barcelona"),
         ("rmfg", "2005-07-01", "레알 마드리드", "2000~2005", "Real Madrid"), ("intfg", None, "인테르", "2005~2009", "Inter")]
TM_CLUB = {"336": "spfg", "131": "fcbfg", "418": "rmfg", "46": "intfg"}
def club_of(d):
    for k, u, *_ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {c[0]: c[2] for c in CLUBS}
ST = collections.OrderedDict((c[0], [0, 0, 0, 0]) for c in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
if "--debug" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print("last Sporting game", max(ldate(g) for g in GAMES if g["club_id"] == "336"), "first Barca", min(ldate(g) for g in GAMES if g["club_id"] == "131"),
          "last Barca", max(ldate(g) for g in GAMES if g["club_id"] == "131"), "first RM", min(ldate(g) for g in GAMES if g["club_id"] == "418"),
          "last RM", max(ldate(g) for g in GAMES if g["club_id"] == "418"), "first Inter", min(ldate(g) for g in GAMES if g["club_id"] == "46"), "last Inter", max(ldate(g) for g in GAMES if g["club_id"] == "46"))

# ---------------------------------------------------------------- 동료 자료 대조(다른 파일은 고치지 않음)
CROSS = []
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
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    return diffs
MATES = {"rau.js": "라울", "zid.js": "지단", "rno.js": "호나우두", "ibr.js": "이브라히모비치"}
for fn, nm in MATES.items():
    if fn not in OTHERS: continue
    P, ent, om = OTHERS[fn]
    mm = {(m[0]): m for m in om}
    for r in E:
        # 피구 도움 -> 동료 골 (같은 날·분 ±3·스코어)
        if r[0] == "a" and norm(r[13]).split()[-1] in norm(nm_full := {"라울": "Raul Gonzalez Raul", "지단": "Zinedine Zidane", "호나우두": "Ronaldo", "이브라히모비치": "Zlatan Ibrahimovic"}[nm]).split():
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append((f"피구 도움→{nm} 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and "igo" in str(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((f"{nm} 도움→피구 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    # 같은 경기(같은 날짜·같은 상대) 팀 단위 비교
    for x in ent:
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                CROSS.append(("같은 경기", nm, r[9], r[1], d or "같음"))
                break
    # 같은 경기에서 동료 파일 쪽 출전 행과 날짜·상대·대회 비교
    for m in om:
        for fm in M:
            if fm[0] == m[0] and key(fm[1]) == key(m[1]):
                CROSS.append(("출전 행", nm, m[0], fm[1], "같음" if fm[2] == m[2] else f"대회 {fm[2]}/{m[2]}"))
if "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
