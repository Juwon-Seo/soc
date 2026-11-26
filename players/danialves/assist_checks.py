# 도움 판정 근거: A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). 2014.8 이후 TM 단독 도움(FotMob 이벤트·선수 경기 목록에 없음)은 TM 외 독립 출처 2곳이 있어야 넣음.
# 2014.8 전 정상 유형(패스·크로스·헤더·프리킥·코너·빈칸) TM 도움은 단일 출처로 유지(클로제·인시녜·라모스 선례) — 단, 경기 기사가 다른 패서나 리바운드를 적으면 뺌.
A_CHECK = {
 "58475|38": (False, "경기 기사가 다른 패서를 적음: soccer-spain 경기 기사 37분 카누테 골 '헤나투가 머리로 넘긴 공을 헤더로 꽂음'(아우베스 지명 없음, ESPN 도움자 없음) — TM 'Cross' 아우베스와 어긋남"),
 "66482|41": (False, "수비벽 맞고 나온 공: soccer-spain UEFA컵 기사 요약 '아우베스 프리킥이 수비벽에 막힌 뒤 풀센이 따라 들어가 넣음' → 리바운드"),
 "46146|89": (True, "2014.8 전 TM 'Pass' 유지: soccer-spain UEFA컵 기사 '미드필드에서 온 긴 패스를 받아' — 패서 이름 없음(다른 선수 지명 아님)"),
 "988666|110": (True, "2014.8 전 TM 'Cross' 유지: Al Jazeera·Bleacher Report '알베스 크로스를 메시가 가슴으로' (Sky Sports는 사비 크로스로 적음 — 출처 차이, 사비 자료에 이 골 도움 없음)"),
 "3475860|62": (True, "TM + ESPN keyEvent 'Pablo ast: Dani Alves' + Lance!·Goal 브라질 경기 기사('아우베스가 중앙을 몰고 들어가 페널티 지역 안으로 빠른 패스, 파블로 마무리'). FotMob 선수 경기 목록 도움 0"),
 "3475860|89": (True, "TM + ESPN keyEvent 'Gabriel Sara ast: Dani Alves' + Lance!·Goal 브라질·Jornal de Brasília 기사('아우베스의 크로스를 가브리에우 사라가 머리로'). FotMob 선수 경기 목록 도움 0"),
 "3401496|39": (False, "2014.8 이후 TM 단독(FotMob 경기 없음): ESPN keyEvent 'Pablo ast: Dani Alves' 1곳뿐, 경기 기사(Gazeta Esportiva·Jovem Pan 등)는 도움자 언급 없음 → 확인 못 함"),
}
ADD_A = []
# FotMob 단독: 2011.9.28 챔스 BATE전 38분 메시 헤더(TM 도움자 없음, messivsronaldo 도움자 없음, ESPN 도움자 없음) → 넣지 않음.
# FotMob 단독: 2015.5.30 코파 델 레이 결승 아틀레틱전 20분 메시(ESPN 같은 Opta 계열 표기뿐, TM·messivsronaldo 도움자 없음, TNT·NESN 기사는 메시 단독 돌파) → 넣지 않음.
# soccer-spain 기사만 아우베스 패스를 적은 골(2006.3.15 릴 카누테, 2006.4.6 제니트 케파, 2007.2.22 스테아우아 케르자코프, 2008.2.3 레크레아티보·2008.5.11 베티스 루이스 파비아누): TM 도움 없음, 두 번째 출처 없음 → 넣지 않음.
