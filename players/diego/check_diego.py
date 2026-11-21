# build_diego.py 가 exec 로 읽는 부분: FotMob 대조·동료 대조·클럽 통계·§16 점검·파일 쓰기

# ---------------------------------------------------------------- FotMob 골 대조(2010-11 이후, FotMob 경기 이벤트가 있는 경기)
FM_CMP = []; FM_N = 0
for gid, evs in EVS.items():
    if gid not in G or gid not in FME: continue
    if not any(r["time"] for r in FME[gid]): continue
    if FME[gid][0]["date_utc"][:4] == "2026": continue     # 2969653: FotMob 경기 대응이 잘못됨(2026년 경기)
    tm = [e for e in evs if e["scorer_id"] == ME and not is_og(e)]
    fm = [r for r in FME[gid] if r["diego_scorer"] == "1" and r["pen_shootout_event"] != "True"]
    if tm or fm: FM_N += 1
    if len(tm) != len(fm):
        FM_CMP.append(("골 수 다름", gid, ldate(G[gid]), [x["minute"] for x in tm], [x["time"] for x in fm])); continue
    for t, f in zip(sorted(tm, key=lambda x: mins(x["minute"])[0]), sorted(fm, key=lambda x: int(x["time"]) + int(x["overloadTime"] or 0))):
        tp = t["goal_desc"] == "Penalty"; fp = "penalty" in (f["goalDescriptionKey"] or "").lower() or "pen" in (f["suffix"] or "").lower()
        a = mins(t["minute"])[0]; b = int(f["time"]) + int(f["overloadTime"] or 0)
        if tp != fp or abs(a - b) > 1: FM_CMP.append(("다름", gid, ldate(G[gid]), t["minute"], t["goal_desc"], f["time"], f["overloadTime"], f["goalDescriptionKey"]))

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(수정 없음)
def cmp_rows(a, b):
    d = []
    if abs(a[4] - b[4]) > 2: d.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): d.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    if a[3] != b[3]: d.append(f"대회 {a[3]}/{b[3]}")
    if a[2] != b[2]: d.append(f"Elo {a[2]}/{b[2]}")
    if a[12] != b[12]: d.append(f"lv {a[12]}/{b[12]}")
    if a[7] != b[7] or (a[14] if len(a) > 14 else None) != (b[14] if len(b) > 14 else None): d.append(f"단판/합산 {a[7]},{a[14] if len(a) > 14 else None}/{b[7]},{b[14] if len(b) > 14 else None}")
    if a[10] != b[10]: d.append("연장")
    if a[8] != b[8]: d.append("PK")
    return d
CROSS = []
ALLO = dict(OTHERS); ALLO.update(STAGED)
def same_team(x, r): return key(x[1]) == key(r[1]) or bool(toks(x[1]) & toks(r[1]))
IS_ME = re.compile(r"^Diego$")
for b, (oe, om) in ALLO.items():
    for x in oe:
        if x[0] == "a" and IS_ME.match(x[13] or ""):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            CROSS.append(("타인 도움(디에구 골)", b, x[9], x[4], x[1], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for r in E:
        if r[0] == "a":
            hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x, r)]
            if hit: CROSS.append(("디에구 도움→타인 골", b, r[9], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
        if r[0] == "g":
            hit = [x for x in oe if x[0] == "a" and x[9] == r[9] and abs(x[4] - r[4]) <= 2 and same_team(x, r)]
            for x in hit:
                if not IS_ME.match(x[13] or ""): CROSS.append(("타인 도움 표기 다름(디에구 골)", b, r[9], r[4], x[13]))
    for r in E:
        for x in oe:
            if x[9] == r[9] and same_team(x, r):
                dd = [t for t in cmp_rows(r, x) if t.startswith(("Elo", "lv", "대회"))]
                if dd: CROSS.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], dd))
                break
    for m in M:
        for mm in om:
            if mm[0] == m[0] and same_team(mm, m) and mm[2] != m[2]:
                CROSS.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[1], mm[2], m[2]))
    mdates = {(m[0], key(m[1])) for m in M}
    for mm in om:
        for dd in (-1, 1):
            try: d2 = (datetime.date.fromisoformat(mm[0]) + datetime.timedelta(days=dd)).isoformat()
            except Exception: continue
            if (d2, key(mm[1])) in mdates and (mm[0], key(mm[1])) not in mdates and mm[0][:4] >= "2002":
                CROSS.append(("같은 상대 출전 날짜 하루 차이", b, mm[0], d2, mm[1]))
# TM 디에구 도움을 규칙대로 뺀 골이 동료 자료에 도움자 '디에구'로 남아 있는지
for b, (oe, om) in ALLO.items():
    for x in oe:
        if x[0] == "a" and x[13] == "Diego": continue
        if x[0] == "g":
            for j in judg:
                if (j[0] == "도움 제외" or j[0].endswith("drop")) and j[1] == x[9] and abs(mins(j[3])[0] - x[4]) <= 2 and (key(x[1]) == key(j[2]) or toks(x[1]) & toks(j[2])):
                    CROSS.append(("TM 디에구 도움을 뺀 타인 골(타인 자료 확인)", b, x[9], x[4], j[4], j[-1][:40]))
_seen = set(); CROSS = [c for c in CROSS if not (str(c) in _seen or _seen.add(str(c)))]

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("santd", "2004-08-01", "산투스", "산투스", "2002~2004"), ("pordi", "2006-07-01", "FC 포르투", "포르투", "2004~2006"),
         ("werdi", "2009-07-01", "베르더 브레멘", "브레멘", "2006~2009"), ("juvdi", "2010-08-27", "유벤투스", "유벤투스", "2009~2010"),
         ("wobdi", "2011-08-31", "VfL 볼프스부르크", "볼프스부르크", "2010~2011, 2012~2014"), ("atmdi", "2012-06-30", "아틀레티코 마드리드", "아틀레티코", "2011~2012, 2014"),
         ("wobdi", "2014-01-31", "VfL 볼프스부르크", "볼프스부르크", "2010~2011, 2012~2014"), ("atmdi", "2014-07-10", "아틀레티코 마드리드", "아틀레티코", "2011~2012, 2014"),
         ("fendi", "2016-07-19", "페네르바흐체", "페네르바흐체", "2014~2016"), ("fladi", None, "플라멩구", "플라멩구", "2016~2022")]
TM_CLUB = {"221": "santd", "720": "pordi", "86": "werdi", "506": "juvdi", "82": "wobdi", "13": "atmdi", "36": "fendi", "614": "fladi"}
def club_of(d):
    for k, u, n, sh, y in CLUBS:
        if u is None or d < u: return k
CN = {}
for k, u, n, sh, y in CLUBS: CN.setdefault(k, n)
for g in GAMES:
    if club_of(ldate(g)) != TM_CLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CN)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({(r[9]) for r in E if len(r) > 14})
CAL = {"santd", "fladi"}; JUL10 = {"juvdi", "fendi"}
def eu_jul10(d):
    y = int(d[:4]); s = y if d[5:] >= "07-10" else y - 1
    return f"{s}-{str(s + 1)[2:]}"
def season_of(d, club):
    y = int(d[:4])
    if club in CAL: return str(y)
    if club in JUL10: return eu_jul10(d)
    s = y if int(d[5:7]) >= 8 else y - 1
    return f"{s}-{str(s + 1)[2:]}"
if "--stat" in sys.argv:
    for k, v in ST.items(): print(k, v)
    print(NG, NGo, NA, NPK, MIN_TOT, len(E), NTIE, NTIEG, dict(ELO_SRC))
    print("FotMob", FM_N, FM_CMP)
    for c in CROSS: print(c)
    print(collections.Counter(season_of(m[0], club_of(m[0])) for m in M))
    sys.exit(0)

exec(open(os.path.join(HERE, "note_diego.py"), encoding="utf-8").read())

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
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
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
mm_ = {m[0]: m for m in M}
Gstart = {ldate(g): g["isStarting"] == "True" for g in GAMES}
for r in E:
    m = mm_.get(r[9])
    if m and (m[1] != r[1] or m[2] != r[3]): problems.append(("상대/대회 다름", r[9], r[1], m[1], r[3], m[2]))
    if m and r[4] > m[3] + 3 and not r[10] and Gstart[r[9]]: problems.append(("출전 분보다 늦은 기록", r[9], r[1], r[4], m[3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
open(OUT_JS, "w", encoding="utf-8").write(f"const DIE_E={J(E)};\nconst DIE_M={J(M)};\nconst DIE_NOTE={J(NOTE)};\n")
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS,
           "fotmob_goal_diffs": FM_CMP, "elo_sources": ELO_SRC, "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for k, v in ST.items(): print(" ", k, v)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
