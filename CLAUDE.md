# 클럽 SOC 계산기 (축구력 계산기) — Claude Code 작업 규칙

축구 선수의 클럽 경력 SOC(축구력)를 계산하는 단일 페이지 계산기. 답변은 **한국어**로 한다.
현재 **v1.306**, 수록 **320명**(마지막으로 추가된 선수: 에네르 발렌시아). 국가대표 SOC 계산기와는 별개 프로젝트이며 디자인·데이터 처리 규칙을 섞지 않는다.

## 저장소 구조

```
src/index.html      화면·계산 코드 (약 246KB). 본문 <script> 앞에 <script src="data/xxx.js"> 323개
src/data/xxx.js     선수 1명당 파일 1개 (XXX_E·XXX_M·XXX_NOTE 상수) 320개 + hon.js(HON_DATA 우승·수상) + clubcolors.js(CLUB_COLORS 클럽 상징 색, v1.227) + finals.js(FINALS 경기 최종 스코어, 결승골·최종 동점골 표시용, v1.257)
tools/build.py      dist/ 만들기: club-soc.html(단독 실행) · club-soc.artifact.html(게시용 한 파일, gzip 압축본) · club-soc.packed-test.html(압축본 시험용) · dev.html
tools/verify.js     playwright 검증: snap(스냅숏) / cmp(비교) / check(한 번에)
tools/unbundle.py   프로젝트의 *_bundle.b85.txt 원자료 묶음을 players/<선수>/ 로 풀기
tools/add_players.py  새 선수를 index.html·hon.js 에 넣는 패치(integration.json 사용)
tools/final_scores.py  경기 최종 스코어 수집(TM performance-game API) → src/data/finals.js. 선수별 인자는 tools/final_scores_specs.txt(프리셋id:접두어:TM선수id, 320명)
tools/league_points.py  승점·득실 간격(5대 리그 elo/league_points_big5.json, 다른 리그 elo/league_points_other.json, league_rank_apply가 불러 씀, v1.288·v1.290)
tools/elo_table.js  src/data 에서 상대 Elo 팀×시즌 통합표 만들기(npm run elo → elo/)
elo/                상대 Elo 팀×시즌 통합표·별칭·충돌 목록(ents.json 덤프는 git 제외)
tests/baseline-latest.json   기존 선수 수치 기준 스냅숏(작업이 끝나면 갱신)
docs/               인수인계 문서(아래 '문서' 절)
players/            (선택) 선수별 원자료·build 스크립트·순위표 — 모델을 고치면 전원 재빌드가 필요하므로 보관
```

명령: `npm install` → `npm run check` (= 빌드 + 기준 스냅숏과 비교). 크롬 경로는 `CHROME_PATH`로 지정.
`dist/`는 git에 올리지 않는다(빌드로 매번 만든다). `src/`가 정본이다.

## 반드시 지킬 것

1. **기존 선수 수치는 바뀌지 않아야 한다.** 새 선수 추가·화면 수정 뒤 `npm run check`가 "통과"여야 한다. 일부러 값을 바꾼 선수는 `--allow 이름`으로 허용하고, 바뀐 선수·수치를 **표로 요약해 알린다**.
2. **초기 렌더 순서(TDZ)**: `render()`는 스크립트 앞부분에서 처음 실행된다. render 안에서 부르는 코드가 뒤에 선언된 `const`를 건드리면 스크립트 전체가 멈춘다. render에서 쓸 새 상수는 `const DEF=` 앞에, 새 함수는 `function` 선언으로 둔다.
3. **데이터 `<script src>`는 본문 `<script>`보다 앞**에 둔다(상수가 먼저 있어야 `PRESETS`가 만들어짐). 데이터 파일을 추가하면 `index.html`에 태그를 반드시 같이 추가한다(build.py가 짝이 안 맞으면 멈춘다).
4. 바꿀 때마다 **버전을 올린다**: `index.html`의 `v1.306</span>` 한 곳(제목 `<h1>` 안). 형식 v1.xx.
5. 기록은 **출처로 확인된 것만** 넣는다. 추정하거나 뺀 내용과 출처 간 차이는 그 선수의 설명(`XXX_NOTE`)에 남긴다. 근거는 '데이터 출처와 처리 방식'(게시본 설명)이 정본이다.
6. 별도의 '○○추가.md'를 만들지 않는다. 바뀐 내용은 `docs/`의 인수인계 문서에 반영한다.
7. 설명(`XXX_NOTE`)·`lv` 문구에 작업용 코드/변수명(dc·dk·dsf·ko·OTHER_LEG·seasonOf·v1.xxx 등)을 쓰지 않는다. 도움·골을 더하거나 빼면 설명 첫 줄 합계와 '클럽별 경기·골·도움' 줄도 같이 고친다(docs 17절).
8. **작업이 끝나면 알림을 보낸다**: 몇 분 이상 걸린 작업(선수 추가, 데이터 수정·검증, 게시 등)이 끝나거나 사용자 결정이 필요해 멈출 때 `PushNotification`으로 한 줄 알림을 보낸다(200자 이내, 결과를 앞에: 예 "v1.147 완료: 새 선수 추가, check 통과"). 바로 끝나는 짧은 답변에는 보내지 않는다. 클라우드 세션에는 자동 완료 알림이 없어서 사용자가 요청한 규칙이다.

## 지표 정의 (사용자와 합의된 규칙 — 바꾸지 말 것)

SOC = Σ 기본값 × S × O × C
- 기본값: 골 1.0, PK 골 0.8, 도움 0.6.
- S(상황 보정): 포아송 기대 승점 모델. 양 팀 λ=1.35/90분, 정규시간 끝 94분, 연장 122분. 승 3·무 1, 단판 토너먼트 무승부 1.5. S = (골 뒤 기대 승점 − 골 전) ÷ 평균 골 1개의 증가량(norm≈0.706, `computeNorm`). 두 경기 합산은 진출 기대값=3×진출 확률, 정규화는 단판과 같은 `computeNorm`, **S 상한 2.83**(`DEF.scap`), 동점이어도 원정골 진출은 승리와 같게.
- O(상대 보정) = clamp(e^(0.0015×(상대 추정 Elo − 1500)), 0.3, 2.6).
- C(대회 중요도) = (I/25)^강도(1). 리그 25, 국내컵 16강까지 10 / 8강 이후 20, 챔스 예선 25 / 조별 30 / 16강 45 / 8강 이후 45, 유로파 20/25/30, 컨퍼런스 15/20/25, 클럽 월드컵 35 등(전체 표는 docs 2절). 준결승 ×1.15, **결승 ×1.5**.
- 상대 Elo 리그 시즌 수준(v1.216, v1.222 확대): 유럽 30개 리그(5대 리그·네덜란드·포르투갈 + 튀르키예·벨기에 등 23개 나라)는 `tools/league_era_normalize.py`로 시즌마다 5대 리그 평균 1762.1 고정 + UEFA 계수(앞뒤 5시즌, 시즌 척도 나눔) × 22.2. 목표 평균·흩어짐은 `elo/league_season_mean.json`. 새 선수는 이 값(또는 통합표 값)을 쓰고, 넣은 뒤 도구를 돌려 이동량 0을 확인(docs 4절).
- 비유럽 리그(v1.217): `tools/league_world_normalize.py`로 Opta 수준 + Transfermarkt 몸값 변화 절반(`elo/league_world_mean.json`). 새 선수도 넣은 뒤 두 도구를 돌려 이동량 0 확인.
- 유럽 2부(v1.218): `tools/league_second_tier.py`로 1부(2025-26) − Opta 간격 + 1부 시즌 이동의 절반(`elo/league_second_mean.json`). 새 선수는 세 도구를 모두 돌려 이동량 0 확인.
- 다른 나라 2부(v1.219): `tools/league_second_tier_x.py`(튀르키예·브라질 B·J2·아르헨티나 2부·USL·NASL·사우디·카타르 2부). 새 선수는 도구 네 개를 모두 돌려 이동량 0(±2 반올림) 확인.
- **상대 순위 → Elo(v1.226)**: `tools/league_rank_apply.py`가 모든 '리그·시즌·순위/팀 수' 라벨 행 값을 기준 평균(나라·단계·시즌) + 흩어짐 × 순위 곡선으로 정확히 맞춘다(같은 리그·시즌·순위면 모든 선수 같은 값). 순위는 라벨 앞부분(첫 ' (' 앞)에 `N위/M팀`으로 적는다. 새 형식 `<나라> <k>부 <시즌> <N>위/<M>팀`(예 `독일 4부 2012-13 5위/18팀 (Regionalliga Nord, 리그 수준 추정)`), 5대 리그·2부 도구 리그는 기존 형식. 순위는 출처로 확인(최종 순위, 스플릿·플레이오프 뒤 최종, 아페르투라형 리그는 경기 날짜에 진행 중이던 단계, 진행 중 시즌은 현재 순위). 하부 리그 기준점은 `elo/league_lower_base.json`(v1.226 이전 평균 수준, 위 단계보다 최소 100 낮게). **새 선수는 라벨을 이 형식으로 넣고 `python3 tools/league_rank_apply.py --apply` 뒤 도구 다섯 개 모두 이동량 0, Elo 통합표 충돌 0 확인.** 순위를 못 찾은 행만 '순위 없음' 라벨(그 단계 기준점 값).
- **리그 이름 통일(v1.291, 사용자 결정)**: 라벨 맨 앞 리그 이름은 리그마다 하나로 쓴다(J1리그·K리그1·쉬페르리그·MLS·리가MX·사우디 프로리그·중국 슈퍼리그·브라질 세리에 A·오스트리아 분데스리가·엑스트라클라사·챔피언십·세군다·리그2, 그 밖에는 `<나라> 1부`; 나라 이름만 쓰지 않음, 아르헨티나 단계 이름은 한글). 승점 표 키도 같은 이름.
- **감점 시즌 예외(v1.287)**: 승점 감점·우승 박탈·행정 처분(최하위 배치 등)으로 공식 최종 순위가 경기장 성적과 달라진 리그·시즌은 **감점 전 순위**(감점을 되돌린 승점 순, 동률은 그 리그 규칙)를 라벨에 쓰고 괄호 첫머리에 `감점 전 순위`를 적는다(예 `세리에A 2005-06 1위 (감점 전 순위)`). 감점 팀뿐 아니라 그 때문에 밀린 같은 시즌의 다른 팀도 바꾼다. 시즌 중 퇴출·경기 무효·몰수패(경기 결과 변경)·취소된 감점·진행 중 시즌은 제외. 조사 기록은 `elo/penalty_seasons.json`(새 선수의 상대가 이 목록의 시즌이면 그 순위를 쓴다).
- **5대 리그 승점·득실 간격(v1.288)**: 5대 리그 1부 상대는 리그 안 간격을 순위 곡선 대신 그 시즌 성적으로 정한다(사용자 결정). Elo = 시즌 중심값 + 흩어짐×(순위 곡선의 리그 평균) + k_L×[(경기당 승점−리그 평균) + 0.3×(경기당 득실−리그 평균)], 승점은 승 3·무 1로 다시 셈(감점 전). 다른 시즌과 비교하지 않음(시대 영향 없음). k_L(프리미어리그 157.13·세리에A 146.79·라리가 168.82·분데스리가 171.3·리그1 181.09)은 모든 시즌을 합친 흩어짐이 순위 방식과 같게 맞춘 상수. 자료 `elo/league_points_big5.json`(위키백과 시즌 순위표 186개), 계산 `tools/league_points.py`, `league_rank_apply.py`가 자동으로 씀(표 없는 시즌·진행 중 시즌은 순위 곡선). 새 시즌 표를 넣으면 그 시즌 행만 바뀐다(k는 고정). `league_era_normalize.py`는 이 시즌들을 평균 추정에서 뺀다. **v1.290부터 다른 리그도 같은 방식**: 리그·시즌 2,316개 중 2,190개 표(위키백과+RSSSF 대조, 오류는 세 번째 출처로 고침)를 `elo/league_points_other.json`에 두고(키 = 라벨의 순위 앞부분, map = 데이터 팀 이름 → 표·행), k는 리그(나라|단계)별로 같은 방식으로 맞춤(팀 40개 미만 리그는 k/흩어짐 중앙값 1.728). 진행 중 시즌(ongoing)·skip·10경기 미만 표·전 경기 몰수패 팀은 순위 곡선. 평균 추정 도구 네 개는 이 행들을 빼고 고정 흩어짐(`league_points.sd_fix`)을 씀. 새 선수의 상대가 표 있는 시즌이면 map에 데이터 팀 이름을 추가한다.
- 최고 3·5시즌 평균: 최소 출전 시간(기본 900분) 이상 시즌만, 부족하면 있는 시즌만 평균하고 `*`. 대회 필터가 챔스·컵류면 90분 기준(`peakMin`).
- **SOC-CAR(커리어 점수, v1.236, v1.237 식 변경)** = 누적 SOC × 0.5 + 3-peak 평균 + 5-peak 평균(야구 JAWS 방식, 사용자 결정. 최고 3시즌 각 약 0.53, 4·5번째 시즌 0.2의 무게). 시즌 목록은 3·5-peak와 같음(최소 출전 시간 이상, 부족하면 있는 시즌만 평균하고 `*`), 기간은 통산·대회 필터 적용. `socCar`, 비교 표 열·선수 요약 카드.
- 합계는 `pStats(p, st.coef)`의 soc·n·g·a·min·pk3·pk5·car.

## 기록 판정 (모든 선수 공통, 요약 — 전문은 docs 3절)

- 경기·출전 분: Transfermarkt performance-game(played·playedMinutes)을 쓰고 FotMob·위키백과와 대조. 자료 없으면 90분 추정이라 밝힘.
- 골: 상대 자책골 제외. PK 막힌 뒤 리바운드 골은 PK 아님. 추가시간 90+4 → 94분, 45+2 → 47분(전반 추가시간 골은 `45+x`분으로 적음).
- 도움: **PK 유도·슈팅 리바운드('Shot on goal')·굴절·상대 자책골 유도·본인 PK 골의 본인 도움은 뺀다**. 단일 출처 도움은 다른 출처 2곳이 확인한 것만.
- 날짜는 현지 날짜(북미 저녁 경기는 UTC에서 하루 앞).
- 클럽 월드컵 2025 조별은 리그식(`ko:0`, 무승부 1점), 16강부터 단판(`ko:1`).
- 시즌 구분(`seasonOf`): 기본 8월 1일 기준, 2020년 8월 경기는 2019-20. 클럽별 예외(7월 10일 기준·달력 연도)는 docs 6절 목록에 새 키를 추가해 관리.

## 새 선수 추가 절차 (이 저장소 기준)

1. **자료조사**: FotMob·Transfermarkt·위키백과·경기 기사 대조(docs 8절, 프로젝트의 `GUIDE-선수자료조사에이전트.md`). 상대 Elo는 순위표+리그 모델(docs 4절)이며 순위표·모델에 없는 리그·상대는 직접 추정해 설명에 '추정'으로 적는다.
2. `players/<선수>/`에 원자료·`build_<선수>.py`·순위표를 둔다(`<선수>.json` → `mk()` 행으로 변환).
3. `src/data/xxx.js` 새로 만들기: `XXX_E`·`XXX_M`·`XXX_NOTE` 세 상수. 접두어는 상수 이름 앞부분 소문자(파일명).
4. `src/index.html`에 `<script src="data/xxx.js"></script>`를 **마지막 data 태그 뒤, 본문 `<script>` 앞**에 추가.
5. 새 클럽 키가 생기면(integration.json의 `colors`, add_players.py는 색을 넣지 않으므로 따로) `src/data/clubcolors.js`의 `CLUB_COLORS`에 [주 색, 보조 색, 셋째 색](위키백과 유니폼·클럽 색) 추가(없으면 그래프가 기본 팔레트를 씀). `python3 tools/final_scores.py <캐시 폴더> <프리셋id:접두어:TM선수id>`로 `finals.js`에 최종 스코어 추가하고 `tools/final_scores_specs.txt`에 한 줄 추가(결승골·동점골 표시, TM에 없음·스코어 모순 확인). `src/data/hon.js`의 `HON_DATA` 한 줄에 우승·개인수상 항목 추가(프리셋 id 키, Transfermarkt 업적 페이지. 준우승은 넣지 않음(v1.220), 클럽 월드컵·슈퍼컵은 시즌 표기).
6. `src/index.html` 나머지(**`players/<선수>/integration.json`을 만들어 `ADD_PLAYERS_REAL=1 python3 tools/add_players.py <마지막 선수 id> <json…>`로 한 번에 넣는다** — 정본 보호 장치 때문에 환경 변수가 필요, 검증은 복사본에서, v1.150): `PRESETS`·`PCLUBS`·`CLUBS2`·클럽 판정 함수·`pClub`·`seasonOf`(필요 시)·`CL`·`CLN`·`RETIRED`(은퇴 시)·`POS_OF`·국기(`FLAG`, 새 나라는 `flagBody`)·그래프 색 `--s<N>`(라이트 1곳·다크 2곳)·`slotOf`의 `(i%N)+1`·버전. `MAXSEL`은 7로 고정이라 올리지 않는다. 앵커는 **마지막 선수(에네르 발렌시아, 프리셋 `ennervalencia`) 기준**으로 잡고, 정확히 지정 횟수만큼 있는지 검사하는 `rep()` 방식 패치 스크립트를 쓴다.
7. `npm run check` → 기존 선수 동일·새 선수 '추가'로 표시, 콘솔 오류 없음 확인. 화면이 바뀌면 넓은 화면·휴대폰 폭(390px)·다크 모드를 playwright로 캡처해 확인.
8. `tests/baseline-latest.json`을 새 스냅숏(`dist/snapshot.json`)으로 교체, `docs/`에 반영(5절 표, 선수별 규칙, 새 리그 수준, 새 시즌 규칙, 버전 이력), 후보 풀(`football_200_등록표시.md`) 등록 표시.

## 게시 (링크로 확인하기)

- 정본 게시본(채팅에서 만든 기존 링크): https://claude.ai/artifact/QAwELkPtyT2ZGvpPfmvUDt — slug `bba54db4-c9db-4117-bd38-c8859144fe7f`. 파일은 `src/index.html`→`index.html`, `src/data/*.js`→`data/*.js` 그대로 대응한다. **claude.ai 채팅 세션에서** `publish_files`로 바뀐 파일만 올리면 같은 링크가 갱신된다(slug·base_version 필요, 파일은 작업 폴더 아래). 올린 뒤 `list_files` sha256으로 확인.
- Claude Code에서 직접 게시하면 **새 링크**가 생기고 **한 파일만** 가능하다(상대 경로 불가, 렌더 후 16MiB 이하). 이때는 `dist/club-soc.artifact.html`을 게시한다. v1.257부터 데이터·본문 스크립트를 gzip+base64로 압축해 넣고 열 때 브라우저(DecompressionStream)가 풀어 실행하므로 약 4.7MB(원본 약 15MB, 16MiB 한도). 압축본 확인은 `dist/club-soc.packed-test.html`을 열어 보면 됨. 기존 링크를 Claude Code에서 갱신할 수 있는지는 아직 확인 못 함.
- Claude Code 게시본(2026-11-10 v1.146부터): https://claude.ai/artifact/1GGsVtJ4cca2x1h6VwUc4A — 다음 세션에서 갱신할 때는 이 URL을 `url`로 넘겨 같은 링크를 유지한다(안 넘기면 또 새 링크가 생김). 채팅 정본 링크(위)와는 따로 관리되므로 둘 중 어느 쪽이 최신인지 버전 문구로 확인한다.
- 게시 직전에 다른 세션이 올렸는지(버전·sha256) 확인한다.

## 문서

- `docs/HANDOFF-클럽SOC계산기-자료편.md`: 수록 선수 값·선수별 규칙·소스 묶음·후보 풀·디자인·후속(5·9·10·11·12절).
- `docs/HANDOFF-클럽SOC계산기.md`: 작업 규칙편(0~4·6~8·15~17절: 버전 이력, 지표, 기록 판정, 상대 Elo 리그 표, 시즌 구분, 수집 요령, 일관성 점검, 설명 작성 규칙). **프로젝트에서 내려받아 이 폴더에 넣는다.** 단, 그 문서의 1절·9절 '게시본 받기'와 0절 '게시본' 줄은 옛 방식이라 이 CLAUDE.md와 `docs/HANDOFF-분리구조.md`가 우선한다.
- `docs/HANDOFF-분리구조.md`: 파일 분리 경위와 규칙.
- 작업이 끝나면 바뀐 인수인계 문서를 프로젝트(claude.ai)에도 다시 올린다(프로젝트 지식 용량 2MB 한도에 가까우니 원자료·스크립트는 올리지 않는다).
