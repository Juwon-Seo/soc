# tadic.json의 map_need → map_lines.txt (승점 표 map 추가 필요 목록) + (--apply <elo 파일>) 스크래치 복사본에 적용
import json, re, sys, unicodedata, os
H = os.path.dirname(os.path.abspath(__file__))
O = json.load(open('/home/user/soc/elo/league_points_other.json'))['seasons']
need = json.load(open(os.path.join(H, 'tadic.json')))['map_need']
def n(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(fk|gfk|ofk|fc|if|cf|nk|sc|csc|afc|1912|1926|1924|al)\b', ' ', s); return ' '.join(re.sub('[^a-z ]', ' ', s).split())
lines = []
for head, o, lv in need:
    rows = O[head]['tables'][0]['rows']; rk = int(re.search(r' (\d+)위', lv).group(1))
    cand = [i for i, r in enumerate(rows) if set(n(o).split()) & set(n(r[0]).split())]
    i = rk - 1 if (rk - 1) in cand else (cand[0] if len(cand) == 1 else None)
    if i is None: sys.exit('못 찾음 ' + head + ' ' + o)
    if i != rk - 1: print('순위와 행 다름', head, o, rk, i)
    lines.append((head, o, rows[i][0], [0, i]))
open(os.path.join(H, 'map_lines.txt'), 'w').write(''.join(f'{h} | {o} | {t} | {json.dumps(ix)}\n' for h, o, t, ix in lines))
if '--apply' in sys.argv:
    f = sys.argv[sys.argv.index('--apply') + 1]; D = json.load(open(f))
    for h, o, t, ix in lines: D['seasons'][h].setdefault('map', {})[o] = ix
    json.dump(D, open(f, 'w'), ensure_ascii=False, indent=1)
print(len(lines))
