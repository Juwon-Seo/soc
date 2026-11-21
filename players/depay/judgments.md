# 멤피스 데파이 (Memphis Depay, TM 167850 · FotMob 303824) — 판정 기록 (2026-11-21)

재현: `python3 players/depay/build_depay.py [--out <data 폴더>]` → `players/depay/dep.js`(기본, src/에는 쓰지 않음), `players/depay/depay.json`. `--debug` Elo 출처, `--stat` 요약·판정·동료 대조, `--ties` 합산 행. 스크래치 복사본은 `SOC_ROOT=<복사본>`(Elo 통합표는 복사본에서 `node tools/elo_table.js`로 다시 만든 것을 씀 — 쿠티뉴·하메스 등 v1.268 자료 반영).
하메스 로드리게스 build 스크립트를 바탕으로 함. 보조: `assist_checks.py`(2014.8 이후 도움 웹 확인), `man_elo.py`(순위표 밖 상대 라벨), `note_depay.py`(설명).
결과: **527경기 181골(PK 24) 102도움, 34,469분**, 기록 283행(합산 28행/25경기). 접두어 DEP(src/data·index.html에 없음 확인), 프리셋 `depay`, 이름 '멤피스 데파이'(후보 풀 B-216~220 표). 현역(코린치안스).

## 1. 범위·클럽
- TM performance-game 성인 클럽 played 527경기 전부. 제외: 용 PSV(Beloften Eredivisie/nacompetitie, 리저브 리그) 19경기 12골 1도움, PSV U19 2경기, 맨유 U21 1경기 3도움, 네덜란드 대표팀, FotMob 친선(ICC 4경기).
- 모든 팀×시즌 프로 1부(에레디비시·PL·리그1·라리가·브라질 세리에 A) → 제외 시즌 없음. 캄페오나투 파울리스타(TM BCP1, 2025·2026 16경기)는 1부 팀의 주 선수권 → 넣음(네이마르·루카스 모우라·하메스·쿠티뉴 선례).
- 클럽 키(미사용 확인): psvdp mundp lyodp fcbdp atmdp cordp. 경계(TM 이적일): 2015-07-01 / 2017-01-20 / 2021-07-01 / 2023-01-20 / 2024-09-09. 빌드가 TM 클럽 id와 경계를 대조(불일치 0).
- 시즌: cordp calendar, 나머지 8월 1일. **수동 seasonOf 분기 필요(add_players.py가 못 넣음)**: 기본 규칙 '2020년 8월 경기는 2019-20'에서 lyodp의 2020-08-21 이후(2020.8.28 리그1 디종전, 2020-21 시즌 경기, E 행 있음)를 빼야 함. 스크래치에서 쓴 패치: `&&!(club==="arsau"&&d==="2020-08-29")` 뒤에 `&&!(club==="lyodp"&&d>="2020-08-21")` 추가(라피냐 renq·벤예데르 monby 예외와 같은 취지). 참고: 같은 경기 아우아르(lyoha) 출전 행은 이 예외 없이 2019-20으로 들어가 있음(보고만).
- 포지션 CF(TM 주 포지션 Centre-Forward; 부 포지션 LW·SS), 국기 NL(flagBody 있음), retired false.

## 2. 출전·분·날짜
- TM playedMinutes 그대로(90분 추정 없음). 연장 경기 6, 승부차기 6(discrepancies 9: TM API 스코어의 승부차기 골은 쓰지 않음; E 행 스코어는 리포트 골 순서로 계산).
- 날짜: date_local_computed(UTC→클럽 시간대). 코린치안스 저녁 경기 33경기는 TM 일정·리포트 날짜보다 하루 앞(discrepancies 8·11). 유럽 경기는 TM과 같음.
- **지예흐(보타포구, 이번 차례 병행 판정)와 공유 경기**: 2026-11-18(현지) 브라질 세리에 A 35라운드 코린치안스 4-0 보타포구. 데파이 행: 34분 골(골 전 1-0), 60분 카이우 세자르 골 도움(골 전 2-0), 상대 Elo 1648 '브라질 세리에 A 2026 11위/20팀'(통합표, 쿠티뉴 자료 값). 지예흐 자료도 날짜 2026-11-18·최종 0-4로 맞아야 함.

## 3. 골 (TM 181 그대로, PK 24 = API penGoals)
- 2011-09-21 KNVB컵 2라운드 VVSB 0-8 PSV 20'·73'(TM 데파이, FotMob 데리크·라비아드, en.wiki 시즌 표 컵 1골): PSV 구단 기사 'Our heroes: Memphis Depay'(psv.nl, 'Memphis immediately scored two goals'), blikopnoordwijkerhout.nl(에인트호번스 다흐블라트 인용, VVSB 수비수 페리르 '데파이 두 골을 봤다'), en.wiki 본문('opening an 8–0 away win') → **데파이 2골 유지**(골 전 0-0, 0-4).
- 2026-11-18 보타포구 34'(TM 데파이, FotMob 아르투르 샤베스 자책골): Lance!(‘gols de Kaio César (três vezes) e Memphis’), Mix Vale(34분 두 번째 골 데파이), InfoTimão(데파이 1골 1도움) — 한 매체는 굴절 자책골로 적음 → **데파이 골 유지**(골 전 1-0), NOTE에 기록.
- 2010-11 이후 FotMob 대조 149경기 181골: 위 두 경기 빼고 수·순서·PK 같음. 분 차이(discrepancies 6)는 TM 사용.
- 4582054(2025-05-10 미라솔 2-1 코린치안스): TM HTML 스코어 표시 오류(discrepancies 10) — 빌드는 편별 누적으로 스코어를 계산하므로 영향 없음(45+7 카카 골 전 0-0, 데파이 코너 도움, FotMob 이벤트도 데파이 도움).

## 4. 도움 (TM 109 → 102)
- 제외 7: PK 유도 4(2011.9.21 VVSB 23' 베이날뒴, 2016.1.9 셰필드 Utd 90+3 루니, 2017.2.8 낭시 54' 라카제트, 2019.10.26 메스 33' 뎀벨레), 'Shot on goal' 2(2012.8.30 제타 63' 마타브즈, 2014.8.7 장크트푈텐 70' 더용), 상대 자책골 유도 1(2016.2.25 미트윌란 32' 보두로프).
- 도움 아님(API도 0): 본인 PK 골 본인 도움 표기 5(제니트 2019, 브레스트 2020·2021, 레반테·에스파뇰 2021), 2020.8.7 유벤투스 43' 호날두 PK의 'Handball by Memphis Depay'.
- 2014.8 이전 TM 단일 출처(일반 유형·빈칸) 그대로.
- 2014.8 이후: TM+FotMob 이벤트(±2분) 67개.
- TM+FotMob 선수 경기 목록(이벤트에 도움자 없음) 12개 — 지시대로 세 번째 출처 확인: ESPN 경기 기록(site.api.espn.com summary 'Assisted by Memphis Depay') 모두 확인 → 넣음: 2018.2.4 모나코 12' 마리아노, 2018.4.28 낭트 69' 트라오레, 2018.9.15 캉 89' 망디, 2018.11.27 맨시티 55' 코르네, 2025.2.6 팔메이라스 43', 2.12 산투스 44', 2.19 UCV 36' 카리요, 2.26 UCV 40' 비두, 3.2 미라솔 22' 호메로, 3.9 산투스 12', 3.16 팔메이라스 58'(유리 알베르투), 2026.2.5 카피바리아누 80' 카이키.
- TM 단독 5개(다른 출처 2곳, WebSearch/원문 2026-11-21):

| 경기 | 판정 | 근거 |
|---|---|---|
| 2014.8.21 PSV-샤흐툐르 59' 마헤르 | 넣음 | Total Dutch Football('after a short corner from Depay') + fcupdate.nl 경기 페이지(도움 데파이) |
| 2015.8.18 맨유-브뤼헤 90+4 펠라이니 | 넣음 | Sports Mole('a peach of a cross for Fellaini') + RNZ(통신, 'converted a cross from Depay') |
| 2015.8.26 브뤼헤-맨유 20' 루니 | 넣음 | Sky Sports('setting up Rooney with superbly weighted pass') + ESPN 경기 기사 |
| 2015.9.23 맨유-입스위치 90+2 마르시알 | 넣음 | Sky Sports('bundled the ball into the path of Martial') + Sports Mole('from a Memphis Depay through-ball') |
| 2018.1.6 낭시-리옹 CdF 25' 페키르 | 넣음 | AS 낭시 공식 경기 기록('Depay entre dans la surface et sert Fekir') + Maxifoot(같은 매체 두 기사는 1곳으로 셈) |

- 확인 못 해 뺀 단일 출처 도움 없음. FotMob 단독 도움 없음. 금지 사이트 미사용(검색 결과의 worldfootball·fbref·sofascore 무시).

## 5. 대회 코드·합산
- lg NL1 GB1 FR1 ES1 BRA1. 국내컵 NLP FAC CGB FRC FRL CDR BRC: 결승 df / 준결승 dsf / 8강·FA컵 6라운드 dk / 그 외 dc. 쿠프 드 프랑스 TM 'Sixth Round'(2017.1.31 마르세유, 2018.1.24 모나코)는 dc(아우아르·페키르·발부에나 같은 경기 dc와 맞춤 — 처음에 dk로 잡았다가 고침). BCP1 모든 단계 dc(결승 두 경기 합산 (0,0)). NLSC·SCBR df, SUC 2022 준결승 dsf. CLQ clq, ELQ elq, CL·EL 단계별, 2020.8 리스본 8강·준결승 단판 clk/clsf. CLI 예선 2·3라운드 lib(바스투스 2016 선례), 16강 lib, 8강 libk. CS 조별 csa, 8강 csak, 준결승 csasf.
- 합산(원정 다득점, 연장): CL·EL·CLQ·ELQ 2021-08 전 (1,1), 뒤 (0,1); CDR 2024 준결승 (0,1)(데파이 G/A 없음); CLI·CS 2022~ (0,0); BRC 2025 (0,0); BCP1 (0,0). 합산 행 28개/25경기.
- 연장 시간 기록: 2024.1.18 CDR 레알 마드리드 119' 도움(et 1). 2022.4.14 프랑크푸르트 90+11 PK 골은 정규 시간.

## 6. 상대 Elo (283행: 같은 경기 95 / 통합표 127 / 순위표→라벨 47 / 순위표 밖 라벨 14)
- 순서: 같은 경기 다른 선수 자료(git 추적 파일) → 통합표(스크래치 재생성본) → man_elo.py → raw/ranks.txt(TM 표). 라벨 값은 league_rank_apply value(); 통합표 라벨 재계산 차이 0.
- eu(): 2020-06-01~08-20 경기는 2019-20(유벤투스 2020.8.7 → 세리에A 2019-20 1위 1958; 처음 2020-21로 잡힌 것을 고침).
- 순위표 밖: VVSB 2011-12 토프클라서 일요일 11/16(nl.wiki 'Topklasse voetbal 2011/12'), 아힐레스 '29 2012-13 토프클라서 일요일 1/16(nl.wiki 2012/13, 우승), EHC 호엔스브룩 2012-13 호프트클라서 일요일 B 4/14(RSSSF ned-amat2013, 'EHC/Heuts'), 샤흐툐르 솔리고르스크 2014 3/12(RSSSF witr2014 챔피언십 플레이오프 최종; 같은 표의 디나모 민스크 2위는 통합표와 같음), 상 베르나르두 2025 브라질 3부 4/20(pt.wiki Série C 2025 Classificação geral; 같은 표 CSA 17위는 통합표와 같음), UCV 2025 베네수엘라 아페르투라 3/14(TM VZ1A = 'Liga FUTVE Apertura 2025' 표, 2월 경기 = 진행 중 단계), 아메리카 데 칼리 2025 콜롬비아 아페르투라 1/20(TM COLP 2025; 같은 표 나시오날 5·산타페 6·온세 칼다스 7·치코 17·마그달레나 19는 통합표 라벨과 같음), 로사리오 센트랄 2026 클라우수라 두 조 통합 1/30(futbolargentino.com 표, 조별 단계 16경기 종료: B조 1위 34점 +14, A조 1위 인스티투토 34점 +11). 카피바리아누 2026: pt.wiki 2026 세리에 C·D 참가 목록에 없음 → '브라질 5부 2026 순위 없음 (Campeonato Paulista Série A1 2026 (state league); 리그 수준 추정)', 값은 같은 해 기존 자료 값 1267(루카스 모우라 자료 EC Primavera; 쿠티뉴 선례 방식, tools base()와 다를 수 있음 — **확인 요청**).
- 7월 예선: 2013.7.30 줄터 바레험(CLQ 1차전)은 벨기에 2013-14가 7.26 이미 개막 → 2013-14 순위(4위); 2차전 8.7과 같은 값.
- 새 팀×시즌 35개: depay.json new_team_seasons(NOTE '새로 정한 팀-시즌 순위' 줄과 같음).

## 7. 동료 자료 대조 (수정 없음)
- 일치: 아우아르(aou) 17, 페키르(fek) 9(2018.1.6 낭시 포함), 라카제트 2, 테리에 2, 그리즈만 2, 뎀벨레 2, 카라스코 1, 박지성 1(2014.3.15 비테서), 루니 1(2015.8.26 브뤼헤 20') — 날짜·분·스코어·Elo·lv 같음.
- 거짓 경보: pay.js 2020-12-16(파예 상대 스타드 렌, 데파이 상대 스타드 브레스트 — 'Stade' 토큰), ica.js 2021-01-09(다른 경기), hdz.js 2021-10-20(디나모 키이우/휴스턴 다이너모).
- 출전 행 대회 코드: 쿠프 드 프랑스 'Sixth Round' dc로 맞춘 뒤 차이 0.
- 이번 차례 병행: 지예흐 — 2026-11-18 보타포구전(2절). PSV-아약스 2012.8.5 슈퍼컵은 지예흐 아약스 입단(2016) 전이라 무관. 블라호비치·와킨스·황희찬과 공유 경기 없음(데파이 2024.9 이후 남미). 다른 판정 파일은 읽지 않음.

## 8. 우승·수상 (TM 업적 raw/tm_honours.html)
- t: UEL 16/17 맨유; LG 22/23 바르셀로나·14/15 PSV; DC 2025 코린치안스(코파 두 브라질)·2016 맨유(FA컵)·11/12 PSV(KNVB컵); LC 2017 맨유(TM 목록대로, 3라운드 1경기 출전); SC 2026 코린치안스(수페르코파 두 브라질)·22/23 바르셀로나(수페르코파)·12/13 PSV(요한 크라위프 스할 2012.8.5; TM '2013').
- o: 캄페오나투 파울리스타 2025 코린치안스(TM '24/25' → 달력 연도).
- a: TOP 14/15 에레디비시 22골. 요한 크라위프 트로피(2015 유망주)·네이션스리그 득점왕·U21 PL·유럽 U-17 우승·준우승은 넣지 않음. 연맹·선수협회 올해의 팀/선수 해당 없음 확인(에레디비시는 hon 분류 밖).
- 색(integration colors): 기존 같은 클럽 값(psvjs, mund, lyoha, barcou, atgr, corrn).

## 9. 점검
- §16: 중복 0, 같은 날 두 경기 0, 스코어 역순 0, 분 범위, E 날짜 모두 M에 있음, 도움 득점자 이름 있음, NOTE 작업용 표현 0.
- 스크래치 복사본(add_players.py jamesrodriguez + 위 seasonOf 패치): `npm run check` 해당 단계 통과 — 기존 245명 동일, 데파이 추가, 콘솔 오류 0. 합계 527경기 181골 102도움 34,469분, SOC 264.62, 3-peak 31.52, 5-peak 28.66, SOC-CAR 192.49.
- 클럽별 SOC: 리옹 124.31(47%), PSV 48.00, 코린치안스 33.98, 아틀레티코 25.10, 바르셀로나 23.32, 맨유 9.91.
- league_rank_apply 바뀌는 행 0; era·world·second_tier·second_tier_x 출력 dep.js 있고/없고 이동량 차이 0(베네수엘라 2025 새 키 +0). elo_table.js: 선수 246명, 값이 여럿인 팀-시즌 0.
- 고친 것: 같은 경기 판정에서 'Stade' 토큰이 겹쳐 2021.1.9 렌전(데파이 도움 82분 드나예르)이 이카르디 자료의 브레스트 값(1537)을 집던 것을 막음(STOP 단어에 stade·olympique·fc 추가) → 통합표 렌 2020-21 6위 1681.
