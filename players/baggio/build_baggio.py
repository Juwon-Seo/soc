#!/usr/bin/env python3
"""Roberto Baggio: raw/ -> baggio.json + src/data/bag.js (판정 근거는 judgments.md)

  python3 players/baggio/build_baggio.py            # 파일 쓰기
  python3 players/baggio/build_baggio.py --debug    # Elo 출처 목록
  python3 players/baggio/build_baggio.py --cross    # 같은 경기 다른 선수 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/ranks.txt(순위표), src/data/*.js(git 추적 파일: 같은 경기·같은 팀-시즌 값, 동료 대조),
      tools/league_rank_apply.py(라벨 → Elo, v1.226 순위 규칙).
바티스투타 build 스크립트(같은 수집 형식)를 바탕으로 함.
상대 Elo: 같은 경기 다른 선수 자료 → 같은 팀·시즌 다른 선수 자료 → 순위표 라벨. 순위 라벨이 있는 행은 마지막에
league_rank_apply.py 의 value()로 값을 정함(--apply 를 돌려도 이 자료 행은 바뀌지 않게).
"""
import csv, json, os, re, sys, unicodedata, collections, io, contextlib, subprocess
from datetime import date as Date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
OUT_JS = os.path.join(ROOT, "src", "data", "bag.js")
OUT_JSON = os.path.join(HERE, "baggio.json")
ME = "로베르토 바조"
INCLUDE_REGGIANA = True   # 1985.3.17 레지아나전(영어 위키백과 1984-85 비첸차 시즌 문서 경기 기록, judgments.md 1절)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 판정 표
MIN_FIX = {}
# 골 고침: gameId|TM 분 -> (분, 표시 분, 골 전 우리, 상대)
GOAL_FIX = {
    # 1984.10.21 모데나: TM 분 '121'(자리값)·맨 앞 순서 → 영어 위키백과 시즌 문서 45분. 다른 골 7분(모데나)·17분(론돈) 뒤라 1-1
    "2953692|121": (45, 0, 1, 1),
}
EXCL_G = {}
# 도움 제외: gameId|분 -> 이유 (judgments.md 4절)
EXCL_A = {
    "1099286|70": "PK 유도(Penalty: Fouled player, 스킬라치 PK)",
    "2216337|47": "슈팅 리바운드(Shot on goal, 플랫)",
    "2216726|57": "슈팅 리바운드(Shot on goal, 스킬라치)",
    "2217112|62": "슈팅 리바운드(Shot on goal, 델로글리오)",
    "2987137|70": "슈팅 리바운드(Shot on goal, 라바넬리)",
    "2216130|25": "상대 자책골(S. 펠레그리니) + 슈팅 리바운드(Shot on goal)",
    "2215665|23": "상대 자책골(말탈리아티) 유도(프리킥)",
    "2216012|85": "상대 자책골(페리) 유도(프리킥)",
}
DATE_FIX = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT3A"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE or cid == "ITPO": return "lg"   # 세리에A 플레이오프: 인자기·호나우두·비에리 선례
    if cid == "CIT":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "SCI": return "df"
    if cid == "UI": return "elq"     # 인터토토컵(토니 같은 경기 선례)
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("quarter"): return "clk"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "EPP":   # 컵위너스컵: 호나우두·피구·네드베드·바티스투타 선례
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1   # 단판(ITPO 단판 플레이오프·코파 이탈리아 단판·수페르코파)

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(" ")[0].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    if g["competitionId"] == "ITPO":
        return [leg, home, fu, ft, 1, 0]   # 1999 UEFA컵 플레이오프: 원정 다득점·연장 없음(인자기 같은 대회 선례)
    return [leg, home, fu, ft, 1, 1]       # UEFA 대회·코파 이탈리아: 원정 다득점·연장

# ---------------------------------------------------------------- 이름 정규화
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

ALIAS = {}
with open(os.path.join(ROOT, "elo", "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
MANUAL_ALIAS = {"inter milan": "inter", "ac parma": "parma", "parma calcio 1913": "parma", "parma fc": "parma",
                "brescia calcio": "brescia calcio", "fc internazionale": "inter"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

# ---------------------------------------------------------------- 다른 선수 자료(git 추적 파일만: 병행 판정자 새 파일 제외)
def tracked():
    try:
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split()
        s = {os.path.basename(x) for x in out}
        if s: return s
    except Exception: pass
    return None
TRACKED = tracked()
def load_js(fn, P, part="E"):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + "_" + part + r"=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
OTHERS = {}
for fn in sorted(os.listdir(os.path.join(ROOT, "src", "data"))):
    if not fn.endswith(".js") or fn in ("hon.js", "clubcolors.js", "bag.js"): continue
    if TRACKED is not None and fn not in TRACKED: continue
    try: OTHERS[fn] = load_js(fn, fn[:-3].upper())
    except Exception: continue
ENTS = [dict(p=fn, opp=r[1], elo=r[2], date=r[9], lv=r[12], comp=r[3]) for fn, ent in OTHERS.items() for r in ent]

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 같은 팀·시즌(다른 선수 자료): 라벨의 시즌을 씀
SEAS_PAT = re.compile(r"(\d{4}-\d{2}|\d{4})")
TABLE = collections.defaultdict(collections.Counter)
for e in ENTS:
    lv = str(e["lv"] or "")
    m = SEAS_PAT.search(lv.split(" (")[0])
    if not m or not re.search(r"\d+위", lv.split(" (")[0]): continue
    TABLE[(key(e["opp"]), m.group(1))][(e["elo"], lv)] += 1

# ---------------------------------------------------------------- 순위 라벨 → Elo (tools/league_rank_apply.py)
_RA = {"__file__": os.path.join(ROOT, "tools", "league_rank_apply.py"), "__name__": "x"}
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_RA["__file__"], encoding="utf-8").read().split("if __name__ == '__main__':")[0], "rank", "exec"), _RA)
sys.argv = _argv
def label_value(lv, d):
    p = _RA["parse"](lv, d)
    return _RA["value"](*p) if p else None

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        code = p[0].split("(")[0]
        RANKS[(code, p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))
# 순위 고침(순위표 원문 확인, judgments.md 6절)
RANK_FIX = {}
# 나라·리그 이름(라벨)
FOREIGN = {"A1": ("오스트리아 1부", "Austrian Bundesliga"), "BE1": ("벨기에 1부", "Belgian First Division"),
           "BU1": ("불가리아 1부", "A Group"), "GR1": ("그리스 1부", "Alpha Ethniki"), "NO1": ("노르웨이 1부", "Tippeligaen"),
           "PL1": ("폴란드 1부", "I liga"), "RU1": ("러시아 1부", "Russian Top League"), "SU1": ("소련 1부", "Soviet Top League"),
           "LET1": ("라트비아 1부", "Virslīga"), "ZYP1": ("키프로스 1부", "Cypriot First Division")}
BIGL = {"ES1": "라리가", "FR1": "리그1", "L1": "분데스리가", "PO1": "포르투갈 1부"}

def make_label(code, season, r, n):
    y = int(season[:4]) + 1 if "-" in season else int(season)
    if code == "IT1":
        return f"세리에A {season} {r}위" + ("" if n == 18 else f"/{n}팀")
    if code == "IT2":
        return f"세리에B {season} {r}위/{n}팀"
    if code in ("IT3A", "IT3B"):
        return f"이탈리아 3부 {season} {r}위/{n}팀 (Serie C1 Girone {code[-1]}, 리그 수준 추정)"
    if code in BIGL:
        lg = BIGL[code]
        dflt = _RA["ERA"]["teams"](lg, y)
        return f"{lg} {season} {r}위" + ("" if n == dflt else f"/{n}팀")
    if code in FOREIGN:
        nm, ln = FOREIGN[code]
        return f"{nm} {season} {r}위/{n}팀 ({ln})"
    sys.exit("라벨 없음 " + code)

# 순위표 파일에 없는 상대(순위 확인: judgments.md 6절)
MAN_LV = {}
MAN_LV[(key("IFK Göteborg"), "1996")] = "스웨덴 1부 1996 1위/14팀 (Allsvenskan)"   # 영어 위키백과 1996 Allsvenskan, 우승

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)
CAL = {"NO1", "RU1", "SU1", "LET1"}

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
    seasons = [eu, d[:4]] if cid in ("CL", "CLQ", "UEFA", "EPP", "UI") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = TABLE[(k, s)].most_common(1)[0]
            ELO_SRC["같은 팀·시즌 다른 선수 자료"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    if (k, eu) in MAN_LV or (k, d[:4]) in MAN_LV:
        lv = MAN_LV.get((k, eu)) or MAN_LV[(k, d[:4])]
        ELO_SRC["순위표 라벨"] += 1; ELO_LOG.append((d, opp, None, lv, "man"))
        return None, lv
    # 순위표: 이탈리아 리그는 8월 1일 시즌, 다른 나라는 그 경기 때 진행 중인 시즌(달력 연도 리그는 그해)
    order = ["IT1", "IT2", "IT3A", "IT3B"] if cid not in ("CL", "CLQ", "UEFA", "EPP", "UI") else list(BIGL) + list(FOREIGN)
    for code in order:
        s = d[:4] if code in CAL else eu
        t = RANKS.get((code, s))
        if t and k in t:
            r, n = RANK_FIX.get((code, s, k), t[k])
            lv = make_label(code, s, r, n)
            ELO_SRC["순위표 라벨"] += 1; ELO_LOG.append((d, opp, None, lv, "rank " + code))
            return None, lv
    return None

# ---------------------------------------------------------------- 출전
def sched_date(s):
    return datetime.strptime(s.split(" ")[1], "%d/%m/%Y").strftime("%Y-%m-%d") if s else ""
def ldate(g):
    return DATE_FIX.get(g["gameId"]) or g["date_local_tm_report"] or sched_date(g["date_tm_schedule"])
def clean_opp(o): return re.sub(r"\s*\(- ?\d{4}\)\s*$", "", o).strip()

M = []
for g in GAMES:
    M.append([ldate(g), clean_opp(g["opponent"]), comp_of(g["competitionId"], g["round"]),
              MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])
EXTRA_M, EXTRA_G = [], []
if INCLUDE_REGGIANA:
    # 세리에C1 1984-85 24라운드 비첸차 3-0 레지아나(TM '명단 외'): 파시울로 30·론돈 41·바조 81 PK. 출전 분 자료 없음 → 90분 추정
    EXTRA_M.append(["1985-03-17", "AC Reggiana", "lg", 90, 1])
    EXTRA_G.append(("1985-03-17", "AC Reggiana", "IT3A", "lg", 81, 0, 2, 0, 1))
M += EXTRA_M
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, d, cid)); res = (0, "?")
    elo, lv = res
    v = label_value(lv, d) if lv != "?" else None
    if v is not None:
        if elo is not None and elo != v: judg.append(("Elo 라벨값으로 맞춤", d, opp, elo, v, lv))
        elo = v
    if elo is None:
        missing_elo.add((opp, d, cid, lv)); elo = 0
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["baggio_scorer"] == "1", e["baggio_assist_other"] == "1", e["baggio_self_assist"] == "1"
    if iss: judg.append(("본인 PK 골의 본인 도움(도움 아님)", ldate(g), e["minute"]))
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
    tag = f"{gid}|{e['minute']}"
    if tag in GOAL_FIX:
        mi, dm, gf, ga = GOAL_FIX[tag]; judg.append(("골 시각·스코어 고침", gid, e["minute"], GOAL_FIX[tag]))
    et = int(mi > 90 and (not dm or int(str(dm).split("+")[0]) >= 105))
    if et and g["gameState"] == "regularly_terminated": sys.exit("연장 판정 이상 " + gid + " " + e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = clean_opp(g["opponent"])
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal", "Deflected"):
            sys.exit("도움 유형 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

for d, o, c, comp, mi, dm, gf, ga, pk in EXTRA_G:
    add_row("g", mi, dm, gf, ga, pk, 0, None, comp, 0, d, o, c, 0)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

def sort_min(r):
    return r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5
rows.sort(key=lambda r: (r[9], sort_min(r), 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)
    for j in judg:
        if j[0].startswith("Elo"): print(j)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    return diffs
CROSS, SAMEGAME = [], []
for fn, ent in OTHERS.items():
    for r in E:
        if r[0] != "a": continue
        hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1])]
        if hit: CROSS.append(("바조 도움→" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:
        if x[0] == "a" and norm(str(x[13])) in (norm("Roberto Baggio"), "baggio", "r baggio"):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn + " 도움→바조 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                SAMEGAME.append((fn, r[9], r[1], tuple(dd) or "같음"))
                break
SAMEGAME = sorted(set(SAMEGAME))
# 같은 경기 출전 행(M) 대조: 날짜·대회
MCROSS = []
for fn in OTHERS:
    try: Mo = load_js(fn, fn[:-3].upper(), "M")
    except Exception: continue
    for x in Mo:
        for m in M:
            if m[0] == x[0] and key(m[1]) != key(x[1]) and False: pass
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s_ in SAMEGAME:
        if s_[-1] != "같음": print("같은 경기 차이", s_)
    print("같은 경기", collections.Counter((s_[0], s_[-1] == "같음") for s_ in SAMEGAME))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("vicbg", "1985-07-01"), ("fiobg", "1990-07-01"), ("juvbg", "1995-07-06"), ("milbg", "1997-07-18"),
         ("bolbg", "1998-07-01"), ("intbg", "2000-07-01"), ("brebg", None)]
TM_CLUB = {"2655": "vicbg", "430": "fiobg", "506": "juvbg", "5": "milbg", "1025": "bolbg", "46": "intbg", "19": "brebg"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
    if season_eu(ldate(g))[:4] != g["seasonId"] and not (ldate(g)[5:7] == "08" and int(ldate(g)[:4]) == int(g["seasonId"])):
        sys.exit("시즌 불일치 " + g["gameId"] + " " + ldate(g) + " " + g["seasonId"])
    if ldate(g)[5:7] == "07": sys.exit("7월 경기 " + g["gameId"])
PERIODS = [("비첸차", "1982~1985", None, "1985-07-01"), ("피오렌티나", "1985~1990", "1985-07-01", "1990-07-01"),
           ("유벤투스", "1990~1995", "1990-07-01", "1995-07-06"), ("AC 밀란", "1995~1997", "1995-07-06", "1997-07-18"),
           ("볼로냐", "1997~1998", "1997-07-18", "1998-07-01"), ("인테르", "1998~2000", "1998-07-01", "2000-07-01"),
           ("브레시아", "2000~2004", "2000-07-01", None)]
def per(lo, hi):
    inr = lambda d: (lo is None or d >= lo) and (hi is None or d < hi)
    return [sum(1 for m in M if inr(m[0])), sum(1 for r in E if r[0] == "g" and inr(r[9])),
            sum(1 for r in E if r[0] == "a" and inr(r[9])), sum(m[3] for m in M if inr(m[0]))]
ST = [(n, y, per(lo, hi)) for n, y, lo, hi in PERIODS]

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NEST = sum(1 for m in M if len(m) > 4)
NOTE_LINES = [
    f"로베르토 바조(비첸차·피오렌티나·유벤투스·AC 밀란·볼로냐·인테르·브레시아)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 피아첸차전 ~ {d_(M[-1][0])} 밀란전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·이탈리아 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n}({y}) {v[0]}·{v[1]}·{v[2]}" for n, y, v in ST)
    + f". 출전 분 합계 {MIN_TOT:,}분(90분으로 추정한 {NEST}경기 포함)",
    "출처: 경기 목록·출전 분(연장·교체 반영)은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 대회 경기 전부; 바조 골·도움 수는 선수 경기 성적과 경기마다 같음). FotMob에는 바조 기록이 없음(검색되는 같은 이름은 브라질 선수). 피오렌티나~브레시아 경기·골은 영어·이탈리아어 위키백과 시즌별 기록과 모두 같음. 비첸차 1984-85 골은 영어 위키백과 시즌 문서 경기 기록과 대조",
    "비첸차(1982~1985)는 세리에C1(3부, 프로 리그) 시절이라 셈. Transfermarkt 비첸차 39경기 14골 + 1985.3.17 세리에C1 레지아나전(비첸차 3-0) 1경기 1골: Transfermarkt는 이 경기를 '명단 외'로 적었으나 영어 위키백과 1984-85 비첸차 시즌 문서 경기 기록에 바조 81분 PK 골(파시울로 30분·론돈 41분 뒤)이 있고, 그 시즌 리그 기록(위키백과 12골, 라 레푸블리카 기사 '25경기 12골')과도 맞아 넣음(출전 분 자료가 없어 90분 추정). 위키백과 1984-85 리그 29경기와의 나머지 차이 4경기(Transfermarkt가 '명단 외'로 적은 3·7·21·22라운드; 바조는 1985.5.5 리미니전 8분에 무릎을 크게 다쳐 30~34라운드는 결장)와 1984-85 코파 이탈리아 토리노전(위키백과 5경기, Transfermarkt 4경기), 1983-84 코파 이탈리아 세리에C 2경기 1골(위키백과)은 경기별 출전 근거가 없어 넣지 않음",
    "비첸차 골 시각 차이: 1984.10.21 모데나전 골은 Transfermarkt 분 칸이 비어(121로 표시) 영어 위키백과 시즌 문서의 45분으로 적고 그 시각 순서대로 1-1에서 넣은 골로 봄(PK 여부는 Transfermarkt 기록 PK, 위키백과는 PK 표시 없음). 나머지는 Transfermarkt 분(위키백과와 1~10분 차이: 리미니 5분/4분, 레냐노 60분/70분, 카라레세 28분/30분 등)",
    "브레시아 2003-04: Transfermarkt 일정에만 있는 세리에A 1·2라운드(키에보·로마)와 인터토토컵 4경기(글로리아 비스트리차·비야레알)는 Transfermarkt 경기 리포트 출전 명단에 바조가 없고 위키백과 시즌 기록(리그 26경기, 인터토토 0경기)과도 맞아 출전하지 않은 것으로 봄",
    "골: Transfermarkt 리포트 골(자책골 없음)과 위 레지아나전 골. PK는 Transfermarkt 'Penalty' 표기만(PK 실축 뒤 리바운드 골 3개 — 1990.4.29 아탈란타전, 1993.1.31 칼리아리전, 2002.5.5 볼로냐전 — 는 일반 골). 2000.8.16 '올스타'(클럽 선발팀) 프랑스 대표팀 친선경기 1골은 뺌",
    f"도움: 모두 Transfermarkt 경기 리포트 도움(2014년 이전이라 단일 출처; FotMob·위키백과에 도움 기록 없음). 도움 {NA} = Transfermarkt 156 − PK 유도 1(1990.10.24 컵위너스컵 아우스트리아 빈전 스킬라치 PK) − 슈팅 리바운드('Shot on goal') 4(1993.5.23 삼프도리아전 플랫, 1990.10.28 인테르전 스킬라치, 1989.12.17 인테르전 델로글리오, 1993.9.15 UEFA컵 로코모티프 모스크바전 라바넬리) − 상대 자책골 유도 3(1992.11.8 우디네세전 펠레그리니, 1995.4.9 말탈리아티, 1994.4.2 페리). 본인 PK 골에 본인 도움으로 적힌 3개(1989.5.7·1990.2.4 밀란전, 1996.10.23 레지아나전)는 원래 도움 합계에 없음. 1990년대 중반 이전 Transfermarkt 리포트는 도움 칸이 빈 골이 많아(리포트 골 1,254개 중 517개) 이 시기 도움은 실제보다 적을 수 있음",
    "출전 분: Transfermarkt 그대로. 연장 경기: 1989.8.30 코파 이탈리아 코모전(120분, 승부차기), 1989.9.26 UEFA컵 아틀레티코 마드리드전(120분, 승부차기), 1992.2.26 코파 이탈리아 8강 2차전 인테르 원정(연장, 교체 50분), 1997.11.19 코파 이탈리아 아탈란타전(120분, 승부차기)",
    "날짜: Transfermarkt 경기 리포트·일정 날짜(선수 경기 성적의 22:00/23:00 UTC 자리값은 하루 앞섬)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 상대 리그 최종 순위(Transfermarkt 순위표; 소련 1989·라트비아 1998은 영어 위키백과, 키프로스 1992-93은 RSSSF) 순으로 정하고, 순위가 있는 상대는 리그·시즌 기준 평균 + 순위 곡선 값(같은 리그·시즌·순위면 모든 선수 같은 값). 기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['같은 팀·시즌 다른 선수 자료']}, 순위표 {SRC['순위표 라벨']}. 세리에C1(3부) 상대는 리그 수준 추정 값. 1980년대 세리에A는 16팀",
    "대회 비중: 세리에A 순위 플레이오프 3번(1989.6.30 UEFA컵 출전권 로마전 단판, 1999.5.27·5.30 UEFA컵 출전권 볼로냐전 두 경기, 2000.5.23 챔피언스리그 예선 출전권 파르마전 단판)은 리그 경기로 셈(다른 선수 자료와 같음; 단판은 무승부 없는 단판, 1999년 두 경기는 원정 다득점만 있는 합산). 코파 이탈리아는 조별·16강까지 국내컵 앞 단계, 8강·준결승·결승 가중(결승은 두 경기 합산), 수페르코파 이탈리아나는 국내컵 결승, 컵위너스컵 1990-91은 1라운드~8강 유로파 토너먼트·준결승 유로파 준결승, UEFA컵 1라운드는 유로파 예선, 2라운드 이후 유로파 토너먼트(결승은 두 경기 합산, 유로파 결승 비중), 인터토토컵 결승(2001)은 유로파 예선, 챔스 예선 2라운드는 챔스 예선, 챔스 조별·8강은 챔스 비중",
    f"두 경기 합산(UEFA 대회·코파 이탈리아·1999 플레이오프) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(UEFA 대회·코파 이탈리아는 원정 다득점·연장 있음). 바조가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 8월 1일 기준(7월 공식 경기 없음). 클럽 구분은 1985.7.1 전 비첸차, 1990.7.1 전 피오렌티나, 1995.7.6 전 유벤투스, 1997.7.18 전 밀란, 1998.7.1 전 볼로냐, 2000.7.1 전 인테르, 이후 브레시아(Transfermarkt 이적일)",
    "우승·수상은 Transfermarkt 업적 페이지 기준: 세리에A 1994-95(유벤투스)·1995-96(밀란), 코파 이탈리아 1994-95·UEFA컵 1992-93(유벤투스). 개인: 발롱도르 1993, FIFA 올해의 선수 1993, 컵위너스컵 득점왕 1990-91. 준우승과 대표팀 기록(월드컵)은 뺌",
    "은퇴: 2004년(마지막 경기 2004.5.16 브레시아 원정 밀란전)",
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
    gs = sorted({(r[5], r[6], sort_min(r)) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
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
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r, mm[r[9]]))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const BAG_E={J(E)};\nconst BAG_M={J(M)};\nconst BAG_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game": SAMEGAME, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for n, y, v in ST: print(" ", n, y, v)
