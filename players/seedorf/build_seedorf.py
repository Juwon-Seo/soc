#!/usr/bin/env python3
"""Clarence Seedorf: raw/ -> seedorf.json + src/data/see.js (판정 근거는 judgments.md)

  python3 players/seedorf/build_seedorf.py            # 파일 쓰기
  python3 players/seedorf/build_seedorf.py --debug    # Elo 출처 목록
  python3 players/seedorf/build_seedorf.py --cross    # 동료 자료 대조
지단 build 스크립트를 바탕으로 함.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "see.js")
OUT_JSON = os.path.join(HERE, "seedorf.json")
ME = "클라렌스 세도르프"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]   # 밀란 프리마베라 유스 경기 제외
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 판정 표
DATE_FIX = {}
EXCL_G = {}
EXCL_A = {
    "984856|64": "슈팅 리바운드(Shot on goal, 라울)",
}
INCOMPLETE = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"NL1", "IT1", "ES1", "BRA1"}
CUPS = {"NLP", "CIT", "CDR", "BRC"}
STATE = {"BRCG", "BRCR"}     # 카리오카 타사 과나바라·타사 히우: 국내컵 비중(네이마르·루카스 모우라 파울리스타 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SCI", "SUC", "USC", "NLSC"): return "df"
    if cid in ("WEPO", "KLUB"): return "cwc"
    if cid == "CLQ": return "clq"
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
    if cid == "EPP":
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "CS":
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        if r.startswith("quarter"): return "csak"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["competitionId"] in STATE and (g["round"].lower().endswith("matchday") or g["round"].lower().startswith("group")): return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_rule(g):
    cid = g["competitionId"]; d = g["date_local_tm_report"]
    if cid in ("CS",): return (1, 0)                    # 수다메리카나 2012: 원정 다득점, 연장 없이 승부차기(루카스 모우라 2012 선례)
    if cid in ("BRC",): return (0, 0)                   # 코파 두 브라질: 원정 다득점·연장 없음 규칙 문서(브라질)
    return (1, 1)                                       # UEFA·코파 이탈리아(~2021-22)·코파 델 레이(~2018-19)·수페르코파(~2018-19)

def tie_of(g):
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
    ag, et = tie_rule(g)
    return [leg, home, fu, ft, ag, et]

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
MANUAL_ALIAS = {
    "inter milan": "inter", "ac parma": "parma calcio 1913", "parma ac": "parma calcio 1913",
}
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
        RANKS[(p[0].split("(")[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위(?: \(리그 수준 추정\))?$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

def mid_fill(m, r):
    lo = max([k for k in m if k < r], default=None); hi = min([k for k in m if k > r], default=None)
    if lo is None or hi is None: return None
    return int(m[lo] + (m[hi] - m[lo]) * (r - lo) / (hi - lo) + 0.5)

# 세리에A 18팀(1993-94~2003-04): 델 피에로·토티·지단 자료와 같은 값
SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 7: 1762, 8: 1743, 9: 1728, 10: 1713, 11: 1704, 12: 1697,
        13: 1690, 14: 1676, 15: 1657, 16: 1645, 17: 1633, 18: 1614}
# 에레디비시 18팀: 기존 자료 순위값(시즌 간 같음)
ERE = {1: 1837, 2: 1735, 3: 1677, 4: 1642, 5: 1624, 6: 1608, 7: 1587, 8: 1563, 9: 1542, 10: 1528, 11: 1516, 12: 1504,
       13: 1499, 14: 1482, 15: 1459, 16: 1441, 17: 1430, 18: 1406}
def br1_union():
    c = collections.defaultdict(collections.Counter)
    for e in ENTS:
        m = re.match(r"^브라질 세리에 A (\d{4}) (\d+)위$", e["lv"] or "")
        if m and 2009 <= int(m.group(1)) <= 2013 and int(m.group(2)) <= 20: c[int(m.group(2))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
BR1U = br1_union()

def model(lg, season, r, n):
    if lg == "NL1":
        m = ents_map("에레디비시", season)
        return m.get(r, ERE[r]), f"에레디비시 {season} {r}위"
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        v = mid_fill(m, r) if n == 20 else None
        if v: return v, f"세리에A {season} {r}위"
        assert n == 18, (season, n, r)
        return SA18[r], f"세리에A {season} {r}위"
    if lg == "ES1":
        m = ents_map("라리가", season)
        if r in m: return m[r], f"라리가 {season} {r}위"
        v = mid_fill(m, r)
        if v: return v, f"라리가 {season} {r}위"
        return None
    if lg == "IT2":   # 세리에B 22팀: 2006-07·2011-12 기존 순위값(시즌 간 같음), 빈 순위는 앞뒤 가운데
        m = {}
        for ss in ("2011-12", "2006-07"): m.update(ents_map("세리에B", ss))
        v = m.get(r) or mid_fill(m, r)
        if v and n == 22: return v, f"세리에B {season} {r}위"
        return None
    if lg == "BRA1":
        m = ents_map("브라질 세리에 A", season)
        v = m.get(r, BR1U.get(r))
        if v: return v, f"브라질 세리에 A {season} {r}위"
        return None
    return None

RANK_LG = ["NL1", "IT1", "IT2", "ES1", "BRA1"]

MAN = {}
def M_(name, season, elo, lv): MAN[(key(name), season)] = (elo, lv)
exec(open(os.path.join(HERE, "man_seedorf.py"), encoding="utf-8").read()) if os.path.exists(os.path.join(HERE, "man_seedorf.py")) else None

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

CAL = {"BRA1", "BRC", "CS", "BRCG", "BRCR"}
def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    cal = cid in CAL
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    euro = cid in ("CL", "CLQ", "UEFA", "EPP", "WEPO", "USC", "KLUB", "SUC")
    if cal: seasons = [d[:4]]
    elif euro: seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)]
    else: seasons = [eu]
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
            if t and k in t:
                r, n = t[k]
                res = model(lg, s, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg))
                    return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    if g["club_id"] == "537" and g["date_local_brazil_from_api_utc"]: return g["date_local_brazil_from_api_utc"]
    return DATE_FIX.get(g["gameId"], g["date_local_tm_report"])

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid, d)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, 0, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["seedorf_scorer"] == "1", e["seedorf_assist_other"] == "1", e["seedorf_self_assist"] == "1"
    if iss: judg.append(("본인 골의 본인 도움(도움 아님)", g["date_local_tm_report"], e["minute"]))
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
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal"):
            sys.exit("도움 유형 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[3]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("ajxse", "1995-07-01", "아약스", "1992~1995"), ("sampse", "1996-07-01", "삼프도리아", "1995~1996"),
         ("rmse", "2000-01-01", "레알 마드리드", "1996~1999"), ("intse", "2002-07-01", "인터 밀란", "2000~2002"),
         ("acmse", "2012-07-01", "AC 밀란", "2002~2012"), ("botse", None, "보타포구", "2012~2013")]
TM_CLUB = {"610": "ajxse", "1038": "sampse", "418": "rmse", "46": "intse", "5": "acmse", "537": "botse"}
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})

NOTE = ""
if os.path.exists(os.path.join(HERE, "note_seedorf.py")):
    exec(open(os.path.join(HERE, "note_seedorf.py"), encoding="utf-8").read())
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
    gs = sorted({(r[5], r[6], r[4]) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
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
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 동료 대조
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    return json.loads(re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S).group(1))
MATES = {"Raúl": ("rau.js", "RAU"), "Kaká": ("kak.js", "KAK"), "Ronaldinho": ("rdg.js", "RDG"), "Zlatan Ibrahimović": ("ibr.js", "IBR"),
         "Andriy Shevchenko": ("she.js", "SHE"), "Ronaldo": ("rno.js", "RNO"), "Filippo Inzaghi": None, "Alessandro Nesta": None}
def cmp_rows(a, b):
    diffs = []
    if len(a) <= 14 and len(b) > 14 and not b[14]: b = b[:14]
    if len(b) <= 14 and len(a) > 14 and not a[14]: a = a[:14]
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    return diffs
NAMES = {"RAU": "Raúl", "KAK": "Kaká", "RDG": "Ronaldinho", "IBR": "Zlatan Ibrahimović", "SHE": "Andriy Shevchenko", "RNO": "Ronaldo"}
CROSS = []
for fn in sorted(os.listdir(os.path.join(ROOT, "src", "data"))):
    if fn in ("hon.js", "see.js") or not fn.endswith(".js"): continue
    P = fn[:-3].upper()
    try: ent = load_js(fn, P)
    except Exception: continue
    # 1) 같은 경기(날짜·상대) 항목 대회·Elo·lv·합산 비교 — 세도르프 출전일만
    for x in ent:
        if x[9] in mdates and mm.get(x[9]) and key(mm[x[9]][1]) == key(x[1]):
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    CROSS.append(("같은 경기", P, r[9], r[1], d or "같음")); break
    # 2) 도움 상호 (득점자 이름이 알려진 동료만 이름으로 짝지음)
    nm = NAMES.get(P)
    for r in E:
        if r[0] == "a" and r[13]:
            for x in ent:
                if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1]):
                    if nm and norm(nm) != norm(r[13]): continue
                    CROSS.append(("세도르프 도움→" + P + " 골" + ("" if nm else "(이름 미확인)"), r[9], r[4], r[13], cmp_rows(r, x) or "같음"))
    for x in ent:
        if x[0] == "a" and "Seedorf" in str(x[13]):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3]
            CROSS.append((P + " 도움→세도르프 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0].split("→")[0] if "→" in c[0] else c[0], c[-1] == "같음") for c in CROSS))
    print([c for c in CROSS if c[0] != "같은 경기" and c[-1] == "같음"].__len__(), "도움 관련 같음")

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const SEE_E={J(E)};\nconst SEE_M={J(M)};\nconst SEE_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
