#!/usr/bin/env python3
"""히바우두 (Transfermarkt 3372): raw/ -> rivaldo.json + src/data/riv.js (판정 근거는 judgments.md)

  python3 players/rivaldo/build_rivaldo.py            # 파일 쓰기
  python3 players/rivaldo/build_rivaldo.py --debug    # Elo 출처 로그만 출력
  python3 players/rivaldo/build_rivaldo.py --stat     # 요약·동료 대조
  python3 players/rivaldo/build_rivaldo.py --ties     # 합산 행

입력: raw/tm_games.csv(출전·분·날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv(2011~2015 골 대조), raw/ranks.txt(Transfermarkt 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
순위표 보충(코드 안 표): 브라질 세리에 A 1993(포르투갈어 위키백과, 호나우두 자료와 같은 표)·1994·1995(영어 위키백과 최종 순위).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "riv.js")
OUT_JSON = os.path.join(HERE, "rivaldo.json")
ME = "3372"
ME_KO = "히바우두"

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

# ---------------------------------------------------------------- 날짜
# 기본: date_local(Transfermarkt 리포트 날짜, 없으면 일정 날짜 = 경기 현지 날짜; API UTC 날짜가 하루 이른 183경기는 이 값으로 바로잡힘).
# 브라질 클럽 2011~2015(상파울루·상카에타누·모지 미링): Transfermarkt 일정 날짜가 브라질 저녁 경기에서 하루 늦은 23경기 →
#   API UTC 시각을 브라질 시간으로 바꾼 날짜(FotMob 경기 시각이 있는 14경기는 FotMob과 같음). 1993~1995·2004 브라질 경기는
#   API 시각이 자리채움 값이라 일정 날짜를 씀.
BR_LATE = {"585", "291", "1784"}
def ldate(g):
    if g["club_id"] in BR_LATE and g["date_local_brazil_from_api_utc"]:
        return g["date_local_brazil_from_api_utc"]
    return g["date_local"]
DATE_FIXED = [(g["gameId"], g["date_local"], ldate(g)) for g in GAMES if ldate(g) != g["date_local"]]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 판정 표
EXCL_GOAL_OG = "1091631"   # 2001.3.11 마요르카전 51분: 히바우두 자책골(상대 득점) — 골 아님
GAP = "2014-08-01"         # 이 전 도움은 Transfermarkt 단일 출처 허용(그 뒤 경기: 모지 미링 2015 4경기, 도움 0)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES1", "IT1", "GR1", "POGR", "UZ1", "BRA1", "BRA2", "BRA3"}   # 그리스 2007-08 플레이오프 = 리그(발부에나·벨기에 플레이오프 선례), 세리에 C 2014 조별 = 리그
STATE = {"BCP1", "BCPF"}   # 캄페오나투 파울리스타: 국내컵 하위 비중(네이마르·호나우두 선례), 조별 리그식·토너먼트 단판

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid in ("CDR", "BRC", "CIT", "GRP", "KOBU"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SUC", "USC"): return "df"          # 수페르코파·UEFA 슈퍼컵 = 국내컵 결승
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"    # 1999-2003 2차 조별(Group A~D·1~4) 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEQ": return "elq"                 # UEFA컵 예선
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                              # 3라운드·16강·8강, 2004-05 32강('intermediate stage')
    if cid == "AFCL":
        if r.startswith("quarter"): return "aclk"
        if r.startswith("semi"): return "aclsf"
        if r.startswith("final"): return "aclf"
        return "acl"
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
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "CLQ", "UEFA", "UEQ", "USC"): return (1, 1)   # UEFA 대회 2020-21까지
    if cid in ("CDR", "SUC"): return (1, 1)       # 코파 델 레이·수페르코파(2018-19까지)
    if cid == "CIT": return (1, 1)                # 코파 이탈리아(2021-22까지) — 셰브첸코·인자기 자료 2003 결승과 같음
    if cid == "GRP": return (1, 1)                # 그리스컵 2004-05·2005-06 두 경기 라운드: 원정 다득점·연장(추정, 발부에나 2019~23 확인값과 같은 방식)
    if cid == "KOBU": return (1, 1)               # 우즈베키스탄컵 2009·2010 준결승: 원정 다득점·연장(추정, 셰브첸코 우크라이나컵 선례)
    if cid == "BCPF": return (0, 1)               # 파울리스타 1995 결승: 원정 다득점 없음(중립·같은 도시), 2차전 연장(Transfermarkt 연장 경기)
    if cid == "BRC": return (0, 0)                # 코파 두 브라질 2009~13: 원정 다득점·연장 없음(네이마르 선례)
    if cid == "CLI": return (1, 0)                # 리베르타도레스 1995(주니뉴 1998~2000 선례와 같은 추정)
    if cid == "CS": return (1, 0)                 # 수다메리카나 2011(주니뉴·네이마르 선례)
    if cid == "AFCL": return (0, 1)               # AFC 대회 원정 다득점 없음(3절)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    # 클럽 id가 바뀐 경우(쿠루브치 → 분요드코르): 홈/원정 표시로
    return "h" if g["venue"] == "H" else "a"

def other_leg(gid):
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G and G[oid]["gameState"] != "penalty_shootout":
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    # other_leg_score는 다른 차전의 (홈:원정) — 그 경기의 홈은 이 경기의 원정
    return (oa, oh) if s == "h" else (oh, oa)

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
        cnt[sd] += 1           # 리포트 골 순서대로 득점 팀별로 셈(자책골은 득점 팀 기준 표시)
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("골 아님(본인 자책골, 상대 득점)", ldate(g), opp(g), e["minute"], e["goal_desc"])); continue
        is_g = e["scorer_id"] == ME
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
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

# 리포트 골·도움 = API 경기별 합계 점검
cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
API_A = sum(int(g["assists"] or 0) for g in GAMES)
REP_A_ALL = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)

# 리포트 골 수 = 최종 스코어 점검(승부차기 제외)
SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI.get(gid, {}).get("final") else (h, a)
    if (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))

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
MANUAL_ALIAS = {"inter milan": "inter", "lokomotiv moskau": "lokomotiv moscow", "olympique lyon": "olympique lyonnais",
                "pfc kuruvchi tashkent": "bunyodkor tashkent", "fc agmk olmaliq": "fc olmaliq",
                "samarqand dinamo samarqand": "dinamo samarqand", "clube do remo": "clube do remo pa",
                "coritiba fc": "coritiba foot ball club", "goias esporte clube": "goias ec", "criciuma esporte clube": "criciuma ec",
                "associacao portuguesa de desportos": "portuguesa", "paysandu sport club": "paysandu sc", "ec vitoria": "esporte clube vitoria",
                "santa cruz fc": "santa cruz fc pe", "fc sochaux montbeliard": "fc sochaux", "rcd espanyol barcelona": "rcd espanyol"}
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
    if b in ("hon.js", "riv.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "milan", "inter", "madrid", "moscow", "moskau", "paulista", "paulo", "ca", "cs", "club", "deportivo", "deportes", "universidad", "san", "santa",
        "athens", "piraeus", "thessaloniki", "tashkent", "barcelona", "coruna"}
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

# 브라질 세리에 A 1993(32팀, 조별 방식) 최종 순위: 포르투갈어 위키백과 'Campeonato Brasileiro de Futebol de 1993 - Série A'
#   'Classificação geral' — 호나우두 자료(build_ronaldonazario.py)와 같은 표. Transfermarkt 1993 표는 받지 못함.
BRA1993 = {"Sport Club Corinthians Paulista": 3, "Esporte Clube Bahia": 30, "CR Flamengo": 7, "Botafogo de Futebol e Regatas": 31,
           "CA Bragantino": 19, "Sport Club Internacional": 17, "Sociedade Esportiva Palmeiras": 1, "Santos FC": 5,
           "São Paulo Futebol Clube": 4, "Grêmio Foot-Ball Porto Alegrense": 13, "Clube de Regatas Vasco da Gama": 20,
           "Fluminense Football Club": 28, "Clube Atlético Mineiro": 32, "Guarani Futebol Clube (SP)": 6, "Paraná Clube": 10,
           "Sport Club do Recife": 25, "Goiás Esporte Clube": 26, "Criciúma Esporte Clube": 14, "Coritiba FC": 22,
           "Clube do Remo": 8, "Associação Portuguesa de Desportos": 9, "Paysandu Sport Club": 11, "União São João EC (SP)": 12,
           "América Futebol Clube (MG)": 16, "Clube Náutico Capibaribe": 18, "Ceará Sporting Club": 21, "Santa Cruz FC": 23,
           "Atlético Paranaense": 24, "Fortaleza Esporte Clube": 27, "Desportiva Ferroviária": 29, "EC Vitória": 2,
           "Cruzeiro Esporte Clube": 15}
RANKS[("BRA1", "1993")] = {key(nm): (r, 32, nm) for nm, r in BRA1993.items()}
# 브라질 세리에 A 1994·1995: Transfermarkt 표는 여러 단계 대회를 한 줄로 늘어놓은 순서라(1994 크루제이루 23위·과라니 2위 등) 공식 최종 순위와 다름
#   → 영어 위키백과 '1994/1995 Campeonato Brasileiro Série A' 'Final standings'(24팀)로 바꿈(주니뉴 2000 RSSSF 선례). 통합표에 이미 값이 있는
#   팀-시즌(보타포구·코린치안스·상파울루·그레미우·크리시우마 1994, 아틀레치쿠 미네이루·산투스·파이산두 1995 — 주니뉴 자료, Transfermarkt 순서)은
#   통합표 값을 먼저 씀(값 충돌 방지).
WIKI_BRA = {
    "1994": ["Sociedade Esportiva Palmeiras", "Sport Club Corinthians Paulista", "Guarani Futebol Clube (SP)", "Clube Atlético Mineiro",
             "Botafogo de Futebol e Regatas", "São Paulo Futebol Clube", "Esporte Clube Bahia", "CA Bragantino", "Santos FC", "Portuguesa",
             "Grêmio Foot-Ball Porto Alegrense", "Clube de Regatas Vasco da Gama", "Sport Club do Recife", "CR Flamengo",
             "Fluminense Football Club", "Paysandu SC", "Sport Club Internacional", "Paraná Clube", "Esporte Clube Vitória", "Criciúma EC",
             "União São João EC (SP)", "Cruzeiro Esporte Clube", "Clube do Remo (PA)", "Clube Náutico Capibaribe"],
    "1995": ["Botafogo de Futebol e Regatas", "Santos FC", "Cruzeiro Esporte Clube", "Fluminense Football Club", "Sociedade Esportiva Palmeiras",
             "CA Bragantino", "Clube Atlético Mineiro", "Goiás EC", "Sport Club Internacional", "Portuguesa", "Esporte Clube Juventude",
             "São Paulo Futebol Clube", "Paraná Clube", "Sport Club Corinthians Paulista", "Grêmio Foot-Ball Porto Alegrense", "Criciúma EC",
             "Esporte Clube Bahia", "Guarani Futebol Clube (SP)", "Sport Club do Recife", "Clube de Regatas Vasco da Gama", "CR Flamengo",
             "Esporte Clube Vitória", "Paysandu SC", "União São João EC (SP)"]}
for y, lst in WIKI_BRA.items():
    tm = RANKS[("BRA1", y)]
    if {key(n) for n in lst} != set(tm): sys.exit("브라질 %s 위키 표 이름 불일치 %s" % (y, {key(n) for n in lst} ^ set(tm)))
    RANKS[("BRA1", y)] = {key(n): (i + 1, 24, n) for i, n in enumerate(lst)}
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

# 라리가 1994-95~1998-99: 라울·지단·호나우두 자료와 같은 모형(평균 1712.7+13.5, 흩어짐 100.16 × 순위 곡선, 리그 수준 추정)
LL_OLD_MEAN = 1712.7 + 13.5
LL_SD = 100.16
# 세리에A 18팀 시즌(2003-04까지): 기존 자료 순위값 + 빈 순위 7·9·12·16위 = 1762·1728·1697·1645(토티·델 피에로 통일값)
SA18_FILL = {7: 1762, 9: 1728, 12: 1697, 16: 1645}
# 그리스 슈퍼리그: 발부에나 자료와 같은 국가 계수 회귀(1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 흩어짐 119)
#   + 그리스 보정 GR_K(발부에나 자료 기준점: 올림피아코스 2019-20 1위 1680·2020-21 1위 1690, PAOK 2021-22 2위 1590).
#   계수(kassiesa.net 국가 순위표 2006·2008·2010·2011): 2003-04 4.166, 2004-05 6.166, 2005-06 3.333, 2006-07 4.666, 2007-08 7.500, 2008-09 6.500
def reg_mean(coefs): return 1473 + 23.33 * (sum(coefs) / len(coefs) - 7.3333)
GR_COEF_V = {2018: 5.1, 2019: 4.9, 2020: 5.1, 2021: 8.0, 2022: 2.125, 2023: 11.4, 2024: 12.688}
def _gr_reg_v(start):
    ys = (start - 1, start, start + 1) if start + 1 in GR_COEF_V else (start - 2, start - 1, start)
    return reg_mean([GR_COEF_V[y] for y in ys])
GR_K = sum(v - (_gr_reg_v(y) + 119 * curve(r, 14)) for y, r, v in [(2019, 1, 1680), (2020, 1, 1690), (2021, 2, 1590)]) / 3
GR_COEF = {2003: 4.166, 2004: 6.166, 2005: 3.333, 2006: 4.666, 2007: 7.500, 2008: 6.500}
def gr_mean(season):
    s = int(season[:4]); return reg_mean([GR_COEF[s - 1], GR_COEF[s], GR_COEF[s + 1]]) + GR_K
# 우즈베키스탄 1부(새 리그 수준, 추정): 기존 자료 파크타코르 2017 1위 1380·나사프 2025-26 3위 1360에 맞춘 순위당 10점 직선(1위 1380)
def uz(r): return 1380 - 10 * (r - 1)

SEG = [1753, 1712, 1687, 1674, 1660, 1654, 1647, 1640, 1632, 1623, 1615, 1610, 1606, 1601, 1598, 1595, 1589, 1580, 1572, 1567, 1560, 1553]
BL_OLD = {}
for e in ENTS:
    m = re.match(r"^분데스리가 (199\d|200[0-3])-\d\d (\d+)위$", e[12] or "")
    if m: BL_OLD.setdefault(int(m.group(2)), collections.Counter())[e[2]] += 1
BL_OLD = {r: c.most_common(1)[0][0] for r, c in BL_OLD.items()}

INTERP_USED = set()
def rank_model(lg, season, r, n):
    if lg == "BRA1":
        return half_up(1598 + 63 * curve(r, n)), f"브라질 세리에 A {season} {r}위"
    if lg == "BRA2":
        return half_up(1370 + SD2 * curve(r, n)), f"브라질 세리에 B {season} {r}위"
    if lg == "ES1":
        m = ents_map("라리가", season)
        if int(season[:4]) <= 1998:
            if r in m: return m[r], f"라리가 {season} {r}위"
            return half_up(LL_OLD_MEAN + LL_SD * curve(r, n)), f"라리가 {season} {r}위 (리그 수준 추정)"
        v, it = mid(m, r)
        if v is None:
            v = edge(m, r, n, LL_SD); INTERP_USED.add(("ES1", season, r, v, "끝"))
            return v, f"라리가 {season} {r}위 (추정, 이웃 순위값에 순위 곡선 차이)"
        if it: INTERP_USED.add(("ES1", season, r, v))
        return v, f"라리가 {season} {r}위"
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        if n == 18 and r in SA18_FILL: INTERP_USED.add(("IT1", season, r, SA18_FILL[r])); return SA18_FILL[r], f"세리에A {season} {r}위"
        v, it = mid(m, r)
        if v is None: return None
        INTERP_USED.add(("IT1", season, r, v)); return v, f"세리에A {season} {r}위"
    if lg == "L1":     # 분데스리가 2003-04 이전: 기존 자료 고정 순위값(라울 자료와 같은 방식)
        v, it = mid(BL_OLD, r)
        return (v, f"분데스리가 {season} {r}위") if v else None
    if lg == "ES2":    # 세군다 22팀: 기존 고정값(라울 자료)
        if n == 22: return SEG[r - 1], f"세군다(2부) {season} {r}위"
        return half_up(1624 + SD2 * curve(r, n)), f"세군다(2부) {season} {r}위"
    if lg == "GR1":
        if int(season[:4]) - 1 not in GR_COEF or int(season[:4]) + 1 not in GR_COEF: return None
        return half_up(gr_mean(season) + 119 * curve(r, n)), f"그리스 슈퍼리그 {season} {r}위 (리그 수준 추정)"
    if lg == "UZ1":
        return uz(r), f"우즈베키스탄 1부 {season} {r}위 (리그 수준 추정)"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
SOUTH = {"BRA1", "BRA2", "BRA3", "BCP1", "BCPF", "BRC", "CLI", "CS"}
LG_FOR = {"ES1": ["ES1"], "CDR": ["ES1"], "SUC": ["ES1"], "IT1": ["IT1"], "CIT": ["IT1"], "GR1": ["GR1"], "POGR": ["GR1"], "GRP": ["GR1"],
          "UZ1": ["UZ1"], "KOBU": ["UZ1"]}

# 순위표·기존 자료에 없는 상대(직접 추정, 모두 lv에 '추정') — judgments.md 6절
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
    if cid in SOUTH or cid in ("UZ1", "KOBU", "AFCL"):
        seasons = [y]
    elif cid in ("CL", "CLQ", "UEFA", "UEQ", "USC"):
        # 연도 시즌 리그 상대(노르웨이·러시아 등): 7월 이후 경기는 그해, 1~6월 경기는 전해 시즌(통합표 키)
        seasons = [eu(d), y if int(d[5:7]) >= 7 else str(int(y) - 1)]
    else:
        seasons = [eu(d)]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    if cid in SOUTH:
        lgs = [("BRA1", y), ("BRA2", y)]
    elif cid in LG_FOR:
        lgs = [(lg, s) for lg in LG_FOR[cid] for s in seasons]
    else:
        lgs = [(lg, s) for lg in ("ES1", "IT1", "GR1", "L1") for s in seasons]
    if cid == "CDR": lgs += [("ES2", s) for s in seasons]
    for lg, s in lgs:
        t = RANKS.get((lg, s), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

# 직접 추정(모두 lv에 '추정') — judgments.md 6절. 기준은 통합표의 같은 나라·같은 수준 값.
man("CS Emelec", "1995", 1450, "에콰도르 1부 상위 팀 (추정, 다른 선수 자료 에멜레크 2012·2018 1450과 같음)")
man("CD El Nacional", "1995", 1450, "에콰도르 1부 상위 팀 (추정, 다른 선수 자료 에콰도르 상위 팀 에멜레크 1450과 같음)")
man("Bolívar La Paz", "1995", 1400, "볼리비아 1부 상위 팀 (추정, 다른 선수 자료 볼리비아 상위 팀 1400과 같음)")
man("Mogi Mirim EC", "1995", half_up(1370 + SD2 * curve(3, 24)), "브라질 세리에 B 1995 3위 (포르투갈어 위키백과 최종 순위)")
man("Polideportivo Almería", "1999-00", 1350, "스페인 3부(세군다 B) 1999-00 (추정, 다른 선수 자료 스페인 3부 1350과 같음)")
man("Gimnástica de Torrelavega", "2000-01", 1350, "스페인 3부(세군다 B) 2000-01 (추정, 다른 선수 자료 스페인 3부 1350과 같음)")
man("Club Brugge KV", "2000-01", 1620, "벨기에 2000-01 2위 (추정, 다른 선수 자료 클뤼프 브뤼허 2003-04 1위권 1620과 같음)")
man("AEK Athens", "2000-01", 1550, "그리스 2000-01 3위 (추정, 다른 선수 자료 AEK 2001-02~2006-07 1550과 같음)")
man("Wisla Kraków", "2001-02", 1500, "폴란드 2001-02 2위 (추정, 다른 선수 자료 비스와 크라쿠프 1위 1529보다 조금 낮게)")
man("Galatasaray", "2001-02", 1680, "튀르키예 2001-02 1위 (추정, 다른 선수 자료 갈라타사라이 1위 1680과 같음)")
man("Chaidari FC", "2006-07", half_up(gr_mean("2006-07") - 162), "그리스 2부(베타 에트니키) 2006-07 (추정, 그리스 1부 평균 − 162, 순위 미확인)")
man("Red Bull Salzburg", "2007-08", 1556, "오스트리아 2007-08 2위 (추정, 다른 선수 자료 오스트리아 2위 1556과 같음)")
man("Saipa FC", "2008", 1380, "이란 1부 2008-09 10위·2006-07 우승 팀 (추정, 다른 선수 자료 이란 1위 1440보다 낮게)")
man("Piroozi FC", "2009", 1420, "이란 1부 2008-09 5위 (추정, 다른 선수 자료 이란 1위 1440보다 조금 낮게)")
man("Al-Ittihad Club", "2010", 1500, "사우디 1부 2009-10 2위 (추정, 2009 AFC 챔스 준우승 팀; 같은 시기 서아시아 상위 팀 1450~1480보다 조금 높게)")
man("Al-Wahda FC", "2010", 1480, "UAE 1부 2009-10 1위 (추정, 다른 선수 자료 UAE 1위 1480과 같음)")
man("Clube Atlético Linense (SP)", "2011", 1200, "브라질 4부 이하 (추정)")

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
    print("가운데값", sorted(INTERP_USED))
    sys.exit(0)
if __name__ == "__main__" and "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print("score mismatches", SCORE_MISMATCH)
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    print(len(E), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E))
    print(collections.Counter(j[0] + "/" + str(j[-1]) for j in judg))
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2011~2015)
FM_CMP, FM_SEEN = [], 0
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["scorer"].strip() == "Rivaldo" and r["own_goal"] != "1"]
    FM_SEEN += len(fm)
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["minute"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["minute"]) + int(x["overload"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "penalty" in (f["goal_desc"], f["type"])
        a = mins(t["minute"])[0]; b = int(f["minute"]) + int(f["overload"] or 0)
        if tp != fp or a != b: FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["minute"], f["type"], f["score_after"]))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None): d.append("단판/합산 %s/%s" % (a[14] if len(a) > 14 else None, b[14] if len(b) > 14 else None))
    if a[10] != b[10]: d.append("연장")
    return d
def same_opp(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.match(r"^Rivaldo$", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(히바우두 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_opp(x[1], r[1])]
            if hit: CROSS.append(("히바우두 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g" and r[13] == 0:
            pass
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_opp(x[1], r[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_opp(mm[1], m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
# 같은 경기 득점 순서(같은 경기 타인 골·도움과 골 전 스코어가 시간순으로 맞는지)
for b, (oe, om) in OTHERS.items():
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_opp(x[1], r[1]) and x[0] == "g" and r[0] == "g" and x[4] < r[4] and (x[5], x[6]) > (r[5], r[6]):
                CROSS.append(("같은 경기 골 순서 의심", b, r[9], r[1], x[4], (x[5], x[6]), r[4], (r[5], r[6])))
# 타인 골에 Transfermarkt가 히바우두 도움으로 적었으나 규칙으로 뺀 것
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_opp(x[1], j[2]):
                    CROSS.append(("Transfermarkt 히바우두 도움을 규칙대로 뺀 타인 골", b, x[9], x[4], x[13], j[5]))
# 동료 출전 날짜 대조(같은 상대·하루 차이)
TEAMMATE_FILES = {"fig.js": ("1997-08-15", "2000-07-24"), "luc.js": ("2011-01-22", "2011-11-30"), "she.js": ("2002-07-27", "2004-01-05"),
                  "inz.js": ("2002-07-27", "2004-01-05"), "see.js": ("2002-07-27", "2004-01-05"), "kak.js": ("2003-08-01", "2004-01-05")}
import datetime as _dt
def _dd(a, b): return abs((_dt.date.fromisoformat(a) - _dt.date.fromisoformat(b)).days)
for b, (lo, hi) in TEAMMATE_FILES.items():
    if b not in OTHERS: continue
    om = OTHERS[b][1]
    for m in M:
        if not (lo <= m[0] < hi): continue
        near = [mm for mm in om if same_opp(mm[1], m[1]) and _dd(mm[0], m[0]) == 1 and mm[2] == m[2]]
        same = [mm for mm in om if same_opp(mm[1], m[1]) and mm[0] == m[0]]
        if near and not same: CROSS.append(("동료 출전 날짜 하루 차이", b, m[0], m[1], near[0][0]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("corriv", "1994-08-09", "코린치안스", "코린치안스", "1993"), ("palriv", "1996-07-08", "팔메이라스", "팔메이라스", "1994~1995"),
         ("depriv", "1997-08-15", "데포르티보 라코루냐", "데포르티보", "1996~1997"), ("fcbriv", "2002-07-27", "바르셀로나", "바르셀로나", "1997~2002"),
         ("acmriv", "2004-01-05", "AC 밀란", "밀란", "2002~2003"), ("cruriv", "2004-07-22", "크루제이루", "크루제이루", "2004"),
         ("olyriv", "2007-07-01", "올림피아코스", "올림피아코스", "2004~2007"), ("aekriv", "2008-08-28", "AEK 아테네", "AEK", "2007~2008"),
         ("bunriv", "2011-01-22", "분요드코르", "분요드코르", "2008~2010"), ("spriv", "2013-01-16", "상파울루", "상파울루", "2011"),
         ("scariv", "2013-12-01", "상카에타누", "상카에타누", "2013"), ("mogriv", None, "모지 미링", "모지 미링", "2014~2015")]
TM_CLUB = {"199": "corriv", "1023": "palriv", "897": "depriv", "131": "fcbriv", "5": "acmriv", "609": "cruriv", "683": "olyriv",
           "2441": "aekriv", "19401": "bunriv", "585": "spriv", "291": "scariv", "1784": "mogriv"}
CALENDAR = ["corriv", "palriv", "cruriv", "bunriv", "spriv", "scariv", "mogriv"]
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
CN = {k: n for k, u, n, sh, y in CLUBS}
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
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in CALENDAR: return str(y)
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    print("FotMob", FM_SEEN, FM_CMP)
    for c in CROSS: print(c)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
SHOT = "슈팅 리바운드('Shot on goal')"
def ex_list(why):
    return ", ".join(f"{d_(j[1])} {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == why)
NOTE_LINES = [
    f"히바우두(코린치안스·팔메이라스·데포르티보 라코루냐·바르셀로나·AC 밀란·크루제이루·올림피아코스·AEK 아테네·분요드코르·상파울루·상카에타누·모지 미링)의 클럽 공식 경기 {NG}경기({d_(first[0])} 크루제이루전 ~ {d_(last[0])} 루베르덴시전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·브라질 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CN[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있거나 리그 밖 대회·두 경기 합산인 모든 경기; 리포트 골 309개·도움 112개가 선수 경기 성적과 경기마다 같음). FotMob은 2011~2015 브라질 경기만 있어 히바우두 골 {FM_SEEN}개를 대조함(스코어·PK 같음, 분은 2011.8.10 세아라전 22분(FotMob 23분)·2011.9.3 피게이렌시전 60분(59분)·2011.9.17 세아라전 72분(71분)이 1분 다름 → Transfermarkt 분). 2011.9.25 보타포구전 90+2분 골은 FotMob이 90분 PK로 적었으나 Transfermarkt(호제리우 세니 프리킥 뒤 헤더)와 경기 기사(jornaldebrasilia·foxsports: 세니 프리킥을 머리로 넣은 추가시간 동점골)가 같아 PK 아닌 골·Transfermarkt 분으로 셈. 1993~2010 경기에는 두 번째 경기 단위 출처가 없음",
    "넣지 못한 경기(경기별 날짜·출전 시간·골 시각 자료를 찾지 못함): Transfermarkt에 없는 경기는 넣지 않음. 영어 위키백과 시즌 표와 비교하면 산타크루스 1991~1992 27경기 9골(포르투갈어 위키백과 40경기 36골), 모지 미링 1992 31경기 13골, 코린치안스 1993 3경기·1994 2경기 1골, 팔메이라스 1995 주 리그 등 18경기 17골·1996 34경기 22골(대부분 캄페오나투 파울리스타), 크루제이루 2004 국내 경기 7경기 2골, 카부스코르프(앙골라) 2012 21경기 11골이 빠져 있음(합계 약 143경기 75골; 스페인어 위키백과의 파울리스타(1989~1990) 52경기 27골은 영어 위키백과에 없음). 이 기간 기록은 실제보다 적음",
    "출처 간 경기 수 차이: 올림피아코스 2004-05는 Transfermarkt 38경기(그리스컵 6경기) · 영어 위키백과 34경기, 2006-07은 33·31경기, 분요드코르 2008은 16·17경기, 2009는 42·40경기 — Transfermarkt 경기 목록을 씀(골 수는 같음)",
    f"날짜: 경기 현지 날짜. 브라질 2011~2015 저녁 경기 {len(DATE_FIXED)}경기는 Transfermarkt 일정 날짜가 하루 늦어 경기 시각을 브라질 시간으로 바꾼 날짜를 씀(FotMob 경기 시각이 있는 14경기는 같은 날짜). 1993~1995·2004 브라질 경기는 Transfermarkt 일정 날짜",
    "골 판정: 2001.3.11 마요르카전 51분은 히바우두의 자책골(마요르카 득점)이라 뺌(같은 경기 74분 PK 골은 넣음). 2015.7.14 마카에전은 아들 히바우지뉴가 같은 팀에서 뛰어 이름이 겹침 — Transfermarkt 선수 번호와 FotMob 이름('Rivaldo'·'Rivaldo Junior')으로 17분 PK 골만 히바우두 골로 셈(3분·42분은 히바우지뉴). 골 직전 스코어는 리포트 골 순서로 셈. 리포트 골 목록이 빠지거나 표기가 겹친 경기(2000.1.20 오렌세전, 2001.1.16 토레라베가전, 2011.8.24 세아라전)에는 히바우두 골·도움이 없음",
    f"도움: Transfermarkt 도움 112개 중 {112 - NA}개를 뺌 — 슈팅 리바운드('Shot on goal') {EX[SHOT]}개({ex_list(SHOT)}), PK 유도 {EX['PK 유도']}개({ex_list('PK 유도')}), 상대 자책골 유도 {EX['상대 자책골 유도']}개({ex_list('상대 자책골 유도')}). 1998.2.11 메리다전 52분 본인 PK 골에 본인 도움으로 적힌 것은 도움이 아님(선수 경기 성적 도움에도 없음). 2014년 8월 전 도움은 Transfermarkt 단일 출처(그 뒤 경기는 모지 미링 2015 4경기, 도움 없음). 스페인어 위키백과 클럽별 도움(데포르티보 10·바르셀로나 53·팔메이라스 24 등)은 Transfermarkt보다 많으나 경기별 자료가 없어 쓰지 않음",
    "출전 분: Transfermarkt 출전 분 그대로(90분 추정 경기 없음). 연장 경기 6경기는 120분(교체 시각 반영), 1997.1.16 세비야전·1998.4.29 코파 델 레이 결승·2013.4.17 아라퐁가스전은 승부차기 경기",
]
SRC = ELO_SRC
NOTE_LINES += [
    f"상대 Elo: 같은 경기 다른 선수 자료 {SRC['같은 경기 다른 선수 자료']}개, 통합표의 같은 팀·같은 시즌 값 {SRC['기존 팀×시즌 값']}개, 순위표+리그 모형 {SRC['순위표+리그 모형']}개, 직접 추정 {SRC['직접 추정']}개(기록 기준)",
    "브라질 세리에 A·B는 달력 연도 순위(평균 1598·1370, 다른 브라질 선수 자료와 같은 방식). 1993은 32팀 조별 방식이라 포르투갈어 위키백과 최종 순위(호나우두 자료와 같은 표), 1994·1995는 Transfermarkt 순위표가 여러 단계 대회를 한 줄로 늘어놓은 순서라 영어 위키백과 최종 순위를 씀(통합표에 이미 값이 있는 팀은 그 값). 세아라 2011은 통합표 값(세리에 B 11위 1356)을 그대로 씀(Transfermarkt 2011 순위표에는 세리에 A 18위)",
    f"그리스 슈퍼리그 2004-05~2007-08(모두 '리그 수준 추정'): 기존 모형이 없어 발부에나 자료와 같은 국가 계수 회귀(리그 평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 흩어짐 119, 16팀 순위 곡선)에 그리스 보정 {GR_K:+.0f}점을 더함. 그리스 계수(kassiesa.net): 2003-04 4.166, 2004-05 6.166, 2005-06 3.333, 2006-07 4.666, 2007-08 7.500, 2008-09 6.500 → 리그 평균 2004-05 {gr_mean('2004-05'):.0f}, 2005-06 {gr_mean('2005-06'):.0f}, 2006-07 {gr_mean('2006-07'):.0f}, 2007-08 {gr_mean('2007-08'):.0f}. 순위는 Transfermarkt 순위표(2007-08은 플레이오프 전 정규 시즌 순위). 통합표에 값이 있는 팀(파나티나이코스 2004-05·2005-06, AEK 2006-07, 아리스·올림피아코스 2007-08)은 그 값. 그리스 2007-08 플레이오프는 리그 경기로 셈",
    "우즈베키스탄 1부 2008~2010(새 리그 수준, '리그 수준 추정'): 통합표의 파크타코르 2017 1위 1380·나사프 2025-26 3위 1360에 맞춰 1위 1380에서 순위마다 10점씩 내린 직선(16팀 최하위 1230). 순위는 Transfermarkt 순위표(연도 시즌)",
    "라리가 1996-97~1998-99는 라울·지단·호나우두 자료와 같은 리그 수준 추정 모형(통합표 값이 있으면 그 값), 1999-00 이후는 기존 순위값·빈 순위는 앞뒤 가운데(1999-00 8위 1749, 2000-01 3위 1868·7위 1777, 2001-02 10위 1714). 세리에A 2002-03은 기존 순위값, 분데스리가 1997-98 도르트문트 10위 1723(기존 고정 순위값), 세군다 1999-00 오사수나 2위 1712(기존 22팀 고정값)",
    "직접 추정(모두 '추정'): " + ", ".join(f"{o} {e}" for o, e, lv in MAN_USED) + " — 같은 나라·같은 수준의 통합표 값 기준(에콰도르 상위 1450, 볼리비아 상위 1400, 스페인 3부 1350, 그리스 2부 = 1부 평균 − 162, 이란 1위 1440보다 낮게, UAE 1위 1480, 브라질 4부 이하 1200). 모지 미링 1995는 세리에 B 3위(포르투갈어 위키백과)를 2부 모형에 넣음",
    "대회 비중: 캄페오나투 파울리스타(상파울루 주 선수권)는 리그 단계·준결승·결승 모두 국내컵 하위 라운드 비중(네이마르·호나우두 자료와 같음). 코파 델 레이·코파 이탈리아·그리스컵·우즈베키스탄컵·코파 두 브라질은 국내컵(16강까지·8강·준결승·결승), 수페르코파(스페인)·UEFA 슈퍼컵은 국내컵 결승. 챔스 2차 조별(1999-00~2002-03)은 조별, 챔스 예선 3라운드는 챔스 예선, UEFA컵 예선·1라운드는 유로파 예선, UEFA컵 2007-08 조별은 유로파 조별, UEFA컵 3라운드·16강·8강과 2004-05 32강은 유로파 토너먼트. 브라질 세리에 C 2014 조별은 리그",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점·연장: UEFA 대회·코파 델 레이·수페르코파·UEFA 슈퍼컵·코파 이탈리아(2003 결승 두 경기) 있음, 그리스컵 2004-05·2005-06과 우즈베키스탄컵 2009·2010 준결승은 있는 것으로 둠(추정), 파울리스타 1995 결승은 원정 다득점 없이 연장(2차전 연장), 리베르타도레스 1995·수다메리카나 2011은 원정 다득점 있고 연장 없음(리베르타도레스 1995는 추정), AFC 챔스는 원정 다득점 없이 연장. 못 뛴 차전 스코어는 Transfermarkt 리포트",
    "시즌 구분: 코린치안스·팔메이라스·크루제이루·분요드코르·상파울루·상카에타누·모지 미링은 달력 연도, 데포르티보·바르셀로나·밀란·올림피아코스·AEK는 8월 1일 기준. 클럽 구분(Transfermarkt 이적 기록): 1994.8.9 전 코린치안스, 1996.7.8 전 팔메이라스, 1997.8.15 전 데포르티보, 2002.7.27 전 바르셀로나, 2004.1.5 전 밀란, 2004.7.22 전 크루제이루, 2007.7.1 전 올림피아코스, 2008.8.28 전 AEK, 2011.1.22 전 분요드코르, 2013.1.16 전 상파울루, 2013.12.1 전 상카에타누, 이후 모지 미링(2015.8.17 은퇴)",
    "우승 커리어: Transfermarkt 업적 페이지 기준(챔스 2002-03, UEFA 슈퍼컵 1997-98·2003-04, 라리가 1997-98·1998-99, 코파 델 레이 1997-98, 코파 이탈리아 2002-03, 브라질 세리에 A 1994, 그리스 리그 2004-05~2006-07, 그리스컵 2004-05·2005-06, 우즈베키스탄 리그 2008~2010, 우즈베키스탄컵 2008·2010, 캄페오나투 파울리스타 1996, 캄페오나투 미네이루 2004). 우즈베키스탄 2008 우승·컵은 Transfermarkt에 옛 이름 쿠루브치로 적힘. 개인: 발롱도르·FIFA 올해의 선수 1999, 득점왕(챔스 1999-00 10골, 코파 델 레이 1997-98 8골, 우즈베키스탄 1부 2009 20골). 대표팀 기록은 뺌",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ("dc", "dk", "dsf", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP"):
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 낱말: " + bad)

# ---------------------------------------------------------------- §16 점검
problems = []
seen = collections.Counter((r[0], r[9], r[4], r[5], r[6], r[13]) for r in E)
for k, v in seen.items():
    if v > 1: problems.append(("중복", k))
byd = collections.defaultdict(list)
for r in E: byd[(r[9], r[1])].append(r)
for k, rs in byd.items():
    gs = sorted(rs, key=lambda r: r[4])
    for a, b in zip(gs, gs[1:]):
        if (b[5], b[6]) < (a[5], a[6]) and not (a[11] and str(a[11]).startswith("45+")): problems.append(("스코어 역순", k, a[4], b[4]))
Md = {m[0] for m in M}
for r in E:
    if r[9] not in Md: problems.append(("E 날짜가 M에 없음", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
mm_ = {m[0]: m for m in M}
Gstart = {ldate(g): g["isStarting"] == "True" for g in GAMES}
for r in E:
    m = mm_.get(r[9])
    if m and (key(m[1]) != key(r[1]) or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > m[3] + 3 and not r[10] and Gstart[r[9]]: problems.append(("출전 분보다 늦은 기록", r, m))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))
if len(Md) != len(M): problems.append(("같은 날 두 경기", len(M) - len(Md)))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const RIV_E={J(E)};\nconst RIV_M={J(M)};\nconst RIV_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "date_fixed": DATE_FIXED, "elo_sources": ELO_SRC,
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
