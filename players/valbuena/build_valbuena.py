#!/usr/bin/env python3
"""마티외 발부에나 (Transfermarkt 40687, FotMob 40060): raw/ -> valbuena.json + src/data/vab.js (판정 근거는 judgments.md)

  python3 players/valbuena/build_valbuena.py            # 파일 쓰기
  python3 players/valbuena/build_valbuena.py --debug    # Elo 출처 로그
  python3 players/valbuena/build_valbuena.py --stat     # 요약·동료 대조·FotMob 대조

입력: raw/tm_games.csv(출전·분·현지 날짜, 성인 클럽 802경기; 올림피아코스 B는 raw/youth_reserve_games.csv라 읽지 않음),
      raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전), raw/fotmob_events.csv·fotmob_playerMatches.csv(2014-08 이후 도움 대조),
      raw/ranks.txt(Transfermarkt 순위표), elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "vab.js")
OUT_JSON = os.path.join(HERE, "valbuena.json")
ME = "40687"
ME_KO = "마티외 발부에나"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

def ldate(g): return g["date_local"]
def opp(g): return re.sub(r"\s*\(\s*\d{4}\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"     # 이 전 도움은 TM 단일 출처 허용(클로제·인시녜 선례), 이후는 TM+FotMob 일치 또는 다른 출처 2곳

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR3", "FR1", "RU1", "TR1", "GR1", "POGR", "S1PO", "ZYP1", "ZYPA", "MAL2"}   # 그리스 플레이오프·플레이아웃, 키프로스 2단계도 리그(벨기에 플레이오프 선례)
CUPS = {"FRC", "FRL", "TRP", "GRP", "CPO1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "FRCH": return "df"                      # 트로페 데 샹피옹 = 슈퍼컵 = 국내컵 결승
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "UI": return "elq"                       # 인터토토컵 = 유로파 예선(램파드·비야·델 피에로·지단 선례)
    if cid in ("CLQ",): return "clq"
    if cid in ("ELQ",): return "elq"                   # 유로파 예선 2·3라운드·플레이오프
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "UEFA":                                  # 2007-08·2008-09 UEFA컵 3라운드(32강)·16강·8강 (벤 아르파 선례)
        return "elk"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                   # 32강('Second Round'·'intermediate stage')·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "UI"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid == "TRP": return (1, 1) if d < "2021-07-01" else (0, 1)     # 튀르키예컵: 2020-21까지 원정 다득점·연장(문서 3절, v1.152)
    if cid == "GRP": return (1, 1)     # 그리스컵 2019-20~2022-23: 원정 다득점(연장 원정골 포함)·연장 — judgments.md 5절 출처
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G and G[oid]["gameState"] == "regularly_terminated":
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    sc = re.sub(r"[^0-9:]", "", m["other_leg_score"])
    oh, oa = map(int, sc.split(":"))                   # 이 경기 홈:원정 방향
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

def assist_reason(e):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty") or t.startswith("Handball"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

def fm_rows(gid): return [f for f in FME.get(gid, []) if f["pen_shootout_event"] != "True"]
def fm_has_vb_assist(gid, after_ha):
    return any(f["vb_assist"] == "1" and f["newScore_home_away"] == after_ha for f in fm_rows(gid))

# 2014-08-01 이후 TM 도움 중 FotMob 경기 이벤트에 발부에나 도움이 없는 것: 다른 출처 2곳(경기 기사·구단 기사 등)으로 확인되면 넣음(judgments.md 4절)
#   (gameId, TM 분) -> (판정, 근거 요약)
POST_GAP = {}
def post(gid, mn, ok, why): POST_GAP[(gid, mn)] = (ok, why)
post("2483454", "33", False, "FotMob 도움 없음, 검색에서 발부에나 패스를 적은 곳은 출처가 불분명한 1곳뿐")
post("2492413", "52", False, "FotMob 도움 없음, worldfootball.net만 발부에나 도움 표기(UEFA·DFB·ESPN은 도움 이름 없음)")
post("2514863", "37", False, "FotMob은 사바(Samba) 도움으로 적음, 다른 출처 확인 못 함")
post("2814012", "4", True, "FotMob 도움 없음, Maxifoot·Lyon Mag 기사가 발부에나의 짧은 프리킥 → 라카제트 골로 서술")
post("2883860", "78", True, "FotMob 도움 없음, TRT Haber·Gzt(Yeni Şafak) 기사가 발부에나 코너킥 → 슈크르텔 헤더(클리시 무릎에 맞고 들어감)로 서술")
post("3244663", "11", False, "FotMob은 47분 골만 발부에나 도움, Agonasport·El Telégrafo도 후반 골만 발부에나 도움으로 서술")
post("3209362", "12", False, "FotMob 경기 이벤트·선수 경기 목록 모두 도움 0, 다른 출처 확인 못 함")
post("3209362", "71", False, "FotMob 경기 이벤트·선수 경기 목록 모두 도움 0, 다른 출처 확인 못 함")
post("3507087", "90+3", False, "FotMob 도움 없음, iefimerida 1곳만 '발부에나 프리킥 뒤'로 서술")
post("4039709", "25", False, "FotMob 도움 없음, 다른 출처 확인 못 함")
for _g, _m in (("4156781", "4"), ("4192783", "67"), ("4156665", "36"), ("4291712", "3"), ("4291712", "45")):
    post(_g, _m, False, "키프로스 경기: FotMob이 도움을 적지 않음(아폴론 시즌 전체 도움 0), 경기 기사에서 도움 확인 못 함")
# FotMob에만 있는 도움(TM 없음): 다른 출처 2곳이 확인한 것만 더함 — 확인된 것 없음(judgments.md 4절)
ADD_A = []

raw_rows, judg, unconf = [], [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if ldate(g) >= GAP and not fm_has_vb_assist(gid, e["score_home_away_after"]):
                ok, src = POST_GAP.get((gid, e["minute"]), (None, "판정 없음"))
                if ok is None: sys.exit(f"2014-08 이후 TM 단독 도움 판정 필요: {gid} {ldate(g)} {opp(g)} {e['minute']} {e['scorer']}")
                judg.append(("2014-08 이후 TM 단독 도움 " + ("넣음" if ok else "뺌(확인 못 함)"), ldate(g), opp(g), e["minute"], e["scorer"], src))
                if not ok:
                    unconf.append((ldate(g), opp(g), e["minute"], e["scorer"], src)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

# FotMob 경기 이벤트에만 있는 발부에나 도움(2014-08 이후) — 기록하고 넣지 않음(ADD_A 확인분만)
FM_ONLY = []
for gid, fl in FME.items():
    if gid not in G or ldate(G[gid]) < GAP: continue
    tmafter = {e["score_home_away_after"] for e in EVS.get(gid, []) if e["assist_id"] == ME}
    for f in fl:
        if f["vb_assist"] == "1" and f["pen_shootout_event"] != "True" and f["newScore_home_away"] not in tmafter:
            FM_ONLY.append((gid, ldate(G[gid]), opp(G[gid]), f["time"], f["newScore_home_away"], f["scorer"]))

# 리포트 골 = API 경기별 골 수 점검
cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, re.sub(r"[^0-9:]", "", MI[gid]["final"]).split(":")) if MI[gid]["final"] else (h, a)
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))

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
MANUAL_ALIAS = {"inter milan": "inter", "olympique lyon": "olympique lyonnais", "dinamo moscow": "dynamo moscow",
                "fk krasnodar": "fc krasnodar"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "vab.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "foot", "olympique",
        "cd", "ud", "sv", "as", "ss", "moscow", "moskau", "sk", "fk", "pfk", "nfc", "piraeus", "athens", "thessaloniki", "limassol", "nicosia",
        "famagusta", "spor", "jk", "1964", "hsc", "sco", "lille", "losc", "rc", "aj", "ogc", "fco", "ea", "es", "us", "sm"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
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

def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e[12] or "")
        if m: c[int(m.group(1))][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
def mid(tab, r):
    if r in tab: return tab[r], False
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up(tab[a] + (tab[b] - tab[a]) * (r - a) / (b - a)), True
def edge(tab, r, n, sd):
    k = min(tab, key=lambda x: abs(x - r))
    return half_up(tab[k] + sd * (curve(r, n) - curve(k, n)))
LL_SD = 100.16
INTERP_USED = set()

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 튀르키예 1부: 2017-18은 2016-17 리그 수준(평균 1479, 에투 자료 선례), 2018-19는 팔카오·메르턴스 자료의 회귀식
TR_COEF = {2017: 6.8, 2018: 5.5, 2019: 5.0}     # 2017-18 6.8: 위키백과(Turkish football clubs in European competitions) 시즌별 계수
def tr_mean(start):
    c = sum(TR_COEF[y] for y in (start - 1, start, start + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)

MODELS = {}       # 아래 rank_model에서 쓰는 리그별 함수 — 그리스·키프로스·몰타는 judgments.md 6절

def reg_mean(coefs): return 1473 + 23.33 * (sum(coefs) / len(coefs) - 7.3333)
# 그리스 1부: 튀르키예·우크라이나와 같은 회귀(앞뒤 3시즌 UEFA 국가 계수 평균) + 그리스 보정 GR_K.
#   계수(시작 연도): UAF 계수표·football-coefficient.eu. 2024-25는 2025-26이 끝나지 않아 2022-23~2024-25 세 시즌 평균(튀르키예 2025-26 선례)
GR_COEF = {2018: 5.1, 2019: 4.9, 2020: 5.1, 2021: 8.0, 2022: 2.125, 2023: 11.4, 2024: 12.688}
def gr_reg(start):
    ys = (start - 1, start, start + 1) if start + 1 in GR_COEF else (start - 2, start - 1, start)
    return reg_mean([GR_COEF[y] for y in ys])
# 보정: 통합표의 같은 시기 그리스 팀 값(올림피아코스 2019-20 1위 1680·2020-21 1위 1690, PAOK 2021-22 2위 1590)과 회귀 값 차이의 평균
GR_ANCH = [(2019, 1, 1680), (2020, 1, 1690), (2021, 2, 1590)]
GR_K = sum(v - (gr_reg(y) + 119 * curve(r, 14)) for y, r, v in GR_ANCH) / len(GR_ANCH)
def gr_mean(season): return gr_reg(int(season[:4])) + GR_K
def m_gr1(season, r, n): return half_up(gr_mean(season) + 119 * curve(r, n)), f"그리스 슈퍼리그 {season} {r}위 (추정, 리그 수준 추정)"
def m_grs2(season, r, n): return half_up(gr_mean(season) - 162 + SD2 * curve(r, n)), f"그리스 2부(슈퍼리그 2) {season} {r}위 (추정, 리그 수준 추정)"
MODELS["GR1"] = m_gr1; MODELS["GRS2"] = m_grs2
# 키프로스 1부 2023-24: 같은 회귀(2022-23 5.1·2023-24 3.75·2024-25 2.75), 흩어짐은 작은 리그라 노르웨이 선례 63
CY_MEAN = {"2023-24": reg_mean([5.1, 3.75, 2.75])}
def m_cy1(season, r, n): return half_up(CY_MEAN[season] + 63 * curve(r, n)), f"키프로스 1부 {season} {r}위 (추정, 리그 수준 추정)"
def m_cy2(season, r, n): return half_up(CY_MEAN[season] - 162 + SD2 * curve(r, n)), f"키프로스 2부 {season} {r}위 (추정, 리그 수준 추정)"
MODELS["ZYP1"] = m_cy1; MODELS["1CY2"] = m_cy2
# 몰타 2부(챌린지 리그) 2026-27: 1부 평균 약 1340(같은 회귀, 계수 약 1.5) − 162 = 1180, 순위 곡선 없이 평평하게(보수적 추정)
def m_mal2(season, r, n): return 1180, f"몰타 2부(챌린지 리그) {season} {r}위(2026.11.12 현재) (추정, 리그 수준 추정)"
MODELS["MAL2"] = m_mal2
def rank_model(lg, season, r, n):
    if lg == "FR1":
        m = ents_map("리그1", season)
        v, it = mid(m, r)
        if v is None:
            v = edge(m, r, n, LL_SD); INTERP_USED.add((season, r, v, "끝"))
            return v, f"리그1 {season} {r}위 (추정, 이웃 순위값에 순위 곡선 차이)"
        if it: INTERP_USED.add((season, r, v))
        return v, f"리그1 {season} {r}위"
    if lg == "FR2":
        m = ents_map("리그2", season); v, it = mid(m, r)
        if v is None: return half_up(1540 + SD2 * curve(r, n)), f"리그2 {season} {r}위 (추정, 프랑스 2부 평균 1540 모형)"
        return v, f"리그2 {season} {r}위"
    if lg == "FR3":       # 리베리 자료의 나시오날 순위값과 같은 식(1311 + 2부 흩어짐 × 순위 곡선)
        return half_up(1311 + SD2 * curve(r, n)), f"프랑스 3부(나시오날) {season} {r}위 (추정)"
    if lg == "RU1":       # 에투 자료의 러시아 모형(평균 1520·흩어짐 55)
        return half_up(1520 + 55 * curve(r, n)), f"러시아 프리미어리그 {season} {r}위 (리그 수준 추정)"
    if lg == "TR1":
        if season == "2017-18":
            return half_up(1479 + 119 * curve(r, n)), f"쉬페르리그 {season} {r}위 (추정, 2016-17 리그 수준 사용)"
        if season == "2018-19":
            return half_up(tr_mean(2018) + 119 * curve(r, n)), f"쉬페르리그 {season} {r}위"
    if lg in MODELS:
        f = MODELS[lg]
        res = f(season, r, n)
        if res: return res
    return None

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)

CLUB_LG = {"2968": ["FR3"], "244": ["FR1", "FR2", "FR3"], "1041": ["FR1", "FR2", "FR3"], "121": ["RU1"], "36": ["TR1", "TR2"],
           "683": ["GR1", "GRS2"], "429": ["ZYP1", "1CY2"], "3062": ["GR1", "GRS2"], "37653": ["MAL2"]}
EURO = {"CL", "CLQ", "EL", "ELQ", "UEFA", "UI"}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, g):
    cid = g["competitionId"]
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o); s = eu(d)
    seasons = [s]
    if (k, s) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    if (k, s) in MAN:
        e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    if cid not in EURO:
        for lg in CLUB_LG[g["club_id"]]:
            t = RANKS.get((lg, s), {})
            if k in t:
                r, n, _ = t[k]
                res = rank_model(lg, s, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
                MISS.append((o, d, cid, s, f"{lg} {r}/{n} 모형 없음")); return 0, "?"
    MISS.append((o, d, cid, s, "")); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, g)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)
