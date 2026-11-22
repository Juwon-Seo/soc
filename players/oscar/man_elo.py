# 오스카: 순위표 밖 상대 라벨(build_oscar.py가 exec로 읽음). 값은 라벨에서 tools/league_rank_apply.py로 계산(순위 없음 라벨은 아래 주석).
# 중국 슈퍼리그 2020: 두 조 1단계 뒤 챔피언십·강등 단계 → 영어 위키백과 '2020 Chinese Super League' Final ranking(16팀 최종 순위).
for o_, r_ in (("Beijing Guoan", 3), ("Chongqing Dangdai Lifan", 6), ("Hebei China Fortune", 8), ("Tianjin Teda", 10), ("Qingdao Huanghai", 14), ("Wuhan Zall", 15)):
    man(o_, "2020", f"중국 슈퍼리그 2020 {r_}위/16팀 (두 조 1단계 뒤 챔피언십·강등 단계 최종 순위)")
# 중국 슈퍼리그 2021: 두 조 1단계 뒤 챔피언십 단계(1~8위)·강등 단계(9~16위) → 영어 위키백과 '2021 Chinese Super League' 두 단계 표.
for o_, r_ in (("Shenzhen FC", 6), ("Guangzhou City", 7), ("Hebei FC", 8), ("Shanghai Shenhua", 9), ("Tianjin Jinmen Tiger", 12), ("Wuhan FC", 14), ("Dalian Professional", 15)):
    man(o_, "2021", f"중국 슈퍼리그 2021 {r_}위/16팀 (두 조 1단계 뒤 챔피언십·강등 단계 최종 순위)")
# K리그1 2024: 33라운드 뒤 파이널 A(1~6위)·B(7~12위) → 울산 1위(파이널 A 1위), 광주 9위(파이널 B 3위) (raw/ranks.txt RSK1 2024 group1·group2).
man("Ulsan HD FC", "2024", "한국 1부 2024 1위/12팀 (K League 1, 플레이오프·스플릿 뒤 최종 순위)")
man("Gwangju FC", "2024", "한국 1부 2024 9위/12팀 (K League 1, 플레이오프·스플릿 뒤 최종 순위)")
# AFC 챔스 2017 예선 플레이오프(2017.2.7) 수코타이: 태국 리그 2017 개막(2.11) 전 → 막 끝난 2016 시즌. 2016 타이 리그는 국왕 서거로 31라운드 뒤 중단·종료,
#   최종 순위 7위/18팀(ESPN 순위표 '2016 Thai Premier League': 수코타이 45점 7위, 치앙라이 45점 8위).
FORCE["2819190"] = "태국 1부 2016 7위/18팀 (Thai League 1, 리그 중단 뒤 최종 순위)"
# 리베르타도레스 2011 조별(2011.2.23) 하과레스 데 치아파스: 멕시코 클라우수라 2011 진행 중 → 클라우수라 2011 최종 18위/18팀
#   (raw/tables/tm_MEX1_2010.html 세 조 표를 승점으로 합친 순위: 하과레스 14점 18팀 중 최하위).
man("Jaguares de Chiapas", "2011", "멕시코 1부 2010-11 18위/18팀 (Liga MX Clausura 2011, 경기 날짜에 진행 중이던 단계 순위)")
# 리베르타도레스 2011 조별(2011.3.30) 조르지 윌스테르만: 2010 아페르투라 우승 뒤 2010 시즌 종합으로 강등(RSSSF 'Bolivia 2010' Relegated: Jorge Wilstermann),
#   2011 아데쿠아시온(1부, 1~5월)에 없음(RSSSF 'Bolivia 2011/12' 12팀 표) → 막 끝난 1부 마지막 단계 클라우수라 2010 순위 12위/12팀(ESPN 'Serie A' 2010 순위표 22점 최하위).
man("Club Jorge Wilstermann", "2011", "볼리비아 1부 2010 12위/12팀 (Liga de Fútbol Profesional Boliviano Clausura 2010, 막 끝난 시즌 순위; 2011년 2부 강등)")
# 캄페오나투 가우슈 상대(포르투갈어 위키백과 'Campeonato Brasileiro de Futebol de 2011/2012 - Série C·D' 참가표·종합 순위 표):
#   2012 세리에 C 카시아스 9위/20팀, 2012 세리에 D 주벤투지 14위/40팀. 2011 카노아스, 2012 노부 암부르구·크루제이루(RS)·이피랑가·산타크루스(RS)는 그해 세리에 A~D에 없음(주 리그 전용).
man("SER Caxias do Sul (RS)", "2012", "브라질 3부 2012 9위/20팀 (Campeonato Brasileiro Série C, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)")
man("Esporte Clube Juventude", "2012", "브라질 4부 2012 14위/40팀 (Campeonato Brasileiro Série D, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)")
man("Canoas SC", "2011", "브라질 5부 2011 순위 없음 (Campeonato Gaúcho 2011 (state league); 리그 수준 추정)")
for o_ in ("EC Novo Hamburgo", "EC Cruzeiro", "Ypiranga FC", "FC Santa Cruz"):
    man(o_, "2012", "브라질 5부 2012 순위 없음 (Campeonato Gaúcho 2012 (state league); 리그 수준 추정)")
# 주 리그 전용 팀 값: 브리프 규칙대로 tools/league_rank_apply.py base()(브라질 5부 기준점). 같은 해 기존 자료의 '브라질 5부 … 순위 없음' 값(2011 1292, 2012 1291 —
#   파투·쿠티뉴 선례)은 같은 경기 세리에 C·D 팀(카시아스 1259·주벤투지 1175)보다 높아져 순서가 뒤집히므로 쓰지 않음(judgments.md 6절, 확인 요청).
NORANK_VAL = {}
# 캄페오나투 파울리스타 2025·코파 두 브라질 2025 상대(포르투갈어 위키백과 'Campeonato Brasileiro de Futebol de 2025 - Série C' 종합 순위): 퐁치 프레타 1위·나우치쿠 3위·상베르나르두 4위/20팀.
man("Associação Atlética Ponte Preta", "2025", "브라질 3부 2025 1위/20팀 (Campeonato Brasileiro Série C, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)")
man("Clube Náutico Capibaribe", "2025", "브라질 3부 2025 3위/20팀 (Campeonato Brasileiro Série C, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)")
man("São Bernardo FC", "2025", "브라질 3부 2025 4위/20팀 (Campeonato Brasileiro Série C, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)")
# K리그1 2019 울산 현대: raw/ranks.txt(TM 표)는 울산 1위로 적었으나 우승은 전북(영어 위키백과 '2019 K League 1' Champions: Jeonbuk Hyundai Motors (7th title),
#   K League United 2019.12 기사 — 승점 79 같고 다득점으로 전북) → 울산 2위/12팀.
man("Ulsan Hyundai", "2019", "한국 1부 2019 2위/12팀 (K League 1, 플레이오프·스플릿 뒤 최종 순위)")
