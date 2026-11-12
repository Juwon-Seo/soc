#!/usr/bin/env python3
"""Zinedine Pavel Nedved: raw/ -> nedved.json + src/data/ned.js (판정 근거는 judgments.md)

  python3 players/nedved/build_nedved.py            # 파일 쓰기
  python3 players/nedved/build_nedved.py --debug    # Elo 출처 목록
  python3 players/nedved/build_nedved.py --cross    # 동료(델 피에로·앙리·판니스텔로이) 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/del.js·hen.js·nis.js.
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다. 델 피에로 build 스크립트를 바탕으로 함.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "ned.js")
OUT_JSON = os.path.join(HERE, "nedved.json")
ME = "파벨 네드베드"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 판정 표
# 날짜: TM 리포트 날짜(현지) 그대로(API 날짜는 13경기에서 하루 앞섬)
DATE_FIX = {}
# 골 제외(Transfermarkt 리포트 골이지만 넣지 않음) — 자책골은 코드에서 자동 제외
EXCL_G = {}
# 도움 제외: gameId|분 -> 이유 (아래 AUTO_EXCL 유형은 코드가 확인해서 제외하고, 여기에는 유형 밖 제외만 둔다)
EXCL_A = {}
# 도움 유형으로 자동 제외: PK 유도, 슈팅 리바운드, 상대 자책골(own_goal=1)
AUTO_EXCL_TYPES = ("Penalty: Fouled player", "Shot on goal")
INCOMPLETE = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "TS1"}
CUPS = {"CIT", "TSP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"           # 1~3라운드·16강(Round of 16 / Last 16)
    if cid in ("SCI", "USC"): return "df"
    if cid == "ITC": return "elq"       # 인터토토컵 = 유로파 예선(램파드·비야·델 피에로·지단 선례)
    if cid == "UEQ": return "elq"       # UEFA컵 예선 라운드
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("first round") or r.startswith("second round"): return "clq"   # 1993-94 본선 1·2라운드(조별 전 토너먼트) = 챔스 예선 비중(기그스 선례)
        if r.startswith("group"): return "clg"   # 1999-2003 2차 조별도 조별
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid in ("UEFA", "EPP"):
        if cid == "UEFA" and r.startswith("first round"): return "elq"   # UEFA컵 1라운드 = 유로파 예선
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 컵위너스컵(호나우두 선례: 1라운드 포함 elk)·UEFA컵 2라운드 이후
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
    # 원정 다득점·연장: UEFA 대회(2020-21까지)·코파 이탈리아(2021-22까지) 모두 해당 기간
    return [leg, home, fu, ft, 1, 1]

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
    "bohemians praha": "fc bohemians praha", "bohemians prague": "fc bohemians praha",
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

# 순위표(Transfermarkt): (리그, 시즌) -> {key: (순위, 팀 수)}
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

# 리그1(디비지옹 1) 20팀: 기존 자료의 20팀 순위값(2002-03~2022-23 lv, 시즌 간 같은 값, 20칸 모두 있음)
L1_20 = {1: 1955, 2: 1872, 3: 1825, 4: 1792, 5: 1776, 6: 1764, 7: 1750, 8: 1733, 9: 1715, 10: 1699,
         11: 1688, 12: 1679, 13: 1669, 14: 1664, 15: 1655, 16: 1640, 17: 1621, 18: 1610, 19: 1602, 20: 1582}
# 세리에A 18팀(1993-94~2003-04): 델 피에로·토티 자료와 같은 값(7·9·12·16위는 앞뒤 값의 가운데)
SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 7: 1762, 8: 1743, 9: 1728, 10: 1713, 11: 1704, 12: 1697,
        13: 1690, 14: 1676, 15: 1657, 16: 1645, 17: 1633, 18: 1614}
# 리그2(디비지옹 2) 평균 1540·2부 흩어짐 51.24 × 표준 곡선(문서 4절 '프랑스 2부'); 1990년대 2부는 두 조라 조 순위를 조 팀 수 곡선에 넣음
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

def mid_fill(m, r):
    """기존 순위값에 없는 순위: 앞뒤 순위 값의 가운데"""
    lo = max([k for k in m if k < r], default=None); hi = min([k for k in m if k > r], default=None)
    if lo is None or hi is None: return None
    return int(m[lo] + (m[hi] - m[lo]) * (r - lo) / (hi - lo) + 0.5)

# 세리에B 2006-07(22팀): 같은 22팀 시즌(2006-07·2011-12·2013-14)의 기존 순위값 합집합, 빈 순위(1·10위)는 앞뒤 값의 가운데
def serieb_map():
    m = {}
    for s in ("2011-12", "2013-14", "2006-07"):
        m.update(ents_map("세리에B", s))
    return m

# 체코 1부(체코슬로바키아 1992-93·체코 1993~96, 16팀): 기존 체코 팀-시즌 값에 맞춘 추정 — 1위 1500(슬라비아 1995-96 1위 1500, 리베레츠 2001-02 1위 1500),
# 9위 1400(테플리체 2003-04 9위 1400)을 이은 직선, 16위까지 같은 기울기로 연장(1위 1500 → 9위 1400 → 16위 약 1312). 순위 간격 12.5.
def czech(r, n):
    return int(round(1500 - 12.5 * (r - 1) * 15 / (n - 1)))

def model(lg, season, r, n):
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        if n == 18:
            return SA18[r], f"세리에A {season} {r}위"
        v = mid_fill(m, r)
        if v: return v, f"세리에A {season} {r}위"
        return None
    if lg == "IT2":
        m = serieb_map()
        if n == 22:
            if r in m: return m[r], f"세리에B {season} {r}위"
            v = mid_fill(m, r)
            if v: return v, f"세리에B {season} {r}위"
        return None
    if lg == "TS1":
        return czech(r, n), f"체코 {season} {r}위 (추정)"
    return None

RANK_LG = ["IT1", "IT2", "TS1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv) — 골·도움 상대만 필요
MAN = {}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    euro = cid in ("CL", "CLQ", "UEFA", "UI", "WEPO", "USC")
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if euro else [eu]
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
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, 0, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["nedved_scorer"] == "1", e["nedved_assist_other"] == "1", e["nedved_self_assist"] == "1"
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
    if gid in INCOMPLETE: judg.append(("리포트 불완전", d, opp, e["minute"], INCOMPLETE[gid]))
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골(지단이 자기 골문에 넣은 골)")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1":
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "상대 자책골에 준 도움")); continue
        if not ours: sys.exit("상대 득점 도움 이상 " + tag)
        if e["assist_type"] in AUTO_EXCL_TYPES:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "PK 유도" if e["assist_type"].startswith("Penalty") else "슈팅 리바운드(Shot on goal)")); continue
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
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

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Alessandro Del Piero": ("del.js", "DEL", "1996-07-01", "2001-07-01"),
         "Thierry Henry": ("hen.js", "HEN", "1999-01-01", "1999-08-01"),
         "Ruud van Nistelrooy": ("nis.js", "NIS", "2006-07-01", "2006-07-01")}
CROSS = []
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
for nm, (fn, P, lo, hi) in MATES.items():
    ent = load_js(fn, P)
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("지단 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and x[13] == "Pavel Nedved":
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→지단 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    # 같은 경기(같은 날짜·상대) 다른 항목 — 상대 Elo·lv·대회·합산
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    CROSS.append(("같은 경기", nm, r[9], r[1], d or "같음"))
                    break
    # TM이 지단 도움으로 적었지만 뺀 동료 골 / 동료 도움이 동료 파일에 없는 지단 골
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["nedved_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 지단 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:
        if e["nedved_scorer"] == "1" and e["own_goal"] != "1" and norm(e["assist_player"]) == norm(nm) and e["gameId"] in G:
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움이 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("canzd", "1992-07-01", "AS 칸", "1988~1992"), ("borzd", "1996-07-01", "보르도", "1992~1996"),
         ("juvzd", "2001-07-01", "유벤투스", "1996~2001"), ("rmzd", None, "레알 마드리드", "2001~2006")]
TM_CLUB = {"895": "canzd", "40": "borzd", "506": "juvzd", "418": "rmzd"}
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NOTE_LINES = [
    f"지네딘 지단(AS 칸·보르도·유벤투스·레알 마드리드)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 낭트전 ~ {d_(M[-1][0])} 세비야전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·프랑스 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]}({y}) {c3(ST[k])}" for k, u, n, y in CLUBS)
    + f". 출전 분 합계 {MIN_TOT:,}분(Transfermarkt 기록, 90분으로 추정한 경기 없음)",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(출전한 689경기 전부). 경기 수·골은 프랑스어 위키백과 클럽·시즌·대회별 기록과 모두 같음(칸 71·6, 보르도 179·39, 유벤투스 212·31, 레알 마드리드 227·49; 영어 위키백과는 수페르코파를 두 칸에 겹쳐 세어 유벤투스 214·레알 230으로 적음). FotMob에는 지단의 클럽 경기별 자료가 없어 골 시각은 Transfermarkt만 근거(결승 경기는 영어 위키백과 경기 문서와 같거나 1분 차이). 칸 2군(프랑스 3·4부, 1987~90) 경기는 넣지 않음",
    "골: Transfermarkt 리포트 골 125개를 모두 씀. PK 골 5개는 Transfermarkt 골 유형 'Penalty' 기준(선수 경기 성적의 PK 골 수와 같음). 지단이 자기 골문에 넣은 자책골 2개(1997.5.18 파르마전 29분, 1999.11.21 밀란전 21분)는 골이 아님",
    f"도움: 모두 Transfermarkt 경기 리포트 도움(2014년 이전이라 단일 출처, 경기마다 다른 출처로 대조하지 못함). 도움 {NA} = Transfermarkt 리포트 145 − PK 유도 5(1997.9.17 페예노르트전·1998.4.1 모나코전 델 피에로, 2001.12.15 레알 소시에다드전·2004.11.7 말라가전 피구, 2002.3.9 비야레알전 이에로) − 슈팅 리바운드('Shot on goal') 3(2001.12.18 타라고나전 라울, 2004.2.1 바야돌리드전 호나우두, 2005.5.28 사라고사전 오언) − 상대 자책골에 준 도움 3(1997.9.21 브레시아전 필리피니, 2000.4.9 볼로냐전·2001.2.3 아탈란타전 파가닌). 유형 칸이 빈 도움 20개는 일반 도움으로 셈. Transfermarkt 리포트가 지단 PK 골에 동료 이름을 도움 칸('PK 유도')에 적은 것은 지단 골의 정보일 뿐 지단 도움이 아님",
    "도움 자료의 공백: Transfermarkt 리포트에는 칸 시절(1988~92)과 보르도 1992-93의 지단 도움이 하나도 없고, 보르도 1993~96도 24개뿐임. 프랑스어·스페인어 위키백과는 시즌 합계로 칸 1990-91 6·1991-92 10, 보르도 1992-93 2·1993-94 7·1994-95 9·1995-96 18개를 적었으나 어느 경기의 도움인지 알 수 없어 넣지 않음 — 이 때문에 칸·보르도 시절 도움은 실제보다 적음(위키백과 기준 약 28개 차이). 유벤투스·레알 마드리드 시즌 도움은 위키백과와 0~2개 차이",
    "Transfermarkt 리포트의 골 목록이 불완전한 쿠프 드 프랑스 경기: 1995.1.14 US 포르바크전(4-2 승)은 상대 두 골(후반)의 시각이 없어 지단의 81분 도움 직전 스코어를 리포트 순서대로 2-0으로 둠(실제로는 2-1이나 2-2였을 수 있음), 1995.2.4 스타드 몽투아전(2-1 승)은 상대 골(후반) 시각이 없어 지단 79분 골 직전 스코어를 1-0으로 둠(1-1이었을 수 있음). 경기 기사를 찾지 못해 확인 못 함. 1992.2.23 세트전·1996.1.13 퐁드로이드전도 상대 골이 빠졌지만 지단 골·도움이 없어 영향 없음",
    "1998.4.1 챔스 준결승 1차전 모나코전(4-1): Transfermarkt가 전반 추가시간의 동점골(1-1)과 델 피에로 PK 골(2-1) 순서를 바꿔 적었으나 지단 기록(88분 골, 골 전 3-1)에는 영향 없음. 이 경기 PK를 얻어낸 것은 도움이 아님(델 피에로 자료와 같음)",
    "날짜는 경기 현지 날짜(Transfermarkt 리포트 날짜; 선수 경기 성적의 날짜는 킥오프 시각이 없는 프랑스 경기 등 171경기에서 하루 앞섬). 1996 인터콘티넨털컵 리버 플레이트전(도쿄)은 영어 위키백과가 1996.11.26(현지)로 적었으나 같은 경기의 델 피에로 자료와 맞춰 Transfermarkt 날짜 1996.11.27로 둠",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "디비지옹 1(1989~96, 20팀)은 다른 선수 자료의 리그1 20팀 순위값(1위 1955 ~ 20위 1582)을 그대로 씀. 세리에A 18팀 시즌(1996~2001)은 다른 선수 자료의 18팀 순위값(자료에 없는 7·9·12·16위는 앞뒤 순위 값의 가운데, 델 피에로·토티 자료와 같음). 라리가 2001-02~2005-06은 같은 시즌 다른 선수 자료 순위값을 쓰고 빈 순위는 앞뒤 값의 가운데, 2001-02 20위(사라고사)는 2003-04 순위값을 같은 시즌 수준으로 옮긴 추정. 라리가 1995-96(22팀, 베티스)은 델 피에로 자료와 같은 추정(1999-00 리그 수준에 순위 보간), 분데스리가 1993-94·1995-96(카를스루에·프랑크푸르트)은 2000-01 순위값, 에레디비시 1996-97(아약스 4위)은 다른 선수 자료 순위값. 디비지옹 2 1992-93(뮐루즈, 쿠프 드 프랑스)은 프랑스 2부 모형(평균 1540)에 조 순위를 넣은 추정",
    "직접 추정(모두 '추정', 다른 선수 자료의 같은 팀·나라 값 기준): 보헤미안(더블린) 1993·1995 1300, 릴레스트룀 1994 1480, 노르셰핑 1995 1450, 오덴세 1995 1480, 로센보리 1996·1998 1530, 올림피아코스 1998-99 1690, 레프스키 소피아 1999 1480, 스파르타 프라하 2001 1520, AEK 아테네 2002 1550, 툴롱(프랑스 3부) 1995-96 1311, US 포르바크·스타드 몽투아(프랑스 4부 이하 아마추어) 1994-95 1250",
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·코파 이탈리아·코파 델 레이는 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), 수페르코파 이탈리아나·수페르코파(스페인, 두 경기)·UEFA 슈퍼컵(1996-97 두 경기, 2002 단판)은 국내컵 결승, 인터콘티넨털컵(1996·2002)은 클럽 월드컵, UEFA컵 1라운드와 인터토토컵(1995 조별·16강·준결승·결승, 1999 결승)은 유로파 예선, UEFA컵 2라운드 이후는 유로파 토너먼트(1996 결승 2차전 바이에른전 포함), 챔스 2차 조별(1999-2000~2002-03)은 조별로 계산함",
    f"두 경기 합산(챔스·UEFA컵·인터토토컵 결승·UEFA 슈퍼컵 1996-97·코파 이탈리아·코파 델 레이·수페르코파) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음). 지단이 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움(2001.12.18 코파 델 레이 16강 2차전 타라고나전의 1차전 원정 0-1, 2004.1.28 코파 델 레이 8강 2차전 발렌시아전의 1차전 홈 3-0 등)",
    "시즌 구분: 칸·보르도·유벤투스는 7월 시작 경기를 새 시즌으로 셈(디비지옹 1이 7월 중순에 개막, 보르도 1995 인터토토컵 조별 7.1·7.8 경기도 1995-96), 레알 마드리드는 기본 8월 1일. 클럽 구분은 1992.7.1 전 칸, 1996.7.1 전 보르도, 2001.7.1 전 유벤투스, 이후 레알 마드리드",
    "동료 자료 대조: 알레산드로 델 피에로 자료(유벤투스 1996~2001)와 같은 경기 41경기의 대회·상대 Elo·합산 정보가 모두 같고, 지단 도움→델 피에로 골 12개·델 피에로 도움→지단 골 4개의 날짜·분·스코어가 같음. 지단이 얻어낸 델 피에로 PK 2개(1997.9.17·1998.4.1)는 양쪽 모두 도움에서 뺌",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 챔스 2001-02, 세리에A 1996-97·1997-98, 라리가 2002-03, UEFA 슈퍼컵 1996-97·2002-03, 인터콘티넨털컵 1996·2002, 수페르코파 이탈리아나 1997-98, 수페르코파 2001-02·2003-04, 인터토토컵 1995·1999. 준우승은 챔스 결승 2회(1996-97·1997-98)와 UEFA컵 1995-96. 개인: 발롱도르 1998, FIFA 올해의 선수 3회(1998·2000·2003), UEFA 올해의 선수 2002, 올해의 선수 3회(1998·2001·2002), 디비지옹 1 올해의 선수 1995-96. 월드컵·유로 등 대표팀 기록은 뺌",
    "은퇴: 2006 월드컵 뒤 은퇴(마지막 클럽 경기 2006.5.16 세비야전)",
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

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const NED_E={J(E)};\nconst NED_M={J(M)};\nconst NED_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
