#!/usr/bin/env python3
"""5대 리그 시즌 순위표(승·무·패·득점·실점)를 영어 위키백과 원문(Module:Sports table)에서 읽어 elo/league_points_big5.json에 넣기 (v1.288)
  python3 tools/league_points_fetch.py <캐시 폴더> "프리미어리그 2026-27" [...]   # 시즌 표를 넣거나 바꿈(k는 바꾸지 않음)
그 뒤 python3 tools/league_rank_apply.py --apply. 경기장 성적 순서(감점 전, 승점÷경기 수) 그대로 저장. 진행 중 시즌은 넣지 않는다(시즌이 끝난 뒤).
"""
import re, os, sys, json, time, urllib.request, urllib.parse
P = sys.argv[1] if len(sys.argv) > 1 else '.'
L={'프리미어리그':['{s} Premier League','{s} FA Premier League','{s} Football League First Division','{s} Football League'],'세리에A':['{s} Serie A'],'라리가':['{s} La Liga'],'분데스리가':['{s} Bundesliga'],'리그1':['{s} Ligue 1','{s} French Division 1']}
def raw(title):
    fn=P+'/raw/'+title.replace('/','_')+'.wt'
    if os.path.exists(fn):return open(fn).read()
    u='https://en.wikipedia.org/w/index.php?'+urllib.parse.urlencode({'title':title,'action':'raw'})
    for a in range(6):
        try:
            t=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'soc-calc-research/1.0 (standings lookup)'}),timeout=40).read().decode();break
        except urllib.error.HTTPError as e:
            if e.code==404:t='';break
            if e.code==429:time.sleep(20*(a+1));continue
            raise
    else:t=None
    if t is None:return None
    m=re.match(r'#REDIRECT\s*\[\[([^\]#]+)',t,re.I)
    if m:t=raw(m.group(1).strip())
    open(fn,'w').write(t or '');time.sleep(1);return t
def tableblock(t):
    # Sports table 블록 중 win_ 가 가장 많은 것
    best=None
    for m in re.finditer(r'\{\{\s*#invoke:\s*[Ss]ports table',t):
        i=m.start();d=0;j=i
        while j<len(t):
            if t.startswith('{{',j):d+=1;j+=2;continue
            if t.startswith('}}',j):
                d-=1;j+=2
                if d==0:break
                continue
            j+=1
        b=t[i:j];n=len(re.findall(r'win_\w+\s*=',b))
        if n>=10 and best is None:best=(n,b)
    return best[1] if best else None
def get(title,depth=0):
    t=raw(title)
    if not t:return None,None
    b=tableblock(t)
    if b:return title,b
    if depth>1:return title,None
    # 표 틀 끌어오기
    for m in re.finditer(r'\{\{\s*([^{}|\n]*?(?:table|Table)[^{}|\n]*?)\s*(?:\|[^{}]*)?\}\}',t):
        name=m.group(1).strip()
        if name.startswith(':'):name=name[1:].split('#')[0]
        elif not name.lower().startswith('template:'):name='Template:'+name
        tt,bb=get(name,depth+1)
        if bb:return tt,bb
    for m in re.finditer(r'\{\{\s*:([^{}|#]+)#',t):
        tt,bb=get(m.group(1).strip(),depth+1)
        if bb:return tt,bb
    return title,None
def strip_comments(b):return re.sub(r'<!--.*?-->','',b,flags=re.S)
def params(b):
    b=strip_comments(b);P={}
    b=re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]',r'\1',b)
    b=re.sub(r'\{\{(?:[^{}|]*\|)?([^{}|]*)\}\}',r'\1',b)
    for m in re.finditer(r'\|\s*([\w ]+?)\s*=\s*([^|\n]*)',b):
        P[m.group(1).strip()]=m.group(2).strip()
    return P
def iv(x):
    m=re.match(r'^\s*[+-−]?\d+',(x or '').replace('−','-'));return int(m.group()) if m else 0
def rows(b):
    P=params(b)
    order=[]
    if 'team_order' in P:order=[x.strip() for x in P['team_order'].split(',') if x.strip()]
    else:
        tn=sorted(((int(k[4:]),v) for k,v in P.items() if re.fullmatch(r'team\d+',k)),key=lambda x:x[0]);order=[v for _,v in tn]
    wp=iv(P.get('winpoints','3')) or 3
    out=[]
    for i,c in enumerate(order):
        W,D,L=iv(P.get('win_'+c)),iv(P.get('draw_'+c)),iv(P.get('loss_'+c))
        if W+D+L==0:continue
        nm=P.get('name_'+c,c);nm=re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]',r'\1',nm);nm=re.sub(r'\{\{[^{}]*\}\}|<[^>]*>','',nm).strip()
        adj=iv(P.get('adjust_points_'+c))+iv(P.get('startpoints_'+c))
        gf,ga=iv(P.get('gf_'+c)),iv(P.get('ga_'+c))
        out.append({'team':nm,'code':c,'Pld':W+D+L,'W':W,'D':D,'L':L,'GF':gf,'GA':ga,'raw':wp*W+D,'Pts':wp*W+D+adj,'adj':adj,'ix':i,'ppg':(3*W+D)/(W+D+L),'wp':wp})
    return out
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TWO = {'세리에A': 1994, '라리가': 1995, '분데스리가': 1995, '리그1': 1994, '프리미어리그': 1981}
if __name__ == '__main__':
    os.makedirs(os.path.join(P, 'raw'), exist_ok=True)
    jf = os.path.join(ROOT, 'elo', 'league_points_big5.json'); J = json.load(open(jf, encoding='utf-8'))
    for key in sys.argv[2:]:
        lg, ss = key.split(); y = int(ss[:4]); cands = [f"{y}–{ss[5:]}", f"{y}–{y+1}"] if y != 1999 else ["1999–2000", "1999–00"]
        got = None
        for pat in L[lg]:
            for c in cands:
                tt, b = get(pat.format(s=c))
                if b: got = (tt, b); break
            if got: break
        if not got: print(key, '표 없음'); continue
        R = rows(got[1])
        if y < TWO[lg]:
            for r in R: r['raw'] = 2 * r['W'] + r['D']
        R.sort(key=lambda r: (-r['raw'] / r['Pld'], r['ix']))
        J['seasons'][key] = {'src': 'https://en.wikipedia.org/wiki/' + got[0].replace(' ', '_'), 'two_point': y < TWO[lg],
                             'teams': [[r['team'], r['Pld'], r['W'], r['D'], r['L'], r['GF'], r['GA']] for r in R]}
        print(key, len(R), '팀', got[0])
    json.dump(J, open(jf, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
