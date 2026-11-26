#!/usr/bin/env python3
"""Alexis Sánchez: raw/ -> alexis.json + src/data/axs.js (판정 근거는 judgments.md)

  python3 players/alexis/build_alexis.py            # 파일 쓰기
  python3 players/alexis/build_alexis.py --debug    # Elo 출처 목록
  python3 players/alexis/build_alexis.py --cross    # 같은 경기 다른 선수 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/ranks.txt·raw/wiki_es_standings.txt(순위표), raw/rsssf_alexis_lines.txt(코브렐로아 리그 골),
      <ROOT>/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(동료 대조).
크레스포 build 스크립트를 바탕으로 함.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "axs.js")
OUT_JSON = os.path.join(HERE, "alexis.json")
ME = "알렉시스 산체스"
INCLUDE_RSSSF = True   # Transfermarkt 'not in squad'인 코브렐로아 리그 6경기 8골(RSSSF 경기 줄, judgments.md 1절)
CUTOFF = "2026-11-18"

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
# 골 제외: gameId|분 -> 이유
EXCL_G = {}
# 도움 제외: gameId|분 -> 이유 (judgments.md 4절)
EXCL_A = {
    "1125576|26": "상대 자책골 유도(TM 'Shot on goal' — 로베르 자책골, 스카이스포츠·EFE 보도)",
    "2517320|20": "2014.8 이후 TM 단일 출처(FotMob 도움 정보 없음), 다른 출처 2곳 확인 못 함",
    "2530788|29": "2014.8 이후 TM 단일 출처(FotMob 도움 정보 없음), 다른 출처 2곳 확인 못 함",
    "2754914|46": "2014.8 이후 TM 단일 출처(FotMob 도움 없음), 다른 출처 2곳 확인 못 함",
    "2828200|75": "2014.8 이후 TM 단일 출처(FotMob 도움 없음), 다른 출처 2곳 확인 못 함",
    "2916161|25": "2014.8 이후 TM 단일 출처(FotMob 도움 정보 없음), 다른 출처 2곳 확인 못 함",
    "3614701|66": "2014.8 이후 TM 단일 출처(FotMob 도움 없음), 다른 출처 2곳 확인 못 함",
}
CONFIRMED_SINGLE = {}   # 2014.8 이후 단일 출처 도움 중 다른 출처 2곳으로 확인한 것(gameId|분 -> 근거)
NO_TYPE_RULE = {"Penalty: Fouled player": "PK 유도", "Shot on goal": "슈팅 리바운드", "Deflected": "굴절"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "ES1", "GB1", "FR1", "MLS1", "ARG1", "ARGC", "CHLA", "CHL1"}
CUPS = {"CIT", "FAC", "CGB", "CDR", "FRC", "CAN"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round") and cid == "FAC": return "dk"
        return "dc"
    if cid in ("CHLP", "CHPL"):   # 칠레 플레이오프 = 멕시코 리길야 선례(MLS 플레이오프 비중)
        if r.startswith("final"): return "mlpf"
        if r.startswith("semi"): return "mlpsf"
        return "mlp"
    if cid in ("SUC", "SCI", "GBCS", "USC"):
        return "dsf" if r.startswith("semi") else "df"
    if cid == "KLUB": return "cwc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("final"): return "elf"
        if r.startswith("semi"): return "elsf"
        return "elk"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "CLI":
        if r.startswith("group") or r.startswith("last 16"): return "lib"
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
    if cid == "CS":
        if r.startswith("qualifying") or r.startswith("last 16"): return "csa"
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
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

def tie_flags(cid, d):
    if cid in ("CLI", "CS"): return (1, 0)        # 2005~2008 남미 대회: 원정 다득점·연장 없음(승부차기), 리켈메·팔카오 선례
    if cid in ("CHLP", "CHPL", "CAN"): return (0, 0)  # 칠레 플레이오프: 합계 동률이면 바로 승부차기(추정) / 캐나디안 챔피언십(뮐러 선례)
    if cid in ("CL", "CLQ", "EL", "UEFA") and d >= "2021-07-01": return (0, 1)   # UEFA 원정 다득점 폐지(2021-22)
    return (1, 1)                                  # UEFA 대회·국왕컵·코파 이탈리아 준결승·수페르코파

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, re.match(r"(\d+):(\d+)", o["final"]).groups())
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    return [leg, home, fu, ft, *tie_flags(g["competitionId"], g["date_local_computed"])]

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
MANUAL_ALIAS = {"inter milan": "inter"}
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
    s = y if m >= 8 else y - 1          # 8월 1일 기준(계산기 시즌 구분), 2020년 8월 경기는 2019-20
    if y == 2020 and m == 8: s = 2019
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league" or "[TM table" in p[1]: continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

def ents_map(prefix, season, extra=""):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위" + extra + "$")
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

def mid_fill(m, r):
    lo = max([k for k in m if k < r], default=None); hi = min([k for k in m if k > r], default=None)
    if lo is None or hi is None: return None
    return half_up(m[lo] + (m[hi] - m[lo]) * (r - lo) / (hi - lo))

LG_NAME = {"IT1": "세리에A", "ES1": "라리가", "GB1": "프리미어리그", "FR1": "리그1"}
def model(lg, season, r, n):
    if lg in LG_NAME:
        nm = LG_NAME[lg]
        m = ents_map(nm, season)
        if r in m: return m[r], f"{nm} {season} {r}위"
        v = mid_fill(m, r)
        return (v, f"{nm} {season} {r}위") if v else None
    if lg in ("ARG1", "ARGC"):   # 리켈메·포를란·크레스포 선례: 반시즌 표, 평균 1583·흩어짐 63
        y0 = int(season[:4])
        t, y = ("아페르투라", y0) if lg == "ARG1" else ("클라우수라", y0 + 1)
        return half_up(1583 + 63 * curve(r, n)), f"아르헨티나 1부 {t} {y} {r}위"
    return None

# 칠레 1부(새 리그 수준, 추정): 다른 선수 자료의 칠레 팀 값(1위권 1550, 4~6위 1480~1500, 하위 팀 1350)에 맞춘
# 평균 1450·흩어짐 40. 순위는 그해 아페르투라+클라우수라 합산 승점표(es.wiki; 2006은 위키 연간표, 2005는 두 대회 합).
CHL_MEAN, CHL_SD = 1450, 40
def wiki_tables():
    T = collections.defaultdict(list)
    for line in open(os.path.join(RAW, "wiki_es_standings.txt"), encoding="utf-8"):
        if line.startswith("#"): continue
        f, ti, row = line.rstrip("\n").split("|", 2)
        c = [x.strip() for x in row.split(";")]
        if c[0] == "Pos": continue
        T[(f, int(ti))].append(c)
    return T
WT = wiki_tables()
def _rows(f, ti): return [(re.sub(r"\[.*?\]", "", c[1]).strip(), int(c[2]), int(c[3]), int(c[7]), int(c[8])) for c in WT[(f, ti)]]
def annual(year):
    if year == 2006:
        rows = _rows("es_Torneo_Clausura_2006_(Chile).html", 8)   # 위키 연간 합산표(36경기)
        rows = [(n, p, gf - ga, gf) for n, p, pj, gf, ga in rows]
    elif year == 2005:
        agg = collections.defaultdict(lambda: [0, 0, 0])
        for f in ("es_Torneo_Apertura_2005_(Chile).html", "es_Torneo_Clausura_2005_(Chile).html"):
            for n, p, pj, gf, ga in _rows(f, 7):
                a = agg[n]; a[0] += p; a[1] += gf - ga; a[2] += gf
        rows = [(n, *v) for n, v in agg.items()]
    elif year == 2007:
        rows = _rows("es_Torneo_Apertura_2007_(Chile).html", 3)
        rows = [(n, p, gf - ga, gf) for n, p, pj, gf, ga in rows]
    else:
        return {}
    rows.sort(key=lambda x: (-x[1], -x[2], -x[3]))
    out = {}
    for i, (n, p, dg, gf) in enumerate(rows):
        r = 1 + sum(1 for x in rows if (x[1], x[2], x[3]) > (p, dg, gf))   # 승점·득실차·다득점 같으면 공동 순위
        out[key(n)] = (r, len(rows), p)
    return out
CHL_RANK = {y: annual(y) for y in (2005, 2006, 2007)}
CHL_LABEL = {2005: "아페르투라·클라우수라 합산", 2006: "연간 합산", 2007: "아페르투라"}
def chl_lookup(opp, year):
    t = CHL_RANK.get(year) or {}
    GEN = {"cd", "csd", "club", "fc", "deportes", "de"}
    tk = lambda x: set(x.split()) - GEN
    k = key(opp)
    cand = [kk for kk in t if tk(kk) and tk(k) and (tk(kk) <= tk(k) or tk(k) <= tk(kk))]
    cand = [c for c in cand if ("universidad" in c.split()) == ("universidad" in k.split())]
    if len(cand) != 1: return None
    r, n, p = t[cand[0]]
    return half_up(CHL_MEAN + CHL_SD * curve(r, n)), f"칠레 1부 {year} {CHL_LABEL[year]} {r}위/{n}팀 (리그 수준 추정)"

# 직접 추정(모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
exec(open(os.path.join(HERE, "man_alexis.py"), encoding="utf-8").read()) if os.path.exists(os.path.join(HERE, "man_alexis.py")) else None

ELO_SRC = collections.Counter()
ELO_LOG = []
NEW_TS = {}   # 새로 만든 팀-시즌 값
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

SA_COMP = {"CLI", "CS", "ARG1", "ARGC", "CHLA", "CHL1", "CHLP", "CHPL"}
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
    y = int(d[:4])
    if cid in SA_COMP:
        seasons = [str(y), f"{y-1}-{str(y)[2:]}", f"{y}-{str(y+1)[2:]}"]
    else:
        euro = cid in ("CL", "CLQ", "UEFA", "EL", "USC", "KLUB")
        seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if euro else [eu, str(y)]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            NEW_TS[(opp, s)] = (e, lv)
            return e, lv
    if cid in ("CHLA", "CHL1", "CHLP", "CHPL"):
        res = chl_lookup(opp, y)
        if res:
            ELO_SRC["칠레 1부 순위표+추정 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "chl"))
            NEW_TS[(opp, str(y))] = res
            return res
        return None
    if cid in ("ARG1", "ARGC"):
        cands = [(cid, sid)]
    elif cid in SA_COMP:
        cands = []
    else:
        cands = [(lg, s) for s in seasons for lg in ("IT1", "ES1", "GB1", "FR1")]
    for lg, s in cands:
        t = RANKS.get((lg, s))
        if t and k in t:
            r, n = t[k]
            res = model(lg, s, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg))
                NEW_TS[(opp, s)] = res
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g): return g["date_local_computed"]
def opp_name(g): return re.sub(r"\s*\(-? ?\d{4}\)\s*$", "", g["opponent"]).strip()

M = []
for g in GAMES:
    M.append([ldate(g), opp_name(g), comp_of(g["competitionId"], g["round"]), MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])

# RSSSF 경기 줄로만 확인되는 코브렐로아 리그 경기(Transfermarkt API 'not in squad', 경기 id는 TM 것): 출전 분은 90분(추정)
RSSSF_M = [["2005-03-18", "Deportes Concepción", "lg", 90, "CHLA", "4472975"],
           ["2005-05-29", "CD Puerto Montt", "lg", 90, "CHLA", "4473385"],
           ["2005-10-01", "Santiago Wanderers", "lg", 90, "CHL1", "4469430"],
           ["2006-01-29", "CD Cobresal", "lg", 90, "CHLA", "4387220"],
           ["2006-03-11", "Huachipato FC", "lg", 90, "CHLA", "4467068"],
           ["2006-04-01", "Deportes La Serena", "lg", 90, "CHLA", "4467124"]]
# RSSSF 골: (날짜, 분, 골 전 우리, 상대) — 득점 순서는 RSSSF 경기 줄(raw/rsssf_alexis_lines.txt)
RSSSF_G = [("2005-03-18", 73, 0, 1), ("2005-05-29", 53, 3, 0), ("2005-10-01", 71, 2, 0),
           ("2006-01-29", 48, 0, 1), ("2006-01-29", 78, 3, 1), ("2006-03-11", 11, 0, 0), ("2006-03-11", 82, 1, 3),
           ("2006-04-01", 51, 1, 1)]
if INCLUDE_RSSSF:
    for d, o, c, mi, *_ in RSSSF_M:
        M.append([d, o, c, mi, 1])
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
    isg, isa, iss = e["alexis_scorer"] == "1", e["alexis_assist_other"] == "1", e["alexis_self_assist"] == "1"
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
    d = ldate(g); opp = opp_name(g)
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
        if e["assist_type"] in NO_TYPE_RULE:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], NO_TYPE_RULE[e["assist_type"]] + f"(TM '{e['assist_type']}')")); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et, tm_sid(g))

if INCLUDE_RSSSF:
    rm = {r[0]: r for r in RSSSF_M}
    for d, mi, gf, ga in RSSSF_G:
        r = rm[d]
        add_row("g", mi, 0, gf, ga, 0, 0, None, "lg", 0, d, r[1], r[4], 0)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv and "--missing" not in sys.argv: sys.exit(1)
if "--missing" in sys.argv: sys.exit(0)

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
TRACKED = None
try:
    import subprocess
    TRACKED = set(subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
except Exception:
    pass
for fn in sorted(os.listdir(os.path.join(ROOT, "src", "data"))):
    if not fn.endswith(".js") or fn in ("hon.js", "axs.js"): continue
    if TRACKED and ("src/data/" + fn) not in TRACKED: continue   # 다른 병렬 판정 파일은 읽지 않음
    P = fn[:-3].upper()
    try: OTHERS[fn] = load_js(fn, P)
    except Exception: continue
MY = norm("Alexis Sánchez")
for fn, ent in OTHERS.items():
    for r in E:
        if r[0] != "a": continue
        hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1])]
        if hit: CROSS.append(("알렉시스 도움→" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:
        if x[0] == "a" and norm(str(x[13])).replace("alexis sanchez", MY) in (MY, "alexis", "sanchez"):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn + " 도움→알렉시스 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                SAMEGAME.append((fn, r[9], r[1], tuple(d) or "같음"))
                break
SAMEGAME = sorted(set(SAMEGAME))
# 엄격 대조: 알렉시스 도움의 득점자가 계산기에 있는 선수면 그 선수 파일의 같은 경기 골(스코어 같음)과 비교
def first_note(fn):
    t = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r'_NOTE="([^"(]*)\(', t)
    return m.group(1).strip() if m else ""
STRICT = []
for fn, ent in OTHERS.items():
    gs = [x for x in ent if x[0] == "g"]
    for r in E:
        if r[0] != "a": continue
        same = [x for x in gs if x[9] == r[9] and key(x[1]) == key(r[1])]
        if not same: continue
        hit = [x for x in same if (x[5], x[6]) == (r[5], r[6])]
        if hit: STRICT.append((fn, r[9], r[13], r[4], cmp_rows(r, hit[0]) or "같음"))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s_ in SAMEGAME:
        if s_[-1] != "같음": print("같은 경기 차이", s_)
    for x in STRICT: print("엄격", x)
    print("같은 경기", collections.Counter((s_[0], s_[-1] == "같음") for s_ in SAMEGAME))
# 득점자 파일이 그 경기를 갖고 있는데 같은 스코어 골이 없는 도움(득점자 이름이 파일 첫 줄 이름과 같은 경우)
NAMEFILE = {}
for fn in OTHERS:
    t = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    for nm in set(re.findall(r'"a","[^"]*",\d+,"[^"]*",\d+,\d+,\d+,\d,\d,"[^"]*",\d,[^,]*,"[^"]*","([^"]*)"', t)):
        pass
STRICT_KEYS = {(x[0], x[1], x[3]) for x in STRICT}
if __name__ == "__main__" and "--cross" in sys.argv:
    for r in E:
        if r[0] != "a": continue
        for fn, ent in OTHERS.items():
            if any(x[9] == r[9] and key(x[1]) == key(r[1]) and x[0] == "g" for x in ent) and (fn, r[9], r[4]) not in STRICT_KEYS:
                gl = [(x[4], x[5], x[6]) for x in ent if x[9] == r[9] and x[0] == "g"]
                print("득점자 미대조", fn, r[9], r[1], r[13], r[4], (r[5], r[6]), "파일 골:", gl)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("cobax", "2006-07-01", "코브렐로아"), ("ccax", "2007-07-01", "콜로콜로"), ("rivax", "2008-07-01", "리버 플레이트"),
         ("udiax", "2011-07-21", "우디네세"), ("barax", "2014-07-10", "바르셀로나"), ("arsax", "2018-01-22", "아스널"),
         ("mnuax", "2019-08-29", "맨체스터 유나이티드"), ("intax", "2022-08-10", "인테르"), ("omax", "2023-08-26", "올랭피크 마르세유"),
         ("intax", "2024-08-10", "인테르"), ("udiax", "2025-09-01", "우디네세"), ("sevax", "2026-08-11", "세비야"),
         ("mtlax", None, "CF 몬트리올")]
TM_CLUB = {"9103": "cobax", "2433": "ccax", "209": "rivax", "410": "udiax", "131": "barax", "11": "arsax", "985": "mnuax",
           "46": "intax", "244": "omax", "368": "sevax", "4078": "mtlax"}
def club_of(d):
    for k, u, _ in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
    if g["club_id"] in ("410", "131", "11", "985", "46", "244", "368") and season_eu(ldate(g))[:4] != g["seasonId"]:
        sys.exit("시즌 불일치 " + g["gameId"])
for r in E + M:
    d = r[9] if len(r) > 9 else r[0]
    if d > CUTOFF: sys.exit("기준일 뒤 기록 " + d)
PERIODS = [("코브렐로아", "2005~2006", None, "2006-07-01"), ("콜로콜로", "2006~2007", "2006-07-01", "2007-07-01"),
           ("리버 플레이트", "2007~2008", "2007-07-01", "2008-07-01"), ("우디네세", "2008~2011", "2008-07-01", "2011-07-21"),
           ("바르셀로나", "2011~2014", "2011-07-21", "2014-07-10"), ("아스널", "2014~2018", "2014-07-10", "2018-01-22"),
           ("맨체스터 유나이티드", "2018~2019", "2018-01-22", "2019-08-29"), ("인테르", "2019~2022", "2019-08-29", "2022-08-10"),
           ("올랭피크 마르세유", "2022~2023", "2022-08-10", "2023-08-26"), ("인테르", "2023~2024", "2023-08-26", "2024-08-10"),
           ("우디네세", "2024~2025", "2024-08-10", "2025-09-01"), ("세비야", "2025~2026", "2025-09-01", "2026-08-11"),
           ("CF 몬트리올", "2026~", "2026-08-11", None)]
def per(lo, hi):
    inr = lambda d: (lo is None or d >= lo) and (hi is None or d < hi)
    return [sum(1 for m in M if inr(m[0])), sum(1 for r in E if r[0] == "g" and inr(r[9])),
            sum(1 for r in E if r[0] == "a" and inr(r[9])), sum(m[3] for m in M if inr(m[0]))]
ST = [(n, y, per(lo, hi)) for n, y, lo, hi in PERIODS]

# ---------------------------------------------------------------- 내부 점검(16절)
problems = []
mdates = collections.Counter(m[0] for m in M)
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
mm = {m[0]: m for m in M}
seen = collections.Counter((r[0], r[9], r[4], r[5], r[6], r[13]) for r in E)
for k_, c in seen.items():
    if c > 1: problems.append(("중복 행", k_))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if r[9] not in mm: problems.append(("출전 없는 날 기록", r)); continue
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r, mm[r[9]]))
    if r[4] > mm[r[9]][3] + 125 and False: pass
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
# 스코어 순서: 같은 경기 기록은 분 순서로 골 전 스코어가 줄지 않아야 함
byd = collections.defaultdict(list)
for r in E: byd[r[9]].append(r)
for d, L in byd.items():
    L2 = sorted(L, key=lambda r: r[4])
    for a, b in zip(L2, L2[1:]):
        if (b[5] < a[5] or b[6] < a[6]): problems.append(("스코어 순서", d, a[4], b[4]))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
NEST = sum(1 for m in M if len(m) > 4)
NOTE = open(os.path.join(HERE, "note_alexis.txt"), encoding="utf-8").read().strip() if os.path.exists(os.path.join(HERE, "note_alexis.txt")) else ""
FMT = dict(NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN=f"{MIN_TOT:,}", NEST=NEST, NTIE=NTIE, NTIEG=NTIEG, FIRST=d_(M[0][0]), LAST=d_(M[-1][0]),
           CLUBLINE=", ".join(f"{n}({y}) {v[0]}·{v[1]}·{v[2]}" for n, y, v in ST),
           SRC="같은 경기 다른 선수 자료 {0}·팀×시즌 통합표 {1}·칠레 1부 순위표+추정 모형 {2}·순위표+리그 모형 {3}·직접 추정 {4}".format(
               ELO_SRC["같은 경기 다른 선수 자료"], ELO_SRC["팀×시즌 통합표"], ELO_SRC["칠레 1부 순위표+추정 모형"], ELO_SRC["순위표+리그 모형"], ELO_SRC["직접 추정"]))
NOTE = NOTE.format(**FMT)
for bad in ("dc", "dk", "dsf", "seasonOf", "v1."):
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 코드명 " + bad)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const AXS_E={J(E)};\nconst AXS_M={J(M)};\nconst AXS_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS, "strict": STRICT,
               "same_game": SAMEGAME, "elo_sources": ELO_SRC, "elo_log": ELO_LOG,
               "new_team_seasons": [[o, s, e, lv] for (o, s), (e, lv) in sorted(NEW_TS.items())]},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for n, y, v in ST: print(" ", n, y, v)
if "--stat" in sys.argv:
    for n, y, v in ST: print(" ", n, y, v)
    for x in judg: print(x)
    for (o, s), (e, lv) in sorted(NEW_TS.items()): print("새 팀-시즌", o, s, e, lv)
