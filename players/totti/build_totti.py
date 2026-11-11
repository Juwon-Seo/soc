#!/usr/bin/env python3
"""Francesco Totti: raw/ -> totti.json + src/data/tot.js (판정 근거는 judgments.md)

  python3 players/totti/build_totti.py            # 출력 파일 쓰기
  python3 players/totti/build_totti.py --debug    # Elo 출처 목록
  python3 players/totti/build_totti.py --fm       # FotMob 골 대조(2010-11 이후)
  python3 players/totti/build_totti.py --cross    # 같은 경기 다른 선수 자료 대조

입력: raw/tm_games.csv(출전 785경기), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/sal.js(살라).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "tot.js")
OUT_JSON = os.path.join(HERE, "totti.json")
ME = "프란체스코 토티"
GAP = "2014-08-01"   # 도움 출처 기준일(이전 Transfermarkt, 이후 Transfermarkt∩FotMob)

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
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    "2266823|41": "PK 유도(Penalty: Fouled player, 폰세카 PK)",
    "2215434|44": "PK 유도(Penalty: Fouled player, 디비아조 PK)",
    "2215333|17": "슈팅 리바운드(Shot on goal)",
    "2214741|78": "슈팅 리바운드(Shot on goal)",
    "2214260|9": "슈팅 리바운드(Shot on goal)",
    "65419|55": "슈팅 리바운드(Shot on goal)",
    "2265584|90": "슈팅 리바운드(Shot on goal)",
    "2265585|84": "슈팅 리바운드(Shot on goal)",
    "1047505|86": "슈팅 리바운드(Shot on goal)",
    "2251400|5": "슈팅 리바운드(Shot on goal)",
    "2215410|50": "상대 자책골(안드레 크루스)",
    "27422|26": "상대 자책골(베르바토프)",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2490850|31": "AFP 경기 기사(토티 패스를 제르비뉴가 밀어 넣음)·Antara 경기 기사(토티가 제르비뉴 두 번째 골을 만듦)",
}
# FotMob에만 있는 도움(넣지 않음)
FM_ONLY = ["2015.5.17 우디네세전 65분 토로시디스 골(FotMob은 토티 도움, Transfermarkt·worldfootball은 도움 없음)"]

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1"}
CUP = {"CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 1·2라운드, 16강
    if cid == "SCI": return "df"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 2001-02·2002-03 2차 조별 포함(앙리 2002.11.27 로마전 선례)
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # UEFA컵 2·3라운드·16강·8강, 유로파 32강(intermediate stage)·16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

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
    # 원정 다득점·연장: UEFA 대회(2020-21까지), 코파 이탈리아(2021-22까지) 모두 적용
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
    "inter milan": "inter", "lokomotiv moskau": "lokomotiv moscow", "dinamo moscow": "dynamo moscow",
    "ac fiorentina": "acf fiorentina", "ac parma": "parma fc", "torino calcio": "torino fc",
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

# 세리에A 20팀(2004-05~) 고정 순위값(기존 자료)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
# 세리에A 18팀(1988-89~2003-04): 기존 선수 자료(앙리·카카·즐라탄·판페르시·램파드·드록바·로번)의 순위값.
#   기존 자료에 없는 7·9·12·16위는 앞뒤 순위값의 가운데
SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 8: 1743, 10: 1713, 11: 1704, 13: 1690, 14: 1676,
        15: 1657, 17: 1633, 18: 1614}
for r_ in (7, 9, 12, 16):
    SA18[r_] = int(round((SA18[r_ - 1] + SA18[r_ + 1]) / 2 + 0.01))
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

# 라리가: 에투 자료와 같은 방식 — 기존 자료 2003-04 순위값(14위는 2004-05 값 − 1)에 같은 시즌 기존 값과의 차(중앙값)를 더함.
#   1998-99는 기존 값이 없어 1999-00 차(+11)를 씀(추정)
LL_BASE = ents_map("라리가", "2003-04"); LL_BASE[14] = 1661
assert len(LL_BASE) == 20, LL_BASE
def laliga(season, r):
    m = ents_map("라리가", season)
    if r in m: return m[r], f"라리가 {season} {r}위"
    est = ""
    if not m:
        assert season == "1998-99"; m = ents_map("라리가", "1999-00"); est = " (추정, 1999-00 시즌 다른 선수 자료의 순위값 차이 사용)"
    diffs = sorted(v - LL_BASE[k] for k, v in m.items())
    n_ = len(diffs)
    sh = diffs[n_ // 2] if n_ % 2 else (diffs[n_ // 2 - 1] + diffs[n_ // 2]) / 2
    return int(round(LL_BASE[r] + sh)), f"라리가 {season} {r}위{est}"

def model(lg, season, r, n):
    """(Elo, lv) — 순위표 + 리그 모형"""
    if lg == "IT1":
        if n == 18: return SA18[r], f"세리에A {season} {r}위"
        assert n == 20
        return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "IT3A":  # 세리에C1(3부): 인시녜 자료와 같은 모형(평균 1416.56, 흩어짐 51.24)
        return int(round(1416.56 + 51.24 * curve(r, n))), f"세리에C1(3부) A조 {season} {r}위/{n}팀 (추정)"
    if lg == "ES1":
        return laliga(season, r)
    if lg == "GB1":   # 프리미어리그: 기존 자료 1998-99 값 = 2025-26 순위값 − 142(램파드 자료 보정)
        m = ents_map("프리미어리그", season)
        if r in m: return m[r], f"프리미어리그 {season} {r}위"
        base = ents_map("프리미어리그", "2025-26")
        sh = {k: v - base[k] for k, v in m.items() if k in base}
        assert len(set(sh.values())) == 1, sh
        return base[r] + list(sh.values())[0], f"프리미어리그 {season} {r}위"
    if lg == "IT2":   # 세리에B: 인시녜·라우타로 자료와 같은 모형(평균 1577.78, 흩어짐 51.24)
        return int(round(1577.78 + 51.24 * curve(r, n))), f"세리에B {season} {r}위"
    return None

RANK_LG = ["IT1", "IT2", "IT3A", "ES1", "GB1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {
    (key("KSC Eendracht Aalst"), "1995-96"): (1400, "벨기에 1995-96 13위/18팀 (추정, 다른 선수 자료 벨기에 1부 2010-11 12위 1412·14위 1361 수준)"),
    (key("SK Slavia Prague"), "1995-96"): (1500, "체코 1995-96 1위 (추정, 다른 선수 자료의 슬라비아 프라하 1500과 같음)"),
    (key("Bröndby IF"), "1995-96"): (1520, "덴마크 1995-96 1위 (추정, 다른 선수 자료의 브뢴뷔 2003 1520과 같음)"),
    (key("Dinamo Moscow"), "1996"): (1550, "러시아 1996 3위 (추정, 다른 선수 자료 러시아 상위권 1580~1600보다 조금 낮게)"),
    (key("Silkeborg IF"), "1998-99"): (1400, "덴마크 1998-99 9위/12팀 (추정, 다른 선수 자료 덴마크 중하위권 에스비에르 1450보다 낮게)"),
    (key("FC Zürich"), "1998-99"): (1450, "스위스 1998-99 (추정, 다른 선수 자료의 취리히 2008 1450과 같음)"),
    (key("ND Gorica"), "2000-01"): (1300, "슬로베니아 2000-01 7위/12팀 (추정, 다른 선수 자료 무라 2012-13 9위 1300과 같은 수준)"),
    (key("Lokomotiv Moskau"), "2001-02"): (1580, "러시아 2001 상위권 (추정, 다른 선수 자료의 로코모티프 모스크바 2003·2007 1580과 같음)"),
    (key("Aris Thessaloniki"), "2005-06"): (1480, "그리스 2005-06 (추정, 다른 선수 자료의 아리스 2007·2010 1480과 같음)"),
    (key("KAA Gent"), "2009-10"): (1545, "벨기에 2009-10 3위 (추정, 다른 선수 자료의 겐트 2010-11 5위 1545와 같음)"),
    (key("MFK Kosice"), "2009-10"): (1330, "슬로바키아 2009-10 11위/12팀 (추정, 다른 선수 자료 슬로바키아 1부 푸호프 1330과 같은 수준)"),
    (key("FC Basel 1893"), "2009-10"): (1600, "스위스 2009-10 1위 (추정, 다른 선수 자료의 바젤 2008-09 1600과 같음)"),
    (key("Slovan Bratislava"), "2011-12"): (1450, "슬로바키아 2011-12 3위 (추정, 다른 선수 자료의 슬로반 브라티슬라바 2009·2014 1450과 같음)"),
    (key("Austria Vienna"), "2016-17"): (1556, "오스트리아 2016-17 2위 (추정, 다른 선수 자료 오스트리아 분데스리가 2014-15 2위 1556과 같음)"),
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
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL", "ELQ", "UEFA") else [eu]
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
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model"))
                    return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_tm_report"]

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["totti_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

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

used_excl = set()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa = e["totti_scorer"] == "1", e["totti_assist_other"] == "1"
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
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        if tag in EXCL_A:
            used_excl.add(tag)
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal") or e["assist_type"].startswith("Handball"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP and tag not in ADD_CONFIRMED:
            if not any(abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - mi) <= 2 for t in FM_ASSIST.get(gid, [])):
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)
if set(EXCL_A) - used_excl: sys.exit("쓰이지 않은 도움 제외 " + str(set(EXCL_A) - used_excl))

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

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
