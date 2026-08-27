# Raility (Flutter · Android)

> 지도 앱은 **지금 다니는 길**을 알려준다.
> Raility는 **그 길 위 어느 역 하나가 멈추면 돌아갈 수 있는지**를 알려준다.

2026년도 공공데이터 활용 공모전 — 분야 1(실제 구현 가능한 신규 웹/앱 서비스 개발) 출품작의
네이티브 안드로이드 버전. 웹 PWA 버전은 `../raility_app` 에 있다.

## 실행

```bash
export PATH="/c/src/flutter/bin:$PATH"

flutter emulators --launch raility_pixel   # 에뮬레이터 부팅
flutter run                                # 디버그 실행 (핫 리로드)
```

VS Code에서는 `F5` → **Raility (Flutter · 에뮬레이터)** 를 고르면 된다.

### 검증

```bash
flutter analyze     # 0 issues
flutter test        # 30건
```

`test/graph_test.dart` 는 웹판 `raility_app/test_graph.js` 와 **같은 기준**으로
Dart 포팅을 검증한다. 두 구현이 어긋나면 즉시 드러난다.

### 데이터 갱신

```bash
cd ..                      # 프로젝트 루트
python build_app_data.py   # assets/network.json 재생성 (웹판 data.js 와 동시 생성)
```

## 지도

`flutter_map` 기반이며 타일은 **VWorld 우선 · CARTO 대체** 로 동작한다.

- 기본값은 CARTO(OpenStreetMap)로, 키 없이 바로 뜬다.
- VWorld(국토교통부) 키가 있으면 국내 공공 지도로 바뀐다. 타일이 실패하면 CARTO로 자동 전환된다.

```bash
# vworld.kr → 오픈API → 인증키 발급 후
flutter run --dart-define=VWORLD_KEY=발급받은키
```

지도 위에는 역(원 크기 = 일평균 승하차), 노선(고유색), **끊기면 망이 분리되는 구간·역**(적색)이
겹쳐 그려진다. 역을 누르면 상세가 열린다.

## 구조

```
lib/
  graph.dart              그래프 · 최단경로 · SPOF · 절점    ← 웹판 graph.js 의 Dart 포팅
  state.dart              앱 상태 (출도착·권역, 선택 영속화)
  theme.dart              디자인 토큰 (라이트/다크)
  widgets.dart            공용 UI 조각
  screens/
    diagnose.dart         경로 진단 · 등급 · 경로 스트립
    station_search.dart   역 검색 바텀시트
    map_screen.dart       실지도 + 취약구간 오버레이
    daejeon.dart          대전 전용 뷰
    data_screen.dart      데이터 출처 · 분석 방법
assets/network.json       네트워크 번들 (build_app_data.py 생성)
test/graph_test.dart      로직 검증 30건
```

## 대전권 결과

대전은 운영 중인 도시철도가 **1호선 단일 노선**이다. 망에 순환이나 병렬 경로가 없어
중간역 어느 하나가 끊기면 우회할 방법이 **구조적으로 존재하지 않는다.**

판암→반석 전 구간 진단: **중간역 20개 전부가 단일고장점**(등급 E).

권역별 **절점 비율** — 절점은 제거하면 철도망이 둘 이상으로 쪼개지는 역이다.

| 권역 | 절점 / 역 | 비율 |
|---|---:|---:|
| 대전 | 20 / 22 | **91%** |
| 광주 | 18 / 20 | 90% |
| 대구 | 82 / 97 | 85% |
| 부산 | 80 / 141 | 57% |
| 수도권 | 198 / 661 | 30% |

## 개발 환경

- Flutter 3.44.9 / Dart 3.12.2
- Android SDK 35 (compile 36), JDK 17
- 에뮬레이터 AVD `raility_pixel` (Pixel 6 규격 1080×2400, 420dpi)

데이터 처리 시 확인한 원본 데이터의 문제(역명 표기 불일치, 인접 구간 노선 라벨 어긋남 등)는
`../raility_app/README.md` 에 정리해 두었다. 두 구현이 같은 번들을 쓰므로 동일하게 적용된다.
