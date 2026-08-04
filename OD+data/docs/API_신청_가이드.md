# 공공데이터포털 API 활용신청 가이드 — 도시철도 전체노선정보 · 역사별 환승정보

- 작성일: 2026-08-03
- 대상: 조윤상 (데이터 수집 담당) — **로그인·신청은 본인 계정으로 직접 수행 필요**
- 표기 원칙: **[확인]** = 페이지 직접 확인 / **[추정]** = 로그인 후 확인 필요하거나 일반적 관례

---

## 0. 핵심 요약 (먼저 읽을 것)

두 API 모두 공공데이터포털(data.go.kr)에서 **API 유형 "LINK"** 로 등록되어 있다. [확인]
즉, 실제 API 서버는 **철도산업정보센터 레일포털(data.kric.go.kr)의 openapi.kric.go.kr**이며, **인증키(서비스키)는 레일포털에서 발급**받는 구조다. 레일포털은 "회원가입 → 인증키 발급 → 하나의 인증키로 다수 Open API 사용" 절차를 안내한다. [확인: https://data.kric.go.kr/rips/serviceInfo/openapi/process.do ]

> **실무 권고**: data.go.kr 활용신청과 별개로, 레일포털(data.kric.go.kr) 회원가입 후 인증키 1개를 발급받으면 노선정보·환승정보·열차별 운행시각표 등 레일포털의 36개 API를 모두 같은 키로 호출할 수 있다.

---

## 1. 대상 API 정리

### 1-1. 국가철도공단_도시철도 전체노선정보 [확인]

| 항목 | 내용 | 출처 |
|---|---|---|
| data.go.kr 페이지 | https://www.data.go.kr/data/15041666/openapi.do | 직접 확인 |
| 레일포털 상세 | https://data.kric.go.kr/rips/M_01_02/detail.do?id=431&service=trainUseInfo&operation=subwayRouteInfo | 직접 확인 |
| 제공기관 | 국가철도공단 (관리부서: 디지털관리처 / 레일포털 표기: 전국도시철도운영기관) | 양쪽 페이지 |
| 설명 | 도시철도 운영기관 및 노선에 따른 상행→하행 노선구성 역명 정보 | 레일포털 |
| 엔드포인트 | `https://openapi.kric.go.kr/openapi/trainUseInfo/subwayRouteInfo` | 레일포털 |
| 포맷 / 유형 | JSON/XML, REST | 레일포털 |
| 승인 방식 | 자동승인 (개발·운영 단계 모두) | data.go.kr |
| 트래픽 제한 | 페이지에 구체 수치 없음 — "해당 기관의 정책에 따라 트래픽 수는 상이할 수 있음" | data.go.kr |
| 비용 / 라이선스 | 무료 / 이용허락범위 제한 없음(data.go.kr), 저작권표시(레일포털) | 양쪽 페이지 |

**요청 파라미터** [확인]

| 파라미터 | 설명 | 예시 |
|---|---|---|
| `serviceKey` | 서비스키(인증키) | — |
| `format` | 응답 포맷 | `json` 또는 `xml` |
| `mreaWideCd` | 권역코드 | `01`=수도권, `02`=부산, `03`=대구, `04`=광주, `05`=대전 |
| `lnCd` | 선코드 | 예: `I2`, `A1` |

**응답 필드** [확인]: `lnCd`(선코드), `mreaWideCd`(권역코드), `railOprIsttCd`(철도운영기관코드), `routCd`(노선코드), `routNm`(노선명), `stinCd`(역코드), `stinConsOrdr`(역구성순서), `stinNm`(역명)

→ `stinConsOrdr`(역구성순서)로 인접역 엣지를 바로 구성할 수 있어 **그래프 구축의 핵심 API**다.

### 1-2. 국가철도공단_역사별 환승정보 [확인]

| 항목 | 내용 | 출처 |
|---|---|---|
| data.go.kr 페이지 | https://www.data.go.kr/data/15041673/openapi.do | 직접 확인 |
| 레일포털 상세 | https://data.kric.go.kr/rips/M_01_02/detail.do?id=181&service=convenientInfo&operation=stationTransferInfo | 직접 확인 |
| 제공기관 | 국가철도공단 (관리부서: 디지털관리처) | data.go.kr |
| 엔드포인트 | `https://openapi.kric.go.kr/openapi/convenientInfo/stationTransferInfo` | 레일포털 |
| 포맷 / 유형 | JSON/XML, REST | 레일포털 |
| 승인 방식 | 자동승인 (개발·운영 단계 모두) | data.go.kr |
| 트래픽 제한 | "해당 기관의 정책에 따라 트래픽 수는 상이할 수 있음" (수치 미공개) | data.go.kr |

**요청 파라미터** [확인]

| 파라미터 | 설명 | 예시 |
|---|---|---|
| `serviceKey` | 서비스키(인증키) | — |
| `format` | 응답 포맷 | `json` / `xml` |
| `railOprIsttCd` | 철도운영기관코드 | `S1`(서울교통공사) |
| `lnCd` | 선코드 | `3` |
| `stinCd` | 역코드 | `312`(불광역 샘플) |

**응답 필드** [확인]: `chtnDst`(환승거리), `chtnLn`(환승선), `stLocCont`(시작위치내용), `clsLocCont`(종료위치내용), `lnCd`, `railOprIsttCd`, `stinCd`

→ `chtnDst`(환승거리)를 **환승 엣지 가중치**(환승비용)로 직접 사용할 수 있다.

### 1-3. (권장 추가 신청) 국가철도공단_열차별운행시각표 [확인]

같은 인증키로 호출 가능. R1 대응(운행빈도 가중치)의 핵심.

- data.go.kr: https://www.data.go.kr/data/15041665/openapi.do
- 엔드포인트: `https://openapi.kric.go.kr/openapi/trainUseInfo/subwayTimetable`
- 파라미터: `serviceKey`, `format`, `dayCd`(7=토, 8=평일, 9=휴일), `lnCd`, `railOprIsttCd`, `stinCd`
- 응답: `arvTm`, `dptTm`, `trnNo`, `dayCd`, `dayNm`, `lnCd`, `railOprIsttCd`, `stinCd`
- 급행 표시 버전: `trainUseInfo/subwayTimetableExp` (레일포털 id=434)

---

## 2. 활용신청 절차 (단계별)

### 경로 A — 레일포털 직접 발급 (권장) [확인: 절차 페이지]

1. **[사람 필요 — 조윤상]** 레일포털 회원가입: https://data.kric.go.kr → 우측 상단 "회원가입" (개인 정보 입력·본인 확인 필요)
2. **[사람 필요 — 조윤상]** 로그인 후 **인증키 발급** 신청 (Open API 메뉴 → 활용신청 버튼 / 마이페이지에서 발급·확인)
   - "OPEN API 사용을 위한 인증키를 발급받습니다. 발급된 하나의 인증키 정보를 이용해 다수의 OPEN API를 사용" [확인]
   - 인증키는 필요 시 폐기 후 재발급 가능 [확인]
3. 발급된 인증키를 `.env` 등에 보관 (저장소에 커밋 금지)
4. 아래 3장의 샘플 호출로 즉시 동작 확인
   - 발급 후 반영 대기 시간은 레일포털 페이지에 명시 없음 [확인]. 즉시~수 시간 내 사용 가능할 것으로 보이나 [추정], 호출이 인증 오류를 반환하면 다음날 재시도.
   - "과도한 데이터 트래픽 발생 시 사용 제한 가능" [확인] — 전수 수집 시 역별 호출 사이에 sleep을 넣을 것.

### 경로 B — 공공데이터포털(data.go.kr) 경유 [부분 확인]

1. **[사람 필요 — 조윤상]** data.go.kr 회원가입 및 로그인 (본인인증 필요)
2. 각 API 페이지( 15041666 / 15041673 )에서 **"활용신청"** 버튼 클릭 — 두 API 모두 **자동승인**으로 표기됨 [확인]
3. 활용목적 등 신청 양식 작성 후 제출
4. **마이페이지 → 오픈API → 개발계정** 에서 승인 상태와 인증키 확인 [추정: data.go.kr 일반 절차]
   - 일반 API는 자동승인 직후 발급되며 실제 호출 반영까지 통상 1시간 내외 [추정: 포털 일반 안내 관례]
   - **주의**: 이 두 건은 LINK형이므로, 활용신청 클릭 시 레일포털로 연계되거나 레일포털 키를 요구할 수 있다 [추정 — 로그인해야 확인 가능]. 그 경우 경로 A로 진행하면 된다.

> **Day 1 체크리스트 (조윤상)**
> 1. 레일포털 회원가입 + 인증키 발급 (경로 A)
> 2. 노선정보 5개 권역(01~05) 호출 → JSON 저장
> 3. 환승정보·열차별운행시각표 호출 테스트
> 4. data.go.kr 계정도 만들어 두기 (표준데이터 CSV 다운로드 및 타 API 대비)

---

## 3. 샘플 호출

서비스키는 발급받은 값으로 교체 (`YOUR_SERVICE_KEY`). 샘플 URL 형식은 레일포털 상세 페이지의 공식 샘플 기준. [확인]

### 3-1. curl

```bash
# 도시철도 전체노선정보 — 대전권(05) 전체 노선
curl -s "https://openapi.kric.go.kr/openapi/trainUseInfo/subwayRouteInfo?serviceKey=YOUR_SERVICE_KEY&format=json&mreaWideCd=05"

# 도시철도 전체노선정보 — 수도권(01) 특정 노선(lnCd 예: A1)
curl -s "https://openapi.kric.go.kr/openapi/trainUseInfo/subwayRouteInfo?serviceKey=YOUR_SERVICE_KEY&format=xml&mreaWideCd=01&lnCd=A1"

# 역사별 환승정보 — 불광역(서울교통공사 S1, 3호선, 역코드 312) 공식 샘플
curl -s "https://openapi.kric.go.kr/openapi/convenientInfo/stationTransferInfo?serviceKey=YOUR_SERVICE_KEY&format=json&railOprIsttCd=S1&lnCd=3&stinCd=312"

# 열차별 운행시각표 — 서울역 평일(dayCd=8) 공식 샘플
curl -s "https://openapi.kric.go.kr/openapi/trainUseInfo/subwayTimetable?serviceKey=YOUR_SERVICE_KEY&format=json&railOprIsttCd=S1&dayCd=8&lnCd=1&stinCd=150"
```

### 3-2. Python (requests)

```python
import requests, time

SERVICE_KEY = "YOUR_SERVICE_KEY"  # .env로 관리 권장
BASE = "https://openapi.kric.go.kr/openapi"

def kric_get(path: str, **params) -> dict:
    params.update(serviceKey=SERVICE_KEY, format="json")
    r = requests.get(f"{BASE}/{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()

# 1) 전국 노선정보 수집 (권역 01 수도권 ~ 05 대전)
routes = []
for mrea in ["01", "02", "03", "04", "05"]:
    data = kric_get("trainUseInfo/subwayRouteInfo", mreaWideCd=mrea)
    routes.append(data)
    time.sleep(0.5)  # 트래픽 예절

# 2) 특정 역 환승정보 (예: 불광역)
transfer = kric_get("convenientInfo/stationTransferInfo",
                    railOprIsttCd="S1", lnCd="3", stinCd="312")

# 3) 특정 역 평일 열차별 시각표 (예: 서울역) → 운행빈도 = len(레코드)
timetable = kric_get("trainUseInfo/subwayTimetable",
                     railOprIsttCd="S1", dayCd="8", lnCd="1", stinCd="150")
```

> 응답 JSON의 최상위 키 구조(예: `body` 리스트 여부)는 인증키 발급 후 첫 호출에서 확인할 것 [추정 — 문서에 응답 예시 미제공].

---

## 4. 참고: 신청 없이 바로 받을 수 있는 표준데이터 (R2 대응)

승인 대기 중 착수용, 로그인 불필요 즉시 다운로드:

- 전국도시철도역사정보 표준데이터: https://www.data.go.kr/data/15013205/standard.do
- 전국도시철도노선정보 표준데이터: https://www.data.go.kr/data/15013203/standard.do
- 전국도시철도운행정보 표준데이터: https://www.data.go.kr/data/15013206/standard.do

### 확인된 주요 출처
- https://www.data.go.kr/data/15041666/openapi.do
- https://www.data.go.kr/data/15041673/openapi.do
- https://data.kric.go.kr/rips/M_01_02/detail.do?id=431&service=trainUseInfo&operation=subwayRouteInfo
- https://data.kric.go.kr/rips/M_01_02/detail.do?id=181&service=convenientInfo&operation=stationTransferInfo
- https://data.kric.go.kr/rips/M_01_02/detail.do?id=162&service=trainUseInfo&operation=subwayTimetable
- https://data.kric.go.kr/rips/serviceInfo/openapi/process.do
