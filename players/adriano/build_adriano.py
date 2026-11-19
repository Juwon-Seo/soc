#!/usr/bin/env python3
"""아드리아누 (Adriano Leite Ribeiro, Transfermarkt 5876): raw/ -> adriano.json + src/data/adr.js (판정 근거는 judgments.md)

  python3 players/adriano/build_adriano.py            # 파일 쓰기
  python3 players/adriano/build_adriano.py --debug    # Elo 출처 로그만 출력
  python3 players/adriano/build_adriano.py --stat     # 요약·판정·동료 대조
  python3 players/adriano/build_adriano.py --ties     # 합산 행

테베스 build 스크립트(players/tevez)를 바탕으로 함. 입력: raw/tm_games.csv(출전·분·날짜 후보), raw/tm_events.csv(리포트 골 목록),
raw/tm_match_info.csv(리포트 머리·다른 차전), raw/fotmob_tm_map.csv·fotmob_events.csv(2010-11 이후 골 대조), raw/ranks.txt(순위표),
elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료), tools/league_*_normalize.py(리그 시즌 목표 평균).
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime, io, contextlib
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "adr.js")
OUT_JSON = os.path.join(HERE, "adriano.json")
ME = "5876"
ME_KO = "아드리아누"

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
FMMAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv") if r["fotmob_utc"]}
BR_CLUBS = ("614", "585", "199", "679")

# ---------------------------------------------------------------- 날짜
# 브라질 클럽 경기: TM 리포트·일정 날짜는 중부 유럽 날짜라 저녁 경기가 하루 밀림 → 경기 시각(UTC)을 경기장 시간대로 바꾼 날짜.
#   FotMob 경기 시각이 있으면 그것(2011~2014). TM 시각이 12:00/13:00 UTC 정각이면 시각 미상 자리값 → 일정 날짜.
# 이탈리아 클럽 경기: TM 날짜와 바꾼 날짜가 모두 같음(빌드에서 확인).
DATE_FIX = {}
DATE_LOG = []
def _conv(utc, tz):
    return datetime.datetime.fromisoformat(utc.replace("Z", "+00:00")).astimezone(ZoneInfo(tz)).date().isoformat()
def _ldate(g):
    gid = g["gameId"]
    if gid in DATE_FIX: return DATE_FIX[gid], "fix"
    sched = g["date_local_schedule"]
    if g["club_id"] not in BR_CLUBS:
        conv = _conv(g["date_utc"], g["tz_used"])
        if conv != sched: sys.exit("유럽 날짜 불일치 " + gid)
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

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "BRA1"}
STATE = {"BCP1", "BCPF", "BRCG", "BRCR", "BRCF", "BRPR"}   # 주 선수권(파울리스타·카리오카·파라나엔시): 국내컵 하위 라운드 비중(네이마르·비니시우스 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid in ("CIT", "BRC"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "SCI": return "df"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "CLQ": return "clq"
    if cid == "UEFA":   # UEFA컵 1라운드 = 유로파 예선, 2라운드·3라운드 = 유로파 토너먼트(크레스포·비에리 선례)
        if r.startswith("first round"): return "elq"
        if r.startswith(("second round", "3rd round", "fourth", "last 16", "quarter")): return "elk"
        sys.exit("UEFA 라운드 " + rnd)
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"
    if cid == "CMER":   # 코파 메르코수르 = 남미 2부 대회 비중(주니뉴·리켈메·포를란 선례)
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
    if cid in ("CL", "CLQ", "UEFA", "CIT"): return (1, 1)
    if cid == "CLI":
        if d < "2005-01-01": return (0, 0)
        if r.startswith("final") and d >= "2008-01-01": return (0, 1)
        return (1, 0)                                    # 2005~: 원정 다득점 있고 연장 없이 승부차기(리켈메·테베스 선례)
    if cid in ("CMER", "BRC"): return (1, 0)            # 주니뉴·네이마르·호나우두 선례(메르코수르 규정은 추정)
    if cid in STATE: return (0, 0)                      # 주 선수권 두 경기 라운드: 원정 다득점·연장 없음(네이마르 파울리스타 선례)
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
EST = []
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    row = [ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g))]
    if g["playedMinutes"]:
        row.append(int(g["playedMinutes"]))
    else:   # 출전 분 자료 없음(플라멩구 2000 교체 출전 4경기) → 90분 추정
        row += [90, 1]; EST.append((ldate(g), opp(g), g["gameId"]))
    M.append(row)

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

def assist_reason(e):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t.startswith("Handball"): return "핸드볼 반칙(상대 PK 허용)"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    return None   # 모두 2014년 8월 이전이라 Transfermarkt 단일 출처 허용(클로제·인시녜·리켈메·크레스포 선례)

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
        if e["scorer_id"] == ME and is_og(e): sys.exit("자책골 " + gid)
        if is_a and sd != side:
            judg.append(("도움 아님(상대 골, 아드리아누 반칙으로 준 PK)", ldate(g), opp(g), e["minute"], e["scorer"], e["assist_type"])); continue
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if e["goal_desc"].startswith("Deflected"):
                judg.append(("도움 유지(패스 뒤 득점자 슈팅이 굴절돼 들어감, 도움 유형은 패스)", ldate(g), opp(g), e["minute"], e["scorer"]))
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk and e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
            if e["goal_desc"] == "Penalty rebound": judg.append(("PK 리바운드 골(PK 아님)", ldate(g), opp(g), e["minute"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

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
MANUAL_ALIAS = {"inter milan": "inter", "ac parma": "parma fc", "ca bragantino": "ca bragantino"}
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
    if b in ("hon.js", "adr.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss", "us",
        "athletic", "milan", "inter", "madrid", "moscow", "paulista", "paulo", "ca", "cs", "deportivo", "universidad", "san", "fk", "vfl", "bv",
        "nacional", "chile", "verona", "cska", "donetsk", "1909", "1907", "1898", "1893", "1993", "rangers", "sao"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
SA_DOM = {"BRA1", "BRC", "CLI", "CMER"} | STATE
def same_match(o, d, cid):
    if cid in SA_DOM:   # 남미 대회는 같은 이름 다른 팀이 많아 정확한 이름(별칭) 일치만
        cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    else:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
        if not cand and cid in ("IT1", "CIT", "SCI"):   # 이탈리아 팀 이름 표기 차이만 느슨하게(유럽 대회는 CSKA 모스크바/소피아처럼 같은 날 다른 팀이 있어 정확한 이름만)
            cand = [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 리그 시즌 목표 평균(v1.216~v1.219 도구)
def load_tool(name):
    Gd = {"__file__": os.path.join(ROOT, "tools", name), "__name__": "x"}
    src = open(Gd["__file__"], encoding="utf-8").read().rsplit("if '--apply' in sys.argv:", 1)[0]
    a = sys.argv; sys.argv = ["x"]
    with contextlib.redirect_stdout(io.StringIO()): exec(compile(src, name, "exec"), Gd)
    sys.argv = a
    return Gd
WT = load_tool("league_world_normalize.py")
XT = load_tool("league_second_tier_x.py")
def half_up(x): return int(x + 0.5)
def bra_v(y, r, n): return half_up(WT["target"]("BRA", y) + WT["SD"]["BRA"] * WT["cv"](r, n))
def brb_v(y, r, n): return half_up(XT["target2"]("브라질 세리에 B", y) + XT["SD2"] * XT["cv"](r, n))
BRA_SHIFT = lambda y: WT["target"]("BRA", y) - WT["target"]("BRA", 2000)   # 3부·4부 이하 평탄값(1253·1200)을 옮기는 양(기존 값과 같은 방식)

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
# 2000 브라질 1부: TM 표(29팀)는 1위가 크루제이루 → RSSSF 'Copa João Havelange 2000' 블루 모듈 25팀 1단계 순위(주니뉴 자료와 같은 방식, judgments.md)
BLUE00 = {"Clube de Regatas Vasco da Gama": 5, "São Paulo Futebol Clube": 6, "Santos FC": 14, "Santa Cruz FC (PE)": 25, "Goiás EC": 4,
          "Coritiba Foot Ball Club": 23, "Sociedade Esportiva do Gama (DF)": 22}
RANKS[("BRA1", "2000")] = {key(k): (v, 25, k) for k, v in BLUE00.items()}

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

def rank_model(lg, season, v):
    r, n, nm = v
    if lg == "BRA1":
        return bra_v(int(season), r, n), f"브라질 세리에 A {season} {r}위" + (f"/{n}팀" if n != 20 else "")
    if lg == "BRA2":
        return brb_v(int(season), r, n), f"브라질 세리에 B {season} {r}위"
    if lg == "IT1":
        m = ents_map("세리에A", season); x, it = mid(m, r)
        if x is None: return None
        return x, f"세리에A {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
def seasons_for(cid, d, o):
    if cid in SA_DOM: return [d[:4]]
    return [eu(d), d[:4]]   # 달력 연도 리그 팀(CSKA 등)은 연도 키
def lg_cands(cid, d, o):
    if cid in SA_DOM: return [("BRA1", d[:4]), ("BRA2", d[:4])]
    return [("IT1", eu(d))]

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
MAN_HIT = set()

def opp_elo(o, d, cid):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    seasons = seasons_for(cid, d, o)
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); MAN_HIT.add((o, s, e, lv)); return e, lv
    for lg, s in lg_cands(cid, d, o):
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
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["adriano_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "pen" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))
FM_ASSIST = [(gid, r["time"], r["scorer"]) for gid, rs in FME.items() for r in rs if r["adriano_assist"] == "1"]

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
NAME_RE = r"Adriano(?! (Correia|Claro|Gabiru|Michael|Pimenta))"
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(NAME_RE, x[13] or "") and x[9] in G_BYDATE:
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(아드리아누 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("아드리아누 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
# 아드리아누 도움을 뺀 경기의 동료 골
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 아드리아누 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
# 동료 자료에 있는 골에 TM이 아드리아누 도움을 적었는데 동료 행에 다른 도움자 표시가 있는지는 동료 자료에 없음(골 행에는 도움자 없음)
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("flaad", "2001-08-11", "플라멩구", "플라멩구", "2000~2001"), ("intad", "2002-01-11", "인테르", "인테르", "2001~2002"),
         ("fioad", "2002-07-01", "피오렌티나", "피오렌티나", "2002"), ("parad", "2004-01-21", "파르마", "파르마", "2002~2004"),
         ("intad", "2008-01-01", "인테르", "인테르", "2004~2007"), ("spaad", "2008-06-30", "상파울루", "상파울루", "2008"),
         ("intad", "2009-05-06", "인테르", "인테르", "2008~2009"), ("flaad", "2010-07-01", "플라멩구", "플라멩구", "2009~2010"),
         ("romad", "2011-03-25", "AS 로마", "로마", "2010~2011"), ("corad", "2014-01-06", "코린치안스", "코린치안스", "2011~2012"),
         ("capad", None, "아틀레치쿠 파라나엔시", "아틀레치쿠 PR", "2014")]
TM_CLUB = {"614": "flaad", "46": "intad", "430": "fioad", "130": "parad", "585": "spaad", "12": "romad", "199": "corad", "679": "capad"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
SCAL = ("flaad", "spaad", "corad", "capad")
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in SCAL: return str(y)
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
for g in GAMES:   # 이탈리아 클럽: 8월 1일 기준 시즌 = TM 시즌
    if g["club_id"] not in BR_CLUBS and season_of(ldate(g), "x")[:4] != g["seasonId"]: sys.exit("시즌 불일치 " + g["gameId"])
STINTS = [("플라멩구(2000~2001)", "2001-08-11"), ("인테르(2001)", "2002-01-11"), ("피오렌티나", "2002-07-01"), ("파르마", "2004-01-21"),
          ("인테르(2004~2007)", "2008-01-01"), ("상파울루", "2008-06-30"), ("인테르(2008~2009)", "2009-05-06"), ("플라멩구(2009~2010)", "2010-07-01"),
          ("AS 로마", "2011-03-25"), ("코린치안스", "2014-01-06"), ("아틀레치쿠 파라나엔시", "9999")]
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
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A, UNTYPED)
    for j in judg: print(j)
    for c in CROSS: print(c)
    print("FM", FM_CMP, FM_ASSIST)
    print("score mismatch", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("dates changed", len(DATE_LOG), collections.Counter(x[3] for x in DATE_LOG))
    for x in DATE_LOG: print("  ", x)
    for o, e, lv in MAN_USED: print("MAN", o, e, lv)
    print("EST", EST)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_adriano.py"), encoding="utf-8").read())   # NOTE_LINES
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
    if not (1000 <= r[2] <= 2100): problems.append(("Elo 범위", r))
mm_ = {m[0]: m for m in M}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > 90 and not r[10] and not (r[11] and str(r[11]).startswith("90+")): problems.append(("90분 넘는 골 시각", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const ADR_E={J(E)};\nconst ADR_M={J(M)};\nconst ADR_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "date_changes": DATE_LOG, "estimated_minutes": EST, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
