# 통합표 밖 상대의 순위 라벨(build_veron.py가 exec로 읽음). 값은 라벨에서 tools/league_rank_apply.py로 계산 — judgments.md 6절.
# 아르헨티나 1부 상대는 raw/ranks.txt(Transfermarkt 반시즌 표)로 자동 라벨(기존 자료와 같은 공동 순위 표기), 고칠 것만 RANK_FIX.
RANK_FIX[("ARG1", "2008-09", key("Club Atlético Tigre"))] = (2, 20, "아페르투라 2008: 보카·티그레·산로렌소 승점 같아 3팀 결정 리그 → 보카 우승, 티그레 2위(리켈메 판정과 같음; TM 표는 셋 다 1위)")
man("Wisla Kraków", "1998-99", "엑스트라클라사 1998-99 1위/16팀")                                   # TM 표·위키백과 승점 표 1위(우승)
man("Feyenoord Rotterdam", "1999-00", "에레디비시 1999-00 3위/18팀")                               # TM 표·승점 표 3위
man("Danubio FC", "2007-08", "우루과이 1부 2008 12위/16팀 (Primera División – Torneo Clausura 2008, 경기 날짜에 진행 중이던 단계 순위)")   # RSSSF uru08·TM URUC 12위
man("Deportivo Quito", "2008-09", "에콰도르 1부 2009 4위/12팀 (Ecuadorian Serie A, 연간 합산 순위; 결승에서 이겨 2009 우승)")   # RSSSF ecua09 Aggregate Table 4위
man("Club Libertad Asunción", "2008-09", "파라과이 1부 2009 1위/12팀 (Paraguayan Primera División, 연간 합산 순위)")   # RSSSF para09 Aggregate 1위(82점)
man("Defensor Sporting Club", "2008-09", "우루과이 1부 2009 1위/15팀 (Primera División – Torneo Clausura 2009, 경기 날짜에 진행 중이던 단계 순위)")   # RSSSF uru09 Clausura winners·TM URUC 1위
man("Bolívar La Paz", "2009-10", "볼리비아 1부 2010 5위/12팀 (Liga de Fútbol Profesional Boliviano Apertura 2010, 경기 날짜에 진행 중이던 단계 순위; 6팀 결승 리그 5위)")   # RSSSF bol2010
man("Club Alianza Lima", "2009-10", "페루 1부 2010 3위/16팀 (Torneo Descentralizado (Peruvian Primera División), 연간 합산 순위)")   # RSSSF peru2010 Aggregate 3위
man("San Luis FC", "2009-10", "리가MX 2009-10 18위/18팀 (Liga MX 클라우수라 2010(비센테나리오), 경기 날짜에 진행 중이던 단계의 조별 표를 합친 전체 순위)")   # 영어 위키백과 2009-10 시즌 문서 Bicentenario 표 18위
man("Club Guaraní", "2010-11", "파라과이 1부 2011 6위/12팀 (Paraguayan Primera División, 연간 합산 순위)")   # RSSSF para2011 아페르투라 4위 34점 + 클라우수라 9위 24점 = 58점, 루비오 뉴와 같고 득실 −1 vs −3; 승점 표도 6위
man("Barcelona SC Guayaquil", "2016-17", "에콰도르 1부 2017 3위/12팀 (감점 전 순위; Ecuadorian Serie A, 연간 합산 순위)")   # RSSSF ecua2017 Tabla Anual 5위 67점[-6] → 감점 전 73점 3위
