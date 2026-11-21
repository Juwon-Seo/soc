#!/usr/bin/env python3
"""Domenico Berardi: raw/ -> berardi.json + src/data/ber.js (판정 근거는 judgments.md)

  python3 players/berardi/build_berardi.py            # 파일 쓰기
  python3 players/berardi/build_berardi.py --debug    # Elo 출처 목록
  python3 players/berardi/build_berardi.py --fm       # FotMob 골 대조(2013-14 이후)

입력: raw/tm_games.csv(출전 436경기), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(Transfermarkt 순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다. 디 나탈레 빌드 스크립트와 같은 구조.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "ber.js")
OUT_JSON = os.path.join(HERE, "berardi.json")
ME = "도메니코 베라르디"
GAP = "2014-08-01"   # 도움 출처 기준일(이전 Transfermarkt, 이후 Transfermarkt∩FotMob 또는 다른 출처 2곳)
CUTOFF = "2026-11-18"

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
GOAL_MIN_FIX = {}
EXCL_G = {}

# 도움 제외(Transfermarkt 리포트·선수 경기 성적이 도움으로 셌지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    # 상대 자책골에 준 도움
    "2478866|50": "상대 자책골(2015.3.22 엠폴리전 루가니 자책골, 크로스)",
    "3433428|34": "상대 자책골(2021.3.3 나폴리전 막시모비치 자책골, 프리킥)",
    "4620930|45+1": "상대 자책골(2026.1.31 피사전 카라촐로 자책골, 'Shot on goal' — 슈팅이 상대 맞고 들어감)",
    # PK 유도(동료 PK 골)
    "2726817|74": "PK 유도(2017.5.7 피오렌티나전 폴리타노 PK 골, 'Penalty: Fouled player')",
    "3614807|29": "PK 유도(2022.3.6 베네치아전 스카마카 PK 골, 'Penalty: Fouled player')",
    # 2014.8.1 이후 Transfermarkt 단독(FotMob 도움 없음), 다른 출처 2곳이 확인하지 못함
    "2611210|67": "2014.8 이후 Transfermarkt 단독(2015.8.15 코파 이탈리아 모데나전 플로로 플로레스 골). Forza Italian Football 경기 기사는 교체로 들어온 플로로 플로레스의 로빙 슛만 적고 도움자를 적지 않음, 다른 기사 못 찾음",
    "2726835|7": "2014.8 이후 Transfermarkt 단독(2017.5.21 칼리아리전 마냐넬리 골). FotMob은 폴리타노 도움으로 적음. Sporting Life 중계(Opta 문자 중계)만 베라르디 코너킥 도움, Unione Sarda 기사는 코너킥 뒤 상황(센시의 흘림)만 적고 키커를 적지 않음 → 독립 출처 2곳 없음",
    "3089417|80": "2014.8 이후 Transfermarkt 단독(2018.8.12 코파 이탈리아 테르나나전 마냐넬리 골). il Resto del Carlino 기사는 마냐넬리 골만 적고 도움자 없음, 다른 기사 못 찾음",
    "3229204|50": "2014.8 이후 Transfermarkt 단독(2019.9.22 SPAL전 던컨 골). Forza Italian Football: 카푸토가 내준 공을 베라르디가 골키퍼 베리샤를 제치려다 공이 옆으로 흘렀고 던컨이 밀어 넣음 → 의도한 패스가 아닌 흘러나온 공",
    "3614595|17": "2014.8 이후 Transfermarkt 단독(2021.10.17 제노아전 스카마카 17분 골). calciomercato.com 평점 기사만 '도움'으로 적고, futbolfantasy 문자 중계는 골 직전 비라스키의 패스 차단을 적음(굴절 가능) → 독립 출처 2곳 없음",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움: gameId|분 -> 근거
ADD_CONFIRMED = {
    "2486232|12": "Sports Mole(자차가 베라르디 코너킥을 왼발 발리로)·FourFourTwo(베라르디 코너킥에서 자차 선제골)",
    "2486232|52": "Sports Mole(베라르디의 두 번째 도움, 산소네 골)·FourFourTwo(베라르디가 뒤에서 산소네에게 찔러 줌)",
    "2740236|41": "LaPresse(폴리타노와 원투 뒤 베라르디의 부드러운 패스)·Football Italia(베라르디와 원투로 골키퍼와 일대일)",
    "3614776|73": "Football Italia(트라오레가 베라르디 크로스를 가슴으로 받아 슈팅)·Tuttomercatoweb(베라르디가 연결)",
    "4385929|57": "Tuttomercatoweb 평점 기사(라우리엔테 슈팅에 베라르디 도움)·Yahoo 스포츠 문자 중계('Domenico Berardi with an assist there')",
    "4386312|24": "il Resto del Carlino(베라르디가 만들고 라우리엔테가 마무리)·Tuttomercatoweb(베라르디가 1-0 도움)",
    "4631308|32": "Corriere dello Sport 문자 중계(베라르디 스루패스 도움)·Fox Sports 경기 기록(베라르디 도움 1)",
}
# FotMob 단독 도움 중 다른 출처 2곳이 확인해 넣은 것: tm gameId -> (FotMob 분, 골 뒤 스코어(홈-원정), 득점자, 근거)
ADD_FM = {
    "3081132": (42, "0-1", "Federico Di Francesco",
                "LaPresse(보아텡에서 시작해 베라르디를 거쳐 디 프란체스코가 마무리)·Blitz quotidiano 경기 기록('베라르디가 디 프란체스코의 침투에 맞춰 줌')"),
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "CIT":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 1~4라운드·32강·16강
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    # UEFA 대회 2016-17: 원정 다득점·연장 모두 적용
    return [leg, home, fu, ft, 1, 1]

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
                "cesena fc": "ac cesena"}
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
    """상대 Elo 시즌: 7월 이후는 새 시즌(7월 유로파 예선), 다만 코로나로 미뤄진 2020년 7~8월 경기는 2019-20"""
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

# 세리에A 20팀 순위값(기존 자료) → 표준 곡선(디 나탈레·토티·델 피에로 스크립트와 같음)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

SB_MEAN, SB_SD = 1577.78, 51.24   # 세리에B(문서 4절)
C1_MEAN = 1416.56                 # 세리에C(3부): 인시녜·디 나탈레 자료와 같은 모형

def model(lg, season, r, n):
    if lg == "IT1":
        m = ents_map("세리에A", season)
        lab = f"세리에A {season} (11월 18일 현재) {r}위" if season == "2026-27" else f"세리에A {season} {r}위"
        if r in m: return m[r], lab
        assert n == 20, (season, n)
        return SA[r - 1], lab
    if lg == "IT2":
        m = ents_map("세리에B", season)
        if r in m: return m[r], f"세리에B {season} {r}위"
        return int(round(SB_MEAN + SB_SD * curve(r, n))), f"세리에B {season} {r}위"
    if lg == "IT3B":
        return int(round(C1_MEAN + SB_SD * curve(r, n))), f"세리에C B조 {season} {r}위/{n}팀 (추정)"
    return None

RANK_LG = ["IT1", "IT2", "IT3B"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {
    (key("FC Luzern"), "2016-17"): (1461, "스위스 슈퍼리그 2016-17 5위 (추정, 다른 선수 자료 스위스 슈퍼리그 2012-13 5위 1461과 같음)"),
    (key("Red Star Belgrade"), "2016-17"): (1500, "세르비아 2016-17 2위 (추정, 다른 선수 자료 츠르베나 즈베즈다 2위 1500과 같음)"),
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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    seasons = [eu]
    if (k, eu) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, eu)]).most_common(1)[0]
        ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + eu))
        return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
        return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, eu))
        if t and k in t:
            r, n = t[k]
            res = model(lg, eu, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg))
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_tm_report"] or g["date_local_computed"]
for g in GAMES:
    if g["date_local_tm_report"] and g["date_local_tm_report"] != g["date_local_computed"]:
        sys.exit("리포트 날짜와 계산 날짜 다름 " + g["gameId"])
    if not g["playedMinutes"]: sys.exit("출전 분 없음 " + g["gameId"])
    if g["club_id"] != "6574": sys.exit("사수올로가 아닌 경기 " + g["gameId"])

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
        if r["berardi_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, 0, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

def before(g, side_home, score_after):
    our_home = g["venue"] == "H"
    if g["gameId"] in INFO and (INFO[g["gameId"]]["home_id"] == g["club_id"]) != our_home: sys.exit("홈·원정 불일치 " + g["gameId"])
    h, a = map(int, score_after.split("-"))
    if side_home: h -= 1
    else: a -= 1
    return (h, a) if our_home else (a, h), side_home == our_home

used_excl, used_add = set(), set()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["berardi_scorer"] == "1", e["berardi_assist_other"] == "1", e["berardi_self_assist"] == "1"
    if iss: judg.append(("본인 PK 골의 본인 도움(도움 아님)", ldate(g), e["minute"]))
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
            if tag in ADD_CONFIRMED: used_add.add(tag)
            elif not any(abs(t - mi) <= 3 for t in FM_ASSIST.get(gid, [])):
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)
for nm_, s_, u_ in (("도움 제외", EXCL_A, used_excl), ("다른 출처 확인 도움", ADD_CONFIRMED, used_add)):
    if set(s_) - u_: sys.exit("쓰이지 않은 " + nm_ + " " + str(set(s_) - u_))

# FotMob 단독 도움(다른 출처 2곳 확인)
for gid, (fmin, after, scorer, why) in ADD_FM.items():
    g = G[gid]
    hit = [r for r in FM_EV[gid] if r["berardi_assist"] == "1" and int(r["time"]) == fmin and r["newScore_home_away"] == after]
    if len(hit) != 1: sys.exit("FotMob 단독 도움 이벤트 없음 " + gid)
    if any(e["gameId"] == gid and e["berardi_assist_other"] == "1" for e in EVENTS): sys.exit("TM에도 있는 도움 " + gid)
    (gf, ga), ours = before(g, hit[0]["isHome"] == "True", after)
    assert ours
    add_row("a", fmin, 0, gf, ga, 0, scorer, tie_of(g), comp_of(g["competitionId"], g["round"]), ko_of(g), ldate(g), g["opponent"].strip(), g["competitionId"])

# FotMob 단독 도움이 이것 말고 없는지(2013-14 이후)
for gid, evs in FM_EV.items():
    if gid not in G: continue
    for r in evs:
        if r["berardi_assist"] != "1": continue
        t = int(r["time"]) + int(r["overloadTime"] or 0)
        tm = [e for e in EVENTS if e["gameId"] == gid and e["berardi_assist_other"] == "1" and abs(minute(e["minute"])[0] - t) <= 3]
        if not tm and gid not in ADD_FM:
            # 2017.5.21 칼리아리전 7분: FotMob은 폴리타노 도움(베라르디 아님)이라 여기 오지 않음
            sys.exit(f"FotMob 단독 도움 판정 누락 {gid} {t}")

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

def sk(r):
    return (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1)
rows.sort(key=sk)
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["berardi_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV: continue
    fg = [r for r in FM_EV[gid] if r["berardi_scorer"] == "1" and r["pen_shootout_event"] != "True"]
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

# ---------------------------------------------------------------- 시즌
def season_calc(d):
    """계산기 시즌 구분(사수올로: 7월 10일 기준, 2020.7.1~8.31은 2019-20)"""
    y, m = int(d[:4]), int(d[5:7])
    if "2020-07-01" <= d < "2020-09-01": return "2019-20"
    s = y if d[5:] >= "07-10" else y - 1
    return f"{s}-{str(s + 1)[2:]}"
SEASONS = collections.OrderedDict()
for m in M:
    s = season_calc(m[0]); SEASONS.setdefault(s, [0, 0, 0, 0]); SEASONS[s][0] += 1; SEASONS[s][3] += m[3]
for r in E:
    SEASONS[season_calc(r[9])][1 if r[0] == "g" else 2] += 1

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
POST_A = NA - PRE_A
SRC = ELO_SRC
B1 = [len([m for m in M if m[0] < "2013-07-01"]), sum(1 for r in E if r[0] == "g" and r[9] < "2013-07-01"), sum(1 for r in E if r[0] == "a" and r[9] < "2013-07-01")]
B2 = [len([m for m in M if "2024-07-01" <= m[0] < "2025-07-01"]), sum(1 for r in E if r[0] == "g" and "2024-07-01" <= r[9] < "2025-07-01"), sum(1 for r in E if r[0] == "a" and "2024-07-01" <= r[9] < "2025-07-01")]
TM_API_A = sum(int(g["assists"] or 0) for g in GAMES)
last = M[-1]
NOTE_LINES = [
    f"도메니코 베라르디(사수올로)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 아벨리노전 ~ {d_(last[0])} 피오렌티나전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·대표팀(이탈리아·청소년 대표)·유스(사수올로 프리마베라) 경기 제외",
    f"클럽별 경기·골·도움: 사수올로 {NG}·{NGo}·{NA}(세리에B 2012-13 {B1[0]}·{B1[1]}·{B1[2]}, 세리에B 2024-25 {B2[0]}·{B2[1]}·{B2[2]} 포함). 출전 분 합계 {MIN_TOT:,}분",
    "성인 클럽은 사수올로 하나뿐. 2013.9.1~2015.6.30에는 유벤투스가 공동 소유권을 사서 사수올로로 임대한 형태였으나 유벤투스 공식 경기는 0경기(Transfermarkt 이적 기록·FotMob·위키백과 일치)라 따로 나누지 않음. 세리에B 두 시즌(2012-13 우승 승격, 2024-25 우승 승격)은 이탈리아 2부 프로 리그라 셈",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(출전 분이 빈 경기 없음, 90분으로 추정한 경기 없음), 골 시각·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부), 2013-14 이후 골·도움은 FotMob 경기 이벤트와 대조함(FotMob은 2012-13 세리에B 도움 자료가 없음). 위키백과(영어·이탈리아어) 시즌별 경기·골과도 대조함(영어 433경기·이탈리아어 435경기는 최근 시즌 갱신이 늦은 차이)",
    "날짜는 현지(이탈리아) 날짜. 유로파리그 예선 원정(루체른·베오그라드)도 같은 시간대",
    f"골: Transfermarkt 리포트 골 {NGo}개를 그대로 씀(선수 경기 성적·FotMob과 같은 경기·같은 수). PK 골 {NPK}개는 골 유형 'Penalty' 기준(FotMob도 같은 {NPK}개). 2026.2.20 베로나전 44분 골은 PK가 몬티포에게 막힌 뒤 리바운드로 넣은 골('Penalty rebound')이라 일반 골로 셈. 실축 PK 9개(그 경기 포함)는 기록에 넣지 않음",
    "골 시각은 Transfermarkt 리포트 분(FotMob과 1분 안팎 차이 또는 추가시간을 '90'으로만 적은 차이뿐, 골 뒤 스코어는 모두 같음)",
    f"도움: 2014.8.1 이전은 Transfermarkt 경기 리포트 도움, 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것과 다른 출처 2곳이 확인한 것만 씀. 도움 {NA} = Transfermarkt {TM_API_A} − 상대 자책골에 준 도움 3(2015.3.22 엠폴리전 루가니, 2021.3.3 나폴리전 막시모비치, 2026.1.31 피사전 카라촐로 — 피사전은 슈팅이 상대 맞고 들어간 것) − PK 유도 2(2017.5.7 피오렌티나전 폴리타노, 2022.3.6 베네치아전 스카마카 PK 골) − 2014.8 이후 Transfermarkt 단독으로 다른 출처 2곳이 확인하지 못한 5 + FotMob 단독이지만 다른 출처 2곳이 확인한 1",
    "Transfermarkt 리포트가 본인 PK 골에 본인 도움(PK 유도)으로 적은 15개는 도움으로 세지 않음(선수 경기 성적도 세지 않음)",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처. 그중 2012-13 세리에B 6개(2012.9.1 크로토네전 파볼레티, 10.14 바레세전 가촐라, 10.30 테르나나전 파볼레티, 2013.3.9 바레세전 마수치, 4.20 바리전 파볼레티·테라노바)는 FotMob에 그 시즌 도움 자료가 아예 없어 Transfermarkt만 근거이고, 2014.2.2 베로나전 90+2분 플로로 플로레스 골 도움도 FotMob에 없음",
    f"2014.8.1 이후 도움 {POST_A}개 중 {POST_A - len(ADD_CONFIRMED) - len(ADD_FM)}개는 Transfermarkt와 FotMob이 함께 적은 것. FotMob에 없지만 다른 출처 2곳이 확인해 넣은 {len(ADD_CONFIRMED)}개: 2014.8.21 코파 이탈리아 치타델라전 자차 12분·산소네 52분(Sports Mole·FourFourTwo), 2016.8.18 유로파리그 예선 츠르베나 즈베즈다전 41분 폴리타노(LaPresse·Football Italia), 2022.2.13 로마전 73분 트라오레(Football Italia·Tuttomercatoweb), 2024.11.9 쥐트티롤전 57분 라우리엔테(Tuttomercatoweb·Yahoo 문자 중계), 2025.4.25 체세나전 24분 라우리엔테(il Resto del Carlino·Tuttomercatoweb), 2025.8.15 코파 이탈리아 카탄차로전 32분 도이그(Corriere dello Sport 문자 중계·Fox Sports)",
    "FotMob에만 있는 도움 1개는 다른 출처 2곳이 확인해 넣음: 2018.11.4 키에보전 42분 페데리코 디 프란체스코 골(LaPresse·Blitz quotidiano, Transfermarkt는 도움 없음)",
    "다른 출처 2곳이 확인하지 못해 뺀 Transfermarkt 단독 도움 5개: 2015.8.15 코파 이탈리아 모데나전 67분 플로로 플로레스(경기 기사에 도움자 없음), 2017.5.21 칼리아리전 7분 마냐넬리(코너킥 뒤 골, FotMob은 폴리타노 도움, Opta 문자 중계만 베라르디), 2018.8.12 코파 이탈리아 테르나나전 80분 마냐넬리(기사에 도움자 없음), 2019.9.22 SPAL전 50분 던컨(베라르디가 골키퍼를 제치려다 흘러나온 공을 던컨이 밀어 넣음 — 흘러나온 공이라 도움 아님), 2021.10.17 제노아전 17분 스카마카(평점 기사 한 곳만 도움, 문자 중계는 골 직전 상대 차단 기록)",
    f"상대 Elo는 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위를 기존 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "순위는 Transfermarkt 최종 순위표(세리에A·B·C). 세리에A 2026-27은 진행 중이라 2026.11.18 현재 순위(토리노 11위). 세리에B는 다른 선수 자료와 같은 리그 모형(평균 약 1578, 22팀 시즌 2012-13·20팀 시즌 2024-25), 세리에C(3부, 2018-19 B조 테르나나 11위/20팀)는 다른 선수 자료와 같은 추정 모형(평균 약 1417)으로 '추정'",
    "직접 추정(모두 '추정'): 루체른 2016-17(스위스 5위) 1461(다른 선수 자료 스위스 슈퍼리그 5위 값), 츠르베나 즈베즈다 2016-17(세르비아 2위) 1500(다른 선수 자료의 같은 팀 2위 값). 유로파리그 예선 상대는 경기가 열린 시즌(2016-17)의 최종 순위로 봄",
    "대회 비중: 코파 이탈리아는 국내컵(1~4라운드·32강·16강은 낮은 비중, 8강 이후 높은 비중), 유로파리그 3차 예선·플레이오프는 유로파 예선. 2016-17 유로파리그 조별 6경기는 부상으로 결장",
    f"두 경기 합산(2016-17 유로파리그 3차 예선 루체른 1-1·3-0, 플레이오프 츠르베나 즈베즈다 3-0·1-1) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 적용). 코파 이탈리아는 모두 단판. 승부차기 경기(2023.11.2 스페치아전, 2026.9.2 프로시노네전)는 승부차기 골을 스코어에 넣지 않음(베라르디 골·도움 없음)",
    "시즌 구분: 7월 10일 기준(2016.7.28 유로파리그 예선 루체른 원정은 2016-17), 코로나로 미뤄진 2020년 7~8월 세리에A 경기는 2019-20",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 세리에B 우승 2012-13·2024-25, AIC(이탈리아 선수협회) 세리에B 올해의 선수 2012-13(영어 위키백과 AIC Serie B Footballer of the Year 명단과 대조). Transfermarkt의 2012-13 '올해의 공격수'(포지션별 상)·승격 표기와 유로 2020 우승·U21 대회 등 대표팀 기록은 뺌. AIC 세리에A 올해의 팀 명단에는 없음",
    f"2026.11.18 기준 현역(사수올로). 마지막 반영 경기 {d_(last[0])} 피오렌티나전(세리에A, {last[3]}분), 2026.11.7 경기는 부상으로 결장(2026.11.18 수집)",
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
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
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
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const BER_E={J(E)};\nconst BER_M={J(M)};\nconst BER_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG, "seasons": SEASONS,
               "assist_count_vs_api": A_DIFF},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in SEASONS.items(): print(" ", k, v)
    print("도움 수 API와 다른 날:", A_DIFF)
