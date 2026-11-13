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

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Alessandro Del Piero": ("del.js", "DEL"), "Zinédine Zidane": ("zid.js", "ZID"), "Pavel Nedvěd": ("ned.js", "NED"),
         "Ronaldo": ("rno.js", "RNO"), "Clarence Seedorf": ("see.js", "SEE"), "Andriy Shevchenko": ("she.js", "SHE"),
         "Kaká": ("kak.js", "KAK"), "Filippo Inzaghi": ("inz.js", "INZ")}
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
for nm, (fn, P) in MATES.items():
    ent = load_js(fn, P)
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("비에리 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and x[13] == "Christian Vieri":
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→비에리 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    # TM이 비에리 도움으로 적었지만 뺀 동료 골 / TM 동료 도움이 동료 파일에 없는 비에리 골
    for e in EVENTS:
        if e["gameId"] not in G: continue
        d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
        if e["vieri_assist_other"] == "1" and norm(e["scorer"]) == norm(nm) and not any(r[0] == "a" and r[9] == d and abs(r[4] - mi) <= 2 for r in E):
            has = any(x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent)
            CROSS.append(("TM 비에리 도움을 뺀 동료 골", nm, d, e["minute"], e["assist_type"], "동료 골 있음" if has else "동료 골 없음"))
        if e["vieri_scorer"] == "1" and norm(e["assist_player"]) == norm(nm):
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움이 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
# 같은 날·같은 상대의 다른 선수 자료 전체(동료) — 대회·Elo·lv·합산
SAMEGAME = []
for fn in sorted(os.listdir(os.path.join(ROOT, "src", "data"))):
    if not fn.endswith(".js") or fn in ("hon.js", "vie.js"): continue
    P = fn[:-3].upper()
    try: ent = load_js(fn, P)
    except Exception: continue
    for x in ent:
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                SAMEGAME.append((fn, r[9], r[1], d or "같음"))
                break
SAMEGAME = sorted(set((a, b, c, tuple(d) if isinstance(d, list) else d) for a, b, c, d in SAMEGAME))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
    for s_ in SAMEGAME:
        if s_[-1] != "같음": print("같은 경기 차이", s_)
    print("같은 경기", collections.Counter((s_[0], s_[-1] == "같음") for s_ in SAMEGAME))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("torvi", "1992-11-10", "토리노", "1991~1992"), ("pisvi", "1993-07-01", "피사", "1992~1993"),
         ("ravvi", "1994-07-01", "라벤나", "1993~1994"), ("venvi", "1995-07-01", "베네치아", "1994~1995"),
         ("atavi", "1996-07-01", "아탈란타", "1995~1996"), ("juvvi", "1997-07-01", "유벤투스", "1996~1997"),
         ("atmvi", "1998-07-01", "아틀레티코 마드리드", "1997~1998"), ("lazvi", "1999-07-01", "라치오", "1998~1999"),
         ("intvi", "2005-07-01", "인테르", "1999~2005"), ("milvi", "2006-01-01", "AC 밀란", "2005~2006"),
         ("monvi", "2006-07-01", "AS 모나코", "2006"), ("atavi", "2007-07-01", "아탈란타", "2006~2007"),
         ("fiovi", "2008-07-01", "피오렌티나", "2007~2008"), ("atavi", None, "아탈란타", "2008~2009")]
TM_CLUB = {"416": "torvi", "4172": "pisvi", "1105": "ravvi", "607": "venvi", "800": "atavi", "506": "juvvi", "13": "atmvi",
           "398": "lazvi", "46": "intvi", "5": "milvi", "162": "monvi", "430": "fiovi"}
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
ORDER = list(dict.fromkeys(k for k, *_ in CLUBS))
CLUB_KO = {k: n for k, u, n, y in CLUBS}
CLUB_Y = {"torvi": "1991~1992", "pisvi": "1992~1993", "ravvi": "1993~1994", "venvi": "1994~1995", "atavi": "1995~1996·2006~2007·2008~2009",
          "juvvi": "1996~1997", "atmvi": "1997~1998", "lazvi": "1998~1999", "intvi": "1999~2005", "milvi": "2005", "monvi": "2006", "fiovi": "2007~2008"}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in ORDER)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
    if season_eu(ldate(g))[:4] != g["seasonId"]: sys.exit("시즌 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NOTE_LINES = [
    f"크리스티안 비에리(토리노·피사·라벤나·베네치아·아탈란타·유벤투스·아틀레티코 마드리드·라치오·인테르·AC 밀란·AS 모나코·피오렌티나)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 라치오전 ~ {d_(M[-1][0])} 카타니아전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·이탈리아 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]}({CLUB_Y[k]}) {c3(ST[k])}" for k in ORDER)
    + f". 출전 분 합계 {MIN_TOT:,}분(Transfermarkt 기록, 90분으로 추정한 경기 없음)",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골이나 도움이 있는 경기와 리그 밖 경기 전부). 경기 수·골은 영어·이탈리아어 위키백과 클럽·시즌별 기록과 대조함(통산 Transfermarkt 477경기 236골 = 영어 위키백과 476경기 236골, 라벤나 1993-94 코파 이탈리아 1경기를 영어 위키백과만 뺌). FotMob에는 비에리의 클럽 경기별 자료가 없어(2010년 이전) 골 시각은 Transfermarkt만 근거",
    "넣지 않은 경기: 이탈리아어 위키백과에만 있는 프라토 1989-90 세리에C 코파 이탈리아 1경기(0골)와 베네치아 1994-95 코파 델레 알피 2경기(1골) — 코파 델레 알피는 이탈리아·스위스 클럽 친선 성격의 지역 대회라 공식 대회로 보지 않았고 Transfermarkt에도 경기가 없음. 토리노 1990-91은 출전 기록 없음",
    "골: Transfermarkt 리포트 골 236개를 모두 씀(자책골 없음). PK 골 25개는 Transfermarkt 골 유형 'Penalty' 기준(선수 경기 성적의 PK 골 수와 같음)",
    f"도움: 모두 Transfermarkt 경기 리포트 도움(2014년 이전이라 단일 출처, 경기마다 다른 출처로 대조하지 못함). 도움 {NA} = Transfermarkt 39 − PK 유도 4(1996.12.15 베로나전·1997.2.16 페루자전 델 피에로, 1997.3.1 비첸차전 파도바노, 1997.5.18 파르마전 아모루소) − 슈팅 리바운드('Shot on goal') 2(1999.2.21 인테르전 콘세이상, 2000.12.23 아탈란타전 세도르프) − 상대 자책골에 준 도움 1(1998.5.10 바르셀로나전 페르난두 쿠투). 1998.3.21 살라망카전 비에리 PK 골에 비에리 본인이 PK 유도로 적힌 것은 도움이 아님(Transfermarkt 도움 합계에도 없음). 2007.9.29 리보르노전 산타나 골(비에리 크로스, 슈팅이 굴절돼 들어감)은 크로스 도움이라 남김. 유형 칸이 빈 도움 1개(2004.2.15 우디네세전 크루스)는 일반 도움으로 셈",
    "출전 분: 2003.4.19 브레시아전 18분은 46분 교체 투입 뒤 63분 퇴장(난투로 빌리카와 함께 퇴장, Transfermarkt 리포트)이라 그대로 씀",
    "날짜는 경기 현지 날짜(Transfermarkt 리포트·일정표 날짜; 선수 경기 성적의 날짜는 킥오프 시각이 없는 1990년대 세리에B·라리가 경기 등에서 하루 앞섬)",
    "2005.4.12 챔스 8강 2차전 밀란전(관중 소요로 0-1에서 중단, 0-3 몰수)은 비에리가 벤치에만 있어 출전·기록 없음. 1차전(2005.4.6, 35분 출전)은 골·도움이 없어 합산 계산에 쓰이지 않음",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표를 영어 위키백과 최종 순위와 대조)를 기존 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "세리에A 18팀 시즌(1991-92·1995-96)은 다른 선수 자료의 18팀 순위값(1위 1969 ~ 18위 1614, 7·9·12·16위는 앞뒤 값의 가운데), 세리에B 1992-93~1995-96은 다른 선수 자료와 같은 세리에B 모형(평균 1578, 2부 흩어짐)에 위키백과 최종 순위(동률은 공동 순위: 1993-94 비첸차 공동 10위)를 넣음. 세리에A 1991-92 라치오는 34점 동률로 Transfermarkt 11위·위키백과 10위라 10위로 씀. 라리가 1997-98 살라망카(15위)는 라울·호나우두·지단 자료와 같은 1990년대 라리가 모형(리그 수준 추정)",
    "직접 추정(다른 선수 자료의 같은 팀·나라 값 기준): PAOK 1997-98 그리스 4위 1500, AEK 아테네 2007-08 그리스 2위 1550, 믈라다 볼레슬라프 2007-08 체코 7위 1450(모두 추정), 벤피카 2003-04 포르투갈 2위 1795(다른 선수 자료의 포르투갈 2위 값)",
    "대회 비중: 코파 이탈리아·코파 델 레이·쿠프 드 라 리그는 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), UEFA 슈퍼컵 1996-97(두 경기)은 국내컵 결승, UEFA컵 1라운드는 유로파 예선, UEFA컵 2라운드 이후·32강과 컵위너스컵 8강은 유로파 토너먼트, 2007-08 UEFA컵 조별은 유로파 조별, 컵위너스컵 준결승·결승(1999 마요르카전)은 유로파 준결승·결승, 챔스 2차 조별(2002-03)은 조별로 계산함. 2000.5.23 세리에A 챔스 진출 플레이오프 파르마전(단판, 골·도움 없음)은 리그 비중",
    f"두 경기 합산(챔스·UEFA컵·컵위너스컵·UEFA 슈퍼컵 1996-97·코파 이탈리아) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음). 비에리가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움(1997.2.5 UEFA 슈퍼컵 2차전 파리 생제르맹전의 1차전 원정 6-1, 2001.12.6 UEFA컵 3라운드 2차전 입스위치전의 1차전 원정 0-1 등)",
    "시즌 구분은 기본 8월 1일 기준(7월 경기 없음). 클럽 구분은 1992.11.10 전 토리노, 1993.7.1 전 피사, 1994.7.1 전 라벤나, 1995.7.1 전 베네치아, 1996.7.1 전 아탈란타, 1997.7.1 전 유벤투스, 1998.7.1 전 아틀레티코 마드리드, 1999.7.1 전 라치오, 2005.7.1 전 인테르, 2006.1.1 전 AC 밀란, 2006.7.1 전 AS 모나코, 2007.7.1 전 아탈란타, 2008.7.1 전 피오렌티나, 이후 아탈란타(아탈란타 세 시기는 한 클럽으로 묶음)",
    "동료 자료 대조: 같은 경기를 다룬 델 피에로·지단·네드베드·호나우두·세도르프·셰브첸코·카카 자료의 대회·상대 Elo·합산 정보가 모두 같음. 세도르프 도움→비에리 골 4개, 델 피에로·호나우두 도움→비에리 골 각 1개, 비에리 도움→셰브첸코 골 2개·호나우두·세도르프 골 각 1개의 날짜·분·스코어가 같음. Transfermarkt가 비에리 도움으로 적었으나 뺀 델 피에로 PK 2개(1996.12.15·1997.2.16)와 세도르프 리바운드 골(2000.12.23)은 동료 자료에도 비에리 도움이 없음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 세리에A 1996-97(유벤투스), 코파 이탈리아 1992-93(토리노)·2004-05(인테르), UEFA 슈퍼컵 1996-97, 인터콘티넨털컵 1996(유벤투스, 비에리 출전 없음). 컵위너스컵 1998-99(라치오), 준우승은 챔스 결승 1996-97(유벤투스)과 UEFA컵 1991-92(토리노, 비에리 출전 없음). 개인: 라리가 득점왕 1997-98(24골)·세리에A 득점왕 2002-03(24골), 올해의 선수 1999·2002. U-21 유럽선수권·월드컵 등 대표팀 기록은 뺌",
    "은퇴: 2009년 아탈란타에서 은퇴(마지막 클럽 경기 2009.2.1 카타니아전)",
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
    gs = sorted({(r[5], r[6], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const VIE_E={J(E)};\nconst VIE_M={J(M)};\nconst VIE_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game": SAMEGAME, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
