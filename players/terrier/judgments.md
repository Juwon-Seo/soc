# 마르탱 테리에(Martin Terrier) 판정 기록

자료: `raw/`(2026-11-18 수집, Transfermarkt=TM 선수 경기 성적 API·경기 리포트 155개, FotMob=FM matchDetails 111개·playerMatches, en/fr 위키백과). 빌드: `python3 players/terrier/build_terrier.py` → `src/data/ter.js`, `terrier.json`. 판정 표는 build_terrier.py 상단 상수.

## 결과
- 310경기 81골(PK 3) 29도움, 18,299분. 기록 110개(골 81·도움 29), 두 경기 합산 기록 2개.
- 클럽별(경기·골·도움·분): 릴 15·2·0·533 / 스트라스부르 29·4·3·1816 / 리옹 77·17·2·4068 / 렌 141·51·21·10036 / 레버쿠젠 48·7·3·1846.
- 계산기(v1.204 스크래치 복사본): SOC 119.89, 최고 3시즌 21.32, 최고 5시즌 18.30. 클럽별 SOC 렌 77.52·리옹 19.51·레버쿠젠 16.15·스트라스부르 6.62·릴 0.09.

## 범위
- 1군 공식 경기만. 제외: 릴 B(CFA 2 2015-16 17/2/0, CFA 2016-17 12/4/0 — 아마추어 4·5부), 렌 B(내셔널 3 2023-24 1/0/0), 릴 U19(출전 없음), 프랑스 U20·U21, FotMob에만 있는 ICC 친선 3경기(2018.8, 리옹).
- 1군 다섯 클럽 모두 1부 프로 리그 → 제외 시즌 없음.
- 몰수·판정승 경기: 없음(TM 리포트·FM 상태·일정 페이지 확인, discrepancies 6).

## 출전·분
- TM API played·playedMinutes 그대로(310경기). en.wikipedia 경기·골 = TM(전 행), fr.wikipedia 경기·골 = TM, FM careerHistory 경기·골 = TM(스트라스부르는 FM이 18+11로 나눔).
- FM playerMatches와 29경기 1분 차이(2분 이상 없음) → TM 기준. FM 목록에 없는 19경기(릴 12, 리옹 컵 7)는 FM 대회 일정 파일로 같은 경기 확인(fotmob_tm_map.csv).
- 날짜: TM 리포트 날짜 = 파리/베를린 현지 날짜(모든 경기). 미주 경기 없음.

## 골
- TM 81 = FM 81, 경기·수·PK 여부 모두 일치. 분 차이 ≤1(2019.1.5 부르주 60/59, 2019.12.18 툴루즈 90+1/90, 2026.2.3 장크트파울리 31/32) → TM. PK 골 3(2021.3.20 메스 38', 2022.3.20 메스 18', 2022.4.15 모나코 90+3; FM 90) TM=FM.
- 자책골·PK 리바운드 없음. 놓친 PK 1(2023.10.5 비야레알 90+2, 선방) — 기록 영향 없음.
- 승부차기 4경기(2017.10.25 생테티엔 FRL, 2020.1.21 릴 FRL 준결승, 2024.1.21 마르세유 FRC, 2024.8.17 슈투트가르트 DFL 슈퍼컵): 리포트 최종 스코어에 승부차기 포함 — 골 뒤 스코어는 경기 중 순서로만 계산(tm_events 누적 점검 0 불일치).
- 연장: 2025.10.29 파더보른(DFB 2라운드, AET) — 테리에 골·도움 없음.

## 도움(discrepancies 1)
TM 33 → 계산기 29.
1. TM 'Penalty: Fouled player' 4개 제외(PK 유도, 규칙): 2018.1.20 디종 19' 랄라 / 2020.10.20 크라스노다르 56' 기라시 / 2022.2.25 몽펠리에 52' 라보르드 / 2024.2.22 AC 밀란 54' 부리조. FM도 4개 모두 도움 없음, fr.wikipedia도 밀란 도움 0.
2. FM 단독 2020.1.18 낭트(FRC 32강) 9' 셰르키 골(0-2): 넣지 않음. TM 도움 베르트랑 트라오레(Pass). maxifoot 경기 기사: "A la suite d'un ballon en profondeur de Terrier, B. Traoré se bat bien … Cherki réalise une frappe placée (0-2, 9e)", 같은 기사 "un tir placé après un centre de B. Traoré"; AP(NBC Sports) "after being set up by right winger Bertrand Traore". → 테리에는 도움 전 패스. (https://m.maxifoot.fr/football/article-42559.htm, https://www.nbcsports.com/soccer/news/16-year-old-cherki-scores-2-as-lyon-advances-in-french-cup)
3. 유형 빈칸 2024.12.10 인테르(챔스 리그 단계) 90' 무키엘레(1-0): 넣음. TM+FM 일치('assist by Martin Terrier'), 바이어 04 구단 기사 "with an assist from substitute Martin Terrier", CBS Sports "Alex Grimaldo flicked the ball back in the mixer, Martin Terrier got nothing more than a heel on the ball, teeing it up perfectly for Mukiele to drive home" → 의도된 뒤꿈치 패스. 반론: 로이터(ESPN·FMT 재게재, 1개 출처) "pounced on a loose ball", footitalia "his initial acrobatic effort was blocked, but he managed to retrieve the ball" — 슈팅 리바운드·굴절로 볼 근거는 아님(테리에 슈팅이 아님). 이 기록이 테리에 기록 중 값이 가장 큼(3.36) — 사용자 확인 권장. (https://www.bayer04.de/en-us/news/champions-league/werkself-beat-inter-milan-1-0-with-last-minute-winner, https://www.cbssports.com/soccer/news/leverkusens-touch-of-destiny-remains-after-statement-win-over-inter-in-champions-league-showdown)
4. 나머지 28개는 TM·FM 일치(분 차이 ≤1: 2021.3.14 스트라스부르 25/24, 2021.4.17 앙제 45+1/45+2, 2024.5.4 메스 23/22 → TM). 'Shot on goal'·'Deflected'·자책골 유도·본인 PK 도움 없음.
- 확인 못 한 단일 출처 도움: 없음.
- 합계 비교: TM 33 / FM 이벤트 30 / FM careerHistory 렌 20(나머지 클럽 TM과 같음) / fr.wikipedia 32 / 계산기 29.

## 대회 코드·단판/합산
- FR1·L1 lg. 쿠프 드 프랑스(5·6라운드=64·32강, 16강)·쿠프 드 라 리그(3라운드·16강)·DFB 포칼(2라운드·16강) dc, 8강 dk, 준결승 dsf. DFL 슈퍼컵 df(비르츠 자료와 같음).
- 챔스 조별/리그 단계 clg, 16강·녹아웃 PO cl16(두에 자료), 유로파 조별/리그 단계 elg, 녹아웃 PO elk, 컨퍼런스 조별 ecg, 16강 eck, 컨퍼런스 PO(로센보리, TM 'Qualifying Round') ecq(구이리·렌 동료 선례와 같음).
- 합산 기록 2개: 2021.8.26 로센보리 2차전(원정, 1차전 2-0) 81' 아블린 도움 [2,0,2,0,0,1]; 2022.3.17 레스터 2차전(홈, 1차전 0-2) 8' 부리조 도움 [2,1,0,2,0,1]. 2021-22부터 원정 다득점 없음·연장 있음. 다른 합산(바르셀로나 2019, 유벤투스 2020, 밀란 2024, 올림피아코스·아스널 2026)에는 테리에 골·도움 없음.

## 시즌·클럽
- 클럽 키: lilmt(~2017-08-18), strmt(~2018-07-01; 2018.1.26 릴→리옹 이적 뒤 재임대, 한 키), lyomt(~2020-07-06), renmt(~2024-07-18), levmt. 경계 = TM 이적일(모든 경기 TM 클럽과 일치 확인).
- 시즌: 릴·스트라스부르·리옹 기본(8월 1일). 렌·레버쿠젠 jul10 목록(기존 levks·nicag와 같은 분기) — 렌 2020.8.22 릴전·8.29 몽펠리에전이 기본 규칙 '2020년 8월=2019-20'에 걸리지 않게(2020-21). 레버쿠젠은 2020 규칙과 무관해 bayt 분기 불필요, 2024.8.17 슈퍼컵 = 2024-25. 7월 경기 없음.
- 리옹은 2020년 8월 경기 없음(유벤투스 2차전 TM 행 없음).

## 상대 Elo
- 출처: 같은 경기 다른 선수 자료 26, 팀×시즌 통합표 80, 직접 추정 4. 순위표 모형 사용 0.
- 직접 추정: 엑셀시오르(레위니옹 Premier League 2016, TM 리그 없음; 검색 결과 2016 우승팀은 JS 생피에루아즈) 1100(마르티니크 지역 1부 1100 선례) / 그르노블 2017-18 나시오날 3위(ranks.txt FR3 2017-18) 1361(다른 자료 나시오날 3위 1361) / 부르주 풋 2018-19 프랑스 5부 C조 1위(ranks.txt FR5C) 1150 / 로센보리 2021 엘리테세리엔 5위(ranks.txt NO1 2021) 1447 = 3위 1464·7위 1430 가운데.
- 리그1 2019-20(중단 시즌)은 통합표 값(공식 최종 순위, 경기당 승점) 그대로.
- 스크래치 복사본 `node tools/elo_table.js`: 값이 여럿인 팀-시즌 0.

## 동료·상대 대조(다른 파일 수정 없음)
- 같은 경기 출전 대조: 아우아르 67, 두에 46, 구이리 49(리옹 2019-20 포함), 페키르 28, 비르츠 20, 하피냐 4, 디아비 4 — 대회 코드 차이 0.
- 골·도움 상호 기록: 구이리→테리에 5, 두에→테리에 2, 아우아르→테리에 1, 테리에→구이리 2, 테리에→두에 1 — 날짜·분·스코어·대회·Elo·lv 모두 같음. TM 동료 도움인데 동료 파일에 없는 것 0.
- 상대팀 쪽 기록(다른 선수의 상대가 테리에 소속팀인 같은 날 경기) 대회 코드 차이 0.

## 수상(hon)
- TM 업적: DFL 슈퍼컵 24/25(레버쿠젠) → t.SC. 준우승 항목 없음(TM 업적에 없음).
- UNFP 리그1 올해의 팀 2021-22(fr.wikipedia 'Trophées UNFP du football 2022', 레퀴프 2022.5.15 "trio d'attaque Terrier-Ben Yedder-Mbappé") → a.XI "21/22 리그1 · UNFP(선수협회)". 다른 연도 2021·2023·2024 페이지에 마르탱 테리에 없음(2024 페이지의 Terrier는 다른 인물 다비드 테리에). 올해의 선수 수상 없음.
