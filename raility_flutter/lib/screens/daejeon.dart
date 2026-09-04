import 'package:flutter/material.dart';

import '../graph.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets.dart';

/// 권역 진단 — 권역 선택 + 절점 히어로 + 권역 비교 + 수도권 스트레스 테스트 + 최우선 대비역.
/// (파일명은 딥링크·탭 식별자 호환을 위해 daejeon 을 유지한다)
class DaejeonScreen extends StatefulWidget {
  const DaejeonScreen({super.key});

  @override
  State<DaejeonScreen> createState() => _DaejeonScreenState();
}

class _DaejeonScreenState extends State<DaejeonScreen> {
  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    final app = AppScope.of(context);
    final g = app.graph;
    final regions = g.regions.where((r) => r != '기타').toList();
    var reg = app.panelRegion ?? (regions.contains(app.region) ? app.region : '수도권');
    if (!regions.contains(reg)) reg = '수도권';
    app.panelRegion = reg;

    final frag = g.regionFragility(reg);
    final comp = regions
        .map(g.regionFragility)
        .whereType<RegionFragility>()
        .toList()
      ..sort((a, b) => b.ratio.compareTo(a.ratio));

    return ListView(
      padding: const EdgeInsets.only(bottom: 32),
      children: [
        const Eyebrow('권역 진단', padding: EdgeInsets.fromLTRB(20, 18, 16, 8)),
        // 권역 선택 칩
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(children: [
            for (final r0 in regions) ...[
              InkWell(
                borderRadius: BorderRadius.circular(999),
                onTap: () => setState(() => app.panelRegion = r0),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 7),
                  decoration: BoxDecoration(
                    color: r0 == reg ? ink.tint : ink.surface2,
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(r0,
                      style: TextStyle(
                          fontSize: 13,
                          fontWeight: r0 == reg ? FontWeight.w600 : FontWeight.w500,
                          color: r0 == reg ? Colors.white : ink.i2)),
                ),
              ),
              const SizedBox(width: 7),
            ],
          ]),
        ),
        const SizedBox(height: 10),

        // 히어로 — 이 권역의 절점 비율
        if (frag != null)
          Panel(
            padding: const EdgeInsets.all(20),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text('${(frag.ratio * 100).round()}',
                        style: TextStyle(
                            fontSize: 44, fontWeight: FontWeight.w700,
                            color: ink.i0, letterSpacing: -2, height: 1)),
                    Text('%',
                        style: TextStyle(
                            fontSize: 19, fontWeight: FontWeight.w600, color: ink.i3)),
                  ]),
              const SizedBox(height: 9),
              Text.rich(TextSpan(
                style: TextStyle(fontSize: 13, color: ink.i3, height: 1.55),
                children: [
                  TextSpan(text: '$reg 역 ${frag.total}개 중 '),
                  TextSpan(
                      text: '${frag.cuts}개',
                      style: TextStyle(fontWeight: FontWeight.w700, color: ink.i0)),
                  const TextSpan(text: '는 그 역 하나가 멈추면 철도망이 둘 이상으로 쪼개지는 '),
                  TextSpan(
                      text: '절점',
                      style: TextStyle(fontWeight: FontWeight.w700, color: ink.i0)),
                  const TextSpan(text: '입니다.'),
                ],
              )),
            ]),
          ),

        if (reg == '대전')
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Container(
              padding: const EdgeInsets.fromLTRB(14, 13, 14, 13),
              decoration: BoxDecoration(
                color: ink.risk3Bg,
                borderRadius: BorderRadius.circular(8),
                border: Border(left: BorderSide(color: ink.risk3, width: 3)),
              ),
              child: Text(
                  '대전은 운영 중인 도시철도가 1호선 단일 노선입니다. 망에 순환이나 병렬 경로가 없어 '
                  '중간역 어느 하나가 끊기면 우회할 방법이 구조적으로 없습니다. '
                  '2호선(트램) 개통 시 이 지표의 변화가 곧 투자 효과의 정량적 근거가 됩니다.',
                  style: TextStyle(fontSize: 13.5, color: ink.i1, height: 1.55)),
            ),
          ),

        // 권역 비교
        const Eyebrow('권역별 구조적 취약도'),
        Panel(
          child: Column(children: [
            for (var i = 0; i < comp.length; i++)
              _gaugeRow(ink, comp[i].region,
                  '역 ${comp[i].total}개 중 절점 ${comp[i].cuts}개',
                  comp[i].ratio, '절점 비율', divider: i > 0),
          ]),
        ),
        const Note('절점은 그 역을 빼면 철도망이 둘 이상으로 쪼개지는 역입니다. '
            '비율이 높을수록 한 역의 사고가 망 전체를 끊을 가능성이 큽니다.'),

        // 수도권 스트레스 테스트 (분석 파이프라인 산출물 = 수도권 기준)
        if (reg == '수도권' && g.summary['복원력_adaptive_10%효율비율'] != null)
          ..._metroStress(context, g)
        else if (reg != '수도권')
          const Note('공격 전략별 복원력·환승역 마비·최우선 대비역 분석은 수도권 기준으로 '
              '산출되어 있습니다. 수도권을 선택하면 볼 수 있습니다.'),

        // 이용 규모 상위 역
        Eyebrow('$reg 이용 규모 상위 역'),
        Panel(
          child: Column(children: [
            () {
              final mem = <int>[];
              for (var i = 0; i < g.stations.length; i++) {
                if (g.stations[i].region == reg) mem.add(i);
              }
              mem.sort((a, b) => g.stations[b].demand.compareTo(g.stations[a].demand));
              final arts = frag?.stations.toSet() ?? {};
              return Column(children: [
                for (var k = 0; k < mem.length && k < 10; k++)
                  RowTile(
                    divider: k > 0,
                    rank: '${k + 1}',
                    title: g.stations[mem[k]].name,
                    subtitle: arts.contains(mem[k])
                        ? '절점 — 멈추면 망이 쪼개집니다'
                        : g.stations[mem[k]].lines.join(', '),
                    value: comma(g.stations[mem[k]].demand),
                    valueLabel: '일평균',
                    onTap: () => showStationSheet(context, mem[k]),
                  ),
              ]);
            }(),
          ]),
        ),
      ],
    );
  }

  List<Widget> _metroStress(BuildContext context, RailGraph g) {
    final ink = Palette.of(context);
    final sm = g.summary;
    double? v(String k) => (sm[k] as num?)?.toDouble();
    final strat = [
      ('무작위 사고', v('복원력_random_10%효율비율')),
      ('매개중심성 순 표적', v('복원력_betweenness_10%효율비율')),
      ('연결 많은 역 순 표적', v('복원력_degree_10%효율비율')),
      ('적응적 표적(재계산)', v('복원력_adaptive_10%효율비율')),
    ].where((x) => x.$2 != null).toList()
      ..sort((a, b) => b.$2!.compareTo(a.$2!));
    final rnd = ((v('복원력_random_10%효율비율') ?? 0) * 100).round();
    final adp = ((v('복원력_adaptive_10%효율비율') ?? 0) * 100).round();
    final par = (sm['환승역_상위N_마비'] as List?) ?? [];

    return [
      const Eyebrow('역 10%가 멈추면 — 공격 전략별 잔존 효율'),
      Panel(
        child: Column(children: [
          for (var i = 0; i < strat.length; i++)
            _gaugeRow(ink, strat[i].$1, '', strat[i].$2!, '잔존 효율',
                divider: i > 0, invertColor: true),
        ]),
      ),
      Note('무작위 사고로 역 10%가 멈추면 성능의 $rnd%가 남지만, 매번 다시 계산해 가장 아픈 역만 '
          '노리면 $adp%만 남습니다. 같은 규모의 고장이라도 어디가 멈추느냐가 결과를 가릅니다.'),
      const Eyebrow('환승역이 이용객 순으로 마비되면'),
      Panel(
        child: Column(children: [
          () {
            final rows = par
                .whereType<Map>()
                .where((p) => const [3, 10, 30].contains(p['제거환승역수']))
                .toList();
            return Column(children: [
              for (var i = 0; i < rows.length; i++)
                RowTile(
                  divider: i > 0,
                  title: '환승역 ${rows[i]['제거환승역수']}개 마비',
                  subtitle:
                      '망 연결성분 ${((rows[i]['LCC비율'] as num) * 100).round()}% 유지 — 쪼개지진 않는다',
                  value: '-${rows[i]['효율저하_%']}%',
                  valueLabel: '전역 효율',
                ),
            ]);
          }(),
        ]),
      ),
      const Note('환승역 30개가 마비돼도 망은 거의 쪼개지지 않지만 효율은 4분의 1 넘게 떨어집니다. '
          '"끊기지 않았다"와 "쓸 만하다"는 다른 말입니다.'),
      if (g.prio.isNotEmpty) ...[
        const Eyebrow('최우선 대비 역 — 구조 취약 × 이용 수요'),
        Panel(
          child: Column(children: [
            for (var k = 0; k < g.prio.length && k < 7; k++)
              () {
                final p = g.prio[k];
                final si = g.staOf[(p[0] as num).toInt()];
                final sep = (p[3] as num).toInt();
                return RowTile(
                  divider: k > 0,
                  rank: '${k + 1}',
                  title: g.stations[si].name,
                  subtitle: g.nodes[(p[0] as num).toInt()].line +
                      (sep > 0 ? ' · 멈추면 $sep개 역 고립' : ''),
                  value: '${(p[2] as num).toStringAsFixed(1)}%',
                  valueLabel: '효율 저하',
                  onTap: () => showStationSheet(context, si),
                );
              }(),
          ]),
        ),
      ],
    ];
  }

  Widget _gaugeRow(InkPalette ink, String name, String sub, double ratio,
      String valueLabel, {bool divider = false, bool invertColor = false}) {
    final pct = (ratio * 100);
    final color = invertColor
        ? (pct < 30 ? ink.risk3 : pct < 50 ? ink.risk2 : ink.risk0)
        : (pct >= 75 ? ink.risk3 : pct >= 40 ? ink.risk2 : ink.i3);
    return Container(
      decoration: divider
          ? BoxDecoration(border: Border(top: BorderSide(color: ink.line, width: 0.5)))
          : null,
      margin: divider ? const EdgeInsets.only(left: 16) : null,
      padding: EdgeInsets.fromLTRB(divider ? 0 : 16, 12, 16, 12),
      child: Row(children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(name,
                style: TextStyle(
                    fontSize: 15, fontWeight: FontWeight.w600, color: ink.i0,
                    letterSpacing: -0.15)),
            if (sub.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 1),
                child: Text(sub, style: TextStyle(fontSize: 12.5, color: ink.i3)),
              ),
            Gauge(value: ratio, color: color),
          ]),
        ),
        const SizedBox(width: 12),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text('${pct.round()}%',
              style: TextStyle(
                  fontSize: 15, fontWeight: FontWeight.w600, color: ink.i1,
                  fontFeatures: const [FontFeature.tabularFigures()])),
          Text(valueLabel,
              style: TextStyle(fontSize: 11.5, color: ink.i3)),
        ]),
      ]),
    );
  }
}
