#!/usr/bin/env python3
"""Victor Osimhen: raw/ -> osimhen.json + src/data/osi.js (판정 근거는 judgments.md)

  python3 players/osimhen/build_osimhen.py [출력 data 폴더]

입력: raw/tm_games.csv(출전·분), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(도움 대조), raw/ranks.txt(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값), src/data/*.js(같은 경기 동료 자료 대조).
새 팀×시즌 값(벨기에 1부 2018-19, 쉬페르리그 2024-25~2026-27)은 tools/league_era_normalize.py의
시즌 목표 평균 + 흩어짐 × 순위 곡선(v1.216 규칙). 하부 리그(벨기에 2·3부, 프랑스 5부)는 추정.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, io, contextlib, runpy, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "src", "data")
OUT_JS = os.path.join(DATA_DIR, "osi.js")
OUT_JSON = os.path.join(HERE, "osimhen.json")
PID = "401923"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 도움 판정
# Transfermarkt 도움 중 FotMob 경기 이벤트에 없는 것(PK 유도·자책골 제외 뒤): gameId|분 -> (넣음 여부, 근거)
SINGLE = {
    "4573310|47": (1, "2025.4.22 튀르키예컵 준결승 코냐스포르전 47분 살라이 골: FotMob 경기 이벤트엔 도움자가 없지만 FotMob 선수 경기 목록에 오시멘 도움 1(Transfermarkt 'Pass'와 일치)"),
}
# 'Shot on goal'·굴절: 도움에서 뺌(엄격 규칙: Opta·FotMob이 세어도 슈팅이 굴절·리바운드된 공은 도움 아님)
SHOT_DROP = {"4647978|58": "2026.2.28 알라니아스포르전 58분 토레이라 골: 오시멘의 오버헤드킥이 수비에 맞고 튄 공을 토레이라가 넣음(beIN Sports·하베르튀르크 경기 기사). Transfermarkt 'Shot on goal', FotMob은 도움으로 셈"}
# FotMob 선수 경기 목록에만 있는 도움(Transfermarkt·FotMob 경기 이벤트 없음) — 뺌
PM_ONLY = [("2021-05-23", "Hellas Verona", "2021.5.23 엘라스 베로나전 60분 라흐마니 골: 코너킥 뒤 라흐마니 헤더가 오시멘에 맞고 굴절된 공을 라흐마니가 다시 넣음(Sky Sport·Mediotiempo는 오시멘 도움으로 적었으나 경기 서술은 의도하지 않은 굴절). FotMob 선수 경기 목록에만 도움 1, Transfermarkt·FotMob 경기 이벤트는 도움 없음")]

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"L1", "L1PO", "BE1", "POBE", "ESJP", "FR1", "IT1", "TR1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 조별, 2024-25부터 리그 페이즈('Group Stage')
        if r.startswith("intermediate") or r.startswith("last 16"): return "cl16"   # 녹아웃 플레이오프 = 16강
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                       # 32강(intermediate)·녹아웃 플레이오프
    if cid in ("DFB", "CCB", "FRC", "FRL", "CIT", "TRP"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                                        # 16강까지·조별
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE_IDS: return 0                         # 벨기에 유로파 플레이오프 결정전도 리그(선례)
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 입력
games = [g for g in rd("tm_games.csv") if g["level"] == "senior"]   # Wolfsburg II(U23 PLIC) 1경기 제외
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FMAP = {g["gameId"]: g["fotmobMatchId"] for g in games}
PM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

def ldate(g): return g["date_local"]
for g in games: g["opponent"] = g["opponent"].strip()

M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), g["opponent"], comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    if cid in ("CL", "EL"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid == "CIT": return (1, 1)
    if cid == "L1PO": return (1, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    m = MI[gid]; s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    oh, oa = map(int, m["other_leg_score"].split(":"))   # 이 리포트의 홈:원정 순서
    ours, theirs = (oh, oa) if s == "h" else (oa, oh)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def assist_reason(e, side):
    t = e["assist_type"]
    if e["scorer_id"] == PID: return "본인 PK 골의 본인 도움"
    if e["side"] != side: return "상대 골(오시멘이 내준 PK)"
    if e["own_goal"] == "1": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    return None

def fm_has_assist(gid, mi, score_after):
    # 골 뒤 스코어(홈-원정)가 같고 시각이 가까운 FotMob 이벤트(FotMob은 추가시간을 90·45분으로만 적기도 함)
    for f in FME[gid]:
        if f["osimhen_assist"] == "1":
            t = int(f["time"]) + int(f["overloadTime"] or 0)
            if f["newScore_home_away"] == score_after and (abs(t - mi) <= 2 or (t in (45, 90) and mi > t)): return True
    return False

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); sname = "home" if side == "h" else "away"; prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == PID and e["own_goal"] != "1"
        is_a = e["assist_id"] == PID
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        tag = f"{gid}|{e['minute']}"
        mi, dm = mins(e["minute"])
        d = ldate(g)
        if is_a:
            why = assist_reason(e, sname)
            if not why and tag in SHOT_DROP: why = "슈팅 굴절('Shot on goal')"
            if why:
                judg.append(("도움 제외", d, g["opponent"], e["minute"], e["scorer"], why))
            elif fm_has_assist(gid, mi, e["score_home_away_after"]):
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
            elif tag in SINGLE:
                ok, src = SINGLE[tag]
                judg.append(("단일 출처 도움 " + ("넣음" if ok else "뺌"), d, g["opponent"], e["minute"], e["scorer"], src))
                if ok: raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
            else:
                sys.exit("FotMob에 없는 도움 판정 누락: " + tag + " " + d + " " + g["opponent"])
        if is_g:
            if e["side"] != sname: sys.exit("득점 편 이상 " + tag)
            pk = 1 if e["penalty"] == "1" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))
for d, o, why in PM_ONLY: judg.append(("FotMob 목록 단독 도움 뺌", d, o, "60", "Amir Rrahmani", why))

# FotMob 경기 이벤트에만 있는 오시멘 골·도움이 없는지 확인
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["osimhen_assist"] == "1":
            t = int(f["time"]) + int(f["overloadTime"] or 0)
            if not any(e["assist_id"] == PID and e["score_home_away_after"] == f["newScore_home_away"] for e in EVS[gid]):
                sys.exit("FotMob 단독 도움 " + gid)

# ---------------------------------------------------------------- 상대 Elo
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
    k = norm(n); return ALIAS.get(k, k)

TABLE = {}
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

# v1.216 리그 시즌 수준: 목표 평균·흩어짐·순위 곡선을 tools/league_era_normalize.py에서 그대로 읽음
with contextlib.redirect_stdout(io.StringIO()):
    _sa = sys.argv; sys.argv = ["x"]
    ERA = runpy.run_path(os.path.join(ROOT, "tools", "league_era_normalize.py"))
    sys.argv = _sa
# 기존 자료가 이미 있는 리그-시즌이라 내 행이 들어가도 목표는 그대로. 값은 수집 시점 목표로 고정(다시 돌려도 같은 값)
TGT = {("Belgium", 2019): 1509.6, ("Turkey", 2025): 1559.4, ("Turkey", 2026): 1548.1, ("Turkey", 2027): 1523.6}
OSD = {"Belgium": 117.7, "Turkey": 117.3}
for (cn, y), v in TGT.items():
    if abs(ERA["otarget"](cn, y) - v) > 0.06: sys.exit(f"목표 평균 바뀜 {cn} {y} {ERA['otarget'](cn, y):.1f}")
cv = ERA["cv"]
SD2 = 51.24
# 벨기에 2부(1B 프로리그, 8팀): 2부 규칙(v1.218)과 같은 꼴 = 1부 2025-26 목표 − Opta 1·2부 간격 + 1부 시즌 차의 절반 (추정)
BE2_MEAN = round(1608.0 - 27.01 * (83.56 - 70.94) + 0.5 * (1509.6 - 1608.0), 1)   # 약 1218

# 순위(최종 순위 확인: judgments.md)
FINAL_RANK = {   # (팀, 시즌) -> (리그, 순위, 팀 수, 현재 순위 표기)
    ("KRC Genk", "2018-19"): ("BE", 1, 16, ""),
    ("KAA Gent", "2018-19"): ("BE", 5, 16, ""),
    ("Sint-Truidense VV", "2018-19"): ("BE", 7, 16, ""),
    ("KAS Eupen", "2018-19"): ("BE", 12, 16, ""),
    ("KV Oostende (-2024)", "2018-19"): ("BE", 14, 16, ""),
    ("Samsunspor", "2024-25"): ("TR", 3, 19, ""),
    ("Beşiktaş JK", "2024-25"): ("TR", 4, 19, ""),
    ("Caykur Rizespor", "2025-26"): ("TR", 8, 18, ""),
    ("Alanyaspor", "2025-26"): ("TR", 11, 18, ""),
    ("Genclerbirligi Ankara", "2025-26"): ("TR", 14, 18, ""),
    ("Eyüpspor", "2025-26"): ("TR", 15, 18, ""),
    ("Fatih Karagümrük", "2025-26"): ("TR", 18, 18, ""),
    ("Kasimpasa", "2026-27"): ("TR", 5, 18, "11월 18일 현재"),
    ("Fenerbahce", "2026-27"): ("TR", 6, 18, "11월 18일 현재"),
    ("Erzurumspor FK", "2026-27"): ("TR", 12, 18, "11월 18일 현재"),
}
BE2_RANK = {("KFCO Beerschot Wilrijk", "2018-19"): 2, ("KVC Westerlo", "2018-19"): 4}
MAN = {
    ("SC Eendracht Aalst (-2024)", "2018-19"): (1150, "벨기에 3부(1부 아마추어) 2018-19 14위/16팀 (추정, 다른 선수 자료 프랑스 5부 1150과 같은 수준)"),
    ("ESM Gonfreville", "2019-20"): (1150, "프랑스 5부(나시오날 3) 2019-20 노르망디조 14위/14팀 (추정, 다른 선수 자료 프랑스 5부 1150과 같음)"),
}

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(opp, d, cid):
    k = key(opp); s = eu(d)
    if (k, s) in TABLE:
        e, lv = TABLE[(k, s)]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(opp, s)] = ("table", e, lv); return e, lv
    if (k, d[:4]) in TABLE:   # 달력 연도 리그(노르웨이 등) 팀은 경기 연도
        e, lv = TABLE[(k, d[:4])]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(opp, d[:4])] = ("table", e, lv); return e, lv
    if (opp, s) in FINAL_RANK:
        lg, r, n, cur = FINAL_RANK[(opp, s)]
        y = int(s[:4]) + 1
        cn = "Belgium" if lg == "BE" else "Turkey"
        e = round(TGT[(cn, y)] + OSD[cn] * cv(r, n))
        lv = (f"벨기에 1부 {s} {r}위/{n}팀" if lg == "BE" else
              (f"쉬페르리그 {s} ({cur}) {r}위" if cur else f"쉬페르리그 {s} {r}위/{n}팀"))
        ELO_SRC["순위표+리그 시즌 수준"] += 1; ELO_LOG[(opp, s)] = ("model", e, lv); return e, lv
    if (opp, s) in BE2_RANK:
        r = BE2_RANK[(opp, s)]
        e = round(BE2_MEAN + SD2 * cv(r, 8))
        lv = f"벨기에 2부 {s} {r}위/8팀 (추정, 1부 평균에서 Opta 1·2부 리그 점수 차만큼 뺀 2부 규칙 방식)"
        ELO_SRC["2부 추정"] += 1; ELO_LOG[(opp, s)] = ("model2", e, lv); return e, lv
    if (opp, s) in MAN:
        e, lv = MAN[(opp, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(opp, s)] = ("man", e, lv); return e, lv
    MISS.append((opp, d, cid, s)); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(g["opponent"], d, cid)
    et = 1 if (g["gameState"] == "extra_time" and mi > 90) else 0
    row = [typ, g["opponent"], elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))

# ---------------------------------------------------------------- 동료·같은 경기 대조(보고용)
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
TRACKED = set(os.path.basename(x) for x in subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b not in TRACKED or b in ("hon.js", "osi.js"): continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)
MATE_NAME = {"bam.js": "Jonathan Bamba", "iko.js": "Jonathan Ikoné", "ins.js": "Lorenzo Insigne", "kva.js": "Khvicha Kvaratskhelia",
             "mer.js": "Dries Mertens", "pol.js": "Matteo Politano", "san.js": "Leroy Sané"}
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and re.search(r"Osimhen", str(x[13])):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (x[5], x[6], x[2], x[12], x[3])
            cross.append(("동료 도움→오시멘 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "오시멘 골 없음"), x[2:7], hit[0][2:7] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and r[13] == nm:
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (r[5], r[6], r[2], r[12], r[3])
                cross.append(("오시멘 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else "동료 골 없음"), r[2:7], hit[0][2:7] if hit else None))
    for r in E:
        for x in oe:
            if x[9] == r[9] and key(x[1]) == key(r[1]) and (x[2] != r[2] or x[12] != r[12]):
                cross.append(("같은 경기 Elo/lv 다름", b, r[9], r[1], (x[2], x[12]), (r[2], r[12])))
    mdates = {m[0]: m for m in om}
    for m in M:
        if b in MATE_NAME and m[0] in mdates and mdates[m[0]][1] == m[1] and mdates[m[0]][2] != m[2]:
            cross.append(("같은 경기 대회 코드 다름", b, m[0], m[1], mdates[m[0]][2], m[2]))
for gid, evs in EVS.items():
    if gid not in G: continue
    for e in evs:
        if e["scorer_id"] == PID and e["assist_id"] and not e["assist_type"].startswith("Penalty"):
            for b, nm in MATE_NAME.items():
                if e["assist_player"] == nm:
                    d = ldate(G[gid]); oe, om = OTHERS[b]
                    if not any(x[0] == "a" and x[9] == d and re.search(r"Osimhen", str(x[13])) for x in oe):
                        cross.append(("TM 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"], "출전 행 있음" if any(m[0] == d for m in om) else "출전 행 없음"))
DUP = set(); cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 합계
CLUBS = [("2018-08-22", "볼프스부르크"), ("2019-08-01", "샤를루아"), ("2020-09-01", "릴"), ("2024-09-04", "나폴리"), ("9999-12-31", "갈라타사라이")]
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for _, n in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
TM_A_API = sum(int(g["assists"]) for g in games)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
SHOTR = "슈팅 굴절('Shot on goal')"
EXJ = [j for j in judg if j[0] == "도움 제외"]
EX = collections.Counter(j[5] for j in EXJ)
def jl(reason): return ", ".join(f"{d_(j[1])} {j[2]} {j[3]}분 {j[4]}" for j in EXJ if j[5] == reason)
first, last = M[0], M[-1]
NEW_ELO = sorted({(o, s): v for (o, s), v in ELO_LOG.items() if v[0] != "table"}.items(), key=lambda t: (t[0][1], t[0][0]))

NOTE_LINES = [
    f"빅터 오시멘(볼프스부르크·샤를루아·릴·나폴리·갈라타사라이)의 클럽 공식 경기 {NG}경기({d_(first[0])} 보루시아 묀헨글라트바흐전 ~ {d_(last[0])} 슈투트가르트전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    f"클럽별 경기·골·도움: 볼프스부르크 {c3(ST['볼프스부르크'])}, 샤를루아 {c3(ST['샤를루아'])}, 릴 {c3(ST['릴'])}, 나폴리 {c3(ST['나폴리'])}, 갈라타사라이 {c3(ST['갈라타사라이'])}(2024-25 임대 41경기 37골 포함). 출전 분 합계 {MIN_TOT:,}분",
    "경기·출전 분·골 시간·골 뒤 스코어는 Transfermarkt 선수 경기 성적(API)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음(퇴장 경기는 퇴장 시각까지: 2020.10.29 레알 소시에다드전 교체 출전 뒤 경고 누적, 2021.8.22 베네치아전 23분 퇴장, 2023.12.23 AS 로마전 86분 경고 누적)",
    "클럽별·시즌별 경기 수와 골은 영어·이탈리아어 위키백과 경력 표와 모두 같음(위키백과는 2026.11.3 슈투트가르트전을 아직 넣지 않아 1경기 적음). FotMob 경력 합계도 경기·골이 같음",
    "볼프스부르크 2군(U-23) 경기 1경기(2017.11.1 프리미어리그 인터내셔널컵 더비 카운티 U-23전)와 나이지리아 대표팀·청소년 대표팀 경기는 뺌",
    f"PK 골 {NPK}개. 2025.1.25 코냐스포르전 PK 골은 Transfermarkt 22분, FotMob 20분이라 Transfermarkt를 씀. 추가시간 골 시각은 Transfermarkt 표기(FotMob은 90분으로만 적은 경우가 있음)",
    "2025.2.9 아다나 데미르스포르전은 아다나 선수단이 경기장을 떠나 중단됐고 3-0 몰수승으로 처리됨(오시멘 30분 출전, 골·도움 없음). 출전은 넣고 실제 경기에서 나온 골·도움이 없어 점수 영향 없음",
    "도움은 Transfermarkt와 FotMob 경기 이벤트(또는 FotMob 선수 경기 목록)가 같이 적은 것을 기준으로 함",
    f"도움 {NA}개 = Transfermarkt 도움 {TM_A_API}개 − PK 유도 {EX['PK 유도']}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 − 슈팅 굴절 {EX[SHOTR]}개",
    "PK 유도로 뺀 도움: " + jl("PK 유도"),
    "상대 자책골에 붙은 도움으로 뺀 것: " + jl("상대 자책골 유도") + "(FotMob은 자책골로 적음)",
    "슈팅 굴절로 뺀 것: 2026.2.28 알라니아스포르전 58분 토레이라 골(오시멘의 오버헤드킥이 수비에 맞고 튄 공을 토레이라가 넣음, beIN Sports·하베르튀르크 경기 기사. FotMob은 오시멘 도움으로 셈)",
    "Transfermarkt 리포트가 오시멘 본인 PK 골에 본인 도움으로 적은 10개와 2022.11.5 아탈란타전 오시멘이 핸드볼로 내준 PK(리포트 도움 칸에 이름이 붙음)는 도움이 아니라 셈하지 않음(Transfermarkt 선수 경기 성적도 세지 않음)",
    "FotMob 선수 경기 목록에만 있는 도움 1개는 넣지 않음: 2021.5.23 엘라스 베로나전 60분 라흐마니 골(코너킥 뒤 라흐마니 헤더가 오시멘에게 맞고 굴절된 공을 라흐마니가 다시 넣음, Transfermarkt·FotMob 경기 이벤트는 도움 없음)",
    "FotMob 경기 이벤트에 도움자가 없지만 넣은 도움: 2025.4.22 튀르키예컵 준결승 코냐스포르전 47분 살라이 골(Transfermarkt 'Pass', FotMob 선수 경기 목록 도움 1)",
    "날짜는 경기 현지 날짜(모두 유럽 경기)",
    "상대 Elo는 기존 선수 자료의 같은 팀·같은 시즌 값을 먼저 쓰고, 없으면 그 시즌 최종 순위(진행 중인 2026-27은 11월 18일 현재 순위)를 리그 시즌 수준 모형(5대 리그 평균 고정 + UEFA 계수)에 넣음",
    "벨기에 1부 2018-19 순위는 챔피언십 플레이오프 최종 1~6위, 나머지는 정규 시즌 순서(기존 선수 자료와 같은 방식)",
    "벨기에 2부(1B 프로리그 2018-19, 8팀) 베이르스호트·베스터를로는 1부 평균에서 Opta 1·2부 리그 점수 차를 뺀 2부 규칙 방식으로 추정(평균 약 1218). 벨기에 3부(1부 아마추어) 알스트(벨기에컵)와 프랑스 5부(나시오날 3) 공프르빌(쿠프 드 프랑스)은 다른 선수 자료의 프랑스 5부 값 1150으로 추정",
    "대회 비중: 분데스리가 승강 플레이오프(2017.5.29 브라운슈바이크전 1분)와 벨기에 플레이오프 2 조별·유로파리그 플레이오프 결정전 2경기(2019.5.22 코르트레이크전·5.26 앤트워프전)는 리그 비중(다른 선수 자료 선례). DFB-포칼·벨기에컵·쿠프 드 프랑스·쿠프 드 라 리그·코파 이탈리아·튀르키예컵은 국내컵(16강까지 낮은 비중·8강·준결승·결승, 2024-25 튀르키예컵 조별은 리그식). 챔스·유로파는 조별·리그 페이즈와 토너먼트로 나누고 녹아웃 플레이오프는 16강과 같은 비중",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회는 2020-21까지 원정 다득점·연장, 2021-22부터 연장만. 다른 차전 스코어는 Transfermarkt 리포트. 2026.2.25 유벤투스 원정(챔스 녹아웃 플레이오프 2차전, 연장 120분)의 105+1분 골은 연장 골로 계산",
    "시즌은 모든 클럽 8월 1일 기준",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준(준우승·대표팀 기록은 뺌)",
    "2026.11.18 기준: 마지막 출전은 2026.11.3 챔스 슈투트가르트전(90분). 그 뒤 무릎 부상으로 결장 중(FotMob 12월 초 복귀 예상)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "elk", "cl16", "clg"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []; seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6], r[13])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mdates = collections.Counter(m[0] for m in M)
for d, rs in by.items():
    gl = sorted([r for r in rs if r[0] == "g"], key=lambda r: (r[5] + r[6], r[4]))
    for a, b in zip(gl, gl[1:]):
        if b[5] < a[5] + 1 or b[6] < a[6]: problems.append(("스코어 역순", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if MISS:
    for x in MISS: print("상대 Elo 없음:", x)
    sys.exit(1)
open(OUT_JS, "w", encoding="utf-8").write(f"const OSI_E={J(E)};\nconst OSI_M={J(M)};\nconst OSI_NOTE={J(NOTE)};\n")
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg, "cross_check": cross,
           "elo_sources": ELO_SRC, "new_elo": [[o, s, v[1], v[2]] for (o, s), v in NEW_ELO]},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("도움 제외", dict(EX))
print("새 Elo:"); [print("  ", o, s, v[1], v[2]) for (o, s), v in NEW_ELO]
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if not (len(c) > 4 and c[4] == "일치"): print("  대조:", c)
print("일치 대조", sum(1 for c in cross if len(c) > 4 and c[4] == "일치"))
