#!/usr/bin/env python3
"""더글라스 코스타 (Douglas Costa de Souza, Transfermarkt 75615): raw/ -> douglascosta.json + players/douglascosta/dgc.js (판정 근거는 judgments.md)

  python3 players/douglascosta/build_douglascosta.py [--out <data 폴더>]   # 파일 쓰기(기본 players/douglascosta/dgc.js; 스크래치 복사본 검증 때 --out <복사본>/src/data)
  python3 players/douglascosta/build_douglascosta.py --debug               # Elo 출처 로그
  python3 players/douglascosta/build_douglascosta.py --stat                # 요약·판정·동료 대조
  python3 players/douglascosta/build_douglascosta.py --ties                # 합산 행

요렌테·클라우디오 로페스 build(같은 수집 형식)를 바탕으로 함. 접두어 DGC(DCO는 디에구 코스타 dco.js가 이미 씀).
상대 Elo(v1.226): 같은 경기 다른 선수 자료 → Elo 통합표(같은 팀·시즌) → 출처로 확인한 순위로 라벨을 만들고
tools/league_rank_apply.py 의 value()로 값을 정함(직접 숫자를 넣지 않음). 스크래치 복사본에서는 SOC_ROOT=<복사본>.
보조: assist_checks.py(2014.8 이후 단일 출처 도움 웹 확인), man_elo.py(순위표 밖 상대 라벨), note_douglascosta.py(설명).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime, io, contextlib, gzip

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "dgc.js")
OUT_JSON = os.path.join(HERE, "douglascosta.json")
ME = "75615"
ME_KO = "더글라스 코스타"
PFX = "DGC"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# 키에보 베로나 2025-26(세리에 D 지로네 B, 4부 아마추어 LND) = 비프로 리그 시즌 → 리그·플레이오프 13경기 모두 제외(v1.159 규칙)
EXCL_CLUB = {"862": "키에보 베로나(세리에 D)"}
GAMES_ALL = rd("tm_games.csv")
EXCLUDED = [g for g in GAMES_ALL if g["club_id"] in EXCL_CLUB]
GAMES = [g for g in GAMES_ALL if g["club_id"] not in EXCL_CLUB]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["fotmob_matchId"]}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}
ESPNG = collections.defaultdict(list)
for r in rd("espn_goals.csv"): ESPNG[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 날짜
# TM API 경기 시각(UTC)을 경기 장소 시간대로 바꾼 현지 날짜(raw tm_games.csv date_local_tz_conv).
# 다른 날짜가 있는 21경기(raw tm_date_disagreements.csv)는 모두 FotMob 경기 시각의 현지 날짜와 같음(북미 저녁 경기 5개는 TM 리포트 CET 날짜가 하루 뒤).
LD = {gid: g["date_local_tz_conv"] for gid, g in G.items()}
DATE_LOG = [(r["gameId"], r["tz_conv"], r["report_CET"], r["fotmob_conv"]) for r in rd("tm_date_disagreements.csv")]
for gid, tz, rep, fm in DATE_LOG:
    if fm and fm != LD[gid]: sys.exit("FotMob 날짜 다름 " + gid)
def ldate(g): return LD[g["gameId"]]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BRA1", "UKR1", "L1", "IT1", "MLS1", "AUS1", "UAE2"}
CUPS = {"BRC", "UKRP", "DFB", "CIT", "MLSP"}          # MLSP = 2023 US 오픈컵(TM 대회 id, 그리즈만 선례)
STATE = {"BRga", "BRRS", "RS2f", "BRCG"}               # 캄페오나투 가우슈 2009·카리오카 2024(주 선수권 = 국내컵, 파투·쿠티뉴 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("UKRS", "DFL", "SCI", "RECO"): return "df"   # 슈퍼컵류·레코파 = 국내컵 결승 비중(디에구·파푸 고메스 선례)
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"                                       # 2009-10·2013-14 32강('Second Round')
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"                                       # 조별·16강
    if cid == "CS":
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    if cid == "ACL2":
        if r.startswith("quarter"): return "ac2k"
        if r.startswith("semi"): return "ac2sf"
        if r.startswith("final"): return "ac2f"
        return "ac2"                                       # 조별·16강
    if cid == "KLUB": return "cwc"
    if cid == "USMX": return "lcg"                         # 리그스컵 2023 조별
    if cid == "POUS": return "mlp"                         # MLS 플레이오프 2022 1라운드·콘퍼런스 준결승(단판)
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
    if cid in ("CL", "EL"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid == "CIT": return (int(d < "2022-07-01"), 1)
    if cid == "UKRP": return (1, 1)                        # 우크라이나컵 두 경기 라운드(셰브첸코·파푸 고메스 선례)
    if cid == "ACL2": return (0, 1)                        # AFC 2023-24부터 원정 다득점 없음, 연장 뒤 승부차기(docs 3절)
    if cid in ("CLI", "CS", "RECO"):                       # CONMEBOL: 2005~2021 원정 다득점(결승은 연장), 2022~ 없음(디에구 선례)
        if d >= "2022-01-01": return (0, 0)
        return (0, 1) if rnd.lower().startswith("final") else (1, 0)
    if cid == "BRC": return (0, 0)                         # 코파 두 브라질 2018~ 원정 다득점 없음
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

TIES = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
def other_leg(gid):
    t = TIES.get(gid); club = G[gid]["club_id"]
    if not t: sys.exit("다른 차전 없음 " + gid)
    o = MI.get(t["other_leg_id"])
    if o and o["final"]:   # 다른 차전 리포트: 클럽 id로 편 판정
        fh, fa = map(int, o["final"].split(":"))
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    # 리포트의 '다른 차전' 스코어는 이 경기 홈 팀 기준(홈:원정) 표기
    oh, oa = map(int, t["other_leg_final"].split(":"))
    return (oh, oa) if side_of(gid) == "h" else (oa, oh)

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
    if not g["playedMinutes"]: sys.exit("출전 분 없음 " + g["gameId"])
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

# TM HTML 리포트 1029090(아스널 키이우 원정 2010.7.30)은 45+2분 코스타 골 뒤 스코어를 1:3으로 두 번 적음(오타) → tmapi 경기 JSON·FotMob의 1-2로(골 전 1-1).
SCORE_FIX = {("1029090", "45+2"): "1-2"}
for (gid_, mn_), sc in SCORE_FIX.items():
    hit_ = [e for e in EVS[gid_] if e["minute"] == mn_]
    if len(hit_) != 1: sys.exit("스코어 고침 대상 없음 " + gid_)
    hit_[0]["score_home_away_after"] = sc

A_CHECK = {}; ADD_A = []
def a_key(gid, minute): return f"{gid}|{minute}"
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())   # A_CHECK·ADD_A(근거 포함)

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    return any(f["cl_assist"] == "1" and fm_min_match(f, e["minute"]) for f in FME.get(gid, []))
def fm_pm_assists(gid):
    m = FMMAP.get(gid)
    if m and m["fotmob_matchId"] in FMPM: return int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
    return None
def espn_assist(gid, e):
    a = mins(e["minute"])[0]
    for r in ESPNG.get(gid, []):
        try: c = sum(int(x) for x in re.findall(r"\d+", r["clock"]))
        except ValueError: continue
        if abs(c - a) <= 2 and "Douglas Costa" in (r["assisted_by"] + r["participant2"]): return True
    return False

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
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    k = a_key(gid, e["minute"])
    if d < GAP:
        if k in A_CHECK and not A_CHECK[k][0]: return A_CHECK[k][1]
        return None
    if fm_assist(gid, e):
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트" + (" +ESPN" if espn_assist(gid, e) else ""))); return None
    pm = fm_pm_assists(gid)
    if pm and pm > fm_confirmed(gid) and k not in A_CHECK:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], f"TM+FotMob 선수 경기 목록(도움 {pm})" + (" +ESPN" if espn_assist(gid, e) else ""))); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "2014.8 이후 단일 출처(다른 출처 2곳 확인 못 함)"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], f"판정 없음 FMpm={fm_pm_assists(gid)} ESPN={espn_assist(gid, e)}"))
    return "2014.8 이후 단일 출처(판정 없음)"

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid)
    prev = (0, 0)
    for e in EVS[gid]:
        sd = e["side"][0]
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = (h - 1, a) if sd == "h" else (h, a - 1)
        if before != prev and not ((gid, e["minute"]) in SCORE_FIX): judg.append(("스코어 순서 확인", gid, e["minute"], prev, before))
        prev = (h, a)
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
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
            if e["penalty"] == "1" and not pk and e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

# FotMob에만 있는 도움 중 다른 출처 2곳으로 확인한 것(assist_checks.py ADD_A): (gid, 분 문자열, gf, ga, 득점자, 근거)
for gid, mstr, gf, ga, scorer, why in ADD_A:
    mi, dm = mins(mstr)
    raw_rows.append(("a", gid, mi, dm, gf, ga, 0, scorer, "added"))
    judg.append(("도움 추가(FotMob 단독 + 다른 출처 2곳)", ldate(G[gid]), opp(G[gid]), mstr, scorer, why))
    A_STATUS.append((ldate(G[gid]), gid, mstr, scorer, "넣음(FotMob 단독): " + why))
FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["cl_assist"] == "1" and f["pen_shootout_event"] != "True":
            mi = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(e["assist_id"] == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, mi, f["scorer"], any(x[0] == gid for x in ADD_A)))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G or not MI.get(gid, {}).get("final"): continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":"))
    if (h, a) != (fh, fa) and G[gid]["gameState"] != "penalty_shootout": SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))

# FotMob 골 대조(2010-11 이후 FotMob 이벤트가 있는 경기)
FM_CMP = []
for gid in EVS:
    if gid not in G or gid not in FME: continue
    tm = [e for e in EVS[gid] if e["scorer_id"] == ME and not is_og(e)]
    fm = [f for f in FME[gid] if f["cl_scorer"] == "1" and f["pen_shootout_event"] != "True"]
    if len(tm) != len(fm): FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(tm, fm):
        if not fm_min_match(f, t["minute"], 1): FM_CMP.append(("시각 다름", gid, ldate(G[gid]), t["minute"], f["time"], f["overloadTime"]))
        if (t["goal_desc"] == "Penalty") != ("penalty" in (f["goalDescriptionKey"] or "").lower() and "rebound" not in (f["goalDescriptionKey"] or "").lower()):
            FM_CMP.append(("PK 다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["goalDescriptionKey"]))

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
    if b in ("hon.js", "clubcolors.js", "finals.js", "dgc.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "cd", "ud", "sv", "as", "ss", "vfl", "vfb", "tsg",
        "athletic", "wanderers", "milan", "inter", "madrid", "paulo", "ca", "deportivo", "universidad", "san", "santa", "fk", "bv", "borussia", "werder",
        "bayer", "eintracht", "hertha", "los", "angeles", "new", "york", "kyiv", "donetsk", "dynamo", "metalurg", "metalist", "red", "bull", "hellas",
        "melbourne", "sydney", "western", "al", "arabi", "olympique", "lyonnais", "saint", "germain", "paris", "hotspur", "manchester", "chelsea",
        "arsenal", "sevilla", "atletico", "porto", "benfica", "lisbon", "zorya", "karpaty", "fluminense", "gremio", "flamengo", "internacional",
        "botafogo", "vasco", "gama", "mineiro", "paranaense", "goianiense", "recife", "bahia", "fortaleza", "palmeiras", "corinthians", "santos",
        "cruzeiro", "vitoria", "juventus", "roma", "lazio", "napoli", "genoa", "torino", "sampdoria", "atalanta", "udinese", "bologna", "verona",
        "fiorentina", "sassuolo", "cagliari", "parma", "spal", "chievo", "crotone", "benevento", "frosinone", "empoli", "lecce", "brescia",
        "hoffenheim", "augsburg", "mainz", "wolfsburg", "schalke", "leverkusen", "hamburger", "hannover", "ingolstadt", "darmstadt", "koln", "freiburg",
        "stuttgart", "frankfurt", "gladbach", "leipzig", "rb", "fsv", "sc", "fortuna", "dusseldorf", "union", "berlin", "arminia", "bielefeld"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위 → 라벨 → 값(tools/league_rank_apply.py)
_LRA = {"__file__": os.path.join(ROOT, "tools", "league_rank_apply.py"), "__name__": "lra"}
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA["__file__"], encoding="utf-8").read().split("if __name__ == '__main__':")[0], "lra", "exec"), _LRA)
sys.argv = _argv
def lv_value(lv, d):
    m_ = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv)
    if m_:
        cal = m_.group(4) is None; y = int(m_.group(3)) + (0 if cal else 1)
        return int(round(_LRA["base"](_LRA["KO"][m_.group(1)], int(m_.group(2)), y, cal)))
    p = _LRA["parse"](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA["value"](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    return v

# 상대 시즌: 우크라이나 대회(리그·컵·슈퍼컵)는 7월 개막이라 7월 경기가 새 시즌. 브라질·MLS·남미 대회는 달력 연도.
def eu(d, jul=False):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= (7 if jul else 8) else y - 1
    return f"{s}-{str(s + 1)[2:]}"
def seasons_for(cid, d):
    if cid in ("UKR1", "UKRP", "UKRS"): return [eu(d, True)]
    if cid in ("BRA1", "BRC", "CLI", "CS", "RECO", "MLS1", "MLSP", "POUS", "USMX") or cid in STATE: return [d[:4], eu(d)]
    if cid == "ACL2": return [eu(d), d[:4], str(int(d[:4]) - 1)]
    return [eu(d), d[:4]]

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[0].startswith("#"): continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1])
def rank_label(cid, s, k):
    if cid == "UKR1" and (cid, s) in RANKS and k in RANKS[(cid, s)]:
        r, n, nm, _ = RANKS[(cid, s)][k]; return f"우크라이나 1부 {s} {r}위/{n}팀 (Ukrainian Premier League)"
    if cid == "BRA1" and (cid, s) in RANKS and k in RANKS[(cid, s)]:
        r, n, nm, _ = RANKS[(cid, s)][k]; return f"브라질 세리에 A {s} {r}위/{n}팀"
    if cid == "AUS1" and (cid, s) in RANKS and k in RANKS[(cid, s)]:
        r, n, nm, _ = RANKS[(cid, s)][k]; return f"호주 1부 {s} {r}위/{n}팀 (A-League Men)"
    return None

MAN = {}   # (key, 시즌) -> lv
def man(o, s, lv): MAN[(key(o), s)] = lv
MANV = {}  # 리그 모형 밖 나라(순위 도구가 읽지 못하는 라벨): (key, 시즌) -> (lv, 값)
def manv(o, s, lv, v): MANV[(key(o), s)] = (lv, v)
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
RANK_CID = {"UKRP": "UKR1", "UKRS": "UKR1", "BRC": "BRA1", "ACL2": "AUS1", "AUS1": "AUS1", "UKR1": "UKR1", "BRA1": "BRA1"}

def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o); seasons = seasons_for(cid, d)
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            p = _LRA["parse"](lv, d)
            if p and _LRA["value"](*p) not in (None, e): TABLE_DIFF.append((o, s, e, lv, _LRA["value"](*p)))
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for s in seasons:
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d)
            ELO_SRC["순위 라벨(출처 확인)"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    for s in seasons:
        if (k, s) in MANV:
            lv, e = MANV[(k, s)]
            ELO_SRC["직접 추정(모형 밖 리그)"] += 1; ELO_LOG[(o, d)] = ("manv", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    for s in seasons:
        lv = rank_label(RANK_CID.get(cid, cid), s, k)
        if lv:
            e = lv_value(lv, d); ELO_SRC["순위표 → 라벨"] += 1; ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
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
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
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
DC_RE = r"Douglas Costa|D\. Costa"
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(DC_RE, str(x[13] or "")):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(코스타 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and key(x[1]) == key(r[1])]
            if hit: CROSS.append(("코스타 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and key(x[1]) == key(r[1])]
            if hit: CROSS.append(("타인 도움 행이 코스타 골과 같은 시각", b, r[9], r[4], hit[0][13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and key(x[1]) == key(r[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and key(mm[1]) == key(m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
# 뺀 코스타 도움에 해당하는 동료 골 행(정보)
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and key(x[1]) == key(j[2]):
                    CROSS.append(("TM 코스타 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("gredgc", "2010-01-01"), ("shadgc", "2015-07-01"), ("baydgc", "2017-07-12"), ("juvdgc", "2020-10-04"), ("baydgc", "2021-05-21"),
         ("gredgc", "2022-02-10"), ("gladgc", "2024-01-28"), ("fludgc", "2024-08-26"), ("syddgc", "2026-07-13"), ("ittdgc", None)]
TM_CLUB = {"210": "gredgc", "660": "shadgc", "27": "baydgc", "506": "juvdgc", "1061": "gladgc", "2462": "fludgc", "8054": "syddgc", "93797": "ittdgc"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in ("gredgc", "gladgc", "fludgc"): return str(y)
    s_ = y if m >= (7 if club == "shadgc" else 8) else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("그레미우 2008~2009", "2010-01-01"), ("샤흐타르 도네츠크", "2015-07-01"), ("바이에른 뮌헨 2015~2017", "2017-07-12"),
          ("유벤투스", "2020-10-04"), ("바이에른 뮌헨 2020~2021(임대)", "2021-05-21"), ("그레미우 2021(임대)", "2022-02-10"),
          ("LA 갤럭시", "2024-01-28"), ("플루미넨시", "2024-08-26"), ("시드니 FC", "2026-07-13"), ("알이티파크", "9999")]
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
EXJ = [j for j in judg if j[0] == "도움 제외"]
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
EXC_N = (len(EXCLUDED), sum(int(g["goals"] or 0) for g in EXCLUDED), sum(int(g["assists"] or 0) for g in EXCLUDED), sum(int(g["playedMinutes"] or 0) for g in EXCLUDED))
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A, EXC_N)
    for j in judg: print(j)
    for a in A_STATUS: print("A", a)
    print("FM_ONLY", FM_ONLY)
    print("FM_CMP", FM_CMP)
    for c in CROSS: print(c)
    print("score mismatch", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("TABLE_DIFF", TABLE_DIFF)
    for x in sorted(NEW_TS.items()): print("NEW", x)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_douglascosta.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl", "ac2", "mlp", "lcg", "clg", "cl16"]:
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
        if b[4] > a[4] and b[5] < a[5] + 1: problems.append(("스코어 역순", d, a[4], b[4]))
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
    js = f"const {PFX}_E={J(E)};\nconst {PFX}_M={J(M)};\nconst {PFX}_NOTE={J(NOTE)};\n"
    open(OUT_JS, "w", encoding="utf-8").write(js)
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "fotmob_goal_diffs": FM_CMP, "cross_check": CROSS, "elo_sources": ELO_SRC, "date_disagreements": DATE_LOG,
               "excluded_games": [[ldate(g) if g["gameId"] in G else g["date_local_tz_conv"], g["opponent"], g["competitionId"], g["playedMinutes"], g["goals"], g["assists"]] for g in EXCLUDED],
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
