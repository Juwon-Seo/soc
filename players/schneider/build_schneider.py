#!/usr/bin/env python3
"""베른트 슈나이더 (Bernd Schneider, Transfermarkt 90): raw/ -> schneider.json + src/data/snb.js (판정 근거는 judgments.md)

  python3 players/schneider/build_schneider.py            # 파일 쓰기
  python3 players/schneider/build_schneider.py --debug    # Elo 출처 로그만 출력
  python3 players/schneider/build_schneider.py --stat     # 요약·판정·동료 대조
  python3 players/schneider/build_schneider.py --ties     # 합산 행

입력: raw/tm_games.csv(출전·분, 경기 이름 없음), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·라운드·다른 차전),
      raw/tables/*.html(Transfermarkt 표·일정: 상대 클럽 id → 이름), raw/ranks.txt(Transfermarkt 순위표),
      players/*/raw/tm_games.csv(다른 선수 원자료의 상대 id → 이름, 읽기만),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
환경 변수 SNB_ROOT: 저장소 뿌리(스크래치 복사본에서 돌릴 때).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SNB_ROOT") or os.path.dirname(os.path.dirname(HERE))
PLAYERS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "players")   # 원자료는 늘 원래 저장소의 players/ 에서 읽음
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "snb.js")
OUT_JSON = os.path.join(HERE, "schneider.json")
ME = "90"
ME_KO = "베른트 슈나이더"

def rd(n, base=RAW):
    with open(os.path.join(base, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

ALLG = rd("tm_games.csv")
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# ---------------------------------------------------------------- 범위
# 프로 리그 규칙(사용자 기준): 카를 차이스 예나 1994-95는 레기오날리가 북동부(당시 독일 3부, 옛 레기오날리가 = 프로 리그 아님) → 그 시즌 리그·컵 경기 전부 뺌
#   (리그 34경기 + 튀링겐 주 컵 4경기 + DFB-포칼 1경기). 로이스·클로제·발라크·알틴톱 선례와 같음.
EXCL_SEASON = {("113", "94/95")}
EXCL = [g for g in ALLG if (g["clubId"], g["season_tm"]) in EXCL_SEASON]
GAMES = [g for g in ALLG if (g["clubId"], g["season_tm"]) not in EXCL_SEASON]
G = {g["gameId"]: g for g in GAMES}
GALL = {g["gameId"]: g for g in ALLG}
if any(g["competitionId"] == "TFVP" for g in GAMES): sys.exit("프로 시즌의 튀링겐 주 컵 경기 — 판정 필요")

def ldate(g):
    # 유럽 경기: API 협정 세계시를 중부 유럽 시간으로 바꾼 날짜(= 리포트 날짜; 리포트가 있는 경기는 같은지 확인)
    return datetime.datetime.fromisoformat(g["date_utc"]).astimezone(ZoneInfo("Europe/Berlin")).date().isoformat()
for gid, g in GALL.items():
    if gid in MI and MI[gid]["date_report"] != ldate(g): sys.exit("날짜 불일치 " + gid)

# ---------------------------------------------------------------- 상대 이름 (API에는 클럽 id만 있음)
def clean(n): return re.sub(r"\s*\([^)]*\d{4}[^)]*\)", "", n).strip()
NAMES = collections.defaultdict(collections.Counter)
for r in MI.values():
    NAMES[r["home_id"]][("1", r["home"])] += 1; NAMES[r["away_id"]][("1", r["away"])] += 1
for f in glob.glob(os.path.join(RAW, "tables", "*.html")):
    for t, i in re.findall(r'title="([^"]*)" href="/[^"]*/verein/(\d+)', open(f, encoding="utf-8", errors="ignore").read()):
        NAMES[i][("2", clean(t))] += 1
for f in glob.glob(os.path.join(PLAYERS, "*", "raw", "tm_games.csv")):
    if "/schneider/" in f: continue
    with open(f, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or "opponent_id" not in rows[0] or "opponent" not in rows[0]: continue
    for r in rows:
        if r["opponent"]: NAMES[r["opponent_id"]][("3", clean(r["opponent"]))] += 1
def opp_name(oid):
    c = NAMES.get(oid)
    if not c: sys.exit("상대 이름 없음 " + oid)
    return sorted(c.items(), key=lambda kv: (kv[0][0], -kv[1]))[0][0][1]
def opp(g):
    gid = g["gameId"]
    if gid in MI:
        m = MI[gid]
        return m["away"] if m["home_id"] == g["clubId"] else m["home"]
    return opp_name(g["opponentId"])
def rnd_of(g): return MI[g["gameId"]]["round"] if g["gameId"] in MI else ""

# ---------------------------------------------------------------- 판정 표
MIN_EST = {}
GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용(전 경력이 이 전)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "L2", "L2S", "L2SA"}   # L2SA = 1991-92 2. 분데스리가 남부 2단계(승격 라운드) — 같은 시즌 리그 경기라 리그 비중

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "DFB":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "LPO":                       # DFB-리가포칼(발라크·클로제·제 호베르투 선례): 첫 경기(intermediate stage) 8강, 준결승, 결승
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        return "dk"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 1999-2003 2차 조별(Group 1~4)도 조별
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "CLQ": return "clq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                       # 3라운드·32강(intermediate stage)·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid):
    if cid in ("UEFA", "CL", "CLQ"): return (1, 1)    # UEFA 대회: 원정 다득점(연장 포함)·2차전 연장
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = GALL[gid], MI[gid]
    if m["home_id"] == g["clubId"]: return "h"
    if m["away_id"] == g["clubId"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    # 리포트 other_leg_score는 <그 리포트에 표시된 홈 팀>:<원정 팀> 순서(이 경기 홈 팀 기준). 선수가 뛴 다른 차전은 API 스코어 사용
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G:
        a, b = map(int, G[oid]["score_club_opp"].split("-")); via_api = (a, b)
    else: via_api = None
    oh, oa = map(int, m["other_leg_score"].split(":"))
    via_rep = (oh, oa) if s == "h" else (oa, oh)
    if via_api and via_api != via_rep: sys.exit("다른 차전 스코어 불일치 " + gid)
    return via_rep

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"])
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    gid = g["gameId"]
    row = [ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), MIN_EST.get(gid, int(g["playedMinutes"] or 0))]
    if gid in MIN_EST: row.append(1)
    M.append(row)

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

def assist_reason(e):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if e["goal_desc"] == "Penalty": return "PK 골(도움 없음)"
    return None

# 2000.9.20 스포르팅전(990077): 리포트가 12분 안드레 크루스 골과 65분 라멜로브 골을 둘 다 0:1로 적어 뒤 레버쿠젠 골이 한 골씩 적게 나옴
#   (끝이 2:2, 실제 3:2). 발라크 자료·독일축구협회 기록: 12분 0:1, 65분 1:1, 72분 2:1, 77분 3:1(노이빌레), 79분 3:2. 슈나이더 골·도움은 없음.
#   골 뒤 스코어를 아래 순서로 고쳐 씀(이 경기에서 나오는 슈나이더 기록은 없어 수치 영향 없음, 점검용).
SCORE_SEQ_FIX = {"990077": ["0-1", "1-1", "2-1", "3-1", "3-2"]}
BEFORE_FIX = {}
raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(GALL[k]) if k in GALL else "", k)):
    if gid not in GALL: continue
    g = GALL[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    seq = SCORE_SEQ_FIX.get(gid)
    for i, e in enumerate(EVS[gid]):
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        if seq:
            before = tuple(map(int, seq[i - 1].split("-"))) if i else (0, 0)
            cnt["h"], cnt["a"] = map(int, seq[i].split("-"))
        else:
            cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if not (is_g or is_a): continue
        if gid not in G:
            judg.append(("제외 시즌 기록", ldate(g), opp(g), e["minute"], "골" if is_g else "도움", e["scorer"])); continue
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        if (gid, e["minute"]) in BEFORE_FIX: gf, ga = BEFORE_FIX[(gid, e["minute"])]
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if not e["assist_type"]: judg.append(("도움 유형 빈칸(일반 도움으로 셈)", ldate(g), opp(g), e["minute"], e["scorer"], e["goal_desc"]))
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk:
                if e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
                judg.append(("PK 아님(PK가 막힌 뒤 리바운드 골)", ldate(g), opp(g), e["minute"], e["goal_desc"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"):
        if not any(j[0].startswith("PK 아님") and j[1] == ldate(g) for j in judg): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in GALL: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final_raw"].split(":"))
    if GALL[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(GALL[gid]), (h, a), (fh, fa)))

# ---------------------------------------------------------------- 이름·기존 자료
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
MANUAL_ALIAS = {"inter milan": "inter", "olympique lyon": "olympique lyonnais"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "snb.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio", "sport", "cd", "ud", "rcd",
        "sv", "as", "ss", "milan", "inter", "madrid", "moscow", "ca", "cs", "deportivo", "san", "santa", "borussia", "bayer", "vfl", "vfb", "tsv",
        "fsv", "munich", "munchen", "hamburger", "eintracht", "werder", "bsc", "hertha", "rb", "spvgg", "kfc", "msv", "ssv", "tsg", "1899", "rot", "weiss"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
def load_ranks(fn, only=None):
    with open(fn, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("|")
            if len(p) < 5 or p[0] == "league": continue
            lg, s = p[0], p[1].split(" ")[0]
            if only and lg not in only: continue
            RANKS[(lg, s)][key(clean(p[4]))] = (int(p[2]), int(p[3]), clean(p[4]))
load_ranks(os.path.join(RAW, "ranks.txt"), only={"L1", "L2"})
# Transfermarkt 표 순서 고침(공식 최종 순위): 2. 분데스리가 1996-97 볼프스부르크·헤르타 모두 58점, 골득실 +23 대 +19로 볼프스부르크 2위
#   (영어 위키백과 1996–97 2. Bundesliga 표, 검색 요약). TM 표는 헤르타 2위·볼프스부르크 3위
RANKS[("L2", "1996-97")][key("VfL Wolfsburg")] = (2, 18, "VfL Wolfsburg")
RANKS[("L2", "1996-97")][key("Hertha BSC")] = (3, 18, "Hertha BSC")
# 분데스리가 2000-01~2008-09 표는 이 선수 원자료에 없음 → 발라크 원자료의 Transfermarkt 표(같은 출처, 제 호베르투 선례)
_bal = os.path.join(PLAYERS, "ballack", "raw", "ranks.txt")
with open(_bal, encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] != "L1": continue
        s = p[1].split(" ")[0]
        if ("L1", s) in RANKS and s in ("1999-00",): continue
        RANKS[("L1", s)].setdefault(key(clean(p[4])), (int(p[2]), int(p[3]), clean(p[4])))

def ents_map(prefix, season=None):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + (re.escape(season) if season else r"\S+") + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e[12] or "")
        if m: c[int(m.group(1))][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
L2MAP = ents_map("2. 분데스리가")      # 2. 분데스리가 순위별 값(다른 선수 자료에서 시즌과 무관하게 같은 값)
def half_up(x): return int(x + 0.5)
def mid(tab, r):
    if r in tab: return tab[r], False
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up(tab[a] + (tab[b] - tab[a]) * (r - a) / (b - a)), True
INTERP_USED = set()

def rank_model(lg, season, r, n):
    if lg == "L2":
        if r not in L2MAP: return None
        return L2MAP[r], f"2. 분데스리가 {season} {r}위"
    if lg == "L1":
        m = ents_map("분데스리가", season)
        if season <= "2006-07" and r not in m:   # 1998-99~2006-07은 모든 시즌이 같은 순위값(기존 자료 2000-01 표; 제 호베르투 선례)
            m = dict(m); m[r] = ents_map("분데스리가", "2000-01")[r]
        v, it = mid(m, r)
        if v is None: return None
        if it: INTERP_USED.add(("분데스리가", season, r, v))
        return v, f"분데스리가 {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
def eu_jul10(d):
    y = int(d[:4]); s = y if d[5:] >= "07-10" else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 순위표·기존 자료에 없는 상대(직접 추정) — judgments.md 6절
MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
exec(open(os.path.join(HERE, "man_schneider.py"), encoding="utf-8").read())

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid, lgcode):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    s = eu(d) if cid in ("CL", "CLQ", "UEFA") else eu_jul10(d)
    if (k, s) in MAN:
        e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    if (k, s) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for lg in ("L1", "L2"):
        t = RANKS.get((lg, s), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], lg); return res
    MISS.append((o, d, cid, s)); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, cid)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
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
    print("보간", sorted(INTERP_USED))
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print("score mismatches", SCORE_MISMATCH)
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    print(len(E), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E))
    sys.exit(0)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None): d.append("단판/합산")
    if a[10] != b[10]: d.append("연장")
    return d
NAMEPAT = re.compile(r"^Bernd Schneider$|^Schneider$")
CROSS = []
def same_team(x, r): return key(x[1]) == key(r[1]) or bool(toks(x[1]) & toks(r[1]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and NAMEPAT.match(x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(슈나이더 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x, r)]
            if hit: CROSS.append(("슈나이더 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x, r)]
            for x in hit:
                if not NAMEPAT.match(x[13] or ""): CROSS.append(("타인 도움 표기 다름(슈나이더 골)", b, r[9], r[4], x[13]))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x, r):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm, m) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
    mdates = {(m[0], key(m[1])) for m in M}
    for mm in om:
        for dd in (-1, 1):
            try: d2 = (datetime.date.fromisoformat(mm[0]) + datetime.timedelta(days=dd)).isoformat()
            except Exception: continue
            if (d2, key(mm[1])) in mdates and (mm[0], key(mm[1])) not in mdates:
                CROSS.append(("같은 상대 출전 날짜 하루 차이", b, mm[0], d2, mm[1]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and (key(x[1]) == key(j[2]) or toks(x[1]) & toks(j[2])):
                    CROSS.append(("TM 슈나이더 도움을 규칙대로 뺀 타인 골", b, x[9], x[4], x[13], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("jensb", "1998-07-01", "카를 차이스 예나", "1991~1998"), ("frasb", "1999-07-01", "아인트라흐트 프랑크푸르트", "1998~1999"),
         ("levsb", None, "바이어 레버쿠젠", "1999~2009")]
TM_CLUB = {"113": "jensb", "24": "frasb", "15": "levsb"}
def club_of(d):
    for k, u, n, y in CLUBS:
        if u is None or d < u: return k
CN = {}
for k, u, n, y in CLUBS: CN.setdefault(k, n)
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CN)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({(r[9]) for r in E if len(r) > 14})
JUL10 = {"jensb", "levsb"}
def season_of(d, club):
    y = int(d[:4])
    if club in JUL10: return eu_jul10(d)
    s = y if int(d[5:7]) >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
# 뺀 시즌 합계(TM API)
EXN_G = len(EXCL); EXN_GO = sum(int(g["goals"] or 0) for g in EXCL); EXN_A = sum(int(g["assists"] or 0) for g in EXCL)
EXN_BY = collections.Counter(g["competitionId"] for g in EXCL)
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    print("제외 시즌", EXN_G, EXN_GO, EXN_A, EXN_BY)
    print("score mismatch", SCORE_MISMATCH)
    for c in CROSS: print(c)
    print(sorted(collections.Counter(season_of(m[0], club_of(m[0])) for m in M).items()))
    for j in judg: print(j)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_schneider.py"), encoding="utf-8").read())

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6], r[13])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mdates = collections.Counter(m[0] for m in M)
for d, rs in by.items():
    gl = sorted([r for r in rs if r[0] == "g"], key=lambda r: (r[5] + r[6], r[4]))
    for a, b in zip(gl, gl[1:]):
        if b[5] < a[5] + 1 or b[6] < a[6]: problems.append(("스코어 역순", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
mm_ = {m[0]: m for m in M}
Gstart = {ldate(g): g["isStarting"] == "True" for g in GAMES}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > m[3] + 3 and not r[10] and Gstart[r[9]]: problems.append(("출전 분보다 늦은 기록", r, m))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const SNB_E={J(E)};\nconst SNB_M={J(M)};\nconst SNB_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "excluded_games": [[ldate(g), opp(g), g["competitionId"], int(g["playedMinutes"] or 0), int(g["goals"] or 0), int(g["assists"] or 0)] for g in sorted(EXCL, key=ldate)],
               "elo_sources": ELO_SRC, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
