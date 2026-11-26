#!/usr/bin/env python3
"""박지성: raw/ -> parkjisung.json + src/data/pjs.js (판정 근거는 judgments.md)

  python3 players/parkjisung/build_parkjisung.py            # 파일 쓰기
  python3 players/parkjisung/build_parkjisung.py --debug    # Elo 출처 목록
  python3 players/parkjisung/build_parkjisung.py --cross    # 같은 경기 다른 선수 자료 대조
  스크래치 복사본에서는 SOC_ROOT=<복사본>.

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/ranks.txt(순위표), jleague_official.json(J리그 공식 기록 data.j-league.or.jp 판독본),
      <ROOT>/elo/*(기존 선수 자료·리그 시즌 평균), src/data/*.js(동료 대조).
루카 토니 build 스크립트를 바탕으로 함(같은 수집 형식).
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "pjs.js")
OUT_JSON = os.path.join(HERE, "parkjisung.json")
ME = "박지성"
MYFILE = "pjs.js"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
JL = json.load(open(os.path.join(HERE, "jleague_official.json"), encoding="utf-8"))

# ---------------------------------------------------------------- 판정 표 (judgments.md)
# 출전 분 고침: gameId -> 분
MIN_FIX = {"1161162": 120}   # 2011.11.30 리그컵 8강 크리스털 팰리스전(연장 1-2): TM 90분, FotMob 선발·교체 없음, 경기 기사(교체 3장 파비우·베르바토프·하파엘) -> 120분
# 추가 경기(Transfermarkt '명단 외', J리그 공식 기록에 선발 출전): [날짜, 상대, 대회, 분]
ADD_M = [["2000-07-05", "FC Tokyo", "dc", 90]]   # 2000 J리그컵 2라운드 1차전 FC 도쿄전(홈 1-1), J리그 공식 기록 match_card_id=5033 선발·교체 없음
# 골 시각 고침: gameId|TM 분 -> 분 (J리그 공식 기록)
GOAL_MIN_FIX = {"3011231|90": 89, "3011247|89": 88, "3011571|36": 35}
EXCL_G = {"3011629|25": "J리그 공식 기록에 없는 골(2001.9.22 미토전 0-1: 정규시간 0-0, 연장 95분 구로베 V골)"}
# 도움 제외: gameId|분 -> 이유
EXCL_A = {
    "986264|52": "PK 유도(케즈만 PK)",
    "37811|17": "PK 유도(판니스텔로이 PK)",
    "936034|22": "PK 유도(호날두 PK)",
    "1050889|71": "슈팅 리바운드(Shot on goal, 오언; FotMob 도움 없음)",
    "1050153|62": "슈팅 리바운드(Shot on goal, 안데르송; FotMob 도움 없음)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"JL11", "JL12", "JAP2", "NL1", "GB1"}
CUPS = {"JAPC", "JEMP", "NLP", "FAC", "CGB"}
SUPER = {"NLSC", "GBCS", "USC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "df"
    if cid == "KLUB": return "cwc"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("6th round"): return "dk"   # 리그컵 5라운드·FA컵 6라운드 = 8강
        return "dc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid in ("UEFA", "EL"):
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # UEFA컵 2003-04 3라운드·16강·8강, 유로파 32강·16강
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
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    if g["competitionId"] not in ("CL", "CLQ", "UEFA", "EL"): sys.exit("합산 규칙 없음 " + gid)
    return [leg, home, fu, ft, 1, 1]       # UEFA 대회(2020-21까지): 원정 다득점·연장

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
MANUAL_ALIAS = {}
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

SEASON_MEAN = json.load(open(os.path.join(ELO, "league_season_mean.json"), encoding="utf-8"))
WORLD_MEAN = json.load(open(os.path.join(ELO, "league_world_mean.json"), encoding="utf-8"))
SECOND_X = json.load(open(os.path.join(ELO, "league_second_x_mean.json"), encoding="utf-8"))
SD2X = 51.24   # tools/league_second_tier_x.py
LC = [2.51, 1.668, 1.189, 0.842, 0.664, 0.555, 0.43, 0.259, 0.079, -0.096, -0.231, -0.321, -0.412, -0.502, -0.531, -0.649, -0.814, -0.999, -1.103, -1.177, -1.378]
def cv(r, n):   # tools/league_era_normalize.py 순위 곡선
    x = (r - 1) / (n - 1) * 20; i = min(19, int(x)); t = x - i
    return LC[i] + (LC[i + 1] - LC[i]) * t
def half_up(x): return int(x + 0.5)

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 순위표: Transfermarkt 표(raw/ranks.txt) + J1 2000·2002 연간 순위(영어 위키백과 'Overall table', raw/ranks_wiki.txt와 같은 내용)
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        lg = p[0]
        if lg.startswith("JAP1 overall"): lg = "J1Y"
        se = p[1].split(" ")[0]
        RANKS[(lg, se)][key(p[4])] = (int(p[2]), int(p[3]))
# J2 2001 공식 최종 순위(영어 위키백과 2001 J.League Division 2): TM 표는 4~6위 순서가 다름(알비렉스 4·오미야 5·오이타 6위)
for nm, r in (("Albirex Niigata", 4), ("Omiya Ardija", 5), ("Oita Trinita", 6)):
    RANKS[("JAP2", "2001")][key(nm)] = (r, 12)

def ents_map(prefix, season, suffix=""):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위" + re.escape(suffix) + "$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

# tools/league_world_normalize.py를 이 자료와 함께 돌렸을 때 이동 0이 되도록 맞춘 값(J1 2000은 점이 하나뿐이라
# 도구가 다시 구한 일본 흩어짐(2002 시즌 점 포함)으로 1721 -> 1722)
J1_TOOL_FIX = {(2000, 1): 1722}
EU_LG = {"GB1": "프리미어리그", "NL1": "에레디비시"}
def model(lg, season, r, n):
    if lg in EU_LG:
        nm = EU_LG[lg]
        m = ents_map(nm, season)
        if r in m: return m[r], f"{nm} {season} {r}위"
        mu = SEASON_MEAN["평균"][f"{nm}|{season}"]
        return half_up(mu + SEASON_MEAN["흩어짐"][nm] * cv(r, n)), f"{nm} {season} {r}위"
    if lg == "J1Y":   # J1 연간 순위(16팀, 두 스테이지 합산)
        y = int(season)
        if (y, r) in J1_TOOL_FIX: return J1_TOOL_FIX[(y, r)], f"J1리그 {y} 연간 {r}위/{n}팀"
        return half_up(WORLD_MEAN["평균"][f"JPN|{y}"] + WORLD_MEAN["흩어짐"]["JPN"] * cv(r, n)), f"J1리그 {y} 연간 {r}위/{n}팀"
    if lg == "JAP2":
        y = int(season)
        return half_up(SECOND_X["평균"][f"J2리그|{y}"] + SD2X * cv(r, n)), f"J2리그 {y} {r}위/{n}팀"
    return None

# 직접 추정(모두 '추정')
MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
# 세르비아·몬테네그로 2004-05(16팀) 2위: 리그 시즌 수준(목표 평균 1442.3, 흩어짐 92.4) + 순위 곡선. 같은 시즌 파르티잔 1위 1674(통합표)와 같은 눈금
man("Red Star Belgrade", "2004-05", 1582, "세르비아·몬테네그로 2004-05 2위/16팀 (추정, 리그 시즌 수준 모형)")
# 에이르스터 디비시 2004-05(19팀) 5위: 유럽 2부 시즌 평균 1235.6 + 흩어짐 54.2 × 순위 곡선
man("FC Volendam", "2004-05", 1269, "에이르스터 디비시(네덜란드 2부) 2004-05 5위/19팀")

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid, club_id):
    k = key(opp)
    if club_id == "593":   # 교토: J리그 연도 시즌(천황배 결승 2003.1.1은 2002 시즌)
        y = "2002" if d == "2003-01-01" else d[:4]
        lgs = ["J1Y", "JAP2"]
        for lg in lgs:
            t = RANKS.get((lg, y))
            if t and k in t and (lg == "JAP2") == (y == "2001"):
                r, n = t[k]
                res = model(lg, y, r, n)
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg))
                return res
        return None
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    if (k, eu) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, eu)]).most_common(1)[0]
        ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + eu))
        return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
        return e, lv
    for lg in ("GB1", "NL1"):
        t = RANKS.get((lg, eu))
        if t and k in t:
            r, n = t[k]
            res = model(lg, eu, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg))
                return res
    return None

# ---------------------------------------------------------------- 출전
def sched_date(s):
    return datetime.strptime(s.split(" ")[1], "%d/%m/%Y").strftime("%Y-%m-%d") if s else ""
def ldate(g):
    return sched_date(g["date_tm_schedule"]) or g["date_local_tm_report"]
def oname(g): return re.sub(r"\s*\(- ?\d{4}\)|\s*\(\d{4} - \d{4}\)", "", g["opponent"]).strip()

M = []
for g in GAMES:
    M.append([ldate(g), oname(g), comp_of(g["competitionId"], g["round"]), MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])
M += [list(x) for x in ADD_M]
M.sort(key=lambda r: r[0])

# J리그 공식 기록과 교토 출전 대조(출전 여부, 교체 분)
jl_play = {x["date"]: x for x in JL if x["played"]}
for m in M:
    if "2000-01-01" <= m[0] < "2002-12-01":
        if m[0] not in jl_play: sys.exit("J리그 공식 기록에 없는 출전 " + str(m))
for d in jl_play:
    if d not in {m[0] for m in M}: sys.exit("J리그 공식 기록 출전이 빠짐 " + d)

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et, club_id):
    res = opp_elo(opp, d, cid, club_id)
    if res is None:
        missing_elo.add((opp, d, cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["park_scorer"] == "1", e["park_assist_other"] == "1", e["park_self_assist"] == "1"
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
    tag = f"{gid}|{e['minute']}"
    mi, dm = minute(e["minute"])
    if tag in GOAL_MIN_FIX: mi, dm = GOAL_MIN_FIX[tag], 0
    et = int(mi > 90 and (not dm or int(str(dm).split("+")[0]) >= 105))
    if et and g["gameState"] == "regularly_terminated": sys.exit("연장 판정 이상 " + gid)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = oname(g)
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        pk = int(e["penalty"] == "1")
        add_row("g", mi, dm, gf, ga, pk, 0, tie, comp, ko, d, opp, cid, et, g["club_id"])
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal", "Deflected") or e["penalty"] == "1":
            sys.exit("도움 유형 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et, g["club_id"])

# 교토 골은 J리그 공식 기록(2000~2002 리그)의 박지성 골과 하나씩 맞아야 함
jl_goals = sorted((x["date"], int(m.strip("'"))) for x in JL for m in x["park_goals"])
my_k = sorted((r[9], r[4]) for r in rows if r[0] == "g" and r[9] < "2002-12-01")
if jl_goals != my_k: sys.exit(f"J리그 공식 골과 다름 {jl_goals} {my_k}")

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
        seen.add(k)
        print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
def load_m(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_M=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1)) if m else []
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
CROSS, SAMEGAME, MCROSS = [], [], []
OTHERS, OTHERS_M = {}, {}
for fn in sorted(os.listdir(os.path.join(ROOT, "src", "data"))):
    if not fn.endswith(".js") or fn in ("hon.js", MYFILE): continue
    P = fn[:-3].upper()
    try: OTHERS[fn] = load_js(fn, P); OTHERS_M[fn] = load_m(fn, P)
    except Exception: continue
PARK_NAMES = {norm("Ji-sung Park"), norm("Park Ji-sung"), norm("Ji-Sung Park"), norm("Park Ji-Sung")}
for fn, ent in OTHERS.items():
    for r in E:
        if r[0] != "a": continue
        hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1])]
        if hit: CROSS.append(("박지성 도움→" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:
        if x[0] == "a" and norm(str(x[13])) in PARK_NAMES:
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn + " 도움→박지성 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                SAMEGAME.append((fn, r[9], r[1], tuple(d) or "같음"))
                break
SAMEGAME = sorted(set(SAMEGAME))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s_ in SAMEGAME:
        if s_[-1] != "같음": print("같은 경기 차이", s_)
    print("같은 경기", collections.Counter((s_[0], s_[-1] == "같음") for s_ in SAMEGAME))
    # 동료 골에 박지성 도움이 있는데 동료 파일 행이 없는 경우, 같은 경기 대회 코드 차이
    mm = {m[0]: m for m in M}
    for fn, Ms in OTHERS_M.items():
        for x in Ms:
            if x[0] in mm and key(x[1]) == key(mm[x[0]][1]) and x[2] != mm[x[0]][2]:
                print("같은 경기 대회 코드 다름", fn, x, mm[x[0]])

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("kyojs", "2003-01-02", "교토 퍼플 상가", "2000~2002"), ("psvjs", "2005-07-05", "PSV 에인트호번", "2003~2005"),
         ("mujs", "2012-07-09", "맨체스터 유나이티드", "2005~2012"), ("qprjs", "2013-08-08", "퀸스 파크 레인저스", "2012~2013"),
         ("psvjs", None, "PSV 에인트호번", "2013~2014")]
TM_CLUB = {"593": "kyojs", "383": "psvjs", "985": "mujs", "1039": "qprjs"}
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
lo = None
PERIODS = []
for k, u, n, y in CLUBS:
    PERIODS.append((n, y, lo, u)); lo = u
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
NOTE_LINES = [
    f"박지성(교토 퍼플 상가·PSV 에인트호번·맨체스터 유나이티드·퀸스 파크 레인저스·PSV 에인트호번)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} JEF 유나이티드 이치하라전 ~ {d_(M[-1][0])} NAC 브레다전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·한국 대표팀·연령별 대표팀 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n}({y}) {v[0]}·{v[1]}·{v[2]}" for n, y, v in ST)
    + f". 출전 분 합계 {MIN_TOT:,}분(90분 추정 없음). PSV 두 시기(2003~2005, 2013~2014 퀸스 파크 레인저스에서 임대)는 클럽 탭에서 한 클럽으로 묶임",
    "프로 리그: 모든 시즌이 1부 리그이고 교토 2001만 J2리그(일본 2부 프로 리그)라 모든 시즌을 셈. 명지대 시절(1999)은 클럽 공식 경기 기록 없음",
    "출처: 경기 목록·출전 분(연장·교체·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 대회 경기 전부). 교토 시절(2000~2002) 리그·J리그컵 경기는 J리그 공식 기록(data.j-league.or.jp 경기별 공식 기록: 선발·교체 시각·득점자·득점 시각)과 모두 대조함. 2010-11 이후 골·도움은 FotMob 경기 기록과 대조함(골 순서·골 뒤 스코어 같음, 시각은 1분 안). 클럽·시즌별 경기·골은 PSV·맨유·퀸스 파크 레인저스 모든 시즌에서 영어 위키백과와 같음",
    "교토 시절 차이: J리그 공식 기록에 따라 2000.7.5 J리그컵 2라운드 1차전 FC 도쿄전(홈 1-1, 선발 90분; Transfermarkt는 명단 외)을 더하고, 2001.9.22 J2 미토 홀리호크 원정(0-1, 정규시간 0-0 뒤 연장 95분 구로베 V골)의 Transfermarkt 박지성 25분 골은 공식 기록에 없어 뺌(J2 2001 리그 골 3 = J리그 공식 기록·J리그 기사·위키백과, Transfermarkt 4). J2 2001 세 골 시각은 공식 기록(89·88·35분, Transfermarkt는 90·89·36분)을 씀",
    "넣지 못한 경기: 위키백과(영어·한국어)의 교토 천황배 출전 4경기(2000 1경기, 2001 1경기, 2002 3라운드~준결승 중 2경기)는 Transfermarkt에 명단 외로 적혀 있고(리포트에 선발 명단 없음) 날짜·출전을 확인할 경기별 자료를 찾지 못해 넣지 않음. 천황배 2002 8강 나고야전·결승 가시마전(Transfermarkt 출전)은 넣음. 그래서 교토 합계(81경기 12골)는 위키백과(85경기 12골)보다 4경기 적음",
    "골: Transfermarkt 리포트 골 59개 − 위 미토전 1 = 58골(PK·자책골 없음). 맨유 2011.4.12 챔스 8강 2차전 첼시전 77분·2011.5.22 블랙풀전 21분 골은 FotMob 경기 기록이 없어 Transfermarkt만 근거(시즌 골 수는 위키백과와 같음)",
    f"도움: Transfermarkt 경기 리포트 도움 48개 − PK 유도 3(2004.4.14 UEFA컵 8강 뉴캐슬전 케즈만, 2005.10.1 풀럼전 17분 판니스텔로이, 2009.3.14 리버풀전 호날두) − 슈팅 리바운드('Shot on goal') 2(2010.9.22 리그컵 스컨소프전 71분 오언, 2010.12.7 챔스 발렌시아전 안데르송; 둘 다 FotMob도 도움 없음) = {NA}. 교토 골(천황배 결승 제외)은 Transfermarkt·J리그 공식 기록에 도움 정보가 없어 교토 시절 도움 0(확인된 0이 아님)",
    "2014년 8월 전 도움은 Transfermarkt 단일 출처도 셈(다른 선수 자료 선례). 2010-11 전 도움 25개는 Transfermarkt만 근거. 2010-11 이후 FotMob이 박지성 도움으로 세지 않은 것: 2011.10.25 리그컵 올더숏전 15분 베르바토프, 2012.9.26 리그컵 레딩전 14분 호일렛(둘 다 FotMob 이벤트에 도움 이름 없음); FotMob 경기 기록이 없는 2011.5.8 첼시전 1분 에르난데스, 2011.5.22 블랙풀전 62분 안데르송. 나머지 2010-11 이후 도움 14개는 Transfermarkt·FotMob이 같음",
    "출전 분: Transfermarkt 그대로이고 J리그 공식 기록 교체 시각과 1분 안에서 같음. 2011.11.30 리그컵 8강 크리스털 팰리스전(연장 1-2)은 Transfermarkt 90분이 아니라 120분(FotMob 선발·교체 없음, 경기 기사에 맨유 교체 3장이 파비우·베르바토프·하파엘). 2000.7.5 FC 도쿄전은 공식 기록 선발·교체 없음이라 90분",
    "J리그 연장: 2000~2002 J1·J2 리그 경기는 90분 동점이면 V골(골든골) 연장 30분을 했음(V골 승 승점 2). 이 계산기는 리그 경기를 보통 리그 경기(무승부 1점)로 계산하고, 연장 골 1개(2002.7.20 비셀 고베 원정 113분 V골 결승골, 1-1에서)만 연장 시간(122분까지)으로 계산함(골든골 규칙은 반영하지 않음)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 리그 수준 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']})",
    "리그 수준: J1리그 2000·2002 상대는 연간 순위(1·2스테이지 합산 16팀, 영어 위키백과 연간 순위표)를 비유럽 리그 시즌 수준(일본 J1 평균 1536, 흩어짐 73.9)과 순위 곡선에 넣은 값, J2리그 2001(12팀) 상대는 다른 나라 2부 수준(J2 평균 1242, 흩어짐 51.2)과 순위 곡선(J2 2001 순위는 영어 위키백과 최종 순위; Transfermarkt 표는 4~6위 순서가 다름). 천황배 2002(결승 2003.1.1)는 2002 시즌 순위",
    "대회 비중: 천황배 8강은 국내컵 8강 이후, 결승은 국내컵 결승. 요한 크루이프 실드·커뮤니티 실드·UEFA 슈퍼컵은 국내컵 결승과 같은 비중, 클럽 월드컵 2008 결승은 클럽 월드컵, UEFA컵 2003-04 3라운드·16강·8강과 유로파 2011-12 32강·16강은 유로파 토너먼트, 챔스 예선(2004-05·2005-06 3차 예선, 2013-14 플레이오프)은 챔스 예선, 잉글랜드 리그컵 5라운드·FA컵 6라운드(재경기 포함)는 8강, J리그컵 1·2라운드는 국내컵",
    f"두 경기 합산(챔스·UEFA컵 토너먼트·챔스 예선) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음). 박지성이 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 교토는 달력 연도(천황배 2002 결승 2003.1.1은 달력 연도에 따라 2003으로 표시됨), PSV·맨유·퀸스 파크 레인저스는 8월 1일 기준. 클럽 구분은 2003.1.2 전 교토, 2005.7.5 전 PSV, 2012.7.9 전 맨유, 2013.8.8 전 퀸스 파크 레인저스, 이후 PSV(임대). 날짜는 Transfermarkt 일정의 현지 날짜(선수 경기 성적의 UTC 자리값 28경기는 하루 앞섬)",
    "우승·수상은 Transfermarkt 업적 페이지 기준(영어 위키백과와 같음): 챔스 2007-08(결승 명단 제외, 시즌 출전), 클럽 월드컵 2008, 프리미어리그 2006-07·2007-08·2008-09·2010-11, 리그컵 2005-06·2008-09·2009-10, 커뮤니티 실드 2010·2011, 에레디비시 2002-03·2004-05, KNVB컵 2004-05, 요한 크루이프 실드 2003, J2리그 2001, 천황배 2002. 개인: 대한축구협회 올해의 선수 2010. 대표팀 기록은 뺌",
    "은퇴: 2014년(마지막 클럽 경기 2014.5.3 PSV-NAC 브레다전)",
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const PJS_E={J(E)};\nconst PJS_M={J(M)};\nconst PJS_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game": SAMEGAME, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for n, y, v in ST: print(" ", n, y, v)
