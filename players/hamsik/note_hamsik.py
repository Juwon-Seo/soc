# build_hamsik.py에서 exec로 읽음: 설명(NOTE)·일관성 점검·출력
def d_(s): y, m, d = s.split("-"); return f"{int(y)}.{int(m)}.{int(d)}"
def c3(v): return "·".join(map(str, v[:3]))
NG, NGo, NA = len(M), sum(r[0] == "g" for r in E), sum(r[0] == "a" for r in E)
NPK = sum(r[8] for r in E)
MIN_TOT = sum(m[3] for m in M)
NTIE = sum(1 for r in E if len(r) > 14); NTIEG = len({r[9] for r in E if len(r) > 14})
N_TM_A = sum(1 for e in EVENTS if e["gameId"] in G and e["hamsik_assist_other"] == "1")
SRC = ELO_SRC
OPP_KO = {"Chievo Verona": "키에보", "Trabzonspor": "트라브존스포르", "Alanyaspor": "알라니아스포르"}
NOTE_LINES = [
    f"마렉 함식(브레시아·나폴리·다롄 이팡·IFK 예테보리·트라브존스포르)의 클럽 공식 경기 {NG}경기({d_(M[0][0])} 키에보전 ~ {d_(M[-1][0])} 알라니아스포르전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·슬로바키아 대표팀·유소년(슬로반 브라티슬라바 U19·브레시아 프리마베라) 경기 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{CLUB_KO[k]} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    f"출처: 경기 목록·출전 분(연장·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시간·골 뒤 스코어·PK·도움은 Transfermarkt 경기 리포트, 2010-11부터는 FotMob 경기 이벤트와 대조함(FotMob에는 브레시아·나폴리 2007~10 경기 자료가 없고, 나폴리 2010-11 7경기는 FotMob 경기 자료가 비어 있음)",
    "경기·골 수는 영어·이탈리아어·슬로바키아어 위키백과 클럽·시즌·대회별 기록과 모두 같음(슬로반 브라티슬라바 2004-05 제외). 출전 분은 Transfermarkt 그대로(90분 추정 없음)",
    "넣지 않은 기록: 슬로반 브라티슬라바 2004-05(2004년 7~8월) 6경기 1골 — 위키백과·FotMob 합계에만 있고 경기별 자료(날짜·상대·분)가 없어 넣지 않음(위키백과는 슬로바키아 2부, FotMob은 1부로 적어 리그도 엇갈림; Transfermarkt에는 2003-04 슬로반 1군 명단 제외 36경기만 있고 출전 없음). 은퇴 뒤 2025년 상반기 유피에 반스카 비스트리차 등록은 출전 기록 없음",
    "브레시아 2005-06·2006-07은 세리에B(이탈리아 2부, 프로 리그), 2004-05는 세리에A 1경기(2005.3.20 키에보전 25분)",
    "골: Transfermarkt 리포트 145골 그대로. 2010-11 이후 골은 FotMob과 수·스코어·PK 여부가 같음. 다만 2019.6.29 베이징 런허전 52분(1:2) 골은 FotMob 경기 이벤트가 상대 천제 자책골로 적었으나 Transfermarkt·FotMob 선수 경기 기록(골 1)·Sportsmole 경기 기록·위키백과 시즌 합계가 모두 함식 골이라 넣음",
    f"도움: 2014년 8월 전은 Transfermarkt 리포트 도움(FotMob 도움 기록이 2010~14년에 거의 비어 있음), 이후는 Transfermarkt와 FotMob 경기 이벤트가 함께 센 것 + 다른 출처 2곳이 확인한 것. 도움 {NA} = Transfermarkt 리포트 {N_TM_A} − PK 유도 {EXCL['PK 유도']} − 상대 자책골에 준 도움 {EXCL['상대 자책골에 준 도움']}(2013.4.21 칼리아리전 아스토리, 2015.1.6 체세나전 카펠리, 2015.4.19 칼리아리전 발차노, 2015.4.30 엠폴리전 라우리니) − 'Shot on goal'(슈팅 리바운드) {EXCL[chr(39) + 'Shot on goal' + chr(39) + '(슈팅 리바운드)']}(2011.12.11 노바라전 제마일리) − 2014년 8월 이후 확인 못 한 단일 출처 {EXCL['2014.8 이후 단일 출처(확인 못 함)']}",
    "2014년 8월 이후 FotMob에 없어 뺀 Transfermarkt 도움 4개: 2014.11.1 로마전 3분 이과인 골(경기 기사는 인시녜 크로스), 2017.11.21 샤흐타르전(챔스) 56분 인시녜 골(기사는 인시녜 단독 돌파), 2019.6.2 상하이 SIPG전 61분 무셰크위 골(도움자 적은 기사 없음), 2021.9.23 코냐스포르전 1분 코르넬리우스 골(기사가 함식 크로스·바카세타스 연결로 엇갈림)",
    "FotMob에 없지만 다른 출처 2곳이 함식 도움으로 적어 넣은 3개: 2014.8.19 아틀레틱 빌바오전(챔스 예선) 68분 이과인 골(The Siren's Song 경기 기록·경기 기사), 2017.8.22 니스전(챔스 예선) 48분 카예혼 골(Voetbal International·maxifoot 기사), 2021.11.6 베식타시전 45+4분 아브뒬카디르 외뮈르 골(튀르키예 언론 경기 기사 2곳)",
    "FotMob에만 있는 도움 1개(2015.1.6 체세나전 29분 카예혼 골, Transfermarkt 도움 없음)는 넣지 않음. 2014년 8월 전 도움은 Transfermarkt 한 곳 기준이라 하나하나 대조하지 않음(2011.11.29 유벤투스전 40분 판데프 골처럼 FotMob이 다른 선수를 도움으로 적은 것도 Transfermarkt 기준)",
    f"도움 합계 비교: Transfermarkt {N_TM_A}·FotMob 경력 합계 95·이 계산기 {NA}",
    "날짜는 현지 날짜(유럽은 Transfermarkt 리포트 날짜, 중국은 베이징 시간). 2019 중국 FA컵 8강 톈진 톈하이전은 Transfermarkt 2019.7.23이지만 FotMob 경기 시각(베이징 7.24 18시)·CGTN 기사(7.25 '4강 진출')로 2019.7.24로 고침(출전 8분, 기록 없음)",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(카바니·이과인·인시녜·메르턴스·카예혼·제르비뉴 등) 값, 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위를 리그 순위값에 넣은 값, 직접 추정 순으로 씀(기록 {len(E)}개: 같은 경기 {SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {SRC['팀×시즌 통합표']}, 순위+리그 순위값 {SRC['순위+리그 모형']}, 직접 {SRC['직접 추정']})",
    "리그 순위값: 세리에B는 다른 선수 자료의 22팀 순위별 값(5위는 4·6위 값의 가운데), 중국 슈퍼리그 2019·2020은 다른 선수 자료의 2012 순위별 값(같은 모형으로 1~3·8·9위 보충, '추정'), 쉬페르리그 2022-23은 다른 선수 자료와 같은 튀르키예 회귀식(앞뒤 3시즌 UEFA 국가 계수 평균, 흩어짐 119). 중국 슈퍼리그 2020은 조별 1단계 뒤 순위 결정전이 있어 최종 순위(허난 9위)를 씀. 광저우 헝다 2020(최종 2위)은 같은 팀·시즌 다른 선수 자료 값 1540('상위권' 추정)을 그대로 씀",
    "직접 추정(모두 '추정'): 선전 2020(13~16위 결정전, 최종 순위 확인 못 함) 13~16위 값 평균 1416, 블라즈니아 2008-09(알바니아 2위) 1300, 파니오니오스 2008-09(그리스 8위) 1401, 시리우스 2021(스웨덴 11위) 1370, 츠르베나 즈베즈다 2022-23(세르비아 1위) 1580",
    "대회 비중: 코파 이탈리아·중국 FA컵·튀르키예컵은 국내컵(16강까지 낮은 비중, 8강 이후 높은 비중), 수페르코파 이탈리아나·튀르키예 슈퍼컵은 국내컵 결승으로 계산함. 인터토토컵·UEFA컵 예선·UEFA컵 1라운드는 유로파 예선, 유로파 32강(2라운드)·16강·8강은 유로파 토너먼트, 컨퍼런스리그 예선은 컨퍼런스로 계산함",
    f"두 경기 합산(챔스·유로파·UEFA컵·인터토토 토너먼트와 예선, 코파 이탈리아 16강(2005~08)·준결승, 튀르키예컵 준결승) 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. 원정 다득점은 UEFA 대회 2020-21까지, 코파 이탈리아 2021-22까지, 튀르키예컵 2020-21까지(모두 연장 있음). 함식이 뛰지 않은 다른 차전 스코어는 Transfermarkt 경기 리포트로 채움",
    "시즌 구분: 나폴리는 7월 10일 기준(2008.7.20·7.26 인터토토 파니오니오스전 = 2008-09), 트라브존스포르도 7월 10일 기준(2022.7.30 튀르키예 슈퍼컵 = 2022-23), 다롄 이팡·IFK 예테보리는 연도, 브레시아는 8월 1일 기준. 클럽 구분은 2007.7.1 전 브레시아, 2019.2.14 전 나폴리, 2021.3.8 전 다롄, 2021.7.1 전 IFK 예테보리, 이후 트라브존스포르",
    "수상 기록은 Transfermarkt 업적 페이지 기준: 쉬페르리그 2021-22, 코파 이탈리아 2011-12·2013-14, 수페르코파 이탈리아나 2014-15, 튀르키예 슈퍼컵 2022-23, 슬로바키아 올해의 선수 8회(2009·2010·2013~2018). 슬로바키아 대표팀 기록과 올해의 젊은 선수상은 뺌",
    "은퇴(마지막 공식 경기 2023.6.3 알라니아스포르전)",
]
NOTE = "\n".join(NOTE_LINES)
for bad in ["dc", "dk", "dsf", "ko", "OTHER_LEG", "seasonOf", "v1.", "SELFA", "GAP", "TM "]:
    if re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", NOTE):
        sys.exit("설명에 작업용 표현: " + bad)

# ---------------------------------------------------------------- 일관성 점검(§16)
problems = []
seen = set()
for r in E:
    k = (r[0], r[9], r[4], r[5], r[6])
    if k in seen: problems.append(("중복", r))
    seen.add(k)
by = collections.defaultdict(list)
for r in E: by[r[9]].append(r)
mdates = collections.Counter(m[0] for m in M)
mby = {m[0]: m for m in M}
for d, rs in by.items():
    gs = sorted({(r[5], r[6], r[4] if not (r[11] and str(r[11]).startswith("45+")) else 45.5) for r in rs}, key=lambda x: (x[0] + x[1], x[2]))
    for a, b in zip(gs, gs[1:]):
        if b[0] < a[0] or b[1] < a[1] or b[2] < a[2]: problems.append(("스코어 역순", d, a, b))
    if d not in mdates: problems.append(("출전 없음", d))
    else:
        for r in rs:
            if r[3] != mby[d][2] or r[1] != mby[d][1]: problems.append(("상대/대회 M 불일치", r, mby[d]))
for d, c in mdates.items():
    if c > 1: problems.append(("같은 날 출전 2개", d))
for r in E:
    if r[4] > 125 or r[4] < 1: problems.append(("분 범위", r))
    if r[0] == "a" and not r[13]: problems.append(("도움 득점자 없음", r))
    if r[2] < 900 or r[2] > 2100: problems.append(("Elo 이상", r))
for m in M:
    if m[3] < 1 or m[3] > 120: problems.append(("출전 분 범위", m))
if problems:
    for p in problems: print("점검:", p)
    sys.exit(1)

# ---------------------------------------------------------------- 출력
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
if __name__ == "__main__" and len(sys.argv) == 1:
    open(OUT_JS, "w", encoding="utf-8").write(f"const HAM_E={J(E)};\nconst HAM_M={J(M)};\nconst HAM_NOTE={J(NOTE)};\n")
    keys = ["type", "opp", "elo", "comp", "min", "gf", "ga", "ko", "pk", "date", "et", "dm", "lv", "note", "tie"]
    json.dump({"E": [dict(zip(keys, r)) for r in E], "M": M, "note": NOTE, "judgments": judg, "post_gap": POST_LOG, "cross_check": CROSS,
               "fotmob_goal_diffs": FM_CMP, "fotmob_only_assists": FM_ONLY, "elo_sources": ELO_SRC, "elo_log": ELO_LOG,
               "date_fix": DATE_FIX}, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{NG}경기 {NGo}골({NPK} PK) {NA}도움 {MIN_TOT}분 · 기록 {len(E)} · 합산 {NTIE}/{NTIEG}경기 · Elo {dict(ELO_SRC)}")
    for k, v in ST.items(): print(" ", k, v)
