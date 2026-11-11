#!/usr/bin/env python3
"""Ronaldo Nazário (호나우두, TM 3140 — 크리스티아누 호나우두 아님): raw/ -> ronaldonazario.json + src/data/rno.js
(판정 근거는 judgments.md)

  python3 players/ronaldonazario/build_ronaldonazario.py            # 파일 쓰기
  python3 players/ronaldonazario/build_ronaldonazario.py --debug    # Elo 출처 로그만 출력

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/ranks.txt(Transfermarkt 순위표), raw/fotmob_events.csv(2010 브라질 리그 대조),
      elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값), src/data/*.js(같은 경기 다른 선수 자료).
"""
import csv, json, os, re, sys, unicodedata, collections, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "rno.js")
OUT_JSON = os.path.join(HERE, "ronaldonazario.json")
ME = "3140"            # Transfermarkt 선수 id (호나우두 나자리우)
ME_KO = "호나우두"
# 같은 회차에 다른 판정 에이전트가 쓰는 파일(대조·재사용에서 뺌)
NEW_FILES = {"rau.js", "zid.js", "she.js", "ozi.js", "fod.js", "got.js", "com.js", "pas.js", "cal.js", "rno.js"}

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

# ---------------------------------------------------------------- 판정 표
# 날짜: date_local(Transfermarkt 경기 시각 UTC → 현지 시간대). 코린치안스 25경기는 리포트 날짜(중부 유럽)보다 하루 앞인데,
# 2009.3.4 이툼비아라전 데뷔(Jornal de Brasília 경기 정보: 수요일 3월 4일 21:50 브라질리아 시간)·2011.2.2 톨리마전 탈락(마지막 경기)
# 등 기사 날짜와 맞아 현지 날짜를 씀(루카스 모우라·네이마르 선례와 같음).
def ldate(g): return g["date_local"]
def opp(g): return g["opponent"].strip()

# 출전 분 고침: 1993.10.28 수페르코파 8강 2차전 나시오날 원정(TM gameDuration 120, playedMinutes 120)은 RSSSF 경기 기록상
# 연장 표시 없이 2-3 뒤 바로 승부차기(4-2) — 원정 다득점·연장 없이 승부차기(같은 대회 플라멩구-리버 플레이트 8강도 같음) → 90분
MIN_FIX = {"4748711": 90}

# 출전 시간이 TM에 있는 경기만. 크루제이루의 캄페오나투 미네이루·코파 두 브라질 경기는 TM에 없어 넣지 않음(judgments.md 1절)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BRA1", "NL1", "ES1", "IT1", "ITPO"}          # ITPO: 1999 세리에A UEFA컵 진출 플레이오프(볼로냐) = 리그 경기
CUP = {"NLP", "CDR", "CIT", "BRC", "BCP1", "BCPF"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("BCP1", "BCPF"): return "dc"              # 캄페오나투 파울리스타: 리그 단계·준결승·결승 모두 국내컵 하위 비중(네이마르 선례)
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "SUC": return "df"                         # 수페르코파(두 경기)
    if cid == "RECO": return "df"                        # 헤코파 수다메리카나(두 경기 결승) = 슈퍼컵(네이마르 2012 선례)
    if cid == "WEPO": return "cwc"                       # 인터콘티넨털컵 2002
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2002-03 2차 조별('Group 3') 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 2·3라운드·16강·8강
    if cid == "EPP":                                     # UEFA 컵위너스컵 1996-97: 유로파 비중, 1라운드(32팀)는 UEFA컵 2라운드(32팀)와 같은 토너먼트
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "CLI":                                     # 리베르타도레스
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"                                     # 조별·16강·예선
    if cid == "SCSA":                                    # 수페르코파 수다메리카나(수페르코파 리베르타도레스) 1993: 수다메리카나 비중
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE or cid == "BCP1": return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("UEFA", "CL", "CLQ", "EPP"): return (1, 1)
    if cid in ("CDR", "SUC"): return (1, 1)             # 스페인 국내 대회 2018-19까지 원정 다득점·연장
    if cid == "CIT": return (1, 1)                      # 코파 이탈리아 2021-22까지 원정 다득점, 연장
    if cid == "ITPO": return (1, 1)
    if cid == "BCPF": return (0, 0)                     # 파울리스타 두 경기 라운드: 원정 다득점·연장 없음(네이마르 선례)
    if cid == "BRC": return (1, 0)                      # 코파 두 브라질 2009: 원정 다득점, 연장 없음(네이마르 2009~13 선례)
    if cid == "CLI":
        if d >= "2010-01-01": return (1, 0)             # 2010 16강 플라멩구전: 합산 2-2 원정 다득점으로 플라멩구 진출
        return (0, 0)                                   # 1994: 원정 다득점 없이 승부차기(호나우두 골·도움 없음)
    if cid == "SCSA": return (0, 0)                     # 1993 8강 나시오날전: 합산 4-4(크루제이루 원정 3골)인데 바로 승부차기(RSSSF)
    if cid == "RECO": return (0, 0)                     # 1993 헤코파: 0-0·0-0 뒤 승부차기
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
    oh, oa = map(int, m["other_leg_score"].split(":"))   # 이 리포트의 홈 팀 기준
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
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])

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
    g = G[gid]; side = side_of(gid); prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if not (is_g or is_a): continue
        if e["side"][0] != side and not (is_a and is_og(e)):
            sys.exit("득점 편 이상 " + gid + " " + e["minute"])
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
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

# 리포트 골·도움 = API 경기별 합계 점검
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
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b == "hon.js" or b in NEW_FILES: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "milan", "inter", "madrid", "moscow", "moskau", "paulista", "paulo"}   # 도시 이름(인테르-AC 밀란, 레알-아틀레티코, 코린치안스-상파울루 오인 방지)
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
# 'Classificação geral'(Transfermarkt 1993 표는 다른 시즌이 나와 못 씀). 크루제이루 상대만 TM 이름으로 적음.
BRA1993 = {"Sport Club Corinthians Paulista": 3, "Esporte Clube Bahia": 30, "CR Flamengo": 7, "Botafogo de Futebol e Regatas": 31,
           "CA Bragantino": 19, "Sport Club Internacional": 17, "Sociedade Esportiva Palmeiras": 1, "Santos FC": 5,
           "São Paulo Futebol Clube": 4, "Grêmio Foot-Ball Porto Alegrense": 13, "Clube de Regatas Vasco da Gama": 20,
           "Fluminense Football Club": 28, "Clube Atlético Mineiro": 32, "Guarani Futebol Clube (SP)": 6, "Paraná Clube": 10,
           "Sport Club do Recife": 25, "Goiás Esporte Clube": 26, "Criciúma Esporte Clube": 14, "Coritiba FC": 22,
           "Clube do Remo": 8, "Associação Portuguesa de Desportos": 9, "Paysandu Sport Club": 11, "União São João EC (SP)": 12,
           "América Futebol Clube (MG)": 16, "Clube Náutico Capibaribe": 18, "Ceará Sporting Club": 21, "Santa Cruz FC": 23,
           "Atlético Paranaense": 24, "Fortaleza Esporte Clube": 27, "Desportiva Ferroviária": 29, "EC Vitória": 2}
for nm, r in BRA1993.items(): RANKS[("BRA1", "1993")][key(nm)] = (r, 32, nm)

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
def half_up(x): return int(x + 0.5)

# 기존 자료의 고정 순위값
SA18 = [1969, 1884, 1837, 1808, 1793, 1780, 1762, 1743, 1728, 1713, 1704, 1697, 1690, 1676, 1657, 1645, 1633, 1614]   # 세리에A 18팀(7·9·12·16위는 앞뒤 가운데, 토티·델 피에로 v1.149)
SEG = [1753, 1712, 1687, 1674, 1660, 1654, 1647, 1640, 1632, 1623, 1615, 1610, 1606, 1601, 1598, 1595, 1589, 1580, 1572, 1567, 1560, 1553]  # 세군다 22팀(기존 고정값)
BUL = {1: 2006, 2: 1912, 3: 1860, 5: 1812, 6: 1797, 7: 1777, 9: 1737, 10: 1723, 11: 1713, 14: 1682, 15: 1661, 16: 1644, 17: 1634}  # 분데스리가 1994-95~2002-03 기존 순위값
ERE = [1837, 1735, 1677, 1642, 1624, 1608, 1587, 1563, 1542, 1528, 1516, 1504, 1499, 1482, 1459, 1441, 1430, 1406]  # 에레디비시 18팀(모든 시즌 같은 값)

# 라리가: 기존 자료의 시즌별 순위값, 없는 순위는 앞뒤 기존 순위값의 가운데(교훈: 단순 중간값, 반올림은 0.5 올림)
LL = collections.defaultdict(dict)
for (k, s), vals in TABLE.items():
    for e, lv in vals:
        m = re.match(r"라리가 (\d{4}-\d\d) (\d+)위$", lv)
        if m: LL[m.group(1)].setdefault(int(m.group(2)), collections.Counter())[e] += 1
LL = {s: {r: c.most_common(1)[0][0] for r, c in d.items()} for s, d in LL.items()}
def mid(pts, r):
    if r in pts: return pts[r], False
    lo = [k for k in pts if k < r]; hi = [k for k in pts if k > r]
    a, b = max(lo), min(hi)
    return half_up(pts[a] + (pts[b] - pts[a]) * (r - a) / (b - a)), True
# 라리가 1996-97(22팀)은 기존 자료가 없음 → 2003-04 순위값이 '1712.7 + 100.16 × 순위 곡선'(오차 1 이내)이라
# 같은 흩어짐에 평균을 1995-96(6위 1782, 2003-04보다 +16)·1998-99(13위 1677, +11) 기존 값 차이의 평균(+13.5)만큼 올려 22팀 곡선으로 계산(추정)
LL9697_MEAN = 1712.7 + 13.5
LL_SD = 100.16

INTERP_USED = set()
def rank_model(lg, season, r, n):
    if lg == "NL1":
        assert n == 18; return ERE[r - 1], f"에레디비시 {season} {r}위"
    if lg == "IT1":
        if n == 18: return SA18[r - 1], f"세리에A {season} {r}위"
        return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "ES1":
        if season == "1996-97":
            return half_up(LL9697_MEAN + LL_SD * curve(r, n)), f"라리가 1996-97 {r}위 (리그 수준 추정)"
        v, it = mid(LL[season], r)
        if it: INTERP_USED.add((season, r, v))
        return v, f"라리가 {season} {r}위"
    if lg == "ES2":   # 세군다: 22팀 시즌은 기존 고정 순위값, 20팀 시즌(1996-97)은 같은 모형(1624 + 51.24 × 순위 곡선)
        if n == 22: return SEG[r - 1], f"세군다(2부) {season} {r}위"
        return half_up(1624 + SD2 * curve(r, n)), f"세군다(2부) {season} {r}위"
    if lg == "L1" and season < "2003-04" and r in BUL:   # 분데스리가 1994-95~2002-03 기존 값은 시즌과 상관없이 순위마다 같은 값
        return BUL[r], f"분데스리가 {season} {r}위"
    if lg == "BRA1": return half_up(1598 + 63 * curve(r, n)), f"브라질 세리에 A {season} {r}위"
    if lg == "BRA2": return half_up(1370 + SD2 * curve(r, n)), f"브라질 세리에 B {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
SOUTH = {"BRA1", "BCP1", "BCPF", "BRC", "CLI", "RECO", "SCSA"}
def table_candidates(cid, d):
    y = d[:4]
    if cid in SOUTH: return [("BRA1", y), ("BRA2", y)]
    s = eu(d)
    return [("NL1", s), ("ES1", s), ("IT1", s), ("ES2", s), ("L1", s)]

C4 = "브라질 4부 이하 (추정)"
# 순위표·기존 자료에 없는 상대(직접 추정, 모두 lv에 '추정') — judgments.md 6절
MAN = {
    ("CSD Colo-Colo", "1993"): (1550, "칠레 1부 1993 1위 (추정, 다른 선수 자료 콜로콜로 2007 칠레 상위 팀 1550과 같음)"),
    ("Club Nacional", "1993"): (1600, "우루과이 상위 팀 (추정, 다른 선수 자료 페냐롤 2011 우루과이 우승 팀 1600과 같음)"),
    ("CA Vélez Sarsfield", "1994"): (half_up(1583 + 63 * curve(1, 20)), "아르헨티나 1부 1위권 (추정, 1993 클라우수라·1994 리베르타도레스 우승, 아르헨티나 1부 모형 1위 값; 1993-94 순위표 없음)"),
    ("CA Boca Juniors", "1994"): (half_up(1583 + 63 * curve(5, 20)), "아르헨티나 1부 중상위권 (추정, 아르헨티나 1부 모형 5위 값; 1993-94 순위표 없음)"),
    ("Myllykosken Pallo -47", "1995-96"): (1400, "핀란드 1995 2위 (추정, 다른 선수 자료 HJK 헬싱키 2022 1400과 같음)"),
    ("AEK Larnaca", "1996-97"): (1400, "키프로스 (추정, 다른 선수 자료 아폴론 리마솔 2001 1400과 같음)"),
    ("AIK", "1996-97"): (1450, "스웨덴 상위권 (추정, 다른 선수 자료 AIK 1999 1450과 같음)"),
    ("Neuchâtel Xamax", "1997-98"): (1406, "스위스 1997-98 7위 (추정, 다른 선수 자료의 스위스 7위 1406과 같음)"),
    ("Spartak Moscow", "1997-98"): (1600, "러시아 1997 1위 (추정, 다른 선수 자료 스파르타크 모스크바 2000 1위 1600과 같음)"),
    ("Spartak Moscow", "1998-99"): (1600, "러시아 1998 1위 (추정, 다른 선수 자료 스파르타크 모스크바 2000 1위 1600과 같음)"),
    ("AEK Athens", "2002-03"): (1550, "그리스 상위권 (추정, 다른 선수 자료 AEK 2003-04·2006-07 1550과 같음)"),
    ("Club Olimpia", "2002-03"): (1500, "파라과이 상위 팀, 2002 리베르타도레스 우승 (추정, 다른 선수 자료의 파라과이 상위 팀 1500과 같음)"),
    ("Lokomotiv Moskau", "2002-03"): (1580, "러시아 2002 1위 (추정, 다른 선수 자료 로코모티프 모스크바 2001·2003 1580과 같음)"),
    ("Wisla Kraków", "2004-05"): (1529, "엑스트라클라사 2003-04 1위 (추정, 다른 선수 자료 비슬라 크라쿠프 2008-09 1위 1529와 같음)"),
    ("Dynamo Kyiv", "2004-05"): (1620, "우크라이나 상위권 (추정, 다른 선수 자료 디나모 키이우 2003-04 1620과 같음)"),
    ("Club Cerro Porteño", "2010"): (1500, "파라과이 상위 팀 (추정)"),
    ("Ituano Futebol Clube (SP)", "2009"): (1200, C4),            # 2009 세리에 D(포르투갈어 위키백과 2009 세리에 D 참가 팀)
    ("Ituano Futebol Clube (SP)", "2010"): (1200, C4),            # 2010 세리에 C·D 참가표에 없음
    ("Mirassol Futebol Clube (SP)", "2010"): (1200, C4),          # 2010 세리에 C·D 참가표에 없음(2009 D)
    ("Rio Claro Futebol Clube (SP)", "2010"): (1200, C4),         # 2010 세리에 C·D 참가표에 없음
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
    seasons = [d[:4], eu(d)] if cid in SOUTH else ([eu(d), d[:4], str(int(d[:4]) + 1)] if cid in ("CL", "CLQ", "UEFA", "EPP", "WEPO") else [eu(d)])
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for lg, s in table_candidates(cid, d):
        t = RANKS.get((lg, s), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    for s in seasons:
        if (o, s) in MAN:
            e, lv = MAN[(o, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (mi > 95 and ko) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))

if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
if "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    print("라리가 가운데값:", sorted(INTERP_USED))
    sys.exit(0)
