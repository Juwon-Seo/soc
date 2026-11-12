#!/usr/bin/env python3
"""뤼도비크 지울리 (Transfermarkt 5299): raw/ -> giuly.json + src/data/giu.js (판정 근거는 judgments.md)

  python3 players/giuly/build_giuly.py            # 파일 쓰기
  python3 players/giuly/build_giuly.py --debug    # Elo 출처 로그만 출력
  python3 players/giuly/build_giuly.py --stat     # 요약·동료 대조·FotMob 대조
  python3 players/giuly/build_giuly.py --ties     # 합산 행 출력

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv(2010~13 골 대조), raw/ranks.txt(Transfermarkt 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "giu.js")
OUT_JSON = os.path.join(HERE, "giuly.json")
ME = "5299"
ME_KO = "뤼도비크 지울리"

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

def ldate(g): return g["date_local_tm_report"]     # 리포트 현지 날짜(API UTC 날짜는 53경기에서 하루 이름)
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 판정 표
MIN_FIX, MIN_EST = {}, {}       # 출전 분은 Transfermarkt 그대로(빈칸 0경기)
GAP = "2014-08-01"              # 이 전 도움은 TM 단일 출처 허용(몽도르 2014-15 포함 모든 도움이 이전 또는 도움 0)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "FR2", "ES1", "IT1", "FR4B", "FR4C"}
CUPS = {"FRC", "FRL", "CDR", "CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("FRCH", "SUC", "SCI", "USC"): return "df"      # 슈퍼컵류 = 국내컵 결승 비중
    if cid == "KLUB": return "cwc"
    if cid == "UI": return "elq"                              # 인터토토컵 = 유로파 예선(지단·램파드·비야 선례, 조별·결승 포함)
    if cid == "ELQ": return "elq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"           # UEFA컵 1라운드 = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                          # 2·3라운드·32강·16강·8강
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
    if cid in ("UEFA", "CL", "EL", "ELQ", "UI"): return (1, 1)  # UEFA 대회 2020-21까지(인터토토는 램파드 선례 가정)
    if cid == "CDR": return (1, 1)                              # 코파 델 레이 2018-19까지 원정 다득점·연장
    if cid == "SUC": return (1, 1)                              # 수페르코파(에투·호나우지뉴 자료와 같음)
    if cid == "CIT": return (1, 1)                              # 코파 이탈리아 2021-22까지 원정 다득점(토티 자료와 같음)
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
    oh, oa = map(int, m["other_leg_score"].split(":"))     # 이 경기 홈 팀 기준 표기
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

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
for gid in G:
    if gid not in EVS and MI.get(gid, {}).get("final") not in (None, "", "0:0") and G[gid]["gameState"] != "penalty_shootout":
        SCORE_MISMATCH.append((gid, ldate(G[gid]), (0, 0), MI[gid]["final"]))
# 지울리 골·도움이 있는 경기의 리포트 골 목록 점검: 2015.5.16 마리냔전만 해당(목록 3-1, 최종 4-1, 하프타임 2-1 = 43분 골 뒤 2-1이므로 빠진 골은 후반 → 골 전 0-2 그대로)
GA_GAMES = {r[1] for r in raw_rows}
SM_GA = [x for x in SCORE_MISMATCH if x[0] in GA_GAMES]
if {x[0] for x in SM_GA} - {"4723641"}: sys.exit("골·도움 경기 리포트 불완전 " + str(SM_GA))

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
MANUAL_ALIAS = {"inter milan": "inter", "olympique lyon": "olympique lyonnais", "lks lodz": "lks lodz"}
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
        "deportivo", "san", "santa", "saint", "us", "ogc", "losc", "stade", "racing", "athletic"}
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

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
def half_up(x): return int(x + 0.5)
SEG = [1753, 1712, 1687, 1674, 1660, 1654, 1647, 1640, 1632, 1623, 1615, 1610, 1606, 1601, 1598, 1595, 1589, 1580, 1572, 1567, 1560, 1553]  # 세군다 22팀(라울·호나우두 자료 고정값)

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
SD1 = {"FR1": 100.16, "ES1": 100.16, "IT1": 91.3}
LGNAME = {"FR1": "리그1", "ES1": "라리가", "IT1": "세리에A"}
INTERP_USED = set()
LADDER_FR1 = {}

for _n, _s in ((20, "2002-03"), (18, "2023-24")):
    _m = ents_map("리그1", _s)
    if sorted(_m) != list(range(1, _n + 1)): sys.exit("리그1 기준 순위표 불완전 " + _s)
    LADDER_FR1[_n] = [_m[i] for i in range(1, _n + 1)]

def rank_model(lg, season, r, n):
    if lg in LGNAME:
        m = ents_map(LGNAME[lg], season)
        if not m: return None
        v, it = mid(m, r)
        if v is None:
            # 끝 순위(앞이나 뒤에 기존 값이 없음): 같은 팀 수의 기존 전체 순위값(리그1 20팀 2002-03·18팀 2023-24 표)을 그대로 씀
            if lg == "FR1" and n in LADDER_FR1:
                v = LADDER_FR1[n][r - 1]; INTERP_USED.add((lg, season, r, v, "표"))
                return v, f"{LGNAME[lg]} {season} {r}위"
            v = edge(m, r, n, SD1[lg]); INTERP_USED.add((lg, season, r, v, "끝"))
            return v, f"{LGNAME[lg]} {season} {r}위 (추정, 이웃 순위값에 순위 곡선 차이)"
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"{LGNAME[lg]} {season} {r}위"
    if lg == "FR2":
        m = ents_map("리그2", season)
        v, it = mid(m, r)
        if v is None: return half_up(1540 + SD2 * curve(r, n)), f"리그2 {season} {r}위 (추정, 프랑스 2부 평균 1540 모형)"
        return v, f"리그2 {season} {r}위"
    if lg == "ES2" and n == 22:
        return SEG[r - 1], f"세군다(2부) {season} {r}위"
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
    seasons = [s0]
    if cid == "KLUB": seasons = [s0, d[:4]]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for lg in ("FR1", "ES1", "IT1", "FR2", "ES2"):
        t = RANKS.get((lg, s0), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s0, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, s0)); return 0, "?"

# ---------------------------------------------------------------- 직접 추정(모두 lv에 '추정') — judgments.md 6절
C4 = 1231      # 프랑스 4부(CFA): 주니뉴 자료 바이욘 CFA 2006-07 1231(3부 약 1311과 하부 아마추어 1150의 가운데)과 같음
C5 = 1150      # 프랑스 5부(CFA2) 이하 아마추어: 오바메양·주니뉴 자료 1150과 같음
def cfa(o, s, extra=""):
    man(o, s, C4, f"프랑스 4부(CFA) {s} (추정, 다른 선수 자료 프랑스 4부 1231과 같음{extra})")
for o in ["ASM Belfort", "FC Villefranche-Beaujolais", "Olympique Lyon B", "AS Lyon-Duchère", "AS Saint-Priest", "AS Yzeure",
          "FC Montceau Bourgogne", "FC Mulhouse", "Football Club de Vesoul", "Jura Sud Foot", "SAS Épinal", "US Raon-l'Étape", "US Sarre-Union"]:
    cfa(o, "2013-14")
for o in ["AS Béziers", "AS Lyon-Duchère", "AS Monaco B", "AS Saint-Priest", "FC Sète 34", "FC Villefranche-Beaujolais", "Grenoble Foot 38",
          "Hyères FC", "Montpellier HSC B", "OGC Nice B", "Rodez AF", "US Le Pontet", "US Marignane"]:
    cfa(o, "2014-15")

man("Trélissac FC", "1994-95", C5, "프랑스 하부 아마추어 1994-95 (추정, 디비전 확인 못 함; 다른 선수 자료 프랑스 하부 아마추어 1150과 같음)")
man("SC Farense", "1995-96", 1560, "포르투갈 1부 1995-96 10위 (추정, 다른 선수 자료 포르투갈 1부 18팀 시즌 10위 1560과 같음)")
man("Rapid Bucharest", "1997-98", 1500, "루마니아 1997-98 2위 (추정, 다른 선수 자료 루마니아 2위 1500과 같음)")
man("Istanbulspor", "1997-98", 1620, "튀르키예 1997-98 4위 (추정, 다른 선수 자료 베식타시 2000-01 4위 1620과 같음)")
man("Grazer AK", "1998-99", 1480, "오스트리아 1998-99 3위 (추정, 다른 선수 자료 그라츠 AK 2003-04·2004-05 1480과 같음)")
man("Widzew Lodz", "1999-00", 1450, "폴란드 1999-00 7위 (추정, 다른 선수 자료 폴란드 1부 6위 루흐 호주프 2000-01 1450과 같음)")
man("AEK Athens", "1999-00", 1550, "그리스 1999-00 3위 (추정, 다른 선수 자료 AEK 2001-02~2003-04 1550과 같음)")
man("Zamora CF", "2005-06", 1350, "스페인 3부(세군다 B) 2005-06 (추정, 2부 순위표에 없음; 다른 선수 자료 스페인 3부 1350과 같음)")
man("Football Club de Vesoul", "2009-10", C4, "프랑스 4부(CFA) 2009-10 (추정, 다른 선수 자료 프랑스 4부 1231과 같음)")
man("Maccabi Tel Aviv", "2010-11", 1480, "이스라엘 2010-11 3위 (추정, 다른 선수 자료 하포엘 텔아비브 2010-11 2위 1500보다 조금 낮게)")
man("FC Istres Ouest Provence", "2013-14", 1480, "프랑스 리그2 2013-14 19위")

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

# ---------------------------------------------------------------- FotMob 골 대조(2010~13)
FM_CMP = []; FM_N = 0
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    if not tm: continue
    fm = [r for r in FME[gid] if "Giuly" in r["scorer"] and r["own_goal"] not in ("1", "True")]
    FM_N += 1
    if not FME[gid] or not any(r["scorer"] for r in FME[gid]):
        FM_CMP.append(("FotMob 골 기록 없음", gid, ldate(G[gid]))); continue
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["minute"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["minute"]))):
        a = mins(t["minute"])[0]; b = int(f["minute"]) + int(f["overload"] or 0)
        if abs(a - b) > 0 and not (t["minute"].startswith("90+") and b == 90):
            FM_CMP.append(("분 다름", gid, ldate(G[gid]), t["minute"], f["minute"]))

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
        if x[0] == "a" and re.search(r"Giuly", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움→지울리 골", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_opp(x, r)]
            if hit: CROSS.append(("지울리 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
# 같은 경기 타인 골 중 TM이 지울리 도움으로 적었으나 규칙으로 뺀 것
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and (key(x[1]) == key(j[2]) or toks(x[1]) & toks(j[2])):
                    CROSS.append(("TM 지울리 도움을 규칙대로 뺀 타인 골(타인 파일에 도움 표기 없음 확인 필요)", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("lyogu", "1998-01-12", "리옹", "1994~1998"), ("mongu", "2004-07-01", "모나코", "1998~2004"),
         ("fcbgu", "2007-07-01", "바르셀로나", "2004~2007"), ("romgu", "2008-07-01", "AS 로마", "2007~2008"),
         ("psggu", "2011-07-01", "파리 생제르맹", "2008~2011"), ("mongu", "2012-07-01", "모나코", "2011~2012"),
         ("lorgu", "2013-07-01", "로리앙", "2012~2013"), ("mdogu", None, "몽도르 아제르그", "2013~2015")]
TM_CLUB = {"1041": "lyogu", "162": "mongu", "131": "fcbgu", "12": "romgu", "583": "psggu", "1158": "lorgu", "30443": "mdogu"}
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
# 모나코 두 시기 나눔(설명용)
MON2 = [0, 0, 0, 0]
for m in M:
    if club_of(m[0]) == "mongu" and m[0] >= "2011-07-01": MON2[0] += 1; MON2[3] += m[3]
for r in E:
    if club_of(r[9]) == "mongu" and r[9] >= "2011-07-01": MON2[1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({(r[9]) for r in E if len(r) > 14})
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club == "lyogu": s = y if m >= 7 else y - 1
    elif club in ("mongu", "psggu"): s = y if d[5:] >= "07-10" else y - 1
    else: s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print("모나코 2기", MON2)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    print("FotMob", FM_N, FM_CMP)
    for c in CROSS: print(c)
    print(sorted(collections.Counter(season_of(m[0], club_of(m[0])) for m in M).items()))
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
SRC = ELO_SRC
first, last = M[0], M[-1]
EXA = [j for j in judg if j[0] == "도움 제외"]
SHOT = "슈팅 리바운드('Shot on goal')"
def exa_txt(why): return ", ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]}" for j in EXA if j[5] == why)
NOTE_LINES = [
    f"뤼도비크 지울리(리옹·모나코·바르셀로나·AS 로마·파리 생제르맹·로리앙·몽도르 아제르그)의 클럽 공식 경기 {NG}경기({d_(first[0])} {first[1]}전 ~ {d_(last[0])} {last[1]}전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·프랑스 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CN[k]} {c3(v)}" for k, v in ST.items()) + f"(모나코는 1998~2004 {ST['mongu'][0]-MON2[0]}·{ST['mongu'][1]-MON2[1]}·{ST['mongu'][2]-MON2[2]}과 2011~2012 리그2 {c3(MON2)}의 합계). 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(출전한 클럽 경기 전부의 리포트, 리포트 골 170개·도움 54개가 선수 경기 성적과 경기마다 같음). 날짜는 리포트의 현지 날짜(경기 시각이 없는 53경기는 선수 경기 성적의 UTC 날짜가 하루 이름). 영어·프랑스어 위키백과 클럽·시즌별 경기·골과 대조",
    f"FotMob은 2010~2013 경기만 있어 지울리 골이 있는 {FM_N}경기를 대조함: 2010.8.26 마카비 텔아비브전 63분(FotMob 64분)·2011.2.20 니스전 24분(FotMob 25분)만 1분 다르고 나머지는 분·스코어가 같음 → Transfermarkt 분 유지. 2011.1.8 랑스전·2012.1.9 앙제전(2골) 등은 FotMob에 골 기록이 비어 있음. FotMob 경기 기록에는 이 시기 도움 자료가 없음",
    "몽도르 아제르그(4부 CFA 아마추어 클럽, 2013~2015) 39경기 16골은 1군의 공식 리그·쿠프 드 프랑스 경기라 넣음(말루다 디페르당주·라울 뉴욕 코스모스·발부에나 몰타 선례). Transfermarkt 리포트 8경기는 골 목록이 빠져 있으나 지울리 골이 있는 2015.5.16 마리냔전은 하프타임 2-1과 43분 골 뒤 2-1이 맞아 골 전 0-2를 그대로 씀. 위키백과에 있는 2014-15 쿠프 드 프랑스 1경기 2골은 Transfermarkt에 경기가 없어 넣지 않음(날짜·출전·골 시각 미확인)",
    "골: 자책골 없음. PK 골 5개는 Transfermarkt 골 유형 'Penalty'(1997.9.30 브뢴뷔전 14분, 1998.8.7 로리앙전 90분, 1999.8.14 바스티아전 87분, 2004.1.9 리옹전 90분, 2015.2.28 그르노블전 54분). 모나코 1998-99 UEFA컵 골은 Transfermarkt 3골(1998.9.15 LKS 우치전 58분·1998.10.20 그라츠 AK전 78분·1998.11.24 마르세유전 56분)이 위키백과(2골)와 다르나, fbref 골 기록·RSSSF 유럽 대회 기록·playmakerstats 경기 기록이 세 골을 모두 확인해 3골로 둠(위키백과 시즌 골 10 → 11). 리옹 1994-95 쿠프 드 프랑스 트렐리사크전 골은 프랑스어 위키백과에 없지만 Transfermarkt·영어 위키백과에 있어 넣음",
    f"도움: 2014년 8월 이전 도움은 Transfermarkt 경기 리포트 단일 출처(클로제·인시녜·주니뉴 선례). Transfermarkt 도움 54개에서 슈팅 리바운드('Shot on goal') 5개({exa_txt(SHOT)})와 상대 자책골에 준 도움 2개({exa_txt('상대 자책골 유도')})를 빼 {NA}개. 도움 유형 칸이 빈 {UNTYPED}개는 일반 도움으로 셈. 본인 PK 골에 본인을 도움으로 적은 표기와 PK 유도 도움은 없음. Transfermarkt는 리옹(1994~1998) 도움이 0개, 모나코 1998~2004 도움이 10개뿐이라 실제보다 적을 수 있음(프랑스어 위키백과 도움 칸은 모나코 1997~2004 약 45개, 바르셀로나 10개(Transfermarkt 16), 로마 3개(4)로 출처마다 크게 다르고 경기별 근거가 없어 쓰지 않음)",
    "출전 분: Transfermarkt 그대로(빈칸 없음, 추정한 경기 없음). 연장 경기는 Transfermarkt 출전 분(연장 포함), 연장 없이 승부차기로 끝난 경기는 90분 기준. 연장 골: 2000.1.29 쿠프 드 라 리그 16강 스트라스부르전 110분(76분 교체 투입), 2010.10.27 쿠프 드 라 리그 16강 리옹전 101분(78분 교체 투입)",
    "넣지 않은 기록: 리옹 1994-95 출전하지 않은 명단 경기, 2016.8.20 몽도르 CFA 경기(명단 제외), 프랑스 대표팀 경기. 위키백과와의 차이: 프랑스어 위키백과는 모나코 1997-98 14경기(Transfermarkt·영어 위키백과 16), 리옹 1997-98 쿠프 드 라 리그 2경기(Transfermarkt·영어 위키백과 1), 바르셀로나 2006-07 코파 델 레이 1경기(Transfermarkt·영어 위키백과 7)로 적어 Transfermarkt를 따름",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(에투·호나우지뉴·메시·이니에스타·토티), 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 순위값·리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['기존 팀×시즌 값']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "리그1(1994-95~2012-13)은 그 시즌 기존 순위값에 순위를 넣고, 빈 순위는 앞뒤 기존 값의 가운데(직선 보간), 앞이나 뒤에 기존 값이 없는 끝 순위는 같은 팀 수 시즌의 기존 전체 순위값(20팀 2002-03, 18팀 2023-24 표; 1996-97 1위 1955·1998-99와 1999-00 2위 1866·1998-99 5위 1771·1999-00 14위 1647)을 씀. 리그2는 기존 순위값, 없으면 평균 1540 모형. 라리가·세리에A는 같은 경기·같은 팀·시즌 기존 값, 세군다(2부)는 22팀 고정값(알라베스 2006-07 17위)",
    "직접 추정(모두 '추정'): " + ", ".join(f"{o} {e}" for o, e, lv in MAN_USED if e != C4) + f"; 4부(CFA) 상대(몽도르 시기 리그 상대·리옹 B·모나코 B·몽펠리에 B 등 2군 팀 포함, 2009-10 쿠프 드 프랑스 브줄)는 모두 {C4}(주니뉴 자료 바이욘 CFA 값과 같음). 트렐리사크 1994-95는 디비전을 확인하지 못해 하부 아마추어 1150. 이스트르 2013-14는 다른 선수 자료의 리그2 19위 1480을 그대로 씀. 순위 근거: 라피드 부쿠레슈티 1997-98 루마니아 2위(영어 위키백과·RSSSF), 브줄 2009-10 CFA(경기 기사), 사모라 2005-06은 세군다 순위표에 없어 3부로 봄",
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·코파 델 레이·코파 이탈리아는 국내컵(16강까지·8강·준결승·결승), 트로페 데 샹피옹·수페르코파(스페인 두 경기)·수페르코파 이탈리아나·UEFA 슈퍼컵은 국내컵 결승 비중, 클럽 월드컵 2006(준결승·결승)은 클럽 월드컵 비중 단판. UEFA컵 1라운드·인터토토컵(조별·준결승·결승)·유로파 플레이오프는 유로파 예선, UEFA컵·유로파 조별은 유로파 조별, UEFA컵 2·3라운드·16강·8강과 유로파 32강·16강은 유로파 토너먼트. 챔스 조별·16강·8강·준결승·결승",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·인터토토컵은 원정 다득점·연장(인터토토컵은 램파드 선례 가정), 코파 델 레이·수페르코파·코파 이탈리아는 원정 다득점·연장(에투·호나우지뉴·토티 자료와 같음). 못 뛴 다른 차전 스코어는 Transfermarkt 리포트로 채움",
    "시즌 구분: 리옹은 7월 1일 기준(1997.7.5 인터토토컵 조별 경기가 1997-98, 지단 보르도 선례), 모나코·파리 생제르맹은 7월 10일 기준(1999.7.30·2001.7.28 리그1 개막전, 2000.7.22·2010.7.28 트로페 데 샹피옹이 새 시즌), 바르셀로나·로마·로리앙·몽도르는 기본 8월 1일. 클럽 구분: 1998.1.12 전 리옹(마지막 경기 1998.1.10, 모나코 첫 경기 1998.1.17), 2004.7.1 전 모나코, 2007.7.1 전 바르셀로나, 2008.7.1 전 로마, 2011.7.1 전 파리 생제르맹, 2012.7.1 전 모나코(두 번째 시기, 같은 클럽으로 묶음), 2013.7.1 전 로리앙, 이후 몽도르(경기 클럽과 경계 불일치 0)",
    "같은 경기 동료 자료: 바르셀로나 시기 에투(지울리 도움→에투 골 5, 에투 도움→지울리 골 4)·호나우지뉴(호나우지뉴 도움→지울리 골 8, 지울리 도움→호나우지뉴 골 1)·메시(지울리 도움→메시 골 1)·이니에스타(이니에스타 도움→지울리 골 1), 로마 토티(2008.1.16 토리노전 지울리 도움→토티 골)와 날짜·분·골 전 스코어·대회·상대 Elo·수준 설명·합산이 모두 같음. Transfermarkt가 지울리 도움으로 적었지만 슈팅 리바운드라 뺀 3골(2005.1.29 세비야전 호나우지뉴, 2005.9.11 마요르카전 에투, 2006.12.14 클럽 월드컵 아메리카전 호나우지뉴)은 그 선수 자료에도 도움 표기가 없음. 상대 팀 선수 자료(라울·지단·호나우두·피구 2004 챔스 8강, 드로그바·말루다·카카·파예·토레스·비야)와 골 순서도 맞음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 챔스 2005-06, 라리가 2004-05·2005-06, 리그1 1999-00, 쿠프 드 프랑스 2009-10, 코파 이탈리아 2007-08, 쿠프 드 라 리그 2002-03, 수페르코파 2005·2006, 수페르코파 이탈리아나 2007, 트로페 데 샹피옹 2000, 인터토토컵 1997(리옹). 챔스 2003-04 준우승. 대표팀(컨페더레이션스컵 2003)은 뺌. 클럽 월드컵 2006·UEFA 슈퍼컵 2006은 준우승이지만 Transfermarkt 업적에 없어 넣지 않음",
    "은퇴: 2013.5.11 프로 은퇴 발표(영어 위키백과) 뒤 아마추어 몽도르에서 뛰었고, 마지막 클럽 공식 경기는 2015.11.14 쿠프 드 프랑스 그르노블전. Transfermarkt는 2017.7.1 은퇴로 표시",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elk", "elq", "cwc", "MAN", "csa", "lib"]:
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
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
    if r[4] > 90 and not r[10] and not r[11]: problems.append(("90분 넘는데 표기 없음", r))
mm_ = {m[0]: m for m in M}
Gst = {ldate(g): g for g in GAMES}
SUBIN = {}
for r in rd("tm_giuly_subs_cards.csv"):
    if r["kind"] == "sub_IN": SUBIN[r["gameId"]] = int(r["minute"])
for r in E:
    m = mm_.get(r[9]); g = Gst[r[9]]
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    start = 0 if g["isStarting"] == "True" else SUBIN.get(g["gameId"])
    if start is None: problems.append(("교체 시각 없음", r[9]))
    elif not (start - 1 <= r[4] <= start + m[3] + 6): problems.append(("출전 구간 밖 기록", r[9], r[4], start, m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const GIU_E={J(E)};\nconst GIU_M={J(M)};\nconst GIU_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
