# 토뱅 빌드 뒷부분(동료·같은 경기 대조, 클럽 합계, 설명, 점검, 출력) — build_thauvin.py가 exec로 읽음. 판정 근거는 judgments.md.

# ---------------------------------------------------------------- 같은 경기 다른 선수 자료 대조(다른 파일은 고치지 않음)
CROSS = []
def cmp_rows(a, b):
    diffs = []
    if abs(a[4] - b[4]) > 2: diffs.append(f"분 {a[4]}/{b[4]}")
    if (a[5], a[6]) != (b[5], b[6]): diffs.append(f"스코어 {a[5]}-{a[6]}/{b[5]}-{b[6]}")
    for i, nm in ((3, "대회"), (2, "Elo"), (12, "lv"), (8, "PK"), (10, "연장"), (7, "단판")):
        if a[i] != b[i]: diffs.append(f"{nm} {a[i]}/{b[i]}")
    ta = a[14] if len(a) > 14 else None; tb = b[14] if len(b) > 14 else None
    if ta != tb: diffs.append(f"합산 {ta}/{tb}")
    return diffs
IS_ME = lambda s: norm(str(s or "")) in ("florian thauvin", "thauvin")
for b, (P, oe, om) in OTHERS.items():
    for r in E:   # 내 도움 → 다른 선수 골
        if r[0] == "a":
            hit = sorted([x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 3 and key(x[1]) == key(r[1]) and (x[5], x[6]) == (r[5], r[6])], key=lambda x: abs(x[4] - r[4]))
            if hit: CROSS.append((f"토뱅 도움→{b} 골", r[9], r[1], r[4], r[13], cmp_rows(r, hit[0]) or "같음"))
    for x in oe:   # 다른 선수 도움 → 내 골
        if x[0] == "a" and IS_ME(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 3], key=lambda r: abs(r[4] - x[4]))
            CROSS.append((f"{b} 도움→토뱅 골", x[9], x[1], x[4], "없음" if not hit else (cmp_rows(hit[0], x) or "같음")))
    for x in oe:   # 같은 경기(같은 상대) 다른 골·도움: Elo·lv·대회·합산
        for r in E:
            if r[9] == x[9] and key(r[1]) == key(x[1]):
                d = [t for t in cmp_rows(r, x) if not t.startswith(("분", "스코어", "PK", "연장"))]
                if d: CROSS.append(("같은 경기 값 다름", b, r[9], r[1], d))
                break
    mm = {(m[0], key(m[1])): m for m in om}
    for m in M:
        o = mm.get((m[0], key(m[1])))
        if o and o[2] != m[2]: CROSS.append(("같은 경기 출전 대회 코드 다름", b, m[0], m[1], m[2], o[2]))
# 이 계산기에 넣지 않은 Transfermarkt 토뱅 도움인데 다른 선수 파일에 그 골이 있는 경우(참고)
for e in EVENTS:
    if e["thauvin_assist_other"] == "1" and e["gameId"] in G:
        d = ldate(G[e["gameId"]]); mi = minute(e["minute"])[0]
        if not any(r[0] == "a" and r[9] == d and abs(r[4] - mi) <= 2 for r in E):
            for b, (P, oe, om) in OTHERS.items():
                if any(x[0] == "g" and x[9] == d and abs(x[4] - mi) <= 2 and key(x[1]) == key(G[e["gameId"]]["opponent"]) for x in oe):
                    CROSS.append(("TM 토뱅 도움을 뺀 골이 다른 파일에 있음", b, d, e["minute"], e["scorer"], e["assist_type"]))
G_CLUBNAME = {ldate(g): g['club'] for g in GAMES}
SHARED = []   # 다른 선수가 같은 날 같은 경기(상대 편 포함)에 기록이 있는 내 행
for r in E:
    for b, x in BYDATE.get(r[9], []):
        if key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1]) or toks(x[1]) & toks(G_CLUBNAME.get(r[9], "")):
            SHARED.append((r[9], r[1], b, x[0], x[1], x[4], x[5], x[6], x[2], x[12]))
if "--cross" in sys.argv:
    for c in CROSS:
        if c[-1] != "같음": print(c)
    print(collections.Counter((c[0].split("→")[0], c[-1] == "같음") for c in CROSS))
    for s in sorted(set(SHARED)): print("같은 날 기록:", s)

# ---------------------------------------------------------------- 클럽·시즌
CLUBS = [("grethv", "2011-07-01"), ("basthv", "2013-09-02"), ("omthv", "2015-08-19"), ("ncthv", "2016-01-31"),
         ("omthv", "2021-07-01"), ("tigthv", "2023-01-31"), ("udithv", "2025-08-08"), ("lenthv", None)]
def club_of(d):
    for k, u in CLUBS:
        if u is None or d < u: return k
CLUB_KO = {"grethv": "그르노블", "basthv": "바스티아", "omthv": "마르세유", "ncthv": "뉴캐슬", "tigthv": "티그레스", "udithv": "우디네세", "lenthv": "랑스"}
TMID = {"1290": "grethv", "595": "basthv", "244": "omthv", "762": "ncthv", "7055": "tigthv", "410": "udithv", "826": "lenthv"}
ST = collections.OrderedDict((k, [0, 0, 0, 0]) for k in CLUB_KO)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
for g in GAMES:
    if club_of(ldate(g)) != TMID[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])

# ---------------------------------------------------------------- 설명(NOTE)
sys.path.insert(0, HERE)
from note_thauvin import make_note
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E); MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["thauvin_assist_other"] == "1")
NOTE = make_note(dict(M=M, E=E, ST=ST, CLUB_KO=CLUB_KO, NG=NG, NGo=NGo, NA=NA, NPK=NPK, MIN_TOT=MIN_TOT, NTIE=NTIE, NTIEG=NTIEG,
                      N_TM_A=N_TM_A, EXCL_CNT=EXCL_CNT, SRC=ELO_SRC, FM_CONF=FM_CONF))
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "GAP", "TM ", "mlp", "elk", "lg"]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE):
        sys.exit("설명에 작업용 표현: " + bad)

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
mopp = {m[0]: m for m in M}
for d, rs in by.items():
    gs = sorted({(r[5], r[6], r[4]) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
    for a, b in zip(gs, gs[1:]):
        if b[0] < a[0] or b[1] < a[1]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
    elif any(key(r[1]) != key(mopp[d][1]) or r[3] != mopp[d][2] for r in rs): problems.append(("상대/대회 M 불일치", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900: problems.append(("Elo 이상", r))
    if r[4] > mopp.get(r[9], [0, 0, 0, 999])[3] + 125: pass
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if len([a for a in sys.argv[1:] if a != "--force"]) == 0:
    open(OUT_JS, "w", encoding="utf-8").write(f"const THV_E={J(E)};\nconst THV_M={J(M)};\nconst THV_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "cross_check": CROSS, "shared_rows": sorted(set(SHARED)),
               "fotmob_assists_not_used": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG, "assist_confirmation": FM_CONF},
              open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE} · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
