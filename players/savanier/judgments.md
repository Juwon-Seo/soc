# 테지 사바니에(Téji Savanier) 판정 기록

자료: `raw/`(2026-11-18 수집, Transfermarkt=TM 선수 경기 성적 API 652행·경기 리포트 196개, FotMob=FM matchDetails 295개·playerMatches 294행, en/fr 위키백과). 빌드: `python3 players/savanier/build_savanier.py` → `src/data/sav.js`, `savanier.json`. 판정 표는 build_savanier.py 상단 상수, 설명 문장은 note_savanier.py.
웹 확인용 임시 파일(기사 원문 캐시)은 스크래치에만 둠(저장소에 넣지 않음).

## 결과
- 470경기 84골(PK 43) 64도움, 35,790분. 기록 148개(골 84·도움 64), 두 경기 합산 기록 0.
- 클럽별(경기·골·도움·분): 아를아비뇽 118·9·5·7751 / 님 132·22·20·10849 / 몽펠리에 210·50·37·16418 / 메스 10·3·2·772.
- 계산기(스크래치 복사본 v1.206 + 사바니에, `npm run check` 통과·기존 185명 동일·콘솔 오류 없음): SOC 142.87, 최고 3시즌 17.07, 최고 5시즌 15.36. 클럽별 SOC 몽펠리에 82.41·님 41.81·아를아비뇽 15.37·메스 3.28.

## 범위
- 1군 공식 경기만. 제외: 몽펠리에 B(CFA·CFA 2 2008~2011, en.wiki 29경기 5골, TM 행은 모두 'not in squad'), 아를아비뇽 B(CFA 2 2013~2015 4경기, en.wiki·FM), 몽펠리에 U19, 프랑스 올림픽 대표팀(TM OLYM 2021 3경기)·FS 1행.
- 소속 팀 시즌: 아를아비뇽 2011-12~2014-15 리그2, 님 2015-16~2017-18 리그2·2018-19 리그1, 몽펠리에 2019-20~2024-25 리그1·2025-26 리그2, 메스 2026-27 리그2. 모두 프로 1·2부 → 제외 시즌 없음.
- 몰수·판정승: 없음. 중단 경기 2개(discrepancies F):
  - 2025-03-16 몽펠리에 0-2 생테티엔(리그1 26R): 63분(자료마다 57/63) 홍염으로 중단, LFP 징계위원회(2025.4.2)가 재개 없이 중단 시 스코어 0-2 확정. 경기장 스코어 = 공식 결과라 그대로(사바니에 63분, 골·도움 없음). 출처 maxifoot article-60848, asse.fr, ligue1.com.
  - 2023-10-08 몽펠리에–클레르몽(4-2에서 중단): 무관중 재경기 2023-11-29 1-1(TM 4094648, 사바니에 90분 1골). 중단 경기는 TM·FM 모두 행 없음 → 재경기만.
  - 2024-10-27 툴루즈전(최루가스로 잠시 중단, 끝까지 진행) 그대로.

## 출전·분(discrepancies A·D)
- TM API played·playedMinutes 그대로 469경기 + 아래 1경기.
- **A1 아를아비뇽 2011-12 21번째 경기 → 넣음**: 1163986 2012-05-11 아를아비뇽 1-0 메스(리그2 37R). TM API 'in squad'이지만 TM 리포트 카드란에 사바니에 90+4분 경고(교체 시간 'Not reported', 아를 교체 2명만 기록). maxifoot 경기 기록(https://www.maxifoot.fr/match/arles-avignon-metz-20120511.htm): "Y. Abdelhamid (T. Savagnier, 46e)", 경고 "T. Savagnier (90+4e)". en/fr.wiki·FM 경력 2011-12 리그 21경기 = TM 20 + 이 경기. 출전 45분(46분 투입). 1150421 2011-09-19 모나코전은 리포트상 벤치 → 넣지 않음.
- A2 아를아비뇽 2012-13·2013-14 FM 경력이 TM보다 1경기씩 적음 → TM(위키 = TM).
- A3·A4·A5 님 2018-19·몽펠리에 2025-26 등: TM = FM, 위키 행 오류/미갱신 → TM. 'in squad' 벤치 행은 FM도 미출전.
- 분: FM playerMatches와 2분 넘게 다른 것 2경기(2021-03-06 알레스 26/28, 2022-08-13 PSG 90/86) → TM.
- 날짜: TM 리포트 날짜 = 파리 현지 날짜(전 경기). 북미 경기 없음.

## 골(discrepancies C)
- TM 84 = 위키 시즌별(en 아를 9·님 22·몽펠리에 50) = FM 경기 이벤트 이름 기준 84(2012-11-17 로슈생주네스트전은 FM 이벤트 없음; fr.wiki 아를 2012-13 시즌 문서 일정표 "80e Savanier" — 시간은 TM 83 사용).
- **C1 2017-04-07 클레르몽 2-3 님**: FM 이벤트만 45분 'Teji Savanier' 골. TM 45분 크리스티앙 쿠아쿠(도움 시소코), maxifoot 경기 기록 "C. Kouakou (45e), C. Kouakou (55e)", FM playerMatches 사바니에 0골, 위키 2016-17 8골 = TM → **골 아님**. 같은 경기 7분 리파르 골 TM 도움은 아래 B2(단일 출처, Midi Libre 1곳) → 뺌.
- **C3 2026-10-17 메스 3-2 소쇼**: FM playerMatches 2골은 10분 아구줄 자책골 포함 → 77분 1골만.
- **PK**: TM penGoals 42 + 2017-09-15 오세르전 50분(TM 일반 골, FM 'penalty', fr.wiki 2017-18 님 시즌 문서 일정표 "{{but|50|pen}}") = 43(PK_FIX). PK 리바운드 골 없음. 놓친 PK 4(2020-11-29 로리앙, 2021-02-21 렌, 2022-03-12 니스, 2026-01-23 바스티아) 영향 없음.
- 분 차이(C4) 1~2분 → TM.
- 자책골로 뺄 골 없음. 연장 골 없음(2014-10-28 랭스전 골은 81분).

## 도움(discrepancies B)
TM 94 → 계산기 64.
- 2014.8.1 전 TM 단독 허용(클로제·인시녜 선례): 5개(2011-10-14 아미앵 소로, 2013-05-17 디종 카세레스, 2013-05-24 르아브르 압델하미드, 2013-09-13 캉 압델하미드, 2014-05-02 크레테유 나바브).
- 2014.8.1 뒤:
  - TM∩FM 경기 이벤트(±3분) 47.
  - TM∩FM 선수 경기 목록 5(이벤트 도움자 빈칸, playerMatches 사바니에 도움 수 = TM, 호드리구·다비드·토뱅 선례): 3047431 2018-08-11 앙제 4' 티우브(B1, TM 'Pass'; 리그1 2018-19 TM 14도움 = fr.wiki '리그1 최다 도움 14'), 3519923 2021-02-10 스트라스부르 88' 슈쿨레티치, 3549067 2021-04-20 카네 루시용 60' 들로르, 4271186 2024-01-24 페녜 올누아 90+2' 애덤스, 4778390 2025-12-19 카네 루시용 76' 망디.
  - **다른 출처 2곳 확인 7개(ADD_CONFIRMED, 넣음)**:

| 경기 | 분·득점자 | 출처 |
|---|---|---|
| 2726318 2016-08-26 님 2-3 아미앵 | 13 알리우이 | Midi Libre 문자중계 "Corner tiré depuis la droite par Savanier sur la tête d'Alioui"(https://www.midilibre.fr/2016/08/26/nimes-olympique-amiens-ligue-2-5e-journee,1384749.php) · Objectif Gard "Des buts et une défaite en plus"(https://www.objectifgard.com/2016/08/26/nimes-olympique-des-buts-et-une-defaite-en-plus/, 검색 요약: 사바니에가 알리우이 머리에 맞춤) |
| 2761183 2016-10-28 발랑시엔 2-3 님 | 65 슬리만 시소코 | Midi Libre "sur le corner de Savanier"(…/2016/10/28/football-ligue-2-nimes-a-battu-valenciennes-3-a-2,1416796.php) · France Bleu "sur un corner de Téji Savanier, Sissoko … de la tête"(https://www.francebleu.fr/sports/football/ligue-2-j13-tres-belle-victoire-du-nimes-olympique-valencienne-3-2-1477693886, 검색 요약) · Objectif Gard "Corner tiré par Téji Savanier, tête rageuse"(검색 요약) |
| 2761208 2016-11-25 님 3-0 랭스 | 29 리파르 | Midi Libre "Savanier offrait une 4e passe décisive en le déposant sur la tête (retournée) de Ripart"(…/2016/11/25/…nimes-olympique-reims,1430937.php) · Objectif Sud/Gard "Tiré par Savanier un beau corner … Renaud Ripart reprend … d'une tête rageuse"(https://www.objectifsud.fr/sports-gard/nimes-olympique/nimes-olympique-le-football-champagne-reussit-aux-crocos-58425.php) |
| 2761460 2017-03-31 님 1-0 발랑시엔 | 27 리파르 | Midi Libre "le ballon distillé par Savanier (sa 8e passe décisive)"(…/2017/03/31/…vainqueur-de-valenciennes…,1486985.php) · France Bleu "un bon corner de Téji Savanier est habilement dévié par Renaud Ripart"(https://www.francebleu.fr/sports/football/ligue-2-j31-le-nimes-olympique-bat-valenciennes-1-0-et-peut-continuer-rever-de-ligue-1-1491003263) |
| 3016475 2018-03-09 오를레앙 1-4 님 | 50 아레크 | Midi Libre "sur un coup franc de Savanier prolongé victorieusement de la tête par Harek (0-3, 50e)"(…/2018/03/09/…orleans-qui-recoit-nimes,1638030.php) · Objectif Gard "On prend de l'élan à Orléans"(https://www.objectifgard.com/2018/03/09/nimes-olympique-on-prend-de-lelan-a-orleans/, 검색 요약: 사바니에 세트피스를 아레크 헤더) |
| 3018817 2018-03-19 브레스트 0-2 님 | 47 브리앙송 | Midi Libre "Briançon, de la tête, coupait la trajectoire du centre de Savanier (0-2, 47e)"(…/2018/03/20/…a-brest-nimes-ne-s-en-laisse-pas-compter-0-2,1642770.php) · Objectif Sud/Gard "Les Crocos ramassent la galette en Bretagne"(https://www.objectifsud.fr/a-la-une/nimes-olympique-les-crocos-ramassent-la-galette-en-bretagne-44475.php, 검색 요약) |
| 3261674 2019-10-30 몽펠리에 3-2 낭시(CdL) | 21 들로르 | ESPN(Opta) 문자중계 "Assisted by Téji Savanier with a through ball following a fast break"(https://www.espn.co.uk/football/commentary/_/gameId/557823) · France Bleu "Coupe de la Ligue : Montpellier se fait peur mais se qualifie contre Nancy"(https://www.francebleu.fr/sports/football/coupe-de-la-ligue-montpellier-se-fait-peur-mais-se-qualifie-contre-nancy-1572472755, 검색 요약: 사바니에가 만든 들로르 골, 몽펠리에 첫 도움) |

  - **개별 판정으로 뺌(EXCL_A)**:
    - 2873562 2017-09-22 님 1-5 니오르 41' 보조크: Objectif Gard "Coup du lapin des Crocos face aux Chamois"(https://www.objectifsud.fr/a-la-une/nimes-olympique-coup-du-lapin-des-crocos-face-aux-chamois-48833.php): "Téji Savanier prend le ballon … stoppé de manière illicite … L'arbitre ne siffle pas, Bozok récupère le ballon, frappe et marque" → 반칙 뒤 흐른 공(패스 아님).
    - 4094792 2024-03-03 몽펠리에 2-2 스트라스부르 71' (B1, TM 노르딘 'Corner'): ESPN(Opta) 문자중계 "Own Goal by Ismaël Doukouré, Strasbourg"(https://www.espn.co.uk/football/commentary/_/gameId/677473), FM 이벤트 도움 없음·playerMatches 0, fr.wiki 2023-24 리그 도움 6(TM 7) → 상대 자책골 유도로 봄. (검색 요약상 worldfootball은 노르딘 헤더·사바니에 도움 — 금지 사이트라 근거로 쓰지 않음.)
  - **다른 출처 2곳을 찾지 못해 뺀 단일 출처 28개(UNCONFIRMED)** — FM 이벤트에 도움 자료가 없는 경기(2014-15 아를, 2015-16·2016-17·2017-18 님), FM playerMatches는 2017.3 이후만 있고 그 기간 도움 0(빈칸과 같음):
    - 아를아비뇽 2014-15: 2014-09-12 투르 37 판케설, 2014-10-28 랭스(CdL, 연장) 102 우아마르, 2014-11-07 발랑시엔 24 투레(maxifoot·livefoot 경기 기록은 득점자만), 2015-05-01 크레테유 45 블랑, 2015-05-15 오를레앙 56 지고.
    - 님 2015-16: 2015-09-22 파리 FC 51 바리용, 2015-09-25 메스 82 시소코(TM 'Ousmane Cissokho'), 2015-12-11 르아브르 86 마울리다, 2015-12-18 라발 20 쿠라, 2016-01-15 클레르몽 7 쿠라·16 무니에(Objectif Gard 기사에 도움 서술 없음), 2016-03-04 부르 43 마울리다. (fr.wiki 2015-16 시즌 문서의 참고 출처가 옛 lfp.fr 경기 기록이라 열 수 없음.)
    - 님 2016-17: 2016-09-20 트루아 52 브리앙송(Objectif Gard 1곳 "un corner joliment tiré par Téji Savanier"; Midi Libre·France Bleu는 서술 없음), 2016-11-25 랭스 88 알리우이(Midi Libre·Objectif Gard 모두 알리우이 개인 감아 차기로만 서술 — 도움 근거 없음), 2017-01-21 랑스 38 시소코(Objectif Gard 1곳 "offre la passe parfaite à Sissoko"), 2017-02-07 니오르 45+1 아주니(Midi Libre 1곳 "Savanier le déposait sur la tête d'Azouni"), 2017-03-17 소쇼 84 브리앙송(Midi Libre 1곳 "consécutif à un coup de pied arrêté de Savanier"), 2017-04-07 클레르몽 7 리파르(Midi Libre 1곳 "Savanier à nouveau au corner, Ripart toujours à la réception"), 2017-04-21 랭스 83 브리앙송, 2017-05-12 AC 아작시오 10 브리앙송·62 리파르.
    - 님 2017-18: 2017-08-08 르아브르(CdL) 90+3 브리앙송, 2017-11-24 부르 62 보조크, 2017-11-28 로리앙 9 아레크, 2017-12-11 클레르몽 43 알리우이(Midi Libre 1곳 "Un premier corner de Savanier est retombé sur la tête d'Alioui"), 2018-02-16 투르 31 알리우이(Midi Libre 문자중계는 내용 없음), 2018-02-23 니오르 36 알리우이(Objectif Gard 1곳 "Téji Savanier sert magistralement le Marocain"), 2018-03-03 파리 FC 90+1 리파르.
    - 단일 출처 1곳이 있는 7개는 사용자 판단에 따라 넣을 수 있음(규칙상 2곳 필요라 뺌).
  - 시도한 출처: Midi Libre(위키백과 시즌 문서 참고 링크로 직접 열기; 문자중계 페이지는 본문이 사라져 빈 경우 많음), Objectif Gard/Objectif Sud, France Bleu(ici.fr), maxifoot 경기 기록(득점자만), ESPN(2015~2018 리그2는 문자중계 없음), footmercato(라인업만). lequipe·sofoot·matchendirect는 접속 차단, fbref·worldfootball 등은 금지라 쓰지 않음. Wikipedia 서술은 Midi Libre를 인용해 독립 출처로 세지 않음.
- 본인 PK 골 본인 도움(B4, 2020-09-15 리옹 38'): TM API도 세지 않음 → 넣지 않음.
- 'Shot on goal'·'Deflected'·PK 유도 도움 없음(TM 유형 B3). FM 단독 도움 없음(B5).
- 득점자 이름 고침: 2761183 65' TM 'Ousmane Cissokho' → FM·Midi Libre·France Bleu·Objectif Gard 모두 슬리만 시소코(SCORER_FIX).
- 합계 비교: TM 94 / FM 경력 75(아를 0·님 37·몽펠리에 36·메스 2) / fr.wiki 83(2025-26까지) / 계산기 64.

## 대회 코드·단판/합산
- FR1·FR2 lg. 쿠프 드 프랑스(3~6라운드·32강·16강)·쿠프 드 라 리그(1~3라운드·16강) dc, 8강 dk(2021-04-20 카네 루시용), 준결승 dsf(2021-05-12 PSG, 골·도움 없음). ko=1.
- 유럽 대회·두 경기 합산 없음(tm_two_leg_ties 0). 연장 2경기(2014-10-28 랭스 CdL, 2014-12-06 리옹뒤셰르 CdF) — 넣은 연장 골·도움 없음(랭스 102' 도움은 미확인으로 뺌). 승부차기 5경기, 리포트 최종 스코어의 승부차기 골은 골 뒤 스코어에 쓰지 않음(tm_events 누적 점검 0 불일치).

## 시즌·클럽
- 클럽 키: arlsv(~2015-08-06), nimsv(~2019-07-02), mtpsv(~2026-08-10), metsv. 경계 = TM 이적일(모든 경기 TM 클럽과 일치 확인).
- 시즌: 네 키 모두 jul10 목록. 이유: 2011-07-22 르망전(CdL 1R)은 TM·아를 리그 시즌 2011-12(E1), 리그2 2016-17·2017-18 개막전이 7월 말(2016-07-29 라발, 2017-07-28 랭스), 2020-08-29 렌전(리그1 2020-21)이 기본 규칙 '2020년 8월 = 2019-20'에 걸리지 않게(테리에 renmt 선례). 메스는 7월 경기 없지만 일관성으로 같은 목록. Elo 시즌 판정도 같은 7월 10일 기준.

## 상대 Elo
- 출처: 팀×시즌 통합표 104, 순위표+순위값 39, 직접 추정 5. 같은 날 같은 상대 다른 선수 기록 0(동료 중 계산기 선수 없음).
- 리그2 20팀 시즌: 기존 `리그2 YYYY-YY N위` 값 중 순위별 최다값 FR2_20 = {1:1669, 2:1624, 3:1603, 4:1582, 5:1574, 6:1567, 7:1559, 8:1550, 9:1540, 10:1532, 11:1526, 12:1521, 13:1516, 14:1513, 15:1508, 16:1500, 17:1490, 18:1484, 19:1480, 20:1469}(동수였던 16·17·20위는 1540+51.24×곡선 정수값 쪽). 18팀 시즌(2025-26·2026-27): int(1540+51.24×곡선(r,18)) — 기존 '리그2(프랑스 2부) 2024-25 4위 1578'과 같은 식. 2026-27은 '(11월 중순 현재)'.
- 리그1: 통합표에 모두 있음(리그1 순위값 모형 사용 0).
- 순위: raw/ranks.txt(TM 최종 순위표). 리그2 우승 팀 확인: 2011-12 바스티아, 2012-13 모나코, 2013-14 메스, 2014-15 트루아, 2015-16 낭시, 2016-17 스트라스부르, 2017-18 랭스, 2019-20 로리앙, 2025-26 트루아(TM 표). 리그1·리그2 2019-20(중단)은 경기당 승점 최종 순위.
- 직접 추정(MAN): 로슈생주네스트 2012-13 1000(fr.wiki Coupe de France 2012-2013: "FC Roche St-Genest (D8)", PHR), 카네 루시용 2020-21 1220(N2 D조 12/16, 시즌 조기 중단)·2025-26 1150(N3, TM FR5A 2/14), 앙드레지외부테옹 2021-22 1220(N2 D조 4위), 페녜 올누아 2023-24 1220(N2 D조 8/14). (통합표의 'Feignies Aulnoye 2021-22 1150'은 다른 시즌.)
- 스크래치 복사본 `node tools/elo_table.js`: 값이 여럿인 팀-시즌 0.

## 다른 선수 자료 대조(다른 파일 수정 없음)
- 동료로 겹치는 계산기 선수 없음(델로르·라보르드·와히·지냑은 계산기 밖이거나 겹침 없음; 아를아비뇽 2011~2015에 카벨라 없음 — 카벨라 아를 임대는 2010-11).
- 상대가 사바니에 소속팀인 같은 날 다른 선수 기록 83개(음바페·네이마르·메시·파예·페페·테리에·토뱅·마레즈 등): 대회 코드 모두 같음.
- 병렬 판정(이코네): 공유 가능 경기는 사바니에 팀 대 이코네 팀(릴 2018-19~2021-22 등) 경기라 상대 Elo는 서로 다른 팀 값. 사바니에 쪽 릴전 기록: 2018-12-16 님–릴(리그1, 사바니에 기록 1개, 상대 릴 2018-19 1872 '리그1 2018-19 2위'). M 행: 2018-12-16·2019-04-28(님), 2019-12-13·2021-04-16·2021-08-29 등(몽펠리에) 모두 lg.

## 수상(hon)
- TM 업적 페이지: '1x Olympics participant 20/21'(대표팀) 뿐 → 클럽 우승·수상 없음, hon 빈 값.
- 넣지 않은 것(규칙상): 리그2 준우승 2017-18(님, 리그 준우승은 기존 자료에 항목 없음), UNFP 리그2 올해의 팀 2017-18(fr.wiki Trophées UNFP 2018 'équipe type de Ligue 2' 미드필더 사바니에 — 2부 XI는 기존 자료에 없음), UNFP 리그1 이달의 선수 2021.12, 리그1 최다 도움 2018-19(14). UNFP 리그1 올해의 팀: fr.wiki 2019·2021~2026 문서에 사바니에 없음(2019·2022·2024 문서는 '올해의 골' 후보만).
