#!/usr/bin/env python3
"""카를로스 테베스 (Transfermarkt 4276): raw/ -> tevez.json + src/data/tvz.js (판정 근거는 judgments.md)

  python3 players/tevez/build_tevez.py            # 파일 쓰기
  python3 players/tevez/build_tevez.py --debug    # Elo 출처 로그만 출력
  python3 players/tevez/build_tevez.py --stat     # 요약·판정·동료 대조
  python3 players/tevez/build_tevez.py --ties     # 합산 행

리켈메 build 스크립트(players/riquelme)를 바탕으로 함. 입력: raw/tm_games.csv(출전·분·날짜 후보), raw/tm_events.csv(리포트 골 목록),
raw/tm_match_info.csv(리포트 머리·다른 차전), raw/fotmob_tm_map.csv(FotMob 경기 시각), raw/fotmob_events.csv·fotmob_playerMatches.csv(도움 대조),
raw/espn_tevez_check.csv(ESPN 도움 대조), raw/ranks.txt(순위표), elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료).
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "tvz.js")
OUT_JSON = os.path.join(HERE, "tevez.json")
ME = "4276"
ME_KO = "카를로스 테베스"

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
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["status"] == "OK"}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}
ESPN = collections.defaultdict(list)
for r in rd("espn_tevez_check.csv"): ESPN[r["gameId"]].append(r)

# ---------------------------------------------------------------- 날짜
# 남미(보카·코린치안스): TM 리포트·일정 날짜는 중부 유럽 날짜라 저녁 경기가 하루 밀림 → 경기 시각(UTC)을 경기장 시간대로 바꾼 날짜.
#   FotMob 경기 시각이 있으면(2010-11 이후) 그것을 씀(TM API 시각이 하루 이상 틀린 코파 아르헨티나 2016 경기가 있음; ESPN 일정과 같음).
#   TM 시각이 12:00/13:00 UTC 정각이면 시각 미상 자리값 → 일정 날짜.
# 유럽·중국·일본 경기: TM 날짜와 바꾼 날짜가 모두 같음(빌드에서 확인).
DATE_FIX = {
    "3733907": "2016-06-29",   # 코파 아르헨티나 2015-16 64강 귀에메스전: TM 2016.7.28(시각 7.28 23:10Z)은 틀림. ESPN 경기 452674(2016-06-30T00:10Z = 6.29 21:10 현지, 산후안), diariouno 2016.6.29 기사
    "2530909": "2006-08-16",   # 브라질 세리에 A 2006 플루미넨시 원정: TM 시각 8.15 23:00Z는 틀림. ESPN 일정 2006-08-17T01:00Z(= 8.16 22:00 현지), TM 리포트·일정 8.16
}
DATE_LOG = []
def _conv(utc, tz):
    return datetime.datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(ZoneInfo(tz)).date().isoformat()
def _ldate(g):
    gid = g["gameId"]
    if gid in DATE_FIX: return DATE_FIX[gid], "fix"
    sched = g["date_local_schedule"]
    if g["club_id"] not in ("189", "199"):
        conv = _conv(g["date_utc"], g["tz_used"])
        if conv != sched: sys.exit("유럽·중국 날짜 불일치 " + gid)
        return sched, "tm"
    if gid in FMMAP: return _conv(FMMAP[gid]["fotmob_utc"], g["tz_used"]), "fm"
    u = datetime.datetime.fromisoformat(g["date_utc"])
    if (u.hour, u.minute) in ((12, 0), (13, 0)): return sched, "sched"
    return g["date_local_tz_conv"], "conv"
LD = {}
for gid, g in G.items():
    LD[gid], how = _ldate(g)
    if LD[gid] != g["date_local_schedule"]: DATE_LOG.append((gid, g["date_local_schedule"], LD[gid], how, g["opponent"]))
def ldate(g): return LD[g["gameId"]]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ARG1", "ARGC", "AR1N", "BRA1", "GB1", "IT1", "CSL", "CDLP"}   # CDLP = 코파 마라도나 2020·코파 데 라 리가 2021 조별(1부 전 팀 리그식)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "CDCA":   # 코파 마라도나·코파 데 라 리가 결선: 2020 결선 조(Fase Campeón)는 리그식, 8강 이후는 국내컵 단계
        if r.startswith("group"): return "lg"
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "BCP1": return "dc"   # 캄페오나투 파울리스타(주 선수권, 네이마르·루카스 선례)
    if cid in ("FAC", "CGB", "CIT", "ARCA", "BRC", "CHFA", "ARLC"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth"): return "dk"
        return "dc"
    if cid in ("GBCS", "SCI", "SCAG", "USC", "RECO"): return "df"   # 슈퍼컵류(레코파 = 리켈메 선례)
    if cid in ("WEPO", "KLUB"): return "cwc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "ELQ": return "elq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"
        sys.exit("UEFA 라운드 " + rnd)
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 32강(Second Round)·16강·8강
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"
    if cid == "CS":
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    if cid == "ACLQ": return "acl"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g):
    return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE or cid == "BCP1": return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    r = rnd.lower()
    if cid in ("CL", "UEFA", "EL", "ELQ", "CGB", "CIT"): return (1, 1)
    if cid == "CHFA": return (1, 1)                     # 중국 FA컵(엘 샤라위 선례)
    if cid == "CLI":
        if d < "2005-01-01": return (0, 0)              # 2004년까지 원정 다득점·연장 없이 승부차기(리켈메 선례)
        if r.startswith("final") and d >= "2008-01-01": return (0, 1)
        return (1, 0)
    if cid == "CS": return (1, 0)                       # 리켈메·팔카오 선례
    if cid == "BRC": return (1, 0)                      # 코파 두 브라질(호나우두·루카스 선례)
    if cid == "ARLC": return (0, 0)                     # 코파 데 라 수페르리가 2019: 원정 다득점 없이 승부차기(추정)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
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
    oid = MI[gid]["other_leg_id"]
    if oid in G and G[oid]["gameState"] == "penalty_shootout": sys.exit("다른 차전이 승부차기 " + gid)
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

# 2014.8 이후 도움 판정: TM + FotMob(경기 이벤트 또는 선수 경기 목록) 일치면 넣음, 아니면 다른 출처 2곳(경기 기사·문자 중계) 필요.
# 아래 표는 judgments.md 4절의 웹 검색 결과(TM 외 출처). 값: (넣음 여부, 근거)
A_CHECK = {}
def a_key(gid, minute): return f"{gid}|{minute}"
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())   # A_CHECK 채움(근거 URL 포함)

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base   # FotMob 90 = TM 90+x
def fm_assist(gid, e):
    """FotMob 이벤트에 이 골의 테베스 도움이 있나(분 ±2, 득점자 성 일치)"""
    mi = mins(e["minute"])[0]
    sur = norm(e["scorer"]).split()[-1] if e["scorer"] else ""
    for f in FME.get(gid, []):
        if f["tevez_assist"] == "1" and fm_min_match(f, e["minute"]): return True
    return False
def fm_pm_assists(gid):
    m = FMMAP.get(gid)
    if m and m["fotmob_matchId"] in FMPM: return int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
    return None
def espn_assist(gid, e):
    for r in ESPN.get(gid, []):
        if r["role"] != "goal" and r["minute_tm"] == e["minute"] and r["espn_names_tevez"] == "1": return True
    return False

def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

A_STATUS = []   # 2014.8 이후 도움 판정 기록
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    if d < GAP: return None
    fa, pm, es = fm_assist(gid, e), fm_pm_assists(gid), espn_assist(gid, e)
    k = a_key(gid, e["minute"])
    if fa:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if pm and pm >= 1 and k not in A_CHECK:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], f"TM+FotMob 선수 경기 목록(도움 {pm})")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "2014.8 이후 단일 출처(확인 못 함)"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], f"판정 없음 ESPN={es} FMpm={pm}"))
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
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e): sys.exit("테베스 자책골 " + gid)
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
            if e["goal_desc"] == "Penalty rebound": judg.append(("PK 리바운드 골(PK 아님)", ldate(g), opp(g), e["minute"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

# FotMob 전용 도움(TM 도움 없음): 판정 기록만(넣지 않음 — assist_checks.py)
FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["tevez_assist"] == "1" and f["pen_shootout_event"] != "True":
            mi = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(e["assist_id"] == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, mi, f["scorer"]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))

# ---------------------------------------------------------------- 이름·기존 자료
ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
MANUAL_ALIAS = {"inter milan": "inter", "club atletico gimnasia y esgrima la plata": "club de gimnasia y esgrima la plata"}
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
    if b in ("hon.js", "tvz.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "paulista", "paulo", "ca", "cs", "deportivo", "deportes", "universidad", "san", "santa", "fk", "vfl", "bv",
        "racing", "arsenal", "juniors", "plate", "river", "nacional", "independiente", "estudiantes", "union", "boca", "gimnasia", "esgrima", "lorenzo", "almagro", "hotspur", "palace", "villa", "ham", "manchester", "verona", "sheffield", "bristol", "birmingham", "nottingham", "queens", "park", "west", "aston"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
SA_DOM = {"ARG1", "ARGC", "AR1N", "CDLP", "CDCA", "ARLC", "ARCA", "SCAG", "CLI", "CS", "RECO", "BRA1", "BCP1", "BRC", "CSL", "CHFA", "ACLQ"}
def same_match(o, d, cid):
    if cid in SA_DOM:   # 남미·중국 대회는 같은 이름 다른 팀이 많아 정확한 이름(별칭) 일치만
        cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    else:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)] or [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        m = re.search(r"group(\d+)", p[1])
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4], int(m.group(1)) if m else 0)

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
def half_up(x): return int(x + 0.5)
def arg_v(r, n): return half_up(1583 + 63 * curve(r, n))
CN_FIX = {4: 1526, 5: 1514, 6: 1501, 7: 1489, 10: 1458, 11: 1452, 12: 1446, 13: 1433, 14: 1422, 15: 1411, 16: 1397}   # 함식·엘 샤라위 자료

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e[12] or "")
        if m: c[int(m.group(1))][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
def mid(tab, r):
    if r in tab: return tab[r], False
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up((tab[a] + tab[b]) / 2), True

def arg_tour(lg, season):
    y0 = int(season[:4])
    if lg == "ARG1": return "아페르투라", y0
    return "클라우수라", y0 + 1

def rank_model(lg, season, v):
    r, n, nm, grp = v
    if lg in ("ARG1", "ARGC"):
        t, y = arg_tour(lg, season)
        return arg_v(r, n), f"아르헨티나 1부 {t} {y} {r}위", str(y)
    if lg == "AR1N":
        if grp: return arg_v(r, n), f"아르헨티나 1부 {season} {grp}조 {r}위/{n}팀", season
        return arg_v(r, n), f"아르헨티나 1부 {season} {r}위", season
    if lg == "CDLP":
        return arg_v(r, n), f"아르헨티나 리가 컵 {season} {grp}조 {r}위/{n}팀", season
    if lg == "BRA1":
        return half_up(1598 + 63 * curve(r, n)), f"브라질 세리에 A {season} {r}위", season
    if lg == "CSL":
        if r in CN_FIX: v_, how = CN_FIX[r], "같음"
        else: v_, how = round(1484 + 63 * curve(r, 16)), "같은 모형"
        return v_, f"중국 슈퍼리그 {season} {r}위 (추정, 다른 선수 자료 중국 슈퍼리그 2012 순위별 값과 {how})", season
    for code, pre in (("GB1", "프리미어리그"), ("IT1", "세리에A")):
        if lg == code:
            m = ents_map(pre, season); x, it = mid(m, r)
            if x is None: return None
            return x, f"{pre} {season} {r}위", season
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

ARG_KEYS = set()
for (lg, s), t in RANKS.items():
    if lg in ("ARG1", "ARGC", "AR1N", "CDLP"): ARG_KEYS |= set(t)
def arg_season(d):
    """아르헨티나 팀의 상대 수준 시즌(통합표 키)"""
    if d < "2016-08-01": return d[:4]
    if d < "2020-08-01": return eu(d)
    if d < "2021-02-01": return "2019-20"   # 코파 마라도나 2020(4팀 조): 직전 수페르리가 2019-20 최종 순위를 씀(추정)
    return d[:4]
CAL = {"BRA1", "BCP1", "BRC", "CSL", "CHFA", "CLI", "CS", "RECO"}
MEX_KEYS = {key("Tigres UANL")}
def seasons_for(cid, d, o):
    k = key(o)
    if k in ARG_KEYS and (cid in SA_DOM): return [arg_season(d)] if d >= "2015" else [d[:4]]
    if k in MEX_KEYS: return [eu(d)]
    if cid in CAL or cid in SA_DOM: return [d[:4]]
    return [eu(d), d[:4]]   # 달력 연도 리그 팀(말뫼 등)은 연도 키

def lg_cands(cid, d, o, sid):
    k = key(o)
    if cid in ("ARG1", "ARGC"): return [(cid, f"{sid}-{str(int(sid) + 1)[2:]}")]
    if k in ARG_KEYS and d >= "2015":
        s = arg_season(d)
        if s == "2021": return [("CDLP", "2021")]
        return [("AR1N", s)]
    if k in ARG_KEYS:   # 2001~2004 대륙 대회의 아르헨티나 상대: 그때 진행 중인 반시즌
        y = int(d[:4]); mo = int(d[5:7])
        if mo <= 7: return [("ARGC", f"{y-1}-{str(y)[2:]}")]
        return [("ARG1", f"{y}-{str(y+1)[2:]}")]
    if cid in ("BRA1", "BCP1", "BRC", "CLI", "CS"): return [("BRA1", d[:4])]
    if cid in ("CSL", "CHFA"): return [("CSL", d[:4])]
    s = eu(d)
    return [("GB1", s), ("IT1", s)]

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
ARG_USE = collections.defaultdict(set)
MAN_HIT = set()

def opp_elo(o, d, cid, sid=None):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    seasons = seasons_for(cid, d, o)
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); MAN_HIT.add((o, s, e)); return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for lg, s in lg_cands(cid, d, o, sid):
        t = RANKS.get((lg, s), {})
        if k in t:
            res = rank_model(lg, s, t[k])
            if res and res[0]:
                if lg in ("ARG1", "ARGC", "AR1N", "CDLP"): ARG_USE[(k, res[2])].add(res[:2])
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res[0], res[1]
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())   # 직접 추정(MAN) 목록

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, g["seasonId"])
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)

# 아르헨티나: 통합표 시즌 키(연도)가 같은데 대회별 값이 다르면 평균(리켈메·포를란 선례)
ARG_AVG = []
for (k, y), vs in ARG_USE.items():
    if len({v[0] for v in vs}) > 1:
        vv = sorted(vs, key=lambda v: v[1])
        avg = half_up(sum(v[0] for v in vv) / len(vv))
        lv = f"아르헨티나 1부 {y} (추정, " + "·".join(re.sub(r"^아르헨티나 1부 ", "", v[1]) for v in vv) + " 값 평균)"
        ARG_AVG.append((k, y, avg, [v[0] for v in vv]))
        for r in E:
            if key(r[1]) == k and r[12] in {v[1] for v in vv}:
                r[2], r[12] = avg, lv
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
    print("평균:", ARG_AVG)
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
    fm = [r for r in FME[gid] if r["tevez_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "penalty" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))
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
G_BYDATE = {ldate(g): g["competitionId"] for g in GAMES}
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"T[eé]vez", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(테베스 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("테베스 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) if G_BYDATE.get(r[9], "ARG1") in SA_DOM else same_team(x[1], r[1])):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm[1], m[1]) and mm[2] != m[2] and (key(mm[1]) == key(m[1]) or G_BYDATE.get(m[0], "ARG1") not in SA_DOM):
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 테베스 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("boctv", "2005-01-01", "보카 주니어스", "보카", "2001~2004"), ("cortv", "2006-08-31", "코린치안스", "코린치안스", "2005~2006"),
         ("whutv", "2007-08-10", "웨스트햄 유나이티드", "웨스트햄", "2006~2007"), ("mnutv", "2009-07-14", "맨체스터 유나이티드", "맨유", "2007~2009"),
         ("mcitv", "2013-07-01", "맨체스터 시티", "맨시티", "2009~2013"), ("juvtv", "2015-07-11", "유벤투스", "유벤투스", "2013~2015"),
         ("boctv", "2017-01-01", "보카 주니어스", "보카", "2015~2016"), ("shatv", "2018-01-06", "상하이 선화", "상하이 선화", "2017"),
         ("boctv", None, "보카 주니어스", "보카", "2018~2021")]
TM_CLUB = {"189": "boctv", "199": "cortv", "379": "whutv", "985": "mnutv", "281": "mcitv", "506": "juvtv", "3183": "shatv"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
SCAL = ("boctv", "cortv", "shatv")
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in SCAL: return str(y)
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("보카 주니어스(2001~2004)", "2005-01-01"), ("코린치안스", "2006-08-31"), ("웨스트햄", "2007-08-10"), ("맨체스터 유나이티드", "2009-07-14"),
          ("맨체스터 시티", "2013-07-01"), ("유벤투스", "2015-07-11"), ("보카 주니어스(2015~2016)", "2017-01-01"), ("상하이 선화", "2018-01-06"), ("보카 주니어스(2018~2021)", "9999")]
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
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EXJ = [j for j in judg if j[0] == "도움 제외"]
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8] and r[1] in G and ldate(G[r[1]]) < GAP)
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A, UNTYPED)
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    print("FM only", FM_ONLY)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G, FM_CMP)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("dates changed", len(DATE_LOG), collections.Counter(x[3] for x in DATE_LOG))
    for o, e, lv in MAN_USED: print("MAN", o, e, lv)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
def exl(kind):
    return ", ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]}" for j in EXJ if j[5].startswith(kind))
UNCONF = [j for j in EXJ if j[5].startswith("2014.8")]
ADDED_WEB = [a for a in A_STATUS if a[4].startswith("넣음")]
PM_ONLY = [a for a in A_STATUS if a[4].startswith("TM+FotMob 선수")]
NOTE_LINES = [
    f"카를로스 테베스(보카 주니어스·코린치안스·웨스트햄 유나이티드·맨체스터 유나이티드·맨체스터 시티·유벤투스·보카 주니어스·상하이 선화·보카 주니어스)의 클럽 공식 경기 {NG}경기({d_(first[0])} 탈레레스전 ~ {d_(last[0])} 라싱전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·아르헨티나 대표팀(A·올림픽·청소년) 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{k} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(90분 추정 없음), 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있거나 리그 밖 대회인 경기 489개; 테베스 골 수·PK 수는 선수 경기 성적과 경기마다 같음). 2010-11 이후 골 {FM_G}개({FM_N}경기)는 FotMob 경기 기록과 대조해 수·순서·PK가 모두 같음(추가시간 표기만 다름). 2008-09 이후 경기는 ESPN 경기 기록, 2005 브라질 리그는 RSSSF 경기 기록과도 대조함. 경기 수·골 수 합계는 영어·스페인어 위키백과와 같음(747경기 308골; 보카 2002-03·2003-04·2004-05 대륙 대회 경기·골의 시즌 배분과 유벤투스 2014-15 코파 이탈리아 경기 수만 위키백과와 1경기·1골씩 다름)",
    "프로 리그 규칙: 모든 소속 팀-시즌이 1부(아르헨티나 1부, 브라질 세리에 A, 프리미어리그, 세리에A, 중국 슈퍼리그)라 뺀 시즌 없음. 캄페오나투 파울리스타(상파울루 주 선수권)는 코린치안스가 1부 소속일 때의 공식 대회라 넣음",
    f"도움: 2014년 8월 이전은 Transfermarkt 경기 리포트 단일 출처(클로제·인시녜·리켈메 선례; 유형 칸이 빈 {UNTYPED}개는 일반 도움으로 셈). Transfermarkt 도움 {TM_A}개에서 PK 유도 {sum(1 for j in EXJ if j[5].startswith('PK'))}개({exl('PK')}), 슈팅 리바운드('Shot on goal') {sum(1 for j in EXJ if j[5].startswith('슈팅'))}개({exl('슈팅')}), 상대 자책골 유도 1개({exl('상대')})를 빼고, 본인 PK 골의 본인 도움 표기 2개(2007.3.17 블랙번전 71분, 2013.10.20 피오렌티나전 37분)는 도움으로 세지 않음. 2014년 8월 이후는 Transfermarkt와 FotMob(경기 이벤트 또는 선수 경기 목록)이 같은 도움만 넣고, 한쪽에만 있는 도움은 다른 출처 2곳(ESPN 문자 중계·경기 기사)이 확인한 것만 넣음: 넣은 것 {len(ADDED_WEB)}개(" + ", ".join(f"{d_(a[0])} {a[3]} {a[2]}분" for a in ADDED_WEB) + f"), FotMob 선수 경기 목록으로 확인한 것 {len(PM_ONLY)}개(" + ", ".join(f"{d_(a[0])} {a[3]} {a[2]}분" for a in PM_ONLY) + f"), 확인 못 해 뺀 것 {len(UNCONF)}개(" + ", ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]}" for j in UNCONF) + "). FotMob에만 있는 2021.4.3 데펜사 이 후스티시아전 65분 사라테 골 도움(Transfermarkt 리포트는 도움 없음, FotMob 선수 경기 목록도 도움 0)은 넣지 않음. 스페인어 위키백과·FotMob의 시즌 도움 합계는 경기별 근거가 없어 쓰지 않음",
    "골: 자책골 없음(FotMob과 대조한 2010-11 이후 경기에서 출처 간 득점자가 다른 골 없음). PK 골은 Transfermarkt 골 유형 'Penalty'(선수 경기 성적 PK 골 수, FotMob과 같음). 골 전 스코어는 리포트 골 순서대로 셈. 승부차기 경기의 Transfermarkt 경기 성적 스코어는 승부차기 골을 더한 값이라 쓰지 않음(22경기)",
    "출전 분: Transfermarkt 그대로. 연장 120분 경기: 2008 챔스 결승 첼시전·2008 커뮤니티 실드·2009 리그컵 결승·2009 FA컵 준결승 에버턴전(모두 승부차기), 2009.9.23 풀럼·2012.9.25 애스턴 빌라 리그컵, 2014 수페르코파 나폴리전(연장 107분 골, 승부차기), 2015 코파 이탈리아 결승 라치오전. 2018 리베르타도레스 결승 2차전(마드리드, 연장)은 교체 9분",
    f"날짜: 경기 현지 날짜. 유럽·중국·일본 경기는 Transfermarkt 날짜. 보카·코린치안스 경기는 Transfermarkt 일정·리포트 날짜가 중부 유럽 기준이라 경기 시각(UTC)을 경기장 시간대로 바꾼 날짜를 씀(2010-11 이후는 FotMob 경기 시각, 그 전은 Transfermarkt 시각; 저녁 경기 {len(DATE_LOG)}경기가 Transfermarkt 날짜보다 하루 앞, RSSSF 2005 브라질 리그·ESPN 일정과 같음). 시각이 비어 자리값만 있는 경기는 일정 날짜. 예외: 코파 아르헨티나 2015-16 64강 귀에메스전은 Transfermarkt가 2016.7.28로 적었으나 ESPN·현지 기사 기준 2016.6.29(산후안), 2006.8.16 플루미넨시 원정은 Transfermarkt 시각(8.15)이 틀려 ESPN·Transfermarkt 리포트 날짜(8.16)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(루니·호날두·긱스·나니·베르바토프·실바·제코·아구에로 등), 직접 추정, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위(Transfermarkt 순위표)를 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {ELO_SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {ELO_SRC['기존 팀×시즌 값']}, 순위표+모형 {ELO_SRC['순위표+리그 모형']}, 직접 {ELO_SRC['직접 추정']})",
    "리그 수준: 아르헨티나 1부는 평균 1583·흩어짐 63 모형(리켈메 선례). 2001~2004는 반시즌(아페르투라·클라우수라) Transfermarkt 순위표(경기가 속한 대회, 대륙 대회의 아르헨티나 상대는 그때 진행 중인 대회)이고 같은 팀이 한 해 두 대회 값이 다르면 평균(우라칸·뉴웰스 2002, 라싱·차카리타 2003). 2015(30팀)·2016 상반기(15팀 2개 조, 조 순위/15팀)·2016-17~2019-20 수페르리가는 그 대회 최종 순위. 코파 마라도나 2020(4팀 조)은 조 순위가 수준을 잘 나타내지 못해 직전 2019-20 수페르리가 최종 순위를 씀(추정), 코파 데 라 리가 2021은 13팀 조 순위(카바니 리가 컵 선례). 브라질 세리에 A는 기존 모형(평균 1598), 세리에 B는 루카스 모우라 선례 모형(평균 1370), 파울리스타 상대는 그해 전국 리그 순위(네이마르 방식; 세리에 C 1253, 그 아래 1200 — RSSSF 2005·2006 세리에 B·C 명단). 중국 슈퍼리그 2017은 다른 선수 자료의 2012 순위별 값(모형 평균 1484, 추정). 콜롬비아는 아페르투라·피날리사시온 정규 단계 승점 합 순위를 평균 1580 모형에, 멕시코 2005-06은 조별 표 승점 합 순위를 기존 멕시코 모형에 넣은 추정. 프리미어리그·세리에A·챔스 상대는 기존 값",
    "직접 추정(모두 '추정'): " + ", ".join(f"{o} {s_} {e}" for o, s_, e in sorted(MAN_HIT)) + ". 볼리비아·페루·파라과이·칠레·베네수엘라 상대는 순위표가 없어 다른 선수 자료의 같은 팀·같은 나라 상위 팀 값에 맞춤. 코파 아르헨티나의 과라니 안토니오 프랑코(2015)·알바라도(2018)는 3부(토르네오 페데랄 A) 1253",
    "대회 비중: FA컵·리그컵·코파 이탈리아·코파 아르헨티나·코파 두 브라질·중국 FA컵·코파 데 라 수페르리가 2019는 국내컵(16강까지 낮은 비중, 8강부터 높은 비중·준결승·결승). 커뮤니티 실드·UEFA 슈퍼컵·수페르코파 이탈리아나·수페르코파 아르헨티나·레코파 수다메리카나 2004는 국내컵 결승 비중(슈퍼컵류). 인터콘티넨털컵 2003·클럽 월드컵 2008은 클럽 월드컵 비중. 캄페오나투 파울리스타는 국내컵(네이마르 선례, 리그 단계라 무승부 1점). 코파 마라도나 2020·코파 데 라 리가 2021의 조별 단계(1부 전 팀, 리그식)와 2020 결선 조는 리그, 8강·준결승·결승은 국내컵 단계(나니의 MLS is Back 2020 선례와 같은 방식, 판단). AFC 챔스 예선(브리즈번전)은 AFC 챔스 비중. 리베르타도레스·수다메리카나·챔스·유로파는 단계별 비중(UEFA컵 2006-07 1라운드는 유로파 예선)",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·리그컵 준결승·코파 이탈리아 준결승은 원정 다득점·연장. 리베르타도레스는 2004년까지 원정 다득점·연장 없이 승부차기, 2005년부터 원정 다득점 있고 연장 없음(리켈메 선례). 수다메리카나 2004·2005와 코파 두 브라질 2005는 원정 다득점 있고 연장 없이 승부차기(리켈메·호나우두 선례). 못 뛴 다른 차전 스코어는 Transfermarkt 리포트",
    "시즌 구분: 보카·코린치안스·상하이 선화는 달력 연도(보카 2001은 1경기), 잉글랜드·이탈리아 클럽은 8월 1일 기준. 보카 세 시기(2001~2004, 2015~2016, 2018~2021)는 같은 클럽. 클럽 구분: 2005.1.1 코린치안스, 2006.8.31 웨스트햄, 2007.8.10 맨체스터 유나이티드(임대), 2009.7.14 맨체스터 시티, 2013.7.1 유벤투스, 2015.7.11 보카, 2017.1.1 상하이 선화, 2018.1.6 보카(경기 클럽과 경계 불일치 0)",
    "은퇴: 마지막 공식 경기 2021.5.31 코파 데 라 리가 준결승 라싱전(승부차기 패). Transfermarkt 2021.7.1부터 소속 없음, 2022.6.4 은퇴",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl"]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const TVZ_E={J(E)};\nconst TVZ_M={J(M)};\nconst TVZ_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "arg_averages": ARG_AVG,
               "date_changes": DATE_LOG, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
