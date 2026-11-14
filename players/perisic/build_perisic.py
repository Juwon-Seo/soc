#!/usr/bin/env python3
"""Ivan Perišić: raw/ -> perisic.json + src/data/per.js (판정 근거는 judgments.md)

  python3 players/perisic/build_perisic.py            # 파일 쓰기
  python3 players/perisic/build_perisic.py --debug    # Elo 출처 로그·도움 제외 목록
  python3 players/perisic/build_perisic.py --cross    # 같은 경기 다른 선수 자료 대조
  python3 players/perisic/build_perisic.py --fm       # FotMob 골 대조
  python3 players/perisic/build_perisic.py --root=<복사본>   # 스크래치 복사본의 src/data에 쓰기

에릭센(build_eriksen.py) 빌드를 바탕으로 함. 입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트), raw/ranks.txt(순위표),
/home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/*.js(같은 경기 대조).
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections, glob
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1 and sys.argv[1].startswith("--root="):   # 스크래치 복사본에 쓰기(검증용)
    ROOT = sys.argv.pop(1).split("=", 1)[1]
ELO = os.path.join(os.path.dirname(os.path.dirname(HERE)), "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "per.js")
OUT_JSON = os.path.join(HERE, "perisic.json")
ME = "이반 페리시치"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트, 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
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
# 출전 분 고침: gameId -> (분, 근거)  (없음: Transfermarkt 출전 분 그대로)
MIN_FIX = {}
# Transfermarkt 리포트의 골 순서·스코어 표기 오류(FotMob 순서로 고침): gameId|분 -> 고친 '골 뒤 스코어(홈-원정)'
SCORE_FIX = {
    # 2022.5.1 우디네세-인테르 1:2: TM은 72분 우디네세 골을 0:2로 적음. FotMob 0-1(12 페리시치)·0-2(39 라우타로)·1-2(72)
    "3614887|72": "1-2",
    # 2026.3.22 텔스타르-PSV 3:1: TM은 45+3분 텔스타르 골 1:1, 47분 실디야 골 0:1로 적음. FotMob 45+3 1-0(브라우어)·47 1-1(실디야, 페리시치 코너킥)
    "4641591|45+3": "1-0",
    "4641591|47": "1-1",
}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음, 일반 규칙 밖): gameId|분 -> 이유
EXCL_A = {}
# 2014.8.1 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳 이상이 확인해 넣은 도움: gameId|분 -> 근거
ADD_CONFIRMED = {}
# 2014.8.1 이후 Transfermarkt에만 있고 다른 출처 2곳을 찾지 못해 넣지 않은 도움: gameId|분 -> 근거
UNCONF_A = {}
ADD_FM_ONLY = {}
exec(open(os.path.join(HERE, "assist_checks.py"), encoding="utf-8").read())

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BE1", "EJPL", "EBEL", "L1", "IT1", "GB1", "KR1", "NL1"}
CUP = {"CCB", "DFB", "CIT", "CGB", "FAC", "KRC", "NLP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"   # 벨기에 챔피언 플레이오프(EJPL)·강등 테스트매치(EBEL) = 리그(데 브라위너 선례)
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("DFL", "SCI", "NLSC"): return "df"   # 슈퍼컵 = 국내컵 결승
    if cid == "ELQ": return "elq"
    if cid == "ECLQ": return "ecq"
    if cid == "CL":
        if r.startswith("group"): return "clg"      # 2024-25부터 리그 단계('Group Stage') 포함
        if r.startswith("last 16") or r.startswith("intermediate"): return "cl16"   # 녹아웃 플레이오프 = 16강
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 2라운드(32강)·intermediate stage·16강·8강
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
        oh, oa = map(int, o["final"].split(":")[:2])
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "ELQ", "EL", "ECLQ"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CIT":   # 코파 이탈리아: 원정 다득점 2021-22까지·연장, 2019-20 준결승 2차전(2020.6)만 연장 없이 승부차기
        ag, et = int(d < "2022-07-01"), int(not ("2020-02-01" <= d < "2020-07-01"))
    elif cid == "CCB":   # 벨기에컵 8강 두 경기(2008-09·2009-10): 원정 다득점(2009 세르클러 브뤼허가 원정 다득점으로 진출)·연장
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
MANUAL_ALIAS = {"inter milan": "inter", "royal antwerp fc": "royal antwerp"}
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
    if d[:7] in ("2020-07", "2020-08"): s = 2019   # 코로나로 늦게 끝난 2019-20 시즌
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

exec(open(os.path.join(HERE, "elo_tables.py"), encoding="utf-8").read())

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
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]",
                        sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in ("CL", "ELQ", "EL", "ECLQ") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    res = rank_model(k, eu)
    if res:
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model", []))
        return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local"]   # Transfermarkt 리포트 날짜(모두 유럽 현지)

M = []
for g in GAMES:
    mins = MIN_FIX[g["gameId"]][0] if g["gameId"] in MIN_FIX else int(g["playedMinutes"])
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), mins])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["perisic_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
EXCL_CNT = collections.Counter()
EXCL_LIST = collections.defaultdict(list)
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, 0, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

PEN_REBOUND = []
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["perisic_scorer"] == "1", e["perisic_assist_other"] == "1"
    if e["perisic_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", tag)); EXCL_CNT["본인 도움"] += 1
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, SCORE_FIX.get(tag, e["score_home_away_after"]).split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        pk = int(e["penalty"] == "1" and "rebound" not in e["goal_desc"].lower())
        if e["penalty"] == "1" and not pk: PEN_REBOUND.append((d, opp, e["minute"]))
        add_row("g", mi, dm, gf, ga, pk, 0, tie, comp, ko, d, opp, cid)
    if isa:
        why = None
        if not ours and e["assist_type"].startswith("Handball"): why = "상대 PK(페리시치 핸드볼 반칙)"
        elif e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        elif tag in UNCONF_A: why = "확인 못 함: " + UNCONF_A[tag]
        if why:
            k = why if tag not in EXCL_A and tag not in UNCONF_A else ("개별 판정" if tag in EXCL_A else "출처 부족")
            EXCL_CNT[k] += 1; EXCL_LIST[k].append((d, opp, e["minute"], e["scorer"]))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 3 or abs(t - mi) <= 3]
            if not hit:
                print("2014.8 이후 FotMob에 없는 도움 판정 누락", tag, d, opp, e["scorer"], e["assist_type"])
                if "--debug" not in sys.argv: sys.exit(1)
            used_fm[gid] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid)

# FotMob에만 있는 도움 중 다른 출처 2곳이 확인한 것(Transfermarkt 리포트에 없음)
for gid, (fmin, scorer, why) in ADD_FM_ONLY.items():
    g = G[gid]; inf = INFO[gid]; our_home = inf["home_id"] == g["club_id"]
    ev = [r for r in FM_EV[gid] if r["perisic_assist"] == "1" and int(r["time"]) == fmin]
    if len(ev) != 1: sys.exit("FotMob 도움 찾기 실패 " + gid)
    h, a = map(int, ev[0]["newScore_home_away"].split("-"))
    if ev[0]["isHome"] == "True": h -= 1
    else: a -= 1
    if (ev[0]["isHome"] == "True") != our_home: sys.exit("FotMob 도움 팀 이상 " + gid)
    gf, ga = (h, a) if our_home else (a, h)
    add_row("a", fmin, 0, gf, ga, 0, scorer, tie_of(g), comp_of(g["competitionId"], g["round"]), ko_of(g), ldate(g), g["opponent"].strip(), g["competitionId"])
    used_fm[gid] += 1
    judg.append(("FotMob 단독 도움 넣음", ldate(g), fmin, scorer, why))

FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local"] >= GAP and len(ts) > used_fm.get(gid, 0) + sum(1 for k in ADD_CONFIRMED if k.startswith(gid + "|")) + sum(1 for k in UNCONF_A if k.startswith(gid + "|")):
        FM_ONLY.append((gid, G[gid]["date_local"], ts))

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4], 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "FotMob 전용 도움:", FM_ONLY, EXCL_CNT, "PK 리바운드:", PEN_REBOUND)
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
    if e["perisic_scorer"] == "1" and e["gameId"] in G and G[e["gameId"]]["date_local"] >= "2010-08-01":
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if not FM_EV.get(gid):
        FM_CMP.append(("FotMob 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["perisic_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1" and "rebound" not in t["goal_desc"].lower()
        fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
for gid, evs in FM_EV.items():
    n_fm = sum(1 for r in evs if r["perisic_scorer"] == "1" and r["pen_shootout_event"] != "True")
    if n_fm and gid not in TMG: FM_CMP.append(("FotMob만 골", gid, G[gid]["date_local"] if gid in G else "?"))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
def load_all():
    out = {}
    for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
        b = os.path.basename(fn)
        if b in ("per.js", "hon.js"): continue
        s = open(fn, encoding="utf-8").read()
        m = re.search(r"const ([A-Z0-9]+)_E=(\[.*?\]);\n", s, re.S)
        if m: out[b] = json.loads(m.group(2))
    return out
CROSS = []
def cmp_rows(a, b, full=True):
    diffs = []
    if full and abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if full and (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if full and a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or (ta is None) != (tb is None) or (ta and tb and (ta[0], ta[4], ta[5]) != (tb[0], tb[4], tb[5])):
        diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    elif ta and tb and full and ta != tb:
        diffs.append(f"합산 {ta}/{tb}")
    return diffs
PR = lambda s: norm(s or "") in ("ivan perisic", "perisic")
if "--cross" in sys.argv or (__name__ == "__main__" and len(sys.argv) == 1):
    ALL = load_all()
    for fn, ent in ALL.items():
        for r in E:
            same = [x for x in ent if x[9] == r[9] and (key(x[1]) == key(r[1]) or _sub(key(x[1]), key(r[1])))]
            if not same: continue
            x0 = same[0]
            d = cmp_rows(r, x0, full=False)
            if d: CROSS.append(("같은 경기 다름", fn, r[9], r[1], d))
            if r[0] == "a":
                hit = [x for x in same if x[0] == "g" and norm(x[13] if False else r[13]) and abs(x[4] - r[4]) <= 3 and (x[5], x[6]) == (r[5], r[6])]
                if hit: CROSS.append(("페리시치 도움→" + fn + " 골", r[9], r[4], cmp_rows(r, hit[0]) or "같음"))
            if r[0] == "g":
                hit = [x for x in same if x[0] == "a" and PR(x[13]) and abs(x[4] - r[4]) <= 3]
                if hit: CROSS.append((fn + " 도움→페리시치 골", r[9], r[4], cmp_rows(r, hit[0]) or "같음"))
        for x in ent:
            if x[0] == "a" and PR(x[13]):
                if not any(r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3 for r in E):
                    CROSS.append(("다른 파일에 페리시치 골 도움이 있는데 페리시치 골 없음", fn, x[9], x[4]))
        # 페리시치 도움(TM)인데 동료 파일에 그 골이 있는지: 동료 골 행의 날짜·분으로 찾음
        for x in ent:
            if x[0] != "g": continue
            tm = [e for e in EVENTS if e["perisic_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9]
                  and abs(minute(e["minute"])[0] - x[4]) <= 2 and (key(G[e["gameId"]]["opponent"]) == key(x[1]) or _sub(key(G[e["gameId"]]["opponent"]), key(x[1])))]
            if tm:
                mine = any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E)
                CROSS.append(("TM 페리시치 도움 → " + fn + " 골", x[9], x[4], tm[0]["scorer"], "넣음" if mine else "뺌(" + tm[0]["assist_type"] + ")"))
    if "--cross" in sys.argv:
        for c in CROSS: print(c)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("roeip", "2009-07-01", "KSV 루셀라러", "2009"), ("brgip", "2011-07-01", "클뤼프 브뤼허", "2009~2011"),
         ("bvbip", "2013-01-06", "보루시아 도르트문트", "2011~2013"), ("wobip", "2015-08-30", "VfL 볼프스부르크", "2013~2015"),
         ("intip", "2019-08-13", "인테르", "2015~2022"), ("bayip", "2020-09-01", "바이에른 뮌헨", "2019~2020"),
         ("intip", "2022-07-01", "인테르", "2015~2022"), ("totip", "2024-01-19", "토트넘 홋스퍼", "2022~2024"),
         ("hajip", "2024-09-18", "하이두크 스플리트", "2024"), ("psvip", None, "PSV 에인트호번", "2024~2026")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
TM_CLUB = {"2977": "roeip", "2282": "brgip", "16": "bvbip", "82": "wobip", "46": "intip", "27": "bayip", "148": "totip", "447": "hajip", "383": "psvip"}
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_perisic import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["perisic_assist_other"] == "1")
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
    open(OUT_JS, "w", encoding="utf-8").write(f"const PER_E={J(E)};\nconst PER_M={J(M)};\nconst PER_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
