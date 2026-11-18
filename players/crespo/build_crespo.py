#!/usr/bin/env python3
"""Hernán Crespo: raw/ -> crespo.json + src/data/crs.js (판정 근거는 judgments.md)

  python3 players/crespo/build_crespo.py            # 파일 쓰기
  python3 players/crespo/build_crespo.py --debug    # Elo 출처 목록
  python3 players/crespo/build_crespo.py --cross    # 같은 경기 다른 선수 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/ranks.txt(순위표), raw/rsssf/*.html(아르헨티나 리그 경기 줄),
      <ROOT>/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(동료 대조).
비에리 build 스크립트를 바탕으로 함(리켈메 스크립트의 아르헨티나 모형).
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "crs.js")
OUT_JSON = os.path.join(HERE, "crespo.json")
ME = "에르난 크레스포"
INCLUDE_RSSSF = True   # Transfermarkt에 없는 리버 리그 경기 중 RSSSF 경기 줄로 확인되는 5경기(judgments.md 1절)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 판정 표
MIN_FIX = {}
EXCL_G = {}
# 도움 제외: gameId|분 -> 이유 (유형 'Shot on goal' 4개, judgments.md 4절)
EXCL_A = {
    "1022507|84": "슈팅 리바운드(Shot on goal, 비에리)",
    "2211401|11": "슈팅 리바운드(Shot on goal, 칸나바로)",
    "3296050|77": "슈팅 리바운드(Shot on goal, 소린)",
    "65264|41": "슈팅 리바운드(Shot on goal, 사네티)",
}
# 남미 대회 날짜: RSSSF·영어 위키백과가 같으면 그 날짜, 다르면 Transfermarkt와 맞는 쪽(judgments.md 2절)
DATE_FIX = {
    "3295750": "1995-04-13",   # 세로(H) TM 3.18 / RSSSF·위키 4.13
    "3295752": "1995-04-19",   # 페냐롤(H) TM 4.8 / RSSSF·위키 4.19
    "3263156": "1996-04-11",   # 미네르벤(H) TM·위키 4.11 / RSSSF 4.12
    "3263152": "1996-03-28",   # 카라카스(A) TM·위키 3.28 / RSSSF 3.29
    "3263158": "1996-04-19",   # 카라카스(H) API 4.19 23:00Z·RSSSF 4.19 / 위키 4.18 / TM 리포트 4.20
    "3296021": "1996-05-01",   # 스포르팅 크리스탈(A) RSSSF·위키 5.1 / API 5.2 23:00Z / 리포트 5.3
    "3296042": "1996-05-15",   # 산로렌소(A) RSSSF·위키 5.15 / API 5.16 00:00Z / 리포트 5.16
    "3296043": "1996-05-22",   # 산로렌소(H) RSSSF·위키·API 5.22 23:00Z / 리포트 5.23
    "3296050": "1996-06-05",   # 우니베르시다드 데 칠레(A) RSSSF·위키 6.5 / 리포트 6.6
    "3296051": "1996-06-12",   # 우니베르시다드 데 칠레(H) RSSSF·위키 6.12
    "3296054": "1996-06-19",   # 결승 1차전 RSSSF·위키 6.19 / 리포트 6.20
    "3296055": "1996-06-26",   # 결승 2차전 RSSSF·위키 6.26 / 리포트 6.27
    "4978177": "1995-06-25",   # 클라우수라 1995 벨레스(A): 리포트·일정 없음, API 날짜
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "GB1", "ARGC", "ARG1", "ITPO"}   # ITPO = 2000.5.23 세리에A 챔스 진출 플레이오프(비에리 같은 경기 lg)
CUPS = {"CIT", "FAC", "CGB", "ARC1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round"): return "dk"   # 리그컵 8강(5라운드)·FA컵 6라운드 = 8강
        return "dc"
    if cid in ("SCI", "GBCS"): return "df"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "CLI":
        if r.startswith("group") or r.startswith("last 16"): return "lib"
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
    if cid == "SCSA":
        if r.startswith("last 16"): return "csa"
        return "csak"
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
    if g["competitionId"] in ("CLI", "SCSA"):
        return [leg, home, fu, ft, 0, 0]   # 리베르타도레스 2004년까지: 원정 다득점·연장 없음(승부차기), 리켈메 선례
    return [leg, home, fu, ft, 1, 1]       # UEFA 대회·코파 이탈리아: 원정 다득점·연장

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
MANUAL_ALIAS = {"inter milan": "inter", "ac parma": "parma"}
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
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))
# RSSSF 최종 순위표와 다른 곳(동률 공동 순위, v1.157 규칙): 클라우수라 1996 라싱·우라칸 29점 공동 7위(TM 라싱 8위)
RANK_FIX = {("ARGC", "1995-96", "Racing Club"): 7}
for (lg, se, nm), r in RANK_FIX.items():
    k = key(nm); RANKS[(lg, se)][k] = (r, RANKS[(lg, se)][k][1])

def ents_map(prefix, season):
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
def half_up(x): return int(x + 0.5)
SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 7: 1762, 8: 1743, 9: 1728, 10: 1713, 11: 1704, 12: 1697,
        13: 1690, 14: 1676, 15: 1657, 16: 1645, 17: 1633, 18: 1614}

def mid_fill(m, r):
    lo = max([k for k in m if k < r], default=None); hi = min([k for k in m if k > r], default=None)
    if lo is None or hi is None: return None
    return half_up(m[lo] + (m[hi] - m[lo]) * (r - lo) / (hi - lo))

def model(lg, season, r, n):
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        if n == 18: return SA18[r], f"세리에A {season} {r}위"
        v = mid_fill(m, r)
        return (v if v else SA[r - 1]), f"세리에A {season} {r}위"
    if lg == "GB1":
        m = ents_map("프리미어리그", season)
        if r in m: return m[r], f"프리미어리그 {season} {r}위"
        v = mid_fill(m, r)
        return (v, f"프리미어리그 {season} {r}위") if v else None
    if lg in ("ARG1", "ARGC"):   # 리켈메·포를란 선례: 반시즌 표, 평균 1583·흩어짐 63
        y0 = int(season[:4])
        t, y = ("아페르투라", y0) if lg == "ARG1" else ("클라우수라", y0 + 1)
        return half_up(1583 + 63 * curve(r, n)), f"아르헨티나 1부 {t} {y} {r}위"
    return None

# 직접 추정(모두 '추정'): (key, 시즌) -> (Elo, lv) — 골·도움 상대만 필요
MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
man("CA Cerro", "1995", half_up(1540 + 63 * curve(4, 13)),
    "우루과이 1부 1994 연간 4위/13팀 (추정, RSSSF 연간 순위를 다른 선수 자료의 우루과이 모형에 넣음)")
man("Minerven FC", "1996", 1380, "베네수엘라 1부 상위 팀 (추정, 다른 선수 자료 베네수엘라 팀 1380과 같음)")
man("Caracas FC", "1996", 1400, "베네수엘라 1부 상위 팀 (추정, 전 시즌 우승 팀, 다른 선수 자료 카라카스 우승 팀 1400과 같음)")
man("Club Sporting Cristal", "1996", 1400, "페루 1부 우승 팀 (추정, 그해·전 시즌 우승 팀, 다른 선수 자료 페루 상위 팀 1400과 같음)")
man("CD América de Cali", "1996", half_up(1580 + 63 * curve(2, 16)),
    "콜롬비아 1부 1995-96 2위/16팀 (리그 수준 추정, 다른 선수 자료의 콜롬비아 모형)")
# 유럽 대회 상대(순위표는 다른 선수 자료에서 복사한 Transfermarkt 표, raw/ranks.txt)
man("Widzew Lodz", "1997-98", 1460, "폴란드 1997-98 4위 (추정, 다른 선수 자료 폴란드 2002-03 4위 1460과 같음)")
man("Galatasaray", "1997-98", 1680, "튀르키예 1997-98 1위 (추정, 다른 선수 자료의 갈라타사라이 1위 값 1680과 같음)")
man("Fenerbahce", "1998-99", 1650, "튀르키예 1998-99 3위 (추정, 1990년대 다른 선수 자료 튀르키예 3위 1650과 같음)")
man("Kryvbas Kryvyi Rig", "1999-00", 1488, "우크라이나 1부 1999-00 3위 (추정, 다른 선수 자료 크리우바스 1998-99 3위 1488과 같음)")
man("FC Copenhagen", "2001-02", 1520, "덴마크 2001-02 2위 (추정, 다른 선수 자료 덴마크 1998-99 2위 1520과 같음)")
man("Sporting CP", "2006-07", 1795, "포르투갈 1부 2006-07 2위")   # 다른 선수 자료의 포르투갈 1부 2위 고정값(비에리 벤피카 2003-04 선례)
man("Genoa CFC", "1998-99", half_up(1577.78 + 51.24 * curve(12, 20)), "세리에B 1998-99 12위")   # 세리에B 모형(비에리·인자기 선례)

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

SA_COMP = {"CLI", "SCSA", "ARG1", "ARGC", "ARC1"}
def arg_cands(d):
    y, mo = int(d[:4]), int(d[5:7])
    if mo <= 7: return [("ARGC", f"{y-1}-{str(y)[2:]}")]
    return [("ARG1", f"{y}-{str(y+1)[2:]}")]

def opp_elo(opp, d, cid, sid=None):
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or (cid not in SA_COMP and _sub(key(x["opp"]), k)))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    if cid in SA_COMP:
        seasons = [d[:4]]
    else:
        euro = cid in ("CL", "CLQ", "UEFA", "EL")
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
    if cid in ("ARG1", "ARGC"):
        cands = [(cid, sid)]
    elif cid in SA_COMP:
        cands = arg_cands(d)
    else:
        cands = [(lg, s) for s in seasons for lg in ("IT1", "GB1")]
    for lg, s in cands:
        t = RANKS.get((lg, s))
        if t and k in t:
            r, n = t[k]
            res = model(lg, s, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg))
                return res
    return None

# ---------------------------------------------------------------- 출전
def sched_date(s):
    return datetime.strptime(s.split(" ")[1], "%d/%m/%Y").strftime("%Y-%m-%d") if s else ""
def ldate(g):
    return DATE_FIX.get(g["gameId"]) or g["date_local_tm_report"] or sched_date(g["date_tm_schedule"])

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].split(" (")[0].strip(), comp_of(g["competitionId"], g["round"]),
              MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])

# RSSSF 경기 줄로만 확인되는 리버 리그 경기(Transfermarkt 'not in squad'): 출전 분은 90분(추정, 1994.3.19는 교체 없는 선발 명단)
RSSSF_M = [["1994-03-19", "AA Argentinos Juniors", "lg", 90, "ARG1", "1993-94"],
           ["1995-08-12", "Club Atlético Belgrano", "lg", 90, "ARG1", "1995-96"],
           ["1996-03-22", "CA Vélez Sarsfield", "lg", 90, "ARGC", "1995-96"],
           ["1996-04-28", "Racing Club", "lg", 90, "ARGC", "1995-96"],
           ["1996-05-26", "CA Huracán", "lg", 90, "ARGC", "1995-96"]]
RSSSF_EST = {"1995-08-12", "1996-03-22", "1996-04-28", "1996-05-26"}
# RSSSF 골: (날짜, 분, 골 전 우리, 상대)
RSSSF_G = [("1995-08-12", 63, 0, 0), ("1995-08-12", 72, 1, 0), ("1996-03-22", 86, 1, 2),
           ("1996-04-28", 37, 0, 1), ("1996-04-28", 42, 1, 1), ("1996-05-26", 58, 1, 0)]
if INCLUDE_RSSSF:
    for d, o, c, mi, *_ in RSSSF_M:
        M.append([d, o, c, mi] + ([1] if d in RSSSF_EST else []))
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et, sid=None):
    res = opp_elo(opp, d, cid, sid)
    if res is None:
        missing_elo.add((opp, d, cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

def tm_sid(g):
    return f"{g['seasonId']}-{str(int(g['seasonId']) + 1)[2:]}"

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["crespo_scorer"] == "1", e["crespo_assist_other"] == "1", e["crespo_self_assist"] == "1"
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
    et = int(mi > 90 and (not dm or int(str(dm).split("+")[0]) >= 105))
    if et and g["gameState"] == "regularly_terminated": sys.exit("연장 판정 이상 " + gid)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].split(" (")[0].strip()
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid, et, tm_sid(g))
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal", "Deflected"):
            sys.exit("도움 유형 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et, tm_sid(g))

if INCLUDE_RSSSF:
    rm = {r[0]: r for r in RSSSF_M}
    for d, mi, gf, ga in RSSSF_G:
        r = rm[d]
        add_row("g", mi, 0, gf, ga, 0, 0, None, "lg", 0, d, r[1], r[4], 0, r[5])

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

def sort_min(r):
    return r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5
rows.sort(key=lambda r: (r[9], sort_min(r), 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
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
CROSS, SAMEGAME = [], []
OTHERS = {}
for fn in sorted(os.listdir(os.path.join(ROOT, "src", "data"))):
    if not fn.endswith(".js") or fn in ("hon.js", "crs.js"): continue
    P = fn[:-3].upper()
    try: OTHERS[fn] = load_js(fn, P)
    except Exception: continue
for fn, ent in OTHERS.items():
    # 크레스포 도움 → 다른 선수 골 / 다른 선수 도움 → 크레스포 골
    for r in E:
        if r[0] != "a": continue
        hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1])]
        if hit: CROSS.append(("크레스포 도움→" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:
        if x[0] == "a" and norm(str(x[13])) == norm("Hernán Crespo"):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn + " 도움→크레스포 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                SAMEGAME.append((fn, r[9], r[1], tuple(d) or "같음"))
                break
SAMEGAME = sorted(set(SAMEGAME))
# TM이 크레스포 도움으로 적었으나 뺀 동료 골·TM 동료 도움이 동료 파일에 없는 크레스포 골
for e in EVENTS:
    g = G.get(e["gameId"])
    if not g: continue
    d = ldate(g); mi = minute(e["minute"])[0]
    if e["crespo_scorer"] == "1" and e["assist_player"]:
        for fn, ent in OTHERS.items():
            if any(x[0] == "g" and x[9] == d for x in ent) or any(x[9] == d for x in ent):
                pass
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s_ in SAMEGAME:
        if s_[-1] != "같음": print("같은 경기 차이", s_)
    print("같은 경기", collections.Counter((s_[0], s_[-1] == "같음") for s_ in SAMEGAME))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("rivcr", "1996-07-01", "리버 플레이트", "1993~1996"), ("parcr", "2000-07-01", "파르마", "1996~2000"),
         ("lazcr", "2002-07-01", "라치오", "2000~2002"), ("intcr", "2003-07-01", "인테르", "2002~2003"),
         ("checr", "2004-07-01", "첼시", "2003~2004"), ("milcr", "2005-07-01", "AC 밀란", "2004~2005"),
         ("checr", "2006-07-01", "첼시", "2005~2006"), ("intcr", "2009-07-01", "인테르", "2006~2009"),
         ("gencr", "2010-01-29", "제노아", "2009~2010"), ("parcr", None, "파르마", "2010~2012")]
TM_CLUB = {"209": "rivcr", "130": "parcr", "398": "lazcr", "46": "intcr", "631": "checr", "5": "milcr", "252": "gencr"}
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
    if g["club_id"] != "209" and season_eu(ldate(g))[:4] != g["seasonId"]: sys.exit("시즌 불일치 " + g["gameId"])
# 기간별(클럽 시기) 합계
PERIODS = [("리버 플레이트", "1993~1996", None, "1996-07-01"), ("파르마", "1996~2000", "1996-07-01", "2000-07-01"),
           ("라치오", "2000~2002", "2000-07-01", "2002-07-01"), ("인테르", "2002~2003", "2002-07-01", "2003-07-01"),
           ("첼시", "2003~2004", "2003-07-01", "2004-07-01"), ("AC 밀란", "2004~2005", "2004-07-01", "2005-07-01"),
           ("첼시", "2005~2006", "2005-07-01", "2006-07-01"), ("인테르", "2006~2009", "2006-07-01", "2009-07-01"),
           ("제노아", "2009~2010", "2009-07-01", "2010-01-29"), ("파르마", "2010~2012", "2010-01-29", None)]
def per(lo, hi):
    inr = lambda d: (lo is None or d >= lo) and (hi is None or d < hi)
    return [sum(1 for m in M if inr(m[0])), sum(1 for r in E if r[0] == "g" and inr(r[9])),
            sum(1 for r in E if r[0] == "a" and inr(r[9])), sum(m[3] for m in M if inr(m[0]))]
ST = [(n, y, per(lo, hi)) for n, y, lo, hi in PERIODS]

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NEST = sum(1 for m in M if len(m) > 4)
NOTE_LINES = [
    f"에르난 크레스포(리버 플레이트·파르마·라치오·인테르·첼시·AC 밀란·제노아)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 산로렌소전 ~ {d_(M[-1][0])} 엘라스 베로나전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·아르헨티나 대표팀(A·올림픽) 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n}({y}) {v[0]}·{v[1]}·{v[2]}" for n, y, v in ST)
    + f". 출전 분 합계 {MIN_TOT:,}분(90분으로 추정한 {NEST}경기 포함)",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 대회 경기 전부; 크레스포 골·도움 수는 선수 경기 성적과 경기마다 같음). 파르마·라치오·인테르·첼시·밀란·제노아·파르마 시기 경기·골은 영어·이탈리아어 위키백과 클럽·시즌별 기록과 같음(밀란 2004-05 리그 골은 스페인어·이탈리아어 위키백과가 1골 많고, 파르마 1999-00 코파 이탈리아 골은 영어 위키백과가 1골 많음 — 경기별 근거가 없어 Transfermarkt 기준). 2010-11 이후 파르마 골 13개 중 11개(7경기)는 FotMob 경기 기록과 대조함(골 순서·골 뒤 스코어·PK 같음; FotMob 경기 기록이 없는 2011.1.30 제노아전 32분·2011.2.20 체세나전 64분 PK는 Transfermarkt만 근거; 2010.11.28 인테르전 36분(FotMob 34분), 2010.12.14 코파 이탈리아 피오렌티나전 연장 115·117분(FotMob 116·118분), 2011.8.21 그로세토전 90+1분(FotMob 90분)은 Transfermarkt 분을 씀). 그 전은 경기별 두 번째 출처가 없음(리버 플레이트의 남미 대회 골은 RSSSF·영어 위키백과 경기 기록과 대조)",
    "리버 플레이트 리그 경기 공백: Transfermarkt는 리버 플레이트의 1993-94~1995-96 아페르투라·클라우수라 경기를 거의 갖고 있지 않음(출전 3경기 0골; 나머지 100경기는 명단 외로 표시). 위키백과의 리버 리그 기록은 62~64경기 24골(영어 64경기 24골, 스페인어·이탈리아어 62경기 24골). 경기별 기록(날짜·상대·득점자)이 있는 것만 넣음: RSSSF 경기 줄의 5경기 6골 — 1994.3.19 아르헨티노스 주니어스전(아페르투라 1993 우승 확정 경기, 교체 없는 선발 명단, 골 없음), 1995.8.12 벨그라노 원정 63·72분 2골, 1996.3.22 벨레스 원정 86분 1골, 1996.4.28 라싱전 37·42분 2골, 1996.5.26 우라칸전 58분 1골(골 시각·골 전 스코어는 RSSSF 득점 순서, PK 표시 없음). 이 5경기는 Transfermarkt에 명단 외로 적혀 있으나 RSSSF 경기 줄을 따름(출전 분 기록이 없어 골이 있는 4경기는 90분 추정, 단일 출처). 나머지 리그 약 55경기 18골(클라우수라 1994 득점왕 11골 포함)은 경기별 자료가 없어 넣지 않음. 그래서 리버 플레이트 시기 기록(31경기 18골)은 위키백과(79~85경기 36골)보다 적음",
    "리버 플레이트의 남미 대회 날짜: Transfermarkt 날짜가 RSSSF·영어 위키백과와 다른 경기는 두 출처가 같으면 그 날짜, 다르면 Transfermarkt와 맞는 쪽을 씀 — 리베르타도레스 1995 조별 세로전 4.13(Transfermarkt 3.18)·페냐롤전 4.19(4.8), 1996 카라카스 홈 4.19(위키백과 4.18, Transfermarkt 4.20), 16강 1차전 스포르팅 크리스탈 원정 5.1, 8강 산로렌소 5.15·5.22, 준결승 6.5·6.12, 결승 6.19·6.26(Transfermarkt는 중부 유럽 날짜라 하루 늦음). 골 시각은 Transfermarkt(1996.4.11 미네르벤전 79분은 영어 위키백과 71분, 골 전 스코어는 같음)",
    "골: Transfermarkt 리포트 골 248개(PK 14개, 자책골 없음)와 RSSSF 리그 골 6개. 2011.1.6 유벤투스전 62분 PK 골에 크레스포 본인이 PK 유도 도움으로 적힌 것은 도움이 아님(Transfermarkt 도움 합계에도 없음)",
    f"도움: 모두 Transfermarkt 경기 리포트 도움(2014년 이전이라 단일 출처, 클로제·비에리 선례). 도움 {NA} = Transfermarkt 54 − 슈팅 리바운드('Shot on goal') 4(2002.12.1 브레시아전 비에리, 1999.12.12 베네치아전 칸나바로, 1996.6.5 리베르타도레스 준결승 우니베르시다드 데 칠레전 소린, 2006.11.5 아스콜리전 사네티). 유형 칸이 빈 도움 5개는 일반 도움으로 셈. 스페인어 위키백과의 시즌 도움 합계(통산 72, 리버 14 등)는 경기별로 나눌 수 없어 쓰지 않음. FotMob 시즌 합계의 파르마 2009-10 도움 4개(Transfermarkt 3)·2010-11 1개(0)도 경기별 기록이 없어 넣지 않음",
    "2005.4.12 챔스 8강 2차전 인테르-밀란전(관중 소요로 0-1에서 중단, 0-3 몰수)은 크레스포가 60분 뛰었고 골·도움이 없어 출전만 셈",
    "출전 분: Transfermarkt 그대로. 연장 경기: 1994.1.21 코파 센테나리오 벨그라노전(교체 74분), 1999.12.9 UEFA컵 3라운드 2차전 슈투름 그라츠 원정(교체 74분, 120+2분 골), 2006.8.26 수페르코파 로마전(교체 59분), 2009.1.13 코파 이탈리아 제노아전(120분), 2010.12.14 코파 이탈리아 피오렌티나전(교체 39분, 연장 2골). 2005 챔스 결승 리버풀전(연장 뒤 승부차기)은 교체 85분",
    "날짜: 유럽 경기는 Transfermarkt 리포트·일정 날짜(선수 경기 성적의 22:00/23:00 UTC 자리값은 하루 앞섬). 리버 플레이트의 그 밖의 경기는 Transfermarkt 일정 날짜(1995.6.25 클라우수라 벨레스 원정은 일정표에 없어 선수 경기 성적 날짜)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위를 기존 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "리그 수준: 아르헨티나 1부는 반시즌(아페르투라·클라우수라) 최종 순위(Transfermarkt 순위표를 RSSSF 표와 대조, 클라우수라 1996 라싱은 29점 동률 공동 7위)를 다른 선수 자료와 같은 모형(평균 1583·흩어짐 63)에 넣음(리베르타도레스의 아르헨티나 상대도 그때 진행 중인 대회 순위: 산로렌소 1996 클라우수라 19위). 우라칸 1996은 다른 선수 자료 값(아페르투라 1996 19위 1509)을 그대로 씀. 세리에A·프리미어리그는 기존 순위값(빈 순위는 앞뒤 값 사이)",
    "직접 추정(남미 대회 상대, 모두 '추정'): 세로 1995(우루과이 1994 연간 4위/13팀을 다른 선수 자료의 우루과이 모형 평균 1540에 넣음), 미네르벤 1996 1380·카라카스 1996 1400(베네수엘라, 다른 선수 자료 값과 같은 수준), 스포르팅 크리스탈 1996 1400(페루 우승 팀, 다른 선수 자료 페루 상위 팀 값), 아메리카 데 칼리 1996(콜롬비아 1995-96 2위, 다른 선수 자료의 콜롬비아 리그 수준 추정 모형 평균 1580)",
    "대회 비중: 리베르타도레스 조별·16강은 리베르타도레스 조별, 8강·준결승·결승은 리베르타도레스 토너먼트(준결승·결승 가중), 수페르코파 수다메리카나 1994는 수다메리카나와 같은 비중(골·도움 없음), 코파 센테나리오(1993-94 아르헨티나 축구협회 100주년 컵)는 국내컵, 수페르코파 이탈리아나·커뮤니티 실드는 국내컵 결승, 잉글랜드 리그컵 8강·FA컵 6라운드는 국내컵 8강, UEFA컵 1라운드는 유로파 예선, UEFA컵 2라운드 이후는 유로파 토너먼트, 2009-10 유로파리그 조별은 유로파 조별, 챔스 2차 조별(2002-03)은 조별로 계산함. 2000.5.23 세리에A 챔스 진출 플레이오프 인테르전(단판, 골·도움 없음)은 리그 비중",
    f"두 경기 합산(챔스·UEFA컵·코파 이탈리아·리베르타도레스) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·코파 이탈리아는 원정 다득점·연장 있음, 리베르타도레스 1996은 원정 다득점·연장 없이 승부차기(리켈메 자료와 같은 규정). 크레스포가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움(1999.12.9 슈투름 그라츠전의 1차전 홈 2-1 등)",
    "시즌 구분: 리버 플레이트는 달력 연도(다른 선수 자료의 아르헨티나 클럽과 같음), 유럽 클럽은 8월 1일 기준(7월 경기 없음). 클럽 구분은 1996.7.1 전 리버 플레이트, 2000.7.1 전 파르마, 2002.7.1 전 라치오, 2003.7.1 전 인테르, 2004.7.1 전 첼시, 2005.7.1 전 AC 밀란(임대), 2006.7.1 전 첼시, 2009.7.1 전 인테르(2006~2008 임대, 2008-09 완전 이적), 2010.1.29 전 제노아, 이후 파르마(파르마·인테르·첼시 두 시기는 각각 한 클럽으로 묶음)",
    "우승·수상은 Transfermarkt 업적 페이지 기준: 아르헨티나 1부 아페르투라 1993·1994(리버 플레이트), 코파 리베르타도레스 1996(리버 플레이트), UEFA컵 1998-99·코파 이탈리아 1998-99(파르마), 세리에A 2006-07·2007-08·2008-09(인테르), 프리미어리그 2005-06(첼시), 수페르코파 이탈리아나 5회(파르마 1999·라치오 2000·밀란 2004·인테르 2006·2008), 커뮤니티 실드 2005(첼시), 챔스 준우승 2004-05(밀란). 개인: 세리에A 득점왕 2000-01(26골), 아르헨티나 클라우수라 1994 득점왕(11골), 코파 이탈리아 득점왕 1998-99(6골)·2006-07(4골). 올림픽·월드컵 예선 등 대표팀 기록은 뺌",
    "은퇴: 2012년(마지막 클럽 경기 2011.11.29 코파 이탈리아 엘라스 베로나전)",
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
    gs = sorted({(r[5], r[6], sort_min(r)) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
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
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r, mm[r[9]]))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const CRS_E={J(E)};\nconst CRS_M={J(M)};\nconst CRS_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game": SAMEGAME, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for n, y, v in ST: print(" ", n, y, v)
