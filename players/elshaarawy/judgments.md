# 스테판 엘 샤라위 판정 기록 (2026-11-18, 자료 기준일 2026-11-18)

빌드: `python3 players/elshaarawy/build_elshaarawy.py` → `src/data/els.js`, `players/elshaarawy/elshaarawy.json`.
결과: 534경기 109골(PK 0) 55도움, 29,533분, 기록 164개(합산 15개/13경기).

## 1. 범위·출전
- 성인 클럽 공식 경기만: Transfermarkt(TM) performance-game의 played 534경기 = TM 리포트 = en/it 위키백과 경기·골(차이 0).
- 뺌: 제노아·밀란 프리마베라(50경기 20골), TM '다른 팀에서 뜀' 39행, 대표팀, 친선(FotMob 친선 27경기).
- 파도바 2010-11 세리에B(2부 프로) + 승격 플레이오프 4경기(POSB) 포함(caz·brf·can 선례: 리그 비중).
- 상하이 선화 2020은 1단계 6경기만 출전(이후 TM 'absent'/'not in squad'), AFC 챔스 출전 없음.
- 출전 분: 전부 TM playedMinutes. FotMob 대비 ±1분 차이(34경기)는 TM 기준. 90분 추정 없음.
- 날짜: TM 리포트 날짜, 없으면 UTC→현지(로마·모나코·상하이) 변환. 2008-12-21 키에보전 데뷔(UTC 12-20 23:00).

## 2. 골
- TM 리포트 109골 = API 109골, PK 0. 자책골 판정 대상 없음.
- FotMob 대조(`--fm`): 차이 없음(±1분은 TM). FotMob 없는 경기: 파도바 6경기 7골(2011-01-15, 03-26, 04-21, 05-07, 05-14, 06-05 2골), 2019-08-19 중국 FA컵 준결승 다롄 이팡전 2골(22분, 45+2) → TM 리포트만(위키백과 시즌 골 수와 같음). 다롄 이팡전은 함식(ham.js) 14분 골 경기와 같은 경기(함식 행은 단판 dsf, 우리 행도 dsf·ko 1).

## 3. 도움 (TM 72 → 55)
| 구분 | 수 | 경기 |
|---|---|---|
| PK 유도(뺌) | 9 | 2013-02-03 우디네세 90+3 발로텔리, 2016-08-28 칼리아리 6 페로티, 2016-09-15 플젠 4 페로티, 2019-01-19 토리노 34 콜라로프, 2019-02-18 볼로냐 55 콜라로프, 2023-06-04 스페치아 90+1 디발라, 2025-01-26 우디네세 64 도우비크, 2025-03-13 빌바오 90+3 파레데스, 2026-03-15 코모 7 말런 |
| 'Shot on goal'(뺌) | 4 | 2012-01-22 노바라 73 호비뉴(FotMob은 도움), 2017-04-04 라치오 66 살라, 2020-08-10 다롄 8 김신욱(굴절 슛), 2021-02-25 브라가 23 제코(FotMob은 도움) |
| 상대 자책골(뺌) | 2 | 2012-12-16 페스카라 79 조나타스(TM 'Corner'), 2022-10-27 HJK 62 호스코넨 |
| 굴절로 판정(뺌) | 2 | 아래 4절 |
| 2014.8 이후 TM 단독 → 2곳 확인(넣음) | 2 | 아래 4절 |

- 2014.8 이전 TM 도움은 TM 단일 출처로 넣음(카사노·클로제 선례). FotMob에 없는 것 4개: 2011-01-22 크로토네 72 반타지아토, 2011-04-21 비첸차 62 데 파울라(파도바, FotMob 도움 기록 없음), 2012-12-16 페스카라 1 노체리노, 2013-02-03 우디네세 25 발로텔리.
- TM 도움 유형 빈칸 9개 중 상대 자책골(HJK)·브루노 페레스(아래) 외 7개는 FotMob도 엘 샤라위 도움 → 넣음.

## 4. 개별 판정 (출처)
- **2017-01-19 삼프도리아(코파 16강) 47분 제코 골 — 넣음.** TM Pass, FotMob 없음. Football Italia(https://football-italia.net/?p=483451) "El Shaarawy won back possession and threaded through for Edin Dzeko’s angled drive"; worldsoccertalk 통신 기사(https://worldsoccertalk.com/2017/01/19/nainggolan-hits-maiden-roma-brace-in-cup-romp/) "El Shaarawy won back possession to set up Edin Dzeko". 제코 판정(dze.js)은 같은 경기 61분 제코→엘 샤라위 도움을 넣었음(우리 골 행과 일치).
- **2017-12-01 SPAL 32분 스트로트만 골 — 넣음.** PA Sport(ESPN, https://www.espn.com/soccer/report/_/gameId/491545) "played in by El Shaarawy's back-heel"; Corriere dello Sport "servito in area da un assist delizioso di tacco di El Shaarawy"; Antara "menyambar bola kiriman dari Stephan El Shaarawy". (OA Sport는 '스트로트만이 흐른 공(rimpallo)을 따냄'으로 적음 — 소수 의견.) FotMob 선수 경기 목록 도움 1(=19분 제코 골).
- **2019-12-06 중국 FA컵 결승 2차전 산둥전 60분 김신욱 골 — 뺌.** 신화통신(https://www.xinhuanet.com/english/2019-12/06/c_138611600.htm) "Kim drove home ... after a cross from the right was headed into his path by a Shandong defender" → 상대 굴절. CGTN·ESPN Deportes는 도움 언급 없음. FotMob 도움 없음.
- **2021-04-03 사수올로 69분 브루노 페레스 골 — 뺌(불확실).** Tuttosport 문자 중계 "Spinazzola ubriaca Toljan, cross sporcato da El Shaarawy, Bruno Peres incrocia"; Forza Italian Football "latched onto a Leonardo Spinazzola cutback"; FotMob 도움 없음 → 엘 샤라위의 의도한 패스가 아닌 굴절. 반대: Quotidiano.net "è proprio il Faraone al 69' a regalare a Bruno Peres la palla", Sporza 문자 중계 "De assist komt op naam van Stephan El Shaarawy". 엄격 규칙(굴절 제외)에 따라 뺌 — 사용자 확인 권장.
- **FotMob 단독 2012-11-30 카타니아 56분 보아텡 골 — 뺌.** 2014.8 이전이지만 TM 기준 규칙이라 FotMob 단독은 다른 출처가 필요(카사노 ADD_A 선례: FotMob+다른 출처). Sports Mole·Bleacher Report: 보아텡의 중거리 감아차기, 도움 언급 없음.
- **FotMob 단독 2015-09-17 안데를레흐트 85분 트라오레 골 — 뺌.** PA Sport(ESPN 434407) "When El Shaarawy forced a save from Proto from close range, Traore capitalised"; UEFA 기사 "El Shaarawy's effort was rebounded to Traore" → 슈팅 리바운드.

## 5. 대회 코드·합산
- IT1·IT2·FR1·CSL·POSB = lg. CIT·CHFA: 2라운드·32강·16강 dc, 8강 dk, 준결승 dsf, 결승 df. CL 조별 clg, 16강 cl16, 8강 clk, 4강 clsf. CLQ clq, ECLQ ecq. EL 조별/리그 단계 elg, intermediate·16강·8강 elk, 4강 elsf, 결승 elf. UCOL 조별 ecg, 16강 eck.
- 합산 [차전, 홈, 1차전 우리, 상대, 원정골, 연장]: UEFA ag=날짜<2021-07-01, et=1; 코파 이탈리아 ag≤2021-22, et=1; 중국 FA컵 결승 ag=1·et=1(2018 결승 베이징 궈안 원정 다득점 우승 — en.wikipedia 2018 Chinese FA Cup; 2019 규정 직접 확인 못 해 추정, NOTE에 적음); 세리에B 승격 PO ag=0·et=0(it.wikipedia Serie B 2010-11 "Qualificato per il miglior piazzamento in classifica" → 동점이면 상위 팀; 계산은 50%, caz.js 선례).
- 합산 기록 15개: 2011-06-05 바레세 2골[2,0,1,0,0,0], 2012-02-08 유벤투스[1,1,..,1,1], 2013-02-20 바르셀로나 도움, 2013-08-20 PSV, 2015-08-04 영 보이스[2,1,3,1,1,1], 2017-04-04 라치오[2,1,0,2,1,1], 2019-12-06 산둥[2,1,0,1,1,1], 2021-03-11 샤흐타르, 2021-08-26 트라브존스포르[2,1,2,1,0,1], 2023-03-09 레알 소시에다드, 2023-04-20 페예노르트 101분(연장), 2024-02-22 페예노르트, 2024-03-07 브라이턴 2도움.
- 몰수 경기: 출전 경기 중 없음(discrepancies 6절). 로마 몰수 2경기(2020-09-19, 2021-01-19)는 엘 샤라위 미소속.

## 6. 시즌·클럽
- 클럽 키: genel(2008-10, 2026-), padel, milel, monel, romel(2016-19, 2021-26), shsel. TM 이적일 기준 경계(2010-07-01, 2011-07-01, 2015-07-13, 2016-01-26, 2019-07-08, 2021-01-30, 2026-07-01).
- 시즌: 기본 8월 1일. monel = jul10(2015-07-28 챔스 예선 영 보이스전 = 2015-16; 8월 기준이면 2014-15 1경기 시즌이 생김). shsel = calendar. 특수 분기 수작업 없음.

## 7. 상대 Elo
출처: 같은 경기 66, 팀×시즌 통합표 76, 순위표+모형 15, 직접 추정 7. `node tools/elo_table.js`(스크래치 복사본) 값이 여럿인 팀-시즌 0.
- 세리에B 2010-11(22팀): 함식 빌드 SB 순위값(기존 9위 1585·21위 1517과 일치): 아탈란타 1위 1707, 노바라 3위 1641, 바레세 4위 1623, 레지나 6위 1608, 크로토네 11위 1569, 비첸차 12위 1564, 사수올로 16위 1549, 아스콜리 17위 1542. 순위: TM 표 IT2 2010.
- 중국 슈퍼리그 2019(TM 표 CSL saison 2018 = 2019, 광저우 헝다 우승): 톈진 톈하이 14위 1422(CN_FIX), 다롄 이팡 9위 1466(같은 모형 1484+63×curve). 선전 15위 1411·산둥 5위 1514는 기존 표.
- 세리에A 2026-27 베네치아 19위(11월 18일 현재, TM 표) 1632.
- 직접 추정: 영 보이스 2015-16(스위스 2위, TM C1 2015) 1609; 보되/글림트 2021(노르웨이 1위, TM NO1 2021) 1560 — 통합표 '2022 노르웨이 2위' 값이 연도 대체로 잡히던 것을 막고 2021 키로 둠; CSKA 소피아 2021-22(불가리아 챔피언십 그룹 2위) 1480; 조랴 2021-22(우크라이나, 18라운드 뒤 중단 시점 4위) 1530; 미트윌란 2025-26(덴마크 2위 — RSSSF https://www.rsssf.org/tablesd/den2026.html 챔피언십 PO 최종: AGF 1, 미트윌란 2) 1560; 트라브존스포르 2021-22(쉬페르리그 1위, 우승) 1770 = 함식·외질 쉬페르리그 회귀(같은 식 2위 = 1667, 기존 페네르바흐체 값과 같음).

## 7-1. 순위 확인
TM 최종 순위표(ranks.txt): IT2 2010-11, CSL 2019, C1 2015-16, NO1 2021, BU1 2021-22 그룹, UKR1 2021-22(중단), TR1 2021-22, DK1 2025-26(정규 단계뿐 → RSSSF 최종으로 확인), IT1 2026-27(진행 중).

## 8. 동료·같은 경기 대조 (`--cross`)
- 같은 경기 93건 모두 Elo·lv·대회·합산 같음(csn, ibr, see, men, sal, tot, dze, pas, ped, dyb, mba).
- 동료 도움→엘 샤라위 골 16건 모두 일치(분·스코어·대회·Elo·lv): csn 2011-09-21, dyb 2023-01-22·2025-01-17·2026-05-24, dze 7건, mba 2015-12-10, men 2014-11-08, sal 2016-03-04·2016-10-23, tot 2016-10-20.
- 엘 샤라위 도움→동료 골 15건 모두 일치.
- TM 엘 샤라위 도움을 뺀 동료 골 3건(dyb 2023-06-04 PK, dze 2021-02-25 'Shot on goal', sal 2017-04-04 'Shot on goal'): 동료 파일은 골만 있어 충돌 없음.
- 불일치 없음.

## 9. 병렬 판정(폴리타노)과 같은 경기
폴리타노 파일은 읽지 않음. 엘 샤라위 기록 중 폴리타노 소속 팀(페스카라 2012-13, 사수올로 2015-18, 인테르 2018-20, 나폴리 2020-) 상대 행은 보고서에 표로 적음.

## 10. 수상(hon)
TM 업적: 컨퍼런스리그 21/22(로마) → o "컨퍼런스리그 우승"(기존 표기), 중국 FA컵 2019 → DC "2019 상하이 선화", 수페르코파 11/12 밀란(명단 제외, 카사노 선례대로 SC), UEL 준우승 22/23. 세리에B 최우수 선수 10/11 = AIC 그란 갈라 2011 "Miglior calciatore della Serie B"(it.wikipedia 엘 샤라위 문서, en.wikipedia Serie B Footballer of the Year 목록) → POY "10/11 세리에B · AIC(선수협회)". AIC 세리에A 올해의 팀 없음. 유소년·대표 기록 제외.
