#!/usr/bin/env python3
"""호아킨 산체스(Joaquín): raw/ -> joaquin.json + src/data/joa.js (판정 근거는 judgments.md)

  python3 players/joaquin/build_joaquin.py              # 파일 쓰기
  python3 players/joaquin/build_joaquin.py --debug      # Elo 출처 로그·도움 판정 목록
  python3 players/joaquin/build_joaquin.py --cross      # 동료 자료 대조
  python3 players/joaquin/build_joaquin.py --fm         # FotMob 골 대조
  python3 players/joaquin/build_joaquin.py --root=DIR   # (맨 앞) 다른 저장소 복사본의 src/data에 쓰기

카소를라(build_cazorla.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움,
Transfermarkt 경기 리포트), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트),
raw/ranks.txt(순위표), /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
src/data/*.js(같은 경기 동료 자료 대조). 개별 판정 표는 judg_joaquin.py, 설명 문장은 note_joaquin.py.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date, datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(os.path.dirname(os.path.dirname(HERE)), "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "joa.js")
OUT_JSON = os.path.join(HERE, "joaquin.json")
ME = "호아킨 산체스"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트, 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

MAD = ZoneInfo("Europe/Madrid")
def local_date(g):
    """리포트 날짜(현지)가 있으면 그것, 없으면 API UTC 시각을 스페인·이탈리아 시간으로 바꾼 날짜(리그 경기만 해당)"""
    if g["date_local_tm_report"]: return g["date_local_tm_report"]
    return datetime.fromisoformat(g["date_utc"]).astimezone(MAD).date().isoformat()

GAMES = rd("tm_games.csv")
for g in GAMES: g["date_local"] = local_date(g)
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
IS_JOA = lambda s: s.strip().lower() in ("joaquin", "joaquín", "joaquin sanchez", "joaquín sánchez")

sys.path.insert(0, HERE)
from judg_joaquin import EXCL_A, ADD_CONFIRMED, MIN_FIX, ADD_M, INCOMPLETE_REPORTS, MAN_RAW, BEFORE_FIX

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ES1", "ES2", "IT1"}
CUP = {"CDR", "CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "SUC": return "df"   # 수페르코파 = 국내컵 결승 비중(두 경기)
    if cid in ("ELQ", "CLQ"):
        return "clq" if cid == "CLQ" else "elq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 2·3라운드·32강(intermediate stage)·16강·8강
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 2라운드(32강)·intermediate stage·16강·8강
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
    if cid in ("CL", "CLQ", "EL", "ELQ", "UEFA"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid in ("CDR", "SUC"):   # 코파 델 레이·수페르코파: 원정 다득점 2018-19까지, 연장 있음
        ag, et = int(d < "2019-07-01"), 1
    elif cid == "CIT":   # 코파 이탈리아 준결승: 원정 다득점 2021-22까지, 2차전 연장
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
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))

def half_up(x): return int(x + 0.5)

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

def mid(tab, r):
    if r in tab: return tab[r], False
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up((tab[a] + tab[b]) / 2) if (b - a) == 2 else half_up(tab[a] + (tab[b] - tab[a]) * (r - a) / (b - a)), True

SEG = [1753, 1712, 1687, 1674, 1660, 1654, 1647, 1640, 1632, 1623, 1615, 1610, 1606, 1601, 1598, 1595, 1589, 1580, 1572, 1567, 1560, 1553]  # 세군다 22팀(기존 고정값)
LL_INTERP = set()

def model(lg, season, r, n):
    if lg == "ES1":
        v, it = mid(ents_map("라리가", season), r)
        if v is None: return None
        if it: LL_INTERP.add(("라리가", season, r, v))
        return v, f"라리가 {season} {r}위"
    if lg == "IT1":
        v, it = mid(ents_map("세리에A", season), r)
        if v is None: return None
        if it: LL_INTERP.add(("세리에A", season, r, v))
        return v, f"세리에A {season} {r}위"
    if lg == "ES2":
        if n == 22: return SEG[r - 1], f"세군다(2부) {season} {r}위"
        return None
    return None
RANK_LG = ["ES1", "ES2", "IT1"]

MAN = {(key(t), s): v for (t, s), v in MAN_RAW.items()}

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
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "CLQ", "EL", "ELQ", "UEFA") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
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
    return g["date_local"]

M = []
for g in GAMES:
    mins = MIN_FIX[g["gameId"]][0] if g["gameId"] in MIN_FIX else int(g["playedMinutes"])
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), mins])
for d, opp, comp, mins, _why in ADD_M:   # Transfermarkt 'not in squad'이지만 경기 단위 출처로 출전이 확인된 경기(90분 추정)
    M.append([d, opp, comp, mins, 1])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["assist"] and IS_JOA(r["assist"].replace("assist by", "")):
            FM_ASSIST[gid].append(int(r["minute"]) + int(r["overload"] or 0))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
PENDING = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

# 골 전 스코어: 리포트 골 순서대로 득점 팀별로 셈
BEFORE, SCORE_FIX = {}, []
EV_BY = collections.defaultdict(list)
for i, e in enumerate(EVENTS): EV_BY[e["gameId"]].append(i)
for gid, idx in EV_BY.items():
    h = a = 0
    for i in idx:
        BEFORE[i] = (h, a)
        if EVENTS[i]["side"] == "home": h += 1
        else: a += 1
        if EVENTS[i]["score_home_away_after"] != f"{h}-{a}" and gid in G:
            SCORE_FIX.append((gid, EVENTS[i]["minute"], EVENTS[i]["score_home_away_after"], f"{h}-{a}"))
    if gid in INFO and gid in G and G[gid]["gameState"] != "penalty_shootout":
        fh, fa = map(int, INFO[gid]["final"].split(":"))
        if (h, a) != (fh, fa) and gid not in INCOMPLETE_REPORTS:
            sys.exit(f"리포트 골 수와 최종 스코어 다름: {gid} {(h, a)} {(fh, fa)}")

for i, e in enumerate(EVENTS):
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["joaquin_scorer"] == "1", e["joaquin_assist_other"] == "1"
    if e["joaquin_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag)); EXCL_CNT["본인 도움"] += 1
    if not (isg or isa): continue
    if gid in INCOMPLETE_REPORTS: sys.exit("골 목록이 불완전한 리포트에 호아킨 기록: " + gid)
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = BEFORE_FIX.get(tag, BEFORE[i])
    side_home = e["side"] == "home"
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
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
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
            if not hit:
                PENDING.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"], cid)); continue
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    n_tm = sum(1 for e in EVENTS if e["gameId"] == gid and e["joaquin_assist_other"] == "1")
    if gid in G and len(ts) > n_tm:
        FM_ONLY.append((gid, G[gid]["date_local"], G[gid]["opponent"], ts, n_tm))

if PENDING:
    for p in PENDING: print("판정 필요(2014.8 이후 FotMob에 없는 도움):", p)
    if "--force" not in sys.argv: sys.exit(1)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY, EXCL_CNT)
    print("리포트 스코어 표시 고침:", [x for x in SCORE_FIX])
    for k, v in EXCL_LIST.items(): print(k, v)
    print("리그 보간:", sorted(LL_INTERP))
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["joaquin_scorer"] == "1" and e["gameId"] in G and G[e["gameId"]]["date_local"] >= "2010-08-01":
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if IS_JOA(r["scorer"]) and r["own_goal"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["minute"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["minute"]) + int(r["overload"] or 0))):
        tpk = t["penalty"] == "1"; fpk = f["goal_desc"] == "penalty"
        tm_min = minute(t["minute"])[0]; fm_min = int(f["minute"]) + int(f["overload"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["minute"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["goal_desc"], f["minute"], f["overload"], f["goal_desc"]))
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if IS_JOA(r["scorer"]) and r["own_goal"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local"] if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"David Villa": ("vil.js", "VIL", "2006-07-01", "2010-07-01", ("david villa",)),
         "David Silva": ("sil.js", "SIL", "2006-07-01", "2010-07-15", ("david silva",)),
         "Juan Mata": ("mat.js", "MAT", "2007-07-01", "2011-07-01", ("juan mata",)),
         "Isco": ("isc.js", "ISC", "2011-07-01", "2013-07-01", ("isco",)),
         "Santi Cazorla": ("caz.js", "CAZ", "2011-07-26", "2012-08-07", ("santi cazorla",)),
         "Ruud van Nistelrooy": ("nis.js", "NIS", "2011-07-01", "2012-07-01", ("ruud van nistelrooy",)),
         "Mohamed Salah": ("sal.js", "SAL", "2015-01-01", "2015-07-01", ("mohamed salah",)),
         "Juan Cuadrado": ("cua.js", "CUA", "2013-07-01", "2015-02-02", ("juan cuadrado",)),
         "Mario Gómez": ("gom.js", "GOM", "2013-07-01", "2015-07-01", ("mario gomez",)),
         "Josip Ilicic": ("ili.js", "ILI", "2013-07-01", "2015-07-01", ("josip ilicic",)),
         "Nabil Fekir": ("fek.js", "FEK", "2019-07-01", "2023-07-01", ("nabil fekir",)),
         "Roberto Soldado": ("sol.js", "SOL", "2010-07-01", "2011-07-01", ("roberto soldado",)),
         "Pablo Aimar": ("aim.js", "AIM", "2006-07-01", "2006-08-31", ("pablo aimar",)),
         "Fernando Morientes": ("mor.js", "MOR", "2006-07-01", "2009-07-01", ("fernando morientes",)),
         "Ricardo Oliveira": ("oli.js", "OLI", "2003-07-01", "2006-07-01", ("ricardo oliveira",))}
MATE_E = {}
for nm, v in list(MATES.items()):
    fn = os.path.join(ROOT, "src", "data", v[0])
    if not os.path.exists(fn):
        del MATES[nm]; continue
    s = open(fn, encoding="utf-8").read()
    if not re.search(r"const " + v[1] + r"_E=", s): del MATES[nm]; continue
    MATE_E[nm] = load_js(v[0], v[1])
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
JOA = lambda s: IS_JOA(norm(s or ""))
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    names = MATES[nm][4]
    for r in E:
        if r[0] == "a" and norm(r[13]) in names:
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("호아킨 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and JOA(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→호아킨 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    for x in ent:   # Transfermarkt 호아킨 도움을 이 계산기에서 뺀 동료 골(참고)
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["joaquin_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 호아킨 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # TM 리포트상 동료 도움 → 호아킨 골인데 동료 파일에 없는 것(참고)
        if e["joaquin_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) in names:
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 호아킨 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
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
CLUBS = [("betjq", "2006-07-01", "레알 베티스", "2000~2006"), ("valjq", "2011-07-01", "발렌시아", "2006~2011"),
         ("maljq", "2013-07-01", "말라가", "2011~2013"), ("fiojq", "2015-07-01", "피오렌티나", "2013~2015"),
         ("betjq", None, "레알 베티스", "2015~2023")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_ID = {"150": "betjq", "1049": "valjq", "1084": "maljq", "430": "fiojq"}
for g in GAMES:
    if club_of(ldate(g)) != CLUB_ID[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
SPANS = []
prev = ""
for k, u, n, y in CLUBS:
    SPANS.append((k, prev, u or "9999", n, y)); prev = u
ST = collections.OrderedDict()
for k, lo, hi, n, y in SPANS:
    st = [0, 0, 0, 0]
    for m in M:
        if lo <= m[0] < hi: st[0] += 1; st[3] += m[3]
    for r in E:
        if lo <= r[9] < hi: st[1 if r[0] == "g" else 2] += 1
    ST[(n, y)] = st

# ---------------------------------------------------------------- 설명(NOTE)
from note_joaquin import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["joaquin_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC, ELO_LOG=ELO_LOG, MAN=MAN_RAW))
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
        if b[0] < a[0] or b[1] < a[1]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
    for r in rs:
        if d in mm and mm[d][1] != r[1]: problems.append(("상대 이름 다름", d, r[1], mm[d][1]))
        if d in mm and mm[d][2] != r[3]: problems.append(("대회 다름", d, r[3], mm[d][2]))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const JOA_E={J(E)};\nconst JOA_M={J(M)};\nconst JOA_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
