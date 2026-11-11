#!/usr/bin/env python3
"""Ruud van Nistelrooy: raw/ -> vannistelrooy.json + src/data/nis.js (판정 근거는 judgments.md)

  python3 players/vannistelrooy/build_vannistelrooy.py          # 쓰기
  python3 players/vannistelrooy/build_vannistelrooy.py --debug  # Elo 출처
  python3 players/vannistelrooy/build_vannistelrooy.py --fm     # FotMob 골 대조(2010-11 이후)
  python3 players/vannistelrooy/build_vannistelrooy.py --cross  # 동료(호날두·루니·이과인·로번·카카·벤제마·이스코) 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/{ron,roo,hig,rob,kak,bzm,isc}.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "nis.js")
OUT_JSON = os.path.join(HERE, "vannistelrooy.json")
ME = "뤼트 판니스텔로이"
CLUB_ID = {"404": "dbnis", "306": "heenis", "383": "psvnis", "985": "munnis", "418": "rmnis", "41": "hsvnis", "1084": "malnis"}

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
EXCL_G = {}     # 골 제외 없음(자책골 0, Transfermarkt 골 348 = 위키백과(네덜란드어) 통산)
EXCL_A = {}     # 상대 자책골 도움 없음(자동 점검)
PK_FIX = {}
MIN_FIX = {}
AUTO_EXCL_TYPES = {"Penalty: Fouled player": "PK 유도", "Shot on goal": "슈팅 리바운드(Shot on goal)"}
# 출전 분 수정: 없음. 1998.4.22 트벤테 원정(1047261)은 Transfermarkt 선수 경기 성적 1분(교체 투입 뒤 퇴장)을 그대로 씀 — judgments.md 2절

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"NL1", "NL2", "GB1", "ES1", "L1", "PON2"}   # PON2 = 1995-96 에이르스터 디비시 승격 플레이오프 조별(리그식, 리그 비중)
CUP = {"NLP", "FAC", "CGB", "CDR", "DFB"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth") or r.startswith("third place"): return "dk"   # FA컵 6라운드 = 8강, KNVB 3위 결정전(준결승 뒤) = 8강 이후
        return "dc"
    if cid in ("GBCS", "NLSC", "SUC"): return "df"   # 슈퍼컵류 = 국내컵 결승
    if cid == "UI": return "elq"                      # 인터토토(비야 선례)
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"        # 1999-2003 2차 조별(Group 1~4·A~D 표기) 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 유로파 2009-10 32강('Second Round')·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # KNVB컵 조별·인터토토 조별·챔스 조별
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]
    leg = 1 if "1st" in g["round"].lower() else 2
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    return [leg, home, fu, ft, 1, 1]   # UEFA·리그컵 준결승·코파 델 레이·수페르코파: 원정 다득점·연장

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
MANUAL_ALIAS = {"inter milan": "inter"}
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

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

def mid(tab, r):
    """빈 순위: 앞뒤 기존 순위값의 가운데(한 칸 이상 비면 그 사이 직선)"""
    if r in tab: return tab[r], False
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return int(round(tab[lo] + (tab[hi] - tab[lo]) * (r - lo) / (hi - lo))), True

# 에레디비시(18팀): 기존 자료 고정 순위값(시즌 조정 없는 리그, 1~18위 모두 있음)
EREDIV = {}
for e in ENTS:
    m = re.match(r"^에레디비시 \d{4}-\d\d (\d+)위$", e["lv"] or "")
    if m: EREDIV.setdefault(int(m.group(1)), collections.Counter())[e["elo"]] += 1
EREDIV = {r: c.most_common(1)[0][0] for r, c in EREDIV.items()}
assert sorted(EREDIV) == list(range(1, 19)), EREDIV
# 에이르스터 디비시(네덜란드 2부, 18팀): docs 4절 평균 1331 + 2부 흩어짐 51.24 × 표준 순위 곡선(세리에A 20팀 값에서 만든 21칸 곡선, 팔카오 선례)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
# 분데스리가 2003-04 이전: 기존 자료 고정 순위값(시즌마다 같음)
BL_OLD = {}
for e in ENTS:
    m = re.match(r"^분데스리가 (199\d|200[0-3])-\d\d (\d+)위$", e["lv"] or "")
    if m: BL_OLD.setdefault(int(m.group(2)), collections.Counter())[e["elo"]] += 1
BL_OLD = {r: c.most_common(1)[0][0] for r, c in BL_OLD.items()}
# 프리미어리그: 기존 시즌별 순위값, 빈 순위는 2003-04 값 + 같은 시즌 차이 중앙값(제라드 방식)
PL_BASE = ents_map("프리미어리그", "2003-04")
def median(xs):
    xs = sorted(xs); n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
def premier(season, r):
    m = ents_map("프리미어리그", season)
    if r in m: return m[r], False
    sh = median([v - PL_BASE[k] for k, v in m.items()])
    return int(round(PL_BASE[r] + sh)), True
CH = {1: 1761, 2: 1717, 3: 1689, 4: 1669, 5: 1656, 6: 1648, 7: 1642, 8: 1635, 9: 1626, 10: 1617, 11: 1607, 12: 1600,
      13: 1594, 14: 1589, 15: 1584, 16: 1580, 17: 1578, 18: 1572, 19: 1564, 20: 1555, 21: 1547, 22: 1542, 23: 1537, 24: 1527}

def model(lg, season, r, n):
    """(Elo, lv) — 순위표 + 기존 순위값/리그 모형"""
    if lg == "NL1":
        assert n == 18
        return EREDIV[r], f"에레디비시 {season} {r}위"
    if lg == "NL2":
        return int(round(1331 + SD2 * curve(r, n))), f"에이르스터 디비시(네덜란드 2부) {season} {r}위"
    if lg == "L1" and int(season[:4]) <= 2003:
        v, it = mid(BL_OLD, r)
        return v, f"분데스리가 {season} {r}위"
    if lg == "GB1":
        v, it = premier(season, r)
        return v, f"프리미어리그 {season} {r}위"
    if lg == "GB2":
        return CH[r], f"챔피언십 {season} {r}위"
    if lg == "ES1":
        m = ents_map("라리가", season)
        if m:
            v, it = mid(m, r)
            return v, f"라리가 {season} {r}위" + (" (추정, 앞뒤 순위값 사이)" if it else "")
    if lg == "FR1":
        m = ents_map("리그1", season)
        if m:
            v, it = mid(m, r)
            return v, f"리그1 {season} {r}위" + (" (추정, 앞뒤 순위값 사이)" if it else "")
    return None

RANK_LG = ["NL1", "NL2", "L1", "GB1", "GB2", "ES1", "FR1"]

# 직접 추정(모두 '추정'): (key, 시즌) -> (Elo, lv). 순위는 raw/ranks.txt(Transfermarkt·위키백과 순위표)
MAN = {
    (key("KVV Quick Boys Katwijk"), "1994-95"): (1100, "네덜란드 아마추어 (추정, 다른 선수 자료 네덜란드 아마추어 1100과 같음)"),
    (key("VV Katwijk"), "1994-95"): (1100, "네덜란드 아마추어 (추정, 다른 선수 자료 네덜란드 아마추어 1100과 같음)"),
    (key("HJK Helsinki"), "1998-99"): (1350, "핀란드 1998 2위 (추정, 다른 선수 자료 핀란드 1350과 같음)"),
    (key("NK Maribor"), "1998-99"): (1420, "슬로베니아 1998-99 1위 (추정, 다른 선수 자료 마리보르 1420과 같음)"),
    (key("Rangers FC"), "1999-00"): (1620, "스코틀랜드 1999-00 1위 (추정, 다른 선수 자료 레인저스 1620과 같음)"),
    (key("Rangers FC"), "2003-04"): (1620, "스코틀랜드 2003-04 2위 (추정, 다른 선수 자료 레인저스 1620과 같음)"),
    (key("Olympiacos Piraeus"), "2001-02"): (1690, "그리스 2001-02 1위 (추정, 다른 선수 자료 올림피아코스 2000-01·2004-05 1690과 같음)"),
    (key("Zalaegerszegi TE FC"), "2002-03"): (1420, "헝가리 2002-03 4위 (추정, 다른 선수 자료 헝가리 3위 1420과 같은 수준)"),
    (key("Maccabi Haifa"), "2002-03"): (1500, "이스라엘 2002-03 2위 (추정, 다른 선수 자료 이스라엘 2위·상위권 1500과 같음)"),
    (key("AC Sparta Praha"), "2004-05"): (1520, "체코 2004-05 1위 (추정, 다른 선수 자료 스파르타 프라하 2003-04·2005-06 1520과 같음)"),
    (key("Écija Balompié"), "2006-07"): (1350, "스페인 3부 (추정, 다른 선수 자료 스페인 3부 1350과 같음)"),
    (key("BATE Borisov"), "2008-09"): (1500, "벨라루스 2008 1위 (추정, 다른 선수 자료 BATE 1500과 같음)"),
    (key("RSC Anderlecht"), "2009-10"): (1740, "벨기에 1부 2009-10 1위 (추정, 평균 1440에 2010-11 1위 모형값과 같은 차이 +300)"),
    (key("Torgelower SV Greif"), "2010-11"): (1180, "독일 5부(NOFV-오버리가) 2010-11 (추정, 다른 선수 자료 독일 5부 1180과 같음)"),
}
# 순위 확인 + 기존 리그 순위값(시즌 조정 없는 리그)
FIXED = {
    (key("SL Benfica"), "1998-99"): (1730, "포르투갈 1부 1998-99 3위"),      # 18팀 시즌 3위 값(2020-21·2021-22)
    (key("Boavista FC"), "2001-02"): (1795, "포르투갈 1부 2001-02 2위"),     # 18팀 시즌 2위 값(2017-18·2024-25)
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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    if cid in ("CL", "CLQ", "EL", "UI"): seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)]
    else: seasons = [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    for s in seasons:
        if (k, s) in FIXED:
            e, lv = FIXED[(k, s)]; ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, e, lv, "fixed"))
            return e, lv
    for s in seasons:
        for lg in RANK_LG:
            t = RANKS.get((lg, s))
            if t and k in t:
                r, n = t[k]
                res = model(lg, s, r, n)
                if res:
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model"))
                    return res
    return None

# ---------------------------------------------------------------- 출전
def opp_name(g):
    return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

def ldate(g):
    return g["date_local"]   # Transfermarkt 리포트 날짜(모두 유럽 현지)

M = []
for g in GAMES:
    M.append([ldate(g), opp_name(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et):
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
    isg, isa = e["vn_scorer"] == "1", e["vn_assist_other"] == "1"
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    tag = f"{gid}|{e['minute']}"
    mi, dm = minute(MIN_FIX.get(tag, e["minute"]))
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
    d = ldate(g); opp = opp_name(g)
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        if e["vn_self_assist"] == "1":
            judg.append(("도움 아님(본인 PK 골의 본인 도움)", d, opp, e["minute"], e["assist_type"]))
        add_row("g", mi, dm, gf, ga, int((e["penalty"] == "1" and e["goal_desc"] == "Penalty") or tag in PK_FIX), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["assist_type"] in AUTO_EXCL_TYPES:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], AUTO_EXCL_TYPES[e["assist_type"]])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k)
        if not x[4].startswith("table"): print(x)
if __name__ == "__main__" and "--table" in sys.argv:
    seen = set()
    for x in ELO_LOG:
        if x[4].startswith("table") and (x[1], x[2]) not in seen:
            seen.add((x[1], x[2])); print(x)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["vn_scorer"] == "1" and e["own_goal"] != "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
FM_GAMES = 0
for gid, evs in TMG.items():
    if gid not in FM_EV or not FM_EV[gid]: continue
    FM_GAMES += 1
    fg = [r for r in FM_EV[gid] if r["vn_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        h, a = map(int, t["score_home_away_after"].split("-")); fh, fa = map(int, f["newScore_home_away"].split("-"))
        if tpk != fpk or abs(tm_min - fm_min) > 1 or (h, a) != (fh, fa):
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], t["score_home_away_after"], f["time"], f["overloadTime"], f["newScore_home_away"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)
    print("FotMob 대조 경기", FM_GAMES)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    t = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", t, re.S)
    return json.loads(m.group(1))
MATES = {"Cristiano Ronaldo": ("ron.js", "RON", "2003-08-12", "2006-07-01"), "Wayne Rooney": ("roo.js", "ROO", "2004-08-31", "2006-07-01"),
         "Gonzalo Higuaín": ("hig.js", "HIG", "2007-01-01", "2010-01-01"), "Arjen Robben": ("rob.js", "ROB", "2007-08-22", "2009-08-29"),
         "Kaká": ("kak.js", "KAK", "2009-07-01", "2010-01-01"), "Karim Benzema": ("bzm.js", "BZM", "2009-07-01", "2010-01-01"),
         "Cristiano Ronaldo ": ("ron.js", "RON", "2009-07-01", "2010-01-01"), "Isco": ("isc.js", "ISC", "2011-07-01", "2012-07-01")}
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items()}
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
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    return diffs
def nm_eq(a, b): return norm(a) == norm(b)
for nm0, ent in MATE_E.items():
    nm = nm0.strip(); lo, hi = MATES[nm0][2], MATES[nm0][3]
    for r in E:   # 판니스텔로이 도움 → 동료 골
        if r[0] == "a" and nm_eq(r[13], nm) and lo <= r[9] < hi:
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("판니스텔로이 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:  # 동료 도움 → 판니스텔로이 골
        if x[0] == "a" and x[13] == "Ruud van Nistelrooy" and lo <= x[9] < hi:
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→판니스텔로이 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:  # 같은 경기 Elo/lv/대회
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "연장"))]
                    if dd: CROSS.append(("같은 경기 다름", nm, r[9], r[1], dd))
                    break
    for x in ent:  # 동료 골에 TM 판니스텔로이 도움이 있는데 이 파일에 도움 행이 없음
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["vn_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 판니스텔로이 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:  # TM 동료 도움 → 판니스텔로이 골이 동료 파일에 없음
        if e["vn_scorer"] == "1" and e["gameId"] in G and nm_eq(e["assist_player"], nm):
            d = ldate(G[e["gameId"]])
            if lo <= d < hi and not any(x[0] == "a" and x[9] == d and abs(x[4] - minute(e["minute"])[0]) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움이 동료 파일에 없음", nm, d, e["minute"], e["assist_type"], e["goal_desc"]))
    for x in ent:  # 동료 파일의 판니스텔로이 도움 → 동료 골이 이 파일에 없음
        if x[0] == "g" and lo <= x[9] < hi:
            pass
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("dbnis", "1997-06-21", "FC 덴보스", "1993~1997"), ("heenis", "1998-07-01", "헤이렌베인", "1997~1998"),
         ("psvnis", "2001-07-01", "PSV", "1998~2001"), ("munnis", "2006-07-28", "맨체스터 유나이티드", "2001~2006"),
         ("rmnis", "2010-01-24", "레알 마드리드", "2006~2010"), ("hsvnis", "2011-07-01", "함부르크", "2010~2011"),
         ("malnis", None, "말라가", "2011~2012")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != CLUB_ID[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
if __name__ == "__main__" and "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E), sum(r[8] for r in E), sum(m[3] for m in M), len(E))
    print([j for j in judg])
    print("합산", sum(1 for r in E if len(r) > 14), len({r[9] for r in E if len(r) > 14}), "연장", [r for r in E if r[10]])
    print("단판", collections.Counter((r[3], r[7]) for r in E))
