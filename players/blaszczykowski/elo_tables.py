# 상대 Elo: 순위표 모형·직접 추정 (judgments.md 7절). build_blaszczykowski.py가 exec로 읽는다.
# 엑스트라클라사 공식 최종 순위(위키백과 영어·폴란드어, 출처 90minut.pl). Transfermarkt 표와 다른 시즌은 이 표가 우선.
#  2005-06: 승점 동률은 상대 전적(자글렘비에 3·아미카 4, 디스코볼리아 7·크라코비아 8·베우하투프 9·포곤 10),
#           레흐 포즈난은 라이선스 미신청으로 최하위(16위)로 옮겨짐 → 비스와 프워츠크 11·폴로니아 15.
#  2018-19: 챔피언십 라운드 뒤 최종 순위(크라코비아 4·야기엘로니아 5, 승점 57 동률 상대 전적).
#  2019-20: 강등 라운드 뒤 최종 순위(구르니크 자브제 9·라쿠프 10·자글렘비에 11).
PL_OFFICIAL = {
    "2004-05": ["Wisla Kraków", "Dyskobolia Grodzisk Wielkopolski", "Legia Warszawa", "Wisla Plock", "Cracovia", "Amica Wronki",
                "Gornik Leczna", "Lech Poznań", "Pogon Szczecin", "Polonia Warsaw", "Górnik Zabrze", "Zaglebie Lubin",
                "Odra Wodzislaw Slaski", "GKS Katowice"],
    "2005-06": ["Legia Warszawa", "Wisla Kraków", "Zaglebie Lubin", "Amica Wronki", "Korona Kielce", "Odra Wodzislaw Slaski",
                "Dyskobolia Grodzisk Wielkopolski", "Cracovia", "GKS Belchatow", "Pogon Szczecin", "Wisla Plock", "Gornik Leczna",
                "Górnik Zabrze", "Arka Gdynia", "Polonia Warsaw", "Lech Poznań"],
    "2006-07": ["Zaglebie Lubin", "GKS Belchatow", "Legia Warszawa", "Cracovia", "Dyskobolia Grodzisk Wielkopolski", "Lech Poznań",
                "Korona Kielce", "Wisla Kraków", "LKS Lodz", "Odra Wodzislaw Slaski", "Arka Gdynia", "Widzew Lodz", "Gornik Leczna",
                "Górnik Zabrze", "Wisla Plock", "Pogon Szczecin"],
    "2018-19": ["Piast Gliwice", "Legia Warszawa", "Lechia Gdansk", "Cracovia", "Jagiellonia Bialystok", "Zaglebie Lubin",
                "Pogon Szczecin", "Lech Poznań", "Wisla Kraków", "Korona Kielce", "Górnik Zabrze", "Slask Wroclaw", "Arka Gdynia",
                "Wisla Plock", "Miedz Legnica", "Zaglebie Sosnowiec"],
    "2019-20": ["Legia Warszawa", "Lech Poznań", "Piast Gliwice", "Lechia Gdansk", "Slask Wroclaw", "Pogon Szczecin", "Cracovia",
                "Jagiellonia Bialystok", "Górnik Zabrze", "Raków Częstochowa", "Zaglebie Lubin", "Wisla Plock", "Wisla Kraków",
                "Arka Gdynia", "Korona Kielce", "LKS Lodz"],
    "2020-21": ["Legia Warszawa", "Raków Częstochowa", "Pogon Szczecin", "Slask Wroclaw", "Warta Poznan", "Piast Gliwice",
                "Lechia Gdansk", "Zaglebie Lubin", "Jagiellonia Bialystok", "Górnik Zabrze", "Lech Poznań", "Wisla Kraków",
                "Wisla Plock", "Cracovia", "Stal Mielec", "Podbeskidzie Bielsko-Biala"],
}
# 폴란드 UEFA 국가 계수(시즌 점수, kassiesa.net 국가 순위표 2008·2009·2022·2023): 시작 연도 → 점수
PL_COEF = {2003: 4.125, 2004: 2.500, 2005: 1.125, 2006: 2.625, 2007: 1.666, 2008: 5.000, 2009: 2.125, 2010: 4.500,
           2017: 2.875, 2018: 2.250, 2019: 2.125, 2020: 4.000, 2021: 4.625, 2022: 7.750}
def pl_mean(season):
    y = int(season[:4])
    c = (PL_COEF[y - 1] + PL_COEF[y] + PL_COEF[y + 1]) / 3
    return 1473 + 23.33 * (c - 7.333)   # 튀르키예·우크라이나·노르웨이와 같은 계수 회귀(레반도프스키 2007-08~2009-10 값 재현)
# 16팀 순위 간격: 기존 레반도프스키 자료 2008-09·2009-10 순위값 − 그 시즌 평균(두 시즌 평균). 8·15위는 앞뒤 순위의 가운데
OFF16 = {1: 158.72, 2: 94.70, 3: 60.68, 4: 41.72, 5: 32.70, 6: 19.20, 7: 4.70, 8: -6.80, 9: -18.30, 10: -26.30,
         11: -32.32, 12: -38.30, 13: -51.30, 14: -65.30, 15: -76.05, 16: -86.80}
def off(r, n):
    if n == 16: return OFF16[r]
    x = 1 + (r - 1) * 15 / (n - 1)          # 14팀 시즌(2004-05): 같은 상대 위치의 16팀 값을 직선 보간
    a = int(x); f = x - a
    return OFF16[a] if f == 0 else OFF16[a] + f * (OFF16[a + 1] - OFF16[a])
PL_RANK = {}
for s, lst in PL_OFFICIAL.items():
    for i, t in enumerate(lst): PL_RANK[(key(t), s)] = (i + 1, len(lst))
def model(lg, season, r, n):
    return None
def pl_model(k, season):
    if (k, season) not in PL_RANK: return None
    r, n = PL_RANK[(k, season)]
    return int(round(pl_mean(season) + off(r, n))), f"엑스트라클라사 {season} {r}위"

# 순위표·모형이 안 되는 상대(직접 추정, 모두 '추정')
MAN = {
    (key("FC Basel 1893"), "2006-07"): (1600, "스위스 2006-07 2위 (추정, 다른 선수 자료 바젤 2005-06 2위 1600과 같음)"),
}
RANK_LG = []
