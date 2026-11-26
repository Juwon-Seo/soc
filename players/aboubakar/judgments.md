# 뱅상 아부바카르 (Vincent Aboubakar) 판정 기록

- Transfermarkt 147487, FotMob 202443 (1369001은 다른 선수). 프리셋 `aboubakar`, 접두어 `ABK`(abk.js; `vab`은 다른 선수 사용 중, `abk.js`·`ABK_` 미사용 확인).
- 자료 기준일 2026-11-25. 현역(보드룸 FK, 튀르키예 2부). 마지막 반영 경기 2026-11-08 볼루스포르전(58분 퇴장). 11-23 반스포르전 결장.
- 재현: `python3 players/aboubakar/build_aboubakar.py [--out <data 폴더>]` (raw/ → aboubakar.json·abk.js). 직접 라벨 `man_elo.py`, 도움 판정 `assist_checks.py`, 설명 `note_aboubakar.py`.
- 결과: **456경기 185골(PK 18) 40도움, 29,904분**, 기록 225행(골 185·도움 40), 두 경기 합산 10행.

## 1. 범위
| 항목 | 판정 | 근거 |
|---|---|---|
| 코통 스포르 2009-10 (카메룬 1부) | 뺌 | 영어·프랑스어 위키백과 시즌 합계(15경기 7골; 영어판 citation needed, 프랑스어판 본문은 득점왕 20골)뿐, TM·FotMob·경기 기록 없음(S1). NOTE에 적음 |
| 발랑시엔 B 2012-13 (CFA, 4부) 3경기 1골 | 뺌 | 2군·아마추어 |
| 포르투 B 2019-08-17 (포르투갈 2부) 1경기 | 뺌 | 2군 |
| 그 밖 1군 공식 경기 456경기 | 넣음 | TM performance-game(played), en/fr 위키백과 클럽·시즌별 합계 일치(tm_vs_wiki.csv) |

## 2. 출전 분
| 경기 | TM | 판정 | 근거 |
|---|---|---|---|
| 2016-05-22 타사 결승 브라가 | 11 | **41** | 위키백과 결승 문서: 2-2 연장 뒤 승부차기, 79분 투입(TM JSON 교체 79분). API가 90분까지만 셈 |
| 2018-09-22 세투발 원정 | 63 | **73** | FotMob 교체 이벤트 73분, ESPN 라인업 74분(A. Pereira ↔ Aboubakar) |
| 2018-01-24 타사 다 리가 준결승 스포르팅 | 22 | 22 | 위키백과 2017–18 Taça da Liga: 0-0 뒤 바로 승부차기(연장 없음) |
| 2021-03-16 튀르키예컵 준결승 바샥셰히르(연장) | 46 | 46 | FotMob 교체 이벤트도 46분(FotMob playerMatches 120은 오기) |
| 2017-03-19 안탈리아스포르 | 64 | 64 | 경고 누적 퇴장(FotMob 이벤트 65분 YellowRed; playerMatches 90은 오기) |
| 퇴장 경기 2016-12-06 디나모 키이우 56, 2017-03-16 올림피아코스 39, 2026-11-08 볼루스포르 58, 2011-01-08 앙제 119(연장) | TM | 그대로 | |
| 2021-02-11 튀르키예컵 8강 코니아스포르(승부차기) 55, 2018-04-18 타사 준결승 2차전 54 | TM | 그대로 | 연장 포함 계산이 맞음 |

## 3. 골 (185, PK 18)
- TM 경기 기록 골 = TM API 골(185), FotMob 180골(151경기) 대조: 골 수·PK 모두 같음, 시각 차이 26건(±1~2분·45/90+ 표기)은 TM 기준.
- **S5 2017-11-17 타사 4라운드 포르티모넨스전(3-2)**: TM은 브라이미 90분(2-2) → 아부바카르 90+3분(3-2). FotMob·CM 기사(“golos de Aboubakar (90+1’) e Brahimi (90+6’)”)·Bola na Rede 기사(아부바카르 90분 동점, 브라이미 ‘4분 추가시간’ 결승; 경기 기록 “Aboubakar aos 90’ e Brahimi aos 94’”)가 모두 아부바카르 동점골 → **90+1분, 골 전 1-2**로 고침(S 영향).
- FotMob 기록 없는 골 확인: 2012-01-06 르망 원정 73분(ESPN 경기 기록, maxifoot 32강 결과), 2017-10-13 루지타누 20·21분(CM 문자 중계, DN 기사), 2025-10-29 MOIK 바쿠 8·42분(T24 기사 2골, playerstats·TM 8·42분).
- 본인 자책골 없음. PK 리바운드 골 없음.

## 4. 도움 (TM 58행 → 40)
TM JSON 도움 58행 = 자기 팀 57 + 2013-09-22 보르도 상대 골의 ‘Handball (opponent)’ 1. 본인 PK 골 자기 도움 4개(2014-08-10 모나코, 2017-12-10 세투발, 2017-12-21 히우 아브, 2025-11-23 이미실리)는 TM API도 세지 않아 처음부터 제외.
| 뺀 것 | 개수 | 목록 |
|---|---|---|
| PK 유도 | 3 | 2012-03-24 렌(다닉), 2013-11-23 에비앙(주프레), 2013-12-07 렌(주프레) |
| Shot on goal | 3 | 2012-05-06 PSG(고미스), 2013-05-05 PSG(다닉), 2017-12-14 기마랑이스(안드레 안드레) |
| 상대 자책골 유도 | 1 | 2012-04-29 니스(디가르 자책골, 유형 Shot on goal) |
| 핸드볼 행 | 1 | 2013-09-22 보르도 8분 디아바테 |
| 2014.8 이후 TM 단독, 확인 못 함 | 10 | 아래 표 |

2014.8 이후 TM 단독(FotMob 이벤트 도움 없음) 14개 판정:
| 경기 | 골 | 판정 | 근거 |
|---|---|---|---|
| 2015-03-06 브라가 원정 73' | 텔루 | **넣음** | Bola na Rede(“rodar sobre si mesmo e endossar a bola a Tello”), Combination Play(“Aboubakar left Tello one on one”) |
| 2015-04-06 이스토릴 70' | 다닐루 | 뺌 | Gazeta Esportiva(“passe de calcanhar de Aboubakar”) 1곳 확인. beIN 리뷰는 검색 요약에만 보이고 원문 접속 불가 |
| 2015-04-11 히우 아브 원정 83' | 에르나니 | 뺌 | RTP 문자 중계만(zerozero 제공 → 금지 출처) |
| 2015-05-22 페나피엘 90' | 다닐루 | 뺌 | FourFourTwo(통신 기사) 1곳. CM·Bola na Rede 언급 없음. (그 기사는 90+2분) |
| 2015-09-12 아로우카 원정 15' | 코로나 | **넣음** | Sports Mole(“held off a couple of challenges … teeing up Corona”), El Universal(“a pass from Aboubakar”), ESPN 경기 기록 |
| 2016-03-02 타사 준결승 2차전 질 비센트 81' | 마레가 | 뺌 | Bola na Rede 기사에 도움 언급 없음 |
| 2017-09-22 포르티모넨스 68' | 브라이미 | 뺌 | ESPN(옵타)만. FotMob playerMatches 도움 0. Sporting Life는 같은 옵타 피드 |
| 2017-10-21 파수스 25' | 마레가 | 뺌 | ESPN(옵타)만. CM·Bola na Rede는 “Brahimi, Aboubakar e Marega 연계”(마지막 패스 명시 없음) |
| 2017-12-10 세투발 82' | 마레가 | 뺌 | ESPN(옵타)만. FotMob 0. PortuGOAL·Bola na Rede 언급 없음 |
| 2018-05-06 페이렌스 59' | 브라이미 | **넣음** | RTP 기사(“O avançado encontrou Brahimi com um passe picado”), Bola na Rede(“Passe picado de Aboubakar”), ESPN(EFE) 기사, ESPN 경기 기록 |
| 2018-08-04 수페르타사 아베스 25' | 브라이미 | **넣음** | Bola na Rede(“passa para Aboubakar que devolve”), Observador(“numa tabela perfeita com Aboubakar”) |
| 2022-02-21 킹스컵 8강 알힐랄 17' | 탈리스카 | 뺌 | Soccernet은 아부바카르, The Eagle Online은 조나탄 로드리게스 크로스 — 상충 |
| 2022-12-21 킹스컵 16강 알아달라 85' | 알나제이 | 뺌 | 확인 출처 없음 |
| 2025-10-26 가발라 원정 72' | 이페아니 매슈 | 뺌 | playerstats 기록 도움 없음, 다른 출처 없음 |
- 2014.8 이전 TM 단독 정상 유형 7개(툴루즈·마르세유·로리앙·캉·렌·소쇼·몽펠리에) 선례대로 넣음. TM+FotMob 일치 29개(이후 25). FotMob 단독 도움 없음.
- 넣은 40개 = 이전 11 + 이후 29.

## 5. 상대 Elo·라벨
- 같은 경기 다른 선수 자료 13행(콰레스마 qua.js), 기존 팀×시즌 156행, 순위표 → 라벨 51행, 직접 라벨 5행(man_elo.py). TABLE_DIFF 0.
- 직접 라벨: 트랙토르 `이란 1부 2020-21 4위/16팀`(2021-09-14 AFC 챔스 16강, 이란 2021-22 리그 10월 개막 → 직전 시즌; 위키백과 2020–21 Persian Gulf Pro League 순위 team4=TRC 확인), 루지타누 GC `포르투갈 4부 2017-18 4위/14팀 (AF Évora 1ª Divisão, 리그 수준 추정)`(위키백과 Lusitano G.C. 시즌 표 26경기 승점 48 → 14팀), MOIK 바쿠 `아제르바이잔 2부 2025-26 6위/10팀 (Azerbaijan First League, 리그 수준 추정)`(위키백과 2025–26 Azerbaijan First League, 27경기 끝난 최종).
- TM 순위표로 만든 라벨 중 위키백과로 대조: 아제르바이잔 2025-26(team_order SAB,QAR,TUR,NEF,ZIR,ARA,SUM,SHA,IMI,KAP,GAB,KRV = TM 같음), 알바니아 2022-23(티라나 2위)·2023-24(5위), 이란 2020-21. 나머지(포르투갈 2015-16 등)는 승점 표 행 순서와 같음.
- 튀르키예 2부 2026-27: TM 현재 순위표(11-25 수집) `(TFF 1. Lig, 2026년 11월 25일 현재 순위)`. 기존 통합표에 같은 팀×시즌 없음.
- 2023-07-27 티라나 1차전은 알바니아 2022-23(2위), 8-03 2차전은 8월 1일 기준으로 2023-24(5위) — 날짜 기준 시즌 규칙 그대로(같은 상대 두 값).
- 이름: Istres Football Club → FC Istres Ouest Provence, Thonon Évian Grand Genève FC → FC Évian Thonon Gaillard, Ankaraspor(2016-17) → Osmanlispor FK, Erzurumspor FK(2020-21) → Büyüksehir Belediye Erzurumspor(기존 자료 이름).

### 승점 표 map 추가 필요 (elo/league_points_other.json; 스크래치 복사본에서 적용해 값 계산, 원본은 안 고침)
`<label head> | <opp name> | <table team> | [table,row]`
- 리그2 2010-11 | US Boulogne | Boulogne | [0,7]
- 리그2 2011-12 | Le Mans FC | Le Mans | [0,16]
- 리그2 2012-13 | FC Istres Ouest Provence | Istres | [0,12]
- 사우디 프로리그 2021-22 | Abha Club | Abha | [0,8]
- 사우디 프로리그 2021-22 | Al-Ahli SFC | Al-Ahli | [0,14]
- 사우디 프로리그 2021-22 | Al-Taawoun FC | Al-Taawoun | [0,11]
- 사우디 프로리그 2021-22 | Al-Tai FC | Al-Tai | [0,5]
- 사우디 프로리그 2021-22 | Damac FC | Damac | [0,4]
- 사우디 프로리그 2022-23 | Al-Khaleej FC | Al-Khaleej | [0,13]
- 쉬페르리그 2016-17 | Trabzonspor | Trabzonspor | [0,5]
- 쉬페르리그 2020-21 | Fatih Karagümrük | Fatih Karagümrük | [0,7]
- 쉬페르리그 2020-21 | Kasimpasa | Kasımpaşa | [0,13]
- 쉬페르리그 2020-21 | Yeni Malatyaspor | Yeni Malatyaspor | [0,14]
- 쉬페르리그 2022-23 | Adana Demirspor | Adana Demirspor | [0,3]
- 쉬페르리그 2022-23 | Galatasaray | Galatasaray | [0,0]
- 아제르바이잔 1부 2023-24 | Neftchi PFK | Neftçi | [0,4]
- 아제르바이잔 1부 2025-26 | Araz-Nakhchivan | Araz-Naxçıvan | [0,5]
- 아제르바이잔 1부 2025-26 | FC Imishli | Imishli | [0,8]
- 아제르바이잔 1부 2025-26 | FC Shamakhi | Shamakhi | [0,7]
- 아제르바이잔 1부 2025-26 | FK Gabala | Gabala | [0,10]
- 아제르바이잔 1부 2025-26 | Kapaz PFK | Kapaz | [0,9]
- 아제르바이잔 1부 2025-26 | Sumgayit PFC | Sumgayit | [0,6]
- 우크라이나 1부 2023-24 | Dynamo Kyiv | Dynamo Kyiv | [0,1]
(모두 표 행 순서 = 라벨 순위 확인)

## 6. 대회 코드·합산
- 리그: FR1·PO1·TR1·SA1·AZ1·TR2. 국내컵: 프랑스컵·쿠프 드 라 리그·타사 드 포르투갈·타사 다 리가·튀르키예컵·킹스컵·아제르바이잔컵(8강 dk, 준결승 dsf, 결승 df). 타사 다 리가 조별·2016-17 튀르키예컵 조별 ko 0(brf·ldz·van 선례). 수페르타사 df.
- CL 조별 clg·16강 cl16, CLQ clq, EL 조별 elg·32강/16강 elk, ECLQ ecq, 컨퍼런스 조별 ecg, AFC 챔스 2021 16강(단판) acl·8강 aclk·준결승 aclsf.
- 합산 tie: UEFA·타사 준결승 2020-21까지 원정 다득점·연장, 이후 원정 다득점 없음. 크라스노다르(2019)·티라나·네프치·디나모 키이우(2023)는 수집기가 수동으로 짝지음(tm_two_leg_ties.csv).

## 7. 시즌·클럽
- 베식타시 키 `besabk`는 jul10(2023-07-27 컨퍼런스 예선 = 2023-24). 나머지 8월 1일. 한 번만 있는 7월 경기라 다른 시즌 영향 없음.
- 클럽 키: valabk·lorabk·porabk(두 번)·besabk(세 번)·nasabk·hatabk·nefabk·bodabk. 국기 CM(이미 있음, 에투). 포지션 CF.
- 색: 발랑시엔 빨강·흰(#E2001A), 로리앙·포르투·베식타시·알나스르·네프치는 기존 clubcolors 값 재사용, 하타이스포르 적갈·흰(#800000), 보드룸 초록·흰(#009A44).

## 8. 우승·수상 (TM 업적)
- LG: 포르투 17/18·19/20, 베식타시 16/17·20/21. DC: 포르투 2020(19/20 타사), 베식타시 20/21·23/24. SC: 포르투 18/19(2018-08-04 수페르타사, TM 표기 '2019'), 베식타시 24/25(튀르키예 슈퍼컵 2024-08-03; 그 경기 명단 외, 2024-25 베식타시 출전 0경기지만 9월 이적 전까지 1군 명단·TM 업적 등재 → 지시대로 넣음, **사용자 확인 필요**).
- 뺀 것: 코통 스포르 카메룬 1부 2009-10(시즌 미수록), 네이션스컵 2017 우승·2021 득점왕(대표팀). 개인 클럽 수상 없음.

## 9. 다른 선수 자료 대조
- 공유 경기: qua.js(콰레스마) 47경기, ldz.js(루이스 디아스) 6경기, 그 밖 상대 팀으로 만난 경기 다수(blh·pay·aub 등). 같은 경기 Elo/lv/대회 차이 0.
- 콰레스마 도움 → 아부바카르 골 6개(2014-10-25 아로우카 87', 2015-03-15 아로우카 32', 2015-04-06 이스토릴 45', 2016-10-19 나폴리 86', 2016-11-23 벤피카 89', 2017-05-07 페네르바흐체 46') 모두 날짜·분·스코어·Elo·lv 같음.
- 이번 회차 병렬(슬리마니·론돈·우드): 판정 파일 없음(raw만) — 공유 경기 대조 못 함. 슬리마니는 스포르팅(2013-16)·페네르바흐체(2018-19)라 포르투(2014-16)·베식타시와 맞대결 가능 — 같은 팀×시즌 라벨은 rank_apply로 같아짐.

## 10. 검증(스크래치 복사본)
- add_players.py leekangin → build → verify check: 기존 306명 동일, aboubakar 추가(아래 보고).
- league_rank_apply.py: 바뀌는 행 0. league_era/world/second_tier_x: 0. **league_second_tier.py: 포르투갈 2부 2015-16 −3**(이 시즌 행은 2015-12-16 페이렌스 1행뿐, 3위/24팀이라 그 도구가 한 행으로 흩어짐을 맞추는 데서 생기는 차이; --apply 하면 이 행만 −3).
- elo_table.js: 값이 여럿인 팀-시즌 0.

### 검증 결과
- verify check: "기준 306 명 · 새 307 명, 추가된 선수: 뱅상 아부바카르, 탭 표 글자가 달라진 선수 0, 새 파일 콘솔 오류 없음, 결과: 통과".
- pStats: SOC 191.94, 456경기 185골 40도움 29,904분, 3-peak 24.49, 5-peak 21.68, SOC-CAR ≈ 142.1.
