#!/usr/bin/env python3
"""Bruno Fernandes: raw/ -> brunofernandes.json + src/data/brf.js (판정 근거는 judgments.md)

  python3 players/brunofernandes/build_brunofernandes.py            # 파일 쓰기
  python3 players/brunofernandes/build_brunofernandes.py --debug    # Elo 출처 로그
  python3 players/brunofernandes/build_brunofernandes.py --cross    # 다른 선수 자료 대조
  python3 players/brunofernandes/build_brunofernandes.py --fm       # FotMob 골 대조
  python3 players/brunofernandes/build_brunofernandes.py --check    # 쓰지 않고 점검만

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/*.js(같은 경기 다른 선수 자료 대조, 읽기만).
빌드 스크립트는 foden·sancho(players/foden/build_foden.py)를 바탕으로 함. 판정 표(대문자 상수)는 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, glob, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "brf.js")
OUT_JSON = os.path.join(HERE, "brunofernandes.json")
ME = "브루노 페르난데스"
GAP = "2014-08-01"   # 도움 출처 기준일: 전에는 Transfermarkt 단독 허용, 뒤에는 Transfermarkt∩FotMob 또는 독립 경기 기사 1곳 이상(반대 출처 없음, 사용자 결정 2026.11.12)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
# Transfermarkt 자책골(상대 선수)을 브루노 골로 고침: gameId|분 -> 이유
TM_OG_TO_GOAL = {
    "3174310|45": "2019.5.25 타사 드 포르투갈 결승 포르투전 45분: Transfermarkt는 다닐루 자책골(브루노 'Shot on goal'), FotMob·영어 위키백과·worldfootball·AFP(World Soccer Talk)·Portugoal·브라질 Gazeta/Lance는 브루노 골(다닐루 맞고 굴절). CM Jornal은 다닐루 자책골로 적음 -> 다수 출처대로 브루노 골",
}
# 2014.8.1 이후 Transfermarkt에만 있는 도움 중 독립 경기 기사 1곳 이상이 확인하고 반대 출처가 없어 넣은 것: gameId|분 -> 근거
ADD_CONFIRMED = {
    "2747453|71": "2016.11.30 칼리아리전(코파 이탈리아) 쉬크 골: 삼프도리아 공식 리포트('sent Patrick Schick clean through')·Unione Sarda/Blitz 기사(롱패스)",
    "2905731|60": "2017.8.23 FCSB전(챔스 예선) 아쿠냐 골: Vavel('outro excelente passe de Bruno Fernandes')·Sábado('novamente após passe de Bruno')",
    "2905731|64": "2017.8.23 FCSB전 젤송 마르팅스 골: fcupdate.nl 득점 목록('Gelson Martins (Bruno Fernandes) 64'')·Sábado 기사",
    "2883726|6": "2017.10.22 샤베스전 도스트 골: futbolfantasy 경기 기록('centro preciso de Bruno Fernandes')·Bola na Rede(도스트 최고 골 기사, 브루노 크로스)",
    "2883746|66": "2017.11.5 브라가전 도스트 골: footmercato/fichajes 득점 목록('Asist. Bruno Fernandes')·Portugoal 기사(니어포스트 패스)·Bola na Rede",
    "2941734|65": "2017.11.16 파말리캉전(타사 4라운드) 코아테스 골: Record 문자중계(브루노 코너)·Bola na Rede('dupla assistência')",
    "2941734|81": "2017.11.16 파말리캉전 도스트 골: Bola na Rede('brilhou com duas assistências')·Observador(교체 30분 만에 결정)",
    "2883782|60": "2017.12.17 포르티모넨스전 도스트 골: ontourfootball 득점 목록('B. Dost(Bruno Fernandes) 60'')·Sábado 기사(젤송 크로스를 브루노가 의도적으로 흘려 줌), sporteden. 다른 기사는 젤송 크로스로만 적음",
    "2883808|50": "2018.1.7 마리티무전 브라이언 루이스 골: 포르투갈 기사 2곳(Bola na Rede·Sapo 24 '브루노 패스')·Lance",
    "2883808|74": "2018.1.7 마리티무전 도스트 골: Portugoal('Fernandes's cutback was steered over the line by Dost')·Bola na Rede('mais uma assistência')",
    "2884490|20": "2018.4.8 파수스 드 페헤이라전 도스트 골: Observador(브루노 머리 도움)·Bola na Rede(루이스 크로스를 브루노가 니어포스트에서 흘려 줌)",
    "2884497|12": "2018.4.15 벨레넨스스전 도스트 골: LiveSoccerTV 득점 목록·Voetbal International 기사(브루노 정확한 패스)",
    "2884497|16": "2018.4.15 벨레넨스스전 젤송 골: LiveSoccerTV 득점 목록·futbolfantasy 경기 기록",
    "3130755|77": "2018.12.19 히우 아브전(타사 16강) 디아비 골: Bola na Rede('Bruno Fernandes isola Abdoulay Diaby')·Record 문자중계(78분, 브루노 도움)",
    "3093846|4": "2018.12.29 페이렌스전(타사 다 리가 조별) 하피냐 골: worldfootball 득점 목록·Record 문자중계(브루노 패스 뒤 왼발 슛)",
    "3255928|90+4": "2019.12.4 질 비센트전(타사 다 리가 조별) 비에투 골: Bola na Rede(브루노 도움)·Notícias ao Minuto 문자중계(브루노가 끌고 가 비에투에게 되돌려 줌)",
    "3255936|37": "2019.12.21 포르티모넨스전(타사 다 리가 조별) 비에투 헤더 골: Lusa 통신 기사(DN·Postal 재게재, 한 출처)가 '브루노 크로스를 머리로' — 반대 출처 없음 -> 사용자 결정(2026.11.12: 경기 기사 1곳 이상·반대 없음이면 넣음)으로 넣음",
    "3255936|84": "2019.12.21 포르티모넨스전(타사 다 리가 조별) 플라타 골: Observador(역습, 브루노 도움)·Notícias ao Minuto/DN(83분, 브루노 도움)",
    "3296895|44": "2020.1.21 브라가전(타사 다 리가 준결승) 마티외 골: worldfootball 득점 목록·Portugoal('quick free kick to the unmarked Mathieu')·Observador",
    "3912592|53": "2022.10.6 오모니아전(유로파 조별) 래시퍼드 골: Yahoo/Evening Standard 리포트('wonderful diagonal Bruno Fernandes pass')·90min 평점 기사('sensational pass up to Rashford')",
}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    "2359350|45": "2013.12.7 나폴리전 45분: Transfermarkt는 외르토 헤더 골(브루노 코너)이지만 FotMob·Fox Sports·Sportsmole·ESPN은 페데리코 페르난데스 자책골(외르토 헤더를 막다가) -> 상대 자책골에 준 도움",
    "3069566|80": "2019.1.30 세투발전 도스트 골: Transfermarkt 도움 유형 'Shot on goal'(슈팅 리바운드), FotMob 도움 없음",
    "2489320|20": "2014.12.3 체세나전(코파 이탈리아) 알란 골: FotMob 도움 없음, 기사(forzaitalianfootball·Sportsmole·FourFourTwo)는 알란 단독 드리블 골 -> 확인 실패",
    "2923635|81": "2017.12.20 우니앙 마데이라전(타사 다 리가) 이우리 메데이루스 골: 득점 목록(LiveSoccerTV·footballcritic)만 브루노 도움, 경기 기사(DN·Bola na Rede)는 도움을 적지 않음 -> 집계 사이트 외 확인 실패",
    "3421845|21": "2021.1.20 풀럼전 카바니 골: 브루노 크로스를 골키퍼 아레올라가 놓친 공을 카바니가 넣음(manutd.com·Sportsmole), 경기 기록 도움 0 -> 골키퍼가 흘린 공(리바운드 성격), FotMob 도움 없음",
}
# FotMob에만 있는 도움 중 넣은 것: gameId -> (분 문자열, 득점자, 근거)
FM_ONLY_ADD = {
    "3429739": ("57", "Daniel James", "2021.2.21 뉴캐슬전 제임스 골: FotMob·Sky Sports/Opta 문자중계('Assist - Bruno Fernandes')·worldfootball 득점 목록·Reuters 계열 기사('Fernandes's touch teed up Daniel James'). Transfermarkt는 마티치 도움"),
    "3429858": ("15", "Edinson Cavani", "2021.5.18 풀럼전 카바니 장거리 로브 골: FotMob·Reuters 기사('Bruno Fernandes flicked David De Gea's long ball')·beIN/BeSoccer 기사(브루노 뒤꿈치 연결). Transfermarkt는 데 헤아 도움"),
}
FM_ONLY_EXCL = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT2", "IT1", "PO1", "GB1", "POSB"}    # 세리에B 승격 플레이오프(POSB)는 리그 경기(판니스텔로이·카모라네시 선례)
CUP = {"CIT", "POPO", "FAC", "CGB"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round"): return "dk"
        return "dc"
    if cid == "POCP":   # 타사 다 리가: 조별은 리그식 국내컵(하피냐·팔카오 선례), 4강·결승
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("group"): return "dc"
    if cid in ("POSU", "GBCS"): return "df"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("intermediate") or r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
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
    if g["round"].lower().startswith("group"): return 0   # 챔스·유로파 조별/리그 페이즈, 타사 다 리가 조별
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local"]
    leg = 1 if "1st" in g["round"].lower() else 2
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        t = TIES_RAW[gid]
        oh, oa = map(int, t["other_leg_final"].split(":"))
        # other_leg_final은 이번 차전의 홈:원정 순서로 적혀 있음(2021.5.6 로마 2차전 '2:6' = 1차전 맨유 6-2 로마)
        if home: fu, ft = oh, oa
        else: fu, ft = oa, oh
    if cid in ("CL", "EL", "CLQ"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CIT":       # 코파 이탈리아 준결승: 2021-22까지 원정 다득점, 2차전 연장
        ag, et = int(d < "2022-07-01"), 1
    elif cid == "POPO":      # 타사 드 포르투갈 준결승: 원정 다득점·연장(2019 벤피카전은 원정 다득점으로 진출, 2018 포르투전 2차전 연장 120분)
        ag, et = 1, 1
    elif cid == "CGB":       # 잉글랜드 리그컵 준결승: 2018-19부터 원정 다득점·연장 없음
        ag = et = int(d < "2018-07-01")
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
    if "2020-07-01" <= d < "2020-09-01": return "2019-20"   # 코로나로 늦게 끝난 2019-20(2020.7~8 리그·FA컵·유로파)
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 리그 순위 -> Elo 고정값(기존 선수 자료 lv 문구에서 뽑은 같은 순위 값; 시즌 보정 없는 리그)
SA20 = {1: 1969, 2: 1890, 3: 1845, 4: 1814, 5: 1798, 6: 1787, 7: 1774, 8: 1757, 9: 1740, 10: 1725,
        11: 1714, 12: 1705, 13: 1697, 14: 1692, 15: 1683, 16: 1668, 17: 1651, 18: 1640, 19: 1632, 20: 1614}
PO18 = {1: 1912, 2: 1795, 3: 1730, 4: 1690, 5: 1670, 6: 1652, 7: 1627, 8: 1600, 9: 1576, 10: 1560,
        11: 1546, 12: 1533, 13: 1527, 14: 1507, 15: 1482, 16: 1461, 17: 1448, 18: 1421}
# 세리에B 22팀(2006-07·2011-12 기존 자료 값). 10위는 기존 값이 없어 9·11위 가운데(1577)
SB22 = {2: 1665, 3: 1641, 4: 1623, 5: 1614, 6: 1608, 7: 1602, 8: 1594, 9: 1585, 10: 1577, 11: 1569, 12: 1564,
        13: 1559, 14: 1555, 15: 1552, 16: 1549, 17: 1542, 18: 1534, 19: 1526, 20: 1521, 21: 1517, 22: 1507}
FIX = {"IT1": ("세리에A", SA20, 20), "PO1": ("포르투갈 1부", PO18, 18), "IT2": ("세리에B", SB22, 22)}
RANK_LG = ["IT2", "IT1", "PO1"]
def model(lg, season, r, n):
    nm, tab, nn = FIX[lg]
    if n == nn and r in tab:
        return tab[r], f"{nm} {season} {r}위"
    return None

from brunofernandes_elo import build as _build_man   # noqa  (같은 폴더: 직접 추정·순위 확인 값)
MAN = _build_man(key)

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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL", "CLQ") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    for s in seasons:
        for lg in RANK_LG:
            t = RANKS.get((lg, s))
            if t and k in t:
                r, n = t[k]
                res = model(lg, s, r, n)
                if res:
                    ELO_SRC["순위표+고정값"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model"))
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
        if r["brunofernandes_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))

# Transfermarkt 리포트 순서대로 누적 스코어(표시된 골 뒤 스코어는 2025.12.15 본머스전처럼 틀린 경우가 있어 쓰지 않음)
EV_BY_GAME = collections.defaultdict(list)
for e in EVENTS:
    EV_BY_GAME[e["gameId"]].append(e)
BEFORE = {}
for gid, evs in EV_BY_GAME.items():
    h = a = 0
    for i, e in enumerate(evs):
        BEFORE[(gid, i)] = (h, a)
        if e["side"] == "home": h += 1
        else: a += 1
    if gid in INFO and INFO[gid]["final"]:
        fh, fa = map(int, INFO[gid]["final"].split(":"))
        if (h, a) != (fh, fa) and INFO[gid]["result_flag"] not in ("pens", "AET", "on pens"):
            pass

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
used_add = set(); used_excl = set(); used_og = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, g):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    et = int(mi > 90 and not str(dm).startswith("90+") and g["gameState"] in ("extra_time", "penalty_shootout"))   # 연장 골(105+2 같은 연장 전반 추가시간 포함)
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for gid, evs in EV_BY_GAME.items():
    g = G.get(gid)
    if not g: continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    for i, e in enumerate(evs):
        tag = f"{gid}|{e['minute']}"
        isg = e["brunofernandes_scorer"] == "1"
        isa = e["brunofernandes_assist_other"] == "1"
        if tag in TM_OG_TO_GOAL:
            isg, isa = True, False; used_og.add(tag)
        if not (isg or isa): continue
        h, a = BEFORE[(gid, i)]
        ours = (e["side"] == "home") == our_home
        gf, ga = (h, a) if our_home else (a, h)
        mi, dm = minute(e["minute"])
        cid = g["competitionId"]
        comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
        d = ldate(g); opp = g["opponent"].strip()
        if isg:
            if not ours or (e["own_goal"] == "1" and tag not in TM_OG_TO_GOAL):
                judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
            add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, g)
            continue
        # 도움
        if tag in EXCL_A:
            used_excl.add(tag); judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "상대 자책골에 준 도움")); continue
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal"):
            sys.exit("도움 유형 판정 누락 " + tag)
        hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - mi) <= 2 or abs(t - int(e["minute"].split("+")[0])) <= 2]
        if hit:
            used_fm[gid] += 1
        elif d >= GAP:
            if tag in ADD_CONFIRMED:
                used_add.add(tag)
            else:
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag + " " + e["scorer"])
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, g)

# FotMob에만 있는 도움
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if len(ts) > used_fm.get(gid, 0):
        FM_ONLY.append((gid, G[gid]["date_local"] if gid in G else "?", ts))
if sorted(x[0] for x in FM_ONLY) != sorted(list(FM_ONLY_ADD) + list(FM_ONLY_EXCL)):
    sys.exit("FotMob 단독 도움 판정 누락 " + repr(FM_ONLY))
for gid, (ms, scorer, why) in FM_ONLY_ADD.items():
    g = G[gid]; evs = EV_BY_GAME[gid]; inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    idx = [i for i, e in enumerate(evs) if e["minute"] == ms]
    assert len(idx) == 1, gid
    e = evs[idx[0]]; h, a = BEFORE[(gid, idx[0])]
    assert (e["side"] == "home") == our_home and e["own_goal"] == "0"
    assert norm(e["scorer"]) == norm(scorer), (e["scorer"], scorer)
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(ms)
    add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie_of(g), comp_of(g["competitionId"], g["round"]), ko_of(g), ldate(g), g["opponent"].strip(), g["competitionId"], g)
    judg.append(("FotMob 단독 도움 넣음", ldate(g), g["opponent"], why))

for nm, s, u in (("ADD_CONFIRMED", ADD_CONFIRMED, used_add), ("EXCL_A", EXCL_A, used_excl), ("TM_OG_TO_GOAL", TM_OG_TO_GOAL, used_og)):
    if set(s) != u: sys.exit(f"{nm} 미사용 항목 {set(s) - u}")

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
for gid, evs in EV_BY_GAME.items():
    if gid not in G: continue
    tg = [e for e in evs if (e["brunofernandes_scorer"] == "1") or f"{gid}|{e['minute']}" in TM_OG_TO_GOAL]
    if not tg: continue
    if gid not in FM_EV:
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["brunofernandes_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(tg):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in tg], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(tg, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
        elif tm_min != fm_min:
            FM_CMP.append(("분 1 차이", gid, G[gid]["date_local"], t["minute"], f["time"], f["overloadTime"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
OTHER = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "brf.js"): continue
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const ([A-Z]+)_E=(\[.*?\]);\n", s, re.S)
    if m: OTHER[b] = json.loads(m.group(2))
CROSS = []
def cmp_rows(a, b, full=True):
    diffs = []
    if full and abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if full and (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb:
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
BRUNO_NAMES = {"bruno fernandes", "bruno miguel borges fernandes"}
for fn, ent in OTHER.items():
    for x in ent:
        same = [r for r in E if r[9] == x[9] and (key(r[1]) == key(x[1]) or _sub(key(r[1]), key(x[1])))]
        if not same: continue
        # 같은 경기: Elo·lv·대회·합산 비교(경기 단위)
        d = cmp_rows(same[0], x, full=False)
        if d: CROSS.append(("같은 경기 다름", fn, x[9], x[1], tuple(d)))
        # 다른 선수의 도움 -> 브루노 골
        if x[0] == "a" and norm(x[13] or "") in BRUNO_NAMES:
            hit = [r for r in same if r[0] == "g" and abs(r[4] - x[4]) <= 2]
            CROSS.append((fn + " 도움→브루노 골", x[9], x[4], "없음" if not hit else (tuple(cmp_rows(hit[0], x)) or "같음")))
    # 브루노 도움 -> 그 선수 골(득점자 이름이 그 파일 도움 대상인지 모르므로 같은 날·같은 분·스코어로 찾음)
    for r in E:
        if r[0] != "a": continue
        hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and (x[5], x[6]) == (r[5], r[6]) and (key(r[1]) == key(x[1]) or _sub(key(r[1]), key(x[1])))]
        if hit:
            CROSS.append((fn + " 골(브루노 도움 " + r[13] + ")", r[9], r[4], tuple(cmp_rows(r, hit[0])) or "같음"))
    # 브루노 골 -> 그 선수 도움 행
    for r in E:
        if r[0] != "g": continue
        hit = [x for x in ent if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and (key(r[1]) == key(x[1]) or _sub(key(r[1]), key(x[1])))]
        for x in hit:
            if norm(x[13] or "") not in BRUNO_NAMES:
                CROSS.append((fn + " 같은 분 도움 행(득점자 다름)", r[9], r[4], x[13], x[4], (x[5], x[6]), (r[5], r[6])))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0].split(" ")[0] + " " + " ".join(c[0].split(" ")[1:2]) for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("novbf", "2013-07-01", "노바라", "2012~2013"),
         ("udibf", "2016-08-16", "우디네세", "2013~2016"),
         ("sampbf", "2017-07-02", "삼프도리아", "2016~2017"),
         ("scpbf", "2020-01-29", "스포르팅", "2017~2020"),
         ("munbf", None, "맨체스터 유나이티드", "2020~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
CLUB_Y = {k: y for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TMC = {"6692": "novbf", "410": "udibf", "1038": "sampbf", "336": "scpbf", "985": "munbf"}
for g in GAMES:
    if club_of(ldate(g)) != TMC[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["brunofernandes_assist_other"] == "1")
N_PRE = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
N_BOTH = sum(used_fm.values())
FIRST, LAST = M[0], M[-1]
from brunofernandes_note import note_lines   # noqa  (같은 폴더)
NOTE = "\n".join(note_lines(globals()))
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
if __name__ == "__main__":
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const BRF_E={J(E)};\nconst BRF_M={J(M)};\nconst BRF_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("썼음:", OUT_JS)
