#!/usr/bin/env python3
"""Jadon Sancho: raw/ -> sancho.json + src/data/sch.js (판정 근거는 judgments.md)

  python3 players/sancho/build_sancho.py            # 파일 쓰기
  python3 players/sancho/build_sancho.py --debug    # Elo 출처 로그
  python3 players/sancho/build_sancho.py --cross    # 동료 자료 대조
  python3 players/sancho/build_sancho.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/{reu,haa,got,bel,aub,ron,dem}.js(같은 경기 동료 자료 대조).
빌드 스크립트는 foden(players/foden/build_foden.py)을 바탕으로 함. 판정 표(대문자 상수)는 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "sch.js")
OUT_JSON = os.path.join(HERE, "sancho.json")
ME = "제이든 산초"
GAP = "2014-08-01"   # 도움 출처 기준일(이후 Transfermarkt∩FotMob). 산초의 성인 경기는 모두 이후

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    "3058524|40": "PK 유도(로이스 PK, 'Penalty: Fouled player')",
    "3058595|43": "슈팅 리바운드(괴체 골, 'Shot on goal')",
    "3058641|62": "PK 유도(로이스 PK, 'Penalty: Fouled player')",
    "4096121|58": "PK 유도(퓔크루크 PK, 'Penalty: Fouled player')",
    "4361373|28": "PK 유도(팔머 PK, 'Penalty: Fouled player')",
    "3412981|53": "출처 충돌: TM·bundesliga.com은 산초 코너, FotMob·ESPN·Sportsmole·t-online 등은 뫼니에 도움(산초 코너가 훔멜스 몸에 맞고 들어감) -> 다른 출처 2곳 확인 실패, 굴절 성격",
}
# TM 단일 출처이지만 다른 출처 2곳(WebSearch 경기 기사)이 확인해 넣은 도움: gameId|분
ADD_CONFIRMED = {
    "3048419|120+1": "2018.8.20 퓌르트전 연장 로이스 결승골: AFP 계열 기사('low right-wing cross from Jadon Sancho')와 다른 기사('Sancho ... cutting the ball back to Reus')",
    "3058521|76": "2018.11.24 마인츠전 피슈체크 골: BVB 공식 기록('Piszczek (Sancho, 76)')·Sportsmole 라이브·경기 기사('Sancho lay the ball to Piszczek')",
    "3203460|83": "2019.9.14 레버쿠젠전 게레이루 골: BVB 공식 기록('Guerreiro (Sancho, 83)')·AFP 계열 기사·Sky Italia 기사. 반대: Sky Sports 라인업 페이지는 도움 없음",
    "3404450|58": "2020.9.14 뒤스부르크전 로이스 골: 득점 목록('Marco Reus 58. left-footed shot (Jadon Sancho)', 검색 요약, 사이트 미확인)과 독일 보도('Reus ... following a Sancho cross', 검색 요약). TM 도움 유형은 프리킥",
}
# 분 보정: TM이 정각 90으로 적었으나 FotMob이 추가시간(90+4)으로 적은 도움 -> FotMob 추가시간 표기(인시녜·팔카오 선례)
MIN_FIX = {"3203449|90": (94, "90+4")}   # 2019.8.23 쾰른전 알카세르 골(TM 90, FotMob 90+4)
# FotMob에만 있는 도움(넣지 않음): gameId -> 이유 (없음 기대)
FM_ONLY_EXCL = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "GB1"}
CUP = {"DFB", "FAC", "CGB"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"    # DFB-포칼·FA컵 8강
        return "dc"                                 # 1~3라운드·16강
    if cid in ("DFL", "GBCS"): return "df"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"      # 조별·리그 페이즈(2025-26)
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                # intermediate stage(32강 플레이오프)·16강·8강
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"      # 2024-25 리그 페이즈
        if r.startswith("semi"): return "ecsf"
        if r.startswith("final"): return "ecf"
        return "eck"                                # 16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스·유로파·컨퍼런스 조별/리그 페이즈
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local"]
    leg = 1 if "1st" in g["round"].lower() else 2
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    if cid in ("CL", "EL"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "UCOL":
        ag, et = 0, 1
    elif cid == "CGB":   # 잉글랜드 리그컵 준결승: 2018-19부터 원정 다득점·연장 없음
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
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 순위표+모형으로 채울 수 없는 상대(직접 추정, 모두 lv에 '추정')와 순위표+기존 고정값: judgments.md 7절
from sancho_elo import MAN, model   # noqa  (같은 폴더)

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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"
                        + ("" if len({(x["elo"], x["lv"]) for x in same}) == 1 else " 값 여럿:" + repr(sorted({(x["elo"], x["lv"]) for x in same})))))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL", "UCOL", "KLUB", "USC") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    for s in seasons:
        t = None
        for lg in ("ENG2", "DEN1", "POL1", "SWE1"):
            t = RANKS.get((lg, s))
            if t and k in t:
                r, n = t[k]
                res = model(lg, s, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model"))
                    return res
    return None

# ---------------------------------------------------------------- 출전
M = []
for g in GAMES:
    M.append([g["date_local"], g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["sancho_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

G_BY_DATE = {g["date_local"]: g for g in GAMES}
rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    et = int(mi > 90 and not dm and G_BY_DATE[d]["gameState"] in ("extra_time", "penalty_shootout"))   # 연장 골
    if dm and str(dm).startswith("120+"):   # 연장 후반 추가시간(퓌르트 120+1): 같은 경기 로이스 자료와 같게 et 1·dm 없음(화면은 같음)
        et, dm = 1, 0
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa = e["sancho_scorer"] == "1", e["sancho_assist_other"] == "1"
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
    if f"{gid}|{e['minute']}" in MIN_FIX: mi, dm = MIN_FIX[f"{gid}|{e['minute']}"]
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = g["date_local"]; opp = g["opponent"].strip()
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - mi) <= 2]
            if not hit:
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
            used_fm[gid] += 1
        elif tag in ADD_CONFIRMED:
            judg.append(("도움 포함(TM 단일+기사 확인)", d, opp, e["minute"], e["scorer"], ADD_CONFIRMED[tag]))
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

# FotMob에만 있는 도움(넣지 않음) 확인
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if len(ts) > used_fm.get(gid, 0):
        FM_ONLY.append((gid, G[gid]["date_local"] if gid in G else "?", ts))
if sorted(x[0] for x in FM_ONLY) != sorted(FM_ONLY_EXCL):
    sys.exit("FotMob 단독 도움 판정 누락 " + repr(FM_ONLY))
for gid in FM_ONLY_EXCL: judg.append(("FotMob 단독 도움 제외", G[gid]["date_local"], G[gid]["opponent"], FM_ONLY_EXCL[gid]))

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["sancho_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV:
        FM_CMP.append(("FotMob 없음", gid)); continue
    fg = [r for r in FM_EV[gid] if r["sancho_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Marco Reus": ("reu.js", "REU"), "Erling Haaland": ("haa.js", "HAA"), "Mario Götze": ("got.js", "GOT"),
         "Jude Bellingham": ("bel.js", "BEL"), "Pierre-Emerick Aubameyang": ("aub.js", "AUB"),
         "Cristiano Ronaldo": ("ron.js", "RON"), "Ousmane Dembélé": ("dem.js", "DEM")}
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
    if a[10] != b[10]: diffs.append(f"et {a[10]}/{b[10]}")
    if a[11] != b[11]: diffs.append(f"dm {a[11]}/{b[11]}")
    return diffs
for nm, ent in MATE_E.items():
    # 산초 도움 -> 동료 골
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("산초 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    # 동료 도움 -> 산초 골
    for x in ent:
        if x[0] == "a" and norm(x[13]) == "jadon sancho":
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→산초 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    # 같은 경기(날짜·상대 같음) 대회·Elo·lv 대조
    for x in ent:
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                d = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회"))]
                if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                break
    # TM 리포트에서 산초가 도움 준(또는 받은) 동료 골인데 동료 파일에 없는 것(참고)
    for e in EVENTS:
        if e["gameId"] not in G: continue
        d = G[e["gameId"]]["date_local"]; mi = minute(e["minute"])[0]
        if e["sancho_assist_other"] == "1" and norm(e["scorer"]) == norm(nm):
            if not any(x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("산초 도움 대상 골이 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
        if e["sancho_scorer"] == "1" and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 산초 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] for c in CROSS))
    print(collections.Counter((c[0], c[1] if c[0].endswith("산초 골") or "→" in c[0] else "") for c in CROSS if c[-1] == "같음"))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("bvbsa", "2021-08-01", "보루시아 도르트문트", "2017~2021"),
         ("munsa", "2024-01-11", "맨체스터 유나이티드", "2021~2024"),
         ("bvbsa", "2024-07-01", "보루시아 도르트문트", "2024"),
         ("munsa", "2024-09-01", "맨체스터 유나이티드", "2024"),
         ("chesa", "2025-09-01", "첼시 (임대)", "2024~2025"),
         ("avlsa", None, "애스턴 빌라 (임대)", "2025~2026")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {"bvbsa": "도르트문트", "munsa": "맨체스터 유나이티드", "chesa": "첼시", "avlsa": "애스턴 빌라"}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in ["bvbsa", "munsa", "chesa", "avlsa"])
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TM_CLUB = {"16": "bvbsa", "985": "munsa", "631": "chesa", "405": "avlsa"}
for g in GAMES:
    if club_of(g["date_local"]) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
from sancho_note import make_note   # noqa
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
NOTE = make_note(M, E, ST, ELO_SRC, NG, NGo, NA, NPK, MIN_TOT, NTIE, NTIEG)
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
    if r[12] == "?" : problems.append(("lv 없음", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const SCH_E={J(E)};\nconst SCH_M={J(M)};\nconst SCH_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
