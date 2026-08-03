# -*- coding: utf-8 -*-
"""
도시철도 네트워크 그래프 구축 (정밀 버전)
- 노드: 역사정보 (복합키 노선번호|역번호)
- 인접엣지: 노선정보 정거장구성 ∪ 운행정보(일반열차) 순서  → 신설/연장 구간 보완
- 환승엣지: 동일 역명 + 좌표근접(<1.2km) + 다른 노선
- 가중치: 직선거리(하버사인), 소요시간(운행정보 중앙값), 평일 운행횟수(운행정보)
"""
import pandas as pd, re, unicodedata, itertools, math, json
from collections import defaultdict
import networkx as nx

RAW="data/raw/"; OUT="data/processed/"

def norm(s):
    if pd.isna(s): return ""
    s=unicodedata.normalize("NFC",str(s)); s=re.sub(r"\(.*?\)","",s); s=re.sub(r"\s+","",s)
    if s.endswith("역") and len(s)>1: s=s[:-1]
    return s

# 노선정보 정거장구성 역명 표기 → 역사정보 표준명 (개명/오타/약칭 보정, 근거는 README 참조)
ALIAS={'교대앞':'교대','디엠시':'디지털미디어시티','민주묘지':'4.19민주묘지','성당못':'서부정류장',
       '성서공단':'성서산업단지','송도달비축제공원':'송도달빛축제공원','신길온천':'능길'}
def hangul_name(t):
    t=unicodedata.normalize("NFC",str(t)).strip().strip('"')
    m=re.search(r"[가-힣].*$",t); nm=norm(m.group(0) if m else t)
    return ALIAS.get(nm,nm)

# ---------- 노드 ----------
sta=pd.read_excel(RAW+"전체_도시철도역사정보_20260630.xlsx")
for c in ['역번호','노선번호']: sta[c]=sta[c].astype(str).str.strip()
# 좌표 오류 보정 (근거: 원본 좌표가 동명이역/오입력. README 참조)
COORD_FIX={('양원역','경의중앙선'):(37.60130,127.10670),  # 원본 36.96/129.09(봉화 영동선 양원역) → 중랑구 양원역
           ('마곡','5호선'):(37.560180,126.825484),        # 원본이 발산 좌표와 중복 → 실측거리로 교차검증해 보정
           ('이촌(국립중앙박물관)','4호선'):(37.522476,126.973816)}  # 원본이 신용산 좌표와 중복 → 이촌역 실제 위치로 보정
for (nm,ln),(la,lo) in COORD_FIX.items():
    m=(sta['역사명']==nm)&(sta['노선명']==ln)
    sta.loc[m,'역위도']=la; sta.loc[m,'역경도']=lo
sta['역사명']=sta['역사명'].astype(str).str.replace(r'\s+',' ',regex=True).str.strip()
sta['name_n']=sta['역사명'].map(norm)
sta['nid']=sta['노선번호']+"|"+sta['역번호']
sta=sta.drop_duplicates('nid',keep='first').reset_index(drop=True)
by=sta.set_index('nid')
sta['lat']=pd.to_numeric(sta['역위도'],errors='coerce'); sta['lon']=pd.to_numeric(sta['역경도'],errors='coerce')
lat=sta.set_index('nid')['lat'].to_dict(); lon=sta.set_index('nid')['lon'].to_dict()
name2nids=defaultdict(list)
for _,r in sta.iterrows(): name2nids[r['name_n']].append(r['nid'])

def hav(a,b):
    va,vb,la,lb=lat.get(a),lat.get(b),lon.get(a),lon.get(b)
    if any(v is None or pd.isna(v) for v in (va,vb,la,lb)): return None
    R=6371000.0; import math as m
    p1,p2=m.radians(va),m.radians(vb); dphi=m.radians(vb-va); dl=m.radians(lb-la)
    x=m.sin(dphi/2)**2+m.cos(p1)*m.cos(p2)*m.sin(dl/2)**2
    return R*2*m.atan2(m.sqrt(x),m.sqrt(1-x))
def approx(a,b):
    va,vb,la,lb=lat.get(a),lat.get(b),lon.get(a),lon.get(b)
    if any(v is None or pd.isna(v) for v in (va,vb,la,lb)): return 9e9
    return math.hypot((va-vb)*111000,(la-lb)*88000)

def resolve_seq(names):
    """역명 시퀀스 → node id 시퀀스 (연속성 기반 후보 선택)"""
    out=[]; prev=None
    for i,nm in enumerate(names):
        cands=name2nids.get(nm,[])
        if not cands: out.append(None); prev=None; continue
        if prev is not None and len(cands)>1: pick=min(cands,key=lambda c:approx(prev,c))
        elif len(cands)==1: pick=cands[0]
        else:
            nc=[];
            for j in range(i+1,min(i+3,len(names))):
                nc=name2nids.get(names[j],[]);
                if nc: break
            pick=min(cands,key=lambda c:min([approx(c,x) for x in nc],default=0)) if nc else cands[0]
        out.append(pick); prev=pick
    return out

# ---------- 인접엣지: 노선정보 ----------
lin=pd.read_excel(RAW+"전체_도시철도노선정보_20260630.xlsx")
lin['노선번호']=lin['노선번호'].astype(str).str.strip()
adj=set()
for _,r in lin.iterrows():
    if pd.isna(r['정거장구성']): continue
    names=[hangul_name(t) for t in re.split(r'[,+]',str(r['정거장구성'])) if t.strip()]
    seq=resolve_seq(names)
    for a,b in zip(seq,seq[1:]):
        if a and b and a!=b: adj.add(tuple(sorted((a,b))))
adj_from_line=len(adj)

# ---------- 인접엣지 보완 + 가중치: 운행정보(일반) ----------
# 운행정보는 두 형식 혼재: (a) 1행=1정차(시각 有), (b) 1행=열차 전체경로('+'로 나열)
op=pd.read_excel(RAW+"전체_도시철도운행정보_20260228.xlsx")
op=op.rename(columns={'정가장출발시각':'출발','정거장도착시각':'도착','운행구간정거장':'역명'})
def to_sec(t):
    if pd.isna(t): return None
    try:
        h,m,s=str(t).split(':'); return int(h)*3600+int(m)*60+int(s)
    except: return None
op['arr']=op['도착'].map(to_sec); op['dep']=op['출발'].map(to_sec)
def hname(t):  # '001-가락시장' 형태 → 한글명
    t=unicodedata.normalize("NFC",str(t)).strip()
    m=re.search(r"[가-힣].*$",t); return norm(m.group(0) if m else t)
gen=op[op['운행유형']=='일반'].reset_index(drop=True)
gen['is_seq']=gen['역명'].astype(str).str.contains(r'[+,]')
tt=defaultdict(list); freqwk=defaultdict(int); op_pairs=set()

def add_pair(a,b,wk,dd=None):
    if not(a and b) or a==b: return
    key=tuple(sorted((a,b))); op_pairs.add(key)
    if wk: freqwk[key]+=1
    if dd is not None:
        if dd<0: dd+=24*3600
        if 0<dd<3600: tt[key].append(dd)

# (b) 전체경로형: 한 행이 곧 시퀀스
for _,r in gen[gen['is_seq']].iterrows():
    names=[hname(t) for t in re.split(r'[,+]',str(r['역명'])) if t.strip()]
    seq=resolve_seq(names); wk=str(r['요일구분']).startswith('평일')
    for a,b in zip(seq,seq[1:]): add_pair(a,b,wk)
# (a) 정차별형: 열차번호로 묶어 순서·시각 사용
perstop=gen[~gen['is_seq']].copy(); perstop['nm']=perstop['역명'].map(norm)
for tn,g in perstop.groupby('열차번호',sort=False):
    g=g.reset_index(drop=True)
    if len(g)<2: continue
    seq=resolve_seq(list(g['nm'])); wk=str(g['요일구분'].iloc[0]).startswith('평일')
    for i in range(len(seq)-1):
        arr2=g['arr'][i+1]; dep1=g['dep'][i]; dep2=g['dep'][i+1]
        dd=(arr2-dep1) if (arr2 is not None and dep1 is not None) else ((dep2-dep1) if (dep2 is not None and dep1 is not None) else None)
        add_pair(seq[i],seq[i+1],wk,dd)

# ---- 운행정보는 '짧은 다리 엣지'로만 구조 보완(건너뛰기 엣지 배제) ----
# 노선정보 구조에서 서로 다른 연결요소를 잇는 <2.5km 엣지만 채택
GL=nx.Graph(); GL.add_nodes_from(sta['nid']); GL.add_edges_from(adj)
cand=sorted([(approx(a,b),(a,b)) for (a,b) in op_pairs], key=lambda x:x[0])
new_from_op=set()
for dist,(a,b) in cand:
    if dist>=4000: break
    if GL.nodes.get(a) is None or GL.nodes.get(b) is None: continue
    import networkx as _nx
    if not _nx.has_path(GL,a,b):
        GL.add_edge(a,b); adj.add(tuple(sorted((a,b)))); new_from_op.add(tuple(sorted((a,b))))
new_from_op=len(new_from_op)
adj=sorted(adj)

# ---------- 역간거리(실측 선로거리) 결합: data/raw/역간거리/*.csv ----------
import glob,os
gapdist={}; gap_drop=[]  # (nid,nid) -> 실측 m
gap_files=sorted(glob.glob(RAW+"역간거리/*.csv")+glob.glob(RAW+"역간거리/*.CSV"))
for fp in gap_files:
    df=None
    for enc in ('cp949','utf-8-sig','euc-kr'):
        try: df=pd.read_csv(fp,encoding=enc); break
        except Exception: continue
    if df is None: continue
    cols=list(df.columns)
    gcol='선명' if '선명' in cols else ('호선' if '호선' in cols else None)
    ncol='역명' if '역명' in cols else None
    dcol=next((c for c in cols if '역간거리' in c and '후행' not in c and '누계' not in c), None)
    if not(gcol and ncol and dcol): continue
    def fnum(x):
        try: return float(x)
        except: return None
    for gv,g in df.groupby(gcol,sort=False):
        g=g.reset_index(drop=True)
        seq=resolve_seq([norm(x) for x in g[ncol]])
        vals=[fnum(v) for v in g[dcol]]
        # 규약 판별: 첫 값이 0/결측 → '이전역에서', 아니면 '다음역까지'
        from_prev = (vals[0] in (0,0.0,None))
        for i in range(len(seq)-1):
            a,b=seq[i],seq[i+1]
            km=vals[i+1] if from_prev else vals[i]
            if a and b and a!=b and km and km>0:
                m=round(km*1000); h=approx(a,b)
                # 실측/직선 교차검증: 직선이 신뢰구간이면(>80m) 0.4~3.0배만 채택(오배열 방지). 직선이 비정상(<80m)이면 실측 신뢰
                if (h>=9e8) or (h<80) or (0.4<=m/h<=3.0):
                    gapdist[tuple(sorted((a,b)))]=m
                else:
                    gap_drop.append((by.at[a,'역사명'],by.at[b,'역사명'],m,round(h)))
print("역간거리 파일:",[os.path.basename(f) for f in gap_files],"| 결합 구간수:",len(gapdist),"| 기각:",len(gap_drop))

# ---------- 환승엣지 ----------
trans=sorted({tuple(sorted((a,b))) for nm,ids in name2nids.items() if len(ids)>1
              for a,b in itertools.combinations(ids,2)
              if by.at[a,'노선번호']!=by.at[b,'노선번호'] and approx(a,b)<1200})

# ---------- 그래프 ----------
import numpy as np
G=nx.Graph()
for _,r in sta.iterrows():
    G.add_node(r['nid'],역사명=r['역사명'],노선명=r['노선명'],운영기관=r['운영기관명'],
               lat=r['lat'] if pd.notna(r['lat']) else '',lon=r['lon'] if pd.notna(r['lon']) else '',
               환승역=str(r['환승역구분']))
adj_rows=[]
for a,b in adj:
    key=tuple(sorted((a,b)))
    hv=hav(a,b); hv=round(hv) if hv is not None else ''
    실측=gapdist.get(key,'')
    거리=실측 if 실측!='' else hv          # 실측 우선, 없으면 직선
    times=tt.get(key,[]); tmed=int(np.median(times)) if times else ''
    fw=freqwk.get(key,'')
    G.add_edge(a,b,type='운행',거리_m=거리,거리_실측_m=실측,거리_직선_m=hv,소요시간_s=tmed,평일운행횟수=fw)
    adj_rows.append({'source':a,'target':b,'역A':by.at[a,'역사명'],'역B':by.at[b,'역사명'],
                     '거리_m':거리,'거리_실측_m':실측,'거리_직선_m':hv,'소요시간_s':tmed,'평일운행횟수':fw})
for a,b in trans:
    G.add_edge(a,b,type='환승',거리_m=0,거리_실측_m='',거리_직선_m=0,소요시간_s='',평일운행횟수='')

comps=sorted(nx.connected_components(G),key=len,reverse=True)
iso=[n for n in G if G.degree(n)==0]
wcov=sum(1 for r in adj_rows if r['소요시간_s']!='')
fcov=sum(1 for r in adj_rows if r['평일운행횟수']!='')
stats={"노드수":G.number_of_nodes(),"엣지수":G.number_of_edges(),
       "운행엣지":len(adj),"  ├노선정보":adj_from_line,"  └운행정보보완":new_from_op,
       "환승엣지":len(trans),"연결요소수":len(comps),"최대요소":len(comps[0]),
       "최대요소비율%":round(len(comps[0])/G.number_of_nodes()*100,1),
       "상위요소":[len(c) for c in comps[:8]],"고립노드수":len(iso),
       "소요시간_커버리지%":round(wcov/len(adj)*100,1),"운행빈도_커버리지%":round(fcov/len(adj)*100,1),
       "실측거리_커버리지%":round(sum(1 for r in adj_rows if r['거리_실측_m']!='')/len(adj)*100,1)}
print(json.dumps(stats,ensure_ascii=False,indent=2))
print("고립노드:",[(by.at[n,'역사명'],by.at[n,'노선명']) for n in iso])

# ---------- 검증 리포트 ----------
val=[{'구분':'장거리엣지(>15km)','역A':by.at[u,'역사명'],'노선A':by.at[u,'노선명'],
      '역B':by.at[v,'역사명'],'노선B':by.at[v,'노선명'],'값':round(float(d['거리_직선_m']))}
     for u,v,d in G.edges(data=True) if d['type']=='운행' and d['거리_직선_m'] not in ('',None) and float(d['거리_직선_m'])>15000]
for c in comps[1:]:
    if len(c)<=5:
        val.append({'구분':'소규모연결요소','역A':' / '.join(by.at[n,'역사명'] for n in c),
                    '노선A':by.at[list(c)[0],'노선명'],'역B':'','노선B':'','값':len(c)})
lat2=pd.to_numeric(sta['역위도'],errors='coerce'); lon2=pd.to_numeric(sta['역경도'],errors='coerce')
val.append({'구분':'좌표결측','역A':int(lat2.isna().sum()+lon2.isna().sum()),'노선A':'','역B':'','노선B':'','값':''})
pd.DataFrame(val).to_csv(OUT+"_validation.csv",index=False,encoding='utf-8-sig')
print("장거리엣지(>15km):",sum(1 for x in val if x['구분']=='장거리엣지(>15km)'),
      "| 좌표결측:",int(lat2.isna().sum()+lon2.isna().sum()))

# ---------- 저장 ----------
out=sta[['nid','역번호','역사명','노선번호','노선명','운영기관명','역위도','역경도','환승역구분','환승노선명','역사도로명주소']].rename(columns={'nid':'node_id'})
out.to_csv(OUT+"nodes.csv",index=False,encoding='utf-8-sig')
pd.DataFrame(adj_rows).to_csv(OUT+"edges_adjacency.csv",index=False,encoding='utf-8-sig')
pd.DataFrame([{'source':a,'target':b,'역A':by.at[a,'역사명'],'역B':by.at[b,'역사명']} for a,b in trans]).to_csv(OUT+"edges_transfer.csv",index=False,encoding='utf-8-sig')
ea=pd.concat([pd.DataFrame(adj_rows)[['source','target']].assign(type='운행'),
              pd.DataFrame(trans,columns=['source','target']).assign(type='환승')],ignore_index=True)
ea.to_csv(OUT+"edges_all.csv",index=False,encoding='utf-8-sig')
nx.write_graphml(G,OUT+"network.graphml")
json.dump(stats,open(OUT+"_build_stats.json","w"),ensure_ascii=False,indent=2)
print("\n저장 완료.")
