#!/usr/bin/env python3
"""Cole Palmer: raw/ -> palmer.json + pal.js (판정 근거는 judgments.md)

  python3 players/palmer/build_palmer.py [출력 data 폴더]  (기본: players/palmer/ — 오케스트레이터가 src/data로 옮김)
  (스크래치 복사본에서는 SOC_ROOT=<복사본> 으로 elo/·src/data·tools 기준을 바꿀 수 있음)

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(다른 차전),
      raw/fotmob_events.csv(도움 대조), raw/ranks.txt(순위표), elo/opponent_elo_by_team_season.csv + aliases.csv,
      src/data/*.js(같은 경기 다른 선수 자료 값·동료 대조; git으로 관리되는 파일만),
      tools/league_rank_apply.py(새 팀×시즌 값은 순위 라벨에서 계산 — 직접 숫자를 넣지 않음).
줄기는 왓킨스 build 스크립트(같은 수집기 계열), 대회 코드는 포든 build(맨체스터 시티 동료).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else HERE
OUT_JS = os.path.join(DATA_DIR, "pal.js")
OUT_JSON = os.path.join(HERE, "palmer.json")
PID = "568177"
CUTOFF = "2026-11-21"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 도움 판정
# Transfermarkt 도움 중 FotMob 경기 이벤트에 파머 도움이 없는 것(유형으로 빼는 PK 유도·상대 자책골 제외): gameId|분 -> (넣음 여부, 근거)
SINGLE = {
    "3710352|14": (1, "2022.1.7 FA컵 3라운드 스윈던전 14분 베르나르두 실바 골: Transfermarkt(유형 Pass)·ESPN('ast: Cole Palmer')이 파머 도움, FotMob은 도움자 없음. "
                      "잉글랜드 축구협회 경기 기사(thefa.com ‘fine work by Palmer down the right helped set up Silva for a simple finish’), "
                      "아이리시 타임스 기사(‘waltzing past Ellis Iandolo … sending in a delicious cross into the six-yard box, where Silva was on hand to tap in’), "
                      "PA 통신 기사(FourFourTwo 게재, ‘Teenager Palmer played the ball into the box and Silva timed his run perfectly’) → 넣음"),
}
# FotMob(+다른 출처)에만 있는 도움: gameId|분 -> 근거 (없음: FotMob에만 있는 도움은 2026.7.28 친선경기뿐)
EXTRA = {}
SCORE_FIX = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"GB1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2025-26 리그 단계('Group Stage') = 조별과 같은 비중
        if r.startswith("intermediate") or r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UCOL":
        if r.startswith("group") or r.startswith("league"): return "ecg"
        if r.startswith("semi"): return "ecsf"
        if r.startswith("final"): return "ecf"
        return "eck"
    if cid == "ECLQ": return "ecq"
    if cid == "KLUB": return "cwc"
    if cid in ("GBCS", "USC"): return "df"               # 커뮤니티 실드·UEFA 슈퍼컵(포든·데 브라위너 선례)
    if cid in ("FAC", "CGB"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round"): return "dk"
        return "dc"                                       # FA컵 5라운드·리그컵 4라운드 = 16강까지
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE_IDS: return 0
    if r.startswith("group") or r.startswith("league"): return 0   # 챔스 조별·리그 단계, 클럽 월드컵 2025 조별(리그식)
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
    if cid == "CGB": return (1, 1) if d < "2018-07-01" else (0, 0)   # 리그컵 준결승: 2018-19부터 원정 다득점·연장 없이 승부차기(포든 선례)
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
            if int(f["time"]) in (45, 90) and not f["overloadTime"] and int(f["time"]) <= mi <= int(f["time"]) + 10: return True
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
for gid, fl in FME.items():
    if gid not in G: continue
    for f in fl:
        if f["wat_assist"] == "1":
            t = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(r[0] == "a" and r[1] == gid and abs(r[2] - t) <= 2 for r in raw_rows):
                if not any(j[1] == ldate(G[gid]) and abs(mins(j[3])[0] - t) <= 2 for j in judg):
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
if not TRACKED:
    TRACKED = set(os.path.basename(x) for x in subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b not in TRACKED or b in ("hon.js", "pal.js", "clubcolors.js", "finals.js"): continue
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
        s2 = p[1].replace(" (calendar year)", "")
        RANKS[(p[0], s2)][key(p[4])] = (int(p[2]), int(p[3]), p[4])
# 스플릿 리그(스위스) 그룹 표 → 최종 순위(1그룹 1~6위, 2그룹 7~12위)
for (lg, s2), t in list(RANKS.items()):
    mm = re.match(r"(\d{4}-\d{2}) group([12])$", s2)
    if mm:
        for k_, (r, n, nm) in t.items():
            RANKS[(lg, mm.group(1))][k_] = (r + (6 if mm.group(2) == "2" else 0), 12, nm)

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# Transfermarkt 덴마크 2024-25 표는 정규 22라운드 순위(코펜하겐 2위) — 챔피언십 라운드 뒤 최종은 코펜하겐 우승(영어 위키백과 2024–25 Danish Superliga)
RANK_FIX = {("DK1", "2024-25", "FC Copenhagen"): 1, ("DK1", "2024-25", "FC Midtjylland"): 2}
NOW = "2026년 11월 중순 현재 순위"
def make_label(lg, s, r, n):
    cur = s == "2026-27"
    if lg == "GB1": return f"프리미어리그 {s} {r}위" + (f"/{n}팀 ({NOW})" if cur else ("" if n == 20 else f"/{n}팀"))
    if lg == "GB2": return f"챔피언십 {s} {r}위/{n}팀" + (f" (EFL Championship, {NOW})" if cur else "")
    if lg == "GB3": return f"잉글랜드 3부 {s} {r}위/{n}팀 (EFL League One, " + (f"{NOW}, " if cur else "") + "리그 수준 추정)"
    if lg == "GB4": return f"잉글랜드 4부 {s} {r}위/{n}팀 (EFL League Two, " + (f"{NOW}, " if cur else "") + "리그 수준 추정)"
    if lg == "C1": return f"스위스 1부 {s} {r}위/{n}팀 (Swiss Super League, 플레이오프·스플릿 뒤 최종 순위)"
    if lg == "DK1": return f"덴마크 1부 {s} {r}위/{n}팀 (Danish Superliga, 플레이오프·스플릿 뒤 최종 순위)"
    if lg == "BRA1": return f"브라질 세리에 A {s} {r}위/{n}팀"
    return None
MANUAL = {}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def seasons_for(cid, d):
    s = eu(d)
    if cid in ("KLUB", "UCOL", "CL", "ECLQ", "USC"): return [s, d[:4]]   # 달력 연도 리그 상대(브라질·MLS·스웨덴 등)
    return [s]
def opp_elo(opp, d, cid):
    k = key(opp)
    same = SAME.get((d, k))
    if same:
        (e, lv), _ = same.most_common(1)[0]
        if len(same) > 1: print("  [같은 경기 값 여럿]", opp, d, dict(same))
        ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(opp, d)] = ("same", e, lv); return e, lv
    for s2 in seasons_for(cid, d):
        if (k, s2) in TABLE:
            e, lv = TABLE[(k, s2)]
            p = _LRA['parse'](lv, d)
            if p and _LRA['value'](*p) not in (None, e): TABLE_DIFF.append((opp, s2, e, lv, _LRA['value'](*p)))
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(opp, d)] = ("table", e, lv, s2); return e, lv
    for s2 in seasons_for(cid, d):
        for (lg, ss), t in RANKS.items():
            if ss == s2 and k in t:
                r, n, nm = t[k]
                r = RANK_FIX.get((lg, ss, nm), r)
                lv = make_label(lg, s2, r, n)
                if lv:
                    e = lv_value(lv, d)
                    ELO_SRC["순위표 → 라벨"] += 1; ELO_LOG[(opp, d)] = ("rank", e, lv); NEW_TS[(opp, s2)] = (e, lv); return e, lv
    MISS.append((opp, d, cid, eu(d))); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(g["opponent"], d, cid)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and ko and not (dm and str(dm).startswith("90+"))) else 0
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
        if x[0] == "a" and x[13] and re.search(r"Cole Palmer", str(x[13])):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7]) == (x[5], x[6], x[2], x[12], x[3], x[7])
            cross.append(("동료 도움→파머 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "파머 골 없음"), x[2:8], hit[0][2:8] if hit else None))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and key(x[1]) == key(r[1]) and abs(x[4] - r[4]) <= 2]
            if hit:
                ok = (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7]) == (r[5], r[6], r[2], r[12], r[3], r[7])
                cross.append(("파머 도움→동료 골", b, r[9], r[4], r[13], "일치" if ok else "값 다름", r[2:8], hit[0][2:8]))
    for r in E:
        for x in oe:
            if x[9] == r[9] and key(x[1]) == key(r[1]) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3] or x[7] != r[7]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[3], x[7], x[12]), (r[2], r[3], r[7], r[12])))
    mm = {(m[0], key(m[1])): m[2] for m in om}
    for m in M:
        c = mm.get((m[0], key(m[1])))
        if c and c != m[2]: cross.append(("같은 경기 출전 행 대회 다름", b, m[0], m[1], c, m[2]))
    for x in oe:
        if x[0] != "g": continue
        for gid, evs in EVS.items():
            if gid not in G or ldate(G[gid]) != x[9] or key(G[gid]["opponent"]) != key(x[1]): continue
            for e in evs:
                if e["assist_id"] == PID and abs(mins(e["minute"])[0] - x[4]) <= 2 and e["scorer_id"] != PID:
                    if not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                        cross.append(("동료 골에 TM 파머 도움, 이 자료에서 뺌", b, x[9], x[4], e["scorer"], e["assist_type"]))
DUP = set(); cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 합계
CLUBS = [("2023-09-01", "맨체스터 시티"), ("9999-12-31", "첼시")]
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
assert not SKIP and len(ADDS) == 1, (SKIP, ADDS)
first, last = M[0], M[-1]
NOTE_LINES = [
    f"콜 파머(맨체스터 시티·첼시)의 클럽 공식 경기 {NG}경기({d_(first[0])} 리그컵 번리전 ~ {d_(last[0])} 선덜랜드전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기 제외",
    f"클럽별 경기·골·도움: 맨체스터 시티 {c3(ST['맨체스터 시티'])}, 첼시 {c3(ST['첼시'])}. 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(90분 추정 없음), 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부, Transfermarkt 경기 자료(JSON)와 대조), FotMob·ESPN 경기 기록과 대조. 시즌·대회별 경기 수·골 수는 영어 위키백과와 모두 같음",
    "뺀 기록: 맨체스터 시티 U-21·U-23(프리미어리그 2와 EFL 트로피 3경기 1골 1도움 포함, 2군)·U-18·U-19(유소년), 잉글랜드 대표팀, 친선경기(FotMob 기준 맨체스터 시티 8경기·첼시 7경기)",
    f"골: {NGo}골 모두 Transfermarkt·FotMob·ESPN이 같은 경기·같은 순서로 적음. PK 골 {NPK}개, PK 실축 2개(2025.3.9 레스터전, 2026.5.4 노팅엄 포리스트전 — 골 아님). 파머 자책골 없음",
    "도움은 Transfermarkt와 FotMob 경기 이벤트가 같이 적은 것을 기준으로 하고, 한쪽에만 있는 것은 다른 출처 2곳이 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 도움 {TM_A_API}개 − 상대 자책골에 붙은 도움 {EX['상대 자책골 유도']}개. Transfermarkt가 본인 PK 골에 본인을 PK 유도자로 적은 2개(2024.4.15 에버턴전 64분, 2024.12.8 토트넘전 84분)는 도움이 아님(골로만 셈)",
    "상대 자책골에 붙은 도움으로 뺀 것: 2025.2.3 웨스트햄전 74분 완비사카 자책골(Transfermarkt 유형 '슈팅'; FotMob·ESPN은 도움자 없음, FotMob 경기 목록도 도움 0)",
    "다른 출처로 확인해 넣은 도움: 2022.1.7 FA컵 스윈던전 14분 베르나르두 실바 골(Transfermarkt·ESPN, FotMob은 도움자 없음; 잉글랜드 축구협회 경기 기사·아이리시 타임스 기사·PA 통신 기사가 파머의 돌파 뒤 크로스로 적음). 확인하지 못해 뺀 도움은 없음",
    "출전 분은 Transfermarkt 그대로. 연장 경기는 2024.2.25 리그컵 결승 리버풀전(0-1 연장 패, 120분)과 2025.6.28 클럽 월드컵 16강 벤피카전(4-1 연장 승, 117분 도움) 둘. 승부차기 경기(2021 리그컵 웨스트햄, 2023 커뮤니티 실드 아스널, 2023 UEFA 슈퍼컵 세비야, 2023 리그컵 뉴캐슬)의 승부차기 골은 스코어에 넣지 않음",
    "2023.8.6 커뮤니티 실드 아스널전(웸블리 중립 경기)은 Transfermarkt가 아스널을 홈, FotMob이 맨체스터 시티를 홈으로 적었지만 77분 파머 골 전 스코어는 0-0으로 같음(다른 선수 자료와 같은 값)",
    "날짜는 경기 현지 날짜(잉글랜드 경기는 런던, 유럽 원정은 개최지 시간). 클럽 월드컵 2025 8강 팔메이라스전은 필라델피아 저녁 경기라 2025.7.4(Transfermarkt 일정은 UTC 기준 7.5)",
    "상대 Elo는 같은 경기를 다룬 다른 선수 자료(데 브라위너·스털링·산초 등)의 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위(Transfermarkt 순위표, 진행 중인 2026-27 시즌은 2026년 11월 중순 순위) 순으로 씀. 리그 원·리그 투 상대는 순위에 하부 리그 수준을 붙인 추정",
    "대회 비중: FA컵·리그컵은 국내컵(16강까지 낮은 비중, 8강부터 높은 비중), 커뮤니티 실드·UEFA 슈퍼컵은 국내컵 결승 비중. 챔스 리그 단계(2025-26)는 조별 비중. 컨퍼런스리그 2024-25(플레이오프 라운드 세르베트전 포함, 우승). 클럽 월드컵 2025는 조별 리그식, 16강부터 단판(우승). 2024.2.7 FA컵 4라운드 재경기 애스턴 빌라전은 단판",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기): 2024 리그컵 준결승 2차전 미들즈브러전(원정 다득점·연장 없이 승부차기), 2025 컨퍼런스리그 준결승 1차전 유르고르덴전(2021-22부터 원정 다득점 없음)",
    "시즌 구분: 8월 1일 기준(클럽 월드컵 2025는 2024-25). 클럽 구분 2023.9.1 첼시(Transfermarkt 이적일)",
    "우승·수상: 챔피언스리그 2022-23·UEFA 슈퍼컵 2023-24·프리미어리그 4회(2020-21~2023-24, 맨체스터 시티 소속 시즌; Transfermarkt 기준 — 영어 위키백과는 2022-23만 적음, 2020-21은 리그 출전 없음·2023-24는 1경기)·FA컵 2023·리그컵 2021(맨체스터 시티), 컨퍼런스리그 2024-25·클럽 월드컵 2025(첼시). 클럽 월드컵 2025 골든볼과 PFA·프리미어리그 영플레이어상은 칸이 없어 적지 않음",
    f"{d_(CUTOFF)} 기준 현역(첼시). 마지막 반영 경기 {d_(last[0])} 프리미어리그 선덜랜드전(0-1 패, 90분)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "cwc", "clg", "cl16", "clk", "df", "lg", "acl", "ecq", "ecg", "eck"]:
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
open(OUT_JS, "w", encoding="utf-8").write(f"const PAL_E={J(E)};\nconst PAL_M={J(M)};\nconst PAL_NOTE={J(NOTE)};\n")
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
