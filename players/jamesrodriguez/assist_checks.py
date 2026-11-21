# 2014.8 이후 Transfermarkt 도움 중 FotMob(경기 이벤트·선수 경기 목록)이 확인하지 않는 것: TM 외 다른 출처 2곳 확인 결과.
# 웹 검색·원문 확인 2026-11-21(금지 사이트 미사용; 검색 결과에 나온 worldfootball·fbref 등은 근거로 쓰지 않음; 같은 통신 기사를 옮겨 실은 매체는 한 곳으로 셈).
# build_jamesrodriguez.py가 exec로 읽음. ADD_A: FotMob에만 있는 도움 중 다른 출처 2곳이 확인한 것(gid, 분, 득점자).
A_CHECK.update({
    a_key("2505177", "10"): (True, "Sports Mole 전반 보고('Varane powered in a header from Rodriguez's corner') + ESPN 문자중계(코너킥 James)"),
    a_key("2505204", "32"): (True, "Football España 경기 기사('the former Malaga ace returned the favour ... from the Colombian's assist') + Sports Mole 경기 기사('the Colombian starlet then turned provider') + ESPN 문자중계"),
    a_key("2633810", "3"): (True, "Sports Mole('James Rodriguez played him into space') + Football España('met James' pinpoint square pass') + FourFourTwo('A brilliant lofted pass from James Rodriguez found Cheryshev')"),
    a_key("2633810", "74"): (True, "FourFourTwo('after collecting James' pinpoint pass') + Sports Mole('Rodriguez cut open the home side's backline with an incisive through-ball')"),
    a_key("2767506", "46"): (False, "출처가 엇갈림: El Heraldo(AFP)는 하메스 도움, OKDiario 문자중계는 'Isco para Morata', Football España는 'profited from a flick' → 확인 못 함"),
    a_key("2767506", "55"): (True, "Sky Sports(PA, 'Morata turned home his second from James Rodriguez's cross') + Football España('Morata met James' cross') + OKDiario 문자중계('¡Qué maravilla de pase de James!')"),
    a_key("2767506", "68"): (True, "FourFourTwo('Nacho latching onto James' inviting lofted pass') + El Heraldo(AFP, 'volea de Nacho a centro de James')"),
    a_key("2805576", "90+3"): (True, "FourFourTwo('Ronaldo raced onto James Rodriguez's pass') + FIFA 경기 기사('having been set up by James Rodriguez')"),
    a_key("3640012", "69"): (True, "카타르 스타스 리그 공식 경기 보고('Boli scored ... by heading home a long-range free-kick taken by Rodriguez') + Trome('James Rodríguez dio una asistencia de gol con Al Rayyan, pero fue expulsado')"),
    a_key("3640030", "41"): (True, "El Tiempo('90 minutos y una asistencia', 41분 브라이미) + Win Sports('James aportó asistencia en el triunfo de Al Rayyan sobre Shamal') + RTVC"),
    a_key("3640034", "26"): (True, "Win Sports('cabezazo de Yasser con asistencia de James ... desde un tiro libre') + El Tiempo('levantó un cobro de tiro libre que luego Ahmed Yasser mandó al fondo') + Noticias RCN"),
    a_key("3640045", "19"): (True, "EFE 통신(ESPN Deportes·El Heraldo 게재, Khalilzadeh가 하메스의 코너킥을 헤더로 넣음) + Semana('realizó una nueva asistencia luego de enviar un centro preciso para poner el 1-0') + Colombia.com('asistencia desde un tiro de esquina ... Shojae Khalilzadeh')"),
    a_key("3640080", "14"): (True, "카타르 스타스 리그 공식 경기 보고('Shojae, who headed in James Rodriguez's corner kick') + Noticias RCN('magistral asistencia para el empate 1-1 ... Shojae Khalilzadeh')"),
    a_key("3640088", "39"): (True, "Win Sports('desde el tiro de esquina asistió a Steven N'Zonzi para poner el 1-1') + Noticias Caracol('una asistencia, en el triunfo 2-1') + TUDN('Con asistencia de James Rodríguez, el Al Rayyan ganó')"),
    a_key("3889138", "67"): (True, "Noticias Caracol('se vistió de asistidor para que su compañero Sergi Canós decretara el 4-0') + Noticias RCN('asistió a Sergi Canós para el cuarto gol'); FotMob 선수 경기 목록은 도움 0"),
    a_key("5078450", "66"): (False, "Minuto30·Telemedellín·Vanguardia·Vavel 모두 로만의 단독 돌파 골로만 적고 하메스를 도움으로 적은 출처를 찾지 못함 → 확인 못 함"),
})
ADD_A = [
    # 2022.10.22 파네톨리코스 0-2 올림피아코스 82분 발부에나 골: Transfermarkt는 도움 없음, FotMob 선수 경기 목록 도움 1(경기 이벤트에는 도움자 없음).
    # ESPN Deportes('se llevó a dos rivales y tocó para Valbuena que definió a placer para el 0-2') + Noticias Caracol·Noticias RCN(하메스가 발부에나에게 도움) → 넣음.
    ("3889048", 82, 1, 0, 0, "Mathieu Valbuena", "FotMob 선수 경기 목록 + ESPN Deportes·Noticias Caracol·Noticias RCN 기사"),
]
