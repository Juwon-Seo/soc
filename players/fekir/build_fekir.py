#!/usr/bin/env python3
"""Nabil Fekir: raw/ -> fekir.json + src/data/fek.js (판정 근거는 judgments.md)

  python3 players/fekir/build_fekir.py            # 파일 쓰기
  python3 players/fekir/build_fekir.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/fekir/build_fekir.py --cross    # 동료 자료 대조
  python3 players/fekir/build_fekir.py --fm       # FotMob 골 대조
  python3 players/fekir/build_fekir.py --root=<스크래치 복사본>   # 그 복사본의 src/data에 쓰기(검증용)

에릭센(build_eriksen.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/fotmob_playerMatches.csv,
raw/ranks.txt(순위표), /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
src/data/{lac,vab,gou,isc}.js(같은 경기 동료 자료 대조).
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
OUT_JS = os.path.join(ROOT, "src", "data", "fek.js")
OUT_JSON = os.path.join(HERE, "fekir.json")
ME = "나빌 페키르"
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
# 출전 분 고침: gameId -> (분, 근거)  (없음: Transfermarkt 출전 분 그대로)
MIN_FIX = {
    "2770607": (90, "2016.12.14 쿠프 드 라 리그 16강 갱강전(2:2 뒤 승부차기). Transfermarkt 출전 분 120(경기 시간 120으로 잡음)이지만 2016-17 쿠프 드 라 리그는 연장 없이 바로 승부차기(Lyon Capitale·영어 위키백과 2016-17 대회 문서) → 풀타임 90분"),
}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'·본인 도움은 일반 규칙)
EXCL_A = {
    "2480869|58": "TM 단독(유형 빈칸, FotMob 도움 없음). 경기 기사: Maxifoot은 '페키르의 왼쪽 돌파 뒤' 라카제트 골로 적고, FK 믈라다 볼레슬라프 구단 기사는 수비수 맞고 굴절된 공으로 적음 → 다른 출처 2곳 확인 안 됨(굴절 가능성)",
    "2770607|43": "TM 단독('Pass', FotMob 이벤트 도움 없음). fbref 골 기록만 페키르 도움, Lyonmag·Maxifoot 등 경기 기사에 도움 언급 없음 → 다른 출처 1곳뿐",
    "3047852|85": "TM 단독(유형 빈칸, FotMob 도움 없음). Maxifoot: 은돔벨레의 빗맞은 슛이 페키르 맞고 뎀벨레에게 흘러감(본인 의도 없는 굴절). worldfootball·Fox Sports는 페키르 도움, Goal.com은 데파이 도움 → 굴절이라 뺌",
    "4579435|45+5": "TM 단독(UAE 리그컵, FotMob 경기 자료 없음). 알아인 구단·알자지라 구단·UAE 프로리그 기사 모두 비니시우스 멜루 골만 적고 도움자 없음 → 확인 안 됨",
    "4610210|4": "TM 단독(FotMob UAE 경기에 도움 자료 없음). UAE 프로리그 기사: 샤들리가 박스 밖에서 찬 중거리 슛. Soccerway 이벤트 목록에 페키르 이름만 있음 → 확인 안 됨",
    "4768475|40": "TM 단독(유형 빈칸). 알자지라 구단·Sharjah24·Voice of Emirates 기사에 도움자 없음 → 확인 안 됨",
    "4807977|50": "TM 단독('Corner'). 알자지라 구단·Sharjah24·Panafrica Football 기사가 반자 헤더만 적고 페키르 코너킥 언급 없음 → 확인 안 됨",
    "4825100|47": "TM 단독(유형 빈칸). 알이티하드(Aletihad)·Sherepost 기사는 브루누 골만 적고 도움자 없음 → 확인 안 됨",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳 이상이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2814012|9": "Maxifoot 'un but et trois passes décisives' · Lyonmag 'Nabil Fekir centre ... trouve la tête de Mouctar Diakhaby (2-0)'",
    "2814012|70": "Maxifoot(1골 3도움, 코르네 두 골 모두 페키르 패스) · Lyon Capitale(코르네 두 골 모두 페키르가 만듦)",
    "2814012|75": "Maxifoot 'troisième passe décisive de Fekir (5-0, 75e)' · Lyon Capitale(코르네 두 골 모두 페키르가 만듦)",
    "4460969|37": "알자지라 구단 경기 기사(jc.ae) 'Fekir ... squaring it to Bruno De Oliveira' · UAE 프로리그 공식 기사(같은 설명)",
    "4499200|49": "알자지라 구단 경기 기사(jc.ae): 후반 시작 직후 페키르가 박스로 넣어 준 공을 쿨리발리가 마무리 · valuestats 경기 기록(쿨리발리 49분, 도움 페키르)",
    "4560611|60": "UAE 프로리그 공식 기사 'Neeskens Kebano converted Fekir's assist to make it 3-0' · 알자지라 구단 경기 기사(jc.ae, 같은 내용)",
    "4807961|77": "알자지라 구단 경기 기사(jc.ae) 77분 'Nabil Fekir delivered a cross ... Banza rose ... header' · UAE 프로리그 공식 기사(같은 설명)",
    "4807977|20": "알자지라 구단 경기 기사(jc.ae) 페키르 패스를 받은 브루누 선제골 · Voice of Emirates 'following a precise pass from Nabil Fekir'",
}
# FotMob에만 있는 도움(넣지 않음 / 넣음) — judgments.md 4절
FM_ONLY_DECIDED = {
    "3748330": "2022.2.9 라요 바예카노전(코파 델 레이 준결승 1차전) 26분 보르하 이글레시아스 골: FotMob 경기 이벤트와 Forza Football(데이터 피드)만 페키르 도움, Transfermarkt 도움 없음, 경기 기사(베티스 구단·스페인 언론)에 도움 언급 없음 → 넣지 않음",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "ES1", "UAE1", "SA1"}
CUP = {"FRC", "FRL", "CDR", "UAEP", "UALC", "SAKC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 16강까지(쿠프 드 프랑스 5~7라운드·코파 델 레이 1~3라운드 포함)
    if cid == "FRCH": return "df"   # 트로페 데 샹피옹 = 국내컵 결승
    if cid == "SUC": return "dsf"   # 수페르코파(4팀) 준결승
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 2라운드(32강)·intermediate stage·16강·8강
    if cid == "ECLQ": return "ecq"
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"
        if r.startswith("semi"): return "ecsf"
        if r.startswith("final"): return "ecf"
        return "eck"   # 녹아웃 플레이오프(intermediate stage)
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
    if cid in ("CL", "CLQ", "EL", "ELQ", "ECLQ", "UCOL"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CDR":   # 코파 델 레이 준결승: 원정 다득점 2018-19까지, 연장 있음
        ag, et = int(d < "2019-07-01"), 1
    elif cid == "UALC":  # UAE 리그컵: 원정 다득점·연장 없이 승부차기(judgments.md 5절)
        ag, et = 0, 0
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
# 통합표와 이름 표기가 다른 같은 팀(Transfermarkt 표기 → 통합표 표기)
MANUAL_ALIAS = {"al ain fc": "al ain", "al wasl sc": "al wasl", "shabab al ahli club": "shabab al ahli dubai fc",
                "al nasr sc": "al nasr dubai"}
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

def interp(tab, r):
    """기존 순위값 사이는 앞뒤 값의 직선 보간(빈 순위 하나면 가운데)"""
    if r in tab: return tab[r]
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return int(tab[lo] + (tab[hi] - tab[lo]) * (r - lo) / (hi - lo) + 0.5)

# 리그2(프랑스 2부): 기존 선수 자료의 순위값(디 마리아·카바니·라카제트 선례, 평균 1540 + 2부 흩어짐 × 곡선) — judgments.md 7절
FR2_KNOWN = {1: 1669, 2: 1624, 4: 1582, 6: 1567, 7: 1559, 8: 1550, 10: 1532, 13: 1516, 14: 1513, 15: 1508, 17: 1490, 19: 1480}
# 세군다(스페인 2부): 기존 순위값
ES2_KNOWN = {1: 1753, 2: 1712, 3: 1687, 6: 1654, 7: 1647, 8: 1640, 9: 1632, 10: 1623, 11: 1615, 13: 1606, 14: 1601, 16: 1595, 17: 1589, 19: 1572, 20: 1567, 21: 1563, 22: 1554}
# UAE 프로리그 14팀: 이니에스타 자료(2023-24)의 순위값 3위 1510·4위 1491·6위 1451·9위 1403·11위 1380 + 그 사이 보간
UAE_KNOWN = {3: 1510, 4: 1491, 6: 1451, 9: 1403, 11: 1380}
# 기존 순위값 범위 밖(1·2·12~14위)은 4절 UAE 모형(평균 1440·흩어짐 85 × 21칸 순위 곡선, 기존 값을 ±2 안으로 재현)
_SA20 = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
_CV = [(v - 1739) / 91.3 for v in _SA20]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return _CV[i] + (_CV[i + 1] - _CV[i]) * t
# 사우디 프로리그 18팀: 다른 선수 자료의 순위값(2025-26·2026-27, 시즌 무관 같은 값)
SA_KNOWN = {1: 1813, 2: 1703, 3: 1641, 4: 1604, 5: 1585, 6: 1568, 7: 1544, 8: 1519, 9: 1497, 10: 1481,
            11: 1469, 12: 1456, 13: 1450, 14: 1432, 15: 1408, 16: 1389, 17: 1377, 18: 1352}
NOW = "(11월 중순 현재)"

def model(lg, season, r, n):
    if lg == "UAE1":
        if r in UAE_KNOWN or (min(UAE_KNOWN) < r < max(UAE_KNOWN)):
            return interp(UAE_KNOWN, r), f"UAE 프로리그 {season} {r}위"
        return int(1440 + 85 * curve(r, n) + 0.5), f"UAE 프로리그 {season} {r}위 (리그 모형값)"
    if lg == "SA1":
        cur = " " + NOW if season == "2026-27" else ""
        return SA_KNOWN[r], f"사우디 프로리그 {season}{cur} {r}위"
    if lg == "FR2" and FR2_KNOWN:
        return interp(FR2_KNOWN, r), f"리그2 {season} {r}위"
    if lg == "ES2" and ES2_KNOWN:
        return interp(ES2_KNOWN, r), f"세군다 {season} {r}위"
    return None
RANK_LG = ["UAE1", "SA1", "FR2", "ES2"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정')
MAN = {
    (key("Ludogorets Razgrad"), "2022-23"): (1520, "불가리아 2022-23 1위 (추정, 다른 선수 자료 루도고레츠 2020-21 1위 1520과 같음)"),
    (key("CD Ibiza Islas Pitiusas"), "2022-23"): (1150, "스페인 4부(세군다 페데라시온) 2022-23 (추정, 다른 선수 자료 스페인 4부 1150과 같음)"),
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
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "CLQ", "EL", "ELQ", "ECLQ", "UCOL") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            if (k, s) in LV_FIX: lv = LV_FIX[(k, s)]
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
# 통합표 값을 쓰되 기록의 상대 수준 설명은 확인한 최종 순위로 적는 것(judgments.md 7절)
LV_FIX = {
    (key("Al-Wasl SC"), "2024-25"): "UAE 프로리그 2024-25 4위 (추정, 다른 선수 자료 값 1480과 같음)",
    (key("Shabab Al-Ahli Club"), "2025-26"): "UAE 프로리그 2025-26 2위 (추정, 다른 선수 자료 값 1480과 같음)",
}

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local"]   # 유럽: Transfermarkt 리포트 날짜, UAE·사우디: UTC를 현지 시간(두바이·리야드)으로 바꾼 날짜

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
        if r["fekir_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et=0):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["fekir_scorer"] == "1", e["fekir_assist_other"] == "1"
    if e["fekir_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag, ldate(g))); EXCL_CNT["본인 도움"] += 1
        EXCL_LIST["본인 도움"].append((ldate(g), g["opponent"], e["minute"], e["scorer"], e["assist_type"]))
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
    et = int(ko == 1 and tie is None and "+" not in e["minute"] and mi > 90)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if e["own_goal"] == "1" or not ours:
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
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
            if not hit:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local"] >= GAP and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")):
        FM_ONLY.append((gid, G[gid]["date_local"], ts))

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
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["fekir_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["fekir_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["fekir_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local"] if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Alexandre Lacazette": ("lac.js", "LAC", "2013-07-01", "2017-07-05"),
         "Mathieu Valbuena": ("vab.js", "VAB", "2015-07-01", "2017-07-01"),
         "Yoann Gourcuff": ("gou.js", "GOU", "2013-07-01", "2015-07-01"),
         "Isco": ("isc.js", "ISC", "2023-07-01", "2024-08-30")}
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
FK = lambda s: norm(s or "") in ("nabil fekir", "fekir")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("페키르 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and FK(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→페키르 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    for x in ent:   # Transfermarkt 페키르 도움을 이 계산기에서 뺀 동료 골(참고)
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["fekir_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 페키르 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # TM 동료 도움 → 페키르 골인데 동료 파일에 없음(참고)
        if e["fekir_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 페키르 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
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
CLUBS = [("lyofk", "2019-07-23", "올랭피크 리옹", "2013~2019"), ("betfk", "2024-08-30", "레알 베티스", "2019~2024"),
         ("jazfk", "2026-08-06", "알자지라", "2024~2026"), ("abhfk", None, "아브하", "2026~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"1041": "lyofk", "150": "betfk", "2524": "jazfk", "40039": "abhfk"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_fekir import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["fekir_assist_other"] == "1")
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const FEK_E={J(E)};\nconst FEK_M={J(M)};\nconst FEK_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
