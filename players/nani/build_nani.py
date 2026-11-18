#!/usr/bin/env python3
"""나니 (Transfermarkt 33706): raw/ -> nani.json + src/data/nan.js (판정 근거는 judgments.md)

  python3 players/nani/build_nani.py                 # 파일 쓰기
  python3 players/nani/build_nani.py --debug         # Elo 출처 로그
  python3 players/nani/build_nani.py --stat          # 요약·동료 대조·FotMob 대조
  python3 players/nani/build_nani.py --ties          # 합산 행·판정
  python3 players/nani/build_nani.py --root=<복사본>  # 그 복사본의 src/data·elo 사용(검증용)

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv·fotmob_tm_map.csv(FotMob), raw/ranks.txt(Transfermarkt 순위표),
      mls_overall_ranks.txt(MLS 전체 순위: 2019·2021 FotMob 서포터스 실드 표, 2020 영어 위키백과 승점률 표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조).
뼈대는 벨한다 build_belhanda.py(니앙·사바니에 계열).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
GITROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "nan.js")
OUT_JSON = os.path.join(HERE, "nani.json")
ME = "33706"
ME_KO = "나니"

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
FM_MAP = {r["tm_gameId"]: r["fotmob_matchId"] for r in rd("fotmob_tm_map.csv")}
FM_PM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 날짜
DATE_FIX = {}   # date_local_computed(클럽 현지 시간: 올랜도 뉴욕, 멜버른, 악퇴베, 클럽 월드컵 요코하마)를 그대로 씀
def ldate(g): return DATE_FIX.get(g["gameId"], g["date_local_computed"])
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 판정 표
# 2016.5.26 튀르키예컵 결승 갈라타사라이전: TM API 출전 0분(선발). 리포트 선발 명단에 있고 교체 기록 없음, FotMob 경기 기록에 90+6분 퇴장 → 90분
MIN_FIX = {"2689315": 90}
MIN_EST = {}
GAP = "2014-08-01"              # 이 날짜 전 도움은 Transfermarkt 리포트 단일 출처 허용(클로제·인시녜·벨한다 선례)
# 2014-08-01 뒤 TM 도움 중 FotMob 경기 이벤트에 도움자가 없지만 FotMob 선수 경기 목록의 그 경기 나니 도움 수가 TM과 같은 경기
FM_PM_OK = {"3197707"}           # 2019.7.10 US 오픈컵 8강 NYCFC전 61분 뮬러(FotMob 선수 경기 목록 도움 1)
ADD_CONFIRMED = {
    ("3123518", "73"): "2018.11.24 타사 드 포르투갈 비우데모이뉴스전 73분 디아비 골: Bola na Rede 경기 기사('브루누 페르난드스와 2대1을 주고받은 나니가 디아비에게 도움')·Observador 문자중계(나니가 왼쪽에서 받아 바로 크로스, 디아비가 마무리)",
    ("4835157", "74"): "2026.3.7 토볼전 74분 오르데츠 골(나니 데뷔전): sport24.ru('나니가 이반 오르데츠에게 도움')·카즈프라브다 경기 기사(나니의 패스로 오르데츠가 마무리)·yuz.uz(측면 크로스를 오르데츠가 머리로)",
}
UNCONFIRMED = {
    ("2466874", "15"): "2014.10.26 마리티무전 15분 주앙 마리우 골: Bola na Rede 기사('이 경기에서 도움 2개') 1곳뿐이고 이 골 장면 설명이 없음",
    ("2466874", "42"): "2014.10.26 마리티무전 42분 파울루 올리베이라 헤더: Bola na Rede 기사(나니 코너킥) 1곳뿐",
    ("2469530", "49"): "2014.11.9 파수스 드 페헤이라전 49분 몬테로 골: Observador 기사는 몬테로가 30m 앞에서 바로 찬 골로만 적음",
    ("2480183", "67"): "2015.1.18 히우 아브전 67분 주앙 마리우 골: Bola na Rede 기사에 도움자 없음, 다른 출처 못 찾음",
    ("2498722", "52"): "2015.2.22 질 비센트전 52분 다나카 골: 다른 출처 못 찾음",
    ("2526209", "30"): "2015.4.4 파수스 드 페헤이라전 30분 슬리마니 골: 다른 출처 못 찾음",
    ("3119165", "42"): "2018.10.20 타사 드 포르투갈 로우르스전 42분 브루누 페르난드스 골: Bola na Rede·Record는 브루누가 페널티 지역 앞에서 공을 받아 찬 중거리 골로만 적음(도움자 없음)",
    ("4238959", "89"): "2024.1.17 튀르키예컵 24 에르진잔스포르전 89분 미쇼 골: FotMob 선수 경기 목록 도움 0, DHA 계열 기사(밀리예트·파나틱)는 미쇼가 페널티 지역에 들어가자마자 찬 골로만 적음",
    ("4835006", "71"): "2026.6.14 알타이전 71분 오르데츠 골: NUR.KZ 기사 1곳만 나니 도움",
    ("4835030", "45+1"): "2026.7.5 제티수전 45+1분 오르데츠 골: 다른 출처 못 찾음",
    ("4835076", "77"): "2026.8.15 카이사르전 77분 소사 골: 다른 출처 못 찾음",
    ("4835141", "90+4"): "2026.10.31 토볼전 90+4분 예를라노프 골: 다른 출처 못 찾음",
}
EXCL_A = {}
# 골 판정으로 뺀 TM 골: (gameId, 분 표기) -> 이유
EXCL_G = {
    ("961085", "33"): "2010.1.31 아스널전 33분: BBC·스카이스포츠·알자지라 경기 기사와 다수 기록은 나니 크로스를 알무니아가 자기 골문에 넣은 자책골(TM·포르투갈어 위키백과는 나니 골, 영어 위키백과는 시즌 3골로 자책골 처리)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"PO1", "GB1", "TR1", "ES1", "IT1", "MLS1", "AUS1", "KAS1"}
CUPS = {"POPO", "POCP", "FAC", "CGB", "TRP", "CDR", "CIT", "MLSP", "FFAC", "KAZP"}
SUPER = {"GBCS", "USC"}
MLS_LIKE = {"MLS1", "MLSP", "USSP", "POUS", "USMX"}
KAZ = {"KAS1", "KAZP"}
UEFA_C = {"CL", "CLQ", "EL", "ELQ", "ECLQ", "UEFA", "USC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in SUPER: return "df"                              # 커뮤니티 실드·UEFA 슈퍼컵 = 국내컵 결승 비중(문서 3절)
    if cid == "KLUB": return "cwc"
    if cid == "POUS": return "mlp"                            # MLS 컵 플레이오프(2020 와일드카드·1라운드·콘퍼런스 준결승, 2021 1라운드 — 모두 단판)
    if cid == "USMX": return "lcg" if r.startswith("group") else "lck"   # 리그스컵 2021 8강
    if cid == "USSP":                                         # MLS is Back 2020: 조별 3경기는 정규 리그 순위에 들어감 → 리그, 토너먼트는 리그 주관 컵(국내컵 단계)
        if r.startswith("group"): return "lg"
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round") or r.startswith("6th round"): return "dk"   # FA컵 6라운드(재경기 포함) = 8강
        return "dc"
    if cid in ("CLQ",): return "clq"
    if cid == "ELQ": return "elq"
    if cid == "UEFA": return "elq"                            # UEFA컵 1라운드(2009년 이전) = 유로파 예선
    if cid == "ECLQ": return "ecq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                          # 32강('Second Round' 2014-15·'intermediate stage')·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g): return "leg" in g["round"].lower()
def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0                         # 챔스·유로파 조별, 튀르키예컵 2015-16 조별, MLS is Back 조별
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "CLQ", "EL", "ELQ", "ECLQ", "UEFA"):
        return (1, 1) if d < "2021-07-01" else (0, 1)         # UEFA 원정 다득점 2020-21까지
    if cid == "TRP": return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid == "CGB": return (1, 1) if d < "2018-07-01" else (0, 0)   # 잉글랜드 리그컵 준결승 2017-18까지 원정 다득점·연장
    if cid in ("CDR", "CIT", "POPO"): return (1, 1)           # 코파 델 레이 2018-19까지, 코파 이탈리아 2021-22까지, 타사 준결승(브루누·팔카오 선례)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

TIES = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
def other_leg(gid):
    t = TIES[gid]; oid = t["other_leg_id"]
    if oid in G and G[oid]["gameState"] != "penalty_shootout":
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    a, b = map(int, t["other_leg_final"].split(":"))        # 리포트의 다른 차전 스코어는 이 경기 홈 팀 기준으로 적힘
    return (a, b) if side_of(gid) == "h" else (b, a)

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

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FME.items():
    for r in evs:
        if r["nani_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))
def pm_assists(gid):
    p = FM_PM.get(FM_MAP.get(gid, ""))
    return int(p["assists"]) if p and p["assists"] not in ("", None) else None

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
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e): judg.append(("본인 자책골(골 아님)", ldate(g), opp(g), e["minute"]))
        if is_a and sd != side and not is_og(e):
            sys.exit("상대 골 도움 칸에 나니 " + gid)
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        k = (gid, e["minute"])
        if is_g and k in EXCL_G:
            judg.append(("골 제외(상대 자책골로 봄)", ldate(g), opp(g), e["minute"], EXCL_G[k])); continue
        if is_a:
            why = assist_reason(e) or EXCL_A.get(k)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why, e["assist_type"])); continue
            if ldate(g) >= GAP:
                base = int(e["minute"].split("+")[0])
                hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - mi) <= 3 or abs(t - base) <= 3]
                if hit and USED_FM[gid] < len(FM_ASSIST[gid]):
                    USED_FM[gid] += 1; src = "TM∩FotMob 경기 이벤트"
                elif gid in FM_PM_OK and pm_assists(gid) == sum(1 for x in EVS[gid] if x["assist_id"] == ME and x["scorer_id"] != ME):
                    src = "TM∩FotMob 선수 경기 목록"
                elif k in ADD_CONFIRMED:
                    src = "TM + 다른 출처 2곳"
                elif k in UNCONFIRMED:
                    judg.append(("도움 제외(단일 출처 미확인)", ldate(g), opp(g), e["minute"], e["scorer"], UNCONFIRMED[k], e["assist_type"])); continue
                else:
                    UNDECIDED.append((gid, ldate(g), opp(g), e["minute"], e["scorer"], e["assist_type"], FM_ASSIST.get(gid), pm_assists(gid))); continue
            else:
                src = "2014.8 전 Transfermarkt"
            SRC_A[src] += 1
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk:
                if e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
                judg.append(("PK 아님(PK가 막힌 뒤 리바운드 골)", ldate(g), opp(g), e["minute"], e["goal_desc"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

for t in list(ADD_CONFIRMED) + list(UNCONFIRMED) + list(EXCL_A):
    if not any(x["minute"] == t[1] and x["assist_id"] == ME for x in EVS.get(t[0], [])): sys.exit("판정 표 키가 TM 도움과 맞지 않음 " + str(t))
for t in EXCL_G:
    if not any(x["minute"] == t[1] and x["scorer_id"] == ME for x in EVS.get(t[0], [])): sys.exit("골 제외 키가 TM 골과 맞지 않음 " + str(t))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    exg = sum(1 for t in EXCL_G if t[0] == gid)
    if cnt_[(gid, "g")] + exg != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fin = MI[gid]["final"]
    fh, fa = map(int, fin.split(":")) if fin else (h, a)
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
GA_GAMES = {r[1] for r in raw_rows}
if [x for x in SCORE_MISMATCH if x[0] in GA_GAMES]: sys.exit("골·도움 경기 리포트 불완전 " + str(SCORE_MISMATCH))

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
MANUAL_ALIAS = {norm("New York Red Bulls"): norm("Red Bull New York"), norm("Minnesota United"): norm("Minnesota United FC"),
                norm("Atlanta United"): norm("Atlanta United FC"), norm("Chicago Fire FC"): norm("Chicago Fire"),
                norm("Montreal Impact"): norm("CF Montréal"), norm("Orlando City"): norm("Orlando City SC"),
                norm("Seattle Sounders FC"): norm("Seattle Sounders FC"), norm("LA Galaxy"): norm("Los Angeles Galaxy"),
                norm("Columbus Crew SC"): norm("Columbus Crew"), norm("Houston Dynamo FC"): norm("Houston Dynamo"),
                norm("Vancouver Whitecaps"): norm("Vancouver Whitecaps FC"), norm("Real Salt Lake"): norm("Real Salt Lake City"),
                norm("DC United"): norm("D.C. United")}
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
    if b in ("hon.js", "nan.js") or "src/data/" + b not in TRACKED: continue
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
        "new", "york", "vitoria", "red", "bull", "bulls", "manchester", "west", "hotspur", "wanderers", "rovers", "town", "albion"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, collections.Counter((x[2], x[12]) for b, x in cand)

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[0].startswith("MLS1"): continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
with open(os.path.join(HERE, "mls_overall_ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) >= 5: RANKS[("MLS", p[1])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
RANK_FIX = {}

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
def half_up(x): return int(x + 0.5)

def ents_map(prefix, season, suffix=""):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위" + suffix + "$")
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

# 포르투갈 1부: 기존 선수 자료의 순위별 최빈값(16팀 시즌 2006-07~2013-14 / 18팀 시즌), 카펠 선례
def po1_era(nteams):
    t = collections.defaultdict(collections.Counter)
    for x in ENTS:
        m = re.match(r"포르투갈 1부 (\d{4})-\d\d (\d+)위$", x[12] or "")
        if not m: continue
        y = int(m.group(1))
        if (nteams == 16) == (2006 <= y <= 2013): t[int(m.group(2))][x[2]] += 1
    return {k: v.most_common(1)[0][0] for k, v in t.items()}
PO1_16, PO1_18 = po1_era(16), po1_era(18)

# MLS: 기존 자료 순위값(1581 평균 계열)을 재현하는 모형(끝 순위에만 씀). 기존 2019~2021 순위값에 최소제곱으로 맞춘 평균·흩어짐
def _fit_mls():
    xs, ys = [], []
    nteam = {"2019": 24, "2020": 26, "2021": 27}
    for s, n in nteam.items():
        m = ents_map("MLS", s, r"(?:/\d+팀)?")
        for r, v in m.items(): xs.append(curve(r, n)); ys.append(v)
    k = len(xs); mx = sum(xs) / k; my = sum(ys) / k
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return my - b * mx, b, k
MLS_A, MLS_B, MLS_K = _fit_mls()

TR_COEF = {2016: 6.8, 2017: 6.8, 2018: 5.5, 2019: 5.0, 2020: 3.1, 2021: 6.7, 2022: 11.8, 2023: 12.0, 2024: 10.3}
def tr_mean(season):
    s = int(season[:4]); c = sum(TR_COEF[y] for y in (s - 1, s, s + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)

def rank_model(lg, season, r, n):
    if lg == "PO1":
        m = ents_map("포르투갈 1부", season)
        if r in m: return m[r], f"포르투갈 1부 {season} {r}위"
        tab = PO1_16 if n == 16 else PO1_18
        INTERP_USED.add((lg, season, r, tab[r], "같은 팀 수 시즌 순위값"))
        return tab[r], f"포르투갈 1부 {season} {r}위"
    if lg == "PO2":
        return half_up(1367 + SD2 * curve(r, n)), f"포르투갈 2부 {season} {r}위 (추정)"
    if lg == "MLS":
        m = ents_map("MLS", season, r"(?:/\d+팀)?")
        lv = f"MLS {season} {r}위" + ("" if season == "2019" else f"/{n}팀")
        v, it = mid(m, r)
        if v is not None:
            if it: INTERP_USED.add((lg, season, r, v))
            return v, lv
        v = half_up(MLS_A + MLS_B * curve(r, n)); INTERP_USED.add((lg, season, r, v, "모형"))
        return v, lv + " (추정, 기존 MLS 순위값 모형)"
    if lg == "AUS1":
        return half_up(1450 - 100 * (r - 1) / (n - 1)), f"호주 A리그 {season} {r}위 (추정: 1위 1450~꼴찌 1350 직선)"
    if lg == "KAS1":
        return 1400 - 10 * (r - 1), f"카자흐스탄 {season} {r}위 (추정: 1위 1400에서 순위마다 10씩 낮춤)"
    if lg == "TR1":
        m = ents_map("쉬페르리그", season)
        if r in m: return m[r], f"쉬페르리그 {season} {r}위"
        lo = [k for k in m if k < r]; hi = [k for k in m if k > r]
        if lo and hi:
            a, b = max(lo), min(hi); v = half_up(m[a] + (m[b] - m[a]) * (r - a) / (b - a))
            INTERP_USED.add((lg, season, r, v))
            return v, f"쉬페르리그 {season} {r}위 (추정, 다른 선수 자료 {a}위 {m[a]}·{b}위 {m[b]} 사이)"
        v = round(tr_mean(season) + 119 * curve(r, n)); INTERP_USED.add((lg, season, r, v, "모형"))
        return v, f"쉬페르리그 {season} {r}위 (추정, 튀르키예 리그 수준 회귀)"
    if lg == "TR3B":
        return half_up(tr_mean(season) - 324 + SD2 * curve(r, n)), f"튀르키예 3부 {season} {r}위/{n}팀 (추정, 쉬페르리그 평균 − 2×독일 1·2부 평균 차)"
    return None
RANK_LG = ["PO1", "PO2", "TR1", "TR3B", "AUS1", "KAS1"]

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}; MAN_NOTE = {}
def man2(o, s, e, lv, why): MAN[(key(o), s)] = (e, lv); MAN_NOTE[(key(o), s)] = why
# 직접 추정(judgments.md 6절)
man2("Celtic FC", "2015-16", 1640, "스코틀랜드 2015-16 1위 (추정, 다른 선수 자료 셀틱 2013-14·2017-18 1위 1640과 같음)",
     "2015-16 스코틀랜드 프리미어십 우승(Transfermarkt SC1 표 1위)")
man2("Molde FK", "2015", 1369, "노르웨이 2015 6위 (추정, 다른 선수 자료 노르웨이 2015 4위 1392에 맞춘 리그 모형, 흩어짐 63)",
     "엘리테세리엔 2015 6위/16팀(Transfermarkt NO1 표). 평균 = 1392 − 63×곡선(4/16) ≈ 1349, 6위 = 1349 + 63×곡선(6/16)")
man2("Amed SK", "2015-16", 1147, "튀르키예 3부 2015-16 백색조 8위/18팀 (추정, 쉬페르리그 평균 − 2×독일 1·2부 평균 차)",
     "TFF 2. Lig 2015-16 8위/18팀(Transfermarkt TR3B 표). 2015-16 쉬페르리그 평균은 다른 선수 자료 튀르키예 2부 2015-16 7위 1326(= 평균 − 162 + SD2×곡선(7/20))에서 거꾸로 구한 약 1468")

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; SAME_MULTI = []
def seasons_for(d, cid):
    y = d[:4]
    if cid in MLS_LIKE or cid in KAZ: return [y]
    if cid in UEFA_C: return [eu(d), y]
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
    if cid in MLS_LIKE:
        t = RANKS.get(("MLS", d[:4]), {})
        if k in t:
            r, n, _ = t[k]; res = rank_model("MLS", d[:4], r, n)
            ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], ("MLS", d[:4], r, n)); return res
    for s0 in seasons_for(d, cid) + ([d[:4]] if cid in KAZ else []):
        for lg in RANK_LG:
            t = RANKS.get((lg, s0), {})
            if k in t:
                r, n, _ = t[k]
                r = RANK_FIX.get((lg, s0, k), r)
                res = rank_model(lg, s0, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1], (lg, s0, r, n)); return res
    MISS.append((o, d, cid, seasons_for(d, cid))); return 0, "?"

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
    print(ELO_SRC, "MLS 모형", MLS_A, MLS_B, MLS_K)
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
    tm = [e for e in EVS[gid] if e["scorer_id"] == ME and not is_og(e) and (gid, e["minute"]) not in EXCL_G]
    if not tm: continue
    fm_all = [r for r in FME.get(gid, []) if r["pen_shootout_event"] != "True"]
    if not any(r["scorer"] for r in fm_all): continue
    fm = [r for r in fm_all if (r["nani_scorer"] == "1") and r["ownGoal"] not in ("1", "True") and (r["goalDescriptionKey"] or "") != "owngoal"]
    FM_N += 1
    if len(tm) != len(fm): FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        a = mins(t["minute"])[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
        if abs(a - b) > 1 and not (t["minute"].startswith(("90+", "45+")) and int(f["time"]) in (45, 90)): FM_CMP.append(("분 다름", gid, ldate(G[gid]), t["minute"], f["time"], f["overloadTime"]))
        fpk = (f["suffix"] or "").lower().startswith("pen") or "pen" in (f["goalDescriptionKey"] or "").lower()
        if (t["goal_desc"] == "Penalty") != fpk: FM_CMP.append(("PK 표기 다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["suffix"], f["goalDescriptionKey"]))

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
TEAMN = {"336": "Sporting CP Lisbon", "985": "Manchester United", "36": "Fenerbahce", "1049": "Valencia CF", "398": "SS Lazio",
         "45604": "Orlando City SC", "607": "Venezia FC", "7006": "Melbourne Victory", "3840": "Adana Demirspor",
         "2431": "Estrela Amadora", "10157": "Aktobe"}
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.fullmatch(r"Nani", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움→나니 골", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_opp(x, r)]
            if hit: CROSS.append(("나니 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
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
                CROSS.append(("상대 팀 선수 같은 경기 기록", b, r[9], x[0], x[4], x[5], x[6], "나니 행", r[0], r[4], r[5], r[6]))
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0].startswith("도움 제외") and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_opp(x, [0, j[2]]):
                    CROSS.append(("TM 나니 도움을 뺀 타인 골", b, x[9], x[4], j[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("spnn", "2007-07-02", "스포르팅 CP", "2005~2007, 2014~2015, 2018~2019"), ("munn", "2014-08-19", "맨체스터 유나이티드", "2007~2014"),
         ("spnn", "2015-07-07", "스포르팅 CP", "2005~2007, 2014~2015, 2018~2019"), ("fenn", "2016-07-05", "페네르바흐체", "2015~2016"),
         ("valnn", "2017-08-31", "발렌시아", "2016~2017"), ("laznn", "2018-07-11", "라치오", "2017~2018"),
         ("spnn", "2019-02-18", "스포르팅 CP", "2005~2007, 2014~2015, 2018~2019"), ("orlnn", "2022-01-14", "올랜도 시티", "2019~2021"),
         ("vennn", "2022-07-12", "베네치아", "2022"), ("melnn", "2023-07-13", "멜버른 빅토리", "2022~2023"),
         ("adann", "2024-07-31", "아다나 데미르스포르", "2023~2024"), ("estnn", "2026-01-25", "에스트렐라 다 아마도라", "2024"),
         ("aktnn", None, "악퇴베", "2026~")]
TM_CLUB = {"336": "spnn", "985": "munn", "36": "fenn", "1049": "valnn", "398": "laznn", "45604": "orlnn", "607": "vennn",
           "7006": "melnn", "3840": "adann", "2431": "estnn", "10157": "aktnn"}
def club_of(d):
    for k, u, n, y in CLUBS:
        if u is None or d < u: return k
CN = collections.OrderedDict()
for k, u, n, y in CLUBS: CN.setdefault(k, n)
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
def season_of(d, club):
    y = int(d[:4])
    if club in ("orlnn", "aktnn"): return str(y)
    if club in ("fenn", "adann"): s = y if d[5:] >= "07-10" else y - 1
    else: s = y if int(d[5:7]) >= 8 else y - 1
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
from note_nani import make_note
NOTE = make_note(globals())
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elk", "elq", "ecq", "lg", "MAN", "clg", "elg", "mlp", "lck", "cwc"]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const NAN_E={J(E)};\nconst NAN_M={J(M)};\nconst NAN_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "assist_sources": SRC_A,
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}, "man_notes": {f"{k[0]}|{k[1]}": v for k, v in MAN_NOTE.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} · 도움 {dict(SRC_A)}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
