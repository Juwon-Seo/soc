#!/usr/bin/env python3
"""다른 나라 2부 리그 수준(v1.219, 사용자 결정 2026-11-19: '남은 일들' — v1.218 유럽 2부 규칙을 넓힘)

2부 목표 평균(시즌 y) = 1부(2025-26) − 간격 + 0.5 × (1부(y) − 1부(2025-26))
  - 1부(y): 튀르키예는 tools/league_era_normalize.py, 나머지는 tools/league_world_normalize.py의 시즌 목표 평균.
  - 간격: Opta 2026-11-19 1부·2부 리그 평균 차 × 27.01.
  - 시즌 평균은 순위 라벨 행(평균 − 흩어짐 × 순위 곡선)과 순위 없는 행(그대로 평균으로 봄)으로 계산, 그 시즌 모든 행을 같은 양만큼 옮김.
대상 라벨: 튀르키예 2부, 브라질 세리에 B, J2리그, 아르헨티나 2부, USL·NASL(미국 2부), 사우디 2부, 카타르 2부.
이 라벨들은 1부 도구(league_era_normalize·league_world_normalize)가 옮기지 않는다. 결과 elo/league_second_x_mean.json.

  python3 tools/league_second_tier_x.py            # 표만
  python3 tools/league_second_tier_x.py --apply
"""
import json, re, glob, os, sys, statistics as st, collections, io, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); import league_points as _LP   # v1.290: 승점·득실 모형 행은 평균 추정에서 뺌
OPTA = json.load(open(os.path.join(ROOT, 'elo', 'opta_league_2026-11-19.json')))['리그']
def opta(prefix): return next(v for k, v in OPTA.items() if k.startswith(prefix))
# 라벨 앞부분: (기준 도구, 나라, Opta 1부, Opta 2부, 달력 연도 여부, 기본 팀 수)
X = {
 '튀르키예 2부': ('era', 'Turkey', 'Turkish Super Lig', 'Turkish 1. Lig', False, 18),
 '브라질 세리에 B': ('world', 'BRA', 'Brazilian Serie A', 'Brazilian Serie B', True, 20),
 'J2리그': ('world', 'JPN', 'Japanese J1', 'Japanese J2', True, 22),
 '아르헨티나 2부': ('world', 'ARG', 'Liga Profesional Argentina', 'Argentina Primera Nacional', True, 20),
 'USL': ('world', 'USA', 'US Major League Soccer', 'USL Championship', True, 12),
 'NASL': ('world', 'USA', 'US Major League Soccer', 'USL Championship', True, 11),
 '사우디 2부': ('world', 'KSA', 'Saudi Arabian League', 'Saudi Arabian First', False, 18),
 '카타르 2부': ('world', 'QAT', 'Qatar Stars League|', 'Qatar Stars League 2', False, 10),
}
PREFIXES = tuple(X)
GAP = {k: 27.01 * (opta(v[2]) - opta(v[3])) for k, v in X.items()}
def load(name):
    G = {'__file__': os.path.join(ROOT, 'tools', name), '__name__': 'x'}
    argv = sys.argv; sys.argv = ['x']
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(open(G['__file__'], encoding='utf-8').read().rsplit("if '--apply' in sys.argv:", 1)[0], name, 'exec'), G)
    sys.argv = argv; return G
ERA = load('league_era_normalize.py'); WORLD = load('league_world_normalize.py')
cv = ERA['cv']
def T1(k, y):
    tool, cc = X[k][0], X[k][1]
    return ERA['otarget'](cc, y) if tool == 'era' else WORLD['target'](cc, y)
def target2(k, y): return T1(k, 2026) - GAP[k] + 0.5 * (T1(k, y) - T1(k, 2026))
def which(lv):
    for p in PREFIXES:
        if lv.startswith(p): return p
    return None
def year_of(lv, d, cal):
    m = re.search(r'(\d{4})(?:-(\d{2}))?', lv)
    if m: return int(m.group(1)) + (1 if m.group(2) else 0)
    y, mo = int(d[:4]), int(d[5:7]); return y if cal else (y + 1 if mo >= 8 else y)
data = {}
for f in sorted(glob.glob(os.path.join(ROOT, 'src', 'data', '*.js'))):
    t = open(f, encoding='utf-8').read(); m = re.search(r'const (\w+)_E=(\[.*?\]\]);', t, re.S)
    if m: data[f] = (t, m, json.loads(m.group(2)))
SD2 = 51.24
VALS = collections.defaultdict(dict)
for f, (t, m, E) in data.items():
    for r in E:
        lv = str(r[12]); k = which(lv)
        if not k: continue
        if _LP.covered(lv, r[1]): continue
        y = year_of(lv, str(r[9]), X[k][4])
        mm = re.search(r'(\d+)위(?:/(\d+)팀)?', lv)
        if mm:
            rk = int(mm.group(1)); n = int(mm.group(2)) if mm.group(2) else X[k][5]
            VALS[(k, y)][r[1]] = r[2] - SD2 * cv(min(rk, n), max(n, rk))
        else:
            VALS[(k, y)][r[1]] = r[2]
MEAN = {kk: st.mean(v.values()) for kk, v in VALS.items()}
SHIFT = {kk: int(round(target2(*kk) - MEAN[kk])) for kk in MEAN}
for k in X:
    ys = sorted(y for (c, y) in MEAN if c == k)
    if ys: print(f'{k} (간격 {GAP[k]:.0f}):', ' '.join(f'{y}:{target2(k, y):.0f}({SHIFT[(k, y)]:+d})' for y in ys))
if '--apply' in sys.argv:
    cnt = 0
    for f, (t, m, E) in data.items():
        n = 0
        for r in E:
            lv = str(r[12]); k = which(lv)
            if not k: continue
            d = SHIFT.get((k, year_of(lv, str(r[9]), X[k][4])), 0)
            if d: r[2] = int(r[2]) + d; n += 1
        if n:
            open(f, 'w', encoding='utf-8').write(t[:m.start(2)] + json.dumps(E, ensure_ascii=False, separators=(',', ':')) + t[m.end(2):]); cnt += n
    json.dump({'설명': '다른 나라 2부 시즌 목표 평균 = 1부(2025-26) − 간격 + 0.5 × (1부(y) − 1부(2025-26)), 흩어짐 51.24', '간격': {k: round(v, 1) for k, v in GAP.items()},
               '평균': {f'{k}|{y}': round(target2(k, y), 1) for k in X for y in range(1995, 2028)}},
              open(os.path.join(ROOT, 'elo', 'league_second_x_mean.json'), 'w'), ensure_ascii=False, indent=0)
    print('적용:', cnt, '행')
