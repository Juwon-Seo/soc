#!/usr/bin/env python3
"""프레디 융베리 (Transfermarkt 3134): raw/ -> ljungberg.json + src/data/lju.js (판정 근거는 judgments.md)

  python3 players/ljungberg/build_ljungberg.py            # 파일 쓰기
  python3 players/ljungberg/build_ljungberg.py --debug    # Elo 출처 로그만 출력
  python3 players/ljungberg/build_ljungberg.py --stat     # 요약·동료 대조·시즌별
  python3 players/ljungberg/build_ljungberg.py --ties     # 합산 행·판정 목록 출력

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/ranks.txt(Transfermarkt 순위표), elo/opponent_elo_by_team_season.csv + aliases.csv,
      src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기 대조), raw/fotmob_events.csv(2010-07 이후 대조), raw/wiki_career.csv.
피레스(players/pires/build_pires.py) 구조를 따름.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "lju.js")
OUT_JSON = os.path.join(HERE, "ljungberg.json")
ME = "3134"
ME_KO = "프레디 융베리"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

def ldate(g): return g["date_local"]     # 리포트 현지 날짜(MLS는 경기장 시간대), 리포트 없는 리그 경기는 TM 일정 날짜
def opp(g):
    return re.sub(r"\s*\(\s*(?:-\s*\d{4}|\d{4}\s*-\s*\d{4})\s*\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 판정 표
MIN_FIX, MIN_EST = {}, {}       # 출전 분은 Transfermarkt 그대로
BEFORE_FIX = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "MLS1", "SC1", "JAP1", "IND1"}
CUPS = {"FAC", "CGB", "SFA", "JEMP", "JAPC", "MLSP"}     # MLSP = Transfermarkt 'US Open Cup'(대회 이름 확인)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth"): return "dk"      # FA컵 6라운드 = 8강, 리그컵·일왕배 8강
        return "dc"
    if cid == "GBCS": return "df"                                            # 커뮤니티 실드 = 국내컵 결승 비중
    if cid == "POUS": return "mlp"                                           # Transfermarkt 'MLS Cup Playoffs' 콘퍼런스 준결승
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"                               # 1999-00·2000-01·2001-02 2차 조별 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid in ("UI", "UEQ"): return "elq"                                    # 인터토토(결승 포함)·UEFA컵 예선 = 유로파 예선
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"                        # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                                         # 3라운드·16강·8강
    if cid == "EPP":                                                         # 컵위너스컵: 호나우두·피구 선례(유로파 비중)
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("UEFA", "UEQ", "CL", "CLQ", "UI", "EPP"): return (1, 1)   # UEFA 대회 2020-21까지
    if cid == "CGB": return (1, 1)                                     # 잉글랜드 리그컵 준결승 2017-18까지
    if cid == "POUS": return (0, 1)                                    # MLS 플레이오프 두 경기: 앙리 선례(원정 다득점은 2014년부터)
    if cid == "JAPC": return (1, 1)                                    # J리그컵 두 경기(기록 없음, 출전만)
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
    oh, oa = map(int, m["other_leg_score"].split(":"))     # 이 경기 홈 팀 기준 표기
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
        if e["scorer_id"] == ME and is_og(e): judg.append(("본인 자책골(골 아님)", ldate(g), opp(g), e["minute"]))
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

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
NPK_API = sum(int(g["penGoals"] or 0) for g in GAMES)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
for gid in G:
    if gid in MI and gid not in EVS and MI[gid].get("final") not in (None, "", "0:0") and G[gid]["gameState"] != "penalty_shootout":
        SCORE_MISMATCH.append((gid, ldate(G[gid]), (0, 0), MI[gid]["final"]))
GA_GAMES = {r[1] for r in raw_rows}
SM_GA = [x for x in SCORE_MISMATCH if x[0] in GA_GAMES]
if SM_GA: sys.exit("골·도움 경기 리포트 불완전 " + str(SM_GA))

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
MANUAL_ALIAS = {"chicago fire": "chicago fire fc", "cd chivas usa": "cd chivas usa"}
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
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "foot", "ball",
        "atletico", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss", "olympique", "milan", "inter", "madrid", "fk", "if",
        "deportivo", "san", "santa", "saint", "us", "ogc", "losc", "stade", "racing", "athletic", "girondins", "germain", "paris",
        "manchester", "west", "sheffield", "bristol", "rovers", "wanderers", "town", "hotspur", "albion", "county", "vfl", "vfb",
        "sad", "cp", "rc", "aj", "hsc", "ea", "sm", "ssc", "afc", "sk", "nk", "gnk", "kv", "kaa", "rsc", "bsc", "psv", "new"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
# 내가 뛴 클럽 이름(상대 쪽 자료의 '상대'가 융베리 팀인 행은 같은 경기 Elo 후보에서 뺌)
MYCLUB = {"1011": "halmstad", "11": "arsenal", "379": "west ham", "9636": "seattle", "432": "chicago", "371": "celtic",
          "1062": "shimizu", "45274": "mumbai"}
def same_match(o, d, club_id):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o)) and MYCLUB[club_id] not in norm(x[1])]
    return cand, collections.Counter((x[2], x[12]) for b, x in cand)

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        s = p[1]
        if re.match(r"^\d\d/\d\d$", s):                     # 97/98 -> 1997-98
            y = int(s[:2]); y = 1900 + y if y > 50 else 2000 + y
            s = f"{y}-{s[3:]}"
        RANKS[(p[0], s)][key(p[4])] = (int(p[2]), int(p[3]), p[4])

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
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
LGNAME = {"FR1": "리그1", "GB1": "프리미어리그"}
# 기존 자료가 시즌마다 같은 순위값 사다리를 쓰는 리그: 그 시즌 값 → 사다리 같은 순위 값
LADDER_LG = {"GB2": ("잉글랜드 2부", r"^(?:챔피언십(?:\((?:잉글랜드 )?2부\))?|잉글랜드 2부) (\d{4}-\d{2}) (\d+)위$"),
             "JAP1": ("J1리그", r"^J1리그 (\d{4}) (\d+)위$")}
def ladder(lg):
    pat = re.compile(LADDER_LG[lg][1]); bys = collections.defaultdict(dict); allr = collections.defaultdict(collections.Counter)
    for e in ENTS:
        m = pat.match(e[12] or "")
        if m: bys[m.group(1)][int(m.group(2))] = e[2]; allr[int(m.group(2))][e[2]] += 1
    return bys, {r: c.most_common(1)[0][0] for r, c in allr.items()}

INTERP_USED = set()
def rank_model(lg, season, r, n):
    if lg in LGNAME:
        m = ents_map(LGNAME[lg], season)
        if not m: return None
        v, it = mid(m, r)
        if v is None: return None
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"{LGNAME[lg]} {season} {r}위"
    if lg in LADDER_LG:
        bys, lad = ladder(lg); m = bys.get(season, {})
        if r in m: return m[r], f"{LADDER_LG[lg][0]} {season} {r}위"
        cand = collections.Counter(t[r] for s2, t in bys.items() if s2 != season and r in t and len(t) >= 3 and all(t[k] == v for k, v in m.items() if k in t))
        if cand:
            v = cand.most_common(1)[0][0]; INTERP_USED.add((lg, season, r, v, "사다리")); return v, f"{LADDER_LG[lg][0]} {season} {r}위"
        v, it = mid(m, r)
        if v is None: return None
        INTERP_USED.add((lg, season, r, v)); return v, f"{LADDER_LG[lg][0]} {season} {r}위"
    if lg == "MLS1":   # 기존 MLS 순위값과 같은 식(평균 1581, 흩어짐 58; 베컴 자료) — 그 시즌 기존 값이 있으면 그 값
        m = ents_map("MLS", season)
        if r in m: return m[r], f"MLS {season} {r}위"
        v = half_up(1581 + 58 * curve(r, n)); INTERP_USED.add((lg, season, r, v, "모형"))
        return v, f"MLS {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
CAL_OPP = {"Turun Palloseura", "Rosenborg BK"}          # 달력 연도 리그 상대(핀란드·노르웨이)
def season_key(d, cid, o):
    if cid in ("MLS1", "MLSP", "POUS", "JAP1", "JAPC", "JEMP", "IND1") or o in CAL_OPP: return d[:4]
    return eu(d)

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; SAME_MULTI = []
def opp_elo(o, d, cid, club_id):
    cand, vals = same_match(o, d, club_id)
    if vals:
        if len(vals) > 1: SAME_MULTI.append((o, d, dict(vals)))
        (e, lv), _ = vals.most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand}), sorted({x[1] for b, x in cand})); return e, lv
    k = key(o)
    s0 = season_key(d, cid, o)
    if (k, s0) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, s0)]).most_common(1)[0]
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s0); return e, lv
    if (k, s0) in MAN:
        e, lv = MAN[(k, s0)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for lg in ("GB1", "FR1", "GB2", "MLS1", "JAP1"):
        t = RANKS.get((lg, s0), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s0, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, s0)); return 0, "?"

# ---------------------------------------------------------------- 직접 추정(모두 lv에 '추정') — judgments.md 7절
MANUAL = [
    ("Turun Palloseura", "1997", 1350, "핀란드 1997 4위 (추정, 다른 선수 자료 핀란드 4위 1350과 같음)"),
]
for o, s, e, lv in MANUAL: man(o, s, e, lv)

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, g["club_id"])
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
    for x in SAME_MULTI: print("같은 경기 값 여럿", x)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    print("보간", sorted(INTERP_USED))
    sys.exit(0)
if __name__ == "__main__" and "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print("score mismatches", SCORE_MISMATCH)
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
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
    if a[7] != b[7] or ((a[14] if len(a) > 14 else 0) or 0) != ((b[14] if len(b) > 14 else 0) or 0): d.append(f"단판/합산 {a[7]}{a[14] if len(a) > 14 else ''}/{b[7]}{b[14] if len(b) > 14 else ''}")
    if a[10] != b[10]: d.append("연장")
    return d
def same_opp(x, r): return key(x[1]) == key(r[1]) or bool(toks(x[1]) & toks(r[1]))
TEAMMATE_FILES = {"hen.js": ["Henry"], "pir.js": ["Pirès", "Pires"], "fab.js": ["Fàbregas", "Fabregas"], "van.js": ["van Persie"]}
def dnum(s): return int(s[:4]) * 400 + int(s[5:7]) * 32 + int(s[8:])
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Ljungberg", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            near = [r for r in E if r[0] == "g" and abs(dnum(r[9]) - dnum(x[9])) <= 3 and abs(r[4] - x[4]) <= 2 and same_opp(x, r)]
            CROSS.append(("타인 도움→융베리 골", b, x[9], x[4], x[1], "없음" + (f" (가까운 날짜 {[r[9] for r in near]})" if near else "") if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_opp(x, r)]
            if hit: CROSS.append(("융베리 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
            elif b in TEAMMATE_FILES and any(n in (r[13] or "") for n in TEAMMATE_FILES[b]):
                near = [x for x in oe if x[0] == "g" and abs(dnum(x[9]) - dnum(r[9])) <= 3 and abs(x[4] - r[4]) <= 2 and same_opp(x, r)]
                CROSS.append(("융베리 도움→타인 골", b, r[9], r[4], r[13], "그 선수 자료에 골 행 없음" + (f" (가까운 날짜 {[x[9] for x in near]})" if near else "")))
    for x in oe:
        mine = [r for r in E if r[9] == x[9] and same_opp(x, r)]
        if mine and b in TEAMMATE_FILES:
            d = [c for c in cmp_rows(mine[0], x) if not c.startswith(("분", "스코어"))]
            if d: CROSS.append(("같은 경기 행 차이", b, x[9], x[1], d))
# 같은 경기를 상대 쪽에서 기록한 다른 선수 자료: 날짜가 같고 그쪽 상대가 융베리 소속 팀인 행
GBYDATE = {ldate(g): g for g in GAMES}
OPPSIDE = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        g = GBYDATE.get(x[9])
        if not g or MYCLUB[g["club_id"]] not in norm(x[1]): continue
        mine = [r for r in E if r[9] == x[9]]
        bad = [r for r in mine if (r[4] < x[4] and (r[5] > x[6] or r[6] > x[5])) or (r[4] > x[4] and (r[5] < x[6] or r[6] < x[5]))]
        OPPSIDE.append((b, x[9], x[0], x[4], f"{x[5]}-{x[6]}", "모순" if bad else ("대조" if mine else "융베리 기록 없는 경기")))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("hallj", "1998-09-12", "할름스타드", "1994~1998"), ("arslj", "2007-07-23", "아스널", "1998~2007"),
         ("whulj", "2008-10-20", "웨스트햄", "2007~2008"), ("sealj", "2010-07-30", "시애틀 사운더스", "2009~2010"),
         ("chilj", "2011-01-01", "시카고 파이어", "2010"), ("cellj", "2011-08-27", "셀틱", "2011"),
         ("shilj", "2014-09-02", "시미즈 S펄스", "2011"), ("mumlj", None, "뭄바이 시티", "2014")]
TM_CLUB = {"1011": "hallj", "11": "arslj", "379": "whulj", "9636": "sealj", "432": "chilj", "371": "cellj", "1062": "shilj", "45274": "mumlj"}
CAL = {"hallj", "sealj", "chilj", "shilj", "mumlj"}
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
if NPK != NPK_API: sys.exit("PK 수 불일치")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({(r[9]) for r in E if len(r) > 14})
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in CAL: return str(y)
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
SEAS = collections.OrderedDict()
for m in M:
    s = season_of(m[0], club_of(m[0])); SEAS.setdefault(s, [0, 0, 0, 0]); SEAS[s][0] += 1; SEAS[s][3] += m[3]
for r in E:
    s = season_of(r[9], club_of(r[9])); SEAS[s][1 if r[0] == "g" else 2] += 1
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    for c in CROSS: print(c)
    for c in OPPSIDE: print("상대 쪽 기록", c)
    for k, v in SEAS.items(): print(k, v)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_ljungberg.py"), encoding="utf-8").read())

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
    ar = sorted(rs, key=lambda r: r[4])
    for a, b in zip(ar, ar[1:]):
        if b[5] < a[5] or b[6] < a[6]: problems.append(("시간순 스코어 역순", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
    if r[4] > 90 and not r[10] and not r[11]: problems.append(("90분 넘는데 표기 없음", r))
mm_ = {m[0]: m for m in M}
Gst = {ldate(g): g for g in GAMES}
for r in E:
    m = mm_.get(r[9]); g = Gst[r[9]]
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if g["isStarting"] in ("1", "True") and r[4] > m[3] + 6 and not (m[3] >= 90): problems.append(("선발 출전 분보다 늦은 기록", r[9], r[4], m[3]))
    if g["isStarting"] not in ("1", "True"):
        end = 120 if g["gameState"] in ("extra_time", "penalty_shootout") else 90
        if r[4] < end - m[3] - 6 and not r[11]: problems.append(("교체 출전 전 기록", r[9], r[4], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const LJU_E={J(E)};\nconst LJU_M={J(M)};\nconst LJU_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS, "opponent_side_rows": OPPSIDE,
               "elo_sources": ELO_SRC, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}, "seasons": SEAS},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
