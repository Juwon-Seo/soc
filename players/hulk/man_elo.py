# 헐크 상대 라벨(순위 출처는 judgments.md 5절). build_hulk.py가 exec로 읽음.

# ── 페널티(감점) 시즌: elo/penalty_seasons.json — 감점 전 순위
PEN = {}
for c_ in json.load(open(os.path.join(ELO, "penalty_seasons.json"), encoding="utf-8"))["changes"]:
    PEN[(c_["line"].split(" [")[0], key(c_["team"]))] = (c_["official"], c_["onfield"])

def br_label(o, y, state=None):
    """브라질 클럽의 그해 전국 리그 단계 순위(세리에 A·B는 TM 순위표, C·D는 포르투갈어 위키백과 최종 순위)."""
    for lg, nm in (("BRA1", "브라질 세리에 A"), ("BRA2", "브라질 세리에 B")):
        t = RANKS.get((lg, y), {})
        for n_ in nm_cands(o):
            if key(n_) in t:
                r, n, _ = t[key(n_)]
                pe = PEN.get((f"{nm} {y}", key(n_)))
                if pe and pe[0] == r: return f"{nm} {y} {pe[1]}위/{n}팀 (감점 전 순위)"
                return f"{nm} {y} {r}위/{n}팀"
    return None

# TM 경기 이름 → TM 순위표 이름(같은 클럽의 그 시즌 이름)
NAME_ALIAS.update({
 "Thespa Gunma": "Thespa Kusatsu", "Hokkaido Consadole Sapporo": "Consadole Sapporo", "Associação Naval 1893": "Naval 1º de Maio",
 "Spartak Vladikavkaz": "Alania Vladikavkaz", "Akhmat Grozny": "Terek Grozny",
 "Shandong Taishan": "Shandong Luneng Taishan", "Tianjin Tianhai": ["Tianjin Quanjian", "Tianjin Tianhai (-2019)"],
 "Guizhou FC": ["Guizhou Hengfeng Zhicheng", "Guizhou Hengfeng"], "Shanghai Shenhua": "Shanghai Greenland Shenhua",
 "Guangzhou City": "Guangzhou R&F", "Dalian Professional": "Dalian Yifang", "Wuhan Yangtze": "Wuhan Zall",
 "Guangzhou FC": "Guangzhou Evergrande Taobao", "Jiangsu FC": "Jiangsu Suning", "Hebei FC": "Hebei China Fortune",
 "Henan FC": "Henan Jianye", "Chongqing Liangjiang Athletic": ["Chongqing Dangdai Lifan", "Chongqing Lifan"], "Liaoning FC": "Liaoning FC",
 "Changchun Yatai": "Changchun Yatai", "Tianjin Jinmen Tiger": "Tianjin Teda", "Beijing Guoan": "Beijing Guoan",
 "Shenzhen FC": "Shenzhen FC", "Zhejiang FC": "Hangzhou Greentown", "Cangzhou Mighty Lions": "Shijiazhuang Ever Bright",
 "Qingdao FC": "Qingdao Huanghai", "Ulsan HD FC": "Ulsan Hyundai",
})
man("Sydney FC", "2019-04-23", "호주 A리그 2018-19 2위/10팀")   # 2019 AFC 조별 4월: A리그 2018-19 정규리그 2위(통합표 값)

# ── 일본: 일왕배 2006 3라운드 상대 신닛테쓰 오이타 = 규슈 사회인 리그(4부) 2위/9팀(RSSSF Japan Fourth and Lower Levels 2006)
man("Nippon Steel Oita FC", "2006-10-08", "일본 4부 2006 2위/9팀 (Kyushu Soccer League 지역 리그, RSSSF 최종 순위, 리그 수준 추정)")   # 신닛테쓰 오이타(실업팀, 오이타 트리니타 아님)

# ── 포르투갈 하부 리그(타사 드 포르투갈 상대; 영어 위키백과 시즌 문서, 승점 표는 elo/league_points_other.json)
man("Sertanense FC", "2008-10-18", "포르투갈 4부 2008-09 1위/14팀 (Terceira Divisão Série D 1단계 순위(승격 조 순위 미확인), 리그 수준 추정)")
man("CD Cinfães", "2008-12-14", "포르투갈 4부 2008-09 5위/14팀 (Terceira Divisão Série C, 승격 조 뒤 최종 순위, 리그 수준 추정)")
man("Sertanense FC", "2009-10-17", "포르투갈 3부 2009-10 9위/16팀 (Segunda Divisão Zona Centro, 리그 수준 추정)")
man("AD Limianos", "2010-10-16", "포르투갈 4부 2010-11 2위/12팀 (Terceira Divisão Série A, 승격 조 뒤 최종 순위, 리그 수준 추정)")
man("CD Pinhalnovense", "2011-01-12", "포르투갈 3부 2010-11 4위/16팀 (Segunda Divisão Zona Sul, 리그 수준 추정)")

# ── 챔스 예선 노르셸란(TM DK1 2013-14 표; 덴마크 시즌 7월 시작 → 경기 날짜의 시즌)
man("FC Nordsjælland", "2013-07-30", "덴마크 1부 2013-14 6위/12팀 (Danish Superliga)", "2013-08-07")
# ── 중국 슈퍼리그 2020 스자좡 융창(TM 이름 Cangzhou Mighty Lions): 강등 단계 15·16위전 패배 → 최종 16위(영어 위키백과 2020 CSL)
man("Cangzhou Mighty Lions", "2020-01-01", "중국 슈퍼리그 2020 16위/16팀 (두 조 1단계 뒤 챔피언십·강등 단계 최종 순위)", "2020-12-31")

# ── 남미 대회 상대(경기 날짜에 진행 중이던 단계)
man("CD América de Cali", "2021-04-27", "콜롬비아 1부 2021 아페르투라 8위/19팀 (Torneo Apertura 2021 1단계, 경기 날짜에 진행 중이던 단계 순위)", "2021-05-13")
man("Deportivo La Guaira", "2021-04-21", "베네수엘라 1부 2021 1위/7팀 (Liga FUTVE 2021 1단계 중부 조, 경기 날짜에 진행 중이던 단계 순위)", "2021-05-25")
man("CA River Plate", "2021-08-11", "아르헨티나 1부 2021 1위/26팀", "2021-08-18")   # Liga Profesional 2021(7~12월) 우승
man("Independiente del Valle", "2022-04-26", "에콰도르 1부 2022 3위/16팀 (Ecuadorian Serie A, 연간 합산 순위)", "2022-05-19")
man("CS Emelec", "2022-06-28", "에콰도르 1부 2022 6위/16팀 (Ecuadorian Serie A, 연간 합산 순위)", "2022-07-05")
man("Carabobo FC", "2023-02-22", "베네수엘라 1부 2023 5위/15팀 (Liga FUTVE 2023 1단계, 경기 날짜에 진행 중이던 단계 순위)", "2023-03-01")
man("Millonarios FC", "2023-03-08", "콜롬비아 1부 2023 아페르투라 2위/20팀 (Torneo Apertura 2023 1단계, 경기 날짜에 진행 중이던 단계 순위)", "2023-03-15")
man("Club Alianza Lima", "2023-05-01", "페루 1부 2023 1위/19팀 (Liga 1 Torneo Apertura 2023, 경기 날짜에 진행 중이던 단계 순위)", "2023-06-30")
man("CA Peñarol", "2024-04-01", "우루과이 1부 2024 아페르투라 1위/16팀 (Torneo Apertura 2024, 경기 날짜에 진행 중이던 단계 순위)", "2024-04-30")
man("Caracas FC", "2024-04-01", "베네수엘라 1부 2024 11위/14팀 (Liga FUTVE 아페르투라 2024 1단계, 경기 날짜에 진행 중이던 단계 순위)", "2024-05-31")
man("Club Cienciano", "2025-04-01", "페루 1부 2025 10위/19팀 (Liga 1 Torneo Apertura 2025, 경기 날짜에 진행 중이던 단계 순위)", "2025-06-30")
man("Atlético Bucaramanga", "2025-07-17", "콜롬비아 1부 2025 피날리사시온 4위/20팀 (Torneo Finalización 2025 1단계, 경기 날짜에 진행 중이던 단계 순위)", "2025-07-25")
man("CD Godoy Cruz Antonio Tomba", "2025-08-14", "아르헨티나 1부 클라우수라 2025 29위/30팀", "2025-08-21")   # 통합표 같은 팀·시즌 라벨
man("Independiente del Valle", "2025-10-21", "에콰도르 1부 2025 1위/16팀 (LigaPro Serie A 2025 1단계, 경기 날짜에 진행 중이던 단계 순위)", "2025-10-28")
man("Club Atlético Platense", "2026-09-08", "아르헨티나 1부 클라우수라 2026 19위/30팀 (두 조 통합 순위, 클라우수라 2026 1단계 최종)", "2026-09-15")

# ── 미네이루·코파 두 브라질 상대: 그해 전국 리그 단계(세리에 B는 위키백과 표, C·D는 포르투갈어 위키백과 'Classificação geral'),
#    전국 리그에 없던 팀은 브라질 5부 순위 없음(guerrero 선례)
BR_LOW = {
 ("Uberlândia EC", "2021"): "브라질 4부 2021 7위/68팀",
 ("Tombense Futebol Clube (MG)", "2021"): "브라질 3부 2021 2위/20팀",
 ("Tombense Futebol Clube (MG)", "2022"): "브라질 세리에 B 2022 15위/20팀",
 ("Cruzeiro Esporte Clube", "2022"): "브라질 세리에 B 2022 1위/20팀",
 ("AA Caldense", "2022"): "브라질 4부 2022 61위/64팀",
 ("Tombense Futebol Clube (MG)", "2023"): "브라질 세리에 B 2023 18위/20팀",
 ("CA Patrocinense", "2023"): "브라질 4부 2023 13위/64팀",
 ("Athletic Club", "2023"): "브라질 4부 2023 3위/64팀",
 ("Athletic Club", "2024"): "브라질 3부 2024 2위/20팀",
 ("Tombense Futebol Clube (MG)", "2025"): "브라질 3부 2025 20위/20팀",
 ("Maringá FC", "2025"): "브라질 3부 2025 11위/20팀",
 ("Tocantinópolis EC", "2025"): "브라질 4부 2025 48위/64팀",
 ("Itabirito FC", "2025"): "브라질 4부 2025 58위/64팀",
}
BR_SFX = {"3": "Campeonato Brasileiro Série C", "4": "Campeonato Brasileiro Série D"}
for (o_, y_), lv_ in BR_LOW.items():
    t_ = re.match(r"브라질 (\d)부", lv_)
    if t_: lv_ += f" ({BR_SFX[t_.group(1)]}, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)"
    man(o_, f"{y_}-01-01", lv_, f"{y_}-12-31")
BR_STATE5 = {("Coimbra Esporte Clube Ltda (MG)", "2021"), ("CA Patrocinense", "2022"), ("Athletic Club", "2022"), ("AA Caldense", "2023"),
             ("Itabirito FC", "2024"), ("Democrata FC", "2023"), ("EC Democrata", "2024"), ("Villa Nova AC", "2025"), ("Itabirito FC", "2026")}
for (o_, y_) in BR_STATE5: man(o_, f"{y_}-01-01", f"브라질 5부 {y_} 순위 없음 (Campeonato Mineiro {y_} (state league); 리그 수준 추정)", f"{y_}-12-31")

# ── 코파 데 라 리가 2024(4월, 진행 중 단계) 로사리오 센트랄: A조 11위/14팀(영어 위키백과 2024 Copa de la Liga Profesional·승점 표)
FIXED = {}
man("CA Rosario Central", "2024-04-10", "아르헨티나 리가 컵 2024 조 11위/14팀 (Copa de la Liga Profesional 2024 A조, 경기 날짜에 진행 중이던 단계 순위)")

# TM 순위표가 틀린 시즌(우승 팀): K리그1 2019 전북 우승(울산과 승점 79 동률, 다득점 72-71; 승점 표 elo/league_points_other.json 1위),
# 러시아 2015-16 스파르타크 5위·로코모티프 6위(승점 표; TM 표는 둘이 바뀜, 통합표 로코모티프 6위)
man("Jeonbuk Hyundai Motors", "2019-01-01", "K리그1 2019 1위/12팀 (K League 1)", "2019-12-31")
man("Spartak Moscow", "2015-07-01", "러시아 1부 2015-16 5위/16팀 (Russian Premier League)", "2016-06-30")
# 승점 표 map 줄 직접 지정(이름 비슷도로 잘못 고르는 경우): (라벨 앞부분, 데이터 이름 키) -> (표 이름, [표, 행])
MAP_OVERRIDE = {
 ("아르헨티나 1부 2021", "CA River Plate@1"): ("Club Atlético River Plate", [3, 0]),   # 리가 프로페시오날 2021 최종 표(기존 'CA River Plate' 키는 코파 데 라 리가 A조 행)
 ("중국 슈퍼리그 2020", "Cangzhou Mighty Lions@16"): ("Shijiazhuang Ever Bright", [3, 5]),   # B조 6위(최종 16위)
 ("K리그1 2019", "Jeonbuk Hyundai Motors"): ("Jeonbuk Hyundai Motors", [0, 0]),
 ("러시아 1부 2015-16", "Spartak Moscow"): ("Spartak Moscow", [0, 4]),
}
man("Spartak Moscow", "2013-07-01", "러시아 1부 2013-14 6위/16팀 (Russian Premier League)", "2014-06-30")   # TM 표 5위 — 최종 6위(크라스노다르 5위, 승점 표)
