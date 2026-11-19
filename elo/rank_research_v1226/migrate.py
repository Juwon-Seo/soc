#!/usr/bin/env python3
"""v1.226 이전: 조사한 상대 순위로 라벨을 표준 형식으로 바꾸고, 하부 리그 기준점 표를 만든다.
python3 migrate.py            # 바꿀 내용 요약(쓰지 않음)
python3 migrate.py --write    # src/data/*.js 라벨·값, elo/league_lower_base.json 쓰기
"""
import csv, glob, json, re, os, sys, collections, statistics as st, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = '/home/user/soc'
spec = importlib.util.spec_from_file_location('lra', ROOT + '/tools/league_rank_apply.py'); M = importlib.util.module_from_spec(spec)
argv = sys.argv; sys.argv = ['x']; spec.loader.exec_module(M); sys.argv = argv
WRITE = '--write' in sys.argv

EN = {'Czech Republic': 'Czechia', 'Republic of Ireland': 'Ireland', 'Bosnia and Herzegovina': 'Bosnia-Herzegovina', 'FR Yugoslavia': 'Serbia',
      'Serbia and Montenegro': 'Serbia', 'Yugoslavia': 'Serbia', 'United States': 'USA', 'USA': 'USA', 'Brazil': 'BRA', 'Argentina': 'ARG', 'Mexico': 'MEX',
      'Saudi Arabia': 'KSA', 'Qatar': 'QAT', 'United Arab Emirates': 'UAE', 'UAE': 'UAE', 'Japan': 'JPN', 'South Korea': 'KOR', 'Korea Republic': 'KOR',
      'China': 'CHN', 'Australia': 'AUS', 'India': 'IND', 'Uruguay': 'URU', 'Colombia': 'COL', 'Chile': 'CHI', 'Paraguay': 'PAR', 'Peru': 'PER',
      'Ecuador': 'ECU', 'Venezuela': 'VEN', 'Bolivia': 'BOL', 'Uzbekistan': 'UZB', 'Egypt': 'EGY', 'Iran': 'IRN', 'Iraq': 'IRQ', 'Honduras': 'HON',
      'Canada': 'CAN', 'Hong Kong': 'HKG', 'DR Congo': 'Congo DR', 'Türkiye': 'Turkey', 'Soviet Union': 'Soviet Union', 'USSR': 'Soviet Union',
      'Liechtenstein': 'Switzerland'}   # 리히텐슈타인 팀(파두츠)은 스위스 리그
PREF_KO = {'Serbia': '세르비아', 'KSA': '사우디', 'USA': '미국'}
KEY2KO = {}
for ko, k in M.KO.items():
    if k not in KEY2KO or len(ko) < len(KEY2KO[k]): KEY2KO[k] = ko
KEY2KO.update(PREF_KO)
def key_of(country):
    k = EN.get(country, country)
    if k not in KEY2KO: raise KeyError(country)
    return k
S2LAB = {'England': '챔피언십', 'Spain': '세군다', 'Germany': '2. 분데스리가', 'Italy': '세리에B', 'France': '리그2',
         'Netherlands': '에이르스터 디비시(네덜란드 2부)', 'Portugal': '포르투갈 2부'}
def is_anchor(key, tier):
    if tier == 1: return key not in M.BIG and key not in M.ERA['C'] and key not in M.WCC
    if tier == 2 and (key in M.BIG or key in M.SX_KEY): return False
    return True
def season_parts(s):
    m = re.match(r'^(\d{4})(?:[-–/](\d{2,4}))?$', s.strip())
    if not m: return None
    y1 = int(m.group(1))
    if m.group(2): return f'{y1}-{str(y1 + 1)[2:]}', y1 + 1, False
    return str(y1), y1, True
def head(key, tier, season, rank, n):
    s = f'{season} {rank}위/{n}팀'
    if tier == 1 and key in M.BIG: return f'{M.BIG[key]} {s}'
    if tier == 2 and key in S2LAB: return f'{S2LAB[key]} {s}'
    if tier == 2 and key in M.SX_KEY: return f'{M.SX_KEY[key]} {s}'
    return f'{KEY2KO[key]} {tier}부 {s}'
def extra(r, key, tier):
    bits = []
    ln = (r.get('league_name') or '').strip(); gp = (r.get('group') or '').strip()
    if ln and not (tier == 1 and key in M.BIG): bits.append(ln + (' ' + gp if gp else ''))
    elif gp: bits.append(gp)
    rt = r.get('rank_type', '')
    if rt == 'stage': bits.append('경기 날짜에 진행 중이던 단계 순위')
    if rt == 'aggregate': bits.append('연간 합산 순위')
    if rt == 'current': bits.append('2026년 11월 중순 현재 순위')
    if rt == 'final_after_playoffs': bits.append('플레이오프·스플릿 뒤 최종 순위')
    if is_anchor(key, tier): bits.append('리그 수준 추정')
    return f" ({', '.join(bits)})" if bits else ''

# ── 조사 결과 읽기: (팀, 날짜) → 기록 ──
ITEM = {}
for f in glob.glob(HERE + '/items_*.csv'):
    for r in csv.DictReader(open(f)): ITEM[r['id']] = r
RES = {}; miss = []
for f in sorted(glob.glob(HERE + '/out_*.csv')):
    if f.endswith('out_teams.csv'): continue
    for r in csv.DictReader(open(f)):
        it = ITEM.get(r['id'])
        if not it: miss.append(r['id']); continue
        ds = (r.get('dates') or '').split() or it['dates'].split()
        for d in ds: RES[(it['team'], d)] = r
print('조사 기록', len(RES), '· 항목 없는 출력 id', len(miss))
# 팀 수 표
TEAMS = {}
if os.path.exists(HERE + '/out_teams.csv'):
    for r in csv.DictReader(open(HERE + '/out_teams.csv')):
        try: TEAMS[(r['key'], int(r['tier']), int(r['season_key']))] = int(r['n_teams'])
        except (ValueError, KeyError): pass
print('팀 수 표', len(TEAMS))

# ── 데이터 ──
data = {}
for f in sorted(glob.glob(ROOT + '/src/data/*.js')):
    t = open(f, encoding='utf-8').read(); m = re.search(r'const (\w+)_E=(\[.*?\]\]);', t, re.S)
    if m: data[f] = (t, m, json.loads(m.group(2)))

stat = collections.Counter(); ANC = collections.defaultdict(dict); TS = {}; issues = []
def deepest(key):
    return {'BRA': 5}.get(key, 6)
for f, (t, m, E) in data.items():
    for r in E:
        rec = RES.get((r[1], str(r[9])))
        if not rec: continue
        try: key = key_of(rec['country'])
        except KeyError: issues.append(('나라', rec['country'], rec['id'])); continue
        sp = season_parts(rec['season'] or '')
        if not sp: issues.append(('시즌', rec['season'], rec['id'])); continue
        season, y, cal = sp
        tier = int(rec['tier']) if (rec.get('tier') or '').strip().isdigit() else deepest(key)
        old = r[2]
        if rec['rank'].strip().isdigit():
            rk = int(rec['rank']); n = int(rec['n_teams']) if rec['n_teams'].strip().isdigit() else 18
            if not rec['n_teams'].strip().isdigit(): issues.append(('팀 수 없음, 18로 둠', r[1], rec['id']))
            if rk > n: issues.append(('순위>팀 수', r[1], rec['id'])); continue
            r[12] = head(key, tier, season, rk, n) + extra(rec, key, tier)
            if is_anchor(key, tier): ANC[(key, tier)][(r[1], season)] = (old, y, cal, rk, n)
            TS[(r[1], key, tier, y)] = (rk, n, rec, season)
            stat['순위 라벨로 바꿈'] += 1
        else:
            why = rec.get('league_name') or rec.get('note', '')[:40]
            r[12] = f'{KEY2KO[key]} {tier}부 {season} 순위 없음 ({why}; 리그 수준 추정)'
            if is_anchor(key, tier): ANC[(key, tier)][(r[1], season)] = (old, y, cal, None, None)
            stat['순위 없음'] += 1
# ── 같은 팀·같은 시즌의 다른 행도 조사 순위로 통일 + 팀 수 채우기 ──
for f, (t, m, E) in data.items():
    for r in E:
        mm = re.match(r'^수페레탄 (\d{4}) (\d+)위(?:/\d+팀)?(.*)$', str(r[12]))
        if mm:   # 스웨덴 2부(2000년부터 16팀) — 예전 도구가 1부로 읽던 라벨
            r[12] = f'스웨덴 2부 {mm.group(1)} {mm.group(2)}위/16팀' + (mm.group(3) or ''); stat['수페레탄 → 스웨덴 2부'] += 1
        lv = str(r[12]); p = M.parse(lv, str(r[9]))
        if not p: continue
        key, tier, y, cal, rk, n = p
        hit = TS.get((r[1], key, tier, y))
        if hit and (hit[0], hit[1]) != (rk, n) and not RES.get((r[1], str(r[9]))):
            r[12] = head(key, tier, hit[3], hit[0], hit[1]) + extra(hit[2], key, tier); stat['같은 팀·시즌 통일'] += 1; continue
        h = lv.split(' (')[0]
        if not re.search(r'\d+위/\d+팀', h) and (key, tier, y) in TEAMS:
            nn = TEAMS[(key, tier, y)]
            if rk <= nn:
                r[12] = re.sub(r'(\d+)위', lambda mm: f'{mm.group(1)}위/{nn}팀', lv, count=1); stat['팀 수 채움'] += 1
            else: issues.append(('팀 수<순위', r[1], lv[:60]))
# ── 기준점 ──
anchors = {}
for (key, tier), d in ANC.items():
    xs = []
    for (team, season), (v, y, cal, rk, n) in d.items():
        t1n, t1y = M.T1(key, M.REF), M.T1(key, y, cal)
        adj = 0.5 * (t1y - t1n) if (tier >= 2 and t1n is not None and t1y is not None) else 0
        sdv = M.SD1 if tier == 1 else M.SDL
        xs.append(v - adj - (sdv * M.cv(rk, n) if rk else 0))
    anchors[f'{key}|{tier}'] = round(st.mean(xs), 1)
# 단계 순서 보장: 각 단계는 바로 위 단계(2026 기준)보다 최소 MINSTEP 낮게
MINSTEP = 100.0; raw = dict(anchors); clamped = []
M.ANCHOR.clear()
for k in sorted(anchors, key=lambda s: (s.split('|')[0], int(s.split('|')[1]))):
    key, tier = k.split('|')[0], int(k.split('|')[1])
    if tier >= 2:
        up = M.base(key, tier - 1, M.REF)
        if up is not None and anchors[k] > up - MINSTEP:
            clamped.append((k, anchors[k], round(up - MINSTEP, 1))); anchors[k] = round(up - MINSTEP, 1)
    M.ANCHOR[k] = anchors[k]
print('위 단계보다 높아 낮춘 기준점', clamped)
print(dict(stat)); print('문제', len(issues))
for x in issues[:40]: print('  ', x)
print('기준점', len(anchors)); print(sorted(anchors.items()))
if WRITE:
    for f, (t, m, E) in data.items():
        nt = t[:m.start(2)] + json.dumps(E, ensure_ascii=False, separators=(',', ':')) + t[m.end(2):]
        if nt != t: open(f, 'w', encoding='utf-8').write(nt)
    json.dump({'설명': 'v1.226 하부 리그·모형 밖 비유럽 1부 기준점(2025-26 기준 평균 수준). 키 = 나라|단계. tools/league_rank_apply.py가 씀. '
               'v1.226 이전 값의 평균에서 순위 곡선과 1부 시즌 이동의 절반을 빼서 정함(기존 평균 수준 유지).', '기준점': anchors},
              open(ROOT + '/elo/league_lower_base.json', 'w'), ensure_ascii=False, indent=0)
    print('씀')
