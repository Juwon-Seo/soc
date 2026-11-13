#!/usr/bin/env python3
"""Shinji Kagawa: raw/ -> kagawa.json + src/data/kag.js (판정 근거는 judgments.md)

  python3 players/kagawa/build_kagawa.py            # 파일 쓰기
  python3 players/kagawa/build_kagawa.py --debug    # Elo 출처·도움 판정
  python3 players/kagawa/build_kagawa.py --cross    # 동료 자료 대조
  python3 players/kagawa/build_kagawa.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv, raw/ranks.txt(순위표),
      elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(동료 자료 대조).
괴체(players/gotze/build_gotze.py) 빌드를 바탕으로 함. 판정 표는 judgments.md에 출처와 함께 적혀 있다.
OUT_ROOT 환경 변수가 있으면 그 저장소 복사본의 src/data에 쓴다(검증용).
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(os.environ.get("OUT_ROOT", ROOT), "src", "data", "kag.js")
OUT_JSON = os.path.join(HERE, "kagawa.json")
ME = "가가와 신지"
GAP = "2014-08-01"   # 도움: 이전은 Transfermarkt 단독 허용, 이후는 Transfermarkt ∩ FotMob(또는 다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")          # 성인 클럽 공식 경기(도르트문트 II 경기는 이 파일에 없음)
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표 (judgments.md 4절)
EXCL_A = {}      # gameId|분 -> 이유 (유형으로 자동 분류되지 않는 제외)
ADD_CONFIRMED = {}   # 2014.8.1 이후 FotMob에 없지만 다른 출처 2곳이 확인한 도움
FM_SOG_OK = {}   # TM 'Shot on goal'이지만 FotMob이 도움으로 세고 경기 기사가 패스를 확인한 것
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "GB1", "ES2", "TR1", "GR1", "BE1", "JAP1", "JAP2", "J1YV", "ES1P"}
CUP = {"DFB", "FAC", "CGB", "CDR", "GRP", "JEMP", "JAPC"}
JCOMP = {"JAP1", "JAP2", "J1YV", "JAPC", "JEMP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"     # 승격 플레이오프(ES1P)·J1 백년구상 리그 플레이오프 라운드도 리그 비중
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or (cid == "FAC" and r.startswith("sixth")): return "dk"
        return "dc"
    if cid in ("DFL", "GBCS"): return "df"
    if cid == "ELQ": return "elq"
    if cid == "ECLQ": return "ecq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower() or (g["competitionId"] == "J1YV" and g["round"] == "Platzierungsrunde")

def ko_of(g):
    cid, r = g["competitionId"], g["round"].lower()
    if is_leg(g): return 0
    if cid == "J1YV": return 1        # 무승부 없이 승부차기(90분 승 3·승부차기 승 2·승부차기 패 1) → 무승부 기대 승점 1.5
    if cid in LEAGUE: return 0
    if r.startswith("group"): return 0
    return 1

J1YV_LEG = {"4889570": 1, "4889580": 2}   # 플레이오프 라운드(동·서 2위끼리 홈·원정, 연장은 2차전 뒤)

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = g["date_local"]
    home = int(inf["home_id"] == g["club_id"])
    if cid == "J1YV":
        leg = J1YV_LEG[gid]
        fu = ft = 0
        if leg == 2: fu, ft = 2, 2     # 1차전 2:2(2026.5.30 홈)
        return [leg, home, fu, ft, 0, 1]
    leg = 1 if "1st" in g["round"].lower() else 2
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "EL", "ELQ", "ECLQ"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CGB":
        ag, et = 1, 1                  # 잉글랜드 리그컵 준결승 2017-18까지 원정 다득점·연장
    elif cid == "GRP":
        ag, et = 1, 1                  # 그리스컵 2020-21 두 경기 합산(원정 다득점·연장)
    elif cid == "JAPC":
        ag, et = 0, 1                  # 2025 J리그컵 플레이오프 라운드: 합산 4-4에서 원정골 없이 연장(요코하마 FC 2025.6.8)
    elif cid == "ES1P":
        ag, et = 0, 1
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
MANUAL_ALIAS = {"fagiano okayama fc": "fagiano okayama", "yokohama f marinos": "yokohama f marinos",
                "tokyo verdy 1969": "tokyo verdy", "kyoto sanga fc": "kyoto sanga", "consadole sapporo": "hokkaido consadole sapporo",
                "thespa kusatsu": "thespakusatsu gunma", "thespa gunma": "thespakusatsu gunma"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    k = ALIAS.get(k, k)
    return k.replace("yokohama f marinos", "yokohama f marinos")

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

def season_j(d):
    """J리그: 2026년 6월까지 달력 연도, 2026년 7월부터 2026-27(8월 개막 추춘제)"""
    if d >= "2026-07-01": return season_eu(d)
    return d[:4]

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

exec(open(os.path.join(HERE, "elo_tables.py"), encoding="utf-8").read())   # MAN·model·RANK_LG (judgments.md 7절)

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def opp_elo(opp, d, cid):
    k = key(opp)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    if cid in JCOMP:
        seasons = [season_j(d)]
    else:
        eu = season_eu(d); y0 = int(eu[:4])
        seasons = [eu, str(y0), str(y0 + 1)] if cid in ("CL", "EL", "ELQ", "ECLQ") else [eu]
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
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
MIN_FIX = {}     # 출전 분 수정(없음: Transfermarkt 그대로, judgments.md 2절)
M = []
for g in GAMES:
    M.append([g["date_local"], g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["kagawa_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
A_STATUS = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, d, cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa = e["kagawa_scorer"] == "1", e["kagawa_assist_other"] == "1"
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
    d = g["date_local"]; opp = g["opponent"].strip()
    et = 0
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        st = None
        if tag in EXCL_A:
            st = "제외:" + EXCL_A[tag]
        elif e["own_goal"] == "1" or not ours:
            st = "제외:상대 자책골"
        elif e["assist_type"] == "Penalty: Fouled player":
            st = "제외:" + e["assist_type"]
        elif e["assist_type"] == "Shot on goal" and tag not in FM_SOG_OK:
            st = "제외:" + e["assist_type"]
        if st:
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], st))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], st)); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 5 or abs(t - mi) <= 5]
            if not hit:
                A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "TM단독-미확인"))
                judg.append(("도움 미확인", d, opp, e["minute"], e["scorer"])); continue
            used_fm[gid] += 1
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "TM∩FotMob" + (" (Shot on goal, 기사 확인)" if tag in FM_SOG_OK else "")))
        else:
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "추가확인" if tag in ADD_CONFIRMED else "2014.8 이전 TM"))
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if len(ts) > used_fm.get(gid, 0) and G.get(gid, {}).get("date_local", "0") >= GAP:
        FM_ONLY.append((gid, G[gid]["date_local"] if gid in G else "?", ts))

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--allow-missing" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)
    print(collections.Counter(s[5] for s in A_STATUS))
    for s in A_STATUS:
        if s[5] not in ("TM∩FotMob", "2014.8 이전 TM"): print(s)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["kagawa_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV:
        FM_CMP.append(("FotMob 이벤트 파일 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["kagawa_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["score_home_away_after"], t["penalty"], f["time"], f["overloadTime"], f["newScore_home_away"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)
    for gid, evs in FM_EV.items():
        if gid not in G: continue
        tma = [(minute(e["minute"])[0]) for e in EVENTS if e["gameId"] == gid and e["kagawa_assist_other"] == "1"]
        for r in evs:
            if r["kagawa_assist"] == "1" and not any(abs(t - int(r["time"])) <= 5 for t in tma):
                print("FotMob만 도움", gid, G[gid]["date_local"], r["time"], r["scorer"], r["newScore_home_away"], tma)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
DATA = os.path.join(ROOT, "src", "data")
def load_js(fn, P):
    s = open(os.path.join(DATA, fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Robert Lewandowski": ("lew.js", "LEW"), "Marco Reus": ("reu.js", "REU"), "Pierre-Emerick Aubameyang": ("aub.js", "AUB"),
         "Mario Götze": ("got.js", "GOT"), "Jadon Sancho": ("sch.js", "SCH"), "Wayne Rooney": ("roo.js", "ROO"),
         "Robin van Persie": ("van.js", "VAN"), "Ousmane Dembélé": ("dem.js", "DEM")}
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items() if os.path.exists(os.path.join(DATA, v[0]))}
KAG_NAMES = ("Shinji Kagawa", "Kagawa")
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
for nm, ent in MATE_E.items():
    for r in E:
        if r[0] == "a" and r[13] == nm:
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 6], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("가가와 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and x[13] in KAG_NAMES:
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→가가와 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for e in EVENTS:
        if e["kagawa_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = G[e["gameId"]]["date_local"]; mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움→가가와 골인데 동료 파일에 도움 없음", nm, d, e["minute"], e["assist_type"]))
    for s in A_STATUS:
        if s[3] == nm and (s[5].startswith("제외") or s[5] == "TM단독-미확인"):
            hit = [x for x in ent if x[0] == "g" and x[9] == s[1] and abs(x[4] - minute(s[2])[0]) <= 2]
            CROSS.append(("가가와 도움에서 뺀 TM 도움(참고)", nm, s[1], s[2], s[5][:20], "동료 골 행 있음" if hit else "동료 골 행 없음"))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], str(c[-1])[:12]) for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("cerkg", "2010-07-01", "세레소 오사카", "2006~2010"), ("bvbkg", "2012-07-01", "보루시아 도르트문트", "2010~2012"),
         ("munkg", "2014-08-31", "맨체스터 유나이티드", "2012~2014"), ("bvbkg", "2019-01-31", "보루시아 도르트문트", "2014~2019"),
         ("bjkkg", "2019-07-01", "베식타시", "2019"), ("zarkg", "2021-01-27", "레알 사라고사", "2019~2020"),
         ("paokg", "2022-01-10", "PAOK", "2021"), ("stvkg", "2023-02-01", "신트트라위던", "2022"),
         ("cerkg", None, "세레소 오사카", "2023~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
TMC = {"1022": ["cerkg"], "16": ["bvbkg"], "985": ["munkg"], "114": ["bjkkg"], "142": ["zarkg"], "1091": ["paokg"], "475": ["stvkg"]}
ST = collections.OrderedDict()
for i in range(len(CLUBS)): ST[i] = [0, 0, 0, 0]
def stage(d):
    for i, (k, u, _, _) in enumerate(CLUBS):
        if u is None or d < u: return i
for m in M: ST[stage(m[0])][0] += 1; ST[stage(m[0])][3] += m[3]
for r in E: ST[stage(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(g["date_local"]) not in TMC[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
exec(open(os.path.join(HERE, "note_kagawa.py"), encoding="utf-8").read())
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "lv", "cerkg", "bvbkg"]:
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
if __name__ == "__main__" and len([a for a in sys.argv[1:] if a != "--allow-missing"]) == 0:
    open(OUT_JS, "w", encoding="utf-8").write(f"const KAG_E={J(E)};\nconst KAG_M={J(M)};\nconst KAG_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for i, v in ST.items(): print(" ", CLUBS[i][0], CLUBS[i][3], v)
