#!/usr/bin/env python3
"""조르디 알바 (Jordi Alba, Transfermarkt 69751, FotMob 150739): raw/ -> jordialba.json + players/jordialba/jba.js (판정 근거는 judgments.md)

  python3 players/jordialba/build_jordialba.py [--out <data 폴더>]   # 스크래치 검증: SOC_ROOT=<복사본> … --out <복사본>/src/data
  python3 players/jordialba/build_jordialba.py --debug | --stat | --ties

뎀프시(같은 수집기 raw 형식)·사비(바르셀로나) build 스크립트를 알바에 맞춰 고친 것. 순위 라벨 행의 Elo는
tools/league_rank_apply.py parse()/value()(+ tools/league_points.py 승점 모형)로 라벨에서 계산. 같은 경기가 다른 선수
자료에 있으면 그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
코르네야(2006-07 카탈루냐 1부 = 6부 아마추어)·발렌시아 B(2007-08 테르세라 = 4부)는 TM performance-game에 없고 아마추어라 제외.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "jba.js")
OUT_JSON = os.path.join(HERE, "jordialba.json")
ME = "69751"
ME_KO = "조르디 알바"
GAP = "2014-08-01"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["team_level"] == "senior"]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
TIES = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 날짜·출전 분
# 2023 US 오픈컵 준결승 신시내티 원정: TM 시각 22:00 UTC는 자리채움(실제 2023.8.23 수 19:30 현지; 메시 자료·MLS 발표와 같음)
DATE_FIX = {"4085386": "2023-08-23"}
# 2023 리그스컵 결승 내슈빌전: 1-1 뒤 연장 없이 바로 승부차기(리그스컵 규정) → 90분(TM 120, FotMob 90, 메시 자료 90)
# 2025 리그스컵 8강 티그레스전: FotMob 47분 교체 아웃, TM 경기 JSON 교체 기록도 47분 노아 앨런 ↔ 알바(같은 JSON의 90+2분 아빌레스 ↔ 알바는 중복 표기) → 47분
MIN_FIX = {"4160855": 90, "4699933": 47}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local"])
def opp(g):
    o = re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
    o = re.sub(r"\s*\(\s*\d{4}\s*-\s*\d{4}\)", "", o).strip()
    return RNAME.get(o, o)
RNAME = {"Red Bull New York": "New York Red Bulls"}   # 메시 자료·위키백과 순위표 이름
def rnd_of(g): return g["round"] or ""

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES1", "ES2", "MLS1"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("CDR", "MLSP"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "SUC": return "dsf" if r.startswith("semi") else "df"   # 수페르코파 = 국내컵 결승 비중(4팀 준결승 dsf)
    if cid == "KLUB": return "cwc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                        # 32강('intermediate stage', 'Second Round')·16강·8강 = 토너먼트
    if cid == "USMX": return "lcg" if r.startswith("group") else "lck"
    if cid == "POUS":
        if r.startswith("final"): return "mlpf"
        if r.startswith("semi"): return "mlpsf"             # 컨퍼런스 결승
        return "mlp"                                        # 1라운드(3판 2선승)·컨퍼런스 준결승
    if cid == "CCL":
        if r.startswith("semi"): return "cccsf"
        if r.startswith("final"): return "cccf"
        if r.startswith("quarter"): return "ccck"
        return "ccc"                                        # 1라운드·16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid == "POUS": return 1                              # MLS 플레이오프 1라운드 3판 2선승: 경기마다 단판(메시 자료와 같음)
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0                      # 챔스·유로파 조별, 클럽 월드컵 2025 조별(리그식), 리그스컵 조별(승점제, 수아레스 자료와 같음)
    return 1

def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "EL"): return (int(d < "2021-07-01"), 1)   # UEFA: 2020-21까지 원정 다득점(연장 포함)
    if cid == "CDR": return (int(d < "2019-07-01"), 1)          # 코파 델 레이: 2018-19까지 원정 다득점, 이후 두 경기 준결승은 연장만
    if cid == "SUC": return (1, 1)                              # 두 경기 수페르코파(2017년까지): 원정 다득점·연장
    if cid == "CCL": return (1, int(d < "2025-01-01"))          # 북중미 챔스: 원정 다득점, 2024 자료는 연장 1·2025 자료는 0(메시·수아레스 자료와 같게)
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

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("gimjba", "2009-07-01"), ("valjba", "2012-07-01"), ("barjba", "2023-07-01"), ("miajba", None)]
TM_CLUB = {"5648": "gimjba", "1049": "valjba", "131": "barjba", "69261": "miajba"}
CAL = {"miajba"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
def eu(d):
    y = int(d[:4]); m = int(d[5:7]); s_ = y if m >= 8 else y - 1
    if y == 2020 and m == 8: s_ = 2019
    return f"{s_}-{str(s_ + 1)[2:]}"
def season_of(d):
    return d[:4] if club_of(d) in CAL else eu(d)

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
import functools
@functools.lru_cache(maxsize=None)
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
        if f["alba_assist"] == "1" and f["pen_shootout_event"] != "True" and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])): return True
    return False

A_CHECK = {     # 다른 출처로 판정한 Transfermarkt 도움(judgments.md 4절)
 # 2014.8 이전(TM 단독 허용이지만 다른 출처와 어긋나는 것)
 "957614|85": (False, "2010.4.11 마요르카 원정 85분 파블로 에르난데스 골: TM은 알바 크로스로 적었으나 ESPN 문자중계 'Assisted by David Albelda with a through ball'·Soccer Punter도 알벨다, Periódico de Ibiza는 '수비 실수를 틈탄 골' → 뺌"),
 # 2014.8 이후 TM 단독 도움
 "2518529|39": (False, "2015.1.8 코파 델 레이 16강 1차전 엘체전 40분 수아레스 골: ESPN 문자중계만 'Assisted by Jordi Alba'(FotMob 도움 칸 비어 있음), 다른 경기 기사(Sports Mole·FCB 구단 기사·Bleacher Report)는 도움을 적지 않음 — 다른 출처 2곳이 안 돼 뺌"),
 "2528140|41": (True, "2015.1.28 코파 델 레이 8강 2차전 아틀레티코 원정 41분 네이마르 골: FC 바르셀로나 구단 기사·Sportskeeda·Irish Times 모두 '알바가 (그리즈만 슈팅을 막은 뒤) 네이마르에게 연결' → 넣음"),
 "3451091|43": (False, "2020.12.16 레알 소시에다드전 43분 프렝키 더용 골: AP 기사 'Alba's low cross was deflected off a defender'(굴절), FotMob 도움 없음 → 뺌"),
 "3989534|77": (True, "2023.1.4 코파 델 레이 32강 인테르시티 원정 77분 하피냐 골: LaLiga.com 경기 기록이 알바 도움, football-espana 기사 'Alba supplied the pass' → 넣음(TM 유형 빈칸, FotMob 도움 칸 비어 있음)"),
}
# 2014.8 이전 FotMob 단독 도움(다른 출처 확인): 2010.11.24 챔스 조별 부르사스포르전 37분 호아킨 골(4-0)
ADD_A = [("1050146", 37, 0, 3, 0, "Joaquín",
          "FotMob 'assist by Jordi Alba' + ESPN 문자중계 'Assisted by Jordi Alba' + Sky Sports 경기 기사 '알바가 페널티 지역 가장자리의 호아킨을 찾아 줌'(UEFA 기사는 호아킨이 왼쪽에서 파고들어 감아 찬 골로만 적음); TM 도움 칸 비어 있음 → 넣음")]
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
    if d < GAP:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "2014.8 이전 TM 단독(유형 " + (t or "빈칸") + ") 선례대로 넣음")); return None
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음"))
    return "2014.8 이후 단일 출처(판정 없음)"
SHOT_WHY = {"2675295|63": "2016.4.5 챔스 8강 1차전 아틀레티코전 63분 수아레스 골: TM 유형 'Shot on goal' — Eurosport·LaLiga 문자중계 모두 다니 아우베스 크로스를 알바가 발리로 찬 것을 수아레스가 문전에서 방향만 바꿈(슈팅 리바운드·굴절형, FotMob은 도움으로 셈) → 뺌"}

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
                why = SHOT_WHY.get(f"{gid}|{e['minute']}", why)
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if (e["penalty"] == "1" or e["api_actionId"] == "204") and e["api_actionId"] != "205" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))
for gid, mi, dm, gf, ga, scorer, why in ADD_A:
    raw_rows.append(("a", gid, mi, dm, gf, ga, 0, scorer))
    judg.append(("도움 추가(FotMob 단독, 2014.8 이전)", ldate(G[gid]), opp(G[gid]), mi, scorer, why))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["alba_assist"] == "1" and f["pen_shootout_event"] != "True":
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
@functools.lru_cache(maxsize=None)
def key(n):
    k = norm(n)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue   # 이 선수만 쓴 팀-시즌만 건너뜀
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
TRACKED = set(subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "clubcolors.js", "finals.js", "jba.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
PAR = {}   # 이번 회차 병렬 판정(읽기만)
for slug in ("danialves", "ramos", "marcelo", "robertocarlos"):
    for pth in glob.glob(os.path.join(os.path.dirname(HERE), slug, "*.js")):
        try: P, oe, om = load_js(pth)
        except Exception: continue
        PAR["players/" + slug + "/" + os.path.basename(pth)] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss", "us", "vfl", "vfb", "tsg", "sd", "ca",
        "real", "borussia", "bayer", "eintracht", "olympique", "atletico", "athletic", "fk", "sk", "bv", "united", "city", "deportivo", "balompie"}
@functools.lru_cache(maxsize=None)
def toks(n): return frozenset({t for t in norm(n).split() if t not in STOP and len(t) > 2})
@functools.lru_cache(maxsize=None)
def same_team(a, b):
    if key(a) == key(b): return True
    return bool(toks(a)) and bool(toks(b)) and (toks(a) <= toks(b) or toks(b) <= toks(a))
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
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

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
def make_label(lg, season, v):
    r, n, nm = v
    if lg == "ES2": return f"세군다 {season} {r}위/{n}팀"
    return None

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv
def man(o, s, lv): MAN[(key(o), s)] = lv
# 리가MX 2025-26 연간 합산 순위(아페르투라 2025 + 클라우수라 2026 정규 단계 합산; 수아레스 자료 UNAM·티그레스 2025-26 라벨과 같은 방식) — 네카사 13위/18팀
# (elo/league_points_other.json '리가MX 2025-26' 합산 표 13번째 행, 영어 위키백과 Apertura 2025·Clausura 2026 Liga MX 순위표)
man("Club Necaxa", "2025-26", "리가MX 2025-26 13위/18팀 (Liga MX, 연간 합산 순위)")
# MLS 2025 뉴욕 레드불스: 전체 순위 18위/30팀(영어 위키백과 2025 MLS 순위표, elo/league_points_other.json 'MLS 2025' 18번째 행)
man("New York Red Bulls", "2025", "MLS 2025 18위/30팀")

def seasons_for(cid, d):
    if cid == "MLS1": return [d[:4]]
    if cid in ("ES1", "ES2"): return [eu(d)]
    return [eu(d), d[:4]]
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def opp_elo(o, d, cid, g):
    cand, vals = same_match(o, d)
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
    s = eu(d)
    for lg in ("ES2",):
        t = RANKS.get((lg, s), {})
        if k in t:
            lv = make_label(lg, s, t[k])
            e = lv_value(lv, d, o); ELO_SRC["순위표 → 라벨"] += 1
            ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
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
if "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        print(d, o, v)
    print("TABLE_DIFF", TABLE_DIFF)
    print("MAPNEED", sorted(set(MAPNEED)))
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14 or r[7] or r[10]: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14] if len(r) > 14 else "")
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["alba_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "1", "true")]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 0): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], f["time"], f["overloadTime"]))

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
VRE = re.compile(r"Jordi Alba|^Alba$|^J\. Alba$|조르디 알바")
G_DATES = {m[0] for m in M}
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for x in oe:
        if x[0] == "a" and VRE.search(str(x[13] or "")) and x[9] in G_DATES:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(알바 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    OED = collections.defaultdict(list)
    for x in oe: OED[x[9]].append(x)
    for r in E:
        if r[0] == "a":
            hit = [x for x in OED.get(r[9], []) if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("알바 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in OED.get(r[9], []):
            if same_team(x[1], r[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], x[1], dd))
                break
    OMD = collections.defaultdict(list)
    for mm in om: OMD[mm[0]].append(mm)
    for m in M:
        for mm in OMD.get(m[0], []):
            if same_team(mm[1], m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[2], m[2]))
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 알바 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5][:60]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
SHARED = collections.Counter()
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    OMD = collections.defaultdict(list)
    for mm in om: OMD[mm[0]].append(mm)
    for m in M:
        if any(same_team(mm[1], m[1]) for mm in OMD.get(m[0], [])): SHARED[b] += 1
# 같은 상대·하루 차이 날짜(날짜 표기 차이 점검)
DATE_DIFF = []
import datetime as _dt
for b, (oe, om) in OTHERS.items():
    for m in M:
        if club_of(m[0]) not in ("barjba", "miajba"): continue
        for mm in om:
            if mm[0] != m[0] and abs(int(mm[0][:4]) - int(m[0][:4])) <= 1 and mm[0][:7] in (m[0][:7],) and same_team(mm[1], m[1]) and abs((_dt.date.fromisoformat(mm[0]) - _dt.date.fromisoformat(m[0])).days) == 1 and mm[2] == m[2]:
                DATE_DIFF.append((b, m[0], mm[0], m[1]))

# ---------------------------------------------------------------- 클럽·시즌 점검
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["clubId"])
    if TM_CLUB[g["clubId"]] in CAL: continue
    if season_of(ldate(g))[2:4] + "/" + season_of(ldate(g))[5:7] != g["season"]: sys.exit("시즌 불일치 " + g["gameId"] + " " + g["season"] + " " + ldate(g))
CLUB_KO = {"gimjba": ("힘나스티크", "2008~2009 임대"), "valjba": ("발렌시아", "2009~2012"), "barjba": ("바르셀로나", "2012~2023"), "miajba": ("인터 마이애미", "2023~2025")}
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
    print("FM only", FM_ONLY)
    for c in CROSS: print(c)
    print("FM_CMP", FM_CMP)
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF)
    print("MAPNEED", sorted(set(MAPNEED)))
    print("DATE_DIFF", DATE_DIFF)
    print("SHARED", SHARED.most_common())
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_jordialba.py"), encoding="utf-8").read())
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "elk", "elq", "cwc", "mlp", "lcg", "lck", "ccc", "clg"]:
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
    gl = sorted([r for r in rs if r[0] == "g"], key=lambda r: r[4])
    for a, b in zip(gl, gl[1:]):
        if (b[5], b[6]) < (a[5] + 1, a[6]) and b[4] > a[4] and b[5] <= a[5]: problems.append(("스코어 역순", d, a[4], b[4]))
for r in E:
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if not r[2] or r[12] == "?": problems.append(("Elo 없음", r))
mm_ = {m[0]: m for m in M}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > m[3] + 0 and not r[10] and r[4] > 90 and m[3] < 90: problems.append(("출전 분보다 늦은 기록", r[9], r[4], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const JBA_E={J(E)};\nconst JBA_M={J(M)};\nconst JBA_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "table_label_diffs": TABLE_DIFF, "points_map_needed": sorted(set(MAPNEED)),
               "shared_games": dict(SHARED), "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for v in ST: print(" ", v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
