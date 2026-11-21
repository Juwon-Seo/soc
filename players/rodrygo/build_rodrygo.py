#!/usr/bin/env python3
"""Rodrygo(호드리구): raw/ -> rodrygo.json + src/data/rod.js (판정 근거는 judgments.md)

  python3 players/rodrygo/build_rodrygo.py            # 파일 쓰기
  python3 players/rodrygo/build_rodrygo.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/rodrygo/build_rodrygo.py --cross    # 동료 자료 대조
  python3 players/rodrygo/build_rodrygo.py --fm       # FotMob 골 대조
  python3 players/rodrygo/build_rodrygo.py --root=<스크래치 복사본>   # 그 복사본의 src/data에 쓰기(검증용)
  (--elo=<elo 폴더>: 상대 Elo 통합표 위치, 기본은 저장소 elo/)

아우아르(build_aouar.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전, 1군만), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv(다른 차전 스코어), raw/fotmob_events.csv(FotMob 경기 이벤트), raw/fotmob_playerMatches.csv·fotmob_tm_map.csv(FotMob 선수 경기 기록),
/home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
src/data/{vin,bzm,bel,mba}.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
for a in list(sys.argv[1:]):
    if a.startswith("--root="): ROOT = a.split("=", 1)[1]; sys.argv.remove(a)
    elif a.startswith("--elo="): ELO = a.split("=", 1)[1]; sys.argv.remove(a)
OUT_JS = os.path.join(ROOT, "src", "data", "rod.js")
OUT_JSON = os.path.join(HERE, "rodrygo.json")
ME = "호드리구"
GAP = "2014-08-01"   # 이 선수의 경기는 모두 이 날짜 뒤: 도움은 Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

ALLG = rd("tm_games.csv")
GAMES = [g for g in ALLG if g["level"] == "senior"]            # 카스티야(2군, 세군다 B) 3경기 제외
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)
FM_MAP = {r["tm_gameId"]: r["fotmob_matchId"] for r in rd("fotmob_tm_map.csv")}
FM_PM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 판정 표
# 출전 분 고침: gameId -> (분, 근거)  (없음: Transfermarkt 출전 분 그대로)
MIN_FIX = {"3092282": (81, "2018.8.28 리베르타도레스 16강 2차전 인데펜디엔테전: 관중 소요로 후반 36분(81분)에 중단·종료(El Universo/AP 81분, Goal.com·Gazeta Esportiva 후반 35~36분), Transfermarkt 90분 → 실제 뛴 81분")}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'·상대 자책골은 일반 규칙)
EXCL_A = {
    "4099533|66": "다른 출처 1곳만 확인(코파 두 브라질 2019.4.17 바스쿠전 66분 장 모타 골: Jovem Pan 기사만 호드리구 패스, JB 기사는 언급 없음, FotMob 이벤트·선수 기록 모두 도움 없음)",
    "4322084|90+6": "확인 안 됨(파울리스타 2019.3.2 오에스치전 90+6분 비토르 페하스 골: FotMob 자료 없음, Lance!·Jovem Pan 기사에 호드리구 도움 언급 없음)",
}
# FotMob 경기 이벤트·선수 경기 기록 어디에도 없지만 다른 출처 2곳 이상이 확인해 넣은 도움 (judgments.md 4절)
ADD_CONFIRMED = {}
# FotMob 이벤트에는 도움 표시가 없지만 FotMob 선수 경기 기록(playerMatches)의 도움 수가 Transfermarkt와 같은 경기 (judgments.md 4절)
FM_PM_OK = {
    "3036872|73": "2018.6.3 비토리아전 73분 가브리엘 바르보자 골",
    "3036879|75": "2018.6.6 코린치안스전 75분 비토르 페하스 골",
    "3036932|34": "2018.7.25 플라멩구전 34분 가브리엘 바르보자 골",
    "3252242|64": "2019.12.11 브뤼허전 64분 비니시우스 골",
    "3716579|39": "2022.1.5 알코야노전 39분 밀리탕 골(코너킥)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BRA1", "ES1"}
CUP = {"BRC", "CDR"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("BCP1", "BCPF"): return "dc"      # 캄페오나투 파울리스타: 단계 무관 국내컵 하위 라운드 비중(네이마르 선례)
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 16강까지(코파 두 브라질 2~4라운드·16강, 코파 델 레이 1라운드~16강)
    if cid == "SUC": return "df" if r.startswith("final") else "dsf"   # 수페르코파(4팀): 준결승 dsf, 결승 df
    if cid == "USC": return "df"                                       # UEFA 슈퍼컵 = 국내컵 결승 비중
    if cid in ("KLUB", "FIC1"): return "cwc"
    if cid == "CLI":
        if r.startswith("final"): return "libf"
        if r.startswith("semi"): return "libsf"
        if r.startswith("quarter"): return "libk"
        return "lib"  # 조별·16강
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 2024-25부터 리그 단계 포함
        if r.startswith("last 16") or r.startswith("intermediate"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE or g["competitionId"] == "BCP1": return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스 조별·리그 단계, 리베르타도레스 조별, 클럽 월드컵 2025 조별(리그식)
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local"]
    leg = 1 if "1st" in g["round"].lower() else 2
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        a, b = map(int, inf["other_leg_score"].split(":"))   # 이 리포트의 홈:원정 순서로 적힌 1차전 스코어
        fu, ft = (a, b) if home else (b, a)
    if cid == "CL":
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CLI":   # 리베르타도레스 2018: 원정 다득점 있고 연장 없이 승부차기
        ag, et = 1, 0
    elif cid in ("BRC", "BCPF"):   # 코파 두 브라질·파울리스타: 원정 다득점·연장 없이 승부차기
        ag, et = 0, 0
    elif cid == "CDR":   # 코파 델 레이 2019-20부터 원정 다득점 없음, 연장 있음
        ag, et = 0, 1
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

def season_of(d, cid):
    """브라질 경기는 달력 연도, 유럽은 8월 1일 기준(2020년 7·8월은 2019-20)"""
    if cid in ("BRA1", "BCP1", "BCPF", "BRC", "CLI"): return d[:4]
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 8 else y - 1
    if d[:7] in ("2020-07", "2020-08"): s = 2019
    return f"{s}-{str(s + 1)[2:]}"

# 브라질 세리에 A·B 순위값: 기존 선수 자료(네이마르·호나우두 등)에서 가장 많이 쓴 값(judgments.md 6절)
BRA1_KNOWN = {1: 1757, 2: 1702, 3: 1671, 4: 1650, 5: 1639, 6: 1631, 7: 1622, 8: 1611, 9: 1599, 10: 1588,
              11: 1581, 12: 1575, 13: 1569, 14: 1566, 15: 1559, 16: 1549, 17: 1537, 18: 1530, 19: 1524, 20: 1512}
BRA2_KNOWN = {1: 1499, 3: 1429, 5: 1403, 6: 1397, 7: 1390, 8: 1380, 9: 1371, 10: 1362, 11: 1356, 12: 1351, 13: 1346,
              15: 1338, 16: 1330, 17: 1321, 18: 1314, 19: 1310, 20: 1300}
def interp(tab, r):
    if r in tab: return tab[r]
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return int(tab[lo] + (tab[hi] - tab[lo]) * (r - lo) / (hi - lo) + 0.5)

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league" or p[0].startswith("INVALID"): continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 순위 검증(judgments.md 6절): 쓰는 순위는 위키백과 최종 순위표와 대조했다
# Transfermarkt 순위표가 위키백과(CBF) 최종 순위와 다른 것: 2018 세리에 A 스포르트 헤시피는 승점 3 삭감으로 18위(TM 표는 17위)
RANK_FIX = {("BRA1", "2018", key("Sport Club do Recife")): 18}
def model(k, season):
    for lg, name, tab in (("BRA1", "브라질 세리에 A", BRA1_KNOWN), ("BRA2", "브라질 세리에 B", BRA2_KNOWN)):
        t = RANKS.get((lg, season))
        if t and k in t:
            r, n = t[k]
            r = RANK_FIX.get((lg, season, k), r)
            return interp(tab, r), f"{name} {season} {r}위"
    return None

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정') — judgments.md 6절
MAN = {
    (key("Club Nacional"), "2018"): (1635, "우루과이 1부 2018 연간 2위 (추정, 다른 선수 자료 우루과이 연간 2위 1635와 같음)"),
    (key("Ituano Futebol Clube (SP)"), "2018"): (1200, "브라질 4부 이하 2018 (추정, 파울리스타 팀, 세리에 A~D 참가 팀 아님; 다른 선수 자료 4부 이하 1200과 같음)"),
    (key("América FC"), "2019"): (1200, "브라질 4부 이하 2019 (추정, 아메리카 RN, 세리에 D 참가 팀; 다른 선수 자료 4부 이하 1200과 같음)"),
    (key("CP Cacereño"), "2022-23"): (1150, "스페인 4부(세군다 페데라시온) 2022-23 (추정, 다른 선수 자료 스페인 4부 1150과 같음)"),
    (key("Arandina CF"), "2023-24"): (1150, "스페인 4부(세군다 페데라시온) 2023-24 (추정, 다른 선수 자료 스페인 4부 1150과 같음)"),
}
LV_FIX = {}
ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    s = season_of(d, cid)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    if (k, s) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
        ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
        if (k, s) in LV_FIX: lv = LV_FIX[(k, s)]
        return e, lv
    if (k, s) in MAN:
        e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    res = model(k, s)
    if res:
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model", []))
        return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local"]   # UTC를 경기장 현지 시간으로 바꾼 날짜(브라질 상파울루, 원정 남미는 개최국, 2025 클럽 월드컵 뉴욕 등)

M = []
for g in GAMES:
    if g["gameId"] in MIN_FIX: mins = MIN_FIX[g["gameId"]][0]
    else: mins = int(g["playedMinutes"])
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
        if r["rodrygo_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))
def pm_assists(gid):
    p = FM_PM.get(FM_MAP.get(gid, ""))
    return int(p["assists"]) if p and p["assists"] not in ("", None) else None

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
PM_USED = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et=0):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_of(d, cid), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["rodrygo_scorer"] == "1", e["rodrygo_assist_other"] == "1"
    if e["rodrygo_self_assist"] == "1":
        EXCL_CNT["본인 도움"] += 1; EXCL_LIST["본인 도움"].append((ldate(g), g["opponent"], e["minute"]))
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
    et = int(int(e["minute"].split("+")[0]) > 90)
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
        if tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
            if hit:
                used_fm[gid] += 1
            elif tag in FM_PM_OK:
                PM_USED.append((d, opp, e["minute"], e["scorer"]))
            else:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"], "FotMob 선수 기록 도움 " + str(pm_assists(gid)))); continue
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and len(ts) > used_fm.get(gid, 0):
        FM_ONLY.append((gid, G[gid]["date_local"], ts))
# FotMob 선수 경기 기록 도움 수가 이 계산기 도움 수보다 많은 경기(참고)
PM_MORE = []

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u)
for f in FM_ONLY: print("판정 필요(FotMob 단독 도움):", f)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
if UNDECIDED or missing_elo or FM_ONLY:
    if "--force" not in sys.argv: sys.exit(1)

def _sk(r):
    return (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1)
rows.sort(key=_sk)
E = rows
for gid in G:
    pa = pm_assists(gid)
    if pa is None: continue
    n = sum(1 for r in E if r[0] == "a" and r[9] == ldate(G[gid]))
    if pa > n: PM_MORE.append((gid, ldate(G[gid]), G[gid]["opponent"], pa, n))

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY, EXCL_CNT, "선수 기록으로 확인:", PM_USED, "선수 기록이 더 많음:", PM_MORE)
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
    if e["rodrygo_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid) or not any(r["scorer"] for r in FM_EV[gid]):
        FM_CMP.append(("FotMob 이벤트 없음", gid, G[gid]["date_local"], G[gid]["opponent"])); continue
    fg = [r for r in FM_EV[gid] if r["rodrygo_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["rodrygo_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Vinicius Junior": ("vin.js", "VIN", "2019-07-01", "2026-12-31"),
         "Karim Benzema": ("bzm.js", "BZM", "2019-07-01", "2023-07-01"),
         "Jude Bellingham": ("bel.js", "BEL", "2023-07-01", "2026-12-31"),
         "Kylian Mbappé": ("mba.js", "MBA", "2024-07-01", "2026-12-31")}
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
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb:
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
ISME = lambda s: norm(s or "") in ("rodrygo", "rodrygo goes")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("호드리구 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and ISME(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→호드리구 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and (key(r[1]) == key(x[1]) or _sub(key(r[1]), key(x[1]))):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    for x in ent:   # Transfermarkt 호드리구 도움을 이 계산기에서 뺀 동료 골(참고)
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["rodrygo_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 호드리구 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # TM 동료 도움 → 호드리구 골인데 동료 파일에 없음(참고)
        if e["rodrygo_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 호드리구 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
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
CLUBS = [("sntro", "2019-07-01", "산투스", "2017~2019"), ("rmro", None, "레알 마드리드", "2019~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"221": "sntro", "418": "rmro"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_rodrygo import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14)
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["rodrygo_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC, PM_USED=PM_USED))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const ROD_E={J(E)};\nconst ROD_M={J(M)};\nconst ROD_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "fotmob_pm_confirmed": PM_USED,
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
