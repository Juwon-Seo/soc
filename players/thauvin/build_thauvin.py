#!/usr/bin/env python3
"""Florian Thauvin: raw/ -> thauvin.json + src/data/thv.js (판정 근거는 judgments.md)

  python3 players/thauvin/build_thauvin.py                 # 파일 쓰기
  python3 players/thauvin/build_thauvin.py --debug         # Elo 출처 로그·도움 제외 목록
  python3 players/thauvin/build_thauvin.py --cross         # 동료·같은 경기 자료 대조
  python3 players/thauvin/build_thauvin.py --root=<스크래치 복사본>   # 그 복사본의 src/data·elo 사용(검증용)

구이리(build_gouiri.py)·지냑(build_gignac.py, 티그레스 처리) 빌드를 바탕으로 함.
입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
raw/fotmob_events.csv·fotmob_playerMatches.csv(FotMob), raw/ranks.txt(순위표),
<root>/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv, <root>/src/data/*.js(git 추적 파일만, 같은 경기 대조),
players/gignac/raw/fotmob/leagues/230_*.json.gz(리가MX 정규리그 표 → 시즌 누적 순위, 지냑과 같은 방식; 읽기만).
"""
import csv, json, os, re, sys, unicodedata, collections, gzip, glob, subprocess
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "thv.js")
OUT_JSON = os.path.join(HERE, "thauvin.json")
GIGNAC_LEAGUES = os.path.join(os.path.dirname(HERE), "gignac", "raw", "fotmob", "leagues")
ME = "플로리앙 토뱅"
GAP = "2014-08-01"
TV = "184892"   # Transfermarkt 선수 id

try:
    TRACKED = set(os.path.basename(p) for p in subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
except Exception:
    TRACKED = None

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)
FPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 판정 표
# FotMob에만 있는 출전(Transfermarkt 'in squad'): 다른 출처로 확인해 넣음 (날짜, 상대, TM 대회, TM 라운드, 분, 근거)
ADD_GAMES = [("2021-11-25", "Santos Laguna", "POMX", "Quarter-Finals 1st Leg", 16,
              "리길야 8강 1차전 산토스 2-1 티그레스: FotMob 라인업 75분 교체 투입 16분, Depor 라인업·경기 기록(74분 비곤 대신 투입)·Mediotiempo(75분 투입)·ESPN 라인업. Transfermarkt만 '명단 포함'")]
# 2014.8.1 이후 Transfermarkt 리포트 도움 중 FotMob 경기 이벤트에 없는 것: 넣음(근거)
ADD_CONFIRMED = {
    "2612554|8": "2015.8.25 노샘프턴전(리그컵) 8분 더용 골: NUFC.com 경기 기사(토뱅 프리킥을 더용이 머리로) · beIN Sports/PA 기사(1골 3도움)",
    "2612554|56": "2015.8.25 노샘프턴전 56분 얀마트 골: NUFC.com 경기 기사(페레스·더용·토뱅 연계 뒤 토뱅이 얀마트에게 패스) · beIN Sports/PA 기사(1골 3도움)",
    "2612554|63": "2015.8.25 노샘프턴전 63분 윌리엄슨 골: NUFC.com 경기 기사(토뱅 프리킥을 먼 쪽 포스트 윌리엄슨이 헤더) · beIN Sports/PA 기사(1골 3도움)",
    "2761053|68": "2016.10.26 클레르몽전(쿠프 드 라 리그) 68분 고미스 골: maxifoot 경기 기사(토뱅의 정확한 스루패스) · ESPN 문자중계('Assisted by Florian Thauvin')",
    "2887590|2": "2017.7.27 오스텐더전(유로파 예선) 2분 제르맹 골: maxifoot 경기 기사(토뱅 크로스) · 마르세유 구단 기사(om.fr) · DH(벨기에) 경기 기사('Thauvin centrait pour Germain')",
    "2904770|63": "2017.8.17 돔잘레전(유로파 예선) 63분 상송 골: maxifoot 경기 기사('très belle passe décisive pour Sanson') · AFP 기사(tendanceouest 게재, '토뱅이 상송을 띄워 보냄')",
    "2905744|56": "2017.8.24 돔잘레전 56분 제르맹 골: 마르세유 구단 기사(토뱅 크로스를 제르맹이 받아 마무리) · AFP 기사(tendanceouest 게재, '토뱅의 크로스')",
    "2990187|90+3": "2018.1.23 에피날전(쿠프 드 프랑스) 90+3분 상송 골: ESPN 문자중계('Assisted by Florian Thauvin with a cross') · 마르세유 구단 기사 · maxifoot 경기 기사(토뱅 크로스)",
    "4894930|45+2": "2026.9.13 르망전 45+2분 시마 골: maxifoot 경기 기사(토뱅 크로스를 에두아르가 놓쳐 먼 쪽 포스트 시마가 헤더) · Flashscore 경기 기사(같은 설명). 에두아르는 공에 닿지 않음(굴절 아님)",
}
# FotMob 선수 경기 목록 도움 수로 FotMob 확인으로 본 경기(이 경기들의 FotMob 경기 이벤트는 도움 칸이 비어 있음; 지냑 선례)
FM_PM_OK = {"4151667": 1, "4423377": 2, "4788536": 1}
# FotMob에만 있는 도움(선수 경기 목록 수치만, 경기 이벤트에 없음): 넣지 않음
FM_ONLY_DECIDED = {
    "2942776": "2018.1.28 모나코전: FotMob 선수 경기 목록 도움 1(경기 이벤트에 토뱅 도움 없음, 제르맹 골은 파예 도움). maxifoot 기사상 라미 골은 토뱅이 투레의 걷어내기를 막은 공에서 나옴(굴절·튄 공) → 넣지 않음",
    "3047889": "2019.5.18 툴루즈전: FotMob 선수 경기 목록 도움 1(경기 이벤트·Transfermarkt에 토뱅 도움 없음) → 단일 출처라 넣지 않음",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "FR2", "GB1", "IT1", "MEXA", "MEX1"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("FRC", "FRL", "FAC", "CGB", "CIT"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "FRCH": return "df"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        return "clk"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 'intermediate stage'(32강)·16강·8강
    if cid in ("POMX", "POME"):
        if r.startswith("semi"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
        return "mlp"   # 8강·리길야 진출전(repechaje)
    if cid == "USMX": return "lcg" if r.startswith("group") else "lck"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

def tie_rule(cid, d, rnd):
    if cid in ("EL", "ELQ", "CL"): return (int(d < "2021-07-01"), 1)
    if cid in ("POMX", "POME"): return (0, 1) if rnd.lower().startswith("final") else (0, 0)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], INFO[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def tie_of(g):
    rnd = g["round"].lower()
    if "leg" not in rnd: return None
    gid = g["gameId"]; s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], g["date_local_computed"], g["round"])
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, int(s == "h"), 0, 0, ag, et]
    m = INFO[gid]; oid = m["other_leg_id"]
    if oid in INFO and INFO[oid]["final"]:
        o = INFO[oid]; oh, oa = map(int, o["final"].split(":"))
        ours, theirs = (oh, oa) if o["home_id"] == g["club_id"] else (oa, oh)
    else:
        oh, oa = map(int, m["other_leg_score"].split(":"))
        ours, theirs = (oh, oa) if s == "h" else (oa, oh)
    return [2, int(s == "h"), ours, theirs, ag, et]

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
def key(n):
    k = norm(n); return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    P = re.search(r"const (\w+)_E=", s).group(1)
    e = json.loads(re.search(r"const \w+_E=(\[.*?\]);\n", s, re.S).group(1))
    m = json.loads(re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S).group(1))
    return P, e, m
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "thv.js") or (TRACKED is not None and b not in TRACKED): continue
    try: OTHERS[b] = load_js(fn)
    except Exception: continue
BYDATE = collections.defaultdict(list)
for b, (P, oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio",
        "atletico", "ca", "us", "as", "ss", "ssc", "hsc", "osc", "acf", "olympique", "stade", "fk", "sv", "saint", "paris", "cd", "deportivo", "rc", "ogc"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}

# 리그 순위값(다른 선수 자료 lv '리그 시즌 N위', 추정 제외)
LGPTS = collections.defaultdict(dict)
for b, (P, oe, om) in OTHERS.items():
    for x in oe:
        lv = str(x[12])
        if "추정" in lv: continue
        m = re.match(r"(리그1|리그2|세리에A|세리에B|프리미어리그) (\d{4}-\d\d) (\d+)위$", lv)
        if m: LGPTS[(m.group(1), m.group(2))].setdefault(int(m.group(3)), x[2])
def fill(known, n):
    out = {}; ks = sorted(known)
    for r in range(1, n + 1):
        if r in known: out[r] = known[r]; continue
        lo = max([k for k in ks if k < r], default=None); hi = min([k for k in ks if k > r], default=None)
        out[r] = round((known[lo] + known[hi]) / 2) if lo and hi else known[lo or hi]
    return out
FR1_KNOWN18 = {1: 1955, 2: 1866, 3: 1817, 4: 1786, 5: 1771, 6: 1757, 7: 1738, 8: 1718, 9: 1700, 10: 1687,
               11: 1677, 12: 1667, 13: 1662, 14: 1647, 15: 1628, 16: 1612, 17: 1603, 18: 1582}   # 구이리·그린우드 자료와 같은 표
L1_STD = dict(LGPTS[("리그1", "2016-17")])   # 지냑 선례(20팀 리그1 표준값)
L2_STD = fill({1: 1669, 2: 1624, 4: 1582, 6: 1567, 7: 1559, 8: 1550, 10: 1532, 11: 1526, 12: 1521, 13: 1516, 14: 1513, 15: 1508,
               17: 1490, 19: 1480, 20: 1470}, 20)   # 지냑·메네즈 리그2 표

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))
LGNAME = {"FR1": "리그1", "FR2": "리그2", "IT1": "세리에A"}
CUR = {"2026-27": " (11월 18일 현재)"}

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7]); s = y if m >= 8 else y - 1
    if d[:7] == "2020-08": s = 2019
    return f"{s}-{str(s + 1)[2:]}"
def mex_season(d):
    y, m = int(d[:4]), int(d[5:7]); s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

def model(lg, season, r, n):
    cur = CUR.get(season, "")
    name = LGNAME[lg]
    if lg == "FR1" and n == 18:
        v = LGPTS.get((name, season), {}).get(r, FR1_KNOWN18[r])
    elif lg == "FR1":
        v = LGPTS.get((name, season), {}).get(r, L1_STD.get(r))
    elif lg == "FR2":
        v = LGPTS.get((name, season), {}).get(r, L2_STD[r])
    elif lg == "IT1":
        k = LGPTS.get((name, season), {})
        if r not in k: return None
        v = k[r]
    else:
        return None
    return v, f"{name} {season}{cur} {r}위"

# 리가MX 시즌 누적 순위(지냑과 같은 방식: FotMob 아페르투라·클라우수라 정규리그 표 합산, 승점→득실차→다득점)
FMN = {"Monterrey": "CF Monterrey", "León": "Club León FC", "CF América": "CF America", "Pumas": "UNAM Pumas", "Toluca": "Deportivo Toluca",
       "Pachuca": "CF Pachuca", "Chivas": "Deportivo Guadalajara", "Puebla": "Puebla FC", "Santos Laguna": "Santos Laguna", "Cruz Azul": "CD Cruz Azul",
       "Querétaro FC": "Querétaro FC", "Tijuana": "Club Tijuana", "Atlas": "Atlas Guadalajara", "Necaxa": "Club Necaxa",
       "Atlético de San Luis": "Atlético de San Luis", "FC Juárez": "FC Juárez", "Mazatlán FC": "Mazatlán FC", "Tigres": "Tigres UANL"}
MX = fill({1: 1789, 3: 1683, 5: 1648, 6: 1637, 7: 1623, 9: 1594, 10: 1584, 11: 1576, 13: 1563, 14: 1553, 17: 1519, 18: 1503}, 18)
MXCUM = {}
for y in (2021, 2022):
    d = json.load(gzip.open(os.path.join(GIGNAC_LEAGUES, f"230_{y}-{y + 1}-Apertura.json.gz")))
    agg = collections.defaultdict(lambda: [0, 0, 0])
    for t in d["table"][0]["data"]["tables"]:
        for r in t["table"]["all"]:
            gf_, ga_ = map(int, r["scoresStr"].split("-")); a = agg[r["name"]]
            a[0] += r["pts"]; a[1] += gf_ - ga_; a[2] += gf_
    rk = sorted(agg.items(), key=lambda kv: (-kv[1][0], -kv[1][1], -kv[1][2]))
    for i, (n, v) in enumerate(rk):
        MXCUM[(key(FMN[n]), f"{y}-{str(y + 1)[2:]}")] = (i + 1, len(rk))

# 순위표·모형으로 안 되는 상대(직접 추정 또는 순위 확인값). judgments.md 7절
MAN = {
    (key("Northampton Town"), "2015-16"): (1440, "리그 투(4부) 2015-16 1위 (추정, 다른 선수 자료 리그 투 7위 1416보다 높게, 리그 원 하위권 1440과 같은 수준)"),
    (key("US Avellino 1912"), "2024-25"): (1548, "세리에C 2024-25 C조 1위 (추정, 다른 선수 자료 세리에C 조 1위 1548과 같음)"),
    (key("US Catanzaro"), "2023-24"): (1608, "세리에B 2023-24 5위"),   # 같은 시즌 다른 선수 자료 4위 1619·7위 1597의 가운데
    (key("FC Sochaux-Montbéliard"), "2025-26"): (1375, "프랑스 3부(나시오날) 2025-26 2위/17팀 (추정, 다른 선수 자료 나시오날 3위 1361보다 조금 높게)"),
    (key("SAS Épinal"), "2017-18"): (1220, "프랑스 4부(나시오날 2) 2017-18 B조 7위 (추정, 다른 선수 자료 프랑스 4부 1220과 같음)"),
    (key("NK Domzale"), "2017-18"): (1380, "슬로베니아 2017-18 3위 (추정, 다른 선수 자료 슬로베니아 3위 1380과 같음)"),
    (key("Como 1907"), "2026-27"): (1816, "세리에A 2026-27 (11월 13일 현재) 5위"),   # 같은 시즌 다른 선수 자료 3위 1845·6위 1787의 가운데
}
ELO_SRC = collections.Counter(); ELO_LOG = []; MISS = []

def opp_elo(opp, d, cid):
    k = key(opp)
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == k or (toks(x[1]) & toks(opp))]
    vals = {(x[2], x[12]) for b, x in cand}
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({b for b, _ in cand})))); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", opp, d, vals)
    mex = cid in ("MEXA", "MEX1", "POMX", "POME", "USMX")
    eu = mex_season(d) if mex else season_eu(d)
    if mex and (k, eu) in MXCUM and (k, eu) not in TABLE:
        r, n = MXCUM[(k, eu)]; e, lv = MX[r], f"리가MX {eu} 누적 {r}위"
        ELO_SRC["리가MX 누적 순위+순위값"] += 1; ELO_LOG.append((d, opp, e, lv, "mxcum")); return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL", "ELQ", "USMX") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            if len(set(TABLE[(k, s)])) > 1: print("  [통합표 값 여럿]", opp, s, set(TABLE[(k, s)]))
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s)); return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정" if "추정" in lv else "순위표+리그 순위값"] += 1; ELO_LOG.append((d, opp, e, lv, "man")); return e, lv
    for lg in ("FR1", "FR2", "IT1"):
        t = RANKS.get((lg, eu))
        if t and k in t:
            res = model(lg, eu, *t[k])
            if res:
                ELO_SRC["순위표+리그 순위값"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg)); return res
    MISS.append((opp, eu, cid)); return 0, "?"

# ---------------------------------------------------------------- 출전
def ldate(g): return g["date_local_computed"]
M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
for d, o, cid, rnd, mi, why in ADD_GAMES:
    M.append([d, o, comp_of(cid, rnd), mi])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def fm_assist_at(gid, after_ha):
    return any(f["newScore_home_away"] == after_ha and f["thauvin_assist"] == "1" and f["pen_shootout_event"] != "True" for f in FM_EV.get(gid, []))

rows, judg = [], []
EXCL_CNT = collections.Counter(); EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []; USED_ADD = set(); FM_PM_USED = collections.Counter(); FM_CONF = collections.Counter()
for gid in sorted({e["gameId"] for e in EVENTS}, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; s = side_of(gid); prev = (0, 0)
    for e in EVENTS:
        if e["gameId"] != gid: continue
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        tag = f"{gid}|{e['minute']}"; d = ldate(g); opp = g["opponent"].strip()
        if e["thauvin_self_assist"] == "1":
            EXCL_CNT["본인 도움"] += 1; EXCL_LIST["본인 도움"].append((d, opp, e["minute"]))
        isg, isa = e["thauvin_scorer"] == "1", e["thauvin_assist_other"] == "1"
        if not (isg or isa): continue
        gf, ga = (before[0], before[1]) if s == "h" else (before[1], before[0])
        mi, dm = minute(e["minute"])
        cid = g["competitionId"]
        comp = comp_of(cid, g["round"]); ko = ko_of(cid, g["round"]); tie = tie_of(g)
        et = int(ko == 1 and tie is None and "+" not in e["minute"] and mi > 90)
        if tie and tie[5] and g["gameState"] == "extra_time" and "+" not in e["minute"] and mi > 90: et = 1
        typ = None
        if isg:
            if e["own_goal"] == "1": judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
            typ = "g"; pk = int(e["penalty"] == "1" and e["goal_desc"] != "Penalty rebound"); note = 0
        else:
            why = None
            if e["own_goal"] == "1": why = "상대 자책골에 준 도움"
            elif e["assist_type"].startswith("Penalty"): why = "PK 유도"
            elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
            if why:
                EXCL_CNT[why] += 1; EXCL_LIST[why].append((d, opp, e["minute"], e["scorer"]))
                judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
            if d >= GAP:
                if fm_assist_at(gid, e["score_home_away_after"]): FM_CONF["FotMob 경기 이벤트"] += 1
                elif gid in FM_PM_OK and FM_PM_USED[gid] < FM_PM_OK[gid]:
                    FM_PM_USED[gid] += 1; FM_CONF["FotMob 선수 경기 목록"] += 1
                elif tag in ADD_CONFIRMED:
                    USED_ADD.add(tag); FM_CONF["다른 출처 2곳 이상"] += 1
                else:
                    UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
            else:
                FM_CONF["2014.8 전 Transfermarkt"] += 1
            typ = "a"; pk = 0; note = e["scorer"]
        res = opp_elo(opp, d, cid)
        row = [typ, opp, res[0], comp, mi, gf, ga, ko, pk, d, et, dm, res[1], note]
        if tie: row.append(tie)
        rows.append(row)

for t in ADD_CONFIRMED:
    if t not in USED_ADD: print("쓰이지 않은 확인 도움:", t)
# FotMob에만 있는 도움
FM_ONLY = []
for gid, g in G.items():
    pm = FPM.get(g["fotmobMatchId"])
    if pm and int(pm["assists"] or 0) > int(g["assists"] or 0): FM_ONLY.append((gid, ldate(g), g["opponent"], "선수 경기 목록", pm["assists"]))
    for f in FM_EV.get(gid, []):
        if f["thauvin_assist"] == "1" and f["thauvin_scorer"] != "1":
            tm = [e for e in EVENTS if e["gameId"] == gid and e["score_home_away_after"] == f["newScore_home_away"]]
            if not any(e["thauvin_assist_other"] == "1" for e in tm): FM_ONLY.append((gid, ldate(g), g["opponent"], "이벤트", f["time"]))
for f in FM_ONLY:
    if f[0] not in FM_ONLY_DECIDED: print("FotMob 도움 미판정:", f)
if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u)
if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
if (UNDECIDED or MISS or [f for f in FM_ONLY if f[0] not in FM_ONLY_DECIDED]) and "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, EXCL_CNT, FM_CONF)
    for k, v in EXCL_LIST.items(): print(k, v)
    seen = set()
    for x in ELO_LOG:
        kk = (x[1], x[2], x[3])
        if kk in seen: continue
        seen.add(kk); print(x)

exec(open(os.path.join(HERE, "out_thauvin.py"), encoding="utf-8").read())
