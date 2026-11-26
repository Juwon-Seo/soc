# 순위표 밖 상대·통합표에 없는 상대 라벨(값은 라벨에서 계산). 순위 출처는 judgments.md '상대 Elo'.
# 코파 두 브라질 2002(바이아): 히우그란지두노르치 주 팀(전국 리그 단계 확인 못 함) → 주 선수권 팀 선례(브라질 5부 순위 없음)
man("Atlético Clube Coríntians (RN)", "2002", "브라질 5부 2002 순위 없음 (Campeonato Potiguar 2002 (state league), 전국 리그 소속 확인 못 함; 리그 수준 추정)")
man("América FC", "2002", "브라질 5부 2002 순위 없음 (América-RN, Campeonato Potiguar 2002 (state league), 전국 리그 소속 확인 못 함; 리그 수준 추정)")
# 코파 델 레이 2015-16 32강: en.wiki 2015-16 Segunda División B 4조 표 12위
man("CF Villanovense", "2015-16", "스페인 3부 2015-16 12위/20팀 (Segunda División B Grupo IV, 리그 수준 추정)")
# 캄페오나투 파울리스타 주 팀(전국 리그 1·2부 밖): 기존 파울리스타 선례 형식(바스투스·네이마르·루카스 모우라 자료)
_PA = lambda y: f"브라질 5부 {y} 순위 없음 (Campeonato Paulista Série A1 {y} (state league); 리그 수준 추정)"
man("EC Água Santa (SP)", "2020", _PA(2020))
man("EC Santo André", "2020", _PA(2020))
man("Osasco Sporting", "2020", _PA(2020))
man("AD São Caetano (SP)", "2021", _PA(2021))
man("EC Santo André", "2021", _PA(2021))
# 수다메리카나 2020 2라운드(2020.11.4): 그때 진행 중이던 코파 데 라 리가 프로페시오날 2020 1단계 4조 최종 4위(en.wiki 표, AFA 출처)
man("CA Lanús", "2020", "아르헨티나 1부 2020-21 4위/4팀 (Copa de la Liga Profesional 2020 (Copa Diego Maradona) Fase de grupos Zone 4, 경기 날짜에 진행 중이던 단계 순위)")
# 리베르타도레스 2021 조별(2021.4.29): 그때 진행 중이던 우루과이 아페르투라 2021 최종 12위(TM URU1 표)
man("CA Rentistas", "2021", "우루과이 1부 2021 아페르투라 12위/16팀 (Torneo Apertura 2021, 경기 날짜에 진행 중이던 단계 순위)")
# 리가MX 2022-23: 기존 '누적' 라벨 형식(지냑 자료) — FotMob 아페르투라 2022 + 클라우수라 2023 정규리그 합산 17위(같은 계산으로 후아레스 13·네카사 14·티후아나 15·마사틀란 18위 = 기존 값)
man("Querétaro FC", "2022-23", "리가MX 2022-23 누적 17위/18팀")
