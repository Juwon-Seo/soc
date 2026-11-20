# 2014.8 이후 Transfermarkt 도움 중 FotMob(경기 이벤트·선수 경기 목록)이 확인하지 않는 것: TM 외 다른 출처 2곳(ESPN 문자 중계 + 경기 기사·구단 기록) 확인 결과.
# 웹 검색·원문 확인 2026-11-20(금지 사이트 미사용; 검색 결과에 나온 sofascore·ogol 등은 근거로 쓰지 않음). build_pato.py가 exec로 읽음.
A_CHECK.update({
    a_key("2454502", "42"): (True, "ESPN + Superesportes(2014.9.10 'Desta vez Pato cruzou, Souza dominou e fuzilou')"),
    a_key("2454526", "45+1"): (True, "ESPN + Estadão 계열 기사(meon.com.br 'Auro deu lançamento longo, Pato ajeitou de cabeça e Michel Bastos chegou chutando cruzado')"),
    a_key("4311825", "55"): (True, "ESPN + 상파울루 팬 블로그 경기 기록(torcedorspfc1935.blogspot.com '3 gols e 1 assistência', Kardec 골 'após passe de Pato')"),
    a_key("4312728", "46"): (True, "ESPN + Santa Portal(santaportal.com.br 'São Paulo goleia Bragantino': 파투의 패스를 받은 보스칠리아가 수비를 제치고 골)"),
    a_key("4318593", "87"): (True, "ESPN + Acervo Santista(2015.4.19 경기 기록 'servido por Alexandre Pato') + Blog do Paulinho 칼럼(파투의 패스, 오프사이드 논란)"),
    a_key("2547076", "59"): (True, "ESPN + 경기 기사(meon.com.br·spfc.net: 파투가 공을 받아 미셰우 바스투스에게 내줌 'rolou para Michel Bastos')"),
    a_key("2569453", "19"): (True, "ESPN + Terra 문자 중계('Alexandre Pato cruzou pela esquerda, e Michel Bastos apareceu na área para completar de cabeça')"),
    a_key("2569460", "15"): (True, "코리치바 구단 경기 기사(coritiba.com.br/artigo/23622: 파투가 침투해 낮게 크로스, 센투리온 골) + saopaulo.blog 경기 분석(루캉의 롱패스를 받은 파투가 센투리온에게)"),
    a_key("2615450", "53"): (False, "ESPN만(경기 기사에서 도움자 확인 못 함)"),
    a_key("4256841", "59"): (True, "ESPN + Metrópoles('Alexandre Pato serviu para Centurión completar') + Gazeta Esportiva('Pato recebeu passe, cruzou rasteiro e Centurión apareceu de carrinho')"),
    a_key("2626647", "43"): (False, "ESPN만(경기 기사에서 도움자 확인 못 함)"),
    a_key("2626662", "30"): (True, "ESPN + Terra 경기 기사·CruzeiroPédia(파투의 코너킥을 루이스 파비아누가 헤더)"),
    a_key("2810020", "77"): (False, "ESPN만(EFE·Ámbito는 트리게로스의 40m 중거리 슛으로만 적고 패스 언급 없음)"),
    a_key("2991903", "57"): (True, "신화통신(China.org.cn 같은 기사: 비첼의 헤더를 받은 파투가 수비 뒤로 넘겨 모데스트 골) + Rappler 문자 중계(Witsel → Pato → Modeste)"),
    a_key("2995319", "30"): (False, "AFC 경기 기사: 파투 크로스 → 자오쉬르 헤더가 골키퍼에 막히고 자오쉬르가 리바운드 골(골키퍼 선방 뒤 리바운드라 도움 아님), 다른 출처 없음"),
    a_key("3397423", "74"): (True, "ESPN + Terra·Estadão 문자 중계(다니 아우베스가 파투와 2대1 패스 뒤 골) + Gazeta Esportiva('dois gols e uma assistência')"),
    a_key("3397446", "67"): (True, "ESPN + Lance 경기 기사('Pato lançou de pé esquerdo e Pablo, na segunda trave, virou: 2 a 1')"),
})
