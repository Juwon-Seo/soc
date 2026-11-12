#!/usr/bin/env python3
"""필리포 인자기: raw/ -> inzaghi.json + src/data/inz.js (판정 근거는 judgments.md)

  python3 players/inzaghi/build_inzaghi.py            # 파일 쓰기
  python3 players/inzaghi/build_inzaghi.py --debug    # Elo 출처 목록
  python3 players/inzaghi/build_inzaghi.py --fm       # FotMob 골 대조
  python3 players/inzaghi/build_inzaghi.py --cross    # 동료 파일(델 피에로·지단·셰브첸코·카카·호나우두·호나우지뉴 등) 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(동료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "inz.js")
OUT_JSON = os.path.join(HERE, "inzaghi.json")
ME = "필리포 인자기"
INZ = "Filippo Inzaghi"

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
# 골 제외(Transfermarkt 리포트 골이지만 넣지 않음): gameId|분 -> 이유
EXCL_G = {}

# 도움 제외는 유형으로 자동 판정(아래 add 부분): 'Penalty: Fouled player'(PK 유도), 'Shot on goal'(슈팅 리바운드), 상대 자책골.
# 도움 유형이 비어 있는 5개는 TM 단일 출처(2014-08-01 전)로 남김.
# 본인 PK 골의 본인 도움(inz_self_assist): 990059 2000-09-13 함부르크전 88분 PK 골 -> 도움 아님.

# 일부러 PK가 아닌 골로 처리: 1022468 밀란–레지나 2002-11-03 20분 'Penalty rebound' (TM penalty 플래그 0)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "IT3A", "IT3B", "ITPO"}   # ITPO = 1998-99 세리에A UEFA컵 진출 플레이오프(두 경기, 리그 비중 + 합산: 호나우두·메르턴스 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "CIT":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # First/Second Round, Round of 16, Last 16
    if cid in ("SCI", "USC"): return "df"
    if cid in ("WEPO", "KLUB"): return "cwc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 2002-03 2차 조별(Group 3)도 조별
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UI": return "elq"   # 인터토토컵: 램파드·델 피에로 선례(전 라운드 elq)
    if cid == "EPP":   # 컵위너스컵: 호나우두·네드베드 선례
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r and g["competitionId"] != "ITPO": return 0
    return 1 if ("1st" in r) else 2

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
    if g["competitionId"] == "ITPO":   # 1998-99 UEFA컵 진출 플레이오프: 원정 다득점으로 결정(연장 없음) — 우디네세가 원정 다득점 승
        return [leg, home, fu, ft, 1, 0]
    # 원정 다득점·연장: UEFA 대회(2020-21까지), 코파 이탈리아(2021-22까지), 인터토토컵(델 피에로·램파드 선례)
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

# 표준 순위 곡선(세리에A 20팀 기존 값을 표준화, 다른 선수 자료와 같음)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24   # 2부 흩어짐(세리에B·튀르키예 2부 선례)

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

# 세리에A 18팀(1988-89~2003-04): 기존 자료의 순위값, 7·9·12·16위는 앞뒤 값의 가운데(토티·델 피에로·셰브첸코 자료와 같음)
SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 7: 1762, 8: 1743, 9: 1728, 10: 1713, 11: 1704, 12: 1697, 13: 1690, 14: 1676, 15: 1657, 16: 1645, 17: 1633, 18: 1614}
SB_MEAN = 1577.78   # 세리에B(문서 4절 평균·흩어짐)
C1_MEAN = 1416.56   # 세리에C1·레가 프로 1(3부) 평균(인시녜 선례 1416.56, 토티 1994-95·델 피에로 1996-97 값도 재현), 흩어짐 SD2

def c1_elo(r, n):
    return int(round(C1_MEAN + SD2 * curve(r, n)))

def model(lg, season, r, n):
    """(Elo, lv) — 순위표 + 리그 모형"""
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        if n == 18: return SA18[r], f"세리에A {season} {r}위"
        assert n == 20, (season, n)
        return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "IT2":
        m = ents_map("세리에B", season)
        if r in m: return m[r], f"세리에B {season} {r}위"
        return int(round(SB_MEAN + SD2 * curve(r, n))), f"세리에B {season} {r}위"
    if lg in ("IT3A", "IT3B"):
        grp = "A" if lg == "IT3A" else "B"
        if int(season[:4]) >= 2008: return c1_elo(r, n), f"세리에C(레가 프로 1) {grp}조 {season} {r}위/{n}팀 (추정)"
        return c1_elo(r, n), f"세리에C1(3부) {grp}조 {season} {r}위/{n}팀 (추정)"
    for lg2, lab in (("ES1", "라리가"), ("NL1", "에레디비시"), ("PO1", "포르투갈 1부")):
        if lg == lg2:
            m = ents_map(lab, season)
            if r in m: return m[r], f"{lab} {season} {r}위"
            vals = collections.Counter()
            for e in ENTS:
                mm = re.match("^" + re.escape(lab) + r" (\d{4}-\d\d) (\d+)위$", e["lv"] or "")
                if mm and int(mm.group(2)) == r: vals[e["elo"]] += 1
            if vals:
                return vals.most_common(1)[0][0], f"{lab} {season} {r}위"
            return None
    return None

RANK_LG = ["IT1", "IT2", "IT3A", "IT3B", "ES1", "NL1", "PO1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {
    (key("Halmstads BK"), "1995"): (1439, "스웨덴 1995 3위/14팀 (추정, 다른 선수 자료의 알스벤스칸 2001 3위 1439와 같은 값; 네드베드 자료 할름스타드 1994 7위 1390과 같은 순위 보간)"),
    (key("KF Teuta"), "1995-96"): (1300, "알바니아 1995-96 2위 (추정, 다른 선수 자료의 KF 티라나 2009-10 3위 1300과 같은 값)"),
    (key("Panathinaikos"), "2000-01"): (1560, "그리스 2000-01 2위 (추정, 다른 선수 자료의 파나티나이코스 2001-02·2009-10 2위 1560과 같은 값)"),
    (key("FC Slovan Liberec"), "2002-03"): (1463, "체코 2002-03 4위 (추정, 체코 1부 순위 직선 1500−12.5×(순위−1): 다른 선수 자료의 슬로반 리베레츠 2001-02 1위 1500·테플리체 2003-04 9위 1400과 같은 직선)"),
}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    # 1) 같은 경기 다른 선수 자료(날짜 ±1)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    euro = cid in ("CL", "CLQ", "EL", "UEFA", "WEPO", "USC", "UI", "EPP", "KLUB")
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if euro else [eu]
    # 2) 같은 팀·같은 시즌 기존 값(팀×시즌 통합표)
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    # 3) 직접 추정
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    # 4) 순위표 + 리그 모형
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
    return g["date_local_tm_report"] or g["date_local"]

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
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

TM_A_TYPES = collections.Counter()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["inz_scorer"] == "1", e["inz_assist_other"] == "1", e["inz_self_assist"] == "1"
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
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    et = 0
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        TM_A_TYPES[e["assist_type"]] += 1
        if e["own_goal"] == "1" or not ours:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "상대 자책골")); continue
        if e["assist_type"] == "Penalty: Fouled player":
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "PK 유도")); continue
        if e["assist_type"] == "Shot on goal":
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "슈팅 리바운드")); continue
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
    sys.exit(0)
