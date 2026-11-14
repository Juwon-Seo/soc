#!/usr/bin/env python3
"""Sidney Govou: raw/ -> govou.json + src/data/gov.js (판정 근거는 judgments.md)

  python3 players/govou/build_govou.py [루트]      (루트 생략 = 이 저장소)

입력: raw/tm_games.csv(출전·분·현지 날짜; 프로 클럽 리옹 1041·파나티나이코스 265·에비앙 14171만), raw/tm_events.csv(리포트 골 목록),
      raw/tm_match_info.csv(리포트 머리·다른 차전), raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값), src/data/*.js(같은 경기 다른 선수 자료 대조·재사용).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "gov.js")
OUT_JSON = os.path.join(HERE, "govou.json")
JP = "5357"
GAP = "2014-08-01"           # 이 날짜 전 도움은 Transfermarkt 리포트(단일 출처 허용) — 고부의 프로 경기는 모두 이 전
NEW_FILES = {"gov.js"}
PRO_CLUBS = {"1041": "리옹", "265": "파나티나이코스", "14171": "에비앙"}

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"FR1", "GR1", "POGR"}      # 그리스 슈퍼리그 플레이오프(2~5위 미니 리그) = 리그(히바우두·발부에나 선례)
CUPS = {"FRC", "FRL", "GRP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid == "CL":
        if r.startswith("group"): return "clg"      # 2000-01 2차 조별('Group 3') 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "UEFA": return "elk"                  # 2001-02 UEFA컵 3라운드·16강(챔스 조 3위 합류)
    if cid == "FRCH": return "df"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE_IDS: return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 입력
ALLG = rd("tm_games.csv")
games = [g for g in ALLG if g["level"] == "senior" and g["club_id"] in PRO_CLUBS]
EXCL = [g for g in ALLG if g not in games]
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

def ldate(g): return g["date_local"]
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    if cid in ("CL", "UEFA"): return (1, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G:
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, m["other_leg_score"].split(":"))      # 이 경기 홈:원정 방향
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def fm_ev(gid, after_ha):
    for f in FME.get(gid, []):
        if f["newScore_home_away"] == after_ha and f["pen_shootout_event"] != "True": return f
    return None

def assist_reason(e):
    t = e["assist_type"]
    if e["scorer_id"] == JP: return "본인 PK 골에 본인 도움(PK 유도)"
    if e["own_goal"] == "1": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

raw_rows, judg, min_fix, own_goals = [], [], [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid)
    prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        if e["scorer_id"] == JP and e["own_goal"] == "1":
            own_goals.append((gid, ldate(g), opp(g), e["minute"], e["score_home_away_after"])); continue
        is_g = e["scorer_id"] == JP
        is_a = e["assist_id"] == JP
        if not (is_g or is_a): continue
        if e["side"][0] != side and not (is_a and assist_reason(e)):
            sys.exit("득점 편 이상 " + gid)
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        f = fm_ev(gid, e["score_home_away_after"])
        if dm == 0 and mi in (45, 90) and f and f["overloadTime"] and int(f["time"]) == mi and int(f["overloadTime"]) > 0:
            dm = f"{mi}+{int(f['overloadTime'])}"; min_fix.append((gid, ldate(g), opp(g), e["minute"], dm)); mi = mi + int(f["overloadTime"])
        d = ldate(g)
        if is_a:
            why = assist_reason(e)
            if why: judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], why))
            elif d >= GAP: sys.exit("[판정 필요] 2014.8 이후 도움 " + gid)
            else: raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            raw_rows.append(("g", gid, mi, dm, gf, ga, 1 if e["penalty"] == "1" else 0, 0))

# FotMob(2010-11 이후)에만 있는 고부 골·도움 확인
fm_only_seen = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        tm = [e for e in EVS.get(gid, []) if e["score_home_away_after"] == f["newScore_home_away"]]
        if f["govou_assist"] == "1" and not any(e["assist_id"] == JP for e in tm):
            fm_only_seen.append(("a", gid, f["time"], f["scorer"])); sys.exit("[판정 필요] FotMob 전용 도움 " + gid)
        if f["govou_scorer"] == "1" and not any(e["scorer_id"] == JP for e in tm):
            sys.exit("[판정 필요] FotMob 전용 골 " + gid)

# ---------------------------------------------------------------- 상대 Elo
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
def key(n):
    k = norm(n); return ALIAS.get(k, k)

TABLE = {}
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if "시드니 고부" in r["선수"] and r["선수"].strip() == "시드니 고부": continue
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
# Transfermarkt 순위표 고침(공식 최종 순위 확인): 아트로미토스 2010-11은 RSSSF·영어 위키백과 시즌 문서 11위(승점 34, 케르키라 33) — TM 표 12위
RANK_FIX = {("GR1", "2010-11", "Atromitos Athens"): 11}
for (lg_, s_, t_), r_ in RANK_FIX.items():
    o_ = RANKS[(lg_, s_)][key(t_)]; RANKS[(lg_, s_)][key(t_)] = (r_, o_[1], o_[2])

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
def half_up(x): return int(x + 0.5)
SD2 = 51.24

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

LGPTS = collections.defaultdict(dict)
for (k, s), (e, lv) in TABLE.items():
    if "추정" in lv: continue
    m = re.match(r"(리그1) (\d{4}-\d\d) (\d+)위$", lv)
    if m: LGPTS[(m.group(1), m.group(2))][int(m.group(3))] = e
FR_STD = LGPTS[("리그1", "2011-12")]
INTERP = []

# 그리스 슈퍼리그: 히바우두·발부에나 자료와 같은 국가 계수 회귀(1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 흩어짐 119)
#   + 그리스 보정 GR_K(발부에나 자료 기준점: 올림피아코스 2019-20 1위 1680·2020-21 1위 1690, PAOK 2021-22 2위 1590).
def reg_mean(coefs): return 1473 + 23.33 * (sum(coefs) / len(coefs) - 7.3333)
GR_COEF_V = {2018: 5.1, 2019: 4.9, 2020: 5.1, 2021: 8.0, 2022: 2.125, 2023: 11.4, 2024: 12.688}
def _gr_reg_v(start):
    ys = (start - 1, start, start + 1) if start + 1 in GR_COEF_V else (start - 2, start - 1, start)
    return reg_mean([GR_COEF_V[y] for y in ys])
GR_K = sum(v - (_gr_reg_v(y) + 119 * curve(r, 14)) for y, r, v in [(2019, 1, 1680), (2020, 1, 1690), (2021, 2, 1590)]) / 3
# 그리스 국가 시즌 계수(영어 위키백과 Greek football clubs in European competitions·TSN UEFA 계수 표: 2008-09 6.500(히바우두 자료와 같음)·2009-10 7.900·2010-11 7.600·2011-12 7.600)
GR_COEF = {2009: 7.900, 2010: 7.600, 2011: 7.600}
def gr_mean(season):
    s = int(season[:4]); return reg_mean([GR_COEF[s - 1], GR_COEF[s], GR_COEF[s + 1]]) + GR_K

def rank_model(lg, season, r, n):
    if lg == "FR1":
        pts = LGPTS.get(("리그1", season), {})
        if r in pts: return pts[r], f"리그1 {season} {r}위"
        lo = [k for k in pts if k < r]; hi = [k for k in pts if k > r]
        if lo and hi:
            a, b = max(lo), min(hi); v = half_up(pts[a] + (pts[b] - pts[a]) * (r - a) / (b - a))
            INTERP.append((season, r, a, b, v)); return v, f"리그1 {season} {r}위"
        if n == 20: INTERP.append((season, r, "20팀 공통값", FR_STD[r])); return FR_STD[r], f"리그1 {season} {r}위"
        return None
    if lg == "FR2":     # 리그2: 평균 1540, 흩어짐 2부(디 마리아·라카제트 선례; 4위 1582 = 기존 리그2 1999-00 4위 값과 같음)
        return half_up(1540 + SD2 * curve(r, n)), f"리그2(프랑스 2부) {season} {r}위"
    if lg == "GR1":
        return half_up(gr_mean(season) + 119 * curve(r, n)), f"그리스 슈퍼리그 {season} {r}위 (리그 수준 추정)"
    return None

def table_candidates(cid, d):
    if cid in ("FR1", "FRC", "FRL", "FRCH"): return [("FR1", eu(d)), ("FR2", eu(d))]
    if cid in ("GR1", "GRP", "POGR"): return [("GR1", eu(d))]
    return []

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
try:
    tracked = set(os.path.basename(x) for x in subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
except Exception:
    tracked = None
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b == "hon.js" or b in NEW_FILES or (tracked and b not in tracked): continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio", "fk", "bk",
        "atletico", "ca", "us", "as", "ss", "ssc", "hsc", "osc", "acf", "olympique", "stade", "sv", "saint", "paris", "rc", "ea", "losc", "sco", "fco", "vfb"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, {(x[2], x[12]) for b, x in cand}

# 순위표·기존 자료에 없는 상대(직접 추정, 모두 '추정') — judgments.md 6절
MAN = {
    ("AS Red Star 93", "1999-00"): (1311, "프랑스 3부(나시오날) 1999-00 (추정, 순위 미확인, 다른 선수 자료 프랑스 3부 1311과 같음)"),
    ("Vendée Fontenay Foot", "2000-01"): (1231, "프랑스 4부(CFA) 2000-01 (추정, 다른 선수 자료 프랑스 4부(CFA) 1231과 같음)"),
    ("US Laon", "2006-07"): (1150, "프랑스 5부(CFA2) 2006-07 (추정, 다른 선수 자료 프랑스 5부 1150과 같음)"),
    ("Kozani FC", "2010-11"): (half_up(gr_mean("2010-11") - 162 - 162), "그리스 3부(풋볼 리그 2) 2010-11 (추정, 그리스 1부 평균 − 162 × 2, 순위 미확인)"),
}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand}))
        return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    s = eu(d)
    if cid == "CL" and (key(o), d[:4]) in TABLE and (key(o), s) not in TABLE:      # 달력 연도 리그 상대(노르웨이): 가을 조별 = 그해 시즌
        e, lv = TABLE[(key(o), d[:4])]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv)
        return e, lv
    if (key(o), s) in TABLE:
        e, lv = TABLE[(key(o), s)]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv)
        return e, lv
    for lg, ss in table_candidates(cid, d):
        tab = RANKS.get((lg, ss), {})
        if key(o) in tab:
            r, n, _ = tab[key(o)]
            res = rank_model(lg, ss, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    if (o, s) in MAN:
        e, lv = MAN[(o, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv)
        return e, lv
    MISS.append((o, d, cid, s)); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (ko and mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))

if MISS:
    for m in sorted(set(MISS), key=lambda x: x[1]): print("MISS", m)
    sys.exit("상대 Elo 없음 %d" % len(MISS))

exec(open(os.path.join(HERE, "out_govou.py"), encoding="utf-8").read())
