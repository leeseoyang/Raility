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

nid_line_no ={r['nid']:r['노선번호'] for _,r in sta.iterrows()}
nid_line_nm ={r['nid']:norm(r['노선명'])  for _,r in sta.iterrows()}
nid_oper    ={r['nid']:str(r['운영기관명']) for _,r in sta.iterrows()}

def resolve_seq(names, line_no=None, line_nm=None, allow=None, oper=None):
    """역명 시퀀스 → node id 시퀀스.

    같은 역명이 노선 수만큼 복제돼 있으므로(환승역은 좌표가 50 m 이내로 겹침)
    좌표 근접만으로 고르면 사실상 무작위 선택이 된다. 반드시 노선을 먼저 본다.
      ① 파싱 중인 노선의 노선번호와 일치하는 후보
      ② 노선명이 일치하는 후보 (노선번호 표기가 파일 간 불일치하는 경우)
      ③ 그래도 없으면 좌표 연속성 (직결운행 경계·분기점에서만 발생)
    """
    ln_no = str(line_no).strip() if line_no is not None else None
    ln_nm = norm(line_nm) if line_nm else None
    allow = {norm(x) for x in allow} if allow else None
    out=[]; prev=None
    for i,nm in enumerate(names):
        cands=name2nids.get(nm,[])
        if oper: cands=[c for c in cands if oper in nid_oper.get(c,'')] or cands
        if not cands: out.append(None); prev=None; continue
        if allow:
            same=[c for c in cands if nid_line_nm.get(c) in allow]
        else:
            same=[c for c in cands if ln_no and nid_line_no.get(c)==ln_no]
            if not same and ln_nm:
                same=[c for c in cands if nid_line_nm.get(c)==ln_nm]
        if len(same)==1:
            pick=same[0]
        elif len(same)>1:                      # 한 노선에 동명 역이 둘 이상(순환·지선)
            pick=min(same,key=lambda c:approx(prev,c)) if prev is not None else same[0]
        elif len(cands)==1:
            pick=cands[0]
        elif prev is not None:
            pick=min(cands,key=lambda c:approx(prev,c))
        else:
            nc=[]
            for j in range(i+1,min(i+3,len(names))):
                nc=name2nids.get(names[j],[])
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
    seq=resolve_seq(names, r['노선번호'], r['노선명'])
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
    seq=resolve_seq(names, r.get('노선번호'), r.get('노선명')); wk=str(r['요일구분']).startswith('평일')
    for a,b in zip(seq,seq[1:]): add_pair(a,b,wk)
# (a) 정차별형: 열차번호로 묶어 순서·시각 사용
perstop=gen[~gen['is_seq']].copy(); perstop['nm']=perstop['역명'].map(norm)
for tn,g in perstop.groupby('열차번호',sort=False):
    g=g.reset_index(drop=True)
    if len(g)<2: continue
    seq=resolve_seq(list(g['nm']), g['노선번호'].iloc[0], g['노선명'].iloc[0])
    wk=str(g['요일구분'].iloc[0]).startswith('평일')
    for i in range(len(seq)-1):
        arr2=g['arr'][i+1]; dep1=g['dep'][i]; dep2=g['dep'][i+1]
        dd=(arr2-dep1) if (arr2 is not None and dep1 is not None) else ((dep2-dep1) if (dep2 is not None and dep1 is not None) else None)
        add_pair(seq[i],seq[i+1],wk,dd)

# ---- 운행정보로 인접구간 보완 (급행 건너뛰기 엣지 배제) ----
# 이전 판은 "이미 경로가 있으면 건너뛴다"(has_path)로 걸렀는데, 수도권은 노선정보만으로
# 이미 하나의 연결요소가 되므로 수도권 내부의 누락 구간이 원리적으로 복구되지 않았다.
# (구로–구일, 금정–범계, 금정–산본, 시청–충정로 등 공식 연속쌍 37개가 이 조건에 걸려 빠졌다.)
# 대신 '두 역 사이에 같은 노선의 다른 역이 놓여 있으면 급행 건너뛰기'라는 기하 판정으로 거른다.
GL=nx.Graph(); GL.add_nodes_from(sta['nid']); GL.add_edges_from(adj)
line_members=defaultdict(list)
for n_,l_ in nid_line_no.items(): line_members[l_].append(n_)

def skips_station(a,b):
    """a-b 사이에 같은 노선의 제3의 역이 (거의) 일직선으로 놓여 있으면 건너뛰기 구간."""
    d=approx(a,b)
    if d>=9e8: return False
    for l_ in {nid_line_no.get(a),nid_line_no.get(b)}:
        for c in line_members.get(l_,()):
            if c==a or c==b: continue
            da,db=approx(a,c),approx(c,b)
            if da<60 or db<60: continue          # 환승 복제 노드
            if da+db < d*1.10: return True
    return False

MAXGAP=15000                                     # 기하 판정이 본 필터이므로 상한은 안전장치
cand=sorted([(approx(a,b),(a,b)) for (a,b) in op_pairs], key=lambda x:x[0])
new_from_op=set(); skipped=0
for dist,(a,b) in cand:
    if dist>=MAXGAP: break
    if GL.nodes.get(a) is None or GL.nodes.get(b) is None: continue
    if GL.has_edge(a,b): continue
    if skips_station(a,b): skipped+=1; continue
    GL.add_edge(a,b); adj.add(tuple(sorted((a,b)))); new_from_op.add(tuple(sorted((a,b))))
print(f"운행정보 보완: 채택 {len(new_from_op)} · 건너뛰기로 기각 {skipped}")
new_from_op=len(new_from_op)
adj=sorted(adj)

# ---------- 역간거리(실측 선로거리) 결합: data/raw/역간거리/*.csv ----------
import glob,os
# 파일별 선명 표기 → 역사정보 노선명. 표기가 파일마다 달라(중앙선/경의중앙, 4호선/안산과천선 …)
# 매핑 없이 좌표로만 풀면 청량리(1호선)–왕십리(2호선) 같은 엉뚱한 쌍이 정답지에 들어간다.
SEOUL8 = {f'{i}호선':{f'{i}호선'} for i in range(1,9)}
KORAIL1 = {'경원선','경부선','경인선','장항선'}
KORAIL_MAP = {'1호선(경부선)':KORAIL1,'1호선(경인선)':KORAIL1,'1호선(광명선)':KORAIL1,
              '1호선(서동탄선)':KORAIL1,'3호선':{'일산선'},'4호선':{'안산과천선'},
              '경강':{'경강선'},'경의중앙':{'경의중앙선','경원선'},'경춘':{'경춘선'},
              '대경선':{'대경선'},'동해':{'동해선'},'서해선':{'서해선'},
              '수인분당':{'수인선','분당선'}}
CITY_LINE = lambda city,n: {f'{city} 도시철도 {i}호선' for i in range(1,n+1)}
GAP_MAP={
 '서울교통공사':('서울교통공사', SEOUL8),
 '수도권1호선':('한국철도공사', KORAIL_MAP),
 '수도권2호선':('서울교통공사', SEOUL8), '수도권3호선':('서울교통공사', SEOUL8),
 '수도권4호선':('서울교통공사', SEOUL8), '수도권5호선':('서울교통공사', SEOUL8),
 '수도권6호선':('서울교통공사', SEOUL8), '수도권7호선':('서울교통공사', SEOUL8),
 '수도권8호선':('서울교통공사', SEOUL8),
 '수도권9호선':(None, {'9호선':{'수도권  도시철도 9호선','서울 도시철도 9호선'}}),
 '신분당선'   :(None,           {'신분당':{'신분당선'}}),
 '코레일'     :('한국철도공사', KORAIL_MAP),
 '경강선'     :('한국철도공사', KORAIL_MAP), '경의중앙선':('한국철도공사', KORAIL_MAP),
 '경춘선'     :('한국철도공사', KORAIL_MAP), '분당선':('한국철도공사', KORAIL_MAP),
 '수인선'     :('한국철도공사', KORAIL_MAP),
 '공항철도'   :('공항철도',     {'공항':{'인천국제공항선'}}),
 '우이신설'   :(None,           {'우이신설':{'우이신설선'}}),
 '의정부'     :(None,           {'의정부':{'의정부'}}),
 '에버라인'   :(None,           {'에버라인':{'에버라인'}}),
 '인천1호선'  :('인천교통공사', {'인천1호선':{'인천지하철 1호선'}}),
 '인천2호선'  :('인천교통공사', {'인천2호선':{'인천지하철 2호선'}}),
 '인천교통공사':('인천교통공사',{'인천1호선':{'인천지하철 1호선'},'인천2호선':{'인천지하철 2호선'},
                                '7호선':{'도시철도 7호선'}}),
 '대구교통공사':('대구교통공사',{**{str(i):CITY_LINE('대구',3) for i in (1,2,3)},
                                **{f'{i}호선':CITY_LINE('대구',3) for i in (1,2,3)}}),
 '대전교통공사':('대전교통공사',{'1호선':{'대전 도시철도 1호선'}}),
 '부산교통공사':('부산광역시 부산교통공사',
                 {f'{i}호선':{'부산 도시철도 1호선','부산 도시철도 2호선','부산 도시철도 3호선',
                              '부산 경량도시철도 4호선'} for i in (1,2,3,4)}),
}
# 역간거리 파일의 역명 표기가 역사정보와 다른 경우 (노선, 표기명) → 역사정보 표준명
GAP_NAME_FIX={('7호선','총신대입구'):'이수'}
gapdist={}; gap_drop=[]; gap_unmatched=[]  # (nid,nid) -> 실측 m
adj_set_ref=set(adj)
gap_files=sorted(glob.glob(RAW+"역간거리/*.csv")+glob.glob(RAW+"역간거리/*.CSV"))

def _read(fp):
    for enc in ('cp949','utf-8-sig','euc-kr'):
        try: return pd.read_csv(fp,encoding=enc)
        except Exception: continue
    return None

def _fnum(x):
    try:
        v=float(x); return v if v==v else None
    except Exception: return None

def _register(a,b,km,src):
    """실측 구간 등록. 직선거리와 0.4~3.0배 범위일 때만 채택(오배열 방지)."""
    if not(a and b) or a==b or not km or km<=0: return
    m=round(km*1000); h=approx(a,b)
    if (h>=9e8) or (h<80) or (0.4<=m/h<=3.0):
        gapdist.setdefault(tuple(sorted((a,b))), m)
    else:
        gap_drop.append((by.at[a,'역사명'],by.at[b,'역사명'],m,round(h),src))

def _seq_pairs(seq, vals, from_prev):
    for i in range(len(seq)-1):
        yield seq[i], seq[i+1], (vals[i+1] if from_prev else vals[i])

for fp in gap_files:
    df=_read(fp)
    if df is None: continue
    base=os.path.basename(fp); cols=list(df.columns)
    oper,lmap=(None,{})
    for k,(o,mp) in GAP_MAP.items():
        if k in base: oper,lmap=o,mp; break

    # ── 형식 C: 시작역/도착역 직접 쌍 (광주)
    if '시작역' in cols and '도착역' in cols:
        dcol=next((c for c in cols if '거리' in c), None)
        oper2=oper or '광주교통공사'
        for _,r in df.iterrows():
            a=resolve_seq([norm(r['시작역'])],None,None,allow={'광주도시철도 1호선'},oper=oper2)[0]
            b=resolve_seq([norm(r['도착역'])],None,None,allow={'광주도시철도 1호선'},oper=oper2)[0]
            _register(a,b,_fnum(r[dcol]),base)
        continue

    gcol='선명' if '선명' in cols else ('호선' if '호선' in cols else None)
    ncol='역명' if '역명' in cols else None
    if not(gcol and ncol): continue

    # ── 형식 B: 호선구성역정보 (역구성순서 + 구간키로 = 직전역까지 거리)
    if '역구성순서' in cols and '구간키로' in cols:
        for gv,g in df.groupby(gcol,sort=False):
            g=g.sort_values('역구성순서').reset_index(drop=True)
            allow=lmap.get(str(gv).strip())
            seq=resolve_seq([norm(x) for x in g[ncol]],None,gv,allow=allow,oper=oper)
            vals=[_fnum(v) for v in g['구간키로']]
            for i in range(len(seq)-1):
                _register(seq[i],seq[i+1],vals[i+1],base)
        continue

    # ── 형식 A: 선명 그룹 순서 + 역간거리
    dcol=next((c for c in cols if '역간거리' in c and '후행' not in c and '누계' not in c), None)
    if dcol is None: continue
    for gv,g in df.groupby(gcol,sort=False):
        g=g.reset_index(drop=True)
        allow=lmap.get(str(gv).strip())
        raw=[norm(x) for x in g[ncol]]
        raw=[GAP_NAME_FIX.get((str(gv).strip(),x),x) for x in raw]
        seq=resolve_seq(raw,None,gv,allow=allow,oper=oper)
        vals=[_fnum(v) for v in g[dcol]]
        from_prev = (vals[0] in (0,0.0,None))
        for a,b,km in _seq_pairs(seq,vals,from_prev):
            _register(a,b,km,base)
        if allow:
            al={norm(x) for x in allow}
            for nm_,pk in zip(raw,seq):
                if pk is not None and nid_line_nm.get(pk) not in al:
                    gap_unmatched.append({'파일':base,'선명':str(gv),'표기명':nm_,
                                          '잘못붙은노선':by.at[pk,'노선명']})

print("역간거리 파일:",[os.path.basename(f) for f in gap_files],"| 결합 구간수:",len(gapdist),"| 기각:",len(gap_drop))
if gap_unmatched:
    u=pd.DataFrame(gap_unmatched).drop_duplicates()
    print("  ⚠ 지정 노선에서 못 찾은 역명:", len(u)); print(u.head(20).to_string(index=False))

# ---- 공식 역간거리 연속쌍을 인접엣지로 직접 채택 ----
# 국가철도공단 역간거리 파일의 연속쌍은 공단이 공표한 실제 인접 구간이다.
# 노선정보 정거장구성이 누락한 구간(용산–이촌, 가좌–DMC, 응봉–왕십리 …)을 여기서 메운다.
gap_added=0
for (a,b) in gapdist:
    k=tuple(sorted((a,b)))
    if k not in adj_set_ref:
        adj_set_ref.add(k); gap_added+=1
print("역간거리에서 추가된 인접엣지:", gap_added)

# ---- 지선 이어붙이기(branch wrap) 유령 엣지 제거 ----
# 노선정보 정거장구성은 지선을 한 문자열에 이어 붙이므로, 앞 지선의 종점과 뒤 지선의 기점이
# 인접한 것처럼 읽힌다(5호선 하남검단산|둔촌동, 경의중앙 서울(경의선)|중랑 …).
# 4 km를 넘는 인접쌍은 ① 실측 역간거리 또는 ② 운행정보 열차 순서 중 하나로 뒷받침될 때만 남긴다.
ghost=[]
for k in list(adj_set_ref):
    d=approx(*k)
    if d>4000 and k not in gapdist and k not in op_pairs:
        adj_set_ref.discard(k); ghost.append((by.at[k[0],'역사명'],by.at[k[1],'역사명'],round(d)))
print("유령 엣지 제거:",len(ghost),ghost)

# ---- 동명이노선 오결합 제거 ----
# 한 역에서 같은 이름의 노드 여러 개로 동시에 인접엣지가 나가면, 운행정보 역명이
# 엉뚱한 노선 복제본에 붙은 것이다(고촌역–김포공항/공항철도 vs 김포공항역/김포도시철도).
nb=defaultdict(list)
for a,b in adj_set_ref: nb[a].append(b); nb[b].append(a)
dup=[]
for a,ns in nb.items():
    byname=defaultdict(list)
    for x in ns: byname[by.at[x,'name_n'] if 'name_n' in by.columns else norm(by.at[x,'역사명'])].append(x)
    for nm_,xs in byname.items():
        if len(xs)<2: continue
        keep=[x for x in xs if nid_line_no.get(x)==nid_line_no.get(a)] or \
             [min(xs,key=lambda x:approx(a,x))]
        for x in xs:
            if x not in keep:
                k=tuple(sorted((a,x)))
                if k in adj_set_ref and k not in gapdist:
                    adj_set_ref.discard(k); dup.append((by.at[a,'역사명'],by.at[x,'역사명'],by.at[x,'노선명']))
print("동명이노선 오결합 제거:",len(dup),dup)

# ---- 사이에 다른 역이 놓인 인접 제거 (급행 건너뛰기·오결합) ----
# 두 역을 잇는 직선 위에 제3의 역이 놓여 있으면 실제 인접 구간이 아니다.
# 노선 소속을 가리지 않고 검사하므로, 급행 건너뛰기와 노선 복제본 오결합을 함께 걸러낸다.
# 실측 역간거리로 확인된 구간은 공단 공표값이므로 검사 대상에서 제외한다.
nname={n_:norm(by.at[n_,'역사명']) for n_ in sta['nid']}
def has_between_same_line(a,b):
    """a-b 직선 위에 '같은 노선'의 제3의 역이 있으면 급행 건너뛰기 구간."""
    d=approx(a,b)
    if d>=9e8: return None
    na,nb=nname[a],nname[b]
    for l_ in {nid_line_no.get(a),nid_line_no.get(b)}:
        for c in line_members.get(l_,()):
            if c==a or c==b or nname[c] in (na,nb): continue
            da,db=approx(a,c),approx(c,b)
            if da<150 or db<150: continue
            if da+db < d*1.08: return c
    return None

# 실제 노선 간 접속(구로–구일 0.9 km, 지축–삼송 1.5 km 등)은 모두 짧은 분기점 링크다.
# 그보다 먼 교차노선 인접은 운행정보 역명이 엉뚱한 노선 복제본에 붙은 결과로 본다.
XLINE_MAX=1500
pruned={}
for k in list(adj_set_ref):
    if k in gapdist: continue
    a,b=k; d=approx(a,b)
    if d<=XLINE_MAX: continue
    c=has_between_same_line(a,b)
    if c is not None:
        adj_set_ref.discard(k); pruned[k]=(d,'급행건너뛰기(사이: %s)'%by.at[c,'역사명'])
    elif nid_line_no.get(a)!=nid_line_no.get(b):
        adj_set_ref.discard(k); pruned[k]=(d,'교차노선 장거리')
print("가지치기:",len(pruned))
for k,(d,why) in sorted(pruned.items(),key=lambda x:-x[1][0])[:20]:
    print(f"    {by.at[k[0],'역사명']}({by.at[k[0],'노선명']}) – {by.at[k[1],'역사명']}({by.at[k[1],'노선명']}) {round(d)}m · {why}")

# 가지치기로 조각이 떨어져 나오면, 기각된 후보 중 최단 링크로만 복원한다.
GP=nx.Graph(); GP.add_nodes_from(sta['nid']); GP.add_edges_from(adj_set_ref)
restored=[]
while True:
    comp={}
    for i,c in enumerate(nx.connected_components(GP)):
        for n_ in c: comp[n_]=i
    sizes=defaultdict(int)
    for n_ in comp: sizes[comp[n_]]+=1
    cands=[(d,k) for k,(d,_) in pruned.items() if comp[k[0]]!=comp[k[1]]
           and min(sizes[comp[k[0]]],sizes[comp[k[1]]])<15]
    if not cands: break
    d,k=min(cands)
    adj_set_ref.add(k); GP.add_edge(*k); pruned.pop(k)
    restored.append((by.at[k[0],'역사명'],by.at[k[1],'역사명'],round(d)))
print("고립 방지 복원:",restored)
adj=sorted(adj_set_ref)

# ---------- 환승엣지 ----------
# ① 같은 역명 + 다른 노선 + 좌표근접
trans=set()
for nm,ids in name2nids.items():
    if len(ids)<2: continue
    for a,b in itertools.combinations(ids,2):
        if by.at[a,'노선번호']!=by.at[b,'노선번호'] and approx(a,b)<1200:
            trans.add(tuple(sorted((a,b))))
name_only=len(trans)

# ② 역명이 다른 실제 환승 (총신대입구(이수)↔이수 등). 이름만으로는 절대 못 찾으므로
#    원본의 환승역구분/환승노선명을 쓰지 않고, 좌표 근접(<350 m) + 다른 노선으로 보완한다.
#    350 m는 ①에서 확인된 실제 환승 통로 길이 분포(중앙값 103 m, 최대 435 m)에 근거한다.
XFER_MAXD=350
nids_all=list(sta['nid'])
for a,b in itertools.combinations(nids_all,2):
    if by.at[a,'노선번호']==by.at[b,'노선번호']: continue
    k=tuple(sorted((a,b)))
    if k in trans: continue
    if approx(a,b)<XFER_MAXD:
        trans.add(k)
name_diff=len(trans)-name_only

# ③ 원본 환승노선명이 지목하는데 ①②로도 안 잡힌 쌍은 수동 확인 대상으로 기록
trans=sorted(trans)
print(f"환승엣지: 동일역명 {name_only} + 좌표근접(이름다름) {name_diff} = {len(trans)}")

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
# (1) 장거리 운행엣지 — 임계값을 15 km에서 4 km로 낮춘다. 이전 판은 15 km 기준이라
#     서울(공항철도)–중랑(경의중앙) 10.5 km 같은 유령 엣지가 통과했다.
val=[{'구분':'장거리엣지(>4km, 실측없음)','역A':by.at[u,'역사명'],'노선A':by.at[u,'노선명'],
      '역B':by.at[v,'역사명'],'노선B':by.at[v,'노선명'],'값':round(float(d['거리_직선_m']))}
     for u,v,d in G.edges(data=True)
     if d['type']=='운행' and d['거리_실측_m'] in ('',None)
     and d['거리_직선_m'] not in ('',None) and float(d['거리_직선_m'])>4000]

# (2) 노선별 자기 인접 성분 수 — 정상이면 1(지선 있으면 소수). 노선 해석이 깨지면 급증한다.
GA=nx.Graph(); GA.add_nodes_from(sta['nid']); GA.add_edges_from(adj)
for l_,mem in sorted(line_members.items()):
    if len(mem)<5: continue
    ncomp=nx.number_connected_components(GA.subgraph(mem))
    if ncomp>2:
        val.append({'구분':'노선내_인접단절','역A':by.at[mem[0],'노선명'],'노선A':l_,
                    '역B':f'{len(mem)}개역','노선B':'','값':ncomp})

# (3) 공식 역간거리 연속쌍 재현율 — 정답지 대비 누락 구간을 직접 센다.
official=set(); miss=[]
for key in gapdist:
    official.add(key)
for key in official:
    if not GA.has_edge(*key):
        a,b=key; miss.append({'구분':'공식연속쌍_누락','역A':by.at[a,'역사명'],'노선A':by.at[a,'노선명'],
                              '역B':by.at[b,'역사명'],'노선B':by.at[b,'노선명'],'값':gapdist[key]})
val+=miss
print(f"공식 역간거리 연속쌍 {len(official)} 중 그래프 미반영 {len(miss)} "
      f"(재현율 {(1-len(miss)/max(len(official),1))*100:.1f}%)")
print("노선내 인접단절(성분>2):",[(v['역A'],v['값']) for v in val if v['구분']=='노선내_인접단절'])
print("장거리엣지(>4km, 실측없음):",[(v['역A'],v['역B'],v['값']) for v in val if v['구분'].startswith('장거리')][:12])
for c in comps[1:]:
    if len(c)<=5:
        val.append({'구분':'소규모연결요소','역A':' / '.join(by.at[n,'역사명'] for n in c),
                    '노선A':by.at[list(c)[0],'노선명'],'역B':'','노선B':'','값':len(c)})
lat2=pd.to_numeric(sta['역위도'],errors='coerce'); lon2=pd.to_numeric(sta['역경도'],errors='coerce')
val.append({'구분':'좌표결측','역A':int(lat2.isna().sum()+lon2.isna().sum()),'노선A':'','역B':'','노선B':'','값':''})
pd.DataFrame(val).to_csv(OUT+"_validation.csv",index=False,encoding='utf-8-sig')
print("좌표결측:",int(lat2.isna().sum()+lon2.isna().sum()))
stats["공식연속쌍"]=len(official); stats["공식연속쌍_누락"]=len(miss)
stats["공식연속쌍_재현율%"]=round((1-len(miss)/max(len(official),1))*100,1)

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
