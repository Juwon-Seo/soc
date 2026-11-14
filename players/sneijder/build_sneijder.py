#!/usr/bin/env python3
"""Wesley Sneijder: raw/ -> sneijder.json + src/data/sne.js (판정 근거는 judgments.md)

  python3 players/sneijder/build_sneijder.py            # 파일 쓰기
  python3 players/sneijder/build_sneijder.py --debug    # Elo 출처 로그
  python3 players/sneijder/build_sneijder.py --cross    # 동료 자료 대조
  python3 players/sneijder/build_sneijder.py --fm       # FotMob 골 대조

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
OUT_JS = os.path.join(ROOT, "src", "data", "sne.js")
OUT_JSON = os.path.join(HERE, "sneijder.json")
ME = "베슬리 스네이더르"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트, 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# 성인 클럽 경기만: TM이 'Ajax Amsterdam U21'(club 8817)로 적은 2경기는 Jong Ajax 경기(judgments.md 1절)라 뺀다
ALL_GAMES = rd("tm_games.csv")
GAMES = [g for g in ALL_GAMES if g["level"] != "u21_label"]
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
OTHER = {g: r["other_leg_id"] for g, r in TIES_RAW.items()}
for gid, r in INFO.items():   # 두 경기 짝: 리포트의 'other leg' 링크(한쪽에만 적힌 경우 반대쪽도 채움)
    if r["other_leg_id"]:
        OTHER.setdefault(gid, r["other_leg_id"]); OTHER.setdefault(r["other_leg_id"], gid)
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'·상대 자책골은 아래에서 일반 규칙으로 뺌)
EXCL_A = {}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2988893|22": "2018.3.1 알라이얀전 22분 하템 골: QSL 공식 경기 기사 'provided the assists for the goals by Abdelaziz Hatem (22nd), Diego Amado (54th) and Mehdi Taremi (62nd)' · Voetbal International 'Enorm aandeel Sneijder in stunt Al Gharafa'(하템 2-0 도움)",
    "2988893|54": "같은 경기 54분 아마두 골: QSL 공식 경기 기사 · Voetbal International(후반 두 골 모두 도움)",
    "2988893|62": "같은 경기 62분 타레미 골: QSL 공식 경기 기사 · Voetbal International(후반 두 골 모두 도움)",
    "2995676|44": "2018.4.3 알자지라전(AFC 챔스) 44분 아마두 골: QSL 경기 기사 'Amado controlled Sneijder's in-swinging corner' · Gulf News 'Gharafa took the lead through … Sneijder's corner'",
}
# 넣지 않은 TM 단독 도움(다른 출처 2곳을 못 찾음): gameId|분
UNCONFIRMED_A = {
    "2988898|45": "2018.3.9 알사일리야전 45분 타레미 골 (QSL 공식 경기 기사 1곳만)",
    "3126032|53": "2018.10.26 알코르전 53분 바이스 골 (QSL·페닌슐라 기사에 도움 언급 없음)",
}
# 골 뒤 스코어 고침: TM 골 순서 대신 FotMob·월드풋볼·ESPN 순서를 쓴 경우 gameId|분 -> (gf, ga, 이유)
SCORE_FIX = {
    "2995672|71": (1, 3, "2018.2.12 알자지라전: TM은 스네이더르 71분 골(2-2) 뒤 알아타스 89분 골(3-2) 순서, FotMob·월드풋볼·ESPN은 알아타스 69분 골(3-1) 뒤 스네이더르 71분 골(3-2)이 마지막 골 → 골 전 1-3"),
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"NL1", "ES1", "IT1", "TR1", "FR1", "QSL", "PONL"}
CUP = {"NLP", "CDR", "CIT", "TRP", "QEC1", "QSCP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"          # PONL(네덜란드 유럽 대항전 플레이오프)도 lg + 합산 (수아레스·메르턴스 선례)
    if cid in CUP:
        if cid == "QSCP": return "dc"      # 카타르 QSL컵 조별 (에투 선례)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                        # 16강까지(코파 델 레이 4라운드·16강, 코파 이탈리아 16강, KNVB 2라운드·16강, 튀르키예컵 조별·16강)
    if cid in ("NLSC", "SUC", "SCI", "USC", "TRS"): return "df"   # 슈퍼컵류 = 국내컵 결승
    if cid == "KLUB": return "cwc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 2002-03 2차 조별('Group 2') 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid == "UEFA" and r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
    if cid in ("EL", "UEFA"):
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # intermediate stage(32강)·16강·8강
    if cid in ("AFCL", "ACLQ"): return "acl"   # AFC 챔스 조별·예선 플레이오프(단판)
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
    if cid in ("CL", "CLQ", "EL", "ELQ", "UEFA"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid in ("CDR", "SUC"):   # 스페인 국내 대회: 원정 다득점(2018-19까지)·연장
        ag, et = int(d < "2019-07-01"), 1
    elif cid == "PONL":           # 네덜란드 유럽 플레이오프: 원정 다득점·연장 (수아레스·메르턴스 선례)
        ag, et = 1, 1
    elif cid == "TRP":            # 튀르키예컵: 원정 다득점 없음·연장 있음 (판페르시·에투 선례)
        ag, et = 0, 1
    elif cid == "CIT":            # 코파 이탈리아 준결승: 2021-22까지 원정 다득점, 연장
        ag, et = int(d < "2022-07-01"), 1
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
MANUAL_ALIAS = {"inter milan": "inter", "ac milan": "milan", "fenerbahce": "fenerbahce sk", "ss lazio": "lazio"}
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

def ldate(g):
    return g["date_local"]

# ---------------------------------------------------------------- 출전
M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

if __name__ == "__main__" and "--list" in sys.argv:
    seen = set()
    for e in EVENTS:
        g = G.get(e["gameId"])
        if g and (e["sneijder_scorer"] == "1" or e["sneijder_assist_other"] == "1"):
            k = (g["opponent"], season_eu(ldate(g)), g["competitionId"], g["club_id"])
            if k not in seen:
                seen.add(k); print(*k)

# ---------------------------------------------------------------- 리그 모형 (아래 상수는 judgments.md 6절)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

# 에레디비시 순위별 값: 기존 선수 자료의 시즌 무관 18칸 값 (1위 1837 … 18위 1406, 시즌별 값이 있는 순위는 모두 같음)
MAP18 = [1837, 1735, 1677, 1642, 1624, 1608, 1587, 1563, 1542, 1528, 1516, 1504, 1499, 1482, 1459, 1441, 1430, 1406]
# 에이르스터 디비시(네덜란드 2부) 20팀: 기존 값 중 17위 1282 (포르투나 시타르트 2007-08)
NL2_FIX = {17: 1282}
# 쉬페르리그 2013-14: 기존 선수 자료의 순위별 값(없는 순위는 이웃 순위 값 사이 직선 보간 — 브리프의 '이웃 기존 값' 규칙)
TR_1314 = {1: 1778, 3: 1606, 6: 1533, 8: 1485, 9: 1462, 10: 1446, 11: 1434, 16: 1354, 17: 1342, 18: 1317}
def interp(tab, r):
    if r in tab: return tab[r]
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return round(tab[lo] + (tab[hi] - tab[lo]) * (r - lo) / (hi - lo))
# 쉬페르리그 2014-15: 기존 값은 1위 1750뿐(임모빌레 자료) → 평균 1450.2(= 1750 − 119 × 곡선 1위) + 119 × 곡선
TR_MEAN = {"2014-15": 1750 - 119 * CV[0], "2016-17": 1479}
SD2 = 51.24   # 튀르키예 2·3부 흩어짐(문서 4절)
# 카타르 12팀: 마레즈·에투 자료와 같은 리그 수준(평균 1460, 흩어짐 45)

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 lv에 '추정')
MAN = {
    (key("FC Thun"), "2005-06"): (1461, "스위스 2005-06 5위 (추정, 다른 선수 자료 스위스 슈퍼리그 2012-13 5위 값과 같음)"),
    (key("Bröndby IF"), "2005-06"): (1520, "덴마크 2005-06 2위 (추정, 다른 선수 자료 브뢴뷔 2003-04 값과 같음)"),
    (key("CSKA Moscow"), "2009-10"): (1604, "러시아 2009 2위 (추정, 다른 선수 자료 러시아 프리미어리그 2011-12 2위 값과 같음)"),
    (key("FC Astana"), "2015-16"): (1400, "카자흐스탄 2015 1위 (추정, 다른 선수 자료 카자흐스탄 1위 1400과 같음)"),
    (key("FC Vaslui"), "2012-13"): (1480, "루마니아 2012-13 5위 (추정, 같은 시즌 다른 선수 자료 1위 1520과 8위 1440의 중간)"),
    (key("HNK Hajduk Split"), "2012-13"): (1430, "크로아티아 2012-13 4위 (추정, 다른 선수 자료 하이두크 2017-18 3위 1430과 같음)"),
    (key("Austria Vienna"), "2006-07"): (1385, "오스트리아 2006-07 6위 (추정, 다른 선수 자료 오스트리아 분데스리가 2012-13·2013-14 6위 1396·1373의 평균)"),
    (key("IK Start"), "2006-07"): (1350, "노르웨이 2006 13위/14팀 (추정, 다른 선수 자료 노르웨이 4위 1392보다 낮게)"),
    (key("Pakhtakor Tashkent"), "2017-18"): (1380, "우즈베키스탄 2017 1위 (추정, 다른 선수 자료 파크타코르 2026-27 값과 같음)"),
}
RANK_LG = ["NL1", "NL2", "TR1", "TR4A", "TR4C", "QSL"]
def model(lg, season, r, n):
    if lg == "NL1":
        return MAP18[r - 1], f"에레디비시 {season} {r}위"
    if lg == "NL2" and r in NL2_FIX:
        return NL2_FIX[r], f"에이르스터 디비시(네덜란드 2부) {season} {r}위"
    if lg == "TR1" and season == "2013-14":
        return interp(TR_1314, r), f"쉬페르리그 {season} {r}위"
    if lg == "TR1" and season == "2014-15":
        return round(TR_MEAN[season] + 119 * curve(r, n)), f"쉬페르리그 {season} {r}위 (추정, 2014-15 1위 1750에 맞춘 리그 수준·흩어짐 119)"
    if lg in ("TR4A", "TR4C"):
        return round(TR_MEAN[season] - 486 + SD2 * curve(r, n)), f"튀르키예 4부 {season} {r}위/{n}팀 (추정, 근거 약함: 쉬페르리그 평균에서 3단계 아래)"
    if lg == "QSL":
        return round(1460 + 45 * curve(r, n)), f"카타르 {season} {r}위 (추정, 마레즈 자료와 같은 리그 수준)"
    return None

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
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "ECLQ", "UCOL") else [eu]
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

# ---------------------------------------------------------------- 골·도움
FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["sneijder_assist"] == "1":
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
    isg, isa = e["sneijder_scorer"] == "1", e["sneijder_assist_other"] == "1"
    if e["sneijder_self_assist"] == "1":
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
    if tag in SCORE_FIX:
        gf, ga = SCORE_FIX[tag][:2]; judg.append(("골 뒤 스코어 고침", tag, SCORE_FIX[tag][2]))
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
        if tag in UNCONFIRMED_A:
            EXCL_CNT["다른 출처 2곳 미확인(2014.8 이후 TM 단독)"] += 1
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], UNCONFIRMED_A[tag])); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - mi) <= 2]
            if not hit:
                judg.append(("2014.8 이후 FotMob에 없는 도움", tag, e["scorer"], d, opp))
                EXCL_CNT["TM 단독(2014.8 이후) 미확정"] += 1
                print("미확정 TM 단독 도움:", tag, d, opp, e["scorer"], e["assist_type"], file=sys.stderr)
                continue
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

if __name__ == "__main__" and "--missing" in sys.argv:
    for x in sorted(missing_elo, key=lambda x: (x[2], x[1], x[0])): print("Elo 없음:", x)
    print(len(missing_elo), "빠짐 /", len(rows), "기록", dict(ELO_SRC), dict(EXCL_CNT))

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    seen = set()
    for x in ELO_LOG:
        if x[4].startswith("same"): continue
        k = (x[1], x[2], x[3])
        if k in seen: continue
        seen.add(k); print(x[:5])

# ---------------------------------------------------------------- FotMob 골 대조 (2010-11 이후)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["sneijder_scorer"] == "1" and e["gameId"] in G and G[e["gameId"]]["date_local"] >= "2010-08-01":
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["sneijder_scorer"] == "1" and r["pen_shootout_event"] != "True"]
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
# 이름(기록의 도움 득점자 표기에 쓰는 TM 철자) -> (파일, 접두어, 같은 클럽 기간 시작, 끝)
MATES = {"Didier Drogba": ("dro.js", "DRO", "2013-01-22", "2014-06-01"),
         "Samuel Eto'o": ("eto.js", "ETO", "2009-08-29", "2011-08-24"),
         "Gonzalo Higuaín": ("hig.js", "HIG", "2007-08-12", "2009-08-29"),
         "Zlatan Ibrahimović": ("ibr.js", "IBR", "2002-07-01", "2004-07-01"),
         "Ruud van Nistelrooy": ("nis.js", "NIS", "2007-08-12", "2009-08-29"),
         "Raúl": ("rau.js", "RAU", "2007-08-12", "2009-08-29"),
         "Arjen Robben": ("rob.js", "ROB", "2007-08-12", "2009-08-29")}
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
SN = lambda s: norm(s or "") in ("wesley sneijder", "sneijder")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append((ME + " 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and SN(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→" + ME + " 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    # Transfermarkt 스네이더르 도움이지만 이 계산기에서 뺀 동료 골(참고)
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["sneijder_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    # TM 리포트에서 동료가 스네이더르 골의 도움인데 동료 파일에 없는 것(참고)
    for e in EVENTS:
        if e["sneijder_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 스네이더르 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0].split("→")[0] if "→" in c[0] else c[0], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("ajxsn", "2007-08-12", "아약스", "2002~2007"), ("rmasn", "2009-08-29", "레알 마드리드", "2007~2009"),
         ("intsn", "2013-01-22", "인테르", "2009~2013"), ("galsn", "2017-08-07", "갈라타사라이", "2013~2017"),
         ("nicsn", "2018-01-05", "니스", "2017~2018"), ("gfasn", None, "알가라파", "2018~2019")]
TM_CLUB = {"610": "ajxsn", "418": "rmasn", "46": "intsn", "141": "galsn", "417": "nicsn", "6297": "gfasn"}
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["sneijder_assist_other"] == "1")
assert (N_TM_A, NA) == (146, 138), (N_TM_A, NA)
FIRST, LAST = M[0], M[-1]
NOTE_LINES = [
    f"베슬리 스네이더르(아약스·레알 마드리드·인테르·갈라타사라이·니스·알가라파)의 클럽 공식 경기 {NG}경기({d_(FIRST[0])} 빌럼 2세전 ~ {d_(LAST[0])} 알아흘리전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·네덜란드 대표팀·유소년과 아약스 2군(Jong Ajax) 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기 전부), 2010-11 이후 골은 FotMob 경기 이벤트와 대조함(FotMob에는 아약스·레알 마드리드·인테르 2009-10 경기 자료가 없고, 인테르 2010-11의 6경기는 자료가 비어 있으며, 카타르 리그 경기에는 골 이벤트가 없음). FotMob 자료가 없는 2010-11 이전 경기는 Transfermarkt 리포트가 유일한 경기별 출처라 위키백과(영어·네덜란드어·튀르키예어)의 시즌별 경기·골·도움 합계로 총량만 확인함",
    "빼 놓은 유소년 경기: Transfermarkt가 'Ajax Amsterdam U21'로 적은 2경기 — 2002.2.7 KNVB컵 8강 텔스타전(45분)과 2002.8.20 KNVB컵 조별 홀란디아 호른전(90분, 6-0). 영어 위키백과 2001-02 KNVB컵 문서(검색 결과 요약)는 텔스타 3-0을 Young Ajax(2군) 경기로, RSSSF 2002-03 컵 결과는 홀란디아전을 'Ajax 2'로 적고, 영어·네덜란드어 위키백과 본문은 공식 아약스 데뷔를 2003.2.2 빌럼 2세전으로 적으며 영어 위키백과 클럽·시즌 표는 아약스 2002-03 컵을 3경기(16강·8강·준결승)만 세므로 1군 경기에서 제외. 두 경기 모두 골·도움 없음",
    f"클럽별 경기 수는 영어 위키백과와 같음(통산 575경기; 시즌별로는 알가라파 2017-18에 아미르컵 8강 1경기가 Transfermarkt·네덜란드어 위키백과에만 있어 1경기 더 많음). 골은 영어 위키백과(156골)보다 2개 적음 — 갈라타사라이 2015-16 튀르키예컵 1골(Transfermarkt·튀르키예어 위키백과에는 없음, 경기 기록에서 찾지 못함)과 알가라파 2018-19 QSL컵 두 번째 경기 1골(영어 위키백과 QSL컵 2경기 2골, Transfermarkt 1경기 1골; 경기 기사로 찾지 못함). 네덜란드어 위키백과는 아약스 2001-02 컵 1경기(위 텔스타전)를 더 세고, 알가라파 2018-19 컵 경기를 세지 않음",
    "골: 7개가 PK(Transfermarkt 'Penalty' 기준, 모두 알가라파: " + ", ".join(d_(r[9]) + " " + {"Pakhtakor Tashkent": "파크타코르", "Al-Markhiya SC": "알마르키야", "Al-Rayyan SC": "알라이얀", "Al-Sailiya SC": "알사일리야", "Al-Ahli SC": "알아흘리", "Umm Salal SC": "움 살랄", "Qatar SC": "카타르 SC"}[r[1]] + "전" for r in E if r[8]) + "). 카타르 리그는 FotMob에 골 이벤트가 없어 Transfermarkt 리포트와 시즌 합계로만 확인함(영어 위키백과 카타르 리그 15골과 같음). 분 차이: 2013.8.19 가지안테프스포르전 골 Transfermarkt 10분·FotMob 8분은 Transfermarkt를 씀",
    "골 순서를 고친 1개: 2018.2.12 알자지라전(AFC 챔스) 71분 골. Transfermarkt는 스네이더르 71분 골(2-2) 뒤 알아타스 89분 골(3-2)로 적었으나 FotMob과 경기 중계 기록(월드풋볼·ESPN, 검색 결과 요약)이 알아타스 69분 골(3-1) 뒤 스네이더르 71분 골(3-2, 경기 마지막 골)로 적어 골 전 스코어를 1-3으로 둠",
    f"도움 {NA} = Transfermarkt 리포트 {N_TM_A} − PK 유도 2(2014.1.19 안탈리아스포르전 튀르키예컵 44분 이난, 2016.1.16 시바스스포르전 86분 부라크 일마즈) − 슈팅 리바운드('Shot on goal') 3(2003.3.8 즈볼레전 15분 판더파르트, 2009.3.22 알메리아전 23분 마르셀루, 2015.10.3 바샥셰히르전 84분 불루트; 이 중 바샥셰히르전은 FotMob도 도움으로 세지만 리바운드 제외 기준으로 뺌) − 상대 자책골에 준 도움 1(2007.12.1 라싱 산탄데르전 9분 세르히오 산체스 자책골) − 2014.8 이후 Transfermarkt 한 곳뿐이고 다른 출처 2곳을 못 찾은 2(2018.3.9 알사일리야전 45분 타레미 골: QSL 공식 기사 1곳, 2018.10.26 알코르전 53분 바이스 골: 도움 언급 없음)",
    "2014.8.1 이전 도움(101개)은 Transfermarkt 한 곳 기준(FotMob 도움 기록이 이 시기에 거의 비어 있음)이라 경기별로 다른 출처와 대조하지는 않음. 2014.8.1 이후 도움 중 Transfermarkt·FotMob 이벤트가 함께 센 것(±2분)은 그대로 쓰고, FotMob 이벤트가 없는 카타르 경기 4개는 다른 출처 2곳이 확인해 넣음: 2018.3.1 알라이얀전 22분 하템·54분 아마두·62분 타레미 골(QSL 공식 경기 기사, Voetbal International 'Enorm aandeel Sneijder in stunt Al Gharafa'), 2018.4.3 알자지라전(AFC 챔스) 44분 아마두 골 코너킥(QSL 경기 기사, Gulf News). 2014.8 이후 FotMob에만 있는 도움은 없음(FotMob 경기 자료는 Transfermarkt 골·도움 경기와 2017.3 이후 출전 경기만 받음)",
    "2010.11.28 파르마전은 FotMob이 스탄코비치 75분 골에 더해 캄비아소 22분 골도 스네이더르 도움으로 적었으나(Transfermarkt는 비아비아니 헤더 도움) 인테르 공식 경기 기사는 스네이더르 코너킥에서 비아비아니가 건드린 뒤 골로 적고 월드풋볼도 비아비아니 도움이라 넣지 않음(Transfermarkt 1개만 셈). 2010.10.29 제노아전 무리안타리 골의 분은 Transfermarkt 45+3분·FotMob 45분이라 Transfermarkt 표기를 씀",
    "도움 합계 비교: Transfermarkt 146·네덜란드어 위키백과 145(아약스 2003-04만 Transfermarkt 12·위키백과 11)·튀르키예어 위키백과 134(니스·알가라파 빠짐)·FotMob 경력 합계는 아약스·레알 마드리드 자료 없음. 이 계산기 138은 위 제외 8개를 뺀 값",
    "날짜는 현지 날짜(Transfermarkt 리포트 날짜, 카타르 리그·AFC 챔스는 UTC를 카타르 시간으로 바꿈)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(에투·이브라히모비치·드록바·라울·판니스텔로이·이과인·로번) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위(Transfermarkt 순위표)를 리그 모형에 넣은 값, 직접 추정 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "리그 모형: 에레디비시 2004-05~2006-07은 다른 선수 자료의 순위별 18칸 값(1위 1837~18위 1406), 에이르스터 디비시(2부) 2005-06 17위는 다른 선수 자료 17위 값 1282, 쉬페르리그 2013-14는 다른 선수 자료의 순위별 값에 없는 순위를 이웃 순위 값 사이 직선 보간(4위 1582·7위 1509·12위 1418·13위 1402·14위 1386·15위 1370), 쉬페르리그 2014-15는 다른 선수 자료에 1위(갈라타사라이 1750)뿐이라 그 값에 맞춘 평균 약 1450·흩어짐 119 곡선(추정), 카타르 2017-18·2018-19는 마레즈·에투 자료와 같은 리그 수준(평균 1460·흩어짐 45)에 Transfermarkt 최종 순위",
    "직접 추정(모두 '추정'): 튀르키예 4부 발조바 야샴 스포르 2014-15(16위/18팀) 910과 24 에르진잔스포르 2016-17(9위/19팀) 990(튀르키예 4부, 쉬페르리그 평균에서 3단계 아래로 잡은 것이라 근거 약함), 파크타코르 2017 1위 1380, 아스타나 2015 1위 1400, CSKA 모스크바 2009 2위 1604, 스위스 툰 2005-06 5위 1461, 브뢴뷔 2005-06 2위 1520, 바슬루이 2012-13 5위 1480, 하이두크 스플리트 2012-13 4위 1430, 아우스트리아 빈 2006-07 6위 1385, IK 스타르트 2006 13위 1350(각 근거는 기록의 상대 수준 설명에 적음)",
    "대회 비중: KNVB컵·코파 델 레이·코파 이탈리아·튀르키예컵·카타르 컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), 요한 크라위프 실드·수페르코파·수페르코파 이탈리아나·UEFA 슈퍼컵·튀르키예 슈퍼컵은 국내컵 결승, FIFA 클럽 월드컵(2010)은 클럽 월드컵, UEFA컵 1라운드(2006)는 유로파 예선, 인터미디어트 스테이지(32강)는 유로파 토너먼트, AFC 챔스 조별·예선 플레이오프(단판)는 아시아 대회 비중으로 계산함. 네덜란드 유럽 대항전 플레이오프(2005-06 흐로닝언, 2006-07 헤이렌베인·AZ)는 리그 경기로 둠(수아레스·메르턴스 선례). 튀르키예컵·QSL컵 조별은 리그식(무승부 1점)",
    f"두 경기 합산(챔스 예선과 토너먼트, 유로파 예선, UEFA컵 1라운드, 수페르코파, 네덜란드 유럽 플레이오프, 튀르키예컵 준결승·8강) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회 2020-21까지, 스페인 수페르코파 2018-19까지, 네덜란드 유럽 플레이오프에는 적용(연장 있음), 튀르키예컵은 판페르시·에투 자료처럼 원정 다득점 없음·연장 있음으로 둠(튀르키예 축구협회가 튀르키예컵 원정 다득점을 폐지한 것은 2021-22라는 보도가 있어 근거 약함). 스네이더르가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "연장·승부차기: 2016.8.13 튀르키예 슈퍼컵 결승(승부차기) 100분 발타 골 도움은 연장 시간으로 계산. 2007.5.6 KNVB컵 결승(승부차기)·2013.8.11 슈퍼컵(연장)·2014.8.25 슈퍼컵(승부차기)의 출전 분은 Transfermarkt 그대로. 2003.8.27 챔스 예선 그라저전은 실버골 규정(59분 교체)이라 출전 분 그대로 둠",
    "시즌 구분: 스네이더르의 경기 가운데 7월에 열린 것이 없어 클럽 모두 기본 8월 1일 기준(아약스·갈라타사라이 7월 10일 기준 선례와 값이 같음). 클럽 구분은 2007.8.12 전 아약스(2007.5.20 네덜란드 플레이오프까지), 2009.8.29 전 레알 마드리드, 2013.1.22 전 인테르(2012.9.26까지), 2017.8.7 전 갈라타사라이(2017.6.3까지), 2018.1.5 전 니스, 이후 알가라파(2018.1.12 첫 경기)",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 챔스 2009-10, 클럽 월드컵 2010(Transfermarkt 표기 2011), 리그 우승 5회(에레디비시 2003-04, 라리가 2007-08, 세리에A 2009-10, 쉬페르리그 2012-13·2014-15), 국내컵 7회(KNVB컵 2005-06·2006-07, 코파 이탈리아 2009-10·2010-11, 튀르키예컵 2013-14·2014-15·2015-16), 슈퍼컵 5회(요한 크라위프 실드 2006, 수페르코파 이탈리아나 2010, 튀르키예 슈퍼컵 2013·2015·2016), 카타르 스타스컵(QSL컵) 2018-19. 대표팀 기록과 출처 단체가 적히지 않은 개인상(2004 '최고 신인'·2009-10 '올해의 미드필더')은 뺌",
    f"은퇴(2019.8.12 발표). 마지막 경기 {d_(LAST[0])} 알아흘리전",
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const SNE_E={J(E)};\nconst SNE_M={J(M)};\nconst SNE_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
