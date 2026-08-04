# OD·승하차 데이터 배치 안내

서울시 실측 역간 OD(교통카드)와 지방 도시철도 승하차 데이터. `od_analysis.py`
(2026-07-22~28 7일치)와 `od_h1_analysis.py`(2026년 상반기 181일, 기간 정합판)가
이 폴더를 읽어 그래프 노드와 연결한 산출물을 `processed/` 에 만든다.
상세 조사·검증 내역은 `docs/OD_데이터_조사.md` 참조.

## 저장소에 포함된 파일

| 파일 | 내용 | 출처 |
|---|---|---|
| `seoul_역사마스터.csv` | 서울시 역사_ID(4자리) → 역사명·호선·좌표 (784역) | 공공데이터포털 15099382 (아래 zip 동봉분) |
| `busan_시간대별_승하차인원.csv` | 부산 1~4호선 역별·시간대별 승하차 (2026-01~06) | <https://www.data.go.kr/data/3057229/fileData.do> |
| `busan_월별역별권종별_승하차.csv` | 부산 월별·권종별 승하차 | <https://www.data.go.kr/data/15113504/fileData.do> |
| `daegu_역별일별시간별_승하차인원.csv` | 대구 1~3호선 역별·일별·시간대별 승하차 (2026-01~06) | <https://www.data.go.kr/data/15002503/fileData.do> |
| `daejeon_시간대별_승하차인원.csv` | 대전 1호선 역별·시간대별 승하차 (2026-01~06) | <https://www.data.go.kr/data/15060591/fileData.do> |
| `daejeon_역별_수송실적.csv` | 대전 1호선 역별 연간 수송실적 | <https://www.data.go.kr/data/15060556/fileData.do> |
| `incheon_1호선_일별승하차.csv` 외 2 | 인천 1·2호선, 인천 7호선 구간 일별 승하차 | 공공데이터포털 (인천교통공사) |
| `incheon_역별일별시간대별_이용인원_202501-202604.csv` | 인천 1·2호선(+7호선 구간) 역별·일별·시간대별 승하차 (2025-01~2026-04) — `od_h1_analysis.py` 는 2026-01~04만 사용 | <https://www.data.go.kr/data/15159353/fileData.do> |
| `gwangju_역일시간대별_승하차량_202601-202606.csv` | 광주 1호선 역별·일별·시간대별 승하차 (2026-01~06) | <https://www.data.go.kr/data/15060048/fileData.do> |
| `busan_역별_수송수입_2025.csv` | 부산 역별 연간 수송수입 (참고용) | 공공데이터포털 (부산교통공사) |
| `seoul_CARD_SUBWAY_MONTH_202512.csv`, `_202606.csv` | 서울 월별 역별 승하차 (대표 2개월) | 서울열린데이터광장 OA-12914 |

서울 월별 승하차(CARD_SUBWAY_MONTH)는 2025-07~2026-06 12개월분이 있으나 용량
(월 1.2MB × 12)을 고려해 대표 2개월만 포함했다. 나머지는 서울열린데이터광장
<https://data.seoul.go.kr/dataList/OA-12914/S/1/datasetView.do> 에서 월 단위로
내려받을 수 있다.

## 별도로 내려받아야 하는 파일 (용량 제외, `.gitignore` 처리)

기존 저장소의 "용량 제외 + 안내" 컨벤션(`data/raw/README.md`)을 따라 zip 은
커밋하지 않는다. **아래 파일들을 받아 이 폴더에 그대로 넣으면 된다.**

### 서울시 역간 OD 7일치 (약 66MB) — `od_analysis.py` 의 핵심 입력

- 데이터셋: 서울시 정류장·역사별 출발지-도착지(OD) 정보 (한국스마트카드 제공)
- 공공데이터포털: <https://www.data.go.kr/data/15099382/fileData.do>
- 받을 파일: `kscc_dx_ra_od_20260722.zip` ~ `kscc_dx_ra_od_20260728.zip` (7일치,
  일별·시간대별 승객수. 역사마스터 `seoul_역사마스터.csv` 도 같은 페이지에서 제공)
- 2026-07-22(수)~28(화) 1주일치 = 주중 5일 + 주말 2일

### 서울시 역간 OD 월별 아카이브 6개 (약 1.6GB) — `od_h1_analysis.py` 의 핵심 입력

- 같은 페이지(15099382)에서 월 단위 소급 제공: `kscc_dx_ra_od_202601.zip` ~
  `kscc_dx_ra_od_202606.zip` (각 ~250~290MB, 내부에 일별 CSV 28~31개)
- 2026년 상반기 181일 전체. 지방 승하차(부산·대구·대전·광주 2026-01~06)와
  기간이 완전히 중첩되어 기간 정합 분석이 가능 (`docs/README_OD분석.md` 참조).
- 참고: 월별 zip 내부 일별 CSV 는 대부분 cp949 이나 일부(2026-01-09, 05-16 등)는
  utf-8 — `od_h1_analysis.py` 가 자동 판별. 2026-01-09·05-16 두 날은 포털 원천이
  헤더만 있는 빈 CSV 라 집계에서 제외된다(유효 179일).
- 중간 캐시 `h1_cache/od_YYYYMMDD.csv.gz`(역사_ID 수준 일별 집계, 총 ~210MB)가
  있으면 zip 재파싱 없이 2~3분에 재실행된다. 캐시·zip 중 하나만 있으면 됨.

### 서울시 환승경로 통계 (약 10MB, 선택)

- `kscc_dx_trnsf_path_sum_20260728.zip` — 같은 페이지에서 제공. 현재
  `od_analysis.py` 는 사용하지 않으나 환승 페널티 추정에 활용 가능.

zip 이 없으면 `od_analysis.py` 는 OD 집계를 건너뛰고 매핑 테이블과
지방 승하차 가중치만 생성하며, `od_h1_analysis.py` 는 H1 집계를 건너뛴다.

**주의**: `od_analysis.py`(7월 1주)는 `kscc_dx_ra_od_*.zip` 글롭 개수가 정확히
7개일 때만 OD 집계를 수행한다. 풀버전 zip 처럼 월별·7월 일별 zip 이 함께 배치된
상태에서 7월 1주 집계를 재실행하려면 2026-07-22~28 외의 `kscc_dx_ra_od_*.zip` 을
임시로 다른 폴더에 옮겨 두면 된다 (H1 산출물·캐시에는 영향 없음).

## processed/ 산출물

- `od_station_mapping.csv` / `od_station_unmatched.csv` / `node_weights.csv` /
  `node_weights_2026H1.csv` — 작아서 커밋됨 (실행 없이 바로 사용 가능)
- `od_daily_avg.csv`(약 13MB) / `od_peak.csv`(약 8MB) — 커밋 제외,
  `python od_analysis.py` 실행으로 재생성
- `od_daily_avg_2026H1.csv`(약 17MB) / `od_peak_2026H1.csv`(약 13MB) — 커밋 제외,
  `python od_h1_analysis.py` 실행으로 재생성 (월별 zip 또는 `h1_cache/` 필요)
