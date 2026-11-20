# 2014.8 이후 Transfermarkt 도움 중 FotMob(경기 이벤트·선수 경기 목록)이 확인하지 않는 것: TM 외 다른 출처 2곳 확인 결과.
# 웹 검색·원문 확인 2026-11-20(금지 사이트 미사용; 검색 결과에 나온 fbref 등은 근거로 쓰지 않음). build_lavezzi.py가 exec로 읽음.
A_CHECK.update({
    a_key("2542732", "3"): (False, "Maxifoot 경기 기사: 코너킥 뒤 문전 혼전에서 다비드 루이스가 먼저 머리로 밀어 넣음('Sur corner, après un cafouillage dans la surface') → 혼전 볼이라 도움 아님, 다른 출처 없음"),
    a_key("2654385", "54"): (True, "Maxifoot 경기 기사('Sur un corner sortant de Lavezzi au premier poteau, David Luiz place une tête') + AP 경기 기사(Fox News 게재: 라베치의 코너킥을 다비드 루이스가 헤더)"),
    a_key("2658218", "34"): (False, "확인 못 함(경기 기사·문자 중계에서 도움자 확인 못 함)"),
    a_key("2658231", "71"): (False, "확인 못 함(경기 기사·문자 중계에서 도움자 확인 못 함)"),
    a_key("2658239", "34"): (True, "신랑(新浪)체육 경기 기사(2016.5.6 '第34分钟，拉维奇助攻，热尔维尼奥长途奔袭破门') + Sport Eden 경기 이벤트('assist by E. Lavezzi')"),
    a_key("2658239", "76"): (True, "신랑(新浪)체육 경기 기사('第76分钟，拉维奇送出妙传，卡库塔挑射破门') + Sport Eden 경기 이벤트('assist by E. Lavezzi')"),
    a_key("2835178", "27"): (False, "FotMob 경기 이벤트·선수 경기 목록은 이 경기 라베치 도움 3개(43·50·84분)만 셈, ESPN 도움자 없음 → 확인 못 함"),
    a_key("2835273", "23"): (False, "FotMob 선수 경기 목록 도움 0, ESPN 도움자 없음, 경기 기사 확인 못 함"),
})
