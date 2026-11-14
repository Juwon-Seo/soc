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
        "sport", "cd", "ud", "rcd", "sv", "as", "ss", "milan", "inter", "madrid", "ca", "fk", "sk", "ssc", "us", "balompie", "club", "deportivo", "sporting", "bilbao"}
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

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NOTE_LINES = [
    f"루이스 피구(스포르팅 CP·바르셀로나·레알 마드리드·인테르)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 마리티무전 ~ {d_(M[-1][0])} 아탈란타전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·포르투갈 대표팀·유소년 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{c[2]}({c[3]}) {c3(ST[c[0]])}" for c in CLUBS)
    + f". 출전 분 합계 {MIN_TOT:,}분(Transfermarkt 기록, 90분으로 추정한 경기 없음)",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(출전한 792경기 전부). 경기 수·골은 영어 위키백과 클럽·시즌·대회별 기록과 모두 같음(스포르팅 158·23, 바르셀로나 249·45, 레알 마드리드 245·58, 인테르 140·11). FotMob에는 피구의 클럽 경기별 자료가 없어(2004-05 이후 리그·챔스 시즌 합계만 있음) 골 시각·도움은 Transfermarkt 단일 출처. FotMob 시즌 출전 분은 Transfermarkt와 0~34분 차이",
    "골: Transfermarkt 리포트 골 137개를 모두 씀(자책골 없음). PK 골 34개는 골 유형 'Penalty'(선수 경기 성적의 PK 골 수와 같음). 2004.3.24 챔스 8강 모나코전 77분 골은 PK가 막힌 뒤 리바운드('Penalty rebound')라 PK로 안 셈. 레알 마드리드 2003-04 리그 골은 Transfermarkt·영어 위키백과 9골, 스페인어·이탈리아어 위키백과 8골(통산 137 대 136)로 갈리는데 경기별 근거를 찾지 못해 리포트 9골을 그대로 씀",
    f"도움: 모두 Transfermarkt 경기 리포트 도움(1995 이전과 2014년 이전이라 단일 출처, 경기마다 다른 출처로 대조하지 못함). 도움 {NA} = Transfermarkt 리포트 232 − PK 유도 4(1997.4.13 호나우두·1998.1.8·1999.4.4·2000.4.18 챔스 8강 2차전 연장 99분 히바우두) − 슈팅 리바운드('Shot on goal') 7(1995.10.31 셀라데스, 2000.10.25 구티, 2002.2.10·2002.4.14 모리엔테스, 2004.3.24 지단, 2005.1.16 호나우두, 2005.2.5 라울) − 상대 자책골에 준 도움 2(2000.2.20 에인세, 2002.1.31 라리나르). 본인 PK 골에 본인 이름이 도움 칸에 적힌 6건(1999.10.23·2000.10.17·2001.9.22·2002.12.21·2003.9.13·2004.5.8)은 도움이 아님. 유형 칸이 빈 도움 37개는 일반 도움으로 셈",
    "도움 자료의 공백: Transfermarkt 리포트에는 스포르팅 시절 피구 도움이 13개뿐임(1991-92 1, 1994-95 12; 1992~94 리포트는 득점자만 적음). 스페인어 위키백과는 시즌 합계로 1991-92 13·1992-93 10·1993-94 13·1994-95 17(통산 53)을 적었으나 어느 경기의 도움인지 알 수 없어 넣지 않음 — 스포르팅 시절 도움은 실제보다 약 40개 적음. 바르셀로나·레알 마드리드·인테르 시즌 도움은 스페인어 위키백과와 합계가 달라 쓰지 않음(제외 기준과 집계 범위 차이)",
    "Transfermarkt 리포트가 불완전한 경기: 2000.1.20 코파 델 레이 16강 1차전 오렌세전(상대 홈 골 빠짐), 1993.1.16 타사 데 포르투갈 파티마전(파티마 둘째 골 빠짐)은 피구 골·도움이 없어 영향 없음. 2000.4.26 코파 델 레이 준결승 2차전 아틀레티코전은 몰수패(0-3)로 피구 미출전. 승부차기로 끝난 1998.4.29 코파 델 레이 결승 마요르카전(1-1)과 2008.8.24 수페르코파 이탈리아나 로마전(2-2)은 Transfermarkt 점수가 승부차기 점수(6-5·8-7)라 골 목록의 정규시간·연장 점수를 씀. 연장전 골: 1997.6.28 코파 델 레이 결승 베티스전 115분, 2006.8.26 수페르코파 이탈리아나 로마전 94분(결승골)",
    "날짜는 경기 현지 날짜(Transfermarkt 경기 리포트 날짜; 선수 경기 성적의 날짜는 킥오프 시각이 없는 328경기에서 하루 앞섬). 인터콘티넨털컵 2000(보카전, 도쿄)·2002(올림피아전, 요코하마)는 라울·지단·호나우두 자료와 같은 날짜",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt·위키백과 순위표)를 기존 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['기존 팀×시즌 값']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "리그 모형: 라리가 1995-96~1998-99는 라울·호나우두 자료와 같은 모형(2003-04 순위값 1712.7에 평균 +13.5를 올리고 흩어짐 100.16 × 순위 곡선, 22팀·20팀 곡선, 기존 같은 시즌 순위값이 있으면 그 값; lv에 '리그 수준 추정'). 라리가 1999-00 이후는 같은 시즌 기존 순위값에 빈 순위는 앞뒤 값의 가운데. 포르투갈 1부(1989~95)는 기존 자료의 18팀 순위값(1위 1912 ~ 18위 1421), 포르투갈 2부(레사 1993-94 8위 1369)는 1367 + 2부 흩어짐 × 순위 곡선(추정), 세리에A 18팀·에레디비시 18팀은 기존 순위값, 세군다는 기존 모형",
    "직접 추정(모두 '추정'): 올리바이스 이 모스카비드(포르투갈 3부 남부 7위) 1994-95 1250, 아포엘 베에르셰바 1995-96 1425, 누만시아 1995-96·베니도름 1998-99·란사로테 2001-02(스페인 3부로 봄, 순위표 없음) 1350, 츠르베나 즈베즈다 1996-97 2위 1500, 스콘토 리가 1997 1위 1350, 브뢴뷔 1998-99 2위 1500(1위 1520과 3위 1480의 가운데), 아스널 1999-00 2위 1896(같은 시즌 1위 1962와 3위 1830의 가운데), 스파르타 프라하 1999-00 1위 1520(RSSSF 최종 순위로 우승 확인), 안더레흐트 2000-01 1위 1620, 아르트메디아 브라티슬라바 2005-06 2위 1400",
    "대회 비중: 타사 데 포르투갈·코파 델 레이·코파 이탈리아는 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중; 타사 결승 재경기도 결승), 수페르코파(스페인, 두 경기)·수페르코파 이탈리아나·UEFA 슈퍼컵(1997 두 경기, 2000·2002 단판)은 국내컵 결승, 인터콘티넨털컵은 클럽 월드컵, UEFA컵 1라운드는 유로파 예선·이후 라운드는 유로파 토너먼트, 컵위너스컵 1996-97은 유로파 토너먼트(호나우두 자료와 같음), 챔스 2차 조별(1999-2003)은 조별로 계산함",
    f"두 경기 합산(챔스·UEFA컵·컵위너스컵·UEFA 슈퍼컵 1997·코파 델 레이·수페르코파·코파 이탈리아) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음). 피구가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 7월 경기가 없어 네 클럽 모두 기본 8월 1일 기준. 클럽 구분은 1995.7.1 전 스포르팅, 2000.7.1 전 바르셀로나, 2005.7.1 전 레알 마드리드, 이후 인테르",
    "동료 자료 대조: 라울·지단·호나우두·이브라히모비치 자료와 같은 경기의 대회·상대 Elo·합산 정보가 모두 같고, 피구 도움→동료 골(라울 25·호나우두 21·지단 8·이브라히모비치 2)과 동료 도움→피구 골(라울 2·호나우두 2·지단 1)의 날짜·분·스코어가 같음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 챔스 2001-02, 라리가 1997-98·1998-99·2000-01·2002-03, 세리에A 2005-06~2008-09, 컵위너스컵 1996-97, 코파 델 레이 1996-97·1997-98, 코파 이탈리아 2005-06, 타사 데 포르투갈 1994-95, UEFA 슈퍼컵 1997·2002, 인터콘티넨털컵 2002(2000 준우승), 수페르코파 1996-97·2001-02·2003-04, 수페르코파 이탈리아나 2005~2008. 개인: 발롱도르 2000, FIFA 올해의 선수 2001, 포르투갈 올해의 선수 1995~2000. 월드컵·유로 등 대표팀 기록은 뺌",
    "은퇴: 2009년 7월 은퇴(마지막 클럽 경기 2009.5.31 아탈란타전)",
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
        if b[0] < a[0] or b[1] < a[1]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
    if len({(r[1], r[3]) for r in rs}) > 1: problems.append(("같은 날 상대·대회 다름", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
mm = {m[0]: m for m in M}
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if MISS: problems.append(("Elo 없음", MISS))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const FIG_E={J(E)};\nconst FIG_M={J(M)};\nconst FIG_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "elo_sources": ELO_SRC}, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
