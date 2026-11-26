# 마우로 이카르디 (Mauro Icardi) 판정 기록

- Transfermarkt 선수 id **68863**, FotMob 282770. 프리셋 `icardi`, 접두어 `ICA`(src/data·기존 상수에 없음 확인), 데이터 파일 `ica.js`. final_scores 인자 `icardi:ICA:68863`.
- 재현: `python3 players/icardi/build_icardi.py` (raw/ → `ica.js`·`icardi.json`). 보조 파일: `assist_checks.py`(2014.8 이후 단일 출처 도움 판정·FotMob 전용 도움 추가), `goal_checks.py`(비어 있음), `man_elo.py`(비어 있음), `note_icardi.py`(설명).
- 라베치 build(같은 수집 형식)를 바탕으로 함. 데이터 기준일 2026-11-21.

## 결과

- 478경기 250골(PK 39) 58도움, 33,796분. 기록 308개, 두 경기 합산 11행/7경기.
- 클럽별(경기·골·도움): 삼프도리아 33·11·2, 인테르 219·124·25, PSG 92·38·7, 갈라타사라이 134·77·24.
- 수치(SOC·3/5-peak·SOC-CAR·클럽별 SOC)는 최종 보고 참조(스크래치 복사본 verify).

## 1. 범위·소속

- **현재 소속 없음**(TM 2026.7.1 Without Club, FotMob primaryTeam 없음, 영어 위키 'free agent'), 은퇴 발표 없음 → `retired: false`(산초 v1.2xx·팔카오 선례: 무소속이어도 은퇴 아님). 설명 마지막 줄에 기준일·마지막 반영 경기(2026.5.17 카슴파샤전 90분).
- 삼프도리아 2011-12 세리에B(이탈리아 2부, 프로) 2경기 1골 → 넣음(v1.159 프로 리그 규칙). 삼프도리아 프리마베라 39경기(유소년), 바르셀로나 유소년 → 제외. 아르헨티나 대표 제외.
- 친선(FotMob에만 있는 ICC·클럽 친선 15경기) 제외.

## 2. 경기·출전 분

- TM performance-game 그대로(478경기, 빈칸 없음). 영어·이탈리아어 위키 클럽·시즌별 경기·골 = TM.
- **2021.2.10 쿠프 드 프랑스 캉-PSG**: FotMob만 90분 출전. Maxifoot 경기 기록(교체 명단 'M. Icardi', 투입 없음)·culturepsg 라인업 = 미출전, TM 'in squad' → 넣지 않음.
- 2017.12.12 포르데노네전 TM 40분 vs FotMob 10분 → TM.

## 3. 날짜

- 이탈리아·프랑스·튀르키예·유럽 원정만. TM 일정 날짜 = TM API 시각의 현지 변환(빌드에서 478경기 확인), 수집기 날짜 불일치 0.

## 4. 골 (TM 250 = 기록 250)

- 자책골 2개(2016.10.2 로마전 76분 Manolas 헤더 굴절, 2024.3.17 카슴파샤전 34분; TM·FotMob 모두 OG) → 본인 골 아님, 스코어 계산에만 넣음.
- 2023.4.14 카이세리스포르전 45+12분 'Penalty rebound' → PK 아님(같은 경기 42분 PK 골은 PK). PK 39 = TM penGoals.
- **2019.1.31 코파 이탈리아 8강 라치오전**(1-1 연장, 승부차기 패): 120+5분 골은 연장 추가시간 PK(D'Ambrosio 파울 유도)로 TM 경기 이벤트·FotMob 경기 이벤트(120분 PK, 1-1, shoot-out 아님)·ESPN(120'+5') 모두 같음 → 정상 골(연장 골 et 1, 분 125, 표기 120+5). FotMob 선수 경기 목록 '0골 90분'은 틀린 기록. 승부차기 골 아님.
- **2024.4.7 튀르키예 슈퍼컵 결승 페네르바흐체전(몰수, v1.203)**: 1분 이카르디 골 뒤 페네르바흐체(U19)가 경기장을 떠나 중단, PFDK가 갈라타사라이 3-0 몰수승. TGRT Haber(2024.4.11 'Icardi'nin golü geçerli sayılacak mı?')는 징계 규정상 몰수패 팀의 골은 무효지만 몰수승 팀 선수의 골은 공식 기록에 남는다고 보도, TM·영어 위키(2023 Turkish Super Cup 문서 goals1 = Icardi 1')도 골로 셈 → 골 넣음(골 전 0-0, 출전 2분, 대회 결승 df). TFF 원문 확인은 못 함 — 설명에 적음. 상대 Elo는 페네르바흐체 2023-24 리그 순위값(U19 출전은 반영 안 함).
- FotMob 대조: 250골 모두 수·순서·PK 같음(2013.1.27 페스카라전 61·64분 vs FotMob 56·59분 → TM).
- 2021.5.19 쿠프 드 프랑스 결승 모나코전 19분: 수집기 비교의 '스코어 0-1'은 FotMob 홈·원정 표기 차이일 뿐(TM PSG 홈 1-0).

## 5. 도움 (TM 68 → 58)

- 2014.8 이전 TM 단일 출처 허용. 뺀 것: PK 유도 6(2012.12.16 카타니아 Maresca, 2013.5.18 유벤투스 Éder, 2019.12.4 낭트 Neymar, 2021.1.13 마르세유(트로페) Neymar, 2021.1.31 로리앙 Neymar, 2021.3.10 바르셀로나 Mbappé), 'Shot on goal' 3(2015.1.11 제노아 Palacio, 2019.1.13 베네벤토 Candreva, 2024.3.17 카슴파샤 Carlos Vinícius). 본인 PK 골의 본인 도움 표기 13개(TM API 도움 수에도 없음) → 도움 아님.
- 2014.8 이후 TM+FotMob 경기 이벤트 일치 52개는 넣음(그중 ESPN은 도움자를 안 적은 것 포함 — 규칙상 TM+FotMob 일치로 충분, ESPN은 보조). 2013.5.5 우디네세 Éder(ESPN만 확인)는 2014.8 이전이라 TM 기준으로 넣음.
- 2014.8 이후 TM 단일 출처 판정(`assist_checks.py`, 웹 확인 2026-11-21):
  - 넣음: **2026.1.13 튀르키예컵 페티예스포르전 80분 Barış Alper Yılmaz** — DHA 경기 기사('Sol çaprazdan Icardi'nin ortasında Barış Alper kafayı vurdu') + 하베르튀르크 기사('Icardi arka direğe ortaladı') (+ A Spor 문자 중계/gzt 'Icardi'nin arka direğe kestiği topa').
  - 뺌: **2014.12.15 키에보전 19분 Kovacic** — inter.it 경기 센터 '나가토모 크로스, 이카르디 헤더 떨굼, 문전 혼전(mischia in area)에서 코바치치' → 혼전 볼(라베치 2015.3.4 '카파유아주' 선례). Liputan6는 바로 연결로 적었지만 공식 기록이 혼전이라 뺌. **2015.2.23 칼리아리전 47분 Kovacic** — 경기 기사 'pounced on the loose ball' → 혼전 볼, 다른 출처 없음.
- FotMob만 적은 도움(TM 없음):
  - 넣음: **2020.1.29 쿠프 드 프랑스 16강 포전 25분 Paredes** — Maxifoot(골 설명 'Icardi remet de la poitrine en direction de Paredes', 평점 'passe décisive à Paredes'), Omnisport(mykhel: 'laid Kurzawa's cross into the path'), Goal.fr('sur une remise de Mauro Icardi'), PSG 공식('chesting into Paredes' path') → 독립 2곳 이상. (Maxifoot은 수비 실수를 함께 적었으나 도움으로 명시.)
  - 뺌: **2017.1.14 키에보전 86분 Perisic** — inter.it 경기 기사·문자 중계 'Icardi wins it back and feeds/releases Perisic' 1곳 확인, 442(Perfil)는 '이카르디의 볼 탈취'만 적어 도움 근거로 부족, ESPN·TM 없음 → 2곳 확인 실패로 뺌(사용자가 다시 볼 항목).
- 2014.8 이후 도움 합계 54(TM+FotMob 52 + TM 단일·웹 확인 1 + FotMob 전용·웹 확인 1), 그 전 4(삼프도리아 2·인테르 2013-14 2).

## 6. 대회 코드·합산

- IT1·IT2·FR1·TR1 lg. CIT·FRC·FRL·TRP: 16강까지 dc, 8강 dk, 준결승 dsf, 결승 df(쿠프 드 프랑스 5·6라운드 dc). 튀르키예컵 2025-26 조별(A조) ko 0 dc(메르턴스 선례). FRCH df. TRS: 단판 결승 df, 2025-26 4팀 대회 준결승 dsf(사네 san.js 같은 경기 같음).
- CL: 조별·2025-26 리그 페이즈 clg, 녹아웃 PO(intermediate)·16강 cl16, 8강 clk, 준결승 clsf. CLQ clq, ELQ elq. EL: 조별·2024-25 리그 페이즈 elg, 32강·16강 elk.
- 두 경기 합산: UEFA 대회 2020-21까지 원정 다득점·연장, 2021-22부터 연장만. 코파 이탈리아 준결승(2016 유벤투스 1차전, 기록 없음) 규칙 (1,1). E 행이 있는 합산 경기 7개: 스타르난 1·2차전(ELQ), 볼프스부르크 1차전, 올림피야 2차전(1차전 3-0), 몰데 1·2차전, 스파르타 프라하 1차전.

## 7. 상대 Elo·순위 라벨 (v1.226)

- 순서: 같은 경기 다른 선수 자료 156 → 통합표 같은 팀·시즌 141 → 순위표 라벨 11. 통합표 값과 라벨 계산 차이 0.
- **새 팀×시즌 8개**(값은 tools/league_rank_apply.py로 라벨에서 계산):
  - Stjarnan Gardabaer 2014 `아이슬란드 1부 2014 1위/12팀 (Úrvalsdeild karla (Pepsideild))` 1503 (TM 표, 2014 우승)
  - Qarabağ FK 2014-15 `아제르바이잔 1부 2014-15 1위/10팀 (Azerbaijan Premier League)` 1556
  - Hapoel Beer Sheva 2016-17 `이스라엘 1부 2016-17 1위/14팀 (…플레이오프·스플릿 뒤 최종 순위)` 1561
  - Pau FC 2019-20 `프랑스 3부 2019-20 1위/18팀 (Championnat National, 리그 수준 추정)` 1406 (영어 위키 2019-20 Championnat National 최종 표 team1=PAU, 코로나 중단·승점률 순위, 우승 '수여 안 함')
  - Konyaspor 2025-26 `쉬페르리그 2025-26 9위/18팀` 1530, Kasimpasa 13위 1484, Genclerbirligi 14위 1466 (TM 2025-26 최종 표; 통합표의 같은 시즌 다른 팀 순위(Fatih Karagümrük 18·Kayserispor 17·Antalyaspor 16·Eyüpspor 15·Alanyaspor 11·Rizespor 8·Göztepe 6·Trabzonspor 3)와 모두 맞음)
  - Fethiyespor 2025-26 `튀르키예 3부 2025-26 13위/18팀 (TFF 2. Lig Kırmızı Grup, 리그 수준 추정)` 1097 (TM 표 + 영어 위키 'Template:2025–26 2. Lig Red Group standings' update=complete team13=FET)
- 페녜·올누아(Entente Feignies Aulnoye) 2021-22: 수집기는 못 찾았으나 영어 위키 2021-22 Championnat National 3 Group I(오드프랑스) 최종 2위/14팀, 통합표에 음바페 자료 값 `프랑스 5부 2021-22 2위/14팀 (National 3 Groupe Hauts-de-France, 리그 수준 추정)` 1159가 있어 같은 경기 값 사용(순위 없음 라벨 불필요).
- 스크래치 복사본: `league_rank_apply.py` 바뀌는 행 0, 다섯 리그 도구 이동량 0(±1 반올림), `node tools/elo_table.js` 값이 여럿인 팀-시즌 0.

## 8. 같은 경기 다른 선수 자료 대조 (수정 없음)

- 페리시치(per.js)·칸드레바(can.js)·포돌스키(pod.js)·폴리타노(pol.js)·음바페(mba.js)·디 마리아(dim.js)·드락슬러(dra.js)·네이마르(ney.js)·메르턴스(mer.js)·오시멘(osi.js)·사네(san.js): 이카르디 도움 ↔ 그들 골, 그들 도움 ↔ 이카르디 골 모두 날짜·분(±2)·스코어·대회·Elo·lv 같음. 같은 경기 Elo/lv/대회 불일치 0, 출전 행 대회 코드 불일치 0.
- TM이 이카르디 도움으로 적었으나 뺀 것과 겹치는 남의 골(그쪽 파일 도움자 없음, 일치): can.js 2019.1.13(Shot on goal), mba.js 2021.3.10(PK), ney.js 2019.12.4·2021.1.13·2021.1.31(PK).
- 이번 차례 다른 판정과 겹칠 수 있는 경기(그쪽 파일 읽지 않음): **쿠치뉴** — 2018.10.24·2018.11.6 챔스 조별 인테르-바르셀로나(쿠치뉴 바르사 2018-19; 이카르디 11.6 87분 골, 상대 FC Barcelona 2112 '라리가 2018-19 1위' = 통합표 값), 2021.2.16·3.10 PSG-바르셀로나(쿠치뉴 부상, 이카르디 E 행 없음: 3.10 도움은 PK 유도라 뺌), 2013.4.3 삼프도리아-인테르(쿠치뉴는 2013.1 리버풀 이적, 해당 없음). **하메스** — 2019.9.18·11.26 챔스 PSG-레알 마드리드(하메스 레알 2019-20; 이카르디 E 행 없음). 빌토르·두카와는 겹치는 경기 없음(기간·클럽).

## 9. 시즌·클럽

- 클럽 키(index.html 미사용 확인): sampic 삼프도리아, intic 인테르, psgic PSG(임대+완전 이적 한 키), galic 갈라타사라이(임대+완전 이적 한 키). 경계(TM 이적일) 2013-07-09 / 2019-09-02 / 2022-09-08. 경기 클럽과 불일치 0.
- 시즌: 모두 기본 8월 1일(특수 seasonOf 없음). 시즌 경기 수: 2011-12 2 … 2025-26 47.
- 색: sampic = 기존 삼프도리아(#2345C0·#FFFFFF·#E2001A), intic = 인테르(#0068A8·#000000), psgic = PSG(#003665·#D32A31·#FFFFFF), galic = 갈라타사라이(#A32638·#FFB300).
- 국기 AR(flagBody 있음), 포지션 CF.

## 10. 우승·수상 (hon)

- TM 업적 페이지(FotMob trophies·영어 위키 Honours와 같음): 리그 19/20·21/22 PSG, 22/23~25/26 갈라타사라이; 국내컵 19/20·20/21 PSG, 24/25 갈라타사라이; 리그컵 19/20 PSG; 슈퍼컵 20/21·22/23 PSG(트로페 2021.1·2022.7), 23/24 갈라타사라이(몰수 결승). 세리에B 승격·준우승 제외.
- 개인: TOP 23/24 쉬페르리그 25골·17/18 세리에A 29골·14/15 세리에A 22골(TM 'Top goal scorer'; 프리마베라 득점왕은 유소년이라 제외, TM 'Top scorer'(골+도움, 23/24 34·25/26 슈퍼컵 2)는 득점왕이 아니라 제외).
- TM 'Footballer of the Year 2018 (Inter)' = AIC 그란 갈라 2017-18 올해의 선수(영어 위키 Serie A Footballer of the Year 목록 2017-18 Icardi) → `POY 17/18 세리에A · AIC(선수협회)`(FOY와 중복하지 않음). AIC 올해의 팀 2014-15·2017-18(영어 위키 Serie A Team of the Year) → `XI`. 'Footballer of the Year 2023 (Galatasaray)' = 밀리예트 튀르키예 올해의 선수 → `FOY 2023 갈라타사라이`(오시멘 형식). 쉬페르리그 시즌 팀 2022-23은 주관 기관 불명확(선수협회·사무국 공식 확인 못 함)이라 뺌. TM 시즌 선수 제외.

## 11. 사용자가 다시 볼 만한 판단

1. 2024.4.7 몰수 슈퍼컵 결승 1분 골을 넣음(보도·TM·위키 근거, TFF 공식 원문 미확인).
2. 2017.1.14 키에보전 페리시치 골 도움(FotMob + inter.it)을 2곳 확인 실패로 뺌.
3. 2014.12.15·2015.2.23 코바치치 골 두 개를 혼전 볼로 보고 뺌.
4. 2020.1.29 포전 파레데스 골 도움(FotMob만, 기사 다수)을 넣음.
5. 무소속 상태를 은퇴로 보지 않음(retired false).
