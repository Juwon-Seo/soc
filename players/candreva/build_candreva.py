#!/usr/bin/env python3
"""Antonio Candreva: raw/ -> candreva.json + src/data/can.js (판정 근거는 judgments.md)

  python3 players/candreva/build_candreva.py            # 파일 쓰기
  python3 players/candreva/build_candreva.py --debug    # Elo 출처·도움 판정 로그
  python3 players/candreva/build_candreva.py --cross    # 다른 선수 자료 대조(모든 src/data/*.js)
  python3 players/candreva/build_candreva.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv·fotmob_tm_map.csv·fotmob_playerMatches.csv(FotMob),
      raw/ranks.txt(순위표), /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/*.js(같은 경기 다른 선수 자료 대조).
키에사(players/chiesa/build_chiesa.py)를 바탕으로 함. 판정 표(대문자 상수)는 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections, glob
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "can.js")
OUT_JSON = os.path.join(HERE, "candreva.json")
ME = "안토니오 칸드레바"
GAP = "2014-08-01"   # 전: Transfermarkt 도움 단독 허용, 후: Transfermarkt ∩ FotMob(또는 다른 출처 2곳)

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

# ---------------------------------------------------------------- 판정 표(judgments.md 4절)
EXCL_A = {
}
ADD_CONFIRMED = {
}   # FotMob에 없지만 다른 출처 2곳 이상이 확인해 넣은 도움: "gameId|minute": "근거"

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "IT3B", "POSB"}   # 세리에B 승격 플레이오프(POSB) = 리그 비중(브루노 페르난데스·판니스텔로이·카모라네시 선례)
CUP = {"CIT"}
TIE_UEFA = {"CL", "EL", "CLQ", "ELQ"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"     # 1~4라운드·16강
    if cid == "SCI": return "df"      # 수페르코파 이탈리아나(단판 결승)
    if cid == "CLQ": return "clq"
    if cid == "ELQ": return "elq"
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
        return "elk"   # 32강('Second Round'·'intermediate stage')·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def CIT_RULE(d):
    """코파 이탈리아 두 경기 합산: 원정 다득점 2021-22까지, 연장 있음(2019-20 준결승 2차전만 연장 없이 승부차기)"""
    et = 0 if "2020-06-01" <= d <= "2020-06-30" else 1
    return int(d < "2022-07-01"), et

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
    if cid in TIE_UEFA:
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CIT":
        ag, et = CIT_RULE(d)
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
    """계산기 시즌 구분과 같게: 모든 클럽 8월 1일 기준(2020년 8월은 2019-20)"""
    y = int(d[:4])
    if d.startswith("2020-08"):
        s = 2019
    else:
        s = y if int(d[5:7]) >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

exec(open(os.path.join(HERE, "elo_candreva.py"), encoding="utf-8").read())   # MAN·MODEL (judgments.md 7절)

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

UEFA = {"CL", "EL", "CLQ", "ELQ"}
def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    if (k, d) in MAN_GAME:
        e, lv = MAN_GAME[(k, d)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man-game"))
        return e, lv
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})) + " [" + "/".join(sorted({x["opp"] for x in same})) + "]"))
        return e, lv
    seasons = [eu, d[:4]] if cid in UEFA else [eu]   # 달력 연도 리그(노르웨이 등) 상대는 경기 연도
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
    return g["date_local"]   # 이탈리아·유럽 대회: TM 리포트 날짜(현지), 리포트 없는 리그 경기는 UTC → 로마 시간

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
        if r["cand_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

# FotMob 선수 경기 목록(playerMatches: 인테르·삼프도리아·살레르니타나)의 경기별 도움 수
PM_A = {}
_PM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}
for r in rd("fotmob_tm_map.csv"):
    pm = _PM.get(r["fotmob_matchId"])
    if pm and pm["assists"] not in ("", None):
        PM_A[r["tm_gameId"]] = int(float(pm["assists"]))
used_pm = collections.Counter()
rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
A_STATUS = []   # (gid, date, minute, scorer, type, status)
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
    isg, isa = e["cand_scorer"] == "1", e["cand_assist_other"] == "1"
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
    et = int(int(e["minute"].split("+")[0]) > 90)   # 연장 전·후반(90+x 추가시간 제외)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
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
        elif e["assist_type"] in ("Penalty: Fouled player", "Shot on goal"):
            st = "제외:" + e["assist_type"]
        if st:
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], st))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], st)); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - mi) <= 2]
            if not hit and PM_A.get(gid, 0) > used_pm[gid] + len(FM_ASSIST.get(gid, [])):
                used_pm[gid] += 1
                A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "TM∩FotMob선수경기목록"))
                add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et); continue
            if not hit:
                A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "TM단독-미확인"))
                judg.append(("도움 미확인", d, opp, e["minute"], e["scorer"])); continue
            used_fm[gid] += 1
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "TM∩FotMob"))
        elif d >= GAP:
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "추가확인:" + ADD_CONFIRMED[tag]))
        else:
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "2014.8 전 TM"))
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

SELF_A = [(e["gameId"], e["date"], e["minute"]) for e in EVENTS if e["cand_self_assist"] == "1"]

# FotMob에만 있는 도움(넣지 않음) 확인: 2014.8 이후만 의미 있음
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid in G and G[gid]["date_local"] >= GAP:
        tm_a = [e for e in EVENTS if e["gameId"] == gid and e["cand_assist_other"] == "1"]
        for t in ts:
            if not any(abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - minute(e["minute"])[0]) <= 2 for e in tm_a):
                FM_ONLY.append((gid, G[gid]["date_local"], t))
PM_ONLY = []   # FotMob 선수 경기 목록 도움 > Transfermarkt 도움(제외 전) 경기
for gid, n in PM_A.items():
    if gid in G and n > int(G[gid]["assists"] or 0):
        PM_ONLY.append((gid, G[gid]["date_local"], G[gid]["opponent"], n, G[gid]["assists"]))

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--allow-missing" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "\nFotMob 전용 도움:", FM_ONLY, "\n선수 경기 목록 도움 > TM:", PM_ONLY, "\nself:", SELF_A)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)
    print(collections.Counter(s[5][:12] for s in A_STATUS))
    for s in A_STATUS:
        if s[5] not in ("TM∩FotMob", "2014.8 전 TM"): print(s)

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["cand_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV:
        FM_CMP.append(("FotMob 이벤트 파일 없음", gid, G[gid]["date_local"])); continue
    fg = [r for r in FM_EV[gid] if r["cand_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["score_home_away_after"], t["goal_desc"], t["penalty"], f["time"], f["overloadTime"], f["newScore_home_away"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
DATA = os.path.join(ROOT, "src", "data")
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(DATA, "*.js"))):
    b = os.path.basename(fn)
    if b in ("can.js", "hon.js"): continue
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const ([A-Z0-9]+)_E=(\[.*?\]);\n", s, re.S)
    if m: OTHERS[b] = json.loads(m.group(2))
MY_NAMES = ("Antonio Candreva",)
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
for fn, ent in OTHERS.items():
    for r in E:
        same = [x for x in ent if x[9] == r[9] and key(x[1]) == key(r[1])]
        if not same: continue
        # 칸드레바 도움 → 그 선수 골
        if r[0] == "a":
            hit = sorted([x for x in same if x[0] == "g" and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            if hit: CROSS.append((fn, "칸드레바 도움→골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        for x in same:
            if (x[2], x[12], x[3]) != (r[2], r[12], r[3]):
                CROSS.append((fn, "같은 경기 Elo/lv/대회 다름", r[9], r[1], (r[2], r[12], r[3]), (x[2], x[12], x[3])))
    for x in ent:
        if x[0] == "a" and x[13] in MY_NAMES:
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn, "도움→칸드레바 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
# TM 리포트상 칸드레바 골의 도움자가 다른 수록 선수인데 그 선수 파일에 도움 행이 없는 경우 / 칸드레바 도움인데 상대 파일에 골 없음
SCORER_FILES = collections.defaultdict(set)
for fn, ent in OTHERS.items():
    for x in ent:
        if x[0] == "a" and isinstance(x[13], str): pass
for e in EVENTS:
    if e["gameId"] not in G: continue
    d = ldate(G[e["gameId"]]); opp = G[e["gameId"]]["opponent"]; mi = minute(e["minute"])[0]
    if e["cand_scorer"] == "1" and e["assist_player"]:
        for fn, ent in OTHERS.items():
            gl = [x for x in ent if x[0] == "g" and x[9] == d and key(x[1]) == key(opp)]
            # 그 선수 파일에 같은 경기 골이 있으면 그 선수가 같은 팀에서 뛴 것
            if gl and not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append((fn, "참고: 같은 경기 골이 있는 선수 파일, 칸드레바 골의 도움 행 없음", d, e["minute"], e["assist_player"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[1], str(c[-1])[:4]) for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("tercv", "2007-07-01", "테르나나", "2004~2007"), ("udicv", "2008-07-07", "우디네세", "2007~2008"),
         ("livcv", "2010-01-21", "리보르노", "2008~2010"), ("juvcv", "2010-08-30", "유벤투스", "2010"),
         ("parcv", "2011-07-21", "파르마", "2010~2011"), ("cescv", "2012-01-31", "체세나", "2011~2012"),
         ("lazcv", "2016-08-03", "라치오", "2012~2016"), ("intcv", "2020-09-25", "인테르", "2016~2020"),
         ("sampcv", "2022-08-12", "삼프도리아", "2020~2022"), ("salcv", None, "살레르니타나", "2022~2024")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
TMC = {"1103": ["tercv"], "410": ["udicv"], "1210": ["livcv"], "506": ["juvcv"], "130": ["parcv"], "1429": ["cescv"],
       "398": ["lazcv"], "46": ["intcv"], "1038": ["sampcv"], "380": ["salcv"]}
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
CNT_A = collections.Counter(s[5].split(":")[0] if s[5].startswith("제외") else s[5] for s in A_STATUS)
exec(open(os.path.join(HERE, "note_candreva.py"), encoding="utf-8").read())
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
    if r[10] and not r[7] and len(r) < 15: problems.append(("연장인데 단판 아님", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const CAN_E={J(E)};\nconst CAN_M={J(M)};\nconst CAN_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "self_assist_events": SELF_A, "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY,
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for i, v in ST.items(): print(" ", CLUBS[i][0], CLUBS[i][3], v)
