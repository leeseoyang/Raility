# 추가 원본 데이터 안내 (역간거리 확대 + 환승정보)

기존 `역간거리/` 4종(코레일·서울교통공사·신분당선·대구)에 더해 노선별 실측
역간거리 CSV 25종·호선구성역정보 3종(합계 28개)과 `환승정보/` 15종을 추가했다.
전부 공공데이터포털(data.go.kr) 공개 파일이며 인코딩은 cp949.

> **현 파이프라인(`build_graph.py`)은 이 파일들을 아직 사용하지 않는다.**
> 기존 스크립트는 수정하지 않았으며, 아래 '활용처'는 향후 반영 제안이다.

## 활용처 (제안)

1. **실측 거리 커버리지 확대** — 기존 4종이 커버하지 못하는 수도권 광역선
   (경의중앙·수인·분당·경춘·경강·공항철도), 인천 1·2호선, 경전철
   (에버라인·우이신설·의정부), 부산·대전·광주까지 실측 선로거리를 확보.
   좌표 직선거리 근사 대신 실측 거리로 엣지 가중치를 줄 수 있다.
2. **환승엣지 공식화** — 현재 환승엣지는 역사정보의 환승역구분·좌표 근접으로
   추정하는데, 국가철도공단 환승정보 15종은 노선별 환승 관계(환승선명·환승이후역명)를
   공식 데이터로 제공한다. 환승엣지 검증·보정에 사용 가능.
3. **호선구성역정보 3종(대구·부산·대전)** — 역구성순서·구간키로·기점키로 컬럼으로
   지방 노선의 정거장 순서와 실측 거리를 동시에 검증할 수 있다.

## 역간거리/ 추가 파일 (28개)

| 파일 | 제공기관 | 원본 URL |
|---|---|---|
| 국가철도공단_수도권1호선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041460/fileData.do> |
| 국가철도공단_수도권2호선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041425/fileData.do> |
| 국가철도공단_수도권3호선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041423/fileData.do> |
| 국가철도공단_수도권4호선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041350/fileData.do> |
| 국가철도공단_수도권5호선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041348/fileData.do> |
| 국가철도공단_수도권6호선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041297/fileData.do> |
| 국가철도공단_수도권7호선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041340/fileData.do> |
| 국가철도공단_수도권8호선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041299/fileData.do> |
| 국가철도공단_수도권9호선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041298/fileData.do> |
| 국가철도공단_경의중앙선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041327/fileData.do> |
| 국가철도공단_수인선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041269/fileData.do> |
| 국가철도공단_분당선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041284/fileData.do> |
| 국가철도공단_경춘선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041295/fileData.do> |
| 국가철도공단_경강선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041296/fileData.do> |
| 국가철도공단_공항철도_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15041310/fileData.do> |
| 국가철도공단_인천1호선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15081855/fileData.do> |
| 국가철도공단_인천2호선_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15081856/fileData.do> |
| 국가철도공단_인천교통공사_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15081857/fileData.do> |
| 국가철도공단_에버라인_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15081850/fileData.do> |
| 국가철도공단_우이신설_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15081853/fileData.do> |
| 국가철도공단_의정부경전철_역간거리.csv | 국가철도공단 | <https://www.data.go.kr/data/15081852/fileData.do> |
| 서울교통공사_역간거리.csv | 서울교통공사 | <https://www.data.go.kr/data/15044418/fileData.do> |
| 부산교통공사_역간거리및소요시간.csv | 부산교통공사 | <https://www.data.go.kr/data/3033564/fileData.do> |
| 대전교통공사_1호선_역간소요시간거리요금.csv | 대전교통공사 | <https://www.data.go.kr/data/15082979/fileData.do> |
| 광주교통공사_역간구간거리및소요시간.csv | 광주교통공사 | <https://www.data.go.kr/data/15046044/fileData.do> |
| 국가철도공단_대구교통공사_호선구성역정보.csv | 국가철도공단 | <https://www.data.go.kr/data/15041441/fileData.do> |
| 국가철도공단_부산교통공사_호선구성역정보.csv | 국가철도공단 | <https://www.data.go.kr/data/15041436/fileData.do> |
| 국가철도공단_대전교통공사_호선구성역정보.csv | 국가철도공단 | <https://www.data.go.kr/data/15041445/fileData.do> |

(28개 = 국가철도공단 역간거리 21 + 서울교통공사 자체본 1 + 지방 3 + 호선구성역정보 3.
서울교통공사_역간거리.csv 는 기존 `국가철도공단_서울교통공사 역간거리`와 제공기관·
컬럼 구성이 다른 별도 파일이라 함께 넣었다.)

- 김포골드라인·신림선·부산김해경전철·대경선의 개별 역간거리 파일데이터는
  data.go.kr 미등록 — 좌표 근사 또는 노선정보의 노선연장으로 보정 필요.

## 환승정보/ 추가 파일 (15종)

국가철도공단이 노선별로 공개하는 환승정보(철도운영기관명, 노선명, 역명,
환승철도운영기관, 환승선명, 환승이후역명, 환승기점역명 등).

| 파일 | 원본 URL |
|---|---|
| 국가철도공단_서울교통공사_환승정보.csv | <https://www.data.go.kr/data/15041087/fileData.do> |
| 국가철도공단_코레일_환승정보.csv | <https://www.data.go.kr/data/15041085/fileData.do> |
| 국가철도공단_서울9호선_환승정보.csv | <https://www.data.go.kr/data/15041088/fileData.do> |
| 국가철도공단_경의중앙선_환승정보.csv | <https://www.data.go.kr/data/15041064/fileData.do> |
| 국가철도공단_수인분당선_환승정보.csv | <https://www.data.go.kr/data/15041060/fileData.do> |
| 국가철도공단_경춘선_환승정보.csv | <https://www.data.go.kr/data/15041061/fileData.do> |
| 국가철도공단_경강선_환승정보.csv | <https://www.data.go.kr/data/15041066/fileData.do> |
| 국가철도공단_공항철도_환승정보.csv | <https://www.data.go.kr/data/15041090/fileData.do> |
| 국가철도공단_신분당선_환승정보.csv | <https://www.data.go.kr/data/15041072/fileData.do> |
| 국가철도공단_에버라인_환승정보.csv | <https://www.data.go.kr/data/15041075/fileData.do> |
| 국가철도공단_우이신설_환승정보 — 미등록, 우이신설 환승은 서울교통공사분에 포함 | — |
| 국가철도공단_의정부경전철_환승정보.csv | <https://www.data.go.kr/data/15041069/fileData.do> |
| 국가철도공단_인천지하철_환승정보.csv | <https://www.data.go.kr/data/15041093/fileData.do> |
| 국가철도공단_부산지하철_환승정보.csv | <https://www.data.go.kr/data/15041091/fileData.do> |
| 국가철도공단_부산김해경전철_환승정보.csv | <https://www.data.go.kr/data/15041080/fileData.do> |
| 국가철도공단_대구교통공사_환승정보.csv | <https://www.data.go.kr/data/15041092/fileData.do> |

수집일: 2026-08-03. 전체 출처 대장은 팀 내부 `docs/data_sources.md` 기준이며,
OD·승하차 데이터는 `data/od/README.md` 와 `docs/OD_데이터_조사.md` 참조.
