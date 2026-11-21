# elo_diego.py 가 exec 로 읽는 부분: 순위표 보정·리그 모형 보강·직접 추정(MAN). 근거는 judgments.md 6절.

def rank_any_season(prefix, r):
    """같은 리그 다른 시즌 기존 자료의 같은 순위 값(가장 많이 쓴 값) — 시즌과 관계없이 같은 순위값을 쓰는 리그(2. 분데스리가·포르투갈 1부)"""
    c = collections.Counter()
    pat = re.compile("^" + re.escape(prefix) + r" \d{4}-\d\d " + str(r) + "위")
    for x in ENTS:
        if pat.match(x[12] or ""): c[x[2]] += 1
    return c.most_common(1)[0][0] if c else None

def same_season_mid(prefix, season, r):
    """같은 시즌 기존 자료의 앞뒤 순위 값의 가운데(병렬 판정 일치용: 단순 중간값)"""
    tab = {}
    pat = re.compile("^" + re.escape(prefix) + " " + re.escape(season) + r" (\d+)위")
    for x in ENTS:
        m = pat.match(x[12] or "")
        if m: tab.setdefault(int(m.group(1)), x[2])
    if r in tab: return tab[r], None
    lo = [k for k in tab if k < r]; hi = [k for k in tab if k > r]
    a, b = max(lo), min(hi)
    return half_up((tab[a] + tab[b]) / 2), (a, tab[a], b, tab[b])

# ---- 포르투갈 1부 2004-05·2005-06: 기존 자료의 순위별 값(시즌 공통)
def po1(season, r, extra=""):
    v = rank_any_season("포르투갈 1부", r)
    return v, f"포르투갈 1부 {season} {r}위{extra}"
# Transfermarkt 2005-06 표는 경기 성적 순서: 벨레넨스스 13위·나발 15위 → 공식 최종 순위 벨레넨스스 15위(승점 39, 질비센트 행정 강등으로 잔류)·
#   아카데미카 13위·나발 14위(영어 위키백과 2005-06 프리메이라 리가 표 사본·statscrew·fbref 검색 요약)
for nm, s, r in [("SC Braga", "2004-05", 4), ("CD Nacional", "2004-05", 12), ("CF Os Belenenses", "2004-05", 9), ("UD Leiria", "2004-05", 14),
                 ("CD Nacional", "2005-06", 5), ("UD Leiria", "2005-06", 7), ("CF Os Belenenses", "2005-06", 15), ("Naval 1º de Maio", "2005-06", 14)]:
    man(nm, s, *po1(s, r))

# ---- 2. 분데스리가(시즌 공통 순위값)
man("FSV Frankfurt", "2012-13", rank_any_season("2. 분데스리가", 4), "2. 분데스리가 2012-13 4위")
man("VfR Aalen", "2013-14", rank_any_season("2. 분데스리가", 11), "2. 분데스리가 2013-14 11위")

# ---- 쉬페르리그 2014-15(같은 시즌 기존 값 1·2·6·8·9·11·14~18위, 빈 순위는 앞뒤 값의 가운데)
for nm, r in [("Basaksehir FK", 4), ("Mersin Idmanyurdu", 7), ("Kasimpasa", 13)]:
    v, nb = same_season_mid("쉬페르리그", "2014-15", r)
    man(nm, "2014-15", v, f"쉬페르리그 2014-15 {r}위 (같은 시즌 다른 선수 자료 {nb[0]}위 {nb[1]}·{nb[2]}위 {nb[3]}의 중간)")
TR1415_MEAN = 1450   # 같은 시즌 기존 값(1위 1750, 흩어짐 119)에서 역산한 리그 평균
man("Altinordu FK", "2014-15", half_up(TR1415_MEAN - 162 + SD2 * curve(7, 18)), "튀르키예 2부 2014-15 7위 (추정, 쉬페르리그 평균 − 독일 1·2부 평균 차)")
man("Bayburt Grup Özel Idare Genclik Ve Spor", "2014-15", TR1415_MEAN - 324, "튀르키예 3부 2014-15 (추정, 쉬페르리그 평균 − 독일 1·2부 평균 차 × 2, 순위 미확인)")

# ---- 유럽 기타
man("GNK Dinamo Zagreb", "2007-08", 1520, "크로아티아 2007-08 1위 (추정, 다른 선수 자료 디나모 자그레브 2006-07·2009-10 1위 1520과 같음)")
man("Anorthosis Famagusta", "2008-09", 1450, "키프로스 1부 2008-09 3위 (추정, 다른 선수 자료 키프로스 상위권 1450과 같음)")
man("FK Pirmasens", "2006-07", 1300, "독일 4부(오버리가 남서부) 2006-07 (추정, 다른 선수 자료 독일 4부 1300과 같음)")
man("SC Victoria Hamburg", "2010-11", 1180, "독일 5부(오버리가 함부르크) 2010-11 (추정, 다른 선수 자료 독일 5부 1180과 같음)")
man("FC Schönberg 95", "2012-13", 1180, "독일 5부(NOFV-오버리가 북부) 2012-13 (추정, 다른 선수 자료 독일 5부 1180과 같음)")

# ---- 브라질
# 2002 세리에 A: Transfermarkt 표는 단계를 섞은 순서(상파울루 2위). 공식 최종 순위는 결승 토너먼트 결과 순(카카 자료: 산투스 1·코린치안스 2·그레미우 3·
#   플루미넨시 4위) → 상파울루는 1단계 1위·8강에서 산투스에 탈락 → 8강 탈락 팀 중 1단계 최상위 = 5위로 추정
man("São Paulo Futebol Clube", "2002", half_up(1598 + 63 * curve(5, 26)), "브라질 세리에 A 2002 5위 (추정, 1단계 1위·8강 탈락)")
C4 = "다른 선수 자료 4부 이하 1200과 같음"
man("Ji-Paraná FC", "2002", 1200, f"브라질 4부 이하 2002 (추정, 혼도니아 주 리그 팀; {C4})")
man("EC Santo André", "2004", 1370, "브라질 세리에 B 2004 (추정, 순위 미확인 — 승점 12 삭감 시즌, 세리에 B 평균)")
man("União São João EC (SP)", "2004", 1200, f"브라질 세리에 A·B 밖 2004 (추정, 파울리스타 팀; {C4})")
RJ = f"리우 주 리그 하위 팀, 전국 리그 4부 이하 (추정)"   # 비니시우스 자료와 같은 표기·값
for nm, ys in [("Boavista SC", ["2017", "2018", "2019", "2020", "2021", "2022"]), ("Madureira EC", ["2017", "2019", "2020", "2021", "2022"]),
               ("Bangu Atlético Clube (RJ)", ["2019", "2020", "2021", "2022"]), ("Associação Desportiva Cabofriense (RJ)", ["2019", "2020"]),
               ("Americano FC (RJ)", ["2019"]), ("Nova Iguaçu FC (RJ)", ["2022"])]:
    for y in ys: man(nm, y, 1200, RJ)
man("Macaé Esporte Futebol Clube (RJ)", "2017", 1253, "브라질 세리에 C 2017 (추정, 다른 선수 자료 세리에 C 1253과 같음; 그해 세리에 C 강등)")

# ---- 남미 대회 상대(순위표 없음, 모두 추정)
man("CD América de Cali", "2003", 1450, "콜롬비아 1부 2003 (추정, 다른 선수 자료 콜롬비아 상위 팀 1450과 같음)")
man("Club 12 de Octubre de Itauguá", "2003", 1450, "파라과이 1부 2003 (추정, 다른 선수 자료 나시오날 아순시온 1450과 같음)")
man("Club Nacional", "2003", 1600, "우루과이 1부 2002 우승 팀 (추정, 다른 선수 자료 나시오날 우루과이 상위 팀 1600과 같음)")
man("CD Cruz Azul", "2003", 1607, "멕시코 1부 2002-03 (추정, 다른 선수 자료 리가MX 중위권 1607과 같음)")
man("Club Jorge Wilstermann", "2004", 1400, "볼리비아 상위 팀 (추정, 다른 선수 자료 볼리바르 1400과 같음)")
man("LDU Quito", "2004", 1480, "에콰도르 1부 2003 우승 팀 (추정, 다른 선수 자료 에콰도르 상위 팀 1480과 같음)")
man("CA San Lorenzo de Almagro", "2017", 1620, "아르헨티나 1부 2016-17 상위권 (추정, 순위 미확인; 다른 선수 자료 산 로렌소 2014 1620과 같음)")
man("LDU Quito", "2019", 1480, "에콰도르 1부 2018 우승 팀 (추정, 다른 선수 자료 에콰도르 상위 팀 1480과 같음)")
man("Club Deportivo San José", "2019", 1400, "볼리비아 상위 팀 (추정, 다른 선수 자료 볼리바르 1400과 같음)")
man("Racing Club", "2020", 1620, "아르헨티나 1부 2019-20 상위권 (추정, 순위 미확인; 2018-19 우승 팀)")
man("Club Olimpia", "2021", 1480, "파라과이 1부 2021 상위 팀 (추정, 다른 선수 자료 올림피아 2012 1480과 같음)")
man("Independiente Santa Fe", "2018", 1450, "콜롬비아 상위 팀 (추정, 다른 선수 자료 콜롬비아 상위 팀 1450과 같음)")
