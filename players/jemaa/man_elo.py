# 순위표에서 정한 상대 라벨(build_jemaa.py가 exec로 읽음). man(상대, 시즌 키, 라벨). 출처는 judgments.md 5절.
# 시즌 키: 8월 1일 기준 'YYYY-YY' 또는 달력 연도 'YYYY'(build의 seasons_for가 두 키를 차례로 찾음).
KW = "Kuwaiti Premier League, 리그 수준 추정"
# 튀니지 1부 2004-05(영어 위키백과 시즌 문서 = RSSSF tun05 최종 순위; Transfermarkt 표는 EGS 가프사 8위·EOG 크람 9위로 승자승 순서가 틀림)
man("EGS Gafsa", "2004-05", "튀니지 1부 2004-05 9위/14팀 (Tunisian Ligue Professionnelle 1, 리그 수준 추정)")
man("Club Africain", "2004-05", "튀니지 1부 2004-05 3위/14팀 (Tunisian Ligue Professionnelle 1, 리그 수준 추정)")
man("EO Goulette et Kram", "2004-05", "튀니지 1부 2004-05 6위/14팀 (Tunisian Ligue Professionnelle 1, 리그 수준 추정)")
# 수단 1부 2005(2월 16일 개막, 2005.3.19 경기 때 진행 중): 알힐랄 옴두르만 우승(RSSSF soed05 최종 순위 1/12)
man("Al-Hilal Club (Omdurman)", "2005", "수단 1부 2005 1위/12팀 (Sudan Premier League, 리그 수준 추정)")
# 스웨덴 1부 2005(알스벤스칸, Transfermarkt = 영어 위키백과): 할름스타드 10/14
man("Halmstads BK", "2005", "스웨덴 1부 2005 10위/14팀")
# 리그2 2006-07: 크레테유 18/20(Transfermarkt = 승점 표 순서)
man("US Créteil Football", "2006-07", "리그2 2006-07 18위/20팀")
# 키프로스 1부 2006-07: 에스니코스 아흐나 4/14(Transfermarkt = 영어 위키백과)
man("Ethnikos Achna", "2006-07", "키프로스 1부 2006-07 4위/14팀")
# 덴마크 1부 2006-07: 오덴세 4/12(Transfermarkt = 승점 표 OB 4위)
man("Odense Boldklub", "2006-07", "덴마크 1부 2006-07 4위/12팀 (Danish Superliga)")
# 리그2 2008-09(영어 위키백과 = Transfermarkt): 스트라스부르 4, 브레스트 14, 아미앵 18
man("RC Strasbourg Alsace", "2008-09", "리그2 2008-09 4위/20팀")
man("Stade Brestois 29", "2008-09", "리그2 2008-09 14위/20팀")
man("Amiens SC", "2008-09", "리그2 2008-09 18위/20팀")
# AFC 대회 상대(시즌은 경기 날짜에 진행 중이던 시즌의 최종 순위; 2014.2 우즈베키스탄은 3월 개막 전이라 끝난 2013 시즌)
man("Al-Wehdat SC", "2012-13", "요르단 1부 2012-13 2위/12팀 (Jordanian Pro League, 리그 수준 추정)")
man("Al-Ettifaq FC", "2012-13", "사우디 프로리그 2012-13 6위/14팀")
man("Regar-TadAZ Tursunzoda", "2013", "타지키스탄 1부 2013 4위/11팀 (Tajikistan Higher League, 리그 수준 추정)")
man("Riffa SC", "2012-13", "바레인 1부 2012-13 4위/8팀 (Bahraini Premier League, 리그 수준 추정)")
man("Riffa SC", "2013-14", "바레인 1부 2013-14 1위/10팀 (Bahraini Premier League, 리그 수준 추정)")
man("New Radiant SC", "2013", "몰디브 1부 2013 1위/8팀 (Dhivehi Premier League, 리그 수준 추정)")
man("East Bengal FC", "2013-14", "인도 1부 2013-14 2위/13팀 (I-League)")
man("Lokomotiv Tashkent", "2013-14", "우즈베키스탄 1부 2013 2위/14팀 (리그 수준 추정)")
man("Al-Jaish SC", "2013-14", "시리아 1부 2014 1위/18팀 (Syrian Premier League, 조별 리그 뒤 챔피언십 플레이오프 우승, 리그 수준 추정)")
# 쿠웨이트 1부(영어 위키백과 시즌 문서; 2012-13 살리비카트 6위·살미야 7위는 RSSSF와 순서가 다르나 살미야가 7위로 승강 플레이오프에 나감 — 쿠우라 238606)
for o, r in (("Al-Salibikhaet SC", 6), ("Kazma SC", 8), ("Al-Salmiya SC", 7), ("Al-Nasr SC Kuwait", 4), ("Al-Arabi SC Kuwait", 3), ("Al-Jahra SC", 5)):
    man(o, "2012-13", f"쿠웨이트 1부 2012-13 {r}위/8팀 ({KW})")
man("Al-Sahel SC Kuwait", "2012-13", "쿠웨이트 2부 2012-13 5위/6팀 (Kuwaiti Division One, 리그 수준 추정)")   # RSSSF kuw2013 1부 리그 최종 순위
for o, r in (("Qadsia SC", 1), ("Al-Jahra SC", 3), ("Al-Arabi SC Kuwait", 5), ("Al-Salmiya SC", 6), ("Al-Tadhamon SC", 7), ("Al-Nasr SC Kuwait", 8),
             ("Khaitan SC", 9), ("Al-Salibikhaet SC", 11), ("Al-Shabab SC Kuwait", 12), ("Al-Sahel SC Kuwait", 13)):
    man(o, "2013-14", f"쿠웨이트 1부 2013-14 {r}위/14팀 ({KW})")
# 카타르 1부 2014-15(Transfermarkt = 영어 위키백과 = RSSSF qat2015)
for o, r in (("Qatar SC", 4), ("Al-Khor SC", 10), ("Al-Shahania SC", 13), ("Al-Ahli SC", 5), ("Al-Gharafa SC", 7), ("Al-Sadd SC", 2), ("Umm Salal SC", 6), ("Al-Arabi SC", 8)):
    man(o, "2014-15", f"카타르 1부 2014-15 {r}위/14팀 (Qatar Stars League)")
