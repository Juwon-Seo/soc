#!/usr/bin/env python3
"""Jonathan Bamba(조나탕 밤바): raw/ -> bamba.json + src/data/bam.js (판정 근거는 judgments.md)

  python3 players/bamba/build_bamba.py            # 파일 쓰기
  python3 players/bamba/build_bamba.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/bamba/build_bamba.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/bamba/build_bamba.py --fm       # FotMob 골 대조
  python3 players/bamba/build_bamba.py --root=<스크래치 복사본>   # 그 복사본의 src/data·elo 사용(검증용)

이코네(build_ikone.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
<root>/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), <root>/src/data/*.js(같은 경기 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections, glob
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "bam.js")
OUT_JSON = os.path.join(HERE, "bamba.json")
ME = "조나탕 밤바"
GAP = "2014-08-01"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
OTHER = {r["gameId"]: r["other_leg_id"] for r in rd("tm_two_leg_ties.csv")}
for gid, r in INFO.items():
    if r["other_leg_id"]:
        OTHER.setdefault(gid, r["other_leg_id"]); OTHER.setdefault(r["other_leg_id"], gid)
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
MIN_FIX = {}   # 출전 분 고침 없음(Transfermarkt 그대로; 2026.10.24 애틀랜타전 90분은 TM 리포트 90+1분 교체·FotMob 라인업 90분 교체로 TM 기준)
# Transfermarkt API에 출전이 없지만 넣는 경기: [gameId, 날짜, 상대, 대회 id, 라운드, 분, 근거]
ADD_GAMES = [
    ["2836509", "2017-04-05", "FC Girondins Bordeaux", "FRC", "Quarter-Finals", 13,
     "쿠프 드 프랑스 8강 앙제 2-1 보르도: TM 리포트는 77분 교체 투입을 'Abdoulaye Bamba'로 적고 조나탕 밤바(22번)를 벤치로 둠. FotMob 라인업(77분 페페 대신 조나탕 밤바, 13분)·ESPN 라인업('#22 J. Bamba' 77분 페페 대신)·영어·프랑스어 위키백과 앙제 20경기(컵 4)·FotMob 경력 20경기가 모두 출전으로 셈"],
]
# 골 판정(TM 골 중 다른 출처와 다툼이 있는 것): gameId|분 -> 근거(넣음)
GOAL_DECIDED = {
    "2761166|82": "2016.9.21 벨기에컵 하렐베커전 82분 1-6 골: TM 밤바(이베 스베르스 크로스)·foot-direct 경기 기록 '82' J. Bamba'·FootballCritic 'Bamba (82')'·영어·프랑스어 위키백과 신트트라위던 컵 3경기 1골·FotMob 경력 벨기에컵 1골. FotMob 경기 이벤트·영어 위키백과 2016-17 벨기에컵 문서는 80분 요한 볼리 골로 적음(출처 차이 설명에 남김)",
}
# 도움 제외(일반 규칙 PK 유도·'Shot on goal'·상대 자책골 말고 개별 판정): gameId|분 -> 이유
EXCL_A = {
    "2645511|21": "2016.1.3 쿠프 드 프랑스 라옹레타프전 21분 모페 골: TM 'Pass' 단독(FotMob 이벤트 도움 없음, 선수 경기 목록 없음), ESPN 문자 중계에 도움 없음, 확인한 기사 없음",
    "2654473|60": "2016.3.18 리그2 메스전 60분 타라트 골: TM 단독(FotMob 이 시즌 도움 자료 없음), 도움을 적은 다른 출처를 찾지 못함",
    "2654514|18": "2016.4.22 리그2 크레테유전 18분 케이타 골: TM 단독(FotMob 이 시즌 도움 자료 없음), footmercato·sporteden 경기 기록에 도움 없음",
    "3290282|14": "2020.1.5 쿠프 드 프랑스 라옹레타프전 14분 아라우조 골: TM 단독(FotMob 이벤트 도움 없음), Sporting Life·ESPN 문자 중계 도움 없음, goal.com·maxifoot·FFF 기사에 도움자 없음",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처로 확인해 넣은 TM 도움: gameId|분 -> 근거
ADD_CONFIRMED = {
    "2735658|88": "2017.5.20 몽펠리에전 88분 테 골: TM(유형 빈칸)+FotMob 선수 경기 목록 도움 1(호드리구 선례: 이벤트 도움자 빈칸 + 선수 경기 목록 수 일치)",
    "3199427|24": "2019.9.28 니스전 24분 아라우조 골: TM(유형 빈칸)+FotMob 선수 경기 목록 도움 1(호드리구 선례)",
    "3717187|33": "2022.1.4 쿠프 드 프랑스 랑스전 33분 오나나 골: TM 'Pass'+FotMob 선수 경기 목록 도움 1(호드리구 선례)",
    "4606030|50": "2025.5.7 US 오픈컵 디트로이트 시티전 50분 글래스고 골: TM 'Pass'+FotMob 선수 경기 목록 도움 1(호드리구 선례)",
    "2942790|9": "2018.2.9 마르세유전 9분 모네파케 골: TM 밤바 + FotMob 선수 경기 목록 이 경기 도움 2(이벤트는 아무앙 도움) + Sporting Life(Opta) 문자 중계 'Assisted by Jonathan Bamba' + LiveSoccerTV 'Assist: J. Bamba'. 생테티엔 구단 공식 기사·maxifoot은 아무앙 패스로 서술(출처 차이 설명에 남김)",
}
# FotMob에만 있는 밤바 도움: gameId -> (넣을 골의 TM 분 또는 None, 근거). 넣는 것은 TM 리포트의 그 골 행을 씀
FM_ONLY_DECIDED = {
    "3307463": ("8", "2020.1.29 쿠프 드 프랑스 16강 에피날전 8분 레미 골: FotMob 이벤트 + Sporting Life(Opta) 'Assisted by Jonathan Bamba' + fflose 경기 기사('Sur une passe lumineuse de Jonathan Bamba') + livefoot('Le coup d'oeil de Bamba et la vitesse de Rémy') → 넣음"),
    "3589263": ("45", "2021.12.1 렌전 45분 헤나투 산체스 골: FotMob 이벤트·선수 경기 목록 + TM API assistsOfficial 1 + Sky Sports 경기 기록('J Bamba Assist 45'') + Betfred Insights 경기 기록 → 넣음"),
    "2846237": (None, "2017.4.25 쿠프 드 프랑스 준결승 갱강전 38분 망가니 골: FotMob 이벤트·선수 경기 목록뿐. TM·Sporting Life(Opta)·ESPN 문자 중계 도움 없음, maxifoot은 밤바가 망가니에게 줬다고, FourFourTwo는 디에디우가 망가니에게 내줬다고 서술 → 다툼 있어 뺌"),
    "2942861": (None, "2018.4.6 PSG전: FotMob 선수 경기 목록 도움 1·TM API assistsOfficial 1이지만 어느 골인지 특정 못 함(카벨라 17분 도움 없음, 90+3분 상대 자책골) → 뺌(메르턴스 선례)"),
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "FR2", "BE1", "ES1", "MLS1"}
CUP = {"FRC", "FRL", "CCB", "CDR", "MLSP"}   # MLSP = US 오픈컵(§3)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 쿠프 드 프랑스 5·6라운드·32강·16강, 쿠프 드 라 리그 3라운드·16강, 벨기에컵 32강·16강, 코파 델 레이 1라운드·16강, US 오픈컵 4라운드·16강
    if cid == "FRCH": return "df"    # 트로페 데 샹피옹 = 국내컵 결승 비중(선례)
    if cid == "POUS": return "mlp"   # MLS 컵 플레이오프 와일드카드·1라운드(3판 2선승, 경기마다 단판)
    if cid == "USMX":                # 리그스컵 리그 단계 lcg, 8강 lck
        return "lcg" if r.startswith("group") else "lck"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"   # 녹아웃 PO('intermediate stage')
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    # MLS 컵 플레이오프 1라운드는 TM이 '1st leg/2nd leg'로 적지만 3판 2선승(합산 아님) → 경기마다 단판(§3, 메시·손흥민·뮐러 2025 선례)
    return "leg" in g["round"].lower() and g["competitionId"] != "POUS"

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local_computed"]
    leg = 1 if "1st" in g["round"].lower() else 2
    o = INFO[OTHER[gid]]
    if (o["date_report"] < inf["date_report"]) != (leg == 2): sys.exit("차전 순서 이상 " + gid)
    home = int(inf["home_id"] == g["club_id"])
    if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    fu = ft = 0
    if leg == 2:
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "EL", "ELQ"):   # 2021-22부터 UEFA 원정 다득점 없음, 연장 있음
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CIT":                        # 코파 이탈리아 준결승: 원정 다득점 2021-22까지, 연장 있음(선례)
        ag, et = int(d < "2022-07-01"), 1
    else:
        sys.exit("합산 규칙 없음 " + cid)
    return [leg, home, fu, ft, ag, et]

# ---------------------------------------------------------------- 이름 정규화·상대 Elo
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
        if r["선수"] == ME: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

with open(os.path.join(ELO, "ents.json"), encoding="utf-8") as f:
    ENTS = [x for x in json.load(f) if x["p"] != ME]

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    if d >= "2025-02-01": return str(y)   # 시카고 파이어: MLS 달력 연도(상대 Elo 통합표도 연도 키)
    s = y if m >= 8 else y - 1
    # 2020년 8월 경기는 릴 리그1 2020-21 경기뿐(릴은 7월 10일 기준 → 2020-21, 조나탄 다비드·이코네 자료와 같음)
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 리그1·라리가·벨기에 1부: 다른 선수 자료의 시즌·순위별 값을 그대로 씀
RANKVAL = collections.defaultdict(collections.Counter)
for x in ENTS:
    mm = re.match(r"^(리그1|라리가|벨기에 1부) (\d{4}-\d\d)(?: \([^)]*\))? (\d+)위$", x["lv"])
    if mm: RANKVAL[(mm.group(1), mm.group(2), int(mm.group(3)))][x["elo"]] += 1
LGNAME = {"FR1": "리그1", "ES1": "라리가", "BE1": "벨기에 1부"}
def model(lg, season, r, n):
    nm = LGNAME[lg]
    c = RANKVAL.get((nm, season, r))
    if not c: return None
    if len(c) > 1: sys.exit("순위값 여러 개 " + str((nm, season, r, c)))
    return next(iter(c)), f"{nm} {season} {r}위"
RANK_LG = ["FR1", "ES1", "BE1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정') — judgments.md 'Elo' 절
MAN = {
    (key("KVRS Waasland - SK Beveren"), "2016-17"): (1356, "벨기에 1부 2016-17 14위 (리그 모형값)"),
    (key("Racing Club Harelbeke"), "2016-17"): (1150, "벨기에 4부(2부 아마추어) 2016-17 VV A조 12위 (추정, 다른 선수 자료 네덜란드 3부 이하 아마추어 1150과 같은 수준)"),
    (key("SAS Épinal"), "2019-20"): (1220, "프랑스 4부(나시오날 2) 2019-20 A조 6위 (추정, 다른 선수 자료 프랑스 4부 1220과 같음)"),
    (key("Turégano CF"), "2023-24"): (1050, "스페인 6부(지역 리그) 2023-24 (추정, 다른 선수 자료 스페인 6부 1050과 같음)"),
    (key("Detroit City FC"), "2025"): (1347, "USL 챔피언십(미국 2부) 동부 2025 8위/13팀 (추정, 다른 선수 자료 USL 챔피언십 서부 2026 8위/12팀 1347과 같음)"),
}
ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "EL", "ELQ") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, eu))
        if t and k in t:
            r, n = t[k]
            res = model(lg, eu, r, n)
            if res:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_computed"]

M = []
for g in GAMES:
    mins = MIN_FIX[g["gameId"]][0] if g["gameId"] in MIN_FIX else int(g["playedMinutes"])
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), mins])
for gid, d, opp, cid, rnd, mins, why in ADD_GAMES:
    M.append([d, opp, comp_of(cid, rnd), mins])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["bamba_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et=0):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["bamba_scorer"] == "1", e["bamba_assist_other"] == "1"
    fm_add = gid in FM_ONLY_DECIDED and FM_ONLY_DECIDED[gid][0] == e["minute"]
    if fm_add:
        if isa: sys.exit("FotMob 단독인데 TM도 도움 " + tag)
        isa = True
    if e["bamba_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag, ldate(g))); EXCL_CNT["본인 도움"] += 1
        EXCL_LIST["본인 도움"].append((ldate(g), g["opponent"], e["minute"], e["scorer"], e["assist_type"]))
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = int(ko == 1 and tie is None and "+" not in e["minute"] and mi > 90)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] != "Penalty rebound"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            k = why if tag not in EXCL_A else "개별 판정"
            EXCL_CNT[k] += 1; EXCL_LIST[k].append((d, opp, e["minute"], e["scorer"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= GAP and tag not in ADD_CONFIRMED and not fm_add:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - mi) <= 3 or abs(t - int(e["minute"].split("+")[0])) <= 3]
            if not hit:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")):
        FM_ONLY.append((gid, G[gid]["date_local_computed"], G[gid]["opponent"], ts))

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u)
for f in FM_ONLY:
    if f[0] not in FM_ONLY_DECIDED: print("FotMob 도움 미반영:", f)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
if UNDECIDED or missing_elo:
    if "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, EXCL_CNT)
    for k, v in EXCL_LIST.items(): print(k, v)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["bamba_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local_computed"])); continue
    fg = [r for r in FM_EV[gid] if r["bamba_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1" and t["goal_desc"] != "Penalty rebound"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or tm_min != fm_min:
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["bamba_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local_computed"] if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
TRACKED = None
try:
    import subprocess
    TRACKED = set(subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
except Exception:
    pass
def load_all():
    out = {}
    for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
        b = os.path.basename(fn)
        if b in ("hon.js", "bam.js"): continue
        if TRACKED is not None and "src/data/" + b not in TRACKED: continue   # 같은 회차 다른 판정자 새 파일은 읽지 않음
        s = open(fn, encoding="utf-8").read()
        me = re.search(r"const ([A-Z0-9]+)_E=(\[.*?\]);\n", s, re.S)
        mm = re.search(r"const ([A-Z0-9]+)_M=(\[.*?\]);\n", s, re.S)
        if me and mm: out[b] = (json.loads(me.group(2)), json.loads(mm.group(2)))
    return out
CROSS, SAME_GAME = [], []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
MYCLUB = {"618": "AS Saint-Étienne", "10004": "Paris FC", "475": "Sint-Truidense VV", "1420": "SCO Angers", "1082": "LOSC Lille", "940": "Celta de Vigo", "432": "Chicago Fire FC"}
IK = lambda s: norm(str(s or "")) in ("jonathan bamba", "bamba")
if __name__ == "__main__" and "--cross" in sys.argv:
    ALL = load_all()
    Mi = {(m[0], key(m[1])): m for m in M}
    gclub = {(ldate(g), key(g["opponent"])): MYCLUB[g["club_id"]] for g in GAMES}
    mates = collections.Counter(); opps = collections.Counter()
    for fn, (ent, mat) in ALL.items():
        # 같은 편(같은 날·같은 상대) 출전 행: 대회 코드 대조
        for m in mat:
            o = Mi.get((m[0], key(m[1])))
            if o:
                mates[fn] += 1
                if o[2] != m[2]: SAME_GAME.append(("같은 편 출전 대회 코드 다름", fn, m[0], m[1], o[2], m[2]))
        for x in ent:
            k = (x[9], key(x[1]))
            if k in Mi:   # 같은 편 골·도움
                mine = [r for r in E if r[9] == x[9] and key(r[1]) == k[1]]
                if mine:
                    d = [t for t in cmp_rows(mine[0], x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                    if d: CROSS.append(("같은 경기(같은 편) 다름", fn, x[9], x[1], d))
                if x[0] == "a" and IK(x[13]):
                    hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
                    CROSS.append((fn + " 도움→밤바 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
                if x[0] == "g":
                    hit = [r for r in E if r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
                    tm = [e for e in EVENTS if e["bamba_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
                    if hit: CROSS.append(("밤바 도움→" + fn + " 골", x[9], x[4], cmp_rows(hit[0], x) or "같음"))
                    elif tm: CROSS.append(("TM 밤바 도움을 뺀 같은 편 골", fn, x[9], x[4], tm[0]["assist_type"]))
            # 상대편: 이 선수의 상대가 밤바 소속팀인 같은 날 경기
            for (dd, ok), club in gclub.items():
                if x[9] == dd and (key(x[1]) == key(club) or _sub(key(x[1]), key(club))):
                    opps[fn] += 1
                    m = Mi[(dd, ok)]
                    if x[3] != m[2]: SAME_GAME.append(("상대편 대회 코드 다름", fn, dd, x[1], x[3], m[2]))
                    tt = x[14] if len(x) > 14 else None
                    mine = [r for r in E if r[9] == dd]
                    if mine:
                        t2 = mine[0][14] if len(mine[0]) > 14 else None
                        if (tt is None) != (t2 is None) or x[7] != mine[0][7]:
                            SAME_GAME.append(("상대편 단판/합산 다름", fn, dd, x[7], tt, mine[0][7], t2))
                    break
    for e in EVENTS:   # TM 도움 제공자 → 이코네 골인데 그 선수 파일에 없음
        pass
    print("같은 편 출전 겹침:", dict(mates)); print("상대편 골·도움 겹침:", dict(opps))
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))
    for c in CROSS:
        if c[-1] == "같음": print("  같음:", c[:3])
    for s in SAME_GAME: print(s)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("stebm", "2016-01-18", "AS 생테티엔", "2014~2016"), ("pfcbm", "2016-08-17", "파리 FC", "2016"),
         ("stvbm", "2017-01-04", "신트트라위던 VV", "2016"), ("angbm", "2017-06-30", "앙제 SCO", "2017"),
         ("stebm2", "2018-07-02", "AS 생테티엔", "2017~2018"), ("lilbm", "2023-07-18", "LOSC 릴", "2018~2023"),
         ("celbm", "2025-01-31", "셀타 비고", "2023~2025"), ("chibm", None, "시카고 파이어", "2025~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return "stebm" if k == "stebm2" else k
CLUB_KO = {"stebm": "생테티엔", "pfcbm": "파리 FC", "stvbm": "신트트라위던", "angbm": "앙제", "lilbm": "릴", "celbm": "셀타", "chibm": "시카고 파이어"}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CLUB_KO)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TMC = {"618": "stebm", "10004": "pfcbm", "475": "stvbm", "1420": "angbm", "1082": "lilbm", "940": "celbm", "432": "chibm"}
for g in GAMES:
    if club_of(ldate(g)) != TMC[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_bamba import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["bamba_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC))
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM "]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE):
        sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mdates = collections.Counter(m[0] for m in M)
for d, rs in by.items():
    gs = sorted({(r[5], r[6], r[4]) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
    for a, b in zip(gs, gs[1:]):
        if b[0] < a[0] or b[1] < a[1] or b[2] < a[2]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const BAM_E={J(E)};\nconst BAM_M={J(M)};\nconst BAM_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg,
               "fotmob_goal_diffs": FM_CMP, "fotmob_assists_not_used": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
