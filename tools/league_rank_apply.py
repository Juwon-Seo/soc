#!/usr/bin/env python3
"""상대 팀 순위 → Elo 일괄 적용 (v1.226, 사용자 결정 2026-11-19: '순위를 확실히 파악하고 그에 해당하는 Elo로 정확히 반영,
기준점은 추정이더라도 순위에 따른 차이는 확실히 반영')

모든 '리그·시즌·순위/팀 수' 라벨 행의 상대 Elo = 기준 평균(나라, 단계, 시즌) + 흩어짐(나라, 단계) × 순위 곡선 cv(순위, 팀 수).
같은 리그·시즌·순위면 어느 선수 자료든 같은 값이 된다(같은 팀·시즌 값이 갈리지 않음).

기준 평균
  1부: 5대 리그·네덜란드·포르투갈 = tools/league_era_normalize.py target, 다른 UEFA 나라 = 같은 도구의 UEFA 계수 공식
       (v1.222의 23개 나라 + 이번에 나머지 UEFA 나라로 확대), 비유럽 27개 나라 = tools/league_world_normalize.py target,
       그 밖의 비유럽 나라 = Opta 2026-11 수준 → Elo(같은 회귀식, 시즌 변화 없음).
       달력 연도 시즌(YYYY)인데 계수 시즌이 가을~봄인 나라는 Y·Y+1 두 계수 시즌 목표의 평균.
  2부: 7개 나라는 tools/league_second_tier.py, 튀르키예·브라질·일본·아르헨티나·미국·사우디·카타르는 tools/league_second_tier_x.py.
  그 밖의 k부(k≥2): 1부(2025-26) − 27.01 × (Opta 1부 − Opta k부) + 0.5 × (1부(y) − 1부(2025-26))   (v1.218 규칙을 넓힘)
       Opta k부 = 그 나라 Opta 목록의 k번째 리그(브라질 주 리그 등 피라미드 밖 리그 제외). 목록보다 깊으면 한 단계마다 Opta −9.
흩어짐
  순위 라벨이 충분히 쌓인 리그(기존 도구가 쓰는 값): 그대로. 나머지 1부 60, 2부 이하 51.24(v1.219 기본값과 같음).
라벨 형식(이 도구가 읽는 것)
  기존 도구 형식(프리미어리그 2010-11 3위/20팀, 러시아 2012-13 2위/16팀, 브라질 세리에 A 2010 5위/20팀, 챔피언십 2010-11 …, 튀르키예 2부 …)
  + 새 형식 '<나라> <k>부 <시즌> <순위>위/<팀 수>팀' (시즌은 YYYY-YY 또는 달력 연도 YYYY).
순위가 없는 행(라벨에 순위 없음)은 건드리지 않는다.

  python3 tools/league_rank_apply.py            # 바뀔 행 수·리그별 요약만
  python3 tools/league_rank_apply.py --apply    # src/data/*.js 에 적용(이미 맞으면 0행)
적용 뒤 네 도구(league_era_normalize·league_world_normalize·league_second_tier·league_second_tier_x)의 이동량은 0(±2 반올림)이어야 한다.
"""
import json, re, glob, os, sys, io, contextlib, collections, statistics as st
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load(name):
    G = {'__file__': os.path.join(ROOT, 'tools', name), '__name__': 'x'}
    argv = sys.argv; sys.argv = ['x']
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(open(G['__file__'], encoding='utf-8').read().rsplit("if '--apply' in sys.argv:", 1)[0], name, 'exec'), G)
    sys.argv = argv; return G
ERA = load('league_era_normalize.py'); W = load('league_world_normalize.py')
S2 = load('league_second_tier.py'); SX = load('league_second_tier_x.py')
cv = ERA['cv']; OA, OB = W['OA'], W['OB']
OPTA = json.load(open(os.path.join(ROOT, 'elo', 'opta_league_2026-11-19.json')))['리그']

# ── 나라 이름(한국어 라벨) ↔ 키 ──
# 키: UEFA 계수 파일 이름(유럽) 또는 world 도구 코드(비유럽 27개) 또는 영어 이름(그 밖)
KO = {
 '잉글랜드': 'England', '스페인': 'Spain', '독일': 'Germany', '이탈리아': 'Italy', '프랑스': 'France', '네덜란드': 'Netherlands', '포르투갈': 'Portugal',
 '튀르키예': 'Turkey', '벨기에': 'Belgium', '오스트리아': 'Austria', '그리스': 'Greece', '우크라이나': 'Ukraine', '러시아': 'Russia', '스위스': 'Switzerland',
 '스코틀랜드': 'Scotland', '체코': 'Czechia', '폴란드': 'Poland', '덴마크': 'Denmark', '노르웨이': 'Norway', '키프로스': 'Cyprus', '스웨덴': 'Sweden',
 '크로아티아': 'Croatia', '이스라엘': 'Israel', '헝가리': 'Hungary', '세르비아': 'Serbia', '루마니아': 'Romania', '슬로베니아': 'Slovenia',
 '아제르바이잔': 'Azerbaijan', '슬로바키아': 'Slovakia', '불가리아': 'Bulgaria',
 '벨라루스': 'Belarus', '몰도바': 'Moldova', '카자흐스탄': 'Kazakhstan', '핀란드': 'Finland', '리투아니아': 'Lithuania', '라트비아': 'Latvia',
 '에스토니아': 'Estonia', '알바니아': 'Albania', '조지아': 'Georgia', '아르메니아': 'Armenia', '북마케도니아': 'North Macedonia',
 '보스니아 헤르체고비나': 'Bosnia-Herzegovina', '몬테네그로': 'Montenegro', '아일랜드': 'Ireland', '북아일랜드': 'Northern Ireland', '웨일스': 'Wales',
 '룩셈부르크': 'Luxembourg', '아이슬란드': 'Iceland', '몰타': 'Malta', '페로 제도': 'Faroe Islands', '코소보': 'Kosovo', '안도라': 'Andorra',
 '지브롤터': 'Gibraltar', '산마리노': 'San Marino', '리히텐슈타인': 'Liechtenstein', '소련': 'Soviet Union', '동독': 'East Germany',
 '유고슬라비아': 'Serbia', '세르비아·몬테네그로': 'Serbia',
 '미국': 'USA', '브라질': 'BRA', '아르헨티나': 'ARG', '멕시코': 'MEX', '사우디': 'KSA', '사우디아라비아': 'KSA', '카타르': 'QAT', 'UAE': 'UAE',
 '일본': 'JPN', '한국': 'KOR', '중국': 'CHN', '호주': 'AUS', '인도': 'IND', '우루과이': 'URU', '콜롬비아': 'COL', '칠레': 'CHI', '파라과이': 'PAR',
 '페루': 'PER', '에콰도르': 'ECU', '베네수엘라': 'VEN', '볼리비아': 'BOL', '우즈베키스탄': 'UZB', '이집트': 'EGY', '이란': 'IRN', '이라크': 'IRQ',
 '온두라스': 'HON', '캐나다': 'CAN', '홍콩': 'HKG',
 '코스타리카': 'Costa Rica', '엘살바도르': 'El Salvador', '자메이카': 'Jamaica', '과테말라': 'Guatemala', '파나마': 'Panama', '트리니다드 토바고': 'Trinidad and Tobago',
 '튀니지': 'Tunisia', '모로코': 'Morocco', '알제리': 'Algeria', '케냐': 'Kenya', '콩고민주공화국': 'Congo DR', '남아프리카공화국': 'South Africa', '나이지리아': 'Nigeria',
 '도미니카공화국': 'Dominican Republic', '가나': 'Ghana', '코트디부아르': 'Ivory Coast', '세네갈': 'Senegal', '카메룬': 'Cameroon', '말리': 'Mali',
 '요르단': 'Jordan', '태국': 'Thailand', '타지키스탄': 'Tajikistan', '투르크메니스탄': 'Turkmenistan', '뉴질랜드': 'New Zealand', '쿠웨이트': 'Kuwait',
 '바레인': 'Bahrain', '오만': 'Oman', '레바논': 'Lebanon', '시리아': 'Syria', '베트남': 'Vietnam', '인도네시아': 'Indonesia', '말레이시아': 'Malaysia',
 '싱가포르': 'Singapore', '키르기스스탄': 'Kyrgyzstan', '마르티니크': 'Martinique', '레위니옹': 'Reunion', '프랑스령 기아나': 'French Guiana',
}
KO_NAMES = sorted(KO, key=len, reverse=True)
BIG = {'England': '프리미어리그', 'Spain': '라리가', 'Germany': '분데스리가', 'Italy': '세리에A', 'France': '리그1', 'Netherlands': '에레디비시', 'Portugal': '포르투갈 1부'}
BIG_R = {v: k for k, v in BIG.items()}
OTHER = set(ERA['OTEAMS'])
WCC = set(W['LG'])
# Opta 나라 이름(파일의 '|' 뒤) — 키와 다를 때만
OPTA_NAME = {'Turkey': 'Türkiye', 'Bosnia-Herzegovina': 'Bosnia and Herzegovina', 'Ireland': 'Republic of Ireland', 'USA': 'USA',
             'BRA': 'Brazil', 'ARG': 'Argentina', 'MEX': 'Mexico', 'KSA': 'Saudi Arabia', 'QAT': 'Qatar', 'UAE': 'United Arab Emirates', 'JPN': 'Japan',
             'KOR': 'Korea Republic', 'CHN': 'China PR', 'AUS': 'Australia', 'IND': 'India', 'URU': 'Uruguay', 'COL': 'Colombia', 'CHI': 'Chile',
             'PAR': 'Paraguay', 'PER': 'Peru', 'ECU': 'Ecuador', 'VEN': 'Venezuela', 'BOL': 'Bolivia', 'UZB': 'Uzbekistan', 'EGY': 'Egypt', 'IRN': 'Iran',
             'IRQ': 'Iraq', 'HON': 'Honduras', 'CAN': 'Canada', 'HKG': 'Hong Kong, China'}
NOT_PYRAMID = re.compile(r'Paulista|Carioca|Mineiro|Gaúcho|Goiano|Pernambucano|Baiano|Paranaense|Sergipano|Paraibano|Paraense|Brasiliense|Catarinense|'
                         r'Amazonense|Piauiense|Capixaba|Matogrossense|Cearense|Amapaense|Alagoano|Maranhense|Acreano|Women|Youth|U\d\d|Reserve|Cup', re.I)
OPTA_C = collections.defaultdict(list)
for k, v in OPTA.items():
    nm, cn = (k.split('|') + ['?'])[:2]
    if not NOT_PYRAMID.search(nm): OPTA_C[cn].append(v)
for cn in OPTA_C: OPTA_C[cn].sort(reverse=True)
# 같은 단계에 리그가 둘 이상 나란히 있는 나라(Opta 목록에서 따로 매겨져 단계가 밀리는 것): 단계별 Opta 값 직접 지정
OPTA_TIERS = {
 'ARG': [82.96, 76.66, (69.97 + 62.06) / 2, (53.92 + 47.8) / 2, 40.83],     # 3부 = 토르네오 페데랄 A·프리메라 B 메트로, 4부 = 지역 아마추어·프리메라 C
}
def opta_tiers(key):
    if key in OPTA_TIERS: return OPTA_TIERS[key]
    return OPTA_C.get(OPTA_NAME.get(key, key), [])
SLOPE = 27.01; STEP = 9.0
def opta_of(key, k):
    L = opta_tiers(key)
    if not L: return None
    return L[k - 1] if k <= len(L) else L[-1] - STEP * (k - len(L))

# ── 1부 기준 평균 ──
def T1(key, y, cal=False):
    """y: 시즌 끝 연도(가을~봄) 또는 달력 연도(cal=True)."""
    if key in BIG:
        return (ERA['target'](BIG[key], y) + ERA['target'](BIG[key], y + 1)) / 2 if cal else ERA['target'](BIG[key], y)
    if key in ERA['C']:
        if key in OTHER and key in ERA['OCAL']: return ERA['otarget'](key, y)
        if cal: return (ERA['otarget_raw'](key, y) + ERA['otarget_raw'](key, y + 1)) / 2
        return ERA['otarget_raw'](key, y)
    if key in WCC: return W['target'](key, y)
    if f'{key}|1' in ANCHOR: return ANCHOR[f'{key}|1']
    o = opta_of(key, 1)
    return OA + OB * o if o is not None else None
REF = 2026
SX_KEY = {'Turkey': '튀르키예 2부', 'BRA': '브라질 세리에 B', 'JPN': 'J2리그', 'ARG': '아르헨티나 2부', 'USA': 'USL', 'KSA': '사우디 2부', 'QAT': '카타르 2부'}
# 하부 리그(2부 도구 밖)·모형 밖 비유럽 1부의 기준점: 기존 자료 평균 수준을 2025-26 기준으로 고정한 값(elo/league_lower_base.json,
# v1.226 이전 값에서 순위 곡선과 1부 시즌 이동의 절반을 뺀 평균). 없는 단계는 2부 = 1부 − 277(유럽 2부 간격 중앙값), 그 아래는 한 단계마다 −120.
ANCHOR = json.load(open(os.path.join(ROOT, 'elo', 'league_lower_base.json')))['기준점'] if os.path.exists(os.path.join(ROOT, 'elo', 'league_lower_base.json')) else {}
GAP2, STEPL = 277.0, 120.0
def anchor(key, tier):
    if f'{key}|{tier}' in ANCHOR: return ANCHOR[f'{key}|{tier}']
    if tier <= 1: return T1(key, REF)
    up = anchor(key, tier - 1)
    if up is None: return None
    return up - (GAP2 if tier == 2 else STEPL)
def base(key, tier, y, cal=False):
    if tier == 1: return T1(key, y, cal)
    if tier == 2 and key in BIG: return S2['target2'](BIG[key], y)
    if tier == 2 and key in SX_KEY: return SX['target2'](SX_KEY[key], y)
    a = anchor(key, tier)
    if a is None: return None
    t1n, t1y = T1(key, REF), T1(key, y, cal)
    return a + (0.5 * (t1y - t1n) if (t1n is not None and t1y is not None) else 0)

# ── 흩어짐 ──
KEEP_OTHER = {'Turkey', 'Belgium', 'Austria', 'Greece', 'Ukraine', 'Russia', 'Switzerland', 'Czechia', 'Poland', 'Croatia'}   # 순위 행이 40개 이상
KEEP_WORLD = {'USA', 'BRA', 'ARG', 'MEX', 'KSA', 'QAT', 'JPN', 'CHN'}
SD1, SDL = 60.0, 51.24
# v1.225 자료에서 각 도구가 추정하던 흩어짐을 고정(다시 돌려도 같은 값이 나오게). 이 값으로 맞춘 자료라 기존 도구가 다시 추정해도 같다.
SDFIX = {'England|1': 97.87, 'England|2': 60.32, 'Spain|1': 100.51, 'Spain|2': 51.78, 'Germany|1': 101.24, 'Germany|2': 43.66,
         'Italy|1': 91.34, 'Italy|2': 51.69, 'France|1': 96.24, 'France|2': 51.46, 'Netherlands|1': 110.84, 'Netherlands|2': 54.19,
         'Portugal|1': 126.51, 'Portugal|2': 53.52, 'Czechia|1': 56.07, 'Ukraine|1': 115.5, 'Turkey|1': 117.35, 'Croatia|1': 98.57,
         'Poland|1': 65.85, 'Belgium|1': 117.71, 'Greece|1': 117.05, 'Switzerland|1': 98.57, 'Austria|1': 112.6, 'Russia|1': 60.08,
         'MEX|1': 74.72, 'ARG|1': 58.39, 'KSA|1': 112.68, 'BRA|1': 60.44, 'USA|1': 55.31, 'JPN|1': 73.91, 'CHN|1': 62.94, 'QAT|1': 44.81}
def sd(key, tier):
    return SDFIX.get(f'{key}|{tier}', SD1 if tier == 1 else SDL)

# ── 라벨 읽기 ──
NEWPAT = re.compile(r'^(' + '|'.join(re.escape(k) for k in KO_NAMES) + r') ([1-9])부 (\d{4})(?:-(\d{2}))? (\d+)위/(\d+)팀')
def parse(lv, d):
    """→ (key, tier, y, cal, rank, n) 또는 None. 순위는 라벨 앞부분(첫 ' (' 앞)에 있어야 한다(괄호 안 설명의 순위는 쓰지 않음)."""
    lv = lv.split(' (')[0]
    if not re.search(r'\d+위', lv): return None
    mm = NEWPAT.match(lv)
    if mm:
        key = KO[mm.group(1)]; tier = int(mm.group(2)); cal = mm.group(4) is None
        y = int(mm.group(3)) + (0 if cal else 1)
        return key, tier, y, cal, int(mm.group(5)), int(mm.group(6))
    mm = ERA['PAT'].match(lv)
    if mm and mm.group(1) in ERA['LEAGUE'] and mm.group(4):
        lg = mm.group(1); y = int(mm.group(2)) + 1
        return BIG_R[lg], 1, y, False, int(mm.group(4)), int(mm.group(5)) if mm.group(5) else ERA['teams'](lg, y)
    lab, top = S2['which'](lv)
    if top:
        m2 = S2['PAT'].match(lv)
        if not m2: return None
        y = int(m2.group(1)) + 1
        return BIG_R[top], 2, y, False, int(m2.group(3)), int(m2.group(4)) if m2.group(4) else S2['TIER2'][top][3](y)
    k = SX['which'](lv)
    if k:
        mm = re.search(r'(\d+)위(?:/(\d+)팀)?', lv)
        if not mm: return None
        key = {v: kk for kk, v in SX_KEY.items()}.get(k, 'USA')
        y = SX['year_of'](lv, d, SX['X'][k][4])
        return key, 2, y, False, int(mm.group(1)), int(mm.group(2)) if mm.group(2) else SX['X'][k][5]
    cn = ERA['octry'](lv)
    if cn:
        if ERA['is_lower'](lv): return None
        pr = ERA['oparse'](lv, cn)
        if not pr: return None
        y, rk, n = pr
        return cn, 1, y, cn in ERA['OCAL'], rk, n or ERA['OTEAMS'][cn]
    cc = W['country'](lv)
    if cc:
        if W['is_lower'](lv): return None
        mm = W['YPAT'].search(lv)
        if not mm: return None
        y = W['label_year'](lv, W['LG'][cc][3])
        if not y: return None
        return cc, 1, y, False, int(mm.group(3)), int(mm.group(4)) if mm.group(4) else W['LG'][cc][4]
    return None

def value(key, tier, y, cal, rk, n):
    b = base(key, tier, y, cal)
    if b is None or rk > n or n < 2: return None
    return int(round(b + sd(key, tier) * cv(rk, n)))

if __name__ == '__main__':
    data = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'src', 'data', '*.js'))):
        t = open(f, encoding='utf-8').read(); m = re.search(r'const (\w+)_E=(\[.*?\]\]);', t, re.S)
        if m: data[f] = (t, m, json.loads(m.group(2)))
    stat = collections.Counter(); moved = collections.Counter(); delta = collections.defaultdict(list); nofit = 0
    for f, (t, m, E) in data.items():
        ch = 0
        for r in E:
            p = parse(str(r[12]), str(r[9]))
            if not p: nofit += 1; continue
            v = value(*p)
            if v is None: stat['기준 없음'] += 1; continue
            stat['적용 대상'] += 1
            if v != r[2]:
                delta[(p[0], p[1])].append(v - r[2]); moved[(p[0], p[1])] += 1
                r[2] = v; ch += 1
        if ch and '--apply' in sys.argv:
            open(f, 'w', encoding='utf-8').write(t[:m.start(2)] + json.dumps(E, ensure_ascii=False, separators=(',', ':')) + t[m.end(2):])
    print('순위 라벨 행', stat['적용 대상'], '· 기준 없음', stat['기준 없음'], '· 순위 라벨 아님(건드리지 않음)', nofit)
    print('바뀌는 행', sum(moved.values()))
    for k, v in sorted(moved.items(), key=lambda x: -x[1])[:60]:
        dl = delta[k]; print(f'  {k[0]} {k[1]}부: {v}행, 차이 중앙값 {st.median(dl):+.0f}, 최대 |{max(abs(x) for x in dl)}|')
    if '--apply' in sys.argv: print('적용 완료')
