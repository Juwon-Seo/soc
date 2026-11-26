# 게레로 상대 라벨(순위 출처는 judgments.md 5절). build_guerrero.py가 exec로 읽음.
NAME_ALIAS.update({"Lovech": "Litex Lovech"})   # TM 'Lovech' = 리텍스 로베치(판데르파르트 같은 경기)

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
                if (lg, y, o) == ("BRA1", "2013", "Coritiba Foot Ball Club"):   # 플라멩구·포르투게자 −4점 되돌리면 11위 → 13위(감점 목록에 빠진 밀린 팀)
                    return f"{nm} {y} 13위/{n}팀 (감점 전 순위)"
                pe = PEN.get((f"{nm} {y}", key(n_)))
                if pe and pe[0] == r: return f"{nm} {y} {pe[1]}위/{n}팀 (감점 전 순위)"
                return f"{nm} {y} {r}위/{n}팀"
    return None

# 세리에 C·D(포르투갈어 위키백과 'Classificação geral'), 전국 리그 밖 주 리그 팀(브라질 5부 순위 없음)
BR_LOW = {
 ("Fortaleza Esporte Clube", "2016"): "브라질 3부 2016 6위/20팀 (Campeonato Brasileiro Série C, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)",
 ("Paysandu SC", "2019"): "브라질 3부 2019 5위/20팀 (Campeonato Brasileiro Série C, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)",
 ("Boavista SC", "2016"): "브라질 4부 2016 43위/68팀 (Campeonato Brasileiro Série D, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)",
 ("AA Portuguesa", "2016"): "브라질 4부 2016 45위/68팀 (Campeonato Brasileiro Série D, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)",
 ("SER Caxias do Sul (RS)", "2019"): "브라질 4부 2019 6위/68팀 (Campeonato Brasileiro Série D, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)",
 ("EC Pelotas", "2020"): "브라질 4부 2020 36위/68팀 (Campeonato Brasileiro Série D, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)",
 ("CE Aimoré", "2021"): "브라질 4부 2021 53위/68팀 (Campeonato Brasileiro Série D, 플레이오프·스플릿 뒤 최종 순위, 리그 수준 추정)",
}
BR_STATE5 = {   # 그해 세리에 A~D 어디에도 없던 팀(포르투갈어 위키백과 세리에 D 참가 팀 목록에 없음)
 ("Osasco Sporting", "2013"): "Campeonato Paulista Série A1 2013", ("Clube Atlético Linense (SP)", "2013"): "Campeonato Paulista Série A1 2013",
 ("Paulista FC (SP)", "2014"): "Campeonato Paulista Série A1 2014", ("Nacional FC", "2014"): "Campeonato Amazonense 2014",
 ("Marília AC (SP)", "2015"): "Campeonato Paulista Série A1 2015", ("Resende FC", "2016"): "Campeonato Carioca 2016",
 ("Bangu Atlético Clube (RJ)", "2016"): "Campeonato Carioca 2016", ("Nova Iguaçu FC (RJ)", "2017"): "Campeonato Carioca 2017",
 ("CE Aimoré", "2020"): "Campeonato Gaúcho 2020", ("Esportivo", "2020"): "Campeonato Gaúcho 2020",
}
for (o_, y_), lv_ in BR_LOW.items(): man(o_, f"{y_}-01-01", lv_, f"{y_}-12-31")
for (o_, y_), st_ in BR_STATE5.items(): man(o_, f"{y_}-01-01", f"브라질 5부 {y_} 순위 없음 ({st_} (state league); 리그 수준 추정)", f"{y_}-12-31")

# ── 유럽 대회 상대(TM 순위표)
man("Unirea Urziceni", "2008-10-02", "루마니아 1부 2008-09 1위/18팀 (Liga I)")
man("Galatasaray", "2009-03-12", "쉬페르리그 2008-09 5위/18팀", "2009-03-19")
man("Randers FC", "2009-07-30", "덴마크 1부 2009-10 10위/12팀 (Danish Superliga)")   # 덴마크 2009-10 시즌은 7월 18일 시작(진행 중 시즌)
# ── 클럽 월드컵 2012 준결승 알아흘리: 이집트 리그 2011-12 중단(포트사이드 참사)·2012-13 취소 → 순위 없음
man("Al Ahly FC", "2012-12-12", "이집트 프리미어리그 2012-13 순위 없음 (리그 중단·취소; 리그 수준 추정)")
# ── 남미 대회 상대
man("Club Deportivo San José", "2013-02-20", "볼리비아 1부 2012-13 3위/12팀 (Liga de Fútbol Profesional Boliviano, 경기 날짜에 진행 중이던 단계 순위)")   # 파투 같은 시즌 라벨
man("Once Caldas", "2015-02-04", "콜롬비아 1부 2015 13위/20팀 (Torneo Apertura 2015 1단계, 경기 날짜에 진행 중이던 단계 순위)")
man("CD Palestino", "2016-09-21", "칠레 1부 2016-17 6위/16팀 (Chilean Primera División (Apertura 2016), 경기 날짜에 진행 중이던 단계 순위)")
man("CD Universidad Católica", "2017-05-03", "칠레 1부 2016-17 4위/16팀 (Chilean Primera División (Clausura 2017), 경기 날짜에 진행 중이던 단계 순위)")
man("CD Palestino", "2019-04-09", "칠레 1부 2019 3위/16팀 (Chilean Primera División)")
man("Club Nacional", "2019-07-24", "우루과이 1부 2019 연간 1위/16팀", "2019-07-31")
man("Deportes Tolima", "2020-02-26", "콜롬비아 1부 2020 2위/20팀 (Torneo Apertura 2020 1단계, 경기 날짜에 진행 중이던 단계 순위)")
man("CD Universidad Católica", "2020-03-03", "칠레 1부 2020 1위/18팀 (Chilean Primera División)")
man("CD Ñublense", "2023-04-05", "칠레 1부 2023 12위/16팀 (Chilean Primera División)", "2023-08-10")
man("Defensa y Justicia", "2023-09-27", "아르헨티나 1부 2023 리가 3위/28팀")
man("CA Unión (Santa Fe)", "2023-03-17", "아르헨티나 1부 2023 리가 20위/28팀")
man("CS General San Martín (Formosa)", "2023-02-22", "아르헨티나 3부 2023 순위 없음 (Torneo Federal A 2023; 리그 수준 추정)")
man("CA Talleres", "2025-04-22", "아르헨티나 1부 아페르투라 2025 통합 24위/30팀 (2025 연간 통합 순위)")
man("Club Libertad Asunción", "2025-05-27", "파라과이 1부 2025 아페르투라 1위/12팀 (Copa de Primera 아페르투라 2025, 경기 날짜에 진행 중이던 단계 순위)")

# ── 에콰도르 2023(연간 합산 순위, 기존 LDU 라벨과 같은 형식)
EC23 = {"Independiente del Valle": 3, "Técnico Universitario": 8, "Libertad FC": 13, "Cumbayá FC": 14}
for o_, r_ in EC23.items(): man(o_, "2023-07-01", f"에콰도르 1부 2023 {r_}위/16팀 (Ecuadorian Serie A, 연간 합산 순위)", "2023-12-31")

# ── 페루 Liga 1: 경기 날짜에 진행 중이던 단계(아페르투라·클라우수라) 순위(TM 단계 표, 영어 위키백과·FotMob 대조)
def pe_stage(d):
    o_ = d[:4]
    ap = {"2024": "2024-07-15", "2025": "2025-07-20", "2026": "2026-07-01"}[o_]
    return ("TDeA", "Apertura") if d < ap else ("TDeC", "Clausura")
PE_TEAMS = {"TDeA|2025": 19, "TDeC|2025": 18}
def pe_label(o, d):
    lg, st = pe_stage(d); y = d[:4]
    if (o, d) == ("Club Sporting Cristal", "2025-12-06"):   # 2025 플레이오프(두 단계 뒤): 연간 합산 순위
        return "페루 1부 2025 4위/19팀 (Liga 1 2025 연간 합산 순위)"
    if (o, y, st) == ("FC Cajamarca", "2026", "Clausura"):   # 진행 중 단계: FotMob 현재 순위(14점 동률, 득실 차 −19로 로스 찬카스 −18 아래)
        return "페루 1부 2026 16위/18팀 (Liga 1 Torneo Clausura 2026, 2026년 11월 25일 현재 순위)"
    t = RANKS.get((lg, y), {})
    for n_ in nm_cands(o):
        if key(n_) in t:
            r, n, _ = t[key(n_)]
            if (o, y, st) == ("Sport Huancayo", "2026", "Apertura"):   # UTC −5점 되돌린 감점 전 순위(TM 표 순서, 위키백과 공식 16위)
                return f"페루 1부 2026 {r}위/{n}팀 (감점 전 순위; Liga 1 Torneo Apertura 2026, 경기 날짜에 진행 중이던 단계 순위)"
            n = PE_TEAMS.get(f"{lg}|{y}", n)
            return f"페루 1부 {y} {r}위/{n}팀 (Liga 1 Torneo {st} {y}, 경기 날짜에 진행 중이던 단계 순위)"
    return None
man("Danubio FC", "2015-03-17", "우루과이 1부 2014-15 연간 4위/16팀 (추정, 다른 선수 자료 우루과이 연간 3위 1613·5위 1586의 중간)", "2015-04-01")   # 파투·바스투스 같은 시즌 라벨(통합표 값)
