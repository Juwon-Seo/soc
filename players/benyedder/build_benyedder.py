#!/usr/bin/env python3
"""위삼 벤 예데르 (Wissam Ben Yedder, Transfermarkt 146854): raw/ -> benyedder.json + src/data/ben.js (판정 근거는 judgments.md)

  python3 players/benyedder/build_benyedder.py [복사본 루트]     # 파일 쓰기
  python3 players/benyedder/build_benyedder.py --debug           # Elo 출처
  python3 players/benyedder/build_benyedder.py --stat            # 요약·도움 판정·동료 대조·§16 점검

입력: raw/tm_games.csv(출전·분·날짜, level=senior만: 툴루즈 B(CFA 2) 36경기 제외), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(2010-11 이후 대조), raw/ranks.txt(순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(git 추적 파일: 같은 경기·동료 대조).
구조는 파푸 고메스 build(build_papugomez.py)를 따름. 뒤쪽(동료 대조·클럽·설명·점검·출력)은 out_benyedder.py(exec).
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
if ARGS: ROOT = os.path.abspath(ARGS[0])
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "ben.js")
OUT_JSON = os.path.join(HERE, "benyedder.json")
ME = "146854"
ME_KO = "위삼 벤 예데르"
GAP = "2014-08-01"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

ALLG = rd("tm_games.csv")
RESERVE = [g for g in ALLG if g["level"] == "reserve"]          # 툴루즈 B(CFA 2, 5부 아마추어 리그의 2군): 제외
GAMES = [g for g in ALLG if g["level"] == "senior"]
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

def ldate(g): return g["date_local"]           # 리포트/일정 날짜 = UTC 날짜와 모두 같음(모로코 라마단 기간 22:00 UTC 경기도 현지 UTC+0이라 같은 날)
def opp(g): return re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
def minutes(g): return int(g["playedMinutes"])

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"FR1", "ES1", "IRN1", "TR2", "MAR1"}
DOM = {"FRC", "FRL", "CDR", "IRNP", "MARP"}
def rnd_of(g): return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in DOM:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                                  # 쿠프 드 프랑스 5~7라운드·32강·16강, 쿠프 드 라 리그 3라운드·16강, 코파 델 레이 32강·16강, 스론컵 32강
    if cid == "SUC": return "df"                     # 수페르코파(2016 두 경기 결승·2018 단판 결승) = 국내컵 결승 비중
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        return "clk"
    if cid == "ELQ": return "elq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"                                 # 32강('intermediate stage')·16강
    if cid == "CAFC":                                # CAF 컨페더레이션컵(아프리카 2부 대륙 대회): 비중 표가 없어 코파 수다메리카나와 같은 대륙 2부 비중(조별 15·8강 20)
        if r.startswith("quarter"): return "csak"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r: return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    if cid in ("CL", "CLQ", "EL", "ELQ"): return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid == "CDR": return (1, 1) if d < "2019-07-01" else (0, 1)
    if cid == "SUC": return (1, 1)
    if cid == "CAFC": return (1, 0)                  # CAF 대회: 원정 다득점, 연장 없이 승부차기(G/A 없음)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g = G[gid]
    if gid not in MI: return "h" if g["venue"] == "H" else "a"
    m = MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; s = side_of(gid); oid = m["other_leg_id"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split(":"))
        club = G[gid]["club_id"]
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 " + gid)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    return (oh, oa) if s == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 골·도움 판정 표
# 2014.8 이후 Transfermarkt에만 있는 도움(FotMob 경기 기록·선수 경기 목록 모두 도움 없음): gameId|분 -> 근거(넣음) / None(뺌)
POST_GAP = {
    "2482254|70": None,   # 2014.11.29 로리앙전 페시치: 벤 예데르 헤더가 골대를 맞고 나온 것을 페시치가 넣음(Sky Sports·maxifoot) → 슈팅 리바운드
    "2645498|37": None,   # 2016.1.2 상누아 생그라티앵전(쿠프 드 프랑스) 브레이스웨이트: ESPN·maxifoot 등 득점자만, 도움 언급 없음
    "2767532|22": None,   # 2016.12.21 포르멘테라전(코파 델 레이) 비에토: ESPN 문자 중계 1곳만 벤 예데르 도움
    "2719066|41": "벨가 통신 기사(dhnet.be 'passe décisive de Ben Yedder')·FourFourTwo 경기 기사('Ben Yedder … slipped a pass to Sarabia')",
    "3076982|92": None,   # 2018.7.26 우이페슈트전(유로파 예선) 바스케스: 세비야 구단·fichajes 등 득점자만, 도움 언급 없음
    "3199516|84": "maxifoot 경기 기사('profitait d'un service de Ben Yedder')·AS 모나코 구단 경기 기사(벤 예데르 크로스)·LiveSoccerTV",
    "3290268|61": "Goal.com 프랑스판 경기 기사('reprend de la tête un bon centre de Wissam Ben Yedder')·beIN Sports 기사('headed home a cross from Wissam Ben Yedder')",
    "3717186|37": None,   # 2022.1.2 케비이 루앙전(쿠프 드 프랑스) 볼란트: Monaco Tribune 1곳만 벤 예데르 패스, maxifoot·thefishy 경기 기록은 도움 없음
}
# FotMob 경기 기록 이벤트에는 도움자가 없지만 FotMob 선수 경기 목록(도움 수)이 Transfermarkt와 같은 경기 = Transfermarkt·FotMob 일치로 봄
PM_OK = {"4655893", "4655922"}       # 사카리아스포르 2025.10.18 아다나 데미르스포르전·2025.11.8 세리크스포르전(FotMob 선수 통산 사카리아스포르 14경기 5골 3도움과도 같음)

def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def fm_ev(gid, after_ha):
    for f in FME.get(gid, []):
        if f["newScore_home_away"] == after_ha and f["pen_shootout_event"] != "True": return f
    return None

def assist_reason(e):
    t = e["assist_type"]
    if e["scorer_id"] == ME: return "본인 PK 골에 본인 도움"
    if e["own_goal"] == "1" or e["goal_desc"] == "Own-goal": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

def pm_assists(gid):
    pm = FPM.get(G[gid]["fotmobMatchId"])
    return int(pm["assists"] or 0) if pm else None

raw_rows, judg, post_gap_log = [], [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0); d = ldate(g)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == ME and e["own_goal"] != "1"
        is_a = e["assist_id"] == ME
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        f = fm_ev(gid, e["score_home_away_after"])
        tag = f"{gid}|{mi}"
        if is_a:
            why = assist_reason(e)
            if why:
                if why != "본인 PK 골에 본인 도움": judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], why))
            elif d >= GAP and not (f and f["by_assist"] == "1"):
                if gid in PM_OK and pm_assists(gid) == int(g["assists"]):
                    post_gap_log.append((gid, d, opp(g), e["minute"], e["scorer"], e["assist_type"], g["competitionId"], "FotMob 선수 경기 목록 도움 수 일치"))
                    raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
                else:
                    v = POST_GAP.get(tag, "미판정")
                    post_gap_log.append((gid, d, opp(g), e["minute"], e["scorer"], e["assist_type"], g["competitionId"], v))
                    if v == "미판정": sys.exit("[판정 필요] 2014.8 이후 Transfermarkt 단일 도움 " + tag + " " + d + " " + opp(g) + " " + e["scorer"])
                    if v: raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
                    else: judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"],
                                       "슈팅 리바운드(기사)" if tag == "2482254|70" else "2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)"))
            else:
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            if e["side"][0] != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))
# FotMob 단독 도움(이벤트에 벤 예데르 도움, Transfermarkt 같은 스코어 골에 벤 예데르 도움 없음)
fm_only_seen = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        if f["by_assist"] != "1" or f["pen_shootout_event"] == "True": continue
        tm = [e for e in EVS[gid] if e["score_home_away_after"] == f["newScore_home_away"]]
        if any(e["assist_id"] == ME for e in tm): continue
        fm_only_seen.append((gid, ldate(G[gid]), opp(G[gid]), f["time"], f["scorer"]))
if fm_only_seen and "--force" not in sys.argv: sys.exit("[판정 필요] FotMob 단독 도움 " + str(fm_only_seen))
for gid, g in G.items():
    pm = FPM.get(g["fotmobMatchId"])
    if pm and int(pm["assists"] or 0) > int(g["assists"] or 0):
        fm_only_seen.append((gid, ldate(g), opp(g), "FotMob 선수 경기 목록 도움", pm["assists"], g["assists"]))
# 골 수 대조(API)
cnt_ = collections.Counter((r[1], r[0]) for r in raw_rows)
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
    if int(g["penGoals"] or 0) != sum(r[6] for r in raw_rows if r[1] == gid and r[0] == "g"): sys.exit("PK 수 불일치 " + gid)

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
    k = norm(n); return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["선수"].split("·") == [ME_KO]: continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(os.path.basename(p) for p in subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "ben.js") or b not in TRACKED: continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)
ENTS = [x for oe, om in OTHERS.values() for x in oe]
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio", "rc", "ca", "us",
        "as", "ss", "ssc", "fk", "sv", "nk", "cd", "bc", "madrid", "racing", "olympique", "stade", "barcelona", "sd", "ud", "rcd", "sk", "fu", "sm", "es", "ea", "aj", "af"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 + 리그 모형
RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1])][key(p[4])] = (int(p[2]), int(p[3]), p[4])

SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
SEG = [1753, 1712, 1687, 1674, 1660, 1654, 1647, 1640, 1632, 1623, 1615, 1610, 1606, 1601, 1598, 1595, 1589, 1580, 1572, 1567, 1560, 1553]  # 세군다 22팀(기존 고정값)
def half_up(x): return int(x + 0.5)
def ents_map(prefix, season):
    c = collections.defaultdict(collections.Counter)
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위$")
    for e in ENTS:
        m = pat.match(str(e[12] or ""))
        if m: c[int(m.group(1))][e[2]] += 1
    return {r: v.most_common(1)[0][0] for r, v in c.items()}
def mid(tab, r):
    if r in tab: return tab[r]
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    if not lo or not hi: return None
    return half_up((tab[max(lo)] + tab[min(hi)]) / 2)

L2_STD = {1: 1669, 2: 1624, 3: 1603, 4: 1582, 5: 1575, 6: 1567, 7: 1559, 8: 1550, 9: 1541, 10: 1532, 11: 1526, 12: 1521, 13: 1516,
          14: 1513, 15: 1508, 16: 1499, 17: 1490, 18: 1485, 19: 1480, 20: 1470}   # 리그2 20팀 순위값(지냑·고미스 자료와 같은 표)
TR_MEAN_2526 = 1567          # 쉬페르리그 2025-26 평균(살라·자네 자료의 튀르키예 회귀)
MAR_MEAN, MAR_SD = 1440, 63  # 모로코 1부: 다른 선수 자료 위다드 2024-25 3위 1500에 맞춘 평균(16팀 3위 ≈ 1502), 흩어짐은 작은 리그 값(노르웨이·이란 선례 63). 근거 약함

def rank_model(lg, season, r, n):
    if lg == "FR1":
        v = mid(ents_map("리그1", season), r)
        return (v, f"리그1 {season} {r}위") if v else None
    if lg == "FR2":
        return L2_STD[r], f"리그2 {season} {r}위"
    if lg == "FR3":
        return half_up(1311 + SD2 * curve(r, n)), f"프랑스 3부(나시오날) {season} {r}위 (추정)"
    if lg.startswith("FR4"):
        return 1220, f"프랑스 4부(CFA·나시오날 2) {season} {lg[-1]}조 {r}위 (추정, 다른 선수 자료 프랑스 4부 1220과 같음)"
    if lg == "ES1":
        v = mid(ents_map("라리가", season), r)
        return (v, f"라리가 {season} {r}위") if v else None
    if lg == "ES2":
        return SEG[r - 1], f"세군다(2부) {season} {r}위"
    if lg == "ES3D":
        return 1350, f"스페인 3부(세군다 B) {season} {r}위 (추정, 다른 선수 자료 스페인 3부 1350과 같음)"
    if lg == "TR2":
        return half_up(TR_MEAN_2526 - 162 + SD2 * curve(r, n)), f"튀르키예 2부 {season} {r}위 (추정, 쉬페르리그 평균 − 독일 1·2부 평균 차)"
    if lg == "MAR1":
        return half_up(MAR_MEAN + MAR_SD * curve(r, n)), f"모로코 1부(보톨라 프로) {season} {r}위 (리그 수준 추정)"
    if lg == "NL1":
        v = mid(ents_map("에레디비시", season), r)
        return (v, f"에레디비시 {season} {r}위") if v else None
    if lg == "PO1":
        v = mid(ents_map("포르투갈 1부", season), r)
        return (v, f"포르투갈 1부 {season} {r}위") if v else None
    if lg == "RU1":
        return half_up(1520 + 55 * curve(r, n)), f"러시아 프리미어리그 {season} {r}위 (리그 수준 추정)"
    return None

def eu(d):       # 세비야 7월 유로파 예선(2018.7.26)이 새 시즌이 되도록 7월 10일 기준(다른 클럽은 7월 10일~31일 경기 없음)
    y = int(d[:4]); s = y if d[5:] >= "07-10" else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}
def man(o, s, e, lv): MAN[(key(o), s)] = (e, lv)
man("SD Formentera", "2016-17", 1150, "스페인 4부(테르세라) 2016-17 (추정, 다른 선수 자료 스페인 4부 1150과 같음)")
man("Nairobi United FC", "2025-26", 1250, "케냐 1부 (추정, 근거 약함: 다른 선수 자료 인도 슈퍼리그 평균 1250 수준)")
man("FK Zalgiris Vilnius", "2018-19", 1300, "리투아니아 2018 2위 (추정, 다른 선수 자료 잘기리스 2013·2023 1300과 같음)")
man("Újpest FC", "2018-19", 1380, "헝가리 2018-19 5위 (추정, 다른 선수 자료 우이페슈트 2002-03 1380과 같음)")
man("SK Sigma Olomouc", "2018-19", 1420, "체코 2018-19 8위 (추정, 다른 선수 자료 체코 중위권 값 1400~1450 사이)")
man("Standard Liège", "2018-19", 1546, "벨기에 1부 2018-19 3위 (추정, 다른 선수 자료 스탕다르 리에주 2014-15 4위 1546과 같음)")

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
LGS = ["FR1", "FR2", "FR3", "FR4A", "FR4B", "FR4C", "FR4D", "ES1", "ES2", "ES3D", "TR2", "MAR1", "NL1", "PO1", "RU1"]

def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o); s = eu(d)
    if (k, s) in MAN:
        e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    for s2 in [s, d[:4]]:
        if (k, s2) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s2)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s2); return e, lv
    for lg in LGS:
        t = RANKS.get((lg, s), {})
        if k in t:
            r, n, _ = t[k]
            res = rank_model(lg, s, r, n)
            if res and res[0]:
                ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(o, d)] = ("model", res[0], res[1]); return res
    MISS.append((o, d, cid, s)); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    t = tie_of(gid)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if t: row.append(t)
    E.append(row)
def tkey(r): return 45 + int(str(r[11])[3:]) / 100 if str(r[11]).startswith("45+") else r[4]
E.sort(key=lambda r: (r[9], tkey(r), 0 if r[0] == "g" else 1))

if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)

M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), minutes(g)])

if "--debug" in sys.argv:
    print(ELO_SRC)
    seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k = (o, v[1], v[2])
        if k in seen: continue
        seen.add(k); print(d, o, v)
    sys.exit(0)

exec(open(os.path.join(HERE, "out_benyedder.py"), encoding="utf-8").read())
