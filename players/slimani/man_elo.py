# 순위표 밖 상대 직접 라벨(build_slimani.py가 exec로 읽음). 출처는 judgments.md 5절.
# 알제리 1부 2009-10 WA 틀렘센: 공식 8위/18팀이지만 CA 보르지 부 아레리지 승점 3 감점(13승 10무 = 49점 → 46점, 영어 위키백과 시즌 문서 adjust_points)
#   → 감점 전 순위는 BBA가 46점 두 팀(WA 틀렘센·CR 벨루이즈다드) 위로 올라가 WA 틀렘센 9위(사용자 규칙 v1.287)
man("WA Tlemcen", "2009-10", "알제리 1부 2009-10 9위/18팀 (감점 전 순위; Championnat National, 리그 수준 추정)")
# 알제리 2부 2011-12(2011.12.30 알제리컵 64강): ES 모스타가넴 6위/16팀(RSSSF alg2012 Ligue Professionnelle 2 최종 순위표, CA BBA 1위·JS 사우라 2위)
man("ES Mostaganem", "2011-12", "알제리 2부 2011-12 6위/16팀 (Algerian Ligue Professionnelle 2, 리그 수준 추정)")
# 알제리 2부 2012-13(2013.3.5 알제리컵 16강): CRB 아인 프크룬 1위/16팀(RSSSF alg2013 Ligue Professionnelle 2 최종 순위표 'CRB Ain Fekroun 30 17 6 7 43-25 57 Promoted')
man("CRB Aïn Fakroun", "2012-13", "알제리 2부 2012-13 1위/16팀 (Algerian Ligue Professionnelle 2, 리그 수준 추정)")
# 말리 1부 2009-10(2010.7.31 CAF 컨페더레이션컵 플레이오프 2차전): 졸리바 AC 2위/14팀(RSSSF mali2010 최종 순위표, 스타드 말리앵 우승)
man("Djoliba AC", "2009-10", "말리 1부 2009-10 2위/14팀 (Malian Première Division, 리그 수준 추정)")
# 이집트 프리미어리그 2012-13(2013.2 UAFA 클럽컵 8강): 이스마일리 2조 2위/9팀(영어 위키백과 시즌 문서 = RSSSF egy2013; 2013.7 쿠데타로 시즌 중단, 챔피언 플레이오프 미개최 → 중단 시점 순위)
man("Ismaily SC", "2012-13", "이집트 프리미어리그 2012-13 2위/9팀 (2조, 2013년 7월 시즌 중단 시점 순위)")
# MC 데브다브(베샤르 주) 2012-13: 리그·단계를 출처로 찾지 못함(알제리360 기사 '모데스트 팀', 2024-25 RSSSF 베샤르 지역 리그) → 순위 없음, 지역 리그(5부) 기준점
MAN_ELO[(key("MC Debdaba"), "2012-13")] = ("알제리 5부 2012-13 순위 없음 (MC Debdaba, 리그·단계 확인 못 함 — 지역 리그 추정, 리그 수준 추정)", "Algeria", 5, 2013)
