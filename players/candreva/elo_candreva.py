# 상대 Elo: 통합표·같은 경기 자료에 없는 팀-시즌(judgments.md 7절). build_candreva.py가 exec로 읽는다.
# 순위는 raw/ranks.txt(Transfermarkt 최종 순위표)와 영어 위키백과·RSSSF로 확인(우승 팀 확인).
MANUAL_ALIAS.update({"bassano virtus 55 st": key("FC Bassano")})   # 클로제 자료 표기
RANK_LG = []
def model(lg, season, r, n):
    return None

MAN = {
    # 세리에C1 B조 2006-07(18팀): 다른 선수 자료의 세리에C 18팀 조 순위값(10위 1402)
    (key("Salernitana Calcio 1919"), "2006-07"): (1402, "세리에C1 B조 2006-07 10위/18팀 (추정)"),
    # 세리에B 2008-09(22팀): 다른 선수 자료의 22팀 세리에B 순위값(2006-07·2011-12·2013-14와 같은 척도), 10위는 9위 1585·11위 1569의 가운데
    (key("FC Empoli"), "2008-09"): (1614, "세리에B 2008-09 5위"),
    (key("Piacenza FC"), "2008-09"): (1577, "세리에B 2008-09 10위"),
    (key("Salernitana Calcio 1919"), "2008-09"): (1555, "세리에B 2008-09 14위"),
    (key("AC Ancona"), "2008-09"): (1526, "세리에B 2008-09 19위"),
    # 세리에B 20팀 척도(2021-22·2023-24 같은 시즌 다른 순위 값과 같은 곡선)
    (key("US Alessandria Calcio 1912"), "2021-22"): (1522, "세리에B 2021-22 18위"),
    (key("Ternana Calcio"), "2023-24"): (1538, "세리에B 2023-24 16위"),
    # 추정
    (key("Rosenborg BK"), "2015-16"): (1500, "노르웨이 2015 1위 (추정, 다른 선수 자료 로센보리 2004·2010 1위 1500과 같음)"),
    (key("Dnipro Dnipropetrovsk (- 2020)"), "2015-16"): (1600, "우크라이나 2015-16 3위 (추정, 다른 선수 자료 드니프로 2014-15 3위 1600과 같음)"),
}
MAN_GAME = {}
