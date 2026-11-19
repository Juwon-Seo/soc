#!/usr/bin/env python3
"""리그 시즌 보정(v1.215): 세리에A·리그1·에레디비시·포르투갈 1부(전 시즌)와 분데스리가(2006-07 이전)의
상대 Elo를 시즌별 리그 수준에 맞게 옮긴다.

- 기준 리그(이미 시즌 보정이 있는 리그): 프리미어리그·라리가·분데스리가(2007-08 이후).
- 목표 평균(리그 L, 시즌 y) = 기준 리그 A마다 [A의 y 평균 + (L − A의 2025-26 평균 차) + 11.5 × ((L−A의 y 계수 차) − (L−A의 기준 계수 차))]의 평균.
  계수 = UEFA 국가 시즌 계수(kassiesa.net) 앞뒤 3시즌 평균, 기준 계수 = 2019-20~2025-26 시즌 평균, 11.5 = 기존 시즌 조정 기울기(23)의 절반.
- 시즌 평균은 같은 시즌 순위별 값에서 공통 흩어짐 × 순위 곡선을 빼서 구한다. 그 시즌 모든 값을 (목표 − 현재 평균)만큼 같이 옮겨 순위 사이 간격은 그대로.
- 2025-26 이후는 옮기지 않는다(스냅숏 시기). 같은 라벨의 값은 모두 같은 양만큼 옮겨 팀×시즌 통합표 값도 일관.
- 다시 돌려도 결과가 같다(목표는 기준 리그 값만으로 정하므로 두 번째 실행의 이동량은 0).

  python3 tools/league_season_adjust.py          # 이동량 표만 출력
  python3 tools/league_season_adjust.py --apply  # src/data/*.js에 적용(elo/league_season_shift.json이 이미 있으면 --force 필요)


새 선수: 이 리그·시즌의 값을 리그 모델로 새로 계산했으면 elo/league_season_shift.json의 이동량을 더한다.
통합표(elo/)나 다른 선수 자료에서 가져온 값은 이미 옮겨진 값이라 더하지 않는다. 섞이면 elo_table.js 충돌로 드러난다.
players/*/build_*.py를 다시 돌리면 통합표에서 가져온 값(옮겨진 값)과 모델 값(옮기기 전)이 섞이므로,
다시 돌린 파일은 elo_table.js 충돌 목록을 보고 모델 값에만 이동량을 더한다(파일 전체에 더하면 두 번 옮겨짐).
"""
import json, re, glob, os, sys, statistics as st, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LC = [2.51, 1.668, 1.189, 0.842, 0.664, 0.555, 0.43, 0.259, 0.079, -0.096, -0.231, -0.321, -0.412, -0.502, -0.531, -0.649, -0.814, -0.999, -1.103, -1.177, -1.378]
def cv(r, n):
    x = (r - 1) / (n - 1) * 20; i = min(19, int(x)); t = x - i
    return LC[i] + (LC[i + 1] - LC[i]) * t
COUNTRY = {'프리미어리그': 'England', '라리가': 'Spain', '분데스리가': 'Germany', '세리에A': 'Italy', '리그1': 'France', '에레디비시': 'Netherlands', '포르투갈 1부': 'Portugal'}
TARGET = ['세리에A', '리그1', '에레디비시', '포르투갈 1부', '분데스리가']
K = 11.5
LAST_ADJ = 2025          # 시즌 끝 연도 2025(2024-25)까지 옮김
BL_LAST = 2007           # 분데스리가는 2006-07까지만
def teams(lg, y):        # y = 시즌 끝 연도
    if lg == '프리미어리그': return 22 if y <= 1995 else 20
    if lg == '세리에A': return 18 if y <= 2004 else 20
    if lg == '분데스리가': return 20 if y == 1992 else 18
    if lg == '리그1': return 18 if (1998 <= y <= 2002 or y >= 2024) else 20
    if lg == '라리가': return 22 if y in (1996, 1997) else 20
    if lg == '포르투갈 1부': return 16 if 2007 <= y <= 2014 else 18
    return 18
PAT = re.compile(r'^(프리미어리그|라리가|분데스리가|세리에A|리그1|에레디비시|포르투갈 1부) (\d{4})-(\d{2}) (\d+)위(?:/(\d+)팀)?')
C = {k: {int(y): v for y, v in d.items()} for k, d in json.load(open(os.path.join(ROOT, 'elo', 'uefa_country_coef.json'))).items()}
def c3(cn, y): return st.mean([C[cn][t] for t in (y - 1, y, y + 1) if t in C[cn]])
def cref(cn): return st.mean([C[cn][t] for t in range(2020, 2027) if t in C[cn]])

files = sorted(glob.glob(os.path.join(ROOT, 'src', 'data', '*.js')))
data = {}
for f in files:
    t = open(f, encoding='utf-8').read()
    m = re.search(r'const (\w+)_E=(\[.*?\]\]);', t, re.S)
    if not m: continue
    data[f] = (t, m, json.loads(m.group(2)))
# 팀×시즌별 값(같은 팀·시즌·라벨은 한 번만)
pts = collections.defaultdict(dict)
for f, (t, m, E) in data.items():
    for r in E:
        mm = PAT.match(str(r[12]))
        if not mm: continue
        lg, y, rk, n = mm.group(1), int(mm.group(2)) + 1, int(mm.group(4)), mm.group(5)
        n = int(n) if n else teams(lg, y)
        if rk > n: continue
        pts[(lg, y)][r[1]] = (rk, n, r[2])
# 리그별 공통 흩어짐, 시즌 평균
SD, MEAN = {}, {}
for lg in COUNTRY:
    num = den = 0
    for (l, y), v in pts.items():
        if l != lg or len(v) < 2: continue
        L = [(cv(rk, n), e) for rk, n, e in v.values()]
        mx = st.mean(c for c, _ in L); my = st.mean(e for _, e in L)
        num += sum((c - mx) * (e - my) for c, e in L); den += sum((c - mx) ** 2 for c, _ in L)
    SD[lg] = num / den
    for (l, y), v in pts.items():
        if l == lg: MEAN[(lg, y)] = st.mean(e - SD[lg] * cv(rk, n) for rk, n, e in v.values())
SNAP = {lg: MEAN[(lg, 2026)] for lg in COUNTRY}
def target(lg, y):
    anchors = ['프리미어리그', '라리가'] + (['분데스리가'] if (lg != '분데스리가' and y > BL_LAST) else [])
    vals = [MEAN[(a, y)] + (SNAP[lg] - SNAP[a]) + K * ((c3(COUNTRY[lg], y) - c3(COUNTRY[a], y)) - (cref(COUNTRY[lg]) - cref(COUNTRY[a])))
            for a in anchors if (a, y) in MEAN]
    return st.mean(vals) if vals else None
SHIFT = {}
for lg in TARGET:
    ys = sorted(y for (l, y) in MEAN if l == lg)
    last = LAST_ADJ if lg != '분데스리가' else BL_LAST
    for y in ys:
        if y > last: continue
        tg = target(lg, y)
        if tg is not None: SHIFT[(lg, y)] = int(round(tg - MEAN[(lg, y)]))
    # 기준 리그 값이 없는 이른 시즌은 가장 가까운 시즌 이동량
    for y in ys:
        if y <= last and (lg, y) not in SHIFT:
            near = min((abs(y2 - y), d) for (l2, y2), d in SHIFT.items() if l2 == lg)
            SHIFT[(lg, y)] = near[1]
for lg in TARGET:
    print(lg, ' '.join(f"{y-1}-{y%100:02d}:{SHIFT[(l,y)]:+d}" for (l, y) in sorted(SHIFT) if l == lg))
SHIFT_FILE = os.path.join(ROOT, 'elo', 'league_season_shift.json')
if '--apply' in sys.argv and os.path.exists(SHIFT_FILE) and '--force' not in sys.argv:
    sys.exit('이미 적용됨(elo/league_season_shift.json). 다시 옮기려면 --force (두 번 옮기지 않게 주의)')
if '--apply' in sys.argv:
    changed = collections.Counter()
    for f, (t, m, E) in data.items():
        n = 0
        for r in E:
            mm = PAT.match(str(r[12]))
            if not mm: continue
            k = (mm.group(1), int(mm.group(2)) + 1)
            d = SHIFT.get(k, 0)
            if d: r[2] = int(r[2]) + d; n += 1
        if n:
            nt = t[:m.start(2)] + json.dumps(E, ensure_ascii=False, separators=(',', ':')) + t[m.end(2):]
            open(f, 'w', encoding='utf-8').write(nt); changed[os.path.basename(f)] = n
    old = json.load(open(SHIFT_FILE)) if os.path.exists(SHIFT_FILE) else {}   # 누적(--force로 다시 옮겨도 처음부터의 총 이동량)
    tot = dict(old)
    for (l, y), d in SHIFT.items():
        k = f'{l}|{y-1}-{y%100:02d}'; tot[k] = tot.get(k, 0) + d
    json.dump(dict(sorted(tot.items())), open(SHIFT_FILE, 'w'), ensure_ascii=False, indent=0)
    print('적용:', len(changed), '파일,', sum(changed.values()), '행')
