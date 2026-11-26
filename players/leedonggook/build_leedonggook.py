#!/usr/bin/env python3
"""이동국 (李同國, Lee Dong-gook, Transfermarkt 688): raw/ -> leedonggook.json + players/leedonggook/ldg.js (판정 근거는 judgments.md)

  python3 players/leedonggook/build_leedonggook.py [--out <data 폴더>]   # 파일 쓰기(기본 players/leedonggook/ldg.js)
  python3 players/leedonggook/build_leedonggook.py --debug               # Elo 출처 로그
  python3 players/leedonggook/build_leedonggook.py --stat                # 요약·판정·동료 대조

이재성 build 스크립트(build_leejaesung.py)를 바탕으로 함. 출처:
  TM  = Transfermarkt tmapi performance-game(경기·출전 분) + game/<id> JSON(골·도움·시각·PK) (raw/tm_*.csv)
  KL  = K리그 데이터 포털 공식 경기 기록(portal.kleague.com, raw/kleague/): 1998~2020 K리그·리그컵·챔피언십 모든 경기의 선발·교체 시각·득점·도움·PK
  FM  = FotMob 경기 기록(2010.7 이후)
순위 라벨이 있는 행의 Elo는 tools/league_rank_apply.py 의 parse()/value()(+ league_points)로 라벨에서 계산.
같은 경기가 다른 선수 자료에 있으면 그 값, 같은 팀×시즌이 elo/opponent_elo_by_team_season.csv에 있으면 그 값.
스크래치 복사본에서는 SOC_ROOT=<복사본>.
"""
import csv, json, os, re, sys, unicodedata, collections, glob, subprocess, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
ROOT = os.environ.get("SOC_ROOT") or os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
OUT_DIR = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
OUT_JS = os.path.join(OUT_DIR, "ldg.js")
OUT_JSON = os.path.join(HERE, "leedonggook.json")
ME = "688"
ME_KO = "이동국"
GAP = "2014-08-01"   # 이 전 도움은 단일 출처 허용(정상 유형)

def rd(n):
    with open(os.path.join(RAW, n), encoding="utf-8") as f:
        return list(csv.DictReader(f))

GAMES = rd("tm_games.csv")                       # TM 클럽 공식 경기 688
G = {g["gameId"]: g for g in GAMES}
MI = {r["gameId"]: r for r in rd("tm_match_info.csv")}
EVS = collections.defaultdict(list)
for e in rd("tm_events.csv"): EVS[e["gameId"]].append(e)
MERGED = rd("ldg_games_merged.csv")
PORTAL_OF = {r["tm_gameId"]: r["portal_id"] for r in MERGED if r["portal_id"] and r["tm_gameId"] != "NOT IN TM"}
PM = {f'{r["year"]}_{r["meetSeq"]}_{r["gameId"]}': r for r in rd("kleague/portal_matches.csv")}
PG = collections.defaultdict(list)
for r in rd("kleague/portal_goals.csv"): PG[f'{r["year"]}_{r["meetSeq"]}_{r["gameId"]}'].append(r)
FME = collections.defaultdict(list)
for r in rd("fotmob_events.csv"): FME[r["tm_gameId"]].append(r)
TWO = {r["gameId"]: r for r in rd("tm_two_leg_ties.csv")}

KCOMP = {"RSK1", "RSKM", "KLS1", "KLS2", "KREL", "KLCP"}   # K리그 포털 공식 기록이 있는 대회

# ---------------------------------------------------------------- 상대 이름(그 시즌 이름, 영어)
def opp_name(oid, name, year):
    y = int(year)
    if oid == "3610": return "Cheonan Ilhwa Chunma" if y <= 1999 else ("Seongnam Ilhwa Chunma" if y <= 2013 else "Seongnam FC")
    if oid == "19684": return "Bucheon SK" if y <= 2005 else "Jeju United"
    if oid == "6502": return "Jeonbuk Hyundai Dinos" if y <= 1999 else "Jeonbuk Hyundai Motors"
    if oid == "3535": return "Ulsan Hyundai"
    if oid == "6500": return "Anyang LG Cheetahs" if y <= 2003 else "FC Seoul"
    if oid == "6499": return "Daejeon Citizen"
    if oid == "2582": return "Busan Daewoo Royals" if y <= 1999 else ("Busan I'Cons" if y <= 2004 else "Busan IPark")
    if oid == "6505": return "Gwangju Sangmu" if y <= 2010 else "Sangju Sangmu"
    if oid == "10948": return "Guangzhou Evergrande"
    if oid == "3182": return "Shandong Luneng Taishan"
    if oid == "3187": return "Tianjin Teda"
    if oid == "33714": return "Tianjin Quanjian"
    if oid == "22219": return "Jiangsu Suning"
    if oid == "27190": return "Shanghai SIPG"
    if oid == "10756": return "Becamex Binh Duong FC"
    if oid == "34970": return "Gangneung City"
    if oid == "76180": return "Asan Mugunghwa"
    if oid == "30028": return "Ulsan Hyundai Mipo Dolphin"
    return re.sub(r"\s*\(\s*-?\s*\d{4}\s*-?\s*\d{0,4}\)", "", name).strip()
def opp(g): return opp_name(g["opponentId"], g["opponent"], g["date_local"][:4])

# ---------------------------------------------------------------- 대회 코드
LEAGUE = {"RSK1", "RSKM", "KLS1", "KLS2", "L1", "GB1"}
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return "lg"
    if cid == "KREL":   # K리그 챔피언십(플레이오프) = MLS 플레이오프·리길야 선례: 6강·준PO mlp, PO(준결승) mlpsf, 챔피언결정전 mlpf
        if r.startswith("final"): return "mlpf"
        if r.startswith("semi"): return "mlpsf"
        return "mlp"
    if cid in ("KLCP", "RKPO", "FAC", "CGB", "DLC"):   # 리그컵·FA컵·잉글랜드 FA컵·리그컵: 16강까지 dc, 8강 dk, 준결승 dsf, 결승 df
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter") or r.startswith("sixth"): return "dk"
        return "dc"
    if cid == "AFCL":
        if r.startswith("quarter"): return "aclk"
        if r.startswith("semi"): return "aclsf"
        if r.startswith("final"): return "aclf"
        return "acl"
    if cid == "ACCS": return "aclsf"   # 아시안 클럽 챔피언십 1997-98 결승 라운드 준결승(AFC 챔스 전신)
    if cid == "AACC": return "cwc"     # 아프로-아시안 클럽 챔피언십 1998(아시아·아프리카 클럽 챔피언 대결, 대륙 간 클럽 경기)
    if cid == "KLUB": return "cwc"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if cid in LEAGUE: return 0
    if r.startswith("group") or "matchday" in r or re.match(r"^\d+$", r) or r == "": return 0
    return 1

# ---------------------------------------------------------------- 두 경기 합산
def tie_rule(cid, d):
    if cid == "AFCL": return (1, 1)   # AFC 2022 시즌까지 원정 다득점(연장 포함)
    if cid == "KREL": return (0, 1)   # 2009 챔피언결정전: 원정 다득점 없음, 동률이면 연장(엑스포츠뉴스 1차전 기사)
    sys.exit("합산 규칙 없음 " + cid)
def side_of(gid):
    g, m = G[gid], MI[gid]
    if m["home_id"] == g["clubId"]: return "h"
    if m["away_id"] == g["clubId"]: return "a"
    sys.exit("편 판정 실패 " + gid)
def tie_of(gid):
    g = G[gid]; rnd = g["round"].lower()
    if "leg" not in rnd: return None
    s = side_of(gid); ag, et = tie_rule(g["competitionId"], g["date_local"])
    if "1st" in rnd: return [1, 1 if s == "h" else 0, 0, 0, ag, et]
    t = TWO[gid]; a, b = map(int, t["other_leg_score"].split("-"))
    # 1차전 스코어(홈-원정): 우리가 2차전 홈이면 1차전은 원정
    ours, theirs = (b, a) if s == "h" else (a, b)
    return [2, 1 if s == "h" else 0, ours, theirs, ag, et]

# ---------------------------------------------------------------- 출전(M)
M = []
for g in sorted(GAMES, key=lambda g: (g["date_local"], g["gameId"])):
    M.append([g["date_local"], opp(g), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])])
# K리그 공식 기록에만 있는 리그컵(대한화재컵) 2경기: 공식 경기 기록 선발·교체 시각, 위키백과 시즌 출전 수에도 포함
PORTAL_ONLY_GAMES = [["1999-04-21", "Bucheon SK", "dc", 58], ["2000-03-19", "Anyang LG Cheetahs", "dc", 90]]
M += PORTAL_ONLY_GAMES
M.sort(key=lambda m: m[0])

# ---------------------------------------------------------------- 골·도움
def mins(s):
    s = s.strip()
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0
def is_og(e): return e["own_goal"] == "1"

def portal_lee(gid, kind):
    """K리그 공식 기록의 이동국 득점(kind='g')/도움('a') [(분, pk, 득점자, 설명)] (공식 기록이 없으면 None)"""
    pid = PORTAL_OF.get(gid)
    if not pid or pid not in PG and pid not in PM: return None
    out = []
    for r in PG.get(pid, []):
        if kind == "g" and r["ldg_scorer"] == "1": out.append((int(r["abs_min"]), int(r["pk"]), r["scorer"], r["desc"]))
        if kind == "a" and r["ldg_assist"] == "1": out.append((int(r["abs_min"]), int(r["pk"]), r["scorer"], r["desc"]))
    return out

A_CHECK = {   # 2014.8 이후 단일 출처 도움 확인 (gameId|분) -> (넣음?, 근거)
    "3141468|71": (True, "TM 'Cross' + 신화통신(China Daily 게재 'Lee set up substitute Kim Shin-Wook to steer his header') + 골닷컴 코리아('왼발 크로스로 김신욱의 헤딩 쐐기골까지 도우며 1골 1도움')"),
}
# K리그 공식 기록에만 있는 도움(TM 도움 없음). 2014.8 이후는 다른 출처 2곳이 필요: 확인 못 해 뺌(아래 판정)
PORTAL_A_CHECK = {
    "2485803|35": (False, "공식 기록 + 기사 인용 1곳(팬 카페 게재 '1골 1도움')뿐 — 독립 출처 2곳 확인 못 함"),
    "2548081|71": (False, "공식 기록만(TM·FotMob 도움 없음, 기사 확인 못 함)"),
    "2561713|68": (False, "공식 기록만(TM·FotMob 도움 없음, 기사 확인 못 함)"),
    "2580058|73": (False, "공식 기록만(TM·FotMob 도움 없음, 기사 확인 못 함)"),
}
PK_FIX = {("2609285", "28"): (1, "2015.8.30 성남전 28분: TM 일반 골, K리그 공식 기록 'PK-R-G'·FotMob 'Penalty' → PK 골")}
MIN_FIX = {("1188627", "65"): ("63", "2012.4.8 경남전: TM 65분, K리그 공식 기록 후반 17분(62분대)·FotMob 63분 → 63분")}

judg, raw_rows, A_STATUS = [], [], []
def assist_reason(e, d, gid):
    t = e["assist_type"]
    if is_og(e): return "상대 자책골 유도"
    if t.startswith("Penalty"): return "PK 유도"
    if t == "Shot on goal": return "슈팅 리바운드('Shot on goal')"
    if t.startswith("Deflect"): return "굴절"
    k = f'{gid}|{e["minute"]}'
    pl = portal_lee(gid, "a") if G[gid]["competitionId"] in KCOMP else None
    if pl is not None:
        if any(abs(m - mins(e["minute"])[0]) <= 3 for m, _, _, _ in pl):
            A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM+K리그 공식 기록")); return None
        return "K리그 공식 기록에 이 골 도움자 없음(TM 단독, 공식 기록과 어긋남)"
    if d < GAP:
        A_STATUS.append((d, gid, e["minute"], e["scorer"], "TM 단독(2014.8 전, 정상 유형)")); return None
    if k in A_CHECK:
        ok, why = A_CHECK[k]; A_STATUS.append((d, gid, e["minute"], e["scorer"], ("넣음: " if ok else "뺌: ") + why))
        return None if ok else "2014.8 이후 단일 출처(확인 못 함)"
    A_STATUS.append((d, gid, e["minute"], e["scorer"], "판정 없음")); return "2014.8 이후 단일 출처(판정 없음)"

SCORE_MISMATCH = []
for gid in sorted(EVS, key=lambda k: (G[k]["date_local"] if k in G else "", k)):
    if gid not in G: continue
    g = G[gid]; side = side_of(gid); cnt = {"h": 0, "a": 0}; d = g["date_local"]
    tm_a_mins = []
    for e in EVS[gid]:
        sd = e["side"][0]; before = (cnt["h"], cnt["a"]); cnt[sd] += 1
        is_g = e["scorer_id"] == ME and not is_og(e)
        is_a = e["assist_id"] == ME and e["scorer_id"] != ME
        if e["scorer_id"] == ME and e["assist_id"] == ME:
            judg.append(("도움 아님(본인 PK 골의 본인 도움 표기)", d, opp(g), e["minute"], e["assist_type"]))
        if e["scorer_id"] == ME and is_og(e): sys.exit("자책골 " + gid)
        if not (is_g or is_a): continue
        gf, ga = (before[0], before[1]) if side == "h" else (before[1], before[0])
        mstr = e["minute"]
        if (gid, mstr) in MIN_FIX:
            judg.append(("시각 수정", d, opp(g), mstr, MIN_FIX[(gid, mstr)][1])); mstr = MIN_FIX[(gid, mstr)][0]
        mi, dm = mins(mstr)
        if is_a:
            tm_a_mins.append(mins(e["minute"])[0])
            why = assist_reason(e, d, gid)
            if why:
                judg.append(("도움 제외", d, opp(g), e["minute"], e["scorer"], why)); continue
            raw_rows.append(("a", gid, mi, dm, gf, ga, 0, e["scorer"], e["assist_type"]))
        if is_g:
            if sd != side: sys.exit("득점 편 이상 " + gid)
            pk = 1 if e["goal_desc"] == "Penalty" else 0
            if (gid, e["minute"]) in PK_FIX:
                pk = PK_FIX[(gid, e["minute"])][0]; judg.append(("PK 수정", d, opp(g), e["minute"], PK_FIX[(gid, e["minute"])][1]))
            raw_rows.append(("g", gid, mi, dm, gf, ga, pk, 0, e["goal_desc"]))
    # K리그 공식 기록에만 있는 도움
    if g["competitionId"] in KCOMP:
        pl = portal_lee(gid, "a") or []
        pid = PORTAL_OF[gid]
        for m, _, scorer, desc in pl:
            if any(abs(m - x) <= 3 for x in tm_a_mins): continue
            k = f"{gid}|{m}"
            if d >= GAP and False:   # v1.295 사용자 결정: K리그 공식 기록 단독 도움은 날짜와 관계없이 넣음
                ok, why = PORTAL_A_CHECK.get(k, (False, "판정 없음"))
                A_STATUS.append((d, gid, str(m), scorer, ("넣음: " if ok else "뺌: ") + why + " [공식 기록 단독]"))
                if not ok:
                    judg.append(("도움 제외(공식 기록 단독, 2014.8 이후)", d, opp(g), str(m), scorer, why, desc)); continue
            # 골 전 스코어: 공식 기록 득점 순서(자책골은 이득 팀 칸)
            ph = PM[pid]["home"]; seq = sorted(PG[pid], key=lambda r: int(r["abs_min"]))
            hh = aa = 0; found = None
            for r in seq:
                if r["ldg_assist"] == "1" and int(r["abs_min"]) == m and r["scorer"] == scorer:
                    found = (hh, aa); break
                if ph.startswith(r["team"]) or r["team"] in ph: hh += 1
                else: aa += 1
            if found is None: sys.exit("공식 기록 순서 " + k)
            gf, ga = found if side == "h" else (found[1], found[0])
            mm_ = 1 if m == 0 else m
            dm = f"90+{mm_ - 90}" if mm_ > 90 and g["gameState"] == "regularly_terminated" else 0
            A_STATUS.append((d, gid, str(m), scorer, "공식 기록 단독 넣음"))
            judg.append(("도움 추가(K리그 공식 기록 단독)", d, opp(g), str(m), scorer, desc))
            raw_rows.append(("a", gid, mm_, dm, gf, ga, 0, scorer, "portal"))
    h = cnt["h"]; a = cnt["a"]
    fh, fa = map(int, MI[gid]["final"].split("-")) if MI[gid]["final"] else (h, a)
    if (h, a) != (fh, fa) and g["gameState"] != "penalty_shootout": SCORE_MISMATCH.append((gid, d, (h, a), (fh, fa)))

# 득점자 이름: 공식 기록 한국어 → 다른 행과 같은 영어 표기
KO_EN = {"이승현": "Seung-hyun Lee", "에닝요": "Eninho", "드로겟": "Hugo Droguett", "서상민": "Sang-min Seo", "이재성": "Jae-sung Lee",
         "한교원": "Kyo-won Han", "카이오": "Kaio", "이승기": "Seung-gi Lee", "에두": "Edú", "레오나르도": "Leonardo"}
raw_rows = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], KO_EN.get(r[7], r[7]), r[8]) if r[8] == "portal" else r for r in raw_rows]
for r in raw_rows:
    if r[8] == "portal" and re.search(r"[가-힣]", r[7]): sys.exit("영어 이름 없음 " + r[7])

# 추가시간 표기: TM이 45·90분으로만 적은 골·도움을 공식 기록 전·후반 추가시간(예: 후반 47분 → 90+2)으로
ADDED_FIX = []
def _addfix(rows):
    out = []
    for r in rows:
        g = G[r[1]]
        if g["competitionId"] in KCOMP and r[8] != "portal" and not r[3] and r[2] in (45, 90):
            pl = portal_lee(r[1], r[0]) or []
            cand = [m for m, *_ in pl if (r[2] == 90 and 90 < m <= 100) or (r[2] == 45 and 45 < m <= 52)]
            if len(cand) == 1 and not any(m == r[2] for m, *_ in pl):
                m = cand[0]; base = r[2]; dm = f"{base}+{m - base}"
                ADDED_FIX.append((g["date_local"], r[0], r[2], dm)); r = (r[0], r[1], m, dm) + tuple(r[4:])
        out.append(r)
    return out
raw_rows = _addfix(raw_rows)

# 대조: TM 골 수 = 경기 골 수, PK 수
cnt_ = collections.Counter((r[1], r[0]) for r in raw_rows)
for gid, g in G.items():
    if cnt_[(gid, "g")] != int(g["goals"] or 0): sys.exit("골 수 불일치 " + gid)
# 대조: K리그 공식 기록 골(경기별 수·시각·PK)
KL_G_DIFF = []
for gid, g in G.items():
    if g["competitionId"] not in KCOMP: continue
    pg = portal_lee(gid, "g")
    if pg is None: KL_G_DIFF.append(("공식 기록 없음", gid, g["date_local"])); continue
    tg = sorted([r for r in raw_rows if r[1] == gid and r[0] == "g"], key=lambda r: r[2])
    pg = sorted(pg)
    if len(tg) != len(pg): KL_G_DIFF.append(("골 수", gid, g["date_local"], len(tg), len(pg))); continue
    for t, p in zip(tg, pg):
        if abs(t[2] - p[0]) > 2 or t[6] != p[1]: KL_G_DIFF.append(("골", gid, g["date_local"], t[2], t[6], p[0], p[1]))
PK_TM = sum(int(g["penGoals"] or 0) for g in GAMES)

# ---------------------------------------------------------------- 이름·기존 자료
def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n); n = re.sub(r"[^a-z0-9 ]", " ", n)
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

TRACKED = set(subprocess.run(["git", "-C", ROOT, "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
if not TRACKED:
    TRACKED = set(subprocess.run(["git", "-C", "/home/user/soc", "ls-files", "src/data"], capture_output=True, text=True).stdout.split())
def load_js(fn):
    s = open(fn, encoding="utf-8").read()
    m = re.search(r"const (\w+)_E=(\[.*?\]);\n", s, re.S); mm = re.search(r"const \w+_M=(\[.*?\]);\n", s, re.S)
    return m.group(1), json.loads(m.group(2)), json.loads(mm.group(1))
OTHERS = {}
for fn in sorted(glob.glob(os.path.join(ROOT, "src", "data", "*.js"))):
    b = os.path.basename(fn)
    if b in ("hon.js", "clubcolors.js", "finals.js", "ldg.js") or "src/data/" + b not in TRACKED: continue
    P, oe, om = load_js(fn); OTHERS[b] = (oe, om)
BYDATE = collections.defaultdict(list)
for b, (oe, om) in OTHERS.items():
    for x in oe: BYDATE[x[9]].append((b, x))
STOP = {"fc", "cf", "ac", "sc", "club", "the", "afc", "football", "united", "city", "real", "sv", "as", "ss", "athletic", "town", "county",
        "rovers", "albion", "wanderers", "al", "hyundai", "samsung", "motors", "ilhwa", "chunma", "sangmu", "citizen", "dragons", "steelers", "bluewings",
        "red", "osaka", "fk", "vfl", "bv", "borussia", "werder", "bayer", "eintracht", "hertha", "manchester", "west", "new", "aston", "villa"}
def toks(n): return {t for t in norm(n).split() if t not in STOP and len(t) > 2}
def same_team(a, b): return key(a) == key(b) or bool(toks(a) & toks(b))
def same_match(o, d):
    cand = [(b, x) for b, x in BYDATE.get(d, []) if key(x[1]) == key(o)] or [(b, x) for b, x in BYDATE.get(d, []) if same_team(x[1], o)]
    return cand, {(x[2], x[12]) for b, x in cand}

# ---------------------------------------------------------------- 순위 라벨 → Elo
_LRA = {"__file__": os.path.join(ROOT, "tools", "league_rank_apply.py"), "__name__": "lra"}
_argv = sys.argv; sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(_LRA["__file__"], encoding="utf-8").read().split("if __name__ == '__main__':")[0], "lra", "exec"), _LRA)
sys.argv = _argv
sys.path.insert(0, os.path.join(ROOT, "tools")); import league_points as PTS
def lv_value(lv, d, o=None):
    m_ = re.match(r"^(\S+) (\d)부 (\d{4})(?:-(\d{2}))? 순위 없음", lv)
    if m_:
        cal = m_.group(4) is None; y = int(m_.group(3)) + (0 if cal else 1)
        return int(round(_LRA["base"](_LRA["KO"][m_.group(1)], int(m_.group(2)), y, cal)))
    p = _LRA["parse"](lv, d)
    if not p: sys.exit("라벨 해석 실패 " + lv)
    v = _LRA["value"](*p)
    if v is None: sys.exit("라벨 값 없음 " + lv)
    if o is not None:
        b_, sd_ = _LRA["base"](p[0], p[1], p[2], p[3]), _LRA["sd"](p[0], p[1])
        vp = PTS.value(lv, o, b_, sd_, _LRA["cv"]) if (p[1] == 1 and p[0] in _LRA["BIG"]) else PTS.value_other(lv, o, p[0], p[1], b_, sd_, _LRA["cv"])
        if vp is not None: v = vp
    return v
MAP_NEED = {}
def map_check(lv, o):
    head = lv.split(" (")[0]; mm = re.match(r"^(.*?) (\d+)위", head)
    if not mm: return
    E_ = PTS.O["seasons"].get(mm.group(1))
    if not E_ or "skip" in E_ or E_.get("ongoing") or "tables" not in E_: return
    if PTS.other_score(lv, o) is not None: return
    rk = int(mm.group(2)); R = E_["tables"][0]["rows"]
    MAP_NEED[(mm.group(1), o)] = (R[rk - 1][0] if rk <= len(R) else "?", rk - 1)

# 순위표: raw/ranks.txt (K리그 1997~2020 = 영어 위키백과 시즌 문서 최종표(플레이오프 최종 순위 반영), 그 밖은 TM 표·위키 표)
RANKS = collections.defaultdict(dict)
for line in open(os.path.join(RAW, "ranks.txt"), encoding="utf-8"):
    p = line.rstrip("\n").split("|")
    if len(p) < 6 or p[0] == "league": continue
    lg, se = p[0], p[1]
    if lg.startswith("20") and "_" in lg:   # 위키 모듈: '2015_J1_League' + 'Overall table / …'
        yy = lg[:7] if lg[4] == "–" else lg[:4]
        if "Overall" not in se and not se.startswith(("Standings", "League table")): continue
        lg, se = lg[5:] if lg[4] == "_" else lg[8:], yy.replace("–", "-")
        if len(se) == 7: se = se[:5] + se[5:]
    se = se.split(" ")[0]
    nm = p[4].replace("&nbsp;", " ")
    if lg == "K League 1": nm = {"Ulsan Hyundai Horang-i": "Ulsan Hyundai", "Gwangju Sangmu Bulsajo": "Gwangju Sangmu", "Sangju Sangmu Phoenix": "Sangju Sangmu"}.get(nm, nm)
    RANKS[(lg, se)][key(nm)] = (int(p[2]), int(p[3]), p[4], p[5])
KL_PEN = {("2016", key("FC Seoul")): 2, ("2016", key("Jeonbuk Hyundai Motors")): 1}   # 2016 전북 승점 9 감점 → 감점 전 순위(감점 시즌 규칙)
def kl_desc(y):
    y = int(y)
    if y <= 2000 or 2004 <= y <= 2011: return "K리그, 챔피언십 플레이오프 반영 최종 순위"
    if y <= 2003: return "K리그 단일 리그 최종 순위"
    if y <= 2018: return "K League Classic/K League 1, 스플릿 뒤 최종 순위"
    return "K League 1, 플레이오프·스플릿 뒤 최종 순위"
WORLD = {"JAP1": "J1리그", "CSL": "중국 슈퍼리그", "AUS1": "호주 A리그", "SA1": "사우디 프로리그", "HGKG": "홍콩 프리미어리그", "QSL": "카타르 1부", "UAE1": "UAE 프로리그"}
def make_label(lg, se, v, k):
    r, n, nm, src = v
    if lg == "K League 1":
        if (se, k) in KL_PEN: r = KL_PEN[(se, k)]; return f"K리그1 {se} {r}위/{n}팀 (감점 전 순위; {kl_desc(se)})"
        return f"K리그1 {se} {r}위/{n}팀 ({kl_desc(se)})"
    if lg == "J1_League": return f"J1리그 {se} 연간 {r}위/{n}팀"
    if lg in WORLD: return f"{WORLD[lg]} {se} {r}위/{n}팀"
    if lg == "THA1": return f"태국 1부 {se} {r}위/{n}팀 (Thai League 1)"
    if lg == "Thai_Premier_League": return f"태국 1부 {se} {r}위/{n}팀 (Thai Premier League)"
    if lg == "Indonesia_Super_League": return f"인도네시아 1부 {se} {r}위/{n}팀 (Indonesia Super League)"
    if lg == "V.League_1": return f"베트남 1부 {se} {r}위/{n}팀 (V.League 1)"
    if lg == "RSK2": return f"한국 2부 {se} {r}위/{n}팀 (K League Challenge, 리그 수준 추정)"
    if lg == "Korea_National_League": return f"한국 3부 {se} {r}위/{n}팀 (Korea National League, 리그 수준 추정)"
    if lg == "GB3": return f"잉글랜드 3부 {se} {r}위/{n}팀 (Football League One, 리그 수준 추정)"
    if lg == "GB4": return f"잉글랜드 4부 {se} {r}위/{n}팀 (Football League Two, 리그 수준 추정)"
    if lg == "GB2": return f"챔피언십 {se} {r}위/{n}팀"
    if lg == "GB1": return f"프리미어리그 {se} {r}위" + ("" if n == 20 else f"/{n}팀")
    return None
CAL_LG = {"K League 1", "JAP1", "J1_League", "CSL", "THA1", "Thai_Premier_League", "V.League_1", "RSK2", "Korea_National_League"}
def lg_cands(d):
    y, m = int(d[:4]), int(d[5:7]); s_ = y if m >= 8 else y - 1
    eu = f"{s_}-{str(s_ + 1)[2:]}"
    out = []
    for lg in ["K League 1", "JAP1", "J1_League", "CSL", "THA1", "Thai_Premier_League", "V.League_1", "RSK2", "Korea_National_League", "AUS1", "SA1", "HGKG",
               "QSL", "UAE1", "Indonesia_Super_League", "GB1", "GB2", "GB3", "GB4"]:
        out.append((lg, str(y) if lg in CAL_LG else eu))
    return out, [str(y), eu]

MAN = {}   # 순위표 밖 상대: gameId -> lv
def man(gid, lv): MAN[gid] = lv
# 대학 팀(한국 FA컵): 리그 소속 없음 → 한국 4부 '순위 없음' 기준값(대학 팀 = 실업 3부 아래로 봄, 추정)
man("3177341", "한국 3부 2002 순위 없음 (아주대학교, 대학 팀 — 리그 소속 없음, 실업 리그 아래 단계로 봄; 리그 수준 추정)")
man("1016876", "인도네시아 1부 2009-10 2위/18팀 (Indonesia Super League)")   # 영어 위키백과 시즌 문서 순위표(raw/ranks.txt)
man("2518354", "베트남 1부 2015 1위/14팀 (V.League 1)")   # 영어 위키백과 2015 V.League 1: 베카멕스 빈즈엉 우승(14팀; 수집 모듈은 11행만)
man("3268733", "한국 3부 2005 순위 없음 (호남대학교, 대학 팀 — 리그 소속 없음, 실업 리그 아래 단계로 봄; 리그 수준 추정)")
man("1017424", "호주 A리그 2009-10 10위/10팀")   # TM 표는 2010-11 창단 멜버른 하트를 넣어 11팀으로 잘못 셈(영어 위키백과 10팀, 애들레이드 최하위)
man("3138341", "한국 2부 2010 3위/15팀 (Korea National League, 실업 리그·플레이오프 뒤 최종 순위; 리그 수준 추정)")   # 2010년 K리그 2부 없음 → 내셔널리그가 2단계. 통합 1위, 플레이오프 준결승 탈락(영어 위키백과)

ELO_SRC = collections.Counter(); ELO_LOG = {}; MISS = []; NEW_TS = {}; TABLE_DIFF = []
def opp_elo(o, d, g):
    gid = g["gameId"]
    cand, vals = same_match(o, d)
    if len(vals) == 1:
        e, lv = next(iter(vals)); ELO_SRC["같은 경기 다른 선수 자료"] += 1
        ELO_LOG[(o, d)] = ("same", e, lv, sorted({b for b, _ in cand})); return e, lv
    if len(vals) > 1: print("  [같은 경기 값 여럿]", o, d, vals)
    if gid in MAN:
        lv = MAN[gid]; e = lv_value(lv, d, o); ELO_SRC["직접 라벨"] += 1; ELO_LOG[(o, d)] = ("man", e, lv); return e, lv
    k = key(o); cands, seasons = lg_cands(d)
    for s in seasons:
        if (k, s) in TABLE:
            (e, lv), _ = collections.Counter(TABLE[(k, s)]).most_common(1)[0]
            ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(o, d)] = ("table", e, lv, s)
            if _LRA["parse"](lv, d) and lv_value(lv, d, o) != e: TABLE_DIFF.append((o, s, e, lv, lv_value(lv, d, o)))
            map_check(lv, o); return e, lv
    for lg, s in cands:
        t = RANKS.get((lg, s), {})
        if k in t:
            lv = make_label(lg, s, t[k], k)
            if lv:
                e = lv_value(lv, d, o); map_check(lv, o); ELO_SRC["순위표 → 라벨"] += 1
                ELO_LOG[(o, d)] = ("model", e, lv); NEW_TS[(o, s)] = (e, lv); return e, lv
    MISS.append((o, d, g["competitionId"], tuple(seasons))); return 0, "?"

exec(open(os.path.join(HERE, "man_elo.py"), encoding="utf-8").read()) if os.path.exists(os.path.join(HERE, "man_elo.py")) else None

E = []
for typ, gid, mi, dm, gf, ga, pk, note, desc in raw_rows:
    g = G[gid]; d = g["date_local"]; cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    elo, lv = opp_elo(opp(g), d, g)
    et = 1 if (g["gameState"] in ("extra_time", "penalty_shootout", "golden_goal") and mi > 90 and not (dm and str(dm).startswith("90+"))) else 0
    row = [typ, opp(g), elo, comp, mi, gf, ga, ko, pk, d, et, dm, lv, note]
    t = tie_of(gid)
    if t: row.append(t)
    E.append(row)
E.sort(key=lambda r: (r[9], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5, 0 if r[0] == "g" else 1))

if MISS:
    for x in sorted(set(MISS), key=lambda x: x[1]): print("Elo 없음:", x)
    if "--force" not in sys.argv: sys.exit(1)
if "--debug" in sys.argv:
    print(ELO_SRC); seen = set()
    for (o, d), v in sorted(ELO_LOG.items(), key=lambda kv: kv[0][1]):
        k_ = (o, v[1], v[2])
        if k_ in seen: continue
        seen.add(k_); print(d, o, v)
    print("TABLE_DIFF", TABLE_DIFF); sys.exit(0)

# ---------------------------------------------------------------- FotMob 골 대조(2010.7 이후)
FM_CMP = []
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    tm = [r for r in raw_rows if r[1] == gid and r[0] == "g"]
    fm = [r for r in FME[gid] if r["ldg_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if len(tm) != len(fm): FM_CMP.append(("골 수 다름", gid, G[gid]["date_local"], [x[2] for x in tm], [x["time"] for x in fm]))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[10] != b[10]: d.append("연장")
    return d
CROSS = []
LRE = re.compile(r"Dong-?gook Lee|Lee Dong-?gook|이동국", re.I)
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and LRE.search(str(x[13] or "")):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(이동국 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x[1], r[1])]
            if hit: CROSS.append(("이동국 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x[1], r[1]):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm[1], m[1]) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "g":
            for j in judg:
                if j[0].startswith("도움 제외") and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and same_team(x[1], j[2]):
                    CROSS.append(("이동국 도움을 뺀 타인 골", b, x[9], x[4], j[5]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("pohldg", "2001-01-01", "포항 스틸러스", "포항", "1998~2000"), ("wbrldg", "2001-07-01", "베르더 브레멘", "브레멘", "2001"),
         ("pohldg", "2003-01-01", "포항 스틸러스", "포항", "2001~2002"), ("smldg", "2005-04-01", "광주 상무", "상무", "2003~2005"),
         ("pohldg", "2007-01-01", "포항 스틸러스", "포항", "2005~2006"), ("mboldg", "2008-07-01", "미들즈브러", "미들즈브러", "2007~2008"),
         ("snldg", "2009-01-01", "성남 일화 천마", "성남", "2008"), ("jbldg", None, "전북 현대 모터스", "전북", "2009~2020")]
TM_CLUB = {"311": "pohldg", "86": "wbrldg", "6505": "smldg", "641": "mboldg", "3610": "snldg", "6502": "jbldg"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
for g in GAMES:
    if club_of(g["date_local"]) != TM_CLUB[g["clubId"]]: sys.exit("클럽 경계 불일치 " + g["gameId"] + " " + g["clubId"] + " " + g["date_local"])
CAL = {"pohldg", "smldg", "snldg", "jbldg"}
def season_of(d, club):
    y, m = int(d[:4]), int(d[5:7])
    if club in CAL: return str(y)
    s_ = y if m >= 8 else y - 1
    return f"{s_}-{str(s_ + 1)[2:]}"
STINTS = [("포항 스틸러스", "2001-01-01"), ("베르더 브레멘(임대)", "2001-07-01"), ("포항 스틸러스", "2003-01-01"), ("광주 상무", "2005-04-01"),
          ("포항 스틸러스", "2007-01-01"), ("미들즈브러", "2008-07-01"), ("성남 일화 천마", "2009-01-01"), ("전북 현대 모터스", "9999")]
CLUBNAME = {"pohldg": "포항 스틸러스", "wbrldg": "베르더 브레멘(임대)", "smldg": "광주 상무", "mboldg": "미들즈브러", "snldg": "성남 일화 천마", "jbldg": "전북 현대 모터스"}
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for n in ["포항 스틸러스", "베르더 브레멘(임대)", "광주 상무", "미들즈브러", "성남 일화 천마", "전북 현대 모터스"])
for m in M: n = CLUBNAME[club_of(m[0])]; ST[n][0] += 1; ST[n][3] += m[3]
for r in E: n = CLUBNAME[club_of(r[9])]; ST[n][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g"); MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14)

if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, "TM PK", PK_TM, MIN_TOT, len(E), NTIE, dict(ELO_SRC))
    for j in judg: print(j)
    for a in A_STATUS: print(a)
    for c in CROSS: print(c)
    print("FM", FM_CMP)
    print("KL_G_DIFF", KL_G_DIFF); print("ADDED_FIX", ADDED_FIX)
    print("SCORE_MISMATCH", SCORE_MISMATCH)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    for (o, s), (e, lv) in sorted(NEW_TS.items(), key=lambda kv: kv[0][1]): print("NEW", o, s, e, lv)
    print("TABLE_DIFF", TABLE_DIFF)
    for k, v in sorted(MAP_NEED.items()): print("MAP_NEED", k, v)
    sys.exit(0)

# ---------------------------------------------------------------- 설명(NOTE)
exec(open(os.path.join(HERE, "note_leedonggook.py"), encoding="utf-8").read())   # NOTE_LINES
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "MAN", "cwc", "acl", "mlp", "lg"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE): sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []; seen = set()
for r in E:
    k_ = (r[0], r[9], r[4], r[5], r[6], r[13])
    if k_ in seen: problems.append(("중복", r))
    seen.add(k_)
mdates = collections.Counter(m[0] for m in M)
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
for d, rs in by.items():
    if d not in mdates: problems.append(("E 날짜가 M에 없음", d))
for r in E:
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if not r[2] or r[12] == "?": problems.append(("Elo 없음", r))
mm_ = {m[0]: m for m in M}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__":
    open(OUT_JS, "w", encoding="utf-8").write(f"const LDG_E={J(E)};\nconst LDG_M={J(M)};\nconst LDG_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "assist_status": A_STATUS,
               "cross_check": CROSS, "fotmob_goal_diffs": FM_CMP, "kleague_goal_diffs": KL_G_DIFF, "elo_sources": ELO_SRC,
               "new_team_seasons": {f"{o}|{s}": v for (o, s), v in NEW_TS.items()}, "table_label_diffs": TABLE_DIFF,
               "points_map_needed": [f"{k[0]} | {k[1]} | {v[0]} | {v[1]}" for k, v in sorted(MAP_NEED.items())],
               "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행 · Elo {dict(ELO_SRC)} → {OUT_JS}")
    for k, v in ST.items(): print(" ", k, v)
    print("점검 문제", len(problems))
    for p_ in problems: print("  ", p_)
