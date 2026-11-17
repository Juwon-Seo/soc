#!/usr/bin/env python3
"""Ademola Lookman: raw/ -> lookman.json + src/data/loo.js (판정 근거는 judgments.md)

  python3 players/lookman/build_lookman.py            # 파일 쓰기
  python3 players/lookman/build_lookman.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/lookman/build_lookman.py --cross    # 동료 자료 대조
  python3 players/lookman/build_lookman.py --fm       # FotMob 골 대조
  python3 players/lookman/build_lookman.py --root=<스크래치 복사본>   # 그 복사본의 src/data에 쓰기(검증용)

래시포드(build_rashford.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
/home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(git에 있는 기존 선수 파일만, 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, subprocess, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
REPO = os.path.dirname(os.path.dirname(HERE))
ROOT = REPO
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):   # 스크래치 복사본에 쓰기(검증용)
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(REPO, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "loo.js")
OUT_JSON = os.path.join(HERE, "lookman.json")
ME = "아데몰라 루크먼"
GAP = "2014-08-01"   # 이 날짜 뒤 도움은 Transfermarkt∩FotMob, 한쪽에만 있으면 다른 출처 2곳 필요(루크먼은 모든 경기가 이 뒤)

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

# ---------------------------------------------------------------- 판정 표
MIN_FIX = {}   # 출전 분 고침 없음(Transfermarkt 출전 분 그대로)
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음; PK 유도·'Shot on goal'·자책골은 일반 규칙으로 처리): gameId|분 -> 이유
EXCL_A = {}
# FotMob 경기 이벤트에 없지만(Transfermarkt만) 다른 출처 2곳 이상이 확인해 넣은 도움
ADD_CONFIRMED = {
    "3710344|25": "Sky Sports 경기 리포트(PA 통신 기사: 루크먼이 돌아서 매디슨에게 찔러 줌, 사진 설명 'Maddison was assisted by Ademola Lookman') · 90min 경기 평점 기사(루크먼 패스가 매디슨 골을 만듦)",
    "3710344|54": "Sky Sports 경기 리포트(PA 통신 기사: 'Lookman was again the provider', 반스 골) · 90min 경기 평점 기사(반스가 루크먼 패스로 마무리)",
}
# FotMob에만 있는 도움 중 다른 출처 2곳이 확인해 넣는 것: gameId|Transfermarkt 골 분 -> 근거
FM_ADD = {
    "2872216|67": "2017.11.5 왓퍼드전 67분 니아스 골: Transfermarkt 리포트는 도움 없음, FotMob은 루크먼 도움. theScore 경기 문자 기록(루크먼이 왓퍼드 미드필드·수비 너머로 띄운 공에 골키퍼가 못 미치고 니아스가 밀어 넣음) · HITC 경기 뒤 기사(루크먼이 니아스 골을 만듦) — 넣음",
}
# FotMob에만 있는 도움 중 넣지 않는 것
FM_ONLY_DECIDED = {
    "3714110": "2022.2.17 란데르스전 23분 은디디 골: FotMob만 루크먼 도움, Transfermarkt 도움 없음. Sky Sports 경기 기사 본문에 '루크먼의 컷백이 상대 안케르센의 발에 맞고' 들어갔다고 적혀 있어 굴절 골 — 넣지 않음(레스터 구단 기사는 루크먼이 내줬다고 적음)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "GB2", "GB3", "L1", "IT1", "ES1"}
CUP = {"FAC", "CGB", "CDR", "DFB", "CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth") or r.startswith("6th"): return "dk"
        return "dc"   # FA컵 1~4라운드·재경기, 리그컵 1·3·4라운드, DFB 포칼·코파 이탈리아 16강
    if cid == "USC": return "df"   # UEFA 슈퍼컵 = 국내컵 결승 비중
    if cid == "SCI": return "df" if r.startswith("final") else "dsf"   # 수페르코파 이탈리아나(4팀) 준결승
    if cid == "ELQ": return "elq"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 조별(Group G)·리그 단계(TM 'Group Stage')
        if r.startswith("intermediate") or r.startswith("last 16"): return "cl16"   # 녹아웃 플레이오프 = 16강
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 16강·8강
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"
        if r.startswith("semi"): return "ecsf"
        if r.startswith("final"): return "ecf"
        return "eck"   # 녹아웃 플레이오프(intermediate stage)·16강·8강
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
    if cid in ("CL", "EL", "ELQ", "UCOL"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CIT":   # 코파 이탈리아 준결승: 원정 다득점 2021-22까지, 2차전 연장
        ag, et = int(d < "2022-07-01"), 1
    elif cid == "CDR":   # 코파 델 레이: 원정 다득점 2018-19까지, 연장 있음
        ag, et = int(d < "2019-07-01"), 1
    elif cid == "CGB":
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
    s = y if m >= 8 else y - 1
    if d[:7] == "2020-08": s = 2019
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

def mid(tab, r):
    """기존 순위값에 없는 순위는 앞뒤 기존 값의 단순 중간값(병렬 판정과 맞추기 위한 규칙)"""
    if r in tab: return tab[r], False
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return int((tab[lo] + tab[hi]) / 2 + 0.5), (lo, hi)

# 잉글랜드 2~4부: 다른 선수 자료의 순위별 값(시즌 무관, 래시포드 자료와 같은 표) — judgments.md 7절
GB2_KNOWN = {1: 1761, 2: 1717, 3: 1689, 4: 1669, 5: 1656, 6: 1648, 7: 1642, 8: 1635, 9: 1626, 10: 1617, 11: 1607, 12: 1600,
             13: 1594, 14: 1589, 15: 1584, 16: 1580, 17: 1578, 18: 1572, 19: 1564, 20: 1555, 21: 1547, 22: 1542, 23: 1537, 24: 1527}
GB3_KNOWN = {3: 1555, 4: 1539, 5: 1530, 6: 1522, 7: 1518, 8: 1513, 9: 1506, 10: 1498, 11: 1491, 12: 1489, 14: 1477, 15: 1473,
             16: 1469, 17: 1467, 18: 1461, 19: 1457, 20: 1450, 22: 1440, 23: 1436, 24: 1428}
GB4_KNOWN = {2: 1460, 4: 1433, 6: 1406, 7: 1403, 8: 1396, 12: 1368, 13: 1367, 16: 1363, 19: 1340, 22: 1335}
LGNAME = {"GB2": "챔피언십", "GB3": "리그 원", "GB4": "리그 투"}

def bl_known(season):
    """분데스리가 그 시즌 순위값: 기존 선수 자료 lv '분데스리가 <시즌> [(… 현재)] N위'"""
    t = {}
    for x in ENTS:
        m = re.match(r"분데스리가 " + season + r" (?:\([^)]*현재\) )?(\d+)위", x["lv"])
        if m: t.setdefault(int(m.group(1)), collections.Counter())[x["elo"]] += 1
    return {k: v.most_common(1)[0][0] for k, v in t.items()}

def model(lg, season, r, n):
    if lg == "GB3" and r == 2:   # 리그 원 1·2위 기존 값 없음
        return 1583, f"리그 원 {season} 2위 (추정, 다른 선수 자료 리그 원 3위 1555보다 챔피언십 2·3위 차이(28)만큼 높게)"
    if lg == "GB4" and r == 1:
        return 1491, f"리그 투 {season} 1위 (추정, 다른 선수 자료 리그 투 1위 1491과 같음)"
    t = {"GB2": GB2_KNOWN, "GB3": GB3_KNOWN, "GB4": GB4_KNOWN}.get(lg)
    if t:
        v, how = mid(t, r)
        return v, f"{LGNAME[lg]} {season} {r}위" + (f" (추정, 다른 선수 자료 {how[0]}위 {t[how[0]]}·{how[1]}위 {t[how[1]]}의 중간)" if how else "")
    if lg == "L1":
        t = bl_known(season)
        v, how = mid(t, r)
        now = " (11월 중순 현재)" if season == "2026-27" else ""
        return v, f"분데스리가 {season}{now} {r}위" + (f" (추정, 다른 선수 자료 {how[0]}위 {t[how[0]]}·{how[1]}위 {t[how[1]]}의 중간)" if how else "")
    return None
RANK_LG = ["GB2", "GB3", "GB4", "L1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정') — judgments.md 7절
MAN = {
    (key("Randers FC"), "2021-22"): (1480, "덴마크 2021-22 6위 (추정, 다른 선수 자료 브뢴뷔 2021-22 1520보다 낮게, 덴마크 4·5위 1480과 같음)"),
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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL", "ELQ", "UCOL", "USC") else [eu]
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
def ldate(g):
    return g["date_local_computed"]

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
        if r["lookman_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
FM_ADDED = []
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
    isg, isa = e["lookman_scorer"] == "1", e["lookman_assist_other"] == "1"
    if tag in FM_ADD:
        if isa or e["assist_player"]: sys.exit("FM_ADD 대상에 이미 도움 " + tag)
        isa = True; e = dict(e, scorer=e["scorer"]); used_fm[gid] += 1; FM_ADDED.append(tag)
    if e["lookman_self_assist"] == "1":
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
        if d >= GAP and tag not in ADD_CONFIRMED and tag not in FM_ADD:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - mi) <= 3 or abs(t - int(e["minute"].split("+")[0])) <= 3]
            if not hit:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

# FotMob 도움인데 이 계산기에 들어가지 않은 것(규칙상 제외된 'Shot on goal' 포함) — 목록만
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")):
        FM_ONLY.append((gid, G[gid]["date_local_computed"], G[gid]["opponent"], ts))

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u)
for f in FM_ONLY:
    if f[0] not in FM_ONLY_DECIDED: print("FotMob 도움 미반영:", f)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
if UNDECIDED or missing_elo:
    if "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, EXCL_CNT)
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
    if e["lookman_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local_computed"])); continue
    fg = [r for r in FM_EV[gid] if r["lookman_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["lookman_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local_computed"] if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P, what="E"):
    s = open(os.path.join(REPO, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + "_" + what + r"=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1)) if m else []
# 기존 선수 파일(git에 있는 것만 — 병렬 판정 중인 다른 새 선수 파일은 보지 않음)
TRACKED = subprocess.run(["git", "-C", REPO, "ls-files", "src/data"], capture_output=True, text=True).stdout.split()
MDATES = {(m[0], key(m[1])) for m in M}
MATES = {}
for path in TRACKED:
    fn = os.path.basename(path)
    if fn in ("hon.js", "loo.js"): continue
    P = fn[:-3].upper()
    mm = load_js(fn, P, "M")
    hit = sorted(m[0] for m in mm if (m[0], key(m[1])) in MDATES)
    if hit: MATES[fn] = (P, hit[0], hit[-1], load_js(fn, P), mm)
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
FK = lambda s: "lookman" in norm(s or "")
for nm, (P, lo, hi, ent, mm) in MATES.items():
    hi = hi + "~"
    for r in E:   # 루크먼 도움 → 동료 골
        if r[0] == "a":
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and key(x[1]) == key(r[1]) and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            if hit: CROSS.append(("루크먼 도움→" + nm + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:   # 동료 도움 → 루크먼 골
        if x[0] == "a" and FK(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→루크먼 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] <= hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    mmap = {(m[0], key(m[1])): m for m in mm}
    for m in M:
        o = mmap.get((m[0], key(m[1])))
        if o and o[2] != m[2]: CROSS.append(("같은 경기 대회 코드 다름", nm, m[0], m[1], m[2], o[2]))
    for x in ent:   # 동료 골인데 Transfermarkt 도움이 루크먼(이 계산기에서 뺀 것) — 참고
        if x[0] == "g" and lo <= x[9] <= hi:
            tm = [e for e in EVENTS if e["lookman_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 루크먼 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for r in E:   # 루크먼 골인데 동료 파일 도움 없음(Transfermarkt 도움자가 그 파일 선수인지 확인용) — 참고
        if r[0] == "g" and lo <= r[9] <= hi:
            e = [e for e in EVENTS if e["lookman_scorer"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == r[9] and minute(e["minute"])[0] == r[4]]
            if e and e[0]["assist_player"] and not any(x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 for x in ent):
                CROSS.append(("TM 도움자 확인(동료 파일에 이 골 도움 없음)", nm, r[9], r[4], e[0]["assist_player"], e[0]["assist_type"]))
SAME_GAME = []
for r in E:
    for x in ENTS:
        if x["date"] == r[9] and (key(x["opp"]) == key(r[1]) or _sub(key(x["opp"]), key(r[1]))):
            if x.get("comp") and x["comp"] != r[3]:
                SAME_GAME.append(("대회 다름", r[9], r[1], x["p"], x["comp"], r[3]))
            break
if __name__ == "__main__" and "--cross" in sys.argv:
    print({k: (v[1], v[2]) for k, v in MATES.items()})
    for c in CROSS:
        if c[-1] != "같음" or "-v" in sys.argv: print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
    for s in SAME_GAME: print(s)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("chalm", "2017-01-05"), ("evelm", "2018-01-31"), ("rbllm", "2018-07-01"), ("evelm", "2019-07-25"), ("rbllm", "2020-09-30"),
         ("fullm", "2021-07-01"), ("leilm", "2022-07-01"), ("atalm", "2026-02-02"), ("atmlm", None)]
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {"chalm": "찰턴", "evelm": "에버턴", "rbllm": "RB 라이프치히", "fullm": "풀럼", "leilm": "레스터 시티", "atalm": "아탈란타", "atmlm": "아틀레티코 마드리드"}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CLUB_KO)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"358": "chalm", "29": "evelm", "23826": "rbllm", "931": "fullm", "1003": "leilm", "800": "atalm", "13": "atmlm"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_lookman import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["lookman_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, FM_ADDED=FM_ADDED, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const LOO_E={J(E)};\nconst LOO_M={J(M)};\nconst LOO_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_assists_not_used": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
