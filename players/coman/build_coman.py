#!/usr/bin/env python3
"""Kingsley Coman: raw/ -> coman.json + src/data/com.js (판정 근거는 judgments.md)

  python3 players/coman/build_coman.py            # 파일 쓰기
  python3 players/coman/build_coman.py --debug    # Elo 출처 로그
  python3 players/coman/build_coman.py --cross    # 동료 자료 대조
  python3 players/coman/build_coman.py --fm       # FotMob 골 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv(FotMob 경기 이벤트),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료),
      src/data/{mul,lew,mus,kan,san,gna,man,rib,rob,ron,ibr,cav,luc,dyb}.js(같은 경기 동료 자료 대조).
그나브리 빌드 스크립트(players/gnabry/build_gnabry.py)를 같은 형식의 원자료에 맞게 고친 것.
판정 표(아래 대문자 상수)는 모두 judgments.md에 출처와 함께 적혀 있다.
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "com.js")
OUT_JSON = os.path.join(HERE, "coman.json")
ME = "킹슬리 코망"
GAP = "2014-08-01"   # 도움 출처 기준일: 코망의 성인 도움은 모두 이후(유벤투스 2014.11.9부터) → Transfermarkt∩FotMob

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
# 도움 제외(Transfermarkt 리포트 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    # PK 유도('Penalty: Fouled player', 득점자 = 동료)
    "2618546|90+2": "PK 유도(뮐러 PK, 올림피아코스 원정)",
    "2871980|87": "PK 유도(레반도프스키 PK, 하노버)",
    "3174557|80": "PK 유도(레반도프스키 PK, 브레멘 DFB-포칼 준결승)",
    "3203447|20": "PK 유도(레반도프스키 PK, 샬케)",
    "3413063|44": "PK 유도(레반도프스키 PK, 도르트문트)",
    "3839085|59": "PK 유도(마네 PK, 보훔)",
    # 'Shot on goal'(코망 슈팅 뒤 리바운드) — FotMob 경기 이벤트는 도움으로 셌지만 v1.116 이후 리바운드 제외 기준
    "2618604|29": "리바운드('Shot on goal', 아스널전 뮐러 골; FotMob은 도움)",
    "2618621|16": "리바운드('Shot on goal', 올림피아코스전 레반도프스키 골; FotMob은 도움)",
    "3496449|42": "리바운드('Shot on goal', 라치오전 자네 골; FotMob은 도움)",
    "3839483|17": "리바운드('Shot on goal', 호펜하임전 파바르 골; FotMob은 도움)",
    # Transfermarkt 단독(FotMob 경기 이벤트 없음) — 기사 확인 결과 도움 기준에 안 맞음
    "3058701|75": "굴절(뉘른베르크전 그나브리 75분: 바이에른 구단 경기 기사 '굴절된 코망 크로스', 다른 기사는 상대 바우어의 걷어내기가 그나브리 맞고 들어감)",
    "3195536|32": "리바운드(코트부스전 레반도프스키 32분: 바이에른 구단 경기 기사·bundesliga.com — 키미히 크로스를 코망이 헤더, 골키퍼 모저가 막은 공을 레반도프스키가 밀어 넣음)",
}
# FotMob 경기 이벤트에 없지만(Transfermarkt 단독) 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "3588470|9": "바이에른 구단 경기 기사 '뮐러 칩 패스 → 코망 헤더로 내줌 → 레반도프스키 첫 터치 뒤 마무리' · AP 기사(Fox Sports 게재) 'Lewandowski did well to control Kingsley Coman's ball back'",
    "4618871|71": "playerstats.football 경기 기록 '71' 0-3 J. Félix (K. Coman)' · 노동신문(laodong.vn) 경기 기사 '코망의 도움을 받아 펠릭스가 정확히 마무리' (Arab News·ESPN은 71분 펠릭스 골만 적음)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1", "IT1", "FR1", "SA1"}
CUP = {"DFB", "CIT", "SAKC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("DFL", "FRCH", "SCI"): return "df"          # 단판 슈퍼컵 = 국내컵 결승
    if cid == "SASS":                                       # 사우디 슈퍼컵(4팀): 준결승 dsf, 결승 df(마네·호날두 자료와 같음)
        return "dsf" if r.startswith("semi") else "df"
    if cid == "KLUB": return "cwc"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2024-25부터 리그 페이즈('Group Stage') 포함
        if r.startswith("intermediate") or r.startswith("last 16"): return "cl16"   # 녹아웃 플레이오프 = 16강
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ACL2":
        if r.startswith("quarter"): return "ac2k"
        if r.startswith("semi"): return "ac2sf"
        if r.startswith("final"): return "ac2f"
        return "ac2"                                      # 조별·16강
    if cid == "ACLE":
        if r.startswith("quarter"): return "aclk"
        if r.startswith("semi"): return "aclsf"
        if r.startswith("final"): return "aclf"
        return "acl"                                      # 리그 단계·16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g):
    return "leg" in g["round"].lower()

def ko_of(g):
    if is_leg(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스 조별/리그 페이즈, 클럽 월드컵 2025 조별, AFC 조별·리그 단계
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
    if cid == "CL":
        ag, et = int(d < "2021-07-01"), 1
    elif cid == "CIT":   # 코파 이탈리아 준결승: 2021-22까지 원정 다득점, 2차전 연장
        ag, et = 1, 1
    elif cid == "ACL2":  # AFC 대회: 원정 다득점 없음, 연장
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
MANUAL_ALIAS = {"inter milan": "inter", "al fateh sc": "al fateh fc", "istiqlol dushanbe": "fc istiklol", "al zawraa sc": "al zawraa"}
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
    if "2020-07-01" <= d < "2020-09-01": return "2019-20"   # 코로나로 늦게 끝난 2019-20(DFB-포칼 결승·챔스 8강~결승)
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 순위표·모형·다른 선수 자료로 안 되는 상대(직접 추정, 모두 '추정')
MAN = {
    # 사우디 2부(퍼스트 디비전) 2025-26 13위/18팀(raw/ranks.txt, TM 표). 마네 자료의 사우디 2부 값 1300(오호드 2023-24)·1330(알하젬 2024-25)과 같은 수준
    (key("Jeddah SC"), "2025-26"): (1300, "사우디 2부 2025-26 13위 (추정, 다른 선수 자료의 사우디 2부 값과 같은 수준)"),
}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

INTL = ("CL", "KLUB", "ACL2", "ACLE")
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
    seasons = [eu, str(int(eu[:4])), str(int(eu[:4]) + 1)] if cid in INTL else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s))
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man"))
            return e, lv
    return None

# ---------------------------------------------------------------- 출전
def ldate(g):
    return g["date_local"]   # Transfermarkt 리포트 날짜(유럽·사우디 현지), 클럽 월드컵 2021은 카타르, 2025는 미국 동부 현지 날짜

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
        if r["coman_assist"] == "1":
            FM_ASSIST[gid].append(int(r["time"]))

rows, judg = [], []
missing_elo = set()
used_fm = collections.Counter()
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
    isg, isa = e["coman_scorer"] == "1", e["coman_assist_other"] == "1"
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
    # 연장전 골: 연장까지 간 경기에서 90분(+추가시간) 뒤 골
    et = int(g["gameDuration"] == "120" and int(e["minute"].split("+")[0]) > 90)
    cid = g["competitionId"]
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip()
    tag = f"{gid}|{e['minute']}"
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
        if e["coman_self_assist"] == "1":
            judg.append(("도움 세지 않음", d, opp, e["minute"], "본인 PK 골의 본인 도움(PK 유도) 줄"))
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours:
            sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal"):
            sys.exit("도움 유형 판정 누락 " + tag)
        if d >= GAP and tag not in ADD_CONFIRMED:
            hit = [t for t in FM_ASSIST.get(gid, []) if abs(t - int(e["minute"].split("+")[0])) <= 2 or abs(t - mi) <= 2]
            if not hit:
                sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag)
            used_fm[gid] += 1
        if tag in ADD_CONFIRMED:
            judg.append(("도움 넣음(2곳 확인)", d, opp, e["minute"], e["scorer"], ADD_CONFIRMED[tag]))
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)

# FotMob에만 있는 도움(넣지 않음) 확인
FM_ONLY = []
for gid, ts in FM_ASSIST.items():
    tm = [int(e["minute"].split("+")[0]) for e in EVENTS if e["gameId"] == gid and e["coman_assist_other"] == "1"]
    for t in ts:
        if not any(abs(t - x) <= 2 for x in tm):
            FM_ONLY.append((gid, G[gid]["date_local"] if gid in G else "?", t))

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

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

# ---------------------------------------------------------------- FotMob 골 대조
FM_CMP = []
TMG = collections.defaultdict(list)
for e in EVENTS:
    if e["coman_scorer"] == "1" and e["gameId"] in G:
        TMG[e["gameId"]].append(e)
for gid, evs in TMG.items():
    if gid not in FM_EV:
        FM_CMP.append(("FotMob 없음", gid)); continue
    fg = [r for r in FM_EV[gid] if r["coman_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(fg) != len(evs):
        FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x["minute"] for x in evs], [r["time"] for r in fg])); continue
    for t, f in zip(sorted(evs, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty") or "pen" in (f["suffix"] or "").lower()
        tm_min = minute(t["minute"])[0]; fm_min = int(f["time"]) + int(f["overloadTime"] or 0)
        base = int(t["minute"].split("+")[0])
        h, a = map(int, t["score_home_away_after"].split("-")); fh, fa = map(int, f["newScore_home_away"].split("-"))
        if tpk != fpk or not (abs(tm_min - fm_min) <= 1 or int(f["time"]) == base) or (h, a) != (fh, fa):
            FM_CMP.append(("다름", gid, G[gid]["date_local"], t["minute"], t["score_home_away_after"], t["goal_desc"], f["time"], f["overloadTime"], f["newScore_home_away"], f["goalDescriptionKey"], f["suffix"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
MATES = {"Thomas Müller": ("mul.js", "MUL", "2015-08-30", "2025-08-15"),
         "Robert Lewandowski": ("lew.js", "LEW", "2015-08-30", "2022-07-01"),
         "Jamal Musiala": ("mus.js", "MUS", "2020-06-01", "2025-08-15"),
         "Harry Kane": ("kan.js", "KAN", "2023-08-12", "2025-08-15"),
         "Leroy Sané": ("san.js", "SAN", "2020-07-15", "2025-08-15"),
         "Serge Gnabry": ("gna.js", "GNA", "2018-07-01", "2025-08-15"),
         "Sadio Mané": ("man.js", "MAN", "2022-07-01", "2099-01-01"),
         "Franck Ribéry": ("rib.js", "RIB", "2015-08-30", "2019-07-01"),
         "Arjen Robben": ("rob.js", "ROB", "2015-08-30", "2019-07-01"),
         "Cristiano Ronaldo": ("ron.js", "RON", "2025-08-15", "2099-01-01"),
         "Zlatan Ibrahimović": ("ibr.js", "IBR", "2013-01-01", "2014-07-01"),
         "Edinson Cavani": ("cav.js", "CAV", "2013-07-01", "2014-07-01"),
         "Lucas Moura": ("luc.js", "LUC", "2013-01-01", "2014-07-01"),
         "Paulo Dybala": ("dyb.js", "DYB", "2015-07-01", "2015-08-30")}
MATE_E = {}
for nm, v in MATES.items():
    try: MATE_E[nm] = load_js(v[0], v[1])
    except Exception as ex: print("동료 자료 못 읽음", nm, ex)
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
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("코망 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if not (lo <= x[9] < hi): continue
        # 로번 자료의 도움 행은 득점자 칸에 도움 유형이 들어 있어 날짜·분으로만 맞춤
        if x[0] == "a" and (norm(str(x[13])) == "kingsley coman" or (nm == "Arjen Robben" and any(r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E))):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→코망 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]):
                    d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                    if d: CROSS.append(("같은 경기 다름", nm, r[9], r[1], d))
                    break
    # Transfermarkt 코망 도움을 이 자료에서 뺀 동료 골(참고)
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["coman_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 코망 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    # 동료 파일에서 코망 골의 도움으로 적혔어야 할 것(TM 리포트 기준, 참고)
    for e in EVENTS:
        if e["coman_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움 → 코망 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter(c[0] for c in CROSS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("psgcm", "2014-07-01", "파리 생제르맹", "2013~2014"), ("juvcm", "2015-08-30", "유벤투스", "2014~2015"),
         ("baycm", "2025-08-15", "바이에른 뮌헨", "2015~2025"), ("nascm", None, "알나스르", "2025~")]
def club_of(d):
    for k, u, _, _ in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {"psgcm": "PSG", "juvcm": "유벤투스", "baycm": "바이에른", "nascm": "알나스르"}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    tm_club = {"583": "psgcm", "506": "juvcm", "27": "baycm", "18544": "nascm"}[g["club_id"]]
    if club_of(ldate(g)) != tm_club: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NOTE_LINES = [
    f"킹슬리 코망(파리 생제르맹·유벤투스·바이에른 뮌헨·알나스르)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 소쇼전 ~ {d_(M[-1][0])} 네프치 페르가나전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·프랑스 대표팀·유소년과 2군(PSG 2군 CFA 16경기, PSG UEFA 유스리그 6경기) 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]}({y}) {c3(ST[k])}" for k, u, n, y in CLUBS) + f". 출전 분 합계 {MIN_TOT:,}분. 바이에른은 2015.8.30~2017.6.30 유벤투스에서 임대, 2017.7.1 완전 이적",
    f"출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(출전한 {NG}경기 전부), 골·도움은 FotMob 경기 이벤트와 대조함. 출전 분이 없어 90분으로 추정한 경기 없음",
    "경기 수·골은 영어 위키백과 클럽별 기록(PSG 4·0, 유벤투스 22·1, 바이에른 339·72, 알나스르 49·17)과 FotMob 경력 합계(414경기 90골)와 같음. 바이에른 2017-18만 위키백과가 국내컵 6경기 3골·유럽 대회 5경기 1골로 나눠 Transfermarkt(국내컵 5경기 2골·챔스 6경기 2골)와 대회 구분이 다름(합계는 같음) — Transfermarkt를 씀",
    "골: Transfermarkt와 FotMob이 모든 경기에서 수·골 뒤 스코어·PK 여부가 같음. PK 골 1개(2026.1.30 알콜루드전 87분)는 0.8점. 이 골은 Transfermarkt 리포트가 코망을 PK 유도 도움으로도 적었지만 본인 골의 본인 도움이라 도움으로 세지 않음",
    f"도움: 코망의 성인 도움은 모두 2014년 8월 이후라 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것을 쓰고, Transfermarkt 한 곳만 센 것은 다른 출처 2곳이 확인한 경우에만 넣음. 도움 {NA} = Transfermarkt 85 − PK 유도 6(2015.9.16 올림피아코스전 뮐러, 2017.12.2 하노버전 레반도프스키, 2019.4.24 브레멘전(DFB-포칼) 레반도프스키, 2019.8.24 샬케전 레반도프스키, 2021.3.6 도르트문트전 레반도프스키, 2022.8.21 보훔전 마네) − 슈팅 리바운드 4 − Transfermarkt 단독이고 굴절·리바운드로 확인된 2",
    "뺀 슈팅 리바운드 4개(Transfermarkt 유형 'Shot on goal', FotMob은 도움으로 셈): 2015.11.4 아스널전 29분 뮐러, 2015.11.24 올림피아코스전 16분 레반도프스키, 2021.2.23 라치오전 42분 자네, 2023.4.15 호펜하임전 17분 파바르",
    "뺀 Transfermarkt 단독 도움 2개: 2019.4.28 뉘른베르크전 75분 그나브리 골(바이에른 구단 경기 기사는 굴절된 코망 크로스, 다른 기사는 상대 수비의 걷어내기가 그나브리 맞고 들어간 골로 적음 — 굴절), 2019.8.12 코트부스전(DFB-포칼) 32분 레반도프스키 골(바이에른 구단 경기 기사·bundesliga.com: 코망 헤더를 골키퍼가 막은 뒤 레반도프스키가 밀어 넣음 — 리바운드)",
    "FotMob 경기 이벤트에 없지만 다른 출처 2곳이 코망 도움으로 적어 넣은 2개: 2022.2.12 보훔전 9분 레반도프스키 골(바이에른 구단 경기 기사·AP 기사), 2025.9.23 제다 SC전(킹스컵) 71분 주앙 펠릭스 골(playerstats.football 경기 기록·베트남 노동신문 기사; 근거 중간)",
    f"도움 합계 비교: Transfermarkt 85·FotMob 경력 74·프랑스어 위키백과 74·이 계산기 {NA}",
    "같은 경기 동료 자료(뮐러·레반도프스키·무시알라·케인·자네·그나브리·마네·리베리·로번·호날두)와 코망 도움 → 동료 골, 동료 도움 → 코망 골의 분·골 전 스코어·대회·상대 Elo가 모두 같음. 날짜는 클럽 월드컵 2025 보카 주니어스전 케인 골만 케인 자료가 Transfermarkt 리포트 날짜(2025.6.21)로 적어 이 자료(미국 현지 2025.6.20)와 하루 다름",
    "출전 분은 Transfermarkt. FotMob 선수 경기 목록(2017.2 이후)과 1분 차이 26경기, 그보다 큰 차이 없음",
    "날짜는 현지 날짜. 클럽 월드컵 2021(카타르)은 카타르 현지, 2025(미국)는 미국 현지 날짜(보카 주니어스전 2025.6.20, Transfermarkt 리포트는 6.21)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(레반도프스키·뮐러·리베리·로번·자네·그나브리·케인·무시알라·마네·호날두 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정 순으로 씀"
    f"(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 직접 추정 {SRC['직접 추정']})",
    "직접 추정 1개: 2025.9.23 제다 SC(킹스컵 1라운드)는 사우디 2부 2025-26 13위/18팀으로 1300(추정, 마네 자료의 사우디 2부 값 1300·1330과 같은 수준)",
    "대회 비중: DFB-포칼·코파 이탈리아·킹스컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), DFL-슈퍼컵·트로페 데 샹피옹·수페르코파 이탈리아나는 국내컵 결승, 사우디 슈퍼컵(4팀)은 준결승·결승, 클럽 월드컵(2021 카타르·2025 미국)은 클럽 월드컵, AFC 챔스 투(2025-26)·AFC 챔스 엘리트(2026-27)는 아시아 대회 비중으로 계산함. 챔스 리그 페이즈(2024-25부터)는 조별과 같고, 녹아웃 플레이오프는 16강. 2020년 8월 챔스 8강·4강·결승은 단판. 클럽 월드컵 2025 조별은 리그식(무승부 1점)",
    f"두 경기 합산(챔스 토너먼트) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회 2020-21까지(2016.3.16 유벤투스전 연장 110분 골 포함). 코망이 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움. AFC 대회 두 경기 합산(2026.2 아르카다크전)은 득점·도움이 없음",
    "시즌 구분: 바이에른은 뮐러·무시알라·그나브리 자료와 같이 7월 10일 기준이되 2020.7.1~9.1(코로나로 늦게 끝난 2019-20 DFB-포칼 결승·챔스)은 2019-20(2022.7.30 DFL-슈퍼컵 = 2022-23, 2025.6~7 클럽 월드컵 = 2024-25). PSG·유벤투스·알나스르는 8월 1일 기준(2025.8 사우디 슈퍼컵 = 2025-26). 클럽 구분은 2014.7.1 전 PSG, 2015.8.30 전 유벤투스, 2025.8.15 전 바이에른, 이후 알나스르",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 챔스 2019-20, 리그 우승 14회(분데스리가 2015-16~2022-23·2024-25 9회, 세리에A 2014-15·2015-16, 리그1 2012-13·2013-14, 사우디 프로리그 2025-26), DFB-포칼 2015-16·2018-19·2019-20, 코파 이탈리아 2014-15, 쿠프 드 라 리그 2013-14, DFL-슈퍼컵 6회, 수페르코파 이탈리아나 2015, 트로페 데 샹피옹 2013, 클럽 월드컵 2020-21. 준우승: 챔스 2014-15(유벤투스), DFB-포칼 2017-18, AFC 챔스 투 2025-26. UEFA 네이션스리그 등 대표팀 기록은 뺌",
    f"현재 선수(알나스르). 마지막 반영 경기 {d_(M[-1][0])} 네프치 페르가나전(AFC 챔스 엘리트), 그 뒤 햄스트링 부상으로 명단 제외(2026.11.11 수집)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "clq", "cwc", "ac2", "acl"]:
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
mmin = {m[0]: m[3] for m in M}
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
    if r[10] and r[4] <= 90: problems.append(("연장 표시 이상", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const COM_E={J(E)};\nconst COM_M={J(M)};\nconst COM_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
