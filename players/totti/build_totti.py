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

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["totti_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
FM_NONE = []
for gid, evs in TMG.items():
    if gid not in FM_EV:
        if ldate(G[gid]) >= "2010-08-01": FM_NONE.append((ldate(G[gid]), G[gid]["opponent"]))
        continue
    fg = [r for r in FM_EV[gid] if r["totti_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["newScore_home_away"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)
    print("FotMob 기록 없음:", FM_NONE)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Mohamed Salah": ("sal.js", "SAL", "2015-08-01", "2017-06-22")}
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[7] != b[7] or ((a[14] if len(a) > 14 else 0) or 0) != ((b[14] if len(b) > 14 else 0) or 0):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    return diffs
for nm, (fn, P, lo, hi) in MATES.items():
    ent = load_js(fn, P)
    for r in E:   # 토티 도움 → 동료 골
        if r[0] == "a" and r[13] == nm:
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("토티 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:  # 동료 도움 → 토티 골
        if x[0] == "a" and x[13] == "Francesco Totti":
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→토티 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:  # 같은 경기·같은 상대 Elo/lv/대회
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    CROSS.append(("같은 경기", nm, r[9], r[1], d or "같음")); break
    for x in ent:  # 동료 골에 대한 Transfermarkt 토티 도움을 뺀 경우(참고)
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["totti_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 토티 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("romtt", None, "로마", "1993~2017")]
def club_of(d): return "romtt"
ST = {"romtt": [len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E), sum(m[3] for m in M)]}
for g in GAMES:
    if g["club_id"] != "12": sys.exit("로마 아닌 경기 " + g["gameId"])

def season_tt(d):   # 7월 10일 기준(2009.7.30 겐트전 = 2009-10)
    y = int(d[:4]); s = y if d[5:] >= "07-10" else y - 1
    return f"{s}-{str(s + 1)[2:]}"
SEASONS = collections.OrderedDict()
for m in M:
    s = season_tt(m[0]); SEASONS.setdefault(s, [0, 0, 0, 0]); SEASONS[s][0] += 1; SEASONS[s][3] += m[3]
for r in E:
    SEASONS[season_tt(r[9])][1 if r[0] == "g" else 2] += 1

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
POST_A = NA - PRE_A
SRC = ELO_SRC
MDATES = {m[0] for m in M}
OTHER_NOT_PLAYED = sorted({TIES_RAW[g["gameId"]]["other_leg_date"] for g in GAMES
                           if g["gameId"] in TIES_RAW and TIES_RAW[g["gameId"]]["other_leg_date"] not in MDATES and "2nd" in g["round"].lower()})
OTHER_NOT_PLAYED_E = sorted({r[9] for r in E if len(r) > 14 and r[14][0] == 2} & {g["date_local_tm_report"] for g in GAMES
                            if g["gameId"] in TIES_RAW and TIES_RAW[g["gameId"]]["other_leg_date"] not in MDATES})
def opp_ko(n):
    return n
NOTE_LINES = [
    f"프란체스코 토티(로마)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 브레시아전 ~ {d_(M[-1][0])} 제노아전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·이탈리아 대표팀 제외",
    f"클럽별 경기·골·도움: 로마 {NG}·{NGo}·{NA}. 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분(연장·교체 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(출전한 {NG}경기 전부 있음), 2010-11 이후 골·도움은 FotMob 경기 이벤트와 대조함. 90분 추정 경기 없음. 로마 유스(프리마베라) 경기는 어느 출처에도 없음",
    "경기 수·골은 영어·이탈리아어 위키백과 시즌별 기록과 같음(위키백과 786경기 307골). 다른 곳은 2008-09 세리에A 하나: 위키백과(이탈리아어 위키백과 로마 2008-09 시즌 문서 포함) 24경기, Transfermarkt·FotMob 23경기. Transfermarkt에서 그 시즌 토티가 뛰지 않은 리그 15경기는 부상 14경기와 벤치 1경기(2009.1.25 나폴리전, 경기 리포트 교체 명단에도 없음)라 빠진 1경기를 찾지 못해 넣지 않음",
    "2004.9.15 챔스 조별 디나모 키이우전은 0-1로 전반이 끝난 뒤 중단돼 0-3 몰수패로 처리된 경기(Transfermarkt 'Result as per court'). 출전 45분으로 셈. 토티 골·도움은 없고, 리포트의 득점 목록(0-1)과 최종 스코어(0-3)가 다른 것은 몰수 판정 때문이라 다른 기록에 영향 없음",
    "날짜는 현지 날짜(Transfermarkt 경기 리포트). 선수 경기 성적의 날짜가 하루 앞선 8경기(1994.10.26 제노아전, 1998.1.7·1.21 라치오전, 2000.1.12·1.25 칼리아리전, 2001.5.20 바리전, 2003.2.5 라치오전, 2010.5.5 코파 이탈리아 결승)는 리포트 날짜를 씀. 2010-11 이후 경기는 FotMob 경기 시간과 모두 같음",
    f"골: Transfermarkt 리포트 골 {NGo}개를 그대로 씀(위키백과 합계와 같음). PK 골 {NPK}개는 Transfermarkt 골 유형 'Penalty' 기준(선수 경기 성적의 PK 골 수와 같음). 2012.10.31 파르마전 71분 골은 'Penalty rebound'(PK가 막힌 뒤 리바운드)라 일반 골로 셈",
    "2010-11 이후 골은 FotMob 경기 이벤트와 분·스코어·PK가 모두 같음. FotMob 기록이 없는 2010.8.21 수페르코파 인테르전(골 없음)·2011.1.22 칼리아리전·2011.2.20 제노아전 골은 Transfermarkt만 근거",
    f"도움: 2014.8.1 이전은 Transfermarkt 경기 리포트 도움, 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것만 씀. 도움 {NA} = Transfermarkt 리포트 205 − PK 유도 2(1996.5.12 디비아조 PK, 1996.9.10 디나모 모스크바전 폰세카 PK) − 슈팅 리바운드 8(1996.2.25 스타투토, 1998.3.15 알다이르, 1998.10.25 델베키오, 2007.2.25 타바노, 2007.5.9·5.17 코파 이탈리아 결승 파누치·페로타, 2011.1.6 부치니치, 2012.11.25 데스트로) − 상대 자책골에 준 도움 2(1996.4.20 나폴리전 안드레 크루스, 2004.10.19 레버쿠젠전 베르바토프). Transfermarkt 리포트가 본인 PK 골에 본인 도움으로 적은 3개(2009.7.30 겐트전, 2009.12.3 바젤전, 2014.10.5 키에보전)는 도움으로 세지 않음",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(1990~2000년대는 경기별 도움을 적은 다른 출처가 없고, FotMob 경기 이벤트도 2010~14 도움이 대부분 비어 있음). 도움 유형 칸이 빈 7개(1995.5.7 발보, 1997.1.12 발보, 1997.2.16 모리에로, 2002.2.26 몬텔라, 2003.2.26 에메르송, 2010.10.19 보리엘로, 2010.10.30 부치니치 골)도 일반 도움으로 셈",
    f"2014.8.1 이후 도움 {POST_A}개 중 {POST_A - 1}개는 FotMob도 토티 도움으로 적음. 2014.9.17 챔스 CSKA 모스크바전 31분 제르비뉴 골은 FotMob에 도움이 없지만 AFP·Antara 경기 기사가 토티 패스로 적어 넣음(Sports Mole 평점 기사는 세 번째 골 도움으로 적어 다름)",
    "FotMob에만 있는 도움 1개는 넣지 않음: " + "; ".join(FM_ONLY) + ". FotMob 경력 시즌별 도움 합계(2010-11 리그 9, 2011-12 리그 7 등)는 경기 이벤트가 빈 경기가 많아 Transfermarkt와 다름",
    "상대 Elo는 같은 경기를 다룬 다른 선수 자료(살라) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 모형에 넣은 값 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "세리에A 18팀 시즌(1992-93~2003-04)은 다른 선수 자료(앙리·카카·즐라탄 등)의 18팀 순위별 값(1위 1969 … 18위 1614)을 쓰고, 다른 선수 자료에 없는 7·9·12·16위는 앞뒤 순위 값의 가운데(1762·1728·1697·1645)로 둠. 20팀 시즌(2004-05~)은 다른 선수 자료와 같은 순위별 값. 세리에B(코파 이탈리아 상대)는 다른 선수 자료와 같은 리그 모형, 세리에C1 피오렌출라 1994-95(A조 3위)는 같은 방식의 3부 추정",
    "라리가 2001-02 바르셀로나(4위)는 같은 시즌 다른 선수 자료 값과 2003-04 순위별 값의 차이(+16)로, 1998-99 아틀레티코 마드리드(13위)는 그 시즌 자료가 없어 1999-00 차이(+11)로 계산(추정). 프리미어리그 1998-99 리즈(4위)는 다른 선수 자료의 그 시즌 값(현재 순위별 값 − 142)",
    "직접 추정(모두 '추정'): 알스트 1995-96(벨기에 13위) 1400, 슬라비아 프라하 1995-96 1500, 브뢴뷔 1995-96 1520, 디나모 모스크바 1996(러시아 3위) 1550, 실케보르 1998-99(덴마크 9위) 1400, 취리히 1998-99 1450, 고리차 2000-01(슬로베니아 7위) 1300, 로코모티프 모스크바 2001 1580, 아리스 2005-06 1480, 겐트 2009-10 1545, 코시체 2009-10(슬로바키아 11위) 1330, 바젤 2009-10 1600, 슬로반 브라티슬라바 2011-12 1450, 아우스트리아 빈 2016-17(오스트리아 2위) 1556. 모두 다른 선수 자료의 같은 팀 다른 시즌 값이나 같은 리그 비슷한 순위 값에 맞춘 것으로 근거 약함",
    "대회 비중: 코파 이탈리아는 국내컵(1·2라운드·16강은 낮은 비중, 8강 이후 높은 비중), 수페르코파 이탈리아나는 국내컵 결승, UEFA컵 1라운드·유로파 예선(3·4라운드·플레이오프)은 유로파 예선, UEFA컵 2·3라운드·16강·8강과 유로파 32강·16강은 유로파 토너먼트, UEFA컵 2005-06 조별과 유로파 조별은 유로파 조별, 챔스 2001-02·2002-03 2차 조별은 챔스 조별로 계산함",
    f"두 경기 합산(UEFA 대회 토너먼트·예선, 코파 이탈리아 두 경기 라운드와 2002-03~2006-07 두 경기 결승) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점과 연장은 UEFA 대회·코파 이탈리아 모두 적용(1993-94 삼프도리아전·1998-99 아탈란타전·2004-05 피오렌티나전은 합산 동점·원정골 같음으로 연장 뒤 승부차기, 1995-96 슬라비아 프라하전은 연장 뒤 원정 다득점으로 탈락해 같은 규칙과 맞음)",
    "토티가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움(모두 저장된 리포트): " + ", ".join(d_(x) for x in OTHER_NOT_PLAYED),
    "연장·승부차기: 1996.3.19 UEFA컵 8강 슬라비아 프라하전 99분 도움은 연장 시간으로 계산. 승부차기로 끝난 5경기(1993.12.16 삼프도리아전, 1998.11.12 아탈란타전, 2005.3.16 피오렌티나전, 2008.8.24 수페르코파 인테르전, 2009.3.11 아스널전)는 모두 연장을 치렀고 스코어는 연장까지의 골만 셈(Transfermarkt 최종 스코어에는 승부차기가 들어 있음). 2017.2.1 코파 이탈리아 8강 체세나전 90+7분 PK 골은 정규시간 추가시간",
    "시즌 구분: 7월 10일 기준(2009.7.30 유로파 예선 겐트전이 2009-10 시즌). 6월 경기(2005.6.12·6.15 코파 이탈리아 결승, 1995·1997·2001년 6월 리그)는 전 시즌",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 세리에A 2000-01, 코파 이탈리아 2006-07·2007-08, 수페르코파 이탈리아나 2001·2007. 개인: 유러피언 골든슈 2006-07(26골), 세리에A 득점왕 2006-07(26골), 이탈리아 올해의 선수 5회(2000·2001·2003·2004·2007). 세리에A 올해의 젊은 선수(1999)는 표 항목이 없어 뺌. 월드컵 2006·U-21 유로 1996 등 대표팀 기록은 뺌",
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
        if b[0] < a[0] or b[1] < a[1]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
mm = {m[0]: m for m in M}
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if r[3] != mm[r[9]][2]: problems.append(("대회 코드 출전 행과 다름", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
# 골 수·분이 경기별 Transfermarkt 선수 경기 성적과 맞는지
api_g = collections.Counter(); api_a = collections.Counter()
for g in GAMES:
    api_g[ldate(g)] += int(g["goals"] or 0)
gcount = collections.Counter(r[9] for r in E if r[0] == "g")
for d in set(api_g) | set(gcount):
    if api_g[d] != gcount[d]: problems.append(("골 수 API와 다름", d, api_g[d], gcount[d]))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const TOT_E={J(E)};\nconst TOT_M={J(M)};\nconst TOT_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG, "seasons": SEASONS},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in SEASONS.items(): print(" ", k, v)
