#!/usr/bin/env python3
"""유럽 2부 리그 수준(v1.218, 사용자 결정 2026-11-19)

2부 목표 평균(시즌 y) = 1부(2025-26) − 간격 + 0.5 × (1부(y) − 1부(2025-26))
  - 1부(y): tools/league_era_normalize.py의 시즌 목표 평균(5대 리그 평균 고정 + UEFA 계수).
  - 간격: 2026-11-19 Opta 파워 랭킹 1부·2부 리그 평균 차 × 27.01(Opta→Elo 기울기, tools/league_world_normalize.py).
  - 1부의 시즌 이동은 절반만 따라감(UEFA 계수는 상위 클럽 성적이라 2부까지 그대로 따라가면 과함:
    예 2011-12 세군다가 같은 시즌 리그1보다 높아졌음).
  - 시즌 평균은 'YYYY-YY N위' 라벨 행으로 계산, 그 시즌 모든 행(순위 없는 행은 경기 날짜 시즌)을 같은 양만큼 옮김. 다시 돌리면 이동 0.
대상: 챔피언십·세군다·2. 분데스리가·세리에B·리그2·에이르스터 디비시·포르투갈 2부. 결과는 elo/league_second_mean.json.

  python3 tools/league_second_tier.py            # 표만
  python3 tools/league_second_tier.py --apply
"""
import json, re, glob, os, sys, statistics as st, collections, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPTA_SLOPE = 27.01
OPTA = json.load(open(os.path.join(ROOT, 'elo', 'opta_league_2026-11-19.json')))['리그']
def opta(prefix): return next(v for k, v in OPTA.items() if k.startswith(prefix))
# 2부 라벨 → (1부, Opta 1부 이름, Opta 2부 이름, 기본 팀 수 함수)
TIER2 = {
 '프리미어리그': (['챔피언십(2부)', '챔피언십'], 'English Premier League', 'English Football League - Championship', lambda y: 24),
 '라리가': (['세군다(2부)', '세군다'], 'Spanish La Liga', 'Spanish Segunda', lambda y: 22),
 '분데스리가': (['2. 분데스리가'], 'German Bundesliga|', 'German Bundesliga Zwei', lambda y: 18),
 '세리에A': (['세리에B'], 'Italian Serie A', 'Italian Serie B', lambda y: 22 if y <= 2019 else 20),
 '리그1': (['리그2(프랑스 2부)', '프랑스 리그2', '리그2'], 'French Ligue 1', 'French Ligue 2', lambda y: 20),
 '에레디비시': (['에이르스터 디비시(네덜란드 2부)'], 'Dutch Eredivisie', 'Dutch Eerste', lambda y: 20),
 '포르투갈 1부': (['포르투갈 2부'], 'Portuguese Primeira', 'Portuguese Segunda', lambda y: 18),
}
GAP = {top: OPTA_SLOPE * (opta(a) - opta(b)) for top, (_, a, b, _) in TIER2.items()}
G = {'__file__': os.path.join(ROOT, 'tools', 'league_era_normalize.py'), '__name__': 'x'}
_argv = sys.argv; sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(open(G['__file__'], encoding='utf-8').read().rsplit("if '--apply' in sys.argv:", 1)[0], 'era', 'exec'), G)
sys.argv = _argv
T1 = G['target']; cv = G['cv']
def target2(top, y): return T1(top, 2026) - GAP[top] + 0.5 * (T1(top, y) - T1(top, 2026))
LAB = sorted(((lab, top) for top, (labs, *_r) in TIER2.items() for lab in labs), key=lambda x: -len(x[0]))
def which(lv):
    for lab, top in LAB:
        if lv.startswith(lab + ' ') or lv == lab: return lab, top
    return None, None
PAT = re.compile(r'^\S.*? (\d{4})-(\d{2}) (\d+)위(?:/(\d+)팀)?')
def dseason(d): y, m = int(d[:4]), int(d[5:7]); return y + 1 if m >= 8 else y
data = {}
for f in sorted(glob.glob(os.path.join(ROOT, 'src', 'data', '*.js'))):
    t = open(f, encoding='utf-8').read(); m = re.search(r'const (\w+)_E=(\[.*?\]\]);', t, re.S)
    if m: data[f] = (t, m, json.loads(m.group(2)))
PTS = collections.defaultdict(dict)
for f, (t, m, E) in data.items():
    for r in E:
        lv = str(r[12]); lab, top = which(lv)
        if not top: continue
        mm = PAT.match(lv)
        if not mm: continue
        y = int(mm.group(1)) + 1; rk = int(mm.group(3)); n = int(mm.group(4)) if mm.group(4) else TIER2[top][3](y)
        if rk <= n: PTS[(top, y)][r[1]] = (rk, n, r[2])
SD, MEAN = {}, {}
for top in TIER2:
    num = den = 0
    for (c, y), v in PTS.items():
        if c != top or len(v) < 2: continue
        L = [(cv(rk, n), e) for rk, n, e in v.values()]
        mx = st.mean(a for a, _ in L); my = st.mean(e for _, e in L)
        num += sum((a - mx) * (e - my) for a, e in L); den += sum((a - mx) ** 2 for a, _ in L)
    SD[top] = num / den if den > 0 and num > 0 else 51.24
    for (c, y), v in PTS.items():
        if c == top: MEAN[(top, y)] = st.mean(e - SD[top] * cv(rk, n) for rk, n, e in v.values())
SHIFT = {k: int(round(target2(*k) - MEAN[k])) for k in MEAN}
def shift_for(top, y):
    if (top, y) in SHIFT: return SHIFT[(top, y)]
    ys = [y2 for (c, y2) in SHIFT if c == top]
    return SHIFT[(top, min(ys, key=lambda y2: abs(y2 - y)))] if ys else 0
for top in TIER2:
    ys = sorted(y for (c, y) in MEAN if c == top)
    print(f'{TIER2[top][0][-1]} (간격 {GAP[top]:.0f}, 흩어짐 {SD[top]:.0f}):', ' '.join(f'{y-1}-{y%100:02d}:{target2(top, y):.0f}({SHIFT[(top, y)]:+d})' for y in ys))
if '--apply' in sys.argv:
    cnt = 0
    for f, (t, m, E) in data.items():
        n = 0
        for r in E:
            lv = str(r[12]); lab, top = which(lv)
            if not top: continue
            mm = re.search(r'(\d{4})-(\d{2})', lv)
            y = int(mm.group(1)) + 1 if mm else dseason(str(r[9]))
            d = shift_for(top, y)
            if d: r[2] = int(r[2]) + d; n += 1
        if n:
            open(f, 'w', encoding='utf-8').write(t[:m.start(2)] + json.dumps(E, ensure_ascii=False, separators=(',', ':')) + t[m.end(2):]); cnt += n
    json.dump({'설명': '유럽 2부 시즌 목표 평균 = 1부(2025-26) − 간격 + 0.5 × (1부(y) − 1부(2025-26))', '간격': {k: round(v, 1) for k, v in GAP.items()},
               '흩어짐': {k: round(v, 1) for k, v in SD.items()},
               '평균': {f'{TIER2[top][0][-1]}|{y-1}-{y%100:02d}': round(target2(top, y), 1) for top in TIER2 for y in range(1990, 2028)}},
              open(os.path.join(ROOT, 'elo', 'league_second_mean.json'), 'w'), ensure_ascii=False, indent=0)
    print('적용:', cnt, '행')
