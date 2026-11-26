# 도움 판정 근거: A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). 2014.8 이후 TM 단독 도움(FotMob 이벤트·선수 경기 목록에 없음)은 TM 외 독립 출처 2곳이 있어야 넣음(ESPN 경기 기록·경기 기사).
A_CHECK = {
 "2517431|15": (True, "TM + ESPN 경기 기록(Assisted by Toni Kroos) + 경기 기사 FourFourTwo('코로나 골키퍼가 크로스의 프리킥을 잡으러 나왔다가 비운 골문에 라모스가 헤더') · Football España('크로스의 감아 올린 공을 라모스가 헤더')"),
 "2518507|37": (True, "TM + ESPN 경기 기록(Assisted by Toni Kroos) + 경기 기사(SI·FourFourTwo: 왼쪽에서 크로스가 올린 코너킥을 라모스가 헤더)"),
 "2518532|20": (True, "TM + ESPN 경기 기록(Assisted by Toni Kroos) + 경기 기사 Sports Mole 선수 평점('크로스의 프리킥을 라모스가 헤더로 넣음')"),
 "2805576|45+2": (True, "TM + ESPN 경기 기록(Assisted by Toni Kroos) + 경기 기사 Bleacher Report('Toni Kroos produces nutmeg assist for Karim Benzema')·FIFA 경기 기사(크로스의 패스를 벤제마가 바깥발로 넣음)"),
 "2810019|29": (True, "TM + ESPN 경기 기록(Assisted by Toni Kroos) + 경기 기사 Bleacher Report('바란이 토니 크로스의 코너킥을 헤더로 넣음')·Sports Mole(코너킥)"),
 "2594773|62": (False, "TM 단독(FotMob 이벤트·ESPN 경기 기록 모두 도움자 없음). SI 경기 기사는 크로스의 크로스가 굴절된 뒤 벤제마가 오버헤드킥으로 넣었다고 적음 → 독립 출처 2곳 없음·굴절"),
}
ADD_A = []
