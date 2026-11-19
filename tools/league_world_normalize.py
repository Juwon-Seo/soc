#!/usr/bin/env python3
"""비유럽 리그 시즌 수준(v1.217, 사용자 결정 2026-11-19)

유럽 15개 리그(tools/league_era_normalize.py)와 같은 척도에 비유럽 리그를 올린다.
  목표 평균(리그 L, 시즌 y) = Opta_L → Elo  +  0.5 × 144.5 × [ln 몸값비율_L(y) − ln 몸값비율_L(기준)]
  - Opta_L → Elo: 2026-11-19 Opta 파워 랭킹 리그 평균을 유럽 13개 리그의 v1.216 2025-26 목표 평균에 회귀(Elo = a + b × Opta, r≈0.96).
    대륙 사이 수준은 Opta(경기 결과 기반)로 정한다(Transfermarkt 몸값은 남미·일본을 200~320 낮게, 걸프를 50~70 높게 봄).
  - 몸값비율_L(y) = 그 시즌 Transfermarkt 리그 팀 평균 몸값 ÷ 그 시즌 5대 리그 평균(기하평균). 유럽 15개 리그에서
    Elo = 1748.3 + 144.5 × ln(비율), r = 0.91. 시즌 사이 변화만 쓰고(대륙 쏠림 제거), 경제 요인이 섞여 있어 절반(0.5)만 반영.
  - 기준 = 2025-26(달력 연도 리그는 2026). 몸값 자료가 없는 시즌은 가장 가까운 시즌 값.
  - 라벨이 그 나라 이름(리그 이름)으로 시작하는 모든 행(2부 이하·순위 없는 추정값 포함)을 그 나라·시즌 이동량만큼 옮긴다.
    시즌 평균은 'YYYY(-YY) … N위' 라벨 행으로 계산(공통 흩어짐 × 순위 곡선을 뺀 평균). 순위 없는 행은 경기 날짜로 시즌.
  - 다시 돌리면 이동 0. 결과 목표 평균은 elo/league_world_mean.json.

  python3 tools/league_world_normalize.py            # 표만
  python3 tools/league_world_normalize.py --apply
자료: elo/opta_league_2026-11-19.json, elo/tm_league_values.csv(Transfermarkt 리그 시작 페이지, 2004-05~2026-27, 2026-11 수집)
"""
import json, re, glob, os, sys, csv, math, statistics as st, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LC = [2.51, 1.668, 1.189, 0.842, 0.664, 0.555, 0.43, 0.259, 0.079, -0.096, -0.231, -0.321, -0.412, -0.502, -0.531, -0.649, -0.814, -0.999, -1.103, -1.177, -1.378]
def cv(r, n):
    n = max(n, 2); r = min(max(r, 1), n)
    x = (r - 1) / (n - 1) * 20; i = min(19, int(x)); t = x - i
    return LC[i] + (LC[i + 1] - LC[i]) * t
MV_SLOPE, SHRINK = 144.5, 0.5
# 나라: (라벨 앞부분들, Opta 리그 키, TM 코드들, 달력 연도 여부, 기본 팀 수)
LG = {
 'USA':  (['MLS', 'USL', 'NASL', '미국'], 'US Major League Soccer|USA', ['MLS1'], True, 20),
 'BRA':  (['브라질', '리우 주', '가우슈 주', '파울리스타', '카리오카'], 'Brazilian Serie A|Brazil', ['BRA1'], True, 20),
 'ARG':  (['아르헨티나'], 'Liga Profesional Argentina|Argentina', ['ARG1', 'ARGC', 'AR1N'], True, 20),
 'MEX':  (['리가MX', '멕시코'], 'Mexican Primera|Mexico', ['MEXA', 'MEX1'], False, 18),
 'KSA':  (['사우디'], 'Saudi Arabian League|Saudi Arabia', ['SA1'], False, 16),
 'QAT':  (['카타르'], 'Qatar Stars League|Qatar', ['QSL'], False, 12),
 'UAE':  (['UAE'], 'UAE Pro League|United Arab Emirates', ['UAE1'], False, 14),
 'JPN':  (['J1', 'J2', 'J3', '일본'], 'Japanese J1 League|Japan', ['JAP1'], True, 18),
 'KOR':  (['K리그', '한국'], 'Korean K-League 1|Korea Republic', ['RSK1'], True, 12),
 'CHN':  (['중국'], 'Chinese Super League|China PR', ['CSL'], True, 16),
 'AUS':  (['호주', 'A리그'], 'Australian A-League Men|Australia', ['AUS1'], False, 10),
 'IND':  (['인도'], 'Indian Super League|India', ['IND1'], False, 10),
 'URU':  (['우루과이'], 'Uruguay Liga AUF|Uruguay', ['URU1', 'URUC'], True, 16),
 'COL':  (['콜롬비아'], 'Colombia Primera A|Colombia', ['COLP', 'COL1'], True, 20),
 'CHI':  (['칠레'], 'Chile Primera|Chile', ['CHLA', 'CHL1', 'CLPD'], True, 16),
 'PAR':  (['파라과이'], 'Paraguay Primera División|Paraguay', ['PR1A', 'PR1C'], True, 12),
 'PER':  (['페루'], 'Peru Liga 1|Peru', ['PERC', 'TDeA', 'TDeC'], True, 18),
 'ECU':  (['에콰도르'], 'Ecuador Liga Pro|Ecuador', ['ECPE', 'ECSE', 'EL1A', 'EL1S', 'EC1N'], True, 16),
 'VEN':  (['베네수엘라'], 'Venezuela Primera División|Venezuela', ['VZ1A', 'VZ1C', 'VZ1L'], True, 18),
 'BOL':  (['볼리비아'], 'Bolivia Primera División|Bolivia', [], True, 16),
 'UZB':  (['우즈베키스탄'], 'Super League|Uzbekistan', ['UZ1'], True, 14),
 'EGY':  (['이집트'], 'Egyptian Premier League|Egypt', ['EGY1'], False, 18),
 'IRN':  (['이란'], 'Persian Gulf Pro League|Iran', ['IRN1'], False, 16),
 'IRQ':  (['이라크'], 'Iraqi League|Iraq', [], False, 20),
 'HON':  (['온두라스'], 'Honduras Liga Nacional|Honduras', [], False, 10),
 'CAN':  (['캐나다'], 'Canadian Premier League|Canada', [], True, 8),
 'HKG':  (['홍콩'], 'Premier League|Hong Kong, China', [], False, 10),
}
OPTA = json.load(open(os.path.join(ROOT, 'elo', 'opta_league_2026-11-19.json')))['리그']
# Opta → Elo: 유럽 13개 리그 v1.216 2025-26 목표 평균에 회귀
EU_OPTA = {'English Premier League|England': 'GB', 'Spanish La Liga|Spain': 'ES', 'German Bundesliga|Germany': 'DE', 'Italian Serie A|Italy': 'IT', 'French Ligue 1|France': 'FR'}
def opta_fit():
    sys_argv = sys.argv; sys.argv = ['x']
    import io, contextlib
    G = {'__file__': os.path.join(ROOT, 'tools', 'league_era_normalize.py'), '__name__': 'x'}
    src = open(G['__file__'], encoding='utf-8').read().rsplit("if '--apply' in sys.argv:", 1)[0]
    with contextlib.redirect_stdout(io.StringIO()): exec(compile(src, 'era', 'exec'), G)
    sys.argv = sys_argv
    pairs = [('English Premier League', '프리미어리그', None), ('Spanish La Liga', '라리가', None), ('German Bundesliga', '분데스리가', None), ('Italian Serie A', '세리에A', None),
             ('French Ligue 1', '리그1', None), ('Dutch Eredivisie', '에레디비시', None), ('Portuguese Primeira Liga', '포르투갈 1부', None), ('Turkish Super Lig', None, 'Turkey'),
             ('Belgian Pro League', None, 'Belgium'), ('Austrian Bundesliga', None, 'Austria'), ('Greek Super League', None, 'Greece'), ('Scottish Premiership', None, 'Scotland'), ('Ukrainian Premier League', None, 'Ukraine')]
    xs, ys = [], []
    for name, lg, cn in pairs:
        k = next((k for k in OPTA if k.split('|')[0].lower().startswith(name.lower()[:12]) and any(w in k for w in name.split()[:1])), None)
        if not k: continue
        xs.append(OPTA[k]); ys.append(G['target'](lg, 2026) if lg else G['otarget'](cn, 2026))
    mx, my = st.mean(xs), st.mean(ys); b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return my - b * mx, b, r, len(xs)
OA, OB, OR, ON = opta_fit()
# 몸값 비율
TV = collections.defaultdict(dict)
for r in csv.DictReader(open(os.path.join(ROOT, 'elo', 'tm_league_values.csv'))):
    TV[r['code']][int(r['saison_id']) + 1] = float(r['mean_club_value_m'])   # 끝 연도(달력 연도 리그는 그 연도)
def big5(end):
    v = [TV[c][end] for c in ('GB1', 'ES1', 'L1', 'IT1', 'FR1') if end in TV[c]]
    return math.exp(st.mean(math.log(x) for x in v)) if len(v) == 5 else None
def big5cal(C):
    a = [big5(e) for e in (C, C + 1) if big5(e)]
    return math.exp(st.mean(math.log(x) for x in a)) if a else None
LR = {}   # (나라, 연도) -> ln 비율
for cc, (pre, ok, codes, cal, nt) in LG.items():
    tmp = collections.defaultdict(list)
    for c in codes:
        for y, m in TV.get(c, {}).items():
            b = big5cal(y) if cal else big5(y)
            if b and m > 0: tmp[y].append(math.log(m / b))
    for y, v in tmp.items(): LR[(cc, y)] = st.mean(v)
def lr(cc, y):
    ys = [y2 for (c, y2) in LR if c == cc]
    if not ys: return None
    return LR[(cc, min(ys, key=lambda y2: (abs(y2 - y), -y2)))]
def target(cc, y):
    lv0 = OA + OB * OPTA[LG[cc][1]]
    a, ref = lr(cc, y), lr(cc, 2026)
    return lv0 if a is None or ref is None else lv0 + SHRINK * MV_SLOPE * (a - ref)
X2 = ('브라질 세리에 B', 'J2리그', '아르헨티나 2부', 'USL', 'NASL', '사우디 2부', '카타르 2부')   # v1.219부터 tools/league_second_tier_x.py가 맡음
def country(lv):
    if lv.startswith(X2): return None
    for cc, (pre, *_r) in LG.items():
        for p in pre:
            if lv.startswith(p): return cc
    return None
YPAT = re.compile(r'(\d{4})(?:-(\d{2}))?[^\d(]*?(\d+)위(?:/(\d+)팀)?')
def label_year(lv, cal):
    m = re.search(r'(\d{4})(?:-(\d{2}))?', lv)
    if not m: return None
    y = int(m.group(1)); return y + 1 if m.group(2) else y
def date_year(d, cal):
    y, mo = int(d[:4]), int(d[5:7])
    return y if cal else (y + 1 if mo >= 8 else y)
def is_lower(lv): return bool(re.search(r'[2-9]부|세리에 [BCD]|J[23]|2부|하위|주 리그|USL|NASL', lv.split(' (')[0]))
data = {}
for f in sorted(glob.glob(os.path.join(ROOT, 'src', 'data', '*.js'))):
    t = open(f, encoding='utf-8').read(); m = re.search(r'const (\w+)_E=(\[.*?\]\]);', t, re.S)
    if m: data[f] = (t, m, json.loads(m.group(2)))
PTS = collections.defaultdict(dict)
for f, (t, m, E) in data.items():
    for r in E:
        lv = str(r[12]); cc = country(lv)
        if not cc or is_lower(lv): continue
        mm = YPAT.search(lv)
        if not mm: continue
        y = label_year(lv, LG[cc][3]); rk = int(mm.group(3)); n = int(mm.group(4)) if mm.group(4) else LG[cc][4]
        if y and rk <= n: PTS[(cc, y)][r[1]] = (rk, n, r[2])
SD, MEAN = {}, {}
for cc in LG:
    num = den = 0
    for (c, y), v in PTS.items():
        if c != cc or len(v) < 2: continue
        L = [(cv(rk, n), e) for rk, n, e in v.values()]
        mx = st.mean(a for a, _ in L); my = st.mean(e for _, e in L)
        num += sum((a - mx) * (e - my) for a, e in L); den += sum((a - mx) ** 2 for a, _ in L)
    SD[cc] = num / den if den > 0 and num > 0 else 60.0
    for (c, y), v in PTS.items():
        if c == cc: MEAN[(cc, y)] = st.mean(e - SD[cc] * cv(rk, n) for rk, n, e in v.values())
SHIFT = {k: int(round(target(k[0], k[1]) - MEAN[k])) for k in MEAN}
def shift_for(cc, y):
    if (cc, y) in SHIFT: return SHIFT[(cc, y)]
    ys = [y2 for (c, y2) in SHIFT if c == cc]
    return SHIFT[(cc, min(ys, key=lambda y2: abs(y2 - y)))] if ys else 0
print(f'Opta → Elo = {OA:.1f} + {OB:.2f} × Opta (유럽 {ON}개 리그, r={OR:.3f})')
for cc in LG:
    ys = sorted(y for (c, y) in MEAN if c == cc)
    if ys: print(cc, f'Opta {OPTA[LG[cc][1]]:.1f} → {OA + OB * OPTA[LG[cc][1]]:.0f} |', ' '.join(f'{y}:{target(cc, y):.0f}({SHIFT[(cc, y)]:+d})' for y in ys))
if '--apply' in sys.argv:
    cnt = 0
    for f, (t, m, E) in data.items():
        n = 0
        for r in E:
            lv = str(r[12]); cc = country(lv)
            if not cc: continue
            cal = LG[cc][3]
            y = label_year(lv, cal) or date_year(str(r[9]), cal)   # 라벨에 시즌이 있으면 그 시즌(같은 팀·시즌 값이 갈리지 않게)
            d = shift_for(cc, y)
            if d: r[2] = int(r[2]) + d; n += 1
        if n:
            open(f, 'w', encoding='utf-8').write(t[:m.start(2)] + json.dumps(E, ensure_ascii=False, separators=(',', ':')) + t[m.end(2):]); cnt += n
    out = {'설명': '비유럽 리그 시즌 목표 평균(Opta 수준 + 몸값 변화 절반). 키 = 나라|연도(달력 연도 리그는 그 해, 그 밖은 시즌 끝 연도)',
           'Opta→Elo': [round(OA, 1), round(OB, 3)], '흩어짐': {c: round(v, 1) for c, v in SD.items()},
           '평균': {f'{cc}|{y}': round(target(cc, y), 1) for cc in LG for y in range(1990, 2028) if LG[cc][1] in OPTA}}
    json.dump(out, open(os.path.join(ROOT, 'elo', 'league_world_mean.json'), 'w'), ensure_ascii=False, indent=0)
    print('적용:', cnt, '행')
