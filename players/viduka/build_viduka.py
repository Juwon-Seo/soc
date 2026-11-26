#!/usr/bin/env python3
"""Mark Viduka: raw/ -> viduka.json + vid.js (판정 근거는 judgments.md)

  python3 players/viduka/build_viduka.py            # 파일 쓰기 (players/viduka/vid.js)
  python3 players/viduka/build_viduka.py --debug    # Elo 출처 로그
  python3 players/viduka/build_viduka.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/viduka/build_viduka.py --out DIR  # DIR/src/data/vid.js 로 쓰기(검증용 복사본)

입력: raw/tm_games.csv(출전·분·TM 일정 날짜), raw/tm_events.csv(리포트/API 골·도움), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv,
      raw/ranks.txt(TM 순위표), elo/opponent_elo_by_team_season.csv·aliases.csv, tools/league_rank_apply.py(순위 라벨 → Elo),
      src/data/*.js(git 추적 파일만: 같은 경기 다른 선수 자료).
      Transfermarkt에 없는 경기(EXTRA_*)는 RSSSF(raw/rsssf)·영어 위키백과(raw/wiki) 경기 줄로 넣음(judgments.md 2절).
카누테 build_kanoute.py(같은 Transfermarkt 원자료 형식)를 바탕으로 함. FotMob에는 비두카 자료가 없음.
"""
import csv, json, os, re, sys, io, unicodedata, collections, subprocess, contextlib, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_ROOT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else ROOT
OUT_JS = os.path.join(OUT_ROOT, "src", "data", "vid.js") if "--out" in sys.argv else os.path.join(HERE, "vid.js")
OUT_JSON = os.path.join(HERE, "viduka.json")
ME = "3242"
ME_KO = "마크 비두카"

# Transfermarkt에 경기 기록이 없는 시기의 경기를 넣을지(오케스트레이터·사용자가 빼기로 하면 False)
INCLUDE_NSL = True        # 멜버른 나이츠(NSL, 호주 1부 — 세미프로 여부 경계, v1.163 규칙으로 포함) RSSSF 경기 4개
INCLUDE_CRO_EXTRA = True  # 크로아티아 자그레브 리그 2경기(위키 시즌 문서 + RSSSF)·컵 4경기(위키 컵/시즌 문서, 일부 RSSSF)

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
LEAGUE = {"GB1", "SC1"}
CUPS = {"FAC", "CGB", "SCP", "SFA", "KRC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth") or r.startswith("6th"): return "dk"   # FA컵 6라운드(재경기 포함)·8강
        return "dc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"          # 2000-01 2차 조별(Group 4) 포함
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEQ": return "elq"                        # UEFA컵 예선
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"           # 2004~2009 UEFA컵 조별
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 2·3라운드·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def two_leg(cid, rnd):
    if cid in ("FAC", "CGB", "SCP", "SFA"): return False
    return "leg" in rnd.lower()

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return 0
    if two_leg(cid, rnd): return 0
    if r.startswith("group"): return 0
    return 1

def tie_rule(cid):
    """(원정 다득점, 연장) — 1990~2000년대 UEFA 대회, 크로아티아컵 두 경기 결승(규정 출처 못 찾음: UEFA 방식으로 둠)"""
    if cid in ("UEFA", "CL", "CLQ", "UEQ", "KRC"): return (1, 1)
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
EXTRA_NSL = [
    # RSSSF aus94: NSL 1993-94 결선 메이저 준결승 2차전(4.17) 멜버른 나이츠 2-2 사우스 멜버른 [Viduka 4, De Amicis 86; Wade 41, Awaritefe 80].
    # 1차전(4.10) 사우스 멜버른 1-2 나이츠. 명단 없음 → 90분 추정. 결선 규정(원정 다득점) 출처 없음 → 원정 다득점 없음·연장 있음으로 둠.
    ["1994-04-17", "South Melbourne FC", "mlp", 90, 1, [(4, 0, 0, 0)], [2, 1, 2, 1, 0, 1], "RSSSF aus94"],
    # 영어 위키백과 '1994 NSL Cup final'(1994.10.16, 올림픽 파크) + RSSSF aus95 NSL컵 결승 나이츠 6-0 하이델베르크 [Spiteri 30, 70, Horvat 51, Biskic 80, Viduka 86, 87].
    # 명단 없음 → 90분 추정. 골 전 스코어 4-0, 5-0.
    ["1994-10-16", "Heidelberg United", "df", 90, 1, [(86, 4, 0, 0), (87, 5, 0, 0)], None, "RSSSF aus95 + 위키백과 1994 NSL Cup final"],
    # RSSSF aus95: 1994-95 결선 예선 결승(4.30, 올림픽 파크) 나이츠 3-2 사우스 멜버른 [Viduka 27, 37, 53; Boutsianis 44, 72],
    # 선발 명단에 Viduka(교체 없음) → 90분.
    ["1995-04-30", "South Melbourne FC", "mlpsf", 90, 0, [(27, 0, 0, 0), (37, 1, 0, 0), (53, 2, 1, 0)], None, "RSSSF aus95"],
    # RSSSF aus95: 그랜드 파이널(5.7, 애들레이드 힌드마시) 애들레이드 시티 0-2 나이츠, 선발 명단에 Viduka(교체 없음) → 90분, 골 없음.
    ["1995-05-07", "Adelaide City", "mlpf", 90, 0, [], None, "RSSSF aus95"],
]
EXTRA_CRO = [
    # 영어 위키백과 1995–96 Croatian Football Cup 준결승 1차전(Slobodna Dalmacija 기사 인용): 1996.4.3 자다르 1-3 크로아티아 자그레브
    # [Viduka 31', Slišković 62', Marić 77'; Bogdan 66']. RSSSF kroa96은 스코어만. 2차전 크로아티아 2-1 자다르(4.17).
    ["1996-04-03", "NK Zadar", "dsf", 90, 1, [(31, 0, 0, 0)], [1, 0, 0, 0, 1, 1], "위키백과 1995–96 Croatian Football Cup"],
    # 위키백과 1996–97 Croatian Football Cup(Viduka 20', 55' PK) + RSSSF kroa97(Viduka 20 PK, 55): 1997.4.9 크로아티아 2-1 오시예크.
    # PK가 어느 골인지 엇갈림 → 신문 기사(Slobodna Dalmacija)를 인용한 위키 기준 55분 PK. 2차전 4.16 오시예크 0-0.
    ["1997-04-09", "NK Osijek", "dsf", 90, 1, [(20, 0, 0, 0), (55, 1, 0, 1)], [1, 1, 0, 0, 1, 1], "위키백과 1996–97 Croatian Football Cup + RSSSF kroa97"],
    # 위키백과 1997–98 Croatian Football Cup 준결승 1차전: 1998.4.1 크로아티아 4-0 NK 자그레브 [Marić 14', Viduka 45' PK, 53' PK, Muñoz 65'].
    # RSSSF kroa98은 스코어만(4:0). 2차전 4.15 NK 자그레브 0-3 크로아티아.
    ["1998-04-01", "NK Zagreb", "dsf", 90, 1, [(45, 1, 0, 1), (53, 2, 0, 1)], [1, 1, 0, 0, 1, 1], "위키백과 1997–98 Croatian Football Cup"],
    # 위키백과 1998–99 NK Croatia Zagreb season: 컵 32강 1998.9.8 두고 셀로(4부) 3-2 크로아티아 [Viduka 17', Šokota 45'; Benkoci 48', 자책골 75', Car 88'].
    # RSSSF kroa99는 스코어만(3-2). 단판.
    ["1998-09-08", "NK Dugo Selo", "dc", 90, 1, [(17, 0, 0, 0)], None, "위키백과 1998–99 NK Croatia Zagreb season"],
    # 1. HNL 1998-99 5라운드 1998.9.11 믈라도스트 127 0-4 크로아티아 [Mujčin 15', 18', Viduka 60', Mikić 85'] — 위키 시즌 문서·RSSSF kroa99 같음.
    ["1998-09-11", "NK Mladost 127", "lg", 90, 1, [(60, 2, 0, 0)], None, "위키백과 1998–99 NK Croatia Zagreb season + RSSSF kroa99"],
    # 11라운드 1998.11.1 하이두크 1-1 크로아티아 [Viduka 9'; Leko 49'] — 위키 시즌 문서·RSSSF kroa99 같음.
    ["1998-11-01", "HNK Hajduk Split", "lg", 90, 1, [(9, 0, 0, 0)], None, "위키백과 1998–99 NK Croatia Zagreb season + RSSSF kroa99"],
    # 넣지 않음: 12라운드 1998.11.7 시베니크 1-2 크로아티아 — 위키 시즌 문서는 Viduka 65', 75', RSSSF kroa99는 Mikić 65, 75.
    # 위키·NFT 1998-99 리그 7경기 2골(= 위 두 경기 2골)과 맞는 RSSSF를 따름 → 비두카 골 아님, 출전 근거 없음.
]
EXTRA = (EXTRA_NSL if INCLUDE_NSL else []) + (EXTRA_CRO if INCLUDE_CRO_EXTRA else [])

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

# 골 시각 고침: 4092644 1999.3.14 애버딘 1-5 셀틱 — TM 리포트는 비두카 47·59분이지만 같은 리포트의 전반 스코어가 0:1(전반에 셀틱 1골).
# 영어 위키백과 1998–99 Celtic F.C. season 경기 상자: Viduka 26', 47' → 전반 0:1과 맞음. 골 순서·골 전 스코어(0-0, 0-1)는 같음.
MIN_FIX = {("4092644", "47"): "26", ("4092644", "59"): "47"}
raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); run = [0, 0]
    for e in EVS[gid]:
        bh, ba = run
        run[0 if e["side"] == "home" else 1] += 1
        h, a = map(int, e["score_home_away_after"].split("-"))
        if (h, a) != tuple(run) and (e["vid_scorer"] == "1" or e["vid_assist_other"] == "1"):
            judg.append(("표기 스코어와 순서상 스코어 다름(순서 사용)", ldate(g), opp(g), e["minute"], f"{h}-{a}", f"{run[0]}-{run[1]}"))
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("자책골(상대 득점, 본인 골 아님)", ldate(g), opp(g), e["minute"])); continue
        is_g = e["vid_scorer"] == "1" and not is_og(e)
        is_a = e["vid_assist_other"] == "1"
        if e["vid_self_assist"] == "1":
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
    if b in ("hon.js", "vid.js", "clubcolors.js", "finals.js") or not os.path.exists(fn): continue
    OTHERS[b] = load_js(fn)
BYDATE = collections.defaultdict(list)
for b, (P, oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "atletico", "calcio",
        "sport", "cd", "ud", "rcd", "sv", "as", "ss", "milan", "inter", "madrid", "ca", "fk", "sk", "ssc", "us", "balompie", "deportivo",
        "bilbao", "rotterdam", "eindhoven", "amsterdam", "athletic", "racing", "bvo", "vigo", "wednesday", "sheffield", "olympique",
        "west", "wanderers", "rovers", "town", "albion", "hotspur", "county", "paris", "saint", "germain", "stade", "spor", "kulubu",
        "bromwich", "crystal", "palace", "aston", "hnk", "gnk", "nk", "manchester", "newcastle", "leeds", "zagreb"}
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
    return None
RANK_LG = ["GB1", "GB2", "GB3", "SC1", "C1", "ISR1", "NL1", "PO1", "RO1", "RU1", "SER1", "UKR1"]
CAL_LG = {"RU1"}

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
CLUBS = [("melvd", "1995-07-01", "멜버른 나이츠", "1992~1995", "Melbourne Knights", "651"),
         ("dinvd", "1998-11-20", "크로아티아 자그레브", "1995~1998", "Croatia Zagreb", "419"),
         ("celvd", "2000-07-21", "셀틱", "1998~2000", "Celtic", "371"),
         ("leevd", "2004-07-08", "리즈 유나이티드", "2000~2004", "Leeds United", "399"),
         ("mbovd", "2007-06-07", "미들즈브러", "2004~2007", "Middlesbrough", "641"),
         ("newvd", None, "뉴캐슬 유나이티드", "2007~2009", "Newcastle United", "762")]
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
        if x[0] == "a" and "Viduka" in str(x[13]):
            hit = sorted([r for r in MYG if r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append(("동료 도움→비두카 골", b, x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
for r in E:
    if r[0] != "a": continue
    for b, x in BYDATE.get(r[9], []):
        if x[0] == "g" and abs(x[4] - r[4]) <= 3 and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])):
            CROSS.append(("비두카 도움→동료 골", b, r[9], r[4], r[13], cmp_rows(r, x) or "같음"))
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
exec(open(os.path.join(HERE, "note_viduka.py"), encoding="utf-8").read())

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
    open(OUT_JS, "w", encoding="utf-8").write(f"const VID_E={J(E)};\nconst VID_M={J(M)};\nconst VID_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "elo_sources": ELO_SRC, "elo_log": {f"{d} {o}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
