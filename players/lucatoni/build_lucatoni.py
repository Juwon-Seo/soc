#!/usr/bin/env python3
"""Luca Toni: raw/ -> lucatoni.json + src/data/ton.js (판정 근거는 judgments.md)

  python3 players/lucatoni/build_lucatoni.py            # 파일 쓰기
  python3 players/lucatoni/build_lucatoni.py --debug    # Elo 출처 목록
  python3 players/lucatoni/build_lucatoni.py --cross    # 같은 경기 다른 선수 자료 대조
  스크래치 복사본에서는 SOC_ROOT=<복사본>.

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/ranks.txt(순위표), <ROOT>/elo/*(기존 선수 자료·리그 시즌 평균), src/data/*.js(동료 대조).
크레스포 build 스크립트를 바탕으로 함(같은 수집 형식).
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "ton.js")
OUT_JSON = os.path.join(HERE, "lucatoni.json")
ME = "루카 토니"
MYFILE = "ton.js"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 판정 표 (judgments.md)
MIN_FIX = {}
# 골 시각 고침: gameId|TM 분 -> 분
GOAL_MIN_FIX = {"1050054|104": 119}   # 2010.10.20 코파 이탈리아 그로세토전 연장 결승골: TM 104분, FotMob 119분·ESPN 118분·blitzquotidiano 119분
# PK 고침: gameId|분 -> pk
PK_FIX = {"2478951|80": 1}            # 2015.5.24 파르마전 80분: TM 설명 없음, FotMob 'Pen'·ESPN·blitzquotidiano 페달 핸드볼 PK
EXCL_G = {}
# 도움 제외: gameId|분 -> 이유
EXCL_A = {
    "1133564|73": "슈팅 리바운드(Shot on goal, 바조)",
    "1133564|87": "슈팅 리바운드(Shot on goal, 바조)",
    "2217492|56": "슈팅 리바운드(Shot on goal, 소메세)",
    "2370732|71": "슈팅 리바운드(Shot on goal, 차울리)",
    "912669|48": "슈팅 리바운드(Shot on goal, 슈바인슈타이거)",
    "959078|42": "슈팅 리바운드(Shot on goal, 뮐러)",
    "69034|31": "PK 유도(리베리 PK)",
    "2251425|18": "PK 유도(피사로 PK)",
    "2359253|67": "PK 유도(조르지뉴 PK)",
    "2359260|74": "PK 유도(조르지뉴 PK)",
    "2359279|61": "PK 유도(조르지뉴 PK)",
    "2359545|28": "상대 자책골 도움(프리손 자책골; FotMob만 토니 골로 적음)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "IT3A", "IT3B", "IT3O", "L1", "UAE1"}   # IT3O = 세리에C1 잔류 플레이아웃(리그 비중, 디 나탈레 선례)
CUPS = {"CIT", "DFB"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "UI": return "elq"   # 인터토토컵 = 유로파 예선(선례)
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "AFCL":
        if r.startswith("group"): return "acl"
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
    if g["competitionId"] == "IT3O":
        return [leg, home, fu, ft, 0, 0]   # 세리에C1 플레이아웃: 합산 동률이면 정규 시즌 순위가 높은 팀 잔류(원정 다득점·연장 없음, 디 나탈레 선례)
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
MANUAL_ALIAS = {"inter milan": "inter"}
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
SECOND_MEAN = json.load(open(os.path.join(ELO, "league_second_mean.json"), encoding="utf-8"))
WORLD_MEAN = json.load(open(os.path.join(ELO, "league_world_mean.json"), encoding="utf-8"))
LC = [2.51, 1.668, 1.189, 0.842, 0.664, 0.555, 0.43, 0.259, 0.079, -0.096, -0.231, -0.321, -0.412, -0.502, -0.531, -0.649, -0.814, -0.999, -1.103, -1.177, -1.378]
def cv(r, n):   # tools/league_era_normalize.py 순위 곡선
    x = (r - 1) / (n - 1) * 20; i = min(19, int(x)); t = x - i
    return LC[i] + (LC[i + 1] - LC[i]) * t
def half_up(x): return int(x + 0.5)

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 공식 최종 순위와 다른 Transfermarkt 표(v1.157 규칙; 영어·이탈리아어 위키백과 시즌 문서, judgments.md 7절)
RANK_FIX = {("IT2", "1999-00", "AC Cesena"): 17,              # 45점 동률, 피스토이에세 16위·체세나 17위(강등)
            ("IT3B", "1998-99", "ASG Nocerina"): 7,           # it.wiki 최종 순위(TM 6위)
            ("IT3B", "1998-99", "FC Crotone Calcio"): 10,     # 43점 4팀 동률(TM 12위)
            ("IT3B", "1998-99", "Atletico Catania"): 11,      # (TM 9위)
            ("IT3B", "1998-99", "Ancona Calcio"): 14}         # (TM 15위)
for (lg, se, nm), r in RANK_FIX.items():
    k = key(nm); RANKS[(lg, se)][k] = (r, RANKS[(lg, se)][k][1])

def ents_map(prefix, season, suffix=""):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위" + re.escape(suffix) + "$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

# 세리에C1(3부) 18팀 조 순위값: 기존 선수 자료(인자기·디 나탈레·페페·토티·델 피에로·인시녜 등)의 시즌 공통 값, 12위는 11·13위 가운데
C1 = {1: 1546, 2: 1498, 3: 1472, 4: 1455, 5: 1447, 6: 1439, 7: 1429, 8: 1419, 9: 1409, 10: 1402, 11: 1397, 12: 1393,
      13: 1388, 14: 1381, 15: 1371, 16: 1362, 17: 1357, 18: 1346}
def c1_val(r, n):   # 18팀이 아닌 조는 18팀 눈금에 비례 위치로 보간
    if n == 18: return C1[r]
    p = 1 + (r - 1) * 17 / (n - 1); i = int(p); t = p - i
    return half_up(C1[i] + (C1[min(18, i + 1)] - C1[i]) * t)
GROUP = {"IT3A": "A조", "IT3B": "B조", "IT3C": "C조"}

def model(lg, season, r, n):
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        mu = SEASON_MEAN["평균"][f"세리에A|{season}"]
        return half_up(mu + SEASON_MEAN["흩어짐"]["세리에A"] * cv(r, n)), f"세리에A {season} {r}위"
    if lg == "L1":
        m = ents_map("분데스리가", season)
        if r in m: return m[r], f"분데스리가 {season} {r}위"
        mu = SEASON_MEAN["평균"][f"분데스리가|{season}"]
        return half_up(mu + SEASON_MEAN["흩어짐"]["분데스리가"] * cv(r, n)), f"분데스리가 {season} {r}위"
    if lg == "IT2":
        suf = "" if n == 22 else f"/{n}팀"
        m = ents_map("세리에B", season, suf)
        if r in m: return m[r], f"세리에B {season} {r}위{suf}"
        mu = SECOND_MEAN["평균"][f"세리에B|{season}"]
        return half_up(mu + SECOND_MEAN["흩어짐"]["세리에A"] * cv(r, n)), f"세리에B {season} {r}위{suf}"
    if lg in GROUP:
        y = int(season[:4])
        if y <= 2007:
            return c1_val(r, n), f"세리에C1 {GROUP[lg]} {season} {r}위/{n}팀 (추정)"
        return c1_val(r, n), f"세리에C(레가 프로) {GROUP[lg]} {season} {r}위/{n}팀 (추정, 다른 선수 자료의 세리에C 18팀 조 순위값에 맞춤)"
    if lg == "UAE1":
        y = int(season[:4]) + 1
        return half_up(WORLD_MEAN["평균"][f"UAE|{y}"] + WORLD_MEAN["흩어짐"]["UAE"] * cv(r, n)), f"UAE 프로리그 {season} {r}위/{n}팀"
    if lg == "QSL":
        y = int(season[:4]) + 1
        return half_up(WORLD_MEAN["평균"][f"QAT|{y}"] + WORLD_MEAN["흩어짐"]["QAT"] * cv(r, n)), f"카타르 {season} {r}위 (추정, 다른 선수 자료와 같은 리그 수준)"
    return None

# 직접 추정(모두 '추정')
MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
man("AS Cisco Lodigiani", "2005-06", 1278, "세리에C2(4부) C조 2005-06 6위/18팀 (추정, 시스코 로마; 다른 선수 자료의 세리에C2 6위 값)")

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid, club_id):
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    seasons = [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    if club_id == "27": lgs = ["L1"]
    elif club_id == "5432": lgs = ["UAE1", "QSL"]
    else: lgs = ["IT1", "IT2", "IT3A", "IT3B", "IT3C"]
    for lg in lgs:
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
    return g["date_local_tm_report"] or sched_date(g["date_tm_schedule"])
def oname(g): return re.sub(r"\s*\(- ?\d{4}\)|\s*\(\d{4} - \d{4}\)", "", g["opponent"]).strip()

M = []
for g in GAMES:
    M.append([ldate(g), oname(g), comp_of(g["competitionId"], g["round"]), MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])
M.sort(key=lambda r: r[0])

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
    isg, isa, iss = e["toni_scorer"] == "1", e["toni_assist_other"] == "1", e["toni_self_assist"] == "1"
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
        pk = PK_FIX.get(tag, int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"))
        add_row("g", mi, dm, gf, ga, pk, 0, tie, comp, ko, d, opp, cid, et, g["club_id"])
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal", "Deflected"):
            sys.exit("도움 유형 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et, g["club_id"])

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
        if not x[4].startswith("same"): print(x)

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
    if not fn.endswith(".js") or fn in ("hon.js", MYFILE): continue
    P = fn[:-3].upper()
    try: OTHERS[fn] = load_js(fn, P)
    except Exception: continue
for fn, ent in OTHERS.items():
    for r in E:
        if r[0] != "a": continue
        hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1])]
        if hit: CROSS.append(("토니 도움→" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:
        if x[0] == "a" and norm(str(x[13])) == norm("Luca Toni"):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn + " 도움→토니 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                SAMEGAME.append((fn, r[9], r[1], tuple(d) or "같음"))
                break
SAMEGAME = sorted(set(SAMEGAME))
# TM 리포트의 동료 도움(토니 골)·토니 도움(동료 골) 중 동료 파일에 대응 행이 없는 것
MISSING_X = []
NAMEFILE = {}
for fn in OTHERS:
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r'_NOTE="([^"\\]*(?:\\.[^"\\]*)*)"', s)
    NAMEFILE[fn] = (m.group(1)[:40] if m else "")
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s_ in SAMEGAME:
        if s_[-1] != "같음": print("같은 경기 차이", s_)
    print("같은 경기", collections.Counter((s_[0], s_[-1] == "같음") for s_ in SAMEGAME))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("modlt", "1996-07-01", "모데나", "1994~1996"), ("emplt", "1997-07-01", "엠폴리", "1996~1997"),
         ("fzolt", "1998-07-01", "피오렌추올라", "1997~1998"), ("lodlt", "1999-07-01", "로디자니", "1998~1999"),
         ("trelt", "2000-07-01", "트레비소", "1999~2000"), ("viclt", "2001-07-01", "비첸차", "2000~2001"),
         ("brelt", "2003-07-01", "브레시아", "2001~2003"), ("pallt", "2005-07-01", "팔레르모", "2003~2005"),
         ("fiolt", "2007-07-01", "피오렌티나", "2005~2007"), ("baylt", "2010-01-01", "바이에른 뮌헨", "2007~2009"),
         ("romlt", "2010-07-01", "AS 로마", "2010"), ("genlt", "2011-01-08", "제노아", "2010~2011"),
         ("juvlt", "2012-01-30", "유벤투스", "2011~2012"), ("naslt", "2012-08-31", "알나스르(두바이)", "2012"),
         ("fiolt", "2013-07-05", "피오렌티나", "2012~2013"), ("verlt", None, "엘라스 베로나", "2013~2016")]
TM_CLUB = {"1385": "modlt", "749": "emplt", "4163": "fzolt", "4086": "lodlt", "2251": "trelt", "2655": "viclt", "19": "brelt",
           "458": "pallt", "430": "fiolt", "27": "baylt", "12": "romlt", "252": "genlt", "506": "juvlt", "5432": "naslt", "276": "verlt"}
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
    if season_eu(ldate(g))[:4] != g["seasonId"]: sys.exit("시즌 불일치 " + g["gameId"] + " " + ldate(g))
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
    f"루카 토니(모데나·엠폴리·피오렌추올라·로디자니·트레비소·비첸차·브레시아·팔레르모·피오렌티나·바이에른 뮌헨·AS 로마·제노아·유벤투스·알나스르·엘라스 베로나)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 알레산드리아전 ~ {d_(M[-1][0])} 유벤투스전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·이탈리아 대표팀·바이에른 뮌헨 2군 경기(2009-10 독일 3부 2경기 0골 1도움) 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n}({y}) {v[0]}·{v[1]}·{v[2]}" for n, y, v in ST)
    + f". 출전 분 합계 {MIN_TOT:,}분(90분 추정 없음). 피오렌티나 두 시기(2005~2007, 2012~2013)는 클럽 탭에서 한 클럽으로 묶임",
    "프로 리그: 가장 낮은 리그는 세리에C1(3부, 레가 프로 소속 프로 리그 — 모데나 1994-96·피오렌추올라 1997-98·로디자니 1998-99)이라 모든 시즌을 셈",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 대회 경기 전부; 토니 골·도움 수는 선수 경기 성적과 경기마다 같음). 클럽·시즌별 경기·골은 영어·이탈리아어 위키백과와 같음(아래 두 대회 제외). 2010-11 이후 골은 FotMob 경기 기록과 대조함(골 순서·골 뒤 스코어 같음, 시각은 1분 안; FotMob 기록이 없는 2011.2.5 칼리아리전·2011.4.10 제노아전·알나스르 3경기는 Transfermarkt만 근거). 그 전(로마 2010 포함)은 경기별 두 번째 출처가 없음",
    "넣지 못한 경기: 코파 이탈리아 세리에C(3부 리그 팀들의 컵) 6경기 3골(피오렌추올라 1997-98 4경기 2골, 로디자니 1998-99 2경기 1골)과 UAE 리그컵(에티살라트컵) 2011-12 2경기 2골은 위키백과·FotMob 시즌 합계에만 있고 날짜·상대·출전 분을 적은 경기별 자료를 찾지 못해 넣지 않음. 그래서 이 계산기 합계(648경기 301골)는 위키백과(658경기 306골)보다 10경기 5골 적음. 모데나 1994-95 코파 이탈리아 3경기는 Transfermarkt에 명단 외로 적혀 있음",
    "골: Transfermarkt 리포트 골 301개(자책골 없음). PK는 Transfermarkt PK 23개에 2015.5.24 파르마 원정 80분 골(Transfermarkt 리포트는 설명이 비어 있으나 FotMob·ESPN·이탈리아 기사 모두 페달 핸드볼로 얻은 PK)을 더한 24개. 2016.2.20 키에보전 29분 골은 PK가 막힌 뒤 리바운드 골이라 PK 아님. 2010.10.20 코파 이탈리아 그로세토전 연장 결승골은 Transfermarkt 104분이 아니라 FotMob 119분(ESPN 118분, 이탈리아 기사 119분)을 씀",
    "2014.4.27 카타니아전 28분 2-0 골: Transfermarkt·ESPN 등은 골키퍼 프리손 자책골(토니 헤딩 슈팅)로, FotMob·스카이스포츠는 토니 골로 적음. 공식 시즌 득점(2013-14 세리에A 20골, Transfermarkt·FotMob 시즌 합계와 같음)에 맞춰 자책골로 보고 토니 골·도움 모두 아님",
    f"도움: Transfermarkt 경기 리포트 도움 83개 − 슈팅 리바운드('Shot on goal') 6(2001.4.14 볼로냐전 소메세, 2002.4.21 피오렌티나전 바조 2개, 2004.1.11 리보르노전 차울리, 2009.4.11 프랑크푸르트전 슈바인슈타이거, 2009.10.17 프라이부르크전 뮐러) − PK 유도 5(2007.8.18 브레멘전 리베리, 2012.12.16 시에나전 피사로, 2013.9.25 토리노전·9.29 리보르노전·10.20 파르마전 조르지뉴) − 상대 자책골 도움 1(위 카타니아전) = {NA}. 본인 PK 골에 본인이 PK 유도 도움으로 적힌 2개(2010.11.24 비첸차전 88분, 2014.9.15 팔레르모전 41분)는 원래 도움 합계에 없음. 1994~2000(모데나~트레비소) Transfermarkt 경기 도움은 모두 0이고 다른 경기별 출처가 없어 도움 0",
    "2014년 8월 전 도움은 Transfermarkt 단일 출처도 셈(다른 선수 자료 선례). 그중 FotMob 경기 기록(2010-11 이후)에 토니 도움이 없는 것: 2010.10.3 제노아전 팔라시오, 2010.11.10 제노아전 밀라네토, 2012.11.11 피오렌티나전 아퀼라니(FotMob은 랴이치 도움), 2013-14 베로나의 고메스 2개·마르치뉴·호물루 2개, 2012.5.15 AFC 챔스 레퀴야전 후마이드 압둘라; FotMob 기록이 없는 2011.4.10 유벤투스전 마트리, 알나스르 2012.2.9 브레시아노·3.25 힐랄 사이드. 2014년 8월 뒤 도움 2개(2014.9.24 제노아전 이오니처, 2014.11.23 피오렌티나전 로페스)는 Transfermarkt·FotMob이 같음",
    "출전 분: Transfermarkt 그대로. 연장 경기: 2000.9.6 코파 이탈리아 브레시아전(120분), 2005.8.14 코파 이탈리아 리미니전(120분, 연장 120분 도나델 골 도움), 2008.2.27 DFB-포칼 8강 1860 뮌헨전(84분), 2008.4.10 UEFA컵 8강 2차전 헤타페 원정(120분, 연장 115·120분 2골), 2008.4.19 DFB-포칼 결승 도르트문트전(120분, 연장 103분 결승골), 2010.10.20 그로세토전(120분, 연장 119분 골), 2010.11.24 비첸차전(교체 52분, 88분 PK·연장 92분 골), 2013.1.16 코파 이탈리아 8강 로마전(78분)",
    "날짜: Transfermarkt 리포트·일정 날짜(선수 경기 성적의 22:00/23:00 UTC 자리값은 하루 앞섬). 로디자니 1998-99 세 경기(크로토네·유베 스타비아·바티팔리에세전)는 Transfermarkt 결과 칸이 0-0으로 잘못 적혀 있어 리포트 득점 목록의 순서·스코어를 씀",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 리그 수준 모형에 넣은 값, 직접 추정 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "리그 수준: 세리에A·분데스리가 상대는 모두 다른 선수 자료 값. 세리에B는 유럽 2부 시즌 평균(1부 수준 이동의 절반)과 순위 곡선(1996-97·1999-00 20팀, 2003-04 24팀, 2005-06·2010-11·2013-14 22팀). 세리에C1(3부)은 다른 선수 자료의 18팀 조 순위값(1위 1546 … 18위 1346, 12위는 11·13위 가운데)을 시즌 구분 없이 씀(추정), 레가 프로 2014-15(20팀 조)·2015-16 상대도 같은 눈금에 맞춤(추정). 시스코 로마(옛 로디자니) 2005-06은 세리에C2 C조 6위(영어 위키백과)를 다른 선수 자료의 세리에C2 6위 값 1278로(추정). UAE 프로리그 2011-12(12팀)는 다른 선수 자료와 같은 UAE 리그 수준 모형, 레퀴야 2011-12(카타르 1위)는 카타르 리그 수준 모형(추정)",
    "순위: Transfermarkt 표를 영어·이탈리아어 위키백과 최종 순위와 대조해 고친 곳 — 세리에B 1999-00 체세나 17위(45점 동률, Transfermarkt 16위), 세리에C1 B조 1998-99 노체리나 7위·크로토네 10위·아틀레티코 카타니아 11위·안코나 14위(Transfermarkt 표는 로디자니 세 경기 결과가 빠져 순서가 다름). 세리에C1 1994-95·1995-96·1997-98 A조와 세리에B 1996-97·2003-04·2005-06·2010-11, 레가 프로 2014-15 A조는 같음",
    "대회 비중: 세리에C1 잔류 플레이아웃(1995.6 마사세전 두 경기)은 리그 비중 + 두 경기 합산(합산 동률이면 정규 시즌 순위가 높은 팀 잔류라 원정 다득점·연장 없음, 다른 선수 자료의 세리에C2 플레이아웃 선례), 인터토토컵 결승(2001 PSG전)·UEFA컵 1라운드는 유로파 예선, UEFA컵 2007-08 조별은 유로파 조별, 32강·16강·8강은 유로파 토너먼트, AFC 챔스 2012 조별은 AFC 챔스 리그 단계, 코파 이탈리아 1999-00·2003-04 조별은 국내컵(조별이라 단판 아님)",
    f"두 경기 합산(UEFA컵·챔스·코파 이탈리아·플레이아웃) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·코파 이탈리아는 원정 다득점·연장 있음. 토니가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 모든 클럽 8월 1일 기준(7월 경기 없음). 클럽 구분은 1996.7.1 전 모데나, 1997.7.1 전 엠폴리, 1998.7.1 전 피오렌추올라, 1999.7.1 전 로디자니, 2000.7.1 전 트레비소, 2001.7.1 전 비첸차, 2003.7.1 전 브레시아, 2005.7.1 전 팔레르모, 2007.7.1 전 피오렌티나, 2010.1.1 전 바이에른 뮌헨, 2010.7.1 전 AS 로마(임대), 2011.1.8 전 제노아, 2012.1.30 전 유벤투스, 2012.8.31 전 알나스르, 2013.7.5 전 피오렌티나, 이후 엘라스 베로나",
    "우승·수상은 Transfermarkt 업적 페이지 기준: 분데스리가 2007-08·2009-10, DFB-포칼 2007-08·2009-10(2009-10은 2010.1 로마 임대 전까지 뛴 시즌, Transfermarkt 기준), DFB-리가포칼 2007(Transfermarkt 업적 목록에는 없으나 영어 위키백과·같은 팀 다른 선수 자료와 같게 넣음), 세리에B 우승 2003-04(팔레르모). 개인: 유러피언 골든 슈 2005-06(31골), 득점왕 세리에A 2005-06(31골)·2014-15(22골), 분데스리가 2007-08(24골), UEFA컵 2007-08(10골), 세리에B 2003-04(30골; Transfermarkt 업적 페이지는 02/03으로 적었으나 30골은 팔레르모 2003-04 시즌), 세리에A 올해의 팀 2014-15(이탈리아 선수협회). 월드컵 2006 우승 등 대표팀 기록은 뺌",
    "은퇴: 2016년(마지막 클럽 경기 2016.5.8 유벤투스전)",
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const TON_E={J(E)};\nconst TON_M={J(M)};\nconst TON_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game": SAMEGAME, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for n, y, v in ST: print(" ", n, y, v)
