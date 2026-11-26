# 아리츠 아두리스: 2014.8 이후 Transfermarkt 단일 출처 도움 판정. A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). 기준: TM 외 독립 출처 2곳(FotMob·ESPN·경기 기사).
# 웹 확인 2026-11-21(WebSearch·curl). FotMob 이벤트는 세 경기 모두 도움자 없음, FotMob 선수 경기 목록은 2016-17부터라 2016.12.22·2017.1.5 경기는 목록에 없음.
A_CHECK = {
 "2618744|90": (False, "유로파 조별 아우크스부르크전 90분 수사에타 골: ESPN만 아두리스 도움. RFEF 기사('tras un gran recorte en el área')·TUDN 기사('gran disparo desde la frontal')·Sports Mole 경기 기사는 수사에타 개인 돌파 골로만 적고 도움자를 적지 않음"),
 "2767523|47": (False, "코파 32강 2차전 라싱 산탄데르전 47분 라울 가르시아 골: ESPN만 아두리스 도움. maxifoot 경기 기록·ESPN 경기 기사 본문에 도움자 없음, 다른 기사 못 찾음"),
 "2810018|28": (True, "코파 16강 1차전 바르셀로나전 28분 이냐키 윌리엄스 골: ESPN(아두리스 도움) + El Tiempo 경기 기사(아두리스의 뒤꿈치 패스) + World Soccer Talk 경기 기사(Aduriz's backheeled layoff)"),
}
ADD_A = []
