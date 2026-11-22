# 페르난도 요렌테: 2014.8 이후 Transfermarkt 단일 출처 도움 판정. A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). 기준: TM 외 독립 출처 2곳(FotMob·ESPN은 같은 Opta 계열이면 하나로 봄, 경기 기사).
# 웹 확인 2026-11-22(WebSearch·curl). 세 경기 모두 FotMob 이벤트에 요렌테 도움 없음(FotMob 선수 경기 목록은 2017년부터).
A_CHECK = {
 "2495328|66": (False, "챔스 조별 올림피아코스전 66분 포그바 골: ESPN·FotMob 도움 없음. 로이터 기사는 요렌테 크로스가 포그바에게 갔고 보티아가 뺏을 뻔한 뒤 공이 포그바에게 떨어졌다고 적고, FourFourTwo(PA) 기사는 포그바의 뒤꿈치 시도가 보티아에게 맞고 돌아온 공을 찼다고 적음(흘러나온 공) → 확인 못 함"),
 "2478763|29": (False, "세리에A 나폴리 원정 29분 포그바 골: ESPN만 요렌테 도움. Bleacher Report·Montevideo.com 경기 기사는 테베스 슈팅이 등진 요렌테에게 맞고 뜬 공을 포그바가 발리로 넣었다고 적음(굴절) → 도움 아님"),
 "2528964|89": (True, "코파 이탈리아 8강 파르마 원정 89분 모라타 골: FourFourTwo 경기 기사('latched on to Fernando Llorente's ball') + 유벤투스 구단 기사(알레그리 'Morata did well after latching on to Llorente's nice assist', 경기 기사 'gathered compatriot Fernando Llorente's inch-perfect pass')"),
}
ADD_A = []
