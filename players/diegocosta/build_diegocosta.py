#!/usr/bin/env python3
"""디에구 코스타 (Diego da Silva Costa, Transfermarkt 44779): raw/ -> diegocosta.json + src/data/dco.js (판정 근거는 judgments.md)

  python3 players/diegocosta/build_diegocosta.py            # 파일 쓰기
  python3 players/diegocosta/build_diegocosta.py --debug    # Elo 출처 로그만 출력
  python3 players/diegocosta/build_diegocosta.py --stat     # 요약·판정·동료 대조
  python3 players/diegocosta/build_diegocosta.py --ties     # 합산 행

호비뉴 build 스크립트(players/robinho)를 바탕으로 함. 입력: raw/tm_games.csv(출전·분·날짜 후보), raw/tm_events.csv(리포트 골 목록),
raw/tm_match_info.csv(리포트 머리·다른 차전), raw/fotmob_tm_map.csv·fotmob_playerMatches.csv(FotMob 경기 시각·선수 경기 목록),
raw/fotmob_events.csv(골·도움 대조), raw/ranks.txt(순위표), elo/opponent_elo_by_team_season.csv + aliases.csv, elo/league_*_mean.json,
src/data/*.js(git에 올라간 다른 선수 자료). 보조: assist_checks.py(2014.8 이후 단일 출처 도움 웹 확인), man_elo.py(직접 추정 Elo·리그 소속).
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "dco.js")
OUT_JSON = os.path.join(HERE, "diegocosta.json")
ME = "44779"
ME_KO = "디에구 코스타"

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
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["fotmob_matchId"]}
FMPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 날짜
# 유럽 경기: TM 일정 날짜(API UTC를 경기장 시간대로 바꾼 날짜와 모두 같음 — 빌드에서 확인).
# 브라질·아르헨티나·칠레(2021~2024): TM 리포트·일정 날짜는 중부 유럽 날짜라 저녁 경기가 하루 밀림 →
#   FotMob 경기 시각(선수 경기 목록·이벤트, 전 경기 매핑)을 경기장 시간대로 바꾼 날짜(테베스·호비뉴 선례).
DATE_FIX = {
    "4061324": "2023-10-21",   # 보타포구–아틀레치쿠-PR: 10.21 저녁 시작, 정전으로 중단 후 10.22 오후 재개(Gazeta·abcdoabc 기사) → 시작일(니코 윌리엄스 선례). FotMob은 재개 시각
}
DATE_LOG = []
def _conv(utc, tz):
    return datetime.datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(ZoneInfo(tz)).date().isoformat()
def fm_utc(gid):
    m = FMMAP.get(gid)
    if not m: return None
    if m["fotmob_matchId"] in FMPM: return FMPM[m["fotmob_matchId"]]["utc"]
    if m["fm_utc"]: return m["fm_utc"]
    for r in FME.get(gid, []): return r["date_utc"]
    return None
def _ldate(g):
    gid = g["gameId"]
    if gid in DATE_FIX: return DATE_FIX[gid], "fix"
    sched = g["date_local_schedule"]
    if not g["tz_used"].startswith("America"):
        conv = _conv(g["date_utc"], g["tz_used"])
        if conv != sched: sys.exit("유럽 날짜 불일치 " + gid)
        return sched, "tm"
    u = fm_utc(gid)
    if u: return _conv(u, g["tz_used"]), "fm"
    return g["date_local_tz_conv"], "conv"
LD = {}
for gid, g in G.items():
    LD[gid], how = _ldate(g)
    if LD[gid] != g["date_local_schedule"]: DATE_LOG.append((gid, g["date_local_schedule"], LD[gid], how, g["opponent"]))
def ldate(g): return LD[g["gameId"]]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"PO1", "PO2", "ES1", "ES2", "GB1", "BRA1"}
STATE = {"BRRS", "RS2f"}   # 캄페오나투 가우슈(1단계·결선): 국내컵 낮은 비중(호비뉴·네이마르·수아레스 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid in ("FAC", "CGB", "CDR", "BRC"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth") or (cid == "CGB" and r.startswith("fifth")): return "dk"
        return "dc"
    if cid in ("SUC", "USC"): return "df"   # 수페르코파 데 에스파냐·UEFA 슈퍼컵
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "UEFA":   # UEFA컵 2006-07: 32강(TM 'intermediate stage')·16강 = 유로파 토너먼트
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        return "elk"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
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
    if cid in ("CL", "UEFA", "EL", "SUC"): return (1, 1)          # UEFA 2020-21까지, 수페르코파 2013
    if cid == "CDR":
        if d < "2019-07-01": return (1, 1)                          # 코파 델 레이 2018-19까지
        sys.exit("CDR 2019 이후 두 경기 " + d)
    if cid == "CGB":
        if d < "2018-07-01": return (1, 1)                          # 리그컵 준결승 2017-18까지(아자르 선례)
        return (0, 0)
    if cid == "CLI":
        if d < "2022-01-01": return (1, 0)                          # 리베르타도레스 2021까지 원정 다득점·연장 없음(디에구 히바스 2021 선례)
        return (0, 0)
    if cid == "CS":
        if d < "2022-01-01": return (1, 0)
        return (0, 0)                                               # 수다메리카나 2022부터 원정 다득점 없음(루카스 모우라 2023 선례)
    if cid == "BRC":
        if d < "2018-01-01": return (1, 0)
        return (0, 0)                                               # 코파 두 브라질 2018부터 원정 다득점 없음, 연장 없이 승부차기(수아레스·루카스·파예 선례)
    if cid in STATE: return (0, 0)                                  # 주 선수권 결선: 원정 다득점·연장 없음(네이마르·호비뉴 선례)
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
MIN_EST = {}
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

A_CHECK = {}
def a_key(gid, minute): return f"{gid}|{minute}"
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())   # A_CHECK 채움(근거 URL 포함)

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if (f["costa_assist"] == "1" or f["assistStr"].strip() == "assist by Diego Costa") and fm_min_match(f, e["minute"]): return True
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
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    if d < GAP: return None
    fa, pm = fm_assist(gid, e), fm_pm_assists(gid)
    k = a_key(gid, e["minute"])
    if fa:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if pm and pm >= 1 and k not in A_CHECK:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], f"TM+FotMob 선수 경기 목록(도움 {pm})")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "2014.8 이후 단일 출처(확인 못 함)"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], f"판정 없음 FMpm={pm}"))
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
            if e["goal_desc"] == "Penalty rebound": judg.append(("PK 리바운드 골(PK 아님)", ldate(g), opp(g), e["minute"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

FM_ONLY = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if (f["costa_assist"] == "1" or f["assistStr"].strip() == "assist by Diego Costa") and f["pen_shootout_event"] != "True":
            mi = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(e["assist_id"] == ME and fm_min_match(f, e["minute"]) for e in EVS.get(gid, [])):
                FM_ONLY.append((ldate(G[gid]), gid, mi, f["scorer"]))
PM_MORE = []   # FotMob 선수 경기 목록 도움 > TM 도움(넣지 않음, 기록만)
for gid, g in G.items():
    pm = fm_pm_assists(gid)
    if pm and pm > int(g["assists"] or 0): PM_MORE.append((ldate(g), gid, opp(g), pm, g["assists"]))

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
for gid, *_ in SCORE_MISMATCH:
    if any(r[1] == gid for r in raw_rows): sys.exit("골 목록이 모자란 리포트에 코스타 기록 " + gid)

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
    if b in ("hon.js", "dco.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "paulista", "paulo", "ca", "cs", "deportivo", "deportes", "universidad", "san", "santa", "fk", "vfl", "bv",
        "racing", "arsenal", "juniors", "plate", "river", "nacional", "independiente", "estudiantes", "union", "boca", "gimnasia", "esgrima", "lorenzo", "almagro", "hotspur", "palace", "villa", "ham", "manchester", "verona", "sheffield", "bristol", "birmingham", "nottingham", "queens", "park", "west", "aston",
        "sevilla", "betis", "celta", "vigo", "gijon", "coruna", "las", "palmas", "valencia", "levante", "atletico", "rayo", "vallecano", "balompie", "sociedad", "barcelona", "espanyol", "tel", "aviv", "hapoel", "maccabi", "brasil", "gremio"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
SA_DOM = {"CLI", "CS", "BRA1", "BRRS", "RS2f", "BRC"}
def same_match(o, d, cid):
    exact = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    if cid in SA_DOM: cand = exact
    else: cand = exact or [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4], 0)

LC = [2.51, 1.668, 1.189, 0.842, 0.664, 0.555, 0.43, 0.259, 0.079, -0.096, -0.231, -0.321, -0.412, -0.502, -0.531, -0.649, -0.814, -0.999, -1.103, -1.177, -1.378]
def cv(r, n):
    n = max(n, 2); r = min(max(r, 1), n)
    x = (r - 1) / (n - 1) * 20; i = min(19, int(x)); t = x - i
    return LC[i] + (LC[i + 1] - LC[i]) * t
def half_up(x): return int(x + 0.5)
WM = json.load(open(os.path.join(ELO, "league_world_mean.json"), encoding="utf-8"))
SM = json.load(open(os.path.join(ELO, "league_season_mean.json"), encoding="utf-8"))
S2 = json.load(open(os.path.join(ELO, "league_second_mean.json"), encoding="utf-8"))
XM = json.load(open(os.path.join(ELO, "league_second_x_mean.json"), encoding="utf-8"))
EU_LG = {"ES1": ("라리가", 20), "GB1": ("프리미어리그", 20), "IT1": ("세리에A", 20), "FR1": ("리그1", 20), "PO1": ("포르투갈 1부", None)}
EU_2 = {"ES2": ("세군다", "라리가", 22), "GB2": ("챔피언십", "프리미어리그", 24), "PO2": ("포르투갈 2부", "포르투갈 1부", 18)}
def rank_model(lg, season, v):
    r, n, nm, grp = v
    if lg == "BRA1":
        return half_up(WM["평균"][f"BRA|{season}"] + WM["흩어짐"]["BRA"] * cv(r, 20)), f"브라질 세리에 A {season} {r}위", season
    if lg == "BRA2":
        return half_up(XM["평균"][f"브라질 세리에 B|{season}"] + 51.24 * cv(r, n)), f"브라질 세리에 B {season} {r}위", season
    if lg in EU_LG:
        pre, n0 = EU_LG[lg]
        y = int(season[:4]) + 1
        if lg == "PO1": n0 = 16 if 2007 <= y <= 2014 else 18
        lab = f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
        return half_up(SM["평균"][f"{pre}|{season}"] + SM["흩어짐"][pre] * cv(r, n)), lab, season
    if lg in EU_2:
        pre, top, n0 = EU_2[lg]
        lab = f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
        return half_up(S2["평균"][f"{pre}|{season}"] + S2["흩어짐"][top] * cv(r, n)), lab, season
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

CAL = {"BRA1", "BRRS", "RS2f", "BRC"}
def seasons_for(cid, d, o):
    if cid in ("CLI", "CS"): return [d[:4], eu(d)]
    if cid in CAL: return [d[:4]]
    return [eu(d), d[:4]]

def lg_cands(cid, d, o):
    if cid in ("BRA1", "BRRS", "RS2f", "BRC", "CLI", "CS"): return [("BRA1", d[:4]), ("BRA2", d[:4])]
    s = eu(d)
    return [(x, s) for x in ("ES1", "ES2", "GB1", "GB2", "PO1", "PO2", "IT1", "FR1")]

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
MAN_HIT = set(); NEW_TS = {}

def opp_elo(o, d, cid):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    seasons = seasons_for(cid, d, o)
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); MAN_HIT.add((o, s, e)); NEW_TS[(o, s)] = (e, lv); return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for lg, s in lg_cands(cid, d, o):
        t = RANKS.get((lg, s), {})
        if k in t:
            res = rank_model(lg, s, t[k])
            if res and res[0]:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); NEW_TS[(o, s)] = (res[0], res[1]); return res[0], res[1]
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())   # 직접 추정(MAN) 목록

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
    print("NEW", NEW_TS)
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or not any(r["time"] for r in FME.get(gid, [])): continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["costa_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "penalty" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))
FM_N = sum(1 for gid in EVS if gid in G and any(r["time"] for r in FME.get(gid, [])) and any(e["scorer_id"] == ME for e in EVS[gid]))
FM_G = sum(1 for gid in EVS if gid in G and any(r["time"] for r in FME.get(gid, [])) for e in EVS[gid] if e["scorer_id"] == ME and not is_og(e))

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
        if x[0] == "a" and re.search(r"Diego Costa|D\. Costa", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(코스타 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("코스타 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 코스타 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
# 상대 팀 선수 자료에서 같은 날 이 클럽을 상대한 경기(날짜 대조)
MYCLUB_NAMES = {"Penafiel", "Braga", "Celta", "Albacete", "Valladolid", "Atlético", "Atletico", "Rayo", "Chelsea", "Mineiro", "Wolverhampton", "Wolves", "Botafogo", "Grêmio", "Gremio"}
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("pendco", "2007-01-01", "FC 페나피엘", "페나피엘", "2006"), ("bradco", "2007-08-25", "SC 브라가", "브라가", "2007"),
         ("celdco", "2008-08-23", "셀타 비고", "셀타", "2007~2008"), ("albdco", "2009-07-01", "알바세테", "알바세테", "2008~2009"),
         ("valdco", "2010-07-01", "레알 바야돌리드", "바야돌리드", "2009~2010"), ("atmdco", "2012-01-24", "아틀레티코 마드리드", "아틀레티코", "2010~2011"),
         ("raydco", "2012-07-01", "라요 바예카노", "라요", "2012"), ("atmdco", "2014-07-01", "아틀레티코 마드리드", "아틀레티코", "2012~2014"),
         ("chedco", "2018-01-01", "첼시", "첼시", "2014~2017"), ("atmdco", "2021-08-14", "아틀레티코 마드리드", "아틀레티코", "2018~2020"),
         ("camdco", "2022-09-12", "아틀레치쿠 미네이루", "아틀레치쿠-MG", "2021"), ("wlvdco", "2023-08-12", "울버햄프턴", "울버햄프턴", "2022~2023"),
         ("botdco", "2024-02-08", "보타포구", "보타포구", "2023"), ("gredco", None, "그레미우", "그레미우", "2024")]
TM_CLUB = {"3327": "pendco", "1075": "bradco", "940": "celdco", "1532": "albdco", "366": "valdco", "13": "atmdco", "367": "raydco",
           "631": "chedco", "330": "camdco", "543": "wlvdco", "537": "botdco", "210": "gredco"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
SCAL = ("camdco", "botdco", "gredco")
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in SCAL: return str(y)
    if y == 2020 and m == 8: return "2019-20"
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("페나피엘(임대)", "2007-01-01"), ("브라가(임대)", "2007-08-25"), ("셀타 비고(임대)", "2008-08-23"), ("알바세테(임대)", "2009-07-01"),
          ("레알 바야돌리드", "2010-07-01"), ("아틀레티코 마드리드(2010~2011)", "2012-01-24"), ("라요 바예카노(임대)", "2012-07-01"),
          ("아틀레티코 마드리드(2012~2014)", "2014-07-01"), ("첼시", "2018-01-01"), ("아틀레티코 마드리드(2018~2020)", "2021-08-14"),
          ("아틀레치쿠 미네이루", "2022-09-12"), ("울버햄프턴", "2023-08-12"), ("보타포구", "2024-02-08"), ("그레미우", "9999")]
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
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A, UNTYPED)
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    print("FM only", FM_ONLY)
    print("PM more", PM_MORE)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G, FM_CMP)
    print("score mismatch", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("dates changed", len(DATE_LOG), collections.Counter(x[3] for x in DATE_LOG))
    for x in sorted(NEW_TS.items()): print("NEW", x)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_diegocosta.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl", "df", "clg", "cl16"]:
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
        if b[4] > a[4] and (b[5], b[6]) <= (a[5], a[6]) and b[5] < a[5] + 1: problems.append(("스코어 역순", d, a[4], b[4]))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const DCO_E={J(E)};\nconst DCO_M={J(M)};\nconst DCO_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS, "fotmob_only_assists": FM_ONLY,
               "fotmob_pm_more_assists": PM_MORE, "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "date_changes": DATE_LOG, "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
