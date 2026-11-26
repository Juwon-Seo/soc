#!/usr/bin/env python3
"""Antonio Valencia(안토니오 발렌시아): raw/ -> valencia.json + src/data/val.js (판정 근거는 judgments.md)

  python3 players/valencia/build_valencia.py            # 파일 쓰기
  python3 players/valencia/build_valencia.py --debug    # Elo 출처·도움 판정 로그
  python3 players/valencia/build_valencia.py --cross    # 동료 자료 대조
  python3 players/valencia/build_valencia.py --fm       # FotMob 골 대조
  OUT_ROOT=<복사본> 로 다른 저장소 복사본에 쓰기(검증용)

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv, /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv,
      src/data/*.js(동료 대조). 월콧(players/walcott/build_walcott.py)을 바탕으로 함.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT_ROOT = os.environ.get("OUT_ROOT", ROOT)
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(OUT_ROOT, "src", "data", "val.js")
OUT_JSON = os.path.join(HERE, "valencia.json")
ME = "안토니오 발렌시아"
GAP = "2014-08-01"   # 전: Transfermarkt 도움 단독 허용, 후: Transfermarkt ∩ FotMob(또는 다른 출처로 확인)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")   # 성인 클럽 played 492경기(맨유 U21 1경기·대표팀·'다른 팀으로 출전' 행은 수집 단계에서 빠짐)
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 판정 표
# Transfermarkt 리포트가 다른 선수 골로 적은 발렌시아 골(judgments.md 3절): "gameId|분" -> (도움 선수, 근거)
GOAL_FIX = {
    "81842|52": ("Jason Koumas", "2008.5.3 애스턴 빌라전(원정 2:0) 52분 첫 골: Transfermarkt는 팔라시오스 골로 적었으나 Sky Sports 경기 기사(발렌시아 후반 두 골)·worldfootball 경기 기록(52분·63분 발렌시아)·ESPN 경기 기록·soccernews('Valencia double')가 발렌시아 골. FotMob 경력·영어/스페인어 위키백과 2007-08 3골과도 맞음"),
}
# 2014.8 이후 FotMob 이벤트에 도움자가 없는 Transfermarkt 도움 중 다른 출처로 확인한 것(judgments.md 4절)
ADD_CONFIRMED = {
    "2478487|17": "2014.8.24 선덜랜드전 마타 골: FotMob 이벤트는 도움자 빈칸. NBC Sports·FourFourTwo·ESPN 경기 기사가 발렌시아 크로스(일부 기사는 살짝 굴절된 크로스라 적음)",
    "2770139|62": "2016.11.30 웨스트햄전(리그컵 8강) 마르시알 두 번째 골: FotMob 이벤트는 도움자 빈칸. Daily Express(Valencia's low cross)·FourFourTwo(Valencia's pass across goal)",
    "3187022|85": "2019.7.23 올림피아전(리베르타도레스 16강 1차전) 아기레 골: FotMob은 이 대회 도움 자료가 없음. EFE 기사(프리킥에서 발렌시아가 살짝 밀어 준 공을 아기레가 슛)·Trivela(Valencia rolou a cobrança de falta)",
    "3189802|83": "2019.9.22 무슉 루나전 아기레 네 번째 골: FotMob은 에콰도르 리그 도움 자료가 없음. El Comercio 경기 기사(발렌시아 크로스를 아기레가 머리로)",
    "3276426|76": "2019.11.10 델핀전(코파 에콰도르 결승 1차전) 치카이사 골: FotMob 자료 없음. Primicias 기사(발렌시아 패스)",
}
# Transfermarkt 'Shot on goal' 도움은 뺀다(2017.3.4 본머스전 로호 골은 FotMob은 도움으로 세지만 기사상 발렌시아 슈팅을 로호가 방향만 바꿈)
SOG_KEEP = {}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"GB1", "ES1", "ES2", "MEX1", "EC1N", "EL1A"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in ("GBCS", "USC", "ECSC"): return "df"            # 커뮤니티 실드·UEFA 슈퍼컵·수페르코파 에콰도르 = 국내컵 결승 비중
    if cid in ("FAC", "CGB", "ECUP"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth round") or r.startswith("6th round"): return "dk"   # FA컵 6라운드(재경기 포함) = 8강
        return "dc"     # 2·3·4라운드·16강, FA컵 5라운드(16강)와 재경기
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
        return "elk"    # 32강('intermediate stage', 2011-12 'Second Round')·16강·8강
    if cid == "CLI":
        if r.startswith("group") or r.startswith("last 16"): return "lib"
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
    if cid in ("LPPL", "POME"):   # 에콰도르 리그 플레이오프(3단계)·멕시코 리길야 진출전 = MLS 플레이오프 비중(지냑·카모라네시 리길야 선례)
        if r.startswith("semi"): return "mlpsf"
        if r.startswith("final"): return "mlpf"
        return "mlp"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    if "matchday" in g["round"].lower(): return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = ldate(g)
    leg = 1 if "1st" in g["round"].lower() else 2
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        oid = TIES_RAW[gid]["other_leg_id"]
        o = INFO[oid]
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "EL"):
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CGB":
        if d >= "2018-07-01": sys.exit("리그컵 2018-19 이후 준결승 규칙 확인 필요 " + gid)
        ag, et = 1, 1      # 잉글랜드 리그컵 준결승: 2017-18까지 원정 다득점·연장
    elif cid == "CLI":
        ag, et = 1, 0      # 리베르타도레스 2019: 원정 다득점, 연장 없이 승부차기(결승 제외)
    elif cid == "ECUP":
        ag, et = 1, 0      # 코파 에콰도르 2019: 원정 다득점(결승 LDU 우승), 연장 없이 승부차기(준결승 2차전)
    elif cid == "LPPL":
        ag, et = 0, 0      # 에콰도르 2019 플레이오프: 합산 동률이면 정규 단계 상위 팀 진출(8강·4강), 결승은 승부차기
    else:
        sys.exit("합산 규칙 없음 " + cid)
    return [leg, home, fu, ft, ag, et]

# ---------------------------------------------------------------- 날짜(현지)
def ldate(g):
    # 남미·멕시코 경기: API UTC 시각을 개최지 시간대로 바꾼 날짜(Transfermarkt 리포트·일정 날짜는 유럽 기준이라 저녁 경기가 하루 밀림)
    if g["date_local_from_utc_host_tz_americas"]: return g["date_local_from_utc_host_tz_americas"]
    return g["date_local_tm_report"] or g["date_local_tm_schedule"]

OPP_NAME = {"17584": "CD Universidad Católica del Ecuador"}   # 칠레 'CD Universidad Católica'와 구분
def opp_of(g):
    return OPP_NAME.get(g["opponent_id"], g["opponent"].strip())

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

def season_eu(d):
    y = int(d[:4])
    s = 2019 if d.startswith("2020-08") else (y if int(d[5:7]) >= 8 else y - 1)
    return f"{s}-{str(s + 1)[2:]}"

exec(open(os.path.join(HERE, "elo_valencia.py"), encoding="utf-8").read())   # MAN

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

AMERICAS = ("CLI", "EC1N", "EL1A", "LPPL", "ECUP", "ECSC", "MEX1", "POME")
def opp_elo(opp, d, cid):
    k = key(opp)
    eu = season_eu(d)
    if cid not in AMERICAS:
        same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
                and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
        if same:
            (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
            ELO_SRC["같은 경기 다른 선수 자료"] += 1
            ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
            return e, lv
    seasons = [d[:4]] if cid in ("CLI", "EC1N", "EL1A", "LPPL", "ECUP", "ECSC") else [eu]
    if cid in ("CL", "EL"):   # 달력 연도 리그 팀(유럽 대회 상대): 가을 경기는 그해 시즌
        y0 = int(eu[:4]); seasons = [eu, str(y0) if int(d[5:7]) >= 7 else str(y0 + 1)]
    if cid in ("MEX1", "POME"):
        y = int(d[:4]); s = y if int(d[5:7]) >= 7 else y - 1; seasons = [f"{s}-{str(s + 1)[2:]}"]
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    return None

# ---------------------------------------------------------------- 출전
M = []
for g in GAMES:
    M.append([ldate(g), opp_of(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

FM_ASSIST = collections.defaultdict(list)
for gid, evs in FM_EV.items():
    for r in evs:
        if r["valencia_assist"] == "1":
            FM_ASSIST[gid].append((int(r["time"]) + int(r["overloadTime"] or 0), int(r["time"]), r["scorer"]))
rows, judg = [], []
missing_elo = set()
A_STATUS = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et):
    res = opp_elo(opp, d, cid)
    if res is None:
        missing_elo.add((opp, season_eu(d), cid, d)); res = (0, "?")
    elo, lv = res
    row = [typ, opp, elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    rows.append(row)

def fm_hit(gid, tm_min_str):
    mi = minute(tm_min_str)[0]; base = int(tm_min_str.split("+")[0])
    return [t for t in FM_ASSIST.get(gid, []) if abs(t[0] - mi) <= 2 or abs(t[1] - base) <= 2]

def ctx(e, g):
    inf = INFO[e["gameId"]]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    return ours, gf, ga

for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    tag = f"{gid}|{e['minute']}"
    isg, isa = e["valencia_scorer"] == "1", e["valencia_assist_other"] == "1"
    if tag in GOAL_FIX:
        assert e["valencia_scorer"] == "0" and e["own_goal"] == "0"
        isg = True
        judg.append(("골 추가(득점자 정정)", ldate(g), opp_of(g), e["minute"], GOAL_FIX[tag][1]))
    if not (isg or isa): continue
    ours, gf, ga = ctx(e, g)
    mi, dm = minute(e["minute"])
    et = int(int(e["minute"].split("+")[0]) > 90)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = opp_of(g)
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골(" + e["goal_desc"] + ")")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        st = None
        if e["own_goal"] == "1" or not ours:
            st = "제외:상대 자책골"
        elif e["assist_type"].startswith("Penalty"):
            st = "제외:PK 유도"
        elif e["assist_type"] == "Shot on goal" and tag not in SOG_KEEP:
            st = "제외:Shot on goal"
        if st:
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], st))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], st)); continue
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = fm_hit(gid, e["minute"])
            if not hit:
                A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "TM단독-미확인"))
                judg.append(("도움 미확인", d, opp, e["minute"], e["scorer"])); continue
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "TM∩FotMob"))
        elif d >= GAP:
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "추가확인"))
        else:
            A_STATUS.append((gid, d, e["minute"], e["scorer"], e["assist_type"], "TM(2014.8 전)"))
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

# FotMob에만 있는 도움(같은 경기 TM 도움 없음): 기록용
TM_A = collections.defaultdict(list)
for e in EVENTS:
    if e["valencia_assist_other"] == "1": TM_A[e["gameId"]].append(minute(e["minute"])[0])
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    if gid not in G: continue
    for t in ts:
        if "Valencia" in t[2]: continue
        if any(abs(t[0] - x) <= 2 or abs(t[1] - x) <= 2 for x in TM_A.get(gid, [])): continue
        FM_ONLY.append((gid, ldate(G[gid]), t))
SELF_A = [(e["gameId"], e["date"], e["minute"]) for e in EVENTS if e["valencia_self_assist"] == "1"]

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[3]): print("Elo 없음:", x)
    if "--allow-missing" not in sys.argv: sys.exit(1)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, "\nFotMob 전용 도움:", FM_ONLY, "\nself:", SELF_A)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)
    print(collections.Counter(s[5][:12] for s in A_STATUS))
    for s in A_STATUS:
        if s[5] not in ("TM∩FotMob", "TM(2014.8 전)"): print(s)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11부터)
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["valencia_scorer"] == "1" and e["own_goal"] == "0" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if ldate(G[gid]) < "2010-08-01": continue
    if gid not in FM_EV:
        FM_CMP.append(("FotMob 이벤트 파일 없음", gid, ldate(G[gid]))); continue
    fg = [r for r in FM_EV[gid] if r["valencia_scorer"] == "1" and r["pen_shootout_event"] != "True" and r["ownGoal"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or t["score_home_away_after"] != f["newScore_home_away"]:
            FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["score_home_away_after"], f["time"], f["overloadTime"], f["newScore_home_away"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
DATA = os.path.join(ROOT, "src", "data")
def load_js(fn, P):
    s = open(os.path.join(DATA, fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Wayne Rooney": ("roo.js", "ROO"), "Robin van Persie": ("van.js", "VAN"), "Ryan Giggs": ("gig.js", "GIG"),
         "Shinji Kagawa": ("kag.js", "KAG"), "Zlatan Ibrahimović": ("ibr.js", "IBR"), "Ángel Di María": ("dim.js", "DIM"),
         "Radamel Falcao": ("fal.js", "FAL")}
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items() if os.path.exists(os.path.join(DATA, v[0]))}
MY_NAMES = ("Antonio Valencia", "Luis Antonio Valencia")
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
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("발렌시아 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and x[13] in MY_NAMES:
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→발렌시아 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for e in EVENTS:
        if e["valencia_scorer"] == "1" and e["own_goal"] == "0" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움→발렌시아 골인데 동료 파일에 도움 없음", nm, d, e["minute"], e["assist_type"]))
    for s in A_STATUS:
        if norm(s[3]) == norm(nm) and (s[5].startswith("제외") or s[5] == "TM단독-미확인"):
            hit = [x for x in ent if x[0] == "g" and x[9] == s[1] and abs(x[4] - minute(s[2])[0]) <= 2]
            CROSS.append(("발렌시아 도움에서 뺀 TM 도움(참고)", nm, s[1], s[2], s[5][:20], "동료 골 행 있음" if hit else "동료 골 행 없음"))
    for r in E:
        same = [x for x in ent if x[9] == r[9] and key(x[1]) == key(r[1])]
        for x in same:
            if (x[2], x[12], x[3]) != (r[2], r[12], r[3]):
                CROSS.append(("같은 경기 Elo/lv/대회 다름", nm, r[9], r[1], (r[2], r[12], r[3]), (x[2], x[12], x[3])))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], str(c[-1])[:12]) for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("nacav", "2005-07-01", "엘 나시오날", "2003~2005"), ("vilav", "2006-01-03", "비야레알", "2005~2006"),
         ("recav", "2006-08-03", "레크레아티보", "2006"), ("wigav", "2009-07-01", "위건 애슬레틱", "2006~2009"),
         ("munav", "2019-07-12", "맨체스터 유나이티드", "2009~2019"), ("lduav", "2021-01-01", "LDU 키토", "2019~2020"),
         ("queav", None, "케레타로", "2021")]
TMC = {"1143": "nacav", "1050": "vilav", "2867": "recav", "1071": "wigav", "985": "munav", "9855": "lduav", "4961": "queav"}
def club_idx(d):
    for i, (k, u, _, _) in enumerate(CLUBS):
        if u is None or d < u: return i
ST = collections.OrderedDict((i, [0, 0, 0, 0]) for i in range(len(CLUBS)))
for m in M: ST[club_idx(m[0])][0] += 1; ST[club_idx(m[0])][3] += m[3]
for r in E: ST[club_idx(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if CLUBS[club_idx(ldate(g))][0] != TMC[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
exec(open(os.path.join(HERE, "note_valencia.py"), encoding="utf-8").read())
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "lv", "mlp", "lib"]:
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
    mm = [m for m in M if m[0] == r[9]]
    if mm and (mm[0][2] != r[3] or key(mm[0][1]) != key(r[1])): problems.append(("출전 행과 대회·상대 다름", r, mm[0]))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len([a for a in sys.argv[1:] if a.startswith("--")]) == 0:
    open(OUT_JS, "w", encoding="utf-8").write(f"const VAL_E={J(E)};\nconst VAL_M={J(M)};\nconst VAL_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "self_assist_events": SELF_A, "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY,
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{OUT_JS}: {NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for i, v in ST.items(): print(" ", CLUBS[i][0], CLUBS[i][3], v)
