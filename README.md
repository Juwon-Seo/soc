# 클럽 SOC 계산기

축구 선수 클럽 경력 SOC(축구력) 계산기. 작업 규칙은 [CLAUDE.md](CLAUDE.md)를 본다.

## 처음 세팅

1. `npm install` (playwright) — 검증에 쓴다. 크롬이 따로 있으면 `CHROME_PATH`를 지정.
2. `npm run check` — 빌드 후 v1.145 기준 스냅숏과 비교. "통과"가 나오면 준비 끝.
3. `dist/club-soc.html`을 브라우저로 열면 계산기가 뜬다(`dist/dev.html`은 `src/data`를 따로 읽는 개발용).
4. 프로젝트(claude.ai)에서 내려받아 `docs/`에 넣을 것:
   - `claude/HANDOFF-클럽SOC계산기.md` (작업 규칙편)
   - `claude/GUIDE-선수자료조사에이전트.md`
   - `claude/football_200_등록표시.md` (후보 풀)
5. (선택) 선수 원자료 묶음 `claude/src/*_bundle*.txt`를 한 폴더에 내려받아 `python3 tools/unbundle.py <폴더>` — `players/`에 풀린다.

## 폴더

`src/` 정본(index.html + data/*.js) · `tools/` 빌드·검증 · `tests/` 기준 스냅숏 · `docs/` 인수인계 문서 · `players/` 선수 원자료(선택) · `dist/` 빌드 결과(git 제외)
