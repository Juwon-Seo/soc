# Transfermarkt 골 판정 바꿈(build_coutinho.py가 exec로 읽음). G_EXCL: 쿠티뉴 골에서 뺄 것, G_ADD: TM이 다른 선수 골로 적었지만 쿠티뉴 골로 볼 것(gid|TM 분 -> 이유).
G_ADD.update({
    "2899916|64": "2018.5.13 레반테 5-4 바르셀로나 64분(2-5에서 3-5): Transfermarkt만 수아레스 골('Deflected shot on goal', 쿠티뉴 'Shot on goal' 도움)로 적고 FotMob(64분 쿠티뉴, 부스케츠 도움)·ESPN(64' Philippe Coutinho)·Sky Sports·Sports Mole 경기 기록(38·59·64분)·FourFourTwo(Opta: 쿠티뉴 해트트릭, 진 경기 해트트릭)는 쿠티뉴 골 → 쿠티뉴 일반 골(PK 아님), 도움 없음. 수아레스 자료(sua.js)도 이 골을 뺐음",
})
