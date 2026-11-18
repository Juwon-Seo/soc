#!/usr/bin/env python3
"""Luis Alberto: raw/ -> luisalberto.json + src/data/lal.js (판정 근거는 judgments.md)

  python3 players/luisalberto/build_luisalberto.py            # 파일 쓰기
  python3 players/luisalberto/build_luisalberto.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/luisalberto/build_luisalberto.py --cross    # 동료·같은 경기 자료 대조
  python3 players/luisalberto/build_luisalberto.py --fm       # FotMob 골 대조
  python3 players/luisalberto/build_luisalberto.py --root=<스크래치 복사본>   # 그 복사본의 src/data에 쓰기(검증용)

아스파스(build_aspas.py)·드락슬러(카타르) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트),
raw/ranks.txt(순위표), /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
src/data/sua.js·ger.js·ste.js·rey.js(같은 경기 동료 자료 대조).
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
OUT_JS = os.path.join(ROOT, "src", "data", "lal.js")
OUT_JSON = os.path.join(HERE, "luisalberto.json")
ME = "루이스 알베르토"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트, 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

BARCA_B = "2464"   # 바르셀로나 B(2군) — 리저브 팀이라 제외(judgments.md 1절)
GAMES = [g for g in rd("tm_games.csv") if g["club_id"] != BARCA_B]
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
MIN_FIX = {
    "4601025": (120, "2025.4.22 카타르컵 준결승 알가라파전: Transfermarkt 90분(경기 시간 90분으로 적음)이지만 FotMob 경기 기록에 101·115분 교체와 연장 전후반이 있고 FotMob 출전 120분(선발 풀타임) → 120분(연장 뒤 승부차기)"),
}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'·상대 자책골·본인 도움은 일반 규칙)
EXCL_A = {
    "2633849|68": "2015.12.15 야고스테라전(코파 델 레이) 68분 후안 도밍게스 골: FotMob 도움 없음, 루이스 알베르토 코너킥으로 적은 곳은 Vavel 1곳(AP·Sports Mole·TNT는 도움자 없음) → 넣지 않음",
    "3496449|49": "2021.2.23 바이에른전(챔스 16강 1차전) 49분 코레아 골: FotMob 도움 없음(선수 경기 목록도 0), Football Web Pages·TNT 문자중계는 코레아 단독 돌파로 적고 도움자 없음, 루이스 알베르토 패스로 적은 곳은 팬 사이트 1곳 → 넣지 않음",
    "3614886|68": "2022.4.30 스페치아전 68분 밀린코비치사비치 골: FotMob(경기 이벤트·선수 경기 목록 1개는 90분 아체르비 골)·Mediotiempo 문자중계 모두 이 골 도움자로 루이스 알베르토를 적지 않음 → 넣지 않음",
    "4400930|90+6": "2024.8.10 카타르 SC전 90+6분 올룽가 골: FotMob 자료 없음, 리그(QSL) 공식 기사·걸프 타임스(같은 글)는 도움자 언급 없이 '쉬운 골'로만 적음 → 넣지 않음",
    "4400935|27": "2024.9.14 알와크라전 27분 에드밀송 골: FotMob 자료 없음, QSL·걸프 타임스·더 페닌슐라 기사 모두 도움자 언급 없음 → 넣지 않음",
    "4400954|40": "2024.9.21 알사드전 40분 에드밀송 골: FotMob 자료 없음, QSL 기사는 왼쪽에서 때린 중거리 슛으로 적고 도움자 언급 없음 → 넣지 않음",
    "4400974|23": "2024.11.1 알샤말전 23분 올룽가 골: FotMob 자료 없음, 걸프 타임스·알두하일 구단 기사 모두 도움자 언급 없음 → 넣지 않음",
    "5024752|88": "2026.10.24 알아라비전 88분 젤송 달라 골: FotMob 도움 없음(이벤트·선수 경기 목록 모두), 루이스 알베르토 도움으로 적은 곳은 걸프 타임스 기사 1곳(카타르 트리뷴·MENAFN은 같은 글 재게재) → 넣지 않음",
}
# FotMob 경기 이벤트에 도움자 이름이 없지만 FotMob 선수 경기 목록(경기별 도움 수)이 Transfermarkt와 같은 도움(+ 확인 출처)
PM_OK = {
    "3433508|51": "2021.4.26 밀란전 51분 코레아 골: FotMob 선수 경기 목록·선수 통계 도움 1(이벤트에는 이름 없음) + Lazio Stories·Football Web Pages",
    "4793113|89": "2026.2.27 움살랄전 89분 베르카네 골: FotMob 선수 경기 목록 도움 1",
    "4793142|29": "2026.4.3 카타르 SC전 29분 라이두니 골: FotMob 선수 경기 목록 도움 2",
    "4793142|60": "2026.4.3 카타르 SC전 60분 조주 골: FotMob 선수 경기 목록 도움 2",
}
# FotMob 경기 이벤트에 없지만 다른 출처 2곳 이상이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2505188|11": "2014.12.3 데포르티보전(코파 델 레이 1차전) 11분 카마초 골: ESPN 데포르테스 경기 기사(루이스 알베르토 프리킥을 카마초가 헤더)·Sports Mole(루이스 알베르토 크로스를 헤더)",
    "4400947|19": "2024.8.16 알라이얀전 19분 에드밀송 골: QSL 공식 기사(=걸프 타임스 같은 글, 'sublime pass by Alberto') + Sport Eden 경기 기록(루이스 알베르토 도움 2) — 근거 보통",
    "4400947|77": "2024.8.16 알라이얀전 77분 알모에즈 골: QSL 공식 기사(=걸프 타임스, 루이스 알베르토 코너킥 헤더) + Sport Eden 경기 기록(assist by Luis Alberto)",
    "4400974|11": "2024.11.1 알샤말전 11분 베리시무 골: 걸프 타임스('inch-perfect overhead cross by Alberto') + 알두하일 구단 기사(루이스 알베르토 크로스를 헤더)",
    "4400990|11": "2025.1.12 카타르 SC전 11분 호맘 골: QSL 공식 기사(=걸프 타임스·카타르 트리뷴 같은 글, 루이스 알베르토의 빠른 프리킥) + 알두하일 구단 기사(루이스 알베르토 프리킥 패스)",
    "4400990|36": "2025.1.12 카타르 SC전 36분 호맘 골: QSL 공식 기사('sublime pass from Alberto') + Sport Eden 경기 기록(루이스 알베르토 도움 2) — 근거 보통",
}
# FotMob에만 있는 도움: gameId -> 판정
FM_ONLY_DECIDED = {
    "2897379": "넣음 — 2018.3.18 볼로냐전 16분 루카스 레이바 골: FotMob 경기 이벤트·선수 경기 목록 도움 1(Transfermarkt 도움 없음) + Sports Mole('played through on goal by Alberto')·Fantacalcio(루이스 알베르토 스루패스)",
    "3651689": "뺌 — 2021.9.30 로코모티프 모스크바전 38분 파트릭 골: FotMob 이벤트만 도움(선수 경기 목록은 0), 경기 기사는 수비 맞고 들어간 골로 적고 도움자 없음",
    "3461819": "뺌 — 2020.12.8 브뤼헤전 12분 코레아 골: Transfermarkt 'Shot on goal'(루이스 알베르토 슈팅 리바운드), FotMob 이벤트만 도움(선수 경기 목록 0) → 리바운드 규칙으로 뺌",
    "3614886": "뺌 — 2022.4.30 스페치아전 90분 아체르비 골: Transfermarkt 'Shot on goal'(슈팅 리바운드), FotMob은 도움으로 셈 → 리바운드 규칙으로 뺌",
}
# FotMob 전용 도움 중 넣는 것: gameId -> (분, 득점자, 골 전 우리-상대)
FM_ADD = {"2897379": (16, "Lucas Leiva", 0, 1)}
# 골 시각 고침 gameId|Transfermarkt 분 -> (분, 근거)
GOAL_MIN_FIX = {}
OG_TO_GOAL = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES1", "GB1", "IT1", "QSL"}
CUP = {"CDR", "FAC", "CGB", "CIT", "QEC1", "QUC1", "QSCP"}   # 국내컵(리그컵·QSL컵·카타르컵 포함)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 16강까지(코파 델 레이 4라운드·16강, EFL컵 2라운드, FA컵 3·4라운드, QSL컵 조별)
    if cid == "SCI":   # 수페르코파 이탈리아나: 결승 = 국내컵 결승, 4팀(2023-24~) 준결승 = 국내컵 준결승
        if r.startswith("semi"): return "dsf"
        return "df"
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
        return "elk"   # 32강·녹아웃 PO(intermediate stage)·16강·8강
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"
        if r.startswith("semi"): return "ecsf"
        if r.startswith("final"): return "ecf"
        return "eck"   # 녹아웃 PO(intermediate stage)·16강
    if cid == "ACLE":   # AFC 챔스 엘리트 리그 단계
        if r.startswith("quarter"): return "aclk"
        if r.startswith("semi"): return "aclsf"
        if r.startswith("final"): return "aclf"
        return "acl"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스·유로파·AFC 조별, QSL컵 조별(리그식)
    return 1

CIT_ET_FROM_2023 = 1   # 코파 이탈리아 2022-23~2023-24 준결승 2차전: 원정 다득점 없음, 합산 동점이면 연장 뒤 승부차기(goal.com·sportface 2024.4 규정 기사, judgments.md 5절)

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
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "EL", "UCOL"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CDR":   # 코파 델 레이: 원정 다득점 2018-19까지, 연장 있음
        ag, et = int(d < "2019-07-01"), 1
    elif cid == "CIT":   # 코파 이탈리아 준결승: 원정 다득점 2021-22까지
        ag = int(d < "2022-07-01")
        et = 1 if d < "2022-07-01" else CIT_ET_FROM_2023
        if et is None: sys.exit("코파 이탈리아 연장 규칙 미정 " + gid)
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
    if d[:7] in ("2020-07", "2020-08"): s = 2019   # 코로나로 늦게 끝난 2019-20 시즌
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 카타르 스타스리그 2025-26 공식 최종 순위: Transfermarkt 표는 2026.4.3 카타르 SC 1-4 알와크라 경기를 경기 결과대로 셈.
# 카타르축구협회 징계위원회가 이 경기를 알와크라 0-3 패배로 정해(출전 자격 없는 베르카네 출전), 공식 순위는 6위 카타르 SC(32점)·7위 알아라비(32점, 득실차)·8위 알와크라(27점)
# (영어 위키백과 2025-26 시즌 문서(출처 QSL)·RSSSF qat2026 최종표 일치, judgments.md 7절)
for _nm, _r in (("Qatar SC", 6), ("Al-Arabi SC", 7), ("Al-Wakrah SC", 8)):
    RANKS[("QSL", "2025-26")][key(_nm)] = (_r, 12)

def interp(tab, r):
    """기존 순위값 사이는 앞뒤 값의 직선 보간(빈 순위 하나면 가운데)"""
    if r in tab: return tab[r]
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return int(tab[lo] + (tab[hi] - tab[lo]) * (r - lo) / (hi - lo) + 0.5)

# 세군다(스페인 2부): 기존 선수 자료(elo/ents.json)의 순위별 최빈값
ES2_KNOWN = {1: 1753, 2: 1712, 3: 1687, 4: 1674, 5: 1660, 6: 1654, 7: 1647, 8: 1640, 9: 1632, 10: 1623, 11: 1615, 12: 1610, 13: 1606, 14: 1601, 15: 1598, 16: 1595, 17: 1589, 18: 1580, 19: 1572, 20: 1567, 21: 1560, 22: 1553}
# 카타르 스타스리그 12팀: 기존 선수 자료(마레즈·에투·라울·카소를라·드락슬러) 순위값(시즌 무관), 드락슬러 빌드의 QA_KNOWN과 같음
QA_KNOWN = {1: 1573, 2: 1518, 3: 1493, 4: 1482, 5: 1470, 6: 1456, 7: 1446, 8: 1439, 9: 1433, 10: 1420, 11: 1410, 12: 1398}
NOW = "11월 18일 현재 순위"

def model(lg, season, r, n):
    if lg == "ES2":
        return interp(ES2_KNOWN, r), f"세군다(2부) {season} {r}위"
    if lg == "QSL":
        if season == "2026-27":
            return QA_KNOWN[r], f"카타르 {season} {r}위 (추정, {NOW})"
        return QA_KNOWN[r], f"카타르 {season} {r}위 (추정, 마레즈 자료와 같은 리그 수준)"
    return None
RANK_LG = ["ES2", "QSL"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정') — judgments.md 7절
MAN = {}
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
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL", "UCOL", "ACLE") else [eu]
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
LV_FIX = {}

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_computed"]   # Transfermarkt 리포트 날짜(= UTC를 마드리드 시간으로 바꾼 날짜, 224경기 차이 0)

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
        if r["la_assist"] == "1":
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
    isg, isa = e["la_scorer"] == "1", e["la_assist_other"] == "1"
    if e["la_self_assist"] == "1":
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
    if tag in GOAL_MIN_FIX: mi, dm = GOAL_MIN_FIX[tag][0], 0
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = int(ko == 1 and tie is None and "+" not in e["minute"] and mi > 90)
    d = ldate(g); opp = g["opponent"].strip()
    if tag in OG_TO_GOAL:   # Transfermarkt 상대 자책골 → 아스파스 골(judgments.md)
        add_row("g", mi, dm, gf, ga, 0, 0, tie, comp, ko, d, opp, cid, et)
        judg.append(("자책골 → 아스파스 골", d, opp, e["minute"], OG_TO_GOAL[tag])); EXCL_CNT["자책골→골"] += 1
        continue
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
        if d >= GAP and tag not in ADD_CONFIRMED and tag not in PM_OK:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
            if not hit:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

for gid, (mi, sc, gf, ga) in FM_ADD.items():
    g = G[gid]
    add_row("a", mi, 0, gf, ga, 0, sc, tie_of(g), comp_of(g["competitionId"], g["round"]), ko_of(g), ldate(g), g["opponent"].strip(), g["competitionId"])
    judg.append(("FotMob 전용 도움 넣음", ldate(g), g["opponent"], mi, sc, FM_ONLY_DECIDED[gid]))
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local_computed"] >= GAP and len(ts) > used_fm.get(gid, 0):
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
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["la_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local_computed"])); continue
    fg = [r for r in FM_EV[gid] if r["la_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["la_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local_computed"] if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

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
    if fn == "lal.js" or not os.path.exists(os.path.join(ROOT, "src", "data", fn)): continue
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
ME_NAMES = ("luis alberto", "luis alberto romero")
CROSS = []
for fn, ent in OTHERS.items():
    # 같은 날짜·같은 상대(= 같은 팀 동료 자료)
    for x in ent:
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                d = cmp_rows(r, x, full=False)
                CROSS.append(("같은 경기(동료)", fn, r[9], r[1], d or "같음"))
                break
    for x in ent:   # 동료 도움 → 루이스 알베르토 골
        if x[0] == "a" and norm(x[13] or "") in ME_NAMES:
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append(("동료 도움→LA 골", fn, x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:   # LA 도움 → 동료 골
        if r[0] == "a":
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and key(x[1]) == key(r[1]) and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            if hit: CROSS.append(("LA 도움→동료 골", fn, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:   # Transfermarkt LA 도움을 뺀 동료 골(참고)
        if x[0] == "g":
            tm = [e for e in EVENTS if e["la_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and key(G[e["gameId"]]["opponent"]) == key(x[1]) and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM LA 도움을 뺀 동료 골", fn, x[9], x[4], tm[0]["assist_type"]))
    for x in ent:   # 동료 골 중 LA 도움이 이 파일에 있으나 동료 쪽 행이 없음 → 위 'LA 도움→동료 골'로 확인
        pass
    for e in EVENTS:   # TM 동료 도움 → LA 골인데 동료 파일에 없음(참고)
        if e["la_scorer"] == "1" and e["gameId"] in G and e["assist_player"]:
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            mates = [x for x in ent if x[9] == d and key(x[1]) == key(G[e["gameId"]]["opponent"])]
            if mates and not any(x[0] == "a" and abs(x[4] - mi) <= 2 for x in mates):
                CROSS.append(("TM 동료 도움 → LA 골(동료 파일에 도움 없음, 참고)", fn, d, e["minute"], e["assist_player"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음" or c[0].startswith(("동료", "LA")): print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("sevla", "2013-07-01", "세비야", "2010~2012"), ("livla", "2014-07-01", "리버풀", "2013~2014"),
         ("malla", "2015-07-06", "말라가 (임대)", "2014~2015"), ("depla", "2016-07-01", "데포르티보 라코루냐 (임대)", "2015~2016"),
         ("lazla", "2024-07-01", "라치오", "2016~2024"), ("duhla", "2026-01-14", "알두하일", "2024~2026"), ("wakla", None, "알와크라", "2026~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
CLUB_KO.update({"malla": "말라가", "depla": "데포르티보"})
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TMC = {"368": "sevla", "31": "livla", "1084": "malla", "897": "depla", "398": "lazla", "26091": "duhla", "13509": "wakla"}
for g in GAMES:
    if club_of(ldate(g)) != TMC[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_luisalberto import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["la_assist_other"] == "1")
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const LAL_E={J(E)};\nconst LAL_M={J(M)};\nconst LAL_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
