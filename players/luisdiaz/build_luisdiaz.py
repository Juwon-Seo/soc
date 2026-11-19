#!/usr/bin/env python3
"""Luis Díaz: raw/ -> luisdiaz.json + src/data/ldz.js (판정 근거는 judgments.md)

  python3 players/luisdiaz/build_luisdiaz.py [출력 data 폴더]

입력: raw/tm_games.csv(출전·분), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(도움 대조), raw/ranks.txt(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값), src/data/*.js(같은 경기 동료 자료 대조).
콜롬비아 리그 순위는 스페인어 위키백과 대회 문서(Torneo Apertura/Finalización 2018, Apertura 2019, Primera B 2016·2017)의
정규 단계 순위표로 확인한 값을 아래 COL_RANK 에 적음(FotMob 표와 같음).
"""
import csv, json, os, re, sys, unicodedata, collections, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "src", "data")
OUT_JS = os.path.join(DATA_DIR, "ldz.js")
OUT_JSON = os.path.join(HERE, "luisdiaz.json")
PID = "480692"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 도움 판정
# Transfermarkt 도움 중 FotMob 경기 이벤트에 없는 것: gameId|분 -> (넣음 여부, 근거)
SINGLE = {
    "3004223|81": (0, "2018.2.15 리베르타도레스 과라니전 81분 차라 골: El Heraldo(Rincón Juniorista) 한 곳만 디아스 패스로 서술"),
    "3012639|83": (1, "2018.4.19 리베르타도레스 알리안사 리마전 83분 알베스 골: futbolperuano.com 기사(디아스 패스 뒤 골)·footballcritic 경기 기록(도움 L. Díaz)"),
    "3046873|12": (0, "2018.4.11 산타페전 12분 테오 구티에레스 골: 금지 출처 외에 도움자를 적은 기사 없음"),
    "3107359|34": (1, "2018.9.22 라 에키다드전 34분 요니 곤살레스 골: La FM·Win Sports 기사(디아스 도움)"),
    "3114408|58": (0, "2018.10.9 톨리마전 58분 바레라 골: ESPN 문자중계(Opta 계열) 한 곳만 디아스 도움"),
    "3114408|83": (0, "2018.10.9 톨리마전 83분 테오 구티에레스 골: ESPN 문자중계 한 곳만 디아스 도움"),
    "3121854|48": (1, "2018.11.8 수다메리카나 4강 1차전 산타페전 48분 피에드라이타 골: ESPN 문자중계(코너킥 뒤 디아스 도움)·fussballtransfers 경기 기록"),
    "3148303|43": (0, "2019.1.30 파트리오타스전 43분 피에드라이타 골: 금지 출처(worldfootball) 외 확인 없음"),
    "3153135|23": (0, "2019.2.10 아메리카 데 칼리전 23분 삼부에사 골: ESPN은 여러 선수의 연결 플레이로만 서술, 도움자 명시는 금지 출처뿐"),
    "3919565|74": (0, "2017.4.30 야네로스전 74분 스카르페타 골(코너킥): FotMob 기록 없음, 기사 확인 못 함"),
    "3269584|8": (0, "2019.10.19 타사 코임브로이스전 8분 치키뉴 소아레스 골: Bola na Rede 한 곳만 디아스 패스로 서술"),
    "3703885|31": (1, "2021.12.23 타사 벤피카전 31분 에바닐송 골: Record 문자중계·La FM 기사(디아스가 에바닐송에게 내줌)"),
    "3729278|68": (1, "2022.2.6 FA컵 카디프전 68분 미나미노 골: This Is Anfield·리버풀 구단 기사(디아스 도움, FotMob은 조타 도움으로 적음)"),
    "3621411|90+6": (1, "2021.10.30 보아비스타전 90+6분 나마소 골: FotMob 선수 경기 목록 도움 1(경기 이벤트엔 도움자 없음)"),
}
# 'Shot on goal'이지만 넣는 것(골키퍼·골대 리바운드가 아님)
SHOT_KEEP = {"3592264|85": "2022.4.24 에버턴전 85분 오리기 골: 디아스의 오버헤드킥이 튀어 오른 공을 오리기가 머리로 넣음(골키퍼·골대 리바운드 아님), FotMob 경기 이벤트·선수 경기 목록도 디아스 도움"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"CO2T", "COLP", "COL1", "PO1", "GB1", "L1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid in ("COLF", "COLO"):            # 콜롬비아 리그 결선: 4팀 리그 = 리그, 녹아웃 = 리길야와 같은 플레이오프 비중
        if r.startswith("group"): return "lg"
        if r.startswith("quarter"): return "mlp"
        if r.startswith("semi"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"                       # 예선·조별·16강
    if cid == "CS":
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid in ("POSU", "GBCS", "DFL", "COSP"): return "df"
    if cid in ("POPO", "POCP", "FAC", "CGB", "DFB", "COPO"):
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
games = rd("tm_games.csv")
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
PM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

def ldate(g): return g["date_local"]
# 같은 이름 꼴의 다른 팀과 섞이지 않게 바꾼 표기(아틀레티코 FC = 칼리의 2부 팀, 아틀레티코 마드리드와 다름)
OPP_NAME = {"Atlético FC": "Atlético FC Cali"}
for g in games: g["opponent"] = OPP_NAME.get(g["opponent"].strip(), g["opponent"].strip())

M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    if cid in ("CL", "CLQ", "EL"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid in ("CLI", "CS"): return (1, 0)         # 2017~2018 남미 대회(결승 제외): 원정 다득점, 연장 없이 승부차기
    if cid in ("COLO", "COLF", "COSP"): return (0, 0)   # 콜롬비아 리그 결선·슈페르리가: 합계 동률이면 바로 승부차기
    if cid == "CGB": return (0, 0)                 # 잉글랜드 리그컵 준결승 2018-19부터
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    m = MI[gid]; s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    oh, oa = map(int, m["other_leg_score"].split(":"))
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
    if e["scorer_id"] == PID: return "본인 골"
    if e["own_goal"] == "1": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

def fm_has_assist(gid, mi):
    for f in FME[gid]:
        if f["diaz_assist"] == "1":
            t = int(f["time"]) + int(f["overloadTime"] or 0)
            if abs(t - mi) <= 2: return True
    return False

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == PID and e["own_goal"] != "1"
        is_a = e["assist_id"] == PID
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        tag = f"{gid}|{e['minute']}"
        mi, dm = mins(e["minute"])
        d = ldate(g)
        if is_a:
            why = assist_reason(e)
            if why and tag in SHOT_KEEP: why = None; judg.append(("도움 넣음(Shot on goal)", d, g["opponent"], e["minute"], e["scorer"], SHOT_KEEP[tag]))
            if why:
                judg.append(("도움 제외", d, g["opponent"], e["minute"], e["scorer"], why))
            elif fm_has_assist(gid, mi) or tag in SHOT_KEEP:
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
            elif tag in SINGLE:
                ok, src = SINGLE[tag]
                judg.append(("단일 출처 도움 " + ("넣음" if ok else "뺌"), d, g["opponent"], e["minute"], e["scorer"], src))
                if ok: raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
            else:
                sys.exit("FotMob에 없는 도움 판정 누락: " + tag + " " + d + " " + g["opponent"])
        if is_g:
            if e["side"] != ("home" if side == "h" else "away"): sys.exit("득점 편 이상 " + tag)
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

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24

# 포르투갈 1부 18팀: 기존 선수 자료의 순위값(2017-18~2025-26 공통)
PT18 = {1: 1912, 2: 1795, 3: 1730, 4: 1690, 5: 1670, 6: 1652, 7: 1627, 8: 1600, 9: 1576, 10: 1560,
        11: 1546, 12: 1533, 13: 1527, 14: 1507, 15: 1482, 16: 1461, 17: 1448, 18: 1421}

# 콜롬비아 순위(스페인어 위키백과 대회 문서의 정규 단계 순위표, FotMob 표와 같음): (팀, 연도) -> (대회, 순위, 팀 수, 등급)
COL_RANK = {
    ("Atlético Bucaramanga", "2018"): ("아페르투라", 16, 20, 1),
    ("Once Caldas", "2018"): ("아페르투라", 8, 20, 1),
    ("Asociación Deportivo Pasto", "2018"): ("피날리사시온", 18, 20, 1),
    ("Envigado FC", "2018"): ("피날리사시온", 13, 20, 1),
    ("Club Deportivo Atlético Huila", "2018"): ("피날리사시온", 17, 20, 1),
    ("Independiente Medellín", "2018"): ("피날리사시온", 5, 20, 1),
    ("CD La Equidad", "2018"): ("피날리사시온", 3, 20, 1),
    ("Rionegro Águilas", "2018"): ("피날리사시온", 7, 20, 1),
    ("Deportes Tolima", "2018"): ("피날리사시온", 1, 20, 1),
    ("Independiente Medellín", "2019"): ("아페르투라", 9, 20, 1),
    ("Independiente Santa Fe", "2019"): ("아페르투라", 20, 20, 1),
    ("Deportes Tolima", "2019"): ("아페르투라", 3, 20, 1),
    ("Boyacá Patriotas FC", "2019"): ("아페르투라", 12, 20, 1),
    ("CD América de Cali", "2019"): ("아페르투라", 4, 20, 1),
    ("Cúcuta Deportivo", "2016"): ("", 10, 16, 2),
    ("Universitario Popayán", "2016"): ("", 5, 16, 2),
    ("Atlético FC Cali", "2017"): ("아페르투라", 16, 16, 2),
    ("Llaneros FC", "2017"): ("아페르투라", 4, 16, 2),
}
COL2_MEAN = 1580 - 228     # 콜롬비아 2부: 1부 평균 − (잉글랜드 1부−2부 평균 차), 아르헨티나 2부·포르투갈 2부 선례

# 아르헨티나 1부 2018-19(26팀, 영어 위키백과 최종 순위표·FotMob 같음)
ARG_RANK = {("CA Lanús", "2018-19"): (11, 26), ("Defensa y Justicia", "2018-19"): (2, 26)}

# 순위표(TM)+기존 리그 순위값: 에레디비시 3위 1677·챔피언십 18위 1572는 다른 시즌 기존 값과 같음. 바이킹은 노르웨이 달력 시즌 2026 기존 값
FIXED = {
    ("Feyenoord Rotterdam", "2019-20"): (1677, "에레디비시 2019-20 3위"),
    ("Cardiff City", "2021-22"): (1572, "챔피언십 2021-22 18위"),
    ("Viking FK", "2026-27"): (1550, "노르웨이 (추정)"),
}
# 직접 추정(모두 '추정')
MAN = {
    ("Club Cerro Porteño", "2017"): (1500, "파라과이 1부 2017 클라우수라 1위 (추정, 다른 선수 자료 세로 포르테뇨·파라과이 상위 팀 1500과 같음)"),
    ("Club Alianza Lima", "2018"): (1400, "페루 1부 2018 상위 팀 (추정, 2017 우승 팀, 다른 선수 자료 페루 상위 팀 1400과 같음)"),
    ("Club Guaraní", "2018"): (1450, "파라과이 1부 2018 아페르투라 8위/12팀 (추정, 다른 선수 자료 과라니 1450과 같음)"),
}

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or "FotMob" in p[0]: continue
        nm = re.sub(r"\s*\(TM .*\)$", "", p[4])
        RANKS[(p[0], p[1])][key(nm)] = (int(p[2]), int(p[3]), nm)

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

SOUTH = {"CO2T", "COLP", "COL1", "COLO", "COLF", "COSP", "COPO", "CLI", "CS"}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(opp, d, cid):
    k = key(opp); y = d[:4]
    south = cid in SOUTH
    seasons = [y] if south else [eu(d)]
    if south and (opp, eu(d)) in {(a, s) for a, s in ARG_RANK}: seasons = [eu(d)]
    for s in seasons:
        if (k, s) in TABLE:
            e, lv = TABLE[(k, s)]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(opp, s)] = ("table", e, lv); return e, lv
    s = seasons[0]
    if (opp, s) in COL_RANK:
        t, r, n, tier = COL_RANK[(opp, s)]
        if tier == 1:
            e = round(1580 + 63 * curve(r, n)); lv = f"콜롬비아 1부 {s} {t} {r}위/{n}팀 (리그 수준 추정)"
        else:
            e = round(COL2_MEAN + SD2 * curve(r, n)); lv = f"콜롬비아 2부 {s} {(t + ' ') if t else ''}{r}위/{n}팀 (추정)"
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(opp, s)] = ("model", e, lv); return e, lv
    if (opp, s) in ARG_RANK:
        r, n = ARG_RANK[(opp, s)]
        e = round(1583 + 63 * curve(r, n)); lv = f"아르헨티나 1부 {s} {r}위"
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(opp, s)] = ("model", e, lv); return e, lv
    if (opp, s) in FIXED:
        e, lv = FIXED[(opp, s)]; ELO_SRC["기존 순위값·같은 팀 값"] += 1; ELO_LOG[(opp, s)] = ("fixed", e, lv); return e, lv
    if (opp, s) in MAN:
        e, lv = MAN[(opp, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(opp, s)] = ("man", e, lv); return e, lv
    sid = s[:4]
    for code in ("PO1", "PO2", "CPSB"):
        tab = RANKS.get((code, s), {})
        if k in tab:
            r, n, _ = tab[k]
            if code == "PO1": e, lv = PT18[r], f"포르투갈 1부 {s} {r}위"
            elif code == "PO2": e, lv = round(1367 + SD2 * curve(r, n)), f"포르투갈 2부 {s} {r}위 (추정)"
            else: e, lv = 1250, f"포르투갈 3부 {s} B조 {r}위 (추정, 다른 선수 자료 포르투갈 3부 값과 같음)"
            ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(opp, s)] = ("model", e, lv); return e, lv
    MISS.append((opp, d, cid, s)); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(g["opponent"].strip(), d, cid)
    et = 1 if (g["gameState"] == "extra_time" and mi > 90 and ko) else 0
    row = [typ, g["opponent"].strip(), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))

# ---------------------------------------------------------------- 동료·같은 경기 대조(보고용)
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
import subprocess
TRACKED = set(os.path.basename(x) for x in subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b not in TRACKED: continue
    if b in ("hon.js", "ldz.js"): continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)
MATE_NAME = {"sal.js": "Mohamed Salah", "kan.js": "Harry Kane", "gna.js": "Serge Gnabry", "mus.js": "Jamal Musiala"}
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and re.search(r"Luis D[ií]az", str(x[13])):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (x[5], x[6], x[2], x[12], x[3])
            cross.append(("동료 도움→디아스 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "디아스 골 없음"), x[2:7], hit[0][2:7] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and r[13] == nm:
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (r[5], r[6], r[2], r[12], r[3])
                cross.append(("디아스 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else "동료 골 없음"), r[2:7], hit[0][2:7] if hit else None))
    for r in E:
        for x in oe:
            if x[9] == r[9] and key(x[1]) == key(r[1]) and (x[2] != r[2] or x[12] != r[12]):
                cross.append(("같은 경기 Elo/lv 다름", b, r[9], r[1], (x[2], x[12]), (r[2], r[12])))
# TM상 동료 도움인데 동료 파일에 없는 것
for gid, evs in EVS.items():
    if gid not in G: continue
    for e in evs:
        if e["scorer_id"] == PID and e["assist_id"] and not e["assist_type"].startswith("Penalty"):
            for b, nm in MATE_NAME.items():
                if e["assist_player"] == nm:
                    d = ldate(G[gid]); oe, om = OTHERS[b]
                    if not any(x[0] == "a" and x[9] == d and re.search(r"D[ií]az", str(x[13])) for x in oe):
                        cross.append(("TM 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"], "출전 행 있음" if any(m[0] == d for m in om) else "출전 행 없음"))
DUP = set(); cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 합계
CLUBS = [("2017-07-01", "바랑키야"), ("2019-07-10", "주니오르"), ("2022-01-30", "포르투"), ("2025-07-30", "리버풀"), ("9999-12-31", "바이에른 뮌헨")]
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
TM_A_ALL = sum(1 for gid, evs in EVS.items() if gid in G for e in evs if e["assist_id"] == PID)
SHOTR = "슈팅 리바운드('Shot on goal')"
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
def jl(reason): return ", ".join(f"{d_(j[1])} {j[2]} {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
SKIP = [j for j in judg if j[0] == "단일 출처 도움 뺌"]
ADDS = [j for j in judg if j[0] == "단일 출처 도움 넣음"]
MAN_USED = sorted({(o, s) for (o, s), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: (t[1], t[0]))
first, last = M[0], M[-1]

NOTE_LINES = [
    f"루이스 디아스(바랑키야·주니오르·포르투·리버풀·바이에른 뮌헨)의 클럽 공식 경기 {NG}경기({d_(first[0])} 하과레스 데 코르도바전 ~ {d_(last[0])} 아스널전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    f"클럽별 경기·골·도움: 바랑키야 {c3(ST['바랑키야'])}, 주니오르 {c3(ST['주니오르'])}, 포르투 {c3(ST['포르투'])}, 리버풀 {c3(ST['리버풀'])}, 바이에른 뮌헨 {c3(ST['바이에른 뮌헨'])}. 출전 분 합계 {MIN_TOT:,}분",
    "경기·출전 분·골 시간·골 뒤 스코어는 Transfermarkt 선수 경기 성적(API)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음(퇴장 2경기 2017.9.19 세로 포르테뇨전 74분·2021.2.10 브라가전 70분은 퇴장 시각까지)",
    "클럽별·시즌별 경기 수와 골은 영어·스페인어 위키백과 경력 표와 모두 같음(영어 위키백과 통산 줄의 484경기 139골은 자체 클럽 합계 483경기 136골과 다른 표기 오류). FotMob 경력 합계는 포르투 124경기 39골로 1경기 2골 적음",
    "바랑키야 FC(2016~2017)는 콜롬비아 2부 프리메라 B(디마요르 주관 프로 리그) 소속이라 넣음(주니오르와 같은 소유주의 별도 클럽, 위키백과·Transfermarkt 통산에 포함). 이 시기는 FotMob 경기 자료가 없어 Transfermarkt만 근거",
    "콜롬비아 대표팀·U-20 대표팀 경기는 뺌",
    "PK 골은 없음. 2018.9.22 라 에키다드전 골(Transfermarkt 90+1분, FotMob 90분) 등 추가시간 표기는 Transfermarkt를 씀. 2020.1.10 모레이렌스전 골은 Transfermarkt 72분, FotMob 66분이라 Transfermarkt를 씀(골 순서는 같음)",
    "도움은 Transfermarkt와 FotMob 경기 이벤트(또는 FotMob 선수 경기 목록)가 같이 적은 것을 기준으로 함. 콜롬비아 시기와 일부 포르투갈 컵 경기는 FotMob 이벤트에 도움자가 없어 Transfermarkt 단일 출처이므로 다른 출처 2곳이 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 도움 {TM_A_ALL}개 − PK 유도 {EX['PK 유도']}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 − 슈팅 리바운드 {EX[SHOTR]}개 − 확인 못 한 단일 출처 {len(SKIP)}개",
    "PK 유도로 뺀 도움: " + jl("PK 유도"),
    "상대 자책골에 붙은 도움으로 뺀 것: " + jl("상대 자책골 유도"),
    "슈팅 리바운드로 뺀 것: " + jl("슈팅 리바운드('Shot on goal')") + " (FotMob도 도움 없음)",
    "Transfermarkt 유형이 'Shot on goal'이지만 넣은 도움: 2022.4.24 에버턴전 85분 오리기 골(디아스의 오버헤드킥이 튀어 오른 공을 오리기가 머리로 넣은 골로 골키퍼·골대에 맞은 리바운드가 아님, FotMob도 디아스 도움)",
    "다른 출처 2곳으로 확인해 넣은 단일 출처 도움: " + "; ".join(j[5] for j in ADDS),
    "확인하지 못해 뺀 단일 출처 도움: " + "; ".join(j[5] for j in SKIP),
    "2017.4.30 야네로스전 Transfermarkt 리포트는 최종 3-1인데 골 목록에 야네로스의 세 번째 골(90+4분)이 빠져 있음(골·도움 기록에는 영향 없음)",
    "날짜는 경기 현지 날짜. 콜롬비아 클럽 경기는 UTC를 콜롬비아 시간으로 바꿔 Transfermarkt 리포트 날짜(중부 유럽 기준)보다 하루 앞인 경우가 많음",
    "상대 Elo는 기존 선수 자료의 같은 팀·같은 시즌 값을 먼저 쓰고, 없으면 그 시즌 순위를 리그 모형에 넣음. 산타페 2018은 다른 선수 자료 값 1450(추정)을 그대로 씀",
    "콜롬비아 1부는 콰드라도·팔카오 자료와 같은 리그 수준 추정(평균 1580·흩어짐 63, 근거 약함). 순위는 그 대회(2018 아페르투라·피날리사시온, 2019 아페르투라)의 정규 단계 순위(스페인어 위키백과 순위표, FotMob과 같음)이고 결선·코파·슈페르리가 경기도 그 해 대회 순위를 씀",
    "콜롬비아 2부(프리메라 B)는 1부 평균에서 잉글랜드 1·2부 평균 차이를 뺀 약 1352에 2부 흩어짐을 둔 추정(아르헨티나·포르투갈 2부 선례, 근거 약함). 순위는 스페인어 위키백과 2016 정규 단계·2017 아페르투라 순위표",
    "아르헨티나 상대(라누스·데펜사 이 후스티시아 2018)는 2018-19 시즌 최종 순위(26팀)를 아르헨티나 1부 모형에 넣음. 포르투갈 2부(카사 피아·샤베스 2019-20)는 2부 모형(추정), 코임브로이스(3부 캄페오나투 드 포르투갈)는 다른 선수 자료의 포르투갈 3부 값 1250(추정)",
    "리그 표가 없는 남미 상대는 당시 수준을 추정함(모두 '추정'): " + ", ".join(f"{o} {s} {ELO_LOG[(o, s)][1]}" for o, s in MAN_USED),
    "콜롬비아 리그 결선의 4팀 리그(2019 아페르투라 쿠아드랑굴라르)는 리그 경기로, 녹아웃(8강·4강·결승 두 경기)은 멕시코 리길야와 같은 플레이오프 비중으로 계산함. 코파 콜롬비아는 국내컵(조별은 리그식), 슈페르리가는 국내컵 결승과 같은 비중",
    "코파 리베르타도레스 예선·조별은 남미 대회 낮은 단계, 코파 수다메리카나 16강까지는 낮은 단계·8강 이후는 높은 단계로 계산함. 타사 다 리가 조별은 리그식 국내컵, 수페르타사·커뮤니티 실드·DFL 슈퍼컵은 국내컵 결승, 2024-25부터 챔스 리그 단계는 조별과 같은 비중",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회는 2020-21까지 원정 다득점·연장, 2021-22부터 연장만. 2017~2018 남미 대회(결승 제외)는 원정 다득점 있고 연장 없이 승부차기. 콜롬비아 리그 결선·슈페르리가와 잉글랜드 리그컵 준결승은 원정 다득점·연장 없이 승부차기. 다른 차전 스코어는 Transfermarkt 리포트",
    "연장·승부차기 경기의 출전 분은 Transfermarkt 그대로(2018.12.12 수다메리카나 결승 2차전 120분 등). 연장 시간의 골·도움은 없음",
    "시즌은 콜롬비아 클럽은 달력 연도(2017년은 바랑키야·주니오르 합침), 리버풀은 7월 10일 기준(2022.7.30 커뮤니티 실드는 2022-23), 포르투·바이에른은 8월 1일 기준(2020.8.1 타사 결승은 2019-20)",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준(콜롬비아 리그 우승은 실제 대회 연도 2018 피날리사시온·2019 아페르투라로 적음, 코파 아메리카 득점왕은 대표팀 기록이라 뺌). 선수협회 올해의 팀: 2025-26 분데스리가 VDV(FC 바이에른 발표), 2018 콜롬비아 1부 Acolfutpro(El Heraldo)",
    "2026.11.18 기준: 마지막 출전은 2026.10.21 챔스 아스널전(교체 22분). 그 뒤 햄스트링 부상으로 결장 중(FotMob 11월 말 복귀 예상)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "csa", "lib", "mlp"]:
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
open(OUT_JS, "w", encoding="utf-8").write(f"const LDZ_E={J(E)};\nconst LDZ_M={J(M)};\nconst LDZ_NOTE={J(NOTE)};\n")
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg, "cross_check": cross,
           "elo_sources": ELO_SRC, "elo_log": {f"{o}|{s}": v for (o, s), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if not (c[0].startswith(("동료", "디아스")) and c[4] == "일치"): print("  대조:", c)
print("일치 대조", sum(1 for c in cross if len(c) > 4 and c[4] == "일치"))
