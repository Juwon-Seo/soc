#!/usr/bin/env python3
"""마리오 만주키치 (Transfermarkt 34572): raw/ -> mandzukic.json + src/data/mzk.js (판정 근거는 judgments.md)

  python3 players/mandzukic/build_mandzukic.py            # 파일 쓰기
  python3 players/mandzukic/build_mandzukic.py --debug    # Elo 출처 로그만 출력
  python3 players/mandzukic/build_mandzukic.py --stat     # 요약·판정·동료 대조
  python3 players/mandzukic/build_mandzukic.py --ties     # 합산 행

호비뉴 build 스크립트(players/robinho)를 바탕으로 함. 입력: raw/tm_games.csv(출전·분·날짜), raw/tm_events.csv(리포트 골 목록),
raw/tm_match_info.csv(리포트 머리·다른 차전), raw/fotmob_events.csv(2010-11 이후 골·도움 대조), raw/ranks.txt(순위표),
elo/opponent_elo_by_team_season.csv + aliases.csv, elo/league_*_mean.json, tools/league_era_normalize.py(크로아티아 등 리그 수준),
src/data/*.js(git에 올라간 다른 선수 자료). 웹 확인 근거는 judgments.md.
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "mzk.js")
OUT_JSON = os.path.join(HERE, "mandzukic.json")
ME = "34572"
ME_KO = "마리오 만주키치"

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

# ---------------------------------------------------------------- 경기 단위 출처로 더하는 경기(Transfermarkt에 없거나 '명단 제외')
# 크레스포·바티스투타 선례: 골 시각이 있는 경기 단위 출처가 만주키치 골을 적은 경기만, 출전 90분 추정.
#   영어 위키백과 2007–08·2008–09 Croatian Football Cup 문서(경기 상자: 날짜·스코어·득점자·분)
EXTRA = [
    # id, date, comp(TM), round, venue, opponent, opp_id, final(h:a), minutes, goals[(minute, '', pk)], other leg (ours, theirs) or None, leg
    dict(gameId="X20080409", date="2008-04-09", competitionId="KRC", round="Semi-Finals 1st Leg", club_id="419", venue="H",
         opponent="NK Zagreb", final="3:1", minutes=90, goals_seq=[("h", "30", ME), ("h", "42", ""), ("a", "58", ""), ("h", "90", "")], leg=1),
    dict(gameId="X20090318", date="2009-03-18", competitionId="KRC", round="Semi-Finals 2nd Leg", club_id="419", venue="H",
         opponent="NK Zagreb", final="4:1", minutes=90, goals_seq=[("h", "10", ME), ("h", "18", ME), ("h", "38", ME), ("a", "87", ""), ("h", "88", "")],
         leg=2, other=(2, 0)),   # 1차전 2009.3.4 NK 자그레브 0-2 디나모(위키백과)
]

# ---------------------------------------------------------------- 날짜(모두 Transfermarkt 일정 날짜 = 경기 현지 날짜, 빌드에서 UTC→현지 변환과 같음 확인)
def ldate(g):
    if g["gameId"].startswith("X"): return g["date"]
    s = g["date_tm_schedule"]
    if s: return datetime.datetime.strptime(s.split()[1], "%d/%m/%Y").date().isoformat()
    return g["date_local_tm_report"]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"KR1", "L1", "ES1", "IT1", "QSL"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("KRC", "DFB", "CDR", "CIT", "QUC1"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("DFL", "SUC", "SCI", "USC"): return "df"
    if cid == "KLUB": return "cwc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "CLQ": return "clq"
    if cid in ("UI", "ELQ"): return "elq"   # 인터토토컵 = 유로파 예선(기존 선례)
    if cid == "UEFA":   # UEFA컵 1라운드 = 유로파 예선, 조별 = 유로파 조별(§3)
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        return "elk"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "AFCL":
        if r.startswith("group") or "16" in r: return "acl"
        return "aclk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g):
    return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "CLQ", "UEFA", "EL", "ELQ", "UI", "CDR", "CIT", "SUC"): return (1, 1)
    if cid == "KRC": return (1, 0)   # 크로아티아컵: 원정 다득점(2006 결승 위키백과 'won on away goals rule'), 연장 없이 승부차기(2009 결승 경기 규칙)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g = G[gid]
    if g["venue"] == "H": return "h"
    if g["venue"] == "A": return "a"
    m = MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; oid = m["other_leg_id"]; club = G[gid]["club_id"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split(":"))
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    return (oh, oa) if side_of(gid) == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    if gid.startswith("X"): ours, theirs = g["other"]
    else: ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
for x in EXTRA: G[x["gameId"]] = x
MIN_FIX = {"4268921": (90, "2009 크로아티아컵 결승 2차전: Transfermarkt 120분이나 경기 규칙이 '90분, 연장 없이 승부차기'(위키백과 결승 문서)라 90분")}
M = []
for gid, g in sorted(G.items(), key=lambda kv: (ldate(kv[1]), kv[0])):
    c = comp_of(g["competitionId"], rnd_of(g))
    if gid.startswith("X"): M.append([ldate(g), opp(g), c, g["minutes"], 1]); continue
    mins_ = MIN_FIX[gid][0] if gid in MIN_FIX else int(g["playedMinutes"])
    M.append([ldate(g), opp(g), c, mins_])

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

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["minute"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["minute"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["mandzukic_assist"] == "1" and fm_min_match(f, e["minute"]): return True
    return False

# 2014.8 이후 Transfermarkt·FotMob 한쪽에만 있는 도움: 다른 출처 2곳 확인 결과(judgments.md 4절, 웹 확인 2026-11-19)
A_CHECK = {
    "2800305|22": (True, "SI('Dybala met Mario Manduzkic's bouncing header of set-up') + LaPresse('al 22' ... su assist di Mandzukic')"),
    "2840938|22": (True, "SI('The goal was set up by Mario Mandzukic, who hit the cut-back pass') + FourFourTwo('Mario Mandzukic's cut-back') + Football España"),
    "2726788|43": (True, "Juventus.com('turning in Mandzukic's knockdown') + FourFourTwo('Mandzukic's knockdown') + Blitz Quotidiano('Mandzukic che di testa corregge per Higuain')"),
    "3011975|65": (False, "FourFourTwo: 돈나룸마가 놓친 공을 베나티아가 밀어 넣음(골키퍼 실수로 흘러나온 공) — 도움 아님"),
}
A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    if d < GAP: return None
    k = f"{gid}|{e['minute']}"
    if fm_assist(gid, e):
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "Transfermarkt+FotMob")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "2014.8 이후 단일 출처(" + why.split(":")[0] + ")"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음"))
    return "2014.8 이후 단일 출처(판정 없음)"

# 이벤트 열(합성 경기 포함)
def events_of(gid):
    g = G[gid]
    if gid.startswith("X"):
        return [dict(side=("home" if s == "h" else "away"), minute=m, scorer_id=sc, scorer=("Mario Mandžukić" if sc == ME else ""),
                     assist_id="", assist_type="", goal_desc="", own_goal="0", penalty="0") for s, m, sc in g["goals_seq"]]
    return EVS.get(gid, [])

raw_rows, judg = [], []
for gid in sorted(G, key=lambda k: (ldate(G[k]), k)):
    g = G[gid]; side = side_of(gid) if not gid.startswith("X") else ("h" if g["venue"] == "H" else "a"); cnt = {"h": 0, "a": 0}
    for e in events_of(gid):
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e): sys.exit("만주키치 자책골 " + gid)
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e, ldate(g), gid)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk and e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

# Transfermarkt 리포트에 골 목록이 없는 경기(선수 경기 성적에는 1골): 2020.1.10 카타르컵 준결승 알사일리야전 → 출처 판정은 judgments.md
NOLIST = {"3677063"}
NOLIST_GOAL = {"3677063": ("59", 0, 0, 0)}   # Gulf Times·QSL 경기 기사·The Peninsula: 59분 선제골(0-0에서), 2-0은 72분 알모에즈 알리 PK
for gid, v in NOLIST_GOAL.items():
    mi, dm = mins(v[0]); raw_rows.append(("g", gid, mi, dm, v[1], v[2], v[3], 0, ""))

# FotMob 전용 도움(TM 도움 없음): 판정 기록
FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["mandzukic_assist"] == "1":
            if not any(e["assist_id"] == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, int(f["minute"]) + int(f["overloadTime"] or 0), f["scorer"]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
GOAL_GAP = []
for gid, g in G.items():
    if gid.startswith("X"): continue
    if cnt_[(gid, "g")] != int(g["goals"] or 0):
        if gid in NOLIST and gid not in NOLIST_GOAL: GOAL_GAP.append((gid, ldate(g), opp(g), int(g["goals"]))); continue
        sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

# ---------------------------------------------------------------- 이름·기존 자료
ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
MANUAL_ALIAS = {"inter milan": "inter", "fc bayern munich": "bayern munich"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if ME_KO in r["선수"].split("·"): continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
if not TRACKED:
    TRACKED = set(subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "mzk.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "milan", "inter", "madrid", "moscow", "fk", "vfl", "bv", "nk", "hnk", "gnk", "bc", "us", "acf", "ssc", "tsg", "vfb", "fsv", "spvgg", "borussia", "eintracht", "hotspur", "manchester", "zagreb", "split", "atletico", "munich"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)] or [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
# 순위 확인(영어 위키백과·RSSSF 최종 순위표, judgments.md 5절): 크로아티아 2009-10은 Transfermarkt 표가 13·14위(동률 승점)를 바꿔 적음 → RSSSF·위키백과(상대 전적) 대로
RANKS[("KR1", "2009-10")][key("NK Inter Zapresic")] = (13, 16, "NK Inter Zapresic")
RANKS[("KR1", "2009-10")][key("NK Zagreb")] = (14, 16, "NK Zagreb")

LC = [2.51, 1.668, 1.189, 0.842, 0.664, 0.555, 0.43, 0.259, 0.079, -0.096, -0.231, -0.321, -0.412, -0.502, -0.531, -0.649, -0.814, -0.999, -1.103, -1.177, -1.378]
def cv(r, n):
    n = max(n, 2); r = min(max(r, 1), n)
    x = (r - 1) / (n - 1) * 20; i = min(19, int(x)); t = x - i
    return LC[i] + (LC[i + 1] - LC[i]) * t
def half_up(x): return int(x + 0.5)
SM = json.load(open(os.path.join(ELO, "league_season_mean.json"), encoding="utf-8"))
WM = json.load(open(os.path.join(ELO, "league_world_mean.json"), encoding="utf-8"))
def _era():
    G_ = {"__file__": os.path.join(ROOT, "tools", "league_era_normalize.py"), "__name__": "x"}
    src = open(G_["__file__"], encoding="utf-8").read().replace("if '--apply' in sys.argv:", "if False:")
    argv = sys.argv; sys.argv = ["x"]
    with contextlib.redirect_stdout(io.StringIO()): exec(compile(src, "era", "exec"), G_)
    sys.argv = argv
    return G_["otarget"], G_["OSD"]
_ERA = None
def other_v(cn, r, n, y_end):
    global _ERA
    if _ERA is None: _ERA = _era()
    return half_up(_ERA[0](cn, y_end) + _ERA[1][cn] * cv(r, n))
EU_LG = {"ES1": "라리가", "IT1": "세리에A", "L1": "분데스리가"}
OTHER_LG = {"KR1": ("Croatia", "크로아티아", 10), "SL1": ("Slovenia", "슬로베니아", 10), "A1": ("Austria", "오스트리아 분데스리가", 10)}
def rank_model(lg, season, v):
    r, n, nm = v
    if lg in EU_LG:
        pre = EU_LG[lg]
        return half_up(SM["평균"][f"{pre}|{season}"] + SM["흩어짐"][pre] * cv(r, n)), f"{pre} {season} {r}위"
    if lg in OTHER_LG:
        cn, pre, dn = OTHER_LG[lg]
        return other_v(cn, r, n, int(season[:4]) + 1), f"{pre} {season} {r}위" + (f"/{n}팀" if n != dn else "")
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []

def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o); s = eu(d); seasons = [s, d[:4]]
    for s_ in seasons:
        if (k, s_) in MAN:
            e, lv = MAN[(k, s_)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv, s_); return e, lv
    for s_ in seasons:
        if (k, s_) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s_)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s_); return e, lv
    for lg in ("KR1", "L1", "ES1", "IT1", "SL1", "A1"):
        t = RANKS.get((lg, s), {})
        if k in t:
            res = rank_model(lg, s, t[k])
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], s); return res
    MISS.append((o, d, cid, s)); return 0, "?"

# 직접 추정(순위표·통합표에 없는 팀-시즌) — judgments.md 5절
exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read()) if os.path.exists(os.path.join(HERE, "man_elo.py")) else None

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    aet = (not gid.startswith("X")) and (g["gameState"] in ("extra_time", "penalty_shootout") or MI.get(gid, {}).get("result_flag") in ("AET", "pens"))
    et = 1 if (aet and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
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
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14 or r[10]: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14] if len(r) > 14 else "")
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["mandzukic_scorer"] == "1"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["minute"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["minute"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goal_description"] + f["suffix"]).lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["minute"], f["overloadTime"], f["goal_description"], f["suffix"]))
FM_N = sum(1 for gid in EVS if gid in G and gid in FME and any(e["scorer_id"] == ME for e in EVS[gid]))
FM_G = sum(1 for gid in EVS if gid in G and gid in FME for e in EVS[gid] if e["scorer_id"] == ME and not is_og(e))

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
        if x[0] == "a" and re.search(r"Mand.uki", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(만주키치 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("만주키치 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x[1], r[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm[1], m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("Transfermarkt 만주키치 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
            if x[9] in {f[0] for f in FM_ONLY}:
                CROSS.append(("FotMob 전용 도움 경기의 타인 골", b, x[9], x[4], x[1], x[13]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("nkzmz", "2007-07-01", "NK 자그레브", "NK 자그레브", "2005~2007"), ("dinmz", "2010-07-16", "디나모 자그레브", "디나모", "2007~2010"),
         ("wobmz", "2012-07-01", "볼프스부르크", "볼프스부르크", "2010~2012"), ("baymz", "2014-07-10", "바이에른 뮌헨", "바이에른", "2012~2014"),
         ("atmmz", "2015-07-01", "아틀레티코 마드리드", "아틀레티코", "2014~2015"), ("juvmz", "2020-01-01", "유벤투스", "유벤투스", "2015~2019"),
         ("duhmz", "2021-01-19", "알두하일", "알두하일", "2020"), ("milmz", None, "AC 밀란", "밀란", "2021")]
TM_CLUB = {"5107": "nkzmz", "419": "dinmz", "82": "wobmz", "27": "baymz", "13": "atmmz", "506": "juvmz", "26091": "duhmz", "5": "milmz"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for gid, g in G.items():
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + gid)
J1 = ("nkzmz", "dinmz"); J10 = ("baymz",)
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7]); md = d[5:]
    if club in J1: s_ = y if md >= "07-01" else y - 1
    elif club in J10: s_ = y if md >= "07-10" else y - 1
    else: s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("NK 자그레브", "2007-07-01"), ("디나모 자그레브", "2010-07-16"), ("볼프스부르크", "2012-07-01"), ("바이에른 뮌헨", "2014-07-10"),
          ("아틀레티코 마드리드", "2015-07-01"), ("유벤투스", "2020-01-01"), ("알두하일", "2021-01-19"), ("AC 밀란", "9999")]
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
EXJ = [j for j in judg if j[0] == "도움 제외"]
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A)
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    print("FM only", FM_ONLY)
    print("GOAL_GAP", GOAL_GAP)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G); [print(" ", x) for x in FM_CMP]
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    sys.exit(0)

exec(open(os.path.join(HERE, "note_mandzukic.py"), encoding="utf-8").read())   # NOTE 만들기

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
    gl = sorted([r for r in rs if r[0] == "g"], key=lambda r: r[4])
    for a, b in zip(gl, gl[1:]):
        if b[4] > a[4] and (b[5], b[6]) < (a[5] + 1, a[6]) and b[5] <= a[5]: problems.append(("스코어 역순", d, a[4], b[4]))
for r in E:
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if not r[2] or r[12] == "?": problems.append(("Elo 없음", r))
mm_ = {m[0]: m for m in M}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > 90 and m[3] <= 90 and not r[11]: problems.append(("연장 분인데 출전 90분 이하", r[9], r[4], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const MZK_E={J(E)};\nconst MZK_M={J(M)};\nconst MZK_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "goal_gap": GOAL_GAP,
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
