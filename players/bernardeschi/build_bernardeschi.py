#!/usr/bin/env python3
"""Federico Bernardeschi: raw/ -> bernardeschi.json + src/data/brd.js (판정 근거는 judgments.md)

  python3 players/bernardeschi/build_bernardeschi.py            # 파일 쓰기
  python3 players/bernardeschi/build_bernardeschi.py --debug    # Elo 출처 목록(빠진 Elo가 있어도 멈추지 않음)
  python3 players/bernardeschi/build_bernardeschi.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(출전 470경기), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv, raw/fotmob_playerMatches.csv, raw/ranks.txt(Transfermarkt 순위표),
      mls_overall_ranks.txt(인시녜 원자료의 FotMob MLS 서포터스 실드 전체 순위를 그대로 옮김),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료).
폴리타노(같은 수집 형식)·인시녜(토론토 FC) 빌드 스크립트와 같은 구조.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "brd.js")
OUT_JSON = os.path.join(HERE, "bernardeschi.json")
ME = "페데리코 베르나르데스키"
GAP = "2014-08-01"
CUTOFF = "2026-11-18"
CLUBS = collections.OrderedDict([("4083", "크로토네"), ("430", "피오렌티나"), ("506", "유벤투스"), ("11141", "토론토 FC"), ("1025", "볼로냐")])
TORONTO = "11141"

def rd(name, base=RAW):
    with open(os.path.join(base, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)
FM_PM = {}
for r in rd("fotmob_playerMatches.csv"):
    FM_PM[r["matchId"]] = r

# ---------------------------------------------------------------- 판정 표
EXCL_G = {}
# 도움 제외: gameId|분 -> 이유
EXCL_A = {
    "2981993|9": "PK 유도(2018.2.13 챔스 16강 1차전 토트넘전 이과인 PK 골, 'Penalty: Fouled player')",
    "3135814|86": "PK 유도(2019.3.12 챔스 16강 2차전 아틀레티코전 호날두 PK 골, 'Penalty: Fouled player')",
    "3289604|26": "PK 유도(2020.1.15 코파 이탈리아 16강 우디네세전 디발라 PK 골, 'Penalty: Fouled player')",
    "3614724|40": "슈팅 리바운드(2021.12.21 칼리아리전 킨 골, 'Shot on goal'; FotMob 도움 없음)",
    "3080904|75": "상대 자책골(2018.8.18 키에보전 바니 자책골, 코너킥; FotMob도 자책골·도움 없음)",
}
# 2014.8 이후 FotMob 경기 이벤트에는 도움자가 없지만 FotMob 선수 경기 기록(playerMatches)이 그 경기 도움 1개로 세고(호드리구 선례)
# 경기 기사도 확인한 Transfermarkt 도움: gameId|분 -> 근거
ADD_CONFIRMED = {
    "3651100|73": "2021.11.2 챔스 제니트전 73분 키에사 골: FotMob 선수 경기 기록 도움 1, Sports Mole 경기 기록(문자중계·선수 기록)이 베르나르데스키 도움(검색 요약 기준, 근거 약함)",
    "3846362|75": "2022.7.26 캐나디안 챔피언십 결승 밴쿠버전 75분 맥노턴 헤더: FotMob 선수 경기 기록 도움 1, MLS 공식·AFTN·World Football Index가 베르나르데스키 크로스",
    "4341557|80": "2024.5.21 캐나디안 챔피언십 8강 2차전 생로랑전 80분 오우수 골: FotMob 선수 경기 기록 도움 1, 캐나다 축구협회 경기 기록이 베르나르데스키 도움",
    "4366592|50": "2024.8.27 캐나디안 챔피언십 4강 2차전 포지전 50분 인시녜 골: FotMob 선수 경기 기록 도움 1, 토론토 FC 공식·CTV/캐나디안 프레스·캐나디안 프리미어리그 공식이 베르나르데스키 크로스",
}
ADD_FM = {}
# FotMob 단독 도움(넣지 않음): tm gameId -> 이유
FM_ONLY_EXCL = {
    "2492422": "2014.10.2 유로파 디나모 민스크전 33분 아퀼라니 골: FotMob만 베르나르데스키 도움. ESPN(PA) 경기 기사는 파스콸 크로스를 골키퍼가 놓치고 콘체보이가 걷어낸 공을 아퀼라니가 넣었다고 함 → 반대 출처",
    "2897184": "2017.9.9 키에보전 83분 디발라 골: FotMob만 베르나르데스키 도움(Transfermarkt 없음). Forza Italian Football은 '디발라가 베르나르데스키에게서 공을 가져가 두 명을 제친 뒤' 골이라 하고 통신 기사 1곳만 '베르나르데스키 패스' → 출처가 갈려 독립 출처 2곳 없음",
}
FM_ONLY_GOAL_EXCL = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "POSB", "MLS1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("CIT", "SCI", "CAN"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "USMX":
        return "lcg" if r.startswith("group") else "lck"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    cid = g["competitionId"]
    if cid in LEAGUE and cid != "POSB": return 0
    if cid == "USMX": return 1                      # 리그스컵 조별은 무승부면 승부차기(인시녜·메시 선례)
    if g["round"].lower().startswith("group"): return 0
    return 1

def ldate(g):
    return g["date_local_computed"]

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = ldate(g)
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    if cid in ("CL", "EL"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CIT":
        ag, et = int(d < "2022-07-01"), 1
    elif cid == "CAN":
        ag, et = 1, 0      # 캐나디안 챔피언십 2024: 원정 다득점, 연장 없이 승부차기(포지전 2-2 원정 다득점 진출)
    else:
        sys.exit("합산 규칙 없음 " + cid + " " + gid)
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
MANUAL_ALIAS = {"inter milan": "inter", "ac parma": "parma calcio 1913", "parma ac": "parma calcio 1913",
                "dc united": "d c united", "la galaxy": "los angeles galaxy", "atlanta united": "atlanta united fc",
                "vancouver whitecaps": "vancouver whitecaps fc", "red bull new york": "new york red bulls",
                "orlando city": "orlando city sc", "st louis city": "st louis city sc", "minnesota united": "minnesota united fc",
                "real salt lake": "real salt lake city", "houston dynamo": "houston dynamo fc"}
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

MLS_LIKE = {"MLS1", "CAN", "USMX"}
def season_eu(d):
    if "2020-07-01" <= d < "2020-09-01": return "2019-20"
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))
MLSR = collections.defaultdict(dict)   # 연도 -> {팀: (순위, 팀 수)}  FotMob 서포터스 실드 전체 순위(인시녜 원자료)
with open(os.path.join(HERE, "mls_overall_ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        MLSR[p[1]][key(p[4])] = (int(p[2]), int(p[3]))

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

def ents_map(pat_re):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile(pat_re)
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

SB_MEAN, SB_SD = 1577.78, 51.24

def model(lg, season, r, n):
    if lg == "IT2":
        m = ents_map(r"^세리에B " + re.escape(season) + r" (\d+)위$")
        if r in m: return m[r], f"세리에B {season} {r}위"
        return int(round(SB_MEAN + SB_SD * curve(r, n))), f"세리에B {season} {r}위"
    if lg == "MLS":
        m = ents_map(r"^MLS " + season + r" (\d+)위(?:/\d+팀)?$")
        lv = f"MLS {season} {r}위" + ("/28팀" if n == 28 else "")
        if r in m: return m[r], lv
        lo = max([k for k in m if k < r], default=None); hi = min([k for k in m if k > r], default=None)
        if lo and hi:   # 이웃 순위값의 단순 중간(병렬 판정 규칙)
            return int(round(m[lo] + (m[hi] - m[lo]) * (r - lo) / (hi - lo))), lv
    return None

# 순위표에 없는 상대(직접 지정): 모두 judgments.md에 근거
MAN = {
    (key("CF Os Belenenses"), "2015-16"): (1576, "포르투갈 1부 2015-16 9위"),   # 다른 선수 자료 포르투갈 1부 9위(2016-17~2019-20·2024-25) 1576과 같은 순위값
    (key("PAOK Thessaloniki"), "2016-17"): (1550, "그리스 2016-17 2위 (추정, 다른 선수 자료 그리스 2위 1550과 같음)"),
    (key("Red Bull Salzburg"), "2025-26"): (1534, "오스트리아 분데스리가 2025-26 3위 (추정, 다른 선수 자료 오스트리아 2019-20 3위 1534와 같음)"),
    (key("Inter Miami CF"), "2023"): (1515, "MLS 2023 27위 (다른 선수 자료 MLS 2024 27위/29팀 1515와 같음)"),
    (key("CS Saint-Laurent"), "2024"): (1150, "캐나다 3부(리그1 퀘벡, 세미프로) 2024 (추정, 다른 선수 자료 아마추어·세미프로 하부 리그 1150과 같음)"),
}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    seasons = [d[:4], eu] if cid in MLS_LIKE else [eu, d[:4]]
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    if cid in MLS_LIKE and k in MLSR.get(d[:4], {}):
        r, n = MLSR[d[:4]][k]
        res = model("MLS", d[:4], r, n)
        if res:
            ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model MLS"))
            return res
    t = RANKS.get(("IT2", eu))
    if t and k in t:
        r, n = t[k]; res = model("IT2", eu, r, n)
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model IT2"))
        return res
    return None

# ---------------------------------------------------------------- 출전
for g in GAMES:
    if g["date_local_tm_report"] and g["date_local_tm_report"] != g["date_local_computed"] and g["club_id"] != TORONTO:
        sys.exit("리포트 날짜와 계산 날짜 다름 " + g["gameId"])
    if not g["playedMinutes"]: sys.exit("출전 분 없음 " + g["gameId"])
    if g["club_id"] not in CLUBS: sys.exit("모르는 클럽 " + g["gameId"])

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
        if r["bernardeschi_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, d, cid)); res = (0, "?")
    elo, lv = res
    et = int(mi > 90 and not dm)   # 연장 시간(91~120분) 기록. 90+x 추가시간은 정규시간
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

def before(g, side_home, score_after):
    our_home = g["venue"] == "H"
    if g["gameId"] in INFO and (INFO[g["gameId"]]["home_id"] == g["club_id"]) != our_home: sys.exit("홈·원정 불일치 " + g["gameId"])
    h, a = map(int, score_after.split("-"))
    if side_home: h -= 1
    else: a -= 1
    return (h, a) if our_home else (a, h), side_home == our_home

used_excl = set(); used_add = set()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["bernardeschi_scorer"] == "1", e["bernardeschi_assist_other"] == "1", e["bernardeschi_self_assist"] == "1"
    if iss: judg.append(("본인 PK 골의 본인 도움(도움 아님)", ldate(g), g["opponent"], e["minute"]))
    if not (isg or isa): continue
    (gf, ga), ours = before(g, e["side"] == "home", e["score_home_away_after"])
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        if e["goal_desc"] == "Penalty rebound":
            judg.append(("PK 리바운드 골은 일반 골", d, opp, e["minute"]))
        add_row("g", mi, dm, gf, ga, int(e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        if tag in EXCL_A:
            used_excl.add(tag)
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal") or e["assist_type"].startswith("Handball"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP:
            if tag in ADD_CONFIRMED:
                used_add.add(tag)
                pm = FM_PM.get(g["fotmobMatchId"])
                if not pm or int(pm["assists"]) < 1: sys.exit("FotMob 선수 경기 기록 도움 없음 " + tag)
                judg.append(("도움 추가(FotMob 선수 경기 기록+기사)", d, opp, e["minute"], e["scorer"], ADD_CONFIRMED[tag]))
            elif not any(abs(t - mi) <= 3 for t in FM_ASSIST.get(gid, [])):
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)
if set(EXCL_A) - used_excl: sys.exit("쓰이지 않은 도움 제외 " + str(set(EXCL_A) - used_excl))
if set(ADD_CONFIRMED) - used_add: sys.exit("쓰이지 않은 도움 추가 " + str(set(ADD_CONFIRMED) - used_add))

for gid, evs in FM_EV.items():
    if gid not in G: continue
    for r in evs:
        t = int(r["time"]) + int(r["overloadTime"] or 0)
        if r["bernardeschi_assist"] == "1":
            tm = [e for e in EVENTS if e["gameId"] == gid and e["bernardeschi_assist_other"] == "1" and abs(minute(e["minute"])[0] - t) <= 3]
            if not tm and gid not in FM_ONLY_EXCL and gid not in ADD_FM:
                sys.exit(f"FotMob 단독 도움 판정 누락 {gid} {t}")
        if r["bernardeschi_scorer"] == "1" and r["pen_shootout_event"] != "True":
            tm = [e for e in EVENTS if e["gameId"] == gid and e["bernardeschi_scorer"] == "1" and abs(minute(e["minute"])[0] - t) <= 3]
            if not tm and gid not in FM_ONLY_GOAL_EXCL:
                sys.exit(f"FotMob 단독 골 판정 누락 {gid} {t}")

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

def sk(r):
    return (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1)
rows.sort(key=sk)
E = rows

if __name__ == "__main__" and "--debug" in sys.argv and "--fm" not in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["bernardeschi_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV: FM_CMP.append(("FotMob 경기 없음", gid)); continue
    fg = [r for r in FM_EV[gid] if r["bernardeschi_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty")
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], t["score_home_away_after"], f["newScore_home_away"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)
    sys.exit(0)

# ---------------------------------------------------------------- 시즌·클럽별
def season_calc(d, club):
    """계산기 시즌 구분: 토론토 FC는 달력 연도, 그 밖은 8월 1일 기준(2020년 8월은 2019-20)"""
    if club == TORONTO: return d[:4]
    y = int(d[:4])
    if "2020-08-01" <= d < "2020-09-01": return "2019-20"
    s = y if d[5:] >= "08-01" else y - 1
    return f"{s}-{str(s + 1)[2:]}"
CLUB_OF = {ldate(g): g["club_id"] for g in GAMES}
SEASONS = collections.OrderedDict()
for m in M:
    s = season_calc(m[0], CLUB_OF[m[0]]); SEASONS.setdefault(s, [0, 0, 0, 0]); SEASONS[s][0] += 1; SEASONS[s][3] += m[3]
for r in E:
    SEASONS[season_calc(r[9], CLUB_OF[r[9]])][1 if r[0] == "g" else 2] += 1
BYCLUB = collections.OrderedDict((c, [0, 0, 0, 0]) for c in CLUBS)
for m in M: BYCLUB[CLUB_OF[m[0]]][0] += 1; BYCLUB[CLUB_OF[m[0]]][3] += m[3]
for r in E: BYCLUB[CLUB_OF[r[9]]][1 if r[0] == "g" else 2] += 1

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
SRC = ELO_SRC
TM_API_A = sum(int(g["assists"] or 0) for g in GAMES)
last = M[-1]
bc = lambda c: "·".join(str(x) for x in BYCLUB[c][:3])
NOTE_LINES = [
    f"페데리코 베르나르데스키(크로토네·피오렌티나·유벤투스·토론토 FC·볼로냐)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 페스카라전 ~ {d_(last[0])} 파르마전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·인터내셔널 챔피언스컵·대표팀·유스(피오렌티나 프리마베라) 경기 제외",
    f"클럽별 경기·골·도움: 크로토네 {bc('4083')}, 피오렌티나 {bc('430')}, 유벤투스 {bc('506')}, 토론토 FC {bc('11141')}, 볼로냐 {bc('1025')}. 출전 분 합계 {MIN_TOT:,}분",
    "크로토네(2013-14 피오렌티나에서 임대)는 세리에B(2부, 프로 리그): 리그 38경기와 승격 플레이오프 예비 라운드 바리전(홈, 0-3 패) 1경기. 피오렌티나 프리마베라(유스) 39경기 23골과 2012-13 피오렌티나 1군 명단(출전 없음)은 넣지 않음. 토론토 FC는 2022.7 자유 이적부터 2025.5.24 경기까지, 볼로냐는 2025.7 자유 이적 뒤",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(출전 분이 빈 경기 없음, 90분으로 추정한 경기 없음), 골 시각·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부)이고 FotMob 경기 이벤트·선수 경기 기록과 대조함. 영어·이탈리아어 위키백과 클럽별 경기·골과 같음(영어 위키백과는 볼로냐 2026-27 리그 출전이 1경기 적음)",
    "날짜는 현지 날짜. 토론토 FC 저녁 경기 38경기는 Transfermarkt 리포트 날짜(중부 유럽 기준)보다 하루 앞인 경기장 현지 날짜를 씀",
    f"골: Transfermarkt 리포트 골 {NGo}개(선수 경기 성적·위키백과·FotMob과 같은 수). PK 골 {NPK}개는 골 유형 'Penalty' 기준(선수 경기 성적과 같음). 2024.5.4 FC 댈러스전 45+3분 골은 본인 PK가 막힌 뒤 리바운드를 넣은 것이라 일반 골로 셈. 실축 PK 5개(2017.4.22 인테르전, 2024.4.20 뉴잉글랜드전, 2024.5.4 댈러스전, 2024.6.19 내슈빌전, 2024.9.25 캐나디안 챔피언십 결승 밴쿠버전)는 기록에 넣지 않음",
    "골 시각은 Transfermarkt 리포트 분(FotMob과 1분 안팎 차이뿐이고 골 뒤 스코어는 모두 같음). 2017.1.11 코파 이탈리아 키에보전 PK 골은 Transfermarkt 90+2분(FotMob 90분)",
    f"도움: 2014.8.1 이전은 Transfermarkt 경기 리포트 도움, 이후는 Transfermarkt와 FotMob이 함께 센 것만 씀. 도움 {NA} = Transfermarkt {TM_API_A} − PK 유도 3(2018.2.13 챔스 토트넘전 이과인, 2019.3.12 챔스 아틀레티코전 호날두, 2020.1.15 코파 이탈리아 우디네세전 디발라) − 슈팅 리바운드 1(2021.12.21 칼리아리전 40분 킨, 'Shot on goal') − 상대 자책골에 준 도움 1(2018.8.18 키에보전 바니 자책골, 코너킥)",
    "본인 PK 골에 Transfermarkt 리포트가 본인 도움으로도 적은 2개(2017.1.11 코파 이탈리아 키에보전, 2022.8.31 LA 갤럭시전)는 도움으로 세지 않음(선수 경기 성적도 세지 않음)",
    f"2014.8.1 이전 도움 {PRE_A}개(모두 크로토네 2013-14 세리에B)는 FotMob에 그 시즌 도움 자료가 없어 Transfermarkt 단일 출처",
    "FotMob 경기 이벤트에는 도움자가 비었지만 FotMob 선수 경기 기록이 그 경기 도움 1개로 센 Transfermarkt 도움 4개는 Transfermarkt·FotMob이 함께 센 것으로 보고 넣음: 2021.11.2 챔스 제니트전 73분 키에사(유벤투스 공식·Cult of Calcio 기사는 도움자를 적지 않아 근거 약함), 2022.7.26 캐나디안 챔피언십 결승 밴쿠버전 75분 맥노턴 헤더(MLS 공식·AFTN 기사, 베르나르데스키 크로스), 2024.5.21 캐나디안 챔피언십 생로랑전 80분 오우수(캐나다 축구협회 경기 기록), 2024.8.27 캐나디안 챔피언십 포지전 50분 인시녜(토론토 FC 공식·캐나디안 프레스 기사, 베르나르데스키 크로스)",
    "FotMob에만 있는 도움 2개는 넣지 않음: 2014.10.2 유로파 디나모 민스크전 33분 아퀼라니 골(ESPN 기사는 파스콸 크로스를 걷어낸 공이라 함), 2017.9.9 키에보전 83분 디발라 골(기사가 '베르나르데스키 패스'와 '베르나르데스키에게서 공을 가져감'으로 갈림)",
    f"상대 Elo는 같은 경기 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 기존 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 지정 {SRC['직접 추정']})",
    "순위는 Transfermarkt 최종 순위표(세리에B 2013-14는 다른 선수 자료와 같은 세리에B 모형), MLS는 FotMob 서포터스 실드 전체 순위(인시녜 자료와 같음)를 다른 선수 자료의 같은 시즌 순위값에 넣고, 없는 순위는 이웃 순위값 사이로 맞춤(2022 밴쿠버 17위·뉴잉글랜드 20위·LA 갤럭시 8위·애틀랜타 23위, 2024 댈러스 19위·휴스턴 8위). 인터 마이애미 2023(29팀 중 27위)은 2024 27위/29팀 값",
    "직접 정한 값: 생로랑(캐나다 3부 리그1 퀘벡 세미프로, 2024 캐나디안 챔피언십 8강) 1150 추정, PAOK 2016-17(그리스 2위) 1550 추정, 잘츠부르크 2025-26(오스트리아 3위) 1534 추정, 벨레넨세스 2015-16(포르투갈 9위) 1576은 다른 시즌 포르투갈 9위 값",
    "대회 비중: 코파 이탈리아는 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), 수페르코파 이탈리아나(2025-26 4강·결승)는 국내컵 4강·결승, 캐나디안 챔피언십은 국내컵(8강·4강·결승), 리그스컵은 조별·토너먼트(조별도 무승부면 승부차기라 단판), 세리에B 승격 플레이오프는 리그 비중의 단판. 챔스 조별, 16강, 8강과 유로파 조별·리그 페이즈, 32강·녹아웃 플레이오프·16강·8강은 각 단계 비중",
    f"두 경기 합산(유럽 대항전 토너먼트, 코파 이탈리아 4강, 2024 캐나디안 챔피언십 8강·4강) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회는 2021-22부터, 코파 이탈리아는 2022-23부터 원정 다득점 없음. 캐나디안 챔피언십 2024는 원정 다득점이 있고 연장 없이 승부차기(포지전 합계 2-2에서 원정 다득점으로 진출). 2021.3.9 챔스 포르투전 117분 라비오 골 도움은 연장 시간 기록",
    "연장·승부차기 경기(2020.6.17 코파 이탈리아 결승, 2022.7.26·2024.9.25 캐나디안 챔피언십 결승, 2024.7.27 리그스컵 뉴욕 레드불스전, 2025.12.19 수페르코파 4강 인테르전, 2026.2.11 코파 이탈리아 8강 라치오전 등)는 Transfermarkt 출전 분을 그대로 쓰고 승부차기 골은 스코어에 넣지 않음",
    "시즌 구분: 토론토 FC는 MLS 달력 연도, 그 밖은 8월 1일 기준(코로나로 미뤄진 2020년 8월 유벤투스 경기는 2019-20)",
    "몰수·판정승으로 결과가 바뀐 경기는 없음",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 세리에A 우승 2017-18·2018-19·2019-20, 코파 이탈리아 우승 2017-18·2020-21, 수페르코파 이탈리아나 우승 2018-19·2020-21(모두 유벤투스). 프리마베라 득점왕(유스)·대표팀 우승(유로 2020)과 Transfermarkt 업적 페이지에 없는 준우승은 뺌. AIC(선수협회) 세리에A 올해의 팀·올해의 선수 명단에는 없음",
    f"2026.11.18 기준 현역(볼로냐). 마지막 반영 경기 {d_(last[0])} 파르마전(세리에A, 선발 {last[3]}분, 2026.11.18 수집)",
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
        if b[0] < a[0] or b[1] < a[1] or b[2] < a[2]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
    if len({(r[1], r[3]) for r in rs}) > 1: problems.append(("같은 날 상대·대회 다름", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
mm = {m[0]: m for m in M}
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r))
    if r[4] > mm[r[9]][3] + 100: problems.append(("분 이상", r))
for m in M:
    if m[3] < 1 or m[3] > 125: problems.append(("출전 분 범위", m))
    if m[0] > CUTOFF: problems.append(("기준일 뒤", m))
api_g = collections.Counter(); api_a = collections.Counter()
for g in GAMES:
    api_g[ldate(g)] += int(g["goals"] or 0); api_a[ldate(g)] += int(g["assists"] or 0)
gcount = collections.Counter(r[9] for r in E if r[0] == "g")
for d in set(api_g) | set(gcount):
    if api_g[d] != gcount[d]: problems.append(("골 수 API와 다름", d, api_g[d], gcount[d]))
api_pk = sum(int(g["penGoals"] or 0) for g in GAMES)
if api_pk != NPK: problems.append(("PK 골 수 API와 다름", api_pk, NPK))
acount = collections.Counter(r[9] for r in E if r[0] == "a")
A_DIFF = sorted((d, api_a[d], acount[d]) for d in set(api_a) | set(acount) if api_a[d] != acount[d])
if len(A_DIFF) != len(EXCL_A): problems.append(("도움 차이 날짜 수", len(A_DIFF), len(EXCL_A)))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const BRD_E={J(E)};\nconst BRD_M={J(M)};\nconst BRD_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg,
               "excluded_assists": EXCL_A, "added_assists_fotmob_playermatches": ADD_CONFIRMED,
               "fotmob_only_assists_excluded": FM_ONLY_EXCL, "fotmob_goal_diffs": FM_CMP,
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG, "seasons": SEASONS,
               "by_club": {CLUBS[c]: v for c, v in BYCLUB.items()}, "assist_count_vs_api": A_DIFF},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for c, v in BYCLUB.items(): print(" ", CLUBS[c], v)
    for k, v in SEASONS.items(): print(" ", k, v)
    print("도움 수 API와 다른 날:", A_DIFF)
