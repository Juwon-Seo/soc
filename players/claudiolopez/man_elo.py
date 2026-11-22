# 순위표(Elo 통합표에 없는 팀-시즌): 순위는 출처로 확인(judgments.md 6절), 값은 라벨에서 tools/league_rank_apply.py로 계산(build가 exec로 읽음)
# 아르헨티나 1993·1995-96: RSSSF arg93·arg96 최종 순위표(동률은 같은 순위, 크레스포 선례 '라싱 클라우수라 1996 공동 7위')
for o, r in (("CA Independiente", 2), ("CA Vélez Sarsfield", 1), ("CA River Plate", 3)):
    man(o, "1993/Clausura", f"아르헨티나 1부 클라우수라 1993 {r}위/20팀 (코파 센테나리오 1993.6~7월: 직전 끝난 클라우수라 1993 최종 순위, RSSSF)")
for o, r in (("CA Rosario Central", 10), ("CA Independiente", 13), ("Club Estudiantes de La Plata", 9), ("Club Atlético Gimnasia y Esgrima (Jujuy)", 8),
             ("CA Lanús", 2), ("CA Newell's Old Boys", 11), ("CA Boca Juniors", 2), ("CA Colón", 13)):
    man(o, "1995/Apertura", f"아르헨티나 1부 아페르투라 1995 {r}위/20팀")
for o, r in (("AA Argentinos Juniors", 20), ("Club Atlético Belgrano", 13), ("CA River Plate", 14), ("CA Huracán", 7), ("Club Ferro Carril Oeste", 9),
             ("CA Boca Juniors", 5)):
    man(o, "1996/Clausura", f"아르헨티나 1부 클라우수라 1996 {r}위/20팀")
# 아르헨티나 2007: Transfermarkt 순위표(= RSSSF arg07·arg08, 기존 자료 2007 라벨과 같은 순서)
man("Club Estudiantes de La Plata", "2007/Clausura", "아르헨티나 1부 클라우수라 2007 3위/20팀")
man("CD Godoy Cruz Antonio Tomba", "2007/Clausura", "아르헨티나 1부 클라우수라 2007 10위/20팀")
man("CA San Martín (San Juan)", "2007/Apertura", "아르헨티나 1부 아페르투라 2007 19위/20팀")
man("Arsenal FC", "2007/Apertura", "아르헨티나 1부 아페르투라 2007 12위/20팀")
# 유럽 대회 상대(Transfermarkt 순위표, 루마니아는 RSSSF, 러시아 1998은 영어 위키백과 1998 Russian Top Division)
man("FC Bayern Munich", "1996-97", "분데스리가 1996-97 1위")
man("Beşiktaş JK", "1996-97", "튀르키예 1부 1996-97 2위/18팀 (Süper Lig)")
man("Shinnik Yaroslavl", "1998", "러시아 1부 1998 14위/16팀 (Russian Top Division, 인터토토 1998.7월: 진행 중이던 1998 시즌 최종 순위)")
man("Steaua Bucharest", "1998-99", "루마니아 1부 1998-99 3위/18팀 (Divizia A)")
man("Hapoel Haifa", "1999-00", "이스라엘 1부 1999-00 7위/14팀 (Ligat ha'Al)")
man("PSV Eindhoven", "1999-00", "에레디비시 1999-00 1위")
man("PSV Eindhoven", "2001-02", "에레디비시 2001-02 2위")
man("Skoda Xanthi", "2002-03", "그리스 1부 2002-03 9위/16팀 (Alpha Ethniki)")
man("Beşiktaş JK", "2002-03", "튀르키예 1부 2002-03 1위/18팀 (Süper Lig)")
man("FC Porto", "2002-03", "포르투갈 1부 2002-03 1위")
# 멕시코: 스페인어 위키백과 토너먼트 문서 '테이블 헤네랄'(정규 단계 전체 순위), 경기 날짜에 진행 중이던 토너먼트(리길야는 그 토너먼트)
MX = {("Apertura", 2004): {"Dorados de Sinaloa": 17, "Club Necaxa": 11, "CF Pachuca": 3, "Tigres UANL": 8},
      ("Clausura", 2005): {"Jaguares de Chiapas": 12, "CF Monterrey": 7, "Monarcas Morelia": 1, "Deportivo Guadalajara": 10, "UNAM Pumas": 16,
                           "Tigres UANL": 9, "Atlas Guadalajara": 18, "Santos Laguna": 6, "CD Cruz Azul": 2, "Tecos de la UAG": 4},
      ("Apertura", 2005): {"Club Necaxa": 3, "Club San Luis": 15, "Tigres UANL": 8},
      ("Clausura", 2006): {"Deportivo Toluca": 6, "CD Cruz Azul": 3},
      ("Apertura", 2006): {"Tiburones Rojos de Veracruz": 9, "Club Atlético Morelia": 12, "Atlas Guadalajara": 6}}
MXKO = {"Apertura": "아페르투라", "Clausura": "클라우수라"}
for (st_, y), t in MX.items():
    s = f"{y}-{str(y + 1)[2:]}" if st_ == "Apertura" else f"{y - 1}-{str(y)[2:]}"
    for o, r in t.items():
        man(o, f"{s}/{st_}", f"멕시코 1부 {s} {r}위/18팀 (Liga MX {MXKO[st_]} {y}, 경기 날짜에 진행 중이던 단계의 전체 순위)")
# 콜롬비아 2005(수다메리카나 9월): RSSSF col05 Copa Mustang II(피날리사시온) 정규 단계 11위/18팀
man("Atlético Nacional", "2005", "콜롬비아 1부 2005 11위/18팀 (Copa Mustang II 피날리사시온, 경기 날짜에 진행 중이던 단계 순위)")
# MLS 2008·2009: 영어 위키백과 시즌 표(서포터스 실드 전체 순위; 기존 자료 값과 순서 같음)
for o, r in (("Chicago Fire", 3), ("Columbus Crew", 1), ("Los Angeles Galaxy", 13), ("New York Red Bulls", 8), ("CD Chivas USA", 4)):
    man(o, "2008", f"MLS 2008 {r}위/14팀")
for o, r in (("New York Red Bulls", 15), ("New England Revolution", 7), ("Los Angeles Galaxy", 2), ("Houston Dynamo", 3), ("D.C. United", 10)):
    man(o, "2009", f"MLS 2009 {r}위/15팀")
# US 오픈컵 2008 캐롤라이나 레일호크스: RSSSF usa08 USL 퍼스트 디비전 2008 8위/11팀
man("Carolina RailHawks FC", "2008", "USL 2008 8위/11팀 (USL First Division, 리그 수준 추정)")
