#!/usr/bin/env python3
"""마우로 카모라네시 (Transfermarkt 5762): raw/ -> camoranesi.json + src/data/cam.js (판정 근거는 judgments.md)

  python3 players/camoranesi/build_camoranesi.py            # 파일 쓰기
  python3 players/camoranesi/build_camoranesi.py --debug    # Elo 출처 로그만 출력
  python3 players/camoranesi/build_camoranesi.py --stat     # 요약·동료 대조

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv(2010~13 골 대조), raw/ranks.txt·raw/mexico_group_tables.csv(Transfermarkt 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
주니뉴 build 스크립트를 바탕으로 함.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "cam.js")
OUT_JSON = os.path.join(HERE, "camoranesi.json")
ME = "5762"
ME_KO = "마우로 카모라네시"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

# 1999 베라노 14라운드 아메리카전(4-0, 카모라네시 2골): Transfermarkt 날짜 1999.3.17이 9라운드 네캑사전과 같은 날로 적힘.
# RSSSF 클라시코 호벤 기록 1999.4.17(스페인어 위키백과 Torneo Verano 1999는 4.15) → 13라운드(4.11)·15라운드(4.25) 사이인 RSSSF 날짜를 씀
DATE_FIX = {"3684306": "1999-04-17"}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local"])
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용(선수 경력이 모두 이전)

# ---------------------------------------------------------------- 대회 코드
# ITPO: 2001.6 세리에A 잔류 플레이아웃(베로나-레지나 두 경기) = 리그 경기(인자기·호나우두 ITPO 선례) + 두 경기 합산
LEAGUE = {"IT1", "IT2", "L1", "ARG1", "ARGC", "ARG3", "MEXA", "MEX1", "ITPO"}
LIGUILLA = {"POMX", "POME"}   # 멕시코 리귈라(우승 결정 플레이오프) = MLS 플레이오프와 같은 비중(북미 리그 플레이오프 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in LIGUILLA:
        if r.startswith("final"): return "mlpf"
        if r.startswith("semi"): return "mlpsf"
        return "mlp"
    if cid in ("CIT", "DFB", "ARCA"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "SCI": return "df"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                       # 32강('Second Round')·16강
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"
    if cid == "CS":
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r: return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "CLQ", "EL"): return (1, 1)        # UEFA 2020-21까지
    if cid == "CIT": return (1, 1)                      # 코파 이탈리아 2021-22까지 원정 다득점, 연장
    if cid == "ITPO": return (1, 0)                     # 2001 잔류 플레이아웃: 원정 다득점으로 베로나 잔류(기사), 연장 규정 미확인 → 인자기 ITPO 선례(연장 없음)
    if cid in LIGUILLA: return (0, 0)                   # 1999 리귈라: 동률 시 정규리그 상위 팀 진출(모형에 없음) → 원정 다득점·연장 없음으로 둠
    if cid == "CLI": return (1, 0)
    if cid == "CS": return (1, 0)                       # 주니뉴 2011 수다메리카나 선례
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
    oh, oa = map(int, m["other_leg_score"].split(":"))
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
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
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
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

# 리포트 골 수 = 최종 스코어 점검(승부차기 제외) / 골 목록 순서대로 센 스코어 = 리포트 스코어 라벨 점검
SCORE_MISMATCH, LABEL_MISMATCH = [], []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
    c = {"h": 0, "a": 0}
    for e in evs:
        c[e["side"][0]] += 1
        if f"{c['h']}-{c['a']}" != e["score_home_away_after"]: LABEL_MISMATCH.append((gid, ldate(G[gid]), e["minute"], e["score_home_away_after"])); break
# 이 세 경기(1181465·2372462·65611)는 리포트 표기 문제이며 카모라네시의 골·도움이 없음(judgments.md 3절)
G_WITH_ME = {r[1] for r in raw_rows}
for x in LABEL_MISMATCH:
    if x[0] in G_WITH_ME: sys.exit("스코어 라벨 불일치가 카모라네시 기록 경기에 있음 " + str(x))

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
MANUAL_ALIAS = {"inter milan": "inter", "club atletico morelia": "monarcas morelia", "cd cruz azul": "cruz azul"}
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
    if b in ("hon.js", "cam.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio", "sport",
        "cd", "ud", "rcd", "sv", "as", "ss", "us", "bc", "milan", "inter", "ca", "cs", "deportivo", "atletico", "san", "santa", "1909", "1898", "1993"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
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
def half_up(x): return int(x + 0.5)

# 멕시코 1부 시즌 누적 순위(인비에르노+베라노): Transfermarkt 조별 순위표(4개 조, 18팀)의 경기·승점·득실·득점을 두 대회 합산해
# 승점 → 득실차 → 다득점 순으로 18팀 통합 순위를 만듦(공식 통합표가 아님 — 디 마리아 아르헨티나 두 조 통합 순위 선례,
# '리가MX 2014-15 누적' 선례). Elo = 리가MX 모형 1604.25 + 73.41 × 곡선(순위, 18팀): 기존 자료의 리가MX 순위값
# (아페르투라 2014 1·3·5·9·10·11·17·18위 1789·1683·1648·1594·1584·1576·1519·1503, 2025-26 7·9위 1623·1594)을 ±1로 재현하는 값.
MX_MEAN, MX_SD = 1604.25, 73.41
def mex_tables():
    acc = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, 0, 0]))
    names = {}
    for r in rd("mexico_group_tables.csv"):
        c = [x.strip() for x in r["cells_raw(played|W|D|L|goals|gd|pts as printed by TM)"].split("|")]
        gfor, gag = map(int, c[4].split(":"))
        s = f"{r['tm_saison']}-{str(int(r['tm_saison']) + 1)[2:]}"
        k = key(r["team"]); names.setdefault(k, r["team"])
        a = acc[s][k]; a[0] += int(c[6]); a[1] += gfor - gag; a[2] += gfor; a[3] += int(c[0])
    out = {}
    for s, t in acc.items():
        if len(t) != 18 or any(v[3] != 34 for v in t.values()): sys.exit("멕시코 표 이상 " + s)
        order = sorted(t, key=lambda k: (-t[k][0], -t[k][1], -t[k][2]))
        out[s] = {k: (i + 1, t[k]) for i, k in enumerate(order)}
    return out
MEX = mex_tables()

# 아르헨티나 1부: 평균 1583, 흩어짐 63(문서 4절) × 곡선(반시즌 순위/20팀). lv는 주니뉴·호나우지뉴 형식 "아르헨티나 1부 2011-12 클라우수라 10위 (리그 수준 추정)"
ARG_T = {"ARGC|2010-11 Clausura": ("2010-11", "클라우수라"), "ARG1|2011 Apertura": ("2011-12", "아페르투라"),
         "ARGC|2011-12 Clausura": ("2011-12", "클라우수라"), "ARG1|2012-13 Inicial": ("2012-13", "이니시알"), "ARGC|2012-13 Final": ("2012-13", "피날")}
def arg_tab(d):
    """경기 날짜 → 그 반시즌 순위표 키"""
    if d < "2011-07-01": return "ARGC|2010-11 Clausura"
    if d < "2012-01-15": return "ARG1|2011 Apertura"
    if d < "2012-07-15": return "ARGC|2011-12 Clausura"
    if d < "2013-01-15": return "ARG1|2012-13 Inicial"
    if d < "2013-07-15": return "ARGC|2012-13 Final"
    return None

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e[12] or "")
        if m: c[int(m.group(1))][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 7: 1762, 8: 1743, 9: 1728, 10: 1713, 11: 1704, 12: 1697,
        13: 1690, 14: 1676, 15: 1657, 16: 1645, 17: 1633, 18: 1614}
def mid_fill(m, r):
    lo = max([k for k in m if k < r], default=None); hi = min([k for k in m if k > r], default=None)
    if lo is None or hi is None: return None
    return half_up(m[lo] + (m[hi] - m[lo]) * (r - lo) / (hi - lo))

def rank_model(lg, season, r, n):
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        if n == 18: return SA18[r], f"세리에A {season} {r}위"
        v = mid_fill(m, r)
        if v: return v, f"세리에A {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
SOUTH = {"ARG1", "ARGC", "ARCA", "CLI", "CS"}
MEXC = {"MEXA", "MEX1", "POMX", "POME"}

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o); y = d[:4]
    seasons = [eu(d), y] if (cid in SOUTH or cid in MEXC) else [eu(d)]
    for s in seasons:
        cands = TABLE.get((k, s), [])
        if k == key("Arsenal FC") and cid in SOUTH: cands = [c for c in cands if "아르헨티나" in c[1]]   # 아르센알 데 사란디 ≠ 아스널(잉글랜드)
        if cands:
            (e, lv), _ = collections.Counter(cands).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    res = None
    if cid in MEXC:
        s = eu(d)
        if k in MEX.get(s, {}):
            r, v = MEX[s][k]
            res = (half_up(MX_MEAN + MX_SD * curve(r, 18)),
                   f"멕시코 1부 {s} 누적 {r}위 (추정, 인비에르노·베라노 조별 순위표를 합친 승점 순위에 리가MX 모형)")
    elif cid in SOUTH:
        tk = arg_tab(d)
        if tk:
            lg, lab = tk.split("|"); t = RANKS.get((lg, lab), {})
            if k in t:
                r, n, _ = t[k]; s, nm = ARG_T[tk]
                res = (half_up(1583 + 63 * curve(r, n)), f"아르헨티나 1부 {s} {nm} {r}위 (리그 수준 추정)")
    elif cid in ("IT1", "CIT", "ITPO", "SCI"):
        t = RANKS.get(("IT1", eu(d)), {})
        if k in t: res = rank_model("IT1", eu(d), t[k][0], t[k][1])
    if res:
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

# 같은 팀·같은 시즌 한 값: 콜론 2012-13은 수다메리카나(2012.8)와 피날 리그 경기(2013.4)를 같은 값(피날 17위)으로
FORCE = {}

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    if key(opp(g)) == key("CA Colón") and eu(d) == "2012-13":
        elo, lv = opp_elo(opp(g), "2013-04-19", "ARGC"); ELO_LOG[(opp(g), d)] = ("force", elo, lv)
    else:
        elo, lv = opp_elo(opp(g), d, cid)
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
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]): print(d, o, v)
    print("label mismatch", LABEL_MISMATCH); print("score mismatch", SCORE_MISMATCH)
    for s, t in MEX.items():
        print(s, [(r, k, v[0]) for k, (r, v) in sorted(t.items(), key=lambda kv: kv[1][0])])
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010~13)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r.get("player_scorer", r.get("jp_scorer")) == "1"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], len(fm)))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None): d.append("단판/합산")
    if a[10] != b[10]: d.append("연장")
    return d
REG = {"Alessandro Del Piero": "del.js", "Pavel Nedved": "ned.js", "Zlatan Ibrahimović": "ibr.js"}
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Camoranesi", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(카모라네시 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a" and REG.get(r[13]) == b:
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1]))]
            if hit: CROSS.append(("카모라네시 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
            else:
                # 동료 파일에 이 날 같은 상대 기록이 있는데 득점자 골 행이 없으면 보고
                pass
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
# 동료 골에 TM 카모라네시 도움이 있었는데 규칙으로 뺀 것
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and (key(x[1]) == key(j[2]) or toks(x[1]) & toks(j[2])):
                    CROSS.append(("TM 카모라네시 도움을 규칙대로 뺀 타인 골", b, x[9], x[4], j[5]))
# 카모라네시 도움→득점자가 등록 선수(델 피에로·네드베드·이브라히모비치)인데 그 선수 파일에 골 행이 없는 것
REG = {"Alessandro Del Piero": "del.js", "Pavel Nedved": "ned.js", "Zlatan Ibrahimović": "ibr.js"}
for r in E:
    if r[0] == "a" and r[13] in REG:
        oe = OTHERS[REG[r[13]]][0]
        if not [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]:
            CROSS.append(("등록 선수 골 행 없음", REG[r[13]], r[9], r[4], r[13]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("aldcam", "1996-01-01", "알도시비", "1995"), ("czcam", "2000-07-01", "크루스 아술", "1998~2000"),
         ("vercam", "2002-07-11", "헬라스 베로나", "2000~2002"), ("juvcam", "2010-08-31", "유벤투스", "2002~2010"),
         ("vfbcam", "2011-02-02", "슈투트가르트", "2010~2011"), ("lancam", "2012-07-22", "라누스", "2011~2012"),
         ("raccam", None, "라싱 클루브", "2012~2014")]
TM_CLUB = {"12301": "aldcam", "3711": "czcam", "276": "vercam", "506": "juvcam", "79": "vfbcam", "333": "lancam", "1444": "raccam"}
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
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
def season_of(d, club):
    y = int(d[:4])
    if club == "juvcam": s = y if d[5:] >= "07-10" else y - 1
    else: s = y if int(d[5:7]) >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    print("FotMob", FM_CMP)
    for c in CROSS: print(c)
    for j in judg: print(j)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    for r in E:
        if len(r) > 14: print("tie", r)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
SRC = ELO_SRC
first, last = M[0], M[-1]
NOTE_LINES = [
    f"마우로 카모라네시(알도시비·크루스 아술·헬라스 베로나·유벤투스·슈투트가르트·라누스·라싱 클루브)의 클럽 공식 경기 {NG}경기({d_(first[0])} 알바라도전 ~ {d_(last[0])} 뉴웰스 올드 보이스전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·이탈리아 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CN[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(출전 분이 빈 경기 없음, 90분 추정 0경기), 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(리포트 골 60개·도움 106개가 선수 경기 성적과 경기마다 같음). 유벤투스·베로나 시즌별 경기·골은 영어·스페인어·이탈리아어 위키백과와 같고(베로나는 스페인어 위키백과 55경기 7골 11도움과 같음, 영어·이탈리아어는 잔류 플레이아웃 2경기를 빼 53경기), 슈투트가르트·라누스·라싱도 위키백과 합계와 같음",
    "FotMob은 2010-11 이후(슈투트가르트·라누스·라싱) 골이 있는 경기만 대조함: 카모라네시 골 4개는 분이 1분 차이(2012.4.3 올림피아전 30/29분, 2012.12.1 올보이스전 28/29분, 2013.3.17 벨그라노전 11/12분, 2013.4.19 콜론전 67/66분)라 Transfermarkt 분을 씀. FotMob 경기 기록에는 카모라네시 도움이 하나도 없음(이 기간 FotMob 도움 칸이 거의 비어 있음)",
    "넣지 못한 경기(경기별 날짜·출전·골 시각 자료를 찾지 못함): 산토스 라구나 1995~97(위키백과 13경기 1골), 몬테비데오 원더러스 1997(6경기 1골), 반필드 1997-98(아르헨티나 2부, 38경기 16골)은 Transfermarkt에 출전 경기가 없고 FotMob에도 없어 뺌. 알도시비는 Transfermarkt 1995년 2경기(아르헨티나 3부, 골 없음)만 넣음 — 위키백과는 1994-95 31경기 0골(영어·이탈리아어)·15경기 2골(스페인어)로 서로 다름. 크루스 아술은 Transfermarkt 68경기 17골(정규리그 57경기 16골, 리귈라 11경기 1골)이고 위키백과는 75~76경기 21골이라 약 7경기 4골이 빠져 있음(어느 경기인지 경기별로 가릴 수 없음). 따라서 1995~2000년 기록은 실제보다 적음",
    "크루스 아술 리포트 가운데 1999.2.5 테코스전(2-0)·2000.3.25 아틀라스전(1-1)·2000.4.16 과달라하라전(3-4)·2000.4.22 아틀란테전(2-2)·2000.4.29 톨루카전(3-2)은 골 목록이 없음. 선수 경기 성적상 이 다섯 경기의 카모라네시 골·도움은 0이라 출전만 넣음. 멕시코 경기 골은 Transfermarkt에 골 유형이 거의 없어 PK 여부를 확인하지 못함(모두 일반 골로 셈)",
    f"도움: 2014년 8월 이전 도움은 Transfermarkt 경기 리포트 단일 출처(클로제·인시녜·네드베드 선례, 선수 경력이 모두 그 이전). Transfermarkt 도움 106개에서 슈팅 리바운드('Shot on goal') 2개(2002.1.6 피아첸차전 74분 찬키, 2002.4.14 우디네세전 32분 프리크), 상대 자책골에 준 도움 3개(2004.4.4 인테르전 25분, 2008.11.13 제노아전 90+2분, 2009.4.5 키에보전 53분), PK 유도 1개(2005.1.30 아탈란타전 80분 델 피에로 PK)를 빼 {NA}개. 도움 유형 칸이 빈 {UNTYPED}개는 일반 도움으로 셈. 2005.1.9 리보르노전 90분 PK 골에 본인을 도움으로 적은 표기는 도움으로 세지 않음. 스페인어 위키백과 시즌별 도움(유벤투스 77·베로나 11·라누스 12·라싱 3)은 Transfermarkt와 합계가 같거나(라싱만 3 대 2) 시즌 배분만 다름",
    "골: 자책골 없음. PK 골 1개(2005.1.9 리보르노전 90분, 선수 경기 성적 PK 골 수와 같음). 골 직전 스코어는 리포트 골 목록 순서 기준(카모라네시 골·도움이 있는 모든 경기에서 목록 순서·스코어 표기·최종 스코어가 맞음). 리포트 표기가 어긋난 세 경기(2006.8.27 코파 이탈리아 나폴리전 연장 골 순서, 2006.11.1 브레시아전 자책골 편 표기, 2012.5.21 아르센알전 36분 두 골 순서)는 카모라네시 골·도움이 없어 영향 없음",
    "출전 분: Transfermarkt 그대로. 연장 경기 120분: 2005.3.9 챔스 16강 2차전 레알 마드리드전, 2012.5.9 리베르타도레스 16강 2차전 바스쿠전(승부차기). 2003.5.28 챔스 결승 밀란전(승부차기)은 46분, 1999.12.19 리귈라 결승 2차전 파추카전(연장)은 92분",
    "날짜: 유럽 경기는 Transfermarkt 리포트 날짜(현지). 아르헨티나·멕시코 경기는 경기 시각(UTC)을 현지 시간대로 바꾼 날짜를 씀(아르헨티나 47경기는 리포트 날짜보다 하루 앞). 2003년 이전 미주 경기는 시각 자료가 자리표시 값이라 일정 날짜 그대로. 1999 베라노 14라운드 아메리카전(4-0, 카모라네시 2골)은 Transfermarkt가 9라운드 네캑사전과 같은 1999.3.17로 적어 RSSSF 클라시코 호벤 기록의 1999.4.17로 고침(스페인어 위키백과는 4.15)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(델 피에로·네드베드·이브라히모비치 등), 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 순위표를 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['기존 팀×시즌 값']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "세리에A 2000-01(18팀)은 델 피에로·토티 자료와 같은 18팀 순위값. 아르헨티나 1부는 Transfermarkt 반시즌(클라우수라 2011·아페르투라 2011·이니시알 2012·피날 2013) 순위표를 평균 1583·흩어짐 63 모형에 넣은 값(리그 수준 추정). 'Arsenal FC'는 아르센알 데 사란디(잉글랜드 아스널 값을 쓰지 않음). 콜론 2012-13은 2012.8 수다메리카나 경기도 같은 시즌 피날 2013 리그 경기와 같은 값(17위)으로 둠",
    "멕시코 1부(1998-99·1999-00)는 이 계산기에 그 시기 순위값이 없어 새로 추정함: Transfermarkt 인비에르노·베라노 조별 순위표(4개 조, 18팀)를 시즌 단위로 합쳐 승점·득실차·다득점 순으로 18팀 누적 순위를 만들고(공식 통합표 아님), 기존 리가MX 순위값과 같은 모형(평균 약 1604, 흩어짐 약 73)에 넣음. 과달라하라 1998·네캑사 1999-00은 다른 선수 자료의 추정값(1560)을 그대로 씀",
    "대회 비중: 코파 이탈리아·DFB-포칼·코파 아르헨티나는 국내컵(16강까지·8강·준결승·결승), 수페르코파 이탈리아나는 국내컵 결승 비중. 유로파리그 32강·16강은 유로파 토너먼트. 멕시코 리귈라(정규리그 뒤 우승 결정 플레이오프)는 MLS 플레이오프와 같은 비중(8강·준결승·결승). 2001.6 세리에A 잔류 플레이아웃(베로나-레지나)은 리그 경기 비중(인자기·호나우두 자료의 세리에A 플레이오프 선례)",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·코파 이탈리아는 원정 다득점·연장. 2001 잔류 플레이아웃은 원정 다득점(1차전 베로나 1-0, 2차전 레지나 2-1, 85분 코사토 골로 베로나 잔류 — 이탈리아 기사들은 86분, 분은 Transfermarkt), 연장 규정은 확인하지 못해 없음으로 둠. 1999 리귈라는 합계 동률이면 정규리그 상위 팀이 올라가는 방식이라 원정 다득점·연장 없음으로 둠(상위 팀 규정은 계산에 넣지 않음). 수다메리카나는 원정 다득점 있고 연장 없이 승부차기(다른 선수 자료 선례). 못 뛴 다른 차전 스코어는 Transfermarkt 리포트로 채움",
    "시즌 구분: 유벤투스는 7월 10일 기준(델 피에로·네드베드 유벤투스와 같음, 7월 경기 없음), 나머지는 8월 1일 기준(크루스 아술 1998-99 = 인비에르노 1998+베라노 1999, 라누스·라싱은 아페르투라·이니시알이 시즌 시작). 클럽 구분: 1996.1.1 전 알도시비, 2000.7.1 전 크루스 아술, 2002.7.11 전 베로나, 2010.8.31 전 유벤투스, 2011.2.2 전 슈투트가르트, 2012.7.22 전 라누스, 이후 라싱(Transfermarkt 이적 기록 기준, 경기 클럽과 경계 불일치 0)",
    "같은 경기 동료 자료: 델 피에로·네드베드·이브라히모비치(유벤투스)와 주고받은 골·도움은 날짜·분·골 전 스코어·대회·상대 Elo·수준 설명이 모두 같음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 세리에A 2002-03, 수페르코파 이탈리아나 2002-03·2003-04, 세리에B 2006-07(유벤투스). 챔스 준우승 2002-03. 2004-05·2005-06 세리에A 우승은 박탈돼 페이지에 없음. 대표팀(2006 월드컵 우승)은 뺌",
    "은퇴: 2014년 라싱에서 은퇴(Transfermarkt 2014.7.1 은퇴, 영어·스페인어 위키백과 2014), 마지막 클럽 경기 2014.3.16 뉴웰스 올드 보이스전(22분)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elk", "elq", "cwc", "MAN", "csa", "lib", "mlp"]:
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
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
mm_ = {m[0]: m for m in M}
Gstart = {ldate(g): g["isStarting"] == "True" for g in GAMES}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > m[3] + 3 and not r[10] and Gstart[r[9]]: problems.append(("출전 분보다 늦은 기록", r, m))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const CAM_E={J(E)};\nconst CAM_M={J(M)};\nconst CAM_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "label_mismatch": LABEL_MISMATCH,
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
