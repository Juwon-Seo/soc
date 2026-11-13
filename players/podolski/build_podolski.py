#!/usr/bin/env python3
"""Lukas Podolski: raw/ -> podolski.json + src/data/pod.js (판정 근거는 judgments.md)

  python3 players/podolski/build_podolski.py            # 파일 쓰기
  python3 players/podolski/build_podolski.py --debug    # Elo 출처 로그
  python3 players/podolski/build_podolski.py --cross    # 동료 자료 대조
  python3 players/podolski/build_podolski.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/fotmob_playerMatches.csv,
      raw/fotmob_tm_map.csv, raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/*.js(git에 있는 기존 선수 파일: 같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다. 빌드 뼈대는 외질(build_ozil.py).
"""
import csv, json, os, re, sys, unicodedata, collections, subprocess
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "pod.js")
OUT_JSON = os.path.join(HERE, "podolski.json")
ME = "루카스 포돌스키"
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
FM_MAP = {r["tm_gameId"]: r["fotmob_matchId"] for r in rd("fotmob_tm_map.csv")}
FM_PM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 판정 표
# 출전 분 고침: 없음. 981897(2010.2.10 아우크스부르크 DFB-포칼 8강)은 60분 교체 투입 뒤 69분 두 번째 경고 퇴장 → API 9분이 맞음.
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'·상대 자책골은 아래 일반 규칙)
EXCL_A = {
    "2495324|89": "Transfermarkt 단독. FotMob은 체임버스 도움, 경기 기사(FA·SI 등)도 체임버스 크로스를 깁스가 발리로 넣었다고 적음",
    "2478762|88": "Transfermarkt 단독(코너킥). 인테르 구단 경기 기록·경기 기사: 포돌스키 코너킥이 굴절된 공을 비디치가 넣음 → 굴절이라 도움 아님",
    "2478848|48": "Transfermarkt 단독. FotMob은 이카르디 도움, 경기 기사(Sports Mole·ESPN 등)도 이카르디 크로스",
    "2994643|34": "Transfermarkt 단독. 확인 출처 1곳(Goal 일본판 '포돌스키의 롱패스')뿐 → 다른 출처 2곳 미확인",
    "4158825|77": "Transfermarkt 단독. FotMob 경기 이벤트에 이 골 자체가 없고 경기 기사로도 득점자·도움 확인 못 함",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 넣은 도움: gameId|분 -> 근거
ADD_CONFIRMED = {
    "2515982|71": "인테르 구단 경기 기록 '포돌스키 힐패스' · Sports Mole 'latching on to Podolski's back-heeled pass'",
    "2927487|90+4": "FotMob 선수 경기 목록 이 경기 도움 1(이 경기 Transfermarkt 도움도 하베나르 골 1개뿐) — Transfermarkt·FotMob 일치",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "L2", "GB1", "IT1", "TR1", "JAP1", "PL1"}
CUP = {"DFB", "FAC", "CGB", "CIT", "TRP", "JEMP", "POPU"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round"): return "dk"
        return "dc"   # 1~5라운드·16강·튀르키예컵 조별
    if cid == "LPO":   # DFB-리가포칼 2006: 준결승 dsf, 결승 df
        if r.startswith("semi"): return "dsf"
        if r.startswith("final"): return "df"
    if cid in ("TRS", "GBCS"): return "df"   # 튀르키예 슈퍼컵·커뮤니티 실드
    if cid == "JAPC":   # J리그컵: 조별 lcg, 토너먼트 lck(이니에스타 선례)
        return "lcg" if r.startswith("group") else "lck"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA" and r.startswith("first round"): return "elq"   # UEFA컵 1라운드 = 유로파 예선
    if cid in ("EL", "UEFA"):
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # UEFA컵 3라운드(32강)·16강·8강, 유로파 intermediate stage
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스·UEFA컵·J리그컵 조별, 튀르키예컵 2016-17 조별(리그식)
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
    if cid in ("CL", "CLQ", "EL", "UEFA"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "TRP":   # 튀르키예컵 두 경기: 2020-21까지 원정 다득점·연장
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "JAPC":
        ag, et = 1, 0
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
MANUAL_ALIAS = {"inter milan": "inter", "1 fc koln": "1 fc koeln"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if ME in r["선수"].split("·") and r["선수"] == ME: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

with open(os.path.join(ELO, "ents.json"), encoding="utf-8") as f:
    ENTS = [x for x in json.load(f) if x["p"] != ME]

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

def season_of_game(g):
    """상대 순위를 볼 시즌: 일본 리그 상대는 연도(2020.1.1 일왕배 결승은 2019), 나머지 유럽식"""
    d = g["date_local"]
    if g["club_id"] == "3958":
        return "2019" if d == "2020-01-01" else d[:4]
    return season_eu(d)

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))

# 리그 모형 공통 곡선(유럽 5대 리그 20칸, 기존 선수 자료와 같음)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

# 기존 선수 자료의 순위값(확인값, '추정' 없는 lv): 라벨 접두어 -> {시즌: {순위: Elo}}
def existing(label):
    out = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    pat = re.compile("^" + re.escape(label) + r" (\d{4}(?:-\d\d)?) (\d+)위$")
    for x in ENTS:
        m = pat.match(x["lv"] or "")
        if m: out[m.group(1)][int(m.group(2))][x["elo"]] += 1
    return {s: {r: c.most_common(1)[0][0] for r, c in v.items()} for s, v in out.items()}
EX_BL = existing("분데스리가")
EX_BL2 = existing("2. 분데스리가")
EX_TR = existing("쉬페르리그")
EX_J1 = existing("J1리그")
EX_PL = existing("프리미어리그")

def fill(tab, r):
    """같은 시즌(또는 시즌 무관 고정값)에 이웃 순위 값이 있으면 그 사이 직선(한 칸이면 가운데)"""
    if r in tab: return tab[r], ""
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if lo and hi:
        a, b = max(lo), min(hi)
        return round(tab[a] + (tab[b] - tab[a]) * (r - a) / (b - a)), f" (다른 선수 자료 {a}위 {tab[a]}·{b}위 {tab[b]} 사이)"
    return None, ""

# 2. 분데스리가·J1: 시즌 무관 고정값(기존 자료 모든 시즌을 합쳐 순위별 최빈값)
def pooled(ex):
    c = collections.defaultdict(collections.Counter)
    for s, t in ex.items():
        for r, e in t.items(): c[r][e] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
L2_FIX = pooled(EX_BL2)
GB2_FIX = pooled(existing("챔피언십"))
J1_FIX = pooled({s: t for s, t in EX_J1.items() if s not in ("2021", "2024", "2025")})   # 18팀 시즌만(2021·2024·2025는 20팀)
# 분데스리가: 2025-26 기준값 + 시즌 폭(그 시즌 기존 값들과의 차이 중앙값; 외질·클로제 자료와 같은 방식)
BL_BASE = [2006, 1912, 1860, 1828, 1812, 1797, 1777, 1756, 1737, 1723, 1713, 1702, 1697, 1682, 1661, 1644, 1634, 1613]
def bl_shift(season):
    t = EX_BL.get(season, {})
    ds = sorted(e - BL_BASE[r - 1] for r, e in t.items() if r <= 18)
    return ds[len(ds) // 2] if ds else None
# 튀르키예 1부: 평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 흩어짐 119(팔카오·발부에나 자료와 같은 계수)
TR_COEF = {2014: 6.0, 2017: 6.8, 2018: 5.5, 2019: 5.0, 2020: 3.1, 2021: 6.7}
def tr_mean_season(season):
    """기존 자료가 있는 시즌은 그 1위 값에서 거꾸로 구한 평균(2015-16 1773·2016-17 1779 재현), 없으면 계수 공식"""
    s = int(season[:4])
    if season in EX_TR and 1 in EX_TR[season]:
        return EX_TR[season][1] - 119 * curve(1, 18)
    c = sum(TR_COEF[y] for y in (s - 1, s, s + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)
# 폴란드 엑스트라클라사 2021-22~2025-26: 레반도프스키 자료와 같은 회귀(평균 = 1473 + 23.33 × (앞뒤 3시즌 폴란드 UEFA 계수 평균 − 7.333), 흩어짐 63).
# 계수(시즌 시작 연도): 2020 4.000, 2021 4.625, 2022 7.750, 2023 6.875, 2024 11.750, 2025 15.750
# (영어 위키백과 'Polish football clubs in European competitions'·football-coefficient.eu). 2025-26은 다음 시즌 계수가 끝나지 않아 최근 3시즌(2023~2025) 평균.
PL_COEF = {2020: 4.000, 2021: 4.625, 2022: 7.750, 2023: 6.875, 2024: 11.750, 2025: 15.750}
def pl_mean(season):
    s = int(season[:4])
    ys = (s - 1, s, s + 1) if s + 1 in PL_COEF else (s - 2, s - 1, s)
    c = sum(PL_COEF[y] for y in ys) / 3
    return 1473 + 23.33 * (c - 7.3333)
SD_PL = 63
SD2 = 51.24

def model(lg, season, r, n):
    if lg == "L1":
        t = EX_BL.get(season, {})
        if r in t: return t[r], f"분데스리가 {season} {r}위"
        sh = bl_shift(season)
        if sh is not None: return BL_BASE[r - 1] + sh, f"분데스리가 {season} {r}위"
    if lg == "L2":
        e, why = fill(L2_FIX, r)
        if e: return e, f"2. 분데스리가 {season} {r}위" + ((" (추정, " + why[2:]) if why else "")
    if lg == "JAP1":
        e, why = fill(J1_FIX, r)
        if e: return e, f"J1리그 {season} {r}위" + ((" (추정, " + why[2:]) if why else "")
    if lg == "TR1":
        t = EX_TR.get(season, {})
        if r in t: return t[r], f"쉬페르리그 {season} {r}위"
        return round(tr_mean_season(season) + 119 * curve(r, n)), f"쉬페르리그 {season} {r}위"
    if lg == "TR2":   # 쉬페르리그 평균 − 162, 흩어짐 SD2(판페르시 자료 선례)
        return round(tr_mean_season(season) - 162 + SD2 * curve(r, n)), f"튀르키예 2부 {season} {r}위 (추정, 쉬페르리그 평균 − 독일 1·2부 평균 차)"
    if lg == "PL1":
        return round(pl_mean(season) + SD_PL * curve(r, n)), f"엑스트라클라사 {season} {r}위 (리그 수준 추정)"
    if lg == "GB2":
        e, why = fill(GB2_FIX, r)
        if e: return e, f"챔피언십 {season} {r}위" + ((" (추정, " + why[2:]) if why else "")
    if lg == "GB1":
        t = EX_PL.get(season, {})
        if r in t: return t[r], f"프리미어리그 {season} {r}위"
    return None
RANK_LG = ["L1", "L2", "GB1", "GB2", "TR1", "TR2", "JAP1", "PL1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정')
MAN = {
    (key("FC St. Pauli"), "2006-07"): (1450, "독일 3부(레기오날리가 북부) 2006-07 1위 (추정, 다른 선수 자료 독일 3부 1450과 같음)"),
    (key("Olympiacos Piraeus"), "2012-13"): (1630, "그리스 2012-13 1위 (추정, 다른 선수 자료 올림피아코스 2011-12 1620·2013-14 1640의 가운데)"),
    (key("SC Wiedenbrück"), "2011-12"): (1300, "독일 4부(레기오날리가 서부) 2011-12 (추정, 다른 선수 자료 독일 4부 1300과 같음)"),
    (key("Kickers Emden"), "2009-10"): (1180, "독일 5부(오버리가 니더작센 서부) 2009-10 5위 (추정, 다른 선수 자료 독일 5부 1180과 같음)"),
    (key("Dersim Spor"), "2016-17"): (1000, "튀르키예 아마추어 리그 2016-17 (추정, 다른 선수 자료 튀르키예 4부 990보다 조금 위)"),
    (key("GKS Katowice"), "2022-23"): (1290, "폴란드 2부 2022-23 10위 (추정, 엑스트라클라사 평균 − 독일 1·2부 평균 차)"),
    (key("Spartak Moscow"), "2006-07"): (1600, "러시아 2006 2위 (추정, 다른 선수 자료 스파르타크 모스크바 2006 1600과 같음)"),
}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid, season):
    k = key(opp)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [season]
    if cid in ("CL", "CLQ", "EL", "UEFA"): seasons += [season[:4], str(int(season[:4]) + 1)]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, season) in MAN:
        e, lv = MAN[(k, season)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, season))
        if t and k in t:
            r, n = t[k]
            res = model(lg, season, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                return res
    return None

# ---------------------------------------------------------------- 출전
M = []
for g in GAMES:
    M.append([g["date_local"], g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["podolski_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, g, et):
    d = g["date_local"]; opp = g["opponent"].strip()
    res = opp_elo(opp, d, g["competitionId"], season_of_game(g))
    if res is None:
        missing_elo.add((opp, season_of_game(g), g["competitionId"])); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["podolski_scorer"] == "1", e["podolski_assist_other"] == "1"
    if e["podolski_self_assist"] == "1":
        judg.append(("본인 골의 본인 도움 제외", g["date_local"], tag)); EXCL_CNT["본인 도움"] += 1
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
    et = int(mi > 90 and not dm)   # 연장 시간 골(분 > 90, 추가시간 표기 아님)
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", g["date_local"], e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and "rebound" not in e["goal_desc"].lower()), 0, tie, comp, ko, g, et)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = "개별 판정"
        if why:
            EXCL_CNT[why] += 1
            EXCL_LIST.append((g["date_local"], g["opponent"], e["minute"], e["scorer"], why, EXCL_A.get(tag, "")))
            continue
        if g["date_local"] >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - mi) <= 2]
            if not hit:
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag + " " + e["scorer"])
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, g, et)

# 2014.8 이후 FotMob에만 있는 도움(넣지 않음): 경기 이벤트 + 선수 경기 목록(2017.1.31부터)
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local"] >= GAP and len(ts) > used_fm.get(gid, 0):
        FM_ONLY.append(("이벤트", gid, G[gid]["date_local"], ts))
a_by_date = collections.Counter(r[9] for r in rows if r[0] == "a")
for gid, g in G.items():
    pm = FM_PM.get(FM_MAP.get(gid, ""))
    if pm and int(pm["assists"] or 0) > a_by_date.get(g["date_local"], 0):
        FM_ONLY.append(("선수 경기 목록", gid, g["date_local"], g["opponent"], pm["assists"], a_by_date.get(g["date_local"], 0)))

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, EXCL_CNT)
    for x in FM_ONLY: print("FotMob만:", x)
    for x in EXCL_LIST: print("도움 제외:", x)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11부터)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["podolski_scorer"] == "1" and e["gameId"] in G and G[e["gameId"]]["date_local"] >= "2010-08-01":
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["podolski_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1" and "rebound" not in t["goal_desc"].lower()
        fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료·상대 자료 대조(다른 파일은 고치지 않음)
def tracked_data():
    try:
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split()
    except Exception:
        out = []
    return [os.path.basename(p) for p in out if p.endswith(".js") and not p.endswith(("hon.js", "pod.js"))]
def load_js(fn):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const ([A-Z0-9]+)_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(2)) if m else []
DATES = {m[0] for m in M}
OTHERS = {}
if "--cross" in sys.argv:
    for fn in tracked_data():
        rs = [x for x in load_js(fn) if x[9] in DATES]
        if rs: OTHERS[fn] = rs
CROSS = []
def cmp_rows(a, b, full=True):
    diffs = []
    if full and abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if full and (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if full and a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or (ta and tb and ta[2:] != tb[2:]) or (bool(ta) != bool(tb)):
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
PODO = lambda s: "podolski" in norm(str(s or ""))
for fn, ent in OTHERS.items():
    for r in E:
        if r[0] == "a":
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1])], key=lambda x: abs(x[4] - r[4]))
            if hit: CROSS.append((fn, "포돌스키 도움→골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:
        if x[0] == "a" and PODO(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn, "도움→포돌스키 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    seen = set()
    for x in ent:
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]) and (fn, x[9]) not in seen:
                seen.add((fn, x[9]))
                d = cmp_rows(r, x, full=False)
                if d: CROSS.append((fn, "같은 경기 다름", r[9], r[1], d))
                break
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[1], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("kolpd", "2006-07-01", "1. FC 쾰른", "2003~2006"), ("baypd", "2009-07-01", "바이에른 뮌헨", "2006~2009"),
         ("kolpd", "2012-07-01", "1. FC 쾰른", "2009~2012"), ("arspd", "2015-01-05", "아스널", "2012~2015"),
         ("intpd", "2015-07-01", "인테르", "2015"), ("galpd", "2017-07-01", "갈라타사라이", "2015~2017"),
         ("kobpd", "2020-01-23", "비셀 고베", "2017~2020"), ("antpd", "2021-07-01", "안탈리아스포르", "2020~2021"),
         ("gorpd", None, "고르니크 자브제", "2021~2026")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {}
for k, u, n, y in CLUBS: CLUB_KO.setdefault(k, n)
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TMC = {"3": "kolpd", "27": "baypd", "11": "arspd", "46": "intpd", "141": "galpd", "3958": "kobpd", "589": "antpd", "428": "gorpd"}
for g in GAMES:
    if club_of(g["date_local"]) != TMC[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
# 쾰른 두 시기를 나눠서도 집계(설명용)
ST2 = collections.OrderedDict()
for k, u, n, y in CLUBS: ST2[(k, y)] = [0, 0, 0]
def club_period(d):
    for k, u, n, y in CLUBS:
        if u is None or d < u: return (k, y)
for m in M: ST2[club_period(m[0])][0] += 1
for r in E: ST2[club_period(r[9])][1 if r[0] == "g" else 2] += 1

if __name__ == "__main__" and "--clubs" in sys.argv:
    for k, v in ST2.items(): print(k, v)
    for k, v in ST.items(): print(k, v)

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["podolski_assist_other"] == "1")
PERIOD_KO = {("kolpd", "2003~2006"): "1. FC 쾰른(2003~2006)", ("baypd", "2006~2009"): "바이에른 뮌헨(2006~2009)",
             ("kolpd", "2009~2012"): "1. FC 쾰른(2009~2012)", ("arspd", "2012~2015"): "아스널(2012~2015)",
             ("intpd", "2015"): "인테르(2015 임대)", ("galpd", "2015~2017"): "갈라타사라이(2015~2017)",
             ("kobpd", "2017~2020"): "비셀 고베(2017~2020)", ("antpd", "2020~2021"): "안탈리아스포르(2020~2021)",
             ("gorpd", "2021~2026"): "고르니크 자브제(2021~2026)"}
NOTE_LINES = [
    f"루카스 포돌스키(1. FC 쾰른·바이에른 뮌헨·아스널·인테르·갈라타사라이·비셀 고베·안탈리아스포르·고르니크 자브제)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 함부르크전 ~ {d_(M[-1][0])} 라도미아크 라돔전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·독일 대표팀·유소년(쾰른 U17·U19)·쾰른 2군·바이에른 2군 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{PERIOD_KO[k]} {c3(v)}" for k, v in ST2.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 나온 경기와 리그 밖 경기 전부), 2010-11부터는 FotMob 경기 이벤트와 대조함(FotMob에는 쾰른 2003~2006·바이에른·쾰른 2009-10 경기 자료가 없고, 쾰른 2010-11 6경기는 FotMob 경기 자료가 비어 있음). 출전 분이 없어 90분으로 추정한 경기는 없음",
    "경기 수·골은 영어 위키백과 클럽·시즌·대회별 기록과 모든 시즌에서 같음(위키백과 통산 708경기는 쾰른 2군 2경기·바이에른 2군 2경기 포함). Transfermarkt가 '다른 팀으로 출전'으로 표시한 바이에른 2007.8 분데스리가 2경기(그날 2군 경기 출전)는 넣지 않음",
    "2010.2.10 아우크스부르크전(DFB-포칼 8강)은 60분에 교체로 들어가 69분에 경고 두 번으로 퇴장해 9분 출전",
    f"골: Transfermarkt 경기 리포트 {NGo}골 그대로. 2010-11 이후 골은 FotMob과 수·분·PK 여부가 모두 같음(FotMob 자료가 빈 경기 제외). PK 골 {NPK}개(2010-11 이후 5개 중 FotMob 자료가 있는 4개는 FotMob도 PK). 자책골·연장 골 없음(2008.4.19 DFB-포칼 결승 103분 토니 골 도움은 연장 시간 기록)",
    f"도움: 2014년 8월 전은 Transfermarkt 리포트 도움(FotMob 도움 기록이 이 시기에 거의 비어 있음), 이후는 Transfermarkt와 FotMob이 함께 센 것 + 다른 출처 2곳이 확인한 것. 도움 {NA} = Transfermarkt 리포트 {N_TM_A} − 'Shot on goal'(슈팅 리바운드) {EXCL_CNT[chr(39)+'Shot on goal'+chr(39)+'(슈팅 리바운드)']} − PK 유도 {EXCL_CNT['PK 유도']}(2019.12.7 이와타전 비야, 2022.10.16 레흐 포즈난전 브워다르치크) − 상대 자책골에 준 도움 {EXCL_CNT['상대 자책골에 준 도움']}(2016.4.16 안탈리아스포르전) − 개별 판정 {EXCL_CNT['개별 판정']}",
    "개별 판정으로 뺀 도움 5개(모두 2014년 8월 뒤 Transfermarkt에만 있음): 2014.10.22 안데를레흐트전 89분 깁스 골(FotMob·경기 기사는 체임버스 크로스), 2015.1.11 제노아전 88분 비디치 골(포돌스키 코너킥이 굴절된 뒤 골), 2015.3.15 체세나전 48분 팔라시오 골(FotMob·경기 기사는 이카르디 크로스), 2018.4.25 가시마전 34분 미타 골(확인 출처 1곳뿐), 2023.9.27 GKS 카토비체전(폴란드컵) 77분 엔날리 골(득점자·도움 확인 못 함)",
    "FotMob 경기 이벤트에 없지만 넣은 도움 2개: 2015.1.21 삼프도리아전(코파 이탈리아 16강) 71분 샤키리 골(인테르 구단 경기 기록·Sports Mole 기사 모두 포돌스키 힐패스), 2017.10.25 가시마전(일왕배 8강) 90+4분 하베나르 골(FotMob 선수 경기 목록 도움 1과 같음)",
    "Transfermarkt 리포트가 포돌스키 본인 PK 골에 본인을 도움으로 적은 4개(2004.10.22 에센전, 2005.3.11 오버하우젠전, 2011.5.7 프랑크푸르트전, 2012.3.31 아우크스부르크전)는 셈하지 않음(Transfermarkt 선수 도움 합계에도 없음)",
    "FotMob 선수 경기 목록에는 2021.12.3 실롱스크 브로츠와프전 도움 1이 있으나 Transfermarkt·FotMob 경기 이벤트에 없어 넣지 않음. 2014년 8월 전 도움은 Transfermarkt 한 곳 기준이라 하나하나 다른 출처와 대조하지는 않음",
    f"도움 합계 비교: Transfermarkt {N_TM_A}·폴란드어 위키백과(2022-23까지) 클럽별 합계 쾰른 44·바이에른 20·아스널 17·인테르 4·갈라타사라이 18·고베 12·안탈리아스포르 5·FotMob 경력 합계 84(경기 이벤트 도움이 2010~14 거의 비어 있음)·이 계산기 {NA}",
    "날짜는 현지 날짜(Transfermarkt 리포트·일정 날짜, 일본 경기는 일본 날짜)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(리베리·클로제·피사로·뮐러·외질·스네이더르·이니에스타·비야 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 리그 모형에 넣은 값, 직접 추정 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "리그 모형: 2. 분데스리가·J1리그·챔피언십은 다른 선수 자료의 순위별 값(J1 5위는 4위·6위 값 사이), 쉬페르리그는 다른 선수 자료와 같은 튀르키예 회귀식(2016-17은 그 시즌 기존 값과 같은 수준, 2019-20·2020-21은 앞뒤 3시즌 UEFA 국가 계수 평균), 튀르키예 2부는 쉬페르리그 평균 − 162",
    "엑스트라클라사 2021-22~2025-26은 기존 폴란드 모형과 같은 회귀식(평균 = 1473 + 23.33 × (앞뒤 3시즌 폴란드 UEFA 국가 계수 평균 − 7.333), 흩어짐 63)으로 계산한 리그 수준 추정: 계수 2020-21 4.000·2021-22 4.625·2022-23 7.750·2023-24 6.875·2024-25 11.750·2025-26 15.750, 리그 평균 2021-22 약 1429·2022-23 약 1452·2023-24 약 1507·2024-25와 2025-26 약 1569(2025-26은 다음 시즌 계수가 아직 없어 최근 3시즌 평균). 순위는 Transfermarkt 최종 순위표",
    "직접 추정(모두 '추정'): 킥커스 엠덴 2009-10(독일 5부, 3. 리가에서 자진 강등) 1180, SC 비덴브뤼크 2011-12(독일 4부) 1300, 장크트파울리 2006-07(독일 3부 레기오날리가 북부 1위) 1450, 올림피아코스 2012-13 1630, 스파르타크 모스크바 2006-07 1600, 데르심 스포르 2016-17(튀르키예 아마추어) 1000, GKS 카토비체 2022-23(폴란드 2부 10위) 1290",
    "대회 비중: DFB-포칼·FA컵·리그컵·코파 이탈리아·튀르키예컵·일왕배·폴란드컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), DFB-리가포칼·튀르키예 슈퍼컵은 준결승·결승을 국내컵 준결승·결승으로, J리그컵은 리그스컵 비중(조별·토너먼트)으로 계산함. 튀르키예컵 2016-17 조별과 J리그컵 조별은 리그식(무승부 1점). UEFA컵 1라운드는 유로파 예선, UEFA컵 3라운드 이후·유로파 32강은 유로파 토너먼트로 계산함",
    f"두 경기 합산(챔스·UEFA컵·유로파 토너먼트와 예선, 튀르키예컵 8강·준결승) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회·튀르키예컵 모두 2020-21까지(연장 있음). 포돌스키가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 쾰른·바이에른·고르니크 자브제는 7월 10일 기준(2011.7.31 DFB-포칼 비덴브뤼크전 = 2011-12, 고르니크 7월 개막전 = 새 시즌), 비셀 고베는 연도 기준(2020.1.1 일왕배 결승은 2020 시즌으로 잡힘, 이니에스타 자료와 같음), 아스널·인테르·갈라타사라이·안탈리아스포르는 8월 1일 기준. 클럽 구분은 2006.7.1 전 쾰른, 2009.7.1 전 바이에른, 2012.7.1 전 쾰른, 2015.1.5 전 아스널, 2015.7.1 전 인테르, 2017.7.1 전 갈라타사라이, 2020.1.23 전 비셀 고베, 2021.7.1 전 안탈리아스포르, 이후 고르니크 자브제",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 분데스리가 2007-08, DFB-포칼 2007-08, FA컵 2014, 커뮤니티 실드 2014, 튀르키예컵 2015-16, 튀르키예 슈퍼컵 2015·2016, 일왕배 2019, 폴란드컵 2025-26, 2. 분데스리가 우승 2004-05(준우승 칸에 2부 우승으로 표시), 2. 분데스리가 득점왕 2004-05(24골). 월드컵 우승 등 대표팀 기록과 리그 준우승(분데스리가 2008-09)은 뺌",
    "은퇴(2026.5.22 발표). 마지막 경기 2026.5.23 라도미아크 라돔전",
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
# 골·도움 분이 그 경기 출전 구간 안인지(선발/교체 정보가 없어 출전 분 이하인지만 점검: 선발이면 분 ≤ 출전 분+추가시간)
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const POD_E={J(E)};\nconst POD_M={J(M)};\nconst POD_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "excluded_assists": EXCL_LIST,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST2.items(): print(" ", k, v)
