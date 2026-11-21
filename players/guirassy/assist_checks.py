# 도움 판정 보조: A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). build_guirassy.py가 exec로 읽음.
# 2014.8 이후 Transfermarkt 도움 중 FotMob(경기 이벤트·선수 경기 목록)이 같이 적지 않은 것: TM 외 독립 출처 2곳으로 확인한 것만 넣음.
A_CHECK = {
 "2914246|35": (True, "FotMob 도움자 없음; ESPN 'Assisted by Sehrou Guirassy'(헤더 패스), Sport1 경기 기사 '기라시의 헤더 패스(Kopfball-Vorlage)', 헤르타 구단 기사(기라시 헤더 뒤 촐러 득점)"),
 "2654407|85": (False, "TM만 도움(Header)으로 적음; FotMob·ESPN 도움자 없음, 경기 기사(foot-direct 등)에서 도움자 확인 못 함"),
 "2654461|53": (False, "TM만 도움(유형 빈칸); FotMob·ESPN 도움자 없음, Eurosport 경기 요약 등에서 도움자 확인 못 함"),
 "4096246|90+3": (False, "TM만 도움(유형 빈칸, TM 공식 도움 필드는 0); FotMob 이벤트·선수 경기 목록·ESPN 모두 도움 없음, FC 바이에른 경기 기사·스카이 스포츠도 도움 언급 없음"),
 "2871937|90+5": (False, "상대(프라이부르크) 골에 '기라시 핸드볼'로 적힌 항목 — 도움 아님"),
}
# FotMob에만 있는 도움 중 다른 출처 2곳으로 확인한 것: (gid, 분, gf, ga, pk, 득점자, 근거)
ADD_A = [
 ("4096268", 75, 2, 0, 0, "Woo-Yeong Jeong", "FotMob 경기 이벤트·선수 경기 목록 도움 1; ESPN 'Assisted by Serhou Guirassy', Transfermarkt 공식 도움 필드(assistsOfficial 1, 기본 도움 수는 0)"),
]
# 확인 못 해 넣지 않은 FotMob 단독 도움: 2019.3.9 니메전 64분 피터르스 골 — ESPN 도움자 없음, maxifoot 경기 기사는 코나테 크로스로 적음
