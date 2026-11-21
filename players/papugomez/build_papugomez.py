#!/usr/bin/env python3
"""파푸 고메스 (Alejandro Darío 'Papu' Gómez, Transfermarkt 20005): raw/ -> papugomez.json + src/data/pap.js (판정 근거는 judgments.md)

  python3 players/papugomez/build_papugomez.py [복사본 루트]     # 파일 쓰기
  python3 players/papugomez/build_papugomez.py --debug           # Elo 출처
  python3 players/papugomez/build_papugomez.py --stat            # 요약·동료 대조·점검

입력: raw/tm_games.csv(출전·분·날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(2010-11 이후 대조), raw/ranks.txt·raw/tables(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git 추적 파일: 같은 경기·동료 대조).
아르헨티나 부분(대회 코드·합산·아르헨티나 1부 모형·한 해 두 대회 평균)은 리켈메(build_riquelme.py), 유럽 부분은 일리치치(build_ilicic.py) 방식.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime, html as HTML

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
if ARGS: ROOT = os.path.abspath(ARGS[0])
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "pap.js")
OUT_JSON = os.path.join(HERE, "papugomez.json")
ME = "20005"
ME_KO = "파푸 고메스"
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
# raw date_local: 아르헨티나 클럽 경기 = TM API UTC 시각을 아르헨티나 시간(UTC−3)으로 바꾼 날짜(남미 원정·스루가 뱅크(일본)도 경기지 날짜와 같음),
# 유럽 = TM 리포트 날짜, UAE = 두바이 시간. UTC 22:00 정각(중부 유럽 자정) 경기도 실제 킥오프로 봄(2009.10.16 로사리오 센트랄전: 디아리오 데 쿠요 10.16 기사).
def ldate(g): return g["date_local"]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
# 연장 없이 바로 승부차기로 간 코파 수다메리카나 두 경기: Transfermarkt는 경기 시간 120분으로 셈 → 90분 기준(대회 규정·RSSSF 'p' 표기, 연장 표기 없음)
MIN_FIX = {"975666": (90, "2009.11.4 수다메리카나 8강 2차전 리버 플레이트(몬테비데오)전: 선발 풀타임, Transfermarkt 120분 → 90분(1-1 원정골 같아 연장 없이 승부차기, RSSSF)"),
           "994412": (19, "2007.11.14 수다메리카나 준결승 2차전 리버 플레이트전: Transfermarkt 49분(120분 경기에서 71분 교체 투입으로 계산) → 90분 경기 기준 19분(0-0·0-0 뒤 연장 없이 승부차기 2-4, RSSSF)")}
def minutes(g):
    if g["gameId"] in MIN_FIX: return MIN_FIX[g["gameId"]][0]
    return int(g["playedMinutes"])

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ARG1", "ARGC", "IT1", "IT2", "ES1", "UKR1", "UAE2"}
def rnd_of(g): return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("CIT", "CDR", "UKRP"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("RECO", "SURU"): return "df"      # 레코파 수다메리카나(리켈메·호나우지뉴 선례)·스루가 뱅크 챔피언십(수다메리카나 우승팀 vs J리그컵 우승팀 단판) = 슈퍼컵류
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("semi"): return "clsf"
        return "clk"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"                               # 예선(2008 미네로스)·조별
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
    if r.startswith("group") or "matchday" in r: return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    if cid in ("CL", "EL", "ELQ"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid == "CIT": return (1, 1) if d < "2022-07-01" else (0, 1)
    if cid == "CDR": return (1, 1) if d < "2019-07-01" else (0, 1)
    if cid == "CLI": return (1, 0)                 # 2005년부터 원정 다득점, 연장 없이 승부차기(리켈메 선례)
    if cid == "CS": return (1, 0)                  # 원정 다득점, 연장 없음(2007 결승 4-4 원정 다득점 우승·2009 8강 승부차기, RSSSF)
    if cid == "RECO": return (0, 1)                # 리켈메 자료와 같은 경기·같은 규칙(추정)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g = G[gid]
    if gid not in MI: return "h" if g["venue"] == "H" else "a"
    m = MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid); oid = m["other_leg_id"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split(":"))
        club = G[gid]["club_id"]
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 " + gid)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 골·도움 판정 표
# 2014.8 이후 Transfermarkt에만 있는 도움(FotMob 경기 기록에 도움 없음): gameId|분 -> 근거(넣음) / None(뺌)
POST_GAP = {
    "2515985|40": None,   # 2015.1.21 코파 이탈리아 피오렌티나전 비안키: football-italia·Sports Mole·Forza Italian Football 기사 모두 도움자 언급 없음
    "2604153|75": "Sports Mole 경기 기사('turned home Alejandro Gomez's low cross with the outside of his boot')·블리츠쿠오티디아노 문자 중계('servitogli … da Gomez')",
    "3229326|72": None,   # 2019.12.22 밀란전 일리치치 두 번째 골: 기사들은 일리치치 감아차기 골로만 적음(고메스 프리킥 도움 언급 없음)
}
# FotMob에만 있는 도움(Transfermarkt는 도움자 없음/다른 선수): gameId|FotMob 골 뒤 스코어 -> (근거|None, 분, 득점자)
FM_ONLY = {
    "3081312|1-1": ("Football Italia 경기 기록('Pasalic 24, assist Papu Gómez')·World Soccer Talk 경기 기사('equaliser on 24 minutes off a Papu Gomez cross')", 24, "Mario Pašalić"),
    "2897248|1-0": (None, 50, "Remo Freuler"),   # 2017.10.25 베로나전: Footmercato(Opta 계열)만 고메스 도움, 판타가제타 공식 도움은 프로일러·고젠스만 → 2곳 확인 못 함
    "2251303|1-1": (None, 52, "Nicolás Spolli"), # 2012.9.26 아탈란타전(2014 이전): Transfermarkt는 로디 코너킥 도움 → Transfermarkt 기준
}
# Transfermarkt에 없는 골(경기별 출처로 확인): gameId -> (분, 표시, 골 전 우리-상대, PK, 근거)
ADD_GOAL = {"1003116": (89, 0, (1, 2), 0, "2010.3.20 콜론전 89분 동점골: Transfermarkt 리포트는 콜론 선수 리카르도 고메스(Ricardo Gómez)로 적었지만 산로렌소 기록 사이트 estadisticascasla.com 경기 기록(90분 고메스 골, 91분 유니폼을 벗어 퇴장)·디아리오 데 쿠요 경기 기사('El Papu los salvó', 정규시간 마지막 분 2-2 동점골)·영어·이탈리아어 위키백과 시즌 합계(리그 7골)가 파푸 고메스 골로 셈. 분은 Transfermarkt 89분")}

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
    if t.startswith("Handball by Papu"): return "고메스 핸드볼로 내준 PK(도움 아님)"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

raw_rows, judg, post_gap_log, min_fix = [], [], [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0); d = ldate(g)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == ME and e["own_goal"] != "1"
        is_a = e["assist_id"] == ME
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        f = fm_ev(gid, e["score_home_away_after"])
        tag = f"{gid}|{mins(e['minute'])[0]}"
        if dm == 0 and mi in (45, 90) and f and f["overloadTime"] and int(f["time"]) == mi and int(f["overloadTime"]) > 0:
            dm = f"{mi}+{int(f['overloadTime'])}"; min_fix.append((gid, ldate(g), opp(g), e["minute"], dm)); mi += int(f["overloadTime"])   # 일리치치 선례: Transfermarkt 90분, FotMob 추가시간
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], why))
            elif d >= GAP and not (f and f["papu_assist"] == "1"):
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
# FotMob 단독 도움
fm_only_seen = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["papu_assist"] != "1" or f["pen_shootout_event"] == "True": continue
        tm = [e for e in EVS[gid] if e["score_home_away_after"] == f["newScore_home_away"]]
        if any(e["assist_id"] == ME for e in tm): continue
        k = f"{gid}|{f['newScore_home_away']}"
        if k not in FM_ONLY: sys.exit("[판정 필요] FotMob 단독 도움 " + k)
        why, mi, sc = FM_ONLY[k]; g = G[gid]; side = side_of(gid)
        fm_only_seen.append((gid, ldate(g), opp(g), mi, sc, why))
        if why:
            h, a = map(int, f["newScore_home_away"].split("-"))
            if f["isHome"] == "True": h -= 1
            else: a -= 1
            gf, ga = (h, a) if side == "h" else (a, h)
            raw_rows.append(("a", gid, mi, 0, gf, ga, 0, sc))
        else:
            judg.append(("도움 제외(FotMob 단독)", ldate(g), opp(g), str(mi), sc, "FotMob에만 있음, 다른 출처 2곳 확인 못 함" if ldate(g) >= GAP else "2014 이전: Transfermarkt는 다른 선수 도움"))
for gid, g in G.items():
    pm = FPM.get(g["fotmobMatchId"])
    if pm and int(pm["assists"] or 0) > int(g["assists"] or 0):
        fm_only_seen.append((gid, ldate(g), opp(g), "FotMob 선수 경기 목록 도움", pm["assists"], g["assists"]))
for gid, (mi, dm, (gf, ga), pk, why) in ADD_GOAL.items():
    raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))
# 골 수 대조(API)
cnt_ = collections.Counter((r[1], r[0]) for r in raw_rows)
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0) + (1 if gid in ADD_GOAL else 0): sys.exit("골 수 불일치 " + gid)
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
    if b in ("hon.js", "pap.js") or b not in TRACKED: continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting", "calcio",
        "atletico", "ca", "us", "as", "ss", "ssc", "acf", "olympique", "fk", "sv", "nk", "cd", "bc", "milan", "inter", "madrid", "fbc",
        "racing", "arsenal", "juniors", "plate", "river", "nacional", "independiente", "estudiantes", "union", "boca", "gimnasia", "esgrima",
        "lorenzo", "almagro", "san", "deportivo", "universidad", "rosario", "sarsfield", "tomba", "csc", "scc"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
SA_DOM = {"ARG1", "ARGC", "CLI", "CS", "RECO", "SURU"}
def same_match(o, d, cid):
    if cid in SA_DOM: cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    else: cand = [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
def s_norm(s):
    if "/" in s:
        a, b = s.split("/"); y = 2000 + int(a) if int(a) < 50 else 1900 + int(a); return f"{y}-{b}"
    return s
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        lg = p[0].split("#")[0]
        RANKS[(lg, s_norm(p[1]))][key(p[4])] = (int(p[2]), int(p[3]), p[4])

# 아페르투라 2008: 승점 같은 세 팀 결정전 뒤 최종 순위 보카 1·티그레 2·산로렌소 3(리켈메 자료와 같음)
RANKS[("ARG1", "2008-09")][key("Club Atlético Tigre")] = (2, 20, "Club Atlético Tigre")
RANKS[("ARG1", "2008-09")][key("CA San Lorenzo de Almagro")] = (3, 20, "CA San Lorenzo de Almagro")

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
        m = pat.match(str(e[12] or ""))
        if m: c[int(m.group(1))][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
def mid(tab, r):
    if r in tab: return tab[r]
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None
    return half_up((tab[max(lo)] + tab[min(hi)]) / 2)

# 우크라이나 1부 2013-14: 셰브첸코 모형(리그 평균 = 1473 + 23.33 × (앞뒤 3시즌 국가 계수 평균 − 7.333) − 73, 흩어짐 119).
# 계수 kassiesa.net method4: 2012-13 9.500, 2013-14 7.833, 2014-15 10.000 → 평균 9.111 → 리그 평균 1441
UA_MEAN_1314 = 1473 + 23.33 * ((9.5 + 7.833 + 10.0) / 3 - 7.3333) - 73
# UAE 2부(퍼스트 디비전): UAE 프로리그 평균 1440(이니에스타 모형) − 162(1·2부 차, 일본 J2 선례), 흩어짐 2부(SD2)
UAE2_MEAN = 1440 - 162

def arg_tour(lg, season):
    y0 = int(season[:4])
    return ("아페르투라", y0) if lg == "ARG1" else ("클라우수라", y0 + 1)

def rank_model(lg, season, r, n):
    if lg in ("ARG1", "ARGC"):
        t, y = arg_tour(lg, season)
        return half_up(1583 + 63 * curve(r, n)), f"아르헨티나 1부 {t} {y} {r}위"
    if lg == "BRA1":
        return half_up(1598 + 63 * curve(r, n)), f"브라질 세리에 A {season} {r}위"
    if lg == "UKR1":
        return half_up(UA_MEAN_1314 + 119 * curve(r, n)), f"우크라이나 1부 {season} {r}위 (추정)"
    if lg == "UAE2":
        return half_up(UAE2_MEAN + SD2 * curve(r, n)), f"UAE 2부(퍼스트 디비전) {season} {r}위 (추정, 11월 중순 현재 순위)"
    if lg == "ES1":
        v = mid(ents_map("라리가", season), r)
        return (v, f"라리가 {season} {r}위") if v else None
    if lg == "IT1":
        v = mid(ents_map("세리에A", season), r)
        return (v, f"세리에A {season} {r}위") if v else None
    if lg == "IT2":
        v = mid(ents_map("세리에B", season), r)
        return (v, f"세리에B {season} {r}위") if v else None
    return None

def eu(d):
    if "2020-07-01" <= d < "2020-09-01": return "2019-20"     # 코로나로 미뤄진 2019-20 세리에A 막바지·챔스 8강
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
man("Universitario de Deportes", "2009", 1400, "페루 1부 2009 우승팀 (추정, 다른 선수 자료 페루 상위 팀 알리안사 리마 1400과 같음)")
man("CD Motagua Tegucigalpa", "2008", 1400, "온두라스 1부 (추정, 다른 선수 자료 모타과 2011-12·2022-23 1400과 같음)")
man("Deportivo Guadalajara", "2007-08", half_up(1604.25 + 73.41 * curve(2, 18)), "멕시코 1부 2007-08 아페르투라·클라우수라 합산 2위 (추정: 조별 표 승점 합, 공식 순위표 아님)")   # 리켈메 멕시코 합산 방식(아틀라스 15위 1538과 같은 표)
man("GNK Dinamo Zagreb", "2021-22", 1615, "크로아티아 2021-22 1위 (추정, 다른 선수 자료 디나모 자그레브 2020-21 1위 1620·2022-23 1위 1610의 가운데)")
man("FK Sarajevo", "2018-19", 1400, "보스니아 헤르체고비나 2018-19 1위 (추정, 다른 선수 자료 보스니아 상위 팀 젤레즈니차르 2002-03 2위 1400과 같음)")

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
ARG_USE = collections.defaultdict(set)
CAL = {"ARG1", "ARGC", "CLI", "CS", "RECO", "SURU"}

def arg_cands(d):
    y = int(d[:4]); mo = int(d[5:7])
    if mo <= 7: return [("ARGC", f"{y-1}-{str(y)[2:]}")]
    return [("ARG1", f"{y}-{str(y+1)[2:]}")]

def lg_cands(cid, d, o, sid):
    y = d[:4]
    if cid in ("ARG1", "ARGC"): return [(cid, f"{sid}-{str(int(sid) + 1)[2:]}")]
    if cid in CAL: return arg_cands(d) + [("BRA1", y)]
    s = eu(d)
    return [("ES1", s), ("IT1", s), ("IT2", s), ("UKR1", s), ("UAE2", s)]

def opp_elo(o, d, cid, sid):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    seasons = [d[:4], eu(d)] if cid in CAL else [eu(d), d[:4]]
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    for lg, s in lg_cands(cid, d, o, sid):
        t = RANKS.get((lg, s), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s, r, n)
            if res and res[0]:
                if lg in ("ARG1", "ARGC"): ARG_USE[(k, d[:4])].add(res)
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, g["seasonId"])
    t = tie_of(gid)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if t: row.append(t)
    E.append(row)

# 아르헨티나: 같은 팀이 한 해 두 대회 값이 다르면 평균(통합표 시즌 키가 연도; 리켈메·포를란·팔카오 선례)
ARG_AVG = []
for (k, y), vs in ARG_USE.items():
    if len({v[0] for v in vs}) > 1:
        vv = sorted(vs, key=lambda v: v[1])
        avg = half_up(sum(v[0] for v in vv) / len(vv))
        lv = f"아르헨티나 1부 {y} (추정, " + "·".join(re.sub(r"^아르헨티나 1부 ", "", v[1]) for v in vv) + " 값 평균)"
        ARG_AVG.append((k, y, avg, [v[0] for v in vv]))
        for r in E:
            if key(r[1]) == k and r[9][:4] == y and str(r[12]).startswith("아르헨티나 1부"):
                r[2], r[12] = avg, lv
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
    print("평균:", ARG_AVG)
    sys.exit(0)

exec(open(os.path.join(HERE, "out_papugomez.py"), encoding="utf-8").read())
