#!/usr/bin/env python3
"""스턴 존 (Stern John, Transfermarkt 3793, soccerbase 18633): raw/ -> sternjohn.json + players/sternjohn/stj.js (판정 근거는 judgments.md)

  python3 players/sternjohn/build_sternjohn.py [--out <data 폴더>]   # 스크래치 검증: SOC_ROOT=<복사본> … --out <복사본>/src/data
  python3 players/sternjohn/build_sternjohn.py --debug | --stat | --ties | --mapneed

로비 킨 build 스크립트(같은 수집기 raw 형식)를 존에 맞춰 고친 것. FotMob 경기 자료 없음(마지막 경기 2010.5).
순위 라벨 행의 Elo는 tools/league_rank_apply.py parse()/value()(+ tools/league_points.py 승점 모형)로 라벨에서 계산.
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "stj.js")
OUT_JSON = os.path.join(HERE, "sternjohn.json")
ME = "3793"
ME_KO = "스턴 존"
CUTOFF = "2026-11-25"
GAP = "2014-08-01"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["team_level"] == "senior"]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
TIES = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 날짜·출전 분
# TM 자리표시 시각(UTC 22:00/23:00 = 베를린 자정) 경기: 미국 경기는 위키백과 1998·1999 콜럼버스 크루 시즌 문서와 모두 같은 날짜이고,
# 아래 두 US 오픈컵 경기만 하루 늦음(RSSSF·영어 위키백과). 잉글랜드 경기는 soccerbase 날짜와 모두 같음.
DATE_FIX = {"3357125": "1997-07-29", "3365146": "1999-07-13"}
MIN_FIX = {}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local"])
# 당시 팀 이름(TM은 지금 이름): 1997~1999 미국 팀만 해당
OPP_NAME = {"FC Dallas": "Dallas Burn", "Sporting Kansas City": "Kansas City Wizards", "Red Bull New York": "MetroStars",
            "San Jose Earthquakes": "San Jose Clash", "Chicago Fire FC": "Chicago Fire", "Rochester New York FC": "Rochester Raging Rhinos",
            "Salem City FC": "Carolina Dynamo"}   # 1999 US 오픈컵 3라운드 상대: RSSSF·영어 위키백과는 캐롤라이나 다이너모(TM 'Salem City FC'는 오류)
def opp(g):
    o = re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
    o = re.sub(r"\s*\(\s*\d{4}\s*-\s*\d{4}\)", "", o).strip()
    return OPP_NAME.get(o, o) if ldate(g) < "2000-01-01" else o
def rnd_of(g): return g["round"] or ""

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "GB2", "EFD2", "MLS1"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("FAC", "CGB", "MLSP"):                      # MLSP = US 오픈컵
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth") or r.startswith("6th"): return "dk"
        return "dc"
    if cid == "POUS":                                       # MLS 플레이오프(1998·1999: 컨퍼런스 준결승·결승, 3판 2선승)
        if r.startswith("final"): return "mlpf"
        if r.startswith("semi"): return "mlpsf"             # 컨퍼런스 결승
        return "mlp"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid == "POUS": return 1                              # 3판 2선승은 경기마다 단판(메시·손흥민·밤바 선례)
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    return 1

def tie_rule(cid, d, rnd):
    if cid == "CGB": return (1, 1)                          # 리그컵 1라운드 두 경기: 원정 다득점·연장
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
    if "leg" not in rnd or g["competitionId"] == "POUS": return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# 클럽 구분: Transfermarkt 이적 기록(더비 임대는 영어 위키백과 2005.9.16, 입스위치 임대 복귀 2010.1.30 경기 다음 날)
CLUBS = [("nostj", "1998-02-27"), ("colstj", "1999-11-22"), ("nfostj", "2002-02-08"), ("bcstj", "2004-09-14"), ("covstj", "2005-09-16"),
         ("derstj", "2005-12-16"), ("covstj", "2007-01-29"), ("sunstj", "2007-08-29"), ("soustj", "2008-10-24"), ("bristj", "2009-07-31"),
         ("cpstj", "2009-11-29"), ("ipsstj", "2010-01-31"), ("cpstj", None)]
TM_CLUB = {"44498": "nostj", "813": "colstj", "703": "nfostj", "337": "bcstj", "990": "covstj", "22": "derstj", "289": "sunstj",
           "180": "soustj", "698": "bristj", "873": "cpstj", "677": "ipsstj"}
CAL = {"nostj", "colstj"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
def season_of(d):
    y = int(d[:4]); m = int(d[5:7])
    if club_of(d) in CAL: return str(y)
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"

# ---------------------------------------------------------------- TM에 없는 경기(judgments.md 3절)
# 2002 퍼스트 디비전 승격 플레이오프 3경기(soccerbase·영어 위키백과·ESPN 48339/48383/48461·아이리시 타임스): 리그 비중(애슐리 영 선례),
# 준결승은 원정 다득점 없는 두 경기 합산·연장, 결승(카디프 중립)은 단판.
# 2006.9.23 크리스털 팰리스 원정(soccerbase·코번트리 팬 매치 리포트 2곳: 68~69분 교체 투입 → 22분)
EXTRA_M = [["2002-04-28", "Millwall FC", "lg", 90], ["2002-05-02", "Millwall FC", "lg", 90], ["2002-05-12", "Norwich City", "lg", 120],
           ["2006-09-23", "Crystal Palace", "lg", 22]]
# (종류, 날짜, 상대, 분, 표시분, 득, 실, 단판, PK, 연장, 메모, tie, 대회, 시즌표)
EXTRA_E = [("g", "2002-05-02", "Millwall FC", 91, "90+1", 0, 0, 0, 0, 0, 0, [2, 0, 1, 1, 0, 1]),
           ("a", "2002-05-12", "Norwich City", 102, 0, 0, 1, 1, 0, 1, "Geoff Horsfield", None)]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])
M += [list(x) for x in EXTRA_M]
M.sort(key=lambda m: m[0])

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

A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도" + (f"(유형 '{t}')" if t else "")
    if t.startswith("Penalty"): return "PK 유도('Penalty: Fouled player')"
    if t == "Handball (opponent)": return "상대 핸드볼 PK"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
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
        mi, dm = mins(e["minute"])
        if is_a:
            if sd != side:
                judg.append(("상대 골 도움 칸(도움 아님)", ldate(g), opp(g), e["minute"], e["scorer"], e["assist_type"])); continue
            why = assist_reason(e, ldate(g), gid)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if (e["penalty"] == "1" or e["api_actionId"] == "204") and e["api_actionId"] != "205" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)
# 이벤트 마지막 스코어 = 경기 최종 스코어(승부차기 제외) 확인: MLS 승부차기 경기는 TM 최종 스코어에 승부차기가 들어 있음(판정 기록)
SO_GAMES = []
for gid, g in G.items():
    evs = EVS.get(gid, [])
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, re.match(r"(\d+)-(\d+)", MI[gid]["final"]).groups())
    if (h, a) != (fh, fa):
        if g["gameState"] == "penalty_shootout": SO_GAMES.append((ldate(g), opp(g), f"{h}-{a}", f"{fh}-{fa}"))
        else: sys.exit(f"이벤트 스코어 불일치 {gid} {h}-{a} {fh}-{fa}")

# ---------------------------------------------------------------- 이름·기존 자료
ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
def key(n):
    k = norm(n)
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "stj.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
PAR = {}   # 이번 회차 병렬 판정(읽기만)
for slug in ("morata", "mitrovic", "jimenez", "ennesyri", "leekangin"):
    for pth in glob.glob(os.path.join(os.path.dirname(HERE), slug, "*.js")):
        try: P, oe, om = load_js(pth)
        except Exception: continue
        PAR["players/" + slug + "/" + os.path.basename(pth)] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "city", "united", "town", "county", "athletic", "rovers", "wanderers", "albion"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
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
    if mm:
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

WIKI_LG = {"en.wiki First Division": "EFD2", "en.wiki Football League First Division": "EFD2", "en.wiki Second Division": "EFD3",
           "en.wiki Third Division": "EFD4", "en.wiki FA Premier League": "GB1", "en.wiki Premier League": "GB1",
           "en.wiki Football League Championship": "GB2", "en.wiki Football League One": "GB3", "en.wiki League One": "GB3",
           "en.wiki Football League Two": "GB4", "en.wiki Major League Soccer season table": "MLS1"}
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] not in WIKI_LG: continue
        lg = WIKI_LG[p[0]]; ss = p[1].split(" ")[0].replace("–", "-")
        if re.match(r"^\d{4}-\d{4}$", ss): ss = ss[:5] + ss[7:]
        RANKS[(lg, ss)][key(p[4])] = (int(p[2]), int(p[3]), p[4])
RNAME = {"MetroStars": "MetroStars", "Miami Fusion": "Miami Fusion"}

PEN = {}
for c in json.load(open(os.path.join(ELO, "penalty_seasons.json"), encoding="utf-8"))["changes"]:
    hd = c["line"].split(" [")[0].replace("챔피언십(2부)", "챔피언십")
    PEN[(hd, key(c["team"]))] = c["onfield"]
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
def make_label(lg, season, v):
    r, n, nm = v
    if lg == "GB1":
        hd = f"프리미어리그 {season}"; pr = PEN.get((hd, key(nm)))
        return f"{hd} {pr or r}위" + (" (감점 전 순위)" if pr else "")
    if lg == "GB2":
        hd = f"챔피언십 {season}"; pr = onfield_rank(hd, nm); pr = pr if pr and pr != r else None
        return f"{hd} {pr or r}위/{n}팀" + (" (감점 전 순위)" if pr else "")
    if lg == "GB3":
        hd = f"잉글랜드 3부 {season}"; pr = onfield_rank(hd, nm); pr = pr if pr and pr != r else None
        return f"{hd} {pr or r}위/{n}팀 (" + ("감점 전 순위; " if pr else "") + "Football League One, 리그 수준 추정)"
    if lg == "GB4":
        hd = f"잉글랜드 4부 {season}"; pr = onfield_rank(hd, nm); pr = pr if pr and pr != r else None
        return f"{hd} {pr or r}위/{n}팀 (" + ("감점 전 순위; " if pr else "") + "Football League Two, 리그 수준 추정)"
    if lg == "EFD2":
        hd = f"챔피언십 {season}"; pr = onfield_rank(hd, nm); pr = pr if pr and pr != r else None
        return f"{hd} {pr or r}위/{n}팀 (" + ("감점 전 순위; " if pr else "") + "Football League First Division)"
    if lg == "EFD3":
        hd = f"잉글랜드 3부 {season}"; pr = onfield_rank(hd, nm); pr = pr if pr and pr != r else None
        return f"{hd} {pr or r}위/{n}팀 (" + ("감점 전 순위; " if pr else "") + "Football League Second Division, 리그 수준 추정)"
    if lg == "EFD4":
        hd = f"잉글랜드 4부 {season}"; pr = onfield_rank(hd, nm); pr = pr if pr and pr != r else None
        return f"{hd} {pr or r}위/{n}팀 (" + ("감점 전 순위; " if pr else "") + "Football League Third Division, 리그 수준 추정)"
    if lg == "MLS1": return f"MLS {season} {r}위/{n}팀"
    return None
LEAGUES_EU = ("GB1", "GB2", "GB3", "GB4", "EFD2", "EFD3", "EFD4")
LEAGUES_CAL = ("MLS1",)

def eu(d):
    y = int(d[:4]); m = int(d[5:7]); s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
def seasons_for(d):
    return [season_of(d), eu(d), d[:4]]

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv
def man(o, s, lv): MAN[(key(o), s)] = lv
# 1999 USL D3 Pro League(미국 3부 프로): 세 디비전 26팀을 승·승부차기승 순으로 합친 순위 10위(애틀랜틱 디비전 3위/8팀, 11승 1승부차기승 6패;
# 위키백과 1999 USL D3 Pro League 순위표). 미국 3부 기준점(리그 수준 추정)
man("Carolina Dynamo", "1999", "미국 3부 1999 10위/26팀 (USL D3 Pro League 세 디비전 합친 승률 순위, 애틀랜틱 디비전 3위/8팀; 리그 수준 추정)")

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    for s in seasons_for(d):
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d, o); ELO_SRC["직접 라벨(순위표 밖)"] += 1
            ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
            p = _LRA["parse"](lv, d)
            if p and lv_value(lv, d, o) != e: TABLE_DIFF.append((o, s, e, lv, lv_value(lv, d, o)))
            return e, lv
    for lg in LEAGUES_EU + LEAGUES_CAL:
        ss = d[:4] if lg in LEAGUES_CAL else eu(d)
        t = RANKS.get((lg, ss), {})
        kk = k if k in t else next((x for x in t if _nn(t[x][2]) == _nn(RNAME.get(o, o))), None)
        if kk:
            lv = make_label(lg, ss, t[kk])
            e = lv_value(lv, d, o); ELO_SRC["순위표 → 라벨"] += 1
            ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, ss)] = (e, lv); return e, lv
    MISS.append((o, d, cid)); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
for typ, d, o, mi, dm, gf, ga, ko, pk, et, note, tie in EXTRA_E:
    elo, lv = opp_elo(o, d, "PO")
    row = [typ, o, elo, "lg", mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
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
        if len(r) > 14 or r[7] or r[10]: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14] if len(r) > 14 else "")
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
def same_team(a, b, d):
    if key(a) == key(b): return True
    return bool(toks(a)) and toks(a) == toks(b)
CROSS = []
VRE = re.compile(r"Stern John|^S\. John$|스턴 존")
G_DATES = {m[0] for m in M}
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for x in oe:
        if x[0] == "a" and VRE.search(str(x[13] or "")) and x[9] in G_DATES:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(존 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1], r[9])]
            if hit: CROSS.append(("존 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 존 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
SHARED = collections.Counter()
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for m in M:
        if any(mm[0] == m[0] and key(mm[1]) == key(m[1]) for mm in om): SHARED[b] += 1

# ---------------------------------------------------------------- 클럽·시즌
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["clubId"])
    if TM_CLUB[g["clubId"]] in CAL: continue
    if season_of(ldate(g))[2:4] + "/" + season_of(ldate(g))[5:7] != g["season"]: sys.exit("시즌 불일치 " + g["gameId"] + " " + g["season"] + " " + ldate(g))
CLUB_KO = {"nostj": ("뉴올리언스 리버보트 갬블러스", "1997"), "colstj": ("콜럼버스 크루", "1998~1999"), "nfostj": ("노팅엄 포리스트", "1999~2002"),
           "bcstj": ("버밍엄 시티", "2002~2004"), "covstj": ("코번트리 시티", "2004~2005, 2005~2007"), "derstj": ("더비 카운티(임대)", "2005"),
           "sunstj": ("선덜랜드", "2007"), "soustj": ("사우샘프턴", "2007~2008"), "bristj": ("브리스틀 시티(임대)", "2008~2009"),
           "cpstj": ("크리스털 팰리스", "2009~2010"), "ipsstj": ("입스위치 타운(임대)", "2009~2010")}
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
    for a in A_STATUS: print(a)
    for c in CROSS: print(c)
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF); print("MAPNEED", sorted(set(MAPNEED))); print("SHARED", SHARED.most_common()); print("SO", SO_GAMES)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_sternjohn.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "elk", "cwc", "clg", "cl16", "mlp"]:
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
    if m and r[4] > 90 and not r[10] and not str(r[11]).startswith("90+"): problems.append(("90분 넘는 분 표기", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const STJ_E={J(E)};\nconst STJ_M={J(M)};\nconst STJ_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "cross_check": CROSS, "elo_sources": ELO_SRC, "shootout_games": SO_GAMES,
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
