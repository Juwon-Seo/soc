# J리그 공식 기록(data.j-league.or.jp SFMS02) 판독: 요코하마 (F・)마리노스 1997~2002.7 경기에서 나카무라 슌스케(中村 俊輔) 출전·교체·득점
import re,html,json,sys,os
D=sys.argv[1]; OUT=sys.argv[2]
L=json.load(open(os.path.join(D,'jl_mar_list.json')))
def tx(s): return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',s))).strip()
ME='中村 俊輔'
res=[]
for o in L:
    mid=o[9]; t=open(os.path.join(D,'jl',mid+'.html'),encoding='utf-8').read()
    teams=re.findall(r'class="team-name"[^>]*>\s*<a[^>]*>([^<]*)</a>',t)
    left = o[5] in ('横浜M','横浜FM')   # 목록의 홈 팀이 마리노스면 왼쪽
    halves=re.findall(r'<dd class="left-area">(\d+)</dd>\s*<dt class="png-bg">([^<]*)</dt>\s*<dd class="right-area">(\d+)</dd>',t)
    et='延長前半' in [h[1] for h in halves]
    pk=[h for h in halves if 'ＰＫ' in h[1] or 'PK' in h[1]]
    g=t[t.find('得点イベント情報エリア　Start'):t.find('得点イベント情報エリア　End')]
    la=g[:g.find('<th>得点</th>')]; ra=g[g.find('<th>得点</th>'):]
    def goals(seg,lft):
        tds=[tx(x) for x in re.findall(r'<td>(.*?)</td>',seg,re.S) if '<table' not in x]
        out=[]
        for i in range(0,len(tds)-1,2):
            a,b=tds[i],tds[i+1]
            nm,mn=(a,b) if lft else (b,a)
            out.append((nm,mn))
        return out
    GL=[('L',)+x for x in goals(la,True)]; GR=[('R',)+x for x in goals(ra,False)]
    sec={}
    for m in re.finditer(r'<!-- (A\d)　(先発メンバー|控えメンバー|交代イベント)情報エリア　Start -->(.*?)<!-- \1　\2情報エリア　End',t,re.S):
        sec.setdefault(m.group(2),[]).append(m.group(3))
    side=0 if left else 1
    def names(s): return [tx(x) for x in re.findall(r'<td class="name">(.*?)</td>',s,re.S)]
    st=sec.get('先発メンバー',['',''])[side] if len(sec.get('先発メンバー',[]))>1 else ''
    bn=sec.get('控えメンバー',['',''])[side] if len(sec.get('控えメンバー',[]))>1 else ''
    # 交代 box: left box / right box may be missing if no subs → identify by position in page
    subs_all=[]
    for m in re.finditer(r'<div class="two-column-table-box-(l|r)">\s*<!-- A7　交代イベント情報エリア　Start -->(.*?)<!-- A7　交代イベント情報エリア　End',t,re.S):
        subs_all.append((m.group(1),m.group(2)))
    sb=''.join(s for lr,s in subs_all if (lr=='l')==bool(left))
    subs=re.findall(r'<td class="change">\s*(▽|▲)\s*</td>\s*<td class="name">(.*?)</td>\s*<td class="time">(.*?)</td>',sb,re.S)
    ev=[];last=None
    for ch,nm,tm in subs:
        nm=tx(nm);tm=tx(tm) or last;last=tm;ev.append((ch,nm,tm))
    res.append(dict(mid=mid,url='https://data.j-league.or.jp/SFMS02/?match_card_id='+mid,list=o,teams=teams,mar_left=bool(left),et=et,halves=halves,
        goals=GL+GR,start=ME in names(st),bench=ME in names(bn),ev=[e for e in ev if e[1]==ME]))
json.dump(res,open(OUT,'w'),ensure_ascii=False,indent=0)
print(len(res))
