#!/usr/bin/env python3
"""에네르 발렌시아 (Enner Valencia, Transfermarkt 139503, FotMob 195927): raw/ (+ espn_emelec_2010_2011.csv) -> ennervalencia.json + players/ennervalencia/env.js
   판정 근거는 judgments.md

  python3 players/ennervalencia/build_ennervalencia.py [--out <data 폴더>]   # 기본 players/ennervalencia/env.js; 스크래치 복사본 검증 때 SOC_ROOT=<복사본> … --out <복사본>/src/data
  python3 players/ennervalencia/build_ennervalencia.py --debug | --stat | --map | --applymap(스크래치 전용)

론돈 build 스크립트(같은 수집기 계열)를 발렌시아 raw 열 이름과 에콰도르·리가MX·프리미어리그·쉬페르리그·브라질·아르헨티나 대회에 맞춰 고친 것.
순위 라벨 행의 Elo는 tools/league_rank_apply.py parse()/value()(+ tools/league_points.py 승점 모형)로 라벨에서 계산.
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌(통합표 키)이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "env.js")
OUT_JSON = os.path.join(HERE, "ennervalencia.json")
ME = "139503"
ME_KO = "에네르 발렌시아"
CUTOFF = "2026-11-25"
GAP = "2014-08-01"

def rd(n, base=RAW):
    with open(os.path.join(base, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["team_level"] == "senior"]   # 608경기(웨스트햄 U21 1경기 제외)
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
ESPN = rd("espn_emelec_2010_2011.csv", HERE)   # TM에 없는 에멜렉 2010·2011 리그 경기(ESPN 경기 기록: 선발·교체 시각·골)

# ---------------------------------------------------------------- 날짜·출전 분
DATE_FIX = {}
# 2022.2.28 카슴파샤전: 90분 교체 투입 뒤 90+10분 다시 교체(TM 경기 기록), TM 출전 분 0 → 1분(출전 분 범위 0 초과)
MIN_FIX = {"3613100": 1}
EV_MIN_FIX = {}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local"])
def opp(g): return re.sub(r"\s*\(\s*-?\s*\d{4}\s*(-\s*\d{4})?\s*\)", "", g["opponent"]).strip()
# 리길야 클라우수라 2026: TM 라운드 이름이 비어 있음(tm_two_leg_ties_extra.csv) → 8강 1·2차전·준결승 1·2차전(론돈 자료와 같게)
RND_FIX = {"4878183": "Quarter-Finals 1st Leg", "4884188": "Quarter-Finals 2nd Leg", "4886540": "Semi-Finals 1st Leg", "4886545": "Semi-Finals 2nd Leg"}
def rnd_of(g): return RND_FIX.get(g["gameId"], g["round"] or "")

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ECPE", "ECSE", "GB1", "MEX1", "MEXA", "TR1", "BRA1", "ARGC"}
CUP = {"FAC", "CGB", "TRP", "BRC", "ARCA", "MXCA", "MXCC"}
STATE = {"BRRS", "RS2f"}   # 캄페오나투 가우슈(1부 클럽 주 선수권) = 국내컵 하위 라운드 비중(오스카·파투 선례)
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round") or r.startswith("6th round"): return "dk"
        return "dc"
    if cid == "CAMC": return "df"            # 캄페오네스컵 = 국내컵 결승 비중(지냑 선례)
    if cid == "ECPL": return "mlp"           # 에콰도르 2012 3단계(2위 결정 두 경기) = 리그 플레이오프(리길야 선례)
    if cid in ("POME", "POMX"):              # 리길야 = MLS 플레이오프 비중(치차리토·지냑·론돈 선례), 플레이인 mlp
        if r.startswith("semi"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
        return "mlp"
    if cid == "CCL":                         # 북중미 챔스 2018~2020
        if r.startswith("final"): return "cccf"
        if r.startswith("semi"): return "cccsf"
        if r.startswith("quarter"): return "ccck"
        return "ccc"
    if cid == "USMX": return "lck"           # 리그스컵 2019 8강·준결승
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"                         # 예선·조별·16강
    if cid == "CS":
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"                         # 1·2라운드·조별·16강 플레이오프·16강
    if cid == "CLQ": return "clq"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"
    if cid == "UCOL": return "eck"           # 컨퍼런스리그 2021-22 녹아웃 플레이오프
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd, gid):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if cid in STATE and not r: return 0      # 가우슈 리그 단계
    if r.startswith("group"): return 0       # 리베르타도레스·수다메리카나·유로파·코파 MX 조별
    return 1

def tie_rule(cid, d, rnd):
    r = rnd.lower()
    if cid in ("EL", "ELQ", "CLQ", "UCOL"): return (int(d < "2021-07-01"), 1)
    if cid in ("CLI", "CS"):
        if d >= "2022-01-01": return (0, 0)
        return (1, 0)                        # 2021년까지 원정 다득점, 연장 없이 승부차기(오스카·파투 선례)
    if cid == "CCL": return (1, 0)           # 북중미 챔스 2023년까지 원정 다득점·연장 없음(지냑 선례)
    if cid in ("POME", "POMX"):
        if r.startswith("final"): return (0, 1)
        return (0, 0)                        # 리길야 8강·준결승: 합계 동률이면 정규리그 상위 팀
    if cid == "ECPL": return (0, 0)
    if cid == "BRC": return (0, 0)           # 코파 두 브라질 2018부터 원정 다득점 없음
    if cid in STATE: return (0, 0)           # 주 선수권 두 경기: 원정 다득점·연장 없음(오스카·네이마르 선례)
    if cid == "TRP": return (0, 1)           # 튀르키예컵 준결승 2023: 원정 다득점 없음, 연장(2022-23 규정)
    if cid == "MXCA": return (0, 0)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home"] == g["club"] or m["home_id"] == g["clubId"]: return "h"
    if m["away"] == g["club"] or m["away_id"] == g["clubId"]: return "a"
    sys.exit("편 판정 실패 " + gid)

EXTRA = {}
for r in rd("tm_two_leg_ties_extra.csv"):
    for a, b in (("leg1", "leg2"), ("leg2", "leg1")):
        EXTRA[r[a + "_gameId"]] = (r[b + "_home"], r[b + "_away"], r[b + "_score"])
OTHER_FIX = {"2372617": (2, 1)}   # 에콰도르 2012 2위 결정전 1차전 LDU 키토 1-2 에멜렉(영어 위키백과 2012 시즌 문서; TM에 1차전 경기 기록 없음, ESPN 기록상 발렌시아 명단 밖)
def other_leg(gid):
    if gid in OTHER_FIX: return OTHER_FIX[gid]
    g = G[gid]; club = g["club"]
    m = MI[gid]; oid = m["other_leg_id"]
    if oid and oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split("-"))
        if o["home_id"] == g["clubId"]: return (fh, fa)
        if o["away_id"] == g["clubId"]: return (fa, fh)
    if gid in EXTRA:
        h, a, sc = EXTRA[gid]; fh, fa = map(int, sc.split("-"))
        if h == club: return (fh, fa)
        if a == club: return (fa, fh)
    if m["other_leg_score"]:   # '2-1' 같은 다른 차전 스코어(홈-원정): 다른 차전 홈 = 이 경기 원정
        fh, fa = map(int, m["other_leg_score"].split(":") if ":" in m["other_leg_score"] else m["other_leg_score"].split("-"))
        return (fa, fh) if side_of(gid) == "h" else (fh, fa)
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
for r in ESPN:   # 에멜렉 2010·2011 리그(ESPN 경기 기록의 선발·교체 시각으로 출전 분)
    if r["played"] == "1":
        M.append([r["date_local"], r["opp"], "mlpf" if r["stage"] == "final" else "lg", int(r["minutes"])])
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
        if f["valencia_assist"] == "1" and f["pen_shootout_event"] != "True" and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])): return True
    return False

# 2014.8 이후 Transfermarkt에만 있는 일반 유형 도움: 다른 출처 2곳으로 판정(judgments.md 4절)
A_CHECK = {
 "2486523|37": (False, "2014.9.27 맨유전 37분 사코 골: 웨스트햄 공식 문자중계('Valencia, whose header comes back off the bar, but Sakho is waiting to knock the loose ball home')·Sportsmole 기사 모두 발렌시아 헤더가 크로스바에 맞고 나온 공을 사코가 넣은 것 — 슈팅 리바운드라 도움 아님(TM Header 유형, FotMob 도움 없음)"),
 "3007847|31": (True, "2018.2.17 아틀라스전 31분 지냑 골: Mediotiempo 문자중계('Asistencia de Enner Valencia con un centro al área')·La Razón 경기 기사('remató de cabeza un centro de Enner Valencia')·ESPN 문자중계 'Assisted by Enner Valencia with a cross'"),
 "3012299|8": (True, "2018.3.4 베라크루스전 8분 셀라라얀 골: ESPN 문자중계 'Assisted by Enner Valencia'·Mediotiempo 문자중계·Soccerway 경기 기록"),
 "3023873|45": (True, "2018.3.31 레온전 45분 이스마엘 소사 골: ESPN 문자중계 'Assisted by Enner Valencia'·Mediotiempo 문자중계('con asistencia de Enner Valencia')"),
 "3070140|51": (False, "2018.7.24 코파 MX 산루이스전 51분 바르가스 골: 경기 기사·문자중계에서 도움을 확인하지 못함"),
 "3114480|17": (False, "2018.10.3 코파 MX 파추카전 17분 이스마엘 소사 골: TUDN·El Universal 등 경기 기사에 도움 언급 없음('Sosa, tras recibir el balón dentro del área')"),
 "3164676|48": (True, "2019.4.14 로보스 BUAP전 48분 바르가스 골: ESPN 문자중계 'Assisted by Enner Valencia'·Mediotiempo 문자중계"),
 "3225047|57": (True, "2019.7.24 리그스컵 리얼 솔트레이크전 57분 바르가스 골: 리얼 솔트레이크 구단 경기 기사(발렌시아의 패스를 받은 바르가스 슈팅)·ESPN 문자중계 'Assisted by Enner Valencia'"),
 "3285791|70": (False, "2019.12.1 리길야 8강 2차전 아메리카전 70분 지냑 골: ESPN 경기 기사(Notimex)는 '발렌시아의 패스를 연결'이라 쓰지만 ESPN 문자중계는 도움 없음, EFE 기사는 발렌시아·키뇨네스가 만든 공격이라고만 써서 확인 출처가 한 곳뿐"),
 "3332764|57": (False, "2020.3.14 후아레스전 57분 지냑 골: Milenio·ESPN 경기 기록에 도움 없음, 다른 경기 기사에도 발렌시아 도움 언급 없음"),
 "3427202|90+9": (True, "2021.5.15 카이세리스포르전 90+9분 세르다르 아지즈 골: Fox Sports 박스스코어 'S. Aziz scored a goal, assisted by E. Valencia'·튀르키예 문자중계('Sağ kanattan Valencia ortaladı, … Serdar Aziz nefis bir kafa vuruşuyla')"),
 "4241101|70": (True, "2024.1.21 가우슈 아베니다전 70분 완데르송 골: ESPN 기사('Enner Valencia dio una asistencia')·Trivela·Flashscore 경기 기사(발렌시아가 머리로 떨궈 준 공을 완데르송이 헤더)"),
 "4241112|15": (True, "2024.1.27 가우슈 이피랑가전 15분 알랑 파트리크 골: ESPN 기사('Nueva asistencia de Enner Valencia')·Jornal do Comércio·Gazeta Esportiva 경기 기사(발렌시아 패스를 알랑 파트리크가 마무리)"),
 "4241151|28": (True, "2024.2.18 가우슈 노부 암부르구전 28분 알랑 파트리크 골: ESPN 기사('Enner: gol y asistencia')·Trivela 경기 기사(발렌시아가 끝줄까지 몰고 가 내준 공을 알랑 파트리크가 마무리)"),
 "4509626|70": (True, "2025.2.12 가우슈 상루이스전 70분 완데르송 골: Itatiaia('Wanderson marcou o terceiro com assistência de Valencia')·Soccerway·ESPN 경기 기사"),
}
# FotMob에만 있는 도움(넣지 않음): 2021.10.17 트라브존스포르전 3분 디에구 로시 골 — beIN Sports 기사는 발렌시아와 비토르 우구가 다투다 흘러나온 공을 로시가 넣었다고 써 도움으로 보지 않음(Betfred·Sportsmole 기록은 같은 Opta 계열 자료)
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
        if f["valencia_assist"] == "1" and f["pen_shootout_event"] != "True":
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
    if b in ("hon.js", "clubcolors.js", "finals.js", "env.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
PAR = {}   # 이번 회차 병렬 판정(읽기만)
for slug in ("sternjohn", "dempsey", "guerrero"):
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
    if " 순위 없음" in lv.split(" (")[0]:   # 순위 없는 하부 리그 팀: 그 단계 기준점(league_rank_apply base())
        mm = re.match(r"^(.+?) (\d)부 (\d{4})", lv)
        k = [_LRA["KO"][mm.group(1)]]
        return int(round(_LRA["base"](k[0], int(mm.group(2)), int(mm.group(3)), True)))
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

# 데이터 상대 이름(TM) → 순위표·통합표 이름(옛 이름·다른 표기)
NAME_ALIAS = {}
def nm_cands(o): return [o] + (NAME_ALIAS[o] if isinstance(NAME_ALIAS.get(o), list) else [NAME_ALIAS[o]] if o in NAME_ALIAS else [])

WIKI = collections.defaultdict(dict)
for r in rd("ranks_wiki_tables.csv"):
    WIKI[(r["file"], r["headings"])][key(r["team"])] = (int(r["rank"]), int(r["teams"]), r["team"])
def tab_rank(t, o):
    for nm in nm_cands(o):
        k = key(nm)
        if k in t: return t[k][:2]
    for nm in nm_cands(o):
        for kk, v in t.items():
            if toks(kk) and (toks(kk) <= toks(nm) | {"fc"} or toks(nm) <= toks(kk)): return v[:2]
    return None
def wiki_rank(fn, hd, o): return tab_rank(WIKI[(fn, hd)], o)

# FotMob 리그 표(fotmob_league_tables.csv): (파일, 소표) → 팀 → (순위, 팀 수, 이름, 승점, 득실, 득점)
FMT = collections.defaultdict(dict)
for r in rd("fotmob_league_tables.csv"):
    gf, ga = map(int, r["goals"].split("-"))
    FMT[(r["file"], r["subtable"])][key(r["team"])] = (int(r["rank"]), int(r["n_teams"]), r["team"], int(r["pts"]), gf - ga, gf, int(r["played"]))
def fm_combined(parts):   # 여러 소표(두 조·두 단계)를 승점→득실차→다득점으로 합친 순위
    tot = collections.defaultdict(lambda: [0, 0, 0, ""])
    for fp in parts:
        for k, v in FMT[fp].items():
            t = tot[k]; t[0] += v[3]; t[1] += v[4]; t[2] += v[5]; t[3] = v[2]
    order = sorted(tot.items(), key=lambda kv: (-kv[1][0], -kv[1][1], -kv[1][2]))
    return {k: (i + 1, len(order), v[3]) for i, (k, v) in enumerate(order)}

def eu(d):
    y = int(d[:4]); m = int(d[5:7]); s_ = y if m >= 8 else y - 1
    if y == 2020 and m in (7, 8): s_ = 2019
    return f"{s_}-{str(s_ + 1)[2:]}"
def jul1(d):
    y = int(d[:4]); s_ = y if int(d[5:7]) >= 7 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"

# 에콰도르 1부: 기존 자료(바르셀로나 SC 2012·데포르티보 쿠엥카 2010)와 같은 연간 합산 순위(영어 위키백과 시즌 문서 Aggregate table)
def ecu_label(o, d):
    y = d[:4]
    v = wiki_rank(f"en_{y}_ecu.txt", "Results / Aggregate table", o)
    return v and f"에콰도르 1부 {y} {v[0]}위/{v[1]}팀 (Ecuadorian Serie A, 연간 합산 순위)"
ECU = {"CS Emelec", "LDU Quito", "Deportivo Quito", "Barcelona SC Guayaquil", "CD El Nacional", "Deportivo Cuenca", "Manta FC", "Independiente del Valle",
       "CD Olmedo", "CD Espoli", "Imbabura SC", "LDU de Loja", "CD Macará", "CD Universidad Católica", "Deportivo Quevedo", "Técnico Universitario", "Universidad Católica"}

# 리가MX: 2014년 클라우수라·2025-26은 경기 날짜에 진행 중이던 단계 순위(론돈·히메네스 형식),
# 티그레스 시절 2017-18~2019-20은 지냑 자료와 같은 '누적'(아페르투라+클라우수라 정규리그 합산) 순위
def mx_label(o, d):
    y, mo = int(d[:4]), int(d[5:7])
    if d < "2014-08-01" or d >= "2025-07-01":
        st, fn_st = ("아페르투라", "Apertura") if mo >= 7 else ("클라우수라", "Clausura")
        s = f"{y}-{str(y + 1)[2:]}" if mo >= 7 else f"{y - 1}-{str(y)[2:]}"
        fn = f"230_{s[:4]}-{int(s[:4]) + 1}-{fn_st}.json.gz"
        v = tab_rank(FMT[(fn, fn_st)], o)
        return v and f"리가MX {s} {v[0]}위/{v[1]}팀 (Liga MX {st} {y}, 경기 날짜에 진행 중이던 단계의 정규리그 순위)"
    s = jul1(d); a = s[:4]
    parts = [(f"230_{a}-{int(a) + 1}-Clausura.json.gz", "Apertura"), (f"230_{a}-{int(a) + 1}-Clausura.json.gz", "Clausura")]
    if not FMT[parts[0]]: return None
    v = tab_rank(fm_combined(parts), o)
    return v and f"리가MX {s} 누적 {v[0]}위/{v[1]}팀"

# 브라질 세리에 A(달력 연도 최종 순위, FotMob 표 = 위키백과)
def bra_label(o, d):
    v = tab_rank(FMT[(f"268_{d[:4]}.json.gz", "Série A")], o)
    return v and f"브라질 세리에 A {d[:4]} {v[0]}위/20팀"

# 아르헨티나 1부 클라우수라 2026: 두 조(각 15팀) 통합 30팀 순위(디 마리아·데파울 자료 형식), 2026.11.25 현재 16라운드 조별 단계 종료(결선 진행 중)
def arg_label(o, d):
    fn = "112_2026-Clausura.json.gz"
    v = tab_rank(fm_combined([(fn, "Clausura Group A"), (fn, "Clausura Group B")]), o)
    return v and f"아르헨티나 1부 클라우수라 2026 {v[0]}위/{v[1]}팀 (두 조 통합 순위, 조별 단계 종료 뒤)"

def tr_label(o, d):
    s = eu(d); t = RANKS.get(("TR1", s), {})
    v = tab_rank(t, o)
    return v and f"쉬페르리그 {s} {v[0]}위/{v[1]}팀"

MAN = []   # 순위표 밖·직접 정한 상대: (key, 날짜 시작, 날짜 끝, lv)
def man(o, d, lv, d2=None): MAN.append((key(o), d, d2 or d, lv))
def man_get(o, d):
    for k_, a_, b_, lv_ in MAN:
        if k_ == key(o) and a_ <= d <= b_: return lv_
    return None
exec(open(os.path.join(HERE, "man_labels.py"), encoding="utf-8").read())   # 손으로 정한 라벨(judgments.md 6절)

def stage_key(lv):   # tools/elo_table.js lvSeason()과 같은 시즌 키
    t = lv
    for _ in range(3): t = re.sub(r"\([^()]*\)", " ", t)
    s = None
    for m in re.finditer(r"((?:19|20)\d\d)\s*[-–/]\s*(\d{2}|\d{4})(?!\d)", t):
        a, b = int(m.group(1)), int(m.group(2))
        if b == (a + 1) % 100 or b == a + 1: s = f"{a}-{str(a + 1)[2:]}"; break
    if not s:
        m = re.search(r"(?:^|[^\d])((?:19|20)\d\d)(?![\d-])", t); s = m.group(1) if m else None
    g = re.search(r"(Apertura|Clausura|Inicial|Torneo Final|Torneo I{1,2}\b|Copa de la Liga|아페르투라|클라우수라)", lv)
    return s + "/" + g.group(1).replace("아페르투라", "Apertura").replace("클라우수라", "Clausura") if s and g else s

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def table_hit(o, ks):
    for nm in nm_cands(o):
        for s in ks:
            if (key(nm), s) in TABLE:
                return collections.Counter(TABLE[(key(nm), s)]).most_common(1)[0][0], s
    return None
MXT = {"CF Pachuca", "Tigres UANL", "CF Monterrey", "Club América", "CF América", "Deportivo Toluca", "Club Tijuana", "Club León FC", "Atlas Guadalajara",
       "CF Atlante", "Club Atlético Morelia", "Santos Laguna", "Jaguares FC", "Deportivo Guadalajara", "Puebla FC", "Querétaro FC", "UNAM Pumas", "Tiburones Rojos de Veracruz",
       "Lobos BUAP", "Club Necaxa", "Cruz Azul", "CD Cruz Azul", "FC Juárez", "Mazatlán FC", "Atlético de San Luis", "Monarcas Morelia", "Chivas Guadalajara"}
def label_for(o, d, cid):
    if man_get(o, d): return man_get(o, d), "man"
    if cid in ("ECPE", "ECSE", "ECPL", "ESPN") or o in ECU: return ecu_label(o, d), "ecu"
    if o in MXT: return mx_label(o, d), "mx"
    if cid in ("BRA1",) or (cid in ("CLI", "CS", "BRC") and bra_label(o, d)): return bra_label(o, d), "bra"
    if cid in ("ARGC", "ARCA") or (cid == "CS" and d >= "2026-07-01" and arg_label(o, d)): return arg_label(o, d), "arg"
    if cid in ("TR1", "TRP") and tr_label(o, d): return tr_label(o, d), "tr"
    return None, None
def opp_elo(o, d, cid, g=None):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    lv, how = label_for(o, d, cid)
    if lv:   # 같은 팀×단계 키가 통합표에 있으면 그 라벨
        h = table_hit(o, [stage_key(lv)])
        if h:
            (e, lv2), s = h; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv2, s)
            p = _LRA["parse"](lv2, d)
            if p and lv_value(lv2, d, o) != e: TABLE_DIFF.append((o, s, e, lv2, lv_value(lv2, d, o)))
            if lv2.split(" (")[0] != lv.split(" (")[0]: TABLE_DIFF.append(("라벨 다름", o, s, lv2, lv))
            return e, lv2
        e = lv_value(lv, d, o); ELO_SRC["순위 라벨(" + how + ")"] += 1
        ELO_LOG[(o, d)] = (how, e, lv); NEW_TS[(o, d)] = (e, lv); return e, lv
    h = table_hit(o, [eu(d), d[:4], jul1(d)])
    if h:
        (e, lv), s = h
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
        p = _LRA["parse"](lv, d)
        if p and lv_value(lv, d, o) != e: TABLE_DIFF.append((o, s, e, lv, lv_value(lv, d, o)))
        return e, lv
    MISS.append((o, d, cid, eu(d))); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd, gid)
    elo, lv = opp_elo(opp(g), d, cid, g)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
for r in ESPN:   # ESPN 경기 기록 골(2010·2011 리그, 도움은 넣지 않음)
    for gtok in r["goals"].split():
        mm_, sc = gtok.split("@"); pk = 1 if sc.endswith("P") else 0
        gf, ga = map(int, sc.rstrip("P").split("-"))
        mi, dm = mins(mm_.replace("'", ""))
        elo, lv = opp_elo(r["opp"], r["date_local"], "ESPN")
        E.append(["g", r["opp"], elo, "mlpf" if r["stage"] == "final" else "lg", mi, gf, ga, 0, pk, r["date_local"], 0, dm, lv, 0])
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

# ---------------------------------------------------------------- 승점 표 map 줄(elo/league_points_other.json) 계산
def tnorm(x): return norm(re.sub(r"\(.*?\)", " ", x))
def row_of(rows, o, rk):
    def sc1(nm, t):
        a, b = set(tnorm(nm).split()), set(tnorm(t).split())
        if b and b <= a: return 1.0
        x, y = tnorm(nm).split(), tnorm(t).split()
        if x and y and x[0] == y[0] and len(x[0]) >= 4: return 0.8
        return PTS.sim(tnorm(nm), tnorm(t))
    def sc(i): return max(sc1(nm, rows[i][0]) for nm in nm_cands(o) + [re.sub(r"^(CA|CD|CF|FC|Club Atlético|Club|AA|GFK|FK) ", "", o)])
    if 0 < rk <= len(rows) and sc(rk - 1) >= 0.5: return sc(rk - 1), rk - 1
    return max((sc(i), i) for i in range(len(rows)))
MAP_LINES = {}
for r in E:
    lv, o = r[12], r[1]
    head = lv.split(" (")[0]; mm = re.match(r"^(.*?) (\d+)위", head)
    if not mm: continue
    ent = PTS.O["seasons"].get(mm.group(1))
    if not ent or "skip" in ent or ent.get("ongoing"): continue
    rk = int(mm.group(2)); tabs = ent["tables"]
    ti = 0
    st = "Apertura" if ("아페르투라" in lv or "Apertura" in lv) else "Clausura" if ("클라우수라" in lv or "Clausura" in lv) else None
    mp = ent.get("map", {})
    alias_pos = next((mp[a] for a in nm_cands(o)[1:] if a in mp), None)
    if len(tabs) > 1:
        cand = [i for i, t in enumerate(tabs) if st and st in t["name"]]
        if mm.group(1) == "중국 슈퍼리그 2020" or same_tabs: cand = [0]   # 2020 1단계 A조(다롄·장쑤·산둥·상하이 선화·선전·허난 모두 A조)
        if len(cand) != 1 and not alias_pos: continue
        ti = cand[0] if len(cand) == 1 else alias_pos[0]
    cur = mp.get(f"{rk}={o}") or mp.get(f"{o}@{rk}") or mp.get(o)
    res = PTS.other_score(lv, o)
    src = ELO_LOG.get((o, r[9]), ("?",))[0]
    same_tabs = all(sorted(map(tuple, t["rows"])) == sorted(map(tuple, tabs[0]["rows"])) for t in tabs)
    if src in ("table", "same"):   # 기존 라벨 재사용: 기존 선수 값이 바뀌지 않게, 내 이름이 표에서 안 찾힐 때만 이름 줄 추가
        if res is not None: continue
    elif res is not None and (len(tabs) == 1 or same_tabs or (cur and cur[0] == ti)): continue
    if alias_pos and PTS.other_score(lv, o) is None:
        MAP_LINES[(mm.group(1), o)] = (tabs[alias_pos[0]]["rows"][alias_pos[1]][0], alias_pos, rk, 1.0, "기존 다른 표기와 같은 행"); continue
    sc_, ri = row_of(tabs[ti]["rows"], o, rk)
    kname = o if (o not in mp and (len(tabs) == 1 or same_tabs)) else f"{o}@{rk}"
    MAP_LINES[(mm.group(1), kname)] = (tabs[ti]["rows"][ri][0], [ti, ri], rk, round(sc_, 2), "표 순위 다름" if ri + 1 != rk else "")
# 이름 유사도로 잘못 고른 행 바로잡기(표 순서 = 라벨 순위 확인)
for (h_, k_), pos_, nm_ in ((("에콰도르 1부 2010", "LDU Quito"), [0, 1], "Liga Deportiva Universitaria de Quito"), (("에콰도르 1부 2012", "LDU Quito"), [0, 2], "Liga Deportiva Universitaria de Quito"),
                          (("에콰도르 1부 2012", "CD Macará"), [0, 9], "Club Social y Deportivo Macará"),
                          (("리가MX 2025-26", "Atlético de San Luis@15"), [1, 14], "Atlético San Luis"),):
    if (h_, k_) in MAP_LINES: MAP_LINES[(h_, k_)] = (nm_, pos_, MAP_LINES[(h_, k_)][2], 1.0, "손으로 고침")
if "--map" in sys.argv:
    for (h, k), v in sorted(MAP_LINES.items()): print(f"{h} | {k} | {v[0]} | {v[1]} {v[4]} sim={v[3]}")
    sys.exit(0)
if "--applymap" in sys.argv:   # 스크래치 복사본 전용: SOC_ROOT의 elo/league_points_other.json에 map 줄 추가
    if os.path.realpath(ROOT) == "/home/user/soc": sys.exit("정본에는 쓰지 않음")
    fp = os.path.join(ELO, "league_points_other.json"); O_ = json.load(open(fp, encoding="utf-8"))
    for (h, k), v in MAP_LINES.items(): O_["seasons"][h].setdefault("map", {})[k] = v[1]
    json.dump(O_, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); print("map 줄", len(MAP_LINES)); sys.exit(0)

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
    fm = [r for r in FME[gid] if r["valencia_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "1")]
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
VRE = re.compile(r"Enner Valencia|Valencia|발렌시아")
G_DATES = {ldate(g) for g in GAMES}
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for x in oe:
        if x[0] == "a" and VRE.search(str(x[13] or "")) and x[9] in G_DATES:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(발렌시아 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1], r[9])]
            if hit: CROSS.append(("발렌시아 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 발렌시아 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
SHARED = collections.Counter()
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for m in M:
        if any(mm[0] == m[0] and key(mm[1]) == key(m[1]) for mm in om): SHARED[b] += 1

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("emeenv", "2014-01-01"), ("pacenv", "2014-07-01"), ("whuenv", "2016-08-31"), ("eveenv", "2017-07-01"), ("tigenv", "2020-07-01"),
         ("fenenv", "2023-07-01"), ("intenv", "2025-09-10"), ("pacenv", "2026-08-09"), ("bocenv", None)]
TM_CLUB = {"4561": "emeenv", "4035": "pacenv", "379": "whuenv", "29": "eveenv", "7055": "tigenv", "36": "fenenv", "6600": "intenv", "189": "bocenv"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["clubId"])
PERIODS = [("에멜렉", "2010~2013", None, "2014-01-01"), ("파추카", "2014", "2014-01-01", "2014-07-01"),
           ("웨스트햄 유나이티드", "2014~2016", "2014-07-01", "2016-08-31"), ("에버턴", "2016~2017", "2016-08-31", "2017-07-01"),
           ("티그레스 UANL", "2017~2020", "2017-07-01", "2020-07-01"), ("페네르바흐체", "2020~2023", "2020-07-01", "2023-07-01"),
           ("인테르나시오나우", "2023~2025", "2023-07-01", "2025-09-10"), ("파추카", "2025~2026", "2025-09-10", "2026-08-09"),
           ("보카 주니어스", "2026~", "2026-08-09", None)]
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
exec(open(os.path.join(HERE, "note_ennervalencia.py"), encoding="utf-8").read())   # NOTE_LINES
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const ENV_E={J(E)};\nconst ENV_M={J(M)};\nconst ENV_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()}, "map_need": sorted(set(MAPNEED)),
               "table_label_diffs": TABLE_DIFF, "map_lines": [[h, k, v[0], v[1]] for (h, k), v in sorted(MAP_LINES.items())], "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for v in ST: print(" ", v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
