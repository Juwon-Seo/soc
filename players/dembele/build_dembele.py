#!/usr/bin/env python3
"""Ousmane Dembélé: raw/ -> dembele.json + src/data/dem.js (판정은 judgments.md)

  python3 players/dembele/build_dembele.py

입력: raw/tm_games.csv(출전 409경기, level=senior), raw/dem_goal_assist_events.csv(골·도움, TM 리포트+FotMob 이벤트),
      raw/tm_match_info.csv·tm_two_leg_ties.csv(합산 다른 차전), raw/ranks.txt(TM 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv(기존 선수 팀×시즌 값),
      src/data/*.js(같은 경기 동료·다른 선수 자료 대조, 새로 만드는 자료 파일은 뺌).
"""
import csv, json, os, re, sys, unicodedata, collections, glob

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "dem.js")
OUT_JSON = os.path.join(HERE, "dembele.json")
SKIP_FILES = {"dem.js", "hon.js", "gna.js", "mer.js", "nis.js", "luc.js"}   # 이 선수·동시에 작업 중인 새 선수 파일

# ---------------------------------------------------------------- 판정 표
# Transfermarkt 도움이지만 넣지 않는 것: gameId|분 -> 이유
EXCL_A = {
    "2899862|11": "'Shot on goal'(쿠티뉴 리바운드 골) - FotMob도 도움 없음",
    "4094686|18": "'Shot on goal'(하무스 리바운드 골) - FotMob도 도움 없음",
    "4094686|39": "PK 유도(음바페 PK) - FotMob도 도움 없음",
    "4312028|61": "PK 유도(음바페 PK) - FotMob도 도움 없음",
    "4363761|33": "PK 유도(비티냐 PK) - FotMob도 도움 없음",
    "2704524|48": "Transfermarkt에만 있음. FotMob(Opta)·Sporting Life 해설은 긴터 도움, BVB 공식 리포트도 뎀벨레 크로스를 긴터가 머리로 떨궈 피슈체크가 넣었다고 서술 → 마지막 패스는 긴터, 확인 출처 2곳 없음",
    "4363798|52": "Transfermarkt에만 있음. LFP 경기위원회가 2024.10.9 니스 봄비토 자책골로 정정(FotMob·ESPN도 자책골) → 상대 자책골 유도",
}
# FotMob 이벤트에 없지만 다른 출처 2곳이 확인해 넣는 Transfermarkt 도움
ADD_CONFIRMED = {
    "4778403|25": "ESPN 경기 보고서('assisted by Ousmane Dembélé with a through ball')·Maxifoot/CulturePSG 경기 기사(뎀벨레가 오른쪽에서 침투 패스, 두에 마무리)",
}
# FotMob에만 있는 도움(Transfermarkt 없음): 판정
FM_ONLY = [
    # (넣음?, gameId, date, opp, venue, minute, score_after(home-away), scorer, 이유)
    (True, "3079491", "2018-12-08", "RCD Espanyol Barcelona", "A", "45", "0-3", "Luis Suárez",
     "FotMob 이벤트 + ESPN 경기 기록(assisted by Ousmane Dembélé) + FC 바르셀로나 공식 리포트(뎀벨레의 공간 패스를 수아레스가 마무리)"),
    (False, "4171285", "2023-10-25", "AC Milan", "H", "53", "2-0", "Randal Kolo Muani",
     "FotMob에만 있음. AC 밀란 공식 리포트·Soccerway 기사: 뎀벨레 슈팅을 메냥이 쳐낸 것을 콜로 무아니가 밀어 넣음(리바운드) → 'Shot on goal'과 같은 경우라 제외"),
]

# ---------------------------------------------------------------- 대회 코드
LEAGUES = ("FR1", "L1", "ES1")

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUES: return "lg"
    if cid in ("FRC", "DFB", "CDR"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                          # 1·2라운드·64강·32강·16강(코파 2018-19 32강 'intermediate stage' 포함)
    if cid == "FRL": return "dc"             # 쿠프 드 라 리그 16강
    if cid in ("FRCH", "USC", "DFL"): return "df"
    if cid == "SUC":
        return "dsf" if r.startswith("semi") else "df"   # 4팀 수페르코파 준결승
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
        return "elk"                          # 녹아웃 PO('intermediate stage')·16강·8강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUES: return 0
    if r.startswith("group"): return 0
    return 1

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# ---------------------------------------------------------------- 출전
games = [g for g in csv.DictReader(open(os.path.join(RAW, "tm_games.csv"), encoding="utf-8")) if g["level"] == "senior"]
G = {g["gameId"]: g for g in games}
M = []
for g in sorted(games, key=lambda g: (g["date_local"], g["gameId"])):
    M.append([g["date_local"], g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 합산(두 경기) 다른 차전
INFO = {r["gameId"]: r for r in csv.DictReader(open(os.path.join(RAW, "tm_match_info.csv"), encoding="utf-8"))}
TL = {r["gameId"]: r for r in csv.DictReader(open(os.path.join(RAW, "tm_two_leg_ties.csv"), encoding="utf-8"))}
CLUB_IDS = {"273", "16", "131", "583"}

def ours_theirs(gid):
    r = INFO[gid]
    h, a = map(int, r["final"].split(":"))
    if r["home_id"] in CLUB_IDS: return h, a
    if r["away_id"] in CLUB_IDS: return a, h
    sys.exit("우리 팀 없음 " + gid)

def tie_of(gid):
    g = G[gid]
    rnd = g["round"].lower()
    if "leg" not in rnd: return None
    leg = 1 if "1st" in rnd else 2
    home = 1 if g["venue"] == "H" else 0
    s = season_eu(g["date_local"])
    if g["competitionId"] in ("CL", "EL"): ag = 1 if s <= "2020-21" else 0
    elif g["competitionId"] == "CDR": ag = 1 if s <= "2018-19" else 0
    else: sys.exit("합산 규칙 없음 " + gid)
    et = 1
    if leg == 1: return [1, home, 0, 0, ag, et]
    o = TL[gid]["other_leg_id"]
    fo, ft = ours_theirs(o)
    return [2, home, fo, ft, ag, et]

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

GENERIC = {"fc", "cf", "ac", "sc", "as", "ss", "ssc", "rc", "sv", "vfl", "vfb", "tsg", "ca", "ud", "cd", "rcd", "sd", "club",
           "de", "real", "hsc", "ogc", "losc", "the", "afc", "us", "1", "04", "05", "29", "1899", "1846", "01", "football", "foot"}
def toks(n):
    return {t for t in norm(n).split() if t not in GENERIC and not t.isdigit()}
def same_team(a, b):
    if key(a) == key(b): return True
    ta, tb = toks(a), toks(b)
    if ta and tb and (ta <= tb or tb <= ta): return True
    # 접미 차이(Ferencvaros / Ferencvárosi TC): 6자 이상 토큰이 서로 앞부분으로 같으면 같은 팀
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return bool(small) and all(any(len(x) >= 6 and len(y) >= 6 and (x.startswith(y) or y.startswith(x)) for y in big) for x in small)

TABLE = {}
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

# 다른 선수 자료(같은 날·같은 상대)
def load_js(path):
    s = open(path, encoding="utf-8").read()
    P = os.path.basename(path)[:-3].upper()
    m = re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S)
    return P, json.loads(m.group(1))
OTHERS = {}
for p in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    if os.path.basename(p) in SKIP_FILES: continue
    P, E = load_js(p)
    OTHERS[P] = E
BYDATE = collections.defaultdict(list)
for P, E in OTHERS.items():
    for x in E: BYDATE[x[9]].append((P, x))

# 리그1 18팀 고정 순위값(기존 자료), 프리미어리그 2025-26 이후 순위값(바르콜라 자료와 같음)
L1_18 = [1955, 1866, 1817, 1786, 1771, 1757, 1738, 1718, 1700, 1687, 1677, 1667, 1662, 1647, 1628, 1612, 1603, 1582]
PL = [2083, 1998, 1951, 1917, 1901, 1889, 1875, 1857, 1839, 1822, 1811, 1802, 1792, 1787, 1778, 1762, 1743, 1731, 1723, 1703]
NOW = "(11월 초 현재)"
RANKED = {   # raw/ranks.txt(TM 순위표, 2026-27은 2026.11.11 받은 진행 중 순위)
    (key("Stade Brestois 29"), "2026-27"): (L1_18[8], f"리그1 2026-27 {NOW} 9위"),
    (key("RC Strasbourg Alsace"), "2026-27"): (L1_18[12], f"리그1 2026-27 {NOW} 13위"),
    (key("Manchester City"), "2026-27"): (PL[2], f"프리미어리그 2026-27 {NOW} 3위"),
}
MAN = {   # 순위표·모형에 없는 상대(직접 추정, 모두 '추정')
    (key("Sportfreunde Lotte"), "2016-17"): (1414, "독일 3부 리가 2016-17 12위 (추정)"),
    (key("Cultural Leonesa"), "2018-19"): (1350, "스페인 3부(세군다 B) 2018-19 1조 5위 (추정)"),
    (key("UE Cornellà"), "2020-21"): (1350, "스페인 3부(세군다 B) 2020-21 (추정)"),
    (key("Linares Deportivo"), "2021-22"): (1350, "스페인 3부(프리메라 페데라시온) 2021-22 2조 5위 (추정)"),
    (key("Vendée Fontenay Foot"), "2025-26"): (1220, "프랑스 4부(내셔널 2) 2025-26 B조 6위 (추정)"),
    (key("Slovan Bratislava"), "2026-27"): (1500, f"슬로바키아 2026-27 {NOW} 2위 (추정)"),
}

NAME2P = {"Pierre-Emerick Aubameyang": "AUB", "Marco Reus": "REU", "Lionel Messi": "MES", "Luis Suárez": "SUA",
          "Antoine Griezmann": "GRZ", "Robert Lewandowski": "LEW", "Raphinha": "RAP", "Lamine Yamal": "YAM",
          "Kylian Mbappé": "MBA", "Bradley Barcola": "BCL", "Khvicha Kvaratskhelia": "KVA"}
ELO_SRC = collections.Counter()
ELO_LOG = {}

def opp_elo(opp, date):
    s = season_eu(date)
    same = [(P, x) for P, x in BYDATE.get(date, []) if same_team(x[1], opp)]
    vals = {(x[2], x[12]) for P, x in same}
    if len(vals) > 1:   # 같은 팀 동료 자료 값을 우선
        mates = set(NAME2P.values())
        vals = {(x[2], x[12]) for P, x in same if P in mates}
    if len(vals) > 1: sys.exit(f"같은 경기 값이 여럿: {opp} {date} {vals}")
    if vals:
        e, lv = vals.pop()
        ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(opp, date)] = ("같은 경기", e, lv, sorted({P + ":" + x[1] for P, x in same}))
        return e, lv
    k = key(opp)
    for src, tab in (("기존 팀×시즌 값", TABLE), ("순위표+리그 모형", RANKED), ("직접 추정", MAN)):
        if (k, s) in tab:
            e, lv = tab[(k, s)]
            ELO_SRC[src] += 1; ELO_LOG[(opp, date)] = (src, e, lv)
            return e, lv
    sys.exit(f"상대 Elo 없음: {opp} {s} {date}")

# ---------------------------------------------------------------- 골·도움
ev = list(csv.DictReader(open(os.path.join(RAW, "dem_goal_assist_events.csv"), encoding="utf-8")))
for (inc, gid, d, opp, venue, mstr, sc, scorer, why) in FM_ONLY:
    g = G[gid]
    assert g["date_local"] == d and g["opponent"].strip() == opp and g["venue"] == venue, gid
    ev.append({"gameId": gid, "date_local": d, "dem_role": "assist" if inc else "fm_only_excluded", "minute_tm": mstr,
               "score_after_home_away": sc, "scorer": scorer, "assist_type_tm": "", "penalty": "0", "own_goal": "0",
               "fm_assistStr": "assist by Ousmane Dembélé", "venue": venue, "opponent": opp, "_fm_only": why})

def minute(s, et_game):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s, 0
    v = int(s)
    if v > 90:
        if not et_game: sys.exit("연장 아닌 경기 90분 넘음 " + s)
        return v, 0, 1
    return v, 0, 0

rows, judg = [], []
for e in ev:
    gid, mstr = e["gameId"], e["minute_tm"]
    g = G[gid]
    tag = f"{gid}|{mstr}"
    role = e["dem_role"]
    if role == "fm_only_excluded":
        judg.append(("도움 제외(FotMob에만)", e["date_local"], e["opponent"], mstr, e["scorer"], e["_fm_only"])); continue
    if role not in ("goal", "assist"): sys.exit("역할 " + role)
    if role == "goal" and e["own_goal"] == "1": sys.exit("자책골 " + tag)
    if role == "assist":
        if tag in EXCL_A:
            judg.append(("도움 제외", e["date_local"], e["opponent"], mstr, e["scorer"], EXCL_A[tag])); continue
        if "_fm_only" in e:
            judg.append(("도움 추가(FotMob에만)", e["date_local"], e["opponent"], mstr, e["scorer"], e["_fm_only"]))
        elif "dembele" not in norm(e["fm_assistStr"]):
            if tag not in ADD_CONFIRMED: sys.exit("FotMob에 없는 도움 판정 누락: " + tag)
            judg.append(("도움 넣음(TM+다른 출처 2곳)", e["date_local"], e["opponent"], mstr, e["scorer"], ADD_CONFIRMED[tag]))
        if e["assist_type_tm"] in ("Shot on goal", "Deflection") or e["assist_type_tm"].startswith("Penalty"):
            sys.exit("도움 유형 판정 누락: " + tag)
    et_game = g["gameState"] in ("extra_time", "penalty_shootout")
    mi, dm, et = minute(mstr, et_game)
    ah, aa = map(int, e["score_after_home_away"].split("-"))
    if g["venue"] == "H": bh, ba = ah - 1, aa
    else: bh, ba = ah, aa - 1
    gf, ga = (bh, ba) if g["venue"] == "H" else (ba, bh)
    if min(gf, ga) < 0: sys.exit("스코어 " + tag)
    cid, rnd = g["competitionId"], g["round"]
    pk = 1 if (role == "goal" and e["penalty"] == "1") else 0
    elo, lv = opp_elo(g["opponent"].strip(), e["date_local"])
    tie = tie_of(gid)
    if tie and et: sys.exit("합산 연장 골 판정 필요 " + tag)
    row = ["g" if role == "goal" else "a", g["opponent"].strip(), elo, comp_of(cid, rnd), mi, gf, ga, ko_of(cid, rnd), pk,
           e["date_local"], et, dm, lv, 0 if role == "goal" else e["scorer"]]
    if tie: row.append(tie)
    rows.append(row)

def sk(r):
    m = r[4]
    if r[11] and str(r[11]).startswith("45+"): m = 45.5
    return (r[9], m)
rows.sort(key=sk)
E = rows

# ---------------------------------------------------------------- 다른 선수 자료 대조
cross, mism = [], []
for r in E:
    if r[0] == "a" and r[13] in NAME2P:
        P = NAME2P[r[13]]
        hit = [x for x in OTHERS[P] if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
        hit = [x for x in hit if x[4] == r[4]] or hit
        cross.append(["뎀벨레 도움→동료 골", r[9], r[13], r[4], "있음" if hit else "없음"])
        if not hit: mism.append(("동료 골 없음", r[9], r[13], r[4]))
        for x in hit:
            if (x[2], x[12], x[3], x[5], x[6], x[7], x[10]) != (r[2], r[12], r[3], r[5], r[6], r[7], r[10]) or x[14:] != r[14:] or x[4] != r[4]:
                mism.append(("값 다름", r[9], r[13], "동료", x[2:8], x[12], x[14:], "뎀벨레", r[2:8], r[12], r[14:]))
for P, Es in OTHERS.items():
    for x in Es:
        if x[0] == "a" and re.search(r"Ousmane Demb[eé]l[eé]", str(x[13])):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            hit = [r for r in hit if r[4] == x[4]] or hit
            cross.append(["동료 도움→뎀벨레 골", x[9], P, x[4], "있음" if hit else "없음"])
            if not hit: mism.append(("뎀벨레 골 없음", x[9], P, x[4], x[1]))
            for r in hit:
                if (x[2], x[12], x[3], x[5], x[6], x[7], x[4]) != (r[2], r[12], r[3], r[5], r[6], r[7], r[4]) or x[14:] != r[14:]:
                    mism.append(("값 다름", x[9], P, "동료", x[2:8], x[12], x[14:], "뎀벨레", r[2:8], r[12], r[14:]))
# 같은 날 같은 상대: 대회·ko·tie(같은 경기면 같아야)
for r in E:
    for P, x in BYDATE.get(r[9], []):
        if same_team(x[1], r[1]) and ((x[3], x[7]) != (r[3], r[7]) or (len(x) > 14) != (len(r) > 14) or (len(x) > 14 and x[14][:2] + x[14][4:] != r[14][:2] + r[14][4:])):
            mism.append(("같은 경기 대회·단판·합산 다름", r[9], P, x[1], x[3], x[7], x[14:], r[3], r[7], r[14:]))
# 동료 골 중 뎀벨레 TM 도움이 없는 같은 경기 기록(참고): 동료 파일 'a'가 아닌데 뎀벨레가 득점자로 적힌 경우 없음
for m in mism: print("대조:", m)

# ---------------------------------------------------------------- 클럽별 합계
CLUBS = [("2016-07-01", "렌"), ("2017-08-25", "도르트문트"), ("2023-08-12", "바르셀로나"), ("9999-12-31", "PSG")]
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
def c3(v): return "·".join(map(str, v))

NOTE_LINES = [
    f"우스만 뎀벨레(렌·도르트문트·바르셀로나·PSG)의 클럽 공식 경기 {NG}경기(2015.11.6 앙제전 ~ 2026.10.20 바르셀로나전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    f"클럽별 경기·골·도움: 렌 {c3(ST['렌'])}(2015-16), 도르트문트 {c3(ST['도르트문트'])}(2016-17), 바르셀로나 {c3(ST['바르셀로나'])}(2017-23), PSG {c3(ST['PSG'])}(2023~, 진행 중)",
    f"경기·출전 분·골 시간·골 직전 스코어는 Transfermarkt 선수 경기 성적(출전 {NG}경기·{MIN_TOT}분)과 경기 리포트 기준이고, FotMob 경기 기록과 골 수·스코어가 모두 같음(골 시각 1분 차이 몇 개는 Transfermarkt를 씀). 출전 시간 90분 추정 경기는 없음",
    "경기 수·골은 영어 위키백과 시즌·대회별 기록과 모든 칸이 같음(렌 29경기 12골, 도르트문트 50경기 10골, 바르셀로나 185경기 40골, PSG 145경기 65골)",
    "렌 2군(5부 CFA 2, 22경기 13골)·유스·프랑스 대표팀 경기는 뺌. FotMob 경력에만 있는 2018 카탈루냐 슈퍼컵(수페르코파 데 카탈루냐) 1경기는 Transfermarkt·위키백과에 없는 지역 대회라 뺌",
    f"PK 골 {NPK}개(Transfermarkt·FotMob 같음). 상대 자책골은 골로 세지 않음",
    "도움은 Transfermarkt 도움 116개 중 FotMob 경기 이벤트가 같이 적은 것을 기준으로 하고, 한쪽에만 있는 도움은 다른 출처 2곳이 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 116개 − PK 유도 3개(2023.11.24 모나코전 39분 음바페, 2024.4.16 챔스 바르셀로나전 61분 음바페, 2024.9.1 릴전 33분 비티냐) − 슈팅 리바운드('Shot on goal') 2개(2018.5.9 비야레알전 11분 쿠티뉴, 2023.11.24 모나코전 18분 하무스) − 확인 안 된 도움 2개 + FotMob에만 있는 도움 1개",
    "뺀 Transfermarkt 도움: 2017.2.18 볼프스부르크전 48분 피슈체크 골(FotMob·Sporting Life 해설은 긴터 도움, 도르트문트 구단 리포트도 뎀벨레 크로스를 긴터가 머리로 떨군 것으로 서술), 2024.10.6 니스전 52분(리그 사무국이 누누 멘드스 골을 니스 봄비토 자책골로 정정 — 상대 자책골 유도)",
    "Transfermarkt에만 있지만 넣은 도움: 2025.12.20 쿠프 드 프랑스 방데 퐁트네전 25분 두에 골(ESPN 경기 기록·Maxifoot·CulturePSG 기사, 뎀벨레 침투 패스)",
    "FotMob에만 있는 도움: 2018.12.8 에스파뇰전 45분 수아레스 골은 ESPN 경기 기록·FC 바르셀로나 공식 리포트(뎀벨레의 공간 패스)로 확인해 넣음. 2023.10.25 챔스 밀란전 53분 콜로 무아니 골은 뎀벨레 슈팅을 골키퍼가 쳐낸 리바운드라(AC 밀란 리포트·Soccerway 기사) 넣지 않음",
    "날짜는 경기 현지 날짜(2025 클럽 월드컵은 미국 현지, 2025 인터콘티넨털컵은 카타르 현지)",
    "상대 Elo는 같은 경기를 다룬 다른 선수 자료(오바메양·로이스·메시·수아레스·그리즈만·레반도프스키·하피냐·음바페·바르콜라·크바라츠헬리아 등)의 값을 먼저 쓰고, 없으면 기존 선수 자료의 같은 팀·같은 시즌 값, 그다음 그 시즌 순위(2026-27은 11월 초 현재 순위)를 기존 리그 모형에 넣음: 리그1 2026-27 브레스트 9위·스트라스부르 13위, 프리미어리그 2026-27 맨시티 3위",
    "순위표·모형에 없는 상대는 당시 수준을 추정함(모두 '추정'): 슈포르트프로인데 로테 2016-17 1414(독일 3부 리가 12위, 다른 선수 자료의 3부 리가 9위 1429·13위 1409 사이), 쿨투랄 레오네사 2018-19·UE 코르네야 2020-21·리나레스 2021-22 1350(스페인 3부, 다른 선수 자료와 같은 수준), 방데 퐁트네 2025-26 1220(프랑스 4부 내셔널 2, 다른 선수 자료와 같은 수준), 슬로반 브라티슬라바 2026-27 1500(슬로바키아 11월 초 현재 2위, 다른 선수 자료 2024-25 값)",
    "쿠프 드 프랑스·쿠프 드 라 리그·DFB-포칼·코파 델 레이는 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중, 준결승 단판·합산), 트로페 데 샹피옹·DFL-슈퍼컵·UEFA 슈퍼컵과 수페르코파 결승은 국내컵 결승, 4팀 수페르코파 준결승은 국내컵 준결승으로, 클럽 월드컵·인터콘티넨털컵은 클럽 월드컵 비중으로 계산함. 2025 클럽 월드컵은 16강부터만 뛰어 모두 단판. 챔스 리그 단계는 조별과 같고 녹아웃 플레이오프는 16강으로, 유로파 녹아웃 플레이오프는 유로파 토너먼트로 계산함",
    f"두 경기 합산(챔스 녹아웃·코파 델 레이) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회 2020-21까지, 코파 델 레이 2018-19까지 적용, 연장 있음. 뎀벨레가 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 넣음(2018 첼시 1차전 1-1, 2019 코파 준결승 레알 마드리드 1차전 1-1)",
    "2021.1.21 코파 델 레이 코르네야전 92분 골은 연장 전반 골이라 연장 시간으로 계산함. 승부차기로 끝난 경기는 연장까지의 스코어를 쓰고 출전 분은 Transfermarkt 그대로",
    "시즌은 8월 1일 기준(2025년 6~7월 클럽 월드컵은 2024-25, 바르콜라·크바라츠헬리아 자료와 같음)",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준: 2018 월드컵(대표팀)·VDV 신인상·Transfermarkt 시즌 선수는 뺌. 2026.8.16 트로페 데 샹피옹은 랑스에 져서 우승 아님",
    "2026.11.11 기준: 마지막 출전은 2026.10.20 챔스 바르셀로나전(20분), 그 뒤 허벅지 부상으로 결장 중",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "cwc", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE):
        sys.exit("설명에 작업용 표현: " + bad)
assert M[0][1] == "Angers SCO" and M[0][0] == "2015-11-06" and M[-1][0] == "2026-10-20" and M[-1][1] == "FC Barcelona", (M[0], M[-1])

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
    for r in rs:
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
js = f"const DEM_E={J(E)};\nconst DEM_M={J(M)};\nconst DEM_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": cross,
           "mismatch": [list(map(str, m)) for m in mism], "elo_sources": ELO_SRC,
           "elo_log": {f"{k[0]}|{k[1]}": v for k, v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v, MINC[n], "분")
print("점검 문제", len(problems), "· 대조 불일치", len(mism))
