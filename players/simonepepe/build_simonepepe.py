#!/usr/bin/env python3
"""Simone Pepe: raw/ -> simonepepe.json + src/data/spe.js (판정 근거는 judgments.md)

  python3 players/simonepepe/build_simonepepe.py            # 파일 쓰기
  python3 players/simonepepe/build_simonepepe.py --debug    # Elo 출처 목록
  python3 players/simonepepe/build_simonepepe.py --fm       # FotMob 골 대조(2010-11 이후)

입력: raw/tm_games.csv(출전 397경기), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(Transfermarkt 순위표),
      elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료; 환경 변수 SOC_ELO로 다른 폴더 지정 가능).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다. 폴리타노·디 나탈레 빌드 스크립트와 같은 구조.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.environ.get("SOC_ELO") or os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "spe.js")
OUT_JSON = os.path.join(HERE, "simonepepe.json")
ME = "시모네 페페"
GAP = "2014-08-01"   # 도움 출처 기준일(이전 Transfermarkt, 이후 Transfermarkt∩FotMob 또는 다른 출처 2곳)
CUTOFF = "2026-11-18"
CLUBS = {"5514": "레코", "1415": "테라모", "458": "팔레르모", "1408": "피아첸차", "410": "우디네세",
         "1390": "칼리아리", "506": "유벤투스", "862": "키에보", "2921": "페스카라"}

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
EXCL_G = {}

# 도움 제외(Transfermarkt 리포트·선수 경기 성적이 도움으로 셌지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    "2940910|38": "PK 유도(2002.11.3 테라모-줄리아노바 파이에타 PK 골, 'Penalty: Fouled player')",
    "927290|60": "PK 유도(2008.11.6 UEFA컵 스파르타크 모스크바 원정 콸리아렐라 PK 골, 'Penalty: Fouled player')",
    "1047685|13": "PK 유도(2011.5.9 유벤투스-키에보 델 피에로 PK 골, 'Penalty: Fouled player'; FotMob도 도움 없음)",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2532969|24": "2015.3.5 코파 이탈리아 4강 1차전 피오렌티나전 요렌테 24분 헤딩 골: 유벤투스 공식 경기 기사('Llorente … incorna il traversone di Pepe')·Sky Sports 경기 기사('Pepe … provided a perfect cross from the right')·Forza Italian Football('Simone Pepe's dinked in a lovely ball')",
}
# FotMob 단독 도움(Transfermarkt 없음)으로 넣지 않은 것: tm gameId|FotMob 분 -> 이유
FM_ONLY_EXCL = {
    "2604308|60": "2016.4.20 키에보-프로시노네 60분 사르도 골: FotMob과 같은 계열 데이터 사이트(voetbalkrant·statslook)만 페페 도움, Transfermarkt는 도움 없음, PA(ESPN) 경기 기사에 도움자 없음 → 독립 출처 2곳 없음",
}
# FotMob만 페페 골로 적은 것(넣지 않음)
FM_ONLY_GOAL_EXCL = {
    "2604032|24": "2015.9.27 사수올로-키에보 24분 동점골: FotMob·ESPN 기록란·위키백과는 페페 골, Transfermarkt('Deflected shot on goal')·LaPresse 경기 기사(코너킥을 팔로스키가 머리로 돌려놓고 카차토레가 이미 선을 넘은 공을 건드림)·PA 경기 기사(ESPN 본문)·Sports Mole은 팔로스키 골 → 골로 세지 않음",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "IT3A", "IT3B", "IT3P"}   # IT3P = 세리에C1 B조 승격 플레이오프(리그 비중, 폴리타노·디 나탈레 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "CIT":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 조별(2003-04·2004-05 예선 조)·1~3라운드·16강
    if cid == "ELQ": return "elq"
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선(디 나탈레 선례)
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # UEFA컵 32강(3rd round)·16강·8강
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # UEFA컵·유로파 조별, 코파 이탈리아 예선 조
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    if cid in ("CL", "EL", "ELQ", "UEFA", "CIT"):
        return [leg, home, fu, ft, 1, 1]   # 원정 다득점·연장(UEFA 2020-21까지, 코파 이탈리아 2021-22까지)
    sys.exit("합산 규칙 없음 " + cid + " " + gid)

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
MANUAL_ALIAS = {"inter milan": "inter", "ac parma": "parma calcio 1913", "parma ac": "parma calcio 1913",
                "us avellino": "us avellino 1912", "torino calcio": "torino fc"}
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
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))

# 세리에A 20팀 순위값(기존 자료) → 표준 곡선(디 나탈레·폴리타노 스크립트와 같음)
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

SB_MEAN, SB_SD = 1577.78, 51.24   # 세리에B(문서 4절)
C1_MEAN = 1416.56                 # 세리에C1(3부): 인시녜·디 나탈레 자료와 같은 모형

def model(lg, season, r, n):
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        assert n == 20, (season, n)
        return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "IT2":
        m = ents_map("세리에B", season)
        if r in m: return m[r], f"세리에B {season} {r}위"
        return int(round(SB_MEAN + SB_SD * curve(r, n))), f"세리에B {season} {r}위"
    if lg in ("IT3A", "IT3B"):
        grp = lg[-1]
        return int(round(C1_MEAN + SB_SD * curve(r, n))), f"세리에C1 {grp}조 {season} {r}위/{n}팀 (추정)"
    return None

RANK_LG = ["IT1", "IT2", "IT3B", "IT3A"]
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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    euro = cid in ("CL", "EL", "ELQ", "UEFA")
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
    return g["date_local_tm_report"] or g["date_local_computed"]
for g in GAMES:
    if g["date_local_tm_report"] and g["date_local_tm_report"] != g["date_local_computed"]:
        sys.exit("리포트 날짜와 계산 날짜 다름 " + g["gameId"])
    if not g["playedMinutes"]: sys.exit("출전 분 없음 " + g["gameId"])
    if g["club_id"] not in CLUBS: sys.exit("모르는 클럽 " + g["gameId"])

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def fm_min(r):
    return int(r["time"]) + int(r["overloadTime"] or 0)

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["pepe_assist"] == "1":
            FM_ASSIST[gid].append(fm_min(r))

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

def before(g, side_home, score_after):
    our_home = g["venue"] == "H"
    if g["gameId"] in INFO and (INFO[g["gameId"]]["home_id"] == g["club_id"]) != our_home: sys.exit("홈·원정 불일치 " + g["gameId"])
    h, a = map(int, score_after.split("-"))
    if side_home: h -= 1
    else: a -= 1
    return (h, a) if our_home else (a, h), side_home == our_home

used_excl, used_add = set(), set()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["pepe_scorer"] == "1", e["pepe_assist_other"] == "1", e["pepe_self_assist"] == "1"
    if iss: judg.append(("본인 PK 골의 본인 도움(도움 아님)", ldate(g), e["minute"]))
    if not (isg or isa): continue
    (gf, ga), ours = before(g, e["side"] == "home", e["score_home_away_after"])
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
        add_row("g", mi, dm, gf, ga, int(e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        if tag in EXCL_A:
            used_excl.add(tag)
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal") or e["assist_type"].startswith("Handball") or e["assist_type"].startswith("Deflect"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP:
            if tag in ADD_CONFIRMED: used_add.add(tag)
            elif not any(abs(t - mi) <= 3 for t in FM_ASSIST.get(gid, [])):
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)
if set(EXCL_A) - used_excl: sys.exit("쓰이지 않은 도움 제외 " + str(set(EXCL_A) - used_excl))
if set(ADD_CONFIRMED) - used_add: sys.exit("쓰이지 않은 도움 추가 " + str(set(ADD_CONFIRMED) - used_add))

# FotMob 단독 도움·골이 판정 목록 밖에 없는지
for gid, evs in FM_EV.items():
    if gid not in G: continue
    for r in evs:
        t = fm_min(r)
        if r["pepe_assist"] == "1":
            tm = [e for e in EVENTS if e["gameId"] == gid and e["pepe_assist_other"] == "1" and abs(minute(e["minute"])[0] - t) <= 3]
            if not tm and f"{gid}|{t}" not in FM_ONLY_EXCL:
                sys.exit(f"FotMob 단독 도움 판정 누락 {gid} {t}")
        if r["pepe_scorer"] == "1" and r["pen_shootout_event"] != "True":
            tm = [e for e in EVENTS if e["gameId"] == gid and e["pepe_scorer"] == "1" and abs(minute(e["minute"])[0] - t) <= 4]
            if not tm and f"{gid}|{t}" not in FM_ONLY_GOAL_EXCL:
                sys.exit(f"FotMob 단독 골 판정 누락 {gid} {t}")

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
    for x in ELO_LOG: print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["pepe_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV: continue
    fg = [r for r in FM_EV[gid] if r["pepe_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(evs, fg):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty")
        if tpk != fpk or abs(minute(t["minute"])[0] - fm_min(f)) > 1 or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], t["score_home_away_after"], f["newScore_home_away"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 시즌·클럽별
def season_calc(d, club):
    """계산기 시즌 구분(유벤투스 7월 10일 기준, 그 밖은 8월 1일 기준)"""
    y = int(d[:4])
    cut = "07-10" if club == "506" else "08-01"
    s = y if d[5:] >= cut else y - 1
    return f"{s}-{str(s + 1)[2:]}"
CLUB_OF = {ldate(g): g["club_id"] for g in GAMES}
SEASONS = collections.OrderedDict()
for m in M:
    s = season_calc(m[0], CLUB_OF[m[0]]); SEASONS.setdefault(s, [0, 0, 0, 0]); SEASONS[s][0] += 1; SEASONS[s][3] += m[3]
for r in E:
    SEASONS[season_calc(r[9], CLUB_OF[r[9]])][1 if r[0] == "g" else 2] += 1
BYCLUB = collections.OrderedDict((c, [0, 0, 0, 0]) for c in CLUBS)
for m in M: BYCLUB[CLUB_OF[m[0]]][0] += 1; BYCLUB[CLUB_OF[m[0]]][3] += m[3]
for r in E: BYCLUB[CLUB_OF[r[9]]][1 if r[0] == "g" else 2] += 1

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
SRC = ELO_SRC
TM_API_A = sum(int(g["assists"] or 0) for g in GAMES)
N120 = sum(1 for m in M if m[3] >= 120)
last = M[-1]
bc = lambda c: "·".join(str(x) for x in BYCLUB[c][:3])
NOTE_LINES = [
    f"시모네 페페(레코·테라모·팔레르모·피아첸차·우디네세·칼리아리·유벤투스·키에보·페스카라)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 바레세전 ~ {d_(last[0])} 키에보전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·대표팀(이탈리아·청소년 대표)·유스(로마·유벤투스 프리마베라) 경기 제외",
    f"클럽별 경기·골·도움: 레코 {bc('5514')}, 테라모 {bc('1415')}, 팔레르모 {bc('458')}, 피아첸차 {bc('1408')}, 우디네세 {bc('410')}, 칼리아리 {bc('1390')}, 유벤투스 {bc('506')}, 키에보 {bc('862')}, 페스카라 {bc('2921')}. 출전 분 합계 {MIN_TOT:,}분",
    "레코(2001-02)·테라모(2002-03)는 세리에C1(3부, 이탈리아 프로 리그)이라 셈. 테라모는 리그 31경기와 승격 플레이오프 4강 마르티나전 2경기(리그 비중). 팔레르모는 2003-04(세리에B)와 2005.7~12(세리에A·UEFA컵) 두 시기, 우디네세는 2006.1~6과 2007-10 두 시기로 각각 한 클럽으로 셈. 피아첸차(2004-05 세리에B)·칼리아리(2006-07)는 임대, 유벤투스는 2010-11 임대 뒤 2011.7 완전 이적이라 한 클럽으로 셈. 로마(2001-02)는 1군 명단에만 들고 출전 없음",
    "유벤투스 프리마베라(19세 이하 팀) 나이 초과 출전 3경기(2012.11.11 시에나·2013.8.24 스페치아·2013.12.14 삼프도리아, 2골)는 유스 경기라 뺌",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(출전 분이 빈 경기 없음, 90분으로 추정한 경기 없음), 골 시각·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부), 2010-11 이후 골·도움은 FotMob 경기 이벤트와 대조함(FotMob은 2009-10 이전 자료가 없고 2011.1~5 유벤투스 11경기는 자료 없음). FotMob 라인업이 있는 115경기는 선발·교체·출전 분이 Transfermarkt와 같음",
    "위키백과와의 차이: 영어·이탈리아어 위키백과 클럽별 경기·골은 대체로 같으나, 이탈리아어판은 테라모 2002-03에 코파 이탈리아 세리에C 1경기 1골을 더 적었고(Transfermarkt 경기 목록에 없어 뺌), 영어판은 우디네세 2009-10 코파 이탈리아를 5경기로 적음(Transfermarkt 4경기). 키에보 2015-16 골은 위키백과·FotMob 3골, 여기 2골(아래 2015.9.27 사수올로전)",
    "날짜는 현지(이탈리아) 날짜. 원정 유럽 대항전도 같은 날짜",
    f"골: Transfermarkt 리포트 골 {NGo}개를 그대로 씀(선수 경기 성적과 같은 수). PK 골 {NPK}개(2008.1.23 코파 이탈리아 8강 1차전 카타니아전 70분, 2015.5.23 나폴리전 90+3분). 2015.5.23 나폴리전 PK 골은 Transfermarkt 90+3분, FotMob 90분(영어 위키백과 '90분 PK')이라 Transfermarkt 분을 씀. 실축 PK 1개(2007.5.27 칼리아리 소속 아스콜리 원정 5분, 골키퍼 선방)는 기록에 넣지 않음",
    "2015.9.27 사수올로-키에보 24분 동점골은 FotMob·위키백과가 페페 골로 적었으나, Transfermarkt('굴절된 슈팅')·LaPresse 경기 기사(코너킥을 팔로스키가 머리로 돌려놓았고 카차토레가 이미 골라인을 넘은 공을 건드림)·PA 경기 기사·Sports Mole이 팔로스키 골로 적어 페페 골로 세지 않음(Transfermarkt·FotMob 모두 페페 도움도 아님)",
    "골 시각은 Transfermarkt 리포트 분(2010-11 이후 FotMob과 1분 안팎 차이뿐, 골 뒤 스코어는 모두 같음)",
    f"도움: 2014.8.1 이전은 Transfermarkt 경기 리포트 도움, 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것과 다른 출처 2곳이 확인한 것만 씀. 도움 {NA} = Transfermarkt {TM_API_A} − PK 유도 3(2002.11.3 줄리아노바전 파이에타, 2008.11.6 UEFA컵 스파르타크 모스크바전 콸리아렐라, 2011.5.9 키에보전 델 피에로). 슈팅 리바운드·굴절·상대 자책골에 준 도움은 없음",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(FotMob은 2009-10 이전 자료가 없음). 그중 FotMob과 다른 것: 2010.9.26 칼리아리전 34분 크라시치 골·2011.12.18 노바라전 75분 콸리아렐라 골(FotMob 도움 없음), 2012.2.25 밀란 원정 83분 마트리 동점골(FotMob은 비달 도움) — 규칙대로 Transfermarkt를 따랐으나 출처가 갈림",
    "2014.8.1 이후 FotMob에 없는 Transfermarkt 도움 1개(2015.3.5 코파 이탈리아 4강 1차전 피오렌티나전 24분 요렌테 헤딩 골)는 유벤투스 공식 경기 기사·Sky Sports·Forza Italian Football이 모두 페페 크로스로 적어 넣음. FotMob에만 있는 2016.4.20 프로시노네전 60분 사르도 골 도움은 같은 계열 데이터 사이트만 적고 경기 기사로 확인되지 않아 넣지 않음(FotMob 키에보 통산 도움 3, 여기 2)",
    f"상대 Elo는 같은 경기 다른 선수 자료 값(우디네세 디 나탈레·칸드레바, 유벤투스 델 피에로 등), 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 기존 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']})",
    "순위는 Transfermarkt 최종 순위표. 세리에B 2003-04(24팀)·2004-05(22팀)는 다른 선수 자료와 같은 리그 모형(평균 약 1578), 세리에C1 B조 2002-03(18팀)은 다른 선수 자료와 같은 3부 추정 모형(평균 약 1417, '추정', 근거 약함). 제노아 2004-05는 경기 성적 1위였으나 승부 조작 징계로 공식 순위 꼴찌(22위)라 공식 순위값을 씀(2005.6.5 피아첸차-제노아전 골, 실제 전력보다 낮게 잡힘 — 유벤투스 2005-06 공식 20위 처리와 같은 방식)",
    "대회 비중: 코파 이탈리아는 국내컵(예선 조·1~3라운드·16강은 낮은 비중, 8강 이후 높은 비중, 4강·결승은 국내컵 4강·결승), 2003-04·2004-05 코파 이탈리아 예선 조는 리그식(무승부 1점). UEFA컵 1라운드(2005-06·2008-09)는 유로파리그 예선, UEFA컵 조별은 유로파 조별, 32강·16강·8강은 유로파 토너먼트 비중. 챔스 16강(2015.3.18 도르트문트 원정 9분)은 챔스 16강",
    f"두 경기 합산(코파 이탈리아 2003-04 16강 로마·2007-08 8강 카타니아·2014-15 4강 피오렌티나, UEFA컵 2008-09 1라운드 도르트문트·32강 레흐 포즈난·16강 제니트) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음). 승부차기 2경기(2008.10.2 UEFA컵 도르트문트전, 2009.1.21 코파 이탈리아 8강 삼프도리아전, 둘 다 120분)는 승부차기 골을 스코어에 넣지 않음(페페 골·도움 없음). 120분 출전 {N120}경기",
    "2016.8.28 사수올로-페스카라전(0-3 몰수 처리)은 명단에만 들고 뛰지 않아 출전에 없음",
    "시즌 구분: 유벤투스는 7월 10일 기준(2010.7.29 유로파리그 예선 샴록 로버스 원정은 2010-11), 그 밖은 8월 1일 기준",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 세리에A 우승 2011-12~2014-15·코파 이탈리아 우승 2014-15(유벤투스), 세리에B 우승 2003-04(팔레르모). 영어 위키백과의 수페르코파 이탈리아나 2012·2013(두 경기 모두 명단 제외)과 코파 이탈리아 2011-12·챔스 2014-15 준우승은 Transfermarkt 업적에 없어 넣지 않음. AIC(선수협회) 세리에A 올해의 팀·올해의 선수 명단에는 없음",
    f"은퇴: 마지막 경기 {d_(last[0])} 키에보전(세리에A, 페스카라 교체 {last[3]}분), 2017.7.1 Transfermarkt 은퇴 처리",
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
    if m[3] < 1 or m[3] > 125: problems.append(("출전 분 범위", m))
    if m[0] > CUTOFF: problems.append(("기준일 뒤", m))
api_g = collections.Counter(); api_a = collections.Counter()
for g in GAMES:
    api_g[ldate(g)] += int(g["goals"] or 0); api_a[ldate(g)] += int(g["assists"] or 0)
gcount = collections.Counter(r[9] for r in E if r[0] == "g")
for d in set(api_g) | set(gcount):
    if api_g[d] != gcount[d]: problems.append(("골 수 API와 다름", d, api_g[d], gcount[d]))
api_pk = sum(int(g["penGoals"] or 0) for g in GAMES)
if api_pk != NPK: problems.append(("PK 골 수 API와 다름", api_pk, NPK))
acount = collections.Counter(r[9] for r in E if r[0] == "a")
A_DIFF = sorted((d, api_a[d], acount[d]) for d in set(api_a) | set(acount) if api_a[d] != acount[d])
if len(A_DIFF) != len(EXCL_A): problems.append(("도움 차이 날짜 수", len(A_DIFF), len(EXCL_A)))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const SPE_E={J(E)};\nconst SPE_M={J(M)};\nconst SPE_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg,
               "excluded_assists": EXCL_A, "added_assists_confirmed": ADD_CONFIRMED,
               "fotmob_only_assists_excluded": FM_ONLY_EXCL, "fotmob_only_goal_excluded": FM_ONLY_GOAL_EXCL,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG, "seasons": SEASONS,
               "by_club": {CLUBS[c]: v for c, v in BYCLUB.items()}, "assist_count_vs_api": A_DIFF},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for c, v in BYCLUB.items(): print(" ", CLUBS[c], v)
    for k, v in SEASONS.items(): print(" ", k, v)
    print("도움 수 API와 다른 날:", A_DIFF)
