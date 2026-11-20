#!/usr/bin/env python3
"""Frédéric Kanouté: raw/ -> kanoute.json + src/data/knt.js (판정 근거는 judgments.md)

  python3 players/kanoute/build_kanoute.py            # 파일 쓰기
  python3 players/kanoute/build_kanoute.py --debug    # Elo 출처 로그
  python3 players/kanoute/build_kanoute.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/kanoute/build_kanoute.py --out DIR  # DIR/src/data/knt.js 로 쓰기(검증용 복사본)

입력: raw/tm_games.csv(출전·분·TM 일정 날짜), raw/tm_events.csv(리포트 골·도움), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv,
      raw/fotmob_events.csv(2010-11부터 골 대조), raw/ranks.txt·ranks_wiki.txt(순위표),
      elo/opponent_elo_by_team_season.csv·aliases.csv, tools/league_rank_apply.py(순위 라벨 → Elo),
      src/data/*.js(git 추적 파일만: 같은 경기 다른 선수 자료).
아넬카 build_anelka.py(같은 Transfermarkt 원자료 형식)를 바탕으로 함.
"""
import csv, json, os, re, sys, io, unicodedata, collections, subprocess, contextlib, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_ROOT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else ROOT
OUT_JS = os.path.join(OUT_ROOT, "src", "data", "knt.js")
OUT_JSON = os.path.join(HERE, "kanoute.json")
ME = "3700"
ME_KO = "프레데리크 카누테"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")          # 성인 클럽 경기만(유소년·2군 경기는 TM API에 없음)
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

def ldate(g):
    """TM 일정 날짜(= 리포트 날짜, 현지). API UTC 23:00/22:00(킥오프 시각 없음)을 런던 시각으로 바꾸면 하루 앞서는 잉글랜드 컵 8경기·풀럼전은 일정 날짜"""
    return g["date_local_schedule"]
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "FR1", "ES1", "CSL"}
CUPS = {"FAC", "CGB", "CDR", "FRC", "FRL", "CHFA"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth"): return "dk"   # FA컵 6라운드·리그컵 'Quarter-Finals' = 8강
        return "dc"                                              # FA컵 재경기('4th/5th round deciders') = 그 라운드
    if cid in ("USC", "SUC"): return "df"                        # UEFA 슈퍼컵·수페르코파 = 국내컵 결승 비중(나바스·사비올라·이니에스타 선례)
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid in ("UI", "ELQ"): return "elq"                        # 인터토토컵(결승 포함)·유로파 예선
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"             # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"                   # 2004~2009 UEFA컵 조별
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                             # 2·3라운드·32강('intermediate stage')·16강·8강
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                             # 2010-11 'Second Round' = 32강
    if cid == "AFCL":
        if r.startswith("group"): return "acl"
        if r.startswith("semi"): return "aclsf"
        if r.startswith("final"): return "aclf"
        return "aclk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def two_leg(cid, rnd):
    if cid == "FAC": return False
    return "leg" in rnd.lower()

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return 0
    if two_leg(cid, rnd): return 0
    if r.startswith("group"): return 0   # 인터토토·챔스·UEFA컵·유로파·AFC 챔스 조별 = 리그식
    return 1

def tie_rule(cid):
    """(원정 다득점, 연장) — 1990~2010년대 UEFA 대회·인터토토·코파 델 레이·수페르코파, 2013 AFC 챔스·중국 FA컵 준결승"""
    if cid in ("UEFA", "CL", "CLQ", "EL", "ELQ", "UI", "CDR", "SUC", "AFCL", "CHFA"): return (1, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]
    oid = m["other_leg_id"] or TIES_RAW[gid]["other_leg_id"]
    o = MI[oid]
    oh, oa = map(int, o["final"].split(":"))
    if o["home_id"] == G[gid]["club_id"]: return (oh, oa)
    if o["away_id"] == G[gid]["club_id"]: return (oa, oh)
    sys.exit("다른 차전 팀 불일치 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if not two_leg(g["competitionId"], g["round"]): return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"])
    leg = 1 if ("1st" in rnd or "first leg" in rnd) else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
# Transfermarkt에 없는 경기(경기 단위 출처 2곳으로 확인, judgments.md 2절): 2009.11.10 코파 델 레이 32강 2차전 세비야 5-1 아틀레티코 시우다드.
# Transfermarkt API는 'not in squad'. ESPN 경기 기록(gameId 284888: 카누테 59분 PK 골)과 영어 위키백과 2009–10 Sevilla FC season 경기 상자
# (RFEF 공식 경기 보고서 링크, 카누테 58분 골)가 득점 확인. 출전 분 기록 없음 → 90분 추정(est 1, 크레스포 선례).
ADDED_M = [["2009-11-10", "Atlético Ciudad (- 2010)", "dc", 90, 1]]
M += ADDED_M
M.sort(key=lambda m: m[0])

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
    if t.startswith("Deflected"): return "굴절"
    return None

# 리포트 골 순서 고침(같은 분 두 골의 순서가 거꾸로): 골 전 스코어는 리포트 순서대로 세되 아래 경기만 순서를 바꿈.
#  1036221 2010.12.11 세비야 1-3 알메리아: TM은 카누테·피아티 두 골 모두 82분. FotMob(피아티 81분 0-2, 카누테 83분 1-2)·ESPN·Sporting Life 경기 기록
#          (피아티 81분, 카누테 83분) → 피아티 골이 먼저, 카누테 골 = 0-2에서.
#  58475   2006.10.15 바르셀로나 3-1 세비야: TM은 호나우지뉴 프리킥·카누테 헤더 모두 38분. FC 바르셀로나 구단 경기 기록·soccer-spain.com 경기 기사
#          (호나우지뉴 PK 25~27분 → 카누테 헤더 동점 36~37분 → 호나우지뉴 프리킥 38~39분) → 카누테 골 = 1-0에서(동점골).
ORDER_FIX = {"1036221": ["Fabián Vargas", "Pablo Piatti", "Frédéric Kanouté", "Pablo Piatti"],
             "58475": ["Ronaldinho", "Frédéric Kanouté", "Ronaldinho", "Lionel Messi"]}

def ordered(gid):
    ev = list(EVS[gid])
    if gid not in ORDER_FIX: return ev
    want = ORDER_FIX[gid]; out = []; pool = ev[:]
    for nm in want:
        i = next(i for i, e in enumerate(pool) if e["scorer"] == nm); out.append(pool.pop(i))
    if pool: sys.exit("순서 고침 남은 골 " + gid)
    return out

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); run = [0, 0]
    if gid in ORDER_FIX: judg.append(("골 순서 고침(같은 분 두 골)", ldate(g), opp(g), ORDER_FIX[gid]))
    for e in ordered(gid):
        bh, ba = run
        run[0 if e["side"] == "home" else 1] += 1          # side = 골을 얻은 편(자책골도 얻은 편)
        h, a = map(int, e["score_home_away_after"].split("-"))
        if (h, a) != tuple(run) and e["kanoute_scorer"] == "1" or (h, a) != tuple(run) and e["kanoute_assist_other"] == "1":
            judg.append(("리포트 표기 스코어와 순서상 스코어 다름(순서 사용)", ldate(g), opp(g), e["minute"], f"{h}-{a}", f"{run[0]}-{run[1]}"))
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("자책골(상대 득점, 본인 골 아님)", ldate(g), opp(g), e["minute"])); continue
        is_g = e["kanoute_scorer"] == "1" and not is_og(e)
        is_a = e["kanoute_assist_other"] == "1"
        if e["kanoute_self_assist"] == "1":
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if is_a and e["assist_type"].startswith("Handball by"):
            judg.append(("도움 아님(상대 PK 골 — 카누테 핸드볼 반칙, 리포트 도움 칸 표기)", ldate(g), opp(g), e["minute"], e["scorer"])); continue
        if not (is_g or is_a): continue
        if (e["side"] == "home") != (side == "h"): sys.exit("득점 편 이상 " + gid + " " + e["minute"])
        gf, ga = (bh, ba) if side == "h" else (ba, bh)
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if not e["assist_type"]: judg.append(("유형 빈칸 도움 유지(2014 전 규칙)", ldate(g), opp(g), e["minute"], e["scorer"], e["goal_desc"]))
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + gid)
            if e["goal_desc"].startswith("Deflected"):
                judg.append(("굴절 슈팅 골 = 본인 골 유지", ldate(g), opp(g), e["minute"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

cnt = collections.Counter()
for r in raw_rows: cnt[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt[(gid, "g")] != int(g["goals"]): sys.exit("골 수 불일치 " + gid)
    if int(g["goals"]) and gid not in EVS: sys.exit("리포트 없음 " + gid)
api_a = sum(int(g["assists"]) for g in GAMES)

# FotMob 대조(2010-11부터): 골 수·시각
FM = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FM[r["tm_gameId"]].append(r)
FM_DIFF = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    if gid not in FM or typ != "g": continue
    hits = [r for r in FM[gid] if r["kanoute_scorer"] == "1"]
    if not hits: FM_DIFF.append(("FotMob 골 없음", gid, G[gid]["date_local_schedule"])); continue
    mm_ = [int(r["time"]) + int(r["overloadTime"] or 0) for r in hits]
    if min(abs(x - mi) for x in mm_) > 0: FM_DIFF.append(("골 시각", ldate(G[gid]), mi, mm_))

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
MANUAL_ALIAS = {"inter milan": "inter"}
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
    except Exception:
        sys.exit("git ls-files 실패(병렬 판정 파일을 읽지 않으려고 추적 파일만 씀)")
    return [os.path.join(ROOT, x) for x in out if x.endswith(".js")]

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in tracked_data():
    b = os.path.basename(fn)
    if b in ("hon.js", "knt.js", "clubcolors.js", "finals.js") or not os.path.exists(fn): continue
    OTHERS[b] = load_js(fn)
BYDATE = collections.defaultdict(list)
for b, (P, oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "atletico", "calcio",
        "sport", "cd", "ud", "rcd", "sv", "as", "ss", "milan", "inter", "madrid", "ca", "fk", "sk", "ssc", "us", "balompie", "deportivo",
        "bilbao", "rotterdam", "eindhoven", "amsterdam", "athletic", "racing", "bvo", "vigo", "wednesday", "sheffield", "olympique",
        "west", "wanderers", "rovers", "town", "albion", "hotspur", "county", "paris", "saint", "germain", "stade", "spor", "kulubu",
        "beijing", "shanghai", "guangzhou", "dalian", "bromwich", "crystal", "palace", "aston"}
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

RANKS = collections.defaultdict(dict)     # (리그 코드, 시즌) -> {팀 키: (순위, 팀 수, 이름)}
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

def label(lg, s, r, n):
    if lg == "FR1": return f"리그1 {s} {r}위" if n == 18 and s < "2002" else f"리그1 {s} {r}위/{n}팀" if n != 20 else f"리그1 {s} {r}위"
    if lg == "GB1": return f"프리미어리그 {s} {r}위"
    if lg == "ES1": return f"라리가 {s} {r}위"
    if lg == "IT1": return f"세리에A {s} {r}위"
    if lg == "L1": return f"분데스리가 {s} {r}위"
    if lg == "GB2": return f"챔피언십 {s} {r}위/{n}팀"
    if lg == "GB3": return f"잉글랜드 3부 {s} {r}위/{n}팀 (Football League One, 리그 수준 추정)"
    if lg == "FR2": return f"리그2 {s} {r}위/{n}팀"
    if lg == "CSL": return f"중국 슈퍼리그 {s} {r}위/{n}팀" if s == "2012" else f"중국 1부 {s} {r}위/{n}팀 (Chinese Super League)"
    if lg == "CLO": return f"중국 2부 {s} {r}위/{n}팀 (China League One, 리그 수준 추정)"
    if lg == "PL1": return f"폴란드 1부 {s} {r}위/{n}팀 (Ekstraklasa)"
    if lg == "A1": return f"오스트리아 1부 {s} {r}위/{n}팀"
    if lg == "TR1": return f"튀르키예 1부 {s} {r}위/{n}팀 (Süper Lig)"
    if lg == "DK1": return f"덴마크 1부 {s} {r}위/{n}팀"
    if lg == "SER1": return f"세르비아 1부 {s} {r}위/{n}팀 (First League of FR Yugoslavia)"
    if lg == "BE1": return f"벨기에 1부 {s} {r}위/{n}팀"
    if lg == "SL1": return f"슬로베니아 1부 {s} {r}위/{n}팀"
    if lg == "FI1": return f"핀란드 1부 {s} {r}위/{n}팀 (Veikkausliiga)"
    if lg == "RU1": return f"러시아 1부 {s} {r}위/{n}팀"
    if lg == "PO1": return f"포르투갈 1부 {s} {r}위" if n == 18 else f"포르투갈 1부 {s} {r}위/{n}팀"
    if lg == "GR1": return f"그리스 1부 {s} {r}위/{n}팀"
    if lg == "TS1": return f"체코 1부 {s} {r}위/{n}팀"
    if lg == "RO1": return f"루마니아 1부 {s} {r}위/{n}팀 (Liga I)"
    if lg == "UKR1": return f"우크라이나 1부 {s} {r}위/{n}팀"
    if lg == "SC1": return f"스코틀랜드 1부 {s} {r}위/{n}팀"
    if lg == "JAP1": return f"일본 1부 {s} {r}위/{n}팀 (J1리그)"
    if lg == "RSK1": return f"한국 1부 {s} {r}위/{n}팀 (K리그 클래식)"
    if lg == "UZ1": return f"우즈베키스탄 1부 {s} {r}위/{n}팀"
    if lg.startswith("ES3"): return f"스페인 3부 {s} {r}위/{n}팀 (Segunda División B Group {'ABCD'.index(lg[-1]) + 1}, 리그 수준 추정)"
    return None
RANK_LG = ["ES1", "GB1", "FR1", "CSL", "IT1", "L1", "GB2", "GB3", "FR2", "CLO", "PL1", "A1", "TR1", "DK1", "SER1", "BE1", "SL1", "FI1",
           "RU1", "PO1", "GR1", "TS1", "RO1", "UKR1", "SC1", "JAP1", "RSK1", "UZ1", "ES3A", "ES3B", "ES3C", "ES3D"]
CAL_LG = {"CSL", "CLO", "RU1", "FI1", "JAP1", "RSK1", "UZ1"}

def eu(d, july_prev=False):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

def ra_value(lv, d):
    p = RA["parse"](lv, d)
    if not p: sys.exit("순위 라벨 해석 실패 " + lv)
    v = RA["value"](*p)
    if v is None: sys.exit("기준 없음 " + lv)
    return v

# 순위표(raw/ranks.txt)에 없는 팀-시즌(직접 확인한 라벨: judgments.md 4절)
MANUAL_LV = {   # 잉글랜드 2부(Football League First Division) 2003-04 최종 순위: 영어 위키백과 2003–04 Football League First Division(raw/wiki/tbl_…, raw/ranks_wiki.txt)
    ("Coventry City", "2003-09-24"): "챔피언십 2003-04 12위/24팀 (Football League First Division)",
    ("Crystal Palace", "2004-01-03"): "챔피언십 2003-04 6위/24팀 (Football League First Division)",   # 6위로 플레이오프 승격
}
NORANK = {}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid, gid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1:
        print("  [같은 경기 값 여럿]", o, d, vals)
    if (o, d) in NORANK:
        e, lv = NORANK[(o, d)]; ELO_SRC["순위 없음(그 단계 기준점)"] += 1; ELO_LOG[(o, d)] = ("norank", e, lv); return e, lv
    if (o, d) in MANUAL_LV:
        lv = MANUAL_LV[(o, d)]; e = ra_value(lv, d)
        ELO_SRC["직접 확인 라벨(새 팀-시즌)"] += 1; ELO_LOG[(o, d)] = ("manual", e, lv); return e, lv
    k = key(o)
    euro = cid in ("CL", "CLQ", "UEFA", "UI", "EL", "ELQ", "USC", "AFCL")
    s0 = eu(d)
    if cid in ("CSL", "CHFA", "AFCL"): seasons = [d[:4]]
    else: seasons = [s0, d[:4]] if euro else [s0]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for lg in RANK_LG:
        ss = d[:4] if lg in CAL_LG else s0
        t = RANKS.get((lg, ss))
        if t and k in t:
            r, n, _ = t[k]
            lv = label(lg, ss, r, n)
            e = ra_value(lv, d)
            ELO_SRC["순위표+순위 규칙(새 팀-시즌)"] += 1; ELO_LOG[(o, d)] = ("model", e, lv, ss); return e, lv
    MISS.append((o, d, cid, tuple(seasons), gid)); return 0, "?"

# ---------------------------------------------------------------- 기록 행
E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, gid)
    et = 1 if (g["gameState"] != "regularly_terminated" and mi > 90 and dm == 0) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
# Transfermarkt에 없는 골(위 ADDED_M): 2009.11.10 아틀레티코 시우다드전 58분 PK(ESPN 59분 'Pen', 위키백과 경기 상자 58분 — 공식 보고서 링크가 있는 위키백과 시각),
# 골 전 1-1(46분 아틀레티코 시우다드 조시우 골, 51분 나바스 골 뒤), 2차전 홈, 1차전 4-2 승(Transfermarkt 리포트 976418 / 위키백과 2–4).
_e, _lv = opp_elo("Atlético Ciudad (- 2010)", "2009-11-10", "CDR", None)
E.append(["g", "Atlético Ciudad (- 2010)", _e, "dc", 58, 1, 1, 0, 1, "2009-11-10", 0, 0, _lv, 0, [2, 1, 4, 2, 1, 1]])
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분", "API 도움", api_a)
    print(ELO_SRC)
    for m in MISS: print("Elo 없음:", m)
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda x: x[0][1]):
        if v[0] != "table": print(d, o, v)
    print("FM_DIFF", FM_DIFF)
    for t in TOKS_LOG: print("TOKS", t)
    for j in judg: print("judg", j)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("lyokt", "2000-03-01", "올랭피크 리옹", "1997~2000", "Olympique Lyon", "1041"),
         ("whukt", "2003-08-05", "웨스트햄 유나이티드", "2000~2003", "West Ham United", "379"),
         ("totkt", "2005-08-17", "토트넘 홋스퍼", "2003~2005", "Tottenham Hotspur", "148"),
         ("sevkt", "2012-07-01", "세비야", "2005~2012", "Sevilla", "368"),
         ("bjgkt", None, "베이징 궈안", "2012~2013", "Beijing Guoan", "3176")]
def club_of(d):
    for c in CLUBS:
        if c[1] is None or d < c[1]: return c[0]
ST = collections.OrderedDict((c[0], [0, 0, 0, 0]) for c in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TM_CLUB = {"1041": ("lyokt",), "379": ("whukt",), "148": ("totkt",), "368": ("sevkt",), "3176": ("bjgkt",)}
for g in GAMES:
    if club_of(ldate(g)) not in TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
JULY = sorted({(club_of(m[0]), m[0]) for m in M if m[0][5:7] in ("06", "07")})
if "--debug" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print("6·7월 경기", JULY)

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
        if x[0] == "a" and "Kanout" in str(x[13]):
            hit = sorted([r for r in MYG if r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append(("동료 도움→카누테 골", b, x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
for r in E:
    if r[0] != "a": continue
    for b, x in BYDATE.get(r[9], []):
        if x[0] == "g" and abs(x[4] - r[4]) <= 3 and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])):
            CROSS.append(("카누테 도움→동료 골", b, r[9], r[4], r[13], cmp_rows(r, x) or "같음"))
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

exec(open(os.path.join(HERE, "note_kanoute.py"), encoding="utf-8").read())

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
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if MISS: problems.append(("Elo 없음", MISS))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and not ({"--debug", "--cross"} & set(sys.argv)):
    open(OUT_JS, "w", encoding="utf-8").write(f"const KNT_E={J(E)};\nconst KNT_M={J(M)};\nconst KNT_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "elo_sources": ELO_SRC, "elo_log": {f"{d} {o}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
