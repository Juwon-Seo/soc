#!/usr/bin/env python3
"""Josip Iličić: raw/ -> ilicic.json + src/data/ili.js (판정 근거는 judgments.md)

  python3 players/ilicic/build_ilicic.py

입력: raw/tm_games.csv(출전·분), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(리포트 머리·다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(대조), raw/ranks.txt(Transfermarkt 순위표),
      elo/opponent_elo_by_team_season.csv + aliases.csv, src/data/*.js(같은 경기 다른 선수 자료, git 추적 파일만).
뒤쪽(Elo 직접 추정·동료 대조·설명·점검·출력)은 elo_ilicic.py·out_ilicic.py를 exec로 읽음.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
if len(sys.argv) > 1: ROOT = os.path.abspath(sys.argv[1])     # 스크래치 복사본에 쓸 때
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.path.join(ROOT, "src", "data", "ili.js")
OUT_JSON = os.path.join(HERE, "ilicic.json")
JP = "80351"
GAP = "2014-08-01"   # 이 날짜 전 도움은 Transfermarkt 리포트, 뒤는 Transfermarkt ∩ FotMob(+ 다른 출처 2곳 / FotMob 도움 자료 없는 슬로베니아 리그는 경기 기사)

try:
    TRACKED = set(os.path.basename(p) for p in subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
except Exception:
    TRACKED = None

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 판정 표
# 2014.8 이후 Transfermarkt 단일 출처 도움: gameId|분 -> 근거(넣음) / None(뺌)
# (1) FotMob 도움 자료가 있는 대회(세리에A 등): 다른 출처 2곳 필요
# (2) 슬로베니아 1부·컵(FotMob 경기 기록에 도움 자료가 전혀 없음): 경기 기사(siol.net Sportal 라운드 기사 등)로 확인되면 넣음
SIOL = "siol.net Sportal 1. SNL "
POST_GAP = {
    "3229326|10": None,   # 2019.12.22 밀란전 고메스: 로이터 등 기사는 고메스 단독 돌파 골('stunning individual goal'), 일리치치 도움 언급 없음
    "3842180|80": None,   # 2022.12.11 고리차전 비포트니크: siol 20라운드 기사 '20m 밖에서 강하게 찬 골', 도움 언급 없음
    "3842227|72": SIOL + "30라운드 기사('po podaji Iličića … popeljal Maribor v vodstvo s 3:0')",
    "4091093|19": SIOL + "4라운드 기사('Iličić je bil pri prvem zadetku na tekmi podajalec … Marko Božić')",
    "4091099|43": SIOL + "5라운드 기사('zadel Marko Božić, potem ko je unovčil natančno podajo Josipa Iličića')",
    "4091138|68": SIOL + "13라운드 기사('Iličić je podal iz kota, Skuka pa dosegel svoj prvi gol')",
    "4091174|24": None,   # 2024.2.11 알루미니 전 야쿠포비치: siol 20라운드 기사는 '브르호베츠와 일리치치가 함께한 세 번의 패스' 뒤 골이라고만 적음(마지막 패스 미확인), 다른 기사(svet24)도 도움자 없음
    "4091200|84": SIOL + "25라운드 기사('po podaji Josipa Iličića s prostega strela … z glavo meril Sven Šoštarič Karič')",
    "4091201|77": SIOL + "연기 경기 기사('Po podaji Iličića je z več kot 20 metrov streljal Jan Repas', 수비수 맞고 굴절된 슛이지만 도움 패스는 일리치치)",
    "4091223|19": SIOL + "30라운드 기사('z natančno podajo z desne strani zaposlil Hillala Soudanija … Iličić je vpisal šesto podajo')",
    "4091245|28": SIOL + "34라운드 기사('izkoristil izjemno podajo Josipa Iličića in njegovo osmo asistenco')",
    "4091245|85": None,   # 2024.5.4 첼레전 바리시치: siol 34라운드 기사 '교체 선수 바리시치가 마무리', 도움자 없음; 경기 기록 사이트도 도움 없음
    "4091246|15": SIOL + "35라운드 기사(사진 설명 'Josip Iličić je asistiral za oba gola na večnem derbiju' — 마리보르의 두 골 소다니·시르비스)",
    "4091246|66": SIOL + "35라운드 기사('Po podaji Iličića je … zadel Pijus Širvys')",
    "4372375|26": SIOL + "6라운드 기사('Žiga Repas zadel … po odloženi žogi Josipa Iličića')",
    "4372384|58": SIOL + "8라운드 기사('končni rezultat po asistenci Josipa Iličića dosegel … Marko Božić')",
    "4372401|3": SIOL + "11라운드 기사('Josip Iličić je izvedel kot, strel branilca domačih z glavo' — 일리치치 코너킥을 크라이은츠가 헤더)",
    "4630180|73": None,   # 2025.8.9 라돔레전 D. 유리치: siol 4라운드 기사에 도움 언급 없음
    "4630233|65": SIOL + "13라운드 기사('Iličić v 65. minuti poslal lep predložek … Isaac Matondo … z glavo')",
    "4630237|67": SIOL + "14라운드 기사('v 67. minuti po podaji Josipa Iličića odločil Isaac Matondo')",
    "4630259|15": SIOL + "18라운드 기사('Prvi gol je po podaji povratnika Josipa Iličića zabil Filip Damjanović')",
    "4630260|5": SIOL + "19라운드 기사('Iličić je v peti minuti s podajo našel Ruedla')",
    "4630269|47": SIOL + "20라운드 기사('Iz kota je podal Iličić … Maj Mittendorfer … z glavo zadel')",
    "4630287|78": None,   # 2026.3.1 무라전 롱곤다: 경기 기사 못 찾음(siol 24라운드 기사 없음), 결과 사이트(penzcentrum)는 리마츠 도움으로 적음
    "4630336|6": SIOL + "31라운드 기사('Josip Iličić izvedel prosti strel … z glavo … Andraž Ruedl')",
    "4899239|27": None,   # 2026.7.17 나프타전 만세리: siol 1라운드 기사에 도움 언급 없음
    "4899848|50": None,   # 2026.10.18 브리녜전 바출랴: siol 12라운드 기사는 득점자만 나열
    "4899849|67": SIOL + "13라운드 기사('ko je po Iličićevi podaji iz bližine zadel Fran Tomek')",
    "4899858|53": SIOL + "14라운드 기사('Iličić je poslal žogo v kazenski prostor … Luka Guček pa je z glavo zadel')",
}
# PK 판정 고침: gameId|분 -> (PK 여부, 근거)
PK_FIX = {"4420836|59": (0, "2024.8.8 보이보디나전 59분: Transfermarkt 골 설명 'Penalty rebound'(막힌 PK 리바운드 골) — PK 골 아님(공통 규칙), FotMob도 일반 골")}
# 분 고침(전반 추가시간): gameId|분 -> (분, 표시)
MIN_FIX = {"4091102|46": (46, "45+1", "2023.8.26 돔잘레전 PK 골: Transfermarkt 46분, FotMob 45+1분, siol 6라운드 기사 '전반 끝 무렵 PK … 전반 1:1'")}

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"IT1", "SL1", "POSL"}       # POSL = 슬로베니아 1부 강등 플레이오프(리그 비중, 2010.5 트리글라우전 2경기, 기록 없음)
CUP_ROUND = {"946053": "Round of 16", "946061": "Quarter-Finals", "946066": "Semi-Finals 1st Leg", "946067": "Semi-Finals 2nd Leg"}   # 2008-09 슬로베니아컵(Transfermarkt 'N. Matchday' 표기, 위키백과 대진)
def rnd_of(g): return CUP_ROUND.get(g["gameId"], g["round"])
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid in ("CIT", "SLP"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        return "clk"
    if cid == "ELQ": return "elq"
    if cid == "ECLQ": return "ecq"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        return "elk"        # 32강('intermediate stage', 2013-14 'Second Round')·16강
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE_IDS: return 0
    if cid in ("CL", "EL") and r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 입력
games = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
FPM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}
def ldate(g): return g["date_local"]          # 모두 유럽 경기: Transfermarkt 리포트·일정 날짜(현지)
def opp(g): return g["opponent"].strip()

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    if cid in ("CL", "ELQ", "EL", "ECLQ", "CLQ"): return (1, 1) if d < "2021-07-01" else (0, 1)   # UEFA 원정 다득점 2020-21까지
    if cid == "CIT": return (1, 1) if d < "2022-07-01" else (0, 1)       # 코파 이탈리아 준결승: 원정 다득점 2021-22까지, 2차전 연장
    if cid == "SLP": return (1, 1)                                       # 슬로베니아컵 두 경기 라운드(추정: UEFA식 원정 다득점·연장)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

OTHER_LEG = {"946067": (2, 2)}     # 2008-09 컵 준결승 1차전 인터블록 2-2 마리보르(리포트에 다른 차전 링크 없음)
def other_leg(gid):
    if gid in OTHER_LEG: return OTHER_LEG[gid]
    m = MI[gid]; s = side_of(gid); oid = m["other_leg_id"]
    if oid in G:
        a, b = map(int, G[oid]["score_club_opp"].split("-")); return (a, b)
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

# ---------------------------------------------------------------- 골·도움
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
    if e["scorer_id"] == JP: return "본인 PK 골에 본인 도움"
    if e["own_goal"] == "1": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

def fm_assist_ok(gid, f):
    if f and f["ilicic_assist"] == "1": return True
    return False

raw_rows, judg, post_gap_log, min_fix = [], [], [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid)
    prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == JP and e["own_goal"] != "1"
        is_a = e["assist_id"] == JP
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        f = fm_ev(gid, e["score_home_away_after"])
        tag = f"{gid}|{e['minute']}"
        if tag in MIN_FIX:
            mi, dm = MIN_FIX[tag][0], MIN_FIX[tag][1]; min_fix.append((gid, ldate(g), opp(g), e["minute"], dm, MIN_FIX[tag][2]))
        elif dm == 0 and mi in (45, 90) and f and f["overloadTime"] and int(f["time"]) == mi and int(f["overloadTime"]) > 0:
            dm = f"{mi}+{int(f['overloadTime'])}"; min_fix.append((gid, ldate(g), opp(g), e["minute"], dm, "FotMob 추가시간")); mi = mi + int(f["overloadTime"])
        d = ldate(g)
        if is_a:
            why = assist_reason(e)
            if why:
                judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], why))
            elif d >= GAP and not fm_assist_ok(gid, f):
                v = POST_GAP.get(tag, "미판정")
                post_gap_log.append((gid, d, opp(g), e["minute"], e["scorer"], e["assist_type"], g["competitionId"], v))
                if v == "미판정": sys.exit("[판정 필요] 2014.8 이후 Transfermarkt 단일 도움 " + tag + " " + d + " " + opp(g) + " " + e["scorer"])
                if v: raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
                else:
                    sl = g["competitionId"] in ("SL1", "SLP")
                    judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"],
                                 "슬로베니아 리그 Transfermarkt 단독(경기 기사로 확인 못 함)" if sl else "2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)"))
            else:
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
        if is_g:
            pk = 1 if e["penalty"] == "1" else 0
            if tag in PK_FIX: pk = PK_FIX[tag][0]
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))

fm_only_seen = []
for gid, fs in FME.items():
    if gid not in G: continue
    for f in fs:
        tm = [e for e in EVS[gid] if e["score_home_away_after"] == f["newScore_home_away"]]
        if f["ilicic_assist"] == "1" and not any(e["assist_id"] == JP for e in tm):
            fm_only_seen.append((gid, ldate(G[gid]), opp(G[gid]), f["time"], f["scorer"]))
        if f["ilicic_scorer"] == "1" and f["pen_shootout_event"] != "True" and not any(e["scorer_id"] == JP for e in tm):
            sys.exit("[판정 필요] FotMob 전용 골 " + gid)
for gid, g in G.items():
    pm = FPM.get(g["fotmobMatchId"])
    if pm and int(pm["assists"] or 0) > int(g["assists"] or 0):
        fm_only_seen.append((gid, ldate(g), opp(g), "선수 경기 목록", pm["assists"]))

# ---------------------------------------------------------------- 상대 Elo
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
TABLE = {}
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if "일리치치" in r["선수"]: continue
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0][:4].split("(")[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4])
# 공식 최종 순위(동률은 상대 전적 우선 — 슬로베니아 리그 규정, 위키백과 시즌 문서): Transfermarkt 표(득실차 순)와 다른 두 시즌
RANK_FIX = {("SL1", "2008-09", "FC Koper"): 8, ("SL1", "2008-09", "NK Drava Ptuj"): 9,
            ("SL1", "2023-24", "NS Mura"): 6, ("SL1", "2023-24", "NK Domzale"): 7}
for (lg, s, t), r in RANK_FIX.items():
    k = key(t); old = RANKS[(lg, s)][k]; RANKS[(lg, s)][k] = (r, old[1], old[2])

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "ili.js") or (TRACKED is not None and b not in TRACKED): continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)

# 기존 선수 자료의 리그 순위값(추정 아닌 lv): 세리에A·세리에B
LGPTS = collections.defaultdict(dict)
for b, (oe, om) in OTHERS.items():
    for x in oe:
        lv = str(x[12])
        if "추정" in lv: continue
        m = re.match(r"(세리에A|세리에B) (\d{4}-\d\d) (\d+)위$", lv)
        if m: LGPTS[(m.group(1), m.group(2))][int(m.group(3))] = x[2]
def fill_one(known, r):
    if r in known: return known[r]
    ks = sorted(known)
    lo = max([k for k in ks if k < r], default=None); hi = min([k for k in ks if k > r], default=None)
    if lo is None: return known[hi]
    if hi is None: return known[lo]
    return round(known[lo] + (known[hi] - known[lo]) * (r - lo) / (hi - lo))

# 슬로베니아 1부(10팀) 순위값(추정): 기존 선수 자료의 슬로베니아 상대 값(1위 1420 여러 시즌, 3위 1400·1360, 4위 1360, 7위 1300, 9위 1300)을
# 순위별로 모으고, 빈 순위는 이웃 값의 가운데(3위는 두 값의 평균 1380), 8·10위는 7·9위와 같은 1300
SLO = {1: 1420, 2: 1400, 3: 1380, 4: 1360, 5: 1340, 6: 1320, 7: 1300, 8: 1300, 9: 1300, 10: 1300}

BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "the", "afc", "football", "united", "city", "real", "sporting", "calcio",
        "atletico", "ca", "us", "as", "ss", "ssc", "acf", "olympique", "fk", "sv", "nk", "nd", "ns", "cd", "bc"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if (key(x[1]) == key(o) or toks(x[1]) & toks(o))]
    return cand, {(x[2], x[12]) for b, x in cand}

MAN = {}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(o, d, cid):
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand}))
        return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    seasons = [eu(d), d[:4]]
    for s in seasons:
        if (key(o), s) in TABLE:
            e, lv = TABLE[(key(o), s)]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv)
            return e, lv
    s = eu(d)
    tab = RANKS.get(("SL1", s), {})
    if key(o) in tab:
        r, n, _ = tab[key(o)]
        prog = " (11월 중순 현재)" if s == "2026-27" else ""
        e, lv = SLO[r], f"슬로베니아 {s}{prog} {r}위 (추정, 슬로베니아 1부 순위값)"
        ELO_SRC["순위표+슬로베니아 순위값(추정)"] += 1; ELO_LOG[(o, d)] = ("slo", e, lv); return e, lv
    tab = RANKS.get(("IT2", s), {})
    if key(o) in tab and LGPTS.get(("세리에B", s)):
        r, n, _ = tab[key(o)]; e = fill_one(LGPTS[("세리에B", s)], r)
        ELO_SRC["순위표+리그 순위값"] += 1; ELO_LOG[(o, d)] = ("model", e, f"세리에B {s} {r}위"); return e, f"세리에B {s} {r}위"
    for s2 in seasons:
        if (o, s2) in MAN:
            e, lv = MAN[(o, s2)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(o, d)] = ("man", e, lv)
            return e, lv
    MISS.append((o, d, cid)); return 0, "?"

exec(open(os.path.join(HERE, "elo_ilicic.py"), encoding="utf-8").read())   # MAN 표(판정 기록 7절)

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid)
    t = tie_of(gid)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and (ko or t)) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4], r[0]))
if MISS:
    for x in sorted(set(MISS), key=lambda t: t[1]): print("MISS", x)
    sys.exit("상대 Elo 없음 %d" % len(MISS))

exec(open(os.path.join(HERE, "out_ilicic.py"), encoding="utf-8").read())   # 동료 대조·설명·점검·출력
