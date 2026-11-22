# 케빈 가메이로 설명(NOTE) 문장. build_gameiro.py가 exec로 읽음(변수: ST·NG·NGo·NA·NPK·MIN_TOT·EXJ·A_STATUS·TM_A·ELO_SRC·FM_G·FM_N·NTIE·NTIEG·NEW_TS·E·M·G).
first, last = M[0], M[-1]
OPP_KO = {"Le Mans Union Club 72": "르망", "Grenoble Foot 38": "그르노블", "OGC Nice": "니스", "RC Lens": "랑스", "SM Caen": "캉", "Granada CF": "그라나다",
          "Borussia Mönchengladbach": "묀헨글라트바흐", "Rayo Vallecano": "라요 바예카노", "Getafe CF": "헤타페", "ESTAC Troyes": "트루아", "Stade Rennais FC": "렌",
          "UD Las Palmas": "라스팔마스"}
SC_KO = {"Christophe Jallet": "잘레", "Fabrice Abriel": "아브리엘", "Marama Vahirua": "바이루아", "Morgan Amalfitano": "아말피타노", "Nenê": "네네",
         "Diego Maínz": "디에고 마인스(그라나다)", "Gerard Deulofeu": "데울로페우", "Éver Banega": "바네가", "Vicente Iborra": "이보라", "Dani Parejo": "파레호",
         "Habib Diallo": "하비브 디알로", "Denis Suárez": "데니스 수아레스", "Antoine Griezmann": "그리즈만"}
def jl(j): return f"{d_(j[1])} {OPP_KO.get(j[2], j[2])}전 {j[3]}분 {SC_KO.get(j[4], j[4])} 골"
def exl(kind): return ", ".join(jl(j) for j in EXJ if j[5].startswith(kind))
def nex(kind): return sum(1 for j in EXJ if j[5].startswith(kind))
NEWL = sorted({(o, lv, e) for (o, s_), (e, lv) in NEW_TS.items()}, key=lambda t: t[1])
NOTE_LINES = [
    f"케빈 가메이로(RC 스트라스부르·FC 로리앙·파리 생제르맹·세비야·아틀레티코 마드리드·발렌시아·RC 스트라스부르)의 클럽 공식 경기 {NG}경기({d_(first[0])} 파리 생제르맹 원정 ~ {d_(last[0])} 메스전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·프랑스 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{k} {c3(v)}" for k, v in ST.items())
    + f". 출전 분 합계 {MIN_TOT:,}분(90분 추정 경기 없음)",
    "제외한 시즌: 스트라스부르 2군 2004-05(CFA = 4부, 아마추어 리그·2군, 영어 위키백과 서술 20경기 4골, Transfermarkt 경기 기록 없음). "
    "경기·골 수는 Transfermarkt와 영어 위키백과 시즌별 표가 모두 같음(세비야 2013-14 유럽 대회만 위키백과 12경기·Transfermarkt 13경기: 2013.8.22 유로파 예선 플레이오프 1차전 실롱스크 브로츠와프전 90분 1골을 Transfermarkt대로 넣음). "
    "프랑스어 위키백과는 715경기 239골(발렌시아 2018-19 코파 델 레이 2골)로 아래 2019.1.8 스포르팅 히혼전 골 1개가 다름",
    "출처: 경기 목록·출전 분(교체·퇴장 반영)은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(7경기는 Transfermarkt 경기 자료 API, 리포트와 같은 내용). "
    f"2010-11 이후 골 {FM_G}개({FM_N}경기)는 FotMob 경기 기록과 대조해 수·순서·PK가 같음(아래 1골 제외, FotMob 자료가 빈 2010-11 로리앙 13경기는 ESPN과 대조). 2010-11 전 골은 ESPN 경기 기록과 대조(ESPN 자료가 없는 3경기는 위키백과 시즌별 골 수와 같음)",
    "2019.1.8 코파 델 레이 16강 1차전 스포르팅 히혼 원정 45분 골: FotMob·스카이스포츠·Sports Mole은 파레호 골, Transfermarkt·ESPN·Sporting Life·영어 위키백과 2018-19 발렌시아 시즌 문서는 가메이로 골 → 가메이로 골로 셈",
    f"도움: Transfermarkt 도움 {TM_A}개에서 PK 유도 {nex('PK')}개({exl('PK')}), 슈팅 리바운드('Shot on goal') {nex('슈팅')}개({exl('슈팅')}), 상대 자책골 유도 1개({exl('상대 자책골')})를 뺌. "
    "Transfermarkt가 본인 PK 골에 본인 도움으로 적은 2개(2015.10.24 헤타페전 60분, 2017.2.21 레버쿠젠 원정 59분)는 도움이 아님. 2014년 8월 전 도움은 Transfermarkt 기록을 씀(FotMob 경기 기록이 없는 2010-11 전 포함, 유형 칸이 빈 2개(2006.12.16 오스트발트전·2013.1.6 아라스전)는 일반 도움으로 셈). "
    "2014년 8월 이후는 Transfermarkt와 FotMob 경기 기록이 같이 적은 것을 셈",
    "Transfermarkt에만 있어 다른 출처 2곳으로 확인해 넣은 도움: 2015.1.14 코파 델 레이 그라나다전 64분 데니스 수아레스 골(ESPN·Sports Mole 문자 중계), 2017.1.3 코파 델 레이 라스팔마스 원정 51분 그리즈만 골(ESPN·FourFourTwo 경기 기사, 헤더 패스). "
    "뺀 도움: 2016.2.21 라요 바예카노 원정 20분 이보라 골(Transfermarkt·ESPN, 라리가 공식 기사는 가메이로 슈팅을 골키퍼가 막은 리바운드)",
    "FotMob이 2017.12.30 알아흘리전 3골을 적었으나 친선경기라 넣지 않음. PK: 2022.10.23 툴루즈전 73분 골은 PK가 막힌 뒤 리바운드 골이라 일반 골",
    "날짜는 경기 현지 날짜(Transfermarkt 일정과 모두 같음)",
    "상대 Elo는 같은 경기를 다룬 다른 선수 자료 값(그리즈만·레예스·메넨·파스토레·라베치·이브라히모비치·요렌테 등), 같은 팀·같은 시즌 기존 값, 그 시즌 순위를 순위 규칙(리그·시즌 기준 평균 + 흩어짐 × 순위 곡선)에 넣은 값 순으로 씀"
    + f" (기록 {len(E)}개: " + ", ".join(f"{k} {v}" for k, v in ELO_SRC.items()) + ")",
    "새로 정한 팀-시즌 순위: " + ", ".join(f"{o} {lv.split(' (')[0]} {e}" for o, lv, e in NEWL)
    + ". 쿠프 드 프랑스 아마추어 상대의 단계·순위는 프랑스어 위키백과 대회·리그 시즌 문서: 가젤렉 아작시오(CFA B조), US 알랑송(CFA 2 G조), 아부안 시농(National 2 B조)은 리그 수준 추정, "
    "FC 오스트발트 2006-07은 '디스트릭트' 리그(알자스 지역 리그 아래)라 9부로 보고 순위 없이 그 단계 기준값(추정)",
    "대회 비중: 쿠프 드 프랑스·쿠프 드 라 리그·코파 델 레이는 국내컵(16강까지·8강·준결승·결승), 수페르코파 2019-20 준결승(단판)은 국내컵 준결승, UEFA 슈퍼컵 2015는 국내컵 결승 비중, "
    "유로파 예선(2011 플레이오프·2013 플레이오프)은 예선, UEFA컵 2005-06 조별·32강과 유로파 32강~8강은 조별·토너먼트, 준결승·결승은 단계별",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함(UEFA 대회·코파 델 레이 2018-19까지 원정 다득점·연장; 코파 델 레이 2019-20은 단판). 다른 차전 스코어는 Transfermarkt 리포트",
    "연장 골: 2009.1.24 쿠프 드 프랑스 투르전 108분(연장). 나머지 연장·승부차기 경기의 골·도움은 정규시간",
    "시즌 구분: 8월 1일 기준(7월 경기 없음). 클럽 구분은 Transfermarkt 이적일(2008.7.1 로리앙, 2011.7.1 PSG, 2013.7.25 세비야, 2016.7.30 아틀레티코, 2018.8.12 발렌시아, 2021.7.18 스트라스부르)",
    "동료 자료 대조: 그리즈만·디에구 코스타·토레스·레예스·이브라히모비치·메넨·파스토레·라베치·마린·아스파스 자료와 같은 경기의 대회·상대 Elo가 같고, 서로 주고받은 골·도움의 날짜·분·스코어가 같음",
    "우승·수상 기록은 Transfermarkt 업적 페이지와 프랑스어 위키백과 UNFP 시상 문서 기준(준우승·대표팀 기록 제외)",
    f"은퇴(2025.3.16 발표, 2024.7 이후 무소속). 마지막 클럽 경기 {d_(last[0])} 리그1 메스전",
]
