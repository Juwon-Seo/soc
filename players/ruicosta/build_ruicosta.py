#!/usr/bin/env python3
"""Rui Costa: raw/ -> ruicosta.json + src/data/rui.js (판정 근거는 judgments.md)

  python3 players/ruicosta/build_ruicosta.py            # 파일 쓰기
  python3 players/ruicosta/build_ruicosta.py --debug    # Elo 출처 로그
  python3 players/ruicosta/build_ruicosta.py --cross    # 동료(셰브첸코·인자기·세도르프·히바우두·카카·디 마리아·비에리) 자료 대조

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골·도움), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv,
      raw/ranks.txt(순위표), elo/opponent_elo_by_team_season.csv·aliases.csv, src/data/*.js(git 추적 파일: 같은 경기 다른 선수 자료),
      players/vieri/staged/vie.js(읽기 전용, 대조용).
피구(fig.js)·셰브첸코(she.js) 빌드 스크립트를 바탕으로 함. 환경 변수 SOC_ROOT로 저장소 위치를 바꿀 수 있음(스크래치 검증용).
"""
import csv, json, os, re, sys, unicodedata, collections, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "rui.js")
OUT_JSON = os.path.join(HERE, "ruicosta.json")
ME_KO = "후이 코스타"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

def ldate(g): return g["date_local_tm_report"] or g["date_local"]   # 리포트(현지) 날짜, 리포트 없는 리그 경기는 일정표(현지) 날짜
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 판정 표 (judgments.md)
# 출전 분 고침: Transfermarkt 90분이지만 전반 뒤 중단된 경기
MIN_FIX = {"1159923": (45, "1998.11.3 UEFA컵 2라운드 2차전 그라스호퍼전(살레르노): 전반 종료 때 폭죽이 대기심을 다치게 해 전반 뒤 중단, UEFA가 0-3 몰수패로 정함 — 실제 경기 45분")}
# 도움 제외: gameId|분 -> 이유
EXCL_A = {
    "1022456|90+4": "슈팅 리바운드('Shot on goal', 토마손)",
    "6201|26": "슈팅 리바운드('Shot on goal', 셰브첸코 탭인)",
    "1173404|45": "상대 자책골 유도(하포엘 텔아비브 게르손 자책골, 유형 Cross)",
}
# 연장이 있었던 단판 경기(Transfermarkt 상태는 정규 종료로 적혔지만 경기 시간 120분, 94·95·102·109분 골)
ET_GAMES = {"4852514": "1993.12.23 타사 5라운드 우니앙 마데이라전: 90분 1-1, 연장 1-5"}
# 몰수·중단 경기(골·도움 기록에는 영향 없음): judgments.md
ODD = {"31091": "2005.4.12 챔스 8강 2차전 인테르전: 73분께 홍염으로 중단, 0-3 몰수승(후이 코스타 30분 출전, 골·도움 없음)",
       "1022592": "2003.2.22 토리노전: 0-3에서 중단, 결과 그대로 인정(63분 출전, 골·도움 없음)"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"PO1", "IT1"}
CUPS = {"POPO", "CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SCI", "USC", "POSU"): return "df"          # 슈퍼컵류 = 국내컵 결승(수페르타사 두 경기·재경기 포함)
    if cid == "WEPO": return "cwc"
    if cid == "CLQ": return "clq"
    if cid == "EPL":                                        # 유러피언컵 1991-92: 조별 전 1·2라운드 = 챔스 예선 비중(기그스·네드베드 선례)
        if r.startswith("group"): return "clg"
        return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"             # 2001-02·2002-03 2차 조별(Group 2·3)도 조별
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"       # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                       # 2·3라운드·32강(intermediate stage)·16강·8강
    if cid == "EPP":                                       # 컵위너스컵 1996-97: 호나우두·인자기 선례(유로파 토너먼트)
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

def tie_rule(cid):
    """(원정 다득점, 연장)"""
    if cid in ("UEFA", "CL", "CLQ", "EPP", "EPL", "CIT"): return (1, 1)
    sys.exit("합산 규칙 없음 " + cid)                       # 수페르타사 두 경기 결승에는 골·도움 없음

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    oid = MI[gid]["other_leg_id"] or TIES_RAW[gid]["other_leg_id"]
    o = MI[oid]
    oh, oa = map(int, o["final"].split(":"))
    if o["home_id"] == G[gid]["club_id"]: return (oh, oa)
    if o["away_id"] == G[gid]["club_id"]: return (oa, oh)
    sys.exit("다른 차전 팀 불일치 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"])
    if "1st" in rnd: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
judg = []
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    mins_ = int(g["playedMinutes"])
    if g["gameId"] in MIN_FIX:
        judg.append(("출전 분 고침", ldate(g), opp(g), mins_, MIN_FIX[g["gameId"]][0], MIN_FIX[g["gameId"]][1]))
        mins_ = MIN_FIX[g["gameId"]][0]
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), mins_])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

raw_rows, SEQ_DIFF, ATYPES = [], [], collections.Counter()
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        bh, ba = (h - 1, a) if e["side"] == "home" else (h, a - 1)
        if (bh, ba) != prev: SEQ_DIFF.append((gid, ldate(g), e["minute"], (bh, ba), prev))
        prev = (h, a)
        is_g = e["rc_scorer"] == "1" and not is_og(e)
        is_a = e["rc_assist_other"] == "1"
        if e["rc_self_assist"] == "1":
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"]))
        if not (is_g or is_a): continue
        gf, ga = (bh, ba) if side == "h" else (ba, bh)
        mi, dm = mins(e["minute"])
        tag = f"{gid}|{e['minute']}"
        if is_a:
            ATYPES[e["assist_type"]] += 1
            if tag in EXCL_A:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], EXCL_A[tag]))
            else:
                if is_og(e) or e["assist_type"] in ("Shot on goal",) or e["assist_type"].startswith(("Penalty", "Handball")):
                    sys.exit("도움 판정 누락 " + tag)
                if (e["side"] == "home") != (side == "h"): sys.exit("득점 편 이상 " + tag)
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            if (e["side"] == "home") != (side == "h"): sys.exit("득점 편 이상 " + tag)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + tag)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))

cnt = collections.Counter((r[1], r[0]) for r in raw_rows)
for gid, g in G.items():
    if cnt[(gid, "g")] != int(g["goals"]): sys.exit("골 수 불일치 " + gid)

# ---------------------------------------------------------------- 이름·기존 자료
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
        if r["선수"] == ME_KO: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

def tracked_data():
    try:
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True, check=True).stdout.split()
        return [os.path.join(ROOT, x) for x in out if x.endswith(".js")]
    except Exception:
        import glob
        return sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js")))

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in tracked_data():
    b = os.path.basename(fn)
    if b in ("hon.js", "rui.js"): continue
    OTHERS[b] = load_js(fn)
VIE = os.path.join(ROOT, "players", "vieri", "staged", "vie.js")
if not os.path.exists(VIE): VIE = "/home/user/soc/players/vieri/staged/vie.js"
STAGED = {"vie.js(staged)": load_js(VIE)} if os.path.exists(VIE) else {}
BYDATE = collections.defaultdict(list)
for b, (P, oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "atletico", "calcio",
        "sport", "cd", "ud", "sv", "as", "ss", "us", "milan", "inter", "ca", "fk", "sk", "ssc", "acf", "fbc", "bc", "cs", "gd", "sl", "vitoria"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o) or toks(x[1]) & toks(o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
def half_up(x): return int(x + 0.5)
SA18 = [1969, 1884, 1837, 1808, 1793, 1780, 1762, 1743, 1728, 1713, 1704, 1697, 1690, 1676, 1657, 1645, 1633, 1614]
PO18 = [1912, 1795, 1730, 1690, 1670, 1652, 1627, 1600, 1576, 1560, 1546, 1533, 1527, 1507, 1482, 1461, 1448, 1421]
PO16 = [1912, 1786, 1716, 1679, 1660, 1633, 1605, 1578, 1559, 1545, 1531, 1518, 1493, 1465, 1443, 1421]   # 2009-10 16팀 시즌 기존 값 전부
SB_MEAN = 1577.78     # 세리에B(문서 4절)
PO2_MEAN = 1367       # 포르투갈 2부(문서 4절, 피구·디 마리아 선례)

def season_vals(prefix, season):
    """기존 자료(팀×시즌 통합표)의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위")
    for vals in TABLE.values():
        for e, lv in vals:
            m = pat.match(lv)
            if m and "추정" not in lv: c[int(m.group(1))][e] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

def rank_model(lg, season, r, n):
    if lg == "PO1":
        m = season_vals("포르투갈 1부", season)
        if r in m: return m[r], f"포르투갈 1부 {season} {r}위"
        if n == 18: return PO18[r - 1], f"포르투갈 1부 {season} {r}위"
        if n == 16: return PO16[r - 1], f"포르투갈 1부 {season} {r}위"
        return None
    if lg == "PO2":
        return half_up(PO2_MEAN + SD2 * curve(r, n)), f"포르투갈 2부 {season} {r}위 (추정)"
    if lg == "IT1":
        m = season_vals("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        if n == 18: return SA18[r - 1], f"세리에A {season} {r}위"
        return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "IT2":
        m = season_vals("세리에B", season)
        if r in m: return m[r], f"세리에B {season} {r}위"
        return half_up(SB_MEAN + SD2 * curve(r, n)), f"세리에B {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANK_LG = ["PO1", "PO2", "IT1", "IT2"]
def rank_lookup(k, s):
    for lg in RANK_LG:
        t = RANKS.get((lg, s))
        if t and k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s, r, n)
            if res: return res
    return None

# 순위표·기존 자료에 없는 상대(직접 추정·외부 순위): (TM 상대 이름, 시즌) -> (Elo, lv) — judgments.md 6절
MAN = {
    ("Dynamo Kyiv", "1991-92"): (1600, "소련 1991 5위/16팀 (추정, 다른 선수 자료 디나모 키이우 2006-07 1600과 같음)"),
    ("Dinamo Moscow", "1992-93"): (1560, "러시아 1992 3위 (추정, 다른 선수 자료 디나모 모스크바 1996 4위 1550보다 조금 높게)"),
    ("CSKA Sofia", "1993-94"): (1480, "불가리아 1993-94 2위 (추정, 다른 선수 자료 CSKA 소피아 2005-06 2위 1480과 같음)"),
    ("Bayer 04 Leverkusen", "1993-94"): (1860, "분데스리가 1993-94 3위 (2000-01 순위값 사용)"),
    ("CF Gloria Bistrita (- 2015)", "1996-97"): (1400, "루마니아 1996-97 (추정, 1995-96 12위·컵 준우승, 다른 선수 자료 글로리아 비스트리차 2007-08 10위 1400과 같음)"),
    ("Hapoel Tel Aviv", "2001-02"): (1500, "이스라엘 2001-02 2위 (추정, 다른 선수 자료 하포엘 텔아비브 2010-11 2위 1500과 같음)"),
    ("FC Dinamo 1948", "2006-07"): (1520, "루마니아 2006-07 1위 (추정, 다른 선수 자료 루마니아 1위 FCSB 2012-13 1520과 같음)"),
    ("US Lecce", "1995-96"): (1417, "세리에C1 1995-96 (승격 팀, 순위 확인 못 함; 세리에C 평균 추정)"),
    ("Calcio Padova", "1998-99"): (1417, "세리에C1 1998-99 (순위 확인 못 함; 세리에C 평균 추정)"),
    ("Moreirense FC", "2007-08"): (1250, "포르투갈 3부 2007-08 조 8위 (추정, 다른 선수 자료 포르투갈 3부 1250과 같음)"),
}
# 순위표 순위를 공식 최종 순위로 고치거나 순위표에 없는 팀의 순위를 더함(judgments.md 6절, 출처 위키백과·zerozero·futebol365)
RANK_FIX = {
    ("CS Marítimo", "1991-92"): ("PO1", 7, 18),          # 파렌스와 35점 동률, 공식 순위 7위
    ("SC Farense", "1993-94"): ("PO1", 8, 18),          # 33점 3팀 동률, 공식 순위 8위(v1.157 순위 대조와 같음)
    ("CF União Madeira (-2021)", "1993-94"): ("PO1", 12, 18),   # 31점 3팀 동률(질 비센트 10·살게이루스 11·우니앙 12)
    ("Calcio Padova", "1994-95"): ("IT1", 14, 18),      # 제노아와 40점 동률, 잔류 플레이오프 승리(제노아 15위)
    ("US Palermo", "1995-96"): ("IT2", 7, 20),          # 제노아와 52점 동률, 공식 순위 7위
    ("US Lecce", "1998-99"): ("IT2", 4, 20),            # 레지나와 64점 동률, 공식 순위 4위
    ("CS Marítimo", "2006-07"): ("PO1", 11, 16),        # 나발과 32점 동률, 공식 순위 11위
    ("Ancona Calcio", "2002-03"): ("IT2", 4, 20),       # 세리에B 2002-03 4위(승격), 순위표 없음
    ("Amora FC", "1992-93"): ("PO2", 17, 18),           # 2부(세군다 지비상 드 온라) 1992-93 17위, 순위표 없음
}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1:
        print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    euro = cid in ("CL", "CLQ", "UEFA", "EPP", "EPL", "WEPO", "USC")
    s0 = eu(d)
    seasons = [s0, str(int(s0[:4])), str(int(s0[:4]) + 1)] if euro else [s0]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for s in seasons:
        if (o, s) in MAN:
            e, lv = MAN[(o, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for s in seasons:
        if (o, s) in RANK_FIX:
            lg, r, n = RANK_FIX[(o, s)]
            res = rank_model(lg, s, r, n)
            ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model-fix", res[0], res[1]); return res
    for s in seasons:
        res = rank_lookup(k, s)
        if res:
            ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

# ---------------------------------------------------------------- 기록 행
E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if mi > 90 and dm == 0 and (g["gameState"] != "regularly_terminated" or gid in ET_GAMES) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    for m in MISS: print("Elo 없음:", m)
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda x: x[0][1]):
        print(d, o, v)
    print("SEQ_DIFF", SEQ_DIFF)
    print("ATYPES", ATYPES)
    for j in judg: print(j)

# ---------------------------------------------------------------- 클럽·시즌 (7·8월 초 경기 없음: 전부 기본 8월 1일)
CLUBS = [("benrc", "1994-07-01", "벤피카", "1991~1994"), ("fiorc", "2001-07-01", "피오렌티나", "1994~2001"),
         ("acmrc", "2006-07-01", "AC 밀란", "2001~2006"), ("benrc", None, "벤피카", "2006~2008")]
TM_CLUB = {"294": "benrc", "430": "fiorc", "5": "acmrc"}
def stint_of(d):
    for i, (k, u, *_) in enumerate(CLUBS):
        if u is None or d < u: return i
for g in GAMES:
    if CLUBS[stint_of(ldate(g))][0] != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((i, [0, 0, 0, 0]) for i in range(len(CLUBS)))
for m in M: ST[stint_of(m[0])][0] += 1; ST[stint_of(m[0])][3] += m[3]
for r in E: ST[stint_of(r[9])][1 if r[0] == "g" else 2] += 1
STK = collections.OrderedDict()
for i, v in ST.items():
    STK.setdefault(CLUBS[i][0], [0, 0, 0, 0])
    for j in range(4): STK[CLUBS[i][0]][j] += v[j]
def season_of(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
SEASON_TM = collections.Counter((season_of(ldate(g)), g["season_tm"]) for g in GAMES)
if "--debug" in sys.argv:
    for i, v in ST.items(): print(CLUBS[i], v)
    print(sorted(SEASON_TM.items()))

# ---------------------------------------------------------------- 동료 자료 대조(다른 파일은 고치지 않음)
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    return diffs
MATES = {"she.js": "Andriy Shevchenko", "inz.js": "Filippo Inzaghi", "see.js": "Clarence Seedorf", "riv.js": "Rivaldo",
         "kak.js": "Kaká", "dim.js": "Ángel Di María", "vie.js(staged)": "Christian Vieri"}
ALLF = dict(OTHERS); ALLF.update(STAGED)
TMEV = [(e, ldate(G[e["gameId"]]), mins(e["minute"])[0]) for gid in EVS for e in EVS[gid] if gid in G]
for fn, nm in MATES.items():
    if fn not in ALLF: continue
    P, ent, om = ALLF[fn]
    for r in E:   # 후이 코스타 도움 -> 동료 골
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append((f"후이 코스타 도움→{nm} 골", fn, r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for e, d, mi in TMEV:   # 동료 도움 -> 후이 코스타 골 (리포트 도움 선수 기준)
        if e["rc_scorer"] == "1" and norm(e["assist_player"]) == norm(nm):
            mine = [r for r in E if r[0] == "g" and r[9] == d and r[4] == mi]
            hit = sorted([x for x in ent if x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 3], key=lambda x: abs(x[4] - mi))
            CROSS.append((f"{nm} 도움→후이 코스타 골", fn, d, mi, "동료 파일에 없음" if not hit else (cmp_rows(mine[0], hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and "Rui Costa" in str(x[13]):
            if not any(r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3 for r in E):
                CROSS.append(("동료 파일의 후이 코스타 골 도움이 이 자료에 없음", fn, x[9], x[4]))
    for e, d, mi in TMEV:   # TM 리포트상 후이 코스타 도움인데 이 자료에서 뺀 동료 골
        if e["rc_assist_other"] == "1" and norm(e["scorer"]) == norm(nm) and not any(r[0] == "a" and r[9] == d and r[4] == mi for r in E):
            has = any(x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 3 for x in ent)
            CROSS.append(("TM 도움을 뺀 동료 골", fn, d, e["minute"], e["assist_type"], "동료 골 행 있음" if has else "동료 골 행 없음"))
    for x in ent:   # 같은 경기 대회·Elo·lv·합산
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                CROSS.append(("같은 경기", fn, r[9], r[1], dd or "같음"))
                break
    mm_ = {m[0]: m for m in M}
    for m in om:    # 출전 행 대회
        if m[0] in mm_ and key(mm_[m[0]][1]) == key(m[1]):
            CROSS.append(("출전 행", fn, m[0], m[1], "같음" if mm_[m[0]][2] == m[2] else f"대회 {mm_[m[0]][2]}/{m[2]}"))
# 이 자료의 모든 기록과 같은 날·같은 상대인 다른 선수 기록(동료 외 포함): Elo·lv·대회
for r in E:
    for b, x in BYDATE.get(r[9], []):
        if key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1]):
            dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회"))]
            if dd: CROSS.append(("같은 날 다른 선수 기록과 다름", b, r[9], r[1], dd))
if "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[1], c[-1] == "같음") for c in CROSS))
