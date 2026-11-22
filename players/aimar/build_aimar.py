#!/usr/bin/env python3
"""파블로 아이마르 (Pablo César Aimar, Transfermarkt 3411): raw/ -> aimar.json + aim.js (판정 근거는 judgments.md)

  python3 players/aimar/build_aimar.py            # 파일 쓰기(players/aimar/aim.js; AIM_OUT=<경로>로 바꿀 수 있음)
  python3 players/aimar/build_aimar.py --debug    # Elo 출처 로그
  python3 players/aimar/build_aimar.py --stat     # 요약·판정·동료 대조
  python3 players/aimar/build_aimar.py --ties     # 합산 행

사비올라 build(players/saviola, 수집기 형식이 거의 같음)를 바탕으로 함. 리버 1998~2001 날짜는 사비올라 자료와 같은 규칙(같은 경기는 같은 날짜).
상대 Elo는 v1.226 규칙: 같은 경기 다른 선수 자료 → Elo 통합표(같은 팀·시즌) → 출처로 확인한 순위로 라벨을 만들고
tools/league_rank_apply.py 의 value()로 값을 정함(직접 숫자를 넣지 않음). 스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_JS = os.environ.get("AIM_OUT") or os.path.join(HERE, "aim.js")
OUT_JSON = os.path.join(HERE, "aimar.json")
ME = "3411"
ME_KO = "파블로 아이마르"
PFX = "AIM"
# 사용자 확인 대상(Transfermarkt에 없는 경기, 경기 단위 출처로 골이 확인된 것만): False로 두면 뺌
INCLUDE_RIVER_1998 = True    # 1998.2.20 로사리오 센트랄전(클라우수라 2라운드) 42분 골
INCLUDE_JDT_2014 = True      # 조호르 다룰 타짐 2014 말레이시아 슈퍼리그 골 2경기

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)

# ---------------------------------------------------------------- 날짜
# 유럽 클럽: TM 리포트 날짜(없으면 TM API UTC 시각을 클럽 연고지 시간으로 바꾼 날짜). 리버 플레이트: 사비올라 자료와 같은 규칙 —
# 같은 경기(경기 id)는 사비올라 build의 날짜를 그대로 쓰고, 나머지는 TM API 시각(UTC)이 실제 킥오프면 UTC−3 날짜,
# 중부 유럽 자정(UTC 22:00/23:00 정각)·12:00·13:00 정각이면 시각 미상 자리값 → 중부 유럽 날짜(TM 일정 날짜). RSSSF 경기 목록과 대조.
def _lastsun(y, m):
    x = datetime.date(y, m, 31)
    while x.weekday() != 6: x -= datetime.timedelta(1)
    return x
def _cet_mid_utc_hour(d):
    return 22 if _lastsun(d.year, 3) <= d < _lastsun(d.year, 10) else 23
def _sv_dates():
    """사비올라 build의 리버 날짜 규칙(players/saviola/build_saviola.py _ldate)을 사비올라 raw에 적용."""
    fn = os.path.join(os.path.dirname(HERE), "saviola", "raw", "tm_games.csv")
    fix = {"4453246": "1998-10-31", "4453358": "1998-12-04", "4453366": "1998-12-12", "4553217": "1999-05-22", "4159230": "1999-08-28",
           "4161332": "1999-11-06", "3797006": "2000-03-11", "3799997": "2000-04-12", "3800036": "2000-05-20", "3837964": "2000-08-19",
           "3840488": "2000-09-06"}
    out = {}
    for g in csv.DictReader(open(fn, encoding="utf-8")):
        gid = g["gameId"]
        if g["club_id"] != "209": continue
        if gid in fix: out[gid] = fix[gid]; continue
        sched = g["date_local_tm_report"] or g["date_local_schedule"]
        u = datetime.datetime.fromisoformat(g["date_utc"])
        if (u.hour, u.minute) in ((12, 0), (13, 0)): out[gid] = sched; continue
        sd = datetime.date.fromisoformat(sched)
        if u.minute == 0 and u.hour == _cet_mid_utc_hour(sd) and u.date() == sd - datetime.timedelta(1): out[gid] = sched; continue
        out[gid] = (u - datetime.timedelta(hours=3)).date().isoformat()
    return out
SV_LD = _sv_dates()
DATE_LOG = []
def _river_rule(g):
    u = datetime.datetime.fromisoformat(g["date_utc"])
    if (u.hour, u.minute) in ((12, 0), (13, 0)): return u.date().isoformat(), "자리값 12/13시"
    nxt = u.date() + datetime.timedelta(1)
    if u.minute == 0 and u.hour == _cet_mid_utc_hour(nxt): return nxt.isoformat(), "자리값 중부 유럽 자정"
    return (u - datetime.timedelta(hours=3)).date().isoformat(), "UTC−3"
# 사비올라 자료에 없는 리버 경기 중 규칙 날짜가 RSSSF 경기 날짜(요일 표기, rsssf/arg99.txt)와 다른 5경기 → RSSSF 날짜(사비올라 선례)
DATE_FIX = {"4453137": "1998-08-22", "4453193": "1998-09-25", "4453205": "1998-10-03", "4453231": "1998-10-25", "4453263": "1998-11-14"}
def _ldate(g):
    gid = g["gameId"]
    if gid in DATE_FIX:
        DATE_LOG.append((gid, g["date_local_computed"], DATE_FIX[gid], g["date_utc"][:16], g["opponent"], "RSSSF")); return DATE_FIX[gid]
    if g["club_id"] != "209":
        return g["date_report"] or g["date_local_computed"]
    if gid in SV_LD: return SV_LD[gid]
    d, why = _river_rule(g)
    if d != g["date_local_computed"]: DATE_LOG.append((gid, g["date_local_computed"], d, g["date_utc"][:16], g["opponent"], why))
    return d
LD = {gid: _ldate(g) for gid, g in G.items()}
def ldate(g): return LD[g["gameId"]]

# RSSSF 아르헨티나 경기 목록(rsssf/arg98·arg99·arg00·arg01.txt, 요일 표기)과 리버 리그 경기 날짜 대조
RS_NAME = {"Dep Español": "Club Deportivo Español", "Huracán": "CA Huracán", "Huracán BA": "CA Huracán", "Unión": "CA Unión (Santa Fe)", "Unión SF": "CA Unión (Santa Fe)",
           "Boca Juniors": "CA Boca Juniors", "Platense": "Club Atlético Platense", "Newell's OB": "CA Newell's Old Boys", "Newell's Old Boys": "CA Newell's Old Boys",
           "Vélez": "CA Vélez Sarsfield", "Vélez Sarsfield": "CA Vélez Sarsfield", "San Lorenzo": "CA San Lorenzo de Almagro", "Independiente": "CA Independiente",
           "Gimnasia J": "Club Atlético Gimnasia y Esgrima (Jujuy)", "Colón": "CA Colón", "Colón SF": "CA Colón", "Arg Juniors": "AA Argentinos Juniors",
           "Argentinos Juniors": "AA Argentinos Juniors", "Estudiantes LP": "Club Estudiantes de La Plata", "Estudiantes": "Club Estudiantes de La Plata",
           "Talleres Cba": "CA Talleres", "Rosario Central": "CA Rosario Central", "Rosario C": "CA Rosario Central", "Lanús": "CA Lanús",
           "Ferro Carril Oeste": "Club Ferro Carril Oeste", "Ferro": "Club Ferro Carril Oeste", "Belgrano Cba": "Club Atlético Belgrano",
           "Gimnasia LP": "Club de Gimnasia y Esgrima La Plata", "Racing Club": "Racing Club", "Racing": "Racing Club", "Instituto": "Instituto ACC",
           "Chacarita Juniors": "CA Chacarita Juniors", "Chacarita": "CA Chacarita Juniors", "Los Andes": "CA Los Andes", "Almagro": "Club Almagro", "Argentinos Js": "AA Argentinos Juniors",
           "Newell's": "CA Newell's Old Boys", "Talleres": "CA Talleres", "Belgrano": "Club Atlético Belgrano", "Gimnasia (LP)": "Club de Gimnasia y Esgrima La Plata",
           "Chacarita Js": "CA Chacarita Juniors", "Boca": "CA Boca Juniors", "Boca Js": "CA Boca Juniors", "Racing C": "Racing Club", "Rosario Central": "CA Rosario Central",
           "Estudiantes (LP)": "Club Estudiantes de La Plata", "Gimnasia (J)": "Club Atlético Gimnasia y Esgrima (Jujuy)", "Huracán (BA)": "CA Huracán",
           "Unión (SF)": "CA Unión (Santa Fe)", "Colón (SF)": "CA Colón", "Arg Js": "AA Argentinos Juniors", "Instituto (C)": "Instituto ACC", "Newell's O.B.": "CA Newell's Old Boys",
           "Newell´s O. B.": "CA Newell's Old Boys", "Chacarita Jrs": "CA Chacarita Juniors", "Argentinos Jrs": "AA Argentinos Juniors", "Ferro C. O.": "Club Ferro Carril Oeste"}
MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
def rsssf_river(fn, y0):
    out = []; cur = None; second = False   # second: 해가 바뀐 뒤(클라우수라) — 7월 경기도 다음 해
    for line in open(os.path.join(HERE, "rsssf", fn), encoding="utf-8", errors="replace"):
        m = re.match(r"\s*\[(\w{3}) (\d+)(?:, \w+)?\]", line)
        if m:
            mo = MON[m.group(1)]
            if mo < 7: second = True
            if re.match(r"\s*(Apertura|Clausura)\s*$", line): pass
            y = y0 + (1 if (mo < 7 or (second and mo == 7)) else 0); cur = f"{y}-{mo:02d}-{int(m.group(2)):02d}"; continue
        if re.match(r"\s*Apertura\s*$", line): second = False
        m = re.match(r"\s*(.+?)\s+(\d+)-(\d+)\s+(.+?)\s*(\[.*)?$", line)
        if m and cur and ({m.group(1).strip(), m.group(4).strip()} & {"River Plate", "River"}):
            o = m.group(4).strip() if m.group(1).strip() in ("River Plate", "River") else m.group(1).strip()
            out.append((cur, o))
    return out
RS_RIVER = rsssf_river("arg98.txt", 1997) + rsssf_river("arg99.txt", 1998) + rsssf_river("arg00.txt", 1999) + rsssf_river("arg01.txt", 2000)
RS_CHECK = []
for g in GAMES:
    if g["club_id"] != "209" or g["competitionId"] not in ("ARG1", "ARGC"): continue
    d = ldate(g); o = re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
    near = [(rd_, ro) for rd_, ro in RS_RIVER if RS_NAME.get(ro, ro) == o and abs((datetime.date.fromisoformat(rd_) - datetime.date.fromisoformat(d)).days) <= 20]
    if not near: RS_CHECK.append(("RSSSF에 없음", g["gameId"], d, o)); continue
    if not any(rd_ == d for rd_, _ in near): RS_CHECK.append(("날짜 다름", g["gameId"], d, [x[0] for x in near], o))

OPP_RENAME = {"Club Almagro": "Club Almagro (Buenos Aires)"}   # 사비올라 자료와 같은 이름(Elo 통합표 이름 묶임 방지)
def opp(g):
    o = re.sub(r"\s*\(\s*-\s*\d{4}\)", "", g["opponent"]).strip()
    return OPP_RENAME.get(o, o)

GAP = "2014-08-01"   # 이 전 도움은 TM 단일 출처 허용

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"ARG1", "ARGC", "AR1N", "ES1", "PO1", "MYS1"}
CUPS = {"CDR", "POPO", "POCP", "ARCA"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid in CUPS:
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"                                      # 조별(타사 다 리가)·2~4라운드·16강, 코파 아르헨티나 3라운드(64강)
    if cid == "ALPL": return "dc"                        # 리길야 프레 리베르타도레스 결승(단판): 국내컵 비중(사비올라·바티스투타·밀리토 선례)
    if cid in ("SUC", "POSU", "USC"): return "df"        # 수페르코파·수페르타사·UEFA 슈퍼컵(소니 앤더슨 선례) = 결승 비중
    if cid == "UI": return "elq"                         # 인터토토컵(리켈메·소니 앤더슨 선례)
    if cid == "CLQ": return "clq"
    if cid == "CL":
        if r.startswith("group"): return "clg"           # 2001-02·2002-03 2차 조별('Group 1·2') 포함
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "ELQ": return "elq"
    if cid == "UEFA":
        if r.startswith("first round"): return "elq"     # UEFA컵 1라운드(2009년 이전) = 유로파 예선
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 2·3라운드·32강(intermediate stage)·16강·8강
    if cid == "EL":
        if r.startswith("group"): return "elg"
        if r.startswith("semi"): return "elsf"
        if r.startswith("final"): return "elf"
        return "elk"                                     # 32강('Second Round')·16강·8강
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"                                     # 조별·16강
    if cid in ("CMER", "CS"):                            # 코파 메르코수르 = 수다메리카나 비중(사비올라·주니뉴·리켈메 선례)
        if r.startswith("quarter"): return "csak"
        if r.startswith("semi"): return "csasf"
        if r.startswith("final"): return "csaf"
        return "csa"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def rnd_of(g):
    return g["round"] or (MI[g["gameId"]]["round_report"] if g["gameId"] in MI else "")

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r): return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d, rnd):
    """(원정 다득점, 연장)"""
    if cid in ("CL", "CLQ", "UEFA", "EL", "ELQ", "UI"): return (1, 1)  # UEFA 2020-21까지
    if cid in ("CDR", "SUC"): return (1, 1)                         # 스페인 국내 대회 2018-19까지
    if cid == "POPO": return (1, 1)                                 # 타사 준결승(팔카오·사비올라 선례)
    if cid == "CLI": return (0, 0) if d < "2005-01-01" else (1, 0)  # 리베르타도레스 2004년까지 원정 다득점 없음(리켈메·사비올라 선례)
    if cid in ("CMER", "CS"): return (1, 0)                         # 메르코수르(사비올라·주니뉴 선례)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def other_leg(gid):
    m = MI[gid]; oid = m["other_leg_id"]; club = G[gid]["club_id"]
    if oid in MI:
        o = MI[oid]; fh, fa = map(int, o["final"].split(":"))
        if o["result_flag"] == "pens": sys.exit("다른 차전이 승부차기 " + gid)
        if o["home_id"] == club: return (fh, fa)
        if o["away_id"] == club: return (fa, fh)
        sys.exit("다른 차전 편 판정 실패 " + gid)
    oh, oa = map(int, m["other_leg_score"].split(":"))
    return (oh, oa) if side_of(gid) == "h" else (oa, oh)

def tie_of(gid):
    g = G[gid]; rnd = rnd_of(g).lower()
    if "leg" not in rnd: return None
    s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g), rnd)
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    ours, theirs = other_leg(gid)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- Transfermarkt에 없는 경기(경기 단위 출처로 골이 확인된 것만)
# (날짜, 상대, 대회 TM 코드, 라운드, 출전 분(추정), 골 목록[(분, 표시 분, 골 전 우리, 상대, PK)], 출처)
EXTRA = []
if INCLUDE_RIVER_1998:
    # 클라우수라 1998 2라운드 로사리오 센트랄 2-2 리버(원정). 스페인어 위키백과 'Anexo:Temporada 1997-98 del Club Atlético Rosario Central'
    # 경기 상자(InfoFútbol 경기 기록 인용): 소린 26', 아이마르 42' / 카르보나리 50'·66'. 본문 '0-2로 지다가 카르보나리 두 골로 비김'.
    # geocities futbolpasion(아이마르 첫 골 1998.2.20, 42분 전반), La Página Millonaria 2015.2.20 기사(2라운드 원정 2-2, 살라스 패스), RSSSF arg98 [Feb 20, Fri].
    EXTRA.append(("1998-02-20", "CA Rosario Central", "ARGC", "2. Matchday", 90, [(42, 0, 1, 0, 0)], "es.wiki 경기 상자·geocities·La Página Millonaria·RSSSF"))
if INCLUDE_JDT_2014:
    # 영어 위키백과 '2014 Johor Darul Ta'zim F.C. season' 경기 상자 3·4라운드, '2014 Malaysia Super League' 경기 상자(같은 득점자, 1.28 골 42분), RSSSF malay2014(스코어).
    EXTRA.append(("2014-01-28", "LionsXII", "MYS1", "3. Matchday", 90, [(41, 0, 1, 0, 0)], "en.wiki JDT 2014 시즌·2014 말레이시아 슈퍼리그·RSSSF"))
    EXTRA.append(("2014-02-07", "Pahang FA", "MYS1", "4. Matchday", 90, [(47, "45+2", 0, 1, 0)], "en.wiki JDT 2014 시즌·2014 말레이시아 슈퍼리그·RSSSF"))

# ---------------------------------------------------------------- 출전
M = []
for g in sorted(GAMES, key=lambda g: (ldate(g), g["gameId"])):
    if not g["playedMinutes"]: sys.exit("출전 분 없음 " + g["gameId"])
    M.append([ldate(g), opp(g), comp_of(g["competitionId"], rnd_of(g)), int(g["playedMinutes"])])
for d, o, cid, rnd, mn, gl, src in EXTRA:
    M.append([d, o, comp_of(cid, rnd), mn, 1])
M.sort(key=lambda m: m[0])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def is_og(e): return e["own_goal"] == "1" or e["goal_desc"] == "Own-goal"

A_CHECK = {}   # 2014.8 이후 도움 없음(아이마르 마지막 TM 도움 2013년)
def a_key(gid, minute): return f"{gid}|{minute}"

def fm_min_match(f, tm_min_str, tol=2):
    a = mins(tm_min_str)[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
    if abs(a - b) <= tol: return True
    base = int(tm_min_str.split("+")[0]) if "+" in tm_min_str else None
    return base is not None and not f["overloadTime"] and int(f["time"]) == base
def fm_assist(gid, e):
    for f in FME.get(gid, []):
        if f["time"] and ("Aimar" in f["assistStr"]) and fm_min_match(f, e["minute"]): return True
    return False

def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())

A_STATUS = []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t == "Deflected": return "굴절"
    if d < GAP:
        if d >= "2010-07-01": A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+FotMob 이벤트" if fm_assist(gid, e) else "TM 단독(2014.8 전 허용)"))
        return None
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음"))
    return "2014.8 이후 단일 출처(판정 없음)"

def ev_key(e):
    h, a = map(int, e["score_home_away_after"].split("-"))
    return h + a
raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid)
    evs = sorted(EVS[gid], key=ev_key)
    if [ev_key(e) for e in evs] != list(range(1, len(evs) + 1)):
        if any(ME in (e["scorer_id"], e["assist_id"]) for e in evs): sys.exit("골 순서 이상 " + gid)
        continue   # 아이마르 기록 없는 경기의 리포트 스코어 표기 오류(986210 마카비 하이파전 90분 0-4 두 번) — 쓰지 않음
    for e in evs:
        sd = e["side"][0]
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = (h - (sd == "h"), a - (sd == "a"))
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 골의 본인 도움 표기)", ldate(g), opp(g), e["minute"], e["assist_type"] or "(유형 빈칸)", e["goal_desc"] or "(설명 빈칸)"))
        if e["scorer_id"] == ME and is_og(e): sys.exit("자책골 " + gid)
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mi, dm = mins(e["minute"])
        if is_a:
            why = assist_reason(e, ldate(g), gid)
            if why:
                judg.append(("도움 제외", ldate(g), opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if e["penalty"] == "1" and not pk and e["goal_desc"] != "Penalty rebound": sys.exit("PK 판정 확인 " + gid)
            if e["goal_desc"] == "Penalty rebound": judg.append(("PK 리바운드 골(PK 아님)", ldate(g), opp(g), e["minute"]))
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
    if MI[gid]["result_flag"] == "pens": continue   # 승부차기 경기: 최종 스코어에 승부차기 포함
    if (h, a) != (fh, fa): SCORE_MISMATCH.append((gid, ldate(G[gid]), (h, a), (fh, fa)))
for gid, *_ in SCORE_MISMATCH:
    if any(r[1] == gid for r in raw_rows): sys.exit("골 목록이 최종 스코어와 다른 경기에 아이마르 기록 " + gid)

# ---------------------------------------------------------------- 이름·기존 자료
ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "):
            ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
MANUAL_ALIAS = {}
import functools
@functools.lru_cache(maxsize=None)
def key(n):
    k = norm(n); k = MANUAL_ALIAS.get(k, k)
    return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if ME_KO in r["선수"].split("·"): continue
        for nm in [r["팀"]] + r["이름 표기"].split(" / "):
            TABLE[(key(nm), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

TRACKED = set(subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "clubcolors.js", "finals.js", "aim.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn)
    OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "de", "futebol", "clube", "the", "afc", "football", "united", "city", "real", "sporting", "cp",
        "ec", "foot", "ball", "atletico", "calcio", "sport", "sociedade", "olympique", "cd", "ud", "rcd", "sv", "as", "ss", "sl", "gd", "cs",
        "athletic", "wanderers", "rangers", "town", "county", "albion", "rovers", "milan", "inter", "madrid", "moscow", "ca", "deportivo", "fk", "vfl", "bv",
        "racing", "arsenal", "hotspur", "palace", "villa", "ham", "manchester", "park", "west", "aston", "vitoria", "academica", "uniao",
        "sevilla", "betis", "celta", "vigo", "gijon", "coruna", "las", "palmas", "valencia", "levante", "rayo", "vallecano", "balompie", "sociedad", "barcelona", "espanyol",
        "belenenses", "braga", "porto", "benfica", "lisboa", "bk", "jk", "spor", "kulubu", "istanbul", "ankara", "athens", "praha", "bayer", "borussia", "hertha", "brugge",
        "juniors", "gimnasia", "esgrima", "plata", "central", "union", "santa", "atlas", "nacional", "universidad", "river", "plate", "independiente", "deportes", "almagro",
        "lorenzo", "san", "old", "boys", "velez", "colon", "talleres", "estudiantes", "chacarita", "ferro", "carril", "oeste", "lanus", "huracan", "belgrano", "instituto",
        "platense", "andes", "argentinos", "rosario", "newell", "newells", "zaragoza", "mallorca", "osasuna", "valladolid", "santander", "racing", "alaves", "getafe",
        "villarreal", "deportiva", "guimaraes", "setubal", "maritimo", "leiria", "olhanense", "pacos", "ferreira", "esporte", "regatas", "chile", "catolica", "lionsxii", "pahang"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d, cid):
    exact = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)]
    cand = exact or [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위표 → 라벨 → 값(tools/league_rank_apply.py)
_LRA = {'__file__': os.path.join(ROOT, 'tools', 'league_rank_apply.py'), '__name__': 'lra'}
_argv = sys.argv; sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA['__file__'], encoding='utf-8').read().split("if __name__ == '__main__':")[0], 'lra', 'exec'), _LRA)
sys.argv = _argv
def lv_value(lv, d):
    m_ = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv)
    if m_:   # 순위를 못 찾은 상대: 그 나라·단계 기준점(tools/league_rank_apply.py base())
        cal = m_.group(4) is None; y = int(m_.group(3)) + (0 if cal else 1)
        return int(round(_LRA['base'](_LRA['KO'][m_.group(1)], int(m_.group(2)), y, cal)))
    p = _LRA['parse'](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA['value'](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    return v

RANKS = collections.defaultdict(dict)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league" or p[0].startswith("INVALID"): continue
        if p[0] == "ES3C" and p[1].startswith("2001-02"): continue    # TM 페이지가 모든 팀을 1위로 표시(결과 없음) → 쓰지 않음
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]), p[4], p[1])
# 아르헨티나 반시즌(아페르투라·클라우수라) 순위: 영어 위키백과 시즌 문서(wiki_tables/, 사비올라 자료와 같은 파일) — RSSSF 최종 순위와 같음.
# 클라우수라 1998은 RSSSF arg98 최종표(rsssf/arg98.txt).
WT = os.path.join(HERE, "wiki_tables")
def wiki_tables(fn):
    t = open(os.path.join(WT, fn), encoding="utf-8").read(); out = {}
    for m in re.finditer(r"\{\{#invoke:sports table", t):
        b_ = t[m.start():]; b_ = b_[:b_.find("\n}}")]
        sec = re.search(r"\|section\s*=\s*([^\n|]+)", b_)
        names = {k: re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", v).strip() for k, v in re.findall(r"\|name_([^=\s]+)\s*=\s*([^\n]+)", b_)}
        order = re.search(r"\|team_order\s*=\s*([^\n]+)", b_)
        if order: teams = [x.strip() for x in order.group(1).split(",") if x.strip()]
        else:
            teams = []
            for _, nm_ in re.findall(r"\|team(\d+)\s*=\s*([^|\n]+)", b_):
                if nm_.strip() not in teams: teams.append(nm_.strip())
        out[sec.group(1).strip() if sec else "?"] = [names.get(x, x) for x in teams]
    return out
ARG_WIKI = {}   # (단계, 연도) -> [팀 이름(위키백과)]
for fn, yA, yC in (("1998–99_Argentine_Primera_División.txt", 1998, 1999), ("1999–2000_Argentine_Primera_División.txt", 1999, 2000),
                   ("2000–01_Argentine_Primera_División.txt", 2000, 2001)):
    w = wiki_tables(fn)
    ARG_WIKI[("Apertura", yA)] = w["Torneo Apertura"]; ARG_WIKI[("Clausura", yC)] = w["Torneo Clausura"]
# RSSSF arg98 Clausura 1998 최종표(위키백과 이름으로 옮김)
ARG_WIKI[("Clausura", 1998)] = ["Vélez Sársfield", "Lanús", "Gimnasia y Esgrima (LP)", "Gimnasia y Esgrima (J)", "San Lorenzo", "Boca Juniors", "River Plate",
                                "Argentinos Juniors", "Newell's Old Boys", "Ferro Carril Oeste", "Independiente", "Estudiantes (LP)", "Rosario Central", "Platense",
                                "Racing", "Colón", "Gimnasia y Tiro", "Huracán", "Unión", "Deportivo Español"]
ARG_NAME = {"CA Boca Juniors": "Boca Juniors", "Club de Gimnasia y Esgrima La Plata": "Gimnasia y Esgrima (LP)", "Racing Club": "Racing",
            "CA Lanús": "Lanús", "CA Colón": "Colón", "CA San Lorenzo de Almagro": "San Lorenzo", "AA Argentinos Juniors": "Argentinos Juniors",
            "CA Newell's Old Boys": "Newell's Old Boys", "CA Unión (Santa Fe)": "Unión", "CA Rosario Central": "Rosario Central",
            "CA Vélez Sarsfield": "Vélez Sársfield", "Club Estudiantes de La Plata": "Estudiantes (LP)", "CA Talleres": "Talleres (C)",
            "Club Atlético Gimnasia y Esgrima (Jujuy)": "Gimnasia y Esgrima (J)", "CA River Plate": "River Plate", "CA Independiente": "Independiente",
            "Club Ferro Carril Oeste": "Ferro Carril Oeste", "CA Huracán": "Huracán", "Club Atlético Belgrano": "Belgrano", "Club Atlético Platense": "Platense",
            "CA Chacarita Juniors": "Chacarita Juniors", "Instituto ACC": "Instituto", "Club Almagro (Buenos Aires)": "Almagro", "CA Los Andes": "Los Andes",
            "Club Deportivo Español": "Deportivo Español"}
APERTURA_START = {1998: "1998-08-07", 1999: "1999-08-06", 2000: "2000-07-28"}   # RSSSF 1라운드 날짜
def arg_stage(d, cid, g):
    """경기 날짜에 진행 중이던 아르헨티나 1부 단계 (단계, 연도). 리그 경기는 그 경기의 대회."""
    if g is not None and cid == "ARG1": return ("Apertura", int(g["seasonId"]))
    if g is not None and cid == "ARGC": return ("Clausura", int(g["seasonId"]) + 1)
    y = int(d[:4])
    if y in APERTURA_START and d >= APERTURA_START[y]: return ("Apertura", y)
    return ("Clausura", y)
ARG_KEYS = {key(n) for n in ARG_NAME}
ARG_KO = {"Apertura": "아페르투라", "Clausura": "클라우수라"}
RANK_LOG = []
def arg_label(o, d, cid, g):
    st_, y = arg_stage(d, cid, g)
    L = ARG_WIKI[(st_, y)]; nm = ARG_NAME[o]
    r = L.index(nm) + 1
    tm = RANKS.get(("ARG1" if st_ == "Apertura" else "ARGC", f"{y if st_ == 'Apertura' else y - 1}-{str(y + (1 if st_ == 'Apertura' else 0))[2:]}"), {}).get(key(o))
    if tm and tm[0] != r: RANK_LOG.append((st_, y, o, tm[0], r))
    return f"아르헨티나 1부 {ARG_KO[st_]} {y} {r}위/{len(L)}팀", f"{y}/{st_}"

BIGL = {"PO1": "포르투갈 1부", "ES1": "라리가", "GB1": "프리미어리그", "IT1": "세리에A", "FR1": "리그1", "L1": "분데스리가", "NL1": "에레디비시"}
OTHL = {"TR1": ("튀르키예", "Süper Lig"), "RU1": ("러시아", "Russian Premier League"), "ISR1": ("이스라엘", "Ligat ha'Al")}
CAL_LG = {"RU1", "AR1N", "CLPD", "SE1", "BRA1"}
def make_label(lg, season, r, n):
    if lg in BIGL:
        pre = BIGL[lg]; y = int(season[:4]) + 1
        n0 = _LRA['ERA']['teams'](pre, y)
        return f"{pre} {season} {r}위" + (f"/{n}팀" if n != n0 else "")
    if lg in OTHL:
        cn, nm = OTHL[lg]
        return f"{cn} 1부 {season} {r}위/{n}팀 ({nm})"
    if lg == "AR1N": return f"아르헨티나 1부 {season} {r}위/{n}팀"
    if lg == "PO2": return f"포르투갈 2부 {season} {r}위/{n}팀"
    if lg == "ES2": return f"세군다 {season} {r}위/{n}팀"
    return None

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

MAN = {}   # 순위표 밖 상대: (key, 시즌) -> lv (값은 라벨에서 계산)
def man(o, s, lv): MAN[(key(o), s)] = lv
# 7월 예선: 상대 리그 시즌이 아직 시작 전이면 막 끝난 시즌(튀르키예 쉬페르리그 2011-12는 2011.9.9 개막)
SEASON_OVERRIDE = {("Trabzonspor", "2011-07-27"): "2010-11"}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []

def opp_elo(o, d, cid, g):
    cand, vals = same_match(o, d, cid)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    k = key(o)
    arg = k in ARG_KEYS and d < "2002-01-01"
    if arg: alv, aseason = arg_label(o, d, cid, g); seasons = [aseason]
    elif cid in ("AR1N", "MYS1"): seasons = [d[:4]]
    else: seasons = [eu(d), d[:4]]
    if (o, d) in SEASON_OVERRIDE: seasons = [SEASON_OVERRIDE[(o, d)]]
    for s in seasons:
        if (k, s) in MAN:
            lv = MAN[(k, s)]; e = lv_value(lv, d)
            ELO_SRC["순위 라벨(직접 확인)"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            if cid in BIGL and not lv.startswith(BIGL[cid]): continue   # 같은 이름 다른 나라 팀(CD Nacional: 우루과이 나시오날과 이름이 같음)
            p = _LRA['parse'](lv, d)
            if p and _LRA['value'](*p) != e: TABLE_DIFF.append((o, s, e, lv, _LRA['value'](*p)))
            if arg:
                rr = re.search(r"(\d+)위", lv.split(" (")[0]); ra = re.search(r"(\d+)위", alv)
                if rr and rr.group(1) != ra.group(1): TABLE_DIFF.append(("순위 다름", o, s, lv, alv))
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s); return e, lv
    if arg:
        e = lv_value(alv, d); ELO_SRC["순위표 → 라벨"] += 1; ELO_LOG[(o, d)] = ("rank", e, alv); NEW_TS[(o, seasons[0])] = (e, alv); return e, alv
    for (lg, s), t in RANKS.items():
        if lg in ("ARG1", "ARGC"): continue
        if k in t and (s == eu(d) or (lg in CAL_LG and s == d[:4])):
            r, n, nm, _ = t[k]
            lv = make_label(lg, s, r, n)
            if lv:
                e = lv_value(lv, d)
                ELO_SRC["순위표 → 라벨"] += 1; ELO_LOG[(o, d)] = ("rank", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    MISS.append((o, d, cid, tuple(seasons))); return 0, "?"

if os.path.exists(os.path.join(HERE, "man_elo.py")):
    exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read())

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], rnd_of(g)
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, cid, g)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
for d, o, cid, rnd, mn, gl, src in EXTRA:
    for mi, dm, gf, ga, pk in gl:
        elo, lv = opp_elo(o, d, cid, None)
        E.append(["g", o, elo, comp_of(cid, rnd), mi, gf, ga, ko_of(cid, rnd), pk, d, 0, dm, lv, 0])

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
    print("TABLE_DIFF", TABLE_DIFF)
    for x in RANK_LOG: print("RANK", x)
    for x in sorted(NEW_TS.items()): print("NEW", x)
    sys.exit(0)
if "--ties" in sys.argv:
    for r in E:
        if len(r) > 14: print(r[:2], r[3], r[9], r[0], r[4], r[5], r[6], r[7], r[10], r[11], r[14])
    print([(r[9], r[1], r[4], r[10], r[11]) for r in E if r[4] > 90])
    sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or not any(r["time"] for r in FME.get(gid, [])): continue
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["aimar_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "pen" in (f["goalDescriptionKey"] or f["goalDescription"] or "").lower() or "penalty" in (f["suffix"] or "").lower()
        if tp != fp or not fm_min_match(f, t["minute"], 1): FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None): d.append(f"단판/합산 {a[7]}{a[14] if len(a) > 14 else ''}/{b[7]}{b[14] if len(b) > 14 else ''}")
    if a[10] != b[10]: d.append("연장")
    return d
CROSS = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and re.search(r"Aimar", x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(아이마르 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("아이마르 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("타인 도움 행이 아이마르 골과 같은 시각", b, r[9], r[4], hit[0][13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x[1], r[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회", "단판"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    OMK = collections.defaultdict(list)
    for mm in om: OMK[key(mm[1])].append(mm)
    for m in M:
        km = key(m[1])
        for mm in OMK.get(km, []):
            if mm[0] == m[0] and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
            # 같은 상대·가까운 날짜(±2일)인데 날짜가 다른 출전 행(날짜 규칙 차이 점검)
            elif mm[0] != m[0] and abs((datetime.date.fromisoformat(mm[0]) - datetime.date.fromisoformat(m[0])).days) <= 2:
                CROSS.append(("같은 상대 출전 행 날짜 1~2일 차이", b, m[0], mm[0], m[1]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0] == "도움 제외" and j[1] == x[9] and j[3] != "?" and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("TM 아이마르 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("rivai", "2001-01-31"), ("valai", "2006-07-29"), ("zarai", "2008-07-17"), ("benai", "2013-08-07"), ("jdtai", "2014-04-21"), ("rivai", None)]
TM_CLUB = {"209": "rivai", "1049": "valai", "142": "zarai", "294": "benai"}
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["club_id"])
for d, o, cid, *_ in EXTRA:
    if club_of(d) != ("jdtai" if cid == "MYS1" else "rivai"): sys.exit("추가 경기 클럽 " + d)
def season_of(d, club):
    y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
    if club in ("rivai", "jdtai"): return str(y)
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("리버 플레이트 1998~2001", "2001-01-31"), ("발렌시아", "2006-07-29"), ("레알 사라고사", "2008-07-17"), ("벤피카", "2013-08-07"),
          ("조호르 다룰 타짐", "2014-04-21"), ("리버 플레이트 2015", "9999")]
def stint(d):
    for n, u in STINTS:
        if d < u: return n
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for n, u in STINTS)
for m in M: ST[stint(m[0])][0] += 1; ST[stint(m[0])][3] += m[3]
for r in E: ST[stint(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NEST = sum(1 for m in M if len(m) > 4)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
def d_(x): y, m, d = x.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EXJ = [j for j in judg if j[0] == "도움 제외"]
TM_A = sum(1 for gid in EVS if gid in G for e in EVS[gid] if e["assist_id"] == ME and e["scorer_id"] != ME)
UNTYPED = sum(1 for r in raw_rows if r[0] == "a" and not r[8])
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC), TM_A, UNTYPED, NEST)
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    for c in CROSS: print(c)
    print("FM", FM_CMP)
    print("score mismatch", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    print("dates changed", len(DATE_LOG)); [print(" ", x) for x in DATE_LOG]
    print("RSSSF", RS_CHECK)
    print("TABLE_DIFF", TABLE_DIFF)
    for x in RANK_LOG: print("RANK", x)
    for x in sorted(NEW_TS.items()): print("NEW", x)
    sys.exit(0)

exec(open(os.path.join(HERE, "note_aimar.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "csa", "lib", "elk", "elq", "cwc", "acl", "df", "clg", "cl16", "EXTRA"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6], r[13])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
mdates = collections.Counter(m[0] for m in M)
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
for d, rs in by.items():
    if d not in mdates: problems.append(("E 날짜가 M에 없음", d))
    gl = sorted(rs, key=lambda r: (r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5))
    for a, b in zip(gl, gl[1:]):
        if (b[5], b[6]) < (a[5], a[6]) or b[5] < a[5] or b[6] < a[6]: problems.append(("스코어 역순", d, a[4], b[4]))
for r in E:
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if not r[2] or r[12] == "?": problems.append(("Elo 없음", r))
mm_ = {m[0]: m for m in M}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > 90 and not r[10] and not r[11]: problems.append(("90분 넘는 정규 시간 골", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const {PFX}_E={J(E)};\nconst {PFX}_M={J(M)};\nconst {PFX}_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "rsssf_date_check": RS_CHECK,
               "date_changes": DATE_LOG, "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()},
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분(추정 {NEST}경기) · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
