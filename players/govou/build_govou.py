#!/usr/bin/env python3
"""Hatem Ben Arfa: raw/ -> benarfa.json + src/data/bna.js (판정 근거는 judgments.md)

  python3 players/benarfa/build_benarfa.py

입력: raw/tm_games.csv(출전·분·현지 날짜, level=senior만), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv(대조), raw/ranks.txt(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값), src/data/*.js(같은 경기 다른 선수 자료 대조·재사용).
"""
import csv, json, os, re, sys, unicodedata, collections, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "bna.js")
OUT_JSON = os.path.join(HERE, "benarfa.json")
JP = "18900"
GAP = "2014-08-01"           # 이 날짜 전 도움은 Transfermarkt 리포트, 뒤는 Transfermarkt ∩ FotMob(+ 다른 출처 2곳)
# 같은 회차에 다른 판정 에이전트가 쓰는 파일(대조·재사용에서 뺌) — git에 없는 새 파일은 아래에서 자동으로 뺌
NEW_FILES = {"bna.js"}

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 판정 표
# 2014.8 이후 Transfermarkt 단일 출처 도움(FotMob 경기 이벤트에 Ben Arfa 도움 없음): gameId|분 -> 근거(넣음) / None(뺌)
POST_GAP = {
    "2490240|50": "Sky Sports 경기 기사('Ben Arfa tricked his way inside and his ball split the Baggies' defence for Brady to collect and steer into the corner')·Bleacher Report(헐 시절 최고 장면으로 이 패스를 적음). FotMob은 이 경기 도움 칸이 빔",
    "2814001|57": "maxifoot 경기 기사(벤 아르파의 왼발 크로스를 모타가 페널티 지점에서 헤더, 4-0 57분)·Corse Net Infos(벤 아르파가 흘러나온 공을 잡아 수비 뒤로 크로스)·FourFourTwo/beIN(Omnisport, 'header after Hatem Ben Arfa's cross'). FotMob은 이 경기 도움 칸이 모두 빔",
    "2814001|89": "FourFourTwo/beIN(Omnisport, 'Draxler ... racing on to a pass from Hatem Ben Arfa')·CulturePSG 문자중계('Lancé dans la profondeur par Ben Arfa, Draxler envoie un petit bijou de piqué'). FotMob은 이 경기 도움 칸이 모두 빔",
    "2646599|44": "우에스트 프랑스 문자중계('Ben Arfa déborde la surface guingampaise et centre en retrait pour Alex Mendy qui s'y prend à deux fois avant de tromper Lössl'). 다른 기사·ESPN·LFP는 도움자를 적지 않았고 다른 선수 도움으로 적은 출처 없음(이번 회차 사용자 결정: 독립 경기 기사 1곳 + 반대 출처 없음이면 넣음)",
}
# FotMob에만 있는 Ben Arfa 도움·골(Transfermarkt 리포트엔 없음): 없음(빌드가 확인)
FM_ONLY = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"FR1", "GB1", "ES1"}
CUPS = {"FRC", "FRL", "CGB", "FAC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "CLQ": return "clq"
    if cid == "UEFA":      # 2008-09 UEFA컵: 3라운드(챔스 조 3위 합류 32강)·16강·8강
        return "elk"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"       # 32강(2009-10 'Second Round', 2018-19 'intermediate stage')·16강·8강
    if cid == "FRCH": return "df"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"     # 2~6라운드·16강(잉글랜드 리그컵 'Round of 16' = 4라운드)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE_IDS: return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 입력
games = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

def ldate(g): return g["date_local_tz_conv"]
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round_report"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    if cid in ("CL", "CLQ", "EL", "UEFA"): return (1, 1) if d < "2021-07-01" else (0, 1)
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
    g = G[gid]; rnd = g["round_report"].lower()
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
    if e["own_goal"] == "1": return "상대 자책골 유도(슈팅 리바운드)"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

raw_rows, judg, post_gap_log, min_fix = [], [], [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid)
    prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == JP and e["own_goal"] != "1"
        is_a = e["assist_id"] == JP
        if not (is_g or is_a): continue
        if e["side"][0] != side and not (is_a and assist_reason(e)):
            sys.exit("득점 편 이상 " + gid)
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        f = fm_ev(gid, e["score_home_away_after"])
        if dm == 0 and mi in (45, 90) and f and f["overloadTime"] and int(f["time"]) == mi and int(f["overloadTime"]) > 0:
            dm = f"{mi}+{int(f['overloadTime'])}"; min_fix.append((gid, ldate(g), opp(g), e["minute"], dm)); mi = mi + int(f["overloadTime"])
        d = ldate(g); tag = f"{gid}|{e['minute']}"
        if is_a:
            why = assist_reason(e)
            fm_ok = bool(f and "Ben Arfa" in (f["assistStr"] or ""))
            if why:
                judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], why))
            elif d >= GAP and not fm_ok:
                v = POST_GAP.get(tag, "미판정")
                post_gap_log.append((gid, d, opp(g), e["minute"], e["scorer"], e["assist_type"], v))
                if v == "미판정": sys.exit("[판정 필요] 2014.8 이후 Transfermarkt 단일 도움 " + tag)
                if v: raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
                else: judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], "2014.8 이후 Transfermarkt 단일 출처(다른 출처 확인 못 함)"))
            else:
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            raw_rows.append(("g", gid, mi, dm, gf, ga, 1 if e["penalty"] == "1" else 0, 0))

fm_only_seen = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        tm = [e for e in EVS.get(gid, []) if e["score_home_away_after"] == f["newScore_home_away"]]
        if f["bena_assist"] == "1" and not any(e["assist_id"] == JP for e in tm):
            k = f"{gid}|{f['time']}"; fm_only_seen.append(("a", k, ldate(G[gid]), f["scorer"]))
            if k not in FM_ONLY: sys.exit("[판정 필요] FotMob 전용 도움 " + k)
        if f["bena_scorer"] == "1" and not any(e["scorer_id"] == JP for e in tm):
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
        if "하템 벤 아르파" in r["선수"]: continue
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 기존 자료의 리그별·시즌별 순위값
LGPTS = collections.defaultdict(dict)
for (k, s), (e, lv) in TABLE.items():
    if "추정" in lv: continue
    m = re.match(r"(리그1|프리미어리그) (\d{4}-\d\d) (\d+)위$", lv)
    if m: LGPTS[(m.group(1), m.group(2))][int(m.group(3))] = e
FR_STD = LGPTS[("리그1", "2011-12")]
INTERP = []      # 20팀 리그1 공통 순위값(2010-11~2022-23 같음)

def rank_model(lg, season, r, n):
    if lg == "FR1":
        # 그 시즌 기존 순위값 → 없으면 앞뒤 기존 순위값 사이 직선 보간(반올림, 발뷔에나 판정과 같은 방식) → 끝이면 20팀 공통값
        pts = LGPTS.get(("리그1", season), {})
        if r in pts: return pts[r], f"리그1 {season} {r}위"
        lo = [k for k in pts if k < r]; hi = [k for k in pts if k > r]
        if lo and hi:
            a, b = max(lo), min(hi); v = int(pts[a] + (pts[b] - pts[a]) * (r - a) / (b - a) + 0.5)
            INTERP.append((season, r, a, b, v)); return v, f"리그1 {season} {r}위"
        return FR_STD[r], f"리그1 {season} {r}위"
    if lg == "GB1":
        pts = LGPTS[("프리미어리그", season)]
        if r in pts: return pts[r], f"프리미어리그 {season} {r}위"
        lo, hi = pts[r - 1], pts[r + 1]          # 빈 순위는 앞뒤 순위값의 중간(병렬 판정 규칙)
        return round((lo + hi) / 2), f"프리미어리그 {season} {r}위"
    return None

def table_candidates(cid, d):
    if cid in ("FR1", "FRC", "FRL", "FRCH"): return [("FR1", eu(d))]
    return []

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
# git에 아직 없는 새 데이터 파일(병렬 판정 중인 다른 선수)은 빼고 읽음
import subprocess
try:
    tracked = set(os.path.basename(x) for x in subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
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

# 순위표·기존 자료에 없는 상대(직접 추정, 모두 '추정')
MAN = {
    ("Trélissac FC", "2009-10"): (1150, "프랑스 5부(CFA2) 2009-10 A조 (추정, 다른 선수 자료의 프랑스 5부 팀 값 1150과 같음)"),
    ("FC Copenhagen", "2009-10"): (1560, "덴마크 2009-10 1위 (추정, 다른 선수 자료 코펜하겐 2007-08·2008-09 1위 값 1560과 같음)"),
    ("CS Marítimo", "2012-13"): (1545, "포르투갈 1부 2012-13 10위 (16팀 시즌의 다른 선수 자료 10위 값 1545와 같음)"),
    ("Morecambe FC", "2013-14"): (1341, "리그 투(4부) 2013-14 19위 (추정, 리그 원 같은 시즌 18·20위 값의 중간 1456 − 115)"),
    ("FK Jablonec", "2018-19"): (1480, "체코 2018-19 4위 (추정, 다른 선수 자료 체코 4위 값 1480과 같음)"),
}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand}))
        return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    s = eu(d)
    if (key(o), s) in TABLE:
        e, lv = TABLE[(key(o), s)]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv)
        return e, lv
    for lg, ss in table_candidates(cid, d) + [("GB1", s)]:
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
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round_report"]
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


# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(수정 없음, 보고용)
MATE_NAME = {"bzm.js": "Karim Benzema", "jun.js": "Juninho", "mld.js": "Florent Malouda", "dim.js": "Ángel Di María",
             "cav.js": "Edinson Cavani", "pas.js": "Javier Pastore", "luc.js": "Lucas Moura", "mba.js": "Kylian Mbappé", "ney.js": "Neymar"}
ALT = {"Karim Benzema": ("Benzema",), "Juninho": ("Juninho",), "Florent Malouda": ("Malouda",), "Ángel Di María": ("Di Mar",),
       "Edinson Cavani": ("Cavani",), "Javier Pastore": ("Pastore",), "Lucas Moura": ("Lucas",), "Kylian Mbappé": ("Mbapp",), "Neymar": ("Neymar",)}
def same_vals(a, b): return (a[5], a[6], a[2], a[12], a[3], a[7], a[14:]) == (b[5], b[6], b[2], b[12], b[3], b[7], b[14:])
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and "Ben Arfa" in str(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2], key=lambda r: abs(r[4] - x[4]))
            ok = hit and same_vals(hit[0], x)
            cross.append(("동료 도움→벤 아르파 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "벤 아르파 골 없음"), x[2:8], hit[0][2:8] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and any(t in r[13] for t in ALT[nm]):
                hit = sorted([x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2], key=lambda x: abs(x[4] - r[4]))
                ok = hit and same_vals(hit[0], r)
                has_m = any(m[0] == r[9] for m in om)
                cross.append(("벤 아르파 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else ("동료 골 없음" + ("" if has_m else "(출전 행도 없음)"))), r[2:8], hit[0][2:8] if hit else None))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[12], x[3]), (r[2], r[12], r[3])))
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                cross.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[2], m[2]))
for gid, evs in EVS.items():
    if gid not in G: continue
    for e in evs:
        if e["scorer_id"] == JP and e["assist_id"] and e["assist_id"] != JP and not e["assist_type"].startswith("Penalty"):
            for b, nm in MATE_NAME.items():
                if b in OTHERS and any(t in e["assist_player"] for t in ALT[nm]):
                    d = ldate(G[gid]); oe, om = OTHERS[b]
                    if not any(x[0] == "a" and x[9] == d and "Ben Arfa" in str(x[13]) for x in oe):
                        cross.append(("Transfermarkt 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"] or "(유형 빈칸)",
                                      "출전 행 있음" if any(m[0] == d for m in om) else "출전 행도 없음"))
DUP = set()
cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 클럽별 합계
CLUBS = [("2008-07-01", "리옹"), ("2010-08-29", "마르세유"), ("2014-09-01", "뉴캐슬 유나이티드"), ("2015-07-01", "헐 시티"),
         ("2016-07-01", "니스"), ("2018-09-02", "파리 생제르맹"), ("2020-01-28", "렌"), ("2020-10-07", "레알 바야돌리드"),
         ("2022-01-19", "보르도"), ("9999-12-31", "릴")]
TMCLUB = {"1041": "리옹", "244": "마르세유", "762": "뉴캐슬 유나이티드", "3008": "헐 시티", "417": "니스", "583": "파리 생제르맹",
          "273": "렌", "366": "레알 바야돌리드", "40": "보르도", "1082": "릴"}
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
for g in games:
    if club_of(ldate(g)) != TMCLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for _, n in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
TM_A_API = sum(int(g["assists"]) for g in games)
API_G = sum(int(g["goals"]) for g in games); API_PK = sum(int(g["penGoals"]) for g in games)
if (API_G, API_PK) != (NGo, NPK): sys.exit(f"골 합계 불일치 API {API_G}/{API_PK} vs {NGo}/{NPK}")
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
def jl(reason):
    return ", ".join(f"{d_(j[1])} {j[2]} {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
SAME_N = ELO_SRC["같은 경기 다른 선수 자료"]
MODEL_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "model"}, key=lambda t: t[2])

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
KO = {"OGC Nice": "니스", "FC Girondins Bordeaux": "보르도"}
n_excl = EX["PK 유도"] + EX["상대 자책골 유도(슈팅 리바운드)"] + EX["2014.8 이후 Transfermarkt 단일 출처(다른 출처 확인 못 함)"]
NOTE_LINES = [
    f"하템 벤 아르파(리옹·마르세유·뉴캐슬 유나이티드·헐 시티·니스·파리 생제르맹·렌·레알 바야돌리드·보르도·릴)의 클럽 공식 경기 {NG}경기({d_(first[0])} {KO[first[1]]}전 ~ {d_(last[0])} {KO[last[1]]}전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n} {c3(v)}" for n, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(1군 출전 {NG}경기)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음",
    "클럽·시즌별 경기·골은 영어 위키백과 경력 표와 모두 같음(427경기 74골). 프랑스어 위키백과는 리옹 2007-08(49경기 9골)·마르세유 2008-09(49경기)·2010-11(3경기 1골)·뉴캐슬 2011-12(35경기)·니스 2015-16(39경기)에 경기를 더 적었으나 경기별 자료가 없어 넣지 않음",
    "FotMob 경력 합계는 마르세유 88경기 14골·뉴캐슬 86·14·헐 9·0·니스 37·18·PSG 32·4·렌 41·9·바야돌리드 5·0·보르도 25·2·릴 9·0으로, 마르세유 외에는 Transfermarkt와 같음. FotMob에는 2010-11 이전 경기 기록이 없어 리옹·마르세유 2008~10의 골·도움은 Transfermarkt 리포트만 씀",
    "프랑스 대표팀, 리옹 유소년(2005.6.4 쿠프 감바르델라 결승 툴루즈 U19전 1골), 뉴캐슬 U21(2014.8.25 레딩 U21전 1골) 경기는 뺌. 2014.8.23 애스턴 빌라전·8.26 질링엄전(리그컵)은 Transfermarkt가 출전으로 세지 않고(다른 팀 소속 표시) 위키백과 2014-15 뉴캐슬 출전도 0이라 넣지 않음. PSG 2017-18은 1군 출전이 없음(명단 제외·부상)",
    f"골 {NGo}개 중 PK {NPK}개. 2010-11 이후 골은 FotMob 경기 기록과 수·PK 여부가 같음. FotMob과 골 시각이 1분 다른 것(2012.9.2 애스턴 빌라 59/60, 2016.1.4 쿠프 드 프랑스 렌전 연장 117/118)과 2014.3.22 크리스털 팰리스전 도움(Transfermarkt 90+4, FotMob 90)은 Transfermarkt 시각을 씀",
    "2005.7.27 트로페 데 샹피옹 오세르전 PK 골은 Transfermarkt·영어 위키백과 1분(RSSSF 2분)으로 1분을 씀",
    "도움은 2014.8.1 이전은 Transfermarkt 리포트 도움(유형이 비어 있는 도움 포함)을 쓰고, 그 뒤는 Transfermarkt와 FotMob 경기 기록이 같이 적은 도움을 기준으로 함. 2014.8 이후 Transfermarkt 도움은 다른 출처 1곳 이상(경기 기사·문자중계, 반대 출처 없음)이 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 선수 경기 성적 도움 {TM_A_API}개 − PK 유도 {EX['PK 유도']}개 − 상대 자책골로 이어진 슈팅 리바운드 {EX['상대 자책골 유도(슈팅 리바운드)']}개. 2012.8.18 토트넘전 80분 PK 골은 리포트에 본인이 얻은 PK의 본인 도움으로 적혀 있어 도움으로 세지 않음(선수 경기 성적에도 도움 0)",
    "PK 유도로 뺀 도움: " + jl("PK 유도"),
    "상대 자책골로 뺀 도움: 2008.8.17 오세르전 63분(벤 아르파 슈팅이 그리흐팅 맞고 들어감)",
    "2014.8 이후 FotMob 경기 기록에 도움이 없지만 다른 출처로 확인해 넣은 도움: 2014.9.24 리그컵 웨스트 브로미치전 50분 브래디 골(Sky Sports·Bleacher Report), 2015.12.15 쿠프 드 라 리그 갱강전 44분 망디 골(우에스트 프랑스 문자중계: 벤 아르파 컷백, 다른 선수 도움으로 적은 출처 없음), 2017.1.7 쿠프 드 프랑스 바스티아전 57분 모타 헤더(maxifoot·Corse Net Infos·FourFourTwo)와 89분 드락슬러 골(FourFourTwo·CulturePSG 문자중계). 바스티아전은 FotMob 경기 기록에 도움 칸이 모두 비어 있음",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(2010-11~2013-14는 FotMob과 일부 대조, 어긋나는 것 없음). 리옹·마르세유 2008~10은 대조할 자료가 없음",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(벤제마·주니뉴·말루다·디 마리아·카바니·루카스 모우라·파스토레 등) 값을 먼저 쓰고({SAME_N}개 기록), 없으면 기존 선수 자료의 같은 팀·같은 시즌 값, 그다음 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 모형에 넣음(리그1 2005-06·2007-08·2008-09·2009-10·2020-21 일부 팀; 그 시즌 기존 순위값이 없는 순위는 앞뒤 순위값 사이를 직선으로 나눈 값)",
    "리그 표가 없는 상대는 당시 수준을 추정함: " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED),
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·FA컵·리그컵은 16강까지·8강·준결승·결승, 트로페 데 샹피옹은 국내컵 결승, 2008-09 챔스 3차 예선(브란)은 챔스 예선, 2008-09 UEFA컵 32강·16강·8강과 유로파리그 32강 이후는 유로파 토너먼트로 계산함",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(UEFA컵·유로파리그: 원정 다득점·연장 적용). 단판 연장 골 2개(2004.11.10 쿠프 드 라 리그 릴전 101분 PK, 2016.1.4 쿠프 드 프랑스 렌전 117분 PK)",
    "시즌은 리옹·마르세유·PSG는 다른 선수 자료와 같이 7월 10일 기준(트로페 데 샹피옹 2005.7.27 = 2005-06, 2006.7.30 = 2006-07, 2007.7.28 = 2007-08, 2010.7.28 = 2010-11), 나머지는 8월 1일 기준(바야돌리드 2020.7 경기 = 2019-20)",
    "우승 기록은 Transfermarkt 업적 페이지 기준(리그1 5회·쿠프 드 프랑스 3회·쿠프 드 라 리그 2회·트로페 데 샹피옹 6회). 트로페 데 샹피옹 17/18 PSG는 출전 명단에 없었지만 업적 페이지에 있어 그대로 둠. U-17 유럽선수권 우승·득점왕은 대표팀 기록이라 뺌",
    "2026.11.12 기준: 마지막 출전은 2022.4.2 보르도전(릴). 릴과 계약이 2022.6.30 끝난 뒤 소속 팀이 없음. Transfermarkt는 2024.7.1부터 은퇴로 적지만 본인의 공식 은퇴 발표는 없음(2024~25 언론 보도: 은퇴를 공식 발표하지 않았고 2022년 여름 뒤로 경기를 뛰지 않음)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elq", "elk", "elg", "lg", "clq"]:
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
    gl = sorted([r for r in rs if r[0] == "g"], key=lambda r: (r[5] + r[6], r[4]))
    for a, b in zip(gl, gl[1:]):
        if b[5] < a[5] + 1 or b[6] < a[6]: problems.append(("스코어 역순", d, a[4], b[4]))
    allr = sorted(rs, key=lambda r: r[4])
    for a, b in zip(allr, allr[1:]):
        if b[5] < a[5] or b[6] < a[6]: problems.append(("시간순 스코어 역행", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
    if mdates[d] > 1: problems.append(("같은 날 두 경기", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 출전 행", d))
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
    mm = [m for m in M if m[0] == r[9]]
    if mm and mm[0][2] != r[3]: problems.append(("기록·출전 대회 코드 다름", r[9]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
js = f"const BNA_E={J(E)};\nconst BNA_M={J(M)};\nconst BNA_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg,
           "post_gap_tm_only": post_gap_log, "post_gap_verdicts": POST_GAP, "fm_only_assists": FM_ONLY, "fm_only_seen": fm_only_seen,
           "minute_fixes": min_fix, "cross_check": cross, "elo_sources": ELO_SRC,
           "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("분 고침", min_fix)
print("리그1 보간", INTERP)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if not (len(c) > 4 and c[4] == "일치"): print("  대조:", c)
print("대조 요약", collections.Counter((c[0], c[4] if len(c) > 4 and c[0].endswith("골") else "") for c in cross))
