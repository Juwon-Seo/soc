#!/usr/bin/env python3
"""Téji Savanier: raw/ -> savanier.json + src/data/sav.js (판정 근거는 judgments.md)

  python3 players/savanier/build_savanier.py            # 파일 쓰기
  python3 players/savanier/build_savanier.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/savanier/build_savanier.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/savanier/build_savanier.py --fm       # FotMob 골 대조
  python3 players/savanier/build_savanier.py --root=<스크래치 복사본>   # 그 복사본의 src/data·elo 사용(검증용)

테리에(build_terrier.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv, raw/fotmob_events.csv·fotmob_playerMatches.csv·fotmob_tm_map.csv(FotMob),
raw/ranks.txt(순위표), <root>/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "sav.js")
OUT_JSON = os.path.join(HERE, "savanier.json")
ME = "테지 사바니에"
GAP = "2014-08-01"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)
FM_MAP = {r["tm_gameId"]: r["fotmob_matchId"] for r in rd("fotmob_tm_map.csv")}
FM_PM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

# ---------------------------------------------------------------- 판정 표
MIN_FIX = {}   # 출전 분 고침 없음(Transfermarkt 그대로)
# Transfermarkt API에 출전으로 없지만 넣은 경기: (날짜, 상대, 대회 코드, 분, 근거)
ADD_M = [
    ("2012-05-11", "FC Metz", "lg", 45,
     "리그2 37라운드 아를아비뇽 1-0 메스: Transfermarkt API는 '명단 포함(in squad)'이지만 같은 경기 리포트에 90+4분 경고, "
     "maxifoot 경기 기록에 46분 아브델하미드 대신 교체 투입(T. Savagnier, 46e)·90+4분 경고. "
     "en/fr 위키백과·FotMob 시즌 출전 21경기(Transfermarkt 20) → 넣음, 출전 45분"),
]
# 골 득점자 이름 고침(Transfermarkt 리포트 오기): gameId|분 -> 이름
SCORER_FIX = {
    "2761183|65": "Slimane Sissoko",   # TM 'Ousmane Cissokho'. FotMob·Midi Libre·France Bleu·Objectif Gard 모두 슬리만 시소코(교체 투입 직후 헤더)
}
# PK 여부 고침: gameId|분 -> 1/0
PK_FIX = {
    "2873451|50": 1,   # 2017.9.15 오세르전 50분: Transfermarkt는 일반 골(penGoals 0), FotMob 'penalty'·fr.위키백과 시즌 문서 일정표 '50 pen' → PK 골
}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음, PK 유도·'Shot on goal'·자책골은 일반 규칙): gameId|분 -> 이유
EXCL_A = {
    "2873562|41": "2017.9.22 니오르전 41분 보조크 골: Objectif Gard 경기 기사 — 사바니에가 공을 몰고 가다 반칙으로 넘어졌고 주심이 어드밴티지, 보조크가 흐른 공을 잡아 골(패스 아님)",
    "4094792|71": "2024.3.3 스트라스부르전 71분: ESPN(Opta) 문자중계는 스트라스부르 두쿠레 자책골, FotMob 도움 없음(선수 경기 목록 도움 0), fr.위키백과 2023-24 리그 도움 6(Transfermarkt 7) → 상대 자책골 유도로 봄",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처로 확인해 넣은 도움: gameId|분 -> 근거
ADD_CONFIRMED = {
    "2726318|13": "2016.8.26 아미앵전 13분 알리우이 헤더: Midi Libre 문자중계('Corner tiré depuis la droite par Savanier sur la tête d'Alioui')·Objectif Gard 경기 기사(사바니에 코너를 알리우이가 가까운 포스트에서 헤더)",
    "2761183|65": "2016.10.28 발랑시엔전 65분 시소코 헤더: Midi Libre('sur le corner de Savanier')·France Bleu('sur un corner de Téji Savanier, Sissoko … de la tête')·Objectif Gard('Corner tiré par Téji Savanier, tête rageuse')",
    "2761208|29": "2016.11.25 랭스전 29분 리파르 헤더: Midi Libre('Savanier offrait une 4e passe décisive … sur la tête de Ripart')·Objectif Gard('Tiré par Savanier un beau corner … Renaud Ripart reprend … d'une tête')",
    "2761460|27": "2017.3.31 발랑시엔전 27분 리파르: Midi Libre('le ballon distillé par Savanier (sa 8e passe décisive)')·France Bleu('un bon corner de Téji Savanier est habilement dévié par Renaud Ripart')",
    "3016475|50": "2018.3.9 오를레앙전 50분 아레크 헤더: Midi Libre('sur un coup franc de Savanier prolongé victorieusement de la tête par Harek')·Objectif Gard(사바니에 세트피스를 주장 아레크가 헤더)",
    "3018817|47": "2018.3.19 브레스트전 47분 브리앙송 헤더: Midi Libre('Briançon, de la tête, coupait la trajectoire du centre de Savanier')·Objectif Gard('Les Crocos ramassent la galette en Bretagne', 사바니에 코너를 브리앙송 헤더)",
    "3261674|21": "2019.10.30 낭시전(쿠프 드 라 리그) 21분 들로르: ESPN(Opta) 문자중계('Assisted by Téji Savanier with a through ball following a fast break')·France Bleu 경기 기사(사바니에가 만든 들로르 골, 몽펠리에 첫 도움)",
}
# FotMob 경기 이벤트에 도움자가 비었지만 FotMob 선수 경기 목록(playerMatches)이 그 경기 사바니에 도움 수를 Transfermarkt와 같게 센 것(TM∩FotMob, 호드리구·다비드 선례)
FM_PM_OK = {"3047431", "3519923", "3549067", "4271186", "4778390"}
# 2014.8.1 이후 Transfermarkt 단독 도움 가운데 다른 출처 2곳을 찾지 못해 뺀 것(목록은 judgments.md·설명에): gameId|분 -> 찾은 출처
UNCONFIRMED = {
    "2490415|37": "", "2502454|102": "", "2507084|24": "maxifoot·livefoot 경기 기록은 득점자만", "2547672|45": "", "2547691|56": "",
    "2616502|51": "", "2616511|82": "", "2616638|86": "", "2616646|20": "",
    "2648145|7": "Objectif Gard 경기 기사에 도움 서술 없음", "2648145|16": "Objectif Gard 경기 기사에 도움 서술 없음", "2654452|43": "",
    "2747228|52": "Objectif Gard 1곳(코너)", "2761269|38": "Objectif Gard 1곳(프리킥)", "2761297|46": "Midi Libre 1곳(프리킥)",
    "2761439|84": "Midi Libre 1곳('coup de pied arrêté de Savanier')", "2761475|7": "Midi Libre 1곳(코너)",
    "2761555|83": "", "2761609|10": "", "2761609|62": "", "2909835|93": "",
    "2883403|62": "", "2883413|9": "", "2883439|43": "Midi Libre 1곳(코너)", "2899528|91": "",
    "2900986|31": "", "2901012|36": "Objectif Gard 1곳('Savanier sert magistralement')",
    "2761208|88": "Midi Libre·Objectif Gard 모두 알리우이 개인 돌파 뒤 감아 차기로만 서술",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "FR2"}
CUP = {"FRC", "FRL"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 쿠프 드 프랑스 3~6라운드·32강·16강, 쿠프 드 라 리그 1~3라운드·16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(g):
    return 0 if g["competitionId"] in LEAGUE else 1

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
def key(n):
    k = norm(n)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

with open(os.path.join(ELO, "ents.json"), encoding="utf-8") as f:
    ENTS = [x for x in json.load(f) if x["p"] != ME]

def season_of(d):
    """사바니에 네 클럽 모두 7월 10일 기준(리그2 7월 말 개막, 2020년 8월 리그1 2020-21 개막전)"""
    y = int(d[:4]); s = y if d[5:] >= "07-10" else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 리그1: 다른 선수 자료의 시즌·순위별 값(lv '리그1 2019-20 7위' 등)
RANKVAL = collections.defaultdict(collections.Counter)
for x in ENTS:
    mm = re.match(r"^리그1 (\d{4}-\d\d)(?: \([^)]*\))? (\d+)위$", x["lv"])
    if mm: RANKVAL[(mm.group(1), int(mm.group(2)))][x["elo"]] += 1
# 리그2(20팀 시즌): 다른 선수 자료 '리그2 시즌 N위' 값 중 순위별로 가장 많이 쓴 값(동수면 1540+51.24×곡선 정수값과 같은 쪽)
FR2_20 = {1: 1669, 2: 1624, 3: 1603, 4: 1582, 5: 1574, 6: 1567, 7: 1559, 8: 1550, 9: 1540, 10: 1532,
          11: 1526, 12: 1521, 13: 1516, 14: 1513, 15: 1508, 16: 1500, 17: 1490, 18: 1484, 19: 1480, 20: 1469}
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
def fr2_18(r):   # 18팀 시즌(2024-25~): 기존 '리그2(프랑스 2부) 2024-25 4위 1578'과 같은 식 int(1540 + 51.24×곡선)
    return int(1540 + 51.24 * curve(r, 18))
CUR = {"2026-27": " (11월 중순 현재)"}

def model(lg, season, r, n):
    cur = CUR.get(season, "")
    if lg == "FR1":
        c = RANKVAL.get((season, r))
        if c:
            if len(c) > 1: sys.exit("순위값 여러 개 " + str((season, r, c)))
            return next(iter(c)), f"리그1 {season}{cur} {r}위"
        # 같은 시즌 이웃 순위 값의 가운데(병렬 판정 규칙)
        lo = [k for (s, k) in RANKVAL if s == season and k < r]; hi = [k for (s, k) in RANKVAL if s == season and k > r]
        if lo and hi:
            a, b = max(lo), min(hi)
            va, vb = next(iter(RANKVAL[(season, a)])), next(iter(RANKVAL[(season, b)]))
            return int(va + (vb - va) * (r - a) / (b - a) + 0.5), f"리그1 {season}{cur} {r}위"
        return None
    if lg == "FR2":
        if n == 20: return FR2_20[r], f"리그2 {season}{cur} {r}위"
        if n == 18: return fr2_18(r), f"리그2 {season}{cur} {r}위"
    return None
RANK_LG = ["FR1", "FR2"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정')
MAN = {
    (key("FC Roche Saint Genest"), "2012-13"): (1000, "프랑스 8부(PHR) 2012-13 (추정, 다른 선수 자료 프랑스 아마추어 하부 1000과 같음)"),
    (key("Canet Roussillon FC"), "2020-21"): (1220, "프랑스 4부(나시오날 2) 2020-21 D조 12위 (추정, 다른 선수 자료 프랑스 4부 1220과 같음)"),
    (key("Andrézieux-Bouthéon FC"), "2021-22"): (1220, "프랑스 4부(나시오날 2) 2021-22 D조 4위 (추정, 다른 선수 자료 프랑스 4부 1220과 같음)"),
    (key("Entente Feignies Aulnoye FC"), "2023-24"): (1220, "프랑스 4부(나시오날 2) 2023-24 D조 8위 (추정, 다른 선수 자료 프랑스 4부 1220과 같음)"),
    (key("Canet Roussillon FC"), "2025-26"): (1150, "프랑스 5부(나시오날 3) 2025-26 2위 (추정, 다른 선수 자료 프랑스 5부 1150과 같음)"),
}
ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_of(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    if (k, eu) in TABLE:
        (e, lv), _ = collections.Counter(TABLE[(k, eu)]).most_common(1)[0]
        ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + eu, sorted(set(TABLE[(k, eu)]))))
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
for d, opp, comp, mins, _ in ADD_M:
    if any(m[0] == d for m in M): sys.exit("ADD_M 중복 " + d)
    M.append([d, opp, comp, mins])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["savanier_assist"] == "1" and r["pen_shootout_event"] != "True":
            FM_ASSIST[gid].append(int(r["time"]) + int(r["overloadTime"] or 0))
def pm_assists(gid):
    p = FM_PM.get(FM_MAP.get(gid, ""))
    return int(p["assists"]) if p and p["assists"] not in ("", None) else None

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
UNDECIDED = []
SRC_A = collections.Counter()
def add_row(typ, mi, dm, gf, ga, pk, note, comp, ko, d, opp, cid, et=0):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_of(d), cid)); res = (0, "?")
    elo, lv = res
    rows.append([typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note])

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{minute(e['minute'])[0]}"
    isg, isa = e["savanier_scorer"] == "1", e["savanier_assist_other"] == "1"
    if e["savanier_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag, ldate(g))); EXCL_CNT["본인 도움"] += 1
        EXCL_LIST["본인 도움"].append((ldate(g), g["opponent"], e["minute"], e["scorer"], e["assist_type"]))
    if not (isg or isa): continue
    inf = INFO.get(gid)
    if not inf: sys.exit("리포트 없음 " + gid)
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g)
    et = int(ko == 1 and "+" not in e["minute"] and mi > 90)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        pk = PK_FIX.get(tag, int(e["penalty"] == "1" and e["goal_desc"] != "Penalty rebound"))
        add_row("g", mi, dm, gf, ga, pk, 0, comp, ko, d, opp, cid, et)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] in ("Shot on goal", "Deflected"): why = "'" + e["assist_type"] + "'(리바운드·굴절)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            k = why if tag not in EXCL_A else "개별 판정"
            EXCL_CNT[k] += 1; EXCL_LIST[k].append((d, opp, e["minute"], e["scorer"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        scorer = SCORER_FIX.get(tag, e["scorer"])
        if d >= GAP:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - mi) <= 3 or abs(t - int(e["minute"].split("+")[0])) <= 3]
            if hit:
                used_fm[gid] += 1; SRC_A["TM∩FotMob 경기 이벤트"] += 1
            elif gid in FM_PM_OK and pm_assists(gid) == sum(1 for x in EVENTS if x["gameId"] == gid and x["savanier_assist_other"] == "1"):
                SRC_A["TM∩FotMob 선수 경기 목록"] += 1
            elif tag in ADD_CONFIRMED:
                SRC_A["TM + 다른 출처 2곳"] += 1
            elif tag in UNCONFIRMED:
                EXCL_CNT["단일 출처 미확인"] += 1; EXCL_LIST["단일 출처 미확인"].append((d, opp, e["minute"], scorer, UNCONFIRMED[tag]))
                judg.append(("도움 제외(단일 출처 미확인)", d, opp, e["minute"], scorer, UNCONFIRMED[tag])); continue
            else:
                UNDECIDED.append((tag, d, opp, e["minute"], e["scorer"], e["assist_type"])); continue
        else:
            SRC_A["2014.8 전 Transfermarkt"] += 1
        add_row("a", mi, dm, gf, ga, 0, scorer, comp, ko, d, opp, cid, et)

for t in list(ADD_CONFIRMED) + list(UNCONFIRMED) + list(EXCL_A) + list(SCORER_FIX):
    gid, mi = t.split("|")
    if not any(x["gameId"] == gid and minute(x["minute"])[0] == int(mi) and x["savanier_assist_other"] == "1" for x in EVENTS):
        sys.exit("판정 표 키가 TM 도움과 맞지 않음 " + t)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and len(ts) > used_fm.get(gid, 0):
        FM_ONLY.append((gid, G[gid]["date_local_computed"], G[gid]["opponent"], ts))

if UNDECIDED:
    for u in UNDECIDED: print("판정 필요(TM 단독 도움):", u)
for f in FM_ONLY: print("FotMob 도움 미반영:", f)
if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
if UNDECIDED or missing_elo or FM_ONLY:
    if "--force" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, EXCL_CNT, SRC_A)
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
    if e["savanier_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local_computed"])); continue
    fg = [r for r in FM_EV[gid] if r["savanier_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] not in ("True", "true", "1")]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local_computed"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = bool(PK_FIX.get(gid + "|" + str(minute(t["minute"])[0]), int(t["penalty"] == "1" and t["goal_desc"] != "Penalty rebound")))
        fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower() or "penalty" in (f["goalDescription"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local_computed"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["savanier_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local_computed"] if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
CLUB_NAMES = {"arlsv": ["arles avignon", "ac arles avignon", "arles"], "nimsv": ["nimes olympique", "nimes"],
              "mtpsv": ["montpellier hsc", "montpellier"], "metsv": ["fc metz", "metz"]}
CLUBS = [("arlsv", "2015-08-06", "AC 아를아비뇽", "2011~2015"), ("nimsv", "2019-07-02", "님 올랭피크", "2015~2019"),
         ("mtpsv", "2026-08-10", "몽펠리에 HSC", "2019~2026"), ("metsv", None, "FC 메스", "2026~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
SAME_GAME = []   # 다른 선수의 상대가 사바니에 소속팀인 같은 날 경기(대회 코드 대조)
MDATE = {m[0]: m for m in M}
for x in ENTS:
    m = MDATE.get(x["date"])
    if not m: continue
    if norm(x["opp"]) in CLUB_NAMES[club_of(x["date"])] or key(x["opp"]) in [key(n) for n in CLUB_NAMES[club_of(x["date"])]]:
        SAME_GAME.append((x["date"], x["p"], x["opp"], m[1], x.get("comp"), m[2], "같음" if x.get("comp") == m[2] else "대회 다름"))
SAME_OPP = []    # 같은 날 같은 상대(=동료 자료) 대회·Elo 대조
for r in E:
    for x in ENTS:
        if x["date"] == r[9] and key(x["opp"]) == key(r[1]):
            SAME_OPP.append((r[9], r[1], x["p"], (x["elo"], x["lv"], x.get("comp")), (r[2], r[12], r[3])))
if __name__ == "__main__" and "--cross" in sys.argv:
    print("상대가 사바니에 소속팀인 다른 선수 기록:", len(SAME_GAME), collections.Counter(s[-1] for s in SAME_GAME))
    for s in SAME_GAME: print(" ", s)
    print("같은 날 같은 상대:", SAME_OPP)

# ---------------------------------------------------------------- 클럽·시즌
CLUB_KO = {"arlsv": "아를아비뇽", "nimsv": "님", "mtpsv": "몽펠리에", "metsv": "메스"}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CLUB_KO)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"11300": "arlsv", "1160": "nimsv", "969": "mtpsv", "347": "metsv"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_savanier import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["savanier_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, EXCL_LIST=EXCL_LIST, SRC=ELO_SRC, SRC_A=SRC_A))
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
        if b[0] < a[0] or b[1] < a[1]: problems.append(("스코어 역순", d, a, b))
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const SAV_E={J(E)};\nconst SAV_M={J(M)};\nconst SAV_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg,
               "same_game_other_players": SAME_GAME, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG,
               "assist_sources": SRC_A},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · Elo {dict(ELO_SRC)} · 도움 {dict(SRC_A)}")
    for k, v in ST.items(): print(" ", k, v)
