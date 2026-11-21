#!/usr/bin/env python3
"""Rafael van der Vaart: raw/ -> vandervaart.json + src/data/vdv.js (판정 근거는 judgments.md)

  python3 players/vandervaart/build_vandervaart.py            # 파일 쓰기
  python3 players/vandervaart/build_vandervaart.py --debug    # Elo 출처 로그
  python3 players/vandervaart/build_vandervaart.py --cross    # 동료 자료 대조
  python3 players/vandervaart/build_vandervaart.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/*.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "vdv.js")
OUT_JSON = os.path.join(HERE, "vandervaart.json")
ME = "라파엘 판데르파르트"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트, 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
OTHER = {g: r["other_leg_id"] for g, r in TIES_RAW.items()}
for gid, r in INFO.items():
    if r["other_leg_id"]:
        OTHER.setdefault(gid, r["other_leg_id"]); OTHER.setdefault(r["other_leg_id"], gid)
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
SCORER_FIX = {}
EXCL_A = {}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2458337|70": "Sport1 'Westermann köpfte … einen Freistoß von van der Vaart zum 1:1 ein' · Reuters(Yahoo·SBS·Gulf News 재게재, 1곳) 'headed in a free-kick from van der Vaart'",
    "2488533|85": "kicker 경기 분석(교체 투입된 판데르파르트의 칩 패스를 라소가가 헤더) · FC 바이에른 구단 경기 기사(판데르파르트 크로스) · Sport1",
    "2633852|18": "레알 베티스 구단 경기 기사(판데르파르트의 안쪽 패스를 판볼프스빙컬이 마무리) · betisweb.com 경기 기록(판데르파르트가 만든 동점 골)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"NL1", "L1", "ES1", "GB1", "DK1", "DKMR", "L1PO"}   # DKMR = 덴마크 수페르리가 우승 결정 라운드(리그), L1PO = 분데스리가 승강 PO(리그 비중+합산, v1.156)
CUP = {"NLP", "DFB", "CDR", "FAC", "CGB", "DKP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round"): return "dk"   # FA컵 6라운드 = 8강
        return "dc"
    if cid == "LPO":   # DFB-리가포칼: 첫 경기(8강 격) dk, 준결승 dsf (클로제·리베리·외질 선례)
        if r.startswith("semi"): return "dsf"
        if r.startswith("intermediate"): return "dk"
    if cid in ("SUC", "NLSC"): return "df"   # 수페르코파·요한 크루이프 스할(슈퍼컵) = 국내컵 결승
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid in ("ELQ", "UI", "UEQ"): return "elq"   # 인터토토(결승 포함)·UEFA컵 예선 = 유로파 예선(토레스·비야·포를란 선례)
    if cid == "UEFA" and r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
    if cid in ("EL", "UEFA"):
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 2라운드·3라운드·intermediate stage(32강)·16강·8강
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
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local"]
    leg = 1 if "1st" in g["round"].lower() else 2
    o = INFO[OTHER[gid]]
    if (o["date_report"] < inf["date_report"]) != (leg == 2): sys.exit("차전 순서 이상 " + gid)
    home = int(inf["home_id"] == g["club_id"])
    if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    fu = ft = 0
    if leg == 2:
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "UI", "UEQ"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid in ("CDR", "SUC"):   # 스페인 국내 대회: 원정 다득점(2018-19까지)·연장
        ag, et = int(d < "2019-07-01"), 1
    elif cid == "L1PO":   # 분데스리가 승강 PO: 원정 다득점(2020-21까지)·연장(고메스 선례)
        ag, et = int(d < "2021-07-01"), 1
    else:
        sys.exit("합산 규칙 없음 " + cid)
    return [leg, home, fu, ft, ag, et]

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
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 리그 모형(기존 선수 자료의 같은 리그 값과 같은 방식)
# 에레디비시: 시즌과 관계없는 순위별 고정값(기존 선수 자료 18개 순위 값 그대로)
NL_FIX = {1: 1837, 2: 1735, 3: 1677, 4: 1642, 5: 1624, 6: 1608, 7: 1587, 8: 1563, 9: 1542, 10: 1528,
          11: 1516, 12: 1504, 13: 1499, 14: 1482, 15: 1459, 16: 1441, 17: 1430, 18: 1406}
# 챔피언십(잉글랜드 2부) 순위별 고정값(기존 선수 자료)
GB2_FIX = {10: 1617, 11: 1607, 12: 1600}
# 2. 분데스리가: 시즌 조정 없는 고정값(기존 선수 자료 값, 외질·고메스 자료와 같음)
L2_FIX = {1: 1697, 3: 1636, 4: 1622, 5: 1615, 6: 1609, 7: 1600, 8: 1592, 9: 1584, 10: 1579, 11: 1574, 12: 1570, 13: 1568, 14: 1561}
# 3. 리가: 평균 1428 + 51.24 × 순위 곡선(외질 자료와 같은 모형, 기존 값 2014-15 6위 1456 등 재현)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
DE3_MEAN, SD2 = 1428, 51.24

def model(lg, season, r, n):
    if lg == "NL1" and n == 18:
        return NL_FIX[r], f"에레디비시 {season} {r}위"
    if lg == "L2" and r in L2_FIX:
        return L2_FIX[r], f"2. 분데스리가 {season} {r}위"
    if lg == "L3":
        return round(DE3_MEAN + SD2 * curve(r, n)), f"3. 리가 {season} {r}위"
    if lg == "GB2" and r in GB2_FIX:
        return GB2_FIX[r], f"챔피언십 {season} {r}위"
    return None
RANK_LG = ["NL1", "GB2", "L2", "L3"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정'). 순위는 judgments.md의 출처로 확인
MAN = {
    (key("KAA Gent"), "2000-01"): (1545, "벨기에 2000-01 5위 (추정, 다른 선수 자료 벨기에 1부 5위 1545와 같음)"),
    (key("RBC Roosendaal"), "2001-02"): (1390, "에이르스터 디비시(네덜란드 2부) 2001-02 3위 (추정, 다른 선수 자료 에이르스터 디비시 3위 1390과 같음)"),
    (key("Stuttgarter Kickers"), "2005-06"): (1450, "독일 3부(레기오날리가 남부) 2005-06 8위 (추정, 다른 선수 자료 독일 3부 레기오날리가 1450과 같음)"),
    (key("Viking FK"), "2005-06"): (1371, "노르웨이 2005 5위 (추정, 다른 선수 자료 노르웨이 4위 1392·6위 1350의 중간)"),
    (key("FC Copenhagen"), "2005-06"): (1560, "덴마크 2005-06 1위 (추정, 다른 선수 자료 코펜하겐 1위 2008-09·2009-10 1560과 같음)"),
    (key("SK Sigma Olomouc"), "2005-06"): (1400, "체코 2005-06 9위 (추정, 다른 선수 자료 체코 9위 1400과 같음)"),
    (key("CSKA Moscow"), "2006-07"): (1630, "러시아 2006 1위 (추정, 다른 선수 자료 CSKA 모스크바 2004-05 1600·2007-08 1660의 중간)"),
    (key("Kispest–Honvéd FC"), "2007-08"): (1380, "헝가리 2007-08 8위 (추정, 다른 선수 자료 헝가리 9위 1380과 같음)"),
    (key("Dacia Chisinau"), "2007-08"): (1350, "몰도바 2007-08 (추정, 다른 선수 자료 몰도바 4위 1350과 같음)"),
    (key("GNK Dinamo Zagreb"), "2007-08"): (1520, "크로아티아 2007-08 1위 (추정, 다른 선수 자료 디나모 자그레브 2006-07·2009-10 1위 1520과 같음)"),
    (key("Litex Lovech"), "2007-08"): (1450, "불가리아 2007-08 4위 (추정, 다른 선수 자료 불가리아 3·5위 1450과 같음)"),
    (key("Holstein Kiel"), "2007-08"): (1300, "독일 4부(오버리가 북부) 2007-08 1위 (추정, 다른 선수 자료 독일 4부 1300과 같음)"),
    (key("Rot-Weiss Essen"), "2007-08"): (1450, "독일 3부(레기오날리가 북부) 2007-08 12위 (추정, 다른 선수 자료 독일 3부 레기오날리가 1450과 같음)"),
    (key("SV Schott Jena"), "2013-14"): (1300, "독일 4부(레기오날리가 북동부) 2013-14 (추정, 다른 선수 자료 독일 4부 1300과 같음)"),
    (key("FC Copenhagen"), "2016-17"): (1590, "덴마크 2016-17 1위 (추정, 다른 선수 자료 코펜하겐 2016-17 1590과 같음)"),
    (key("Bröndby IF"), "2016-17"): (1560, "덴마크 2016-17 2위 (추정, 다른 선수 자료 덴마크 2위 1560과 같음)"),
    (key("AC Horsens"), "2016-17"): (1450, "덴마크 2016-17 하위권 (추정, 다른 선수 자료 에스비에르 2013-14 1450과 같음)"),
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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]",
                        sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "UI", "UEQ") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    for s in [eu, str(int(eu[:4]))]:
        for lg in RANK_LG:
            t = RANKS.get((lg, s))
            if t and k in t:
                r, n = t[k]
                res = model(lg, eu, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                    return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local"]   # Transfermarkt 리포트 날짜(유럽 현지)

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
        if r["vdv_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, 0, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["vdv_scorer"] == "1", e["vdv_assist_other"] == "1"
    if tag in SCORER_FIX:
        isg, isa = True, False
        judg.append(("득점자 고침", tag, e["scorer"], SCORER_FIX[tag][1]))
    if e["vdv_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag)); EXCL_CNT["본인 도움"] += 1
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
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            EXCL_CNT[why if tag not in EXCL_A else "개별 판정"] += 1
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - mi) <= 2]
            if not hit:
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

# 2014.8 이후 FotMob에만 있는 도움(넣지 않음) 확인
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local"] >= GAP and len(ts) > used_fm.get(gid, 0):
        FM_ONLY.append((gid, G[gid]["date_local"], ts))

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY, EXCL_CNT)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["vdv_scorer"] == "1" and e["gameId"] in G and G[e["gameId"]]["date_local"] >= "2010-08-01":
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["vdv_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Zlatan Ibrahimović": ("ibr.js", "IBR", "2001-07-01", "2005-07-01"),
         "Wesley Sneijder": ("sne.js", "SNE", "2002-07-01", "2010-08-31"),
         "Heung-min Son": ("son.js", "SON", "2012-08-31", "2013-07-01"),
         "Raúl": ("rau.js", "RAU", "2008-08-04", "2010-07-01"),
         "Gonzalo Higuaín": ("hig.js", "HIG", "2008-08-04", "2010-08-31"),
         "Arjen Robben": ("rob.js", "ROB", "2008-08-04", "2009-08-28"),
         "Ruud van Nistelrooy": ("nis.js", "NIS", "2008-08-04", "2010-01-26"),
         "Kaká": ("kak.js", "KAK", "2009-07-01", "2010-08-31"),
         "Cristiano Ronaldo": ("ron.js", "RON", "2009-07-01", "2010-08-31"),
         "Karim Benzema": ("bzm.js", "BZM", "2009-07-01", "2010-08-31"),
         "Gareth Bale": ("bal.js", "BAL", "2010-08-31", "2012-08-31"),
         "Harry Kane": ("kan.js", "KAN", "2010-08-31", "2012-08-31")}
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items()}
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb:
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
OZ = lambda s: norm(s or "") in ("rafael van der vaart", "van der vaart")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("판데르파르트 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and OZ(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→판데르파르트 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    # Transfermarkt 외질 도움을 이 계산기에서 뺀 동료 골(참고)
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["vdv_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 판데르파르트 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    # 동료 파일에서 외질 골의 도움으로 적혔어야 할 것(TM 리포트 기준, 참고)
    for e in EVENTS:
        if e["vdv_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 판데르파르트 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
# 기간(stint) 단위. 함부르크 두 기간은 같은 키(임모빌레 torim 선례). 경계 = Transfermarkt 이적일
CLUBS = [("ajavv", "2005-07-01", "아약스", "2000~2005", "610"), ("hsvvv", "2008-08-04", "함부르크 SV", "2005~2008", "41"),
         ("rmavv", "2010-08-31", "레알 마드리드", "2008~2010", "418"), ("totvv", "2012-08-31", "토트넘 홋스퍼", "2010~2012", "148"),
         ("hsvvv", "2015-07-01", "함부르크 SV", "2012~2015", "41"), ("betvv", "2016-08-10", "레알 베티스", "2015~2016", "150"),
         ("fcmvv", "2018-08-04", "FC 미트윌란", "2016~2018", "865"), ("efbvv", None, "에스비에르", "2018", "3426")]
def stint_of(d):
    for i, c in enumerate(CLUBS):
        if c[1] is None or d < c[1]: return i
ST = [[0, 0, 0, 0] for _ in CLUBS]
for m in M: ST[stint_of(m[0])][0] += 1; ST[stint_of(m[0])][3] += m[3]
for r in E: ST[stint_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if CLUBS[stint_of(ldate(g))][4] != g["club_id"]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["vdv_assist_other"] == "1")
N_PKW = sum(1 for e in EVENTS if e["gameId"] in G and e["vdv_assist_other"] == "1" and e["assist_type"] == "Penalty: Fouled player")
N_SOG = sum(1 for e in EVENTS if e["gameId"] in G and e["vdv_assist_other"] == "1" and e["assist_type"] == "Shot on goal" and e["own_goal"] != "1")
N_OGA = sum(1 for e in EVENTS if e["gameId"] in G and e["vdv_assist_other"] == "1" and e["own_goal"] == "1")
KO_OPP = {"FC Copenhagen": "코펜하겐", "1.FC Kaiserslautern": "카이저슬라우테른", "Borussia Mönchengladbach": "묀헨글라트바흐", "FC Bayern Munich": "바이에른",
          "Borussia Dortmund": "도르트문트", "SV Werder Bremen": "브레멘", "Dacia Chisinau": "다치아 키시너우", "Bayer 04 Leverkusen": "레버쿠젠",
          "VfL Bochum": "보훔", "Eintracht Frankfurt": "프랑크푸르트", "SC Freiburg": "프라이부르크", "Karlsruher SC": "카를스루에",
          "Wolverhampton Wanderers": "울버햄프턴", "Arsenal FC": "아스널", "Bolton Wanderers": "볼턴", "Newcastle United": "뉴캐슬",
          "Hannover 96": "하노버", "FC Schalke 04": "샬케", "TSG 1899 Hoffenheim": "호펜하임", "1.FSV Mainz 05": "마인츠", "SC Paderborn 07": "파더보른"}
PK_DATES = ", ".join(d_(r[9]) + " " + KO_OPP[r[1]] + "전" for r in E if r[8])
NOTE_LINES = [
    f"라파엘 판데르파르트(아약스·함부르크 SV·레알 마드리드·토트넘 홋스퍼·함부르크 SV·레알 베티스·FC 미트윌란·에스비에르)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 덴보스전 ~ {d_(M[-1][0])} 오르후스전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·네덜란드 대표팀(A·U21·U20 등)·유소년·미트윌란 2군(덴마크 예비 리그 6경기 3골)·에스비에르 2군(2경기 1골) 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUBS[i][2]}({CLUBS[i][3]}) {c3(v)}" for i, v in enumerate(ST)) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(리그 외 경기 전부와 골·도움이 있는 경기 전부), 2010-11부터는 FotMob 경기 이벤트와 대조함(FotMob에는 아약스·함부르크 2005-08·레알 마드리드 시절 경기 자료가 없고, 토트넘 2011년 4경기는 FotMob 자료가 비어 있음)",
    "경기·골 수는 영어 위키백과 클럽·시즌별 기록과 모든 시즌에서 같음(통산 538경기 171골). 대회 구분만 다름: 미트윌란 2016-17 위키백과 리그 15경기 = Transfermarkt 리그 12경기 + 우승 결정 라운드 3경기. FotMob 경력 합계는 미트윌란 19경기·에스비에르 3경기로 Transfermarkt보다 1경기씩 적음(Transfermarkt 기준). Transfermarkt가 '다른 팀에서 뛰었음'으로 적은 미트윌란 2017-18 리그 5경기(같은 주 2군 경기)는 출전이 아님",
    "골: 2010-11 이후 골은 Transfermarkt와 FotMob이 수·분(±1분)·PK 여부가 모두 같음(FotMob 자료가 빈 2011.4.20 아스널전 제외). 자책골 없음. PK 골: " + PK_DATES,
    f"도움: 2014년 8월 전은 Transfermarkt 리포트 도움(유형이 비어 있는 것 포함, FotMob 도움 기록이 이 시기에 없거나 거의 비어 있음), 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것 + 다른 출처 2곳이 확인한 것. 도움 {NA} = Transfermarkt 리포트 {N_TM_A} − 'Shot on goal'(슈팅 리바운드) {N_SOG} − 상대 자책골에 준 도움 {N_OGA}. PK 유도·본인 PK 골의 본인 도움은 없음",
    "'Shot on goal'로 뺀 5개: 2008.2.2 하노버전 올리치·2008.3.2 프랑크푸르트전 게레로(함부르크), 2010.10.16 파울류첸코(토트넘), 2014.3.26·2014.5.10 라소가(함부르크) — 이 중 2010.10.16·2014.3.26·2014.5.10은 FotMob이 판데르파르트 도움으로 세지만 슈팅 리바운드는 넣지 않는 규칙대로 뺌. 상대 자책골에 준 도움 3개: 2006.3.12 카이저슬라우테른전 쇤하임, 2006.8.19 코트부스전 치비히, 2008.9.30 제니트전 후보찬",
    "FotMob에 없지만 다른 출처 2곳이 판데르파르트 도움으로 적어 넣은 3개: 2014.8.18 코트부스전(DFB-포칼) 70분 베스테르만 골(Sport1·로이터: 판데르파르트 프리킥을 헤더), 2014.10.29 바이에른전(DFB-포칼) 85분 라소가 골(kicker·FC 바이에른 구단 경기 기사), 2015.12.15 스포르팅 히혼전(코파 델 레이) 18분 판볼프스빙컬 골(레알 베티스 구단 기사·betisweb 경기 기록, 근거가 상대적으로 약함). 2014년 8월 이후 FotMob에만 있는 도움은 없음(FotMob 경기 자료는 Transfermarkt 골·도움 경기만 받음)",
    "2014년 8월 전 도움(아약스 28개 포함)은 Transfermarkt 한 곳 기준이라 하나하나 다른 출처와 대조하지는 않음. 2013.10.27 프라이부르크전 47분 라소가 골 도움은 Transfermarkt에만 있으나 2014년 8월 전이라 넣음",
    f"도움 합계 비교: Transfermarkt 1군 117·FotMob 경력 합계(아약스 제외, 함부르크 2005-08 0) 46·이 계산기 {NA}",
    "날짜는 현지 날짜(Transfermarkt 리포트 날짜, 리포트가 없는 리그 경기는 Transfermarkt 일정표 날짜; 모든 경기가 유럽)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(이브라히모비치·스네이더르·이과인·라울·로번·판니스텔로이·호날두·카카·벤제마·베일·손흥민 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위를 리그 모형에 넣은 값 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "리그 모형: 에레디비시는 다른 선수 자료의 순위별 값(시즌 무관), 2. 분데스리가·챔피언십은 다른 선수 자료의 순위별 값, 3. 리가 2014-15(코트부스 7위)는 다른 선수 자료와 같은 3부 모형",
    "직접 추정(모두 '추정'): 헨트 2000-01(벨기에 5위) 1545, RBC 로젠달 2001-02(네덜란드 2부 3위) 1390, 슈투트가르터 키커스 2005-06(독일 3부 레기오날리가 남부 8위) 1450, 바이킹 2005(노르웨이 5위) 1371, 코펜하겐 2005-06(덴마크 1위) 1560, 시그마 올로모우츠 2005-06(체코 9위) 1400, CSKA 모스크바 2006(러시아 1위) 1630, 혼베드 2007-08(헝가리 8위) 1380, 다치아 키시너우 2007-08(몰도바) 1350, 디나모 자그레브 2007-08(크로아티아 1위) 1520, 리텍스 로베치 2007-08(불가리아 4위) 1450, 홀슈타인 킬 2007-08(독일 4부 1위) 1300, 로트바이스 에센 2007-08(독일 3부 12위) 1450, 쇼트 예나 2013-14(독일 4부) 1300, 코펜하겐 2016-17(덴마크 1위) 1590, 브뢴뷔 2016-17(덴마크 2위) 1560, 호르센스 2016-17(덴마크 하위권) 1450. 덴마크·노르웨이·체코 등은 리그 모형이 없어 다른 선수 자료의 같은 수준 값을 씀",
    "대회 비중: KNVB컵·DFB-포칼·코파 델 레이·FA컵·리그컵·덴마크컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중; FA컵 5라운드 재경기는 16강, 6라운드는 8강), DFB-리가포칼(시즌 전 리그컵)은 첫 경기(8강 격)·준결승을 국내컵 8강·준결승으로, 요한 크루이프 스할·수페르코파(두 경기)는 국내컵 결승으로 계산함. 인터토토컵(결승 포함)·UEFA컵 예선·UEFA컵 1라운드는 유로파 예선, UEFA컵 2라운드·3라운드·32강·16강은 유로파 토너먼트, UEFA컵 조별은 유로파 조별로 계산함. 덴마크 수페르리가 우승 결정 라운드는 리그 경기",
    "분데스리가 승강 플레이오프(2014 그로이터 퓌르트, 2015 카를스루에)는 리그 비중에 두 경기 합산(원정 다득점·연장 있음)으로 계산함(다른 선수 자료와 같은 규칙). 2014.5.18 퓌르트전 14분 라소가 골 도움이 여기에 해당(1차전 0:0, 1:1로 끝나 원정 다득점으로 잔류)",
    f"두 경기 합산(챔스·UEFA컵 토너먼트와 예선, 인터토토컵, 코파 델 레이 32강, 수페르코파, 승강 플레이오프) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회·승강 플레이오프 2020-21까지, 스페인 국내 대회 2018-19까지(모두 연장 있음). 판데르파르트가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 함부르크는 7월 10일 기준(2005.7 인터토토·2006.7.29 DFB-리가포칼·2007.7 인터토토가 새 시즌), 나머지 클럽은 8월 1일 기준. 클럽 구분은 2005.7.1 전 아약스, 2008.8.4 전 함부르크, 2010.8.31 전 레알 마드리드, 2012.8.31 전 토트넘, 2015.7.1 전 함부르크, 2016.8.10 전 레알 베티스, 2018.8.4 전 미트윌란, 이후 에스비에르(Transfermarkt 이적일). 함부르크 두 시기는 같은 클럽으로 묶음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 에레디비시 2001-02·2003-04(아약스), 덴마크 수페르리가 2017-18(미트윌란, 그 시즌 출전 2경기), KNVB컵 2001-02, 요한 크루이프 스할 2002, 수페르코파 2008, 인터토토컵 2005·2007(함부르크), 골든 보이 2003. 월드컵 준우승 등 대표팀 기록은 뺌",
    "은퇴(2018년 11월 발표). 마지막 경기 2018.9.30 에스비에르 오르후스전. 2018.11 알가라파 이적 기록은 있으나 출전 없음",
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
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const VDV_E={J(E)};\nconst VDV_M={J(M)};\nconst VDV_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for i, v in enumerate(ST): print(" ", CLUBS[i][0], v)
