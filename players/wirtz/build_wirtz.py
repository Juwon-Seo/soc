#!/usr/bin/env python3
"""Florian Wirtz: raw/ -> wirtz.json + src/data/wir.js (판정 근거는 judgments.md)

  python3 players/wirtz/build_wirtz.py            # 파일 쓰기
  python3 players/wirtz/build_wirtz.py --debug    # Elo 출처 로그
  python3 players/wirtz/build_wirtz.py --cross    # 동료 자료 대조
  python3 players/wirtz/build_wirtz.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/*.js(같은 경기 동료 자료 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections, glob
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "wir.js")
OUT_JSON = os.path.join(HERE, "wirtz.json")
ME = "플로리안 비르츠"
GAP = "2000-01-01"   # 도움 출처 기준일: 이전은 Transfermarkt 단독 허용, 이후는 Transfermarkt ∩ FotMob(또는 다른 출처 2곳)

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
# 도움 제외 사유(유형으로 자동 분류되는 것 외의 판정). gameId|분 -> 이유
EXCL_A = {
    "4096244|90+6": "확인 못 함(2024.4.27 슈투트가르트전 90+6분 안드리히 골 — Transfermarkt만 비르츠 프리킥 도움으로 적고 FotMob 이벤트·선수 경기 목록에는 도움 없음. 로이터 기사 요약은 '비르츠가 감아 올린 공의 리바운드를 안드리히가 넣음', bundesliga.com 계열 요약은 '프리킥이 걷어내지지 않고 안드리히 발 앞으로 튀어 나옴' → 깨끗한 도움으로 확인하는 출처 2곳이 없고 리바운드 서술이라 뺌)",
}
ADD_CONFIRMED = {}   # FotMob에 없지만 다른 출처 2곳이 확인해 넣은 도움: 없음

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "GB1"}
CUP = {"DFB", "FAC", "CGB"}
TIE_COMPS = {"CL", "EL"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("DFL", "GBCS"): return "df"   # DFL-슈퍼컵·커뮤니티 실드 = 국내컵 결승
    if cid == "KLUB": return "cwc"
    if cid == "CLQ": return "clq"
    if cid == "ELQ": return "elq"
    if cid == "ECLQ": return "ecq"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2024-25부터 리그 페이즈('Group Stage') 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 32강(intermediate stage)·16강·8강
    if cid == "UCOL":
        if r.startswith("group"): return "ecg"
        if r.startswith("semi"): return "ecsf"
        return "eck"
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
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        o = INFO[TIES_RAW[gid]["other_leg_id"]]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    if cid in TIE_COMPS:
        ag, et = int(d < "2021-07-01"), 1
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
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

exec(open(os.path.join(HERE, "elo_tables.py"), encoding="utf-8").read())   # MAN·MODEL_RULES (judgments.md 7절)

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
    y0 = int(eu[:4])
    seasons = [eu, str(y0), str(y0 + 1)] if cid in ("CL", "EL") else [eu]
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
    return g["date_local"]   # Transfermarkt 리포트 날짜(유럽 현지, 클럽 월드컵 2013 모로코도 현지와 같음)

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
        if r["wirtz_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
A_STATUS = []   # (gid, date, minute, scorer, type, status)
def et_of(g, raw, mi, tie):
    """단판 경기의 연장 시간 기록(91분 이후, '90+x' 추가시간 표기 제외)만 1. 합산 경기는 tie 배열의 연장 규칙으로 계산"""
    in_et = mi > 90 and ("+" not in raw or raw.startswith("120+") or raw.startswith("105+"))
    return int(tie is None and g["gameState"] in ("extra_time", "penalty_shootout") and in_et)
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
    isg, isa = e["wirtz_scorer"] == "1", e["wirtz_assist_other"] == "1"
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
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"].strip().lower() != "penalty rebound"), 0, tie, comp, ko, d, opp, cid, et_of(g, e["minute"], mi, tie))
    if isa:
        st = None
        if tag in EXCL_A:
            st = "제외:" + EXCL_A[tag]
        elif e["own_goal"] == "1" or not ours:
            st = "제외:상대 자책골"
        elif e["assist_type"] in ("Penalty: Fouled player", "Shot on goal"):
            st = "제외:" + e["assist_type"]
        if st:
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], st))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], st)); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - mi) <= 2]
            if not hit:
                A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "TM단독-미확인"))
                judg.append(("도움 미확인", d, opp, e["minute"], e["scorer"])); continue
            used_fm[gid] += 1
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "TM∩FotMob"))
        else:
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "추가확인" if tag in ADD_CONFIRMED else "기준일 이전 TM"))
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et_of(g, e["minute"], mi, tie))

# FotMob에만 있는 도움(넣지 않음) 확인
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
        if s[5] not in ("TM∩FotMob", "기준일 이전 TM"): print(s)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["wirtz_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV:
        FM_CMP.append(("FotMob 이벤트 파일 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["wirtz_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["score_home_away_after"], t["goal_desc"], f["time"], f["overloadTime"], f["newScore_home_away"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)
    # FotMob 도움 중 TM과 안 맞는 것
    for gid, evs in FM_EV.items():
        if gid not in G: continue
        tma = [(minute(e["minute"])[0]) for e in EVENTS if e["gameId"] == gid and e["wirtz_assist_other"] == "1"]
        for r in evs:
            if r["wirtz_assist"] == "1" and not any(abs(t - int(r["time"])) <= 2 for t in tma):
                print("FotMob만 도움", gid, G[gid]["date_local"], r["time"], r["scorer"], r["newScore_home_away"], tma)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
DATA = os.path.join(ROOT, "src", "data")
def load_js(fn, P):
    s = open(os.path.join(DATA, fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Mohamed Salah": ("sal.js", "SAL"), "Bradley Barcola": ("bcl.js", "BCL")}
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items() if os.path.exists(os.path.join(DATA, v[0]))}
GOT_NAMES = ("Florian Wirtz",)
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
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and key(x[1]) == key(r[1]) and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("비르츠 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and x[13] in GOT_NAMES:
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→비르츠 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    # TM이 동료 도움으로 적은 비르츠 골이 동료 파일에 없는 경우
    for e in EVENTS:
        if e["wirtz_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움→비르츠 골인데 동료 파일에 도움 없음", nm, d, e["minute"], e["assist_type"]))
    # 비르츠 도움에서 뺀 TM 도움 중 동료 골 행
    for s in A_STATUS:
        if s[3] == nm and s[5].startswith("제외") or (s[3] == nm and s[5] == "TM단독-미확인"):
            hit = [x for x in ent if x[0] == "g" and x[9] == s[1] and abs(x[4] - minute(s[2])[0]) <= 2]
            CROSS.append(("비르츠 도움에서 뺀 TM 도움(참고)", nm, s[1], s[2], s[5][:20], "동료 골 행 있음" if hit else "동료 골 행 없음"))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], str(c[-1])[:12]) for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("levwz", "2025-07-01", "바이어 04 레버쿠젠", "2020~2025"), ("livwz", None, "리버풀", "2025~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
TMC = {"15": ["levwz"], "31": ["livwz"]}
CLUB_KO = collections.OrderedDict()
for k, u, n, y in CLUBS: CLUB_KO.setdefault(k, n)
ST = collections.OrderedDict()
for i, (k, *_ ) in enumerate(CLUBS): ST[i] = [0, 0, 0, 0]
def stage(d):
    for i, (k, u, _, _) in enumerate(CLUBS):
        if u is None or d < u: return i
for m in M: ST[stage(m[0])][0] += 1; ST[stage(m[0])][3] += m[3]
for r in E: ST[stage(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) not in TMC[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
exec(open(os.path.join(HERE, "note_wirtz.py"), encoding="utf-8").read())
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "lv"]:
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const WIR_E={J(E)};\nconst WIR_M={J(M)};\nconst WIR_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for i, v in ST.items(): print(" ", CLUBS[i][0], CLUBS[i][3], v)
