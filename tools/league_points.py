#!/usr/bin/env python3
"""5대 리그 상대 Elo: 순위 곡선 대신 그 시즌 승점·득실 편차로 리그 안 간격을 정함 (v1.288, 사용자 결정 2026-11-23)

  상대 Elo = 시즌 중심값 b + 흩어짐 × (순위 곡선의 리그 평균) + k_L × 실력 점수
  실력 점수 = (경기당 승점 − 리그 평균) + w × (경기당 득실 − 리그 평균),  w = 0.3 (득실 약 3골 ≒ 승점 1점)
  - 승점은 승 3·무 1로 다시 셈(2점제 시즌도 같은 기준, 감점은 자동으로 빠짐).
  - 다른 시대와 비교하지 않음: 그 시즌 리그 안 편차만 씀. 리그 평균(중심값)은 순위 곡선 방식과 같음.
  - k_L은 리그 모든 시즌을 합친 흩어짐이 순위 곡선 방식과 같아지게 한 번 맞춘 상수(elo/league_points_big5.json의 k).
  - 팀 찾기: 라벨 순위(감점 전 경기장 성적 순서)의 팀을 쓰고, 상대 이름이 표의 다른 팀과 뚜렷이 더 맞으면 그 팀을 씀.
  - 표가 없는 시즌(진행 중 시즌 등)은 None → 기존 순위 곡선 값.
자료: elo/league_points_big5.json (영어 위키백과 시즌 문서의 Module:Sports table 원문에서 승·무·패·득점·실점).
tools/league_rank_apply.py가 이 모듈을 불러 5대 리그 행에 적용한다(따로 돌릴 필요 없음).
  python3 tools/league_points.py "프리미어리그 2025-26"   # 그 시즌 팀별 점수·Elo 표(중심값은 순위 도구 기준)
"""
import json, os, re, sys, statistics as st, unicodedata, difflib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(os.path.join(ROOT, 'elo', 'league_points_big5.json'), encoding='utf-8'))
W = D['w']; K = D['k']
PAT = re.compile(r'^(프리미어리그|라리가|분데스리가|세리에A|리그1) (\d{4}-\d{2}) (\d+)위')
ALIAS = {'internazionale': 'inter', 'nurnberg': 'nuremberg', 'chievoverona': 'chievo', 'brestois': 'brest', 'rennais': 'rennes',
         'gladbach': 'monchengladbach', 'koln': 'cologne', 'munchen': 'munich', 'sporting gijon': 'gijon', 'deportivo coruna': 'deportivo',
         'hellas verona': 'verona'}
STOP = r'\b(fc|cf|ac|as|ss|us|sc|rc|cd|ud|sd|rcd|ssc|afc|acf|calcio|club|de|del|la|vfb|vfl|sv|tsv|fsv|bv|bsc|ogc|olympique|stade|sporting|real|football|futbol|balompie|hotspur|united|city|athletic|atletico|borussia|town|county|wanderers|albion|rovers|alsace|sco|losc|hsc|and|of|the)\b'
def nz(s):
    s = s.replace('Español', 'Espanyol'); s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z ]', ' ', s); s = re.sub(r'^man ', 'manchester ', s); s = s.replace('espanyol barcelona', 'espanyol')
    for k, v in ALIAS.items(): s = s.replace(k, v)
    return ' '.join(re.sub(STOP, ' ', s).split())
def sim(a, b):
    a, b = nz(a), nz(b)
    if not a or not b: return 0
    return 1 if a == b else difflib.SequenceMatcher(None, a, b).ratio()
_SC = {}
def scores(key):
    """시즌 키('세리에A 2005-06') → [(팀, 실력 점수)] 경기장 성적 순서. 표 없으면 None."""
    if key in _SC: return _SC[key]
    s = D['seasons'].get(key)
    if not s: _SC[key] = None; return None
    T = s['teams']; ppg = [(3 * w + d) / p for _, p, w, d, l, gf, ga in T]; gd = [(gf - ga) / p for _, p, w, d, l, gf, ga in T]
    m, gm = st.mean(ppg), st.mean(gd)
    _SC[key] = [(T[i][0], (ppg[i] - m) + W * (gd[i] - gm)) for i in range(len(T))]
    return _SC[key]
_TS = {}
def team_score(lv, opp):
    """라벨·상대 이름 → (리그, 실력 점수, 팀 수) 또는 None."""
    ck = (lv.split(' (')[0], opp)
    if ck not in _TS: _TS[ck] = _team_score(*ck)
    return _TS[ck]
def _team_score(lv, opp):
    mm = PAT.match(lv)
    if not mm: return None
    S = scores(f'{mm.group(1)} {mm.group(2)}')
    if not S: return None
    rk = int(mm.group(3))
    if rk > len(S): return None
    w = S[rk - 1]; sw = sim(opp, w[0])
    best = max(S, key=lambda x: sim(opp, x[0])); sb = sim(opp, best[0])
    if best is not w and sb >= 0.75 and sb - sw >= 0.25: w = best
    return mm.group(1), w[1], len(S)
def value(lv, opp, b, sd, cv):
    """b = 시즌 중심값, sd = 리그 흩어짐, cv = 순위 곡선 함수. 표 없으면 None."""
    t = team_score(lv, opp)
    if not t: return None
    lg, sc, n = t
    mc = st.mean(cv(i, n) for i in range(1, n + 1))
    return int(round(b + sd * mc + K[lg] * sc))
if __name__ == '__main__' and len(sys.argv) > 1:
    S = scores(sys.argv[1])
    for i, (t, sc) in enumerate(S or []): print(i + 1, t, round(sc, 3))

# ── 다른 리그(v1.290): elo/league_points_other.json ──
# 형식 {"k": {"<나라키>|<단계>": k}, "w": 0.3, "seasons": {"<라벨 앞부분(순위 앞)>": {"src","tables":[{"name","rows":[[팀,경기,승,무,패,득,실]]}],"map":{"<데이터 팀 이름>":[표,행]},"note","check"}}}
_OF = os.path.join(ROOT, 'elo', 'league_points_other.json')
O = json.load(open(_OF, encoding='utf-8')) if os.path.exists(_OF) else {'k': {}, 'seasons': {}}
def table_scores(rows, w=None):
    w = W if w is None else w
    ppg = [(3 * r[2] + r[3]) / r[1] for r in rows]; gd = [(r[5] - r[6]) / r[1] for r in rows]
    m, gm = st.mean(ppg), st.mean(gd)
    return [(ppg[i] - m) + w * (gd[i] - gm) for i in range(len(rows))]
_OS = {}
def other_score(lv, opp):
    """라벨·상대 이름 → (실력 점수, 표 팀 수) 또는 None."""
    head = lv.split(' (')[0]; mm = re.match(r'^(.*?) \d+위', head)
    if not mm: return None
    E = O['seasons'].get(mm.group(1))
    if not E or 'skip' in E or E.get('ongoing'): return None
    rk = re.search(r'(\d+)위', head).group(1)
    pos = E.get('map', {}).get(f'{rk}={opp}') or E.get('map', {}).get(f'{opp}@{rk}') or E.get('map', {}).get(opp)   # 같은 팀이 한 줄에 순위 둘이면 '순위=팀' 키
    if not pos: return None
    ti, ri = pos; ck = (mm.group(1), ti)
    if ck not in _OS: _OS[ck] = table_scores(E['tables'][ti]['rows'])
    return _OS[ck][ri], len(E['tables'][ti]['rows'])
def value_other(lv, opp, key, tier, b, sd, cv):
    k = O['k'].get(f'{key}|{tier}')
    s = other_score(lv, opp)
    if k is None or not s: return None
    sc, n = s
    mc = st.mean(cv(i, n) for i in range(1, n + 1))
    return int(round(b + sd * mc + k * sc))
def covered(lv, opp):
    """이 행 값이 승점·득실 모형으로 정해지는가(평균 추정 도구들이 이 행을 빼는 데 씀)."""
    return bool(team_score(lv, opp)) or bool(other_score(lv, opp) and True)
