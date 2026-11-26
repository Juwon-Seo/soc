#!/usr/bin/env python3
"""Alberto Gilardino: raw/ -> gilardino.json + src/data/gil.js (판정 근거는 judgments.md)

  python3 players/gilardino/build_gilardino.py            # 파일 쓰기
  python3 players/gilardino/build_gilardino.py --debug    # Elo 출처 목록
  python3 players/gilardino/build_gilardino.py --cross    # 같은 경기 다른 선수 자료 대조
  스크래치 복사본에서는 SOC_ROOT=<복사본>.

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/ranks.txt(순위표), <ROOT>/elo/opponent_elo_by_team_season.csv·aliases.csv,
      <ROOT>/tools/league_rank_apply.py(새 팀-시즌의 순위 → Elo), src/data/*.js(git에 있는 기존 선수 파일만: 같은 경기 대조).
루카 토니 build 스크립트(같은 수집 형식)를 바탕으로 함.
"""
import csv, json, os, re, sys, unicodedata, collections, subprocess, io, contextlib
from datetime import date as Date

HERE = os.environ.get("GIL_HERE") or os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "gil.js")
OUT_JSON = os.path.join(HERE, "gilardino.json")
ME = "알베르토 질라르디노"
MYFILE = "gil.js"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

# ---------------------------------------------------------------- 판정 표 (judgments.md)
# 골 제외: gameId|TM 분 -> 이유
EXCL_G = {
    "2255397|32": "2012.8.18 코파 이탈리아 베로나전 32분 1-0 골: Transfermarkt만 질라르디노 골(얀코비치 프리킥 도움), ESPN·유로스포츠는 메스토 골(34·33분), FotMob은 얀코비치 골 → 질라르디노 골 아님",
}
# 도움 제외: gameId|분 -> 이유
EXCL_A = {
    "40940|43": "PK 유도(셰우첸코 PK)",
    "66378|7": "PK 유도(카카 PK)",
    "929785|52": "PK 유도(무투 PK)",
    "932427|60": "PK 유도(무투 PK)",
    "932221|59": "PK 유도(요베티치 PK)",
    "964328|76": "PK 유도(요베티치 PK)",
    "1047370|61": "PK 유도(랴이치 PK)",
    "1047563|47": "PK 유도(다고스티노 PK)",
    "2251383|48": "PK 유도(디아만티 PK)",
    "2359219|61": "PK 유도(로디 PK)",
    "84207|66": "슈팅 리바운드(Shot on goal, 파투 탭인)",
    "1137407|80": "슈팅 리바운드(Shot on goal)이자 상대 자책골(델 그로소 자책골)",
    "2489979|7": "2014년 8월 뒤 Transfermarkt 단일 출처(FotMob 경기 기록에 도움자 없음, 다른 출처 확인 못 함: 가오린 골)",
    "2489979|69": "2014년 8월 뒤 Transfermarkt 단일 출처(FotMob 경기 기록에 도움자 없음, 다른 출처 확인 못 함: 엘케손 골)",
    "2497951|35": "2014년 8월 뒤 Transfermarkt 단일 출처(FotMob 경기 기록에 도움자 없음, 다른 출처 확인 못 함: 엘케손 골)",
}
# 2014년 8월 뒤 단일 출처지만 다른 출처 2곳으로 확인해 넣은 도움
SINGLE_KEEP = {
    "2458227|61": "AFC 챔스 8강 2차전 웨스턴 시드니전 디아만티 골: Transfermarkt 도움, FotMob 경기 기록은 도움자 없음; "
                  "야후 뉴스(AAP) '질라르디노의 떨궈 준 공을 디아만티가 차 넣음', FourFourTwo '질라르디노가 머리로 떨궈 준 공을 디아만티가 슈팅'",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "CSL", "ITPO"}   # ITPO = 세리에A 잔류 결정전(스파레조, 리그 비중: 카모라네시 2001 선례)
CUPS = {"CIT", "CHFA"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "USC": return "df"   # UEFA 슈퍼컵(인자기·카카 선례)
    if cid == "KLUB": return "cwc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":   # UEFA컵 1라운드 = 유로파 예선, 조별 = 유로파 조별, 2라운드·3라운드(32강)·중간 라운드(32강)·16강·8강 = 유로파 토너먼트
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        if r.startswith(("second round", "3rd round", "intermediate", "last 16", "quarter")): return "elk"
    if cid == "AFCL":
        if r.startswith("group"): return "acl"
        if r.startswith("quarter"): return "aclk"
        if r.startswith("semi"): return "aclsf"
        if r.startswith("final"): return "aclf"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        t = TIES_RAW[gid]
        o = INFO.get(t["other_leg_id"])
        if o:
            oh, oa = map(int, o["final"].split(":"))   # 다른 차전 리포트의 홈:원정 스코어(타이 표의 other_leg_final은 이 경기 홈팀 기준)
            if o["home_id"] == g["club_id"]: fu, ft = oh, oa
            elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
            else: sys.exit("다른 차전 팀 불일치 " + gid)
            if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
        else:
            sys.exit("다른 차전 리포트 없음 " + gid)
    if g["competitionId"] == "ITPO":
        return [leg, home, fu, ft, 1, 0]   # 세리에A 잔류 결정전: 원정 다득점, 연장 없음(카모라네시 2001 선례)
    return [leg, home, fu, ft, 1, 1]       # UEFA 대회·코파 이탈리아·AFC 챔스: 원정 다득점·연장

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

TABLE = {}
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE.setdefault((key(nm), r["시즌"]), (int(r["Elo"]), r["수준 라벨(lv)"]))

# 같은 경기 다른 선수 자료: git에 있는 파일만(병행 판정자의 새 파일은 읽지 않음)
try:
    TRACKED = set(os.path.basename(x) for x in subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
except Exception:
    TRACKED = set()
if not TRACKED:   # 스크래치 복사본에 .git이 없을 때: 원본 저장소 기준
    TRACKED = set(os.path.basename(x) for x in subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(os.listdir(os.path.join(ROOT, "src", "data"))):
    if not fn.endswith(".js") or fn in ("hon.js", "clubcolors.js", MYFILE) or fn not in TRACKED: continue
    try: OTHERS[fn] = load_js(fn)
    except Exception: continue
SAME = collections.defaultdict(collections.Counter)
for fn, (P, oe, om) in OTHERS.items():
    for x in oe: SAME[x[9]][(key(x[1]), x[2], x[12])] += 1
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

# 순위 → Elo: tools/league_rank_apply.py 와 같은 식(라벨에서 바로 계산하므로 도구를 다시 돌려도 이동량 0)
def _load_rank_tool():
    p = os.path.join(ROOT, "tools", "league_rank_apply.py")
    Gx = {"__file__": p, "__name__": "rank_tool"}
    argv = sys.argv; sys.argv = ["x"]
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(open(p, encoding="utf-8").read(), p, "exec"), Gx)
    sys.argv = argv
    return Gx
RT = _load_rank_tool()
def rank_value(lv, d):
    p = RT["parse"](lv, d)
    if not p: sys.exit("순위 라벨을 도구가 못 읽음: " + lv)
    v = RT["value"](*p)
    if v is None: sys.exit("기준 없음: " + lv)
    return v

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league" or len(p) < 5: continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 새 팀-시즌(통합표에 없음) 라벨: 리그 코드 -> (라벨 함수)
NEWLAB = {
    "IT3B": lambda s, r, n: f"이탈리아 3부 {s} {r}위/{n}팀 (Serie C1 Girone B, 리그 수준 추정)",
    "A1": lambda s, r, n: f"오스트리아 1부 {s} {r}위/{n}팀 (Bundesliga)",
    "TR1": lambda s, r, n: f"튀르키예 1부 {s} {r}위/{n}팀 (Süper Lig)",
    "CSL": lambda s, r, n: f"중국 1부 {s} {r}위/{n}팀 (Chinese Super League)",
    "AUS1": lambda s, r, n: f"호주 1부 {s} {r}위/{n}팀 (A-League, 경기 때 직전 완료 시즌 정규리그 순위)",
    "IT2": lambda s, r, n: f"세리에B {s} {r}위/{n}팀",
    "IT1": lambda s, r, n: f"세리에A {s} {r}위/{n}팀",
}
# 경기 -> (순위표 리그, 순위표 시즌, 통합표 시즌)
def where(g, d):
    cid = g["competitionId"]; opp = oname(g)
    if cid in ("CSL", "CHFA"): return [("CSL", "2014", "2014")]
    if cid == "AFCL": return [("AUS1", "2013-14", "2013-14")]   # 2014.8 AFC 챔스 8강: 호주 2014-15 시즌은 10월 시작 → 직전 완료 시즌
    s = season_eu(d)
    return [(lg, s, s) for lg in ("IT1", "IT2", "IT3B", "A1", "TR1")]

ELO_SRC = collections.Counter()
ELO_LOG = []
NEW_TS = {}
def opp_elo(g, d):
    opp = oname(g); k = key(opp)
    same = [(kk, e, lv) for (kk, e, lv), c in SAME.get(d, {}).items() for _ in range(c) if kk == k or _sub(kk, k)]
    if same:
        (_, e, lv), _ = collections.Counter(same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG.append((d, opp, e, lv, "same")); return e, lv
    W = where(g, d)
    for lg, rs, ts in W:
        if (k, ts) in TABLE:
            e, lv = TABLE[(k, ts)]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + ts)); return e, lv
    for lg, rs, ts in W:
        t = RANKS.get((lg, rs))
        if t and k in t:
            r, n = t[k]
            lv = NEWLAB[lg](rs, r, n)
            e = rank_value(lv, d)
            NEW_TS[(opp, ts)] = (e, lv)
            ELO_SRC["순위표+리그 수준(새 팀-시즌)"] += 1; ELO_LOG.append((d, opp, e, lv, "new " + lg)); return e, lv
    return None

# ---------------------------------------------------------------- 출전
def ldate(g): return g["date_local_tm_report"]
def oname(g): return re.sub(r"\s*\(- ?\d{4}\)|\s*\(\d{4} - \d{4}\)", "", g["opponent"]).strip()

M = []
for g in GAMES:
    if not ldate(g): sys.exit("날짜 없음 " + g["gameId"])
    M.append([ldate(g), oname(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

_cache = {}
def rd_cache(n):
    if n not in _cache: _cache[n] = rd(n)
    return _cache[n]

rows, judg = [], []
missing_elo = set()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["ac_scorer"] == "1", e["ac_assist_other"] == "1", e["ac_self_assist"] == "1"
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
    tag = f"{gid}|{e['minute']}"
    mi, dm = minute(e["minute"])
    et = int(mi > 90 and (not dm or int(str(dm).split("+")[0]) >= 105))
    if et and g["gameState"] == "regularly_terminated": sys.exit("연장 판정 이상 " + gid)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = oname(g)
    def add(typ, pk, note):
        res = opp_elo(g, d)
        if res is None:
            missing_elo.add((opp, d, cid)); res = (0, "?")
        row = [typ, opp, res[0], comp, mi, gf, ga, ko, pk, d, et, dm, res[1], note]
        if tie: row.append(tie)
        rows.append(row)
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag]))
        else:
            add("g", int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"), 0)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal", "Deflected") or e["assist_type"].startswith("Handball"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= "2014-08-01":
            fm = [r for r in rd_cache("ac_assists.csv") if r["gameId"] == gid and r["minute"] == e["minute"]]
            src = fm[0]["sources_with_assist"] if fm else "?"
            if src != "TM + FotMob" and tag not in SINGLE_KEEP:
                sys.exit("2014.8 뒤 단일 출처 도움 판정 누락 " + tag)
            if tag in SINGLE_KEEP: judg.append(("단일 출처 도움 넣음(다른 출처 2곳)", d, opp, e["minute"], e["scorer"], SINGLE_KEEP[tag]))
        add("a", 0, e["scorer"])


if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

def sort_min(r):
    return r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5
rows.sort(key=lambda r: (r[9], sort_min(r), 0 if r[0] == "g" else 1))
E = rows

# 한 팀·한 시즌 한 값(내 자료 안)
_chk = collections.defaultdict(set)
for r in E:
    _chk[(key(r[1]), season_eu(r[9]) if r[3] not in ("lg",) or "중국" not in r[12] else "2014")].add((r[2], r[12]))
for k_, v in _chk.items():
    if len(v) > 1: print("같은 팀-시즌 값 여럿(내 자료):", k_, v)

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k)
        if not x[4].startswith("same"): print(x)
    print("새 팀-시즌:", NEW_TS)

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
CROSS, SAMEGAME, MATEMISS = [], [], []
for fn, (P, ent, om) in OTHERS.items():
    for r in E:
        if r[0] != "a": continue
        hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1])]
        if hit: CROSS.append(("질라르디노 도움→" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        elif any(m[0] == r[9] for m in om):
            # 같은 팀 동료가 같은 경기에 뛰었는데 그 골이 동료 파일에 없음(득점자가 그 선수일 때만 의미)
            pass
    for x in ent:
        if x[0] == "a" and "gilardino" in norm(str(x[13])):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn + " 도움→질라르디노 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                SAMEGAME.append((fn, r[9], r[1], tuple(d) or "같음"))
                break
SAMEGAME = sorted(set(SAMEGAME))
# TM 리포트의 동료 도움(질라르디노 골)·질라르디노 도움(동료 골) 중 동료 파일에 대응 행이 없는 것
MATE = {"see.js": "Clarence Seedorf", "kak.js": "Kaka", "inz.js": "Filippo Inzaghi", "gou.js": "Yoann Gourcuff", "she.js": "Andriy Shevchenko",
        "adr.js": "Adriano", "cam.js": "Mauro Camoranesi", "rui.js": "Rui Costa", "rno.js": "Ronaldo", "ili.js": "Josip Ilicic",
        "sal.js": "Mohamed Salah", "joa.js": "Joaquin", "gom.js": "Mario Gomez", "brd.js": "Federico Bernardeschi", "imm.js": "Ciro Immobile"}
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    d = ldate(g); mi = minute(e["minute"])[0]; tag = f"{gid}|{e['minute']}"
    for fn, nm in MATE.items():
        if fn not in OTHERS: continue
        P, ent, om = OTHERS[fn]
        if e["ac_scorer"] == "1" and norm(e["assist_player"]) == norm(nm) and tag not in EXCL_G:
            ok = any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 3 for x in ent)
            MATEMISS.append(("동료 도움→질라르디노 골", fn, d, e["minute"], e["assist_type"], "동료 파일에 있음" if ok else "동료 파일에 없음"))
        if e["ac_assist_other"] == "1" and norm(e["scorer"]) == norm(nm):
            ok = any(x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 3 for x in ent)
            MATEMISS.append(("질라르디노 도움→동료 골", fn, d, e["minute"], "제외" if tag in EXCL_A else "넣음", "동료 골 행 있음" if ok else "동료 골 행 없음"))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s_ in SAMEGAME:
        if s_[-1] != "같음": print("같은 경기 차이", s_)
    print("같은 경기", collections.Counter((s_[0], s_[-1] == "같음") for s_ in SAMEGAME))
    for m_ in MATEMISS: print(m_)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("pcagi", "2000-09-18", "피아첸차", "피아첸차", "1999~2000"), ("vergi", "2002-07-01", "헬라스 베로나", "베로나", "2000~2002"),
         ("pargi", "2005-07-17", "파르마", "파르마", "2002~2005"), ("milgi", "2008-07-01", "AC 밀란", "밀란", "2005~2008"),
         ("fiogi", "2012-01-03", "피오렌티나", "피오렌티나", "2008~2012"), ("gengi", "2012-08-31", "제노아", "제노아", "2012"),
         ("bolgi", "2013-06-30", "볼로냐", "볼로냐", "2012~2013"), ("gengi", "2014-07-12", "제노아", "제노아", "2013~2014"),
         ("gzegi", "2015-01-26", "광저우 헝다", "광저우", "2014"), ("fiogi", "2015-08-27", "피오렌티나", "피오렌티나", "2015"),
         ("palgi", "2016-07-07", "팔레르모", "팔레르모", "2015~2016"), ("empgi", "2017-01-09", "엠폴리", "엠폴리", "2016"),
         ("pesgi", "2017-10-03", "페스카라", "페스카라", "2017"), ("spegi", None, "스페치아", "스페치아", "2017~2018")]
TM_CLUB = {"1408": "pcagi", "276": "vergi", "130": "pargi", "5": "milgi", "430": "fiogi", "252": "gengi", "1025": "bolgi",
           "10948": "gzegi", "458": "palgi", "749": "empgi", "2921": "pesgi", "3522": "spegi"}
def club_of(d):
    for k, u, *_ in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
    s_tm = g["seasonId"]
    if g["club_id"] == "10948":
        if ldate(g)[:4] != "2014": sys.exit("광저우 시즌 이상 " + g["gameId"])
    elif season_eu(ldate(g))[:4] != s_tm: sys.exit("시즌 불일치 " + g["gameId"] + " " + ldate(g))
lo = None
PERIODS = []
for k, u, n, sh, y in CLUBS:
    PERIODS.append((n, y, lo, u)); lo = u
def per(lo, hi):
    inr = lambda d: (lo is None or d >= lo) and (hi is None or d < hi)
    return [sum(1 for m in M if inr(m[0])), sum(1 for r in E if r[0] == "g" and inr(r[9])),
            sum(1 for r in E if r[0] == "a" and inr(r[9])), sum(m[3] for m in M if inr(m[0]))]
ST = [(n, y, per(lo, hi)) for n, y, lo, hi in PERIODS]
if __name__ == "__main__" and "--debug" in sys.argv:
    for x in ST: print(x)

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NOTE_LINES = [
    f"알베르토 질라르디노(피아첸차·헬라스 베로나·파르마·AC 밀란·피오렌티나·제노아·볼로냐·광저우 헝다·팔레르모·엠폴리·페스카라·스페치아)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} AC 밀란전 ~ {d_(M[-1][0])} 파르마전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·이탈리아 대표팀(U-21·올림픽 포함) 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n}({y}) {v[0]}·{v[1]}·{v[2]}" for n, y, v in ST)
    + f". 출전 분 합계 {MIN_TOT:,}분(90분 추정 없음). 피오렌티나 두 시기(2008~2012, 2015 임대)와 제노아 두 시기(2012, 2013~2014)는 클럽 탭에서 각각 한 클럽으로 묶임",
    "프로 리그: 모든 시즌 팀이 세리에A·세리에B·중국 슈퍼리그(모두 프로 리그)라 전부 셈. 피아첸차 2000-01(세리에B)은 시즌 전 코파 이탈리아 3경기만 뛰고 베로나로 옮김. 유소년·2군 경기 없음",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(뛴 클럽 경기 643개 전부). 클럽·시즌·대회별 경기·골은 영어·이탈리아어 위키백과와 모두 같음(이탈리아어 위키백과 통산 줄 646경기는 시즌 줄 합계 643경기와 다른 표기 오류). 2010-11 이후 골은 FotMob 경기 기록과 대조함(골 순서·스코어 같음, 시각은 1분 안). 그 전은 경기별 두 번째 출처가 없음. 2014.7.24 중국 FA컵 16강 허난 젠예전(1골)은 FotMob에 경기가 없어 Transfermarkt만 근거(위키백과 컵 1경기 1골과 같음)",
    "골: Transfermarkt 리포트 골 232개 − 1 = {}. 뺀 골: 2012.8.18 코파 이탈리아 3라운드 제노아-베로나(1-1, 승부차기 패) 전반 1-0 골 — Transfermarkt(와 이를 따른 위키백과)만 질라르디노 골이고 ESPN·유로스포츠는 메스토 골, FotMob은 얀코비치 골이라 질라르디노 골로 보지 않음(출전 120분은 셈). PK 골 {}개는 Transfermarkt 리포트 기준(2010-11 이후 8개는 FotMob과 같음). 자책골·본인 PK 골의 본인 도움 없음".format(NGo, NPK),
    f"도움: Transfermarkt 경기 리포트 도움 65개 − PK 유도 10(2005.9.25 트레비소전 셰우첸코, 2006.11.1 안데를레흐트전 7분 카카, 2008.11.22 우디네세전·2009.2.15 제노아전 무투, 2009.4.5 아탈란타전·2009.9.26 리보르노전 요베티치, 2010.9.26 파르마전 랴이치, 2011.2.6 파르마전 다고스티노, 2012.11.18 팔레르모전 디아만티, 2013.9.1 피오렌티나전 로디) − 슈팅 리바운드 2(2008.3.22 토리노전 파투 탭인, 2012.4.22 시에나전 델 그로소 자책골) − 2014년 8월 뒤 Transfermarkt 단일 출처라 확인 못 한 3 = {NA}",
    "2014년 8월 전 도움은 Transfermarkt 단일 출처도 셈(다른 선수 자료 선례; 1999~2010 도움은 경기별 두 번째 출처가 없음). 그중 FotMob 경기 기록(2010-11 이후)에 질라르디노 도움이 없는 것: 2011.1.9 브레시아전 랴이치, 2011.3.6 카타니아전 무투, 2012.1.15 우디네세전·1.22 팔레르모전·3.25 피오렌티나전 팔라시오, 2012.5.13 팔레르모전 스쿨리, 2012.9.16 로마전 디아만티. 2014년 8월 뒤 Transfermarkt 도움 8개 중 4개(2015.2.22 토리노전 살라, 2015.5.24 팔레르모전 마르코스 알론소, 2015.9.19 밀란전 힐램마르크, 2016.5.1 삼프도리아전 바스케스)는 Transfermarkt·FotMob이 같고, 2014.8.27 AFC 챔스 8강 웨스턴 시드니전 디아만티 골은 FotMob 경기 기록에 도움자가 없으나 야후 뉴스(AAP)·FourFourTwo 경기 기사가 질라르디노가 떨궈 준 공이라 적어 넣음(나머지 3개는 아래)",
    "확인 못 해 뺀 도움(2014년 8월 뒤 Transfermarkt만 도움으로 적고 FotMob 중국 슈퍼리그 경기 기록에는 도움자가 없으며 다른 경기 기사도 찾지 못함): 2014.9.13 상하이 둥야전 7분 가오린 골·69분 엘케손 골, 2014.9.28 광저우 R&F전 35분 엘케손 골. FotMob 시즌 합계(중국 슈퍼리그 2도움)도 경기별로는 확인되지 않음",
    "출전 분: Transfermarkt 그대로(FotMob 선발·교체·출전 분과 3분 안에서 같음). FotMob 명단에 없거나 명단 자료가 없는 코파 이탈리아 6경기·중국 슈퍼리그 12경기, FotMob에 벤치로만 적힌 2015.4.29 유벤투스전(교체 18분)도 Transfermarkt대로 셈. 2009.9.16 리옹 원정은 전반 추가시간 퇴장(45분)",
    "날짜: Transfermarkt 경기 리포트 날짜(모두 유럽·동아시아 경기라 현지 날짜와 같음). 2007 클럽 월드컵은 준결승 우라와전(2007.12.13, 63분)만 뛰고 결승은 벤치",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 리그 수준 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위+리그 수준 {SRC['순위표+리그 수준(새 팀-시즌)']})",
    "새로 정한 팀·시즌(최종 순위 → 리그 수준 모형): 비테르베세 2000-01(세리에C1 B조 16위/18팀, 플레이아웃으로 잔류; 3부 리그 수준 추정), 오스트리아 잘츠부르크 2003-04(오스트리아 1부 7위/10팀), 베식타시 2004-05(튀르키예 1부 4위/18팀), 중국 슈퍼리그 2014 허난 젠예 14위·창춘 야타이 13위·다롄 아얼빈 15위·랴오닝 10위·광저우 R&F 3위(16팀), 웨스턴 시드니 원더러스(2014.8 경기 — 호주 2014-15 시즌은 10월 시작이라 직전 완료 시즌 2013-14 정규리그 2위/10팀), 세리에B 2017-18 프로시노네 3위·포자 9위·프로 베르첼리 20위(22팀, 체세나 승점 삭감 뒤 공식 최종 순위)",
    "대회 비중: 세리에A 잔류 결정전(2001.6 베로나-레지나, 2005.6 파르마-볼로냐 2차전 원정 골)은 리그 비중 + 두 경기 합산(원정 다득점, 연장 없음; 다른 선수 자료의 2001 베로나-레지나 선례). UEFA컵 1라운드는 유로파 예선, 2004-05 조별은 유로파 조별, 2라운드·3라운드·중간 라운드(32강)·16강·8강은 유로파 토너먼트, 챔스 3·4차 예선은 챔스 예선, UEFA 슈퍼컵 2007은 국내컵 결승 비중(다른 선수 자료 선례), 클럽 월드컵 2007 준결승은 클럽 월드컵(단판), 코파 이탈리아 2000-01 조별(비테르베세전)은 국내컵(조별이라 단판 아님), 중국 FA컵 16강은 국내컵, AFC 챔스 8강은 AFC 챔스 토너먼트",
    f"두 경기 합산(UEFA 대회·챔스·코파 이탈리아·AFC 챔스·잔류 결정전) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·코파 이탈리아·AFC 챔스는 원정 다득점·연장 있음. 질라르디노가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움. 코파 이탈리아 2001-02 베로나-시에나는 Transfermarkt 라운드 이름이 '1라운드 1차전'·'2라운드 2차전'으로 다르지만 한 대진의 두 경기",
    "시즌 구분: 유럽 클럽은 8월 1일 기준, 광저우 헝다(2014)는 달력 연도. 클럽 구분은 2000.9.18 전 피아첸차(Transfermarkt 이적일 2000.9.1이지만 9.6 베로나전·9.17 우디네세전 코파 이탈리아를 피아첸차 소속으로 뛰어 경기 기준), 2002.7.1 전 헬라스 베로나, 2005.7.17 전 파르마, 2008.7.1 전 AC 밀란, 2012.1.3 전 피오렌티나, 2012.8.31 전 제노아, 2013.6.30 전 볼로냐(임대), 2014.7.12 전 제노아, 2015.1.26 전 광저우 헝다, 2015.8.27 전 피오렌티나(임대; 2015.6.30~8.27 광저우 복귀 기간 경기 없음), 2016.7.7 전 팔레르모, 2017.1.9 전 엠폴리, 2017.10.3 전 페스카라, 이후 스페치아",
    "우승·수상은 Transfermarkt 업적 페이지와 영어 위키백과 기준: UEFA 챔피언스리그 2006-07, UEFA 슈퍼컵 2007, 클럽 월드컵 2007(Transfermarkt는 2008로 적음), 중국 슈퍼리그 2014(Transfermarkt는 13/14로 적음). 개인: 세리에A 올해의 선수 2004-05(이탈리아 선수협회 오스카 델 칼초 2005 최우수 선수; Transfermarkt 'Footballer of the Year 2005'와 같은 해라 소속별 올해의 선수로 따로 넣지 않음 — 같은 해 이탈리아 선수상도 받음). 오스카 델 칼초 최우수 신인 2004는 이 계산기 수상 항목에 없어 뺌. 월드컵 2006 우승·U-21 유럽선수권 2004 우승 등 대표팀 기록은 뺌",
    "은퇴: 2018년(마지막 클럽 경기 2018.5.18 스페치아-파르마, 세리에B)",
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const GIL_E={J(E)};\nconst GIL_M={J(M)};\nconst GIL_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game": SAMEGAME, "mate_check": MATEMISS, "elo_sources": ELO_SRC, "new_team_seasons": {f"{a}|{b}": v for (a, b), v in NEW_TS.items()},
               "elo_log": ELO_LOG}, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for n, y, v in ST: print(" ", n, y, v)
