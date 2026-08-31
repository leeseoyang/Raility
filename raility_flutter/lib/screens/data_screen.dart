import 'package:flutter/material.dart';

import '../state.dart';
import '../theme.dart';
import '../widgets.dart';

// 기준일자를 함께 표기한다 — 취약성 진단에서 데이터 시점은 신뢰도의 일부다.
const _sources = [
  ('국가철도공단_전국 도시철도 역사정보', '역 위치·노선·환승 구분 · 기준 2026-06-30'),
  ('국가철도공단_전국 도시철도 노선정보', '노선별 정거장 구성 · 기준 2026-06-30'),
  ('국가철도공단_전국 도시철도 운행정보', '열차 운행 순서·소요시간·운행 횟수 · 기준 2026-02-28'),
  ('국가철도공단_노선별 역간거리', '구간 실측 거리 (32개 파일) · 기준 2023-12 ~ 2025-12 (노선별 상이)'),
  ('국가철도공단_노선별 환승정보', '환승 연결 관계 (15개 기관)'),
  ('국가철도공단_노선별 승강장 정보', '역층·승강장연결·스크린도어·안전발판 (30개 노선) · 기준 2024-09 ~ 2025-06'),
  ('국토교통부_철도역 빠른 환승 정보', '환승 통로와 가장 가까운 차량순서(칸)·출입문 (103개 환승역) · 기준 2025-11-13'),
  ('각 도시철도 운영기관_역별 승하차실적', '역별 일평균 이용 규모 · 2025년 연간'),
];

class DataScreen extends StatelessWidget {
  const DataScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    final g = AppScope.of(context).graph;

    final counts = <String, int>{};
    for (final s in g.stations) {
      counts[s.region] = (counts[s.region] ?? 0) + 1;
    }
    final regionLine = (counts.keys.toList()
          ..sort((a, b) => counts[b]!.compareTo(counts[a]!)))
        .map((k) => '$k ${counts[k]}')
        .join(' · ');

    final methods = [
      ('그래프 구성',
          '역을 노드, 인접 운행구간·환승·도보 연계를 엣지로 하는 무향 가중그래프를 만듭니다. '
          '가중치는 실제 운행 소요시간입니다.'),
      ('환승 대기',
          '환승·도보 뒤 새 노선에 올라탈 때 그 노선의 기대 대기시간(운행횟수에서 역산한 '
          '배차간격의 절반)을 ${g.transferSec}초 기본 비용에 더합니다.'),
      ('도보 환승',
          '500m 이내·다른 노선·다른 역이면 도보 엣지로 연결합니다(보행 1.2m/s + 게이트 90초). '
          '도보는 경로 탐색에만 쓰고 절점 등 망 위상 지표에는 넣지 않습니다.'),
      ('단일고장점 판정',
          '출발–도착 최단경로를 구한 뒤, 경로 위의 역을 하나씩 그래프에서 제거하고 다시 탐색합니다. '
          '경로가 사라지면 그 역을 단일고장점으로 판정합니다.'),
      ('우회 부담', '제거 후에도 경로가 남으면 늘어난 소요시간을 우회 비용으로 계산합니다.'),
      ('절점', '권역 전체에서 제거 시 망이 분리되는 역을 Tarjan 알고리즘으로 한 번에 찾습니다.'),
      ('승강장 접근성',
          '공단 승강장 정보의 안전발판·승강장연결·스크린도어를 역 단위로 결합해 교통약자 장벽을 '
          '표시합니다. 자료가 발행되지 않은 노선은 0이 아니라 "정보 미공개"로 구분합니다.'),
      ('한계',
          '실시간 운행 상황·열차 시각표·버스 등 대체 수단은 반영하지 않습니다. '
          '물리적 선로 연결 구조만으로 판단한 결과입니다. 승강기 실시간 가동 상태는 포함하지 않습니다.'),
    ];

    return ListView(
      padding: const EdgeInsets.only(bottom: 32),
      children: [
        const Eyebrow('활용한 공공데이터', padding: EdgeInsets.fromLTRB(16, 18, 16, 9)),
        Panel(
          child: Column(children: [
            for (var i = 0; i < _sources.length; i++)
              _item(ink, _sources[i].$1, _sources[i].$2, i > 0),
          ]),
        ),
        const Eyebrow('분석 방법'),
        Panel(
          child: Column(children: [
            for (var i = 0; i < methods.length; i++)
              _item(ink, methods[i].$1, methods[i].$2, i > 0),
          ]),
        ),
        const Eyebrow('분석 범위'),
        Panel(
          child: _item(ink, '역 ${g.stations.length}개 · 구간 ${g.edges.length}개', regionLine, false),
        ),
        const Note('모든 계산은 이 기기에서 수행되며, 어떤 정보도 외부로 전송되지 않습니다. '
            '지도 타일만 네트워크를 사용합니다.'),
      ],
    );
  }

  Widget _item(InkPalette ink, String title, String desc, bool divider) => Container(
        decoration: divider ? BoxDecoration(border: Border(top: BorderSide(color: ink.line))) : null,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        width: double.infinity,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: ink.i0)),
          const SizedBox(height: 3),
          Text(desc, style: TextStyle(fontSize: 12, color: ink.i4, height: 1.55)),
        ]),
      );
}
