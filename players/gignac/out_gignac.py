# build_gignac.py 뒤쪽: 동료 대조·클럽 합계·설명(NOTE)·일관성 점검·출력 (build_gignac.py가 exec로 읽음)

# ---------------------------------------------------------------- 같은 경기 동료 자료 대조(수정 없음, 보고용)
MATE_NAME = {"pay.js": ("Dimitri Payet", ("Payet",)), "vab.js": ("Mathieu Valbuena", ("Valbuena",))}
def mate_hit(name, toksx): return any(t in str(name) for t in toksx)
cross = []
for b, (oe, om) in OTHERS.items():
    for x in oe:
        if x[0] == "a" and x[13] and "Gignac" in str(x[13]):
            hit = [r for r in E if r[0] == "g" and r[9] == x[9] and abs(r[4] - x[4]) <= 2]
            ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7], hit[0][14:]) == (x[5], x[6], x[2], x[12], x[3], x[7], x[14:])
            cross.append(("동료 도움→지냑 골", b, x[9], x[4], "일치" if ok else ("값 다름" if hit else "지냑 골 없음"), x[1:8], hit[0][1:8] if hit else None))
    if b in MATE_NAME:
        nm, tk = MATE_NAME[b]
        for r in E:
            if r[0] == "a" and mate_hit(r[13], tk):
                hit = [x for x in oe if x[0] == "g" and x[9] == r[9] and abs(x[4] - r[4]) <= 2]
                ok = hit and (hit[0][5], hit[0][6], hit[0][2], hit[0][12], hit[0][3], hit[0][7], hit[0][14:]) == (r[5], r[6], r[2], r[12], r[3], r[7], r[14:])
                has_m = any(m[0] == r[9] for m in om)
                cross.append(("지냑 도움→동료 골", b, r[9], r[4], "일치" if ok else ("값 다름" if hit else ("동료 골 없음" + ("" if has_m else "(출전 행도 없음)"))), r[1:8], hit[0][1:8] if hit else None))
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
                    if not any(x[0] == "a" and x[9] == d and "Gignac" in str(x[13]) for x in oe):
                        cross.append(("Transfermarkt 동료 도움이 동료 파일에 없음", b, d, e["minute"], e["assist_type"] or "(유형 빈칸)",
                                      "출전 행 있음" if any(m[0] == d for m in om) else "출전 행도 없음"))
DUP = set()
cross = [c for c in cross if not (str(c) in DUP or DUP.add(str(c)))]

# ---------------------------------------------------------------- 클럽별 합계
CLUBS = [("2007-07-01", "로리앙"), ("2010-08-20", "툴루즈"), ("2015-07-01", "마르세유"), ("9999-12-31", "티그레스 UANL")]
TMCLUB = {"1158": "로리앙", "415": "툴루즈", "244": "마르세유", "7055": "티그레스 UANL"}
def club_of(d):
    for u, n in CLUBS:
        if d < u: return n
for g in games:
    if club_of(ldate(g)) != TMCLUB[g["club_id"]]: sys.exit("클럽 경계 불일치 " + g["gameId"])
ST = collections.OrderedDict((n, [0, 0, 0, 0]) for _, n in CLUBS)
for m in M: ST[club_of(m[0])][0] += 1; ST[club_of(m[0])][3] += m[3]
for r in E: ST[club_of(r[9])][1 if r[0] == "g" else 2] += 1
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E if r[0] == "g")
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
PRE_A = sum(1 for r in E if r[0] == "a" and r[9] < GAP)
TM_A_ALL = sum(1 for gid, evs in EVS.items() if gid in G for e in evs if e["assist_id"] == JP and e["scorer_id"] != JP)
PAU_N = len(PAU_G); PAU_GO = sum(int(g["goals"] or 0) for g in PAU_G); PAU_A = sum(int(g["assists"] or 0) for g in PAU_G)
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return f"{v[0]}·{v[1]}·{v[2]}"
EX = collections.Counter(j[5] for j in judg if j[0] == "도움 제외")
SHOT = "슈팅 리바운드('Shot on goal')"; UNC = "2014.8 이후 Transfermarkt 단일 출처(다른 출처 2곳 확인 못 함)"
KO_NAME = {"Le Mans Union Club 72": "르망", "Grenoble Foot 38": "그르노블", "Stade Brestois 29": "브레스트", "AC Arles-Avignon": "아를아비뇽",
           "Chiapas FC (- 2017)": "치아파스", "Deportivo Toluca": "톨루카", "CF America": "아메리카", "CF América": "아메리카", "CD Cruz Azul": "크루스 아술",
           "CF Monterrey": "몬테레이", "UNAM Pumas": "푸마스", "Club Tijuana": "티후아나", "Monarcas Morelia": "모렐리아", "Club Necaxa": "네캑사",
           "Santos Laguna": "산토스 라구나", "CD Olimpia": "올림피아",
           "CF Pachuca": "파추카", "Club León FC": "레온", "Tiburones Rojos de Veracruz": "베라크루스", "Deportivo Guadalajara": "과달라하라",
           "Puebla FC": "푸에블라", "Lobos BUAP (- 2019)": "로보스 BUAP", "Alianza FC": "알리안사", "New York City FC": "뉴욕 시티"}
def jl(reason):
    return ", ".join(f"{d_(j[1])} {KO_NAME.get(j[2], j[2])}전 {j[3]}분 {j[4]}" for j in judg if j[0] == "도움 제외" and j[5] == reason)
MAN_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "man"}, key=lambda t: t[0])
OVR_USED = sorted({(o, v[1], v[2]) for (o, d), v in ELO_LOG.items() if v[0] == "ovr"}, key=lambda t: t[0])
SAME_N = ELO_SRC["같은 경기 다른 선수 자료"]
ADDED = [(d_(v[1]), KO_NAME.get(v[2], v[2]), v[3], v[4], v[6]) for v in post_gap_log if v[6]]

# ---------------------------------------------------------------- 설명(NOTE)
first, last = M[0], M[-1]
NOTE_LINES = [
    f"앙드레피에르 지냑(로리앙·툴루즈·마르세유·티그레스 UANL)의 클럽 공식 경기 {NG}경기({d_(first[0])} 샤토루전 ~ {d_(last[0])} 톨루카전)에서 나온 {NGo}골 {NA}도움, 친선경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{n} {c3(v)}" for n, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"경기·출전 분·골 시간·골 뒤 스코어·PK는 Transfermarkt 선수 경기 성적(클럽 공식 경기 825경기)과 경기 리포트 기준. 출전 시간 90분 추정 경기는 없음",
    f"포 FC 임대(2005-06, 프랑스 3부 내셔널)는 프로 리그가 아니라서 그 시즌 {PAU_N}경기 {PAU_GO}골 {PAU_A}도움(Transfermarkt)을 모두 뺌. 2026년 9월에 들어간 몬테레이 아마추어 리그 팀(베나라미 FC) 경기도 기록이 없고 아마추어라 넣지 않음. 프랑스 대표·올림픽 대표 경기는 뺌",
    "은퇴: 마지막 공식 경기는 2026.5.30 북중미 챔피언스컵 결승 톨루카전(42분, 승부차기 패). Transfermarkt는 2026.7.1부터 무소속, FotMob 경력은 티그레스 2026.6.30까지",
    "클럽별 경기·골은 영어·프랑스어 위키백과 합계와 같음(로리앙 54·11, 마르세유 188·77, 티그레스 445·222). 다만 위키백과는 툴루즈 2010-11에 2경기 1골을 적지만 Transfermarkt는 1경기(2010.8.7 브레스트전, 골 없음)뿐이고 그 골을 경기 단위로 찾지 못해 넣지 않음(툴루즈 위키백과 119경기 42골 vs 이 계산기 118경기 41골). FotMob 경력은 마르세유 188·77, 티그레스 445·222로 같음",
    f"골 {NGo}개 중 PK {NPK}개. 2022.7.23 아틀라스전 45+1분 골은 Transfermarkt만 PK로 적고 FotMob·Sportsmole 문자중계는 코르도바 도움의 일반 골이라 일반 골로 셈(Transfermarkt PK 48개 중 하나)",
    "2022.2.6 마사틀란전(4-3)은 Transfermarkt 리포트 골 목록 순서가 어긋나 있어(78분 곤살레스 골이 맨 앞에 121분으로 적힘) FotMob 순서로 골 직전 스코어를 정함: 11분 비곤 골 도움 0-0, 76분 PK 골 2-2. 2024.4.13 몬테레이전(3-3)도 45+2분 고리아란 골이 46분 브루네타 골보다 먼저라 브루네타 골 도움을 2-1에서 셈",
    "도움은 2014.8.1 이전은 Transfermarkt 리포트 도움을 쓰고, 그 뒤는 Transfermarkt와 FotMob 경기 기록(또는 FotMob 선수 경기 목록)이 같이 적은 도움을 기준으로 함. Transfermarkt에만 있는 도움은 다른 출처 2곳(경기 기사·문자중계·득점 기록)이 확인한 것만 넣음",
    f"도움 {NA}개 = Transfermarkt 리포트 도움 {TM_A_ALL}개(포 FC 0개) − 슈팅 리바운드 {EX[SHOT]}개 − PK 유도 {EX['PK 유도']}개 − 상대 자책골 유도 {EX['상대 자책골 유도']}개 − 2014.8 이후 Transfermarkt에만 있고 확인되지 않은 {EX[UNC]}개",
    "슈팅 리바운드로 뺀 도움: " + jl(SHOT) + ". PK 유도로 뺀 도움: " + jl("PK 유도") + ". 상대 자책골 유도로 뺀 도움: " + jl("상대 자책골 유도"),
    "2014.8 이후 Transfermarkt에만 있어 뺀 도움(다른 출처 2곳을 찾지 못함): " + jl(UNC),
    "2014.8 이후 FotMob 경기 기록에 도움이 없지만 다른 출처 2곳으로 확인해 넣은 도움: " + ", ".join(f"{a}전 {c}분 {d}" for a, b, c, d, e in [(f'{x[0]} {x[1]}', 0, x[2], x[3], x[4]) for x in ADDED]),
    "2020.12.15 북중미 챔스 뉴욕 시티전 85분 아키노 골 도움은 FotMob 경기 기록 도움 칸이 비었지만 FotMob 선수 경기 목록이 도움 1로 적어 넣음. FotMob에만 있는 도움(2021.10.20 파추카전 49분 비곤 골)은 넣지 않음",
    f"2014.8.1 이전 도움 {PRE_A}개는 Transfermarkt 단일 출처(FotMob은 2010-11~2013-14 도움 칸이 거의 비어 있고 2010년 이전 기록이 없음)",
    "날짜는 경기 현지 날짜. 티그레스 경기는 Transfermarkt UTC 시각을 경기장 시간대로 바꿈(멕시코 저녁 경기는 리포트 날짜보다 하루 앞). Transfermarkt 시각이 00:00(자리표시)인 경기는 FotMob 시각을 씀(2017.1.21 아메리카전: Transfermarkt 변환 1.20 → FotMob 1.21, 경기 기사도 토요일 1.21). 2015.12.6 리길야 준결승 2차전 톨루카전은 Transfermarkt가 2015.11.6로 잘못 적어 고침",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(파예·발부에나 등) 값을 먼저 쓰고({SAME_N}개 기록), 없으면 기존 선수 자료의 같은 팀·같은 시즌 값, 그다음 그 시즌 최종 순위를 기존 리그 순위값에 넣음",
    "리가MX 상대는 그 시즌(7월~이듬해 6월) 아페르투라·클라우수라 정규리그 표(FotMob)의 승점·득실차·다득점을 합친 누적 순위를 기존 리가MX 순위값(호나우지뉴·카모라네시·로이스 자료, 빈 순위는 이웃 값의 가운데; 18팀 1위 1789 ~ 18위 1503)에 넣음. 19팀인 2019-20은 같은 표를 19칸으로 보간. 공식 통합 순위표는 아님(클루브 아메리카 2016-17 누적 6위는 다른 선수 자료와 같음). 리가MX 상대가 낸 북중미 챔스·리그스컵·캄페온 데 캄페오네스 경기도 경기 날짜의 리가MX 시즌 누적 순위를 씀",
    ("같은 팀·같은 시즌에 다른 선수 자료가 이미 쓴 값이 있어 그 값을 그대로 쓴 리가MX 상대: " + ", ".join(f"{o} {e}({lv})" for o, e, lv in OVR_USED)) if OVR_USED else "",
    "순위표에 없거나 하위 리그·외국 리그인 상대는 당시 수준을 추정함(순위가 확인된 것 외에는 '추정'): " + ", ".join(f"{o} {e}({lv})" for o, e, lv in MAN_USED),
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·코파 MX(조별)는 16강까지·8강·준결승·결승, 캄페온 데 캄페오네스·수페르코파 MX·캄페오네스컵은 국내컵 결승, 멕시코 리길야는 MLS 플레이오프(8강·리길야 진출전, 준결승, 결승), 북중미 챔스는 16강까지·8강·준결승·결승, 리그스컵은 조별·토너먼트, 리베르타도레스 2015 준결승·결승, 클럽 월드컵 2020(2021.2 카타르), UEFA컵 2007-08 1라운드는 유로파 예선으로 계산함",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함: UEFA 대회 원정 다득점·연장, 북중미 챔스 2023년까지 원정 다득점·연장 없음·2024년부터 원정 다득점 뒤 연장, 리베르타도레스 2015 준결승 원정 다득점·연장 없음, 멕시코 리길야 8강·준결승은 원정 다득점·연장 없음(실제 규정은 합산 동률이면 정규리그 상위 팀 진출), 리길야 결승은 연장·승부차기",
    "시즌은 티그레스는 7월 1일 기준(아페르투라가 7월 초에 시작: 2022.7.2·2024.7.6 개막전 = 새 시즌, 2023.6.25 캄페온 데 캄페오네스·2024.6.30 수페르코파 = 앞 시즌, 2015.7 리베르타도레스 = 2015-16), 로리앙·툴루즈·마르세유는 8월 1일 기준",
    "우승 기록은 Transfermarkt 업적 페이지 기준: 리가MX 아페르투라 2015·2016·2017과 클라우수라 2019·2023은 리그 우승, 캄페온 데 캄페오네스(2016-17·2017-18·2022-23)는 국내 슈퍼컵, 쿠프 드 라 리그 2010-11·2011-12(마르세유), 북중미 챔스 2020·캄페오네스컵 2회는 그 밖의 우승. 북중미 챔스 2020 최우수 선수상은 들어갈 항목이 없어 넣지 않음",
]
NOTE = "\n".join(l for l in NOTE_LINES if l)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM ", "elq", "lg", "mlp", "ccc", "lcg", "lck"]:
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
        if (b[5] < a[5] or b[6] < a[6]) and not (a[11] and str(a[11]).startswith("45+")): problems.append(("시간순 스코어 역행", d, a[4], b[4]))
    if d not in mdates: problems.append(("출전 없음", d))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 두 경기", d))
mm = {m[0]: m for m in M}
for r in E:
    if r[4] > 130 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2200: problems.append(("Elo 범위", r))
    if r[9] in mm and (mm[r[9]][1] != r[1] or mm[r[9]][2] != r[3]): problems.append(("상대/대회 M 불일치", r[9], r[1], r[3], mm[r[9]][1:3]))
for m in M:
    if not (0 < m[3] <= 125): problems.append(("출전 분 범위", m))

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
js = f"const GNC_E={J(E)};\nconst GNC_M={J(M)};\nconst GNC_NOTE={J(NOTE)};\n"
open(OUT_JS, "w", encoding="utf-8").write(js)
keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "assist_judgments": judg,
           "post_gap_tm_only": post_gap_log, "post_gap_verdicts": POST_GAP, "fm_only_seen": fm_only_seen, "pk_fix": PK_FIX,
           "fm_goal_diff": fm_goal_diff, "date_changes": DATE_LOG, "date_fix": DATE_FIX, "pau_excluded": [[g["date_local"], g["opponent"], g["competitionId"], g["playedMinutes"], g["goals"], g["assists"]] for g in PAU_G],
           "minute_fixes": min_fix, "cross_check": cross, "elo_sources": ELO_SRC,
           "elo_log": {f"{o}|{d}": v for (o, d), v in ELO_LOG.items()}},
          open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{NG}경기 {NGo}골(PK {NPK}) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}행/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
for n, v in ST.items(): print(" ", n, v)
print("날짜 바꿈", DATE_LOG)
print("분 고침", min_fix)
print("FotMob 전용", fm_only_seen)
print("FotMob PK 차이", fm_goal_diff)
print("점검 문제", len(problems))
for p_ in problems: print("  ", p_)
for c in cross:
    if not (len(c) > 4 and c[4] == "일치"): print("  대조:", c)
print("대조 요약", collections.Counter((c[0], c[4] if c[0].endswith("골") else "") for c in cross))
