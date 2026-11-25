#!/usr/bin/env python3
"""라울 히메네스 (Raúl Jiménez, Transfermarkt 206040, FotMob 292313): raw/ -> jimenez.json + players/jimenez/rjm.js (판정 근거는 judgments.md)

  python3 players/jimenez/build_jimenez.py [--out <data 폴더>]   # 기본 players/jimenez/rjm.js; 스크래치 복사본 검증 때 SOC_ROOT=<복사본> … --out <복사본>/src/data
  python3 players/jimenez/build_jimenez.py --debug               # Elo 출처 로그
  python3 players/jimenez/build_jimenez.py --stat                # 요약·판정·동료 대조

바렐라 build 스크립트(같은 수집기 계열)를 히메네스 raw 열 이름과 리가MX(단계·리길야·코파 MX·북중미 챔스)에 맞춰 고친 것.
순위 라벨 행의 Elo는 tools/league_rank_apply.py parse()/value()(+ tools/league_points.py 승점 모형)로 라벨에서 계산.
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "rjm.js")
OUT_JSON = os.path.join(HERE, "jimenez.json")
ME = "206040"
ME_KO = "라울 히메네스"
CUTOFF = "2026-11-25"
GAP = "2014-08-01"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["team_level"] == "senior"]   # 클럽 아메리카 U-20(유소년) 53경기 제외
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 날짜·출전 분
# 2012.10.25 푸에블라 원정(TM 2239794): TM UTC 10.25 02:00(현지 10.24)이지만 ESPN(2012-10-26T02:00Z)·FotMob 모두 하루 뒤 = 현지 10.25(목) 21시.
# 2016.1.26 타사 다 리가 모레이렌스 원정(TM 2636396): TM 1.25 20:30 UTC, FotMob·CM 문자중계·사커웨이 1.26(화) 20:30 → 1.26
DATE_FIX = {"2239794": "2012-10-25", "2636396": "2016-01-26"}
# 2015.11.21 타사 드 포르투갈 4라운드 스포르팅 원정(연장 2-1 패): TM 교체 기록 '90+5'는 연장 95분(TM은 연장 분을 90+X로 적음,
#   같은 경기 슬리마니 결승골 90+22 = 112분), RTP 문자중계·Portugoal도 95분 교체 → 120−95 = 25분(TM 선수 합계 1분은 연장 미반영)
MIN_FIX = {"2634993": 25}
# 골 시각: 2020.9.14 셰필드 유나이티드전 TM '3+1' → 3분(FotMob 3분, 전반 3분 골)
EV_MIN_FIX = {("3420827", "3+1"): "3"}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local"])
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
def rnd_of(g): return g["round"] or ""

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"MEXA", "MEX1", "ES1", "PO1", "GB1", "GB2"}
CUP = {"CDR", "POPO", "FAC", "CGB", "MXCA", "MXCC"}   # 코파 MX(아페르투라 MXCA·클라우수라 MXCC) = 국내컵
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round"): return "dk"   # FA컵 6라운드·리그컵 8강·코파 MX 8강
        return "dc"   # 조별(코파 MX)·1~5라운드·16강(FA컵 'Round of 16' = 5라운드)·재경기('4th round deciders')·타사 16강
    if cid == "POCP":   # 타사 다 리가: 조별은 리그식 국내컵(브루노·교케레스 선례), 준결승·결승
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("group"): return "dc"
    if cid in ("POSU", "SUC"): return "df"   # 수페르타사·수페르코파 = 국내컵 결승 비중(다른 선수 자료 2014 수페르코파와 같음)
    if cid in ("POME", "POMX"):              # 리길야 = MLS 플레이오프 비중(치차리토 선례)
        if r.startswith("semi"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
        return "mlp"
    if cid == "CCL": return "ccc"            # 북중미 챔피언스리그 2013-14 조별
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 32강(intermediate stage)·16강·8강(2020.8 단판)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0   # 코파 MX·타사 다 리가·챔스·유로파·북중미 챔스 조별
    return 1

def tie_rule(cid, d, rnd):
    if cid in ("CL", "EL", "ELQ"): return (int(d < "2021-07-01"), 1)
    if cid in ("POME", "POMX"):
        if rnd.lower().startswith("final"): return (0, 1)   # 리길야 결승: 원정 다득점 없이 연장·승부차기(지냑 선례)
        return (0, 0)                                       # 8강·4강: 합계 동률이면 정규리그 상위 팀(치차리토·지냑 선례)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["clubId"]: return "h"
    if m["away_id"] == g["clubId"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    g = G[gid]; club = g["clubId"]; rnd = rnd_of(g).lower()
    base = re.sub(r"\s*(1st|2nd) leg", "", rnd)
    cand = [x for x in GAMES if x["gameId"] != gid and x["competitionId"] == g["competitionId"] and x["opponentId"] == g["opponentId"]
            and re.sub(r"\s*(1st|2nd) leg", "", rnd_of(x).lower()) == base and "1st" in rnd_of(x).lower()]
    if len(cand) == 1:
        a, b = map(int, cand[0]["score_club_opp"].split("-")); return (a, b)
    m = MI[gid]; oid = m["other_leg_id"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split("-"))
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
    sys.exit("다른 차전 없음 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

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
def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"
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
        if f["jimenez_assist"] == "1" and f["pen_shootout_event"] != "True" and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])): return True
    return False

# 2014.8 이후 Transfermarkt에만 있는 일반 유형 도움: 다른 출처 2곳으로 판정(judgments.md 4절)
A_CHECK = {
 "2480574|73": (True, "2014.8.2 푸에블라전 73분 오리베 페랄타 골: ESPN 문자중계 'Assisted by Raúl Jiménez'·Quadratín 경기 기사 'Pase de Jiménez filtrado para Oribe Peralta'"),
 "2480584|62": (True, "2014.8.9 티그레스전 62분 라윤 골: ESPN 문자중계 'Assisted by Raúl Jiménez following a fast break'·Quadratín('Raúl Jiménez habilitó con un servicio a la espalda de la defensiva')·Récord('pase medido de Raúl Jiménez')"),
 "2609455|34": (False, "2016.1.6 마리티무전 34분 피치 골: ESPN 도움 없음, FotMob 도움 없음. Observador 문자중계 — 히메네스 크로스가 '다시 한 번 굴절(um desvio)'된 뒤 피치에게 감(굴절이라 도움 아님)"),
 "2609469|57": (True, "2016.1.11 나시오날전 57분 조나스 골: Observador 문자중계('Eliseu 스로인 → 히메네스가 원터치 크로스 → 조나스 발리')·CM 문자중계('Sai Raúl Jiménez, que fez a assistência para o segundo golo de Jonas')"),
 "2720822|87": (False, "2016.10.28 파수스 드 페헤이라전 87분 피치 골: ESPN 문자중계는 도움 없음, FotMob 도움 없음, CM 경기 평점 기사에 히메네스 패스 언급 없음, LiveSoccerTV(통계 집계)만 도움 — 확인 못 함"),
 "2720939|80": (False, "2017.2.19 브라가 원정 80분 미트로글루 골: ESPN 문자중계만 'Assisted by Raúl Jiménez', RTP 문자중계는 미트로글루가 수비 여럿을 제친 개인 돌파 골로 적음 — 다른 출처 2곳 확인 못 함"),
 "2883642|89": (True, "2017.8.19 벨레넨세스전 89분 조나스 골(4-0): ESPN 문자중계 'Assisted by Raúl Jiménez'(90분 표기)·Gazeta Esportiva 경기 기사('Jiménez tocou para Jonas, que dominou de peito e arrematou')"),
 "2884441|90+4": (True, "2018.2.24 파수스 드 페헤이라 원정 90+4분 하파 골: ESPN 문자중계 'Assisted by Raúl Jiménez with a headed pass'·Bola na Rede 경기 기사(히메네스 패스를 받은 하파가 마무리)"),
 "2884469|76": (True, "2018.3.17 페이렌스 원정 76분 하파 골: ESPN 문자중계 'Assisted by Raúl Jiménez with a through ball'·Observador 문자중계·Portugoal('Jiménez set Rafa through on goal')"),
 "2884482|78": (True, "2018.3.31 비토리아 기마랑이스전 78분 조나스 헤더 골: ESPN 문자중계 'Assisted by Raúl Jiménez'·CM('Jiménez … fez um cruzamento de letra … até à cabeça de Jonas para o 2-0')·Gazeta Esportiva"),
 "2884516|90+4": (True, "2018.4.28 톤델라전 90+4분 살비오 골: ESPN 문자중계 'Assisted by Raúl Jiménez'·Observador 경기 기사(루이장 롱볼 → 히메네스 터치 → 살비오)·Quadratín"),
 "3710357|80": (True, "2022.1.9 FA컵 셰필드 유나이티드전 80분 포덴세 골: ESPN 문자중계 'Assisted by Raúl Jiménez'·스카이 스포츠 경기 기사('beaten to the ball by Jimenez, who calmly rolled back to allow Podence to fire into an empty net')"),
}
A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도('Penalty: Fouled player')"
    if t == "Handball (opponent)": return "상대 핸드볼 PK"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    k = f"{gid}|{e['minute']}"
    if d < GAP:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "2014.8 이전 Transfermarkt 일반 유형(" + (t or "유형 없음") + ")" + (" + FotMob" if fm_assist(gid, e) else "")))
        return None
    if fm_assist(gid, e):
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else why
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음"))
    sys.exit("2014.8 이후 단일 출처 도움 판정 누락 " + k + " " + d)

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
        if e["scorer_id"] == ME and e["assist_id"] == ME: judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], "본인 PK 골의 본인 도움(PK 유도)"))
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(EV_MIN_FIX.get((gid, e["minute"]), e["minute"]))
        if is_a:
            why = assist_reason(e, ldate(g), gid)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if sd != side: sys.exit("도움 편 이상 " + gid)
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["penalty"] == "1" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["jimenez_assist"] == "1" and f["pen_shootout_event"] != "True":
            if not any(e["assist_id"] == ME and e["scorer_id"] != ME and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])) for e in EVS.get(gid, [])):
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "rjm.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
PAR = {}   # 이번 회차 병렬 판정(읽기만)
for slug in ("morata", "mitrovic", "ennesyri", "leekangin"):
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

# 리가MX 단계 표(TM)의 이름 차이: 데이터 상대 이름 → 순위표 이름
MX_NAME = {"Jaguares FC": ["Jaguares de Chiapas", "Chiapas FC (- 2017)"], "Club Atlético Morelia": ["Monarcas Morelia"], "Tecos FC": ["Estudiantes Tecos"]}
# 순위 고침(출처 대조, judgments.md 6절)
RANK_FIX = {("MEX1", "2011-12", "unam pumas"): 13}   # 클라우수라 2012: TM·FotMob 13위(승점 16, 득실 −5) / 영어 위키백과 14위 — 리가MX 규칙(승점→득실차)으로 13위
def mx_stage(d):
    y, mo = int(d[:4]), int(d[5:7])
    return ("아페르투라", y, "MEXA" if mo >= 7 else "MEX1") if mo >= 7 else ("클라우수라", y, "MEX1")
def mx_label(o, d):
    st, y, lg = mx_stage(d)
    s = f"{y}-{str(y + 1)[2:]}" if st == "아페르투라" else f"{y - 1}-{str(y)[2:]}"
    t = RANKS.get((lg, s), {})
    for nm in [o] + MX_NAME.get(o, []):
        k = key(nm)
        if k in t:
            r, n, _ = t[k]; r = RANK_FIX.get((lg, s, k), r)
            if (st, y) == ("아페르투라", 2014): return f"리가MX 아페르투라 2014 {r}위/{n}팀"   # 호나우지뉴 자료와 같은 형식(같은 단계)
            return f"리가MX {st} {y} {r}위/{n}팀 (경기 날짜에 진행 중이던 단계의 정규리그 순위)"
    return None

def make_label(lg, season, v):
    r, n, nm = v
    if lg == "PO1": return f"포르투갈 1부 {season} {r}위"
    if lg == "GB2":
        if season == "2026-27": return f"챔피언십 2026-27 {r}위/{n}팀 (2026년 11월 25일 현재 순위)"
        return f"챔피언십 {season} {r}위/{n}팀"
    if lg == "GB3":
        if season == "2026-27": return None
        return f"잉글랜드 3부 {season} {r}위/{n}팀 (EFL League One, 리그 수준 추정)"
    if lg == "SLO1": return f"슬로바키아 1부 {season} {r}위/{n}팀 (Slovak First Football League)"
    return None

def eu(d):
    y = int(d[:4]); m = int(d[5:7]); s_ = y if m >= 8 else y - 1
    if y == 2020 and m in (7, 8): s_ = 2019
    return f"{s_}-{str(s_ + 1)[2:]}"

MAN = {}   # 순위표 밖·순위 고친 상대: (key, 날짜) -> lv
def man(o, d, lv): MAN[(key(o), d)] = lv
# 멕시코 2부 아페르투라 2012(코파 MX 조별 2012.8.22): TM MEXB 2012-13 표
man("Correcaminos de la UAT", "2012-08-22", None)
# 파나마 아페르투라 2013 정규 단계(RSSSF Panama 2013/14 'Regular Stage Final Table'): 스포르팅 산미겔리토 8위/10팀(6승 2무 10패) — TM 표(1위)는 다른 단계 표
man("Sporting San Miguelito", "2013-09-17", "파나마 1부 2013-14 8위/10팀 (Liga Panameña de Fútbol, 경기 날짜에 진행 중이던 아페르투라 2013 정규 단계 순위)")
# 포르투갈 3부 2016-17(Campeonato de Portugal) 1단계 세리G 2위/10팀(영어 위키백과·FPF; 뒤에 남부 승격 그룹 1위로 승격)
man("Real SC", "2016-12-14", "포르투갈 3부 2016-17 2위/10팀 (Campeonato de Portugal Série G 1단계, 경기 날짜에 진행 중이던 단계 순위, 리그 수준 추정)")
# 북아일랜드 2018-19(2019-20 시즌은 8.9 개막이라 8.1 경기는 직전 시즌): 영어 위키백과 최종 4위(글레나번 승점 70 > 크루세이더스 65; TM 표 3위는 오류)
man("Crusaders FC", "2019-08-01", "북아일랜드 1부 2018-19 4위/12팀 (NIFL Premiership, 2019-20 시즌 개막 전이라 직전 시즌 최종 순위)")
# 아르메니아 2019-20(8.2 개막, 8월 경기 때 진행 중): 강등 라운드 2위 = 최종 8위/10팀(영어 위키백과 2019–20 Armenian Premier League)
for d_ in ("2019-08-08", "2019-08-15"):
    man("FC Pyunik Yerevan", d_, "아르메니아 1부 2019-20 8위/10팀 (Armenian Premier League, 스플릿 뒤 최종 순위)")

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def seasons_for(d):
    return [eu(d), d[:4]]
def opp_elo(o, d, cid, g):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    if (k, d) in MAN:
        lv = MAN[(k, d)]
        if lv is None:   # 멕시코 2부(TM 아페르투라 표)
            r, n, _ = RANKS[("MEXB", "2012-13")][k]
            lv = f"멕시코 2부 2012-13 {r}위/{n}팀 (Ascenso MX, 경기 날짜에 진행 중이던 아페르투라 2012 단계 순위, 리그 수준 추정)"
        e = lv_value(lv, d, o); ELO_SRC["직접 라벨(순위표 밖·순위 고침)"] += 1
        ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, d)] = (e, lv); return e, lv
    if cid in ("MEXA", "MEX1", "POME", "POMX", "MXCA", "MXCC", "CCL"):
        lv = mx_label(o, d)
        if lv:
            e = lv_value(lv, d, o); ELO_SRC["리가MX 단계 순위"] += 1
            ELO_LOG[(o, d)] = ("mx", e, lv); NEW_TS[(o, d)] = (e, lv); return e, lv
    for s in seasons_for(d):
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
            p = _LRA["parse"](lv, d)
            if p and lv_value(lv, d, o) != e: TABLE_DIFF.append((o, s, e, lv, lv_value(lv, d, o)))
            return e, lv
    s = eu(d)
    for lg in ("PO1", "GB2", "GB3", "SLO1"):
        t = RANKS.get((lg, s), {})
        if k in t:
            lv = make_label(lg, s, t[k])
            if not lv: continue
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
    fm = [r for r in FME[gid] if r["jimenez_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "1")]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["penalty"] == "1"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "pen" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 0): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["penalty"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
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
VRE = re.compile(r"Jim[eé]nez|히메네스")
G_DATES = {ldate(g) for g in GAMES}
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for x in oe:
        if x[0] == "a" and VRE.search(str(x[13] or "")) and x[9] in G_DATES:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(히메네스 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1], r[9])]
            if hit: CROSS.append(("히메네스 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 히메네스 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
SHARED = collections.Counter()
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for m in M:
        if any(mm[0] == m[0] and key(mm[1]) == key(m[1]) for mm in om): SHARED[b] += 1

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("amerj", "2014-08-13"), ("atmrj", "2015-08-13"), ("benrj", "2018-07-01"), ("wolrj", "2023-07-25"), ("fulrj", "2026-07-01"), ("wolrj", None)]
TM_CLUB = {"3631": "amerj", "13": "atmrj", "294": "benrj", "543": "wolrj", "931": "fulrj"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["clubId"])
PERIODS = [("클루브 아메리카", "2011~2014", None, "2014-08-13"), ("아틀레티코 마드리드", "2014~2015", "2014-08-13", "2015-08-13"),
           ("벤피카", "2015~2018", "2015-08-13", "2018-07-01"), ("울버햄튼", "2018~2023", "2018-07-01", "2023-07-25"),
           ("풀럼", "2023~2026", "2023-07-25", "2026-07-01"), ("울버햄튼", "2026~", "2026-07-01", None)]
def per(lo, hi):
    inr = lambda d: (lo is None or d >= lo) and (hi is None or d < hi)
    return [sum(1 for m in M if inr(m[0])), sum(1 for r in E if r[0] == "g" and inr(r[9])),
            sum(1 for r in E if r[0] == "a" and inr(r[9])), sum(m[3] for m in M if inr(m[0]))]
ST = [(n, y, per(lo, hi)) for n, y, lo, hi in PERIODS]
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
exec(open(os.path.join(HERE, "note_jimenez.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "elk", "elq", "cwc", "clg", "cl16", "mlp", "ccc"]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const RJM_E={J(E)};\nconst RJM_M={J(M)};\nconst RJM_NOTE={J(NOTE)};\n")
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
