# 케빈 가메이로: 순위표 밖 상대 라벨(build_gameiro.py가 exec로 읽음). 값은 라벨에서 tools/league_rank_apply.py로 계산.
# 쿠프 드 프랑스 아마추어 상대 — 프랑스어 위키백과 쿠프 드 프랑스 시즌 문서(경기표의 리그 표기)와 그 리그 시즌 문서 최종 순위표(judgments.md 7절):
#   FC 오스트발트 2006-07: 'Coupe de France de football 2006-2007' 8라운드 'RC Strasbourg (L2) 6-0 Ostwald (District)' — 디스트릭트(알자스 지역 리그 아래) 리그, 순위표 없음.
#     2006-07 프랑스 단계: 1 리그1, 2 리그2, 3 National, 4 CFA, 5 CFA 2, 6 DH, 7 DHR, 8 PH → 디스트릭트 최상위 = 9부로 봄(추정).
#   가젤렉 아작시오 2006-07: 같은 문서 'Gazélec Ajaccio (CFA)'; 'Championnat de France de football de quatrième division 2006-2007' B조 18팀 중 7위(85점).
#   US 알랑송 2008-09: 'Coupe de France de football 2008-2009' 'US Alençonnaise (CFA 2 (Div 5))'; '...cinquième division 2008-2009' G조 17팀 중 6위(82점).
#   아부안 올랭피크 시농 시네 2023-24: 'Coupe de France de football 2023-2024' 'Avoine OCC (N2)'; '...quatrième division 2023-2024' B조 14팀 중 12위(26점, 강등).
man("FC Ostwald", "2006-07", "프랑스 9부 2006-07 순위 없음 (District (Alsace); 리그 수준 추정)")
man("Gazélec Football Club Olympique Ajaccio", "2006-07", "프랑스 4부 2006-07 7위/18팀 (CFA Groupe B, 리그 수준 추정)")
man("US Alençon 61", "2008-09", "프랑스 5부 2008-09 6위/17팀 (CFA 2 Groupe G, 리그 수준 추정)")
man("Avoine Olympique Chinon Cinais", "2023-24", "프랑스 4부 2023-24 12위/14팀 (National 2 Groupe B, 리그 수준 추정)")
