# 레온 베일리 (Leon Bailey) 판정 기록 (2026-11-18)

재현: `python3 players/bailey/build_bailey.py` → `src/data/bly.js`, `players/bailey/bailey.json` (`--debug` Elo 출처·도움 제외 목록, `--cross` 동료 대조, `--fm` FotMob 골 대조, `--root=<복사본>`). 판정 표는 `decisions_bailey.py`, 설명 문장은 `note_bailey.py`. 호프만 빌드(같은 원자료 형식) 바탕, 벨기에 Elo는 데이비드·토르강 아자르 빌드의 국가 계수 회귀.
접두어 BLY(`bly.js` 없던 것 확인), 프리셋 id `bailey`, 클럽 키 `genlb`·`levlb`·`avllb`·`romlb`·`olylb`(index.html에 없음 확인). 빌라 두 시기는 같은 키(`torim` 선례).
결과: **412경기 79골(PK 2) 65도움, 24,579분**, 기록 144행(합산 15행). SOC 132.84(186명 중 164위), 최고 3시즌 23.25 · 5시즌 19.16.

## 1. 범위
- TM performance-game played 성인 1군 412경기 = TM 리포트 = FotMob 라인업(412 전부 매핑). 클럽별 TM = en.wiki(헹크 77·레버쿠젠 156·빌라 163·로마 11; 올림피아코스는 위키 2026-09-16 기준이라 2/5).
- 제외: 유소년(피닉스 올스타 아카데미, USK 아니프/리퍼링, AS 트렌친 U19 — 성인 공식 경기 없음), 자메이카 대표, 친선(FM playerMatches 10경기), FM이 센 2022-23 Queensland Champions Cup 2경기(친선 대회, TM·위키에 없음), 2026-05-20 EL 결승(교체 명단만, 미출전).
- v1.159 프로 리그 규칙: 모든 팀-시즌이 1부(벨기에·분데스리가·PL·세리에A·그리스) → 제외 시즌 없음.
- 몰수·무효 경기 없음(discrepancies 7).
- 현역(올림피아코스, 2026-09-02 이적). 마지막 경기 2026-11-04 렌전(EL 리그 페이즈, 59분). 2026-11-08 GR1은 명단만.

## 2. 출전·분·날짜
- TM playedMinutes 그대로(MIN_FIX 없음). discrepancies 4의 차이(FM 라인업 교체 기록 누락 등 5경기)는 TM 리포트 교체 기록·FM playerMatches 분과 맞는 TM.
- 날짜 = date_local_computed = TM 리포트 날짜(build 전부 확인). 승부차기 3경기 API 스코어(6-5, 4-4, 5-5)는 승부차기 포함이라 리포트 스코어·다른 차전 리포트 사용.

## 3. 골 (79, PK 2)
- TM 리포트 골 = API 골(78). FM 대조(`--fm`): 수·PK·분 일치(1분 차이 2026-03-19 85/86, FM 45분 표기 2개는 TM).
- **추가 1(`ADD_G`)**: 2016-10-02 헹크 2-1 메헬런 51분(1-1에서). TM은 사마타 'Deflected shot on goal'. FM matchDetails 베일리, DH(벨가) 경기 기사 'Leon Bailey (51e)…Une erreur que Bailey lui a fait payer cash (51e, 2-1)', Voetbalkrant 문자 중계 '51 Doelpunt van Leon Bailey … Bailey draait zich vrij en trapt via een Mechels been binnen', Foot Direct(Foot Mercato) '51' L. Bailey', en.wiki 헹크 2016-17 리그 2골 → **베일리 골**(굴절된 본인 슈팅). Elo 1487 '벨기에 1부 2016-17 7위 (리그 모형값)'.
- PK 골 2: 2016-08-18 로코모티바 원정 35분(ELQ 플레이오프 1차), 2016-09-15 라피트 빈 90분(EL 조별). 자책골·PK 실축 뒤 리바운드 없음.
- 연장 골: 2017-08-11 카를스루에(DFB 1R) 105분 2-0에서, 2021-02-02 로트바이스 에센(DFB 16강) 105분 0-0에서(et 1).

## 4. 도움 (TM 리포트 71 → 65)
모든 경기가 2014-08-01 뒤 → TM∩FM은 그대로, 한쪽 단독은 다른 독립 출처 2곳(TM·FM 제외)이 확인한 것만.
| 구분 | 수 | 내용 |
|---|---|---|
| PK 유도 | 1 | 2017-05-20 헤르타 81' 아랑기스 PK('Penalty: Fouled player') |
| 상대 자책골 | 1 | 2020-12-06 샬케 10' 티아브 자책골(TM 도움 칸 베일리, 유형 빈칸) |
| TM 단독 확인 못 함 | 5 | 아래 '뺌' |
| TM 단독 2곳 확인(넣음) | 11 | 아래 '넣음' |
| TM에 없는 도움 추가(ADD_A) | +1 | 2016-10-29 베스테를로 66' 카렐리스 |
- TM∩FM 일치 53개(이벤트 기준; 스로인·빈칸·'Header' 유형 포함, PK 표시 없음 → 일반 도움: 2017-09-24 함부르크 20' 폴란트, 2020-10-26 아우크스부르크 90+4' 디아비, 2021-10-22 아스널 82' 램지, 2022-08-20 팰리스 5' 왓킨스, 2023-08-31 히버니언 61' 캐시, 2023-10-29 루턴 49' 디아비).
- 출처 약칭: VK = Voetbalkrant 문자 중계(herbeleef)·경기 기사(같은 매체 = 1곳), FD = Foot Mercato/Foot Direct 경기 기록('P.D' = passe décisive). 둘은 서로 다른 매체이고 TM과도 독립(예: FD는 TM이 월시 도움으로 적은 2016-02-13 베일리 골에 도움 없음, VK는 데설전 27'에 TM과 다른 도움자 칸).
- ESPN(Belgian 1부 2015-17·EL 예선)은 득점자만 있고 도움 자료 없음. fbref·worldfootball·soccerway 등 금지/확인 불가 출처는 쓰지 않음.

TM 단독 16개(FM 2015-16 헹크 이벤트 도움 자료 없음 11, FM 기록 없음/0 5):
| gameId|분 | 날짜·상대 | 득점자 | 판정 | 근거 |
|---|---|---|---|---|---|
| 2630703|9 | 2015-10-04 스탕다르 | 카바셀레 | **넣음** | VK '9 Kabasele brengt Genk op voorsprong Goal! Kabasele kopt de corner van Bailey staalhard in de hoek' · FD '9' C. Kabasele (P.D L. Bailey)' |
| 2630703|78 | 〃 | 뷔펠 | **넣음** | VK '78 Doelpunt van Thomas Buffel (Leon Bailey) Goal! Hele mooie actie en voorzet van Bailey' · FD '78' T. Buffel (P.D L. Bailey)' |
| 2636601|27 | 2015-09-23 데설(CCB) | 드바스트 | 뺌 | VK 문자 '30 … Bailey zet voor, Dewaest kopt staalhard binnen'(같은 VK 기록 칸은 포수엘로) 1곳, FD 도움 없음 |
| 2653887|87 | 2016-01-23 메헬런 원정 | 카바셀레 | **넣음** | VK '87 Doelpunt van Christian Kabasele (Leon Bailey)' · FD '87' C. Kabasele (P.D L. Bailey)' |
| 2653898|21 | 2016-01-30 코르트레이크 | 카바셀레 | **넣음** | VK 'Bailey schildert een vrije trap op het hoofd van Kabasele' · FD (P.D L. Bailey) |
| 2653914|84 | 2016-02-13 바슬란트베베런 | 카바셀레 | **넣음** | VK '84 Doelpunt van Christian Kabasele (Leon Bailey) … vanop een corner' · FD '84' C. Kabasele (P.D L. Bailey)' |
| 2662197|50 | 2016-02-28 브뤼허 | 뷔펠 | **넣음** | VK 'Bailey zet voor, Buffel neemt de bal ineens op de slof: 2-1' · FD '50' T. Buffel (P.D L. Bailey)' |
| 2668505|24 | 2016-03-13 오스텐더 | 사마타 | **넣음** | VK 'Bailey met een goede voorzet, … de kopbal van Samatta' · FD '24' M. Samatta (P.D L. Bailey)' |
| 2673772|21 | 2016-04-08 오스텐더(EJPL) | 뷔펠 | 뺌 | FD (P.D L. Bailey)·VK 기록 칸 베일리지만 VK 문자 본문은 'Capon kopt het leer zomaar in de voeten van Karelis. Het is een koud kunstje voor de Griek om Buffel in het straatje te sturen'(카렐리스 패스)로 엇갈림. 검색 요약상 soccerway도 베일리이나 직접 확인 불가 → 확인된 독립 출처 1곳으로 보고 뺌(사용자 확인 가능 항목) |
| 2674066|65 | 2016-05-19 안데를레흐트(EJPL) | 뷔펠 | **넣음** | VK 경기 기사 'Een voorzet van Bailey belandde bij Buffel en die schoot de 2-2' · FD '65' T. Buffel (P.D L. Bailey)' |
| 2693849|45+3 | 2016-05-29 샤를루아(ESJP 2차) | 월시 | **넣음** | VK 기사 'In de 3de minuut van de toegevoegde tijd maakte Walsh er 3-1 van op voorzet van een ijzersterke Bailey' · FD '45+3' S. Walsh (P.D L. Bailey)' |
| 2711535|79 | 2016-07-14 부두치노스트(ELQ) | 사마타 | 뺌 | RTBF(벨가) 'À la 79ème minute, Bailey servait Samatta' 1곳. FD·VK(득점자만)·ESPN 도움 없음 |
| 2725299|13 | 2016-08-04 코크 원정(ELQ) | 뷔펠 | **넣음** | RTÉ 'Bailey … racing away clear down the left before finding the incoming Buffel with a pinpoint cross' · Irish Examiner '13 mins … Leon Bailey gets in behind the defence and his low cross is met by a first-time Thomas Buffel effort'(Irish Times도 같은 서술, 검색 요약) |
| 2752314|2 | 2016-08-25 로코모티바(ELQ PO 2차) | 사마타 | **넣음** | VK 기사 'Samatta opende de score op aangeven van Bailey al na anderhalve minuut' · FD '2' M. Samatta (P.D L. Bailey)' |
| 2761171|42 | 2016-09-21 알스트(CCB) | 카렐리스 | 뺌 | VK '43 … Karelis maakt makkelijk zijn derde'(도움자 없음), 다른 출처 없음 |
| 3098756|84 | 2018-11-29 루도고레츠(EL) | 바이저 | 뺌 | ESPN(Opta) 득점 이벤트 참가자에만 베일리('following a set piece'), 같은 ESPN 선수 기록 goalAssists 0, FM 이벤트·playerMatches 도움 0, SID(Sport1·t-online)·DFB 데이터센터 도움자 없음, 루도고레츠 구단 기사(검색 요약)는 중앙 슈팅을 레낭이 걷어낸 뒤 바이저가 넣은 장면 → 1곳뿐 |

FotMob 단독 4개:
| 경기 | 판정 | 근거 |
|---|---|---|
| 2016-10-20 아틀레틱(EL) 40' 브라베츠 | 뺌 | ESPN(Opta) 문자 '40' Attempt saved. Leon Bailey … is saved' → '40' Goal! … Jakub Brabec … from very close range' — GK 리바운드 |
| 2016-10-29 베스테를로 66' 카렐리스 | **넣음(ADD_A)** | FM 이벤트 + VK 기록 칸 '( Leon Bailey ) Nikolaos Karelis 66'' 및 기사 제목 'Bailey trekt hen over de streep met mooie assists' + FD '66' N. Karelis (P.D L. Bailey)'. TM은 같은 골 도움자 없음 |
| 2016-11-24 라피트 빈(EL) 11' 카렐리스 | 뺌 | ESPN '11' Leon Bailey … hits the right post with a header' → 카렐리스 골 — 골대 리바운드 |
| 2023-10-26 AZ 원정(UECL) 51' 왓킨스 | 뺌 | ESPN '51' Attempt saved. Leon Bailey …' → '51' Goal! … Ollie Watkins … from very close range' — GK 리바운드 |

- 도움 합계 비교: TM 71 · FM 경력 65 · 이 계산기 65.

## 5. 대회 코드·합산
- lg: BE1·EJPL(챔피언십 PO)·ESJP(유로파 PO 결승 2경기, kdb 선례 '벨기에 플레이오프 2 결승은 리그', 단판/합산 아님 ko 0)·L1·GB1·IT1·GR1.
- 국내컵 CCB·DFB·FAC·CGB·CIT·GRP: 결승 df(2020-07-04 DFB 결승), 준결승 dsf, 8강 dk, 나머지 dc(벨기에컵 6라운드, FA컵 3~5R·4R 재경기, 리그컵 2~4R, 코파 16강, 그리스컵 조별).
- CL clg(2024-25 리그 페이즈 포함)·cl16, EL elg(2026-27 리그 페이즈 포함)·elk(32강 'intermediate'·16강·8강·2020-08-10 단판 8강)·elsf, ELQ elq(2·3R·PO), ECLQ ecq(2023 PO), UCOL ecg·eck(16강·8강)·ecsf.
- 합산: UEFA ag = 2021-07-01 전, et 1. 벨기에컵 2016 준결승(베일리 기록 없음)은 ag 1·et 1 규칙만. 합산 기록 15행: 코크 1차 골·2차 도움, 로코모티바 1차 PK 골·2차 골·도움, 레인저스 1차 골, 히버니언 1차 골·2차 골·도움, 아약스 2차 골, 릴 2024 1차 도움, 올림피아코스 2024 1차 도움, 브뤼허 2025 1차 골·2차 도움, 릴 2026 2차 골.

## 6. 상대 Elo (기록 144: 같은 경기 39 / 팀×시즌 71 / 순위표 모형 16 / 직접 18)
- 순서: 같은 경기 다른 선수 자료(ents ±1일) → 통합표 → MAN → 순위표+모형.
- **벨기에 1부 2015-16·2016-17**: 데 브라위너·데이비드·토르강 아자르와 같은 회귀(a 1300.09, b 23.593) + kassiesa.net 벨기에 시즌 계수 2014-15 9.6(아자르 자료)·**2015-16 7.400(method4 ccoef2016)**·**2016-17 12.500(method4 ccoef2017)**·2017-18 2.6(데이비드 자료) → 평균 2015-16 1532.1, 2016-17 1477.0, 흩어짐 119, 16팀 곡선, lv '(리그 모형값)'. (2015-16 계수 평균 9.83은 회귀를 맞춘 범위 5.9~7.8보다 조금 높음 — 모형 3위 1649가 기존 헨트 2015-16 3위 1640과 맞아 그대로 씀.)
- **최종 순위**(영어 위키백과 시즌 문서 wikitext): 챔피언십 PO 1~6 + 정규 7~16. 2015-16: 브뤼허·안데를레흐트·헨트·헹크·오스텐더·쥘터 | 스탕다르 7·샤를루아 8·코르트레이크 9·메헬런 10·로케런 11·바슬란트베베런 12·STVV 13·무스크롱 14·베스테를로 15·OHL 16(TM 표는 STVV·무스크롱 순서 반대). 2016-17: 안데를레흐트·브뤼허·헨트·오스텐더·샤를루아·쥘터 | 메헬런 7·헹크 8·스탕다르 9·코르트레이크 10·로케런 11·STVV 12·오이펜 13·바슬란트베베런 14·무스크롱 15·베스테를로 16(기존 '헹크 2016-17 8위'·'스탕다르 9위'와 같음).
- 통합표 값 우선: 브뤼허 2015-16 1700, 헨트 2015-16·2016-17 1640, 안데를레흐트 2015-16 1640('벨기에 상위권'), 스탕다르 2016-17 1410.
- 직접(MAN, 모두 '추정'): 데설 2015-16 1250(벨기에 2부 10위/17, 스위스·체코 2부 1250 수준), 코크 시티 2016 1300(아일랜드 2위, 기존 아일랜드 2006 2위 1300), 로코모티바 자그레브 2016-17 1390(크로아티아 5위/10, 기존 4위 1430·8위 1350의 가운데), 라피트 빈 2016-17 1426(오스트리아 5위, 기존 오스트리아 5위 1426), 카를스루에 2017-18 1496(3. 리가 3위, 기존 3위 1496), 로트바이스 에센 2020-21 1300(레기오날리가 서부 2위, 독일 4부 1300), 볼턴 2022-23 1530(리그 원 5위, 기존 5위 1530), 히버니언 2023-24 1450(스코틀랜드 최종 8위/12 — 위키백과 team_order, 기존 4위 1500·10위 1400의 가운데), AZ 2023-24 1642(에레디비시 4위 순위값), 칼라마타 2026-27 1440(GR1 11월 중순 8위/14, 호프만 OFI 선례 2024-25 리그 수준 1475.5+119×곡선 — 6위 1492·7위 1462 재현).
- 스크래치 `node tools/elo_table.js`(186명): **값이 여럿인 팀-시즌 0**.

## 7. 동료·같은 경기 대조 (`--cross`, 다른 파일 수정 없음)
- 동료 도움→베일리 골: blr 2020-12-10 슬라비아 8'(실제 32' 골은 FM만 시크 도움, TM 없음 → 수치 무관), dia 2020-03-12 레인저스 88'·2020-11-08 묀헨글라트바흐 68'·2021-02-06 슈투트가르트 56'·2021-04-17 쾰른 5'·2021-04-24 프랑크푸르트 70'·2023-09-16 팰리스 90+11'(101분), wir 2020-11-05 베르셰바 5'·2020-11-21 빌레펠트 27' — 모두 '같음'.
- 베일리 도움→동료 골: blr 2018-12-16 65'·2020-10-22 83', dia 2020-10-26 94'·2021-01-19 14'·2021-04-17 51'·2023-10-29 49'·2024-05-02 52', els 2025-11-27 미트윌란 83', wir 2020-12-16 59' — 모두 '같음'.
- 같은 날·같은 상대 ents.json 전체와 대회·Elo·lv 차이 0. 뺀 TM 도움(헤르타 PK·샬케 자책골·루도고레츠)과 겹치는 동료 골 행 없음. **불일치 0.**
- 계산기의 다른 동료(래시포드·애슐리 영·디발라·엘 샤라위 외 로마 동료, 하베르츠·폴란트·벨라라비 외 레버쿠젠 동료)와 주고받은 골·도움은 위 목록 말고 없음(--cross 결과).
- 병렬 판정 선수(숄·사바니에·이코네·로텐) 파일은 읽지 않음. 베일리 G/A 경기 중 그 선수들의 클럽이 상대일 수 있는 경기: 릴 2024-04-11(UECL 8강 1차, 56' 맥긴 골 도움, Elo 1786 '리그1 2023-24 4위', eck, [1,1,0,0,0,1])·2026-03-19(EL 16강 2차, 85' 골, 1817 '리그1 2025-26 3위', elk, [2,1,1,0,0,1] — 산초 같은 경기 값). 그 밖에 몽펠리에·님·피오렌티나·PSG·랭스·바이에른(1990년대) 상대 G/A 없음.

## 8. 클럽·시즌·integration
- 경계(TM 이적 API): 2017-01-31(레버쿠젠), 2021-08-04(빌라), 2025-08-20(로마 임대), 2026-01-21(빌라 복귀), 2026-09-02(올림피아코스). build가 클럽 id와 날짜 경계 대조.
- 시즌: genlb jul10(2016-07-14 ELQ = 2016-17; genjd 선례), avllb jul10(avlay 선례, 7월 경기 없음), levlb는 **바이에른 묶음(bayt: 7월 10일 + 2020.7.1~9.1 = 2019-20)** — 2020-08-06 레인저스 16강 2차·08-10 인테르 8강이 2019-20. add_players.py가 지원하지 않으므로 integration.json에는 jul10으로 넣고, **스크래치에서 jul10 목록의 `levlb`를 빼고 `if(club==="bayt"||` 묶음에 `club==="levlb"`를 손으로 넣음(오케스트레이터 적용 필요)**. romlb·olylb 기본(8월 1일).
- pos RW, **flag JM — flagBody에 자메이카 없음(오케스트레이터 추가 필요)**, retired false.
- hon(TM 업적): t.UEL '25/26 애스턴 빌라'(산초 선례; 결승 미출전이지만 TM대로, NOTE에 적음), o 'DFB-포칼 준우승 19/20 레버쿠젠'(결승 76분 출전). a.XI '17/18 분데스리가 · VDV(선수협회)'(en.wiki VDV 시즌 팀 2017-18 목록에 베일리, 스크래치 union/raw/en_vdv.txt 776행; de.wiki 'Mitglied der VDV 11: 2017/18'). 뺀 것: VDV 신인상 17/18(신인상), 벨기에 젊은 프로 선수상 2016(신인상·언론/협회 기타), 골드컵(대표팀), 대회 참가 기록, 분데스리가 시즌 팀(구단/리그 외부 매체 선정)·이달의 골·UECL 시즌 팀·빌라 이달의 선수. PFA·AIC 명단에 베일리 없음.

## 9. 검증 (스크래치, ailton 앵커)
- 스크래치에서 다른 새 판정 파일(iko·rot·sav·scl) 제거 → add_players(ailton) → levlb 시즌 분기 수동 → build → `verify check`: 기준 185명 동일, 레온 베일리 '추가', 탭 글자 변경 0, 콘솔 오류 없음 → 통과. `elo_table.js`(186명) 충돌 0.
- §16(build 내장): 중복 0, 스코어 역순 0, E 날짜 전부 M에 있음, 같은 날 두 경기 0, 분 범위 OK, 도움 득점자 이름 모두 있음, E 상대·대회 = M 행.
- pStats: SOC 132.84, 412경기 79골 65도움 24,579분, 최고 3시즌 23.25(2023-24 26.43·2020-21 22.92·2017-18 20.41), 5시즌 19.16(+2019-20 14.37·2022-23 11.65).

| 클럽 | 경기 | 골 | 도움 | 분 | SOC |
|---|---|---|---|---|---|
| KRC 헹크 | 77 | 16 | 16 | 5,888 | 20.54 (15%) |
| 바이어 레버쿠젠 | 156 | 39 | 22 | 9,555 | 64.35 (48%) |
| 애스턴 빌라(두 시기) | 163 | 23 | 25 | 8,687 | 47.31 (36%) |
| AS 로마(임대) | 11 | 0 | 2 | 318 | 0.65 |
| 올림피아코스 | 5 | 1 | 0 | 131 | <0.01 |

- 상위 기록: 2024-04-14 아스널 84' 골(0-0) 4.86 · 2023-12-06 맨시티 74' 골 4.65 · 2022-09-03 맨시티 74' 골(0-1) 3.10 · 2021-04-24 프랑크푸르트 70' 2.84 · 2025-01-04 레스터 76' 2.82 · 2019-11-30 바이에른 35' 2.58 · 2020-11-08 묀헨글라트바흐 68' 2.53 · 2020-02-08 도르트문트 81' 2.47 · 2019-02-02 바이에른 53' 2.40 · 2019-11-30 바이에른 10' 2.18.
