#!/usr/bin/env python3
"""후안 로만 리켈메 (Transfermarkt 3854): raw/ -> riquelme.json + src/data/riq.js (판정 근거는 judgments.md)

  python3 players/riquelme/build_riquelme.py            # 파일 쓰기
  python3 players/riquelme/build_riquelme.py --debug    # Elo 출처 로그만 출력
  python3 players/riquelme/build_riquelme.py --stat     # 요약·동료 대조
  python3 players/riquelme/build_riquelme.py --ties     # 합산 행

입력: raw/tm_games.csv(출전·분·날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv(2010-11 이후 골 대조), raw/ranks.txt·raw/tables/*.html(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
스크래치 복사본에서는 RIQ_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime, html as HTML

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("RIQ_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "riq.js")
OUT_JSON = os.path.join(HERE, "riquelme.json")
ME = "3854"
ME_KO = "후안 로만 리켈메"

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

# ---------------------------------------------------------------- 날짜
# TM 일정·리포트 날짜는 중부 유럽 시간이라 남미 저녁 경기(UTC 22~02시)는 하루 밀림. TM API 경기 시각(UTC)이 실제 킥오프면
# UTC−3(아르헨티나)로 바꾼 날짜를 씀(남미 원정도 UTC−3~−5라 결과가 같음; 2010-11 이후 FotMob UTC 시각과 일치).
# 시각이 중부 유럽 자정(UTC 22:00/23:00 정각)이나 12:00·13:00 정각이면 시각 미상 자리값 → 일정 날짜 그대로.
def _lastsun(y, m):
    x = datetime.date(y, m, 31)
    while x.weekday() != 6: x -= datetime.timedelta(1)
    return x
def _cet_mid_utc_hour(d):   # 그 날짜 0시(중부 유럽)를 UTC 시각으로
    return 22 if _lastsun(d.year, 3) <= d < _lastsun(d.year, 10) else 23
DATE_FIX = {"1169665": "2001-11-27",   # 2001 인터콘티넨털컵(도쿄 11.27 19:20 현지; TM UTC 시각 오류, 피사로 선례·영어 위키백과)
            "1169664": "2000-11-28"}   # 2000 인터콘티넨털컵(도쿄 11.28, 피구·라울 선례)
DATE_LOG = []
def _ldate(g):
    gid = g["gameId"]
    if gid in DATE_FIX: return DATE_FIX[gid]
    sched = g["date_local"]
    u = datetime.datetime.fromisoformat(g["date_utc"])
    t = (u.hour, u.minute)
    if t in ((12, 0), (13, 0)): return sched
    sd = datetime.date.fromisoformat(sched)
    if u.minute == 0 and u.hour == _cet_mid_utc_hour(sd) and u.date() == sd - datetime.timedelta(1): return sched
    if g["club_id"] in ("131", "1050"):   # 스페인 클럽: 리포트 날짜(현지)
        return sched
    loc = (u - datetime.timedelta(hours=3)).date().isoformat()
    if loc != sched: DATE_LOG.append((gid, sched, loc, g["date_utc"][:16], g["opponent"]))
    return loc
LD = {gid: _ldate(g) for gid, g in G.items()}
def ldate(g): return LD[g["gameId"]]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용(아르헨티노스 2014 TM 도움 0개)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ARG1", "ARGC", "ES1", "AR2T", "MARG"}   # MARG = 아페르투라 2008 우승 결정 3팀 리그(partidos definición)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("CDR", "ARCA"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "RECO": return "df"           # 레코파 수다메리카나 = 슈퍼컵류(호나우지뉴 선례)
    if cid == "WEPO": return "cwc"          # 인터콘티넨털컵
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "CLQ": return "clq"
    if cid == "UI": return "elq"            # 인터토토 = 유로파 예선(토레스·포를란 선례)
    if cid == "UEFA":
        if r.startswith("group"): return "elg"
        if r.startswith("first round"): return "elq"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                        # 2라운드·3라운드·'intermediate stage'·16강·8강
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"
    if cid in ("CS", "CMER", "SCSA"):       # 수다메리카나·메르코수르(주니뉴·포를란 선례)·수페르코파(호나우두 선례)
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
    if cid in ("CL", "CLQ", "UEFA", "UI"): return (1, 1)
    if cid == "CDR": return (1, 1)
    if cid == "CLI":
        if d < "2005-01-01": return (0, 0)          # 2004년까지: 원정 다득점·연장 없음, 바로 승부차기
        if r.startswith("final") and d >= "2008-01-01": return (0, 1)   # 2008년부터 결승은 원정 다득점 없이 연장
        return (1, 0)                               # 2005년부터 원정 다득점, 연장 없이 승부차기
    if cid in ("CS", "CMER"): return (1, 0)
    if cid == "RECO": return (0, 1)                 # 2008 레코파: 결승이라 리베르타도레스 2008 결승 규정(원정 다득점 없음·연장) 준용(추정)
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
    if MI[gid]["other_leg_id"] in MI and G.get(MI[gid]["other_leg_id"], {}).get("gameState") == "penalty_shootout":
        sys.exit("다른 차전이 승부차기 " + gid)
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

def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if d >= GAP: return "2014.8 이후 단일 출처(판정 없음)"
    return None

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
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))

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
MANUAL_ALIAS = {"inter milan": "inter", "club atletico gimnasia y esgrima la plata": "club de gimnasia y esgrima la plata",
                "deportivo toluca": "deportivo toluca", "toluca": "deportivo toluca"}
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
    if b in ("hon.js", "riq.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "paulista", "paulo", "ca", "cs", "deportivo", "deportes", "universidad", "san", "santa", "fk", "vfl", "bv",
        "racing", "arsenal", "juniors", "plate", "river", "nacional", "independiente", "estudiantes", "union", "boca", "gimnasia", "esgrima", "lorenzo", "almagro"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
SA_DOM = {"ARG1", "ARGC", "AR2T", "ARCA", "MARG", "CLI", "CS", "CMER", "SCSA", "RECO"}
def same_match(o, d, cid):
    if cid in SA_DOM:   # 남미 대회는 같은 이름 다른 팀이 많아 정확한 이름(별칭) 일치만
        cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    else:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
# 아페르투라 2008: 승점 같은 세 팀 결정전(2008.12) 뒤 최종 순위 보카 1·티그레 2·산로렌소 3(결정전 득실 +1·0·−1; 리켈메 2008.12.20 경기 포함)
RANKS[("ARG1", "2008-09")][key("Club Atlético Tigre")] = (2, 20, "Club Atlético Tigre")
RANKS[("ARG1", "2008-09")][key("CA San Lorenzo de Almagro")] = (3, 20, "CA San Lorenzo de Almagro")

def tm_tables(fn):
    """TM 순위표 html의 표들(조별이면 여러 개): [[(순위, 짧은 이름, 승점, 득실, 득점), …], …]"""
    t = open(os.path.join(RAW, "tables", fn), encoding="utf-8").read()
    out = []
    for m in re.finditer(r'<table class="items">', t):
        body = t[m.start():].split("</table>")[0]
        rows = []
        for r in re.findall(r"<tr.*?</tr>", body, re.S):
            c = [HTML.unescape(re.sub("<[^>]+>", "", x)).strip() for x in re.findall(r"<td.*?</td>", r, re.S)]
            if len(c) >= 10 and c[0].isdigit():
                gf, ga = map(int, c[7].split(":")); rows.append((int(c[0]), c[2], int(c[9]), gf - ga, gf))
        out.append(rows)
    return out

def annual(code_a, code_c, season, fa, fc, n_expect):
    """두 반시즌 표(조별 포함)의 승점 합 → 연간 순위(득실차·다득점 순). 짧은 이름은 ranks.txt의 같은 순서 정식 이름으로."""
    def full(code, fn):
        ts = tm_tables(fn); names = {}
        rk = RANKS[(code, season)]
        if len(ts) == 1:
            order = sorted(rk.values())
            for (r, sh, *_), (rr, n, nm) in zip(ts[0], order): names[sh] = nm
        else:
            for gi, tab in enumerate(ts):
                L = sorted(v for k2, v in RANKS[(code, season)].items() if False)  # 자리
            # 조별: ranks.txt 의 group1..k 를 다시 읽음
            grp = collections.defaultdict(list)
            with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
                for line in f:
                    p = line.rstrip("\n").split("|")
                    if p[0] == code and p[1].startswith(season + " group"): grp[p[1]].append((int(p[2]), p[4]))
            keys = sorted(grp)
            if len(keys) != len(ts): sys.exit("조 수 다름 " + fn)
            for k2, tab in zip(keys, ts):
                for (r, sh, *_), (rr, nm) in zip(tab, sorted(grp[k2])): names[sh] = nm
        pts = {}
        for tab in ts:
            for r, sh, p, gd, gf in tab: pts[names[sh]] = (p, gd, gf)
        return pts
    A = full(code_a, fa); C = full(code_c, fc)
    tot = collections.defaultdict(lambda: [0, 0, 0])
    for D in (A, C):
        for nm, v in D.items():
            for i in range(3): tot[key(nm)][i] += v[i]
    order = sorted(tot, key=lambda k2: (-tot[k2][0], -tot[k2][1], -tot[k2][2]))
    if len(order) != n_expect: print("  [연간 표 팀 수]", season, len(order))
    return {k2: (i + 1, len(order)) for i, k2 in enumerate(order)}, tot

MEX = {s: annual("MEXA", "MEX1", s, f"tm_MEXA_{y}.html", f"tm_MEX1_{y}.html", 18)[0] for s, y in (("2006-07", 2006), ("2007-08", 2007), ("2012-13", 2012))}
URU, URU_PTS = annual("URU1", "URUC", "2012-13", "tm_URU1_2012.html", "tm_URUC_2012.html", 16)

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
def half_up(x): return int(x + 0.5)

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

# 아르헨티나 반시즌 표 이름(ranks.txt 키 → 대회 이름·연도)
def arg_tour(lg, season):
    y0 = int(season[:4])
    if lg == "ARG1":
        return ("이니시알" if y0 >= 2012 else "아페르투라"), y0
    return ("피날" if y0 >= 2012 else "클라우수라"), y0 + 1

def rank_model(lg, season, r, n):
    if lg in ("ARG1", "ARGC"):
        t, y = arg_tour(lg, season)
        return half_up(1583 + 63 * curve(r, n)), f"아르헨티나 1부 {t} {y} {r}위"
    if lg == "BRA1":
        return half_up(1598 + 63 * curve(r, n)), f"브라질 세리에 A {season} {r}위"
    if lg == "MEXY":
        return half_up(1604.25 + 73.41 * curve(r, n)), f"멕시코 1부 {season} 아페르투라·클라우수라 합산 {r}위 (추정: 조별 표 승점 합, 공식 순위표 아님)"
    if lg == "URUA":
        return half_up(1540 + 63 * curve(r, n)), f"우루과이 1부 {season} 연간 {r}위"
    if lg == "ES1":
        m = ents_map("라리가", season); v, it = mid(m, r)
        if v is None: return None
        return v, f"라리가 {season} {r}위"
    if lg == "GB1":
        m = ents_map("프리미어리그", season); v, it = mid(m, r)
        if v is None: return None
        return v, f"프리미어리그 {season} {r}위"
    if lg == "IT1":
        m = ents_map("세리에A", season); v, it = mid(m, r)
        if v is None: return None
        return v, f"세리에A {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
ARG_USE = collections.defaultdict(set)
CAL = {"ARG1", "ARGC", "AR2T", "ARCA", "MARG", "CLI", "CS", "CMER", "SCSA", "RECO"}

def seasons_for(cid, d, o):
    y = d[:4]
    if cid in CAL:
        k = key(o)
        if k in MEX_KEYS: return [eu(d)]      # 멕시코 팀(리베르타도레스): 유럽식 시즌
        if k in URU_KEYS and eu(d) == "2012-13": return [eu(d)]
        return [y]
    if cid == "WEPO": return [eu(d)]
    return [eu(d)]

MEX_KEYS = {k for s in MEX for k in MEX[s]}
URU_KEYS = set(URU)

def arg_cands(d):
    y = int(d[:4]); mo = int(d[5:7])
    if y <= 2012 and not (y == 2012 and mo >= 7):
        # 2~7월 = 클라우수라(그해), 8~12월 = 아페르투라(그해)
        if mo <= 7: return [("ARGC", f"{y-1}-{str(y)[2:]}")]
        return [("ARG1", f"{y}-{str(y+1)[2:]}")]
    if mo <= 7: return [("ARGC", f"{y-1}-{str(y)[2:]}")]
    return [("ARG1", f"{y}-{str(y+1)[2:]}")]

def lg_cands(cid, d, o, sid=None):
    k = key(o); y = d[:4]
    if cid in ("ARG1", "ARGC"):   # 리그 경기는 그 경기가 속한 대회(Transfermarkt 시즌 id) 순위표
        return [(cid, f"{sid}-{str(int(sid) + 1)[2:]}")]
    if k in MEX_KEYS and eu(d) in MEX: return [("MEXY", eu(d))]
    if k in URU_KEYS and eu(d) == "2012-13": return [("URUA", eu(d))]
    if cid in CAL:
        return arg_cands(d) + [("BRA1", y)]
    s = eu(d)
    return [("ES1", s), ("GB1", s), ("IT1", s)]

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
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for lg, s in lg_cands(cid, d, o, sid):
        if lg == "MEXY": t = {kk: v for kk, v in MEX.get(s, {}).items()}
        elif lg == "URUA": t = URU
        else: t = RANKS.get((lg, s), {})
        if k in t:
            v = t[k]; r, n = v[0], v[1]
            res = rank_model(lg, s, r, n)
            if res and res[0]:
                if lg in ("ARG1", "ARGC"): ARG_USE[(k, d[:4])].add(res)
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

# ---------------------------------------------------------------- 직접 추정(MAN)
def b2(r, n): return half_up(1355 + SD2 * curve(r, n))   # 아르헨티나 2부(디발라 선례 평균 1355, SD2)
man("Blooming Santa Cruz", "2000", 1400, "볼리비아 1부 상위 팀 (추정, 1998·1999 볼리비아 우승팀; 다른 선수 자료 볼리비아 상위 팀 1400과 같음)")
man("Club Deportivo Oriente Petrolero", "2001", 1400, "볼리비아 1부 상위 팀 (추정, 다른 선수 자료 볼리비아 상위 팀 1400과 같음)")
man("Bolívar La Paz", "2007", 1400, "볼리비아 상위 팀 (추정, 다른 선수 자료 볼리바르 1400과 같음)")
man("CD El Nacional", "2000", 1450, "에콰도르 1부 상위 팀 (추정, 다른 선수 자료 엘 나시오날 1450과 같음)")
man("CA Peñarol", "2000", 1600, "우루과이 1부 상위 팀 (추정, 다른 선수 자료 페냐롤 1997·1999 1600과 같음)")
man("Junior FC", "2001", 1500, "콜롬비아 1부 상위 팀 (추정, 다른 선수 자료 칠레·파라과이 상위 팀 1500과 같은 수준)")
man("Cúcuta Deportivo", "2007", 1500, "콜롬비아 1부 2006 피날리사시온 우승팀 (추정, 다른 선수 자료 남미 상위 팀 1500과 같은 수준)")
man("Club Libertad Asunción", "2007", 1500, "파라과이 1부 상위 팀 (추정, 다른 선수 자료 리베르타드 1500과 같음)")
man("Club Guaraní", "2009", 1450, "파라과이 1부 2009 (추정, 다른 선수 자료 나시오날 아순시온 2009 1450과 같음)")
man("FUA Maracaibo", "2008", 1380, "베네수엘라 1부 (추정, 다른 선수 자료 베네수엘라 2위 1380과 같음)")
man("Zamora FC", "2012", 1380, "베네수엘라 1부 (추정, 다른 선수 자료 사모라 2013-14 1380과 같음)")
man("Unión Española", "2012", 1480, "칠레 1부 2012 (추정, 다른 선수 자료 칠레 상위 팀 1480~1500 수준; 2012 순위표 미확보)")
man("CD Cobreloa", "2001", 1490, "칠레 1부 2001 5위 (추정, 다른 선수 자료 칠레 2001 4위 콜로콜로 1500보다 조금 낮게)")
man("Novelda CF", "2002-03", 1350, "스페인 3부(세군다 B) 2002-03 (추정, 다른 선수 자료 스페인 3부 1350과 같음)")
man("CB Ramón Santamarina", "2012", 1253, "아르헨티나 3부(토르네오 아르헨티노 A) 2011-12 (추정, 근거 약함; 다른 선수 자료 아르헨티나 3부 1253과 같음)")
man("CS Deportivo Merlo", "2012", 1328, "아르헨티나 2부 2011-12 14위 (추정)")   # 디발라 자료 같은 팀·시즌 값(메를로 2011-12 = 프리메라 B 나시오날)
man("CA Estudiantes", "2014", 1253, "아르헨티나 3부(프리메라 B 메트로폴리타나) 2014 (추정, 근거 약함; 다른 선수 자료 아르헨티나 3부 1253과 같음)")
man("CA Boca Unidos", "2014", b2(7, 11), "아르헨티나 2부 2014 A조 7위/11팀 (추정)")
man("Racing Club", "2014", half_up(1583 + 63 * curve(1, 20)), "아르헨티나 1부 트란시시온 2014 1위 (우승팀; 순위표 미수집, 우승은 경기 기사로 확인)")
man("Lokomotiv Moskau", "2002-03", 1590, "러시아 2002 1위 (추정, 다른 선수 자료 로코모티프 2002 값과 같음)")
man("Torpedo Moskau", "2003-04", 1530, "러시아 2003 8위 (추정, 다른 선수 자료 스파르타크 2003 10위 1520보다 조금 높게)")
man("Club Brugge KV", "2002-03", 1620, "벨기에 2002-03 1위 (추정, 다른 선수 자료 브뤼허 1위권 1620과 같음)")
man("Legia Warszawa", "2002-03", 1460, "폴란드 2002-03 4위 (추정, 다른 선수 자료 레기아 2위 1465·3위 1480보다 조금 낮게)")
man("Trabzonspor", "2003-04", 1660, "튀르키예 2003-04 2위 (추정, 다른 선수 자료 튀르키예 2위 1660과 같음)")
man("Steaua Bucharest", "2004-05", 1500, "루마니아 2004-05 1위 (추정, 다른 선수 자료 스테아우아 1450~1520 사이)")
man("CA Douglas Haig", "2014", b2(9, 11), "아르헨티나 2부 2014 A조 9위/11팀 (추정)")

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

# 1996.11.24 보카 6-0 우라칸(Transfermarkt에 없는 경기, 사용자 결정으로 추가): 출전은 90분 추정,
# 골 82분·골 전 스코어는 RSSSF arg97 득점 순서(Toresani 15, Rambert 40 PK, Fabbri 45, Cedres 67, Latorra 71, Riquelme 82) → 5-0.
# 상대 Elo: RSSSF 아페르투라 1996 최종 순위 우라칸(BA) 19위/20팀(승점 16, 데포르티보 에스파뇰과 같고 득실차로 19위)을 아르헨티나 1부 모형에.
EXTRA_M = [["1996-11-24", "CA Huracán", "lg", 90, 1]]
EXTRA_E = [["g", "CA Huracán", half_up(1583 + 63 * curve(19, 20)), "lg", 82, 5, 0, 0, 0, "1996-11-24", 0, 0, "아르헨티나 1부 아페르투라 1996 19위", 0]]
M = EXTRA_M + M
E.extend(EXTRA_E)
ELO_SRC["순위표+리그 모형"] += 1

# 아르헨티나: 같은 팀이 한 해 두 대회 값이 다르면 평균(포를란·팔카오 선례; 통합표 시즌 키가 연도)
ARG_AVG = []
for (k, y), vs in ARG_USE.items():
    if len({v[0] for v in vs}) > 1:
        vv = sorted(vs, key=lambda v: v[1])
        avg = half_up(sum(v[0] for v in vv) / len(vv))
        lv = f"아르헨티나 1부 {y} (추정, " + "·".join(re.sub(r"^아르헨티나 1부 ", "", v[1]) for v in vv) + " 값 평균)"
        ARG_AVG.append((k, y, avg, [v[0] for v in vv]))
        for r in E:
            if key(r[1]) == k and r[9][:4] == y and r[12].startswith("아르헨티나 1부"):
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
    print("날짜 고침:", len(DATE_LOG))
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print("score mismatches", SCORE_MISMATCH)
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["riquelme_scorer"] == "1"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["minute"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["minute"]) + int(x["extra_minute"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goal_description"] or "").lower()
        a = mins(t["minute"])[0]; b = int(f["minute"]) + int(f["extra_minute"] or 0)
        if tp != fp or abs(a - b) > 1: FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["minute"], f["extra_minute"], f["goal_description"]))
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
        if x[0] == "a" and re.search(r"Riquelme", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(리켈메 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("리켈메 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 리켈메 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
# 같은 상대·하루 차이(날짜 기준 차이) 경기: 다른 선수 자료가 같은 경기를 다른 날짜로 적었는지
for b, (oe, om) in OTHERS.items():
    for mm in om:
        for m in M:
            if mm[0] != m[0] and abs((datetime.date.fromisoformat(mm[0]) - datetime.date.fromisoformat(m[0])).days) == 1 and key(mm[1]) == key(m[1]) and mm[2] == m[2]:
                CROSS.append(("같은 상대 하루 차이(같은 경기일 수 있음)", b, m[0], mm[0], m[1]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("bocriq", "2002-07-01", "보카 주니어스", "보카", "1996~2002"), ("barriq", "2003-08-01", "바르셀로나", "바르셀로나", "2002~2003"),
         ("vilriq", "2007-01-15", "비야레알", "비야레알", "2003~2007"), ("bocriq", "2014-07-01", "보카 주니어스", "보카", "2007~2014"),
         ("argriq", None, "아르헨티노스 주니어스", "아르헨티노스", "2014")]
TM_CLUB = {"189": "bocriq", "131": "barriq", "1050": "vilriq", "1030": "argriq"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
CN = {}
for k, u, n, sh, y in CLUBS: CN.setdefault(k, n)
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
SCAL = ("bocriq", "argriq"); JUL10 = ("vilriq",)
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in SCAL: return str(y)
    if club in JUL10: s_ = y if d[5:] >= "07-10" else y - 1
    else: s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
# 클럽별(보카 두 시기 나눔)
def stint(d):
    if d < "2002-07-01": return "보카 주니어스(1996~2002)"
    if d < "2003-08-01": return "바르셀로나"
    if d < "2007-01-15": return "비야레알"
    if d < "2014-07-01": return "보카 주니어스(2007~2014)"
    return "아르헨티노스 주니어스"
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in ["보카 주니어스(1996~2002)", "바르셀로나", "비야레알", "보카 주니어스(2007~2014)", "아르헨티노스 주니어스"])
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
DATE_CHG = [x for x in DATE_LOG]
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A, UNTYPED)
    for j in judg: print(j)
    for c in CROSS: print(c)
    print("FM", FM_N, FM_G, FM_CMP)
    print("score mismatch", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("dates changed", len(DATE_CHG), "G/A dates changed", sorted({x[1] + "→" + x[2] for x in DATE_CHG if any(r[9] == x[2] for r in E)}))
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
def exl(kind):
    return ", ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]}" for j in EXJ if j[5].startswith(kind))
NOTE_LINES = [
    f"후안 로만 리켈메(보카 주니어스·바르셀로나·비야레알·보카 주니어스·아르헨티노스 주니어스)의 클럽 공식 경기 {NG}경기({d_(first[0])} 우라칸전 ~ {d_(last[0])} 더글러스 하이그전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·아르헨티나 대표팀(A·U-20·올림픽) 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{k} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(Transfermarkt에 없는 1996.11.24 우라칸전 1경기만 90분 추정), 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있거나 리그 밖 대회인 경기 331개; 리켈메 골·도움 수는 선수 경기 성적과 경기마다 같음). 2010-11 이후 골 {FM_G}개({FM_N}경기)는 FotMob 경기 기록과 대조함(골 수·순서·PK 같음; 2011.8.15 우니온전 85분(FotMob 83분)·2014.3.30 리버전 67분(FotMob 69분)은 Transfermarkt 분을 씀). 그 전은 경기별 두 번째 출처가 없고, 리그 골 수는 RSSSF 시즌별 득점 기록과 대조함(1999-00·2000-01·2001-02·2007-08·2008-09 리그 골 수 같음)",
    "아르헨티나 1부·2부 경기는 소속 팀이 프로 리그에 있던 시즌이라 모두 넣음(아르헨티노스 주니어스 2014는 2부 프리메라 B 나시오날, 프로 리그)",
    f"경기 수 차이: Transfermarkt의 보카 경기 기록은 1997.2.23부터라 1996-97 아페르투라(데뷔 1996.11.10)의 리그 경기가 거의 없음(위키백과 영어·스페인어 1996-97 22경기 4골 vs Transfermarkt 6경기 1골). 이 중 1996.11.24 우라칸전(보카 6-0)은 RSSSF 경기 기록(득점자·분), 영어 위키백과 1996-97 시즌 문서, 엘 그라피코 경기 기사(선발 출전)로 출전과 골이 확인돼 넣음: 출전 시간 기록이 없어 90분으로 추정, 골은 RSSSF 82분(영어 위키백과도 82분, 엘 그라피코는 후반 34분 = 79분으로 3분 차이), 골 전 스코어 5-0은 RSSSF 득점 순서(토레사니 15·람베르트 40 PK·파브리 45·세드레스 67·라토레 71·리켈메 82). 나머지 약 15경기 3골은 경기별 출전 기록이 없어 넣지 않음. 그 밖에 위키백과와 경기 수가 1~2경기 다른 시즌(보카 1997-98·2008-09·2009-10·2011-12·2012-13, 비야레알 2003-04 코파 델 레이)은 Transfermarkt 기준(위키백과 클럽 합계 596경기 150골 vs 이 계산기 {NG}경기 {NGo}골)",
    f"도움: 2014년 8월 이전은 Transfermarkt 경기 리포트 단일 출처(클로제·인시녜·포를란 선례). Transfermarkt 도움 {TM_A}개에서 슈팅 리바운드('Shot on goal') {sum(1 for j in EXJ if j[5].startswith('슈팅'))}개({exl('슈팅')})를 빼 {NA}개. PK 유도·상대 자책골 유도·본인 PK 골의 본인 도움 표기는 없음. 도움 유형 칸이 빈 {UNTYPED}개는 일반 도움으로 셈. 아르헨티노스 주니어스(2014.8~12)는 Transfermarkt 도움 0개(스페인어 위키백과는 2개라 적지만 경기별 근거가 없어 넣지 않음). 스페인어 위키백과의 시즌 도움 합계(보카 119·비야레알 44 등)는 경기별로 나눌 수 없어 쓰지 않음",
    "골: 자책골 없음. 1996.11.24 우라칸전 골만 RSSSF 기준(PK 아님), 나머지 PK 골은 Transfermarkt 골 유형 'Penalty'(선수 경기 성적 PK 골 수와 경기마다 같음). 골 전 스코어는 리포트 골 순서대로 셈. 리포트 머리 스코어가 틀린 2000.8.27 뉴웰스전(머리 0:1, 골 목록 1-3 = RSSSF 1-3)과 Ferro 골 하나가 빠진 1998.8.9 페로전(머리 2:4, 목록 1-4; 리켈메 골은 전반 45분 0-3에서 나와 영향 없음)은 골 목록 순서를 씀. 승부차기 경기의 Transfermarkt 스코어는 승부차기를 더한 값이라 쓰지 않음",
    "출전 분: Transfermarkt 그대로. 연장 120분 경기: 2001.11.27 인터콘티넨털컵 바이에른전(0-1 연장패), 2004.8.24 인터토토컵 결승 2차전 아틀레티코전(연장 뒤 승부차기). 2003.4.22 챔스 8강 유벤투스전(연장)은 교체 34분. 연장 없이 승부차기로 끝난 7경기(리베르타도레스 2000 결승·2001 준결승·2001 결승·2013 8강, 코파 아르헨티나 2012 두 경기·2014 8강)는 90분 기준",
    f"날짜: 경기 현지 날짜. 바르셀로나·비야레알은 Transfermarkt 날짜. 보카·아르헨티노스 경기는 Transfermarkt 일정·리포트 날짜가 중부 유럽 기준이라 경기 시각(UTC)을 아르헨티나 시간(UTC−3)으로 바꾼 날짜를 씀(저녁 경기 {len(DATE_CHG)}경기가 Transfermarkt 날짜보다 하루 앞; 2010-11 이후는 FotMob 경기 시각과 같음. 남미 원정도 경기지 날짜가 같음). 시각이 비어 자리값만 있는 경기는 일정 날짜. 2001 인터콘티넨털컵은 도쿄 현지 2001.11.27(영어 위키백과; Transfermarkt 11.28)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(포를란·피레스 등), 직접 추정, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위(Transfermarkt 순위표)를 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {ELO_SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {ELO_SRC['기존 팀×시즌 값']}, 순위표+모형 {ELO_SRC['순위표+리그 모형']}, 직접 {ELO_SRC['직접 추정']})",
    "리그 수준: 아르헨티나 1부는 반시즌(아페르투라·클라우수라, 2012-13부터 이니시알·피날) Transfermarkt 순위표를 평균 1583·흩어짐 63 모형에 넣음(경기가 속한 대회 그대로: 2~7월 클라우수라·피날, 8~12월 아페르투라·이니시알; 리베르타도레스·수다메리카나의 아르헨티나 상대도 그때 진행 중인 대회 순위). 통합표 시즌 키가 연도라 같은 팀이 한 해 두 대회 값이 다르면 평균(포를란·팔카오 선례). 아페르투라 2008은 3팀 결정전 뒤 최종 순위(보카 1·티그레 2·산로렌소 3). 브라질 세리에 A는 기존 모형(평균 1598). 멕시코는 기존 멕시코 모형(1604.25 + 73.41 × 곡선)에 아페르투라·클라우수라 조별 표 승점 합으로 낸 18팀 순위를 넣은 추정. 우루과이 2012-13은 아페르투라·클라우수라 승점 합 연간 순위를 평균 1540 모형에 넣음(수아레스·포를란 선례). 라리가·프리미어리그·세리에A는 기존 순위값. 아르헨티나 2부 2014(아르헨티노스 상대)는 디발라 선례 2부 모형(평균 1355, 2부 흩어짐)에 조 순위(11팀)를 넣은 추정(순위는 위키백과 2014 프리메라 B 나시오날 표 검색 요약), 1996.11.24 우라칸(BA)은 RSSSF 아페르투라 1996 최종 순위 19위/20팀(승점 16 동률, 득실차)을 같은 모형에 넣음. 2012 코파 아르헨티나 메를로(2011-12 2부 14위)는 디발라 자료 값, 3부 상대(산타마리나·에스투디안테스 부에노스아이레스)는 다른 선수 자료 3부 1253",
    "직접 추정(모두 '추정'): " + ", ".join(f"{o} {e}" for o, e, lv in MAN_USED) + ". 볼리비아·에콰도르·콜롬비아·파라과이·베네수엘라·칠레 상대는 순위표가 없거나(Transfermarkt 표 없음) 다른 선수 자료의 같은 나라 상위 팀 값에 맞춤",
    "대회 비중: 코파 아르헨티나·코파 델 레이는 국내컵(16강까지 낮은 비중, 8강부터 높은 비중·준결승). 레코파 수다메리카나 2008은 국내컵 결승 비중(호나우지뉴 선례). 인터콘티넨털컵 2000·2001은 클럽 월드컵 비중(단판). 리베르타도레스 조별·16강, 8강·준결승·결승은 단계별 비중. 코파 수다메리카나·메르코수르·수페르코파 수다메리카나(1997)는 남미 2부 대회 비중(주니뉴·포를란·호나우두 선례). UEFA컵 1라운드·인터토토컵은 유로파 예선, UEFA컵 조별은 유로파 조별, UEFA컵 2·3라운드·16강·8강은 유로파 토너먼트. 2008.12.20 아페르투라 결정전(보카·산로렌소·티그레 3팀 리그)은 리그 비중의 리그식 경기(무승부 1점). 아르헨티나 2부 2014는 리그",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·코파 델 레이는 원정 다득점·연장. 리베르타도레스는 2004년까지 원정 다득점·연장 없이 승부차기, 2005년부터 원정 다득점 있고 연장 없음(2007 결승 포함), 수다메리카나 2008도 원정 다득점·연장 없음(팔카오 선례), 레코파 2008은 결승이라 원정 다득점 없이 연장으로 봄(규정 미확인 추정). 못 뛴 다른 차전 스코어는 Transfermarkt 리포트",
    "시즌 구분: 보카·아르헨티노스는 달력 연도(보카 1996은 우라칸전 1경기, 보카 2002.1~5와 바르셀로나 2002-03은 다른 시즌), 비야레알은 7월 10일 기준, 바르셀로나는 8월 1일 기준. 보카 1996~2002와 2007~2014(2007년 상반기는 비야레알에서 임대)는 같은 클럽. 클럽 구분: 2002.7.1 바르셀로나, 2003.8.1 비야레알, 2007.1.15 보카, 2014.7.1 아르헨티노스(경기 클럽과 경계 불일치 0)",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 아르헨티나 리그 1998(아페르투라)·1999(클라우수라)·2000(아페르투라)·2008(아페르투라)·2011(아페르투라), 코파 아르헨티나 2011-12, 인터콘티넨털컵 2000, 코파 리베르타도레스 2000·2001·2007, 레코파 수다메리카나 2008, UEFA 인터토토컵 2004. 개인: 아르헨티나 올해의 선수 2000·2001·2008·2011. 대표팀·청소년 대표 우승(U-20 월드컵 1997, 올림픽 2008)은 뺌",
    "은퇴: 2015.1.25 ESPN 인터뷰에서 은퇴 발표(쿠페라티바·디아리오 데 쿠요 기사), 마지막 클럽 경기 2014.12.7 아르헨티노스 주니어스(프리메라 B 나시오날) 더글러스 하이그전",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

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
    if m and r[4] > m[3] + 4 and not r[10] and Gstart.get(r[9], True): problems.append(("출전 분보다 늦은 기록", r[9], r[4], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const RIQ_E={J(E)};\nconst RIQ_M={J(M)};\nconst RIQ_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "arg_averages": ARG_AVG,
               "date_changes": DATE_CHG, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
