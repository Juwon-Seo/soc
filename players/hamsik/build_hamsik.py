#!/usr/bin/env python3
"""Marek Hamšík: raw/ -> hamsik.json + src/data/ham.js (판정 근거는 judgments.md)

  python3 players/hamsik/build_hamsik.py            # 파일 쓰기
  python3 players/hamsik/build_hamsik.py --debug    # Elo 출처 로그
  python3 players/hamsik/build_hamsik.py --cross    # 동료 자료 대조

입력: raw/tm_games.csv(출전), raw/tm_events.csv(골·도움, Transfermarkt 경기 리포트), raw/tm_match_info.csv,
      raw/tm_two_leg_ties.csv, raw/fotmob_events.csv·fotmob_playerMatches.csv(대조), raw/ranks.txt(순위표),
      elo/ents.json·opponent_elo_by_team_season.csv·aliases.csv(기존 선수 자료), src/data/{cav,hig,ins,mer,cal,grv}.js(동료 대조).
"""
import csv, json, os, re, sys, unicodedata, collections
from datetime import date as Date

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "ham.js")
OUT_JSON = os.path.join(HERE, "hamsik.json")
ME = "마렉 함식"
GAP = "2014-08-01"   # 도움 출처 기준일: 전은 Transfermarkt 리포트, 이후는 Transfermarkt∩FotMob(+다른 출처 2곳)

def rd(name):
    with open(os.path.join(RAW, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
EVENTS = rd("tm_events.csv")
INFO = {r["gameId"]: r for r in rd("tm_match_info.csv")}
OTHER = {}
for r in rd("tm_two_leg_ties.csv"):
    OTHER[r["gameId"]] = r["other_leg_id"]; OTHER.setdefault(r["other_leg_id"], r["gameId"])
for gid, r in INFO.items():
    if r["other_leg_id"]:
        OTHER.setdefault(gid, r["other_leg_id"]); OTHER.setdefault(r["other_leg_id"], gid)
FM_EV = collections.defaultdict(list)
for r in rd("fotmob_events.csv"):
    FM_EV[r["tm_gameId"]].append(r)
FM_PM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

CLUB_OF_ID = {"19": "brehm", "6195": "naphm", "33304": "dalhm", "801": "ifkhm", "449": "trahm"}

# ---------------------------------------------------------------- 판정 표
# 날짜 고침: gameId -> (현지 날짜, 근거)
DATE_FIX = {
    "3192144": ("2019-07-24", "중국 FA컵 8강 톈진 톈하이–다롄: Transfermarkt 2019.7.23(API 시각 자정 자리표시), FotMob 2019-07-24T10:00Z(베이징 18:00), CGTN 2019.7.25 기사 '4강 진출'"),
}
# 2014.8.1 이후 FotMob 경기 이벤트·선수 경기 목록에 함식 도움이 없는 Transfermarkt 도움: gameId|분 -> 근거(넣음) / None(뺌, 이유는 주석·judgments.md)
POST_GAP = {
    "2483332|68": "The Siren's Song 경기 기록('Higuain (68' assist Hamsik)')·경기 기사('picked out by Marek Hamsik', 검색 요약 인용)",
    "2478683|3": None,     # 2014.11.1 로마전 이과인: Forza Italian Football·Bleacher Report는 인시녜 크로스(굴절)로 서술
    "2905727|48": "Voetbal International 기사('uit een voorzet van Hamsik')·maxifoot 기사('bien servi par Hamsik')",
    "2917432|56": None,    # 2017.11.21 샤흐타르전 인시녜: 기사들은 인시녜 단독 돌파 뒤 감아 차기, 함식 언급 없음
    "3156440|61": None,    # 2019.6.2 상하이 SIPG전 무셰크위: 도움자 적은 기사 없음
    "3612889|1": None,     # 2021.9.23 코냐스포르전 코르넬리우스: Habertürk는 함식 크로스를 바카세타스가 내준 공(마지막 패스 바카세타스), aspor는 함식 크로스 — 엇갈림
    "3612943|45+4": "Türkiye 언론 경기 기사 2곳(함식의 수비 뒷공간 패스를 아브뒬카디르 외뮈르가 마무리, beIN Sports 요약·Milliyet 등 검색 요약 인용)",
}

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"IT1", "IT2", "CSL", "SE1", "TR1"}
CUP = {"CIT", "CHFA", "TRP"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUP:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid in ("SCI", "TRS"): return "df"
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        return "clk"
    if cid in ("ELQ", "UEQ", "UI"): return "elq"          # 인터토토·UEFA컵 예선 = 유로파 예선(선례)
    if cid == "UEFA" and r.startswith("first round"): return "elq"   # UEFA컵 1라운드(2009년 이전)
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"   # 32강(2라운드·intermediate stage)·16강·8강
    if cid == "ECLQ": return "ecq"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def is_leg(g): return "leg" in g["round"].lower()
def ko_of(g):
    if is_leg(g) or g["competitionId"] in LEAGUE or g["competitionId"] == "UI": return 0
    if g["round"].lower().startswith("group"): return 0
    return 1

def ldate(g):
    if g["gameId"] in DATE_FIX: return DATE_FIX[g["gameId"]][0]
    return g["date_local"]

def tie_of(g):
    if not is_leg(g): return None
    gid = g["gameId"]; inf = INFO[gid]; cid = g["competitionId"]; d = ldate(g)
    leg = 1 if "1st" in g["round"].lower() else 2
    o = INFO[OTHER[gid]]
    if (o["date_report"] < inf["date_report"]) != (leg == 2): sys.exit("차전 순서 이상 " + gid)
    home = int(inf["home_id"] == g["club_id"])
    fu = ft = 0
    if leg == 2:
        oh, oa = map(int, o["final"].split(":"))
        if o["home_id"] == g["club_id"]: fu, ft = oh, oa
        elif o["away_id"] == g["club_id"]: fu, ft = oa, oh
        else: sys.exit("다른 차전 팀 불일치 " + gid)
    if cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "UEQ", "UI", "ECLQ"): ag, et = int(d < "2021-07-01"), 1
    elif cid == "CIT": ag, et = 1, 1          # 코파 이탈리아 2021-22까지 원정 다득점·연장
    elif cid == "TRP": ag, et = (1, 1) if d < "2021-07-01" else (0, 1)
    else: sys.exit("합산 규칙 없음 " + cid)
    return [leg, home, fu, ft, ag, et]

# ---------------------------------------------------------------- 이름·상대 Elo
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
MANUAL_ALIAS = {"inter milan": "inter", "shanghai sipg": "shanghai port"}
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if ME in r["선수"].split("·"): continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))
with open(os.path.join(ELO, "ents.json"), encoding="utf-8") as f:
    ENTS = [x for x in json.load(f) if x["p"] != ME]
ENTS_BY_D = collections.defaultdict(list)
for x in ENTS: ENTS_BY_D[x["date"]].append(x)

def season_eu(d):
    y, m = int(d[:4]), int(d[5:7]); s = y if m >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
def season_of(d, club):
    if club in ("dalhm", "ifkhm"): return d[:4]
    return season_eu(d)

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]))

# 리그 순위값
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
# 세리에B(22팀): 기존 선수 자료의 순위별 값(2006-07 델 피에로·카모라네시 자료 등), 빠진 순위는 이웃 기존 값의 가운데
SB = {1: 1707, 2: 1665, 3: 1641, 4: 1623, 6: 1608, 7: 1602, 8: 1594, 9: 1585, 10: 1577, 11: 1569, 12: 1564, 13: 1559, 14: 1555,
      15: 1552, 16: 1549, 17: 1542, 18: 1534, 19: 1526, 20: 1521, 21: 1517, 22: 1507}
SB[5] = round((SB[4] + SB[6]) / 2)
# 중국 슈퍼리그(16팀): 드록바 2012 자료 순위별 값(제르비뉴 2016~18 선례), 기존 값이 없는 순위는 같은 모형(평균 1484·흩어짐 63)
CN_FIX = {4: 1526, 5: 1514, 6: 1501, 7: 1489, 10: 1458, 11: 1452, 12: 1446, 13: 1433, 14: 1422, 15: 1411, 16: 1397}
def cn_val(r):
    return (CN_FIX[r], "같음") if r in CN_FIX else (round(1484 + 63 * curve(r, 16)), "같은 모형")
# 튀르키예 1부: 외질·메르턴스 자료와 같은 회귀(앞뒤 3시즌 UEFA 국가 계수 평균), 흩어짐 119
TR_COEF = {2020: 3.1, 2021: 6.7, 2022: 11.8, 2023: 12.0}
def tr_mean(start):
    c = sum(TR_COEF[y] for y in (start - 1, start, start + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)

def model(lg, season, r, n):
    if lg == "IT1" and n == 20: return SA[r - 1], f"세리에A {season} {r}위"
    if lg == "IT2" and n == 22: return SB[r], f"세리에B {season} {r}위"
    if lg == "CSL" and n == 16:
        v, how = cn_val(r); return v, f"중국 슈퍼리그 {season} {r}위 (추정, 다른 선수 자료 중국 슈퍼리그 2012 순위별 값과 {how})"
    if lg == "TR1": return round(tr_mean(int(season[:4])) + 119 * curve(r, n)), f"쉬페르리그 {season} {r}위"
    return None
RANK_LG = ["IT1", "IT2", "CSL", "TR1"]

# 직접 추정(모두 '추정')
MAN = {
    (key("Shenzhen FC"), "2020"): (round(sum(cn_val(r)[0] for r in (13, 14, 15, 16)) / 4),
        "중국 슈퍼리그 2020 13~16위 (추정: 1단계 조 5위 뒤 강등권 단계 첫 판에서 져 13~16위 결정전, 최종 순위 확인 못 함, 다른 선수 자료 중국 슈퍼리그 13~16위 값 평균)"),
    (key("KF Vllaznia"), "2008-09"): (1300, "알바니아 2008-09 2위 (추정, 다른 선수 자료 알바니아 2위 1300과 같음)"),
    (key("Panionios FC"), "2008-09"): (1401, "그리스 슈퍼리그 2008-09 8위 (리그 수준 추정, 다른 선수 자료 2007-08 8위 값과 같음)"),
    (key("IK Sirius"), "2021"): (1370, "스웨덴 알스벤스칸 2021 11위 (추정, 다른 선수 자료 스웨덴 8위/14팀 1377보다 조금 낮게)"),
    (key("Red Star Belgrade"), "2022-23"): (1580, "세르비아 2022-23 1위 (추정, 다른 선수 자료 츠르베나 즈베즈다 2018-19·2023-24 1580과 같음)"),
}
CN2020 = {key("Guangzhou Evergrande Taobao"): 2, key("Henan Jianye"): 9}   # 2020 최종 순위(챔피언십 결승 장쑤 승, 허난 9위 결정전 승: China Daily 2020.11)

ELO_SRC = collections.Counter(); ELO_LOG = []
def _sub(a, b):
    A, B = set(a.split()), set(b.split())
    return bool(A) and bool(B) and (A <= B or B <= A)
def opp_elo(opp, d, cid, club):
    k = key(opp); eu = season_eu(d); se = season_of(d, club)
    dd = Date.fromisoformat(d)
    same = []
    for delta in (-1, 0, 1):
        dx = Date.fromordinal(dd.toordinal() + delta).isoformat()
        same += [x for x in ENTS_BY_D.get(dx, []) if key(x["opp"]) == k or _sub(key(x["opp"]), k)]
    if same:
        (e, lv), _ = collections.Counter((x["elo"], x["lv"]) for x in same).most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG.append((d, opp, e, lv, "same:" + "·".join(sorted({x["p"] for x in same})), sorted({(x["elo"], x["lv"]) for x in same})))
        return e, lv
    if (k, se) in MAN:
        e, lv = MAN[(k, se)]; ELO_SRC["직접 추정"] += 1; ELO_LOG.append((d, opp, e, lv, "man", [])); return e, lv
    if club == "dalhm" and d[:4] == "2020" and k in CN2020:
        r = CN2020[k]; v, how = cn_val(r)
        ELO_SRC["순위+리그 모형"] += 1
        lv = f"중국 슈퍼리그 2020 {r}위 (추정, 다른 선수 자료 중국 슈퍼리그 2012 순위별 값과 {how})"
        ELO_LOG.append((d, opp, v, lv, "cn2020", [])); return v, lv
    euro = cid in ("CL", "CLQ", "EL", "ELQ", "UEFA", "UEQ", "UI", "ECLQ")
    seasons = [se] + ([str(int(eu[:4])), str(int(eu[:4]) + 1)] if euro else [])
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["팀×시즌 통합표"] += 1; ELO_LOG.append((d, opp, e, lv, "table " + s, sorted(set(TABLE[(k, s)]))))
            return e, lv
    for lg in RANK_LG:
        t = RANKS.get((lg, se))
        if t and k in t:
            r, n = t[k]
            res = model(lg, se, r, n)
            if res:
                ELO_SRC["순위+리그 모형"] += 1; ELO_LOG.append((d, opp, res[0], res[1], "model " + lg, []))
                return res
    return None

# ---------------------------------------------------------------- 출전
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
CLUBS = [("brehm", "2007-07-01"), ("naphm", "2019-02-14"), ("dalhm", "2021-03-08"), ("ifkhm", "2021-07-01"), ("trahm", None)]
M = []
for g in GAMES:
    if club_of(ldate(g)) != CLUB_OF_ID[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
    M.append([ldate(g), g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
M.sort(key=lambda r: r[0])

# ---------------------------------------------------------------- 골·도움
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def fm_assist_ok(gid, e):
    """FotMob 경기 이벤트(같은 골 뒤 스코어) 또는 선수 경기 목록 도움 수로 함식 도움 확인"""
    for r in FM_EV.get(gid, []):
        if r["newScore_home_away"] == e["score_home_away_after"] and r["hamsik_assist"] == "1": return "event"
    return None

rows, judg = [], []
missing = set(); EXCL = collections.Counter(); FM_USED = collections.Counter(); POST_LOG = []
for e in EVENTS:
    gid = e["gameId"]; g = G.get(gid)
    if not g: continue
    isg, isa = e["hamsik_scorer"] == "1", e["hamsik_assist_other"] == "1"
    if not (isg or isa): continue
    tag = f"{gid}|{e['minute']}"
    inf = INFO[gid]; our_home = inf["home_id"] == g["club_id"]
    h, a = map(int, e["score_home_away_after"].split("-"))
    side_home = e["side"] == "home"
    if side_home: h -= 1
    else: a -= 1
    ours = side_home == our_home
    gf, ga = (h, a) if our_home else (a, h)
    mi, dm = minute(e["minute"])
    cid = g["competitionId"]; comp = comp_of(cid, g["round"]); ko = ko_of(g); tie = tie_of(g)
    d = ldate(g); opp = g["opponent"].strip(); club = CLUB_OF_ID[g["club_id"]]
    def add(typ, pk, note):
        res = opp_elo(opp, d, cid, club)
        if res is None: missing.add((opp, season_of(d, club), cid)); res = (0, "?")
        et = 1 if (ko and mi > 90 and g["gameState"] in ("extra_time", "penalty_shootout") and not dm) else 0
        row = [typ, opp, res[0], comp, mi, gf, ga, ko, pk, d, et, dm, res[1], note]
        if tie: row.append(tie)
        rows.append(row)
    if isg:
        if e["own_goal"] == "1" or not ours: judg.append(("골 제외(자책골)", tag)); continue
        add("g", int(e["penalty"] == "1"), 0)
    if isa:
        why = None
        if e["own_goal"] == "1" or not ours: why = "상대 자책골에 준 도움"
        elif e["assist_type"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type"] == "Shot on goal": why = "'Shot on goal'(슈팅 리바운드)"
        if why:
            EXCL[why] += 1; judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], why)); continue
        if d >= GAP:
            if fm_assist_ok(gid, e): FM_USED[gid] += 1
            else:
                if tag not in POST_GAP: sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락 " + tag + " " + d + " " + opp)
                POST_LOG.append((d, opp, e["minute"], e["scorer"], POST_GAP[tag]))
                if not POST_GAP[tag]:
                    EXCL["2014.8 이후 단일 출처(확인 못 함)"] += 1
                    judg.append(("도움 제외", d, opp, e["minute"], e["scorer"], "2014.8 이후 Transfermarkt 단독, 다른 출처 2곳 확인 못 함")); continue
        add("a", 0, e["scorer"])

if missing:
    for x in sorted(missing, key=lambda x: x[1]): print("Elo 없음:", x)
    sys.exit(1)

# FotMob 전용 도움(2014.8 이후, TM에는 다른 도움자·없음) — 넣지 않음
FM_ONLY = []
for gid, evs in FM_EV.items():
    if gid not in G or ldate(G[gid]) < GAP: continue
    for r in evs:
        if r["hamsik_assist"] == "1":
            tm = [e for e in EVENTS if e["gameId"] == gid and e["score_home_away_after"] == r["newScore_home_away"]]
            if not any(e["hamsik_assist_other"] == "1" for e in tm):
                FM_ONLY.append((gid, ldate(G[gid]), G[gid]["opponent"], r["time"], r["scorer"]))
for gid, g in G.items():
    pm = FM_PM.get(g["fotmobMatchId"])
    if pm and int(pm["assists"] or 0) > int(g["assists"] or 0):
        FM_ONLY.append((gid, ldate(g), g["opponent"], "선수 경기 목록", pm["assists"]))

rows.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))
E = rows

if __name__ == "__main__" and "--debug" in sys.argv:
    print(ELO_SRC, EXCL, FM_ONLY)
    seen = set()
    for x in ELO_LOG:
        k = (x[1], x[2], x[3], x[4][:5])
        if k in seen: continue
        seen.add(k); print(x)
    for p in POST_LOG: print("POST", p)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid in sorted({e["gameId"] for e in EVENTS if e["hamsik_scorer"] == "1"}):
    g = G[gid]
    if ldate(g) < "2010-08-01": continue
    tg = [e for e in EVENTS if e["gameId"] == gid and e["hamsik_scorer"] == "1"]
    fg = [r for r in FM_EV.get(gid, []) if r["hamsik_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if not FM_EV.get(gid): FM_CMP.append(("FotMob 자료 없음", gid, ldate(g))); continue
    if len(fg) != len(tg): FM_CMP.append(("골 수 다름", gid, ldate(g), [x["minute"] for x in tg], [(r["time"], r["scorer"], r["goalDescriptionKey"]) for r in FM_EV[gid] if r["newScore_home_away"] in {x["score_home_away_after"] for x in tg}])); continue
    for t, f in zip(sorted(tg, key=lambda x: minute(x["minute"])[0]), sorted(fg, key=lambda r: int(r["time"]) + int(r["overloadTime"] or 0))):
        tpk = t["penalty"] == "1"; fpk = (f["goalDescriptionKey"] or "").lower().startswith("penalty")
        if tpk != fpk or abs(minute(t["minute"])[0] - int(f["time"]) - int(f["overloadTime"] or 0)) > 1 and int(f["time"]) != int(t["minute"].split("+")[0]):
            FM_CMP.append(("다름", gid, ldate(g), t["minute"], t["penalty"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))
if __name__ == "__main__" and "--fm" in sys.argv:
    for x in FM_CMP: print(x)

# ---------------------------------------------------------------- 동료 자료 대조(다른 파일은 고치지 않음)
def load_js(fn, P):
    s = open(os.path.join(ROOT, "src", "data", fn), encoding="utf-8").read()
    return json.loads(re.search(r"const " + P + r"_E=(\[.*?\]);\n", s, re.S).group(1))
MATES = {"Edinson Cavani": ("cav.js", "CAV", "2010-07-01", "2013-07-16"),
         "Gonzalo Higuaín": ("hig.js", "HIG", "2013-07-01", "2016-07-26"),
         "Lorenzo Insigne": ("ins.js", "INS", "2012-07-01", "2019-02-14"),
         "Dries Mertens": ("mer.js", "MER", "2013-07-01", "2019-02-14"),
         "José Callejón": ("cal.js", "CAL", "2013-07-01", "2019-02-14"),
         "Gervinho": ("grv.js", "GRV", "2021-07-01", "2022-07-01")}
MATE_E = {nm: load_js(v[0], v[1]) for nm, v in MATES.items()}
CROSS = []
def cmp_rows(a, b):
    df = []
    if abs(a[4] - b[4]) > 2: df.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): df.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: df.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: df.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: df.append(f"lv {a[12]}/{b[12]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if a[7] != b[7] or ta != tb: df.append(f"단판/합산 {a[7]},{ta}/{b[7]},{tb}")
    return df
HM = lambda s: "hamsik" in norm(s or "")
for nm, ent in MATE_E.items():
    lo, hi = MATES[nm][2], MATES[nm][3]
    for r in E:
        if r[0] == "a" and norm(r[13]) == norm(nm):
            hit = sorted([x for x in ent if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3], key=lambda x: abs(x[4] - r[4]))
            CROSS.append(("함식 도움→" + nm + " 골", r[9], r[4], "없음" if not hit else (cmp_rows(r, hit[0]) or "같음")))
    for x in ent:
        if x[0] == "a" and HM(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((nm + " 도움→함식 골", x[9], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in ent:
        if lo <= x[9] < hi:
            for r in E:
                if r[9] == x[9]:
                    dd = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어"))]
                    if dd: CROSS.append(("같은 경기 다름", nm, r[9], r[1], dd))
                    break
    # Transfermarkt 함식 도움인데 이 계산기에서 뺀 동료 골(참고)
    for x in ent:
        if x[0] == "g" and lo <= x[9] < hi:
            tm = [e for e in EVENTS if e["hamsik_assist_other"] == "1" and e["gameId"] in G and ldate(G[e["gameId"]]) == x[9] and abs(minute(e["minute"])[0] - x[4]) <= 2]
            if tm and not any(r[0] == "a" and r[9] == x[9] and abs(r[4] - x[4]) <= 2 for r in E):
                CROSS.append(("TM 함식 도움을 뺀 동료 골", nm, x[9], x[4], tm[0]["assist_type"]))
    # TM 동료 도움 → 함식 골인데 동료 파일에 없는 것(참고)
    for e in EVENTS:
        if e["hamsik_scorer"] == "1" and e["gameId"] in G and e["assist_player"] and norm(e["assist_player"]) == norm(nm):
            d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
            if not any(x[0] == "a" and x[9] == d and abs(x[4] - mi) <= 2 for x in ent):
                CROSS.append(("TM 동료 도움→함식 골인데 동료 파일에 없음", nm, d, e["minute"], e["assist_type"]))
if __name__ == "__main__" and "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0], c[-1] == "같음") for c in CROSS))

# ---------------------------------------------------------------- 클럽별 집계
CLUB_KO = {"brehm": "브레시아", "naphm": "나폴리", "dalhm": "다롄 이팡", "ifkhm": "IFK 예테보리", "trahm": "트라브존스포르"}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k, _ in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1

exec(open(os.path.join(HERE, "note_hamsik.py"), encoding="utf-8").read())   # 설명·점검·출력
