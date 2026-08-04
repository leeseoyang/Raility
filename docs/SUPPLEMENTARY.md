# 보충자료 (Supplementary Materials)

**국가철도공단 공공데이터를 활용한 도시철도 네트워크 취약성 분석**
Vulnerability Analysis of Urban Rail Transit Networks Using Public Data from the Korea National Railway

한국ITS학회논문지 투고규정 8조가 원고 분량을 그림·표 포함 6쪽으로 제한하므로, 본문에 싣지 못한 결과를 여기에 공개한다. 본문은 규정 18조 4항(웹페이지 인용)에 따라 이 문서를 URL로 참조한다.

모든 수치는 저장소의 스크립트로 재생성 가능하다. 재현 절차는 [README](../README.md) 참조.

그림 원본(300 dpi, 인쇄용)은 별도 저장소 <https://github.com/leeseoyang/Railityfig> 에 있다.
본문 그림 4종(Fig. 1~4)과 보충자료 그림 3종(Fig. S1~S3)이 함께 보관된다.

---

## S1. 취약 구간과 병목 — 수도권

![FigS1](https://raw.githubusercontent.com/leeseoyang/Railityfig/main/FigS1_segments_en.png)

**\<Fig. S1\>** Segments whose failure disconnects the Seoul metropolitan network (left) and bottlenecks that carry heavy flow without causing disconnection (right)

수도권 1,016개 구간 중 208개(20.5%)가 단절을 유발한다. 왼쪽은 그중 수요가중 효율 저하가 큰 12개, 오른쪽은 단절을 일으키지 않으면서 구간 매개중심성이 높은 12개다.

두 목록은 겹치지 않는다. 왼쪽은 5호선 강동 분기부와 경원선 북부, 우이신설선처럼 **끊기면 그 너머가 고립되는** 단일 축이고, 오른쪽은 신도림–구로, 영등포–신길처럼 **끊겨도 우회는 되지만 통행이 몰리는** 경부·경인선 분기부다. 전자는 우회 노선 신설, 후자는 증차·용량 확충이 대응책이다.

원자료: [`results/edge_vulnerability_by_region.csv`](../results/edge_vulnerability_by_region.csv), [`results/edge_removal_impact_metro.csv`](../results/edge_removal_impact_metro.csv)

### \<Table S1\> Top disconnecting segments by region

| Region | Segment | Demand-weighted loss (%) | Stations isolated |
|---|---|---|---|
| Seoul Metropolitan Area | Gangdong – Gildong (Line 5) | 1.25 | 10 |
| Seoul Metropolitan Area | Dobongsan – Mangwolsa (Gyeongwon) | 1.19 | 31 |
| Busan–Gimhae | Beomnaegol – Beomil (Line 1) | 14.92 | 23 |
| Daegu | Jungangno – Banwoldang (Line 1) | 26.29 | 27 |
| Daejeon | Government Complex – City Hall (Line 1) | 28.48 | 11 |
| Gwangju | Geumnamno 4-ga – Geumnamno 5-ga (Line 1) | 27.85 | 6 |

---

## S2. 환승 비용 가정 민감도

![FigS2](https://raw.githubusercontent.com/leeseoyang/Railityfig/main/FigS2_sensitivity_en.png)

**\<Fig. S2\>** Sensitivity of the results to the transfer-cost assumption

환승 1회를 200 m 상당의 거리 비용으로 환산한 것은 임의 가정이므로, 50 m에서 1,600 m까지 32배 범위를 훑어 결론의 안정성을 확인했다.

매개중심성 순위상관은 0.939 이상, 우선 보강 대상의 영향도 순위상관은 0.893 이상을 유지한다. **순위 기반 결론은 가정에 강건하다.** 다만 상위 20개 역의 *집합* 자체는 자카드 0.739까지 내려가므로, 본문은 개별 역을 단정적으로 지목하지 않고 순위 구조와 사분면 분류로 진술한다.

### \<Table S2\> Transfer-cost sensitivity

| Transfer cost (m) | Betweenness rank ρ | Top-20 Jaccard | Priority-target impact ρ |
|---|---|---|---|
| 50 | 0.963 | 0.905 | 0.893 |
| 100 | 0.974 | 0.905 | 0.929 |
| **200 (baseline)** | — | — | — |
| 400 | 0.982 | 0.739 | 1.000 |
| 800 | 0.951 | 0.739 | 1.000 |
| 1,600 | 0.939 | 0.739 | 1.000 |

원자료: [`results/sensitivity_transfer_cost.csv`](../results/sensitivity_transfer_cost.csv)

---

## S3. 노선·운영기관 단위 동시 장애 시나리오

![FigS3](https://raw.githubusercontent.com/leeseoyang/Railityfig/main/FigS3_scenarios_en.png)

**\<Fig. S3\>** Simultaneous shutdown scenarios at line and operator level. Labels show impact per removed station.

지식그래프의 타입 관계(`ON_LINE`, `OPERATED_BY`, `LOCATED_IN`)를 질의해 노선·운영기관·광역시도 단위로 역사를 한꺼번에 제거한 결과다. 제거 규모가 크면 저하율도 당연히 커지므로, 비교에는 **역당 파급력**(효율 저하 ÷ 제거 역수)을 함께 본다.

서울교통공사는 276개 역, 수도권의 3분의 1을 동시에 지워도 역당 파급력이 0.25에 그친다. 대구 3호선은 30개 역만으로 1.78이다. 7배 차이이며, 규모가 아니라 순환밀도가 결과를 만든다는 본문 주장의 직접 증거다.

### \<Table S3\> Line- and operator-level shutdown scenarios

| Unit | Target | Stations removed | Share of region (%) | Efficiency loss (%) | LCC (%) | Impact per station |
|---|---|---|---|---|---|---|
| Line | Daegu Line 3 | 30 | 31.9 | 53.3 | 68.1 | **1.78** |
| Line | Daegu Line 1 | 35 | 37.2 | 52.5 | 62.8 | 1.50 |
| Line | Busan Line 2 | 43 | 31.9 | 48.5 | 68.1 | 1.13 |
| Line | Busan Line 1 | 40 | 29.6 | 46.6 | 70.4 | 1.17 |
| Operator | Busan Transportation Corp. | 114 | 84.4 | 94.8 | 15.6 | 0.83 |
| Operator | Seoul Metro | 276 | 33.5 | 70.1 | 63.1 | **0.25** |

원자료: [`results/kg_scenario_line.csv`](../results/kg_scenario_line.csv), [`results/kg_scenario_operator.csv`](../results/kg_scenario_operator.csv), [`results/kg_scenario_region.csv`](../results/kg_scenario_region.csv)

---

## S4. 지식그래프

본문에서는 지면상 다루지 않았으나, 위 계층적 시나리오는 별도로 구축한 지식그래프에서 질의해 산출했다.

`Station`(1,094) · `Line`(46) · `Operator`(20) · `Region`(12) · `MetroArea`(5) 5종 엔티티와 `CONNECTS_TO` · `TRANSFERS_TO` · `ON_LINE` · `OPERATED_BY` · `LOCATED_IN` · `IN_METRO_AREA` · `LINE_OPERATED_BY` 7종 관계로 구성된다. 중심성과 제거 영향도가 역 속성으로 병합되어 있어 그래프 자체가 진단 결과를 담는다.

- 온톨로지·질의 예시: [`docs/ONTOLOGY.md`](ONTOLOGY.md)
- 산출물: [`kg/`](../kg) — CSV, GraphML, RDF Turtle, Neo4j Cypher
- 설치 없이 보기: [`kg_explorer.html`](../kg_explorer.html) (단일 HTML, 브라우저로 열면 역 클릭 → 관계·취약성 확인)

---

## S5. 자료 품질 검증 상세

본문 Ⅲ장 3절에서 요약한 검증 절차의 전체 결과다.

| 검증 항목 | 값 |
|---|---|
| 공단 공식 역간거리 연속쌍 (정답지) | 1,048 |
| 그래프 미반영 | 0 (**재현율 100%**) |
| 실측 역간거리 커버리지 | 90.3% |
| 노선 내 인접 부분그래프가 2개 초과로 분리된 노선 | 0 |
| 실측으로 뒷받침되지 않는 4 km 초과 엣지 | 1 (고촌–김포공항, 김포골드라인 실제 장대 구간) |
| 좌표 결측 | 0 |
| 고립 노드 | 0 |
| 수요 노드 매칭률 | 98.4% (1,076 / 1,094) |

검증은 `build_graph.py` 실행 시마다 자동 수행되며 결과는 [`data/processed/_validation.csv`](../data/processed/_validation.csv)와 [`data/processed/_build_stats.json`](../data/processed/_build_stats.json)에 기록된다.

수요 미매칭 18개 노드는 인천공항 자기부상철도(6, 운행 중단), 구리 8호선(3, 자료 기간 이후 개통), 용인 에버라인 일부(2), 개칭·표기 차이(7)다.

---

## 재현

```bash
pip install -r requirements.txt
python build_graph.py            # 그래프 구축 + 자동 검증
python build_ridership.py        # 수요 결합
python analyze.py                # 중심성·제거 실험·복원력
python edge_vulnerability_all.py # 권역별 구간 취약성 (Fig. 1, S1)
python demand_sources.py         # 수요 지표 3원 교차검증 (Fig. 3)
python sensitivity.py            # 환승 비용 민감도 (S2)
python build_kg.py && python kg_scenarios.py   # 지식그래프·시나리오 (S3)
python make_figs_en.py           # 본문 그림
python make_fig1_map.py          # 본문 Fig. 1
python make_figs_supp.py         # 보충자료 그림
```
