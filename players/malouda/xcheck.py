import re,json,glob,os,sys,unicodedata
def load(f):
    s=open(f,encoding='utf-8').read()
    m=re.search(r'const (\w+)_E=(\[.*?\]);\nconst',s,re.S)
    return m.group(1),json.loads(m.group(2))
me=json.load(open('malouda.json'))['E']
mine=[[r['type'],r['opp'],r['elo'],r['comp'],r['min'],r['gf'],r['ga'],r['ko'],r['pk'],r['date'],r['et'],r['dm'],r['lv'],r['note']]+([r['tie']] if r.get('tie') else []) for r in me]
def nm(s): return unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
others={}
for f in sorted(glob.glob('/home/user/soc/src/data/*.js')):
    b=os.path.basename(f)
    if b in('hon.js','mld.js'): continue
    try: p,E=load(f)
    except Exception as e: continue
    others[p]=E
print(len(others))
# 1) others' assist rows noting Malouda -> my goal rows
bad=0;cnt=0
for p,E in others.items():
    for r in E:
        if r[0]=='a' and 'malouda' in nm(str(r[13])):
            cnt+=1
            c=[m for m in mine if m[0]=='g' and m[9]==r[9] and abs(m[4]-r[4])<=2]
            if not c: print('NO MATCH (their assist, my goal missing)',p,r[:13]); bad+=1; continue
            m=c[0]
            for i,n in ((2,'elo'),(3,'comp'),(5,'gf'),(6,'ga'),(7,'ko'),(12,'lv'),(1,'opp')):
                if m[i]!=r[i]: print('MISMATCH',p,n,r[9],r[1],'theirs',r[i],'mine',m[i]); bad+=1
            if (len(m)>14)!=(len(r)>14) or (len(m)>14 and m[14]!=r[14]): print('TIE MISMATCH',p,r[9],r[14:] ,m[14:]); bad+=1
print('their assists from Malouda',cnt,'bad',bad)
# 2) my assist rows (scorer name) -> their goal rows
nm_map={'Didier Drogba':'dro','Frank Lampard':'lam','Michael Ballack':'blk','Andriy Shevchenko':'she','Fernando Torres':'tor','Karim Benzema':'bzm','Juninho Pernambucano':'jun','Nicolas Anelka':None}
bad=0;cnt=0
for m in mine:
    if m[0]!='a': continue
    # find any other player's goal row same date, minute±2
    for p,E in others.items():
        for r in E:
            if r[0]=='g' and r[9]==m[9] and abs(r[4]-m[4])<=2 and r[1]==m[1]:
                cnt+=1
                diffs=[n for i,n in ((2,'elo'),(3,'comp'),(5,'gf'),(6,'ga'),(7,'ko'),(12,'lv')) if m[i]!=r[i]]
                if (len(m)>14)!=(len(r)>14) or (len(m)>14 and m[14]!=r[14]): diffs.append('tie')
                print(('OK ' if not diffs else 'DIFF ')+p,m[9],m[1],m[4],m[13],diffs,'| their note',r[13])
