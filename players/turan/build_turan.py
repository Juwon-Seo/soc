#!/usr/bin/env python3
"""Arda Turan: raw/ -> turan.json + src/data/tur.js (판정 근거는 judgments.md)

  python3 players/turan/build_turan.py            # 파일 쓰기
  python3 players/turan/build_turan.py --debug    # Elo 출처 로그·판정 목록
  python3 players/turan/build_turan.py --cross    # 동료 자료 대조
  python3 players/turan/build_turan.py --fm       # FotMob 골·도움 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료; ents.json은 `npm run elo`로 만듦),
      src/data/{fal,grz,tor,vil,mes,ney,sua,ini,rib}.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "tur.js")
OUT_JSON = os.path.join(HERE, "turan.json")
ME = "아르다 투란"
NAME = "Arda Turan"
GAP = "2014-08-01"   # 이 날 뒤 도움은 Transfermarkt + FotMob 일치(또는 다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 범위
# 모든 소속 팀-시즌이 1부(쉬페르리그·라리가) 프로 리그 → 제외 없음. 대표팀·2군 자료는 tm_games.csv에 없음.
GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
OTHER = {}
for r in rd("tm_two_leg_ties.csv"):
    OTHER[r["gameId"]] = r["other_leg_id"]; OTHER.setdefault(r["other_leg_id"], r["gameId"])
for gid, r in INFO.items():
    if r["other_leg_id"]:
        OTHER.setdefault(gid, r["other_leg_id"]); OTHER.setdefault(r["other_leg_id"], gid)
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
# 916155(2008.11.2 가지안테프스포르전) 39분 'Handball by Arda Turan' = 투란이 내준 PK(상대 골) → 도움 아님
NOT_ASSIST = {"916155|39": "상대 PK 골의 핸드볼 반칙(도움 아님)"}
# 2014.8 이후 Transfermarkt 도움 중 FotMob 경기 이벤트에 도움 이름이 없는 것 → 다른 출처 2곳으로 확인한 것만 넣음
ADD_CONFIRMED = {}
EXCL_A = {
    # 2016.12.21 에르쿨레스전(코파 델 레이 32강 1차전) 50분 하피냐 골: Transfermarkt만 투란 도움, FotMob 도움 이름 없음.
    # 다른 독립 출처 2곳에서 확인하지 못해 넣지 않음(judgments.md 4절).
    "2767530|50": "2014.8 이후 Transfermarkt 단독 도움(다른 출처 2곳 확인 못 함)",
}
# 963458(2009.8.31 앙카라스포르–갈라타사라이): 경기는 끝까지 치러졌고(0-2, 74분 큐얼 0-1·83분 논다 0-2) 뒤에 앙카라스포르가
# 리그에서 제외되면서 0-3 몰수로 기록됨 → 실제로 뛴 90분과 실제 경기 중 스코어(골 전 0-0)를 씀(드록바 2013 베식타시전 선례).

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"TR1", "ES1"}
CUP = {"TRP", "CDR"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 튀르키예컵 3·5라운드·예선 라운드·조별·16강, 코파 델 레이 4라운드·32강(intermediate stage)·16강
    if cid in ("USC", "SUC"): return "df"   # UEFA 슈퍼컵·수페르코파 = 국내컵 결승
    if cid in ("CLQ",): return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid == "UEFA" and r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
    if cid in ("UEFA", "EL"):
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # UEFA컵 3라운드(32강)·유로파 2라운드(32강)·intermediate stage·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return g["gameId"] in OTHER

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스·UEFA컵·유로파 조별, 튀르키예컵 조별(리그식)
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local"]
    o = INFO[OTHER[gid]]
    leg = 2 if o["date_report"] < inf["date_report"] else 1
    rl = g["round"].lower()
    if ("1st" in rl and leg != 1) or ("2nd" in rl and leg != 2): sys.exit("차전 순서 이상 " + gid)
    home = int(inf["home_id"] == g["club_id"])
    if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    fu = ft = 0
    if leg == 2:
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "CLQ", "UEFA", "EL", "ELQ"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid in ("CDR", "SUC"):   # 스페인 국내 대회: 원정 다득점(2018-19까지)·연장
        ag, et = int(d < "2019-07-01"), 1
    elif cid == "TRP":           # 튀르키예컵: 2020-21까지 원정 다득점·연장
        ag, et = int(d < "2021-07-01"), 1
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
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 리그 모형(기존 선수 자료와 같은 곡선)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
# 쉬페르리그: 평균 = 1473 + 23.33 × (앞뒤 3시즌 튀르키예 UEFA 국가 계수 평균 − 7.333), 흩어짐 119(팔카오·포돌스키·외질 자료와 같은 공식)
# 계수(시즌 시작 연도): 영어 위키백과 'Turkish football clubs in European competitions' 시즌별 계수. 2009~2021은 기존 선수 자료 값과 같음.
TR_COEF = {2003: 4.290, 2004: 3.547, 2005: 2.640, 2006: 4.026, 2007: 9.750, 2008: 7.000, 2009: 7.6, 2010: 4.6, 2011: 5.1,
           2016: 6.8, 2017: 6.8, 2018: 5.5, 2019: 5.0, 2020: 3.1, 2021: 6.7, 2022: 11.8}
# 기존 선수 자료의 쉬페르리그 순위값(같은 시즌 같은 순위는 그 값을 씀)
EX_TR = collections.defaultdict(dict)
for x in ENTS:
    m = re.match(r"쉬페르리그 (\d{4}-\d\d) (\d+)위( \(추정, 2016-17 리그 수준 사용\)| \(추정\))?$", x["lv"])
    if m: EX_TR[m.group(1)][int(m.group(2))] = x["elo"]
def tr_mean(season):
    """기존 자료에 그 시즌 1위 값이 있으면 거기서 거꾸로 구한 평균(포돌스키 자료 방식), 없으면 계수 공식"""
    if 1 in EX_TR.get(season, {}):
        return EX_TR[season][1] - 119 * curve(1, 18)
    s = int(season[:4])
    c = sum(TR_COEF[y] for y in (s - 1, s, s + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)

def model(lg, season, r, n):
    if lg == "TR1":
        t = EX_TR.get(season, {})
        if r in t: return t[r], f"쉬페르리그 {season} {r}위"
        lo = [k for k in t if k < r]; hi = [k for k in t if k > r]
        if lo and hi:   # 같은 시즌 기존 순위값 사이: 가운데(직선) 값(병렬 판정 규칙)
            a, b = max(lo), min(hi)
            return round(t[a] + (t[b] - t[a]) * (r - a) / (b - a)), f"쉬페르리그 {season} {r}위 (추정, 다른 선수 자료 {a}위 {t[a]}·{b}위 {t[b]} 사이)"
        return round(tr_mean(season) + 119 * curve(r, n)), f"쉬페르리그 {season} {r}위"
    if lg == "TR2":
        return round(tr_mean(season) - 162 + SD2 * curve(r, n)), f"튀르키예 2부 {season} {r}위 (추정, 쉬페르리그 평균 − 독일 1·2부 평균 차)"
    if lg == "TR3A":
        return round(tr_mean(season) - 324 + SD2 * curve(r, n)), f"튀르키예 3부 {season} 백색조 {r}위/{n}팀 (추정, 쉬페르리그 평균 − 2×독일 1·2부 평균 차)"
    return None
RANK_LG = ["TR1", "TR2", "TR3A"]

# 직접 추정(모두 '추정') — 순위표·모형·다른 선수 자료로 안 되는 상대
MAN = {
    (key("FK Mlada Boleslav"), "2006-07"): (1475, "체코 2006-07 3위 (추정, 다른 선수 자료 체코 2006-07 2위 1488·4위 1462의 가운데)"),
    (key("FC Sion"), "2007-08"): (1406, "스위스 2007-08 7위/10팀 (추정, 다른 선수 자료의 스위스 7위 1406과 같음)"),
    (key("Helsingborgs IF"), "2007-08"): (1377, "스웨덴 2007 8위/14팀 (추정, 다른 선수 자료 스웨덴 7위 1390·10위 1350 사이 직선)"),
    (key("SL Benfica"), "2008-09"): (1733, "포르투갈 1부 2008-09 3위/16팀 (추정, 다른 선수 자료 16팀 시즌 2위 1786·4위 1679의 가운데)"),
    (key("Tobol Kostanay"), "2009-10"): (1300, "카자흐스탄 2009 4위 (추정, 다른 선수 자료 악퇴베 2009 1위 1350보다 낮게)"),
    (key("Maccabi Netanya"), "2009-10"): (1420, "이스라엘 2009-10 9위/16팀 (추정, 다른 선수 자료 이스라엘 8위 1425보다 조금 낮게)"),
    (key("OFK Beograd"), "2010-11"): (1400, "세르비아 2010-11 7위/16팀 (추정, 다른 선수 자료 세르비아 1위 1520·중위권 1300 사이)"),
    (key("St. Johnstone FC"), "2021-22"): (1380, "스코틀랜드 2021-22 11위/12팀 (추정, 다른 선수 자료 하츠 중위권 1450보다 낮게)"),
    (key("Hércules CF"), "2016-17"): (1350, "스페인 3부(세군다 B) 2016-17 3조 7위 (추정, 다른 선수 자료 스페인 3부 1350과 같음)"),
}
# 앙카라스포르 2009-10: 2009.11 튀르키예 축구협회가 리그에서 제외(남은 경기·치른 경기 모두 0-3 몰수), Transfermarkt 표 18위 → 18위 값에 설명
LV_FIX = {(key("Ankaraspor"), "2009-10"): " (리그에서 제외돼 전 경기 0-3 몰수, 순위는 최하위)"}

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
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "CLQ", "UEFA", "EL", "ELQ", "USC") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, eu))
        if t and k in t:
            r, n = t[k]
            res = model(lg, eu, r, n)
            if res:
                e, lv = res
                lv += LV_FIX.get((k, eu), "")
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, e, lv, "model " + lg, []))
                return e, lv
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local"]   # Transfermarkt 리포트 날짜(유럽·튀르키예 현지; 리포트 없는 리그 경기는 일정 페이지 날짜)

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def fm_has_assist(gid, gf_after_home, gf_after_away):
    for r in FM_EV.get(gid, []):
        if r["turan_assist"] == "1" and r["newScore_home_away"] == f"{gf_after_home}-{gf_after_away}":
            return True
    return False

rows, judg = [], []
missing_elo = set()
EXCL_CNT = collections.Counter()
FM_A = []   # 2014.8 이후 도움 FotMob 대조
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et=0):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid, d)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

ET_GAMES = {g["gameId"] for g in GAMES if g["gameState"] in ("extra_time", "penalty_shootout") and g["gameDuration"] == "120"}
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["turan_scorer"] == "1", e["turan_assist_other"] == "1"
    if e["turan_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag)); EXCL_CNT["본인 도움"] += 1
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    hb, ab = (h - 1, a) if side_home else (h, a - 1)
    ours = side_home == our_home
    gf, ga = (hb, ab) if our_home else (ab, hb)
    mi, dm = minute(e["minute"])
    et = int(gid in ET_GAMES and "+" not in e["minute"] and mi > 90)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        why = None
        if tag in NOT_ASSIST: why = NOT_ASSIST[tag]
        elif e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            EXCL_CNT[why if tag not in EXCL_A else "개별 판정"] += 1
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], e["assist_type"], why)); continue
        if d >= GAP:
            ok = fm_has_assist(gid, h, a)
            FM_A.append((d, opp, e["minute"], e["scorer"], "FotMob 일치" if ok else ("다른 출처 확인" if tag in ADD_CONFIRMED else "없음")))
            if not ok and tag not in ADD_CONFIRMED:
                sys.exit("2014.8 이후 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[3]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[5] + r[6], 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, EXCL_CNT)
    for x in ELO_LOG: print(x)
    for j in judg: print(j)
    for x in FM_A: print(x)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["turan_scorer"] == "1" and e["gameId"] in G and G[e["gameId"]]["date_local"] >= "2010-07-01":
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid) or not any(r["scorer"] for r in FM_EV[gid]):
        FM_CMP.append(("FotMob 자료 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["turan_scorer"] == "1" and r["pen_shootout_event"] != "True"]
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
    for x in FM_A: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P, part="E"):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + "_" + part + r"=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
ATM = ("2011-08-26", "2015-07-06"); BAR = ("2015-07-06", "2018-01-15"); GAL1 = ("2004-07-01", "2011-08-26"); GAL2 = ("2020-08-05", "2022-07-01")
MATES = {"Radamel Falcao": ("fal.js", "FAL", [ATM, GAL2]), "Antoine Griezmann": ("grz.js", "GRZ", [ATM]),
         "Fernando Torres": ("tor.js", "TOR", [ATM]), "David Villa": ("vil.js", "VIL", [ATM]),
         "Lionel Messi": ("mes.js", "MES", [BAR]), "Neymar": ("ney.js", "NEY", [BAR]),
         "Luis Suárez": ("sua.js", "SUA", [BAR]), "Andrés Iniesta": ("ini.js", "INI", [BAR]),
         "Franck Ribéry": ("rib.js", "RIB", [GAL1])}
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
IS_ME = lambda s: norm(s or "") == norm(NAME)
def in_per(d, pers): return any(lo <= d < hi for lo, hi in pers)
for nm, ent in MATE_E.items():
    pers = MATES[nm][2]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("투란 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and IS_ME(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→투란 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if in_per(x[9], pers):
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if dd: CROSS.append(("같은 경기 다름", nm, r[9], r[1], dd))
                    break
    for x in ent:   # Transfermarkt 투란 도움을 이 계산기에서 뺀 동료 골(참고)
        if x[0] == "g" and in_per(x[9], pers):
            tm = [e for e in EVENTS if e["turan_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 투란 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"], x[13]))
            if x[13] and IS_ME(x[13]): pass
    for e in EVENTS:   # 동료 파일에서 투란 골의 도움으로 적혔어야 할 것(TM 리포트 기준, 참고)
        if e["turan_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 투란 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
    for r in E:      # 투란 도움 → 동료 골인데 동료 파일에서 도움자가 다르거나 없음
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3]
            if not hit: CROSS.append(("투란 도움 동료 골이 동료 파일에 없음", nm, r[9], r[4]))
MATE_M = {nm: load_js(v[0], v[1], "M") for nm, v in MATES.items()}
for nm, mm in MATE_M.items():
    for x in mm:
        for m in M:
            if m[0] == x[0] and key(m[1]) == key(x[1]) and m[2] != x[2]:
                CROSS.append(("같은 경기 대회 코드 다름(출전)", nm, m[0], m[1], m[2], x[2]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("galar", "2006-01-09", "갈라타사라이", "2004~2006"), ("manar", "2006-07-01", "마니사스포르", "2006"),
         ("galar", "2011-08-26", "갈라타사라이", "2006~2011"), ("atmar", "2015-07-06", "아틀레티코 마드리드", "2011~2015"),
         ("barar", "2018-01-15", "바르셀로나", "2015~2018"), ("ibfar", "2020-08-05", "이스탄불 바샥셰히르", "2018~2020"),
         ("galar", None, "갈라타사라이", "2020~2022")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {"galar": "갈라타사라이", "manar": "마니사스포르", "atmar": "아틀레티코 마드리드", "barar": "바르셀로나", "ibfar": "이스탄불 바샥셰히르"}
# 클럽별 표(갈라타사라이는 기간 셋을 따로 집계해 설명에 씀)
SPELL = lambda d: next(i for i, (k, u, _, _) in enumerate(CLUBS) if u is None or d < u)
ST = collections.OrderedDict((i, [0, 0, 0, 0]) for i in range(len(CLUBS)))
for m in M: ST[SPELL(m[0])][0] += 1; ST[SPELL(m[0])][3] += m[3]
for r in E: ST[SPELL(r[9])][1 if r[0] == "g" else 2] += 1
TMC = {"141": "galar", "1267": "manar", "13": "atmar", "131": "barar", "6890": "ibfar"}
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
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["turan_assist_other"] == "1")
def exl(kind):
    return [j for j in judg if j[0] == "도움 제외" and j[-1] == kind]
def lst(js): return ", ".join(f"{d_(j[1])} {OPPKO.get(j[2], j[2])}전 {j[4]}" for j in js)
OPPKO = {}
PKW, SOG, OGA = exl("PK 유도"), exl("'Shot on goal'(슈팅 리바운드)"), exl("상대 자책골에 준 도움")
ST_L = lambda i: c3(ST[i])
GAL_T = [ST[0][k] + ST[2][k] + ST[6][k] for k in range(4)]
NOTE_LINES = [
    f"아르다 투란(갈라타사라이·마니사스포르·아틀레티코 마드리드·바르셀로나·이스탄불 바샥셰히르)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 부르사스포르전 ~ {d_(M[-1][0])} 알타이전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·튀르키예 대표팀 경기 제외",
    "클럽별 경기·골·도움: " + f"갈라타사라이 {c3(GAL_T)}(2004-05 {ST_L(0)}, 2006~2011 {ST_L(2)}, 2020~2022 {ST_L(6)}), 마니사스포르 {ST_L(1)}(임대), 아틀레티코 마드리드 {ST_L(3)}, 바르셀로나 {ST_L(4)}, 이스탄불 바샥셰히르 {ST_L(5)}(임대)"
    + f". 출전 분 합계 {MIN_TOT:,}분(갈라타사라이 {GAL_T[3]:,}분, 마니사스포르 {ST[1][3]:,}분, 아틀레티코 마드리드 {ST[3][3]:,}분, 바르셀로나 {ST[4][3]:,}분, 이스탄불 바샥셰히르 {ST[5][3]:,}분)",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 나온 경기와 리그 밖 경기 전부). 2010-11 이후 골·도움 경기는 FotMob 경기 이벤트와 대조함(FotMob에는 2010-11 전 갈라타사라이·마니사스포르 경기 자료가 없음). 출전 분이 없어 90분으로 추정한 경기는 없음",
    "경기 수·골은 튀르키예어 위키백과 클럽·시즌별 기록(경기·골·도움)과 같음. 영어 위키백과는 갈라타사라이 2006-07 리그 29경기·바샥셰히르 2018-19 리그 17경기로 Transfermarkt·튀르키예어 위키백과·FotMob(26·14경기)보다 3경기씩 많아 Transfermarkt를 따름. 소속 팀은 모든 시즌 1부 프로 리그(쉬페르리그·라리가)",
    "골: 2008.2.9 마니사스포르전 27분 PK 골은 본인이 얻은 PK(도움 없음). 2007.2.27 카이세리 에르지예스스포르전(튀르키예컵 8강 2차전) 92분 골은 연장 전반 골. 2010-11 이후 골은 FotMob과 수·분·PK가 같음(2011.1.11 베이파자르 셰케르스포르전은 FotMob 자료가 비어 있음)",
    f"도움: 2014년 8월 전은 Transfermarkt 리포트 도움 기준, 그 뒤는 Transfermarkt와 FotMob 경기 이벤트가 모두 투란 도움으로 적은 것만 넣음. 도움 {NA} = Transfermarkt 리포트 도움 칸 {N_TM_A} − 핸드볼 반칙 1(2008.11.2 가지안테프스포르전 39분 상대 PK 골의 도움 칸에 'Handball by Arda Turan'으로 적힌 것, 투란이 내준 PK라 도움 아님) − PK 유도 {len(PKW)} − 'Shot on goal'(슈팅 리바운드) {len(SOG)} − 상대 자책골에 준 도움 {len(OGA)} − 2014년 8월 뒤 Transfermarkt 단독 도움 1",
    "PK 유도로 뺀 도움: 2007.9.29 베식타시전 논다, 2008.12.21 베식타시전 바로시, 2013.1.13 사라고사전 팔카오, 2016.12.21 에르쿨레스전 라키티치, 2019.3.3 예니 말라티아스포르전 엠레 벨뢰졸루. 'Shot on goal'로 뺀 도움: 2008.3.8 카이세리스포르전 위미트 카란, 2008.10.19 트라브존스포르전 세르베트 체틴, 2012.12.12 헤타페전(코파 델 레이) 필리피 루이스(2010.8.29 에스키셰히르스포르전은 상대 자책골이기도 함). 상대 자책골로 뺀 도움: 2009.8.20 레바디아전, 2009.8.23 카이세리스포르전, 2010.5.8 안탈리아스포르전, 2010.8.29 에스키셰히르스포르전, 2012.11.25 세비야전",
    "2014년 8월 뒤 Transfermarkt에만 있는 도움 1개(2016.12.21 에르쿨레스전 50분 하피냐 골)는 FotMob 득점 이벤트에 도움 이름이 없고 다른 출처 2곳에서 확인하지 못해 넣지 않음. 2014년 8월 전 Transfermarkt 도움 중 FotMob 득점 이벤트에 도움 이름이 없는 2개(2010.8.26 카르파티 리비우전 아이든 이을드즈, 2012.3.18 마요르카전 팔카오)는 기준대로 넣음. 2006~2010 갈라타사라이·마니사스포르 도움은 Transfermarkt 한 곳 기준",
    "몰수 경기: 2009.8.31 앙카라스포르–갈라타사라이(리그)는 끝까지 치러져 0-2로 끝났으나 앙카라스포르가 2009년 11월 리그에서 제외되면서 0-3 몰수로 기록됨. 실제로 뛴 90분과 실제 경기 중 스코어(74분 큐얼 골 0-0 → 0-1, 투란 코너킥 도움)로 계산함. 2008.12.21 베식타시전은 Transfermarkt 리포트가 13분 두 골의 순서를 거꾸로 적어(델가도 1-1 뒤 바로시 PK 2-1) 순서를 바로잡음(투란 기록에는 영향 없음: 바로시 PK는 PK 유도라 뺌)",
    "날짜는 현지 날짜(Transfermarkt 리포트 날짜, 모든 경기가 유럽·튀르키예)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 리그 모형에 넣은 값 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 추정 {SRC['직접 추정']})",
    "쉬페르리그 리그 수준(추정): 평균 = 1473 + 23.33 × (앞뒤 3시즌 튀르키예 UEFA 국가 계수 평균 − 7.333), 순위별 흩어짐 119(다른 선수 자료와 같은 공식). 2005-06~2009-10 계수는 영어 위키백과 'Turkish football clubs in European competitions'(2004 3.547·2005 2.640·2006 4.026·2007 9.750·2008 7.000·2009 7.600·2010 4.600·2011 5.100)로 평균 약 1381(2005-06)·1430(2006-07)·1464(2007-08)·1491(2008-09)·1451(2009-10)·1436(2010-11). 같은 시즌 1위 값이 다른 선수 자료에 있는 시즌(2017-18·2018-19·2019-20·2020-21)은 그 값에서 평균을 구함. 같은 팀·시즌 값이 다른 선수 자료에 이미 있으면 그 값을 씀(예: 페네르바흐체 2005-06·베식타시 2009-10·갈라타사라이 2009-10 손으로 정한 추정값). 튀르키예 2·3부 상대는 같은 시즌 쉬페르리그 평균에서 162·324를 뺀 추정",
    "대회 비중: 튀르키예컵·코파 델 레이는 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중; 튀르키예컵 조별은 무승부 1점 리그식), UEFA 슈퍼컵·수페르코파는 국내컵 결승으로 계산함. UEFA컵 1라운드(2007-08·2008-09)와 유로파 예선·플레이오프는 유로파 예선, UEFA컵 조별·유로파 조별은 유로파 조별, UEFA컵 3라운드(32강)·16강과 유로파 2라운드(32강)·intermediate stage·16강·8강은 유로파 토너먼트, 챔스 예선 3라운드·2라운드는 챔스 예선으로 계산함. 2020.9.17 유로파 예선 2라운드 네프치전은 단판",
    f"두 경기 합산(챔스·UEFA컵·유로파 예선과 토너먼트, 튀르키예컵·코파 델 레이 두 경기 라운드, 수페르코파) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회 2020-21까지, 스페인 국내 대회 2018-19까지, 튀르키예컵 2020-21까지 적용(연장 있음). 투란이 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "연장·승부차기: 2007.2.27 카이세리 에르지예스스포르전(튀르키예컵 8강 2차전, 1차전 0-0) 92분 투란 골은 연장 골, 97분 상대 PK로 1-1, 원정 다득점으로 탈락. 2009.2.3 시바스스포르전(튀르키예컵 8강 2차전) 8분 골은 연장 뒤 승부차기로 탈락한 경기. 2013.5.17 코파 델 레이 결승(연장)·2015.3.17 레버쿠젠전(승부차기)의 출전 분은 Transfermarkt 그대로",
    "시즌 구분: 갈라타사라이는 7월 10일 기준(2009.7.16·7.23·7.30, 2010.7.29, 2021.7.21·7.28 유럽 대회 예선이 새 시즌), 나머지는 8월 1일 기준. 클럽 구분은 Transfermarkt 이적일 기준: 2006.1.9 전 갈라타사라이, 2006.7.1 전 마니사스포르(임대), 2011.8.26 전 갈라타사라이, 2015.7.6 전 아틀레티코 마드리드, 2018.1.15 전 바르셀로나(2016.1 첫 경기, 2017-18 출전 없음), 2020.8.5 전 이스탄불 바샥셰히르(임대, 2020.1~8 바르셀로나 복귀 기간 출전 없음), 이후 갈라타사라이",
    "수상 기록은 Transfermarkt 업적 페이지 기준",
    f"은퇴. 마지막 경기 {d_(M[-1][0])} 알타이전(쉬페르리그), 2022.7 갈라타사라이와 계약 종료 뒤 은퇴",
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
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if r[10] and r[4] <= 90: problems.append(("연장 표시 이상", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const TUR_E={J(E)};\nconst TUR_M={J(M)};\nconst TUR_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_assists_after_2014_08": FM_A,
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", CLUBS[k][0], CLUBS[k][3], v)
