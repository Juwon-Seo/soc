# 순위표(raw/ranks.txt) 밖 상대: 순위는 출처로 확인(judgments.md 'Elo·순위' 절), 값은 라벨에서 tools/league_rank_apply.py로 계산
# 브라질 세리에 A: 영어 위키백과 시즌 문서 'Final standings' 표(raw/ranks_wiki.txt)
man("Criciúma EC", "1988", "브라질 세리에 A 1988 23위/24팀")
man("Goiás EC", "1990", "브라질 세리에 A 1990 10위/20팀")
man("CR Flamengo", "1992", "브라질 세리에 A 1992 1위/20팀")
man("Botafogo de Futebol e Regatas", "1992", "브라질 세리에 A 1992 2위/20팀")
man("Portuguesa", "1992", "브라질 세리에 A 1992 16위/20팀")
# 유럽 대회 상대(영어 위키백과 시즌 문서 순위표)
man("Crusaders FC", "1993-94", "북아일랜드 1부 1993-94 4위/16팀 (Irish League)")
man("Hutnik Krakow", "1996-97", "폴란드 1부 1996-97 16위/18팀 (I liga)")
man("HJK Helsinki", "1999", "핀란드 1부 1999 2위/12팀 (Veikkausliiga)")
man("ASK Inter Slovnaft Bratislava", "2000-01", "슬로바키아 1부 2000-01 1위/10팀 (Slovak Superliga)")
man("Club Brugge KV", "2001-02", "벨기에 1부 2001-02 2위/18팀 (First Division)")
man("1. FC Brno", "2003-04", "체코 1부 2003-04 14위/16팀 (Gambrinus liga; Transfermarkt 표는 13위)")
# 프랑스 하부 리그 컵 상대(RSSSF France 1994/95·2001/02, FFF AS 모나코 컵 기록)
man("Stade Poitevin FC (inactif)", "1994-95", "프랑스 3부 1994-95 2위/18팀 (National 1 Groupe A, 리그 수준 추정)")
man("La Vitréenne FC", "1994-95", "프랑스 9부 1994-95 순위 없음 (Promotion de Ligue (Bretagne); 리그 수준 추정)")
man("US Saint-Malo", "2001-02", "프랑스 5부 2001-02 9위/16팀 (CFA 2 Groupe G, 리그 수준 추정)")
# 카타르 스타스리그: RSSSF 최종 순위(qat05·qat06, 10팀)
Q05 = ["Al-Gharafa", "Al-Rayyan SC", "Al-Khor SC", "Qatar SC", "Al-Arabi SC", "Al-Wakrah SC", "Al-Sadd SC", "Al-Ahli SC", "Al-Shamal SC", "Al-Kharaitiyat SC"]
Q06 = ["Al-Sadd SC", "Qatar SC", "Al-Arabi SC", "Al-Rayyan SC", "Al-Ahli SC", "Al-Gharafa", "Al-Khor SC", "Al-Wakrah SC", "Al-Shamal SC", "Al-Sailiya SC"]
for _s, _L in (("2004-05", Q05), ("2005-06", Q06)):
    for _i, _t in enumerate(_L, 1):
        man(_t, _s, f"카타르 {_s} {_i}위/10팀 (Qatar Stars League, 리그 수준 추정)")
