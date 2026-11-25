# 도움 판정 근거: A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). 2014.8 이후 TM 단독 도움은 TM 외 독립 출처 2곳이 있어야 넣음.
# 'Shot on goal'(슈팅 리바운드)·'Penalty: Fouled player'(PK 유도)는 규칙상 빼고(FotMob·ESPN 모두 도움자 없음), 2014.8 전 정상 유형 TM 단독 도움은 넣음.
A_CHECK = {
 # 2021.3.21 FA컵 8강 레스터전 38분 그린우드 골: TM 'Cross', FotMob 이벤트·ESPN 이벤트에는 도움자 없음
 "3537809|38": (True, "TM 단독(FotMob·ESPN 이벤트 도움자 없음)이지만 경기 기사 여러 곳이 포그바의 크로스로 적음: 잉글랜드축구협회(thefa.com) 경기 기사 "
                "'Greenwood ... pounced on Paul Pogba's centre', ESPN 경기 기사 'Greenwood got on the end of a Paul Pogba cross', "
                "Goal.com 'van de Beek's delightful dummy allowed Paul Pogba to set up Mason Greenwood', PA 통신(스포츠몰) 'Paul Pogba found space on the left and his cross was dummied by Donny Van de Beek for Greenwood'"),
}
ADD_A = []
