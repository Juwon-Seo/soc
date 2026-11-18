# 도메니코 베라르디 판정 기록 (2026-11-18)

재현: `python3 players/berardi/build_berardi.py` → `src/data/ber.js`, `players/berardi/berardi.json` (`--debug` Elo 출처, `--fm` FotMob 골 대조).
결과: 436경기 158골(PK 54) 105도움, 33,731분, 기록 263행(합산 6행/4경기). Elo 출처: 팀×시즌 통합표 215, 순위표+모형 42, 직접 추정 6(같은 경기 다른 선수 자료 0 — 사수올로 동료가 계산기에 없음).
접두어 BER(src/data/ber.js·BER_ 미사용 확인), 프리셋 berardi, 클럽 키 sasdb(미사용 확인).

## 1. 범위·클럽
- 성인 클럽 공식 경기만: TM API played·사수올로(6574) 436경기 = 리그 393(세리에A 327 + 세리에B 2012-13 37·2024-25 29), 코파 이탈리아 17, 유로파리그 예선 4. 친선·대표팀(이탈리아·U21) 제외.
- 유스 제외: 사수올로 프리마베라(TM 19114) 출전 28경기 7골 1도움(1군 데뷔 뒤 5경기 포함)과 'played for a different team' 12행(discrepancies 7) — 프로젝트 선례대로 뺌.
- 프로 리그 규칙(v1.159): 세리에A·세리에B만(둘 다 프로) → 제외 시즌 없음. 세리에B는 2012-13(우승 승격)·2024-25(2023-24 세리에A 19위 강등 뒤, 우승 승격). 작업 지시의 '2025-26 세리에B' 추정은 출처(TM·FotMob·위키백과)와 맞지 않아 2024-25로 판단(discrepancies 7).
- 유벤투스: 2013.9.1 공동 소유권 매입 + 같은 날 사수올로 임대, 2015.6.30 임대 종료, 2015.7.1 사수올로가 되삼(TM 이적 기록). 유벤투스 공식 경기 0경기(TM·FotMob·영어 위키백과) → 클럽은 사수올로 하나(키 sasdb), 설명에 공동 소유 사실만 적음. 2013.8.17 코파 이탈리아 노바라전은 공동 소유 전.
- 포지션 RW(TM Right Winger), 국기 IT(기존), 현역(retired false).
- 날짜: TM 리포트 날짜 = 계산한 현지 날짜(차이 0, 빌드가 확인). 리포트 없는 리그 경기는 UTC→Europe/Rome 계산 날짜.

## 2. 출전·분
- TM playedMinutes 그대로(빈 값 0, 90분 추정 0). FotMob playerMatches(2017.2 이후 289경기)와 경기 목록 같음, 분 차이 1~2분뿐(discrepancies 4). 2017.2 이전은 FotMob 라인업과 대조해 3분 넘는 차이 0(discrepancies 5).
- 위키백과 차이(discrepancies 3): 영어 433(2026-27 리그 6경기로 갱신 늦음), 이탈리아어 435(2025-26 리그 25) → TM·FotMob 436이 맞음.

## 3. 골 (TM 리포트 158 = API 158 = FotMob 158)
- PK 54 = TM 'Penalty' = API penGoals = FotMob penalty 키(빌드가 API PK 수와 대조).
- 2026.2.20 베로나전 44분: PK 실축(몬티포 선방) 뒤 리바운드 골('Penalty rebound', API penGoals 0, FotMob 페널티 표시 없음) → 일반 골(지시·규칙).
- 골 분: TM 리포트 분. FotMob과 1분 차이·추가시간 '90'/'45' 표기 차이만(discrepancies 2), 골 뒤 스코어 모두 같음(`--fm` 차이 0). 수정 없음.
- 실축 PK 9개는 기록 없음.

## 4. 도움 (TM API 114 → 105)
| 구분 | 경기 | 판정 |
|---|---|---|
| 상대 자책골 | 2478866 2015.3.22 엠폴리 50분 루가니(Cross) | 제외 |
| 상대 자책골 | 3433428 2021.3.3 나폴리 34분 막시모비치(Free kick) | 제외 |
| 상대 자책골 | 4620930 2026.1.31 피사 45+1분 카라촐로('Shot on goal' = 슈팅이 수비 맞고 들어감) | 제외 |
| PK 유도 | 2726817 2017.5.7 피오렌티나 74분 폴리타노 PK('Penalty: Fouled player') | 제외 |
| PK 유도 | 3614807 2022.3.6 베네치아 29분 스카마카 PK | 제외 |
| 본인 PK 골의 본인 도움(API 미포함) | 15개(discrepancies 1 목록) | 도움 아님 |
| 2014.8 이전 TM 단일(FotMob 없음) | 2012-13 세리에B 6개(2012.9.1 크로토네 파볼레티, 10.14 바레세 가촐라, 10.30 테르나나 파볼레티, 2013.3.9 바레세 마수치, 4.20 바리 파볼레티·테라노바) + 2014.2.2 베로나 90+2 플로로 플로레스 | 포함(규칙: 2014.8 이전 TM 단일 허용, 클로제·인시녜 선례; FotMob 2012-13 도움 자료 전무) |

2014.8.1 이후 TM 단독(FotMob 도움 없음) 12개 — 다른 출처 2곳 확인(WebSearch·curl):
| 경기 | 판정 | 근거 |
|---|---|---|
| 2486232 2014.8.21 CIT 치타델라 12분 자차(Corner) | 포함 | Sports Mole "Zaza stroked home a left-footed volley from a Domenico Berardi corner"; FourFourTwo "Zaza had opened the scoring from Domenico Berardi's corner" |
| 2486232 같은 경기 52분 산소네 | 포함 | Sports Mole "soon bagged his second assist, setting up Sansone"; FourFourTwo "picked out Nicola Sansone from deep and the forward found the net" |
| 2611210 2015.8.15 CIT 모데나 67분 플로로 플로레스 | 제외 | Forza Italian Football은 플로로 플로레스 로빙만, 도움자 없음. 다른 기사 못 찾음 |
| 2740236 2016.8.18 ELQ 츠르베나 즈베즈다 41분 폴리타노 | 포함 | LaPresse "splendida combinazione tra Politano e Berardi … con un delizioso tocco morbido serve il numero 16"; Football Italia "A cute one-two with Berardi put him one-on-one" (AP 기사 Saudi Gazette/Yahoo "after a one-two with Berardi"는 같은 통신이라 추가 셈 안 함) |
| 2726835 2017.5.21 칼리아리 7분 마냐넬리(Corner) | 제외 | FotMob은 폴리타노 도움. Sporting Life Opta 문자 중계("Assisted by Domenico Berardi following a corner")·Foot Mercato(같은 Opta 계열) = 1곳. Unione Sarda는 "sugli sviluppi di un corner: il velo di Sensi…"로 키커 미기재 |
| 3089417 2018.8.12 CIT 테르나나 80분 마냐넬리 | 제외 | il Resto del Carlino "La chiude il capitano Magnanelli" 도움자 없음, 다른 기사 못 찾음 |
| 3229204 2019.9.22 SPAL 50분 던컨 | 제외 | Forza Italian Football "Caputo laid one off for Berardi who was closed down quickly by Etrit Berisha. Trying to beat him, the Italian's touch found its way wide where Duncan tapped in" → 흘러나온 공(도움 아님 규칙) |
| 3614595 2021.10.17 제노아 17분 스카마카 | 제외 | calciomercato.com 평점 "pur confezionando l'assist"만. futbolfantasy 문자 중계는 골 직전 "Davide Biraschi intercepta un pase"(굴절 가능) → 독립 2곳 없음 |
| 3614776 2022.2.13 로마 73분 트라오레 | 포함 | Football Italia "sneaking in front of Rick Karsdorp to chest down a Berardi cross"; Tuttomercatoweb "l'invito a nozze arriva dall'altro grande prim'attore, Berardi" |
| 4385929 2024.11.9 쥐트티롤 57분 라우리엔테 | 포함 | Tuttomercatoweb 평점 "Mette al referto un assist sulla conclusione di Laurientè"; Yahoo Sports 문자 중계 "Domenico Berardi with an assist there" (TM 골 유형은 '직접 프리킥'이나 두 출처 모두 베라르디 도움) |
| 4386312 2025.4.25 체세나 24분 라우리엔테 | 포함 | il Resto del Carlino "Berardi inventa, Laurientè finalizza"; Tuttomercatoweb(평점 기사 '1-0 도움') |
| 4631308 2025.8.15 CIT 카탄차로 32분 도이그 | 포함 | Corriere dello Sport 문자 중계 "J. Doig, 32' (ass.: D. Berardi)"; Fox Sports 경기 기록 "Domenico Berardi … 1 Assist" |

FotMob 단독 도움(TM 없음) 1개:
| 경기 | 판정 | 근거 |
|---|---|---|
| 3081132 2018.11.4 키에보 42분 페데리코 디 프란체스코(0-0 → 0-1, FotMob 분) | 포함 | LaPresse "azione iniziata da Boateng, proseguita da Berardi e finalizzata da Di Francesco, che dopo aver raccolto il passaggio…"; Blitz quotidiano 경기 기록 "Berardi premia l'inserimento di Di Francesco" |

- 2014.8 이후 도움 = TM∩FotMob 85 + 다른 출처 2곳 7 + FotMob 단독 확인 1 = 93; 이전 12(TM 단일). 합계 105.
- 도움 유형 빈칸(2014.8 치타델라 산소네, 2015.11.8 카르피 산소네, 2016.4.24 토리노 펠루소, 2016.8.18 폴리타노, 2017.12.10 크로토네 폴리타노): 다른 출처 또는 FotMob 일치 → 일반 도움.
- 빌드가 FotMob 단독 도움이 이것 말고 없음을 확인(2017.5.21 칼리아리 7분은 FotMob이 폴리타노).

## 5. 대회 코드·합산
- 리그 lg(IT1·IT2). 코파 이탈리아: 1~4라운드·32강·16강 dc, 8강 dk(2022.2.10 유벤투스, 골·도움 없음). 모두 단판 ko 1.
- 유로파리그 3차 예선(루체른)·플레이오프(츠르베나 즈베즈다) elq, 두 경기 tie [leg, home, 1차전 우리, 상대, 원정 다득점 1, 연장 1](UEFA 2016-17). 다른 차전 스코어는 TM 리포트(tm_two_leg_ties): 루체른 1-1(원정)·3-0(홈), 츠르베나 즈베즈다 3-0(홈)·1-1(원정). 조별 6경기는 부상 결장.
- 승부차기: 2023.11.2 스페치아(5-4 pens, 44분)·2026.9.2 프로시노네(35분) — 골·도움 없음. 2013.8.17 노바라 연장 — 골·도움 없음.

## 6. 상대 Elo
- 우선순위: 같은 경기 다른 선수 자료(±1일, 해당 0) → 팀×시즌 통합표(215) → 직접 추정 → 순위표+모형(디 나탈레 스크립트와 같음).
- 시즌: 7월 이후 새 시즌(2016.7.28 루체른 = 2016-17), 단 2020.7~8월 코로나 재개 경기는 2019-20.
- 세리에B 모형(1577.78 + 51.24×곡선): 기존 순위값과 1점 안에서 같음을 확인(2013-14 7위 1602·13위 1559, 2025-26 12위 1559·14위 1551·17위 1528·18위 1522 재현). 쓰인 값: 2012-13 5위 노바라 1614·7위 바레세 1602·10위 바리 1577·12위 크로토네 1564·14위 체세나 1555(13위 1559·15위 1552 가운데와 같음)·18위 란차노 1534·19위 비첸차 1527·20위 아스콜리 1521·21위 프로 베르첼리 1517; 2014-15 20위 치타델라 1521; 2017-18 10위 스페치아 1577; 2022-23 10위 모데나 1570; 2024-25 2위 피사 1663·7위 체세나 1597·10위 쥐트티롤 1570·11위 모데나 1564·12위 카라레세 1559·13위 레조아나 1554·14위 만토바 1551·15위 프로시노네 1546·16위 살레르니타나 1538·17위 삼프도리아 1528·18위 브레시아 1522·19위 치타델라 1518·20위 코센차 1508; 2025-26 5위 카탄차로 1611. 순위는 raw/ranks.txt(TM 최종 순위표).
- 세리에C(3부) 2018-19 B조 테르나나 11위/20팀: 1416.56 + 51.24×곡선 = 1403 "(추정)"(인시녜·디 나탈레 자료와 같은 모형; 같은 모형 20팀 2위 1501 = 기존 파도바 2020-21 값).
- 세리에A 2026-27 토리노: 2026.11.18 TM 순위표 11위 → 1714 "세리에A 2026-27 (11월 18일 현재) 11위"(20팀 순위값 = 기존 제노아 2026-27 11위 1714).
- 직접 추정: 루체른 2016-17(스위스 5위, TM C1 2016) 1461 = 기존 스위스 슈퍼리그 2012-13 5위 툰 1461; 츠르베나 즈베즈다 2016-17(세르비아 2위, 챔피언십 그룹 2위) 1500 = 기존 같은 팀 2위(2001-02·2007-08) 1500.
- `node tools/elo_table.js`(스크래치, 베라르디 포함 166명): 값이 여럿인 팀-시즌 0.

## 7. 동료 자료 대조
- 계산기에 사수올로 시절 동료가 없음(src/data 전체에 'Domenico Berardi' 0건, 같은 날 같은 상대 기록 0). 불일치 없음.
- 같은 라운드의 다른 새 선수(두에·구이리·키슬링·코스티치)와 겹치는 경기 없음(사수올로 경기만).

## 8. 시즌 구분(계산기)
- 7월 10일 기준 + 2020.7.1~8.31은 2019-20(아탈란타 `atapg`와 같은 분기). add_players.py의 jul10 목록은 2020년 7월 예외가 없어(2020.7.21·7.25 경기가 2020-21로 감) integration.json에는 넣지 않고, 스크래치 복사본에서 `if(club==="atapg"){`를 `if(club==="atapg"||club==="sasdb"){`로 손으로 고침 → 정본 반영 필요.
- 효과: 2016.7.28 루체른전(1골)이 2016-17. 기본 8월 1일이면 2015-16.

## 9. 우승·수상(hon)
- TM 업적: 세리에B 우승 12/13·24/25 → o(임모빌레 페스카라 선례 "세리에B 우승"). 승격 표기·유로 2020·U21 대회 제외. 클럽 1부 우승 없음 → t {}.
- POY "12/13 세리에B · AIC(선수협회)": TM 'Player of the Year 12/13 Serie B' = AIC Gran Galà Serie B 올해의 선수(영어 위키백과 AIC Serie B Footballer of the Year 목록 2012-13 Domenico Berardi, Sassuolo; 스크래치 union/raw/en_serieb_poy.txt), 임모빌레 11/12 선례.
- TM 'Striker of the Year 12/13'은 포지션별 상이라 뺌. AIC 세리에A 올해의 팀(union/raw/en_aic_xi.txt)에 베라르디 없음. FWA·디 스테파노·볼라 지 오루 해당 없음. 득점왕 없음.

## 10. 미확인·한계
- 2014.8 이후 TM 단독 도움 5개 제외(4절): 모데나 2015, 칼리아리 2017, 테르나나 2018, SPAL 2019(흘러나온 공), 제노아 2021.
- 2012-13 세리에B 도움 6개는 TM 단일 출처(FotMob 자료 없음, 규칙상 허용).
- 루체른·츠르베나 즈베즈다 Elo, 세리에C 테르나나 Elo는 추정.
- espn.com·fantacalcio.it는 이 세션 네트워크에서 못 읽음(espn.co.uk는 읽었으나 해당 경기 기사 없음).

## 11. 검증(스크래치 복사본, 다른 새 선수 파일 제외)
- `python3 tools/add_players.py dinatale players/berardi/integration.json`(색 #1d7cbf/#399ee6 자동) + seasonOf 분기 손수정(8절) → `tools/build.py` → `node tools/verify.js check dist/club-soc.html`: 기준 165명 수치 동일, 베라르디 '추가', 탭 글자 변화 0, 콘솔 오류 없음 → 통과.
- `node tools/elo_table.js`: 166명, 값이 여럿인 팀-시즌 0.
- pStats: SOC 297.11(166명 중 75위), 436경기 158골 105도움 33,731분, 최고 3시즌 31.84(2021-22 37.73·2020-21 29.15·2014-15 28.66), 최고 5시즌 29.42(+2013-14 26.00·2019-20 25.59).
- 시즌별 SOC: 12-13 17.33, 13-14 26.00, 14-15 28.66, 15-16 20.20, 16-17 15.99, 17-18 6.98, 18-19 17.10, 19-20 25.59, 20-21 29.15, 21-22 37.73, 22-23 23.08, 23-24 19.91, 24-25 13.39, 25-26 11.64, 26-27 4.37.
- §16 점검(빌드 내장): 중복 0, 스코어 역순 0, 분 범위 이상 0, 모든 기록 날짜가 출전 행에 있음, 출전 행과 상대·대회 일치, 도움 득점자 이름 모두 있음, 경기별 골 수·PK 수 = TM API. 도움 수가 API와 다른 날은 위 제외 10건·추가 1건뿐.
