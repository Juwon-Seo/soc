#!/usr/bin/env python3
"""소니 앤더슨 (Sonny Anderson, Anderson da Silva, Transfermarkt 3500): raw/ -> sonnyanderson.json + sna.js (판정 근거는 judgments.md)

  python3 players/sonnyanderson/build_sonnyanderson.py            # 파일 쓰기
  python3 players/sonnyanderson/build_sonnyanderson.py --debug    # Elo 출처 로그
  python3 players/sonnyanderson/build_sonnyanderson.py --stat     # 요약·판정·동료 대조
  python3 players/sonnyanderson/build_sonnyanderson.py --ties     # 합산 행

빌토르 build(players/wiltord, 같은 형식의 원자료)를 바탕으로 함. 상대 Elo는 v1.226 규칙: 같은 경기 다른 선수 자료 → Elo 통합표(같은 팀·시즌)
→ 출처로 확인한 순위로 라벨을 만들고 tools/league_rank_apply.py 의 value()로 값을 정함(직접 숫자를 넣지 않음).
카타르 리그 경기(Transfermarkt에 없음)는 RSSSF 경기 줄(raw/qatar_rsssf_games.csv)에서 골이 있는 경기만 넣음(바티스투타 선례).
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "sna.js") if os.environ.get("SOC_ROOT") else os.path.join(HERE, "sna.js")   # 정본 src/는 오케스트레이터가 통합
OUT_JSON = os.path.join(HERE, "sonnyanderson.json")
ME = "3500"
ME_KO = "소니 앤더슨"
PFX = "SNA"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

# ---------------------------------------------------------------- 날짜
# TM 리포트 날짜(없으면 일정 날짜). 브라질 경기 시각은 자리값(12/13시 UTC)이라 TM 날짜 = 현지 날짜. 세 날짜 열이 549경기 모두 같음.
LD = {}
for gid, g in G.items():
    ds = {x for x in (g["date_local_tm_report"], g["date_local_schedule"], g["date_local_tz_conv"]) if x}
    if len(ds) != 1: sys.exit("날짜 다름 " + gid)
    LD[gid] = ds.pop()
def ldate(g): return LD[g["gameId"]]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "ES1", "C1", "BRA1"}
CUP = {"FRC", "FRL", "CDR", "SCC"}        # 쿠프 드 프랑스·쿠프 드 라 리그·코파 델 레이·스위스컵

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                     # 2~6라운드(쿠프 드 프랑스 '6라운드' = 32강)·16강
    if cid == "BCPF": return "dc"       # 캄페오나투 파울리스타 결선 조별 = 국내컵 낮은 비중(주 선수권 선례)
    if cid in ("FRCH", "SUC", "USC"): return "df"   # 트로페 데 샹피옹·수페르코파·UEFA 슈퍼컵 = 국내컵 결승 비중
    if cid == "CL":
        if r.startswith("group"): return "clg"
        sys.exit("CL 단계 " + rnd)
    if cid == "CLQ": return "clq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 2라운드·3라운드·16강·8강
    if cid == "UI": return "elq"                         # 인터토토컵 = 유로파 예선(리켈메·포를란 선례)
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        return "lib"
    if cid == "AFCL": return "acl"
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
    if cid in ("CL", "CLQ", "UEFA", "UI", "USC", "SUC", "CDR"): return (1, 1)   # UEFA 대회·코파 델 레이·수페르코파(라울·피구·리발도 자료와 같음)
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
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
EST = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    row = [ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g))]
    if g["playedMinutes"]: row.append(int(g["playedMinutes"]))
    else:
        row += [90, 1]; EST.append((ldate(g), opp(g), g["competitionId"]))   # 출전 분 없음(브라질 6경기): 90분 추정
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

A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    if d < GAP:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM 단독(2014.8 전 허용)"))
        return None
    sys.exit("2014.8 이후 도움 " + gid)

raw_rows, judg = [], []
# 리포트에 상대 골이 빠진 경기(discrepancies 3): 앤더슨 골의 골 전 스코어를 다른 출처로 정함. gameId -> {분: (gf, ga)}
SM_FIX = {
    # 1995.2.4 쿠프 드 프랑스 3라운드 스타드 푸아트뱅 2-1 모나코(하프타임 0-1). 앤더슨 10분 선제골(리포트 0-1) — 하프타임 0-1이라
    # 푸아티에 두 골은 모두 후반, 앤더슨 골 앞에는 골이 없음 → 골 전 0-0 그대로.
    "3150166": {"10": (0, 0)},
    # 1997.5.24 모나코 2-1 낭트(하프타임 0-1). 낭트 골은 전반(하프타임 0-1) → 콜린스 76분·앤더슨 90분 골은 모두 낭트 골 뒤:
    # 앤더슨 골 전 1-1(리포트 순서대로면 1-0).
    "1011229": {"90": (1, 1)},
    # 2001.4.7 리옹 2-1 모나코: 리포트가 57분 앤더슨 PK와 57분 논다 골을 같은 스코어 1-1로 적음. 리포트 순서(앤더슨 PK 먼저, 결과 1-1)는
    # 모나코 선제골 뒤 동점 PK → 골 전 0-1. 결승골(2-1)은 다른 선수. 아래 판정 참고.
}
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
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        if gid in SM_FIX and e["minute"] in SM_FIX[gid]: gf, ga = SM_FIX[gid][e["minute"]]
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
    if MI[gid]["result_flag"] == "pens": continue   # 승부차기 경기: 리포트 최종 = 승부차기 포함 스코어
    if (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
SM_OK = set(SM_FIX) | {"1003040", "1019299"}   # 1003040: 순서·수 맞음(스코어 표기만 겹침), 1019299: 앤더슨 기록 없음
for gid, *_ in SCORE_MISMATCH:
    if any(r[1] == gid for r in raw_rows) and gid not in SM_OK: sys.exit("골 목록이 모자란 리포트에 앤더슨 기록 " + gid)

# ---------------------------------------------------------------- 카타르 리그(RSSSF 경기 줄, Transfermarkt에 없음)
QNAME = {"Arabi": "Al-Arabi SC", "Qatar": "Qatar SC", "Khritiyat": "Al-Kharaitiyat SC", "Ahli": "Al-Ahli SC", "Wakra": "Al-Wakrah SC",
         "Shamal": "Al-Shamal SC", "Khor": "Al-Khor SC", "Sadd": "Al-Sadd SC", "Siliya": "Al-Sailiya SC", "Gharrafa": "Al-Gharafa"}
MON = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
def parse_scorers(s):
    """'A 16, 61, B 40pen; C 5' -> [[(분, 이름, pen, og)], [...]] (홈, 원정)"""
    out = []
    for part in (s.split(";") + [""])[:2]:
        ev, name = [], None
        for tok in [t.strip() for t in part.split(",") if t.strip()]:
            m = re.match(r"^(.*?)\s*(\d+)(pen|og)?$", tok)
            if not m: sys.exit("RSSSF 득점자 해석 실패 " + tok)
            if m.group(1): name = m.group(1).strip()
            ev.append((int(m.group(2)), name, m.group(3) == "pen", m.group(3) == "og"))
        out.append(ev)
    return out
QAT = []   # [날짜, 상대, 시즌, 골 행[(분, pk, gf, ga)]]
for r in rd("qatar_rsssf_games.csv"):
    if r["section"] != "league" or "Rayyan" not in (r["home"], r["away"]) or "Sonny Anderson" not in r["scorers_v1"]: continue
    hs, as_ = parse_scorers(r["scorers_v1"])
    home = r["home"] == "Rayyan"
    ours, theirs = (hs, as_) if home else (as_, hs)
    if not any(n == "Sonny Anderson" for _, n, _, _ in ours): continue
    sh, sa = map(int, r["score"].split("-"))
    if (len(hs), len(as_)) != (sh, sa): sys.exit("RSSSF 득점자 수와 스코어 다름 " + str(r))
    mo, dd = r["date_rsssf"].split()
    y0 = int(r["season"][:4]); y = y0 if MON[mo] >= 7 else y0 + 1
    d = f"{y}-{MON[mo]:02d}-{int(dd):02d}"
    evs = sorted([(m, 0, n, p) for m, n, p, o in ours] + [(m, 1, n, p) for m, n, p, o in theirs], key=lambda x: (x[0], x[1]))
    rows, gf, ga = [], 0, 0
    for m, s, n, p in evs:
        if s == 0 and n == "Sonny Anderson": rows.append((m, 1 if p else 0, gf, ga))
        if s == 0: gf += 1
        else: ga += 1
    QAT.append([d, QNAME[r["away"] if home else r["home"]], r["season"], rows, r["round"]])
QAT.sort()
for d, o, s, rows, rnd in QAT:
    M.append([d, o, "lg", 90, 1])
M.sort(key=lambda m: m[0])

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
    if b in ("hon.js", "clubcolors.js", "finals.js", "sna.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting", "cp",
        "ec", "foot", "ball", "atletico", "calcio", "sport", "sociedade", "olympique", "cd", "ud", "rcd", "sv", "as", "ss", "sl", "gd", "cs",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "ca", "deportivo", "fk", "vfl", "bv",
        "racing", "arsenal", "hotspur", "palace", "villa", "ham", "manchester", "park", "west", "aston", "vitoria", "academica", "uniao",
        "sevilla", "betis", "celta", "vigo", "gijon", "coruna", "las", "palmas", "valencia", "levante", "rayo", "vallecano", "balompie", "sociedad", "barcelona", "espanyol",
        "belenenses", "braga", "porto", "benfica", "lisboa", "bk", "jk", "spor", "kulubu", "dynamos",
        "istanbul", "ankara", "athens", "praha", "bayer", "borussia", "hertha", "brugge", "regatas", "gama", "vasco", "saint", "stade", "rc", "ogc", "aj", "en", "avant", "garde"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d, cid):
    exact = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    cand = exact or [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 → 라벨 → 값(tools/league_rank_apply.py)
_LRA = {'__file__': os.path.join(ROOT, 'tools', 'league_rank_apply.py'), '__name__': 'lra'}
_argv = sys.argv; sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA['__file__'], encoding='utf-8').read().split("if __name__ == '__main__':")[0], 'lra', 'exec'), _LRA)
sys.argv = _argv
def lv_value(lv, d):
    mnr = re.match(r"^(\S+) (\d)부 (\d{4})-(\d{2}) 순위 없음", lv)
    if mnr:
        return int(round(_LRA['base'](_LRA['KO'][mnr.group(1)], int(mnr.group(2)), int(mnr.group(3)) + 1)))
    p = _LRA['parse'](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA['value'](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    return v

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[0].startswith("INVALID"): continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1])
RANK_FIX = {}

BIGL = {"PO1": "포르투갈 1부", "ES1": "라리가", "GB1": "프리미어리그", "IT1": "세리에A", "FR1": "리그1", "L1": "분데스리가", "NL1": "에레디비시"}
CAL_LG = set()
def make_label(lg, season, r, n):
    if lg in BIGL:
        pre = BIGL[lg]; y = int(season[:4]) + 1
        n0 = _LRA['ERA']['teams'](pre, y)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    if lg == "FR2": return f"리그2 {season} {r}위/{n}팀"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산)
def man(o, s, lv): MAN[(key(o), s)] = lv
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []

def opp_elo(o, d, cid):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    seasons = [eu(d), d[:4]]
    for s in seasons:
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d)
            ELO_SRC["순위 라벨(직접 확인)"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            p = _LRA['parse'](lv, d)
            if p and _LRA['value'](*p) != e: TABLE_DIFF.append((o, s, e, lv, _LRA['value'](*p)))
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for (lg, s), t in RANKS.items():
        if k in t and (s == eu(d) or (lg in CAL_LG and s == d[:4])):
            r, n, nm, _ = t[k]
            if (k, s) in RANK_FIX: r, n, _why = RANK_FIX[(k, s)]
            lv = make_label(lg, s, r, n)
            if lv:
                e = lv_value(lv, d)
                ELO_SRC["순위표 → 라벨"] += 1; ELO_LOG[(o, d)] = ("rank", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

if os.path.exists(os.path.join(HERE, "man_elo.py")):
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
for d, o, s, rows, rnd in QAT:
    elo, lv = opp_elo(o, d, "QSL")
    for mi, pk, gf, ga in rows:
        E.append(["g", o, elo, "lg", mi, gf, ga, 0, pk, d, 0, 0, lv, 0])

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
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Sonny Anderson", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(앤더슨 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("앤더슨 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("타인 도움 행이 앤더슨 골과 같은 시각", b, r[9], r[4], hit[0][13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x[1], r[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and key(mm[1]) == key(m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and j[3] != "?" and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 앤더슨 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("vassa", "1991-07-01"), ("guasa", "1992-07-01"), ("sersa", "1993-11-05"), ("omsa", "1994-07-01"), ("monsa", "1997-07-01"),
         ("fcbsa", "1999-07-01"), ("olsa", "2003-07-11"), ("vilsa", "2004-10-16"), ("raysa", None)]   # = integration.json
TM_CLUB = {"978": "vassa", "1755": "guasa", "61": "sersa", "244": "omsa", "162": "monsa", "131": "fcbsa", "1041": "olsa", "1050": "vilsa", "3229": "raysa"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
CAL = {"vassa", "guasa"}; JUL10 = {"omsa", "monsa", "olsa"}; JUL1 = {"sersa", "vilsa"}
def season_of(d, club):
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    if club in CAL: return str(y)
    s_ = y if (m >= 8 or (club in JUL10 and (m, dd) >= (7, 10)) or (club in JUL1 and m >= 7)) else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("바스쿠 다 가마(1988~1991)", "1991-07-01"), ("과라니(1991~1992)", "1992-07-01"), ("세르베트(1992~1993)", "1993-11-05"),
          ("마르세유(1993~1994, 임대)", "1994-07-01"), ("AS 모나코(1994~1997)", "1997-07-01"), ("바르셀로나(1997~1999)", "1999-07-01"),
          ("리옹(1999~2003)", "2003-07-11"), ("비야레알(2003~2004)", "2004-10-16"), ("알라이얀(2004~2006)", "9999")]
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
NQ = len(QAT); NQG = sum(len(x[3]) for x in QAT)
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A, UNTYPED, "QAT", NQ, NQG)
    for j in judg: print(j)
    for c in CROSS: print(c)
    print("score mismatch", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("TABLE_DIFF", TABLE_DIFF)
    for x in sorted(NEW_TS.items()): print("NEW", x)
    print("EST", EST)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_sonnyanderson.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl", "df", "clg", "cl16", "libk"]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const {PFX}_E={J(E)};\nconst {PFX}_M={J(M)};\nconst {PFX}_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "cross_check": CROSS, "elo_sources": ELO_SRC, "qatar_games": QAT, "estimated_minutes": EST,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
