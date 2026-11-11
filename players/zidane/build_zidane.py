#!/usr/bin/env python3
"""Zinedine Zidane: raw/ -> zidane.json + src/data/zid.js (판정 근거는 judgments.md)

  python3 players/zidane/build_zidane.py            # 파일 쓰기
  python3 players/zidane/build_zidane.py --debug    # Elo 출처 목록
  python3 players/zidane/build_zidane.py --cross    # 동료(델 피에로·앙리·판니스텔로이) 자료 대조

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
OUT_JS = os.path.join(ROOT, "src", "data", "zid.js")
OUT_JSON = os.path.join(HERE, "zidane.json")
ME = "지네딘 지단"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 판정 표
# 날짜: TM 리포트 날짜(현지)를 쓰되, 1996 인터콘티넨털컵은 델 피에로 자료(1996-11-27)와 같게 둠(도쿄 현지 11.26 — judgments.md)
DATE_FIX = {}
# 골 제외(Transfermarkt 리포트 골이지만 넣지 않음) — 자책골 2개는 코드에서 자동 제외
EXCL_G = {}
# 도움 제외: gameId|분 -> 이유
EXCL_A = {
    "1069353|11": "PK 유도(델 피에로 PK)",
    "1069417|45": "PK 유도(델 피에로 PK)",
    "1089641|78": "PK 유도(피구 PK)",
    "1089772|59": "PK 유도(이에로 PK)",
    "27969|24": "PK 유도(피구 PK)",
    "2423395|45": "슈팅 리바운드(Shot on goal, 라울)",
    "28271|25": "슈팅 리바운드(Shot on goal, 오언)",
    "4528|48": "슈팅 리바운드(Shot on goal, 호나우두 — 골 유형도 굴절 슈팅)",
    "2214543|7": "상대 자책골(필리피니)",
    "2217412|73": "상대 자책골(파가닌)",
    "2211543|90+4": "상대 자책골(파가닌)",
}
# 리포트 골 목록이 불완전한 경기(쿠프 드 프랑스, 상대 골 누락): 지단 기록의 골 전 스코어는 리포트 순서 그대로(judgments.md)
INCOMPLETE = {
    "3150174": "1995.2.4 쿠프 드 프랑스 스타드 몽투아전(1-2): 리포트에 홈 골(후반) 시각이 없음 — 지단 79분 골 전 스코어를 리포트 순서대로 1-0으로 둠(홈 골이 79분 전이면 1-1)",
    "3931039": "1995.1.14 쿠프 드 프랑스 US 포르바크전(2-4): 리포트에 홈 두 골(모두 후반) 시각이 없음 — 지단 81분 도움 전 스코어를 리포트 순서대로 2-0으로 둠(실제 2-0·2-1·2-2 중 하나)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "IT1", "ES1"}
CUPS = {"FRC", "FRL", "CIT", "CDR"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SCI", "SUC", "USC"): return "df"
    if cid == "WEPO": return "cwc"
    if cid == "UI": return "elq"       # 인터토토컵 = 유로파 예선(램파드·비야·델 피에로 선례, 조별·결승 포함)
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 1999-2003 2차 조별도 조별
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드 = 유로파 예선
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 2라운드·16강(3라운드)·8강
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
    # 원정 다득점·연장: UEFA 대회(2020-21까지), 코파 이탈리아(2021-22까지), 코파 델 레이·수페르코파(2018-19까지) 모두 해당 기간
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
    return int(round(m[lo] + (m[hi] - m[lo]) * (r - lo) / (hi - lo)))

def model(lg, season, r, n):
    if lg == "FR1":
        m = ents_map("리그1", season)
        if r in m: return m[r], f"리그1 {season} {r}위"
        assert n == 20, (season, n)
        return L1_20[r], f"리그1 {season} {r}위"
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        assert n == 18, (season, n)
        return SA18[r], f"세리에A {season} {r}위"
    if lg == "ES1":
        m = ents_map("라리가", season)
        if r in m: return m[r], f"라리가 {season} {r}위"
        v = mid_fill(m, r)
        if v: return v, f"라리가 {season} {r}위"
        return None
    if lg == "FR2":
        return int(round(1540 + 51.24 * curve(r, n))), f"리그2 {season} {r}위/{n}팀 (추정: 프랑스 2부 모형, 두 조 시절 조 순위)"
    return None

RANK_LG = ["FR1", "IT1", "ES1", "FR2"]

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
    isg, isa, iss = e["zidane_scorer"] == "1", e["zidane_assist_other"] == "1", e["zidane_self_assist"] == "1"
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
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal"):
            sys.exit("도움 유형 판정 누락 " + tag)
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
