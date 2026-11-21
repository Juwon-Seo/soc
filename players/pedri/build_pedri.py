#!/usr/bin/env python3
"""Pedri: raw/ -> pedri.json + src/data/pdr.js (판정 근거는 judgments.md)

  python3 players/pedri/build_pedri.py            # 파일 쓰기
  python3 players/pedri/build_pedri.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/pedri/build_pedri.py --cross    # 동료·같은 경기 자료 대조
  python3 players/pedri/build_pedri.py --fm       # FotMob 골 대조
  python3 players/pedri/build_pedri.py --root=<스크래치 복사본>   # 그 복사본의 src/data에 쓰기(검증용)

카라스코(build_carrasco.py) 빌드를 바탕으로 함. 접두어 PDR(pdr.js), 프리셋 id pedri.
입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/fotmob_playerMatches.csv(FotMob 선수 경기 목록),
raw/ranks.txt(순위표), /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
src/data/*.js(동료 자료 대조, git 추적 파일만). 판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections, subprocess
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
REPO = os.path.dirname(os.path.dirname(HERE))
ROOT = REPO
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):   # 스크래치 복사본에 쓰기(검증용)
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(REPO, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "pdr.js")
OUT_JSON = os.path.join(HERE, "pedri.json")
ME = "페드리"
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
MAP = {r["fotmob_matchId"]: r for r in rd("fotmob_tm_map.csv")} if os.path.exists(os.path.join(RAW, "fotmob_tm_map.csv")) else {}
FM_PM = {}   # tm gameId -> FotMob 선수 경기 목록 도움 수
_pm = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}
for g in GAMES:
    r = _pm.get(g["fotmobMatchId"])
    if r: FM_PM[g["gameId"]] = int(r["assists"] or 0)

# ---------------------------------------------------------------- 판정 표
MIN_FIX = {}     # 출전 분 고침 없음(Transfermarkt 그대로)
SCORE_FIX = {}   # 리포트 스코어 고침 없음
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유 (PK 유도·'Shot on goal'·자책골은 일반 규칙)
EXCL_A = {}
# 2014.8.1 이후 FotMob 이벤트·선수 경기 목록에 없지만 다른 출처 2곳 이상이 확인해 넣은 도움
ADD_CONFIRMED = {
    "3209301|68": "2020.7.8 레알 오비에도전 68분 루벤 카스트로 골: udlaspalmas.net 경기 기사('terminó con una asistencia del tinerfeño a Rubén Castro')·Target Scouting 경기 분석('managed to get one assist'); FotMob 도움 없음",
}
# FotMob 선수 경기 목록 도움 수가 Transfermarkt 도움을 확인하는 경기(FotMob 이벤트는 도움자 빈칸) — 로드리구·비니시우스·칸드레바 선례
PM_CONFIRMED = {
    "3496461|37": "2021.3.10 PSG전(챔스 16강 2차전) 37분 메시 골: FotMob 이벤트 도움자 빈칸, FotMob 선수 경기 목록 도움 1",
}
# FotMob에만 있는 도움(판정 끝남, 넣지 않음) — judgments.md 4절
FM_ONLY_DECIDED = {
    "3209287": "2020.7.5 폰페라디나전 90+3분 나르바에스 골(3:0): FotMob 이벤트만 페드리 도움(같은 경기 2:0 골도 페드리로 적음), FotMob 선수 경기 목록 도움 1, Transfermarkt는 알렉스 수아레스 도움, udlaspalmas.net 경기 기사는 '상대 수비 혼란'으로 적고 페드리 언급 없음 — 넣지 않음",
    "3610368": "2022.2.20 발렌시아전 63분 오바메양 골(1:4): FotMob은 페드리 도움, Transfermarkt는 'Shot on goal'(페드리 슈팅이 막힌 뒤 리바운드) — 리바운드 규칙으로 넣지 않음(오바메양 자료도 도움 없음)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES2", "ES1"}
CUPS = {"CDR"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:   # 코파 델 레이: 16강까지 dc / 8강 dk / 준결승 dsf / 결승 df
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "SUC":   # 수페르코파(4팀): 준결승 dsf, 결승 df
        return "dsf" if r.startswith("semi") else "df"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 2024-25부터 리그 페이즈(Transfermarkt 'Group Stage')
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 녹아웃 플레이오프(intermediate stage)·16강·8강
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
        oh, oa = map(int, re.match(r"(\d+):(\d+)", o["final"]).groups())
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "EL"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CDR":   # 코파 델 레이: 원정 다득점 2018-19까지, 2차전 연장
        ag, et = int(d < "2019-07-01"), 1
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
ENTS_BY_D = collections.defaultdict(list)
for x in ENTS: ENTS_BY_D[x["date"]].append(x)

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    if d[:7] in ("2020-07", "2020-08"): s = 2019   # 코로나로 늦게 끝난 2019-20 시즌
    return f"{s}-{str(s + 1)[2:]}"

def season_of(d, cid):
    return season_eu(d)

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 세군다 2019-20(22팀): 같은 시즌 다른 선수 자료 순위값(5위 1660·7위 1647·11위 1615·15위 1599·16위 1595·18위 1581·21위 1563·22위 1554)
# 사이 순위는 이웃 두 값 사이 직선(13위 1607·14위 1603·19위 1575)
ES2_1920 = {5: 1660, 7: 1647, 11: 1615, 15: 1599, 16: 1595, 18: 1581, 21: 1563, 22: 1554}
def es2_1920(r):
    if r in ES2_1920: return ES2_1920[r]
    lo = max(k for k in ES2_1920 if k < r); hi = min(k for k in ES2_1920 if k > r)
    return round(ES2_1920[lo] + (ES2_1920[hi] - ES2_1920[lo]) * (r - lo) / (hi - lo))

def model(lg, season, r, n):
    if lg == "ES2" and season == "2019-20" and n == 22:
        return es2_1920(r), f"세군다 2019-20 {r}위"
    return None
RANK_LG = ["ES2"]

MAN = {}
ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d); se = season_of(d, cid)
    dd = Date.fromisoformat(d)
    same = []
    for delta in (-1, 0, 1):
        dx = Date.fromordinal(dd.toordinal() + delta).isoformat()
        same += [x for x in ENTS_BY_D.get(dx, []) if key(x["opp"]) == k or _sub(key(x["opp"]), k)]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]",
                        sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [se, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL") else [se]
    for s in seasons:
        if (k, s) in TABLE:
            cand = TABLE[(k, s)]
            (e, lv), _ = collections.Counter(cand).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, se) in MAN:
        e, lv = MAN[(k, se)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
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
    return g["date_local_computed"]

for g in GAMES:   # 리포트가 있는 경기는 리포트 날짜와 같은지 확인
    if g["date_local_tm_report"] and g["date_local_tm_report"] != g["date_local_computed"]:
        sys.exit("날짜 불일치 " + g["gameId"])

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
        if r["pedri_assist"] == "1" and r["pen_shootout_event"] != "True":
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
        missing_elo.add((opp, season_of(d, cid), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["pedri_scorer"] == "1", e["pedri_assist_other"] == "1"
    if e["pedri_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag, ldate(g))); EXCL_CNT["본인 도움"] += 1
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, SCORE_FIX.get(tag, e["score_home_away_after"]).split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = int(ko == 1 and tie is None and int(e["minute"].split("+")[0]) > 90)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if not ours:
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
        hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
        if tag in ADD_CONFIRMED:
            judg.append(("도움 넣음(다른 출처 2곳)", d, opp, e["minute"], e["scorer"], ADD_CONFIRMED[tag]))
        elif tag in PM_CONFIRMED:
            judg.append(("도움 넣음(FotMob 선수 경기 목록)", d, opp, e["minute"], e["scorer"], PM_CONFIRMED[tag]))
        elif not hit:
            UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
        else:
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and len(ts) > used_fm.get(gid, 0) + sum(1 for k in list(ADD_CONFIRMED) + list(PM_CONFIRMED) if k.startswith(gid + "|")):
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

# FotMob 선수 경기 목록 도움 수 대조(경기별)
PM_DIFF = []
for gid in G:
    mine = sum(1 for r in E if r[0] == "a" and r[9] == ldate(G[gid]))
    if gid in FM_PM and FM_PM[gid] != mine:
        PM_DIFF.append((ldate(G[gid]), G[gid]["opponent"], "FotMob 선수 경기 목록", FM_PM[gid], "이 계산기", mine))

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY, EXCL_CNT)
    for k, v in EXCL_LIST.items(): print(k, v)
    print("FotMob 선수 경기 목록 도움 수 차이:", PM_DIFF)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["pedri_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local_computed"])); continue
    fg = [r for r in FM_EV[gid] if r["pedri_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
TRACKED = subprocess.run(["git", "-C", REPO, "ls-files", "src/data"], capture_output=True, text=True).stdout.split()
OTHERS = {}
for fn in TRACKED:
    b = os.path.basename(fn)
    if not b.endswith(".js") or b in ("hon.js", "pdr.js"): continue
    t = open(os.path.join(REPO, fn), encoding="utf-8").read()
    m = re.search(r"const ([A-Z0-9]+)_E=(\[.*?\]);\n", t, re.S)
    if m: OTHERS[b] = json.loads(m.group(2))
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    if a[11] != b[11]: diffs.append(f"표시 분 {a[11]}/{b[11]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
def same_name(a, b):
    A, B = norm(a).split(), norm(b).split()
    if not A or not B: return False
    return set(A) <= set(B) or set(B) <= set(A) or (A[-1] == B[-1] and A[0][0] == B[0][0])
CLUB_TOKEN = {"472": "palmas", "131": "barcelona"}
GAME_BY_D = {ldate(g): g for g in GAMES}
CROSS, SAME_GAME, VS = [], [], []
for fn, ent in OTHERS.items():
    for x in ent:
        g = GAME_BY_D.get(x[9])
        if not g: continue
        same_opp = key(g["opponent"]) == key(x[1]) or _sub(key(g["opponent"]), key(x[1]))
        if same_opp:   # 같은 팀 동료(같은 상대)
            for r in E:
                if r[9] == x[9] and (r[3] != x[3] or r[2] != x[2] or r[12] != x[12] or r[7] != x[7]):
                    SAME_GAME.append((fn, x[9], x[1], f"대회 {r[3]}/{x[3]} Elo {r[2]}/{x[2]} lv {r[12]}/{x[12]} 단판 {r[7]}/{x[7]}"))
            if x[0] == "g":   # 페드리 도움 → 동료 골
                for r in E:
                    if r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 3:
                        CROSS.append(("페드리 도움→" + fn + " 골", x[9], x[4], r[13], cmp_rows(r, x) or "같음"))
            if x[0] == "a" and "pedri" in norm(str(x[13])):
                hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3]
                CROSS.append((fn + " 도움→페드리 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        elif CLUB_TOKEN[g["club_id"]] in x[1].lower() and "espanyol" not in x[1].lower():
            VS.append((fn, x[9], x[0], x[1], x[4], x[5], x[6], x[3], x[7]))   # 상대 팀 선수 기록
# 계산기에 있는 바르셀로나 동료: 파일 → 이름
MATES = {"mes.js": "Lionel Messi", "grz.js": "Antoine Griezmann", "dem.js": "Ousmane Dembélé", "lew.js": "Robert Lewandowski",
         "rap.js": "Raphinha", "yam.js": "Lamine Yamal", "aub.js": "Pierre-Emerick Aubameyang"}
CROSS = [c for c in CROSS if not c[0].startswith("페드리 도움→") or same_name(MATES.get(c[0].split("→")[1].split(" ")[0], "?"), c[3])]
for e in EVENTS:
    if e["gameId"] not in G: continue
    d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
    for fn, nm in MATES.items():
        ent = OTHERS[fn]
        if e["pedri_assist_other"] == "1" and same_name(nm, e["scorer"]):
            mine = [r for r in E if r[0] == "a" and r[9] == d and abs(r[4] - mi) <= 2]
            theirs = [x for x in ent if x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 2]
            if not mine: CROSS.append(("TM 페드리 도움을 뺀 동료 골", fn, d, e["minute"], e["assist_type"], "동료 골 행 " + ("있음" if theirs else "없음")))
            elif not theirs: CROSS.append(("페드리 도움인데 동료 골 행 없음", fn, d, e["minute"]))
        if e["pedri_scorer"] == "1" and e["assist_player"] and same_name(nm, e["assist_player"]):
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 페드리 골, 동료 파일에 도움 행 없음", fn, d, e["minute"], e["assist_type"]))
for fn, nm in MATES.items():
    for x in OTHERS[fn]:
        if x[0] == "a" and "pedri" in norm(str(x[13])) and not any(r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3 for r in E):
            CROSS.append(("동료 파일 '페드리 골' 도움인데 페드리 골 행 없음", fn, x[9], x[4]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s_ in sorted(set(SAME_GAME)): print("같은 경기 차이:", s_)
    print("상대 팀 선수 기록", len(VS))
    for v in sorted(VS, key=lambda v: v[1]): print("  ", v)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("lpapd", "2020-08-01", "UD 라스팔마스", "2019~2020"), ("fcbpd", None, "바르셀로나", "2020~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != {"472": "lpapd", "131": "fcbpd"}[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_pedri import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["pedri_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const PDR_E={J(E)};\nconst PDR_M={J(M)};\nconst PDR_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game_diffs": sorted(set(SAME_GAME)), "vs_rows": VS, "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY,
               "fotmob_playermatches_assist_diffs": PM_DIFF, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
