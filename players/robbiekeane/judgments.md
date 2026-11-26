# 로비 킨 (Robbie Keane) 판정 기록

- Transfermarkt 3144, FotMob 24635, soccerbase 11957. 프리셋 `robbiekeane`, 접두어 `RKN` (rkn.js; src/data에 같은 파일·상수 없음 확인).
- 스크래치 검증: add_players(slimani 앵커) → build → verify check **통과(기존 311명 수치 동일, 로비 킨 추가, 콘솔 오류 없음)**; league_rank_apply 바뀌는 행 0, 네 리그 도구 이동량 0(포르투갈 2부 2015-16 −3은 기존 자료, 킨과 무관), elo_table 값이 여럿인 팀-시즌 0.
- 수치: SOC 427.79, 3-peak 35.05, 5-peak 32.87, SOC-CAR 281.8.
- 결과: **738경기 325골(PK 40) 95도움, 54,924분**, 기록 행 420, 두 경기 합산 35행(25경기). 은퇴(2018.11.28 발표), 마지막 경기 2018.4.3 인도 슈퍼컵 16강 FC 고아 원정.
- 빌드: `SOC_ROOT=<스크래치 복사본> python3 players/robbiekeane/build_robbiekeane.py [--out …/src/data]` (`--stat`·`--ties`·`--debug`·`--mapneed`). 라벨 직접 지정은 `man_robbiekeane.py`, 설명은 `note_robbiekeane.py`.

## 1. 범위
- 1군 공식 경기 738(TM API = TM 경기 JSON, 영어 위키백과 737 — 차이는 아래 3절 헬싱보리). 클럽: 울버햄프턴 87·코번트리 34·인테르 15·리즈 56·토트넘 306(네 시기, 한 키 totrbk)·리버풀 28·셀틱 19·웨스트햄 10·LA 갤럭시 165(두 시기, 한 키 lagrbk)·애스턴 빌라 7·ATK 11.
- 제외: 웨스트햄 U21 프리미어 리저브 리그 2011.3.15 뉴캐슬 U21전(67분 1골, S15). 친선·대표팀·MLS 올스타전은 TM 목록에서 이미 빠짐.
- 프로 리그 규칙: 모든 시즌 프로 1·2부(퍼스트 디비전 1997~99 = 잉글랜드 2부 프로) — 뺄 시즌 없음.

## 2. 날짜·출전 분 (S8, S9, AUTO E/G/H)
- 날짜를 정하지 않은 옛 경기(TM UTC 22:00/23:00)가 soccerbase와 하루 차이(S9) → 기사로 확인해 고침(`DATE_FIX`):
  - 1998.8.18 리그컵 1라운드 2차전 울버햄프턴 5-0 바넷 (TM 8.19; soccerbase·영어 위키백과 1998–99 Wolves 시즌·wolvescompletehistory 8.18)
  - 2005.4.25 아스널 1-0 토트넘(월요일; spursodyssey·thfcdb·statmuse) — TM 4.23
  - 2006.4.30 토트넘 1-0 볼턴(일요일; thfcdb·RTÉ·spursodyssey) — TM 4.29
  - 2007.1.14 토트넘 2-3 뉴캐슬(일요일; nufc.com·thfcdb·spursodyssey·RTÉ) — TM 1.13
  - 2007.2.4 토트넘 0-4 맨유(soccerbase; 베르바토프·레넌·긱스 자료도 2.4) — TM 2.3
- 갤럭시 날짜는 LA 현지(수집기 변환), ATK는 인도 시각. soccerbase 2016 MLS 날짜는 영국 날짜라 하루 늦음(무시).
- 출전 분: TM API 그대로, 예외 1개 — 2013.11.7 MLS 플레이오프 RSL 원정(0-2 연장, n.V.) TM 90분이나 TM 경기 JSON 교체 없음·FotMob 선발·교체 없음 → **120분**(`MIN_FIX`).
- 퇴장: 2007.2.25 볼턴 36분, 2007.12.2 버밍엄 68분(TM API), 2012.8.23 CCL 메타판 70분(경고 누적 — LA 갤럭시·MLSsoccer 기사 "Keane sent off in the 70th minute"; FotMob 라인업에 킨 없음은 FotMob 누락).
- 2013.7.13 포틀랜드 원정: TM 79분 vs FotMob 85분 교체 → TM(다른 독립 출처 없음; worldfootball 79분은 금지 출처라 근거로 쓰지 않음).
- CCL 9경기 FotMob 라인업 누락(S10)은 TM 출전 그대로.

## 3. 경기·대회
- 인테르 2000-01 챔스 예선 3라운드 헬싱보리 1·2차전(TM 둘 다 출전, 위키 각주 '챔스 1경기') → TM 따름(두 경기 모두 TM 라인업에 킨, S1).
- 대회 코드: 퍼스트 디비전·PL·세리에A·SPL·MLS·ISL = lg. FA컵·리그컵·스코티시컵·코파 이탈리아·US 오픈컵(TM 'MLSP')·인도 슈퍼컵 = dc/dk(8강·FA컵 6라운드)/dsf/df. 수페르코파 2000 = df. UEFA컵 1라운드 elq, 2·3라운드·16강·8강 elk(비두카·세도르프·큐얼 선례), 조별 elg. 챔스 예선 clq, 조별 clg. MLS 플레이오프 mlp(와일드카드·컨퍼런스 준결승)·mlpsf(컨퍼런스 결승)·mlpf(MLS컵). CCL 조별 ccc·8강 ccck·준결승 cccsf.
- 합산 규칙: 리그컵(1·2라운드 두 경기·준결승)·UEFA컵·챔스 예선·코파 이탈리아 (원정 다득점 1, 연장 1); CCL (1, 0); MLS 플레이오프 두 경기 2011~2013 (0, 1), 2014~ (1, 1) — 앙리·베컴·케이힐 자료와 같음.
- 인도 슈퍼컵 2018: 예선(첸나이 시티)·16강(FC 고아) 모두 dc(16강까지). 과제 메모의 '8강'은 TM 'Round of 16'.

## 4. 골·도움
- 골 325 = TM 전부(PK 40). 2009.10.27 리그컵 에버턴 57분 'Penalty rebound'(actionId 205) = 일반 골(TM API penGoals도 40으로 일치). 자책골 없음.
- FotMob 대조(2010-11~): 81경기 114골 수·PK 일치, 분 차이 12건은 TM(1분 차·추가시간 표기); 2011.8.20 갤럭시 데뷔골 TM 28분 vs FotMob 21분 → TM(베컴 자료 도움 행도 28분).
- TM 도움 103(API) → 95:
  - 뺌: PK 유도 4(1998.8.22 스윈던 컬 29', 1999.2.13 포트 베일 컬 90', 2002.9.15 웨스트햄 셰링엄 71', 2008.1.5 FA컵 레딩 베르바토프 50' — 베르바토프 자료에 해당 골 있음), Shot on goal 3(2006.1.8 FA컵 레스터 지나스 20', 2007.11.11 위건 지나스 13', 2009.3.15 빌라 벤트 50'), 2018.3.16 슈퍼컵 첸나이 시티 제키냐 58'(2014.8 이후 TM 단독 — sportskeeda 경기 기사: 킨 컷백 → 음바타가 내줌 → 제키냐, 마지막 패스 음바타).
  - 본인 PK 골의 본인 도움 5(S5): 셈하지 않음(API도 0).
  - 2007.2.25 볼턴 스피드 PK 'Handball (opponent)'(S6): 상대 골, 도움 아님.
  - 넣음(2014.8 이후 TM 단독 확인): 2015.8.18 CCL 코무니카시오네스 54' 고든 — LA 갤럭시 공식 경기 보고서 "Alan Gordon (Assisted by Robbie Keane) 54'" + MLSsoccer.com/LAG Confidential 경기 기사(킨이 고든에게 연결).
  - 2014.8 이전 TM 단독(유형 Pass/Cross/Corner/Header/빈칸) 73개 선례대로 넣음(빈칸 17개 포함). TM+FotMob 일치 20개(갤럭시 2014~16·빌라).
  - FotMob 단독 3개(S3) 넣지 않음: 2010.8.17 영 보이스 83' 파블류첸코, 2010.10.20 인테르 90'·90+1' 베일 2골 — 두 번째 출처 없음, 베일 3번째 골은 Eurosport·TNT 기사상 레넌 패스(FotMob 오류).
- 연장: 2004.10.27 리그컵 볼턴 103' 디포 골 도움(et 1), 2014.12.7 MLS컵 결승 111' 골(et 1).

## 5. 상대 Elo (출처: 같은 경기 122, 기존 팀×시즌 200, 순위표→라벨 69, 직접 라벨 29)
- 순위표: 1997-98·1998-99 퍼스트 디비전·세컨드·서드 디비전(영어 위키백과, 라벨 `챔피언십 1998-99 N위/24팀 (Football League First Division)`·`잉글랜드 3부/4부 … (Football League Second/Third Division, 리그 수준 추정)` — 기존 오언·큐얼 형식), 챔피언십 2004-05(TM), 리그 투 2006-07(TM), SPL 2009-10(TM, 스플릿 뒤 최종), 키프로스 2007-08(TM, 아노르토시스 우승), MLS 2011~2013(TM 전체 표 = 기존 라벨 순위와 일치), 인도 슈퍼리그 2017-18(TM, 정규 리그; 1위 벵갈루루).
- 직접 라벨(`man_robbiekeane.py`):
  - MLS 2014 전체 순위(위키백과 Template:2014 Major League Soccer season table): 뉴욕 레드불스 8·밴쿠버 9·포틀랜드 11·치바스 USA 16 / 2015: 시애틀 6·스포팅 KC 10(기존 라벨 순위와 빈칸이 정확히 맞음).
  - 던펌린 2009-10 스코티시 퍼스트 디비전 3위/10(위키백과 2009–10 Scottish First Division) — `스코틀랜드 2부 … 리그 수준 추정`.
  - CCL: 모렐리아(2011.9.13) 아페르투라 2011 7위(TM MEXA 2011), 에레디아노(2013.3.13) 베라노 2013 정규리그 1위(FotMob 121), 카르타기네스(2013.8.20) 인비에르노 2013 4위(TM CRPD 2013), 티후아나(2014.3) 클라우수라 2014 7위(TM MEX1 2013 = 클라우수라 2014; 히메네스 자료 산토스 4위와 같은 표), 코무니카시오네스(2015.8.18) 아페르투라 2015 3위(TM GU1A 2015). 메타판 2012는 베컴 같은 경기 값.
  - PSA 엘리트(2015 US 오픈컵 4라운드, 아마추어) `미국 5부 2015 순위 없음` → 기준점 911.
  - 첸나이 시티 2017-18 I리그 8위/10: `인도 1부`로 표기(그 시즌 I리그는 ISL과 병행한 공동 1부, 우승 팀이 AFC 챔스 예선 출전권). '인도 2부'로 두면 751로 ISL 꼴찌(1001)보다 250 낮아져 1부로 봄 — 사용자 확인 필요.
  - 델리 다이너모스(TM 현재 이름 Odisha FC) 표시 이름은 당시 이름으로.
- 감점 시즌: 해당 상대 없음(onfield_rank 검사 통과).
- 승점 표 map 추가 필요(스크래치 복사본에 적용해 값 계산함, `mapneed.json`):
```
MLS 2011 | Houston Dynamo FC | Houston Dynamo | [0, 5]
MLS 2011 | Vancouver Whitecaps FC | Vancouver Whitecaps FC | [0, 17]
MLS 2012 | Seattle Sounders FC | Seattle Sounders FC | [0, 6]
MLS 2013 | FC Dallas | FC Dallas | [0, 14]
MLS 2013 | San Jose Earthquakes | San Jose Earthquakes | [0, 9]
MLS 2013 | Sporting Kansas City | Sporting Kansas City | [0, 1]
MLS 2014 | Portland Timbers | Portland Timbers | [0, 10]
MLS 2014 | Vancouver Whitecaps FC | Vancouver Whitecaps FC | [0, 8]
MLS 2014 | CD Chivas USA | Chivas USA | [0, 15]
MLS 2014 | Red Bull New York | New York Red Bulls | [0, 7]
MLS 2015 | Seattle Sounders FC | Seattle Sounders FC | [0, 5]
MLS 2015 | Sporting Kansas City | Sporting Kansas City | [0, 9]
스코틀랜드 1부 2009-10 | Aberdeen FC | Aberdeen | [0, 8]
스코틀랜드 1부 2009-10 | Dundee United FC | Dundee United | [0, 2]
스코틀랜드 1부 2009-10 | Falkirk FC | Falkirk | [0, 11]
스코틀랜드 1부 2009-10 | Hibernian FC | Hibernian | [0, 3]
스코틀랜드 1부 2009-10 | Kilmarnock FC | Kilmarnock | [0, 10]
스코틀랜드 1부 2009-10 | Motherwell FC | Motherwell | [0, 4]
스코틀랜드 1부 2009-10 | St. Johnstone FC | St Johnstone | [0, 7]
인도 슈퍼리그 2017-18 | Delhi Dynamos FC | Delhi Dynamos | [0, 7]
인도 슈퍼리그 2017-18 | FC Goa | Goa | [0, 2]
인도 슈퍼리그 2017-18 | NorthEast United FC | NorthEast United | [0, 9]
잉글랜드 3부 1998-99 | AFC Bournemouth | Bournemouth | [0, 6]
잉글랜드 4부 2006-07 | Milton Keynes Dons | Milton Keynes Dons | [0, 3]
챔피언십 1997-98 | Bury FC | Bury | [0, 16]
챔피언십 1997-98 | Crewe Alexandra | Crewe Alexandra | [0, 10]
챔피언십 1997-98 | Ipswich Town | Ipswich Town | [0, 4]
챔피언십 1997-98 | Norwich City | Norwich City | [0, 14]
챔피언십 1997-98 | Stockport County | Stockport County | [0, 7]
챔피언십 1998-99 | Birmingham City | Birmingham City | [0, 3]
챔피언십 1998-99 | Bolton Wanderers | Bolton Wanderers | [0, 5]
챔피언십 1998-99 | Huddersfield Town | Huddersfield Town | [0, 9]
챔피언십 1998-99 | Norwich City | Norwich City | [0, 8]
챔피언십 1998-99 | Oxford United | Oxford United | [0, 22]
챔피언십 1998-99 | Stockport County | Stockport County | [0, 15]
챔피언십 1998-99 | Sunderland AFC | Sunderland | [0, 0]
챔피언십 1998-99 | Tranmere Rovers | Tranmere Rovers | [0, 14]
챔피언십 1998-99 | Watford FC | Watford | [0, 4]
챔피언십 2004-05 | Brighton & Hove Albion | Brighton & Hove Albion | [0, 19]
챔피언십 2004-05 | Nottingham Forest | Nottingham Forest | [0, 22]
```

## 6. 다른 선수 자료 대조
- 같은 경기 출전(M 행 기준): 레넌 145, 베르바토프 83, 카누테 64, 제라드 55, 비두카 48, 큐얼 39, 베일 38, 베컴 35, 모드리치 35, 토레스 17, 세도르프 13, 그 밖(apl 7, vdv 7, vie 2, lav 1).
- 킨 골↔동료 도움, 킨 도움↔동료 골 쌍(베컴·베르바토프·제라드·큐얼·카누테·레넌·모드리치·세도르프·토레스·비두카·베일) 모두 날짜·분·스코어·대회·Elo·lv 일치(`robbiekeane.json` cross_check). 2008.1.5 FA컵 레딩전 베르바토프 PK 골은 킨 PK 유도라 도움에서 뺌. `--stat`의 '다름' 2건은 2분 이내 다른 골과 짝지어진 거짓 경보(2007.10.7 리버풀 45'·47' 두 골, 2000.9.28 루흐 87'·89').
- **다른 선수 파일 날짜 불일치(수정 안 함, 보고)**: 2007.1.14 토트넘–뉴캐슬을 베르바토프(brb.js)·레넌(len.js) 자료는 2007-01-13으로 적음(기사로는 1.14 일요일). 2005.4.25 아스널–토트넘을 파브레가스(fab.js) 자료는 2005-04-23으로 적음(실제 월요일 4.25).
- 이번 회차 병렬(아데바요르·산타크루스·세이두 케이타·제마): 킨은 2011.8 토트넘을 떠나 아데바요르(2011-12 토트넘)와 같은 팀 경기 없음. 다른 셋과 같은 경기 상대 검사 결과 없음.

## 7. 우승·수상 (TM 업적 + 영어 위키백과)
- t.LC 2008 토트넘(2008.2.24 결승 출전). o: MLS컵 2011·2012·2014, 서포터스 실드 2011(LA 갤럭시, 각 시즌 출전).
- a: MVP 2014, XI = MLS 베스트 11 2012~2015(사무국) + PFA 올해의 팀 1997-98 퍼스트 디비전(위키백과 PFA Team of the Year (1990s) 1997–98 First Division 표에 Robbie Keane, 울버햄프턴), FOY = FAI 올해의 선수 2009·2013(위키백과·TM 'Footballer of the Year').
- 제외: U-18 유럽 선수권 1998·네이션스컵 2011(대표팀), 신인상(FAI·TM 'Best young player'), 이달의 선수, 구단 올해의 선수, MLS컵 MVP·ESPY·올스타.

## 8. 통합 메모
- 클럽 키(접미사 rbk, index.html 미사용 확인): wolrbk·covrbk·intrbk·leerbk·totrbk·livrbk·celrbk·whurbk·lagrbk·avlrbk·atkrbk. 같은 클럽 반복은 같은 키(토트넘 4시기, 갤럭시 2시기).
- seasonOf: lagrbk 달력 연도(add_players `calendar`), 나머지 기본 8월 1일. 수동 패치 없음.
- 국기 IE(있음), 포지션 CF, 은퇴 true. 색은 integration.json colors(기존 클럽 색 재사용, ATK는 빨강·흰색).
- final_scores 인자: `robbiekeane:RKN:3144`.
