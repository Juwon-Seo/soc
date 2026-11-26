# 이강인 (Lee Kang-in) 판정 기록

Transfermarkt 557149 · FotMob 940976 · 프리셋 `leekangin` · 접두어 `LKI` (`lki.js`; src/data에 lki.js 없음, `LKI_` 상수 없음 확인) · 자료 기준일 2026-11-25 · 현역(아틀레티코 마드리드).
재현: `python3 players/leekangin/build_leekangin.py` (설명 문장은 note_leekangin.py, 요약 `--stat`, Elo 출처 `--debug`).
결과: **275경기 28골(PK 1) 31도움, 14,595분**, 기록 59행. 발렌시아 62·3·4, 마요르카 73·7·10, PSG 124·16·16, 아틀레티코 16·2·1.

## 1. 범위
- 성인 1군 공식 경기 275경기(Transfermarkt 선수 경기 성적 = 영어·스페인어 위키백과 = FotMob 경력 합계, 클럽·시즌·대회별 경기·골 모두 같음).
- 제외: 발렌시아 메스타야(2군, 세군다 B) 26경기 4골 2도움(2군 선례), 발렌시아 U-19 UEFA 유스리그 3경기 1골(유소년), 친선경기, 대표팀.
- 클럽 경계(discrepancies J): Transfermarkt 이적일 메스타야→발렌시아 2019-01-30이지만 1군 경기는 2018-10-30 코파 델 레이 에브로 원정부터 있음 → 실제 1군 경기 기준으로 발렌시아 경력 시작(첫 행 2018-10-30). 클럽 함수 경계는 2021-08-30 마요르카, 2023-07-08 PSG, 2026-07-25 아틀레티코(TM 이적일, 경계와 경기 클럽 모두 일치 확인).

## 2. 출전 분
- TM playedMinutes 그대로(90분 추정 0). 퇴장 경기는 선례(퇴장 경기 API 분)대로 TM 값: 2019-10-19 아틀레티코전 77분 투입·90+1분 퇴장 13분, 2020-06-18 레알 마드리드전 76분 투입·89분 퇴장 14분, 2021-10-23 발렌시아전 54분 경고 누적 54분.
- 2025-08-13 UEFA 슈퍼컵 토트넘전: 연장 없이 승부차기, 67분 투입 23분(TM). 
- FotMob 분: 마요르카·아틀레티코 동일, PSG 6379 vs 6384, 발렌시아는 FotMob 분 없는 3경기 → TM 유지.

## 3. 골
- TM 28골 = FotMob 28골(26경기, 시각·PK 모두 같음). PK 골 1: 2025-06-15 클럽 월드컵 아틀레티코전 90+7분.
- 본인 자책골 2022-04-16 엘체 원정 81분(TM actionId 206·FotMob 자책골) → 골 아님(discrepancies G).
- 메스타야 골(2018-05-06 사바델, 09-08 코르네야 PK, 10-27 알코야노, 12-16 온티녠트)·U-19 골(2018-10-23 영 보이스)은 범위 밖.

## 4. 도움 (TM 31개 모두 넣음)
- TM+FotMob 경기 이벤트 일치 29개 → 넣음. 이 중 2021-10-23 발렌시아전 32분 앙헬 로드리게스(TM 유형 칸 빈칸)는 FotMob이 이강인 도움 → 넣음(A3).
- **2025-11-04 챔스 바이에른전 74분 주앙 네베스**(discrepancies B): TM(크로스)·FotMob 경기 이벤트(assistStr 이강인) 일치 → 표준 규칙 충족, 넣음. FotMob 선수 경기 기록 숫자만 0(내부 집계 차이, 설명에 적음).
- **2021-12-16 코파 델 레이 야네라 0-6 마요르카 74분(0-3→0-4) 가야**(A1, TM 단독, 유형 빈칸): 
  - 라리가 공식 경기 페이지 중계 기록: "Josep Gayá (Mallorca) remate de cabeza desde muy cerca … Asistencia de Lee Kang-In con un centro al área tras un saque de esquina." https://www.laliga.com/partido/temporada-2021-2022-copa-del-rey-ud-llanera-rcd-mallorca-2
  - 울티마 오라 경기 기사: "…a los 73 minutos gracias a otro saque de esquina. Kang In sirvió el lanzamiento al corazón del área pequeña y ahí Gayà remató otra vez a placer." https://www.ultimahora.es/deportes/real-mallorca/2021/12/16/1679841/copa-del-rey-llanera-mallorca.html
  - 코너킥 크로스 = 일반 도움. 다른 출처 2곳(리그 공식 경기 기록 + 지역지 기사) 확인 → **넣음**. (FotMob 선수 경기 기록도 도움 1, 마요르카 공식 기사는 도움자 언급 없음.)
- **2023-01-07 마요르카 1-0 바야돌리드 90+4분 아브돈 프라츠**(A2; TM 이강인 크로스, FotMob 마페오):
  - 울티마 오라 경기 기사: "Abdón convertía en oro molido un centro de Kang In Lee … Una falta provocada por Kenedy le brindaba una última ocasión para sacarse una asistencia de la chistera y su centro desde la derecha lo cabeceaba Abdón". https://www.ultimahora.es/deportes/real-mallorca/2023/01/07/1859219/real-mallorca-real-valladolid-resumen-del-partido-primera-division.html
  - EFE 기사(온다 바스카 게재): "sacó una falta cometida por Kenedy y Abdón, con un efectivo remate de cabeza, firmó el triunfo" (주어 Kang In Lee). https://www.ondavasca.com/abdon-da-la-victoria-al-mallorca-en-el-93/
  - TUDN: "Lee Kang-in cobró un tiro libre de costado y Abdón Prats … puso de cabeza el tanto". (EFE와 내용이 비슷해 독립 출처로 세지 않음.)
  - 반대: FotMob·ESPN 'Assisted by Pablo Maffeo following a set piece'. 
  - 판정: TM + 독립 기사 2곳(울티마 오라, EFE)이 이강인 프리킥→아브돈 헤더 직접 연결로 적음 → **넣음**, 설명에 FotMob·ESPN 차이 기록.
- 제외할 유형(PK 유도·Shot on goal·굴절·상대 자책골·핸드볼) 도움 없음(discrepancies AUTO 7 빈칸). FotMob 단독 도움·골 없음.
- 메스타야 도움 2개(2018-08-25 에브로, 09-23 올로트)는 범위 밖.
- es.wikipedia 도움 합계(28)와의 차이(마요르카 2022-23 6 vs 7 = 바야돌리드 도움, PSG 2024-25 4 vs 6, 2025-26 리그 5 vs 4·챔스 0 vs 1)는 출처 집계 차이로 보고 경기 단위 판정을 따름.
- 확인 못 한 도움: 없음.

## 5. 대회 코드·합산
- 라리가·리그1 `lg`. 코파 델 레이·쿠프 드 프랑스: 1·2·3라운드·32강(intermediate)·16강·5·6라운드 `dc`, 8강 `dk`, 준결승 `dsf`, 결승 `df`. 트로페 데 샹피옹·UEFA 슈퍼컵 `df`(뎀벨레·바르콜라와 같음). 클럽 월드컵 2025·인터콘티넨털컵 2025 `cwc`(조별 ko 0, 16강부터 ko 1; 크바라츠헬리아·뎀벨레와 같음). 챔스 조별/리그 페이즈 `clg`, 녹아웃 PO·16강 `cl16`, 8강 `clk`, 준결승 `clsf`. 유로파 32강·8강 `elk`.
- 같은 경기 다른 선수 출전 행과 대회 코드 다름 0건.
- 합산: 기록 행 중 2차전 1행(2024-03-05 챔스 16강 레알 소시에다드 원정, 1차전 2-0, 원정 다득점 없음·연장). 코파 델 레이 2018-19 두 경기 합산(원정 다득점·연장, 선례)에는 골·도움 없음.
- 연장: 2021-12-01 세고비아나, 2023-01-04 폰테베드라(골·도움 없음).

## 6. 날짜
- TM 현지 날짜 = FotMob 날짜(전 경기). 클럽 월드컵 2025 미국 현지 날짜(보타포구전 2025-06-19, UTC 06-20 01:00). 2025-02-11 브레스트 홈(갱강 개최) 그대로.

## 7. 상대 Elo·라벨
- 출처: 같은 경기 다른 선수 자료 30행, 기존 팀×시즌 값 27행, 순위표 → 새 라벨 2행. 라벨→값 재계산 차이(TABLE_DIFF) 0.
- 새 팀×시즌:
  - Yeclano Deportivo 2020-21: `스페인 3부 2020-21 9위/10팀 (Segunda División B Grupo IV (Subgrupo B), 경기 날짜에 진행 중이던 단계 순위, 리그 수준 추정)` = 1247 (TM ES3D 2020 표 subgroup B 9/10; 2021-01-07 1단계 진행 중, 1단계 최종 순위; 코르도바 같은 시즌 라벨과 같은 형식).
  - UD Llanera 2021-22: `스페인 4부 2021-22 16위/18팀 (Segunda Federación Grupo I, 리그 수준 추정)` = 1073 (TM E4G1 2021 표).
- 라리가 2026-27 라벨(말라가 20위, 세비야 6위, 오사수나 '16위 (10월 중순 현재)')은 같은 경기 다른 선수(훌리안 알바레스 등) 라벨 그대로 — 새 진행 중 시즌 라벨은 없음.
- 클럽 월드컵 2025 아틀레티코 = 라리가 2024-25 3위(기존 값), 인터콘티넨털컵 플라멩구 = 브라질 세리에 A 2025 1위/20팀(kva.js 같은 경기).

### 승점 표 map 추가 필요
- `스페인 3부 2020-21 | Yeclano Deportivo | Yeclano | 0,8` (표 'First phase > Group 4 > Subgroup 4B' 9번째 행, 18경기 2승 5무 11패 13-27).
- (참고) `스페인 4부 2021-22`는 표에 Group 4·5만 있어 Llanera(Group 1)는 map 불가 → 순위 곡선 값 그대로.

## 8. 다른 선수와 대조
- 같은 경기 공유: 바르콜라 107, 뎀벨레 90, 두에 69, 크바라츠헬리아 51, 가메이로 46, 음바페 29, 루크먼 14, 훌리안 알바레스 12, 조너선 데이비드 10경기.
- 도움↔골 대조 모두 일치: 이강인→바르콜라(2024-11-09 45+2, 2026-02-28 37), →뎀벨레(2025-01-12, 2025-02-01), →음바페(2024-03-05 챔스); 뎀벨레→이강인(2024-01-03 트로페 3분), jdv.js→이강인(2026-09-16 오사수나 54분). 같은 경기 Elo·lv·대회 차이 0.
- 이번 회차 병렬 판정과 같은 경기(라벨은 rank_apply로 같은 팀×시즌 같은 값):
  - 모라타(아틀레티코): 2019-10-19 발렌시아-아틀레티코, 2022-11-09 마요르카-아틀레티코, 2023-04-26 아틀레티코-마요르카(모라타 골).
  - 엔네시리(레가네스·세비야): 2019-09-22 레가네스전, 2020-07-19 세비야전, 2021-01-27 코파 델 레이 세비야전, 2022-10-15 세비야전, 2023-02-11 세비야전(엔네시리 골). 이강인 기록 행 상대 세비야는 2026-08-29(라리가 2026-27 6위, jal.js 같은 경기 값)뿐.
  - 미트로비치·히메네스: 같은 경기 없음.

## 9. 우승·수상 (TM 업적 페이지, 1군 기록 있는 시즌)
- 챔스 2024-25·2025-26(결승 둘 다 벤치), 리그1 2023-24·2024-25·2025-26, 쿠프 드 프랑스 2023-24·2024-25(2024-25 결승 벤치), 트로페 데 샹피옹 2023-24·2024-25, UEFA 슈퍼컵 2025-26, 인터콘티넨털컵 2025-26(hon 키 CWC, 뎀벨레·바르콜라와 같은 표기), 코파 델 레이 2018-19(발렌시아; 32강·16강·8강 출전, 준결승 명단 제외·결승 결장).
- 트로페 데 샹피옹 2025-26은 TM 업적에 이강인 항목이 없어 넣지 않음(뎀벨레 등은 있음 — 이강인 출전 기록 없음). 
- 넣지 않음: 클럽 월드컵 2025 준우승, 아시안게임 금메달·U-20 월드컵 골든볼(대표팀), 개인 수상 없음(UNFP 올해의 팀 없음).

## 10. 점검
- §16 점검 문제 0(중복·같은 날 두 경기·E 날짜 M에 있음·스코어 순서·도움 득점자·출전 분 범위).
- 스크래치 복사본: add_players(앵커 barella) → build → verify check: 기존 301명 동일, 이강인 추가, 콘솔 오류 0. league_rank_apply --apply 바뀌는 행 0, 리그 도구 4개 이동 0(챔피언십 2026-27 −1은 기존 행, ±1 범위), elo_table 값이 여럿인 팀-시즌 0.
