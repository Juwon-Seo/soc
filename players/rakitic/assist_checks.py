# 도움·골 판정 근거(build_rakitic.py가 exec로 읽음).
# A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). 2014.8 이후 TM 단독 도움은 TM 외 독립 출처 2곳이 있어야 넣음(FotMob·ESPN·경기 기사).
A_CHECK = {
 # 2014.12.3 코파 델 레이 32강 1차전 우에스카 원정 16분 이니에스타 골(TM 'Pass', FotMob 이벤트 도움자 없음)
 "2505176|16": (True, "TM 단독(FotMob 도움자 없음) → ESPN 경기 문자중계('Andrés Iniesta ... Assisted by Ivan Rakitic') + Football España 경기 기사('Iniesta driving home from the edge of the area on 16 minutes after being teed up by Rakitic') 2곳 확인. Sports Mole 중계도 '뮌니르·라키티치가 관여한 팀 골'"),
}
# TM이 상대 자책골로 적었지만 라키티치 골로 보는 것: (경기id, TM 분) → 근거
GOAL_FIX = {
 ("2718996", "83"): "TM은 마티외 소니에 자책골 + 라키티치 'Shot on goal' 도움, FotMob·ESPN·FC 바르셀로나 구단 경기 기사('Rakitic ha hecho el tercer gol con un disparo potente desde fuera del área')·Sports Mole 문자중계·영어/스페인어 위키백과 시즌 골 수는 라키티치 골. FourFourTwo만 소니에 굴절 자책골로 적음 → 라키티치 골(PK 아님, 도움 없음)",
}
# FotMob에만 있는 도움 중 다른 출처 2곳으로 확인한 것: 없음(수집 자료에 FotMob 단독 도움 없음)
ADD_A = []
