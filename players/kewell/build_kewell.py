#!/usr/bin/env python3
"""Harry Kewell: raw/ -> kewell.json + kew.js (판정 근거는 judgments.md)

  python3 players/kewell/build_kewell.py            # 파일 쓰기 (players/kewell/kew.js)
  python3 players/kewell/build_kewell.py --debug    # Elo 출처 로그
  python3 players/kewell/build_kewell.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/kewell/build_kewell.py --out DIR  # DIR/src/data/kew.js 로 쓰기(검증용 복사본)

입력: raw/tm_games.csv(출전·분·TM 일정 날짜), raw/tm_events.csv(리포트/API 골·도움), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv,
      raw/ranks.txt(TM 순위표), elo/opponent_elo_by_team_season.csv·aliases.csv, tools/league_rank_apply.py(순위 라벨 → Elo),
      src/data/*.js(git 추적 파일만: 같은 경기 다른 선수 자료).
비두카 build_viduka.py(같은 수집기 원자료 형식)를 바탕으로 함. Transfermarkt에 없는 출전 2경기(EXTRA)는 판정 2절.
"""
import csv, json, os, re, sys, io, unicodedata, collections, subprocess, contextlib, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_ROOT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else ROOT
OUT_JS = os.path.join(OUT_ROOT, "src", "data", "kew.js") if "--out" in sys.argv else os.path.join(HERE, "kew.js")
OUT_JSON = os.path.join(HERE, "kewell.json")
ME = "3241"
ME_KO = "해리 큐얼"


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
    """TM 일정 날짜(현지). API UTC 23:00/22:00(킥오프 시각 없음) 11경기는 UTC 날짜가 하루 앞서므로 일정 날짜를 씀.
    영어 위키백과와 날짜가 다른 3경기(2002.10.26 미들즈브러전, 2006.3.11 찰턴전, 2007.1.6 헐전)는 TM 일정·API·ESPN이 같아 TM 날짜."""
    return g["date_local_schedule"]
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "TR1", "AUS1", "QSL"}
CUPS = {"FAC", "CGB", "TRP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth") or r.startswith("6th"): return "dk"   # FA컵 6라운드·8강, 튀르키예컵 8강
        return "dc"     # FA컵 3~5라운드(재경기 포함)·리그컵 2~4라운드·튀르키예컵 예선·조별
    if cid == "TRS": return "df"                         # 튀르키예 슈퍼컵 = 국내컵 결승
    if cid == "KLUB": return "cwc"                       # 2005 FIFA 클럽 월드 챔피언십 결승
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"          # 2000-01 2차 조별(Group 4) 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"                        # 유로파 예선·플레이오프
    if cid in ("UEFA", "EL"):
        if cid == "UEFA" and r.startswith("first round"): return "elq"     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"           # 2008-09 UEFA컵 조별, 2009-10 유로파 조별
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 2·3라운드·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def two_leg(cid, rnd):
    if cid == "FAC": return False
    return "leg" in rnd.lower()                          # 리그컵 1997-98 2라운드·튀르키예컵 2010-11 8강 포함

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return 0
    if two_leg(cid, rnd): return 0
    if r.startswith("group"): return 0                   # 챔스·UEFA컵·유로파 조별, 튀르키예컵 조별(리그식)
    return 1

def tie_rule(cid):
    """(원정 다득점, 연장) — UEFA 대회 2020-21까지, 잉글랜드 리그컵 두 경기 라운드(1990년대), 튀르키예컵 2020-21까지"""
    if cid in ("UEFA", "EL", "CL", "CLQ", "ELQ", "CGB", "TRP"): return (1, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

ALLG = rd("tm_games_all.csv")
def other_leg(gid):
    m = MI[gid]
    oid = m["other_leg_id"] or (TIES_RAW[gid]["other_leg_id"] if gid in TIES_RAW else "")
    if not oid:   # 짝 정보가 없는 경기: performance-game 목록의 같은 대회·같은 상대 다른 차전(출전 여부와 무관하게 스코어 있음)
        g = G[gid]
        o = [a for a in ALLG if a["opponentId"] == g["opponent_id"] and a["competitionId"] == g["competitionId"] and a["gameId"] != gid
             and abs(int(a["date"][:4]) - int(ldate(g)[:4])) <= 1]
        if len(o) != 1: sys.exit("다른 차전 못 찾음 " + gid)
        judg.append(("다른 차전 스코어(performance-game 목록)", ldate(g), opp(g), o[0]["gameId"], o[0]["score_club"] + "-" + o[0]["score_opp"]))
        return int(o[0]["score_club"]), int(o[0]["score_opp"])
    if oid not in MI:   # 다른 차전 경기 자료가 없을 때: performance-game 목록(우리-상대 스코어)
        a = [x for x in ALLG if x["gameId"] == oid]
        if len(a) != 1: sys.exit("다른 차전 못 찾음 " + gid)
        judg.append(("다른 차전 스코어(performance-game 목록)", ldate(G[gid]), opp(G[gid]), oid, a[0]["score_club"] + "-" + a[0]["score_opp"]))
        return int(a[0]["score_club"]), int(a[0]["score_opp"])
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

# ---------------------------------------------------------------- Transfermarkt에 없는 경기(judgments.md 2절)
# [날짜, 상대, 대회, 출전 분, 추정?, 골 목록[(분, 골 전 우리, 골 전 상대, PK)], 합산, 출처]
# 1998-99 FA컵 3라운드·재경기: Transfermarkt 선수 경기 성적은 '명단 제외'지만 영어 위키백과 선수 표(1998-99 FA컵 5경기 1골, TM 3경기)와
# 리즈 팬 기록 보관소(ozwhitelufc.net.au, 요크셔 이브닝 포스트 경기 기사 바탕) 경기별 명단: 두 경기 모두 큐얼 선발·교체 없음 → 90분.
EXTRA = [
    ["1999-01-02", "Rushden & Diamonds", "dc", 90, 0, [], None, "ozwhitelufc 1999.1.2 경기 기록(0-0, 선발 명단)"],
    ["1999-01-13", "Rushden & Diamonds", "dc", 90, 0, [], None, "ozwhitelufc 1999.1.13 경기 기록(3-1, 선발 명단, 득점 스미스 2·하셀바잉크)"],
]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
for x in EXTRA:
    M.append([x[0], x[1], x[2], x[3], 1] if x[4] else [x[0], x[1], x[2], x[3]])
M.sort(key=lambda m: m[0])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"
def is_pk(e): return e["penalty"] == "1" or e["goal_desc"] == "Penalty"

def assist_reason(e):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty") or is_pk(e): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t.startswith("Deflected"): return "굴절"
    return None

# 963458(2009.8.31 앙카라스포르–갈라타사라이, 뒤에 0-3 몰수 기록): 경기장 기록대로 74분 골 유지(골 전 0-0) — 아르다 투란 자료(이 골 도움)와 같음.
MIN_FIX = {}
raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); run = [0, 0]
    for e in EVS[gid]:
        bh, ba = run
        run[0 if e["side"] == "home" else 1] += 1
        h, a = map(int, e["score_home_away_after"].split("-"))
        if (h, a) != tuple(run) and (e["kew_scorer"] == "1" or e["kew_assist_other"] == "1"):
            judg.append(("표기 스코어와 순서상 스코어 다름(순서 사용)", ldate(g), opp(g), e["minute"], f"{h}-{a}", f"{run[0]}-{run[1]}"))
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("자책골(상대 득점, 본인 골 아님)", ldate(g), opp(g), e["minute"])); continue
        is_g = e["kew_scorer"] == "1" and not is_og(e)
        is_a = e["kew_assist_other"] == "1"
        if e["kew_self_assist"] == "1":
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if not (is_g or is_a): continue
        if (e["side"] == "home") != (side == "h"): sys.exit("득점 편 이상 " + gid + " " + e["minute"])
        gf, ga = (bh, ba) if side == "h" else (ba, bh)
        mi, dm = mins(MIN_FIX.get((gid, e["minute"]), e["minute"]) if is_g else e["minute"])
        if (gid, e["minute"]) in MIN_FIX and is_g: judg.append(("골 시각 고침", ldate(g), opp(g), e["minute"], MIN_FIX[(gid, e["minute"])]))
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if not e["assist_type"]: judg.append(("유형 빈칸 도움 유지(2014 전 규칙)", ldate(g), opp(g), e["minute"], e["scorer"], e["goal_desc"]))
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            raw_rows.append(("g", gid, mi, dm, gf, ga, 1 if is_pk(e) else 0, 0, e["goal_desc"]))

cnt = collections.Counter()
for r in raw_rows: cnt[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if cnt[(gid, "a")] != int(g["assists"] or 0): judg.append(("도움 수 API와 다름", gid, cnt[(gid, "a")], g["assists"]))
api_a = sum(int(g["assists"] or 0) for g in GAMES)

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
    if b in ("hon.js", "kew.js", "clubcolors.js", "finals.js") or not os.path.exists(fn): continue
    OTHERS[b] = load_js(fn)
BYDATE = collections.defaultdict(list)
for b, (P, oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "atletico", "calcio",
        "sport", "cd", "ud", "rcd", "sv", "as", "ss", "milan", "inter", "madrid", "ca", "fk", "sk", "ssc", "us", "balompie", "deportivo",
        "bilbao", "rotterdam", "eindhoven", "amsterdam", "athletic", "racing", "bvo", "vigo", "wednesday", "sheffield", "olympique",
        "west", "wanderers", "rovers", "town", "albion", "hotspur", "county", "paris", "saint", "germain", "stade", "spor", "kulubu",
        "bromwich", "crystal", "palace", "aston", "hnk", "gnk", "nk", "manchester", "newcastle", "leeds", "zagreb", "dinamo", "1948"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
TOKS_LOG = []
def same_match(o, d):
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

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

def label(lg, s, r, n):
    if lg == "GB1": return f"프리미어리그 {s} {r}위"
    if lg == "GB2": return f"챔피언십 {s} {r}위/{n}팀"
    if lg == "GB3": return f"잉글랜드 3부 {s} {r}위/{n}팀 (Football League One, 리그 수준 추정)"
    if lg == "SC1": return f"스코틀랜드 1부 {s} {r}위/{n}팀 (Scottish Premier League)"
    if lg == "C1": return f"스위스 1부 {s} {r}위/{n}팀"
    if lg == "ISR1": return f"이스라엘 1부 {s} {r}위/{n}팀"
    if lg == "NL1": return f"에레디비시 {s} {r}위"
    if lg == "PO1": return f"포르투갈 1부 {s} {r}위" if n == 18 else f"포르투갈 1부 {s} {r}위/{n}팀"
    if lg == "RO1": return f"루마니아 1부 {s} {r}위/{n}팀 (Liga I)"
    if lg == "RU1": return f"러시아 1부 {s} {r}위/{n}팀"
    if lg == "SER1": return f"세르비아 1부 {s} {r}위/{n}팀 (First League of FR Yugoslavia)"
    if lg == "UKR1": return f"우크라이나 1부 {s} {r}위/{n}팀"
    if lg == "TR1": return f"쉬페르리그 {s} {r}위/{n}팀"                 # 기존 자료(투란) 라벨 형식
    if lg == "TS1": return f"체코 1부 {s} {r}위/{n}팀 (1. liga)"
    if lg == "EST1": return f"에스토니아 1부 {s} {r}위/{n}팀 (Meistriliiga)"
    if lg == "AUS1": return f"호주 1부 {s} {r}위/{n}팀 (A-League, 정규 리그 최종 순위)"
    if lg == "QSL": return f"카타르 1부 {s} {r}위/{n}팀 (Qatar Stars League)"
    if lg == "A1": return f"오스트리아 1부 {s} {r}위/{n}팀"
    return None
RANK_LG = ["GB1", "TR1", "AUS1", "QSL", "TS1", "EST1", "A1", "C1", "ISR1", "NL1", "PO1", "RO1", "RU1", "SER1", "UKR1"]
CAL_LG = {"RU1", "EST1"}

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

def ra_value(lv, d):
    p = RA["parse"](lv, d)
    if not p: sys.exit("순위 라벨 해석 실패 " + lv)
    v = RA["value"](*p)
    if v is None: sys.exit("기준 없음 " + lv)
    return v

# 순위표(raw/ranks.txt)·통합표에 없는 팀-시즌(직접 확인한 라벨: judgments.md 4절)
MANUAL_LV = {}
NORANK = {}
exec(open(os.path.join(HERE, "manual_lv.py"), encoding="utf-8").read())

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1:
        print("  [같은 경기 값 여럿]", o, d, vals)
    if (o, d) in NORANK:
        lv = NORANK[(o, d)]; e = NORANK_VAL[lv]
        ELO_SRC["순위 없음(그 단계 기준점)"] += 1; ELO_LOG[(o, d)] = ("norank", e, lv); return e, lv
    if (o, d) in MANUAL_LV:
        lv = MANUAL_LV[(o, d)]; e = ra_value(lv, d)
        ELO_SRC["직접 확인 라벨(새 팀-시즌)"] += 1; ELO_LOG[(o, d)] = ("manual", e, lv); return e, lv
    k = key(o)
    s0 = eu(d)
    euro = cid in ("CL", "CLQ", "UEFA", "UEQ")
    seasons = [s0, d[:4]] if euro else [s0]
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
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

# ---------------------------------------------------------------- 기록 행
E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (g["gameState"] != "regularly_terminated" and mi > 90 and dm == 0) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
for d, o, comp, mn, est, goals, tie, src in EXTRA:
    if not goals: continue
    elo, lv = opp_elo(o, d, "X")
    for mi, gf, ga, pk in goals:
        row = ["g", o, elo, comp, mi, gf, ga, 0 if tie or comp == "lg" else 1, pk, d, 0, 0, lv, 0]
        if tie: row.append(tie)
        E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분", "API 도움", api_a)
    print(ELO_SRC)
    for m in MISS: print("Elo 없음:", m)
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda x: x[0][1]):
        if v[0] != "table": print(d, o, v)
    for t in TOKS_LOG: print("TOKS", t)
    for j in judg: print("judg", j)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("leekw", "2003-07-01", "리즈 유나이티드", "1996~2003", "Leeds United", "399"),
         ("livkw", "2008-07-29", "리버풀", "2003~2008", "Liverpool", "31"),
         ("galkw", "2011-09-29", "갈라타사라이", "2008~2011", "Galatasaray", "141"),
         ("mvkw", "2013-04-06", "멜버른 빅토리", "2011~2012", "Melbourne Victory", "7006"),
         ("garkw", "2013-07-01", "알가라파", "2013", "Al-Gharafa", "6297"),
         ("mhkw", None, "멜버른 하트", "2013~2014", "Melbourne Heart", "25580")]
def club_of(d):
    for c in CLUBS:
        if c[1] is None or d < c[1]: return c[0]
ST = collections.OrderedDict((c[0], [0, 0, 0, 0]) for c in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TM_CLUB = {c[5]: c[0] for c in CLUBS}
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
if "--debug" in sys.argv:
    for k, v in ST.items(): print(k, v)

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
        if x[0] == "a" and "Kewell" in str(x[13]):
            hit = sorted([r for r in MYG if r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append(("동료 도움→큐얼 골", b, x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
for r in E:
    if r[0] != "a": continue
    for b, x in BYDATE.get(r[9], []):
        if x[0] == "g" and abs(x[4] - r[4]) <= 3 and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])):
            CROSS.append(("큐얼 도움→동료 골", b, r[9], r[4], r[13], cmp_rows(r, x) or "같음"))
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

NG, NGo, NA, NPK = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E), sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14)
exec(open(os.path.join(HERE, "note_kewell.py"), encoding="utf-8").read())

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
    if r[4] > mm[r[9]][3] + 2 and r[4] <= 90: pass
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if MISS: problems.append(("Elo 없음", MISS))
if problems:
    for p in problems: print("점검:", p)
    if "--debug" not in sys.argv: sys.exit(1)

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and not ({"--debug", "--cross"} & set(sys.argv)):
    open(OUT_JS, "w", encoding="utf-8").write(f"const KEW_E={J(E)};\nconst KEW_M={J(M)};\nconst KEW_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "elo_sources": ELO_SRC, "elo_log": {f"{d} {o}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
