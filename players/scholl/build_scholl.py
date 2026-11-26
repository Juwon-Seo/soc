#!/usr/bin/env python3
"""메멧 숄 (Mehmet Scholl, Transfermarkt 217): raw/ -> scholl.json + src/data/scl.js (판정 근거는 judgments.md)

  python3 players/scholl/build_scholl.py            # 파일 쓰기
  python3 players/scholl/build_scholl.py --debug    # Elo 출처·도움 판정 로그
  python3 players/scholl/build_scholl.py --cross    # 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)

입력: raw/tm_games.csv(출전·분·현지 날짜), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/ranks.txt(Transfermarkt 순위표; 분데스리가 1989-90~1994-95는 2점제 공식 순위와 대조해 고친 표 RANK_FIX),
      /home/user/soc/elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료).
FotMob에는 이 선수 자료가 없음(raw/README.md). 환경 변수 SCL_ROOT: 저장소 뿌리(스크래치 복사본에서 돌릴 때).
"""
import csv, json, os, re, sys, glob, unicodedata, collections, subprocess
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SCL_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "scl.js")
OUT_JSON = os.path.join(HERE, "scholl.json")
ME = "메멧 숄"
ME_ID = "217"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 범위
# tm_games.csv = 1군 공식 경기(카를스루에 SC 48, 바이에른 27)만. 2군(카를스루에 II 오버리가·아마추어 선수권, 바이에른 II 레기오날리가)·U19은
# raw/youth_reserve_games.csv에 따로 있어 넣지 않음(2군·유스 제외 선례). 대표팀 제외.
GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
OTHER = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

CLUB_KEY = {"48": "kscms", "27": "bayms"}
CLUBS = [("kscms", "1992-07-01", "카를스루에 SC", "카를스루에", "1989~1992"),
         ("bayms", None, "바이에른 뮌헨", "바이에른", "1992~2007")]
def club_of(d):
    for k, u, *_ in CLUBS:
        if u is None or d < u: return k

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"L1"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "DFB":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"   # 1·2·3라운드·16강
    if cid == "LPO":   # DFB-리가포칼: 첫 경기(intermediate stage) 8강, 준결승, 결승(엘베르·클로제·발라크 선례)
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        return "dk"
    if cid == "DSC": return "df"   # DFB-슈퍼컵 1994 = 슈퍼컵류(국내컵 결승 비중)
    if cid == "CL":
        if r.startswith("group"): return "clg"   # 1999-00·2000-01 2차 조별도 조별
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "CLQ": return "clq"
    if cid == "ITC": return "elq"   # 옛 인터토토컵(1990, 조별) = 유로파 예선(네드베드·엘베르 선례)
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전)
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"   # 1996 결승 두 경기
        return "elk"   # 2라운드·3라운드(Last 16)·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g): return "leg" in g["round"].lower()
def ko_of(g):
    r = g["round"].lower()
    if is_leg(g) or g["competitionId"] in LEAGUE or r.startswith("group"): return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    if not is_leg(g): return None
    gid = g["gameId"]; o = OTHER[gid]
    leg = 1 if o["this_leg"] == "1st" else 2
    inf = INFO[gid]
    home = int(inf["home_id"] == g["club_id"])
    if not home and inf["away_id"] != g["club_id"]: sys.exit("홈 판정 이상 " + gid)
    if (o["other_leg_date"] < o["date_report"]) != (leg == 2): sys.exit("차전 순서 이상 " + gid)
    fu = ft = 0
    if leg == 2:   # 다른 차전 리포트의 최종 스코어(홈:원정). tm_two_leg_ties.csv의 other_leg_final은 이 경기 홈 팀 기준이라 쓰지 않음
        oi = INFO[o["other_leg_id"]]
        oh, oa = map(int, oi["final"].split(":"))
        if oi["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif oi["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if bool(home) == (oi["home_id"] == g["club_id"]): sys.exit("다른 차전 홈 이상 " + gid)
    if g["competitionId"] in ("UEFA", "CL", "CLQ"): return [leg, home, fu, ft, 1, 1]   # UEFA 대회 2021 전: 원정 다득점·연장
    sys.exit("합산 규칙 없음 " + gid)

# ---------------------------------------------------------------- 이름·기존 자료
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

def season_eu(d):   # 상대 팀 시즌(7월 1일 기준)
    y, m = int(d[:4]), int(d[5:7]); s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# ---------------------------------------------------------------- 리그 순위값
# 분데스리가: 기존 자료가 모든 시즌에 같은 순위값(2000-01 표 1~18위; 엘베르·아일톤 선례)
BL = [2006, 1912, 1860, 1828, 1812, 1797, 1777, 1756, 1737, 1723, 1713, 1702, 1697, 1682, 1661, 1644, 1634, 1613]
def half_up(x): return int(x + 0.5)
def bl_val(r, n):
    if n == 18: return BL[r - 1], False
    # 1991-92(통일 뒤 20팀): 18팀 순위값을 상대 위치로 보간(추정)
    p = (r - 1) * 17 / (n - 1); i = min(int(p), 16); t = p - i
    return half_up(BL[i] + (BL[i + 1] - BL[i]) * t), True
# 2. 분데스리가 순위값(기존 자료 순위별 값; 엘베르 L2_FIXED)
L2 = {1: 1697, 2: 1667, 3: 1636, 4: 1622, 5: 1615, 6: 1609, 7: 1600, 8: 1592, 9: 1584, 10: 1579, 11: 1574, 12: 1570,
      13: 1568, 14: 1561, 15: 1544, 16: 1545, 17: 1541, 18: 1532}

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or not p[2].isdigit(): continue
        RANKS[(p[0], p[1])][p[4]] = (int(p[2]), int(p[3]))
# 분데스리가 1989-90~1994-95는 2점제: Transfermarkt 표(3점제 재계산) 순서가 공식 순위와 다른 팀만 공식 최종 순위로 고침
# (de/en.wikipedia 'Fußball-Bundesliga 19xx/xx' 최종 순위표 — judgments.md 6절)
RANK_FIX = {}

def model(cid, d, opp):
    eu = season_eu(d)
    for lg in ("L1", "L2"):
        t = RANKS.get((lg, eu), {})
        if opp not in t: continue
        r, n = t[opp]
        r = RANK_FIX.get((opp, eu), r)
        if lg == "L1":
            v, est = bl_val(r, n)
            if est: return v, f"분데스리가 {eu} {r}위/{n}팀 (추정, 18팀 시즌 순위값을 상대 위치로 보간)"
            return v, f"분데스리가 {eu} {r}위"
        return L2[r], f"2. 분데스리가 {eu} {r}위"
    return None

# 직접 추정(모두 lv에 '추정') — judgments.md 6절
DE3 = "다른 선수 자료 독일 3부 1450과 같음"
DE4 = "다른 선수 자료 독일 4부 1300과 같음"
MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
man("Rot-Weiss Essen", "1991-92", 1450, f"독일 3부(오버리가 노르트라인) 1991-92 2위 (추정, {DE3})")
man("Tennis Borussia Berlin", "1996-97", 1450, f"독일 3부(레기오날리가 북동부) 1996-97 6위 (추정, {DE3})")
man("VfL Osnabrück", "2001-02", 1450, f"독일 3부(레기오날리가 북부) 2001-02 7위 (추정, {DE3})")
man("FC Schönberg 95", "2000-01", 1300, f"독일 4부(NOFV-오버리가 북부) 2000-01 3위 (추정, {DE4})")
man("MSV 1919 Neuruppin", "2005-06", 1300, f"독일 4부(NOFV-오버리가 북부) 2005-06 2위 (추정, {DE4})")
man("TSV Völpke", "2004-05", 1180, "독일 5부(페어반츠리가 작센안할트) 2004-05 (추정, 다른 선수 자료 독일 5부 1180과 같음)")
man("FC Twente Enschede", "1993-94", 1624, "에레디비시 1993-94 5위")   # 기존 에레디비시 5위 값(트벤테 1994-95·아약스 1999-00)
man("Ajax Amsterdam", "1994-95", 1837, "에레디비시 1994-95 1위")       # 기존 에레디비시 1위 값(아약스 1995-96·1997-98)
man("SL Benfica", "1995-96", 1795, "포르투갈 1부 1995-96 2위")          # 기존 포르투갈 1부 18팀 시즌 2위 값
man("FC Girondins Bordeaux", "1995-96", 1638, "리그1 1995-96 16위 (추정, 다른 선수 자료 같은 시즌 15위 1655·17위 1621의 가운데)")
man("Dynamo Kyiv", "1994-95", 1640, "우크라이나 1994-95 1위 (추정, 다른 선수 자료 디나모 키이우 1997-98·1999-00 1위 1640과 같음)")
man("Lokomotiv Moskau", "1995-96", 1580, "러시아 1995 2위 (추정, 다른 선수 자료의 로코모티프 모스크바 2001 1580과 같음)")
man("Beşiktaş JK", "1997-98", 1620, "튀르키예 1997-98 6위 (추정, 다른 선수 자료의 갈라타사라이 2003-04 6위 1620과 같음)")
man("Helsingborgs IF", "2000-01", 1542, "스웨덴 2000 2위 (추정, 다른 선수 자료 스웨덴 1997 2위 1542와 같음)")

# ---------------------------------------------------------------- 상대 Elo
ELO_SRC = collections.Counter(); ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)
def opp_elo(opp, d, cid):
    k = key(opp); eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        c = collections.Counter((x["elo"], x["lv"]) for x in same)
        (e, lv), _ = c.most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted(c)))
        return e, lv
    y = int(d[:4]); ycal = str(y if int(d[5:7]) >= 7 else y - 1)   # 달력 연도 리그 팀(스웨덴·노르웨이·러시아): 7월 1일 기준 연도
    seasons = [eu, ycal] if cid in ("CL", "CLQ", "UEFA", "ITC") else [eu]
    for s in seasons:
        if (k, s) in TABLE:
            c = collections.Counter(TABLE[(k, s)])
            (e, lv), _ = c.most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(c)))
            return e, lv
    if (k, eu) in MAN:
        e, lv = MAN[(k, eu)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", []))
        return e, lv
    res = model(cid, d, opp)
    if res:
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model", [])); return res
    return None

# ---------------------------------------------------------------- 출전
def ldate(g): return g["date_local_computed"]   # 리포트가 있는 경기는 모두 리포트 날짜와 같음
def opp_name(g): return g["opponent"].strip()
M = []
for g in GAMES:
    M.append([ldate(g), opp_name(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])
for g in GAMES:
    if club_of(ldate(g)) != CLUB_KEY[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 골·도움
MIN_FIX = {("16601", "59"): 58}   # 1994.5.3 뉘른베르크 재경기 두 번째 골: DFB 데이터센터 58분(TM 59분) — judgments.md 4절
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0
rows, judg = [], []; missing = set(); EXCL_CNT = collections.Counter(); EXCL_A = []
def add_row(typ, mi, dm, gf, ga, pk, note, tie, comp, ko, d, opp, cid, et):
    res = opp_elo(opp, d, cid)
    if res is None: missing.add((opp, season_eu(d), cid, d)); res = (0, "?")
    row = [typ, opp, res[0], comp, mi, gf, ga, ko, pk, d, et, dm, res[1], note]
    if tie: row.append(tie)
    rows.append(row)
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue   # 뛰지 않은 다른 차전
    if e["scholl_self_assist"] == "1":
        judg.append(("본인 PK 골의 본인 도움 제외", ldate(g), opp_name(g), e["minute"], e["assist_type"])); EXCL_CNT["본인 PK 골 본인 도움"] += 1
    isg, isa = e["scholl_scorer"] == "1", e["scholl_assist_other"] == "1"
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
    mi = MIN_FIX.get((gid, e["minute"]), mi)
    cid = g["competitionId"]; comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = opp_name(g)
    et = 1 if mi > 95 and g["gameState"] in ("extra_time", "penalty_shootout") else 0
    if mi > 95 and not et: sys.exit("95분 넘는 정규 골? " + gid)
    if isg:
        if e["own_goal"] == "1" or not ours: judg.append(("골 제외", d, opp, e["minute"], "자책골")); continue
        add_row("g", mi, dm, gf, ga, int(e["penalty"] == "1"), 0, tie, comp, ko, d, opp, cid, et)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        elif e["assist_type"] == "Deflected shot on goal": why = "굴절"
        if why:
            EXCL_CNT[why] += 1; EXCL_A.append((d, opp, e["minute"], e["scorer"], why))
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= "2014-08-01": sys.exit("2014.8 이후 도움 " + gid)
        if not e["assist_type"]: EXCL_CNT["유형 없음(넣음)"] += 1
        add_row("a", mi, dm, gf, ga, 0, e["scorer"], tie, comp, ko, d, opp, cid, et)
if missing:
    for x in sorted(missing, key=lambda x: x[3]): print("Elo 없음:", x)
    sys.exit(1)
rows.sort(key=lambda r: (r[9], r[4], 0 if r[0] == "g" else 1))
E = rows
# API 합계와 대조
for gid, g in G.items():
    ng = sum(1 for e in EVENTS if e["gameId"] == gid and e["scholl_scorer"] == "1" and e["own_goal"] != "1")
    if ng != int(g["goals"]): sys.exit("골 수 불일치 " + gid)

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, EXCL_CNT)
    for x in ELO_LOG: print(x)
    for j in judg: print(j)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
TRACKED = set(subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_all():
    out = {}
    for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
        b = os.path.basename(fn)
        if b in ("scl.js", "hon.js") or "src/data/" + b not in TRACKED: continue   # 병렬 판정 중인 새 파일은 보지 않음
        s = open(fn, encoding="utf-8").read()
        me = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S); mm = re.search(r"const (\w+)_M=(\[.*?\]);\n", s, re.S)
        if me and mm: out[b] = (json.loads(me.group(2)), json.loads(mm.group(2)))
    return out
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
    if a[7] != b[7] or ta != tb: diffs.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return diffs
OUR_NAMES = {"kscms": ["Karlsruher SC"], "bayms": ["FC Bayern Munich", "Bayern Munich", "Bayern München"]}
IS_ME = lambda s: isinstance(s, str) and norm(s) in ("mehmet scholl", "scholl")
CROSS = []
if __name__ == "__main__" and "--cross" in sys.argv:
    ALL = load_all()
    mdates = {m[0] for m in M}
    for fn, (ent, mm) in ALL.items():
        for r in E:
            for x in ent:
                if x[9] == r[9] and key(x[1]) == key(r[1]):
                    if r[0] == "a" and x[0] == "g" and abs(x[4] - r[4]) <= 2:
                        CROSS.append(("숄 도움↔" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, x) or "같음"))
                    if r[0] == "g" and x[0] == "a" and IS_ME(x[13]) and abs(x[4] - r[4]) <= 2:
                        CROSS.append((fn + " 도움→숄 골", r[9], r[4], cmp_rows(r, x) or "같음"))
        for x in ent:
            if x[0] == "a" and IS_ME(x[13]) and not any(r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append((fn + " 도움→숄 골인데 내 자료에 없음", x[9], x[4], x[1]))
        # 숄 도움으로 그 선수 골이 났는데 그 선수 자료에 골이 없는 경우(득점자 이름은 대조표에서 확인)
        for x in ent:
            if x[9] in mdates:
                for r in E:
                    if r[9] == x[9] and key(r[1]) == key(x[1]):
                        dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                        if dd: CROSS.append(("같은 경기 다름", fn, r[9], r[1], dd))
                        break
        for x in ent:   # 상대편 같은 경기: 골 순서·스코어
            for r in E:
                if r[9] == x[9] and key(x[1]) in {key(c) for c in OUR_NAMES[club_of(r[9])]}:
                    CROSS.append(("상대편 같은 경기", fn, r[9], r[0], r[4], f"{r[5]}-{r[6]}", "|", x[0], x[4], f"{x[5]}-{x[6]}", x[3], r[3]))
        for x in mm:
            for m in M:
                if m[0] == x[0] and key(m[1]) == key(x[1]) and m[2] != x[2]:
                    CROSS.append(("같은 경기 대회 코드 다름(출전)", fn, m[0], m[1], m[2], x[2]))
                if m[0] == x[0] and key(x[1]) in {key(c) for c in OUR_NAMES[club_of(m[0])]} and m[2] != x[2]:
                    CROSS.append(("상대편 출전 대회 코드 다름", fn, m[0], m[1], m[2], x[2]))
    for c in CROSS: print(c)

# ---------------------------------------------------------------- 클럽별 합계
CLUB_KO = {k: n for k, u, n, s, y in CLUBS}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, *_ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E); MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["scholl_assist_other"] == "1")
N_BLANK = EXCL_CNT["유형 없음(넣음)"]
RES = [r for r in csv.DictReader(open(os.path.join(RAW, "youth_reserve_games.csv"), encoding="utf-8"))]
SRC = ELO_SRC
NOTE_LINES = [
    f"메멧 숄(카를스루에 SC·바이에른 뮌헨)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 쾰른전 ~ {d_(M[-1][0])} 마인츠전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·2군 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분("
    + ", ".join(f"{CLUB_KO[k]} {v[3]:,}분" for k, v in ST.items()) + ")",
    "출처: 경기 목록·출전 분(연장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트(골·도움이 나온 경기와 리그 밖 경기 전부). FotMob에는 이 선수 자료가 없어(검색 결과 없음, 2010년 이전 경기도 없음) Transfermarkt가 경기별 유일한 출처이고, 경기 수·골은 영어·독일어 위키백과 클럽·시즌별 기록과 대조함(바이에른 469경기 117골, 카를스루에 리그·컵 61경기 12골로 같음). 출전 분이 없어 90분으로 추정한 경기는 없음",
    "넣은 기록: 카를스루에 1990년 7월 인터토토컵 조별 2경기(1990.7.11 한자 로스토크전 24분, 7.18 브뢴비전 45분, 골·도움 없음)는 위키백과 시즌 기록에는 없지만 Transfermarkt 공식 경기라 넣음. 1994.8.7 DFB-슈퍼컵 브레멘전(연장 120분)도 넣음",
    "뺀 기록: 카를스루에 2군(오버리가 바덴뷔르템베르크·독일 아마추어 선수권) 12경기 5골, 바이에른 2군(레기오날리가 남부, 2003-04) 2경기, 카를스루에 U19 1경기는 2군·유스 경기라 넣지 않음. 대표팀 경기 제외",
    "몰수·무효 경기: 1995.4.15 프랑크푸르트 원정(경기장 결과 바이에른 5-2 승)은 바이에른이 아마추어 선수 4명을 내보내 프랑크푸르트 2-0 몰수승으로 바뀜. 숄은 90분 뛰었고 골·도움이 없어 출전만 넣음. 1994.4.23 뉘른베르크전(헬머의 '유령 골' 2-1)은 무효가 되어 재경기를 치렀으므로 기록에 없고, 1994.5.3 재경기(5-0, 숄 2골 2도움)만 셈",
    "골: 자책골은 셈하지 않음(1998.4.18 빌레펠트전 74분 숄의 자책골 제외). PK 골은 Transfermarkt 골 유형 'Penalty' 기준. 1994.5.3 뉘른베르크 재경기 두 번째 골은 DFB 데이터센터 58분(Transfermarkt 59분)을 씀. 승부차기 골은 셈하지 않음",
    f"도움: 모두 2014년 8월 전이라 Transfermarkt 리포트 도움 기준(다른 출처 없음). 도움 {NA} = Transfermarkt {N_TM_A} − PK 유도 {EXCL_CNT['PK 유도']}(1995.9.23 레버쿠젠전 클린스만, 1999.11.3 레인저스전 슈트룬츠, 2003.8.30 DFB-포칼 노인키르헨전 발라크) − 상대 자책골에 준 도움 {EXCL_CNT['상대 자책골에 준 도움']}(2002.5.4 로스토크전 39분 바움가르트 자책골). 1995.10.28 슈투트가르트전 본인 PK 골에 본인이 도움으로 적힌 것은 처음부터 도움으로 세지 않음. 넣은 도움 중 {N_BLANK}개(대부분 1990년대)는 Transfermarkt에 도움 유형이 비어 있어 PK 유도·리바운드·굴절 여부를 확인할 수 없음(일반 도움으로 넣음 — 다른 선수 선례). 1990년대 Transfermarkt 리포트는 골의 도움 칸이 빈 경우가 많아 도움이 실제보다 적을 수 있음",
    "날짜는 현지 날짜(Transfermarkt 리포트 날짜와 같음)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(엘베르·발라크·피사로·마카이·제 호베르투) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 직접 추정, 그 시즌 최종 순위를 리그 순위값에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 직접 추정 {SRC['직접 추정']}, 순위표+순위값 {SRC['순위표+리그 모형']})",
    "리그 순위값: 분데스리가는 다른 선수 자료의 순위값(모든 시즌 같은 표), 순위는 공식 최종 순위(1989-90~1994-95는 승리 2점제; Transfermarkt 표 순서와 영어 위키백과 최종 순위표가 모두 같음). 1991-92는 20팀 시즌이라 18팀 순위값을 상대 위치로 보간한 추정(도르트문트 2위 1922, 쾰른 4위 1838, 카이저슬라우테른 5위 1819, 뉘른베르크 7위 1790, 바이에른 10위 1736, 함부르크 12위 1715, 묀헨글라트바흐 13위 1705, 슈투트가르터 키커스 17위 1656, 로스토크 18위 1642, 뒤셀도르프 20위 1613)",
    "직접 추정(모두 '추정'): 디나모 키이우 1994-95(우크라이나 1위) 1640, 로코모티프 모스크바 1995(러시아 2위) 1580, 보르도 1995-96(리그1 16위) 1638, 베식타시 1997-98(튀르키예 6위) 1620, 헬싱보리 2000(스웨덴 2위) 1542 — 모두 다른 선수 자료의 비슷한 순위 값. 하부 리그 DFB-포칼 상대: 로트바이스 에센 1991-92(3부 오버리가 노르트라인 2위)·테니스 보루시아 베를린 1996-97(3부 레기오날리가 6위)·오스나브뤼크 2001-02(3부 레기오날리가 7위) 1450, 쇤베르크 95 2000-01(4부 오버리가 3위)·노이루핀 2005-06(4부 오버리가 2위) 1300, 푈프케 2004-05(5부 페어반츠리가, 순위 미확인) 1180. 트벤테 1993-94(에레디비시 5위 1624)·아약스 1994-95(1위 1837)·벤피카 1995-96(포르투갈 2위 1795)은 다른 선수 자료의 같은 순위 값. 예테보리 1994·1997, 로센보리 1999·2000, 스파르타크 모스크바 2000 등 달력 연도 리그 팀은 그해 값",
    "대회 비중: DFB-포칼은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), DFB-리가포칼은 첫 경기·준결승·결승을 국내컵 8강·준결승·결승으로, DFB-슈퍼컵은 국내컵 결승으로 계산함. 옛 인터토토컵 조별과 UEFA컵 1라운드는 유로파 예선, UEFA컵 2·3라운드·8강은 유로파 토너먼트, 1996 UEFA컵 결승(두 경기)은 결승으로, 챔스 2차 조별(1999-00·2000-01)은 조별로 계산함",
    f"두 경기 합산(UEFA 대회) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음). 숄이 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 두 클럽 모두 7월 10일 기준(1990.7 인터토토컵, 1997~2003년 7월 리가포칼, 2001.7.28 리그 개막전이 새 시즌). 클럽 구분은 1992.7.1 전 카를스루에, 이후 바이에른",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 챔피언스리그 2000-01, UEFA컵 1995-96, 분데스리가 8회, DFB-포칼 5회, DFB-리가포칼 3회(Transfermarkt 표기 1998·2000·2001). 준우승 챔피언스리그·DFB-포칼 1998-99. 분데스리가 준우승은 뺌",
    "은퇴. 마지막 경기 2007.5.19 마인츠전(바이에른)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM "]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []; seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6], r[13])
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
mmap = {m[0]: m for m in M}
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    m = mmap[r[9]]
    if key(m[1]) != key(r[1]) or m[2] != r[3]: problems.append(("상대/대회 M 불일치", r[9], m, r[1], r[3]))
    if r[4] > m[3] + 60 and m[3] < 90: pass
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const SCL_E={J(E)};\nconst SCL_M={J(M)};\nconst SCL_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "excluded_assists": EXCL_A,
               "elo_sources": ELO_SRC, "elo_log": ELO_LOG, "club_totals": ST},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}/{NTIEG} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
