#!/usr/bin/env python3
"""Yannick Carrasco: raw/ -> carrasco.json + src/data/crr.js (판정 근거는 judgments.md)

  python3 players/carrasco/build_carrasco.py            # 파일 쓰기
  python3 players/carrasco/build_carrasco.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/carrasco/build_carrasco.py --cross    # 동료·같은 경기 자료 대조
  python3 players/carrasco/build_carrasco.py --fm       # FotMob 골 대조
  python3 players/carrasco/build_carrasco.py --root=<스크래치 복사본>   # 그 복사본의 src/data에 쓰기(검증용)

코스티치(build_kostic.py) 빌드를 바탕으로 함. 접두어 CRR(crr.js), 프리셋 id carrasco.
입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
/home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(동료 자료 대조).
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
OUT_JS = os.path.join(ROOT, "src", "data", "crr.js")
OUT_JSON = os.path.join(HERE, "carrasco.json")
ME = "야닉 카라스코"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트, 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

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
# 출전 분 고침: gameId -> (분, 근거)  (없음: Transfermarkt 출전 분 그대로)
MIN_FIX = {}
# Transfermarkt 리포트 골 뒤 스코어 고침(리포트 내부 오류): gameId|분 -> 골 뒤 스코어(홈-원정)
SCORE_FIX = {
    "2223643|45+3": "0-1",   # 앙제-모나코: 리포트가 45+3분 카라스코·48분 투레 모두 0:2로 적음. 전반 0:1(리포트), FotMob 45분 0-1·48분 0-2
}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'·자책골은 일반 규칙)
EXCL_A = {
    "2529699|9": "2015.2.11 렌전(쿠프 드 프랑스 16강) 9분 알마미 투레 골: FotMob 경기 기록에 도움·라인업 없음, 카라스코 코너킥이라고 적은 곳은 Maxifoot 경기 기사 1곳뿐(다른 출처 2곳 확인 못 함)",
    "2529699|11": "2015.2.11 렌전 11분 왈라스 골: FotMob 도움 없음, 카라스코 프리킥이라고 적은 곳은 Maxifoot 1곳뿐",
    "3003879|73": "2018.9.14 톈진 취안젠전 73분 리솨이 골: FotMob 도움 없음, 카라스코 도움으로 적은 다른 출처 없음(ESPN 경기 기록·영어 위키백과 시즌 문서는 득점자만)",
    "3156459|52": "2019.6.29 베이징 런허전 52분 함식 골: FotMob 경기 이벤트는 이 골을 상대 자책골로 적고 도움 없음, 카라스코 도움으로 적은 다른 출처 없음",
    "3716578|16": "2022.1.6 라요 마하다온다전(코파 델 레이) 16분 쿠냐 골: FotMob 도움 없음, 아틀레티코 구단 기사는 '카라스코에 맞고 나온 공'(굴절·흐른 공)을 쿠냐가 찼다고 적음 — LaLiga 문자 중계만 도움으로 셈",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳 이상이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2518999|8": "2015.1.14 갱강전(쿠프 드 라 리그 8강) 8분 베르바토프 골: Maxifoot 경기 기사(제르맹 헤더 패스를 받은 카라스코가 오른발 크로스, 베르바토프 헤더)·monacoinfo.com 영상 기사('great assist of Yannick Ferreira Carrasco'); FotMob은 이 경기 라인업·도움 자료 없음",
    "2647660|40": "2016.1.14 라요 바예카노전(코파 델 레이 16강 2차전) 40분 코레아 골: ESPN 문자 중계('Assisted by Yannick Carrasco')·LaLiga 공식 문자 중계('Asistencia de Yannick Carrasco')·worldfootball 경기 기록; FotMob은 이 경기 도움 자료 없음",
    "4222014|24": "2023.12.11 알나스르전(킹스컵 8강) 24분 카를루스 주니오르 골: Arab News 경기 기사('headed home a Carrasco corner')·Trivela 경기 기사(카라스코 코너킥을 헤더)",
    "4587285|67": "2025.4.1 알이티하드전(킹스컵 준결승) 67분 구안카 골: Arab News 경기 기사('Carrasco floated over a cross to the far post')·Saudi Gazette 경기 기사(카라스코 크로스 헤더)",
}
# FotMob에만 있는 도움(판정 끝남, 넣지 않음) — judgments.md 4절
FM_ONLY_DECIDED = {
    "2755698": "2016.11.1 로스토프전(챔스 조별) 29분 그리즈만 골: Transfermarkt 도움 없음, ESPN 경기 기사는 카라스코 공이 아즈문에 맞고 흘러 그리즈만이 마무리했다고 적음(굴절) — 넣지 않음",
    "4138396": "2023.10.5 알리야드전 53분 사이스 골: Transfermarkt·Fox Sports는 바네가 도움, FotMob·Sporting Life만 카라스코 — 넣지 않음(87분 이아구 산투스 골 도움은 두 출처 일치로 넣음)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR2", "FR1", "ES1", "CSL", "SA1"}
CUPS = {"FRC", "FRL", "CDR", "CHFA", "SAKC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:   # 국내컵: 16강까지 dc / 8강 dk / 준결승 dsf / 결승 df
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "SUC":   # 수페르코파 2021-22(4팀): 준결승 dsf
        return "dsf" if r.startswith("semi") else "df"
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
        return "elk"   # intermediate stage(32강)·16강·8강
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
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local_computed"]
    leg = 1 if "1st" in g["round"].lower() else 2
    o = INFO[OTHER[gid]]
    if (o["date_report"] < inf["date_report"]) != (leg == 2): sys.exit("차전 순서 이상 " + gid)
    home = int(inf["home_id"] == g["club_id"])
    if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    fu = ft = 0
    if leg == 2:
        oh, oa = map(int, re.match(r"(\d+):(\d+)", o["final"]).groups())
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "EL"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CDR":   # 코파 델 레이: 원정 다득점 2018-19까지, 2차전 연장
        ag, et = int(d < "2019-07-01"), 1
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
ENTS_BY_D = collections.defaultdict(list)
for x in ENTS: ENTS_BY_D[x["date"]].append(x)

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    if d[:7] in ("2020-07", "2020-08"): s = 2019   # 코로나로 늦게 끝난 2019-20 시즌
    return f"{s}-{str(s + 1)[2:]}"

def season_of(d, cid):
    """상대 수준 시즌: 중국 대회는 달력 연도, 나머지는 유럽식"""
    return d[:4] if cid in ("CSL", "CHFA") else season_eu(d)

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 순위 곡선(league_model.py와 같은 21칸 곡선)
SA_CURVE = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA_CURVE]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

# 프랑스 리그2 2012-13(20팀): 다른 선수 자료(마레즈)의 순위값 = int(1540 + 51.24 × 곡선) — 2·9·10·11·14·16·18위 재현
def fr2(r, n):
    return int(1540 + 51.24 * curve(r, n))
# 중국 슈퍼리그(16팀): 함식 자료와 같은 방식 — 드록바 2012 자료 순위별 값, 없는 순위는 같은 모형(평균 1484·흩어짐 63)
CN_FIX = {4: 1526, 5: 1514, 6: 1501, 7: 1489, 10: 1458, 11: 1452, 12: 1446, 13: 1433, 14: 1422, 15: 1411, 16: 1397}
def cn_val(r):
    return (CN_FIX[r], "같음") if r in CN_FIX else (round(1484 + 63 * curve(r, 16)), "같은 모형")
# 사우디 프로리그(18팀): 다른 선수 자료의 순위값(2023-24~2025-26 시즌 모두 같은 값)
SAU = {1: 1813, 2: 1703, 3: 1641, 4: 1604, 5: 1585, 6: 1568, 7: 1544, 8: 1519, 9: 1497, 10: 1481, 11: 1469, 12: 1456,
       13: 1450, 14: 1432, 15: 1408, 16: 1389, 17: 1377, 18: 1352}
NOW = "(11월 중순 현재)"

def model(lg, season, r, n):
    if lg == "FR2" and n == 20:
        return fr2(r, n), f"프랑스 리그2 {season} {r}위"
    if lg == "CSL" and n == 16:
        v, how = cn_val(r); return v, f"중국 슈퍼리그 {season} {r}위 (추정, 다른 선수 자료 중국 슈퍼리그 2012 순위별 값과 {how})"
    if lg == "SA1" and n == 18:
        cur = " " + NOW if season == "2026-27" else ""
        return SAU[r], f"사우디 프로리그 {season}{cur} {r}위"
    if lg == "SA2L":
        cur = " " + NOW if season == "2026-27" else ""
        return 1300, f"사우디 2부 {season}{cur} {r}위/{n}팀 (추정, 다른 선수 자료 사우디 2부 1300과 같음)"
    if lg == "E4G1":
        return 1150, f"스페인 4부(세군다 페데라시온) {season} 1조 {r}위 (추정, 다른 선수 자료 스페인 4부 1150과 같음)"
    return None
RANK_LG = ["FR2", "CSL", "SA1", "SA2L", "E4G1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정') — judgments.md 7절
MAN = {}
ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d); se = season_of(d, cid)
    dd = Date.fromisoformat(d)
    same = []
    for delta in (-1, 0, 1):
        dx = Date.fromordinal(dd.toordinal() + delta).isoformat()
        same += [x for x in ENTS_BY_D.get(dx, []) if key(x["opp"]) == k or _sub(key(x["opp"]), k)]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]",
                        sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [se, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL") else [se]
    for s in seasons:
        if (k, s) in TABLE:
            cand = TABLE[(k, s)]
            pref = {"SA1": "사우디", "SAKC": "사우디", "CSL": "중국", "CHFA": "중국"}.get(cid)
            if pref and any(pref in lv for _, lv in cand):   # 같은 이름 다른 나라 팀(알아흘리 사우디/카타르) 구분
                cand = [c for c in cand if pref in c[1]]
            (e, lv), _ = collections.Counter(cand).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, se) in MAN:
        e, lv = MAN[(k, se)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, se))
        if t and k in t:
            r, n = t[k]
            res = model(lg, se, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_computed"]   # Transfermarkt 리포트 날짜와 모두 같음(254경기 대조)

M = []
for g in GAMES:
    mins = MIN_FIX[g["gameId"]][0] if g["gameId"] in MIN_FIX else int(g["playedMinutes"])
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), mins])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["carrasco_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
PRE_GAP_TM_ONLY = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et=0):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_of(d, cid), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["carrasco_scorer"] == "1", e["carrasco_assist_other"] == "1"
    if e["carrasco_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag, ldate(g))); EXCL_CNT["본인 도움"] += 1
        EXCL_LIST["본인 도움"].append((ldate(g), g["opponent"], e["minute"], e["scorer"], e["assist_type"]))
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, SCORE_FIX.get(tag, e["score_home_away_after"]).split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = int(ko == 1 and tie is None and int(e["minute"].split("+")[0]) > 90)   # 연장 골(120+2 포함), 90+x는 정규시간
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            k = why if tag not in EXCL_A else "개별 판정"
            EXCL_CNT[k] += 1; EXCL_LIST[k].append((d, opp, e["minute"], e["scorer"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
        if d >= GAP and tag not in ADD_CONFIRMED:
            if not hit:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
            used_fm[gid] += 1
        elif d < GAP and not hit:
            PRE_GAP_TM_ONLY.append((d, opp, e["minute"], e["scorer"], e["assist_type"]))
        elif d < GAP:
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local_computed"] >= GAP and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")):
        FM_ONLY.append((gid, G[gid]["date_local_computed"], ts))

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u)
for f in FM_ONLY:
    if f[0] not in FM_ONLY_DECIDED: print("판정 필요(FotMob 단독 도움):", f)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
if UNDECIDED or missing_elo or any(f[0] not in FM_ONLY_DECIDED for f in FM_ONLY):
    if "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY, EXCL_CNT)
    for k, v in EXCL_LIST.items(): print(k, v)
    print("2014.8 전 Transfermarkt 단독 도움", len(PRE_GAP_TM_ONLY), PRE_GAP_TM_ONLY)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["carrasco_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local_computed"])); continue
    fg = [r for r in FM_EV[gid] if r["carrasco_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
# git에 올라간 기존 선수 파일만 읽음(병렬 판정 중인 다른 새 선수 파일은 읽지 않음)
import subprocess
TRACKED = subprocess.run(["git", "-C", os.path.dirname(os.path.dirname(HERE)), "ls-files", "src/data"], capture_output=True, text=True).stdout.split()
OTHERS = {}
for fn in TRACKED:
    b = os.path.basename(fn)
    if not b.endswith(".js") or b in ("hon.js", "crr.js"): continue
    t = open(os.path.join(os.path.dirname(os.path.dirname(HERE)), fn), encoding="utf-8").read()
    m = re.search(r"const ([A-Z0-9]+)_E=(\[.*?\]);\n", t, re.S)
    if m: OTHERS[b] = json.loads(m.group(2))
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
def same_name(a, b):
    A, B = norm(a).split(), norm(b).split()
    if not A or not B: return False
    return set(A) <= set(B) or set(B) <= set(A) or (A[-1] == B[-1] and A[0][0] == B[0][0])
MY_CLUB_NAMES = {"162": ["AS Monaco", "Monaco"], "13": ["Atlético Madrid", "Atletico Madrid", "Atlético de Madrid"],
                 "33304": ["Dalian Yifang", "Dalian Professional", "Dalian"], "9840": ["Al-Shabab", "Al Shabab", "Al-Shabab FC"]}
CROSS, SAME_GAME, VS = [], [], []
MDATES = {m[0] for m in M}
for fn, ent in OTHERS.items():
    for x in ent:
        if x[9] not in MDATES: continue
        mine = [r for r in E if r[9] == x[9] and (key(r[1]) == key(x[1]) or _sub(key(r[1]), key(x[1])))]
        same_opp = bool(mine) or any(m[0] == x[9] and (key(m[1]) == key(x[1]) or _sub(key(m[1]), key(x[1]))) for m in M)
        if same_opp:   # 같은 팀 동료(같은 상대)
            for r in E:
                if r[9] == x[9] and (key(r[1]) == key(x[1]) or _sub(key(r[1]), key(x[1]))):
                    if r[3] != x[3] or r[2] != x[2] or r[12] != x[12]:
                        SAME_GAME.append((fn, x[9], x[1], f"대회 {r[3]}/{x[3]} Elo {r[2]}/{x[2]} lv {r[12]}/{x[12]}"))
            if x[0] == "g":   # 카라스코 도움 → 동료 골
                for r in E:
                    if r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 3:
                        CROSS.append(("카라스코 도움→" + fn + " 골", x[9], x[4], r[13], cmp_rows(r, x) or "같음"))
            if x[0] == "a" and "carrasco" in norm(str(x[13])):
                hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3]
                CROSS.append((fn + " 도움→카라스코 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        elif {"162": "monaco", "13": "atl", "33304": "dalian", "9840": "shabab"}[next(g["club_id"] for g in GAMES if ldate(g) == x[9])] in x[1].lower():
            VS.append((fn, x[9], x[0], x[1], x[4], x[5], x[6]))   # 상대 팀 선수 기록(날짜·스코어 참고)
# 계산기에 있는 동료(같은 팀 같은 경기): 파일 → 이름
MATES = {"grz.js": "Antoine Griezmann", "tor.js": "Fernando Torres", "sua.js": "Luis Suárez", "bsi.js": "Bernardo Silva",
         "fal.js": "Radamel Falcao", "ham.js": "Marek Hamsik"}
CROSS = [c for c in CROSS if not c[0].startswith("카라스코 도움→") or same_name(MATES.get(c[0].split("→")[1].split(" ")[0], "?"), c[3])]
for e in EVENTS:
    if e["gameId"] not in G: continue
    d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
    for fn, nm in MATES.items():
        ent = OTHERS[fn]
        if e["carrasco_assist_other"] == "1" and same_name(nm, e["scorer"]):
            mine = [r for r in E if r[0] == "a" and r[9] == d and abs(r[4] - mi) <= 2]
            theirs = [x for x in ent if x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 2]
            if not mine: CROSS.append(("TM 카라스코 도움을 뺀 동료 골", fn, d, e["minute"], e["assist_type"], "동료 골 행 " + ("있음" if theirs else "없음")))
            elif not theirs: CROSS.append(("카라스코 도움인데 동료 골 행 없음", fn, d, e["minute"]))
        if e["carrasco_scorer"] == "1" and e["assist_player"] and same_name(nm, e["assist_player"]):
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 카라스코 골, 동료 파일에 도움 행 없음", fn, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s_ in sorted(set(SAME_GAME)): print("같은 경기 차이:", s_)
    print("상대 팀 선수 기록", len(VS))
    for v in sorted(VS, key=lambda v: v[1]): print("  ", v)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("moncr", "2015-07-10", "AS 모나코", "2012~2015"), ("atmcr", "2018-02-26", "아틀레티코 마드리드", "2015~2018, 2020~2023"),
         ("dalcr", "2020-01-31", "다롄 이팡", "2018~2020"), ("atmcr", "2023-09-04", "아틀레티코 마드리드", "2015~2018, 2020~2023"),
         ("shbcr", None, "알샤바브", "2023~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"162": "moncr", "13": "atmcr", "33304": "dalcr", "9840": "shbcr"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])
# 아틀레티코 두 시기 나눔(설명용)
ATM1 = [sum(1 for m in M if "2015-07-10" <= m[0] < "2018-02-26"), sum(1 for r in E if r[0] == "g" and "2015-07-10" <= r[9] < "2018-02-26"),
        sum(1 for r in E if r[0] == "a" and "2015-07-10" <= r[9] < "2018-02-26")]

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_carrasco import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["carrasco_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC, PRE=PRE_GAP_TM_ONLY, ATM1=ATM1))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const CRR_E={J(E)};\nconst CRR_M={J(M)};\nconst CRR_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game_diffs": sorted(set(SAME_GAME)), "vs_rows": VS, "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY,
               "pre_2014_tm_only_assists": PRE_GAP_TM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
