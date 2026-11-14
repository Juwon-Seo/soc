# build_ilicic.py 뒤쪽: 동료 대조·클럽 합계·설명(NOTE)·일관성 점검·출력 (build_ilicic.py가 exec로 읽음)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(수정 없음, 보고용)
MATE_NAME = {"pas.js": ("Javier Pastore", ("Pastore",)), "sal.js": ("Mohamed Salah", ("Salah",)),
             "gom.js": ("Mario Gómez", ("Mario Gómez", "Mario Gomez")), "cua.js": ("Juan Cuadrado", ("Cuadrado",))}
def mate_hit(name, toksx): return any(t in str(name) for t in toksx)
def is_me(n): return "Ilicic" in str(n) or "Iličić" in str(n)
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and is_me(x[13]):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7], hit[0][14:]) == (x[5], x[6], x[2], x[12], x[3], x[7], x[14:])
            cross.append(("동료 도움→일리치치 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "일리치치 골 없음"), x[1:8], hit[0][1:8] if hit else None))
    if b in MATE_NAME:
        nm, tk = MATE_NAME[b]
        for r in E:
            if r[0] == "a" and mate_hit(r[13], tk):
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7], hit[0][14:]) == (r[5], r[6], r[2], r[12], r[3], r[7], r[14:])
                has_m = any(m[0] == r[9] for m in om)
                cross.append(("일리치치 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else ("동료 골 없음" + ("" if has_m else "(출전 행도 없음)"))), r[1:8], hit[0][1:8] if hit else None))
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
        if e["scorer_id"] == JP and e["assist_id"] and not e["assist_type"].startswith("Penalty"):
            for b, (nm, tk) in MATE_NAME.items():
                if b in OTHERS and mate_hit(e["assist_player"], tk):
                    d = ldate(G[gid]); oe, om = OTHERS[b]
                    if not any(x[0] == "a" and x[9] == d and is_me(x[13]) for x in oe):
                        cross.append(("Transfermarkt 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"] or "(유형 빈칸)",
                                      "출전 행 있음" if any(m[0] == d for m in om) else "출전 행도 없음"))
DUP = set()
cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 클럽별 합계
CLUBS = [("2010-07-01", "인터블록"), ("2010-08-27", "마리보르"), ("2013-07-23", "팔레르모"), ("2017-07-05", "피오렌티나"),
         ("2022-10-05", "아탈란타"), ("2025-07-01", "마리보르"), ("9999-12-31", "코페르")]
TMCLUB = {"11006": "인터블록", "790": "마리보르", "458": "팔레르모", "430": "피오렌티나", "800": "아탈란타", "433": "코페르"}
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
for g in games:
    if club_of(ldate(g)) != TMCLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ORDER = ["인터블록", "마리보르", "팔레르모", "피오렌티나", "아탈란타", "코페르"]
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for n in ORDER)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
def mspell(lo, hi):
    v = [0, 0, 0]
    for m in M:
        if lo <= m[0] < hi: v[0] += 1
    for r in E:
        if lo <= r[9] < hi: v[1 if r[0] == "g" else 2] += 1
    return v
MB1, MB2 = mspell("2010-07-01", "2010-08-27"), mspell("2022-10-05", "2025-07-01")
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
TM_A_ALL = sum(1 for gid, evs in EVS.items() if gid in G for e in evs if e["assist_id"] == JP and e["scorer_id"] != JP)
TM_PK = sum(1 for gid, evs in EVS.items() if gid in G for e in evs if e["scorer_id"] == JP and e["penalty"] == "1")
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
SHOT = "슈팅 리바운드('Shot on goal')"; UNC = "2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)"
SLUNC = "슬로베니아 리그 Transfermarkt 단독(경기 기사로 확인 못 함)"
KO_NAME = {"Parma FC": "파르마", "Novara Calcio 1908": "노바라", "US Lecce": "레체", "AC Milan": "밀란", "US Cremonese": "크레모네세",
           "Manchester City": "맨체스터 시티", "Udinese Calcio": "우디네세", "Torino FC": "토리노", "Bologna FC 1909": "볼로냐",
           "US Sassuolo": "사수올로", "ND Gorica": "고리차", "NK Aluminij Kidricevo": "알루미니", "NK Celje": "첼레", "NK Radomlje": "라돔레",
           "NS Mura": "무라", "NK Nafta 1903": "나프타", "NK Brinje Grosuplje": "브리녜", "NK Olimpija Ljubljana": "올림피야"}
def jl(reason):
    return ", ".join(f"{d_(j[1])} {KO_NAME.get(j[2], j[2])}전 {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
SAME_N = ELO_SRC["같은 경기 다른 선수 자료"]
SLO_ADDED = [v for v in post_gap_log if v[7] and v[6] in ("SL1", "SLP")]

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
NOTE_LINES = [
    f"요십 일리치치(인터블록·마리보르·팔레르모·피오렌티나·아탈란타·코페르)의 클럽 공식 경기 {NG}경기({d_(first[0])} 루다르 벨레녜전 ~ {d_(last[0])} 무라전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n} {c3(v)}" for n, v in ST.items()) + f" (마리보르는 2010년 {c3(MB1)}, 2022~2025년 {c3(MB2)}). 출전 분 합계 {MIN_TOT:,}분",
    "현역(코페르): 2026.11.7 무라전까지 반영",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(클럽 공식 경기 {NG}경기)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음. 클럽별 경기·골은 영어 위키백과 시즌별 합계(대회별)와 모두 같음(위키백과 표에 아직 없는 코페르 2026-27 10경기 3골 제외)",
    "보니피카(2007-08, 슬로베니아 2부)의 24경기 3골은 위키백과·FotMob의 시즌 합계만 있고 경기 날짜·상대·출전 시간 기록이 없어 넣지 않음(통산 기록에는 보통 포함되는 시즌). 인터블록(2008-09·2009-10)은 슬로베니아 1부(프로 리그)라서 넣음. 슬로베니아 대표 경기는 뺌",
    "인터블록 2009-10 시즌 끝의 1부 잔류 플레이오프 2경기(2010.5.23·5.30 트리글라우 크란전, 기록 없음)는 리그 비중으로 셈",
    f"골 {NGo}개 중 PK {NPK}개. 2024.8.8 보이보디나전 59분 골은 Transfermarkt가 PK로 적었지만 막힌 PK를 다시 차 넣은 골이라 일반 골로 셈(Transfermarkt PK {TM_PK}개). 2024.3.17 코페르전 38분 PK는 FotMob에 PK 표시가 없지만 경기 기사(siol.net)가 PK 골로 적어 Transfermarkt를 따름",
    "2011.2.6 레체전 62분 골은 FotMob 경기 기록에 없지만 Transfermarkt와 파스토레 자료(도움)를 따름. 2023.8.26 돔잘레전 PK 골은 Transfermarkt 46분, FotMob·경기 기사 기준 전반 추가시간(45+1분)으로 적음",
    "도움은 2014.8.1 이전은 Transfermarkt 리포트 도움을 쓰고, 그 뒤는 Transfermarkt와 FotMob 경기 기록이 같이 적은 도움을 기준으로 함. Transfermarkt에만 있는 도움은 다른 출처 2곳이 확인한 것만 넣음. 다만 슬로베니아 1부(2022~)는 FotMob 경기 기록에 도움 자료가 아예 없어서, Transfermarkt 도움 중 경기 기사(siol.net 라운드 기사 등)가 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 리포트 도움 {TM_A_ALL}개 − 슈팅 리바운드 {EX[SHOT]}개 − PK 유도 {EX['PK 유도']}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 − 2014.8 이후 Transfermarkt에만 있고 다른 출처 2곳으로 확인되지 않은 {EX[UNC]}개 − 슬로베니아 리그에서 경기 기사로 확인되지 않은 {EX[SLUNC]}개",
    "슈팅 리바운드로 뺀 도움: " + jl(SHOT) + ". PK 유도로 뺀 도움: " + jl("PK 유도") + ". 상대 자책골 유도로 뺀 도움: " + jl("상대 자책골 유도"),
    "Transfermarkt에만 있어 뺀 도움: " + jl(UNC) + "(기사는 고메스 단독 돌파 골로 적음). 슬로베니아 리그에서 경기 기사로 확인되지 않아 뺀 도움: " + jl(SLUNC),
    f"슬로베니아 리그 Transfermarkt 도움 중 경기 기사로 확인해 넣은 것은 {len(SLO_ADDED)}개(마리보르 2023~24·코페르 2025~26 경기, 기사에 일리치치의 패스·코너킥·프리킥 뒤 골로 적힘)",
    "FotMob에만 있는 도움(2019.3.10 삼프도리아전 선수 경기 목록, 2019.4.25 피오렌티나전 69분 고메스 골, 2025.7.17 젤레즈니차르전 45+1분 만세리 골)은 넣지 않음",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(FotMob은 2010-11~2013-14 도움 칸이 거의 비어 있고 2010년 이전 슬로베니아 기록이 없음)",
    "날짜는 경기 현지 날짜(모두 유럽 경기, Transfermarkt 리포트 날짜)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(파스토레·살라·콰드라도·고메스 등) 값을 먼저 쓰고({SAME_N}개 기록), 없으면 기존 선수 자료의 같은 팀·같은 시즌 값, 그다음 그 시즌 최종 순위를 리그 순위값에 넣음",
    "슬로베니아 1부 상대는 그 시즌 최종 순위를 슬로베니아 1부 순위값(추정)에 넣음: 기존 선수 자료의 슬로베니아 팀 값(1위 1420, 3위 1400·1360, 4위 1360, 7위·9위 1300)을 바탕으로 1위 1420, 2위 1400, 3위 1380, 4위 1360, 5위 1340, 6위 1320, 7~10위 1300. 같은 팀·시즌 값이 이미 있으면 그 값을 씀(마리보르 2010-11 1420, 올림피야 2023-24 1360). 2026-27은 11월 중순 현재 순위",
    "순위는 공식 최종 순위(승점 같으면 상대 전적 우선): 2008-09 코페르 8위·드라바 9위, 2023-24 무라 6위·돔잘레 7위는 Transfermarkt 표(득실차 순)와 다르게 위키백과·리그 규정 순서를 따름",
    "세리에B 상대(시에나 2013-14 9위)는 기존 선수 자료의 같은 시즌 세리에B 순위값 사이를 보간(7위 1602·13위 1559 → 1588)",
    "순위표에 없거나 하위 리그·외국 리그인 상대는 당시 수준을 추정함(순위는 Transfermarkt 표·위키백과로 확인): " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED),
    "대회 비중: 코파 이탈리아·슬로베니아컵은 16강까지·8강·준결승·결승, 유로파리그 2013-14 2라운드(32강)·32강·16강은 유로파 토너먼트, 2014-15 준결승은 유로파 준결승, 유로파·컨퍼런스 예선과 플레이오프는 예선으로 계산함. 2008-09 슬로베니아컵(Transfermarkt 'N. Matchday' 표기)은 위키백과 대진으로 16강·8강·준결승 두 경기로 나눔",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함: UEFA 대회는 2020-21까지 원정 다득점·연장, 2021-22부터 원정 다득점 없이 연장, 코파 이탈리아 준결승은 원정 다득점·2차전 연장, 2008-09 슬로베니아컵 준결승(1차전 2-2)은 원정 다득점·연장으로 둠(대회 규정 확인 못 함, 추정). 2023.8.3 디페르당주전 결승골은 연장 121분(120+1분) PK",
    "시즌은 인터블록·마리보르·코페르와 팔레르모는 7월 1일 기준(슬로베니아 리그와 유럽 예선이 7월에 시작, 팔레르모 2011.7.28 툰전 = 2011-12), 피오렌티나·아탈란타는 8월 1일 기준",
    "우승 기록은 Transfermarkt 업적 페이지 기준: 슬로베니아 리그 2010-11(마리보르, 시즌 초 8월까지 뛰고 이적), 슬로베니아컵 2008-09(인터블록, 결승은 명단 제외), 2019년 슬로베니아 올해의 선수(Transfermarkt 표기, 아탈란타 시절)",
]
NOTE = "\n".join(l for l in NOTE_LINES if l)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elq", "ecq", "lg", "elk", "mlp"]:
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
    allr = sorted(rs, key=tkey)
    for a, b in zip(allr, allr[1:]):
        if (b[5] < a[5] or b[6] < a[6]): problems.append(("시간순 스코어 역행", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
mm = {m[0]: m for m in M}
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
    if r[9] in mm and (mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]): problems.append(("상대/대회 M 불일치", r[9], r[1], r[3], mm[r[9]][1:3]))
    if r[9] in mm and r[4] > mm[r[9]][3] + 100: pass
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
js = f"const ILI_E={J(E)};\nconst ILI_M={J(M)};\nconst ILI_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg,
           "post_gap_tm_only": post_gap_log, "post_gap_verdicts": POST_GAP, "fm_only_seen": fm_only_seen, "pk_fix": PK_FIX,
           "minute_fixes": min_fix, "cross_check": cross, "elo_sources": ELO_SRC,
           "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("마리보르 1·2기", MB1, MB2)
print("분 고침", min_fix)
print("FotMob 전용", fm_only_seen)
print("제외 사유", dict(EX), "TM 도움", TM_A_ALL, "TM PK", TM_PK)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if not (len(c) > 4 and c[4] == "일치"): print("  대조:", c)
print("대조 요약", collections.Counter((c[0], c[4] if "골" in c[0] else "") for c in cross))
