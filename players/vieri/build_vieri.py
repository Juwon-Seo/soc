#!/usr/bin/env python3
"""Christian Vieri: raw/ -> vieri.json + src/data/vie.js (판정 근거는 judgments.md)

  python3 players/vieri/build_vieri.py            # 파일 쓰기
  python3 players/vieri/build_vieri.py --debug    # Elo 출처 목록
  python3 players/vieri/build_vieri.py --cross    # 동료(델 피에로·지단·네드베드·호나우두·세도르프·셰브첸코·카카·인자기) 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/ranks.txt(순위표),
      <ROOT>/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(동료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다. 지단 build 스크립트를 바탕으로 함.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "vie.js")
OUT_JSON = os.path.join(HERE, "vieri.json")
ME = "크리스티안 비에리"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 판정 표
# 출전 분 고침: 없음. 1022661(2003.4.19 브레시아전) API 18분 = 리포트 46분 교체 투입 → 63분 퇴장(난투, 빌리카와 함께)과 맞음(judgments.md 2절)
MIN_FIX = {}
# 골 제외(Transfermarkt 리포트 골이지만 넣지 않음) — 없음(자책골 0)
EXCL_G = {}
# 도움 제외: gameId|분 -> 이유
EXCL_A = {
    "2214935|64": "PK 유도(델 피에로 PK)",
    "2215004|37": "PK 유도(델 피에로 PK)",
    "2215023|62": "PK 유도(파도바노 PK)",
    "2215107|39": "PK 유도(아모루소 PK)",
    "2214400|39": "슈팅 리바운드(Shot on goal, 콘세이상)",
    "2217366|65": "슈팅 리바운드(Shot on goal, 세도르프)",
    "2208611|25": "상대 자책골(페르난두 쿠투)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "ES1", "FR1", "ITPO"}   # ITPO = 2000.5.23 세리에A 챔스 진출 플레이오프(단판, 리그 비중 — 인자기·호나우두 선례)
CUPS = {"CIT", "CDR", "FRL"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 1·2라운드·16강(재경기 포함)
    if cid == "USC": return "df"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 2002-03 2차 조별(Group 1) 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid in ("UEFA", "EPP"):   # EPP = 컵위너스컵(네드베드 자료와 같게 UEFA컵 단계 코드)
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드 = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 2·3라운드·32강(intermediate stage)·16강·8강
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
    # 원정 다득점·연장: UEFA 대회(2020-21까지)·코파 이탈리아(2021-22까지)·코파 델 레이(2018-19까지) 모두 해당 기간
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
MANUAL_ALIAS = {"inter milan": "inter", "sp ars et labor": "spal"}
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

# 순위표(Transfermarkt, judgments.md 7절에서 위키백과 최종 순위와 대조): (리그, 시즌) -> {key: (순위, 팀 수)}
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))
# Transfermarkt 순서와 영어 위키백과 최종 순위가 다른 곳(동률): 위키백과 순위를 씀(v1.157 순위 대조 규칙, judgments.md 7절)
RANK_FIX = {("IT1", "1991-92", "SS Lazio"): 10,      # 34점 동률, 위키백과 10위 라치오·11위 아탈란타(TM은 반대)
            ("IT2", "1993-94", "Vicenza Calcio"): 10}  # 37점 4팀 공동 10위(위키백과), TM 12위
for (lg, se, nm), r in RANK_FIX.items():
    k = key(nm); RANKS[(lg, se)][k] = (r, RANKS[(lg, se)][k][1])

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
SB_MEAN = 1577.78   # 세리에B 평균(문서 4절, 인자기·델 피에로 자료와 같은 모형)
# 세리에A 18팀(1988-89~2003-04): 델 피에로·토티·인자기·지단 자료와 같은 값(7·9·12·16위는 앞뒤 값의 가운데)
SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 7: 1762, 8: 1743, 9: 1728, 10: 1713, 11: 1704, 12: 1697,
        13: 1690, 14: 1676, 15: 1657, 16: 1645, 17: 1633, 18: 1614}
# 리그1 20팀: 지단 자료와 같은 기존 순위값
L1_20 = {1: 1955, 2: 1872, 3: 1825, 4: 1792, 5: 1776, 6: 1764, 7: 1750, 8: 1733, 9: 1715, 10: 1699,
         11: 1688, 12: 1679, 13: 1669, 14: 1664, 15: 1655, 16: 1640, 17: 1621, 18: 1610, 19: 1602, 20: 1582}

def mid_fill(m, r):
    """기존 순위값에 없는 순위: 앞뒤 순위 값의 가운데"""
    lo = max([k for k in m if k < r], default=None); hi = min([k for k in m if k > r], default=None)
    if lo is None or hi is None: return None
    return int(m[lo] + (m[hi] - m[lo]) * (r - lo) / (hi - lo) + 0.5)

def model(lg, season, r, n):
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        if n == 18: return SA18[r], f"세리에A {season} {r}위"
        v = mid_fill(m, r)
        return (v if v else SA[r - 1]), f"세리에A {season} {r}위"
    if lg == "IT2":
        m = ents_map("세리에B", season)
        if r in m: return m[r], f"세리에B {season} {r}위"
        return int(round(SB_MEAN + SD2 * curve(r, n))), f"세리에B {season} {r}위"
    if lg == "ES1":   # 라리가 1994-95~1998-99: 라울·호나우두·지단 자료와 같은 모형(리그 수준 추정)
        m = ents_map("라리가", season)
        if r in m: return m[r], f"라리가 {season} {r}위 (리그 수준 추정)"
        return int(1712.7 + 13.5 + 100.16 * curve(r, n) + 0.5), f"라리가 {season} {r}위 (리그 수준 추정)"
    if lg == "FR1":
        m = ents_map("리그1", season)
        if r in m: return m[r], f"리그1 {season} {r}위"
        return L1_20[r], f"리그1 {season} {r}위"
    return None

RANK_LG = ["IT1", "IT2", "ES1", "FR1"]

# 순위표·모형·기존 자료로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv) — 골·도움 상대만 필요
MAN = {
    (key("PAOK Thessaloniki"), "1997-98"): (1500, "그리스 1997-98 4위 (추정, 다른 선수 자료의 AEK 상위권 1550보다 낮게)"),
    (key("SL Benfica"), "2003-04"): (1795, "포르투갈 1부 2003-04 2위 (다른 선수 자료의 포르투갈 1부 2위 값 1795와 같음)"),
    (key("AEK Athens"), "2007-08"): (1550, "그리스 2007-08 2위 (추정, 다른 선수 자료 AEK 2006-07 2위 1550과 같음)"),
    (key("FK Mlada Boleslav"), "2007-08"): (1450, "체코 2007-08 7위 (추정, 다른 선수 자료의 믈라다 볼레슬라프 2014-15 4위 1480보다 낮게)"),
}

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
    euro = cid in ("CL", "CLQ", "UEFA", "EPP", "USC")
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
    return g["date_local_tm_report"] or g["date_local_tm_schedule"]

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])
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
    if not g: continue
    isg, isa, iss = e["vieri_scorer"] == "1", e["vieri_assist_other"] == "1", e["vieri_self_assist"] == "1"
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
    et = int(mi > 90 and not dm)
    if et and g["gameState"] == "regularly_terminated": sys.exit("연장 판정 이상 " + gid)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
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
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal"):
            sys.exit("도움 유형 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

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
