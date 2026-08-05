# Raility — 도시철도 네트워크 취약성 분석

> 한국ITS학회논문지 투고 · 공공데이터 활용 공모전 (마감 2026-08-31)
> 이 페이지는 팀 공동작업 허브입니다. 코드·데이터 원본은 GitHub, 원고 편집은 이 페이지에서 진행합니다.

## 링크

| 항목 | 주소 | 내용 |
|---|---|---|
| 메인 저장소 | https://github.com/leeseoyang/Raility | 코드·데이터·결과 전체 (231개 파일) |
| 그림 저장소 | https://github.com/leeseoyang/Railityfig | 300 dpi 인쇄용 그림 원본 7종 |
| 보충자료 | https://github.com/leeseoyang/Raility/blob/main/docs/SUPPLEMENTARY.md | 본문 6쪽 제한으로 뺀 결과 S1~S5 |
| 논문 초안 (MD) | https://github.com/leeseoyang/Raility/blob/main/docs/논문_원고.md | 아래 전문과 동일 |
| 지식그래프 뷰어 | https://github.com/leeseoyang/Raility/blob/main/kg_explorer.html | 설치 없이 브라우저로 열람 |
| 투고규정 점검 | https://github.com/leeseoyang/Raility/blob/main/docs/투고규정_점검.md | 규정 대조표·감축 계획 |

## 재현 절차

```bash
git clone https://github.com/leeseoyang/Raility.git
cd Raility && pip install -r requirements.txt
python build_graph.py             # 그래프 구축 + 자동 검증
python build_ridership.py         # 수요 결합
python analyze.py                 # 중심성·제거 실험·복원력
python edge_vulnerability_all.py  # 권역별 구간 취약성 (Fig. 1, S1)
python demand_sources.py          # 수요 지표 3원 교차검증 (Fig. 3)
python sensitivity.py             # 환승 비용 민감도 (S2)
python build_kg.py && python kg_scenarios.py   # 지식그래프·시나리오 (S3)
python make_figs_en.py && python make_fig1_map.py && python make_figs_supp.py
```

---

# 1. 데이터셋

## 1-1. 원본 자료 — 국가철도공단 (공공데이터포털)

| 자료 | 규모 | 저장소 경로 | 용도 |
|---|---|---|---|
| 전국도시철도역사정보 | 1,099건 | `data/raw/전체_도시철도역사정보_20260630.xlsx` | 노드 정의·좌표 |
| 전국도시철도노선정보 | 47건 | `data/raw/전체_도시철도노선정보_20260630.xlsx` | 노선별 정거장 구성 |
| 전국도시철도운행정보 | 223,425건 | 용량 제외 (data.go.kr 15013206) | 인접 구간 보완·운행빈도 |
| 역간거리 | 32종 | `data/raw/역간거리/` | 엣지 가중치 (실측 90.3%) |
| 환승정보 | 15종 | `data/raw/환승정보/` | 환승 엣지 |

## 1-2. 수요 자료 — 외부 보완

공단은 시설 관리 기관이라 수요를 개방하지 않습니다. 서로 독립인 3종을 교차검증에 사용했습니다.

| 지표 | 출처 | 성격 | 저장소 경로 |
|---|---|---|---|
| ① 운행빈도 | 공단 운행정보 | 공급 (역별 정차 횟수) | 파생값, `results/demand_source_scatter.csv` |
| ② 역별 승하차 | KRIC 철도통계 19개 운영기관 | 기관 보고 | `data/raw/승하차/` (19 files) |
| ③ 교통카드 승하차 | 서울시·한국스마트카드 역간 OD | 단말 계측 | `OD+data/data/od/` |

지방 OD 보조자료(부산·대구·대전·광주·인천 시간대별 승하차)도 `OD+data/data/od/`에 포함되어 있습니다.

## 1-3. 가공 산출물

| 파일 | 크기 | 내용 |
|---|---|---|
| `data/processed/network.graphml` | 585 KB | 최종 그래프 (노드 1,094 · 엣지 1,344) |
| `data/processed/nodes.csv` | 180 KB | 노드 속성 (좌표·노선·운영기관·권역) |
| `data/processed/edges_all.csv` | 39 KB | 엣지 전체 (운행 1,160 + 환승 184) |
| `data/processed/node_demand.csv` | 123 KB | 노드별 결합 수요 (매칭률 98.4%) |
| `data/processed/_validation.csv` | — | 빌드마다 자동 기록되는 검증 결과 |
| `results/` | 24개 | 중심성·제거영향·복원력·민감도·시나리오 |
| `kg/` | 6개 | 지식그래프 (CSV · GraphML · RDF Turtle · Cypher) |
| `data/raw/basemap_municipalities.geojson` | 1.0 MB | Fig. 1 배경 시군구 경계 (통계청 2018) |

## 1-4. 자료 품질 검증 (build_graph.py 실행 시 자동)

| 검증 항목 | 값 |
|---|---|
| 공단 공식 역간거리 연속쌍 (정답지) | 1,048 |
| 그래프 미반영 | 0 (**재현율 100%**) |
| 실측 역간거리 커버리지 | 90.3% |
| 노선 내 인접 부분그래프가 분리된 노선 | 0 |
| 실측 미뒷받침 4 km 초과 엣지 | 1 (고촌–김포공항, 실제 장대 구간) |
| 좌표 결측 / 고립 노드 | 0 / 0 |
| 수요 노드 매칭률 | 98.4% (1,076 / 1,094) |

---

# 2. 핵심 결과 요약

| 발견 | 근거 수치 | 근거 파일 |
|---|---|---|
| ① 취약성은 규모가 아니라 위상적 여유가 결정 | 순환밀도 수도권 0.284 → 대전·광주 0.000 / 최악 단일 구간 손실 1.2% vs 28.5% (23배) | `results/topology_summary.csv`, `results/edge_vulnerability_by_region.csv` |
| ② 정적 표적은 위험을 과소평가 | 10% 제거 시 잔존 효율 — 적응형 24.9% < 연결 41.5% < 무작위 57.7% < 정적 매개 61.1% | `results/resilience_*.csv` |
| ③ 운행빈도 프록시는 실수요를 대변 못 함 | 기관통계↔카드 ρ=0.838, 프록시는 양쪽 모두 ρ≈0.38 / 상위 5위 겹침 0곳 | `results/demand_source_agreement.csv`, `results/criticality_metro.csv` |
| 정책 산출 | 우선 보강 대상 7개 역, 단절 유발 구간 208개 | `results/priority_stations.csv` |

---

# 3. 남은 작업

| 항목 | 근거 규정 | 담당 |
|---|---|---|
| 저자 전원 한국ITS학회 회원 가입 확인 | 규정 1 | |
| 영문 Abstract 원어민 교정 의뢰 | 규정 13 | |
| Ⅱ장 "국내 단일도시 편중" 서술 — DBpia·RISS로 확정 | — | |
| hwp 제출형식에 붙여 6쪽 여부 확인 (초과 시 Ⅴ.6 각주화) | 규정 8 | |
| 추가게재료 확인 (KITS 사무국 02-3413-0042) | 규정 8 | |
| 제출 서류 4종 작성 (투고신청서·Checklist·게재권한위임서·원고) | — | |

---

# 4. 논문 초안 (전문)

## 국가철도공단 공공데이터를 활용한 도시철도 네트워크 취약성 분석

### Vulnerability Analysis of Urban Rail Transit Networks Using Public Data from the Korea National Railway

---

#### 국문요약

도시철도는 선로에 갇힌 평면 네트워크여서 특정 역사나 구간이 중단되면 우회 경로가 제한적이다. 본 연구는 국가철도공단 공공데이터로 전국 도시철도망을 노드 1,094개, 엣지 1,344개의 그래프로 구축하고 운영 중단의 영향을 정량화하였다. 공단이 공표한 역간거리 연속쌍 1,048개를 정답지로 삼아 재현율 100%를 검증하였으며, 공단이 개방하지 않는 수요 자료는 외부 통계로 보완하였다. 분석 결과 첫째, 순환밀도는 수도권 0.284에서 대전·광주 0.000까지 분포하고 순환이 없는 두 권역은 모든 구간이 다리에 해당하여, 위상적 여유가 취약성의 1차 결정 변수임을 확인하였다. 둘째, 정적 매개중심성 표적은 무작위 고장보다 오히려 덜 파괴적이었고(잔존 효율 61.1% 대 57.7%), 매 단계 재계산하는 적응형에서만 24.9%까지 하락하였다. 셋째, 서로 독립인 두 수요 측정은 ρ=0.838로 일치한 반면 널리 쓰이는 운행빈도 프록시는 어느 쪽과도 ρ≈0.38에 그쳐, 어긋나는 것은 수요 측정이 아니라 프록시임을 확인하였다. 이를 토대로 우선 보강 대상 7개 역과 단절 유발 구간 208개를 도출하였다.

**핵심어** : 도시철도 네트워크, 네트워크 취약성, 표적 공격, 수요가중 네트워크 분석, 순환밀도

#### Abstract

Urban rail transit is a planar network constrained by fixed tracks, so the suspension of a station or a segment leaves few alternative paths. This study builds a nationwide graph of Korean urban rail—1,094 nodes and 1,344 edges—from public data of the Korea National Railway (KNR), and quantifies how disruptions degrade network structure and passenger movement. Line-aware adjacency resolution was validated against 1,048 officially published consecutive station pairs, achieving 100% recall and 90.3% coverage of measured inter-station distances. Because KNR, as an infrastructure agency, does not publish demand data, ridership was supplemented from external statistics.

Three findings follow. First, topological redundancy is the primary determinant of vulnerability: cyclomatic density ranges from 0.284 in the Seoul metropolitan area to 0.000 in Daejeon and Gwangju, where the networks are topologically trees and every segment is a bridge. The worst single segment costs 1.2% of demand-weighted efficiency in the metropolitan area but 28.5% in Daejeon, a 23-fold gap.

Second, static betweenness-targeted attack proved less destructive than random failure (61.1% versus 57.7% residual efficiency at 10% node removal), because high-betweenness stations concentrate on a single trunk corridor so their removal effects overlap. Only adaptive targeting with per-step recomputation reduced efficiency substantially, to 24.9%.

Third, we triangulated demand weighting with three independent sources. Agency ridership statistics and smart-card measurements agree at ρ=0.838, whereas the service-frequency proxy widely used in prior work correlates with neither (ρ≈0.38). The proxy's distortion is directional: it overrates peripheral cut vertices and underrates central transfer hubs, with no overlap among the top five stations under the two weightings.

**Keywords** : Urban rail transit network, Network vulnerability, Targeted attack, Demand-weighted network analysis, Cyclomatic density

---

### Ⅰ. 서론

도시철도는 대도시권 통행의 근간이지만, 도로망과 달리 물리적 선로에 통행이 갇혀 있다. 도로는 한 구간이 막혀도 격자 형태의 대체 경로가 남지만, 철도는 선로가 놓인 곳으로만 열차가 다닌다. 따라서 한 역사나 구간이 중단되면 승객이 선택할 수 있는 우회 경로가 구조적으로 제한되며, 그 영향은 중단 지점의 위상적 위치에 따라 크게 달라진다. 어느 역사와 구간이 네트워크 전체 성능을 좌우하는지를 사전에 파악하는 일은 시설 보강 투자와 비상 대응 계획의 출발점이 된다.

복잡계 네트워크 이론을 적용한 도시철도 취약성 연구는 2000년대 이후 상당한 축적을 이루었다. 그러나 국내 연구에는 두 가지 공백이 남아 있다. 첫째, 대부분의 연구가 단일 도시, 주로 서울을 대상으로 하여 권역 간 위상 구조의 차이가 취약성에 어떻게 반영되는지를 비교하지 못했다. 서울은 순환선과 다수의 방사축이 얽힌 조밀한 망이지만, 대전과 광주는 1개 노선만 운영된다. 같은 방법론으로 나란히 놓고 보지 않으면 "노선 하나뿐인 도시가 취약하다"는 직관을 정량적 근거로 바꿀 수 없다.

둘째, 기종점(OD) 자료를 확보하기 어려운 현실 때문에 운행빈도와 같은 공급 지표를 수요의 대리변수로 사용하는 관행이 굳어졌으나, 그 대리변수가 실제 수요를 얼마나 대변하는지는 검증된 바 없다. 이는 방법론의 세부 사항이 아니라 결론의 타당성을 좌우하는 문제다. 가중치가 틀리면 "어느 역을 먼저 보강할 것인가"라는 정책 결론 자체가 뒤집힌다.

본 연구는 이 두 공백을 겨냥한다. 국가철도공단 공공데이터를 이용해 전국 5개 권역의 도시철도망을 동일한 방법론으로 구축하고, 역사·구간 단위 전수 제거 실험과 순차 제거 시뮬레이션으로 취약성을 정량화한다. 나아가 서로 독립적으로 수집된 세 개의 수요 지표를 교차검증하여, 기존 연구가 사용해 온 공급 프록시의 타당성 자체를 평가한다.

이하의 구성은 다음과 같다. Ⅱ장에서 관련 연구를 검토하고, Ⅲ장에서 자료와 네트워크 구축 절차 및 품질 검증 방법을 기술한다. Ⅳ장에서 분석 방법을, Ⅴ장에서 결과를 제시하고, Ⅵ장에서 정책적 함의와 한계를 논한다.

### Ⅱ. 관련 연구

Latora and Marchiori(2001)는 네트워크 성능 지표로 전역 효율을 제안하여, 연결 여부라는 이분법 대신 노드 제거에 따른 성능 저하를 연속적으로 측정할 수 있게 하였다. 전역 효율은 모든 노드쌍 최단거리의 역수 평균으로 정의되므로, 망이 끊기지 않더라도 우회로 길어진 만큼의 손실을 포착한다. Albert et al.(2000)은 무작위 고장과 표적 공격에 대한 내성이 네트워크 위상에 따라 크게 달라짐을 보였고, 이후 이 대비는 교통망 취약성 연구의 표준 분석틀이 되었다. Derrible and Kennedy(2010)는 세계 지하철망을 비교하여 강건성을 독립 순환의 수로 설명하였으며, 이는 본 연구가 사용하는 순환밀도 개념의 이론적 근거가 된다.

수요를 결합한 취약성 평가로는 Rodríguez-Núñez and García-Palomares(2014)가 대표적이다. 이들은 마드리드 지하철에서 링크 단절의 영향을 통행 시간 증가로 환산하고 이를 미충족 수요와 교차하여 정책 우선순위를 도출하였다. 위상만으로는 "끊기면 큰일 나는 곳"과 "끊겨도 사람이 적은 곳"이 구분되지 않는다는 문제의식이다. Sun et al.(2017)은 상하이 지하철을 대상으로 정적·동적 표적 전략을 비교하여, 표적을 매 단계 갱신하면 피해가 크게 증폭됨을 보였다.

국내에서는 Kim and Lee(2022)가 건넘선과 환승역 등 지하철 고유의 시설 구조를 반영하고 시간대별 수요를 결합해 서울 지하철의 역사·구간 취약성을 평가하였다. 열차 운영 설비를 네트워크 모형에 반영한 점에서 진전이며, 본 연구가 다루지 못한 부분 운행 시나리오를 포괄한다.

본 연구는 세 가지 점에서 선행 연구와 구별된다. 첫째, 분석 범위가 단일 도시에 국한되지 않고 전국 5개 권역을 동일 방법론으로 비교한다. 둘째, 선행 연구가 수요 지표를 사용하는 데 그친 반면, 본 연구는 수요 지표 자체의 타당성을 서로 독립인 세 자료의 교차검증으로 평가한다. 셋째, 무작위·정적 표적·적응형 표적을 나누어 표적 전략에 따른 복원력 차이를 비교한다.

### Ⅲ. 자료 및 네트워크 구축

#### 1. 자료

네트워크 구축에는 국가철도공단이 공공데이터포털을 통해 개방한 자료 5종을 사용하였다. 전국도시철도역사정보(1,099건), 전국도시철도노선정보(47건), 전국도시철도운행정보(223,425건), 역간거리 32종, 환승정보 15종이다. 역사정보는 역별 좌표와 소재지를, 노선정보는 노선별 정거장 구성을, 운행정보는 열차별 정차 순서를 제공한다.

공단은 철도시설의 건설과 관리를 담당하는 기관이므로 승객 수요 자료를 개방하지 않는다. 이에 승객 이동 영향 산정에 필요한 수요는 외부 자료로 보완하였다. 철도산업정보센터(KRIC) 철도통계의 19개 운영기관 역별 승하차 실적과, 서울시·한국스마트카드가 공개한 교통카드 기반 역간 통행 자료를 사용하였다.

#### 2. 노드와 엣지 정의

노드는 역사로 정의하되, 환승역이 노선별로 분리 운영되는 실태를 반영하여 「노선번호|역번호」를 전역 고유키로 사용하였다. 그 결과 노드 1,094개 가운데 수도권 792개 노드는 물리적으로 703개 역에 해당한다. 이 구분은 환승 저항을 모형에 반영하기 위해 필요하다. 하나의 노드로 합치면 서울역에서 2호선으로 갈아타는 통행과 1호선을 그대로 타고 지나는 통행이 같은 비용을 갖게 된다.

엣지는 두 종류다. 운행 엣지 1,160개는 열차가 실제로 연속 정차하는 인접 구간이고, 환승 엣지 184개는 서로 다른 노선 간 도보 환승 연결이다. 환승 엣지는 동일 역명이면서 1.2 km 이내인 노드쌍, 그리고 역명이 다르더라도 350 m 이내인 노드쌍에 대해 생성하였다.

가중치는 공단 실측 역간거리를 우선 사용하였으며 커버리지는 90.3%다. 미확보 구간은 좌표 기반 직선거리로 대체하였고, 실측과 대조 시 실측/직선 비율의 중앙값은 1.03으로 대체값의 편의는 크지 않았다. 환승은 200 m 상당의 거리 비용으로 환산하였으며, 이 가정의 임의성은 Ⅴ장 6절에서 민감도로 검증한다.

#### 3. 자료 품질 처리와 검증

원본 자료에는 결과를 좌우할 수 있는 품질 문제가 존재하여 별도의 처리와 검증 절차를 설계하였다.

첫째, 역명을 노드에 연결할 때 노선을 먼저 확인해야 한다. 환승역은 여러 노선의 노드가 50 m 이내에 겹쳐 있으므로 좌표 근접만으로 후보를 고르면 사실상 무작위 선택이 된다. 예비 구축에서는 이 때문에 전체 엣지의 22.3%가 서로 다른 노선을 잘못 연결하였고, 2호선 인접 부분그래프가 18개 조각으로 갈라졌다. 본 연구는 노선번호, 노선명, 좌표 연속성의 순서로 해석하며, 직결운행 경계에서만 좌표를 사용한다.

둘째, 급행 열차의 건너뛰기 구간을 인접으로 오인하지 않아야 한다. 급행 운행정보를 그대로 인접으로 읽으면 실제로는 정차하지 않는 두 역이 직결된 것으로 처리된다. 두 역을 잇는 직선 위에 같은 노선의 제3의 역이 놓이면 인접 구간으로 채택하지 않는 기하 판정을 적용하였다.

셋째, 수요 결합에서도 노선 단위 매칭을 적용하였다. 역명만으로 집계하면 서울 시청과 부산 시청, 대구 중앙로와 대전 중앙로가 합산된다. 특히 광역철도 실적 자료는 (노선, 역) 단위의 발착·통과 원장이어서, 역명으로만 합치면 통과 열차 실적이 해당 역의 승하차로 잘못 계상된다. 운영기관과 노선을 키에 포함하고 통과 행을 제거하여 이를 차단하였으며, 노드 매칭률은 98.4%(1,076/1,094)다.

넷째, 검증을 자동화하였다. 공단이 공표한 역간거리 파일의 연속쌍 1,048개를 정답지로 삼아 최종 그래프의 재현율을 빌드마다 측정하며, 현재 재현율은 100%다. 아울러 각 노선의 인접 부분그래프가 하나의 연결요소를 이루는지, 실측으로 뒷받침되지 않는 4 km 초과 엣지가 존재하는지, 고립 노드가 있는지를 함께 점검한다. 검증 상세는 보충자료 S5(Raility, 2026)에 수록하였다.

### Ⅳ. 분석 방법

#### 1. 성능 지표

네트워크 성능은 Latora and Marchiori(2001)의 전역 효율 *E*로 측정한다. 승객 이동 영향은 노드 가중 효율 *E*<sub>d</sub> = Σ *d*<sub>i</sub>·*d*<sub>j</sub> / dist<sub>ij</sub> 로 산정하며, *d*는 역별 일평균 승하차 인원이다. 전자는 구조의 손실을, 후자는 그 손실이 실제로 몇 사람의 통행에 걸리는지를 나타낸다.

제거 분석에서 효율은 원 네트워크 크기로 정규화한다. 남은 노드만으로 재정규화하면 종단부 역사를 제거할 때 평균 거리가 짧아져 효율이 오히려 증가하는 인위적 결과가 발생하기 때문이다. 이 규약에서 제거된 역사는 도달 불가로 0을 기여한다.

#### 2. 제거 실험

수도권 792개 노드와 1,016개 구간을 하나씩 제거하며 전역 효율, 수요가중 효율, 최대연결요소 크기의 변화를 실측하였다. 나머지 4개 권역에 대해서도 동일한 구간 단위 전수 제거를 수행하여 권역 간 비교가 가능하도록 하였다.

순차 제거는 네 전략으로 수행하였다. 무작위 고장(고정 시드 10회 평균), 연결중심성 순, 매개중심성 순, 그리고 매 단계 중심성을 재계산하는 적응형이다. 앞의 셋은 초기 네트워크에서 산출한 순위를 고정해 사용하고, 적응형은 한 노드를 제거할 때마다 남은 망에서 중심성을 다시 계산한다.

#### 3. 수요 지표 교차검증

세 지표는 수집 주체와 방식이 서로 다르다. ①운행빈도는 공단 운행정보에서 역별 정차 횟수로 산출한 공급 지표, ②역별 승하차는 KRIC 철도통계의 운영기관 집계, ③교통카드 승하차는 서울시 역간 OD 자료에서 집계한 실측치다. ①은 공급, ②는 기관 보고, ③은 단말 계측으로 생성 경로가 겹치지 않는다. ②와 ③이 서로 일치하는지, ①이 두 지표와 어떤 관계인지를 스피어만 순위상관으로 비교한다.

지표를 둘만 비교하면 "두 값이 다르다"는 사실까지만 알 수 있고 어느 쪽이 실제 수요를 잘못 대변하는지는 판정할 수 없다. 독립인 세 번째 측정을 넣는 이유가 여기에 있다.

### Ⅴ. 결과

#### 1. 권역 간 위상 격차

**\<Table 1\> Topological indicators by region**

| Region | Nodes | Edges | Cycles | Cyclomatic density | Cut vertices (%) | Bridges (%) | Worst single segment (%) |
|---|---|---|---|---|---|---|---|
| Seoul Metropolitan Area | 792 | 1,016 | 225 | 0.284 | 26.3 | 20.5 | 1.2 |
| Busan–Gimhae | 158 | 178 | 21 | 0.133 | 53.2 | 47.2 | 14.9 |
| Daegu | 102 | 110 | 9 | 0.088 | 85.3 | 78.2 | 26.3 |
| Daejeon | 22 | 21 | 0 | 0.000 | 90.9 | 100.0 | 28.5 |
| Gwangju | 20 | 19 | 0 | 0.000 | 90.0 | 100.0 | 27.9 |

<sub>Worst single segment: demand-weighted efficiency loss when the most critical single segment of the region is severed.</sub>

순환밀도(독립 순환 수 ÷ 노드 수)는 수도권 0.284, 부산·김해 0.133, 대구 0.088, 대전과 광주 0.000으로 단조 감소하며, 다리 비율은 그 역순으로 20.5%에서 100%까지 증가한다(\<Table 1\>). 대전과 광주는 순환이 하나도 없어 위상적으로 완전한 트리이며, 따라서 모든 구간이 다리다. 어느 한 구간이 끊겨도 반드시 망이 두 조각으로 갈라진다.

이 위상 격차는 실제 성능 저하폭으로 그대로 이어진다. 각 권역의 모든 구간을 하나씩 끊어 수요가중 효율 저하를 측정한 결과, 최악의 단일 구간이 유발하는 손실은 수도권 1.2%, 부산·김해 14.9%, 대구 26.3%, 대전 28.5%, 광주 27.9%였다. 수도권에서 가장 취약한 구간이 끊겨도 손실이 1.2%인 반면, 대전에서는 단 한 구간이 28.5%를 앗아간다. 23배의 차이다. \<Fig. 1\>은 통계청 시군구 경계를 배경으로 다섯 권역을 동일한 색·굵기 척도로 그린 것으로, 수도권 전체가 옅은 선으로 남는 반면 대전과 광주는 전 구간이 짙은 굵은 띠로 나타난다.

해석에 한 가지 주의가 필요하다. 절점과 다리가 많다는 사실 자체는 발견이 아니라 희소한 위상의 산술적 귀결이다. 노선이 방사형으로만 뻗고 순환선이 없으면 다리 비율은 자동으로 100%가 된다. 의미 있는 비교 대상은 절대 수가 아니라 순환밀도 격차이며, 위 손실폭 비교가 그 격차의 실질적 귀결을 보여준다.

![Fig1](https://raw.githubusercontent.com/leeseoyang/Raility/main/figures/Fig1_vulnmap_en.png)

**\<Fig. 1\>** Segment vulnerability of five regional urban rail networks, drawn on a shared colour and line-width scale over municipal boundaries

#### 2. 표적 공격에 대한 복원력

**\<Table 2\> Residual network performance at 10% station removal**

| Removal strategy | Global efficiency (%) | Largest connected component (%) |
|---|---|---|
| Adaptive targeted (recomputed) | 24.9 | 16.3 |
| Degree-targeted | 41.5 | 74.6 |
| Random failure (mean of 10 runs) | 57.7 | 70.3 |
| Betweenness-targeted (static) | 61.1 | 81.7 |

역사의 10%를 제거했을 때 잔존 전역 효율은 적응형 표적 24.9%, 연결중심성 표적 41.5%, 무작위 고장 57.7%, 정적 매개중심성 표적 61.1%였다(\<Table 2\>, \<Fig. 2\>). 정적 매개중심성 표적이 무작위 고장보다 오히려 덜 파괴적이라는 결과는 통상의 예상과 어긋난다.

원인은 표적의 공간 분포에 있다. 매개중심성 상위 역사는 경부선과 2호선 간선 축 한 곳에 집중되어 있어, 앞쪽 몇 개를 제거하면 나머지 상위 역사는 이미 고립된 구간 안에 놓여 추가 피해를 주지 못한다. 반면 무작위 제거는 손상을 망 전체에 분산시켜 여러 지점에서 동시에 조각을 떼어낸다. 매 단계 중심성을 재계산하는 적응형은 이 중복을 회피하므로 최대연결요소를 16.3%까지 축소시킨다.

다만 정적 매개중심성이 무의미한 지표라는 뜻은 아니다. 개별 역사의 제거 영향도와 매개중심성의 순위상관은 ρ=0.613으로 네 중심성 가운데 가장 높다(연결 0.309, 근접 0.264, 고유벡터 0.228). 한 번에 한 곳이 멈추는 일상적 장애의 예측에는 매개중심성이 유효하며, 다수가 동시에 멈추는 시나리오에서만 중복 효과가 나타난다.

실무적 함의는 명확하다. 표적 위험을 정적 중심성 순위로 평가하면 위험을 과소평가한다. 연쇄적으로 표적이 갱신되는 시나리오를 함께 상정해야 한다.

![Fig2](https://raw.githubusercontent.com/leeseoyang/Raility/main/figures/Fig2_resilience_en.png)

**\<Fig. 2\>** Resilience curves under random failure and three targeted attack strategies

#### 3. 수요 지표의 타당성

**\<Table 3\> Agreement among three independent demand indicators**

| Comparison | Spearman ρ | Pearson r (log) | n |
|---|---|---|---|
| Agency statistics ↔ Smart-card measurement | 0.838 | 0.805 | 757 |
| Service-frequency proxy ↔ Agency statistics | 0.384 | 0.192 | 780 |
| Service-frequency proxy ↔ Smart-card measurement | 0.380 | 0.246 | 757 |

서로 독립적으로 수집된 두 수요 측정, 즉 기관 통계 승하차와 교통카드 실측 승하차는 스피어만 ρ=0.838(n=757)로 잘 일치하였다. 반면 선행 연구가 널리 사용해 온 운행빈도 프록시는 기관 통계와 ρ=0.384, 교통카드와 ρ=0.380으로 두 지표 어느 쪽과도 낮은 상관을 보였다(\<Table 3\>, \<Fig. 3\>). 세 번째 독립 측정이 더해지면서 수요 측정 자체는 견고하며 어긋나는 것은 프록시임이 확정된다.

왜곡의 크기보다 중요한 것은 방향이다. 같은 네트워크에서 가중치만 바꾸어 제거 영향도를 산출하면, 실수요 가중에서는 홍대입구(3.49%), 서울역(3.45%), 강남(3.06%)이 상위를 차지하는 반면 프록시 가중에서는 도봉산(3.68%), 망월사(3.51%), 회룡(3.44%)이 올라온다. 두 목록은 상위 5위 안에서 한 곳도 겹치지 않는다. 전자는 분리 규모가 0인 중추 환승역이고 후자는 분리 규모 29~31역의 외곽 절점이다. 즉 두 가중치는 순위가 흔들리는 정도가 아니라 서로 다른 종류의 위험을 가리킨다.

프록시가 외곽을 과대평가하는 이유는 구조적이다. 운행빈도는 그 역을 지나는 열차의 수를 세므로, 장거리 광역노선의 종단 구간처럼 열차는 자주 다니지만 타고 내리는 사람은 적은 역에서 값이 부풀려진다. 반대로 도심 환승역은 노선당 정차 횟수가 특별히 많지 않아 과소평가된다.

![Fig3](https://raw.githubusercontent.com/leeseoyang/Raility/main/figures/Fig3_demand_en.png)

**\<Fig. 3\>** Cross-validation of three independent demand indicators

#### 4. 핵심 역사와 우선 보강 대상

**\<Table 4\> Priority reinforcement targets**

| Station | Line | Daily boardings + alightings | Demand-weighted efficiency loss (%) | Stations disconnected |
|---|---|---|---|---|
| Gangdong | Line 5 | 35,683 | 1.63 | 10 |
| Suwon | Gyeongbu Line | 97,120 | 1.35 | 22 |
| Hoeryong | Gyeongwon Line | 34,496 | 1.15 | 29 |
| Nowon | Line 4 | 43,051 | 1.09 | 5 |
| Geomam | AREX | 46,755 | 0.70 | 12 |
| Sanggye | Line 4 | 36,737 | 0.57 | 4 |
| Uijeongbu | Gyeongwon Line | 38,088 | 0.57 | 13 |

절점은 수도권에만 208개로, 그 자체로는 정책 우선순위가 되지 못한다. 실수요 가중 영향도와 일평균 승하차가 모두 상위 25%이면서 절점인 역사로 좁히면 7개가 남는다(\<Table 4\>, \<Fig. 4\>). 강동, 수원역, 회룡역, 노원, 검암, 상계, 의정부역이다.

목록이 경원선 북부(회룡·의정부)와 4호선 북부(노원·상계)에 집중되는 점이 주목된다. 두 축은 모두 우회로가 없는 단일 선형이면서 수요가 큰 통근 축이라는 공통점을 갖는다. 강동은 5호선이 하남 방면과 마천 방면으로 분기하는 지점이고, 검암은 공항철도와 인천 2호선의 접속점이다. 수원역은 경부선 축의 중간 결절로 하루 9.7만 명이 이용하면서 22개 역의 연결을 책임진다. 이 유형은 운영적 대응만으로 해소되지 않으며 우회 경로 확보가 필요하다.

\<Fig. 4\>의 사분면 분류는 이 판단의 근거를 시각화한다. 가로축을 구조적 영향도, 세로축을 실수요로 놓으면 우상단이 우선 보강 대상, 좌상단은 수요는 많으나 대체 경로가 있는 역(증차·용량 대응), 우하단은 구조적으로 중요하나 수요가 적은 역(모니터링 대상)으로 갈린다.

![Fig4](https://raw.githubusercontent.com/leeseoyang/Raility/main/figures/Fig4_criticality_en.png)

**\<Fig. 4\>** Structural vulnerability versus actual demand, with priority reinforcement targets

#### 5. 구간 취약성과 규모 효과

수도권 1,016개 구간 중 208개(20.5%)가 단절을 유발하며, 수요가중 영향 상위는 강동–길동(1.25%, 10역 분리), 도봉산–망월사(1.19%, 31역), 망월사–회룡(1.10%, 30역)이다. 반면 단절은 없으나 통행이 집중되는 병목은 신도림–구로(구간 매개중심성 0.196), 구로–구일(0.177) 등 경부·경인선 분기부에 나타난다. 두 목록은 서로 겹치지 않는다. 단절 위험과 혼잡 위험이 서로 다른 구간에 분포하므로 보강 정책은 두 갈래로 설계되어야 한다. 전자는 우회 노선 신설, 후자는 증차와 용량 확충이 대응책이다. 구간별 상세 순위는 보충자료 S1에 수록하였다.

지방 권역에서는 단일 구간의 무게가 전혀 다르다. 대전은 정부청사–시청(28.5%, 11역 분리), 대구는 중앙로–반월당(26.3%, 27역 분리), 광주는 금남로4가–금남로5가(27.9%, 6역), 부산은 범내골–범일(14.9%, 23역)이 최상위다. 모두 도심 중심부의 단일 축에 위치하여, 대체 경로가 없는 상태에서 가장 많은 통행이 통과하는 지점이다.

노선·운영기관 단위 동시 장애 시나리오도 같은 방향을 가리킨다. 서울교통공사 276개 역, 수도권의 3분의 1을 동시에 제거해도 최대연결요소는 63.1%가 남고 역당 파급력(효율 저하율 ÷ 제거 역수)은 0.25에 그친다. 반면 대구 3호선은 30개 역만으로 1.78, 부산 3호선은 17개 역으로 2.03을 기록한다. 7~8배 차이이며, 규모가 아니라 순환밀도가 결과를 만든다는 점을 직접 확인시켜 준다. 이 시나리오는 별도로 구축한 지식그래프의 타입 관계를 질의해 산출하였으며, 상세 결과와 온톨로지는 보충자료 S3·S4에 수록하였다.

#### 6. 민감도

환승 1회를 200 m 상당으로 환산한 가정을 50 m에서 1,600 m까지 32배 범위로 훑었다. 매개중심성 순위상관은 0.939 이상, 우선 보강 대상의 영향도 순위상관은 0.893 이상을 유지하여 순위 기반 결론은 가정에 강건하였다. 다만 상위 20개 역의 집합 자체는 자카드 0.739까지 내려가 완전히 고정되지는 않는다. 이에 본 연구는 개별 역을 단정적으로 지목하기보다 순위 구조와 사분면 분류로 결과를 진술한다. 전체 민감도 결과는 보충자료 S2에 수록하였다.

### Ⅵ. 결론

본 연구는 국가철도공단 공공데이터로 전국 도시철도망을 구축하고 역사·구간의 운영 중단이 네트워크와 승객 이동에 미치는 영향을 정량화하였다. 주요 결과는 다음과 같다.

첫째, 권역 간 취약성 차이는 규모가 아니라 위상적 여유에서 비롯된다. 순환이 없는 대전과 광주는 모든 구간이 단절 지점이며, 단 하나의 구간이 끊겨도 권역 효율의 28%가 사라진다. 수도권에서 같은 지표의 최댓값이 1.2%인 것과 비교하면 23배다. 이들 권역에서는 개별 역사 보강보다 우회 경로 확보가 우선이며, 신규 노선 계획의 편익 산정에 위상적 여유의 개선분을 포함할 필요가 있다.

둘째, 표적 공격 위험은 정적 중심성 순위로 평가할 경우 과소평가된다. 상위 중심성 역사가 한 축에 몰려 있어 제거 효과가 중복되기 때문이다. 표적이 갱신되는 적응형 시나리오를 비상 대응 계획에 포함해야 한다.

셋째, 운행빈도 프록시는 실제 수요를 대변하지 못하며 그 왜곡에는 방향이 있다. 외곽의 단절형 절점을 과대평가하고 중추 환승역을 과소평가하므로, 프록시로 도출된 역 단위 보강 우선순위는 재검토가 필요하다. 수요 자료를 확보할 수 없는 경우라면 최소한 프록시 가중 결과를 구조적 영향도와 병기하여, 어느 유형의 위험을 보고 있는지 명시하는 것이 안전하다.

본 연구의 한계는 다음과 같다. 통행 배정에 기종점 자료가 아닌 최단경로 가정을 사용하였으므로 실제 경로 선택과 차이가 있을 수 있다. 운영 중단 시 버스 등 타 수단으로의 전환을 모형에 반영하지 않았으므로 효율 저하율은 통행 시간 증가의 상한에 가깝다. 또한 Kim and Lee(2022)가 반영한 건넘선 등 열차 운영 설비를 다루지 못하여, 회차 가능 여부에 따른 부분 운행 시나리오는 분석에서 제외되었다. 교통카드 실측 자료는 수도권만 포괄하므로 지방 권역의 수요 검증은 기관 통계에 의존한다. 실측 기종점 자료를 결합한 통행 배정과 시간대별 수요 변동의 반영을 후속 과제로 남긴다.

### References

Albert, R., Jeong, H. and Barabási, A. L.(2000), "Error and attack tolerance of complex networks", *Nature*, vol. 406, no. 6794, pp.378-382.

Derrible, S. and Kennedy, C.(2010), "The complexity and robustness of metro networks", *Physica A: Statistical Mechanics and its Applications*, vol. 389, no. 17, pp.3678-3691.

Kim, J. and Lee, G.(2022), "Measuring Network Vulnerability of Seoul Subway Network Considering the Structure of Subway Facilities (지하철 시설 구조를 고려한 서울시 지하철 네트워크의 취약성 평가)", *Journal of the Korean Geographical Society*, vol. 57, no. 4, pp.411-424.

Latora, V. and Marchiori, M.(2001), "Efficient behavior of small-world networks", *Physical Review Letters*, vol. 87, no. 19, 198701.

Raility(2026), Supplementary materials for vulnerability analysis of urban rail transit networks, https://github.com/leeseoyang/Raility/blob/main/docs/SUPPLEMENTARY.md, 2026.08.04.

Rodríguez-Núñez, E. and García-Palomares, J. C.(2014), "Measuring the vulnerability of public transport networks", *Journal of Transport Geography*, vol. 35, pp.50-63.

Statistics Korea(2018), Administrative boundary data (municipalities), https://github.com/southkorea/southkorea-maps, 2026.08.04.

Sun, D., Zhao, Y. and Lu, Q. C.(2017), "Vulnerability analysis of urban rail transit based on complex network theory: a case study of Shanghai Metro", *Public Transport*, vol. 9, no. 3, pp.501-525.

