#!/usr/bin/env python3
"""하비에르 사비올라 (Javier Pedro Saviola, Transfermarkt 7611): raw/ -> saviola.json + src/data/svl.js (판정 근거는 judgments.md)

  python3 players/saviola/build_saviola.py            # 파일 쓰기
  python3 players/saviola/build_saviola.py --debug    # Elo 출처 로그
  python3 players/saviola/build_saviola.py --stat     # 요약·판정·동료 대조
  python3 players/saviola/build_saviola.py --ties     # 합산 행

시망 build(players/simao)를 바탕으로 함(수집기 형식이 같음). 남미 날짜·대회 처리는 리켈메 build(players/riquelme) 선례.
상대 Elo는 v1.226 규칙: 같은 경기 다른 선수 자료 → Elo 통합표(같은 팀·시즌) → 출처로 확인한 순위로 라벨을 만들고
tools/league_rank_apply.py 의 value()로 값을 정함(직접 숫자를 넣지 않음). 스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "svl.js")
OUT_JSON = os.path.join(HERE, "saviola.json")
ME = "7611"
ME_KO = "하비에르 사비올라"
PFX = "SVL"

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
# 유럽 클럽: TM 리포트 날짜(없으면 일정 날짜). 리버 플레이트: TM 일정·리포트 날짜는 중부 유럽 시간이라 남미 저녁 경기는 하루 밀림 →
# TM API 경기 시각(UTC)이 실제 킥오프면 UTC−3 날짜. 시각이 중부 유럽 자정(UTC 22:00/23:00 정각, 날짜 하루 앞)이나 12:00·13:00 정각이면
# 시각 미상 자리값 → 일정 날짜 그대로(리켈메 선례). 2015년은 FotMob UTC 시각과 같음.
def _lastsun(y, m):
    x = datetime.date(y, m, 31)
    while x.weekday() != 6: x -= datetime.timedelta(1)
    return x
def _cet_mid_utc_hour(d):
    return 22 if _lastsun(d.year, 3) <= d < _lastsun(d.year, 10) else 23
# 리버 리그 경기 중 TM 날짜(자리값 시각 포함)가 RSSSF 경기 날짜(요일 표기, rsssf/arg99·arg00·arg01.txt)와 다른 11경기 → RSSSF 날짜.
# 나머지 리버 리그 92경기·리베르타도레스 조별 14경기는 위 규칙의 날짜가 RSSSF와 같음(judgments.md 2절).
DATE_FIX = {"4453246": "1998-10-31", "4453358": "1998-12-04", "4453366": "1998-12-12", "4553217": "1999-05-22", "4159230": "1999-08-28",
            "4161332": "1999-11-06", "3797006": "2000-03-11", "3799997": "2000-04-12", "3800036": "2000-05-20", "3837964": "2000-08-19",
            "3840488": "2000-09-06"}
DATE_LOG = []
def _ldate(g):
    gid = g["gameId"]
    if gid in DATE_FIX:
        DATE_LOG.append((gid, g["date_local_tm_report"] or g["date_local_schedule"], DATE_FIX[gid], g["date_utc"][:16], g["opponent"], "RSSSF")); return DATE_FIX[gid]
    sched = g["date_local_tm_report"] or g["date_local_schedule"]
    if g["date_local_tm_report"] and g["date_local_schedule"] and g["date_local_tm_report"] != g["date_local_schedule"]: sys.exit("리포트·일정 날짜 다름 " + gid)
    if g["club_id"] != "209": return sched
    u = datetime.datetime.fromisoformat(g["date_utc"])
    if (u.hour, u.minute) in ((12, 0), (13, 0)): return sched
    sd = datetime.date.fromisoformat(sched)
    if u.minute == 0 and u.hour == _cet_mid_utc_hour(sd) and u.date() == sd - datetime.timedelta(1): return sched
    loc = (u - datetime.timedelta(hours=3)).date().isoformat()
    if loc != sched: DATE_LOG.append((gid, sched, loc, g["date_utc"][:16], g["opponent"], g["competitionId"]))
    return loc
LD = {gid: _ldate(g) for gid, g in G.items()}
def ldate(g): return LD[g["gameId"]]
# 'Club Almagro'는 Elo 통합표(tools/elo_table.js)가 이름이 포함되는 'CA San Lorenzo de Almagro'와 같은 팀으로 묶어 버려(같은 날짜 근거) 지역을 붙임
OPP_RENAME = {"Club Almagro": "Club Almagro (Buenos Aires)"}
def opp(g):
    o = re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
    return OPP_RENAME.get(o, o)

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ARG1", "ARGC", "AR1N", "ES1", "FR1", "PO1", "GR1", "IT1"}
CUPS = {"CDR", "POPO", "POCP", "FRC", "FRL", "GRP", "CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                                      # 조별(타사 다 리가)·2~4라운드·16강
    if cid == "ALPL": return "dc"                        # 리길야 프레 리베르타도레스(리베르타도레스 진출 결정전): 국내컵 비중(바티스투타·밀리토·카바니 선례)
    if cid in ("SUC", "POSU", "SURU"): return "df"       # 수페르코파·수페르타사·스루가 뱅크(파푸 고메스 선례) = 슈퍼컵류
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2001-02·2002-03 2차 조별('Group 1·2') 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "ELQ": return "elq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 2·3라운드·32강(intermediate stage)·16강·8강
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 32강('Second Round')·16강·8강
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"                                     # 조별·16강
    if cid in ("CMER", "CS"):                            # 코파 메르코수르 = 남미 2부 대회 비중(주니뉴·리켈메·포를란 선례), 수다메리카나
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
    if cid in ("CL", "CLQ", "UEFA", "EL", "ELQ"): return (1, 1)     # UEFA 2020-21까지
    if cid in ("CDR", "SUC"): return (1, 1)                         # 스페인 국내 대회 2018-19까지
    if cid == "POPO": return (1, 1)                                 # 타사 준결승(팔카오 선례: 2011 벤피카-포르투)
    if cid == "GRP": return (1, 1)                                  # 그리스컵 두 경기 라운드(베르바토프·발부에나·히바우두 선례)
    if cid == "CLI": return (0, 0) if d < "2005-01-01" else (1, 0)  # 리베르타도레스 2004년까지 원정 다득점 없음(리켈메·테베스 선례)
    if cid in ("CMER", "CS"): return (1, 0)                         # 메르코수르·수다메리카나(주니뉴·포를란·팔카오 선례)
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

# 2014.8 이후 단일 출처 도움(FotMob 도움 없음) 웹 확인: 키 = gameId|분 — 사비올라는 해당 없음(2014.8 이후 TM 도움 5개 모두 FotMob 이벤트와 같음)
A_CHECK = {}
def a_key(gid, minute): return f"{gid}|{minute}"

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["time"] and ("Saviola" in f["assistStr"]) and fm_min_match(f, e["minute"]): return True
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
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"] or "(유형 빈칸)", e["goal_desc"] or "(설명 빈칸)"))
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
# 3840480(2000.8.27 로사리오 센트랄전): 리포트 머리 2:1(하프타임 3:1)과 골 목록 4-1이 다름. RSSSF 아르헨티나 2000/01(River Plate 4-1
# Rosario Central [Saviola, Placente, Ángel (2) - Maceratesi (pen)])·La Página Millonaria 기사(4-1)가 골 목록과 같음 → 골 목록(4-1)을 씀.
SM_OK = {"3840480"}
for gid, *_ in SCORE_MISMATCH:
    if any(r[1] == gid for r in raw_rows) and gid not in SM_OK: sys.exit("골 목록이 리포트 머리와 다른 경기에 사비올라 기록 " + gid)

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
    if b in ("hon.js", "clubcolors.js", "svl.js") or "src/data/" + b not in TRACKED: continue
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
        "istanbul", "ankara", "athens", "praha", "bayer", "borussia", "hertha", "real", "club", "brugge",
        "juniors", "gimnasia", "esgrima", "plata", "central", "union", "santa", "atlas", "nacional", "universidad", "river", "plate", "independiente", "sporting", "deportes", "almagro", "lorenzo", "san", "old", "boys", "velez", "colon", "talleres", "racing", "estudiantes", "chacarita", "ferro", "carril", "oeste", "lanus", "huracan", "belgrano", "instituto", "platense", "andes", "argentinos", "rosario", "newell", "newells"}
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
    m_ = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv)
    if m_:   # 순위를 못 찾은 상대: 그 나라·단계 기준점(tools/league_rank_apply.py base())
        cal = m_.group(4) is None; y = int(m_.group(3)) + (0 if cal else 1)
        return int(round(_LRA['base'](_LRA['KO'][m_.group(1)], int(m_.group(2)), y, cal)))
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
# 아르헨티나 반시즌(아페르투라·클라우수라) 순위: TM 순위표는 2000-01 두 대회 순서가 RSSSF와 다름 → 영어 위키백과 시즌 문서
# (wiki_tables/, action=raw, 2026-11-19; RSSSF arg99·arg00·arg01 최종 순위와 여섯 대회 모두 같음)의 순서를 씀.
WT = os.path.join(HERE, "wiki_tables")
def wiki_tables(fn):
    t = open(os.path.join(WT, fn), encoding="utf-8").read(); out = {}
    for m in re.finditer(r"\{\{#invoke:sports table", t):
        b_ = t[m.start():]; b_ = b_[:b_.find("\n}}")]
        sec = re.search(r"\|section\s*=\s*([^\n|]+)", b_)
        names = {k: re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", v).strip() for k, v in re.findall(r"\|name_([^=\s]+)\s*=\s*([^\n]+)", b_)}
        order = re.search(r"\|team_order\s*=\s*([^\n]+)", b_)
        if order: teams = [x.strip() for x in order.group(1).split(",") if x.strip()]
        else:
            teams = []
            for _, nm_ in re.findall(r"\|team(\d+)\s*=\s*([^|\n]+)", b_):
                if nm_.strip() not in teams: teams.append(nm_.strip())
        out[sec.group(1).strip() if sec else "?"] = [names.get(x, x) for x in teams]
    return out
ARG_WIKI = {}   # (단계, 연도) -> [팀 이름(위키백과)]
for fn, yA, yC in (("1998–99_Argentine_Primera_División.txt", 1998, 1999), ("1999–2000_Argentine_Primera_División.txt", 1999, 2000),
                   ("2000–01_Argentine_Primera_División.txt", 2000, 2001)):
    w = wiki_tables(fn)
    ARG_WIKI[("Apertura", yA)] = w["Torneo Apertura"]; ARG_WIKI[("Clausura", yC)] = w["Torneo Clausura"]
# TM 이름 → 위키백과 이름
ARG_NAME = {"CA Boca Juniors": "Boca Juniors", "Club de Gimnasia y Esgrima La Plata": "Gimnasia y Esgrima (LP)", "Racing Club": "Racing",
            "CA Lanús": "Lanús", "CA Colón": "Colón", "CA San Lorenzo de Almagro": "San Lorenzo", "AA Argentinos Juniors": "Argentinos Juniors",
            "CA Newell's Old Boys": "Newell's Old Boys", "CA Unión (Santa Fe)": "Unión", "CA Rosario Central": "Rosario Central",
            "CA Vélez Sarsfield": "Vélez Sársfield", "Club Estudiantes de La Plata": "Estudiantes (LP)", "CA Talleres": "Talleres (C)",
            "Club Atlético Gimnasia y Esgrima (Jujuy)": "Gimnasia y Esgrima (J)", "CA River Plate": "River Plate", "CA Independiente": "Independiente",
            "Club Ferro Carril Oeste": "Ferro Carril Oeste", "CA Huracán": "Huracán", "Club Atlético Belgrano": "Belgrano", "Club Atlético Platense": "Platense",
            "CA Chacarita Juniors": "Chacarita Juniors", "Instituto ACC": "Instituto", "Club Almagro (Buenos Aires)": "Almagro", "CA Los Andes": "Los Andes"}
APERTURA_START = {1998: "1998-08-07", 1999: "1999-08-06", 2000: "2000-07-28"}   # RSSSF 1라운드 날짜
def arg_stage(d, cid, g):
    """경기 날짜에 진행 중이던 아르헨티나 1부 단계 (단계, 연도). 리그 경기는 그 경기의 대회."""
    if cid == "ARG1": return ("Apertura", int(g["seasonId"]))
    if cid == "ARGC": return ("Clausura", int(g["seasonId"]) + 1)
    y = int(d[:4])
    if y in APERTURA_START and d >= APERTURA_START[y]: return ("Apertura", y)
    return ("Clausura", y)
ARG_KEYS = {key(n) for n in ARG_NAME}
ARG_KO = {"Apertura": "아페르투라", "Clausura": "클라우수라"}
RANK_LOG = []
def arg_label(o, d, cid, g):
    st_, y = arg_stage(d, cid, g)
    L = ARG_WIKI[(st_, y)]; nm = ARG_NAME[o]
    r = L.index(nm) + 1
    tm = RANKS.get(("ARG1" if st_ == "Apertura" else "ARGC", f"{y if st_ == 'Apertura' else y - 1}-{str(y + (1 if st_ == 'Apertura' else 0))[2:]}"), {}).get(key(o))
    if tm and tm[0] != r: RANK_LOG.append((st_, y, o, tm[0], r))
    return f"아르헨티나 1부 {ARG_KO[st_]} {y} {r}위/{len(L)}팀", f"{y}/{st_}"

BIGL = {"PO1": "포르투갈 1부", "ES1": "라리가", "GB1": "프리미어리그", "IT1": "세리에A", "FR1": "리그1", "L1": "분데스리가", "NL1": "에레디비시"}
OTHL = {"GR1": ("그리스", "Super League Greece"), "TR1": ("튀르키예", "Süper Lig"), "RU1": ("러시아", "Russian Premier League")}
CAL_LG = {"RU1", "AR1N", "CLPD", "PR1A", "PR1C", "WER1"}
def make_label(lg, season, r, n):
    if lg in BIGL:
        pre = BIGL[lg]; y = int(season[:4]) + 1
        n0 = _LRA['ERA']['teams'](pre, y)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    if lg in OTHL:
        cn, nm = OTHL[lg]
        return f"{cn} 1부 {season} {r}위/{n}팀 ({nm})"
    if lg == "AR1N": return f"아르헨티나 1부 {season} {r}위/{n}팀"
    if lg == "PO2": return f"포르투갈 2부 {season} {r}위/{n}팀"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산)
def man(o, s, lv): MAN[(key(o), s)] = lv
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []

def opp_elo(o, d, cid, g):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    arg = k in ARG_KEYS and d < "2002-01-01"
    if arg: alv, aseason = arg_label(o, d, cid, g); seasons = [aseason]
    elif cid in ("AR1N",) or (k in ARG_KEYS and d[:4] == "2015"): seasons = [d[:4]]
    else: seasons = [eu(d), d[:4]]
    for s in seasons:
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d)
            ELO_SRC["순위 라벨(직접 확인)"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            p = _LRA['parse'](lv, d)
            if p and _LRA['value'](*p) != e: TABLE_DIFF.append((o, s, e, lv, _LRA['value'](*p)))
            if arg and lv.split(" (")[0] != alv and not re.sub(r"아르헨티나 1부 (\d{4}) (\d+위/\d+팀).*", "", lv) == "":
                pass
            if arg:
                rr = re.search(r"(\d+)위", lv.split(" (")[0]); ra = re.search(r"(\d+)위", alv)
                if rr and rr.group(1) != ra.group(1): TABLE_DIFF.append(("순위 다름", o, s, lv, alv))
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    if arg:
        e = lv_value(alv, d); ELO_SRC["순위표 → 라벨"] += 1; ELO_LOG[(o, d)] = ("rank", e, alv); NEW_TS[(o, seasons[0])] = (e, alv); return e, alv
    for (lg, s), t in RANKS.items():
        if lg in ("ARG1", "ARGC"): continue
        if k in t and (s == eu(d) or (lg in CAL_LG and s == d[:4])):
            r, n, nm, _ = t[k]
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
    elo, lv = opp_elo(opp(g), d, cid, g)
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
    fm = [r for r in FME[gid] if r["saviola_scorer"] == "1" and r["pen_shootout_event"] != "True"]
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
        if x[0] == "a" and re.search(r"Saviola", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(사비올라 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("사비올라 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("타인 도움 행이 사비올라 골과 같은 시각", b, r[9], r[4], hit[0][13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 사비올라 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("rivsv", "2001-07-25"), ("fcbsv", "2004-08-31"), ("monsv", "2005-08-13"), ("sevsv", "2006-07-01"), ("fcbsv", "2007-07-10"),
         ("rmasv", "2009-07-01"), ("bensv", "2012-08-30"), ("malsv", "2013-07-24"), ("olysv", "2014-09-01"), ("versv", "2015-07-01"), ("rivsv", None)]
TM_CLUB = {"209": "rivsv", "131": "fcbsv", "162": "monsv", "368": "sevsv", "418": "rmasv", "294": "bensv", "1084": "malsv", "683": "olysv", "276": "versv"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
def season_of(d, club):
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    if club == "rivsv": return str(y)
    if club == "bensv": s_ = y if (m, dd) >= (7, 10) else y - 1
    else: s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("리버 플레이트 1998~2001", "2001-07-25"), ("바르셀로나 2001~2004", "2004-08-31"), ("모나코", "2005-08-13"), ("세비야", "2006-07-01"),
          ("바르셀로나 2006-07", "2007-07-10"), ("레알 마드리드", "2009-07-01"), ("벤피카", "2012-08-30"), ("말라가", "2013-07-24"),
          ("올림피아코스", "2014-09-01"), ("엘라스 베로나", "2015-07-01"), ("리버 플레이트 2015", "9999")]
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

exec(open(os.path.join(HERE, "note_saviola.py"), encoding="utf-8").read())   # NOTE_LINES
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
