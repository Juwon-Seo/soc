#!/usr/bin/env python3
"""Diego Capel Trinidad(디에고 카펠, Transfermarkt 27471): raw/ -> capel.json + src/data/cpl.js (판정 근거는 judgments.md)

  python3 players/capel/build_capel.py            # 파일 쓰기
  python3 players/capel/build_capel.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/capel/build_capel.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/capel/build_capel.py --fm       # FotMob 골 대조(2010-11~)
  python3 players/capel/build_capel.py --root=<스크래치 복사본>   # 그 복사본의 src/data에 쓰기(검증용)

비센테 빌드(build_vicente.py)를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv·tm_two_leg_ties.csv(합산), raw/fotmob_events.csv(FotMob 경기 이벤트, 2010-11~), raw/ranks.txt(순위표),
/home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):   # 스크래치 복사본에 쓰기(검증용)
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(os.path.dirname(os.path.dirname(HERE)), "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "cpl.js")
OUT_JSON = os.path.join(HERE, "capel.json")
ME = "디에고 카펠"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트, 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# 범위: tm_games.csv = 성인 1군 공식 경기 390(세비야·스포르팅·제노아·안데를레흐트·엑스트레마두라·비르키르카라·이로도토스).
# 세비야 아틀레티코(2군, 세군다 B)는 tm_games.csv에 없음(따로 youth_reserve_games.csv, 쓰지 않음).
# 비르키르카라(몰타 1부 2019-20)·이로도토스(그리스 2부 수페르리그 2 2021-22)는 넣음(judgments.md 1절).
GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
OTHER = {r["gameId"]: r["other_leg_id"] for r in rd("tm_two_leg_ties.csv")}
for gid, r in INFO.items():
    if r["other_leg_id"]:
        OTHER.setdefault(gid, r["other_leg_id"]); OTHER.setdefault(r["other_leg_id"], gid)
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
MIN_FIX = {}   # 출전 분 고침 없음(Transfermarkt 그대로, judgments.md 2절)
# 날짜 고침: 2018-19 세군다 41라운드 카디스 원정은 2019.6.4(화) 경기 — LaLiga 공식 경기 페이지·Goal.com 예고·영어 위키 2018-19 카디스 시즌 문서, FotMob 2019-06-04.
# Transfermarkt API·일정은 2019.6.2로 적음(리포트 저장 안 됨)
DATE_FIX = {"3094123": "2019-06-04"}
# 2014-08 이후 Transfermarkt 단독 도움(FotMob 경기 이벤트에 도움자 없음) 중 다른 출처 2곳이 확인한 것
ADD_CONFIRMED = {
    "2526237|85": "2015.4.27 모레이렌스 원정 85분 몬테로 헤더: Observador 경기 기사(카펠이 왼쪽에서 공간을 만들어 크로스) + Correio da Manhã 문자 중계('Capel cruzou da esquerda e o colombiano fez de cabeça o 4-1')",
    "2732110|76": "2016.9.18 헹크 원정 76분 하르바우이: DH·La Libre 기사(같은 글, 1곳으로 셈: 'Capel débordait sur la droite et centrait, Harbaoui reprenait en demi-volée') + anderlecht-online.be 경기 기사('scoring on a centre of Capel')",
}
# 다른 출처 2곳을 찾지 못해 뺀 2014-08 이후 Transfermarkt 단독 도움(judgments.md 4절)
UNCONF = {
    "2466863|82": "2014.10.4 페나피엘 원정 82분 몬테로: Bola na Rede·FourFourTwo 기사에 도움 서술 없음('tapping in at the far post'), FotMob 이벤트 도움자 없음",
    "2512700|32": "2014.11.21 이스피뉴 원정(타사 4라운드) 32분 주앙 마리우: Bola na Rede 기사 1곳만('cruzamento do espanhol'), 다른 기사 못 찾음",
}

# ---------------------------------------------------------------- 대회 코드
# 리그 비중: 라리가·프리메이라리가·세리에A·벨기에 1부와 챔피언십 플레이오프(EJPL, 데 브라위너·데이비드·베일리 선례)·세군다·몰타 1부·그리스 2부
LEAGUE = {"ES1", "ES2", "PO1", "IT1", "BE1", "EJPL", "MAL1", "GRS2"}
CUP = {"CDR", "POPO", "CCB", "MALC"}   # 코파 델 레이·타사 드 포르투갈·벨기에컵·몰타 FA 트로피

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:   # 16강까지 dc / 8강 dk / 준결승 dsf / 결승 df (벨기에컵 6라운드 = 32강, 코파 델 레이 2라운드 재경기 = dc)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "POCP":   # 타사 다 리가 조별: 리그식 국내컵(브루노·하피냐·팔카오 선례)
        if r.startswith("group"): return "dc"
    if cid in ("SUC", "USC"): return "df"   # 수페르코파 = 국내컵 결승(§3)
    if cid == "CLQ": return "clq"
    if cid == "ELQ": return "elq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 32강('Second Round'·'intermediate stage')·16강·8강
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 32강(intermediate stage)·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스·유로파·UEFA컵 조별, 타사 다 리가 조별
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]
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
    if cid in ("CL", "CLQ", "UEFA", "EL", "ELQ", "CDR", "SUC", "POPO"):
        ag, et = 1, 1   # 모두 2017년 이전: UEFA 대회(2020-21까지)·코파 델 레이(2018-19까지)·수페르코파·타사 준결승(브루노·팔카오 선례) 원정 다득점·연장
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
MANUAL_ALIAS = {}
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
        if p[0] == "league" or len(p) < 5: continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 공식 최종 순위로 고친 순위(영어 위키백과 시즌 문서; Transfermarkt 표는 동률 순서가 다름)
#  - 2012-13 프리메이라리가: 리우 아베 6위·스포르팅 7위(TM 표는 반대; 기존 다른 선수 자료도 스포르팅 2012-13 7위)
#  - 2012-13 프리메이라리가: 질 비센트 13위·올라넨스 14위(TM 표는 반대)
#  - 2011-12 프리메이라리가: 베이라마르 12위·아카데미카 13위(승점 29 동률, 상대 전적; TM 표는 반대)
#  - 2013-14 프리메이라리가: 파수스 드 페헤이라 15위·올라넨스 16위(TM 표는 반대)
RANK_FIX = {("PO1", "2012-13", "Rio Ave FC"): 6, ("PO1", "2012-13", "Sporting CP"): 7,
            ("PO1", "2012-13", "Gil Vicente FC"): 13, ("PO1", "2012-13", "SC Olhanense"): 14,
            ("PO1", "2011-12", "SC Beira-Mar"): 12, ("PO1", "2011-12", "Académica Coimbra"): 13,
            ("PO1", "2013-14", "FC Paços de Ferreira"): 15, ("PO1", "2013-14", "SC Olhanense"): 16}
for (lg, s, t), r in RANK_FIX.items():
    n = RANKS[(lg, s)][key(t)][1]; RANKS[(lg, s)][key(t)] = (r, n)

_SA20 = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
_CV = [(v - 1739) / 91.3 for v in _SA20]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return _CV[i] + (_CV[i + 1] - _CV[i]) * t
SD2 = 51.24   # 2부 흩어짐(팔카오·후이 코스타 선례)

def po1_known(nteams):
    """프리메이라리가 16팀(2006-07~2013-14)·18팀 시즌: 기존 선수 자료(elo/ents.json)의 순위별 최빈값"""
    t = collections.defaultdict(collections.Counter)
    for x in ENTS:
        m = re.match(r"포르투갈 1부 (\d{4})-\d\d (\d+)위", x["lv"])
        if not m: continue
        y = int(m.group(1))
        if (nteams == 16) == (2006 <= y <= 2013):
            t[int(m.group(2))][x["elo"]] += 1
    return {k: v.most_common(1)[0][0] for k, v in t.items()}
PO1_16, PO1_18 = po1_known(16), po1_known(18)

def model(lg, season, r, n):
    if lg == "PO1":
        tab = PO1_16 if n == 16 else PO1_18
        return tab[r], f"포르투갈 1부 {season} {r}위"
    if lg == "PO2":   # 포르투갈 2부: 1367 + 2부 흩어짐 × 순위 곡선(디 마리아·팔카오·후이 코스타 선례, 추정)
        return int(1367 + SD2 * curve(r, n) + 0.5), f"포르투갈 2부 {season} {r}위 (추정)"
    if lg == "MAL1":  # 몰타 1부(새, 추정): 평균 1340(발부에나 자료의 몰타 1부 평균 — 국가 계수 회귀, 계수 약 1.5) + 흩어짐 63(키프로스·노르웨이 선례) × 순위 곡선
        return int(1340 + 63 * curve(r, n) + 0.5), f"몰타 1부 {season} {r}위 (추정, 리그 수준 추정)"
    return None
RANK_LG = ["PO1", "PO2", "MAL1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정') — judgments.md 7절
MAN = {
    (key("SC Alba"), "2013-14"): (1150, "포르투갈 지역 리그(아베이루 지구) 2013-14 (추정, 다른 선수 자료 포르투갈 아마추어 1150과 같음)"),
    (key("SC Espinho"), "2014-15"): (1250, "포르투갈 3부 2014-15 C조 10위 (추정, 다른 선수 자료 포르투갈 3부 값과 같음)"),
    (key("FC Nordsjælland"), "2011-12"): (1560, "덴마크 2011-12 1위 (추정, 다른 선수 자료 덴마크 1위 1560과 같음)"),
    (key("AC Horsens"), "2012-13"): (1450, "덴마크 2012-13 11위 (추정, 다른 선수 자료 덴마크 하위권 1450과 같음)"),
    (key("FK Gabala"), "2016-17"): (1450, "아제르바이잔 2016-17 2위 (추정, 다른 선수 자료 아제르바이잔 2위 1450과 같음)"),
    (key("Royal Excel Mouscron (-2022)"), "2016-17"): (1347, "벨기에 1부 2016-17 15위 (추정, 다른 선수 자료 13위 1380·16위 1314의 가운데)"),
}
# 이름이 같은 다른 팀: 통합표는 우루과이 나시오날(Club Nacional)과 포르투갈 CD 나시오날(마데이라)을 한 팀으로 묶어 2012-13에 우루과이 값(1602)이 있음
# → 포르투갈 나시오날 2012-13(최종 8위, 영어 위키백과)은 순위값을 바로 쓰고, 기록의 상대 표기를 'CD Nacional (Madeira)'로 나눔(judgments.md 7절)
PRE_MAN = {("CD Nacional", "2012-13"): (1578, "포르투갈 1부 2012-13 8위")}
OPP_NAME = {("CD Nacional", "2012-13"): "CD Nacional (Madeira)"}
ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    if (A ^ B) & {"b", "c", "ii", "atletico"}: return False   # 2군·다른 팀(아틀레티코 마드리드 ≠ 마드리드)
    return bool(A) and bool(B) and (A <= B or B <= A)

UEFA_C = ("CL", "CLQ", "UEFA", "EL", "ELQ", "USC")
def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    if (opp, eu) in PRE_MAN:
        e, lv = PRE_MAN[(opp, eu)]; ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, e, lv, "pre", []))
        return e, lv
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]",
                        sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in UEFA_C else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, eu))
        if t and k in t:
            r, n = t[k]
            res = model(lg, eu, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    # 현지 날짜: 세비야·엑스트레마두라 마드리드, 스포르팅 리스본, 제노아 로마, 안데를레흐트 브뤼셀, 비르키르카라 몰타, 이로도토스 아테네 시간
    return DATE_FIX.get(g["gameId"], g["date_local_computed"])

M = []
for g in GAMES:
    mins = MIN_FIX[g["gameId"]][0] if g["gameId"] in MIN_FIX else int(g["playedMinutes"])
    M.append([ldate(g), OPP_NAME.get((g["opponent"].strip(), season_eu(ldate(g))), g["opponent"].strip()), comp_of(g["competitionId"], g["round"]), mins])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["capel_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
UNCONF_LIST = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et=0):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    opp = OPP_NAME.get((opp, season_eu(d)), opp)
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["capel_scorer"] == "1", e["capel_assist_other"] == "1"
    if e["capel_self_assist"] == "1":
        EXCL_CNT["본인 도움"] += 1
    if e["capel_own_goal_against_own_team"] == "1":
        judg.append(("본인 자책골(골 아님)", ldate(g), g["opponent"], e["minute"])); EXCL_CNT["본인 자책골"] += 1
        continue
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
    et = int("+" not in e["minute"] and mi > 90)   # 연장 골·도움
    if et and g["gameState"] not in ("extra_time", "penalty_shootout"): sys.exit("연장 판정 이상 " + gid)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"].startswith("Penalty"): why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        if why:
            EXCL_CNT[why] += 1; EXCL_LIST[why].append((d, opp, e["minute"], e["scorer"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - mi) <= 3]
            if not hit:
                if tag in UNCONF:
                    UNCONF_LIST.append((d, opp, e["minute"], e["scorer"], UNCONF[tag])); EXCL_CNT["2014.8 이후 단독 도움(확인 못 함)"] += 1
                    judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], UNCONF[tag])); continue
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []   # FotMob 경기 이벤트의 카펠 도움 6개는 모두 Transfermarkt에도 있음
for gid, ts in FM_ASSIST.items():
    if gid not in G: continue
    for t in ts:
        if not any(e["gameId"] == gid and e["capel_assist_other"] == "1" and abs(minute(e["minute"])[0] - t) <= 3 for e in EVENTS):
            FM_ONLY.append((gid, t))

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u)
for f in FM_ONLY: print("판정 필요(FotMob 단독 도움):", f)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
if UNDECIDED or missing_elo or FM_ONLY:
    if "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, EXCL_CNT)
    for k, v in EXCL_LIST.items(): print(k, v)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11~)
FM_CMP = []
for gid, evs in FM_EV.items():
    if gid not in G: continue
    fg = sorted(int(r["time"]) for r in evs if r["capel_scorer"] == "1" and r["pen_shootout_event"] != "True")
    tg = sorted(minute(e["minute"])[0] for e in EVENTS if e["gameId"] == gid and e["capel_scorer"] == "1")
    if len(fg) != len(tg) or any(abs(a - b) > 1 for a, b in zip(fg, tg)):
        FM_CMP.append((gid, G[gid]["date_local_computed"], tg, fg))
if __name__ == "__main__" and "--fm" in sys.argv:
    print("FotMob 골 차이:", FM_CMP)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
import subprocess
def load_js(fn):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const ([A-Z0-9]+)_E=(\[.*?\]);\n", s, re.S)
    return (m.group(1), json.loads(m.group(2))) if m else (None, [])
try:   # git이 추적하는 기존 선수 파일만(병렬 작업 중인 새 선수 파일은 보지 않음)
    TRACKED = subprocess.run(["git", "-C", os.path.dirname(os.path.dirname(HERE)), "ls-files", "src/data"], capture_output=True, text=True).stdout.split()
    TRACKED = [os.path.basename(t) for t in TRACKED if t.endswith(".js") and not t.endswith("hon.js")]
except Exception:
    TRACKED = []
OTHERS = {}
for fn in TRACKED:
    if fn == "cpl.js" or not os.path.exists(os.path.join(ROOT, "src", "data", fn)): continue
    P, ent = load_js(fn)
    if P: OTHERS[fn] = ent
def cmp_rows(a, b, full=True):
    diffs = []
    if full and abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if full and (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if full and a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or (ta and tb and ta[1:] != tb[1:] and full) or (bool(ta) != bool(tb)):
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
ME_NAMES = ("diego capel", "capel")
CROSS = []
for fn, ent in OTHERS.items():
    for x in ent:   # 같은 날짜·같은 상대(= 같은 팀 동료 자료)
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                CROSS.append(("같은 경기(동료)", fn, r[9], r[1], cmp_rows(r, x, full=False) or "같음"))
                break
    for x in ent:   # 동료 도움 → 카펠 골
        if x[0] == "a" and norm(x[13] or "") in ME_NAMES:
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append(("동료 도움→카펠 골", fn, x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:   # 카펠 도움 → 동료 골
        if r[0] == "a":
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and key(x[1]) == key(r[1]) and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            if hit: CROSS.append(("카펠 도움→동료 골", fn, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:   # Transfermarkt 카펠 도움을 뺀 동료 골(참고)
        if x[0] == "g":
            tm = [e for e in EVENTS if e["capel_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and key(G[e["gameId"]]["opponent"]) == key(x[1]) and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 카펠 도움을 뺀 동료 골", fn, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # TM 동료 도움 → 카펠 골인데 동료 파일에 없음(참고)
        if e["capel_scorer"] == "1" and e["gameId"] in G and e["assist_player"]:
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            mates = [x for x in ent if x[9] == d and key(x[1]) == key(G[e["gameId"]]["opponent"])]
            if mates and not any(x[0] == "a" and abs(x[4] - mi) <= 2 for x in mates):
                CROSS.append(("TM 동료 도움 → 카펠 골(동료 파일에 도움 없음, 참고)", fn, d, e["minute"], e["assist_player"], e["assist_type"]))
# 같은 날 상대 편 자료(상대 팀 선수 파일에 카펠 팀이 상대로 나오는 경기): 날짜 차이 확인
OPP_SIDE = []
MY_TEAMS = {"sevilla", "sevilla fc", "sporting cp", "sporting", "genoa", "genoa cfc", "rsc anderlecht", "anderlecht", "extremadura ud", "birkirkara fc", "pas irodotos"}
for fn, ent in OTHERS.items():
    for x in ent:
        if norm(x[1]) in MY_TEAMS or key(x[1]) in {key(t) for t in MY_TEAMS}:
            near = [m for m in M if abs((Date.fromisoformat(m[0]) - Date.fromisoformat(x[9])).days) <= 1]
            OPP_SIDE.append((fn, x[9], x[1], [m[0] for m in near]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음" or c[0].startswith(("동료", "카펠")): print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("sevcp", "2011-07-01", "세비야", "2004~2011"), ("spocp", "2015-08-18", "스포르팅 CP", "2011~2015"),
         ("gencp", "2016-08-04", "제노아", "2015~2016"), ("andcp", "2017-08-30", "안데를레흐트", "2016~2017"),
         ("extcp", "2019-07-01", "엑스트레마두라", "2018~2019"), ("bircp", "2020-07-01", "비르키르카라", "2020"),
         ("irocp", None, "PAS 이로도토스", "2022")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, _, _, _ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TMC = {"368": "sevcp", "336": "spocp", "252": "gencp", "58": "andcp", "29095": "extcp", "10262": "bircp", "9073": "irocp"}
for g in GAMES:
    if club_of(ldate(g)) != TMC[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_capel import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["capel_assist_other"] == "1")
N_TM_G = sum(1 for e in EVENTS if e["gameId"] in G and e["capel_scorer"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, N_TM_G=N_TM_G, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const CPL_E={J(E)};\nconst CPL_M={J(M)};\nconst CPL_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "opponent_side_dates": OPP_SIDE, "fotmob_goal_diffs": FM_CMP, "unconfirmed_assists": UNCONF_LIST,
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
