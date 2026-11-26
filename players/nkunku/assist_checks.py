# 도움 판정 근거: A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). 2014.8 이후 TM 도움 중 FotMob 이벤트에 없는 것은 TM 외 독립 출처 2곳이 있어야 넣음(ESPN 경기 기록·경기 기사·구단 기사).
A_CHECK = {
 "2770611|57": (True, "TM(크로스) + ESPN 경기 기록(Assisted by Christopher Nkunku) + 경기 기사 beIN Sports(베라티의 패스를 받은 은쿤쿠의 크로스가 먼 쪽 포스트의 루카스에게) · CulturePSG 경기 기록(Lucas 57e, passe décisive de Nkunku)"),
 "3461823|69": (False, "TM·ESPN만 은쿤쿠 도움, FotMob은 하이다라 도움. 맨체스터 유나이티드 구단 경기 기사는 은쿤쿠의 왼쪽 크로스가 굴절된 뒤 매과이어·데 헤아가 처리하지 못한 공을 클라위버르트가 넣었다고 적음 → 굴절·출처 엇갈림으로 뺌"),
 "3601595|45": (True, "TM(패스) + ESPN 경기 기록(Assist by Christopher Nkunku) + RB 라이프치히 구단 경기 기사('역습에서 은쿤쿠가 하이다라에게 연결, 하이다라가 일대일에서 골키퍼를 넘김'). FotMob만 도움자 없음"),
 "3651118|45+1": (True, "TM(패스) + ESPN 경기 기록(Assisted by Christopher Nkunku) + Goal.com 문자 중계(은쿤쿠가 포르스베리에게 내준 공으로 골, '앞선 골에 도움을 더함'). FotMob만 도움자 없음"),
}
ADD_A = []
