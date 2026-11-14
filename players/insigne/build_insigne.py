#!/usr/bin/env python3
"""Lorenzo Insigne: raw/ -> insigne.json + src/data/ins.js (판정은 judgments.md)

  python3 players/insigne/build_insigne.py

입력: raw/tm_games.csv(출전), raw/insigne_goal_assist_events.csv(골·도움), raw/ranks.txt(순위표),
      /home/user/soc/elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값),
      src/data/{imm,cav,hig}.js(같은 경기 동료 자료 대조).
"""
import csv, json, os, re, sys, unicodedata, collections

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "ins.js")
OUT_JSON = os.path.join(HERE, "insigne.json")

YOUTH = "12819"
GAP = "2014-08-01"   # 이 날짜 전 도움은 Transfermarkt(FotMob 경기 이벤트에 도움이 거의 없음)

# ---------------------------------------------------------------- 판정 표
# 도움 제외(TM 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    "1139179|73": "PK 유도(이모빌레 PK)",
    "3614559|24": "Shot on goal(리바운드) - FotMob은 도움으로 셈",
    "4318346|63": "상대 자책골(이언 머피) 유도, Shot on goal",
    "4514497|66": "상대 자책골(루커스 바틀릿) 유도",
    "2492486|45+2": "2014.8 이후 Transfermarkt 단일 출처, 기사 2곳 확인 못 함(FotMob 도움 없음)",
    "2800302|3": "2014.8 이후 Transfermarkt 단일 출처, 기사는 지엘린스키 단독 돌파로 서술(FotMob 도움 없음)",
    "3132935|14": "크로스를 골키퍼 페골로가 쳐낸 뒤 밀리크가 넣음(리바운드성) - FotMob·FotMob 선수 경기 목록 모두 도움 없음",
}
# 2014.8 이후 Transfermarkt 단일 출처지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "2800302|56": "ESPN 경기 기록(assist L. Insigne)·World Soccer Talk/AFP 기사(인시녜의 패스)",
    "2904739|13": "OGC 니스 구단 경기 기사(인시녜의 롱패스)·Il Post(인시녜가 메르턴스에게 침투 패스)",
    "3496495|3": "Sports Mole 문자중계(Assist - Lorenzo Insigne)·경기 기록 목록 'P. Zielinski (L. Insigne) 3'",
}
# FotMob에만 있는 도움(넣지 않음) - judgments.md
FM_ONLY = ["2015-11-05 미트윌란 23분 가비아디니(인시녜 슈팅을 골키퍼가 막은 리바운드)",
           "2018-02-22 라이프치히 33분 지엘린스키(인시녜 슈팅을 굴라치가 막은 리바운드)"]
# 골 분: TM이 90분 정각, FotMob이 추가시간을 적은 경우 FotMob 추가시간
MIN_FIX = {"2726777|90": "90+2"}

# ---------------------------------------------------------------- 대회 코드
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in ("IT1", "IT2", "IT3B", "MLS1"): return "lg"
    if cid == "CIT":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "CILP": return "dc"
    if cid == "SCI": return "df"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"     # intermediate stage(32강)·Second Round(2013-14 32강)·16강·8강
    if cid == "CAN":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "USMX":
        return "lcg" if r.startswith("group") else "lck"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0                     # 두 경기 합산은 tie로
    if cid in ("IT1", "IT2", "IT3B", "MLS1"): return 0
    if r.startswith("group"): return 0          # 단, 리그스컵 조별은 무승부 → 승부차기라 단판(메시 선례)
    return 1

def ko_fix(cid, rnd, ko):
    if cid == "USMX": return 1
    return ko

# 두 경기 합산: gameId -> (leg, home, f_ours, f_theirs, awaygoals, extratime)
TIES = {
    "2385099": (2, 1, 0, 0, 1, 1),   # 2014.2.27 유로파 32강 2차전 스완지(1차전 0-0)
    "2547356": (1, 0, 0, 0, 1, 1),   # 2015.4.16 유로파 8강 1차전 볼프스부르크
    "2560695": (1, 1, 0, 0, 1, 1),   # 2015.5.7 유로파 4강 1차전 드니프로
    "2805638": (1, 0, 0, 0, 1, 1),   # 2017.2.15 챔스 16강 1차전 레알
    "2820739": (1, 0, 0, 0, 1, 1),   # 2017.2.28 코파 4강 1차전 유벤투스
    "2820740": (2, 1, 1, 3, 1, 1),   # 2017.4.5 코파 4강 2차전 유벤투스(1차전 1-3)
    "2904739": (1, 1, 0, 0, 1, 1),   # 2017.8.16 챔스 PO 1차전 니스
    "2905727": (2, 0, 2, 0, 1, 1),   # 2017.8.22 챔스 PO 2차전 니스(1차전 2-0)
    "2982094": (2, 0, 1, 3, 1, 1),   # 2018.2.22 유로파 32강 2차전 라이프치히(1차전 1-3)
    "3135840": (1, 0, 0, 0, 1, 1),   # 2019.2.14 유로파 32강 1차전 취리히
    "3312133": (2, 1, 1, 0, 1, 0),   # 2020.6.13 코파 4강 2차전 인테르(1차전 1-0, 연장 없이 승부차기)
    "3291942": (2, 0, 1, 1, 1, 1),   # 2020.8.8 챔스 16강 2차전 바르셀로나(1차전 1-1)
    "3496495": (2, 1, 0, 2, 1, 1),   # 2021.2.25 유로파 32강 2차전 그라나다(1차전 0-2)
    "3714023": (2, 1, 1, 1, 0, 1),   # 2022.2.24 유로파 32강 2차전 바르셀로나(1차전 1-1, 2021-22부터 원정 다득점 없음)
    "4366592": (2, 1, 1, 2, 0, 0),   # 2024.8.27 캐나디안 챔피언십 4강 2차전 포지(1차전 1-2, 원정 다득점·연장 없음)
}

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
        canon = row[0]
        for part in row[1].split(" / "):
            nm = part.rsplit(":", 1)[0]
            ALIAS[norm(nm)] = norm(canon)
MANUAL_ALIAS = {"dc united": "d c united", "atlanta united fc": "atlanta united fc"}

def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        TABLE[(key(r["팀"]), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

# 순위표
RANKS = collections.defaultdict(dict)   # (league, season) -> {normname: (rank, n)}
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))

# 세리에A 고정 순위값(기존 자료 20팀) → 표준 곡선. 다른 리그는 평균 + 흩어짐 × 곡선(순위 위치 보간)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
SA_MEAN, SA_SD = 1739, 91.3
CV = [(v - SA_MEAN) / SA_SD for v in SA]

def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t

LEAGUE = {   # 평균, 흩어짐
    "IT1": (1739, 91.3), "IT2": (1577.78, 51.24), "IT3": (1416.56, 51.24), "IT4": (1255.34, 51.24),
    "MLS": (1581, 57.98), "CPL": (1300, 51.24),
}

def model(lg, r, n):
    m, sd = LEAGUE[lg]
    return round(m + sd * curve(r, n))

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    if d.startswith("2020-08"): return "2019-20"
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 순위표 리그 → (모형 리그, lv 머리말, 추정 여부)
RANK_LG = {
    "Serie A [TM IT1]": ("IT1", "세리에A {s} {r}위", False),
    "Serie B [TM IT2]": ("IT2", "세리에B {s} {r}위", False),
    "Serie C - Girone B (Lega Pro 1a Div. B 2010-11) [TM IT3B]": ("IT3", "세리에C(레가 프로 1) B조 {s} {r}위/{n}팀 (추정)", True),
    "Serie C - Girone A (Lega Pro 1a Div. A) [TM IT3A]": ("IT3", "세리에C(레가 프로 1) A조 {s} {r}위/{n}팀 (추정)", True),
    "Lega Pro Seconda Divisione - Girone B [TM IT4Y]": ("IT4", "레가 프로 2(4부) B조 {s} {r}위/{n}팀 (추정)", True),
    "MLS Supporters' Shield overall (FotMob 130)": ("MLS", "MLS {s} {r}위", False),
    "Canadian Premier League [TM CDN1]": ("CPL", "캐나디안 프리미어리그 {s} {r}위 (리그 수준 추정)", True),
}
# 순위표에 없는 상대(직접 추정, 모두 '추정')
MAN = {
    (key("BSC Young Boys"), "2014-15"): (1580, "스위스 슈퍼리그 2014-15 2위 (추정)"),
    (key("FC Zürich"), "2018-19"): (1480, "스위스 슈퍼리그 2018-19 7위 (추정)"),
    (key("Dnipro Dnipropetrovsk (- 2020)"), "2014-15"): (1600, "우크라이나 2014-15 3위 (추정)"),
    (key("HNK Rijeka"), "2020-21"): (1460, "크로아티아 2020-21 3위 (추정)"),
    (key("Legia Warszawa"), "2021-22"): (1500, "폴란드 2021-22 10위 (추정)"),
    (key("Paris Saint-Germain"), "2018-19"): (1955, "리그1 2018-19 1위"),   # 리그1 1위 값(기존 자료 고정값)
}
MLS_LIKE = {"MLS1", "CAN", "USMX"}

ELO_SRC = collections.Counter()
ELO_LOG = {}

def opp_elo(opp, date, cid, napoli_season_alt=None):
    k = key(opp)
    eu = season_eu(date)
    y = date[:4]
    if cid in MLS_LIKE:
        seasons = [y, eu]
    else:
        seasons = [eu, str(int(eu[:4]))]          # 스웨덴 등 달력 연도 리그(예: AIK 2012)
    if k == key("CF Pachuca"): seasons = ["2024-25"]
    for s in seasons:
        if (k, s) in TABLE:
            vals = TABLE[(k, s)]
            e, lv = collections.Counter(vals).most_common(1)[0][0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(opp, s)] = ("table", e, lv)
            return e, lv
    for s in seasons:
        if (k, s) in MAN:
            e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(opp, s)] = ("man", e, lv)
            return e, lv
    for (lgname, s), tab in RANKS.items():
        if s in seasons and k in tab and lgname in RANK_LG:
            r, n = tab[k]
            lg, fmt, est = RANK_LG[lgname]
            e = model(lg, r, n)
            ss = s
            if lgname.startswith("Serie B") and s == "2026-27":
                ss = "2026-27 (11월 초 현재)"
            lv = fmt.format(s=ss, r=r, n=n)
            if lg == "MLS" and n == 28: lv = f"MLS {s} {r}위/28팀"
            ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(opp, s)] = ("model", e, lv)
            return e, lv
    sys.exit(f"상대 Elo 없음: {opp} {seasons}")

# ---------------------------------------------------------------- 출전
games = [g for g in csv.DictReader(open(os.path.join(RAW, "tm_games.csv"), encoding="utf-8")) if g["clubId"] != YOUTH]
G = {g["gameId"]: g for g in games}
M = []
for g in sorted(games, key=lambda g: (g["date_local"], g["gameId"])):
    M.append([g["date_local"], g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
ev = [e for e in csv.DictReader(open(os.path.join(RAW, "insigne_goal_assist_events.csv"), encoding="utf-8")) if e["clubId"] != YOUTH]
FM = collections.defaultdict(list)
for r in csv.DictReader(open(os.path.join(RAW, "fotmob_events.csv"), encoding="utf-8")):
    FM[r["tmGameId"]].append(r)

def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
for e in ev:
    gid, mstr = e["gameId"], e["minute_tm"]
    g = G[gid]
    tag = f"{gid}|{mstr}"
    role = e["role"]
    if role == "assist":
        if tag in EXCL_A:
            judg.append(("도움 제외", e["date_local"], e["opponent"].strip(), mstr, e["scorer"], EXCL_A[tag])); continue
        if e["date_local"] >= GAP and "assist by Lorenzo Insigne" not in (e["fm_assistStr"] or "") and tag not in ADD_CONFIRMED:
            sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락: " + tag)
    if tag in MIN_FIX:
        mstr = MIN_FIX[tag]
    mi, dm = minute(mstr)
    bh, ba = map(int, e["score_before_home_away"].split("-"))
    gf, ga = (bh, ba) if e["insigne_side"] == "h" else (ba, bh)
    cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd)
    ko = ko_fix(cid, rnd, ko_of(cid, rnd))
    pk = 1 if (role == "goal" and e["penalty"] == "1") else 0
    elo, lv = opp_elo(g["opponent"].strip(), e["date_local"], cid)
    note = 0 if role == "goal" else e["scorer"]
    tie = TIES.get(gid)
    if ("leg" in rnd.lower()) != bool(tie):
        sys.exit("합산 표 누락: " + gid + " " + rnd)
    row = ["g" if role == "goal" else "a", g["opponent"].strip(), elo, comp, mi, gf, ga, ko, pk, e["date_local"], 0, dm, lv, note]
    if tie: row.append(list(tie))
    rows.append(row)

rows.sort(key=lambda r: (r[9], r[4], r[0]))

# 단판 연장 골 확인(이 선수는 없음)
for r in rows:
    if r[7] and r[4] > 95: sys.exit("연장 골 판정 필요: " + str(r))

E = rows
# ---------------------------------------------------------------- 같은 경기 동료 자료 대조
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
mates = {"Ciro Immobile": load_js("imm.js", "IMM"), "Edinson Cavani": load_js("cav.js", "CAV"),
         "Gonzalo Higuaín": load_js("hig.js", "HIG")}
cross = []
for r in E:
    if r[0] == "a" and r[13] in mates:
        hit = [x for x in mates[r[13]] if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
        cross.append(("인시녜 도움→동료 골", r[9], r[13], r[4], "있음" if hit else "없음",
                      (hit[0][2], hit[0][12]) if hit else None, (r[2], r[12])))
for nm, ent in mates.items():
    for x in ent:
        if x[0] == "a" and x[13] == "Lorenzo Insigne":
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            cross.append(("동료 도움→인시녜 골", x[9], nm, x[4], "있음" if hit else "없음",
                          (x[2], x[12]), (hit[0][2], hit[0][12]) if hit else None))
        # 같은 날 같은 상대 Elo
        for r in E:
            if r[9] == x[9] and x[1] == r[1] and x[2] != r[2]:
                cross.append(("Elo 다름", r[9], nm, r[1], x[2], r[2]))


# ---------------------------------------------------------------- 클럽별 합계(설명 첫 줄·클럽별 줄)
CLUBS = [("2010-02-01", "나폴리 2009-10"), ("2010-07-01", "카베세"), ("2011-07-01", "포자"), ("2012-07-01", "페스카라"),
         ("2022-07-01", "나폴리"), ("2026-01-30", "토론토 FC"), ("2026-07-08", "페스카라 2기"), ("9999-12-31", "삼프도리아")]
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
ST = collections.OrderedDict((n, [0, 0, 0]) for _, n in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE = collections.Counter(club_of(r[9]) for r in E if r[0] == "a" and r[9] < GAP)
MIN_TOT = sum(m[3] for m in M)
nap = [ST["나폴리 2009-10"][i] + ST["나폴리"][i] for i in range(3)]
pes = [ST["페스카라"][i] + ST["페스카라 2기"][i] for i in range(3)]
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v))

NOTE_LINES = [
    f"로렌초 인시녜(나폴리·카베세·포자·페스카라·토론토 FC·삼프도리아)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 리보르노전 ~ {d_(M[-1][0])} 아벨리노전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    f"클럽별 경기·골·도움: 나폴리 {c3(nap)}(2009-10 {c3(ST['나폴리 2009-10'])}, 2012-22 {c3(ST['나폴리'])}), 카베세 {c3(ST['카베세'])}, 포자 {c3(ST['포자'])}, "
    f"페스카라 {c3(pes)}(2011-12 {c3(ST['페스카라'])}, 2025-26 {c3(ST['페스카라 2기'])}), 토론토 FC {c3(ST['토론토 FC'])}, 삼프도리아 {c3(ST['삼프도리아'])}",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(API, 출전 {NG}경기·{MIN_TOT}분)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음",
    "경기 수·골은 영어·이탈리아어 위키백과 시즌별 기록과 포자 2010-11 컵 대회를 빼고 모두 같음. FotMob 경력 합계(나폴리 433경기 + 2010년 1경기, 토론토 76경기 등)와도 경기·골이 같음",
    "포자 2010-11 코파 이탈리아 레가 프로는 위키백과가 7경기 7골이나 Transfermarkt에는 5경기 5골(라퀼라·줄리아노바·첼라노·소렌토·유베 스타비아)만 있음. 나머지 2경기(파노 조별·바를레타 2라운드 또는 코센차 3라운드 조별 중)와 2골은 경기별 자료로 확인되지 않아 넣지 않음",
    "나폴리 유스(프리마베라·비아레지오컵 40경기 20골)와 이탈리아 대표팀 경기는 뺌",
    "2019.4.22 아탈란타전(FotMob 선수 경기 목록에만 교체 13분 출전)은 Transfermarkt가 명단 포함(출전 아님)으로 적고 위키백과 2018-19 리그 출전 수(28경기)도 이 경기를 세지 않아 넣지 않음. 2017.2.28 코파 이탈리아 준결승 1차전 유벤투스전(90분)은 FotMob 선수 경기 목록에 없지만 Transfermarkt·FotMob 경기 기록에 출전이 있어 넣음",
    f"PK 골 {NPK}개는 Transfermarkt 골 유형 기준(FotMob과 같음). 2021.5.16 피오렌티나전 56분 골은 PK가 막힌 뒤 리바운드 골이라 일반 골로 셈. 2022.1.23 살레르니타나전 53분 PK 골은 Transfermarkt 리포트에 본인 도움으로도 적혀 있으나 도움으로 세지 않음",
    "골 시각은 Transfermarkt 기준. 2011-12 페스카라 시절 FotMob과 2분 다른 골 2개(2011.8.14 트리에스티나전 84분·FotMob 82분, 2011.11.12 파도바전 60분·FotMob 62분)는 Transfermarkt를 씀. 2017.4.9 라치오전 두 번째 골은 Transfermarkt가 90분, FotMob이 90+2분이라 추가시간 표기(90+2)를 씀",
    "도움은 2014.8.1 이전은 Transfermarkt 도움을 쓰고, 그 뒤는 FotMob 경기 이벤트와 Transfermarkt가 같이 적은 도움을 기준으로 함",
    f"도움 {NA}개 = Transfermarkt 도움 135개 − PK 유도 1개(2011.9.24 유베 스타비아전 임모빌레 PK) − 'Shot on goal' 리바운드 1개(2021.9.20 우디네세전 24분 오시멘, FotMob은 도움으로 셈) − 상대 자책골 유도 2개(2024.5.25 신시내티전 63분 머피, 2025.5.10 D.C. 유나이티드전 66분 바틀릿) − 2014.8 이후 Transfermarkt 단일 출처로 다른 출처 2곳이 확인하지 못한 2개 − 골키퍼가 쳐낸 크로스를 넣은 리바운드성 1개",
    "다른 출처 2곳이 확인하지 못해 뺀 도움: 2014.11.6 유로파 영 보이스전 45+2분 더 휘즈만 골(FotMob 도움 없음, 경기 기사도 도움자 미기재), 2017.1.10 코파 이탈리아 스페치아전 3분 지엘린스키 골(기사는 단독 돌파로 서술)",
    "2019.1.13 코파 이탈리아 사수올로전 14분 밀리크 골은 Transfermarkt가 인시녜 도움으로 적었으나 경기 기사(ESPN·Eurosport·Goal 이탈리아)는 인시녜 크로스를 골키퍼 페골로가 쳐낸 뒤 밀리크가 넣었다고 하고 FotMob도 도움으로 세지 않아 뺌",
    "2014.8 이후 FotMob 경기 이벤트에 없지만 다른 출처 2곳이 확인해 넣은 도움: 2017.1.10 스페치아전 56분 자케리니 골(ESPN·AFP), 2017.8.16 챔스 플레이오프 니스전 13분 메르턴스 골(니스 구단 기사·Il Post), 2021.2.25 유로파 그라나다전 3분 지엘린스키 골(Sports Mole 문자중계·경기 기록)",
    "FotMob에만 있는 도움 2개는 넣지 않음: 2015.11.5 유로파 미트윌란전 23분 가비아디니 골(인시녜 슈팅을 골키퍼가 막은 리바운드), 2018.2.22 유로파 라이프치히전 33분 지엘린스키 골(인시녜 슈팅을 굴라치가 막은 리바운드)",
    f"2014.8.1 이전 도움 {sum(PRE.values())}개(포자 {PRE['포자']}·페스카라 {PRE['페스카라']}·나폴리 {PRE['나폴리']})는 Transfermarkt 단일 출처이고 다른 출처로 대조하지 못함. 도움 유형 칸이 빈 2012.3.10 치타델라전 29분 산소비니 골 도움도 도움으로 셈",
    "2012.5.1 비첸차전 60분 골은 Transfermarkt가 상대 자책골(임모빌레 도움)로, FotMob이 임모빌레 골로 적음. 인시녜 기록과는 무관하고 임모빌레 자료와 같게 둠",
    "날짜는 경기 현지 날짜. 토론토 저녁 경기는 Transfermarkt 리포트 날짜(중부 유럽 기준)보다 하루 앞인 토론토 날짜를 씀",
    "상대 Elo는 기존 선수 자료의 같은 팀·같은 시즌 값을 먼저 쓰고, 없으면 그 시즌 최종 순위(Transfermarkt 순위표, MLS는 FotMob 서포터스 실드 순위)를 기존 리그 모형에 넣음. 세리에B(평균 1578)는 임모빌레 자료와 같은 방식이며 2026-27은 11월 초 현재 순위",
    "레가 프로 1부(3부, 2010-11 포자·카베세 조와 소렌토 조, 2011-12 트리에스티나)는 세리에B 평균에서 세리에A·B 차이만큼 내린 약 1417에 2부 흩어짐 곡선을, 레가 프로 2부(4부, 라퀼라·줄리아노바)는 한 단계 더 내린 약 1255를 적용한 추정값임(순위는 Transfermarkt, 근거 약함)",
    "캐나디안 프리미어리그 포지 FC 2024(1위)는 뮐러 자료와 같은 리그 수준 추정(평균 1300)으로 1429",
    "리그 표가 없는 상대는 당시 수준을 추정함(모두 '추정'): 영 보이스 2014-15 1580(스위스 2위), FC 취리히 2018-19 1480(스위스 7위), 드니프로 2014-15 1600(우크라이나 3위, 다른 선수 자료 2013-14 값과 같음), HNK 리예카 2020-21 1460(크로아티아 3위), 레기아 바르샤바 2021-22 1500(폴란드 10위). AIK 2012 1470·파추카 2024-25 1610은 다른 선수 자료의 같은 팀·시즌 값을 씀. PSG 2018-19는 리그1 1위 값",
    "코파 이탈리아·코파 이탈리아 레가 프로·캐나디안 챔피언십은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), 수페르코파 이탈리아나는 국내컵 결승으로 계산함. 레가 프로 컵 조별리그는 리그식(무승부 1점), 1라운드(소렌토전)는 단판",
    "리그스컵 2024 조별 경기는 무승부면 승부차기를 하므로 단판으로, 32강(인터 마이애미전)은 토너먼트로 계산함. 유로파 32강('intermediate stage', 2013-14 'Second Round')은 토너먼트, 챔스 플레이오프는 예선으로 계산함",
    f"두 경기 합산(유로파 32강~4강·챔스 16강·챔스 플레이오프·코파 이탈리아 준결승·캐나디안 챔피언십 4강) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회 2020-21시즌까지·코파 이탈리아 2021-22시즌까지 적용, 캐나디안 챔피언십은 원정 다득점·연장 없음. 2020.6.13 코파 이탈리아 준결승 2차전 인테르전은 연장 없이 승부차기 규정",
    "못 뛴 다른 차전 스코어를 채운 경기는 없음(합산 경기의 다른 차전은 모두 출전). 2020.8.8 챔스 16강 2차전 바르셀로나전 45+5분 PK 골은 1차전 1-1을 넣어 합산으로 계산함",
    "연장 없이 승부차기로 끝난 경기(2022.7.26·2024.9.25 캐나디안 챔피언십 결승, 2024.7.27 리그스컵 뉴욕 레드불스전, 2025.4.30 캐나디안 챔피언십 몬트리올전, 2020.6.17 코파 이탈리아 결승)와 연장 뒤 승부차기로 진 2011.8.14 트리에스티나전(120분)은 Transfermarkt 출전 분 그대로 씀. 연장 시간 골은 없음",
    "시즌은 8월 1일 기준(2020년 8월 나폴리 경기는 2019-20), 토론토 FC는 MLS 달력 연도 기준",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 이탈리아 대표팀 우승(유로 2020)은 뺌. 코파 이탈리아 레가 프로 2010-11 득점왕 7골은 Transfermarkt 표기 그대로이며 이 계산기에는 그 대회 5골만 들어 있음. 수페르코파 2014-15 우승은 부상으로 결장했으나 소속 시즌이라 Transfermarkt대로 셈",
    f"2026.11.11 기준: 삼프도리아 마지막 출전은 2026.10.9 아벨리노전이고, 그 뒤 10.18~10.27 부상·10.31 명단 포함(출전 없음)·11.8 명단 제외",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP"]:
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
for r in E:
    by[r[9]].append(r)
mins = {(m[0], m[1]): m[3] for m in M}
for d, rs in by.items():
    prev = None
    for r in sorted(rs, key=lambda r: (r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45 + r[4] / 1000)):
        sc = (r[5], r[6])
        if prev and (sc[0] < prev[0] or sc[1] < prev[1]): problems.append(("스코어 역순", d, r[4]))
        prev = (sc[0] + 1, sc[1]) if True else sc
    if not any(m[0] == d for m in M): problems.append(("출전 없음", d))
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
if problems:
    for p in problems: print("점검:", p)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
js = f"const INS_E={J(E)};\nconst INS_M={J(M)};\nconst INS_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "cross_check": cross,
           "elo_sources": ELO_SRC}, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("점검 문제", len(problems))
