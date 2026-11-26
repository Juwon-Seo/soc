#!/usr/bin/env python3
"""Diego Tristán: raw/ -> tristan.json + players/tristan/tri.js (판정 근거는 judgments.md)

  python3 players/tristan/build_tristan.py                 # players/tristan/tri.js, tristan.json 쓰기
  python3 players/tristan/build_tristan.py --debug         # Elo 출처 로그·판정 목록
  python3 players/tristan/build_tristan.py --cross         # 같은 경기 다른 선수 자료 대조
  python3 players/tristan/build_tristan.py --out DIR       # DIR/src/data/tri.js 로 쓰기(검증용 복사본)
  SOC_ELO=<폴더>                                           # 상대 Elo 통합표 폴더(기본: 저장소 elo/; 검증 때는 src/data에서 새로 만든 표)

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골·도움), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv,
      raw/ranks.txt(순위표), elo/opponent_elo_by_team_season.csv·aliases.csv, tools/league_rank_apply.py(순위 라벨 → Elo),
      src/data/*.js(git 추적 파일만: 같은 경기 다른 선수 자료).
페르난도 모리엔테스 build_morientes.py(같은 수집 형식)를 바탕으로 함.
"""
import csv, json, os, re, sys, io, unicodedata, collections, subprocess, contextlib, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(os.path.dirname(HERE))
ELO = os.environ.get("SOC_ELO") or os.path.join(ROOT, "elo")
OUT_JS = os.path.join(sys.argv[sys.argv.index("--out") + 1], "src", "data", "tri.js") if "--out" in sys.argv else os.path.join(HERE, "tri.js")
OUT_JSON = os.path.join(HERE, "tristan.json")
ME = "7504"
ME_KO = "디에고 트리스탄"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 범위
# 마요르카 B(TM 8494, 1998-99 세군다): 2군 팀 → 제외(마타 카스티야 선례). 베티스 B(세군다 B, TM 경기 없음)·리보르노 유소년 1경기도 제외.
RESERVE_CLUBS = {"8494"}
ALL = rd("tm_games.csv")
GAMES = [g for g in ALL if g["club_id"] not in RESERVE_CLUBS]
EXCL_RES = [g for g in ALL if g["club_id"] in RESERVE_CLUBS]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# ---------------------------------------------------------------- 판정 표(judgments.md)
# 1) 2004.10.26 코파 델 레이 세르세다 0-2 데포르티보: TM 리포트에 골 목록이 없고 API 골 0.
#    BDFutbol 경기 기록(22'·83'), RSSSF 'Spain Cup 2004/05'(23'·81'), soccer-spain.com 기사(전반 중반·종료 10분 전) 모두 트리스탄 2골 → 넣음.
#    분·순서는 BDFutbol(경기 단위 기록), 출전 분은 TM 90 그대로.
ADD_GOALS = {"2423179": [("22", "0-1", "away"), ("83", "0-2", "away")]}
GOALS_FIX = {"2423179": 2}
# 2) PK 표기: TM 리포트는 일반 골, BDFutbol은 PK. 세 번째 출처로 PK 확인 → PK
PEN_FIX = {
    "35977|45": "2005.9.21 베티스전 45분: soccer-spain.com 경기 기사 '45. Diego Tristán (penalty)'·voetbalkrant 기사(페널티킥 성공)·BDFutbol",
    "958341|50": "2010.6.19 누만시아전 50분: ESPN 경기 기록 'Penalty - Scored' 49분 Diego Tristán·BDFutbol",
}
# 3) 2005.11.20 라싱전 16분: TM 트리스탄 골 vs BDFutbol 네루 자책골 17분 → soccer-spain.com 경기 기사 '0-1. 17. Diego Tristán.
#    Turned Capdevila cross past keeper with help from Neru' → 트리스탄 골(TM 그대로, 분은 TM 16)
# 4) 2006.1.4 코파 16강 1차전 오사수나: TM 4-0(골 목록 3개) vs BDFutbol·위키백과 3-0 → 3-0(트리스탄 행 없음, 2차전 출전 없음)
SCORE_FIX = {"2423088": "3:0"}
GAP = "2014-08-01"   # 이 날 이후 경기 없음 → 모든 도움은 2014년 이전 TM 단일 출처 규칙

# 5) 날짜: TM 날짜 그대로(다른 선수 자료와 같음). 단 2003.10.7 코파 델 레이 콤포스텔라 원정(0-1, 트리스탄 82분 골)은 TM 2003.10.8(UTC 22:00 자정 자리값)
#    → BDFutbol 2003.10.7, El Mundo(사망 사건 '2003년 10월 7일 밤')·The Star('Tuesday night') → 2003.10.7
DATE_FIX = {"2423236": "2003-10-07"}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local"])
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES1", "ES2", "IT1", "GB1"}
CUPS = {"CDR", "CIT", "FAC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or (cid == "FAC" and r.startswith("sixth")): return "dk"
        return "dc"                               # 2·3·4라운드, 16강, FA컵 3·5라운드(재경기 포함), 코파 이탈리아 3라운드
    if cid == "SUC": return "df"                  # 수페르코파 = 국내컵 결승 비중
    if cid == "CLQ": return "clq"
    if cid == "UI": return "elq"                  # 인터토토컵 = 유로파 예선(발레론·포를란·토레스 선례)
    if cid == "CL":
        if r.startswith("group"): return "clg"    # 2000-01·2001-02 2차 조별 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                    # 2·3라운드·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return 0
    if "leg" in r: return 0
    if r.startswith("group"): return 0
    return 1

def tie_rule(cid):
    """(원정 다득점, 연장) — 1999~2010 UEFA 대회·인터토토·코파 델 레이·수페르코파 모두 원정 다득점·연장(마카이·발레론 선례)"""
    if cid in ("UEFA", "CL", "CLQ", "UI", "CDR", "SUC"): return (1, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid, club_id=None):
    m = MI[gid]; cid = club_id or G[gid]["club_id"]
    if m["home_id"] == cid: return "h"
    if m["away_id"] == cid: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid, club_id):
    m = MI[gid]
    oid = m["other_leg_id"] or TIES_RAW[gid]["other_leg_gameId"]
    if oid in MI:
        o = MI[oid]
        oh, oa = map(int, SCORE_FIX.get(oid, o["final"]).split(":"))
        if o["home_id"] == club_id: return (oh, oa)
        if o["away_id"] == club_id: return (oa, oh)
        sys.exit("다른 차전 팀 불일치 " + gid)
    # 리포트가 없는 다른 차전: tm_two_leg_ties.csv 점수(홈-원정)와 이번 경기 홈/원정의 반대
    t = TIES_RAW[gid]; oh, oa = map(int, t["other_leg_score_home_away"].split("-"))
    return (oa, oh) if side_of(gid, club_id) == "h" else (oh, oa)

def tie_of(gid, cid, rnd, club_id):
    rnd = rnd.lower()
    if "leg" not in rnd: return None
    s = side_of(gid, club_id)
    ag, et = tie_rule(cid)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid, club_id)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(G.values(), key=lambda g: (ldate(g), g["gameId"])):
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
    if t == "Deflected": return "굴절"
    return None

for gid, gl in ADD_GOALS.items():
    if EVS.get(gid): sys.exit("추가 골 경기에 TM 골 목록이 있음 " + gid)
    for mn, sc, sd in gl:
        EVS[gid].append({"minute": mn, "score_home_away_after": sc, "side": sd, "scorer": "Diego Tristán", "scorer_id": ME,
                         "goal_desc": "", "assist_player": "", "assist_id": "", "assist_type": "", "penalty": "0", "own_goal": "0",
                         "tristan_scorer": "1", "tristan_assist_other": "0", "tristan_self_assist": "0", "src": "bdfutbol"})

INCOMPLETE = {"2423088"}   # TM 4-0인데 골 목록 3개(오사수나) — 트리스탄 행 없음
raw_rows, judg = [], []
SEQ_DIFF = []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        bh, ba = (h - 1, a) if e["side"] == "home" else (h, a - 1)
        if (bh, ba) != prev and gid not in INCOMPLETE: SEQ_DIFF.append((gid, ldate(g), e["minute"], (bh, ba), prev))
        prev = (h, a)
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("자책골(상대 득점, 본인 골 아님)", ldate(g), opp(g), e["minute"])); continue
        is_g = e["tristan_scorer"] == "1" and not is_og(e)
        is_a = e["tristan_assist_other"] == "1"
        if e["tristan_self_assist"] == "1":
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if not (is_g or is_a): continue
        gf, ga = (bh, ba) if side == "h" else (ba, bh)
        if not ((e["side"] == "home") == (side == "h")) and not (is_a and is_og(e)):
            sys.exit("득점 편 이상 " + gid + " " + e["minute"])
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
                judg.append(("PK 아님(PK가 막힌 뒤 리바운드 골)", ldate(g), opp(g), e["minute"]))
            tag = gid + "|" + e["minute"]
            if tag in PEN_FIX:
                if pk: sys.exit("PEN_FIX 불필요 " + tag)
                pk = 1; judg.append(("PK로 고침", ldate(g), opp(g), e["minute"], PEN_FIX[tag]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))
for t in PEN_FIX:
    if not any(r[0] == "g" and r[1] + "|" + str(r[3] or r[2]) == t for r in raw_rows): sys.exit("PEN_FIX 대상 없음 " + t)

cnt = collections.Counter()
for r in raw_rows: cnt[(r[1], r[0])] += 1
for gid, g in G.items():
    want = GOALS_FIX.get(gid, int(g["goals"]))
    if cnt[(gid, "g")] != want: sys.exit("골 수 불일치 " + gid + f" {cnt[(gid, 'g')]} vs {want}")
    if want and gid not in EVS: sys.exit("리포트 없음 " + gid)
    if cnt[(gid, "a")] > int(g["assists"]): sys.exit("도움 수 초과 " + gid)

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
MANUAL_ALIAS = {"inter milan": "inter", "rcd espanol": "rcd espanyol barcelona"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"].split("·") == [ME_KO]: continue   # 트리스탄만 쓴 팀-시즌(다시 만든 통합표)은 건너뜀(오스카 빌드 수정과 같음)
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

def tracked_data():
    try:
        out = subprocess.run(["git", "-C", REPO, "ls-files", "src/data"], capture_output=True, text=True, check=True).stdout.split()
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
    if b in ("hon.js", "tri.js", "clubcolors.js", "finals.js") or not os.path.exists(fn): continue
    OTHERS[b] = load_js(fn)
BYDATE = collections.defaultdict(list)
for b, (P, oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "atletico", "calcio",
        "sport", "cd", "ud", "rcd", "sv", "as", "ss", "milan", "inter", "madrid", "ca", "fk", "sk", "ssc", "us", "balompie", "deportivo",
        "bilbao", "athletic", "racing", "vigo", "olympique", "bk", "rc", "barcelona", "coruna", "la", "sociedad", "sevilla", "betis"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d, cid):
    """같은 날 같은 상대를 다룬 다른 선수 자료. 국내 경기는 팀 키가 같을 때만(요렌테 판정의 에스파뇰/바르셀로나 오인 방지)"""
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    if not cand and cid in ("CL", "CLQ", "UEFA", "UI"):
        cand = [(b, x) for b, x in BYDATE.get(d, []) if toks(x[1]) & toks(o) and x[3] not in ("lg",)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 → 라벨 → Elo(tools/league_rank_apply.py와 같은 값)
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    RA = runpy.run_path(os.path.join(ROOT, "tools", "league_rank_apply.py"), run_name="ra")
sys.argv = _argv

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[0].startswith("#"): continue
        RANKS[(p[0].split(" ")[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
def tmlab(s): return s[2:4] + "/" + s[5:7]

def label(lg, s, r, n):
    if lg == "ES1": return f"라리가 {s} {r}위"
    if lg == "ES2": return f"세군다 {s} {r}위/{n}팀"
    if lg in ("ES3A", "ES3B", "ES3C", "ES3D"):
        grp = {"ES3A": "Grupo I", "ES3B": "Grupo II", "ES3C": "Grupo III", "ES3D": "Grupo IV"}[lg]
        return f"스페인 3부 {s} {r}위/{n}팀 (Segunda División B {grp}, 리그 수준 추정)"
    if lg == "GB1": return f"프리미어리그 {s} {r}위"
    if lg == "GB2": return f"챔피언십 {s} {r}위/{n}팀"
    if lg == "IT1": return f"세리에A {s} {r}위" + (f"/{n}팀" if n != 20 else "")
    if lg == "L1": return f"분데스리가 {s} {r}위"
    if lg == "FR1": return f"리그1 {s} {r}위" + (f"/{n}팀" if n != 20 else "")
    if lg == "NL1": return f"에레디비시 {s} {r}위"
    if lg == "PO1": return f"포르투갈 1부 {s} {r}위" + (f"/{n}팀" if n != 18 else "")
    C = {"GR1": "그리스", "NO1": "노르웨이", "TR1": "튀르키예", "TS1": "체코", "C1": "스위스", "KR1": "크로아티아"}
    if lg in C: return f"{C[lg]} 1부 {s} {r}위/{n}팀"
    return None

def ra_value(lv, d):
    p = RA["parse"](lv, d)
    if not p: sys.exit("순위 라벨 해석 실패 " + lv)
    v = RA["value"](*p)
    if v is None: sys.exit("기준 없음 " + lv)
    return v

CAL = {"NO1"}
# 순위표 밖이거나 시즌 선택이 다른 상대(judgments.md 6절): (상대 키, 날짜) -> 라벨
LABEL_FIX = {
    # 세르세다 2004-05: TM 표 없음 → 영어 위키백과 2004–05 Tercera División Group I 최종 6위/20팀(raw/wiki)
    (key("CCD Cerceda (- 2018)"), "2004-10-26"): "스페인 4부 2004-05 6위/20팀 (Tercera División Grupo I, 리그 수준 추정)",
    # 슬라벤 벨루포 2005.7.23(인터토토): 크로아티아 2005-06 시즌이 2005.7.20 시작 → 진행 중 시즌의 최종 순위
    # (영어 위키백과 2005–06 Croatian First Football League: 강등 그룹 2위 = 전체 8위/12팀, 승점 41)
    (key("Slaven Belupo Koprivnica"), "2005-07-23"): "크로아티아 1부 2005-06 8위/12팀",
}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1:
        print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    if (k, d) in LABEL_FIX:
        lv = LABEL_FIX[(k, d)]; e = ra_value(lv, d)
        ELO_SRC["순위표+순위 규칙(새 팀-시즌)"] += 1; ELO_LOG[(o, d)] = ("model", e, lv, d); return e, lv
    s0 = eu(d)
    seasons = [s0, d[:4]]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    cands = []
    for (lg, sl), t in RANKS.items():
        if k not in t: continue
        if lg in CAL:
            if sl != d[:4]: continue
            disp = sl
        else:
            if sl != tmlab(s0): continue
            disp = s0
        cands.append((lg, sl, disp, t[k]))
    if len(cands) > 1: print("  [순위표 여럿]", o, d, [(c[0], c[1], c[3][:2]) for c in cands])
    if cands:
        lg, sl, disp, (r, n, _) = cands[0]
        lv = label(lg, disp, r, n)
        if lv:
            e = ra_value(lv, d)
            ELO_SRC["순위표+순위 규칙(새 팀-시즌)"] += 1; ELO_LOG[(o, d)] = ("model", e, lv, disp); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

# ---------------------------------------------------------------- 기록 행
E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (g["gameState"] != "regularly_terminated" and mi > 90 and dm == 0) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid, cid, rnd, g["club_id"])
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    for m in MISS: print("Elo 없음:", m)
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda x: x[0][1]):
        if v[0] != "same": print(d, o, v)
    print("SEQ_DIFF", SEQ_DIFF)
    for j in judg: print("judg", j)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("mltr", "2000-07-01", "마요르카", "1999~2000", "237"),
         ("deptr", "2006-09-01", "데포르티보 라코루냐", "2000~2006", "897"),
         ("mltr2", "2007-07-01", "마요르카", "2006~2007", "237"),
         ("livtr", "2008-10-01", "리보르노", "2007~2008", "1210"),
         ("whutr", "2009-07-01", "웨스트햄 유나이티드", "2008~2009", "379"),
         ("cadtr", None, "카디스", "2009~2010", "2687")]
def club_of(d):
    for c in CLUBS:
        if c[1] is None or d < c[1]: return c[0]
ST = collections.OrderedDict((c[0], [0, 0, 0, 0]) for c in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for gid, g in G.items():
    c = club_of(ldate(g))
    if [x for x in CLUBS if x[0] == c][0][4] != g["club_id"]: sys.exit("클럽 경계 불일치 " + gid)
JULY = sorted({(club_of(m[0]), m[0]) for m in M if m[0][5:7] == "07"})
if "--debug" in sys.argv:
    for k, v in ST.items(): print(k, v)
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
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 and b[14] else None
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    return diffs
MYG = [r for r in E if r[0] == "g"]
for b, (P, ent, om) in OTHERS.items():
    for x in ent:
        if x[0] == "a" and "Tristán" in str(x[13]) or (x[0] == "a" and "Tristan" in str(x[13])):
            hit = sorted([r for r in MYG if r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append(("동료 도움→트리스탄 골", b, x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
for r in E:
    if r[0] != "a": continue
    for b, x in BYDATE.get(r[9], []):
        if x[0] == "g" and abs(x[4] - r[4]) <= 3 and (x[5], x[6]) == (r[5], r[6]) and key(x[1]) == key(r[1]):
            CROSS.append(("트리스탄 도움→동료 골", b, r[9], r[4], r[13], cmp_rows(r, x) or "같음"))
for b, (P, ent, om) in OTHERS.items():
    seen_d = set()
    for x in ent:
        if x[9] in seen_d: continue
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                CROSS.append(("같은 경기", b, r[9], r[1], dd or "같음")); seen_d.add(x[9]); break
    mm_ = {m[0]: m for m in M}
    for m in om:
        fm = mm_.get(m[0])
        if fm and key(fm[1]) == key(m[1]):
            CROSS.append(("출전 행", b, m[0], fm[1], "같음" if fm[2] == m[2] else f"대회 {fm[2]}/{m[2]}"))
# TM이 트리스탄 도움으로 적었지만 뺀 것이 동료 파일에서 도움 없는 골인지(참고)
if "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
    print(collections.Counter((c[0], c[1]) for c in CROSS if c[0] != "출전 행"))

exec(open(os.path.join(HERE, "note_tristan.py"), encoding="utf-8").read())

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
    if r[4] > 90 and not r[10] and not r[11]: problems.append(("90분 초과 표기 없음", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r))
    if r[9] >= GAP and r[0] == "a": problems.append(("2014.8 이후 도움", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if MISS: problems.append(("Elo 없음", MISS))
if SEQ_DIFF: problems.append(("골 순서 스코어", SEQ_DIFF))
if problems:
    for p in problems: print("점검:", p)
    if "--debug" not in sys.argv: sys.exit(1)

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and not ({"--debug", "--cross"} & set(sys.argv)):
    open(OUT_JS, "w", encoding="utf-8").write(f"const TRI_E={J(E)};\nconst TRI_M={J(M)};\nconst TRI_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "excluded_reserve_games": [[g["date_local"], g["club"], g["opponent"], g["competitionId"], g["playedMinutes"], g["goals"], g["assists"]] for g in EXCL_RES],
               "elo_sources": ELO_SRC, "elo_log": {f"{d} {o}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
