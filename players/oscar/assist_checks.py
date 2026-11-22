# 오스카: 2014.8 이후 Transfermarkt 도움 중 FotMob(경기 이벤트·선수 경기 목록)이 확인하지 않는 도움 판정. A_CHECK["경기id|TM 분"] = (넣음 여부, 근거).
# 기준(브리프·v1.161): TM 외 독립 출처 2곳. ESPN 문자 중계는 1곳으로 셈. 웹 확인 2026-11-22(WebSearch·curl). 금지 사이트(fbref·sofascore 등)는 근거로 안 씀.
A_CHECK = {
 "2528144|21": (True, "FA컵 4라운드 브래드퍼드전 21분 케이힐 골: 잉글랜드 축구협회(thefa.com) 경기 기사·Sports Mole 경기 기사 모두 '오스카 코너킥을 케이힐이 니어포스트에서 꺾어 넣음'(ESPN·FotMob은 도움자 비움)"),
 "2835127|43": (True, "슈퍼리그 1라운드 창춘전 43분 엘케손 골: ESPN 문자 중계 오스카 도움 + beIN Sports·FourFourTwo 리뷰('Hulk played the ball into Oscar inside the area, and the former Chelsea midfielder found Elkeson with a back-heel')·SCMP 기사"),
 "2867610|6": (False, "중국 FA컵 8강 2차전 톈진 취안젠전 6분 헐크 골: TM만 도움. Lance 기사는 헐크 5분 선제골만 적고 도움 언급 없음, 다른 출처 없음"),
 "2903770|31": (False, "중국 FA컵 준결승 광저우 헝다전 31분 헐크 골(TM 코너킥): FotMob·ESPN 도움 없음, 기사 확인 못 함"),
 "3033954|7": (False, "AFC 챔스 16강 2차전 가시마전 7분 헐크 골(TM 프리킥): JFA·AFC 기사 '프리킥 뒤 흐른 공(loose ball)을 헐크가 넣음' → 직접 도움 아님, FotMob·ESPN 도움 없음"),
 "3038665|39": (False, "중국 FA컵 8강 베이징 궈안전 39분 차이후이캉 골(TM 프리킥): FotMob 도움 없음, ESPN 경기 없음, 기사 확인 못 함"),
 "3003949|69": (False, "슈퍼리그 톈진 취안젠전 69분 리성룽 골(TM 코너킥): FotMob 이벤트·선수 경기 목록 도움 0, 기사 확인 못 함"),
 "3141481|27": (True, "AFC 챔스 조별 시드니 FC 원정 27분 뤼원쥔 골: ESPN 문자 중계 오스카 도움 + A리그 공식 기사(aleagues.com.au)·AFP 기사(오스카 왼쪽 크로스를 뤼원쥔이 헤더)"),
 "3141481|89": (True, "같은 경기 89분 엘케손 동점골: ESPN 문자 중계 오스카 도움 + A리그 공식 기사·AFP 기사(오스카가 치고 나가 엘케손에게 패스)"),
 "3141483|7": (False, "AFC 챔스 조별 가와사키 원정 7분 헐크 골: ESPN만 오스카 도움. JFA·AFC 기사는 헐크가 자기 진영에서 공을 받아 혼자 치고 나가 골키퍼를 제치고 넣었다고 적음 → 뺌"),
 "3141483|71": (True, "같은 경기 71분 헐크 동점골: ESPN 문자 중계(오스카 크로스) + JFA 경기 기사('Hulk responded to the cross delivered by OSCAR')·AFC 분석 기사('Oscar's cross to head in')"),
 "3156470|66": (False, "슈퍼리그 상하이 더비 66분 왕선차오 골(TM 프리킥): FotMob 이벤트·ESPN 도움 없음(FotMob 선수 목록 도움 2 = 헐크 두 골), 기사 확인 못 함"),
 "3307781|90+2": (True, "AFC 챔스 예선 플레이오프 부리람전 90+2분 아르나우토비치 골: China Daily(HK) 기사('Arnautovic slotting home from Oscar's pass')·Football Tribe 기사(헐크 → 오스카 → 아르나우토비치)"),
 "3548205|47": (False, "슈퍼리그 톈진 진먼후전 47분 히카르두 로페스 골: FotMob(이벤트 도움 없음·선수 목록 도움 4 = 다른 네 골)·ESPN 도움 없음, Planet Football만 '도움 5개' → 출처 1곳이라 뺌"),
 "3689285|15": (True, "중국 FA컵 2021 준결승 1차전 상하이 선화전(5-1): Planet Football 기사('directly assisting four goals', 8분 선제골은 빌드업 관여) + football.london 기사('five goal contributions', 오스카 무득점 경기) → TM 도움 4개(15·24·59·85분)와 맞음. FotMob·ESPN 자료 없음"),
 "3689285|24": (True, "같은 경기 24분 허관 골: 위와 같음(Planet Football '두 번째 도움은 수비 뒤로 띄운 칩 패스')"),
 "3689285|59": (True, "같은 경기 59분 파울리뉴 골: 위와 같음"),
 "3689285|85": (True, "같은 경기 85분 류주룬 골: 위와 같음"),
 "3986245|90+3": (False, "중국 FA컵 2022 청두 룽청전 90+3분 아부라한 골(TM 프리킥): FotMob 도움 없음, ESPN 경기 없음, 기사 확인 못 함"),
 "4054679|45": (False, "슈퍼리그 창저우전 45분 우레이 골: FotMob 이벤트·선수 목록 도움 0, ESPN 도움 없음"),
 "4083843|44": (False, "슈퍼리그 상하이 더비 44분 우레이 골: FotMob 이벤트·ESPN 도움 없음(FotMob 선수 목록 도움 1 = 63분 골), 기사 확인 못 함"),
 "4284198|90+2": (False, "슈퍼리그 우한 싼전전 90+2분 왕선차오 골(TM 코너킥): FotMob 이벤트·ESPN 도움 없음(선수 목록 도움 1 = 75분 골)"),
 "4289591|60": (False, "슈퍼리그 칭다오 하이뉴전 60분 구스타보 골: FotMob 이벤트·선수 목록 도움 0, ESPN 도움 없음"),
 "4284468|54": (False, "슈퍼리그 메이저우전 54분 치타디니 골(TM 코너킥): FotMob 이벤트·ESPN 도움 없음(선수 목록 도움 1 = 67분 골)"),
}
ADD_A = []
