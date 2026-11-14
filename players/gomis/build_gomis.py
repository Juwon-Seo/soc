#!/usr/bin/env python3
"""Bafétimbi Gomis: raw/ -> gomis.json + src/data/gms.js (판정 근거는 judgments.md)

  python3 players/gomis/build_gomis.py

입력: raw/tm_games.csv(출전·분), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(대조), raw/ranks.txt(Transfermarkt 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(같은 경기 다른 선수 자료·리그 순위값).
뒤쪽은 elo_gomis.py(직접 추정 MAN)와 out_gomis.py(대조·설명·점검·출력)를 exec로 읽음.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1: ROOT = os.path.abspath(sys.argv[1])     # 검증용 복사본에 쓰기
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "gms.js")
OUT_JSON = os.path.join(HERE, "gomis.json")
JP = "22388"
GAP = "2014-08-01"   # 이 날짜 전 도움은 Transfermarkt 리포트, 뒤는 Transfermarkt ∩ FotMob(+ 기사 확인)

try:
    TRACKED = set(os.path.basename(p) for p in subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
except Exception:
    TRACKED = None

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 판정 표
# 2014.8 이후 Transfermarkt에만 있는 도움(그 경기 FotMob 기록에 도움 자료가 전혀 없음 → 경기 기사로 확인되면 넣음): gameId|분 -> 근거 / None(뺌)
POST_GAP = {
    "2518105|58": "Sky Sports 경기 기사(배로가 고미스의 크로스를 가까이서 밀어 넣음)·worldfootball 득점 기록(도움 고미스)",
    "2518105|85": "스완지 시티 구단 경기 기사(고미스가 교체로 들어온 라우틀리지에게 연결)·worldfootball 득점 기록(도움 고미스)",
    "2761053|45": "maxifoot 경기 기사(토뱅 크로스를 고미스가 머리로 떨궈 마샤슈가 발리 슛)",
    "3148557|79": None,   # 2019.1.21 킹스컵 16강 알파이살리전 나세르 알다우사리 골: 경기 기사(goal.com 아랍어판 등)는 골만 적고 도움자 없음
    "3941839|27": None,   # 2022.10.19 튀르키예컵 카스타모누스포르전 27분: 공식 기록·문자중계는 상대 라마잔 이으크 자책골, 일부 기사만 라시차 골 → 도움 인정 안 함
    "3941839|56": "Fanatik·DHA 경기 기사(베르칸 쿠틀루 패스를 받은 고미스가 라시차에게 내줘 4-0)",
    "3941839|74": "Fanatik·DHA 경기 기사(고미스 패스를 케렘 아크튀르크올루가 차 넣어 6-0)",
}
# Transfermarkt 리포트 골 목록이 빠졌거나 순서가 다른 경기: 득점자|분 -> (분, 골 뒤 스코어 홈-원정), 그리고 빠진 골 추가
EV_FIX = {
    # 2014.1.5 쿠프 드 프랑스 라쉬즈쉬르사르트 1-6 리옹: 리포트는 리옹 6골만 적음. FotMob: 41분 피쇼 PK(1-1) → 그 뒤 골 홈 점수 1
    "2387776": {"Bafétimbi Gomis|6": ("6", "0-1"), "Clément Grenier|42": ("42", "1-2"), "Bafétimbi Gomis|56": ("56", "1-3"),
                "Alexandre Lacazette|58": ("58", "1-4"), "Steed Malbranque|66": ("66", "1-5"), "Alexandre Lacazette|79": ("79", "1-6")},
}
EV_ADD = {"2387776": [{"minute": "41", "score_home_away_after": "1-1", "scorer": "Pichot", "scorer_id": "", "assist_player": "", "assist_id": "",
                       "assist_type": "", "penalty": "1", "own_goal": "0"}]}

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"FR1", "FR2", "GB1", "TR1", "SA1", "JAP1"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid in ("FRCH", "TRS", "SASS", "JASP"): return "df"            # 슈퍼컵류 = 국내컵 결승 비중
    if cid in ("FRC", "FRL", "FAC", "CGB", "TRP", "SAKC", "JEMP"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                                                   # 16강까지(FA컵 3·4라운드, 리그컵 2~4라운드 포함)
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "CLQ": return "clq"
    if cid == "ELQ": return "elq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"                  # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        return "elk"                                                  # 3라운드(32강)·16강
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                                  # 32강(intermediate stage·Second Round)·16강·8강
    if cid == "AFCL":
        if r.startswith("quarter"): return "aclk"
        if r.startswith("semi"): return "aclsf"
        if r.startswith("final"): return "aclf"
        return "acl"                                                  # 조별·16강
    if cid == "KLUB": return "cwc"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE_IDS: return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 입력
games_all = rd("tm_games.csv")
games = [g for g in games_all if g["level"] == "senior"]
RES_G = [g for g in games_all if g["level"] != "senior"]
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

def ldate(g): return g["date_local"]       # 클럽 나라 시간(리포트 날짜와 403경기 모두 같음; 원정·중립 경기도 날짜 바뀌는 시각 없음)
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    if cid in ("CL", "CLQ", "ELQ", "UEFA", "EL"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid == "TRP": return (1, 1) if d < "2021-07-01" else (0, 1)    # 튀르키예컵: 2020-21까지 원정 다득점·연장
    if cid == "AFCL": return (1, 1) if d < "2022-01-01" else (0, 1)   # AFC 챔스 2019 토너먼트: 원정 다득점·연장(대회 규정 11.3), 2023-24는 원정 다득점 없음(호날두 선례)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid); oid = m["other_leg_id"]
    if oid in G:
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), g["round"])
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def events(gid):
    evs = [dict(e) for e in EVS[gid]] + [dict(e) for e in EV_ADD.get(gid, [])]
    fx = EV_FIX.get(gid)
    if fx:
        for e in evs:
            v = fx.get(e["scorer"] + "|" + e["minute"])
            if v: e["minute"], e["score_home_away_after"] = v
    if fx or gid in EV_ADD:
        evs.sort(key=lambda e: sum(map(int, e["score_home_away_after"].split("-"))))
    return evs

def fm_ev(gid, after_ha):
    for f in FME.get(gid, []):
        if f["newScore_home_away"] == after_ha and f["pen_shootout_event"] != "True": return f
    return None

def assist_reason(e):
    t = e["assist_type"]
    if e["scorer_id"] == JP: return "본인 골에 본인 도움"
    if e["own_goal"] == "1": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

raw_rows, judg, post_gap_log, min_fix, own_goals = [], [], [], [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid)
    prev = (0, 0)
    for e in events(gid):
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        if e["scorer_id"] == JP and e["own_goal"] == "1":
            own_goals.append((gid, ldate(g), opp(g), e["minute"])); continue
        is_g = e["scorer_id"] == JP
        is_a = e["assist_id"] == JP
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        f = fm_ev(gid, e["score_home_away_after"])
        if dm == 0 and mi in (45, 90) and f and f["overloadTime"] and int(f["time"]) == mi and int(f["overloadTime"]) > 0:
            dm = f"{mi}+{int(f['overloadTime'])}"; min_fix.append((gid, ldate(g), opp(g), e["minute"], dm)); mi = mi + int(f["overloadTime"])
        d = ldate(g); tag = f"{gid}|{e['minute']}"
        if is_a:
            why = assist_reason(e)
            fm_ok = bool(f and f["gomis_assist"] == "1")
            if why:
                judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], why))
            elif d >= GAP and not fm_ok:
                v = POST_GAP.get(tag, "미판정")
                post_gap_log.append((gid, d, opp(g), e["minute"], e["scorer"], e["assist_type"], v))
                if v == "미판정": sys.exit("[판정 필요] 2014.8 이후 Transfermarkt 단일 도움 " + tag)
                if v: raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
                else: judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], "2014.8 이후 Transfermarkt에만 있고 경기 기사로 확인 못 함"))
            else:
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            pk = 1 if e["penalty"] == "1" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))

fm_only_seen, fm_goal_diff = [], []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        tm = [e for e in events(gid) if e["score_home_away_after"] == f["newScore_home_away"]]
        if f["gomis_assist"] == "1" and not any(e["assist_id"] == JP for e in tm):
            fm_only_seen.append((gid, ldate(G[gid]), opp(G[gid]), f["time"], f["scorer"]))
        if f["gomis_scorer"] == "1" and f["pen_shootout_event"] != "True" and f["ownGoal"] not in ("True", "1"):
            mine = [e for e in events(gid) if e["scorer_id"] == JP and e["own_goal"] != "1"]
            if not mine: sys.exit("[판정 필요] FotMob 전용 골 " + gid)
            hit = [e for e in tm if e["scorer_id"] == JP]
            if hit and (hit[0]["penalty"] == "1") != (f["goalDescriptionKey"] == "penalty"):
                fm_goal_diff.append((gid, ldate(G[gid]), opp(G[gid]), f["time"], "PK 표기 다름 TM=" + hit[0]["penalty"]))
for gid, g in G.items():
    pm = FPM.get(g["fotmobMatchId"])
    if pm and int(pm["assists"] or 0) > int(g["assists"] or 0):
        fm_only_seen.append((gid, ldate(g), opp(g), "선수 경기 목록", pm["assists"]))

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
        if "고미스" in r["선수"]: continue
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "gms.js") or (TRACKED is not None and b not in TRACKED): continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)

# 리그 순위값: 기존 선수 자료 lv '<리그> <시즌> N위' (추정 제외)
LGPTS = collections.defaultdict(dict)
for b, (oe, om) in OTHERS.items():
    for x in oe:
        lv = str(x[12])
        if "추정" in lv: continue
        m = re.match(r"(.+?) (\d{4}(?:-\d\d)?) (\d+)위$", lv)
        if m: LGPTS[(m.group(1), m.group(2))][int(m.group(3))] = x[2]

def fill(known, n):
    out = {}; ks = sorted(known)
    for r in range(1, n + 1):
        if r in known: out[r] = known[r]; continue
        lo = max([k for k in ks if k < r], default=None); hi = min([k for k in ks if k > r], default=None)
        if lo is None or hi is None: continue
        out[r] = round(known[lo] + (known[hi] - known[lo]) * (r - lo) / (hi - lo))
    return out

# 사우디 프로리그 16팀(2018-19~2021-22): 다른 선수 자료 2022-23(16팀) 순위값 + 빈 순위는 이웃 값의 가운데.
# 1·2·16위(양 끝)는 기존 18팀 순위값(2023-24~)을 같은 상대 위치로 옮긴 값(1위 1813, 2위 1695, 16위 1352)
SA16 = fill({1: 1813, 2: 1695, 3: 1629, 4: 1594, 5: 1576, 6: 1552, 8: 1498, 9: 1480, 10: 1466, 12: 1443, 13: 1418, 15: 1378, 16: 1352}, 16)
LGNAME = {"FR1": "리그1", "FR2": "리그2", "GB1": "프리미어리그", "TR1": "쉬페르리그", "SA1": "사우디 프로리그", "JAP1": "J1리그"}

BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio", "sfc",
        "atletico", "ca", "us", "as", "ss", "ssc", "hsc", "osc", "acf", "olympique", "stade", "fk", "sv", "saint", "paris", "cd", "deportivo", "al"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, {(x[2], x[12]) for b, x in cand}

MAN = {}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def season_keys(d, cid):
    if cid in ("JAP1", "JEMP", "JASP") or (cid == "AFCL" and d >= "2023-01-01"): return [d[:4], eu(d)]
    return [eu(d), d[:4]]
def rank_val(lg, s, o):
    tab = RANKS.get((lg, s), {})
    if key(o) not in tab: return None
    r, n, _ = tab[key(o)]
    name = LGNAME[lg]
    if lg == "SA1" and n == 16: return SA16[r], f"{name} {s} {r}위"
    vals = fill(LGPTS.get((name, s), {}), n)
    if r in vals: return vals[r], f"{name} {s} {r}위"
    return None
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand}))
        return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    for s in season_keys(d, cid):
        if (o, s) in MAN:
            e, lv = MAN[(o, s)]; ELO_SRC["직접 추정·순위 확인"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for s in season_keys(d, cid):
        if (key(o), s) in TABLE:
            e, lv = TABLE[(key(o), s)]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv); return e, lv
    for lg in ("FR1", "FR2", "GB1", "TR1", "SA1", "JAP1"):
        for s in season_keys(d, cid):
            v = rank_val(lg, s, o)
            if v:
                ELO_SRC["순위표+리그 순위값"] += 1; ELO_LOG[(o, d)] = ("model", v[0], v[1]); return v
    MISS.append((o, d, cid, eu(d))); return 0, "?"

exec(open(os.path.join(HERE, "elo_gomis.py"), encoding="utf-8").read())   # MAN 표(판정 기록 7절)

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and ko and not str(dm).startswith("90+")) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))
if MISS:
    for x in sorted(set(MISS), key=lambda t: t[1]): print("MISS", x)
    sys.exit("상대 Elo 없음 %d" % len(MISS))

exec(open(os.path.join(HERE, "out_gomis.py"), encoding="utf-8").read())   # 동료 대조·설명·점검·출력
