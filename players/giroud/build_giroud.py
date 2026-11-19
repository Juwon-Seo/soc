#!/usr/bin/env python3
"""Olivier Giroud: raw/ -> giroud.json + src/data/gir.js (판정 근거는 judgments.md)

  python3 players/giroud/build_giroud.py            # 파일 쓰기
  python3 players/giroud/build_giroud.py --debug    # Elo 출처 목록
  python3 players/giroud/build_giroud.py --cross    # 같은 경기 다른 선수 자료 대조
  스크래치 복사본에서는 SOC_ROOT=<복사본>.

입력: raw/tm_games.csv(출전, date_local = 경기장 현지 날짜), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트),
      raw/tm_match_info.csv, raw/tm_two_leg_ties.csv, raw/ranks.txt(순위표), raw/giroud_assists_tm_vs_fotmob.csv,
      <ROOT>/elo/opponent_elo_by_team_season.csv·aliases.csv, <ROOT>/tools/league_rank_apply.py(새 팀-시즌의 순위 → Elo),
      src/data/*.js(git에 있는 기존 선수 파일만: 같은 경기 대조).
질라르디노 build 스크립트(같은 수집 형식)를 바탕으로 함.
"""
import csv, json, os, re, sys, unicodedata, collections, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "gir.js")
OUT_JSON = os.path.join(HERE, "giroud.json")
ME = "올리비에 지루"
MYFILE = "gir.js"

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

ALLGAMES = rd("tm_games.csv")
ISTRES = "2580"   # FC 이스트르 임대 2007-08: 프랑스 3부 나시오날(프로 리그 아님) → 리그·컵 모두 제외
EXCL_GAMES = [g for g in ALLGAMES if g["club_id"] == ISTRES]
GAMES = [g for g in ALLGAMES if g["club_id"] != ISTRES]
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
TIES_RAW = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}
AC = rd("giroud_assists_tm_vs_fotmob.csv")

# ---------------------------------------------------------------- 판정 표 (judgments.md)
EXCL_G = {}
# 도움 제외: gameId|TM 분 -> 이유
EXCL_A = {
    "1163649|51": "2012.3.11 캉전 51분 아이트파나 골: Transfermarkt 도움 유형 'Shot on goal'(슈팅 리바운드 탭인), FotMob 도움 없음",
    "1163731|42": "2012.5.1 에비앙전 42분 벨한다 PK 골: PK 유도(Transfermarkt 'Penalty: Fouled player')",
    "3184382|65": "2019.5.29 유로파 결승 아스널전 65분 아자르 PK 골: PK 유도(Transfermarkt 'Penalty: Fouled player'), FotMob 도움 없음",
    "3614523|17": "2022.1.6 로마전 17분 메시아스 골: Transfermarkt 'Shot on goal'(지루 슈팅이 막힌 리바운드), FotMob 도움 없음",
    "3844819|45+1": "2022.10.8 유벤투스전 45+1분 토모리 골: Transfermarkt 'Shot on goal', FotMob은 도움으로 셈. AC 밀란 공식 기사·더 내셔널(AP)·sportskeeda가 코너킥 뒤 지루의 슈팅(헤더)이 토모리 몸에 맞고 흐른 공을 토모리가 차 넣었다고 적음 → 슈팅 리바운드·굴절이라 도움 아님(사용자 규칙)",
    "2805648|20": "2017.3.7 챔스 16강 바이에른전 20분 월콧 골: 2014년 8월 뒤 Transfermarkt 단일 출처(FotMob 도움 없음). 스카이스포츠·스포츠몰 문자 중계·포포투 기사는 월콧이 수비 둘을 제치고 찼다고만 적고 도움자 없음 → 확인 못 해 뺌",
}
# 2014년 8월 뒤 단일 출처지만 다른 출처 2곳 이상으로 확인해 넣은 도움
SINGLE_KEEP = {
    "2527280|59": "2015.1.25 FA컵 4라운드 브라이턴전 59분 로시츠키 골: Transfermarkt 도움(Pass), FotMob 도움자 없음. "
                  "브라이턴 앤드 호브 뉴스 '지루가 로시츠키에게 공을 찔러 줌', 스포츠몰 문자 중계 '로시츠키의 리버스 패스를 지루가 되돌려 줌', "
                  "블리처 리포트 '로시츠키가 왼쪽의 지루에게 주고 돌려받아 마무리' → 넣음",
}
# FotMob에만 있는 지루 도움(넣지 않음)
FM_ONLY = [
    "2019.4.18 유로파 8강 2차전 슬라비아 프라하전 27분 페드로 골: FotMob만 지루 도움. ESPN 등 경기 기사는 지루의 슈팅을 골키퍼 콜라르가 막은 리바운드를 페드로가 넣었다고 적음 → 슈팅 리바운드라 도움 아님",
    "2023.11.7 챔스 조별 PSG전 12분 레앙 골: FotMob만 지루 도움(Transfermarkt 'Without assist'). 경기 기사(AC 밀란 공식·ESPN 등)는 돈나룸마가 지루 슈팅을 막은 뒤 떠오른 공을 레앙이 오버헤드킥으로 넣었다고 적음 → 슈팅 리바운드라 도움 아님",
]

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "FR2", "GB1", "IT1", "MLS1"}
CUPS = {"FRC", "FRL", "FAC", "CGB", "CIT", "MLSP"}
SUPER = {"GBCS", "SCI", "USC"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith(("quarter", "sixth round")): return "dk"   # FA컵 6라운드 = 8강
        return "dc"
    if cid in SUPER: return "df"
    if cid == "KLUB" or cid == "CWCQ": return "cwc"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith(("intermediate", "last 16", "quarter")): return "elk"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
    if cid == "POUS": return "mlp"          # MLS 컵 플레이오프 1라운드(3판 2선승)·서부 준결승: 단판
    if cid == "USMX": return "lck"          # 리그스컵 16강~결승(메시 2023 선례: 준결승·결승도 lck)
    if cid == "CCL":
        if r.startswith(("first round", "last 16")): return "ccc"
        if r.startswith("quarter"): return "ccck"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def leg_of(g):
    r = g["round"].lower()
    if "leg" not in r or g["competitionId"] == "POUS": return 0
    return 1 if "1st" in r else 2

def ko_of(g):
    if leg_of(g): return 0
    if g["competitionId"] in LEAGUE: return 0
    if g["round"].lower().startswith("group"): return 0   # 챔스·유로파 조별·리그 단계, 클럽 월드컵 2025 조별(리그식)
    return 1

def tie_of(g, d):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정 다득점, 연장]"""
    leg = leg_of(g)
    if not leg: return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        t = TIES_RAW[gid]
        o = INFO.get(t["other_leg_id"])
        if not o: sys.exit("다른 차전 리포트 없음 " + gid)
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
        if (o["home_id"] == g["club_id"]) == bool(home): sys.exit("합산 홈 판정 이상 " + gid)
    if cid in ("CL", "CLQ", "EL", "ELQ"): ag, et = int(d < "2021-07-01"), 1     # UEFA 원정 다득점 2020-21까지
    elif cid == "CGB": ag, et = (1, 1) if d < "2018-07-01" else (0, 0)          # 리그컵 준결승: 2018-19부터 승부차기만
    elif cid == "CIT": ag, et = int(d < "2022-07-01"), 1                        # 코파 이탈리아 준결승: 원정 다득점 2021-22까지
    elif cid == "CCL": ag, et = 1, 0                                            # 북중미 챔스: 원정 다득점, 연장 없이 승부차기(메시 2025 선례)
    else: sys.exit("합산 규칙 없음 " + cid)
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
MANUAL_ALIAS = {"inter milan": "inter", "esperance tunis": "esperance tunis"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = {}
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"] == ME: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE.setdefault((key(nm), r["시즌"]), (int(r["Elo"]), r["수준 라벨(lv)"]))

try:
    TRACKED = set(os.path.basename(x) for x in subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
except Exception:
    TRACKED = set()
if not TRACKED:
    TRACKED = set(os.path.basename(x) for x in subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(os.listdir(os.path.join(ROOT, "src", "data"))):
    if not fn.endswith(".js") or fn in ("hon.js", "clubcolors.js", MYFILE) or fn not in TRACKED: continue
    try: OTHERS[fn] = load_js(fn)
    except Exception: continue
SAME = collections.defaultdict(collections.Counter)
for fn, (P, oe, om) in OTHERS.items():
    for x in oe: SAME[x[9]][(key(x[1]), x[2], x[12])] += 1
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)

def _load_rank_tool():
    p = os.path.join(ROOT, "tools", "league_rank_apply.py")
    Gx = {"__file__": p, "__name__": "rank_tool"}
    argv = sys.argv; sys.argv = ["x"]
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(open(p, encoding="utf-8").read(), p, "exec"), Gx)
    sys.argv = argv
    return Gx
RT = _load_rank_tool()
def rank_value(lv, d):
    p = RT["parse"](lv, d)
    if not p: sys.exit("순위 라벨을 도구가 못 읽음: " + lv)
    v = RT["value"](*p)
    if v is None: sys.exit("기준 없음: " + lv)
    return v

JUL10_TM = {"1290", "3161", "969"}   # 그르노블·투르·몽펠리에: 7월 10일 기준(2006.7.28 리그2 개막전, 2010.7.29 유로파 예선)
def season_eu(d, club=None):
    y, m = int(d[:4]), int(d[5:7])
    if d[:7] == "2020-08": y -= 1          # 2020년 8월 경기(코로나 연기)는 2019-20
    s = y if (m >= 8 or (club in JUL10_TM and m == 7 and int(d[8:10]) >= 10)) else y - 1
    return f"{s}-{str(s + 1)[2:]}"

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league" or len(p) < 5: continue
        RANKS[(p[0].split("#")[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3].split(" ")[0]))

# 달력 연도 리그 상대(시즌 키 = 그 순위의 해)
CAL_SEASON = {   # (상대 키, 날짜 앞부분) -> 시즌
    "bate borisov": lambda d: d[:4],                 # 벨라루스(달력 연도): 2017.9·2018.10~11 경기
    "malmo ff": lambda d: d[:4],                     # 2019.2 유로파 32강: 같은 32강 1차전(2019.2.14)을 다룬 다른 선수 자료가 '스웨덴 1부 2019 2위'를 써서 그 값에 맞춤
    "sk brann": lambda d: d[:4], "fk bodo glimt": lambda d: d[:4], "cr flamengo": lambda d: d[:4],
}
US_COMPS = {"MLS1", "POUS", "USMX", "MLSP", "CCL"}

# 새 팀-시즌(통합표에 없음) 라벨
NEWLAB = {
    "FR2": lambda s, r, n: f"리그2 {s} {r}위/{n}팀",
    "FR3": lambda s, r, n: f"프랑스 3부 {s} {r}위/{n}팀 (Championnat National, 리그 수준 추정)",
    "GB2": lambda s, r, n: f"챔피언십 {s} {r}위/{n}팀",
    "UNG1": lambda s, r, n: f"헝가리 1부 {s} {r}위/{n}팀 (Nemzeti Bajnokság I)",
    "WER1": lambda s, r, n: f"벨라루스 1부 {s} {r}위/{n}팀 (Belarusian Premier League)",
    "SE1": lambda s, r, n: f"스웨덴 1부 {s} {r}위/{n}팀 (Allsvenskan)",
    "NO1": lambda s, r, n: f"노르웨이 1부 {s} {r}위/{n}팀 (Eliteserien)",
    "SER1": lambda s, r, n: f"세르비아 1부 {s} {r}위/{n}팀 (Serbian SuperLiga, 플레이오프·스플릿 뒤 최종 순위)",
}
# 순위표 파일 밖에서 정한 새 팀-시즌(근거는 judgments.md): (상대 키, 시즌) -> 라벨
MANUAL_LV = {
    ("us marseille endoume", "2006-07"): "프랑스 4부 2006-07 18위/18팀 (CFA Groupe B, 리그 수준 추정)",
    ("fc montceau bourgogne", "2009-10"): "프랑스 4부 2009-10 11위/18팀 (CFA Groupe B, 리그 수준 추정)",
    ("us lusitanos saint maur", "2025-26"): "프랑스 4부 2025-26 3위/16팀 (Championnat National 2 Groupe C, 리그 수준 추정)",
    ("bsc young boys", "2025-26"): "스위스 1부 2025-26 6위/12팀 (Swiss Super League, 플레이오프·스플릿 뒤 최종 순위)",
    ("seattle sounders fc", "2024"): "MLS 2024 7위/29팀",
    ("san jose earthquakes", "2024"): "MLS 2024 29위/29팀",
    ("cf america", "2024-25"): "멕시코 1부 2024-25 4위/18팀 (Liga MX, 연간 합산 순위)",
    ("esperance tunis", "2024-25"): "튀니지 1부 2024-25 1위/16팀 (Tunisian Ligue Professionnelle 1, 리그 수준 추정)",
}
# 순위를 찾지 못한 상대: (상대 키, 시즌) -> 라벨(값은 그 단계 기준점)
NORANK = {
    ("ss jeanne d arc", "2008-09"): ("프랑스 6부 2008-09 순위 없음 (Championnat de La Réunion D1; 리그 수준 추정)", ("France", 6, 2009, False)),
}

def opp_season(g, d):
    k = key(oname(g)); cid = g["competitionId"]
    if cid in US_COMPS: return d[:4]
    for kk, f in CAL_SEASON.items():
        if k == key(kk) or norm(oname(g)) == kk: return f(d)
    return season_eu(d, g["club_id"])

ELO_SRC = collections.Counter()
ELO_LOG = []
NEW_TS = {}
def opp_elo(g, d):
    opp = oname(g); k = key(opp)
    same = [(kk, e, lv) for (kk, e, lv), c in SAME.get(d, {}).items() for _ in range(c) if kk == k or _sub(kk, k)]
    if same:
        (_, e, lv), _ = collections.Counter(same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG.append((d, opp, e, lv, "same")); return e, lv
    s = opp_season(g, d)
    if (k, s) in TABLE:
        e, lv = TABLE[(k, s)]
        ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s)); return e, lv
    nk = norm(opp)
    for (mk, ms), lv in MANUAL_LV.items():
        if ms == s and (nk == mk or k == key(mk)):
            e = rank_value(lv, d); NEW_TS[(opp, s)] = (e, lv)
            ELO_SRC["순위+리그 수준(새 팀-시즌)"] += 1; ELO_LOG.append((d, opp, e, lv, "new manual")); return e, lv
    for (mk, ms), (lv, b) in NORANK.items():
        if ms == s and nk == mk:
            e = int(round(RT["base"](*b))); NEW_TS[(opp, s)] = (e, lv)
            ELO_SRC["순위 없음(단계 기준점)"] += 1; ELO_LOG.append((d, opp, e, lv, "norank")); return e, lv
    for lg, f in NEWLAB.items():
        t = RANKS.get((lg, s))
        if t and k in t:
            r, n = t[k]
            lv = f(s, r, n); e = rank_value(lv, d)
            NEW_TS[(opp, s)] = (e, lv)
            ELO_SRC["순위+리그 수준(새 팀-시즌)"] += 1; ELO_LOG.append((d, opp, e, lv, "new " + lg)); return e, lv
    return None

# ---------------------------------------------------------------- 출전
def ldate(g): return g["date_local"]
def oname(g): return re.sub(r"\s*\(- ?\d{4}\)|\s*\(\d{4} - \d{4}\)", "", g["opponent"]).strip()

M = []
for g in GAMES:
    if not ldate(g): sys.exit("날짜 없음 " + g["gameId"])
    M.append([ldate(g), oname(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
A_STATUS = []
missing_elo = set()
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa, iss = e["og_scorer"] == "1", e["og_assist_other"] == "1", e["og_self_assist"] == "1"
    if iss: judg.append(("본인 PK 골의 본인 도움(도움 아님)", ldate(g), e["minute"]))
    if not (isg or isa): continue
    inf = INFO[gid]
    our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    tag = f"{gid}|{e['minute']}"
    mi, dm = minute(e["minute"])
    et = int(mi > 90 and (not dm or int(str(dm).split("+")[0]) >= 105))
    if et and g["gameState"] == "regularly_terminated": sys.exit("연장 판정 이상 " + gid)
    cid = g["competitionId"]; d = ldate(g); opp = oname(g)
    comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g, d)
    def add(typ, pk, note):
        res = opp_elo(g, d)
        if res is None:
            missing_elo.add((opp, d, cid, opp_season(g, d))); res = (0, "?")
        row = [typ, opp, res[0], comp, mi, gf, ga, ko, pk, d, et, dm, res[1], note]
        if tie: row.append(tie)
        rows.append(row)
    if isg:
        if e["own_goal"] == "1" or not ours:
            judg.append(("골 제외", d, opp, e["minute"], "지루의 자책골(상대 골)")); continue
        if tag in EXCL_G: judg.append(("골 제외", d, opp, e["minute"], EXCL_G[tag]))
        else: add("g", int(e["penalty"] == "1"), 0)
    if isa:
        if tag in EXCL_A:
            judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], EXCL_A[tag]))
            A_STATUS.append((d, e["minute"], e["scorer"], "제외", EXCL_A[tag])); continue
        if e["own_goal"] == "1" or not ours: sys.exit("자책골 도움 판정 누락 " + tag)
        if e["assist_type"] in ("Penalty: Fouled player", "Shot on goal", "Deflected") or e["assist_type"].startswith("Handball"):
            sys.exit("도움 유형 판정 누락 " + tag)
        fm = [r for r in AC if r["gameId"] == gid and r["minute"] == e["minute"]]
        src = fm[0]["sources_with_assist"] if fm else "?"
        if d >= "2014-08-01":
            if src != "TM + FotMob" and tag not in SINGLE_KEEP: sys.exit("2014.8 뒤 단일 출처 도움 판정 누락 " + tag)
            if tag in SINGLE_KEEP: judg.append(("단일 출처 도움 넣음(다른 출처 2곳 이상)", d, opp, e["minute"], e["scorer"], SINGLE_KEEP[tag]))
        A_STATUS.append((d, e["minute"], e["scorer"], "넣음", src + (" (유형 빈칸)" if not e["assist_type"] else "")))
        add("a", 0, e["scorer"])

if missing_elo:
    for x in sorted(missing_elo, key=lambda x: x[1]): print("Elo 없음:", x)
    if "--debug" not in sys.argv: sys.exit(1)

def sort_min(r):
    return r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45 + int(str(r[11]).split("+")[1]) / 100
rows.sort(key=lambda r: (r[9], sort_min(r), 0 if r[0] == "g" else 1))
E = rows

_chk = collections.defaultdict(set)
for r in E:
    _chk[(key(r[1]), r[12].split(" (")[0].rsplit(" ", 1)[0] if "위" in r[12] else r[12])].add(r[2])
for k_, v in _chk.items():
    if len(v) > 1: print("같은 팀-시즌 값 여럿(내 자료):", k_, v)

if __name__ == "__main__" and "--debug" in sys.argv:
    print(len(M), "경기", sum(r[0] == "g" for r in E), "골", sum(r[8] for r in E), "PK", sum(r[0] == "a" for r in E), "도움", sum(m[3] for m in M), "분")
    print(ELO_SRC)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k)
        if not x[4].startswith("same"): print(x)
    print("새 팀-시즌:")
    for k_, v in sorted(NEW_TS.items(), key=lambda x: x[0][1]): print("  ", k_, v)

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
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
CROSS, SAMEGAME, MATEMISS = [], [], []
for fn, (P, ent, om) in OTHERS.items():
    for r in E:
        if r[0] != "a": continue
        hit = [x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1])]
        if hit: CROSS.append(("지루 도움→" + fn + " 골", r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in ent:
        if x[0] == "a" and "giroud" in norm(str(x[13])):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((fn + " 도움→지루 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK"))]
                SAMEGAME.append((fn, r[9], r[1], tuple(dd) or "같음"))
                break
SAMEGAME = sorted(set(SAMEGAME))
MATE = {"ozi.js": "Mesut Özil", "axs.js": "Alexis Sánchez", "wal.js": "Theo Walcott", "caz.js": "Santi Cazorla", "pod.js": "Lukas Podolski",
        "haz.js": "Eden Hazard", "ped.js": "Pedro", "lea.js": "Rafael Leão", "ibr.js": "Zlatan Ibrahimović", "blh.js": "Younès Belhanda",
        "pul.js": "Christian Pulisic", "fab.js": "Cesc Fàbregas", "grv.js": "Gervinho", "wil.js": "Willian", "ram.js": "Aaron Ramsey"}
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    d = ldate(g); mi = minute(e["minute"])[0]; tag = f"{gid}|{e['minute']}"
    for fn, nm in MATE.items():
        if fn not in OTHERS: continue
        P, ent, om = OTHERS[fn]
        if e["og_scorer"] == "1" and e["own_goal"] != "1" and norm(e["assist_player"]) == norm(nm):
            ok = any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 3 for x in ent)
            MATEMISS.append(("동료 도움→지루 골", fn, d, e["minute"], e["assist_type"], "동료 파일에 있음" if ok else "동료 파일에 없음"))
        if e["og_assist_other"] == "1" and norm(e["scorer"]) == norm(nm):
            ok = any(x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 3 for x in ent)
            MATEMISS.append(("지루 도움→동료 골", fn, d, e["minute"], "제외" if tag in EXCL_A else "넣음", "동료 골 행 있음" if ok else "동료 골 행 없음"))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print("대조", collections.Counter((c[0].split("→")[0][:6], c[-1] == "같음") for c in CROSS))
    for s_ in SAMEGAME:
        if s_[-1] != "같음": print("같은 경기 차이", s_)
    print("같은 경기", collections.Counter((s_[-1] == "같음") for s_ in SAMEGAME))
    for m_ in MATEMISS:
        if "없음" in m_[-1] or m_[4] == "제외": print(m_)
    print("동료 대조", collections.Counter(m_[-1] for m_ in MATEMISS))

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("greog", "2008-09-01", "그르노블", "그르노블", "2005~2007"), ("touog", "2010-07-01", "투르", "투르", "2008~2010"),
         ("mtpog", "2012-07-01", "몽펠리에", "몽펠리에", "2010~2012"), ("arsog", "2018-01-31", "아스널", "아스널", "2012~2018"),
         ("cheog", "2021-07-17", "첼시", "첼시", "2018~2021"), ("milog", "2024-07-18", "AC 밀란", "밀란", "2021~2024"),
         ("lafog", "2025-07-01", "로스앤젤레스 FC", "LAFC", "2024~2025"), ("lilog", None, "릴", "릴", "2025~")]
TM_CLUB = {"1290": "greog", "3161": "touog", "969": "mtpog", "11": "arsog", "631": "cheog", "5": "milog", "51828": "lafog", "1082": "lilog"}
def club_of(d):
    for k, u, *_ in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
    if g["club_id"] == "51828":
        if ldate(g)[:4] != g["seasonId"] and str(int(g["seasonId"]) + 1) != ldate(g)[:4]: sys.exit("LAFC 시즌 이상 " + g["gameId"])
    elif season_eu(ldate(g), g["club_id"])[:4] != g["seasonId"]: sys.exit("시즌 불일치 " + g["gameId"] + " " + ldate(g))
lo = None
PERIODS = []
for k, u, n, sh, y in CLUBS:
    PERIODS.append((n, y, lo, u)); lo = u
def per(lo, hi):
    inr = lambda d: (lo is None or d >= lo) and (hi is None or d < hi)
    return [sum(1 for m in M if inr(m[0])), sum(1 for r in E if r[0] == "g" and inr(r[9])),
            sum(1 for r in E if r[0] == "a" and inr(r[9])), sum(m[3] for m in M if inr(m[0]))]
ST = [(n, y, per(lo, hi)) for n, y, lo, hi in PERIODS]
if __name__ == "__main__" and "--debug" in sys.argv:
    for x in ST: print(x)

# ---------------------------------------------------------------- 설명(NOTE)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
SRC = ELO_SRC
IST_G = sum(int(g["goals"]) for g in EXCL_GAMES); IST_A = sum(int(g["assists"]) for g in EXCL_GAMES); IST_P = sum(int(g["penGoals"]) for g in EXCL_GAMES)
TM_A = sum(1 for e in EVENTS if e["og_assist_other"] == "1" and e["gameId"] in G)
TM_G = sum(1 for e in EVENTS if e["og_scorer"] == "1" and e["own_goal"] != "1" and e["gameId"] in G)
NEWLIST = "; ".join(f"{o} {s} {v[0]}({v[1]})" for (o, s), v in sorted(NEW_TS.items(), key=lambda x: (x[0][1], x[0][0])))
LAST = M[-1]
NOTE_LINES = [
    f"올리비에 지루(그르노블·투르·몽펠리에·아스널·첼시·AC 밀란·로스앤젤레스 FC·릴)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 괴뇽전 ~ {d_(LAST[0])} 렌전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·프랑스 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n}({y}) {v[0]}·{v[1]}·{v[2]}" for n, y, v in ST)
    + f". 출전 분 합계 {MIN_TOT:,}분(90분 추정 없음)",
    f"프로 리그: 그르노블(2005-06·2006-07)·투르(2008-09·2009-10)는 리그2(프로 리그)라 셈. 2007-08 FC 이스트르 임대(프랑스 3부 나시오날, 프랑스 축구협회가 운영하는 세미프로 리그)는 프로 리그가 아니라서 그 시즌 {len(EXCL_GAMES)}경기 {IST_G}골(PK 골 {IST_P}개) {IST_A}도움(Transfermarkt; 리그 33경기·쿠프 드 라 리그 1경기)을 모두 뺌(리베리·발부에나·페페 등 다른 선수의 나시오날 시즌과 같은 처리). 유소년·2군 경기는 Transfermarkt 경기 목록에 없음",
    f"출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(뛴 클럽 경기 전부). 클럽·시즌·대회별 경기·골은 영어·프랑스어 위키백과와 모두 같음(이스트르 포함 통산 813경기 305골). 2010-11 이후 골은 FotMob 경기 기록과 대조함(골 순서·스코어 같음; 2019.3.14 디나모 키이우전 첫 골은 Transfermarkt 9분·FotMob 5분, 추가시간 골 몇 개는 FotMob이 90분으로만 적어 Transfermarkt 분을 씀; FotMob이 경기 자료를 못 주는 2011.1~2012.1 몽펠리에 21경기는 Transfermarkt만). 2006~2010 그르노블·투르 경기는 FotMob 경기 자료가 없어 Transfermarkt만 근거(위키백과 시즌 합계와 같음)",
    f"골: Transfermarkt 리포트의 지루 골 {TM_G}개(이스트르 제외) 그대로. 2015.12.5 선덜랜드전 전반 추가시간 골은 지루의 자책골(Transfermarkt·FotMob 모두 자책골)이라 넣지 않음. PK 골 {NPK}개. 2009.12.12 쿠프 드 프랑스 몽소전(2-1 승)은 Transfermarkt 리포트에 몽소 골이 빠져 있어 지루의 81분 골 앞 스코어를 리포트 순서대로 1-0으로 둠(몽소 골 시각 확인 못 함)",
    f"도움: Transfermarkt 경기 리포트 도움 {TM_A}개(이스트르 제외) − PK 유도 2(2012.5.1 에비앙전 벨한다, 2019.5.29 유로파 결승 아자르) − 슈팅 리바운드·굴절 3(2012.3.11 캉전 아이트파나, 2022.1.6 로마전 메시아스, 2022.10.8 유벤투스전 토모리 — 토모리 골은 FotMob이 도움으로 세지만 경기 기사가 지루 슈팅이 토모리 몸에 맞고 흐른 공이라 적어 뺌) − 2014년 8월 뒤 Transfermarkt 단일 출처로 확인 못 한 1(2017.3.7 챔스 바이에른전 월콧 골) = {NA}",
    "2014년 8월 전 도움은 Transfermarkt 단일 출처도 셈(다른 선수 자료 선례; 투르·몽펠리에 시기 도움은 대부분 경기별 두 번째 출처가 없고, 투르 9개는 프랑스어 위키백과 시즌 도움 수와만 같음). 2014년 8월 뒤 Transfermarkt만 적은 2015.1.25 FA컵 브라이턴전 로시츠키 골 도움은 브라이턴 앤드 호브 뉴스·스포츠몰 문자 중계·블리처 리포트 경기 기사가 지루의 패스를 적어 넣음. 그 밖의 2014년 8월 뒤 도움은 Transfermarkt·FotMob이 같음",
    "FotMob에만 있는 도움 2개는 넣지 않음: 2019.4.18 유로파 8강 슬라비아 프라하전 27분 페드로 골(경기 기사: 지루 슈팅을 골키퍼가 막은 리바운드), 2023.11.7 챔스 PSG전 12분 레앙 골(경기 기사: 돈나룸마가 지루 슈팅을 막은 뒤 레앙 오버헤드킥). 프랑스어 위키백과 통산 도움(106)과 Transfermarkt(105)의 차이는 경기별로 확인되지 않음",
    "출전 분: Transfermarkt 그대로(FotMob 선수 경기 목록이 있는 2017.1 이후 21경기만 1~2분 차이). 연장 경기는 120분까지 셈",
    "날짜: 현지 날짜. LAFC 경기는 Transfermarkt 리포트 날짜(유럽 기준)가 저녁 경기에서 하루 늦어서 경기장 현지 날짜로 바꿈(예: 클럽 월드컵 플레이인 아메리카전 2025.5.31, 에스페랑스전 2025.6.20, 플라멩구전 2025.6.24)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 리그 수준 모형에 넣은 값 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위+리그 수준 {SRC['순위+리그 수준(새 팀-시즌)']}, 순위 없음 {SRC['순위 없음(단계 기준점)']})",
    "새로 정한 팀·시즌(최종 순위 → 리그 수준 모형, Transfermarkt 순위표·위키백과): " + NEWLIST,
    "순위 근거: 리그2·챔피언십·헝가리·벨라루스·스웨덴·노르웨이·세르비아는 Transfermarkt 최종 순위표(세르비아 2025-26은 스플릿 뒤 최종 순위), 프랑스 4부(CFA) 몽소 2009-10 B조 11위/18팀과 프랑스 3부(나시오날) 파시 2008-09 8위/20팀은 프랑스어 위키백과 시즌 문서, 클루브 아메리카는 리가MX 2024-25 연간 합산 4위(영어 위키백과 합산표; 경기가 열린 2025.5.31은 클라우수라가 끝난 뒤라 다른 선수 자료의 2025 클럽 월드컵 멕시코 팀처럼 연간 합산 순위), 말뫼(2019.2 유로파 32강 두 경기)는 같은 1차전을 다룬 다른 선수 자료 값(스웨덴 1부 2019 2위)에 맞춤, 브란(2025.9 경기)은 노르웨이 2025 최종 4위. 레위니옹 섬 리그의 잔다르크(2008-09 쿠프 드 프랑스)는 순위를 찾지 못해 프랑스 6부 기준점 값을 씀(추정). 쿠프 드 프랑스 아마추어 상대 프리레메지에르(2011-12)는 같은 경기 다른 선수 자료 값",
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·FA컵·리그컵·코파 이탈리아·US 오픈컵은 국내컵(FA컵 6라운드·8강은 8강 비중, 리그컵 준결승 두 경기는 합산), 커뮤니티 실드·수페르코파 이탈리아나·UEFA 슈퍼컵은 국내컵 결승 비중, 챔스 플레이오프(아스널 2013·2014)는 챔스 예선, 유로파 32강·녹아웃 플레이오프·16강·8강은 유로파 토너먼트, 2025-26 유로파·2026-27 챔스 리그 단계는 리그·조별 비중, MLS 플레이오프 1라운드(3판 2선승)와 서부 준결승은 MLS 플레이오프(경기마다 단판), 리그스컵 16강~결승은 리그스컵 토너먼트(다른 선수 자료 선례), 북중미 챔스 1라운드·16강은 북중미 챔스, 8강은 북중미 챔스 8강, 클럽 월드컵 2025 조별은 리그식(무승부 1점), 클럽 월드컵 플레이인 아메리카전(연장 승)은 단판 클럽 월드컵",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회는 2020-21까지 원정 다득점·연장, 2021-22부터 연장만, 리그컵 준결승 2018-19(토트넘전)은 원정 다득점·연장 없이 승부차기, 코파 이탈리아 2021-22 준결승은 원정 다득점·연장, 북중미 챔스는 원정 다득점·연장 없음. 지루가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 유럽 클럽은 8월 1일 기준(2020년 8월 경기는 2019-20), 그르노블·투르·몽펠리에는 7월 10일 기준(2006.7.28 리그2 개막전·2010.7.29 유로파 예선이 새 시즌), 로스앤젤레스 FC는 달력 연도. 클럽 구분은 2008.9.1 전 그르노블(2007-08 이스트르 임대는 제외), 2010.7.1 전 투르, 2012.7.1 전 몽펠리에, 2018.1.31 전 아스널, 2021.7.17 전 첼시, 2024.7.18 전 AC 밀란, 2025.7.1 전 로스앤젤레스 FC, 이후 릴",
    "우승·수상은 Transfermarkt 업적 페이지와 영어·프랑스어 위키백과 기준: 리그1 2011-12(몽펠리에), 세리에A 2021-22, UEFA 챔피언스리그 2020-21, 유로파리그 2018-19, FA컵 2014·2015·2017(아스널)·2018(첼시), 커뮤니티 실드 2014-15·2015-16·2017-18, US 오픈컵 2024(Transfermarkt는 23/24로 적음). 개인: 득점왕 리그2 2009-10(21골)·리그1 2011-12(21골)·유로파리그 2018-19(11골), 리그2 올해의 선수 2009-10(UNFP), 리그1 올해의 팀 2011-12(UNFP). FIFA 푸슈카시상 2017은 이 계산기 수상 항목에 없어 뺌. 월드컵 2018 우승·네이션스리그 2021 우승 등 대표팀 기록은 뺌",
    f"현역(릴, 2025.7 입단). {d_(LAST[0])} 렌 원정(리그1, 교체 {LAST[3]}분)까지 반영, 2026.11.18 기준 마지막 갱신",
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
    if r[4] > 90 and not r[10] and not r[11]: problems.append(("90분 넘는 정규 시간 골", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const GIR_E={J(E)};\nconst GIR_M={J(M)};\nconst GIR_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "fotmob_only_assists_not_added": FM_ONLY, "cross_check": CROSS, "same_game": SAMEGAME, "mate_check": MATEMISS,
               "elo_sources": ELO_SRC, "new_team_seasons": {f"{a}|{b}": v for (a, b), v in NEW_TS.items()},
               "excluded_istres_games": [g["gameId"] for g in EXCL_GAMES], "elo_log": ELO_LOG},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for n, y, v in ST: print(" ", n, y, v)
