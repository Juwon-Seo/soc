#!/usr/bin/env python3
"""호비뉴 (Robson de Souza, Transfermarkt 15511): raw/ -> robinho.json + src/data/rbh.js (판정 근거는 judgments.md)

  python3 players/robinho/build_robinho.py            # 파일 쓰기
  python3 players/robinho/build_robinho.py --debug    # Elo 출처 로그만 출력
  python3 players/robinho/build_robinho.py --stat     # 요약·판정·동료 대조
  python3 players/robinho/build_robinho.py --ties     # 합산 행

테베스 build 스크립트(players/tevez)를 바탕으로 함. 입력: raw/tm_games.csv(출전·분·날짜 후보), raw/tm_events.csv(리포트 골 목록),
raw/tm_match_info.csv(리포트 머리·다른 차전), raw/fotmob_tm_map.csv(FotMob 경기 시각), raw/fotmob_events.csv·fotmob_playerMatches.csv(도움 대조),
raw/espn_robinho_check.csv(ESPN 도움 대조), raw/ranks.txt(순위표), elo/opponent_elo_by_team_season.csv + aliases.csv, elo/league_*_mean.json,
src/data/*.js(git에 올라간 다른 선수 자료). 보조: assist_checks.py(2014.8 이후 도움 웹 확인), man_elo.py(직접 추정 Elo·리그 소속).
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "rbh.js")
OUT_JSON = os.path.join(HERE, "robinho.json")
ME = "15511"
ME_KO = "호비뉴"

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
for r in rd("espn_robinho_check.csv"): ESPN[r["gameId"]].append(r)

# ---------------------------------------------------------------- 날짜
# 브라질(산투스·아틀레치쿠 미네이루): TM 리포트·일정 날짜는 중부 유럽 날짜라 저녁 경기가 하루 밀림 → 경기 시각(UTC)을 경기장 시간대로 바꾼 날짜(테베스 코린치안스 선례).
#   FotMob 경기 시각이 있으면(2010 이후) 그것을 씀. TM 시각이 12:00/13:00 UTC 정각이면 시각 미상 자리값 → 일정 날짜.
# 유럽·중국·튀르키예 경기: TM 날짜와 바꾼 날짜가 모두 같음(빌드에서 확인).
DATE_FIX = {
    "4366539": "2010-05-02",   # 파울리스타 2010 결승 2차전 산투 안드레전: TM은 1차전과 같은 4.25로 적음 → 5.2(네이마르 자료 ney.js와 같음; 1차전 4.25, 2차전 5.2 파카엥부)
}
DATE_LOG = []
def _conv(utc, tz):
    return datetime.datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(ZoneInfo(tz)).date().isoformat()
def _ldate(g):
    gid = g["gameId"]
    if gid in DATE_FIX: return DATE_FIX[gid], "fix"
    sched = g["date_local_schedule"]
    if g["club_id"] not in ("221", "330"):
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
LEAGUE = {"BRA1", "ES1", "GB1", "IT1", "CSL", "TR1"}
STATE = {"BCP1", "BCPF", "BRCM", "BRC2"}   # 파울리스타(1단계·결선)·미네이루·프리메이라 리가 2017: 국내컵 낮은 비중(네이마르·디에구·루카스 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid in ("FAC", "CGB", "CIT", "CDR", "BRC", "TRP"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth"): return "dk"
        return "dc"
    if cid in ("SUC", "SCI"): return "df"   # 슈퍼컵류
    if cid == "KLUB": return "cwc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "CLQ": return "clq"
    if cid == "UEFA":   # UEFA컵 2008-09: 1라운드 = 유로파 예선, 조별 = 유로파 조별, 32강(TM '3rd round')·16강·8강 = 유로파 토너먼트(디에구 선례)
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        return "elk"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 32강(intermediate stage)·16강·8강
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
    r = rnd.lower()
    if cid in ("CL", "UEFA", "EL", "CLQ", "CDR", "CIT", "SUC", "TRP"): return (1, 1)   # 튀르키예컵 2020-21까지 원정 다득점(v1.152)
    if cid in ("CLI", "CS"):
        if d < "2005-01-01": return (0, 0)              # 2004년까지 원정 다득점·연장 없이 승부차기(디에구·리켈메 선례)
        if cid == "CLI" and r.startswith("final") and d >= "2008-01-01": return (0, 1)
        return (1, 0)
    if cid == "BRC": return (1, 0)                      # 코파 두 브라질 2017까지(네이마르·디에구 선례)
    if cid in ("BCPF", "BRCM"): return (0, 0)          # 주 선수권 결선: 원정 다득점·연장 없음(네이마르 선례)
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
MIN_EST = {"3477146": 90, "3477174": 90}   # TM played인데 출전 분 빈칸(2004.5.8 주벤투지, 5.23 팔메이라스) → 90분 추정(디에구 die.js 같은 경기 선례)
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    if g["gameId"] in MIN_EST: M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), MIN_EST[g["gameId"]], 1]); continue
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
        if f["robinho_assist"] == "1" and fm_min_match(f, e["minute"]): return True
    return False
def fm_pm_assists(gid):
    m = FMMAP.get(gid)
    if m and m["fotmob_matchId"] in FMPM: return int(FMPM[m["fotmob_matchId"]]["assists"] or 0)
    return None
def espn_assist(gid, e):
    for r in ESPN.get(gid, []):
        if r["role"] != "goal" and r["minute_tm"] == e["minute"] and r["espn_names_robinho"] == "1": return True
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
        if e["scorer_id"] == ME and is_og(e): sys.exit("호비뉴 자책골 " + gid)
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
        if f["robinho_assist"] == "1" and f["pen_shootout_event"] != "True":
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
    if b in ("hon.js", "rbh.js") or "src/data/" + b not in TRACKED: continue
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
SA_DOM = {"CLI", "CS", "BRA1", "BCP1", "BCPF", "BRCM", "BRC2", "BRC", "CSL", "KLUB"}
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

# 새 팀×시즌 값 = 그 리그·시즌 목표 평균 + 흩어짐 × 순위 곡선(v1.216~v1.219 도구와 같은 식; 넣은 뒤 도구 이동량 0 확인)
LC = [2.51, 1.668, 1.189, 0.842, 0.664, 0.555, 0.43, 0.259, 0.079, -0.096, -0.231, -0.321, -0.412, -0.502, -0.531, -0.649, -0.814, -0.999, -1.103, -1.177, -1.378]
def cv(r, n):
    n = max(n, 2); r = min(max(r, 1), n)
    x = (r - 1) / (n - 1) * 20; i = min(19, int(x)); t = x - i
    return LC[i] + (LC[i + 1] - LC[i]) * t
def half_up(x): return int(x + 0.5)
WM = json.load(open(os.path.join(ELO, "league_world_mean.json"), encoding="utf-8"))
SM = json.load(open(os.path.join(ELO, "league_season_mean.json"), encoding="utf-8"))
XM = json.load(open(os.path.join(ELO, "league_second_x_mean.json"), encoding="utf-8"))
def _turkey():
    import io, contextlib
    G_ = {"__file__": os.path.join(ROOT, "tools", "league_era_normalize.py"), "__name__": "x"}
    src = open(G_["__file__"], encoding="utf-8").read().replace("if '--apply' in sys.argv:", "if False:")
    argv = sys.argv; sys.argv = ["x"]
    with contextlib.redirect_stdout(io.StringIO()): exec(compile(src, "era", "exec"), G_)
    sys.argv = argv
    return G_["otarget"], G_["OSD"]["Turkey"]
_TR = None
def tr_v(r, n, y_end):
    global _TR
    if _TR is None: _TR = _turkey()
    return half_up(_TR[0]("Turkey", y_end) + _TR[1] * cv(r, n))
NTEAMS = {"BRA1": {"2002": 26, "2003": 24, "2004": 24, "2005": 22}}
EU_LG = {"ES1": "라리가", "IT1": "세리에A", "GB1": "프리미어리그"}
def rank_model(lg, season, v):
    r, n, nm, grp = v
    if lg == "BRA1":
        n = 20   # 기존 자료 라벨 규칙: '브라질 세리에 A Y N위'(팀 수 표기 없음 = 20팀 곡선; 2002~2005는 22~26팀이지만 기존 값과 같게)
        return half_up(WM["평균"][f"BRA|{season}"] + WM["흩어짐"]["BRA"] * cv(r, n)), f"브라질 세리에 A {season} {r}위", season
    if lg == "BRA2":
        return half_up(XM["평균"][f"브라질 세리에 B|{season}"] + 51.24 * cv(r, n)), f"브라질 세리에 B {season} {r}위", season
    if lg == "CSL":
        return half_up(WM["평균"][f"CHN|{season}"] + WM["흩어짐"]["CHN"] * cv(r, n)), f"중국 슈퍼리그 {season} {r}위", season
    if lg == "TR1":
        return tr_v(r, n, int(season[:4]) + 1), f"쉬페르리그 {season} {r}위", season
    if lg in EU_LG:
        pre = EU_LG[lg]
        return half_up(SM["평균"][f"{pre}|{season}"] + SM["흩어짐"][pre] * cv(r, n)), f"{pre} {season} {r}위", season
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

CAL = {"BRA1", "BCP1", "BCPF", "BRCM", "BRC2", "BRC", "CSL", "CLI", "CS", "KLUB"}
def seasons_for(cid, d, o):
    if cid in ("CLI", "CS"): return [d[:4], eu(d)]   # 남미 밖·분할 시즌 리그 상대(크루스 아술 2002-03 등)는 시즌 키
    if cid in CAL: return [d[:4]]
    return [eu(d), d[:4]]   # 달력 연도 리그 팀은 연도 키

def lg_cands(cid, d, o, sid):
    if cid in ("BRA1", "BCP1", "BCPF", "BRCM", "BRC2", "BRC", "CLI", "CS"): return [("BRA1", d[:4]), ("BRA2", d[:4])]
    if cid in ("CSL", "KLUB"): return [("CSL", d[:4])]
    s = eu(d)
    return [("ES1", s), ("IT1", s), ("GB1", s), ("TR1", s)]

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
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

ARG_AVG = []
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
    fm = [r for r in FME[gid] if r["robinho_scorer"] == "1" and r["pen_shootout_event"] != "True"]
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
        if x[0] == "a" and re.search(r"Robinho", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(호비뉴 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("호비뉴 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) if G_BYDATE.get(r[9], "BRA1") in SA_DOM else same_team(x[1], r[1])):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm[1], m[1]) and mm[2] != m[2] and (key(mm[1]) == key(m[1]) or G_BYDATE.get(m[0], "BRA1") not in SA_DOM):
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 호비뉴 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("santrb", "2005-08-27", "산투스", "산투스", "2002~2005"), ("rmarb", "2008-09-01", "레알 마드리드", "레알", "2005~2008"),
         ("mcirb", "2010-01-28", "맨체스터 시티", "맨시티", "2008~2010"), ("santrb", "2010-08-31", "산투스", "산투스", "2010"),
         ("acmrb", "2014-08-07", "AC 밀란", "밀란", "2010~2014"), ("santrb", "2015-07-16", "산투스", "산투스", "2014~2015"),
         ("gzerb", "2016-02-11", "광저우 헝다", "광저우", "2015"), ("camrb", "2018-01-23", "아틀레치쿠 미네이루", "아틀레치쿠-MG", "2016~2017"),
         ("sivrb", "2019-01-05", "시바스스포르", "시바스스포르", "2018"), ("ibbrb", None, "이스탄불 바샥셰히르", "바샥셰히르", "2019~2020")]
TM_CLUB = {"221": "santrb", "418": "rmarb", "281": "mcirb", "5": "acmrb", "10948": "gzerb", "330": "camrb", "2381": "sivrb", "6890": "ibbrb"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
SCAL = ("santrb", "gzerb", "camrb")
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in SCAL: return str(y)
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("산투스(2002~2005)", "2005-08-27"), ("레알 마드리드", "2008-09-01"), ("맨체스터 시티", "2010-01-28"), ("산투스(2010 임대)", "2010-08-31"),
          ("AC 밀란", "2014-08-07"), ("산투스(2014~2015 임대)", "2015-07-16"), ("광저우 헝다", "2016-02-11"), ("아틀레치쿠 미네이루", "2018-01-23"),
          ("시바스스포르", "2019-01-05"), ("이스탄불 바샥셰히르", "9999")]
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
CH_D = collections.Counter(x[3] for x in DATE_LOG)
NOTE_LINES = [
    f"호비뉴(산투스·레알 마드리드·맨체스터 시티·산투스·AC 밀란·산투스·광저우 헝다·아틀레치쿠 미네이루·시바스스포르·이스탄불 바샥셰히르)의 클럽 공식 경기 {NG}경기({d_(first[0])} 보타포구전 ~ {d_(last[0])} 카이세리스포르전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·브라질 대표팀(A·올림픽) 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{k} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있거나 리그 밖 대회인 경기; 호비뉴 골 수·PK 수는 선수 경기 성적과 경기마다 같음). 2010 이후 골 {FM_G}개({FM_N}경기)는 FotMob 경기 기록과 대조해 수·순서가 같음(추가시간 표기·2분 이내 시각 차이만 다름). 2008-09 이후 골·도움이 있는 경기는 ESPN 경기 기록과도 대조함",
    "위키백과와 차이: 합계 Transfermarkt 763경기 249골, 영어 위키백과 771경기 249골, 포르투갈어 위키백과 766경기 250골. 영어 위키백과의 산투스 2002 기타 대회 3경기·2003 파울리스타 6경기(골 없음)와 포르투갈어 위키백과의 산투스 2001 5경기 1골은 Transfermarkt·FotMob에 경기가 없고 경기 단위 출처를 찾지 못해 넣지 않음(디에구 히바스 선례). 산투스 2010 코파 두 브라질(Transfermarkt 9경기, 영어 위키백과 8경기)·광저우 2015(Transfermarkt 10경기, 영어 위키백과 11경기)는 Transfermarkt 경기 목록을 따름",
    "프로 리그 규칙: 모든 소속 팀-시즌이 1부(브라질 세리에 A, 라리가, 프리미어리그, 세리에A, 중국 슈퍼리그, 쉬페르리그)라 뺀 시즌 없음. 캄페오나투 파울리스타·캄페오나투 미네이루(주 선수권 1부)와 2017 프리메이라 리가(주 사이 컵)는 1부 팀의 공식 대회라 넣음",
    f"도움: 2014년 8월 이전은 Transfermarkt 경기 리포트 단일 출처(클로제·인시녜·디에구 선례; 유형 칸이 빈 {UNTYPED}개는 일반 도움으로 셈). Transfermarkt 도움 {TM_A}개에서 PK 유도 {sum(1 for j in EXJ if j[5].startswith('PK'))}개({exl('PK')}), 슈팅 리바운드('Shot on goal') {sum(1 for j in EXJ if j[5].startswith('슈팅'))}개({exl('슈팅')}), 상대 자책골 유도 {sum(1 for j in EXJ if j[5].startswith('상대'))}개({exl('상대')})를 빼고, 본인 PK 골의 본인 도움 표기 3개(2005.5.25 우니베르시다드 데 칠레전 89분, 2016.6.5 스포르트전 30분·45+2분)는 도움으로 세지 않음. 2014년 8월 이후는 Transfermarkt와 FotMob(경기 이벤트 또는 선수 경기 목록)이 같은 도움만 넣고, 한쪽에만 있는 도움은 다른 출처 2곳(ESPN 문자 중계·경기 기사)이 확인한 것만 넣음: 기사로 확인해 넣은 것 {len(ADDED_WEB)}개(" + ", ".join(f"{d_(a[0])} {a[3]} {a[2]}분" for a in ADDED_WEB) + f"), FotMob 선수 경기 목록으로 확인한 것 {len(PM_ONLY)}개(" + ", ".join(f"{d_(a[0])} {a[3]} {a[2]}분" for a in PM_ONLY) + f"), 확인 못 해 뺀 것 {len(UNCONF)}개(" + ", ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]}" for j in UNCONF) + "). FotMob 선수 경기 목록·ESPN에만 있는 2017.7.9 보타포구전 23분 마를로니 골 도움(Transfermarkt 리포트는 도움 없음, 경기 기사는 수비 머리에 맞고 들어간 골로 적음)은 넣지 않음. FotMob·위키백과의 시즌 도움 합계는 경기별 근거가 없어 쓰지 않음",
    "골: 자책골 없음. PK 골은 Transfermarkt 골 유형 'Penalty'(선수 경기 성적 PK 골 수와 같음). 2016.10.29 플라멩구전 82분 골은 FotMob이 PK로 적지 않았으나 Transfermarkt·경기 기사(파울에 따른 PK)대로 PK. 2015.3.17 론드리나전 53분 PK 골은 FotMob 경기 기록에 골 이벤트가 없어 Transfermarkt만. 골 전 스코어는 리포트 골 순서대로 셈. 승부차기 경기의 Transfermarkt 경기 성적 스코어는 승부차기 골을 더한 값이라 쓰지 않음",
    "출전 분: Transfermarkt 그대로. 2004.5.8 주벤투지전·5.23 팔메이라스전은 Transfermarkt에 출전으로만 있고 분이 비어 있어 90분 추정(같은 경기의 디에구 히바스 자료와 같은 처리). 연장 경기: 2012.1.18 코파 이탈리아 노바라전(연장 100분 도움), 2020.2.27 유로파 32강 스포르팅전",
    f"날짜: 경기 현지 날짜. 유럽·중국·튀르키예 경기는 Transfermarkt 날짜. 산투스·아틀레치쿠 미네이루 경기는 Transfermarkt 일정·리포트 날짜가 중부 유럽 기준이라 저녁 경기가 하루 밀려 있어, 경기 시각(UTC)을 경기장 시간대로 바꾼 날짜를 씀(2010 이후는 FotMob 경기 시각, 그 전은 Transfermarkt 시각; {len(DATE_LOG) - CH_D['fix']}경기가 Transfermarkt 날짜보다 하루 앞, 같은 경기의 디에구 히바스 자료와 같음). 시각이 비어 자리값(12·13시 UTC)만 있는 경기는 일정 날짜. 예외: 2010 파울리스타 결승 2차전 산투 안드레전은 Transfermarkt가 1차전과 같은 4.25로 적었으나 5.2(네이마르 자료와 같음)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(디에구 히바스·네이마르·라울·판니스텔로이·베컴·즐라탄·카카·라이트필립스·테베스 등), 직접 추정, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 순위를 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {ELO_SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {ELO_SRC['기존 팀×시즌 값']}, 순위표+모형 {ELO_SRC['순위표+리그 모형']}, 직접 {ELO_SRC['직접 추정']})",
    "리그 수준: 새로 계산한 팀×시즌은 리그·시즌 목표 평균 + 흩어짐 × 순위 곡선(브라질·중국·남미는 비유럽 리그 시즌 수준, 라리가·세리에A·쉬페르리그는 유럽 리그 시즌 수준, 브라질 세리에 B는 다른 나라 2부 수준). 브라질 세리에 A는 기존 자료처럼 'N위' 표기에 20팀 곡선(2002 순위는 영어 위키백과 최종 순위표와 Transfermarkt 표가 같음). 주 선수권·코파 두 브라질의 하부 팀은 그해 전국 리그 소속(영어 위키백과 세리에 B·C·D 시즌 문서)으로 나눠 세리에 B는 순위(2004·2005는 1단계 표), 세리에 C는 1253, 세리에 D와 주 리그만 하는 팀은 1200에 그해 브라질 리그 이동량을 더한 값(같은 해 다른 선수 자료와 같음)",
    "직접 추정·새로 계산한 값(브라질 하부·남미): " + ", ".join(f"{o} {e}({lv.split(' (')[0]})" for o, s_, e, lv in sorted({(o, s_, e, MAN[(key(o), s_)][1]) for o, s_, e in MAN_HIT})) + ". 볼리비아 스포르트 보이스 와르네스 2017은 순위표를 찾지 못해 볼리비아 리그 평균(추정). 우니베르시다드 데 칠레 2005는 진행 중이던 아페르투라 합산 순위, 다누비우 2005 리베르타도레스는 직전 2004 시즌(우승)",
    "대회 비중: 캄페오나투 파울리스타(1단계·결선)·캄페오나투 미네이루·2017 프리메이라 리가는 국내컵 낮은 비중(네이마르·디에구 선례, 리그 단계는 무승부 1점, 단판 결선은 단판). 코파 두 브라질·코파 델 레이·FA컵·리그컵·코파 이탈리아·튀르키예컵은 국내컵(16강까지 낮은 비중, 8강부터 높은 비중·준결승·결승). 수페르코파 데 에스파냐·수페르코파 이탈리아나는 국내컵 결승 비중. 2015 클럽 월드컵은 클럽 월드컵 비중. UEFA컵 2008-09는 1라운드 유로파 예선, 조별 유로파 조별, 32강·16강·8강 유로파 토너먼트. 챔스 예선, 리베르타도레스·수다메리카나·챔스·유로파는 단계별 비중",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·코파 델 레이·코파 이탈리아 준결승·수페르코파·튀르키예컵(2020-21까지)은 원정 다득점·연장. 리베르타도레스·수다메리카나는 2004년까지 원정 다득점·연장 없이 승부차기, 2005년부터 원정 다득점 있고 연장 없음(디에구·리켈메 선례). 코파 두 브라질(2017까지)은 원정 다득점 있고 연장 없음, 파울리스타·미네이루 결선은 둘 다 없음(네이마르 선례). 못 뛴 다른 차전 스코어는 Transfermarkt 리포트",
    "시즌 구분: 산투스·광저우 헝다·아틀레치쿠 미네이루는 달력 연도, 유럽·튀르키예 클럽은 8월 1일 기준. 산투스 세 시기(2002~2005, 2010 임대, 2014~2015 임대)는 같은 클럽. 클럽 구분: 2005.8.27 레알 마드리드, 2008.9.1 맨체스터 시티, 2010.1.28 산투스(임대), 2010.8.31 AC 밀란, 2014.8.7 산투스(임대), 2015.7.16 광저우 헝다, 2016.2.11 아틀레치쿠 미네이루, 2018.1.23 시바스스포르, 2019.1.5 이스탄불 바샥셰히르(경기 클럽과 경계 불일치 0)",
    "은퇴: 마지막 공식 경기 2020.7.19 쉬페르리그 카이세리스포르전. 2020.10.10 산투스와 계약했으나 경기 없이 10.16 계약이 중단됨",
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const RBH_E={J(E)};\nconst RBH_M={J(M)};\nconst RBH_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "arg_averages": ARG_AVG,
               "date_changes": DATE_LOG, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
