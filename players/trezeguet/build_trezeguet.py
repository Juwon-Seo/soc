#!/usr/bin/env python3
"""David Trezeguet: raw/ -> trezeguet.json + src/data/trz.js (판정 근거는 judgments.md)

  python3 players/trezeguet/build_trezeguet.py            # 파일 쓰기
  python3 players/trezeguet/build_trezeguet.py --debug    # Elo 출처 목록
  python3 players/trezeguet/build_trezeguet.py --fm       # FotMob 골 대조
  python3 players/trezeguet/build_trezeguet.py --cross    # 동료 자료 대조
  TRZ_ROOT=<복사본> 이면 그 복사본의 src/data·elo 를 씀(출력도 그쪽 src/data).

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), 동료 선수 src/data/*.js.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("TRZ_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "trz.js")
OUT_JSON = os.path.join(HERE, "trezeguet.json")
ME = "다비드 트레제게"
GAP = "2014-08-01"

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
GOAL_MIN_FIX = {}
EXCL_G = {}
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    "1009850|21": "슈팅 리바운드(Shot on goal, 크리스타발)",
    "916|21": "슈팅 리바운드(Shot on goal, 디 바이오)",
    "27564|53": "슈팅 리바운드(Shot on goal, 이브라히모비치)",
    "49371|10": "슈팅 리바운드(Shot on goal, 네드베드)",
    "49371|68": "상대 자책골(비냐티, 유형 Shot on goal)",
    "83954|50": "슈팅 리바운드(Shot on goal, 살리하미지치)",
    "84071|32": "슈팅 리바운드(Shot on goal, 살리하미지치)",
    "1022539|64": "상대 자책골(코차, 유형 Pass)",
}
ADD_CONFIRMED = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "IT1", "IT2", "ES1", "UAE1", "ARG1", "ARGC", "ARG2", "IND1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("FRC", "FRL", "CIT", "ARCA"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SCI", "FRCH"): return "df"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    if cid == "CLI":
        if r.startswith("group"): return "lib"
    sys.exit("모르는 대회 " + cid + " " + rnd)

LEG_FIX = {"936107": 1}   # 2009.3.3 코파 이탈리아 준결승 1차전 라치오(TM 라운드 이름에 'leg' 없음)

def leg_of(g):
    if g["gameId"] in LEG_FIX: return LEG_FIX[g["gameId"]]
    r = g["round_report"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round_report"].lower().startswith("group"): return 0
    return 1

def tie_of(g):
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
    return [leg, home, fu, ft, 1, 1]   # UEFA 대회·코파 이탈리아: 원정 다득점·연장 있음

# ---------------------------------------------------------------- 이름·Elo
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
MANUAL_ALIAS = {"inter milan": "inter", "ac parma": "parma calcio 1913", "parma ac": "parma calcio 1913",
                "club nacional": "cd nacional"}
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
        sid = int(p[1].split("=")[1].split(" ")[0])
        RANKS[(p[0], sid)][key(p[4])] = (int(p[2]), int(p[3]))

# 세리에A 20팀 표준 곡선(델 피에로 판정과 같음)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

def existing_ranks(prefix, season):
    """기존 자료(통합표 lv)의 '<prefix> <season> N위' 값"""
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위(?!/)")
    for vals in TABLE.values():
        for e, lv in vals:
            m = pat.match(lv or "")
            if m: c[int(m.group(1))][e] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}

def interp(m, r):
    """같은 리그·시즌 기존 순위값 사이 직선 보간(앞뒤 순위 값의 가운데). 범위 밖이면 None"""
    if r in m: return m[r]
    lo = [k for k in m if k < r]; hi = [k for k in m if k > r]
    if not lo or not hi: return None
    a, b = max(lo), min(hi)
    return int(m[a] + (m[b] - m[a]) * (r - a) / (b - a) + 0.5)

def ranked(prefix, season, r, n, mean, sd, tag=""):
    m = existing_ranks(prefix, season)
    v = interp(m, r)
    if v is None: v = int(round(mean + sd * curve(r, n)))
    return v, f"{prefix} {season} {r}위{tag}"

# Transfermarkt 순위표 동률 순서 고침(위키백과 2014 Indian Super League 리그 표: 아틀레티코 데 콜카타 3위·케랄라 4위, 승점 19 동률·골득실)
RANK_FIX = {("IND1", 2013, key("Kerala Blasters FC")): (4, 8)}

ARG_HALF = {("ARG1", 2012): "이니시알 2012", ("ARGC", 2012): "피날 2013", ("ARG1", 2013): "이니시알 2013", ("ARGC", 2013): "피날 2014"}

def model(lg, sid, r, n):
    s = f"{sid}-{str(sid + 1)[2:]}"
    if lg == "FR1": return ranked("리그1", s, r, n, 1714, 95.6)
    if lg == "FR2": return ranked("리그2", s, r, n, 1530, 51.24)
    if lg == "ARG2":   # 디발라 자료와 같은 2부 모형(평균 약 1355, 2부 흩어짐)
        v, lv = ranked("아르헨티나 2부", s, r, n, 1355, 51.24)
        return v, lv + " (추정)"
    if lg in ("ARG1", "ARGC"):
        half = ARG_HALF[(lg, sid)]
        return ranked("아르헨티나 1부 " + half.split()[0], half.split()[1], r, n, 1583, 63)
    if lg == "IND1":   # 델 피에로 자료와 같은 추정: 1위 1300 ~ 꼴찌 1200 직선
        return int(round(1300 - (r - 1) * 100 / (n - 1))), f"인도 슈퍼리그 2014 {r}위 (추정: 1위 1300~꼴찌 1200 직선)"
    return None

# 리그 경기 상대: (리그, TM 시즌 id) / 컵·대륙 대회 상대는 날짜로 정한 리그 표
def rank_lookup(k, d, cid, g):
    y = int(d[:4]); m = int(d[5:7])
    cands = []
    if cid in ("ARG1", "ARGC", "ARG2"): cands = [(cid, int(g["seasonId"]))]
    elif cid == "ARCA": cands = [("ARG2", 2011), ("ARG1", 2011)]
    elif cid == "IND1": cands = [("IND1", 2013)]
    else:
        s = y if m >= 7 else y - 1
        cands = [("FR1", s), ("FR2", s)]
    for lg, sid in cands:
        t = RANKS.get((lg, sid))
        if t and k in t:
            res = model(lg, sid, *RANK_FIX.get((lg, sid, k), t[k]))
            if res: return res
    return None

# 직접 추정·확인한 값(모두 출처를 judgments.md에 적음): (key, 시즌 키) -> (Elo, lv)
MAN = {
    # 우루과이 2013-14 연간 순위(영어 위키백과 2013–14 Campeonato Uruguayo 'Aggregate table') 2위. 기존 우루과이 연간·반시즌 2위 값 1635와 같게
    (key("Club Nacional"), "2013-14"): (1635, "우루과이 1부 2013-14 연간 2위"),
    # 스코틀랜드 1999-00 5위/10팀: 다른 선수 자료의 레인저스 1999-00 1위 1620(추정)에서 세리에B 흩어짐(51.24) 곡선으로 옮긴 값
    # 콜론 2013: 피날 2013 17위(1522)·이니시알 2013 20위(1497) 두 대회에서 만남 → 같은 팀·연도 값 하나로 평균(리켈메 자료 선례)
    (key("CA Colón"), "2013"): (1510, "아르헨티나 1부 2013 (추정, 피날 2013 17위·이니시알 2013 20위 값 평균)"),
    (key("St. Johnstone FC"), "1999-00"): (int(round(1620 + 51.24 * (curve(5, 10) - curve(1, 10)))), "스코틀랜드 1999-00 5위/10팀 (추정, 다른 선수 자료의 레인저스 1위 1620을 2부 흩어짐 곡선으로 옮김)"),
}

ELO_SRC = collections.Counter(); ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def season_keys(d, cid):
    eu = season_eu(d); y0 = int(eu[:4])
    if cid in ("ARG1", "ARGC"): return [d[:4]]
    if cid in ("ARG2", "ARCA"): return ["2011-12"]
    if cid == "CLI": return ["2013-14", d[:4]]
    if cid == "IND1": return [d[:4]]
    if cid in ("CL", "CLQ", "UEFA", "EL", "ELQ"): return [eu, str(y0), str(y0 + 1)]
    return [eu]

def opp_elo(opp, d, cid, g):
    k = key(opp)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or (cid not in ("ARG1", "ARGC", "ARG2", "ARCA", "CLI") and _sub(key(x["opp"]), k)))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    for s in season_keys(d, cid):
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in season_keys(d, cid):
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man " + s))
            return e, lv
    res = rank_lookup(k, d, cid, g)
    if res:
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model"))
        return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local_tz_conv"]   # TM API UTC를 클럽 나라 시간으로 바꾼 날짜(아르헨티나 저녁 경기 14개가 TM 리포트 날짜보다 하루 앞)

M = []
for g in GAMES:
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round_report"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, g):
    res = opp_elo(opp, d, cid, g)
    if res is None:
        missing_elo.add((opp, d, cid)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, 0, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["trezeguet_scorer"] == "1", e["trezeguet_assist_other"] == "1", e["trezeguet_self_assist"] == "1"
    if iss: judg.append(("본인 골의 본인 도움(도움 아님)", ldate(g), e["minute"]))
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
    comp = comp_of(cid, g["round_report"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        if tag in EXCL_G:
            judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag])); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1" and e["goal_desc"] == "Penalty"), 0, tie, comp, ko, d, opp, cid, g)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours: sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal", "Deflected"): sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP and tag not in ADD_CONFIRMED: sys.exit("2014.8 이후 도움 판정 누락 " + tag)
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, g)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4], 0 if r[0] == "g" else 1))
E = rows

# 같은 팀·시즌 키에 내 값이 둘 이상이면 멈춤(통합표 충돌 방지)
_tv = collections.defaultdict(set)
for x in ELO_LOG: _tv[(key(x[1]), x[3])].add(x[2])
for (k, lv), v in _tv.items():
    if len(v) > 1: sys.exit(f"같은 팀·lv 값 여럿: {k} {lv} {v}")

if __name__ == "__main__" and "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        kk = (x[1], x[2], x[3])
        if kk in seen: continue
        seen.add(kk); print(x)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["trezeguet_scorer"] == "1" and e["gameId"] in G: TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV: continue
    fg = [r for r in FM_EV[gid] if r["trezeguet_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1" and t["goal_desc"] == "Penalty"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        if tpk != fpk or tm_min != fm_min:
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {  # 이름: (파일, 접두어, 같이 뛴 기간)
    "Alessandro Del Piero": ("del.js", "DEL", "2000-08-01", "2010-09-01"),
    "Pavel Nedved": ("ned.js", "NED", "2001-07-01", "2009-07-01"),
    "Mauro Camoranesi": ("cam.js", "CAM", "2002-07-01", "2010-09-01"),
    "Zlatan Ibrahimović": ("ibr.js", "IBR", "2004-08-01", "2006-08-01"),
    "Zinédine Zidane": ("zid.js", "ZID", "2000-08-01", "2001-07-01"),
    "Diego": ("die.js", "DIE", "2009-07-01", "2010-09-01"),
    "Filippo Inzaghi": ("inz.js", "INZ", "2000-08-01", "2001-07-01"),
    "Antonio Candreva": ("can.js", "CAN", "2010-01-01", "2010-07-01"),
    "Simone Pepe": ("spe.js", "SPE", "2010-07-01", "2010-09-01"),
    "Ciro Immobile": ("imm.js", "IMM", "2009-07-01", "2010-07-01"),
    "Thierry Henry": ("hen.js", "HEN", "1995-07-01", "1999-01-20"),
    "Ludovic Giuly": ("giu.js", "GIU", "1998-01-01", "2000-07-01"),
}
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
for nm, (fn, P, lo, hi) in MATES.items():
    ent = load_js(fn, P)
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("트레제게 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and norm(x[13]) == norm("David Trezeguet"):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→트레제게 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                    if dd: CROSS.append(("같은 경기 다름", nm, r[9], r[1], dd))
                    break
    # TM이 트레제게 도움으로 적었지만 이 자료에서 뺀 동료 골 / TM 동료 도움이 동료 파일에 없는 것
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["trezeguet_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 트레제게 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    for e in EVENTS:
        if e["trezeguet_scorer"] == "1" and e["gameId"] in G and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움이 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("montz", "2000-07-01", "모나코", "1995~2000"), ("juvtz", "2010-09-01", "유벤투스", "2000~2010"),
         ("hertz", "2011-07-01", "에르쿨레스", "2010~2011"), ("bantz", "2012-01-01", "바니야스", "2011"),
         ("rivtz", "2013-07-01", "리버 플레이트", "2012~2013"), ("newtz", "2014-07-01", "뉴웰스 올드 보이스", "2013~2014"),
         ("puntz", None, "FC 푸네 시티", "2014")]
TM_CLUB = {"162": "montz", "506": "juvtz", "7971": "hertz", "4785": "bantz", "209": "rivtz", "1286": "newtz", "45275": "puntz"}
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {k: n for k, u, n, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NOTE_LINES = [
    f"다비드 트레제게(모나코·유벤투스·에르쿨레스·바니야스·리버 플레이트·뉴웰스 올드 보이스·FC 푸네 시티)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 올랭피크 리옹전 ~ {d_(M[-1][0])} 케랄라 블래스터스전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·프랑스 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]}({y}) {c3(ST[k])}" for k, u, n, y in CLUBS)
    + f". 출전 분 합계 {MIN_TOT:,}분(Transfermarkt 기록, 90분으로 추정한 경기 없음)",
    "출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있는 경기와 리그 밖 경기 전부), 2010-11 이후 골은 FotMob 경기 이벤트와 대조함. 클럽별 경기 수·골은 영어·스페인어·프랑스어·이탈리아어 위키백과와 대조함(아래 차이 말고는 같음)",
    "넣지 않은 경기: 플라텐세(아르헨티나 1부, 1993-94·1994-95) 위키백과 5경기 0골은 경기별 자료가 없어 뺌(Transfermarkt는 이 시기 61경기 모두 명단 제외로 적고, 영어 위키백과가 첫 경기로 적은 1994.6.12 힘나시아전도 명단 제외). 모나코 2군(4부 CFA) 경기는 2군이라 뺌. 바니야스의 에티살라트 컵 1경기(위키백과·FotMob 시즌 합계에만 있음)는 날짜·상대를 확인할 자료가 없어 뺌",
    "출처 간 차이: 모나코 1999-00 UEFA컵은 Transfermarkt·스페인어·프랑스어·이탈리아어 위키백과 7경기(영어 위키백과 6경기), 유벤투스 2008-09 코파 이탈리아는 Transfermarkt 등 3경기(영어 위키백과 1경기) — 모두 Transfermarkt 경기 목록을 씀. 리버 플레이트 2012-13 리그는 스페인어 위키백과만 17경기(다른 출처 16경기)",
    "날짜: 아르헨티나·리베르타도레스 저녁 경기 14개는 Transfermarkt 리포트 날짜(중부 유럽 시간)보다 하루 앞인 현지 날짜를 씀(예 2012.6.10 보카 우니도스전, 2013.2.10 벨그라노전). 2003.8.3 수페르코파 이탈리아나(밀란전)는 미국 이스트러더퍼드 경기로 현지 날짜 그대로",
    "골: Transfermarkt 리포트 골 273개를 모두 씀(자책골 없음). PK 골은 골 유형 'Penalty' 기준. 2003.8.3 수페르코파 밀란전 골은 연장 전반 추가시간 105+3분(0-1에서 1-1, 승부차기 승). 2010-11 이후 골은 FotMob과 개수·스코어·PK가 같고, 시각이 1~3분 다른 골은 Transfermarkt 시각을 씀(2012.2.18 인데펜디엔테 리바다비아전 88분, FotMob 85분 등). FotMob 자료가 없는 에르쿨레스 2경기(2011.1.10 아틀레티코전, 2011.2.13 사라고사전) 골은 Transfermarkt만 근거",
    f"도움: 2014.8.1 이전 경기만 있어 Transfermarkt 경기 리포트 도움을 씀(단일 출처: 2010년 이전은 FotMob 경기 자료가 없고, 2011~14 아르헨티나 경기는 FotMob이 도움을 거의 적지 않음). 도움 {NA} = Transfermarkt 53 − 슈팅 리바운드('Shot on goal') 6(1998.11.28 스트라스부르전 크리스타발, 2003.9.21 로마전 디 바이오, 2004.9.25 팔레르모전 이브라히모비치, 2005.12.11 칼리아리전 네드베드, 2007.9.26 레지나전·2007.12.23 시에나전 살리하미지치) − 상대 자책골에 준 도움 2(2003.1.12 레지나전 코차, 2005.12.11 칼리아리전 비냐티). 유형 칸이 빈 도움 4개(2001.11.29 레버쿠젠전 델 피에로, 2003.3.12 데포르티보전 투도르, 2009.3.10 첼시전 이아퀸타, 2013.8.27 힘나시아전 크루사도)는 일반 도움으로 셈",
    "프랑스어 위키백과 시즌별 도움(클럽 대회)은 Transfermarkt와 시즌마다 0~3개 다름(유벤투스 Transfermarkt 40 vs 30, 모나코 9 vs 9) — 경기별 근거가 있는 Transfermarkt 리포트를 씀",
    "동료 자료 대조: 델 피에로·네드베드·카모라네시·지단·이브라히모비치·디에구·칸드레바·앙리·지울리 자료의 트레제게 관련 골·도움과 날짜·분·스코어·대회·상대 Elo가 같음. 델 피에로 자료가 슈팅 리바운드·PK 유도로 뺀 트레제게 골 도움(2003.1.12 레지나전 등)은 이 자료에서도 다른 선수 도움으로 셈하지 않음(트레제게 골만 셈)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위(Transfermarkt 순위표, 위키백과로 확인)를 기존 리그 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위표+모형 {SRC['순위표+리그 모형']}, 직접 {SRC['직접 추정']})",
    "리그1·리그2·아르헨티나 1·2부는 같은 시즌 다른 선수 자료의 순위값 사이를 앞뒤 순위 값으로 보간(없으면 기존 리그 모형). 아르헨티나 2부(프리메라 B 나시오날 2011-12)는 다른 선수 자료와 같은 추정(1부 평균 1583에서 약 228 낮춘 평균 1355, 근거 약함). 인도 슈퍼리그 2014는 다른 선수 자료와 같은 추정(1위 1300~꼴찌 1200 직선). 우루과이 나시오날 2013-14는 연간 순위 2위(기존 우루과이 2위 값 1635). 세인트 존스톤 1999-00(스코틀랜드 5위)은 다른 선수 자료의 레인저스 1위 1620에서 옮긴 추정",
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·코파 이탈리아·코파 아르헨티나는 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), 트로페 데 샹피옹·수페르코파 이탈리아나는 국내컵 결승, UEFA컵 1라운드는 유로파 예선, UEFA컵 2라운드 이후·유로파 32강·16강은 유로파 토너먼트, 챔스 2차 조별(2001-02·2002-03)은 조별, 리베르타도레스 조별은 리베르타도레스 비중, 세리에B·프리메라 B 나시오날·UAE 프로리그·인도 슈퍼리그는 리그로 계산함",
    f"두 경기 합산(챔스·UEFA컵·유로파 예선과 토너먼트, 코파 이탈리아 두 경기 라운드) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음). 2009.3.3 코파 이탈리아 준결승 1차전(라치오)은 Transfermarkt 라운드 이름에 차전 표시가 없지만 1차전으로 셈",
    "시즌 구분: 모나코는 7월 10일 기준(1997.7.23 트로페 데 샹피옹·1999.7.30 리그 개막전이 새 시즌, 다른 선수 자료의 모나코와 같음), FC 푸네 시티는 달력 연도(인도 슈퍼리그 2014), 나머지는 기본 8월 1일(리버 플레이트 2011-12·2012-13, 뉴웰스 2013-14). 클럽 구분은 2000.7.1 전 모나코, 2010.9.1 전 유벤투스, 2011.7.1 전 에르쿨레스, 2012.1.1 전 바니야스, 2013.7.1 전 리버 플레이트, 2014.7.1 전 뉴웰스, 이후 FC 푸네 시티",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 리그1 2회(1996-97·1999-00), 세리에A 2회(2001-02·2002-03), 트로페 데 샹피옹 1997-98, 수페르코파 이탈리아나 2003-04(FotMob은 2002-03도 우승으로 적지만 트레제게는 그 경기에 뛰지 않았고 Transfermarkt에 없음), 세리에B 2006-07, 아르헨티나 2부 2011-12(리버 플레이트). 준우승은 챔스 결승 2002-03(승부차기 패, 120분 출전)만 넣음. 개인: 세리에A 득점왕 2001-02(24골, 이 계산기 기록과 같음), 세리에A 올해의 선수 2001-02(선수협회 AIC 오스카 델 칼초; Transfermarkt의 '올해의 선수 2002'·'최우수 외국인 선수 2002'와 같은 시상이라 한 번만 넣음). 월드컵·유로 등 대표팀 기록은 뺌",
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
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# 통합 때 정정(오케스트레이터): 힘나시아 데 후후이 2011-12는 18위(위키·TM). 디발라 자료의 9위(힘나시아 라플라타 순위) 표기를 18위 1300(17위 1305·19위 1295 가운데)으로 함께 고침
for e in E:
    if e[1] == "Club Atlético Gimnasia y Esgrima (Jujuy)" and e[12] == "아르헨티나 2부 2011-12 9위 (추정)":
        e[2] = 1300; e[12] = "아르헨티나 2부 2011-12 18위 (추정)"
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const TRZ_E={J(E)};\nconst TRZ_M={J(M)};\nconst TRZ_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
