# 상대 Elo: 순위표 모형·직접 추정 (judgments.md 7절). build_perisic.py가 exec로 읽는다(key·RANKS는 build에서 옴).
# 순위 곡선(CURVE): 기존 league_model.py와 같은 21칸 곡선(가가와 elo_tables.py와 같은 식)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
def half_up(x): return int(x + 0.5)

# 벨기에 1부: 데 브라위너 자료의 리그 모형(평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 계수 평균 − 7.333), 흩어짐 119).
# BE_COEF 시작 연도 2007 4.5·2008 4.5·2009 8.7·2010 4.6·2011 10.1 → 2008-09 1439.6, 2009-10 1440.3, 2010-11 1483.9.
# 기존 선수 자료에 같은 시즌·같은 순위 값이 있으면 그 값(모형과 ±3 차이), 없으면 모형 값.
BE_COEF = {2006: 4.7, 2007: 4.5, 2008: 4.5, 2009: 8.7, 2010: 4.6, 2011: 10.1, 2012: 6.5}
def be_mean(y):
    c = (BE_COEF[y - 1] + BE_COEF[y] + BE_COEF[y + 1]) / 3
    return 1473 + 23.33 * (c - 7.333)
BE_EXIST = {"2009-10": {1: 1740, 2: 1616, 8: 1413, 12: 1349, 13: 1320},
            "2010-11": {1: 1784, 2: 1663, 3: 1597, 4: 1563, 5: 1545, 6: 1521, 10: 1435, 11: 1423, 12: 1412, 14: 1361, 16: 1321}}
# 공식 최종 순위(챔피언 플레이오프 1~6위 → 나머지 정규 시즌 순서; 2008-09는 플레이오프 없이 34라운드 + 1위 결정전).
#  2008-09(18팀): 안데를레흐트·스탕다르 승점 77 동률 → 결정전에서 스탕다르 우승. 브뤼허·헨트 승점 59 동률 → 승수(18 > 17)로 브뤼허 3위.
#  2009-10(15팀, 무스크롱 기록 삭제): 메헬렌·스탕다르 승점 39 → 승수 12 > 10, 로케런·루셀라러 18 → 승수 5 > 4(루셀라러 강등 플레이오프).
#  2010-11(16팀): 플레이오프 1 최종 헹크·스탕다르·안데를레흐트·브뤼허·헨트·로케런.
BE_ORDER = {
    "2008-09": ["Standard Liège", "RSC Anderlecht", "Club Brugge KV", "KAA Gent", "Zulte Waregem", "KVC Westerlo", "KSC Lokeren (-2020)",
                "KRC Genk", "Cercle Brugge", "KV Mechelen", "Excelsior Mouscron (-2009)", "Royal Charleroi SC", "Germinal Beerschot Antwerpen",
                "KV Kortrijk", "FCV Dender EH", "KSV Roeselare (-2020)", "AFC Tubize", "RAEC Mons (-2015)"],
    "2009-10": ["RSC Anderlecht", "KAA Gent", "Club Brugge KV", "Sint-Truidense VV", "KV Kortrijk", "Zulte Waregem", "KV Mechelen",
                "Standard Liège", "Cercle Brugge", "Germinal Beerschot Antwerpen", "KRC Genk", "KVC Westerlo", "Royal Charleroi SC",
                "KSC Lokeren (-2020)", "KSV Roeselare (-2020)"],
    "2010-11": ["KRC Genk", "Standard Liège", "RSC Anderlecht", "Club Brugge KV", "KAA Gent", "KSC Lokeren (-2020)", "KV Mechelen",
                "KVC Westerlo", "Cercle Brugge", "KV Kortrijk", "Zulte Waregem", "Sint-Truidense VV", "Germinal Beerschot Antwerpen",
                "Lierse SK (-2018)", "KAS Eupen", "Royal Charleroi SC"],
}
BE_RANK = {}
for s, lst in BE_ORDER.items():
    for i, t in enumerate(lst): BE_RANK[(key(t), s)] = (i + 1, len(lst))

# 에레디비시: 기존 자료의 시즌 무관 순위별 고정값
NL1_FIX = {1: 1837, 2: 1735, 3: 1677, 4: 1642, 5: 1624, 6: 1608, 7: 1587, 8: 1563, 9: 1542, 10: 1528,
           11: 1516, 12: 1504, 13: 1499, 14: 1482, 15: 1459, 16: 1441, 17: 1430, 18: 1406}
NOW = " (11월 중순 현재)"

def rank_model(k, season):
    if (k, season) in BE_RANK:
        r, n = BE_RANK[(k, season)]
        v = BE_EXIST.get(season, {}).get(r)
        if v is None: v = half_up(be_mean(int(season[:4])) + 119 * curve(r, n))
        return v, f"벨기에 1부 {season} {r}위"
    t = RANKS.get(("NL1", season))
    if t and k in t:
        r, n = t[k]
        return NL1_FIX[r], f"에레디비시 {season}{NOW if season == '2026-27' else ''} {r}위"
    return None

# 순위표·모형으로 안 되는 상대(기존 선수 자료의 같은 리그·같은 순위 값을 쓰거나 직접 추정)
MAN = {
    (key("FK Partizan Belgrade"), "2009-10"): (1520, "세르비아 2009-10 1위 (추정, 다른 선수 자료 파르티잔 2008-09·2010-11 1위 1520과 같음)"),
    (key("Karlsruher SC"), "2013-14"): (1615, "2. 분데스리가 2013-14 5위"),          # 기존 2. 분데스리가 5위 값(시즌 무관 같은 곡선)
    (key("Arminia Bielefeld"), "2014-15"): (1557, "독일 3부 리가 2014-15 1위"),       # 기존 3부 리가 1위 값(마그데부르크 2017-18)
    (key("Cagliari Calcio"), "2015-16"): (1707, "세리에B 2015-16 1위"),              # 세리에B 모형(평균 1578·흩어짐 51.24) 1위 = 기존 사수올로 2012-13 1위 1707
    (key("Sporting CP"), "2022-23"): (1690, "포르투갈 1부 2022-23 4위"),             # 기존 포르투갈 1부 4위 값(2017-18·2018-19·2023-24·2024-25 브라가 1690)
    (key("NK Istra 1961"), "2023-24"): (1350, "크로아티아 1부 2023-24 8위/10팀 (추정, 다른 선수 자료 크로아티아 1위 1610·3위 1460·4위 1430에 맞춘 순위 곡선)"),
    (key("Excelsior Rotterdam"), "2024-25"): (1413, "에이르스터 디비시 2024-25 2위"),  # 기존 에이르스터 디비시 2위 값(캄뷔르 1997-98 등 1413)
    (key("Koninklijke HFC Haarlem"), "2024-25"): (1150, "네덜란드 3부(트베이더 디비시) 2024-25 8위 (추정, 다른 선수 자료 네덜란드 3부 이하 아마추어 1150과 같음)"),
    (key("GVVV Veenendaal"), "2025-26"): (1150, "네덜란드 3부(트베이더 디비시) 2025-26 14위 (추정, 다른 선수 자료 네덜란드 3부 이하 아마추어 1150과 같음)"),
}
