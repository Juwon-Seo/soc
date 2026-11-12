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
