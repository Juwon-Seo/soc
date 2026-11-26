# J리그 공식 기록(data.j-league.or.jp) 판독: jleague_kyoto_list.json(SFMS01/search?competition_years=2000~2002 목록 중 교토 경기)의 match_card_id마다
# https://data.j-league.or.jp/SFMS02/?match_card_id=<id> 를 jl/<id>.html로 받아(1.5초 간격, 원본 HTML은 보관하지 않음) 이 스크립트로 읽고,
# 스크래치에서 jleague_official.json(출전·교체·득점)을 만듦.
import re,html,json,sys,os
D=os.path.dirname(os.path.abspath(__file__))
L=json.load(open(os.path.join(D,'jleague_kyoto_list.json')))
def tx(s): return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',s))).strip()
res=[]
for o in L:
    mid=o[9]
    if o[0]=='2003' or not mid: continue
    t=open(os.path.join(D,'jl',mid+'.html'),encoding='utf-8').read()
    teams=re.findall(r'class="team-name"[^>]*>\s*<a[^>]*>([^<]*)</a>',t)
    left_k='京都' in teams[0]
    halves=re.findall(r'<dd class="left-area">(\d+)</dd>\s*<dt class="png-bg">([^<]*)</dt>\s*<dd class="right-area">(\d+)</dd>',t)
    et='延長前半' in [h[1] for h in halves]
    # goals
    g=t[t.find('得点イベント情報エリア　Start'):t.find('得点イベント情報エリア　End')]
    la=g[g.find('class="left-area"'):g.find('<th>得点</th>')]; ra=g[g.find('<th>得点</th>'):]
    def goals(seg,left):
        tds=[tx(x) for x in re.findall(r'<td>(.*?)</td>',seg,re.S)]
        out=[]
        for i in range(0,len(tds)-1,2):
            a,b=tds[i],tds[i+1]
            if left: out.append((a,b))
            else: out.append((b,a))
        return out
    GL,GR=goals(la,True),goals(ra,False)
    # lineups: split into boxes
    boxes=re.findall(r'<div class="two-column-table-box-(l|r)">(.*?)(?=<div class="two-column-table-box-(?:l|r)">|<!-- A\d+　(?!先発|控え|交代)|$)',t,re.S)
    sec={}
    for m in re.finditer(r'<!-- (A\d)　(先発メンバー|控えメンバー|交代イベント|警告|退場)[^S]*Start -->(.*?)<!-- \1',t,re.S):
        sec.setdefault(m.group(2),[]).append(m.group(3))
    side=0 if left_k else 1
    def names(s): return [tx(x) for x in re.findall(r'<td class="name">(.*?)</td>',s,re.S)]
    st=sec.get('先発メンバー',['',''])[side]; bn=sec.get('控えメンバー',['',''])[side]; sb=sec.get('交代イベント',['',''])[side] if len(sec.get('交代イベント',[]))>1 else ''
    start='朴 智星' in names(st); bench='朴 智星' in names(bn)
    subs=re.findall(r'<td class="change">\s*(▽|▲)\s*</td>\s*<td class="name">(.*?)</td>\s*<td class="time">(.*?)</td>',sb,re.S)
    ev=[];last=None
    for ch,nm,tm in subs:
        nm=tx(nm);tm=tx(tm) or last;last=tm;ev.append((ch,nm,tm))
    park_ev=[e for e in ev if e[1]=='朴 智星']
    red='退場' in t and '朴　智星' in t[t.find('退場'):t.find('退場')+3000] 
    res.append(dict(mid=mid,comp=o[1],rnd=o[2],date=o[3],home=o[5],score=o[6],away=o[7],teams=teams,kyoto_left=left_k,et=et,halves=halves,
        GL=GL,GR=GR,start=start,bench=bench,park_ev=park_ev,nsec={k:len(v) for k,v in sec.items()}))
json.dump(res,open(os.path.join(D,'jl_parsed.json'),'w'),ensure_ascii=False,indent=0)
for r in res:
    pg=[x for x in (r['GL'] if r['kyoto_left'] else r['GR']) if '朴' in x[0]]
    print(r['mid'],r['date'],r['comp'][:8],r['rnd'][:8],r['home'],r['score'],r['away'],'ET' if r['et'] else '','S' if r['start'] else ('B' if r['bench'] else '-'),r['park_ev'],pg, r['nsec'] if r['mid']=='5011' else '')
