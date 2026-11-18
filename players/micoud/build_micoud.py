#!/usr/bin/env python3
"""요한 미쿠 (Transfermarkt 2713): raw/ -> micoud.json + src/data/mic.js (판정 근거는 judgments.md)

  python3 players/micoud/build_micoud.py            # 파일 쓰기
  python3 players/micoud/build_micoud.py --debug    # Elo 출처 로그만 출력
  python3 players/micoud/build_micoud.py --stat     # 요약·동료/상대 자료 대조
  python3 players/micoud/build_micoud.py --ties     # 합산 행·판정 출력

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/ranks.txt(Transfermarkt 순위표), elo/opponent_elo_by_team_season.csv + aliases.csv,
      src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
FotMob에는 이 선수 자료가 없음(raw/fotmob/search_attempts.txt). 뼈대는 로텐 build_rothen.py(프랑스 클럽, 같은 raw 형식).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "mic.js")
OUT_JSON = os.path.join(HERE, "micoud.json")
ME = "2713"
ME_KO = "요한 미쿠"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

def ldate(g): return g["date_local_computed"]     # 리포트가 있는 283경기는 리포트 날짜와 모두 같음(raw 점검)
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"              # 모든 도움이 이 날짜 전 → Transfermarkt 리포트 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "FR2", "IT1", "L1", "FRR1"}     # FRR1 = 1993 디비지옹 1·2 승강 플레이오프(리그 비중, 오케스트레이터 지시·아일톤 고이아스 선례)
CUPS = {"FRC", "FRL", "DFB", "CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                                           # 1~6라운드·16강
    if cid == "LPO":                                          # DFB-리가포칼: 첫 경기 dk, 준결승 dsf, 결승 df(클로제·아일톤 선례)
        if r.startswith("semi"): return "dsf"
        if r.startswith("intermediate"): return "dk"
        if r.startswith("final"): return "df"
    if cid == "FRCH": return "df"                             # 트로페 데 샹피옹 = 국내컵 결승 비중
    if cid == "UI": return "elq"                              # 인터토토컵 = 유로파 예선(지단·로텐 선례)
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"                # 1999-2000 2차 조별 포함(지단 선례)
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"
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
def tie_rule(cid):
    """(원정 다득점, 연장)"""
    if cid in ("UEFA", "CL", "CLQ", "UI"): return (1, 1)      # UEFA 대회 2020-21까지
    if cid == "CIT": return (1, 1)                            # 코파 이탈리아 2021-22까지 원정 다득점·연장(문서 3절)
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
    ag, et = tie_rule(g["competitionId"])
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
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t.startswith("Deflect"): return "굴절"
    return None

# 리포트 골 목록이 불완전한 경기의 골 전 스코어(judgments.md 4절): 2000.1.22 실티카임전은 전반 0:1(리포트 머리)이라
# 41분 골 전 0-0 확정. 1997.1.17 브리브전(1:3 연장)은 홈 골 시각이 없어 리포트 순서대로 0-0으로 둠(확인 못 함).
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
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + gid)
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
    fh, fa = map(int, MI[gid]["final"].split(":"))
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
GA_GAMES = {r[1] for r in raw_rows}
SM_GA = [x for x in SCORE_MISMATCH if x[0] in GA_GAMES]
if sorted(x[0] for x in SM_GA) != ["2998014", "3931049"]: sys.exit("골·도움 경기 리포트 불완전 " + str(SM_GA))

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
MANUAL_ALIAS = {"olympique lyon": "olympique lyonnais", "ac parma": "parma"}
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
    if b in ("hon.js", "mic.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "foot", "ball",
        "atletico", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss", "olympique", "milan", "inter", "madrid", "fk", "if",
        "deportivo", "san", "santa", "saint", "us", "ogc", "losc", "stade", "racing", "athletic", "union", "sportive", "vfb", "vfl",
        "borussia", "hsc", "rsc", "tsv", "bayer", "eintracht", "vienna", "moscow", "zurich", "munich", "prague", "praha", "lyon"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, collections.Counter((x[2], x[12]) for b, x in cand)

# ---------------------------------------------------------------- 순위표 + 리그 순위값
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[2] == "?": continue
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
INTERP_USED = set()
LADDER_FR1 = {}
for _n, _s in ((20, "2002-03"), (18, "2023-24")):
    _m = ents_map("리그1", _s)
    if sorted(_m) != list(range(1, _n + 1)): sys.exit("리그1 기준 순위표 불완전 " + _s)
    LADDER_FR1[_n] = [_m[i] for i in range(1, _n + 1)]

def rank_model(lg, season, r, n):
    if lg == "FR1":
        m = ents_map("리그1", season)
        v, it = mid(m, r)
        if v is None:
            v = LADDER_FR1[n][r - 1]; INTERP_USED.add((lg, season, r, v, "표"))
            return v, f"리그1 {season} {r}위"
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"리그1 {season} {r}위"
    if lg == "FR2":
        if season == "1992-93":   # 두 조(18팀씩) 시절: 지단 자료(뮐루즈 1992-93 11위/18팀 1520)와 같은 조 순위 모형
            v = half_up(1540 + SD2 * curve(r, n)); INTERP_USED.add((lg, season, r, v, "조 모형"))
            return v, f"리그2 1992-93 {r}위/18팀 (추정: 프랑스 2부 모형, 두 조 시절 조 순위)"
        m = ents_map("리그2", season)
        v, it = mid(m, r)
        if v is None:
            v = half_up(1540 + SD2 * curve(r, n)); INTERP_USED.add((lg, season, r, v, "모형"))
            return v, f"리그2 {season} {r}위 (추정, 프랑스 2부 평균 1540 모형)"
        if it: INTERP_USED.add((lg, season, r, v))
        return v, f"리그2 {season} {r}위"
    if lg in ("L1", "IT1"):
        pre = "분데스리가" if lg == "L1" else "세리에A"
        m = ents_map(pre, season)
        if r not in m: sys.exit("순위값 없음 " + lg + season + str(r))
        return m[r], f"{pre} {season} {r}위"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# ---------------------------------------------------------------- 직접 추정(모두 lv에 '추정') — judgments.md 6절
MAN, MAN_NOTE = {}, {}
def man2(o, s, e, lv, why): MAN[(key(o), s)] = (e, lv); MAN_NOTE[(key(o), s)] = why
man2("Fenerbahce", "1994-95", 1640, "튀르키예 1994-95 4위 (추정, 1990년대 다른 선수 자료 튀르키예 4위 1640과 같음)",
     "TM TR1 1994-95 표 4위(우승 베식타시); 다른 선수 자료 페네르바체 1996-97 3위 1650(2위 1660·4위 1640의 가운데)")
man2("Grasshopper Club Zurich", "1998-99", 1600, "스위스 1998-99 2위 (추정, 다른 선수 자료 스위스 1·2위 1600과 같음)",
     "en.wikipedia·RSSSF 1998-99 Nationalliga A: 우승 세르베트, 그라스호퍼 2위(챔피언십 라운드 46점 동률). TM 표의 1위는 1단계 순위")
man2("Spartak Moscow", "1999-00", 1600, "러시아 1999 1위 (추정, 다른 선수 자료 스파르타크 모스크바 1위 1600과 같음)",
     "1999 러시아 리그 우승(TM RU1 1999 1위); 1999.9~10 챔스 조별 = 그 해 시즌(달력 연도)")
man2("Pobeda Prilep", "2000-01", 1300, "북마케도니아 2000-01 (추정, 1999-2000 2위로 출전, 다른 선수 자료 북마케도니아 1300과 같음)",
     "RSSSF·en.wikipedia 1999-2000 Macedonian First League 2위(우승 슬로가 유고마그나트); TM 표 없음(INVALID)")
man2("Tampere United", "2007-08", 1400, "핀란드 2007 1위 (추정, 다른 선수 자료 핀란드 1위 1400과 같음)",
     "TM FI1 2007 1위(우승); 기존 HJK 2011 1위·KuPS 1위 1400")
man2("Austria Vienna", "2007-08", 1480, "오스트리아 2007-08 3위 (추정, 다른 선수 자료 오스트리아 3위 1475~1508 사이, 그라처 AK 1998-99 3위 1480과 같음)",
     "TM A1 2007-08 3위(우승 라피트 빈)")
man2("SSV Jahn Regensburg", "2004-05", 1450, "독일 3부(레기오날리가 남부) 2004-05 8위 (추정, 다른 선수 자료 독일 3부 1450과 같음)",
     "TM RS 2004-05 8위/18팀; DFB-포칼 상대")
man2("AC Venezia 1907", "2000-01", 1620, "세리에B 2000-01 4위 (추정, 다른 선수 자료 세리에B 4위 1620과 같음)",
     "TM IT2 2000-01 4위/20팀; 다른 선수 자료 세리에B 1993-94·1994-95·1998-99 4위 1620")
man2("ESA Brive", "1996-97", 1311, "프랑스 3부(나시오날 1) 1996-97 (추정, 순위 미확인, 다른 선수 자료 프랑스 3부 약 1311과 같음)",
     "fr.wikipedia 쿠프 드 프랑스 1996-97 문서 '(Nat.1)'; 순위표 못 구함")
man2("Stade Poitevin PEPP", "1997-98", 1330, "프랑스 3부(나시오날) 1997-98 7위 (추정, 다른 선수 자료 프랑스 3부 7위 1330과 같음)",
     "fr.wikipedia 'Championnat de France de football de troisième division 1997-1998' 7위/18팀(시즌 뒤 행정 강등)")
man2("SC Schiltigheim", "1999-00", 1150, "프랑스 5부(CFA 2) 1999-00 (추정, 다른 선수 자료 프랑스 5부 1150과 같음)",
     "fr.wikipedia 쿠프 드 프랑스 1999-2000 문서 '(CFA2)'")
man2("US Quevilly", "2007-08", 1220, "프랑스 4부(CFA) 2007-08 (추정, 다른 선수 자료 프랑스 4부 1220과 같음)",
     "fr.wikipedia 쿠프 드 프랑스 2007-08 문서 '(CFA)'")

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; SAME_MULTI = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if vals:
        if len(vals) > 1: SAME_MULTI.append((o, d, dict(vals)))
        (e, lv), _ = vals.most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    k = key(o); s0 = eu(d)
    if (k, s0) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, s0)]).most_common(1)[0]
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s0); return e, lv
    if (k, s0) in MAN:
        e, lv = MAN[(k, s0)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for lg in ("FR1", "FR2", "FR2#group1", "FR2#group2", "L1", "IT1"):
        t = RANKS.get((lg, s0), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg.split("#")[0], s0, r, n)
            if res:
                ELO_SRC["순위표+리그 순위값"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], (lg, s0, r, n)); return res
    MISS.append((o, d, cid, s0)); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (mi > 90 and g["gameState"] in ("extra_time", "penalty_shootout") and not str(dm).startswith("90+")) else 0
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

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or ((a[14] if len(a) > 14 else 0) or 0) != ((b[14] if len(b) > 14 else 0) or 0): d.append(f"단판/합산 {a[7]}{a[14] if len(a) > 14 else ''}/{b[7]}{b[14] if len(b) > 14 else ''}")
    if a[10] != b[10]: d.append(f"연장 {a[10]}/{b[10]}")
    if a[8] != b[8]: d.append("PK")
    return d
def same_opp(x, r): return key(x[1]) == key(r[1]) or bool(toks(x[1]) & toks(r[1]))
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Micoud", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움→미쿠 골", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_opp(x, r)]
            if hit: CROSS.append(("미쿠 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
TEAMN = {"895": "AS Cannes", "40": "FC Girondins Bordeaux", "130": "Parma", "86": "SV Werder Bremen"}
for r in E:
    g = [x for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
    for b, (oe, om) in OTHERS.items():
        for x in oe:
            if x[9] == r[9] and toks(x[1]) & toks(TEAMN[g["club_id"]]):
                CROSS.append(("상대 팀 선수 같은 경기 기록(스코어 대조용)", b, r[9], x[0], x[4], x[5], x[6], "미쿠 행", r[0], r[4], r[5], r[6]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_opp(x, [0, j[2]]):
                    CROSS.append(("TM 미쿠 도움을 규칙대로 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("canmc", "1996-07-01", "AS 칸", "1992~1996"), ("bdxmc", "2000-07-01", "보르도", "1996~2000"),
         ("parmc", "2002-08-30", "파르마", "2000~2002"), ("svwmc", "2006-07-01", "베르더 브레멘", "2002~2006"),
         ("bdxmc", None, "보르도", "2006~2008")]
TM_CLUB = {"895": "canmc", "40": "bdxmc", "130": "parmc", "86": "svwmc"}
def club_of(d):
    for k, u, n, y in CLUBS:
        if u is None or d < u: return k
CN = {}
for k, u, n, y in CLUBS: CN.setdefault(k, n)
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
# 시기별 합계(보르도 두 시기 따로)
PER = collections.OrderedDict()
def per_of(d):
    for i, (k, u, n, y) in enumerate(CLUBS):
        if u is None or d < u: return i
for i, (k, u, n, y) in enumerate(CLUBS): PER[i] = [0, 0, 0, 0]
for m in M: PER[per_of(m[0])][0] += 1; PER[per_of(m[0])][3] += m[3]
for r in E: PER[per_of(r[9])][1 if r[0] == "g" else 2] += 1
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CN)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({(r[9]) for r in E if len(r) > 14})
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
N_TM_A = sum(int(g["assists"]) for g in GAMES)
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club == "canmc": s = y if m >= 7 else y - 1
    elif club in ("bdxmc", "svwmc"): s = y if d[5:] >= "07-10" else y - 1
    else: s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
if "--stat" in sys.argv:
    for k, v in PER.items(): print(CLUBS[k][0], CLUBS[k][3], v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), "TM 도움", N_TM_A, "유형 공란", UNTYPED)
    for c in CROSS: print(c)
    print(sorted(collections.Counter(season_of(m[0], club_of(m[0])) for m in M).items()))
    for j in judg: print(j)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
SRC = ELO_SRC
first, last = M[0], M[-1]
EXA = [j for j in judg if j[0] == "도움 제외"]
EXA_PK = [j for j in EXA if j[5] == "PK 유도"]; EXA_OG = [j for j in EXA if j[5] == "상대 자책골 유도"]
if len(EXA_PK) + len(EXA_OG) != len(EXA): sys.exit("도움 제외 사유 확인")
PKS = [r for r in E if r[0] == "g" and r[8]]
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
PER_TXT = ", ".join(f"{CLUBS[i][2]}({CLUBS[i][3]}) {c3(v)}" for i, v in PER.items())
PER_MIN = ", ".join(f"{CLUBS[i][2]}({CLUBS[i][3]}) {v[3]:,}분" for i, v in PER.items())
NOTE_LINES = [
    f"요한 미쿠(AS 칸·보르도·파르마·베르더 브레멘·보르도)의 클럽 공식 경기 {NG}경기({d_(first[0])} {first[1]}전 ~ {d_(last[0])} {last[1]}전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·프랑스 대표팀 제외",
    f"클럽별 경기·골·도움: {PER_TXT}(보르도 합계 {c3(ST['bdxmc'])}). 출전 분 합계 {MIN_TOT:,}분({PER_MIN})",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부, 리포트 골·도움 수가 선수 경기 성적과 경기마다 같음). FotMob에는 이 선수 자료가 없어(2008년 은퇴) Transfermarkt가 경기별 유일한 출처이고, 경기 수·골은 영어·프랑스어 위키백과 클럽·시즌별 기록과 대조함. 출전 분이 없어 90분으로 추정한 경기는 없음",
    "범위: 유스·2군 경기 없음(Transfermarkt 기록 없음). AS 칸 1992-93은 디비지옹 2(프랑스 2부 프로 리그) A조 2위로, 1993.5.21~6.9 디비지옹 1·2 승강 플레이오프 5경기(1골)를 거쳐 승격함 — 플레이오프는 리그 비중·단판으로 계산함(두 경기 합산 아님). 나머지 시즌은 모두 1부",
    "출처 간 차이: 칸 146경기 21골은 프랑스어 위키백과 147경기 20골·영어 위키백과 139경기 19골과 다름 — 영어판은 1993 승강 플레이오프 5경기(1골)와 1995 인터토토컵 2경기를 빼고, 프랑스어판은 1992-93 쿠프 드 프랑스를 2경기로 적음(Transfermarkt는 1993.3.30 포 FC전 '명단 제외'). 1993-94 디비지옹 1 골은 Transfermarkt 4골(1993.8.11 릴전·9.11 앙제전·1994.1.29 소쇼전·4.29 낭트전)·위키백과 3골로, 어느 골이 다른지 경기별 근거가 없어 Transfermarkt를 따름. 보르도 1999-2000 트로페 데 샹피옹(1999.7.24 낭트전)은 Transfermarkt·프랑스어판에 있고 영어판에 없음. 파르마 2001-02 코파 이탈리아는 Transfermarkt 6경기·프랑스어판 7경기(Transfermarkt는 2002.1.9 우디네세전·1.31 브레시아전 '명단 제외'). 브레멘 169경기 47골·보르도 2006~2008 81경기 13골은 위키백과와 같음",
    f"골: 자책골 없음. PK 골 {NPK}개는 Transfermarkt 골 유형 'Penalty'(" + ", ".join(f"{d_(r[9])} {r[1]}전 {r[4]}분" for r in PKS) + "). 놓친 PK 3개(2002.9.10 뉘른베르크전, 2005.8.24 바젤전, 2005.12.18 함부르크전)는 기록에 영향 없음. 연장 골: 1998.2.18 쿠프 드 라 리그 8강 스타드 푸아트뱅전 105분, 2003.10.28 DFB-포칼 볼프스부르크전 95분",
    f"도움: 모두 2014년 8월 전이라 Transfermarkt 경기 리포트 단일 출처를 씀(클로제·인시녜·지울리·로텐 선례). Transfermarkt 도움 {N_TM_A}개에서 PK 유도 {len(EXA_PK)}개(" + ", ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]} PK 골" for j in EXA_PK) + f")와 상대 자책골에 준 도움 {len(EXA_OG)}개(" + ", ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]} 자책골" for j in EXA_OG) + f")를 빼 {NA}개. 도움 유형 칸이 빈 {UNTYPED}개는 PK 유도·슈팅 리바운드 여부를 확인할 수 없어 일반 도움으로 셈(토티·디 나탈레 선례). 슈팅 리바운드·굴절·본인 PK 골 본인 도움 표기는 없음",
    "도움이 실제보다 적을 수 있음: Transfermarkt 리포트는 1990년대 도움 기록이 드묾(칸 1992-93·1995-96 골 기록에 도움자가 하나도 없고, 보르도 1996-97·1997-98 미쿠 도움 0개). 프랑스어 위키백과 시즌 도움 합계는 보르도 1996-97 3개·1997-98 12개(그 시즌 디비지옹 1 도움 1위)·1998-99 8개·1999-2000 6개로 Transfermarkt(0·0·5·3)보다 많지만 어느 경기의 도움인지 알 수 없어 더하지 않음. Transfermarkt 도움 수(제외 전)와 비교하면 칸 12·보르도 2006~08 8개는 위키백과와 같고, 파르마는 위키백과 8개·Transfermarkt 10개, 브레멘은 위키백과 55개·Transfermarkt 60개",
    "Transfermarkt 리포트 골 목록이 빠진 쿠프 드 프랑스 경기: 2000.1.22 SC 실티카임전(1-3)은 홈 팀 골 시각이 없지만 전반 0-1(리포트 머리)이라 미쿠 41분 골 직전 0-0이 맞음. 1997.1.17 ESA 브리브전(1-3, 연장)은 브리브 골(정규시간)의 시각이 없어 미쿠 78분 골 직전 스코어를 리포트 순서대로 0-0으로 둠(실제로는 0-1이었을 수 있음, 경기 기사를 찾지 못해 확인 못 함). 1997.2.8 툴루즈 퐁텐전·2000.2.12 포르토 베키오전도 골 하나가 빠졌지만 미쿠 골·도움이 없어 영향 없음",
    "출전 분: Transfermarkt 그대로(퇴장 5경기: 1993.1.23 바스티아전, 1993.9.11 앙제전, 1995.7.8 파룰 콘스탄차전, 1995.10.4 갱강전, 2002.9.21 레버쿠젠전). 날짜는 경기 현지 날짜(모두 유럽 경기, Transfermarkt 리포트 날짜와 같음). 승부차기 6경기의 승부차기 골은 넣지 않음",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(아일톤·클로제·지단 등), 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 리그 순위값에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['기존 팀×시즌 값']}, 순위표+순위값 {SRC['순위표+리그 순위값']}, 직접 {SRC['직접 추정']})",
    "리그 순위값: 디비지옹 1·리그1은 같은 시즌 다른 선수 자료 순위값(빈 순위는 앞뒤 값의 가운데, 끝 순위는 같은 팀 수 리그1 순위값 표), 분데스리가 2002~2006·세리에A 2000~2002는 같은 시즌 다른 선수 자료 순위값. 디비지옹 2 1992-93(두 조 18팀씩)은 프랑스 2부 평균 1540 모형에 조 순위를 넣은 추정(지단 자료와 같은 방식: 이스트르 A조 8위·루앙퀴소 A조 12위·렌 B조 2위), 디비지옹 2 1995-96 페르피냥 8위·1997-98 르망 6위(22팀)는 같은 모형 추정. 순위표+순위값으로 넣은 순위는 모두 영어 위키백과 시즌 문서 최종 순위와 같음",
    "직접 추정(모두 '추정'): " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED) + ". 순위 근거: Transfermarkt 순위표, 스위스 1998-99(영어 위키백과·RSSSF: 세르베트 우승, 그라스호퍼 2위), 마케도니아 1999-2000(RSSSF: 포베다 2위), 프랑스 3~5부 소속은 프랑스어 위키백과 대회·리그 시즌 문서(브리브 1996-97 순위는 못 찾음)",
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·DFB-포칼·코파 이탈리아는 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), DFB-리가포칼은 첫 경기·준결승·결승을 국내컵 8강·준결승·결승으로, 트로페 데 샹피옹은 국내컵 결승으로 계산함. 인터토토컵(1995 조별·2003 3라운드·준결승)과 UEFA컵 1라운드는 유로파 예선, UEFA컵 조별은 유로파 조별, UEFA컵 2·3라운드·32강·16강·8강은 유로파 토너먼트, 챔스 예선 3라운드는 챔스 예선, 챔스 조별(1999-2000 2차 조별 포함)·16강",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(UEFA 대회·코파 이탈리아: 원정 다득점·연장 있음; 2002 코파 이탈리아 결승은 합계 2-2 원정 다득점으로 파르마 우승). 다른 차전 스코어는 Transfermarkt 경기 성적·리포트",
    "시즌 구분: 칸은 7월 1일 기준(1995.7.8·7.15 인터토토컵 조별, 1993.7.24·1994.7.29·1995.7.19 디비지옹 1 개막 경기가 새 시즌; 1993.6 승강 플레이오프는 1992-93), 보르도·브레멘은 7월 10일 기준(1999.7.24 트로페 데 샹피옹·7.30 개막, 2003.7.19~30 인터토토컵, 2004.7.29·2005.7.23·27 리가포칼이 새 시즌), 파르마는 기본 8월 1일(2001.6 세리에A·코파 이탈리아 결승은 2000-01). 클럽 구분(Transfermarkt 이적 날짜): 1996.7.1 보르도, 2000.7.1 파르마, 2002.8.30 브레멘, 2006.7.1 보르도(두 번째 시기, 같은 클럽으로 묶음)",
    "같은 경기 동료·상대 자료: 아일톤(브레멘 2002~04)·클로제(브레멘 2004~06)와 미쿠 도움→동료 골의 날짜·분·골 전 스코어·대회·상대 Elo·수준 설명이 같음. 상대 팀 선수 자료(피레스·마카이·제 호베르투·발라크·고부·말루다·키슬링·디 나탈레·델 피에로·네드베드·주니뉴)와 같은 경기 골 순서도 맞음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 디비지옹 1 1998-99(보르도), 분데스리가 2003-04(브레멘), DFB-포칼 2003-04(브레멘), 코파 이탈리아 2001-02(파르마), 쿠프 드 라 리그 2006-07(보르도), 분데스리가 도움 1위 2005-06. 선수협회(UNFP) 시상은 프랑스어 위키백과 'Trophées UNFP du football' 목록 기준 디비지옹 1 올해의 팀 1997-98·1998-99. 분데스리가 준우승 2005-06은 뺌(선례). 쿠프 드 라 리그 준우승 1996-97·1997-98, 코파 이탈리아 준우승 2000-01, 트로페 데 샹피옹 준우승 1999는 Transfermarkt 업적에 없어 넣지 않음. 프랑스어 위키백과의 디비지옹 1 도움 1위 1997-98·키커 올해의 팀은 넣지 않음. 대표팀(유로 2000)은 뺌",
    "은퇴: 마지막 클럽 공식 경기는 2008.5.4 올랭피크 마르세유전(리그1, 34분), Transfermarkt 기준 2008.7.1 은퇴",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elk", "elq", "cwc", "MAN", "csa", "lib", "lg", "clq", "clg"]:
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
for r in E:
    g = [x for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
    m = [x for x in M if x[0] == r[9] and x[1] == r[1]][0]
    if m[1] != r[1] or m[2] != r[3]: problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    dur = int(g["gameDuration"])
    if g["isStarting"] == "True": lo, hi = 0, m[3] + 8
    else: lo, hi = dur - m[3] - 8, dur + 10
    if not (lo <= r[4] <= hi): problems.append(("출전 구간 밖 기록", r[9], r[4], g["isStarting"], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const MIC_E={J(E)};\nconst MIC_M={J(M)};\nconst MIC_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "elo_sources": ELO_SRC, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()},
               "man_notes": {f"{k[0]}|{k[1]}": v for k, v in MAN_NOTE.items()}, "per_club": {CLUBS[i][0] + " " + CLUBS[i][3]: v for i, v in PER.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in PER.items(): print(" ", CLUBS[k][0], CLUBS[k][3], v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
