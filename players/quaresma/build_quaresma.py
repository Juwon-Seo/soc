#!/usr/bin/env python3
"""히카르두 콰레스마 (Ricardo Andrade Quaresma Bernardo, Transfermarkt 4188): raw/ -> quaresma.json + src/data/qua.js (판정 근거는 judgments.md)

  python3 players/quaresma/build_quaresma.py            # 파일 쓰기
  python3 players/quaresma/build_quaresma.py --debug    # Elo 출처 로그
  python3 players/quaresma/build_quaresma.py --stat     # 요약·판정·동료 대조
  python3 players/quaresma/build_quaresma.py --ties     # 합산 행

시망 build(players/simao, 같은 형식의 원자료)를 바탕으로 함. 상대 Elo는 v1.226 규칙: 같은 경기 다른 선수 자료 → Elo 통합표(같은 팀·시즌)
→ 출처로 확인한 순위로 라벨(`<리그> <시즌> N위[/M팀]`)을 만들고 tools/league_rank_apply.py 의 value()로 값을 정함(직접 숫자를 넣지 않음).
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "qua.js")
OUT_JSON = os.path.join(HERE, "quaresma.json")
ME = "4188"
ME_KO = "히카르두 콰레스마"
PFX = "QUA"

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
LEAGUE = {"PO1", "ES1", "IT1", "GB1", "TR1", "POT1", "UAE1"}   # POT1 = 쉬페르 리그 2011-12 챔피언십 플레이오프(리그로 셈, 시망 선례)
CUP = {"CDR", "POPO", "TRP", "FAC", "UAEC"}                    # UAEC = UAE 대통령컵(Transfermarkt에 없음, 기사로 추가)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "POCP":   # 타사 다 리가: 조별은 리그식 국내컵(브루노·하피냐·팔카오 선례), 8강(단판)·준결승
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        if r.startswith("group"): return "dc"
    if cid in ("USC", "POSU", "TRS"): return "df"     # UEFA 슈퍼컵·수페르타사·튀르키예 슈퍼컵 = 국내컵 결승 비중
    if cid == "WEPO": return "cwc"                    # 인터콘티넨털컵 2004(피구·델피에로 등 선례)
    if cid == "CLQ": return "clq"                     # 3차 예선·플레이오프
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid in ("UEQ", "ELQ"): return "elq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        return "elk"                                     # 2·3라운드·16강
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 32강('Second Round'·intermediate stage)·16강·8강
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
    if cid == "CDR": return (1, 1)                                         # 코파 델 레이 2018-19까지
    if cid == "TRP": return (1, 1)                                         # 튀르키예컵 2020-21까지(v1.152)
    if cid == "POPO": return (1, 1)                                        # 타사 준결승(브루누·팔카오·나니 선례)
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

# UAE 대통령컵 2012-13 8강(Transfermarkt에 없음): 2013.2.11 알아흘리 1-0 디바 알푸자이라, 콰레스마 결승골(약 62분, 도움 없음).
# Gulf News('Quaresma off the mark for Al Ahli': 52분 기회 'ten minutes later' 콰레스마 골, 전반에도 슈팅), The National('President's Cup: Al Ahli 1 Dibba Al Fujairah 0',
# 두 번째 출전·그라피치 출전 정지로 공격수로 나섬). 날짜: 영어 위키백과 2012–13 UAE President's Cup. 출전 분 출처 없음 → 90분 추정(선발로 보고 교체 기록 없음).
MANUAL_M = [["2013-02-11", "Dibba Al-Fujairah Club", "dk", 90, 1]]
MANUAL_E = [("g", "2013-02-11", "Dibba Al-Fujairah Club", "UAEC", 62, 0, 0, 0, 0, 1)]   # (유형, 날짜, 상대, 대회, 분, gf, ga, pk, dm, ko)
M.extend(MANUAL_M); M.sort(key=lambda m: m[0])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

# 2014.8 이후 단일 출처 도움(FotMob 도움 없음) 웹 확인: 키 = gameId|분
A_CHECK = {
    "2466867|87": (True, "아부바카르 87분 골: Bola na Rede 경기 기사('Quaresma ... fez uma assistência para Aboubakar ... finalizar com frieza'), "
                         "IANS 기사(business-standard, 'following a brilliant pass from Quaresma'), ESPN 경기 이벤트(도움 Ricardo Quaresma) — 독립 출처 3곳"),
    "2512211|32": (True, "아부바카르 32분 헤더: ESPN 경기 이벤트(도움 Ricardo Quaresma), IANS/신화 기사(business-standard, 'with a header, following a cross by Quaresma') — 독립 출처 2곳"),
    "2526205|33": (True, "올리베르 토레스 33분 헤더: Bola na Rede 경기 기사('duas assistências ... dois cruzamentos praticamente iguais'), FourFourTwo('head Quaresma's cross'), "
                         "Gazeta Esportiva('Ricardo Quaresma realizou belo cruzamento ... Óliver') — 독립 출처 3곳"),
    "2526205|45": (True, "아부바카르 45분(ESPN 45+1) 골: Bola na Rede 기사(두 번째 도움), FourFourTwo('Quaresma's delivery from the right wing ... Aboubakar touched the ball home'), "
                           "Gazeta Esportiva('cruzou rasteiro para Aboubakar') — 독립 출처 3곳"),
    "2526248|12": (True, "잭슨 마르티네스 12분 헤더: Bola na Rede 경기 기사('excelente cruzamento para a cabeça de Jackson'), EFE 계열 El Colombiano('Quaresma, también pasador en el primer tanto') "
                         "— 독립 출처 2곳. Reuters(SBS 게재)는 브라이미의 크로스로 적어 출처가 갈림"),
    "2526248|86": (True, "잭슨 마르티네스 86분 바이시클킥: Bola na Rede 기사('Ricardo Quaresma cruzou de forma perfeita para Jackson'), El Colombiano('al recibir una asistencia de Quaresma') — 독립 출처 2곳"),
}
def a_key(gid, minute): return f"{gid}|{minute}"

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["time"] and f["quaresma_assist"] == "1" and fm_min_match(f, e["minute"], 3): return True   # 3분: 2021.2.8 B SAD전 TM 38분·FotMob 41분(같은 1-1 골)
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
        return None if ok else "2014.8 이후 단일 출처, 확인 못 함"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음"))
    sys.exit("2014.8 이후 단일 출처 도움 판정 없음 " + k)

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
# FotMob에만 있는 콰레스마 도움(Transfermarkt는 다른 판정): 넣지 않음
judg.append(("FotMob 단독 도움 제외", "2010-08-26", "HJK Helsinki", "67", "Guti",
             "FotMob은 콰레스마 도움, Transfermarkt 리포트는 보부(Bobô) 도움 — 2014.8 전 기준 출처(Transfermarkt)와 다름"))
judg.append(("FotMob 단독 도움 제외", "2016-12-17", "Kasimpasa", "31", "Cenk Tosun",
             "FotMob만 콰레스마 도움, Transfermarkt는 도움 없음('Tap-in'). NTV·파나틱 기사: 콰레스마 슈팅을 골키퍼가 막고 나온 공을 젱크 토순이 머리로 넣음 = 슈팅 리바운드라 도움 아님"))

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
# 3000411(2018.5.3 페네르바체 원정 몰수 3:0)·3495414(2020.12.13 산타클라라전 0:1, 골 목록 없음): 콰레스마 골·도움 없음
SM_OK = set()
for gid, *_ in SCORE_MISMATCH:
    if any(r[1] == gid for r in raw_rows) and gid not in SM_OK: sys.exit("골 목록이 모자란 리포트에 콰레스마 기록 " + gid)

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
    if b in ("hon.js", "clubcolors.js", "finals.js", "qua.js") or "src/data/" + b not in TRACKED: continue
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
WIKI = {("PO1", f"{y}-{str(y + 1)[2:]}"): f"{y}–{str(y + 1)[2:]}_Primeira_Liga.txt" for y in (2001, 2002, 2003, 2004, 2005, 2006, 2007, 2013, 2014, 2020, 2021)}
WIKI.update({("TR1", f"{y}-{str(y + 1)[2:]}"): f"{y}–{str(y + 1)[2:]}_Süper_Lig.txt" for y in (2010, 2011, 2015, 2016, 2017, 2018, 2019)})
def wiki_order(fn):
    t = open(os.path.join(WT, fn), encoding="utf-8").read()
    i = t.lower().find("#invoke:sports table"); t = t[i:]; t = t[:t.find("\n}}")]
    names = {m.group(1): re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", m.group(2)).strip() for m in re.finditer(r"\|name_([^=\s]+)\s*=\s*(\[\[[^\]]*\]\]|[^|\n]+)", t)}
    for m in re.finditer(r"\|win_([A-Z0-9_]+)\s*=[^\n]*?<!--\s*([^-]+?)\s*-->", t):   # team_order 형식: 이름은 주석
        names.setdefault(m.group(1), m.group(2))
    out = {}
    mo = re.search(r"\|team_order\s*=\s*([^\n|]+)", t)
    if mo:
        for n, c in enumerate([x.strip() for x in mo.group(1).split(",") if x.strip()], 1): out[n] = names.get(c, c)
        return out
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
RANK_FIX = {   # TM 순위표가 1단계 순위인 리그: 최종 순위(스플릿·플레이오프 뒤, 위키백과 시즌 문서)
    (key("FK Partizan Belgrade"), "2018-19"): (3, 16, "세르비아 수페르리가 2018-19: 챔피언십 라운드 3위 = 최종 3위/16팀(위키백과 2018–19 Serbian SuperLiga)"),
    (key("Maccabi Tel Aviv"), "2011-12"): (6, 16, "이스라엘 2011-12: 정규 7위 → 상위 플레이오프 6위 = 최종 6위/16팀(위키백과 2011–12 Israeli Premier League)"),
}

BIGL = {"PO1": "포르투갈 1부", "ES1": "라리가", "GB1": "프리미어리그", "IT1": "세리에A", "FR1": "리그1", "L1": "분데스리가", "NL1": "에레디비시"}
OTHL = {"BE1": ("벨기에", "Belgian First Division A"), "DK1": ("덴마크", "Danish Superliga"), "GR1": ("그리스", "Super League Greece"),
        "ISR1": ("이스라엘", "Israeli Premier League"), "SE1": ("스웨덴", "Allsvenskan"), "SER1": ("세르비아", "Serbian SuperLiga"),
        "TR1": ("튀르키예", "Süper Lig"), "TS1": ("체코", "Czech First League"), "UKR1": ("우크라이나", "Ukrainian Premier League"),
        "ALB1": ("알바니아", "Kategoria Superiore"), "FARO": ("페로 제도", "Effodeildin"), "FI1": ("핀란드", "Veikkausliiga"),
        "WER1": ("벨라루스", "Belarusian Premier League"), "UAE1": ("UAE", "UAE Pro League")}
CAL_LG = {"SE1", "FARO", "FI1", "WER1"}
def make_label(lg, season, r, n):
    if lg in BIGL:
        pre = BIGL[lg]; y = int(season[:4]) + 1
        n0 = _LRA['ERA']['teams'](pre, y)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    if lg in OTHL:
        cn, nm = OTHL[lg]
        return f"{cn} 1부 {season} {r}위/{n}팀 ({nm})"
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
for typ, d, o, cid, mi, gf, ga, pk, dm, ko in MANUAL_E:
    elo, lv = opp_elo(o, d, cid)
    E.append([typ, o, elo, comp_of(cid, "Quarter-Finals"), mi, gf, ga, ko, pk, d, 0, dm, lv, 0])

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
    fm = [r for r in FME[gid] if r["quaresma_scorer"] == "1" and r["pen_shootout_event"] != "True"]
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
        if x[0] == "a" and re.search(r"Quaresma", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(콰레스마 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("콰레스마 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("타인 도움 행이 콰레스마 골과 같은 시각", b, r[9], r[4], hit[0][13], cmp_rows(r, hit[0]) or "같음"))
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
                    CROSS.append(("TM 콰레스마 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("scpqr", "2003-07-09"), ("fcbqr", "2004-07-06"), ("fcpqr", "2008-09-01"), ("intqr", "2009-02-02"), ("cheqr", "2009-06-30"),
         ("intqr", "2010-07-01"), ("bjkqr", "2013-01-07"), ("ahlqr", "2014-01-01"), ("fcpqr", "2015-07-22"), ("bjkqr", "2019-08-29"),
         ("kasqr", "2020-09-07"), ("vitqr", None)]
TM_CLUB = {"336": "scpqr", "131": "fcbqr", "720": "fcpqr", "46": "intqr", "631": "cheqr", "114": "bjkqr", "15541": "ahlqr", "10484": "kasqr", "2420": "vitqr"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("스포르팅 CP 2001~2003", "2003-07-09"), ("바르셀로나 2003~2004", "2004-07-06"), ("포르투 2004~2008", "2008-09-01"),
          ("인테르 2008~2010", "2009-02-02"), ("첼시(임대) 2009", "2009-06-30"), ("인테르 2008~2010 ", "2010-07-01"),
          ("베식타시 2010~2012", "2013-01-07"), ("알아흘리(두바이) 2013", "2014-01-01"), ("포르투 2014~2015", "2015-07-22"),
          ("베식타시 2015~2019", "2019-08-29"), ("카슴파샤 2019~2020", "2020-09-07"), ("비토리아 기마랑이스 2020~2022", "9999")]
def stint(d):
    for n, u in STINTS:
        if d < u: return n.strip()
ST = collections.OrderedDict((n.strip(), [0, 0, 0, 0]) for n, u in STINTS)
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
if "--facts" in sys.argv:
    FM_GAMES = [gid for gid in EVS if gid in G and any(r["time"] for r in FME.get(gid, [])) and any(e["scorer_id"] == ME and not is_og(e) for e in EVS[gid])]
    print("FM goal games", len(FM_GAMES), sum(1 for gid in FM_GAMES for e in EVS[gid] if e["scorer_id"] == ME and not is_og(e)))
    print("ET rows", [(r[9], r[1], r[4], r[3]) for r in E if r[10]])
    print("ET games", [(g["date_local_tm_report"], opp(g), g["competitionId"], g["round"], g["gameState"], g["playedMinutes"]) for g in GAMES if g["gameState"] != "regularly_terminated"])
    print("TM goals no FM events", [(ldate(G[gid]), opp(G[gid])) for gid in EVS if gid in G and not any(r["time"] for r in FME.get(gid, [])) and ldate(G[gid]) >= "2010-07-01" and any(e["scorer_id"] == ME for e in EVS[gid])])
    print("UNTYPED", UNTYPED, collections.Counter(r[8] for r in raw_rows if r[0] == "a"))
    print("min diffs", [(ldate(G[gid]), opp(G[gid])) for gid in []])
    sys.exit(0)
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

exec(open(os.path.join(HERE, "note_quaresma.py"), encoding="utf-8").read())   # NOTE_LINES
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
