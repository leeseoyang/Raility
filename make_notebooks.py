# -*- coding: utf-8 -*-
"""
notebooks/*.ipynb 생성

노트북은 파이프라인 모듈(build_graph / analyze / build_kg / kg_scenarios /
visualize)의 함수를 그대로 호출한다. 코드를 복사해 넣지 않으므로 스크립트를
고치면 노트북 결과도 함께 바뀌며, 로직이 두 곳으로 갈라지지 않는다.
셀 단위로 중간 산출물(표·그림)을 눈으로 확인하는 용도.
"""
import json, os

NB = "notebooks/"
KERNEL = {"display_name": "Python 3 (raility)", "language": "python", "name": "python3"}


_CID = [0]


def _id():
    _CID[0] += 1
    return f"cell{_CID[0]:03d}"


def md(*lines):
    return {"cell_type": "markdown", "id": _id(), "metadata": {},
            "source": "\n".join(lines)}


def code(*lines):
    return {"cell_type": "code", "id": _id(), "execution_count": None,
            "metadata": {}, "outputs": [], "source": "\n".join(lines)}


def nb(cells):
    return {"cells": cells, "metadata": {"kernelspec": KERNEL,
            "language_info": {"name": "python", "version": "3.11"}},
            "nbformat": 4, "nbformat_minor": 5}


ROOT = code(
    "# 저장소 루트에서 실행되도록 경로 이동 (notebooks/ 안에서 열었을 때 대비)",
    "import os, sys",
    "if os.path.basename(os.getcwd()) == 'notebooks':",
    "    os.chdir('..')",
    "sys.path.insert(0, os.getcwd())",
    "print('작업 경로:', os.getcwd())",
)

N1 = nb([
    md("# 01 · 데이터 확인과 그래프 구축",
       "",
       "국가철도공단 표준데이터 3종을 읽어 **물리 네트워크 그래프**(역=노드, 운행·환승=엣지)를 만든다.",
       "",
       "> 실행 전 `data/raw/README.md` 안내대로 운행정보 원본(약 18MB)을 `data/raw/`에 넣어야 한다."),
    ROOT,
    md("## 원본 데이터 훑어보기",
       "",
       "역사정보에는 좌표·환승·운영기관이, 노선정보에는 `정거장구성`(역 순서)이,",
       "운행정보에는 열차별 정차 시각이 들어 있다."),
    code("import pandas as pd",
         "sta = pd.read_excel('data/raw/전체_도시철도역사정보_20260630.xlsx')",
         "lin = pd.read_excel('data/raw/전체_도시철도노선정보_20260630.xlsx')",
         "print('역사정보', sta.shape, '| 노선정보', lin.shape)",
         "sta.head(3)"),
    code("# 노선정보의 정거장구성 = 노선별 역 순서 → 인접(운행) 엣지의 근거",
         "print(lin.loc[0, '노선명'])",
         "print(str(lin.loc[0, '정거장구성'])[:180])"),
    md("## 원본 품질 이슈 확인",
       "",
       "정제 로직이 왜 필요한지 직접 확인한다. 자세한 근거는 `docs/README_데이터.md` 참조."),
    code("# ① 역번호가 전역 고유값이 아님 — 도시 간 충돌",
         "dup = sta[sta['역번호'].astype(str).duplicated(keep=False)]",
         "print('중복 역번호 행수:', len(dup))",
         "dup.sort_values('역번호')[['역번호','역사명','노선명']].head(6)"),
    code("# ② 동일 노선번호에 노선명이 2개인 사례",
         "g = sta.groupby('노선번호')['노선명'].nunique()",
         "for ln in g[g > 1].index:",
         "    print(ln, '→', sorted(sta[sta['노선번호'] == ln]['노선명'].unique()))"),
    md("## 그래프 구축 실행",
       "",
       "`build_graph.py`가 정제·매칭·가중치 결합을 모두 수행한다."),
    code("import build_graph",
         "build_graph.main()"),
    code("import networkx as nx, json",
         "G = nx.read_graphml('data/processed/network.graphml')",
         "print(json.dumps(json.load(open('data/processed/_build_stats.json')),",
         "                 ensure_ascii=False, indent=2))"),
    code("# 연결요소 = 물리적으로 분리된 도시권",
         "for c in sorted(nx.connected_components(G), key=len, reverse=True)[:6]:",
         "    ops = pd.Series([G.nodes[n]['운영기관'] for n in c]).value_counts()",
         "    print(f'{len(c):4d}개 역  주요기관: {ops.index[0]}')"),
])

N2 = nb([
    md("# 02 · 취약성 분석",
       "",
       "1. 중심성 (연결·매개·근접·고유벡터)",
       "2. **역(노드)** 전수 제거 → 핵심 역사",
       "3. **구간(엣지)** 전수 제거 → 취약 구간",
       "4. 표적 공격 vs 무작위 제거 → 복원력 곡선",
       "5. 환승역 표적 마비",
       "",
       "전수 스윕이 포함되어 전체 실행에 수 분이 걸린다."),
    ROOT,
    code("import analyze, networkx as nx, pandas as pd",
         "G = analyze.load_graph()",
         "metro = sorted(max(nx.connected_components(G), key=len))  # 최대 연결요소 = 수도권",
         "print('수도권', len(metro), '개 역')"),
    md("## 중심성"),
    code("cen = analyze.centralities(G, metro)",
         "cen.nlargest(10, '매개중심성')[['역사명','노선명','매개중심성','연결중심성']]"),
    md("## 역(노드) 제거 전수 스윕 → 핵심 역사",
       "",
       "791개 역을 하나씩 제거하며 효율·연결성 저하를 실측한다. **수 분 소요.**",
       "",
       "효율은 원 네트워크 크기로 정규화한다(제거된 역은 도달 불가로 0 기여).",
       "남은 노드로 재정규화하면 종단역 제거 시 효율이 '증가'하는 artifact가 생긴다."),
    code("imp, base = analyze.single_removal_sweep(G, metro)",
         "print('단절유발역:', int(imp['분리유발'].sum()), '/', len(imp))",
         "imp.head(10)[['역사명','노선명','효율저하율_%','승객가중효율저하율_%','분리유발']]"),
    md("## 구간(엣지) 제거 전수 스윕 → 취약 구간",
       "",
       "역이 아니라 **선로 구간**이 끊기는 상황(사고·공사)에 대응한다. 역시 수 분 소요."),
    code("eimp = analyze.edge_removal_sweep(G, metro)",
         "print('단절유발 구간:', int(eimp['단절유발'].sum()), '/', len(eimp))",
         "eimp.head(10)[['역A','역B','구간유형','효율저하율_%','승객가중효율저하율_%','단절유발']]"),
    code("# 구간 매개중심성 상위 — 통과 통행량이 몰리는 병목 구간",
         "eimp.nlargest(8, '구간매개중심성')[['역A','역B','구간유형','구간매개중심성']]"),
    md("## 복원력 곡선 (표적 공격 vs 무작위 제거)"),
    code("net = analyze.Net(G, metro)",
         "curves = {}",
         "for st, runs in [('random', 10), ('degree', 1), ('betweenness', 1), ('adaptive', 1)]:",
         "    curves[st] = analyze.removal_curve(G, metro, st, frac=0.25, step=4,",
         "                                       runs=runs, net=net)",
         "    d = curves[st]; a = d[d['제거비율'] >= 0.10].head(1)",
         "    print(f\"{st:12s} 10% 제거 → 효율 {a['효율비율'].iloc[0]*100:.1f}% \"",
         "          f\"/ LCC {a['LCC비율'].iloc[0]*100:.1f}%\")"),
    code("import matplotlib.pyplot as plt",
         "from matplotlib import font_manager",
         "for c in ['Malgun Gothic','AppleGothic','NanumGothic','Noto Sans CJK KR']:",
         "    if any(c in f.name for f in font_manager.fontManager.ttflist):",
         "        plt.rcParams['font.family'] = c; break",
         "plt.rcParams['axes.unicode_minus'] = False",
         "fig, ax = plt.subplots(figsize=(7, 4.2))",
         "for st, lab in [('random','무작위'), ('degree','연결중심성'),",
         "                ('betweenness','매개중심성'), ('adaptive','적응형')]:",
         "    d = curves[st]",
         "    ax.plot(d['제거비율']*100, d['효율비율']*100, lw=2, label=lab)",
         "ax.set_xlabel('제거된 역사 비율 (%)'); ax.set_ylabel('전역 효율 (%)')",
         "ax.legend(); ax.grid(alpha=.4); plt.show()"),
    md("## 전체 파이프라인 한 번에 실행",
       "",
       "위 단계 + 환승역 표적 마비 + 대전 사례까지 실행해 `results/`에 CSV로 저장한다."),
    code("analyze.main()"),
])

N3 = nb([
    md("# 03 · 지식그래프와 계층적 장애 시나리오",
       "",
       "물리 그래프를 **타입이 있는 이종 그래프**로 재구성한다.",
       "역이 어느 노선·기관·지역에 속하는지를 관계로 표현하면, 단일 그래프로는",
       "표현조차 불가능한 **상위 계층 동시 장애**를 시뮬레이션할 수 있다.",
       "",
       "스키마는 `docs/ONTOLOGY.md` 참조."),
    ROOT,
    code("import build_kg",
         "build_kg.main()"),
    code("import pandas as pd",
         "kgn = pd.read_csv('kg/kg_nodes.csv'); kge = pd.read_csv('kg/kg_edges.csv')",
         "print('엔티티 타입별'); print(kgn['type'].value_counts())",
         "print('\\n관계 타입별'); print(kge['predicate'].value_counts())"),
    md("## 지식그래프 질의 예시",
       "",
       "타입 관계를 필터링하는 것만으로 계층적 질문에 답할 수 있다."),
    code("lab = dict(zip(kgn['id'], kgn['label']))",
         "",
         "# Q1. 7호선에 속한 역은 몇 개인가",
         "line_id = kgn[(kgn['type']=='Line') & (kgn['label']=='7호선')]['id'].iloc[0]",
         "on = kge[(kge['predicate']=='ON_LINE') & (kge['target']==line_id)]",
         "print('7호선 역수:', len(on))"),
    code("# Q2. 운영기관별 '단절 유발 환승역' 수",
         "st = kgn[kgn['type']=='Station'].set_index('id')",
         "op = kge[kge['predicate']=='OPERATED_BY'].set_index('source')['target']",
         "df = st.assign(기관=op.map(lab))",
         "vuln = df[(df['단절유발']==1) & df['환승역'].astype(str).str.contains('환승')]",
         "vuln['기관'].value_counts().head(8)"),
    code("# Q3. 시도별 평균 승객가중 영향도",
         "reg = kge[kge['predicate']=='LOCATED_IN'].set_index('source')['target']",
         "df2 = st.assign(시도=reg.map(lab))",
         "df2.groupby('시도')['승객가중효율저하율'].agg(['count','mean']).round(3).sort_values('mean', ascending=False)"),
    md("## 계층적 장애 시나리오",
       "",
       "노선 단위 / 운영기관 단위 / 광역시도 단위 동시 중단을 시뮬레이션한다."),
    code("import kg_scenarios",
         "out = kg_scenarios.run_scenarios()"),
    code("out['노선'].head(10)"),
])

N4 = nb([
    md("# 04 · 논문용 그림 생성",
       "",
       "`figures/`에 300dpi PNG 5종을 저장하고 노트북에도 인라인으로 표시한다."),
    ROOT,
    code("import visualize",
         "import os; os.makedirs('figures', exist_ok=True)",
         "G = visualize.load()",
         "visualize.fig_network(G)",
         "visualize.fig_resilience()",
         "visualize.fig_top_stations()",
         "visualize.fig_daejeon(G)",
         "visualize.fig_kg_scenarios()"),
    code("from IPython.display import Image, display",
         "for f in ['fig1_network','fig2_resilience','fig3_top_stations',",
         "          'fig4_daejeon','fig5_kg_scenarios']:",
         "    display(Image(f'figures/{f}.png', width=780))"),
    md("## 인터랙티브 지식그래프 탐색기",
       "",
       "생성 후 `kg_explorer.html`을 브라우저로 열면 역 클릭으로 KG 관계를 확인할 수 있다."),
    code("import make_explorer",
         "make_explorer.build()"),
])


def main():
    os.makedirs(NB, exist_ok=True)
    files = {"01_데이터_그래프구축.ipynb": N1, "02_취약성분석.ipynb": N2,
             "03_지식그래프.ipynb": N3, "04_시각화.ipynb": N4}
    for name, doc in files.items():
        with open(NB + name, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        print("생성:", NB + name)


if __name__ == "__main__":
    main()
