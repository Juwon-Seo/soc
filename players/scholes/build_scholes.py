#!/usr/bin/env python3
"""폴 스콜스 (Paul Scholes, Transfermarkt 3397): raw/ -> scholes.json + psc.js (판정 근거는 judgments.md)

  python3 players/scholes/build_scholes.py            # 파일 쓰기(players/scholes/psc.js; PSC_OUT=<경로>로 바꿀 수 있음)
  python3 players/scholes/build_scholes.py --debug    # Elo 출처 로그
  python3 players/scholes/build_scholes.py --stat     # 요약·판정·동료 대조

맥마나만 build(players/mcmanaman, 수집기 형식이 같음)를 바탕으로 함. 클럽 키·대회 코드는 긱스(players/giggs) 판정과 같게.
상대 Elo는 v1.226 규칙: 같은 경기 다른 선수 자료 → Elo 통합표(같은 팀·시즌) → 출처로 확인한 순위로 라벨을 만들고
tools/league_rank_apply.py 의 value()로 값을 정함(직접 숫자를 넣지 않음). 스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib, datetime, functools

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.environ.get("PSC_OUT") or os.path.join(HERE, "psc.js")
OUT_JSON = os.path.join(HERE, "scholes.json")
ME = "3397"
ME_KO = "폴 스콜스"
PFX = "PSC"
GAP = "2014-08-01"   # 이 날짜 전 도움은 Transfermarkt 단일 출처 허용(모든 경기가 이 전)

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# ---------------------------------------------------------------- 날짜
# TM 리포트 날짜(없으면 TM API UTC 시각을 중부 유럽 시간으로 바꾼 날짜; 리포트가 있는 367경기는 모두 같고,
# 긱스 자료의 TM 일정 날짜와 같이 뛴 509경기 모두 같음). 동료 자료와 다른 날짜는 --stat 대조로 확인.
DATE_FIX = {"1149629": ("1998-09-09", "찰턴 홈 4-1: 1998.9.9(수) — 영어 위키백과 1998-99 맨유 시즌·statmuse·sportsmole(요크 첫 골)"),
            "1055185": ("1999-08-30", "뉴캐슬 홈 5-1(콜 4골): 1999.8.30(월) — 영어 위키백과 1999-2000 맨유 시즌·nufc.com·statmuse·sportsmole"),
            "2815694": ("2003-03-02", "리그컵 결승 리버풀전 0-2(카디프): 2003.3.2 — 영어 위키백과 2003 리그컵 결승·BBC 2003.3.2 기사"),
            "55666": ("2007-01-21", "아스널 원정 1-2: 2007.1.21(일) — 영어 위키백과 2006-07 맨유 시즌·RTÉ 2007.1.21·스카이스포츠"),
            "55693": ("2007-02-04", "토트넘 원정 4-0: 2007.2.4(일) — 영어 위키백과 2006-07 맨유 시즌·thfcdb.com·맨유 구단 영상(4 Feb 2007)")}
DATE_LOG = []
def _ldate(g):
    gid = g["gameId"]
    d = g["date_report"] or g["date_local_computed"]
    if gid in DATE_FIX:
        DATE_LOG.append((gid, d, DATE_FIX[gid][0], g["opponent"], DATE_FIX[gid][1])); return DATE_FIX[gid][0]
    return d
LD = {gid: _ldate(g) for gid, g in G.items()}
def ldate(g): return LD[g["gameId"]]
TMD = {gid: (g["date_report"] or g["date_local_computed"]) for gid, g in G.items()}   # 고치기 전 TM 날짜(같은 경기 다른 선수 자료 찾기용)

def opp(g):
    return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 대회 코드(긱스 판정과 같음)
LEAGUE = {"GB1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("GBCS", "USC"): return "df"                               # 커뮤니티 실드·UEFA 슈퍼컵 = 국내컵 결승 비중
    if cid in ("WEPO", "KLUB"): return "cwc"                             # 인터콘티넨털컵 1999·클럽 월드컵 2008
    if cid in ("FAC", "CGB"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"                            # FA컵 준결승·재경기('Deciders'), 리그컵 준결승 두 경기
        if r.startswith("quarter") or r.startswith("sixth"): return "dk"  # FA컵 6라운드('Sixth Round'·'Quarter-Finals'·재경기)·리그컵 8강
        return "dc"                                                      # FA컵 3~5라운드('Round of 16' = 5라운드)·재경기, 리그컵 2~4라운드
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"                           # 1999~2003 2차 조별(Group 1·2·4) 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"                     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        return "elk"
    if cid == "EL": return "elk"                                         # 2011-12 32강(아약스)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g):
    return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")

def is_leg(cid, rnd):
    return "leg" in rnd.lower() and cid != "FAC"

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return 0
    if is_leg(cid, rnd): return 0
    if r.startswith("group"): return 0                                   # 챔스 조별 = 리그식
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    """(원정 다득점, 연장) — UEFA 대회(2020-21까지)·잉글랜드 리그컵 두 경기 라운드(준결승은 2017-18까지)"""
    if cid in ("UEFA", "CL", "CLQ", "EL", "CGB"): return (1, 1)
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
    ag, et = tie_rule(g["competitionId"], ldate(g))
    leg = 1 if "1st" in rnd.lower() else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
# 연장 없이 승부차기로 간 커뮤니티 실드(2003.8.10 아스널, 2008.8.10 포츠머스): TM 출전 120분 -> 90분(정규 시간 끝 승부차기, 출전 분 규칙)
MIN_FIX = {"2319843": (90, "2003 커뮤니티 실드 아스널전 1-1 뒤 바로 승부차기(연장 없음), TM 120분"),
           "946239": (90, "2008 커뮤니티 실드 포츠머스전 0-0 뒤 바로 승부차기(연장 없음), TM 120분")}
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    if not g["playedMinutes"]: sys.exit("출전 분 없음 " + g["gameId"])
    mn = MIN_FIX[g["gameId"]][0] if g["gameId"] in MIN_FIX else int(g["playedMinutes"])
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), mn])

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

# FotMob 경기 이벤트(2010-11~)
FM = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FM[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r["fotmob_matchId"] for r in rd("fotmob_tm_map.csv")}
def fm_has_data(gid):
    if gid not in FMMAP: return False
    p = os.path.join(RAW, "fotmob", FMMAP[gid] + ".json")
    return os.path.exists(p) and os.path.getsize(p) > 100

A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    if d >= GAP: sys.exit("2014.8 이후 도움 " + gid)
    mi_ = mins(e["minute"])[0]
    if fm_has_data(gid):
        hit = [f for f in FM[gid] if f["scholes_assist"] == "1" and abs(int(f["time"]) - mi_) <= 2]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob" if hit else "TM 단독(FotMob 다름)"))
    else:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM 단독(2014.8 전 허용)" + (" — FotMob 경기 자료 없음" if d >= "2010-08-01" else "")))
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
            why = assist_reason(e, ldate(g), gid)
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

# FotMob 대조(골·도움 시각·득점자; FotMob에만 있는 스콜스 골·도움)
FM_CMP = []
for r in raw_rows:
    gid = r[1]
    if not fm_has_data(gid): continue
    col = "scholes_scorer" if r[0] == "g" else "scholes_assist"
    hit = [f for f in FM[gid] if f[col] == "1"]
    best = min(hit, key=lambda f: abs(int(f["time"]) - r[2]), default=None)
    if not best or abs(int(best["time"]) - r[2]) > 0 or (r[0] == "g" and (best["suffix"] == "pen") != bool(r[6])):
        FM_CMP.append((LD[gid], opp(G[gid]), r[0], r[2], r[3], best and (best["time"], best["overloadTime"], best["scorer"])))
FM_ONLY = []
for gid, fl in FM.items():
    for f in fl:
        for col, typ in (("scholes_scorer", "g"), ("scholes_assist", "a")):
            if f[col] == "1" and not any(r[1] == gid and r[0] == typ and abs(r[2] - int(f["time"])) <= 2 for r in raw_rows):
                FM_ONLY.append((gid, typ, f["time"], f["scorer"]))

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "psc.js") or "src/data/" + b not in TRACKED: continue
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
        "charlton", "wolverhampton", "wednesday", "swansea", "norwich", "reading", "watford", "burnley", "blackpool", "lyon", "lille", "roma", "lazio",
        "benfica", "porto", "celtic", "glasgow", "psv", "eindhoven", "ajax", "amsterdam", "fenerbahce", "galatasaray", "besiktas", "basel", "bursaspor"}
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
sys.path.insert(0, os.path.join(ROOT, 'tools')); import league_points as PTS
def lv_value(lv, d, o=None):
    """tools/league_rank_apply.py 본체와 같은 계산(순위 곡선, 승점 표가 있으면 승점·득실 모형)"""
    p = _LRA['parse'](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA['value'](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    if o:
        b, s_ = _LRA['base'](p[0], p[1], p[2], p[3]), _LRA['sd'](p[0], p[1])
        vp = PTS.value(lv, o, b, s_, _LRA['cv']) if (p[1] == 1 and p[0] in _LRA['BIG']) else PTS.value_other(lv, o, p[0], p[1], b, s_, _LRA['cv'])
        if vp is not None: v = vp
    return v

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}   # 통합표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산). man_elo.py에서 채움
def man(o, s, lv): MAN[(key(o), s)] = lv
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []

def opp_elo(o, d, d0=None):
    cand, vals = same_match(o, d)
    if not cand and d0 and d0 != d: cand, vals = same_match(o, d0)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o); s = eu(d)
    if (k, s) in MAN:
        lv = MAN[(k, s)]; e = lv_value(lv, d, o)
        ELO_SRC["순위 라벨(직접 확인)"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
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
    elo, lv = opp_elo(opp(g), d, TMD[gid])
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
        if x[0] == "a" and re.search(r"Scholes", str(x[13] or "")):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(스콜스 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("스콜스 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("타인 도움 행이 스콜스 골과 같은 시각", b, r[9], r[4], hit[0][13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 스콜스 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5], x[13]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("munps", None)]
def season_of(d):
    y, m = int(d[:4]), int(d[5:7]); s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("맨체스터 유나이티드 1994~2011", "2011-07-01"), ("맨체스터 유나이티드 2012~2013", "9999")]
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
def c3(v): return f"{v[0]}경기 {v[1]}골 {v[2]}도움"
EXJ = [j for j in judg if j[0] == "도움 제외"]
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
UNTYPED_G = sum(1 for r in raw_rows if r[0] == "g" and not r[8])
SEASONS = collections.OrderedDict()
for m in M: SEASONS.setdefault(season_of(m[0]), [0, 0, 0, 0]); SEASONS[season_of(m[0])][0] += 1; SEASONS[season_of(m[0])][3] += m[3]
for r in E: SEASONS[season_of(r[9])][1 if r[0] == "g" else 2] += 1
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    for k, v in SEASONS.items(): print(" ", k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), "TM_A", TM_A, "untyped a", UNTYPED, "untyped g", UNTYPED_G)
    for j in judg: print(j)
    print(collections.Counter(a[4] for a in A_STATUS))
    for a in A_STATUS:
        if a[0] >= "2010-08-01": print(" ", a)
    print("FotMob diffs", FM_CMP); print("FotMob only", FM_ONLY)
    for c in CROSS: print(c)
    print("score mismatch", SCORE_MISMATCH)
    print("dates changed", DATE_LOG)
    print("other legs", [x for x in OTHER_LEG_LOG if x[3] != "played"])
    for x in sorted(NEW_TS.items()): print("NEW", x)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_scholes.py"), encoding="utf-8").read())   # NOTE_LINES
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
# 선발/교체 분 범위
for typ, gid, mi, dm, *_ in raw_rows:
    gm = G[gid]
    if mi <= 90 and gm["gameDuration"] in ("", "90") and int(gm["playedMinutes"]) < 90:
        pm = int(gm["playedMinutes"])
        if gm["isStarting"] == "1" and mi > pm + 2: problems.append(("선발인데 골·도움 분이 교체 아웃 뒤", gid, mi, pm))
        if gm["isStarting"] != "1" and mi < 90 - pm - 2: problems.append(("교체 투입 전 골·도움", gid, mi, pm))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const {PFX}_E={J(E)};\nconst {PFX}_M={J(M)};\nconst {PFX}_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "fotmob_diffs": FM_CMP, "fotmob_only": FM_ONLY, "cross_check": CROSS, "elo_sources": ELO_SRC, "date_changes": DATE_LOG,
               "minute_changes": MIN_FIX, "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
