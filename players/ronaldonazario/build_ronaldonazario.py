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

# 같은 경기가 두 번 적힌 것: 1993.9.26 상파울루전 0-0은 헤코파 1차전이 일정 문제로 브라질 세리에 A 5라운드 경기로 함께 치러짐
# (영어 위키백과 '1993 Recopa Sudamericana': "the first leg was played as part of the Campeonato Brasileiro") → 한 경기로 셈(헤코파 행만 둠)
DUP_GAME = {"4798504": "3296953"}

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
    if g["gameId"] in DUP_GAME: continue
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
    sys.exit(1)
if "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    print("라리가 가운데값:", sorted(INTERP_USED))
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 대조(2010 브라질 리그, 골만 — FotMob에 도움 자료 없음)
FM_CMP = []
for gid, fs in FME.items():
    tm = [r for r in E if r[0] == "g" and G[gid]["date_local"] == r[9]]
    fm = [f for f in fs if f["scorer"] == "Ronaldo"]
    for f in fm:
        t = int(f["minute"]) + int(f["overload"] or 0)
        hit = sorted(tm, key=lambda r: abs(r[4] - t))
        FM_CMP.append((G[gid]["date_local"], opp(G[gid]), t, "PK" if f["goalDescriptionKey"] == "penalty" else "",
                       hit[0][4] if hit else None, "PK" if hit and hit[0][8] else ""))
# FotMob 분이 다른 것: 2010.11.13 크루제이루전 PK(FotMob 43분 vs TM 89분) — Jornal do Brasil 2010.11.13('Ronaldo decide em pênalti
# polêmico', 후반 41분 PK 판정)·FourFourTwo('three minutes from time')가 경기 막판이라 TM 분 유지. 2010.11.3 아바이전 PK(TM 88·FotMob 90)는 TM.

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음, 보고용)
MATE_NAME = {"kak.js": "Kaká", "nis.js": "Ruud van Nistelrooy", "hig.js": "Gonzalo Higuaín"}
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] == "Ronaldo" and b in MATE_NAME:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (x[5], x[6], x[2], x[12], x[3])
            cross.append(("동료 도움→호나우두 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "호나우두 골 없음"),
                          x[2:8], hit[0][2:8] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and r[13] == nm:
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (r[5], r[6], r[2], r[12], r[3])
                cross.append(("호나우두 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else "동료 골 없음"), r[2:8], hit[0][2:8] if hit else None))
        for x in oe:   # 동료 골 중 TM이 호나우두 도움으로 적었으나 뺀 것(참고)
            if x[0] == "g":
                for j in judg:
                    if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2:
                        cross.append(("TM 호나우두 도움을 뺀 동료 골", b, x[9], x[4], j[5], "동료 파일 도움 행 " + ("있음" if any(y[0] == "a" and y[9] == x[9] and "Ronaldo" == y[13] for y in oe) else "없음")))
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
CLUBS = [("crurn", "1994-08-18", "크루제이루", "1993~1994"), ("psvrn", "1996-07-17", "PSV 에인트호번", "1994~1996"),
         ("fcbrn", "1997-07-25", "바르셀로나", "1996~1997"), ("intrn", "2002-08-31", "인테르", "1997~2002"),
         ("rmrn", "2007-01-30", "레알 마드리드", "2002~2007"), ("acmrn", "2008-12-12", "AC 밀란", "2007~2008"),
         ("corrn", None, "코린치안스", "2009~2011")]
TM_CLUB = {"609": "crurn", "383": "psvrn", "131": "fcbrn", "46": "intrn", "418": "rmrn", "5": "acmrn", "199": "corrn"}
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
TM_A_ALL = sum(1 for gid, evs in EVS.items() if gid in G for e in evs if e["assist_id"] == ME and e["scorer_id"] != ME)
SELF_PK = [j for j in judg if j[0].startswith("도움 아님")]
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
def jl(reason): return ", ".join(f"{d_(j[1])} {j[2]} {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
SHOT = "슈팅 리바운드('Shot on goal')"
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
PKREB = [j for j in judg if j[0].startswith("PK 아님")]

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
NOTE_LINES = [
    f"호나우두(크루제이루·PSV 에인트호번·바르셀로나·인테르·레알 마드리드·AC 밀란·코린치안스)의 클럽 공식 경기 {NG}경기({d_(first[0])} 코린치안스전 ~ {d_(last[0])} 톨리마전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CN[k]} {c3(v)}" for k, v in ST.items()),
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(출전 {NG}경기·{MIN_TOT:,}분)과 경기 리포트(출전한 {NG}경기 전부) 기준. 출전 시간 90분 추정 경기는 없음. 크리스티아누 호날두와는 다른 선수(Transfermarkt 선수 번호 3140)",
    "PSV·바르셀로나·인테르·레알 마드리드·AC 밀란·코린치안스의 경기·골 수는 영어·포르투갈어 위키백과 경력 표와 같음(PSV 57경기 54골, 바르셀로나 49·47, 인테르 99·59, 레알 마드리드 177·104, AC 밀란 20·9, 코린치안스 69·35)",
    "크루제이루(1993~1994)는 Transfermarkt에 브라질 세리에 A 1993 14경기·헤코파 수다메리카나 2경기·수페르코파 수다메리카나 4경기·리베르타도레스 1994 8경기(28경기 22골)만 있고, 캄페오나투 미네이루(주 선수권) 1993·1994와 코파 두 브라질 경기는 없음. 영어 위키백과는 47경기 44골(1994 주 선수권 18경기 22골 등), 포르투갈어 위키백과는 58경기 56골로 서로도 다름. 빠진 경기는 경기별 자료(날짜·출전 시간·골 시간)를 모두 갖춘 출처를 찾지 못해 넣지 않음 — 이 때문에 크루제이루 시절 기록은 실제보다 적음(Transfermarkt 업적 페이지의 1993-94 미네이루 득점왕 23골도 이 계산에 없음)",
    "1993.10.28 수페르코파 8강 2차전 나시오날 원정(2-3 승, 합산 4-4)은 Transfermarkt가 120분 경기로 적었으나 RSSSF 경기 기록에 연장 표시 없이 바로 승부차기(2-4 패)라 출전 90분으로 셈. 수페르코파 1993 골 시간은 RSSSF와 몇 분 다른 것이 있음(콜로콜로 2차전 Transfermarkt 28·61분, RSSSF 20·71분 — 골 직전 스코어는 같음)이나 Transfermarkt 리포트 시간을 씀",
    "1993.9.26 상파울루전(0-0)은 헤코파 수다메리카나 1차전이 일정 문제로 브라질 세리에 A 경기로 함께 치러진 한 경기라(영어 위키백과) Transfermarkt의 두 줄을 한 경기(헤코파)로 셈. 그래서 경기 수가 Transfermarkt보다 1 적음",
    "1994.4.21 리베르타도레스 16강 1차전 우니온 에스파뇰라 원정(1-4 패) Transfermarkt 리포트는 상대 골 1개만 적혀 있으나 호나우두 골·도움이 없어 영향 없음",
    f"PK 골 {NPK}개는 Transfermarkt 골 유형 'Penalty' 기준. 'Penalty rebound'(PK가 막힌 뒤 리바운드 골) " + ", ".join(f"{d_(j[1])} {j[2]} {j[3]}분" for j in PKREB) + "은 일반 골로 셈",
    "2010 브라질 세리에 A 골은 FotMob 경기 기록과 대조함(FotMob에 있는 8경기). 2010.11.13 크루제이루전 PK 골은 FotMob 43분·Transfermarkt 89분으로 다른데, 경기 기사(Jornal do Brasil: 후반 41분 PK 판정, FourFourTwo: 'three minutes from time')대로 경기 막판인 Transfermarkt 분을 씀. 2010.11.3 아바이전 PK 골(Transfermarkt 88분·FotMob 90분)도 Transfermarkt 분. 파울리스타·코파 두 브라질·리베르타도레스와 2009년 경기는 FotMob에 없어 Transfermarkt만 근거",
    f"도움 {NA}개 = Transfermarkt 리포트 도움 {TM_A_ALL}개 − PK 유도 {EX['PK 유도']}개 − 'Shot on goal' 리바운드 {EX[SHOT]}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개. 모두 2014년 이전이라 Transfermarkt 단일 출처이고 다른 출처로 대조하지 못함. 도움 유형 칸이 빈 {UNTYPED}개도 도움으로 셈",
    "PK 유도로 뺀 도움: " + jl("PK 유도"),
    "리바운드·자책골이라 뺀 도움: " + jl(SHOT) + " (슈팅 리바운드), " + jl("상대 자책골 유도") + " (상대 자책골)",
    f"Transfermarkt 리포트가 본인 PK 골에 본인 이름을 도움 칸('Penalty: Fouled player')에 적은 {len(SELF_PK)}개는 도움이 아님",
    "날짜는 경기 현지 날짜. 코린치안스 경기는 Transfermarkt 경기 시각(UTC)을 상파울루 시간으로 바꾼 날짜라 저녁 경기 25경기는 Transfermarkt 리포트 날짜(중부 유럽 기준)보다 하루 앞(예: 데뷔전 2009.3.4 이툼비아라 원정, 마지막 경기 2011.2.2 톨리마 원정 — 경기 기사 날짜와 같음). 2002 인터콘티넨털컵은 도쿄 날짜",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(카카·판니스텔로이 등) 값을 먼저 쓰고, 없으면 기존 선수 자료의 같은 팀·같은 시즌 값, 그다음 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 모형에 넣음(기록 {len(E)}개: 같은 경기 {ELO_SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {ELO_SRC['기존 팀×시즌 값']}, 순위표+모형 {ELO_SRC['순위표+리그 모형']}, 직접 추정 {ELO_SRC['직접 추정']})",
    "에레디비시 1994-95·1995-96, 세리에A 18팀 시즌(1997-98~2001-02), 분데스리가 1990년대는 다른 선수 자료와 같은 순위별 고정값. 라리가 2002-03의 기존 자료에 없는 4·7·12·19위는 앞뒤 순위 값의 가운데(1813·1759·1685·1599)",
    "라리가 1996-97(22팀)은 다른 선수 자료가 없어 추정함(리그 수준 추정): 2003-04 순위별 값과 같은 흩어짐에 평균을 1995-96·1998-99 기존 값과의 차이만큼(+13.5) 올려 22팀 순위 곡선으로 계산(1위 1979 ~ 22위 1589). 세군다 1996-97(20팀)은 같은 2부 모형(라스팔마스 7위 1644)",
    "브라질 세리에 A·B는 달력 연도 순위(평균 1598·1370, 네이마르·비니시우스·루카스 모우라 자료와 같은 방식). 1993 세리에 A는 32팀 조별 방식이라 포르투갈어 위키백과 시즌 문서의 최종 순위(크루제이루 15위)를 32팀 곡선에 넣음(Transfermarkt 1993 순위표는 받지 못함). 파울리스타·코파 두 브라질 상대 중 세리에 A·B 밖 팀은 브라질 4부 이하 1200(이투아누 2009(세리에 D)·2010, 미라솔·히우 클라루 2010 — 포르투갈어 위키백과 그해 세리에 C·D 참가표)",
    "리그 표가 없는 상대는 당시 수준을 추정함(모두 '추정'): " + ", ".join(f"{o} {e}" for o, e, lv in MAN_USED if e != 1200),
    "대회 비중: 코파 델 레이·코파 이탈리아·KNVB컵·코파 두 브라질은 국내컵(16강까지·8강·준결승·결승), 수페르코파(스페인)·헤코파 수다메리카나 1993(두 경기 결승)은 국내컵 결승, 캄페오나투 파울리스타(상파울루 주 선수권)는 리그 단계·준결승·결승 모두 국내컵 하위 라운드 비중(네이마르 자료와 같음), 1999 세리에A UEFA컵 진출 플레이오프(볼로냐 1차전)는 리그 경기로 셈",
    "UEFA컵: 1라운드는 유로파 예선, 2·3라운드·16강·8강은 유로파 토너먼트, 준결승·결승(1998 라치오전, 파리)은 유로파 준결승·결승. UEFA 컵위너스컵 1996-97(바르셀로나 우승)은 이 계산기에 같은 대회가 없어 유로파 비중으로 계산함: 1라운드(32팀)부터 8강까지 유로파 토너먼트, 준결승·결승(1997.5.14 PSG전, 로테르담)은 유로파 준결승·결승. 2002 인터콘티넨털컵(올림피아전, 요코하마)은 클럽 월드컵. 챔스 2002-03 2차 조별리그도 조별",
    "남미 대회: 리베르타도레스 1994·2010·2011(예선 포함)은 리베르타도레스 조별·16강 비중, 수페르코파 수다메리카나(수페르코파 리베르타도레스) 1993은 남미 2부 대회인 수다메리카나 비중(16강, 8강)으로 계산함",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·스페인 국내 대회·코파 이탈리아는 원정 다득점·연장, 코파 두 브라질 2009와 리베르타도레스 2010~2011은 원정 다득점 있고 연장 없이 승부차기(2010 16강 플라멩구전은 합산 2-2에서 원정 다득점으로 탈락), 파울리스타 준결승·결승과 수페르코파 수다메리카나 1993·헤코파 1993·리베르타도레스 1994는 원정 다득점·연장 없이 승부차기(1993 나시오날전 합산 4-4, 크루제이루 원정 3골인데 승부차기)",
    "못 뛴 다른 차전 스코어는 Transfermarkt 리포트로 채움(1995 리즈 1차전 3-5, 1996 수페르코파 2차전 아틀레티코 3-1 등)",
    "시즌 구분: 크루제이루·코린치안스는 달력 연도, PSV는 7월 10일 기준(로번·판니스텔로이 자료와 같음, 7월 경기 없음), 나머지는 8월 1일 기준. 클럽 구분은 1994.8.18 전 크루제이루, 1996.7.17 전 PSV, 1997.7.25 전 바르셀로나, 2002.8.31 전 인테르, 2007.1.30 전 레알 마드리드, 2008.12.12 전 AC 밀란, 이후 코린치안스",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 월드컵·코파 아메리카·컨페더레이션스컵과 대표팀 득점왕은 뺌. 2006-07 라리가(1월 이적)는 Transfermarkt대로 셈. 1993 코파 두 브라질(크루제이루)·캄페오나투 미네이루 1994도 Transfermarkt대로 넣음(이 계산에는 그 경기들이 없음)",
    "은퇴: 2011.2.14 은퇴 발표(Transfermarkt 이적 기록), 마지막 클럽 경기 2011.2.2 리베르타도레스 예선 톨리마 원정",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "csa", "lib", "TM ", "elk", "elq", "cwc", "MAN"]:
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
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
js = f"const RNO_E={J(E)};\nconst RNO_M={J(M)};\nconst RNO_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": cross,
           "fotmob_goal_cmp": FM_CMP, "elo_sources": ELO_SRC, "laliga_midpoints": sorted(INTERP_USED),
           "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for k, v in ST.items(): print(" ", k, v)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if not (len(c) > 4 and c[4] == "일치"): print("  대조:", c)
for x in FM_CMP: print("  FotMob:", x)
