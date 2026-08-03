# -*- coding: utf-8 -*-
"""
지식그래프 인터랙티브 탐색기(kg_explorer.html) 생성

kg/ 산출물을 단일 HTML 파일로 묶는다. 별도 설치·서버 없이 브라우저로 열면
역을 클릭해 해당 역의 KG 관계(노선·기관·지역·인접역·환승역)를 확인할 수 있다.
"""
import json
import pandas as pd

KG, OUT = "kg/", "kg_explorer.html"

CAT_L = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
CAT_D = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"]


def build():
    n = pd.read_csv(KG + "kg_nodes.csv")
    e = pd.read_csv(KG + "kg_edges.csv")
    st = n[n["type"] == "Station"].copy()
    lab = dict(zip(n["id"], n["label"]))

    def one(pred):
        d = e[e["predicate"] == pred]
        return dict(zip(d["source"], d["target"]))

    on_line, by_op = one("ON_LINE"), one("OPERATED_BY")
    in_reg, in_area = one("LOCATED_IN"), one("IN_METRO_AREA")

    ids = list(st["id"])
    idx = {s: i for i, s in enumerate(ids)}
    # 권역은 규모순 — 색상 슬롯 1(파랑)이 가장 큰 수도권에 배정되도록
    areas = list(pd.Series([lab.get(in_area.get(s), "") for s in ids])
                 .replace("", pd.NA).dropna().value_counts().index)
    lines = sorted({lab.get(on_line.get(s), "") for s in ids} - {""})

    def f(v, d=0.0):
        try:
            x = float(v)
            return d if x != x else round(x, 4)
        except (TypeError, ValueError):
            return d

    nodes = [[
        st.iloc[i]["label"], f(st.iloc[i]["lat"]), f(st.iloc[i]["lon"]),
        lines.index(lab.get(on_line.get(s), "")) if lab.get(on_line.get(s), "") in lines else -1,
        lab.get(by_op.get(s), ""), lab.get(in_reg.get(s), ""),
        areas.index(lab.get(in_area.get(s), "")) if lab.get(in_area.get(s), "") in areas else -1,
        f(st.iloc[i]["매개중심성"]), f(st.iloc[i]["승객가중효율저하율"]),
        int(f(st.iloc[i]["단절유발"])), str(st.iloc[i].get("환승역", "")),
    ] for i, s in enumerate(ids)]

    links = []
    for _, r in e[e["predicate"].isin(["CONNECTS_TO", "TRANSFERS_TO"])].iterrows():
        a, b = idx.get(r["source"]), idx.get(r["target"])
        if a is None or b is None:
            continue
        links.append([a, b, 0 if r["predicate"] == "CONNECTS_TO" else 1,
                      f(r.get("거리_m")), f(r.get("소요시간_s")), f(r.get("평일운행횟수"))])

    counts = n["type"].value_counts().to_dict()
    rel = e["predicate"].value_counts().to_dict()
    data = {"nodes": nodes, "links": links, "areas": areas, "lines": lines,
            "counts": counts, "rel": rel}

    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False,
                                                   separators=(",", ":")))
    html = html.replace("__CAT_L__", json.dumps(CAT_L)).replace("__CAT_D__", json.dumps(CAT_D))
    with open(OUT, "w", encoding="utf-8") as fp:
        fp.write(html)
    print(f"저장 → {OUT}  (역 {len(nodes)} · 관계 {len(links)})")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>도시철도 지식그래프 탐색기</title>
<style>
:root{color-scheme:light;
 --s1:#fcfcfb; --s2:#f2f1ec; --ink:#0b0b0b; --ink2:#52514e; --ink3:#8a8880; --line:#dedcd4;}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;
 --s1:#1a1a19; --s2:#232322; --ink:#fff; --ink2:#c3c2b7; --ink3:#8a8880; --line:#37372f;}}
*{box-sizing:border-box}
body{margin:0;font:14px/1.5 -apple-system,"Segoe UI","Malgun Gothic",sans-serif;
 background:var(--s1);color:var(--ink);overflow:hidden}
#wrap{display:flex;height:100vh}
#main{flex:1;position:relative;min-width:0}
canvas{display:block;cursor:crosshair}
#side{width:330px;border-left:1px solid var(--line);background:var(--s2);
 overflow-y:auto;padding:16px;flex-shrink:0}
#bar{position:absolute;top:12px;left:12px;right:12px;display:flex;gap:8px;
 flex-wrap:wrap;align-items:center;z-index:5}
select,input{font:13px inherit;padding:6px 9px;border:1px solid var(--line);
 border-radius:7px;background:var(--s1);color:var(--ink)}
input{width:150px}
h1{font-size:15px;margin:0 0 3px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--ink3);
 margin:20px 0 7px;font-weight:600}
.sub{color:var(--ink2);font-size:12px;margin:0 0 14px}
.kv{display:flex;justify-content:space-between;gap:10px;padding:4px 0;
 border-bottom:1px solid var(--line);font-size:13px}
.kv span:first-child{color:var(--ink2);flex-shrink:0}
.kv span:last-child{text-align:right;font-variant-numeric:tabular-nums}
.tri{font-size:12.5px;padding:5px 0;border-bottom:1px solid var(--line);color:var(--ink2)}
.tri b{color:var(--ink);font-weight:600}
.pred{display:inline-block;font-size:10.5px;padding:1px 6px;border-radius:4px;
 background:var(--line);color:var(--ink2);margin-right:6px;font-family:ui-monospace,monospace}
.pill{display:inline-flex;align-items:center;gap:5px;font-size:12px;margin:2px 8px 2px 0;color:var(--ink2)}
.dot{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.hint{color:var(--ink3);font-size:12.5px}
#legend{position:absolute;right:12px;top:58px;background:var(--s1);
 border:1px solid var(--line);border-radius:9px;padding:9px 11px;max-width:210px}
.badge{display:inline-block;padding:1px 7px;border-radius:99px;font-size:11px;
 background:#eb683422;color:#eb6834;margin-left:6px}
@media (prefers-color-scheme:dark){.badge{background:#d9592633;color:#d95926}}
</style></head><body>
<div id="wrap">
 <div id="main">
  <div id="bar">
   <select id="color">
    <option value="area">색상: 권역</option>
    <option value="impact">색상: 승객가중 영향도</option>
    <option value="btw">색상: 매개중심성</option>
    <option value="cut">색상: 단절 유발 여부</option>
   </select>
   <select id="area"><option value="">전체 권역</option></select>
   <input id="q" placeholder="역명 검색">
   <span class="hint">클릭 = 역 선택 · 휠 = 확대 · 드래그 = 이동</span>
  </div>
  <canvas id="cv"></canvas>
  <div id="legend"></div>
 </div>
 <div id="side">
  <h1>도시철도 지식그래프</h1>
  <p class="sub" id="stat"></p>
  <div id="detail"><p class="hint">지도에서 역을 클릭하면 그 역의 지식그래프 관계가 여기에 표시됩니다.</p></div>
 </div>
</div>
<script>
const D=__DATA__, CAT_L=__CAT_L__, CAT_D=__CAT_D__;
const dark=matchMedia('(prefers-color-scheme:dark)').matches;
const CAT=dark?CAT_D:CAT_L;
const N=D.nodes, L=D.links;
const cv=document.getElementById('cv'), ctx=cv.getContext('2d');
let W=0,H=0,scale=1,tx=0,ty=0,sel=-1,filterArea='',mode='area',query='';

const KX=0.793;  // 위도 37.5°에서 경도 1°는 위도 1°의 약 0.79배 → 지리 종횡비 보정
const lats=N.map(n=>n[1]).filter(v=>v), lons=N.map(n=>n[2]*KX).filter(v=>v);
const bb={x0:Math.min(...lons),x1:Math.max(...lons),y0:Math.min(...lats),y1:Math.max(...lats)};
const maxImp=Math.max(...N.map(n=>n[8])), maxBtw=Math.max(...N.map(n=>n[7]));

function resize(){const r=document.getElementById('main').getBoundingClientRect();
 const d=devicePixelRatio||1; W=r.width;H=r.height; cv.width=W*d;cv.height=H*d;
 cv.style.width=W+'px';cv.style.height=H+'px';ctx.setTransform(d,0,0,d,0,0);draw();}
function fit(){const pad=64,sx=(W-pad*2)/(bb.x1-bb.x0),sy=(H-pad*2)/(bb.y1-bb.y0);
 scale=Math.min(sx,sy);
 tx=(W-(bb.x1-bb.x0)*scale)/2-bb.x0*scale;              // 가로 중앙 정렬
 ty=(H+(bb.y1-bb.y0)*scale)/2+bb.y0*scale;}             // 세로 중앙 정렬
const PX=n=>n[2]*KX*scale+tx, PY=n=>ty-n[1]*scale;

function ramp(t){ // 단일 색상 순차 스케일(light→dark), 배경에 맞춰 방향 전환
 t=Math.max(0,Math.min(1,t));
 const a=dark?[26,26,25]:[236,240,247], b=dark?[120,180,255]:[16,60,120];
 return `rgb(${a.map((v,i)=>Math.round(v+(b[i]-v)*(0.15+0.85*t))).join(',')})`;}
function colorOf(n){
 if(mode==='area') return CAT[(n[6]>=0?n[6]:0)%CAT.length];
 if(mode==='impact') return ramp(n[8]/maxImp);
 if(mode==='btw') return ramp(n[7]/maxBtw);
 return n[9]?(dark?'#d95926':'#eb6834'):(dark?'#4a4a45':'#c9c8c1');}
const visible=i=>(!filterArea||D.areas[N[i][6]]===filterArea);

function draw(){
 ctx.clearRect(0,0,W,H);
 ctx.lineWidth=Math.max(.5,Math.min(2.2,scale/60));
 for(const [a,b,t] of L){ if(!visible(a)&&!visible(b))continue;
  ctx.strokeStyle=t?(dark?'#55554c':'#c9c8c1'):(dark?'#3d3d37':'#d9d8d1');
  ctx.beginPath();ctx.moveTo(PX(N[a]),PY(N[a]));ctx.lineTo(PX(N[b]),PY(N[b]));ctx.stroke();}
 const r=Math.max(2.1,Math.min(7,scale/110));
 for(let i=0;i<N.length;i++){ if(!visible(i))continue; const n=N[i];
  const hit=query&&n[0].includes(query);
  ctx.beginPath();ctx.arc(PX(n),PY(n),hit?r*2.1:r,0,7);
  ctx.fillStyle=colorOf(n);ctx.fill();
  if(hit){ctx.strokeStyle=dark?'#fff':'#0b0b0b';ctx.lineWidth=1.5;ctx.stroke();}}
 if(sel>=0){const n=N[sel];ctx.beginPath();ctx.arc(PX(n),PY(n),r*2.6,0,7);
  ctx.strokeStyle=dark?'#fff':'#0b0b0b';ctx.lineWidth=2.2;ctx.stroke();
  ctx.font='600 12px sans-serif';ctx.fillStyle=dark?'#fff':'#0b0b0b';
  ctx.textAlign='center';ctx.fillText(n[0],PX(n),PY(n)-r*2.6-6);}
 legend();}

function legend(){const el=document.getElementById('legend');
 if(mode==='area'){el.innerHTML=D.areas.map((a,i)=>
   `<span class="pill"><i class="dot" style="background:${CAT[i%CAT.length]}"></i>${a}</span>`).join('');}
 else if(mode==='cut'){el.innerHTML=
   `<span class="pill"><i class="dot" style="background:${dark?'#d95926':'#eb6834'}"></i>단절 유발 역사</span>`+
   `<span class="pill"><i class="dot" style="background:${dark?'#4a4a45':'#c9c8c1'}"></i>그 외</span>`;}
 else{const t=mode==='impact'?'승객가중 효율 저하율':'매개중심성';
  const mx=mode==='impact'?maxImp.toFixed(2)+'%':maxBtw.toFixed(3);
  el.innerHTML=`<div style="font-size:12px;color:var(--ink2);margin-bottom:5px">${t}</div>`+
   `<div style="display:flex;align-items:center;gap:7px;font-size:11.5px;color:var(--ink3)">0`+
   [...Array(9)].map((_,i)=>`<i style="width:17px;height:11px;border-radius:2px;background:${ramp(i/8)}"></i>`).join('')+
   `${mx}</div>`;}}

function pick(mx,my){let best=-1,bd=15*15;
 for(let i=0;i<N.length;i++){if(!visible(i))continue;
  const dx=PX(N[i])-mx,dy=PY(N[i])-my,d=dx*dx+dy*dy; if(d<bd){bd=d;best=i;}}
 return best;}

function detail(i){const el=document.getElementById('detail');
 if(i<0){el.innerHTML='<p class="hint">지도에서 역을 클릭하면 그 역의 지식그래프 관계가 여기에 표시됩니다.</p>';return;}
 const n=N[i], conn=[],tr=[];
 for(const [a,b,t,dist,sec,fq] of L){ let o=a===i?b:(b===i?a:-1); if(o<0)continue;
  (t?tr:conn).push([N[o][0],dist,sec,fq]);}
 const tri=(p,v)=>`<div class="tri"><span class="pred">${p}</span><b>${v}</b></div>`;
 el.innerHTML=`<h1>${n[0]}${n[9]?'<span class="badge">단절 유발</span>':''}</h1>
  <p class="sub">${D.lines[n[3]]||''} · ${n[4]}</p>
  <h2>속성</h2>
  <div class="kv"><span>매개중심성</span><span>${n[7].toFixed(4)}</span></div>
  <div class="kv"><span>승객가중 효율 저하율</span><span>${n[8].toFixed(2)}%</span></div>
  <div class="kv"><span>환승역 구분</span><span>${n[10]||'—'}</span></div>
  <div class="kv"><span>좌표</span><span>${n[1].toFixed(4)}, ${n[2].toFixed(4)}</span></div>
  <h2>지식그래프 관계</h2>
  ${tri('ON_LINE',D.lines[n[3]]||'—')}
  ${tri('OPERATED_BY',n[4]||'—')}
  ${tri('LOCATED_IN',n[5]||'—')}
  ${tri('IN_METRO_AREA',D.areas[n[6]]||'—')}
  ${conn.map(c=>`<div class="tri"><span class="pred">CONNECTS_TO</span><b>${c[0]}</b>`+
    `<div style="padding-left:2px;font-size:11.5px;color:var(--ink3)">`+
    `${c[1]?Math.round(c[1])+' m':'거리 —'} · ${c[2]?Math.round(c[2])+' s':'소요 —'} · `+
    `${c[3]?Math.round(c[3])+'회/평일':'빈도 —'}</div></div>`).join('')}
  ${tr.map(c=>tri('TRANSFERS_TO',c[0])).join('')}`;}

document.getElementById('stat').textContent =
 `노드 ${Object.values(D.counts).reduce((a,b)=>a+b,0).toLocaleString()} · `+
 `관계 ${Object.values(D.rel).reduce((a,b)=>a+b,0).toLocaleString()} `+
 `(역 ${D.counts.Station} · 노선 ${D.counts.Line} · 기관 ${D.counts.Operator} · `+
 `시도 ${D.counts.Region} · 권역 ${D.counts.MetroArea})`;
const as=document.getElementById('area');
D.areas.forEach(a=>{const o=document.createElement('option');o.value=o.textContent=a;as.appendChild(o);});
as.onchange=e=>{filterArea=e.target.value;draw();};
document.getElementById('color').onchange=e=>{mode=e.target.value;draw();};
document.getElementById('q').oninput=e=>{query=e.target.value.trim();
 if(query){const i=N.findIndex(n=>n[0].includes(query)); if(i>=0){sel=i;detail(i);}} draw();};

let drag=null;
cv.onmousedown=e=>drag={x:e.clientX,y:e.clientY,tx,ty,moved:false};
addEventListener('mousemove',e=>{if(!drag)return;
 const dx=e.clientX-drag.x,dy=e.clientY-drag.y;
 if(Math.abs(dx)+Math.abs(dy)>3)drag.moved=true;
 tx=drag.tx+dx;ty=drag.ty+dy;draw();});
addEventListener('mouseup',e=>{
 if(drag&&!drag.moved){const r=cv.getBoundingClientRect();
  sel=pick(e.clientX-r.left,e.clientY-r.top);detail(sel);draw();}
 drag=null;});
cv.onwheel=e=>{e.preventDefault();const r=cv.getBoundingClientRect();
 const mx=e.clientX-r.left,my=e.clientY-r.top,k=Math.exp(-e.deltaY*0.0016);
 tx=mx-(mx-tx)*k; ty=my-(my-ty)*k; scale*=k; draw();};
addEventListener('resize',resize);
resize();fit();draw();
</script></body></html>
"""

if __name__ == "__main__":
    build()
