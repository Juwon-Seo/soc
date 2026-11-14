# build_govou.py 뒤쪽(exec): 동료 대조·클럽 합계·설명(NOTE)·§16 점검·출력

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(수정 없음, 보고용)
MATE_NAME = {"bzm.js": "Karim Benzema", "jun.js": "Juninho", "mld.js": "Florent Malouda", "elb.js": "Giovane Élber",
             "gms.js": "Bafétimbi Gomis", "bna.js": "Hatem Ben Arfa"}
ALT = {"Karim Benzema": ("Benzema",), "Juninho": ("Juninho",), "Florent Malouda": ("Malouda",), "Giovane Élber": ("Élber", "Elber"),
       "Bafétimbi Gomis": ("Gomis",), "Hatem Ben Arfa": ("Ben Arfa",)}
def same_vals(a, b): return (a[5], a[6], a[2], a[12], a[3], a[7], a[14:]) == (b[5], b[6], b[2], b[12], b[3], b[7], b[14:])
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and "Govou" in str(x[13]):
            hit = sorted([r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2], key=lambda r: abs(r[4] - x[4]))
            ok = hit and same_vals(hit[0], x)
            cross.append(("동료 도움→고부 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "고부 골 없음"), x[2:8], hit[0][2:8] if hit else None))
    nm = MATE_NAME.get(b)
    if nm:
        for r in E:
            if r[0] == "a" and any(t in r[13] for t in ALT[nm]):
                hit = sorted([x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2], key=lambda x: abs(x[4] - r[4]))
                ok = hit and same_vals(hit[0], r)
                has_m = any(m[0] == r[9] for m in om)
                cross.append(("고부 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else ("동료 골 없음" + ("" if has_m else "(출전 행도 없음)"))), r[2:8], hit[0][2:8] if hit else None))
    for r in E:
        for x in oe:
            if x[9] == r[9] and (key(x[1]) == key(r[1]) or toks(x[1]) & toks(r[1])) and (x[2] != r[2] or x[12] != r[12] or x[3] != r[3]):
                cross.append(("같은 경기 Elo/lv/대회 다름", b, r[9], r[1], (x[2], x[12], x[3]), (r[2], r[12], r[3])))
    for m in M:
        for mm in om:
            if mm[0] == m[0] and (key(mm[1]) == key(m[1]) or toks(mm[1]) & toks(m[1])) and mm[2] != m[2]:
                cross.append(("같은 경기 출전 행 대회 코드 다름", b, m[0], m[1], mm[2], m[2]))
for gid, evs in EVS.items():
    if gid not in G: continue
    for e in evs:
        if e["scorer_id"] == JP and e["own_goal"] != "1" and e["assist_id"] and e["assist_id"] != JP and not e["assist_type"].startswith("Penalty"):
            for b, nm in MATE_NAME.items():
                if b in OTHERS and any(t in e["assist_player"] for t in ALT[nm]):
                    d = ldate(G[gid]); oe, om = OTHERS[b]
                    if not any(x[0] == "a" and x[9] == d and "Govou" in str(x[13]) for x in oe):
                        cross.append(("Transfermarkt 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"] or "(유형 빈칸)",
                                      "출전 행 있음" if any(m[0] == d for m in om) else "출전 행도 없음"))
DUP = set()
cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 클럽별 합계
CLUBS = [("2010-07-03", "리옹"), ("2011-07-05", "파나티나이코스"), ("9999-12-31", "에비앙")]
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
for g in games:
    if club_of(ldate(g)) != PRO_CLUBS[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for _, n in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
TM_A_API = sum(int(g["assists"]) for g in games)
API_G = sum(int(g["goals"]) for g in games); API_PK = sum(int(g["penGoals"]) for g in games)
if (API_G, API_PK) != (NGo, NPK): sys.exit(f"골 합계 불일치 API {API_G}/{API_PK} vs {NGo}/{NPK}")
if TM_A_API != NA + sum(1 for j in judg if j[0] == "도움 제외"): sys.exit(f"도움 합계 불일치 API {TM_A_API} vs {NA}")
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
SAME_N = ELO_SRC["같은 경기 다른 선수 자료"]
ET_G = [r for r in E if r[10]]
EXG = [g for g in EXCL if g["level"].startswith("senior (amateur")]
EXG_G = sum(int(g["goals"]) for g in EXG); EXG_A = sum(int(g["assists"]) for g in EXG)
ATRO = [r for r in E if r[1] == "Atromitos Athens"][0]

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
KO = {"AJ Auxerre": "오세르", "LOSC Lille": "릴"}
NOTE_LINES = [
    f"시드니 고부(리옹·파나티나이코스·에비앙)의 클럽 공식 경기 {NG}경기({d_(first[0])} {KO[first[1]]}전 ~ {d_(last[0])} {KO[last[1]]}전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n} {c3(v)}" for n, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(1군 출전 {NG}경기)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음. 리옹 첫 경기는 Transfermarkt 기준 2000.1.15 오세르전(그 전 1군 출전 기록 없음)",
    "클럽·시즌별 경기·골은 프랑스어 위키백과 클럽 기록 표(리옹 410경기 77골·파나티나이코스 24경기 3골·에비앙 43경기 2골, 대표팀 경기를 뺀 값)와 골은 모두 같음. 리옹 경기 수 2경기 차이(2008.8.2 트로페 데 샹피옹을 위키백과는 컵 경기로 분류하는 등)는 경기별 자료가 있는 Transfermarkt를 씀. 파나티나이코스는 영어 위키백과 24경기 3골과도 같음",
    f"프로 리그 시즌만 셈: 은퇴 전 프로 경력은 2013년 에비앙에서 끝남. 그 뒤 아마추어로 뛴 리옹 2군(2013-14 프랑스 4부 CFA, 2경기 0골 89분, 2군이라 제외), GOAL FC(몽도르 아제르그, 2013-14·2014-15 프랑스 4부 CFA, Transfermarkt {len(EXG)}경기 {EXG_G}골 {EXG_A}도움 — 쿠프 드 프랑스 2경기 2골 포함, 아마추어 리그라 제외), FC 마이애미 시티(2015 미국 4부 USL PDL, Transfermarkt 경기 기록 없음, 프랑스어 위키백과 11경기 3골), FC 리모네스트(2015~17 프랑스 5부, Transfermarkt 출전 0, 프랑스어 위키백과 2경기 2골·영어 위키백과 약 24경기 2골)는 넣지 않음. 리옹 2군 1998~2000(프랑스어 위키백과 34경기 10골)도 뺌. 프랑스어 위키백과 정보 상자 통산 546경기 95골은 이 아마추어·2군 경기를 더한 값이고, 클럽 기록 표(흔히 인용되는 프로 통산)에는 들어 있지 않음",
    "프랑스 대표팀(A 49경기·U-21) 경기는 뺌",
    f"골 {NGo}개 중 PK 0개. 2001.1.20 쿠프 드 프랑스 캉전 67분 2-2 골은 Transfermarkt가 고부의 자책골로 적어 넣지 않음(선수 경기 성적 골 0·자책골 1)",
    "2007.1.20 쿠프 드 프랑스 라옹전: Transfermarkt 리포트 골 목록에 라옹의 19분 골(코프만)이 빠져 있어(최종 1-3과 맞지 않음) ESPN·Eurosport 경기 기록대로 넣고 계산함 → 고부 69분 골은 1-1에서 넣은 골",
    "2010-11 이후 골·도움은 FotMob 경기 기록과 수가 같음. 골 시각 차이: 2012.2.7 쿠프 드 프랑스 렌전 Transfermarkt 72분·FotMob 73분, 2012.2.18 캉전 Transfermarkt 90+3·FotMob 90분 → Transfermarkt 시각을 씀. FotMob에는 2010-11 이전 경기 기록이 없고, 2011.2.26 아트로미토스전(경기 자료 없음)과 2010.10.27 그리스컵 코자니전(대회 기록 없음)은 Transfermarkt만 있음",
    f"도움 {NA}개는 모두 2014년 이전이라 Transfermarkt 리포트 도움(유형이 비어 있는 도움 포함, 단일 출처)을 씀. PK 유도·슈팅 리바운드·상대 자책골 유도로 적힌 도움은 없음. 프랑스어 위키백과 시즌별 도움(클럽 합계 52개)과는 여러 시즌이 다르나 경기별 자료가 없어 대조에 쓰지 않음",
    "2012.11.10 랭스전: Transfermarkt는 18분 베리고 골(0-1)을 고부 도움(패스)으로, 53분 아드난 골(0-2)을 코네 도움으로 적고 FotMob도 아드난 골을 코네 도움으로 적음. 영어 위키백과는 고부가 아드난의 결승골을 도왔다고 적었으나(같은 주 11.7 소쇼전 55분 아드난 골이 고부 크로스) Transfermarkt·FotMob을 따름. 베리고 골은 Sky Sports 경기 기사가 고부의 패스로, maxifoot은 고부 슈팅을 베리고가 방향만 바꾼 골로 적어 서로 다르나 Transfermarkt 도움을 그대로 둠",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(주니뉴·벤제마·말루다·엘베르·벤 아르파·고미스 등) 값을 먼저 쓰고({SAME_N}개 기록), 없으면 기존 선수 자료의 같은 팀·같은 시즌 값, 그다음 그 시즌 최종 순위(Transfermarkt 순위표, 우승 팀·위키백과로 확인)를 기존 리그 모형에 넣음: 마르세유 2001-02 리그1 9위 1704(8위·10위 기존 값의 중간), 이스트르 2004-05 리그1 20위 1582, 로리앙 2002-03 리그2 4위 1582(2002.7.27 트로페 데 샹피옹, 그 시즌 리그2)",
    f"그리스 슈퍼리그 2010-11(리그 수준 추정): 다른 선수 자료와 같은 국가 계수 회귀(리그 평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 국가 계수 평균 − 7.333) + 그리스 보정, 흩어짐 119, 16팀 순위 곡선). 그리스 계수 2009-10 7.900·2010-11 7.600·2011-12 7.600 → 리그 평균 {gr_mean('2010-11'):.0f}. 아트로미토스는 최종 순위 11위(RSSSF·영어 위키백과; Transfermarkt 표는 12위) → {ATRO[2]}",
    "리그 표가 없는 상대는 당시 수준을 추정함: " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED) + ". 레드 스타는 1999-00 나시오날(쿠프 드 프랑스 대진 기사), 방데 퐁트네는 2000-01 CFA·라옹은 2006-07 CFA2(대진표·maxifoot 기사), 코자니는 그리스 3부(그리스컵 기록, 근거 약함)",
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·그리스컵은 16강까지·8강·준결승·결승, 트로페 데 샹피옹은 국내컵 결승, 챔스 2000-01 2차 조별은 조별, 2001-02 UEFA컵 3라운드·16강은 유로파 토너먼트로 계산함. 그리스 슈퍼리그 플레이오프(2~5위 미니 리그, 2011년 5월 2경기 출전)는 리그 경기로 셈",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(챔스·UEFA컵: 원정 다득점·연장 적용; 2002.2.21 UEFA컵 16강 리베레츠 1차전, 2005 챔스 16강 브레멘 1·2차전). 연장 골 {len(ET_G)}개(2006.2.1 쿠프 드 프랑스 아작시오전 113분, 2008.5.24 쿠프 드 프랑스 결승 PSG전 102분 결승골)",
    "시즌은 리옹은 다른 선수 자료와 같이 7월 10일 기준(트로페 데 샹피옹 2002.7.27 = 2002-03, 2007.7.28 = 2007-08), 파나티나이코스·에비앙은 8월 1일 기준",
    "우승 기록은 Transfermarkt 업적 페이지 기준(리그1 7회 2001-02~2007-08, 쿠프 드 프랑스 2007-08, 쿠프 드 라 리그 2000-01, 트로페 데 샹피옹 4회 — Transfermarkt 표기 시즌 그대로). 컨페더레이션스컵 우승 등 대표팀 기록은 뺌",
    "은퇴: 프로 마지막 경기는 2013.3.16 릴전(에비앙). Transfermarkt는 2020.7.1부터 은퇴로 적음",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "df", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elq", "elk", "elg", "lg", "clq", "clg"]:
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
for d, rs in by.items():
    gl = sorted([r for r in rs if r[0] == "g"], key=lambda r: (r[5] + r[6], r[4]))
    for a, b in zip(gl, gl[1:]):
        if b[5] < a[5] + 1 or b[6] < a[6]: problems.append(("스코어 역순", d, a[4], b[4]))
    allr = sorted(rs, key=lambda r: r[4])
    for a, b in zip(allr, allr[1:]):
        if b[5] < a[5] or b[6] < a[6]: problems.append(("시간순 스코어 역행", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 출전 행", d))
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
    mm = [m for m in M if m[0] == r[9]]
    if mm and mm[0][2] != r[3]: problems.append(("기록·출전 대회 코드 다름", r[9]))
    mmm = mm[0][3] if mm else 0
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
js = f"const GOV_E={J(E)};\nconst GOV_M={J(M)};\nconst GOV_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg, "own_goals": own_goals,
           "fm_only_seen": fm_only_seen, "minute_fixes": min_fix, "cross_check": cross, "elo_sources": ELO_SRC,
           "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("분 고침", min_fix, "자책골", own_goals, "도움 제외", judg)
print("리그1 보간", INTERP)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if not (len(c) > 4 and c[4] == "일치"): print("  대조:", c)
print("대조 요약", collections.Counter((c[0], c[1], c[4] if len(c) > 4 and c[0].endswith("골") else "") for c in cross))
