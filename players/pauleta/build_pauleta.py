#!/usr/bin/env python3
"""파울레타 (Transfermarkt 3623): raw/ -> pauleta.json + src/data/pau.js (판정 근거는 judgments.md)

  python3 players/pauleta/build_pauleta.py            # 파일 쓰기
  python3 players/pauleta/build_pauleta.py --debug    # Elo 출처 로그만 출력
  python3 players/pauleta/build_pauleta.py --stat     # 요약·동료 대조
  python3 players/pauleta/build_pauleta.py --ties     # 합산 행 출력

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/ranks.txt(Transfermarkt 순위표), elo/opponent_elo_by_team_season.csv + aliases.csv,
      src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기 대조).
FotMob은 2010-11 이전 경기 자료가 없어 쓰지 않음(경력 2008년 끝).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "pau.js")
OUT_JSON = os.path.join(HERE, "pauleta.json")
ME = "3623"
ME_KO = "파울레타"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

def ldate(g): return g["date_local_best"]     # 리포트 현지 날짜(241경기), 리포트 없는 리그 226경기는 TM 일정 날짜
OPP_NAME = {"Матадор Пухов": "MSK Púchov"}
def opp(g):
    o = OPP_NAME.get(g["opponent"], g["opponent"])
    return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", o).strip()

# ---------------------------------------------------------------- 판정 표
MIN_FIX, MIN_EST = {}, {}       # 출전 분은 Transfermarkt 그대로(빈칸 0경기)
GAP = "2014-08-01"              # 이 전 도움은 TM 단일 출처 허용(경력 전체가 이전)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "ES1", "ES2"}
CUPS = {"FRC", "FRL", "CDR"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("FRCH", "SUC"): return "df"                   # 슈퍼컵류 = 국내컵 결승 비중
    if cid == "CL":
        if r.startswith("group"): return "clg"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"           # UEFA컵 1라운드 = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                          # 2·3라운드·32강(intermediate stage)·16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid == "UEFA": return (1, 1)     # UEFA 대회 2020-21까지 원정 다득점·연장
    if cid == "CDR": return (1, 1)      # 코파 델 레이 2018-19까지 원정 다득점·연장
    if cid == "SUC": return (1, 1)      # 수페르코파(에투·호나우지뉴·지울리 자료와 같음)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G and G[oid]["gameState"] != "penalty_shootout":
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, m["other_leg_score"].split(":"))     # 이 경기 홈 팀 기준 표기
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), g["round"])
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    gid = g["gameId"]
    row = [ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), MIN_FIX.get(gid, MIN_EST.get(gid, int(g["playedMinutes"] or 0)))]
    if gid in MIN_EST: row.append(1)
    M.append(row)

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

BEFORE_FIX = {}
raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e): judg.append(("본인 자책골(골 아님)", ldate(g), opp(g), e["minute"]))
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        if (gid, e["minute"]) in BEFORE_FIX: gf, ga = BEFORE_FIX[(gid, e["minute"])]
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk:
                if e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
                judg.append(("PK 아님(PK가 막힌 뒤 리바운드 골)", ldate(g), opp(g), e["minute"], e["goal_desc"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
NPK_API = sum(int(g["penGoals"] or 0) for g in GAMES)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
for gid in G:
    if gid in MI and gid not in EVS and MI[gid].get("final") not in (None, "", "0:0") and G[gid]["gameState"] != "penalty_shootout":
        SCORE_MISMATCH.append((gid, ldate(G[gid]), (0, 0), MI[gid]["final"]))
# 파울레타 골·도움이 있는 경기의 리포트 골 목록 점검: 2005.1.8 랑괴전만 해당(목록 0-6, 최종 1-6, 하프타임 0-3 = 21·29분 골 뒤 0-3이므로 빠진 랑괴 골은 후반 → 골 전 스코어 그대로)
GA_GAMES = {r[1] for r in raw_rows}
SM_GA = [x for x in SCORE_MISMATCH if x[0] in GA_GAMES]
if {x[0] for x in SM_GA} - {"2886240"}: sys.exit("골·도움 경기 리포트 불완전 " + str(SM_GA))

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
MANUAL_ALIAS = {"olympique lyon": "olympique lyonnais"}
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
    if b == "hon.js" or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "foot", "ball",
        "atletico", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss", "olympique", "milan", "inter", "madrid", "fk", "if",
        "deportivo", "san", "santa", "saint", "us", "ogc", "losc", "stade", "racing", "athletic", "girondins", "germain", "paris"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, collections.Counter((x[2], x[12]) for b, x in cand)

# ---------------------------------------------------------------- 순위표 + 리그 모형
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
SEG = [1753, 1712, 1687, 1674, 1660, 1654, 1647, 1640, 1632, 1623, 1615, 1610, 1606, 1601, 1598, 1595, 1589, 1580, 1572, 1567, 1560, 1553]  # 세군다 22팀(라울·호나우두·지울리 자료 고정값)

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e[12] or "")
        if m: c[int(m.group(1))][e[2]] += 1
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
SD1 = {"FR1": 100.16, "ES1": 100.16}
LGNAME = {"FR1": "리그1", "ES1": "라리가"}
INTERP_USED = set()
LADDER_FR1 = {}
for _n, _s in ((20, "2002-03"), (18, "2023-24")):
    _m = ents_map("리그1", _s)
    if sorted(_m) != list(range(1, _n + 1)): sys.exit("리그1 기준 순위표 불완전 " + _s)
    LADDER_FR1[_n] = [_m[i] for i in range(1, _n + 1)]

def rank_model(lg, season, r, n):
    if lg in LGNAME:
        m = ents_map(LGNAME[lg], season)
        if not m: return None
        v, it = mid(m, r)
        if v is None:
            if lg == "FR1" and n in LADDER_FR1:
                v = LADDER_FR1[n][r - 1]; INTERP_USED.add((lg, season, r, v, "표"))
                return v, f"{LGNAME[lg]} {season} {r}위"
            v = edge(m, r, n, SD1[lg]); INTERP_USED.add((lg, season, r, v, "끝"))
            return v, f"{LGNAME[lg]} {season} {r}위 (추정, 이웃 순위값에 순위 곡선 차이)"
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"{LGNAME[lg]} {season} {r}위"
    if lg == "FR2":
        m = ents_map("리그2", season)
        v, it = mid(m, r)
        if v is None: return half_up(1540 + SD2 * curve(r, n)), f"리그2(프랑스 2부) {season} {r}위"
        return v, f"리그2 {season} {r}위"
    if lg == "FR3":    # 프랑스 3부(나시오날): 리베리·벤제마 자료의 평균 1311 × 2부 흩어짐 순위 곡선(2005-06 6위 1338 등과 같은 식)
        return half_up(1311 + SD2 * curve(r, n)), f"프랑스 3부(나시오날) {season} {r}위 (추정)"
    if lg == "ES2":
        if n == 22: return SEG[r - 1], f"세군다(2부) {season} {r}위"
        return half_up(1624 + SD2 * curve(r, n)), f"세군다(2부) {season} {r}위"   # 20팀 시즌(1996-97): 호나우두 자료와 같은 2부 모형
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; SAME_MULTI = []
def opp_elo(o, d, cid, rnd=""):
    cand, vals = same_match(o, d)
    if vals:
        if len(vals) > 1: SAME_MULTI.append((o, d, dict(vals)))
        (e, lv), _ = vals.most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    k = key(o)
    s0 = eu(d)
    if (k, s0) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, s0)]).most_common(1)[0]
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s0); return e, lv
    if (k, s0) in MAN:
        e, lv = MAN[(k, s0)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for lg in ("FR1", "ES1", "FR2", "ES2", "FR3"):
        t = RANKS.get((lg, s0), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s0, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, s0)); return 0, "?"

# ---------------------------------------------------------------- 직접 추정(모두 lv에 '추정') — judgments.md 6절
C4 = 1231      # 프랑스 4부(CFA): 주니뉴·지울리 자료 1231과 같음
C5 = 1150      # 프랑스 5부(CFA2) 이하 아마추어: 오바메양·주니뉴·지울리 자료 1150과 같음
C6 = 1100      # 프랑스 6부(DH, 지역 리그): 다른 선수 자료 리나몽레리 2019-20 6부 1100과 같음
MANUAL = [
    ("Jerez CF", "1998-99", 1350, "스페인 3부 이하 (추정, 디비전 확인 못 함; 다른 선수 자료 스페인 3부 1350과 같음)"),
    ("Panathinaikos", "1999-00", 1560, "그리스 1999-00 2위 (추정, 다른 선수 자료 파나티나이코스 2000-01 2위 1560과 같음)"),
    ("Lierse SK", "2000-01", 1457, "벨기에 1부 2000-01 10위 (추정, 다른 선수 자료 같은 시즌 1위 1764·11위 1423 사이 직선)"),
    ("US Issoire", "2000-01", C6, "프랑스 6부(DH) 2000-01 (추정, 지역 리그 팀; 다른 선수 자료 프랑스 6부 1100과 같음)"),
    ("Debreceni VSC", "2001-02", 1380, "헝가리 2001-02 9위 (추정, 다른 선수 자료 헝가리 8위 1380과 같은 수준)"),
    ("Standard Liège", "2001-02", 1545, "벨기에 1부 2001-02 5위 (추정, 다른 선수 자료 벨기에 1부 5위 1545와 같음)"),
    ("ÉFC Fréjus Saint-Raphaël", "2001-02", C4, "프랑스 4부(CFA) 2001-02 (추정, 다른 선수 자료 프랑스 4부 1231과 같음)"),
    ("MSK Púchov", "2002-03", 1330, "슬로바키아 1부 (추정, 다른 선수 자료 푸호프 2003-04 1330과 같음)"),
    ("JA Armentières", "2002-03", C5, "프랑스 하부 아마추어 2002-03 (추정, 디비전 확인 못 함; 다른 선수 자료 프랑스 하부 아마추어 1150과 같음)"),
    ("Aviron Bayonnais", "2003-04", C4, "프랑스 4부(CFA) 2003-04 (추정, 다른 선수 자료 프랑스 4부 1231과 같음)"),
    ("ESA Brive", "2003-04", C4, "프랑스 4부(CFA) 2003-04 (추정, 다른 선수 자료 프랑스 4부 1231과 같음)"),
    ("US Langueux", "2004-05", C5, "프랑스 하부 아마추어 2004-05 (추정, 디비전 확인 못 함; 다른 선수 자료 프랑스 하부 아마추어 1150과 같음)"),
    ("US Vermeloise", "2005-06", C6, "프랑스 6부(DH) 2005-06 (추정, 다른 선수 자료 프랑스 6부 1100과 같음)"),
    ("AS Lyon-Duchère", "2005-06", C4, "프랑스 4부(CFA) 2005-06 (추정, 다른 선수 자료 프랑스 4부 1231과 같음)"),
    ("Derry City", "2006-07", 1300, "아일랜드 2006 2위 (추정, 다른 선수 자료 아일랜드 1위 보헤미안 2000-01 1300과 같음)"),
    ("Hapoel Tel Aviv", "2006-07", 1475, "이스라엘 2006-07 4위 (추정, 다른 선수 자료 이스라엘 2위 1500·8위 1425 사이 직선)"),
    ("Panathinaikos", "2006-07", 1560, "그리스 2006-07 3위 (추정, 다른 선수 자료 그리스 3위 1560과 같음)"),
    ("US Jeanne d'Arc Carquefou", "2007-08", C5, "프랑스 5부(CFA2) 2007-08 (추정, 다른 선수 자료 프랑스 5부 1150과 같음)"),
]
for o, s, e, lv in MANUAL: man(o, s, e, lv)

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, rnd)
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
    for x in SAME_MULTI: print("같은 경기 값 여럿", x)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    print("보간", sorted(INTERP_USED))
    sys.exit(0)
if __name__ == "__main__" and "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print("score mismatches", SCORE_MISMATCH)
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    print(len(E), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E))
    for j in judg: print(j)
    sys.exit(0)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or ((a[14] if len(a) > 14 else 0) or 0) != ((b[14] if len(b) > 14 else 0) or 0): d.append(f"단판/합산 {a[7]}{a[14] if len(a) > 14 else ''}/{b[7]}{b[14] if len(b) > 14 else ''}")
    if a[10] != b[10]: d.append("연장")
    return d
def same_opp(x, r): return key(x[1]) == key(r[1]) or bool(toks(x[1]) & toks(r[1]))
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Pauleta", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움→파울레타 골", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_opp(x, r)]
            if hit: CROSS.append(("파울레타 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
# 같은 경기를 상대 쪽에서 기록한 다른 선수 자료(파울레타 팀이 그 선수의 상대): 날짜가 같고 상대가 파울레타 소속 팀인 행
MYCLUB = {"1087": "salamanca", "897": "coruna", "40": "bordeaux", "583": "paris saint germain"}
GBYDATE = {ldate(g): g for g in GAMES}
OPPSIDE = []      # (파일, 날짜, 종류, 분, 그쪽 골 전 스코어, 파울레타 쪽 같은 경기 행과 모순 여부)
for b, (oe, om) in OTHERS.items():
    for x in oe:
        g = GBYDATE.get(x[9])
        if not g or MYCLUB[g["club_id"]] not in norm(x[1]): continue
        mine = [r for r in E if r[9] == x[9]]
        bad = [r for r in mine if (r[4] < x[4] and (r[5] > x[6] or r[6] > x[5])) or (r[4] > x[4] and (r[5] < x[6] or r[6] < x[5]))]
        OPPSIDE.append((b, x[9], x[0], x[4], f"{x[5]}-{x[6]}", "모순" if bad else ("대조" if mine else "파울레타 기록 없는 경기")))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("salpl", "1998-07-01", "살라망카", "1996~1998"), ("deppl", "2000-08-28", "데포르티보 라코루냐", "1998~2000"),
         ("bdxpl", "2003-07-01", "보르도", "2000~2003"), ("psgpl", None, "파리 생제르맹", "2003~2008")]
TM_CLUB = {"1087": "salpl", "897": "deppl", "40": "bdxpl", "583": "psgpl"}
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
if NPK != NPK_API: sys.exit("PK 수 불일치")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({(r[9]) for r in E if len(r) > 14})
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in ("bdxpl", "psgpl"): s = y if d[5:] >= "07-10" else y - 1
    else: s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
SEAS = collections.OrderedDict()
for m in M:
    s = season_of(m[0], club_of(m[0])); SEAS.setdefault(s, [0, 0, 0, 0]); SEAS[s][0] += 1; SEAS[s][3] += m[3]
for r in E:
    s = season_of(r[9], club_of(r[9])); SEAS[s][1 if r[0] == "g" else 2] += 1
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    for c in CROSS: print(c)
    for c in OPPSIDE: print("상대 쪽 기록", c)
    for k, v in SEAS.items(): print(k, v)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
SRC = ELO_SRC
first, last = M[0], M[-1]
EXA = [j for j in judg if j[0] == "도움 제외"]
NOTE_LINES = [
    f"파울레타(살라망카·데포르티보 라코루냐·보르도·파리 생제르맹)의 클럽 공식 경기 {NG}경기({d_(first[0])} {first[1]}전 ~ {d_(last[0])} {last[1]}전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·포르투갈 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CN[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있거나 리그 밖 대회인 모든 경기 241경기, 리포트 골 247개·PK 33개가 선수 경기 성적과 경기마다 같음). 리포트가 없는 리그 226경기의 날짜는 Transfermarkt 일정 날짜. FotMob은 2010-11 이전 경기 자료가 없어 대조하지 못함. 영어·프랑스어·스페인어·포르투갈어 위키백과 클럽·시즌별 경기·골과 대조: 살라망카 1997-98부터 파리 생제르맹까지는 데포르티보 1998-99 코파 델 레이를 빼면 모두 같음",
    "넣지 않은 경기(경기별 날짜·출전·골 시각 자료가 없음): 포르투갈 하부 리그 1990~1995(프랑스어 위키백과 산타클라라·오페라리우·앙그렌스·우니앙 미카엘렌스 72경기 22골), 에스토릴 1995-96 2부(영어 위키백과 33경기 23골, 프랑스어판 34경기 24골), 은퇴 뒤 GD 상로케 2010(아소르스 아마추어, 프랑스어 위키백과 1경기 2골). 살라망카 1996-97은 Transfermarkt가 40경기를 알지만 라인업이 있는 15경기(10골)만 넣고, 출전 기록이 없는 25경기(위키백과 기준 9골 차이: 위키백과 40경기 19골)는 넣지 않음. 데포르티보 1998-99 코파 델 레이는 Transfermarkt 출전 7경기(위키백과 9경기, 골은 둘 다 1골)만 넣음. 영어 위키백과 클럽 경력 합계(526경기 279골)와의 차이는 이 경기들",
    f"골: 자책골 없음. PK 골 {NPK}개는 Transfermarkt 골 유형 'Penalty'(선수 경기 성적 PK 골 수와 같음). 2005.1.8 쿠프 드 프랑스 랑괴전은 리포트에 랑괴 골 1개가 빠져 있으나 하프타임 0-3이라 21·29분 골의 골 전 스코어(0-1·0-2)는 그대로",
    "도움: 2014년 8월 이전 도움이라 Transfermarkt 경기 리포트 단일 출처(클로제·인시녜·주니뉴·지울리 선례). Transfermarkt 도움 25개(본인 PK 골에 본인 도움으로 적은 2006.4.1 보르도전 38분은 처음부터 셈하지 않음)에서 " + ", ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]} 골({'PK 유도' if j[5] == 'PK 유도' else '슈팅 리바운드'})" for j in EXA) + f"을 빼 {NA}개. 도움 유형 칸이 빈 {UNTYPED}개는 일반 도움으로 셈. Transfermarkt는 살라망카 도움이 0개, 데포르티보 3개·보르도 6개뿐이라 1996~2003 도움은 실제보다 적을 수 있으나 다른 경기별 출처를 찾지 못함",
    "출전 분: Transfermarkt 그대로(빈칸 없음, 추정한 경기 없음). 연장 경기는 연장 포함 출전 분, 연장 없이 승부차기로 끝난 2004.7.31 트로페 데 샹피옹(56분 교체)은 90분 기준. 연장 골: 2004.1.4 쿠프 드 프랑스 트루아전 95분(결승 골), 2005.2.13 쿠프 드 프랑스 보르도전 95·117분. 퇴장: 1998.2.22 메리다전(경고 누적 69분), 2000.3.18 바르셀로나전(60분 교체 투입 뒤 89분 퇴장), 2006.10.28 렌전(경고 누적 90+4분)",
    f"상대 Elo는 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표, 위키백과로 대조)를 기존 리그 순위값·리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 팀·시즌 {SRC['기존 팀×시즌 값']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']}). 같은 경기를 다룬 동료 자료는 없음",
    "리그1은 그 시즌 기존 순위값에 순위를 넣고, 빈 순위는 앞뒤 기존 값 사이 직선, 앞이나 뒤에 기존 값이 없는 끝 순위는 같은 팀 수 시즌의 기존 전체 순위값(18팀 1999-00 18위 몽펠리에·2000-01 1위 낭트·18위 스트라스부르). 리그2는 기존 순위값이 없으면 평균 1540 모형, 프랑스 3부(님 2006-07 5위)는 다른 선수 자료와 같은 평균 1311 모형. 세군다 1996-97(20팀)은 호나우두 자료와 같은 2부 모형(평균 1624), 라리가 1997~2000은 기존 같은 팀·시즌 값",
    "직접 추정(모두 '추정'): " + ", ".join(f"{o} {e}" for o, e, lv in MAN_USED) + ". 쿠프 드 프랑스 아마추어 상대는 리그 단계에 따라 4부(CFA) 1231, 5부(CFA2) 이하 1150, 6부(DH 지역 리그) 1100(이수아르·베르멜), 디비전을 확인하지 못한 아르망티에르·랑괴는 1150. 순위가 Transfermarkt 표와 다른 것: 데브레첸 2001-02는 Transfermarkt 8위지만 위키백과 표 9위, 데리 시티 2006은 Transfermarkt 7위(시즌 중 표)지만 최종 2위로 적음",
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·코파 델 레이는 국내컵(16강까지·8강·준결승·결승), 트로페 데 샹피옹·수페르코파(1차전만 출전)는 국내컵 결승 비중. 챔스 2004-05 조별은 리그 단계, UEFA컵 1라운드는 유로파 예선, UEFA컵 2006-07 조별은 유로파 조별, UEFA컵 2·3라운드·32강·16강은 유로파 토너먼트",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·코파 델 레이·수페르코파는 원정 다득점·연장. 못 뛴 다른 차전 스코어는 Transfermarkt 리포트로 채움",
    "시즌 구분: 보르도·파리 생제르맹은 7월 10일 기준(2001.7.27 리그1 개막전, 2004.7.31 트로페 데 샹피옹, 2005.7.29 개막전이 새 시즌), 살라망카·데포르티보는 기본 8월 1일(데포르티보 2000.8.20 수페르코파 1차전은 2000-01). 클럽 구분: 1998.7.1 전 살라망카, 2000.8.28 전 데포르티보, 2003.7.1 전 보르도",
    "같은 경기 다른 선수 자료: 동료로 겹친 선수가 없어 주고받은 골·도움은 없음. 상대 쪽 자료(주니뉴·말루다·벤 아르파 리옹, 지울리 모나코, 드록바 마르세유, 리베리 마르세유)의 같은 경기 골·도움과 골 전 스코어 순서가 모두 맞음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 라리가 1999-00(데포르티보), 수페르코파 2000(데포르티보), 쿠프 드 프랑스 2003-04·2005-06(파리 생제르맹), 쿠프 드 라 리그 2001-02(보르도)·2007-08(파리 생제르맹). 개인: 리그1 올해의 선수 2001-02·2002-03, 리그1 득점왕 2001-02(22골)·2005-06(21골)·2006-07(15골), 세군다 득점왕 1996-97(19골), 리그1 외국인 선수상 2001·2002. 대표팀 기록(월드컵 예선 득점왕·유로 2004 준우승)은 뺌. 쿠프 드 프랑스 2007-08 준우승은 Transfermarkt 업적에 없어 넣지 않음",
    "은퇴: 2008년 파리 생제르맹을 떠난 뒤(마지막 공식 경기 2008.5.24 쿠프 드 프랑스 결승 리옹전) 프로 은퇴, 2010-11 아소르스 아마추어 GD 상로케에서 뛴 뒤 2011.7 은퇴(Transfermarkt)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elk", "elq", "elg", "clg", "cwc", "MAN", "csa", "lib"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

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
    ar = sorted(rs, key=lambda r: r[4])
    for a, b in zip(ar, ar[1:]):
        if b[5] < a[5] or b[6] < a[6]: problems.append(("시간순 스코어 역순", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
    if r[4] > 90 and not r[10] and not r[11]: problems.append(("90분 넘는데 표기 없음", r))
mm_ = {m[0]: m for m in M}
Gst = {ldate(g): g for g in GAMES}
for r in E:
    m = mm_.get(r[9]); g = Gst[r[9]]
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if g["isStarting"] in ("1", "True") and r[4] > m[3] + 6 and not (m[3] >= 90): problems.append(("선발 출전 분보다 늦은 기록", r[9], r[4], m[3]))
    if g["isStarting"] not in ("1", "True"):
        end = 120 if g["gameState"] in ("extra_time", "penalty_shootout") else 90
        if r[4] < end - m[3] - 6 and not r[11]: problems.append(("교체 출전 전 기록", r[9], r[4], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const PAU_E={J(E)};\nconst PAU_M={J(M)};\nconst PAU_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS, "opponent_side_rows": OPPSIDE,
               "elo_sources": ELO_SRC, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}, "seasons": SEAS},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
