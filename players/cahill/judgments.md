# 팀 케이힐 (Tim Cahill) 판정 기록

프리셋 `cahill`, 접두어 `CAH`(src/data/cah.js·CAH_ 상수 미사용 확인), Transfermarkt 13556, FotMob 30876, 국기 AU(큐얼·비두카와 같음), 포지션 AM. 은퇴(TM 2019.4.1, 마지막 경기 2019.1.28).
final_scores 줄: `cahill:CAH:13556`.

결과: **698경기 172골(PK 5) 43도움, 55,629분**, 기록 215행(두 경기 합산 9행/8경기). SOC 251.08, 최고 3시즌 25.90, 최고 5시즌 23.87, SOC-CAR 175.32.
클럽별(경기·골·도움): 밀월 1997~2004 245·57·3, 에버턴 278·68·29, 뉴욕 레드불스 72·16·10, 상하이 선화 34·12·0, 항저우 뤼청 17·4·0, 멜버른 시티 31·13·1, 밀월 2018 10·0·0, 잠셰드푸르 11·2·0.

재현: `python3 players/cahill/build_cahill.py`(SOC_ROOT = 새로 만든 상대 Elo 통합표가 있는 루트. 이번 결과는 src/data 275명으로 `node tools/elo_table.js`를 다시 돌린 스크래치 루트로 만듦 — 저장소의 elo/ 표는 lv 문구 2곳(크리스털 팰리스 2002-03·2003-04 '(Football League First Division)')만 다르고 Elo는 같음).

## 스크래치 검증(v1.290, 앵커 `azmoun`)
- add_players.py → build.py → `verify.js check`: 기존 275명 수치 그대로, 팀 케이힐 '추가', 콘솔 오류 없음 → 통과.
- 스크래치 elo/league_points_other.json에 아래 map 66개를 더한 뒤 `league_rank_apply.py --apply`: 바뀌는 행 0(cah.js 그대로).
- league_era_normalize·league_world_normalize·league_second_tier·league_second_tier_x: 이동량 전부 +0.
- `node tools/elo_table.js`(선수 276명): 값이 여럿인 팀-시즌 0.
- §16 점검(중복·같은 날 두 경기·E 날짜가 M에 있음·스코어 순서·도움 득점자·출전 분 범위·상대/대회 일치): 문제 0.

## 1. 범위
- TM performance-game의 성인 클럽 경기 689개(유소년·2군 경기 없음) + 경기 단위 출처로 확인한 9경기(2절) = 698.
- 시드니 유나이티드 1997(NSW 슈퍼리그 = 전국 리그 NSL 아래 주 리그, 세미프로): 영어 위키백과 2경기 0골, TM·FotMob 자료 없음 → v1.159 프로 리그 규칙으로 제외(NOTE 기록).
- 대표팀(호주 A·U23)·친선 제외.

## 2. TM에 없는 경기(discrepancies.txt 10 A) — 크레스포·리켈메 선례: 경기 단위 출처가 확인한 것만
추가(EXTRA):
| 날짜 | 경기 | 분 | 근거 |
|---|---|---|---|
| 2000.5.13 | 2부 디비전 승격 PO 준결승 1차전 밀월 0-0 위건(홈) | 90 | Wigan Athletic Heritage 라인업 lineups/2213(선발, 교체 없음) |
| 2000.5.17 | 같은 2차전 위건 1-0 밀월(원정) | 90 | lineups/2214(선발, 교체 없음) |
| 2000.9.19 | 리그컵 2R 1차전 밀월 2-0 입스위치(홈) **79분 골(1-0→2-0)** | 90 추정 | en.wiki '2000–01 Ipswich Town F.C. season' 경기 상자(Ifill 36', Cahill 79', BBC 930886 링크), en.wiki 밀월 2000-01(득점 Ifill, Cahill), TWTD 경기 기사(이필 선제골 뒤 후반 막판 케이힐이 박스 밖에서 추가골). 11v11 결과는 금지 출처라 쓰지 않음 |
| 2000.9.26 | 같은 2차전 입스위치 5-0 밀월(연장) | 90 추정 | TWTD 경기 기사(케이힐 슈팅을 라이트가 막음 = 출전), 교체 자료 없음 |
| 2002.4.28 | 1부 디비전 승격 PO 준결승 1차전 버밍엄 1-1 밀월 | 90 | ESPN event 48339 라인업(선발, subbedOut false) |
| 2002.5.2 | 같은 2차전 밀월 0-1 버밍엄 | 90 | ESPN event 48383 라인업 |
| 2016.8.24 | FFA컵 16강 브리즈번 스트라이커스 1-2 멜버른 시티 | 26 | ESPN·FTBL 기사: 64분 카세레스 대신 투입 |
| 2016.9.21 | FFA컵 8강 멜버른 시티 4-1 WSW **45분 PK 골(2-0→3-0)** | 90 추정 | australiacup.com.au 경기 기사(선발 'first start together', 토포르스탠리 퇴장 뒤 PK), en.wiki 2016 FFA Cup(Cahill 45' pen.), FotMob 이벤트 45분 케이힐 |
| 2016.10.25 | FFA컵 준결승 멜버른 빅토리 0-2 멜버른 시티 | 69 | 구단 경기 기록(멜버른 시티 ?p=1233, 69분 레트레와 교체), 호주컵 'Road to final' 기사 |
- 플레이오프 준결승은 리그 비중(애슐리 영 2006 POCC 선례), 두 경기 [원정 다득점 0, 연장 1]. 골·도움 없음.
- 리그컵 2000-01 2R 합산 [1,1,0,0,1,1](원정 다득점·연장 — 리그컵 두 경기 규칙).
- 넣지 않음(출전 확인 못 함): 1999.3.16 트로피 남부 결승 2차전 월솔 원정(TM 명단 제외; 위키 1998-99 '기타' 4경기에 들어 있을 것), 1999.10.31 FA컵 1R 하틀풀(TM 명단 제외), 1999-2000 '기타' 3경기 중 1경기(PO 2경기 외), 2000-01 '기타' 1경기(트로피 노샘프턴·스윈던 중 미상), 2017 FFA컵 1경기(교체 0(1), 32강 페닌슐라 파워전으로 보이나 라인업 없음), 2016-17 A리그 위키 21 vs TM 20(FotMob 라인업도 20), 잠셰드푸르 위키 12 vs TM·FotMob 11.
- 위키백과 합계와의 차이: 밀월 249·56 vs 우리 245·57(위키 선수 표는 1998-99 월솔전 4분 골을 빼 6골로 적음 — 위키 대회 문서·TM은 골), 멜버른 시티 33·13 vs 31·13, 잠셰드푸르 12 vs 11.

## 3. 날짜
- TM date_local_tz_conv(경기장 시간대). 뉴욕 레드불스 저녁 경기 46개(MLS·북중미 챔스)는 현지 날짜(TM 일정·리포트보다 하루 앞, FotMob 변환과 일치).
- DATE_FIX 2510777(2014 MLS PO 동부 준결승 2차전 D.C. 원정): TM UTC 11.7 23:00 → **2014.11.8** (FotMob 날짜·앙리 자료와 같게).
- 밀월 1998~2004의 TM '시각 모름'(00:00 CET) 101경기는 TM 일정 날짜.
- 앙리·주니뉴 출전 행과 하루 어긋나는 날짜 없음(빌드 대조).

## 4. 대회 코드·합산
- 리그 lg: ENSD(2부 디비전 = 3부)·EFD2(1부 디비전 = 2부)·GB1·GB2·MLS1·CSL·AUS1·IND1 + 승격 PO(추가 경기).
- 국내컵: FA컵·리그컵·풋볼 리그 트로피(1군 경기, 왓킨스 선례)·중국 FA컵·FFA컵. 16강까지 dc, 8강(FA컵 6R·'Quarter-Finals'·재경기 포함) dk, 준결승 dsf, 결승 df. 트로피 1998-99 남부 지역 결승(TM 'Semi-Finals', 대회 전체 준결승) dsf, 1999 웸블리 결승 df. FA컵 재경기('deciders')는 단판.
- UEFA컵 1R(2005 디나모·2008 스탕다르) elq, UEFA컵 조별 2007 elg, 3R(32강)·16강 2008 elk, 챔스 3차 예선 2005 clq, 유로파 PO 2009 elq, 유로파 조별 elg, 32강 2010 elk. 북중미 챔스 조별 ccc.
- MLS 컵 PO(POUS): 녹아웃 라운드·콘퍼런스 준결승 mlp, 콘퍼런스 결승 mlpsf(앙리 자료와 같음). A리그 파이널 시리즈(2017 엘리미네이션 파이널) mlp 단판(델 피에로 선례).
- 합산 규칙(원정 다득점, 연장): UEFA (1,1), 리그컵 (1,1), 중국 FA컵 (1,1)(엘샤라위·파투·테베스 선례), MLS PO 2012·2013 (0,1)·2014 (1,1)(앙리 tie와 같음), 잉글랜드 PO (0,1), **풋볼 리그 트로피 1999 남부 결승 (1,1) — 규정 문서 못 찾음(추정, 1998-99 대회 문서에 원정골 언급 없음; 리그컵과 같게 둠)**. 해당 행: 1999.3.9 월솔전 4분 골 [1,1,0,0,1,1].
- 합산 행 9개: 월솔 1999, 입스위치 2000, 디나모 2005(2차전 [2,1,1,5]), 브란 2008([2,1,2,0]), 스포르팅 2010, 휴스턴 2013(골·도움 [1,0,0,0,0,1]), 뉴잉글랜드 2014([2,0,1,2,1,1]), 베이징 엔터프라이즈 2015(중국 FA컵 준결승 2차전 [2,0,3,2,1,1]).
- 연장 골 1개: 2007.10.31 리그컵 16강 루턴 101분(et 1). 승부차기 경기(2004 브리스톨 시티, 2009 FA컵 준결승 맨유, 2011 첼시, 2015 상하이 SIPG)에는 기록 없음.

## 5. 골(172 = TM 170 + 추가 2)
- TM 리포트 골 170 = API 170. 본인 자책골 없음. PK 5(TM 4: 상하이 선화 2·항저우 2 + FFA컵 8강 1).
- FotMob 대조(2010-11 이후 골 있는 53경기): 수·PK 모두 같음, 분 차이 1개(2010.11.6 블랙풀전 TM 11분·FotMob 13분 → TM). 2010.10.2 버밍엄 90+3·2013.10.5 뉴잉글랜드 90+7은 FotMob이 90분으로만 적음 → TM 추가시간.
- ESPN: 대조한 골 120개 모두 일치(README). 중국 FA컵 2015.10.21 베이징 엔터프라이즈 17분 골은 TM 단일(FotMob·ESPN 자료 없음) — 골은 TM 단일도 넣는 기존 방식대로 넣음.

## 6. 도움(43 = TM 56 − 13)
규칙으로 뺀 것 9: PK 유도 5(2005.10.23 첼시 비티, 2009.5.16 웨스트햄 사아, 2010.4.25 풀럼 아르테타, 2012.10.27 필라델피아 쿠퍼, 2018.12.4 케랄라 칼보 — TM 공식 도움 칸 0·FotMob 0), Shot on goal 3(2001.12.4 맨시티 새들리어, 2007.12.8 풀럼 야쿠부, 2009.3.14 스토크 레스콧), 상대 자책골 유도 1(2015.3.8 상하이 선신 임유환 자책골, TM 유형 Own-goal).
2014.8 전(TM 단일 허용): 나머지 TM 도움 모두 넣음(유형 빈칸·Pass·Cross·Header·Corner·Free kick). 참고:
- 2003.8.23 크루전 90분 득점자 TM 'Tony Warner'(밀월 골키퍼), ESPN 'Noel Whelan' → 워너의 막판 헤더 동점골이 기사로 확인돼 TM 유지(도움 케이힐 크로스).
- 2012.9.22 뉴잉글랜드전 90+1분 린드페레(TM Cross; ESPN은 상대 팀 켈린 로를 도움자로 적어 모순) → 2014 전 규칙대로 TM 유지.
2014.8 뒤(TM+FotMob 또는 다른 출처 2곳):
- 넣음: 2014.8.26 북중미 챔스 FAS전 11분 세네(TM 유형 빈칸, FotMob 도움자 없음) — ESPN 이벤트 'ast: Tim Cahill', SBI Soccer 기사('Cahill headed the ball into Sene's path'), FourFourTwo 북중미 챔스 정리(케이힐 도움). 2016.10.21 퍼스 글로리전 60분 브란단 — ESPN 이벤트(도움 케이힐), 멜버른 시티 구단 경기 기사(?p=1252: 'Cahill played the Argentine through on goal with a deft pass').
- 2014.6.27 토론토전 90+3 라이트필립스는 2014.8 전이고 FotMob도 도움.
- **확인 못 해 뺀 TM 단독 4개**: 2015.4.11 충칭 58분 차오윈딩(Pass), 2015.4.19 허난 82분 가오디(Header), 2015.10.21 중국 FA컵 베이징 엔터프라이즈 28분 뎀바 바(Header), 2015.10.31 장쑤 36분 뎀바 바(Header). FotMob 이벤트 도움자 없음(FA컵은 FotMob 경기 자료 없음), ESPN 경기 없음, 영어·중국어 검색으로 기사 못 찾음(fbref 결과는 금지 출처라 안 봄). 참고: FotMob 경력 표는 상하이 리그 도움 2(경기 특정 불가).
- FotMob 단독 1개 넣지 않음: 2011.9.17 위건전 33분 자기엘카(TM·ESPN 도움자 없음, 2014 전이지만 단일 출처).
- 밀월 1998~2001: TM이 도움자를 거의 적지 않아(그 시즌 골 90개 중 0개) 도움 과소 가능 — NOTE에 기록.

## 7. 상대 Elo
- 출처(215행): 기존 팀×시즌 값 114, 순위표 → 라벨 85, 같은 경기 다른 선수 자료 15(앙리·주니뉴), 직접 라벨 1(FAS). 모든 순위 라벨 행 값은 league_rank_apply와 같은 계산(승점·득실 모형 포함)으로 다시 계산 — 기존 값 행은 바뀐 것 없음.
- 순위: TM 순위표(raw/ranks.txt), 위키백과 표(4부 1998-99·1999-2000·2001-02, 5부 2003-04 텔퍼드 12/22, 중국 2부 2015 베이징 엔터프라이즈 4/16, ISL 2018-19), 저장소 승점 표 사본(MLS 2012~2014 전체 순위 — TM 2014 표는 콘퍼런스 표라 안 씀, A리그 2016-17, 중국 2015·2016). 승점 표가 있는 리그·시즌은 라벨 순위 행의 팀 이름이 표와 맞는지 자동 대조(66개 모두 통과).
- **순위 고침**: 그리스 2007-08 AE 라리사 TM 5위 → **6위**(파니오니오스와 45점 동률, 위키백과 표·저장소 승점 표 파니오니오스 5위). 2007.10.25 UEFA컵 조별 라리사전 골.
- 시즌 판단: 2008.2.21 UEFA컵 브란 → 노르웨이 2008 개막(4월) 전이라 **2007 시즌 1위/14팀**(기존 표에는 브란 2008 '8위·2007 우승 팀(추정)' 행이 따로 있음 — 다른 시즌 키라 충돌 없음). 2007.12.5 제니트 → 러시아 2007 1위. 2014.8.26 FAS → 엘살바도르 아페르투라 2014(경기 날짜에 진행 중) 최종 3/10(FotMob 표 '2014/2015 - Apertura'의 'Apertura' 표; 라벨 시즌 2014-15, 리그 수준 추정). 위키 표는 요청 제한으로 못 받아 FotMob 단일.
- 감점 시즌: 2007.10.31 루턴(3부 2007-08)은 기존 값의 '감점 전 순위' 라벨(23위). 그 밖에 penalty_seasons 해당 없음(자동 확인).
- 리그 수준 추정: 잉글랜드 3·4·5부, 중국 2부, 엘살바도르. 인도 슈퍼리그 2018-19는 승점 표 없음 → 순위 곡선(케랄라 9위 1026·델리 8위 1046).

### 승점 표 map 추가 필요 (`<라벨 앞부분> | 데이터 상대 이름 | 표 팀 이름 | [표, 행]`)
스크래치에서는 이 66개를 elo/league_points_other.json에 넣고 검증함(넣지 않으면 rank_apply가 이 행들을 순위 곡선 값으로 되돌림).
- 잉글랜드 3부 1998-99 | Wycombe Wanderers | Wycombe Wanderers | [0, 18]
- 잉글랜드 3부 1998-99 | Gillingham FC | Gillingham | [0, 3]
- 잉글랜드 3부 1998-99 | Stoke City | Stoke City | [0, 7]
- 잉글랜드 3부 1998-99 | Walsall FC | Walsall | [0, 1]
- 잉글랜드 3부 1998-99 | Oldham Athletic | Oldham Athletic | [0, 19]
- 잉글랜드 3부 1999-00 | Wigan Athletic | Wigan Athletic | [0, 3]
- 잉글랜드 3부 1999-00 | Chesterfield FC | Chesterfield | [0, 23]
- 잉글랜드 3부 1999-00 | Cambridge United | Cambridge United | [0, 18]
- 잉글랜드 3부 1999-00 | Oxford United | Oxford United | [0, 19]
- 잉글랜드 3부 1999-00 | Burnley FC | Burnley | [0, 1]
- 잉글랜드 3부 1999-00 | Luton Town | Luton Town | [0, 12]
- 잉글랜드 3부 1999-00 | Bristol City | Bristol City | [0, 8]
- 잉글랜드 3부 1999-00 | Scunthorpe United | Scunthorpe United | [0, 22]
- 잉글랜드 3부 2000-01 | Reading FC | Reading | [0, 2]
- 잉글랜드 3부 2000-01 | Peterborough United | Peterborough United | [0, 11]
- 잉글랜드 3부 2000-01 | Oldham Athletic | Oldham Athletic | [0, 14]
- 잉글랜드 3부 2000-01 | Bristol Rovers | Bristol Rovers | [0, 20]
- 잉글랜드 3부 2000-01 | Brentford FC | Brentford | [0, 13]
- 잉글랜드 3부 2000-01 | Stoke City | Stoke City | [0, 4]
- 잉글랜드 3부 2000-01 | Wrexham AFC | Wrexham | [0, 9]
- 챔피언십 2001-02 | Wimbledon FC | Wimbledon | [1, 8]
- 챔피언십 2001-02 | Nottingham Forest | Nottingham Forest | [1, 15]
- 챔피언십 2001-02 | Rotherham United | Rotherham United | [1, 20]
- 챔피언십 2001-02 | Crewe Alexandra | Crewe Alexandra | [1, 21]
- 챔피언십 2001-02 | West Bromwich Albion | West Bromwich Albion | [1, 1]
- 챔피언십 2002-03 | Nottingham Forest | Nottingham Forest | [1, 5]
- 챔피언십 2002-03 | Coventry City | Coventry City | [1, 19]
- 챔피언십 2003-04 | Wigan Athletic | Wigan Athletic | [0, 6]
- 챔피언십 2003-04 | Crewe Alexandra | Crewe Alexandra | [0, 17]
- 챔피언십 2003-04 | West Ham United | West Ham United | [0, 3]
- 챔피언십 2003-04 | Bradford City | Bradford City | [0, 22]
- 챔피언십 2003-04 | Cardiff City | Cardiff City | [0, 12]
- 챔피언십 2003-04 | Walsall FC | Walsall | [0, 21]
- 챔피언십 2003-04 | Preston North End | Preston North End | [0, 14]
- 챔피언십 2003-04 | Rotherham United | Rotherham United | [0, 16]
- 잉글랜드 3부 2003-04 | Tranmere Rovers | Tranmere Rovers | [0, 7]
- 챔피언십 2003-04 | Wimbledon FC | Wimbledon | [0, 23]
- 챔피언십 2003-04 | Sunderland AFC | Sunderland | [0, 2]
- 챔피언십 2004-05 | Plymouth Argyle | Plymouth Argyle | [1, 16]
- 잉글랜드 4부 2006-07 | Peterborough United | Peterborough United | [0, 9]
- 그리스 1부 2007-08 | AE Larisa | AEL | [2, 5]
- 러시아 1부 2007 | Zenit St. Petersburg | Zenit St. Petersburg | [0, 0]
- 노르웨이 1부 2007 | SK Brann | Brann | [0, 0]
- 잉글랜드 3부 2009-10 | Carlisle United | Carlisle United | [0, 13]
- MLS 2013 | Seattle Sounders FC | Seattle Sounders FC | [0, 5]
- MLS 2014 | Toronto FC | Toronto FC | [0, 12]
- MLS 2014 | Seattle Sounders FC | Seattle Sounders FC | [0, 0]
- 중국 슈퍼리그 2015 | Hangzhou Greentown | Hangzhou Greentown | [1, 10]
- 중국 슈퍼리그 2015 | Liaoning FC | Liaoning Whowin | [1, 11]
- 중국 슈퍼리그 2015 | Jiangsu Guoxin Sainty | Jiangsu Guoxin-Sainty | [1, 8]
- 중국 슈퍼리그 2015 | Guangzhou R&F | Guangzhou R&F | [1, 13]
- 중국 슈퍼리그 2015 | Tianjin Teda | Tianjin TEDA | [1, 12]
- 중국 슈퍼리그 2015 | Beijing Guoan | Beijing Guoan | [1, 3]
- 중국 슈퍼리그 2015 | Henan Jianye | Henan Jianye | [1, 4]
- 중국 슈퍼리그 2015 | Guizhou Renhe | Guizhou Renhe | [1, 14]
- 중국 슈퍼리그 2015 | Changchun Yatai | Changchun Yatai | [1, 9]
- 중국 슈퍼리그 2016 | Changchun Yatai | Changchun Yatai | [0, 11]
- 중국 슈퍼리그 2016 | Guangzhou Evergrande Taobao | Guangzhou Evergrande Taobao | [0, 0]
- 중국 슈퍼리그 2016 | Jiangsu Suning | Jiangsu Suning | [0, 1]
- 중국 슈퍼리그 2016 | Yanbian Funde | Yanbian Funde | [0, 8]
- 호주 A리그 2016-17 | Melbourne Victory | Melbourne Victory | [0, 1]
- 호주 A리그 2016-17 | Perth Glory | Perth Glory | [0, 4]
- 호주 A리그 2016-17 | Sydney FC | Sydney FC | [0, 0]
- 호주 A리그 2016-17 | Central Coast Mariners | Central Coast Mariners | [0, 7]
- 호주 A리그 2016-17 | Newcastle United Jets | Newcastle Jets | [0, 9]
- 호주 A리그 2016-17 | Adelaide United | Adelaide United | [0, 8]

## 8. 시즌·클럽
- 클럽 키(소문자, index.html 미사용 확인): milct(밀월 두 시기 같은 키), evect, nyct, shsct, hzct, mcct, jmct. until = TM 이적일(2004-07-23, 2012-07-26, 2015-02-03, 2016-02-21, 2016-08-11, 2018-01-29, 2018-08-31). 모든 경기가 클럽 경계와 맞음(빌드 검사).
- seasonOf: 달력 연도 nyct·shsct·hzct(integration.json 'calendar'), 나머지 8월 1일 기준(수동 index.html 패치 필요 없음). 밀월 1997-98은 1경기(1998.5.2)뿐.
- 색(integration.json colors): 밀월·에버턴·뉴욕·상하이·멜버른 시티는 기존 clubcolors.js 값 재사용(mil·evw·nyh·shs·melvl). 항저우 뤼청(#00843D 녹색·흰색)·잠셰드푸르(#E31E24 빨강·흰색)는 위키백과 원문을 요청 제한으로 못 받아 구단 대표색으로 넣음 — 확인 필요하면 바꿔도 됨.

## 9. 같은 경기·동료 대조
- 앙리(hen.js): 앙리 도움 케이힐 골 6개(2013.4.27 토론토 89·7.13 몬트리올 63·7.27 RSL 11·8.25 치바스 31·11.3 휴스턴 22, 2014.11.29 뉴잉글랜드 26)와 케이힐 도움 앙리 골 2개(2013.5.26 콜럼버스 31·2014.7.30 RSL 57) 모두 날짜·분·스코어·대회·Elo·lv·tie 같음.
- 주니뉴(jun.js): 2013.5.19 LA 갤럭시 90+1분 케이힐 골 도움 같음.
- 이번 회차 다른 4명(오카자키·미나미노·혼다·소보슬러이)과 같은 경기 없음(출전 날짜·상대 대조).
- 같은 경기 Elo/lv/대회 다름: 없음.

## 10. 우승·수상(integration.json hon)
- t.DC: 2016 멜버른 시티(FFA컵). o: 잉글랜드 3부 우승 00/01 밀월(델 피에로 '세리에B 우승'·'독일 2부 우승' 형식), 서포터스 실드 12/13 뉴욕 레드불스(앙리와 같은 표기).
- a.FOY: 2004 오세아니아(TM, 큐얼·비두카 형식). a.XI: 2013 MLS · 사무국(en.wiki 'MLS Best XI' 2013 명단 확인).
- 뺀 것: PFA 올해의 팀 2000-01 2부 디비전·2003-04 1부 디비전(PFA 목록에서 확인했으나 수상 규칙 'PFA는 1부만'), PFA 호주 올해의 선수 2008-09(분류 없음), 구단 상, 준우승(1999 트로피, 2004·2009 FA컵, 2015 중국 FA컵), 대표팀(2015 아시안컵·2004 OFC 네이션스컵), 발롱도르 후보.

## 11. 불확실·확인 요청
1. 추가 9경기 중 3경기 출전 분 90분 추정(입스위치 2경기·FFA컵 8강), 입스위치 79분 골은 위키백과 경기 상자 분(BBC 원문은 못 열어 봄; TWTD 기사 순서와 일치).
2. 트로피 1999 남부 결승 합산 규칙 추정(원정 다득점·연장).
3. 중국 2015 TM 단독 도움 4개 제외, 위건 2011 FotMob 단독 도움 제외.
4. FAS 2014 순위(FotMob 단일, 아페르투라 2014 3위).
5. 항저우·잠셰드푸르 클럽 색.
