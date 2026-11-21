# 상대 Elo: 순위표 + 리그 순위별 값, 직접 추정 (judgments.md 7절). build_bellarabi.py가 exec로 읽는다(key·RANKS는 build에서 옴).

# 3. 리가 2010-11: 공식 최종 순위(영어 위키백과 2010-11 3. Liga, raw/wiki/tier_2010_11_3__Liga.html; 출처 kicker).
# Transfermarkt 표(raw/ranks.txt)는 승점순이라 자격 박탈로 20위가 된 알렌을 17위로, 부르크하우젠·브레멘 II·바이에른 II를
# 18·19·20위로 적음 → 공식 순위를 씀(알렌은 기존 통합표 값을 그대로 씀, judgments.md 7절).
L3_1011 = {"FC Hansa Rostock": 2, "SG Dynamo Dresden": 3, "SV Wehen Wiesbaden": 4, "Rot-Weiß Erfurt": 5, "1.FC Saarbrücken": 6,
           "Kickers Offenbach": 7, "SSV Jahn Regensburg": 8, "1.FC Heidenheim 1846": 9, "VfB Stuttgart II": 10,
           "TuS Koblenz": 11, "SV Sandhausen": 12, "SV Babelsberg 03": 13, "SpVgg Unterhaching": 14, "FC Carl Zeiss Jena": 15,
           "VfR Aalen": 16, "SV Wacker Burghausen": 17, "SV Werder Bremen II": 18, "FC Bayern Munich II": 19, "Rot Weiss Ahlen": 20}
L3_1011 = {key(k): v for k, v in L3_1011.items()}
# 3. 리가(20팀) 순위별 값: 다른 선수 자료에 있는 값(시즌 무관 같은 값) 그대로. 없는 순위는 이웃 기존 값 사이 직선 보간(반올림).
#   기존: 1위 1557, 2위 1513, 5위 1462, 6위 1456, 7위 1448, 8위 1437(2021-22·2023-24; 2014-15는 1439), 9위 1429, 10위 1422,
#        12위 1414, 13위 1409, 14위 1406, 15위 1403, 17위 1379, 18위 1374, 19위 1369
#   보간: 4위 = 2위 1513과 5위 1462 사이 1479, 11위 = 10위 1422와 12위 1414의 중간 1418
DE3 = {1: 1557, 2: 1513, 4: 1479, 5: 1462, 6: 1456, 7: 1448, 8: 1437, 9: 1429, 10: 1422, 11: 1418, 12: 1414, 13: 1409,
       14: 1406, 15: 1403, 17: 1379, 18: 1374, 19: 1369}
DE3_INTERP = {4: "다른 선수 자료 3. 리가 2위 1513·5위 1462 사이 보간", 11: "다른 선수 자료 3. 리가 10위 1422·12위 1414의 중간"}
# 2. 분데스리가 순위별 값(다른 선수 자료, 시즌 무관 같은 값): 4위 1622
DE2 = {3: 1636, 4: 1622, 5: 1615}

def rank_model(k, season):
    if season == "2010-11" and k in L3_1011:
        r = L3_1011[k]
        if r in DE3:
            lv = f"3. 리가 {season} {r}위"
            if r in DE3_INTERP: lv += f" (추정, {DE3_INTERP[r]})"
            return DE3[r], lv
    t = RANKS.get(("L2", season))
    if t and k in t:
        r, n = t[k]
        if r in DE2: return DE2[r], f"2. 분데스리가 {season} {r}위"
    return None

# 순위표 모형 밖: 직접 추정(모두 '추정')
D4 = "다른 선수 자료 독일 4부 1300과 같음"
MAN = {
    # 오스트리아 분데스리가 2012-13 3위(TM 표 A1 2012; 우승 오스트리아 빈). 같은 시즌 기존 값(1위 1733·4위 1473·5위 1426·6위 1396·
    # 7위 1375·8위 1348·9위 1307·10위 1272)이 평균 1434 + 흩어짐 118.5 × 10팀 순위 곡선과 ±1 안에서 같음 → 그 곡선의 3위 값.
    (key("Rapid Vienna"), "2012-13"): (1508, "오스트리아 분데스리가 2012-13 3위 (추정, 같은 시즌 다른 선수 자료 순위값과 맞는 순위 곡선의 3위 값)"),
    (key("FC Carl Zeiss Jena"), "2012-13"): (1300, f"독일 4부(레기오날리가 북동부) 2012-13 2위 (추정, {D4})"),
    (key("FC Viktoria Köln"), "2015-16"): (1300, f"독일 4부(레기오날리가 서부) 2015-16 3위 (추정, {D4})"),
    (key("SpVgg Unterhaching"), "2015-16"): (1300, f"독일 4부(레기오날리가 바이에른) 2015-16 4위 (추정, {D4})"),
    (key("SC Hauenstein"), "2016-17"): (1180, "독일 5부(오버리가 라인란트팔츠/자르) 2016-17 13위 (추정, 다른 선수 자료 독일 5부 1180과 같음)"),
    (key("AEK Larnaca"), "2018-19"): (1400, "키프로스 1부 2018-19 4위 (추정, 다른 선수 자료 키프로스 1부 1400과 같음)"),
    (key("1.FC Saarbrücken"), "2019-20"): (1300, f"독일 4부(레기오날리가 남서부) 2019-20 1위 (추정, {D4})"),
    (key("1. FC Lokomotive Leipzig"), "2021-22"): (1300, f"독일 4부(레기오날리가 북동부) 2021-22 6위 (추정, {D4})"),
}
