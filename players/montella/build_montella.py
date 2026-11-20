#!/usr/bin/env python3
"""Vincenzo Montella: raw/ -> montella.json + src/data/mnt.js (판정 근거는 judgments.md)

  python3 players/montella/build_montella.py            # 파일 쓰기
  python3 players/montella/build_montella.py --debug    # Elo 출처 목록
  python3 players/montella/build_montella.py --cross    # 같은 경기 다른 선수 자료 대조

입력: raw/tm_games.csv(출전), raw/montella_goals.csv(골: Transfermarkt 리포트 분·골 전 스코어, 리포트가 없으면
      이탈리아어 위키백과 시즌 문서 분·골 전 스코어), raw/tm_events.csv·tm_match_info.csv(리포트 도움),
      raw/wiki_goals.csv(리포트 없는 도움의 득점자·분), raw/tm_two_leg_ties.csv, raw/ranks*.txt(순위표),
      src/data/*.js(같은 경기·같은 팀-시즌 값, 동료 대조), tools/league_rank_apply.py(라벨 → Elo, v1.226 순위 규칙).
바조 build 스크립트(같은 수집 형식)를 바탕으로 함.
"""
import csv, json, os, re, sys, unicodedata, collections, io, contextlib, subprocess
from datetime import date as Date, datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
OUT_JS = os.path.join(ROOT, "src", "data", "mnt.js")
OUT_JSON = os.path.join(HERE, "montella.json")
MYFILE = "mnt.js"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
GOALS = rd("montella_goals.csv")
WGOALS = rd("wiki_goals.csv")
WMAP = {r["tm_gameId"]: r for r in rd("tm_wiki_game_map.csv")}

# ---------------------------------------------------------------- 판정 표 (judgments.md)
MIN_FIX = {}
# 골 고침: gameId|골 번호 -> (분, 표시 분, 골 전 우리, 상대, PK)
GOAL_FIX = {
    # 1998.7.18 인터토토 3라운드 1차전 하렐베커 0-1 삼프도리아: TM 골 1(PK)·리포트 없음, 이탈리아어 위키는 0-0으로 잘못 적음.
    # 영어 위키백과 1998-99 삼프도리아 시즌 문서(UEFA 경기 기록 링크)·RSSSF 인터토토 1998(0-1) → 89분 PK, 0-0에서
    "2233654|1": (89, 0, 0, 0, 1),
}
# 위키 시즌 문서에만 있는 골(경기는 TM 출전): (gameId, 분, 표시 분, 골 전 우리, 상대, PK)
EXTRA_G = [
    # 1992.9.13 세리에C1 엠폴리 3-1 키에보: TM 66분 출전·골 0, 이탈리아어 위키 시즌 문서 'Montella 37'(페로티 55 PK·카스텔리 90+2),
    # national-football-teams 1992-93 13경기 5골(= TM 4 + 이 골; 위키 경력표 6골은 무효 처리된 아레초전 1골 포함)
    ("2944977", 37, 0, 0, 0, 0),
]
# 도움 제외: gameId|분 -> 이유
EXCL_A = {
    "1133192|90+3": "슈팅 리바운드(Shot on goal, 마르코스 아순상 탭인)",
    "1019553|27": "슈팅 리바운드(Shot on goal, 토티)",
    "65207|54": "슈팅 리바운드(Shot on goal, 알레안드로 로시)",
}
# 리포트 없는 도움(TM 선수 경기 성적 도움 수만 있음): 출전 시간 안에 팀의 몬텔라 외 골이 하나뿐이라 득점자가 정해지는 것만
# gameId -> (위키 득점자 이름, 분, 표시 분, 득점자 전체 이름)
ADD_A = {
    "2214994": ("R. Mancini", 1, 0, "Roberto Mancini"),        # 1997.2.2 밀란 2-3 삼프: 선발 24분 출전, 그 사이 골은 만치니 1분뿐
    "2215036": ("Carparelli", 8, 0, "Marco Carparelli"),       # 1997.3.16 레지아나 3-0: 다른 골은 몬텔라 5·68 PK
    "2214769": ("Laigle", 93, "90+3", "Pierre Laigle"),        # 1998.4.11 엠폴리 3-0: 몬텔라 41·85, 레글 90+3
    "2233655": ("F. Palmieri", 32, 0, "Francesco Palmieri"),   # 1998.7.25 인터토토 하렐베커 3-0: 몬텔라 36·84 PK
    "2233651": ("F. Palmieri", 26, 0, "Francesco Palmieri"),   # 1998.8.5 인터토토 준결승 2차전 볼로냐 1-0
    "2214440": ("Ortega", 69, 0, "Ariel Ortega"),              # 1999.3.21 인테르 4-0: 몬텔라 12·52 PK·66, 오르테가 69(75분 교체 전)
    "2214509": ("Doriva", 32, 0, "Doriva"),                    # 1999.5.23 바리 1-0
}
# 득점자를 정할 수 없어 넣지 않은 도움(리포트 없음, 후보 골이 둘 이상) — NOTE·judgments.md 4절
UNRESOLVED_A = {
    "2428233": "1997.9.24 코파 이탈리아 토리노전(3-1, 토발리에리 33·35·67)",
    "2214799": "1998.5.3 파르마전(2-2, 파코 66·보고시안 87)",
    "2214401": "1999.2.21 피아첸차전(3-2, 레글 34·오르테가 57)",
    "938540": "1999.9.16 UEFA컵 비토리아 세투발전(7-0, 74분 출전 중 다섯 골)",
    "2428127": "1999.12.14 코파 이탈리아 피아첸차전(0-3 연장, 리날디 55·디 프란체스코 113·칸델라 118)",
    "49887": "2006.2.23 UEFA컵 클뤼프 브뤼허전(2-1, 만치니 55·보보 71)",
    "66822": "2007.1.27 FA컵 스토크전(3-0, 맥브라이드 39·라진스키 54)",
}

# ---------------------------------------------------------------- 날짜
def sched_date(s):
    return datetime.strptime(s.split(" ")[1], "%d/%m/%Y").strftime("%Y-%m-%d") if s else ""
TZ = {"GB1": "Europe/London", "FAC": "Europe/London"}
def ldate(g):
    d = g["date_local_tm_report"] or sched_date(g["date_tm_schedule"])
    if d: return d
    u = datetime.fromisoformat(g["date_utc"])
    return u.astimezone(ZoneInfo(TZ.get(g["competitionId"], "Europe/Rome"))).strftime("%Y-%m-%d")

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "IT3A", "IT3B", "IT3O", "GB1"}
# 리포트·일정이 없어 라운드 이름이 없는 경기: gameId -> (코드, 차전 0/1/2)
MAN_ROUND = {
    "2838629": ("dc", 0),   # 1992.8.23 코파 이탈리아 1라운드 바리(단판)
    "2815977": ("dc", 0),   # 1995.8.20 코파 1라운드 괄도(단판)
    "2815993": ("dc", 0),   # 1995.8.30 코파 2라운드 우디네세(단판)
    "2428373": ("dc", 1), "2428388": ("dc", 2),   # 1996-97 코파 2라운드 제노아(두 경기)
    "2428216": ("dc", 1), "2428233": ("dc", 2),   # 1997-98 코파 2라운드 토리노
    "2267001": ("elq", 1), "2267002": ("elq", 2), # 1997-98 UEFA컵 1라운드 아틀레틱
    "2234396": ("elq", 1), "2234397": ("elq", 2), # 1998 인터토토 2라운드 림바프스카 소보타
    "2233654": ("elq", 1), "2233655": ("elq", 2), # 1998 인터토토 3라운드 하렐베커
    "2233650": ("elq", 1), "2233651": ("elq", 2), # 1998 인터토토 준결승 볼로냐
    "2428147": ("dc", 1),   # 1998-99 코파 32강 1차전 베로나(2차전 결장)
    "66792": ("dc", 0), "66811": ("dc", 0), "66822": ("dc", 0),   # FA컵 3라운드·재경기·4라운드
}
# 리포트 없는 두 경기 합산의 다른 차전 스코어(우리-상대; 이탈리아어 위키 시즌 문서, RSSSF)
MAN_OTHER = {
    "2428388": (2, 2),   # 1차전 제노아 2-2 삼프도리아
    "2428233": (1, 2),   # 1차전 토리노 2-1 삼프도리아
    "2267002": (1, 2),
    "2234397": (2, 0),
    "2233655": (1, 0),   # 1차전 하렐베커 0-1 삼프도리아
    "2233651": (1, 3),   # 1차전 볼로냐 3-1 삼프도리아
    "938589": (7, 0),
    "2428127": (0, 1),   # 1차전 로마 0-1 피아첸차
    "49887": (2, 1),     # 1차전 브뤼허 1-2 로마
    "2366697": (2, 1),   # 1차전 트리에스티나 1-2 로마
    "81186": (1, 0),     # 1차전 하이두크 0-1 삼프도리아
    "76214": (1, 0),
}

def comp_of(g):
    gid, cid, r = g["gameId"], g["competitionId"], g["round"].lower()
    if gid in MAN_ROUND: return MAN_ROUND[gid][0]
    if cid in LEAGUE: return "lg"     # 세리에C1 플레이아웃(IT3O)도 리그(바조 ITPO 선례)
    if cid == "CIT":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "SCI": return "df"
    if cid == "FAC":
        return "dc"   # 5라운드(8강 전)
    if cid in ("UI", "UEQ"): return "elq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        return "clk"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + r)

def leg_of(g):
    if g["gameId"] in MAN_ROUND: return MAN_ROUND[g["gameId"]][1]
    r = g["round"].lower()
    if "leg" not in r: return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def tie_of(g):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]
    home = int(g["venue"] == "H")
    fu = ft = 0
    if leg == 2:
        if gid in MAN_OTHER:
            fu, ft = MAN_OTHER[gid]
        else:
            o = INFO[TIES_RAW[gid]["other_leg_id"]]
            oh, oa = map(int, o["final"].split(" ")[0].split(":"))
            if o["home_id"] == g["club_id"]: fu, ft = oh, oa
            elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
            else: sys.exit("다른 차전 팀 불일치 " + gid)
            if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    return [leg, home, fu, ft, 1, 1]   # UEFA 대회·인터토토·코파 이탈리아(2021-22까지): 원정 다득점·연장

# ---------------------------------------------------------------- 이름 정규화
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

ALIAS = {}
with open(os.path.join(ROOT, "elo", "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
MANUAL_ALIAS = {"inter milan": "inter", "ac parma": "parma", "parma calcio 1913": "parma", "parma fc": "parma",
                "brescia calcio": "brescia calcio", "fc internazionale": "inter"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

# ---------------------------------------------------------------- 다른 선수 자료(git 추적 파일만)
def tracked():
    try:
        out = subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split()
        s = {os.path.basename(x) for x in out}
        if s: return s
    except Exception: pass
    return None
TRACKED = tracked()
def load_js(fn, P, part="E"):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + "_" + part + r"=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
OTHERS = {}
for fn in sorted(os.listdir(os.path.join(ROOT, "src", "data"))):
    if not fn.endswith(".js") or fn in ("hon.js", "clubcolors.js", "finals.js", MYFILE): continue
    if TRACKED is not None and fn not in TRACKED: continue
    try: OTHERS[fn] = load_js(fn, fn[:-3].upper())
    except Exception: continue
ENTS = [dict(p=fn, opp=r[1], elo=r[2], date=r[9], lv=r[12], comp=r[3]) for fn, ent in OTHERS.items() for r in ent]

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

SEAS_PAT = re.compile(r"(\d{4}-\d{2}|\d{4})")
TABLE = collections.defaultdict(collections.Counter)
for e in ENTS:
    lv = str(e["lv"] or "")
    m = SEAS_PAT.search(lv.split(" (")[0])
    if not m or not re.search(r"\d+위", lv.split(" (")[0]): continue
    TABLE[(key(e["opp"]), m.group(1))][(e["elo"], lv)] += 1

# ---------------------------------------------------------------- 순위 라벨 → Elo
_RA = {"__file__": os.path.join(ROOT, "tools", "league_rank_apply.py"), "__name__": "x"}
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_RA["__file__"], encoding="utf-8").read().split("if __name__ == '__main__':")[0], "rank", "exec"), _RA)
sys.argv = _argv
def label_value(lv, d):
    p = _RA["parse"](lv, d)
    return _RA["value"](*p) if p else None

# Transfermarkt 순위표(클럽 id): (코드, 시즌) -> {id: (순위, 팀 수, 이름)}
RANK_ID = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks_tm_ids.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league" or not p[5]: continue
        RANK_ID[(p[0], p[1])][p[5]] = (int(p[2]), int(p[3]), p[4])
# 이탈리아어·영어 위키백과 순위표(세리에C1 공식 최종 순위 등): (리그, 시즌) -> {이름: (순위, 팀 수)}
RANK_X = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks_extra.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        lg = p[0].split(" (")[0]
        RANK_X[(lg, p[1].split(" ")[0])][p[4]] = (int(p[2]), int(p[3]))
# 세리에C1 상대(Transfermarkt id) -> 이탈리아어 위키 순위표 이름
C1_NAME = {"4255": "Arezzo", "3522": "Spezia", "4147": "Casale", "4552": "Palazzolo", "2254": "Pro Sesto",
           "7030": "Vis Pesaro", "4271": "Triestina", "862": "Chievo", "2721": "Alessandria", "6089": "Casarano",
           "4086": "Lodigiani", "5543": "Chieti", "1386": "Reggina", "5585": "Barletta", "5587": "Juventus Stabia (1953-1996)",
           "4090": "Gualdo", "14888": "Pontedera", "4087": "Atletico Catania", "38991": "Nola", "4331": "Trapani",
           "1387": "Siena", "4361": "Varese"}
# 순위표 파일에 없는 상대(judgments.md 6절)
MAN_LV = {
    # 1998.7.18·25 인터토토: 벨기에 1998-99 시즌 개막(8월) 전 → 끝난 1997-98 시즌 최종 순위(영어 위키백과 1997-98 Belgian First Division)
    ("2478", "1998-99"): "벨기에 1부 1997-98 5위/18팀 (Belgian First Division)",
}
TMNAME = {"2478": "KRC Harelbeke"}

ELO_SRC = collections.Counter()
ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def rank_label(oid, d, cid):
    eu = season_eu(d)
    if (oid, eu) in MAN_LV: return MAN_LV[(oid, eu)]
    # 세리에C1: 이탈리아어 위키 공식 최종 순위(1992-93 A조는 아레초 제외 17팀)
    if oid in C1_NAME:
        for gr in ("A", "B"):
            t = RANK_X.get((f"Serie C1 Girone {gr}", eu))
            if t and C1_NAME[oid] in t:
                r, n = t[C1_NAME[oid]]
                return f"이탈리아 3부 {eu} {r}위/{n}팀 (Serie C1 Girone {gr}, 리그 수준 추정)"
    for code in ("IT1", "IT2", "GB1", "GB2", "PO1", "BU1"):
        t = RANK_ID.get((code, eu))
        if t and oid in t:
            r, n, _ = t[oid]
            y = int(eu[:4]) + 1
            dfl = lambda lg: "" if n == _RA["ERA"]["teams"](lg, y) else f"/{n}팀"
            if code == "IT1": return f"세리에A {eu} {r}위" + dfl("세리에A")
            if code == "IT2": return f"세리에B {eu} {r}위/{n}팀"
            if code == "GB1": return f"프리미어리그 {eu} {r}위" + dfl("프리미어리그")
            if code == "GB2": return f"챔피언십 {eu} {r}위/{n}팀"
            if code == "PO1": return f"포르투갈 1부 {eu} {r}위" + dfl("포르투갈 1부")
            if code == "BU1": return f"불가리아 1부 {eu} {r}위/{n}팀 (A Group)"
    t = RANK_X.get(("SE1 Allsvenskan", d[:4]))
    if t and oid == "801" and "IFK Göteborg" in t:
        r, n = t["IFK Göteborg"]; return f"스웨덴 1부 {d[:4]} {r}위/{n}팀 (Allsvenskan)"
    return None

def opp_elo(g, opp, d):
    k = key(opp); cid = g["competitionId"]
    eu = season_eu(d)
    same = [x for x in ENTS if abs((Date.fromisoformat(x["date"]) - Date.fromisoformat(d)).days) <= 1
            and (key(x["opp"]) == k or _sub(key(x["opp"]), k))]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same}))))
        return e, lv
    lab = rank_label(g["opponent_id"], d, cid)
    seasons = [eu, d[:4]] if cid in ("CL", "UEFA", "UI", "UEQ") else [eu]
    if lab and lab.startswith("벨기에 1부 1997-98"): seasons = ["1997-98"]
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = TABLE[(k, s)].most_common(1)[0]
            ELO_SRC["같은 팀·시즌 다른 선수 자료"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s + " | label " + str(lab)))
            return e, lv
    if lab:
        ELO_SRC["순위표 라벨"] += 1; ELO_LOG.append((d, opp, None, lab, "rank"))
        return None, lab
    return None

# ---------------------------------------------------------------- 출전
def clean_opp(g):
    o = re.sub(r"\s*\[name from[^\]]*\]", "", g["opponent"]).strip()
    o = re.sub(r"\s*\(- ?\d{4}\)\s*$", "", o).strip()
    if g["opponent_id"] in TMNAME: return TMNAME[g["opponent_id"]]
    if "[name from" in g["opponent"]:
        # 일정·리포트가 없어 Transfermarkt 현재 클럽 이름 → 그 시즌 Transfermarkt 순위표 이름
        for (code, s), t in RANK_ID.items():
            if s == season_eu(ldate(g)) and g["opponent_id"] in t:
                return t[g["opponent_id"]][2]
    return o

M = []
for g in GAMES:
    M.append([ldate(g), clean_opp(g), comp_of(g), MIN_FIX.get(g["gameId"], int(g["playedMinutes"]))])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
missing_elo = set()
def add_row(typ, mi, dm, gf, ga, pk, note, g):
    d = ldate(g); opp = clean_opp(g)
    res = opp_elo(g, opp, d)
    if res is None:
        missing_elo.add((opp, d, g["competitionId"])); res = (0, "?")
    elo, lv = res
    v = label_value(lv, d) if lv != "?" else None
    if v is not None:
        if elo is not None and elo != v: judg.append(("Elo 라벨값으로 맞춤", d, opp, elo, v, lv))
        elo = v
    if elo is None:
        missing_elo.add((opp, d, g["competitionId"], lv)); elo = 0
    et = int(mi > 90 and (not dm or int(str(dm).split("+")[0]) >= 105))
    row = [typ, opp, elo, comp_of(g), mi, gf, ga, ko_of(g), pk, d, et, dm, lv, note]
    tie = tie_of(g)
    if tie: row.append(tie)
    rows.append(row)

def ours(g, sh_sa):
    h, a = map(int, sh_sa.split("-"))
    return (h, a) if g["venue"] == "H" else (a, h)

GOAL_SRC = collections.Counter()
per_game_g = collections.Counter(); per_game_pk = collections.Counter()
for r in GOALS:
    gid = r["tm_gameId"]; g = G[gid]
    if gid == "2944977": continue   # 키에보전: TM 골 0(위키 골은 EXTRA_G)
    tag = f"{gid}|{r['goal_no']}"
    if tag in GOAL_FIX:
        mi, dm, gf, ga, pk = GOAL_FIX[tag]; GOAL_SRC["고침"] += 1
    elif r["tm_minute"]:
        mi, dm = minute(r["tm_minute"]); gf, ga = ours(g, r["tm_score_before_home_away"]); pk = int(r["tm_penalty"] == "1")
        GOAL_SRC["TM 리포트"] += 1
    else:
        mi, dm = minute(r["wiki_minute"]); gf, ga = ours(g, r["wiki_score_before_home_away"]); pk = int(r["wiki_penalty"] == "1")
        GOAL_SRC["위키 시즌 문서"] += 1
    per_game_g[gid] += 1; per_game_pk[gid] += pk
    add_row("g", mi, dm, gf, ga, pk, 0, g)
for gid, mi, dm, gf, ga, pk in EXTRA_G:
    GOAL_SRC["위키만(추가)"] += 1
    add_row("g", mi, dm, gf, ga, pk, 0, G[gid])
# API 골·PK 수와 경기마다 대조
for gid, g in G.items():
    if int(g["goals"]) != per_game_g[gid] or int(g["penGoals"]) != per_game_pk[gid]:
        if gid != "2944977":
            sys.exit(f"골 수 불일치 {gid} API {g['goals']}/{g['penGoals']} 자료 {per_game_g[gid]}/{per_game_pk[gid]}")

# 리포트 도움
per_game_a = collections.Counter()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g or e["montella_assist_other"] != "1": continue
    tag = f"{gid}|{e['minute']}"
    per_game_a[gid] += 1
    if tag in EXCL_A:
        judg.append(("도움 제외", ldate(g), clean_opp(g), e["minute"], e["scorer"], EXCL_A[tag])); continue
    if e["own_goal"] == "1": sys.exit("자책골 도움 판정 누락 " + tag)
    if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal", "Deflected"): sys.exit("도움 유형 판정 누락 " + tag)
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    if side_home != our_home: sys.exit("상대 골 도움 " + tag)
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(e["minute"])
    add_row("a", mi, dm, gf, ga, 0, e["scorer"], g)
# 리포트 없는 도움: 위키 골 목록에서 득점자·분·골 전 스코어
for gid, (wname, mi, dm, full) in ADD_A.items():
    g = G[gid]; w = WMAP[gid]
    lst = [x for x in WGOALS if x["page"] == w["wiki_page"] and x["date"] == w["wiki_date"]]
    hit = [x for x in lst if x["scorer"] == wname and minute(x["minute"])[0] == mi]
    if len(hit) != 1: sys.exit("도움 득점자 못 찾음 " + gid)
    home_side = "home" if g["venue"] == "H" else "away"
    if hit[0]["side"] != home_side: sys.exit("도움 팀 이상 " + gid)
    gf = sum(1 for x in lst if x["side"] == home_side and minute(x["minute"])[0] < mi)
    ga = sum(1 for x in lst if x["side"] != home_side and minute(x["minute"])[0] < mi)
    per_game_a[gid] += 1
    add_row("a", mi, dm, gf, ga, 0, full, g)
for gid, g in G.items():
    if int(g["assists"]) != per_game_a[gid] and gid not in UNRESOLVED_A:
        sys.exit(f"도움 수 불일치 {gid} API {g['assists']} 자료 {per_game_a[gid]}")
    if gid in UNRESOLVED_A and (int(g["assists"]) != 1 or per_game_a[gid]): sys.exit("미해결 도움 이상 " + gid)

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

def sort_min(r):
    return r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5
rows.sort(key=lambda r: (r[9], sort_min(r), 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC, GOAL_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)
    for j in judg:
        if j[0].startswith("Elo"): print(j)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: diffs.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: diffs.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: diffs.append(f"lv {a[12]}/{b[12]}")
    if a[8] != b[8]: diffs.append(f"PK {a[8]}/{b[8]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None):
        diffs.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else '-'}/{b[7]},{b[14] if len(b) > 14 else '-'}")
    return diffs
CROSS, SAMEGAME = [], []
for fn, ent in OTHERS.items():
    for r in E:
        if r[0] != "a": continue
        hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1])]
        if hit: CROSS.append(("몬텔라 도움→" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:
        if x[0] == "a" and "montella" in norm(str(x[13])):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn + " 도움→몬텔라 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                SAMEGAME.append((fn, r[9], r[1], tuple(dd) or "같음"))
                break
SAMEGAME = sorted(set(SAMEGAME))
MCROSS = []
mby = {m[0]: m for m in M}
for fn in OTHERS:
    try: Mo = load_js(fn, fn[:-3].upper(), "M")
    except Exception: continue
    for x in Mo:
        m = mby.get(x[0])
        if m and key(m[1]) == key(x[1]) and m[2] != x[2]: MCROSS.append((fn, x[0], x[1], m[2], x[2]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS: print(c)
    for s_ in SAMEGAME:
        if s_[-1] != "같음": print("같은 경기 차이", s_)
    print("같은 경기", collections.Counter((s_[0], s_[-1] == "같음") for s_ in SAMEGAME))
    for x in MCROSS: print("출전 행 대회 차이", x)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("empmt", "1995-07-01"), ("genmt", "1996-07-01"), ("sammt", "1999-07-01"), ("rommt", "2007-01-04"),
         ("fulmt", "2007-07-12"), ("sammt", "2008-07-01"), ("rommt", None)]
TM_CLUB = {"749": "empmt", "252": "genmt", "1038": "sammt", "12": "rommt", "931": "fulmt"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
JUL1 = {"sammt"}
def season_of(d, club):
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    s = y if (m >= 8 or (club in JUL1 and m >= 7)) else y - 1
    return f"{s}-{str(s + 1)[2:]}"
for g in GAMES:
    c = club_of(ldate(g))
    if c != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
    s = season_of(ldate(g), c)
    if s[:4] != g["seasonId"]: sys.exit("시즌 불일치 " + g["gameId"] + " " + ldate(g) + " " + g["seasonId"])
PERIODS = [("엠폴리", "1990~1995", None, "1995-07-01"), ("제노아", "1995~1996", "1995-07-01", "1996-07-01"),
           ("삼프도리아", "1996~1999", "1996-07-01", "1999-07-01"), ("AS 로마", "1999~2007", "1999-07-01", "2007-01-04"),
           ("풀럼 임대", "2007", "2007-01-04", "2007-07-12"), ("삼프도리아 임대", "2007~2008", "2007-07-12", "2008-07-01"),
           ("AS 로마", "2008~2009", "2008-07-01", None)]
def per(lo, hi):
    inr = lambda d: (lo is None or d >= lo) and (hi is None or d < hi)
    return [sum(1 for m in M if inr(m[0])), sum(1 for r in E if r[0] == "g" and inr(r[9])),
            sum(1 for r in E if r[0] == "a" and inr(r[9])), sum(m[3] for m in M if inr(m[0]))]
ST = [(n, y, per(lo, hi)) for n, y, lo, hi in PERIODS]
CLUBTOT = collections.OrderedDict()
for n, y, v in ST:
    b = n.replace(" 임대", "")
    t = CLUBTOT.setdefault(b, [0, 0, 0, 0])
    for i in range(4): t[i] += v[i]

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
NWG = GOAL_SRC["위키 시즌 문서"] + GOAL_SRC["위키만(추가)"]
NOTE_LINES = [
    f"빈첸초 몬텔라(엠폴리·제노아·삼프도리아·AS 로마·풀럼)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 바레세전 ~ {d_(M[-1][0])} 카타니아전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·이탈리아 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n}({y}) {v[0]}·{v[1]}·{v[2]}" for n, y, v in ST)
    + f". 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분(교체·연장 반영)은 Transfermarkt 선수 경기 성적. 골 시각·골 전 스코어·PK·도움은 Transfermarkt 경기 리포트, 리포트를 받지 못한 경기(엠폴리·제노아 전부, 1996~99 삼프도리아 대부분 등)는 이탈리아어 위키백과 클럽 시즌 문서의 경기별 득점자·분(풀럼은 영어 위키백과 시즌 문서). "
    f"골 {NGo}개 중 {GOAL_SRC['TM 리포트']}개는 Transfermarkt 리포트, {NWG}개는 위키백과 시즌 문서 시각(Transfermarkt 리포트가 있는 골은 위키백과와 골 전 스코어가 모두 같고 시각 차이는 1분 차이 7개·2003.1.16 코파 이탈리아 비첸차전 29분/40분 1개, 모두 리포트 시각을 씀). 경기마다 골·PK 수는 Transfermarkt 선수 경기 성적과 같음. FotMob에는 이 시기 경기별 기록이 없음",
    "엠폴리(1990~1995)는 세리에C1(3부, 프로 리그) 시절이라 셈(1993-94는 리그 출전 없이 6월 세리에C1 플레이아웃 알레산드리아전 2경기만, 리그 경기로 셈). 1992-93: Transfermarkt는 리그 4골, 위키백과 경력표는 6골. 1992.9.13 키에보전(엠폴리 3-1) 골은 Transfermarkt에 없으나 이탈리아어 위키백과 시즌 문서에 몬텔라 37분 골(페로티 55분 PK·카스텔리 90+2분)이 있고 national-football-teams 시즌 기록(13경기 5골)과도 맞아 넣음. 나머지 1골은 1992.9.27 아레초 원정(3-1, 몬텔라 65분) 골인데, 아레초가 27라운드 뒤 리그에서 제외되며 그 경기 결과가 모두 무효 처리되어(Transfermarkt에도 경기 없음) 경기·골 모두 넣지 않음. 1992-93 코파 이탈리아 바리전(Transfermarkt만)은 Transfermarkt대로 넣음",
    "제노아(1995~1996, 세리에B): 앵글로-이탈리안컵 1995-96(위키백과 경력표 5경기 5골, 우승)은 Transfermarkt에 대회 자체가 없고 경기별 득점 기록도 결승(1996.3.17 웸블리 포트 베일전 5-2, 39분 골) 하나뿐이라 넣지 않음(바티스투타 자료와 같은 처리). 코파 이탈리아는 Transfermarkt 2경기(괄도전 2골·우디네세전), 위키백과는 1경기",
    "풀럼(2007, 임대): Transfermarkt 리그 10경기 2골·FA컵 4경기 3골(영어 위키백과 풀럼 시즌 문서와 같음; 위키백과 경력표의 리그 3골·FA컵 5경기와는 다름)",
    "삼프도리아: 1998.7.18 인터토토컵 3라운드 1차전 하렐베커 원정 골(0-1 승, 89분 PK)은 Transfermarkt 리포트가 없고 이탈리아어 위키백과 시즌 문서는 0-0으로 잘못 적어, 영어 위키백과 1998-99 삼프도리아 시즌 문서(UEFA 경기 기록 인용)의 89분 PK와 RSSSF 인터토토컵 1998 스코어(0-1, 0-3)로 넣음",
    "골: 자책골 없음. PK는 Transfermarkt 리포트 'Penalty', 리포트가 없으면 위키백과 시즌 문서의 PK 표시(경기마다 Transfermarkt PK 골 수와 같음)",
    f"도움: Transfermarkt 도움(2014년 이전이라 단일 출처; 위키백과·RSSSF·FotMob에 도움 기록 없음). Transfermarkt 47개 중 경기 리포트가 있는 33개는 리포트대로 넣되 슈팅 리바운드('Shot on goal') 3개(2001.9.29 유벤투스전 아순상, 2002.10.30 챔스 레알 마드리드전 토티, 2006.9.24 파르마전 로시)는 뺌. 리포트가 없어 경기별 도움 수만 있는 14개는 몬텔라의 출전 시간 안에 팀의 다른 골이 하나뿐인 7개만 그 골(위키백과 시즌 문서 득점자·분)로 넣고(1997.2.2 밀란전 만치니 1분, 1997.3.16 레지아나전 카르파렐리 8분, 1998.4.11 엠폴리전 레글 90+3분, 1998.7.25 인터토토 하렐베커전 팔미에리 32분, 1998.8.5 인터토토 볼로냐전 팔미에리 26분, 1999.3.21 인테르전 오르테가 69분, 1999.5.23 바리전 도리바 32분), 후보 골이 둘 이상인 7개는 득점자·시각을 정할 수 없어 뺌: " + "; ".join(UNRESOLVED_A.values()) + f". 결과 {NA}도움. 리포트 없는 7개는 도움 유형을 확인하지 못함",
    "출전 분: Transfermarkt 그대로(90분 추정 없음). 2004.9.15 챔스 디나모 키이우전은 전반 뒤 중단(몰수 0-3), 몬텔라 45분. 연장 경기: 1999.12.14 코파 이탈리아 피아첸차전(120분), 2002.12.17 코파 이탈리아 트리에스티나전(120분, 승부차기), 2005.3.16 코파 이탈리아 피오렌티나전(연장 98분 교체, 승부차기), 2009.3.11 챔스 16강 아스널전(연장 120+1분 교체 투입, 승부차기)",
    "날짜: Transfermarkt 경기 리포트·일정 날짜, 둘 다 없으면 선수 경기 성적의 킥오프 시각을 현지 시간으로 바꾼 날짜(22:00/23:00 UTC 자리값은 다음 날). 위키백과 시즌 문서와 하루 이틀 다른 경기 16개는 Transfermarkt(다른 선수 자료와 같음; 1999.12.9 뉴캐슬 원정은 위키백과 12.15가 틀림)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 상대 리그 최종 순위(Transfermarkt 순위표; 세리에C1은 이탈리아어 위키백과 최종 순위, 1992-93 A조는 아레초 제외 17팀; 스웨덴 1999·벨기에 1997-98은 영어 위키백과) 순으로 정하고, 순위가 있는 상대는 리그·시즌 기준 평균 + 순위 곡선 값(같은 리그·시즌·순위면 모든 선수 같은 값). 기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['같은 팀·시즌 다른 선수 자료']}, 순위표 {SRC['순위표 라벨']}. 세리에C1(3부) 상대는 리그 수준 추정 값. 1998년 7월 인터토토 하렐베커는 벨기에 1998-99 개막 전이라 1997-98 최종 순위(5위)",
    "대회 비중: 세리에C1 플레이아웃은 리그 경기, 코파 이탈리아는 1·2라운드·32강·16강 국내컵 앞 단계, 8강·준결승 가중, 수페르코파 이탈리아나는 국내컵 결승, FA컵 3~5라운드는 국내컵 앞 단계, 인터토토컵·UEFA컵 예선·UEFA컵 1라운드는 유로파 예선, UEFA컵 2라운드 이후(32강 포함)는 유로파 토너먼트, 챔스 조별·16강은 챔스 비중",
    f"두 경기 합산(UEFA 대회·인터토토·코파 이탈리아) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(원정 다득점·연장 있음). 몬텔라가 뛰지 않았거나 리포트가 없는 다른 차전 스코어는 Transfermarkt 리포트·이탈리아어 위키백과 시즌 문서·RSSSF로 채움",
    "시즌 구분: 8월 1일 기준, 삼프도리아는 7월 1일 기준(1998년 7월·2007년 7월 인터토토컵이 새 시즌). 클럽 구분은 1995.7.1 전 엠폴리, 1996.7.1 전 제노아, 1999.7.1 전 삼프도리아, 2007.1.4 전 로마, 2007.7.12 전 풀럼(임대), 2008.7.1 전 삼프도리아(임대), 이후 로마(Transfermarkt 이적일)",
    "우승: 세리에A 2000-01·수페르코파 이탈리아나 2001(로마), 앵글로-이탈리안컵 1995-96(제노아, 영어 위키백과). 개인 수상 없음(1995-96 세리에B 21골은 득점 2위). 준우승과 대표팀 기록(유로 2000 준우승)은 뺌",
    "은퇴: 2009년(마지막 경기 2009.5.16 로마 홈 카타니아전)",
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
    gs = sorted({(r[5], r[6], sort_min(r)) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
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
    if mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]: problems.append(("출전 행과 상대·대회 다름", r, mm[r[9]]))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const MNT_E={J(E)};\nconst MNT_M={J(M)};\nconst MNT_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
               "same_game": SAMEGAME, "elo_sources": ELO_SRC, "goal_sources": GOAL_SRC, "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)} · 골 {dict(GOAL_SRC)}")
    for n, y, v in ST: print(" ", n, y, v)
