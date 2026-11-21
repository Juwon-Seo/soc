# 마리오 발로텔리 도움 판정(build_balotelli.py가 exec로 읽음). 웹 확인 2026-11-20(금지 사이트 미사용).
# 2014.8 이후 Transfermarkt 도움 중 FotMob이 확인하지 않는 것: TM 외 다른 출처 2곳 필요.
A_CHECK.update({
    a_key("3692001", "14"): (False, "Cumhuriyet 경기 기사(AA 통신 문자 기록: '오르타 사하에서 발로텔리의 패스를 받은 유누스 아크귄') 1곳뿐. ESPN 경기 없음, FotMob 도움 칸 빈칸, vi.nl(Opta) 타임라인 도움 없음, 영어 위키백과 시즌 문서 도움 없음"),
    a_key("3692001", "41"): (False, "Cumhuriyet 경기 기사(AA: '발로텔리의 오른쪽 크로스를 메테한 미마로을루가 헤더') 1곳뿐. 다른 출처 못 찾음"),
})
# FotMob 전용 도움 중 다른 출처 2곳이 확인한 것(TM 리포트는 도움 빈칸): gid -> [(분, 골 전 우리, 골 전 상대, 득점자, 근거)]
FM_ADD.update({
    "2735583": [(27, 1, 1, "Valentin Eysseric", "ESPN 문자 중계(event 449014 'Assisted by Mario Balotelli') + AFP 기사(FourFourTwo·Malay Mail 'Balotelli turned provider 11 minutes later when he set up midfielder Eysseric') + maxifoot 경기 평('Balotelli sert Eysseric à l'entrée de la surface')")],
})
