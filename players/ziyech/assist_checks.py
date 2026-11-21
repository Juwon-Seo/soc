# 2014.8 이후 Transfermarkt 도움 중 FotMob 경기 이벤트가 확인하지 않는 것: TM 외 다른 출처 2곳 확인 결과(웹 확인 2026-11-21, 금지 사이트 미사용).
# build_ziyech.py가 exec로 읽음.
A_CHECK.update({
    a_key("2509861", "40"): (False, "TM만(유형 빈칸). FotMob·ESPN 도움자 없음, Sky Sports 경기 기사는 득점자만 적음 → 확인 못 함"),
    a_key("2524025", "24"): (False, "TM만. walfoot(voetbalkrant 계열) 문자 중계만 지예흐 도움, Sports Mole 기사는 '뒤쪽 포스트에서 받아' 도움자 이름 없음, FotMob·ESPN 도움자 없음 → 1곳뿐"),
    a_key("2754296", "34"): (False, "TM만. ESPN(Opta) 문자 중계는 도움 없는 트라오레 골, afc-ajax.info 경기 기록 'after mistake opponent'(상대 실수) → 도움 아님"),
    a_key("2756542", "13"): (True, "ESPN 문자 중계('Assisted by Hakim Ziyech with a cross following a corner') + afc-ajax.info 경기 기록('assist: Hakim Ziyech, from corner')"),
    a_key("2756542", "25"): (True, "ESPN 문자 중계(코너킥 크로스 도움) + afc-ajax.info 경기 기록 + NOS 기사('uit een corner van Ziyech de 2-0')"),
    a_key("2700880", "71"): (False, "TM만. FotMob 선수 경기 목록 도움 0, afc-ajax.info 경기 기록은 '코너킥(간접)'으로 도움자 없음 → 확인 못 함"),
    a_key("3052109", "88"): (False, "TM만. FotMob 선수 경기 목록 도움 0, afc-ajax.info 경기 기록은 '코너킥(간접)'으로 도움자 없음 → 확인 못 함"),
    a_key("3216161", "32"): (True, "afc-ajax.info 경기 기록('Noa Lang, assist: Hakim Ziyech') + Voetbal International 경기 기사('Op aangeven van Ziyech schoot Lang ... de aansluitingstreffer binnen'); NOS는 '반 더 베이크와 지예흐의 준비 작업'"),
    a_key("4401032", "15"): (False, "TM만. QSL 공식 기사·Gulf Times·QNA는 알모에즈 알리의 박스 가장자리 슈팅만 적고 도움자 없음, FotMob 도움자 없음 → 확인 못 함"),
})
FM_ADD.update({
})
