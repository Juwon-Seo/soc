#!/usr/bin/env python3
"""제롬 로텐 (Transfermarkt 5300): raw/ -> rothen.json + src/data/rot.js (판정 근거는 judgments.md)

  python3 players/rothen/build_rothen.py            # 파일 쓰기
  python3 players/rothen/build_rothen.py --debug    # Elo 출처 로그만 출력
  python3 players/rothen/build_rothen.py --stat     # 요약·동료 대조·FotMob 대조
  python3 players/rothen/build_rothen.py --ties     # 합산 행·판정 출력

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv(2011~13 골 대조), raw/ranks.txt(Transfermarkt 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
뼈대는 지울리 build_giuly.py(같은 프랑스 클럽·같은 판정 규칙)를 따름.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "rot.js")
OUT_JSON = os.path.join(HERE, "rothen.json")
ME = "5300"
ME_KO = "제롬 로텐"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

def ldate(g): return g["date_local_computed"]     # 리포트 날짜가 있는 경기는 리포트 날짜와 모두 같음(raw 점검)
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 판정 표
MIN_FIX, MIN_EST = {}, {}       # 출전 분은 Transfermarkt 그대로(빈칸 0경기)
GAP = "2014-08-01"              # 모든 도움이 이 날짜 전 → Transfermarkt 리포트 단일 출처 허용(클로제·인시녜·지울리 선례)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "FR2", "SC1", "TR1"}
CUPS = {"FRC", "FRL", "SCP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "FRCH": return "df"                             # 트로페 데 샹피옹 = 국내컵 결승 비중
    if cid == "UI": return "elq"                              # 인터토토컵 = 유로파 예선(지단·램파드·지울리 선례, 준결승·결승 포함)
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"           # UEFA컵 1라운드 = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                          # 2·3라운드·32강(intermediate stage)·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("UEFA", "CL", "UI"): return (1, 1)             # UEFA 대회 2020-21까지(인터토토는 램파드·지울리 선례 가정)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G and G[oid]["gameState"] != "penalty_shootout":
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, m["other_leg_score"].split(":"))     # 이 경기 홈 팀 기준 표기(raw tm_two_leg_ties로 확인)
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

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    gid = g["gameId"]
    row = [ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), MIN_FIX.get(gid, MIN_EST.get(gid, int(g["playedMinutes"] or 0)))]
    if gid in MIN_EST: row.append(1)
    M.append(row)

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
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t.startswith("Deflect"): return "굴절"
    return None

BEFORE_FIX = {}
raw_rows, judg = [], []
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
        if e["scorer_id"] == ME and is_og(e): judg.append(("본인 자책골(골 아님)", ldate(g), opp(g), e["minute"]))
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        if (gid, e["minute"]) in BEFORE_FIX: gf, ga = BEFORE_FIX[(gid, e["minute"])]
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk:
                if e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
                judg.append(("PK 아님(PK가 막힌 뒤 리바운드 골)", ldate(g), opp(g), e["minute"], e["goal_desc"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
GA_GAMES = {r[1] for r in raw_rows}
SM_GA = [x for x in SCORE_MISMATCH if x[0] in GA_GAMES]
if SM_GA: sys.exit("골·도움 경기 리포트 불완전 " + str(SM_GA))

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
MANUAL_ALIAS = {"olympique lyon": "olympique lyonnais", "lokomotiv moskau": "lokomotiv moscow"}
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
    if b == "hon.js" or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "foot", "ball",
        "atletico", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss", "olympique", "milan", "inter", "madrid", "fk", "if",
        "deportivo", "san", "santa", "saint", "us", "ogc", "losc", "stade", "racing", "athletic", "union", "sportive", "vfb", "vfl"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, collections.Counter((x[2], x[12]) for b, x in cand)

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
RANK_FIX = {}   # (리그, 시즌, 팀 키) -> 공식 최종 순위(Transfermarkt 표와 다를 때) — judgments.md 6절

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
SD1 = {"FR1": 100.16}
LGNAME = {"FR1": "리그1"}
INTERP_USED = set()
LADDER_FR1 = {}
for _n, _s in ((20, "2002-03"), (18, "2023-24")):
    _m = ents_map("리그1", _s)
    if sorted(_m) != list(range(1, _n + 1)): sys.exit("리그1 기준 순위표 불완전 " + _s)
    LADDER_FR1[_n] = [_m[i] for i in range(1, _n + 1)]

def rank_model(lg, season, r, n):
    if lg == "FR1":
        m = ents_map("리그1", season)
        if not m: return None
        v, it = mid(m, r)
        if v is None:
            # 끝 순위(앞이나 뒤에 기존 값이 없음): 같은 팀 수의 기존 전체 순위값(리그1 20팀 2002-03·18팀 2023-24 표, 지울리 선례)
            v = LADDER_FR1[n][r - 1]; INTERP_USED.add((lg, season, r, v, "표"))
            return v, f"리그1 {season} {r}위"
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"리그1 {season} {r}위"
    if lg == "FR2":
        m = ents_map("리그2", season)
        v, it = mid(m, r)
        if v is None:
            v = half_up(1540 + SD2 * curve(r, n)); INTERP_USED.add((lg, season, r, v, "모형"))
            return v, f"리그2 {season} {r}위 (추정, 프랑스 2부 평균 1540 모형)"
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"리그2 {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; SAME_MULTI = []
def opp_elo(o, d, cid, rnd=""):
    cand, vals = same_match(o, d)
    if vals:
        if len(vals) > 1: SAME_MULTI.append((o, d, dict(vals)))
        (e, lv), _ = vals.most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    k = key(o)
    s0 = eu(d)
    if (k, s0) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, s0)]).most_common(1)[0]
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s0); return e, lv
    if (k, s0) in MAN:
        e, lv = MAN[(k, s0)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for lg in ("FR1", "FR2"):
        t = RANKS.get((lg, s0), {})
        if k in t:
            r, n, _ = t[k]
            r = RANK_FIX.get((lg, s0, k), r)
            res = rank_model(lg, s0, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], (lg, s0, r, n)); return res
    MISS.append((o, d, cid, s0)); return 0, "?"

# ---------------------------------------------------------------- 직접 추정(모두 lv에 '추정') — judgments.md 6절
MAN_NOTE = {}
def man2(o, s, e, lv, why): man(o, s, e, lv); MAN_NOTE[(key(o), s)] = why
# 순위는 영어 위키백과 시즌 문서의 최종 순위표로 확인(judgments.md 6절)
man2("MFK Ruzomberok", "2001-02", 1400, "슬로바키아 2001-02 4위 (추정, 다른 선수 자료 슬로바키아 3위·6위 1400과 같음)",
     "2001-02 Slovak Superliga 4위/10팀; 다른 선수 자료 질리나 2010-11 3위·페트르잘카 2008-09 6위 1400")
man2("Lokomotiv Moskau", "2003-04", 1580, "러시아 2003 4위 (추정, 다른 선수 자료 로코모티프 모스크바 2003 1580과 같음)",
     "2004.2 경기 = 직전 완료 시즌 2003(러시아는 달력 연도 시즌, 2004 시즌은 3월 개막); 2003 Russian Premier League 4위/16팀")
man2("Rodez AF", "2008-09", 1275, "프랑스 3부(나시오날) 2008-09 15위 (추정, 다른 선수 자료 나시오날 13위 1287·17위 1263의 가운데)",
     "2008-09 Championnat National 15위/20팀(쿠프 드 프랑스 16강 상대)")
man2("FC Metz", "2012-13", 1375, "프랑스 3부(나시오날) 2012-13 2위 (추정, 다른 선수 자료 나시오날 2위 1375와 같음)",
     "2012-13 Championnat National 2위/20팀(쿠프 드 라 리그 3라운드 상대)")

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, rnd)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
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
    for x in SAME_MULTI: print("같은 경기 값 여럿", x)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    print("보간", sorted(INTERP_USED))
    sys.exit(0)
if __name__ == "__main__" and "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print("score mismatches", SCORE_MISMATCH)
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    print(len(E), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E))
    for j in judg: print(j)
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2011~13)
FM_CMP = []; FM_N = 0; FM_A = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    fm_all = [r for r in FME[gid] if r["pen_shootout_event"] != "True"]
    for r in fm_all:
        if r["rothen_assist"] == "1": FM_A.append((ldate(G[gid]), opp(G[gid]), r["time"], r["scorer"]))
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    if not tm: continue
    fm = [r for r in fm_all if r["rothen_scorer"] == "1" and r["ownGoal"] not in ("1", "True")]
    FM_N += 1
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]))):
        a = mins(t["minute"])[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
        if a != b and not (t["minute"].startswith("90+") and b == 90):
            FM_CMP.append(("분 다름", gid, ldate(G[gid]), t["minute"], f["time"]))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or ((a[14] if len(a) > 14 else 0) or 0) != ((b[14] if len(b) > 14 else 0) or 0): d.append(f"단판/합산 {a[7]}{a[14] if len(a) > 14 else ''}/{b[7]}{b[14] if len(b) > 14 else ''}")
    if a[10] != b[10]: d.append("연장")
    return d
def same_opp(x, r): return key(x[1]) == key(r[1]) or bool(toks(x[1]) & toks(r[1]))
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Rothen", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움→로텐 골", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_opp(x, r)]
            if hit: CROSS.append(("로텐 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_opp(x, r):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회/합산 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
# 상대 팀 선수 자료: 같은 날 로텐 팀을 상대로 한 기록 → 골 순서(스코어) 대조
TEAMN = {"1162": "SM Caen", "1095": "ESTAC Troyes", "162": "AS Monaco", "583": "Paris Saint-Germain", "124": "Rangers", "868": "Ankaragucu", "595": "SC Bastia"}
for r in E:
    g = [x for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
    for b, (oe, om) in OTHERS.items():
        for x in oe:
            if x[9] == r[9] and toks(x[1]) & toks(TEAMN[g["club_id"]]):
                CROSS.append(("상대 팀 선수 같은 경기 기록(스코어 대조용)", b, r[9], x[0], x[4], x[5], x[6], "로텐 행", r[0], r[4], r[5], r[6]))
# 같은 경기 타인 골 중 TM이 로텐 도움으로 적었으나 규칙으로 뺀 것
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_opp(x, [0, j[2]]):
                    CROSS.append(("TM 로텐 도움을 규칙대로 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("caert", "2000-07-01", "SM 캉", "1997~2000"), ("trort", "2002-01-01", "ESTAC 트루아", "2000~2001"),
         ("monrt", "2004-07-01", "AS 모나코", "2002~2004"), ("psgrt", "2009-09-01", "파리 생제르맹", "2004~2009"),
         ("ranrt", "2010-01-29", "레인저스", "2009"), ("ankrt", "2011-07-01", "MKE 앙카라귀쥐", "2010"),
         ("basrt", "2013-07-01", "SC 바스티아", "2011~2013"), ("caert", None, "SM 캉", "2013")]
TM_CLUB = {"1162": "caert", "1095": "trort", "162": "monrt", "583": "psgrt", "124": "ranrt", "868": "ankrt", "595": "basrt"}
def club_of(d):
    for k, u, n, y in CLUBS:
        if u is None or d < u: return k
CN = {}
for k, u, n, y in CLUBS: CN.setdefault(k, n)
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CN)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
CAEN2 = [0, 0, 0, 0]
for m in M:
    if m[0] >= "2013-07-01": CAEN2[0] += 1; CAEN2[3] += m[3]
for r in E:
    if r[9] >= "2013-07-01": CAEN2[1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({(r[9]) for r in E if len(r) > 14})
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club == "trort": s = y if m >= 7 else y - 1
    elif club in ("caert", "monrt", "psgrt", "basrt"): s = y if d[5:] >= "07-10" else y - 1
    else: s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print("캉 2기", CAEN2)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    print("FotMob", FM_N, FM_CMP, "FM 로텐 도움", FM_A)
    for c in CROSS: print(c)
    print(sorted(collections.Counter(season_of(m[0], club_of(m[0])) for m in M).items()))
    print("blank-type assists", UNTYPED)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
SRC = ELO_SRC
first, last = M[0], M[-1]
EXA = [j for j in judg if j[0] == "도움 제외"]
PKS = [r for r in E if r[0] == "g" and r[8]]
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
MODEL_USED = sorted({(v[3], o) for (o, d), v in ELO_LOG.items() if v[0] == "model"})
KO_NAME = {"Stade Lavallois": "라발", "CS Louhans-Cuiseaux 71": "루앙퀴소", "AS Beauvais Oise": "보베", "EA Guingamp": "갱강",
           "Le Mans Union Club 72": "르망", "Nîmes Olympique": "님", "AS Monaco": "모나코", "FC Nantes": "낭트", "US Boulogne": "불로뉴",
           "Dijon FCO": "디종", "Clermont Foot 63": "클레르몽"}
def model_txt():
    out = []
    for (lg, s, r, n), o in MODEL_USED:
        out.append(f"{KO_NAME.get(o, o)} {s} {r}위/{n}팀")
    return "·".join(out)
NOTE_LINES = [
    f"제롬 로텐(SM 캉·ESTAC 트루아·AS 모나코·파리 생제르맹·레인저스·MKE 앙카라귀쥐·SC 바스티아)의 클럽 공식 경기 {NG}경기({d_(first[0])} {first[1]}전 ~ {d_(last[0])} {last[1]}전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·파리 생제르맹 B팀·프랑스 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CN[k]} {c3(v)}" for k, v in ST.items())
    + f"(SM 캉은 1997~2000 2부 {ST['caert'][0]-CAEN2[0]}·{ST['caert'][1]-CAEN2[1]}·{ST['caert'][2]-CAEN2[2]}과 2013 리그2 {c3(CAEN2)}의 합계). 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부, 리포트 골·도움 수가 선수 경기 성적과 경기마다 같음). 영어·프랑스어 위키백과 클럽·시즌별 경기·골과 모든 시즌이 같음(영어 위키백과는 캉 2013-14 줄이 없음). FotMob은 바스티아·캉 2011~2013 경기만 대조함",
    "범위: 1997~2000 캉(프랑스 2부, 프로)부터 모든 소속 팀-시즌이 프로 1·2부. 파리 생제르맹 B팀(프랑스 4부 CFA 아마추어 2군) 3경기(2009.8.9·2010.8.8·2010.8.22, 골·도움 없음)는 2군이라 뺌. 레인저스(2009.9~2010.1 임대)는 2009.10.20 뒤 부상으로 출전 없음, 앙카라귀쥐 임대(2010.1~6) 뒤 파리 생제르맹 2010-11은 1군 출전 없이 2010.10.19 계약 해지, 2011.7 바스티아 입단",
    f"골: 자책골 없음. PK 골 {NPK}개는 Transfermarkt 골 유형 'Penalty'(" + ", ".join(f"{d_(r[9])} {r[1]}전 {r[4]}분" for r in PKS) + "). 놓친 PK 없음. FotMob(2011~13) 골 기록과 대조한 9경기는 골·PK가 모두 같고 2012.1.18 Le Havre AC전 골만 Transfermarkt 82분·FotMob 83분 → Transfermarkt",
    f"도움: 모든 도움이 2014년 8월 전이라 Transfermarkt 경기 리포트 단일 출처를 씀(클로제·인시녜·지울리 선례). Transfermarkt 도움 85개에서 PK 유도 2개(" + ", ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]}" for j in EXA if j[5] == "PK 유도") + f")를 빼 {NA}개. 도움 유형 칸이 빈 {UNTYPED}개는 일반 도움으로 셈(토티·디 나탈레 선례). 슈팅 리바운드·굴절·상대 자책골 유도·본인 PK 골 본인 도움 표기는 없음. FotMob 경기 기록은 2011~13 도움 칸이 거의 비어 있어(골 212개 중 6개만 도움자) 2013.1.13 Stade Reims전 21분 일랑 골 도움만 겹쳐 확인됨",
    "도움이 실제보다 적을 수 있음: Transfermarkt는 2002-03 전 도움 기록이 거의 없음(캉 1997~2000 0개, 트루아 2000-01 1개, 모나코 2001-02 0개·2002-03 2개). 프랑스어 위키백과 도움 칸은 통산 105개(Transfermarkt 85개)로 트루아 2000-01 6개, 모나코 2002-03 18개·2003-04 18개, 파리 생제르맹 2004-05 7개·2005-06 8개·2008-09 14개로 더 많지만 경기별 근거가 없어 더하지 않음",
    "출전 분: Transfermarkt 그대로(빈칸 없음, 추정한 경기 없음). Transfermarkt는 1998.1.21 2부 27라운드 Stade Lavallois전(로텐 골)과 28라운드 Chamois Niortais FC 원정(15분 출전, 골·도움 없음)을 같은 날짜로 적음 — 라발전 날짜는 다른 경기 기록 사이트로 확인했으나 니오르전의 실제 날짜는 확인하지 못해 Transfermarkt 날짜를 그대로 씀. 연장·승부차기 경기는 Transfermarkt 출전 분(트로페 데 샹피옹 2004·2006은 120분, 같은 경기 다른 선수 자료와 같음). 2013.3.2 리그1 경기 퇴장(90+7분). 연장 골·도움 없음. 날짜는 경기 현지 날짜(모두 유럽 경기)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(파울레타·지울리·토뱅), 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표, 영어 위키백과 시즌 문서로 순위 확인)를 기존 리그 순위값·리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['기존 팀×시즌 값']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    f"리그2(프랑스 2부, 1997-98 22팀·나머지 20팀)는 그 시즌 기존 순위값, 빈 순위는 앞뒤 기존 값의 가운데, 앞이나 뒤에 기존 값이 없으면 평균 1540·2부 흩어짐 모형(추정): {model_txt()}",
    "직접 추정(모두 '추정'): " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED) + ". 순위 근거: 영어 위키백과 2001-02 슬로바키아 1부·2003 러시아 프리미어리그·2008-09·2012-13 프랑스 3부(나시오날) 시즌 문서. 로코모티프 모스크바는 2004년 2월 경기라 직전에 끝난 2003 시즌(러시아는 달력 연도 시즌) 순위를 씀",
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·스코틀랜드 리그컵은 국내컵(16강까지·8강·준결승·결승), 트로페 데 샹피옹은 국내컵 결승 비중. 인터토토컵(2라운드~결승)과 UEFA컵 1라운드는 유로파 예선, UEFA컵 조별은 유로파 조별, UEFA컵 2·3라운드·32강·16강·8강은 유로파 토너먼트. 챔스 조별·16강·8강·준결승·결승(2004 결승 포르투전)",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함: UEFA 대회·인터토토컵은 원정 다득점·연장(인터토토컵은 램파드·지울리 선례 가정). 다른 차전 스코어는 Transfermarkt 경기 성적·리포트",
    "시즌 구분: 트루아는 7월 1일 기준(2001.7.8~7.25 인터토토컵 경기가 2001-02, 2001.6.30 인터토토컵 2라운드 1차전 WIT 조지아전은 2000-01 — 엘베르 1996.6.29 인터토토컵 선례), 캉·모나코·파리 생제르맹·바스티아는 7월 10일 기준(1999.7.31 리그 개막전, 2004.7.31·2006.7.30 트로페 데 샹피옹, 2005.7.29 리그1 개막전, 2011.7.22 쿠프 드 라 리그가 새 시즌), 레인저스·앙카라귀쥐는 기본 8월 1일. 클럽 구분(Transfermarkt 이적 날짜): 2000.7.1 트루아, 2002.1.1 모나코, 2004.7.1 파리 생제르맹, 2009.9.1 레인저스, 2010.1.29 앙카라귀쥐, 2011.7.1 바스티아, 2013.7.1 뒤 캉(두 번째 시기, 같은 클럽으로 묶음). 경기 클럽과 경계 불일치 0",
    "같은 경기 동료 자료: 파울레타(로텐 도움→파울레타 골 9, 파울레타 도움→로텐 골 1: 2007.4.21 FC Nantes전 43분), 지울리(로텐 도움→지울리 골 2: 2003.11.22 RC Lens전·2009.4.19 Le Havre AC전), 토뱅(2013.4.6 Stade Brestois 29전 50분)과 날짜·분·골 전 스코어·대회·상대 Elo·수준 설명이 모두 같음. 상대 팀 선수 자료(엘베르·고부·벤제마·지냑·메네즈·벤 아르파·주니뉴·발부에나·고미스·라카제트)와 골 순서도 맞음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 리그1 우승 없음, 스코틀랜드 리그 2009-10(레인저스), 리그2 2011-12(바스티아), 쿠프 드 프랑스 2005-06(파리 생제르맹), 쿠프 드 라 리그 2002-03(모나코)·2007-08(파리 생제르맹), 스코틀랜드 리그컵 2009-10(레인저스), 인터토토컵 2001(트루아), 챔스 2003-04 준우승. 선수협회(UNFP) 시상은 프랑스어 위키백과 'Trophées UNFP du football' 목록 기준: 리그1 올해의 팀 2002-03, 리그2 올해의 선수 2011-12(리그2 올해의 팀 1999-00·2011-12는 2부 팀 선정이라 넣지 않음). 대표팀(컨페더레이션스컵 2003)은 뺌",
    "은퇴: 마지막 클럽 공식 경기는 2013.9.27 Le Havre AC전(리그2, 68분), Transfermarkt 기준 2013.10.16 캉과 계약 해지 뒤 은퇴",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elk", "elq", "cwc", "MAN", "csa", "lib", "lg"]:
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
    ar = sorted(rs, key=lambda r: r[4])
    for a, b in zip(ar, ar[1:]):
        if b[5] < a[5] or b[6] < a[6]: problems.append(("시간순 스코어 역순", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
SAME_DAY_OK = {"1998-01-21"}   # TM이 2부 27라운드 라발전(리포트·footballdatabase 1998.1.21)과 28라운드 니오르 원정(리포트 없음)을 같은 날짜로 적음 — judgments.md 3절
for d, c in mdates.items():
    if c > 1 and d not in SAME_DAY_OK: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
    if r[4] > 90 and not r[10] and not r[11]: problems.append(("90분 넘는데 표기 없음", r))
for r in E:
    g = [x for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
    m = [x for x in M if x[0] == r[9] and x[1] == r[1]][0]
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    dur = int(g["gameDuration"])
    if g["isStarting"] == "True": lo, hi = 0, m[3] + 8
    else: lo, hi = dur - m[3] - 8, dur + 10      # 교체 투입 시각 자료가 없어 경기 길이 − 출전 분으로 근사
    if not (lo <= r[4] <= hi): problems.append(("출전 구간 밖 기록", r[9], r[4], g["isStarting"], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const ROT_E={J(E)};\nconst ROT_M={J(M)};\nconst ROT_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_rothen_assists": FM_A, "elo_sources": ELO_SRC,
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}, "man_notes": {f"{k[0]}|{k[1]}": v for k, v in MAN_NOTE.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
