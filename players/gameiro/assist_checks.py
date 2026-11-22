# 케빈 가메이로: 2014.8 이후 Transfermarkt 도움 중 FotMob 경기 이벤트에 도움자가 없는 3개 판정. A_CHECK["경기id|TM 분"] = (넣음 여부, 근거).
# 기준: TM 외 독립 출처 2곳(FotMob·ESPN은 Opta 계열 자료지만 이번 3개는 FotMob 이벤트에 도움자가 없으므로 ESPN + 경기 기사 1곳 이상). 웹 확인 2026-11-22(WebSearch·curl).
A_CHECK = {
 "2518536|64": (True, "코파 델 레이 16강 2차전 그라나다전 64분 데니스 수아레스 골: ESPN 경기 기록(gameId 410785) 가메이로 도움 + Sports Mole 문자 중계('Graneiro[가메이로] picked up the ball inside the area ... lay it off to Suarez alongside him who picked his spot')"),
 "2594711|20": (False, "라리가 라요 원정 20분 이보라 골: ESPN만 가메이로 도움. 라리가 공식 경기 기사('an effort from Kevin Gameiro was pushed away by Juan Carlos, but Vicente Iborra was first to react') = 골키퍼가 막은 슈팅 리바운드 → 도움 아님"),
 "2810016|51": (True, "코파 델 레이 16강 1차전 라스팔마스 원정 51분 그리즈만 골: ESPN 경기 기록(gameId 470815) 가메이로 도움 + FourFourTwo 경기 기사('Vrsaljko's right-wing cross brilliantly picked out Kevin Gameiro at the back post and the Frenchman nodded the ball across the face of goal for his compatriot Griezmann to head into an empty net')"),
}
ADD_A = []
