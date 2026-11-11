#!/usr/bin/env python3
"""Radamel Falcao: raw/ -> falcao.json + src/data/fal.js (판정 근거는 judgments.md)

  python3 players/falcao/build_falcao.py

입력: raw/tm_games.csv(출전·분), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(대조), raw/ranks.txt(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값), src/data/*.js(같은 경기 동료 자료 대조).
"""
import csv, json, os, re, sys, unicodedata, collections, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "fal.js")
OUT_JSON = os.path.join(HERE, "falcao.json")
FAL = "39152"
YOUTH_CLUB = "9251"          # 맨체스터 유나이티드 U21(프리미어리그 2) 1경기 → 제외
GAP = "2014-08-01"           # 이 날짜 전 도움은 Transfermarkt 리포트, 뒤는 Transfermarkt ∩ FotMob

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 판정 표
DATE_FIX = {"994290": "2008-04-02"}   # 멕시코시티 원정(UTC 4.3 03:10 = 현지 4.2 21:10). Transfermarkt·아르헨티나 시간 4.3
# Transfermarkt 리포트 도움 중 넣지 않는 것: gameId|분 -> 이유 (본인 PK 골의 본인 도움·PK 유도·리바운드·자책골·상대 골)
EXCL_A = {}   # 유형으로 자동 판정(아래 assist_reason) + 개별 사유
# 2014.8 이후 Transfermarkt 단일 출처 도움 판정(FotMob 경기 이벤트에 없음)
POST_GAP_OK = {
    "4240839|118": "FotMob 선수 경기 목록 도움 1 + ESPN Deportes·Win Sports·Claro Sports 기사(팔카오 도움)",
}
# 골 분: Transfermarkt가 90분 정각, FotMob이 추가시간을 적은 경우 FotMob 추가시간(인시녜 선례)
MIN_FIX = {"3047611|90": "90+7"}
# FotMob에만 있는 도움(넣지 않음)
FM_ONLY = [
    ("2012-03-29", "하노버 96", "89", "살비오", "Transfermarkt 도움 없음, 아틀레티코 구단 기사·Eurosport 문자중계는 팔카오가 머리로 떨군 공이 살비오에게 흘렀다고 서술(도움 표기 없음). 2014.8 이전이라 Transfermarkt 기준"),
    ("2019-02-02", "툴루즈", "63", "파브레가스", "FotMob 선수 경기 목록만 도움 1. Transfermarkt 도움 없음, 기사(AFP·Reuters 계열)는 팔카오의 슈팅 실패 뒤 흐른 공을 파브레가스가 넣었다고 서술"),
]

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"ARG1", "ARGC", "PO1", "ES1", "FR1", "GB1", "TR1", "COL1", "COLP", "COLO", "COLF"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"                      # 조별·16강
    if cid == "CS":
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"                      # 1라운드·조별·16강
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                      # Second Round(32강)·intermediate stage·16강·8강
    if cid in ("USC", "POSU", "FRCH", "GBCS"): return "df"
    if cid in ("CDR", "POPO", "POCP", "FRC", "FRL", "FAC", "CGB", "TRP", "COPO"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                       # 조별·1~5라운드·16강·FA컵 5라운드(16강)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0               # 두 경기 합산은 tie
    if cid in LEAGUE_IDS: return 0
    if r.startswith("group"): return 0    # 리베르타도레스·수다메리카나·챔스·유로파 조별, 타사 다 리가 조별, 코파 콜롬비아 조별
    return 1

# ---------------------------------------------------------------- 입력
games = [g for g in rd("tm_games.csv") if g["clubId"] != YOUTH_CLUB]
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tmGameId"]].append(r)

def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local"])

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "CLQ", "EL", "ELQ"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid in ("CLI", "CS"): return (1, 0)        # 2017 이전 남미 대회: 원정 다득점, 연장 없이 승부차기(결승 제외)
    if cid == "CDR": return (1, 1)                # 코파 델 레이 2018-19까지
    if cid == "POPO": return (1, 1)               # 2009-10·2010-11 타사 준결승(2011 벤피카전 원정 다득점으로 진출)
    if cid == "TRP": return (0, 1)                # 튀르키예컵: 판페르시 자료 선례(원정 다득점 없음·연장)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["clubId"]: return "h"
    if m["away_id"] == g["clubId"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    m = MI[gid]; s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    oh, oa = map(int, m["other_leg_score"].split(":"))     # 이 리포트의 홈 팀 기준 다른 차전 스코어
    ours, theirs = (oh, oa) if s == "h" else (oa, oh)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def assist_reason(e):
    t = e["assistType"]
    if e["scorerId"] == FAL: return "본인 PK 골에 본인 도움(PK 유도)"
    if e["ownGoal"] == "1": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t.startswith("Handball"): return "상대 PK 허용(본인 핸드볼) — 상대 골"
    return None

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]
    side = side_of(gid)
    prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorerId"] == FAL and e["ownGoal"] != "1"
        is_a = e["assistId"] == FAL
        if not (is_g or is_a): continue
        if (e["side"] != side) and not (is_a and assist_reason(e)):
            sys.exit("득점 편 이상 " + gid + " " + e["minute"])
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        tag = f"{gid}|{e['minute']}"
        mi, dm = mins(MIN_FIX.get(tag, e["minute"]))
        if is_a and not is_g or (is_a and is_g):
            if is_a:
                why = assist_reason(e)
                d = ldate(g)
                if why:
                    judg.append(("도움 제외", d, g["opponent"], e["minute"], e["scorer"], why))
                elif d >= GAP:
                    fm = any(f["falcao_assist"] == "1" and abs(int(f["time"]) + int(f["overloadTime"] or 0) - mi) <= 2 for f in FME[gid])
                    if not fm and tag not in POST_GAP_OK:
                        sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락: " + tag)
                    raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
                else:
                    raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            pk = 1 if e["goalType"] == "Penalty" else 0          # 'Penalty rebound'은 일반 골
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))

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
    k = norm(n)
    return ALIAS.get(k, k)

TABLE = {}
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

RANKS = collections.defaultdict(dict)    # (TM code, saison_id) -> {key: (rank, n, name)}
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        m = re.search(r"\[TM (\w+) saison_id (\d+)\]", p[0])
        RANKS[(m.group(1), m.group(2))][key(p[4])] = (int(p[2]), int(p[3]), p[4])

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

SD2 = 51.24
# 튀르키예 1부 평균 = 2012-13 1473 + 23.33 × (앞뒤 3시즌 UEFA 계수 평균 − 7.333), 흩어짐 119
TR_COEF = {2009: 7.6, 2010: 4.6, 2011: 5.1, 2012: 10.2, 2013: 6.7, 2014: 6.0, 2018: 5.5, 2019: 5.0, 2020: 3.1, 2021: 6.7}
def tr_mean(start):
    c = sum(TR_COEF[y] for y in (start - 1, start, start + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)

# 포르투갈 1부 16팀(2009-10·2010-11): 기존 선수 자료 값(1 1912·2 1786·4 1679·5 1660·8 1578·9 1559·11 1531·12 1518·13 1493·14 1465·16 1421)
PT16 = {1: 1912, 2: 1786, 4: 1679, 5: 1660, 8: 1578, 9: 1559, 11: 1531, 12: 1518, 13: 1493, 14: 1465, 16: 1421}
def pt16(r):
    if r in PT16: return PT16[r]
    lo = max(k for k in PT16 if k < r); hi = min(k for k in PT16 if k > r)
    return round(PT16[lo] + (PT16[hi] - PT16[lo]) * (r - lo) / (hi - lo))

# 기존 자료의 라리가·리그1·프리미어리그 시즌별 순위값(빠진 순위가 없음)
LGPTS = collections.defaultdict(dict)
for (k, s), (e, lv) in TABLE.items():
    if "추정" in lv: continue
    m = re.match(r"(라리가|리그1|프리미어리그) (\d{4}-\d\d) (\d+)위$", lv)
    if m: LGPTS[(m.group(1), m.group(2))][int(m.group(3))] = e

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

ARG_T = {"ARG1": "아페르투라", "ARGC": "클라우수라"}
def rank_model(code, sid, r, n, d):
    """(Elo, lv) for a rank in TM table (code, saison_id)."""
    s_eu = f"{sid}-{str(int(sid) + 1)[2:]}"
    if code in ("ARG1", "ARGC"):
        y = sid if code == "ARG1" else str(int(sid) + 1)
        return round(1583 + 63 * curve(r, n)), f"아르헨티나 1부 {ARG_T[code]} {y} {r}위"
    if code in ("COL1", "COLP"):
        y = str(int(sid) + 1); t = "아페르투라" if code == "COLP" else "피날리사시온"
        return round(1580 + 63 * curve(r, n)), f"콜롬비아 1부 {y} {t} {r}위/{n}팀 (리그 수준 추정)"
    if code == "BRA1":
        return round(1598 + 63 * curve(r, n)), f"브라질 세리에 A {int(sid) + 1} {r}위"
    if code in ("URU1",):
        return round(1540 + 63 * curve(r, n)), f"우루과이 1부 {s_eu} 아페르투라 {r}위/{n}팀 (추정)"
    if code == "PO1":
        if n == 16: return pt16(r), f"포르투갈 1부 {s_eu} {r}위"
    if code == "PO2":
        return round(1367 + SD2 * curve(r, n)), f"포르투갈 2부 {s_eu} {r}위 (추정)"
    if code in ("ES1", "FR1", "GB1"):
        lg = {"ES1": "라리가", "FR1": "리그1", "GB1": "프리미어리그"}[code]
        pts = LGPTS.get((lg, s_eu), {})
        if r in pts: return pts[r], f"{lg} {s_eu} {r}위"
        if lg == "리그1" and "2009" <= s_eu <= "2022-23":     # 리그1 20팀 순위값은 2009-10~2022-23 시즌 공통
            return LGPTS[("리그1", "2016-17")][r], f"{lg} {s_eu} {r}위"
        sys.exit(f"{lg} {s_eu} {r}위 값 없음")
    if code == "ES2":
        return round(1624 + SD2 * curve(r, n)), f"세군다(2부) {s_eu} {r}위"
    if code == "FR2":
        return round(1540 + SD2 * curve(r, n)), f"리그2 {s_eu} {r}위"
    if code == "TR1":
        return round(tr_mean(int(sid)) + 119 * curve(r, n)), f"쉬페르리그 {s_eu} {r}위"
    if code == "TR3B":
        return round(tr_mean(int(sid)) - 324 + SD2 * curve(r, n)), f"튀르키예 3부 {s_eu} 적색조 {r}위/{n}팀 (추정)"
    if code == "E4G4":
        return 1150, f"스페인 4부(세군다 페데라시온) {s_eu} 4조 {r}위 (추정)"
    if code == "FR4B":
        return 1220, f"프랑스 4부(CFA) {s_eu} B조 {r}위 (추정)"
    if code == "FR3":
        return None
    return None

# TM 순위표 선택: 상대가 그 경기 시점에 속한 리그 표(code, saison_id) 후보
def table_candidates(cid, d, opp):
    y, mo = int(d[:4]), int(d[5:7])
    sid_eu = str(y if mo >= 7 else y - 1)
    c = []
    if cid in ("ARG1", "ARGC") or (cid in ("CLI", "CS") and d < "2010"):
        # 아르헨티나: 2~6월 = 그해 클라우수라(ARGC saison_id = 연도−1), 7~12월 = 그해 아페르투라(ARG1 saison_id = 연도)
        if cid == "ARGC" or (cid != "ARG1" and mo <= 6): c.append(("ARGC", str(y - 1)))
        else: c.append(("ARG1", str(y)))
        c += [("BRA1", str(y - 1)), ("URU1", sid_eu)]
    elif cid in ("COL1", "COLO"): c.append(("COL1", str(y - 1)))
    elif cid in ("COLP", "COLF"): c.append(("COLP", str(y - 1)))
    elif cid == "COPO" or (cid == "CS" and d > "2020"): c.append(("COLP", str(y - 1)))
    else:
        for code in ("PO1", "PO2", "ES1", "ES2", "E4G4", "FR1", "FR2", "FR3", "FR4B", "GB1", "TR1", "TR3B"):
            c.append((code, sid_eu))
    return c

# 순위표·기존 자료에 없는 상대(직접 추정, 모두 '추정')
MAN = {
    ("CSD Colo-Colo", "2007"): (1550, "칠레 1부 2007 상위 팀 (추정, 2006 아페르투라·클라우수라 우승 팀, 다른 선수 자료의 칠레 1위권 값과 같은 수준)"),
    ("CF América", "2007-08"): (1560, "리가MX 2007-08 (추정, 다른 선수 자료의 2006-07 값과 같음)"),
    ("CD Universidad Católica", "2008"): (1480, "칠레 1부 2008 (추정)"),
    ("Universidad San Martín de Porres", "2008"): (1400, "페루 1부 2008 상위 팀 (추정, 2007 우승 팀, 다른 선수 자료의 페루 상위 팀 값과 같음)"),
    ("Universidad San Martín de Porres", "2009"): (1400, "페루 1부 2009 상위 팀 (추정, 2008 우승 팀, 다른 선수 자료의 페루 상위 팀 값과 같음)"),
    ("Club Nacional Asunción", "2009"): (1450, "파라과이 1부 2009 (추정, 다른 선수 자료의 2014 값과 같음)"),
    ("Deportivo Guadalajara", "2008-09"): (1600, "리가MX 2008 아페르투라 중위권 (추정)"),
    ("Juventude Évora SC", "2010-11"): (1150, "포르투갈 아마추어 리그 (추정)"),
    ("Vannes OC", "2013-14"): (1263, "프랑스 3부(나시오날) 2013-14 17위 (추정)"),
    ("Atlético de Lugones", "2023-24"): (1100, "스페인 5부(테르세라 페데라시온) (추정)"),
    ("KRC Genk", "2010-11"): (1784, "벨기에 1부 2010-11 1위 (추정, 같은 시즌 2~16위 다른 선수 자료 값에 맞춘 모형값)"),
    ("Rapid Vienna", "2010-11"): (1440, "오스트리아 분데스리가 2010-11 5위 (추정)"),
    ("CSKA Sofia", "2010-11"): (1450, "불가리아 1부 2010-11 3위 (추정)"),
    ("Celtic FC", "2011-12"): (1620, "스코틀랜드 2011-12 1위 (추정, 다른 선수 자료의 2009-10·2012-13 값과 같은 수준)"),
}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
ARG_SEEN = collections.defaultdict(set)    # (key, year) -> {(Elo, lv)} 아르헨티나 반기 대회 충돌 확인

def opp_elo(opp, d, cid):
    k = kr = key(opp)
    if opp == "Arsenal FC" and cid in ("ARG1", "ARGC", "CLI", "CS"): k = key("Arsenal de Sarandí")   # 아르헨티나 아스널(사란디)
    y = d[:4]
    south = cid in ("ARG1", "ARGC", "CLI", "CS", "COL1", "COLP", "COLO", "COLF", "COPO")
    seasons = [y, eu(d)] if south else [eu(d)]
    for s in seasons:
        if (k, s) in TABLE:
            e, lv = TABLE[(k, s)]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(opp, s)] = ("table", e, lv)
            return e, lv
    for code, sid in table_candidates(cid, d, opp):
        tab = RANKS.get((code, sid), {})
        if kr in tab:
            r, n, _ = tab[kr]
            res = rank_model(code, sid, r, n, d)
            if res:
                e, lv = res
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(opp, seasons[0])] = ("model", e, lv)
                return e, lv
    for s in seasons:
        if (opp, s) in MAN:
            e, lv = MAN[(opp, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(opp, s)] = ("man", e, lv)
            return e, lv
    MISS.append((opp, d, cid, tuple(seasons))); return 0, "?"

# ---------------------------------------------------------------- 행 만들기
E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(g["opponent"].strip(), d, cid)
    et = 1 if (g["gameState"] == "extra_time" and mi > 90 and ko) else 0
    row = [typ, g["opponent"].strip(), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)

# 아르헨티나 반기 대회: 같은 팀·같은 해에 값이 둘이면 평균으로 맞춤(통합표 시즌 키가 연도)
grp = collections.defaultdict(list)
for r in E:
    if r[12].startswith("아르헨티나 1부") and "추정" not in r[12]:
        grp[(key(r[1]), r[9][:4])].append(r)
ARG_AVG = []
for (k, y), rs in grp.items():
    vals = sorted({(r[2], r[12]) for r in rs})
    if len(vals) > 1:
        avg = round(sum(v for v, _ in vals) / len(vals))
        parts = "·".join(lv.replace("아르헨티나 1부 ", "").replace(f" {y}", "") for _, lv in vals)
        lv = f"아르헨티나 1부 {y} (추정, {parts} 값 {'·'.join(str(v) for v, _ in vals)}의 평균)"
        for r in rs: r[2] = avg; r[12] = lv
        ARG_AVG.append((rs[0][1], y, [v for v, _ in vals], avg))

E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(수정 없음, 보고용)
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "fal.js"): continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)
MATE_NAME = {"mba.js": "Kylian Mbappé", "hig.js": "Gonzalo Higuaín", "dim.js": "Ángel Di María", "roo.js": "Wayne Rooney",
             "van.js": "Robin van Persie", "bsi.js": "Bernardo Silva", "haz.js": "Eden Hazard", "fab.js": "Cesc Fàbregas"}
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and "Falcao" in str(x[13]):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (x[5], x[6], x[2], x[12], x[3])
            cross.append(("동료 도움→팔카오 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "팔카오 골 없음"),
                          x[2:7], hit[0][2:7] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and r[13] == nm:
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (r[5], r[6], r[2], r[12], r[3])
                cross.append(("팔카오 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else "동료 골 없음"),
                              r[2:7], hit[0][2:7] if hit else None))
    for r in E:   # 같은 날·같은 상대 Elo·lv
        for x in oe:
            if x[9] == r[9] and key(x[1]) == key(r[1]) and (x[2] != r[2] or x[12] != r[12]):
                cross.append(("같은 경기 Elo/lv 다름", b, r[9], r[1], (x[2], x[12]), (r[2], r[12])))
# TM 리포트상 동료 도움인데 동료 파일에 없는 것(PK 유도 제외)
for gid, evs in EVS.items():
    if gid not in G: continue
    for e in evs:
        if e["scorerId"] == FAL and e["assistId"] and e["assistId"] != FAL and not e["assistType"].startswith("Penalty"):
            for b, nm in MATE_NAME.items():
                if e["assist"] == nm or (nm == "Cesc Fàbregas" and "Fàbregas" in e["assist"]):
                    d = ldate(G[gid]); oe, om = OTHERS[b]
                    has_m = any(m[0] == d for m in om)
                    has_a = any(x[0] == "a" and x[9] == d and "Falcao" in str(x[13]) for x in oe)
                    if not has_a:
                        cross.append(("Transfermarkt 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assistType"] or "(유형 빈칸)",
                                      "출전 행 있음" if has_m else "출전 행도 없음"))
DUP = set()
cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 클럽별 합계
CLUBS = [("2009-08-01", "리버 플레이트"), ("2011-08-18", "포르투"), ("2013-07-01", "아틀레티코 마드리드"),
         ("2014-09-01", "모나코 1기"), ("2015-07-01", "맨체스터 유나이티드"), ("2016-07-01", "첼시"),
         ("2019-09-02", "모나코 2기"), ("2021-09-04", "갈라타사라이"), ("2024-07-01", "라요 바예카노"), ("9999-12-31", "미요나리오스")]
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
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
POST_A = NA - PRE_A
NEXCL = len([j for j in judg if j[0] == "도움 제외"])
TM_A_ALL = sum(1 for gid, evs in EVS.items() if gid in G for e in evs if e["assistId"] == FAL)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
mon = [ST["모나코 1기"][i] + ST["모나코 2기"][i] for i in range(3)]
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
def jl(reason):
    return ", ".join(f"{d_(j[1])} {j[2]} {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)

# 상대 Elo 직접 추정 목록
MAN_USED = sorted({(o, s) for (o, s), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[1])

# ---------------------------------------------------------------- 설명(NOTE)
SHOT = "슈팅 리바운드('Shot on goal')"
first, last = M[0], M[-1]
KO_OPP = {"Instituto ACC": "인스티투토", "CD O'Higgins": "오이긴스"}
NOTE_LINES = [
    f"라다멜 팔카오(리버 플레이트·포르투·아틀레티코 마드리드·모나코·맨체스터 유나이티드·첼시·갈라타사라이·라요 바예카노·미요나리오스)의 클럽 공식 경기 {NG}경기({d_(first[0])} {KO_OPP[first[1]]}전 ~ {d_(last[0])} {KO_OPP[last[1]]}전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    f"클럽별 경기·골·도움: 리버 플레이트 {c3(ST['리버 플레이트'])}, 포르투 {c3(ST['포르투'])}, 아틀레티코 마드리드 {c3(ST['아틀레티코 마드리드'])}, "
    f"모나코 {c3(mon)}(2013-14 {c3(ST['모나코 1기'])}, 2016-19 {c3(ST['모나코 2기'])}), 맨체스터 유나이티드 {c3(ST['맨체스터 유나이티드'])}, 첼시 {c3(ST['첼시'])}, "
    f"갈라타사라이 {c3(ST['갈라타사라이'])}, 라요 바예카노 {c3(ST['라요 바예카노'])}, 미요나리오스 {c3(ST['미요나리오스'])}",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(API, 출전 {NG}경기·{MIN_TOT}분)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음",
    "클럽별 경기·골은 스페인어·영어 위키백과 경력 표와 같음(클럽 합계 리버 111경기 45골, 포르투 87·72, 아틀레티코 91·70, 모나코 140·83, 맨유 29·4, 첼시 12·1, 갈라타사라이 43·20, 라요 80·12, 미요나리오스 40·12). 시즌 단위 차이는 포르투 2010-11(위키 44경기, Transfermarkt 42경기)·모나코 2018-19(위키 38경기, Transfermarkt 39경기)뿐이고 경기별 자료가 있는 Transfermarkt를 따름",
    "FotMob 경력 합계와도 경기·골이 같음(2010-11 이후 골은 FotMob 경기 기록과 하나씩 대조). FotMob 경기 기록은 2010-11 이전이 없어 리버 플레이트·포르투 2009-10은 Transfermarkt 리포트만 씀",
    "라세로스 보야카(콜롬비아 2부, 1999~2000년 위키백과 8~11경기 2골)는 경기별 기록(날짜·상대·분)이 없어 넣지 않음. 맨체스터 유나이티드 U21(2015.3.10 프리미어리그 2 토트넘 U21전 72분)과 콜롬비아 대표팀 경기는 뺌",
    f"PK 골 {NPK}개는 Transfermarkt 골 유형 기준(FotMob과 같음). 2018.2.4 리옹전 36분 골은 PK가 막힌 뒤 리바운드 골이라 일반 골로 셈",
    "골 시각은 Transfermarkt 기준. FotMob과 2~3분 다른 골: 2010.8.22 베이라마르전 80분(FotMob 83분), 2011.11.6 헤타페전 28분(FotMob 30분), 2012.8.27 아틀레틱전 41분(FotMob 43분). 2018.12.4 아미앵전 두 번째 PK 골은 Transfermarkt가 90분, FotMob이 90+7분이라 추가시간 표기(90+7)를 씀",
    "2010.10.25 레이리아전 75분 골은 Transfermarkt가 카를랑의 PK(73분, 4-1) 다음 골(5-1)로, FotMob이 카를랑 PK(83분)보다 먼저 들어간 골(5-0)로 적음. 경기 기사(Trivela)가 카를랑의 PK를 후반 29분으로 적어 Transfermarkt 순서(골 직전 4-1)를 씀",
    "2024.12.5 산타페전 17분 골은 FotMob이 수비수 야나스의 골로 적었으나 Transfermarkt와 경기 기사(Noticias RCN·Soccerway)가 야나스의 슈팅을 골라인에서 밀어 넣은 팔카오 골로 적어 팔카오 골로 셈",
    "Transfermarkt 리포트 머리의 최종 스코어가 골 목록과 다른 3경기(2007.2.22 콜로콜로전 3-3, 2021.11.6 레알 마드리드전 3-2, 2026.4.7 오이긴스전 4-3)는 골 목록·선수 경기 성적의 스코어(1-2·2-1·2-0)를 씀",
    "도움은 2014.8.1 이전은 Transfermarkt 리포트 도움을 쓰고, 그 뒤는 FotMob 경기 기록과 Transfermarkt가 같이 적은 도움을 기준으로 함",
    f"도움 {NA}개 = Transfermarkt 리포트 도움 {TM_A_ALL}개 − PK 유도 {EX['PK 유도']}개 − 본인 PK 골에 본인 도움으로 적힌 {EX['본인 PK 골에 본인 도움(PK 유도)']}개 − 'Shot on goal' 리바운드 {EX[SHOT]}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 − 핸드볼로 상대 PK를 내준 {EX['상대 PK 허용(본인 핸드볼) — 상대 골']}개(선수 경기 성적의 도움 62개와 리포트의 차이는 본인 PK 골 5개와 이 핸드볼 1개)",
    "PK 유도로 뺀 도움: " + jl("PK 유도"),
    "본인 PK 골의 본인 도움으로 뺀 것: " + jl("본인 PK 골에 본인 도움(PK 유도)"),
    "리바운드·자책골·상대 골이라 뺀 것: " + jl(SHOT) + " (슈팅 리바운드), " + jl("상대 자책골 유도") + " (상대 자책골), " + jl("상대 PK 허용(본인 핸드볼) — 상대 골") + " (팔카오 핸드볼로 내준 보르도 PK 골)",
    "2014.8 이후 FotMob 경기 기록에 없지만 넣은 도움: 2024.1.6 코파 델 레이 우에스카전 118분(연장) 발렌틴 골. Transfermarkt(유형 빈칸)·FotMob 선수 경기 목록(도움 1)·ESPN Deportes·Win Sports 기사가 팔카오 도움으로 적음",
    "FotMob에만 있는 도움 2개는 넣지 않음: 2012.3.29 유로파 하노버전 89분 살비오 골(팔카오가 머리로 떨군 공이 흘렀다는 기사뿐, Transfermarkt 도움 없음), 2019.2.2 툴루즈전 63분 파브레가스 골(FotMob 선수 경기 목록만 도움, 기사는 팔카오의 슈팅 실패 뒤 흐른 공으로 서술)",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처이고 다른 출처로 대조하지 못함(FotMob 경기 기록에 2010~13 도움이 거의 없음). 유형 칸이 빈 2010.2.2 스포르팅전 18분 롤란두 골·2010.4.18 기마랑이스전 27분 헐크 골 도움도 도움으로 셈. 그 뒤 도움 {POST_A}개는 FotMob 경기 기록과 모두 같음",
    "날짜는 경기 현지 날짜. 남미 저녁 경기는 Transfermarkt 리포트 날짜(중부 유럽 기준)보다 하루 앞인 현지 날짜를 씀. 2008.4.2 리베르타도레스 클루브 아메리카 원정(멕시코시티 21시 10분)은 Transfermarkt 날짜 4.3이 아르헨티나 기준이라 현지 날짜로 고침",
    "상대 Elo는 기존 선수 자료의 같은 팀·같은 시즌 값을 먼저 쓰고, 없으면 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 모형에 넣음. 같은 경기의 동료 자료(이과인·음바페·판페르시·루니·디 마리아)와 상대 Elo·수준 설명이 모두 같음",
    "아르헨티나 1부는 아페르투라·클라우수라 대회별 순위(평균 1583, 이과인·아구에로 자료와 같은 방식). 한 해에 두 대회 순위가 다른 팀은 두 값의 평균으로 맞춤: " + ", ".join(f"{o} {y}({'·'.join(map(str, v))} → {a})" for o, y, v, a in ARG_AVG),
    "포르투갈 1부 2009-10·2010-11(16팀)은 기존 선수 자료의 순위값을 쓰고 빈 순위(3·6·7·10·15위)는 앞뒤 순위값 사이로 메움. 포르투갈 2부(샤베스 2009-10 15위·모레이렌스 2010-11 8위)는 디 마리아 자료와 같은 2부 모형(추정)",
    "쉬페르리그 2019-20·2020-21은 기존 튀르키예 회귀식(리그 평균 = 앞뒤 3시즌 UEFA 국가 계수 평균의 함수, 계수 5.5·5.0·3.1·6.7)으로 평균 약 1408·1417, 흩어짐 119. 바샥셰히르 2020-21은 다른 선수 자료의 같은 시즌 값 1600(전 시즌 우승 팀 추정값)을 그대로 씀(그 시즌 순위 12위 모형값보다 높음). 투즐라스포르 2019-20(3부 적색조 4위)은 1부 평균에서 두 단계 내린 추정",
    "콜롬비아 1부는 콰드라도 자료와 같은 리그 수준 추정(평균 1580·흩어짐 63, 근거 약함). 순위는 그 대회(2024 피날리사시온·2025 아페르투라·2026 아페르투라) 정규 단계 순위이고, 결선 4팀 리그(쿠아드랑굴라르) 경기도 그 대회 순위를 씀",
    "남미 대회 상대: 보타포구 2007 브라질 세리에 A 9위, 데펜소르 스포르팅 2007-08 우루과이 아페르투라 1위(우루과이 평균 1540), 아르헨티나 상대는 그 반기 대회 순위. 다른 선수 자료와 같은 팀·시즌 값을 쓴 것: 보카 주니어스 2007 1700·에스투디안테스 2009 1650",
    "리그 표가 없는 상대는 당시 수준을 추정함(모두 '추정'): " + ", ".join(f"{o} {s} {ELO_LOG[(o, s)][1]}" for o, s in MAN_USED),
    "코파 리베르타도레스 조별·16강과 코파 수다메리카나 16강까지·조별·1라운드는 남미 대회 낮은 단계, 수다메리카나 8강·4강은 높은 단계로 계산함. 콜롬비아 리그 결선 4팀 리그는 리그 경기로, 코파 콜롬비아 조별은 리그식 국내컵으로 계산함",
    "타사 다 리가 조별은 리그식 국내컵, 수페르타사·UEFA 슈퍼컵·커뮤니티 실드·트로페 데 샹피옹은 국내컵 결승, 유로파 32강('Second Round'·'intermediate stage')은 토너먼트로 계산함",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·코파 델 레이·타사 드 포르투갈 준결승(2010·2011)은 원정 다득점·연장 적용(2011 벤피카전은 원정 다득점으로 진출), 2007·2008 수다메리카나·리베르타도레스는 원정 다득점 있고 연장 없이 승부차기(2007 데펜소르전은 원정 다득점으로 진출), 튀르키예컵은 판페르시 자료처럼 원정 다득점 없이 연장으로 계산함(규정 문서는 확인 못 함)",
    "못 뛴 다른 차전 스코어를 리포트로 채움: 2011.2.2 타사 준결승 1차전 포르투 0-2 벤피카, 2013.1.31 코파 델 레이 준결승 1차전 아틀레티코 2-1 세비야, 2019.12.4 튀르키예컵 5라운드 1차전 갈라타사라이 0-2 투즐라스포르",
    "연장 경기: 2013.5.17 코파 델 레이 결승(레알 마드리드, 120분, 도움은 35분), 2024.1.6 우에스카전(연장 118분 도움). 승부차기로 끝난 2010.1.20 벨레넨스스전(103분, 골은 15분)·2017.1.10 소쇼전·2022.12.21 사군티노전은 Transfermarkt 출전 분 그대로 씀",
    "시즌은 8월 1일 기준(유럽 클럽, 모나코 2016.7.27 챔스 예선은 음바페·베르나르두 실바 자료처럼 2015-16으로 셈), 리버 플레이트·미요나리오스는 달력 연도 기준(이과인 리버 플레이트·콰드라도 미요나리오스 선례)",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 콜롬비아 U20 남미 선수권 우승은 뺌. 포르투갈 리그 2011-12 우승(시즌 첫 경기만 뛰고 이적)은 Transfermarkt대로 셈. 포르투갈컵·슈퍼컵 연도는 Transfermarkt 표기 그대로(슈퍼컵 '2011'·'2012'는 실제 2010.8.7·2011.8.7 경기)",
    "2026.11.11 기준: 마지막 출전은 2026.5.26 수다메리카나 오이긴스전. 미요나리오스와 계약이 2026.6.30 끝났고(Transfermarkt 무소속 표기) 은퇴 발표는 없음(언론은 파나마 거주·새 팀 물색 보도)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "csa", "lib"]:
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
js = f"const FAL_E={J(E)};\nconst FAL_M={J(M)};\nconst FAL_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg,
           "fm_only_assists_not_added": FM_ONLY, "cross_check": cross, "elo_sources": ELO_SRC,
           "elo_log": {f"{o}|{s}": v for (o, s), v in ELO_LOG.items()}, "argentina_avg": ARG_AVG},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if c[4] != "일치" if len(c) > 4 and c[0].startswith(("동료", "팔카오")) else True: print("  대조:", c)
