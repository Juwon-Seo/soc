#!/usr/bin/env python3
"""디에고 포를란 (Transfermarkt 3408): raw/ -> forlan.json + src/data/frl.js (판정 근거는 judgments.md)

  python3 players/forlan/build_forlan.py            # 파일 쓰기
  python3 players/forlan/build_forlan.py --debug    # Elo 출처 로그만 출력
  python3 players/forlan/build_forlan.py --stat     # 요약·동료 대조
  python3 players/forlan/build_forlan.py --ties     # 합산 행

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv(2010-11 이후 골 대조), raw/ranks.txt·raw/tables/tm_URU1_2015.html·tm_URUC_2015.html(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, html as HTML

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("FRL_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "frl.js")
OUT_JSON = os.path.join(HERE, "forlan.json")
ME = "3408"
ME_KO = "디에고 포를란"

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

# 날짜: 유럽 클럽은 TM 날짜(현지). 남미·아시아 클럽은 TM API 시각(UTC)을 클럽 연고지 시간대로 바꾼 날짜(date_local).
# 연고지와 시간대가 다른 원정(메르코수르·리베르타도레스·AFC 챔스 원정)도 모두 경기지 현지 날짜와 같음(judgments.md 2절) → date_local 그대로.
def ldate(g): return g["date_local"]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ARG1", "ARGC", "GB1", "ES1", "IT1", "BRA1", "JAP1", "JAP2", "URU1", "URUC", "IND1", "HGKG", "URUP"}
STATE = {"BRRS", "BRga", "RS2f"}   # 캄페오나투 가우슈 2013: 국내컵 하위 비중(네이마르 파울리스타·주니뉴 카리오카 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"     # URUP(우루과이 챔피언십 준결승) = 리그(수아레스 2022 준결승 선례)
    if cid in STATE: return "dc"
    if cid in ("CDR", "CGB", "FAC", "BRC", "JEMP", "JAPC", "HKFA", "INDP"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("GBCS", "USC"): return "df"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "CLQ": return "clq"
    if cid in ("UEQ", "ELQ", "UI"): return "elq"      # 인터토토 = 유로파 예선(토레스 선례)
    if cid in ("UEFA", "EL"):
        if r.startswith("group"): return "elg"
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                    # UEFA컵 3라운드·유로파 2라운드(32강)·16강·8강
    if cid == "AFCL":
        if r.startswith("quarter"): return "aclk"
        return "acl"
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"
    if cid == "CMER":   # 코파 메르코수르 = 남미 2부 대회 비중(주니뉴 선례)
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g):
    return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "") or g["round_schedule"]

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE and cid != "URUP": return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "CLQ", "UEFA", "UEQ", "UI", "EL", "ELQ"): return (1, 1)   # UEFA 2020-21까지
    if cid == "CDR": return (1, 1)          # 코파 델 레이 2018-19까지
    if cid == "CGB": return (1, 1)          # 잉글랜드 리그컵 준결승 2017-18까지
    if cid == "BRC": return (1, 0)          # 코파 두 브라질(네이마르·주니뉴 선례)
    if cid == "CMER": return (1, 0)         # 메르코수르(주니뉴 선례)
    if cid == "JAPC": return (1, 1)         # J리그컵(이니에스타 선례)
    if cid == "AFCL": return (0, 1)         # AFC 챔스 원정 다득점 없음(주니뉴 선례)
    if cid == "INDP": return (0, 1)         # 인도 슈퍼리그 2016 준결승: 원정 다득점 없이 연장(델리-케랄라 합산 2-2 연장·승부차기)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    """다른 차전 우리-상대 스코어: 다른 차전 리포트의 최종 스코어(홈·원정 id 기준)."""
    m = MI[gid]; oid = m["other_leg_id"]; club = G[gid]["club_id"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split(":"))
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    return (oh, oa) if side_of(gid) == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

# 2014.8 이후 Transfermarkt 도움(FotMob 경기 기록에 도움 표기 없음): 다른 출처 두 곳이 확인한 것만 넣음(judgments.md 4절).
# 값 = (판정, 근거). 'ok' = 넣음, 'no' = 확인 못 해 뺌.
POST_A = {
    ("2532246", "48"): ("ok", "사커킹 경기 기사(포를란 크로스 → 파블로 발리)·football-lab 경기별 도움"),
    ("2532262", "71"): ("no", "사커킹 경기 기사 1곳만(포를란 크로스 → 파블로)"),
    ("2532265", "75"): ("no", "카카우 골에 포를란 도움을 적은 기사 없음"),
    ("2613455", "57"): ("no", "몬테비데오 포르탈 기사 1곳만(여러 번 튄 뒤 포를란 크로스를 난데스가 발리)"),
    ("2613469", "57"): ("ok", "몬테비데오 포르탈·엘 옵세르바도르 기사(포를란 뒤꿈치 패스 → 아기아르)"),
    ("2613487", "72"): ("ok", "몬테비데오 포르탈·TUDN 기사(포를란 프리킥 크로스 → 아기레가라이 헤딩)"),
    ("2613500", "71"): ("ok", "몬테비데오 포르탈·엘 옵세르바도르·트리벨라 기사(포를란 돌파 뒤 패스 → 아기아르)"),
    ("2630122", "27"): ("ok", "몬테비데오 포르탈·엘 옵세르바도르 기사(포를란 코너킥 → 발데스 헤딩)"),
    ("2630122", "49"): ("no", "몬테비데오 포르탈 기사 1곳만, 그나마 '살라예타가 받지 못한 포를란의 크로스'를 이프란이 넣었다고 적음"),
    ("2630122", "80"): ("ok", "몬테비데오 포르탈·엘 옵세르바도르 기사(포를란 코너킥 → 팔라시오스)"),
    ("2662037", "1"): ("no", "몬테비데오 포르탈 기사 1곳만(포를란 코너킥 → 코스타 슈팅)"),
    ("2662044", "35"): ("no", "몬테비데오 포르탈 기사 1곳만(포를란 컷백 → 아기아르)"),
    ("2662049", "66"): ("ok", "몬테비데오 포르탈(포를란 크로스 → 무리요)·트리벨라·뉴스토크/SBS('해트트릭과 도움 2개')"),
    ("2662049", "82"): ("ok", "트리벨라·뉴스토크/SBS('해트트릭과 도움 2개', 무리요 두 골)"),
    ("2696968", "109"): ("no", "엘 옵세르바도르 기사 1곳만(포를란 크로스 → 올리베라 헤딩)"),
    ("2754534", "68"): ("ok", "ESPN 문자 중계·인도 슈퍼리그 공식 기사(포를란 → 데페데리코)"),
    ("2754577", "60"): ("ok", "ESPN 문자 중계·스포츠키다·켈나우 기사(포를란 크로스 → 바도치)"),
    ("2806592", "19"): ("ok", "ESPN 문자 중계·인도 슈퍼리그 공식 기사·IANS(포를란 프리킥 → 제르송 헤딩)"),
    ("2927352", "38"): ("ok", "킷치 구단 기사·offside.hk(포를란 패스 → 바도치)"),
    ("2995316", "90+2"): ("ok", "ESPN 문자 중계·worldfootball·offside.hk(포를란 패스 → 청친룽)"),
    ("2987034", "23"): ("no", "킷치 구단 기사는 산드루가 직접 만든 슈팅으로 적음, 도움 확인 못 함"),
}
assist_ok = {}
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if d >= GAP:
        v = POST_A.get((gid, e["minute"]))
        if not v: return "2014.8 이후 단일 출처(판정 없음)"
        if v[0] != "ok": return "2014.8 이후 단일 출처, 다른 출처로 확인 못 함(" + v[1] + ")"
    return None

MIN_FIX = {("2613469", "57"): "52"}     # (gameId, TM 분) -> 고친 분: 2015.9.19 라싱전 아기아르 골 = FotMob 52분·기사 "후반 7분"
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
        mi, dm = mins(MIN_FIX.get((gid, e["minute"]), e["minute"]))
        if is_a:
            why = assist_reason(e, ldate(g), gid)
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
    if sum(int(g["penGoals"] or 0) for _ in [0]) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

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
MANUAL_ALIAS = {"inter milan": "inter", "club atletico gimnasia y esgrima la plata": "club de gimnasia y esgrima la plata"}
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
if not TRACKED:   # 스크래치 복사본(git 없음): 원본 저장소 목록
    TRACKED = set(subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "frl.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting",
        "esporte", "ec", "foot", "ball", "regatas", "atletico", "associacao", "calcio", "sport", "sociedade", "esportiva", "olympique", "cd", "ud", "rcd", "sv", "as", "ss",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "paulista", "paulo", "ca", "cs", "deportivo", "deportes", "universidad", "san", "santa", "fk", "vfl", "bv"}
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

# 우루과이 2015-16 연간 순위 = 아페르투라 2015 + 클라우수라 2016 승점 합(득실차·다득점 순), Transfermarkt 두 표에서 계산(수아레스 '연간' 선례)
def tm_table(fn):
    t = open(os.path.join(RAW, "tables", fn), encoding="utf-8").read()
    i = t.find('<table class="items">'); out = {}
    for r in re.findall(r"<tr.*?</tr>", t[i:i + 80000], re.S):
        c = [HTML.unescape(re.sub("<[^>]+>", "", x)).strip() for x in re.findall(r"<td.*?</td>", r, re.S)]
        if len(c) >= 10 and c[0].isdigit():
            gf, ga = map(int, c[7].split(":")); out[c[2]] = (int(c[9]), gf - ga, gf)
    return out
_a, _c = tm_table("tm_URU1_2015.html"), tm_table("tm_URUC_2015.html")
if len(_a) != 16 or set(_a) != set(_c): sys.exit("우루과이 표 파싱 실패")
URU_ANNUAL = sorted(_a, key=lambda t: (-(_a[t][0] + _c[t][0]), -(_a[t][1] + _c[t][1]), -(_a[t][2] + _c[t][2])))
_ap = sorted(RANKS[("URU1", "AP2015")].values())     # Transfermarkt 표 이름(짧은 이름) → 순위표 정식 이름(같은 표, 같은 순서)
_rows = [t for t in _a]
URU_NAMES = {sh: full for sh, (r, n, full) in zip(_rows, _ap)}
for i, nm in enumerate(URU_ANNUAL):
    RANKS[("URUA", "2015-16")][key(URU_NAMES[nm])] = (i + 1, 16, URU_NAMES[nm])

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
    return half_up((tab[a] + tab[b]) / 2) if True else None, True

# J1 18팀 순위값(기존 선수 자료 2018~2023: 해마다 같은 값) → 연도 무관 순위표, 빈 순위는 이웃 값 가운데
def j1_table():
    c = collections.defaultdict(collections.Counter)
    for e in ENTS:
        m = re.match(r"^J1리그 (20\d\d) (\d+)위", e[12] or "")
        if m and m.group(1) in ("2018", "2019", "2020", "2022", "2023"): c[int(m.group(2))][e[2]] += 1
        m = re.match(r"^J1리그 2011 1위", e[12] or "")
        if m: c[1][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
J1 = j1_table()

ARG_T = {"ARG1": "아페르투라", "ARGC": "클라우수라"}
def rank_model(lg, season, r, n):
    if lg in ("ARG1", "ARGC"):
        return half_up(1583 + 63 * curve(r, n)), f"아르헨티나 1부 {ARG_T[lg]} {season[2:]} {r}위"
    if lg == "BRA1":
        return half_up(1598 + 63 * curve(r, n)), f"브라질 세리에 A {season} {r}위"
    if lg == "BRA2":
        return half_up(1370 + SD2 * curve(r, n)), f"브라질 세리에 B {season} {r}위"
    if lg == "URUA":
        return half_up(1540 + 63 * curve(r, n)), f"우루과이 1부 {season} 연간 {r}위"
    if lg == "JAP1":
        v, it = mid(J1, r)
        return v, f"J1리그 {season} {r}위"
    if lg == "JAP2":   # J2 = J1 평균 − 162, 흩어짐 SD2(토레스 선례; 기존 J2 2019 1위 1555 재현)
        return half_up(J2_MEAN + SD2 * curve(r, n)), f"J2리그 {season} {r}위"
    if lg in ("ES1", "GB1", "IT1"):
        name = {"ES1": "라리가", "GB1": "프리미어리그", "IT1": "세리에A"}[lg]
        m = ents_map(name, season); v, it = mid(m, r)
        if v is None: return None
        return v, f"{name} {season} {r}위"
    if lg == "ES2":
        m = ents_map("세군다", season); v, it = mid(m, r)
        if v is not None: return v, f"세군다 {season} {r}위"
        return half_up(1624 + SD2 * curve(r, n)), f"세군다 {season} {r}위"
    if lg == "GB2":   # 챔피언십 24팀 순위값(기존 선수 자료: 해마다 같은 값)
        m = {}
        for e in ENTS:
            mm = re.match(r"^챔피언십(?:\(2부\)|\(잉글랜드 2부\))? \d{4}-\d\d (\d+)위$", e[12] or "")
            if mm: m.setdefault(int(mm.group(1)), e[2])
        v, it = mid(m, r)
        if v is None: return None
        return v, f"챔피언십 {season} {r}위"
    if lg == "HGKG":   # 홍콩 1부(새 리그 수준): 인도 슈퍼리그 선례와 같은 1위 1300 ~ 꼴찌 1200 직선
        return half_up(1300 - 100 * (r - 1) / (n - 1)), f"홍콩 프리미어리그 {season} {r}위 (추정: 1위 1300~꼴찌 1200 직선)"
    if lg == "IND1":   # 델 피에로·말루다 선례: 1위 1300 ~ 꼴찌 1200 직선
        return half_up(1300 - 100 * (r - 1) / (n - 1)), f"인도 슈퍼리그 {season} {r}위 (추정: 1위 1300~꼴찌 1200 직선)"
    return None

# J1 평균: 18팀 J1 순위값을 평균 + 흩어짐 × 곡선에 맞춘 값(최소제곱) → J2 평균 = J1 평균 − 162
def _fit_j1():
    xs = [(curve(r, 18), v) for r, v in J1.items() if r != 1]
    n = len(xs); mx = sum(x for x, _ in xs) / n; my = sum(y for _, y in xs) / n
    s = sum((x - mx) * (y - my) for x, y in xs) / sum((x - mx) ** 2 for x, _ in xs)
    return my - s * mx, s
J1_MEAN, J1_SD = _fit_j1()
J2_MEAN = J1_MEAN - 162

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
ARG_USE = collections.defaultdict(set)

def seasons_for(cid, d, club):
    y = d[:4]
    if cid in ("ARG1", "ARGC", "CMER", "BRA1", "BRC", "BRRS", "BRga", "RS2f", "CLI", "JAP1", "JAP2", "JAPC", "JEMP", "AFCL", "IND1", "INDP"):
        return [y]
    if cid in ("URU1", "URUC", "URUP"): return ["2015-16"]
    if cid in ("HGKG", "HKFA"): return ["2017-18"]
    return [eu(d)]

def lg_cands(cid, d, club):
    y = int(d[:4]); mo = int(d[5:7])
    if cid in ("ARG1", "ARGC"):
        return [("ARGC" if cid == "ARGC" else "ARG1", ("CL" if cid == "ARGC" else "AP") + str(y))]
    if cid in ("BRA1", "BRC", "BRRS", "BRga", "RS2f"): return [("BRA1", str(y)), ("BRA2", str(y))]
    if cid in ("JAP1", "JAPC", "JEMP", "AFCL"): return [("JAP1", str(y)), ("JAP2", str(y))]
    if cid == "JAP2": return [("JAP2", str(y))]
    if cid in ("URU1", "URUC", "URUP"): return [("URUA", "2015-16")]
    if cid in ("IND1", "INDP"): return [("IND1", str(y))]
    if cid in ("HGKG", "HKFA"): return [("HGKG", "2017-18")]
    s = eu(d)
    return [("ES1", s), ("GB1", s), ("IT1", s), ("ES2", s), ("GB2", s)]

NO_SAME = {"URU1", "URUC", "URUP", "ARG1", "ARGC", "BRA1", "BRRS", "BRga", "RS2f", "BRC", "JAP1", "JAP2", "JEMP", "JAPC", "IND1", "INDP", "HGKG", "HKFA"}
def opp_elo(o, d, cid, club):
    cand, vals = same_match(o, d) if cid not in NO_SAME else ([], set())
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    seasons = seasons_for(cid, d, club)
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for lg, s in lg_cands(cid, d, club):
        t = RANKS.get((lg, s), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s, r, n)
            if res and res[0]:
                if lg in ("ARG1", "ARGC"): ARG_USE[(k, d[:4])].add(res)
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

# ---------------------------------------------------------------- 직접 추정(MAN)
C4 = 1200; C3 = 1253
man("CD Universidad Católica", "2000", 1480, "칠레 1부 2000 6위 (추정, 다른 선수 자료 우니베르시다드 카톨리카 2008 1480과 같은 수준)")
man("CSD Colo-Colo", "2001", 1500, "칠레 1부 2001 4위 (추정, 다른 선수 자료 콜로콜로 2011 칠레 상위 팀 1500과 같음)")
man("Rangers FC", "2005-06", 1620, "스코틀랜드 2005-06 3위 (추정, 다른 선수 자료 레인저스 1620과 같음)")
man("NK Maribor", "2006-07", 1400, "슬로베니아 2006-07 3위 (추정, 다른 선수 자료 마리보르 1위 1420보다 조금 낮게)")
man("CF Gloria Bistrita", "2007-08", 1400, "루마니아 2007-08 10위 (추정, 다른 선수 자료 루마니아 중위권 1400과 같음)")
man("Granada 74 CF", "2007-08", half_up(1624 + SD2 * curve(21, 22)), "세군다 2007-08 21위 (추정, 순위는 영어 위키백과)")
man("Orihuela CF", "2008-09", 1350, "스페인 3부(세군다 B) 2008-09 3조 11위 (추정, 다른 선수 자료 스페인 3부 1350과 같음)")
man("Galatasaray", "2009-10", 1650, "튀르키예 2009-10 3위 (추정, 다른 선수 자료 갈라타사라이 상위권 1620~1680 사이)")
man("Strømsgodset IF", "2011-12", 1480, "노르웨이 2011 2위 (추정, 다른 선수 자료 노르웨이 2위 1480과 같음)")
for o, r in [("EC Pelotas", 10), ("Esportivo", 7), ("EC São Luiz", 3), ("Canoas SC", 16), ("Esporte Clube Juventude", 5)]:
    man(o, "2013", C4, f"브라질 4부 이하 2013 (추정, 캄페오나투 가우슈 2013 종합 {r}위; 세리에 C 참가 팀 아님, 다른 선수 자료 4부 이하 1200과 같음)")
man("Rio Branco Football Club (AC)", "2013", C3, "브라질 세리에 C 2013 (추정, 1조 11위; 다른 선수 자료 세리에 C 1253과 같음)")
man("Salgueiro AC", "2013", C4, "브라질 4부 이하 2013 (추정, 세리에 C 참가 팀 아님; 다른 선수 자료 4부 이하 1200과 같음)")
man("Buriram United", "2014", 1380, "태국 1부 2014 1위 (추정, 다른 선수 자료 태국 1위 1380과 같음)")
man("Shandong Luneng Taishan", "2014", 1526, "중국 슈퍼리그 2014 4위 (추정, 다른 선수 자료 중국 슈퍼리그 2012 4위 값과 같음)")
man("Guangzhou Evergrande", "2014", 1560, "AFC 챔스 우승팀·중국 (추정)")

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, g["club"])
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)

# 아르헨티나: 같은 팀이 한 해 아페르투라·클라우수라에서 값이 다르면 평균(팔카오 선례; 통합표 시즌 키가 연도)
for (k, y), vs in ARG_USE.items():
    if len({v[0] for v in vs}) > 1:
        vv = sorted(vs, key=lambda v: v[1])
        avg = half_up(sum(v[0] for v in vv) / len(vv))
        lv = f"아르헨티나 1부 {y} (추정, " + "·".join(re.sub(r"^아르헨티나 1부 ", "", v[1]) for v in vv) + " 값 평균)"
        for r in E:
            if key(r[1]) == k and r[9][:4] == y and r[12].startswith("아르헨티나 1부"):
                r[2], r[12] = avg, lv
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
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print("score mismatches", SCORE_MISMATCH)
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    sys.exit(0)

# @OUT@
# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["forlan_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "penalty" in (f["goalDescriptionKey"] or "").lower() or "pen" in (f["suffix"] or "").lower()
        a = mins(t["minute"])[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
        if tp != fp or abs(a - b) > 1: FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))
FM_N = sum(1 for gid in EVS if gid in G and gid in FME and any(e["scorer_id"] == ME for e in EVS[gid]))
FM_G = sum(1 for gid in EVS if gid in G and gid in FME for e in EVS[gid] if e["scorer_id"] == ME and not is_og(e))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None): d.append(f"단판/합산 {a[7]}{a[14] if len(a) > 14 else ''}/{b[7]}{b[14] if len(b) > 14 else ''}")
    if a[10] != b[10]: d.append("연장")
    return d
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.match(r"^Diego Forl[aá]n$", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(포를란 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("포를란 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x[1], r[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm[1], m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 포를란 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
# 동료 골에 포를란 도움이 있는데 동료 파일에는 도움 없음(득점자 = 동료 선수)
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]
# @OUT2@
