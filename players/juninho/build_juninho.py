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
# 2011.10.26 아우로라전: TM 출전 79분이나 같은 리포트의 83분 도움(FotMob 82분)과 맞지 않음(교체 시각 'Not reported') → 마지막 기록 분인 83분으로
MIN_FIX = {"1158050": 83}
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

# 골 순서 고침(리포트 시계 판독 오류로 보이는 경우, FotMob 순서를 따름): 2011.10.26 수다메리카나 16강 2차전 아우로라전
# TM은 78분 베르나르두 6-1 → 79분 디오메지 페냐 PK 6-2, FotMob은 72분 디오메지 페냐 PK(5-2) → 78분 베르나르두(6-2). 78분 도움의 골 전 스코어를 5-2로.
BEFORE_FIX = {("1158050", "78"): (5, 2)}
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
              "Santos": "Santos FC", "Flamengo-RJ": "CR Flamengo", "Portuguesa (SP)": "Portuguesa", "Flamengo": "CR Flamengo", "Botafogo-RJ": "Botafogo de Futebol e Regatas", "Portuguesa": "Portuguesa",
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
        return half_up(1583 + 63 * curve(r, n)), f"아르헨티나 1부 {season} {r}위/{n}팀 (추정, 가까운 반시즌 순위표)"
    if lg == "FR1":
        m = ents_map("리그1", season)
        v, it = mid(m, r)
        if v is None:
            v = edge(m, r, n, LL_SD); INTERP_USED.add((season, r, v, "끝"))
            return v, f"리그1 {season} {r}위 (추정, 이웃 순위값에 순위 곡선 차이)"
        if it: INTERP_USED.add((season, r, v))
        return v, f"리그1 {season} {r}위"
    if lg == "MLS1":
        m = ents_map("MLS", season); v, it = mid(m, r)
        if v is None: return None
        return v, f"MLS {season} {r}위"
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
        lgs = [("FR1", eu(d)), ("FR2", eu(d))] if cid != "MLS1" else [("MLS1", y)]
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


# 직접 추정(모두 lv에 '추정') — judgments.md 6절
c3 = half_up((1311 + 1150) / 2)
man("CA Peñarol", "1997", 1600, "우루과이 1부 상위 팀 (추정, 다른 선수 자료 페냐롤 2011 우승 팀 1600과 같음)")
man("CA Peñarol", "1999", 1600, "우루과이 1부 상위 팀 (추정, 다른 선수 자료 페냐롤 2011 우승 팀 1600과 같음)")
man("Barcelona SC Guayaquil", "1998", 1480, "에콰도르 1부 상위 팀, 1998 리베르타도레스 결승 진출 (추정, 다른 선수 자료 에콰도르 우승 팀 1480과 같음)")
man("South Melbourne FC", "1999-00", 1400, "호주 NSL 1999-00 우승 팀 (추정, 다른 선수 자료 호주 A리그 1~3위권 1406·1450 아래 수준)")
man("RSC Anderlecht", "2003-04", 1640, "벨기에 1부 2003-04 1위 (추정, 다른 선수 자료 안더레흐트 2005-06·2013-14 1위권 1640과 같음)")
man("Celtic FC", "2003-04", 1620, "스코틀랜드 2003-04 1위 (추정, 다른 선수 자료 셀틱 2001-02·2011-12 1위 1620과 같음)")
man("PSV Eindhoven", "2005-06", 1837, "에레디비시 2005-06 1위")
man("FC Bourg-Péronnas", "2003-04", 1311, "프랑스 3부 2003-04 (추정, 다른 선수 자료 프랑스 3부 약 1311과 같음)")
man("OS Aire Football", "2003-04", 1150, "프랑스 하부 아마추어 (추정, 다른 선수 자료 프랑스 하부 아마추어 1150과 같음)")
man("ES Viry-Châtillon", "2004-05", 1150, "프랑스 하부 아마추어 (추정, 다른 선수 자료 프랑스 하부 아마추어 1150과 같음)")
man("SC Bastia", "2005-06", 1540, "프랑스 2부 2005-06 (추정, 2부 평균 1540; 순위 확인 못 함)")
man("Aviron Bayonnais", "2006-07", c3, "프랑스 4부(CFA) 2006-07 (추정, 3부 약 1311과 하부 아마추어 1150의 가운데)")
man("CS Sedan-Ardennes", "2007-08", half_up(1540 + SD2 * curve(4, 20)), "프랑스 2부 2007-08 4위 (추정, 2부 평균 1540 + 2부 흩어짐 × 순위 곡선; 순위는 검색 요약 기준)")
man("Al-Jazira Club", "2010", 1450, "UAE 1부 상위 팀 2009-10 (추정, 다른 선수 자료 알자지라 2017-18 UAE 1위 1450과 같음; 순위 확인 못 함)")
man("Club Aurora", "2011", 1350, "볼리비아 1부 중위권 (추정, 다른 선수 자료 볼리비아 중위권 레알 포토시 1350과 같음)")
man("Universitario de Deportes", "2011", 1400, "페루 1부 상위 팀 (추정, 다른 선수 자료 페루 상위 팀 1400과 같음)")
man("Club Alianza Lima", "2012", 1400, "페루 1부 상위 팀 (추정, 다른 선수 자료 페루 상위 팀 1400과 같음)")
man("Club Libertad Asunción", "2012", 1500, "파라과이 1부 상위 팀 (추정, 다른 선수 자료 파라과이 상위 팀 1500과 같음)")
man("Club Nacional", "2012", 1600, "우루과이 1부 우승 팀 2011-12 (추정, 다른 선수 자료 우루과이 상위 팀 1600과 같음)")
man("Duque de Caxias FC (RJ)", "2012", 1253, "브라질 세리에 C 2012 (추정, 세리에 C 참가 팀; 다른 선수 자료 세리에 C 1253과 같음)")
man("Macaé Esporte Futebol Clube (RJ)", "2012", 1253, "브라질 세리에 C 2012 (추정, 세리에 C 참가 팀; 다른 선수 자료 세리에 C 1253과 같음)")
man("Madureira EC", "2012", 1253, "브라질 세리에 C 2012 (추정, 세리에 C 참가 팀; 다른 선수 자료 세리에 C 1253과 같음)")
man("Friburguense AC", "2012", 1200, "브라질 세리에 D 2012 (추정, 4부 이하; 다른 선수 자료 1200과 같음)")

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
if __name__ == "__main__" and "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print("score mismatches", SCORE_MISMATCH)
    print([ (r[9],r[1],r[4],r[10],r[11]) for r in E if r[4]>90])
    print(len(E), sum(r[0]=="g" for r in E), sum(r[0]=="a" for r in E))
    print(collections.Counter(j[0]+"/"+str(j[-1]) for j in judg))
    sys.exit(0)
# ---------------------------------------------------------------- FotMob 골 대조(2011~13)
FM_CMP = []
TMG = collections.defaultdict(list)
for r in E:
    pass
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["jp_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "penalty" in (f["goalDescriptionKey"] or "").lower() or "pen" in (f["suffix"] or "").lower()
        a = mins(t["minute"])[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
        if tp != fp or abs(a - b) > 1: FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["goalDescriptionKey"]))
FM_N = sum(1 for gid in EVS if gid in G and gid in FME and any(e["scorer_id"] == ME for e in EVS[gid]))

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
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.match(r"^Juninho( Pernambucano)?$", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(주니뉴 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1]) or True)]
            # 같은 날·같은 분의 타인 골이 있으면, 같은 상대 팀 경기인지 확인
            hit = [x for x in hit if key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])]
            if hit: CROSS.append(("주니뉴 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
# 타인 골에 TM이 주니뉴 도움으로 적었으나 규칙으로 뺀 것 / 동료 도움이 주니뉴 골에 있는데 상대 파일에 없는 것
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and (key(x[1]) == key(j[2]) or toks(x[1]) & toks(j[2])):
                    CROSS.append(("TM 주니뉴 도움을 규칙대로 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("sprju", "1995-01-01", "스포르트 헤시피", "1993~1994"), ("vasju", "2001-07-01", "바스쿠 다 가마", "1995~2001"),
         ("lyoju", "2009-07-01", "리옹", "2001~2009"), ("gharju", "2011-05-05", "알가라파", "2009~2011"),
         ("vasju", "2013-01-01", "바스쿠 다 가마", "2011~2012"), ("nyju", "2013-07-11", "뉴욕 레드불스", "2013"),
         ("vasju", None, "바스쿠 다 가마", "2013")]
TM_CLUB = {"8718": "sprju", "978": "vasju", "1041": "lyoju", "6297": "gharju", "623": "nyju"}
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
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in ("sprju", "vasju", "nyju"): return str(y)
    if club == "lyoju": s = y if d[5:] >= "07-10" else y - 1
    else: s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    print(FM_N, FM_CMP)
    for c in CROSS: print(c)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
SRC = ELO_SRC
first, last = M[0], M[-1]
NOTE_LINES = [
    f"주니뉴 페르남부카누(스포르트 헤시피·바스쿠 다 가마·리옹·알가라파·뉴욕 레드불스)의 클럽 공식 경기 {NG}경기({d_(first[0])} 플루미넨시전 ~ {d_(last[0])} 산투스전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·브라질 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CN[k]} {c3(v)}" for k, v in ST.items()) + f"(바스쿠는 세 시기 합계). 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있거나 리그 밖 대회인 모든 경기, 리포트 골 155개·도움 137개가 선수 경기 성적과 경기마다 같음). FotMob은 2011~2013 바스쿠·뉴욕 경기 34경기만 있어 골 16개를 대조함(스코어·PK 같음, 분은 2012.6.6 바이아전 63분·2012.9.29 피게이렌시전 80분 골만 FotMob이 2분 빠름 → Transfermarkt 분 유지). 2001~2010 리옹 경기에는 두 번째 출처가 없음",
    "넣지 못한 경기(경기별 날짜·출전·골 시각 자료를 찾지 못함): Transfermarkt에 없는 경기는 넣지 않음. 영어 위키백과와 비교하면 바스쿠 1995~2001 약 102경기 19골(1996~2000 캄페오나투 카리오카·타사 과나바라·타사 히우, 토르네이우 히우-상파울루, 타사 시다지 마라빌랴 등 주 리그·지역 대회), 스포르트 헤시피 3경기 2골(1994 페르남부쿠 주 선수권·코파 두 노르데스치 등), 알가라파 55경기 22골(카타르 스타스리그 40경기 15골, 에미르컵·왕세자컵·셰이크 자심컵 등 컵 15경기 7골; Transfermarkt는 AFC 챔피언스리그 11경기만 있음)이 빠져 있어 이 기간 기록은 실제보다 적음. 위키백과 클럽별 기록은 리옹 343경기 100골, 바스쿠 2011~2012 75경기 18골·2013 22경기 2골, 뉴욕 15경기 0골과 같음",
    f"도움: 2014년 8월 이전 도움은 Transfermarkt 경기 리포트 단일 출처(클로제·인시녜·라울 선례, 선수 경력이 모두 그 이전). Transfermarkt 도움 137개에서 상대 자책골에 준 도움 4개(2008.9.30 바이에른전 25분 데미칠리스, 2008.10.18 릴전 22분 셰주, 2012.8.25 플루미넨시전 73분 겅, 2013.8.18 그레미우전 25분 알렉스 텔리스), 슈팅 리바운드('Shot on goal') 1개(2001.10.23 바르셀로나전 66분 루이룅댕), PK 유도 1개(2011.11.10 우니베르시타리오전 23분 디에구 소자 PK)를 빼 {NA}개. 도움 유형 칸이 빈 {UNTYPED}개는 일반 도움으로 셈. 본인 PK 골에 본인을 도움으로 적은 표기는 없음. 프랑스어 위키백과의 시즌별 도움 합계(통산 약 140)와 FotMob 경력 합계는 Transfermarkt와 시즌마다 크게 달라 쓰지 않음",
    f"골: 자책골 없음. PK 골 {NPK}개는 Transfermarkt 골 유형 'Penalty'(선수 경기 성적 PK 골 수와 같음). 2004.10.3 생테티엔전 87분 골은 PK가 막힌 뒤 리바운드라 PK가 아님. 2004.1.24 쿠프 드 프랑스 부르페로나전은 리포트에 골이 4개(5-0 중 하나 빠짐)뿐이라 57분 골의 골 전 스코어는 전반 0-1(하프타임 스코어) 기준 1-0으로 씀. 2011.10.26 수다메리카나 16강 2차전 아우로라전은 Transfermarkt가 78분 베르나르두 골(6-1)과 79분 디오메지 페냐 PK(6-2) 순서를 FotMob(72분 PK 5-2, 78분 6-2)과 다르게 적어, 78분 베르나르두 골에 준 도움의 골 전 스코어는 FotMob 순서(5-2)로 씀",
    "출전 분: Transfermarkt 그대로(2011.10.26 아우로라전만 Transfermarkt 79분이 같은 리포트의 83분 도움과 맞지 않아 83분으로 고침). 출전 분이 비어 있는 4경기(1996.8.14 스포르트전·1998.10.21 아틀레치쿠 파라나엔시전은 선발 표시, 2000.11.5 인테르나시오나우전·2000.11.12 보타포구전은 교체 정보 없음)는 90분으로 추정함. 연장·승부차기 120분: 1996.11.13 코파 코네북 준결승 2차전, 2001.12.1·2003.1.18 쿠프 드 라 리그, 2004.7.31 트로페 데 샹피옹, 2005.3.1 쿠프 드 프랑스 16강, 2005.4.13 챔스 8강 2차전 PSV전, 2006.2.1 쿠프 드 프랑스 아작시오전, 2008.5.24 쿠프 드 프랑스 결승 PSG전(117분), 2012.5.9 리베르타도레스 16강 2차전 라누스전. 2000.1.14 클럽 월드 챔피언십 결승은 연장 없이 승부차기(Transfermarkt 96분)",
    "날짜: 리옹·알가라파는 Transfermarkt 날짜(현지). 스포르트·바스쿠·뉴욕 경기는 Transfermarkt 리포트 날짜가 중부 유럽 기준이라 경기 시각(UTC)을 현지 시간대로 바꾼 날짜를 씀(1993~2004 브라질 경기는 시각 자료가 없어 일정 날짜 그대로)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(벤제마 등), 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 순위값·리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['기존 팀×시즌 값']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "브라질 세리에 A는 달력 연도 순위로 평균 1598 모형(네이마르·호나우두·루카스 모우라 자료와 같은 방식), 2000년은 코파 주앙 아벨란제 블루 모듈 25팀 1단계 순위(RSSSF)를 25팀 곡선에 넣음(Transfermarkt 표는 1위가 크루제이루로 나와 믿기 어려움; 기존 선수 자료에 있는 같은 팀·시즌 값이 있으면 그대로 씀). 2001.1.18 코파 주앙 아벨란제 결승 단계 경기는 2000 대회 값. 아르헨티나 1부는 Transfermarkt 반시즌(아페르투라·클라우수라) 순위표를 평균 1583·흩어짐 63 모형에 넣은 값이며 경기 시기와 반시즌이 정확히 맞지 않아 '추정'으로 표시(리버 플레이트 1998.7·2000.11, 산 로렌소 2000.9, 라누스 2012.5). 리옹 시기 리그1·프랑스 2부는 기존 순위값에 순위를 넣고 빈 순위는 앞뒤 값의 가운데, 끝 순위는 가장 가까운 값에 순위 곡선 차이를 더한 추정. MLS 2013은 기존 순위값(LA 갤럭시 5위는 4위 1627·7위 1600 사이)",
    "직접 추정(모두 '추정', 순위를 확인하지 못한 것은 그렇게 적음): " + ", ".join(f"{o} {e}" for o, e, lv in MAN_USED) + " — 모두 다른 선수 자료의 같은 리그 비슷한 수준 값에 맞춤. 브라질 카리오카 2012 상대는 세리에 C 참가 팀(두키지카시아스·마카에·마두레이라) 1253, 세리에 D(프리부르겐시) 1200(네이마르 선례, 참가 팀은 검색 요약 기준). 프랑스 컵 하부 팀: 부르페로나(3부 내셔널) 1311, 4부 바이욘 1231(3부와 하부 아마추어의 가운데), OS 에르·비리샤티옹 1150, 바스티아 2005-06 2부 1540(순위 확인 못 함), 스당 2007-08 2부 4위 1582(순위는 검색 요약)",
    "대회 비중: 브라질 코파 두 브라질·쿠프 드 프랑스·쿠프 드 라 리그·US 오픈컵은 국내컵(16강까지·8강·준결승·결승), 트로페 데 샹피옹·코파 인터아메리카나는 국내컵 결승 비중, 캄페오나투 카리오카(2012 조별·타사 히우·결승·2000 결승)는 국내컵 하위 비중으로 조별은 리그식·결정전과 결승은 토너먼트(네이마르 파울리스타 선례). 인터콘티넨털컵 1998·클럽 월드 챔피언십 2000은 클럽 월드컵 비중(챔피언십 조별은 리그식, 결승은 단판). 코파 코네북·수페르코파 수다메리카나·코파 메르코수르·수다메리카나는 남미 2부 대회 비중(호나우두 수페르코파 선례를 따라 코네북·수페르코파·메르코수르도 이 비중으로 둔 판단), 리베르타도레스는 조별·16강 / 8강 / 준결승 / 결승. UEFA컵 3라운드·16강은 유로파 토너먼트. AFC 챔피언스리그는 AFC 챔스",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회 2020-21까지 원정 다득점·연장, 리베르타도레스(결승 제외)·메르코수르·수다메리카나·코파 두 브라질은 원정 다득점 있고 연장 없이 승부차기(네이마르·호나우두 선례, 1998~2000년 규정은 문서로 확인하지 못한 추정), 리베르타도레스 결승은 원정 다득점 없이 연장, 코파 코네북·카리오카 결승은 원정 다득점·연장 없이 승부차기, AFC 챔피언스리그는 원정 다득점 없음. 못 뛴 1차전 스코어는 Transfermarkt 리포트로 채움",
    "시즌 구분: 리옹은 7월 10일 기준(2001.7.28 리그1 개막전·7월 트로페 데 샹피옹은 새 시즌, 벤제마·라카제트 리옹과 같음), 스포르트·바스쿠·뉴욕은 달력 연도, 알가라파는 8월 1일 기준. 클럽 구분: 1995.1.1 전 스포르트, 2001.7.1 전 바스쿠, 2009.7.1 전 리옹, 2011.5.5 전 알가라파, 2013.1.1 전 바스쿠, 2013.7.11 전 뉴욕, 이후 바스쿠(Transfermarkt 이적 기록 기준, 경기 클럽과 경계 불일치 0)",
    "같은 경기 동료 자료: 벤제마(리옹 2005~2009)와 주고받은 골·도움(주니뉴 도움→벤제마 골 7, 벤제마 도움→주니뉴 골 3)은 날짜·분·골 전 스코어·대회·상대 Elo·수준 설명이 모두 같음. 2013.5.19 LA 갤럭시전 도움(팀 카힐 90+1분)의 상대는 이 계산기에 없음. 말루다 등 병렬 판정 선수는 대조하지 않음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 리그1 7회(2001-02~2007-08), 쿠프 드 프랑스 2007-08, 트로페 데 샹피옹 3회(2002·2003·2004; 페이지에는 2004-05가 두 번 적힘), 브라질 리그 1997·2000, 리베르타도레스 1998, 코파 메르코수르 2000, 카리오카 1998, 타사 히우 1998·1999, 카타르 리그 2009-10, 스타스컵 2008-09, MLS 서포터스 실드 2013. 인터콘티넨털컵 1998 준우승. 개인: 리그1 올해의 선수 2005-06, 카타르 올해의 선수 2010. 대표팀(컨페더레이션스컵 2005)은 뺌",
    "은퇴: 2014.1.29 은퇴(Transfermarkt), 마지막 클럽 경기 2013.11.10 바스쿠(브라질 세리에 A)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elk", "elq", "cwc", "MAN", "csa", "lib"]:
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
    allr = sorted(rs, key=lambda r: r[4])
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const JUN_E={J(E)};\nconst JUN_M={J(M)};\nconst JUN_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
