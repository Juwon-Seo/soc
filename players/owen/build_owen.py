#!/usr/bin/env python3
"""Michael Owen: raw/ -> owen.json + src/data/owe.js (판정 근거는 judgments.md)

  python3 players/owen/build_owen.py          # 쓰기
  python3 players/owen/build_owen.py --debug  # Elo 출처(통합표 외)
  python3 players/owen/build_owen.py --fm     # FotMob 골 대조(2010-11 이후)
  python3 players/owen/build_owen.py --cross  # 동료 자료 대조(다른 파일은 고치지 않음)
  python3 players/owen/build_owen.py --out DIR  # DIR/src/data/owe.js 로 쓰기(검증용 복사본)

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(같은 경기 동료 자료 대조).
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_ROOT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else ROOT
OUT_JS = os.path.join(OUT_ROOT, "src", "data", "owe.js")
OUT_JSON = os.path.join(HERE, "owen.json")
ME = "마이클 오언"
GAP = "2014-08-01"   # 도움 출처 기준일(오언은 모든 경기가 이전 → Transfermarkt 단일 출처 규칙)
CLUB_ID = {"31": "livmo", "418": "rmmo", "762": "newmo", "985": "munmo", "512": "stkmo"}

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
EXCL_G = {}            # Transfermarkt 골이지만 넣지 않는 골: 없음
EXCL_A = {}            # 유형 외 이유로 빼는 도움: 없음(자책골 유도는 자동)
PK_FIX = {}
MIN_FIX = {}
AUTO_EXCL_TYPES = {"Penalty: Fouled player": "PK 유도", "Shot on goal": "슈팅 리바운드(Shot on goal)",
                   "Deflected": "굴절"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "ES1"}
CUP = {"FAC", "CGB", "CDR"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth"): return "dk"   # 리그컵 8강·FA컵 6라운드 = 8강
        return "dc"                                                      # 코파 델 레이 16강까지 포함
    if cid in ("GBCS", "USC"): return "df"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2001-02·2002-03 1·2차 조별 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 2·3라운드·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    # FA컵 'deciders'·'3rd round 2nd leg'는 재경기(단판)
    return "leg" in g["round"].lower() and g["competitionId"] != "FAC"

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]
    leg = 1 if "1st" in g["round"].lower() else 2
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    return [leg, home, fu, ft, 1, 1]   # UEFA 대회·리그컵 준결승·코파 델 레이: 원정 다득점·연장 있음(당시 규칙)

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
def key(n):
    k = norm(n)
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

def seas_norm(s):
    # '1999-2000' -> '1999-00'
    m = re.match(r"^(\d{4})-(\d{2,4})$", s)
    return f"{m.group(1)}-{m.group(2)[-2:]}" if m else s

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], seas_norm(p[1]))][key(p[4])] = (int(p[2]), int(p[3]))
# 순위표 이름과 Transfermarkt 이름이 다른 팀
RANK_NAME = {key("1.FC Kosice (1951 - 2004)"): key("1. FC Košice"), key("Rapid Bucharest "): key("Rapid București"),
             key("Middlesbrough FC"): key("Middlesbrough"), key("Grimsby Town"): key("Grimsby Town"),
             key("Fulham FC"): key("Fulham"), key("Port Vale FC"): key("Port Vale")}

def ents_rank(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위…' 값(다수값): {N: (elo, lv)}"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][(e["elo"], e["lv"])] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

def pl_value(season, r):
    m = ents_rank("프리미어리그", season)
    if r in m: return m[r]
    lo = max(k for k in m if k < r); hi = min(k for k in m if k > r)
    v = int(round((m[lo][0] + m[hi][0]) / 2 + 1e-9))
    return v, f"프리미어리그 {season} {r}위 (추정, 다른 선수 자료 {lo}위 {m[lo][0]}·{hi}위 {m[hi][0]}의 가운데)"

# 잉글랜드 2부(24팀): 기존 자료의 고정 순위값(제라드 판정과 같음)
CH = {1: 1761, 2: 1717, 3: 1689, 4: 1669, 5: 1656, 6: 1648, 7: 1642, 8: 1635, 9: 1626, 10: 1617, 11: 1607, 12: 1600,
      13: 1594, 14: 1589, 15: 1584, 16: 1580, 17: 1578, 18: 1572, 19: 1564, 20: 1555, 21: 1547, 22: 1542, 23: 1537, 24: 1527}
# 잉글랜드 3부: 기존 자료 순위값(1위 1611 = '잉글랜드 3부 1999-00 1위', 2위 1583 = 기존 2위 값, 3위 1555)
L1 = {1: 1611, 2: 1583, 3: 1555}

def model(lg, season, r, n):
    if lg == "GB1":
        return pl_value(season, r)
    if lg in ("GB2", "wiki-FootballLeague-FirstDivision(tier2)"):
        assert n == 24
        lab = "챔피언십" if season >= "2004-05" else "잉글랜드 2부"
        return CH[r], f"{lab} {season} {r}위"
    if lg in ("GB3", "wiki-FootballLeague-SecondDivision(tier3)"):
        assert n == 24 and r in L1
        lab = "리그 원(3부)" if season >= "2004-05" else "잉글랜드 3부"
        return L1[r], f"{lab} {season} {r}위"
    return None
RANK_LG = ["GB1", "GB2", "GB3", "wiki-FootballLeague-FirstDivision(tier2)", "wiki-FootballLeague-SecondDivision(tier3)"]

# 순위표로 순위를 확인하고 기존 같은 리그 비슷한 순위 값에 맞춘 직접 추정(모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {
    (key("Celtic FC"), "1997-98"): (1620, "스코틀랜드 1997-98 1위 (추정, 다른 선수 자료 셀틱 2001-02·2003-04 1위 1620과 같음)"),
    (key("1.FC Kosice"), "1998-99"): (1400, "슬로바키아 1998-99 4위 (추정, 다른 선수 자료 슬로바키아 4위 1400과 같음)"),
    (key("Rapid Bucharest"), "2000-01"): (1480, "루마니아 2000-01 4위 (추정, 다른 선수 자료 라피드 부쿠레슈티 2011-12 4위 1480과 같음)"),
    (key("FC Slovan Liberec"), "2000-01"): (1438, "체코 2000-01 6위 (추정, 다른 선수 자료의 체코 1부 6위 1438과 같음)"),
    (key("Spartak Moscow"), "2002"): (1580, "러시아 2002 3위 (추정, 다른 선수 자료 로코모티프 모스크바 2005 3위 1580과 같음)"),
    (key("NK Olimpija Ljubljana"), "2003-04"): (1410, "슬로베니아 2003-04 2위 (추정, 다른 선수 자료 슬로베니아 1위 1420·3위 1400의 가운데)"),
    (key("CD Leganés"), "2004-05"): (1350, "스페인 3부(세군다 B 1조) 2004-05 5위 (추정, 다른 선수 자료 스페인 3부 1350과 같음)"),
}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

EURO = ("CL", "CLQ", "UEFA", "USC")
def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    seasons = [eu, d[:4]] if cid in EURO else [eu]   # 달력 연도 리그(러시아·핀란드)는 경기 연도
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    for s in seasons:
        for lg in RANK_LG:
            t = RANKS.get((lg, s))
            kk = RANK_NAME.get(k, k)
            if t and (k in t or kk in t):
                r, n = t.get(k) or t[kk]
                res = model(lg, s, r, n)
                if res:
                    ELO_SRC["순위표+기존 순위값"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg))
                    return res
    return None

# ---------------------------------------------------------------- 출전
def opp_name(g):
    n = re.sub(r"\s*\(\s*(\d{4}\s*)?-\s*\d{4}\s*\)", "", g["opponent"]).strip()   # 해체 연도 꼬리표 제거
    return n

def ldate(g):
    return g["date_local"]   # Transfermarkt 일정·리포트 날짜(현지). API UTC 스탬프는 94경기가 하루 앞서 안 씀

M = []
for g in GAMES:
    M.append([ldate(g), opp_name(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue                               # 유스(FA 유스컵)·다른 차전
    isg, isa = e["owen_scorer"] == "1", e["owen_assist_other"] == "1"
    if e["owen_self_assist"] == "1":
        judg.append(("도움 아님", g["date_local"], opp_name(g), e["minute"], "본인 PK 골의 본인 도움 표기"))
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
    mi, dm = minute(MIN_FIX.get(tag, e["minute"]))
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout", "golden_goal") and not tie) else 0
    d = ldate(g); opp = opp_name(g)
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        pk = int((e["penalty"] == "1" and e["goal_desc"] == "Penalty") or tag in PK_FIX)
        if e["goal_desc"] == "Penalty rebound": judg.append(("일반 골", d, opp, e["minute"], "PK 리바운드 골(PK 아님)"))
        add_row("g", mi, dm, gf, ga, pk, 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "상대 자책골 유도(" + (e["assist_type"] or "유형 없음") + ")")); continue
        if e["assist_type"] in AUTO_EXCL_TYPES:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], AUTO_EXCL_TYPES[e["assist_type"]])); continue
        if e["goal_desc"] == "Penalty":
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "PK 골(유형 없음)")); continue
        if d >= GAP: sys.exit("2014.8 이후 도움 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k)
        if not x[4].startswith("table"): print(x)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid in sorted(FM_EV):
    if gid not in G: continue
    tg = [e for e in EVENTS if e["gameId"] == gid and e["owen_scorer"] == "1"]
    fg = [r for r in FM_EV[gid] if r["owen_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    ta = [e for e in EVENTS if e["gameId"] == gid and e["owen_assist_other"] == "1"]
    fa = [r for r in FM_EV[gid] if r["owen_assist"] == "1"]
    if not FM_EV[gid] or (not tg and not fg and not ta and not fa): continue
    FM_CMP.append((gid, ldate(G[gid]), "TM 골 " + ",".join(e["minute"] for e in tg), "FM 골 " + ",".join(
        r["time"] + ("+" + r["overloadTime"] if r["overloadTime"] else "") for r in fg),
        "TM 도움 " + ",".join(e["minute"] for e in ta), "FM 도움 " + ",".join(r["time"] for r in fa)))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
DATA = os.path.join(ROOT, "src", "data")
TRACKED = set(os.popen(f"git -C {ROOT} ls-files src/data").read().split())
OTHER = {}
for fn in sorted(os.listdir(DATA)):
    if not fn.endswith(".js") or fn in ("hon.js", "owe.js") or f"src/data/{fn}" not in TRACKED: continue
    t = open(os.path.join(DATA, fn), encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", t, re.S)
    if m: OTHER[fn] = json.loads(m.group(2))
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    return diffs
our_dates = {r[9] for r in E}
for fn, ent in OTHER.items():
    for x in ent:
        if x[0] == "a" and x[13] == "Michael Owen":   # 동료 도움 → 오언 골
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn + " 도움→오언 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":   # 오언 도움 → 동료 골(같은 날 ±3분 골 행이 있는 파일)
            hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and x[1] == r[1]]
            if hit: CROSS.append(("오언 도움→" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:   # 같은 경기 Elo/lv/대회
        if x[9] in our_dates:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "연장"))]
                    if dd: CROSS.append(("같은 경기 다름", fn, r[9], r[1], dd))
                    break
    # 동료 파일의 골인데 Transfermarkt 오언 도움(빠진 것 포함)이 있는 경우
    for x in ent:
        if x[0] != "g": continue
        tm = [e for e in EVENTS if e["owen_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9]
              and abs(minute(e["minute"])[0] - x[4]) <= 2 and key(opp_name(G[e["gameId"]])) == key(x[1])]
        if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
            CROSS.append(("TM 오언 도움을 뺀 동료 골", fn, x[9], x[4], tm[0]["scorer"], tm[0]["assist_type"]))
    # 오언 골에 동료 Transfermarkt 도움이 있는데 동료 파일에 도움이 없는 경우는 동료 파일의 판정이라 기록만
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0].split(" ")[0] + " " + c[0].split(" ")[-1] for c in CROSS))
    for c in CROSS:
        if c[-1] == "같음": print("  같음:", c[:4])

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("livmo", "2004-08-14", "리버풀", "1996~2004"), ("rmmo", "2005-08-31", "레알 마드리드", "2004~2005"),
         ("newmo", "2009-07-03", "뉴캐슬 유나이티드", "2005~2009"), ("munmo", "2012-09-04", "맨체스터 유나이티드", "2009~2012"),
         ("stkmo", None, "스토크 시티", "2012~2013")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != CLUB_ID[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 집계
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
TM_A = sum(1 for e in EVENTS if e["owen_assist_other"] == "1" and e["gameId"] in G)
EXA = collections.Counter(j[5].split("(")[0] for j in judg if j[0] == "도움 제외")
N_UNTYPED = sum(1 for r in E if r[0] == "a" and any(e["gameId"] in G and ldate(G[e["gameId"]]) == r[9] and e["owen_assist_other"] == "1"
                and e["assist_type"] == "" and minute(e["minute"])[0] == r[4] for e in EVENTS))
SRC = ELO_SRC

def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))

NOTE_LINES = [
    f"마이클 오언(리버풀·레알 마드리드·뉴캐슬 유나이티드·맨체스터 유나이티드·스토크 시티)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 윔블던전 ~ {d_(M[-1][0])} 사우샘프턴전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 외 모든 경기), 2010-11 이후 골·도움은 FotMob 경기 이벤트와 대조함. 잉글랜드 대표팀과 리버풀 유스(1996 FA 유스컵 결승 2차전 1골) 경기는 뺌. 2군 경기는 어느 출처에도 없음",
    "경기·골 수는 영어 위키백과 클럽·시즌·대회별 기록(482경기 222골)과 모두 같음. 스페인어 위키백과는 시즌 골·도움이 다른 출처·자기 합계와도 맞지 않아(리버풀 2003-04 23골 등) 쓰지 않음. FotMob 경력 합계는 2009년 이전이 일부 경기만 있어 대조에서 뺌",
    f"골: 상대 자책골·오언 자책골 없음. PK 골 {NPK}개 = Transfermarkt 골 유형 'Penalty'(선수 경기 성적의 PK 골 수와 같음). 2002.11.12 바젤전 85분 골은 PK가 막힌 뒤 리바운드 골이라 일반 골로 셈(Transfermarkt도 PK 골로 세지 않음)",
    "2010-11 이후 골은 FotMob과 스코어·PK가 같음. 2011.9.20 리즈전 두 번째 골은 Transfermarkt 33분·FotMob 32분, 2013.1.19 스완지전 골은 Transfermarkt 90+1분·FotMob 90분(추가시간 없음)이라 Transfermarkt 시각을 씀. FotMob 경기 기록에 골 이벤트가 없는 2011.1.29 사우샘프턴전(FA컵)·2011.5.22 블랙풀전 골은 Transfermarkt만 근거",
    f"도움: 모든 경기가 2014.8.1 이전이라 Transfermarkt 경기 리포트 도움을 씀(2010-11 이전은 다른 경기별 출처가 없음, 다른 선수 선례와 같음). 도움 {NA} = Transfermarkt {TM_A} − PK 유도 {EXA['PK 유도']}(1997.9.22 애스턴 빌라전·1997.12.6 맨유전·1998.9.19 찰턴전·1998.10.27 풀럼전 파울러 PK, 2001.5.16 UEFA컵 결승 매캘리스터 PK, 2004.5.2 미들즈브러전 머피 PK) − 슈팅 리바운드 {EXA['슈팅 리바운드']}(2001.8.8 하카전 히피아, 2003.8.30 에버턴전 큐얼, 2004.10.26 레가네스전 모리엔테스, 'Shot on goal') − 상대 자책골에 준 도움 {EXA['상대 자책골 유도']}(2007.11.3 포츠머스전 솔 캠벨, 2009.10.17 볼턴전 잣 나이트)",
    f"도움 유형 칸이 빈 {N_UNTYPED}개도 일반 도움으로 셈(PK·자책골 표시 없음 확인). Transfermarkt 리포트가 본인 PK 골에 본인 도움으로 적은 2개(1997.11.18 그림즈비전 45분, 1999.1.3 포트 베일전 34분)는 도움이 아님(선수 경기 성적 수치에도 없음)",
    "2010.9.22 스컨소프전 54분 박지성 골 도움은 Transfermarkt만 오언 도움으로 적고 FotMob 경기 이벤트는 도움 없음 — 2014.8 이전 Transfermarkt 도움 규칙대로 넣음. FotMob이 오언에게 준 경기별 도움은 없음(FotMob 2009-10 리그 도움 1은 볼턴전 자책골 유도로 보임). 스페인어 위키백과 시즌 도움(통산 63)은 경기별 근거가 없어 쓰지 않음",
    "날짜는 현지 날짜(Transfermarkt 일정·리포트 날짜; 선수 경기 성적의 옛 시각 94경기는 하루 앞서 있어 쓰지 않음). 골 시각은 Transfermarkt 리포트 기준",
    "출전 분: Transfermarkt 그대로. 1998.4.10 맨유전 40분 퇴장, 연장 경기 6개(1998.1.7 뉴캐슬전 115분, 2000.12.13 풀럼전 46분, 2003.1.21 셰필드 유나이티드전 120분, 2004.11.10 테네리페전 120분, 2005.3.9 유벤투스전 30분, 2008.8.26 코번트리전 45분), 2001.5.16 UEFA컵 결승(알라베스, 연장 골든골 5-4) 77분, 2009.8.9 커뮤니티 실드(첼시, 2-2 뒤 승부차기) 45분",
    "상대 Elo는 같은 경기를 다룬 다른 선수 자료(제라드·라울·호나우두·베컴·시어러·긱스 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위를 기존 리그 순위값에 넣은 값 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+기존 순위값 {SRC['순위표+기존 순위값']}, 직접 추정 {SRC['직접 추정']})",
    "순위표+기존 순위값: 웨스트햄 1998-99(프리미어리그 5위)는 기존 자료에 5위 값이 없어 4위 1775·6위 1747의 가운데 1761(추정). 잉글랜드 2·3부 상대(미들즈브러 1997-98 2부 2위, 그림즈비 1997-98 3부 3위, 포트 베일 1998-99 2부 21위, 풀럼 1998-99 3부 1위, 로더럼 2000-01 3부 2위, 반즐리 2007-08·2009-10 2부 18위, 리즈 2009-10 3부 2위, 스컨소프 2010-11 2부 24위)는 다른 선수 자료의 순위별 고정값. 순위는 Transfermarkt 순위표(2004-05 이후)와 영어 위키백과 시즌 문서(그 이전)",
    "직접 추정(모두 '추정', 순위는 Transfermarkt 순위표·영어 위키백과로 확인): 셀틱 1997-98(스코틀랜드 1위) 1620, 코시체 1998-99(슬로바키아 4위) 1400, 라피드 부쿠레슈티 2000-01(루마니아 4위) 1480, 슬로반 리베레츠 2000-01(체코 6위) 1438, 스파르타크 모스크바 2002(러시아 3위) 1580, 올림피야 류블랴나 2003-04(슬로베니아 2위) 1410, 레가네스 2004-05(스페인 3부 세군다 B 1조 5위) 1350 — 모두 다른 선수 자료의 같은 리그 비슷한 순위 값에 맞춤",
    "대회 비중: FA컵·리그컵·코파 델 레이는 국내컵(FA컵 5라운드·리그컵 16강·코파 델 레이 16강까지 낮은 비중, FA컵 6라운드·리그컵 8강 이후 높은 비중, 재경기는 같은 라운드 단판), 채리티·커뮤니티 실드·UEFA 슈퍼컵은 국내컵 결승, UEFA컵 1라운드는 유로파 예선, UEFA컵 2·3라운드·16강·8강은 유로파 토너먼트, 챔스 2001-02·2002-03 1·2차 조별리그는 챔스 조별로 계산함. 2001 UEFA컵 결승(골든골 연장)은 다른 단판 연장 경기와 같이 계산",
    f"두 경기 합산(UEFA 대회·리그컵 준결승·코파 델 레이 16강) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음, 당시 규칙). 2차전 기록의 1차전 스코어는 Transfermarkt 경기 리포트로 채움(오언이 뛰지 않은 1차전은 2000.10.26 리베레츠전 1-0 하나). 연장 골: 1998.1.7 뉴캐슬전 95분, 2000.12.13 풀럼전 105분, 2008.8.26 코번트리전 97분(모두 단판), 2003.1.21 셰필드 유나이티드전 107분(리그컵 준결승 2차전 연장)",
    "시즌 구분: 모든 클럽 8월 1일 기준(오언의 7월 공식 경기 없음). 클럽 구분은 이적일 기준(레알 마드리드 2004.8.14, 뉴캐슬 2005.8.31, 맨유 2009.7.3, 스토크 2012.9.4). 모든 시즌 소속 팀이 1부(프리미어리그·라리가)",
    "수상 기록은 Transfermarkt 업적 페이지 기준: UEFA컵 2000-01, UEFA 슈퍼컵 2001, 프리미어리그 2010-11, FA컵 2001, 리그컵 3회(2001·2003·2010), 채리티·커뮤니티 실드 2회(2001·2010). 준우승: 챔스 2010-11. 개인: 발롱도르 2001, 프리미어리그 득점왕 2회(1997-98·1998-99, 각 18골 공동), 프리미어리그 올해의 선수 1997-98(리그 사무국), PFA 올해의 팀 1997-98(영어 위키백과 PFA 올해의 팀 목록으로 확인). 2006 인터토토컵(뉴캐슬, 부상으로 불참)·PFA 올해의 젊은 선수·대표팀 기록은 뺌",
]

def build_note(extra):
    note = "\n".join(NOTE_LINES[:16] + extra + NOTE_LINES[16:])
    for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM "]:
        if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", note):
            sys.exit("설명에 작업용 표현: " + bad)
    return note

# 동료 대조 결과 요약 줄
mates = collections.Counter()
for c in CROSS:
    if c[-1] == "같음":
        mates[c[0]] += 1
NOTE = build_note([])

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
    gs = sorted({(r[5], r[6], r[4]) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
    for a, b in zip(gs, gs[1:]):
        if b[0] < a[0] or b[1] < a[1]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[0] == "a" and r[13] == "Michael Owen": problems.append(("본인 도움", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if r[4] > 90 and not r[11] and not r[10] and len(r) <= 14: problems.append(("정규시간 90분 초과", r))
mm = {m[0]: m for m in M}
for r in E:
    m = mm.get(r[9])
    if m and m[1] != r[1]: problems.append(("상대 이름 다름", r[9], r[1], m[1]))
    if m and m[2] != r[3]: problems.append(("대회 다름", r[9], r[3], m[2]))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and (len(sys.argv) == 1 or "--out" in sys.argv):
    open(OUT_JS, "w", encoding="utf-8").write(f"const OWE_E={J(E)};\nconst OWE_M={J(M)};\nconst OWE_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_compare": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
