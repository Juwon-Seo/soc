# 클럽 SOC 계산기 — 파일 분리 구조와 저장소 이전 (v1.145, 2026-11-10)

게시본이 4MB(4,230,778바이트)를 넘어 claude.ai 도구의 한 번 읽기 한도(4,194,304바이트)에 걸리게 되어 v1.145에서 선수 데이터를 파일로 분리했다. 이어서 같은 날 작업을 Claude Code(이 저장소)로 옮겼다. SOC 수치는 분리 전후 같다(55명의 SOC·경기·골·도움·3/5-peak, 팀별·시즌별 표, 우승 칸이 playwright로 완전히 일치).

## 1. 구조

- `src/index.html`(약 185KB): 화면·계산 코드. `<title>`부터 시작한다(claude.ai 플랫폼이 앞뒤 doctype·body를 붙여 주므로 게시본도 같은 모양). 본문 `<script>` 바로 앞에 `<script src="data/xxx.js"></script>` 56개.
- `src/data/<접두어>.js` 55개: 선수 1명당 1개, `XXX_E`·`XXX_M`·`XXX_NOTE` 세 상수(20~150KB). 접두어는 상수 이름 앞부분 소문자(`SON`→`son.js`, 호날두 `RON`, 메시 `MES`, 케인 `KAN`, 음바페 `MBA`, 벤제마 `BZM`, 그리즈만 `GRZ`, 리베리 `RIB`, 즐라탄 `IBR`, 이니에스타 `INI`, 이스코 `ISC`, 램파드 `LAM`, 야말 `YAM`).
- `src/data/hon.js`: `HON_DATA`(우승·개인수상) 한 줄.
- 같은 전역 스코프를 쓰는 클래식 스크립트라 `index.html` 안 코드가 `XXX_E` 등을 그대로 쓴다. **데이터 태그는 본문 `<script>`보다 앞**.
- `index.html`에 남은 것: CSS, 본문 HTML, `PEAK_MIN`·`peakMin`·`peakSeasons`, `RETIRED`, `DEF`, `COMP`·`STAGE`·`COMPF`, `CLUBS`·`CLUBS2`·`PCLUBS`, `PRESETS`, 함수들.

## 2. 빌드·검증

- `python3 tools/build.py` → `dist/club-soc.html`(데이터 인라인 단독 실행, 약 4.0MB) · `dist/club-soc.artifact.html`(껍데기 없는 한 파일, Claude Code 아티팩트 게시용) · `dist/dev.html`(개발용, `src/data`를 따로 읽음).
- `node tools/verify.js check dist/club-soc.html`: 스냅숏을 만들어 `tests/baseline-latest.json`과 비교. 새 선수는 '추가'로 따로 표시, 기존 선수가 바뀌면 `[차이]`로 표시. 바꾼 선수는 `--allow 이름`.
- 스냅숏 내용: `st.players.map(pl=>pStats(pl,st.coef))`(soc·n·g·a·min·pk3·pk5)와 탭마다 `#clubTbl`·`#yearTbl`·`#honSec` 글자. 바깥 요청(구글 폰트)은 막고 연다.
- 클럽 SOC 합 = 선수 누적 SOC(0.1 이내)로 팀별 표를 검증할 수 있다(55명 전원 일치 확인).

## 3. 게시

- 기존 링크 https://claude.ai/artifact/QAwELkPtyT2ZGvpPfmvUDt (slug `bba54db4-c9db-4117-bd38-c8859144fe7f`)는 **claude.ai 채팅 세션**에서 `publish_files`로 갱신한다. `src/index.html`→`index.html`, `src/data/x.js`→`data/x.js`. patch 모드라 바뀐 파일만 올리면 되고 나머지는 유지. `base_version`은 직전 `list_files`/`get_artifact` 버전. 파일은 `/home/claude/` 아래에 있어야 첨부된다. 제목·아이콘은 생략하면 유지.
- Claude Code 게시(`claude.ai/code/artifact/…`)는 한 파일만 되므로 `dist/club-soc.artifact.html`을 쓴다. 새 링크가 생긴다.
- v1.144(4.2MB 한 파일) 원본은 게시 이력 `1794291606-d25b`에 남아 있다.

## 4. 주의

- claude.ai 쪽 Claude in Chrome으로 게시본 화면을 읽어 값을 얻으려는 방법은 쓰지 말 것(계산기가 별도 도메인 프레임 안이라 스크립트로 못 읽음). 값이 필요하면 이 저장소에서 `verify.js snap`으로 계산한다.
- 인수인계 문서 `HANDOFF-클럽SOC계산기.md`의 1절·9절 '게시본 받기' 문장, 0절 '게시본' 줄, 5절의 54명 표(이스코 없음), 12절 '현재 앵커'(램파드)는 이 문서·`CLAUDE.md`와 어긋난다. 어긋나면 이 문서와 `CLAUDE.md`가 맞다. 마지막 추가 선수는 이스코(v1.144).
- 프로젝트 지식 용량이 2MB 한도에 가깝다(2026-11-10 약 1.93MB). 새 선수의 원자료·스크립트는 프로젝트에 올리지 않고 이 저장소의 `players/`에 둔다.

## 5. 2026-11-10 단일 클럽 SOC 최고값 (선수별 1위 클럽, 모든 대회, v1.144 기준)

1 메시 바르셀로나 977.95 · 2 호날두 레알 627.86 · 3 벤제마 레알 568.27 · 4 살라 리버풀 454.94 · 5 뮐러 바이에른 411.19 · 6 루니 맨유 401.47 · 7 그리즈만 아틀레티코 400.90 · 8 레반도프스키 바이에른 396.25 · 9 케인 토트넘 395.76 · 10 램파드 첼시 391.67 · 11 앙리 아스널 356.58 · 12 아구에로 맨시티 351.81 · 13 음바페 PSG 326.82 · 14 드록바 첼시 320.07 · 15 수아레스 바르셀로나 302.52 · 16 데 브라위너 맨시티 290.88 · 17 로이스 도르트문트 289.07 · 18 손흥민 토트넘 283.29 · 19 임모빌레 라치오 283.20 · 20 라우타로 인테르 267.62 (21위 이하는 계산기 팀별 SOC 표에서 확인; 값이 바뀌는 갱신 뒤에는 다시 뽑을 것).
