# 순위표(raw/ranks.txt)·통합표 밖 상대의 라벨(build_jamesrodriguez.py가 exec로 읽음). 값은 라벨에서 tools/league_rank_apply.py로 계산.
# 순위 근거는 judgments.md 'Elo' 절.
man("Monarcas Morelia", "2010", "멕시코 1부 2009-10 7위/18팀 (Liga MX 클라우수라 2010(비센테나리오), 경기 날짜에 진행 중이던 단계의 조별 표를 합친 전체 순위)")
man("Deportivo Cuenca", "2010", "에콰도르 1부 2010 5위/12팀 (Ecuadorian Serie A, 연간 합산 순위)")
man("CSKA Moscow", "2010-11", "러시아 1부 2011-12 3위/16팀 (Russian Premier League, 플레이오프·스플릿 뒤 최종 순위)")
man("Shakhtar Donetsk", "2011-12", "우크라이나 1부 2011-12 1위/16팀 (Ukrainian Premier League)")
man("Zenit St. Petersburg", "2011-12", "러시아 1부 2011-12 1위/16팀 (Russian Premier League, 플레이오프·스플릿 뒤 최종 순위)")
man("Cultural Leonesa", "2016-17", "스페인 3부 2016-17 1위/20팀 (Segunda División B Grupo I, 리그 수준 추정)")
man("Unionistas CF", "2024-25", "스페인 3부 2024-25 15위/20팀 (Primera Federación Grupo 1, 리그 수준 추정)")
man("Independiente Medellín", "2026", "콜롬비아 1부 2026 6위/20팀 (리그 수준 추정)")
# 이름이 겹치는 경기(경기 id): 우루과이 나시오날 2009-10(최종 2위, 결승에서 페냐롤에 짐), 포르투갈 나시오날 2012-13(8위, 카펠 자료와 같은 라벨)
FORCE.update({
    "992059": "우루과이 1부 2009-10 2위/16팀 (Uruguayan Primera División, 결승 뒤 최종 순위)",
    "2283374": "포르투갈 1부 2012-13 8위",
    "2240241": "포르투갈 1부 2012-13 8위",
})
