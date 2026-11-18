#!/usr/bin/env python3
"""디미타르 베르바토프 (Transfermarkt 65): raw/ -> berbatov.json + src/data/brb.js (판정 근거는 judgments.md)

  python3 players/berbatov/build_berbatov.py                 # 파일 쓰기
  python3 players/berbatov/build_berbatov.py --debug         # Elo 출처 로그
  python3 players/berbatov/build_berbatov.py --stat          # 요약·동료 대조·FotMob 대조
  python3 players/berbatov/build_berbatov.py --ties          # 합산 행·판정
  python3 players/berbatov/build_berbatov.py --root=<복사본>  # 그 복사본의 src/data·elo 사용(검증용)

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv·fotmob_tm_map.csv(FotMob), raw/ranks.txt(Transfermarkt 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
뼈대는 벨한다 build_belhanda.py. 레버쿠젠 II(오버리가 노르트라인, 4부 2군) 7경기는 tm_games.csv에 없음(제외).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
GITROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "brb.js")
OUT_JSON = os.path.join(HERE, "berbatov.json")
ME = "65"
ME_KO = "디미타르 베르바토프"

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
FM_MAP = {r["tm_gameId"]: r["fotmob_matchId"] for r in rd("fotmob_tm_map.csv") if r["fotmob_matchId"]}

def ldate(g): return g["date_local_computed"]          # Transfermarkt 리포트 날짜와 모두 같음
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 판정 표
GAP = "2014-08-01"              # 이 날짜 전 도움은 Transfermarkt 리포트 단일 출처 허용(클로제·인시녜·벨한다 선례)
ADD_CONFIRMED = {}              # 2014-08 뒤 TM 단독 도움을 다른 출처 2곳으로 확인한 것(해당 없음)
UNCONFIRMED = {}                # 2014-08 뒤 TM 단독 도움을 확인 못 해 뺀 것(해당 없음)
EXCL_A = {}
# Transfermarkt 리포트 스코어 표기 오류: 2007.4.12 토트넘 2-2 세비야(67673) 3분 말브랑크 자책골이 '1:0'(원정 쪽)으로 적혀
# 누적 스코어가 최종 2:2와 어긋남 → 최종 스코어에 맞는 순서 0-1(3분)·0-2(8분)·1-2(65분 디포, 베르바토프 도움)·2-2(66분)
SIDE_FIX = {}   # 득점 편(side)은 맞고 표시 숫자만 틀림 — 누적 스코어를 편으로 세므로 고칠 것 없음

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BU1", "L1", "GB1", "FR1", "GR1", "POGR", "IND1"}     # 그리스 슈퍼리그 플레이오프 = 리그(발부에나·히바우두 선례)
CUPS = {"BULP", "DFB", "FAC", "CGB", "FRC", "FRL", "GRP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "GBCS": return "df"                              # 커뮤니티 실드 = 국내컵 결승 비중
    if cid == "LPO":                                           # DFL-리가포칼: 첫 경기(intermediate stage, 8강급) dk, 준결승 dsf, 결승 df(클로제·발라크 선례)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        return "dk"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or "sixth" in r or "6th" in r: return "dk"   # FA컵 6라운드(재경기 포함)·리그컵 5라운드(8강) = 8강
        return "dc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"                 # 2001-02 2차 조별(Group 1·4) 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEQ": return "elq"                              # UEFA컵 예선
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"           # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                           # UEFA컵 3라운드·16강·8강, 유로파 32강('Second Round')
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
    if cid in ("CL", "CLQ", "UEFA", "UEQ", "EL"): return (1, 1)   # UEFA 2020-21까지
    if cid == "CGB": return (1, 1)                                 # 잉글랜드 리그컵 준결승 2017-18까지
    if cid == "GRP": return (1, 1)                                 # 그리스컵 두 경기 라운드(발부에나·히바우두 선례: 원정 다득점·연장)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

TIES = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
def other_leg(gid):
    """다른 차전 스코어(우리, 상대). tm_two_leg_ties의 other_leg_final은 이번 차전의 홈:원정 순서로 적혀 있음
    (예: 2010.4.7 맨유 홈 3-2 바이에른 행의 1차전 '1:2' = 맨유 1·바이에른 2)."""
    a, b = map(int, TIES[gid]["other_leg_final"].split(":"))
    return (a, b) if side_of(gid) == "h" else (b, a)

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
    if t.startswith("Deflect"): return "굴절"
    if t.startswith("Handball"): return "PK 유도(핸드볼)"
    return None

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FME.items():
    for r in evs:
        if r["berbatov_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))

raw_rows, judg = [], []
SRC_A = collections.Counter()
UNDECIDED = []
USED_FM = collections.Counter()
TM_A_TYPES = collections.Counter()
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        sd = SIDE_FIX.get((gid, e["minute"]), e["side"])[0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e): judg.append(("본인 자책골(골 아님)", ldate(g), opp(g), e["minute"], e["assist_player"]))
        if is_a and sd != side and not is_og(e):
            sys.exit("상대 골 도움 칸에 베르바토프 " + gid)
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        k = (gid, e["minute"])
        if is_a:
            TM_A_TYPES[e["assist_type"] or "(빈칸)"] += 1
            why = assist_reason(e) or EXCL_A.get(k)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why, e["assist_type"])); continue
            if ldate(g) >= GAP:
                base = int(e["minute"].split("+")[0])
                hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - mi) <= 3 or abs(t - base) <= 3]
                if hit and USED_FM[gid] < len(FM_ASSIST[gid]):
                    USED_FM[gid] += 1; src = "TM∩FotMob 경기 이벤트"
                elif k in ADD_CONFIRMED:
                    src = "TM + 다른 출처 2곳"
                elif k in UNCONFIRMED:
                    judg.append(("도움 제외(단일 출처 미확인)", ldate(g), opp(g), e["minute"], e["scorer"], UNCONFIRMED[k], e["assist_type"])); continue
                else:
                    UNDECIDED.append((gid, ldate(g), opp(g), e["minute"], e["scorer"], e["assist_type"], FM_ASSIST.get(gid))); continue
            else:
                src = "2014.8 전 Transfermarkt"
            SRC_A[src] += 1
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"].replace("\u200e", "").strip(), e["assist_type"]))
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

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if SIDE_FIX.get((gid, e["minute"]), e["side"])[0] == "h"); a = len(evs) - h
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
GA_GAMES = {r[1] for r in raw_rows}
if [x for x in SCORE_MISMATCH if x[0] in GA_GAMES]: sys.exit("골·도움 경기 리포트 불완전 " + str(SCORE_MISMATCH))

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
MANUAL_ALIAS = {}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", GITROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "brb.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "foot", "ball",
        "atletico", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss", "olympique", "milan", "inter", "madrid", "fk", "if",
        "deportivo", "san", "santa", "saint", "us", "ogc", "losc", "stade", "racing", "athletic", "union", "sportive", "vfb", "vfl",
        "al", "spor", "jk", "sk", "cska", "moscow", "sofia", "kyiv", "dynamo", "metalurg", "nk", "krc", "hnk", "pfk", "bk", "aalborg",
        "borussia", "eintracht", "hotspur", "wanderers", "rovers", "albion", "town", "county", "athletico", "lokomotiv", "levski",
        "botev", "slavia", "spartak", "tsv", "fsv", "spvgg", "bayer", "hapoel", "maccabi", "manchester", "sheffield", "bristol",
        "west", "aston", "crystal", "queens", "park", "hamburger", "werder", "schalke", "hertha", "munich", "bayern", "plovdiv",
        "panathinaikos", "olympiacos", "aris", "hansa", "arminia", "energie", "alemannia", "kickers", "stuttgarter", "fortuna"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_key(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if same_key(x[1], o)]
    return cand, collections.Counter((x[2], x[12]) for b, x in cand)

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
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
def half_up(x): return int(x + 0.5)

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e[12] or "")
        if m: c[int(m.group(1))][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
INTERP_USED = set()
def mid(tab, r):
    if r in tab: return tab[r], False
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up(tab[a] + (tab[b] - tab[a]) * (r - a) / (b - a)), True

# 그리스 슈퍼리그: 발부에나·마린 자료와 같은 국가 계수 회귀(1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 흩어짐 119)
#   + 그리스 보정 GR_K(기준점 올림피아코스 2019-20 1위 1680·2020-21 1위 1690, PAOK 2021-22 2위 1590, 14팀 곡선).
#   계수(시작 연도): 2014-15 6.200(kassiesa.net method4 ccoef2015), 2015-16 5.400·2016-17 5.800 이후는 마린 자료와 같음.
GR_COEF = {2014: 6.2, 2015: 5.4, 2016: 5.8, 2017: 5.2, 2018: 5.1, 2019: 4.9, 2020: 5.1, 2021: 8.0, 2022: 2.125, 2023: 11.4, 2024: 12.688}
def reg_mean(coefs): return 1473 + 23.33 * (sum(coefs) / len(coefs) - 7.3333)
def gr_reg(start): return reg_mean([GR_COEF[y] for y in (start - 1, start, start + 1)])
GR_ANCH = [(2019, 1, 1680), (2020, 1, 1690), (2021, 2, 1590)]
GR_K = sum(v - (gr_reg(y) + 119 * curve(r, 14)) for y, r, v in GR_ANCH) / len(GR_ANCH)
def gr_mean(season): return gr_reg(int(season[:4])) + GR_K
# 불가리아 1부 1998-99~2000-01: 1위 1480 ~ 최하위 1300 직선(추정). 기존 자료의 불가리아 값(1·2위 1480, 3~5위 1450, 6위 1420)에 맞춘 선
def bg_lin(r, n): return half_up(1480 - 180 * (r - 1) / (n - 1))
# 인도 슈퍼리그: 1위 1300 ~ 최하위 1200 직선(델 피에로·말루다·포를란 선례)
def in_lin(r, n): return half_up(1300 - 100 * (r - 1) / (n - 1))

def rank_model(lg, season, r, n):
    pre = {"L1": "분데스리가", "L2": "2. 분데스리가", "GB1": "프리미어리그", "GB2": "챔피언십", "GB3": "리그 원", "FR1": "리그1"}.get(lg)
    if pre:
        v, it = mid(ents_map(pre, season), r)
        if v is None: return None
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"{pre} {season} {r}위"
    if lg == "GR1":
        return half_up(gr_mean(season) + 119 * curve(r, n)), f"그리스 슈퍼리그 {season} {r}위 (리그 수준 추정)"
    if lg == "BU1":
        return bg_lin(r, n), f"불가리아 1부 {season} {r}위/{n}팀 (추정: 1위 1480~최하위 1300 직선)"
    if lg == "IND1":
        return in_lin(r, n), f"인도 슈퍼리그 {season} {r}위 (추정: 1위 1300~꼴찌 1200 직선)"
    return None
RANK_LG = ["L1", "GB1", "FR1", "GR1", "BU1", "IND1", "L2", "GB2", "GB3"]

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}; MAN_NOTE = {}
def man2(o, s, e, lv, why): MAN[(key(o), s)] = (e, lv); MAN_NOTE[(key(o), s)] = why

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; SAME_MULTI = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if vals:
        if len(vals) > 1: SAME_MULTI.append((o, d, dict(vals)))
        (e, lv), _ = vals.most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    k = key(o); s0 = eu(d)
    if (k, s0) in MAN:
        e, lv = MAN[(k, s0)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    if (k, s0) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, s0)]).most_common(1)[0]
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s0); return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, s0), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s0, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], (lg, s0, r, n)); return res
    MISS.append((o, d, cid, s0)); return 0, "?"

exec(open(os.path.join(HERE, "man_berbatov.py"), encoding="utf-8").read()) if os.path.exists(os.path.join(HERE, "man_berbatov.py")) else None

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(2014-08 뒤 TM 단독 도움):", u)
if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
if (UNDECIDED or MISS) and "--force" not in sys.argv: sys.exit(1)

if "--debug" in sys.argv:
    print(ELO_SRC)
    for x in SAME_MULTI: print("같은 경기 값 여럿", x)
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]): print(d, o, v)
    print("보간", sorted(INTERP_USED)); print("GR_K", GR_K, gr_mean("2015-16")); sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    for j in judg: print(j)
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []; FM_N = 0
for gid in GA_GAMES:
    tm = [e for e in EVS[gid] if e["scorer_id"] == ME and not is_og(e)]
    if not tm: continue
    fm_all = [r for r in FME.get(gid, []) if r["pen_shootout_event"] != "True"]
    if not any(r["scorer"] for r in fm_all): continue
    fm = [r for r in fm_all if (r["berbatov_scorer"] == "1" or "Berbatov" in r["scorer"]) and r["ownGoal"] not in ("1", "True") and (r["goalDescriptionKey"] or "") != "owngoal"]
    FM_N += 1
    if len(tm) != len(fm): FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        a = mins(t["minute"])[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
        if abs(a - b) > 1 and not (t["minute"].startswith(("90+", "45+")) and int(f["time"]) in (45, 90)): FM_CMP.append(("분 다름", gid, ldate(G[gid]), t["minute"], f["time"], f["overloadTime"]))
        fpk = (f["suffix"] or "").lower().startswith("pen") or "pen" in (f["goalDescriptionKey"] or "").lower()
        if (t["goal_desc"] == "Penalty") != fpk: FM_CMP.append(("PK 표기 다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["suffix"], f["goalDescriptionKey"]))
# FotMob에만 있는 베르바토프 도움(넣지 않음)
FM_ONLY_A = []
for gid, ts in FM_ASSIST.items():
    if gid not in G: continue
    tmm = [mins(e["minute"])[0] for e in EVS.get(gid, []) if e["assist_id"] == ME and e["scorer_id"] != ME]
    for t in ts:
        if not any(abs(t - x) <= 3 for x in tmm): FM_ONLY_A.append((gid, ldate(G[gid]), opp(G[gid]), t))

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
CROSS = []
TEAMN = {"208": "CSKA Sofia", "15": "Bayer 04 Leverkusen", "148": "Tottenham Hotspur", "985": "Manchester United",
         "931": "Fulham FC", "162": "AS Monaco", "1091": "PAOK Thessaloniki", "45277": "Kerala Blasters FC"}
def same_team(x1, club_id):
    return key(x1) == key(TEAMN[club_id]) or bool(toks(x1) & toks(TEAMN[club_id]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Berbatov", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움→베르바토프 골", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_key(x[1], r[1])]
            if hit: CROSS.append(("베르바토프 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_key(x[1], r[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회/합산 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_key(mm[1], m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
    for r in E:
        g = [x for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
        for x in oe:
            if x[9] == r[9] and same_team(x[1], g["club_id"]):
                CROSS.append(("상대 팀 선수 같은 경기 기록", b, r[9], x[0], x[4], x[5], x[6], "베르바토프 행", r[0], r[4], r[5], r[6]))
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0].startswith("도움 제외") and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_key(x[1], j[2]):
                    CROSS.append(("TM 베르바토프 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("cskbt", "2001-01-16", "CSKA 소피아", "1998~2001"), ("levbt", "2006-07-01", "바이어 레버쿠젠", "2001~2006"),
         ("totbt", "2008-09-01", "토트넘 홋스퍼", "2006~2008"), ("mubt", "2012-08-31", "맨체스터 유나이티드", "2008~2012"),
         ("fulbt", "2014-01-31", "풀럼", "2012~2014"), ("monbt", "2015-09-02", "AS 모나코", "2014~2015"),
         ("paobt", "2017-08-23", "PAOK", "2015~2016"), ("kerbt", None, "케랄라 블래스터스", "2017~2018")]
TM_CLUB = {"208": "cskbt", "15": "levbt", "148": "totbt", "985": "mubt", "931": "fulbt", "162": "monbt", "1091": "paobt", "45277": "kerbt"}
def club_of(d):
    for k, u, n, y in CLUBS:
        if u is None or d < u: return k
CN = {k: n for k, u, n, y in CLUBS}
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
def season_of(d, club):
    y = int(d[:4])
    if club == "levbt": s = y if d[5:] >= "07-10" else y - 1
    else: s = y if int(d[5:7]) >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CN)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for es in EVS.values() for e in es if e["gameId"] in G and e["assist_id"] == ME and e["scorer_id"] != ME)
SEASONS = collections.Counter(season_of(m[0], club_of(m[0])) for m in M)
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), dict(SRC_A), N_TM_A, dict(TM_A_TYPES))
    print("FotMob 골 대조", FM_N, FM_CMP)
    print("FotMob에만 있는 도움", FM_ONLY_A)
    for c in CROSS: print(c)
    print(sorted(SEASONS.items()))
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_berbatov import make_note
NOTE = make_note(globals())
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elk", "elq", "ecq", "lg", "MAN", "clg", "elg", "clq", "cl16"]:
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
    g = [x for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
    m = [x for x in M if x[0] == r[9] and x[1] == r[1]][0]
    if m[2] != r[3]: problems.append(("대회 다름", r[9], r[1], m[2], r[3]))
    dur = int(g["gameDuration"])
    if g["isStarting"] == "True": lo, hi = 0, m[3] + 8
    else: lo, hi = dur - m[3] - 8, dur + 10
    if r[11] and str(r[11]).startswith("90+") and g["isStarting"] == "True" and m[3] >= 85: hi = max(hi, r[4])
    if not (lo <= r[4] <= hi): problems.append(("출전 구간 밖 기록", r[9], r[4], g["isStarting"], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const BRB_E={J(E)};\nconst BRB_M={J(M)};\nconst BRB_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY_A, "elo_sources": ELO_SRC, "assist_sources": SRC_A,
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}, "man_notes": {f"{k[0]}|{k[1]}": v for k, v in MAN_NOTE.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} · 도움 {dict(SRC_A)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
