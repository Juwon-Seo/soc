#!/usr/bin/env python3
"""다니 아우베스 (Dani Alves, Transfermarkt 15951): raw/ -> danialves.json + players/danialves/dal.js (판정 근거는 judgments.md)

  python3 players/danialves/build_danialves.py [--out <data 폴더>]   # 파일 쓰기(기본 players/danialves/dal.js; 스크래치 검증 때 --out <복사본>/src/data)
  python3 players/danialves/build_danialves.py --debug               # Elo 출처 로그
  python3 players/danialves/build_danialves.py --stat                # 요약·판정·동료 대조
  python3 players/danialves/build_danialves.py --ties                # 합산 행

라모스(players/ramos/build_ramos.py) build 스크립트를 바탕으로 함(같은 수집 형식). 순위 라벨이 있는 행의 Elo는
tools/league_rank_apply.py 의 parse()/value()(승점 모형 포함)로 라벨에서 계산(직접 숫자를 넣지 않음). 같은 경기가 다른 선수 자료에 있으면
그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값(스크래치 복사본에서는 SOC_ROOT=<복사본>).
바이아의 바이아주 선수권·코파 두 노르데스치·코파 두스 캄페앙스 경기는 TM·경기 단위 출처 없음 → 넣지 않음(NOTE).
보조: assist_checks.py(도움 판정 근거), man_elo.py(순위표 밖 상대 라벨), note_danialves.py(설명).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "dal.js")
OUT_JSON = os.path.join(HERE, "danialves.json")
ME = "15951"
ME_KO = "다니 아우베스"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    r["sq_assist"] = "1" if r["danialves_assist"] == "1" else "0"
    r["sq_scorer"] = "1" if (r["danialves_scorer"] == "1" and r["ownGoal"] not in ("True", "1", "true")) else "0"
    FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["status"] == "OK"}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 날짜
# TM API 경기 시각(UTC)을 경기장 시간대로 바꾼 현지 날짜(date_local). 남미·북중미 저녁 경기는 UTC보다 하루 앞.
def ldate(g): return g["date_local"]
OPP_NAME = {"3397423": "Oeste FC"}   # TM 상대 id 21829 이름 'Osasco Sporting' — 바루에리 경기장·Goal 브라질 기사('São Paulo atropela o Oeste')·파투 자료 = 오이스치(Oeste FC)
def opp(g): return OPP_NAME.get(g["gameId"]) or re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용(정상 유형)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES1", "IT1", "FR1", "BRA1", "MEX1", "MEXA"}
CUPS = {"CDR", "FRC", "FRL", "CIT", "BRC"}
SUPER = {"SUC", "USC", "FRCH"}   # 수페르코파·UEFA 슈퍼컵·트로페 데 샹피옹 = 국내컵 결승 비중(다른 바르셀로나·세비야·PSG 선수 자료 같은 경기), 4팀 수페르코파 준결승은 국내컵 준결승

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "dsf" if r.startswith("semi") else "df"
    if cid in ("BCP1", "BCPF"): return "dc"   # 캄페오나투 파울리스타: 단계와 관계없이 국내컵 낮은 비중(마르셀루 카리오카·쿠티뉴 선례)
    if cid == "KLUB": return "cwc"
    if cid == "CLQ": return "clq"
    if cid == "UEFA":   # UEFA컵: 1라운드(조별 전 두 경기) = 유로파 예선 비중(카누테·라모스 선례), 조별, 32강(intermediate stage)·16강·8강 토너먼트
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid in CUPS:   # 16강까지 국내컵, 8강 이후 단계별(쿠프 드 프랑스 'Fifth/Sixth Round' = 64강·32강)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"
    if cid == "CS": return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g): return g["round"] or MI.get(g["gameId"], {}).get("round", "")

def ko_of(cid, rnd, d):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if cid == "BCP1": return 0   # 파울리스타 1단계(조별 리그)
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "CLQ", "UEFA"): return (1, 1) if d < "2021-08-01" else (0, 1)   # UEFA 2020-21까지 원정 다득점(연장 포함)
    if cid == "CDR": return (1, 1) if d < "2019-08-01" else (0, 1)   # 코파 델 레이 두 경기 라운드: 2018-19까지 원정 다득점·연장
    if cid == "SUC": return (1, 1)   # 두 경기 수페르코파: 원정 다득점·연장(메시·사비 자료와 같음)
    if cid == "CIT": return (1, 1)   # 코파 이탈리아 2016-17 준결승: 원정 다득점·연장(콰드라도·칼데론 자료와 같음)
    if cid == "BRC": return (1, 0) if d < "2018-01-01" else (0, 0)   # 코파 두 브라질: 2002 원정 다득점·연장 없음(디에구 자료), 2019년대 원정 다득점 없음(디에구 2019·2020 자료)
    if cid in ("CLI", "CS"): return (1, 0)   # 리베르타도레스·수다메리카나 2020-21: 원정 다득점, 연장 없이 승부차기(타베스·히바스 자료와 같음)
    if cid == "BCPF": return (0, 0)  # 파울리스타 결승 두 경기(마르셀루 카리오카 결승 선례)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["clubId"]: return "h"
    if m["away_id"] == g["clubId"]: return "a"
    sys.exit("편 판정 실패 " + gid)

EXTRA = {r["gameId"]: r for r in rd("tm_two_leg_ties_extra.csv")}
TIES2 = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
def other_leg(gid):
    """다른 차전 (우리, 상대) 골"""
    m = MI[gid]; club = G[gid]["clubId"]
    oid = m["other_leg_id"] or (TIES2[gid]["other_leg_id"] if gid in TIES2 else "")
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split("-"))
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    if gid in EXTRA:
        mm = re.match(r"^\d+ \S+ [HA] (\d+)-(\d+) \(club-opp\)", EXTRA[gid]["other_leg"])
        if mm: return (int(mm.group(1)), int(mm.group(2)))
    sys.exit("다른 차전 없음 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if gid == "4512219": return [1, 0, 0, 0, 1, 0]   # 코파 두 브라질 2002 1라운드 원정 1차전(원정 팀 2골 차 승리로 2차전 없음) = 두 경기 1차전
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
# 2001.8.4 팔메이라스전(데뷔): TM 교체 투입·투입 시각 0/빈칸, 출전 분 없음 → 경력 교체 출전 평균(연장 없는 경기)으로 추정(마르셀루·카카 선례)
_subs = [int(g["playedMinutes"]) for g in GAMES if g["isStarting"] == "0" and g["playedMinutes"] and g["addition"] == "none"]
SUB_EST = int(round(sum(_subs) / len(_subs))); N_SUBS = len(_subs)
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    if not g["playedMinutes"]:
        if g["gameId"] != "3687074": sys.exit("출전 분 없음 " + g["gameId"])
        M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), SUB_EST, 1]); continue
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

A_CHECK = {}; ADD_A = []
def a_key(gid, minute): return f"{gid}|{minute}"
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["sq_assist"] == "1" and f["pen_shootout_event"] != "True" and fm_min_match(f, e["minute"]): return True
    return False
def fm_pm_assists(gid):
    m = FMMAP.get(gid)
    if m and m["fotmob_matchId"] in FMPM: return int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
    return None

def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

A_STATUS = []
def fm_confirmed(gid):
    return sum(1 for e in EVS.get(gid, []) if e["assist_id"] == ME and e["scorer_id"] != ME and fm_assist(gid, e))
def assist_reason(e, d, gid):
    t = e["assist_type"]
    k = a_key(gid, e["minute"])
    if e["side"][0] != side_of(gid)[0] and not is_og(e): return "상대 골의 관련 선수(핸드볼 PK 허용)"
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t.startswith("Handball"): return "PK 유도(핸드볼)"
    if t == "Shot on goal": return A_CHECK[k][1] if k in A_CHECK else "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    if d < GAP:
        if k in A_CHECK and not A_CHECK[k][0]: return A_CHECK[k][1]
        return None
    if k in A_CHECK and not A_CHECK[k][0]:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "뺌: " + A_CHECK[k][1])); return A_CHECK[k][1]
    fa, pm = fm_assist(gid, e), fm_pm_assists(gid)
    if fa:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if pm and pm > fm_confirmed(gid) and k not in A_CHECK:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], f"TM+FotMob 선수 경기 목록(도움 {pm})")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "2014.8 이후 단일 출처(확인 못 함)"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], f"판정 없음 FMpm={pm}"))
    return "2014.8 이후 단일 출처(판정 없음)"

MIN_FIX = {}
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
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("골 아님(아우베스 자책골)", ldate(g), opp(g), e["minute"])); continue
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(MIN_FIX.get((gid, e["minute"]), e["minute"]))
        if is_a:
            why = assist_reason(e, ldate(g), gid)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, " ".join(e["scorer"].split()), e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

for gid, mi, gf, ga, pk, scorer, why in ADD_A:
    raw_rows.append(("a", gid, mi, 0, gf, ga, 0, scorer, "added"))
    judg.append(("도움 추가(FotMob 단독 + 다른 출처 2곳)", ldate(G[gid]), opp(G[gid]), str(mi), scorer, why))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["sq_assist"] == "1" and f["pen_shootout_event"] != "True":
            mi = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(e["assist_id"] == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, mi, f["scorer"]))
PM_ONLY = []
for gid, m in FMMAP.items():
    if gid in G and m["fotmob_matchId"] in FMPM:
        pm = int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
        tm = sum(1 for e in EVS.get(gid, []) if e["assist_id"] == ME and e["scorer_id"] != ME and e["side"][0] == side_of(gid))
        if pm > tm: PM_ONLY.append((ldate(G[gid]), gid, opp(G[gid]), pm, tm))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split("-")) if MI[gid]["final"] else (h, a)
    if (h, a) != (fh, fa) and G[gid]["gameState"] != "penalty_shootout": SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))

# ---------------------------------------------------------------- 이름·기존 자료
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
        if r["선수"] == ME_KO: continue   # 내 자료만 쓴 팀×시즌은 건너뜀(다른 선수와 같이 쓴 행은 그대로, 오스카 선례)
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())   # 다른 심판의 새 파일(추적 안 됨)은 비교에서 뺌
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "clubcolors.js", "finals.js", "dal.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
PEERS = ("ramos/srm.js", "marcelo/mcl.js", "robertocarlos/rcs.js", "jordialba/jba.js")   # 같은 라운드 다른 심판 자료: 대조만(값을 가져오지 않음)
PEER_D = {}
for b in PEERS:
    fn = os.path.join(os.path.dirname(HERE), b)
    if os.path.exists(fn) and "--no-peers" not in sys.argv:
        P, oe, om = load_js(fn); PEER_D["peer:" + b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "ca", "cs", "deportivo", "deportes", "universidad", "san", "santa", "fk", "vfl", "bv",
        "racing", "arsenal", "juniors", "plate", "river", "nacional", "union", "hotspur", "manchester", "borussia", "bayer", "stade", "royal", "kv", "al", "cruz", "azul", "la", "coruna",
        "new", "york", "red", "bull", "bulls", "whitecaps", "vancouver", "toluca", "barcelona", "espanyol", "munich", "munchen", "bayern", "rayo", "celta", "vigo", "las", "palmas"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d, cid):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)] or [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위 라벨 → Elo (tools/league_rank_apply.py)
_LRA = {"__file__": os.path.join(ROOT, "tools", "league_rank_apply.py"), "__name__": "lra"}
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA["__file__"], encoding="utf-8").read().split("if __name__ == '__main__':")[0], "lra", "exec"), _LRA)
sys.argv = _argv
sys.path.insert(0, os.path.join(ROOT, "tools")); import league_points as PTS
def lv_value(lv, d, o=None):
    m_ = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv)
    if m_:
        cal = m_.group(4) is None; y = int(m_.group(3)) + (0 if cal else 1)
        return int(round(_LRA["base"](_LRA["KO"][m_.group(1)], int(m_.group(2)), y, cal)))
    p = _LRA["parse"](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA["value"](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    if o is not None:
        b_, sd_ = _LRA["base"](p[0], p[1], p[2], p[3]), _LRA["sd"](p[0], p[1])
        if p[1] == 1 and p[0] in _LRA["BIG"]:
            vp = PTS.value(lv, o, b_, sd_, _LRA["cv"])
        else:
            vp = PTS.value_other(lv, o, p[0], p[1], b_, sd_, _LRA["cv"])
        if vp is not None: v = vp
    return v
MAP_NEED = {}
def map_check(lv, o):
    head = lv.split(" (")[0]; mm = re.match(r"^(.*?) (\d+)위", head)
    if not mm: return
    E_ = PTS.O["seasons"].get(mm.group(1))
    if not E_ or "skip" in E_ or E_.get("ongoing") or "tables" not in E_: return
    if PTS.other_score(lv, o) is not None: return
    rk = int(mm.group(2)); R = E_["tables"][0]["rows"]
    MAP_NEED[(mm.group(1), o)] = (R[rk - 1][0] if rk <= len(R) else "?", rk - 1)

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[0].startswith("#"): continue
        RANKS[(p[0], p[1].split(" ")[0])][key(re.sub(r"\s*\(\s*-\s*\d{4}\)", "", p[4]))] = (int(p[2]), int(p[3]), p[4], p[1])

EU_LG = {"ES1": "라리가", "FR1": "리그1", "IT1": "세리에A"}
def make_label(lg, season, v):
    r, n, nm, sraw = v
    if lg == "ES2": return f"세군다 {season} {r}위/{n}팀"
    if lg == "RO1": return f"루마니아 1부 {season} {r}위/{n}팀 (Liga I)"
    if lg == "BRA1": return f"브라질 세리에 A {season} {r}위/{n}팀"
    if lg in EU_LG:
        pre = EU_LG[lg]; n0 = _LRA["ERA"]["teams"](pre, int(season[:4]) + 1)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    return None

# 상대 시즌: 유럽은 8월 1일 기준. 브라질·남미 대회는 달력 연도, 단 브라질 세리에 A 2020(2020.8~2021.2)의 2021년 경기는 2020 시즌 순위.
# 리가MX는 7~6월(아페르투라 2022 + 클라우수라 2023 = 2022-23, 기존 '누적' 라벨).
SA = {"BRA1", "BRC", "BCP1", "BCPF", "CLI", "CS"}
def season_of(d, club_id):
    y, m = int(d[:4]), int(d[5:7])
    s_ = y if m >= 8 else y - 1
    if club_id == "7633" and m == 7: s_ = y
    return f"{s_}-{str(s_ + 1)[2:]}"
def seasons_for(cid, d, o, g):
    if cid in SA:
        if cid == "BRA1" and d < "2021-03-01" and d >= "2021-01-01": return ["2020"]
        return [d[:4]]
    return [season_of(d, g["clubId"])]
def lg_cands(cid, d, o, g):
    s = seasons_for(cid, d, o, g)[0]
    if cid in ("ES1", "CDR", "SUC"): doms = ["ES1", "ES2"]
    elif cid in ("FR1", "FRC", "FRL", "FRCH"): doms = ["FR1"]
    elif cid in ("IT1", "CIT"): doms = ["IT1"]
    elif cid in SA: doms = ["BRA1"]
    else: doms = ["ES1", "FR1", "IT1", "RO1"]
    return [(lg, s) for lg in doms]

MAN = {}
def man(o, s, lv): MAN[(key(o), s)] = lv
FORCE = {}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []

def opp_elo(o, d, cid, g):
    if g["gameId"] in FORCE:
        lv = FORCE[g["gameId"]]; e = lv_value(lv, d, o); map_check(lv, o); ELO_SRC["직접 라벨"] += 1
        ELO_LOG[(o, d)] = ("force", e, lv); return e, lv
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    seasons = seasons_for(cid, d, o, g)
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
            p = _LRA["parse"](lv, d)
            if p and lv_value(lv, d, o) != e: TABLE_DIFF.append((o, s, e, lv, lv_value(lv, d, o)))
            map_check(lv, o)
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d, o); map_check(lv, o); ELO_SRC["직접 라벨(순위표 밖)"] += 1
            ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    for lg, s in lg_cands(cid, d, o, g):
        t = RANKS.get((lg, s), {})
        if k in t:
            lv = make_label(lg, s, t[k])
            if lv:
                e = lv_value(lv, d, o); map_check(lv, o); ELO_SRC["순위표 → 라벨"] += 1
                ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, seasons[0])] = (e, lv); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd, d)
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
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]): print(d, o, v)
    print("TABLE_DIFF", TABLE_DIFF)
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["sq_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "penalty" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))
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
G_BYDATE = {ldate(g): g["competitionId"] for g in GAMES}
CROSS = []
JRE = re.compile(r"Dani Alves|Daniel Alves|아우베스", re.I)
ALL_OTHERS = dict(OTHERS); ALL_OTHERS.update(PEER_D)
for b, (oe, om) in ALL_OTHERS.items():
    for x in oe:
        if x[0] == "a" and JRE.search(str(x[13] or "")) and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(아우베스 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("아우베스 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
for b, (oe, om) in ALL_OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 아우베스 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
# 클럽 구분: Transfermarkt 이적일(세비야 2003.1.1 완전 이적 — 2002.7 임대지만 바이아 경기 2002.11까지, 바르셀로나 2008.7.2, 유벤투스 2016.7.1, PSG 2017.7.12, 상파울루 2019.8.1, 바르셀로나 2021.11.12, 푸마스 2022.7.23)
STINTS = [("바이아", "2003-01-01"), ("세비야", "2008-07-02"), ("바르셀로나", "2016-07-01"), ("유벤투스", "2017-07-12"), ("PSG", "2019-08-01"),
          ("상파울루", "2021-11-12"), ("바르셀로나", "2022-07-23"), ("UNAM 푸마스", "9999")]
TM_CLUB = {"10010": "바이아", "368": "세비야", "131": "바르셀로나", "506": "유벤투스", "583": "PSG", "585": "상파울루", "7633": "UNAM 푸마스"}
def stint(d):
    for n, u in STINTS:
        if d < u: return n
for g in GAMES:
    if stint(ldate(g)) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ORDER = ["바이아", "세비야", "바르셀로나", "유벤투스", "PSG", "상파울루", "UNAM 푸마스"]
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for n in ORDER)
for m in M: ST[stint(m[0])][0] += 1; ST[stint(m[0])][3] += m[3]
for r in E: ST[stint(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
def d_(x): y, m, d = x.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EXJ = [j for j in judg if j[0] == "도움 제외"]
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME and e["side"][0] == side_of(gid))
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A)
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    print("FM only", FM_ONLY); print("PM only", PM_ONLY)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G, FM_CMP)
    print("SCORE_MISMATCH", SCORE_MISMATCH)
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF)
    for k, v in sorted(MAP_NEED.items()): print("MAP_NEED", k, v)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_danialves.py"), encoding="utf-8").read())
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl", "mlp", "lcg", "lck", "ccc"]:
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
        if b[5] < a[5] + 1 and b[4] > a[4] and (b[5], b[6]) <= (a[5], a[6]): problems.append(("스코어 역순", d, a[4], b[4]))
for r in E:
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if not r[2] or r[12] == "?": problems.append(("Elo 없음", r))
mm_ = {m[0]: m for m in M}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const DAL_E={J(E)};\nconst DAL_M={J(M)};\nconst DAL_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "fotmob_playermatches_only": PM_ONLY, "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "table_label_diffs": TABLE_DIFF, "points_map_needed": [f"{k[0]} | {k[1]} | {v[0]} | {v[1]}" for k, v in sorted(MAP_NEED.items())],
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
