#!/usr/bin/env python3
"""Julián Álvarez: raw/ -> julianalvarez.json + src/data/jal.js (판정 근거는 judgments.md)

  python3 players/julianalvarez/build_julianalvarez.py [출력 data 폴더]
  (스크래치 복사본에서는 SOC_ROOT=<복사본> 으로 elo/·src/data 기준을 바꿀 수 있음)

입력: raw/tm_games.csv(출전·분), raw/tm_events.csv(리포트 골 목록), raw/tm_match_info.csv(다른 차전),
      raw/fotmob_events.csv·fotmob_playerMatches.csv(도움 대조), raw/ranks.txt(순위표; TM·FotMob 표가 같음을 확인),
      elo/opponent_elo_by_team_season.csv + aliases.csv, elo/league_world_mean.json(비유럽 리그 시즌 목표 평균·흩어짐),
      src/data/*.js(같은 경기 다른 선수 자료 값·동료 대조; git으로 관리되는 파일만).
리그 밖 순위(에콰도르 2020·페루 2020/2022·콜롬비아 2021 아페르투라·칠레 2022)는 영어 위키백과 시즌 문서로 확인한 값을 아래 표에 적음.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, math, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "src", "data")
OUT_JS = os.path.join(DATA_DIR, "jal.js")
OUT_JSON = os.path.join(HERE, "julianalvarez.json")
PID = "576024"

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------- 도움 판정
# Transfermarkt 도움 중 FotMob 경기 이벤트에 Álvarez 도움이 없는 것(유형으로 빼는 PK 유도·상대 자책골 제외): gameId|분 -> (넣음 여부, 근거)
SINGLE = {
    "3136570|73": (1, "2018.12.22 클럽 월드컵 3위 결정전 가시마 앤틀러스전 73분 곤살로 마르티네스 골: ESPN 경기 기록(Opta 문자중계 'Assisted by Julián Álvarez')·FourFourTwo 경기 기사(알바레스의 스루패스)"),
    "3176994|90+3": (0, "2019.5.7 리베르타도레스 인테르나시오나우전 90+3분 프라토 골: ESPN 기록은 도움자 없음(골키퍼 실책 뒤 골), FotMob 선수 경기 목록 도움 0, 현지 기사(La Página Millonaria)도 알바레스 도움으로 쓰지 않음"),
    "3329157|18": (1, "2020.9.17 리베르타도레스 상파울루전 18분 보레 골: ESPN 경기 기록('Assisted by Julián Álvarez')·El Colombiano 경기 기사(알바레스가 측면에서 올린 공을 보레가 마무리)·Los Andes/Diario de Cuyo 기사(알바레스의 돌파가 보레를 골문 앞에 둠)"),
    # FotMob 선수 경기 목록(playerMatches)에 도움이 있는 경기: TM + FotMob(선수 경기 목록) 일치로 넣음(테베스·호드리구·밤바 선례)
    "3316634|14": (1, "2021.2.10 코파 아르헨티나 데펜소레스 데 프로눈시아미엔토전 14분 마티아스 수아레스 골: FotMob 선수 경기 목록 도움 2(경기 이벤트에는 도움자 없음, FotMob 라인업 없음)"),
    "3316634|76": (1, "2021.2.10 코파 아르헨티나 데펜소레스 데 프로눈시아미엔토전 76분 히로티 골: FotMob 선수 경기 목록 도움 2"),
    "3473876|90": (1, "2020.11.24 리베르타도레스 16강 1차전 아틀레치쿠 파라나엔시전 90분 파울로 디아스 골(코너킥): FotMob 선수 경기 목록 도움 1"),
    "3563658|85": (1, "2021.5.25 리베르타도레스 플루미넨시전 85분 히로티 골: FotMob 선수 경기 목록 도움 1"),
    "3789760|65": (1, "2022.4.6 리베르타도레스 알리안사 리마전 65분 마티아스 수아레스 골: FotMob 선수 경기 목록 도움 1"),
    "3791167|89": (1, "2022.4.27 리베르타도레스 콜로콜로전 89분 바르코 골: FotMob 선수 경기 목록 도움 1"),
}
# 'Shot on goal'이지만 넣는 것(골키퍼 선방·골대 리바운드가 아님)
SHOT_KEEP = {"3535004|18": "2021.3.20 고도이 크루스전 18분 보레 골: ESPN 문자중계는 같은 19분 알바레스 슈팅 '빗나감' 기록 바로 뒤에 보레 골을 'Assisted by Julián Alvarez'로 적음(골키퍼 선방·골대 기록 없음), FotMob 경기 이벤트도 알바레스 도움"}

# ---------------------------------------------------------------- 대회 코드
LEAGUE_IDS = {"AR1N", "GB1", "ES1"}

def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE_IDS: return "lg"
    if cid == "CDLP": return "lg"                       # 코파 마라도나 2020·코파 데 라 리가 2021·2022 조별(1부 전 팀, 리그식) — 테베스 선례
    if cid == "CDCA":                                   # 결선: 2020 결선 조 = 리그, 8강 이후 = 국내컵 단계
        if r.startswith("group"): return "lg"
        if r.startswith("quarter"): return "dk"
        if r.startswith("semi"): return "dsf"
        if r.startswith("final"): return "df"
    if cid == "CLI":
        if r.startswith("quarter"): return "libk"
        if r.startswith("semi"): return "libsf"
        if r.startswith("final"): return "libf"
        return "lib"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16") or r.startswith("intermediate"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "KLUB": return "cwc"
    if cid in ("GBCS", "USC", "SCAG", "TDCS"): return "df"
    if cid == "SUC":
        return "dsf" if rnd.lower().startswith("semi") else "df"
    if cid in ("FAC", "CGB", "CDR", "ARCA", "ARLC"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        return "dc"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in LEAGUE_IDS or cid == "CDLP": return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 입력
games = [g for g in rd("tm_games.csv") if g["level"] == "senior"]
G = {g["gameId"]: g for g in games}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
PM = {r["matchId"]: r for r in rd("fotmob_playerMatches.csv")}

def ldate(g): return g["date_local"]
for g in games: g["opponent"] = g["opponent"].strip()

M = []
for g in sorted(games, key=lambda g: (ldate(g), g["gameId"])):
    M.append([ldate(g), g["opponent"], comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    if cid == "CL": return (1, 1) if d < "2021-07-01" else (0, 1)
    if cid == "CLI": return (1, 0) if d < "2022-01-01" else (0, 0)   # 2019~2021 원정 다득점·연장 없음, 2022부터 원정 다득점 폐지
    if cid == "CDR": return (0, 1)                 # 코파 델 레이 준결승: 원정 다득점 없음, 연장
    if cid == "ARLC": return (0, 0)                # 코파 데 라 수페르리가 2019(테베스 선례, 추정)
    sys.exit("합산 규칙 없음 " + cid)

def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["club_id"]: return "h"
    if m["away_id"] == g["club_id"]: return "a"
    sys.exit("편 판정 실패 " + gid)

def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    m = MI[gid]; s = side_of(gid)
    ag, et = tie_rule(g["competitionId"], ldate(g))
    leg = 1 if "1st" in rnd else 2
    if leg == 1: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    oh, oa = map(int, m["other_leg_score"].split(":"))      # 이 경기 홈:원정 기준으로 적힌 다른 차전 스코어
    ours, theirs = (oh, oa) if s == "h" else (oa, oh)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

def assist_reason(e):
    t = e["assist_type"]
    if e["scorer_id"] == PID: return "본인 골"
    if e["own_goal"] == "1": return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    return None

def fm_has_assist(gid, mi):
    for f in FME[gid]:
        if f["alvarez_assist"] == "1":
            t = int(f["time"]) + int(f["overloadTime"] or 0)
            if abs(t - mi) <= 2: return True
    return False

raw_rows, judg = [], []
for gid in sorted(EVS, key=lambda k: (ldate(G[k]) if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); prev = (0, 0)
    for e in EVS[gid]:
        h, a = map(int, e["score_home_away_after"].split("-"))
        before = prev; prev = (h, a)
        is_g = e["scorer_id"] == PID and e["own_goal"] != "1"
        is_a = e["assist_id"] == PID and e["scorer_id"] != PID
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        tag = f"{gid}|{e['minute']}"
        mi, dm = mins(e["minute"])
        d = ldate(g)
        if is_a:
            why = assist_reason(e)
            if why and tag in SHOT_KEEP:
                why = None; judg.append(("도움 넣음(Shot on goal)", d, g["opponent"], e["minute"], e["scorer"], SHOT_KEEP[tag]))
            if why:
                judg.append(("도움 제외", d, g["opponent"], e["minute"], e["scorer"], why))
            elif fm_has_assist(gid, mi):
                raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
            elif tag in SINGLE:
                ok, src = SINGLE[tag]
                kind = "FotMob 선수 경기 목록" if "선수 경기 목록 도움" in src and ok else ("단일 출처 도움 " + ("넣음" if ok else "뺌"))
                judg.append((kind, d, g["opponent"], e["minute"], e["scorer"], src))
                if ok: raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"]))
            else:
                sys.exit("FotMob에 없는 도움 판정 누락: " + tag + " " + d + " " + g["opponent"])
        if is_g:
            if e["side"] != ("home" if side == "h" else "away"): sys.exit("득점 편 이상 " + tag)
            pk = 1 if e["penalty"] == "1" else 0
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0))

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
        TABLE[(key(r["팀"]), r["시즌"])] = (int(r["Elo"]), r["수준 라벨(lv)"])

# 같은 경기 다른 선수 자료(git으로 관리되는 파일만 — 병행 판정자의 새 파일은 읽지 않음)
TRACKED = set(os.path.basename(x) for x in subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S)
    mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b not in TRACKED or b in ("hon.js", "jal.js"): continue
    try: P, oe, om = load_js(fn)
    except Exception: continue
    OTHERS[b] = (oe, om)
SAME = collections.defaultdict(collections.Counter)
for b, (oe, om) in OTHERS.items():
    for x in oe: SAME[(x[9], key(x[1]))][(x[2], x[12])] += 1

# 비유럽 리그 시즌 목표 평균·흩어짐(v1.217 도구 결과)과 같은 순위 곡선
WM = json.load(open(os.path.join(ELO, "league_world_mean.json"), encoding="utf-8"))
LC = [2.51, 1.668, 1.189, 0.842, 0.664, 0.555, 0.43, 0.259, 0.079, -0.096, -0.231, -0.321, -0.412, -0.502, -0.531, -0.649, -0.814, -0.999, -1.103, -1.177, -1.378]
def cv(r, n):
    n = max(n, 2); r = min(max(r, 1), n)
    x = (r - 1) / (n - 1) * 20; i = min(19, int(x)); t = x - i
    return LC[i] + (LC[i + 1] - LC[i]) * t
def wval(cc, y, r, n): return round(WM["평균"][f"{cc}|{y}"] + WM["흩어짐"][cc] * cv(r, n))

# 아르헨티나 1부 최종 순위(TM 표 = FotMob 표, raw/ranks.txt; 우승 팀 2018-19 라싱·2019-20 보카·2021 리버·2022 보카)
ARG = collections.defaultdict(dict)
for line in open(os.path.join(RAW, "ranks.txt"), encoding="utf-8"):
    p = line.rstrip("\n").split("|")
    if len(p) < 5 or p[0] != "AR1N": continue
    s = p[1].split(" ")[0]
    ARG[s][key(re.sub(r"\s*\(TM .*\)$", "", p[4]))] = (int(p[2]), int(p[3]))
ARG_N = {"2018-19": 26, "2019-20": 24, "2021": 26, "2022": 28}
ARG_Y = {"2018-19": 2019, "2019-20": 2020, "2021": 2021, "2022": 2022}
def arg_season(d):
    # 수페르리가 2018-19(2018.8~2019.5), 2019-20(2019.7~2020.3) + 코파 마라도나 2020(2020.10~2021.1, 테베스 선례: 직전 2019-20 최종 순위), 2021·2022는 달력 연도
    if d < "2019-07-01": return "2018-19"
    if d < "2021-02-01": return "2019-20"
    return d[:4]

# 다른 나라 1부(영어 위키백과 시즌 문서로 순위 확인): (팀, 연도) -> (나라, 라벨, 순위, 팀 수)
WORLD = {
    ("Sport Club Internacional", "2019"): ("BRA", "브라질 세리에 A 2019 7위", 7, 20),
    ("São Paulo Futebol Clube", "2020"): ("BRA", "브라질 세리에 A 2020 4위", 4, 20),
    ("Club Athletico Paranaense", "2020"): ("BRA", "브라질 세리에 A 2020 9위", 9, 20),
    ("Fluminense Football Club", "2021"): ("BRA", "브라질 세리에 A 2021 7위", 7, 20),
    ("LDU Quito", "2020"): ("ECU", "에콰도르 1부 2020 2위/16팀 (결승에서 바르셀로나에 승부차기 패, 준우승)", 2, 16),
    ("Deportivo Binacional", "2020"): ("PER", "페루 1부 2020 13위/20팀 (통합 순위)", 13, 20),
    ("Club Alianza Lima", "2022"): ("PER", "페루 1부 2022 1위/19팀 (우승 팀)", 1, 19),
    ("Junior FC", "2021"): ("COL", "콜롬비아 1부 2021 아페르투라 7위/19팀 (리그 수준 추정)", 7, 19),
    ("Independiente Santa Fe", "2021"): ("COL", "콜롬비아 1부 2021 아페르투라 2위/19팀 (리그 수준 추정)", 2, 19),
    ("CSD Colo-Colo", "2022"): ("CHI", "칠레 1부 2022 1위/16팀 (우승 팀)", 1, 16),
}
# 하부 리그(모두 추정): 아르헨티나 3부 = 같은 해 1부 목표 평균 − 357(알바라도 2018 페데랄 A 값과 그해 1부 평균의 차), 4부 = 3부 − 53(브라질 3부 1253·4부 이하 1200 차)
def arg3(y): return round(WM["평균"][f"ARG|{y}"] - 357)
MAN = {
    ("Club Defensores de Pronunciamiento", "2021"): (arg3(2021), "아르헨티나 3부(토르네오 페데랄 A) 2021 (추정, 다른 선수 자료 페데랄 A 상대와 같은 1부 대비 차이)"),
    ("CSC Deportivo Laferrere", "2022"): (arg3(2022) - 53, "아르헨티나 4부(프리메라 C) 2022 (추정, 3부 추정값에서 브라질 3부·4부 이하 차이만큼 낮춤)"),
    ("UE Vic", "2024-25"): (1100, "스페인 6부(리가 엘리트 카탈루냐) 2024-25 (추정, 다른 선수 자료 스페인 5부·프랑스 6부 1100과 같음)"),
    ("CP Cacereño", "2024-25"): (1150, "스페인 4부(세군다 페데라시온) 2024-25 5조 2위/18팀 (추정, 다른 선수 자료 스페인 4부 1150과 같음)"),
}

def eu(d):
    y, mo = int(d[:4]), int(d[5:7]); s = y if mo >= 7 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

ARG_COMPS = {"AR1N", "CDLP", "CDCA", "ARCA", "ARLC", "SCAG", "TDCS"}
ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []
def opp_elo(opp, d, cid):
    k = key(opp)
    same = SAME.get((d, k))
    if same:
        (e, lv), _ = same.most_common(1)[0]
        ELO_SRC["같은 경기 다른 선수 자료"] += 1; ELO_LOG[(opp, d)] = ("same", e, lv); return e, lv
    if cid in ARG_COMPS:
        s = arg_season(d)
    elif cid == "CLI":
        s = d[:4]
    elif cid == "KLUB":                                 # 남미·일본 상대는 달력 연도, 유럽 상대는 시즌
        s = d[:4] if opp in ("Kashima Antlers", "Fluminense Football Club") else eu(d)
    else:
        s = eu(d)
    if (k, s) in TABLE:
        e, lv = TABLE[(k, s)]; ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(opp, s)] = ("table", e, lv); return e, lv
    if (opp, s) in MAN:
        e, lv = MAN[(opp, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(opp, s)] = ("man", e, lv); return e, lv
    if (opp, s) in WORLD:
        cc, lv, r, n = WORLD[(opp, s)]
        e = wval(cc, int(s), r, n); ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(opp, s)] = ("model", e, lv); return e, lv
    if cid in ARG_COMPS and k in ARG.get(s, {}):
        r, n = ARG[s][k]
        if n != ARG_N[s]: sys.exit("팀 수 이상 " + s)
        e = wval("ARG", ARG_Y[s], r, n); lv = f"아르헨티나 1부 {s} {r}위/{n}팀"
        ELO_SRC["순위표+리그 모형"] += 1; ELO_LOG[(opp, s)] = ("model", e, lv); return e, lv
    MISS.append((opp, d, cid, s)); return 0, "?"

E = []
for typ, gid, mi, dm, gf, ga, pk, note in raw_rows:
    g = G[gid]; d = ldate(g); cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(g["opponent"], d, cid)
    et = 1 if (g["gameState"] == "extra_time" and mi > 90 and ko) else 0
    row = [typ, g["opponent"], elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, r[0]))

# 한 팀·한 시즌 한 값(내 자료 안)
chk = collections.defaultdict(set)
for (o, s), v in ELO_LOG.items():
    if v[0] != "same": chk[(key(o), s)].add(v[1])
for k_, v in chk.items():
    if len(v) > 1: sys.exit(f"같은 팀-시즌 값 여럿 {k_} {v}")

# ---------------------------------------------------------------- 동료·같은 경기 대조(보고용)
MATE_NAME = {"haa.js": "Erling Haaland", "fod.js": "Phil Foden", "kdb.js": "Kevin De Bruyne", "mah.js": "Riyad Mahrez",
             "bsi.js": "Bernardo Silva", "grz.js": "Antoine Griezmann", "loo.js": "Ademola Lookman"}
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and re.search(r"Juli[aá]n [ÁA]lvarez", str(x[13])):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (x[5], x[6], x[2], x[12], x[3])
            cross.append(("동료 도움→알바레스 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "알바레스 골 없음"), x[2:7], hit[0][2:7] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and r[13] == nm:
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3]) == (r[5], r[6], r[2], r[12], r[3])
                cross.append(("알바레스 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else "동료 골 없음"), r[2:7], hit[0][2:7] if hit else None))
    for r in E:
        for x in oe:
            if x[9] == r[9] and key(x[1]) == key(r[1]) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[3], x[12]), (r[2], r[3], r[12])))
for gid, evs in EVS.items():
    if gid not in G: continue
    for e in evs:
        if e["scorer_id"] == PID and e["assist_id"] and not e["assist_type"].startswith("Penalty"):
            for b, nm in MATE_NAME.items():
                if e["assist_player"] == nm:
                    d = ldate(G[gid]); oe, om = OTHERS[b]
                    if not any(x[0] == "a" and x[9] == d and re.search(r"lvarez", str(x[13])) for x in oe):
                        cross.append(("TM 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"], "출전 행 있음" if any(m[0] == d for m in om) else "출전 행 없음"))
DUP = set(); cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 합계
CLUBS = [("2022-07-07", "리버 플레이트"), ("2024-08-12", "맨체스터 시티"), ("9999-12-31", "아틀레티코 마드리드")]
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for _, n in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
TM_A_API = sum(int(g["assists"]) for g in games)
SHOTR = "슈팅 리바운드('Shot on goal')"
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
def jl(reason): return ", ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
SKIP = [j for j in judg if j[0] == "단일 출처 도움 뺌"]
ADDS = [j for j in judg if j[0] == "단일 출처 도움 넣음"]
PMS = [j for j in judg if j[0] == "FotMob 선수 경기 목록"]
MAN_USED = sorted({(o, s) for (o, s), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: (t[1], t[0]))
first, last = M[0], M[-1]
ET120 = [m for m in M if m[3] > 90]

NOTE_LINES = [
    f"훌리안 알바레스(리버 플레이트·맨체스터 시티·아틀레티코 마드리드)의 클럽 공식 경기 {NG}경기({d_(first[0])} 알도시비전 ~ {d_(last[0])} 바르셀로나전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기 제외",
    f"클럽별 경기·골·도움: 리버 플레이트 {c3(ST['리버 플레이트'])}, 맨체스터 시티 {c3(ST['맨체스터 시티'])}, 아틀레티코 마드리드 {c3(ST['아틀레티코 마드리드'])}. 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적(90분 추정 없음), 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(전 경기 저장), FotMob 경기 기록(전 경기)과 대조. 경기 수·골 수는 영어·스페인어 위키백과 클럽 합계와 같음(343경기 141골; 스페인어 위키백과 시즌 도움 합계도 Transfermarkt와 같음). 영어 위키백과의 리버 2018-19 시즌 줄(5골)은 자체 합계 줄(54골)과 맞지 않는 표기 오류",
    "리버 플레이트 2군(리저브 리그) 6경기 2골과 U-20 경기, 아르헨티나 대표팀(A·올림픽·U-20) 경기는 뺌. 2022.1.31 맨체스터 시티로 이적한 뒤 2022.7.6까지 리버에 임대로 남은 기간은 리버 경기로 셈",
    "골: 141골 모두 Transfermarkt와 FotMob이 같은 경기·같은 순서(분은 1~3분 차이가 있는 곳이 있어 Transfermarkt를 씀, 2021.12.18 콜론전 54분 골은 FotMob 57분). 알바레스 자책골 없음. PK 골은 두 출처가 같음",
    "도움은 Transfermarkt와 FotMob(경기 이벤트, 이벤트에 도움자가 비어 있으면 선수 경기 목록)이 같이 적은 것을 기준으로 하고, 한쪽에만 있는 것은 다른 출처 2곳이 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 도움 {TM_A_API}개 − PK 유도 {EX['PK 유도']}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 − 확인 못 한 단일 출처 {len(SKIP)}개",
    "PK 유도로 뺀 도움: " + jl("PK 유도"),
    "상대 자책골에 붙은 도움으로 뺀 것: " + jl("상대 자책골 유도") + "(Transfermarkt 유형 'Shot on goal', FotMob은 도움 없음)",
    "Transfermarkt 리포트가 2024.5.11 풀럼전 90+6분 알바레스 PK 골에 본인을 도움으로 적은 것은 도움으로 세지 않음(Transfermarkt 선수 경기 성적도 0)",
    "Transfermarkt 유형이 'Shot on goal'이지만 넣은 도움: 2021.3.20 고도이 크루스전 18분 보레 골(ESPN 문자중계상 빗나가던 알바레스의 슈팅을 보레가 밀어 넣은 골로 골키퍼 선방·골대 리바운드가 아니고, ESPN·FotMob 모두 알바레스 도움)",
    "FotMob 경기 이벤트에는 도움자가 없지만 FotMob 선수 경기 목록에 도움이 있어 넣은 것: " + "; ".join(f"{d_(j[1])} {j[2]}전 {j[3]}분 {j[4]}" for j in PMS),
    "다른 출처 2곳으로 확인해 넣은 단일 출처 도움: " + "; ".join(j[5] for j in ADDS),
    "확인하지 못해 뺀 단일 출처 도움: " + "; ".join(j[5] for j in SKIP),
    "출전 분은 Transfermarkt 그대로(FotMob과 1분 차이 26경기, 2019.10.18 아르세날 데 사란디전 Transfermarkt 79분·FotMob 90분). 코파 아르헨티나 4경기는 FotMob 라인업이 없어 Transfermarkt만 근거",
    "날짜는 경기 현지 날짜. 리버 경기는 경기 시각(UTC)을 아르헨티나 시간(UTC−3)으로 바꿔 Transfermarkt 리포트 날짜(중부 유럽 기준)보다 하루 앞인 경우가 89경기(원정 리베르타도레스 경기도 현지 시간대로 바꿔도 날짜가 같음). 클럽 월드컵 2018(아랍에미리트)·2023(사우디아라비아)은 리포트 날짜, 2025(미국)는 경기장 현지 시간(로즈볼·루멘 필드 모두 태평양 시간): 2025.6.19 시애틀전은 현지 6.19(Transfermarkt 리포트 6.20)",
    "상대 Elo는 같은 경기를 다룬 다른 선수 자료(그리즈만·홀란드·포든·데 브라위너·마레즈·베르나르두 실바·루크먼 등)의 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 리그 모형에 넣은 값, 직접 추정 순으로 씀",
    "아르헨티나 상대: 수페르리가 2018-19(26팀)·2019-20(24팀)과 2021(26팀)·2022(28팀) 리그 최종 순위(Transfermarkt·FotMob 표가 같음)를 리그 수준 모형에 넣음. 코파 마라도나 2020과 코파 아르헨티나 2019 결승·코파 데 라 수페르리가 2019는 진행 중이던 수페르리가 시즌 순위, 2021·2022 코파 데 라 리가·수페르코파 아르헨티나(2021.3)·트로페오 데 캄페오네스는 같은 해 리그 최종 순위(한 팀·한 해 한 값; 다른 선수 자료가 2021 코파 데 라 리가 조 순위로 넣은 투쿠만 2021 값은 그대로 씀)",
    "다른 나라 상대: 브라질 세리에 A·에콰도르·페루·콜롬비아·칠레 1부는 그 시즌 순위(영어 위키백과·Transfermarkt·FotMob 표)를 비유럽 리그 수준 모형에 넣음(에콰도르 2020 리가 데 키토는 결승 준우승 2위, 페루 2020 비나시오날은 통합 순위 13위, 2022 알리안사 리마·칠레 2022 콜로콜로는 우승 팀, 콜롬비아 2021은 리베르타도레스 경기가 열린 아페르투라 정규 단계 순위). 가시마 2018·플루미넨시 2023·보타포구 2025(클럽 월드컵)는 다른 선수 자료 값",
    "리그 표 밖 상대는 추정(모두 '추정'): " + ", ".join(f"{o} {s} {ELO_LOG[(o, s)][1]}" for o, s in MAN_USED) + ". 데펜소레스 데 프로눈시아미엔토(3부 페데랄 A)는 다른 선수 자료의 페데랄 A 상대(알바라도 2018)와 그해 1부 평균 차이를 그대로 적용, 라페레레(4부 프리메라 C)는 3부보다 한 단계 낮춤, UE 빅(카탈루냐 지역 6부)과 카세레뇨(4부)는 다른 선수 자료의 스페인 하부 리그 평탄값",
    "대회 비중: 코파 마라도나 2020·코파 데 라 리가 2021·2022의 조별 단계(1부 전 팀, 리그식)와 2020 결선 조는 리그, 8강 이후는 국내컵 단계(테베스 선례). 코파 아르헨티나·코파 데 라 수페르리가 2019·FA컵·리그컵·코파 델 레이는 국내컵(16강까지 낮은 비중, 8강부터 높은 비중·준결승·결승). 수페르코파 아르헨티나·트로페오 데 캄페오네스·커뮤니티 실드·UEFA 슈퍼컵은 국내컵 결승 비중, 수페르코파 데 에스파냐 준결승은 국내컵 준결승. 클럽 월드컵 2025 조별은 리그식(무승부 1점). 챔스 2024-25부터 리그 단계는 조별과 같은 비중, 녹아웃 플레이오프는 16강과 같은 비중",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 챔스(2022-23 이후)와 코파 델 레이 준결승은 원정 다득점 없이 연장, 리베르타도레스 2019~2021은 원정 다득점 있고 연장 없이 승부차기, 2022는 원정 다득점·연장 없음, 코파 데 라 수페르리가 2019는 원정 다득점·연장 없음(추정). 다른 차전 스코어는 Transfermarkt 리포트",
    "연장 경기의 출전 분은 Transfermarkt 그대로(120분 출전: " + ", ".join(f"{d_(m[0])} {m[1]} {m[3]}분" for m in ET120) + "). 연장 시간의 골·도움은 없음",
    "시즌 구분: 리버 플레이트는 달력 연도(테베스·이과인·팔카오의 아르헨티나 클럽 선례; 2018-19·2019-20 수페르리가도 연도로 나뉨), 맨체스터 시티는 7월 10일 기준(2022.7.30 커뮤니티 실드는 2022-23), 아틀레티코 마드리드는 8월 1일 기준(2025.6 클럽 월드컵은 2024-25). 클럽 구분 2022.7.7 맨체스터 시티, 2024.8.12 아틀레티코 마드리드",
    "우승·수상 기록은 Transfermarkt 업적 페이지 기준. 2018 코파 리베르타도레스는 결승 2차전 교체 출전(23분), 레코파 수다메리카나 2019는 두 경기 모두 결장, 2024 커뮤니티 실드는 이적 직전 결장(Transfermarkt 우승 목록 그대로). 남미 올해의 선수 2021·대표팀 기록은 표 항목이 없어 뺌. 프리미어리그·라리가 선수협회·사무국 올해의 팀은 확인되는 기록 없음",
    f"{d_('2026-11-18')} 기준: 마지막 출전은 {d_(last[0])} 라리가 바르셀로나전(90분, 1도움). 그 뒤 아르헨티나 대표팀 경기만 있음",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "csa", "lib", "mlp", "cwc", "clg", "cl16"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []; seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6], r[13])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mdates = collections.Counter(m[0] for m in M)
for d, rs in by.items():
    gl = sorted([r for r in rs if r[0] == "g"], key=lambda r: (r[5] + r[6], r[4]))
    for a, b in zip(gl, gl[1:]):
        if b[5] < a[5] + 1 or b[6] < a[6]: problems.append(("스코어 역순", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if MISS:
    for x in MISS: print("상대 Elo 없음:", x)
    sys.exit(1)
open(OUT_JS, "w", encoding="utf-8").write(f"const JAL_E={J(E)};\nconst JAL_M={J(M)};\nconst JAL_NOTE={J(NOTE)};\n")
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg, "cross_check": cross,
           "elo_sources": ELO_SRC, "elo_log": {f"{o}|{s}": v for (o, s), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if not (c[0].startswith(("동료", "알바레스")) and c[4] == "일치"): print("  대조:", c)
print("일치 대조", sum(1 for c in cross if len(c) > 4 and c[4] == "일치"))
if "--debug" in sys.argv:
    for k_, v in sorted(ELO_LOG.items(), key=lambda t: str(t[0][1])): print("  elo", k_, v)
