#!/usr/bin/env python3
"""Bradley Barcola: raw/ -> barcola.json + src/data/bcl.js (판정은 judgments.md)

  python3 players/barcola/build_barcola.py

입력: raw/tm_games.csv(출전, category=senior만), raw/barcola_goal_assist_events.csv(골·도움, TM 리포트+FotMob 이벤트),
      raw/ranks.txt(FotMob 순위표), /home/user/soc/elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값),
      src/data/{lac,mba,kva,sal}.js(같은 경기 동료 자료 대조).
"""
import csv, json, os, re, sys, unicodedata, collections

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "bcl.js")
OUT_JSON = os.path.join(HERE, "barcola.json")

# ---------------------------------------------------------------- 판정 표
# 도움 제외(TM 도움이지만 넣지 않음): gameId|분 -> 이유
EXCL_A = {
    "3840439|2": "상대 자책골(랭스 아그바두) 유도 - FotMob도 도움 없음",
    "4635024|51": "PK 유도(뎀벨레 PK, Transfermarkt 'Penalty: Fouled player') - FotMob도 도움 없음",
}
# FotMob 경기 이벤트에 없지만(2014.8 이후 Transfermarkt 단일) 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "3998069|67": "Soccerway 경기 기사(바르콜라 크로스를 라카제트가 마무리)·ESPN 경기 보고서, FotMob 선수 경기 목록도 도움 1",
    "4515311|67": "CulturePSG 문자중계(바르콜라가 6m 안으로 크로스, 두에 마무리)·Soccerway 경기 기사, FotMob 선수 경기 목록도 도움 1",
    "4363982|62": "리그1 공식 기사(LFP, 바르콜라의 컷백을 주앙 네베스가 마무리)·Soccerway 경기 기사(도움 3개)·생테티엔 구단 기사·CulturePSG",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUES = ("FR1", "GB1")

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUES: return "lg"
    if cid == "FRC":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                          # 64강(Fifth Round)·32강(Sixth Round/Round of 32)·16강
    if cid == "CGB": return "dc"             # 리그컵 3라운드·16강(4라운드)
    if cid in ("FRCH", "USC"): return "df"   # 트로페 데 샹피옹·UEFA 슈퍼컵 = 국내컵 결승 비중
    if cid in ("KLUB", "FIC1"): return "cwc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("intermediate") or r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        if r.startswith("final"): return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUES: return 0
    if r.startswith("group"): return 0       # 챔스 리그 단계·유로파 조별·클럽 월드컵 2025 조별(리그식)
    return 1

# 두 경기 합산: gameId -> (leg, home, f_ours, f_theirs, awaygoals, extratime). 2021-22부터 UEFA 원정 다득점 없음
TIES = {
    "4243690": (1, 1, 0, 0, 0, 1),   # 2024.2.14 챔스 16강 1차전 레알 소시에다드(H)
    "4312028": (2, 0, 2, 3, 0, 1),   # 2024.4.16 챔스 8강 2차전 바르셀로나(A, 1차전 2-3)
    "4547601": (2, 1, 3, 0, 0, 1),   # 2025.2.19 챔스 녹아웃 PO 2차전 브레스트(H, 1차전 3-0)
    "4814095": (1, 0, 0, 0, 0, 1),   # 2026.2.17 챔스 녹아웃 PO 1차전 모나코(A)
    "4814354": (1, 1, 0, 0, 0, 1),   # 2026.3.11 챔스 16강 1차전 첼시(H)
    "4814362": (2, 0, 5, 2, 0, 1),   # 2026.3.17 챔스 16강 2차전 첼시(A, 1차전 5-2)
    "4814374": (2, 0, 2, 0, 0, 1),   # 2026.4.14 챔스 8강 2차전 리버풀(A, 1차전 2-0 — 바르콜라 결장, TM 일정·리포트)
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
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])

def key(n):
    k = norm(n)
    return ALIAS.get(k, k)

TABLE = {}
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

# 리그1 고정 순위값(기존 자료: 20팀 2021-23, 18팀 2023-) → 표준 곡선 c = (값 − 1714) / 96.9
L1_20 = [1955, 1872, 1825, 1792, 1776, 1764, 1750, 1733, 1715, 1699, 1688, 1679, 1669, 1664, 1655, 1640, 1621, 1610, 1602, 1582]
L1_18 = [1955, 1866, 1817, 1786, 1771, 1757, 1738, 1718, 1700, 1687, 1677, 1667, 1662, 1647, 1628, 1612, 1603, 1582]
PL = [2083, 1998, 1951, 1917, 1901, 1889, 1875, 1857, 1839, 1822, 1811, 1802, 1792, 1787, 1778, 1762, 1743, 1731, 1723, 1703]  # 2025-26 이후(조정 없음)

def c_of(r, n):
    lst = L1_20 if n == 20 else L1_18
    return (lst[r - 1] - 1714) / 96.9

def model(mean, sd, r, n):
    return round(mean + sd * c_of(r, n))

# 순위표(raw/ranks.txt, FotMob) → (TM 이름, 시즌) -> (Elo, lv)
RANK_NAME = {"Lens": "RC Lens", "Lille": "LOSC Lille", "Auxerre": "AJ Auxerre", "Metz": "FC Metz", "Grenoble": "Grenoble Foot 38",
             "Dunkerque": "USL Dunkerque",
             "Brentford": "Brentford FC", "Brighton & Hove Albion": "Brighton & Hove Albion"}
RANKED = {}
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[4] not in RANK_NAME: continue
        lg, s, r, n = p[0], p[1], int(p[2]), int(p[3])
        if "/" in s: s = s[:4] + "-" + s[7:9]
        tm = RANK_NAME[p[4]]
        if lg == "Ligue 1":
            e, lv = model(1714, 96.9, r, n), f"리그1 {s} {r}위"
        elif lg == "Ligue 2":
            e, lv = model(1540, 51.237, r, n), f"리그2(프랑스 2부) {s} {r}위"
        elif lg == "Premier League":
            e, lv = PL[r - 1], f"프리미어리그 {s} (11월 초 현재) {r}위"
        else:
            continue
        RANKED[(key(tm), s)] = (e, lv)

# 순위표·모형에 없는 상대(직접 추정, 모두 '추정')
MAN = {
    (key("AC Sparta Praha"), "2021-22"): (1550, "체코 2021-22 3위 (추정)"),
    (key("FC Espaly Saint-Marcel"), "2024-25"): (1150, "프랑스 5부 (추정)"),
    (key("Le Mans FC"), "2024-25"): (1350, "프랑스 3부(내셔널) 2024-25 2위 (추정)"),
    (key("Stade Briochin"), "2024-25"): (1220, "프랑스 4부 (추정)"),
    (key("LASK"), "2026-27"): (1539, "오스트리아 분데스리가 2026-27 (11월 초 현재) 3위 (추정)"),
}
YEAR_KEYED = {key("Seattle Sounders FC"), key("Inter Miami CF"), key("Botafogo de Futebol e Regatas"), key("CR Flamengo")}

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

ELO_SRC = collections.Counter()
ELO_LOG = {}

def opp_elo(opp, date):
    k = key(opp)
    s = date[:4] if k in YEAR_KEYED else season_eu(date)
    for src, tab in (("기존 팀×시즌 값", TABLE), ("순위표+리그 모형", RANKED), ("직접 추정", MAN)):
        if (k, s) in tab:
            e, lv = tab[(k, s)]
            ELO_SRC[src] += 1; ELO_LOG[(opp, s)] = (src, e, lv)
            return e, lv
    sys.exit(f"상대 Elo 없음: {opp} {s}")

# ---------------------------------------------------------------- 출전
games = [g for g in csv.DictReader(open(os.path.join(RAW, "tm_games.csv"), encoding="utf-8")) if g["category"] == "senior"]
G = {g["gameId"]: g for g in games}
M = []
for g in sorted(games, key=lambda g: (g["date_local"], g["gameId"])):
    M.append([g["date_local"], g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 골·도움
ev = list(csv.DictReader(open(os.path.join(RAW, "barcola_goal_assist_events.csv"), encoding="utf-8")))

def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
for e in ev:
    gid, mstr = e["gameId"], e["minute_tm"]
    g = G[gid]
    tag = f"{gid}|{mstr}"
    role = "goal" if e["role"] == "scorer" else e["role"]
    if role not in ("goal", "assist"): sys.exit("역할 " + e["role"])
    if e["ownGoal_tm"] == "True" and role == "goal": sys.exit("자책골 " + tag)
    if role == "assist":
        if tag in EXCL_A:
            judg.append(("도움 제외", e["date_local"], e["opponent"], mstr, e["scorer_tm"], EXCL_A[tag])); continue
        if e["ownGoal_tm"] == "True": sys.exit("자책골 도움 판정 누락 " + tag)
        if "assist by Bradley Barcola" not in (e["fm_assistStr"] or "") and tag not in ADD_CONFIRMED:
            sys.exit("FotMob에 없는 도움 판정 누락: " + tag)
        if e["assistType_tm"] in ("Shot on goal", "Deflection") or e["assistType_tm"].startswith("Penalty"):
            sys.exit("도움 유형 판정 누락: " + tag)
    mi, dm = minute(mstr)
    ah, aa = map(int, e["score_after_home_away_tm"].split("-"))
    if e["side"] == "h": bh, ba = ah - 1, aa
    else: bh, ba = ah, aa - 1
    if e["side"] != e["venue"].lower(): sys.exit("득점 팀이 바르콜라 팀이 아님 " + tag)
    gf, ga = (bh, ba) if e["venue"] == "H" else (ba, bh)
    cid, rnd = g["competitionId"], g["round"]
    pk = 1 if (role == "goal" and e["penalty_tm"] == "True") else 0
    elo, lv = opp_elo(g["opponent"].strip(), e["date_local"])
    tie = TIES.get(gid)
    if ("leg" in rnd.lower()) != bool(tie):
        sys.exit("합산 표 누락: " + gid + " " + rnd)
    row = ["g" if role == "goal" else "a", g["opponent"].strip(), elo, comp_of(cid, rnd), mi, gf, ga, ko_of(cid, rnd), pk,
           e["date_local"], 0, dm, lv, 0 if role == "goal" else e["scorer_tm"]]
    if tie: row.append(list(tie))
    rows.append(row)

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))
for r in rows:
    if r[7] and r[4] > 95: sys.exit("연장 골 판정 필요: " + str(r))
E = rows

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return json.loads(m.group(1))
mates = {"Alexandre Lacazette": load_js("lac.js", "LAC"), "Kylian Mbappé": load_js("mba.js", "MBA"),
         "Khvicha Kvaratskhelia": load_js("kva.js", "KVA"), "Mohamed Salah": load_js("sal.js", "SAL")}
SPAN = {"Alexandre Lacazette": ("2021-11-01", "2023-08-31"), "Kylian Mbappé": ("2023-08-31", "2024-07-01"),
        "Khvicha Kvaratskhelia": ("2025-01-17", "2026-08-31"), "Mohamed Salah": ("2026-08-31", "2099")}
cross, mism = [], []
for r in E:
    if r[0] == "a" and r[13] in mates:
        hit = [x for x in mates[r[13]] if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
        cross.append(["바르콜라 도움→동료 골", r[9], r[13], r[4], "있음" if hit else "없음"])
        if not hit: mism.append(("동료 골 없음", r[9], r[13], r[4]))
        for x in hit:
            if (x[2], x[12], x[3], x[5], x[6], x[7]) != (r[2], r[12], r[3], r[5], r[6], r[7]) or x[14:] != r[14:]:
                mism.append(("값 다름", r[9], r[13], x[2:8], x[12], x[14:], r[2:8], r[12], r[14:]))
for nm, ent in mates.items():
    a, b = SPAN[nm]
    for x in ent:
        if x[0] == "a" and "Barcola" in str(x[13]):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            cross.append(["동료 도움→바르콜라 골", x[9], nm, x[4], "있음" if hit else "없음"])
            if not hit: mism.append(("바르콜라 골 없음", x[9], nm, x[4]))
            for r in hit:
                if (x[2], x[12], x[3], x[5], x[6]) != (r[2], r[12], r[3], r[5], r[6]):
                    mism.append(("값 다름", x[9], nm, x[2:8], x[12], r[2:8], r[12]))
        # 같은 날 같은 상대: Elo·lv·대회 같아야
        if a <= x[9] < b:
            for r in E:
                if r[9] == x[9] and key(r[1]) == key(x[1]) and (x[2], x[12], x[3]) != (r[2], r[12], r[3]):
                    mism.append(("같은 경기 Elo/lv/대회 다름", r[9], nm, x[1], x[2], x[12], x[3], r[1], r[2], r[12], r[3]))
        # 같은 날 동료 골 중 바르콜라 TM 도움이 있었는데 뺀 것 확인용
for m in mism: print("대조:", m)

# ---------------------------------------------------------------- 클럽별 합계
CLUBS = [("2023-08-31", "리옹"), ("2026-08-31", "PSG"), ("9999-12-31", "리버풀")]
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
ST = collections.OrderedDict((n, [0, 0, 0]) for _, n in CLUBS)
MINC = collections.Counter()
for m in M: ST[club_of(m[0])][0] += 1; MINC[club_of(m[0])] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
MIN_TOT = sum(m[3] for m in M)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v))
KO = {"AC Sparta Praha": "스파르타 프라하", "Crystal Palace": "크리스털 팰리스"}

NOTE_LINES = [
    f"브래들리 바르콜라(리옹·PSG·리버풀)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} {KO[M[0][1]]}전 ~ {d_(M[-1][0])} {KO[M[-1][1]]}전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    f"클럽별 경기·골·도움: 리옹 {c3(ST['리옹'])}(2021-23), PSG {c3(ST['PSG'])}(2023-26), 리버풀 {c3(ST['리버풀'])}(2026-27, 진행 중)",
    f"경기·출전 분·골 시간·골 직전 스코어는 Transfermarkt 선수 경기 성적(출전 {NG}경기·{MIN_TOT}분)과 경기 리포트 기준이고, FotMob 경기 기록과 골 수·시각·스코어가 모두 같음. 출전 시간 90분 추정 경기는 없음(FotMob과 1분 다른 경기 9개는 Transfermarkt를 씀)",
    "경기 수·골은 영어 위키백과 시즌별 기록(리옹 47경기 7골, PSG 152경기 39골, 리버풀 14경기 3골)과 FotMob 경력 합계와 모두 같음",
    "리옹 2군(내셔널 2, 22경기 5골)·리옹 U19와 UEFA 유스리그(21경기)·프랑스 대표팀 경기는 뺌. 2026.8.12 UEFA 슈퍼컵 애스턴 빌라전은 PSG 벤치에만 있었고 출전하지 않음",
    "PK 골은 없음(2025.9.17 챔스 아탈란타전에 PK 실축 1개, Transfermarkt 기준). 상대 자책골은 골로 세지 않음",
    "도움은 Transfermarkt 도움 52개 중 FotMob 경기 이벤트가 같이 적은 47개를 기준으로 하고, Transfermarkt에만 있는 도움은 다른 출처 2곳이 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 도움 52개 − 상대 자책골 유도 1개(2023.5.27 랭스전 2분 아그바두 자책골) − PK 유도 1개(2025.8.30 툴루즈전 51분 뎀벨레 PK)",
    "Transfermarkt에만 있지만 다른 출처 2곳이 확인해 넣은 도움 3개: 2023.1.21 쿠프 드 프랑스 샹베리전 67분 라카제트 골(Soccerway·ESPN 경기 기사, 바르콜라 크로스), 2025.1.15 쿠프 드 프랑스 에스팔리전 67분 두에 골(CulturePSG 문자중계·Soccerway 기사), 2025.3.29 생테티엔전 62분 주앙 네베스 골(리그1 공식 기사·Soccerway·생테티엔 구단 기사, 바르콜라 컷백). 세 개 모두 FotMob 선수 경기 목록에는 도움으로 있으나 FotMob 경기 이벤트에는 도움자가 비어 있음",
    "2026.2.1 스트라스부르전 22분 마율루 골은 Transfermarkt 도움 유형 칸이 비어 있으나 FotMob이 바르콜라 도움으로 적어 넣음. FotMob에만 있는 도움은 없음",
    "날짜는 경기 현지 날짜(2025 클럽 월드컵은 미국 현지 날짜)",
    "상대 Elo는 기존 선수 자료의 같은 팀·같은 시즌 값을 먼저 쓰고(라카제트·음바페·크바라츠헬리아 자료와 같은 경기는 같은 값), 없으면 그 시즌 최종 순위(FotMob 순위표, 2026-27은 11월 초 현재 순위)를 기존 리그 모형에 넣음: 리그1 2024-25 랑스 8위, 2025-26 릴 3위·오세르 15위, 리그2(프랑스 2부) 2022-23 메스 2위·그르노블 10위·2024-25 됭케르크 4위, 프리미어리그 2026-27 브라이턴 2위·브렌트퍼드 8위(크리스털 팰리스 2026-27은 다른 선수 자료의 10월 말 순위 값 1743을 그대로 씀)",
    "순위표·모형에 없는 상대는 당시 수준을 추정함(모두 '추정'): 스파르타 프라하 2021-22 1550(체코 3위, 다른 선수 자료의 체코 1·2위 팀 1560~1600보다 낮게), 에스팔리 2024-25 1150(프랑스 5부, 다른 선수 자료와 같은 수준), 스타드 브리오섕 2024-25 1220(프랑스 4부), 르망 2024-25 1350(프랑스 3부 내셔널 2위, 음바페 자료 오를레앙과 같은 수준), LASK 2026-27 1539(오스트리아 11월 초 현재 3위, 다른 선수 자료 2023-24 3위 값)",
    "쿠프 드 프랑스·잉글랜드 리그컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중, 쿠프 드 프랑스 준결승은 단판), 트로페 데 샹피옹·UEFA 슈퍼컵은 국내컵 결승으로, 클럽 월드컵·인터콘티넨털컵은 클럽 월드컵 비중으로 계산함. 2025 클럽 월드컵 조별리그는 리그식(무승부 1점), 16강부터 단판. 챔스 리그 단계는 조별과 같고, 녹아웃 플레이오프는 16강으로 계산함",
    f"두 경기 합산(챔스 녹아웃 플레이오프·16강·8강) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(2021-22부터 원정 다득점 없음, 연장 있음). 2026.4.14 챔스 8강 2차전 리버풀전은 바르콜라가 뛰지 않은 1차전 스코어 2-0(Transfermarkt)을 넣음",
    "승부차기로 끝난 경기(2023.2.8 릴전·2024.12.22 랑스전 쿠프 드 프랑스, 2025.3.11 챔스 리버풀전, 2025.8.13 UEFA 슈퍼컵, 2025.12.17 인터콘티넨털컵, 2026.1.8 트로페 데 샹피옹, 2026.5.30 챔스 결승, 2026.10.28 리그컵 첼시전)은 연장까지의 스코어를 쓰고 출전 분은 Transfermarkt 그대로. 2026.1.8 트로페 데 샹피옹 마르세유전 90+5분 하무스 동점 골 도움은 정규시간 기록. 연장 시간 골·도움은 없음",
    "시즌은 8월 1일 기준(2025년 6~7월 클럽 월드컵은 2024-25, 크바라츠헬리아 자료와 같음)",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 프랑스 대표팀(유로 2024 참가)·리옹 U19 쿠프 강바르델라(FotMob에만 있음)는 뺌. 2026-27 UEFA 슈퍼컵은 PSG 벤치에만 있었으나 Transfermarkt 표기대로 셈. 2025 클럽 월드컵 준우승은 Transfermarkt 업적에 없어 넣지 않음",
    f"2026.11.11 기준: 리버풀 2026.8.31 입단, 마지막 출전은 2026.11.8 크리스털 팰리스전",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "cwc", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM"]:
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
for d, rs in by.items():
    prev = None
    for r in rs:   # 이미 시간순(45+x는 전반 끝) 정렬
        sc = (r[5], r[6])
        if prev and (sc[0] < prev[0] or sc[1] < prev[1]): problems.append(("스코어 역순", d, r[4]))
        prev = sc
    if not any(m[0] == d for m in M): problems.append(("출전 없음", d))
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분", m))
for p in problems: print("점검:", p)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
js = f"const BCL_E={J(E)};\nconst BCL_M={J(M)};\nconst BCL_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "excluded": judg, "cross_check": cross,
           "mismatch": mism, "elo_sources": ELO_SRC, "elo_log": {f"{k[0]}|{k[1]}": v for k, v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v, MINC[n], "분")
print("점검 문제", len(problems), "· 대조 불일치", len(mism))
