#!/usr/bin/env python3
"""후안 세바스티안 베론 (Juan Sebastián Verón, Transfermarkt 3143): raw/ -> veron.json + jsv.js (판정 근거는 judgments.md)

  python3 players/veron/build_veron.py            # 파일 쓰기(players/veron/jsv.js; JSV_OUT=<경로>로 바꿀 수 있음)
  python3 players/veron/build_veron.py --debug    # Elo 출처 로그
  python3 players/veron/build_veron.py --stat     # 요약·판정·동료 대조

비에이라 build(players/vieira)를 바탕으로 하고 날짜·남미 대회 코드·합산 규칙은 리켈메 build(players/riquelme)와 같게.
상대 Elo는 v1.226 규칙: 같은 경기 다른 선수 자료 → Elo 통합표(같은 팀·시즌, 아르헨티나는 같은 반시즌 라벨) → 출처로 확인한 순위로
라벨을 만들고 tools/league_rank_apply.py 의 value()로 값을 정함(직접 숫자를 넣지 않음). 스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib, datetime, functools

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.environ.get("JSV_OUT") or os.path.join(HERE, "jsv.js")
OUT_JSON = os.path.join(HERE, "veron.json")
ME = "3143"
ME_KO = "후안 세바스티안 베론"
PFX = "JSV"
GAP = "2014-08-01"   # 이 날짜 전 도움은 Transfermarkt 단일 출처 허용
SA_CLUBS = {"288", "189"}   # 에스투디안테스·보카

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# ---------------------------------------------------------------- 날짜(리켈메 규칙)
# 유럽 클럽: Transfermarkt 리포트 날짜(현지). 에스투디안테스·보카: TM 일정 날짜는 중부 유럽 날짜라 남미 저녁 경기가 하루 밀림 →
# API UTC 시각을 UTC−3(부에노스아이레스)으로 바꾼 날짜. 시각이 중부 유럽 자정(UTC 22:00/23:00 정각, 일정 날짜 전날)이나
# 12:00·13:00 정각이면 시각 미상 자리값 → 일정 날짜 그대로(2011년 4경기는 FotMob 킥오프 시각으로도 확인).
def _lastsun(y, m):
    x = datetime.date(y, m, 31)
    while x.weekday() != 6: x -= datetime.timedelta(1)
    return x
def _cet_mid_utc_hour(d):
    return 22 if _lastsun(d.year, 3) <= d < _lastsun(d.year, 10) else 23
DATE_LOG = []
DATE_FIX = {"2815694": "2003-03-02"}   # 2003 리그컵 결승 리버풀전(카디프 3.2): TM 날짜 2003-02-03(일·월 바뀜), 베컴·긱스·스콜스·판니스텔로이 자료 3.2
def _ldate(g):
    gid = g["gameId"]
    if gid in DATE_FIX: DATE_LOG.append((gid, g["date_local_schedule"], DATE_FIX[gid], "fix", g["opponent"])); return DATE_FIX[gid]
    if g["club_id"] not in SA_CLUBS: return g["date_local_tm_report"] or g["date_local_schedule"]
    sched = g["date_local_schedule"]
    u = datetime.datetime.fromisoformat(g["date_utc"])
    if (u.hour, u.minute) in ((12, 0), (13, 0)): return sched
    sd_ = datetime.date.fromisoformat(sched)
    if u.minute == 0 and u.hour == _cet_mid_utc_hour(sd_) and u.date() == sd_ - datetime.timedelta(1): return sched
    loc = (u - datetime.timedelta(hours=3)).date().isoformat()
    if loc != sched: DATE_LOG.append((gid, sched, loc, g["date_utc"][:16], g["opponent"]))
    return loc
LD = {gid: _ldate(g) for gid, g in G.items()}
def ldate(g): return LD[g["gameId"]]
TMD = {gid: g["date_local_schedule"] for gid, g in G.items()}

def opp(g):
    return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "IT1", "ARG1", "ARGC", "MARG"}   # MARG = 아페르투라 2006 우승 결정전(보카전 단판, 리그 비중)
CUPS = {"FAC", "CGB", "CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("SCI", "USC", "RECO"): return "df"                        # 수페르코파 이탈리아나·UEFA 슈퍼컵·레코파 = 국내컵 결승 비중
    if cid == "KLUB": return "cwc"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"                                                     # 예선(2009 스포르팅 크리스탈)·조별·16강
    if cid in ("CS", "SCSA"):
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g):
    return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")

def is_leg(cid, rnd): return "leg" in rnd.lower()

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE and cid != "MARG": return 0
    if is_leg(cid, rnd): return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    r = rnd.lower()
    if cid in ("UEFA", "CL", "CLQ", "CGB", "CIT"): return (1, 1)
    if cid == "CLI":
        if r.startswith("final") and d >= "2008-01-01": return (0, 1)   # 2008년부터 결승은 원정 다득점 없이 연장
        return (1, 0)                                                     # 2005~: 원정 다득점, 연장 없이 승부차기
    if cid == "CS":
        if r.startswith("final"): return (0, 1)                           # 2008 결승: 원정 다득점 없이 연장(2차전 연장, 리베르타도레스 결승 규정과 같음)
        return (1, 0)
    if cid == "RECO": return (0, 1)
    if cid == "SCSA": return (0, 0)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

OTHER_LEG_LOG = []
def other_leg(gid):
    m = MI[gid]; oid = m["other_leg_id"]; club = G[gid]["club_id"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split(":"))
        if o["result_flag"] == "pens": sys.exit("다른 차전이 승부차기 " + gid)
        OTHER_LEG_LOG.append((gid, oid, o["final"], "played" if oid in G else "not played"))
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    if m["other_leg_score"]:
        oh, oa = map(int, m["other_leg_score"].split(":"))
        OTHER_LEG_LOG.append((gid, oid, m["other_leg_score"], "score only"))
        return (oh, oa) if side_of(gid) == "h" else (oa, oh)
    sys.exit("다른 차전 못 찾음 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g)
    if not is_leg(g["competitionId"], rnd): return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if "1st" in rnd.lower() else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
# 2008 수다메리카나 1라운드 2차전 인데펜디엔테전(합산 3-3, 원정골 같음 → 승부차기): 그 해 대회는 결승만 연장, 나머지는 바로 승부차기 → TM 120분을 90분으로(비에이라 2003 커뮤니티 실드 선례)
MIN_FIX = {"923380": (90, "2008 수다메리카나 1라운드 2차전 인데펜디엔테전, 연장 없이 승부차기")}
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    if not g["playedMinutes"]: sys.exit("출전 분 없음 " + g["gameId"])
    mn = MIN_FIX[g["gameId"]][0] if g["gameId"] in MIN_FIX else int(g["playedMinutes"])
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), mn])

# Transfermarkt에 '명단 외'로만 있는 1995-96 경기 중 RSSSF(arg96) 경기 줄에 베론 골이 있는 4경기(크레스포 선례).
# 날짜·스코어는 TM API 항목(경기 id)과 RSSSF가 같음. 출전 분 자료 없음 → 90분 추정(est 1). PK 표시 없음.
# (TM id, 날짜, 상대, 대회 TM, 리그 시즌 id, 홈/원정, 골 분, 골 전 우리-상대, RSSSF 득점 줄)
EXTRA = [
    ("4973305", "1995-11-19", "Club Ferro Carril Oeste", "ARG1", 1995, 14, (0, 0), "[84' Vidal - 14' J.S. Verón, 36' Peralta (o.g.), 38' Palermo, 71' Maciel] 페로 1-4 에스투디안테스"),
    ("4973313", "1995-11-26", "CA Lanús", "ARG1", 1995, 38, (0, 1), "[38' J.S. Verón, 52' Calderón (p) - 34' Simionato (p)] 에스투디안테스 2-1 라누스"),
    ("4967994", "1996-05-19", "AA Argentinos Juniors", "ARGC", 1995, 30, (1, 0), "[22' Fabbri, 30' J.S. Verón, 60' Caniggia, 71' S.D. Martínez - 63' Cardinal (p)] 보카 4-1 아르헨티노스(영어 위키백과 시즌 문서도 30분)"),
    ("4967999", "1996-05-26", "CA San Lorenzo de Almagro", "ARGC", 1995, 44, (1, 1), "[6' Silas - 16' C.A. González, 44' J.S. Verón] 산로렌소 1-2 보카(영어 위키백과 시즌 문서 45분)"),
]
for x in EXTRA: M.append([x[1], x[2], "lg", 90, 1])
M.sort(key=lambda m: m[0])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

FM = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FM[r["tm_gameId"]].append(r)
FMOK = {r["tm_gameId"] for r in rd("fotmob_veron_match_stats.csv")}

# 2014.8 이후 도움: 두 독립 출처로 확인한 것만(ESPN 경기 문자중계 + 텔람 통신 기사 — 판정 기록 4절)
CONFIRMED_LATE = {("2850733", "80"): "ESPN 경기 문자중계('Assisted by Juan Sebastián Verón') + 경기 기사(La Capital MDP·Diario de Cuyo 같은 통신 기사: '베론의 도움으로 세 번째 골') + FotMob 시즌 도움 1"}
A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty") or t.startswith("Handball"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    if d >= GAP:
        if (gid, e["minute"]) in CONFIRMED_LATE:
            A_STATUS.append((d, gid, e["minute"], e["scorer"], "2014.8 이후, 두 출처 확인")); return None
        return "2014.8 이후 Transfermarkt 단일 출처(확인 못 함)"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM 단독(2014.8 전 허용)" + ("" if t else ", 유형 빈칸")))
    return None

# 리포트 골 목록의 스코어 표기 오류: 929900(2008.11.23 티그레 3-1) 90분 두 골이 둘 다 '3-1' → 베니테스 골을 3-0으로(베론 골·도움은 8·28분이라 영향 없음)
SCORE_FIX = {("929900", "Leandro Benítez"): "3-0"}
for gid_, evs_ in EVS.items():
    for e in evs_:
        if (gid_, e["scorer"]) in SCORE_FIX: e["score_home_away_after"] = SCORE_FIX[(gid_, e["scorer"])]
def ev_key(e):
    h, a = map(int, e["score_home_away_after"].split("-"))
    return h + a
raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid)
    evs = sorted(EVS[gid], key=ev_key)
    if [ev_key(e) for e in evs] != list(range(1, len(evs) + 1)):
        if any(ME in (e["scorer_id"], e["assist_id"]) for e in evs): sys.exit("골 순서 이상 " + gid + " " + str([e["score_home_away_after"] for e in evs]))
        continue
    for e in evs:
        sd_ = e["side"][0]
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = (h - (sd_ == "h"), a - (sd_ == "a"))
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"], e["goal_desc"]))
        if e["scorer_id"] == ME and is_og(e): sys.exit("자책골 " + gid)
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e, ldate(g), gid)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd_ != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0   # "Penalty rebound"(PK 막힌 뒤 리바운드)는 PK 아님
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))
cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)
    na = sum(1 for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
    if na != int(g["assists"] or 0): sys.exit("도움 수 불일치(API) " + gid)

# FotMob 대조(골 시각·PK; 2010-11 이후)
FM_CMP = []
for r in raw_rows:
    gid = r[1]
    if r[0] != "g" or gid not in FM: continue
    hit = [f for f in FM[gid] if f["veron_scorer"] == "1"]
    best = min(hit, key=lambda f: abs(int(f["minute"]) - r[2]), default=None)
    if not best or abs(int(best["minute"]) - r[2]) > 0:
        FM_CMP.append((LD[gid], opp(G[gid]), r[0], r[2], r[3], best and (best["minute"], best["extra_minute"], best["scorer"])))
FM_ONLY = [(gid, f["minute"], f["scorer"]) for gid, fl in FM.items() for f in fl
           if f["veron_scorer"] == "1" and not any(r[1] == gid and r[0] == "g" and abs(r[2] - int(f["minute"])) <= 2 for r in raw_rows)]

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G or gid not in MI: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if MI[gid]["result_flag"] == "pens" or G[gid]["gameState"] == "penalty_shootout": continue
    if (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
for gid, *_ in SCORE_MISMATCH:
    if any(r[1] == gid for r in raw_rows): sys.exit("골 목록이 최종 스코어와 다른 경기에 기록 " + gid)

# ---------------------------------------------------------------- 이름·기존 자료
ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
@functools.lru_cache(maxsize=None)
def key(n):
    k = norm(n)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
HEADS = collections.defaultdict(list)   # (팀 키, 라벨 앞부분 '아르헨티나 1부 아페르투라 2007') -> (Elo, lv)
def head_of(lv): return re.split(r" \d+위| 순위 없음", lv)[0]
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))
            HEADS[(key(nm), head_of(r["수준 라벨(lv)"]))].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "clubcolors.js", "finals.js", "jsv.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "cp", "town", "county", "albion",
        "rovers", "wanderers", "athletic", "rangers", "hotspur", "palace", "villa", "ham", "manchester", "west", "aston", "madrid", "rcd", "cd", "ud",
        "deportivo", "atletico", "sheffield", "bristol", "crystal", "queens", "park", "nottingham", "forest", "coventry", "leicester", "derby",
        "ipswich", "norwich", "southampton", "leeds", "newcastle", "everton", "chelsea", "arsenal", "liverpool", "barcelona", "valencia", "sociedad",
        "blackburn", "bolton", "middlesbrough", "wimbledon", "sunderland", "tottenham", "birmingham", "portsmouth", "stoke", "port", "vale",
        "spartak", "moscow", "bayern", "munich", "milan", "inter", "dynamo", "dinamo", "olympique", "sport", "bromwich", "wigan", "hull", "fulham",
        "charlton", "wolverhampton", "wednesday", "calcio", "acf", "racing", "stade", "associazione", "unione", "sportiva", "societe", "sportive",
        "lyon", "lille", "roma", "lazio", "benfica", "porto", "celtic", "glasgow", "psv", "eindhoven", "ajax", "amsterdam", "fenerbahce", "galatasaray",
        "besiktas", "basel", "genoa", "torino", "verona", "chievo", "hellas", "parma", "napoli", "bari", "lecce", "brescia", "bologna", "udinese",
        "atalanta", "vicenza", "reggina", "piacenza", "empoli", "cagliari", "perugia", "sampdoria", "fiorentina", "juventus", "venezia", "salernitana"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
FUZZY = set()
def same_match(o, d, sa):
    exact = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    cand = exact if (exact or sa) else [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    if cand and not exact: FUZZY.add((o, d, tuple(sorted({x[1] for b, x in cand}))))
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위 라벨 → 값(tools/league_rank_apply.py)
_LRA = {'__file__': os.path.join(ROOT, 'tools', 'league_rank_apply.py'), '__name__': 'lra'}
_argv = sys.argv; sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA['__file__'], encoding='utf-8').read().split("if __name__ == '__main__':")[0], 'lra', 'exec'), _LRA)
sys.argv = _argv
sys.path.insert(0, os.path.join(ROOT, 'tools')); import league_points as PTS
MAP_ADD = {}   # 승점 표가 있는 리그·시즌인데 상대 이름이 map에 없는 것: 표 행을 이름으로 찾아 메모리에서만 넣고 목록으로 보고(오케스트레이터가 elo/에 추가)
NO_MAP = {"볼리비아 1부 2010"}   # 표는 클라우수라 2010인데 라벨은 아페르투라 2010 순위 → map 넣지 않음(순위 곡선)
def ensure_map(lv, o):
    head = lv.split(" (")[0]; mm = re.match(r"^(.*?) (\d+)위", head)
    if not mm or mm.group(1) in NO_MAP: return
    E_ = PTS.O["seasons"].get(mm.group(1))
    if not E_ or "skip" in E_ or E_.get("ongoing"): return
    if PTS.other_score(lv, o): return
    best = max(((PTS.sim(o, r[0]), ti, ri, r[0]) for ti, t in enumerate(E_["tables"]) for ri, r in enumerate(t["rows"])), default=None)
    if not best or best[0] < 0.45: MAP_ADD[(mm.group(1), o)] = ("표에서 못 찾음", None); return
    E_.setdefault("map", {})[o] = [best[1], best[2]]
    MAP_ADD[(mm.group(1), o)] = (best[3], [best[1], best[2]], int(mm.group(2)))
def lv_value(lv, d, o=None):
    if o and not re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv): ensure_map(lv, o)
    m_ = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv)
    if m_:
        cal = m_.group(4) is None; y = int(m_.group(3)) + (0 if cal else 1)
        return int(round(_LRA["base"](_LRA["KO"][m_.group(1)], int(m_.group(2)), y, cal)))
    p = _LRA['parse'](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA['value'](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    if o:
        b, s_ = _LRA['base'](p[0], p[1], p[2], p[3]), _LRA['sd'](p[0], p[1])
        vp = PTS.value(lv, o, b, s_, _LRA['cv']) if (p[1] == 1 and p[0] in _LRA['BIG']) else PTS.value_other(lv, o, p[0], p[1], b, s_, _LRA['cv'])
        if vp is not None: v = vp
    return v

# 아르헨티나 반시즌 표(raw/ranks.txt = Transfermarkt 표; 우승 팀 대조는 판정 기록 6절)
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f.read().splitlines()[1:]:
        lg, se, rk, n, tm = line.split("|")
        RANKS[(lg, se)][key(tm)] = (int(rk), int(n))
RANK_FIX = {}   # (lg, season, key) -> (rank, n, 이유) — 공식 순위가 TM 표와 다른 것(판정 기록 6절)
def arg_head(lg, sid):
    """lg ARG1/ARGC, sid = TM 시즌 시작 연도 → 라벨 앞부분"""
    if lg == "ARG1": return f"아르헨티나 1부 {'이니시알' if sid in (2012, 2013) else '아페르투라'} {sid}"
    return f"아르헨티나 1부 {'피날' if sid in (2012, 2013) else '클라우수라'} {sid + 1}"
def arg_stage(d):
    """대륙·컵 대회의 아르헨티나 상대: 경기 날짜에 진행 중이던 반시즌"""
    y, m = int(d[:4]), int(d[5:7])
    if d <= "1996-08-11" and d >= "1996-01-01": return ("ARGC", 1995)
    return ("ARG1", y) if m >= 8 else ("ARGC", y - 1)
ARG_NEW = {}
def arg_label(o, lg, sid):
    se = f"{sid}-{str(sid + 1)[2:]}"
    k = key(o)
    if (lg, se, k) in RANK_FIX: rk, n, _ = RANK_FIX[(lg, se, k)]
    elif k in RANKS[(lg, se)]: rk, n = RANKS[(lg, se)][k]
    else: return None
    return f"{arg_head(lg, sid)} {rk}위/{n}팀"

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}   # 통합표 밖 상대: (key, 시즌) -> lv. man_elo.py에서 채움
def man(o, s, lv): MAN[(key(o), s)] = lv
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; RANK_CHK = []

ARG_OPP_IDS = None
def is_arg_team(o):
    return any(key(o) in RANKS[k] for k in RANKS if k[0] in ("ARG1", "ARGC"))

def opp_elo(o, d, gid=None, cid=None, sid=None):
    sa = gid is not None and G[gid]["club_id"] in SA_CLUBS
    cand, vals = same_match(o, d, sa)
    if not cand and gid and TMD[gid] != d: cand, vals = same_match(o, TMD[gid], sa)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    # 아르헨티나 1부 상대: 반시즌 라벨
    if cid in ("ARG1", "ARGC", "MARG") or (sa and is_arg_team(o)):
        lg, s0 = (cid, sid) if cid in ("ARG1", "ARGC") else arg_stage(d)
        head = arg_head(lg, s0)
        lab = arg_label(o, lg, s0)
        stg = "Apertura" if lg == "ARG1" else "Clausura"; yy = s0 if lg == "ARG1" else s0 + 1
        alt = TABLE.get((k, f"{yy}/{stg}"), []) + [x for x in TABLE.get((k, str(yy)), []) if head_of(x[1]) == head]
        if (k, head) in HEADS or alt:
            (e, lv), _ = collections.Counter(HEADS.get((k, head)) or alt).most_common(1)[0]
            if lab and lv.split(" (")[0] != lab: RANK_CHK.append((o, head, lv, lab))
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, head); return e, lv
        if (k, head) in MAN: lab = MAN[(k, head)]
        if lab:
            e = lv_value(lab, d, o)
            ELO_SRC["순위 라벨(직접 확인)"] += 1; ELO_LOG[(o, d)] = ("arg", e, lab); NEW_TS[(o, head)] = (e, lab); return e, lab
        MISS.append((o, d, head)); return 0, "?"
    s = eu(d)
    for ss in (s, d[:4]):
        if (k, ss) in MAN:
            lv = MAN[(k, ss)]; e = lv_value(lv, d, o)
            ELO_SRC["순위 라벨(직접 확인)"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, ss)] = (e, lv); return e, lv
    for ss in (s, d[:4]):
        if (k, ss) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, ss)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, ss); return e, lv
    MISS.append((o, d, s)); return 0, "?"

exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, gid, cid, int(g["seasonId"]))
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
for gid_, d, o, lg, sid, mi, (gf, ga), _ in EXTRA:
    elo, lv = opp_elo(o, d, None, lg, sid)
    E.append(["g", o, elo, "lg", mi, gf, ga, 0, 0, d, 0, 0, lv, 0])
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
    for x in sorted(NEW_TS.items()): print("NEW", x)
    for x in RANK_CHK: print("RANKCHK", x)
    sys.exit(0)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None): d.append(f"단판/합산 {a[7]}{a[14] if len(a) > 14 else ''}/{b[7]}{b[14] if len(b) > 14 else ''}")
    if a[10] != b[10]: d.append("연장")
    return d
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Ver[oó]n$", str(x[13] or "")):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(베론 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("베론 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("타인 도움 행이 베론 골과 같은 시각", b, r[9], r[4], hit[0][13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x[1], r[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    OMK = collections.defaultdict(list)
    for mm in om: OMK[key(mm[1])].append(mm)
    for m in M:
        for mm in OMK.get(key(m[1]), []):
            if mm[0] == m[0] and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
            elif mm[0] != m[0] and abs((datetime.date.fromisoformat(mm[0]) - datetime.date.fromisoformat(m[0])).days) <= 2:
                CROSS.append(("같은 상대 출전 행 날짜 1~2일 차이", b, m[0], mm[0], m[1]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 베론 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5], x[13]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
STINTS = [("에스투디안테스 1993~1996", "1996-02-01"), ("보카 주니어스 1996", "1996-08-20"), ("삼프도리아 1996~1998", "1998-07-01"),
          ("파르마 1998~1999", "1999-07-01"), ("라치오 1999~2001", "2001-07-15"), ("맨체스터 유나이티드 2001~2003", "2003-08-01"),
          ("첼시 2003~2004", "2004-08-01"), ("인테르 2004~2006", "2006-07-01"), ("에스투디안테스 2006~2012", "2012-07-01"),
          ("에스투디안테스 2013~2014", "2014-07-01"), ("에스투디안테스 2017", "9999")]
CAL_STINTS = {"에스투디안테스 1993~1996", "보카 주니어스 1996", "에스투디안테스 2006~2012", "에스투디안테스 2013~2014", "에스투디안테스 2017"}
def stint(d):
    for n, u in STINTS:
        if d < u: return n
def season_of(d):
    if stint(d) in CAL_STINTS: return d[:4]
    y, m = int(d[:4]), int(d[5:7]); s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for n, u in STINTS)
for m in M: ST[stint(m[0])][0] += 1; ST[stint(m[0])][3] += m[3]
for r in E: ST[stint(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
def d_(x): y, m, d = x.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}경기 {v[1]}골 {v[2]}도움"
EXJ = [j for j in judg if j[0] == "도움 제외"]
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
SEASONS = collections.OrderedDict()
for m in sorted(M):
    s_ = season_of(m[0]); SEASONS.setdefault(s_, [0, 0, 0, 0]); SEASONS[s_][0] += 1; SEASONS[s_][3] += m[3]
for r in E: SEASONS[season_of(r[9])][1 if r[0] == "g" else 2] += 1
exec(open(os.path.join(HERE, "note_veron.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "elk", "elq", "cwc", "df", "clg", "cl16", "TM", "lib", "csa"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6], r[13])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
mdates = collections.Counter(m[0] for m in M)
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
for d, rs in by.items():
    if d not in mdates: problems.append(("E 날짜가 M에 없음", d))
    gl = sorted(rs, key=lambda r: (r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5))
    for a, b in zip(gl, gl[1:]):
        if b[5] < a[5] or b[6] < a[6]: problems.append(("스코어 역순", d, a[4], b[4]))
for r in E:
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if not r[2] or r[12] == "?": problems.append(("Elo 없음", r))
mm_ = {m[0]: m for m in M}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > 90 and not r[10] and not r[11]: problems.append(("90분 넘는 정규 시간 골", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))
for typ, gid, mi, dm, *_ in raw_rows:
    gm = G[gid]
    if mi <= 90 and gm["gameDuration"] in ("", "90") and int(gm["playedMinutes"]) < 90:
        pm = int(gm["playedMinutes"])
        if gm["isStarting"] in ("1", "True") and mi > pm + 2: problems.append(("선발인데 골·도움 분이 교체 아웃 뒤", gid, mi, pm))
        if gm["isStarting"] not in ("1", "True") and mi < 90 - pm - 2: problems.append(("교체 투입 전 골·도움", gid, mi, pm))

if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    for k, v in SEASONS.items(): print(" ", k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), "TM_A", TM_A, "untyped a", UNTYPED)
    for j in judg: print(j)
    print(collections.Counter(a[4] for a in A_STATUS))
    print("fuzzy same-match", sorted(FUZZY))
    print("FotMob diffs", FM_CMP); print("FotMob only", FM_ONLY)
    for c in CROSS: print(c)
    print("score mismatch", SCORE_MISMATCH)
    print("dates changed", len(DATE_LOG))
    print("other legs", [x for x in OTHER_LEG_LOG if x[3] != "played"])
    for x in sorted(NEW_TS.items()): print("NEW", x)
    for x in RANK_CHK: print("RANKCHK", x)
    for k_, v_ in sorted(MAP_ADD.items()): print("MAPADD", k_, v_)
    print("problems", problems)
    sys.exit(0)

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const {PFX}_E={J(E)};\nconst {PFX}_M={J(M)};\nconst {PFX}_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "fotmob_diffs": FM_CMP, "fotmob_only": FM_ONLY, "cross_check": CROSS, "elo_sources": ELO_SRC, "date_changes": DATE_LOG,
               "extra_games": EXTRA, "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
