# 손으로 정한 라벨(순위는 모두 출처 확인, judgments.md 6절). build_ennervalencia.py가 exec로 읽음
NAME_ALIAS.update({
    "Independiente del Valle": "Independiente José Terán", "Deportivo Guadalajara": ["Chivas", "Guadalajara"], "Club Atlético Morelia": "Atlético Morelia",
    "Jaguares FC": "Jaguares Chiapas", "Tiburones Rojos de Veracruz": "Veracruz", "CD Olmedo": "Olmedo", "CD Espoli": "ESPOLI", "Imbabura SC": "Imbabura",
    "CD Universidad Católica": "Universidad Católica", "LDU de Loja": "Liga de Loja", "LDU Quito": "LDU Quito", "Técnico Universitario": "Técnico Universitario",
})
# 페루 1부(영어 위키백과 시즌 문서 최종 합산 표, 기존 알리안사 리마 2010 라벨 형식)
man("Universidad San Martín de Porres", "2010-01-01", "페루 1부 2010 1위/16팀 (Torneo Descentralizado (Peruvian Primera División), 연간 합산 순위)", "2010-12-31")
man("Sport Huancayo", "2013-01-01", "페루 1부 2013 11위/16팀 (Torneo Descentralizado (Peruvian Primera División), 연간 합산 순위)", "2013-12-31")
# 파라과이 1부 2012 아페르투라(경기 날짜에 진행 중이던 단계): 기존 라벨 그대로(영어 위키백과 아페르투라 표도 2위)
man("Club Olimpia", "2012-02-01", "파라과이 1부 2012 아페르투라 2위/12팀 (추정)", "2012-06-30")
# 코스타리카 1부 클라우수라 정규리그(영어 위키백과 2017–18·2018–19 Liga FPD), 론돈 에레디아노 2024 라벨 형식
man("CS Herediano", "2018-01-01", "코스타리카 1부 2017-18 1위/12팀 (Liga FPD 클라우수라 2018, 경기 날짜에 진행 중이던 단계의 정규리그 순위)", "2018-06-30")
man("Deportivo Saprissa", "2019-01-01", "코스타리카 1부 2018-19 2위/12팀 (Liga FPD 클라우수라 2019, 경기 날짜에 진행 중이던 단계의 정규리그 순위)", "2019-06-30")
# 멕시코 2부 아페르투라 2018 정규리그(영어 위키백과 2018–19 Ascenso MX), 기존 코레카미노스 라벨 형식
man("Atlético de San Luis", "2018-07-01", "멕시코 2부 2018-19 5위/15팀 (Ascenso MX, 경기 날짜에 진행 중이던 아페르투라 2018 단계 순위, 리그 수준 추정)", "2018-12-31")
# 핀란드 1부 2021(영어 위키백과 2021 Veikkausliiga: 챔피언십 라운드 뒤 우승)
man("HJK Helsinki", "2021-01-01", "핀란드 1부 2021 1위/12팀 (Veikkausliiga, 플레이오프·스플릿 뒤 최종 순위)", "2021-12-31")
# 튀르키예 하부 리그(Transfermarkt 표: 2. Lig 크르므즈 조 2021-22, 1. Lig 2022-23)
man("Afyonspor", "2021-08-01", "튀르키예 3부 2021-22 8위/20팀 (TFF Second League Red Group, 리그 수준 추정)", "2022-07-31")
man("Caykur Rizespor", "2022-08-01", "튀르키예 2부 2022-23 2위/19팀", "2023-07-31")
# 아르헨티나 1부 2023(Transfermarkt 표, 카바니 형식), 볼리비아 1부 2023(영어 위키백과 2023 FBF División Profesional 단일 리그 표)
man("CA River Plate", "2023-01-01", "아르헨티나 1부 2023 리가 1위/28팀", "2023-12-31")
man("Bolívar La Paz", "2023-01-01", "볼리비아 1부 2023 2위/17팀 (FBF División Profesional, 연간 합산 순위)", "2023-12-31")
# 캄페오나투 가우슈 상대: 그해 전국 리그(세리에 C·D) 최종 순위(포르투갈어 위키백과 Classificação geral), 전국 리그 밖 팀은 브라질 5부 기준값(오스카 형식)
for o_, y_, lv_ in (
    ("EC Avenida", "2024", "브라질 4부 2024 30위/64팀 (Campeonato Brasileiro Série D, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)"),
    ("EC Novo Hamburgo", "2024", "브라질 4부 2024 32위/64팀 (Campeonato Brasileiro Série D, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)"),
    ("Nova Iguaçu FC (RJ)", "2024", "브라질 4부 2024 10위/64팀 (Campeonato Brasileiro Série D, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)"),
    ("Ypiranga FC", "2024", "브라질 3부 2024 7위/20팀 (Campeonato Brasileiro Série C, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)"),
    ("FC Santa Cruz", "2024", "브라질 5부 2024 순위 없음 (Campeonato Gaúcho 2024 (state league); 리그 수준 추정)"),
    ("EC São Luiz", "2024", "브라질 5부 2024 순위 없음 (Campeonato Gaúcho 2024 (state league); 리그 수준 추정)"),
    ("Grêmio Esportivo Brasil (RS)", "2025", "브라질 4부 2025 43위/64팀 (Campeonato Brasileiro Série D, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)"),
    ("EC São Luiz", "2025", "브라질 4부 2025 52위/64팀 (Campeonato Brasileiro Série D, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)"),
    ("SER Caxias do Sul (RS)", "2025", "브라질 3부 2025 5위/20팀 (Campeonato Brasileiro Série C, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)"),
):
    man(o_, y_ + "-01-01", lv_, y_ + "-12-31")
