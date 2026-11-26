#!/usr/bin/env python3
"""Nicolas Anelka: raw/ -> anelka.json + src/data/anl.js (판정 근거는 judgments.md)

  python3 players/anelka/build_anelka.py            # 파일 쓰기
  python3 players/anelka/build_anelka.py --debug    # Elo 출처 로그
  python3 players/anelka/build_anelka.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/anelka/build_anelka.py --out DIR  # DIR/src/data/anl.js 로 쓰기(검증용 복사본)

입력: raw/tm_games.csv(출전·분·TM 일정 날짜), raw/tm_events.csv(리포트 골·도움), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv,
      raw/fotmob_events.csv·fotmob_tm_map.csv(2010-11부터 골·도움 대조), raw/ranks.txt·ranks_wiki.txt(순위표),
      elo/opponent_elo_by_team_season.csv·aliases.csv, tools/league_rank_apply.py(순위 라벨 → Elo),
      src/data/*.js(git 추적 파일 + 판정이 끝난 오버마스 ovm.js: 같은 경기 다른 선수 자료).
오버마스 build_overmars.py(같은 Transfermarkt 원자료 형식)를 바탕으로 함.
"""
import csv, json, os, re, sys, io, unicodedata, collections, subprocess, contextlib, runpy, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_ROOT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else ROOT
OUT_JS = os.path.join(OUT_ROOT, "src", "data", "anl.js")
OUT_JSON = os.path.join(HERE, "anelka.json")
ME = "3226"
ME_KO = "니콜라 아넬카"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")          # 성인 클럽 경기만(유소년·2군 경기는 TM API에 없음)
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)

def ldate(g):
    """TM 일정 날짜(현지). 리포트 날짜와 다른 경기 없음. API UTC는 킥오프 시각 없는 경기에서 하루 앞섬"""
    return datetime.datetime.strptime(g["date_tm_schedule"].split()[1], "%d/%m/%Y").strftime("%Y-%m-%d")
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "FR1", "ES1", "TR1", "IT1", "CSL", "IND1"}
CUPS = {"FAC", "CGB", "CDR", "FRC", "FRL", "TRP", "CHFA"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"                    # 재경기('Deciders') 포함
        if r.startswith("quarter") or r.startswith("sixth"): return "dk"   # FA컵 6라운드·리그컵 5라운드(TM 'Quarter-Finals') = 8강
        return "dc"                                              # 튀르키예컵 조별(2005-06) 포함
    if cid == "GBCS": return "df"                                # 채리티·커뮤니티 실드 = 국내컵 결승 비중
    if cid == "KLUB": return "cwc"                               # 2000 FIFA 클럽 세계 선수권(조별)
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"                   # 1999~2001 2차 조별 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid in ("UI", "UEQ"): return "elq"                        # 인터토토컵(결승 포함)·UEFA컵 예선 = 유로파 예선
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"             # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"                   # 2004~2009 UEFA컵 조별
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                             # 2·3라운드·32강('intermediate stage')·16강·8강
    if cid == "EPP":                                             # 컵위너스컵 16강 = 유로파 토너먼트(바티스투타·피구 선례)
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def two_leg(cid, rnd):
    r = rnd.lower()
    if cid == "FAC": return False        # FA컵 '3rd round 2nd leg'(2009.1.14 사우스엔드)는 재경기 = 단판
    return "leg" in r

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return 0
    if two_leg(cid, rnd): return 0
    if r.startswith("group"): return 0   # 챔스·UEFA컵·클럽 세계 선수권 2000·튀르키예컵 2005-06 조별 = 리그식
    return 1

def tie_rule(cid):
    """(원정 다득점, 연장) — 1990~2000년대 UEFA 대회·인터토토·코파 델 레이·잉글랜드 리그컵 준결승(2017-18까지)·튀르키예컵(2020-21까지)"""
    if cid in ("UEFA", "CL", "CLQ", "EPP", "UI", "UEQ", "CDR", "CGB", "TRP"): return (1, 1)
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
    if not two_leg(g["competitionId"], g["round"]): return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"])
    leg = 1 if ("1st" in rnd or "first leg" in rnd) else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
# TM played 671경기 모두. 영어 위키백과의 상하이 선화 2012 'continental' 3경기 1골은 경기 단위 출처가 없고
# 선화는 2012 AFC 챔스에 나가지 않아(위키백과 2012 AFC Champions League·2012 Shanghai Shenhua season) 넣지 않음.
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

# 골 직전 스코어 고침(리포트 순서 문제): 2004.1.14 FA컵 3라운드 재경기 레스터 1-3 맨시티 — TM은 아넬카·매컨 두 골을 모두 '1-3' 90분으로 적음.
# ESPN 경기 기록(골 순서 아넬카 90'·매컨 90')과 맨시티 팬 경기 기록(rtfract.com '아넬카 골, 세 번째 골 매컨')으로 아넬카 골 = 1-1에서 1-2.
BEFORE_FIX = {("2286251", "Nicolas Anelka"): (1, 1)}   # (홈, 원정) 골 전

# 골 시각 고침: 2007.12.22 볼턴 3-0 버밍엄 아넬카 두 번째 골 — TM 리포트 시계 '120'(정규시간 경기). Sky Sports 경기 기사 '추가시간 골', 다른 기록 90분 → 90분.
MIN_FIX = {("81654", "120"): "90"}

raw_rows, judg = [], []
SEQ_DIFF = []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        bh, ba = (h - 1, a) if e["side"] == "home" else (h, a - 1)
        if (gid, e["scorer"]) in BEFORE_FIX:
            bh, ba = BEFORE_FIX[(gid, e["scorer"])]
            judg.append(("골 전 스코어 고침(리포트 순서)", ldate(g), opp(g), e["minute"], (bh, ba)))
        if (bh, ba) != prev: SEQ_DIFF.append((gid, ldate(g), e["minute"], (bh, ba), prev))
        prev = (bh + (e["side"] == "home"), ba + (e["side"] != "home"))
        if e["scorer_id"] == ME and is_og(e):
            judg.append(("자책골(상대 득점, 본인 골 아님)", ldate(g), opp(g), e["minute"])); continue
        if e["assist_id"] == ME and e["anelka_assist_other"] != "1" and e["anelka_scorer"] != "1":
            judg.append(("상대 골 도움 칸 표기(도움 아님)", ldate(g), opp(g), e["minute"], e["assist_type"])); continue
        is_g = e["anelka_scorer"] == "1" and not is_og(e)
        is_a = e["anelka_assist_other"] == "1"
        if e["anelka_self_assist"] == "1":
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if not (is_g or is_a): continue
        gf, ga = (bh, ba) if side == "h" else (ba, bh)
        if not ((e["side"] == "home") == (side == "h")) and not (is_a and is_og(e)):
            sys.exit("득점 편 이상 " + gid + " " + e["minute"])
        mstr = MIN_FIX.get((gid, e["minute"]), e["minute"])
        if mstr != e["minute"]: judg.append(("골 시각 고침", ldate(g), opp(g), e["minute"], mstr))
        mi, dm = mins(mstr)
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

# FotMob에만 있는 도움(2011.9.10 선덜랜드 18분 존 테리 골): TM 리포트·API에 없고, AP 기사(Fox Sports 'Chelsea seals victory at Sunderland')는
# 마타 프리킥이 골대를 맞고 나온 뒤 테리의 슈팅이 막히고 다시 찬 공이 바즐리 맞고 들어갔다고 적음 → 넣지 않음.
judg.append(("FotMob만의 도움 넣지 않음", "2011-09-10", "Sunderland AFC", "18", "John Terry", "TM 없음·AP 기사상 마타 프리킥 리바운드"))

cnt = collections.Counter()
for r in raw_rows: cnt[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt[(gid, "g")] != int(g["goals"]): sys.exit("골 수 불일치 " + gid)
    if int(g["goals"]) and gid not in EVS: sys.exit("리포트 없음 " + gid)

# FotMob 대조(2010-11부터): 골 수·시각
FM = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FM[r["tm_gameId"]].append(r)
FM_DIFF = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    if gid not in FM or typ != "g": continue
    hits = [r for r in FM[gid] if r["anelka_scorer"] == "1"]
    if not hits: FM_DIFF.append(("FotMob 골 없음", gid)); continue
    best = min(int(r["minute"]) + int(r["overloadTime"] or 0) for r in hits if True)
    mm_ = [int(r["minute"]) + int(r["overloadTime"] or 0) for r in hits]
    if min(abs(x - mi) for x in mm_) > 0: FM_DIFF.append(("골 시각", ldate(G[gid]), mi, mm_))

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
MANUAL_ALIAS = {"inter milan": "inter", "port vale": "port vale fc", "hajduk split": "hnk hajduk split"}
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
        fs = [os.path.join(ROOT, x) for x in out if x.endswith(".js")]
    except Exception:
        sys.exit("git ls-files 실패(병렬 판정 파일을 읽지 않으려고 추적 파일만 씀)")
    ovm = os.path.join(ROOT, "src", "data", "ovm.js")       # 판정이 끝난 오버마스(아스널 1997~99 동료)
    if os.path.exists(ovm) and ovm not in fs: fs.append(ovm)
    return fs

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in tracked_data():
    b = os.path.basename(fn)
    if b in ("hon.js", "anl.js", "clubcolors.js"): continue
    OTHERS[b] = load_js(fn)
BYDATE = collections.defaultdict(list)
for b, (P, oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "atletico", "calcio",
        "sport", "cd", "ud", "rcd", "sv", "as", "ss", "milan", "inter", "madrid", "ca", "fk", "sk", "ssc", "us", "balompie", "deportivo",
        "bilbao", "rotterdam", "eindhoven", "amsterdam", "athletic", "racing", "afc", "bvo", "vigo", "wednesday", "sheffield", "olympique",
        "west", "wanderers", "rovers", "town", "albion", "hotspur", "county", "athletic", "paris", "saint", "germain", "stade", "spor", "kulubu"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
TOKS_LOG = []
NOT_SAME = {("Arsenal FC", "2003-02-22"),     # 아르헨티나 아르세날 데 사란디(다른 팀) — 이름 토큰만 같음
            ("Manchester United", "2002-11-09")}  # 긱스 자료의 상대 맨시티 행(맨유가 아님)
def same_match(o, d):
    if (o, d) in NOT_SAME: return [], set()
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    if not cand:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if toks(x[1]) & toks(o)]
        if cand: TOKS_LOG.append((o, d, sorted({(b, x[1], x[12]) for b, x in cand})))
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 → 라벨 → Elo(tools/league_rank_apply.py와 같은 값)
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    RA = runpy.run_path(os.path.join(ROOT, "tools", "league_rank_apply.py"), run_name="ra")
sys.argv = _argv

RANKS = collections.defaultdict(dict)     # (리그 코드, 시즌) -> {팀 키: (순위, 팀 수, 이름)}
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
# TM 순위표 고침(공식 동률 규칙): 쉬페르리그 2004-05 카이세리스포르 14위·디야르바크르스포르 15위(승점 같음, 맞대결 득실로 카이세리 앞 — 영어 위키백과 2004–05 Süper Lig)
RANKS[("TR1", "2004-05")][key("Kayserispor")] = (14, 18, "Kayserispor")
WIKI_LG = {"1997–98_Football_League_First_Division": ("GB2w", "1997-98"),
           "1998–99_Football_League|First Division": ("GB2w", "1998-99"),
           "2002–03_Football_League|First Division maps > Second Division": ("GB3w", "2002-03")}
with open(os.path.join(RAW, "ranks_wiki.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "source_page": continue
        for k, (lg, s) in WIKI_LG.items():
            if (p[0] + "|" + p[1]).startswith(k):
                RANKS[(lg, s)][key(re.sub(r"\s*\([A-Z]{2,4}\)$", "", p[4]))] = (int(p[2]), int(p[3]), p[4])

def label(lg, s, r, n):
    if lg == "FR1": return f"리그1 {s} {r}위/{n}팀" if n != 18 else f"리그1 {s} {r}위"
    if lg == "TR1": return f"튀르키예 1부 {s} {r}위/{n}팀 (Süper Lig)"
    if lg == "GB2w": return f"챔피언십 {s} {r}위/{n}팀 (Football League First Division)"
    if lg == "GB2": return f"챔피언십 {s} {r}위/{n}팀"
    if lg == "GB4": return f"잉글랜드 4부 {s} {r}위/{n}팀 (Football League Two, 리그 수준 추정)"
    if lg == "GR1": return f"그리스 1부 {s} {r}위/{n}팀 (Alpha Ethniki)"
    if lg == "UKR1": return f"우크라이나 1부 {s} {r}위/{n}팀"
    if lg == "PL1": return f"폴란드 1부 {s} {r}위/{n}팀 (Ekstraklasa)"
    if lg == "BE1": return f"벨기에 1부 {s} {r}위/{n}팀 (Belgian First Division)"
    if lg == "CSL": return f"중국 슈퍼리그 {s} {r}위/{n}팀"
    return None
RANK_LG = ["CSL", "FR1", "TR1", "GB2w", "GB2", "GB4", "GR1", "UKR1", "PL1", "BE1"]

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

def ra_value(lv, d):
    p = RA["parse"](lv, d)
    if not p: sys.exit("순위 라벨 해석 실패 " + lv)
    v = RA["value"](*p)
    if v is None: sys.exit("기준 없음 " + lv)
    return v

# 순위표에 없는 팀-시즌(직접 확인한 라벨: judgments.md 4절)
MANUAL_LV = {
    ("Rapid Bucharest", "2001-09-25"): "루마니아 1부 2001-02 3위/16팀 (Divizia A)",                        # 영어 위키백과 2001–02 Divizia A(우승 디나모)
    ("B36 Tórshavn", "2006-07-26"): "페로 제도 1부 2006 3위/10팀 (Formuladeildin)",                         # 영어 위키백과 2006 Faroe Islands Premier League(우승 HB)
    ("Rabotnicki Skopje", "2007-10-04"): "북마케도니아 1부 2007-08 1위/12팀 (Macedonian First Football League)",  # 영어 위키백과 2007–08 시즌(우승)
}
# 순위를 정할 수 없는 팀-시즌(그 단계 기준점 값): 2005-06 TFF 2. Lig는 1차 조별 뒤 순위 조별(Kademe)로 나뉘어 최종 순위가 하나로 정해지지 않음
NORANK = {("Tarsus Idman Yurdu", "2006-02-22"): (1118, "튀르키예 3부 2005-06 순위 없음 (TFF 2. Lig; 리그 수준 추정)")}

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid, gid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1:
        print("  [같은 경기 값 여럿]", o, d, vals)
    if (o, d) in NORANK:
        e, lv = NORANK[(o, d)]; ELO_SRC["순위 없음(그 단계 기준점)"] += 1; ELO_LOG[(o, d)] = ("norank", e, lv); return e, lv
    if (o, d) in MANUAL_LV:
        lv = MANUAL_LV[(o, d)]; e = ra_value(lv, d)
        ELO_SRC["직접 확인 라벨(새 팀-시즌)"] += 1; ELO_LOG[(o, d)] = ("manual", e, lv); return e, lv
    k = key(o)
    euro = cid in ("CL", "CLQ", "UEFA", "UEQ", "UI", "EPP", "KLUB")
    s0 = eu(d)
    if cid in ("CSL", "CHFA", "IND1"): seasons = [d[:4]]
    else: seasons = [s0, d[:4]] if euro else [s0]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, d[:4] if lg == "CSL" else s0))
        if t and k in t:
            r, n, _ = t[k]
            lv = label(lg, d[:4] if lg == "CSL" else s0, r, n)
            e = ra_value(lv, d)
            ELO_SRC["순위표+순위 규칙(새 팀-시즌)"] += 1; ELO_LOG[(o, d)] = ("model", e, lv, s0); return e, lv
    MISS.append((o, d, cid, tuple(seasons), gid)); return 0, "?"

# ---------------------------------------------------------------- 기록 행
E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, gid)
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
    print("FM_DIFF", FM_DIFF)
    for t in TOKS_LOG: print("TOKS", t)
    for j in judg: print("judg", j)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("psgan", "1997-02-22", "파리 생제르맹", "1995~1997", "Paris Saint-Germain", "583"),
         ("arsan", "1999-08-02", "아스널", "1997~1999", "Arsenal", "11"),
         ("rman", "2000-07-01", "레알 마드리드", "1999~2000", "Real Madrid", "418"),
         ("psgan2", "2001-12-21", "파리 생제르맹", "2000~2001", "Paris Saint-Germain", "583"),
         ("livan", "2002-06-07", "리버풀", "2001~2002", "Liverpool", "31"),
         ("mcian", "2005-01-31", "맨체스터 시티", "2002~2005", "Manchester City", "281"),
         ("fenan", "2006-08-25", "페네르바흐체", "2005~2006", "Fenerbahce", "36"),
         ("bolan", "2008-01-11", "볼턴 원더러스", "2006~2008", "Bolton Wanderers", "355"),
         ("chean", "2012-01-02", "첼시", "2008~2012", "Chelsea", "631"),
         ("shsan", "2013-01-26", "상하이 선화", "2012", "Shanghai Shenhua", "3183"),
         ("juvan", "2013-07-04", "유벤투스", "2013", "Juventus", "506"),
         ("wbaan", "2014-09-15", "웨스트 브로미치 앨비언", "2013~2014", "West Bromwich Albion", "984"),
         ("mcyan", None, "뭄바이 시티", "2014~2015", "Mumbai City", "45274")]
def club_of(d):
    for c in CLUBS:
        if c[1] is None or d < c[1]: return c[0]
ST = collections.OrderedDict((c[0], [0, 0, 0, 0]) for c in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TM_CLUB = {"583": ("psgan", "psgan2"), "11": ("arsan",), "418": ("rman",), "31": ("livan",), "281": ("mcian",), "36": ("fenan",),
           "355": ("bolan",), "631": ("chean",), "3183": ("shsan",), "506": ("juvan",), "984": ("wbaan",), "45274": ("mcyan",)}
for g in GAMES:
    if club_of(ldate(g)) not in TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
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
    ta = a[14] if len(a) > 14 and a[14] else None; tb = b[14] if len(b) > 14 and b[14] else None
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    return diffs
MYG = [r for r in E if r[0] == "g"]
for b, (P, ent, om) in OTHERS.items():
    for x in ent:
        if x[0] == "a" and "Anelka" in str(x[13]):
            hit = sorted([r for r in MYG if r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append(("동료 도움→아넬카 골", b, x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
for r in E:
    if r[0] != "a": continue
    found = False
    for b, x in BYDATE.get(r[9], []):
        if x[0] == "g" and abs(x[4] - r[4]) <= 3 and (x[5], x[6]) == (r[5], r[6]) and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])):
            CROSS.append(("아넬카 도움→동료 골", b, r[9], r[4], r[13], cmp_rows(r, x) or "같음")); found = True
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
# 동료 골 중 이 자료가 아넬카 도움으로 넣었는데 동료 자료에 다른 도움(또는 없음)으로 적힌 것은 정보만(동료 자료 note가 도움 선수 이름)
if "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
    print(collections.Counter((c[0], c[1]) for c in CROSS if c[0] != "출전 행"))

exec(open(os.path.join(HERE, "note_anelka.py"), encoding="utf-8").read())

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
    open(OUT_JS, "w", encoding="utf-8").write(f"const ANL_E={J(E)};\nconst ANL_M={J(M)};\nconst ANL_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "elo_sources": ELO_SRC, "elo_log": {f"{d} {o}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
