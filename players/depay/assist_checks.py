# 2014.8 이후 Transfermarkt 도움 중 FotMob 경기 이벤트가 확인하지 않는 것: TM 외 다른 출처 확인 결과(build_depay.py가 exec로 읽음).
# 웹 확인 2026-11-21(금지 사이트 미사용: 검색 결과에 나온 worldfootball·fbref·sofascore·11v11은 근거로 쓰지 않음; 같은 통신 기사를 옮긴 매체는 한 곳으로 셈).
# ESPN 기록은 site.api.espn.com 경기 요약(keyEvents·commentary 'Assisted by …').
A_CHECK.update({
    a_key("2483442", "59"): (True, "Total Dutch Football 경기 기사('a deflected shot after a short corner from Depay') + fcupdate.nl 경기 페이지(도움 데파이)"),
    a_key("2609562", "90+4"): (True, "Sports Mole 경기 분석('delivered a peach of a cross for Fellaini to add the third') + RNZ(통신 기사, 'Fellaini converted a cross from Depay')"),
    a_key("2613774", "20"): (True, "Sky Sports 경기 기사('setting up Rooney with superbly weighted pass') + ESPN 경기 기사('Memphis Depay cut inside and slotted a great pass into the striker's path')"),
    a_key("2617969", "90+2"): (True, "Sky Sports 경기 기사('Memphis acted as the target, bundled the ball into the path of Martial') + Sports Mole 경기 기사('from a Memphis Depay through-ball')"),
    a_key("2978635", "25"): (True, "AS 낭시 구단 공식 경기 기록('Depay entre dans la surface et sert Fekir dans l'axe') + Maxifoot 경기 기사('Depay élimine deux adversaires … et sert Fekir')"),
})
# FotMob 선수 경기 목록 도움 수로만 확인되는 것(경기 이벤트에 도움자 없음): ESPN 경기 기록을 세 번째 출처로 확인
PM_EXTRA = {
    a_key("2942780", "12"): "ESPN 경기 기록('Mariano … Assisted by Memphis Depay')",
    a_key("2942894", "69"): "ESPN 경기 기록('Bertrand Traoré … Assisted by Memphis Depay')",
    a_key("3047473", "89"): "ESPN 경기 기록('Ferland Mendy … Assisted by Memphis Depay')",
    a_key("3098037", "55"): "ESPN 경기 기록('Maxwel Cornet … 55' … Assisted by Memphis Depay')",
    a_key("4509482", "43"): "ESPN 경기 기록('Yuri Alberto … Assisted by Memphis Depay')",
    a_key("4509496", "44"): "ESPN 경기 기록('Yuri Alberto … header … Assisted by Memphis Depay')",
    a_key("4560569", "36"): "ESPN 경기 기록('André Carrillo … Assisted by Memphis Depay')",
    a_key("4560577", "40"): "ESPN 경기 기록('Matheus Bidu … Assisted by Memphis Depay')",
    a_key("4568128", "22"): "ESPN 경기 기록('Ángel Romero … Assisted by Memphis Depay with a cross following a corner')",
    a_key("4572568", "12"): "ESPN 경기 기록('Yuri Alberto … Assisted by Memphis Depay with a cross following a corner')",
    a_key("4575780", "58"): "ESPN 경기 기록('Yuri Alberto … Assisted by Memphis Depay')",
    a_key("4783156", "80"): "ESPN 경기 기록('Kayke … Assisted by Memphis Depay')",
}
ADD_A = []
