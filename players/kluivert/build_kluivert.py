#!/usr/bin/env python3
"""Patrick Kluivert: raw/ -> kluivert.json + src/data/klu.js (판정 근거는 judgments.md)

  python3 players/kluivert/build_kluivert.py            # 파일 쓰기
  python3 players/kluivert/build_kluivert.py --debug    # Elo 출처 로그
  python3 players/kluivert/build_kluivert.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/kluivert/build_kluivert.py --out DIR  # DIR/src/data/klu.js 로 쓰기(검증용 복사본)

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골·도움), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv,
      raw/ranks.txt(순위표), elo/opponent_elo_by_team_season.csv·aliases.csv·league_season_mean.json,
      src/data/*.js(git 추적 파일만: 같은 경기 다른 선수 자료).
피구 build_figo.py(같은 Transfermarkt 원자료 형식)를 바탕으로 함.
"""
import csv, json, os, re, sys, unicodedata, collections, subprocess
from datetime import date as Date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_ROOT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else ROOT
OUT_JS = os.path.join(OUT_ROOT, "src", "data", "klu.js")
OUT_JSON = os.path.join(HERE, "kluivert.json")
ME = "4385"
ME_KO = "파트릭 클라위버르트"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")          # 성인 클럽 경기만(아약스 U19·U21 경기는 youth_reserve_games.csv에 따로 있음 → 제외)
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

def ldate(g): return g["date_local"]          # TM 일정 날짜(현지). API UTC는 킥오프 시각 없는 경기에서 하루 앞섬
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"NL1", "IT1", "ES1", "GB1", "FR1"}
CUPS = {"NLP", "CIT", "CDR", "FAC", "CGB", "FRC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth"): return "dk"   # FA컵 6라운드 = 8강
        return "dc"
    if cid in ("NLSC", "SUC", "USC"): return "df"        # 슈퍼컵류 = 국내컵 결승 비중
    if cid == "WEPO": return "cwc"                       # 인터콘티넨털컵
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 1999~2003 2차 조별 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"           # 2004-05 조별(시어러 자료와 같음)
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 2·3라운드·32강(intermediate)·16강·8강
    if cid == "UI": return "elq"                         # 인터토토컵 2005(비야·비센테 자료와 같음)
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return 0
    if "leg" in r: return 0
    if r.startswith("group"): return 0
    return 1

def tie_rule(cid):
    """(원정 다득점, 연장) — 1990~2000년대 UEFA 대회·코파 델 레이·코파 이탈리아·수페르코파·UEFA 슈퍼컵 모두 원정 다득점·연장"""
    if cid in ("UEFA", "CL", "CLQ", "UI", "USC", "CDR", "SUC", "CIT"): return (1, 1)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]
    oid = m["other_leg_id"] or TIES_RAW[gid]["other_leg_id"]
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
    if t == "Deflected": return "굴절"
    return None

raw_rows, judg = [], []
SEQ_DIFF = []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        bh, ba = (h - 1, a) if e["side"] == "home" else (h, a - 1)
        if (bh, ba) != prev: SEQ_DIFF.append((gid, ldate(g), e["minute"], (bh, ba), prev))
        prev = (h, a)
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("자책골(상대 득점, 본인 골 아님)", ldate(g), opp(g), e["minute"])); continue
        if e["assist_id"] == ME and e["kluivert_assist_other"] != "1" and e["kluivert_scorer"] != "1":
            judg.append(("상대 골 도움 칸 표기(도움 아님)", ldate(g), opp(g), e["minute"], e["assist_type"])); continue
        is_g = e["kluivert_scorer"] == "1" and not is_og(e)
        is_a = e["kluivert_assist_other"] == "1"
        if e["kluivert_self_assist"] == "1":
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if not (is_g or is_a): continue
        gf, ga = (bh, ba) if side == "h" else (ba, bh)
        if not ((e["side"] == "home") == (side == "h")) and not (is_a and is_og(e)):
            sys.exit("득점 편 이상 " + gid + " " + e["minute"])
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk:
                if e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
                judg.append(("PK 아님(PK가 막힌 뒤 리바운드 골)", ldate(g), opp(g), e["minute"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

cnt = collections.Counter()
for r in raw_rows: cnt[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt[(gid, "g")] != int(g["goals"]): sys.exit("골 수 불일치 " + gid)
    if int(g["goals"]) and gid not in EVS: sys.exit("리포트 없음 " + gid)

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
        sys.exit("git ls-files 실패(병렬 판정 파일을 읽지 않으려고 추적 파일만 씀)")

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in tracked_data():
    b = os.path.basename(fn)
    if b in ("hon.js", "klu.js"): continue
    OTHERS[b] = load_js(fn)
BYDATE = collections.defaultdict(list)
for b, (P, oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "atletico", "calcio",
        "sport", "cd", "ud", "rcd", "sv", "as", "ss", "milan", "inter", "madrid", "ca", "fk", "sk", "ssc", "us", "balompie", "deportivo",
        "bilbao", "rotterdam", "eindhoven", "amsterdam", "athletic", "racing", "afc", "bvo", "vigo"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = []
    for b, x in BYDATE.get(d, []):
        if key(x[1]) == key(o) or toks(x[1]) & toks(o): cand.append((b, x))
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 시즌 수준(새 팀-시즌만)
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
# 순위 곡선(tools/league_era_normalize.py의 21칸 곡선과 같음)
LC = [2.51, 1.668, 1.189, 0.842, 0.664, 0.555, 0.43, 0.259, 0.079, -0.096, -0.231, -0.321, -0.412, -0.502, -0.531, -0.649, -0.814, -0.999, -1.103, -1.177, -1.378]
def cv(r, n):
    x = (r - 1) / (n - 1) * 20; i = min(19, int(x)); t = x - i
    return LC[i] + (LC[i + 1] - LC[i]) * t
LSM = json.load(open(os.path.join(ELO, "league_season_mean.json"), encoding="utf-8"))
LG_KO = {"NL1": "에레디비시", "IT1": "세리에A", "ES1": "라리가", "GB1": "프리미어리그", "FR1": "리그1"}
def half_up(x): return int(x + 0.5) if x >= 0 else -int(-x + 0.5)
def rank_model(lg, season, r, n):
    nm = LG_KO.get(lg)
    if not nm: return None
    mean = LSM["평균"][f"{nm}|{season}"]; sd = LSM["흩어짐"][nm]
    lab = f"{nm} {season} {r}위" + (f"/{n}팀" if (nm == "에레디비시" and n != 18) else "")
    return half_up(mean + sd * cv(r, n)), lab

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 다른 유럽 리그(tools/league_era_normalize.py 다른 UEFA 리그 목표 평균 + 그 나라 흩어짐 × 순위 곡선; 값은 judgments.md 6절 계산)
# (TM 이름, 시즌) -> (Elo, lv)
MAN = {
    # 기존 값이 없는 팀-시즌(순위는 영어 위키백과 시즌 문서 최종 순위표와 Transfermarkt 표가 같음).
    # 값 = tools/league_era_normalize.py 다른 UEFA 리그 목표 평균(그 시즌) + 그 나라 흩어짐 × 순위 곡선(반올림)
    ("AEK Athens", "1994-95"): (1600, "그리스 1994-95 5위/18팀 (리그 수준 추정)"),            # 1531.7 + 117.05 × 0.587
    ("Grasshopper Club Zurich", "1996-97"): (1575, "스위스 1996-97 3위/12팀 (리그 수준 추정)"),  # 1503.2 + 98.57 × 0.729 (챔피언십 라운드 최종 3위)
    ("Galatasaray", "2002-03"): (1719, "튀르키예 2002-03 2위 (리그 수준 추정)"),               # 1533.6 + 117.34 × 1.583
    ("Panionios FC", "2003-04"): (1583, "그리스 2003-04 6위 (리그 수준 추정)"),                 # 1545.9 + 117.05 × 0.316
    # 스페인 3부: 기존 자료의 스페인 3부 평탄값
    ("Club Atlético de Ceuta", "2000-01"): (1350, "스페인 3부(세군다 B 4조) 2000-01 4위 (추정, 다른 선수 자료 스페인 3부 1350과 같음)"),
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
    euro = cid in ("CL", "CLQ", "UEFA", "UI", "WEPO", "USC")
    s0 = eu(d)
    seasons = [s0, d[:4]] if euro else [s0]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for s in seasons:
        if (o, s) in MAN:
            e, lv = MAN[(o, s)]; ELO_SRC["직접 계산(다른 유럽 리그 수준)"] += 1; ELO_LOG[(o, d)] = ("man", e, lv, s); return e, lv
    for lg in ("NL1", "IT1", "ES1", "GB1", "FR1"):
        t = RANKS.get((lg, s0))
        if t and k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s0, r, n)
            if res:
                ELO_SRC["순위표+리그 시즌 수준"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], s0); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

# ---------------------------------------------------------------- 기록 행
E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    et = 1 if (g["gameState"] != "regularly_terminated" and mi > 90 and dm == 0) else 0
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
        if v[0] != "table": print(d, o, v)
    print("SEQ_DIFF", SEQ_DIFF)
    for j in judg: print("judg", j)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("ajxpkl", "1997-07-01", "아약스", "1994~1997", "Ajax", "610"), ("acmpkl", "1998-08-28", "AC 밀란", "1997~1998", "AC Milan", "5"),
         ("fcbpkl", "2004-07-21", "바르셀로나", "1998~2004", "Barcelona", "131"), ("newpkl", "2005-07-01", "뉴캐슬", "2004~2005", "Newcastle", "762"),
         ("valpkl", "2006-08-31", "발렌시아", "2005~2006", "Valencia", "1049"), ("psvpkl", "2007-08-30", "PSV", "2006~2007", "PSV", "383"),
         ("lilpkl", None, "릴", "2007~2008", "Lille", "1082")]
TM_CLUB = {c[5]: c[0] for c in CLUBS}
def club_of(d):
    for c in CLUBS:
        if c[1] is None or d < c[1]: return c[0]
ST = collections.OrderedDict((c[0], [0, 0, 0, 0]) for c in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
# 7월 경기: 발렌시아 2005.7.17~7.27 인터토토컵(→ 7월 10일 기준 시즌) 외 없음
JULY = sorted({(club_of(m[0]), m[0]) for m in M if m[0][5:7] == "07"})
if "--debug" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print("7월 경기", JULY)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    return diffs
MYG = [r for r in E if r[0] == "g"]
for b, (P, ent, om) in OTHERS.items():
    for x in ent:
        if x[0] == "a" and "Kluivert" in str(x[13]):
            hit = sorted([r for r in MYG if r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append(("동료 도움→클라위버르트 골", b, x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
for r in E:
    if r[0] != "a": continue
    sur = norm(r[13]).split()[-1]
    for b, x in BYDATE.get(r[9], []):
        if x[0] == "g" and abs(x[4] - r[4]) <= 3 and (x[5], x[6]) == (r[5], r[6]) and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])):
            CROSS.append(("클라위버르트 도움→동료 골", b, r[9], r[4], r[13], cmp_rows(r, x) or "같음"))
for b, (P, ent, om) in OTHERS.items():
    seen_d = set()
    for x in ent:
        if x[9] in seen_d: continue
        for r in E:
            if r[9] == x[9] and (key(r[1]) == key(x[1]) or toks(r[1]) & toks(x[1])):
                d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                CROSS.append(("같은 경기", b, r[9], r[1], d or "같음")); seen_d.add(x[9]); break
    mm_ = {m[0]: m for m in M}
    for m in om:
        fm = mm_.get(m[0])
        if fm and (key(fm[1]) == key(m[1]) or toks(fm[1]) & toks(m[1])):
            CROSS.append(("출전 행", b, m[0], fm[1], "같음" if fm[2] == m[2] else f"대회 {fm[2]}/{m[2]}"))
if "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
    print(collections.Counter((c[0], c[1]) for c in CROSS if c[0] != "출전 행"))

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NOTE_LINES = [
    f"파트릭 클라위버르트(아약스·AC 밀란·바르셀로나·뉴캐슬·발렌시아·PSV·릴)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 페예노르트전 ~ {d_(M[-1][0])} 툴루즈전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·네덜란드 대표팀·유소년·2군 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{c[2]}({c[3]}) {c3(ST[c[0]])}" for c in CLUBS)
    + f". 출전 분 합계 {MIN_TOT:,}분(Transfermarkt 기록, 90분으로 추정한 경기 없음)",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트. 클럽·시즌·대회별 경기 수와 골은 영어 위키백과와 모두 같음(아래 2군 컵 경기 1개만 다름). FotMob에는 클라위버르트의 클럽 경기별 자료가 없어(2010-11 이전) 골 시각·도움은 Transfermarkt 단일 출처",
    "제외한 경기: 1994.11.30 KNVB컵 16강 아약스 2군(용 아약스)-도르트레흐트'90전(90분 1골)은 Transfermarkt가 2군 팀 경기로 적고, 같은 날 아약스 1군 컵 경기(NEC전)에는 '다른 팀으로 출전'이라 적음. 위키백과(영어·네덜란드어)는 이 경기를 아약스 1994-95 컵 1경기 1골로 셈 — 2군 경기 제외 원칙에 따라 넣지 않아 위키백과 통산 479경기 206골보다 1경기 1골 적음. 1993년 아약스 U19 경기도 제외",
    "골: Transfermarkt 리포트 골 205개를 모두 씀. PK 골 11개는 골 유형 'Penalty'(선수 경기 성적의 PK 골 수와 같음). 2003.5.18 마요르카전 22분 리포트의 '클라위버르트 자책골'은 상대 득점이라 본인 골에서 뺌(73분 동점 골은 넣음). 연장전 골: 1995.8.16 요한 크루이프 스할 페예노르트전 102분(2-1 승리 결승골), 2000.4.18 챔스 8강 2차전 첼시전 104분",
    f"도움: 모두 Transfermarkt 경기 리포트 도움(2014년 이전이라 단일 출처 규칙, 경기마다 다른 출처로 대조하지 못함). 도움 {NA} = Transfermarkt 84 − PK 유도 4(1998.12.5 데포르티보·1999.3.14 에스파뇰·2000.12.10 에스파뇰 히바우두, 2002.8.28 챔스 예선 레기아 바르샤바 멘디에타) − 슈팅 리바운드('Shot on goal') 4(1999.3.7 살라망카 피구, 1999.5.22 알라베스 코쿠, 2000.4.18 첼시 45분 피구, 2001.5.13 라요 바예카노 루이스 엔리케) − 상대 자책골에 준 도움 1(2003.1.5 레크레아티보 25분). 2001.4.19 UEFA컵 준결승 리버풀전 44분 상대 PK 골의 도움 칸에 적힌 '클라위버르트 핸드볼'은 도움이 아님(선수 경기 성적에도 없음). 유형 칸이 빈 도움 27개는 골 설명이 PK·자책골이 아니어서 일반 도움으로 셈",
    "도움 시즌 합계의 출처 차이: 네덜란드어 위키백과는 바르셀로나 1999-00 리그 5(Transfermarkt 8), 2001-02 유럽 대회 5(4), 아약스 1995-96 9(8)로 적었으나 경기별 근거가 없어 Transfermarkt 경기 리포트를 따름(나머지 시즌은 합계 같음)",
    "날짜는 경기 현지 날짜(Transfermarkt 일정). 승부차기로 끝난 1995.11.28 인터콘티넨털컵 그레미우전(0-0)과 1996.5.22 챔스 결승 유벤투스전(1-1)에는 클라위버르트 골·도움이 없음. 2000.4.26 코파 델 레이 준결승 2차전 아틀레티코전(몰수 0-3)은 명단 외",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 계산, 그 시즌 최종 순위표에 리그 시즌 수준을 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['기존 팀×시즌 값']}, 순위표+리그 시즌 수준 {SRC['순위표+리그 시즌 수준']}, 직접 계산 {SRC['직접 계산(다른 유럽 리그 수준)']})",
    "순위표+리그 시즌 수준(새 팀-시즌): 그 시즌 리그 목표 평균 + 리그 흩어짐 × 순위 곡선 — AC 밀란 1994-95 세리에A 4위 1985, 로다 JC 1995-96 에레디비시 4위 1735, 피테서 1995-96 5위 1717·1996-97 5위 1748, 흐로닝언 1995-96 9위 1635. 다른 유럽 리그(같은 방식, 그 나라 시즌 목표 평균과 흩어짐, '리그 수준 추정'): AEK 아테네 1994-95 그리스 5위 1600, 그라스호퍼 1996-97 스위스 3위(챔피언십 라운드) 1575, 갈라타사라이 2002-03 튀르키예 2위 1719, 파니오니오스 2003-04 그리스 6위 1583. 직접 추정: 세우타 2000-01 스페인 3부(세군다 B 4조 4위) 1350(다른 선수 자료 스페인 3부 값). 순위는 Transfermarkt 순위표와 영어 위키백과 시즌 문서로 확인",
    "대회 비중: KNVB컵·코파 이탈리아·코파 델 레이·FA컵·리그컵·쿠프 드 프랑스는 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중; FA컵 6라운드는 8강), 요한 크루이프 스할·수페르코파(1999 두 경기)·UEFA 슈퍼컵(1996 두 경기)은 국내컵 결승, 인터콘티넨털컵은 클럽 월드컵, UEFA컵 1라운드와 인터토토컵 2005는 유로파 예선, UEFA컵 2004-05 조별은 유로파 조별, 이후 라운드는 유로파 토너먼트, 챔스 2차 조별(1999-2003)은 조별로 계산함",
    f"두 경기 합산(챔스·챔스 예선·UEFA컵·인터토토컵·UEFA 슈퍼컵·수페르코파·코파 델 레이·코파 이탈리아) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음). 클라위버르트가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 발렌시아는 2005.7.17 인터토토컵 첫 경기가 2005-06 시즌이 되도록 7월 10일 기준, 나머지 클럽은 기본 8월 1일. 클럽 구분은 Transfermarkt 이적일(1997.7.1 AC 밀란, 1998.8.28 바르셀로나, 2004.7.21 뉴캐슬, 2005.7.1 발렌시아, 2006.8.31 PSV, 2007.8.30 릴)",
    "동료 자료 대조: 히바우두·피구·호나우지뉴·리켈메·시어러·비야·비센테·바스투스 자료와 같은 경기의 대회·상대 Elo·합산 정보가 같고, 클라위버르트 도움→동료 골(히바우두 16·피구 4·호나우지뉴 1·시어러 1)과 동료 도움→클라위버르트 골(히바우두 12·피구 11·호나우지뉴 2·리켈메 2·시어러 1)의 날짜·분·스코어가 같음",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 챔스 1994-95, UEFA 슈퍼컵 1995, 인터콘티넨털컵 1995, 에레디비시 1994-95·1995-96·2006-07, 라리가 1998-99, 요한 크루이프 스할 1994·1995. 유로 2000 득점왕 등 대표팀 기록은 뺌",
    "은퇴: 2008년 7월 은퇴(마지막 클럽 경기 2008.4.26 툴루즈전)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM "]:
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
    gs = sorted({(r[5], r[6], r[4]) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
    for a, b in zip(gs, gs[1:]):
        if b[0] < a[0] or b[1] < a[1]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
    if len({(r[1], r[3]) for r in rs}) > 1: problems.append(("같은 날 상대·대회 다름", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
mm = {m[0]: m for m in M}
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[4] > 90 and not r[10] and not r[11]: problems.append(("90분 초과 표기 없음", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if MISS: problems.append(("Elo 없음", MISS))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and not ({"--debug", "--cross"} & set(sys.argv)):
    open(OUT_JS, "w", encoding="utf-8").write(f"const KLU_E={J(E)};\nconst KLU_M={J(M)};\nconst KLU_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "elo_sources": ELO_SRC, "elo_log": {f"{d} {o}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
