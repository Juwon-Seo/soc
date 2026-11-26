#!/usr/bin/env python3
"""Edin Dzeko: raw/ -> dzeko.json + src/data/dze.js (판정 근거는 judgments.md)

  python3 players/dzeko/build_dzeko.py            # 파일 쓰기
  python3 players/dzeko/build_dzeko.py --debug    # Elo 출처 로그
  python3 players/dzeko/build_dzeko.py --cross    # 동료 자료 대조
  python3 players/dzeko/build_dzeko.py --fm       # FotMob 골 대조

제코(build_eriksen.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
/home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
src/data/{agu,sil,sal,tot,lau,pas}.js(같은 경기 동료 자료 대조).
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
OUT_JS = os.path.join(ROOT, "src", "data", "dze.js")
OUT_JSON = os.path.join(HERE, "dzeko.json")
ME = "에딘 제코"
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
# 출전 분 고침: gameId -> (분, 근거)
MIN_FIX = {}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'·상대 자책골은 일반 규칙)
EXCL_A = {
    "3030595|86": "TM 단독(FotMob 도움 없음). 경기 기사(Sports Mole 문자 중계 등): 86분 나잉골란 골은 콜라로프가 안으로 파고들어 내준 공 → 제코 도움 아님",
    "4129784|15": "TM 단독(FotMob 도움 없음). DHA(데미뢰렌 통신) 경기 기사: 제코가 골문 앞으로 내준 공이 수비에 맞고 시만스키 앞에 떨어짐(굴절) → 도움 아님(Cumhuriyet 문자 중계는 제코 패스로 적음)",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳 이상이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2800309|61": "AP 기사(ESPN 게재) 'Dzeko returned the favor ... with a 40-yard pass, which El Shaarawy controlled' · Sky Sports(AFP 계열 기사, worldsoccertalk 같은 글) 'controlled Dzeko's 40-yard pass'",
    "3614891|90+4": "인테르 구단 경기 기사(영어 'Edin Dzeko sent in a low cross that Alexis Sanchez converted', 이탈리아어 'su assist di Edin') · Fox Sports 경기 기록 'assisted by E. Dzeko'",
    "4129466|43": "아나돌루 통신 기사(TGRT Haber·Politikam 게재) 'Dzeko'nun ceza alanında pasında ... İrfan Can Kahveci, topu ağlara gönderdi' · Cumhuriyet 문자 중계 'Dzeko'nun pasında İrfan Can net bir vuruşla ağlara yolladı'",
    "4893856|98": "샬케 구단 경기 기사 'Edin Džeko laid the ball off and Moussa Sylla ... (98')' · dpa 기사(Volksstimme 게재) 'ließ einen flachen Ball in den Strafraum zu Sylla abtropfen'",
}
# Transfermarkt 리포트에 없는 도움(FotMob 선수 경기 목록 + 다른 출처 2곳): (gameId, 분, 표시 분, 골 전 우리, 골 전 상대, 득점자, 근거)
ADD_ROWS = [
    ("2897523", 15, 0, 0, 0, "Cengiz Ünder", "FotMob 선수 경기 목록 도움 1 · AS 로마 구단 경기 기사 'Dzeko does well to control the ball and play it into the box for Cengiz' · Forza Italian Football 'latched onto a ball from Edin Dzeko' (Transfermarkt 리포트 없음, 경기 성적 도움 0)"),
]

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"TS1", "L1", "GB1", "IT1", "TR1", "L2"}
CUP = {"TSP", "DFB", "FAC", "CGB", "CIT", "TRP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round"): return "dk"
        return "dc"   # 1~5라운드·16강·재경기·튀르키예컵 조별
    if cid in ("GBCS", "SCI"): return "df"   # 커뮤니티 실드·수페르코파 이탈리아나(2팀 단판) = 국내컵 결승
    if cid == "UI": return "elq"             # 인터토토컵 = 유로파 예선(선례)
    if cid == "UEFA":                        # UEFA컵(2009년 이전): 1라운드 = 예선, 조별, 3라운드(32강) = 토너먼트
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        return "elk"
    if cid == "CLQ": return "clq"
    if cid == "ECLQ": return "ecq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"   # 2024-25 리그 단계 포함
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 2라운드(32강)·intermediate stage(32강·녹아웃 PO)·16강·8강(2020년 8월 단판 포함)
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"   # 2025-26 리그 단계 포함
        if r.startswith("semi"): return "ecsf"
        if r.startswith("final"): return "ecf"
        return "eck"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

UEFA_C = ("CL", "CLQ", "EL", "UEFA", "UI", "ECLQ", "UCOL")
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
        oh, oa = map(int, re.match(r"(\d+):(\d+)", o["final"]).groups())
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in UEFA_C:
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CGB":   # 잉글랜드 리그컵 준결승: 2017-18까지 원정 다득점·연장
        ag = et = int(d < "2018-07-01")
    elif cid == "CIT":   # 코파 이탈리아: 원정 다득점 2021-22까지·연장, 2019-20 준결승 2차전(2020.6)만 연장 없이 승부차기
        ag, et = int(d < "2022-07-01"), int(not ("2020-02-01" <= d < "2020-07-01"))
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
    if d[:7] in ("2020-07", "2020-08"): s = 2019   # 코로나로 늦게 끝난 2019-20 시즌
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))
def half_up(x): return int(x + 0.5)
def mid(a, b): return half_up((a + b) / 2)   # 빠진 순위 = 이웃 순위값의 평균(다른 판정과 같은 방식)

# 체코 1부(16팀): 다른 선수 자료(네드베드 등)의 순위별 값 1위 1500 … 16위 1312, 11위는 10·12위 평균
CZ = {1: 1500, 2: 1488, 3: 1475, 4: 1462, 5: 1450, 6: 1438, 7: 1425, 8: 1412, 9: 1400, 10: 1388,
      11: mid(1388, 1362), 12: 1362, 13: 1350, 14: 1338, 15: 1325, 16: 1312}
# 2. 분데스리가: 다른 선수 자료의 순위별 값(시즌 무관), 13위는 12·14위 평균
BL2 = {1: 1697, 2: 1667, 3: 1636, 4: 1622, 5: 1615, 6: 1609, 7: 1600, 8: 1592, 9: 1584, 10: 1579, 11: 1574,
       12: 1570, 13: mid(1570, 1561), 14: 1561, 15: 1544, 16: 1545, 17: 1541, 18: 1532}

def model(lg, season, r, n):
    if lg == "TS1" and season in ("2005-06", "2006-07"):
        return CZ[r], f"체코 {season} {r}위 (추정, 다른 선수 자료의 체코 1부 순위별 값과 같음)"
    if lg == "L2" and season in ("2010-11", "2025-26"):
        return BL2[r], f"2. 분데스리가 {season} {r}위"
    return None
RANK_LG = ["TS1", "L2"]

# 순위표·모형으로 안 되는 상대(직접 추정·이웃 순위 평균; 순위는 judgments.md 7절의 최종 순위표로 확인)
MAN = {
    (key("Würzburger FV 04"), "2007-08"): (1300, "독일 4부(오버리가 바이에른) 2007-08 14위 (추정, 다른 선수 자료 독일 4부 1300과 같음)"),
    (key("FC Oberneuland"), "2008-09"): (1300, "독일 4부(레기오날리가 북부) 2008-09 9위 (추정, 다른 선수 자료 독일 4부 1300과 같음)"),
    (key("Preußen Münster"), "2010-11"): (1300, "독일 4부(레기오날리가 서부) 2010-11 1위 (추정, 다른 선수 자료 독일 4부 1300과 같음)"),
    (key("Hallescher FC"), "2026-27"): (1300, "독일 4부(레기오날리가 북동부) 2026-27 (11월 초 현재) 4위 (추정, 다른 선수 자료 독일 4부 1300과 같음)"),
    (key("SV Wehen Wiesbaden"), "2009-10"): (1403, "독일 3부 리가 2009-10 15위"),
    (key("Beşiktaş JK"), "2009-10"): (1640, "쉬페르리그 2009-10 4위 (추정, 다른 선수 자료 갈라타사라이 2009-10 3위 1650·페네르바흐체 2008-09 4위 1640에 맞춤)"),
    (key("CSKA Moscow"), "2018-19"): (1537, "러시아 프리미어리그 2018-19 4위 (리그 수준 추정)"),
    (key("Leicester City"), "2013-14"): (1761, "챔피언십(2부) 2013-14 1위"),
    (key("FC Viktoria Plzen"), "2016-17"): (1560, "체코 2016-17 2위 (추정, 다른 선수 자료 플젠 2위 1560과 같음)"),
    (key("KAA Gent"), "2019-20"): (1670, "벨기에 1부 2019-20 2위 (추정, 다른 선수 자료 벨기에 2위 1670과 같음)"),
    (key("SC Braga"), "2020-21"): (1690, "포르투갈 1부 2020-21 4위"),
    (key("Ajax Amsterdam"), "2020-21"): (1837, "에레디비시 2020-21 1위"),
    (key("FC Twente Enschede"), "2023-24"): (1677, "에레디비시 2023-24 3위"),
    (key("Union Saint-Gilloise"), "2023-24"): (1670, "벨기에 1부 2023-24 2위 (추정, 다른 선수 자료 벨기에 2위 1670과 같음)"),
    (key("FC Zimbru Chisinau"), "2023-24"): (1350, "몰도바 2023-24 4위/8팀 (추정, 다른 선수 자료 몰도바 1위 1450보다 100 낮게)"),
    (key("Spartak Trnava"), "2023-24"): (1400, "슬로바키아 2023-24 3위 (추정, 다른 선수 자료 슬로바키아 3위 1400과 같음)"),
    (key("Beşiktaş JK"), "2023-24"): (mid(1644, 1613), "쉬페르리그 2023-24 6위"),
    (key("Gaziantep FK"), "2023-24"): (mid(1549, 1523), "쉬페르리그 2023-24 11위"),
    (key("Istanbulspor"), "2023-24"): (1418, "쉬페르리그 2023-24 20위 (추정, 19위 1428에서 18·19위 간격만큼 낮춤)"),
    (key("Kasimpasa"), "2024-25"): (mid(1554, 1522), "쉬페르리그 2024-25 10위"),
    (key("Alanyaspor"), "2024-25"): (mid(1512, 1492), "쉬페르리그 2024-25 13위"),
    (key("FC Midtjylland"), "2024-25"): (1560, "덴마크 2024-25 2위 (추정, 다른 선수 자료 미트윌란 2위 1560과 같음)"),
    (key("SK Slavia Prague"), "2024-25"): (1600, "체코 2024-25 1위 (추정, 다른 선수 자료 슬라비아 1위 1600과 같음)"),
    (key("RSC Anderlecht"), "2024-25"): (mid(1650, 1508), "벨기에 1부 2024-25 4위 (추정, 다른 선수 자료 2024-25 2위 1650·6위 1508의 평균)"),
    (key("Rapid Vienna"), "2025-26"): (1472, "오스트리아 분데스리가 2025-26 5위 (추정, 다른 선수 자료 오스트리아 2019-20 5위 1472와 같음)"),
    (key("Polissya Zhytomyr"), "2025-26"): (1580, "우크라이나 2025-26 3위 (추정, 다른 선수 자료 우크라이나 3위 1580과 같음)"),
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
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "CLQ", "EL") else [eu]
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
    return g["date_local"]   # Transfermarkt 리포트 날짜(모두 유럽 현지)

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
        if r["dzeko_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
PENDING = []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
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
    isg, isa = e["dzeko_scorer"] == "1", e["dzeko_assist_other"] == "1"
    if e["dzeko_self_assist"] == "1":
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
        if not ours and e["assist_type"].startswith("Handball"): why = "상대 PK(제코 핸드볼 반칙)"
        elif e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            k = why if tag not in EXCL_A else "개별 판정"
            EXCL_CNT[k] += 1; EXCL_LIST[k].append((d, opp, e["minute"], e["scorer"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
            if not hit:
                PENDING.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

for gid, mi, dm, gf, ga, sc, why in ADD_ROWS:
    g = G[gid]
    add_row("a", mi, dm, gf, ga, 0, sc, tie_of(g), comp_of(g["competitionId"], g["round"]), ko_of(g), ldate(g), g["opponent"].strip(), g["competitionId"])
    judg.append(("도움 추가(TM 리포트 없음)", ldate(g), g["opponent"], mi, sc, why))

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local"] >= GAP and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")):
        FM_ONLY.append((gid, G[gid]["date_local"], ts))

if PENDING:
    for x in PENDING: print("판정 누락(2014.8 이후 TM 단독 도움):", x)
    if "--debug" not in sys.argv: sys.exit(1)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY, EXCL_CNT)
    for k, v in EXCL_LIST.items(): print(k, v)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["dzeko_scorer"] == "1" and e["gameId"] in G and G[e["gameId"]]["date_local"] >= "2010-08-01":
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["dzeko_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
# FotMob에만 있는 제코 골(2013.7.27 하우엘레이우 자책골)
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["dzeko_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local"] if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Sergio Agüero": ("agu.js", "AGU", "2011-01-07", "2015-08-12"),
         "David Silva": ("sil.js", "SIL", "2011-01-07", "2015-08-12"),
         "Mohamed Salah": ("sal.js", "SAL", "2015-08-12", "2017-07-01"),
         "Francesco Totti": ("tot.js", "TOT", "2015-08-12", "2017-07-01"),
         "Javier Pastore": ("pas.js", "PAS", "2018-07-01", "2021-07-01"),
         "Lautaro Martínez": ("lau.js", "LAU", "2021-08-13", "2023-07-01")}
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
ER = lambda s: norm(s or "") in ("edin dzeko", "dzeko")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("제코 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and ER(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→제코 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    for x in ent:   # Transfermarkt 제코 도움을 이 계산기에서 뺀 동료 골(참고)
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["dzeko_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 제코 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # 동료 파일에서 제코 골의 도움으로 적혔어야 할 것(TM 리포트 기준, 참고)
        if e["dzeko_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 제코 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
    for x in ent:   # 동료 골인데 제코 파일에 도움이 없고 TM에도 없는 것은 대조 대상 아님
        pass
# 같은 경기를 다룬 다른 선수 기록(상대 포함)의 대회·합산 대조
SAME_GAME = []
for r in E:
    for x in ENTS:
        if x["date"] == r[9] and (key(x["opp"]) == key(r[1]) or _sub(key(x["opp"]), key(r[1]))):
            if x.get("comp") and x["comp"] != r[3]:
                SAME_GAME.append(("대회 다름", r[9], r[1], x["p"], x["comp"], r[3]))
            break
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
    for s in SAME_GAME: print(s)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("zeldz", "2005-07-01", "젤레즈니차르", "2003~2005"), ("tepdz", "2007-07-01", "FK 테플리체", "2006~2007"),
         ("wobdz", "2011-01-07", "VfL 볼프스부르크", "2007~2011"), ("mcidz", "2015-08-12", "맨체스터 시티", "2011~2015"),
         ("romdz", "2021-08-13", "AS 로마", "2015~2021"), ("intdz", "2023-07-01", "인테르", "2021~2023"),
         ("fendz", "2025-07-10", "페네르바흐체", "2023~2025"), ("fiodz", "2026-01-22", "피오렌티나", "2025~2026"),
         ("s04dz", None, "샬케 04", "2026~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"2573": "zeldz", "814": "tepdz", "82": "wobdz", "281": "mcidz", "12": "romdz", "46": "intdz", "36": "fendz", "430": "fiodz", "33": "s04dz"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_dzeko import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["dzeko_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC))
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
mmin = {m[0]: m[3] for m in M}
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const DZE_E={J(E)};\nconst DZE_M={J(M)};\nconst DZE_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
