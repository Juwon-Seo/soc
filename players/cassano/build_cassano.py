#!/usr/bin/env python3
"""Antonio Cassano: raw/ -> cassano.json + src/data/csn.js (판정 근거는 judgments.md)

  python3 players/cassano/build_cassano.py            # 파일 쓰기
  python3 players/cassano/build_cassano.py --debug    # Elo 출처 목록
  python3 players/cassano/build_cassano.py --fm       # FotMob 골 대조(2010-11 이후)
  python3 players/cassano/build_cassano.py --cross    # 계산기 수록 선수 자료와 같은 경기 대조(다른 파일은 고치지 않음)

입력: raw/tm_games.csv(출전 515경기), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(Transfermarkt 순위표),
      ROOT/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(같은 경기 대조).
디 나탈레 빌드 스크립트(build_dinatale.py)와 같은 구조. 판정 표는 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections, glob
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "csn.js")
OUT_JSON = os.path.join(HERE, "cassano.json")
ME = "안토니오 카사노"
GAP = "2014-08-01"

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
# Transfermarkt가 상대 자책골로 적었지만 카사노 골로 넣는 골: gameId|TM 분 -> (분, 이유)
ADD_G = {
    # 2008.5.17 삼프도리아-유벤투스 3-3: TM 21분 몰리나로 자책골(1-2). ESPN 경기 기록 Cassano 22', Trivela 경기 기록 Cassano (22min),
    # AFP(AFPBB) 경기 기사 '전반 22분 카사노', 이탈리아어 위키백과 시즌 문서 Cassano 22', FotMob 시즌 기록 10골(TM 9)
    "84283|21": (22, "ESPN·Trivela·AFP·이탈리아어 위키백과가 카사노 22분 골로 적음(몇몇 블로그는 몰리나로 몸에 맞고 들어갔다고 씀)"),
}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    "2251484|2": "슈팅 리바운드·상대 자책골(2013.2.10 키에보전 2분 푸지오니 자책골, 'Shot on goal')",
    "2293174|75": "상대 자책골(2013.3.14 유로파 토트넘전 75분 갈라스 자책골, 프리킥)",
    "2359251|40": "슈팅 리바운드(2013.9.25 아탈란타전 40분 파롤로 골, 'Shot on goal')",
    "931911|75": "PK 유도(2008.12.14 레조나전 75분 벨루치 PK 골, 'Penalty: Fouled player')",
    # 2014.8.1 이후 Transfermarkt 단독
    "2604146|19": "2014.8 이후 Transfermarkt 단독. 삼프도리아 구단 기사('부르디소가 걷어내다 미끄러져 공이 떠올라 소리아노가 발리')·Forza Italian Football('부르디소가 걷어내지 못해 공이 떠오름')은 상대 수비 맞고 굴절된 공으로 적고 FotMob(Opta)도 도움 없음 → 굴절로 보고 뺌(ANSA·AGI·Tuttosport는 카사노가 소리아노에게 내줬다고만 씀)",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {}
# Transfermarkt에 없고 FotMob + 다른 출처가 확인해 넣는 도움: (gameId, 분, 표시 분, 득점자, 이유)
ADD_A = [
    ("1076009", 94, "90+4", "Zlatan Ibrahimović",
     "Transfermarkt는 피를로 도움, FotMob과 ANSA 경기 기록('49분 카사노가 페널티 지역의 이브라히모비치를 찾아줌', Blitz quotidiano 게재)이 카사노 도움"),
]
# FotMob에만 있고 넣지 않은 도움
FM_ONLY = [
    "2016.1.5 제노아전 39분 에데르 골(FotMob은 카사노 도움, Transfermarkt는 도움 없음. 삼프도리아 구단·ANSA·Forza Italian Football 경기 기사는 카사노가 카르보네로와 2대1 패스를 한 뒤 카르보네로의 크로스가 바헤투 쪽에서 막히고 흘러나온 공을 에데르가 찼다고 적어 카사노 도움이 아님)",
]

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "ES1"}
CUP = {"CIT", "CDR"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 1~4라운드·16강
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 2002-03 2차 조별(Group 2) 포함(토티·앙리 선례)
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
        return "elk"   # UEFA컵 2·3라운드·16강, 유로파 32강(intermediate stage)·16강
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
        if o["result_flag"]: sys.exit("1차전 연장·승부차기 " + gid)
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    # 원정 다득점·연장: UEFA 대회(2020-21까지), 코파 이탈리아(2021-22까지), 코파 델 레이 모두 적용
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
MANUAL_ALIAS = {"inter milan": "inter", "ac parma": "parma calcio 1913", "parma ac": "parma calcio 1913"}
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
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 7: 1762, 8: 1743, 9: 1728, 10: 1713, 11: 1704, 12: 1697,
        13: 1690, 14: 1676, 15: 1657, 16: 1645, 17: 1633, 18: 1614}
SB_MEAN, SB_SD = 1577.78, 51.24
C1_MEAN = 1416.56

def model(lg, season, r, n):
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        if n == 18: return SA18[r], f"세리에A {season} {r}위"
        assert n == 20, (season, n)
        return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "IT2":
        m = ents_map("세리에B", season)
        if r in m: return m[r], f"세리에B {season} {r}위"
        return int(round(SB_MEAN + SB_SD * curve(r, n))), f"세리에B {season} {r}위"
    if lg == "IT3B":
        return int(round(C1_MEAN + SB_SD * curve(r, n))), f"세리에C(레가 프로 1) B조 {season} {r}위/{n}팀 (추정)"
    if lg == "ES1":
        m = ents_map("라리가", season)
        if r in m: return m[r], f"라리가 {season} {r}위"
    return None

RANK_LG = ["IT1", "IT2", "IT3B", "ES1"]

# 순위표·통합표로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {
    (key("HNK Hajduk Split"), "2003-04"): (1480, "크로아티아 2003-04 1위 (추정, 다른 선수 자료의 하이두크 스플리트 2000-01 1위 1480과 같음)"),
    (key("Gaziantepspor"), "2003-04"): (1520, "쉬페르리그 2003-04 4위 (추정, 다른 선수 자료 쉬페르리그 2006-07 4위 1520과 같음)"),
    (key("Red Star Belgrade"), "2005-06"): (1520, "세르비아·몬테네그로 2005-06 1위 (추정, 다른 선수 자료 파르티잔 2004-05·레드스타 2006-07 1위 1520과 같음)"),
    (key("FBK Kaunas (- 2012)"), "2008-09"): (1300, "리투아니아 2008 2위 (추정, 다른 선수 자료 카우나스 2005 1위·잘기리스 2018 2위 1300과 같음)"),
    (key("FK Partizan Belgrade"), "2012-13"): (1520, "세르비아 2012-13 1위 (추정, 다른 선수 자료 파르티잔 2011-12 1위 1520과 같음)"),
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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    euro = cid in ("CL", "CLQ", "EL", "ELQ", "UEFA")
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if euro else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
        return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, eu))
        if t and k in t:
            r, n = t[k]
            res = model(lg, eu, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg))
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
        if r["ac_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

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

def score_before(e, g):
    inf = INFO[e["gameId"]]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    return ours, gf, ga

used_excl, used_add, used_addg = set(), set(), set()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["ac_scorer"] == "1", e["ac_assist_other"] == "1", e["ac_self_assist"] == "1"
    tag = f"{gid}|{e['minute']}"
    if iss: judg.append(("본인 PK 골의 본인 도움(도움 아님)", ldate(g), e["minute"]))
    if tag in ADD_G: isg = True
    if not (isg or isa): continue
    ours, gf, ga = score_before(e, g)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    et = int(INFO[gid]["result_flag"] in ("AET", "pens") and mi > 90 and not dm)
    if mi > 120: sys.exit("승부차기 이벤트 " + tag)
    if isg:
        if tag in ADD_G:
            used_addg.add(tag)
            if not ours: sys.exit("ADD_G 편 이상 " + tag)
            mi = ADD_G[tag][0]
            judg.append(("TM 상대 자책골 → 카사노 골", d, opp, e["minute"], ADD_G[tag][1]))
            add_row("g", mi, 0, gf, ga, 0, 0, tie, comp, ko, d, opp, cid, et)
        elif e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골"))
        else:
            add_row("g", mi, dm, gf, ga, int(e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        if tag in EXCL_A:
            used_excl.add(tag)
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal") or e["assist_type"].startswith("Handball"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP:
            if tag in ADD_CONFIRMED: used_add.add(tag)
            elif not any(abs(t - mi) <= 2 or abs(t - int(e["minute"].split("+")[0])) <= 2 for t in FM_ASSIST.get(gid, [])):
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)
for nm_, s_, u_ in (("도움 제외", EXCL_A, used_excl), ("다른 출처 확인 도움", ADD_CONFIRMED, used_add), ("자책골→골", ADD_G, used_addg)):
    if set(s_) - u_: sys.exit("쓰이지 않은 " + nm_ + " " + str(set(s_) - u_))

# Transfermarkt에 없는 도움(FotMob + 다른 출처)
for gid, mi, dm, scorer, why in ADD_A:
    g = G[gid]
    ev = [e for e in EVENTS if e["gameId"] == gid and minute(e["minute"])[0] == mi and norm(e["scorer"]) == norm(scorer)]
    if len(ev) != 1: sys.exit("ADD_A 골 없음 " + gid)
    ours, gf, ga = score_before(ev[0], g)
    if not ours: sys.exit("ADD_A 편 이상 " + gid)
    judg.append(("FotMob+다른 출처 도움 추가", ldate(g), scorer, mi, why))
    add_row("a", mi, dm, gf, ga, 0, scorer, tie_of(g), comp_of(g["competitionId"], g["round"]), ko_of(g), ldate(g), g["opponent"].strip(), g["competitionId"], 0)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

def sk(r):
    return (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1)
rows.sort(key=sk)
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
    if e["ac_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV: continue
    fg = [r for r in FM_EV[gid] if r["ac_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"], t["score_home_away_after"], f["newScore_home_away"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 계산기 수록 선수 자료와 같은 경기 대조(다른 파일은 고치지 않음)
def load_all():
    out = {}
    for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
        b = os.path.basename(fn)
        if b in ("hon.js", "csn.js"): continue
        s = open(fn, encoding="utf-8").read()
        m = re.search(r"const ([A-Z0-9]+)_E=(\[.*?\]);\n", s, re.S)
        if m: out[b] = json.loads(m.group(2))
    return out
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
CROSS = []
if "--cross" in sys.argv or len(sys.argv) == 1:
    ALL = load_all()
    mdate = {m[0]: m for m in M}
    for fn, ent in ALL.items():
        for x in ent:
            if x[9] not in mdate: continue
            same_team = key(x[1]) == key(mdate[x[9]][1])
            if not same_team: continue   # 상대 팀 쪽 자료(카사노 팀이 상대)는 Elo 대상이 아님
            # 같은 팀 동료 행
            if x[0] == "a" and norm(x[13]) == norm("Antonio Cassano"):
                hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
                CROSS.append((fn, "동료 도움→카사노 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
            elif x[0] == "g":
                mine = sorted([r for r in E if r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
                tm = [e for e in EVENTS if e["ac_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 3]
                if mine: CROSS.append((fn, "카사노 도움→동료 골", x[9], x[4], cmp_rows(mine[0], x) or "같음"))
                elif tm: CROSS.append((fn, "TM 카사노 도움을 뺀 동료 골", x[9], x[4], tm[0]["assist_type"]))
            # 같은 경기 Elo·lv·대회
            r0 = [r for r in E if r[9] == x[9]]
            if r0:
                dd = [t for t in cmp_rows(r0[0], x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                CROSS.append((fn, "같은 경기", x[9], x[1], dd or "같음"))
            else:
                CROSS.append((fn, "같은 경기(카사노 기록 없음)", x[9], x[1], "참고"))
    # 내 도움 행의 득점자가 수록 선수인데 그 선수 파일에 골 행이 없는 경우
    covered = {(c[2], c[3]) for c in CROSS if c[1] == "카사노 도움→동료 골"}
    # 카사노 골의 TM 도움자가 수록 선수인 경우 그 파일에 도움 행이 있는지
    for e in EVENTS:
        if e["ac_scorer"] == "1" and e["gameId"] in G and e["assist_player"]:
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            hits = [(fn, x) for fn, ent in ALL.items() for x in ent if x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 3]
            team_files = {fn for fn, ent in ALL.items() for x in ent if x[9] == d and key(x[1]) == key(G[e["gameId"]]["opponent"].strip())}
            if not hits and team_files:
                CROSS.append(("-", "TM 동료 도움(파일 없음 확인)", d, e["minute"], e["assist_player"] + " / " + e["assist_type"] + " / 같은 경기 파일 " + ",".join(sorted(team_files))))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] not in ("같음", "참고"): print(c)
    print(collections.Counter(c[1] for c in CROSS))
    print(sorted({c[0] for c in CROSS}))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("barcs", "2001-07-01"), ("romcs", "2006-01-04"), ("rmacs", "2007-08-13"), ("smpcs", "2011-01-03"),
         ("milcs", "2012-08-22"), ("intcs", "2013-07-04"), ("parcs", "2015-08-09"), ("smpcs", None)]
TM_CLUB = {"332": "barcs", "12": "romcs", "418": "rmacs", "1038": "smpcs", "5": "milcs", "46": "intcs", "130": "parcs"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
ORDER = ["barcs", "romcs", "rmacs", "smpcs", "milcs", "intcs", "parcs"]
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in ORDER)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
def part(lo, hi):
    v = [0, 0, 0]
    for m in M:
        if lo <= m[0] < hi: v[0] += 1
    for r in E:
        if lo <= r[9] < hi: v[1 if r[0] == "g" else 2] += 1
    return v
SMP1, SMP2 = part("2007-08-13", "2011-01-03"), part("2015-08-09", "2099-01-01")

SEASONS = collections.OrderedDict()
for m in M:
    s = season_eu(m[0]); SEASONS.setdefault(s, [0, 0, 0, 0]); SEASONS[s][0] += 1; SEASONS[s][3] += m[3]
for r in E:
    SEASONS[season_eu(r[9])][1 if r[0] == "g" else 2] += 1

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
POST_A = NA - PRE_A
SRC = ELO_SRC
TM_A = sum(1 for e in EVENTS if e["ac_assist_other"] == "1" and e["gameId"] in G)
NOTE_LINES = [
    f"안토니오 카사노(바리·로마·레알 마드리드·삼프도리아·AC 밀란·인테르·파르마)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 레체전 ~ {d_(M[-1][0])} 제노아전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    f"클럽별 경기·골·도움: 바리 {c3(ST['barcs'])}, 로마 {c3(ST['romcs'])}, 레알 마드리드 {c3(ST['rmacs'])}, 삼프도리아 {c3(ST['smpcs'])}(2007-2011 {c3(SMP1)}, 2015-16 {c3(SMP2)}), AC 밀란 {c3(ST['milcs'])}, 인테르 {c3(ST['intcs'])}, 파르마 {c3(ST['parcs'])}. 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(출전 분이 빈 경기 없음, 90분으로 추정한 경기 없음), 골 시각·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(출전한 {NG}경기 전부), 2010-11 이후 골·도움은 FotMob 경기 이벤트와 대조함. 위키백과(영어·이탈리아어) 시즌별 경기·골도 대조함",
    "모든 시즌이 세리에A·라리가(1부 프로 리그). 유스 경기와 이탈리아 대표팀 경기는 뺌. 1998-99 바리 명단에 들었으나 출전 없음. 2016-17 삼프도리아(명단 제외, 2017.1 계약 해지)·2017년 7월 헬라스 베로나(친선경기만)는 공식 경기 출전 없음",
    "수페르코파 이탈리아나(로마 2001, 밀란 2011)는 우승 멤버로 기록되지만 출전 없음",
    "날짜는 현지 날짜(Transfermarkt 경기 리포트). 2003.2.5 로마, 2006.1.18·1.25 레알 마드리드 경기는 선수 경기 성적의 날짜(UTC)가 하루 앞이라 리포트 날짜를 씀",
    f"골: Transfermarkt 리포트 골 {NGo - len(ADD_G)}개 + 1개. 2008.5.17 유벤투스전 22분 골은 Transfermarkt가 21분 몰리나로 자책골로 적었으나 ESPN·Trivela 경기 기록, AFP 경기 기사, 이탈리아어 위키백과 시즌 문서가 카사노 22분 골로 적어 카사노 골로 셈(위키백과 시즌 골 수 10과 같아짐). PK 골 {NPK}개는 골 유형 'Penalty' 기준",
    "2004.3.21 라치오-로마 더비는 48분 0-0에서 중단된 뒤 2004.4.21에 다시 치러 다시 치른 경기만 셈(중단 경기는 결과가 무효라 출전 여부와 관계없이 넣지 않음, 골·도움 없음)",
    "2010-11 이후 골은 FotMob 경기 이벤트와 분·스코어·PK가 모두 맞음(FotMob 기록이 없는 2011년 2~5월 4경기는 Transfermarkt만 근거, 추가시간을 '45+'·'90+'로만 적은 FotMob 차이는 Transfermarkt 분을 씀)",
    f"도움: 2014.8.1 이전은 Transfermarkt 경기 리포트 도움, 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것과 다른 출처 2곳이 확인한 것만 씀. 도움 {NA} = Transfermarkt 리포트 {TM_A} − 슈팅 리바운드 2(2013.2.10 키에보전 2분 푸지오니 자책골, 2013.9.25 아탈란타전 40분 파롤로 골, 'Shot on goal') − 상대 자책골에 준 도움 1(2013.3.14 유로파 토트넘전 75분 갈라스 자책골) − PK 유도 1(2008.12.14 레조나전 75분 벨루치 PK 골) − 굴절 1(아래 2016.1.5 소리아노 골) + FotMob·ANSA가 확인한 1(아래 2011.5.10 이브라히모비치 골). Transfermarkt 리포트가 본인 PK 골에 본인 도움(PK 유도)으로 적은 3개(2009.5.24 우디네세전, 2010.4.18 AC 밀란전, 2011.4.2 인테르전)는 도움으로 세지 않음",
    "2011.5.10 코파 이탈리아 준결승 2차전 팔레르모전 90+4분 이브라히모비치 골은 Transfermarkt가 피를로 도움으로 적었으나 FotMob과 ANSA 경기 기록('카사노가 페널티 지역의 이브라히모비치를 찾아줌')이 카사노 도움이라 카사노 도움으로 셈",
    "1999~2005년(바리·로마) Transfermarkt 경기 리포트는 팀 골의 50~70%에만 도움자를 적었고 위키백과·FotMob에도 경기별 도움이 없어 이 시기 도움은 리포트에 있는 것만 넣음. 실제 도움보다 적게 잡혔을 수 있음",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(2010~14년 FotMob 경기 이벤트에 없는 도움 21개 포함 — 이 시기 FotMob은 도움이 비어 있는 골이 많음). 도움 유형 칸이 빈 6개(2005.12.1 UEFA컵 츠르베나 즈베즈다전 논다, 2006.3.5 아틀레티코전 바치스타, 2008.4.6 리보르노전 보나촐리, 2008.5.17 유벤투스전 몬텔라, 2008.9.18 UEFA컵 카우나스전 보나촐리 2골)와 2014.5.18 리보르노전 아마우리 골(FotMob도 카사노 도움)도 일반 도움으로 셈",
    f"2014.8.1 이후 도움 {POST_A}개는 모두 FotMob도 카사노 도움으로 적음. 뺀 Transfermarkt 단독 도움: 2016.1.5 제노아전 19분 소리아노 골(삼프도리아 구단 기사·Forza Italian Football은 카사노 패스가 상대 수비 부르디소 발에 맞고 떠오른 공을 소리아노가 찼다고 적어 굴절로 봄, FotMob도 도움 없음)",
    "FotMob에만 있는 도움 1개는 넣지 않음: " + "; ".join(FM_ONLY),
    f"상대 Elo는 같은 경기를 다룬 다른 수록 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위를 기존 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "순위는 Transfermarkt 최종 순위표. 세리에B(레체 2009-10 1위, 헬라스 베로나 2012-13 2위)는 다른 선수 자료와 같은 리그 모형(평균 1578), 레체 2013-14 세리에C(레가 프로 1) B조 3위/17팀은 다른 선수 자료와 같은 3부 추정 모형(평균 약 1417, 근거 약함)",
    "직접 추정(모두 '추정'): 하이두크 스플리트 2003-04(크로아티아 1위) 1480, 가지안테프스포르 2003-04(튀르키예 4위) 1520, 츠르베나 즈베즈다 2005-06(세르비아·몬테네그로 1위) 1520, 카우나스 2008(리투아니아 2위) 1300, 파르티잔 2012-13(세르비아 1위) 1520. 다른 선수 자료의 같은 팀 다른 시즌 값이나 같은 리그 비슷한 순위 값에 맞춘 것으로 근거 약함",
    "대회 비중: 코파 이탈리아·코파 델 레이는 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중, 준결승·결승 가산), 챔스 2002-03 2차 조별은 조별, 챔스 예선 플레이오프(2010 베르더 브레멘)는 챔스 예선, UEFA컵 1라운드는 유로파 예선, UEFA컵 조별·유로파 조별은 유로파 조별, UEFA컵 2·3라운드·16강과 유로파 32강·16강은 유로파 토너먼트",
    f"두 경기 합산(UEFA 대회 예선·토너먼트, 코파 이탈리아 두 경기 라운드와 2003·2005 결승, 코파 델 레이) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 적용). 카사노가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움. 2013.3.14 유로파 16강 2차전 토트넘전 110분 알바레스 골 도움은 연장 시간 기록",
    "승부차기: 2005.3.16 코파 이탈리아 준결승 2차전, 2009.5.13 코파 이탈리아 결승(라치오전)은 승부차기 골을 스코어에 넣지 않음",
    "시즌 구분: 8월 1일 기준",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 라리가 2006-07(레알 마드리드), 세리에A 2010-11(AC 밀란), 수페르코파 이탈리아나 2001(로마)·2011(AC 밀란). 오스카 델 칼초 최우수 젊은 선수(2001·2003)는 신인·젊은 선수 상이라 넣지 않음. 유로 2012 준우승 등 대표팀 기록은 뺌",
    "2016.5.8 제노아전(삼프도리아)이 마지막 공식 경기(Transfermarkt 2018.10 은퇴)",
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
api_g = collections.Counter(); api_a = collections.Counter()
for g in GAMES:
    api_g[ldate(g)] += int(g["goals"] or 0); api_a[ldate(g)] += int(g["assists"] or 0)
gcount = collections.Counter(r[9] for r in E if r[0] == "g")
G_DIFF = sorted((d, api_g[d], gcount[d]) for d in set(api_g) | set(gcount) if api_g[d] != gcount[d])
if G_DIFF != [("2008-05-17", 0, 1)]: problems.append(("골 수 API와 다름", G_DIFF))
acount = collections.Counter(r[9] for r in E if r[0] == "a")
A_DIFF = sorted((d, api_a[d], acount[d]) for d in set(api_a) | set(acount) if api_a[d] != acount[d])
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const CSN_E={J(E)};\nconst CSN_M={J(M)};\nconst CSN_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG, "seasons": SEASONS,
               "goal_count_vs_api": G_DIFF, "assist_count_vs_api": A_DIFF},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    for k, v in SEASONS.items(): print(" ", k, v)
    print("도움 수 API와 다른 날:", A_DIFF)
