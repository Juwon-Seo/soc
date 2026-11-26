# 비달 도움 판정 표(build_vidal.py가 exec로 읽음). 근거는 judgments.md 4절.
# A_CHECK: 2014.8 이후 TM 도움 중 FotMob(경기 이벤트·선수 경기 목록)이 확인하지 않은 것 → (넣음?, 근거)
ESPN = "ESPN 경기 기록(keyEvents 'Assisted by Arturo Vidal')"
A_CHECK = {
 "2576682|17": (True, ESPN + "·FourFourTwo 경기 기사('오른쪽 측면 비달의 정확한 패스를 받아 괴체가 마무리')"),
 "2618546|52": (True, ESPN + "·StatMuse 경기 기록(A. Vidal assists)·FC 바이에른 공식 경기 보고(비달이 오른쪽의 뮐러에게 연결)"),
 "2581714|40": (False, "슈팅 리바운드: FC 바이에른 공식 경기 보고(독일어·영어)·ESPN 해설 — 코망 크로스를 비달이 헤더로 때려 크로스바에 맞고 나온 공을 뮐러가 밀어 넣음(ESPN 경기 기록은 도움 없음)"),
 "2645818|110": (True, ESPN + "('following a fast break')·StatMuse 경기 기록(110' K. Coman, Assist: Arturo Vidal)"),
 "2754880|90+3": (True, ESPN + "·FC 바이에른 공식 경기 보고(비달이 알라바의 쐐기골을 만들어 줌)"),
 "3252237|23": (False, "ESPN 경기 기록·StatMuse 경기 기록 모두 카를레스 페레스 골 도움 없음, FotMob도 도움 없음"),
 "3735636|68": (False, "ESPN 경기 기록·FotMob 이벤트 모두 다르미안 도움(TM만 비달)"),
 "4341966|21": (True, ESPN + "(스루 패스)·ESPN 데포르테스 경기 기사('루카스 소토가 아르투로 비달의 스루 패스를 받아')"),
}
# FotMob 단독 도움(TM 없음) — 넣은 것 없음:
#  2022.5.6 엠폴리전 90+4분 산체스 골: FotMob 이벤트·ESPN 경기 기록은 비달, StatMuse 경기 기록은 제코 도움, TM은 도움 없음 → 다른 출처끼리 엇갈려 넣지 않음
#  2012.2.25 밀란전 83분 마트리 골: 2014.8 이전은 TM 기준(TM 도움 없음)
ADD_A = []
