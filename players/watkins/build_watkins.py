#!/usr/bin/env python3
"""Ollie Watkins: raw/ -> watkins.json + wat.js (판정 근거는 judgments.md)

  python3 players/watkins/build_watkins.py [출력 data 폴더]  (기본: players/watkins/ — 오케스트레이터가 src/data로 옮김)
  (스크래치 복사본에서는 SOC_ROOT=<복사본> 으로 elo/·src/data·tools 기준을 바꿀 수 있음)

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(다른 차전),
      raw/fotmob_events.csv(도움 대조), raw/ranks.txt(순위표), elo/opponent_elo_by_team_season.csv + aliases.csv,
      src/data/*.js(같은 경기 다른 선수 자료 값·동료 대조; git으로 관리되는 파일만),
      tools/league_rank_apply.py(새 팀×시즌 값은 순위 라벨에서 계산 — 직접 숫자를 넣지 않음).
줄기는 음뵈모 build 스크립트(같은 수집기 계열, 브렌트퍼드 2019-20 동료).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else HERE
OUT_JS = os.path.join(DATA_DIR, "wat.js")
OUT_JSON = os.path.join(HERE, "watkins.json")
PID = "324358"
CUTOFF = "2026-11-21"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 도움 판정
# Transfermarkt 도움 중 FotMob 경기 이벤트에 왓킨스 도움이 없는 것(유형으로 빼는 PK 유도·상대 자책골 제외): gameId|분 -> (넣음 여부, 근거)
SINGLE = {
    "2658652|71": (0, "2016.3.19 노츠 카운티전 71분 히베이루 헤더 골: Transfermarkt만 왓킨스 도움, FotMob·ESPN은 트로이 브라운 도움으로 적음 → 뺌"),
    "2658672|28": (1, "2016.3.28 크롤리전 28분 제이크 테일러 골: 스카이 스포츠(PA) 경기 기사 ‘Watkins set up Taylor in front of goal’, 엑서터 구단 경기 기사 ‘Watkins showed great composure to roll the ball to Taylor’ → 넣음"),
    "2674762|79": (0, "2016.4.19 맨스필드전 79분 히베이루 중거리 골: ESPN 문자 중계만 왓킨스 도움, 엑서터 구단 기사·Exeter Daily 기사는 도움을 적지 않음(‘thirty-yard screamer’) → 다른 출처 2곳 확인 안 돼 뺌"),
    "2701693|100": (1, "2016.8.9 리그컵 1라운드 브렌트퍼드전 100분 할리 골(연장): ESPN 문자 중계 ‘Assisted by Ollie Watkins’, 브렌트퍼드 구단 기사 ‘Watkins got on to a long ball … he fed Harley’, West London Sport ‘the excellent Watkins played in Harley’ → 넣음"),
    "2726858|31": (0, "2016.8.13 하틀풀전 31분 매캘린든 골: Transfermarkt만 왓킨스 도움, FotMob·ESPN은 무어테일러 도움 → 뺌"),
    "2727147|41": (0, "2017.1.14 그림즈비전 41분 리드 골: Transfermarkt만 왓킨스 도움(헤더). 엑서터 구단 기사는 ‘제임스 코너킥이 리드 앞에 떨어졌다’, 스카이 스포츠는 ‘6야드에서 밀어 넣음’으로 왓킨스를 적지 않음 → 뺌"),
    "2764996|24": (0, "2016.10.18 EFL 트로피 첼시 U-23전 24분 휠러 골: Transfermarkt만 왓킨스 도움. West London Sport·Exeter Daily(구단 기사)는 휠러가 수비 둘을 제치고 감아 찬 개인 돌파 골로 적음 → 뺌"),
}
# FotMob(+다른 출처)에만 있는 도움: gameId|분 -> 근거
EXTRA = {
    "3219611|26": "2020.1.1 브리스틀 시티전 26분 벤라마 골: FotMob·ESPN 문자 중계(‘Assisted by Ollie Watkins’)·브렌트퍼드 구단 경기 기사(‘although Watkins was unable to force home the loose ball, he fed Benrahma, who slotted in’). Transfermarkt만 도움 없음 → 넣음",
}
SHOT_KEEP = {}
SCORE_FIX = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"GB1", "GB2", "GB4", "SA1", "POCC", "POG2"}   # 승격 플레이오프(챔피언십·리그 투)는 리그 비중(애슐리 영·음뵈모 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2024-25부터 리그 단계 = 조별과 같은 비중
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"
        if r.startswith("semi"): return "ecsf"
        if r.startswith("final"): return "ecf"
        return "eck"
    if cid == "ECLQ": return "ecq"
    if cid == "ACLE": return "acl"
    if cid in ("FAC", "CGB", "GBFL"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in ("POCC", "POG2"): return 1          # 플레이오프 결승은 단판
    if cid in LEAGUE_IDS: return 0
    if r.startswith("group"): return 0             # EFL 트로피 조별·유럽 대회 리그 단계·ACL 엘리트 리그 단계
    return 1

# ---------------------------------------------------------------- 입력
games = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

def ldate(g): return g["date_local_tz_conv"]
for g in games: g["opponent"] = g["opponent"].strip()

M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), g["opponent"], comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    if cid in ("CL", "EL", "UCOL", "ECLQ"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid in ("POCC", "POG2"): return (0, 1)       # EFL 플레이오프 준결승: 원정 다득점 없음, 연장(애슐리 영·음뵈모 선례)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None                          # FA컵 재경기는 단판
    m = MI[gid]; s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    oh, oa = map(int, m["other_leg_score"].split(":"))      # 이 경기 홈:원정 기준으로 적힌 다른 차전 스코어
    ours, theirs = (oh, oa) if s == "h" else (oa, oh)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def assist_reason(e):
    t = e["assist_type"]
    if e["own_goal"] == "1": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t in ("Shot on goal", "Deflected"): return "슈팅 굴절·리바운드('Shot on goal')"
    return None

def fm_has_assist(gid, mi):
    for f in FME[gid]:
        if f["wat_assist"] == "1":
            t = int(f["time"]) + int(f["overloadTime"] or 0)
            if abs(t - mi) <= 2: return True
            if int(f["time"]) in (45, 90) and not f["overloadTime"] and int(f["time"]) <= mi <= int(f["time"]) + 10: return True   # FotMob이 추가시간을 45·90분으로만 적은 경우
    return False

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0); ours = "home" if side == "h" else "away"
    for e in EVS[gid]:
        h, a = map(int, SCORE_FIX.get((gid, e["minute"]), e["score_home_away_after"]).split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == PID and e["own_goal"] != "1"
        is_a = e["assist_id"] == PID and e["scorer_id"] != PID and e["side"] == ours
        tag = f"{gid}|{e['minute']}"
        if e["assist_id"] == PID and e["scorer_id"] == PID:
            judg.append(("도움 제외", ldate(g), g["opponent"], e["minute"], e["scorer"], "본인 PK 골의 본인 도움"))
        if e["assist_id"] == PID and e["side"] != ours and e["own_goal"] != "1":
            judg.append(("상대 골 도움 칸(도움 아님)", ldate(g), g["opponent"], e["minute"], e["scorer"], e["assist_type"]))
        if e["assist_id"] == PID and e["own_goal"] == "1": is_a = True
        if tag in EXTRA and not is_g: is_a = True
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        d = ldate(g)
        if is_a:
            if tag in EXTRA:
                judg.append(("FotMob 등에만 있는 도움 넣음", d, g["opponent"], e["minute"], e["scorer"], EXTRA[tag]))
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"])); continue
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", d, g["opponent"], e["minute"], e["scorer"], why))
            elif fm_has_assist(gid, mi):
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
            elif tag in SINGLE:
                ok, src = SINGLE[tag]
                judg.append(("단일 출처 도움 " + ("넣음" if ok else "뺌"), d, g["opponent"], e["minute"], e["scorer"], src))
                if ok: raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
            else:
                sys.exit("FotMob에 없는 도움 판정 누락: " + tag + " " + d + " " + g["opponent"])
        if is_g:
            if e["side"] != ours: sys.exit("득점 편 이상 " + tag)
            pk = 1 if e["penalty"] == "1" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))
# FotMob 이벤트에서 왓킨스 도움인데 Transfermarkt 도움이 아닌 것이 EXTRA 밖에 있으면 멈춤
for gid, fl in FME.items():
    if gid not in G: continue
    for f in fl:
        if f["wat_assist"] == "1":
            t = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(r[0] == "a" and r[1] == gid and abs(r[2] - t) <= 2 or (r[0] == "a" and r[1] == gid and f["time"] in ("45", "90") and int(f["time"]) <= r[2] <= int(f["time"]) + 10) for r in raw_rows):
                if not any(j[1] == ldate(G[gid]) and abs(mins(j[3])[0] - t) <= 2 or (j[1] == ldate(G[gid]) and f["time"] in ("45", "90") and int(f["time"]) <= mins(j[3])[0] <= int(f["time"]) + 10) for j in judg):
                    sys.exit(f"FotMob 도움 판정 누락 {gid} {f['time']} {f['scorer']}")
# ---------------------------------------------------------------- 상대 Elo
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
    k = norm(n); return ALIAS.get(k, k)

TABLE = {}
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

TRACKED = set(os.path.basename(x) for x in subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
if not TRACKED:   # 스크래치 복사본(git 없음): 원래 저장소의 목록을 씀
    TRACKED = set(os.path.basename(x) for x in subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b not in TRACKED or b in ("hon.js", "wat.js", "clubcolors.js", "finals.js"): continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)
SAME = collections.defaultdict(collections.Counter)
for b, (oe, om) in OTHERS.items():
    for x in oe: SAME[(x[9], key(x[1]))][(x[2], x[12])] += 1

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
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

# 스플릿 리그(스위스·오스트리아 등) 그룹 표 → 최종 순위(1그룹 1~6위, 2그룹 7~12위)
for (lg, s2), t in list(RANKS.items()):
    mm = re.match(r"(\d{4}-\d{2}) group([12])$", s2)
    if mm:
        for k_, (r, n, nm) in t.items():
            RANKS[(lg, mm.group(1))][k_] = (r + (6 if mm.group(2) == "2" else 0), 12, nm)

def eu(d):
    if "2020-06-01" <= d <= "2020-08-31": return "2019-20"     # 코로나 재개 경기(챔피언십 2020.6~8)는 2019-20
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANK_FIX = {}
NOW = "2026년 11월 중순 현재 순위"
def make_label(lg, s, r, n):
    y = int(s[:4])
    if lg == "GB1": return f"프리미어리그 {s} {r}위" + ("" if n == 20 else f"/{n}팀")
    if lg == "GB2": return f"챔피언십 {s} {r}위/{n}팀"
    if lg == "GB3": return f"잉글랜드 3부 {s} {r}위/{n}팀 ({'EFL' if y >= 2016 else 'Football'} League One, 리그 수준 추정)"
    if lg == "GB4": return f"잉글랜드 4부 {s} {r}위/{n}팀 ({'EFL' if y >= 2016 else 'Football'} League Two, 리그 수준 추정)"
    if lg == "CNAT": return f"잉글랜드 5부 {s} {r}위/{n}팀 (National League, 리그 수준 추정)"
    if lg == "SA1": return f"사우디 1부 {s} {r}위/{n}팀 (Saudi Pro League, {NOW})"
    if lg == "QSL": return f"카타르 1부 {s} {r}위/{n}팀 (Qatar Stars League, {NOW})"
    if lg == "UAE1": return f"UAE 1부 {s} {r}위/{n}팀 (UAE Pro League, {NOW})"
    return None
# 순위표가 없는 상대: (팀, 시즌) -> 라벨
MANUAL = {
    ("Chelsea FC U23", "2016-17"): "잉글랜드 4부 2016-17 순위 없음 (첼시 23세 이하 팀, 프리미어리그 2 소속으로 리그 피라미드 밖 — EFL 트로피 초청 팀이라 그 대회 하위 단계인 4부 기준점; 리그 수준 추정)",
}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def opp_elo(opp, d, cid):
    k = key(opp)
    same = SAME.get((d, k))
    if same:
        (e, lv), _ = same.most_common(1)[0]
        if len(same) > 1: print("  [같은 경기 값 여럿]", opp, d, dict(same))
        ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(opp, d)] = ("same", e, lv); return e, lv
    s = eu(d)
    for s2 in [s]:
        if (k, s2) in TABLE:
            e, lv = TABLE[(k, s2)]
            p = _LRA['parse'](lv, d)
            if p and _LRA['value'](*p) not in (None, e): TABLE_DIFF.append((opp, s2, e, lv, _LRA['value'](*p)))
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(opp, d)] = ("table", e, lv, s2); return e, lv
    if (opp, s) in MANUAL:
        lv = MANUAL[(opp, s)]
        e = int(round(_LRA['base']('England', 4, int(s[:4]) + 1, False)))
        ELO_SRC["순위 없음 기준점"] += 1; ELO_LOG[(opp, d)] = ("base", e, lv); NEW_TS[(opp, s)] = (e, lv); return e, lv
    for (lg, s2), t in RANKS.items():
        if s2 == s and k in t:
            r, n, nm = t[k]
            r = RANK_FIX.get((lg, s2, nm), r)
            lv = make_label(lg, s, r, n)
            if lv:
                e = lv_value(lv, d)
                ELO_SRC["순위표 → 라벨"] += 1; ELO_LOG[(opp, d)] = ("rank", e, lv); NEW_TS[(opp, s)] = (e, lv); return e, lv
    MISS.append((opp, d, cid, s)); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(g["opponent"], d, cid)
    et = 1 if (g["gameState"] == "extra_time" and mi > 90 and ko and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, g["opponent"], elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))

chk = collections.defaultdict(set)
for (o, d), v in ELO_LOG.items():
    if v[0] in ("rank", "base"): chk[(key(o), eu(d))].add(v[1])
for k_, v in chk.items():
    if len(v) > 1: sys.exit(f"같은 팀-시즌 값 여럿 {k_} {v}")

if MISS:
    for x in MISS: print("상대 Elo 없음:", x)
    sys.exit(1)

# ---------------------------------------------------------------- 동료·같은 경기 대조(보고용)
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and re.search(r"Watkins", str(x[13])):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7]) == (x[5], x[6], x[2], x[12], x[3], x[7])
            cross.append(("동료 도움→왓킨스 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "왓킨스 골 없음"), x[2:8], hit[0][2:8] if hit else None))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and key(x[1]) == key(r[1]) and abs(x[4] - r[4]) <= 2]
            if hit:
                ok = (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7]) == (r[5], r[6], r[2], r[12], r[3], r[7])
                cross.append(("왓킨스 도움→동료 골", b, r[9], r[4], r[13], "일치" if ok else "값 다름", r[2:8], hit[0][2:8]))
    for r in E:
        for x in oe:
            if x[9] == r[9] and key(x[1]) == key(r[1]) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3] or x[7] != r[7]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[3], x[7], x[12]), (r[2], r[3], r[7], r[12])))
        if x[9:10] and False: pass
    mm = {(m[0], key(m[1])): m[2] for m in om}
    for m in M:
        c = mm.get((m[0], key(m[1])))
        if c and c != m[2]: cross.append(("같은 경기 출전 행 대회 다름", b, m[0], m[1], c, m[2]))
    # 동료 파일의 골 중 TM이 왓킨스 도움으로 적었는데 이 자료에 도움 행이 없는 것
    for x in oe:
        if x[0] != "g": continue
        for gid, evs in EVS.items():
            if gid not in G or ldate(G[gid]) != x[9] or key(G[gid]["opponent"]) != key(x[1]): continue
            for e in evs:
                if e["assist_id"] == PID and abs(mins(e["minute"])[0] - x[4]) <= 2 and e["scorer_id"] != PID:
                    if not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                        cross.append(("동료 골에 TM 왓킨스 도움, 이 자료에서 뺌", b, x[9], x[4], e["scorer"], e["assist_type"]))
DUP = set(); cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 합계
CLUBS = [("2017-07-18", "엑서터 시티"), ("2020-09-09", "브렌트퍼드"), ("2026-08-30", "애스턴 빌라"), ("9999-12-31", "알힐랄")]
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for _, n in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
TM_A_API = sum(int(g["assists"]) for g in games)
TM_G_API = sum(int(g["goals"]) for g in games)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
SKIP = [j for j in judg if j[0] == "단일 출처 도움 뺌"]
ADDS = [j for j in judg if j[0] in ("단일 출처 도움 넣음", "FotMob 등에만 있는 도움 넣음")]
first, last = M[0], M[-1]
SKIPTXT = {"2016-03-19": "2016.3.19 노츠 카운티전 71분 히베이루 골(FotMob·ESPN은 트로이 브라운 도움)",
           "2016-04-19": "2016.4.19 맨스필드전 79분 히베이루 골(ESPN 문자 중계에만 왓킨스 도움, 구단·지역 기사에는 도움 언급 없음)",
           "2016-08-13": "2016.8.13 하틀풀전 31분 매캘린든 골(FotMob·ESPN은 무어테일러 도움)",
           "2016-10-18": "2016.10.18 EFL 트로피 첼시 U-23전 24분 휠러 골(기사는 휠러 개인 돌파 골)",
           "2017-01-14": "2017.1.14 그림즈비전 41분 리드 골(구단·스카이 기사는 코너킥 뒤 리드가 밀어 넣은 골로 적고 왓킨스 언급 없음)"}
assert sorted(SKIPTXT) == sorted(j[1] for j in SKIP), [j[1] for j in SKIP]
NOTE_LINES = [
    f"올리 왓킨스(엑서터 시티·브렌트퍼드·애스턴 빌라·알힐랄)의 클럽 공식 경기 {NG}경기({d_(first[0])} 하틀풀 유나이티드전 ~ {d_(last[0])} 샤바브 알아흘리전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기 제외",
    f"클럽별 경기·골·도움: 엑서터 시티 {c3(ST['엑서터 시티'])}, 브렌트퍼드 {c3(ST['브렌트퍼드'])}, 애스턴 빌라 {c3(ST['애스턴 빌라'])}, 알힐랄 {c3(ST['알힐랄'])}. 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(90분 추정 없음), 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부, Transfermarkt 경기 자료(JSON)와 대조), FotMob·ESPN 경기 기록과 대조. 엑서터·브렌트퍼드·애스턴 빌라의 시즌·대회별 경기 수·골 수는 영어 위키백과와 모두 같음(알힐랄은 위키백과 표가 덜 갱신됨: 7경기 5골, Transfermarkt·FotMob 11경기 8골)",
    "뺀 기록: 웨스트소퍼메어 임대(2014.12~2015.5, 내셔널 리그 사우스 = 잉글랜드 6부 비프로 리그; 영어 위키백과 25경기 10골, FotMob 경기 이벤트 9골, 경기별 출전 자료 없음)는 프로 리그 규칙으로 뺌. 엑서터 유소년, 잉글랜드 대표팀, 애스턴 빌라 친선경기(FotMob 7경기 5골)도 뺌",
    "EFL 트로피(풋볼 리그 트로피) 3경기는 엑서터 1군 경기라 국내컵으로 넣음: 2014.10.7 코번트리전 86분 골(단판), 2016.10.18 첼시 U-23전 2분 골(조별 리그), 2016.11.8 스윈던전(조별, 1-1 뒤 보너스 승점용 승부차기 — 승부차기 골은 셈하지 않음)",
    "골: 191골 모두 Transfermarkt와 FotMob이 같은 경기·같은 순서. 추가시간 골은 Transfermarkt 분을 씀(FotMob이 2016~2019 풋볼 리그 경기에서 90분·45분으로만 적은 2016.4.2 플리머스전 90+2분, 2016.12.31 뉴포트전 90+5분, 2017.1.31 위컴전 90+5분, 2017.2.25 블랙풀전 45+5분, 2019.10.19 밀월전 90+4분, 2019.10.28 QPR전 90+4분 골과 2019.2.2 블랙번전 90+2분 도움). PK 골 6개, PK 실축 7개(골 아님). 왓킨스 자책골 없음",
    "도움은 Transfermarkt와 FotMob 경기 이벤트가 같이 적은 것을 기준으로 하고, 한쪽에만 있는 것은 다른 출처 2곳이 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 도움 {TM_A_API}개 − PK 유도 {EX['PK 유도']}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 − 확인 못 한 단일 출처 {len(SKIP)}개 + FotMob·ESPN·구단 기사로 확인한 도움 1개",
    "PK 유도로 뺀 도움(FotMob·ESPN도 도움 없음): 2017.1.2 레이턴 오리엔트전 65분 할리, 2018.10.6 리즈전 62분 모페, 2019.1.28 FA컵 바닛전 60분 모페, 2019.3.2 QPR전 50분 모페, 2023.8.20 에버턴전 24분 더글라스 루이스, 2023.9.16 크리스털 팰리스전 90+8분 더글라스 루이스",
    "상대 자책골에 붙은 도움으로 뺀 것: 2018.3.6 버턴전 60분 맥패드진 자책골. 2024.12.4 브렌트퍼드전 28분 본인 PK 골에 Transfermarkt 리포트가 본인을 PK 유도자로 적은 것은 도움 아님(골로만 셈)",
    "다른 출처로 확인해 넣은 도움: 2016.3.28 크롤리전 28분 제이크 테일러 골(Transfermarkt만; 스카이 스포츠 경기 기사·엑서터 구단 경기 기사), 2016.8.9 리그컵 브렌트퍼드전 연장 100분 할리 골(Transfermarkt·ESPN; 브렌트퍼드 구단 기사·West London Sport), 2020.1.1 브리스틀 시티전 26분 벤라마 골(FotMob·ESPN, Transfermarkt에는 없음; 브렌트퍼드 구단 기사 ‘왓킨스가 흘러나온 공을 벤라마에게 내줌’)",
    "확인하지 못해 뺀 단일 출처 도움(Transfermarkt만 또는 Transfermarkt·ESPN만): " + "; ".join(SKIPTXT[k] for k in sorted(SKIPTXT)),
    "출전 분은 Transfermarkt 그대로. 연장 경기는 2016.8.9 리그컵 브렌트퍼드전(1-0 연장 승, 100분 도움), 2017.8.8 리그컵 AFC 윔블던전(3-1 연장 승, 105+1분 골), 2020.8.4 챔피언십 플레이오프 결승 풀럼전(1-2 연장 패), 2024.4.18 컨퍼런스리그 8강 2차전 릴전(연장 뒤 승부차기 승) 넷. 승부차기 경기(2016 스윈던, 2019 케임브리지, 2024 릴, 2025 브렌트퍼드)의 승부차기 골은 셈하지 않음",
    "날짜는 경기 현지 날짜(잉글랜드 경기는 런던, 알힐랄은 리야드, 유럽 원정은 개최지 시간; Transfermarkt 일정 날짜와 차이 없음)",
    "상대 Elo는 같은 경기를 다룬 다른 선수 자료(음뵈모·베일리·디아비·마르티넬리 등)의 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위(Transfermarkt 순위표, 진행 중 시즌은 2026년 11월 중순 순위) 순으로 씀. 리그 원·리그 투·내셔널 리그 상대는 순위에 하부 리그 수준을 붙인 추정",
    "첼시 U-23(2016-17 EFL 트로피)은 리저브 리그(프리미어리그 2) 팀이라 순위가 없어 잉글랜드 4부 기준점 값으로 추정",
    "대회 비중: 리그 투·챔피언십 승격 플레이오프는 리그 비중(준결승 두 경기 합산 — 원정 다득점 없이 연장, 결승 단판). FA컵·리그컵·EFL 트로피는 국내컵(16강까지 낮은 비중, 8강부터 높은 비중), EFL 트로피 조별은 리그식. 컨퍼런스리그 2023-24(플레이오프 라운드 히버니언 포함)·챔스 2024-25(리그 단계는 조별 비중)·유로파리그 2025-26(우승, 결승 프라이부르크전 출전)·AFC 챔피언스리그 엘리트 2026-27 리그 단계",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기): 2017 리그 투 플레이오프 준결승 칼라일전, 2020 챔피언십 플레이오프 준결승 2차전 스완지전, 2023 컨퍼런스리그 플레이오프 히버니언전, 2024 컨퍼런스리그 아약스·릴·올림피아코스전, 2026 유로파리그 릴·볼로냐·노팅엄 포리스트전(2021-22부터 원정 다득점 없음)",
    "시즌 구분: 모든 클럽 8월 1일 기준(2020.8.4 플레이오프 결승은 2019-20, 알힐랄은 다른 선수 자료처럼 7월 10일 기준이지만 7월 경기 없음). 클럽 구분 2017.7.18 브렌트퍼드, 2020.9.9 애스턴 빌라, 2026.8.30 알힐랄(Transfermarkt 이적일)",
    "우승·수상: 유로파리그 2025-26(애스턴 빌라). EFL 챔피언십 올해의 선수 2019-20(리그 사무국), PFA 올해의 팀 2019-20 챔피언십·2023-24 프리미어리그. 2017 리그 투·2020 챔피언십 플레이오프는 결승 패배. 프리미어리그 플레이메이커 상 2023-24·팬 투표 올해의 팀 등은 표 항목 밖",
    f"{d_(CUTOFF)} 기준 현역(알힐랄). 마지막 반영 경기 {d_(last[0])} AFC 챔피언스리그 엘리트 샤바브 알아흘리전(2-0 승, 90분 2골)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "cwc", "clg", "cl16", "clk", "df", "lg", "acl", "ecq"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []; seen = set()
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
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
open(OUT_JS, "w", encoding="utf-8").write(f"const WAT_E={J(E)};\nconst WAT_M={J(M)};\nconst WAT_NOTE={J(NOTE)};\n")
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg, "cross_check": cross,
           "elo_sources": ELO_SRC, "elo_log": {f"{o}|{s}": v for (o, s), v in ELO_LOG.items()},
           "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()}, "table_label_diff": TABLE_DIFF},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · TM {TM_G_API}골 {TM_A_API}도움 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if "일치" not in c: print("  대조:", c)
print("일치 대조", sum(1 for c in cross if "일치" in c))
print("새 팀-시즌", len(NEW_TS))
print("통합표 라벨 재계산 차이", TABLE_DIFF)
