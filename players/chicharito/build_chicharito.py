#!/usr/bin/env python3
"""Javier 'Chicharito' Hernández: raw/ -> chicharito.json + src/data/hdz.js (판정 근거는 judgments.md)

  python3 players/chicharito/build_chicharito.py            # 파일 쓰기
  python3 players/chicharito/build_chicharito.py --debug    # Elo 출처 로그
  python3 players/chicharito/build_chicharito.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/chicharito/build_chicharito.py --out DIR  # DIR/src/data/hdz.js 로 쓰기(검증용 복사본)

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골·도움), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv,
      raw/fotmob_events.csv(2010-11부터 골·도움 대조), raw/ranks.txt·ranks_wiki.txt(순위표),
      elo/opponent_elo_by_team_season.csv·aliases.csv, tools/league_rank_apply.py(순위 라벨 → Elo),
      src/data/*.js(git 추적 파일: 같은 경기 다른 선수 자료).
아넬카 build_anelka.py(같은 Transfermarkt 원자료 형식)를 바탕으로 함.
"""
import csv, json, os, re, sys, io, unicodedata, collections, subprocess, contextlib, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_ROOT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else ROOT
OUT_JS = os.path.join(OUT_ROOT, "src", "data", "hdz.js")
OUT_JSON = os.path.join(HERE, "chicharito.json")
ME = "50935"
ME_KO = "하비에르 에르난데스"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# 2022.8.3 리그스컵 쇼케이스(TM 'USMX') 과달라하라전은 친선경기(2022 Leagues Cup Showcase — 2022년 리그스컵 대회 대신 열린 친선 행사) → 뺌
EXCLUDE = {"3894944": "2022.8.3 리그스컵 쇼케이스 과달라하라전(친선경기)"}
GAMES = [g for g in rd("tm_games.csv") if g["gameId"] not in EXCLUDE]   # 1군 공식 경기(2군 Coras·Tapatío는 youth_reserve_games.csv, 넣지 않음)
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# 날짜: 수집본 date_local(유럽 = UTC 날짜, 아메리카 = UTC 시각 10시 전이면 전날). 00:00 UTC 자리표시 의심 18경기는 그대로 둠
# (확인한 1경기: 2006.9.9(토) 네캑사전 데뷔골 — chivasdecorazon.com.mx·TUDN '9 de septiembre' → 00:00 UTC = 현지 9.9 19:00, 수집본 날짜가 맞음)
DATE_FIX = {}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local"])
# 상대 이름 바꿈: Elo 통합표가 'CD Everton'(칠레)을 잉글랜드 에버턴과 같은 팀으로 묶지 않게 정식 이름으로
OPP_NAME = {"CD Everton": "CD Everton de Viña del Mar"}
def opp(g): return OPP_NAME.get(g["opponent"].strip(), g["opponent"].strip())

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "ES1", "L1", "MLS1", "MEXA", "MEX1", "USSP"}      # USSP = MLS is Back 2020 조별(나니 선례: 리그)
CUPS = {"FAC", "CGB", "CDR", "DFB", "MLSP"}                      # MLSP = US 오픈컵(TM 코드 이름)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth") or r.startswith("6th"): return "dk"   # FA컵 6라운드(재경기 포함)·리그컵 8강
        return "dc"                                                   # 리그컵 4라운드 = 16강
    if cid == "MEXP": return "df" if r.startswith("final") else "dc"  # 인터리가(리베르타도레스 진출전, 국내 대회) 조별·결승
    if cid == "GBCS": return "df"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"                                                  # 32강('Second Round'·'intermediate stage')·16강
    if cid == "CCL":
        if r.startswith("quarter"): return "ccck"
        return "ccc"                                                  # 1라운드·16강
    if cid == "CLI": return "lib"                                     # 조별
    if cid == "CS": return "csak" if r.startswith("quarter") else "csa"
    if cid == "SL": return "lcg"                                      # 북중미 슈퍼리가 조별 = 리그스컵 비중(§3)
    if cid in ("POMX", "POME", "POUS"):                               # 리길야·MLS 플레이오프 = MLS 플레이오프 비중(§3)
        if r.startswith("semi"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
        return "mlp"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def two_leg(cid, rnd):
    if cid == "FAC": return False        # FA컵 재경기는 단판
    return "leg" in rnd.lower()

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return 0
    if two_leg(cid, rnd): return 0
    if r.startswith("group"): return 0   # 챔스·유로파·리베르타도레스·슈퍼리가·인터리가 조별 = 리그식
    return 1

def tie_rule(g):
    """(원정 다득점, 연장)"""
    cid, d = g["competitionId"], ldate(g)
    if cid in ("CL", "CLQ", "EL", "CDR", "CGB"): return (1, 1)     # UEFA 2020-21까지·코파 델 레이 2018-19까지·리그컵 준결승 2017-18까지
    if cid == "CCL": return (1, 1) if d >= "2024-01-01" else (1, 0)  # 북중미 챔피언스컵 2024~ 원정 다득점·연장(지냑 선례), 그 전 연장 없음
    if cid == "CS": return (1, 0)
    if cid in ("POME", "POMX"): return (0, 0)                      # 리길야 8강·4강: 동률이면 정규리그 상위 팀(지냑 선례)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    """tm_two_leg_ties.csv 의 other_leg_final 은 이번 차전의 홈:원정 순서로 적혀 있음(아약스·코르네야·스포르팅 대조로 확인)"""
    oh, oa = map(int, TIES_RAW[gid]["other_leg_final"].split(":"))
    return (oh, oa) if side_of(gid) == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if not two_leg(g["competitionId"], g["round"]): return None
    s = side_of(gid)
    ag, et = tie_rule(g)
    leg = 1 if ("1st" in rnd or "first leg" in rnd) else 2
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

GAP = "2014-08-01"   # 이 날짜 뒤 TM 단독 도움은 다른 출처 2곳 필요
FMEV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FMEV[r["tm_gameId"]].append(r)
def fm_assist(gid, scorer_after):
    """FotMob 경기 이벤트에 치차리토 도움이 같은 스코어의 골에 있는가"""
    return any(r["chicharito_assist"] == "1" and r["score_after_home_away"] == scorer_after for r in FMEV.get(gid, []))

# 2014.8 뒤 TM 단독 도움 판정(judgments.md 4절, 경기 기사 검색)
SINGLE_A = {
    ("2505204", "34"): (True, "2014.12.2 코파 델 레이 코르네야 34분 하메스 — TM 도움, FotMob 없음. Sports Mole 문자중계('a clever flick from Hernandez finds James')·Bleacher Report 경기 기사('the Mexican used a delightful backheel touch to pick out James') → 넣음"),
    ("2475547", "83"): (True, "2015.5.17 에스파뇰 83분 호날두 — TM 도움, FotMob 없음. EFE 통신 기사(La Prensa HN·eju.tv 같은 글, 'Chicharito cedió el balón atrás al portugués')·messivsronaldo.app 경기 기록('Assisted by Chicharito') → 넣음(근거 중간)"),
    ("2699232", "67"): (False, "2016.8.21 DFB-포칼 하우엔슈타인 67분 벨라라비 — TM 도움, FotMob 없음. 바이어 04 구단 경기 기사('Chicharito squared the ball')뿐, ESPN·Maxifoot은 도움자 없음 → 다른 출처 2곳이 안 돼 뺌"),
}

def assist_reason(e):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    return None

BEFORE_FIX = {}
MIN_FIX = {}

raw_rows, judg = [], []
SEQ_DIFF = []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        bh, ba = (h - 1, a) if e["side"] == "home" else (h, a - 1)
        if (gid, e["minute"]) in BEFORE_FIX:
            bh, ba = BEFORE_FIX[(gid, e["minute"])]
        if (bh, ba) != prev: SEQ_DIFF.append((gid, ldate(g), e["minute"], (bh, ba), prev))
        prev = (bh + (e["side"] == "home"), ba + (e["side"] != "home"))
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("자책골(상대 득점, 본인 골 아님)", ldate(g), opp(g), e["minute"])); continue
        is_g = e["chicharito_scorer"] == "1" and not is_og(e)
        is_a = e["chicharito_assist_other"] == "1"
        if e["chicharito_self_assist"] == "1":
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if not (is_g or is_a): continue
        gf, ga = (bh, ba) if side == "h" else (ba, bh)
        if not ((e["side"] == "home") == (side == "h")) and not (is_a and is_og(e)):
            sys.exit("득점 편 이상 " + gid + " " + e["minute"])
        mstr = MIN_FIX.get((gid, e["minute"]), e["minute"])
        mi, dm = mins(mstr)
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if ldate(g) >= GAP and not fm_assist(gid, e["score_home_away_after"]):
                ok, txt = SINGLE_A.get((gid, e["minute"]), (None, None))
                if ok is None: sys.exit("2014.8 뒤 TM 단독 도움 판정 없음 " + gid + " " + e["minute"])
                judg.append(("2014.8 뒤 TM 단독 도움 " + ("넣음" if ok else "뺌"), ldate(g), opp(g), e["minute"], e["scorer"], txt))
                if not ok: continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

cnt = collections.Counter()
for r in raw_rows: cnt[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt[(gid, "g")] != int(g["goals"]): sys.exit("골 수 불일치 " + gid)
    if int(g["goals"]) and gid not in EVS: sys.exit("리포트 없음 " + gid)

# FotMob 대조(2010-11부터): 골 수·시각
FM_DIFF = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    if gid not in FMEV or typ != "g": continue
    hits = [r for r in FMEV[gid] if r["chicharito_scorer"] == "1"]
    if not hits: FM_DIFF.append(("FotMob 골 없음", gid)); continue
    mm_ = [int(r["minute"]) + int(r["overloadTime"] or 0) for r in hits]
    if min(abs(x - mi) for x in mm_) > 0: FM_DIFF.append(("골 시각", ldate(G[gid]), mi, mm_))
FM_ONLY_A = []   # FotMob 도움이 TM에 없는 경우
tmA = {(r[1]) for r in raw_rows if r[0] == "a"}
for gid, L in FMEV.items():
    for r in L:
        if r["chicharito_assist"] == "1" and gid in G:
            if not any(e["chicharito_assist_other"] == "1" and e["score_home_away_after"] == r["score_after_home_away"] for e in EVS.get(gid, [])):
                FM_ONLY_A.append((gid, r["date_tm"], r["minute"], r["scorer"]))

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

def tracked_data():
    try:
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True, check=True).stdout.split()
        return [os.path.join(ROOT, x) for x in out if x.endswith(".js")]
    except Exception:
        sys.exit("git ls-files 실패(병렬 판정 파일을 읽지 않으려고 추적 파일만 씀)")

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in tracked_data():
    b = os.path.basename(fn)
    if b in ("hon.js", "hdz.js", "clubcolors.js"): continue
    OTHERS[b] = load_js(fn)
BYDATE = collections.defaultdict(list)
for b, (P, oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "atletico", "calcio",
        "sport", "cd", "ud", "rcd", "sv", "as", "ss", "milan", "inter", "madrid", "ca", "fk", "sk", "ssc", "us", "balompie", "deportivo",
        "athletic", "racing", "olympique", "west", "wanderers", "rovers", "town", "albion", "hotspur", "county", "paris", "saint",
        "stade", "spor", "kulubu", "los", "angeles", "new", "york", "san", "red", "bulls", "uanl", "unam", "manchester"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
TOKS_LOG = []
NOT_SAME = set()
def same_match(o, d):
    if (o, d) in NOT_SAME: return [], set()
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    if not cand:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if toks(x[1]) & toks(o)]
        if cand: TOKS_LOG.append((o, d, sorted({(b, x[1], x[12]) for b, x in cand})))
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 → 라벨 → Elo(tools/league_rank_apply.py와 같은 값)
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    RA = runpy.run_path(os.path.join(ROOT, "tools", "league_rank_apply.py"), run_name="ra")
sys.argv = _argv

def ra_value(lv, d):
    p = RA["parse"](lv, d)
    if not p: sys.exit("순위 라벨 해석 실패 " + lv)
    v = RA["value"](*p)
    if v is None: sys.exit("기준 없음 " + lv)
    return v

# 리가MX: 경기 날짜에 진행 중이던 단계(아페르투라·클라우수라)의 정규리그 순위.
# 2006~09 TM 표는 6팀 3개 조 → 18팀 전체 순위(승점→득실차→다득점, 리가MX 전체 순위표 규칙)로 합침(수집본 'DERIVED combined')
MX_TABLE = {   # (단계 이름, 라벨 시즌) -> ranks.txt (league, season, 표)
    "아페르투라 2006": ("MEXA", "2006-07 Apertura", "DERIVED", "2006-07"),
    "클라우수라 2007": ("MEX1", "2006-07 Clausura", "DERIVED", "2006-07"),
    "아페르투라 2007": ("MEXA", "2007-08 Apertura", "DERIVED", "2007-08"),
    "클라우수라 2008": ("MEX1", "2007-08 Clausura", "DERIVED", "2007-08"),
    "아페르투라 2008": ("MEXA", "2008-09 Apertura", "DERIVED", "2008-09"),
    "클라우수라 2009": ("MEX1", "2008-09 Clausura", "DERIVED", "2008-09"),
    "아페르투라 2009": ("MEXA", "2009-10 Apertura", "table1", "2009-10"),
    "비센테나리오 2010": ("MEX1", "2009-10 Bicentenario (=Clausura 2010)", "DERIVED", "2009-10"),
    "클라우수라 2024": ("MEX1", "2023-24 Clausura", "table1", "2023-24"),
    "아페르투라 2024": ("MEXA", "2024-25 Apertura", "table1", "2024-25"),
    "클라우수라 2025": ("MEX1", "2024-25 Clausura", "table1", "2024-25"),
    "아페르투라 2025": ("MEXA", "2025-26 Apertura", "table1", "2025-26"),
}
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 6 or p[0] == "league": continue
        RANKS[(p[0], p[1], p[5].split()[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

def mx_stage(d):
    y, mo = int(d[:4]), int(d[5:7])
    if y == 2010 and mo <= 6: return "비센테나리오 2010"
    return ("아페르투라 %d" % y) if mo >= 7 else ("클라우수라 %d" % y)

def mx_label(o, d):
    st = mx_stage(d)
    lg, s, tb, sea = MX_TABLE[st]
    t = RANKS[(lg, s, tb)]
    k = key(o)
    if k not in t: return None
    r, n, _ = t[k]
    stage = st.replace("비센테나리오 2010", "클라우수라 2010(비센테나리오)")
    kind = "조별 표를 합친 전체 순위" if tb == "DERIVED" else "정규리그 순위"
    return f"멕시코 1부 {sea} {r}위/{n}팀 (Liga MX {stage}, 경기 날짜에 진행 중이던 단계의 {kind})"

MEX_TEAMS = set()
for (lg, s, tb), t in RANKS.items():
    if lg in ("MEXA", "MEX1"): MEX_TEAMS |= set(t)

# MLS 전체 순위(서포터스 실드 순서): 통합표에 없는 팀-시즌만 — judgments.md 7절(위키백과 시즌 문서 Overall table로 확인)
MLS_N = {"2020": 26, "2021": 27, "2022": 28, "2023": 29}
MLS_ORDER = {   # 영어 위키백과 Template:<연도> Major League Soccer season table 의 team_order(전체 순위; 2020은 승점률 순)
    "2020": "PHI, TOR, SKC, CLB, ORL, SEA, NYC, POR, MIN, COL, DAL, LFC, NYR, NSH, NEW, SJO, VAN, MTL, MIA, LAX, RSL, CHI, ATL, DCU, HOU, CIN",
    "2021": "NEW, COL, SEA, SKC, POR, PHI, NSH, NYC, ATL, ORL, MIN, VAN, RSL, NYR, LAX, DCU, CLB, MTL, LFC, MIA, SJO, CHI, DAL, AUS, HOU, TOR, CIN",
    "2022": "LFC, PHI, MTL, AUS, NYC, NYR, DAL, LAX, NSH, CIN, MIN, MIA, ORL, RSL, POR, CLB, VAN, COL, CLT, NEW, SEA, SKC, ATL, CHI, HOU, SJO, TOR, DCU",
    "2023": "CIN, ORL, CLB, STL, PHI, NEW, SEA, LFC, HOU, ATL, RSL, NSH, VAN, DAL, SKC, SJO, NYR, POR, CLT, MTL, MIN, NYC, DCU, CHI, AUS, LAX, MIA, COL, TOR"}
MLS_CODE = {"Portland Timbers": "POR", "Seattle Sounders FC": "SEA", "New York Red Bulls": "NYR", "Los Angeles FC": "LFC", "Austin FC": "AUS",
            "Vancouver Whitecaps FC": "VAN", "Houston Dynamo FC": "HOU", "Real Salt Lake City": "RSL", "FC Dallas": "DAL",
            "Minnesota United FC": "MIN", "Colorado Rapids": "COL", "San Jose Earthquakes": "SJO"}
MLS_RANK = {}
for nm, c in MLS_CODE.items():
    for y, order in MLS_ORDER.items():
        L = [x.strip() for x in order.split(",")]
        assert len(L) == MLS_N[y]
        if c not in L: continue
        MLS_RANK[(key(nm), y)] = f"MLS {y} {L.index(c) + 1}위/{len(L)}팀" + (" (정규시즌 승점률 순위)" if y == "2020" else "")
# 순위표에 없는 팀-시즌(직접 확인한 라벨)
MANUAL_LV = {
    ("CD Everton de Viña del Mar", "2009-02-25"): "칠레 1부 2009 3위/18팀 (Primera División 아페르투라 2009 정규 단계, 경기 날짜에 진행 중이던 단계 순위)",
    ("CD Everton de Viña del Mar", "2009-04-29"): "칠레 1부 2009 3위/18팀 (Primera División 아페르투라 2009 정규 단계, 경기 날짜에 진행 중이던 단계 순위)",
}
MANUAL_LV.update({
    ("AFC Wimbledon", "2018-08-28"): "잉글랜드 3부 2018-19 20위/24팀 (Football League One, 리그 수준 추정)",       # TM GB3 2018-19 표(우승 루턴)
    ("Qarabağ FK", "2019-09-19"): "아제르바이잔 1부 2019-20 1위/8팀 (Azerbaijan Premier League, 코로나로 중단·카라바흐 우승 확정)",
    ("APOEL Nicosia", "2019-10-03"): "키프로스 1부 2019-20 3위/12팀 (Cypriot First Division, 코로나로 1단계 22라운드 뒤 중단·우승 없음)",
})
# 도구가 읽지 못하는 나라(도미니카공화국): 도구와 같은 식(Opta 리그 점수 → Elo, 흩어짐 60 × 순위 곡선)으로 직접 계산, 라벨 '추정'
def dom_value(rk, n):
    o = RA["OPTA"]["Liga Mayor|Dominican Republic"]
    return int(round(RA["OA"] + RA["OB"] * o + 60.0 * RA["cv"](rk, n)))
MANUAL_EST = {
    ("Cibao FC", "2025-02-12"): (dom_value(1, 8), "도미니카공화국 1부 2024 1위/8팀 (Liga Dominicana de Fútbol 2024 우승, 2025 시즌 개막 전; 추정: 순위 도구 밖 나라라 같은 식으로 직접 계산)"),
}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

def opp_elo(o, d, cid, gid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1:
        print("  [같은 경기 값 여럿]", o, d, vals)
    if (o, d) in MANUAL_EST:
        e, lv = MANUAL_EST[(o, d)]; ELO_SRC["직접 추정(도구 밖 나라)"] += 1; ELO_LOG[(o, d)] = ("est", e, lv); return e, lv
    if (o, d) in MANUAL_LV:
        lv = MANUAL_LV[(o, d)]; e = ra_value(lv, d)
        ELO_SRC["직접 확인 라벨(새 팀-시즌)"] += 1; ELO_LOG[(o, d)] = ("manual", e, lv); return e, lv
    k = key(o)
    if k in MEX_TEAMS:
        lv = mx_label(o, d)
        if lv:
            e = ra_value(lv, d); ELO_SRC["리가MX 단계 순위"] += 1; ELO_LOG[(o, d)] = ("mx", e, lv); return e, lv
    if cid in ("MLS1", "USSP", "MLSP", "POUS"):
        seasons = [d[:4]]
        if (k, d[:4]) in MLS_RANK:
            lv = MLS_RANK[(k, d[:4])]; e = ra_value(lv, d)
            ELO_SRC["MLS 순위(새 팀-시즌)"] += 1; ELO_LOG[(o, d)] = ("mls", e, lv); return e, lv
    else:
        seasons = [eu(d)]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    MISS.append((o, d, cid, tuple(seasons), gid)); return 0, "?"

# ---------------------------------------------------------------- 기록 행
E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, gid)
    et = 1 if (g["gameState"] != "regularly_terminated" and mi > 90 and not str(dm).startswith("90+")) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    for m in MISS: print("Elo 없음:", m)
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda x: x[0][1]):
        if v[0] != "table": print(d, o, v)
    print("SEQ_DIFF", SEQ_DIFF)
    print("FM_DIFF", FM_DIFF)
    print("FM_ONLY_A", FM_ONLY_A)
    for t in TOKS_LOG: print("TOKS", t)
    for j in judg: print("judg", j)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("gdljh", "2010-07-01", "과달라하라", "2006~2010", "6711"),
         ("mujh", "2014-09-01", "맨체스터 유나이티드", "2010~2014", "985"),
         ("rmjh", "2015-07-01", "레알 마드리드", "2014~2015", "418"),
         ("mujh", "2015-08-31", "맨체스터 유나이티드", "2015", "985"),
         ("levjh", "2017-07-24", "바이어 레버쿠젠", "2015~2017", "15"),
         ("whujh", "2019-09-02", "웨스트햄 유나이티드", "2017~2019", "379"),
         ("sevjh", "2020-01-21", "세비야", "2019~2020", "368"),
         ("lagjh", "2024-01-24", "LA 갤럭시", "2020~2023", "1061"),
         ("gdljh", "2026-07-27", "과달라하라", "2024~2025", "6711"),
         ("adljh", None, "아틀레티코 댈러스", "2026~", "130372")]
def club_of(d):
    for c in CLUBS:
        if c[1] is None or d < c[1]: return c[0]
ST = collections.OrderedDict()
for c in CLUBS:
    ST.setdefault(c[0], [0, 0, 0, 0])
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    c = next(x for x in CLUBS if x[1] is None or ldate(g) < x[1])
    if c[4] != g["club_id"]: sys.exit("클럽 경계 불일치 " + g["gameId"])
SPELL = collections.OrderedDict()
for m in M:
    c = next(x for x in CLUBS if x[1] is None or m[0] < x[1])
    SPELL.setdefault(c[1], [c[2], c[3], 0, 0, 0, 0])[2] += 1; SPELL[c[1]][5] += m[3]
for r in E:
    c = next(x for x in CLUBS if x[1] is None or r[9] < x[1])
    SPELL[c[1]][3 if r[0] == "g" else 4] += 1
JULY = sorted({(club_of(m[0]), m[0]) for m in M if m[0][5:7] == "07"})
if "--debug" in sys.argv:
    for k, v in SPELL.items(): print(k, v)
    print("7월 경기", JULY)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    ta = a[14] if len(a) > 14 and a[14] else None; tb = b[14] if len(b) > 14 and b[14] else None
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    return diffs
MYG = [r for r in E if r[0] == "g"]
for b, (P, ent, om) in OTHERS.items():
    for x in ent:
        if x[0] == "a" and re.search(r"Chicharito|Hern[aá]ndez", str(x[13])) and "Juan" not in str(x[13]) and "Pablo" not in str(x[13]):
            hit = sorted([r for r in MYG if r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append(("동료 도움→치차리토 골", b, x[9], x[4], x[13], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
for r in E:
    if r[0] != "a": continue
    found = False
    for b, x in BYDATE.get(r[9], []):
        if x[0] == "g" and abs(x[4] - r[4]) <= 3 and (x[5], x[6]) == (r[5], r[6]) and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])):
            CROSS.append(("치차리토 도움→동료 골", b, r[9], r[4], r[13], cmp_rows(r, x) or "같음")); found = True
for b, (P, ent, om) in OTHERS.items():
    seen_d = set()
    for x in ent:
        if x[9] in seen_d: continue
        for r in E:
            if r[9] == x[9] and (key(r[1]) == key(x[1]) or toks(r[1]) & toks(x[1])):
                d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                CROSS.append(("같은 경기", b, r[9], r[1], d or "같음")); seen_d.add(x[9]); break
    mm_ = {m[0]: m for m in M}
    for m in om:
        fm = mm_.get(m[0])
        if fm and (key(fm[1]) == key(m[1]) or toks(fm[1]) & toks(m[1])):
            CROSS.append(("출전 행", b, m[0], fm[1], "같음" if fm[2] == m[2] else f"대회 {fm[2]}/{m[2]}"))
if "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
    print(collections.Counter((c[0], c[1]) for c in CROSS if c[0] != "출전 행"))

exec(open(os.path.join(HERE, "note_chicharito.py"), encoding="utf-8").read())

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
    gs = sorted({(r[5], r[6], r[4]) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
    for a, b in zip(gs, gs[1:]):
        if b[0] < a[0] or b[1] < a[1]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
    if len({(r[1], r[3]) for r in rs}) > 1: problems.append(("같은 날 상대·대회 다름", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
mm = {m[0]: m for m in M}
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[4] > 90 and not r[10] and not r[11] and not (r[14] if len(r) > 14 else None): problems.append(("90분 초과 표기 없음", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if MISS: problems.append(("Elo 없음", MISS))
if problems and not ({"--debug", "--cross"} & set(sys.argv)):
    for p in problems: print("점검:", p)
    sys.exit(1)

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and not ({"--debug", "--cross"} & set(sys.argv)):
    open(OUT_JS, "w", encoding="utf-8").write(f"const HDZ_E={J(E)};\nconst HDZ_M={J(M)};\nconst HDZ_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "elo_sources": ELO_SRC, "elo_log": {f"{d} {o}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in SPELL.items(): print(" ", k, v)
