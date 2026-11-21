#!/usr/bin/env python3
"""Fernando Morientes: raw/ -> morientes.json + src/data/mor.js (판정 근거는 judgments.md)

  python3 players/morientes/build_morientes.py            # 파일 쓰기
  python3 players/morientes/build_morientes.py --debug    # Elo 출처 로그·판정 목록
  python3 players/morientes/build_morientes.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/morientes/build_morientes.py --out DIR  # DIR/src/data/mor.js 로 쓰기(검증용 복사본)

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골·도움), raw/morientes_goal_assist_events.csv(위키백과 골 4개),
      raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/ranks.txt(순위표), elo/opponent_elo_by_team_season.csv·aliases.csv,
      tools/league_rank_apply.py(순위 라벨 → Elo), src/data/*.js(git 추적 파일만: 같은 경기 다른 선수 자료).
오베르마르스 build_overmars.py(같은 Transfermarkt 원자료 형식)를 바탕으로 함.
"""
import csv, json, os, re, sys, io, unicodedata, collections, subprocess, contextlib, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_ROOT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else ROOT
OUT_JS = os.path.join(OUT_ROOT, "src", "data", "mor.js")
OUT_JSON = os.path.join(HERE, "morientes.json")
ME = "7531"
ME_KO = "페르난도 모리엔테스"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")          # 성인 클럽 경기만(유소년·2군 경기는 TM에 없음)
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# ---------------------------------------------------------------- 판정 표(judgments.md)
# 1) Transfermarkt에 골 목록이 없는 2경기: 영어 위키백과 경기 상자(1994-95·1995-96 코파 델 레이, 1995-96 사라고사 시즌 문서)의 골 순서
WIKI_GOALS = {   # gameId -> [(분, 골 뒤 스코어 홈-원정, 득점 편)]
    "2422295": [("60", "1-0", "home")],                                      # 알바세테 2-1 사라고사: 모리엔테스 60, 폰세카 79, 오스카르 81
    "2422321": [("8", "0-1", "away"), ("28", "0-2", "away"), ("52", "2-3", "away")],   # 아틀레틱 2-3 사라고사: 게레로 43, 에체베리아 51
}
# 2) Transfermarkt 'not in squad'이지만 경기 상자에 모리엔테스 골이 있는 경기(크레스포 RSSSF 선례: 경기 단위 출처가 있는 경기만, 출전 90분 추정)
INCLUDE_WIKI_CDR = True
ADD_GAMES = [   # gameId, 날짜, 상대, 분(추정), 골[(분, 골 뒤 스코어 홈-원정, 편)]
    ("2422300", "1995-02-15", "Real Zaragoza", 90, [("50", "0-1", "away")]),   # 사라고사 1-1 알바세테: 모리엔테스 50, 에스나이데르 86
]
GAP = "2014-08-01"   # 이 날 이후 경기 없음 → 모든 도움은 2014년 이전 TM 단일 출처 규칙

def ldate(g): return g["date_local"]
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES1", "FR1", "GB1", "ES1P"}         # ES1P 1995 승강 플레이오프 = 리그(카소를라 선례)
CUPS = {"CDR", "FRC", "FAC", "CGB"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or (cid == "FAC" and r.startswith("sixth")): return "dk"   # FA컵 6라운드 = 8강
        return "dc"                               # 쿠프 드 프랑스 Fifth/Sixth Round(64·32강)·Round of 16 포함
    if cid in ("SUC", "USC"): return "df"         # 수페르코파·UEFA 슈퍼컵 = 국내컵 결승 비중
    if cid in ("WEPO", "KLUB"): return "cwc"      # 인터콘티넨털컵·클럽 월드 챔피언십 2000·2005
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"    # 1999~2003 2차 조별 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                    # 3라운드(32강)~8강
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"                                    # 2009-10 32강('Second Round')
    if cid == "EPP":                                    # 컵위너스컵 1995-96: 1라운드~8강 유로파 토너먼트(오베르마르스·바티스투타 선례)
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return 0
    if "leg" in r: return 0
    if r.startswith("group"): return 0           # 챔스·UEFA컵 조별, 클럽 월드 챔피언십 2000 조별(리그식, 라울 선례)
    return 1

def tie_rule(cid):
    """(원정 다득점, 연장) — 1990~2000년대 UEFA 대회·코파 델 레이·수페르코파·UEFA 슈퍼컵·잉글랜드 리그컵 준결승 모두 원정 다득점·연장"""
    if cid in ("UEFA", "EL", "CL", "CLQ", "EPP", "CDR", "SUC", "USC", "CGB"): return (1, 1)
    if cid == "ES1P": return (0, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid, club_id=None):
    m = MI[gid]; cid = club_id or G[gid]["club_id"]
    if m["home_id"] == cid: return "h"
    if m["away_id"] == cid: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid, club_id):
    m = MI[gid]
    oid = m["other_leg_id"] or TIES_RAW[gid]["other_leg_id"]
    o = MI[oid]
    oh, oa = map(int, o["final"].split(":"))
    if o["home_id"] == club_id: return (oh, oa)
    if o["away_id"] == club_id: return (oa, oh)
    sys.exit("다른 차전 팀 불일치 " + gid)

def tie_of(gid, cid, rnd, club_id):
    rnd = rnd.lower()
    if "leg" not in rnd: return None
    s = side_of(gid, club_id)
    ag, et = tie_rule(cid)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid, club_id)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# 추가 경기(2422300)는 tm_games.csv에 없으므로 같은 모양의 가짜 행을 만든다(Transfermarkt 일정 정보: 코파 델 레이 16강 2차전)
if INCLUDE_WIKI_CDR:
    for gid, d, o, mn, gl in ADD_GAMES:
        G[gid] = {"gameId": gid, "date_local": d, "opponent": o, "competitionId": "CDR", "round": "Last 16 2nd Leg",
                  "club_id": "1532", "playedMinutes": str(mn), "goals": str(len(gl)), "gameState": "regularly_terminated", "est": "1"}

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(G.values(), key=lambda g: (ldate(g), g["gameId"])):
    row = [ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])]
    if g.get("est"): row.append(1)
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
    if t == "Deflected": return "굴절"
    return None

for gid, gl in WIKI_GOALS.items():
    if EVS.get(gid): sys.exit("위키 골 경기에 TM 골 목록이 있음 " + gid)
    for mn, sc, sd in gl:
        EVS[gid].append({"minute": mn, "score_home_away_after": sc, "side": sd, "scorer": "Fernando Morientes", "scorer_id": ME,
                         "goal_desc": "", "assist_player": "", "assist_id": "", "assist_type": "", "penalty": "0", "own_goal": "0",
                         "morientes_scorer": "1", "morientes_assist_other": "0", "morientes_self_assist": "0", "src": "wiki"})
if INCLUDE_WIKI_CDR:
    for gid, d, o, mn, gl in ADD_GAMES:
        for m_, sc, sd in gl:
            EVS[gid].append({"minute": m_, "score_home_away_after": sc, "side": sd, "scorer": "Fernando Morientes", "scorer_id": ME,
                             "goal_desc": "", "assist_player": "", "assist_id": "", "assist_type": "", "penalty": "0", "own_goal": "0",
                             "morientes_scorer": "1", "morientes_assist_other": "0", "morientes_self_assist": "0", "src": "wiki"})

INCOMPLETE = {"2422341", "2283306"}   # TM 골 목록에 상대 골이 빠진 경기(모리엔테스 골 없음 → 스코어 순서 점검 제외)
raw_rows, judg = [], []
SEQ_DIFF = []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0)
    evs = EVS[gid]
    if gid == "2422321": evs = sorted(evs, key=lambda e: int(e["minute"]))   # 위키 골 순서대로
    for e in evs:
        h, a = map(int, e["score_home_away_after"].split("-"))
        bh, ba = (h - 1, a) if e["side"] == "home" else (h, a - 1)
        if (bh, ba) != prev and gid not in INCOMPLETE and gid not in WIKI_GOALS: SEQ_DIFF.append((gid, ldate(g), e["minute"], (bh, ba), prev))
        prev = (h, a)
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("자책골(상대 득점, 본인 골 아님)", ldate(g), opp(g), e["minute"])); continue
        if e["assist_id"] == ME and e["morientes_assist_other"] != "1" and e["morientes_scorer"] != "1":
            judg.append(("상대 골 도움 칸 표기(도움 아님)", ldate(g), opp(g), e["minute"], e["assist_type"])); continue
        is_g = e["morientes_scorer"] == "1" and not is_og(e)
        is_a = e["morientes_assist_other"] == "1"
        if e["morientes_self_assist"] == "1":
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
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

cnt = collections.Counter()
for r in raw_rows: cnt[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt[(gid, "g")] != int(g["goals"]): sys.exit("골 수 불일치 " + gid + f" {cnt[(gid, 'g')]} vs {g['goals']}")
    if int(g["goals"]) and gid not in EVS: sys.exit("리포트 없음 " + gid)
    if "assists" in g and cnt[(gid, "a")] > int(g["assists"]): sys.exit("도움 수 초과 " + gid)

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
MANUAL_ALIAS = {"inter milan": "inter", "lokomotiv moskau": "lokomotiv moscow", "rcd espanol": "rcd espanyol barcelona",
                "fbk kaunas": "fbk kaunas", "ask inter slovnaft bratislava": "inter bratislava",
                "s sebast reyes ud san sebastian de los reyes": "ud san sebastian de los reyes"}
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
    if b in ("hon.js", "mor.js", "clubcolors.js", "finals.js"): continue
    OTHERS[b] = load_js(fn)
BYDATE = collections.defaultdict(list)
for b, (P, oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "atletico", "calcio",
        "sport", "cd", "ud", "rcd", "sv", "as", "ss", "milan", "inter", "madrid", "ca", "fk", "sk", "ssc", "us", "balompie", "deportivo",
        "bilbao", "rotterdam", "eindhoven", "amsterdam", "athletic", "racing", "afc", "bvo", "vigo", "wednesday", "sheffield", "olympique",
        "moscow", "moskau", "red", "bull", "star", "kv", "bk", "cp", "rc", "fbk", "if", "olympiacos", "piraeus"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = []
    for b, x in BYDATE.get(d, []):
        if key(x[1]) == key(o) or toks(x[1]) & toks(o): cand.append((b, x))
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 → 라벨 → Elo(tools/league_rank_apply.py와 같은 값)
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    RA = runpy.run_path(os.path.join(ROOT, "tools", "league_rank_apply.py"), run_name="ra")
sys.argv = _argv

RANKS = collections.defaultdict(dict)     # (리그 코드, 시즌 라벨) -> {팀 키: (순위, 팀 수, 이름)}
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[0].startswith("#"): continue
        RANKS[(p[0].split(" ")[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
def tmlab(s):   # '1995-96' -> '95/96'
    return s[2:4] + "/" + s[5:7]

# 새 팀-시즌 라벨(순위는 raw/ranks.txt의 Transfermarkt 순위표·위키백과 표, judgments.md 4절)
def label(lg, s, r, n, d):
    """lg: ranks.txt 리그 코드, s: 시즌 라벨(유럽식 YYYY-YY 또는 달력 연도 YYYY)"""
    if lg == "ES1": return f"라리가 {s} {r}위"   # 팀 수(1995-97 22팀)는 도구가 시즌으로 앎
    if lg == "ES2": return f"세군다 {s} {r}위/{n}팀"
    if lg == "ES3A" or lg == "ES3B" or lg == "ES3D" or lg == "ES3":
        grp = {"ES3A": "Grupo I", "ES3B": "Grupo II", "ES3D": "Grupo IV"}.get(lg, "Grupo III")
        return f"스페인 3부 {s} {r}위/{n}팀 (Segunda División B {grp}, 리그 수준 추정)"
    if lg == "ES4": return f"스페인 4부 {s} {r}위/{n}팀 (Tercera División Grupo VII, 리그 수준 추정)"
    if lg == "GB1": return f"프리미어리그 {s} {r}위"
    if lg == "GB2": return f"챔피언십 {s} {r}위/{n}팀"
    if lg == "IT1": return f"세리에A {s} {r}위" + (f"/{n}팀" if n != 20 else "")
    if lg == "L1": return f"분데스리가 {s} {r}위"
    if lg == "FR1": return f"리그1 {s} {r}위" + (f"/{n}팀" if n != 20 else "")
    if lg == "NL1": return f"에레디비시 {s} {r}위"
    if lg == "PO1": return f"포르투갈 1부 {s} {r}위" + (f"/{n}팀" if n != 18 else "")
    C = {"BE1": "벨기에", "GR1": "그리스", "RU1": "러시아", "UKR1": "우크라이나", "NO1": "노르웨이", "SE1": "스웨덴", "DK1": "덴마크",
         "TR1": "튀르키예", "A1": "오스트리아", "PL1": "폴란드", "BU1": "불가리아", "TS1": "체코", "LI1": "리투아니아", "WAL1": "웨일스",
         "SVK1": "슬로바키아", "BRA1": "브라질", "ARG1": "아르헨티나", "ARGC": "아르헨티나"}
    if lg in C: return f"{C[lg]} 1부 {s} {r}위/{n}팀"
    return None

def ra_value(lv, d):
    p = RA["parse"](lv, d)
    if not p: sys.exit("순위 라벨 해석 실패 " + lv)
    v = RA["value"](*p)
    if v is None: sys.exit("기준 없음 " + lv)
    return v

# 달력 연도 리그(러시아·노르웨이·스웨덴·리투아니아·브라질): 경기 날짜가 속한 해의 시즌(진행 중이거나 막 끝난 시즌)
CAL = {"RU1", "NO1", "SE1", "LI1", "BRA1"}
# 순위표가 여럿이거나 없는 상대(judgments.md 4절)
RANK_FIX = {
    # (상대 키, 날짜) -> (리그 코드, 시즌 라벨(ranks.txt), 표시 시즌)
}
LABEL_FIX = {   # Transfermarkt 순위표가 없는 상대: (상대 키, 시즌) -> 순위 라벨(값은 순위 규칙으로 계산)
    # 라자 1999-00: Transfermarkt 표 없음(MAR1 1999 페이지가 2026/27을 돌려줌) → RSSSF 'Morocco 1999/2000' 최종 표 1위/16팀(승점 59, 우승)
    (key("Raja Club Athletic"), "1999-00"): "모로코 1부 1999-00 1위/16팀 (Botola, 리그 수준 추정)",
}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1:
        print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    s0 = eu(d)
    seasons = [s0, d[:4]]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for s in seasons:
        if (k, s) in LABEL_FIX:
            lv = LABEL_FIX[(k, s)]; e = ra_value(lv, d)
            ELO_SRC["순위표+순위 규칙(새 팀-시즌)"] += 1; ELO_LOG[(o, d)] = ("model", e, lv, s); return e, lv
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
    if (k, d) in RANK_FIX:
        lg, sl, disp = RANK_FIX[(k, d)]
        cands = [(lg, sl, disp, RANKS[(lg, sl)][k])]
    if len(cands) > 1:
        # 리그 표가 컵 표보다 우선(ARGC 같은 반시즌 표는 RANK_FIX로 정함)
        print("  [순위표 여럿]", o, d, [(c[0], c[1], c[3][:2]) for c in cands])
    if cands:
        lg, sl, disp, (r, n, _) = cands[0]
        lv = label(lg, disp, r, n, d)
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
CLUBS = [("albmor", "1995-07-01", "알바세테", "1993~1995", "1532"),
         ("zarmor", "1997-07-01", "레알 사라고사", "1995~1997", "142"),
         ("rmmor", "2003-08-31", "레알 마드리드", "1997~2003", "418"),
         ("monmor", "2004-07-01", "AS 모나코(임대)", "2003~2004", "162"),
         ("rmmor2", "2005-01-13", "레알 마드리드", "2004~2005", "418"),
         ("livmor", "2006-07-01", "리버풀", "2005~2006", "31"),
         ("valmor", "2009-07-28", "발렌시아", "2006~2009", "1049"),
         ("ommor", None, "올랭피크 드 마르세유", "2009~2010", "244")]
def club_of(d):
    for c in CLUBS:
        if c[1] is None or d < c[1]: return c[0]
def club_key(c): return "rmmor" if c == "rmmor2" else c
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
        if x[0] == "a" and "Morientes" in str(x[13]):
            hit = sorted([r for r in MYG if r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append(("동료 도움→모리엔테스 골", b, x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
for r in E:
    if r[0] != "a": continue
    for b, x in BYDATE.get(r[9], []):
        if x[0] == "g" and abs(x[4] - r[4]) <= 3 and (x[5], x[6]) == (r[5], r[6]) and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])):
            CROSS.append(("모리엔테스 도움→동료 골", b, r[9], r[4], r[13], cmp_rows(r, x) or "같음"))
for b, (P, ent, om) in OTHERS.items():
    seen_d = set()
    for x in ent:
        if x[9] in seen_d: continue
        for r in E:
            if r[9] == x[9] and (key(r[1]) == key(x[1]) or toks(r[1]) & toks(x[1])):
                dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                CROSS.append(("같은 경기", b, r[9], r[1], dd or "같음")); seen_d.add(x[9]); break
    mm_ = {m[0]: m for m in M}
    for m in om:
        fm = mm_.get(m[0])
        if fm and (key(fm[1]) == key(m[1]) or toks(fm[1]) & toks(m[1])):
            CROSS.append(("출전 행", b, m[0], fm[1], "같음" if fm[2] == m[2] else f"대회 {fm[2]}/{m[2]}"))
# 동료 골 중 이 자료(TM)에 모리엔테스 도움으로 있었으나 뺀 것 / 동료 자료에 모리엔테스 골로 없는 것 확인용
if "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
    print(collections.Counter((c[0], c[1]) for c in CROSS if c[0] != "출전 행"))

exec(open(os.path.join(HERE, "note_morientes.py"), encoding="utf-8").read())

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
    sys.exit(1)

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and not ({"--debug", "--cross"} & set(sys.argv)):
    open(OUT_JS, "w", encoding="utf-8").write(f"const MOR_E={J(E)};\nconst MOR_M={J(M)};\nconst MOR_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "elo_sources": ELO_SRC, "elo_log": {f"{d} {o}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
