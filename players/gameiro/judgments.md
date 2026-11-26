# 케빈 가메이로(Kevin Gameiro) 판정 기록

Transfermarkt id 27389 · FotMob 26392 · 프리셋 `gameiro` · 접두어 `GAM`(GAM_E/GAM_M/GAM_NOTE, src/data·index.html에 없음 확인) · 파일 `gam.js` · final_scores 인자 `gameiro:GAM:27389`.
재현: `python3 players/gameiro/build_gameiro.py` (raw/ → gameiro.json, gam.js). 요렌테 build 스크립트(같은 수집 형식)를 바탕으로 함. 보조: assist_checks.py, man_elo.py, note_gameiro.py.

## 1. 범위
- 715경기(TM performance-game 클럽 공식 경기 전부) · 240골(PK 23) · 66도움 · 42,381분. 90분 추정 없음.
- 제외: 스트라스부르 2군 2004-05(CFA 4부·아마추어·2군, TM 경기 기록 없음, en.wiki 서술 20경기 4골). 그 밖에 비프로 시즌 없음(리그1·리그2 2006-07·라리가).
- 실롱스크 브로츠와프 2013.8.22 유로파 예선 플레이오프 1차전(en.wiki 12 vs TM 13): TM이 90분 출전·85분 골로 적음, ESPN 골 확인 → 넣음.
- FotMob 2017.12.30 알아흘리전 3골: 친선(FotMob Club Friendlies) → 제외.

## 2. 날짜·클럽·시즌
- 날짜: TM API UTC → 경기장 현지 시간대(raw/tm_games.csv date_local_tz_conv). 715경기 모두 TM 일정 날짜와 같음, 고친 날짜 없음.
- 클럽 경계(TM 이적일): strgam ~2008-07-01, lorgam ~2011-07-01, psggam ~2013-07-25, sevgam ~2016-07-30, atmgam ~2018-08-12, valgam ~2021-07-18, strgam(2021~2024, 같은 키). 모든 경기가 경계와 TM 클럽 id 일치.
- 시즌: 모두 8월 1일 기준(7월 경기 없음) → seasonOf 예외 없음, integration season 목록 비움.

## 3. 대회 코드
- FR1·FR2·ES1 = lg. 쿠프 드 프랑스·쿠프 드 라 리그·코파 델 레이: 'Quarter-Finals' dk, 'Semi' dsf, 'Final' df, 나머지(Second~Seventh Round, Fourth/Fifth/Sixth, Round of 16, 4th round, intermediate stage, Third Round) dc.
  * 처음에 요렌테 템플릿(FA컵용 'sixth round'=dk)이 남아 쿠프 드 프랑스 'Sixth Round'(32강 전후)가 dk로 나왔으나, docs 3절 규칙(16강까지 국내컵)과 메넨·파스토레·라베치 자료(사블레 2012.1.20·아라스 2013.1.6 = dc)에 맞춰 dc로 고침.
- 수페르코파 2019-20 준결승(2020.1.8 레알 마드리드, 단판) = dsf(docs 3절 4팀 슈퍼컵 준결승, 이스코·그리즈만 같은 대회 dsf). 출전만, 골·도움 없음.
- UEFA 슈퍼컵 2015(바르셀로나, 연장) = df, 72분 PK 골은 정규시간.
- ELQ(2011 디페르당주, 2013 실롱스크 플레이오프) = elq. UEFA컵 2005-06 조별 elg, 32강(intermediate stage, 리텍스) elk. 유로파 'Second Round'(2014 마리보르 32강)·intermediate stage = elk.
- ko: 'leg' 들어간 라운드는 합산(ko 0 + tie), 조별 ko 0, 나머지 단판 ko 1. 코파 델 레이 2019-20 3라운드·16강은 단판.

## 4. 두 경기 합산
- 합산 행 52개(41경기). UEFA 대회(2020-21까지)·코파 델 레이(2018-19까지) 원정 다득점·연장. 다른 차전 스코어는 TM 리포트(tmapi JSON 경기 3135869 셀틱 2차전은 같은 두 팀 1차전 2-0을 찾아 씀). 수동 점검: 셀틱 [2,1,2,0], 스포르팅 히혼 2차전 [2,1,1,2], 아스널 2019 [2,1,1,3], 샤흐타르 [2,1,2,2], 크라스노다르 [2,0,2,1].

## 5. 골
- TM 이벤트 240골 = API 240(PK 23 = API). 자책골 없음. 상대 자책골을 본인 골로 바꾼 것 없음.
- 3840077 2022.10.23 툴루즈 73분 'Penalty rebound' → 일반 골(API penGoals 0과 같음).
- 3142944 2019.1.8 코파 스포르팅 히혼 원정 45분: FotMob·스카이·Sports Mole = 파레호, TM·ESPN·Sporting Life·영어 위키백과 '2018–19 Valencia CF season' 경기 상자 = 가메이로 → 가메이로 골(fr.wiki 239골의 차이가 이것).
- 연장 골 1개: 2009.1.24 쿠프 드 프랑스 투르전 108분(et 1).
- FotMob 대조: 2010-11 이후 175골 중 위 1개 외 수·순서·PK 같음, 2013.9.1 말라가전 TM 73분/FotMob 71분(TM 분 사용). 2010-11 전·FotMob 빈 경기는 ESPN이 230/231 확인(39443 2006.2.4 랑스전은 ESPN 득점자 목록 없음, en.wiki 2005-06 리그 1골과 맞음).

## 6. 도움(TM 78 → 66)
- 뺀 것: PK 유도 8(2008.8.9 르망, 2008.11.1 그르노블, 2011.4.30 랑스, 2011.10.29 캉 76분 네네, 2015.9.15 묀헨글라트바흐, 2018.11.10 헤타페, 2022.4.17 트루아, 2022.10.1 렌), Shot on goal 2(2009.10.18 니스 48분, 2015.1.8 그라나다 32분), 상대 자책골 유도 1(2014.4.20 그라나다 14분 마인스 자책골), 2014.8 이후 단일 출처 확인 못 함 1(아래).
- 본인 PK 골 본인 도움 표기 2개(2594552, 2805642)는 도움 아님(API 도움 수에도 없음).
- 2014.8 전: TM 유형 Pass/Cross/Header/빈칸은 유지(빈칸 2: 3966602 오스트발트 2분 툼, 2284590 아라스 68분 라베치).
- 2014.8 이후: TM+FotMob 이벤트 일치 35개 유지. FotMob 이벤트에 없는 3개(assist_checks.py):
  * 2518536 2015.1.14 코파 그라나다 64분 데니스 수아레스 — 넣음: ESPN(410785) 도움 + Sports Mole 문자 중계("Graneiro[sic] picked up the ball inside the area ... lay it off to Suarez").
  * 2594711 2016.2.21 라요 원정 20분 이보라 — 뺌: ESPN만 도움, 라리가 공식 기사 "an effort from Kevin Gameiro was pushed away by Juan Carlos, but Vicente Iborra was first to react" = 슈팅 리바운드.
  * 2810016 2017.1.3 코파 라스팔마스 원정 51분 그리즈만 — 넣음: ESPN(470815) + FourFourTwo 경기 기사("nodded the ball across the face of goal for his compatriot Griezmann").
- FotMob 전용 도움 없음, FotMob 선수 경기 목록 전용 도움 없음.

## 7. 상대 Elo
- 306기록: 같은 경기 다른 선수 자료 84, 기존 팀×시즌 값 209, TM 순위표 → 라벨 8, 순위표 밖 직접 라벨 5. 기존 표 값과 라벨 계산 값 차이 0.
- 새 팀×시즌(raw/ranks.txt TM 최종 순위표): 이스트르 리그2 2006-07 19위/20팀 1329, 괴뇽 리그2 2006-07 10위/20팀 1381, 메스 리그2 2010-11 17위/20팀 1343, 스포르팅 히혼 세군다 2018-19 9위/22팀 1614, 셀틱 스코틀랜드 1부 2018-19 1위/12팀 1642(기존 셀틱 2018-19 값 없음, 2018-19 스코틀랜드 라벨 형식은 기존 자료와 같게 '플레이오프·스플릿 뒤 최종 순위').
- 순위표 밖(man_elo.py, 프랑스어 위키백과):
  * FC 오스트발트 2006-07: 'Coupe de France de football 2006-2007' 8라운드 "RC Strasbourg (L2) 6-0 Ostwald (District)" → 디스트릭트 리그(1 L1·2 L2·3 National·4 CFA·5 CFA2·6 DH·7 DHR·8 PH 아래) 9부로 추정, 순위 없음 = 기준값 689. **추정·근거 약함**(O는 하한 0.3 근처).
  * 가젤렉 아작시오 2006-07: 같은 문서 "(CFA)", 'Championnat de France de football de quatrième division 2006-2007' B조 18팀 중 7위 → 1202.
  * US 알랑송 2008-09: 'Coupe de France de football 2008-2009' "CFA 2 (Div 5)", '...cinquième division 2008-2009' G조 17팀 중 6위 → 1106.
  * 아부안 시농 2023-24: 'Coupe de France de football 2023-2024' "(N2)", '...quatrième division 2023-2024' B조 14팀 중 12위 → 1155.
  * 로그로녜스·쿨투랄 레오네사 2019-20, 방데 퐁트네 2010-11은 골·도움 기록이 없어 Elo 불필요.
- 스크래치 복사본: league_rank_apply --apply 바뀌는 행 0(gam.js 그대로), 리그 도구 4개 이동 ±1 이하(반올림), elo_table 값이 여럿인 팀-시즌 0.

## 8. 같은 경기·동료 대조
- 그리즈만(grz) 도움↔골 18건, 디에구 코스타·토레스·레예스·이브라히모비치·라베치·메넨·파스토레·마린·아스파스 모두 날짜·분·스코어·대회·Elo·lv 같음.
- 이번 차례 병행: 요렌테(세비야 2015-16 동료) — 2015.12.12 스포르팅 히혼 75분 가메이로 PK 골, 요렌테 도움(PK 유도)은 요렌테 자료에서 빠졌고 이 자료도 도움자 없음. Elo는 통합표 라리가 2015-16 17위 1835. 2016.2.18 몰데전은 요렌테 자료 값(1426)과 같음. 시세: 2008.5.17 마르세유-스트라스부르(이 자료 상대 마르세유 2007-08 3위 1772, 통합표 값, 가메이로 골·도움 없음). 아이마르·클라우디오 로페스와 겹치는 경기 없음.
- 기존 자료 불일치: 없음(처음 보인 라베치·메넨·파스토레와의 dk/dc 차이는 이 자료 쪽 오류였고 고침).

## 9. 수상·통합
- hon: LG 12/13 PSG · UEL 17/18 아틀레티코, 15/16·14/15·13/14 세비야 · DC 18/19 발렌시아 · XI 10/11 리그1 · UNFP(선수협회)(fr.wiki 'Trophées UNFP du football 2011' 올해의 팀 공격수 소와 가메이로 확인). 준우승·대표팀·유로파 시즌 팀 제외.
- 클럽 색: 기존 clubcolors 값 재사용(스트라스부르 strmt, 로리앙 lorgu, PSG, 세비야 sevas, 아틀레티코, 발렌시아 valad).
- 국기 FR(있음), 포지션 CF, 은퇴(2025.3.16).
