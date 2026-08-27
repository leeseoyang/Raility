import 'package:flutter/material.dart';

import '../graph.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets.dart';

class DaejeonScreen extends StatelessWidget {
  const DaejeonScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    final g = AppScope.of(context).graph;

    final dj = <int>[];
    for (var i = 0; i < g.stations.length; i++) {
      if (g.stations[i].region == '대전') dj.add(i);
    }

    // 양 종점(연결 차수 1) 사이 전 구간을 진단한다.
    final ends = dj.where((i) => g.staAdj[i].length <= 1).toList();
    final a = ends.isNotEmpty ? ends.first : dj.first;
    final b = ends.length > 1 ? ends[1] : dj.last;
    final r = g.diagnose(a, b);
    final pct = r.ok && r.mids.isNotEmpty ? (r.spof.length / r.mids.length * 100).round() : 0;

    final comp = g.regions
        .where((x) => x != '기타')
        .map(g.regionFragility)
        .whereType<RegionFragility>()
        .toList()
      ..sort((x, y) => y.ratio.compareTo(x.ratio));

    final byDemand = [...dj]..sort((x, y) => g.stations[y].demand.compareTo(g.stations[x].demand));
    final spofSet = r.spof.map((s) => s.station).toSet();

    return ListView(
      padding: const EdgeInsets.only(bottom: 32),
      children: [
        const SizedBox(height: 18),
        Panel(
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 20),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(crossAxisAlignment: CrossAxisAlignment.baseline, textBaseline: TextBaseline.alphabetic, children: [
              Text('$pct',
                  style: TextStyle(
                      fontSize: 44, fontWeight: FontWeight.w800, color: ink.i0, letterSpacing: -2,
                      height: 1, fontFeatures: const [FontFeature.tabularFigures()])),
              Text('%', style: TextStyle(fontSize: 19, fontWeight: FontWeight.w700, color: ink.i3)),
            ]),
            const SizedBox(height: 9),
            Text(
              '대전 도시철도 1호선 ${g.stations[a].name} → ${g.stations[b].name} 전 구간에서, '
              '중간역 ${r.ok ? r.mids.length : 0}개 중 ${r.ok ? r.spof.length : 0}개가 멈추면 '
              '우회 경로가 존재하지 않습니다.',
              style: TextStyle(fontSize: 13, color: ink.i3, height: 1.6),
            ),
          ]),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Container(
            padding: const EdgeInsets.fromLTRB(14, 13, 14, 13),
            decoration: BoxDecoration(
              color: ink.risk3Bg,
              border: Border(left: BorderSide(color: ink.risk3, width: 3)),
              borderRadius: const BorderRadius.horizontal(right: Radius.circular(8)),
            ),
            child: Text(
              '대전은 운영 중인 도시철도가 1호선 단일 노선입니다. 망에 순환이나 병렬 경로가 없어 '
              '중간역 어느 하나가 끊기면 그 지점을 우회할 방법이 구조적으로 없습니다. '
              '수도권처럼 노선이 겹치는 곳에서는 같은 사고가 나도 다른 노선으로 돌아갈 수 있습니다.',
              style: TextStyle(fontSize: 13, color: ink.i1, height: 1.6),
            ),
          ),
        ),
        const Eyebrow('권역별 구조적 취약도'),
        Panel(
          child: Column(children: [
            for (var i = 0; i < comp.length; i++)
              () {
                final c = comp[i];
                final p = (c.ratio * 100).round();
                return RowTile(
                  divider: i > 0,
                  title: c.region,
                  subtitle: '역 ${c.total}개 중 절점 ${c.cuts}개',
                  subWidget: Gauge(
                    value: c.ratio,
                    color: p >= 75 ? ink.risk3 : (p >= 40 ? ink.risk2 : ink.i3),
                  ),
                  value: '$p%',
                  valueLabel: '절점 비율',
                );
              }(),
          ]),
        ),
        const Note('절점은 그 역을 빼면 철도망이 둘 이상으로 쪼개지는 역입니다. '
            '비율이 높을수록 한 역의 사고가 망 전체를 끊을 가능성이 큽니다. '
            '권역 전체 위상을 한 번에 계산한 값이라 특정 경로 선택에 좌우되지 않습니다.'),
        const Eyebrow('대전 1호선 역별 이용 규모'),
        Panel(
          child: Column(children: [
            for (var i = 0; i < byDemand.length; i++)
              RowTile(
                divider: i > 0,
                rank: '${i + 1}',
                title: g.stations[byDemand[i]].name,
                subtitle: spofSet.contains(byDemand[i]) ? '멈추면 노선이 양분됩니다' : '종점부',
                value: comma(g.stations[byDemand[i]].demand),
                valueLabel: '일평균',
                onTap: () => showStationSheet(context, byDemand[i]),
              ),
          ]),
        ),
        const Note('대전 도시철도 2호선(트램)이 개통되면 이 지표가 어떻게 바뀌는지가 '
            '곧 투자 효과의 정량적 근거가 됩니다.'),
      ],
    );
  }
}
