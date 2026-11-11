#!/usr/bin/env python3
"""Lucas Moura: raw/ -> lucasmoura.json + src/data/luc.js (판정 근거는 judgments.md)

  python3 players/lucasmoura/build_lucasmoura.py

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(대조), raw/ranks.txt(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값), src/data/*.js(같은 경기 동료 자료 대조·재사용).
"""
import csv, json, os, re, sys, unicodedata, collections, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "luc.js")
OUT_JSON = os.path.join(HERE, "lucasmoura.json")
LM = "77100"
GAP = "2014-08-01"           # 이 날짜 전 도움은 Transfermarkt 리포트, 뒤는 Transfermarkt ∩ FotMob(+ 다른 출처 2곳)
NEW_PREFIXES = ("dem.js", "gna.js", "mer.js", "nis.js")   # 같은 회차에 다른 판정 에이전트가 쓰는 파일(대조에서 뺌)

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 판정 표
# 골 직전 스코어 고침(gameId|분 -> (홈, 원정) 골 직전). 1138628: Transfermarkt 리포트는 루카스 62분 골을 1-0 첫 골로,
# 시세루·다고베르투 65분 두 골을 모두 3-0으로 적음. FotMob(시세루 56분 1-0, 루카스 61분 2-0, 다고베르투 64분 3-0)과
# worldfootball(시세루 56분 1-0, 루카스 62분 2-0)이 시세루 선제골 → 루카스 → 다고베르투 순서.
BEFORE_FIX = {"1138628|62": (1, 0), "1138628|65|Dagoberto": (2, 0)}
# 못 뛴(또는 리포트가 틀린) 다른 차전 스코어(우리, 상대). 2270902: 1차전 리포트(2270898)가 홈·원정 스코어를 뒤집어 적어
# 2차전 리포트의 다른 차전 표기도 0:2. 실제 1차전 우니베르시다드 데 칠레 0-2 상파울루(선수 경기 성적 API·FotMob 0-2).
OTHER_FIX = {"2270902": (2, 0)}
# 2014.8 이후 Transfermarkt 단일 출처 도움(FotMob 경기 이벤트 없음) 판정: gameId|분 -> 근거(넣음) / None(뺌)
POST_GAP = {
    "2511744|54": "maxifoot 경기 기사('double passeur décisif', 카바니에게 침투 패스)·Bleacher Report",
    "2511744|84": "maxifoot('Lucas perfore la défense et sert Bahebeck', 84분)·CulturePSG 문자중계('Bon ballon de Lucas au second poteau pour Bahebeck')",
    "2518998|72": "CulturePSG 문자중계('Centre de Lucas au 2ème poteau pour Zlatan')·maxifoot('sa passe décisive parfaite pour Ibra')",
    "2658417|62": "FourFourTwo('Lucas burst down the left… crossing for Ibrahimovic to chest home')·Bleacher Report",
    "2814001|30": "FourFourTwo('Silva lost his marker after Lucas' corner')·CulturePSG 선수 평가(루카스 코너킥에서 선제골)",
    "4238640|39": "FotMob 선수 경기 목록 도움 1(FotMob 경기 기록에 도움 칸 없음)",
    "4238666|45+3": "FotMob 선수 경기 목록 도움 1(FotMob 경기 기록에 도움 칸 없음)",
    "4238720|25": "FotMob 선수 경기 목록 도움 1(FotMob 경기 기록에 도움 칸 없음)",
    "4311463|23": "FotMob 선수 경기 목록 도움 1(FotMob 경기 기록에 도움 칸 없음)",
    "4568130|63": "FotMob 선수 경기 목록 도움 1(FotMob 경기 기록에 도움 칸 없음)",
}
# FotMob에만 있는 도움(넣지 않음 / 넣음)
FM_ONLY = {
    "2618626|86": ("Zlatan Ibrahimović", "넣음", "FotMob 경기 기록(assist by Lucas Moura)·Sports Mole 문자중계(Assist: Lucas 86')·AP 기사('Ibrahimovic and Lucas set each other up')·maxifoot(골키퍼 킥을 루카스가 머리로 떨굼). Transfermarkt 리포트에는 도움 없음"),
}
# FotMob에만 있는 골(넣지 않음)
FM_ONLY_GOAL = {
    "2511744|84": "FotMob은 84분 골을 루카스 골로 적었으나 Transfermarkt·Sports Mole·ESPN·maxifoot이 바에벡 골(루카스 도움)로 적음",
}
# 골 판정 차이
GOAL_NOTE = []

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"BRA1", "FR1", "GB1"}
PAULISTA = {"BCP1", "BCPF"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid in PAULISTA: return "dc"            # 캄페오나투 파울리스타: 리그 단계·8강·준결승 모두 국내컵 하위 라운드 비중(네이마르·비니시우스 선례)
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
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"                          # intermediate stage·16강
    if cid == "ECLQ": return "ecq"
    if cid == "UCOL": return "ecg"
    if cid == "FRCH": return "df"
    if cid in ("BRC", "FRC", "FRL", "FAC", "CGB"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or (cid == "FAC" and r.startswith("sixth round")): return "dk"   # 리그컵 8강(5라운드)·FA컵 6라운드
        return "dc"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE_IDS: return 0
    if cid in PAULISTA and not (r.startswith("quarter") or r.startswith("semi")): return 0   # 리그 단계·조별
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 입력
games = rd("tm_games.csv")
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
PMS = collections.defaultdict(list)
for r in rd("fotmob_playerMatches.csv"): PMS[r["matchId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv")}

def ldate(g): return g["date_local"]
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    r = rnd.lower()
    if cid in ("CL", "EL", "ELQ", "ECLQ"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid in ("CLI", "CS"):
        if r.startswith("final"): return (0, 1)       # 남미 대회 결승: 원정 다득점 없이 연장(네이마르 2011 리베르타도레스 결승 선례)
        return (1, 0) if d < "2022-01-01" else (0, 0)  # 2021년까지 원정 다득점·연장 없이 승부차기, 2022년부터 둘 다 없음
    if cid == "BRC": return (1, 0) if d < "2018-01-01" else (0, 0)   # 코파 두 브라질: 2013년까지 원정 다득점(네이마르 선례), 2023~ 없음, 연장 없음
    if cid == "CGB": return (0, 0)                     # 리그컵 준결승 2018-19부터 원정 다득점·연장 없음
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    if gid in OTHER_FIX: return OTHER_FIX[gid]
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G:                                        # 다른 차전도 뛰었으면 선수 경기 성적 API 스코어(우리-상대)
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, m["other_leg_score"].split(":"))  # 이 리포트의 홈 팀 기준
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), g["round"])
    leg = 1 if ("1st" in rnd) else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def assist_reason(e):
    t = e["assist_type"]
    if e["scorer_id"] == LM: return "본인 PK 골에 본인 도움(PK 유도)"
    if e["own_goal"] == "1": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

def fm_assist(gid, mi):
    for f in FME[gid]:
        if f["lm_assist"] == "1":
            t = int(f["time"]) + int(f["overloadTime"] or 0)
            if abs(t - mi) <= 2 or abs(int(f["time"]) - mi) <= 2: return True
    return False

def pm_assists(gid):
    mid = FMMAP.get(gid, {}).get("fotmob_matchId")
    rs = PMS.get(mid, [])
    return int(rs[0]["assists"]) if rs else None

raw_rows, judg, post_gap_tm_only = [], [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]
    side = side_of(gid)
    prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == LM and e["own_goal"] != "1"
        is_a = e["assist_id"] == LM
        if not (is_g or is_a): continue
        tag = f"{gid}|{e['minute']}"
        if is_a and not is_g and f"{tag}|{e['scorer']}" in BEFORE_FIX: before = BEFORE_FIX[f"{tag}|{e['scorer']}"]
        elif is_g and tag in BEFORE_FIX: before = BEFORE_FIX[tag]
        if (e["side"][0] != side) and not (is_a and assist_reason(e)):
            sys.exit("득점 편 이상 " + gid + " " + e["minute"])
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        d = ldate(g)
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], why))
            elif d >= GAP and not fm_assist(gid, mi):
                post_gap_tm_only.append((gid, d, opp(g), e["minute"], e["scorer"], e["assist_type"], pm_assists(gid)))
                verdict = POST_GAP.get(tag, "미판정")
                if verdict == "미판정":
                    print("  [판정 필요] 2014.8 이후 Transfermarkt 단일 도움", gid, d, opp(g), e["minute"], e["scorer"], e["assist_type"] or "(유형 빈칸)", "FotMob 선수 경기 목록 도움", pm_assists(gid))
                elif verdict:
                    raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
                else:
                    judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], "2014.8 이후 단일 출처(다른 출처 확인 못 함)"))
            else:
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            pk = 1 if e["penalty"] == "1" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))

# FotMob에만 있는 도움·골(2014.8 이후) 목록
fm_only = []
for gid, fs in FME.items():
    if gid not in G: continue
    d = ldate(G[gid])
    for f in fs:
        t = int(f["time"]) + int(f["overloadTime"] or 0)
        if f["lm_assist"] == "1" and d >= GAP:
            if not any(r[0] == "a" and r[1] == gid and abs(r[2] - t) <= 2 for r in raw_rows) and \
               not any(e["assist_id"] == LM and abs(mins(e["minute"])[0] - t) <= 2 for e in EVS.get(gid, [])):
                fm_only.append(("a", gid, d, opp(G[gid]), t, f["scorer"]))
        if f["lm_scorer"] == "1":
            if not any(r[0] == "g" and r[1] == gid and abs(r[2] - t) <= 3 for r in raw_rows):
                fm_only.append(("g", gid, d, opp(G[gid]), t, f["assistStr"]))

# FotMob에만 있는 도움 중 넣는 것(득점 이벤트는 Transfermarkt 리포트의 같은 골)
for tag, (scorer, verdict, why) in FM_ONLY.items():
    gid, mm = tag.split("|"); mm = int(mm)
    if verdict != "넣음": continue
    side = side_of(gid); prev = (0, 0); hit = None
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        if e["scorer"] == scorer and abs(mins(e["minute"])[0] - mm) <= 2: hit = (e, prev)
        prev = (h, a)
    e, before = hit
    gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
    mi, dm = mins(e["minute"])
    raw_rows.append(("a", gid, mi, dm, gf, ga, 0, scorer))
for x in fm_only:
    k = f"{x[1]}|{x[4]}"
    if (x[0] == "a" and k not in FM_ONLY) or (x[0] == "g" and k not in FM_ONLY_GOAL):
        print("  [판정 필요] FotMob 전용", x)

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
    k = norm(n)
    return ALIAS.get(k, k)

TABLE = {}
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

RANKS = collections.defaultdict(dict)    # (league, season) -> {key: (rank, n, name)}
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

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

SOUTH = {"BRA1", "BCP1", "BCPF", "BRC", "CS", "CLI"}

# 기존 자료의 리그·시즌별 순위값(추정 아님) → 빈 순위는 앞뒤 순위값 사이 직선(교훈: 단순 중간값)
LGPTS = collections.defaultdict(dict)
for (k, s), (e, lv) in TABLE.items():
    if "추정" in lv: continue
    m = re.match(r"(리그 원|챔피언십|리그1|프리미어리그)(?:\([^)]*\))? (\d{4}-\d\d) (\d+)위$", lv)
    if m: LGPTS[(m.group(1), m.group(2))][int(m.group(3))] = e
def interp(pts, r):
    if r in pts: return pts[r]
    lo = [k for k in pts if k < r]; hi = [k for k in pts if k > r]
    if not lo or not hi: return None
    a, b = max(lo), min(hi)
    return round(pts[a] + (pts[b] - pts[a]) * (r - a) / (b - a))

def rank_model(lg, season, r, n):
    if lg == "BRA1": return round(1598 + 63 * curve(r, n)), f"브라질 세리에 A {season} {r}위"
    if lg == "BRA2": return round(1370 + SD2 * curve(r, n)), f"브라질 세리에 B {season} {r}위"
    if lg in ("GB2", "GB3"):
        nm = {"GB2": "챔피언십", "GB3": "리그 원"}[lg]
        v = interp(LGPTS.get((nm, season), {}), r)
        if v: return v, f"{nm} {season} {r}위"
    return None

def table_candidates(cid, d):
    y = d[:4]
    if cid in SOUTH: return [("BRA1", y), ("BRA2", y)]
    s = eu(d)
    return [("GB2", s), ("GB3", s)]

# 같은 경기 다른 선수 자료(동료·상대 선수) — 같은 날짜·상대 이름 토큰 겹침
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "luc.js") or b in NEW_PREFIXES: continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting", "esporte", "ec", "foot", "ball", "porto", "regatas", "atletico", "clube", "associacao"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    vals = {(x[2], x[12]) for b, x in cand}
    return cand, vals

# 순위표·기존 자료에 없는 상대(직접 추정, 모두 '추정') — 아래 판정 표
C4 = "브라질 4부 이하 (추정)"
MAN = {
    ("Treze FC", "2011"): (1200, C4),                      # 2011 세리에 D
    ("EC Santo André", "2011"): (1253, "브라질 세리에 C (추정)"),   # 2010 세리에 B 18위 강등 → 2011 세리에 C
    ("Mirassol Futebol Clube (SP)", "2011"): (1200, C4),
    ("Oeste FC", "2011"): (1200, C4),                      # 2011 세리에 D(2012 세리에 C 우승 팀)
    ("Oeste FC", "2012"): (1253, "브라질 세리에 C (추정)"),
    ("Paulista FC (SP)", "2012"): (1200, C4),
    ("Ituano Futebol Clube (SP)", "2012"): (1200, C4),
    ("EC Santo André", "2024"): (1200, C4),
    ("AA Internacional de Limeira", "2024"): (1200, C4),
    ("Águia de Marabá FC", "2024"): (1200, C4),
    ("EC Primavera", "2026"): (1200, C4),
    ("Club Universidad de Chile", "2012"): (1550, "칠레 1위권, 2011 수다메리카나 우승 (추정)"),   # 네이마르 자료 2012.9.26 헤코파 값·문구 그대로
    ("Club Atlético Tigre", "2012"): (round(1583 + 63 * curve(2, 20)), "아르헨티나 1부 클라우수라 2012 2위 (추정, 결승 때 대회인 2012 이니시알 순위표가 없어 같은 해 클라우수라 순위)"),
    ("LDU Quito", "2023"): (1480, "에콰도르 1부 2023 우승 팀 (추정, 다른 선수 자료의 에콰도르 우승 팀 값과 같음)"),
    ("CA Talleres", "2024"): (round(1583 + 63 * curve(2, 28)), "아르헨티나 1부 2024 리가 2위/28팀"),
    ("US Avranches", "2016-17"): (1350, "프랑스 3부(나시오날) 2016-17 (추정, 다른 선수 자료의 같은 시즌 3부 팀 값과 같음)"),
    ("Marine FC", "2020-21"): (1100, "잉글랜드 8부(노던 프리미어리그 디비전 1) (추정, 다른 선수 자료의 잉글랜드 7부 값과 같은 수준)"),
}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand}))
        return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    seasons = [d[:4], eu(d)] if cid in SOUTH else [eu(d)]
    k = key(o)
    for s in seasons:
        if (k, s) in TABLE:
            e, lv = TABLE[(k, s)]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv)
            return e, lv
    for lg, s in table_candidates(cid, d):
        tab = RANKS.get((lg, s), {})
        if k in tab:
            r, n, _ = tab[k]
            res = rank_model(lg, s, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    for s in seasons:
        if (o, s) in MAN:
            e, lv = MAN[(o, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv)
            return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (g["gameState"] == "extra_time" and mi > 90 and ko) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(수정 없음, 보고용)
MATE_NAME = {"ibr.js": "Zlatan Ibrahimović", "cav.js": "Edinson Cavani", "dim.js": "Ángel Di María", "ney.js": "Neymar",
             "mba.js": "Kylian Mbappé", "son.js": "Heung-min Son", "kan.js": "Harry Kane", "bal.js": "Gareth Bale"}
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and "Lucas Moura" in str(x[13]):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (x[5], x[6], x[2], x[12], x[3])
            cross.append(("동료 도움→루카스 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "루카스 골 없음"),
                          x[2:8], hit[0][2:8] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and r[13] == nm:
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (r[5], r[6], r[2], r[12], r[3])
                has_m = any(m[0] == r[9] for m in om)
                cross.append(("루카스 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else ("동료 골 없음" + ("" if has_m else "(출전 행도 없음)"))),
                              r[2:8], hit[0][2:8] if hit else None))
    for r in E:   # 같은 날·같은 상대 Elo·lv·대회
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[12], x[3]), (r[2], r[12], r[3])))
    for m in M:   # 같은 날 같은 상대 출전 행의 대회 코드
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                cross.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[2], m[2]))
# Transfermarkt 리포트상 동료 도움인데 동료 파일에 없는 것(PK 유도 제외)
for gid, evs in EVS.items():
    if gid not in G: continue
    for e in evs:
        if e["scorer_id"] == LM and e["assist_id"] and e["assist_id"] != LM and not e["assist_type"].startswith("Penalty"):
            for b, nm in MATE_NAME.items():
                if e["assist_player"] == nm and b in OTHERS:
                    d = ldate(G[gid]); oe, om = OTHERS[b]
                    has_a = any(x[0] == "a" and x[9] == d and "Lucas" in str(x[13]) for x in oe)
                    if not has_a:
                        cross.append(("Transfermarkt 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"] or "(유형 빈칸)",
                                      "출전 행 있음" if any(m[0] == d for m in om) else "출전 행도 없음"))
DUP = set()
cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 클럽별 합계
CLUBS = [("2013-01-01", "상파울루 1기"), ("2018-01-31", "파리 생제르맹"), ("2023-08-02", "토트넘 홋스퍼"), ("9999-12-31", "상파울루 2기")]
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for _, n in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
POST_A = NA - PRE_A
TM_A_ALL = sum(1 for gid, evs in EVS.items() if gid in G for e in evs if e["assist_id"] == LM)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
sp = [ST["상파울루 1기"][i] + ST["상파울루 2기"][i] for i in range(3)]
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
def jl(reason):
    return ", ".join(f"{d_(j[1])} {j[2]} {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
SAME_N = sum(1 for v in ELO_LOG.values() if v[0] == "same")
FIRST_OPP = {"Atlético Paranaense": "아틀레치쿠 파라나엔시", "Sport Club Corinthians Paulista": "코린치안스"}
SHOT = "슈팅 리바운드('Shot on goal')"
POST_TM_ONLY_ADDED = [t for t, v in POST_GAP.items() if v]

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
NOTE_LINES = [
    f"루카스 모우라(상파울루·파리 생제르맹·토트넘 홋스퍼·상파울루)의 클럽 공식 경기 {NG}경기({d_(first[0])} {FIRST_OPP[first[1]]}전 ~ {d_(last[0])} {FIRST_OPP[last[1]]}전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    f"클럽별 경기·골·도움: 상파울루 {c3(sp)}(2010~2012 {c3(ST['상파울루 1기'])}, 2023~ {c3(ST['상파울루 2기'])}), 파리 생제르맹 {c3(ST['파리 생제르맹'])}, 토트넘 홋스퍼 {c3(ST['토트넘 홋스퍼'])}",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(출전 {NG}경기·{MIN_TOT}분)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음",
    "클럽별 경기·골은 영어 위키백과 경력 표와 같음(PSG 229경기 46골, 토트넘 221·39). 상파울루 2010~2012는 위키백과 128경기, Transfermarkt 127경기로 2012 코파 두 브라질만 1경기 다름(위키 9, Transfermarkt 8). Transfermarkt는 2012.6.20 준결승 2차전 코리치바 원정을 명단 제외로 적고 리포트 출전 명단에도 없어 넣지 않음",
    "FotMob 경력 합계는 PSG 229경기 46골, 토트넘 221·39, 상파울루 2023~ 114·26으로 같고, 상파울루 2010~12는 FotMob 128경기 33골(위키백과와 같은 1경기 차이). FotMob 경기 기록에는 캄페오나투 파울리스타 2011~2012 일정과 2010~2013 득점자 이름이 대부분 없어 이 구간 골은 Transfermarkt 리포트만 씀",
    "토트넘 U21(프리미어리그 2, 2023년 4경기 3골), 브라질 대표팀·올림픽 대표팀·U20 경기는 뺌. 2024.2.4 수페르코파 두 브라질은 부상으로 결장(Transfermarkt)",
    f"PK 골 {NPK}개는 Transfermarkt 골 유형 기준(FotMob과 같음)",
    "2011.8.24 수다메리카나 세아라전(2차전) 골 순서: Transfermarkt 리포트는 루카스 62분 골을 첫 골(1-0)로, 시세루·다고베르투의 65분 두 골을 모두 3-0으로 적음. FotMob(시세루 56분, 루카스 61분, 다고베르투 64분)과 worldfootball(시세루 56분 1-0, 루카스 62분 2-0)을 따라 루카스 골 직전 1-0, 다고베르투 골(루카스 도움) 직전 2-0으로 씀",
    "2012.10.31 수다메리카나 8강 1차전 우니베르시다드 데 칠레 원정은 Transfermarkt 리포트 머리 스코어가 2:0으로 홈·원정이 뒤집혀 있어 골 목록·선수 경기 성적(상파울루 2-0 승)을 쓰고, 2차전의 1차전 스코어도 2-0으로 고침. 2012.11.22 우니베르시다드 카톨리카 원정(1-1)도 리포트 머리 스코어(3:4)가 틀렸으나 골·도움이 없어 영향 없음",
    "2014.12.17 쿠프 드 라 리그 아작시오전 84분 골은 FotMob이 루카스 골로 적었으나 Transfermarkt·Sports Mole·ESPN·maxifoot이 바에벡 골(루카스 도움)로 적어 도움으로 셈",
    "2012.12.12 수다메리카나 결승 2차전 티그레전은 하프타임에 티그레가 경기장에 나오지 않아 전반만 치르고 끝남(2-0 그대로 우승). 출전 45분, 골(23분)·도움(28분)은 경기 중 스코어 그대로 씀",
    f"도움은 2014.8.1 이전은 Transfermarkt 리포트 도움을 쓰고, 그 뒤는 Transfermarkt와 FotMob(경기 기록 또는 선수 경기 목록)이 같이 적은 도움을 기준으로 함",
    f"도움 {NA}개 = Transfermarkt 리포트 도움 {TM_A_ALL}개 − PK 유도 {EX['PK 유도']}개 − 본인 PK 골에 본인 도움으로 적힌 {EX['본인 PK 골에 본인 도움(PK 유도)']}개 − 'Shot on goal' 리바운드 {EX[SHOT]}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 + FotMob에만 있던 1개",
    "PK 유도로 뺀 도움: " + jl("PK 유도"),
    "본인 PK 골의 본인 도움으로 뺀 것: " + jl("본인 PK 골에 본인 도움(PK 유도)"),
    "리바운드·자책골이라 뺀 것: " + jl(SHOT) + " (슈팅 리바운드), " + jl("상대 자책골 유도") + " (상대 자책골)",
    "2014.8 이후 FotMob 경기 기록에 도움이 없지만 다른 출처 2곳으로 확인해 넣은 도움: 2014.12.17 아작시오전 54분 카바니·84분 바에벡(maxifoot·CulturePSG·Bleacher Report), 2015.1.13 생테티엔전 72분 즐라탄(CulturePSG·maxifoot), 2016.2.10 리옹전 62분 즐라탄(FourFourTwo·Bleacher Report), 2017.1.7 바스티아전 30분 치아구 실바(FourFourTwo·CulturePSG)",
    "상파울루 2024~2025 파울리스타 도움 5개(2024.1.20 산투 안드레 39분 루시아누, 2.28 리메이라 45+3분 페헤이리냐, 3.3 파우메이라스 25분 알리송, 3.17 노보리존치누 23분 페헤이리냐, 2025.3.3 노보리존치누 63분 칼레리)는 FotMob 경기 기록에 도움 칸이 없고 FotMob 선수 경기 목록이 도움 1로 적어 Transfermarkt와 함께 셈",
    "FotMob에만 있던 2015.12.8 챔스 샤흐타르전 86분 즐라탄 골 도움(골키퍼 킥을 루카스가 머리로 떨굼)은 Sports Mole 문자중계·AP 기사가 확인해 넣음(Transfermarkt 리포트는 도움 없음)",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처이고 다른 출처로 대조하지 못함(FotMob 경기 기록에 2010~13 도움이 거의 없음). 유형 칸이 빈 도움(상파울루 2011~2012 7개, 2013.8.3 트로페 데 샹피옹 알렉스 90+3분)도 도움으로 셈",
    "날짜는 경기 현지 날짜. 상파울루 경기는 Transfermarkt 경기 시각(UTC)을 상파울루 시간으로 바꾼 날짜라 저녁 경기 68경기는 Transfermarkt 리포트 날짜(중부 유럽 기준)보다 하루 앞",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(즐라탄·카바니·디 마리아·음바페·네이마르·손흥민·케인·베일) 값을 먼저 쓰고({SAME_N}개 기록), 없으면 기존 선수 자료의 같은 팀·같은 시즌 값, 그다음 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 모형에 넣음",
    "브라질 세리에 A·B는 달력 연도 순위(평균 1598·1370, 네이마르·비니시우스 자료와 같은 방식). 2026 세리에 A·B는 2026.11.11 현재 순위. 파울리스타·코파 두 브라질 상대 중 세리에 A·B 밖 팀은 그해 세리에 C면 1253, 세리에 D 이하면 1200(네이마르 자료 방식, 세리에 C·D 소속은 위키백과 시즌 문서 기준)",
    "챔피언십 2019-20 미들즈브러(17위)는 다른 선수 자료의 같은 시즌 앞뒤 순위값 사이로 메움",
    "리그 표가 없는 상대는 당시 수준을 추정함(모두 '추정'): " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED if e not in (1200, 1253)) + ", 브라질 세리에 C 1253·4부 이하 1200 팀: " + ", ".join(sorted({o for o, e, lv in MAN_USED if e in (1200, 1253)})),
    "캄페오나투 파울리스타(상파울루 주 선수권)는 리그 단계·8강·준결승 모두 국내컵 하위 라운드 비중(네이마르 자료와 같음)이고 8강·준결승은 단판 토너먼트로 셈. 코파 두 브라질은 16강까지·8강·준결승·결승으로 나눔(원정 2골 차 이상 승리로 2차전이 없던 2011 1라운드 트레제전·2012 2라운드 바이아 지 페이라전은 단판)",
    "코파 수다메리카나는 16강까지·8강·준결승·결승, 코파 리베르타도레스는 조별·16강과 8강으로 나눠 계산함. 트로페 데 샹피옹은 국내컵 결승, 쿠프 드 프랑스·쿠프 드 라 리그·FA컵·리그컵은 16강까지·8강(FA컵 6라운드·리그컵 5라운드)·준결승·결승, 유로파 32강('intermediate stage')은 토너먼트로 계산함",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회는 2020-21까지 원정 다득점·연장 적용, 코파 두 브라질 2011~2012와 수다메리카나 2011~2012(결승 제외)는 원정 다득점 있고 연장 없이 승부차기(2012 수다메리카나 준결승 우니베르시다드 카톨리카전 1-1·0-0은 원정 다득점으로 진출), 수다메리카나 결승은 원정 다득점 없이 연장, 코파 두 브라질 2023~2024와 수다메리카나 2023은 둘 다 없이 승부차기",
    "못 뛴 다른 차전 스코어를 리포트로 채움: 2011.8 수다메리카나 2라운드 1차전 세아라 2-1 상파울루, 2023.7 코파 두 브라질 준결승 1차전 코린치안스 2-1 상파울루(루카스 입단 전), 2024.5 코파 두 브라질 3라운드 1차전 아기아 지 마라바 1-3 상파울루",
    "시즌은 상파울루는 달력 연도, PSG·토트넘은 8월 1일 기준(즐라탄·디 마리아·손흥민·케인 자료와 같음)",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 대표팀(컨페더레이션스컵 2013·남미 U20 2011)·유스(코파 상파울루 주니오르스 2010) 우승은 뺌. 2017-18 리그1·쿠프 드 라 리그·트로페 데 샹피옹(시즌 중 이적)과 2024 수페르코파 두 브라질(부상 결장)은 Transfermarkt대로 셈",
    f"2026.11.11 기준: 마지막 출전은 2026.11.4 세리에 A 코린치안스전(상파울루와 계약 2026.12.31까지, Transfermarkt)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "csa", "lib", "TM "]:
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
    if mdates[d] > 1: problems.append(("같은 날 두 경기", d))
mmin = {m[0]: m[3] for m in M}
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if MISS: sys.exit("상대 Elo 없음: " + str(MISS))
js = f"const LUC_E={J(E)};\nconst LUC_M={J(M)};\nconst LUC_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg,
           "post_gap_tm_only": post_gap_tm_only, "post_gap_verdicts": POST_GAP, "fm_only_assists": FM_ONLY,
           "fm_only_goals": FM_ONLY_GOAL, "cross_check": cross, "elo_sources": ELO_SRC,
           "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if len(c) > 4 and c[4] != "일치": print("  대조:", c)
