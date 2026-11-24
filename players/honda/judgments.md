# 혼다 게이스케 (Keisuke Honda) — 판정 기록

- Transfermarkt 선수 id **66521**, 프리셋 `honda`, 접두어 `HND`(src/data/hnd.js 없음·`HND_` 상수 없음 확인; hon.js는 수상 파일이라 다름), 국기 JP(있음), 포지션 AM.
- final_scores 줄: `honda:HND:66521`
- 결과(스크래치 복사본 check 통과, 기존 275명 동일·혼다 추가·콘솔 오류 없음): **511경기 107골(PK 9) 73도움 38,401분, SOC 147.54, 최고 3시즌 15.77·5시즌 14.94, SOC-CAR 약 104.48**.
- 현역(FC 주롱). 자료 기준 2026-11-24, 마지막 경기 2026-11-20 발레스티어 칼사전(교체 1분).

## 1. 경기 범위
| 항목 | 판정 | 근거 |
|---|---|---|
| TM 성인 클럽 경기 510 | 전부 넣음 | 유소년·2군 경기 없음(raw/tm_games.csv level=senior 510) |
| 2004.7.24 J리그컵 주빌로전(13분) | 넣음 | TM·영어/일본어 위키백과 모두 나고야 2004 기록(고교 재학 특별 지정 시기) |
| VVV 2008-09 에이르스터 디비시 | 넣음 | 네덜란드 2부 프로 리그 |
| 네프치 2020-21(아제르바이잔), 수두바 2021(리투아니아 A 리가), 파로 2024(부탄) | 넣음 | v1.163 경계 규칙: TM·영어 위키백과 통산에 들어감 |
| FC 주롱 2026-27(싱가포르 프리미어리그) | 넣음 | 프로 리그. TM 6경기 교체(8·9·11·8·10·1분). FotMob 경기 자료는 교체 명단에만, 영어 위키 1경기 → TM 따름 |
| **2024.10.20 부탄 리그 팀푸 시티 2-2 파로(TM 4600538)** | **추가: 출전 90분 추정, 혼다 2골(34분 0-1→1-1, 90+2분 1-2→2-2), PK 아님** | TM는 'not in squad'. 경기 단위 출처 3곳: FIFA+ 하이라이트 설명(팀푸 선제골 → 혼다 동점골(파로 데뷔골) → 팀푸 막판 PK → 혼다 추가시간 동점골), sporteden 경기 기록(혼다 34·90+2), 부탄 축구협회 기사 bhutanfootball.org(2024.10 2-2, 혼다 득점). 일본어 위키 파로 리그 2경기 2골, planetsport 전반 1-1. 계약 기간(TM 이적 기록 2024.10.15~11.1 재등록)과도 맞음. 크레스포·리켈메 선례(경기 단위 출처로 확인된 경기만, 분 자료 없으면 90분 추정). **사용자 확인 권장**: 선발 여부·출전 분 자료 없음. 부탄 축구협회 기사 문장 'Honda scored in this fixture from the penalty'는 FIFA+ 설명(막판 PK는 팀푸 시티 골)과 맞지 않아 두 골 모두 일반 골로 둠 |
| 2024.8 부탄 U-20 친선(혼다 도움) | 뺌 | 친선경기(TM 없음) |

## 2. 대회 코드
- 리그(lg): JAP1·NL1·NL2·RU1·IT1·MEXA·MEX1·AUS1·BRA1·AZ1·LI1·BH1L·SIN1. PON2(2008 승강 플레이오프 2라운드 ADO 덴하흐 1·2차전·재경기, 골·도움 없음) = 리그 비중(판니스텔로이·바스토스 선례).
- 국내컵: JAPC(J리그컵, 조별 ko 0)·JEMP(일왕배 4·5라운드)·NLP(KNVB컵)·RUP(러시아컵: 6라운드·16강 dc, 8강 dk, 준결승 dsf, 결승 df)·CIT(코파 이탈리아 3·4라운드·16강 dc, 8강 dk, 준결승 dsf, 결승 df)·MXCA(코파 MX 조별 dc ko0, 16강 dc, 8강 dk, 준결승 dsf, 결승 df)·BRC(코파 두 브라질 dc). BRCR(캄페오나투 카리오카 조별·준결승) = dc(아드리아누·네이마르 선례: 주 선수권 낮은 비중).
- RUSS 러시아 슈퍼컵 3경기 = df.
- CL 조별 clg, 16강 cl16, 8강 clk; EL 조별 elg, 16강 elk; ELQ(2010 애노소시스, 2012 AIK 플레이오프) elq. KLUB 클럽 월드컵 2017(2경기, 연장) cwc.
- AUSF A리그 파이널 시리즈(엘리미네이션 파이널 'First Round Replay'·준결승) = mlp 단판(델 피에로·아두리스 선례).
- AFCL AFC 챔스 2019 조별 = acl(ko 0).
- **ACHQ AFC 챌린지 리그 2024-25 예선(네팔 처치 보이스 원정 2-1, 90분, 골·도움 없음) = ac2**: 계산기에 AFC 3부 대회 코드가 없어 가장 가까운 AFC 챔스 투 비중(M 행만 영향). 오케스트레이터 판단 필요하면 바꿔도 SOC 변화 없음.
- 두 경기 합산 E 행 4개(3경기): 챔스 2009-10 16강 2차전 세비야 원정(1차 1-1, 원정 다득점·연장), 유로파 2012-13 PO 1차전 AIK 원정, 코파 이탈리아 2015-16 준결승 2차전 알레산드리아(1차 1-0, 원정 다득점·연장).

## 3. 골 판정
- TM 105골 = API·리포트 일치. FotMob 2010년 이후 57골(53경기) 대조: 수·PK 같음, 2012.9.16 알라니야전 49분(FM 51분) → TM. ESPN 59골 모두 같음.
- 2006.9.16 알비렉스전 리포트에 상대 골 빠짐(스코어 3-0으로 적힘): J리그 공식 기록(data.j-league.or.jp match_card_id=9392) 혼다 17분·욘센 23분·쓰다 74분, 상대 36분 자책골 → 혼다 골 전 0-0 그대로.
- PK 골 9 = TM 'Penalty'(FotMob 키와 일치). 2009.12.4 빌럼 II전 90+1 PK 골의 TM 도움 칸 'Penalty: Fouled player'는 본인 골 행(도움 아님).
- 본인 자책골 없음.

## 4. 도움 판정 (TM 81 → 73)
뺀 것 8:
- 슈팅 리바운드('Shot on goal') 4: 2009.2.6 즈볼레 50분 엘 가우이리, 2011.2.28 러시아컵 시니크 22분 이그나셰비치, 2013.5.12 로코모티프 43분 바그네르 로브, 2013.11.2 볼가 73분 토시치.
- 상대 자책골 유도 1: 2009.5.8 옴니월드 15분 트로스트 자책골.
- PK 유도 1: 2014.11.30 우디네세 65분 메네즈 PK(메네즈 자료 men.js에도 도움 없음).
- 2014.8 이후 확인 못 함·도움 아님 2: **2016.2.22 나폴리 44분 보나벤투라**(혼다 크로스가 쿨리발리 머리 맞고 굴절 — AP·Corriere dello Sport; FotMob·ESPN·FussballTransfers 모두 도움 없음 → 굴절 규칙), **2017.9.12 코파 MX 시마로네스 68분 오마르 곤살레스**(ESPN 경기 기록에 혼다 없음, 다른 기사 못 찾음).
넣은 것(2014.8 이후):
- TM+FotMob 이벤트 14: 밀란 7(파르마 25분·체세나 19분·로마 40·59분·프로시노네 50분·로마 50분·인테르 35분), 멜버른 빅토리 7(퍼스 47·87분, 뉴캐슬 71분, 시티 50분, 브리즈번 24분, 파이널 웰링턴 42분·시드니 90+1분; ESPN도 같음).
- 다른 독립 출처 2곳으로 확인 11:
  - 2015.8.17 CIT 페루자 28분 루이스 아드리아누: FourFourTwo('Honda's pass')·Forza Italian Football('Honda's through-ball'). FussballTransfers는 도움 없음.
  - 2015.12.17 CIT 삼프도리아 90+3분 바카: FourFourTwo('set up by Keisuke Honda')·Sportsmole('Honda found Bacca inside the box').
  - 2016.1.13 CIT 카르피 14분 바카: FussballTransfers(Assist K. Honda)·Eurosport(Honda's through ball)·AP/Fox Sports.
  - 2016.3.1 CIT 알레산드리아 20분 메네즈: FussballTransfers(Assist K. Honda)·Sportsmole·FourFourTwo.
  - 리가MX 클라우수라 2018 7개(1.13 아메리카 47분 무리요, 1.20 로보스 10분 사갈·40분 아기레, 2.11 베라크루스 34분 구티에레스, 3.4 톨루카 53분 페냐, 3.17 네카사 36분 구티에레스, 4.14 산토스 30분 아기레): ESPN 경기 기록 + FussballTransfers 경기 기록(footmercato.net과 같은 Webedia 자료, 한 출처로 셈) 모두 혼다 도움. 아메리카전은 Quadratín 기사(혼다 코너킥)도. FotMob은 이 시즌 도움자 이름·선수 경기 목록 도움이 비어 있음.
- 2014.8 이전 도움: TM 단일 출처 규칙(VVV 2008-09는 FotMob·ESPN 없음, CSKA 2010~13은 FotMob 도움자 대부분 비어 있음). 'Deflected shot'은 골 설명(득점자 슈팅 굴절)이라 도움 유형 아님 → 유지(2009.4.17 엠먼 24분).
- 나고야 2004~07: TM에 도움 자료 없음(0) — 실제 도움 미상, 설명에 적음.
- 2008.8.22 FC 에인트호번 원정 90분 샤컨 골(혼다 도움): 리포트가 90분 골 두 개(에인트호번 코츠·VVV 샤컨)를 모두 '1-2'로 적어 순서가 모호함. 리포트 나열 순서(코츠 골 뒤 샤컨 골)대로 골 전 1-1로 씀(다른 출처 없음).

## 5. 날짜
- TM API UTC → 경기장 시간대 현지 날짜(raw/tm_games.csv date_local_tz_conv). 파추카·보타포구 저녁 경기 49개는 TM 일정(CET)보다 하루 앞. 3411142 보타포구-브라간치누는 UTC 22:15 → 2020-08-11 현지(FotMob 변환 8-12는 UTC 날짜).

## 6. 상대 Elo·순위 라벨
- 출처 순서: 같은 경기 다른 선수 자료 11(밀란 동료 els·men·blt·kak, rbh, tor 등) → 기존 팀×시즌 값 96 → 순위표 → 라벨 65 → 직접 라벨 8. 값은 모두 tools/league_rank_apply.py parse/value(+ league_points 승점 모형)로 계산; 스크래치에서 `league_rank_apply.py` 바뀌는 행 0, 네 도구 이동량 모두 +0, `elo_table.js` 값이 여럿인 팀-시즌 0.
- 순위 확인·고침:
  - 러시아 1부 2011-12: TM 표가 크라스노다르 8위·쿠반 9위 → 공식(영어 위키 챔피언십 그룹 1~8·강등 그룹 9~16)은 쿠반 8위, **크라스노다르 9위**로 라벨.
  - **에이르스터 디비시 2008-09 감점 시즌**: 위키 표(에인트호번·벤담 −3) 되돌리면 15 포르투나 42·16 에인트호번 41·**17 RBC 로센달 40**·18 텔스타 39·19 벤담 39(골득실) → 로센달 `17위/20팀 (감점 전 순위; Eerste Divisie)`. **elo/penalty_seasons.json에 로센달(공식 16 → 경기장 17) 줄이 빠져 있음 — 추가 필요.**
  - 러시아 3부 2012-13 FC 튜멘(러시아컵 16강): 우랄-볼가 지역 2위/15팀(futbol24 순위표: 가조비크 69·튜멘 66; Sportbox 시즌 기록 같은 승점; 아카데미야 톨리야티 시즌 중 기권 포함 15팀).
  - 러시아 2부 2011-12 알라니야 2위/20팀(러시아컵 결승 2011.5.22, FNL 2011-12는 4월 개막해 진행 중 시즌 → 그 시즌 최종 순위).
  - 브라질 4부 2020 방구 42위/64팀: 2020.3.15 카리오카 경기. 방구는 2020 세리에 D(64팀, 8조) A7조 6위로 조별 탈락. 조별 탈락 32팀을 승점·승수·골득실로 매겨 전체 42위(영어 위키 2020 Série D 원문 표로 계산). 기존 선례(아메리카 RJ 2010 세리에 D 순위) 형식.
  - 부탄 1부 2024 팀푸 시티 3위/10팀: 영어 위키 시즌 문서(TM 표는 2위; FIFA+ 설명도 이 무승부로 준우승을 놓쳤다고 적음). **'부탄'이 league_rank_apply.py KO 목록에 없어** 도구의 value('Bhutan',1,2024,cal,3,10)를 직접 불러 240(Opta 부탄 리그 30.06 → Elo 식, 흩어짐 60). 상대 보정 하한 0.3(Elo ≈ 697 이하 같음). KO에 '부탄': 'Bhutan'을 넣으면 같은 값.
  - 리가MX: 경기 날짜에 진행 중이던 단계 정규 리그 순위(아페르투라 2017 = TM MEXA 표, 클라우수라 2018 = TM MEX1 표). 코파 MX 8강 티후아나(2017.11.8)도 아페르투라 2017 11위(기존 표의 '2017-18 누적' 대신 단계 규칙). 사카테펙(아센소 MX)은 기존 값 '멕시코 2부 2017-18 3위/16팀 (연간 합산)' 그대로.
  - J1 2005~2007·러시아 1부 2010·2012-13·2013-14·A리그 2018-19·브라질 2020·아제르바이잔 2020-21·리투아니아 2021: TM 최종 순위표(우승 팀 확인: J1 2005 감바·2006 우라와·2007 가시마, 러시아 2010 제니트, A리그 정규 1위 퍼스, 브라질 2020 플라멩구, A 리가 2021 잘기리스).
- 라벨 이름: J1리그·러시아 1부·리가MX·호주 A리그·브라질 세리에 A·아제르바이잔 1부·세리에B 등 정해진 이름 사용. 에이르스터 디비시(네덜란드 2부)는 기존 형식.

### 승점 표 map 추가 필요
(`<라벨 머리> | <이 자료 상대 이름> | <표 팀 이름> | [표, 행]`)
```
J1리그 2007 | JEF United Chiba | JEF United Chiba | [0,12]
J1리그 2007 | Kashima Antlers | Kashima Antlers | [0,0]
러시아 1부 2010 | Amkar Perm | Amkar Perm | [0,13]
러시아 1부 2010 | Anzhi Makhachkala | Anzhi Makhachkala | [0,10]
러시아 1부 2010 | Krylya Sovetov Samara | Krylia Sovetov Samara | [0,12]
러시아 1부 2010 | Sibir Novosibirsk | Sibir Novosibirsk | [0,15]
러시아 1부 2010 | Terek Grozny | Terek Grozny | [0,11]
러시아 1부 2010 | Tom Tomsk | Tom Tomsk | [0,7]
러시아 1부 2010 | Zenit St. Petersburg | Zenit St. Petersburg | [0,0]
러시아 1부 2011-12 | Anzhi Makhachkala | Anzhi&nbsp;Makhachkala | [0,4]
러시아 1부 2011-12 | Dinamo Moscow | Dynamo Moscow | [0,3]
러시아 1부 2011-12 | FC Krasnodar | Krasnodar | [0,8]
러시아 1부 2011-12 | Tom Tomsk | Tom Tomsk | [0,14]
러시아 1부 2012-13 | Alania Vladikavkaz | Alania Vladikavkaz | [0,15]
러시아 1부 2012-13 | Amkar Perm | Amkar Perm | [0,10]
러시아 1부 2013-14 | Kuban Krasnodar | Kuban Krasnodar | [0,7]
브라질 세리에 A 2020 | Ceará Sporting Club | Ceará Sporting Club | [0,10]
세리에B 2015-16 | AC Perugia Calcio | Perugia | [0,9]
에이르스터 디비시(네덜란드 2부) 2008-09 | AGOVV Apeldoorn | AGOVV | [0,10]
에이르스터 디비시(네덜란드 2부) 2008-09 | FC Emmen | Emmen | [0,12]
에이르스터 디비시(네덜란드 2부) 2008-09 | MVV Maastricht | MVV | [0,5]
에이르스터 디비시(네덜란드 2부) 2008-09 | RBC Roosendaal | RBC Roosendaal | [0,16]
호주 A리그 2018-19 | Brisbane Roar | Brisbane Roar | [0,8]
호주 A리그 2018-19 | Central Coast Mariners | Central Coast Mariners | [0,9]
호주 A리그 2018-19 | Melbourne City FC | Melbourne City | [0,4]
호주 A리그 2018-19 | Newcastle United Jets | Newcastle Jets | [0,6]
호주 A리그 2018-19 | Perth Glory | Perth Glory | [0,0]
호주 A리그 2018-19 | Wellington Phoenix | Wellington Phoenix | [0,5]
호주 A리그 2018-19 | Western Sydney Wanderers | Western Sydney Wanderers | [0,7]
```
(map을 넣으면 이 행들 값이 승점 모형으로 바뀜 — 넣은 뒤 league_rank_apply --apply 필요.)

## 7. 시즌·클럽 구분
- 클럽 키(모두 새 키, index.html에 없음 확인): nagkh·vvvkh·cskkh·milkh·packh·mvkh·vitkh·botkh·nefkh·sudkh·parkh·jurkh. 경계 = TM 이적일.
- 달력 연도: nagkh·botkh·sudkh·parkh(integration.json calendar).
- **index.html seasonOf 수동 패치 필요(CSKA)**: `if(club==="kobvl")return "2019";` 바로 뒤에
  `if(club==="cskkh"){if(y<=2010)return "2010";if(d<"2012-07-01")return "2011-12";const s=d.slice(5)>="07-01"?y:y-1;return s+"-"+String(s+1).slice(2)}`
  (2010 달력 연도, 2011.1~2012.6 = 2011-12 전환 시즌(2011.2.28 컵 16강 포함), 이후 7월 1일 기준: 2013.7.13 슈퍼컵 = 2013-14). 스크래치에서 이 패치로 check 통과.
- 파추카(2017.8.22 첫 경기)·주롱(싱가포르 2025-26부터 가을~봄)·멜버른 빅토리 등은 기본 8월 1일로 맞음.

## 8. 같은 경기 다른 선수 자료
- 일치: 엘샤라위(2014.8.31 라치오 7분·10.19 베로나 27분 혼다 골 도움), 카카(2014.3.29 키에보 27분), 메네즈(2016.3.1 알레산드리아 20분), 발로텔리·로비뉴 등 같은 경기 Elo/lv/대회 동일. 발로텔리 2014.1.26 칼리아리 87분 골은 혼다 도움(89분 파치니) 근처 다른 골이라 불일치 아님.
- okz.js 2010.4.11 센다이전 'Honda' 도움은 다른 선수(혼다 다쿠야, 시미즈) — 무관.
- 이번 회차 다섯 명(오카자키·미나미노·혼다·케이힐·소보슬러이)과 혼다의 같은 클럽 경기 없음.

## 9. 수상(hon)
- TM 업적: 러시아 리그 12/13·13/14(CSKA), 러시아컵 10/11·12/13, 러시아 슈퍼컵 13/14, 수페르코파 16/17(밀란), 네덜란드 2부 08/09(VVV, '(네덜란드 2부)' 표기 — 그리에즈만·카라스코 선례), 아제르바이잔 20/21(네프치), 부탄 2024(파로; TM 표기 23/24이나 부탄 리그는 달력 연도).
- POY: 08/09 에이르스터 디비시 · 사무국(TM 'Player of the Year Jupiler League'; 리그 주관 KNVB '구던 스티어', Japan Times 2009.5.16 'MVP of the second division'). 선수협회 상 아님.
- FOY: 2010 CSKA(TM 'Footballer of the Year 2010').
- 대표팀(아시안컵 2011 등)·준우승 제외.

## 10. 확인 못 한 것·사용자 확인 권장
- 2024.10.20 파로 경기 추가(출전 90분 추정, 2골) — TM 'not in squad'와 다름.
- 브라질 4부 2020 방구 전체 순위(조별 표로 직접 매김).
- ACHQ를 AFC 챔스 투 비중으로 둔 것(골·도움 없음).
- 부탄 리그 Elo 240(도구 KO 목록 밖).
