#!/usr/bin/env python3
"""디에구 히바스 (Diego Ribas da Cunha, Transfermarkt 4248): raw/ -> diego.json + src/data/die.js (판정 근거는 judgments.md)

  python3 players/diego/build_diego.py            # 파일 쓰기
  python3 players/diego/build_diego.py --debug    # Elo 출처 로그만 출력
  python3 players/diego/build_diego.py --stat     # 요약·판정·동료 대조·FotMob 대조
  python3 players/diego/build_diego.py --ties     # 합산 행

입력: raw/tm_games.csv(출전·분), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(2010-11 이후 대조), raw/ranks.txt(Transfermarkt 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git에 올라간 다른 선수 자료: 같은 경기·동료 대조),
      players/candreva/staged/can.js(병렬 판정 중인 동료 자료: 대조만).
환경 변수 DIE_ROOT: 저장소 뿌리(스크래치 복사본에서 돌릴 때).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("DIE_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "die.js")
OUT_JSON = os.path.join(HERE, "diego.json")
ME = "4248"
ME_KO = "디에구 히바스"

def rd(n, base=RAW):
    with open(os.path.join(base, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FPM = rd("fotmob_playerMatches.csv")

# ---------------------------------------------------------------- 날짜(현지)
EU_CLUBS = {"720", "86", "506", "82", "13", "36"}
# 플라멩구 남미 대회 원정: 개최지 나라 시간(원자료 date_local 빈칸). 산투스 2003~04 남미 대회는 Transfermarkt 시각이 날짜만(12·13시 UTC)이라 그 날짜.
AWAY_TZ = {
    "CA San Lorenzo de Almagro": "America/Argentina/Buenos_Aires", "CA River Plate": "America/Argentina/Buenos_Aires",
    "Racing Club": "America/Argentina/Buenos_Aires", "CA Vélez Sarsfield": "America/Argentina/Buenos_Aires",
    "Defensa y Justicia": "America/Argentina/Buenos_Aires", "CA Independiente": "America/Argentina/Buenos_Aires",
    "CD Universidad Católica": "America/Santiago", "Unión La Calera": "America/Santiago",
    "CS Emelec": "America/Guayaquil", "LDU Quito": "America/Guayaquil", "Independiente del Valle": "America/Guayaquil",
    "Barcelona SC Guayaquil": "America/Guayaquil",
    "Independiente Santa Fe": "America/Bogota", "Junior FC": "America/Bogota", "Deportes Tolima": "America/Bogota",
    "Club Deportivo San José": "America/La_Paz", "Club Olimpia": "America/Asuncion", "CA Peñarol": "America/Montevideo",
    "Club Sporting Cristal": "America/Lima",
}
def ldate(g):
    if g["club_id"] in EU_CLUBS:
        # 유럽 클럽: API UTC를 중부 유럽 시간으로 바꾼 날짜(= Transfermarkt 일정·리포트 날짜, 제 호베르투 선례)
        return datetime.datetime.fromisoformat(g["date_utc"]).astimezone(ZoneInfo("Europe/Berlin")).date().isoformat()
    if g["date_local"]: return g["date_local"]           # 브라질 국내 대회(상파울루 시간)·클럽 월드컵(카타르)
    # 남미 대회
    if g["club_id"] == "221": return g["date_sao_paulo"]
    o = opp(g)
    if g["venue"] == "A" and o in AWAY_TZ:
        return datetime.datetime.fromisoformat(g["date_utc"]).astimezone(ZoneInfo(AWAY_TZ[o])).date().isoformat()
    if g["venue"] == "A" and o not in ("Associação Chapecoense de Futebol", "Fluminense Football Club", "Cruzeiro Esporte Clube", "AD São Caetano (SP)"):
        sys.exit("원정 시간대 없음 " + o)
    if g["gameId"] == "3283534":   # 2019 리베르타도레스 결승(리마, 단판): 20:00 UTC = 리마 15:00
        return datetime.datetime.fromisoformat(g["date_utc"]).astimezone(ZoneInfo("America/Lima")).date().isoformat()
    return g["date_sao_paulo"]
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()

# ---------------------------------------------------------------- 판정 표
# Transfermarkt 출전 표시인데 출전 분이 0·빈칸인 3경기 → 90분 추정(M 행 추정 표시)
MIN_EST = {"3687693": 90, "3477146": 90, "3477174": 90}
GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# 2014.8 이후 TM 도움 중 FotMob(경기 이벤트·선수 경기 목록)으로 확인되지 않는 것의 판정
#  "art": 경기 기사 확인 — 브라질 대회 중 FotMob 도움 자료가 아예 없는 경기(v1.161 규칙: 기사 1곳 확인이면 넣음)
#         또는 FotMob 자료가 있는 경기는 다른 출처 2곳
#  "drop": 확인 못 함·반대 출처 → 뺌
POST = {}   # (gameId, minute) -> (판정, 근거)  — post_assists.py 에서 채움
exec(open(os.path.join(HERE, "post_assists.py"), encoding="utf-8").read())

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"BRA1", "PO1", "L1", "IT1", "ES1", "TR1"}
STATE = {"BCP1", "BCPF", "BRCG", "BRCR", "BRCF", "BRC2"}   # 주 선수권(파울리스타·카리오카)·프리메이라 리가: 국내컵 하위 비중(비니시우스·제 호베르투 선례)

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in STATE: return "dc"
    if cid in ("BRC", "DFB", "CIT", "CDR", "TRP", "POPO"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "LPO":
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        return "dk"
    if cid in ("POSU", "SCBR", "RECO"): return "df"    # 슈퍼컵류 = 국내컵 결승 비중(레코파 남미도 같은 슈퍼컵으로 봄)
    if cid in ("WEPO", "KLUB"): return "cwc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "CLQ": return "clq"
    if cid == "ELQ": return "elq"
    if cid in ("UEFA", "EL"):
        if r.startswith("first round"): return "elq"
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                       # 3라운드·intermediate stage(32강)·2라운드(32강)·16강·8강
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"
    if cid == "CS":
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+\.?$", r): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    r = rnd.lower()
    if cid in ("UEFA", "CL", "CLQ", "EL", "ELQ"): return (1, 1)    # UEFA 대회 2020-21까지
    if cid == "CDR": return (1, 1)                                 # 코파 델 레이 2018-19까지
    if cid == "TRP": return (1, 1)                                 # 튀르키예컵 2020-21까지
    if cid in ("BCPF", "BRCF"): return (0, 0)                      # 주 선수권 두 경기: 원정 다득점·연장 없음(네이마르 선례)
    if cid == "BRC":
        if r.startswith("final"): return (0, 0)                    # 코파 두 브라질 결승: 원정 다득점 없음(제 호베르투 선례)
        return (1, 0) if d < "2018-01-01" else (0, 0)   # 원정 다득점은 2017까지(2018 대회부터 폐지: 트리벨라·DCI 기사), 연장 없음
    if cid in ("CLI", "CS", "RECO"):
        # CONMEBOL: 2004년까지 원정 다득점·연장 없이 바로 승부차기, 2005~2021 원정 다득점(2008부터 결승은 원정 다득점 없이 연장),
        #   2022부터 원정 다득점 폐지(2021.11 발표)
        if d < "2005-01-01" or d >= "2022-01-01": return (0, 0)
        if r.startswith("final"): return (0, 1) if d >= "2008-01-01" else (1, 0)
        return (1, 0)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid)
    oid = m["other_leg_id"]
    if oid in G and G[oid]["gameState"] != "penalty_shootout":
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), g["round"])
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    gid = g["gameId"]
    row = [ldate(g), opp(g), comp_of(g["competitionId"], g["round"]), MIN_EST.get(gid, int(g["playedMinutes"] or 0))]
    if gid in MIN_EST: row.append(1)
    M.append(row)

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

def assist_reason(e):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if e["goal_desc"] == "Penalty": return "PK 골(도움 없음)"
    return None

# FotMob 확인(2014.8 이후): 경기 이벤트 assistStr에 Diego, 또는 선수 경기 목록(playerMatches) 도움 수가 TM 도움 수 이상
PM_BY = {}
for r in FPM:
    PM_BY.setdefault(r["utc"][:10], []).append(r)
def fm_pm_assists(g):
    d = datetime.date.fromisoformat(g["date_utc"][:10]); out = []
    for k in (-1, 0, 1):
        out += PM_BY.get((d + datetime.timedelta(days=k)).isoformat(), [])
    return out
def fm_confirms(gid, e):
    mi = mins(e["minute"])[0]
    for r in FME.get(gid, []):
        if r["time"] and abs(int(r["time"]) + int(r["overloadTime"] or 0) - mi) <= 2 and "Diego" in (r["assistStr"] or "") and "Alves" not in r["assistStr"]:
            return "FotMob 경기 이벤트 도움"
    g = G[gid]; tm_a = sum(1 for x in EVS[gid] if x["assist_id"] == ME and x["scorer_id"] != ME and not assist_reason(x) and x["diego_conceded_penalty_note"] != "1")
    pm = fm_pm_assists(g)
    if len(pm) == 1 and int(pm[0]["assists"] or 0) >= tm_a: return "FotMob 선수 경기 목록 도움 %s" % pm[0]["assists"]
    return None

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}
    for e in EVS[gid]:
        sd = e["side"][0]
        before = (cnt["h"], cnt["a"])
        cnt[sd] += 1
        if e["diego_conceded_penalty_note"] == "1":
            judg.append(("도움 아님(디에구가 내준 PK 'Handball by Diego')", ldate(g), opp(g), e["minute"], e["scorer"])); continue
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"]))
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            if ldate(g) >= GAP:
                fc = fm_confirms(gid, e)
                dec = POST.get((gid, e["minute"]))
                if fc and not dec: dec = ("fm", fc)
                if not dec:
                    print("2014.8 이후 도움 판정 없음 %s %s %s %s %s" % (gid, ldate(g), opp(g), e["minute"], e["scorer"])); dec = ("drop", "?")
                judg.append(("2014.8 이후 도움 " + dec[0], ldate(g), opp(g), e["minute"], e["scorer"], dec[1]))
                if dec[0] == "drop": continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk:
                if e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
                judg.append(("PK 아님(PK가 막힌 뒤 리바운드 골)", ldate(g), opp(g), e["minute"], e["goal_desc"]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))

cnt_ = collections.Counter()
for r in raw_rows: cnt_[(r[1], r[0])] += 1
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

SCORE_MISMATCH = []
for gid, evs in EVS.items():
    if gid not in G: continue
    h = sum(1 for e in evs if e["side"][0] == "h"); a = sum(1 for e in evs if e["side"][0] == "a")
    fh, fa = map(int, MI[gid]["final"].split(":")) if MI[gid]["final"] else (h, a)
    if G[gid]["gameState"] != "penalty_shootout" and (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))

exec(open(os.path.join(HERE, "elo_diego.py"), encoding="utf-8").read())

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, rnd)
    et = 1 if (mi > 90 and not dm and g["gameState"] in ("extra_time", "penalty_shootout")) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)
if "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print("score mismatches", SCORE_MISMATCH)
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    print(len(E), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E))
    sys.exit(0)

if "--stat" in sys.argv or True: pass
