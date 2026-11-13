#!/usr/bin/env python3
"""Yoann Gourcuff (Transfermarkt 18912, FotMob 33744): raw/ -> gourcuff.json + src/data/gou.js (판정 근거는 judgments.md)

  python3 players/gourcuff/build_gourcuff.py            # 파일 쓰기
  python3 players/gourcuff/build_gourcuff.py --debug    # Elo 출처 로그
  python3 players/gourcuff/build_gourcuff.py --cross    # 동료 자료 대조
  python3 players/gourcuff/build_gourcuff.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(성인 클럽 출전 418경기; 렌 U19·리옹 B는 raw/youth_reserve_games.csv라 읽지 않음),
      raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv, raw/tm_two_leg_ties.csv,
      raw/fotmob_events.csv(FotMob 경기 이벤트, 2010-11~), raw/ranks.txt(Transfermarkt 순위표),
      elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(git에 올라간 다른 선수 자료),
      src/data/{lac,kak,see,inz,rno,dem}.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "gou.js")
OUT_JSON = os.path.join(HERE, "gourcuff.json")
ME = "요안 구르퀴프"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트(단일 출처 허용), 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
OTHER = {g: r["other_leg_id"] for g, r in TIES_RAW.items()}
for gid, r in INFO.items():
    if r["other_leg_id"]:
        OTHER.setdefault(gid, r["other_leg_id"]); OTHER.setdefault(r["other_leg_id"], gid)
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음; PK 유도·'Shot on goal'·상대 자책골은 아래 일반 규칙으로 뺌)
EXCL_A = {
    "1050119|90+5": "2010.11.2 벤피카전 90+5분 로브렌 헤더: Transfermarkt만 구르퀴프(프리킥), FotMob은 라카제트, ESPN은 곤살론스(세트피스) 도움으로 적음. maxifoot은 하프라인(센터서클) 프리킥이라고만 적고 키커를 밝히지 않음. 구르퀴프를 확인하는 다른 출처가 없고 두 출처가 다른 선수를 적어 넣지 않음(라카제트 자료도 이 도움을 넣지 않음)",
}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2511748|106": "maxifoot 경기 기사·선수 평점(구르퀴프 크로스를 라카제트가 마무리, 1-1 107분) · Lyonmag 경기 기사(구르퀴프가 수비를 버티고 컷백 → 라카제트). FotMob 이벤트는 이 골 도움 칸이 빔",
}

# Transfermarkt 리포트 골 목록에서 빠진 상대 골: gameId -> [분] (FotMob 경기 이벤트로 채움)
# 2014.1.5 라 쉬즈쉬르사르트전(쿠프 드 프랑스): TM 목록은 0-6에서 끝나지만 최종 1-6, FotMob 41분 피쇼 골(1-1). 라카제트 자료(58분 3-1)와 같음
MISSING_OPP = {"2387776": [41]}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "IT1"}
CUP = {"FRC", "FRL", "CIT"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "FRCH": return "df"     # 트로페 데 샹피옹 = 슈퍼컵 = 국내컵 결승
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "UEFA" and r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전) = 유로파 예선
    if cid in ("EL", "UEFA"):
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # UEFA컵 3라운드·유로파 16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local"]
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
    if cid in ("CL", "CLQ", "EL", "UEFA"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CIT":   # 코파 이탈리아: 원정 다득점 2021-22까지, 연장 있음
        ag, et = 1, 1
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
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))

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
        m = pat.match(e["lv"] or "")
        if m: c[int(m.group(1))][e["elo"]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
def mid(tab, r):
    if r in tab: return tab[r]
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None
    a, b = max(lo), min(hi)
    return half_up(tab[a] + (tab[b] - tab[a]) * (r - a) / (b - a))

def model(lg, season, r, n):
    if lg == "FR1":
        v = mid(ents_map("리그1", season), r)
        if v: return v, f"리그1 {season} {r}위"
    if lg == "FR2":
        v = ents_map("리그2", season).get(r)
        if v: return v, f"리그2 {season} {r}위"
        return half_up(1540 + SD2 * curve(r, n)), f"리그2 {season} {r}위 (추정, 프랑스 2부 평균 1540 모형)"
    if lg == "FR3":   # 리베리·발부에나 자료의 나시오날 순위값과 같은 식(1311 + 2부 흩어짐 × 순위 곡선)
        return half_up(1311 + SD2 * curve(r, n)), f"프랑스 3부(나시오날) {season} {r}위 (추정)"
    if lg in ("FR4A", "FR4B"):   # 팔카오·파예 자료의 프랑스 4부(CFA) 1220
        return 1220, f"프랑스 4부(CFA) {season} {lg[-1]}조 (추정)"   # 4부는 순위와 관계없이 같은 값이라 순위를 적지 않음
    if lg.startswith("FR5"):     # 파스토레 자료의 CFA2(5부) 1150
        return 1150, f"프랑스 5부(CFA2) {season} {lg[-1]}조 {r}위 (추정)"
    return None
RANK_LG = ["FR1", "FR2", "FR3", "FR4A", "FR4B", "FR5F", "FR5H"]

# 순위표·모형으로 안 되는 상대(직접 추정, 모두 '추정')
MAN = {}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

EURO = ("CL", "CLQ", "EL", "UEFA")
def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]",
                        sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in EURO else [eu]
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
    return g["date_local"]   # Transfermarkt 리포트·일정 날짜(유럽 현지). 2009.7.25 몬트리올·2012.7.28 해리슨(미국) 트로페도 현지 날짜와 같음

def oname(g):
    return g["opponent"].strip()

M = []
for g in GAMES:
    M.append([ldate(g), oname(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["gourcuff_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
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
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["gourcuff_scorer"] == "1", e["gourcuff_assist_other"] == "1"
    if e["gourcuff_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag)); EXCL_CNT["본인 도움"] += 1
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
    ga += sum(1 for t in MISSING_OPP.get(gid, []) if t < mi)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    et = int(ko == 1 and not tie and g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not dm)
    d = ldate(g); opp = oname(g)
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        if why:
            EXCL_CNT[why if tag not in EXCL_A else "개별 판정"] += 1
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if tag in ADD_CONFIRMED: judg.append(("다른 출처 2곳으로 넣은 도움", tag, ADD_CONFIRMED[tag]))
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - mi) <= 2]
            if not hit:
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local"] >= GAP and len(ts) > used_fm.get(gid, 0):
        FM_ONLY.append((gid, G[gid]["date_local"], ts))

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY, EXCL_CNT)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11~)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["gourcuff_scorer"] == "1" and e["gameId"] in G and G[e["gameId"]]["date_local"] >= "2010-08-01":
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["gourcuff_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Alexandre Lacazette": ("lac.js", "LAC", "2010-08-24", "2015-07-01"),
         "Kaká": ("kak.js", "KAK", "2006-07-01", "2008-07-01"),
         "Clarence Seedorf": ("see.js", "SEE", "2006-07-01", "2008-07-01"),
         "Filippo Inzaghi": ("inz.js", "INZ", "2006-07-01", "2008-07-01"),
         "Ronaldo": ("rno.js", "RNO", "2007-01-01", "2008-07-01"),
         "Ousmane Dembélé": ("dem.js", "DEM", "2016-01-01", "2016-07-01")}
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items()}
CROSS = []
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
    if a[7] != b[7] or ta != tb:
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
ME_N = lambda s: norm(s or "") in ("yoann gourcuff", "gourcuff")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("구르퀴프 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and ME_N(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→구르퀴프 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    for x in ent:   # Transfermarkt 구르퀴프 도움을 이 계산기에서 뺀 동료 골(참고)
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["gourcuff_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 구르퀴프 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:   # 동료 파일에서 구르퀴프 골의 도움으로 적혔어야 할 것(TM 리포트 기준, 참고)
        if e["gourcuff_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 구르퀴프 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
# 같은 날 같은 상대를 다룬 모든 다른 선수 기록과 Elo·lv·대회 비교
for r in E:
    for x in ENTS:
        if x["date"] == r[9] and key(x["opp"]) == key(r[1]) and (x["elo"] != r[2] or x["lv"] != r[12] or x["comp"] != r[3]):
            CROSS.append(("같은 경기 다른 선수 값 다름", x["p"], r[9], r[1], (r[2], r[12], r[3]), (x["elo"], x["lv"], x["comp"])))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("rengf", "2006-07-01", "스타드 렌", "2003~2006"), ("milgf", "2008-07-01", "AC 밀란", "2006~2008"),
         ("borgf", "2010-08-24", "보르도", "2008~2010"), ("lyogf", "2015-07-01", "리옹", "2010~2015"),
         ("rengf", "2018-07-01", "스타드 렌", "2015~2018"), ("dijgf", None, "디종", "2018")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {"rengf": "스타드 렌(2003~2006·2015~2018)", "milgf": "AC 밀란", "borgf": "보르도", "lyogf": "리옹", "dijgf": "디종"}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in ["rengf", "milgf", "borgf", "lyogf", "dijgf"])
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"273": "rengf", "5": "milgf", "40": "borgf", "1041": "lyogf", "2969": "dijgf"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["gourcuff_assist_other"] == "1")
NOTE_LINES = [
    f"요안 구르퀴프(스타드 렌·AC 밀란·보르도·리옹·스타드 렌·디종)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 크루아 드 사부아전 ~ {d_(M[-1][0])} 릴전)에서 나온 {NGo}골 {NA}도움(PK 골 없음), 친선경기·프랑스 대표팀(유소년 포함)·렌 U19(2003 쿠프 갬바르델라 결승)·리옹 2군(2013 CFA 1경기) 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 모든 경기), 2010-11부터는 FotMob 경기 이벤트와 대조함(FotMob에는 2010년 전 경기 자료가 없고, 2011.2.18 낭시전·2011.4.10 랑스전·2011.4.27 몽펠리에전은 FotMob 경기 자료가 비어 있음)",
    "경기·골 수는 프랑스어 위키백과 클럽·시즌별 기록(대표팀 열을 뺀 값)과 모든 시즌에서 같음. 영어 위키백과는 417경기(렌 2003-04 쿠프 드 프랑스 2004.1.25 크루아 드 사부아전 1경기가 빠짐)",
    "골: 2010-11 이후 골은 Transfermarkt와 FotMob이 수·스코어·분이 같음(FotMob 자료가 빈 2경기 제외). 분은 Transfermarkt 추가시간 표기를 씀. PK 골·자책골 없음",
    f"도움: 2014년 8월 전은 Transfermarkt 리포트 도움(FotMob 도움 기록이 이 시기에 거의 비어 있음), 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것 + 다른 출처 2곳이 확인한 것. 도움 {NA} = Transfermarkt {N_TM_A} − PK 유도 1(2012.11.4 바스티아전 90+5분 말브랑크 PK) − 'Shot on goal'(슈팅 리바운드) 2(2009.5.16 르망전 75분 플라뉘스, 2017.4.15 릴전 29분 시오 — 이 골은 FotMob이 구르퀴프 도움으로 셈) − 상대 자책골에 준 도움 2(2008.10.22 클루지전 54분 카두, 2009.9.19 불로뉴전 70분 라쇼르) − 출처가 엇갈린 도움 1",
    "출처가 엇갈려 뺀 도움: 2010.11.2 벤피카전(챔스 조별) 90+5분 로브렌 헤더 — Transfermarkt는 구르퀴프 프리킥 도움, FotMob은 라카제트, ESPN은 곤살론스 도움으로 적고 경기 기사(maxifoot)는 키커를 밝히지 않음. 구르퀴프를 확인해 주는 다른 출처가 없어 넣지 않음(라카제트 자료도 이 도움을 넣지 않음)",
    "FotMob에 없지만 다른 출처 2곳이 구르퀴프 도움으로 적어 넣은 1개: 2014.12.17 모나코전(쿠프 드 라 리그 16강) 연장 106분 라카제트 골(maxifoot 경기 기사·평점, Lyonmag 경기 기사: 구르퀴프가 수비를 버티고 내준 공을 라카제트가 마무리, 기사들은 107분으로 적음). 2014년 8월 이후 FotMob에만 있는 도움은 위 릴전 시오 골뿐(넣지 않음)",
    "2014년 8월 전 도움은 Transfermarkt 한 곳 기준이라 하나하나 다른 출처와 대조하지는 않음(프랑스어 위키백과 시즌 도움 합계는 Transfermarkt보다 8개 적은 62개, FotMob 경력 합계는 2010년 전 자료가 거의 없음)",
    "Transfermarkt 리포트 골 목록이 최종 스코어보다 짧은 경기: 2014.1.5 라 쉬즈쉬르사르트전(1-6)은 FotMob 이벤트로 41분 상대 골(1-1)을 채워 56분 도움의 골 전 스코어를 2-1로 계산함. 2006.1.7 코르트전(3-2)은 구르퀴프 골·도움이 없어 영향 없음",
    "날짜는 현지 날짜(Transfermarkt 리포트·일정 날짜). 2009.7.25 트로페 데 샹피옹(몬트리올)·2012.7.28 트로페 데 샹피옹(미국 해리슨)도 현지 날짜와 같음",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(라카제트·카카·세도르프·인자기·호나우두·뎀벨레 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 리그 모형에 넣은 값 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']})",
    "순위표+모형(추정): 몽펠리에 2005-06 리그2 12위 1521·갱강 2009-10 리그2 18위 1484(프랑스 2부 평균 1540 모형, 다른 선수 자료와 같은 식), 이죄르 2013-14 프랑스 4부(CFA) 1220(다른 선수 자료의 4부 값)",
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·코파 이탈리아는 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), 트로페 데 샹피옹은 국내컵 결승, UEFA컵 1라운드는 유로파 예선, UEFA컵 3라운드·유로파 16강은 유로파 토너먼트로 계산함",
    f"두 경기 합산(챔스 16강·8강 2009-10 올림피아코스·리옹전) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음). 연장 기록 2개(2006.4.12 몽펠리에전 110분, 2014.12.17 모나코전 106분)는 단판 연장으로 계산함",
    "시즌 구분: 보르도·리옹은 7월 10일 기준(2009.7.25·2012.7.28 트로페 데 샹피옹, 2013.7.30 챔스 예선이 새 시즌), 렌·밀란·디종은 8월 1일 기준. 클럽 구분은 2006.7.1 전 렌, 2008.7.1 전 밀란, 2010.8.24 전 보르도(2008-09 임대 포함, 2010.8.22 PSG전까지), 2015.7.1 전 리옹, 2018.7.1 전 렌, 이후 디종(FotMob 경력 날짜 기준). 렌 2015-16은 부상으로 2016.1.9 로리앙전부터 출전",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 챔피언스리그 2006-07·클럽 월드컵 2007(밀란, 준결승 2차전·결승과 클럽 월드컵은 출전하지 않았지만 Transfermarkt 표기대로 넣음), 리그1 2008-09·쿠프 드 라 리그 2008-09·트로페 데 샹피옹 2008·2009(보르도), 쿠프 드 프랑스 2011-12·트로페 데 샹피옹 2012(리옹), 올해의 선수 2009(Transfermarkt 'Footballer of the Year'). U19 유럽 선수권 우승은 대표팀 기록이라 뺌",
    "은퇴(Transfermarkt 2019.1.23 은퇴 표시, 디종과 계약 해지 뒤 복귀 없음 — 본인 2023 인터뷰·부친 발언). 마지막 경기 2018.10.20 릴전",
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
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
mmin = {m[0]: m[3] for m in M}
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if r[4] > 90 and not r[11] and not r[10] and not (len(r) > 14): problems.append(("90분 넘는데 표기 없음", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const GOU_E={J(E)};\nconst GOU_M={J(M)};\nconst GOU_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
