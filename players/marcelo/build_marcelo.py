#!/usr/bin/env python3
"""Build Marcelo (MCL) data from players/marcelo/raw -> players/marcelo/mcl.js + marcelo.json.

Usage: python3 build_marcelo.py [SRC_DATA_DIR] [OUT_JS]
  SRC_DATA_DIR: directory with the other players' data files (default /home/user/soc/src/data),
                used to copy opponent Elo/label of the same match (shared Real Madrid games).
  Elo values are finally set by tools/league_rank_apply.py from the labels; the scratch-copy
  values are read back with --from-js (see judgments.md).
"""
import csv, json, re, sys, os, glob, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, 'raw')
SRC = sys.argv[1] if len(sys.argv) > 1 else '/home/user/soc/src/data'
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE, 'mcl.js')
ELO_JSON = '/home/user/soc/elo/opponent_elo_by_team_season.json'
FROM_JS = None
if '--from-js' in sys.argv:
    FROM_JS = sys.argv[sys.argv.index('--from-js') + 1]

def rd(f):
    return list(csv.DictReader(open(os.path.join(RAW, f), encoding='utf-8')))

G = {g['gameId']: g for g in rd('tm_games.csv')}
EV = rd('marcelo_goal_assist_events.csv')
TIES = {r['gameId']: r for r in rd('tm_two_leg_ties.csv')}
# legs whose game JSON lacks the other-leg field: other leg from performance-game (score ours-theirs)
TIES_X = {r['gameId']: r for r in rd('tm_two_leg_ties_extra.csv')}

# ---------------------------------------------------------------- dates
# TM schedule dates corrected with RSSSF fichas + ESPN kick-off times (local time)
DATE_FIX = {
    '2530370': '2006-05-24',  # at Fortaleza (ESPN 2006-05-25 00:45Z, RSSSF 24/05)
    '2530391': '2006-05-31',  # at São Paulo (ESPN 2006-06-01 00:45Z, RSSSF 31/05)
    '2530510': '2006-07-16',  # at Grêmio (ESPN 16 Jul 15:00 local, RSSSF 16/07)
    '2533316': '2006-11-01',  # at São Caetano (ESPN 2006-11-02 00:45Z, Wednesday)
}
def gdate(gid):
    return DATE_FIX.get(gid, G[gid]['date_local'])

# ---------------------------------------------------------------- competitions
def comp_of(g):
    c, r = g['competitionId'], (g['round'] or '').lower()
    if c in ('ES1', 'BRA1', 'GR1'):
        return 'lg', 0
    if c in ('CDR', 'BRC', 'GRP'):
        if 'final' in r and 'semi' not in r and 'quarter' not in r:
            return 'df', 1
        if 'semi' in r: return 'dsf', 1
        if 'quarter' in r: return 'dk', 1
        return 'dc', 1
    if c in ('BRCG',):       # Campeonato Carioca league phase (Taça Guanabara)
        return 'dc', 0
    if c in ('BRCF',):       # Carioca semi-finals / final: low domestic-cup weight, knockout
        return 'dc', 1
    if c == 'CL':
        if 'group' in r: return 'clg', 0
        if 'last 16' in r: return 'cl16', 1
        if 'quarter' in r: return 'clk', 1
        if 'semi' in r: return 'clsf', 1
        if r == 'final': return 'clf', 1
    if c == 'EL':
        if 'group' in r: return 'elg', 0
    if c == 'CLI':
        if 'group' in r: return 'lib', 0
        if 'last 16' in r: return 'lib', 1
        if 'quarter' in r: return 'libk', 1
        if 'semi' in r: return 'libsf', 1
        if r == 'final': return 'libf', 1
    if c == 'CS':
        return 'csa', 1
    if c == 'KLUB':
        return 'cwc', 1
    if c == 'SUC':
        return ('dsf', 1) if 'semi' in r else ('df', 1)
    if c in ('USC', 'RECO'):
        return 'df', 1
    raise SystemExit('unmapped comp %s %s' % (c, r))

# two-legged rules: (away goals, extra time)
def tie_rule(g):
    c, d = g['competitionId'], gdate(g['gameId'])
    if c in ('CL', 'CDR', 'SUC'): return (1, 1)          # UEFA to 2020-21, Copa del Rey, Supercopa (two-legged era)
    if c == 'BRC': return (1, 0)                          # Copa do Brasil 2006: away goals, no extra time
    if c == 'GRP': return (1, 1)                          # Greek Cup 2022-23 round of 16 (en.wiki format)
    if c == 'BRCF': return (0, 0)                         # Carioca two-legged final: neither (Coutinho precedent)
    if c in ('CLI', 'RECO', 'CS'): return (0, 0)
    raise SystemExit('tie rule? %s' % c)

# ---------------------------------------------------------------- M rows
SUB_EST = 23  # career average of his substitute appearances in 90-minute games (82 games)
M = []
for gid, g in G.items():
    comp, _ = comp_of(g)
    d = gdate(gid)
    mins = g['playedMinutes']
    if gid == '3476816':      # debut, TM: substitute, minute blank (RSSSF: on for Lino)
        M.append([d, g['opponent'], comp, SUB_EST, 1])
        continue
    M.append([d, g['opponent'], comp, int(mins)])
# 2006 Campeonato Carioca game missing in TM (RSSSF ficha: starter, not substituted)
M.append(['2006-03-19', 'Volta Redonda Futebol Clube (RJ)', 'dc', 90, 1])
M.sort(key=lambda r: (r[0], r[1]))

# ---------------------------------------------------------------- E rows
def parse_min(s):
    s = s.strip()
    if '+' in s:
        a, b = s.split('+')
        return int(a) + int(b), s
    return int(s), 0

# minute overrides (display)
MIN_FIX = {('955879', 'goal'): (47, '45+2')}   # Valladolid 2009: TM 46 = first-half added time (ESPN 45+2)

# assists removed (rule) and reasons
REMOVE = {}
KEEP_UNCONF = set()
for e in EV:
    if e['event'] != 'assist': continue
    gid, t, mn = e['tm_gameId'], e['tm_assist_type'], e['tm_minute']
    key = (gid, mn)
    if t.startswith('Penalty'): REMOVE[key] = 'PK 유도'
    elif t == 'Shot on goal': REMOVE[key] = '슈팅 리바운드'
    elif e['tm_scorer'] in ('Zé Castro', 'Nikolaos Karabelas'): REMOVE[key] = '상대 자책골'
# post-2014-08 TM-only (no FotMob confirmation) checked with other sources
REMOVE[('2811524', '90+3')] = '확인 못 함'   # Sevilla CdR 2017: ESPN only; FourFourTwo: deflected shot after Benzema run
REMOVE[('3038747', '83')] = '확인 못 함'     # CL final 2018 Bale 83': ESPN only; reports: long shot, no assist named
CONFIRMED_OTHER = {('3135203', '44'): 'ESPN 문자 중계·Sports Mole', ('3135203', '55'): 'ESPN 문자 중계·Sports Mole'}

def opp_score(e, g):
    hb, ab = map(int, e['score_before_home_away'].split('-'))
    return (hb, ab) if g['venue'] == 'H' else (ab, hb)

def season_key(g, d):
    c = g['competitionId']
    club = g['club']
    if club.startswith('Fluminense'):
        return d[:4]
    y, m = int(d[:4]), int(d[5:7])
    s = y if m >= 8 else y - 1
    return '%d-%02d' % (s, (s + 1) % 100)

# ------------- other players' rows (same match)
def load_others():
    out = {}
    for f in sorted(glob.glob(os.path.join(SRC, '*.js'))):
        b = os.path.basename(f)[:-3]
        if b in ('hon', 'clubcolors', 'finals', 'mcl'): continue
        s = open(f, encoding='utf-8').read()
        m = re.search(r'const\s+(\w+)_E\s*=\s*(\[.*?\]);\s*(?:\n|const|$)', s, re.S)
        if not m: continue
        for r in json.loads(m.group(2)):
            out.setdefault(r[9], []).append((b, r))
    return out
OTH = load_others()

def norm(s):
    s = s.lower()
    for w in ['fc ', 'cf ', 'cd ', 'ud ', 'rcd ', 'club ', 'sd ', 'ca ', ' fc', ' cf', 'de ', 'football club']:
        s = s.replace(w, ' ')
    return set(t for t in re.split(r'\W+', s) if len(t) > 2) - {'real', 'madrid'}

ELO = json.load(open(ELO_JSON, encoding='utf-8'))
NAME_IDX = {}
for k, v in ELO.items():
    t, sk = k.rsplit('|', 1)
    for n in v['names'] + [t]:
        NAME_IDX.setdefault((n, sk), (v['elo'], v['lv']))

# labels for team-seasons not in other data (verified ranks; see judgments.md)
MANUAL = {
    ('Vila Nova Futebol Clube (GO)', '2006'): '브라질 세리에 B 2006 20위/20팀',
    ('Cruzeiro Esporte Clube', '2006'): '브라질 세리에 A 2006 10위/20팀',
    ('CD Alcoyano', '2020-21'): '스페인 3부 2020-21 2위/10팀 (Segunda División B Grupo III (Subgrupo B), 경기 날짜에 진행 중이던 단계 순위, 리그 수준 추정)',
    ('CSD Colo-Colo', '2024'): '칠레 1부 2024 1위/16팀 (우승 팀)',
    ('Club Alianza Lima', '2024'): '페루 1부 2024 4위/18팀 (Liga 1 Torneo Apertura 2024, 경기 날짜에 진행 중이던 단계 순위)',
    ('Club Cerro Porteño', '2024'): '파라과이 1부 2024 아페르투라 2위/12팀 (Copa de Primera 아페르투라 2024, 경기 날짜에 진행 중이던 단계 순위)',
}
# opponent name used in rows (2006 Athletico = name used by the other players' 2006 rows)
NAME_FIX = {('Club Athletico Paranaense', '2006'): 'Atlético Paranaense'}

FROMJS = {}
if FROM_JS:
    s = open(FROM_JS, encoding='utf-8').read()
    m = re.search(r'const\s+MCL_E\s*=\s*(\[.*?\]);', s, re.S)
    for r in json.loads(m.group(1)):
        FROMJS[(r[9], r[1])] = r[2]

E = []
LOG = []
for e in EV:
    if e['event'] not in ('goal', 'assist'): continue
    gid = e['tm_gameId']; g = G[gid]
    key = (gid, e['tm_minute'])
    if e['event'] == 'assist' and key in REMOVE:
        LOG.append(('removed', REMOVE[key], gdate(gid), g['opponent'], e['tm_minute'], e['tm_scorer']))
        continue
    d = gdate(gid)
    comp, ko = comp_of(g)
    mn, dm = parse_min(e['tm_minute'])
    if (gid, e['event']) in MIN_FIX: mn, dm = MIN_FIX[(gid, e['event'])]
    et = 1 if (g['addition'] == 'n.V.' and mn > 90 and not dm) else 0
    gf, ga = opp_score(e, g)
    pk = 1 if e['tm_penalty'] == '1' and e['event'] == 'goal' else 0
    sk = season_key(g, d)
    opp = NAME_FIX.get((g['opponent'], sk), g['opponent'])
    # Elo/label: same match in other data -> team-season table -> manual
    elo = lv = None; src = ''
    cands = [(b, r) for b, r in OTH.get(d, []) if norm(r[1]) & norm(g['opponent'])]
    if cands:
        b, r = cands[0]; elo, lv, src = r[2], r[12], 'same match ' + b
    if lv is None:
        hit = NAME_IDX.get((opp, sk)) or NAME_IDX.get((g['opponent'], sk))
        if hit: elo, lv = hit; src = 'team-season table'
    if lv is None and (g['opponent'], sk) in MANUAL:
        lv = MANUAL[(g['opponent'], sk)]; elo = 1500; src = 'manual label'
    if lv is None:
        raise SystemExit('no label for %s %s %s' % (d, g['opponent'], sk))
    if (d, opp) in FROMJS: elo = FROMJS[(d, opp)]
    note = 0
    if e['event'] == 'assist':
        note = re.sub(r'\s+', ' ', e['tm_scorer']).strip()
    tie = None
    if gid in TIES_X and gid not in TIES:
        t = TIES_X[gid]; ag, xt = tie_rule(g)
        leg = 1 if '1st' in t['round'] else 2
        home = 1 if g['venue'] == 'H' else 0
        if leg == 1: tie = [1, home, 0, 0, ag, xt]
        else:
            o, th = map(int, t['other_leg_score_club_opp'].split('-'))
            tie = [2, home, o, th, ag, xt]
    elif gid in TIES:
        t = TIES[gid]; ag, xt = tie_rule(g)
        leg = 1 if '1st' in t['round'] else 2
        home = 1 if g['venue'] == 'H' else 0
        if leg == 1:
            tie = [1, home, 0, 0, ag, xt]
        else:
            oh, oa = map(int, t['other_leg_score'].split('-'))   # other (first) leg score home-away
            # first leg: we were away if now home
            ours, theirs = (oa, oh) if home else (oh, oa)
            tie = [2, home, ours, theirs, ag, xt]
    if tie: ko = 0          # two-legged legs: aggregate S (project convention ko 0 + tie)
    row = ['g' if e['event'] == 'goal' else 'a', opp, int(elo), comp, mn, gf, ga, ko, pk, d, et, dm, lv, note]
    if tie: row.append(tie)
    E.append(row)
    LOG.append(('row', src, d, opp, e['event'], e['tm_minute']))

E.sort(key=lambda r: (r[9], r[4], r[0]))

# ---------------------------------------------------------------- write
def dumps(a):
    return json.dumps(a, ensure_ascii=False, separators=(',', ':'))

note = open(os.path.join(BASE, 'note_marcelo.txt'), encoding='utf-8').read().strip() if os.path.exists(os.path.join(BASE, 'note_marcelo.txt')) else ''
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('const MCL_E=' + dumps(E) + ';\n')
    f.write('const MCL_M=' + dumps(M) + ';\n')
    f.write('const MCL_NOTE=' + json.dumps(note, ensure_ascii=False) + ';\n')
json.dump({'E': E, 'M': M}, open(os.path.join(BASE, 'marcelo.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
with open(os.path.join(BASE, 'build_log.txt'), 'w', encoding='utf-8') as f:
    for l in LOG: f.write(' | '.join(map(str, l)) + '\n')
ng = sum(1 for r in E if r[0] == 'g'); na = len(E) - ng
print('M', len(M), 'E', len(E), 'goals', ng, 'assists', na, 'minutes', sum(r[3] for r in M))
