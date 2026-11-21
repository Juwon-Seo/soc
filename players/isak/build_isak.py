#!/usr/bin/env python3
"""알렉산데르 이사크 (Alexander Isak, Transfermarkt 349066): raw/ -> isak.json + src/data/isa.js (판정 근거는 judgments.md)

  python3 players/isak/build_isak.py            # 파일 쓰기
  python3 players/isak/build_isak.py --debug    # Elo 출처 로그
  python3 players/isak/build_isak.py --stat     # 요약·판정·동료 대조
  python3 players/isak/build_isak.py --ties     # 합산 행

시망 build(players/simao)를 바탕으로 함. 상대 Elo는 v1.226 규칙: 같은 경기 다른 선수 자료 → Elo 통합표(같은 팀·시즌)
→ 출처로 확인한 순위로 라벨(`<리그> <시즌> N위[/M팀]`)을 만들고 tools/league_rank_apply.py 의 value()로 값을 정함(직접 숫자를 넣지 않음).
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "isa.js")
OUT_JSON = os.path.join(HERE, "isak.json")
ME = "349066"
ME_KO = "알렉산데르 이사크"
PFX = "ISA"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

ALLG = rd("tm_games.csv")
GAMES = [g for g in ALLG if g["level"] == "senior"]          # 도르트문트 2군(레기오날리가 베스트 4부) 12경기·유스 11경기 제외
EXCL = [g for g in ALLG if g["level"] != "senior"]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
PM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# 모든 경기가 유럽(스웨덴·독일·네덜란드·스페인·잉글랜드 및 유럽 대회) — Transfermarkt 리포트 날짜 = 일정 날짜 = 현지 날짜
for g in GAMES:
    if g["date_local"] != g["date_local_tm_report"]: sys.exit("날짜 다름 " + g["gameId"])
def ldate(g): return g["date_local"]
def opp(g): return g["opponent"].strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용(이사크는 모두 이 뒤)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"SE1", "L1", "NL1", "ES1", "GB1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("SEC", "DFB", "NLP", "CDR", "FAC", "CGB"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                                      # 조별(스벤스카 쿠펜)·1~5라운드·16강
    if cid == "SUC": return "dsf" if r.startswith("semi") else "df"   # 수페르코파 4팀 준결승
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 조별, 2024-25부터 리그 페이즈('Group Stage')
        if r.startswith("last 16") or r.startswith("intermediate"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 32강·녹아웃 플레이오프(intermediate stage)·16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g): return g["round"]

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r: return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "EL", "ELQ"): return (1, 1) if d < "2021-07-01" else (0, 1)   # UEFA 원정 다득점 2020-21까지
    if cid == "CDR": return (0, 1)              # 코파 델 레이 준결승 2019-20: 원정 다득점 없음(2018-19까지), 연장
    if cid == "CGB": return (0, 0)              # 리그컵 준결승 2018-19부터 원정 다득점·연장 없이 승부차기
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; oid = m["other_leg_id"]; club = G[gid]["club_id"]
    o = MI[oid]; fh, fa = map(int, o["final"].split(":"))
    if o["home_id"] == club: return (fh, fa)
    if o["away_id"] == club: return (fa, fh)
    sys.exit("다른 차전 편 판정 실패 " + gid)

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

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["time"] and f["isak_assist"] == "1" and f["pen_shootout_event"] != "True" and fm_min_match(f, e["minute"]): return True
    return False

# Transfermarkt 리포트에만 있는 도움(FotMob 경기 이벤트에 이사크 도움 없음): 키 = gameId|분 -> (넣음 여부, 근거)
A_CHECK = {
    "2914241|42": (True, "2017.10.24 DFB-포칼 2라운드 마그데부르크전 42분 곤살루 카스트루 골: Transfermarkt 이사크 도움(유형 '헤더'), FotMob은 도움자 없음. "
                         "beIN Sports(Omnisport) 경기 기사 'Castro was the beneficiary of an assist from Alexander Isak … steered Isak's knockdown'·"
                         "폭스슈티메(마그데부르크 지역지) 경기 기사 '이사크가 헤더 경합에서 이긴 공을 카스트루가 완전히 빈 자리에서 넣음' — 다른 출처 2곳"),
    "3141203|15": (False, "2019.5.15 에레디비시 ADO 덴하흐전 15분 다밀 당커르뤼 골: Transfermarkt만 이사크 도움(유형 없음), FotMob 경기 이벤트는 도움자 없음"
                          "(FotMob 선수 경기 목록의 도움 1은 같은 경기 48분 파블리디스 골 도움 — 두 출처가 같이 적은 것). 다른 출처로 확인하지 못함"),
    "3286280|46": (True, "2019.12.19 코파 델 레이 1라운드 베세릴전 46분 야누자이 골: Transfermarkt 'Pass', 라리가 공식 경기 페이지(스페인어 문자중계 'Asistencia de Alexander Isak')·"
                         "LiveSoccerTV 경기 기록('Assist: A. Isak') — 다른 출처 2곳(FotMob은 이 경기 라인업·도움 자료 없음)"),
    "3700906|70": (True, "2021.12.1 코파 델 레이 1라운드 파나데리아 풀리도전 70분 나이스 주아라 골: Transfermarkt + FotMob 선수 경기 목록 도움 1(FotMob 경기 이벤트에는 이 경기 골 목록이 없음), "
                         "라리가 공식 문자중계·ESPN 경기 기록도 이사크 도움"),
}
# FotMob 경기 이벤트에만 있는 이사크 도움(Transfermarkt 리포트 없음): 키 = gameId|분 -> 근거(모두 뺌)
FM_ONLY = {
    "4171293|17": "2023.10.4 챔스 조별 PSG전 17분 알미론 골: 이사크의 슈팅을 돈나룸마가 막은 공을 알미론이 밀어 넣음(nufc.com 경기 기사·90min 평점 기사) — "
                  "슈팅 리바운드라 도움 아님(FotMob 경기 이벤트에만 도움, FotMob 선수 경기 목록 0, Transfermarkt 도움 없음)",
}

A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    k = f"{gid}|{e['minute']}"
    if fm_assist(gid, e):
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]
        A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "단일 출처(확인 못 함)"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음"))
    return "판정 없음"

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
            if why == "판정 없음": sys.exit("FotMob에 없는 도움 판정 누락: " + gid + "|" + e["minute"])
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["penalty"] == "1" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))
# FotMob에만 있는 도움 확인
for gid, fl in FME.items():
    if gid not in G: continue
    for f in fl:
        if f["isak_assist"] == "1" and f["isak_scorer"] != "1" and f["time"]:
            t = int(f["time"]) + int(f["overloadTime"] or 0)
            if any(e["assist_id"] == ME and abs(mins(e["minute"])[0] - t) <= 2 for e in EVS[gid]): continue
            k = f"{gid}|{f['time']}"
            if k not in FM_ONLY: sys.exit("FotMob에만 있는 도움 판정 누락 " + k)
            judg.append(("도움 제외", ldate(G[gid]), opp(G[gid]), f["time"], f["scorer"], FM_ONLY[k]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
PENS = {"3151159", "3497553", "4285020", "4436240", "5056518"}
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":"))
    if gid in PENS: continue
    if (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
for gid in G:
    if gid not in EVS and MI[gid]["final"] != "0:0" and gid not in PENS: SCORE_MISMATCH.append((gid, "골 목록 없음", MI[gid]["final"]))
if any(x[0] in {r[1] for r in raw_rows} for x in SCORE_MISMATCH): sys.exit("골 목록이 모자란 리포트에 이사크 기록 " + str(SCORE_MISMATCH))

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
def key(n):
    k = norm(n)
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
    if b in ("hon.js", "clubcolors.js", "isa.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "town", "albion", "rovers", "hotspur", "palace", "villa", "ham", "manchester", "west", "aston", "borussia", "bv", "vfl",
        "sociedad", "madrid", "atletico", "fk", "if", "ifk", "bk", "ff", "sk", "hove", "brighton", "and", "wanderers", "forest", "nottingham"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d):
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
        if len(p) < 5 or p[0] == "league" or not p[2].isdigit(): continue
        nm = re.sub(r"\s*\((?:TM|en\.wikipedia).*\)$", "", p[4]).strip()
        RANKS[(p[0], p[1].split(" ")[0])][key(nm)] = (int(p[2]), int(p[3]), nm, p[1])

BIGL = {"ES1": "라리가", "GB1": "프리미어리그", "L1": "분데스리가", "NL1": "에레디비시"}
def make_label(lg, season, r, n):
    if lg in BIGL:
        pre = BIGL[lg]; y = int(season[:4]) + 1
        n0 = _LRA['ERA']['teams'](pre, y)
        if season == "2026-27": return f"{pre} {season} {r}위/{n}팀 (2026년 11월 중순 현재 순위)"   # 진행 중 시즌(다른 선수 자료와 같은 형식)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    if lg == "SE1": return f"스웨덴 1부 {season} {r}위/{n}팀 (Allsvenskan)"
    if lg == "SE3N": return f"스웨덴 3부 {season} {r}위/{n}팀 (Division 1 Norra, 리그 수준 추정)"
    if lg == "ES2": return f"세군다 {season} {r}위" + ("" if n == 22 else f"/{n}팀")
    if lg == "GB2": return f"챔피언십 {season} {r}위" + ("" if n == 24 else f"/{n}팀")
    if lg == "GB3": return f"잉글랜드 3부 {season} {r}위/{n}팀 (EFL League One, 리그 수준 추정)"
    if lg == "L3": return f"독일 3부 {season} {r}위/{n}팀 (3. Liga, 리그 수준 추정)"
    if lg == "E4G4": return f"스페인 4부 {season} {r}위/{n}팀 (Segunda División RFEF Grupo 4, 리그 수준 추정)"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산)
def man(o, s, lv): MAN[(key(o), s)] = lv
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []

def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    if cid in ("SE1",): seasons = [d[:4]]
    elif cid == "SEC": seasons = [d[:4] if d[5:7] >= "04" else str(int(d[:4]) - 1)]   # 스웨덴 리그는 4~11월(달력 연도)
    else: seasons = [eu(d)]
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
        if k in t and s in seasons:
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
    for x in sorted(NEW_TS.items()): print("NEW", x)
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or not any(r["time"] for r in FME.get(gid, [])): continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["isak_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "true")]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["penalty"] == "1"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "penalty" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["penalty"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))

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
        if x[0] == "a" and re.search(r"Isak\b", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(이사크 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("이사크 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("타인 도움 행이 이사크 골과 같은 시각", b, r[9], r[4], hit[0][13], cmp_rows(r, hit[0]) or "같음"))
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
# 이사크 골에 TM이 적은 동료 도움이 그 동료 파일에 있는지
MATE = {"Mikel Oyarzabal": "oya.js", "Martin Ødegaard": "ode.js", "Martin Odegaard": "ode.js", "David Silva": "sil.js", "Mohamed Salah": "sal.js",
        "Florian Wirtz": "wir.js", "Federico Chiesa": "chi.js", "Bradley Barcola": "bcl.js", "Christian Pulisic": "pul.js", "Mario Götze": "got.js",
        "Marco Reus": "reu.js", "Jadon Sancho": "sch.js", "Shinji Kagawa": "kag.js", "Pierre-Emerick Aubameyang": "aub.js", "Andriy Yarmolenko": None}
for gid, evs in EVS.items():
    if gid not in G: continue
    for e in evs:
        if e["scorer_id"] == ME and e["assist_player"] in MATE and MATE[e["assist_player"]]:
            b = MATE[e["assist_player"]]; d = ldate(G[gid])
            if b in OTHERS:
                oe, om = OTHERS[b]
                if not any(x[0] == "a" and x[9] == d and re.search("Isak", str(x[13])) for x in oe):
                    CROSS.append(("TM 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"], "출전 행 있음" if any(m[0] == d for m in om) else "출전 행 없음"))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(str(j[3]))[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("이사크 도움으로 적힌 것을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("aikis", "2017-01-23"), ("bvbis", "2019-01-25"), ("wilis", "2019-07-01"), ("rsois", "2022-08-26"), ("newis", "2025-09-01"), ("livis", None)]
TM_CLUB = {"272": "aikis", "16": "bvbis", "403": "wilis", "681": "rsois", "762": "newis", "31": "livis"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club == "aikis": return str(y)
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("AIK", "2017-01-23"), ("보루시아 도르트문트", "2019-01-25"), ("빌럼 II", "2019-07-01"), ("레알 소시에다드", "2022-08-26"),
          ("뉴캐슬 유나이티드", "2025-09-01"), ("리버풀", "9999")]
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
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A)
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    for c in CROSS: print(c)
    print("FM", FM_CMP)
    print("score mismatch", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("TABLE_DIFF", TABLE_DIFF)
    for x in sorted(NEW_TS.items()): print("NEW", x)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_isak.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "elk", "elq", "elg", "cwc", "df", "clg", "cl16", "clk"]:
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
        if b[4] > a[4] and b[5] < a[5] + 1: problems.append(("스코어 역순", d, a[4], b[4]))
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
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
