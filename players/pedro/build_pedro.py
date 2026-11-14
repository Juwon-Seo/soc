#!/usr/bin/env python3
"""Pedro (Pedro Rodríguez Ledesma): raw/ -> pedro.json + src/data/ped.js (판정 근거는 judgments.md)

  python3 players/pedro/build_pedro.py            # 파일 쓰기
  python3 players/pedro/build_pedro.py --debug    # Elo 출처 로그
  python3 players/pedro/build_pedro.py --cross    # 동료 자료 대조
  python3 players/pedro/build_pedro.py --fm       # FotMob 골 대조

페드로(build_eriksen.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
/home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
src/data/{son,kan,luc,sua,lau,brf,ron,sch}.js(같은 경기 동료 자료 대조).
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
OUT_JS = os.path.join(ROOT, "src", "data", "ped.js")
OUT_JSON = os.path.join(HERE, "pedro.json")
ME = "페드로 로드리게스"
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
MIN_FIX = {}
# 골 시각 고침: gameId|TM 분 -> (분, 근거)
EV_MIN_FIX = {
    "1125063|77": (82, "2012.1.22 말라가전 메시 세 번째 골(페드로 도움): Transfermarkt 77분, FotMob 82분, ESPN·말라가 구단 기사 81분, 메시 자료 82분 → 82분"),
}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'·상대 자책골은 일반 규칙)
EXCL_A = {
    "3844862|29": "2014.8 이후 TM 단독('Pass'), FotMob 도움 없음. 경기 기사는 페드로의 압박에 이바녜스가 박스 안에서 잘못 내준 공이 펠리피 안데르송에게 감(AP·il Romanista 등은 '페드로가 공을 빼앗아 연결'로도 적음) → 패스 도움을 2곳이 분명히 확인하지 못해 뺌",
    "1036283|28": "TM 단독(2014.8 전). 같은 골(29분 메시, 2:0)을 FotMob은 다비드 비야 도움으로 적었고, 비야 자료(vil.js)는 FotMob·La Jornada·Reuters/AP 기사로 비야 도움을 넣어 둠 → 한 골에 도움 두 개가 되지 않도록 페드로 도움은 뺌",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳 이상이 확인해 넣은 도움
ADD_CONFIRMED = {}
# 2014.8.1 이후 FotMob 경기 이벤트에만 있는 도움 판정: gameId -> (넣을 행 정보 또는 None, 근거)
#   넣는 행: (분, 표시 분, 골 전 우리 골, 골 전 상대 골, 득점자)
FM_ONLY_JUDGED = {
    "3614841": ((76, 0, 3, 1, "Ciro Immobile"),
                "2022.4.10 제노아전 76분 임모빌레 골(3:1 → 4:1): Transfermarkt '도움 없음', FotMob 페드로 도움. 다른 출처: Quotidiano.net 경기 기사(페드로가 수비를 가르는 패스), Tuttomercatoweb 평점 기사(페드로가 공을 되찾아 임모빌레에게 줌) → 넣음. ESPN·Sporza 문자 중계도 페드로 도움(데이터 공급이 같을 수 있어 세지 않음). Sportface만 루이스 알베르토 도움으로 적음"),
    "4621049": (None,
                "2026.4.27 우디네세전 90+5분 말디니 골(3:3): FotMob 페드로 도움, Transfermarkt 'Shot on goal'(페드로 슈팅 리바운드). 기사도 '페드로 슈팅이 튀어 나온 공'과 '페드로가 공을 다시 문전으로 보냄'으로 갈림 → 슈팅 리바운드 제외 규칙대로 넣지 않음(비야 자료 2011.2.5 같은 처리)"),
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES1", "GB1", "IT1"}
CUP = {"CDR", "FAC", "CGB", "CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round"): return "dk"
        return "dc"
    if cid in ("SUC", "USC", "GBCS"): return "df"   # 슈퍼컵류 = 국내컵 결승
    if cid == "SCI": return "dsf"                   # 수페르코파 이탈리아나 4팀 준결승(2024.1)
    if cid == "KLUB": return "cwc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"   # 2024-25 리그 단계('Group Stage') 포함
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # intermediate stage(32강)·16강·8강
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"
        if r.startswith("semi"): return "ecsf"
        if r.startswith("final"): return "ecf"
        return "eck"   # 녹아웃 플레이오프(intermediate stage)·16강
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
    if cid in ("CL", "CLQ", "EL", "UCOL"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid in ("CDR", "SUC"):   # 코파 델 레이·수페르코파(두 경기): 원정 다득점·연장(이 선수 경기는 모두 2015년 전)
        ag, et = 1, 1
    elif cid == "CGB":   # 잉글랜드 리그컵 준결승: 2017-18까지 원정 다득점·연장, 이후 둘 다 없음
        ag = et = int(d < "2018-07-01")
    elif cid == "CIT":   # 코파 이탈리아: 원정 다득점 2021-22까지·연장
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
MANUAL_ALIAS = {"inter milan": "inter", "club atletico de ceuta": "ad ceuta"}
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

# 에레디비시: 시즌 무관 순위별 고정값(기존 선수 자료 값 그대로)
NL1_FIX = {1: 1837, 2: 1735, 3: 1677, 4: 1642, 5: 1624, 6: 1608, 7: 1587, 8: 1563, 9: 1542, 10: 1528,
           11: 1516, 12: 1504, 13: 1499, 14: 1482, 15: 1459, 16: 1441, 17: 1430, 18: 1406}
# 리그 원(잉글랜드 3부): 기존 자료의 순위별 값 + 빠진 순위는 이웃 순위 값 사이 직선 보간(외질 자료와 같은 방식)
GB3_KNOWN = {4: 1539, 6: 1522, 7: 1518, 9: 1506, 11: 1491, 12: 1489, 14: 1477, 18: 1461, 19: 1457, 23: 1436}
def interp(tab, r):
    if r in tab: return tab[r]
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return round(tab[lo] + (tab[hi] - tab[lo]) * (r - lo) / (hi - lo))

def model(lg, season, r, n):
    if lg == "NL1": return NL1_FIX[r], f"에레디비시 {season} {r}위"
    if lg == "GB3": return interp(GB3_KNOWN, r), f"리그 원 {season} {r}위"
    return None
RANK_LG = []

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정')
MAN = {
    # 순위표(TM 최종 순위, raw/ranks.txt) + 기존 선수 자료의 같은 리그·같은 순위 값
    (key("Walsall FC"), "2015-16"): (1555, "리그 원(3부) 2015-16 3위"),
    (key("Peterborough United"), "2016-17"): (1491, "리그 원(3부) 2016-17 11위"),
    (key("Brentford FC"), "2016-17"): (1617, "챔피언십 2016-17 10위"),
    (key("Wolverhampton Wanderers"), "2016-17"): (1584, "챔피언십 2016-17 15위"),
    (key("Nottingham Forest"), "2019-20"): (1642, "챔피언십 2019-20 7위"),
    (key("AZ Alkmaar"), "2022-23"): (1642, "에레디비시 2022-23 4위"),
    (key("SSC Napoli"), "2024-25"): (1969, "세리에A 2024-25 1위"),
    # 직접 추정(다른 선수 자료의 같은 팀·비슷한 순위 값)
    (key("Malmö FF"), "2018-19"): (1529, "스웨덴 알스벤스칸 2018 3위 (추정, 다른 선수 자료 스웨덴 3위 1529와 같음)"),
    (key("SK Slavia Prague"), "2018-19"): (1600, "체코 2018-19 1위 (추정, 다른 선수 자료 슬라비아 프라하 2019-20 체코 1위 1600과 같음)"),
    (key("Dynamo Kyiv"), "2018-19"): (1620, "우크라이나 2018-19 2위 (추정, 다른 선수 자료 디나모 키이우 2017-18 2위권 1620과 같음)"),
    (key("CFR Cluj"), "2020-21"): (1500, "루마니아 2020-21 1위 (추정, 다른 선수 자료 클루지 1500과 같음)"),
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
        if r["pedro_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    et = int(ko == 1 and not tie and int(str(dm or mi).split("+")[0]) > 90)   # 연장 골(표시 분 앞부분이 90 넘음)
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["pedro_scorer"] == "1", e["pedro_assist_other"] == "1"
    if e["pedro_self_assist"] == "1":
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
    if tag in EV_MIN_FIX: mi, dm = EV_MIN_FIX[tag][0], 0
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
            k = why if tag not in EXCL_A else "개별 판정"
            EXCL_CNT[k] += 1; EXCL_LIST[k].append((d, opp, e["minute"], e["scorer"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
            if not hit:
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

for gid, (spec, why) in FM_ONLY_JUDGED.items():
    if spec is None:
        judg.append(("FotMob 단독 도움 제외", gid, why)); EXCL_CNT["FotMob 단독(넣지 않음)"] += 1; continue
    g = G[gid]; mi, dm, gf, ga, scorer = spec
    add_row("a", mi, dm, gf, ga, 0, scorer, tie_of(g), comp_of(g["competitionId"], g["round"]), ko_of(g), ldate(g), g["opponent"].strip(), g["competitionId"])
    judg.append(("FotMob 단독 도움 넣음", gid, why))
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and gid not in FM_ONLY_JUDGED and G[gid]["date_local"] >= GAP and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")):
        FM_ONLY.append((gid, G[gid]["date_local"], ts))

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
    if e["pedro_scorer"] == "1" and e["gameId"] in G and G[e["gameId"]]["date_local"] >= "2010-08-01":
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["pedro_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
# FotMob에만 있는 페드로 골(2013.7.27 하우엘레이우 자책골)
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["pedro_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local"] if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Lionel Messi": ("mes.js", "MES", "2008-01-01", "2015-08-20"),
         "David Villa": ("vil.js", "VIL", "2010-07-01", "2013-07-25"),
         "Andrés Iniesta": ("ini.js", "INI", "2008-01-01", "2015-08-20"),
         "Neymar": ("ney.js", "NEY", "2013-06-01", "2015-08-20"),
         "Luis Suárez": ("sua.js", "SUA", "2014-08-01", "2015-08-20"),
         "Thierry Henry": ("hen.js", "HEN", "2008-01-01", "2010-07-01"),
         "Zlatan Ibrahimović": ("ibr.js", "IBR", "2009-07-27", "2010-08-28"),
         "Samuel Eto'o": ("eto.js", "ETO", "2008-01-01", "2009-07-27"),
         "Ronaldinho": ("rdg.js", "RDG", "2008-01-01", "2008-07-15"),
         "Cesc Fàbregas": ("fab.js", "FAB", "2011-08-15", "2019-01-11"),
         "Eden Hazard": ("haz.js", "HAZ", "2015-08-20", "2019-07-01"),
         "Radamel Falcao": ("fal.js", "FAL", "2015-08-20", "2016-07-01"),
         "Gonzalo Higuaín": ("hig.js", "HIG", "2019-01-23", "2019-07-01"),
         "Christian Pulisic": ("pul.js", "PUL", "2019-07-01", "2020-09-01"),
         "Ciro Immobile": ("imm.js", "IMM", "2021-08-19", "2024-07-15")}
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
ER = lambda s: norm(s or "") in ("pedro", "pedro rodriguez", "pedro rodriguez ledesma")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("페드로 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and ER(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→페드로 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    for x in ent:   # Transfermarkt 페드로 도움을 이 계산기에서 뺀 동료 골(참고)
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["pedro_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 페드로 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # 동료 파일에서 페드로 골의 도움으로 적혔어야 할 것(TM 리포트 기준, 참고)
        if e["pedro_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 페드로 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
    for x in ent:   # 동료 골인데 페드로 파일에 도움이 없고 TM에도 없는 것은 대조 대상 아님
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
CLUBS = [("fcbpe", "2015-08-20", "바르셀로나", "2008~2015"), ("chepe", "2020-09-01", "첼시", "2015~2020"),
         ("rompe", "2021-08-19", "AS 로마", "2020~2021"), ("lazpe", None, "라치오", "2021~2026")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"131": "fcbpe", "631": "chepe", "12": "rompe", "398": "lazpe"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_pedro import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["pedro_assist_other"] == "1")
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const PED_E={J(E)};\nconst PED_M={J(M)};\nconst PED_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
