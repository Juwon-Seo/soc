#!/usr/bin/env python3
"""Antonio Di Natale: raw/ -> dinatale.json + src/data/dnt.js (판정 근거는 judgments.md)

  python3 players/dinatale/build_dinatale.py            # 파일 쓰기
  python3 players/dinatale/build_dinatale.py --debug    # Elo 출처 목록
  python3 players/dinatale/build_dinatale.py --fm       # FotMob 골 대조(2010-11 이후)
  python3 players/dinatale/build_dinatale.py --cross    # 우디네세 동료(칸드레바·콰드라도·브루노 페르난데스) 자료 대조

입력: raw/tm_games.csv(출전 688경기), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(순위표: Transfermarkt + 이탈리아어 위키백과 C1·C2),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/can.js·cua.js·brf.js.
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다. 델 피에로·토티 빌드 스크립트와 같은 구조.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "dnt.js")
OUT_JSON = os.path.join(HERE, "dinatale.json")
ME = "안토니오 디 나탈레"
GAP = "2014-08-01"   # 도움 출처 기준일(이전 Transfermarkt, 이후 Transfermarkt∩FotMob 또는 다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
# 골 분 수정: gameId|TM 분|골 뒤 스코어 -> (분, 표시 분)
GOAL_MIN_FIX = {
    # 2011.3.20 우디네세-카타니아 PK 골: TM 84분, FotMob 74분, Blitz 경기 기사 '후반 29분', Eurosport 75분, footballcritic 74분 → 74분
    "1047624|84|2-0": (74, 0),
    # 2010.2.7 우디네세-나폴리: TM 리포트가 91·93분으로 적은 두 골은 정규시간 추가시간(ESPN 90+1·90+3, il Pallonaro 90·91, 연장 없는 리그 경기)
    "964499|91|2-1": (91, "90+1"),
    "964499|93|3-1": (93, "90+3"),
}
EXCL_G = {}

# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    "83956|51": "슈팅 리바운드(Shot on goal, 2007.9.26 제노아전 자와 골)",
    "35616|60": "상대 자책골(2005.11.2 챔스 베르더 브레멘전 슐츠 자책골)",
    # 2014.8.1 이후 Transfermarkt 단독(FotMob 도움 없음), 다른 출처 2곳이 확인하지 못함
    "2478903|58": "2014.8 이후 Transfermarkt 단독. thegoalmac(Sports Mole 계열 문장)만 디 나탈레 코너킥으로 적고, ESPN(PA)·Sports Mole·Forza Italian Football은 코너킥 뒤 밀란 수비가 걷어내지 못한 공을 핀치가 잡아 찼다고만 적어 확인 안 됨",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2611206|31": "Forza Italian Football(디 나탈레의 낮은 크로스를 테로가 밀어 넣음)·Football Italia(디 나탈레의 스루패스를 테로가 마무리)",
    "2604238|56": "Blitz quotidiano 경기 기사(디 나탈레 도움, 골리니 선방 뒤 테로가 밀어 넣음)·ESPN 경기 기사(테로가 디 나탈레 크로스를 두 번째 시도에 마무리)",
}
# FotMob에만 있는 도움(넣지 않음)
FM_ONLY = [
    "2014.9.21 나폴리전 71분 다닐루 골(FotMob은 디 나탈레 도움, Transfermarkt는 도움 없음. ESPN은 디 나탈레 프리킥이 상대 수비 쿨리발리 머리에 맞고 다닐루에게 갔다고 적어 굴절로 봄)",
    "2015.9.22 밀란전 51분 바두 골(FotMob은 디 나탈레 도움, Transfermarkt는 두반 사파타 도움(크로스). 인도네시아 medcom 기사만 디 나탈레로 적고 Foot Mercato는 FotMob과 같은 Opta 자료라 독립 출처 2곳이 안 됨)",
]

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "IT3A", "IT4Y", "IT4X", "IT4W"}   # IT4W = 1997-98 세리에C2 B조 잔류 플레이아웃(리그 비중, 고메스·카모라네시 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "CIT":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 조별·1~4라운드·16강
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # UEFA컵 32강(intermediate stage·3rd round)·16강, 유로파 16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    if g["competitionId"] == "IT4W":
        # 세리에C2 플레이아웃: 합계 동률이면 정규리그 순위가 높은 팀 잔류(이탈리아어 위키백과 세리에C2 1997-98 '각주: 순위로 강등'), 원정 다득점·연장 없음
        return [leg, home, fu, ft, 0, 0]
    # 원정 다득점·연장: UEFA 대회(2020-21까지), 코파 이탈리아(2021-22까지) 모두 적용
    return [leg, home, fu, ft, 1, 1]

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
MANUAL_ALIAS = {
    "inter milan": "inter", "ac parma": "parma calcio 1913", "parma ac": "parma calcio 1913",
}
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
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 순위표: (리그, 시즌) -> {key: (순위, 팀 수)}. 이탈리아어 위키백과 C1·C2 표는 짧은 이름이라 따로 둠
WIKI_LG = {"IT C2 girone B (tier 4, it.wikipedia)": ("IT4", "B"), "IT C2 girone A (tier 4, it.wikipedia)": ("IT4", "A"),
           "IT C2 girone C (tier 4, it.wikipedia)": ("IT4", "C"), "IT C1 girone A (tier 3, it.wikipedia)": ("IT3W", "A")}
RANKS = collections.defaultdict(dict)
WIKI = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        if p[0] in WIKI_LG:
            WIKI[(p[0], p[1])][norm(p[4])] = (int(p[2]), int(p[3]))
        else:
            RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 세리에A 20팀 순위값(기존 자료) → 표준 곡선
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

# 세리에A 18팀(1988-89~2003-04): 토티·델 피에로 자료와 같은 순위값(7·9·12·16위는 앞뒤 순위값의 가운데)
SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 7: 1762, 8: 1743, 9: 1728, 10: 1713, 11: 1704, 12: 1697,
        13: 1690, 14: 1676, 15: 1657, 16: 1645, 17: 1633, 18: 1614}
SB_MEAN, SB_SD = 1577.78, 51.24   # 세리에B(문서 4절)
C1_MEAN = 1416.56                 # 세리에C1(3부): 인시녜·토티·인자기 자료와 같은 모형(세리에B 평균 − 세리에A·B 평균 차)
C2_MEAN = 1255.34                 # 세리에C2(4부): 인시녜 자료의 레가 프로 2부(4부) 모형(한 단계 더 내림), 흩어짐은 같은 2부 곡선

def model(lg, season, r, n, grp=None):
    """(Elo, lv) — 순위표 + 리그 모형"""
    if lg == "IT1":
        m = ents_map("세리에A", season)
        if r in m: return m[r], f"세리에A {season} {r}위"
        if n == 18: return SA18[r], f"세리에A {season} {r}위"
        assert n == 20, (season, n)
        return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "IT2":
        m = ents_map("세리에B", season)
        if r in m: return m[r], f"세리에B {season} {r}위"
        return int(round(SB_MEAN + SB_SD * curve(r, n))), f"세리에B {season} {r}위"
    if lg in ("IT3A", "IT3B", "IT3W"):
        grp = grp or ("A" if lg == "IT3A" else "B")
        return int(round(C1_MEAN + SB_SD * curve(r, n))), f"세리에C1 {grp}조 {season} {r}위/{n}팀 (추정)"
    if lg == "IT4":
        return int(round(C2_MEAN + SB_SD * curve(r, n))), f"세리에C2(4부) {grp}조 {season} {r}위/{n}팀 (추정)"
    return None

RANK_LG = ["IT1", "IT2", "IT3A", "IT3B"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {
    (key("GNK Dinamo Zagreb"), "2008-09"): (1520, "크로아티아 2008-09 1위 (추정, 다른 선수 자료의 디나모 자그레브 2007-08·2009-10 1위 1520과 같음)"),
    (key("Lech Poznań"), "2008-09"): (1439, "엑스트라클라사 2008-09 3위 (추정, 다른 선수 자료 같은 시즌 2위 1465·4위 1412의 가운데)"),
    (key("Anzhi Makhachkala"), "2012-13"): (1574, "러시아 프리미어리그 2012-13 3위 (리그 수준 추정)"),
    (key("NK Siroki Brijeg"), "2013-14"): (1400, "보스니아 헤르체고비나 2013-14 2위 (추정, 다른 선수 자료 보스니아 2위 젤레즈니차르 2002-03 1400과 같음)"),
    (key("FC Slovan Liberec"), "2013-14"): (1462, "체코 2013-14 4위 (추정, 다른 선수 자료의 슬로반 리베레츠 2006-07 4위 1462와 같음)"),
}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    # 1) 같은 경기 다른 선수 자료(날짜 ±1) — 이 선수와 같은 상대(= 우디네세 동료 자료)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    euro = cid in ("CL", "CLQ", "EL", "ELQ", "UEFA")
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if euro else [eu]
    # 2) 같은 팀·같은 시즌 기존 값(팀×시즌 통합표)
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    # 3) 직접 추정
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    # 4) 순위표 + 리그 모형
    for s in seasons:
        for lg in RANK_LG:
            t = RANKS.get((lg, s))
            if t and k in t:
                r, n = t[k]
                res = model(lg, s, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model"))
                    return res
        # 이탈리아어 위키백과 C1·C2 조별 순위표(짧은 이름: 낱말 포함 관계로 대조, 한 팀만 맞아야 함)
        for wl, (lg, grp) in WIKI_LG.items():
            t = WIKI.get((wl, s))
            if not t: continue
            hit = [nm for nm in t if _sub(nm, norm(opp))]
            if len(hit) > 1: sys.exit(f"위키 순위표 이름 겹침 {opp} {hit}")
            if hit:
                r, n = t[hit[0]]
                res = model(lg, s, r, n, grp)
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model-wiki " + hit[0]))
                return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_tm_report"]

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["dn_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, 0, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

used_excl, used_add, used_fix = set(), set(), set()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["dn_scorer"] == "1", e["dn_assist_other"] == "1", e["dn_self_assist"] == "1"
    if iss: judg.append(("본인 PK 골의 본인 도움(도움 아님)", ldate(g), e["minute"]))
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
    fk = f"{gid}|{e['minute']}|{e['score_home_away_after']}"
    if fk in GOAL_MIN_FIX: mi, dm = GOAL_MIN_FIX[fk]; used_fix.add(fk)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid)
    if isa:
        if tag in EXCL_A:
            used_excl.add(tag)
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal") or e["assist_type"].startswith("Handball"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP:
            if tag in ADD_CONFIRMED: used_add.add(tag)
            elif not any(abs(t - mi) <= 2 or abs(t - int(e["minute"].split("+")[0])) <= 2 for t in FM_ASSIST.get(gid, [])):
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)
for nm_, s_, u_ in (("도움 제외", EXCL_A, used_excl), ("다른 출처 확인 도움", ADD_CONFIRMED, used_add), ("골 분 수정", GOAL_MIN_FIX, used_fix)):
    if set(s_) - u_: sys.exit("쓰이지 않은 " + nm_ + " " + str(set(s_) - u_))

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

def sk(r):
    return (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1)
rows.sort(key=sk)
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["dn_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV: continue
    fg = [r for r in FM_EV[gid] if r["dn_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"], t["score_home_away_after"], f["newScore_home_away"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Antonio Candreva": ("can.js", "CAN", "2007-08-01", "2008-07-01"),
         "Juan Cuadrado": ("cua.js", "CUA", "2009-07-01", "2011-07-01"),
         "Bruno Fernandes": ("brf.js", "BRF", "2013-07-01", "2016-07-01")}
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    return diffs
for nm, (fn, P, lo, hi) in MATES.items():
    ent = load_js(fn, P)
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("디 나탈레 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and norm(x[13]) == norm("Antonio Di Natale"):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→디 나탈레 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어"))]
                    CROSS.append(("같은 경기", nm, r[9], r[1], dd or "같음")); break
    # TM 리포트가 디 나탈레 도움으로 적었지만 뺀 동료 골, 동료 도움인데 동료 파일에 없는 디 나탈레 골(참고)
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["dn_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 디 나탈레 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:
        if e["dn_scorer"] == "1" and e["gameId"] in G and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움이 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("empdn", "1997-07-01", "엠폴리", "1996~1997"), ("ipzdn", "1998-07-01", "이페르촐라 (임대)", "1997~1998"),
         ("vardn", "1998-10-05", "바레세 (임대)", "1998"), ("viadn", "1999-07-01", "비아레조 (임대)", "1998~1999"),
         ("empdn", "2004-08-31", "엠폴리", "1999~2004"), ("udidn", None, "우디네세", "2004~2016")]
TM_CLUB = {"749": "empdn", "25376": "ipzdn", "4361": "vardn", "4104": "viadn", "410": "udidn"}
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
ORDER = ["empdn", "ipzdn", "vardn", "viadn", "udidn"]
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in ORDER)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
EMP1 = [len([m for m in M if m[0] < "1997-07-01"]), 0, 0]
EMP2 = [ST["empdn"][0] - EMP1[0], ST["empdn"][1], ST["empdn"][2]]

SEASONS = collections.OrderedDict()
for m in M:
    s = season_eu(m[0]); SEASONS.setdefault(s, [0, 0, 0, 0]); SEASONS[s][0] += 1; SEASONS[s][3] += m[3]
for r in E:
    SEASONS[season_eu(r[9])][1 if r[0] == "g" else 2] += 1

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
POST_A = NA - PRE_A
SRC = ELO_SRC
EMP_ASSIST = sum(1 for r in E if r[0] == "a" and r[9] < "2002-08-01")
NOTE_LINES = [
    f"안토니오 디 나탈레(엠폴리·이페르촐라·바레세·비아레조·우디네세)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 크레모네세전 ~ {d_(M[-1][0])} 카르피전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    f"클럽별 경기·골·도움: 엠폴리 {c3(ST['empdn'])}(1996-97 {c3(EMP1)}, 1999-2004 {c3(EMP2)}), 이페르촐라 {c3(ST['ipzdn'])}, 바레세 {c3(ST['vardn'])}, 비아레조 {c3(ST['viadn'])}, 우디네세 {c3(ST['udidn'])}. 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(출전 분이 빈 경기 없음, 90분으로 추정한 경기 없음), 골 시각·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(출전한 {NG}경기 전부), 2010-11 이후 골·도움은 FotMob 경기 이벤트와 대조함. 우승·득점 기록과 위키백과(영어·이탈리아어) 시즌별 경기·골도 대조함",
    "세리에C1(바레세)·세리에C2(이페르촐라·비아레조)는 이 시기 이탈리아의 프로 리그(이탈리아어 위키백과 세리에C2 1997-98 '네 번째 프로 대회')라 셈. 아마추어(세리에D 이하) 팀 경기는 없음. 유스 경기와 이탈리아 대표팀 경기는 뺌",
    "경기 수·골은 위키백과 686경기 300골과 두 곳이 다름: ① 1998.5.31·6.7 세리에C2 B조 잔류 플레이아웃 토레스전 2경기 2골(이페르촐라)은 위키백과가 정규리그만 적어 빠졌으나 Transfermarkt 경기 리포트·이탈리아어 위키백과 대회 문서(이페르촐라 2-3 토레스, 토레스 3-0 이페르촐라)로 확인돼 넣음. ② 2004.8.14 코파 이탈리아 조별 경기는 Transfermarkt가 엠폴리 경기(72분)로 적어 엠폴리로 셈(위키백과는 우디네세 2004-05 코파 이탈리아 6경기에 넣음, 전체 경기 수는 같음)",
    "1998.6.7 토레스-이페르촐라 플레이아웃 2차전은 Transfermarkt 선수 경기 성적·리포트 머리글이 0-0이지만 리포트 득점 목록(피오리 5분·프라우 48분·크리스토파리 90분)과 이탈리아어 위키백과가 3-0이라 3-0으로 봄(디 나탈레 골·도움 없음)",
    "날짜는 현지 날짜(Transfermarkt 경기 리포트). 엠폴리 1997~2002년 41경기는 선수 경기 성적의 날짜(UTC)가 하루 앞이라 리포트 날짜를 씀",
    f"골: Transfermarkt 리포트 골 {NGo}개를 그대로 씀(선수 경기 성적과 경기마다 같음). PK 골 {NPK}개는 골 유형 'Penalty' 기준. 2010.2.7 나폴리전 7분 골은 'Penalty rebound'(PK가 막힌 뒤 리바운드)라 일반 골로 셈",
    "골 시각: 2010.2.7 나폴리전 두 골은 Transfermarkt 리포트가 91·93분으로 적었으나 연장 없는 리그 경기의 추가시간이라 90+1·90+3분(ESPN 경기 기록)으로 적음. 2011.3.20 카타니아전 PK 골은 Transfermarkt 84분, FotMob 74분·Blitz 경기 기사 후반 29분·Eurosport 75분이라 74분으로 고침",
    "2010-11 이후 골은 FotMob 경기 이벤트와 분·스코어·PK를 대조함(FotMob 기록이 없는 2011년 1~5월 11경기는 Transfermarkt만 근거, 추가시간을 '90+'로만 적은 FotMob 차이는 Transfermarkt 분을 씀)",
    f"도움: 2014.8.1 이전은 Transfermarkt 경기 리포트 도움, 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것과 다른 출처 2곳이 확인한 것만 씀. 도움 {NA} = Transfermarkt 리포트 80 − 슈팅 리바운드 1(2007.9.26 제노아전 자와 골, 'Shot on goal') − 상대 자책골에 준 도움 1(2005.11.2 챔스 베르더 브레멘전 슐츠) − 2014.8 이후 Transfermarkt 단독으로 다른 출처 2곳이 확인하지 못한 1. Transfermarkt 리포트가 본인 PK 골에 본인 도움(PK 유도)으로 적은 5개(2010.1.24 삼프도리아전, 2012.1.15 제노아전, 2012.2.26 볼로냐전, 2014.2.23 아탈란타전, 2015.5.10 삼프도리아전)는 도움으로 세지 않음",
    f"1997~2002년 이페르촐라·비아레조·바레세와 엠폴리 세리에B 시절은 Transfermarkt 경기 리포트에 도움 칸이 거의 비어 있고(2001-02까지 골 431개 중 10개만 도움자 기재) 위키백과·FotMob에도 경기별 도움이 없어 이 시기 도움은 {EMP_ASSIST}개(2001.8.19 코파 이탈리아 카타니아전 타바노 골)뿐임. 실제 도움보다 적게 잡혔을 수 있음",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(2010~14년 FotMob 경기 이벤트는 도움이 비어 있는 경기가 많음). 도움 유형 칸이 빈 2001.8.19 타바노·2007.12.23 엠폴리전 도세나·2013.8.22 유로파 예선 리베레츠전 가브리에우 시우바 골도 일반 도움으로 셈",
    f"2014.8.1 이후 도움 {POST_A}개 중 {POST_A - len(ADD_CONFIRMED)}개는 FotMob도 디 나탈레 도움으로 적음. FotMob에 없지만 다른 출처 2곳이 확인해 넣은 2개: 2015.8.16 코파 이탈리아 노바라전 31분 테로 골(Forza Italian Football·Football Italia), 2016.2.28 베로나전 56분 테로 골(Blitz quotidiano·ESPN — 디 나탈레 크로스를 테로가 첫 슈팅이 막힌 뒤 다시 넣음)",
    "다른 출처 2곳이 확인하지 못해 뺀 도움: 2015.4.25 밀란전 58분 핀치 골(한 블로그만 디 나탈레 코너킥으로 적고 ESPN·Sports Mole 등은 코너킥 뒤 흘러나온 공으로 적음)",
    "FotMob에만 있는 도움 2개는 넣지 않음: " + "; ".join(FM_ONLY),
    f"상대 Elo는 같은 경기를 다룬 우디네세 동료 자료(칸드레바·콰드라도·브루노 페르난데스) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위를 기존 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "순위는 Transfermarkt 최종 순위표(세리에A·B, 세리에C1 2001-02·2002-03), 세리에C2 1997-98 B조·1998-99 A조·2006-07 C조는 Transfermarkt에 표가 없어 이탈리아어 위키백과 대회 문서의 최종 순위를 씀. 세리에A 18팀 시즌(2002-03·2003-04)은 다른 선수 자료의 18팀 순위값(7·9·12·16위는 앞뒤 값의 가운데), 20팀 시즌은 다른 선수 자료와 같은 순위값, 세리에B는 다른 선수 자료와 같은 리그 모형(평균 1578)",
    "세리에C1(3부)은 다른 선수 자료와 같은 추정 모형(세리에B 평균에서 세리에A·B 평균 차만큼 내린 약 1417, 2부 흩어짐 곡선: 18팀 조 1위 1546 … 18위 약 1290), 세리에C2(4부)는 한 단계 더 내린 약 1255(다른 선수 자료의 레가 프로 2부와 같은 모형: 18팀 조 1위 1385 … 18위 약 1129)로 모두 '추정'(근거 약함). 세리에C2 상대 골·도움 기록이 이 선수 SOC를 낮게 잡는 쪽으로 작용함",
    "직접 추정(모두 '추정'): 디나모 자그레브 2008-09(크로아티아 1위) 1520, 레흐 포즈난 2008-09(폴란드 3위) 1439(같은 시즌 2위 1465·4위 1412의 가운데), 안지 마하치칼라 2012-13(러시아 3위) 1574(다른 선수 자료의 러시아 리그 모형 값), 시로키 브리예그 2013-14(보스니아 2013-14 2위) 1400, 슬로반 리베레츠 2013-14(체코 2013-14 4위) 1462. 다른 선수 자료의 같은 팀 다른 시즌 값이나 같은 리그 비슷한 순위 값에 맞춘 것으로 근거 약함",
    "대회 비중: 코파 이탈리아는 국내컵(조별·1~4라운드·16강은 낮은 비중, 8강 이후 높은 비중), 챔스 3차 예선·플레이오프는 챔스 예선, UEFA컵 1라운드·유로파 예선(3차 예선·플레이오프)은 유로파 예선, UEFA컵 조별·유로파 조별은 유로파 조별, UEFA컵 32강·16강과 유로파 16강은 유로파 토너먼트. 코파 이탈리아 조별(1999-2005 여름 조별 리그)은 리그식(무승부 1점). 1998 세리에C2 잔류 플레이아웃은 리그 비중(다른 선수 자료의 세리에A 잔류 플레이아웃 선례)",
    f"두 경기 합산(UEFA 대회 예선·토너먼트, 코파 이탈리아 두 경기 라운드, 세리에C2 플레이아웃) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회·코파 이탈리아는 원정 다득점·연장 적용. 세리에C2 플레이아웃은 합계 동률이면 정규리그 순위가 높은 팀이 잔류하는 방식이라 원정 다득점·연장 없음으로 둠(순위 규정은 계산에 넣지 않음). 디 나탈레가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "승부차기: 2008.10.2 UEFA컵 도르트문트전, 2009.1.21 코파 이탈리아 8강 삼프도리아전(연장, 120분), 2011.1.19 코파 이탈리아 16강 삼프도리아전, 2012.8.28 챔스 예선 브라가전은 승부차기 골을 스코어에 넣지 않음. 연장 시간 골은 없음",
    "시즌 구분: 8월 1일 기준(1998.6.7 플레이아웃은 1997-98, 2013.8.1 유로파 예선 시로키 브리예그전은 2013-14)",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 클럽 우승 없음(엠폴리 2001-02 세리에B 승격은 우승이 아니라 뺌). 세리에A 득점왕 2009-10(29골)·2010-11(28골), 코파 이탈리아 2014-15 득점 1위(4골), 이탈리아 올해의 선수 2010(AIC 오스카 델 칼초 최우수 이탈리아 선수), AIC 세리에A 올해의 팀 2010-11·2011-12·2012-13(이탈리아어 위키백과 Squadra dell'anno AIC). 유로 2012 준우승 등 대표팀 기록은 뺌",
    "2016.5.15 카르피전이 마지막 공식 경기(2016년 은퇴)",
]
NOTE = "\n".join(NOTE_LINES)
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
    if len({(r[1], r[3]) for r in rs}) > 1: problems.append(("같은 날 상대·대회 다름", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
mm = {m[0]: m for m in M}
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
api_g = collections.Counter(); api_a = collections.Counter()
for g in GAMES:
    api_g[ldate(g)] += int(g["goals"] or 0); api_a[ldate(g)] += int(g["assists"] or 0)
gcount = collections.Counter(r[9] for r in E if r[0] == "g")
for d in set(api_g) | set(gcount):
    if api_g[d] != gcount[d]: problems.append(("골 수 API와 다름", d, api_g[d], gcount[d]))
acount = collections.Counter(r[9] for r in E if r[0] == "a")
A_DIFF = sorted((d, api_a[d], acount[d]) for d in set(api_a) | set(acount) if api_a[d] != acount[d])
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const DNT_E={J(E)};\nconst DNT_M={J(M)};\nconst DNT_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG, "seasons": SEASONS,
               "assist_count_vs_api": A_DIFF},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
    for k, v in SEASONS.items(): print(" ", k, v)
    print("도움 수 API와 다른 날:", A_DIFF)
