# 상대 Elo: 순위표 모형·직접 추정 (judgments.md 7절). build_kagawa.py가 exec로 읽는다.
# 순위 곡선(CURVE): 기존 league_model.py와 같은 21칸 곡선(포를란 build_forlan.py와 같은 식)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
SD2 = 51.24
def half_up(x): return int(x + 0.5)

# J1 18팀 순위값: 기존 선수 자료(이니에스타·비야·토레스·포를란 등 2014~2023, 해마다 같은 값). 5위는 4·6위 가운데.
J1_18 = {1: 1776, 2: 1707, 3: 1668, 4: 1644, 5: 1633, 6: 1622, 7: 1607, 8: 1592, 9: 1577, 10: 1568, 11: 1560,
         12: 1552, 13: 1548, 14: 1537, 15: 1522, 16: 1509, 17: 1502, 18: 1486}
# J1 평균·흩어짐: 18팀 순위값(1위 제외)을 평균 + 흩어짐 × 곡선에 최소제곱으로 맞춤(포를란 선례) → 약 1588.3 / 74.3
def _fit():
    xs = [(curve(r, 18), v) for r, v in J1_18.items() if r not in (1, 5)]
    n = len(xs); mx = sum(x for x, _ in xs) / n; my = sum(y for _, y in xs) / n
    s = sum((x - mx) * (y - my) for x, y in xs) / sum((x - mx) ** 2 for x, _ in xs)
    return my - s * mx, s
J1_MEAN, J1_SD = _fit()
J2_MEAN = J1_MEAN - 162          # 토레스·포를란 선례(J2 2015 순위값 재현)
J3_MEAN = J2_MEAN - 162          # 새 추정(근거 약함): 튀르키예 3부·이탈리아 레가 프로와 같은 한 단계 162
# J1 20팀 시즌(2021·2025): 기존 값 5·6·7·8·18·19·20위, 나머지는 J1 모형(평균 + 흩어짐 × 20팀 곡선; 기존 7·8·19위를 그대로 재현)
J1_20_EXIST = {5: 1637, 6: 1628, 7: 1617, 8: 1603, 18: 1507, 19: 1501, 20: 1486}
def j1_20(r):
    return J1_20_EXIST.get(r, half_up(J1_MEAN + J1_SD * curve(r, 20)))

# 튀르키예 2018-19: 기존 값(1·3·4·9·11·14·17위)이 평균 1436.3 + 119 × 곡선과 정확히 같음 → 같은 식
TR_1819 = {1: 1736, 3: 1565, 4: 1527, 9: 1419, 11: 1390, 14: 1353, 17: 1298}
# 독일 3부 리가: 기존 순위값(여러 시즌 같은 곡선 2위 1513 … 19위 1369)에 맞춘 평균 1430·흩어짐 50.2
DE3_EXIST = {2: 1513, 5: 1462, 8: 1439, 9: 1429, 12: 1414, 13: 1409, 15: 1403, 17: 1379, 19: 1369}
# 2. 분데스리가: 기존 순위값(3위 1636·5위 1615·6위 1609·8위 1592·15위 1544)에 맞춘 평균 1587.5·흩어짐 46.6
DE2_EXIST = {3: 1636, 5: 1615, 6: 1609, 8: 1592, 15: 1544}
def _fit2(d, n):
    xs = [(curve(r, n), v) for r, v in d.items()]
    k = len(xs); mx = sum(x for x, _ in xs) / k; my = sum(y for _, y in xs) / k
    s = sum((x - mx) * (y - my) for x, y in xs) / sum((x - mx) ** 2 for x, _ in xs)
    return my - s * mx, s
DE3_M, DE3_S = _fit2(DE3_EXIST, 20)
DE2_M, DE2_S = _fit2(DE2_EXIST, 18)

GRP_KO = {"J1YV-East": "동부", "J1YV-West": "서부"}
RANK_LG = ["J1YV-East", "J1YV-West", "JAP1", "JAP2", "JAP3", "TR1", "ES2", "BE1", "L2", "L3", "RLSW"]
NOW = "(11월 중순 현재)"

def model(lg, season, r, n):
    cur = " " + NOW if season == "2026-27" else ""
    if lg == "JAP1" and n == 18:
        return J1_18[r], f"J1리그 {season} {r}위"
    if lg == "JAP1" and n == 20:
        return j1_20(r), f"J1리그 {season}{cur} {r}위"
    if lg == "JAP2":
        return half_up(J2_MEAN + SD2 * curve(r, n)), f"J2리그 {season}{cur} {r}위"
    if lg == "JAP3":
        return half_up(J3_MEAN + SD2 * curve(r, n)), f"J3리그 {season}{cur} {r}위 (추정, J2 평균 − 162)"
    if lg in GRP_KO:
        # J1 백년구상 리그(2026 상반기 특별 대회, 동·서 각 10팀): 조 순위를 J1 모형의 10팀 곡선에 넣음
        return half_up(J1_MEAN + J1_SD * curve(r, n)), f"J1 백년구상 리그 {season} {GRP_KO[lg]} {r}위/{n}팀"
    if lg == "TR1" and season == "2018-19":
        return TR_1819.get(r, half_up(1436.28 + 119.02 * curve(r, n))), f"쉬페르리그 {season} {r}위"
    if lg == "ES2" and n == 22:
        return half_up(1624 + 51.237 * curve(r, n)), f"세군다 {season} {r}위"
    if lg == "BE1":
        # 벨기에 1부 2021-23: 평균 1500·흩어짐 80(추정, 근거 약함; 다른 선수 자료 벨기에 1위 1700·우승 1680과 맞춤)
        return half_up(1500 + 80 * curve(r, n)), f"벨기에 1부 {season} {r}위 (추정)"
    if lg == "L2":
        return DE2_EXIST.get(r, half_up(DE2_M + DE2_S * curve(r, n))), f"2. 분데스리가 {season} {r}위"
    if lg == "L3":
        if r in DE3_EXIST: v = DE3_EXIST[r]
        elif r == 18: v = half_up((DE3_EXIST[17] + DE3_EXIST[19]) / 2)
        else: v = half_up(DE3_M + DE3_S * curve(r, n))
        return v, f"독일 3부 리가 {season} {r}위"
    if lg == "RLSW":
        return 1300, f"독일 4부(레기오날리가 남서부) {season} {r}위 (추정, 다른 선수 자료 독일 4부 1300과 같음)"
    return None

# 순위표·모형이 안 되는 상대(직접 추정)
MAN = {
    (key("Honda Lock"), "2007"): (1150, "일본 4부(규슈 리그) 2007 (추정, 근거 약함: 다른 선수 자료의 아마추어 하부 리그 1150과 같은 수준)"),
}
