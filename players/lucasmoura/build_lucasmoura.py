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
        if r.startswith("quarter") or r.startswith("sixth round"): return "dk"   # 리그컵 8강(5라운드)·FA컵 6라운드
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
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting", "esporte", "ec"}
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
