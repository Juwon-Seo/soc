# 2014.8 이후 Transfermarkt 도움 중 FotMob 경기 이벤트가 확인하지 않는 것, FotMob만 적은 도움: TM 외 다른 출처 2곳 확인 결과.
# 웹 검색·원문 확인 2026-11-21(금지 사이트 미사용). build_icardi.py가 exec로 읽음.
A_CHECK.update({
    a_key("2478729", "19"): (False, "인테르 공식 경기 센터: 나가토모 크로스 → 이카르디 머리 떨궈 주기 뒤 '문전 혼전(mischia in area)'에서 코바치치 골 → 혼전 볼이라 도움 아님(다른 출처 확인 못 함)"),
    a_key("2478822", "47"): (False, "Football Italia 계열 경기 기사: 코바치치의 뒤꿈치 패스를 이카르디가 지켜 낸 뒤 코바치치가 '흐른 공(loose ball)'을 마무리 → 혼전 볼이라 도움 아님, FotMob·ESPN 도움자 없음"),
    a_key("4780422", "80"): (True, "DHA 경기 기사('Sol çaprazdan Icardi'nin ortasında Barış Alper kafayı vurdu') + 하베르튀르크 문자 중계('Icardi arka direğe ortaladı, Barış Alper skoru 2-0 yaptı'), A Spor 중계(gzt 인용)도 같음"),
})
FM_ADD.update({
    "3307466|25": "Maxifoot 경기 기사('Icardi remet de la poitrine en direction de Paredes', 평점 설명 'passe décisive à Paredes') + Omnisport 경기 기사(mykhel 게재: 'Icardi laid Layvin Kurzawa's cross into the path of the Argentina midfielder') + Goal.fr('sur une remise de Mauro Icardi') + PSG 공식 경기 기사",
})
