#!/usr/bin/env python3
"""플로랑 말루다: raw/ -> malouda.json + src/data/mld.js (판정은 judgments.md)

  python3 players/malouda/build_malouda.py
"""
import csv, json, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import elo_malouda as EL
from elo_malouda import key, TABLE, RANKS, half_up, L1_18, L1_20, TR_1314, PT_0910, egy18, isl8, lux14, interp

RAW = os.path.join(HERE, "raw")
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT_JS = os.path.join(ROOT, "src", "data", "mld.js")
OUT_JSON = os.path.join(HERE, "malouda.json")
GAP = "2014-08-01"

# ---------------------------------------------------------------- 도움 판정
# 2013-09-29 코니아스포르전 71분 유믈루: TM 'Shot on goal'이지만 FotMob이 말루다 도움으로 센 것 -> 남김 (뮐러 keepShotFM 선례).
#   수집자 메모는 제외였으나 문서 3절 선례(FotMob이 센 리바운드성 도움은 FotMob 기준)를 따름. 되돌리려면 KEEP_SHOT_FM을 비움.
KEEP_SHOT_FM = set()
# 2014.8 이후 도움 중 두 번째 출처가 확인하지 못해 뺀 것 (gameId|분 -> 이유)
UNCONFIRMED = {
    "2638662|75": "와디 데글라 2016.2.21 엔피전 75분 라잡 나빌: 이집트 기사 Youm7(2016.6.13)이 말루다 도움으로 적었으나 두 번째 출처 없음",
    "2658710|12": "와디 데글라 2016.2.14 자말렉전 12분 마흐무드 알라(코너킥): Youm7 한 곳만",
    "2658721|33": "와디 데글라 2016.2.17 탈라에 엘 가이시전 33분 무스타파 갈랄(프리킥): Youm7 한 곳만",
    "2667729|83": "와디 데글라 2016.3.7 페트로제트전 83분 마흐무드 알라(프리킥): Youm7 한 곳만",
    "2695510|52": "와디 데글라 2016.6.8 모카울룬전 52분 마흐무드 알라(크로스): Youm7 한 곳만",
    "2689349|90+5": "와디 데글라 2016.5.7 알아흘리전 90+5분 주니오르 마푸쿠: 출처 확인 못 함",
    "2695863|44": "와디 데글라 2016.7.8 이티하드 알렉산드리아전 44분 스탠리 오하우추쿠(코너킥): 출처 확인 못 함",
    "2695863|62": "와디 데글라 2016.7.8 이티하드 알렉산드리아전 62분 마흐무드 알라(프리킥): 출처 확인 못 함",
    "2881546|45": "디페르당주 2018.3.11 빅토리아 로스포르전 45분 니콜라 페레스: FotMob 도움 없음, 기사 확인 못 함",
    "2881589|84": "디페르당주 2018.5.4 위스테르트전 84분 톰 지베나이커: FotMob 도움 없음, 기사 확인 못 함",
    "2950953|9": "디페르당주 2018.3.25 룩셈부르크컵 에르펠당주전 9분 고티에 카롱: FotMob 도움 없음, 기사 확인 못 함",
}
KEEP_UNCONFIRMED = set()          # 비어 있으면 모두 제외
if os.environ.get("MLD_ALT"):   # 검토용: 제외한 도움을 되살린 대안 계산(출력 파일은 쓰지 않음)
    KEEP_UNCONFIRMED = set(UNCONFIRMED) if os.environ["MLD_ALT"] == "all" else {k for k in UNCONFIRMED if "Youm7" in UNCONFIRMED[k] or "한 곳만" in UNCONFIRMED[k]}
# 델리 다이너모스 2015·2016: FotMob 선수 경력 도움 합계(8·3)가 TM과 같고 ISL 공식 사이트(2015 도움 8개)도 같아 TM 도움 11개를 모두 둠.
#   FotMob 경기 이벤트에는 도움이 없음.
DELHI_OK = {"2015": 8, "2016": 3}
MIN_FIX = {}
# 이벤트 보정: gameId|분 -> (골 전 우리 득점, 골 전 상대 득점)
SCORE_FIX = {
    "2987469|85": (4, 0),   # TM 목록에 리옹 자책골(로페스 72분)이 빠져 있음 -> 프랑스어 위키백과 시즌 문서 0-5 (0-1) 골 순서
}

# ---------------------------------------------------------------- 대회 코드
def comp_of(cid, rnd):
    r = rnd.lower()
    if cid in ("FR1", "GB1", "FR2", "TR1", "IND1", "EGY1", "LUX1"): return "lg"
    if cid == "INDP": return "dsf"
    if cid in ("FRC", "FRL", "FAC", "CGB", "EGYP", "LUXP"):
        if r.startswith("final"): return "df"
        if r.startswith("semi"): return "dsf"
        if r.startswith("quarter"): return "dk"
        if cid == "FAC" and r.startswith("sixth"): return "dk"
        return "dc"
    if cid in ("GBCS", "FRCH"): return "df"
    if cid == "ELQ": return "elq"
    if cid == "CL":
        if r.startswith("group"): return "clg"
        if r.startswith("last 16"): return "cl16"
        if r.startswith("quarter"): return "clk"
        if r.startswith("semi"): return "clsf"
        return "clf"
    if cid == "EL":
        if r.startswith("group"): return "elg"
        return "elk"
    sys.exit("모르는 대회 " + cid + " " + rnd)

def ko_of(cid, rnd):
    r = rnd.lower()
    if "leg" in r: return 0
    if cid in ("FR1", "GB1", "FR2", "TR1", "IND1", "EGY1", "LUX1"): return 0
    if r.startswith("group"): return 0
    return 1

# ---------------------------------------------------------------- 상대 Elo
def euro_season(d):
    y, m = int(d[:4]), int(d[5:7])
    if d.startswith("2020-08"): return "2019-20"
    s = y if m >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"

# 직접 추정 (모두 '추정'); 값 근거는 judgments.md
MAN = {
    (key("Rosenborg BK"), "2007"): None,   # 기존 표에 있음 (달력 연도)
    (key("Bourg-Péronnas"), "2003-04"): (1303, "프랑스 3부(나시오날) 2003-04 (추정, 순위 미확인 중위권: 같은 시즌 10위 1303)"),
    (key("FC Bourg-Péronnas"), "2003-04"): (1303, "프랑스 3부(나시오날) 2003-04 (추정, 순위 미확인 중위권: 같은 시즌 10위 1303)"),
    (key("OS Aire Football"), "2003-04"): (1100, "프랑스 아마추어 (추정, 드록바 자료 세이시네 파리제 1100과 같음)"),
}
# 다른 나라 리그: 기존 상위권 값과 같게 (추정)
FOREIGN = {
    "ZYP1": (1450, "키프로스 {s} {r}위 (추정, 키프로스 상위권 1450과 같음)"),
    "ALB1": (1300, "알바니아 {s} {r}위 (추정, KF 티라나 2009-10 3위 1300과 같음)"),
    "PL1": (1480, "폴란드 {s} {r}위 (추정, 레기아 바르샤바 2011-12 3위 1480과 같음)"),
}
ELO_SRC = collections.Counter()
ELO_LOG = collections.OrderedDict()

def season_label(d, opp, lg_hint):
    if lg_hint == "IND1": return d[:4]
    if key(opp) == key("Rosenborg BK"): return d[:4]
    return euro_season(d)

def opp_elo(opp, date, lg_hint):
    k = key(opp); s = season_label(date, opp, lg_hint)
    if (k, s) in TABLE:
        e, lv = collections.Counter(TABLE[(k, s)]).most_common(1)[0][0]
        ELO_SRC["기존 팀×시즌 값"] += 1; ELO_LOG[(opp, s)] = (e, lv, "기존"); return e, lv
    if MAN.get((k, s)):
        e, lv = MAN[(k, s)]; ELO_SRC["직접 추정"] += 1; ELO_LOG[(opp, s)] = (e, lv, "직접 추정"); return e, lv
    for (lg, ss), tab in RANKS.items():
        if ss != s or k not in tab: continue
        r, n = tab[k]
        res = None
        if lg == "FR1":
            res = ((L1_18 if n == 18 else L1_20)[r], f"리그1 {s} {r}위")
        elif lg == "FR2":
            res = (EL_l2(r, n), f"리그2(프랑스 2부) {s} {r}위")
        elif lg == "TR1" and s == "2013-14":
            res = (interp(TR_1314, r), f"쉬페르리그 {s} {r}위")
        elif lg == "PO1" and s == "2009-10":
            res = (PT_0910[r], f"포르투갈 1부 {s} {r}위")
        elif lg == "EGY1":
            res = (egy18(r), f"이집트 프리미어리그 {s} {r}위 (추정)")
        elif lg == "IND1":
            res = (isl8(r), f"인도 슈퍼리그 {s} {r}위 (추정: 1위 1300~꼴찌 1200 직선)")
        elif lg == "LUX1":
            res = (lux14(r), f"룩셈부르크 1부 {s} {r}위 (추정: 1위 1300~꼴찌 1200 직선)")
        elif lg == "LUX2":
            res = (1150, f"룩셈부르크 2부 {s} {r}위 (추정)")
        elif lg in FOREIGN:
            e, t = FOREIGN[lg]; res = (e, t.format(s=s, r=r))
        if res:
            ELO_SRC["순위표+리그 모형/추정(" + lg + ")"] += 1; ELO_LOG[(opp, s)] = (res[0], res[1], lg + " " + str(r)); return res
    sys.exit(f"상대 Elo 없음: {opp} {s}")

L2_KNOWN = {1: 1669, 2: 1624, 4: 1582, 5: 1573, 6: 1567, 7: 1559, 8: 1550, 9: 1540, 10: 1532, 11: 1526, 12: 1521, 13: 1516,
            14: 1513, 15: 1508, 16: 1500, 17: 1490, 18: 1484, 19: 1480, 20: 1469}   # 기존 선수 자료의 리그2(20팀) 순위값, 3위만 2·4위 가운데
def EL_l2(r, n):
    if n != 20: sys.exit("프랑스 2부 %d팀 시즌" % n)
    if r == 3: return 1603                     # 2위 1624와 4위 1582의 가운데
    return interp(L2_KNOWN, r)

# ---------------------------------------------------------------- 출전
games = list(csv.DictReader(open(os.path.join(RAW, "tm_games.csv"), encoding="utf-8")))
for g in games:
    assert g["level"] == "senior"
G = {g["gameId"]: g for g in games}
LD = "date_local_tm_report"
M = [[g[LD], g["opponent"].strip(), comp_of(g["competitionId"], g["round"]), int(g["playedMinutes"])]
     for g in sorted(games, key=lambda g: (g[LD], g["gameId"]))]

# ---------------------------------------------------------------- 두 경기 합산
INFO = {m["gameId"]: m for m in csv.DictReader(open(os.path.join(RAW, "tm_match_info.csv"), encoding="utf-8"))}
OURS = {"Chelsea FC", "Olympique Lyon", "Trabzonspor"}
def tie_of(gid, cid, rnd, date):
    """[차전, 홈, 1차전 우리, 1차전 상대, 원정골, 연장]"""
    g = G[gid]; r = rnd.lower()
    leg = 1 if "1st" in r else 2
    home = 1 if g["venue"] == "H" else 0
    y = int(date[:4]); m = int(date[5:7]); s0 = y if m >= 8 else y - 1
    ag = 1
    if cid in ("CL", "EL", "ELQ") and s0 >= 2021: ag = 0
    if cid == "CGB" and s0 >= 2018: ag = 0
    et = 1
    if leg == 1: return [1, home, 0, 0, ag, et]
    info = INFO[gid]
    oi = INFO.get(info["other_leg_id"])
    if not oi: sys.exit("다른 차전 리포트 없음 " + gid)
    hs, as_ = map(int, oi["final"].split(":"))
    ours_home_first = oi["home"] in OURS
    f_ours, f_theirs = (hs, as_) if ours_home_first else (as_, hs)
    return [2, home, f_ours, f_theirs, ag, et]

# ---------------------------------------------------------------- 골·도움
ev = list(csv.DictReader(open(os.path.join(RAW, "malouda_goal_assist_events.csv"), encoding="utf-8")))
def minute(s):
    if "+" in s:
        a, b = s.split("+"); return int(a) + int(b), s
    return int(s), 0

rows, judg = [], []
for e in ev:
    gid, mstr = e["gameId"], e["minute_tm"]
    g = G[gid]; tag = f"{gid}|{mstr}"; role = e["malouda_role"]
    if role == "goal" and e["own_goal"] == "1":
        judg.append(("골 제외(자책골)", e["date_local"], e["opponent"], mstr)); continue
    if role == "assist":
        why = None
        if e["own_goal"] == "1": why = "상대 자책골 유도"
        elif e["assist_type_tm"] == "Penalty: Fouled player": why = "PK 유도"
        elif e["assist_type_tm"] == "Shot on goal" and tag not in KEEP_SHOT_FM: why = "Shot on goal(슈팅 리바운드)"
        elif tag in UNCONFIRMED and tag not in KEEP_UNCONFIRMED: why = UNCONFIRMED[tag]
        elif e["date_local"] >= GAP and "Malouda" not in (e["fm_assistStr"] or "") and tag not in UNCONFIRMED \
                and not (g["competitionId"] == "IND1" or e["date_local"] >= "2015-10-01" and g["competitionId"] == "IND1"):
            sys.exit("2014.8 이후 FotMob에 없는 도움 판정 누락: " + tag)
        if why:
            judg.append(("도움 제외", e["date_local"], e["opponent"], mstr, e["scorer"], why)); continue
    mi, dm = minute(MIN_FIX.get(tag, mstr))
    bh, ba = map(int, e["score_after_home_away"].split("-"))
    if e["venue"] == "H": bh -= 1
    else: ba -= 1
    gf, ga = (bh, ba) if e["venue"] == "H" else (ba, bh)
    if tag in SCORE_FIX: gf, ga = SCORE_FIX[tag]
    cid, rnd = g["competitionId"], g["round"]
    comp = comp_of(cid, rnd); ko = ko_of(cid, rnd)
    lg_hint = cid if cid in ("IND1",) else None
    elo, lv = opp_elo(g["opponent"].strip(), e["date_local"], lg_hint)
    note = 0 if role == "goal" else e["scorer"]
    pk = 1 if (role == "goal" and e["penalty"] == "1") else 0
    # 연장·승부차기까지 간 단판 토너먼트 경기(ko=1)의 행은 모두 et=1
    went_et = g["gameState"] in ("extra_time", "penalty_shootout") or int(g["gameDuration"] or 90) > 90
    et = 1 if (went_et and ko and "leg" not in rnd.lower()) else 0
    if "leg" in rnd.lower() and mi > 94: et = 1
    row = ["g" if role == "goal" else "a", g["opponent"].strip(), elo, comp, mi, gf, ga, ko, pk, e["date_local"], et, dm, lv, note]
    if "leg" in rnd.lower(): row.append(tie_of(gid, cid, rnd, e["date_local"]))
    rows.append(row)
rows.sort(key=lambda r: (r[9], r[4], r[0]))
E = rows

# ---------------------------------------------------------------- 클럽
CLUBS = [("2000-07-28", "샤토루", "chtml"), ("2003-07-22", "갱강", "guiml"), ("2007-07-09", "리옹", "lyoml"),
         ("2013-07-18", "첼시", "cheml"), ("2014-09-17", "트라브존스포르", "trbml"), ("2015-08-23", "메스", "metml"),
         ("2016-01-29", "델리 다이너모스", "delml"), ("2016-07-19", "와디 데글라", "wadml"),
         ("2018-01-25", "델리 다이너모스", "delml"), ("9999-12-31", "디페르당주 03", "difml")]
def club_of(d):
    for u, n, k in CLUBS:
        if d < u: return n
ORDER = ["샤토루", "갱강", "리옹", "첼시", "트라브존스포르", "메스", "델리 다이너모스", "와디 데글라", "디페르당주 03"]
ST = collections.OrderedDict((n, [0, 0, 0]) for n in ORDER)
for m in M: ST[club_of(m[0])][0] += 1
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
MIN_TOT = sum(m[3] for m in M)

if __name__ == "__main__":
    if os.environ.get("MLD_ALT"):
        json.dump(E, open(os.environ["MLD_OUT"], "w", encoding="utf-8"), ensure_ascii=False); sys.exit(0)
    J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    import malouda_note
    NOTE = malouda_note.make(globals())
    for r in E:
        if r[7] and r[4] > 95 and not r[10] and len(r) <= 14: sys.exit("연장 골 판정 필요: " + str(r))
    # §16 점검
    problems = []
    seen = set()
    for r in E:
        k = (r[0], r[9], r[4], r[5], r[6])
        if k in seen: problems.append(("중복", r))
        seen.add(k)
    mdates = {(m[0], m[1]) for m in M}
    by = collections.defaultdict(list)
    for r in E: by[r[9]].append(r)
    for d, rs in by.items():
        if not any(m[0] == d for m in M): problems.append(("출전 없음", d))
        # 한 경기 안 스코어 순서: 같은 분이 아닐 때 우리+상대 득점 합이 분 순서와 모순되면 경고
        for a in rs:
            for b in rs:
                if a[1] == b[1] and a[4] < b[4] and a[5] + a[6] > b[5] + b[6]: problems.append(("스코어 역순", a, b))
    for r in E:
        if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
        if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
        if r[5] < 0 or r[6] < 0: problems.append(("음수 스코어", r))
    for p in problems: print("점검:", p)
    open(OUT_JS, "w", encoding="utf-8").write(f"const MLD_E={J(E)};\nconst MLD_M={J(M)};\nconst MLD_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judg": judg, "elo_sources": ELO_SRC,
               "elo_log": [[a, b, c[0], c[1], c[2]] for (a, b), c in ELO_LOG.items()]},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골 {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · Elo {dict(ELO_SRC)}")
    for n, v in ST.items(): print(" ", n, v)
