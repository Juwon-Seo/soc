# 후안 마타 (Juan Mata, TM 44068 · FotMob 41468) — 판정 기록 (2026-11-21)

재현: `python3 players/mata/build_mata.py [--out <data 폴더>]` → `players/mata/mat.js`(기본, src/에는 쓰지 않음), `players/mata/mata.json`(최종 행·판정·동료 대조·Elo 출처·새 팀×시즌). `--debug` Elo 출처, `--stat` 요약, `--ties` 합산 행. 스크래치 복사본에서는 `SOC_ROOT=<복사본> ... --out <복사본>/src/data`. `MATA_CASTILLA=1`이면 카스티야 포함판(1절).
황희찬 build 스크립트(같은 수집 형식)를 바탕으로 함. 보조: `assist_checks.py`(2014.8 이후 단일 출처 도움 웹 확인), `man_elo.py`(순위표 밖 상대 — 없음), `note_mata.py`(설명).
결과: **661경기 139골(PK 11) 154도움, 43,715분**, 기록 293행(합산 32행/23경기). 접두어 MAT(src/data·index.html에 없음 확인), 프리셋 `mata`, 은퇴(2026.11.18 발표, 마지막 경기 2026.5.2).

## 1. 범위·클럽 — 카스티야 제외(지시와 다름, 확인 요청)
- 지시문은 "Real Madrid Castilla 2006-07(세군다) — 프로 클럽 구간으로 넣기"였으나, 사용자 규칙(v1.159 "Reserve/youth teams stay excluded as before")과 선례가 모두 2군 제외: 라울(카스티야 2부 1경기 제외), 카예혼(카스티야 2006-07 세군다 4경기 제외), 외데고르·발렌시아 등. 그래서 **기본은 제외**(TM 38경기 9골 0도움 2,766분). `MATA_CASTILLA=1`로 빌드하면 포함판(699경기 148골 154도움 46,481분, Elo 새 팀-시즌에 세군다 2006-07 7개 추가; integration.json에 `rmcmt` 클럽(until 2007-07-18, 색 rmv와 같은 #FFFFFF/#FEBE10/#00529F)과 NOTE 문장을 바꿔야 함). 오케스트레이터/사용자 결정 필요.
- 카스티야 경기 수 차이(TM 38 vs en/es 위키 39, FotMob 39·10골): 제외하므로 영향 없음(NOTE에 기록). 포함하게 되면 TM 38경기(1경기는 TM '명단만')를 씀.
- 그 밖은 TM performance-game 성인 클럽 played 661경기 전부. 대표팀(A·U-21·U-20·U-19·올림픽) 제외, FotMob 선수 경기 목록의 친선·ICC 13경기 제외(discrepancies §6; 2017.8.2 삼프도리아 친선 골 포함).
- 프로 리그 규칙: 라리가·PL·쉬페르리그·J1·A리그 Men(프로, 승강 없음) 모두 1부 → 제외 시즌 없음.
- 위키백과 대조: 카스티야를 빼면 클럽·시즌·대회 범주별 경기·골이 en.wiki와 전부 같음(tm_vs_wiki.csv). en.wiki는 A리그 파이널 시리즈를 Other로 셈.
- 클럽 키(미사용 확인): valmt chemt mnumt galmt kobmt wswmt mvcmt(카스티야 포함 시 rmcmt). 경계(TM 이적일): 2011-08-24 / 2014-01-24 / 2022-09-08 / 2023-09-03 / 2024-09-05(무소속 2024.2~9) / 2025-09-16. 빌드가 모든 경기의 TM 클럽 id와 경계를 대조(불일치 0).
- 시즌: calendar = kobmt(J1 2023, 1경기 2023.9.16 → "2023"; 갈라타사라이 2022-23과 다른 시즌). 나머지 8월 1일(7월 경기 없음). 특수 seasonOf 분기 필요 없음.
- 포지션 AM, 국기 ES(있음), retired true.

## 2. 출전·분·날짜
- TM playedMinutes 그대로(빈칸 0, 90분 추정 없음). 퇴장 1(2016.3.6 웨스트브롬 26분).
- 날짜: TM 일정 날짜 = API UTC → 경기장 시간대 변환 날짜, 661경기 모두 같음(raw §8). 원정 유럽 대회 57경기는 클럽 시간대로 바꿨지만 모두 유럽 저녁 경기라 일정 날짜와 같음. 2012 클럽 월드컵(일본, 낮·저녁)·J1·A리그도 현지 날짜.
- 승부차기 경기 5(2012 챔스 결승 120분, 리그컵 더비·로치데일, 2021 유로파 결승 1분, 2022 FA컵 미들즈브러): TM 출전 분 그대로.

## 3. 골 (TM 139 = 사용 139, PK 11)
- 리포트 골 = API 골(경기마다), PK = API penGoals. 자책골 0. PK 리바운드 골 0.
- FotMob 대조(2010-11 이후 90경기 99골): 수·순서·PK 같음. 2011.9.13 레버쿠젠전 90+1분 골은 FotMob 90분·'Juan M. Mata' 표기라 자동 짝맞춤이 실패했을 뿐 같은 골(ESPN 90+2' Juan Mata, 토레스 tor.js 도움 행 91분과 같음). 2023.1.13 하타이스포르전 45+4·45+6 두 골은 FotMob과 같음(raw §5의 스코어 차이는 짝 어긋남).
- FotMob 경기 기록 없는 골(2010-11 전·2010-11 발렌시아 stub 3골): ESPN 135/138 확인. ESPN이 득점자를 적지 않은 3골 — 2011.8.27 노리치 90+1(FotMob 시대, en.wiki 데뷔골), 2008.4.16 코파 결승 헤타페 4분(다비드 실바 sil.js 도움 행과 같음), 2008.9.21 오사수나 79분(비야 vil.js 도움 행과 같음) — 유지.
- 시각은 TM 추가시간 표기(FotMob 90/45만 적은 경우).

## 4. 도움 (TM 166 → 154)
- 제외 12: PK 유도 6(2009.2.1 알메리아·4.12 히혼·4.19 세비야 비야, 2009.11.5 슬라비아 호아킨, 2016.10.20 페네르바체·2019.4.13 웨스트햄 포그바), 'Shot on goal' 3(2008.5.18 아틀레티코·2008.10.26 레크레아티보 비야, 2013.9.24 스윈던 토레스), 상대 자책골 유도 2(2010.10.30 사라고사 란사로, 2012.12.13 몬테레이 차베스), 2014.8 이후 미확인 1(아래). 본인 PK 골 본인 도움(2019.1.5 레딩 22분) API 0 → 셈 안 함. 3050519 웨스트햄 TM API 'assistsOfficial' 0 = PK 유도 제외와 같음.
- 2014.8 전(100개 남음): TM 단일 출처 허용(선례). FotMob·ESPN 둘 다 마타 표기 없는 것 포함(raw §3: 2010 전 38개 등). 유형 빈칸 5개는 일반 도움.
- 2014.8 이후: TM+FotMob 이벤트(±2분) 52개(+ 아래 확인 2개 = 2014.8 이후 54개). TM 단독 3개 판정(assist_checks.py, WebSearch/curl 2026-11-21):

| 경기 | 판정 | 근거 |
|---|---|---|
| 2015.8.26 챔스 PO 브뤼헤 원정 57 루니(해트트릭 골) | 넣음 | UEFA.com 경기 기사("calmly slotted his hat-trick goal after Juan Mata slid in the No10", curl 확인) + Sports Mole/Sky Sports 경기 기록(마타 도움, 검색 요약). roo.js·dep.js 같은 경기 값 같음 |
| 2016.5.17 본머스 43 루니 | **뺌** | FotMob 이벤트·ESPN 모두 마시알 도움. roo.js 43분 골 행은 도움자 표기 없음(영향 없음) |
| 2022.11.8 튀르키예컵 오프스포르 79 베르칸 쿠틀루 | 넣음 | 파나틱 문자 중계("79' Juan Mata'nın yerden bıraktığı topa ... Berkan, ağları sarstı", curl 확인) + haberler.com 경기 기사(베르칸 헤더 → 마타 → 베르칸 슛, curl 확인). FotMob 이벤트 도움자 없음, ESPN 경기 없음 |

- FotMob 전용 도움: 2010.11.2 레인저스 71분 솔다도 = TM 63분 마타 도움과 같은 골(시각 차이). Sky Sports·FotMob 71분, UEFA 경기 기사 "wall pass with Mata to make it 2-0" → **71분으로 고침**(MIN_FIX, 스코어 2-0 전 1-0 같음). 그 외 FotMob 전용 도움 없음.
- 멜버른 빅토리 2025-26: TM 12 vs FotMob 경력·en.wiki·PFA 기사 13. 2026.3.15 맥아서전 FotMob 선수 경기 목록 2도움이지만 FotMob 이벤트는 63분 에스포지토 1개만 마타 도움, 11분은 다 시우바 자책골(도움자 없음) → 12(자책골 유도는 도움 아님).
- discrepancies §9 풀럼 2012.11.17 테리 골: TM·FotMob 모두 토레스 도움 → 마타 도움 아님.

## 5. 대회 코드·합산
- lg: ES1 GB1 TR1 JAP1 AUS1(ES2는 카스티야 포함 때만).
- 국내컵 CDR FAC CGB TRP: 결승 df / 준결승 dsf / 8강·FA컵 6라운드·6라운드 재경기('6th round deciders')·'Quarter-Finals' dk / 나머지 dc(FA컵 4·5라운드 재경기 포함). 비야 vil.js 발렌시아 2007-10 코드와 같음.
- SUC(2008 수페르코파 두 경기)·GBCS·USC df. KLUB(2012 클럽 월드컵 준결승·결승) cwc. AUSF(A리그 파이널 시리즈): 2025.5.10 TM 'Quarter-Finals' = 엘리미네이션 파이널, 2026.5.2 TM 'Semi-Finals Deciders' = 엘리미네이션 파이널(AAP·멜버른 빅토리 구단 기사 "Victory held out in Elimination Final", 시드니 FC 1-0) → 둘 다 mlp(델 피에로 선례), 골·도움 없음.
- UEFA컵 2008-09: 1라운드 elq, 조별 elg, 3rd round(32강) elk — 비야 선례. EL: 조별 elg, 2009-10 'Second Round'·'intermediate stage'(32강)·16강·8강(2020.8 단판 포함) elk, 준결승 elsf(2020.8 단판 포함), 결승 elf. CL: clg/cl16/clk/clsf/clf. CLQ clq, ELQ elq.
- 합산 (원정 다득점, 연장): CL·EL·CLQ·ELQ·UEFA 2021-07 전 (1,1) — 마타 두 경기 승부는 모두 2020-21 이전; CDR·SUC (1,1); CGB 준결승 2018-08 전 (1,1), 이후 (0,0)(2020 맨시티 준결승은 G/A 없음). 다른 차전 스코어는 TM 리포트(tm_two_leg_ties.csv). 합산 32행/23경기.
- 연장 골·도움 없음(연장 6경기의 G/A는 모두 정규시간). 챔스 결승 2012 88분 드로그바 동점골 도움(clf, ko1) — dro.js와 Elo·lv·분·스코어 같음.

## 6. 상대 Elo (293행: 같은 경기 203 / 통합표 66 / 순위표 → 라벨 24, man_elo 0)
- 순서: 같은 경기 다른 선수 자료(git 추적 파일만) → 통합표 → raw/ranks.txt 라벨(값은 tools/league_rank_apply.py value()). 통합표 값과 라벨 계산 값 차이 0(TABLE_DIFF 없음).
- 같은 경기 매칭에서 A리그·J1은 정확한 이름(별칭)만 맞춤(시드니 FC/웨스턴 시드니, 멜버른 시티/빅토리 혼동 방지).
- **새 팀×시즌 15개**(G/A 행이 있는 것만):
  - Birmingham City 2011-12 챔피언십 4위/24팀 1589 (FA컵)
  - Shrewsbury Town 2015-16 잉글랜드 3부 20위/24팀 (EFL League One, 리그 수준 추정) 1366 (FA컵)
  - Ofspor 2022-23 튀르키예 4부 16위/17팀 (TFF Third League Group 2, 리그 수준 추정) 950 (튀르키예컵; TM TR4B 표, 카흐라만마라슈스포르 기권 17위)
  - A리그(라벨 '호주 1부 YYYY-YY N위/M팀 (A-League Men)', 이니에스타 2021-22 형식; 정규 리그 최종 순위, TM 표와 FotMob 표 순서 같음): 2024-25(13팀) Sydney FC 7위 1270, Macarthur FC 8위 1261, Central Coast Mariners 10위 1245, Brisbane Roar 12위 1216; 2025-26(12팀) Adelaide United 2위 1372, Sydney FC 5위 1308, Melbourne City FC 6위 1289, Macarthur FC 7위 1277, Wellington Phoenix 8위 1267, Central Coast Mariners 9위 1260, Perth Glory 10위 1243, Brisbane Roar 11위 1229.
  - G/A 없는 M 행만의 상대(PSV 2015-16, 위건 2016-17, 더비 2019-20, 왓퍼드 2020-21 등)는 Elo가 필요 없어 만들지 않음.
- 기존 A리그 라벨(델 피에로·더프·나니 '호주 A리그 … (추정: 1위 1450~꼴찌 1350 직선)')은 다른 시즌이라 겹침 없음.
- 정규화 도구(스크래치, --apply 후 mat.js 비교): league_rank_apply 바뀌는 행 0, league_era_normalize·league_world_normalize(AUS 2025·2026 +0)·league_second_tier·league_second_tier_x 모두 mat.js 변화 0. elo_table.js: 선수 251명, 값이 여럿인 팀-시즌 0.

## 7. 동료 자료 대조 (수정 없음)
- 마타 골 ← 동료 도움, 마타 도움 → 동료 골: vil 15, tor 13, sil 11, ras 11, joa 8, haz 6, lam 6, luk 6, roo 6, dro 5, van 4, dim 3, ayo 2, ibr 2, mld 2, val 2, dep 1, grw 1, hdz 1, vic 1 — 모두 날짜·분(±2)·스코어·대회·Elo·lv 같음.
- 대조 도구 표시 중 오검출: luk.js 2017.12.5 CSKA(64분 루카쿠 골과 66분 래시퍼드 골 짝 — ras.js 66분 1-1과 같음), ras.js 2020.1.11 노리치(52분 래시퍼드 PK와 54분 마시알 골 짝), del.js 2013.2.2 'Newcastle United'(뉴캐슬 제츠와 이름 겹침), TM 제외 도움 vs 다른 골(tor.js 2012.12.13 46분 토레스 골 ≠ 48분 자책골).
- 마타가 뺀 TM 도움에 해당하는 동료 골 행: vil.js(비야 PK·리바운드 5), joa.js(호아킨 PK), tor.js(스윈던 리바운드), roo.js(본머스 43분 — 도움자 표기 없음) — 다른 선수 파일은 득점 행이라 영향 없음.
- 이번 차례 병행 선수와 겹칠 수 있는 경기: 나스리(아스널·맨시티 2008-17, 웨스트햄 2019)·샤키리(스토크·리버풀 2015-20)와 PL 맞대결, 큐얼(리버풀 2003-08: 발렌시아 2007-08 챔스 조별은 첼시·샬케·로젠보리라 리버풀 없음; 갈라타사라이 시기 다름). 다른 판정 결과는 읽지 않음. 공유 경기의 상대 Elo는 모두 통합표/기존 같은 경기 값.

## 8. 우승·수상 (TM 업적 raw/tm_honours.html, en.wiki Honours)
- t: UCL 11/12 첼시; UEL 16/17 맨유·12/13 첼시; LG 2023 비셀 고베(1경기 10분 출전, TM 목록대로 — 확인 요청)·22/23 갈라타사라이; DC 2016 맨유·2012 첼시(FA컵)·07/08 발렌시아(코파); LC 2017 맨유; SC 16/17 맨유(커뮤니티 실드).
- a: AST 12/13 프리미어리그·12/13 첼시(TM '2x Best assist provider', 메시·벤제마 등 클럽 표기 선례대로 둘 다); XI 12/13 프리미어리그 · PFA(선수협회)(en.wiki PFA Team of the Year (2010s) 2012-13 확인); XI 25/26 A리그 · PFA(선수협회)(PFA 호주 2026.5.19 "Devenish, Meares captain star-studded PFA A-League Men Team of the Season" — 마타 미드필드 선발, curl 확인); POY 25/26 A리그 · 사무국(조니 워런 메달, A리그 공식 시상 — AAP·멜버른 빅토리·Flashscore 보도). **페이지의 '표기' 설명 문단에 A리그(조니 워런 메달·PFA 호주)가 아직 없음 — 넣을지와 설명 문구 추가 결정 필요.**
- 넣지 않음: 준우승(클럽 월드컵 2012, FA컵 2017-18, 유로파 2020-21), 대표팀(월드컵 2010, 유로 2012, U-21·U-19), 구단 상(첼시 올해의 선수 2012·2013, 빅토리 시즌 선수), PL 이달의 선수(2012.10), A리그 도움 1위(TM 목록에 없음; 공식 13 vs 이 자료 12).
- 색(integration colors): valmt=valvl, chemt=che 계열, mnumt=mnutv, galmt=gal 계열, kobmt=kobvl, mvcmt=melnn(나니 멜버른 빅토리) 기존 값. wswmt 새 값 #E2231A/#000000/#FFFFFF(en.wiki "club colours are red and black", 홈 빨강·검정 가로줄, 흰 바지).

## 9. 점검·확인 못 한 것
- §16: 중복 0, 같은 날 두 경기 0, 스코어 역순 0, 분 범위 0, E 날짜 모두 M에 있음, 도움 득점자 이름 있음, NOTE 작업용 표현 0.
- 스크래치 검증: add_players(hwangheechan 앵커) → build → verify check 통과(기준 250명 동일, 후안 마타 추가, 콘솔 오류 0).
- 확인 요청: (1) 카스티야 제외(지시와 다름), (2) J1 2023 우승 포함, (3) A리그 개인상 두 항목과 hon 설명 문구, (4) 원래 Sports Mole/Sky Sports 본문은 curl로 직접 못 읽고 검색 요약만 씀(UEFA.com은 직접 확인).
