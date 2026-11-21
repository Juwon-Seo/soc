#!/usr/bin/env python3
"""Javier Pastore: raw/ -> pastore.json + src/data/pas.js (판정 근거는 judgments.md)

  python3 players/pastore/build_pastore.py

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv(대조), raw/espn_pastore_check.csv(ESPN 대조), raw/ranks.txt(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값), src/data/*.js(같은 경기 다른 선수 자료 대조·재사용).
"""
import csv, json, os, re, sys, unicodedata, collections, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "pas.js")
OUT_JSON = os.path.join(HERE, "pastore.json")
JP = "55215"
GAP = "2014-08-01"           # 이 날짜 전 도움은 Transfermarkt 리포트, 뒤는 Transfermarkt ∩ FotMob(+ 다른 출처 2곳)
# 같은 회차에 다른 판정 에이전트가 쓰는 파일(대조·재사용에서 뺌)
NEW_FILES = {"pas.js", "rau.js", "rno.js", "zid.js", "she.js", "ozi.js", "fod.js", "got.js", "com.js", "cal.js"}

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 판정 표
# 2014.8 이후 Transfermarkt 단일 출처 도움(FotMob 경기 이벤트에 Pastore 도움 없음): gameId|분 -> 근거(넣음) / None(뺌)
POST_GAP = {
    "2518988|79": "maxifoot 경기 기사('faire le break de la tête sur un beau centre de Pastore entré en jeu (2-0, 79e)')·Sports Mole('Javier Pastore crossed the ball in from the left, leaving Ibrahimovic with a simple header'). FotMob은 이 경기 도움 칸이 모두 빔",
    "2547430|60": "maxifoot 경기 기사(파스토레가 두 번째 기둥으로 올린 크로스를 라베치가 헤더, 2-1 60분)·fbref(Opta) PSG 쿠프 드 프랑스 골 기록(도움 파스토레). FotMob은 이 경기 도움 칸이 모두 빔",
    "3080919|82": "Blitz Quotidiano('di testa su cross di Pastore da calcio di punizione')·AP 기사(Fox Sports 등 재게재, 마놀라스가 파스토레 프리킥을 밀어 넣음). FotMob·ESPN은 도움 없이 세트피스로만 적음",
    "3252457|27": None,   # ESPN·FotMob 도움 없음, 기사(Open·코리에레 델로 스포르트)는 세트피스 뒤 스피나촐라의 우연한 헤더 골로만 적음 → 확인 못 함
    "2942875|86": None,   # FotMob·ESPN 모두 뫼니에 도움 → 뺌
}
# FotMob에만 있는 Pastore 도움(Transfermarkt 리포트엔 없음): 모두 뺌
FM_ONLY = {
    "2331181|2": "2014.5.17 몽펠리에전 2분 라베치 골: FotMob만 파스토레 도움. CulturePSG 문자중계는 흐른 공을 라베치가 넣었다고만 적고, 다른 기사도 도움자를 적지 않음(sporteden 한 곳만) → 뺌",
    "2982005|71": "2018.3.6 레알 마드리드전 71분 카바니 골: FotMob만 파스토레 도움. 기사(the42·AP 등)는 파스토레 헤더가 카제미루 맞고 카바니에게 굴절돼 들어갔다고 적음 → 굴절 규칙으로 뺌(cav.js 골 행에도 도움자 표기 없음)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"ARG1", "ARGC", "IT1", "FR1", "ES1", "QSL"}
CUPS = {"CIT", "CDR", "FRC", "FRL"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"
    if cid == "FRCH": return "df"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"     # 3~7라운드·16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE_IDS: return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 입력
games = rd("tm_games.csv")
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

# 현지 날짜: API UTC를 클럽 나라 시간으로 바꾼 날짜(리포트 날짜와 다른 것은 우라칸 2경기뿐, 아르헨티나 현지 날짜 사용)
def ldate(g): return g["date_local_tz_conv"]
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round_report"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    if cid in ("CL", "EL", "ELQ"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid == "CIT": return (1, 1)    # 코파 이탈리아 준결승: 2021-22까지 원정 다득점, 2차전 연장
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G:
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round_report"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
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

def fm_ev(gid, after_ha):
    """같은 골(골 뒤 스코어 홈-원정 같음)의 FotMob 이벤트"""
    for f in FME.get(gid, []):
        if f["newScore_home_away"] == after_ha and f["pen_shootout_event"] != "True": return f
    return None

def assist_reason(e):
    t = e["assist_type"]
    if e["scorer_id"] == JP: return "본인 PK 골에 본인 도움(PK 유도)"
    if e["own_goal"] == "1": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

raw_rows, judg, post_gap_log, min_fix = [], [], [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid)
    prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == JP and e["own_goal"] != "1"
        is_a = e["assist_id"] == JP
        if not (is_g or is_a): continue
        if e["side"][0] != side and not (is_a and assist_reason(e)):
            sys.exit("득점 편 이상 " + gid)
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        # Transfermarkt가 정각 45·90분으로 적고 FotMob이 추가시간을 적은 골은 FotMob 추가시간(인시녜·팔카오 선례)
        f = fm_ev(gid, e["score_home_away_after"])
        if dm == 0 and mi in (45, 90) and f and f["overloadTime"] and int(f["time"]) == mi and int(f["overloadTime"]) > 0:
            dm = f"{mi}+{int(f['overloadTime'])}"; min_fix.append((gid, ldate(g), opp(g), e["minute"], dm)); mi = mi + int(f["overloadTime"])
        d = ldate(g); tag = f"{gid}|{e['minute']}"
        if is_a:
            why = assist_reason(e)
            fm_ok = bool(f and "Pastore" in (f["assistStr"] or ""))
            if why:
                judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], why))
            elif d >= GAP and not fm_ok:
                v = POST_GAP.get(tag, "미판정")
                post_gap_log.append((gid, d, opp(g), e["minute"], e["scorer"], e["assist_type"], v))
                if v == "미판정": sys.exit("[판정 필요] 2014.8 이후 Transfermarkt 단일 도움 " + tag)
                if v: raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
                else: judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], "2014.8 이후 Transfermarkt 단일 출처(다른 출처 확인 못 함 또는 다른 출처가 다른 선수 도움)"))
            else:
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            raw_rows.append(("g", gid, mi, dm, gf, ga, 1 if e["penalty"] == "1" else 0, 0))

# FotMob에만 있는 도움·골 확인(넣지 않음)
fm_only_seen = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        tm = [e for e in EVS.get(gid, []) if e["score_home_away_after"] == f["newScore_home_away"]]
        if f["pastore_assist"] == "1" and not any(e["assist_id"] == JP for e in tm):
            k = f"{gid}|{f['time']}"
            fm_only_seen.append(("a", k, ldate(G[gid]), f["scorer"]))
            if k not in FM_ONLY: sys.exit("[판정 필요] FotMob 전용 도움 " + k)
        if f["pastore_scorer"] == "1" and not any(e["scorer_id"] == JP for e in tm):
            sys.exit("[판정 필요] FotMob 전용 골 " + gid)

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
        if "하비에르 파스토레" in r["선수"]: continue
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
# 세리에C 2018-19 조 A: 다른 선수 자료 노바라 9위 1416을 재현하는 평균(세리에B 1578 − (세리에A 1739 − 1578) ≈ 1417 근처)
SC_MEAN = 1416 - SD2 * curve(9, 19)

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 기존 자료의 리그1 순위값(2009-10~2022-23 시즌 공통 20팀 값)
LGPTS = collections.defaultdict(dict)
for (k, s), (e, lv) in TABLE.items():
    if "추정" in lv: continue
    m = re.match(r"(리그1) (\d{4}-\d\d) (\d+)위$", lv)
    if m: LGPTS[(m.group(1), m.group(2))][int(m.group(3))] = e

def rank_model(lg, season, r, n):
    if lg == "ARG1": return round(1583 + 63 * curve(r, n)), f"아르헨티나 1부 아페르투라 2008 {r}위"
    if lg == "ARGC": return round(1583 + 63 * curve(r, n)), f"아르헨티나 1부 클라우수라 2009 {r}위"
    if lg == "FR1":
        pts = LGPTS.get(("리그1", season), {})
        v = pts.get(r, LGPTS[("리그1", "2016-17")][r])   # 리그1 20팀 순위값은 2009-10~2022-23 시즌 공통
        return v, f"리그1 {season} {r}위"
    return None

def table_candidates(cid, d):
    if cid in ("ARG1", "ARGC"):
        return [("ARG1", "2008-09 Apertura 2008")] if d < "2009-01-01" else [("ARGC", "2008-09 Clausura 2009")]
    return [("FR1", eu(d))]

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b == "hon.js" or b in NEW_FILES: continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio",
        "atletico", "ca", "us", "as", "ss", "ssc", "hsc", "osc", "acf", "olympique", "stade", "fk", "sv", "saint", "paris"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, {(x[2], x[12]) for b, x in cand}

# 순위표·기존 자료에 없는 상대(직접 추정, 모두 '추정')
MAN = {
    ("NK Maribor", "2010-11"): (1420, "슬로베니아 2010-11 1위 (추정, 다른 선수 자료의 마리보르 1위 값 1420과 같음)"),
    ("FC Lausanne-Sport", "2010-11"): (1250, "스위스 2부(챌린지 리그) 2010-11 (추정, 다른 선수 자료 키아소 2012-13 스위스 2부 1250과 같음)"),
    ("FC Differdange 03", "2011-12"): (1250, "룩셈부르크 2011-12 4위 (추정, 다른 선수 자료 F91 뒤들랑주 2018-19 1위 1300보다 낮게)"),
    ("Saint-Colomban Locminé", "2011-12"): (1150, "프랑스 5부(CFA2) (추정, 다른 선수 자료의 프랑스 5부 팀과 같은 수준)"),
    ("Arras Football Association", "2012-13"): (1150, "프랑스 5부(CFA2) 2012-13 A조 5위 (추정, 다른 선수 자료의 프랑스 5부 팀과 같은 수준)"),
    ("Virtus Entella", "2018-19"): (round(SC_MEAN + SD2 * curve(1, 19)), "세리에C 2018-19 조 A 1위 (추정)"),
    ("Al-Ahli SC", "2022-23"): (1439, "카타르 2022-23 8위 (추정, 다른 선수 자료 카타르 2018-19 8위 값과 같음)"),
}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand}))
        return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    south = cid in ("ARG1", "ARGC")
    seasons = [d[:4]] if south else [eu(d)]
    k = key("Arsenal de Sarandí") if (south and o == "Arsenal FC") else key(o)
    for s in seasons:
        if (k, s) in TABLE:
            e, lv = TABLE[(k, s)]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv)
            return e, lv
    for lg, s in table_candidates(cid, d):
        tab = RANKS.get((lg, s), {})
        if key(o) in tab:
            r, n, _ = tab[key(o)]
            res = rank_model(lg, eu(d), r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    for s in seasons:
        if (o, s) in MAN:
            e, lv = MAN[(o, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv)
            return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round_report"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (g["gameState"] == "extra_time" and mi > 90 and ko) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(수정 없음, 보고용)
MATE_NAME = {"ibr.js": "Zlatan Ibrahimović", "cav.js": "Edinson Cavani", "dim.js": "Ángel Di María", "ney.js": "Neymar",
             "mba.js": "Kylian Mbappé", "luc.js": "Lucas Moura", "eto.js": "Samuel Eto'o"}
ALT = {"Edinson Cavani": ("Cavani",), "Zlatan Ibrahimović": ("Ibrahimovi",), "Ángel Di María": ("Di Mar",), "Lucas Moura": ("Lucas",),
       "Neymar": ("Neymar",), "Kylian Mbappé": ("Mbapp",), "Samuel Eto'o": ("Eto",)}
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and "Pastore" in str(x[13]):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7], hit[0][14:]) == (x[5], x[6], x[2], x[12], x[3], x[7], x[14:])
            cross.append(("동료 도움→파스토레 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "파스토레 골 없음"), x[2:8], hit[0][2:8] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and any(t in r[13] for t in ALT[nm]):
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7], hit[0][14:]) == (r[5], r[6], r[2], r[12], r[3], r[7], r[14:])
                has_m = any(m[0] == r[9] for m in om)
                cross.append(("파스토레 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else ("동료 골 없음" + ("" if has_m else "(출전 행도 없음)"))), r[2:8], hit[0][2:8] if hit else None))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[12], x[3]), (r[2], r[12], r[3])))
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                cross.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[2], m[2]))
# Transfermarkt 리포트상 동료 도움 → 파스토레 골인데 동료 파일에 도움 행이 없는 것
for gid, evs in EVS.items():
    if gid not in G: continue
    for e in evs:
        if e["scorer_id"] == JP and e["assist_id"] and not e["assist_type"].startswith("Penalty"):
            for b, nm in MATE_NAME.items():
                if b in OTHERS and any(t in e["assist_player"] for t in ALT[nm]):
                    d = ldate(G[gid]); oe, om = OTHERS[b]
                    if not any(x[0] == "a" and x[9] == d and "Pastore" in str(x[13]) for x in oe):
                        cross.append(("Transfermarkt 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"] or "(유형 빈칸)",
                                      "출전 행 있음" if any(m[0] == d for m in om) else "출전 행도 없음"))
DUP = set()
cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 클럽별 합계
CLUBS = [("2009-07-11", "우라칸"), ("2011-08-01", "팔레르모"), ("2018-07-01", "파리 생제르맹"), ("2021-08-30", "로마"),
         ("2023-01-06", "엘체"), ("9999-12-31", "카타르 SC")]
TMCLUB = {"2063": "우라칸", "458": "팔레르모", "583": "파리 생제르맹", "12": "로마", "1531": "엘체", "965": "카타르 SC"}
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
for g in games:
    if club_of(ldate(g)) != TMCLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for _, n in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
TM_A_ALL = sum(1 for gid, evs in EVS.items() if gid in G for e in evs if e["assist_id"] == JP)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
def jl(reason):
    return ", ".join(f"{d_(j[1])} {j[2]} {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
SAME_N = ELO_SRC["같은 경기 다른 선수 자료"]
MODEL_ARG = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "model" and "아르헨티나" in v[2]}, key=lambda t: t[2])
TABLE_ARG = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "table" and "아르헨티나" in v[2]}, key=lambda t: t[2])

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
NOTE_LINES = [
    f"하비에르 파스토레(우라칸·팔레르모·파리 생제르맹·로마·엘체·카타르 SC)의 클럽 공식 경기 {NG}경기({d_(first[0])} 리버 플레이트전 ~ {d_(last[0])} 움살랄전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n} {c3(v)}" for n, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(출전 {NG}경기)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음",
    "클럽·시즌별 경기·골은 영어 위키백과 경력 표와 모두 같음. 다만 탈레레스(2006-07 프리메라 B 나시오날, 2부) 5경기 0골은 위키백과에만 있고 Transfermarkt·FotMob에 경기 기록(날짜·상대·출전 분)이 없어 뺌(팔카오 라세로스 보야카 선례). 스페인어 위키백과는 카타르 SC 2022-23에 국제 대회 1경기 1골을 더 적었으나 Transfermarkt·영어 위키백과에 없어 넣지 않음",
    "FotMob 경력 합계는 팔레르모 82경기 16골, PSG 269·45, 로마 37·4, 엘체 16·0, 카타르 SC 7·1로 같고, 우라칸은 30경기(위키백과·Transfermarkt 31). FotMob에는 2010-11 이전 경기 기록이 없어 우라칸·팔레르모 2009-10의 골·도움은 Transfermarkt 리포트만 씀",
    "아르헨티나 대표팀 경기와 탈레레스 유소년 기록은 뺌",
    "골은 모두 PK가 아닌 필드 골. 2010-11 이후 골은 FotMob 경기 기록과 수·스코어가 같음(FotMob 기록이 없는 팔레르모 2010-11 6경기·2012.1.8 로크미네전 제외)",
    "2017.4.18 메스전 마튀디 골(파스토레 도움)은 Transfermarkt가 정각 90분, FotMob이 90+3분으로 적어 90+3분으로 씀",
    "도움은 2014.8.1 이전은 Transfermarkt 리포트 도움을 쓰고, 그 뒤는 Transfermarkt와 FotMob 경기 기록이 같이 적은 도움을 기준으로 함. 한쪽에만 있는 도움은 다른 출처 2곳(경기 기사·ESPN 문자중계·fbref 기록)이 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 리포트 도움 {TM_A_ALL}개 − PK 유도 {EX['PK 유도']}개 − 2014.8 이후 Transfermarkt에만 있고 확인되지 않거나 다른 선수 도움으로 적힌 {EX['2014.8 이후 Transfermarkt 단일 출처(다른 출처 확인 못 함 또는 다른 출처가 다른 선수 도움)']}개",
    "PK 유도로 뺀 도움: " + jl("PK 유도"),
    "2014.8 이후 Transfermarkt에만 있어 뺀 도움: 2018.4.15 모나코전 86분 드락슬러 골(FotMob·ESPN 모두 뫼니에 도움), 2019.10.3 유로파리그 볼프스베르거전 27분 스피나촐라 골(FotMob·ESPN 도움 없음, 기사는 세트피스 뒤 우연히 들어간 헤더로만 적음)",
    "2014.8 이후 FotMob 경기 기록에 도움이 없지만 다른 출처 2곳으로 확인해 넣은 도움: 2015.1.5 쿠프 드 프랑스 몽펠리에전 79분 즐라탄 헤더(maxifoot·Sports Mole: 파스토레 크로스), 2015.4.8 쿠프 드 프랑스 준결승 생테티엔전 60분 라베치 헤더(maxifoot·fbref: 파스토레 크로스), 2018.8.27 아탈란타전 82분 마놀라스 골(Blitz Quotidiano·AP: 파스토레 프리킥). 앞의 두 경기는 FotMob 경기 기록에 도움 칸이 모두 비어 있음",
    "FotMob에만 있는 도움 2개는 넣지 않음: 2014.5.17 몽펠리에전 2분 라베치 골(다른 기사는 흐른 공을 라베치가 넣었다고만 적음), 2018.3.6 챔스 레알 마드리드전 71분 카바니 골(파스토레 헤더가 카제미루 맞고 카바니에게 굴절)",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처. 2010-11~2013-14는 ESPN 문자중계와 FotMob으로 일부 대조했고(어긋나는 것 없음), 우라칸·팔레르모 2009-10은 대조할 자료가 없음",
    "날짜는 경기 현지 날짜. 우라칸 2경기(2008.9.12 히므나시아 후후이 원정, 2009.5.23 로사리오 센트랄 원정)는 아르헨티나 저녁 경기라 Transfermarkt 리포트 날짜(중부 유럽 기준)보다 하루 앞",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(카바니·즐라탄·루카스 모우라·디 마리아·음바페·에투 등) 값을 먼저 쓰고({SAME_N}개 기록), 없으면 기존 선수 자료의 같은 팀·같은 시즌 값, 그다음 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 모형에 넣음",
    "아르헨티나 1부는 아페르투라 2008·클라우수라 2009 대회별 순위(평균 1583, 아구에로·팔카오 자료와 같은 방식), 시즌 키는 달력 연도라 다른 선수 자료에 같은 해 값이 있으면 그 값을 씀(벨레스 2008 = 클라우수라 2008 5위 값, 라누스·아르세날 2009 = 클라우수라 2009 값)",
    "리그 표가 없는 상대는 당시 수준을 추정함(모두 '추정'): " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED),
    "대회 비중: 코파 이탈리아·코파 델 레이·쿠프 드 프랑스·쿠프 드 라 리그는 16강까지·8강·준결승·결승, 트로페 데 샹피옹은 국내컵 결승, 유로파리그 예선(2010 마리보르·2011 디페르당주)은 유로파 예선으로 계산함",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(UEFA 대회와 2010-11 코파 이탈리아 준결승 밀란전: 원정 다득점·연장 적용)",
    "시즌은 우라칸은 달력 연도, PSG는 카바니 자료와 같이 7월 10일 기준(2017.7.29 트로페 데 샹피옹 = 2017-18), 나머지는 8월 1일 기준",
    "우승 기록은 Transfermarkt 업적 페이지 기준(PSG 리그1 5회·쿠프 드 프랑스 4회·쿠프 드 라 리그 5회·트로페 데 샹피옹 4회). 2010-11 코파 이탈리아 준우승(팔레르모)은 업적 페이지에 없어 넣지 않음",
    "은퇴: Transfermarkt는 2023.7.1부터 은퇴로 적고 마지막 공식 경기는 2023.5.9 카타르 SC 움살랄전. 영어 위키백과는 2024.11.2 은퇴 예고, 2025.9.10 은퇴했다고 밝힌 것으로 적어 발표 시점은 출처마다 다름(2023.5.9 이후 공식 경기 없음)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elq", "lg"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE):
        sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
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
    allr = sorted(rs, key=lambda r: r[4])
    for a, b in zip(allr, allr[1:]):
        if b[5] < a[5] or b[6] < a[6]: problems.append(("시간순 스코어 역행", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
    if mdates[d] > 1: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if MISS: sys.exit("상대 Elo 없음: " + str(MISS))
js = f"const PAS_E={J(E)};\nconst PAS_M={J(M)};\nconst PAS_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg,
           "post_gap_tm_only": post_gap_log, "post_gap_verdicts": POST_GAP, "fm_only_assists": FM_ONLY, "fm_only_seen": fm_only_seen,
           "minute_fixes": min_fix, "cross_check": cross, "elo_sources": ELO_SRC,
           "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("분 고침", min_fix)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if len(c) > 4 and c[4] != "일치": print("  대조:", c)
print("대조 요약", collections.Counter((c[0], c[4] if len(c) > 4 and c[0].endswith("골") else "") for c in cross))
