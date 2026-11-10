#!/usr/bin/env node
/*
 클럽 SOC 계산기 검증 도구 (playwright 필요: npm install)

 1) 스냅숏 만들기   node tools/verify.js snap <html> <out.json>
    - 선수별 pStats(soc·경기·골·도움·분·3/5-peak)와, 탭마다 #clubTbl·#yearTbl·#honSec 글자를 저장.
 2) 비교하기        node tools/verify.js cmp <기준.json> <새.json> [--allow 선수1,선수2]
    - 기존 선수 수치가 그대로인지 확인. 새 선수 추가 때는 새 파일에만 있는 선수는 '추가'로 따로 보여 줌.
    - 값을 일부러 바꾼 선수는 --allow 로 이름을 적으면 차이를 허용하고 표로 보여 줌.
 3) 한 번에         node tools/verify.js check <html> [기준.json]
    - 스냅숏을 만들고 기준(기본 tests/baseline-latest.json)과 비교.

 환경변수: CHROME_PATH (크롬 실행 파일; 없으면 playwright 내장 크로미움 사용)
*/
const fs = require('fs');
const path = require('path');
const ROOT = path.dirname(__dirname);

function loadPlaywright() {
  for (const p of ['playwright', '/opt/npm-tools/node_modules/playwright']) {
    try { return require(p); } catch (e) {}
  }
  console.error('playwright 가 없음: npm install 을 먼저 하세요'); process.exit(2);
}

async function snap(html, out) {
  const { chromium } = loadPlaywright();
  const opt = { args: ['--no-sandbox'] };
  if (process.env.CHROME_PATH) opt.executablePath = process.env.CHROME_PATH;
  else if (fs.existsSync('/usr/bin/google-chrome')) opt.executablePath = '/usr/bin/google-chrome';
  const b = await chromium.launch(opt);
  const ctx = await b.newContext({ viewport: { width: 1400, height: 1000 } });
  await ctx.route(/^https?:\/\/(?!file)/, r => r.abort()); // 바깥 요청 차단(폰트 등)
  const p = await ctx.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(String(e)));
  // 바깥 요청(구글 폰트)을 일부러 막았으므로 'Failed to load resource' 는 오류로 세지 않음
  p.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push(m.text()); });
  await p.goto('file://' + path.resolve(html), { waitUntil: 'domcontentloaded' });
  await p.waitForSelector('#tabStrip button', { timeout: 120000 });
  const stats = await p.evaluate(() => st.players.map(pl => {
    const s = pStats(pl, st.coef);
    return { n: pl.name, soc: s.soc, m: s.n, g: s.g, a: s.a, min: s.min, pk3: s.pk3 && s.pk3.v, pk5: s.pk5 && s.pk5.v };
  }));
  const n = await p.locator('#tabStrip button').count();
  const tabs = [];
  for (let i = 0; i < n; i++) {
    await p.locator('#tabStrip button').nth(i).click();
    await p.waitForTimeout(150);
    tabs.push(await p.evaluate(() => ({
      club: document.querySelector('#clubTbl').innerText,
      year: document.querySelector('#yearTbl').innerText,
      hon: document.querySelector('#honSec') ? document.querySelector('#honSec').innerText : ''
    })));
  }
  fs.writeFileSync(out, JSON.stringify({ stats, tabs, errs }));
  console.log('스냅숏', out, '선수', stats.length, '탭', n, '오류', errs.length);
  await b.close();
  return { stats, tabs, errs };
}

function cmp(a, b, allow) {
  const by = d => Object.fromEntries(d.stats.map((s, i) => [s.n, { s, t: d.tabs[i] }]));
  const A = by(a), B = by(b);
  const added = Object.keys(B).filter(k => !A[k]);
  const removed = Object.keys(A).filter(k => !B[k]);
  const diffs = [];
  let tabDiff = 0;
  for (const k of Object.keys(A)) {
    if (!B[k]) continue;
    for (const f of ['soc', 'm', 'g', 'a', 'min', 'pk3', 'pk5']) {
      const x = A[k].s[f], y = B[k].s[f];
      if (!(x === y || (Number.isFinite(x) && Number.isFinite(y) && Math.abs(x - y) < 1e-9))) diffs.push({ n: k, f, x, y });
    }
    if (JSON.stringify(A[k].t) !== JSON.stringify(B[k].t)) tabDiff++;
  }
  const okNames = new Set(allow || []);
  const bad = diffs.filter(d => !okNames.has(d.n));
  console.log('기준', Object.keys(A).length, '명 · 새', Object.keys(B).length, '명');
  if (added.length) console.log('추가된 선수:', added.join(', '));
  if (removed.length) console.log('빠진 선수:', removed.join(', '));
  if (diffs.length) {
    console.log('값이 바뀐 항목(' + diffs.length + '):');
    for (const d of diffs) console.log('  ' + (okNames.has(d.n) ? '[허용] ' : '[차이] ') + d.n + ' ' + d.f + ': ' + d.x + ' → ' + d.y);
  }
  console.log('탭 표 글자가 달라진 선수:', tabDiff, '명 (선수 수치를 안 바꿨는데 이 값이 0이 아니면 확인)');
  console.log('새 파일 콘솔 오류:', b.errs.length ? b.errs.slice(0, 3) : '없음');
  const pass = !bad.length && !removed.length && !b.errs.length;
  console.log(pass ? '결과: 통과 (기존 선수 수치 동일)' : '결과: 확인 필요');
  return pass;
}

(async () => {
  const [cmd, a, b, ...rest] = process.argv.slice(2);
  const allowIdx = process.argv.indexOf('--allow');
  const allow = allowIdx > 0 ? process.argv[allowIdx + 1].split(',') : [];
  if (cmd === 'snap') { await snap(a, b); return; }
  if (cmd === 'cmp') { process.exit(cmp(JSON.parse(fs.readFileSync(a)), JSON.parse(fs.readFileSync(b)), allow) ? 0 : 1); }
  if (cmd === 'check') {
    const base = b && !b.startsWith('--') ? b : path.join(ROOT, 'tests', 'baseline-latest.json');
    const out = path.join(ROOT, 'dist', 'snapshot.json');
    fs.mkdirSync(path.dirname(out), { recursive: true });
    const cur = await snap(a, out);
    process.exit(cmp(JSON.parse(fs.readFileSync(base)), cur, allow) ? 0 : 1);
  }
  console.log('사용: node tools/verify.js snap <html> <out.json> | cmp <기준> <새> [--allow 이름,이름] | check <html> [기준]');
})();
