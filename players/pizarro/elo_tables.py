# 상대 Elo: 순위표 모형·직접 추정 (judgments.md 7절). build_pizarro.py가 exec로 읽는다.
# 분데스리가 18팀 순위값(기존 자료의 1992~2026 모든 시즌에서 같음)
L1_CURVE = {1: 2006, 2: 1912, 3: 1860, 4: 1828, 5: 1812, 6: 1797, 7: 1777, 8: 1756, 9: 1737, 10: 1723,
            11: 1713, 12: 1702, 13: 1697, 14: 1682, 15: 1661, 16: 1644, 17: 1634, 18: 1613}
RANK_LG = ["L1"]

def model(lg, season, r, n):
    if lg == "L1" and n == 18:
        return L1_CURVE[r], f"분데스리가 {season} {r}위"
    return None

MAN = {}
