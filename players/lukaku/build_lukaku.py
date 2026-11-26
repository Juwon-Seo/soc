#!/usr/bin/env python3
"""로멜루 루카쿠 (Transfermarkt 96341): raw/ -> lukaku.json + src/data/luk.js (판정 근거는 judgments.md)

  python3 players/lukaku/build_lukaku.py                 # 파일 쓰기
  python3 players/lukaku/build_lukaku.py --debug         # Elo 출처 로그
  python3 players/lukaku/build_lukaku.py --stat          # 요약·동료 대조·FotMob 대조
  python3 players/lukaku/build_lukaku.py --ties          # 합산 행·판정
  python3 players/lukaku/build_lukaku.py --root=<복사본>  # 그 복사본의 src/data·elo 사용(검증용)

입력: raw/tm_games.csv(성인 경기만: 출전·분·날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv·tm_two_leg_ties.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv·fotmob_tm_map.csv(FotMob), raw/ranks.txt(Transfermarkt 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
뼈대는 나니 build_nani.py(벨한다 계열).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
GITROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "luk.js")
OUT_JSON = os.path.join(HERE, "lukaku.json")
ME = "96341"
ME_KO = "로멜루 루카쿠"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]      # 안데를레흐트 U19(비아레조)·첼시 U21(리저브 리그) 제외
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FM_MAP = {r["tm_gameId"]: r for r in rd("fotmob_tm_map.csv")}

# ---------------------------------------------------------------- 날짜
# 경기는 모두 유럽(+2022.2 아부다비 클럽 월드컵, 현지 저녁)이라 Transfermarkt 리포트 날짜 = 일정 날짜 = API UTC 날짜(원자료 README)
def ldate(g):
    if g["date_local_tm_report"]: return g["date_local_tm_report"]
    m = re.search(r"(\d\d)/(\d\d)/(\d{4})", g["date_tm_schedule"])
    if m: return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return g["date_utc"][:10]
for g in GAMES:
    m = re.search(r"(\d\d)/(\d\d)/(\d{4})", g["date_tm_schedule"])
    if m and f"{m.group(3)}-{m.group(2)}-{m.group(1)}" != ldate(g): sys.exit("날짜 불일치 " + g["gameId"])
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 판정 표
MIN_FIX = {}
MIN_EST = {}
GAP = "2014-08-01"              # 이 날짜 전 도움은 Transfermarkt 리포트 단일 출처 허용(클로제·인시녜·나니 선례)
ADD_CONFIRMED = {}
UNCONFIRMED = {
    ("2745166", "83"): "2016.8.23 리그컵 요빌 타운전 83분 코네 골: FotMob 경기 기록에 도움자 없음, ESPN 문자 중계(Opta)만 루카쿠 도움, PA 경기 기사(스카이스포츠·ESPN 게재)는 코네가 페널티 지역 앞에서 찬 골로만 적음",
}
# 2014.8 전 TM 도움이지만 경기 기사로 도움이 아니라고 본 것
EXCL_A = {
    ("2332046", "84"): "2013.12.8 아스널전 84분 데울로페우 골: 폭스스포츠(AP) 경기 기사는 루카쿠의 오버헤드킥이 공에 맞지 않은 뒤 데울로페우가 넣은 골로 적음(흘러나온 공, FotMob은 오비에도 도움)",
}
EXCL_G = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BE1", "EJPL", "ESJP", "GB1", "IT1", "TR1"}   # EJPL = 벨기에 챔피언십 플레이오프, ESJP = 2008-09 우승 결정 테스트매치(TM 표기 'playoff Europa League')
CUPS = {"CCB", "FAC", "CGB", "CIT"}
SUPER = {"USC"}
UEFA_C = {"CL", "CLQ", "EL", "USC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "df"                              # UEFA 슈퍼컵 = 국내컵 결승 비중(문서 3절)
    if cid == "KLUB": return "cwc"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round"):
            return "dk" if cid != "CCB" else ("dk" if r.startswith("quarter") else "dc")   # FA컵 6라운드 = 8강, 벨기에컵 6라운드 = 32강
        return "dc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"                # 'Group Stage' = 2024~ 리그 페이즈
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                          # 32강('Second Round'·'intermediate stage')·16강·8강(2020.8 단판 포함)
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
    if cid in ("CL", "CLQ", "EL"):
        return (1, 1) if d < "2021-07-01" else (0, 1)         # UEFA 원정 다득점 2020-21까지
    if cid == "CGB": return (1, 1) if d < "2018-07-01" else (0, 0)   # 잉글랜드 리그컵 준결승 2017-18까지 원정 다득점·연장
    if cid == "CIT":
        if "2020-06-01" <= d <= "2020-06-30": return (1, 0)   # 2019-20 준결승 2차전(재개)은 연장 없이 승부차기
        return (1, 1) if d < "2022-07-01" else (0, 1)         # 코파 이탈리아 원정 다득점 2021-22까지
    if cid == "CCB": return (1, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

TIES = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
def other_leg(gid):
    t = TIES[gid]; oid = t["other_leg_id"]
    a, b = map(int, t["other_leg_final"].split(":"))        # 리포트의 다른 차전 스코어는 이 경기 홈 팀 기준으로 적힘
    rep = (a, b) if side_of(gid) == "h" else (b, a)
    if oid in G and G[oid]["gameState"] != "penalty_shootout":
        x = tuple(map(int, G[oid]["score_club_opp"].split("-")))
        if x != rep: sys.exit("다른 차전 스코어 방향 불일치 " + gid)
    return rep

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), g["round"])
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]
# 다른 차전 방향 점검(루카쿠가 두 차전 모두 뛴 합산 경기)
for gid in TIES:
    if gid in G and "leg" in G[gid]["round"].lower(): other_leg(gid)

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

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FME.items():
    for r in evs:
        if r["lukaku_assist"] == "1":
            FM_ASSIST[gid].append(int(r["minute"]) + int(r["overloadTime"] or 0))

raw_rows, judg = [], []
SRC_A = collections.Counter()
UNDECIDED = []
USED_FM = collections.Counter()
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME and not is_og(e):
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e): judg.append(("본인 자책골(골 아님)", ldate(g), opp(g), e["minute"])); continue
        if is_a and sd != side and not is_og(e):
            sys.exit("상대 골 도움 칸에 루카쿠 " + gid)
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        k = (gid, e["minute"])
        if is_g and k in EXCL_G:
            judg.append(("골 제외", ldate(g), opp(g), e["minute"], EXCL_G[k])); continue
        if is_a:
            why = assist_reason(e) or EXCL_A.get(k)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why, e["assist_type"])); continue
            if ldate(g) >= GAP:
                base = int(e["minute"].split("+")[0])
                hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - mi) <= 3 or abs(t - base) <= 3]
                if hit and USED_FM[gid] < len(FM_ASSIST[gid]):
                    USED_FM[gid] += 1; src = "TM∩FotMob 경기 이벤트"
                elif k in ADD_CONFIRMED:
                    src = "TM + 다른 출처 2곳"
                elif k in UNCONFIRMED:
                    judg.append(("도움 제외(단일 출처 미확인)", ldate(g), opp(g), e["minute"], e["scorer"], UNCONFIRMED[k], e["assist_type"])); continue
                else:
                    UNDECIDED.append((gid, ldate(g), opp(g), e["minute"], e["scorer"], e["assist_type"], FM_ASSIST.get(gid))); continue
            else:
                src = "2014.8 전 Transfermarkt"
            SRC_A[src] += 1
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk: sys.exit("PK 판정 확인 " + gid)
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

for t in list(ADD_CONFIRMED) + list(UNCONFIRMED) + list(EXCL_A):
    if not any(x["minute"] == t[1] and x["assist_id"] == ME for x in EVS.get(t[0], [])): sys.exit("판정 표 키가 TM 도움과 맞지 않음 " + str(t))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fin = MI[gid]["final"]
    if not re.fullmatch(r"\d+:\d+", fin or ""): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), fin)); continue
    fh, fa = map(int, fin.split(":"))
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
GA_GAMES = {r[1] for r in raw_rows}
# 973662 2009.9.24 무스크롱전: 리포트 최종 스코어 '-:-'(무스크롱 기록 삭제), 골 목록 1-0·1-1·1-2는 그대로 있음
if [x for x in SCORE_MISMATCH if x[0] in GA_GAMES and x[0] != "973662"]: sys.exit("골·도움 경기 리포트 불완전 " + str(SCORE_MISMATCH))

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
MANUAL_ALIAS = {}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME_KO: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", GITROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "luk.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "foot", "ball",
        "atletico", "calcio", "sport", "cd", "ud", "rcd", "sv", "as", "ss", "olympique", "milan", "inter", "madrid", "fk", "if",
        "deportivo", "san", "santa", "saint", "us", "ogc", "losc", "stade", "racing", "athletic", "union", "sportive", "vfb", "vfl",
        "al", "spor", "jk", "sk", "cska", "moscow", "sofia", "kyiv", "dynamo", "metalurg", "nk", "krc", "hnk", "pfk", "bk", "aalborg",
        "new", "york", "vitoria", "red", "bull", "bulls", "manchester", "west", "hotspur", "wanderers", "rovers", "town", "albion",
        "rsc", "kv", "kaa", "ksc", "kvc", "royal", "brugge", "bsc", "ssc"}
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
        RANKS[(p[0].split("(")[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
# 순위 보정(공식 최종 순위; Transfermarkt 표와 다른 것)
RANK_FIX = {}

def half_up(x): return int(x + 0.5)
def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r"(?: \([^)]*현재\))? (\d+)위$")
    for e in ENTS:
        m = pat.match(e[12] or "")
        if m: c[int(m.group(1))][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
INTERP_USED = set()
def mid_lv(prefix, season, r, label_season=None):
    m = ents_map(prefix, season)
    ls = label_season or season
    if r in m: return m[r], f"{prefix} {ls} {r}위", False
    lo = [k for k in m if k < r]; hi = [k for k in m if k > r]
    if not lo or not hi: return None
    a, b = max(lo), min(hi)
    v = half_up(m[a] + (m[b] - m[a]) * (r - a) / (b - a))
    INTERP_USED.add((prefix, season, r, v))
    return v, f"{prefix} {ls} {r}위 (추정, 다른 선수 자료 같은 시즌 {a}위 {m[a]}·{b}위 {m[b]} 사이)", True

def cross_season(prefix):
    t = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + r" \d{4}-\d\d(?: \([^)]*현재\))? (\d+)위$")
    for e in ENTS:
        m = pat.match(e[12] or "")
        if m: t[int(m.group(1))][e[2]] += 1
    return {k: v.most_common(1)[0][0] for k, v in t.items()}
LG_PREFIX = {"BE1": "벨기에 1부", "GB2": "챔피언십", "GB3": "리그 원", "IT2": "세리에B", "TR1": "쉬페르리그"}
def rank_model(lg, season, r, n):
    if lg == "TR1" and season == "2026-27":
        res = mid_lv("쉬페르리그", season, r, season + " (11월 18일 현재)")
        if res: return res[0], res[1]
        return None
    if lg in LG_PREFIX:
        res = mid_lv(LG_PREFIX[lg], season, r)
        if res: return res[0], res[1]
        if lg in ("GB2", "GB3"):                                  # 잉글랜드 2·3부는 다른 선수 자료에서 순위별 값이 시즌과 무관하게 같음(리그 모형) → 다른 시즌 같은 순위 값
            cs = cross_season(LG_PREFIX[lg])
            if r in cs:
                INTERP_USED.add((lg, season, r, cs[r], "다른 시즌 같은 순위"))
                return cs[r], f"{LG_PREFIX[lg]} {season} {r}위"
    return None
RANK_LG = ["BE1", "GB2", "GB3", "IT2", "TR1"]

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    if "2020-07-01" <= d <= "2020-08-31": s = 2019                 # 코로나 재개 2020년 7~8월 경기(세리에A 막판·유로파 결승 2020.8.21) = 2019-20 상대 순위
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}; MAN_NOTE = {}
def man2(o, s, e, lv, why): MAN[(key(o), s)] = (e, lv); MAN_NOTE[(key(o), s)] = why
# 직접 추정(judgments.md 6절)
man2("Excelsior Mouscron (-2009)", "2009-10", 1277, "벨기에 1부 2009-10 기록 삭제 팀 (추정, 다른 선수 자료 같은 시즌 꼴찌 15위 1277과 같음)",
     "2009년 12월 파산으로 시즌 기록이 지워져 공식 순위가 없음(영어 위키백과 2009-10 시즌 문서). 삭제 직전 하위권")
man2("The New Saints", "2010-11", 1200, "웨일스 2010-11 2위 (추정, 다른 선수 자료 TNS 2003-05 1200과 같음)", "웨일스 프리미어리그 2010-11 2위/12팀(Transfermarkt WAL1 표)")
man2("AEK Athens", "2010-11", 1550, "그리스 2010-11 3위 (추정, 다른 선수 자료 AEK 2000년대 2·3위 1550과 같음)", "그리스 슈퍼리그 2010-11 3위/16팀(Transfermarkt GR1 표)")
man2("BSC Young Boys", "2014-15", 1609, "스위스 슈퍼리그 2014-15 2위 (추정, 다른 선수 자료 영 보이스 2015-16·2016-17 2위 1609와 같음)", "스위스 슈퍼리그 2014-15 2위/10팀(Transfermarkt C1 표)")
man2("Al-Hilal SFC", "2021-22", 1813, "사우디 프로리그 2021-22 1위", "사우디 프로리그 2021-22 우승(Transfermarkt SA1 표 1위). 값은 다른 선수 자료 사우디 1위(2018-19 알나스르·2023-24 알힐랄 등) 1813과 같은 리그 모형값")
man2("Sociedade Esportiva Palmeiras", "2021", 1671, "브라질 세리에 A 2021 3위 (추정, 브라질 1부 리그 모형)", "브라질 세리에 A 2021 3위/20팀(Transfermarkt BRA1 표). 다른 선수 자료 브라질 1부 순위값(산투스 2019 2위 1702·아바이 2019 20위 1512)이 맞는 평균 1598·흩어짐 63에 순위 곡선 3위 값 1.161")
man2("FC Sheriff Tiraspol", "2023-24", 1500, "몰도바 2023-24 1위 (추정, 다른 선수 자료 셰리프 2022-23 1위 1500과 같음)", "몰도바 수페르리가 2023-24 우승(Transfermarkt MO1N 표 1위)")
man2("Servette FC", "2023-24", 1550, "스위스 슈퍼리그 2023-24 3위 (추정, 다른 선수 자료 영 보이스 2013-14 3위 1550과 같음)", "스위스 슈퍼리그 2023-24 3위(Transfermarkt C1 챔피언십 그룹 표 3위, 우승 영 보이스)")

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; SAME_MULTI = []
def seasons_for(d, cid):
    if cid == "KLUB": return [eu(d), str(int(d[:4]) - 1)]       # 2022.2 클럽 월드컵: 남미 상대는 2021 시즌
    if cid in UEFA_C: return [eu(d), d[:4]]
    return [eu(d)]
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if vals:
        if len(vals) > 1: SAME_MULTI.append((o, d, dict(vals)))
        (e, lv), _ = vals.most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    k = key(o)
    for s0 in seasons_for(d, cid):
        if (k, s0) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s0)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s0); return e, lv
    for s0 in seasons_for(d, cid):
        if (k, s0) in MAN:
            e, lv = MAN[(k, s0)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for s0 in seasons_for(d, cid):
        for lg in RANK_LG:
            t = RANKS.get((lg, s0), {})
            if k in t:
                r, n, _ = t[k]
                r = RANK_FIX.get((lg, s0, k), r)
                res = rank_model(lg, s0, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], (lg, s0, r, n)); return res
    MISS.append((o, d, cid, seasons_for(d, cid), [(lg, s0, RANKS.get((lg, s0), {}).get(k)) for s0 in seasons_for(d, cid) for lg in RANKS if lg[1] == s0 and k in RANKS[lg]])); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(2014-08 뒤 TM 단독 도움):", u)
if MISS:
    for x in sorted(set(map(str, MISS))): print("Elo 없음:", x)
if (UNDECIDED or MISS) and "--force" not in sys.argv: sys.exit(1)

if "--debug" in sys.argv:
    print(ELO_SRC)
    for x in SAME_MULTI: print("같은 경기 값 여럿", x)
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]): print(d, o, v)
    print("보간", sorted(INTERP_USED, key=str)); sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    for j in judg: print(j)
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []; FM_N = 0
for gid in GA_GAMES:
    tm = [e for e in EVS[gid] if e["scorer_id"] == ME and not is_og(e)]
    if not tm: continue
    fm_all = FME.get(gid, [])
    if not any(r["scorer"] for r in fm_all): continue
    fm = [r for r in fm_all if r["lukaku_scorer"] == "1" and r["own_goal"] != "1"]
    FM_N += 1
    if len(tm) != len(fm): FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["minute"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["minute"]) + int(x["overloadTime"] or 0))):
        a = mins(t["minute"])[0]; b = int(f["minute"]) + int(f["overloadTime"] or 0)
        if abs(a - b) > 1 and not (t["minute"].startswith(("90+", "45+")) and int(f["minute"]) in (45, 90)): FM_CMP.append(("분 다름", gid, ldate(G[gid]), t["minute"], f["minute"], f["overloadTime"]))
        if (t["goal_desc"] == "Penalty") != (f["suffix"] == "Pen"): FM_CMP.append(("PK 표기 다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["suffix"]))

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
TEAMN = {"58": "RSC Anderlecht", "631": "Chelsea FC", "984": "West Bromwich Albion", "29": "Everton FC", "985": "Manchester United",
         "46": "Inter Milan", "12": "AS Roma", "6195": "SSC Napoli", "36": "Fenerbahce"}
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.fullmatch(r"Romelu Lukaku|Lukaku", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움→루카쿠 골", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_opp(x, r)]
            if hit: CROSS.append(("루카쿠 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
    for r in E:
        g = [x for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
        for x in oe:
            if x[9] == r[9] and toks(x[1]) & toks(TEAMN[g["club_id"]]):
                CROSS.append(("상대 팀 선수 같은 경기 기록", b, r[9], x[0], x[4], x[5], x[6], "루카쿠 행", r[0], r[4], r[5], r[6]))
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0].startswith("도움 제외") and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_opp(x, [0, j[2]]):
                    CROSS.append(("TM 루카쿠 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5], x[13]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("andrl", "2011-08-08", "안데를레흐트", "2009~2011"), ("cherl", "2012-08-10", "첼시", "2011~2012, 2013, 2021~2022"),
         ("wbarl", "2013-07-01", "웨스트브로미치", "2012~2013"), ("cherl", "2013-09-02", "첼시", "2011~2012, 2013, 2021~2022"),
         ("everl", "2017-07-10", "에버턴", "2013~2017"), ("munrl", "2019-08-08", "맨유", "2017~2019"),
         ("intrl", "2021-08-12", "인테르", "2019~2021, 2022~2023"), ("cherl", "2022-07-01", "첼시", "2011~2012, 2013, 2021~2022"),
         ("intrl", "2023-08-30", "인테르", "2019~2021, 2022~2023"), ("romrl", "2024-08-29", "로마", "2023~2024"),
         ("naprl", "2026-08-12", "나폴리", "2024~2026"), ("fenrl", None, "페네르바흐체", "2026~")]
TM_CLUB = {"58": "andrl", "631": "cherl", "984": "wbarl", "29": "everl", "985": "munrl", "46": "intrl", "12": "romrl", "6195": "naprl", "36": "fenrl"}
def club_of(d):
    for k, u, n, y in CLUBS:
        if u is None or d < u: return k
CN = collections.OrderedDict()
for k, u, n, y in CLUBS: CN.setdefault(k, n)
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
def season_of(d, club):
    y = int(d[:4])
    if club == "andrl": s = y if d[5:] >= "07-10" else y - 1          # 안데를레흐트 7월 10일 기준(2011.7.29 리그 개막 = 2011-12, 헹크 데 브라위너 선례)
    else:
        s = y if int(d[5:7]) >= 8 else y - 1
        if d[:7] == "2020-08": s = 2019                              # 2020년 8월 = 2019-20(공통 규칙)
    return f"{s}-{str(s + 1)[2:]}"
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CN)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for es in EVS.values() for e in es if e["gameId"] in G and e["assist_id"] == ME and e["scorer_id"] != ME)
N_TM_G = sum(int(g["goals"] or 0) for g in GAMES)
SEASONS = collections.Counter(season_of(m[0], club_of(m[0])) for m in M)
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), dict(SRC_A), N_TM_A, N_TM_G)
    print("FotMob 골 대조", FM_N, FM_CMP)
    for c in CROSS: print(c)
    print(sorted(SEASONS.items()))
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_lukaku import make_note
NOTE = make_note(globals())
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elk", "elq", "lg", "MAN", "clg", "elg", "cwc", "clq"]:
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
    g = [x for x in GAMES if ldate(x) == r[9] and opp(x) == r[1]][0]
    m = [x for x in M if x[0] == r[9] and x[1] == r[1]][0]
    if m[2] != r[3]: problems.append(("대회 다름", r[9], r[1], m[2], r[3]))
    dur = int(g["gameDuration"])
    if g["isStarting"] == "True": lo, hi = 0, m[3] + 8
    else: lo, hi = dur - m[3] - 8, dur + 10
    if not (lo <= r[4] <= hi): problems.append(("출전 구간 밖 기록", r[9], r[4], g["isStarting"], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const LUK_E={J(E)};\nconst LUK_M={J(M)};\nconst LUK_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "assist_sources": SRC_A,
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}, "man_notes": {f"{k[0]}|{k[1]}": v for k, v in MAN_NOTE.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} · 도움 {dict(SRC_A)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
