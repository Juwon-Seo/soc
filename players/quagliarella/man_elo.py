# 순위표(raw/ranks.txt 세리에A·B)·통합표 밖 상대의 라벨(build_quagliarella.py가 exec로 읽음). 값은 라벨에서 계산(tools/league_rank_apply.py).
# 순위 근거: 이탈리아어 위키백과 Serie C1 2002-2003·2003-2004, Serie C2 2002-2003·2006-2007 'Classifica finale'(raw/ranks_wiki.txt),
# Transfermarkt 순위표 IT3B 2002-03(raw/ranks.txt, 소라 16위는 위키백과와 같음), SE1 2014(raw/ranks.txt), 영어 위키백과 2014 Veikkausliiga(raw/ranks_wiki.txt).
def c1(o, s, r): man(o, s, f"이탈리아 3부 {s} {r}위/18팀 (Serie C1 Girone B, 리그 수준 추정)")
def c2(o, s, r, g): man(o, s, f"이탈리아 4부 {s} {r}위/18팀 (Serie C2 Girone {g}, 리그 수준 추정)")
c2("AS Gualdo Calcio", "2002-03", 11, "B")
c1("Sora Calcio 1907", "2002-03", 16)
for o, r in [("FC Crotone", 2), ("ASD Acireale Calcio", 4), ("FC Sporting Benevento", 5), ("US Sambenedettese", 7), ("Foggia Calcio", 9),
             ("AC Martina 1947", 12), ("Sora Calcio 1907", 13), ("Vis Pesaro 1898", 15), ("Paternò Calcio", 16), ("Taranto SS", 17), ("L'Aquila 1927", 18)]:
    c1(o, "2003-04", r)
c2("Benevento Calcio", "2006-07", 2, "C")   # 2006-07 세리에 C2 조 C(Transfermarkt IT3B 2006-07 표에 없음)
man("IF Brommapojkarna", "2014", "스웨덴 1부 2014 16위/16팀 (Allsvenskan)")
man("HJK Helsinki", "2014", "핀란드 1부 2014 1위/12팀 (Veikkausliiga)")
