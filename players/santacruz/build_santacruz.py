#!/usr/bin/env python3
"""로케 산타크루스 (Roque Santa Cruz, Transfermarkt 215, FotMob 30646): raw/ -> santacruz.json + players/santacruz/rsc.js (판정 근거는 judgments.md)

  python3 players/santacruz/build_santacruz.py [--out <data 폴더>]   # 기본 players/santacruz/rsc.js; 스크래치 복사본 검증 때 SOC_ROOT=<복사본> … --out <복사본>/src/data
  python3 players/santacruz/build_santacruz.py --debug | --stat | --map | --applymap(스크래치 전용)

론돈 build 스크립트(같은 수집기 계열)를 산타크루스 raw 열 이름과 파라과이·리가MX·남미 대회에 맞춰 고친 것.
순위 라벨 행의 Elo는 tools/league_rank_apply.py parse()/value()(+ tools/league_points.py 승점 모형)로 라벨에서 계산.
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌(통합표 키)이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "rsc.js")
OUT_JSON = os.path.join(HERE, "santacruz.json")
ME = "215"
ME_KO = "로케 산타크루스"
CUTOFF = "2026-11-25"
GAP = "2014-08-01"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["team_level"] == "senior"]   # 바이에른 II(6)·맨시티 U21(1) 제외
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 날짜·출전 분
# TM 시각이 기본값(22:00Z 등)이라 현지 날짜가 하루 앞선 경기: FotMob 실제 킥오프(현지 날짜)로 고침. ESPN 일정 API로 4경기 확인
# (2015.4.11 크루스 아술-티그레스, 2018.8.19 세로 포르테뇨-올림피아, 2018.10.28 카피아타-올림피아, 2023.2.4 레시스텐시아-리베르타드)
DATE_FIX = {"2528285": "2015-04-11", "3485021": "2017-11-11", "3446399": "2018-04-01", "3446852": "2018-08-19", "3446876": "2018-09-15",
            "3446915": "2018-10-28", "3446925": "2018-11-10", "3446940": "2018-11-24", "3446936": "2018-11-28", "3446948": "2018-12-02",
            "3646931": "2021-08-14", "3649143": "2021-09-12", "3879491": "2022-10-23", "4005703": "2023-02-04", "4005747": "2023-03-30"}
# 코파 메르코수르 1998 두 경기: TM 출전 분 비어 있음, 경기 기록 선발·교체 없음 → 90분
MIN_FIX = {"4313987": 90, "4314051": 90}
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local"])
def opp(g): return re.sub(r"\s*\(\s*-?\s*\d{4}\s*(-\s*\d{4})?\s*\)", "", g["opponent"]).replace("Myllykosken Pallo -47", "Myllykosken Pallo -47").strip()
def rnd_of(g): return g["round"] or ""

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "GB1", "ES1", "MEX1", "PR1A", "PR1C"}
CUP = {"DFB", "CGB", "FAC", "CDR", "LPO", "PYC1"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "USC": return "df"                # UEFA 슈퍼컵 = 국내컵 결승 비중
    if cid == "PR1P":                           # 파라과이 클라우수라 2020 플레이오프 = MLS 플레이오프 비중(리길야 선례)
        if r.startswith("semi"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
        return "mlp"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
    if cid in ("UEQ", "UEFA"): return "elq"      # UEFA컵 예선·1라운드(2009년 이전)
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        return "lib"                            # 예선 1~3라운드·조별·16강
    if cid in ("CS", "CMER"):                   # 코파 메르코수르 = 수다메리카나 비중(아이마르·아드리아누 선례)
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

def tie_rule(cid, d, rnd):
    if cid in ("CL", "UEFA", "UEQ"): return (int(d < "2021-07-01"), 1)
    if cid == "CDR": return (int(d < "2019-07-01"), 1)
    if cid in ("CLI", "CS"): return (int("2005-01-01" <= d < "2022-01-01"), 0)   # 원정 다득점 2021년까지, 연장 없이 승부차기(결승 제외)
    if cid == "CMER": return (1, 0)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["clubId"]: return "h"
    if m["away_id"] == g["clubId"]: return "a"
    sys.exit("편 판정 실패 " + gid)

EXTRA_LEG = {}
for r in rd("tm_two_leg_ties_extra.csv"):
    if r["comp"] == "FAC": continue
    for a, b in ((r["leg1_gameId"], r["leg2_gameId"]), (r["leg2_gameId"], r["leg1_gameId"])):
        EXTRA_LEG[a] = (b, r["leg1"] if b == r["leg1_gameId"] else r["leg2"])
def other_leg(gid):
    g = G[gid]; club = g["club"]
    if gid in EXTRA_LEG:
        b, txt = EXTRA_LEG[gid]
        m = re.match(r"(.*) (\d+)-(\d+) (.*) (none|n\.V\.|n\.E\.)$", txt)
        h, a = int(m.group(2)), int(m.group(3))
        return (h, a) if m.group(1) == club else (a, h)
    m = MI[gid]; oid = m["other_leg_id"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split("-"))
        if o["home_id"] == g["clubId"]: return (fh, fa)
        if o["away_id"] == g["clubId"]: return (fa, fh)
    base = re.sub(r"\s*(1st|2nd) leg", "", rnd_of(g).lower())
    cand = [x for x in GAMES if x["gameId"] != gid and x["competitionId"] == g["competitionId"] and x["opponentId"] == g["opponentId"]
            and re.sub(r"\s*(1st|2nd) leg", "", rnd_of(x).lower()) == base and "1st" in rnd_of(x).lower()]
    if len(cand) == 1:
        a, b = map(int, cand[0]["score_club_opp"].split("-")); return (a, b)
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

# ---------------------------------------------------------------- TM에 없는 경기(경기 단위 출처 있는 것만, judgments.md 2절)
# (날짜, 상대, 대회 코드, 분, 추정?, 출처)
EXTRA_M = [
    ("1998-10-27", "CA Vélez Sarsfield", "csak", 90, 1, "코파 메르코수르 1998 8강 1차전 벨레스 3-4 올림피아(영어·스페인어 위키백과 경기 상자: 65분 산타크루스 골)"),
    ("1998-11-04", "CA Vélez Sarsfield", "csak", 90, 1, "8강 2차전 올림피아 2-1 벨레스(위키백과 경기 상자: 24·40분 산타크루스 골)"),
    ("2017-07-12", "Club Nacional Asunción", "csa", 45, 0, "수다메리카나 2라운드 1차전 나시오날 1-1 올림피아: TM 명단 제외로 적혔으나 ESPN 경기 기록(45분 I. 토레스 대신 교체 투입)·FotMob 선수 경기 목록(44분) 모두 출전"),
    ("2018-11-07", "Club Libertad Asunción", "dk", 90, 1, "코파 파라과이 2018 8강 올림피아 1-0 리베르타드(영어 위키백과 경기 상자, APF 보도 'Roque mete a Olimpia en semis')"),
    ("2018-11-20", "Sportivo Luqueño", "dsf", 90, 1, "코파 파라과이 2018 준결승 루케뇨 1-3 올림피아(위키백과 경기 상자: 83·90+3분 골)"),
    ("2018-12-05", "Club Guaraní", "df", 90, 1, "코파 파라과이 2018 결승 올림피아 2-2 과라니, 승부차기 3-5(위키백과 경기 상자: 56분 골, 승부차기 실축)"),
    ("2021-09-15", "Club Cristóbal Colón (JAS)", "dc", 90, 1, "코파 파라과이 2021 32강 크리스토발 콜론(JAS) 2-3 올림피아(위키백과 경기 상자: 17분 골, 72분 자책골)"),
    ("2021-12-12", "Club Cerro Porteño", "df", 73, 0, "수페르코파 파라과이 2021 올림피아 3-1 세로 포르테뇨(위키백과 경기 상자·선발 명단: 15분 골, 73분 교체)"),
    ("2022-09-07", "Club Olimpia", "dc", 53, 1, "코파 파라과이 2022 16강 올림피아 0-4 리베르타드(53분 관중 소요로 중단, 리베르타드 승으로 확정; 위키백과 경기 상자: 45+3분 골)"),
    ("2023-11-09", "Club Nacional Asunción", "dsf", 76, 0, "코파 파라과이 2023 준결승 리베르타드 3-1 나시오날(FotMob 선수 경기 목록 76분)"),
    ("2023-12-02", "Club Sportivo Trinidense", "df", 40, 0, "코파 파라과이 2023 결승 트리니덴세 1-1 리베르타드(연장, FotMob 40분·스페인어 위키백과 80분 교체 투입)"),
    ("2024-10-02", "Encarnación FC", "dc", 90, 1, "코파 파라과이 2024 16강 엔카르나시온 0-2 리베르타드(위키백과 경기 상자: 76분 골)"),
    ("2024-11-13", "Sportivo Luqueño", "dsf", 90, 1, "코파 파라과이 2024 준결승 리베르타드 2-0 루케뇨(위키백과 경기 상자: 90+2분 골)"),
    ("2025-01-22", "Club Olimpia", "df", 90, 1, "수페르코파 파라과이 2024(2025.1.22) 리베르타드 2-1 올림피아(위키백과 경기 상자: 62분 골)"),
]
# 골·도움 행: (유형, 날짜, 분, 표시 분, 앞선 우리, 상대, ko, pk, et, 득점자(도움일 때), tie, Elo 지정 단계)
EXTRA_E = [
    ("g", "1998-10-27", 65, 0, 2, 1, 0, 0, 0, 0, [1, 0, 0, 0, 1, 0]),
    ("g", "1998-11-04", 24, 0, 0, 0, 0, 0, 0, 0, [2, 1, 4, 3, 1, 0]),
    ("g", "1998-11-04", 40, 0, 1, 0, 0, 0, 0, 0, [2, 1, 4, 3, 1, 0]),
    ("g", "2018-11-07", 57, 0, 0, 0, 1, 0, 0, 0, None),
    ("g", "2018-11-20", 83, 0, 1, 0, 1, 0, 0, 0, None),
    ("g", "2018-11-20", 93, "90+3", 2, 1, 1, 0, 0, 0, None),
    ("g", "2018-12-05", 56, 0, 1, 1, 1, 0, 0, 0, None),
    ("g", "2021-09-15", 17, 0, 1, 0, 1, 0, 0, 0, None),
    ("g", "2021-12-12", 15, 0, 0, 0, 1, 0, 0, 0, None),
    ("g", "2022-09-07", 48, "45+3", 3, 0, 1, 0, 0, 0, None),
    ("g", "2024-10-02", 76, 0, 1, 0, 1, 0, 0, 0, None),
    ("g", "2024-11-13", 92, "90+2", 1, 0, 1, 0, 0, 0, None),
    ("g", "2025-01-22", 62, 0, 1, 0, 1, 0, 0, 0, None),
    # FotMob에만 있는 도움: ESPN 문자중계 'Assisted by Roque Santa Cruz with a headed pass'·말라가 구단 경기 기사('an assist by a Santa Cruz header')
    ("a", "2016-04-20", 91, "90+1", 0, 1, 0, 0, 0, "Federico Ricca", None),
]
EXTRA_M_DATES = {m[0] for m in EXTRA_M}

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), MIN_FIX.get(g["gameId"], int(g["playedMinutes"] or 0))])
for d, o, c, mi, est, _src in EXTRA_M:
    M.append([d, o, c, mi, 1] if est else [d, o, c, mi])
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
        if f["santacruz_assist"] == "1" and f["pen_shootout_event"] != "True" and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])): return True
    return False

# 2014.8 이후 Transfermarkt에만 있는 일반 유형 도움(FotMob 이벤트에 도움 선수 없음): 다른 독립 출처 2곳을 찾지 못한 것은 뺌(judgments.md 4절)
A_CHECK = {
 "2526544|9": (False, "2015.1.10 리가MX 파추카전 9분 조아우 로하스 골: ESPN 문자중계(옵타)는 'Assisted by Roque Santa Cruz with a cross'지만 밀레니오·메디오티엠포 경기 기록도 같은 옵타 자료이고 경기 기사(엘 우니베르살)는 도움을 적지 않음 — 독립 출처 1곳뿐"),
 "3553444|14": (False, "2021.4.20 리베르타도레스 타치라전 14분 라몬 소사 골: ESPN·스포츠몰 문자중계(같은 옵타 자료)만 도움으로 적고 라 나시온 경기 기사는 소사 단독 돌파로 씀 — 독립 출처 1곳뿐"),
}
A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도('Penalty: Fouled player')"
    if t.startswith("Handball"): return "상대 핸드볼 PK"
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
    why = "Transfermarkt에만 있음(FotMob 이벤트에 도움 선수 없음, 파라과이 리그 경기는 ESPN 자료에도 도움 없음) — 다른 독립 출처 2곳 확인 못 함"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "뺌: " + why))
    return why

# 몰수: 2020.2.8 아페르투라 과라니-올림피아(경기장 4-2 과라니) — APF 징계재판소가 외국인 선수 규정 위반으로 올림피아 3-0 승으로 바꾸고
# 과라니 골은 득실에서 지우며 올림피아에는 득점자 없는 3골을 줌(울티마 오라 'Olimpia obtiene los puntos') → 87분 골 제외, 출전 유지
FORFEIT_GOAL = {("3358834", "87")}

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
        if e["scorer_id"] == ME and e["assist_id"] == ME: judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], "본인 골의 본인 도움"))
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e, ldate(g), gid)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if sd != side: sys.exit("도움 편 이상 " + gid)
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            if (gid, e["minute"]) in FORFEIT_GOAL:
                judg.append(("골 제외", ldate(g), opp(g), e["minute"], "몰수 경기(APF가 경기장 골 무효, 올림피아 3-0 승)")); continue
            pk = 1 if e["penalty"] == "1" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["santacruz_assist"] == "1" and f["pen_shootout_event"] != "True":
            if not any(e["assist_id"] == ME and e["scorer_id"] != ME and (fm_min_match(f, e["minute"]) or same_scorer(f["scorer"], e["scorer"])) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, int(f["time"]) + int(f["overloadTime"] or 0), f["scorer"]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    exp = int(g["goals"] or 0) - sum(1 for (x, _m) in FORFEIT_GOAL if x == gid)
    if cnt_[(gid, "g")] != exp: sys.exit("골 수 불일치 " + gid)

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
    if b in ("hon.js", "clubcolors.js", "finals.js", "rsc.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
PAR = {}   # 이번 회차 병렬 판정(읽기만)
for slug in ("adebayor", "robbiekeane", "seydoukeita", "jemaa"):
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
    if "순위 없음" in lv.split(" (")[0]:   # 순위를 못 찾은 하부 리그: 그 단계 기준점
        mm = re.match(r"^(\S+) (\d)부 (\d{4})", lv)
        return int(round(_LRA["base"](_LRA["KO"][mm.group(1)], int(mm.group(2)), int(mm.group(3)), True)))
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

WIKI = collections.defaultdict(dict)
for r in rd("ranks_wiki_tables.csv"):
    WIKI[(r["file"], r["headings"])][key(r["team"])] = (int(r["rank"]), int(r["teams"]), r["team"])

# 파라과이: TM 이름 → 위키백과 표 이름
PYN = {"Club Nacional Asunción": "Nacional", "Independiente FBC": "Independiente", "CA 3 de Febrero": "3 de Febrero", "Deportivo Capiatá": "Deportivo Capiatá",
       "Club Guaraní": "Guaraní", "Club Sol de América": "Sol de América", "Sportivo Luqueño": "Sportivo Luqueño", "Club Libertad Asunción": "Libertad",
       "CD Santaní": "Deportivo Santaní", "Club Sportivo San Lorenzo": "San Lorenzo", "Club Cerro Porteño": "Cerro Porteño", "River Plate Asunción": "River Plate",
       "Club General Díaz de Luque": "General Díaz", "Club 12 de Octubre de Itauguá": "12 de Octubre", "Club Olimpia": "Olimpia", "Sportivo Ameliano": "Sportivo Ameliano",
       "Club General Caballero (JLM)": "General Caballero", "Guaireña FC": "Guaireña", "Resistencia Sport Club": "Resistencia", "Recoleta FC": "Recoleta",
       "Atlético Tembetary": "Tembetary", "Club Sportivo Trinidense": "Sportivo Trinidense"}
def py_table(y, st):
    f = f"en_{y}_APF_División_de_Honor.txt" if y <= 2023 else f"en_{y}_Copa_de_Primera.txt"
    if y == 1999 and st == "A": return ("en_1999_in_Paraguayan_football.txt", "[[Liga Paraguaya: Primera División|First division]] results / Torneo Apertura")
    if st == "A": return (f, "Torneo Apertura / Standings")
    if st == "C": return (f, "First stage / Standings" if y == 2020 else "Torneo Clausura / Standings")
    for h in ("Top goalscorers / Aggregate table", "Top scorers / Aggregate table"):
        if (f, h) in WIKI: return (f, h)
def py_rank(o, y, st):
    t = WIKI[py_table(y, st)]
    nm = PYN.get(o, o)
    hits = [v for k, v in t.items() if v[2] == nm or (v[2].startswith(nm) and nm in ("General Caballero",))]
    if len(hits) != 1: sys.exit(f"파라과이 순위 못 찾음 {o} {y} {st} {hits}")
    return hits[0][:2]
def py_label(o, d, st):
    y = int(d[:4])
    r, n = py_rank(o, y, st)
    lg = "APF División de Honor" if y <= 2023 else "Copa de Primera"
    if st == "Y": return f"파라과이 1부 {y} {r}위/{n}팀 (Paraguayan Primera División, 연간 합산 순위)"
    sk = "아페르투라" if st == "A" else "클라우수라"
    if y == 1999: return f"파라과이 1부 1999 아페르투라 {r}위/{n}팀 (Torneo Apertura 1999 1단계 리그, 경기 날짜에 진행 중이던 단계 순위)"
    if y == 2020 and st == "C": return f"파라과이 1부 2020 클라우수라 {r}위/{n}팀 ({lg} 클라우수라 2020 1단계(단일 리그) 순위, 경기 날짜에 진행 중이던 단계)"
    if y == 2026 and st == "C": return f"파라과이 1부 2026 클라우수라 {r}위/{n}팀 ({lg} 클라우수라 2026, 2026년 11월 25일 현재 순위)"
    return f"파라과이 1부 {y} {sk} {r}위/{n}팀 ({lg} {sk} {y}, 경기 날짜에 진행 중이던 단계 순위)"

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

def season(d, club=None):
    y = int(d[:4]); m = int(d[5:7]); dd = int(d[8:10])
    if club == "baysc": s_ = y if (m, dd) >= (7, 10) else y - 1
    else: s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"

MAN = []   # 순위표 밖·직접 정한 상대: (key, 날짜 시작, 날짜 끝, lv)
def man(o, d, lv, d2=None): MAN.append((key(o), d, d2 or d, lv))
def man_get(o, d):
    for k_, a_, b_, lv_ in MAN:
        if k_ == key(o) and a_ <= d <= b_: return lv_
    return None
man("1.FSV Mainz 05", "1999-12-22", "2. 분데스리가 1999-00 9위/18팀")
man("SC Paderborn 07", "2001-08-27", "독일 3부 2001-02 14위/18팀 (Regionalliga Nord, 리그 수준 추정)")
man("Myllykosken Pallo -47", "2007-08-16", "핀란드 1부 2007 5위/14팀 (Veikkausliiga)")
man("CP Cacereño", "2012-10-31", "스페인 3부 2012-13 12위/20팀 (Segunda División B Grupo IV, 리그 수준 추정)")
man("CD Mirandés", "2015-12-03", "세군다 2015-16 15위/22팀")
man("Tigres UANL", "2015-04-11", "리가MX 클라우수라 2015 1위/18팀 (경기 날짜에 진행 중이던 단계의 정규리그 순위)")
man("UNAM Pumas", "2015-05-03", "리가MX 클라우수라 2015 13위/18팀 (경기 날짜에 진행 중이던 단계의 정규리그 순위)")
man("Independiente del Valle", "2017-02-09", "에콰도르 1부 2017 4위/12팀 (감점 전 순위; Ecuadorian Serie A, 연간 합산 순위)")
man("Junior FC", "2018-02-01", "콜롬비아 1부 2017 1위/20팀 (Torneo Finalización 2017 1단계, 2018 리그 개막 전 경기라 직전에 끝난 단계 순위)")
man("Club Sporting Cristal", "2019-04-04", "페루 1부 2019 2위/18팀 (Liga 1 Torneo Apertura 2019, 경기 날짜에 진행 중이던 단계 순위)")
man("Universidad de Concepción", "2019-04-23", "칠레 1부 2019 16위/16팀 (Campeonato Nacional, 10월 중단 뒤 확정된 최종 순위)")
man("Club Always Ready", "2021-04-28", "볼리비아 1부 2021 2위/16팀 (FBF División Profesional, 연간 합산 순위)")
man("Club The Strongest", "2022-05-26", "볼리비아 1부 2022 2위/8팀 (FBF División Profesional 아페르투라 2022 1단계 A조, 경기 날짜에 진행 중이던 단계 순위)")
man("Deportivo Táchira", "2024-05-07", "베네수엘라 1부 2024 9위/14팀 (Liga FUTVE 아페르투라 2024 1단계, 경기 날짜에 진행 중이던 단계 순위)")
man("Club Tijuana", "2015-03-21", "리가MX 클라우수라 2015 11위/18팀")
man("Club Athletico Paranaense", "2022-07-05", "브라질 세리에 A 2022 6위/20팀")
man("CA Vélez Sarsfield", "1998-10-27", "아르헨티나 1부 아페르투라 1998 11위/20팀", "1998-11-04")
man("Club Cristóbal Colón (JAS)", "2021-09-15", "파라과이 3부 2021 순위 없음 (Primera División B, 리그 수준 추정)")
man("Encarnación FC", "2024-10-02", "파라과이 2부 2024 순위 없음 (División Intermedia, 리그 수준 추정)")
# 파라과이 팀: 비리그 경기의 단계
PY_STAGE = {"1999-02-24": "A", "2018-11-07": "C", "2018-11-20": "C", "2018-12-05": "C", "2021-12-12": "Y", "2022-09-07": "C", "2024-11-13": "C", "2025-01-22": "Y2024"}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def table_hit(o, ks):
    for s in ks:
        if (key(o), s) in TABLE:
            return collections.Counter(TABLE[(key(o), s)]).most_common(1)[0][0], s
    return None
def opp_elo(o, d, cid, club):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    lv = None
    if o in PYN and o != "Club Olimpia" or (o == "Club Olimpia" and club in ("libsc", "nacsc")):
        st = {"PR1A": "A", "PR1C": "C", "PR1P": "C"}.get(cid) or PY_STAGE.get(d)
        if st == "Y2024": lv = py_label(o, "2024-12-31", "Y")
        elif st: lv = py_label(o, d, st)
    if not lv: lv = man_get(o, d)
    if lv:
        h = table_hit(o, [stage_key(lv)])
        if h:
            (e, lv2), s = h; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv2, s)
            if "순위 없음" not in lv2 and _LRA["parse"](lv2, d) and lv_value(lv2, d, o) != e: TABLE_DIFF.append((o, s, e, lv2, lv_value(lv2, d, o)))
            return e, lv2
        e = lv_value(lv, d, o); ELO_SRC["순위 라벨(새 팀×시즌)"] += 1
        ELO_LOG[(o, d)] = ("label", e, lv); NEW_TS[(o, d)] = (e, lv); return e, lv
    h = table_hit(o, [season(d, club), d[:4]])
    if h:
        (e, lv), s = h
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
        p = _LRA["parse"](lv, d)
        if p and lv_value(lv, d, o) != e: TABLE_DIFF.append((o, s, e, lv, lv_value(lv, d, o)))
        return e, lv
    MISS.append((o, d, cid)); return 0, "?"

# ---------------------------------------------------------------- 클럽
CLUBS = [("olisc", "1999-07-01"), ("baysc", "2007-07-28"), ("blbsc", "2009-07-01"), ("mcisc", "2011-01-14"), ("blbsc", "2011-08-30"),
         ("betsc", "2012-08-31"), ("malsc", "2015-01-02"), ("czsc", "2015-08-26"), ("malsc", "2016-07-01"), ("olisc", "2022-01-01"),
         ("libsc", "2026-01-01"), ("nacsc", None)]
TM_CLUB = {"629": "olisc", "27": "baysc", "164": "blbsc", "281": "mcisc", "150": "betsc", "1084": "malsc", "3711": "czsc", "9875": "libsc", "7098": "nacsc"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["clubId"])

E = []
GID_BY_DATE = {}
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, club_of(d))
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and g["addition"] == "n.V." and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
MD = {m[0]: m for m in M}
for typ, d, mi, dm, gf, ga, ko, pk, et, note, tie in EXTRA_E:
    m = MD[d]; o = m[1]
    elo, lv = opp_elo(o, d, "X", club_of(d))
    row = [typ, o, elo, m[2], mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

# ---------------------------------------------------------------- 승점 표 map 줄(elo/league_points_other.json) 계산
def tnorm(x): return norm(re.sub(r"\(.*?\)", " ", x))
def nm_cands(o): return [o] + ([PYN[o]] if o in PYN else [])
def row_of(rows, o, rk):
    def sc1(nm, t):
        a, b = set(tnorm(nm).split()), set(tnorm(t).split())
        if b and b <= a: return 1.0
        x, y = tnorm(nm).split(), tnorm(t).split()
        if x and y and x[0] == y[0] and len(x[0]) >= 4: return 0.8
        return PTS.sim(tnorm(nm), tnorm(t))
    def sc(i): return max(sc1(nm, rows[i][0]) for nm in nm_cands(o) + [re.sub(r"^(CA|CD|CF|FC|Club Atlético|Club|AA|GFK|FK|CP) ", "", o)])
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
    if len(tabs) > 1:
        gm = re.search(r"Group (\d)|Grupo (I+V?|IV)|(Nord|Süd)", lv)
        cand = [i for i, t in enumerate(tabs) if ("Group 4" in t["name"] and "IV" in lv) or ("Nord" in t["name"] and "Nord" in lv) or ("Süd" in t["name"] and "Süd" in lv)]
        same_tabs = all(sorted(map(tuple, t["rows"])) == sorted(map(tuple, tabs[0]["rows"])) for t in tabs)
        if same_tabs: cand = [0]
        if len(cand) != 1: continue
        ti = cand[0]
    mp = ent.get("map", {})
    res = PTS.other_score(lv, o)
    src = ELO_LOG.get((o, r[9]), ("?",))[0]
    if res is not None and (len(tabs) == 1 or (mp.get(o) and mp.get(o)[0] == ti)): continue
    if src in ("table", "same") and res is not None: continue
    sc_, ri = row_of(tabs[ti]["rows"], o, rk)
    MAP_LINES[(mm.group(1), o)] = (tabs[ti]["rows"][ri][0], [ti, ri], rk, round(sc_, 2), "표 순위 다름" if ri + 1 != rk else "")
if "--map" in sys.argv:
    for (h, k), v in sorted(MAP_LINES.items()): print(f"{h} | {k} | {v[0]} | {v[1]} {v[4]} sim={v[3]}")
    sys.exit(0)
if "--applymap" in sys.argv:   # 스크래치 복사본 전용
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

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["santacruz_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "1")]
    if len(tm) != len(fm): FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm]))

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
def same_team(a, b, d=None):
    if key(a) == key(b): return True
    return bool(toks(a)) and toks(a) == toks(b)
CROSS = []
VRE = re.compile(r"Santa ?Cruz|산타크루스")
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for x in oe:
        if x[0] == "a" and VRE.search(str(x[13] or "")):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(산타크루스 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("산타크루스 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x[1], r[1]):
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
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 산타크루스 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5][:40]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
SHARED = collections.Counter()
for b, (oe, om) in list(OTHERS.items()) + list(PAR.items()):
    for m in M:
        if any(mm[0] == m[0] and key(mm[1]) == key(m[1]) for mm in om): SHARED[b] += 1

# ---------------------------------------------------------------- 클럽·시즌 합계
PERIODS = [("올림피아", "1998~1999", None, "1999-07-01"), ("바이에른 뮌헨", "1999~2007", "1999-07-01", "2007-07-28"),
           ("블랙번 로버스", "2007~2009", "2007-07-28", "2009-07-01"), ("맨체스터 시티", "2009~2011", "2009-07-01", "2011-01-14"),
           ("블랙번 로버스(임대)", "2011", "2011-01-14", "2011-08-30"), ("레알 베티스(임대)", "2011~2012", "2011-08-30", "2012-08-31"),
           ("말라가", "2012~2015", "2012-08-31", "2015-01-02"), ("크루스 아술", "2015", "2015-01-02", "2015-08-26"),
           ("말라가(임대)", "2015~2016", "2015-08-26", "2016-07-01"), ("올림피아", "2016~2021", "2016-07-01", "2022-01-01"),
           ("리베르타드", "2022~2025", "2022-01-01", "2026-01-01"), ("나시오날", "2026~", "2026-01-01", None)]
def per(lo, hi):
    inr = lambda d: (lo is None or d >= lo) and (hi is None or d < hi)
    return [sum(1 for m in M if inr(m[0])), sum(1 for r in E if r[0] == "g" and inr(r[9])),
            sum(1 for r in E if r[0] == "a" and inr(r[9])), sum(m[3] for m in M if inr(m[0]))]
ST = [(n, y, per(lo, hi)) for n, y, lo, hi in PERIODS]
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NEST = sum(1 for m in M if len(m) > 4)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
def d_(x): y, m, d = x.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
if "--stat" in sys.argv:
    for v in ST: print(v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), "TM_A", TM_A, "est", NEST)
    for j in judg: print(j)
    for a in A_STATUS:
        if not a[4].startswith("2014.8 이전"): print(a)
    print("FM only", FM_ONLY)
    for c in CROSS: print(c)
    print("FM", FM_CMP)
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF); print("MAPNEED", sorted(set(MAPNEED))); print("SHARED", SHARED.most_common())
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_santacruz.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "elk", "elq", "cwc", "clg", "cl16", "mlp", "csa", "lib"]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const RSC_E={J(E)};\nconst RSC_M={J(M)};\nconst RSC_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "extra_games": EXTRA_M,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()}, "map_need": sorted(set(MAPNEED)),
               "table_label_diffs": TABLE_DIFF, "map_lines": [[h, k, v[0], v[1]] for (h, k), v in sorted(MAP_LINES.items())], "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for v in ST: print(" ", v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
