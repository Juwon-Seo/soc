#!/usr/bin/env python3
"""Bryan Mbeumo: raw/ -> mbeumo.json + mbe.js (판정 근거는 judgments.md)

  python3 players/mbeumo/build_mbeumo.py [출력 data 폴더]  (기본: players/mbeumo/ — 오케스트레이터가 src/data로 옮김)
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
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else HERE
OUT_JS = os.path.join(DATA_DIR, "mbe.js")
OUT_JSON = os.path.join(HERE, "mbeumo.json")
PID = "413039"
CUTOFF = "2026-11-20"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 도움 판정
# Transfermarkt 도움 중 FotMob 경기 이벤트에 음뵈모 도움이 없는 것(유형으로 빼는 PK 유도·상대 자책골 제외): gameId|분 -> (넣음 여부, 근거)
SINGLE = {
    "3447598|40": (1, "2020.9.16 리그컵 2라운드 사우샘프턴전 40분 뇌르고르 헤더 골(음뵈모 코너킥): ESPN 경기 기록(‘Assisted by Bryan Mbeumo with a cross following a corner’)·브렌트퍼드 구단 경기 기사(‘Mbeumo stood it up towards the far post … Nørgaard … powered a header home’)·스카이 스포츠 경기 기사(‘from Mbeumo's 40th-minute corner’). FotMob 경기 이벤트는 이 골에 도움자 칸이 비어 있음"),
    "3074498|45+1": (0, "2018.8.14 쿠프 드 라 리그 1라운드 케비이 루앙전 45+1분 라벨로손 골: ESPN 경기 기록·Tendance Ouest 경기 기사·Foot Mercato 경기 페이지 어디에도 도움자가 없어 확인 못 함"),
    "4362860|70": (0, "2025.5.4 맨체스터 유나이티드전 70분 샤데 헤더 골: 프리미어리그 공식 경기 기사는 ‘음뵈모의 슈팅 시도가 굴절돼 샤데 앞으로 흘렀다’(슈팅 굴절)고 적었고 the42·모닝스타는 크로스로 적어 출처가 갈림. FotMob·ESPN도 도움자 없음 → 엄격 기준(슈팅 굴절은 도움 아님)으로 뺌"),
}
SHOT_KEEP = {}
# Transfermarkt 리포트(HTML)의 골 뒤 스코어 표시 오류: Transfermarkt JSON·FotMob 값으로 고침
SCORE_FIX = {("4362839", "45+3"): "1-1", ("4362839", "48"): "2-1"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"GB1", "GB2", "FR1", "FR2", "POCC", "FRR1"}   # 승격 플레이오프(챔피언십·리그2)는 리그 비중(애슐리 영 선례)

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
    if cid in ("FAC", "CGB", "FRL", "FRC"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in ("POCC", "FRR1"): return 1          # 플레이오프 결승·리그2 플레이오프 2라운드는 단판
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
    if cid == "POCC": return (0, 1)                 # EFL 플레이오프 준결승: 원정 다득점 없음, 연장(애슐리 영 선례)
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
        if f["mbeumo_assist"] == "1":
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
    if b not in TRACKED or b in ("hon.js", "mbe.js", "clubcolors.js", "finals.js"): continue
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
    if "2020-06-01" <= d <= "2020-08-31": return "2019-20"     # 코로나 재개 경기(챔피언십 2020.6~8)는 2019-20
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1   # 7월 리그 경기(리그2 2019.7.26)는 새 시즌
    return f"{s}-{str(s + 1)[2:]}"

# 순위 확인(judgments.md): 리그2 2018-19(TM 표 = 영어 위키백과 승점·득실 계산과 같은 순서), 내셔널 2018-19(TM 표는 케비이 루앙 10위지만
# 영어 위키백과 최종 순위는 9위(아브랑슈 8위, 포 9→10위: 포 승점 1 삭감 반영) → 9위/18팀), 챔피언십 2019-20·2020-21, 리그 투 2021-22·2025-26(위키백과 최종 순위로 그림즈비 7위),
# 프리미어리그 2026-27은 진행 중 시즌(2026.11.20 TM 표; 같은 표의 다른 팀 순위는 기존 자료 라벨과 모두 같음)
RANK_FIX = {("FR3", "2018-19", "Quevilly Rouen Métropole"): 9}
# 리그2 2019-20(코로나로 중단, 경기당 승점 최종 순위 — 영어 위키백과 2019–20 Ligue 2 표): 니오르 18위/20팀. 수집 순위표에 없어 추가
RANKS["FR2", "2019-20"][key("Chamois Niortais FC")] = (18, 20, "Chamois Niortais FC")
def make_label(lg, s, r, n):
    if lg == "GB1":
        if s == "2026-27": return f"프리미어리그 {s} {r}위/{n}팀 (2026년 11월 중순 현재 순위)"
        return f"프리미어리그 {s} {r}위" + ("" if n == 20 else f"/{n}팀")
    if lg == "GB2": return f"챔피언십 {s} {r}위/{n}팀"
    if lg == "GB4": return f"잉글랜드 4부 {s} {r}위/{n}팀 (EFL League Two, 리그 수준 추정)"
    if lg == "FR2": return f"리그2 {s} {r}위/{n}팀"
    if lg == "FR3": return f"프랑스 3부 {s} {r}위/{n}팀 (Championnat National, 리그 수준 추정)"
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
    if v[0] == "rank": chk[(key(o), eu(d))].add(v[1])
for k_, v in chk.items():
    if len(v) > 1: sys.exit(f"같은 팀-시즌 값 여럿 {k_} {v}")

# ---------------------------------------------------------------- 동료·같은 경기 대조(보고용)
MATE_NAME = {"brf.js": "Bruno Fernandes", "eri.js": "Christian Eriksen"}
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and re.search(r"Bryan Mbeumo", str(x[13])):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (x[5], x[6], x[2], x[12], x[3])
            cross.append(("동료 도움→음뵈모 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "음뵈모 골 없음"), x[2:7], hit[0][2:7] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and r[13] == nm:
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (r[5], r[6], r[2], r[12], r[3])
                cross.append(("음뵈모 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else "동료 골 없음"), r[2:7], hit[0][2:7] if hit else None))
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
                    if not any(x[0] == "a" and x[9] == d and "Mbeumo" in str(x[13]) for x in oe):
                        cross.append(("TM 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"], "출전 행 있음" if any(m[0] == d for m in om) else "출전 행 없음"))
DUP = set(); cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 합계
CLUBS = [("2019-08-05", "트루아"), ("2025-07-21", "브렌트퍼드"), ("9999-12-31", "맨체스터 유나이티드")]
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
KO_OPP = {"Derby County": "더비 카운티", "Swansea City": "스완지", "West Ham United": "웨스트햄", "Ivan Toney": "토니", "Konstantinos Mavropanos": "마브로파노스"}
def ko_(s): return KO_OPP.get(s, s)
def jl(reason): return ", ".join(f"{d_(j[1])} {ko_(j[2])}전 {j[3]}분 {ko_(j[4])}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
SKIP = [j for j in judg if j[0] == "단일 출처 도움 뺌"]
ADDS = [j for j in judg if j[0] == "단일 출처 도움 넣음"]
first, last = M[0], M[-1]
ET_GAMES = [m for m in M if m[3] > 90]
SHOTR = "슈팅 굴절·리바운드('Shot on goal')"

NOTE_LINES = [
    f"브라이언 음뵈모(트루아·브렌트퍼드·맨체스터 유나이티드)의 클럽 공식 경기 {NG}경기({d_(first[0])} 메스전 ~ {d_(last[0])} 애스턴 빌라전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기 제외",
    f"클럽별 경기·골·도움: 트루아 {c3(ST['트루아'])}, 브렌트퍼드 {c3(ST['브렌트퍼드'])}, 맨체스터 유나이티드 {c3(ST['맨체스터 유나이티드'])}. 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(90분 추정 없음), 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부, Transfermarkt 경기 자료(JSON)와 대조), FotMob 경기 기록과 대조. 경기 수·골 수는 영어·프랑스어 위키백과 클럽별·시즌별 합계와 같음(337경기 98골; 프랑스어 위키백과 시즌별 도움 59개도 Transfermarkt와 같음). 영어 위키백과 통산 줄(370경기 112골)은 트루아 2군 33경기 14골을 더한 값",
    "트루아 2군(2016-17 CFA 2, 2017-18 National 3: 프랑스 5부 아마추어 리그, 33경기 14골)과 U-19(쿠프 감바르델라 2017-18 우승, 4경기 3골), 카메룬·프랑스 연령별 대표 경기는 뺌. 트루아 성인 팀 첫 경기는 2018.2.17 리그1 메스전",
    "트루아의 리그컵 3경기·쿠프 드 프랑스 1경기와 브렌트퍼드의 리그컵 2경기(2019.8.13 케임브리지전, 2020.9.16 사우샘프턴전)는 FotMob 선수 경기 목록에 없지만 FotMob 대회 일정·경기 기록과 Transfermarkt에 있어 넣음",
    "골: 98골 모두 Transfermarkt와 FotMob이 같은 경기·같은 순서. 분이 다른 골은 Transfermarkt를 씀(2018.10.5 샤토루전 9분(FotMob 8), 2020.9.19 허더즈필드전 90+1분(FotMob 90), 2021.12.10 왓퍼드전 90+6분(FotMob 90+5), 2022.1.8 FA컵 포트 베일전 66분(FotMob 65)). 음뵈모 자책골 없음",
    "2025.4.19 브라이턴전 Transfermarkt 리포트 화면의 골 뒤 스코어(45+3분 웰벡 2:1, 48분 음뵈모 2:0)는 불가능한 순서라 Transfermarkt 경기 자료·FotMob 값(1-1, 2-1)을 씀",
    "도움은 Transfermarkt와 FotMob 경기 이벤트가 같이 적은 것을 기준으로 하고, 한쪽에만 있는 것은 다른 출처 2곳이 확인한 것만 넣음. FotMob에만 있는 도움은 없음",
    f"도움 {NA}개 = Transfermarkt 도움 {TM_A_API}개 − PK 유도 {EX['PK 유도']}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 − 확인 못 하거나 슈팅 굴절인 단일 출처 {len(SKIP)}개",
    "PK 유도로 뺀 도움(모두 토니 PK 골, FotMob도 도움 없음): " + jl("PK 유도"),
    "상대 자책골에 붙은 도움으로 뺀 것(FotMob은 자책골, 도움 없음): " + jl("상대 자책골 유도"),
    "FotMob 경기 이벤트에는 도움자가 없지만 다른 출처로 확인해 넣은 도움: " + "; ".join(j[5] for j in ADDS),
    "확인하지 못했거나 슈팅 굴절이라 뺀 단일 출처 도움: " + "; ".join(j[5] for j in SKIP),
    "음뵈모의 PK 골 가운데 Transfermarkt가 동료를 PK 유도자로 적은 9개(2021.12.10 왓퍼드전 고도스 등)는 음뵈모 골로만 셈",
    "출전 분은 Transfermarkt 그대로(FotMob과 1~2분 차이 21경기). 연장 경기는 2019.5.24 리그2 플레이오프 랑스전(1-2 연장 패, 106분 출전)과 2020.8.4 챔피언십 플레이오프 결승 풀럼전(1-2 연장 패, 61분 교체) 둘이고 연장 시간의 골·도움은 없음. 리그컵 승부차기 5경기(2019 케임브리지, 2022 길링엄, 2023 뉴포트, 2024 셰필드 웬즈데이, 2025 그림즈비)는 연장 없이 90분 뒤 바로 승부차기라 Transfermarkt 최종 스코어의 승부차기 골은 셈하지 않음",
    "날짜는 경기 현지 날짜(프랑스·잉글랜드·유럽 경기는 Transfermarkt 일정·리포트 날짜와 같음)",
    "상대 Elo는 같은 경기를 다룬 다른 선수 자료(브루노 페르난데스 등)의 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 순위 순으로 씀. 순위로 새로 정한 상대: " + ", ".join(f"{o} {s} '{v[1]}'" for (o, s), v in sorted(NEW_TS.items(), key=lambda t: (t[0][1], t[0][0]))),
    "순위 확인: 내셔널(프랑스 3부) 2018-19 케비이 루앙은 Transfermarkt 표에서 10위지만 영어 위키백과 최종 순위(승점 같은 아브랑슈가 상대 전적으로 앞, 포는 승점 1 삭감으로 아래)로 9위. 리그2 2019-20은 코로나로 중단된 뒤 경기당 승점으로 정한 최종 순위(니오르 18위). 리그 투 2025-26 그림즈비 7위는 영어 위키백과 최종 순위. 프리미어리그 2026-27은 진행 중 시즌이라 2026년 11월 중순 순위",
    "대회 비중: 챔피언십 승격 플레이오프(2020·2021)와 리그2 플레이오프(2019 랑스전)는 리그 비중. 플레이오프 준결승은 두 경기 합산(원정 다득점 없이 연장), 결승·리그2 플레이오프는 단판. FA컵·리그컵·쿠프 드 프랑스·쿠프 드 라 리그는 국내컵(16강까지 낮은 비중, 8강부터 높은 비중·준결승), 2020-21 리그컵 준결승(토트넘)은 단판. 챔스 2026-27 리그 단계는 조별과 같은 비중",
    f"두 경기 합산 기록 {NTIE}개: 2020.7.29 챔피언십 플레이오프 준결승 2차전 스완지전 46분 골(1차전 0-1 패, 합산 S로 계산)",
    "시즌 구분: 트루아는 7월 1일 기준(리그2가 7월 말 개막: 2019.7.26 니오르전은 2019-20), 브렌트퍼드·맨체스터 유나이티드는 8월 1일 기준(2020.6~8월 챔피언십 재개 경기·플레이오프는 2019-20). 클럽 구분 2019.8.5 브렌트퍼드, 2025.7.21 맨체스터 유나이티드(Transfermarkt 이적일)",
    "우승·수상: Transfermarkt 업적 페이지에 성인 클럽 우승·개인 수상 없음(쿠프 감바르델라는 유소년 대회). 2021 챔피언십 플레이오프 우승(승격)은 리그 우승이 아니라 넣지 않음. 프리미어리그 이달의 선수(2025년 10월)·팬 투표 올해의 팀 2024-25는 표 항목 밖. PFA 올해의 팀(프리미어리그) 선정 없음",
    f"{d_(CUTOFF)} 기준: 마지막 출전은 {d_(last[0])} 프리미어리그 애스턴 빌라전(4-4, 83분). 그 뒤 카메룬 대표팀 경기만 있음",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "cwc", "clg", "cl16", "clk", "df", "lg"]:
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
open(OUT_JS, "w", encoding="utf-8").write(f"const MBE_E={J(E)};\nconst MBE_M={J(M)};\nconst MBE_NOTE={J(NOTE)};\n")
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
    if not (c[0].startswith(("동료", "음뵈모")) and c[4] == "일치"): print("  대조:", c)
print("일치 대조", sum(1 for c in cross if len(c) > 4 and c[4] == "일치"))
print("새 팀-시즌", NEW_TS)
print("통합표 라벨 재계산 차이", TABLE_DIFF)
for j in judg: print("  판정:", j)
