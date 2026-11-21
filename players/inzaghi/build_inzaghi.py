#!/usr/bin/env python3
"""필리포 인자기: raw/ -> inzaghi.json + src/data/inz.js (판정 근거는 judgments.md)

  python3 players/inzaghi/build_inzaghi.py            # 파일 쓰기
  python3 players/inzaghi/build_inzaghi.py --debug    # Elo 출처 목록
  python3 players/inzaghi/build_inzaghi.py --fm       # FotMob 골 대조
  python3 players/inzaghi/build_inzaghi.py --cross    # 동료 파일(델 피에로·지단·셰브첸코·카카·호나우두·호나우지뉴 등) 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(동료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "inz.js")
OUT_JSON = os.path.join(HERE, "inzaghi.json")
ME = "필리포 인자기"
INZ = "Filippo Inzaghi"

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
# 골 제외(Transfermarkt 리포트 골이지만 넣지 않음): gameId|분 -> 이유
EXCL_G = {}

# 도움 제외는 유형으로 자동 판정(아래 add 부분): 'Penalty: Fouled player'(PK 유도), 'Shot on goal'(슈팅 리바운드), 상대 자책골.
# 도움 유형이 비어 있는 5개는 TM 단일 출처(2014-08-01 전)로 남김.
# 본인 PK 골의 본인 도움(inz_self_assist): 990059 2000-09-13 함부르크전 88분 PK 골 -> 도움 아님.

# 일부러 PK가 아닌 골로 처리: 1022468 밀란–레지나 2002-11-03 20분 'Penalty rebound' (TM penalty 플래그 0)

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "IT3A", "IT3B", "ITPO"}   # ITPO = 1998-99 세리에A UEFA컵 진출 플레이오프(두 경기, 리그 비중 + 합산: 호나우두·메르턴스 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "CIT":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # First/Second Round, Round of 16, Last 16
    if cid in ("SCI", "USC"): return "df"
    if cid in ("WEPO", "KLUB"): return "cwc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 2002-03 2차 조별(Group 3)도 조별
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UI": return "elq"   # 인터토토컵: 램파드·델 피에로 선례(전 라운드 elq)
    if cid == "EPP":   # 컵위너스컵: 호나우두·네드베드 선례
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r and g["competitionId"] != "ITPO": return 0
    return 1 if ("1st" in r) else 2

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
    if g["competitionId"] == "ITPO":   # 1998-99 UEFA컵 진출 플레이오프: 원정 다득점으로 결정(연장 없음) — 우디네세가 원정 다득점 승
        return [leg, home, fu, ft, 1, 0]
    # 원정 다득점·연장: UEFA 대회(2020-21까지), 코파 이탈리아(2021-22까지), 인터토토컵(델 피에로·램파드 선례)
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

# 순위표(Transfermarkt): (리그, 시즌) -> {key: (순위, 팀 수)}
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

# 표준 순위 곡선(세리에A 20팀 기존 값을 표준화, 다른 선수 자료와 같음)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24   # 2부 흩어짐(세리에B·튀르키예 2부 선례)

def ents_map(prefix, season):
    """기존 선수 자료의 '<prefix> <season> N위' 값(다수값)"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

# 세리에A 18팀(1988-89~2003-04): 기존 자료의 순위값, 7·9·12·16위는 앞뒤 값의 가운데(토티·델 피에로·셰브첸코 자료와 같음)
SA18 = {1: 1969, 2: 1884, 3: 1837, 4: 1808, 5: 1793, 6: 1780, 7: 1762, 8: 1743, 9: 1728, 10: 1713, 11: 1704, 12: 1697, 13: 1690, 14: 1676, 15: 1657, 16: 1645, 17: 1633, 18: 1614}
SB_MEAN = 1577.78   # 세리에B(문서 4절 평균·흩어짐)
C1_MEAN = 1416.56   # 세리에C1·레가 프로 1(3부) 평균(인시녜 선례 1416.56, 토티 1994-95·델 피에로 1996-97 값도 재현), 흩어짐 SD2

def c1_elo(r, n):
    return int(round(C1_MEAN + SD2 * curve(r, n)))

def model(lg, season, r, n):
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
        return int(round(SB_MEAN + SD2 * curve(r, n))), f"세리에B {season} {r}위"
    if lg in ("IT3A", "IT3B"):
        grp = "A" if lg == "IT3A" else "B"
        if int(season[:4]) >= 2008: return c1_elo(r, n), f"세리에C(레가 프로 1) {grp}조 {season} {r}위/{n}팀 (추정)"
        return c1_elo(r, n), f"세리에C1(3부) {grp}조 {season} {r}위/{n}팀 (추정)"
    for lg2, lab in (("ES1", "라리가"), ("NL1", "에레디비시"), ("PO1", "포르투갈 1부")):
        if lg == lg2:
            m = ents_map(lab, season)
            if r in m: return m[r], f"{lab} {season} {r}위"
            vals = collections.Counter()
            for e in ENTS:
                mm = re.match("^" + re.escape(lab) + r" (\d{4}-\d\d) (\d+)위$", e["lv"] or "")
                if mm and int(mm.group(2)) == r: vals[e["elo"]] += 1
            if vals:
                return vals.most_common(1)[0][0], f"{lab} {season} {r}위"
            return None
    return None

RANK_LG = ["IT1", "IT2", "IT3A", "IT3B", "ES1", "NL1", "PO1"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정'): (key, 시즌) -> (Elo, lv)
MAN = {
    (key("Halmstads BK"), "1995"): (1439, "스웨덴 1995 3위/14팀 (추정, 다른 선수 자료의 알스벤스칸 2001 3위 1439와 같은 값; 네드베드 자료 할름스타드 1994 7위 1390과 같은 순위 보간)"),
    (key("KF Teuta"), "1995-96"): (1300, "알바니아 1995-96 2위 (추정, 다른 선수 자료의 KF 티라나 2009-10 3위 1300과 같은 값)"),
    (key("Panathinaikos"), "2000-01"): (1560, "그리스 2000-01 2위 (추정, 다른 선수 자료의 파나티나이코스 2001-02·2009-10 2위 1560과 같은 값)"),
    (key("FC Slovan Liberec"), "2002-03"): (1480, "체코 2002-03 4위 (추정, 다른 선수 자료의 체코 4위 1480과 같음)"),
}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    # 1) 같은 경기 다른 선수 자료(날짜 ±1)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    euro = cid in ("CL", "CLQ", "EL", "UEFA", "WEPO", "USC", "UI", "EPP", "KLUB")
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
                    ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg))
                    return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_tm_report"] or g["date_local"]

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
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

TM_A_TYPES = collections.Counter()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["inz_scorer"] == "1", e["inz_assist_other"] == "1", e["inz_self_assist"] == "1"
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
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    et = 0
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        TM_A_TYPES[e["assist_type"]] += 1
        if e["own_goal"] == "1" or not ours:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "상대 자책골")); continue
        if e["assist_type"] == "Penalty: Fouled player":
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "PK 유도")); continue
        if e["assist_type"] == "Shot on goal":
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "슈팅 리바운드")); continue
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows


# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["inz_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
FM_SEEN = 0
for gid, evs in TMG.items():
    if gid not in FM_EV: continue
    fg = [r for r in FM_EV[gid] if r["inz_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if not fg and not any(r["scorer"] for r in FM_EV[gid]): continue
    FM_SEEN += len(evs)
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        if tpk != fpk or tm_min != fm_min:
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    print("FotMob과 대조한 골", FM_SEEN)
    for x in FM_CMP: print(x)
    for gid in FM_EV:
        for r in FM_EV[gid]:
            if r["inz_scorer"] == "1" or r["inz_assist"] == "1": print("FM", ldate(G[gid]), r["time"], r["overloadTime"], r["scorer"], "| assist:", r["assistStr"], r["newScore_home_away"])

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {   # 이름: (파일, 접두어)
    "Alessandro Del Piero": ("del.js", "DEL"), "Zinédine Zidane": ("zid.js", "ZID"), "Thierry Henry": ("hen.js", "HEN"),
    "Andriy Shevchenko": ("she.js", "SHE"), "Kaká": ("kak.js", "KAK"), "Ronaldo": ("rno.js", "RNO"),
    "Ronaldinho": ("rdg.js", "RDG"), "Zlatan Ibrahimović": ("ibr.js", "IBR"), "Clarence Seedorf": ("see.js", "SEE"),
}
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    ta = (a[14] if len(a) > 14 else None) or None; tb = (b[14] if len(b) > 14 else None) or None
    if a[7] != b[7] or ta != tb:
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    if a[10] != b[10]: diffs.append(f"연장 {a[10]}/{b[10]}")
    return diffs
TMEV = [(e, ldate(G[e["gameId"]]), minute(e["minute"])[0]) for e in EVENTS if e["gameId"] in G]
for nm, (fn, P) in MATES.items():
    if not os.path.exists(os.path.join(ROOT, "src", "data", fn)): CROSS.append(("파일 없음", nm)); continue
    ent = load_js(fn, P)
    # 1) 인자기 도움 -> 동료 골
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("인자기 도움->" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    # 2) 동료 도움 -> 인자기 골 (TM 리포트의 도움 선수로)
    for e, d, mi in TMEV:
        if e["inz_scorer"] == "1" and norm(e["assist_player"]) == norm(nm):
            mine = [r for r in E if r[0] == "g" and r[9] == d and r[4] == mi]
            hit = sorted([x for x in ent if x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 3], key=lambda x: abs(x[4] - mi))
            CROSS.append((nm + " 도움->인자기 골", d, mi, e["assist_type"] or "-", "동료 파일에 없음" if not hit else (cmp_rows(mine[0], hit[0]) or "같음")))
    # 3) 동료 파일의 '인자기' 표기 도움이 TM 리포트와 맞는지
    for x in ent:
        if x[0] == "a" and "Filippo Inzaghi" in str(x[13]):
            if not any(e["inz_scorer"] == "1" and norm(e["assist_player"]) == norm(nm) and d == x[9] and abs(mi - x[4]) <= 3 for e, d, mi in TMEV):
                CROSS.append(("동료 파일의 인자기 골 도움이 TM 리포트와 다름", nm, x[9], x[4]))
    for x in ent:
        if x[0] == "g" and False: pass
    # 4) TM 리포트에 인자기 도움인 동료 골 중 이 자료에서 뺀 것
    for e, d, mi in TMEV:
        if e["inz_assist_other"] == "1" and norm(e["scorer"]) == norm(nm) and not any(r[0] == "a" and r[9] == d and r[4] == mi for r in E):
            has = any(x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 3 for x in ent)
            CROSS.append(("TM 인자기 도움을 뺀 동료 골", nm, d, e["minute"], e["assist_type"], "동료 골 행 있음" if has else "동료 골 행 없음"))
    # 5) 같은 경기(날짜·상대 같음)의 상대 Elo·lv·대회
    for x in ent:
        for r in E:
            if r[9] == x[9] and (key(r[1]) == key(x[1]) or _sub(key(r[1]), key(x[1]))):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                CROSS.append(("같은 경기 비교", nm, r[9], r[1], dd or "같음"))
                break
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] + ("" if c[-1] != "같음" else " (같음)") for c in CROSS))
    sys.exit(0)


# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("piaiz", "1992-07-01", "피아첸차", "1991~1992", "피아첸차"), ("lefiz", "1993-07-01", "레페(임대)", "1992~1993", "레페"),
         ("veriz", "1994-07-01", "헬라스 베로나(임대)", "1993~1994", "베로나"), ("piaiz", "1995-07-01", "피아첸차", "1994~1995", "피아첸차"),
         ("pariz", "1996-07-01", "파르마", "1995~1996", "파르마"), ("atliz", "1997-07-01", "아탈란타", "1996~1997", "아탈란타"),
         ("juviz", "2001-07-02", "유벤투스", "1997~2001", "유벤투스"), ("acmiz", None, "AC 밀란", "2001~2012", "밀란")]
TM_CLUB = {"1408": "piaiz", "25265": "lefiz", "276": "veriz", "130": "pariz", "800": "atliz", "506": "juviz", "5": "acmiz"}
def club_of(d):
    for k, u, *_ in CLUBS:
        if u is None or d < u: return k
def stint_of(d):
    for i, c in enumerate(CLUBS):
        if c[1] is None or d < c[1]: return i
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((i, [0, 0, 0, 0]) for i in range(len(CLUBS)))
for m in M: ST[stint_of(m[0])][0] += 1; ST[stint_of(m[0])][3] += m[3]
for r in E: ST[stint_of(r[9])][1 if r[0] == "g" else 2] += 1
STK = collections.OrderedDict()
for i, v in ST.items():
    k = CLUBS[i][0]; STK.setdefault(k, [0, 0, 0, 0])
    for j in range(4): STK[k][j] += v[j]
def season_of(d, k):   # 계산기 시즌 구분(유벤투스 7월 10일, 나머지 기본 8월 1일)
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:])
    new = (m, dd) >= (7, 10) if k == "juviz" else m >= 8
    s = y if new else y - 1
    return f"{s}-{str(s + 1)[2:]}"
SEASON_TM = collections.Counter()
for g in GAMES:
    SEASON_TM[(club_of(ldate(g)), season_of(ldate(g), club_of(ldate(g))), g["season_tm"])] += 1

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
EX_PK = [x for x in judg if x[0] == "도움 제외" and x[5] == "PK 유도"]
EX_SH = [x for x in judg if x[0] == "도움 제외" and x[5] == "슈팅 리바운드"]
EX_OG = [x for x in judg if x[0] == "도움 제외" and x[5] == "상대 자책골"]
def ex_list(xs): return ", ".join(f"{d_(x[1])} {x[3]}분 {x[4].split()[-1]}" for x in sorted(xs, key=lambda x: (x[1], minute(x[3])[0])))
NTMA = sum(TM_A_TYPES.values())
UNTYPED = sorted((ldate(G[e["gameId"]]), e["minute"], e["scorer"]) for e in EVENTS if e["gameId"] in G and e["inz_assist_other"] == "1" and e["assist_type"] == "")
N_EL = len(E)
PKD = sorted(d_(r[9]) for r in E if r[0] == "g" and r[8])
FIRST, LAST = M[0], M[-1]


NAMEK = {"piaiz": "피아첸차", "lefiz": "레페", "veriz": "헬라스 베로나", "pariz": "파르마", "atliz": "아탈란타", "juviz": "유벤투스", "acmiz": "AC 밀란"}
NOTE_LINES = [
    f"필리포 인자기(피아첸차·레페·헬라스 베로나·파르마·아탈란타·유벤투스·AC 밀란)의 클럽 공식 경기 {NG}경기({d_(FIRST[0])} 모데나전 ~ {d_(LAST[0])} 노바라전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·이탈리아 대표팀·밀란 유스팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUBS[i][2]}({CLUBS[i][3]}) {c3(v)}" for i, v in ST.items())
    + f" (피아첸차 합계 {c3(STK['piaiz'])}). 출전 분 합계 {MIN_TOT:,}분(유벤투스 {STK['juviz'][3]:,}분, AC 밀란 {STK['acmiz'][3]:,}분)",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 나온 경기와 리그 밖 경기 전부). 출전 분이 없어 90분으로 추정한 경기는 없음. 경기 수·골은 영어 위키백과 클럽·시즌·대회별 기록과 같음(피아첸차 44·17, 레페 21·13, 베로나 37·14, 파르마 22·4, 아탈란타 34·25, 유벤투스 165·89, 밀란 300·126). 2010-11 이후 골 5개는 FotMob 경기 이벤트와 골 뒤 스코어·분이 모두 같음(FotMob은 그 전 경기 자료가 없음)",
    "뺀 기록: 밀란 프리마베라(유스) 2011.11.12 1경기와 이탈리아 U21·A대표팀 경기는 클럽 공식 경기가 아니라 넣지 않음. 이탈리아어 위키백과에만 있는 레페 1992-93 코파 이탈리아 세리에C 1경기(골 0)는 Transfermarkt에 없어 넣지 않음(이탈리아어 위키백과 클럽별 합은 624경기·288골). 레페 1992-93 세리에C1 A조 34라운드 중 Transfermarkt 일정에는 32경기만 올라 있고(7·24라운드 빠짐) 그 구간에 인자기 기록은 없음",
    "시즌 표기: 영어 위키백과는 2003.12.14 인터콘티넨털컵(보카 주니어스전, 기록 없음)을 2003-04에 넣고 Transfermarkt는 따로 2003 시즌으로 적음. 이 계산기는 경기 날짜로 2003-04에 셈",
    f"골: Transfermarkt 리포트 골 {NGo}개를 모두 씀(자책골 없음). PK 골 {NPK}개는 Transfermarkt 골 유형 'Penalty' 기준이며 선수 경기 성적의 PK 골 합계와 같음. 2002.11.3 레지나전 20분 골은 PK가 막힌 뒤 리바운드로 넣은 골('Penalty rebound')이라 PK가 아닌 일반 골로 셈",
    "2003.2.22 토리노전(세리에A 22라운드)은 63분(Transfermarkt 기준, 다른 자료는 64분)에 관중 난동으로 중단됐지만 0-3 필드 결과가 그대로 인정돼 경기 결과가 확정됨. 인자기의 2분 골(0-0에서 0-1)은 경기 중 나온 골이라 그대로 넣고 출전 분은 63분. 몰수 판정으로 결과가 바뀐 2005.4.12 인테르전과 달리 필드 결과 그대로",
    "승부차기·연장: 2003.5.28 챔스 결승(유벤투스전 0-0, 120분 출전)·2003.8.3 수페르코파 이탈리아나(유벤투스전, 120분)·2003.12.14 인터콘티넨털컵(보카 주니어스전, 60분 출전)은 모두 승부차기로 끝났고 인자기는 키커가 아니었으며 이 경기들에 골·도움은 없음. 연장 출전 2012.1.18 코파 이탈리아 노바라전은 Transfermarkt 기준 59분 출전(FotMob 라인업에는 인자기가 없음)",
    f"도움: 모두 2014.8.1 이전이라 Transfermarkt 경기 리포트 도움(단일 출처)을 씀. 도움 {NA} = 리포트에서 인자기가 동료 골에 준 도움 {NTMA} − PK 유도 {len(EX_PK)}({ex_list(EX_PK)}) − 슈팅 리바운드('Shot on goal') {len(EX_SH)}({ex_list(EX_SH)}) − 상대 자책골에 준 도움 {len(EX_OG)}({ex_list(EX_OG)}, 유형도 'Shot on goal'). 2000.9.13 함부르크전 88분 인자기 본인 PK 골에 본인 도움으로 적힌 것(리포트에만 있고 선수 경기 성적 도움 56에는 없음)은 도움이 아님",
    f"Transfermarkt 리포트에 도움 유형이 비어 있는 {len(UNTYPED)}개({', '.join(d_(d) + ' ' + m + '분 ' + sc.split()[-1] for d, m, sc in UNTYPED)})는 일반 도움으로 셈. 2014.8.1 이전 도움은 다른 출처로 경기마다 대조하지 못함. 예외로 2012.5.13 노바라전 82분 세이도르프 도움은 Transfermarkt에만 있고 FotMob 이벤트에는 도움이 비어 있으나, 웹 검색으로 본 경기 기사 요약이 세이도르프의 패스를 받아 넣은 결승골로 적어 남김(기사 원문은 열람하지 못함)",
    "2010.11.3 레알 마드리드전 68분 골은 FotMob이 즐라탄 도움으로 적었지만 Transfermarkt에는 도움이 없고, 즐라탄 자료도 이 FotMob 단독 도움을 넣지 않아(ESPN에도 도움 없음) 도움 없는 골로 둠. 2010.8.29 레체전·2010.9.18 카타니아전(호나우지뉴 도움)·2010.11.3 78분(가투소 도움)은 Transfermarkt와 FotMob이 일치",
    "동료 자료 대조: 델 피에로·지단·셰브첸코·카카·세이도르프·앙리·호나우지뉴와 같은 경기·같은 골의 행(날짜·분·스코어·대회·상대 Elo·합산 정보)이 다른 선수 자료와 모두 같음. 인자기가 도움을 주고 PK 유도라 뺀 델 피에로 골 7개, 슈팅 리바운드로 뺀 셰브첸코·카카 골은 각 선수 자료에 골 행만 있고 도움 행은 없어 서로 어긋나지 않음",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표)를 리그 모형에 넣은 값 순으로 씀(기록 {N_EL}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "세리에A 18팀 시즌(1995-96~2003-04)은 다른 선수 자료의 18팀 순위값(1위 1969 ~ 18위 1614, 7·9·12·16위는 앞뒤 값의 가운데 1762·1728·1697·1645)을 쓰고 20팀 시즌은 같은 시즌 다른 선수 자료 값. 세리에B(1993-94·1994-95·1999-00 나폴리·2005-06 브레시아)는 평균 1578·2부 흩어짐 모형(세리에B 20팀·22팀 기존 순위값을 재현). 세리에C1(3부, 레페 1992-93 A조 상대 8곳과 코파 이탈리아 상대 아르스 에 라보르 1996-97·노바라 2009-10)은 세리에C 평균 1416.56·2부 흩어짐 모형으로 계산한 추정(근거 약함, 순위는 Transfermarkt 순위표: 레페 A조 상대 8곳은 1·6·9·13·14·15·16·17위)",
    "직접 추정(모두 '추정'): 할름스타드 1995 스웨덴 3위/14팀 1439(영어 위키백과 순위, 다른 선수 자료의 알스벤스칸 2001 3위 1439와 같은 값), KF 테우타 1995-96 알바니아 2위 1300(영어 위키백과 순위, 다른 선수 자료의 KF 티라나 2009-10 3위 1300과 같은 값), 파나티나이코스 2000-01 그리스 2위 1560(다른 선수 자료의 2001-02 2위 값과 같음), 슬로반 리베레츠 2002-03 체코 4위 1480(다른 선수 자료의 체코 4위 1480과 같음)",
    "대회 비중: 코파 이탈리아는 16강까지 국내컵 기본 비중(첫 두 라운드·16강), 8강 이후 높은 비중(8강·준결승·결승, 2002-03 두 경기 결승은 두 경기 모두 결승), 수페르코파 이탈리아나·UEFA 슈퍼컵은 국내컵 결승, 인터콘티넨털컵(2003)과 클럽 월드컵(2007)은 클럽 월드컵, 챔스 2차 조별(2002-03)은 조별, 챔스 예선 3라운드는 챔스 예선, UEFA컵 1라운드·인터토토컵(1999 준결승·결승)은 유로파 예선, UEFA컵 2라운드 이후와 컵위너스컵 1995-96은 유로파 토너먼트(준결승·결승만 따로)로 계산함. 1998-99 세리에A UEFA컵 진출 플레이오프(유벤투스–우디네세 두 경기)는 리그 비중",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(UEFA 대회·인터토토컵·코파 이탈리아는 원정 다득점·연장 있음). 1999.5.31 세리에A UEFA컵 진출 플레이오프 2차전(유벤투스–우디네세 1-1, 23분 PK 골): 1차전 0-0이었고 연장 없이 원정 다득점으로 우디네세가 진출해 연장 없음으로 둠. 인자기가 뛰지 않은 차전 점수는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 유벤투스는 7월 10일 기준(1999.7.28·8.4 인터토토컵 준결승이 1999-00, 델 피에로·지단 선례), 그 밖의 클럽은 기본 8월 1일(2003.8.3 수페르코파·2006.8.9 챔스 예선은 새 시즌; Transfermarkt 시즌 표기와 모두 같음). 클럽 구분은 1992.7.1 전 피아첸차, 1993.7.1 전 레페(임대), 1994.7.1 전 베로나(임대), 1995.7.1 전 피아첸차, 1996.7.1 전 파르마, 1997.7.1 전 아탈란타, 2001.7.2 전 유벤투스, 이후 밀란",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 챔스 2002-03·2006-07, 세리에A 1997-98(유벤투스)·2003-04·2010-11(밀란), 코파 이탈리아 2002-03, 수페르코파 이탈리아나 1997-98·2011-12, UEFA 슈퍼컵 2003-04·2007-08, 클럽 월드컵 2007(Transfermarkt 표기 2008), 인터토토컵 1999-00, 세리에B 우승 1994-95(피아첸차). 준우승은 챔스 결승 2회(1997-98·2004-05)와 인터콘티넨털컵 2003만 넣음. 개인: 세리에A 득점왕 1996-97(24골). 월드컵 2006 우승·유로·U21 우승·1997 최우수 신인(Transfermarkt 'Best young player')은 칸이 없어 뺌",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "UA_K", "MAN"]:
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
    if r[0] == "g" and r[13] != 0: problems.append(("골 note", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r))
    if len(r) > 14 and r[7]: problems.append(("합산인데 단판", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const INZ_E={J(E)};\nconst INZ_M={J(M)};\nconst INZ_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG,
               "season_vs_tm": [list(k) + [v] for k, v in sorted(SEASON_TM.items())]},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for i, v in ST.items(): print(" ", CLUBS[i][0], CLUBS[i][3], v)

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)
    sys.exit(0)
