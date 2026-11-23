#!/usr/bin/env python3
"""리그 시즌 수준 정규화(v1.216, 사용자 결정 2026-11-19)

목표: 시즌마다 (1) 5대 리그 Elo 평균은 같게(2025-26 ClubElo 스냅숏 평균) 고정해 시대에 따른 일괄 유불리를 없애고,
(2) 리그 사이 간격은 그 시즌 UEFA 국가 계수(앞뒤 5시즌 평균) 차이로 정한다.

  목표 평균(리그 L, 시즌 y) = B + s × (c3_L(y) − c3_5(y)) × (A_ref / A(y))
   B     = 2025-26 5대 리그 평균(스냅숏), s = 22.2 Elo/계수 1점(스냅숏 7개 리그 Elo ~ 직전 3시즌 계수 회귀, r=0.96)
   c3 = 앞뒤 5시즌 평균 시즌 계수, c3_5 = 그 시즌 5대 리그 c3 평균, A(y) = c3_5(y) (포인트 팽창 제거), A_ref = A(2025-26)
  리그: 프리미어리그·라리가·분데스리가·세리에A·리그1·에레디비시·포르투갈 1부. 2025-26 이후도 같은 공식(v1.216 사용자 결정).
  시즌 값 전체를 (목표 − 현재 평균)만큼 옮겨 순위 사이 간격 유지. 같은 나라 2부도 같은 양만큼 옮김.
  시즌 평균 = 순위별 값 − 공통 흩어짐 × 순위 곡선의 평균. 결과 목표 평균·흩어짐은 elo/league_season_mean.json.

  python3 tools/league_era_normalize.py            # 표만
  python3 tools/league_era_normalize.py --apply    # src/data/*.js 적용(이미 맞춰져 있으면 이동 0)
새 선수: 이 리그·시즌 팀을 새로 계산하면 elo/league_season_mean.json의 평균 + 흩어짐 × 순위 곡선(2부는 1부 이동량을 더한 기존 2부 모형).
"""
import json, re, glob, os, sys, statistics as st, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LC = [2.51, 1.668, 1.189, 0.842, 0.664, 0.555, 0.43, 0.259, 0.079, -0.096, -0.231, -0.321, -0.412, -0.502, -0.531, -0.649, -0.814, -0.999, -1.103, -1.177, -1.378]
def cv(r, n):
    x = (r - 1) / (n - 1) * 20; i = min(19, int(x)); t = x - i
    return LC[i] + (LC[i + 1] - LC[i]) * t
LEAGUE = {'프리미어리그': 'England', '라리가': 'Spain', '분데스리가': 'Germany', '세리에A': 'Italy', '리그1': 'France', '에레디비시': 'Netherlands', '포르투갈 1부': 'Portugal'}
BIG5 = ['프리미어리그', '라리가', '분데스리가', '세리에A', '리그1']
SECOND = {}   # v1.218부터 2부는 tools/league_second_tier.py가 맡음(1부 이동의 절반 + Opta 간격). 예전 대응: {'챔피언십': '프리미어리그', '챔피언십(2부)': '프리미어리그', '세군다': '라리가', '세군다(2부)': '라리가', '2. 분데스리가': '분데스리가',           '세리에B': '세리에A', '리그2': '리그1', '리그2(프랑스 2부)': '리그1', '프랑스 리그2': '리그1', '에이르스터 디비시(네덜란드 2부)': '에레디비시', '포르투갈 2부': '포르투갈 1부'}
S_SLOPE = 22.2; LAST = 9999   # v1.216 확정: 2025-26 이후도 공식(스냅숏은 기준 평균 B·기울기를 정하는 데만 씀)
def teams(lg, y):
    if lg == '프리미어리그': return 22 if y <= 1995 else 20
    if lg == '세리에A': return 18 if y <= 2004 else 20
    if lg == '분데스리가': return 20 if y == 1992 else 18
    if lg == '리그1': return 18 if (1998 <= y <= 2002 or y >= 2024) else 20
    if lg == '라리가': return 22 if y in (1996, 1997) else 20
    if lg == '포르투갈 1부': return 16 if 2007 <= y <= 2014 else 18
    return 18
NAMES = '|'.join(re.escape(x) for x in sorted(list(LEAGUE) + list(SECOND), key=len, reverse=True))
PAT = re.compile(r'^(' + NAMES + r') (\d{4})-(\d{2})(?: (\d+)위(?:/(\d+)팀)?)?')
C = {k: {int(y): v for y, v in d.items()} for k, d in json.load(open(os.path.join(ROOT, 'elo', 'uefa_country_coef.json'))).items() if not k.startswith('_')}
def c3(cn, y):
    v = [C[cn][t] for t in range(y - 2, y + 3) if t in C[cn]]
    if not v: v = [C[cn][max(C[cn])]] if y > max(C[cn]) else [C[cn][min(C[cn])]]
    return st.mean(v)   # 앞뒤 5시즌(공식 랭킹과 같은 5시즌 폭)
data = {}
for f in sorted(glob.glob(os.path.join(ROOT, 'src', 'data', '*.js'))):
    t = open(f, encoding='utf-8').read()
    m = re.search(r'const (\w+)_E=(\[.*?\]\]);', t, re.S)
    if m: data[f] = (t, m, json.loads(m.group(2)))
pts = collections.defaultdict(dict)
# v1.288: 5대 리그 중 승점·득실 표가 있는 시즌(tools/league_points.py)은 순위 곡선이 아니므로 평균·흩어짐 추정에서 빼고 목표 평균 그대로 둔다.
PTS_SEASONS = set(json.load(open(os.path.join(ROOT, 'elo', 'league_points_big5.json'), encoding='utf-8'))['seasons'])
PTS_DONE = set()
for f, (t, m, E) in data.items():
    for r in E:
        mm = PAT.match(str(r[12]))
        if not mm or mm.group(1) not in LEAGUE or not mm.group(4): continue
        if f"{mm.group(1)} {mm.group(2)}-{mm.group(3)}" in PTS_SEASONS: PTS_DONE.add((mm.group(1), int(mm.group(2)) + 1)); continue
        lg, y, rk = mm.group(1), int(mm.group(2)) + 1, int(mm.group(4))
        n = int(mm.group(5)) if mm.group(5) else teams(lg, y)
        if rk <= n: pts[(lg, y)][r[1]] = (rk, n, r[2])
SD, MEAN = {}, {}
SD_SAVED = json.load(open(os.path.join(ROOT, 'elo', 'league_season_mean.json'), encoding='utf-8'))['흩어짐']
for lg in LEAGUE:
    num = den = 0
    for (l, y), v in pts.items():
        if l != lg or len(v) < 2: continue
        L = [(cv(rk, n), e) for rk, n, e in v.values()]
        mx = st.mean(c for c, _ in L); my = st.mean(e for _, e in L)
        num += sum((c - mx) * (e - my) for c, e in L); den += sum((c - mx) ** 2 for c, _ in L)
    SD[lg] = num / den if den > 1e-9 else SD_SAVED[lg]
    for (l, y), v in pts.items():
        if l == lg: MEAN[(lg, y)] = st.mean(e - SD[lg] * cv(rk, n) for rk, n, e in v.values())
for (lg, y) in PTS_DONE: MEAN[(lg, y)] = None   # 아래에서 목표 평균으로 채움(이동 0)
B = 1762.1   # 2025-26 ClubElo 스냅숏(2026-10-30) 5대 리그 평균. 상수로 고정(다시 돌려도 같은 결과)
c5 = lambda y: st.mean(c3(LEAGUE[l], y) for l in BIG5)
AREF = c5(2026)
def target(lg, y): return B + S_SLOPE * (c3(LEAGUE[lg], y) - c5(y)) * (AREF / c5(y))
for (lg, y) in list(MEAN):
    if MEAN[(lg, y)] is None: MEAN[(lg, y)] = target(lg, y)
SHIFT = {}
for (lg, y) in MEAN:
    if y <= LAST: SHIFT[(lg, y)] = int(round(target(lg, y) - MEAN[(lg, y)]))
def shift_for(lab_lg, y):
    top = SECOND.get(lab_lg, lab_lg)
    if y > LAST or top not in LEAGUE: return 0
    if (top, y) in SHIFT: return SHIFT[(top, y)]
    ys = [y2 for (l, y2) in SHIFT if l == top]
    if not ys: return 0
    if y < min(ys): return SHIFT[(top, min(ys))]
    if y > max(ys): return SHIFT[(top, max(ys))]
    near = min(ys, key=lambda y2: abs(y2 - y)); return SHIFT[(top, near)]
print('목표 평균(5대 리그 평균 B=%.1f 고정, 기울기 %.1f):' % (B, S_SLOPE))
for y in range(1992, 2027):
    row = []
    for lg in LEAGUE:
        if (lg, y) in MEAN:
            tg = target(lg, y)
            row.append(f"{lg[:3]}{tg:.0f}({SHIFT.get((lg, y), 0):+d})")
    print(f"{y-1}-{y%100:02d} " + ' '.join(row))
if '--apply' in sys.argv:
    cnt = collections.Counter()
    for f, (t, m, E) in data.items():
        n = 0
        for r in E:
            mm = PAT.match(str(r[12]))
            if not mm: continue
            d = shift_for(mm.group(1), int(mm.group(2)) + 1)
            if d: r[2] = int(r[2]) + d; n += 1
        if n:
            open(f, 'w', encoding='utf-8').write(t[:m.start(2)] + json.dumps(E, ensure_ascii=False, separators=(',', ':')) + t[m.end(2):]); cnt[f] = n
    out = {'설명': '리그·시즌(끝 연도 기준 표기 YYYY-YY) 목표 평균과 리그 흩어짐. 새 팀 = 평균 + 흩어짐 × 순위 곡선', '흩어짐': {l: round(SD[l], 1) for l in LEAGUE},
           '평균': {f"{l}|{y-1}-{y%100:02d}": round(target(l, y), 1) for (l, y) in sorted(MEAN)}}
    json.dump(out, open(os.path.join(ROOT, 'elo', 'league_season_mean.json'), 'w'), ensure_ascii=False, indent=0)
    print('적용:', len(cnt), '파일', sum(cnt.values()), '행')

# ── 다른 UEFA 리그(v1.216): 튀르키예·벨기에·오스트리아·그리스·우크라이나·러시아·스위스·스코틀랜드, v1.222에 15개 나라 추가 ──
# 새 15개 나라는 순위 없는 행도 라벨 연도로 시즌을 정함(같은 팀·시즌 값이 갈리지 않게). 기존 8개 나라는 예전 방식(경기 날짜) 그대로.
# 라벨이 나라 이름(또는 리그 이름)으로 시작하는 모든 행을 그 나라의 시즌 이동량만큼 옮긴다(하부 리그·순위 없는 추정값 포함).
# 시즌 평균은 'YYYY-YY N위' 라벨 행으로 계산하고, 시즌은 경기 날짜(8월 1일 기준)로 정한다. 모든 시즌(2025-26 이후 포함)에 공식 적용.
OTHER = [('쉬페르리그', 'Turkey'), ('튀르키예', 'Turkey'), ('벨기에', 'Belgium'), ('오스트리아', 'Austria'), ('그리스', 'Greece'),
         ('우크라이나', 'Ukraine'), ('러시아', 'Russia'), ('스위스', 'Switzerland'), ('스코틀랜드', 'Scotland'),
         # v1.222: UEFA 랭킹 10~30위권 15개 나라 추가
         ('체코', 'Czechia'), ('폴란드', 'Poland'), ('엑스트라클라사', 'Poland'), ('덴마크', 'Denmark'), ('노르웨이', 'Norway'), ('엘리테세리엔', 'Norway'),
         ('키프로스', 'Cyprus'), ('스웨덴', 'Sweden'), ('알스벤스칸', 'Sweden'), ('수페레탄', 'Sweden'), ('크로아티아', 'Croatia'), ('이스라엘', 'Israel'),
         ('헝가리', 'Hungary'), ('세르비아', 'Serbia'), ('루마니아', 'Romania'), ('슬로베니아', 'Slovenia'), ('아제르바이잔', 'Azerbaijan'),
         ('슬로바키아', 'Slovakia'), ('불가리아', 'Bulgaria')]
OCAL = {'Norway', 'Sweden'}   # 달력 연도 리그: 시즌 Y는 UEFA 시즌 끝 연도 Y와 Y+1 목표의 평균
OTEAMS = {'Turkey': 18, 'Belgium': 18, 'Austria': 10, 'Greece': 16, 'Ukraine': 16, 'Russia': 16, 'Switzerland': 10, 'Scotland': 12,
          'Czechia': 16, 'Poland': 18, 'Denmark': 12, 'Norway': 16, 'Cyprus': 14, 'Sweden': 16, 'Croatia': 10, 'Israel': 14, 'Hungary': 12,
          'Serbia': 16, 'Romania': 16, 'Slovenia': 10, 'Azerbaijan': 10, 'Slovakia': 12, 'Bulgaria': 14}
OPAT = re.compile(r'^(\S+(?: (?:1부|프리미어리그|슈퍼리그|분데스리가))?) (\d{4})-(\d{2}) (\d+)위(?:/(\d+)팀)?')
def octry(lv):
    if lv.startswith('튀르키예 2부'): return None   # v1.219부터 tools/league_second_tier_x.py가 맡음
    for pre, cn in OTHER:
        if lv.startswith(pre) and not lv.startswith('오스트리아 분데스리가') or (pre == '오스트리아' and lv.startswith('오스트리아')):
            if lv.startswith(pre): return cn
    return None
def dseason(d, cn=None):  # 날짜 → 시즌 끝 연도(달력 연도 리그는 그 해)
    y, m = int(d[:4]), int(d[5:7])
    return y if cn in OCAL else (y + 1 if m >= 8 else y)
CPAT = re.compile(r'^\S+(?: (?:1부|프리미어리그|슈퍼리그|분데스리가))? (\d{4}) (\d+)위(?:/(\d+)팀)?')
def oparse(lv, cn):  # 순위 라벨 → (시즌 키, 순위, 팀 수) 또는 None
    mm = OPAT.match(lv)
    if mm and mm.group(4): return int(mm.group(2)) + 1, int(mm.group(4)), (int(mm.group(5)) if mm.group(5) else None)
    if cn in OCAL:
        mm = CPAT.match(lv)
        if mm: return int(mm.group(1)), int(mm.group(2)), (int(mm.group(3)) if mm.group(3) else None)
    return None
def oseason(lv, d, cn):  # 행의 시즌 키: 라벨 연도(YYYY-YY는 끝 연도, 달력 연도 리그는 YYYY) 또는 경기 날짜
    m = re.search(r'(\d{4})-(\d{2})', lv)
    if m: return int(m.group(1)) + 1
    if cn in OCAL:
        m = re.search(r'(\d{4})', lv)
        if m: return int(m.group(1))
    return dseason(d, cn)
def is_lower(lv): return bool(re.match(r'^\S+ [2-9]부', lv)) or '2부' in lv.split(' (')[0]
OD = collections.defaultdict(dict)
for f, (t, m, E) in data.items():
    for r in E:
        lv = str(r[12]); cn = octry(lv)
        if not cn or is_lower(lv): continue
        pr = oparse(lv, cn)
        if not pr: continue
        y, rk, n = pr; n = n or OTEAMS[cn]
        if rk <= n: OD[(cn, y)][r[1]] = (rk, n, r[2])
OSD, OMEAN = {}, {}
for cn in OTEAMS:
    num = den = 0
    for (c, y), v in OD.items():
        if c != cn or len(v) < 2: continue
        L = [(cv(rk, n), e) for rk, n, e in v.values()]
        mx = st.mean(c_ for c_, _ in L); my = st.mean(e for _, e in L)
        num += sum((c_ - mx) * (e - my) for c_, e in L); den += sum((c_ - mx) ** 2 for c_, _ in L)
    OSD[cn] = num / den if den else 100
    for (c, y), v in OD.items():
        if c == cn: OMEAN[(cn, y)] = st.mean(e - OSD[cn] * cv(rk, n) for rk, n, e in v.values())
def otarget_raw(cn, y): return B + S_SLOPE * (c3(cn, y) - c5(y)) * (AREF / c5(y))
def otarget(cn, y): return (otarget_raw(cn, y) + otarget_raw(cn, y + 1)) / 2 if cn in OCAL else otarget_raw(cn, y)
OSHIFT = {k: int(round(otarget(k[0], k[1]) - OMEAN[k])) for k in OMEAN if k[0] in C}
def oshift_for(cn, y):
    if (cn, y) in OSHIFT: return OSHIFT[(cn, y)]
    ys = [y2 for (c, y2) in OSHIFT if c == cn]
    if not ys: return 0
    return OSHIFT[(cn, min(ys, key=lambda y2: abs(y2 - y)))]
print('\n다른 UEFA 리그 목표 평균(이동):')
for cn in OTEAMS:
    print(cn, ' '.join(f"{(str(y) if cn in OCAL else f'{y-1}-{y%100:02d}')}:{otarget(cn,y):.0f}({OSHIFT[(cn,y)]:+d})" for (c, y) in sorted(OSHIFT) if c == cn))
if '--apply' in sys.argv:
    cnt = 0
    for f in data:
        t = open(f, encoding='utf-8').read(); m = re.search(r'const (\w+)_E=(\[.*?\]\]);', t, re.S); E = json.loads(m.group(2)); n = 0
        for r in E:
            lv = str(r[12]); cn = octry(lv)
            if not cn: continue
            pr = oparse(lv, cn)
            y = pr[0] if (pr and not is_lower(lv)) else (oseason(lv, str(r[9]), cn) if cn in OCAL or cn not in ('Turkey', 'Belgium', 'Austria', 'Greece', 'Ukraine', 'Russia', 'Switzerland', 'Scotland') else dseason(str(r[9])))
            d = oshift_for(cn, y)
            if d: r[2] = int(r[2]) + d; n += 1
        if n:
            open(f, 'w', encoding='utf-8').write(t[:m.start(2)] + json.dumps(E, ensure_ascii=False, separators=(',', ':')) + t[m.end(2):]); cnt += n
    print('다른 UEFA 리그 적용:', cnt, '행')
