#!/usr/bin/env python3
"""제 호베르투 (Zé Roberto, Transfermarkt 89): raw/ -> zeroberto.json + src/data/zer.js (판정 근거는 judgments.md)

  python3 players/zeroberto/build_zeroberto.py            # 파일 쓰기
  python3 players/zeroberto/build_zeroberto.py --debug    # Elo 출처 로그만 출력
  python3 players/zeroberto/build_zeroberto.py --stat     # 요약·동료 대조·FotMob 대조
  python3 players/zeroberto/build_zeroberto.py --ties     # 합산 행

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(2010-11 이후 대조), raw/ranks.txt(Transfermarkt 순위표),
      ../ballack/raw/ranks.txt(분데스리가 1999-00~2010-11 Transfermarkt 순위표, 발라크 수집본),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조),
      players/makaay/staged/mak.js·players/altintop/staged/alt.js(병렬 판정 중인 동료 자료: 대조만).
환경 변수 ZER_ROOT: 저장소 뿌리(스크래치 복사본에서 돌릴 때).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("ZER_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "zer.js")
OUT_JSON = os.path.join(HERE, "zeroberto.json")
ME = "89"
ME_KO = "제 호베르투"

def rd(n, base=RAW):
    with open(os.path.join(base, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FPM = rd("fotmob_playerMatches.csv")

from zoneinfo import ZoneInfo
import datetime as _dt
EU_CLUBS = {"418", "15", "27", "41"}
def ldate(g):
    # 유럽 클럽 경기: API UTC를 중부 유럽 시간으로 바꾼 날짜(= Transfermarkt 일정·리포트 날짜). 원자료 date_local은 리포트가 없는 경기에
    #   UTC 날짜를 넣어 1997년 레알 마드리드 14경기가 하루 앞당겨져 있었음(라울·세도르프 자료와 하루 차이) → 고침.
    # 브라질·카타르: 원자료 date_local(UTC → 상파울루/카타르 시간).
    if g["club_id"] in EU_CLUBS:
        return _dt.datetime.fromisoformat(g["date_utc"]).astimezone(ZoneInfo("Europe/Berlin")).date().isoformat()
    return g["date_local"]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 판정 표
# 1996.8.25 브라질 세리에 A 아틀레치쿠 미네이루전(4412545): TM 선발 표시인데 playedMinutes 0(교체 정보 없음) → 90분 추정
MIN_EST = {"4412545": 90}
MIN_FIX = {}
GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# 2014.8 이후 TM 도움(13개, Shot on goal 1개 제외 뒤) 판정. FotMob 경기 이벤트는 브라질 경기 도움 칸이 모두 비어 있음.
#  "fm": FotMob 선수 경기 목록(playerMatches) 도움 1과 일치 → TM+FotMob 확인
#  "art": 다른 독립 출처 2곳(경기 기사) 확인 — judgments.md 4절에 출처
#  "gap": FotMob에 도움 자료가 없는 구간(제르비뉴 허베이 2016 선례) + 경기 기사 1곳 또는 FotMob 경력 합계로만 보강 → TM 도움을 씀(확인 요청)
#  "drop": 다른 출처가 반대(다른 선수 도움·단독 돌파 등) → 뺌
POST_GAP = {   # (gameId, minute) -> (판정, 근거)
    ("2454509", "90+2"): ("drop", "2014.9.10 아틀레치쿠 파라나엔시전 바르코스: ESPN 경기 기록(통계 피드)만 확인, 기사 1곳(가제타 두 포보)은 도움자 언급 없음 → 다른 출처 2곳 못 채움"),
    ("2454552", "50"): ("art", "2014.9.28 보타포구전 바르코스: FourFourTwo 경기 기사(제 호베르투가 6야드 박스 가로질러 내줌) + 마이스 고이아스 기사(두두→제 호베르투→옆으로 바르코스)"),
    ("2454639", "76"): ("drop", "2014.11.9 인테르나시오나우전 알란 루이스: 기사(브라질247)는 제 호베르투 프리킥을 호돌푸가 머리로 떨궈 루이스가 넣었다고 적음 → 마지막 패스가 다른 선수(반대 출처)"),
    ("2454650", "38"): ("drop", "2014.11.15 크리시우마전 바르코스: ESPN·SportsNetwork 기사 모두 도움자 언급 없음 → 출처 없음"),
    ("4318043", "52"): ("art", "2015.3.25 파울리스타 상파울루전 하파엘 마르케스: 가제타 이스포르치바 경기 기사 + 트리부나 PR·팔메이라스 구단 기사(제 호베르투 크로스를 바로 슈팅)"),
    ("2547056", "82"): ("drop", "2015.5.9 아틀레치쿠 미네이루전 비토르 우구: 통계 사이트(sporteden) 1곳만 도움자 표기, 구단 기사는 '코너킥'만 적고 키커 언급 없음"),
    ("2569263", "65"): ("drop", "2015.6.4 인테르나시오나우전 비토르 우구: 구단 기사는 '코너킥 뒤'만 적고 키커 언급 없음 → 출처 없음"),
    ("2611093", "6"): ("art", "2015.8.16 플라멩구전 잭슨: 팔메이라스 구단 경기 기사(제 호베르투 코너킥, 잭슨 헤더) + 트리벨라 기사(제 호베르투 코너킥을 먼 쪽 포스트에서 헤더)"),
    ("2626674", "75"): ("art", "2015.11.18 아틀레치쿠 파라나엔시전 잭슨: 팔메이라스 구단 기사(제 호베르투 코너킥을 먼 쪽 포스트로, 잭슨 헤더) + 가제타 두 포보·트리부나 PR 기사(제 호베르투 코너킥, 잭슨 헤더)"),
    ("2770179", "88"): ("art", "2016.10.9 아메리카 미네이루전 알레산드루: 란세 기사 + 조르나우 지 브라질리아·조르나우 두 코메르시우 기사(제 호베르투 롱패스를 받아 득점)"),
    ("2888283", "32"): ("fm", "2017.7.19 플라멩구전 윌리안: FotMob 선수 경기 목록 도움 1"),
    ("2900516", "86"): ("fm", "2017.8.2 보타포구전 데이베르송: FotMob 선수 경기 목록 도움 1"),
    ("4335440", "80"): ("drop", "2017.3.3 파울리스타 레드불 브라질전 호제르 게지스: 구단·가제타 이스포르치바·란세 기사 모두 도움자 언급 없음 → 출처 없음"),
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BRA1", "ES1", "L1", "QSL"}
STATE = {"BCP1", "BCPF", "BRRS", "BRga", "RS2f"}   # 캄페오나투 파울리스타·가우슈: 국내컵 하위 비중(네이마르·히바우두·포를란 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid in ("BRC", "DFB"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "LPO":                       # DFB-리가포칼(발라크·클로제 선례): 첫 경기(intermediate stage) 8강, 준결승, 결승
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        return "dk"
    if cid == "SUC": return "df"           # 수페르코파 = 국내컵 결승 비중
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "CLQ": return "clq"
    if cid == "ELQ": return "elq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                       # 2라운드·3라운드·8강
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                       # 32강('Second Round')·16강·8강
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"                       # 예선·조별·16강
    if cid == "CS":
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    r = rnd.lower()
    if cid in ("UEFA", "CL", "CLQ", "EL", "ELQ"): return (1, 1)    # UEFA 대회 2020-21까지
    if cid == "SUC": return (1, 1)                                 # 수페르코파(스페인 2018-19까지)
    if cid in ("BCPF",): return (0, 0)                             # 파울리스타 결승 단계 두 경기: 원정 다득점·연장 없음(네이마르 선례)
    if cid == "BRC":
        if r.startswith("final"): return (0, 0)                    # 코파 두 브라질 결승: 원정 다득점 없음(2015 결승 합산 2-2 → 승부차기)
        return (1, 0)                                              # 그 밖 라운드: 원정 다득점, 연장 없음(네이마르·루카스 모우라·포를란 선례)
    if cid in ("CLI", "CS"): return (1, 0)                         # 2017까지 원정 다득점, 연장 없이 승부차기(결승 제외)
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
    oh, oa = map(int, m["other_leg_score"].split(":"))
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
    if e["goal_desc"] == "Penalty": return "PK 골(도움 없음)"
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
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        if (gid, e["minute"]) in BEFORE_FIX: gf, ga = BEFORE_FIX[(gid, e["minute"])]
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if ldate(g) >= GAP:
                dec = POST_GAP.get((gid, e["minute"]))
                if not dec: sys.exit("2014.8 이후 도움 판정 없음 %s %s %s" % (gid, ldate(g), e["minute"]))
                judg.append(("2014.8 이후 도움 " + dec[0], ldate(g), opp(g), e["minute"], e["scorer"], dec[1]))
                if dec[0] == "drop": continue
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
MANUAL_ALIAS = {"inter milan": "inter", "olympique lyon": "olympique lyonnais"}
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
STAGED = {}
for fn in [os.path.join(ROOT, "players", "makaay", "staged", "mak.js"), os.path.join(ROOT, "players", "altintop", "staged", "alt.js")]:
    if os.path.exists(fn):
        P, oe, om = load_js(fn); STAGED["staged/" + os.path.basename(fn)] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "milan", "inter", "madrid", "moscow", "moskau", "paulista", "paulo", "ca", "cs", "club", "deportivo", "deportes", "universidad", "san", "santa",
        "borussia", "bayer", "vfl", "vfb", "tsv", "fsv", "munich", "munchen", "hamburger", "eintracht", "werder", "bsc", "hertha", "rb"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
SOUTH = {"BRA1", "BCP1", "BCPF", "BRRS", "BRga", "RS2f", "BRC", "CLI", "CS", "QSL"}
def same_match(o, d, cid):
    if cid in SOUTH:   # 남미·국내 대회: 같은 이름 다른 팀 오인을 막으려 정확히 같은 팀 이름만(포를란 선례)
        cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    else:
        cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
RANK_SRC = {}
def load_ranks(fn, tag, only=None):
    with open(fn, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("|")
            if len(p) < 5 or p[0] == "league": continue
            lg, s = p[0], p[1].split(" ")[0]
            if only and lg not in only: continue
            if (lg, s) in RANK_SRC and RANK_SRC[(lg, s)] != tag: continue
            RANK_SRC[(lg, s)] = tag
            RANKS[(lg, s)][key(p[4])] = (int(p[2]), int(p[3]), p[4])
load_ranks(os.path.join(RAW, "ranks.txt"), "zr", only={"L1", "BRA1", "BRA2", "QSL", "BCP1"})
# 분데스리가 1999-00·2000-01·2004-05~2010-11 표는 이 선수 원자료에 없음 → 발라크 원자료의 Transfermarkt 표(같은 출처)
load_ranks(os.path.join(ROOT, "players", "ballack", "raw", "ranks.txt"), "ballack", only={"L1"})

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

def rank_model(lg, season, r, n):
    if lg == "BRA1":
        m = ents_map("브라질 세리에 A", season)
        if r in m: return m[r], f"브라질 세리에 A {season} {r}위"
        return half_up(1598 + 63 * curve(r, n)), f"브라질 세리에 A {season} {r}위"
    if lg == "BRA2":
        m = ents_map("브라질 세리에 B", season)
        if r in m: return m[r], f"브라질 세리에 B {season} {r}위"
        return half_up(1370 + SD2 * curve(r, n)), f"브라질 세리에 B {season} {r}위"
    if lg == "L1":
        m = ents_map("분데스리가", season)
        if season <= "2006-07" and r not in m:   # 1998-99~2006-07은 모든 시즌이 같은 순위값(기존 자료 2000-01 표 1~18위)
            m = dict(m); m[r] = ents_map("분데스리가", "2000-01")[r]
        v, it = mid(m, r)
        if v is None: return None
        if it: INTERP_USED.add(("분데스리가", season, r, v))
        return v, f"분데스리가 {season} {r}위"
    if lg == "QSL":   # 카타르 스타스리그: 마레즈·에투·라울 자료와 같은 모형(평균 1460, 흩어짐 45)
        return half_up(1460 + 45 * curve(r, n)), f"카타르 {season} {r}위 (추정, 마레즈 자료와 같은 리그 수준)"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
def eu_jul10(d):
    y = int(d[:4]); s = y if d[5:] >= "07-10" else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 순위표·기존 자료에 없는 상대(직접 추정, 모두 lv에 '추정') — judgments.md 6절
MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
C4 = "다른 선수 자료 4부 이하 1200과 같음"
man("Grêmio Barueri Futebol Ltda.", "2007", half_up(1370 + SD2 * curve(13, 20)), "브라질 세리에 B 2007 13위")   # 영어 위키백과 2007 세리에 B 표(검색 요약): 13위 51점
man("Guaratinguetá (SP)", "2007", 1200, f"브라질 4부 이하 2007 (추정, 세리에 A·B 참가 팀 아님, 세리에 C 2007 참가 확인 못 함; {C4})")
man("Defensor Sporting Club", "2007", 1644, "우루과이 1부 2006-07 상위권 (추정, 다른 선수 자료 데펜소르 2005-06 2위 1644와 같음)")
man("Caracas FC", "2007", 1400, "베네수엘라 1부 2006-07 우승 팀 (추정, 다른 선수 자료 베네수엘라 상위 팀 데포르티보 타치라 1400과 같음)")
man("Hapoel Tel Aviv", "2009-10", 1500, "이스라엘 2009-10 1위 (추정, 다른 선수 자료 하포엘 텔아비브 2008-09~2011-12 상위권 1500과 같음)")
man("Barcelona SC Guayaquil", "2012", 1480, "에콰도르 1부 2012 상위 팀 (추정, 다른 선수 자료 에콰도르 상위 팀 바르셀로나 SC 1998·에멜레크 2014 1480과 같음)")
man("Esporte Clube São José (RS)", "2013", 1200, f"브라질 4부 이하 2013 (추정, 캄페오나투 가우슈 팀, 세리에 C 참가 팀 아님; {C4})")
man("CE Lajeadense", "2013", 1200, f"브라질 4부 이하 2013 (추정, 캄페오나투 가우슈 팀, 세리에 C 참가 팀 아님; {C4})")
man("Caracas FC", "2013", 1400, "베네수엘라 1부 2012-13 상위 팀 (추정, 다른 선수 자료 베네수엘라 상위 팀 1400과 같음)")
man("Huachipato FC", "2013", 1480, "칠레 1부 2013 (추정, 다른 선수 자료 칠레 1부 팀 1450~1550 사이 값)")
man("SER Caxias do Sul (RS)", "2014", 1253, "브라질 세리에 C 2014 (추정, 세리에 C B조 참가 팀; 다른 선수 자료 세리에 C 1253과 같음)")
man("Rio Claro Futebol Clube (SP)", "2015", 1200, f"브라질 4부 이하 2015 (추정, 파울리스타 A1 팀, 세리에 A~C 참가 팀 아님; {C4})")
man("Red Bull Brasil (SP)", "2017", 1200, f"브라질 세리에 D 2017 (추정, 4부 이하; {C4})")
man("Club Atlético Tucumán", "2017", 1566, "아르헨티나 1부 2016-17 (추정, 다른 선수 자료 아틀레티코 투쿠만 2017-18 15위 1566과 같음)")
# 1996 세리에 A: Transfermarkt 표는 단계를 합친 순서(크루제이루 2위·포르투게자 5위)라 공식 순위와 다름. 크루제이루는 1단계 1위였으나 결승 단계 8강에서
#   포르투게자에 져 탈락(검색 요약: 영어 위키백과·갈루 지지타우 1996 대진) → 8강 탈락 팀 중 1단계 1위 = 5위로 추정
man("Cruzeiro Esporte Clube", "1996", half_up(1598 + 63 * curve(5, 24)), "브라질 세리에 A 1996 5위 (추정, 1단계 1위·결승 단계 8강 탈락)")
man("Fortuna Düsseldorf", "2009-10", 1622, "2. 분데스리가 2009-10 4위")

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid, rnd=""):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    y = d[:4]
    if cid in SOUTH and cid != "QSL":
        seasons = [y]
    elif cid in ("CL", "CLQ", "UEFA", "EL", "ELQ"):
        seasons = [eu(d), y, str(int(y) - 1)] if int(d[5:7]) < 7 else [eu(d), y]
    elif cid in ("L1", "DFB", "LPO"):
        seasons = [eu_jul10(d)]
    else:
        seasons = [eu(d)]
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    if cid in SOUTH and cid != "QSL":
        lgs = [("BRA1", y), ("BRA2", y)]
    elif cid == "QSL":
        lgs = [("QSL", eu(d))]
    elif cid in ("L1", "DFB", "LPO"):
        lgs = [("L1", eu_jul10(d))]
    else:
        lgs = [("L1", eu(d))]
    for lg, s in lgs:
        t = RANKS.get((lg, s), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], RANK_SRC.get((lg, s))); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

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
    print(collections.Counter(j[0] + "/" + str(j[-1]) for j in judg))
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["zr_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if not FME[gid] or all(not r["time"] for r in FME[gid]): continue
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "penalty" in (f["goalDescriptionKey"] or "").lower() or "pen" in (f["suffix"] or "").lower()
        a = mins(t["minute"])[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
        if tp != fp or abs(a - b) > 1: FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))
FM_N = sum(1 for gid in EVS if gid in G and gid in FME and any(e["scorer_id"] == ME for e in EVS[gid]))

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
ALLO = dict(OTHERS); ALLO.update(STAGED)
def same_team(x, r): return key(x[1]) == key(r[1]) or bool(toks(x[1]) & toks(r[1]))
for b, (oe, om) in ALLO.items():
    for x in oe:
        if x[0] == "a" and re.match(r"^Z[ée] Roberto$", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(제 호베르투 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x, r)]
            if hit: CROSS.append(("제 호베르투 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x, r)]
            for x in hit:
                if not re.match(r"^Z[ée] Roberto$", x[13] or ""): CROSS.append(("타인 도움 표기 다름(제 호베르투 골)", b, r[9], r[4], x[13]))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x, r):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm, m) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
    # 동료 출전 날짜 하루 차이(같은 상대)
    mdates = {(m[0], key(m[1])) for m in M}
    for mm in om:
        for dd in (-1, 1):
            import datetime
            try:
                d2 = (datetime.date.fromisoformat(mm[0]) + datetime.timedelta(days=dd)).isoformat()
            except Exception: continue
            if (d2, key(mm[1])) in mdates and (mm[0], key(mm[1])) not in mdates and mm[0][:4] >= "1994":
                CROSS.append(("같은 상대 출전 날짜 하루 차이", b, mm[0], d2, mm[1]))
for b, (oe, om) in ALLO.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and (key(x[1]) == key(j[2]) or toks(x[1]) & toks(j[2])):
                    CROSS.append(("TM 제 호베르투 도움을 규칙대로 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("porzr", "1997-03-18", "포르투게자", "1994~1996"), ("rmzr", "1998-07-01", "레알 마드리드", "1997"),
         ("levzr", "2002-07-01", "바이어 레버쿠젠", "1998~2002"), ("bayzr", "2006-07-01", "바이에른 뮌헨", "2002~2006"),
         ("sanzr", "2007-07-01", "산투스", "2006~2007"), ("bayzr", "2009-07-02", "바이에른 뮌헨", "2007~2009"),
         ("hsvzr", "2011-07-10", "함부르크 SV", "2009~2011"), ("gharzr", "2012-06-04", "알가라파", "2011~2012"),
         ("grezr", "2015-01-08", "그레미우", "2012~2014"), ("palzr", None, "팔메이라스", "2015~2017")]
TM_CLUB = {"10247": "porzr", "418": "rmzr", "15": "levzr", "27": "bayzr", "221": "sanzr", "41": "hsvzr", "6297": "gharzr", "210": "grezr", "1023": "palzr"}
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
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({(r[9]) for r in E if len(r) > 14})
CAL = {"porzr", "sanzr", "grezr", "palzr"}; JUL10 = {"levzr", "bayzr", "hsvzr"}
def season_of(d, club):
    y = int(d[:4])
    if club in CAL: return str(y)
    if club in JUL10: return eu_jul10(d)
    s = y if int(d[5:7]) >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    print("FotMob", FM_N, FM_CMP)
    for c in CROSS: print(c)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    for j in judg: print(j)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_zeroberto.py"), encoding="utf-8").read())

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
    if m and r[4] > m[3] + 3 and not r[10] and Gstart[r[9]]: problems.append(("출전 분보다 늦은 기록", r, m))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const ZER_E={J(E)};\nconst ZER_M={J(M)};\nconst ZER_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
