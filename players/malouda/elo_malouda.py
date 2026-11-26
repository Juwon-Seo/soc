"""플로랑 말루다 상대 Elo: 기존 팀×시즌 값 -> 순위표+기존 리그 순위값 -> 직접 추정"""
import csv, os, re, sys, unicodedata, collections
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ELO = os.path.join(ROOT, "elo")
RAW = os.path.join(HERE, "raw")

def norm(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\(.*?\)", " ", n); n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(n.split())
ALIAS = {}
with open(os.path.join(ELO, "aliases.csv"), encoding="utf-8-sig") as f:
    for row in csv.reader(f):
        if not row or row[0].startswith("팀"): continue
        for part in row[1].split(" / "): ALIAS[norm(part.rsplit(":", 1)[0])] = norm(row[0])
def key(n): k = norm(n); return ALIAS.get(k, k)

TABLE = collections.defaultdict(list)
with open(os.path.join(ELO, "opponent_elo_by_team_season.csv"), encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        TABLE[(key(r["팀"]), r["시즌"])].append((int(r["Elo"]), r["수준 라벨(lv)"]))

RANKS = collections.defaultdict(dict)   # (league, season label) -> team key -> (rank, n)
with open(os.path.join(RAW, "ranks.txt"), encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5 or p[0] == "league": continue
        RANKS[(p[0], p[1].split(" ")[0])][key(p[4])] = (int(p[2]), int(p[3]))

def half_up(x): return int(x + 0.5)

# ---- 프랑스 1부: 기존 순위값 (20팀 / 18팀 시즌별로 모든 선수 자료가 같은 값)
L1_20 = {1: 1955, 2: 1872, 3: 1825, 4: 1792, 5: 1776, 6: 1764, 7: 1750, 8: 1733, 9: 1715, 10: 1699, 11: 1688, 12: 1679,
         13: 1669, 14: 1664, 15: 1655, 16: 1640, 17: 1621, 18: 1610, 19: 1602, 20: 1582}
L1_18 = {1: 1955, 2: 1866, 3: 1817, 4: 1786, 5: 1771, 6: 1757, 7: 1738, 8: 1718, 9: 1700, 10: 1687, 11: 1677, 12: 1667,
         13: 1662, 14: 1647, 15: 1628, 16: 1612, 17: 1603, 18: 1582}
# ---- 프랑스 2부(20팀): 기존 자료의 2008-09·2012-13·2013-14 순위값, 빈 순위는 앞뒤 순위값 직선(가운데)
L2_KNOWN = {2: 1624, 4: 1582, 5: 1573, 6: 1567, 9: 1540, 10: 1532, 11: 1526, 14: 1513, 15: 1508, 16: 1500, 17: 1490,
            18: 1484, 19: 1480, 20: 1469}
def interp(tab, r):
    if r in tab: return tab[r]
    lo = max(k for k in tab if k < r); hi = min(k for k in tab if k > r)
    return half_up(tab[lo] + (tab[hi] - tab[lo]) * (r - lo) / (hi - lo))
def l2_20(r):
    if r == 1: return 1624 + (1624 - 1603)          # 1위: 2위와 3위 보간 차이만큼 위(끝 순위) -> 1645
    if r == 12 or r == 13:
        return interp(dict(L2_KNOWN, **{}), r) if r in (12, 13) else None
    return interp(L2_KNOWN, r)
L2_KNOWN[13] = None
del L2_KNOWN[13]
def l2(r, n):
    if n != 20: sys.exit("프랑스 2부 %d팀 시즌 모형 없음" % n)
    return l2_20(r)

# ---- 튀르키예 2013-14 (18팀): 기존 값 + 사이 직선
TR_1314 = {1: 1778, 3: 1606, 6: 1533, 8: 1485, 9: 1462, 10: 1446, 11: 1434, 16: 1354, 17: 1342, 18: 1317}
# ---- 포르투갈 2009-10 기존 순위값
PT_0910 = {1: 1912, 2: 1786, 3: 1716, 4: 1679, 5: 1660, 6: 1633, 7: 1605, 8: 1578, 9: 1559, 10: 1545, 11: 1531, 12: 1518}
# ---- 이집트 18팀: 튀르키예 2015-16 순위 곡선 + 이집트 평균 1415 (흩어짐 119 동일)
TR_1516 = {1: 1773, 2: 1663, 3: 1602, 4: 1563, 5: 1543, 7: 1505, 8: 1478, 9: 1457, 10: 1442, 11: 1429, 12: 1416,
           13: 1411, 14: 1393, 15: 1369, 16: 1349, 17: 1337, 18: 1312}
TR_1516[6] = 1524
TR_MEAN = sum(TR_1516.values()) / 18
def egy18(r): return half_up(1415 + TR_1516[r] - TR_MEAN)
def isl8(r): return half_up(1300 - (r - 1) * 100 / 7)
def lux14(r): return half_up(1300 - (r - 1) * 100 / 13)
