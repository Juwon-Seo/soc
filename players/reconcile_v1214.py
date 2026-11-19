import json,csv,re,sys
ents=json.load(open('elo/ents.json'))
conf={}
for r in csv.DictReader(open('elo/conflicts.csv',encoding='utf-8-sig')):
    conf[(r['팀'],r['시즌'])]=int(r['정한 Elo'])
files={'디에고 밀리토':'mlt','카를로스 테베스':'tvz','알렉시스 산체스':'axs','루이스 디아스':'ldz'}
fix={}
for e in ents:
    k=(e['team'],e['season'])
    if k in conf and e['elo']!=conf[k]:
        assert e['p'] in files,(e['p'],k)
        fix.setdefault(e['p'],[]).append((e['i'],conf[k],k))
log=[]
for p,lst in fix.items():
    f='src/data/%s.js'%files[p]; t=open(f).read()
    pre=files[p].upper()
    m=re.search(r'const %s_E=(\[.*?\]\]);'%pre,t,re.S); E=json.loads(m.group(1))
    for i,v,k in lst:
        r=E[i]; old=r[2]; r[2]=v
        r[12]=r[12]+' — 같은 해 다른 대회 값과 맞춰 %d로 씀'%v if '맞춰' not in r[12] else r[12]
        log.append((p,r[9],r[1],old,v))
    t=t[:m.start(1)]+json.dumps(E,ensure_ascii=False,separators=(',',':'))+t[m.end(1):]
    open(f,'w').write(t)
for l in log: print(*l)
