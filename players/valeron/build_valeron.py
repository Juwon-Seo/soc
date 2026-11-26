#!/usr/bin/env python3
"""Juan Carlos Valerón: raw/ -> valeron.json + src/data/vlr.js (판정 근거는 judgments.md)

  python3 players/valeron/build_valeron.py            # 파일 쓰기
  python3 players/valeron/build_valeron.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/valeron/build_valeron.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/valeron/build_valeron.py --root=<스크래치 복사본>   # 그 복사본의 src/data에 쓰기(검증용)

루이스 알베르토(build_luisalberto.py)·카소를라·마카이 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움,
Transfermarkt 경기 리포트), raw/tm_match_info.csv·tm_two_leg_ties.csv(합산), raw/fotmob_events.csv(FotMob 경기 이벤트, 2010-11~),
raw/ranks.txt(순위표), /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료).
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
OUT_JS = os.path.join(ROOT, "src", "data", "vlr.js")
OUT_JSON = os.path.join(HERE, "valeron.json")
ME = "후안 카를로스 발레론"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트, 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# 프로 리그 규칙(v1.159): 라스팔마스 1995-96은 세군다 B(3부, 비프로) → 그 시즌 코파 델 레이 1경기(1995.10.25 레가네스전, 1골)도 같이 제외(바디 플리트우드 FA컵 선례)
NONPRO_SEASON = {("472", "1995")}
ALL_GAMES = rd("tm_games.csv")
GAMES = [g for g in ALL_GAMES if (g["club_id"], g["seasonId"]) not in NONPRO_SEASON]
EXCLUDED_GAMES = [g for g in ALL_GAMES if (g["club_id"], g["seasonId"]) in NONPRO_SEASON]
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
MIN_FIX = {}   # 출전 분 고침 없음(Transfermarkt 그대로, judgments.md 2절)
# 도움 제외(일반 규칙 밖 개별 판정): 없음
EXCL_A = {}
# 2014-08 이후 Transfermarkt 단독 도움(FotMob 경기 이벤트에 도움자 없음) 중 다른 출처 2곳이 확인한 것
ADD_CONFIRMED = {
    "2647658|16": "2016.1.7 에이바르전(코파 델 레이 16강 1차전) 16분 아이타미 골: Sports Mole 경기 기사('second assist of the match')·Sky Sports 경기 라인업(발레론 도움 16분·60분)",
    "2647658|60": "2016.1.7 에이바르전 60분 와카소 골: Sports Mole('Valeron produced his second assist of the match to set up Mubarak Wakaso for 2-2')·Sky Sports 경기 라인업(도움 60분)",
}
GOAL_MIN_FIX = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES1", "ES2", "ES1P"}   # ES1P: 세군다 승격 플레이오프 = 리그 비중(카소를라·아스파스 선례, 골·도움 없음)
CUP = {"CDR"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 2·3·4라운드(재경기 표기 포함 단판)·16강
    if cid == "SUC": return "df"   # 수페르코파 = 국내컵 결승(두 경기)
    if cid == "CLQ": return "clq"
    if cid in ("UEQ", "UI"): return "elq"   # UEFA컵 예선·인터토토컵 = 유로파 예선(포를란·토레스 선례)
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 2000-01·2001-02 2차 조별('Group 2'·'Group 4') 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 2·3라운드·32강·16강
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
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]
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
    if cid in ("CL", "CLQ", "UEFA", "UEQ", "UI", "CDR", "SUC"):
        ag, et = 1, 1   # 모두 2016년 이전: UEFA 대회·코파 델 레이·수페르코파 원정 다득점·연장 있음(마카이 선례)
    elif cid == "ES1P":
        ag, et = 1, 1   # 골·도움 없음(행 없음) — 판정 불필요
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
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

def interp(tab, r):
    if r in tab: return tab[r]
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return int(tab[lo] + (tab[hi] - tab[lo]) * (r - lo) / (hi - lo) + 0.5)

# 세군다(스페인 2부): 기존 선수 자료(elo/ents.json)의 순위별 최빈값(루이스 알베르토 빌드와 같음)
ES2_KNOWN = {1: 1753, 2: 1712, 3: 1687, 4: 1674, 5: 1660, 6: 1654, 7: 1647, 8: 1640, 9: 1632, 10: 1623, 11: 1615, 12: 1610, 13: 1606, 14: 1601, 15: 1598, 16: 1595, 17: 1589, 18: 1580, 19: 1572, 20: 1567, 21: 1560, 22: 1553}

def model(lg, season, r, n):
    if lg == "ES2":
        return interp(ES2_KNOWN, r), f"세군다(2부) {season} {r}위"
    return None
RANK_LG = ["ES2"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정') — judgments.md 7절
MAN = {
    (key("CF Sóller"), "1997-98"): (1350, "스페인 3부(세군다 B) 1997-98 19위 (추정, 다른 선수 자료 스페인 3부 1350과 같음)"),
    # 2008년 7월 인터토토컵: 상대 수준은 직전 시즌(2007-08) 이스라엘 리그 최종 4위(영어 위키백과 2007-08 Israeli Premier League, 인터토토 2라운드 진출 자리)
    (key("Ihud Bnei Sakhnin"), "2008-09"): (1475, "이스라엘 2007-08 4위 (추정, 다른 선수 자료 이스라엘 2006-07 4위 1475와 같음)"),
}
ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    if (A ^ B) & {"b", "c", "ii", "madrileno", "atletico"}: return False   # 2군(바르셀로나 B·아틀레티코 마드릴레뇨 등)은 1군과 다른 팀
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
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "CLQ", "UEFA", "UEQ", "UI") else [eu]
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
    # Transfermarkt 리포트 날짜(= UTC를 마드리드 시간으로 바꾼 날짜). 카나리아 제도 홈경기도 같은 날짜를 씀:
    # 1990년대 카나리아 경기의 UTC 시각은 모두 마드리드 자정(22:00·23:00Z) 자리표시값이라 대서양 시간으로 바꾸면 하루 앞당겨지는 가짜 날짜가 됨(judgments.md 6절)
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
        if r["valeron_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
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
    isg, isa = e["valeron_scorer"] == "1", e["valeron_assist_other"] == "1"
    if e["valeron_self_assist"] == "1":
        EXCL_CNT["본인 도움"] += 1
    if e["valeron_own_goal_against_own_team"] == "1":
        judg.append(("본인 자책골(골 아님)", ldate(g), g["opponent"], e["minute"])); EXCL_CNT["본인 자책골"] += 1
        continue
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
    et = int("+" not in e["minute"] and mi > 90)   # 연장 골·도움(단판 또는 합산 2차전 연장, 코망·드로그바 선례)
    if et and g["gameState"] != "extra_time" and g["gameState"] != "penalty_shootout": sys.exit("연장 판정 이상 " + gid)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"].startswith("Penalty"): why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            k = why if tag not in EXCL_A else "개별 판정"
            EXCL_CNT[k] += 1; EXCL_LIST[k].append((d, opp, e["minute"], e["scorer"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - mi) <= 3]
            if not hit:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = [(gid, ts) for gid, ts in FM_ASSIST.items() if gid in G]   # FotMob 경기 이벤트에 발레론 도움 없음(0건)

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u)
for f in FM_ONLY: print("판정 필요(FotMob 단독 도움):", f)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
if UNDECIDED or missing_elo or FM_ONLY:
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

# ---------------------------------------------------------------- FotMob 골 대조(2010-11~)
FM_CMP = []
for gid, evs in FM_EV.items():
    if gid not in G: continue
    fg = sorted(int(r["time"]) for r in evs if r["valeron_scorer"] == "1" and r["pen_shootout_event"] != "True")
    tg = sorted(minute(e["minute"])[0] for e in EVENTS if e["gameId"] == gid and e["valeron_scorer"] == "1")
    if len(fg) != len(tg) or any(abs(a - b) > 1 for a, b in zip(fg, tg)):
        FM_CMP.append((gid, G[gid]["date_local_computed"], tg, fg))
if __name__ == "__main__" and "--fm" in sys.argv:
    print("FotMob 골 차이:", FM_CMP)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
import subprocess
def load_js(fn):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const ([A-Z0-9]+)_E=(\[.*?\]);\n", s, re.S)
    return (m.group(1), json.loads(m.group(2))) if m else (None, [])
try:   # git이 추적하는 기존 선수 파일만(병렬 작업 중인 새 선수 파일은 보지 않음)
    TRACKED = subprocess.run(["git", "-C", os.path.dirname(os.path.dirname(HERE)), "ls-files", "src/data"], capture_output=True, text=True).stdout.split()
    TRACKED = [os.path.basename(t) for t in TRACKED if t.endswith(".js") and not t.endswith("hon.js")]
except Exception:
    TRACKED = []
OTHERS = {}
for fn in TRACKED:
    if fn == "vlr.js" or not os.path.exists(os.path.join(ROOT, "src", "data", fn)): continue
    P, ent = load_js(fn)
    if P: OTHERS[fn] = ent
def cmp_rows(a, b, full=True):
    diffs = []
    if full and abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if full and (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if full and a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or (ta and tb and ta[1:] != tb[1:] and full) or (bool(ta) != bool(tb)):
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
ME_NAMES = ("valeron", "juan carlos valeron")
CROSS = []
for fn, ent in OTHERS.items():
    for x in ent:   # 같은 날짜·같은 상대(= 같은 팀 동료 자료)
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                CROSS.append(("같은 경기(동료)", fn, r[9], r[1], cmp_rows(r, x, full=False) or "같음"))
                break
    for x in ent:   # 동료 도움 → 발레론 골
        if x[0] == "a" and norm(x[13] or "") in ME_NAMES:
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append(("동료 도움→발레론 골", fn, x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:   # 발레론 도움 → 동료 골
        if r[0] == "a":
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and key(x[1]) == key(r[1]) and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            if hit: CROSS.append(("발레론 도움→동료 골", fn, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:   # Transfermarkt 발레론 도움을 뺀 동료 골(참고)
        if x[0] == "g":
            tm = [e for e in EVENTS if e["valeron_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and key(G[e["gameId"]]["opponent"]) == key(x[1]) and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 발레론 도움을 뺀 동료 골", fn, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # TM 동료 도움 → 발레론 골인데 동료 파일에 없음(참고)
        if e["valeron_scorer"] == "1" and e["gameId"] in G and e["assist_player"]:
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            mates = [x for x in ent if x[9] == d and key(x[1]) == key(G[e["gameId"]]["opponent"])]
            if mates and not any(x[0] == "a" and abs(x[4] - mi) <= 2 for x in mates):
                CROSS.append(("TM 동료 도움 → 발레론 골(동료 파일에 도움 없음, 참고)", fn, d, e["minute"], e["assist_player"], e["assist_type"]))
    # 상대 선수 자료: 같은 날짜, 상대가 발레론 팀(같은 경기 반대편) — Elo는 서로 다른 팀이라 비교 안 함, 날짜만 확인
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음" or c[0].startswith(("동료", "발레론")): print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("lpvn", "1997-07-01", "UD 라스팔마스", "1996~1997"), ("mlvn", "1998-07-01", "마요르카", "1997~1998"),
         ("atmvn", "2000-07-01", "아틀레티코 마드리드", "1998~2000"), ("depvn", "2013-07-14", "데포르티보 라코루냐", "2000~2013"),
         ("lpvn", None, "UD 라스팔마스", "2013~2016")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {"lpvn": "라스팔마스", "mlvn": "마요르카", "atmvn": "아틀레티코", "depvn": "데포르티보"}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in ("lpvn", "mlvn", "atmvn", "depvn"))
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TMC = {"472": "lpvn", "237": "mlvn", "13": "atmvn", "897": "depvn"}
for g in GAMES:
    if club_of(ldate(g)) != TMC[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
SPELL = collections.OrderedDict((k, [0, 0, 0, 0]) for k in ("lp1", "mlvn", "atmvn", "depvn", "lp2"))
def spell(d):
    k = club_of(d)
    return ("lp1" if d < "2000-01-01" else "lp2") if k == "lpvn" else k
for m in M: SPELL[spell(m[0])][0] += 1; SPELL[spell(m[0])][3] += m[3]
for r in E: SPELL[spell(r[9])][1 if r[0] == "g" else 2] += 1

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_valeron import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["valeron_assist_other"] == "1")
N_TM_G = sum(1 for e in EVENTS if e["gameId"] in G and e["valeron_scorer"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, SPELL=SPELL, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, N_TM_G=N_TM_G, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const VLR_E={J(E)};\nconst VLR_M={J(M)};\nconst VLR_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "excluded_games": [[g["date_local_computed"], g["opponent"], g["competitionId"], g["playedMinutes"], g["goals"], g["assists"]] for g in EXCLUDED_GAMES],
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in SPELL.items(): print(" ", k, v)
