#!/usr/bin/env python3
"""마마두 니앙 (Transfermarkt 6118): raw/ -> niang.json + src/data/nia.js (판정 근거는 judgments.md)

  python3 players/niang/build_niang.py            # 파일 쓰기
  python3 players/niang/build_niang.py --debug    # Elo 출처 로그만 출력
  python3 players/niang/build_niang.py --stat     # 요약·동료 대조·FotMob 대조
  python3 players/niang/build_niang.py --ties     # 합산 행·판정 출력

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv(2010~15 골 대조), raw/ranks.txt(Transfermarkt 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
뼈대는 로텐 build_rothen.py(같은 프랑스 클럽·같은 판정 규칙).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "nia.js")
OUT_JSON = os.path.join(HERE, "niang.json")
ME = "6118"
ME_KO = "마마두 니앙"

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

def ldate(g): return g["date_local_computed"]     # 리포트 날짜가 있는 경기는 리포트 날짜와 모두 같음(raw 점검, 아시아 원정·클럽 월드컵 포함)
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 판정 표
MIN_FIX, MIN_EST = {}, {}       # 출전 분은 Transfermarkt 그대로(빈칸 0경기)
GAP = "2014-08-01"              # 이 날짜 전 도움은 Transfermarkt 리포트 단일 출처 허용(클로제·인시녜·로텐 선례)
# 2014-08-01 뒤 도움 중 Transfermarkt 단일 출처(FotMob 도움 칸 빈칸)이고 다른 출처 2곳으로 확인 못 한 것 → 뺌(judgments.md 5절)
A_DROP = {("2490434", "83"): "2014-08 뒤 Transfermarkt 단일 출처(FotMob 도움 없음, 다른 출처 2곳 확인 못 함)"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "FR2", "TR1", "QSL"}
CUPS = {"FRC", "FRL", "TRP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                                           # 쿠프 드 프랑스 3~6라운드·16강, 쿠프 드 라 리그 2·3라운드·16강, 튀르키예컵 조별
    if cid == "UI": return "elq"                              # 인터토토컵 = 유로파 예선(지단·램파드·지울리·로텐 선례, 준결승·결승 포함)
    if cid in ("UEQ", "ELQ"): return "elq"                    # UEFA컵 예선 2라운드, 유로파 플레이오프
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"           # UEFA컵 1라운드 = 유로파 예선(2009년 전)
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                          # 2·3라운드·32강(intermediate stage)·16강·8강, 유로파 32강(Second Round)
    if cid == "AFCL":
        if r.startswith("quarter"): return "aclk"
        if r.startswith("semi"): return "aclsf"
        if r.startswith("final"): return "aclf"
        return "acl"
    if cid == "KLUB": return "cwc"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0                         # 챔스·UEFA컵 조별, 튀르키예컵 2010-11 조별(리그식)
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("UEFA", "CL", "UI", "UEQ", "CLQ", "EL", "ELQ"): return (1, 1)   # UEFA 대회 2020-21까지(인터토토는 램파드·지울리·로텐 선례)
    if cid == "AFCL": return (1, 1)                           # AFC 대회 2022 시즌까지 원정 다득점·연장(문서 3절, 히바우두 2008 선례)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    """다른 차전 스코어(우리-상대). 몰수 경기는 공식 판정 스코어(Transfermarkt 경기 성적의 판정 스코어; 델피에로 1994 CSKA 소피아 선례)."""
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G and G[oid]["gameState"] != "penalty_shootout":
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, m["other_leg_score"].split(":"))     # 이 경기 홈 팀 기준 표기(raw tm_two_leg_ties로 확인)
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

AWARDED = {"2232580": "2002.8.7 인터토토컵 준결승 2차전 트루아–비야레알(경기장 2-1, UEFA 0-3 몰수: 미등록 교체 선수)",
           "1150157": "2011.9.14 AFC 챔스 8강 1차전 세파한–알사드(경기장 1-0, AFC 0-3 몰수: 세파한 출전 정지 선수 기용)"}

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
    if t.startswith("Deflect"): return "굴절"
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
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e): judg.append(("본인 자책골(골 아님)", ldate(g), opp(g), e["minute"]))
        if is_a and sd != side and not is_og(e):
            judg.append(("도움 아님(상대 골의 도움 칸에 니앙 이름: 핸드볼 반칙 PK)", ldate(g), opp(g), e["minute"], e["scorer"], e["assist_type"]))
            continue
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        if (gid, e["minute"]) in BEFORE_FIX: gf, ga = BEFORE_FIX[(gid, e["minute"])]
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if (gid, e["minute"]) in A_DROP:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], A_DROP[(gid, e["minute"])])); continue
            if ldate(g) >= GAP: sys.exit("2014-08 뒤 도움 판정 필요 " + gid)
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
    if gid in AWARDED and (cnt_[(gid, "g")] or cnt_[(gid, "a")]): sys.exit("몰수 경기 골·도움 판정 필요 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
GA_GAMES = {r[1] for r in raw_rows}
SM_GA = [x for x in SCORE_MISMATCH if x[0] in GA_GAMES]
if SM_GA: sys.exit("골·도움 경기 리포트 불완전 " + str(SM_GA))
REPORT_INCOMPLETE = {"2852016"}   # 2007.1.6 캉브레전 리포트에 상대 골 1개 빠짐(니앙 골·도움 없음)
if {x[0] for x in SCORE_MISMATCH} - set(AWARDED) - REPORT_INCOMPLETE: sys.exit("몰수 외 스코어 불일치 " + str(SCORE_MISMATCH))

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
MANUAL_ALIAS = {"olympique lyon": "olympique lyonnais", "el jaish sc": "el jaish sc"}
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
        "deportivo", "san", "santa", "saint", "us", "ogc", "losc", "stade", "racing", "athletic", "union", "sportive", "vfb", "vfl",
        "al", "spor", "jk", "sk", "cska", "moscow", "sofia"}   # CSKA 모스크바/소피아 같은 날 경기 혼동 방지
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, collections.Counter((x[2], x[12]) for b, x in cand)

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
RANK_FIX = {}   # (리그, 시즌, 팀 키) -> 공식 최종 순위(Transfermarkt 표와 다를 때) — judgments.md 6절

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
LADDER_FR1 = {}
for _n, _s in ((20, "2002-03"), (18, "2023-24")):
    _m = ents_map("리그1", _s)
    if sorted(_m) != list(range(1, _n + 1)): sys.exit("리그1 기준 순위표 불완전 " + _s)
    LADDER_FR1[_n] = [_m[i] for i in range(1, _n + 1)]

# 쉬페르리그: 튀르키예 회귀(평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 흩어짐 119; 아르다 투란·아일톤 build 방식)
TR_COEF = {2009: 7.6, 2010: 4.6, 2011: 5.1, 2012: 10.2, 2013: 6.7}   # 투란 build와 같은 값(영어 위키백과 'Turkish football clubs in European competitions')
def tr_mean(season):
    s = int(season[:4]); c = sum(TR_COEF[y] for y in (s - 1, s, s + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)

def rank_model(lg, season, r, n):
    if lg == "FR1":
        m = ents_map("리그1", season)
        if not m: return None
        v, it = mid(m, r)
        if v is None:
            v = LADDER_FR1[n][r - 1]; INTERP_USED.add((lg, season, r, v, "표"))
            return v, f"리그1 {season} {r}위"
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"리그1 {season} {r}위"
    if lg == "FR2":
        m = ents_map("리그2", season)
        v, it = mid(m, r)
        if v is None:
            v = half_up(1540 + SD2 * curve(r, n)); INTERP_USED.add((lg, season, r, v, "모형"))
            return v, f"리그2 {season} {r}위 (추정, 프랑스 2부 평균 1540 모형)"
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"리그2 {season} {r}위"
    if lg == "TR1":
        m = ents_map("쉬페르리그", season)
        if r in m: return m[r], f"쉬페르리그 {season} {r}위"
        lo = [k for k in m if k < r]; hi = [k for k in m if k > r]
        if lo and hi:
            a, b = max(lo), min(hi); v = half_up(m[a] + (m[b] - m[a]) * (r - a) / (b - a))
            INTERP_USED.add((lg, season, r, v))
            return v, f"쉬페르리그 {season} {r}위 (추정, 다른 선수 자료 {a}위 {m[a]}·{b}위 {m[b]} 사이)"
        v = round(tr_mean(season) + 119 * curve(r, n)); INTERP_USED.add((lg, season, r, v, "모형"))
        return v, f"쉬페르리그 {season} {r}위 (추정, 튀르키예 리그 수준 회귀)"
    if lg == "QSL":
        m = ents_map("카타르", season)
        v = round(1460 + 45 * curve(r, n))
        return v, f"카타르 {season} {r}위 (추정, 마레즈 자료와 같은 리그 수준)"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; SAME_MULTI = []
def opp_elo(o, d, cid, rnd=""):
    cand, vals = same_match(o, d)
    if vals:
        if len(vals) > 1: SAME_MULTI.append((o, d, dict(vals)))
        (e, lv), _ = vals.most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    k = key(o)
    s0 = eu(d)
    if (k, s0) in MAN:
        e, lv = MAN[(k, s0)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    if (k, s0) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, s0)]).most_common(1)[0]
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s0); return e, lv
    for lg in ("FR1", "FR2", "TR1", "QSL"):
        t = RANKS.get((lg, s0), {})
        if k in t:
            r, n, _ = t[k]
            r = RANK_FIX.get((lg, s0, k), r)
            res = rank_model(lg, s0, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], (lg, s0, r, n)); return res
    MISS.append((o, d, cid, s0)); return 0, "?"

# ---------------------------------------------------------------- 직접 추정(모두 lv에 '추정') — judgments.md 6절
MAN_NOTE = {}
def man2(o, s, e, lv, why): MAN[(key(o), s)] = (e, lv); MAN_NOTE[(key(o), s)] = why
# 순위 근거: Transfermarkt 순위표 + 웹 확인(judgments.md 6절)
man2("Grenoble Foot 38", "2000-01", 1389, "프랑스 3부(나시오날) 2000-01 1위 (추정, 다른 선수 자료 나시오날 2위 1375·3위 1361 간격만큼 높임)",
     "2000-01 Championnat National 우승(Transfermarkt FR3 표 1위, Soccerway 기록실 우승 팀) — 쿠프 드 프랑스 상대")
man2("Coleraine FC", "2002-03", 1270, "북아일랜드 2002-03 3위 (추정, 다른 선수 자료 북아일랜드 5·6위 1250보다 조금 높게)",
     "2002-03 Irish League 3위/12팀(Transfermarkt 표, 영어 위키백과 2002-03 Irish League 73점 3위)")
man2("BSC Young Boys", "2005-06", 1520, "스위스 2005-06 3위 (추정, 다른 선수 자료 스위스 3위 1520과 같음)",
     "2005-06 스위스 슈퍼리그 3위/10팀(Transfermarkt 표 = 영어 위키백과)")
man2("BSC Young Boys", "2006-07", 1507, "스위스 2006-07 4위 (추정, 다른 선수 자료 스위스 4위 1507과 같음)",
     "2006-07 스위스 슈퍼리그 4위/10팀(Transfermarkt 표 = 영어 위키백과)")
man2("Dnipro Dnipropetrovsk", "2006-07", 1500, "우크라이나 1부 2006-07 4위 (추정, 다른 선수 자료 드니프로 2003-04 1550·우크라이나 1부 2009-10 6위 1520보다 조금 낮게)",
     "2006-07 우크라이나 1부 4위/16팀(Transfermarkt 표 = 영어 위키백과 2006-07 Vyshcha Liha)")
man2("Vannes OC", "2006-07", 1275, "프랑스 3부(나시오날) 2006-07 15위 (추정, 다른 선수 자료 나시오날 13위 1287·17위 1263의 가운데)",
     "2006-07 Championnat National 15위/20팀(Transfermarkt 표)")
man2("AS Beauvais Oise", "2007-08", 1304, "프랑스 3부(나시오날) 2007-08 9위 (추정, 다른 선수 자료 나시오날 9위 1304와 같음)",
     "2007-08 Championnat National 9위/20팀(Transfermarkt 표)")
man2("CSKA Moscow", "2005-06", 1630, "러시아 2005 1위 (추정, 다른 선수 자료 CSKA 모스크바 2006 1위 1630과 같음)",
     "2005.10 경기 = 진행 중인 2005 시즌(러시아 달력 연도) 우승 팀, 2004-05 UEFA컵 우승 팀; Transfermarkt RU1 2005 표 1위")
man2("Spartak Moscow", "2007-08", 1604, "러시아 2007 2위 (추정, 다른 선수 자료 러시아 2위 값 1604와 같음)",
     "2008.2 경기 = 직전 완료 시즌 2007(러시아 달력 연도 시즌) 2위/16팀(Transfermarkt 표 = 영어 위키백과)")
man2("SK Brann", "2008-09", 1400, "노르웨이 2008 8위/14팀·2007 우승 팀 (추정, 다른 선수 자료 노르웨이 1위 1500·6위 1350 사이)",
     "2008 티펠리가엔 8위/14팀(Transfermarkt 표 = 영어 위키백과), 2007 우승 팀으로 챔스 예선 출전")
man2("Yeni Malatyaspor", "2010-11", 1143, "튀르키예 3부 2010-11 백색조 5위/18팀 (추정, 쉬페르리그 평균 − 2×독일 1·2부 평균 차)",
     "2010-11 TFF 2. Lig 백색조 5위(영어 위키백과 순위 변동표 마지막 라운드 5위; Transfermarkt 일정표는 경기 전 순위라 4위로 보임), 투란 build 공식 1436 − 324 + 51.24×곡선")
man2("Sepahan FC", "2011-12", 1440, "이란 1부 2011-12 1위 (추정, 다른 선수 자료 이란 1위 1440과 같음)",
     "2011-12 이란 프로리그 우승(Transfermarkt 표 = 영어 위키백과 2011-12 Persian Gulf Cup)")
man2("Suwon Samsung Bluewings", "2011-12", 1500, "K리그 2011 4위·AFC 챔스 2011 4강 (추정, 다른 선수 자료 포항 2021(AFC 챔스 준우승) 1500과 같음)",
     "2011 K리그 4위/16팀(Transfermarkt 표 = 영어 위키백과 2011 K-League)")

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

# ---------------------------------------------------------------- FotMob 골 대조(2010~15)
FM_CMP = []; FM_N = 0; FM_A = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    fm_all = [r for r in FME[gid] if r["pen_shootout_event"] != "True"]
    for r in fm_all:
        if r["niang_assist"] == "1": FM_A.append((ldate(G[gid]), opp(G[gid]), r["time"], r["scorer"]))
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    if not tm: continue
    fm = [r for r in fm_all if r["niang_scorer"] == "1" and r["ownGoal"] not in ("1", "True")]
    FM_N += 1
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]))):
        a = mins(t["minute"])[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
        if a != b and not (t["minute"].startswith("90+") and b == 90):
            FM_CMP.append(("분 다름", gid, ldate(G[gid]), t["minute"], f["time"]))
        if (t["goal_desc"] == "Penalty") != (f["suffix"] in ("pen", "Pen", "penalty") or "pen" in (f["goalDescriptionKey"] or "").lower()):
            FM_CMP.append(("PK 표기 다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["suffix"], f["goalDescriptionKey"]))
# FotMob 도움 칸과 Transfermarkt 도움 대조(FotMob 이벤트가 있는 경기만)
FM_ACHK = []
for r in E:
    if r[0] != "a": continue
    gid = [x["gameId"] for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
    if gid in FME:
        hit = [f for f in FME[gid] if f["niang_assist"] == "1"]
        FM_ACHK.append((r[9], r[1], r[4], r[13], "FotMob 확인" if hit else ("FotMob 도움 없음" if any(f["scorer"] for f in FME[gid]) else "FotMob 이벤트 없음")))

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
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Mamadou Niang|^Niang$", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움→니앙 골", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_opp(x, r)]
            if hit: CROSS.append(("니앙 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_opp(x, r):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회/합산 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
TEAMN = {"1095": "ESTAC Troyes", "347": "FC Metz", "667": "RC Strasbourg Alsace", "244": "Olympique Marseille", "36": "Fenerbahce",
         "656": "Al-Sadd", "114": "Besiktas", "11300": "AC Arles-Avignon"}
for r in E:
    g = [x for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
    for b, (oe, om) in OTHERS.items():
        for x in oe:
            if x[9] == r[9] and toks(x[1]) & toks(TEAMN[g["club_id"]]):
                CROSS.append(("상대 팀 선수 같은 경기 기록(스코어 대조용)", b, r[9], x[0], x[4], x[5], x[6], "니앙 행", r[0], r[4], r[5], r[6]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_opp(x, [0, j[2]]):
                    CROSS.append(("TM 니앙 도움을 규칙대로 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("trong", "2003-01-27", "ESTAC 트루아", "2000~2002"), ("metng", "2003-07-01", "FC 메스", "2003"),
         ("strng", "2005-07-01", "RC 스트라스부르", "2003~2005"), ("omng", "2010-08-15", "올랭피크 마르세유", "2005~2010"),
         ("fenng", "2011-07-06", "페네르바체", "2010~2011"), ("sadng", "2013-01-31", "알사드", "2011~2012"),
         ("besng", "2013-07-01", "베식타시", "2013"), ("sadng", "2014-08-29", "알사드", "2014"), ("arlng", None, "AC 아를아비뇽", "2014~2015")]
TM_CLUB = {"1095": "trong", "347": "metng", "667": "strng", "244": "omng", "36": "fenng", "656": "sadng", "114": "besng", "11300": "arlng"}
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
SAD2 = [0, 0, 0, 0]
for m in M:
    if m[0] >= "2013-07-01": SAD2[0] += 1 if club_of(m[0]) == "sadng" else 0; SAD2[3] += m[3] if club_of(m[0]) == "sadng" else 0
for r in E:
    if r[9] >= "2013-07-01" and club_of(r[9]) == "sadng": SAD2[1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({(r[9]) for r in E if len(r) > 14})
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club == "trong": s = y if m >= 7 else y - 1
    elif club == "omng": s = y if d[5:] >= "07-10" else y - 1
    else: s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print("알사드 2기", SAD2)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    print("FotMob", FM_N, FM_CMP, "FM 니앙 도움", FM_A)
    for x in FM_ACHK: print("FM 도움 대조", x)
    for c in CROSS: print(c)
    print(sorted(collections.Counter(season_of(m[0], club_of(m[0])) for m in M).items()))
    print("blank-type assists", UNTYPED)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
SRC = ELO_SRC
first, last = M[0], M[-1]
EXA = [j for j in judg if j[0] == "도움 제외"]
PKS = [r for r in E if r[0] == "g" and r[8]]
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
MODEL_USED = sorted({(v[3], o) for (o, d), v in ELO_LOG.items() if v[0] == "model"})
KO_NAME = {"Clermont Foot Auvergne": "클레르몽", "Association sportive d'origine arménienne de Valence": "발랑스", "AS Nancy-Lorraine": "낭시",
           "ESTAC Troyes": "트루아", "Clermont Foot 63": "클레르몽", "Kasimpasa": "카슴파샤", "Genclerbirligi Ankara": "겐칠레르비를리이",
           "Konyaspor": "코냐스포르", "Bucaspor": "부자스포르", "MKE Ankaragücü": "앙카라귀쥐", "Trabzonspor": "트라브존스포르",
           "Kayserispor": "카이세리스포르", "Eskisehirspor": "에스키셰히르스포르", "Umm Salal SC": "움살랄", "El-Jaish SC": "엘자이시"}
def model_txt(lgs):
    out = []
    for (lg, s, r, n), o in MODEL_USED:
        if lg in lgs: out.append(f"{KO_NAME.get(o, o)} {s} {r}위/{n}팀")
    return "·".join(dict.fromkeys(out))
def exa_txt(why):
    return ", ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]} 골" for j in EXA if j[5] == why)
NOTE_LINES = [
    f"마마두 니앙(ESTAC 트루아·FC 메스·RC 스트라스부르·올랭피크 마르세유·페네르바체·알사드·베식타시·AC 아를아비뇽)의 클럽 공식 경기 {NG}경기({d_(first[0])} {first[1]}전 ~ {d_(last[0])} {last[1]}전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·세네갈 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CN[k]} {c3(v)}" for k, v in ST.items())
    + f"(알사드는 2011~2012 {ST['sadng'][0]-SAD2[0]}·{ST['sadng'][1]-SAD2[1]}·{ST['sadng'][2]-SAD2[2]}과 2014년 1월 {c3(SAD2)}의 합계). 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부, 리포트 골·도움 수가 선수 경기 성적과 경기마다 같음). 영어·프랑스어 위키백과 클럽·시즌별 경기·골과 대조(아래 차이 말고는 같음). FotMob은 2010-11 페네르바체부터 2014-15 아를아비뇽까지 경기만 대조함",
    "범위: 모든 소속 팀-시즌이 프로 1·2부(트루아·스트라스부르·마르세유 리그1, 메스 2002-03·아를아비뇽 2014-15 리그2, 쉬페르리그, 카타르 스타스리그). 영어 위키백과의 아를아비뇽 2015-16 4부(CFA) 1경기는 Transfermarkt·FotMob에 기록이 없고(2015.7 계약 만료) 아마추어 리그라 뺌, 2018년 아틀레티코 마르세유(4부 아마추어)는 출전 없음. 영어 위키백과는 트루아·마르세유의 인터토토컵 경기를 클럽 합계에서 빼서 경기 수가 적음(트루아 56, 마르세유 219)",
    "카타르 국내 컵: 영어 위키백과 알사드 2011-12 줄에 국내컵 3경기 1골·리그컵 2경기 3골, 프랑스어 위키백과 2012-13 줄에 컵 1경기가 있지만 Transfermarkt·FotMob에 출전 기록이 없고(에미르컵 2경기는 Transfermarkt 'not in squad') 경기별 날짜·상대·골 시각 근거를 찾지 못해 넣지 않음",
    f"골: 자책골 없음. PK 골 {NPK}개는 Transfermarkt 골 유형 'Penalty'(" + ", ".join(f"{d_(r[9])} {r[1]}전 {r[4] if not r[11] else r[11]}분" for r in PKS) + "). PK가 막힌 뒤 리바운드 골 없음. FotMob(2010~15) 골 기록과 대조한 18경기는 골 수·PK가 모두 같고, 분이 1분 다른 5골(2010.8.29 Manisaspor전 70·73분(FotMob 69·74), 2011.3.13 Konyaspor전 15(16), 2011.9.27 Sepahan전 85(84), 2013.4.27 Orduspor전 25(26))은 Transfermarkt를 씀",
    f"도움: 2014년 8월 전 도움은 Transfermarkt 경기 리포트 단일 출처를 씀(클로제·인시녜·로텐 선례). Transfermarkt 도움 54개에서 PK 유도 4개(" + exa_txt("PK 유도") + "), 슈팅 리바운드 1개(" + exa_txt("슈팅 리바운드('Shot on goal')") + "), 상대 자책골 유도 2개(" + exa_txt("상대 자책골 유도") + "; 앞의 것은 Transfermarkt 유형 'Shot on goal', 뒤의 것은 'Corner')를 빼고, 2014.9.23 Stade Lavallois전 83분 기고 골 도움(유형 빈칸)은 2014년 8월 뒤인데 FotMob 도움 칸이 비어 있고 다른 출처 2곳으로 확인하지 못해 뺌 → " + f"{NA}개. 도움 유형 칸이 빈 {UNTYPED}개는 일반 도움으로 셈(토티·로텐 선례). 본인 PK 골 7개에 붙은 본인 도움 표기('Penalty: Fouled player')와 2010.2.18 FC Copenhagen전 상대 PK 골의 도움 칸 'Handball by Mamadou Niang'(니앙 핸드볼 반칙)은 도움이 아님",
    "FotMob 도움 대조: FotMob 경기 기록이 있는 도움 7개 중 5개는 FotMob도 니앙 도움(2010.9.27 Kasimpasa전 21분, 2010.11.22 Bucaspor전 13·86분, 2013.3.3 Fenerbahce전 90+3분, 2013.3.16 Kasimpasa전 13분). 2010.10.18 Konyaspor전 26·34분 2개는 FotMob 도움 칸이 비어 있지만 2014년 8월 전이라 Transfermarkt 단일 출처 규칙대로 넣음. 2011년 봄 쉬페르리그·튀르키예컵·카타르 리그 경기 대부분은 FotMob 골 기록이 없음",
    "도움이 실제보다 적을 수 있음: Transfermarkt는 트루아 시절(2000~02) 도움이 1개, 알사드 시절 0개뿐이고 위키백과에는 도움 칸이 없어 더 확인할 출처가 없음",
    "출전 분: Transfermarkt 그대로(빈칸 없음, 추정한 경기 없음). FotMob 교체 시각과 3분 넘게 다른 3경기(2011.2.5 84분(FotMob 88분 교체), 2011.4.16 31분(25분), 2015.4.3 58분(55분))도 Transfermarkt. 연장·승부차기 경기는 Transfermarkt 출전 분. 날짜는 경기 현지 날짜(이란·한국 원정과 일본 클럽 월드컵 포함, Transfermarkt 리포트 날짜와 같음)",
    "몰수 경기(공식 기록이 골을 지운 경우만 골·도움을 빼는 규칙): 2002.8.7 인터토토컵 준결승 2차전 트루아–비야레알(경기장 2-1, 트루아의 미등록 선수 교체 출전으로 UEFA가 0-3 몰수패)과 2011.9.14 AFC 챔스 8강 1차전 세파한–알사드(경기장 1-0, 세파한의 출전 정지 선수 기용으로 AFC가 알사드 3-0 몰수승)는 니앙 골·도움이 없어 출전(28분·90분)만 셈. 8강 2차전(2011.9.27, 홈 1-2 패, 니앙 85분 골)의 합산 계산에는 공식 판정 스코어 1차전 3-0을 씀(합산 4-2 알사드 진출, 델피에로 1994 CSKA 소피아전 몰수 선례)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(리베리·발부에나·벤 아르파·라울·사바니에 등), 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표, 영어 위키백과 시즌 문서로 순위 확인)를 기존 리그 순위값·리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['기존 팀×시즌 값']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    f"리그 모형(추정 표시): 리그2는 그 시즌 기존 순위값, 빈 순위는 앞뒤 기존 값의 가운데, 앞이나 뒤에 기존 값이 없으면 평균 1540·2부 흩어짐 모형({model_txt({'FR2'})}). 쉬페르리그는 같은 시즌 기존 순위값 사이의 빈 순위는 직선 값, 끝 순위는 튀르키예 리그 수준 회귀(평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 2010-11 평균 약 1436, 흩어짐 119; 투란 자료와 같은 공식)({model_txt({'TR1'})}). 카타르 스타스리그는 평균 1460·흩어짐 45 순위 곡선(마레즈·라울 자료와 같은 리그 수준)({model_txt({'QSL'})})",
    "직접 추정(모두 '추정'): " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED) + ". 순위 근거: Transfermarkt 순위표와 영어 위키백과 시즌 문서(스위스 2005-06·2006-07, 우크라이나 2006-07, 러시아 2007, 노르웨이 2008, 이란 2011-12, K리그 2011, TFF 2. Lig 2010-11), 2000-01 나시오날 우승은 Soccerway 기록실, 2002-03 북아일랜드 3위는 위키백과. 러시아 팀은 진행 중이거나 직전에 끝난 달력 연도 시즌 순위(CSKA 모스크바 2005.10 → 2005, 스파르타크 모스크바 2008.2 → 2007)",
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·튀르키예컵(2010-11 조별은 리그식)은 국내컵(16강까지·8강·준결승·결승). 인터토토컵(2라운드~결승)·UEFA컵 예선·1라운드·유로파 플레이오프는 유로파 예선, UEFA컵 조별은 유로파 조별, UEFA컵·유로파 2·3라운드·32강·16강·8강은 유로파 토너먼트, 챔스 예선 3라운드·조별. AFC 챔스 2011 8강·준결승(두 경기)·결승(전북 원정, 승부차기 우승), 클럽 월드컵 2011(8강·준결승·3위 결정전, 단판)",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함: UEFA 대회·인터토토컵·AFC 챔스는 원정 다득점·연장. 다른 차전 스코어는 Transfermarkt 경기 성적·리포트(몰수 경기는 공식 판정 스코어)",
    "시즌 구분: 트루아는 7월 1일 기준(2001.7 인터토토컵 경기가 2001-02, 2001.6.30 인터토토컵 2라운드 1차전 WIT 조지아전은 2000-01, 2002.7.6 콜레인전부터 2002-03 — 로텐 트루아 선례), 마르세유는 7월 10일 기준(2005.7.16·2006.7.15 인터토토컵 경기가 새 시즌, 리베리·발부에나·벤 아르파 마르세유 선례), 나머지는 기본 8월 1일(알사드 AFC 챔스 2011.9~11·클럽 월드컵 2011.12는 2011-12). 클럽 구분(Transfermarkt 이적 날짜): 2003.1.27 메스 임대, 2003.7.1 스트라스부르, 2005.7.1 마르세유, 2010.8.15 페네르바체, 2011.7.6 알사드, 2013.1.31 베식타시 임대, 2013.7.1 알사드 복귀(같은 클럽으로 묶음), 2014.8.29 아를아비뇽. 경기 클럽과 경계 불일치 0",
    "같은 경기 동료 자료: 리베리(리베리 도움→니앙 골 5, 니앙 도움→리베리 골 1: 2005.9.18 ESTAC Troyes전 22분), 발부에나(발부에나 도움→니앙 골 3, 니앙 도움→발부에나 골 4), 벤 아르파(벤 아르파 도움→니앙 골 2, 니앙 도움→벤 아르파 골 4)와 날짜·분·골 전 스코어·대회·상대 Elo·수준 설명이 모두 같음. 라울(알사드 2012-13)·사바니에(아를아비뇽 2014-15) 같은 경기 상대 값도 같음. 상대 팀 선수 자료(파울레타·로텐·주니뉴·벤제마·구르퀴프·지냑·아자르·수아레스·파예·바스투스·메네즈·아궤로·말루다)와 골 순서도 맞음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 리그1 2009-10(마르세유), 쉬페르리그 2010-11(페네르바체), 카타르 스타스리그 2012-13(알사드, 전반기 출전), 쿠프 드 라 리그 2004-05(스트라스부르)·2009-10(마르세유), AFC 챔스 2011(알사드), 인터토토컵 2001(트루아)·2005·2006(마르세유), 리그1 득점왕 2009-10(18골). 선수협회(UNFP) 리그1 올해의 팀 2007-08·2009-10(프랑스어 위키백과 'Trophées UNFP du football'·영어 위키백과 UNFP 목록). 대표팀(아프리카 네이션스컵) 제외",
    "은퇴: 마지막 클럽 공식 경기는 2015.5.8 ESTAC Troyes전(리그2, 32분), 2015.7 아를아비뇽 계약 만료 뒤 소속 없음, 2018년 아틀레티코 마르세유(4부) 등록 뒤 출전 없이 은퇴(Transfermarkt)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elk", "elq", "cwc", "MAN", "csa", "lib", "lg", "acl", "aclk"]:
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
for r in E:
    g = [x for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
    m = [x for x in M if x[0] == r[9] and x[1] == r[1]][0]
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    dur = int(g["gameDuration"])
    if g["isStarting"] == "True": lo, hi = 0, m[3] + 8
    else: lo, hi = dur - m[3] - 8, dur + 10      # 교체 투입 시각 자료가 없어 경기 길이 − 출전 분으로 근사
    if not (lo <= r[4] <= hi): problems.append(("출전 구간 밖 기록", r[9], r[4], g["isStarting"], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const NIA_E={J(E)};\nconst NIA_M={J(M)};\nconst NIA_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_niang_assists": FM_A, "fotmob_assist_check": FM_ACHK, "elo_sources": ELO_SRC,
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}, "man_notes": {f"{k[0]}|{k[1]}": v for k, v in MAN_NOTE.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
