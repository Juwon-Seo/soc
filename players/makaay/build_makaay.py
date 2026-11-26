#!/usr/bin/env python3
"""Roy Makaay (로이 마카이, Transfermarkt 3994): raw/ -> makaay.json + src/data/mak.js
(판정 근거는 judgments.md)

  python3 players/makaay/build_makaay.py            # 파일 쓰기
  python3 players/makaay/build_makaay.py --debug    # Elo 출처 로그만 출력

입력: raw/tm_games.csv(출전·분), raw/tm_schedule_all.csv(리포트 없는 경기의 현지 날짜), raw/tm_events.csv(리포트 골 목록),
      raw/tm_match_info.csv(리포트 머리·다른 차전), raw/ranks.txt(Transfermarkt 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값), src/data/*.js(같은 경기 다른 선수 자료, git에 있는 파일만).
"""
import csv, json, os, re, sys, subprocess, unicodedata, collections, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "mak.js")
OUT_JSON = os.path.join(HERE, "makaay.json")
ME = "3994"
ME_KO = "로이 마카이"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
SCHED = {r["gameId"]: r for r in rd("tm_schedule_all.csv")}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# ---------------------------------------------------------------- 판정 표
# 날짜: 리포트 날짜(현지) → 없으면 Transfermarkt 일정 페이지의 날짜(현지). API 날짜(UTC)는 시각 미정 경기 79개 등에서 하루 앞이라 쓰지 않음.
def ldate(g):
    d = g["date_local_tm_report"] or SCHED[g["gameId"]]["date_local"]
    if not d: sys.exit("날짜 없음 " + g["gameId"])
    return d
def opp(g): return g["opponent"].strip()

# 2군 경기 제외: 1993.10.10 KNVB컵 2라운드 De Treffers전(Transfermarkt 클럽 번호 36892 'Vitesse Arnhem U21'로 분류).
# 네덜란드어 위키백과 'KNVB beker 1993/94': "In de tweede ronde stroomden ... één reserveteam (Vitesse 2) ... in", 대진 'De Treffers – Vitesse 2',
# 비테서 1군은 3라운드(1993.11.10 De Graafschap – Vitesse)에 따로 나옴, 영어·독일어 위키백과 1993-94 컵 출전 0 → 2군(비테서 2) 경기
EXCLUDED = {"2232656": "1993.10.10 KNVB컵 2라운드 De Treffers–비테서 2(2군), 120분 1골"}

# 리포트 고침: 2005.5.7 마인츠–바이에른(21622) 리포트는 17분 아우어 골과 17분 마카이 골을 둘 다 '1:1 뒤'로 적음.
# worldfootball 경기 기록: 0:1 마카이 17'(발라크 도움), 1:1 아우어 35' → 아우어 골을 35분으로 옮겨 순서·스코어를 다시 셈(발라크 자료와 같음)
EV_MIN_FIX = {("21622", "805"): "35"}
# 2002.1.9 코파 델 레이 8강 1차전 바야돌리드전(2423393): 리포트 교체 목록이 마카이를 두 번(46분·76분) 뺌 — 61분에 골을 넣었으므로
# 46분 교체는 리포트 오류, 출전 76분(Transfermarkt 선수 경기 성적과 같음)
# 1998.12.16 코파 델 레이 베니도름 1차전(2422227): 리포트에 홈 골 1개가 빠짐(2:2인데 골 3개) — 마카이 골·도움이 없고 두 경기 모두 기록이 없어 영향 없음

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"NL1", "ES1", "L1", "PONL"}       # PONL: 2009 에레디비시 유럽 대항전 플레이오프(NAC 브레다 두 경기) = 리그(수아레스·메르턴스 선례)
CUP = {"NLP", "CDR", "DFB", "LPO"}           # LPO: DFL-리가포칼(준결승·결승 = 국내컵 준결승·결승, 클로제·고메스 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "SUC": return "df"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2000-01·2001-02 2차 조별('Group 2'·'Group 4') 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        sys.exit("CL 라운드 " + rnd)
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        return "elk"                                     # 2·3라운드·16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

PONL_LEG = {"946706": 1, "946709": 2}      # 라운드 이름이 '1. Matchday'·'2. Matchday'

def ko_of(cid, rnd, gid):
    r = rnd.lower()
    if "leg" in r or gid in PONL_LEG: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0                   # KNVB컵 1995-96 조별(Group 11)도 리그식
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid):
    """(원정 다득점, 연장)"""
    if cid in ("UEFA", "CL", "CDR", "SUC", "PONL", "NLP"): return (1, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] in (g["club_id"],): return "h"
    if m["away_id"] in (g["club_id"],): return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G:
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, m["other_leg_score"].split(":"))   # 이 리포트의 홈 팀 기준
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if gid in PONL_LEG:
        leg = PONL_LEG[gid]
    elif "leg" in rnd:
        leg = 1 if "1st" in rnd else 2
    else:
        return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"])
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    if gid in PONL_LEG:
        a, b = map(int, G["946706"]["score_club_opp"].split("-")); ours, theirs = a, b
    else:
        ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    if g["gameId"] in EXCLUDED: continue
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
def mins(s, gid):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s, 0
    v = int(s)
    et = 1 if (v > 90 and G[gid]["gameDuration"] == "120") else 0
    return v, 0, et

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

def assist_reason(e):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

# 1995.11.4 NAC 브레다–비테서(1093950): 리포트 골 목록의 홈·원정 표시가 뒤바뀜(마카이·라투헤루 골이 'home', 전반 1:2·끝 2:2) → 편과 스코어를 바꿔 읽음
SIDE_SWAP = {"1093950"}

def ordered_events(gid):
    evs = [dict(e) for e in EVS[gid]]
    if gid in SIDE_SWAP:
        for e in evs:
            e["side"] = "away" if e["side"] == "home" else "home"
            x, y = e["score_home_away_after"].split("-"); e["score_home_away_after"] = f"{y}-{x}"
    fixed = False
    for e in evs:
        k = (gid, e["scorer_id"])
        if k in EV_MIN_FIX: e["minute"] = EV_MIN_FIX[k]; fixed = True
    if fixed:
        evs.sort(key=lambda e: mins(e["minute"], gid)[0])
    # 골 순서대로 스코어를 다시 세어 리포트의 '골 뒤 스코어'와 대조(고친 경기만 다시 센 값 사용)
    h = a = 0; out = []
    for e in evs:
        if e["side"] == "home": h += 1
        else: a += 1
        rep = tuple(map(int, e["score_home_away_after"].split("-")))
        if rep != (h, a) and not fixed:
            SCORE_MISMATCH.append((gid, e["minute"], rep, (h, a)))
        e["after"] = (h, a) if fixed else rep
        out.append(e)
    return out

SCORE_MISMATCH = []
raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    evs = ordered_events(gid)
    if gid not in G or gid in EXCLUDED: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0)
    for e in evs:
        before = prev; prev = e["after"]
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if not (is_g or is_a): continue
        if e["side"][0] != side and not (is_a and is_og(e)):
            sys.exit("득점 편 이상 " + gid + " " + e["minute"])
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm, et = mins(e["minute"], gid)
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"], et))
        if is_g:
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"], et))

# 리포트 골·도움 = API 경기별 합계 점검(제외 경기 빼고)
cnt = collections.Counter()
for r in raw_rows: cnt[(r[1], r[0])] += 1
EXA = collections.Counter(j[1] for j in judg if j[0] == "도움 제외")
for gid, g in G.items():
    if gid in EXCLUDED: continue
    if cnt[(gid, "g")] != int(g["goals"]): sys.exit("골 수 불일치 " + gid)
    if cnt[(gid, "a")] + EXA[ldate(g)] * 0 > int(g["assists"]): sys.exit("도움 수 초과 " + gid)
    if int(g["penGoals"]) != sum(1 for r in raw_rows if r[1] == gid and r[0] == "g" and r[6]): sys.exit("PK 수 불일치 " + gid)

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
MANUAL_ALIAS = {"inter milan": "inter", "lokomotiv moskau": "lokomotiv moscow"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
TRACKED = set(subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b == "hon.js" or b == "mak.js" or "src/data/" + b not in TRACKED: continue   # 같은 회차 다른 판정 파일(미추적)은 뺌
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "rcd", "sv", "as", "ss",
        "cd", "ud", "vfl", "vfb", "bv", "rc", "ca", "kv", "fk", "sk", "tsv", "fsv", "milan", "inter", "madrid", "moscow", "moskau",
        "munich", "munchen", "amsterdam", "rotterdam", "eindhoven", "enschede", "alkmaar", "la", "coruna", "deportivo", "atletico", "athletic"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 기존 순위값
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

def half_up(x): return int(x + 0.5)
LGNAME = {"NL1": "에레디비시", "ES1": "라리가", "L1": "분데스리가", "NL2": "에이르스터 디비시", "L2": "2. 분데스리가", "ES2": "세군다"}
# 기존 자료의 순위값(리그·시즌·순위 → Elo, lv): 기존 lv 문구에서 모음
RV = collections.defaultdict(collections.Counter)
for (k, s), vals in TABLE.items():
    for e, lv in vals:
        m = re.match(r"(에레디비시|라리가|분데스리가|에이르스터 디비시|2\. 분데스리가|세군다)(\([^)]*\))? (\d{4}-\d\d) (\d+)위", lv)
        if m: RV[(m.group(1), m.group(3), int(m.group(4)))][(e, lv)] += 1
ERE = [1837, 1735, 1677, 1642, 1624, 1608, 1587, 1563, 1542, 1528, 1516, 1504, 1499, 1482, 1459, 1441, 1430, 1406]  # 에레디비시 18팀(모든 시즌 같은 값)
BUL = {1: 2006, 2: 1912, 3: 1860, 4: 1828, 5: 1812, 6: 1797, 7: 1777, 8: 1756, 9: 1737, 10: 1723, 11: 1713, 12: 1702, 13: 1697, 14: 1682,
       15: 1661, 16: 1644, 17: 1634, 18: 1613}  # 분데스리가 18팀(1999-00~2006-07 기존 값이 시즌과 상관없이 같음)
INTERP_USED = set()
def rank_model(lg, season, r, n):
    nm = LGNAME.get(lg)
    if not nm: return None
    c = RV.get((nm, season, r))
    if c:
        (e, lv), _ = c.most_common(1)[0]
        lv = re.sub(r"\s*\(추정, 선수 간 값.*\)$", "", lv)
        return e, lv
    if lg == "L2":   # 2. 분데스리가는 기존 값이 시즌과 상관없이 순위마다 같음(2001-02·2004-05 4위 1622, 9위 1584 등) → 같은 순위의 다른 시즌 값
        other = {e for (l2, s2, rr), cc in RV.items() if l2 == nm and rr == r for (e, _lv) in cc}
        if len(other) == 1:
            v = other.pop(); INTERP_USED.add((nm, season, r, v, "같은 순위 다른 시즌 값")); return v, f"{nm} {season} {r}위"
    if lg == "NL1": assert n == 18; return ERE[r - 1], f"에레디비시 {season} {r}위"
    if lg == "L1": assert n == 18; return BUL[r], f"분데스리가 {season} {r}위"
    if lg in ("ES1", "NL2", "L2"):
        pts = {rr: cc.most_common(1)[0][0][0] for (l2, s2, rr), cc in RV.items() if l2 == nm and s2 == season}
        lo = [k for k in pts if k < r]; hi = [k for k in pts if k > r]
        if lo and hi:
            a, b = max(lo), min(hi)
            v = half_up(pts[a] + (pts[b] - pts[a]) * (r - a) / (b - a)); INTERP_USED.add((nm, season, r, v))
            lab = f"에이르스터 디비시(네덜란드 2부) {season} {r}위" if lg == "NL2" and season < "2000" else f"{nm} {season} {r}위"
            return v, lab
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
def table_candidates(d):
    s = eu(d)
    return [("NL1", s), ("ES1", s), ("L1", s), ("NL2", s), ("L2", s), ("ES2", s)]

NLAM = "네덜란드 3부 이하 아마추어 (추정)"
# 순위표·기존 자료에 없는 상대(직접 추정, 모두 lv에 '추정') — judgments.md 6절
MAN = {
    ("HVV Hollandia Hoorn", "1995-96"): (1150, NLAM),           # 아마추어(호프트클라서), 판페르시 AGOVV 2002-03·ACV 아선 선례 1150
    ("SV Deurne", "2007-08"): (1150, NLAM),
    ("HHC Hardenberg", "2008-09"): (1150, NLAM),
    ("VV Harkemase Boys", "2009-10"): (1150, NLAM),
    # 러시아 2008(달력 연도) 2위(Transfermarkt RU1 2008 표) — 기존 자료의 러시아 2위 값 1604(CSKA 2009·스파르타크 2011-12)와 같게
    ("CSKA Moscow", "2008"): (1604, "러시아 2008 2위 (추정, 다른 선수 자료의 러시아 2위 값 1604와 같음)"),
}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1:
        print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    y = int(d[:4])
    # 유럽 대회 상대의 달력 연도 리그: 가을 경기는 그해, 봄 경기는 전해·그해 시즌
    seasons = ([eu(d), str(y)] if d[5:7] >= "07" else [eu(d), str(y - 1), str(y)]) if cid in ("CL", "UEFA") else [eu(d)]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for lg, s in table_candidates(d):
        t = RANKS.get((lg, s), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s, r, n)
            if res:
                ELO_SRC["순위표+기존 순위값"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    for s in seasons:
        if (o, s) in MAN:
            e, lv = MAN[(o, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc, et in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd, gid)
    elo, lv = opp_elo(opp(g), d, cid)
    if et and not ko: sys.exit("연장 골인데 단판 아님 " + gid)
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))

if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)
if "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    print("가운데값:", sorted(INTERP_USED))
    print("스코어 불일치:", SCORE_MISMATCH)
    sys.exit(0)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음, 보고용)
MATE_NAME = {"blk.js": "Michael Ballack", "piz.js": "Claudio Pizarro", "pod.js": "Lukas Podolski", "pau.js": "Pauleta"}
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] == "Roy Makaay":
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (x[5], x[6], x[2], x[12], x[3])
            cross.append(("동료 도움→마카이 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "마카이 골 없음"),
                          x[2:8], hit[0][2:8] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and r[13] == nm:
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (r[5], r[6], r[2], r[12], r[3])
                cross.append(("마카이 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else "동료 골 없음"), r[2:8], hit[0][2:8] if hit else None))
        for x in oe:
            if x[0] == "g":
                for j in judg:
                    if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3], "1")[0] - x[4]) <= 2:
                        cross.append(("TM 마카이 도움을 뺀 동료 골", b, x[9], x[4], j[5]))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[1], x[2], x[12], x[3]), (r[2], r[12], r[3])))
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                cross.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
DUP = set()
cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 클럽별 합계
CLUBS = [("vitmk", "1997-07-01", "비테서", "1993~1997"), ("tenmk", "1999-07-01", "테네리페", "1997~1999"),
         ("depmk", "2003-07-01", "데포르티보 라코루냐", "1999~2003"), ("baymk", "2007-07-01", "바이에른 뮌헨", "2003~2007"),
         ("feymk", None, "페예노르트", "2007~2010")]
TM_CLUB = {"499": "vitmk", "36892": "vitmk", "648": "tenmk", "897": "depmk", "27": "baymk", "234": "feymk"}
def club_of(d):
    for k, u, n, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
CN = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
TM_A_ALL = sum(1 for gid, evs in EVS.items() if gid in G and gid not in EXCLUDED for e in evs if e["assist_id"] == ME and e["scorer_id"] != ME)
SELF_PK = [j for j in judg if j[0].startswith("도움 아님")]
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
def jl(reason): return ", ".join(f"{d_(j[1])} {j[2]} {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
SHOT = "슈팅 리바운드('Shot on goal')"
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
ETG = [r for r in E if r[10]]

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
NOTE_LINES = [
    f"로이 마카이(비테서·테네리페·데포르티보 라코루냐·바이에른 뮌헨·페예노르트)의 클럽 공식 경기 {NG}경기({d_(first[0])} MVV 마스트리흐트전 ~ {d_(last[0])} 아약스전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CN[k]} {c3(v)}" for k, v in ST.items()),
    f"경기·출전 분은 Transfermarkt 선수 경기 성적(출전 {NG}경기·{MIN_TOT:,}분), 골 시간·골 직전 스코어·PK·도움은 Transfermarkt 경기 리포트 기준(골·도움이 있는 경기와 리그 밖 경기의 리포트 전부). 출전 시간 90분 추정 경기는 없음. FotMob은 이 선수의 클럽 경기 기록이 없어(챔스 2004-05~2006-07 시즌 합계만 있고 골 수·출전 분이 Transfermarkt와 같음) 대조하지 못함",
    "리그 경기·골 수는 영어·독일어·스페인어·네덜란드어 위키백과 경력 표와 시즌마다 같음(비테서 1993-94만 Transfermarkt 9경기, 위키백과 10~11경기). 위키백과 컵 칸은 리가포칼·수페르코파·2009 에레디비시 플레이오프를 빼고 세어 Transfermarkt와 다름",
    "뺀 경기: 1993.10.10 KNVB컵 2라운드 De Treffers 원정(1-2 연장 패, 120분 1골)은 Transfermarkt가 비테서 2군 번호로 분류했고 네덜란드어 위키백과 'KNVB beker 1993/94'가 '비테서 2'(2부 리그 팀·1부 일부 팀과 함께 2라운드에 들어온 2군 팀)로 적음 — 비테서 1군은 3라운드(1993.11.10 De Graafschap전)에 따로 나오고 영어·독일어 위키백과도 그 시즌 컵 출전 0이라 2군 경기로 보고 뺌",
    "비테서 1996-97 KNVB컵: Transfermarkt에는 16강 트벤테전(120분, 승부차기 승)·8강 헬몬트전(1골) 2경기만 있음. 위키백과는 5경기 3골(영어·독일어) 또는 6경기 3골(스페인어)이고, 네덜란드어 위키백과 대회 문서에는 조별 즈볼레 원정(1996.8.16, 1-1, 마카이 48분 골)·DOVO전(1996.9.18, 8-0, 마카이 44분 골)이 있으나, Transfermarkt 리포트에 라인업이 없고(마카이 '명단 제외'로 표시) 출전 여부·출전 시간을 알 수 있는 경기 자료가 없어 넣지 않음(골만 있는 경기를 넣으면 무득점 출전이 빠져 치우침). 이 때문에 이 시즌 컵 기록은 실제보다 2~4경기·2골 적을 수 있음",
    "2005.5.7 마인츠 원정 리포트는 17분 아우어(마인츠) 골과 17분 마카이 골을 둘 다 1:1로 적었으나, 다른 경기 기록(worldfootball)은 마카이 17분 0:1·아우어 35분 1:1이라 마카이 골 직전을 0:0으로 씀(발라크 자료와 같음). 2002.1.9 코파 델 레이 8강 1차전 바야돌리드전 리포트는 마카이를 46분·76분 두 번 교체로 적었으나 61분에 골을 넣었으므로 76분 교체(출전 76분)로 봄",
    f"PK 골 {NPK}개는 Transfermarkt 골 유형 'Penalty' 기준(선수 경기 성적의 PK 골 수와 경기마다 같음)",
    f"도움 {NA}개 = Transfermarkt 리포트 도움 {TM_A_ALL}개 − 'Shot on goal' 리바운드 {EX[SHOT]}개({jl(SHOT)}). 모두 2014년 이전이라 Transfermarkt 단일 출처이고 다른 출처로 대조하지 못함. 도움 유형 칸이 빈 {UNTYPED}개(주로 1990년대 리포트)도 도움으로 셈. PK 유도·상대 자책골에 준 도움은 없음",
    f"Transfermarkt 리포트가 2006.4.23 마인츠전 본인 PK 골(37분)에 본인 이름을 도움 칸('Penalty: Fouled player')에 적은 {len(SELF_PK)}개는 도움이 아님",
    "연장 골: 2008.9.24 KNVB컵 2라운드 TOP 오스전 92분(연장 전반, 0-0 뒤 연장 3-0 승 — Transfermarkt 경기 상태는 승부차기로 적었으나 리포트 골 순서와 대회 결과 기록이 연장 3-0)",
    "날짜는 경기 현지 날짜(Transfermarkt 리포트·일정 페이지 날짜). 선수 경기 성적의 날짜는 1990년대 시각 미정 경기 등에서 하루 앞서 쓰지 않음(예: 테네리페 마지막 경기 1999.6.13)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(발라크·피사로·포돌스키·파울레타 등) 값을 먼저 쓰고, 없으면 기존 선수 자료의 같은 팀·같은 시즌 값, 그다음 그 시즌 최종 순위(Transfermarkt 순위표)에 기존 자료의 순위별 값을 씀(기록 {len(E)}개: 같은 경기 {ELO_SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {ELO_SRC['기존 팀×시즌 값']}, 순위표+기존 순위값 {ELO_SRC['순위표+기존 순위값']}, 직접 추정 {ELO_SRC['직접 추정']})",
    "에레디비시·분데스리가는 다른 선수 자료와 같은 순위별 고정값, 라리가·에이르스터 디비시는 다른 선수 자료의 시즌별 순위값(빈 순위는 앞뒤 순위 값의 가운데)",
    "리그 표가 없는 KNVB컵 아마추어 상대(홀란디아 1995-96·SV 데우르너 2007-08·HHC 하르덴베르흐 2008-09·하르케마서 보이스 2009-10)는 네덜란드 3부 이하 아마추어 1150(추정, 다른 선수 자료의 아마추어 팀 값과 같음)",
    "대회 비중: KNVB컵·코파 델 레이·DFB-포칼은 국내컵(16강까지·8강·준결승·결승), KNVB컵 1995-96 조별리그는 리그식(무승부 1점), DFL-리가포칼은 준결승·결승을 국내컵 준결승·결승으로, 수페르코파(2002 발렌시아전 두 경기)는 국내컵 결승으로 계산함. 2009 에레디비시 유럽 대항전 플레이오프(NAC 브레다 두 경기)는 리그 비중으로, 원정 다득점·연장이 있는 두 경기 합산으로 계산함(수아레스·메르턴스 자료와 같음)",
    "UEFA컵: 1라운드는 유로파 예선, 조별리그(2008-09)는 유로파 조별, 2·3라운드·16강은 유로파 토너먼트. 챔스 2000-01·2001-02 2차 조별리그도 조별",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(UEFA 대회·코파 델 레이·수페르코파·에레디비시 플레이오프 모두 원정 다득점·연장)",
    "시즌 구분: 바이에른은 7월 10일 기준(7월 리가포칼 경기가 새 시즌, 클로제·발라크 자료와 같음), 나머지는 8월 1일 기준. 클럽 구분은 1997.7.1 전 비테서, 1999.7.1 전 테네리페, 2003.7.1 전 데포르티보, 2007.7.1 전 바이에른, 이후 페예노르트",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 유로·올림픽 등 대표팀 기록과 분데스리가 준우승·득점 2위는 뺌. 리가포칼은 Transfermarkt 표기(2005)대로 적음(실제 대회는 2004년 7~8월)",
    "은퇴: 2009-10 시즌 뒤 은퇴, 마지막 클럽 경기 2010.5.6 KNVB컵 결승 2차전 아약스전",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "elk", "elq", "elg", "cwc", "MAN", "TM "]:
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
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
mmin = {m[0]: m[3] for m in M}
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
js = f"const MAK_E={J(E)};\nconst MAK_M={J(M)};\nconst MAK_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": cross,
           "excluded_games": EXCLUDED, "elo_sources": ELO_SRC, "rank_midpoints": sorted(INTERP_USED), "score_mismatch_reports": SCORE_MISMATCH,
           "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · 연장 골 {len(ETG)} · Elo {dict(ELO_SRC)}")
for k, v in ST.items(): print(" ", k, v)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if not (len(c) > 4 and c[4] == "일치"): print("  대조:", c)
print("일치", sum(1 for c in cross if len(c) > 4 and c[4] == "일치"))
