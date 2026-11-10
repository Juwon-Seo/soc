#!/usr/bin/env node
/*
 상대 Elo 팀×시즌 통합표 만들기 (src/data/*.js 만 읽음, 브라우저 불필요)

   node tools/elo_table.js [출력 폴더=elo]

 만드는 파일
   opponent_elo_by_team_season.csv  팀, 시즌, Elo, 근거, 수준 라벨(lv), 사용 기록 수, 선수, 이름 표기, 해소 전 값(값:건수)
   opponent_elo_by_team_season.json 같은 내용, "팀|시즌" 키
   aliases.csv                      팀 대표 이름 ← 묶인 표기들, 묶은 근거
   conflicts.csv                    한 팀-시즌 안에 값이 여럿인 것(차이 큰 순) — 선수 간 불일치 점검용
   ents.json                        전체 득점·도움 기록 덤프(선수, 상대, 팀 키, 시즌, Elo, 대회, 날짜, 분, lv)

 처리 규칙(인수인계 문서 15절의 옛 unify.py/teams2.py 규칙을 이 저장소 자료로 다시 구현)
   1) 이름 정규화: 악센트·대소문자·문장부호 제거, FC·CF·AC·SC 같은 흔한 꼬리표와 '(- 2024)' 같은 해체 표기 제거,
      약칭 치환(man→manchester, utd→united, munich→munchen 등).
   2) 같은 팀 묶기(근거가 있을 때만)
      - 같은 날짜: 한 표기가 다른 표기의 부분집합(예 'Atlético' ⊂ 'Atlético Madrid')이고 Elo 차이 ≤ 160,
        또는 흔하지 않은 단어를 함께 쓰고 Elo가 같음(예 'Red Bull New York' = 'New York Red Bulls').
      - 같은 시즌: 부분집합이고 Elo가 같으며 둘 다 순위 확인값('추정' 아님)(예 'Birmingham' = 'Birmingham City').
      - 짧은 표기가 서로 다른 두 팀에 걸리면(예 'Racing' → 라싱 산탄데르/라싱 클루브) 전체를 묶지 않고
        기록마다 그 날짜·시즌 근거가 있는 쪽으로만 붙인다.
      - NEVER 목록(에스파뇰≠바르셀로나, 밀란≠인테르, 취리히≠그라스호퍼 등)은 묶지 않는다.
        RAW_KEY: 표기만으로 다른 팀을 가르는 예외(보아비스타 SC=브라질, Racing Club=아르헨티나, Portland Timbers 2=2군 등).
   3) 시즌: lv의 시즌 표기 우선('2011-12' 또는 단일 연도 '2024'). 없으면 그 팀이 단일 연도 시즌을 쓰는 팀이면 날짜의 연도,
      아니면 7월 1일 기준 'YYYY-YY'.
   4) 팀-시즌 값 결정: ① 순위가 확인된 값(lv에 '추정' 없음)만 모아 하나면 그 값, 여럿이면 다수값(동수면 평균)
      ② 확인값이 없으면 추정값의 다수값, 동수면 평균. lv는 고른 값을 쓰는 기록 중 가장 흔한 문구.
   이 도구는 표만 만든다. 선수 기록(src/data)은 바꾸지 않는다.
*/
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const ROOT = path.dirname(__dirname);
const OUT = path.resolve(process.argv[2] || path.join(ROOT, 'elo'));

// ---------- 자료 읽기 ----------
const DATA = path.join(ROOT, 'src', 'data');
const ctx = {}; vm.createContext(ctx);
const files = fs.readdirSync(DATA).filter(f => f.endsWith('.js') && f !== 'hon.js').sort();
for (const f of files) vm.runInContext(fs.readFileSync(path.join(DATA, f), 'utf8').replace(/(^|\*\/|;)\s*const /gm, '$1var '), ctx, { filename: f });
// 선수 이름: index.html PRESETS 에서 접두어 → 이름
const html = fs.readFileSync(path.join(ROOT, 'src', 'index.html'), 'utf8');
const PNAME = {};
for (const m of html.matchAll(/name:"([^"]+)",ver:pver\(([A-Z]+)_E/g)) PNAME[m[2]] = m[1];

const ents = [];
for (const f of files) {
  const P = path.basename(f, '.js').toUpperCase();
  const E = ctx[P + '_E'];
  if (!Array.isArray(E)) { console.error('상수 없음', P + '_E'); process.exit(1); }
  E.forEach((e, i) => {
    const [type, opp, elo, comp, min, gf, ga, ko, pk, date, et, dm, lv] = e;
    ents.push({ p: P, player: PNAME[P] || P, i, type, opp, elo, comp, min, date, lv: String(lv || '') });
  });
}

// ---------- 1) 이름 정규화 ----------
const STOP = new Set(('fc cf afc ac as sc cd ud rcd ssc ss us sv vfl vfb tsg fk sk jk bk if club de da do del la le l e y ' +
  'calcio futebol clube sfc the sl sad ca kv rc fsv bsc nk gnk rsc krc sm ea sco hsc fco ogc ' +
  'cfc bc uc hotspur balompie oc lb').split(' '));
const TOK_ALIAS = { man: 'manchester', utd: 'united', munich: 'munchen', dep: 'deportivo', bor: 'borussia',
  gladbach: 'monchengladbach', mgladbach: 'monchengladbach', brom: 'bromwich', wis: 'wisla', gaillar: 'gaillard',
  athletico: 'atletico', internazionale: 'inter', moskau: 'moscow', moskva: 'moscow', wien: 'vienna', praha: 'prague',
  st: 'saint', cologne: 'koln', lisboa: 'lisbon', sevilla: 'sevilla', bucuresti: 'bucharest', kyiv: 'kiev', kiew: 'kiev' };
const GENERIC = new Set(('city united real athletic atletico sporting racing olympique olympic club deportivo union wanderers ' +
  'rovers county town albion inter dynamo dinamo red bull bulls new york saint san santa al ahli fk cs ' +
  'stade sport sports esporte esportivo independiente nacional national 1 2 north south east west').split(' '));
function norm(s) {
  let t = String(s).normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/ø/g, 'o').replace(/ß/g, 'ss').replace(/ł/g, 'l').replace(/æ/g, 'ae')
    .replace(/\(\s*-\s*\d{4}\s*\)/g, ' ')
    .replace(/m'gladbach/g, 'monchengladbach').replace(/[^a-z0-9()]+/g, ' ');
  return t.split(' ').filter(Boolean).map(w => TOK_ALIAS[w] || w)
    .filter(w => !STOP.has(w) && !/^\d{1,2}$/.test(w) && !/^(18|19|20)\d\d$/.test(w)).join(' ') || t.trim();
}
// 같은 이름이라도 다른 팀(정규화 뒤 같은 키가 되지만 실제로 다른 팀)은 여기서 바로 나눈다.
const RAW_KEY = { 'Boavista SC': 'boavista (brasil)', 'Racing Club': 'racing club', 'Portland Timbers 2': 'portland timbers 2',
  'Gazélec Football Club Olympique Ajaccio': 'gazelec ajaccio', 'Inter Milan': 'inter', 'Inter': 'inter' };
// 근거(같은 날짜·같은 값)가 없어 자동으로 못 묶지만 같은 팀인 표기(직접 확인: lv의 리그·나라가 같음) → 대표 표기
const SAME = {
  'FC Sheriff': 'FC Sheriff Tiraspol', 'Sheriff Tiraspol': 'FC Sheriff Tiraspol',
  'Kardemir DC Karabükspor': 'Kardemir Karabükspor', 'Vit. Guimarães': 'Vitória Guimarães SC',
  'Vitória': 'Esporte Clube Vitória', 'Vitesse': 'Vitesse Arnhem',
  'Guangzhou Evergrande': 'Guangzhou Evergrande Taobao', 'Guangzhou FC': 'Guangzhou Evergrande Taobao',
  'Excelsior': 'SBV Excelsior', 'Excelsior Rotterdam': 'SBV Excelsior',
  'Flamengo': 'CR Flamengo', 'Clube de Regatas do Flamengo': 'CR Flamengo',
  'Juventude': 'Esporte Clube Juventude', 'Bahia': 'Esporte Clube Bahia', 'Toluca': 'Deportivo Toluca',
  'Atlas': 'Atlas Guadalajara', 'Raja Club Athletic': 'Raja Casablanca', 'Uniao Rondonopolis': 'União Rondonópolis EC (MT)',
  'Madureira RJ': 'Madureira EC', 'Bangu': 'Bangu Atlético Clube (RJ)', 'Guarani FC': 'Guarani Futebol Clube (SP)',
  'Associação Portuguesa de Desportos': 'Portuguesa', 'Northampton': 'Northampton Town', 'Partizan': 'FK Partizan Belgrade',
  'Grêmio': 'Grêmio Foot-Ball Porto Alegrense', 'America MG': 'América Futebol Clube (MG)',
  'CA Bragantino': 'Red Bull Bragantino', 'SC Veendam (- 2013)': 'BV Veendam' };
function fixKey(k, e) {
  if (RAW_KEY[e.opp]) return RAW_KEY[e.opp];
  if (SAME[e.opp]) return norm(SAME[e.opp]);
  if (k === 'boavista' && /브라질/.test(e.lv)) return 'boavista (brasil)';
  if ((k === 'al ahli') && /카타르|도하/.test(e.lv)) return 'al ahli (qatar)';
  if (k === 'arsenal' && /아르헨티나/.test(e.lv)) return 'arsenal sarandi';
  if ((k === 'al ahli' || k === 'al ahly') && /이집트/.test(e.lv)) return 'al ahly (egypt)';
  return k;
}
// 절대 묶지 않을 짝(정규화 키, 양방향)
const NEVER = [['barcelona', 'espanyol barcelona'], ['arsenal', 'arsenal sarandi'], ['racing santander', 'racing club'],
  ['real madrid', 'atletico madrid'], ['inter', 'inter miami'], ['atletico madrid', 'atletico mineiro'],
  ['milan', 'inter'], ['zurich', 'grasshopper zurich'], ['ajaccio', 'gazelec ajaccio'], ['portland timbers', 'portland timbers 2']];
const never = (a, b) => NEVER.some(([x, y]) => (x === a && y === b) || (x === b && y === a));

const toks = k => k.split(' ').filter(Boolean);
const isSub = (a, b) => { const A = toks(a), B = toks(b); return A.length < B.length && A.every(t => B.includes(t)); };
const sharesRare = (a, b) => { const B = toks(b); return toks(a).some(t => t.length >= 3 && !GENERIC.has(t) && B.includes(t)); };

// ---------- 3) 시즌 ----------
// 괄호 안(출처 설명: 'ClubElo 2026-10', '다른 선수 자료의 2021·2022 값')은 보지 않는다.
// 'YYYY-YY'는 뒤 연도가 앞 연도+1일 때만 시즌으로 본다(2026-10 같은 연-월 제외).
function lvSeason(lv) {
  let t = lv; for (let i = 0; i < 3; i++) t = t.replace(/\([^()]*\)/g, ' ');
  for (const m of t.matchAll(/((?:19|20)\d\d)\s*[-–/]\s*(\d{2}|\d{4})(?!\d)/g)) {
    const y = +m[1], z = +m[2];
    if (z === (y + 1) % 100 || z === y + 1) return y + '-' + String(y + 1).slice(2);
  }
  const s = t.match(/(?:^|[^\d])((?:19|20)\d\d)(?![\d-])/);
  return s ? s[1] : null;
}
const dateSeason = d => { const y = +d.slice(0, 4), m = +d.slice(5, 7); const s = m >= 7 ? y : y - 1; return s + '-' + String(s + 1).slice(2); };

for (const e of ents) { e.k0 = fixKey(norm(e.opp), e); e.lvs = lvSeason(e.lv); e.ds = dateSeason(e.date); }

// ---------- 2) 같은 팀 묶기 ----------
// 증거 모으기: 키 쌍 → 근거 목록
const ev = new Map(); // "a\tb" (a<b) → {date:[], season:[]}
function addEv(a, b, kind, what) {
  if (a === b || never(a, b)) return;
  const key = a < b ? a + '\t' + b : b + '\t' + a;
  if (!ev.has(key)) ev.set(key, { date: new Set(), season: new Set() });
  ev.get(key)[kind].add(what);
}
const byDate = new Map();
for (const e of ents) { if (!byDate.has(e.date)) byDate.set(e.date, []); byDate.get(e.date).push(e); }
for (const [d, L] of byDate) {
  for (let i = 0; i < L.length; i++) for (let j = i + 1; j < L.length; j++) {
    const a = L[i], b = L[j];
    if (a.k0 === b.k0) continue;
    const sub = isSub(a.k0, b.k0) || isSub(b.k0, a.k0);
    if ((sub && Math.abs(a.elo - b.elo) <= 160) || (a.elo === b.elo && sharesRare(a.k0, b.k0))) addEv(a.k0, b.k0, 'date', d);
  }
}
const bySeasonElo = new Map();
for (const e of ents) { if (/추정/.test(e.lv)) continue; const s = e.lvs || e.ds; const key = s + '|' + e.elo; if (!bySeasonElo.has(key)) bySeasonElo.set(key, new Set()); bySeasonElo.get(key).add(e.k0); }
for (const [se, S] of bySeasonElo) {
  const ks = [...S];
  for (let i = 0; i < ks.length; i++) for (let j = i + 1; j < ks.length; j++)
    if (isSub(ks[i], ks[j]) || isSub(ks[j], ks[i])) addEv(ks[i], ks[j], 'season', se);
}
// 짧은 키 → 긴 키 후보. 긴 쪽 = 단어 수가 많은 쪽(같으면 기록이 많은 쪽)
const cnt = new Map(); for (const e of ents) cnt.set(e.k0, (cnt.get(e.k0) || 0) + 1);
const longer = (a, b) => (toks(a).length !== toks(b).length ? toks(a).length > toks(b).length : (cnt.get(a) || 0) >= (cnt.get(b) || 0)) ? a : b;
const parents = new Map(); // short → Map(long → evidence)
for (const [key, v] of ev) {
  const [a, b] = key.split('\t'); const L = longer(a, b), S = L === a ? b : a;
  if (!parents.has(S)) parents.set(S, new Map());
  parents.get(S).set(L, v);
}
// union-find
const par = new Map(); const find = x => { while (par.has(x) && par.get(x) !== x) x = par.get(x); return x; };
const union = (a, b) => { a = find(a); b = find(b); if (a !== b) par.set(longer(a, b) === a ? b : a, longer(a, b)); };
const compatible = (a, b) => a === b || isSub(a, b) || isSub(b, a) || ev.has(a < b ? a + '\t' + b : b + '\t' + a);
const ambiguous = new Map(); // short → [long...]
// 단일 후보부터 묶고, 후보가 여럿이면 후보끼리 서로 같은 팀일 때만 묶는다.
for (const [S, M] of parents) {
  const Ls = [...M.keys()];
  const ok = Ls.every(x => Ls.every(y => compatible(x, y) && !never(x, y)));
  if (ok) Ls.forEach(L => union(S, L)); else ambiguous.set(S, Ls);
}
// 묶은 결과에 NEVER 쌍이 한 무리로 들어갔는지 확인
for (const [x, y] of NEVER) if (find(x) === find(y) && cnt.has(x) && cnt.has(y)) { console.error('묶으면 안 되는 쌍이 묶임:', x, y); process.exit(1); }

// 기록마다 팀 키 정하기(모호한 짧은 표기는 그 날짜·시즌 근거가 있는 쪽)
for (const e of ents) {
  if (ambiguous.has(e.k0)) {
    const M = parents.get(e.k0); let pick = null;
    for (const L of ambiguous.get(e.k0)) { const v = M.get(L); if (v.date.has(e.date)) { pick = L; break; } }
    if (!pick) for (const L of ambiguous.get(e.k0)) { const v = M.get(L); if (v.season.has((e.lvs || e.ds) + '|' + e.elo)) { pick = L; break; } }
    e.team = find(pick || e.k0); e.amb = !pick;
  } else e.team = find(e.k0);
}
// 팀 대표 이름 = 가장 많이 쓴 원래 표기
const teamNames = new Map();
for (const e of ents) { if (!teamNames.has(e.team)) teamNames.set(e.team, new Map()); const m = teamNames.get(e.team); m.set(e.opp, (m.get(e.opp) || 0) + 1); }
const repName = new Map();
for (const [t, m] of teamNames) repName.set(t, [...m].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0][0]);

// 단일 연도 시즌 팀: lv 시즌 표기가 단일 연도인 기록이 더 많은 팀
const cal = new Map();
for (const e of ents) if (e.lvs) { const c = cal.get(e.team) || [0, 0]; c[e.lvs.includes('-') ? 1 : 0]++; cal.set(e.team, c); }
for (const e of ents) {
  const c = cal.get(e.team);
  e.season = e.lvs || (c && c[0] > c[1] ? e.date.slice(0, 4) : e.ds);
  e.seasonSrc = e.lvs ? 'lv' : 'date';
}

// ---------- 4) 팀-시즌 값 ----------
const groups = new Map();
for (const e of ents) { const k = e.team + '|' + e.season; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(e); }
const est = e => /추정/.test(e.lv);
function majority(L) {
  const c = new Map(); L.forEach(e => c.set(e.elo, (c.get(e.elo) || 0) + 1));
  const arr = [...c].sort((a, b) => b[1] - a[1]); const top = arr.filter(x => x[1] === arr[0][1]);
  if (top.length === 1) return { v: top[0][0], how: c.size === 1 ? '단일값' : '다수' };
  return { v: Math.round(top.reduce((s, x) => s + x[0], 0) / top.length), how: '평균', avgOf: top.map(x => x[0]) };
}
const rows = [];
for (const [k, L] of groups) {
  const conf = L.filter(e => !est(e));
  let r, basis;
  if (conf.length) { r = majority(conf); basis = r.how === '단일값' ? (L.length > conf.length && new Set(L.map(e => e.elo)).size > 1 ? '순위 확인값 우선' : '단일값') : r.how; }
  else { r = majority(L); basis = r.how === '단일값' ? '단일값' : r.how + '(추정값)'; }
  const use = L.filter(e => e.elo === r.v);
  const lvc = new Map(); (use.length ? use : L).forEach(e => lvc.set(e.lv, (lvc.get(e.lv) || 0) + 1));
  let lv = [...lvc].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0][0];
  if (r.avgOf) lv += ` (추정, 선수 간 값 ${r.avgOf.join('·')}의 평균으로 맞춤)`;
  const vals = new Map(); L.forEach(e => vals.set(e.elo, (vals.get(e.elo) || 0) + 1));
  const names = new Map(); L.forEach(e => names.set(e.opp, (names.get(e.opp) || 0) + 1));
  const pl = [...new Set(L.map(e => e.player))];
  const [team] = k.split('|');
  const ev2 = [...vals.keys()];
  rows.push({ team: repName.get(team), key: team, season: L[0].season, elo: r.v, basis, lv, n: L.length, players: pl,
    names: [...names].sort((a, b) => b[1] - a[1]).map(x => x[0]), vals: [...vals].sort((a, b) => b[1] - a[1] || a[0] - b[0]),
    spread: Math.max(...ev2) - Math.min(...ev2), dateSeason: L.every(e => e.seasonSrc === 'date') });
}
rows.sort((a, b) => a.team.localeCompare(b.team) || a.season.localeCompare(b.season));

// ---------- 출력 ----------
fs.mkdirSync(OUT, { recursive: true });
const q = v => { const s = String(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
const csv = (file, head, data) => fs.writeFileSync(path.join(OUT, file), '﻿' + [head, ...data].map(r => r.map(q).join(',')).join('\n') + '\n');
csv('opponent_elo_by_team_season.csv',
  ['팀', '시즌', 'Elo', '근거', '수준 라벨(lv)', '사용 기록 수', '선수', '이름 표기', '해소 전 값(값:건수)', '시즌 근거'],
  rows.map(r => [r.team, r.season, r.elo, r.basis, r.lv, r.n, r.players.join('·'), r.names.join(' / '), r.vals.map(([v, c]) => v + ':' + c).join(' '), r.dateSeason ? '날짜(7월 1일 기준)' : 'lv']));
const J = {}; rows.forEach(r => { J[r.team + '|' + r.season] = { elo: r.elo, basis: r.basis, lv: r.lv, n: r.n, players: r.players, names: r.names, vals: Object.fromEntries(r.vals) }; });
fs.writeFileSync(path.join(OUT, 'opponent_elo_by_team_season.json'), JSON.stringify(J, null, 1));
const conf = rows.filter(r => r.vals.length > 1).sort((a, b) => b.spread - a.spread || b.n - a.n);
csv('conflicts.csv', ['팀', '시즌', '차이', '정한 Elo', '근거', '값:건수', '선수별 값'],
  conf.map(r => { const L = groups.get(r.key + '|' + r.season); const byV = new Map(); L.forEach(e => { if (!byV.has(e.elo)) byV.set(e.elo, new Set()); byV.get(e.elo).add(e.player); });
    return [r.team, r.season, r.spread, r.elo, r.basis, r.vals.map(([v, c]) => v + ':' + c).join(' '), [...byV].map(([v, s]) => v + '=' + [...s].join('·')).join(' / ')]; }));
const al = [];
for (const [t, m] of teamNames) if (m.size > 1) al.push([repName.get(t), [...m].sort((a, b) => b[1] - a[1]).map(([n, c]) => n + ':' + c).join(' / ')]);
al.sort((a, b) => a[0].localeCompare(b[0]));
const ambRows = [...ambiguous].map(([s, Ls]) => [s, Ls.map(l => repName.get(find(l)) || l).join(' / '), ents.filter(e => e.k0 === s && e.amb).length]);
csv('aliases.csv', ['팀 대표 이름', '묶인 표기:건수'], al);
if (ambRows.length) csv('ambiguous.csv', ['짧은 표기(정규화)', '걸리는 팀들', '근거 없어 따로 둔 기록 수'], ambRows);
fs.writeFileSync(path.join(OUT, 'ents.json'), '[\n' + ents.map(e => JSON.stringify({ p: e.player, i: e.i, t: e.type, opp: e.opp, team: repName.get(e.team), season: e.season, elo: e.elo, comp: e.comp, date: e.date, min: e.min, lv: e.lv })).join(',\n') + '\n]\n');

console.log(`선수 ${files.length}명 · 기록 ${ents.length} · 표기 ${new Set(ents.map(e => e.opp)).size} → 팀 ${teamNames.size} (별칭 묶음 ${al.length}, 모호한 짧은 표기 ${ambRows.length})`);
console.log(`팀-시즌 ${rows.length} · 값이 여럿인 팀-시즌 ${conf.length} (차이 ≥100: ${conf.filter(r => r.spread >= 100).length}) · 시즌을 날짜로 정한 팀-시즌 ${rows.filter(r => r.dateSeason).length}`);
console.log('출력', path.relative(ROOT, OUT) || '.');
