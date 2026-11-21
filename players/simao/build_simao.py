#!/usr/bin/env python3
"""시망 사브로자 (Simão Pedro Fonseca Sabrosa, Transfermarkt 8019): raw/ -> simao.json + src/data/sim.js (판정 근거는 judgments.md)

  python3 players/simao/build_simao.py            # 파일 쓰기
  python3 players/simao/build_simao.py --debug    # Elo 출처 로그
  python3 players/simao/build_simao.py --stat     # 요약·판정·동료 대조
  python3 players/simao/build_simao.py --ties     # 합산 행

디에구 코스타 build(players/diegocosta)를 바탕으로 함. 상대 Elo는 v1.226 규칙: 같은 경기 다른 선수 자료 → Elo 통합표(같은 팀·시즌)
→ 출처로 확인한 순위로 라벨(`<리그> <시즌> N위[/M팀]`)을 만들고 tools/league_rank_apply.py 의 value()로 값을 정함(직접 숫자를 넣지 않음).
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "sim.js")
OUT_JSON = os.path.join(HERE, "simao.json")
ME = "8019"
ME_KO = "시망 사브로자"
PFX = "SIM"

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
# 모든 경기가 유럽·인도(저녁 경기도 중부 유럽 날짜와 같은 날). TM 리포트 날짜(없으면 일정 날짜)를 씀.
# 1997~2006년 48경기는 API 시각이 22:00/23:00 UTC 자정 자리표시라 UTC 변환 날짜가 하루 앞섬 → 리포트·일정 날짜(디스크레펀시 7절).
DATE_LOG = []
LD = {}
for gid, g in G.items():
    d = g["date_local_tm_report"] or g["date_local_schedule"] or g["date_local_tz_conv"]
    if g["date_local_tm_report"] and g["date_local_schedule"] and g["date_local_tm_report"] != g["date_local_schedule"]: sys.exit("리포트·일정 날짜 다름 " + gid)
    LD[gid] = d
    if d != g["date_local_tz_conv"]: DATE_LOG.append((gid, g["date_local_tz_conv"], d, g["opponent"]))
def ldate(g): return LD[g["gameId"]]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"PO1", "ES1", "TR1", "POT1", "IND1"}   # POT1 = 쉬페르 리그 2011-12 챔피언십 플레이오프(리그로 셈)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("CDR", "POPO", "TRP"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SUC", "USC", "POSU"): return "df"     # 수페르코파·UEFA 슈퍼컵·수페르타사 = 국내컵 결승 비중
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 1999-00 2차 조별('Group 1') 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid in ("UEQ", "ELQ"): return "elq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        return "elk"                                     # 2·3라운드·32강(intermediate stage)·16강·8강
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 32강('Second Round')·16강·8강
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
    if cid in ("CL", "CLQ", "UEFA", "UEQ", "EL", "ELQ"): return (1, 1)   # UEFA 2020-21까지
    if cid in ("CDR", "SUC"): return (1, 1)                                # 스페인 국내 대회 2018-19까지
    if cid == "TRP": return (1, 1)                                         # 튀르키예컵 2020-21까지(v1.152)
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

# 2014.8 이후 단일 출처 도움(FotMob 도움 없음) 웹 확인: 키 = gameId|분
A_CHECK = {
    "2633925|85": (False, "느슨한 공: 시망 프리킥을 뭄바이 골키퍼가 수비수(Pavel Čmovš)와 엉켜 놓친 공을 카마라가 밀어 넣음(AIFF·PTI 기사 "
                          "the-aiff.com 'NorthEast United FC prove two good for Mumbai City FC', business-standard PTI, indiansuperleague.com 경기 기사 'keeper ... spilled the ball') → 도움 아님"),
    "2633929|55": (True, "시망 코너킥을 멘디가 헤더(ESPN 경기 기사 gameId 434728 'attacking Simao's inch-perfect cross', AIFF/ISL 공식 기사 "
                         "'Simao ... delivered a quality corner into the six-yard area which substitute Mendy ... headed') — 독립 출처 2곳"),
}
def a_key(gid, minute): return f"{gid}|{minute}"

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["time"] and (f["simao_assist"] == "1" or f["assistStr"].strip() == "assist by Simão") and fm_min_match(f, e["minute"]): return True
    return False

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
        if d >= "2010-07-01": A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트" if fm_assist(gid, e) else "TM 단독(2014.8 전 허용)"))
        return None
    k = a_key(gid, e["minute"])
    if fm_assist(gid, e):
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "느슨한 공(골키퍼가 놓친 공) — 도움 아님"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음"))
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
# 3570351 타사 5라운드 투리젠스전(0:2): API 도움 1개, 리포트에 골 목록이 없음. 골은 Robert 66'·Nuno Gomes 79'(위키백과 2005-06 타사 문서)
# 이지만 어느 골의 도움인지 확인할 출처가 없어 넣지 않음(골 시각·스코어를 정할 수 없음).
judg.append(("도움 제외", "2006-01-11", "GD Tourizense", "?", "Robert 또는 Nuno Gomes", "TM API 도움 1개, 리포트 골 목록 없음 — 어느 골인지 확인 못 함"))

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
    if MI[gid]["result_flag"] == "pens" and h == a: continue   # 승부차기 경기: 리포트 최종 = 승부차기 스코어
    if (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
# 3989308(2004.12.21 올리베이렌스 4:1 연장): 4번째 벤피카 골이 리포트에 없음 — 시망 골(50' PK, 1-1)은 그 앞이라 골 전 스코어는 영향 없음
SM_OK = {"3989308"}
for gid, *_ in SCORE_MISMATCH:
    if any(r[1] == gid for r in raw_rows) and gid not in SM_OK: sys.exit("골 목록이 모자란 리포트에 시망 기록 " + gid)

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
    if b in ("hon.js", "clubcolors.js", "sim.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting", "cp",
        "ec", "foot", "ball", "atletico", "calcio", "sport", "sociedade", "olympique", "cd", "ud", "rcd", "sv", "as", "ss", "sl", "gd", "cs",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "ca", "deportivo", "fk", "vfl", "bv",
        "racing", "arsenal", "hotspur", "palace", "villa", "ham", "manchester", "park", "west", "aston", "vitoria", "academica", "uniao", "uniao",
        "sevilla", "betis", "celta", "vigo", "gijon", "coruna", "las", "palmas", "valencia", "levante", "rayo", "vallecano", "balompie", "sociedad", "barcelona", "espanyol",
        "belenenses", "braga", "porto", "benfica", "lisboa", "bk", "jk", "spor", "kulubu", "dynamos", "delhi", "mumbai", "goa", "kerala", "chennaiyin", "pune", "northeast",
        "istanbul", "ankara", "athens", "praha", "bayer", "borussia", "hertha", "real", "club", "brugge"}
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
# 순위 고침(출처로 확인; judgments.md 'Elo·순위' 절). TM 순위표는 승점 동률 순서가 공식 규정(포르투갈 상대 전적, 벨기에 승수 등)과
# 다를 수 있어서, 아래 리그·시즌은 영어 위키백과 시즌 문서의 순위표(wiki_tables/, action=raw로 받음)의 순서를 씀.
WT = os.path.join(HERE, "wiki_tables")
WIKI = {("PO1", "1996-97"): "1996–97_Primeira_Divisão.txt", ("PO1", "1997-98"): "1997–98_Primeira_Divisão.txt",
        ("PO1", "1998-99"): "1998–99_Primeira_Divisão.txt", ("PO1", "2001-02"): "2001–02_Primeira_Liga.txt",
        ("PO1", "2002-03"): "2002–03_Primeira_Liga.txt", ("PO1", "2003-04"): "2003–04_Primeira_Liga.txt",
        ("PO1", "2004-05"): "2004–05_Primeira_Liga.txt", ("PO1", "2005-06"): "2005–06_Primeira_Liga.txt",
        ("PO1", "2006-07"): "2006–07_Primeira_Liga.txt", ("ES2", "2013-14"): "2013–14_Segunda_División.txt",
        ("TR1", "2010-11"): "2010–11_Süper_Lig.txt", ("TR1", "2011-12"): "2011–12_Süper_Lig.txt",
        ("BE1", "2003-04"): "2003–04_Belgian_First_Division.txt", ("BE1", "2004-05"): "2004–05_Belgian_First_Division.txt",
        ("SLO1", "2004-05"): "2004–05_Slovak_Superliga.txt", ("PO2", "2005-06"): "2005–06_Liga_de_Honra.txt",
        ("UKR1", "2011-12"): "2011–12_Ukrainian_Premier_League.txt", ("IND1", "2015"): "isl2015.txt"}
def wiki_order(fn):
    t = open(os.path.join(WT, fn), encoding="utf-8").read()
    i = t.find("#invoke:sports table"); t = t[i:]; t = t[:t.find("\n}}")]
    names = {m.group(1): re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", m.group(2)).strip() for m in re.finditer(r"\|name_([^=\s]+)\s*=\s*([^\n]+)", t)}
    out = {}
    for m in re.finditer(r"\|team(\d+)\s*=\s*([^|\n]+)", t):
        n = int(m.group(1))
        if n not in out: out[n] = names.get(m.group(2).strip(), m.group(2).strip())
    return out
WSTOP = {"fc", "sc", "cf", "cd", "ud", "cs", "gd", "sl", "jk", "de", "da", "das", "os", "vitoria", "clube", "futebol", "real", "ad", "kv", "sk", "rsc", "raa", "ksk", "krc", "kvc", "ksc", "kaa", "vv", "royal", "fk", "mfk", "msk", "as", "pfc"}
WALIAS = {"uniao de leiria": "leiria", "academica": "academica coimbra", "istanbul b b": "buyuksehir belediyespor", "desportivo das aves": "desportivo aves",
          "estoril": "estoril praia"}
def wtoks(n):
    n = norm(n); n = WALIAS.get(n, n)
    return {t for t in n.split() if t not in WSTOP and len(t) > 2}
WIKI_RANK = {}
for (lg, s), fn in WIKI.items():
    o = wiki_order(fn); n = len(o)
    for r, nm in o.items(): WIKI_RANK[(lg, s, frozenset(wtoks(nm)))] = (r, n, nm)
def wiki_rank(lg, s, tm_name):
    if (lg, s) not in WIKI: return None
    tt = wtoks(tm_name)
    sc = [(len(w & tt) / len(w | tt), v) for (l2, s2, w), v in WIKI_RANK.items() if l2 == lg and s2 == s and (w & tt)]
    top = max([x for x, _ in sc], default=0)
    hit = [v for x, v in sc if x == top]
    if len(hit) != 1: sys.exit(f"위키 순위표 이름 맞추기 실패 {lg} {s} {tm_name} {hit}")
    return hit[0]
RANK_FIX = {("gnk dinamo zagreb", "2004-05"): (7, 12, "1. HNL 2004-05: 1단계 7위 → 강등 그룹 1위 = 최종 7위/12팀(위키백과 2004–05 Croatian First Football League)")}

BIGL = {"PO1": "포르투갈 1부", "ES1": "라리가", "GB1": "프리미어리그", "IT1": "세리에A", "FR1": "리그1", "L1": "분데스리가", "NL1": "에레디비시"}
OTHL = {"BE1": ("벨기에", "Belgian First Division"), "DK1": ("덴마크", "Danish Superliga"), "GR1": ("그리스", "Super League Greece"),
        "ISR1": ("이스라엘", "Israeli Premier League"), "NO1": ("노르웨이", "Eliteserien"), "RO1": ("루마니아", "Liga I"),
        "RU1": ("러시아", "Russian Premier League"), "SC1": ("스코틀랜드", "Scottish Premier League"), "SE1": ("스웨덴", "Allsvenskan"),
        "SER1": ("세르비아", "Serbian SuperLiga"), "SLO1": ("슬로바키아", "Slovak Superliga"), "TR1": ("튀르키예", "Süper Lig"),
        "TS1": ("체코", "Czech First League"), "UKR1": ("우크라이나", "Ukrainian Premier League"), "ZYP1": ("키프로스", "Cypriot First Division"),
        "KR1": ("크로아티아", "Prva HNL")}
CAL_LG = {"NO1", "SE1", "RU1", "IND1"}
def make_label(lg, season, r, n):
    if lg in BIGL:
        pre = BIGL[lg]; y = int(season[:4]) + 1
        n0 = _LRA['ERA']['teams'](pre, y)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    if lg in OTHL:
        cn, nm = OTHL[lg]
        return f"{cn} 1부 {season} {r}위/{n}팀 ({nm})"
    if lg == "IND1":
        return f"인도 슈퍼리그 {season} {r}위/{n}팀 (추정: 1위 1300~꼴찌 1200 직선)"   # 말루다 2015 같은 리그·시즌 라벨 형식
    if lg == "ES2": return f"세군다 {season} {r}위" + ("" if n == 22 else f"/{n}팀")
    if lg == "PO2": return f"포르투갈 2부 {season} {r}위/{n}팀"
    if lg == "TR2": return f"튀르키예 2부 {season} {r}위/{n}팀"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산)
def man(o, s, lv): MAN[(key(o), s)] = lv
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []; RANK_LOG = []

def opp_elo(o, d, cid):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    seasons = [d[:4], eu(d)] if cid == "IND1" else [eu(d), d[:4]]
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
            else:
                w = wiki_rank(lg, s, nm)
                if w:
                    if w[0] != r: RANK_LOG.append((lg, s, nm, r, w[0], w[2]))
                    r, n = w[0], w[1]
                elif lg in ("PO1",): sys.exit("위키 순위표 없음 " + lg + " " + s)
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
    for x in RANK_LOG: print("RANK", x)
    for x in sorted(NEW_TS.items()): print("NEW", x)
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
    fm = [r for r in FME[gid] if r["simao_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "penalty" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))

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
        if x[0] == "a" and re.search(r"Sim[aã]o", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(시망 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("시망 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("타인 도움 행이 시망 골과 같은 시각", b, r[9], r[4], hit[0][13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 시망 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("scpsm", "1999-07-01"), ("fcbsm", "2001-07-27"), ("bensm", "2007-07-01"), ("atmsm", "2011-01-01"),
         ("bjksm", "2012-08-17"), ("espsm", "2015-07-01"), ("neusm", None)]
TM_CLUB = {"336": "scpsm", "131": "fcbsm", "294": "bensm", "13": "atmsm", "114": "bjksm", "714": "espsm", "45276": "neusm"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club == "neusm": return str(y)
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("스포르팅 CP", "1999-07-01"), ("바르셀로나", "2001-07-27"), ("벤피카", "2007-07-01"), ("아틀레티코 마드리드", "2011-01-01"),
          ("베식타시", "2012-08-17"), ("에스파뇰", "2015-07-01"), ("노스이스트 유나이티드", "9999")]
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
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A, UNTYPED)
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    for c in CROSS: print(c)
    print("FM", FM_CMP)
    print("score mismatch", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("dates changed", len(DATE_LOG))
    print("TABLE_DIFF", TABLE_DIFF)
    for x in sorted(NEW_TS.items()): print("NEW", x)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_simao.py"), encoding="utf-8").read())   # NOTE_LINES
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const {PFX}_E={J(E)};\nconst {PFX}_M={J(M)};\nconst {PFX}_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "date_changes": DATE_LOG, "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
