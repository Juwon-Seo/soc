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
# 2018 튀르키예컵 준결승 2차전 베식타시전: 2018.4.19 57분 0-0에서 중단, 5.3 재개 경기에 베식타시가 나오지 않아 페네르바체 3-0 몰수승.
#   Transfermarkt는 5.3 날짜로 적었으나 실제로 뛴 날은 4.19(NTV·Diken 기사) → 4.19로 고침(출전 11분은 그대로)
for g in GAMES:
    if g["gameId"] == "3000411": g["date_local"] = "2018-04-19"
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

# 그리스 1부 순위: Transfermarkt 표는 26라운드 정규 시즌 순서(2022-23은 정규 1위 파나티나이코스·최종 우승 AEK)라
#   확인된 최종 순위만 고침(AEK 2022-23 우승: GreekReporter 2023.5.15, 파나티나이코스 2024-25 2위: 위키백과 시즌 문서 사본), 나머지는 정규 시즌 순서(벨기에 선례)
for (lg_, s_, o_, r_) in (("GR1", "2022-23", "AEK Athens", 1), ("GR1", "2024-25", "Panathinaikos", 2)):
    t_ = RANKS[(lg_, s_)]; old_r = t_[key(o_)][0]
    for k_, v_ in list(t_.items()):
        if r_ <= v_[0] < old_r: t_[k_] = (v_[0] + 1, v_[1], v_[2])
    t_[key(o_)] = (r_, t_[key(o_)][1], o_)

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
    if "2020-07-01" <= d <= "2020-09-12": return "2019-20"     # 코로나로 늦게 끝난 2019-20(그리스 플레이오프·유로파 16강·그리스컵 결승)
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 튀르키예 1부: 2017-18은 2016-17 리그 수준(평균 1479, 에투 자료 선례), 2018-19는 팔카오·메르턴스 자료의 회귀식
TR_COEF = {2017: 6.8, 2018: 5.5, 2019: 5.0, 2020: 3.1}     # 2017-18 6.8: 위키백과(Turkish football clubs in European competitions) 시즌별 계수
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
def m_gr1(season, r, n): return half_up(gr_mean(season) + 119 * curve(r, n)), f"그리스 슈퍼리그 {season} {r}위 (리그 수준 추정)"
def m_grs2(season, r, n): return half_up(gr_mean(season) - 162 + SD2 * curve(r, n)), f"그리스 2부(슈퍼리그 2) {season} {r}위 (리그 수준 추정)"
MODELS["GR1"] = m_gr1; MODELS["GRS2"] = m_grs2
# 키프로스 1부 2023-24: 같은 회귀(2022-23 5.1·2023-24 3.75·2024-25 2.75), 흩어짐은 작은 리그라 노르웨이 선례 63
CY_MEAN = {"2023-24": reg_mean([5.1, 3.75, 2.75])}
def m_cy1(season, r, n): return half_up(CY_MEAN[season] + 63 * curve(r, n)), f"키프로스 1부 {season} {r}위 (리그 수준 추정)"
def m_cy2(season, r, n): return half_up(CY_MEAN[season] - 162 + SD2 * curve(r, n)), f"키프로스 2부 {season} {r}위 (리그 수준 추정)"
MODELS["ZYP1"] = m_cy1; MODELS["1CY2"] = m_cy2
# 몰타 2부(챌린지 리그) 2026-27: 1부 평균 약 1340(같은 회귀, 계수 약 1.5) − 162 = 1180, 순위 곡선 없이 평평하게(보수적 추정)
def m_mal2(season, r, n): return 1180, f"몰타 2부(챌린지 리그) {season} {r}위(2026.11.12 현재) (리그 수준 추정)"
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
    if lg == "RU1" and season == "2019-20":   # 크바라츠헬리아 자료의 2019-20 순위값(11위 1399·12위 1392·13위 1380·16위 1344)에 맞는 평균 1430.3·흩어짐 63
        return half_up(1430.3 + 63 * curve(r, n)), f"러시아 프리미어리그 {season} {r}위 (리그 수준 추정)"
    if lg == "RU1":       # 에투 자료의 러시아 모형(평균 1520·흩어짐 55)
        return half_up(1520 + 55 * curve(r, n)), f"러시아 프리미어리그 {season} {r}위 (리그 수준 추정)"
    if lg == "TR1":
        m = ents_map("쉬페르리그", season)
        if r in m: return m[r], f"쉬페르리그 {season} {r}위"
        if season == "2017-18":
            return half_up(1479 + 119 * curve(r, n)), f"쉬페르리그 {season} {r}위 (추정, 2016-17 리그 수준 사용)"
        if season in ("2012-13", "2018-19", "2019-20"):
            mean = 1473 if season == "2012-13" else tr_mean(int(season[:4]))
            return half_up(mean + 119 * curve(r, n)), f"쉬페르리그 {season} {r}위"
    if lg == "TR2":       # 판페르시 자료 선례: 같은 시즌 쉬페르리그 평균 − 162, 2부 흩어짐
        mean = 1479 if season == "2017-18" else tr_mean(int(season[:4]))
        return half_up(mean - 162 + SD2 * curve(r, n)), f"튀르키예 2부 {season} {r}위 (리그 수준 추정)"
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
    for s2 in ([s, d[:4]] if cid in EURO else [s]):     # 유럽 대회 상대는 달력 연도 리그(러시아 2010 등) 값도 찾음
        if (k, s2) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s2)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s2); return e, lv
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

# 순위표 리그가 클럽 리그와 다른 상대(유럽 대회·국내 컵): 순위표 + 리그 모형을 직접 지정
XLG = {("Eskisehirspor", "2012-13"): "TR1", ("Fenerbahce", "2012-13"): "TR1", ("Basaksehir FK", "2019-20"): "TR1",
       ("FC Krasnodar", "2019-20"): "RU1", ("Adana Demirspor", "2017-18"): "TR2"}
for (o, s_), lg in XLG.items():
    r, n, _ = RANKS[(lg, s_)][key(o)]
    e, lv = rank_model(lg, s_, r, n); man(o, s_, e, lv)
r_, n_, _ = RANKS[("NL1", "2008-09")][key("Ajax Amsterdam")]
man("Ajax Amsterdam", "2008-09", 1677, f"에레디비시 2008-09 {r_}위")
man("PSV Eindhoven", "2020-21", 1735, "에레디비시 2020-21 2위")
man("ESA Brive", "2005-06", 1220, "프랑스 4부(CFA) 2005-06 (추정, 다른 선수 자료 프랑스 4부 1220과 같음)")
man("Trélissac FC", "2009-10", 1150, "프랑스 5부(CFA2) 2009-10 A조 (추정, 다른 선수 자료의 프랑스 5부 팀 값 1150과 같음)")   # 벤 아르파 판정과 같은 문구
man("AEL Limassol", "2012-13", 1450, "키프로스 1부 2012-13 5위 (추정, 다른 선수 자료 AEL 2014-15 1450과 같음)")
man("KAA Gent", "2015-16", 1640, "벨기에 1부 2015-16 2위 (추정, 다른 선수 자료 안데를레흐트 2015-16 1640과 같음)")
man("SK Sturm Graz", "2017-18", half_up(1471 + 119 * curve(2, 10)), "오스트리아 분데스리가 2017-18 2위 (추정, 다른 선수 자료의 2018-19 리그 평균 1471 사용)")
man("RSC Anderlecht", "2018-19", 1640, "벨기에 1부 2018-19 4위 (추정, 다른 선수 자료 안데를레흐트 2014-15·2015-16 1640과 같음)")
man("FC Viktoria Plzen", "2019-20", 1560, "체코 1부 2019-20 2위 (추정, 다른 선수 자료 플젠 2018-19 2위 1560과 같음)")
man("Omonia Nicosia", "2020-21", 1520, "키프로스 1부 2020-21 1위 (추정, 다른 선수 자료 아포엘 2017-18 1위 1520과 같음)")
man("Neftchi PFK", "2021-22", 1450, "아제르바이잔 1부 2021-22 2위 (추정, 다른 선수 자료 카라바흐 2010-11 3위 1450과 같음)")
man("Slovan Bratislava", "2021-22", 1450, "슬로바키아 1부 2021-22 1위 (추정, 다른 선수 자료 슬로반 상위권 1450과 같음)")
man("Slovan Bratislava", "2022-23", 1450, "슬로바키아 1부 2022-23 상위권 (추정, 다른 선수 자료 슬로반 상위권 1450과 같음)")
e_, lv_ = m_grs2("2021-22", 1, 17)
man("Levadiakos", "2021-22", e_, "그리스 2부(슈퍼리그 2) 2021-22 남부 조 1위 (리그 수준 추정)")

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, g)
    et = 1 if (mi > 90 and (not dm or str(dm).startswith(("105+", "120+"))) and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)

if "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["vb_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "penalty" in (f["goalDescriptionKey"] or "").lower() or "pen" in (f["suffix"] or "").lower()
        a = mins(t["minute"])[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
        if tp != fp or abs(a - b) > 1 or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["score_home_away_after"], t["goal_desc"], f["time"], f["overloadTime"], f["newScore_home_away"], f["goalDescriptionKey"]))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None): d.append("단판/합산")
    if a[10] != b[10]: d.append("연장")
    return d
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:     # 다른 선수 도움 → 발부에나 골
        if x[0] == "a" and "Valbuena" in str(x[13]):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(발부에나 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:      # 발부에나 도움 → 다른 선수 골
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1]))]
            if hit: CROSS.append(("발부에나 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
# 동료 이름(파예·라카제트)의 골에 TM 발부에나 도움이 있는데 그 선수 파일에 골 행이 없는 경우
MATE = {"pay.js": "Dimitri Payet", "lac.js": "Alexandre Lacazette"}
for b, nm in MATE.items():
    oe, om = OTHERS[b]
    for gid, evs in EVS.items():
        if gid not in G: continue
        for e in evs:
            if e["scorer"] == nm and e["assist_id"] == ME and not is_og(e):
                d = ldate(G[gid]); mi = mins(e["minute"])[0]
                if not [x for x in oe if x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 2]:
                    CROSS.append((f"{nm} 골(발부에나 도움)이 {b}에 없음", d, e["minute"], opp(G[gid])))
            if e["scorer_id"] == ME and e["assist_player"] == nm:
                d = ldate(G[gid]); mi = mins(e["minute"])[0]
                if not [x for x in oe if x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2]:
                    CROSS.append((f"{nm} 도움(발부에나 골)이 {b}에 없음", d, e["minute"], opp(G[gid])))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("libvb", "2006-07-01", "리부른", "2004~2006"), ("omvb", "2014-08-02", "마르세유", "2006~2014"),
         ("dynvb", "2015-08-11", "디나모 모스크바", "2014~2015"), ("lyovb", "2017-07-01", "리옹", "2015~2017"),
         ("fenvb", "2019-07-01", "페네르바체", "2017~2019"), ("olyvb", "2023-07-23", "올림피아코스", "2019~2023"),
         ("apovb", "2024-08-05", "아폴론 리마솔", "2023~2024"), ("kalvb", "2025-08-11", "아테네 칼리테아", "2024~2025"),
         ("slcvb", None, "산타 루치아", "2026~")]
TM_CLUB = {"2968": "libvb", "244": "omvb", "121": "dynvb", "1041": "lyovb", "36": "fenvb", "683": "olyvb", "429": "apovb", "3062": "kalvb", "37653": "slcvb"}
def club_of(d):
    for k, u, n, y in CLUBS:
        if u is None or d < u: return k
CN = {k: n for k, u, n, y in CLUBS}; CY = {k: y for k, u, n, y in CLUBS}
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EX = [j for j in judg if j[0] == "도움 제외"]
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
def season_of(d, club):
    y = int(d[:4])
    if club == "olyvb" and "2020-07-01" <= d <= "2020-09-12": return "2019-20"
    if club in ("omvb", "dynvb", "lyovb", "fenvb", "olyvb"): s = y if d[5:] >= "07-10" else y - 1
    else: s = y if int(d[5:7]) >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    print("FM 골 대조", FM_CMP)
    print("FM만 도움", FM_ONLY)
    for c in CROSS: print(c)
    for j in judg: print(j)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("보간", sorted(INTERP_USED))
    print("score mismatch", SCORE_MISMATCH)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
SRC = ELO_SRC
first, last = M[0], M[-1]
EXC = {"상대 자책골 유도": 0, "슈팅 리바운드('Shot on goal')": 0, "PK 유도": 0}
for j in EX: EXC[j[5]] += 1
def ex_list(why): return ", ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]}" for j in EX if j[5] == why)
UNC = "; ".join(f"{d_(u[0])} {u[1]}전 {u[2]}분 {u[3]}" for u in unconf)
NOTE_LINES = [
    f"마티외 발부에나(리부른·마르세유·디나모 모스크바·리옹·페네르바체·올림피아코스·아폴론 리마솔·아테네 칼리테아·산타 루치아)의 클럽 공식 경기 {NG}경기({d_(first[0])} US 루아전 ~ {d_(last[0])} 타르시엔 레인보스전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·프랑스 대표팀·올림피아코스 B(2군, 그리스 2부 11경기 3골) 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CN[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있거나 리그 밖 대회인 모든 경기; 리포트 골·도움 수가 선수 경기 성적과 경기마다 같음). 2010-11부터는 FotMob 경기 기록과 대조함(골 수·골 뒤 스코어·PK 모두 같고, 분만 다른 골 6개 — 2015.3.8 우파전 20분(FotMob 18분), 2017.9.17 알라니아스포르전 45분(45+2분), 2019.4.27 트라브존스포르전 90+6분(90분), 2021.1.3 AEK전 90+4분(90분), 2023.12.8 오텔로스전 48분(54분), 2024.1.6 AEL전 48분(51분) — 은 Transfermarkt 분을 씀)",
    "리부른(프랑스 3부 나시오날 2004~2006): Transfermarkt에는 58경기 11골 0도움(리그 55경기·쿠프 드 프랑스 3경기)만 있음. 프랑스어 위키백과 표는 60경기 14골 8도움(쿠프 드 프랑스 경기·골이 더 많음)이나 경기별 날짜·출전·골 시각 자료가 없어 넣지 않음. 리부른 경기 리포트는 골 경기와 컵 경기만 있고, 2005.11.19 쿠프 드 프랑스 브리브전(1-2 패) 리포트에는 발부에나 28분 골만 있어 골 전 스코어는 하프타임 0-1 기준 0-0으로 씀",
    "출전 분: Transfermarkt 그대로(퇴장·연장 반영). 영어 위키백과와 비교하면 마르세유 2006-07 리그 15경기(Transfermarkt 14), 아폴론·칼리테아 컵 각 2경기(Transfermarkt 3)만 다름 → Transfermarkt를 씀. 2018 튀르키예컵 준결승 2차전 베식타시전은 2018.4.19 57분 0-0에서 관중 소요로 중단되고 5.3 재개 경기에 베식타시가 나오지 않아 페네르바체 3-0 몰수승이 된 경기로, Transfermarkt는 5.3 날짜·출전 11분으로 적었으나 실제로 뛴 날짜인 4.19로 적음(출전 11분, 골 없음)",
    f"도움: 2014년 8월 이전(리부른·마르세유)은 Transfermarkt 경기 리포트 단일 출처(클로제·인시녜 선례). Transfermarkt 도움 165개에서 상대 자책골에 준 도움 {EXC['상대 자책골 유도']}개({ex_list('상대 자책골 유도')}), 슈팅 리바운드('Shot on goal') {EXC[chr(39).join(['슈팅 리바운드(', 'Shot on goal', ')'])]}개({ex_list(chr(39).join(['슈팅 리바운드(', 'Shot on goal', ')']))}), PK 유도 {EXC['PK 유도']}개({ex_list('PK 유도')})를 뺌. 본인이 얻어 본인이 넣은 PK 골에 본인을 도움으로 적은 2개(2019.9.18 토트넘전 54분, 2021.1.3 AEK전 90+4분)는 도움이 아님. 도움 유형 칸이 빈 {UNTYPED}개는 일반 도움으로 셈",
    f"2014년 8월 이후 도움은 Transfermarkt와 FotMob 경기 기록이 함께 적은 것만 넣고, 한쪽에만 있는 것은 경기 기사 등 다른 출처 2곳이 확인한 것만 넣음. 확인되어 넣은 것: 2017.1.8 쿠프 드 프랑스 몽펠리에전 4분 라카제트 골(발부에나의 짧은 프리킥, Maxifoot·Lyon Mag), 2017.9.9 바샥셰히르전 78분 슈크르텔 헤더(발부에나 코너킥, TRT Haber·Gzt). 확인하지 못해 뺀 Transfermarkt 도움 {len(unconf)}개: {UNC}. 키프로스(아폴론) 경기는 FotMob이 도움을 하나도 적지 않아 Transfermarkt 도움 5개가 모두 빠짐. FotMob에만 있는 2021.8.26 슬로반 브라티슬라바전 54분 오니에쿠루 골 도움(Sporting Life는 부할라키스 도움으로 적음)과 FotMob 선수 경기 목록에만 있는 2021.4.21 아스테라스전 도움(기사로는 발부에나 코너킥 뒤 다른 선수 헤더 패스)은 넣지 않음. 프랑스어 위키백과·FotMob 경력 합계의 클럽별 도움 수는 쓰지 않음",
    f"골: 자책골 없음. PK 골 {NPK}개는 Transfermarkt 골 유형 'Penalty'(FotMob과 같음)",
    "날짜: Transfermarkt 경기 날짜(현지)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(파예·라카제트 등), 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 순위(Transfermarkt 순위표)를 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['기존 팀×시즌 값']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "리그 모형: 리그1은 기존 선수 자료의 순위값(빈 순위는 앞뒤 값의 가운데, 2010-11 1위 릴은 가장 가까운 순위값에 순위 곡선 차이를 더한 추정), 프랑스 3부(나시오날)는 리베리 자료와 같은 1311 + 2부 흩어짐 × 순위 곡선(추정), 러시아는 에투 자료의 평균 1520·흩어짐 55(2019-20은 크바라츠헬리아 자료 순위값에 맞춘 평균 1430·흩어짐 63), 튀르키예 2017-18은 2016-17 리그 수준(에투 자료), 2018-19·2019-20은 국가 계수 회귀(팔카오 자료와 같은 식, 2017-18 계수 6.8), 튀르키예 2부는 1부 평균 − 162(판페르시 선례)",
    f"그리스 슈퍼리그(모두 '리그 수준 추정'): 기존 모형이 없어 튀르키예·우크라이나와 같은 국가 계수 회귀(리그 평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333), 흩어짐 119, 14팀 순위 곡선)에 그리스 보정 {GR_K:+.0f}점을 더함. 보정값은 통합표에 이미 있던 같은 시기 그리스 팀 값 3개(올림피아코스 2019-20 1위 1680·2020-21 1위 1690, PAOK 2021-22 2위 1590)와 회귀 값의 평균 차. 국가 계수(UAF·football-coefficient.eu): 2018-19 5.1, 2019-20 4.9, 2020-21 5.1, 2021-22 8.0, 2022-23 2.125, 2023-24 11.4, 2024-25 12.688(2024-25는 2025-26이 끝나지 않아 앞 세 시즌 평균). 보정 뒤 리그 평균: 2019-20 {gr_mean('2019-20'):.0f}, 2020-21 {gr_mean('2020-21'):.0f}, 2021-22 {gr_mean('2021-22'):.0f}, 2022-23 {gr_mean('2022-23'):.0f}, 2024-25 {gr_mean('2024-25'):.0f}. 순위는 Transfermarkt 순위표(26라운드 정규 시즌 순서)이고 확인된 최종 순위만 고침(AEK 2022-23 우승, 파나티나이코스 2024-25 2위), 플레이오프·플레이아웃 뒤 최종 순위와 다를 수 있음. 그리스 2부(슈퍼리그 2)는 1부 평균 − 162, 2부 흩어짐(레바디아코스 2021-22 남부 조 1위)",
    f"키프로스 1부 2023-24(추정): 같은 회귀(2022-23 5.1·2023-24 3.75·2024-25 2.75)로 평균 {CY_MEAN['2023-24']:.0f}, 흩어짐은 작은 리그라 노르웨이 선례 63. 몰타 2부(챌린지 리그) 2026-27(추정, 근거 약함): 몰타 1부 평균 약 1340(같은 회귀, 국가 계수 약 1.5)에서 162를 뺀 1180, 순위 곡선 없이 평평하게 둠(2026.11.8 타르시엔 레인보스전 골 1개에만 쓰임)",
    "직접 지정한 상대(유럽 대회·컵 상대; 순위표가 있는 팀은 그 리그 모형 값, 나머지는 다른 선수 자료의 같은 팀·같은 리그 값에 맞춘 '추정'): " + ", ".join(dict.fromkeys(f"{o} {e}" for o, e, lv in MAN_USED)) + ". 2010.11.23 스파르타크 모스크바는 다른 선수 자료의 2010 값 1620",
    "대회 비중: 그리스 슈퍼리그 플레이오프·플레이아웃과 키프로스 2단계 리그는 리그(벨기에 플레이오프 선례). 쿠프 드 프랑스·쿠프 드 라 리그·튀르키예컵·그리스컵·키프로스컵은 국내컵(16강까지·8강·준결승·결승), 트로페 데 샹피옹은 국내컵 결승 비중. 인터토토컵은 유로파 예선, UEFA컵 3라운드·16강·8강과 유로파 32강·16강·8강은 유로파 토너먼트",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회 2020-21까지 원정 다득점·연장(2021-22부터 원정 다득점 없음), 튀르키예컵 2020-21까지 원정 다득점·연장. 그리스컵 2019-20~2022-23 두 경기 라운드는 원정 다득점(연장 원정골 포함)·연장으로 둠(2019-20 16강 파나이톨리코스-파니오니오스 연장 원정골 진출, 2021-22 준결승 올림피아코스-PAOK 1-1 연장 뒤 PAOK 원정골 진출 기사, 2022-23 대회 문서 사본). 못 뛴 차전 스코어는 Transfermarkt 리포트",
    "시즌 구분: 마르세유·디나모 모스크바·리옹·페네르바체는 7월 10일 기준(2006.7.15 인터토토컵·2015.7 러시아 리그 개막·2017.7.27 유로파 예선은 새 시즌; 파예 마르세유·라카제트 리옹·판페르시 페네르바체 선례), 올림피아코스도 7월 10일 기준이되 2020.7.1~9.12(코로나로 늦게 끝난 2019-20 플레이오프·유로파 16강·그리스컵 결승)는 2019-20, 리부른·아폴론·칼리테아·산타 루치아는 8월 1일 기준. 클럽 구분: 2006.7.1 전 리부른, 2014.8.2 전 마르세유, 2015.8.11 전 디나모, 2017.7.1 전 리옹, 2019.7.1 전 페네르바체, 2023.7.23 전 올림피아코스, 2024.8.5 전 아폴론, 2025.8.11 전 칼리테아, 이후 산타 루치아(Transfermarkt 이적 기록, 경기 클럽과 경계 불일치 0)",
    "같은 경기 동료 자료: 파예(마르세유 2013-14) 골에 준 도움 2개(2013.8.17 에비앙전 67분, 2014.2.2 툴루즈전 7분)와 라카제트(리옹 2015~2017) 골에 준 도움 3개(2017.1.8 몽펠리에전 4분, 2017.3.9 로마전 90+2분, 2017.5.14 몽펠리에전 90+5분)는 날짜·분·골 전 스코어·대회·상대 Elo·수준 설명이 모두 같음. 2016.1.20 샹블리전 발부에나 22분 골의 라카제트 도움(Transfermarkt)은 FotMob에 없어 라카제트 자료에 없음",
    "우승 커리어: Transfermarkt 업적 페이지 기준(리그1 2009-10, 그리스 리그 2019-20·2020-21·2021-22, 그리스컵 2019-20, 쿠프 드 라 리그 2009-10·2010-11·2011-12, 트로페 데 샹피옹 2010·2011, 인터토토컵 2006). 개인 수상 없음. 대표팀 기록은 뺌",
    f"2026.11.12 갱신: 현역(산타 루치아, 몰타 2부 챌린지 리그, 2026.7.27 입단). 2026-27 시즌 6경기 1골(Transfermarkt 2026.11.8 경기까지, FotMob에는 산타 루치아 경기 없음)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elk", "elq", "cwc", "MAN", "csa", "lib", "ADD_A"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

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
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
mm_ = {m[0]: m for m in M}
Gstart = {ldate(g): g["isStarting"] == "True" for g in GAMES}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > m[3] + 3 and not r[10] and Gstart[r[9]]: problems.append(("출전 분보다 늦은 기록(선발)", r[9], r[1], r[4], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const VAB_E={J(E)};\nconst VAB_M={J(M)};\nconst VAB_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "unconfirmed_assists": unconf,
               "fotmob_only_assists": FM_ONLY, "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC,
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
