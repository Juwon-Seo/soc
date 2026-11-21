#!/usr/bin/env python3
"""Michael Olise: raw/ -> olise.json + src/data/oli.js (판정 근거는 judgments.md)

  python3 players/olise/build_olise.py [출력 data 폴더]
  (스크래치 복사본에서는 SOC_ROOT=<복사본> 으로 elo/·src/data·tools 기준을 바꿀 수 있음)

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(다른 차전),
      raw/fotmob_events.csv(도움 대조), raw/ranks.txt(순위표), elo/opponent_elo_by_team_season.csv + aliases.csv,
      src/data/*.js(같은 경기 다른 선수 자료 값·동료 대조; git으로 관리되는 파일만),
      tools/league_rank_apply.py(새 팀×시즌 값은 순위 라벨에서 계산 — 직접 숫자를 넣지 않음).
줄기는 루이스 디아스·훌리안 알바레스 build 스크립트(같은 계열 수집기), 순위 라벨→값은 시망 build 방식.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else os.path.join(ROOT, "src", "data")
OUT_JS = os.path.join(DATA_DIR, "oli.js")
OUT_JSON = os.path.join(HERE, "olise.json")
PID = "566723"
CUTOFF = "2026-11-18"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 도움 판정
# Transfermarkt 도움 중 FotMob 경기 이벤트에 Olise 도움이 없는 것(유형으로 빼는 PK 유도·상대 자책골 제외): gameId|분 -> (넣음 여부, 근거)
SINGLE = {
    "3710350|58": (1, "2022.1.8 FA컵 밀월전 58분 마테타 골(올리세 크로스, 헤더): 크리스털 팰리스 구단 경기 기사(cpfc.co.uk)·스카이 스포츠 기사(‘Mateta headed home after help from Olise’). FotMob 선수 경기 목록도 도움 1"),
    "4353910|79": (1, "2024.8.16 DFB-포칼 울름전 79분 코망 골: FC 바이에른 구단 경기 기사(올리세가 코망에게 내줘 밀어 넣음)·Astro(stadiumastro) 경기 기사(‘Olise's trickery set Coman up’). FotMob 선수 경기 목록도 도움 1"),
    "4373547|1": (1, "2024.12.20 라이프치히전 1분 무시알라 골: 분데스리가 공식 경기 기사(‘1-0 Musiala 1' (assist: Olise)’)·FC 바이에른 구단 경기 기사(올리세의 옆 패스를 무시알라가 마무리)"),
    "4445096|11": (1, "2024.12.10 챔스 샤흐타르전 11분 라이머 골: ESPN 경기 기록(‘Assisted by Michael Olise’)·분데스리가 공식 사이트 경기 기사(‘1-1 Laimer 11' (assist: Olise)’). FotMob 선수 경기 목록도 도움 1"),
}
# 'Shot on goal' 판정: 넣는 것 없음. 2025.5.10 묀헨글라트바흐전 31분 케인 골은 올리세의 슈팅을 케인이 머리로 살짝 방향만 바꾼 골(로이터 기사) → 굴절·슈팅 리바운드로 뺌
SHOT_KEEP = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"GB1", "GB2", "L1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2024-25부터 리그 단계 = 조별과 같은 비중
        if r.startswith("last 16") or r.startswith("intermediate"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "KLUB": return "cwc"
    if cid == "DFL": return "df"
    if cid in ("FAC", "CGB", "DFB"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE_IDS: return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 입력
games = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

def ldate(g): return g["date_local_computed"]
for g in games: g["opponent"] = g["opponent"].strip()

M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), g["opponent"], comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    if cid == "CL": return (1, 1) if d < "2021-07-01" else (0, 1)
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
    if t == "Shot on goal": return "슈팅 굴절·리바운드('Shot on goal')"
    return None

def fm_has_assist(gid, mi):
    for f in FME[gid]:
        if f["olise_assist"] == "1":
            t = int(f["time"]) + int(f["overloadTime"] or 0)
            if abs(t - mi) <= 2: return True
    return False

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0); ours = "home" if side == "h" else "away"
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == PID and e["own_goal"] != "1"
        is_a = e["assist_id"] == PID and e["scorer_id"] != PID and e["side"] == ours
        if e["assist_id"] == PID and e["side"] != ours:
            judg.append(("상대 골 도움 칸(도움 아님)", ldate(g), g["opponent"], e["minute"], e["scorer"], e["assist_type"]))
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        tag = f"{gid}|{e['minute']}"
        mi, dm = mins(e["minute"])
        d = ldate(g)
        if is_a:
            why = assist_reason(e)
            if why and tag in SHOT_KEEP:
                why = None; judg.append(("도움 넣음(Shot on goal)", d, g["opponent"], e["minute"], e["scorer"], SHOT_KEEP[tag]))
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
    if b not in TRACKED or b in ("hon.js", "oli.js", "clubcolors.js"): continue
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

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 순위 확인: 챔피언십 2020-21(TM 표 = 영어 위키백과 최종 순위), 리그 원 2019-20(시즌 중단 뒤 경기당 승점 최종 순위 13위/23팀, 베리 제명),
# 리그 투 2021-22(하틀풀 17위), 2. 분데스리가 2026-27(진행 중, 2026.11.18 TM 표 4위 — 같은 표의 뉘른베르크 2위는 호프만 자료 라벨과 같음)
def make_label(lg, s, r, n):
    if lg == "GB1": return f"프리미어리그 {s} {r}위" + ("" if n == 20 else f"/{n}팀")
    if lg == "GB2": return f"챔피언십 {s} {r}위/{n}팀"
    if lg == "GB3": return f"잉글랜드 3부 {s} {r}위/{n}팀 (EFL League One, 리그 수준 추정)"
    if lg == "GB4": return f"잉글랜드 4부 {s} {r}위/{n}팀 (EFL League Two, 리그 수준 추정)"
    if lg == "L1": return f"분데스리가 {s} {r}위" + ("" if n == 18 else f"/{n}팀")
    if lg == "L2":
        return f"2. 분데스리가 {s} {r}위/{n}팀 (2. Bundesliga" + (", 2026년 11월 중순 현재 순위)" if s == "2026-27" else ")")
    return None

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def opp_elo(opp, d, cid):
    k = key(opp)
    same = SAME.get((d, k))
    if same:
        (e, lv), _ = same.most_common(1)[0]
        if len(same) > 1: print("  [같은 경기 값 여럿]", opp, d, dict(same))
        ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(opp, d)] = ("same", e, lv); return e, lv
    s = eu(d)
    seasons = [s, d[:4]] if cid in ("KLUB", "CL") else [s]     # 달력 연도 리그 상대(노르웨이·뉴질랜드·남미)는 연도 키
    if cid == "KLUB" and opp == "CA Boca Juniors": seasons = ["2025/Apertura"]
    for s2 in seasons:
        if (k, s2) in TABLE:
            e, lv = TABLE[(k, s2)]
            p = _LRA['parse'](lv, d)
            if p and _LRA['value'](*p) not in (None, e): TABLE_DIFF.append((opp, s2, e, lv, _LRA['value'](*p)))
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(opp, d)] = ("table", e, lv, s2); return e, lv
    for (lg, s2), t in RANKS.items():
        if s2 == s and k in t:
            r, n, _ = t[k]
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
    if v[0] == "rank": chk[(key(o), eu(d))].add(v[1])
for k_, v in chk.items():
    if len(v) > 1: sys.exit(f"같은 팀-시즌 값 여럿 {k_} {v}")

# ---------------------------------------------------------------- 동료·같은 경기 대조(보고용)
MATE_NAME = {"kan.js": "Harry Kane", "mus.js": "Jamal Musiala", "gna.js": "Serge Gnabry", "mul.js": "Thomas Müller",
             "san.js": "Leroy Sané", "ldz.js": "Luis Díaz", "com.js": "Kingsley Coman"}
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and re.search(r"Michael Olise", str(x[13])):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (x[5], x[6], x[2], x[12], x[3])
            cross.append(("동료 도움→올리세 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "올리세 골 없음"), x[2:7], hit[0][2:7] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and r[13] == nm:
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (r[5], r[6], r[2], r[12], r[3])
                cross.append(("올리세 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else "동료 골 없음"), r[2:7], hit[0][2:7] if hit else None))
    for r in E:
        for x in oe:
            if x[9] == r[9] and key(x[1]) == key(r[1]) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3] or x[7] != r[7]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[3], x[7], x[12]), (r[2], r[3], r[7], r[12])))
    # 같은 날 같은 상대 출전 행의 대회 코드
    mm = {(m[0], key(m[1])): m[2] for m in om}
    for m in M:
        c = mm.get((m[0], key(m[1])))
        if c and c != m[2]: cross.append(("같은 경기 출전 행 대회 다름", b, m[0], m[1], c, m[2]))
for gid, evs in EVS.items():
    if gid not in G: continue
    for e in evs:
        if e["scorer_id"] == PID and e["assist_id"] and not e["assist_type"].startswith("Penalty"):
            for b, nm in MATE_NAME.items():
                if e["assist_player"] == nm and b in OTHERS:
                    d = ldate(G[gid]); oe, om = OTHERS[b]
                    if not any(x[0] == "a" and x[9] == d and "Olise" in str(x[13]) for x in oe):
                        cross.append(("TM 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"], "출전 행 있음" if any(m[0] == d for m in om) else "출전 행 없음"))
DUP = set(); cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 합계
CLUBS = [("2021-07-08", "레딩"), ("2024-07-07", "크리스털 팰리스"), ("9999-12-31", "바이에른 뮌헨")]
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
KO_OPP = {"1.FC Union Berlin": "우니온 베를린", "Borussia Mönchengladbach": "묀헨글라트바흐", "TSG 1899 Hoffenheim": "호펜하임",
          "VfL Wolfsburg": "볼프스부르크", "Chelsea FC": "첼시", "Harry Kane": "케인", "Moritz Jenz": "옌츠", "Trevoh Chalobah": "찰로바",
          "Diogo Leite": "디오구 레이트"}
def ko_(s): return KO_OPP.get(s, s)
def jl(reason): return ", ".join(f"{d_(j[1])} {ko_(j[2])}전 {j[3]}분 {ko_(j[4])}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
SKIP = [j for j in judg if j[0] == "단일 출처 도움 뺌"]
ADDS = [j for j in judg if j[0] == "단일 출처 도움 넣음"]
first, last = M[0], M[-1]
ET_GAMES = [m for m in M if m[3] > 90]
SHOTR = "슈팅 굴절·리바운드('Shot on goal')"

NOTE_LINES = [
    f"마이클 올리세(레딩·크리스털 팰리스·바이에른 뮌헨)의 클럽 공식 경기 {NG}경기({d_(first[0])} 리즈 유나이티드전 ~ {d_(last[0])} 마인츠전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기 제외",
    f"클럽별 경기·골·도움: 레딩 {c3(ST['레딩'])}, 크리스털 팰리스 {c3(ST['크리스털 팰리스'])}, 바이에른 뮌헨 {c3(ST['바이에른 뮌헨'])}. 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(90분 추정 없음), 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부), FotMob 경기 기록과 대조. 경기 수·골 수는 영어·프랑스어 위키백과 클럽별·시즌별 합계와 같음(285경기 77골; 프랑스어 위키백과 시즌별 도움도 Transfermarkt와 같음). 영어 위키백과 통산 줄(76골)은 자체 클럽 합계(77골)와 맞지 않는 표기 오류",
    "레딩 U-18·U-23(프리미어리그 2·인터내셔널컵)과 크리스털 팰리스 U-23 경기, 프랑스 대표팀(A·올림픽·U-21) 경기는 뺌. 레딩 성인 팀 첫 경기는 2019.3.12 챔피언십 리즈전",
    "레딩의 리그컵 2경기(2019.8.27 플리머스전 64분, 2020.9.5 콜체스터전 90분)는 FotMob 선수 경기 목록에 없지만 FotMob 경기 라인업과 Transfermarkt에 있어 넣음(골·도움 없음)",
    "골: 77골 모두 Transfermarkt와 FotMob이 같은 경기·같은 순서. 분이 1분 다른 골은 Transfermarkt를 씀(2021.4.5 더비전 45+2분(FotMob 45+1), 2025.2.23 프랑크푸르트전 45+2분(FotMob 45+3), 2025.10.18 도르트문트전 78분(FotMob 79), 2026.10.28 마그데부르크전 50분 PK(FotMob 51)). 올리세 자책골 없음",
    "도움은 Transfermarkt와 FotMob 경기 이벤트가 같이 적은 것을 기준으로 하고, 한쪽에만 있는 것은 다른 출처 2곳이 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 도움 {TM_A_API}개 − PK 유도 {EX['PK 유도']}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 − 슈팅 굴절 {EX[SHOTR]}개 − 확인 못 한 단일 출처 {len(SKIP)}개",
    "PK 유도로 뺀 도움(모두 케인 PK 골, FotMob도 도움 없음): " + jl("PK 유도"),
    "상대 자책골에 붙은 도움으로 뺀 것(FotMob도 도움 없음): " + jl("상대 자책골 유도"),
    "슈팅 굴절로 뺀 것: " + jl(SHOTR) + " 헤더 골(Transfermarkt 유형 'Shot on goal', 로이터 기사상 올리세의 슈팅을 케인이 머리로 살짝 방향만 바꾼 골. FotMob은 올리세 도움으로 적었지만 엄격 기준으로 뺌)",
    "FotMob 경기 이벤트에는 도움자가 없지만 다른 출처 2곳으로 확인해 넣은 도움: " + "; ".join(j[5] for j in ADDS),
    ("확인하지 못해 뺀 단일 출처 도움: " + "; ".join(j[5] for j in SKIP)) if SKIP else "확인하지 못해 뺀 단일 출처 도움: 없음",
    "2026.5.23 DFB-포칼 결승 슈투트가르트전 55분 케인 골은 FotMob 선수 경기 목록에 도움 0이지만 FotMob 경기 이벤트·Transfermarkt 모두 올리세 도움이라 넣음. 2025.6.29 클럽 월드컵 플라멩구전 54분 조르지뉴 PK는 Transfermarkt 리포트 도움 칸에 올리세의 핸드볼 반칙이 적힌 것으로 도움이 아님",
    "출전 분은 Transfermarkt 그대로(FotMob과 1~2분 차이 18경기). 연장 경기는 2020.3.3 FA컵 5라운드 셰필드 유나이티드전(1-2 연장 패, 98분 출전) 하나이고 연장 시간의 골·도움은 없음. 2022.11.9 리그컵 3라운드 뉴캐슬전은 0-0 뒤 연장 없이 승부차기(78분 교체)",
    "날짜는 경기 현지 날짜(잉글랜드·독일 경기는 Transfermarkt와 같음). 2025 클럽 월드컵(미국)은 경기장 현지 시간(동부): 2025.6.20 보카 주니어스전(마이애미 21시, Transfermarkt 리포트 6.21)",
    "상대 Elo는 같은 경기를 다룬 다른 선수 자료(케인·무시알라·그나브리·뮐러·자네·디아스·코망 등)의 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 순위 순으로 씀. 순위로 새로 정한 상대: " + ", ".join(f"{o} {s} '{v[1]}'" for (o, s), v in sorted(NEW_TS.items(), key=lambda t: (t[0][1], t[0][0]))),
    "잉글랜드 3부 리그 원 2019-20은 시즌 중단 뒤 경기당 승점으로 정한 최종 순위(23팀, 베리 제명), 2. 분데스리가 2026-27은 진행 중 시즌이라 2026년 11월 중순 순위",
    "대회 비중: FA컵·리그컵·DFB-포칼은 국내컵(16강까지 낮은 비중, 8강부터 높은 비중·준결승·결승), DFL 슈퍼컵(프란츠 베켄바워 슈퍼컵)은 국내컵 결승 비중, 챔스 2024-25부터 리그 단계는 조별과 같은 비중·녹아웃 플레이오프는 16강과 같은 비중, 클럽 월드컵 2025 조별은 리그식(무승부 1점)·16강부터 단판. FA컵 3라운드 재경기(2020.1.14 블랙풀전)는 단판",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(챔스 2024-25·2025-26 녹아웃: 원정 다득점 없이 연장). 다른 차전 스코어는 Transfermarkt 리포트",
    "시즌 구분: 레딩·크리스털 팰리스는 8월 1일 기준(2020.6~7월 재개 경기는 2019-20), 바이에른은 7월 10일 기준(2025.6~7월 클럽 월드컵은 2024-25). 클럽 구분 2021.7.8 크리스털 팰리스, 2024.7.7 바이에른 뮌헨(Transfermarkt 이적일)",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준(리그 24/25·25/26, DFB-포칼 25/26, 슈퍼컵 25/26·26/27, 도움왕 24/25). 리그 올해의 선수·올해의 팀은 분데스리가 사무국(2025-26 올해의 선수, 2024-25·2025-26 올해의 팀)과 VDV(2025-26 시즌 선수, 2024-25·2025-26 시즌 팀) 발표. 챔피언십 PFA 올해의 팀 2020-21·신인상·구단 상·대표팀 기록(올림픽 은메달)은 표 항목 밖이라 뺌",
    f"{d_(CUTOFF)} 기준: 마지막 출전은 {d_(last[0])} 분데스리가 마인츠전(90분). 그 뒤 프랑스 대표팀 경기만 있음",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "cwc", "clg", "cl16", "clk", "df"]:
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
if MISS:
    for x in MISS: print("상대 Elo 없음:", x)
    sys.exit(1)
open(OUT_JS, "w", encoding="utf-8").write(f"const OLI_E={J(E)};\nconst OLI_M={J(M)};\nconst OLI_NOTE={J(NOTE)};\n")
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
    if not (c[0].startswith(("동료", "올리세")) and c[4] == "일치"): print("  대조:", c)
print("일치 대조", sum(1 for c in cross if len(c) > 4 and c[4] == "일치"))
print("새 팀-시즌", NEW_TS)
print("통합표 라벨 재계산 차이", TABLE_DIFF)
for j in judg: print("  판정:", j)
