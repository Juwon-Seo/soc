#!/usr/bin/env python3
"""레미 카벨라 (Rémy Cabella, Transfermarkt 113707, FotMob 199834): raw/ -> cabella.json + src/data/cab.js (판정 근거는 judgments.md)

  python3 players/cabella/build_cabella.py [복사본 루트]     # 파일 쓰기
  python3 players/cabella/build_cabella.py --debug           # Elo 출처
  python3 players/cabella/build_cabella.py --stat            # 요약·동료 대조·점검

입력: raw/tm_games.csv(출전·분·날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(대조), raw/ranks.txt(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git 추적 파일: 같은 경기·동료 대조).
구조는 파푸 고메스(build_papugomez.py), 리그1·그리스·러시아 모형은 발부에나(build_valbuena.py) 방식.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
if ARGS: ROOT = os.path.abspath(ARGS[0])
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "cab.js")
OUT_JSON = os.path.join(HERE, "cabella.json")
ME = "113707"
ME_KO = "레미 카벨라"
GAP = "2014-08-01"

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
FPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 날짜·출전 분
# 모든 경기가 유럽(프랑스·잉글랜드·러시아·그리스 등) 경기: TM API UTC 날짜 = TM 일정 날짜 = 리포트 날짜(521경기 모두 같음 확인)
def ldate(g): return g["date_utc"][:10]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
def minutes(g): return int(g["playedMinutes"])
def season(g): s = int(g["seasonId"]); return f"{s}-{str(s + 1)[2:]}"

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "GB1", "RU1", "GR1"}
CUPS = {"FRC", "FRL", "FAC", "CGB", "RUP", "GRP"}
def rnd_of(g): return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "FRCH": return "df"                       # 트로페 데 샹피옹 = 국내컵 결승 비중
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2024-25 리그 단계도 TM 'Group Stage'
        if r.startswith("last 16"): return "cl16"
        sys.exit("CL 라운드 " + rnd)
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("intermediate"): return "elk"
        sys.exit("EL 라운드 " + rnd)
    if cid == "ECLQ": return "ecq"
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"
        if r.startswith("last 16") or r.startswith("quarter"): return "eck"
        sys.exit("UCOL 라운드 " + rnd)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r: return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    if cid in ("CL", "CLQ", "EL", "ELQ", "UCOL", "ECLQ"): return (1, 1) if d < "2021-07-01" else (0, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g = G[gid]
    if gid not in MI: return "h" if g["venue"] == "H" else "a"
    m = MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; oid = m["other_leg_id"]; club = G[gid]["club_id"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split(":"))
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 " + gid)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    return (oh, oa) if side_of(gid) == "a" else (oa, oh)   # 다른 차전은 홈·원정이 바뀜

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 골·도움 판정 표
# 2014.8 이후 Transfermarkt에만 있는 도움(FotMob 경기 기록에 카벨라 도움 없음): gameId|분 -> 근거(넣음) / None(뺌)
POST_GAP = {
    "2978645|63": "Objectif Gard 경기 기사('Cabella … Beric s'élève plus haut que tout le monde', 카벨라 프리킥에 베리치 헤딩)·Sporting Life 문자 중계(베리치 63분 헤딩, 카벨라 도움)",
    "3646599|85": None,   # 2021.9.22 레닌그라데츠전(러시아컵 조별) 크리호비아크 골: FotMob 이벤트에 도움자 칸이 비어 있고 경기 기사에서 도움자 확인 못 함
    "4718755|25": None,   # 2025.12.3 엘라스 시로스전(그리스컵) 야즈즈 골: FotMob 이벤트 도움 칸 비어 있음, 그리스 경기 기사(iefimerida·in.gr·skai)에 카벨라 도움 언급 없음
    "4788534|52": "Sky Sports 경기 문자 중계(기라시 골, 'Assisted by Rémy Cabella')·PlayerStats 경기 기록(52분 H. Guirassy (R. Cabella))",
}
# FotMob에만 있는 도움(Transfermarkt는 도움자 없음/다른 선수): gameId|FotMob 골 뒤 스코어 -> (근거|None, 분, 득점자)
FM_ONLY = {
    "3047612|2-2": (None, 67, "Wahbi Khazri"),   # 2018.12.5 보르도전 67분: worldfootball 1곳만 카벨라 도움, Transfermarkt는 도움자 없음 → 2곳 확인 못 함
}
ADD_GOAL = {}

def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def fm_ev(gid, after_ha):
    for f in FME.get(gid, []):
        if f["newScore_home_away"] == after_ha and f["pen_shootout_event"] != "True": return f
    return None

def assist_reason(e):
    t = e["assist_type"]
    if e["scorer_id"] == ME: return "본인 PK 골에 본인 도움"
    if e["own_goal"] == "1" or e["goal_desc"] == "Own-goal": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

raw_rows, judg, post_gap_log, min_fix = [], [], [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0); d = ldate(g)
    for i, e in enumerate(EVS[gid]):
        h, a = map(int, e["score_home_away_after"].split("-"))
        if gid == "4445123":       # 리포트가 3·4번째 골 스코어를 바꿔 적음(2:2 → 2:1, 2:1 → 2:2): 순서대로 다시 셈(FotMob 기준)
            h, a = (prev[0] + 1, prev[1]) if e["side"] == "home" else (prev[0], prev[1] + 1)
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == ME and e["own_goal"] != "1"
        is_a = e["assist_id"] == ME
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        f = fm_ev(gid, e["score_home_away_after"])
        tag = f"{gid}|{mins(e['minute'])[0]}"
        if dm == 0 and mi in (45, 90) and f and f["overloadTime"] and int(f["time"]) == mi and int(f["overloadTime"]) > 0:
            dm = f"{mi}+{int(f['overloadTime'])}"; min_fix.append((gid, d, opp(g), e["minute"], dm)); mi += int(f["overloadTime"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], why))
            elif d >= GAP and not (f and f["cabella_assist"] == "1"):
                v = POST_GAP.get(tag, "미판정")
                post_gap_log.append((gid, d, opp(g), e["minute"], e["scorer"], e["assist_type"], g["competitionId"], v))
                if v == "미판정": sys.exit("[판정 필요] 2014.8 이후 Transfermarkt 단일 도움 " + tag + " " + d + " " + opp(g) + " " + e["scorer"])
                if v: raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
                else: judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], "2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)"))
            else:
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            if e["side"][0] != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))
fm_only_seen = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["cabella_assist"] != "1" or f["pen_shootout_event"] == "True": continue
        tm = [e for e in EVS[gid] if e["score_home_away_after"] == f["newScore_home_away"]]
        if any(e["assist_id"] == ME for e in tm): continue
        k = f"{gid}|{f['newScore_home_away']}"
        if k not in FM_ONLY: sys.exit("[판정 필요] FotMob 단독 도움 " + k)
        why, mi, sc = FM_ONLY[k]; g = G[gid]
        fm_only_seen.append((gid, ldate(g), opp(g), mi, sc, why))
        if why: sys.exit("FotMob 단독 도움 추가 처리 미구현")
        judg.append(("도움 제외(FotMob 단독)", ldate(g), opp(g), str(mi), sc, "FotMob에만 있음, 다른 출처 2곳 확인 못 함"))
for gid, g in G.items():
    pm = FPM.get(g["fotmobMatchId"])
    if pm and int(pm["assists"] or 0) > int(g["assists"] or 0):
        fm_only_seen.append((gid, ldate(g), opp(g), "FotMob 선수 경기 목록 도움", pm["assists"], g["assists"]))
cnt_ = collections.Counter((r[1], r[0]) for r in raw_rows)
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

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
def key(n):
    k = norm(n); return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"].split("·") == [ME_KO]: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(os.path.basename(p) for p in subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "cab.js") or b not in TRACKED: continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio",
        "atletico", "us", "as", "ss", "ssc", "acf", "olympique", "fk", "sv", "nk", "cd", "bc", "milan", "inter", "madrid", "fbc",
        "racing", "arsenal", "stade", "sm", "ogc", "aj", "rc", "losc", "hsc", "ea", "estac", "sco", "moscow", "spartak", "dinamo", "dynamo",
        "krasnodar", "athens", "thessaloniki", "saint", "lyon", "girondins", "rennais", "fco", "piraeus", "hotspur", "town", "rovers"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
# 그리스: Transfermarkt 표는 26라운드 정규 시즌 순서라 공식 최종 순위(플레이오프·플레이아웃 뒤)로 고침(영어 위키백과 시즌 문서 표)
#   2020-21 플레이오프: 올림피아코스 1·PAOK 2(64점)·아리스 3·AEK 4(기존 자료 AEK 4위와 같음)
#   2025-26: AEK 1·올림피아코스 2·PAOK 3·파나티나이코스 4 … 플레이아웃 아트로미토스 9·판아이톨리코스 10·키피시아 11·아스테라스 12·라리사 13·판세라이코스 14
RANKS[("GR1", "2020-21")][key("PAOK Thessaloniki")] = (2, 14, "PAOK Thessaloniki")
RANKS[("GR1", "2025-26")][key("Panserraikos")] = (14, 14, "Panserraikos")

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
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위")
    for e in ENTS:
        m = pat.match(str(e[12] or ""))
        if m: c[int(m.group(1))][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
def interp(tab, r):
    """기존 순위값 사이(빈 순위 1칸이면 앞뒤 가운데, 여러 칸이면 직선)"""
    if r in tab: return tab[r], False
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None, True
    a, b = max(lo), min(hi)
    return half_up(tab[a] + (tab[b] - tab[a]) * (r - a) / (b - a)), True
def edge(tab, r, n, sd):
    k = min(tab, key=lambda x: abs(x - r))
    return half_up(tab[k] + sd * (curve(r, n) - curve(k, n)))
INTERP_USED = set()

# 그리스 1부(발부에나 자료 모형): 앞뒤 3시즌 UEFA 국가 계수 회귀 + 그리스 보정, 흩어짐 119
GR_COEF = {2018: 5.1, 2019: 4.9, 2020: 5.1, 2021: 8.0, 2022: 2.125, 2023: 11.4, 2024: 12.688}
def reg_mean(coefs): return 1473 + 23.33 * (sum(coefs) / len(coefs) - 7.3333)
def gr_reg(start):
    ys = (start - 1, start, start + 1) if start + 1 in GR_COEF else (start - 2, start - 1, start)
    return reg_mean([GR_COEF[y] for y in ys])
GR_ANCH = [(2019, 1, 1680), (2020, 1, 1690), (2021, 2, 1590)]
GR_K = sum(v - (gr_reg(y) + 119 * curve(r, 14)) for y, r, v in GR_ANCH) / len(GR_ANCH)
def gr_mean(season): return gr_reg(int(season[:4])) + GR_K

def rank_model(lg, season, r, n):
    if lg == "FR1":
        m = ents_map("리그1", season); v, it = interp(m, r)
        if v is None:
            v = edge(m, r, n, 100.16); INTERP_USED.add(("리그1", season, r, v, "끝"))
            return v, f"리그1 {season} {r}위 (추정, 이웃 순위값에 순위 곡선 차이)"
        if it: INTERP_USED.add(("리그1", season, r, v))
        return v, f"리그1 {season} {r}위"
    if lg == "FR2":
        m = ents_map("리그2", season); v, it = interp(m, r)
        if v is None: return half_up(1540 + SD2 * curve(r, n)), f"리그2 {season} {r}위 (추정, 프랑스 2부 평균 1540 모형)"
        if it: INTERP_USED.add(("리그2", season, r, v))
        return v, f"리그2 {season} {r}위"
    if lg == "RU1":
        if season == "2019-20":   # 크바라츠헬리아·발부에나 자료의 2019-20 순위값에 맞는 평균 1430.3·흩어짐 63
            return half_up(1430.3 + 63 * curve(r, n)), f"러시아 프리미어리그 {season} {r}위 (리그 수준 추정)"
        m = ents_map("러시아 프리미어리그", season); v, it = interp(m, r)
        if v is None:
            v = edge(m, r, n, 63); INTERP_USED.add(("러시아", season, r, v, "끝"))
        elif it: INTERP_USED.add(("러시아", season, r, v))
        return v, f"러시아 프리미어리그 {season} {r}위 (리그 수준 추정)"
    if lg == "GR1":
        if season == "2025-26":   # 2025-26 국가 계수 미확정 → 2024-25 리그 수준(기존 순위값) 사용
            m = ents_map("그리스 슈퍼리그", "2024-25")
            if r in m: return m[r], f"그리스 슈퍼리그 {season} {r}위 (리그 수준 추정, 2024-25 리그 수준 사용)"
            return half_up(gr_mean("2024-25") + 119 * curve(r, n)), f"그리스 슈퍼리그 {season} {r}위 (리그 수준 추정, 2024-25 리그 수준 사용)"
        return half_up(gr_mean(season) + 119 * curve(r, n)), f"그리스 슈퍼리그 {season} {r}위 (리그 수준 추정)"
    return None

LG_OF = {"FR1": ["FR1", "FR2"], "GB1": ["GB1"], "RU1": ["RU1"], "GR1": ["GR1"]}
def lg_cands(g):
    cid = g["competitionId"]
    if cid in LG_OF: return LG_OF[cid]
    return ["FR1", "FR2", "RU1", "GR1"]

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
man("AS Prix-Lès-Mézières", "2011-12", 1100, "프랑스 6부 이하 아마추어 (추정, 다른 선수 자료 프랑스 6부 지역 리그 1100과 같음)")
man("Olympique Strasbourg", "2018-19", 1000, "프랑스 7부(지역 리그 2) 2018-19 (추정, 다른 선수 자료 프랑스 아마추어 하부 1000)")
man("Slovan Bratislava", "2023-24", 1500, "슬로바키아 2023-24 1위 (추정, 다른 선수 자료 슬로반 2024-25 1위 1500과 같음)")

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, g):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o); s = season(g)
    if (k, s) in MAN:
        e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    if (k, s) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for lg in lg_cands(g):
        t = RANKS.get((lg, s), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s, r, n)
            if res and res[0]:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, g["competitionId"], s)); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, g)
    t = tie_of(gid)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if t: row.append(t)
    E.append(row)
def tkey(r): return 45 + int(str(r[11])[3:]) / 100 if str(r[11]).startswith("45+") else r[4]
E.sort(key=lambda r: (r[9], tkey(r), 0 if r[0] == "g" else 1))

if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)

M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), minutes(g)])

if "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    print("보간:", sorted(INTERP_USED))
    sys.exit(0)

exec(open(os.path.join(HERE, "out_cabella.py"), encoding="utf-8").read())
