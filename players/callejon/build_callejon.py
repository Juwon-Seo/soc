#!/usr/bin/env python3
"""호세 카예혼: raw/ -> callejon.json + src/data/cal.js (판정은 judgments.md)

  python3 players/callejon/build_callejon.py
"""
import csv, json, os, re, sys, unicodedata, collections

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "cal.js")
OUT_JSON = os.path.join(HERE, "callejon.json")
GAP = "2014-08-01"
RESERVE = "reserve"     # 레알 마드리드 카스티야(ES3A·ES2 2006-07) 40경기 제외

# ---------------------------------------------------------------- 도움 판정
# 도움 제외: gameId|분 -> 이유 (유형 규칙으로 자동 제외되는 PK 유도·Shot on goal·자책골 유도는 아래에서 처리)
EXCL_A = {
    "2726569|51": "2014.8 이후 Transfermarkt 단일 출처, 기사에서 도움자 확인 못 함(엠폴리 2016.10.26 메르턴스 51분; ESPN·Sports Mole 등은 도움자 미기재)",
    "2917375|7": "2014.8 이후 Transfermarkt 단일 출처, 기사 2곳 확인 못 함(페예노르트 2017.9.26 인시녜 7분)",
    "2897335|56": "2014.8 이후 Transfermarkt 단일 출처, 한 곳만 크로스 언급(라치오 2018.2.10 마리우 후이 56분; worldfootball은 도움 없음)",
    "3637800|51": "2014.8 이후 Transfermarkt 단일 출처, 두 번째 출처 확인 못 함(코센차 2021.8.13 베누티 51분)",
    "3850275|20": "2014.8 이후 Transfermarkt 단일 출처, 한 매체(노우디아리)만 확인(이비사 2023.1.21 빅토르 디아스 20분)",
    "4428551|53": "마르베야 도움: FotMob 도움 0, 기사 2곳 확인 못 함",
    "4428559|61": "마르베야 도움: FotMob 도움 0, 기사 2곳 확인 못 함",
    "4428653|68": "마르베야 도움: FotMob 도움 0, 기사 2곳 확인 못 함",
    "4428660|15": "마르베야 도움: FotMob 도움 0, 기사 2곳 확인 못 함",
    "4428694|33": "마르베야 도움: FotMob 도움 0, 기사 2곳 확인 못 함",
    "4428752|26": "마르베야 도움: FotMob 도움 0, 기사 2곳 확인 못 함",
    "4428776|80": "마르베야 도움: FotMob 도움 0, 기사 2곳 확인 못 함",
    "4428795|90+2": "마르베야 도움: FotMob 도움 0, 기사 2곳 확인 못 함",
    "4428814|13": "마르베야 도움: FotMob 도움 0, 기사 2곳 확인 못 함",
}
EXCL_A["4428488|68"] = "마르베야 도움: FotMob 도움 0, 기사 2곳 확인 못 함"
# 2014.8 이후 FotMob 도움이 없지만 다른 출처 2곳이 확인해 넣은 도움
ADD_CONFIRMED = {
    "3081249|26": "Fox Sports 경기 기록(Callejón 도움)·Anews(아나돌루) 경기 기사",
}
MIN_FIX = {}

# ---------------------------------------------------------------- 대회 코드
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in ("ES1", "ES2", "IT1", "E3G2"): return "lg"
    if cid in ("CDR", "CIT"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SUC", "SCI"): return "df"
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
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in ("ES1", "ES2", "IT1", "E3G2"): return 0
    if r.startswith("group"): return 0
    return 1

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
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(canon)
def key(n):
    k = norm(n); return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        TABLE[(key(r["팀"]), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))
# 스페인 2부 22팀 순위별 기존 값(기존 자료의 세군다 값)
ES2 = {1: 1753, 2: 1712, 3: 1687, 4: 1674, 5: 1660, 6: 1654, 7: 1647, 8: 1640, 9: 1632, 10: 1623, 11: 1615,
       12: 1610, 13: 1606, 14: 1601, 15: 1598, 16: 1595, 17: 1589, 18: 1580, 19: 1572, 20: 1567, 21: 1560, 22: 1553}

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7])
    if d.startswith("2020-08"): return "2019-20"
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 직접 추정(모두 '추정')
MAN = {
    (key("Arosa SC"), "2023-24"): (1100, "스페인 5부(테르세라 페데라시온) (추정)"),
    # 세리에C(3부) 평균 1416.56·흩어짐 51.24에 세리에A 20칸 표준 곡선(2위/20팀) 적용 (인시녜 선례), 순위는 위키백과/Eurosport
    (key("Calcio Padova"), "2020-21"): (1501, "세리에C(레가 프로 1) B조 2020-21 2위/20팀 (추정)"),
}
# 스페인 3부 프리메라 페데라시온 2024-25 (기존 자료의 3부 평탄 값 1350)
P3 = "E3G2|2024-25"
ELO_SRC = collections.Counter()
def opp_elo(opp, date, cid):
    k = key(opp); s = season_eu(date)
    if (k, s) in TABLE:
        e, lv = collections.Counter(TABLE[(k, s)]).most_common(1)[0][0]
        ELO_SRC["기존 팀×시즌 값"] += 1; return e, lv
    if (k, s) in MAN:
        e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; return e, lv
    for (lg, ss), tab in RANKS.items():
        if ss == s and k in tab:
            r, n = tab[k]
            if lg == "ES2":
                ELO_SRC["순위표+기존 세군다 값"] += 1; return ES2[r], f"세군다 {s} {r}위"
            if lg == "E3G2":
                ELO_SRC["스페인 3부 평탄 추정"] += 1; return 1350, f"스페인 3부(프리메라 페데라시온) {s} {r}위 (추정)"
    sys.exit(f"상대 Elo 없음: {opp} {s}")

# ---------------------------------------------------------------- 출전
G = {}
games = [g for g in csv.DictReader(open(os.path.join(RAW, "tm_games.csv"), encoding="utf-8")) if g["level"] != RESERVE]
for g in games: G[g["gameId"]] = g
M = [[g["date_local"], g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])]
     for g in sorted(games, key=lambda g: (g["date_local"], g["gameId"]))]

# ---------------------------------------------------------------- 두 경기 합산
INFO = {m["gameId"]: m for m in csv.DictReader(open(os.path.join(RAW, "tm_match_info.csv"), encoding="utf-8"))}
OURS = {"RCD Espanyol Barcelona", "Real Madrid", "SSC Napoli", "ACF Fiorentina", "Granada CF", "Marbella FC"}
def tie_of(gid, cid, rnd, date):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정골, 연장]"""
    g = G[gid]; r = rnd.lower()
    leg = 1 if "1st" in r else 2
    home = 1 if g["venue"] == "H" else 0
    # 원정 다득점: UEFA 2020-21까지, 코파 델 레이·수페르코파 2018-19까지, 코파 이탈리아 2021-22까지
    y = int(date[:4]); m = int(date[5:7]); s0 = y if m >= 8 else y - 1
    ag = 1
    if cid in ("CL", "EL", "CLQ") and s0 >= 2021: ag = 0
    if cid in ("CDR", "SUC") and s0 >= 2019: ag = 0
    et = 1
    if cid == "CIT" and date == "2020-06-13": et = 0       # 2019-20 준결승 2차전(재개): 연장 없이 승부차기
    if leg == 1: return [1, home, 0, 0, ag, et]
    info = INFO[gid]
    oid = info["other_leg_id"]
    oi = INFO.get(oid)
    if not oi: sys.exit("다른 차전 리포트 없음 " + gid)
    hs, as_ = map(int, oi["final"].split(":"))
    ours_home_first = oi["home"] in OURS
    f_ours, f_theirs = (hs, as_) if ours_home_first else (as_, hs)
    return [2, home, f_ours, f_theirs, ag, et]

# ---------------------------------------------------------------- 골·도움
ev = [e for e in csv.DictReader(open(os.path.join(RAW, "callejon_goal_assist_events.csv"), encoding="utf-8")) if G.get(e["gameId"])]
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
for e in ev:
    gid, mstr = e["gameId"], e["minute_tm"]
    g = G[gid]; tag = f"{gid}|{mstr}"; role = e["cal_role"]
    if role == "goal" and e["own_goal"] == "1":
        judg.append(("골 제외(자책골)", e["date_local"], e["opponent"], mstr)); continue
    if role == "assist":
        why = None
        if e["own_goal"] == "1": why = "상대 자책골 유도"
        elif e["assist_type_tm"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type_tm"] == "Shot on goal": why = "Shot on goal(슈팅 리바운드)"
        elif tag in EXCL_A: why = EXCL_A[tag]
        elif e["date_local"] >= GAP and "Callej" not in (e["fm_assistStr"] or "") and tag not in ADD_CONFIRMED:
            sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락: " + tag)
        if why:
            judg.append(("도움 제외", e["date_local"], e["opponent"], mstr, e["scorer"], why)); continue
    mi, dm = minute(MIN_FIX.get(tag, mstr))
    bh, ba = map(int, e["score_after_home_away"].split("-"))
    # 우리 팀이 넣은 골 하나를 뺀 골 직전 스코어
    if e["venue"] == "H": bh -= 1
    else: ba -= 1
    gf, ga = (bh, ba) if e["venue"] == "H" else (ba, bh)
    cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(g["opponent"].strip(), e["date_local"], cid)
    note = 0 if role == "goal" else e["scorer"]
    row = ["g" if role == "goal" else "a", g["opponent"].strip(), elo, comp, mi, gf, ga, ko, 0, e["date_local"], 0, dm, lv, note]
    if "leg" in rnd.lower(): row.append(tie_of(gid, cid, rnd, e["date_local"]))
    rows.append(row)
rows.sort(key=lambda r: (r[9], r[4], r[0]))
E = rows
for r in E:
    if r[7] and r[4] > 95 and len(r) <= 14: sys.exit("연장 골 판정 필요: " + str(r))

# ---------------------------------------------------------------- 클럽
CLUBS = [("2011-07-01", "에스파뇰"), ("2013-07-11", "레알 마드리드"), ("2020-10-05", "나폴리"), ("2022-07-25", "피오렌티나"),
         ("2024-07-23", "그라나다"), ("9999-12-31", "마르베야")]
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
ST = collections.OrderedDict((n, [0, 0, 0]) for _, n in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v))
PRE = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
TMA = sum(1 for e in ev if e["cal_role"] == "assist")
first, last = M[0], M[-1]

NOTE_LINES = [
    f"호세 카예혼(에스파뇰·레알 마드리드·나폴리·피오렌티나·그라나다·마르베야)의 클럽 공식 경기 {NG}경기({d_(first[0])} {first[1].replace('Deportivo de La Coruña','데포르티보')}전 ~ {d_(last[0])} {last[1]}전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n} {c3(ST[n])}" for _, n in CLUBS),
    f"경기·출전 분·골 시간·골 뒤 스코어는 Transfermarkt 선수 경기 성적(API, 출전 {NG}경기·{MIN_TOT}분)과 경기 리포트 기준이며 출전 시간 90분 추정 경기는 없음. 경기 수·골은 영어 위키백과의 시즌별 클럽 기록과 같음(스페인어 위키백과는 에스파뇰 2009-10·2010-11 골 수, 레알 마드리드 코파 경기 수, 나폴리 2014-15 코파·2019-20 리그 경기 수가 1~2씩 다름)",
    "레알 마드리드 카스티야(2군) 시절 40경기 21골(2006-07 세군다 4경기, 2007-08 세군다 B 36경기)과 스페인 U-21·스페인 대표팀 경기는 뺌",
    "PK 골은 없음(Transfermarkt 골 유형 기준)",
    "2023.11.2 코파 델 레이 1라운드 아로사전 Transfermarkt 리포트 머리글은 결과를 3:0(아로사 승)으로 거꾸로 적었으나 골 순서(0-1·0-2·0-3)와 실제 결과는 그라나다 3-0 승리",
    "2024.9.14 알헤시라스전 34분 골은 본인의 자책골로 골에서 뺌(마르베야 3-1 승)",
    "골 시각은 Transfermarkt 기준(FotMob과 1분 이내 차이만 있음). 2016.8.27 AC 밀란전 골은 Transfermarkt 90+3분, FotMob 90+4분이라 Transfermarkt를 씀",
    "도움은 2014.8.1 이전은 Transfermarkt 도움을 쓰고(FotMob 경기 이벤트에 도움이 거의 없음), 그 뒤는 FotMob 경기 이벤트와 Transfermarkt가 같이 적은 도움을 기준으로 함",
    f"도움 {NA}개 = Transfermarkt 도움 {TMA}개 − 제외 {TMA - NA}개. 제외한 것: 상대 자책골 유도 2개(2011.1.2 발렌시아전 리카르두 코스타, 2014.5.11 삼프도리아전 무스타피), PK 유도 8개(2011.1.9 사라고사 루이스 가르시아, 2014.9.18 스파르타 프라하·2014.12.18 파르마·2016.9.28 벤피카·2018.11.6 PSG·2019.9.17 리버풀·2019.12.10 헹크·2022.8.29 비야레알 B), 'Shot on goal' 리바운드 4개(2010.1.10 사라고사 마르케스, 2013.3.10 셀타 호날두, 2014.1.29 코파 이탈리아 라치오 이과인, 2015.5.18 체세나 메르턴스)",
    "2014.8 이후 Transfermarkt 단일 출처로 다른 출처 2곳이 확인하지 못해 뺀 도움: 2016.10.26 엠폴리전 51분 메르턴스 골(엠폴리·ESPN 등 기사는 도움자 미기재), 2017.9.26 챔스 페예노르트전 7분 인시녜 골(기사에 도움자 미기재), 2018.2.10 라치오전 56분 마리우 후이 골(한 곳만 크로스 언급), 2021.8.13 코파 이탈리아 코센차전 51분 베누티 골(한 곳만 확인), 2023.1.21 이비사전 20분 빅토르 디아스 골(코너킥 도움, 노우디아리 한 매체만 확인)",
    "마르베야 시절 Transfermarkt 도움 10개는 FotMob이 모두 도움 0으로 적었고 경기 기사 2곳으로 확인하지 못해 모두 뺌(알헤시라스 2024.9.14 에드워즈·인테르시티 10.26 아우두·에르쿨레스 11.20 한자·메리다 2025.1.19 한자·에르쿨레스 1.25 푸냘·예클라노 2.14 푸냘·세비야 아틀레티코 3.29 아우두·푸엔라브라다 4.5 한자·레알 마드리드 카스티야 5.4 소토·레크레아티보 5.11 올긴)",
    "2019.2.2 삼프도리아전 26분 인시녜 골 도움은 FotMob 이벤트에 없으나 Fox Sports 경기 기록과 Anews 기사가 카예혼 도움으로 적어 넣음(같은 경기 25분 밀리크 골 도움은 FotMob도 확인)",
    "FotMob에만 있는 도움 1개는 넣지 않음: 2016.1.10 프로시노네전 59분 함시크 골(Transfermarkt 도움 없음)",
    f"2014.8.1 이전 도움 {PRE}개는 Transfermarkt 단일 출처이며 다른 출처로 대조하지 못함. 도움 유형 칸이 빈 도움도 도움으로 셈",
    "날짜는 경기 현지 날짜",
    "상대 Elo는 기존 선수 자료의 같은 팀·같은 시즌 값을 먼저 쓰고, 없으면 그 시즌 최종 순위(Transfermarkt 순위표)를 기존 스페인 2부(세군다) 순위별 값에 넣음",
    "스페인 3부(2021년부터 프리메라 페데라시온) 상대(마르베야 시절 2024-25 상대)는 기존 선수 자료의 스페인 3부 평탄 추정 1350을 씀(근거 약함, 순위는 lv에 기록). 코파 델 레이 2023-24 1라운드 상대 아로사 SC(5부 테르세라 페데라시온)는 기존 5부 추정 1100을 씀(추정)",
    "코파 이탈리아 2020-21 3라운드 상대 파도바(세리에C B조 2위/20팀)는 인시녜 선례의 세리에C 모형(평균 1417, 세리에A 곡선)으로 1501을 추정함. 키프로스·크로아티아 등 일부 상대는 기존 선수 자료의 추정값을 그대로 씀",
    "코파 델 레이·코파 이탈리아는 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), 수페르코파(스페인 2011·2012, 이탈리아 2014)는 국내컵 결승으로 계산함. 챔스 예선은 예선, 유로파 32강('intermediate stage', 2013-14 'Second Round')은 토너먼트로 계산함",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회 2020-21시즌까지·코파 델 레이와 수페르코파 2018-19시즌까지·코파 이탈리아 2021-22시즌까지 적용. 자신이 뛰지 않은 다른 차전은 Transfermarkt 경기 리포트의 스코어를 썼음(2012.3.27 챔스 8강 1차전 APOEL 0-3 레알 마드리드, 2019.2.21 유로파 32강 2차전 나폴리 2-0 취리히). 2019-20 코파 이탈리아 준결승 2차전(2020.6.13 인테르전)은 연장 없이 승부차기 규정",
    "연장 없이 승부차기로 끝난 2020.6.17 코파 이탈리아 결승 유벤투스전(66분)과 연장 뒤 승부차기로 끝난 2014.12.22 수페르코파 이탈리아나 유벤투스전(120분), 2015.1.22 코파 이탈리아 우디네세전(37분), 연장 뒤 패한 2021.1.13 코파 이탈리아 인테르전(23분)은 Transfermarkt 출전 분 그대로 씀. 연장 시간 골·도움은 없음",
    "시즌은 8월 1일 기준(2020년 8월 나폴리 경기는 2019-20). 클럽 경계는 Transfermarkt 이적일(2011.7.1 레알 마드리드, 2013.7.11 나폴리, 2020.10.5 피오렌티나, 2022.7.25 그라나다, 2024.7.23 마르베야)",
    "우승·수상은 Transfermarkt 업적 페이지 기준: 라리가 11/12(레알 마드리드), 수페르코파 12/13(레알 마드리드), 코파 이탈리아 13/14·19/20, 수페르코파 이탈리아나 14/15(나폴리), 스페인 2부 22/23(그라나다), 개인은 13/14 코파 이탈리아 득점왕 3골",
    "2025.5.24 안테케라전(선제골)이 마지막 경기였고 2025.5.19 마르베야가 은퇴를 발표함",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mins = {(m[0], m[1]): m[3] for m in M}
for d, rs in by.items():
    goals = sorted([r for r in rs], key=lambda r: r[4])
    if not any(m[0] == d for m in M): problems.append(("출전 없음", d))
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[0] == "g" and r[4] > mins[(r[9], r[1])] + 0 and mins[(r[9], r[1])] < 90 and False: pass
for p in problems: print("점검:", p)

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
open(OUT_JS, "w", encoding="utf-8").write(f"const CAL_E={J(E)};\nconst CAL_M={J(M)};\nconst CAL_NOTE={J(NOTE)};\n")
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judg": judg, "elo_sources": ELO_SRC},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골 {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
