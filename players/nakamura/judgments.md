# 나카무라 슌스케 (Shunsuke Nakamura, TM 6069) — 판정 기록

결과: **769경기 133골(PK 14) 99도움, 58,303분**, 기록 232행(골 133·도움 99), 두 경기 합산 6행. 스크래치 검증본 pStats: **SOC 209.42(281명 중 176위), 최고 3/5시즌 18.76/16.85**, SOC-CAR 약 140.3.
클럽별(경기·골·도움·SOC, 클럽 탭): 요코하마 FM 408·82·43(112.79; 1기 171·37·0, 2기 237·45·43), 셀틱 166·33·32(53.71), 레지나 87·12·10(27.79), 이와타 52·5·11(11.14), 요코하마 FC 41·1·2(2.10), 에스파뇰 15·0·1(1.89).
재현: `SOC_ROOT=<스크래치 복사본> python3 players/nakamura/build_nakamura.py [--out <data 폴더>]` (→ nks.js, nakamura.json; NOTE는 note_nakamura.py). J리그 공식 기록: `jleague_parse.py`(스크래치의 jl/*.html → `jleague_official.json`), 목록 `jleague_marinos_list.json`.
접두어 NKS(src/data/nks.js·NKS_ 상수 없음 확인). final_scores 인자 **`nakamura:NKS:6069`**. 오카자키 build를 바탕으로 함.

## 1. 범위·경기
- TM 클럽 공식 경기 765(2군·유소년 없음) + 셀틱 스코틀랜드컵 4 = 769. 대표팀 제외. 모든 팀-시즌 프로 리그(J1·J2·세리에A·SPL·라리가).
- **J리그 공식 기록 대조(새 출처, 박지성 선례)**: data.j-league.or.jp SFMS01 목록(1997~2002) → 마리노스 경기 206개 SFMS02 공식 기록(선발·교체 시각·득점자·득점 시각) 판독. TM 1997~2002.7 경기 171개 전부 대조: 출전 여부·골 수 모두 같음, 공식 기록에만 있는 출전 0.
  - 출전 분 고침 4경기(V골 연장까지 풀타임인데 TM 90분): 1998.10.17 가시마 102(공식 3867), 2001.3.10 고베 93(5701), 2001.8.11 후쿠오카 115(5823), 2001.11.10 이와타 94(5917).
  - 날짜 고침 2경기(TM API·일정 모두 틀림, 리포트 없음): 2919268 1999-03-17 → **1999-03-27**(후쿠오카 원정, 공식 4541), 2919454 1999-09-22 → **1999-09-23**(히라쓰카 원정, 4711).
  - 골 순서 고침 1경기: 2919276 1999.4.3 시미즈 원정 3-2 — TM 리포트(이토 44·마쓰다 56·사와노보리 57·나카무라 59·마쓰다 66)가 공식 기록(조 16·이토 44·나카무라 50·사와노보리 57·조 82)과 다름 → 공식 기록: 나카무라 50분, 골 전 1-1(TM이면 1-2).
  - 그 밖의 모든 골 시각·순서 TM = 공식 기록.
- **추가 4경기(discrepancies 1·9절)**: TM '명단 외'/누락, ESPN API 경기 기록(roster starter/subbedOut, keyEvents)으로 출전 확인, 위키백과 시즌 출전 수와 맞음.
  - 2007.1.6 SFA 3R 덤바턴(H 4-0) 45분(ESPN 211981, 45' 리오던과 교체).
  - 2007.2.4 SFA 4R 리빙스턴(A 4-1) 90분(ESPN 212868 선발·교체 없음; 날짜는 ESPN·셀틱 위키 문서 2.4, TM API 2.3).
  - 2007.4.14 SFA 준결승 세인트존스턴(A 2-1) 78분(ESPN 215175).
  - 2008.1.12 SFA 4R 스털링 앨비언(H 3-0) 75분, **75분 골**(2-0에서): ESPN 232189(골·75' 교체), RSSSF scotcup08, RTÉ·Japan Times 경기 기사. TM 경기 목록에 아예 없음.
  - 리빙스턴전 59' 리오던 골 나카무라 스루패스: 아이리시 타임스 1곳 → 도움 넣지 않음(NOTE).
- **넣지 않음**: 마리노스 일왕배 1997(1)·1999(3, 1골)·2000(2)·2001(1) — TM 없음, J리그 공식 기록에 일왕배 없음, ja/en 위키 대회 문서에 출전·득점자 없음, 웹 검색으로 경기별 확인 못 함(크레스포·박지성 선례). 셀틱 2007-08 챔스 1골(en.wiki) — TM·ESPN에 없음(ja.wiki 챔스 0골).
- J1 승강 플레이오프 2018.12.8(TM 1분, 위키 없음): TM대로 넣음(리그).
- 위키 시즌별 합 775경기 135골 vs 우리 769·133: 일왕배 −7경기 −1골, 챔스 −1골, 승강 PO +1.
- 마리노스 2013 일왕배 결승 2014.1.1은 2013 시즌(TM과 같음).

## 2. 대회 코드·합산
- 리그 lg: JAP1·JL11·JL12(J1 스테이지)·JAP2·IT1·SC1·ES1 + ITPO(2003 세리에A 잔류 플레이오프 1차전, 고메스·카모라네시 선례)·J1PO(2018).
- 국내컵: JEMP·JAPC·CIT·SFA·SCP·CDR — 16강까지 dc, 8강(SFA 'Quarter-Finals Deciders' 재경기 포함) dk, 준결승 dsf, 결승 df. J리그컵 조별·코파 이탈리아 2002-03 조별 ko 0.
- JASP(제록스 슈퍼컵 2014) df. **SUNC(2000 J리그 챔피언십 결승 두 경기) mlpf**(리그 우승 결정전 = 리길야·MLS 플레이오프 선례 유추; 출전 행만, 골·도움 없음 — 사용자 확인 권장). AFCL 2014 조별 acl. CL 조별 clg·16강 cl16, CLQ clq.
- 합산 6행: J리그컵 2000.4.19 고후 2차전·2001.4.18 미토 2차전·2001.9.26 나고야 준결승 1차전·2011.7.27 고베 2차전·2013.6.23/6.30 가시마 8강 — 원정 다득점·연장(오카자키·미토마 선례). 다른 차전은 TM 리포트.
- **V골(골든골)**: J리그 1997~2002 리그 경기 연장 = 박지성 교토 선례대로 리그 경기(ko 0) + 연장 골만 et 1(122분 모형). 1997.9.24 세레소 106'(2-2), 2002.4.7 감바 116'(1-1). NOTE에 '골든골 규칙 반영 안 함'. 1997.4.19 베르디전 승부차기(리그)는 출전 행만.

## 3. 골 (TM 132 + 스털링 1 = 133, PK 14)
- TM 리포트 골 = API 골, 자책골 0. PK 14(TM penGoals). FotMob(2010.7~) 42골/41경기 수·순서·PK 같음(추가시간 표기만 다름 → TM 분).
- ESPN 미확인 5골(discrepancies 6절: 2002.9.22 인테르 90+2 PK, 2002.10.5 브레시아 82, 2003.4.6 엠폴리 54 PK, 2007.4.22 킬마녹 90, 2008.4.16 레인저스 25): ESPN 이벤트 누락(레인저스전 25' 골 등 잘 알려진 골), TM 유지.

## 4. 도움 (TM 121 → 99)
- 뺌 7: PK 유도 3(64841 2006.9.26 코펜하겐 밀러, 71849 2007.8.25 하츠 63' 헤셀링크, 921966 2008.9.21 킬마녹 사마라스), Shot on goal 3(66360 벤피카 56' 밀러·90' 피어슨, 1019892 2010.5.15 교토 효도), 상대 자책골 1(71849 2007.8.25 하츠 9' 베라 — TM 'Shot on goal'이자 상대 선수 득점).
- 본인 PK 골 본인 도움(2662389·2818929)은 처음부터 셈하지 않음(2818929의 다른 1도움 28' 오이는 TM+FotMob).
- 1997~2002: 모든 출처에 도움 자료 없음 → 0(확인된 0 아님, NOTE).
- 2014.8 전(레지나 10·셀틱 32·에스파뇰 1·마리노스 2010~14.7): TM 단일 출처 유지(선례). 유형 빈칸 1(2011.11.3 고후 오구로) 유지.
- 2014.8 이후 TM+FotMob 이벤트 일치 14개 유지(2015.8.22 도스 파비우, 2017~2022 이와타·요코하마 FC 13개).
- **2014.8 이후 TM 단독, 다른 출처 2곳 못 찾아 뺌 15개**: 2014.8.30 센다이 18' 구리하라·90+3' 시모히라, 2014.10.22 오미야 52' 사토·90+2' 후지타, 2015.8.29 우라와 64' 파비우(사커킹 기사: 왼쪽 CK, 키커 이름 없음), 2015.9.19 FC 도쿄 88' 도가시(J리그 공식 사진 설명 '中村が決勝ゴールを見事にアシスト' 1곳 — **두 번째 출처가 나오면 넣을 후보**), 2015.10.17 고베 86' 아데밀송, 2015.10.24 가와사키 39' 파비우, 2016.4.16 이와타 41' 사이토, 2016.5.8 고후 31' 나카마치, 2016.5.21 고베 23' 구리하라, 2016.5.29 가시와 45' 나카자와, 2016.7.17 히로시마 31' 파비우, 2016.9.22 일왕배 도쿄 베르디 26' 나카마치, 2017.4.8 마리노스 34' 오이(Goal.com 일본판: CK '흘러나온 공' → 루즈볼, TM 공식 도움 칸 0). FotMob 이벤트는 득점자만, FotMob 선수 경기 목록(이와타·요코하마 FC만)에 해당 경기 없음. 검색: WebSearch 요약(jleague.jp·사커킹·풋볼채널·게키사카), soccer-king·fctokyo.co.jp curl 원문 확인. football-lab 경기 리포트에는 도움 자료 없음.
- FotMob 전용 도움 0, 선수 경기 목록 전용 0.

## 5. 상대 Elo (232행: 기존 팀×시즌 값 64, 순위표→라벨 168; 값은 모두 라벨에서 league_rank_apply·승점 모형으로 계산)
- J1 1997~2002: **연간 종합 순위**(일본어 위키백과 'YYYY年のJリーグ(ディビジョン1)' 年間総合順位; 1·2위는 챔피언십 결과 — 1997 이와타·가시마, 1998 가시마·이와타, 1999 이와타·시미즈, 2000 가시마·마리노스, 2001 가시마·이와타, 2002 챔피언십 없음 이와타·마리노스). 라벨 `J1리그 YYYY 연간 N위/M팀`(박지성 pjs.js 2000·2002와 같은 형식·값). 영어 위키 1997은 연간표 없음, TM은 스테이지 표만.
- J1 2015·2016: 영어 위키 'Overall table'(연간 승점, 기존 가시마 2016 '연간 3위' 라벨과 같은 기준). J1 2010~2014·2017~2021: TM 표 = 영어 위키 표(전 팀 같음). J2: TM 표. JFL 2011(마쓰모토 야마가 4위/18): `일본 3부 … (Japan Football League, 리그 수준 추정)`(JFL은 2013년까지 3부).
- **SPL: TM 표는 스플릿 미반영(2005-06 4팀, 2006-07·2008-09 2팀 순위 다름) → 영어 위키 최종 순위표(스플릿 뒤)** 사용. 라벨 `스코틀랜드 1부 YYYY-YY N위/12팀 (Scottish Premier League, 플레이오프·스플릿 뒤 최종 순위)`. 기존 레인저스 2005-06·애버딘 2007-08 등은 통합표 값.
- 스털링 앨비언 2007-08 `스코틀랜드 2부 2007-08 10위/10팀 (Scottish First Division, 리그 수준 추정)`(TM·영어 위키 같음). 타란토 2002-03 통합표 값(이탈리아 3부 9위). 맨유 2006-07 2090(통합표).
- 감점 시즌(penalty_seasons.json) 해당 없음.
- 스크래치: `league_rank_apply.py` 바뀌는 행 0, 네 도구 이동량 0(JPN 1997~2020·스코틀랜드 2005-09·J2 +0), `elo_table.js` 값이 여럿인 팀-시즌 0.

### 승점 표 map 추가 필요 (`<label head> | 데이터 상대 이름 | 표 팀 이름 | 행 index`)
지금은 순위 곡선 값(map을 넣으면 이 행들만 승점 모형 값으로 바뀜). SPL 행 index는 위키 표(스플릿 뒤) 순서.
- J1리그 2000 연간 | Gamba Osaka | Gamba Osaka | 5
- J1리그 2000 연간 | JEF United Ichihara | JEF United Ichihara | 13
- J1리그 2000 연간 | Nagoya Grampus | Nagoya Grampus Eight | 8
- J1리그 2000 연간 | Verdy Kawasaki | Verdy Kawasaki | 9
- J1리그 2002 연간 | Gamba Osaka | Gamba Osaka | 2
- J1리그 2002 연간 | Nagoya Grampus | Nagoya Grampus Eight | 5
- J1리그 2002 연간 | Sanfrecce Hiroshima | Sanfrecce Hiroshima | 14
- J1리그 2002 연간 | Tokyo Verdy 1969 | Tokyo Verdy 1969 | 9
- J1리그 2010 | Albirex Niigata | Albirex Niigata | 8
- J1리그 2010 | Shimizu S-Pulse | Shimizu S-Pulse | 5
- J1리그 2011 | Cerezo Osaka | Cerezo Osaka | 11
- J1리그 2011 | Júbilo Iwata | Júbilo Iwata | 7
- J1리그 2011 | Kashima Antlers | Kashima Antlers | 5
- J1리그 2011 | Omiya Ardija | Omiya Ardija | 12
- J1리그 2011 | Sanfrecce Hiroshima | Sanfrecce Hiroshima | 6
- J1리그 2011 | Urawa Red Diamonds | Urawa Red Diamonds | 14
- J1리그 2011 | Vegalta Sendai | Vegalta Sendai | 3
- J1리그 2011 | Ventforet Kofu | Ventforet Kofu | 15
- J1리그 2011 | Vissel Kobe | Vissel Kobe | 8
- J1리그 2014 | Sagan Tosu | Sagan Tosu | 4
- J1리그 2014 | Tokushima Vortis | Tokushima Vortis | 17
- J1리그 2016 연간 | Avispa Fukuoka | Avispa Fukuoka | 17
- J1리그 2016 연간 | Gamba Osaka | Gamba Osaka | 3
- J1리그 2016 연간 | Sanfrecce Hiroshima | Sanfrecce Hiroshima | 5
- J1리그 2016 연간 | Vegalta Sendai | Vegalta Sendai | 11
- J1리그 2016 연간 | Vissel Kobe | Vissel Kobe | 6
- J1리그 2017 | Cerezo Osaka | Cerezo Osaka | 2
- J1리그 2017 | Gamba Osaka | Gamba Osaka | 9
- J1리그 2017 | Kawasaki Frontale | Kawasaki Frontale | 0
- J1리그 2017 | Sanfrecce Hiroshima | Sanfrecce Hiroshima | 14
- J1리그 2017 | Shimizu S-Pulse | Shimizu S-Pulse | 13
- J1리그 2018 | FC Tokyo | FC Tokyo | 5
- J1리그 2020 | Kawasaki Frontale | Kawasaki Frontale | 0
- J2리그 2019 | Tokyo Verdy | Tokyo Verdy | 12
- 스코틀랜드 1부 2005-06 | Dundee United FC | Dundee United | 8
- 스코틀랜드 1부 2005-06 | Dunfermline Athletic FC | Dunfermline Athletic | 10
- 스코틀랜드 1부 2005-06 | Falkirk FC | Falkirk | 9
- 스코틀랜드 1부 2005-06 | Heart of Midlothian FC | Heart of Midlothian | 1
- 스코틀랜드 1부 2005-06 | Hibernian FC | Hibernian | 3
- 스코틀랜드 1부 2005-06 | Inverness Caledonian Thistle FC | Inverness Caledonian Thistle | 6
- 스코틀랜드 1부 2005-06 | Kilmarnock FC | Kilmarnock | 4
- 스코틀랜드 1부 2005-06 | Livingston FC | Livingston | 11
- 스코틀랜드 1부 2005-06 | Motherwell FC | Motherwell | 7
- 스코틀랜드 1부 2006-07 | Aberdeen FC | Aberdeen | 2
- 스코틀랜드 1부 2006-07 | Dundee United FC | Dundee United | 8
- 스코틀랜드 1부 2006-07 | Dunfermline Athletic FC | Dunfermline Athletic | 11
- 스코틀랜드 1부 2006-07 | Heart of Midlothian FC | Heart of Midlothian | 3
- 스코틀랜드 1부 2006-07 | Kilmarnock FC | Kilmarnock | 4
- 스코틀랜드 1부 2006-07 | Motherwell FC | Motherwell | 9
- 스코틀랜드 1부 2006-07 | St. Mirren FC | St Mirren | 10
- 스코틀랜드 1부 2007-08 | Falkirk FC | Falkirk | 6
- 스코틀랜드 1부 2007-08 | Heart of Midlothian FC | Heart of Midlothian | 7
- 스코틀랜드 1부 2007-08 | Hibernian FC | Hibernian | 5
- 스코틀랜드 1부 2007-08 | Inverness Caledonian Thistle FC | Inverness Caledonian Thistle | 8
- 스코틀랜드 1부 2007-08 | Motherwell FC | Motherwell | 2
- 스코틀랜드 1부 2007-08 | St. Mirren FC | St Mirren | 9
- 스코틀랜드 1부 2008-09 | Aberdeen FC | Aberdeen | 3
- 스코틀랜드 1부 2008-09 | Dundee United FC | Dundee United | 4
- 스코틀랜드 1부 2008-09 | Falkirk FC | Falkirk | 9
- 스코틀랜드 1부 2008-09 | Hamilton Academical FC | Hamilton Academical | 8
- 스코틀랜드 1부 2008-09 | Hibernian FC | Hibernian | 5
- 스코틀랜드 1부 2008-09 | Inverness Caledonian Thistle FC | Inverness Caledonian Thistle | 11
- 스코틀랜드 1부 2008-09 | Kilmarnock FC | Kilmarnock | 7
- 스코틀랜드 1부 2008-09 | Rangers FC | Rangers | 0
- 스코틀랜드 1부 2008-09 | St. Mirren FC | St Mirren | 10
- 승점 표 없는 시즌(J1 1997·1998·1999·2001·2012·2013·2015 등, J2 2010~2012·2016·2022, JFL 2011, 스코틀랜드 2부 2007-08)은 순위 곡선.

## 6. 동료·공유 경기
- src/data 팀 동료: 에스파뇰 2009-10 칼레혼(cal.js) 같은 경기 14개 — 출전 행 대회 코드 같음, 서로 골·도움 연결 없음. 불일치 0.
- 이번 회차: 스콜스(맨유) 2006.9.13·2006.11.21 챔스 조별(나카무라 골 2개; 우리 상대 맨유 2006-07 2090, 스콜스 쪽 셀틱 1597 — 서로 다른 팀-시즌, 대회 clg 같음), 야야 투레(바르사) 2008.2.20·3.4 챔스 16강(출전 행만, cl16 같음), 가마다(도스) 2015.8.22·2016.3.19·2017.4.16(나카무라 2015.8.22 파비우 도움·2017.4.16 아다일톤 도움; 가마다 파일 쪽 상대는 마리노스·이와타라 값 충돌 없음).
- **라벨 표기 차이(값 같음)**: 가마다 kmd.js는 J1 2015·2016 연간 라벨 끝에 '(1·2스테이지 합산 연간 순위표)'를 붙임(감바 2015·2016, 후쿠오카·센다이·고베 2016). 우리와 기존 가시마 2016은 괄호 없음 — 오케스트레이터가 한쪽으로 맞출 것.
- 이재성과 같은 날 경기만 있고 같은 경기 없음.

## 7. 시즌·클럽 (수동 패치 필요)
- 클럽 키(index.html에 없음 확인): yfmnk(마리노스 두 시기 한 키, 임모빌레 선례)·regnk·celnk·espnk·jubnk·yfcnk. 경계 2002-08-01 / 2005-07-29 / 2009-07-01 / 2010-03-01 / 2017-01-10 / 2019-07-25.
- season: calendar [yfmnk, jubnk, yfcnk], jul10 [celnk](2006.7.29 SPL 개막이 2006-07).
- **index.html seasonOf 수동 패치 필요**: `if(club==="yfmnk")return String(m===1?y-1:y);` — 2014.1.1 일왕배 결승을 2013으로(오카자키 shiok 바로 뒤에 넣어 스크래치에서 검증). 넣지 않으면 '2014' 시즌에 1경기가 붙음.
- 국기 JP 있음, 포지션 AM, 은퇴(retired true).

## 8. 우승·수상 (TM 업적 + 위키 명단)
- LG 05/06·06/07·07/08 셀틱; DC 06/07 셀틱·2013 요코하마 FM(결승 2014.1.1); LC 05/06·08/09 셀틱·2001 요코하마 FM. 준우승(2000 챔피언십 등) 없음.
- POY: 2000·2013 J리그 · 사무국(J.League MVP; 영어 위키 'J.League Player of the Year' 목록), 06/07 스코틀랜드 1부 · PFA 스코틀랜드(선수협회)(PFA Scotland Players' Player of the Year 목록 2006–07; TM 'League Player of the Year 2007').
- XI: 1999·2000·2013 J리그 · 사무국(영어 위키 J.League Best XI), 06/07·07/08 스코틀랜드 1부 · PFA 스코틀랜드(선수협회)(PFA Scotland Team of the Year 목록 Premier League 2006–07·2007–08).
- FOY: 2000·2013 요코하마 FM(TM 'Footballer of the Year' 2회, 미토마 선례). **J리그 MVP와 같은 해라 중복일 수 있음 — 확인 권장**(TM은 MVP·Player of the Year와 별도 항목으로 적음).
- 뺌: SFWA 올해의 선수 2006-07(EPOY 범위 밖), 아시안컵 2000·2004 등 대표팀, 'Player of the Tournament 03/04'(대표팀).
- 'PFA 스코틀랜드(선수협회)'는 새 표기 — 오케스트레이터가 표기 확인.
- 색: yfmnk [#004098,#FFFFFF,#E50012](트리코롤), jubnk [#6CACE4,#FFFFFF](사크스 블루), yfcnk [#00A0E9,#FFFFFF]; celnk·espnk·regnk는 기존 cellj·espca·regmz 값.

## 9. 검증(스크래치)
- add_players.py szoboszlai + seasonOf 패치 → build.py → verify check: **기존 280명 동일, 나카무라 추가, 콘솔 오류 없음, 통과**.
- §16 점검 문제 0(중복·스코어 순서·출전 분 범위·E 날짜 M에 있음·도움 득점자).
- 기록별 SOC 상위 10: 2006.11.21 맨유 81' 6.34, 2006.9.13 맨유 43' 3.30, 2002.4.7 감바 116' V골 2.93, 2003.9.21 브레시아 73' 2.90, 2002.3.9 나고야 89' 2.78, 2007.4.22 킬마녹 90' 2.64, 2005.12.26 리빙스턴 87' 2.31, 2008.2.24 세인트미렌 87' 2.17, 1997.9.24 세레소 106' V골 2.08, 2002.9.22 인테르 90+2' PK 2.04.
- 최고 시즌: 2006-07 셀틱 23.02, 2013 마리노스 18.07, 2012 마리노스 15.20, 2002-03 레지나 14.86, 2010 마리노스 13.11.
