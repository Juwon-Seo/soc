# 도움 판정 보조: A_CHECK["경기id|TM 분"] = (넣음 여부, 근거). build_shaqiri.py가 exec로 읽음.
# 2014.8 이후 Transfermarkt 도움 중 FotMob(경기 이벤트·선수 경기 목록)이 같이 적지 않은 것: TM 외 독립 출처 2곳(ESPN·경기 기사 등)으로 확인한 것만 넣음.
# (2023.5.24 오스틴전 프시빌코 골·2023.6.6 휴스턴전 수케 골은 FotMob 선수 경기 목록이 도움 1로 셈 → TM+FotMob, ESPN도 도움자 샤키리)
A_CHECK = {
 "4456531|86": (False, "TM만 도움으로 적음(FotMob 이벤트·선수 경기 목록 0, ESPN 자료 없음); Blick 경기 기사는 카데의 86분 동점골을 개인 돌파(Einzelaktion)로 적어 도움을 확인하지 못함"),
 "4637947|24": (False, "TM만 도움으로 적음(FotMob 이벤트·선수 경기 목록 0, ESPN 자료 없음); SRF 문자 기사 1곳만 샤키리 패스를 적음(bluewin 기사는 도움자 없음), 다른 출처 2곳 기준 미달"),
}
ADD_A = []
