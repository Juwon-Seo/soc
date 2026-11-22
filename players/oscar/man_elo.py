# 오스카: 순위표 밖 상대 라벨(build_oscar.py가 exec로 읽음). 값은 라벨에서 tools/league_rank_apply.py로 계산(순위 없음 라벨은 아래 주석).
# 중국 슈퍼리그 2020: 두 조 1단계 뒤 챔피언십·강등 단계 → 영어 위키백과 '2020 Chinese Super League' Final ranking(16팀 최종 순위).
for o_, r_ in (("Beijing Guoan", 3), ("Chongqing Dangdai Lifan", 6), ("Hebei China Fortune", 8), ("Tianjin Teda", 10), ("Qingdao Huanghai", 14), ("Wuhan Zall", 15)):
    man(o_, "2020", f"중국 슈퍼리그 2020 {r_}위/16팀 (두 조 1단계 뒤 챔피언십·강등 단계 최종 순위)")
# 중국 슈퍼리그 2021: 두 조 1단계 뒤 챔피언십 단계(1~8위)·강등 단계(9~16위) → 영어 위키백과 '2021 Chinese Super League' 두 단계 표.
for o_, r_ in (("Shenzhen FC", 6), ("Guangzhou City", 7), ("Hebei FC", 8), ("Shanghai Shenhua", 9), ("Tianjin Jinmen Tiger", 12), ("Wuhan FC", 14), ("Dalian Professional", 15)):
    man(o_, "2021", f"중국 슈퍼리그 2021 {r_}위/16팀 (두 조 1단계 뒤 챔피언십·강등 단계 최종 순위)")
# K리그1 2024: 33라운드 뒤 파이널 A(1~6위)·B(7~12위) → 울산 1위(파이널 A 1위), 광주 9위(파이널 B 3위) (raw/ranks.txt RSK1 2024 group1·group2).
man("Ulsan HD FC", "2024", "한국 1부 2024 1위/12팀 (K League 1, 플레이오프·스플릿 뒤 최종 순위)")
man("Gwangju FC", "2024", "한국 1부 2024 9위/12팀 (K League 1, 플레이오프·스플릿 뒤 최종 순위)")
# AFC 챔스 2017 예선 플레이오프(2017.2.7) 수코타이: 태국 리그 2017 개막(2.11) 전 → 막 끝난 2016 시즌. 2016 타이 리그는 국왕 서거로 31라운드 뒤 중단·종료,
#   최종 순위 7위/18팀(ESPN 순위표 '2016 Thai Premier League': 수코타이 45점 7위, 치앙라이 45점 8위).
FORCE["2819190"] = "태국 1부 2016 7위/18팀 (Thai League 1, 리그 중단 뒤 최종 순위)"
# 리베르타도레스 2011 조별(2011.2.23) 하과레스 데 치아파스: 멕시코 클라우수라 2011 진행 중 → 클라우수라 2011 최종 18위/18팀
#   (raw/tables/tm_MEX1_2010.html 세 조 표를 승점으로 합친 순위: 하과레스 14점 18팀 중 최하위).
man("Jaguares de Chiapas", "2011", "멕시코 1부 2010-11 18위/18팀 (Liga MX Clausura 2011, 경기 날짜에 진행 중이던 단계 순위)")
