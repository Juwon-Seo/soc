#!/usr/bin/env python3
"""지오바니 엘베르 (Giovane Élber, Transfermarkt 198): raw/ -> elber.json + src/data/elb.js (판정 근거는 judgments.md)

  python3 players/elber/build_elber.py            # 파일 쓰기
  python3 players/elber/build_elber.py --debug    # Elo 출처 로그만
  python3 players/elber/build_elber.py --stat     # 요약·동료 대조
  python3 players/elber/build_elber.py --ties     # 합산 행

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/ranks.txt(Transfermarkt 순위표), 스위스 1991-94 공식 순위는 raw/rsssf/zwit92~94.html(아래 SWISS 표에 옮김),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조),
      players/*/staged/*.js(병렬 판정 중인 자료: 대조만).
환경 변수 ELB_ROOT: 저장소 뿌리(스크래치 복사본에서 돌릴 때).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("ELB_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "elb.js")
OUT_JSON = os.path.join(HERE, "elber.json")
ME = "198"
ME_KO = "지오바니 엘베르"
ME_RE = r"^Giovane [ÉE]lber$|^[ÉE]lber$"

def rd(n, base=RAW):
    with open(os.path.join(base, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# 2001 인터콘티넨털컵(도쿄): 현지 날짜 2001.11.27(영어 위키백과·JFA 경기 보고서; 피사로 자료와 같음). TM 리포트·API는 11.28
DATE_FIX = {"1169665": "2001-11-27"}
def ldate(g):
    # 유럽: Transfermarkt 리포트 날짜(= 현지 날짜; API UTC가 하루 앞선 38경기는 리포트 날짜를 씀),
    # 크루제이루: API UTC를 상파울루 시간으로 바꾼 날짜(리포트 날짜가 하루 늦은 5경기는 이 날짜) — 원자료 date_local
    return DATE_FIX.get(g["gameId"], g["date_local"])
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 판정 표
# 2000.4.1 볼프스부르크전(18390): TM 선발·출전 0분·0분 퇴장(리포트 카드 칸 '퇴장, 폭력 행위', 시각 없음) → 출전 1경기·0분
MIN_FIX = {}
MIN_EST = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"C1", "CHAA", "L1", "FR1", "BRA1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"   # 스위스 승강 리그(CHAA)도 리그 비중(분데스리가·세리에A 승강 플레이오프·벨기에 PO2 선례)
    if cid in ("SCC", "DFB", "FRC", "FRL", "BRC"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "LPO":                       # DFL-리가포칼: 첫 경기(intermediate stage) 8강, 준결승, 결승(발라크·클로제·제 호베르투 선례)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        return "dk"
    if cid in ("USC", "FRCH"): return "df"  # 슈퍼컵류 = 국내컵 결승
    if cid == "WEPO": return "cwc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "CLQ": return "clq"
    if cid in ("UI", "ITC"): return "elq"  # 인터토토(옛 대회 포함) 조별 = 유로파 예선(네드베드 ITC 선례)
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
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

def tie_rule(cid, d, rnd):
    if cid in ("UEFA", "CL", "CLQ"): return (1, 1)
    if cid == "BRC": return (1, 0)      # 코파 두 브라질(결승 제외): 원정 다득점, 연장 없음
    if cid == "CS": return (1, 0)
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
    sc = re.match(r"(\d+):(\d+)", m["other_leg_score"])
    oh, oa = int(sc.group(1)), int(sc.group(2))
    return (oh, oa) if s == "h" else (oa, oh)   # 다른 차전은 홈·원정이 바뀜: 이 경기 홈이면 그 경기 원정

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
    if e["goal_desc"] == "Penalty": return "PK 골(유형 칸 없음, 도움 아님)"
    return None

BEFORE_FIX = {}
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
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
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
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

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
MANUAL_ALIAS = {"inter milan": "inter", "olympique lyon": "olympique lyonnais"}
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
    if b in ("hon.js", "elb.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
STAGED = {}
for fn in sorted(glob.glob(os.path.join("/home/user/soc", "players", "*", "staged", "*.js"))):
    try:
        P, oe, om = load_js(fn); STAGED["staged/" + os.path.basename(fn)] = (oe, om)
    except Exception: pass
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "milan", "inter", "madrid", "moscow", "moskau", "paulista", "paulo", "ca", "cs", "deportivo", "deportes", "universidad", "san", "santa",
        "borussia", "bayer", "vfl", "vfb", "tsv", "fsv", "munich", "munchen", "hamburger", "eintracht", "werder", "bsc", "hertha", "rb"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
SOUTH = {"BRA1", "BRC", "CS"}
def same_match(o, d, cid):
    if cid in SOUTH:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    else:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
def load_ranks(fn, only=None):
    with open(fn, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("|")
            if len(p) < 5 or p[0] == "league": continue
            lg, s = p[0], p[1].split(" ")[0]
            if only and lg not in only: continue
            RANKS[(lg, s)][key(p[4])] = (int(p[2]), int(p[3]), p[4])
load_ranks(os.path.join(RAW, "ranks.txt"), only={"L1", "L2", "BRA1"})

# 스위스 나치오날리가 A 1991-92~1993-94 공식 최종 순위(RSSSF zwit92~94: 결승 라운드 8팀 1~8위, 승강 라운드로 간 4팀은 예선 순서 9~12위).
#   Transfermarkt C1 표는 예선+결승 라운드 승점을 단순 합산한 순서라 1991-92·1992-93이 공식 순위와 다름(예: 1992-93 그라스호퍼 TM 8위 → 공식 9위).
SWISS = {
    "1991-92": ["FC Sion", "Neuchâtel Xamax", "Grasshopper Club Zurich", "BSC Young Boys", "Servette FC", "FC Lausanne-Sport", "FC Zürich", "FC St. Gallen 1879",
                "FC Luzern", "FC Lugano", "FC Aarau", "FC Wettingen"],
    "1992-93": ["FC Aarau", "BSC Young Boys", "Servette FC", "FC Lugano", "FC Zürich", "FC Sion", "Neuchâtel Xamax", "FC Lausanne-Sport",
                "Grasshopper Club Zurich", "FC St. Gallen 1879", "FC Chiasso", "FC Bulle"],
    "1993-94": ["Servette FC", "Grasshopper Club Zurich", "FC Sion", "FC Aarau", "FC Lugano", "BSC Young Boys", "FC Lausanne-Sport", "FC Luzern",
                "FC Zürich", "Neuchâtel Xamax", "Yverdon Sport FC", "SC Kriens"],
}
# 스위스 1부 순위값: 기존 자료의 스위스 순위별 값(1위 1600 그라스호퍼 1995-96, 2위 1600 바젤 2002-03·2005-06·2006-07, 3위 1520 로잔 1998-99,
#   4위 1507·5위 1461·6위 1430·7위 1406·8위 1382·9위 1342·10위 1306 = 슈퍼리그 2012-13 순위값), 11·12위는 기존 값 없음 → 10위 아래로 직접 추정(2부 1250보다 높게)
SW_RANK = {1: 1600, 2: 1600, 3: 1520, 4: 1507, 5: 1461, 6: 1430, 7: 1406, 8: 1382, 9: 1342, 10: 1306, 11: 1280, 12: 1260}
SW_EXIST = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}

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
INTERP_USED = set()
BL_FIXED = None
L2_FIXED = {1: 1697, 2: 1667, 3: 1636, 4: 1622, 5: 1615, 6: 1609, 7: 1600, 8: 1592, 9: 1584, 10: 1579, 11: 1574, 12: 1570,
            13: 1566, 14: 1561, 15: 1544, 16: 1545, 17: 1541, 18: 1532}

def rank_model(lg, season, r, n):
    global BL_FIXED
    if lg == "BRA1":
        m = ents_map("브라질 세리에 A", season)
        if r in m: return m[r], f"브라질 세리에 A {season} {r}위"
        return half_up(1598 + 63 * curve(r, n)), f"브라질 세리에 A {season} {r}위"
    if lg == "L1":   # 분데스리가 1993-94~2006-07: 기존 자료가 모든 시즌에 같은 순위값(2000-01 표 1~18위)
        if BL_FIXED is None: BL_FIXED = ents_map("분데스리가", "2000-01")
        m = ents_map("분데스리가", season)
        v = m.get(r, BL_FIXED[r])
        if v != BL_FIXED[r]: sys.exit("분데스리가 순위값 다름 %s %s" % (season, r))
        return v, f"분데스리가 {season} {r}위"
    if lg == "L2":   # 2. 분데스리가: 기존 자료 시즌별 순위값이 거의 한 표(가장 많이 쓴 값)
        m = ents_map("2. 분데스리가", season)
        v = m.get(r, L2_FIXED[r])
        return v, f"2. 분데스리가 {season} {r}위"
    return None

def jul1(d):
    y = int(d[:4]); s = y if d[5:] >= "07-01" else y - 1
    return f"{s}-{str(s + 1)[2:]}"
def jul10(d):
    y = int(d[:4]); s = y if d[5:] >= "07-10" else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 순위표·기존 자료에 없는 상대(직접 추정, 모두 lv에 '추정') — judgments.md 6절
MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
SW2 = "다른 선수 자료 스위스 2부 1250과 같음"
for o in ["FC Basel 1893", "SR Delémont", "CS Chênois", "FC Locarno", "FC Wil 1900"]:
    man(o, "1992-93", 1250, f"스위스 2부(나치오날리가 B) 1992-93 (추정, 승강 라운드 상대; {SW2})")
man("FC Baden 1897", "1993-94", 1250, f"스위스 2부(나치오날리가 B) 1993-94 (추정; {SW2})")
man("FC Schaffhausen", "1993-94", 1250, f"스위스 2부(나치오날리가 B) 1993-94 1위 (추정; {SW2})")
man("Sporting CP", "1992-93", 1730, "포르투갈 1부 1992-93 3위")   # TM PO1 1992-93 표(우승 포르투 확인) 3위, 기존 18팀 시즌 3위 값 1730(벤피카 1994-95·1998-99)
DE3 = "다른 선수 자료 독일 3부 1450과 같음"
man("SV Sandhausen", "1995-96", 1450, f"독일 3부(레기오날리가 쥐트) 1995-96 16위 (추정, {DE3})")
man("FC Energie Cottbus", "1996-97", 1450, f"독일 3부(레기오날리가 북동부) 1996-97 1위 (추정, {DE3})")
man("SV Meppen", "1999-00", 1450, f"독일 3부(레기오날리가 북부) 1999-00 11위 (추정, {DE3})")
man("DJK Waldberg", "1997-98", 1180, "독일 5부(란데스리가 바이에른 북부) 1997-98 4위 (추정, 다른 선수 자료 독일 5부 1180과 같음)")   # 영어 위키백과 DJK Waldberg
man("Cliftonville FC", "1995-96", 1250, "북아일랜드 1995-96 6위/8팀 (추정, 다른 선수 자료 아일랜드 상위 팀 1300보다 낮게)")   # 영어 위키백과 1995–96 Irish League(TM 표는 순서가 틀림: 우승 포르타다운이 12위)
man("IFK Göteborg", "1997", 1542, "스웨덴 1997 2위 (추정, 다른 선수 자료 스웨덴 1위 1555·3위 1529의 가운데)")   # 영어 위키백과 1997 Allsvenskan
man("FK Obilic", "1998-99", 1500, "유고슬라비아 1998-99 (추정, 1997-98 우승 팀; 다른 선수 자료 유고슬라비아 상위 팀 츠르베나 즈베즈다 1500과 같음)")
man("Rosenborg BK", "2000", 1530, "노르웨이 2000 1위 (추정, 다른 선수 자료의 로센보리 2001·2002 1530과 같음)")   # TM NO1 2000 표 1위
C4 = "다른 선수 자료 4부 이하 1200과 같음"
man("Nacional FC", "2006", 1200, f"브라질 4부 이하 2006 (추정, 아마조나스 주 리그 팀, 세리에 A~C 참가 팀 아님; {C4})")   # 영어 위키백과 2006 세리에 C 참가표(아마조나스는 패스트 클루브·히우 네그루)
man("Esporte Clube Vitória", "2006", 1253, "브라질 세리에 C 2006 (추정, 세리에 C 참가·승격 팀; 다른 선수 자료 세리에 C 1253과 같음)")

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid, rnd=""):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o); y = d[:4]
    if cid in SOUTH: seasons = [y]
    elif cid in ("C1", "CHAA", "SCC", "ITC"): seasons = [jul1(d)]
    elif cid in ("L1", "DFB", "LPO"): seasons = [jul10(d)]
    elif cid in ("CL", "CLQ", "UEFA", "UI", "USC", "WEPO"): seasons = [jul10(d), y, str(int(y) - 1)] if int(d[5:7]) < 7 else [jul10(d), y]
    else: seasons = [jul10(d)]
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    if cid in ("C1", "CHAA", "SCC"):
        s = jul1(d)
        for i, t in enumerate(SWISS.get(s, [])):
            if key(t) == k:
                r = i + 1; v = SW_RANK[r]
                lv = f"스위스 {s} {r}위 (추정, 다른 선수 자료의 스위스 {r}위 값과 같음)" if r in SW_EXIST else f"스위스 {s} {r}위 (추정, 순위값 없음 — 10위 1306 아래로 직접 추정)"
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("swiss", v, lv); return v, lv
    if cid in SOUTH: lgs = [("BRA1", y)]
    else: lgs = [("L1", jul10(d)), ("L2", jul10(d))]
    for lg, s in lgs:
        t = RANKS.get((lg, s), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], lg); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

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
    print("보간", sorted(INTERP_USED))
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14 or r[7] or r[10] or r[4] > 90: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], "ko", r[7], "et", r[10], r[11], r[14] if len(r) > 14 else "")
    print("score mismatches", SCORE_MISMATCH)
    print(len(E), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E))
    for j in judg: print(j)
    sys.exit(0)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None): d.append("단판/합산 %s/%s" % (a[14] if len(a) > 14 else a[7], b[14] if len(b) > 14 else b[7]))
    if a[10] != b[10]: d.append("연장")
    return d
CROSS = []
ALLO = dict(OTHERS); ALLO.update(STAGED)
def same_team(x, r): return key(x[1]) == key(r[1]) or bool(toks(x[1]) & toks(r[1]))
for b, (oe, om) in ALLO.items():
    for x in oe:
        if x[0] == "a" and re.match(ME_RE, x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(엘베르 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x, r)]
            if hit: CROSS.append(("엘베르 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x, r)]
            for x in hit:
                if not re.match(ME_RE, x[13] or ""): CROSS.append(("타인 도움 표기 다름(엘베르 골)", b, r[9], r[4], x[13]))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x, r):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판", "연장"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm, m) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
    mdates = {(m[0], key(m[1])) for m in M}
    for mm in om:
        for dd in (-1, 1):
            try: d2 = (datetime.date.fromisoformat(mm[0]) + datetime.timedelta(days=dd)).isoformat()
            except Exception: continue
            if (d2, key(mm[1])) in mdates and (mm[0], key(mm[1])) not in mdates and "1991" <= mm[0][:4] <= "2006":
                CROSS.append(("같은 상대 출전 날짜 하루 차이", b, mm[0], d2, mm[1]))
for b, (oe, om) in ALLO.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and (key(x[1]) == key(j[2]) or toks(x[1]) & toks(j[2])):
                    CROSS.append(("TM 엘베르 도움을 규칙대로 뺀 타인 골", b, x[9], x[4], j[5], x[13]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("gcel", "1994-07-01", "그라스호퍼", "1991~1994"), ("vfbel", "1997-07-01", "VfB 슈투트가르트", "1994~1997"),
         ("bayel", "2003-08-30", "바이에른 뮌헨", "1997~2003"), ("lyoel", "2005-01-30", "올랭피크 리옹", "2003~2005"),
         ("bmgel", "2006-01-01", "보루시아 묀헨글라트바흐", "2005"), ("cruel", None, "크루제이루", "2006")]
TM_CLUB = {"504": "gcel", "79": "vfbel", "27": "bayel", "1041": "lyoel", "18": "bmgel", "609": "cruel"}
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
CAL = {"cruel"}; JUL10 = {"bayel", "lyoel"}; JUL1 = {"gcel", "vfbel"}
def season_of(d, club):
    y = int(d[:4])
    if club in CAL: return str(y)
    if club in JUL10: return jul10(d)
    if club in JUL1: return jul1(d)
    s = y if int(d[5:7]) >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    for c in CROSS: print(c)
    print(sorted(collections.Counter(season_of(m[0], club_of(m[0])) for m in M).items()))
    for j in judg: print(j)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_elber.py"), encoding="utf-8").read())

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
Gstart = {ldate(g): g["isStarting"] in ("1", "True") for g in GAMES}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > m[3] + 3 and not r[10] and Gstart[r[9]]: problems.append(("출전 분보다 늦은 기록", r, m))
for m in M:
    if not (0 < m[3] <= 125) and m[0] != "2000-04-01": problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const ELB_E={J(E)};\nconst ELB_M={J(M)};\nconst ELB_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "elo_sources": ELO_SRC, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
