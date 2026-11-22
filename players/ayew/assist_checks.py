# 앙드레 아유: 2014.8 이후 Transfermarkt 도움 중 FotMob 경기 이벤트에 도움자가 없는 4개, FotMob에만 있는 도움 1개 판정.
# A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). 기준: TM 외 독립 출처 2곳(FotMob·ESPN은 같은 Opta 계열이라 한 곳). 웹 확인 2026-11-22(WebSearch·curl).
A_CHECK = {
 "2927238|90+4": (False, "리그컵 3라운드 볼턴전 90+4분 마수아쿠 골: TM(유형 없음)·ESPN 기록만 아유 도움. 런던 스타디움·westhamunitedblog·ESPN(PA) 기사는 마수아쿠의 25야드 중거리 슛만 적고 패스한 선수를 적지 않음 → 다른 출처 2곳 확인 못 함"),
 "3069736|57": (True, "쉬페르리그 카이세리스포르전 57분 슬리마니 골: TM(크로스) + A Spor 경기 문자 중계('57'nci dakikada sağ kanattan gelişen Fenerbahçe atağında Ayew sol ayağının dışıyla topu içeri çevirdi', 슬리마니가 돌아서며 슛) + Starr FM 기사('set up Islam Slimani with a perfect ball from the right'). FotMob·ESPN은 도움자 없음"),
 "3640091|68": (False, "카타르 리그 알코르 원정 68분 아피프 골: TM만 아유 도움(유형 없음). 알사드 구단 기사는 '아피프가 30야드 밖에서 강한 슛'으로만 적고, 카타르 리그(QSL)·페닌술라 기사도 도움자 없음 → 확인 못 함"),
 "3878216|90+2": (False, "카타르 리그 알마르키야전 90+2분 카소를라 골: TM만 아유 도움(유형 없음). 알사드 구단·QSL 기사에 도움자 없음 → 확인 못 함(카소를라 자료도 도움자 없음)"),
}
# FotMob에만 있는 도움: 2017.9.11 허더즈필드전 72분 오비앙 골(굴절 골) — 텔레그래프 문자 중계는 '아유가 오비앙에게 연결', KUMB 기사는 '쿠야테가 공을 빼앗아 오비앙에게 넘김'으로 서로 다르고
# 프리미어리그·스카이·Sports Mole·SI 기사는 굴절만 적음 → 다른 출처 2곳 확인 못 함, 넣지 않음.
ADD_A = []
