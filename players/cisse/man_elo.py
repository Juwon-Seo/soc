# 순위표 밖 상대 라벨(build_cisse.py가 exec로 읽음). 값은 라벨에서 tools/league_rank_apply.py로 계산.
# 쿠프 드 프랑스 아마추어 상대(Transfermarkt 순위표 없음) — 프랑스어 위키백과 시즌 문서 최종 순위표:
#   방 OC 2000-01: CFA(4부) C조 18팀 중 7위(82점, 'Championnat de France de football de quatrième division 2000-2001', 방 OC 문서 시즌표 7위와 같음)
#   CSO 암네빌 2002-03: CFA 2(5부) C조 16팀 중 5위(78점, 'Championnat de France de football de cinquième division 2002-2003')
man("Vannes OC", "2000-01", "프랑스 4부 2000-01 7위/18팀 (CFA Groupe C, 리그 수준 추정)")
man("CSO Amnéville", "2002-03", "프랑스 5부 2002-03 5위/16팀 (CFA 2 Groupe C, 리그 수준 추정)")
# 그리스 슈퍼리그 2010-11 공식 최종 순위(영어 위키백과 시즌 문서, 슈퍼리그 징계 위원회 결정 195/2011): 이라클리스는 서류 위조로 최하위(16위)로 내려가
#   Transfermarkt 표(이라클리스 11위)와 아래 순위가 다름 → 케르키라 12위·라리사 14위·판세라이코스 15위·이라클리스 16위.
#   (올림피아코스 볼로스·카발라의 승부 조작 강등 결정은 항소로 취소, 2011-12 승점 삭감 → 5위·7위 그대로)
man("Iraklis Thessaloniki", "2010-11", "그리스 1부 2010-11 16위/16팀 (Super League Greece, 서류 위조 징계로 최하위 처리된 공식 최종 순위)")
man("AO Kerkyra", "2010-11", "그리스 1부 2010-11 12위/16팀 (Super League Greece)")
man("AE Larisa", "2010-11", "그리스 1부 2010-11 14위/16팀 (Super League Greece)")
man("Panserraikos", "2010-11", "그리스 1부 2010-11 15위/16팀 (Super League Greece)")
# 러시아 프리미어리그 2013-14: 크라스노다르·스파르타크 모스크바 승점 50 동률, 공식 순위 크라스노다르 5위(유로파리그 진출, 영어 위키백과) — Transfermarkt 표는 6위
man("FC Krasnodar", "2013-14", "러시아 1부 2013-14 5위/16팀 (Russian Premier League)")
