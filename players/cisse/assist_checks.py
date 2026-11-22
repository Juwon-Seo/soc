# 도움 웹 확인(build_cisse.py가 exec로 읽음). 2014.8 이후 Transfermarkt 도움 4개 중 3개는 FotMob 경기 이벤트와 같음(±2분).
# 2014.10.28 리그컵 32강 바스티아 3-1 오세르 58분 아이테 헤더(Transfermarkt만 시세 도움, FotMob 이벤트 도움자 빈칸):
#   ESPN 경기 기록(gameId 406263, 골 목록·문자 중계에 도움 표기 없음), Maxifoot 기사 23411('Floyd Ayité avait égalisé', 도움 언급 없음),
#   Sports Mole 경기 페이지(득점자만) — 다른 출처 2곳으로 확인하지 못해 뺌. (시세는 46분 교체 투입, 64·71분 두 골)
A_CHECK.update({
    "2502461|58": (False, "2014.8 이후 Transfermarkt 단독, ESPN·Maxifoot·Sports Mole에 도움 기록 없음"),
})
ADD_A = []
