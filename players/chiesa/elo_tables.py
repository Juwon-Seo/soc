# 상대 Elo: 통합표에 없는 팀-시즌(judgments.md 7절). build_chiesa.py가 exec로 읽는다.
# 순위는 raw/ranks.txt(Transfermarkt 최종 순위표, 우승 팀 확인)와 WebSearch로 확인.
RANK_LG = []
def model(lg, season, r, n):
    return None

MAN = {
    # 기존 자료의 같은 리그·같은 순위 값
    (key("SPAL"), "2020-21"): (1579, "세리에B 2020-21 9위"),
    (key("Southampton FC"), "2025-26"): (1669, "챔피언십 2025-26 4위"),
    # 추정
    (key("Qarabağ FK"), "2016-17"): (1500, "아제르바이잔 2016-17 1위 (추정, 다른 선수 자료 아제르바이잔 1위 1500과 같음)"),
    (key("AC Monza"), "2019-20"): (1548, "세리에C 2019-20 조 A 1위/20팀 (추정, 다른 선수 자료 세리에C 2018-19 조 A 1위 1548과 같음)"),
    (key("Accrington Stanley"), "2024-25"): (1337, "리그 투(4부) 2024-25 21위 (추정, 다른 선수 자료 리그 투 19위 1340·22위 1335 사이 보간)"),
}
MAN_GAME = {}
