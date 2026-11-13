# 상대 Elo: 순위표 모형·직접 추정 (judgments.md 7절). build_gervinho.py가 exec로 읽는다(key·RANKS는 build에서 옴).
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
def half_up(x): return int(x + 0.5)

def rank_model(k, season):
    return None
MAN = {}
