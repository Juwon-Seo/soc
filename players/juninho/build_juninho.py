#!/usr/bin/env python3
"""주니뉴 페르남부카누 (Transfermarkt 5354): raw/ -> juninho.json + src/data/jun.js (판정 근거는 judgments.md)

  python3 players/juninho/build_juninho.py            # 파일 쓰기
  python3 players/juninho/build_juninho.py --debug    # Elo 출처 로그만 출력
  python3 players/juninho/build_juninho.py --stat     # 요약

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv(2011~13 골 대조), raw/ranks.txt(Transfermarkt 순위표), raw/tables/rsssf_braz-joao00.html(2000 블루 모듈),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, html as HTML

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "jun.js")
OUT_JSON = os.path.join(HERE, "juninho.json")
ME = "5354"
ME_KO = "주니뉴 페르남부카누"

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

def ldate(g): return g["date_local"]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 판정 표
# 출전 분이 없는 4경기(TM playedMinutes 0·빈칸): 90분 추정(M 행 다섯째 칸 1). 4412502·4406414는 선발 표시, 4601821·4601845는 교체 정보 없음.
MIN_EST = {"4412502": 90, "4406414": 90, "4601821": 90, "4601845": 90}
# 2000.1.14 클럽 월드 챔피언십 결승 코린치안스전(0-0 뒤 연장 없이 승부차기)의 TM 출전 96분은 그대로 둠.
EXCL_G = {}      # 골 제외 없음(본인 자책골 0, 도움 자동 제외는 아래 규칙)
GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용(선수 활동 기간이 모두 이전)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BRA1", "FR1", "MLS1"}
STATE = {"BRCG", "BRCR", "BRCF"}      # 캄페오나투 카리오카(2012 조별 BRCG·타사 히우 BRCR·결승 BRCF): 국내컵 하위 비중(네이마르 파울리스타 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid == "BRC":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("FRC", "FRL"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "FRCH": return "df"          # 트로페 데 샹피옹 = 슈퍼컵 = 국내컵 결승
    if cid == "MLSP": return "dc"          # US 오픈컵 3라운드·16강
    if cid in ("WEPO", "KLUB"): return "cwc"
    if cid == "CI98": return "df"          # 코파 인터아메리카나 1998(바스쿠-D.C. 유나이티드 두 경기 결승) = 슈퍼컵류
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "UEFA":
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                       # 3라운드(32강)·16강
    if cid == "AFCL":
        if r.startswith("quarter"): return "aclk"
        return "acl"
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"
    if cid in ("CS", "CCON", "SCSA", "CMER"):   # 수다메리카나·코파 코네북(2부 대회)·수페르코파 수다메리카나(호나우두 1993 선례)·코파 메르코수르(2부 대회로 봄)
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or r.startswith("matchday") or re.match(r"^\d+\. matchday", r): return 0
    if cid in ("BRCG", "BRCR") and (r.startswith("group") or "matchday" in r): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    r = rnd.lower()
    if cid in ("UEFA", "CL"): return (1, 1)             # UEFA 대회 2020-21까지 원정 다득점·연장
    if cid == "BRCF": return (0, 0)                     # 카리오카 결승 두 경기: 원정 다득점·연장 없음(파울리스타 선례)
    if cid == "BRC": return (1, 0)                      # 코파 두 브라질: 원정 다득점, 연장 없음(네이마르 선례)
    if cid == "CLI":
        if r.startswith("final") and d >= "2000-01-01": return (0, 1)
        return (1, 0)
    if cid in ("CS", "CMER", "CI98"): return (1, 0)
    if cid in ("CCON", "SCSA"): return (0, 0)
    if cid == "AFCL": return (0, 1)                     # AFC 대회 원정 다득점 없음
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
    gid = g["gameId"]
    row = [ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), MIN_EST.get(gid, int(g["playedMinutes"] or 0))]
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

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1           # 리포트 골 순서대로 득점 팀별로 셈(자책골은 득점 팀 기준 표시)
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

# 리포트 골·도움 = API 경기별 합계 점검
cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)

# 리포트 골 수 = 최종 스코어 점검(승부차기 제외)
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
MANUAL_ALIAS = {"inter milan": "inter", "lokomotiv moskau": "lokomotiv moscow", "olympique lyon": "olympique lyonnais"}
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
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "milan", "inter", "madrid", "moscow", "moskau", "paulista", "paulo", "ca", "cs", "club", "deportivo", "deportes", "universidad", "san", "santa"}
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
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
# 2000 브라질 1부: TM 표(29팀)는 1위가 크루제이루로 나와 믿기 어려움 → RSSSF 'Copa João Havelange 2000' 블루 모듈 25팀 1단계 순위(기존 선수 자료의 2000 순위값도 25팀 곡선)
def rsssf_blue_2000():
    t = open(os.path.join(RAW, "tables", "rsssf_braz-joao00.html"), encoding="latin-1").read()
    t = HTML.unescape(re.sub("<[^>]+>", "", t))
    i = t.find("Table:"); out = {}
    for line in t[i:i + 3000].split("\n"):
        m = re.match(r"\s*(\d+)\.(\S.*?)\s{2,}\d+\s+\d+", line)
        if m and int(m.group(1)) <= 25: out[int(m.group(1))] = m.group(2).strip()
    return out
BLUE00 = rsssf_blue_2000()
if len(BLUE00) != 25: sys.exit("블루 모듈 표 파싱 실패 %d" % len(BLUE00))
BLUE_NAMES = {"Cruzeiro": "Cruzeiro Esporte Clube", "Sport": "Sport Club do Recife", "Fluminense": "Fluminense Football Club", "Goiás": "Goiás EC",
              "Vasco da Gama": "Clube de Regatas Vasco da Gama", "São Paulo": "São Paulo Futebol Clube", "Ponte Preta": "Associação Atlética Ponte Preta",
              "Atlético-PR": "Atlético Paranaense", "Internacional-RS": "Sport Club Internacional", "Grêmio": "Grêmio Foot-Ball Porto Alegrense",
              "Palmeiras": "Sociedade Esportiva Palmeiras", "Bahia": "Esporte Clube Bahia", "Guarani": "Guarani Futebol Clube (SP)",
              "Santos": "Santos FC", "Flamengo": "CR Flamengo", "Botafogo-RJ": "Botafogo de Futebol e Regatas", "Portuguesa": "Portuguesa",
              "Vitória": "Esporte Clube Vitória", "América-MG": "América Futebol Clube (MG)", "Atlético-MG": "Clube Atlético Mineiro",
              "Juventude": "Esporte Clube Juventude", "Gama": "Sociedade Esportiva do Gama (DF)", "Coritiba": "Coritiba Foot Ball Club",
              "Corinthians": "Sport Club Corinthians Paulista", "Santa Cruz": "Santa Cruz FC (PE)"}
for r, nm in BLUE00.items():
    RANKS[("BRA1", "2000")][key(BLUE_NAMES.get(nm, nm))] = (r, 25, nm)
RANKS[("BRA1", "2000")] = {k: v for k, v in RANKS[("BRA1", "2000")].items() if v[1] == 25}

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
def half_up(x): return int(x + 0.5)

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
LL_SD = 100.16
INTERP_USED = set()

def rank_model(lg, season, r, n):
    if lg == "BRA1":
        return half_up(1598 + 63 * curve(r, n)), f"브라질 세리에 A {season} {r}위"
    if lg == "BRA2":
        return half_up(1370 + SD2 * curve(r, n)), f"브라질 세리에 B {season} {r}위"
    if lg == "ARGC":     # 아르헨티나 1부: 평균 1583, 흩어짐 63(클라우수라·아페르투라 반시즌 순위표)
        return half_up(1583 + 63 * curve(r, n)), f"아르헨티나 1부 {season} {r}위/{n}팀 (순위표 반시즌)"
    if lg == "FR1":
        m = ents_map("리그1", season)
        v, it = mid(m, r)
        if v is None:
            v = edge(m, r, n, LL_SD); INTERP_USED.add((season, r, v, "끝"))
            return v, f"리그1 {season} {r}위 (추정, 이웃 순위값에 순위 곡선 차이)"
        if it: INTERP_USED.add((season, r, v))
        return v, f"리그1 {season} {r}위"
    if lg == "FR2":
        m = ents_map("리그2", season)
        v, it = mid(m, r)
        if v is None: return half_up(1540 + SD2 * curve(r, n)), f"리그2 {season} {r}위 (추정, 프랑스 2부 평균 1540 모형)"
        return v, f"리그2 {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
SOUTH = {"BRA1", "BRCG", "BRCR", "BRCF", "BRC", "CLI", "CS", "CMER", "CCON", "SCSA", "CI98"}

# 순위표·기존 자료에 없는 상대(직접 추정, 모두 lv에 '추정') — judgments.md
C4 = "브라질 4부 이하 (추정)"
MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid, rnd=""):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    y = d[:4]
    if cid in SOUTH or cid == "MLS1" or cid == "MLSP":
        # 2001.1 코파 주앙 아벨란제 결승 단계는 2000 대회
        yy = "2000" if (cid == "BRA1" and d < "2001-02-01" and d >= "2001-01-01") else y
        seasons = [yy]
    elif cid in ("CL", "UEFA", "WEPO", "KLUB", "AFCL"):
        seasons = [eu(d), y, str(int(y) - 1)] if int(d[5:7]) < 7 else [eu(d), y]
        if cid in ("WEPO", "KLUB"): seasons = [eu(d), y, str(int(y) - 1)]
        if cid == "AFCL": seasons = [y, eu(d)]
    else:
        seasons = [eu(d)]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    lgs = []
    if cid in SOUTH:
        lgs = [("BRA1", s) for s in seasons] + [("BRA2", s) for s in seasons] + [("ARGC", s2) for s2 in ARGS_FOR(d)]
    else:
        lgs = [("FR1", eu(d)), ("FR2", eu(d))]
    for lg, s in lgs:
        t = RANKS.get((lg, s), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

def ARGS_FOR(d):
    y = int(d[:4]); m = int(d[5:7])
    s = y if m >= 7 else y - 1
    return [f"{s}-{str(s + 1)[2:]}"] + ([f"{y - 1}-{str(y)[2:]}"] if True else [])

exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read()) if os.path.exists(os.path.join(HERE, "man_elo.py")) else None

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
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    sys.exit(0)
exec(open(os.path.join(HERE, "judge_tail.py"), encoding="utf-8").read())
