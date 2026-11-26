# 하킴 지예흐 설명(NOTE) 문장. build_ziyech.py가 exec로 읽음(변수: ST·NG·NGo·NA·NPK·MIN_TOT·EXJ·A_STATUS·TM_A·DATE_LOG·ELO_SRC·FM_G·FM_N·NTIE·NTIEG·E·M).
first, last = M[0], M[-1]
OPP_KO = {"De Graafschap Doetinchem": "더 흐라프스합", "AZ Alkmaar": "AZ", "Panathinaikos": "파나티나이코스", "Heracles Almelo": "헤라클레스",
          "Al-Gharafa SC": "알가라파", "Sparta Rotterdam": "스파르타 로테르담", "Juventus FC": "유벤투스", "Samsunspor": "삼순스포르",
          "PSV Eindhoven": "PSV", "FC Utrecht": "위트레흐트", "Chelsea FC": "첼시"}
def jl(j): return f"{d_(j[1])} {OPP_KO.get(j[2], j[2])}전 {j[3]}분 {j[4]}"
def exl(kind): return ", ".join(jl(j) for j in EXJ if j[5].startswith(kind))
def nex(kind): return sum(1 for j in EXJ if j[5].startswith(kind))
FMEV = [a for a in A_STATUS if a[4].startswith("TM+FotMob")]
NOTE_LINES = [
    f"하킴 지예흐(SC 헤이렌베인·FC 트벤테·아약스·첼시·갈라타사라이·알두하일·위다드 카사블랑카·보타포구)의 클럽 공식 경기 {NG}경기({d_(first[0])} 라피드 부쿠레슈티전 ~ {d_(last[0])} 코린치앙스전)에서 나온 {NGo}골 {NA}도움(PK 골 {NPK}개), 친선경기·유소년·2군·모로코 대표팀 제외",
    "클럽별 경기·골·도움: " + ", ".join(f"{k} {c3(v)}" for k, v in ST.items()) + f". 출전 분 합계 {MIN_TOT:,}분",
    "출처: 경기 목록·출전 분은 Transfermarkt 선수 경기 성적, 골 시각·골 순서·PK·도움은 Transfermarkt 경기 리포트(골·도움이 있거나 리그 밖 대회인 경기). 클럽별 경기·골은 영어 위키백과·FotMob과 같음(영어 위키백과 아약스 2018-19 리그 17골은 Transfermarkt·FotMob 16골, 보타포구 6경기는 Transfermarkt·FotMob 7경기를 씀)",
    f"골: {NGo}골 모두 Transfermarkt 기준이고 FotMob 경기 기록과 대조함(수·순서·PK 같음; 2026.5.23 하사니아 아가디르전 PK 골 시각만 FotMob 33분, Transfermarkt 35분을 씀). 2013.12.21 AZ전 45분 골은 FotMob만 지예흐 골로 적고 Transfermarkt·ESPN은 슬라흐베어르 골이라 넣지 않음(영어 위키백과 헤이렌베인 골 수도 Transfermarkt와 같음). 자책골 없음. 2013.12.18 KNVB컵 AZ전 120+3분 골은 연장 골(FotMob 120분). 2026.3.22 CAF 컨페더레이션컵 8강 2차전 사피전 90+7분 프리킥 골은 승부차기 골이 아님",
    f"도움: 2014년 8월 이전은 Transfermarkt 경기 리포트 단일 출처(선례). Transfermarkt 도움 {TM_A}개에서 PK 유도 {nex('PK')}개({exl('PK')}), 슈팅 리바운드('Shot on goal') {nex('슈팅')}개({exl('슈팅')}), 상대 자책골 유도 {nex('상대 자책골')}개({exl('상대 자책골')})를 뺌. 2014년 8월 이후는 Transfermarkt와 FotMob이 같이 적은 도움 {len(FMEV)}개를 넣고, Transfermarkt만 적은 도움은 다른 출처 2곳이 확인한 것만 넣음: 2016.9.21 KNVB컵 빌럼 II전 13분 바조르·25분 더 리흐트 골(ESPN 문자 중계·afc-ajax.info 경기 기록, NOS), 2019.12.1 트벤테전 32분 노아 랑 골(afc-ajax.info·Voetbal International)",
    f"확인 못 해 뺀 도움(Transfermarkt만): {exl('2014.8')}. 2016.3.12 PEC 즈볼러전 55분 카브랄 골과 2017.5.3 유로파 준결승 리옹전 49분 위네스 골은 득점자 슈팅이 굴절된 골(도움 자체는 정상 패스)이고 Transfermarkt·FotMob(리옹전은 ESPN도) 모두 지예흐 도움이라 넣음. FotMob·위키백과의 시즌 도움 합계는 경기별 근거가 없어 쓰지 않음",
    "출전: 출전 분은 Transfermarkt 그대로이나 2025.5.10 카타르컵 결승 알사드전은 연장까지 간 경기(알두하일 구단 경기 기사)라 75분 교체 투입 뒤 45분으로 고침(Transfermarkt 15분, FotMob 54분). 2017.12.20 KNVB컵 트벤테전은 연장 120분(NOS: 1-1 연장 뒤 승부차기, FotMob 90분). 출전 시간 90분 추정 경기는 없음",
    "날짜는 경기 현지 날짜: 보타포구 저녁 경기 3개(2026.10.7 바스쿠 다 가마전·10.28 헤무전·11.18 코린치앙스전)는 Transfermarkt 일정의 UTC 날짜 대신 브라질 날짜, 2025.4.23 카타르컵 준결승 알가라파전은 Gulf Times·The Peninsula·FotMob 날짜(Transfermarkt 4.22)",
    "범위: 헤이렌베인 19세 이하(25경기 1골)·21세 이하 리저브 리그(33경기 14골)는 유소년·2군이라 뺌",
    f"상대 Elo는 같은 경기를 다룬 다른 선수 자료(훈텔라르·베르너·풀리시치·루카쿠·이카르디·메르턴스·벤 예데르 등), 같은 팀·같은 시즌 다른 선수 자료 값, 그 시즌 최종 순위에 맞춘 값 순으로 씀(기록 {len(E)}개: 같은 경기 {ELO_SRC['같은 경기 다른 선수 자료']}, 같은 팀·시즌 {ELO_SRC['기존 팀×시즌 값']}, 순위표 {ELO_SRC['순위표 → 라벨']})",
    "순위 확인: 에레디비시는 Transfermarkt 최종 순위표(2019-20은 코로나로 중단된 시점 순위), 에이르스터 디비시 2014-15 더 흐라프스합 6위, 루마니아 1부 2012-13 라피드 부쿠레슈티 9위, 모로코 1부(보톨라 프로) 2025-26은 우승 MAS 페스 최종 순위(승점이 같은 KACM 9위·COD 메크네스 10위, 제마므라 11위·하사니아 아가디르 12위는 foot-africa 최종 순위표와 득실차 순서). 모로코 1부 리그 수준은 추정(벤 예데르 자료와 같은 기준)",
    "대회 비중: KNVB컵·FA컵·리그컵·카타르 에미르컵·카타르컵은 국내컵(16강까지 낮은 비중, 8강부터 높은 비중·준결승·결승), 요한 크라위프 실드·UEFA 슈퍼컵·튀르키예 슈퍼컵은 국내컵 결승 비중, 클럽 월드컵은 클럽 월드컵 비중, 에레디비시 유럽 대항전 플레이오프는 리그 비중. CAF 컨페더레이션컵(아프리카 대륙 2부 대회)은 따로 비중이 없어 코파 수다메리카나와 같은 대륙 2부 대회 비중(조별 15, 8강 20, 벤 예데르 선례)",
    f"두 경기 합산 기록 {NTIE}개({NTIEG}경기)는 합산 S로 계산함. UEFA 대회는 2020-21까지 원정 다득점, 연장 있음. CAF 컨페더레이션컵 2025-26 8강은 원정 다득점 있고 연장 없음(사피가 합계 3-3에서 원정 다득점으로 올라감, CAF 경기 기사·Ahram). 못 뛴 다른 차전 스코어는 Transfermarkt 리포트",
    "시즌 구분: 아약스는 7월 10일 기준(2017.7.26·2018.7.25 챔스 예선, 2019.7.27 요한 크라위프 실드가 새 시즌), 보타포구는 달력 연도, 나머지는 8월 1일 기준. 클럽 구분(Transfermarkt 이적일): 2014.8.18 트벤테, 2016.8.30 아약스, 2020.7.1 첼시, 2023.8.19 갈라타사라이(임대, 2024.7.1 완전 이적, 같은 클럽), 2025.1.30 알두하일, 2025.10.23 위다드, 2026.9.10 보타포구",
    "우승·수상은 Transfermarkt 업적 페이지 기준. 쉬페르리그 2024-25 우승은 2025.1 이적 전 11경기를 뛰어 Transfermarkt가 넣음(FotMob 업적에는 없음). 2018 '올해의 선수'는 네덜란드 올해의 선수라 수아레스 선례대로 올해의 선수 칸. 2014-15 에레디비시 도움왕을 넣고, 유로파리그 준우승·Transfermarkt 자체 선정 상·21세 이하 리그 우승은 넣지 않음",
    f"현역(보타포구). 2026.11.21 기준 마지막 반영 경기 {d_(last[0])} 브라질 세리에 A 코린치앙스전({last[3]}분)",
]
