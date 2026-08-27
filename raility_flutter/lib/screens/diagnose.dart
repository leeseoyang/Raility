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

    final gt = gradeText[r.grade]!;
    return [
      const SizedBox(height: 14),
      Panel(
        padding: const EdgeInsets.fromLTRB(16, 18, 16, 0),
        child: Column(children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(
              width: 56, height: 56,
              decoration: BoxDecoration(
                  color: gradeColor(ink, r.grade), borderRadius: BorderRadius.circular(14)),
              alignment: Alignment.center,
              child: Text(r.grade,
                  style: const TextStyle(
                      fontSize: 26, fontWeight: FontWeight.w800, color: Colors.white, letterSpacing: -0.8)),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(gt[0],
                    style: TextStyle(
                        fontSize: 17, fontWeight: FontWeight.w700, color: ink.i0, letterSpacing: -0.3)),
                const SizedBox(height: 4),
                Text(gt[1], style: TextStyle(fontSize: 13, color: ink.i3, height: 1.55)),
              ]),
            ),
          ]),
          const SizedBox(height: 16),
          Container(
            decoration: BoxDecoration(border: Border(top: BorderSide(color: ink.line))),
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
      Note(r.spof.isEmpty
          ? '이 경로의 중간역 ${r.mids.length}개는 모두 우회 가능합니다.'
              '${r.maxDelta > 0 ? ' 가장 불리한 경우에도 ${mins(r.maxDelta)}분만 더 걸립니다.' : ''}'
          : '중간역 ${r.mids.length}개 중 ${r.spof.length}개가 멈추면 이 경로로는 목적지에 갈 수 없습니다.'
              '${r.detour.isNotEmpty ? ' 나머지 ${r.detour.length}개 역은 우회 시 최대 ${mins(r.maxDelta)}분이 더 걸립니다.' : ''}'),
      ..._accessibility(context, g, r),
      const Eyebrow('경로 상세'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: _RouteStrip(result: r),
      ),
      if (r.spof.isNotEmpty) ...[
        const Eyebrow('먼저 대비해야 할 역'),
        Panel(
          child: Column(children: [
            for (var i = 0; i < r.spof.length && i < 6; i++)
              () {
                final sorted = [...r.spof]
                  ..sort((a, b) =>
                      g.stations[b.station].demand.compareTo(g.stations[a.station].demand));
                final s = g.stations[sorted[i].station];
                return RowTile(
                  divider: i > 0,
                  rank: '${i + 1}',
                  title: s.name,
                  subtitle: s.lines.join(', '),
                  value: comma(s.demand),
                  valueLabel: '일평균 승하차',
                  onTap: () => showStationSheet(context, sorted[i].station),
                );
              }(),
          ]),
        ),
      ],
      Note('역 ${g.stations.length}개, 구간 ${g.edges.length}개 그래프에서 '
          '경로 위의 역을 하나씩 제거하고 다시 탐색해 산출했습니다.'),
    ];
  }

  /// 교통약자 관점 — 경로 위 승강장 장벽 집계 (웹판 acc-card 와 동일한 규칙)
  List<Widget> _accessibility(BuildContext context, RailGraph g, Diagnosis r) {
    final ink = Palette.of(context);
    final counts = [0, 0, 0];
    var noData = 0;
    for (final st in r.stops) {
      final ac = g.accOf(st.nodes);
      if (ac == null) {
        noData++;
        continue;
      }
      for (var k = 0; k < 3; k++) {
        if (ac[k + 1] != 0) counts[k]++;
      }
    }
    if (counts[0] + counts[1] + counts[2] + noData == 0) return const [];

    const icons = [Icons.accessible, Icons.link_off, Icons.door_sliding_outlined];
    Widget row(IconData icon, Color iconBg, String label, int n, {bool divider = false}) =>
        Container(
          decoration: divider
              ? BoxDecoration(border: Border(top: BorderSide(color: ink.line, width: 0.5)))
              : null,
          margin: divider ? const EdgeInsets.only(left: 16) : null,
          padding: EdgeInsets.fromLTRB(divider ? 0 : 16, 11, 16, 11),
          child: Row(children: [
            Container(
              width: 28, height: 28,
              decoration: BoxDecoration(color: iconBg, borderRadius: BorderRadius.circular(7)),
              child: Icon(icon, size: 17, color: Colors.white),
            ),
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

    final rows = <Widget>[];
    for (var k = 0; k < 3; k++) {
      if (counts[k] > 0) {
        rows.add(row(icons[k], ink.risk2, accLabels[k], counts[k], divider: rows.isNotEmpty));
      }
    }
    if (noData > 0) {
      rows.add(row(Icons.help_outline, ink.i4, '승강장 정보 미공개', noData, divider: rows.isNotEmpty));
    }

    return [
      const Eyebrow('교통약자 관점'),
      Panel(child: Column(children: rows)),
      const Note('국가철도공단 승강장 정보 기준. 안전발판이 없으면 휠체어·유아차 단독 승하차가 어렵고, '
          '승강장이 미연결이면 반대 방향으로 가려면 개찰구를 나가야 합니다.'),
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
                    ]),
                    // 태그는 가로로 흘려 붙인다. 승강장 장벽은 SPOF 와 별개 축이므로 병기한다.
                    ...() {
                      final ac = g.accOf(st.nodes);
                      final tags = <Widget>[
                        if (st.transferHere && st.fromLine != null && st.toLine != null)
                          _tag(ink, '${st.fromLine} → ${st.toLine} 환승', ink.i3, ink.surface2),
                        if (st.spof)
                          _tag(ink, '이 역이 멈추면 우회 불가', ink.risk3, ink.risk3Bg,
                              icon: Icons.warning_amber_rounded),
                        if (ac == null)
                          _tag(ink, '승강장 정보 없음', ink.i4, ink.surface2)
                        else
                          for (var k = 0; k < 3; k++)
                            if (ac[k + 1] != 0) _tag(ink, accLabels[k], ink.risk2, ink.risk2Bg),
                        if (!st.spof && st.delta > 60 && !sameRun)
                          _tag(ink, '우회 시 +${mins(st.delta)}분', ink.risk2, ink.risk2Bg),
                      ];
                      return tags.isEmpty
                          ? const <Widget>[]
                          : [Wrap(spacing: 5, runSpacing: 0, children: tags)];
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

  Widget _tag(InkPalette ink, String text, Color fg, Color bg, {IconData? icon}) => Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
          decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(6)),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            if (icon != null) ...[Icon(icon, size: 12, color: fg), const SizedBox(width: 4)],
            Text(text, style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: fg)),
          ]),
        ),
      );
}
