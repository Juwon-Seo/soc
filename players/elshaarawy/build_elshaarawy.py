#!/usr/bin/env python3
"""Stephan El Shaarawy: raw/ -> elshaarawy.json + src/data/els.js (판정 근거는 judgments.md)

  python3 players/elshaarawy/build_elshaarawy.py                    # 파일 쓰기
  python3 players/elshaarawy/build_elshaarawy.py --root=<복사본>    # 다른 저장소 복사본의 src/data에 쓰기(검증용)
  python3 players/elshaarawy/build_elshaarawy.py --debug            # Elo 출처 로그
  python3 players/elshaarawy/build_elshaarawy.py --cross            # 계산기 수록 선수 자료와 같은 경기 대조
  python3 players/elshaarawy/build_elshaarawy.py --fm               # FotMob 골 대조

제코(build_dzeko.py)·카사노(build_cassano.py) 빌드를 바탕으로 함. 중국 슈퍼리그 순위값은 함식·카라스코 빌드와 같음.
입력: raw/tm_games.csv(출전 534경기), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
/home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(같은 경기 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, glob, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(os.path.dirname(os.path.dirname(HERE)), "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "els.js")
OUT_JSON = os.path.join(HERE, "elshaarawy.json")
ME = "스테판 엘 샤라위"
GAP = "2014-08-01"

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
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음; PK 유도·'Shot on goal'·상대 자책골은 일반 규칙): gameId|분 -> 이유
EXCL_A = {
    "3246330|60": "2014.8 이후 Transfermarkt 단독(FotMob 도움 없음). 신화통신 경기 기사: 오른쪽 크로스를 산둥 수비수가 머리로 걷어낸 공이 김신욱 앞에 떨어짐(상대 굴절) → 도움 아님",
    "3433470|69": "2014.8 이후 Transfermarkt 단독(FotMob 도움 없음). Tuttosport 문자 중계 '스피나촐라의 크로스를 엘 샤라위가 건드림(sporcato)', Forza Italian Football '스피나촐라의 컷백' → 엘 샤라위의 의도한 패스가 아닌 굴절로 봄(Quotidiano.net·Sporza 문자 중계는 엘 샤라위 도움으로 적음)",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2800309|47": "Football Italia 'El Shaarawy won back possession and threaded through for Edin Dzeko' · worldsoccertalk(통신 기사) 'El Shaarawy won back possession to set up Edin Dzeko'",
    "2897443|32": "PA Sport(ESPN 게재) 'Strootman made it 2-0 from close range after being played in by El Shaarawy's back-heel' · Corriere dello Sport 'servito in area da un assist delizioso di tacco di El Shaarawy' · Antara(인도네시아 통신) '엘 샤라위가 보낸 공을 받아'",
}
# FotMob에만 있는 도움(넣지 않음)
FM_ONLY_JUDGED = {
    "2251404": "2012.11.30 카타니아전 56분 보아텡 골: FotMob만 엘 샤라위 도움. Sports Mole·Bleacher Report 경기 기사는 보아텡의 중거리 슛(혼자 수비를 제치고 감아 찬 골)으로 적고 도움 언급 없음 → 2014.8 이전 FotMob 단독 도움이라 넣지 않음",
    "2618739": "2015.9.17 안데를레흐트전 85분 트라오레 골: FotMob만 엘 샤라위 도움. PA Sport(ESPN) 'El Shaarawy forced a save from Proto from close range, Traore capitalised', UEFA 기사 'El Shaarawy's effort was rebounded to Traore' → 슈팅 리바운드라 도움 아님",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "FR1", "CSL", "POSB"}   # 세리에B 승격 플레이오프는 리그 비중(선례)
CUP = {"CIT", "CHFA"}
UEFA_C = {"CL", "CLQ", "EL", "ECLQ", "UCOL"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 2라운드·32강·16강
    if cid == "CLQ": return "clq"
    if cid == "ECLQ": return "ecq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"   # 2024-25부터 리그 단계 포함
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # intermediate stage(32강·녹아웃 PO)·16강·8강
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"
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

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = ldate(g)
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
    elif cid == "CIT":   # 코파 이탈리아 준결승: 원정 다득점(2021-22까지)·연장
        ag, et = int(d < "2022-07-01"), 1
    elif cid == "CHFA":  # 중국 FA컵 결승(두 경기): 원정 다득점·연장(2018 결승 베이징 궈안 원정 다득점 우승 선례)
        ag, et = 1, 1
    elif cid == "POSB":  # 세리에B 승격 플레이오프: 원정 다득점·연장 없음(동점이면 정규 시즌 상위 팀 진출 → 계산은 50%)
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
ENTS_BY_D = collections.defaultdict(list)
for x in ENTS: ENTS_BY_D[x["date"]].append(x)

def season_eu(d):
    """상대 수준 시즌(유럽식, 7월부터 새 시즌: 2015.7.28 챔스 예선 = 2015-16)"""
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

def season_lv(d, cid):
    return d[:4] if cid in ("CSL", "CHFA") else season_eu(d)

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
# 세리에B(22팀): 함식 빌드와 같은 기존 순위별 값(세리에B 2010-11 9위 1585·21위 1517과 같음), 5위는 4·6위 평균
SB = {1: 1707, 2: 1665, 3: 1641, 4: 1623, 6: 1608, 7: 1602, 8: 1594, 9: 1585, 10: 1577, 11: 1569, 12: 1564, 13: 1559, 14: 1555,
      15: 1552, 16: 1549, 17: 1542, 18: 1534, 19: 1526, 20: 1521, 21: 1517, 22: 1507}
SB[5] = round((SB[4] + SB[6]) / 2)
# 중국 슈퍼리그(16팀): 함식·카라스코 빌드와 같음(드록바 2012 자료 순위별 값, 없는 순위는 같은 모형)
CN_FIX = {4: 1526, 5: 1514, 6: 1501, 7: 1489, 10: 1458, 11: 1452, 12: 1446, 13: 1433, 14: 1422, 15: 1411, 16: 1397}
def cn_val(r):
    return (CN_FIX[r], "같음") if r in CN_FIX else (round(1484 + 63 * curve(r, 16)), "같은 모형")
NOW = "(11월 18일 현재)"

def model(lg, season, r, n):
    if lg == "IT1" and n == 20:
        return SA[r - 1], f"세리에A {season}{' ' + NOW if season == '2026-27' else ''} {r}위"
    if lg == "IT2" and n == 22: return SB[r], f"세리에B {season} {r}위"
    if lg == "CSL" and n == 16:
        v, how = cn_val(r); return v, f"중국 슈퍼리그 {season} {r}위 (추정, 다른 선수 자료 중국 슈퍼리그 2012 순위별 값과 {how})"
    return None
RANK_LG = ["IT1", "IT2", "CSL"]

# 순위표·통합표로 안 되는 상대(직접 추정, 모두 '추정')
MAN = {
    (key("BSC Young Boys"), "2015-16"): (1609, "스위스 슈퍼리그 2015-16 2위 (추정, 다른 선수 자료 영 보이스 2016-17 2위 1609와 같음)"),
    (key("FK Bodø/Glimt"), "2021"): (1560, "노르웨이 2021 1위 (추정, 다른 선수 자료 보되/글림트 2020 1위 1560과 같음)"),
    (key("CSKA-Sofia"), "2021-22"): (1480, "불가리아 2021-22 2위 (추정, 다른 선수 자료 불가리아 2위 CSKA 소피아 1480과 같음)"),
    (key("Zorya Lugansk"), "2021-22"): (1530, "우크라이나 2021-22 4위 (추정, 전쟁으로 중단된 시점 순위, 다른 선수 자료 조랴 2018-19 4위 1530과 같음)"),
    (key("FC Midtjylland"), "2025-26"): (1560, "덴마크 2025-26 2위 (추정, 다른 선수 자료 미트윌란 2위 1560과 같음)"),
    # 쉬페르리그: 함식·외질 빌드와 같은 회귀(앞뒤 3시즌 UEFA 국가 계수 평균 → 리그 평균, 흩어짐 119). 2021-22 2위 1667(기존 값)과 같은 식
    (key("Trabzonspor"), "2021-22"): (round(1473 + 23.33 * ((3.1 + 6.7 + 11.8) / 3 - 7.3333) + 119 * (1969 - 1739) / 91.3), "쉬페르리그 2021-22 1위"),
}
SEASON_KEY_FIX = {key("FK Bodø/Glimt"): lambda d: d[:4]}   # 노르웨이 = 달력 연도 시즌

ELO_SRC = collections.Counter(); ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp); se = season_lv(d, cid)
    if k in SEASON_KEY_FIX: se = SEASON_KEY_FIX[k](d)
    dd = Date.fromisoformat(d)
    same = []
    for delta in (-1, 0, 1):
        dx = Date.fromordinal(dd.toordinal() + delta).isoformat()
        same += [x for x in ENTS_BY_D.get(dx, []) if key(x["opp"]) == k or _sub(key(x["opp"]), k)]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    if (k, se) in MAN:
        e, lv = MAN[(k, se)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", [])); return e, lv
    seasons = [se] + ([str(int(se[:4])), str(int(se[:4]) + 1)] if cid in UEFA_C else [])
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, se))
        if t and k in t:
            r, n = t[k]
            res = model(lg, se, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_tm_report"] or g["date_local_computed"]

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])
G_BY_D = {ldate(g): g for g in GAMES}

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["elshaarawy_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
PENDING = []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
used_excl, used_add = set(), set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_lv(d, cid), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["elshaarawy_scorer"] == "1", e["elshaarawy_assist_other"] == "1"
    if e["elshaarawy_self_assist"] == "1":
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
    et = int(INFO[gid]["result_flag"] in ("AET", "pens", "on pens") and mi > 90 and not dm and not tie)
    if mi > 120: sys.exit("승부차기 이벤트 " + tag)
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드·굴절)"
        elif tag in EXCL_A: why = EXCL_A[tag]; used_excl.add(tag)
        if why:
            k = why if tag not in EXCL_A else "개별 판정"
            EXCL_CNT[k] += 1; EXCL_LIST[k].append((d, opp, e["minute"], e["scorer"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= GAP:
            if tag in ADD_CONFIRMED:
                used_add.add(tag); judg.append(("2014.8 이후 TM 단독 도움 → 다른 출처 2곳 확인", d, opp, e["minute"], e["scorer"], ADD_CONFIRMED[tag]))
            else:
                hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
                if not hit:
                    PENDING.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
                used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)
for nm_, s_, u_ in (("도움 제외", EXCL_A, used_excl), ("다른 출처 확인 도움", ADD_CONFIRMED, used_add)):
    if set(s_) - u_: sys.exit("쓰이지 않은 " + nm_ + " " + str(set(s_) - u_))

# FotMob에만 있는 도움(Transfermarkt 도움과 짝이 없는 것)
FM_ONLY = []
tm_a_by_gid = collections.defaultdict(list)
for e in EVENTS:
    if e["gameId"] in G and e["elshaarawy_assist_other"] == "1":
        tm_a_by_gid[e["gameId"]].append(minute(e["minute"])[0])
for gid, ts in FM_ASSIST.items():
    if gid not in G: continue
    for t in ts:
        if not any(abs(t - x) <= 3 or (t == 90 and x > 90) or (t == 45 and 45 < x < 60) for x in tm_a_by_gid.get(gid, [])):
            FM_ONLY.append((gid, ldate(G[gid]), t))
if {x[0] for x in FM_ONLY} != set(FM_ONLY_JUDGED):
    sys.exit("FotMob 단독 도움 판정 누락 " + str(FM_ONLY))

if PENDING:
    for x in PENDING: print("판정 누락(2014.8 이후 TM 단독 도움):", x)
    if "--debug" not in sys.argv: sys.exit(1)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

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
    if e["elshaarawy_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, ldate(G[gid]))); continue
    fg = [r for r in FM_EV[gid] if r["elshaarawy_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], t["score_home_away_after"], f["newScore_home_away"]))
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["elshaarawy_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, ldate(G[gid]) if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 계산기 수록 선수 자료와 같은 경기 대조(다른 파일은 고치지 않음)
def load_all():
    out = {}
    for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
        b = os.path.basename(fn)
        if b in ("hon.js", "els.js"): continue
        s = open(fn, encoding="utf-8").read()
        m = re.search(r"const ([A-Z0-9]+)_E=(\[.*?\]);\n", s, re.S)
        if m: out[b] = json.loads(m.group(2))
    return out
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    return diffs
CROSS = []
ESH = lambda s: "shaaraw" in norm(s or "").replace(" ", "")
if "--cross" in sys.argv or len(sys.argv) == 1:
    ALL = load_all()
    mdate = {m[0]: m for m in M}
    for fn, ent in ALL.items():
        for x in ent:
            if x[9] not in mdate: continue
            if key(x[1]) != key(mdate[x[9]][1]) and not _sub(key(x[1]), key(mdate[x[9]][1])): continue   # 같은 팀 동료 자료만
            if x[0] == "a" and ESH(x[13]):
                hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
                CROSS.append((fn, "동료 도움→엘 샤라위 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
            elif x[0] == "g":
                mine = sorted([r for r in E if r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
                tm = [e for e in EVENTS if e["elshaarawy_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 3]
                if mine: CROSS.append((fn, "엘 샤라위 도움→동료 골", x[9], x[4], cmp_rows(mine[0], x) or "같음"))
                elif tm: CROSS.append((fn, "TM 엘 샤라위 도움을 뺀 동료 골", x[9], x[4], tm[0]["assist_type"] or "(빈 유형)"))
            r0 = [r for r in E if r[9] == x[9]]
            if r0:
                dd = [t for t in cmp_rows(r0[0], x) if t.startswith(("Elo", "lv", "대회", "단판", "연장"))]
                CROSS.append((fn, "같은 경기", x[9], x[1], dd or "같음"))
    # 엘 샤라위 도움 행의 득점자 파일에 그 골이 있는지는 위에서, 엘 샤라위 골의 TM 도움자가 수록 선수인데 그 파일에 도움 행이 없는 경우
    for e in EVENTS:
        if e["elshaarawy_scorer"] == "1" and e["gameId"] in G and e["assist_player"]:
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            team_files = {fn for fn, ent in ALL.items() for x in ent if x[9] == d and key(x[1]) == key(G[e["gameId"]]["opponent"].strip())}
            hits = [(fn, x) for fn in team_files for x in ALL[fn] if x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 3]
            if team_files and not hits:
                CROSS.append(("-", "TM 동료 도움(그 선수 파일에 도움 없음)", d, e["minute"], e["assist_player"] + " / " + (e["assist_type"] or "") + " / 같은 경기 파일 " + ",".join(sorted(team_files))))
    # 상대 팀 쪽 자료(같은 날 상대가 엘 샤라위 팀): 날짜만 참고
    for fn, ent in ALL.items():
        for x in ent:
            if x[9] in mdate and key(x[1]) != key(mdate[x[9]][1]):
                club = G_BY_D[x[9]]["club"] if x[9] in G_BY_D else ""
                if key(x[1]) == key(club) or _sub(key(x[1]), key(club)) or norm(club).split()[-1] in norm(x[1]):
                    CROSS.append((fn, "상대 팀 쪽 같은 경기", x[9], x[1], "참고"))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] not in ("같음", "참고"): print(c)
    print(collections.Counter((c[1], c[-1] == "같음") for c in CROSS))
    print(sorted({c[0] for c in CROSS if c[1] != "상대 팀 쪽 같은 경기"}))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("genel", "2010-07-01", "제노아", "2008~2010"), ("padel", "2011-07-01", "파도바", "2010~2011"),
         ("milel", "2015-07-13", "AC 밀란", "2011~2015"), ("monel", "2016-01-26", "AS 모나코", "2015~2016"),
         ("romel", "2019-07-08", "AS 로마", "2016~2019"), ("shsel", "2021-01-30", "상하이 선화", "2019~2021"),
         ("romel", "2026-07-01", "AS 로마", "2021~2026"), ("genel", None, "제노아", "2026~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
def spell_of(d):
    for i, (k, u, _, _) in enumerate(CLUBS):
        if u is None or d < u: return i
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ORDER = []
for k, *_ in CLUBS:
    if k not in ORDER: ORDER.append(k)
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in ORDER)
SP = collections.OrderedDict((i, [0, 0, 0, 0]) for i in range(len(CLUBS)))
for m in M:
    ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]; SP[spell_of(m[0])][0] += 1; SP[spell_of(m[0])][3] += m[3]
for r in E:
    ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1; SP[spell_of(r[9])][1 if r[0] == "g" else 2] += 1
TM_CLUB = {"252": "genel", "3037": "padel", "5": "milel", "162": "monel", "12": "romel", "3183": "shsel"}
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

def season_of(d):
    c = club_of(d)
    if c == "shsel": return d[:4]
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    if c == "monel": s = y if (m, dd) >= (7, 10) else y - 1
    else: s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
SEASONS = collections.OrderedDict()
for m in M:
    s = season_of(m[0]) + " " + CLUB_KO[club_of(m[0])]
    SEASONS.setdefault(s, [0, 0, 0, 0]); SEASONS[s][0] += 1; SEASONS[s][3] += m[3]
for r in E:
    SEASONS[season_of(r[9]) + " " + CLUB_KO[club_of(r[9])]][1 if r[0] == "g" else 2] += 1

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_elshaarawy import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["elshaarawy_assist_other"] == "1")
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
NOTE = make_note(dict(M=M, E=E, ST=ST, SP=SP, CLUBS=CLUBS, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT,
                      NTIE=NTIE, NTIEG=NTIEG, N_TM_A=N_TM_A, PRE_A=PRE_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC))
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
mm = {m[0]: m for m in M}
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
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
api_g = collections.Counter(); api_a = collections.Counter()
for g in GAMES:
    api_g[ldate(g)] += int(g["goals"] or 0); api_a[ldate(g)] += int(g["assists"] or 0)
gcount = collections.Counter(r[9] for r in E if r[0] == "g")
G_DIFF = sorted((d, api_g[d], gcount[d]) for d in set(api_g) | set(gcount) if api_g[d] != gcount[d])
if G_DIFF: problems.append(("골 수 API와 다름", G_DIFF))
acount = collections.Counter(r[9] for r in E if r[0] == "a")
A_DIFF = sorted((d, api_a[d], acount[d]) for d in set(api_a) | set(acount) if api_a[d] != acount[d])
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const ELS_E={J(E)};\nconst ELS_M={J(M)};\nconst ELS_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG,
               "seasons": SEASONS, "assist_count_vs_api": A_DIFF},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    for k, v in SEASONS.items(): print(" ", k, v)
    print("도움 수 API와 다른 날:", A_DIFF)
