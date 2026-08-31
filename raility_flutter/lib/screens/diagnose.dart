import 'package:flutter/material.dart';

import '../graph.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets.dart';
import 'station_search.dart';

/// 처음 열었을 때 바로 눌러볼 수 있는 대표 구간(권역 종단 경로).
const _suggested = [
  ('대전', '판암', '반석'),
  ('수도권', '소사', '강남'),
  ('수도권', '인천', '청량리'),
  ('부산', '다대포해수욕장', '노포'),
  ('대구', '설화명곡', '하양(대구가톨릭대)'),
  ('광주', '평동', '녹동'),
];

class DiagnoseScreen extends StatelessWidget {
  const DiagnoseScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final r = app.result;

    return ListView(
      padding: const EdgeInsets.only(bottom: 32),
      children: [
        const Eyebrow('경로 진단', padding: EdgeInsets.fromLTRB(16, 18, 16, 9)),
        const _OdCard(),
        const Note('지도 앱은 지금 다니는 길을 알려줍니다. 이 앱은 그 길 위 어느 역 하나가 멈추면 '
            '돌아갈 수 있는지를 계산합니다.'),
        if (r == null) ..._suggestions(context, app) else ..._result(context, app, r),
      ],
    );
  }

  List<Widget> _suggestions(BuildContext context, AppState app) {
    final g = app.graph;
    final found = <(String, int, int)>[];
    for (final (reg, a, b) in _suggested) {
      final ai = g.lookup(a, reg), bi = g.lookup(b, reg);
      if (ai != null && bi != null && ai != bi) found.add((reg, ai, bi));
    }
    found.sort((x, y) =>
        (x.$1 == app.region ? 0 : 1).compareTo(y.$1 == app.region ? 0 : 1));

    return [
      const Eyebrow('바로 살펴보기'),
      Panel(
        child: Column(
          children: [
            for (var i = 0; i < found.length; i++)
              RowTile(
                divider: i > 0,
                title:
                    '${g.stations[found[i].$2].name} → ${g.stations[found[i].$3].name}',
                subtitle: '${found[i].$1} 종단 구간',
                trailing: Icon(Icons.chevron_right, size: 18, color: Palette.of(context).i4),
                onTap: () {
                  app.setFrom(found[i].$2);
                  app.setTo(found[i].$3);
                },
              ),
          ],
        ),
      ),
      const Note('출발·도착역을 직접 고르면 내 통근 경로를 진단할 수 있습니다.'),
    ];
  }

  List<Widget> _result(BuildContext context, AppState app, Diagnosis r) {
    final ink = Palette.of(context);
    final g = app.graph;

    if (!r.ok) {
      return [
        const SizedBox(height: 14),
        Panel(
          padding: const EdgeInsets.all(18),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('연결된 경로가 없습니다',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: ink.i0)),
            const SizedBox(height: 5),
            Text('두 역은 이 데이터셋의 철도망에서 서로 이어져 있지 않습니다. 같은 권역의 역을 선택해 보세요.',
                style: TextStyle(fontSize: 13, color: ink.i3, height: 1.55)),
          ]),
        ),
      ];
    }

    // 결론 한 문장이 먼저다. '실질적 단절' 기준. (웹판과 동일한 규칙)
    final gt = gradeText[r.grade]!;
    final np = r.practical.length;
    final String headline;
    var sub = gt[0];
    if (np == 0) {
      headline = '어느 역이 멈춰도 돌아갈 길이 있습니다';
      if (r.maxDelta > 0) sub += ' · 우회 시 최대 +${mins(r.maxDelta)}분';
    } else if (np == r.mids.length) {
      headline = r.spof.length == r.mids.length
          ? '중간역 ${r.mids.length}개 전부 — 하나만 멈춰도 갈 수 없습니다'
          : '중간역 ${r.mids.length}개 전부 — 멈추면 사실상 갈 수 없습니다';
    } else {
      headline = '중간역 ${r.mids.length}개 중 $np개는 멈추면 사실상 갈 수 없습니다';
      if (r.detour.isNotEmpty) sub += ' · 나머지는 우회 시 최대 +${mins(r.maxDelta)}분';
    }
    if (np > r.spof.length) {
      sub += ' · 우회 불가 ${r.spof.length}개 + 30분 초과 우회 ${np - r.spof.length}개';
    }
    return [
      const SizedBox(height: 14),
      Panel(
        padding: const EdgeInsets.fromLTRB(16, 18, 16, 0),
        child: Column(children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(
              width: 56, height: 56,
              decoration: BoxDecoration(
                  color: gradeColor(ink, r.grade), borderRadius: BorderRadius.circular(13)),
              alignment: Alignment.center,
              child: Text(r.grade,
                  style: const TextStyle(
                      fontSize: 26, fontWeight: FontWeight.w700, color: Colors.white, letterSpacing: -0.8)),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(headline,
                    style: TextStyle(
                        fontSize: 16.5, fontWeight: FontWeight.w700, color: ink.i0,
                        letterSpacing: -0.3, height: 1.3)),
                const SizedBox(height: 4),
                Text(sub, style: TextStyle(fontSize: 13, color: ink.i3, height: 1.5)),
              ]),
            ),
          ]),
          const SizedBox(height: 16),
          Container(
            decoration: BoxDecoration(border: Border(top: BorderSide(color: ink.line, width: 0.5))),
            child: IntrinsicHeight(
              child: Row(children: [
                _metric(ink, '소요시간', '${mins(r.base!.time)}', '분'),
                _divider(ink),
                _metric(ink, '정차역', '${r.stops.length}', '개'),
                _divider(ink),
                _metric(ink, '단일고장점', '${r.spof.length}', '개'),
              ]),
            ),
          ),
        ]),
      ),
      ..._accessibility(context, g, r),
      const Eyebrow('경로 상세'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: _RouteStrip(result: r),
      ),
      if (r.practical.isNotEmpty) ...[
        const Eyebrow('먼저 대비해야 할 역'),
        Panel(
          child: Column(children: [
            // 사회적 취약도 S = 수요 × min(우회 지연, 30분) 순 (웹판과 동일)
            () {
              double social(Stop st) {
                final d = st.spof
                    ? RailGraph.practicalCapS
                    : (st.delta < RailGraph.practicalCapS ? st.delta : RailGraph.practicalCapS);
                return g.stations[st.station].demand * d;
              }
              final sorted = [...r.practical]
                ..sort((a, b) => social(b).compareTo(social(a)));
              return Column(children: [
                for (var i = 0; i < sorted.length && i < 6; i++)
                  RowTile(
                    divider: i > 0,
                    rank: '${i + 1}',
                    title: g.stations[sorted[i].station].name,
                    subtitle: g.stations[sorted[i].station].lines.join(', ') +
                        (sorted[i].spof ? ' · 우회 불가' : ' · 우회 +${mins(sorted[i].delta)}분'),
                    value: comma(g.stations[sorted[i].station].demand),
                    valueLabel: '일평균 승하차',
                    onTap: () => showStationSheet(context, sorted[i].station),
                  ),
              ]);
            }(),
          ]),
        ),
      ],
      Note('역 ${g.stations.length}개, 구간 ${g.edges.length}개 그래프에서 '
          '경로 위의 역을 하나씩 제거하고 다시 탐색해 산출했습니다.'),
    ];
  }

  /// 교통약자 관점 — 기본은 한 줄 요약, 탭하면 상세 (웹판 acc-fold 와 동일한 규칙)
  List<Widget> _accessibility(BuildContext context, RailGraph g, Diagnosis r) {
    final counts = [0, 0, 0];
    var noData = 0, barrierStations = 0;
    for (final st in r.stops) {
      final ac = g.accOf(st.nodes);
      if (ac == null) {
        noData++;
        continue;
      }
      var any = false;
      for (var k = 0; k < 3; k++) {
        if (ac[k + 1] != 0) {
          counts[k]++;
          any = true;
        }
      }
      if (any) barrierStations++;
    }
    if (barrierStations + noData == 0) return const [];
    return [
      const SizedBox(height: 10),
      _AccFold(counts: counts, noData: noData, barrierStations: barrierStations),
    ];
  }

  Widget _metric(InkPalette ink, String label, String v, String unit) => Expanded(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(0, 13, 0, 16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(label, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: ink.i4)),
            const SizedBox(height: 3),
            Row(crossAxisAlignment: CrossAxisAlignment.baseline, textBaseline: TextBaseline.alphabetic, children: [
              Text(v,
                  style: TextStyle(
                      fontSize: 19, fontWeight: FontWeight.w700, color: ink.i0, letterSpacing: -0.4,
                      fontFeatures: const [FontFeature.tabularFigures()])),
              Text(unit, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: ink.i3)),
            ]),
          ]),
        ),
      );

  Widget _divider(InkPalette ink) => Container(width: 1, color: ink.line, margin: const EdgeInsets.only(left: 14, right: 14));
}

/// 교통약자 요약 접이 카드 — 한 줄 요약, 탭하면 장벽별 상세
class _AccFold extends StatefulWidget {
  final List<int> counts;
  final int noData, barrierStations;
  const _AccFold({required this.counts, required this.noData, required this.barrierStations});

  @override
  State<_AccFold> createState() => _AccFoldState();
}

class _AccFoldState extends State<_AccFold> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    const icons = [Icons.accessible, Icons.link_off, Icons.door_sliding_outlined];

    Widget iconBox(IconData icon, Color bg) => Container(
          width: 28, height: 28,
          decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(7)),
          child: Icon(icon, size: 17, color: Colors.white),
        );

    Widget detail(IconData icon, Color bg, String label, int n) => Container(
          decoration: BoxDecoration(
              border: Border(top: BorderSide(color: ink.line, width: 0.5))),
          margin: const EdgeInsets.only(left: 16),
          padding: const EdgeInsets.fromLTRB(0, 11, 16, 11),
          child: Row(children: [
            iconBox(icon, bg),
            const SizedBox(width: 10),
            Expanded(
                child: Text('$label 역',
                    style: TextStyle(fontSize: 14.5, color: ink.i1, letterSpacing: -0.15))),
            Text('$n',
                style: TextStyle(
                    fontSize: 16, fontWeight: FontWeight.w600, color: ink.i0,
                    fontFeatures: const [FontFeature.tabularFigures()])),
            Text('개', style: TextStyle(fontSize: 12, color: ink.i3)),
          ]),
        );

    return Panel(
      child: Column(children: [
        InkWell(
          onTap: () => setState(() => _open = !_open),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
            child: Row(children: [
              iconBox(Icons.accessible, widget.barrierStations > 0 ? ink.risk2 : ink.i4),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                    widget.barrierStations > 0
                        ? '교통약자 장벽이 있는 역 ${widget.barrierStations}개'
                        : '교통약자 장벽 확인 안 됨 (정보 없음 ${widget.noData}개)',
                    style: TextStyle(fontSize: 14.5, color: ink.i1, letterSpacing: -0.15)),
              ),
              AnimatedRotation(
                turns: _open ? 0.25 : 0,
                duration: const Duration(milliseconds: 160),
                child: Icon(Icons.chevron_right, size: 19, color: ink.i4),
              ),
            ]),
          ),
        ),
        if (_open) ...[
          for (var k = 0; k < 3; k++)
            if (widget.counts[k] > 0) detail(icons[k], ink.risk2, accLabels[k], widget.counts[k]),
          if (widget.noData > 0)
            detail(Icons.help_outline, ink.i4, '승강장 정보 미공개', widget.noData),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
            child: Text(
                '국가철도공단 승강장 정보 기준. 안전발판이 없으면 휠체어·유아차 단독 승하차가 어렵고, '
                '승강장이 미연결이면 반대 방향으로 가려면 개찰구를 나가야 합니다.',
                style: TextStyle(fontSize: 12.5, color: ink.i3, height: 1.5)),
          ),
        ],
      ]),
    );
  }
}

/// 출발/도착 선택 카드
class _OdCard extends StatelessWidget {
  const _OdCard();

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    final app = AppScope.of(context);
    final g = app.graph;

    Widget row(bool isFrom) {
      final idx = isFrom ? app.from : app.to;
      final s = idx != null ? g.stations[idx] : null;
      return InkWell(
        onTap: () async {
          final picked = await pickStation(context, isFrom ? '출발역 선택' : '도착역 선택');
          if (picked != null) {
            isFrom ? app.setFrom(picked) : app.setTo(picked);
          }
        },
        child: Container(
          decoration: isFrom ? null : BoxDecoration(border: Border(top: BorderSide(color: ink.line))),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(children: [
            Container(
              width: 9, height: 9,
              decoration: BoxDecoration(
                  color: isFrom ? ink.tint : ink.risk3, shape: BoxShape.circle),
            ),
            const SizedBox(width: 11),
            SizedBox(
              width: 28,
              child: Text(isFrom ? '출발' : '도착',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: ink.i4)),
            ),
            const SizedBox(width: 4),
            Expanded(
              child: s == null
                  ? Text(isFrom ? '출발역 선택' : '도착역 선택',
                      style: TextStyle(fontSize: 16, color: ink.i4, fontWeight: FontWeight.w500))
                  : Row(children: [
                      Flexible(
                        child: Text(s.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                                fontSize: 16, fontWeight: FontWeight.w600, color: ink.i0, letterSpacing: -0.2)),
                      ),
                      const SizedBox(width: 6),
                      Flexible(
                        child: Text(
                            s.lines.first + (s.lines.length > 1 ? ' 외 ${s.lines.length - 1}' : ''),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(fontSize: 12, color: ink.i4)),
                      ),
                    ]),
            ),
          ]),
        ),
      );
    }

    return Stack(alignment: Alignment.centerRight, children: [
      Panel(child: Column(children: [row(true), row(false)])),
      if (app.from != null || app.to != null)
        Padding(
          padding: const EdgeInsets.only(right: 30),
          child: Material(
            color: ink.surface2,
            shape: const CircleBorder(),
            child: InkWell(
              customBorder: const CircleBorder(),
              onTap: app.swap,
              child: SizedBox(
                  width: 32, height: 32,
                  child: Icon(Icons.swap_vert, size: 17, color: ink.tint)),
            ),
          ),
        ),
    ]);
  }
}

/// 경로 스트립 — 노선색 띠 위에 정차역을 세로로 늘어놓는다.
class _RouteStrip extends StatelessWidget {
  final Diagnosis result;
  const _RouteStrip({required this.result});

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    final app = AppScope.of(context);
    final g = app.graph;

    return Column(
      children: List.generate(result.stops.length, (i) {
        final st = result.stops[i];
        final s = g.stations[st.station];
        final isEnd = i == 0 || i == result.stops.length - 1;
        final lineColor = hexColor(g.colorOf(st.rideLine ?? ''));

        // 같은 우회 시간이 연달아 나오면 첫 역에만 표시해 화면을 어지럽히지 않는다.
        final prev = i > 0 ? result.stops[i - 1] : null;
        final sameRun = prev != null && !prev.spof && prev.delta > 60 &&
            mins(prev.delta) == mins(st.delta);

        return IntrinsicHeight(
          child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            SizedBox(
              width: 22,
              child: Stack(alignment: Alignment.topCenter, children: [
                Padding(
                  padding: EdgeInsets.only(
                      top: i == 0 ? 18 : 0, bottom: i == result.stops.length - 1 ? 18 : 0),
                  child: Container(width: 4, color: lineColor),
                ),
                Padding(
                  padding: const EdgeInsets.only(top: 13),
                  child: Container(
                    width: st.spof || isEnd ? 11 : 9,
                    height: st.spof || isEnd ? 11 : 9,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: st.spof ? ink.risk3 : ink.surface,
                      border: Border.all(
                          color: st.spof ? ink.risk3 : (isEnd ? lineColor : ink.i4), width: 2.5),
                    ),
                  ),
                ),
              ]),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: InkWell(
                onTap: () => showStationSheet(context, st.station),
                child: Container(
                  decoration: BoxDecoration(
                      border: i == result.stops.length - 1
                          ? null
                          : Border(bottom: BorderSide(color: ink.line))),
                  padding: const EdgeInsets.symmetric(vertical: 9),
                  // 태그 다이어트: 텍스트 태그 대신 이름 옆 작은 아이콘.
                  // 상세는 역을 탭하면 시트에서 보여준다. (웹판과 동일한 규칙)
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Flexible(
                        child: Text(s.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                                fontSize: 14.5, fontWeight: FontWeight.w600,
                                color: ink.i1, letterSpacing: -0.2)),
                      ),
                      const SizedBox(width: 7),
                      Flexible(
                        child: Text(st.rideLine ?? '',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                                fontSize: 11.5, fontWeight: FontWeight.w600, color: lineColor)),
                      ),
                      if (st.spof) ...[
                        const SizedBox(width: 6),
                        Icon(Icons.warning_amber_rounded, size: 13, color: ink.risk3),
                      ],
                      if (() {
                        final ac = g.accOf(st.nodes);
                        return ac != null && (ac[1] != 0 || ac[2] != 0 || ac[3] != 0);
                      }()) ...[
                        const SizedBox(width: 5),
                        Icon(Icons.accessible, size: 13, color: ink.risk2),
                      ],
                    ]),
                    ...() {
                      final ftr = st.transferHere ? g.fastTransferAt(result, i) : null;
                      return <Widget>[
                        if (st.walkHere)
                          Padding(
                            padding: const EdgeInsets.only(top: 2),
                            child: Text('도보 이동 ${st.walkM}m — 다음 역까지 걸어서 갈아탑니다',
                                style: TextStyle(fontSize: 12, color: ink.i4)),
                          )
                        else if (st.transferHere && st.fromLine != null && st.toLine != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 2),
                            child: Text(
                                '${st.fromLine} → ${st.toLine} 환승'
                                '${ftr != null ? ' · 빠른 환승 ${ftr.list.map((x) => '${x.car}-${x.door}'
                                    '${ftr.resolved || x.dir.isEmpty ? '' : ' (${x.dir} 방면)'}').join(' · ')}' : ''}',
                                style: TextStyle(fontSize: 12, color: ink.i4)),
                          ),
                        if (!st.spof && st.delta > 60 && !sameRun)
                          Padding(
                            padding: const EdgeInsets.only(top: 2),
                            child: Text('우회 시 +${mins(st.delta)}분',
                                style: TextStyle(fontSize: 12, color: ink.i4)),
                          ),
                      ];
                    }(),
                  ]),
                ),
              ),
            ),
          ]),
        );
      }),
    );
  }

}
