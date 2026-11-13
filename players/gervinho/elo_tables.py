# 상대 Elo: 순위표 모형·직접 추정 (judgments.md 7절). build_gervinho.py가 exec로 읽는다(key·RANKS는 build에서 옴).
# 순위 곡선(CURVE): 기존 league_model.py와 같은 21칸 곡선(페리시치·발부에나 elo 표와 같은 식)
SA = [1969, 1890, 1845, 1814, 1798, 1787, 1774, 1757, 1740, 1725, 1714, 1705, 1697, 1692, 1683, 1668, 1651, 1640, 1632, 1614]
CV = [(v - 1739) / 91.3 for v in SA]
def curve(r, n):
    p = (r - 1) / (n - 1) * 19
    i = min(int(p), 18); t = p - i
    return CV[i] + (CV[i + 1] - CV[i]) * t
def half_up(x): return int(x + 0.5)

# 벨기에 1부 2005-06·2006-07(18팀): 기존 자료의 벨기에 1부 모형(데 브라위너·페리시치: 평균 + 119 × 곡선) 중
# 가장 가까운 18팀 시즌인 2008-09 평균 1439.6을 그대로 씀(그 시즌 UEFA 계수가 없어 '추정').
# 순위: TM 최종 순위표(우승 안더레흐트 두 시즌 확인) + 동률은 승수(2005-06 베스테를로 13승 9위·FC 브뤼셀 12승 10위, 영어 위키백과 표).
BE_MEAN = 1439.6
BE_FIX = {("2005-06", "KVC Westerlo"): 9, ("2005-06", "FC Molenbeek Brüssel"): 10}

# 중국 슈퍼리그(16팀): 드록바 자료의 2012 모형(평균 1484·흩어짐 63) 순위별 값 그대로(포를란 2014 선례),
# 기존 값이 없는 순위는 이웃 순위 값의 직선 보간(5·6위: 4위 1526~7위 1489, 14위: 13위 1433·15위 1411의 가운데)
CN_FIX = {4: 1526, 5: 1514, 6: 1501, 7: 1489, 10: 1458, 11: 1452, 12: 1446, 13: 1433, 14: 1422, 15: 1411, 16: 1397}

# 그리스 1부: 발부에나 자료의 회귀 그대로(평균 = 1473 + 23.33 × (앞뒤 3시즌 UEFA 계수 평균 − 7.3333) + 보정 GR_K, 흩어짐 119)
def reg_mean(coefs): return 1473 + 23.33 * (sum(coefs) / len(coefs) - 7.3333)
GR_COEF = {2018: 5.1, 2019: 4.9, 2020: 5.1, 2021: 8.0, 2022: 2.125, 2023: 11.4, 2024: 12.688}
def gr_reg(start):
    ys = (start - 1, start, start + 1) if start + 1 in GR_COEF else (start - 2, start - 1, start)
    return reg_mean([GR_COEF[y] for y in ys])
GR_ANCH = [(2019, 1, 1680), (2020, 1, 1690), (2021, 2, 1590)]
GR_K = sum(v - (gr_reg(y) + 119 * curve(r, 14)) for y, r, v in GR_ANCH) / len(GR_ANCH)
# 2022-23 공식 최종 순위(플레이오프·플레이아웃 뒤, 영어 위키백과 raw/wiki/gr_2022_23.html): 12 라미아·13 이오니코스·14 레바디아코스
GR_FINAL = {"2022-23": {"PAS Lamia 1964": 12, "Ionikos Nikea": 13}}

# 쉬페르리그 2021-22(20팀): 외질 자료와 같은 회귀(계수 2020 3.1·2021 6.7·2022 11.8, 평균 1469.9), 흩어짐 119, TM 최종 순위(우승 트라브존스포르)
TR_COEF = {2020: 3.1, 2021: 6.7, 2022: 11.8}
def tr_mean(start):
    c = sum(TR_COEF[y] for y in (start - 1, start, start + 1)) / 3
    return 1473 + 23.33 * (c - 7.3333)

def rank_model(k, season):
    for (s, t), r in BE_FIX.items():
        if s == season and key(t) == k:
            return half_up(BE_MEAN + 119 * curve(r, 18)), f"벨기에 1부 {season} {r}위 (추정, 다른 선수 자료 벨기에 1부 2008-09 모형과 같은 수준)"
    t = RANKS.get(("BE1", season))
    if t and k in t:
        r, n = t[k]
        return half_up(BE_MEAN + 119 * curve(r, n)), f"벨기에 1부 {season} {r}위 (추정, 다른 선수 자료 벨기에 1부 2008-09 모형과 같은 수준)"
    t = RANKS.get(("CSL", season))
    if t and k in t:
        r, n = t[k]
        same = "같음" if r in (4, 7, 10, 11, 12, 13, 15, 16) else "사이 보간"
        return CN_FIX[r], f"중국 슈퍼리그 {season} {r}위 (추정, 다른 선수 자료 중국 슈퍼리그 2012 순위별 값과 {same})"
    for nm, r in GR_FINAL.get(season, {}).items():
        if key(nm) == k:
            return half_up(gr_reg(int(season[:4])) + GR_K + 119 * curve(r, 14)), f"그리스 슈퍼리그 {season} {r}위 (리그 수준 추정)"
    t = RANKS.get(("TR1", season))
    if season == "2021-22" and t and k in t:
        r, n = t[k]
        return round(tr_mean(2021) + 119 * curve(r, n)), f"쉬페르리그 {season} {r}위"
    return None

# 순위표 모형 밖: 기존 선수 자료의 같은 리그·같은 순위 값 또는 직접 추정
MAN = {
    (key("FC Lorient"), "2010-11"): (1689, "리그1 2010-11 11위"),                       # 기존 10위 1699·12위 1679의 가운데(TM 최종 11위, 승점 49 동률 중 득실차)
    (key("Feyenoord Rotterdam"), "2014-15"): (1642, "에레디비시 2014-15 4위"),          # 기존 에레디비시 4위 고정값
    (key("Venezia FC"), "2019-20"): (1564, "세리에B 2019-20 11위"),                      # 기존 세리에B 11위 값(1994-95·2022-23 1564, 같은 시즌 12위 1559·16위 1538과 같은 줄)
    (key("Chamois Niortais FC"), "2007-08"): (1484, "리그2 2007-08 18위"),               # 기존 리그2 18위 값(2012-13 등 1484)
    (key("Stade Lavallois"), "2007-08"): (1344, "프랑스 3부(나시오날) 2007-08 5위 (추정, 다른 선수 자료 나시오날 5위 1344와 같음)"),
    (key("SC Selongey"), "2007-08"): (1150, "프랑스 5부(CFA2) 2007-08 F조 11위/14팀 (추정, 다른 선수 자료 프랑스 5부 1150과 같음)"),
}
