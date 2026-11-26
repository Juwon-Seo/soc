# 2014.8 이후 Transfermarkt 단독 도움 판정(build_aboubakar.py가 exec로 읽음). 키 = "TM gameId|TM 분". 근거는 judgments.md 4절.
A_CHECK.update({
 "2512209|73": (True, "2015.3.6 브라가 원정 73분 텔루 골: Bola na Rede 경기 기사('아부바카르가 돌아서 텔루에게 내줌')·Combination Play 경기 기사('Aboubakar left Tello one on one')"),
 "2526205|70": (False, "2015.4.6 이스토릴전 70분 다닐루 골: Gazeta Esportiva 기사만 '아부바카르 뒤꿈치 패스'로 확인(beIN 기사는 검색 요약에만 보여 원문 확인 못 함)"),
 "2526214|83": (False, "2015.4.11 히우 아브 원정 83분 에르나니 골: RTP 문자 중계(zerozero 제공, 쓰지 않는 출처)만 아부바카르 패스, 다른 출처 확인 못 함"),
 "2526268|90": (False, "2015.5.22 페나피엘전 다닐루 골(90+2분): FourFourTwo(통신 기사) 한 곳만 아부바카르 스루패스, CM·Bola na Rede 기사에 도움 언급 없음"),
 "2609345|15": (True, "2015.9.12 아로우카 원정 15분 코로나 골: Sports Mole 기사('Aboubakar … teeing up Corona')·El Universal 기사('a pass from Aboubakar')·ESPN 경기 기록"),
 "2656226|81": (False, "2016.3.2 타사 준결승 2차전 질 비센트전 81분 마레가 골: Bola na Rede 기사에 도움 언급 없음, 다른 출처 확인 못 함"),
 "2883706|68": (False, "2017.9.22 포르티모넨스전 68분 브라이미 골: ESPN(옵타) 경기 기록만 아부바카르 도움, FotMob 선수 기록 도움 0, 다른 기사 확인 못 함"),
 "2883727|25": (False, "2017.10.21 파수스 드 페헤이라전 25분 마레가 골: ESPN(옵타)만 아부바카르 도움, CM·Bola na Rede 기사는 '브라이미·아부바카르·마레가의 연계'로만 적음"),
 "2883773|82": (False, "2017.12.10 세투발 원정 82분 마레가 골: ESPN(옵타)만 아부바카르 도움, FotMob 선수 기록 도움 0, PortuGOAL·Bola na Rede 기사에 도움 언급 없음"),
 "2884524|59": (True, "2018.5.6 페이렌스전 59분 브라이미 골: RTP 경기 기사('아부바카르의 로빙 패스')·Bola na Rede 기사('Passe picado de Aboubakar')·ESPN(EFE) 기사·ESPN 경기 기록"),
 "3052465|25": (True, "2018.8.4 수페르타사 아베스전 25분 브라이미 동점골: Bola na Rede 기사('아부바카르가 되돌려 준 공')·Observador 기사('아부바카르와 완벽한 2대1 패스')"),
 "3718406|17": (False, "2022.2.21 킹스컵 8강 알힐랄전 17분 탈리스카 골: Soccernet은 아부바카르, The Eagle Online은 조나탄 로드리게스 크로스로 출처가 갈림, FotMob 도움 없음"),
 "3988655|85": (False, "2022.12.21 킹스컵 16강 알아달라전 85분 알나제이 골: 다른 출처 확인 못 함, FotMob 도움 없음"),
 "4738660|72": (False, "2025.10.26 가발라 원정 72분 이페아니 매슈 골: playerstats 경기 기록에 도움 없음, 다른 출처 확인 못 함, FotMob 도움 없음"),
})
