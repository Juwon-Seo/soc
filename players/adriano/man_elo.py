# 직접 추정(MAN): 통합표에 없는 팀-시즌. 값 = 리그 시즌 목표 평균(tools/league_*_normalize.py) + 흩어짐 × 순위 곡선, 또는 브라질 하부 평탄값.
# 근거(순위·소속 리그)는 judgments.md 6절.
# 브라질 하부: 세리에 C 1253·4부 이하 1200 + 그해 브라질 1부 목표 평균 이동(2008 +3, 2010 +81, 2012 +91 — 기존 2010·2012 값과 같음)
man("River AC", "2001", 1253, "브라질 세리에 C (추정)")                       # 2001 세리에 C 참가(영어 위키백과 2001 Série C)
man("Guaratinguetá (SP)", "2008", 1256, "브라질 세리에 C (추정)")             # 2008 세리에 C 참가(파울리스타 2008 성적으로 출전)
for o in ("Rio Claro Futebol Clube (SP)", "Sertãozinho Futebol Clube (SP)", "CA Juventus (SP)"):
    man(o, "2008", 1203, "브라질 4부 이하 (추정)")                            # 2008 세리에 A·B·C 명단에 없음
for o in ("Bangu Atlético Clube (RJ)", "Americano FC (RJ)", "Olaria AC", "EC Tigres do Brasil (RJ)", "América Football Club (RJ)"):
    man(o, "2010", 1281, "브라질 4부 이하 (추정)")                            # 2010 세리에 A~C 밖(아메리카-RJ는 세리에 D), 기존 2010 값과 같음
man("Botafogo FC", "2012", 1291, "브라질 4부 이하 (추정)")                    # 보타포구-SP 2012 세리에 A~D 밖, 기존 2012 값과 같음
# 남미(league_world_normalize 목표 평균 + 흩어짐 × 곡선)
man("Audax Italiano", "2008", 1529, "칠레 1부 2008 연간 합산 6위/20팀 (리그 수준 추정)")
man("Sportivo Luqueño", "2008", 1457, "파라과이 1부 2008 연간 합산 10위/12팀 (리그 수준 추정)")
man("Club Nacional", "2008", 1547, "우루과이 1부 2008 (2007-08 시즌 연간 3위/16팀, 리그 수준 추정)")
man("CD Universidad Católica", "2010", 1687, "칠레 1부 2010 1위/18팀 (리그 수준 추정)")
man("Club Universidad de Chile", "2010", 1624, "칠레 1부 2010 4위/18팀 (리그 수준 추정)")
man("Caracas FC", "2010", 1440, "베네수엘라 1부 2009-10 종합 2위/18팀 (리그 수준 추정)")
man("Club The Strongest", "2014", 1572, "볼리비아 1부 2013-14 아페르투라 1위/12팀 (리그 수준 추정)")
# 유럽(league_era_normalize 목표 평균 + 흩어짐 × 곡선)
man("CSKA Moscow", "2002", 1568, "러시아 2002 2위 (리그 수준 추정, 2001-02·2002-03 목표 평균의 가운데)")
man("Wisla Kraków", "2002-03", 1630, "폴란드 2002-03 1위 (리그 수준 추정)")
man("Metalurg Donetsk", "2003-04", 1581, "우크라이나 2003-04 4위 (리그 수준 추정)")
man("FC Basel 1893", "2004-05", 1726, "스위스 2004-05 1위 (리그 수준 추정)")
man("Shakhtar Donetsk", "2005-06", 1813, "우크라이나 2005-06 1위 (리그 수준 추정)")
