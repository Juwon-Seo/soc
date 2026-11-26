# 스턴 존 (Stern John) 판정 기록

- Transfermarkt 3793, soccerbase 18633, FotMob 30816(경기 자료 없음). 프리셋 `sternjohn`, 접두어 `STJ` (stj.js; src/data에 같은 파일·`STJ_` 상수 없음 확인).
- 빌드: `SOC_ROOT=<스크래치 복사본> python3 players/sternjohn/build_sternjohn.py [--out …/src/data]` (`--stat`·`--ties`·`--debug`·`--mapneed`). 설명은 `note_sternjohn.py`. 로비 킨 build(같은 수집기 형식)를 고친 것.
- 결과: **450경기 155골(PK 5) 18도움, 29,383분**, 기록 행 173, 두 경기 합산 2행(2경기). 은퇴(TM 2018.1.1), 마지막 경기 2010.5.2 팰리스–셰필드 웬즈데이(6분).

## 1. 범위 (career.txt)
- 넣음: TM 1군 공식 경기 446 + TM에 없는 4경기(3절) = 450. 클럽: 뉴올리언스 1·콜럼버스 70·포리스트 80·버밍엄 85·코번트리 88(두 시기 한 키)·더비 7·선덜랜드 16·사우샘프턴 52·브리스틀 시티 26·팰리스 16(두 시기 한 키)·입스위치 9.
- 뉴올리언스 리버보트 갬블러스(TM 'New Orleans Storm') 1997: 팀은 USISL A-League = 당시 미국 2부(위키백과 New Orleans Storm 문서 'the second division USISL A-League') — 프로 리그 규칙(미국 USL 2부 프로)으로 시즌 포함. 그러나 경기별 자료는 TM의 US 오픈컵 3라운드 댈러스 번전 1경기뿐(0-3, 90분) → 그 1경기만. A리그 26경기 16골(위키 인포박스)과 오픈컵 2라운드 오스틴 론스타스전(1997.7.1, 출전 여부 모름)은 경기별 자료 없어 제외(크레스포 선례).
- 제외: 캐롤라이나 다이너모 임대 1997(5경기 0골, 경기 자료 없음), 몰타 카리브 알콘스·노스 이스트 스타스·WASA·새들 힐·센트럴 FC(T&T, 경기 자료 없음/센트럴 TM 출전 0), 솔리헐 무어스(6부 비프로, 출전 0), 대표팀·친선·올스타.

## 2. 날짜 (S8, S5, S6, S9)
- 미국 71경기 전부 TM 자리표시 시각. 위키백과 `1998 Columbus Crew season`·`1999 Columbus Crew season`(경기 상자 날짜)과 대조: MLS 정규·플레이오프·오픈컵 모두 같은 날짜, 다른 것은 2개뿐 → 고침(`DATE_FIX`):
  - 1997 오픈컵 3라운드 뉴올리언스 0-3 댈러스 번: TM 7.28 → **1997-07-29** (RSSSF usa97 'Tuesday, July 29'·영어 위키 1997 U.S. Open Cup)
  - 1999 오픈컵 3라운드 콜럼버스 3-0 상대: TM 7.12·'Salem City FC' → **1999-07-13, Carolina Dynamo** (RSSSF usacup99 '[Jul 13] Columbus Crew 3-0 Carolina Dynamo'·영어 위키 1999 U.S. Open Cup·1999 Crew 시즌 문서; 골 47'·84' TM과 같음)
- 잉글랜드: soccerbase 369경기 날짜 전부 TM과 같음(soccerbase_vs_tm.csv) → 고칠 것 없음.
- 더비 임대: TM 이적 기록 2005.5.16은 오류(존은 2005.5.8까지 코번트리 출전, TM 더비 2005.5.18 '명단 제외'), 위키 2005.9.16~12.16 → 클럽 경계 2005-09-16 / 2005-12-16. 첫 더비 경기 2005.9.18.
- 입스위치 임대 2009.11.29~2010.1.30(TM; 1.30 경기는 입스위치) → 경계 2010-01-31.

## 3. TM에 없는 경기 (S1, S2)
- **2002 퍼스트 디비전 승격 플레이오프 3경기**(soccerbase 3행·영어 위키 경력 표 'Other 3경기 1골'·위키 2002 Football League play-offs/결승 문서):
  - 4.28 준결승 1차전 홈 밀월 1-1: ESPN 48339 라인업 선발·교체 없음 → 90분, 무득점.
  - 5.2 준결승 2차전 원정 밀월 0-1: ESPN 48383 선발·교체 없음, 골 이벤트 90' Stern John; 아이리시 타임스 'Goals: John 90', '추가시간 57초' → **90+1분**(91, 표시 '90+1'), 스코어 전 0-0. 도움(비커스 크로스)은 존 기록 아님.
  - 5.12 결승(카디프 중립) 노리치 1-1 연장(승부차기 4-2): ESPN 48461 선발·교체 없음 → 120분. 존의 승부차기 성공은 골 아님.
  - **102분 호스필드 동점골 도움 넣음**: ESPN 48461 문자 중계 "Long free-kick is headed back across the area by Stern John. Horsfield seizes on it."; 아이리시 타임스 2002.5.13 'Revival under Bruce complete' "Jeff Kenna crossed for Stern John to head back across goal… Geoff Horsfield bundled the loose ball in"; 영어 위키 결승 문서 본문(BBC 인용) "Kenna crossed for John who headed the ball back across goal… Horsfield to head the ball in". 독립 출처 3곳이 존의 헤더가 마지막 연결이라고 적음(앞 단계 프리킥/크로스만 다름; 아이리시 타임스 'loose ball' 표현은 굴절 서술이 아니라 골키퍼가 비운 문전) → 도움. 스코어 전 0-1, 연장 1, 단판 1.
  - 비중: 승격 플레이오프 = 리그(애슐리 영 2006 왓퍼드 선례 `lg`). 준결승 합산 tie `[1|2, 홈, …, 원정 다득점 0, 연장 1]`(EFL 플레이오프는 원정 다득점 없음·연장 — 애슐리 영 선례 `[1,0,0,0,0,1]`), 2차전 `[2,0,1,1,0,1]`. 결승 ko 1.
  - 상대 Elo: 밀월 2001-02 4위 1575, 노리치 6위 1559(기존 팀×시즌 값).
- **2006.9.23 크리스털 팰리스 1-0 코번트리**(챔피언십 9라운드): TM 선수 목록에 없음(TM 경기 56916 날짜 'Unknown', API 500). soccerbase 출전 + 코번트리 팬 매치 리포트 2곳(coventrycity-mad.co.uk Kev Monks '68th minute substitution… Stern John… came on for Kevin Kyle'; skybluearmy.blogspot.com 라인업 'Leon McKenzie (Stern John 68)'·Teamtalk 기사 '69th minute… triple substitution… Stern John') + 위키 코번트리 2006-07 리그 23경기(TM 22) → **22분(68분 투입)** 출전, 무득점. 교체 대상 선수는 출처마다 다름(무관).

## 4. 출전 분 (S10)
- TM API 그대로. 1998 오픈컵 결승(골든골 99분) 99분, 퇴장 2(2001.8.27 코번트리전 43분, 2008.5.4 셰필드 유나이티드전 80분). MLS 승부차기 15경기는 연장 없이 90분(1998·1999 MLS는 무승부 시 바로 승부차기).

## 5. 골 (S15)
- 155 = TM 154(PK 5: 1998.6.13 DC·2001.12.29 코번트리·2002.8.28 에버턴·2004.9.15 질링엄·2004.10.30 레딩) + 플레이오프 1. 자책골·PK 리바운드 없음. soccerbase 골 수가 매칭된 모든 경기에서 TM과 같음. 골 유형 108개 빈칸(문제 없음).
- 연장 골 없음. 1998 오픈컵 결승 53분 동점골(0-1 → 1-1, df).

## 6. 도움 (S14)
- TM 22 → 17 + 플레이오프 1 = **18**.
  - 뺌: PK 유도 3(2008.2.23 스컨소프 88' 비냘, 2008.3.8 블랙풀 31' 비냘, 2008.12.20 번리 52' 메이너드), 상대 자책골 2(2006.12.23 루턴 59' 브르코비치 'Header', 2008.4.12 찰턴 11' 랜돌프 'Shot on goal').
  - 넣음(2014.8 이전 TM 단독, 선례): 유형 빈칸 8(MLS 7: 1998.4.18 맥브라이드·7.3 마이소뉴브·8.22 A.윌리엄스·9.9 커닝햄·9.30 플레이오프 R.스미스, 1999.5.15 커닝햄·6.26 마이소뉴브; 2004.1.24 FA컵 윔블던 B.휴스), Cross 2(2006.9.9 카일, 2008.11.25 메이너드), Pass 7(2006.10.23 도일, 2007.2.10 코널리, 2007.3.3 요크, 2007.9.22 이디아케스 90+1, 2007.12.26 비아파라, 2008.12.28 메이너드, 2009.12.28 월터스).
  - 2014.8 이후 도움 없음 → 단일 출처 확인 대상 없음. FotMob 경력 도움 합계(콜럼버스 7*·입스위치 1)는 TM과 같은 수.
- 본인 PK 골의 본인 도움·상대 골 도움 칸: 없음(2004.9.15 존 PK는 스톤턴 PK 유도 — 존 도움 아님).

## 7. 대회·합산 (S11)
- 대회 코드: 프리미어리그·퍼스트 디비전/챔피언십·MLS = lg. FA컵·리그컵·US 오픈컵(TM 'MLSP') = dc(16강까지)/dk(8강·FA컵 6라운드)/dsf/df; 1998 오픈컵 결승 df, 준결승 dsf. FA컵 재경기('deciders') dc.
- MLS 플레이오프 1998·1999(TM POUS): 3판 2선승 → **경기마다 단판 ko 1, 합산 없음**(메시·손흥민·밤바 선례, docs '1라운드(3판 2선승)는 경기마다 단판'). 'Quarter-Finals' = 컨퍼런스 준결승 mlp, 'Semi-Finals'(1~3차전) = 컨퍼런스 결승 mlpsf. 1998.10.3 1-1 승부차기 경기는 단판 무승부.
- MLS 정규리그 승부차기 15경기(SO_GAMES): TM 최종 스코어에 승부차기가 들어 있음(예 1998.4.26 DC 4-3, 경기 1-1) → 이벤트 스코어만 쓰므로 기록 행 영향 없음, 결과는 무승부. **finals.js(최종 스코어) 수집 시 이 15경기는 승부차기 골을 빼야 함**(build `shootout_games` 목록).
- 두 경기 합산: 2000-01 리그컵 1라운드 달링턴(원정 다득점·연장 (1,1); 2차전 홈 9분 골 tie `[2,1,2,2,1,1]`), 2002 플레이오프 준결승(3절).

## 8. 상대 Elo (출처: 순위표 → 라벨 98, 기존 팀×시즌 73, 직접 라벨 2)
- 순위표(raw/ranks.txt, 영어 위키): MLS 1998·1999 전체 순위(Template season table, 12팀) → `MLS 1998 N위/12팀`; 퍼스트 디비전 1999-2004 `챔피언십 1999-00 N위/24팀 (Football League First Division)`, 2·3부 2004년 전 `잉글랜드 3부/4부 … (Football League Second/Third Division, 리그 수준 추정)`, 2004년 뒤 챔피언십/리그 투(킨·오언 형식). 프리미어리그 `프리미어리그 2002-03 N위`.
- 팀 이름: 1997~1999 미국 팀은 당시 이름(Dallas Burn·Kansas City Wizards·MetroStars·San Jose Clash·Chicago Fire·Rochester Raging Rhinos·Carolina Dynamo; TM은 지금 이름). 이 팀-시즌들은 기존 자료에 없음(MLS 기존 라벨은 2007년부터).
- 직접 라벨: 캐롤라이나 다이너모 1999 — USL D3 Pro League(미국 3부, 26팀 3개 디비전). 위키 1999 USL D3 Pro League 순위표: 애틀랜틱 디비전 3위/8팀(11승 1승부차기승 6패) — 세 디비전 합친 승·승부차기승 순 10위/26팀 → `미국 3부 1999 10위/26팀 (… 리그 수준 추정)` = 1118(미국 3부 기준점 + 순위).
- 감점 시즌: 2009-10 챔피언십(팰리스 −10)은 감점 전 순위(QPR 14·더비 15·코번트리 20, 승점 표 '감점 전' 행 순서). 2009-10 리그 원(사우샘프턴 −10, 하틀풀 −3)은 존의 골·도움 상대가 없어 무관 — 참고로 사우샘프턴 경기장 성적 83점(23승 14무)은 찰턴(84) 다음 5위라 공식 4~6위(찰턴 4·스윈던 5·허더즈필드 6)와 순위가 달라짐: 이 시즌 행이 생기면 penalty_seasons.json에 추가 검토(지금은 해당 행 없음). `elo/league_points_other.json`의 '잉글랜드 3부 2009-10' 표 note에 '감점 전' 표시가 없음 — 오케스트레이터 확인 요망.
- league_rank_apply 바뀌는 행 0, 네 도구 이동량 0(포르투갈 2부 2015-16 −3은 기존 자료, 존과 무관), elo_table 값이 여럿인 팀-시즌 0.
- **승점 표 map 추가 필요**(스크래치 복사본에 적용해 값 계산함, `mapneed.json`):
```
잉글랜드 4부 2000-01 | Darlington FC | Darlington | [0, 19]
잉글랜드 4부 2002-03 | Leyton Orient | Leyton Orient | [0, 17]
챔피언십 1999-00 | Crewe Alexandra | Crewe Alexandra | [0, 18]
챔피언십 1999-00 | Port Vale FC | Port Vale | [0, 22]
챔피언십 2000-01 | Stockport County | Stockport County | [0, 18]
챔피언십 2000-01 | Wimbledon FC | Wimbledon | [0, 7]
챔피언십 2001-02 | Portsmouth FC | Portsmouth | [0, 16]
챔피언십 2004-05 | Cardiff City | Cardiff City | [0, 15]
챔피언십 2004-05 | Crewe Alexandra | Crewe Alexandra | [0, 20]
챔피언십 2004-05 | Gillingham FC | Gillingham | [0, 21]
챔피언십 2004-05 | Ipswich Town | Ipswich Town | [0, 2]
챔피언십 2004-05 | Rotherham United | Rotherham United | [0, 23]
챔피언십 2005-06 | Derby County | Derby County | [0, 19]
챔피언십 2005-06 | Hull City | Hull City | [0, 17]
챔피언십 2005-06 | Preston North End | Preston North End | [0, 3]
챔피언십 2006-07 | Colchester United | Colchester United | [0, 9]
챔피언십 2006-07 | Plymouth Argyle | Plymouth Argyle | [0, 10]
챔피언십 2007-08 | Bristol City | Bristol City | [0, 3]
챔피언십 2007-08 | Burnley FC | Burnley | [0, 12]
챔피언십 2007-08 | Colchester United | Colchester United | [0, 23]
챔피언십 2007-08 | Crystal Palace | Crystal Palace | [0, 4]
챔피언십 2007-08 | Ipswich Town | Ipswich Town | [0, 7]
챔피언십 2007-08 | Queens Park Rangers | Queens Park Rangers | [0, 13]
챔피언십 2007-08 | Sheffield United | Sheffield United | [0, 8]
챔피언십 2007-08 | West Bromwich Albion | West Bromwich Albion | [0, 0]
챔피언십 2008-09 | Crystal Palace | Crystal Palace | [0, 14]
챔피언십 2008-09 | Reading FC | Reading | [0, 3]
챔피언십 2009-10 | Coventry City | Coventry City | [0, 19]
챔피언십 2009-10 | Derby County | Derby County | [0, 14]
챔피언십 2009-10 | Queens Park Rangers | Queens Park Rangers | [0, 13]
```

## 9. 다른 선수 자료 대조
- 존과 같은 팀 동료로 계산기에 있는 선수 없음(같은 날짜·같은 상대 M 행 0). 다른 선수 자료의 존 도움·존이 도운 골 쌍 0(`cross_check` 빈 목록).
- 상대 팀×시즌 값은 기존 자료(예: 로비 킨·오언·큐얼 등 2000년대 잉글랜드 팀)를 그대로 씀(73행), 새 팀-시즌은 순위 라벨 → elo_table 충돌 0.
- 이번 회차 병렬(모라타·미트로비치·히메네스·엔네시리·이강인)과 겹치는 경기 없음(존 마지막 경기 2010.5).

## 10. 우승·수상 (TM 업적 + 영어 위키)
- o: 챔피언십(2부) 우승 06/07 선덜랜드(2007.2~5 리그 15경기 출전).
- a: TOP 1998 MLS 26골(TM 'Top goal scorer 97/98'·위키 MLS Golden Boot 목록), XI 1998 MLS · 사무국(위키 MLS Best XI 1998에 Stern John, Columbus), FOY 2002 트리니다드 토바고(TM 'Footballer of the Year 2002'·위키 TTFF Player of the Year).
- 제외: 승격 2회(2002 플레이오프·2007), 1998 US 오픈컵 준우승, MLS 올스타 1998·1999, 대표팀(캐리비언컵·월드컵·골드컵), 차코니아 훈장.

## 11. 통합 메모
- 클럽 키(접미사 stj, index.html 미사용 확인): nostj·colstj·nfostj·bcstj·covstj(두 시기)·derstj·sunstj·soustj·bristj·cpstj(두 시기)·ipsstj.
- seasonOf: nostj·colstj 달력 연도(add_players `calendar`), 나머지 8월 1일 기본. 수동 패치 없음.
- **새 국기 TT(트리니다드 토바고)**: flagBody·FLAG_NAME에 없음(confOf CONCACAF에는 있음) → integration.json `flag_new`의 case 문자열과 `"TT": "트리니다드 토바고"`를 수동 추가해야 함(add_players는 국기를 넣지 않음; 스크래치에서 `case "TG"` 앞에 `…`;`로 넣어 확인).
- 포지션 CF, 은퇴 true. 색은 integration.json colors(기존 클럽 색 재사용; 콜럼버스 노랑·검정(위키 유니폼 FFF200), 뉴올리언스 1997 빨강·흰색·파랑(위키 '빨강·흰색·파랑 유니폼')).
- final_scores 인자: `sternjohn:STJ:3793` (MLS 승부차기 15경기 최종 스코어 주의, TM에 없는 플레이오프 3경기·2006.9.23 팰리스전은 TM 스코어 없음).
