#!/usr/bin/env python3
"""Leon Bailey (레온 베일리, Transfermarkt 387626): raw/ -> bailey.json + src/data/bly.js (판정 근거는 judgments.md)

  python3 players/bailey/build_bailey.py            # 파일 쓰기
  python3 players/bailey/build_bailey.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/bailey/build_bailey.py --cross    # 동료·같은 경기 자료 대조
  python3 players/bailey/build_bailey.py --fm       # FotMob 골 대조
  python3 players/bailey/build_bailey.py --root=<스크래치 복사본>   # 그 복사본의 src/data·elo 사용(검증용)

호프만 빌드(build_hofmann.py, 같은 원자료 형식)를 바탕으로 함. 벨기에 상대 Elo는 데이비드·토르강 아자르 빌드의 국가 계수 회귀.
판정 표는 decisions_bailey.py(근거는 judgments.md), 설명 문장은 note_bailey.py.
입력: raw/tm_games.csv(출전), raw/tm_events.csv(Transfermarkt 경기 리포트 골·도움), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv,
raw/fotmob_events.csv(FotMob 경기 이벤트), raw/fotmob_tm_map.csv(FotMob 선수 경기 기록 골·도움 수), raw/ranks.txt(순위표),
elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 동료 대조).
"""
import csv, json, os, re, sys, unicodedata, collections, subprocess, glob
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
REPO = os.path.dirname(os.path.dirname(HERE))
ROOT = REPO
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "bly.js")
OUT_JSON = os.path.join(HERE, "bailey.json")
ME = "레온 베일리"
GAP = "2014-08-01"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
OTHER = {r["gameId"]: r["other_leg_id"] for r in rd("tm_two_leg_ties.csv")}
for gid, r in INFO.items():
    if r["other_leg_id"]:
        OTHER.setdefault(gid, r["other_leg_id"]); OTHER.setdefault(r["other_leg_id"], gid)
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)
FM_MAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv")}
for g in GAMES:
    if g["date_local_tm_report"] and g["date_local_tm_report"] != g["date_local_computed"]: sys.exit("날짜 불일치 " + g["gameId"])
    if g["gameId"] in INFO and INFO[g["gameId"]]["date_report"] != g["date_local_computed"]: sys.exit("리포트 날짜 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 대회 코드
# 벨기에 챔피언십 플레이오프(EJPL)·유로파 플레이오프 결승(ESJP)은 리그 비중(데 브라위너·데이비드 선례, 문서 3절 '벨기에 플레이오프 2 결승은 리그')
LEAGUE = {"BE1", "EJPL", "ESJP", "L1", "GB1", "IT1", "GR1"}
CUP = {"CCB", "DFB", "FAC", "CGB", "CIT", "GRP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:   # 국내컵: 16강까지 dc / 8강 dk / 준결승 dsf / 결승 df (벨기에컵 6라운드=32강, FA컵 3~5라운드·재경기, 리그컵 2~4라운드는 dc)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round") and cid == "FAC": return "dk"
        return "dc"
    if cid == "ELQ": return "elq"
    if cid == "ECLQ": return "ecq"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 2024-25 리그 페이즈('Group Stage')도 clg
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # intermediate stage(32강·녹아웃 PO)·16강·8강(2020.8 단판 포함)
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"
        if r.startswith("semi"): return "ecsf"
        if r.startswith("final"): return "ecf"
        return "eck"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g): return "leg" in g["round"].lower() and g["competitionId"] != "ESJP"
def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_of(g):
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
        if OTHER[gid] in G and G[OTHER[gid]]["gameState"] == "regularly_terminated":
            a, b = map(int, G[OTHER[gid]]["score_club_opp"].split("-"))
            if (a, b) != (fu, ft): sys.exit("다른 차전 스코어 불일치 " + gid)
    if cid in ("CL", "EL", "ELQ", "ECLQ", "UCOL"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CCB":   # 벨기에컵 준결승(2016): 원정 다득점·연장(토르강 아자르·페리시치 선례)
        ag, et = 1, 1
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
def key(n):
    k = norm(n)
    return ALIAS.get(k, k)

exec(open(os.path.join(HERE, "decisions_bailey.py"), encoding="utf-8").read())   # EXCL_A·ADD_CONFIRMED·FM_ONLY_DECIDED·ADD_G·MAN·MIN_FIX

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if ME in r["선수"].split("·"): continue
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
        if p[0] == "league" or len(p) < 5: continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]) if p[3] else 0)

# 벨기에 1부 공식 최종 순위(영어 위키백과 시즌 문서 wikitext, 2026-11-18): 챔피언십 플레이오프 1~6위 + 정규 시즌 7~16위(데 브라위너·데이비드·토르강 아자르 선례)
# 2015-16 정규 시즌 13·14위는 위키백과 STVV 13위·무스크롱 14위(TM 표는 반대)
BE_FINAL = {
    "2015-16": ["Club Brugge KV", "RSC Anderlecht", "KAA Gent", "KRC Genk", "KV Oostende (-2024)", "Zulte Waregem",
                "Standard Liège", "Royal Charleroi SC", "KV Kortrijk", "KV Mechelen", "KSC Lokeren (-2020)", "KVRS Waasland - SK Beveren",
                "Sint-Truidense VV", "Mouscron-Péruwelz", "KVC Westerlo", "Oud-Heverlee Leuven"],
    "2016-17": ["RSC Anderlecht", "Club Brugge KV", "KAA Gent", "KV Oostende (-2024)", "Royal Charleroi SC", "Zulte Waregem",
                "KV Mechelen", "KRC Genk", "Standard Liège", "KV Kortrijk", "KSC Lokeren (-2020)", "Sint-Truidense VV",
                "KAS Eupen", "KVRS Waasland - SK Beveren", "Royal Excel Mouscron (-2022)", "KVC Westerlo"],
}
for s, teams in BE_FINAL.items():
    if {key(t) for t in teams} != set(RANKS[("BE1", s)]): sys.exit("벨기에 순위 팀 불일치 " + s)
    RANKS[("BE1", s)] = {key(t): (i + 1, 16) for i, t in enumerate(teams)}

def mid(tab, r):
    """기존 순위값에 없는 순위는 앞뒤 기존 값의 단순 중간값(병렬 판정과 맞추기 위한 규칙)"""
    if r in tab: return tab[r], False
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return int((tab[lo] + tab[hi]) / 2 + 0.5), (lo, hi)

_SA20 = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
_CV = [(v - 1739) / 91.3 for v in _SA20]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return _CV[i] + (_CV[i + 1] - _CV[i]) * t

# 벨기에 1부 2015-16·2016-17: 데 브라위너·데이비드·토르강 아자르 자료와 같은 국가 계수 회귀(리그 평균 = a + b × 앞뒤 3시즌 UEFA 국가 계수 평균), 흩어짐 119.
# a·b는 데 브라위너 자료 2009-10 1440·2010-11 1484·2011-12 1467에 맞춘 직선. 벨기에 시즌 계수(kassiesa.net): 2014-15 9.6(토르강 아자르 자료),
# 2015-16 7.4(method4 ccoef2016), 2016-17 12.5(method4 ccoef2017), 2017-18 2.6(데이비드 자료)
_BX = [(4.5 + 8.7 + 4.6) / 3, (8.7 + 4.6 + 10.1) / 3, (4.6 + 10.1 + 6.5) / 3]; _BY = [1440, 1484, 1467]
_mx, _my = sum(_BX) / 3, sum(_BY) / 3
BE_B = sum((x - _mx) * (y - _my) for x, y in zip(_BX, _BY)) / sum((x - _mx) ** 2 for x in _BX)
BE_A = _my - BE_B * _mx
BE_COEF = {2014: 9.6, 2015: 7.4, 2016: 12.5, 2017: 2.6}
def be_mean(season):
    y = int(season[:4])
    return BE_A + BE_B * (BE_COEF[y - 1] + BE_COEF[y] + BE_COEF[y + 1]) / 3

def bl_known(season):
    t = {}
    for x in ENTS:
        m = re.fullmatch(r"분데스리가 " + season + r" (\d+)위", x["lv"])
        if m: t.setdefault(int(m.group(1)), collections.Counter())[x["elo"]] += 1
    return {k: v.most_common(1)[0][0] for k, v in t.items()}

def model(lg, season, r, n):
    if lg == "BE1" and season in BE_FINAL:
        return int(be_mean(season) + 119 * curve(r, n) + 0.5), f"벨기에 1부 {season} {r}위 (리그 모형값)"
    if lg == "L1":
        t = bl_known(season)
        if not t: return None
        v, how = mid(t, r)
        return v, f"분데스리가 {season} {r}위" + (f" (추정, 다른 선수 자료 {how[0]}위 {t[how[0]]}·{how[1]}위 {t[how[1]]}의 중간)" if how else "")
    return None
RANK_LG = ["BE1", "L1"]

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

UEFA = ("CL", "EL", "ELQ", "ECLQ", "UCOL")
def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in UEFA else [eu]
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
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g): return g["date_local_computed"]
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
        if r["bai_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]))
def pm_assists(gid):
    p = FM_MAP.get(gid)
    return int(p["fm_assists"]) if p and p["fm_assists"] not in ("", None) else None

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
PM_USED = []
TM_A_ALL = []
USED = collections.Counter()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et=0):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

def ctx(e, g):
    inf = INFO[e["gameId"]]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    return ours, gf, ga

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["bai_scorer"] == "1", e["bai_assist_other"] == "1"
    if e["bai_self_assist"] == "1":
        judg.append(("본인 골의 본인 도움 제외", tag, ldate(g))); EXCL_CNT["본인 도움"] += 1
    if tag in ADD_G:   # Transfermarkt가 다른 선수 골로 적었지만 베일리 골로 셈
        isg = True; USED["ADD_G"] += 1
    if tag in ADD_A:   # Transfermarkt 리포트에 도움자가 없지만 FotMob과 다른 출처가 베일리 도움으로 적음
        isa = True; USED["ADD_A"] += 1
    if not (isg or isa): continue
    ours, gf, ga = ctx(e, g)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = int(ko == 1 and tie is None and int(e["minute"].split("+")[0]) > 90)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if not ours or (e["own_goal"] == "1" and tag not in ADD_G):
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        pk = int(e["penalty"] == "1") if tag not in ADD_G else 0
        add_row("g", mi, dm, gf, ga, pk, 0, tie, comp, ko, d, opp, cid, et)
        if tag in ADD_G: judg.append(("TM 다른 선수 골 → 베일리 골", d, opp, e["minute"], ADD_G[tag]))
    if isa and tag in ADD_A:
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)
        judg.append(("FotMob+다른 출처 도움 넣음", d, opp, e["minute"], e["scorer"], ADD_A[tag])); continue
    if isa:
        TM_A_ALL.append((d, opp, e["minute"], e["scorer"], e["assist_type"]))
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player" or e["goal_desc"] == "Penalty" or e["penalty"] == "1": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            k = why if tag not in EXCL_A else "개별 판정"
            EXCL_CNT[k] += 1; EXCL_LIST[k].append((d, opp, e["minute"], e["scorer"], e["assist_type"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
        if tag in ADD_CONFIRMED:
            USED["ADD_CONFIRMED"] += 1
        elif hit:
            used_fm[gid] += 1
        elif tag in FM_PM_OK:
            PM_USED.append((d, opp, e["minute"], e["scorer"])); USED["FM_PM_OK"] += 1
        else:
            UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"], "FotMob 선수 기록 도움 " + str(pm_assists(gid)))); continue
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")) + sum(1 for k in ADD_A if k.startswith(gid + "|")):
        FM_ONLY.append((gid, G[gid]["date_local_computed"], ts))

for nm_, tab, n in (("ADD_G", ADD_G, USED["ADD_G"]), ("ADD_A", ADD_A, USED["ADD_A"]), ("ADD_CONFIRMED", ADD_CONFIRMED, USED["ADD_CONFIRMED"]), ("FM_PM_OK", FM_PM_OK, USED["FM_PM_OK"])):
    if len(tab) != n: sys.exit(f"판정 표 {nm_} 사용 수 불일치 {len(tab)} vs {n}")
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
    print("FotMob 선수 기록으로 확인한 도움", PM_USED)
    print("BE 회귀", BE_A, BE_B, {s: be_mean(s) for s in BE_FINAL})
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if (e["bai_scorer"] == "1" or f"{e['gameId']}|{e['minute']}" in ADD_G) and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local_computed"])); continue
    fg = [r for r in FM_EV[gid] if r["bai_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "1")]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
for gid, evs in FM_EV.items():
    if gid in G and gid not in TMG and any(r["bai_scorer"] == "1" and r["pen_shootout_event"] != "True" for r in evs):
        FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local_computed"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
TRACKED = set(subprocess.run(["git", "-C", REPO, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(REPO, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "bly.js") or "src/data/" + b not in TRACKED: continue
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    OTHERS[b] = json.loads(m.group(2))
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
ISK = lambda s: bool(re.search(r"bailey", str(s or ""), re.I))
def same_team(x, r): return key(x[1]) == key(r[1]) or _sub(key(x[1]), key(r[1]))
CROSS = []
for b, oe in OTHERS.items():
    for x in oe:
        if x[0] == "a" and ISK(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((b + " 도움→베일리 골", x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and same_team(x, r)]
            if hit: CROSS.append(("베일리 도움→" + b + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            for x in oe:
                if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x, r) and not ISK(x[13]):
                    CROSS.append(("베일리 골에 다른 도움자(" + b + ")", r[9], r[4], x[13]))
            for x in oe:   # 같은 골을 동료가 골로 적은 경우
                if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 1 and same_team(x, r):
                    CROSS.append(("같은 시각 동료 골(" + b + ")", r[9], r[4], x[4]))
    for (d, opp, mn, sc, ty) in TM_A_ALL:
        mi = minute(mn)[0]
        mine = any(r[0] == "a" and r[9] == d and abs(r[4] - mi) <= 2 for r in E)
        for x in oe:
            if x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 2 and (key(x[1]) == key(opp) or _sub(key(x[1]), key(opp))):
                CROSS.append(("TM 베일리 도움 " + ("넣음" if mine else "뺌") + " — " + b + " 골(참고)", d, mn, sc, ty))
SAME_GAME = []
for r in E:
    for x in ENTS:
        if x["date"] == r[9] and (key(x["opp"]) == key(r[1]) or _sub(key(x["opp"]), key(r[1]))):
            if x.get("comp") and x["comp"] != r[3]: SAME_GAME.append(("대회 다름", r[9], r[1], x["p"], x["comp"], r[3]))
            if x["elo"] != r[2] or x["lv"] != r[12]: SAME_GAME.append(("Elo/lv 다름", r[9], r[1], x["p"], x["elo"], x["lv"], r[2], r[12]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s in sorted(set(SAME_GAME)): print(s)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("genlb", "2017-01-31", "KRC 헹크", "2015~2017"), ("levlb", "2021-08-04", "바이어 레버쿠젠", "2017~2021"),
         ("avllb", "2025-08-20", "애스턴 빌라", "2021~2025"), ("romlb", "2026-01-21", "AS 로마", "2025~2026"),
         ("avllb", "2026-09-02", "애스턴 빌라", "2026"), ("olylb", None, "올림피아코스", "2026~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)   # 빌라 두 번은 같은 키(한 줄)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != {"1184": "genlb", "15": "levlb", "405": "avllb", "12": "romlb", "683": "olylb"}[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_bailey import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=len(TM_A_ALL), EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC, PM_USED=PM_USED,
                      BE={s: be_mean(s) for s in BE_FINAL}))
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "TM "]:
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
mm_ = {m[0]: m for m in M}
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
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    if "--force" not in sys.argv: sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const BLY_E={J(E)};\nconst BLY_M={J(M)};\nconst BLY_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game_diffs": sorted(set(SAME_GAME)), "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY,
               "fotmob_playermatches_assists": PM_USED, "excluded_assists": EXCL_LIST, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
