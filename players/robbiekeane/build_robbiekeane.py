#!/usr/bin/env python3
"""로비 킨 (Robbie Keane, Transfermarkt 3144, FotMob 24635): raw/ -> robbiekeane.json + players/robbiekeane/rkn.js (판정 근거는 judgments.md)

  python3 players/robbiekeane/build_robbiekeane.py [--out <data 폴더>]   # 스크래치 검증: SOC_ROOT=<복사본> … --out <복사본>/src/data
  python3 players/robbiekeane/build_robbiekeane.py --debug | --stat | --ties | --mapneed

크리스 킨 build 스크립트(같은 수집기 raw 형식)를 킨에 맞춰 고친 것. 순위 라벨 행의 Elo는 tools/league_rank_apply.py
parse()/value()(+ tools/league_points.py 승점 모형)로 라벨에서 계산. 같은 경기가 다른 선수 자료에 있으면 그 값,
같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "rkn.js")
OUT_JSON = os.path.join(HERE, "robbiekeane.json")
ME = "3144"
ME_KO = "로비 킨"
CUTOFF = "2026-11-25"
GAP = "2014-08-01"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# 리저브(웨스트햄 21세 이하 2011.3.15)는 team_level로 빠짐. 뺄 1군 클럽 없음
EXCL_CLUB = set()
ALL_SENIOR = [g for g in rd("tm_games.csv") if g["team_level"] == "senior"]
GAMES = [g for g in ALL_SENIOR if g["clubId"] not in EXCL_CLUB]
EXCL_GAMES = [g for g in ALL_SENIOR if g["clubId"] in EXCL_CLUB]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["fotmob_matchId"]}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}
TIES = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 날짜·출전 분
# 날짜를 정하지 않은 유럽 경기(TM UTC 22:00/23:00)의 TM 날짜가 하루 이른 경우: soccerbase + 경기 기사로 고침(judgments.md 2절)
DATE_FIX = {"4294308": "1998-08-18", "28619": "2005-04-25", "38103": "2006-04-30", "55663": "2007-01-14", "55693": "2007-02-04"}
# 2013.11.7 MLS 플레이오프 RSL 원정(연장): TM 90분이나 경기 JSON·FotMob 모두 교체 없음 → 연장 포함 120분
MIN_FIX = {"2378385": 120}
EV_MIN_FIX = {}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local"])
OPP_NAME = {"Odisha FC": "Delhi Dynamos FC"}   # 2017-18 당시 이름(델리 다이너모스, 2019년 오디샤로 이전·개명)
RNAME = {"Chennai City FC": "Chennai City"}   # 순위표(위키백과) 이름
def opp(g):
    o = re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
    o = re.sub(r"\s*\(\s*\d{4}\s*-\s*\d{4}\)", "", o).strip()
    return OPP_NAME.get(o, o)
def rnd_of(g): return g["round"] or ""

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "EFD2", "IT1", "SC1", "MLS1", "IND1"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("FAC", "CGB", "SFA", "CIT", "MLSP", "INSC"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth") or r.startswith("6th"): return "dk"   # FA컵 6라운드 = 8강
        return "dc"
    if cid == "SCI": return "df"                            # 수페르코파 이탈리아나 = 국내컵 결승 비중
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"         # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        return "elk"                                        # 2라운드·3라운드·16강·8강 = 토너먼트(비두카·세도르프 선례)
    if cid == "CLQ": return "clq"
    if cid == "CL": return "clg"
    if cid == "POUS":
        if r.startswith("final"): return "mlpf"
        if r.startswith("semi"): return "mlpsf"             # 컨퍼런스 결승
        return "mlp"
    if cid == "CCL":
        if r.startswith("group"): return "ccc"
        if r.startswith("semi"): return "cccsf"
        if r.startswith("final"): return "cccf"
        return "ccck"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

def tie_rule(cid, d, rnd):
    if cid in ("CGB", "UEFA", "CLQ", "CIT"): return (1, 1)   # 리그컵(준결승 2017-18까지)·UEFA·코파 이탈리아: 원정 다득점·연장
    if cid == "CCL": return (1, 0)                           # 북중미 챔스: 원정 다득점, 연장 없이 승부차기
    if cid == "POUS": return (int(d >= "2014-01-01"), 1)     # MLS 플레이오프 두 경기: 2011~2013 원정 다득점 없음·연장, 2014부터 원정 다득점(앙리·베컴 자료)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["clubId"]: return "h"
    if m["away_id"] == g["clubId"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    t = TIES.get(gid)
    if not t: sys.exit("다른 차전 없음 " + gid)
    oid = t["other_leg_id"]; club_name = G[gid]["club"]
    o = TIES[oid]; fh, fa = map(int, re.match(r"(\d+)-(\d+)", o["final"]).groups())
    if o["home"] == club_name: return (fh, fa)
    if o["away"] == club_name: return (fa, fh)
    sys.exit("다른 차전 편 판정 실패 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# 클럽 구분: 영어 위키백과 이적·임대 날짜(브리스틀 시티·레스터는 첫 경기 날짜)
CLUBS = [("wolrbk", "1999-08-20"), ("covrbk", "2000-07-01"), ("intrbk", "2000-12-22"), ("leerbk", "2002-08-31"), ("totrbk", "2008-07-28"),
         ("livrbk", "2009-02-02"), ("totrbk", "2010-02-01"), ("celrbk", "2010-06-01"), ("totrbk", "2011-01-31"), ("whurbk", "2011-06-01"),
         ("totrbk", "2011-08-15"), ("lagrbk", "2012-01-10"), ("avlrbk", "2012-03-01"), ("lagrbk", "2017-08-01"), ("atkrbk", None)]
TM_CLUB = {"543": "wolrbk", "990": "covrbk", "46": "intrbk", "399": "leerbk", "148": "totrbk", "31": "livrbk", "371": "celrbk", "379": "whurbk",
           "1061": "lagrbk", "405": "avlrbk", "45278": "atkrbk"}
JUL10 = set()
CAL = {"lagrbk"}   # 번리: 2018.7.26 유로파 예선 = 2018-19(7월 10일 기준), 2020년 7월 PL 재개 경기 = 2019-20(울버햄프턴 wolrj와 같은 묶음, 수동 패치)
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
def season_of(d):
    y = int(d[:4]); m = int(d[5:7]); dd = int(d[8:10])
    if club_of(d) in CAL: return str(y)
    if club_of(d) in JUL10 and not ("2020-07-01" <= d < "2020-09-01"):
        s_ = y if (m > 7 or (m == 7 and dd >= 10)) else y - 1
        return f"{s_}-{str(s_ + 1)[2:]}"
    s_ = y if m >= 8 else y - 1
    if y == 2020 and m == 8: s_ = 2019
    return f"{s_}-{str(s_ + 1)[2:]}"
# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0
def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal" or e["api_actionId"] == "206"
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())
def same_scorer(a, b):
    ta, tb = norm(a).split(), norm(b).split()
    return bool(ta and tb and ta[-1] == tb[-1])
def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["keane_assist"] == "1" and f["pen_shootout_event"] != "True" and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])): return True
    return False
def fm_other_assister(gid, e):
    for f in FME.get(gid, []):
        if f["keane_assist"] != "1" and f["assistStr"] and fm_min_match(f, e["minute"]) and same_scorer(f["scorer"], e["scorer"]): return f["assistStr"]
    return None

A_CHECK = {     # 다른 출처로 판정한 Transfermarkt 도움(judgments.md 4절)
 "2609508|54": (True, "2015.8.18 북중미 챔스 코무니카시오네스전 54분 고든 골: LA 갤럭시 공식 경기 보고서 득점 요약 'Alan Gordon (Assisted by Robbie Keane) 54''·MLSsoccer.com/LAG Confidential 경기 기사(킨이 고든에게 연결) → 넣음(FotMob 도움 칸 비어 있음)"),
 "3113582|58": (False, "2018.3.16 슈퍼컵 예선 첸나이 시티전 58분 제키냐 골: 경기 기사(sportskeeda 등)는 킨이 컷백 → 음바타가 내준 공을 제키냐가 마무리 — 마지막 패스는 음바타라 뺌"),
}
ADD_A = []       # FotMob 단독 도움 중 다른 출처 2곳이 확인한 것(없음)
A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도('Penalty: Fouled player')"
    if t == "Handball (opponent)": return "상대 핸드볼 PK"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    k = f"{gid}|{e['minute']}"
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else why
    if fm_assist(gid, e):
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    oth = fm_other_assister(gid, e)
    if oth: sys.exit(f"FotMob이 다른 도움자를 적은 도움 판정 누락 {k} {oth}")
    if d < GAP:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "2014.8 이전 TM 단독(유형 " + (t or "빈칸") + ") 선례대로 넣음")); return None
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음"))
    return "2014.8 이후 단일 출처(판정 없음)"

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and is_og(e): judg.append(("본인 자책골(골 아님)", ldate(g), opp(g), e["minute"]))
        if e["assist_id"] == ME and e["scorer_id"] == ME: judg.append(("본인 PK 골의 본인 도움(도움 아님)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(EV_MIN_FIX.get((gid, e["minute"]), e["minute"]))
        if is_a:
            if sd != side:
                judg.append(("상대 골 도움 칸(도움 아님)", ldate(g), opp(g), e["minute"], e["scorer"], e["assist_type"])); continue
            why = assist_reason(e, ldate(g), gid)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if (e["penalty"] == "1" or e["api_actionId"] == "204") and e["api_actionId"] != "205" else 0   # PK 막힌 뒤 리바운드 골은 일반 골
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))
for gid, mi, dm, gf, ga, scorer in ADD_A:
    raw_rows.append(("a", gid, mi, dm, gf, ga, 0, scorer))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["keane_assist"] == "1" and f["pen_shootout_event"] != "True":
            if not any(e["assist_id"] == ME and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, int(f["time"]) + int(f["overloadTime"] or 0), f["scorer"]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

# ---------------------------------------------------------------- 이름·기존 자료
ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
MANUAL_ALIAS = {}
NO_ALIAS = {"cd nacional"}   # 별칭 표가 우루과이 Club Nacional 쪽에 'CD Nacional'을 묶어 둠 — 마데이라의 CD 나시오날은 따로
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    if k in NO_ALIAS: return k
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue   # 이 선수만 쓴 팀-시즌만 건너뜀
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "rkn.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
PAR = {}   # 이번 회차 병렬 판정(읽기만)
for slug in ("adebayor", "santacruz", "seydoukeita", "jemaa"):
    for pth in glob.glob(os.path.join(os.path.dirname(HERE), slug, "*.js")):
        try: P, oe, om = load_js(pth)
        except Exception: continue
        PAR["players/" + slug + "/" + os.path.basename(pth)] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss", "us", "vfl", "vfb", "tsg",
        "real", "borussia", "bayer", "eintracht", "hamburger", "olympique", "atletico", "athletic", "fk", "sk", "bv", "1899", "1909", "1907", "1913", "1846", "05", "04", "96", "1919"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d, cid):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    if not cand:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if toks(x[1]) and toks(x[1]) == toks(o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위 라벨 → Elo (tools/league_rank_apply.py)
_LRA = {"__file__": os.path.join(ROOT, "tools", "league_rank_apply.py"), "__name__": "lra"}
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA["__file__"], encoding="utf-8").read().split("if __name__ == '__main__':")[0], "lra", "exec"), _LRA)
sys.argv = _argv
sys.path.insert(0, os.path.join(ROOT, "tools"))
import league_points as PTS
MAPNEED = []
def lv_value(lv, d, o=None):
    mm = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv)
    if mm:   # 순위 없음: 그 나라·단계·시즌 기준점
        cal = mm.group(4) is None; y = int(mm.group(3)) + (0 if cal else 1)
        return int(round(_LRA["base"](_LRA["KO"][mm.group(1)], int(mm.group(2)), y, cal)))
    p = _LRA["parse"](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA["value"](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    if o is not None:
        b = _LRA["base"](p[0], p[1], p[2], p[3]); sdv = _LRA["sd"](p[0], p[1])
        if p[1] == 1 and p[0] in _LRA["BIG"]:
            vp = PTS.value(lv, o, b, sdv, _LRA["cv"])
        else:
            vp = PTS.value_other(lv, o, p[0], p[1], b, sdv, _LRA["cv"])
            hd = re.match(r"^(.*?) \d+위", lv.split(" (")[0])
            ent = PTS.O["seasons"].get(hd.group(1)) if hd else None
            if vp is None and ent and "skip" not in ent and not ent.get("ongoing"):
                MAPNEED.append((hd.group(1), o, lv))
        if vp is not None: v = vp
    return v

WIKI_LG = {"en.wiki First Division": "EFD2", "en.wiki Second Division": "EFD3", "en.wiki Third Division": "EFD4", "en.wiki I-League": "ILG"}
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or "group" in p[1] or p[0].startswith("CRC"): continue   # MLS 2014~16 컨퍼런스 표는 쓰지 않음(전체 순위는 man)
        lg = WIKI_LG.get(p[0], p[0]); ss = p[1].split(" ")[0].replace("\u2013", "-")
        if re.match(r"^\d{4}-\d{4}$", ss): ss = ss[:5] + ss[7:]
        RANKS[(lg, ss)][key(p[4])] = (int(p[2]), int(p[3]), p[4])

# 감점 시즌(elo/penalty_seasons.json): 라벨 머리 + 팀 → 감점 전 순위
PEN = {}
for c in json.load(open(os.path.join(ELO, "penalty_seasons.json"), encoding="utf-8"))["changes"]:
    hd = c["line"].split(" [")[0].replace("챔피언십(2부)", "챔피언십")
    PEN[(hd, key(c["team"]))] = c["onfield"]
# penalty_seasons.json 목록은 기존 자료에 나온 팀만 적혀 있어, 같은 시즌의 다른 팀(예: 2009-10 챔피언십 입스위치, 2010-11 리그 원 플리머스)은
# 승점 표(elo/league_points_other.json, '감점 전 순위' 행 순서)에서 경기장 성적 순위를 찾음
_SW = {"fc", "afc", "the"}
def _nn(n): return " ".join(t for t in norm(n).split() if t not in _SW)
def onfield_rank(hd, nm):
    ent = PTS.O["seasons"].get(hd)
    if not ent or "감점 전" not in ent.get("note", ""): return None
    rows = ent["tables"][0]["rows"]
    if hd in PEN_HEADS and (hd, key(nm)) in PEN: return PEN[(hd, key(nm))]
    if nm in ent.get("map", {}):
        t, i = ent["map"][nm]; return i + 1
    hit = [i for i, r in enumerate(rows) if _nn(r[0]) == _nn(nm)]
    if len(hit) != 1: sys.exit(f"감점 시즌 표에서 팀을 못 찾음 {hd} {nm}")
    return hit[0] + 1
PEN_HEADS = {h for h, _ in PEN}
CUR = "2026년 11월 25일 현재 순위"
# 공식 순위가 Transfermarkt 표와 다른 경우(영어 위키백과 시즌 순위표 기준): 2010-11 리그 원 트랜미어는 올덤과 승점·득실·다득점이 같고 위키백과 공식 표 18위(TM 17위)
OFFICIAL_FIX = {("GB3", "2010-11", "tranmere rovers"): 18}
def make_label(lg, season, v):
    r, n, nm = v
    r = OFFICIAL_FIX.get((lg, season, key(nm)), r)
    if lg == "GB1":
        hd = f"프리미어리그 {season}"; pr = PEN.get((hd, key(nm)))
        if season == "2026-27": return f"{hd} {r}위/{n}팀 ({CUR})"
        return f"{hd} {pr or r}위" + (" (감점 전 순위)" if pr else "")
    if lg == "GB2":
        hd = f"챔피언십 {season}"; pr = onfield_rank(hd, nm); pr = pr if pr and pr != r else None
        return f"{hd} {pr or r}위/{n}팀" + (" (감점 전 순위)" if pr else "")
    if lg == "GB3":
        hd = f"잉글랜드 3부 {season}"; pr = onfield_rank(hd, nm); pr = pr if pr and pr != r else None
        return f"{hd} {pr or r}위/{n}팀 (" + ("감점 전 순위; " if pr else "") + f"{'EFL' if int(season[:4]) >= 2016 else 'Football'} League One, 리그 수준 추정)"
    if lg == "GB4":
        hd = f"잉글랜드 4부 {season}"; pr = onfield_rank(hd, nm); pr = pr if pr and pr != r else None
        return f"{hd} {pr or r}위/{n}팀 (" + ("감점 전 순위; " if pr else "") + f"{'EFL' if int(season[:4]) >= 2016 else 'Football'} League Two, 리그 수준 추정)"
    if lg == "PO1": return f"포르투갈 1부 {season} {r}위" + ("" if n == 16 and int(season[:4]) < 2014 else f"/{n}팀")
    if lg == "TR1": return f"쉬페르리그 {season} {r}위/{n}팀"
    if lg == "GR1": return f"그리스 1부 {season} {r}위/{n}팀 (Super League Greece)"
    if lg == "SC1": return f"스코틀랜드 1부 {season} {r}위/{n}팀 (Scottish Premier League, 스플릿 뒤 최종 순위)"
    if lg == "EFD2":
        hd = f"챔피언십 {season}"; pr = onfield_rank(hd, nm); pr = pr if pr and pr != r else None
        return f"{hd} {pr or r}위/{n}팀 (" + ("감점 전 순위; " if pr else "") + "Football League First Division)"
    if lg == "EFD3":
        hd = f"잉글랜드 3부 {season}"; pr = onfield_rank(hd, nm); pr = pr if pr and pr != r else None
        return f"{hd} {pr or r}위/{n}팀 (" + ("감점 전 순위; " if pr else "") + "Football League Second Division, 리그 수준 추정)"
    if lg == "EFD4":
        hd = f"잉글랜드 4부 {season}"; pr = onfield_rank(hd, nm); pr = pr if pr and pr != r else None
        return f"{hd} {pr or r}위/{n}팀 (" + ("감점 전 순위; " if pr else "") + "Football League Third Division, 리그 수준 추정)"
    if lg == "ZYP1": return f"키프로스 1부 {season} {r}위/{n}팀 (Cypriot First Division)"
    if lg == "IND1": return f"인도 슈퍼리그 {season} {r}위/{n}팀 (Indian Super League, 정규 리그 최종 순위)"
    if lg == "ILG": return f"인도 1부 {season} {r}위/{n}팀 (I-League — 2017-18은 인도 슈퍼리그와 나란히 열린 공동 1부, AFC 챔스 예선 출전권 리그)"
    if lg == "MLS1": return f"MLS {season} {r}위/{n}팀"
    return None
LEAGUES_EU = ("GB1", "GB2", "GB3", "GB4", "EFD2", "EFD3", "EFD4", "SC1", "ZYP1", "IND1", "ILG")
LEAGUES_CAL = ("MLS1",)


def eu(d):
    y = int(d[:4]); m = int(d[5:7]); s_ = y if m >= 8 else y - 1
    if y == 2020 and m == 8: s_ = 2019
    return f"{s_}-{str(s_ + 1)[2:]}"
def seasons_for(cid, d):
    return [season_of(d) if cid in LEAGUE else eu(d), d[:4]]

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv
def man(o, s, lv): MAN[(key(o), s)] = lv
exec(open(os.path.join(HERE, "man_robbiekeane.py"), encoding="utf-8").read())   # 직접 라벨(출처는 judgments.md 5절)
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def opp_elo(o, d, cid, g):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    for s in seasons_for(cid, d):
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d, o); ELO_SRC["직접 라벨(순위표 밖)"] += 1
            ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
            p = _LRA["parse"](lv, d)
            if p and lv_value(lv, d, o) != e: TABLE_DIFF.append((o, s, e, lv, lv_value(lv, d, o)))
            return e, lv
    s = season_of(d) if cid in LEAGUE else eu(d)
    for lg in LEAGUES_EU + LEAGUES_CAL:
        ss = d[:4] if lg in LEAGUES_CAL else s
        t = RANKS.get((lg, ss), {})
        kk = k if k in t else next((x for x in t if _nn(t[x][2]) == _nn(RNAME.get(o, o))), None)
        if kk:
            lv = make_label(lg, ss, t[kk])
            e = lv_value(lv, d, o); ELO_SRC["순위표 → 라벨"] += 1
            ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, ss)] = (e, lv); return e, lv
    MISS.append((o, d, cid, s)); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, g)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)
if "--debug" in sys.argv and "--mapneed" not in sys.argv:
    print(ELO_SRC)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    print("TABLE_DIFF", TABLE_DIFF)
    print("MAPNEED", sorted(set(MAPNEED)))
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14 or r[7]: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14] if len(r) > 14 else "")
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["keane_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "1")]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "pen" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 0): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
FM_N = sum(1 for gid in EVS if gid in G and gid in FME and any(e["scorer_id"] == ME and not is_og(e) for e in EVS[gid]))
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
def same_team(a, b, d):
    if key(a) == key(b): return True
    return bool(toks(a)) and toks(a) == toks(b)
CROSS = []
VRE = re.compile(r"Robbie Keane|^Keane$|^R\. Keane$|로비 킨")
G_DATES = {ldate(g) for g in GAMES}
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for x in oe:
        if x[0] == "a" and VRE.search(str(x[13] or "")) and x[9] in G_DATES:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(킨 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1], r[9])]
            if hit: CROSS.append(("킨 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x[1], r[1], r[9]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], x[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and key(mm[1]) == key(m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[2], m[2]))
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2], x[9]):
                    CROSS.append(("TM 킨 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
SHARED = collections.Counter()
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for m in M:
        if any(mm[0] == m[0] and key(mm[1]) == key(m[1]) for mm in om): SHARED[b] += 1

# ---------------------------------------------------------------- 클럽·시즌
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["clubId"])
    if TM_CLUB[g["clubId"]] in CAL or g["competitionId"] == "INSC": continue   # 달력 연도 시즌(갤럭시)·TM '2018' 표기 슈퍼컵
    if season_of(ldate(g))[2:4] + "/" + season_of(ldate(g))[5:7] != g["season"]: sys.exit("시즌 불일치 " + g["gameId"] + " " + g["season"] + " " + ldate(g))
CLUB_KO = {"wolrbk": ("울버햄프턴 원더러스", "1997~1999"), "covrbk": ("코번트리 시티", "1999~2000"), "intrbk": ("인테르", "2000"),
           "leerbk": ("리즈 유나이티드", "2000~2002"), "totrbk": ("토트넘 홋스퍼", "2002~2008, 2009~2011"), "livrbk": ("리버풀", "2008~2009"),
           "celrbk": ("셀틱", "2010"), "whurbk": ("웨스트햄 유나이티드", "2011"), "lagrbk": ("LA 갤럭시", "2011~2016"),
           "avlrbk": ("애스턴 빌라", "2012"), "atkrbk": ("ATK(아틀레티코 데 콜카타)", "2017~2018")}
def per(k_):
    inr = lambda d: club_of(d) == k_
    return [sum(1 for m in M if inr(m[0])), sum(1 for r in E if r[0] == "g" and inr(r[9])),
            sum(1 for r in E if r[0] == "a" and inr(r[9])), sum(m[3] for m in M if inr(m[0]))]
_order = []
for m in M:
    if club_of(m[0]) not in _order: _order.append(club_of(m[0]))
ST = [(CLUB_KO[k_][0], CLUB_KO[k_][1], per(k_)) for k_ in _order]
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
def d_(x): y, m, d = x.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
if "--stat" in sys.argv:
    for v in ST: print(v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), "TM_A", TM_A)
    for j in judg: print(j)
    for a in A_STATUS:
        if a[4] != "TM+FotMob 이벤트": print(a)
    print("TM+FotMob", sum(1 for a in A_STATUS if a[4] == "TM+FotMob 이벤트"))
    print("FM only", FM_ONLY)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G, FM_CMP)
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF); print("MAPNEED", sorted(set(MAPNEED))); print("SHARED", SHARED.most_common())
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_robbiekeane.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "elk", "cwc", "clg", "cl16"]:
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
    gl = sorted(rs, key=lambda r: (r[4], r[5] + r[6]))
    for a, b in zip(gl, gl[1:]):
        if b[5] < a[5] or b[6] < a[6]: problems.append(("스코어 역순", d, a[4], b[4]))
for r in E:
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if not r[2] or r[12] == "?": problems.append(("Elo 없음", r))
    if r[9] > CUTOFF: problems.append(("기준일 뒤", r))
mm_ = {m[0]: m for m in M}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const RKN_E={J(E)};\nconst RKN_M={J(M)};\nconst RKN_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()}, "map_need": sorted(set(MAPNEED)),
               "table_label_diffs": TABLE_DIFF, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for v in ST: print(" ", v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
if "--mapneed" in sys.argv:
    out = []
    for hd, o, lv in sorted(set(MAPNEED)):
        ent = PTS.O["seasons"][hd]
        rk = int(re.search(r" (\d+)위", lv).group(1))
        rows = ent["tables"][0]["rows"]
        hits = [i for i, r in enumerate(rows) if _nn(r[0]) == _nn(o)]
        if len(hits) != 1 or hits[0] + 1 != rk:
            print("확인 필요", hd, o, rk, [(i, r[0]) for i, r in enumerate(rows) if _nn(r[0]).split()[0] == _nn(o).split()[0]]); continue
        out.append((hd, o, rows[hits[0]][0], 0, hits[0]))
    for x in out: print(f"{x[0]} | {x[1]} | {x[2]} | [{x[3]}, {x[4]}]")
    json.dump(out, open(os.path.join(HERE, "mapneed.json"), "w", encoding="utf-8"), ensure_ascii=False)
