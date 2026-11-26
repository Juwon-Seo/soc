#!/usr/bin/env python3
"""Gabriel Batistuta: raw/ -> batistuta.json + src/data/bat.js (판정 근거는 judgments.md)

  python3 players/batistuta/build_batistuta.py            # 파일 쓰기
  python3 players/batistuta/build_batistuta.py --debug    # Elo 출처 목록
  python3 players/batistuta/build_batistuta.py --cross    # 같은 경기 다른 선수 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/ranks.txt(순위표), RSSSF 경기 줄(카타르 2003-04, 보카 1991.6.2),
      <ROOT>/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv·league_*_mean.json, src/data/*.js(동료 대조).
크레스포 build 스크립트를 바탕으로 함. 새 팀-시즌 Elo는 리그 시즌 수준 모형(v1.216~v1.219): 목표 평균 + 흩어짐 × 순위 곡선.
"""
import csv, json, os, re, sys, unicodedata, collections, io, contextlib
from datetime import date as Date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "bat.js")
OUT_JSON = os.path.join(HERE, "batistuta.json")
ME = "가브리엘 바티스투타"
INCLUDE_QATAR = True    # RSSSF 경기 줄(골 시각 있음)로 확인되는 알아라비 2003-04 15경기(judgments.md 1절)
INCLUDE_BOCA_RSSSF = True   # RSSSF 경기 줄 + ESPN 기사(골 시각)로 확인되는 보카 1991.6.2 라싱전

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 판정 표
MIN_FIX = {}
EXCL_G = {}
# 도움 제외: gameId|분 -> 이유 (judgments.md 4절)
EXCL_A = {
    "2211515|60": "슈팅 리바운드(Shot on goal, 미야토비치)",
    "985606|51": "슈팅 리바운드(Shot on goal, 아모로소)",
    "2215523|73": "상대 자책골(칸나바로) 유도 + 슈팅 리바운드(Shot on goal)",
    "2216458|90": "상대 자책골(잔데비아조) 유도",
}
DATE_FIX = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2"}
CUPS = {"CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "SCI": return "df"
    if cid == "ALPL": return "dc"     # 리길야 프레 리베르타도레스(밀리토·카바니 선례), 기록 없음
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "EPP":   # 컵위너스컵: 호나우두·피구·네드베드 선례
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "CLI":
        if r.startswith("group") or r.startswith("last 16"): return "lib"
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
    if cid == "SCSA":
        if r.startswith("last 16"): return "csa"
        return "csak"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(" ")[0].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    if g["competitionId"] in ("CLI", "SCSA", "ALPL"):
        return [leg, home, fu, ft, 0, 0]   # 리베르타도레스 2004년까지: 원정 다득점·연장 없음(리켈메·크레스포 선례)
    return [leg, home, fu, ft, 1, 1]       # UEFA 대회·코파 이탈리아: 원정 다득점·연장

# ---------------------------------------------------------------- 이름 정규화·상대 Elo
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
MANUAL_ALIAS = {"inter milan": "inter", "ac parma": "parma"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

with open(os.path.join(ELO, "ents.json"), encoding="utf-8") as f:
    ENTS = [x for x in json.load(f) if x["p"] != ME]

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))
RANK_FIX = {}

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

# 리그 시즌 수준(v1.216~): 순위 곡선은 tools/league_era_normalize.py의 LC
LC = [2.51, 1.668, 1.189, 0.842, 0.664, 0.555, 0.43, 0.259, 0.079, -0.096, -0.231, -0.321, -0.412, -0.502, -0.531, -0.649, -0.814, -0.999, -1.103, -1.177, -1.378]
def cv(r, n):
    x = (r - 1) / (n - 1) * 20; i = min(19, int(x)); t = x - i
    return LC[i] + (LC[i + 1] - LC[i]) * t
def half_up(x): return int(x + 0.5)
SM = json.load(open(os.path.join(ELO, "league_season_mean.json"), encoding="utf-8"))
S2 = json.load(open(os.path.join(ELO, "league_second_mean.json"), encoding="utf-8"))
WM = json.load(open(os.path.join(ELO, "league_world_mean.json"), encoding="utf-8"))
_ERA = {}
def era_target(lg, y_end):
    """json에 없는 시즌(예: 세리에A 1992-93)은 도구의 목표 공식 그대로"""
    if not _ERA:
        G_ = {"__file__": os.path.join(ROOT, "tools", "league_era_normalize.py"), "__name__": "x"}
        argv = sys.argv; sys.argv = ["x"]
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(open(G_["__file__"], encoding="utf-8").read().rsplit("if '--apply' in sys.argv:", 1)[0], "era", "exec"), G_)
        sys.argv = argv; _ERA["t"] = G_["target"]
    return _ERA["t"](lg, y_end)
def sa_val(season, r, n=18):
    k = f"세리에A|{season}"
    mean = SM["평균"][k] if k in SM["평균"] else era_target("세리에A", int(season[:4]) + 1)
    return half_up(mean + SM["흩어짐"]["세리에A"] * cv(r, n))
def sb_val(season, r, n=22):   # 세리에B 라벨에 팀 수가 없으면 도구는 22팀으로 봄
    return half_up(S2["평균"][f"세리에B|{season}"] + S2["흩어짐"]["세리에A"] * cv(r, n))
def world_val(cc, y, r, n):
    ys = [int(k.split("|")[1]) for k in WM["평균"] if k.split("|")[0] == cc]
    y2 = min(ys, key=lambda t: (abs(t - y), -t))   # 자료 앞 시즌은 가장 가까운 시즌(도구와 같음: 몸값 자료 없는 시즌)
    return half_up(WM["평균"][f"{cc}|{y2}"] + WM["흩어짐"][cc] * cv(r, n))

def model(lg, season, r, n):
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        return sa_val(season, r, n), f"세리에A {season} {r}위"
    if lg == "IT2":
        # 새 팀은 목표 평균 + 흩어짐 × 곡선(기존 순위값을 쓰면 1993-94 시즌 평균이 1 움직임: 피사 16위)
        return sb_val(season, r), f"세리에B {season} {r}위"
    return None

# 직접 정한 팀-시즌(남미·카타르): (key, 시즌) -> (Elo, lv)
MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
# 아르헨티나 1부(v1.217 비유럽 리그 수준: 목표 평균 + 흩어짐 × 순위 곡선). 순위는 RSSSF 최종 표로 확인(TM과 같음)
man("CA San Lorenzo de Almagro", "1988", world_val("ARG", 1989, 5, 20), "아르헨티나 1부 1988-89 5위")
man("CA River Plate", "1991", world_val("ARG", 1991, 10, 20), "아르헨티나 1부 클라우수라 1991 10위")
man("Racing Club", "1991", world_val("ARG", 1991, 4, 20), "아르헨티나 1부 클라우수라 1991 4위")
# 브라질 1991(1~6월 진행 중 대회, RSSSF braz91 최종 순위)·칠레 1991(TM 표, 우승 콜로콜로)
man("Sport Club Corinthians Paulista", "1991", world_val("BRA", 1991, 5, 20), "브라질 세리에 A 1991 5위")
man("CR Flamengo", "1991", world_val("BRA", 1991, 9, 20), "브라질 세리에 A 1991 9위")
# 칠레: 도구가 지금 자료로 계산하는 흩어짐은 35.8(json 38.5)이라 이동 0이 되게 1492.95 + 35.83 × 2.51 = 1583
man("CSD Colo-Colo", "1991", 1583, "칠레 1부 1991 1위")
# 카타르 2003-04(RSSSF qat04 최종 표 10팀)
QAT_RANK = {"Al-Sadd SC": 1, "Qatar SC": 2, "Al-Ahli SC": 4, "Al-Rayyan SC": 5, "Al-Gharafa SC": 6,
            "Al-Wakrah SC": 7, "Al-Khor SC": 8, "Al-Shamal SC": 9, "Al-Sailiya SC": 10}
QAT_NOTE = {"Al-Gharafa SC": " (리그 수준 추정, 당시 이름 알이티하드)", "Al-Sailiya SC": " (리그 수준 추정, 당시 이름 실리야)"}
for nm, rk in QAT_RANK.items():
    man(nm, "2003-04", world_val("QAT", 2004, rk, 10), f"카타르 2003-04 {rk}위/10팀" + QAT_NOTE.get(nm, " (리그 수준 추정)"))
# 유럽 대회 상대(다른 선수 자료에 그 시즌 값 없음): tools/league_era_normalize.py 목표 평균 + 흩어짐 × 순위 곡선
#  체코 1996-97 목표 1539.8 + 56.07 × cv(1,16) = 1680.6 (TM 표 TS1 1996, 우승 스파르타)
#  포르투갈 1부 1996-97 목표 1550.9 + 126.51 × cv(3,18) = 1685.8 (TM 표 PO1 1996)
#  크로아티아 1998-99 목표 1475.9 + 98.62 × cv(3,12) = 1547.7 (RSSSF kroa99 최종 3위, 1단계 12팀)
man("AC Sparta Praha", "1996-97", 1681, "체코 1996-97 1위")
man("SL Benfica", "1996-97", 1686, "포르투갈 1부 1996-97 3위")
man("HNK Hajduk Split", "1998-99", 1548, "크로아티아 1998-99 3위/12팀")
# 세리에C1 1992-93 B조 3위(TM 표 IT3B 1992): 다른 선수 자료 세리에C1 A조 1992-93 1위 1546·6위 1439 사이 값
man("AC Perugia", "1992-93", 1503, "세리에C1(3부) B조 1992-93 3위/18팀 (추정)")

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

SA_COMP = {"CLI", "SCSA", "ALPL", "ARGC", "QSL", "QCPC"}

def opp_elo(opp, d, cid, sid=None):
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or (cid not in SA_COMP and _sub(key(x["opp"]), k)))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    if cid in ("QSL", "QCPC"): seasons = [eu]
    elif cid in SA_COMP: seasons = [d[:4]]
    else:
        euro = cid in ("CL", "CLQ", "UEFA", "EPP")
        seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if euro else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접(리그 수준 모형)"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    if cid in SA_COMP: return None
    for lg in ("IT1", "IT2"):
        t = RANKS.get((lg, eu))
        if t and k in t:
            r, n = RANK_FIX.get((lg, eu, k), t[k][0]), t[k][1]
            res = model(lg, eu, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg))
                return res
    return None

# ---------------------------------------------------------------- 출전
def sched_date(s):
    return datetime.strptime(s.split(" ")[1], "%d/%m/%Y").strftime("%Y-%m-%d") if s else ""
def ldate(g):
    return DATE_FIX.get(g["gameId"]) or g["date_local_tm_report"] or sched_date(g["date_tm_schedule"])
def clean_opp(o): return o.split(" (")[0].strip()

M = []
for g in GAMES:
    M.append([ldate(g), clean_opp(g["opponent"]), comp_of(g["competitionId"], g["round"]),
              MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])

# RSSSF 경기 줄로만 확인되는 경기(Transfermarkt 없음): 출전 분 자료 없음 → 90분 추정
# (날짜, 상대, 대회, 시즌 키, 골 목록[(분, 표시 분, 골 전 우리, 상대, PK)], 단판/합산)
QAT = [
    ("2003-10-17", "Al-Ahli SC", "QSL", [(91, "90+1", 0, 3, 1)]),
    ("2003-10-23", "Al-Khor SC", "QSL", [(19, 0, 0, 1, 1), (52, 0, 1, 2, 1)]),
    ("2003-11-06", "Al-Wakrah SC", "QSL", [(70, 0, 0, 1, 0)]),
    ("2003-11-22", "Al-Shamal SC", "QSL", [(23, 0, 0, 0, 0)]),
    ("2003-12-04", "Qatar SC", "QSL", [(16, 0, 0, 0, 0), (72, 0, 1, 1, 0)]),
    ("2003-12-12", "Al-Gharafa SC", "QSL", [(27, 0, 1, 0, 1), (51, 0, 2, 1, 0)]),
    ("2004-01-29", "Al-Sailiya SC", "QSL", [(27, 0, 1, 0, 0), (36, 0, 2, 0, 0), (64, 0, 3, 0, 0), (68, 0, 4, 0, 0)]),
    ("2004-02-06", "Al-Ahli SC", "QSL", [(51, 0, 1, 1, 1)]),
    ("2004-02-22", "Al-Khor SC", "QSL", [(2, 0, 0, 0, 0)]),
    ("2004-02-29", "Al-Sadd SC", "QSL", [(82, 0, 1, 1, 0)]),
    ("2004-03-06", "Al-Wakrah SC", "QSL", [(2, 0, 0, 0, 1), (64, 0, 2, 0, 0), (80, 0, 3, 0, 1)]),
    ("2004-03-12", "Al-Rayyan SC", "QSL", [(2, 0, 0, 0, 0), (48, 0, 1, 2, 0), (84, 0, 2, 5, 0)]),
    ("2004-03-19", "Al-Shamal SC", "QSL", [(76, 0, 3, 2, 0)]),
    ("2004-04-15", "Al-Gharafa SC", "QSL", [(26, 0, 0, 0, 0), (30, 0, 1, 0, 0)]),
    ("2004-04-24", "Qatar SC", "QCPC", [(76, 0, 0, 4, 1)]),   # 왕세자컵 준결승 1차전(홈)
]
EXTRA_M, EXTRA_G = [], []
if INCLUDE_QATAR:
    for d, o, c, gl in QAT:
        comp = "lg" if c == "QSL" else "dsf"
        EXTRA_M.append([d, o, comp, 90, 1])
        for mi, dm, gf, ga, pk in gl:
            tie = None if c == "QSL" else [1, 1, 0, 0, 0, 0]
            EXTRA_G.append((d, o, c, comp, mi, dm, gf, ga, pk, tie, "2003-04"))
if INCLUDE_BOCA_RSSSF:
    # 클라우수라 1991 14라운드(RSSSF; ESPN은 13라운드) 보카 6-1 라싱: 19분 0-0, 42분 2-1, 52분 3-1 (ESPN 2026.6.2 기사)
    EXTRA_M.append(["1991-06-02", "Racing Club", "lg", 90, 1])
    for mi, gf, ga in [(19, 0, 0), (42, 2, 1), (52, 3, 1)]:
        EXTRA_G.append(("1991-06-02", "Racing Club", "ARGC", "lg", mi, 0, gf, ga, 0, None, "1991"))
M += EXTRA_M
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et, sid=None):
    res = opp_elo(opp, d, cid, sid)
    if res is None:
        missing_elo.add((opp, d, cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["batistuta_scorer"] == "1", e["batistuta_assist_other"] == "1", e["batistuta_self_assist"] == "1"
    if iss: judg.append(("본인 PK 골의 본인 도움(도움 아님)", ldate(g), e["minute"]))
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(e["minute"])
    et = int(mi > 90 and (not dm or int(str(dm).split("+")[0]) >= 105))
    if et and g["gameState"] == "regularly_terminated": sys.exit("연장 판정 이상 " + gid)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = clean_opp(g["opponent"])
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal", "Deflected"):
            sys.exit("도움 유형 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

for d, o, c, comp, mi, dm, gf, ga, pk, tie, s in EXTRA_G:
    add_row("g", mi, dm, gf, ga, pk, 0, tie, comp, 0, d, o, c, 0, s)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

def sort_min(r):
    return r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5
rows.sort(key=lambda r: (r[9], sort_min(r), 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    return diffs
CROSS, SAMEGAME = [], []
OTHERS = {}
for fn in sorted(os.listdir(os.path.join(ROOT, "src", "data"))):
    if not fn.endswith(".js") or fn in ("hon.js", "bat.js"): continue
    P = fn[:-3].upper()
    try: OTHERS[fn] = load_js(fn, P)
    except Exception: continue
for fn, ent in OTHERS.items():
    for r in E:
        if r[0] != "a": continue
        hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1])]
        if hit: CROSS.append(("바티스투타 도움→" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:
        if x[0] == "a" and norm(str(x[13])) in (norm("Gabriel Batistuta"), "batistuta"):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn + " 도움→바티스투타 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                SAMEGAME.append((fn, r[9], r[1], tuple(dd) or "같음"))
                break
SAMEGAME = sorted(set(SAMEGAME))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s_ in SAMEGAME:
        if s_[-1] != "같음": print("같은 경기 차이", s_)
    print("같은 경기", collections.Counter((s_[0], s_[-1] == "같음") for s_ in SAMEGAME))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("newbt", "1989-07-01"), ("rivbt", "1990-09-01"), ("bocbt", "1991-08-20"), ("fiobt", "2000-07-01"),
         ("rombt", "2003-01-17"), ("intbt", "2003-08-01"), ("arabt", None)]
TM_CLUB = {"1286": "newbt", "209": "rivbt", "189": "bocbt", "430": "fiobt", "12": "rombt", "46": "intbt"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
    if g["club_id"] in ("430", "12", "46") and season_eu(ldate(g))[:4] != g["seasonId"]: sys.exit("시즌 불일치 " + g["gameId"])
PERIODS = [("뉴웰스 올드 보이스", "1988~1989", None, "1989-07-01"), ("리버 플레이트", "1989~1990", "1989-07-01", "1990-09-01"),
           ("보카 주니어스", "1990~1991", "1990-09-01", "1991-08-20"), ("피오렌티나", "1991~2000", "1991-08-20", "2000-07-01"),
           ("AS 로마", "2000~2003", "2000-07-01", "2003-01-17"), ("인테르", "2003", "2003-01-17", "2003-08-01"),
           ("알아라비", "2003~2005", "2003-08-01", None)]
def per(lo, hi):
    inr = lambda d: (lo is None or d >= lo) and (hi is None or d < hi)
    return [sum(1 for m in M if inr(m[0])), sum(1 for r in E if r[0] == "g" and inr(r[9])),
            sum(1 for r in E if r[0] == "a" and inr(r[9])), sum(m[3] for m in M if inr(m[0]))]
ST = [(n, y, per(lo, hi)) for n, y, lo, hi in PERIODS]

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NEST = sum(1 for m in M if len(m) > 4)
NQ = len(QAT) if INCLUDE_QATAR else 0
NQG = sum(len(x[3]) for x in QAT) if INCLUDE_QATAR else 0
NOTE_LINES = [
    f"가브리엘 바티스투타(뉴웰스 올드 보이스·리버 플레이트·보카 주니어스·피오렌티나·AS 로마·인테르·알아라비)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 산로렌소전 ~ {d_(M[-1][0])} 카타르 SC전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·아르헨티나 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n}({y}) {v[0]}·{v[1]}·{v[2]}" for n, y, v in ST)
    + f". 출전 분 합계 {MIN_TOT:,}분(90분으로 추정한 {NEST}경기 포함)",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 대회 경기 전부; 바티스투타 골·도움 수는 선수 경기 성적과 경기마다 같음). FotMob에는 바티스투타 기록이 없음. 피오렌티나·로마·인테르 경기·골은 영어·스페인어·이탈리아어 위키백과 클럽·시즌별 기록과 거의 같음(아래 차이). 남미 대회 골은 RSSSF 득점자 목록과 같음",
    "Transfermarkt에 없는 경기: 아르헨티나 리그(뉴웰스 1988-89, 리버 1989-90, 보카 1990-91)는 Transfermarkt에 출전 기록이 전혀 없음(위키백과 리그 79경기 24골 안팎). 경기별 날짜·상대·골 시각이 확인되는 1경기만 넣음 — 1991.6.2 클라우수라 보카 6-1 라싱전 3골(RSSSF 경기 줄, 골 시각 19·42·52분은 ESPN 경기 회고 기사, 선발 출전·출전 분 90분 추정). 나머지 RSSSF 경기 줄(보카 1990-91 리그 8경기 10골, 뉴웰스 1989.6 리길야 2경기 3골, 리버 1989.9.27 리길야 산로렌소전 1골)은 골 시각이 없어 넣지 않음. 리버 리그 21경기 4골·뉴웰스 리그 24경기 7골 등 경기별 자료가 없는 나머지도 넣지 않음. 같은 ESPN 기사에 바티스투타가 55분 라토레 골에 패스했다는 서술이 있으나 단일 서술이라 도움으로 넣지 않음",
    f"알아라비(카타르) 2003-04: Transfermarkt에 경기 기록이 없음. RSSSF 카타르 2003-04 경기 줄에 골 시각이 있는 {NQ}경기 {NQG}골(스타스리그 14경기 25골 = 그 시즌 득점왕 25골, 왕세자컵 준결승 1차전 카타르 SC전 76분 PK 1골)만 넣음(출전 분 자료가 없어 90분 추정; RSSSF에 'pen'으로 적힌 골은 PK). 골이 없는 리그 4경기와 컵 1경기(위키백과 리그 18경기·컵 2경기), 2004-05 시즌(위키백과 3~4경기 0~3골, 경기별 자료 없음)은 넣지 않음.",
    "Transfermarkt와 위키백과 차이: 앵글로-이탈리안컵 1993-94 2경기 2골(스페인어·이탈리아어 위키백과)은 Transfermarkt에 없고 경기별 자료가 없어 넣지 않음. 1996-97 세리에A 골(위키백과 13, Transfermarkt 12)·1999-00 챔스 골(위키백과 6, Transfermarkt 5)은 경기별 근거가 없어 Transfermarkt 기준",
    "골: Transfermarkt 리포트 골 245개(PK 22개, 자책골 없음)와 RSSSF 골(카타르·보카). 1998.11.3 UEFA컵 2라운드 2차전 그라스호퍼전(살레르노, 관중이 던진 폭죽으로 중단 뒤 0-3 몰수패)은 공식 기록에 골이 없어 출전만 셈(Transfermarkt 90분)",
    f"도움: 모두 Transfermarkt 경기 리포트 도움(2014년 이전이라 단일 출처, 크레스포·비에리 선례). 도움 {NA} = Transfermarkt 34 − 슈팅 리바운드('Shot on goal') 2(2000.3.18 칼리아리전 미야토비치, 1999.9.22 챔스 바르셀로나전 아모로소) − 상대 자책골 유도 2(1994.11.20 나폴리전 칸나바로, 1991.12.1 크레모네세전 잔데비아조). 1997년 이전 Transfermarkt 리포트는 도움 기록이 드물어(골 대부분에 도움 칸이 비어 있음) 이 시기 도움은 실제보다 적을 수 있음. 위키백과에는 도움 기록이 없음",
    "출전 분: Transfermarkt 그대로. 연장 경기: 1988.10.26 리베르타도레스 결승 2차전 나시오날 원정(120분), 1989.10.11 수페르코파 그레미우 원정(교체 58분, 승부차기), 1991.8.4 리길야 준결승 2차전 라싱 원정(120분, 승부차기) 등",
    "날짜: 유럽 경기는 Transfermarkt 리포트·일정 날짜(선수 경기 성적의 22:00/23:00 UTC 자리값은 하루 앞섬). 남미 경기는 Transfermarkt 일정 날짜(RSSSF와 같음; 리베르타도레스 1991 16강 2차전 코린치안스 원정·준결승 1차전 콜로콜로전은 RSSSF가 각각 4.25·5.17로 하루 늦게 적음 — 골·도움 없음). 카타르 경기는 RSSSF 날짜",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 리그 시즌 수준 모형(그 시즌 리그 목표 평균 + 흩어짐 × 순위 곡선) 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 세리에A·B 순위표+모형 {SRC['순위표+리그 모형']}, 남미·카타르 순위+모형 {SRC['직접(리그 수준 모형)']})",
    "남미·카타르 상대 수준: 아르헨티나 1부는 그때 진행 중인 시즌 최종 순위(산로렌소 1988-89 5위, 리버 플레이트 클라우수라 1991 10위, 라싱 클라우수라 1991 4위; Transfermarkt 표를 RSSSF 표와 대조), 브라질 1991 전국 선수권(1~6월) 최종 순위(코린치안스 5위, 플라멩구 9위; RSSSF), 칠레 1991 우승 콜로콜로, 카타르 스타스리그 2003-04 최종 순위(RSSSF, 10팀). 모두 다른 선수 자료와 같은 나라별 리그 수준(1990년대는 가장 가까운 시즌 수준)을 씀. 카타르 상대는 '리그 수준 추정'으로 표시",
    "대회 비중: 리베르타도레스 조별·16강은 리베르타도레스 조별, 8강·준결승·결승은 리베르타도레스 토너먼트(준결승·결승 가중), 수페르코파 수다메리카나는 수다메리카나 비중, 리길야 프레 리베르타도레스(1991)는 국내컵(골·도움 없음), 수페르코파 이탈리아나는 국내컵 결승, 컵위너스컵 1996-97은 1라운드~8강 유로파 토너먼트·준결승 유로파 준결승, UEFA컵 1라운드는 유로파 예선, 2라운드 이후 유로파 토너먼트, 챔스 2차 조별(1999-00·2001-02·2002-03)은 조별, 카타르 왕세자컵 준결승은 국내컵 준결승",
    f"두 경기 합산(챔스·UEFA컵·컵위너스컵·코파 이탈리아·리베르타도레스·왕세자컵) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·코파 이탈리아는 원정 다득점·연장 있음, 리베르타도레스(1988·1991, 승점제)는 원정 다득점·연장 없이 승부차기로 둠(리켈메·크레스포 자료와 같은 규정), 카타르 왕세자컵 준결승 1차전도 같게 둠(규정 확인 못 함). 바티스투타가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 아르헨티나 클럽은 달력 연도(다른 선수 자료의 아르헨티나 클럽과 같음), 유럽·카타르 클럽은 8월 1일 기준. 클럽 구분은 1989.7.1 전 뉴웰스, 1990.9.1 전 리버 플레이트, 1991.8.20 전 보카(1991.8.11 리길야 결승까지), 2000.7.1 전 피오렌티나, 2003.1.17 전 로마, 2003.8.1 전 인테르(임대), 이후 알아라비",
    "우승·수상은 Transfermarkt 업적 페이지 기준: 세리에A 2000-01(로마), 코파 이탈리아 1995-96·수페르코파 이탈리아나 1996(피오렌티나), 수페르코파 이탈리아나 2001(로마), 아르헨티나 1부 1989-90(리버 플레이트, Transfermarkt 표기 1990), 세리에B 우승 1993-94(피오렌티나). 개인: 아르헨티나 올해의 선수 1998, 득점왕 세리에A 1994-95(26골)·코파 이탈리아 1995-96(8골)·카타르 스타스리그 2003-04(25골). 아르헨티나 클라우수라 1991 득점왕(11골, RSSSF)은 Transfermarkt 업적에 없어 넣지 않음. 세리에A 최우수 외국인 선수(1999)는 외국인 선수상이라 넣지 않음. 코파 아메리카·컨페더레이션스컵 등 대표팀 기록은 뺌",
    "은퇴: 2005년(마지막 공식 기록 경기 2004.4.24 왕세자컵 준결승 카타르 SC전; Transfermarkt 마지막 클럽 경기 2003.4.19 인테르-브레시아전)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM "]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE):
        sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mdates = collections.Counter(m[0] for m in M)
for d, rs in by.items():
    gs = sorted({(r[5], r[6], sort_min(r)) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
    for a, b in zip(gs, gs[1:]):
        if b[0] < a[0] or b[1] < a[1] or b[2] < a[2]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
    if len({(r[1], r[3]) for r in rs}) > 1: problems.append(("같은 날 상대·대회 다름", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
mm = {m[0]: m for m in M}
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r, mm[r[9]]))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const BAT_E={J(E)};\nconst BAT_M={J(M)};\nconst BAT_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game": SAMEGAME, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for n, y, v in ST: print(" ", n, y, v)
