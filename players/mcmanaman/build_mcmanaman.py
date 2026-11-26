#!/usr/bin/env python3
"""스티브 맥마나만 (Steve McManaman, Transfermarkt 3980): raw/ -> mcmanaman.json + mcm.js (판정 근거는 judgments.md)

  python3 players/mcmanaman/build_mcmanaman.py            # 파일 쓰기(players/mcmanaman/mcm.js; MCM_OUT=<경로>로 바꿀 수 있음)
  python3 players/mcmanaman/build_mcmanaman.py --debug    # Elo 출처 로그
  python3 players/mcmanaman/build_mcmanaman.py --stat     # 요약·판정·동료 대조

아이마르 build(players/aimar, 수집기 형식이 같음)를 바탕으로 함.
상대 Elo는 v1.226 규칙: 같은 경기 다른 선수 자료 → Elo 통합표(같은 팀·시즌) → 출처로 확인한 순위로 라벨을 만들고
tools/league_rank_apply.py 의 value()로 값을 정함(직접 숫자를 넣지 않음). 스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib, datetime, functools

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.environ.get("MCM_OUT") or os.path.join(HERE, "mcm.js")
OUT_JSON = os.path.join(HERE, "mcmanaman.json")
ME = "3980"
ME_KO = "스티브 맥마나만"
PFX = "MCM"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# ---------------------------------------------------------------- 날짜
# TM 리포트 날짜(없으면 TM API UTC 시각을 중부 유럽 시간으로 바꾼 날짜; 리포트가 있는 133경기는 모두 같음).
# lfchistory.net 날짜와 다른 3경기는 세 번째 출처로 확인한 날짜(judgments.md 3절).
DATE_FIX = {"1111455": ("1992-12-07", "에버턴 원정: 1992.12.7(월) — statto.com·englishfootballleaguetables.co.uk·lfchistory"),
            "3305877": ("1993-09-22", "리그컵 풀럼 원정: 1993.9.22 — 리버풀 구단 기사(파울러 데뷔)·lfchistory 신문 스캔 19930922"),
            "1183884": ("2000-01-26", "레알 베티스 홈(라리가 18라운드 연기 경기): 2000.1.26 — 영어 위키백과 1999-2000 레알 베티스 시즌·soccer-spain.com 경기 기사(맥마나만 선발). TM 1.5는 클럽 세계 선수권 알나스르전과 같은 날이라 불가능"),
            "1112925": ("1996-03-03", "애스턴 빌라 홈: 1996.3.3(일) — englishfootballleaguetables.co.uk·sportsmole·avfchistory·lfchistory")}
DATE_LOG = []
def _ldate(g):
    gid = g["gameId"]
    d = g["date_report"] or g["date_local_computed"]
    if gid in DATE_FIX:
        DATE_LOG.append((gid, d, DATE_FIX[gid][0], g["opponent"], DATE_FIX[gid][1])); return DATE_FIX[gid][0]
    return d
LD = {gid: _ldate(g) for gid, g in G.items()}
def ldate(g): return LD[g["gameId"]]

def opp(g):
    return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"EFD1", "GB1", "ES1"}
CUPS = {"FAC", "CGB", "CDR"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth"): return "dk"   # FA컵 6라운드('Sixth Round'·'Quarter-Finals'·재경기 'Deciders')·리그컵 5라운드 = 8강
        return "dc"                                                      # FA컵 3~5라운드(재경기 포함)·리그컵 2~4라운드·코파 델 레이 16강까지
    if cid in ("SUC", "USC"): return "df"                                # 수페르코파 = 국내컵 결승 비중
    if cid in ("KLUB", "WEPO"): return "cwc"                             # 클럽 세계 선수권 2000·인터콘티넨털컵 2000
    if cid == "CL":
        if r.startswith("group"): return "clg"                           # 1999~2003 1·2차 조별
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"                     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                                     # 2라운드·16강·8강
    if cid == "EPP":                                                     # 컵위너스컵: 1라운드~8강 유로파 토너먼트(바조·바티스투타·피구·아넬카 선례)
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g):
    return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")

def is_leg(cid, rnd):
    return "leg" in rnd.lower() and cid != "FAC"

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return 0
    if is_leg(cid, rnd): return 0
    if r.startswith("group") or "matchday" in r: return 0                # 챔스 조별·클럽 세계 선수권 2000 조별 = 리그식(라울·아넬카 선례)
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid):
    """(원정 다득점, 연장) — 1990~2000년대 UEFA 대회·컵위너스컵·잉글랜드 리그컵 두 경기 라운드·코파 델 레이·수페르코파"""
    if cid in ("UEFA", "CL", "EPP", "CGB", "CDR", "SUC"): return (1, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; oid = m["other_leg_id"]; club = G[gid]["club_id"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split(":"))
        if o["result_flag"] == "pens": sys.exit("다른 차전이 승부차기 " + gid)
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    if m["other_leg_score"]:
        oh, oa = map(int, m["other_leg_score"].split(":"))
        return (oh, oa) if side_of(gid) == "h" else (oa, oh)
    # API 경기(다른 차전 링크 없음): tm_cup_ties.csv(같은 클럽·시즌·대회·상대)의 1차전 스코어(클럽 기준)
    g = G[gid]
    c = [r for r in CUPT if r["seasonId"] == g["seasonId"] and r["competitionId"] == g["competitionId"] and r["opponent_id"] == g["opponent_id"]
         and "1st" in r["round(report/api)"].lower()]
    if len(c) != 1 or c[0]["gameState"] != "regularly_terminated": sys.exit("다른 차전 못 찾음 " + gid)
    if c[0]["venue"] == side_of(gid).upper(): sys.exit("다른 차전 홈 이상 " + gid)
    OTHER_LEG_LOG.append((gid, c[0]["gameId"], c[0]["score_club_opp"], c[0]["mcmanaman_participation"]))
    return tuple(map(int, c[0]["score_club_opp"].split("-")))
CUPT = rd("tm_cup_ties.csv"); OTHER_LEG_LOG = []

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g)
    if not is_leg(g["competitionId"], rnd): return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"])
    leg = 1 if "1st" in rnd.lower() else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    if not g["playedMinutes"]: sys.exit("출전 분 없음 " + g["gameId"])
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])])

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

# lfchistory.net 경기별 도움(리버풀 1990~99, 두 번째 출처)
LFC_A = collections.defaultdict(list)
for r in rd("lfchistory_assists.csv"):
    d = datetime.datetime.strptime(r["Date"].replace("Sept", "Sep"), "%d %b %Y").date().isoformat()
    LFC_A[d].append((int(r["Minute"].rstrip("'")), r["Goalscorer"]))
def lfc_assist(d, minute, scorer):
    sn = norm(scorer).split()[-1]
    return any(abs(mm - minute) <= 2 and norm(s).split()[-1] == sn for mm, s in LFC_A.get(d, []))

A_STATUS = []
def assist_reason(e, d, gid, club):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    mi_ = mins(e["minute"])[0]
    if club == "31":
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+lfchistory" if lfc_assist(d, mi_, e["scorer"]) else "TM 단독(2014.8 전 허용)"))
    else:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM 단독(2014.8 전 허용)"))
    return None

def ev_key(e):
    h, a = map(int, e["score_home_away_after"].split("-"))
    return h + a
raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid)
    evs = sorted(EVS[gid], key=ev_key)
    if [ev_key(e) for e in evs] != list(range(1, len(evs) + 1)):
        if any(ME in (e["scorer_id"], e["assist_id"]) for e in evs): sys.exit("골 순서 이상 " + gid)
        continue
    for e in evs:
        sd = e["side"][0]
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = (h - (sd == "h"), a - (sd == "a"))
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"], e["goal_desc"]))
        if e["scorer_id"] == ME and is_og(e): sys.exit("자책골 " + gid)
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e, ldate(g), gid, g["club_id"])
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))
cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

# lfchistory에만 있는 도움(TM은 같은 골에 도움자 없음): 단일 출처 → 넣지 않음(judgments.md 4절)
TM_ASSIST_KEYS = {(LD[gid], e["scorer"]) for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME}
LFC_ONLY = []
for gid, g in G.items():
    if g["club_id"] != "31": continue
    d = ldate(g)
    for mm, s in LFC_A.get(d, []):
        hit = [e for e in EVS.get(gid, []) if e["assist_id"] == ME and abs(mins(e["minute"])[0] - mm) <= 2 and norm(e["scorer"]).split()[-1] == norm(s).split()[-1]]
        if not hit: LFC_ONLY.append((d, opp(g), mm, s))
# lfchistory 골 분과 대조
LFC_G = collections.defaultdict(list)
for r in rd("lfchistory_goals.csv"):
    d = datetime.datetime.strptime(r["Date"].replace("Sept", "Sep"), "%d %b %Y").date().isoformat()
    LFC_G[d].append(int(r["Minute"].rstrip("'")))
LFC_GCMP = []
for r in raw_rows:
    if r[0] != "g" or G[r[1]]["club_id"] != "31": continue
    d = LD[r[1]]
    if not any(abs(x - r[2]) <= 1 for x in LFC_G.get(d, [])): LFC_GCMP.append((d, opp(G[r[1]]), r[2], LFC_G.get(d)))
LFC_GN = sum(len(v) for v in LFC_G.values())

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if MI[gid]["result_flag"] == "pens": continue
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
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue   # 이 선수만 쓴 팀-시즌만 건너뜀(다른 선수와 같이 쓴 행은 그대로 씀)
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "clubcolors.js", "finals.js", "mcm.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "cp", "town", "county", "albion",
        "rovers", "wanderers", "athletic", "rangers", "hotspur", "palace", "villa", "ham", "manchester", "west", "aston", "madrid", "rcd", "cd", "ud",
        "deportivo", "atletico", "sheffield", "bristol", "crystal", "queens", "park", "nottingham", "forest", "coventry", "leicester", "derby",
        "ipswich", "norwich", "southampton", "leeds", "newcastle", "everton", "chelsea", "arsenal", "liverpool", "barcelona", "valencia", "sociedad",
        "espanyol", "zaragoza", "mallorca", "betis", "sevilla", "celta", "vigo", "racing", "santander", "oviedo", "villarreal", "alaves", "osasuna",
        "rayo", "vallecano", "malaga", "tenerife", "numancia", "valladolid", "las", "palmas", "coruna", "athletic", "bilbao", "blackburn", "bolton",
        "middlesbrough", "wimbledon", "sunderland", "tottenham", "birmingham", "portsmouth", "stoke", "port", "vale", "spartak", "moscow"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d):
    exact = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    cand = exact or [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위 라벨 → 값(tools/league_rank_apply.py)
_LRA = {'__file__': os.path.join(ROOT, 'tools', 'league_rank_apply.py'), '__name__': 'lra'}
_argv = sys.argv; sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA['__file__'], encoding='utf-8').read().split("if __name__ == '__main__':")[0], 'lra', 'exec'), _LRA)
sys.argv = _argv
def lv_value(lv, d):
    p = _LRA['parse'](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA['value'](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    return v

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}   # 통합표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산). man_elo.py에서 채움
def man(o, s, lv): MAN[(key(o), s)] = lv
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []

def opp_elo(o, d):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o); s = eu(d)
    if (k, s) in MAN:
        lv = MAN[(k, s)]; e = lv_value(lv, d)
        ELO_SRC["순위 라벨(직접 확인)"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    if (k, s) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
        p = _LRA['parse'](lv, d)
        if p and _LRA['value'](*p) != e: TABLE_DIFF.append((o, s, e, lv, _LRA['value'](*p)))
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    MISS.append((o, d, s)); return 0, "?"

exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
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
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    print("TABLE_DIFF", TABLE_DIFF)
    for x in sorted(NEW_TS.items()): print("NEW", x)
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
        if x[0] == "a" and re.search(r"McManaman", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(맥마나만 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            hit.sort(key=lambda x: (abs(x[4] - r[4]), 0 if norm(r[13]).split()[-1] in norm(str(x[13])) or True else 1))
            if hit: CROSS.append(("맥마나만 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("타인 도움 행이 맥마나만 골과 같은 시각", b, r[9], r[4], hit[0][13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 맥마나만 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5], x[13]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("livsm", "1999-07-01"), ("rmsm", "2003-08-30"), ("mcism", None)]
TM_CLUB = {"31": "livsm", "418": "rmsm", "281": "mcism"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
def season_of(d):
    y, m = int(d[:4]), int(d[5:7]); s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("리버풀", "1999-07-01"), ("레알 마드리드", "2003-08-30"), ("맨체스터 시티", "9999")]
def stint(d):
    for n, u in STINTS:
        if d < u: return n
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for n, u in STINTS)
for m in M: ST[stint(m[0])][0] += 1; ST[stint(m[0])][3] += m[3]
for r in E: ST[stint(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
def d_(x): y, m, d = x.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EXJ = [j for j in judg if j[0] == "도움 제외"]
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), "TM_A", TM_A, "untyped", UNTYPED)
    for j in judg: print(j)
    print(collections.Counter(a[4] for a in A_STATUS))
    for a in A_STATUS:
        if a[4] != "TM+lfchistory" and a[0] < "1999-07-01": print(" TM only LFC", a)
    print("LFC only", LFC_ONLY)
    print("LFC goal minute diffs", LFC_GCMP, "lfc goals", LFC_GN)
    for c in CROSS: print(c)
    print("score mismatch", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0]) for m in M))
    print("dates changed", DATE_LOG)
    print("TABLE_DIFF", TABLE_DIFF)
    for x in sorted(NEW_TS.items()): print("NEW", x)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_mcmanaman.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "elk", "elq", "cwc", "df", "clg", "cl16", "TM"]:
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

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const {PFX}_E={J(E)};\nconst {PFX}_M={J(M)};\nconst {PFX}_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "lfchistory_only_assists": LFC_ONLY, "cross_check": CROSS, "elo_sources": ELO_SRC, "date_changes": DATE_LOG,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
