#!/usr/bin/env python3
"""경기 최종 스코어 수집(v1.239): 골·도움 기록의 결승골·마지막 동점골 표시용.

출처: Transfermarkt performance-game API(선수 1명당 1회, 경기마다 우리 팀·상대 최종 득점, 연장 포함).
승부차기 경기는 goalsTotal에 승부차기가 섞여 있으므로 경기 상세 API(game/<id>)의 GOAL 동작으로 120분 스코어를 구함.

python3 tools/final_scores.py <캐시 폴더> <프리셋id:접두어:TM선수id> ...
  예: python3 tools/final_scores.py /tmp/fs son:SON:91845 drogba:DRO:3924
결과: src/data/finals.js 의 FINALS[프리셋id] 에 '날짜|상대' → 값 을 합쳐 씀(다른 선수 값은 그대로 둠).
  값 = [우리 팀 최종, 상대 최종, 승부차기(1 이김·-1 짐·0 없음)]
  두 경기 합산 1차전 기록은 2차전 결과를 덧붙임: [F, A, p, 2차전 F, 2차전 A, 2차전 p]
"""
import json, os, re, sys, time, datetime, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'src/data/finals.js')
UA = {'User-Agent': 'Mozilla/5.0', 'Accept': '*/*'}


def get(url, path):
    if os.path.exists(path):
        return json.load(open(path))
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                d = json.load(r)
            json.dump(d, open(path, 'w'))
            time.sleep(1.5)
            return d
        except Exception as e:  # 네트워크 오류는 잠깐 쉬고 다시
            print('  다시 시도', url, e)
            time.sleep(3 * (k + 1))
    print('  가져오기 실패: ' + url)
    return None


def shootout_score(cache, gid, venue):
    """승부차기 경기의 연장 120분 스코어(우리 팀, 상대)."""
    D = get(f'https://tmapi.transfermarkt.technology/game/{gid}', os.path.join(cache, f'game_{gid}.json'))
    if not D: return None
    d = D['data']
    h = a = 0
    for x in d.get('actions', []):
        if x.get('type') == 'GOAL' and x.get('score'):
            h = max(h, x['score']['home']); a = max(a, x['score']['away'])
    return (h, a) if venue == 'home' else (a, h)


def encode(d):
    out = []
    for k in sorted(d):
        v = list(d[k])
        if len(v) == 3 and v[2] == 0: v = v[:2]
        out.append(','.join([k[2:4] + k[5:7] + k[8:10]] + [str(x) for x in v]))
    return ';'.join(out)


def decode(s):
    d = {}
    for part in filter(None, s.split(';')):
        a = part.split(','); y = int(a[0][:2])
        k = f'{1900 + y if y > 80 else 2000 + y}-{a[0][2:4]}-{a[0][4:6]}'
        v = [int(x) for x in a[1:]]
        d[k] = v + [0] if len(v) == 2 else v
    return d


def load_rows(prefix):
    f = [p for p in os.listdir(os.path.join(ROOT, 'src/data')) if p.endswith('.js')]
    for p in f:
        t = open(os.path.join(ROOT, 'src/data', p), encoding='utf-8').read()
        m = re.search(r'const ' + prefix + r'_E=(\[.*?\]\]);', t, re.S)
        if m:
            return json.loads(m.group(1))
    raise SystemExit('데이터 없음: ' + prefix)


def main():
    cache = sys.argv[1]; os.makedirs(cache, exist_ok=True)
    finals = {}
    if os.path.exists(OUT):
        m = re.search(r'const FINALS=(\{.*\});', open(OUT, encoding='utf-8').read(), re.S)
        if m: finals = {k: decode(v) for k, v in json.loads(m.group(1)).items()}
    for spec in sys.argv[2:]:
        pid, prefix, tmid = spec.split(':')
        P = get(f'https://tmapi.transfermarkt.technology/player/{tmid}/performance-game', os.path.join(cache, f'perf_{tmid}.json'))
        if not P: print(f'{pid}: 건너뜀(TM 선수 id {tmid} 실패)'); continue
        perf = P['data']['performance']
        games = []
        for g in perf:
            gi = g['gameInformation']
            if gi.get('isNationalGame'): continue
            c = g['clubsInformation']['club']; o = g['clubsInformation']['opponent']
            if c.get('goalsTotal') is None: continue
            d = datetime.date.fromisoformat(gi['date']['dateTimeUTC'][:10])
            games.append(dict(d=d, gid=gi['gameId'], comp=gi['competitionId'], opp=o['clubId'], venue=c['venue'],
                              F=c['goalsTotal'], A=o['goalsTotal'], state=gi['gameState']))
        games.sort(key=lambda x: x['d'])

        def score(g):
            if g['state'] == 'penalty_shootout':
                s = shootout_score(cache, g['gid'], g['venue'])
                if s is None: return None
                F, A = s
                return [F, A, 1 if g['F'] > g['A'] else -1]
            return [g['F'], g['A'], 0]

        def find(date):
            d = datetime.date.fromisoformat(date)
            c = [g for g in games if abs((g['d'] - d).days) <= 1]
            c.sort(key=lambda g: (abs((g['d'] - d).days), g['d'] != d - datetime.timedelta(days=1)))
            return c[0] if c else None

        out = {}; miss = []; bad = []; noleg2 = []
        for r in load_rows(prefix):
            date, opp, gf, ga, tie = r[9], r[1], r[5], r[6], (r[14] if len(r) > 14 else 0)
            key = date
            if key in out: v = out[key]
            else:
                g = find(date)
                if not g: miss.append(key); continue
                v = score(g)
                if v is None: miss.append(key); continue
                if tie and tie[0] == 1:  # 1차전: 같은 대회·같은 상대의 다음 경기(70일 안)를 2차전으로
                    n = [x for x in games if x['comp'] == g['comp'] and x['opp'] == g['opp'] and 0 < (x['d'] - g['d']).days <= 70]
                    s2 = score(n[0]) if n else None
                    if s2: v = v + s2
                    else: noleg2.append(key)
                out[key] = v
            if v[0] < gf + 1 or v[1] < ga:  # 기록의 골 뒤 스코어가 최종 스코어보다 크면 날짜 맞춤이 틀린 것
                bad.append((key, gf, ga, v[:2]))
        for k, *_ in bad: out.pop(k, None)
        finals[pid] = out
        print(f'{pid}: 경기 {len(out)} · TM에 없음 {len(miss)} · 스코어 모순(빼냄) {len(bad)} · 2차전 못 찾음 {len(noleg2)}')
        for x in (miss[:5] + bad[:5] + noleg2[:5]): print('   ', x)
    body = json.dumps({k: encode(v) for k, v in finals.items()}, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    open(OUT, 'w', encoding='utf-8').write(
        '/* 경기 최종 스코어(v1.239, v1.240 압축): 프리셋 id → "yymmdd,우리,상대[,승부차기(1 이김·-1 짐)[,2차전 우리,2차전 상대,2차전 승부차기]];…" (날짜는 기록의 현지 날짜, 두 경기 합산 1차전은 2차전 결과를 덧붙임). '
        '출처 Transfermarkt performance-game·경기 상세. 결승골·마지막 동점골 표시에만 쓰고 SOC 계산에는 쓰지 않음. tools/final_scores.py로 만듦. */\n'
        f'const FINALS={body};\n')


if __name__ == '__main__':
    main()
