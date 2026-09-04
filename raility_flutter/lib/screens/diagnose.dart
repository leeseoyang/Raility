import 'dart:math' as math;

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
      const SizedBox(height: 10),
      _WaitChips(app: app),
      const SizedBox(height: 10),
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
                  _PrepRow(rank: i + 1, st: sorted[i], r: r, divider: i > 0),
              ]);
            }(),
          ]),
        ),
      ],
      const SizedBox(height: 18),
      _AdvFold(r: r),
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

/// 배차 시간대 칩 — 첨두엔 우회 가능해도 한산 시간엔 사실상 단절인 경로가 있다
class _WaitChips extends StatelessWidget {
  final AppState app;
  const _WaitChips({required this.app});

  static const _modes = [('peak', '첨두 배차'), ('avg', '평균 배차'), ('quiet', '한산 배차')];

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(children: [
        for (final (mode, label) in _modes) ...[
          InkWell(
            borderRadius: BorderRadius.circular(999),
            onTap: () {
              if (app.graph.setWaitMode(mode)) app.rediagnose();
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 7),
              decoration: BoxDecoration(
                color: app.graph.waitMode == mode ? ink.tint : ink.surface2,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(label,
                  style: TextStyle(
                      fontSize: 13,
                      fontWeight: app.graph.waitMode == mode ? FontWeight.w600 : FontWeight.w500,
                      color: app.graph.waitMode == mode ? Colors.white : ink.i2)),
            ),
          ),
          const SizedBox(width: 7),
        ],
      ]),
    );
  }
}

/// 대비역 행 — 탭하면 "그래서 어떻게 가야 하나"(대체 경로 요약)를 펼친다
class _PrepRow extends StatefulWidget {
  final int rank;
  final Stop st;
  final Diagnosis r;
  final bool divider;
  const _PrepRow({required this.rank, required this.st, required this.r, required this.divider});

  @override
  State<_PrepRow> createState() => _PrepRowState();
}

class _PrepRowState extends State<_PrepRow> {
  bool _open = false;

  String? _nearestWalkable(RailGraph g, int si) {
    final s = g.stations[si];
    String? best;
    var bestD = 500.0;
    for (final t in g.stations) {
      if (t.index == si) continue;
      if (t.lines.any(s.lines.contains)) continue;
      final d = math.sqrt(math.pow((s.lat - t.lat) * 111000, 2) +
          math.pow((s.lon - t.lon) * 88000, 2));
      if (d <= bestD) {
        bestD = d;
        best = '${t.name}까지 도보 약 ${d.round()}m';
      }
    }
    return best;
  }

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    final g = AppScope.of(context).graph;
    final st = widget.st, r = widget.r;
    final s = g.stations[st.station];

    return Column(children: [
      RowTile(
        divider: widget.divider,
        rank: '${widget.rank}',
        title: s.name,
        subtitle: s.lines.join(', ') +
            (st.spof ? ' · 우회 불가' : ' · 우회 +${mins(st.delta)}분'),
        value: comma(s.demand),
        valueLabel: '일평균 승하차',
        onTap: () => setState(() => _open = !_open),
      ),
      if (_open)
        Container(
          margin: const EdgeInsets.only(left: 16),
          padding: const EdgeInsets.fromLTRB(0, 10, 16, 12),
          decoration: BoxDecoration(
              border: Border(top: BorderSide(color: ink.line, width: 0.5))),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            () {
              final alt = st.spof
                  ? null
                  : g.shortest(r.stops.first.station, r.stops.last.station,
                      block: [st.station]);
              if (alt == null) {
                final walk = _nearestWalkable(g, st.station);
                return Text(
                    '이 역이 멈추면 이 경로로는 갈 수 없습니다. '
                    '${walk != null ? '인근 대체: $walk.' : '500m 안에 다른 노선 역도 없습니다.'}',
                    style: TextStyle(fontSize: 13, color: ink.i2, height: 1.5));
              }
              final lines = <String>[];
              for (final x in g.toStops(alt.path)) {
                final l = x.rideLine;
                if (l != null && !lines.contains(l)) lines.add(l);
              }
              return Text(
                  '우회 경로: ${lines.join(' → ')} · +${mins(alt.time - r.base!.time)}분 '
                  '(${mins(alt.time)}분 소요)',
                  style: TextStyle(fontSize: 13, color: ink.i2, height: 1.5));
            }(),
            const SizedBox(height: 7),
            InkWell(
              onTap: () => showStationSheet(context, st.station),
              child: Text('역 정보 보기',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: ink.tint)),
            ),
          ]),
        ),
    ]);
  }
}

/// 고급 진단 접이 카드 — 구간 사고·연속 폐쇄·이중 고장 (요청 시 계산)
class _AdvFold extends StatefulWidget {
  final Diagnosis r;
  const _AdvFold({required this.r});

  @override
  State<_AdvFold> createState() => _AdvFoldState();
}

class _AdvFoldState extends State<_AdvFold> {
  bool _open = false;
  AdvancedResult? _adv;
  bool _computing = false;

  Future<void> _compute() async {
    final g = AppScope.of(context).graph;      // async 갭 전에 확보
    setState(() => _computing = true);
    await Future.delayed(const Duration(milliseconds: 30));   // 스피너 프레임 먼저
    final adv = g.advancedDiagnose(widget.r);
    if (mounted) setState(() { _adv = adv; _computing = false; });
  }

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    final g = AppScope.of(context).graph;

    Widget item(String title, String sub) => Container(
          margin: const EdgeInsets.only(left: 16),
          padding: const EdgeInsets.fromLTRB(0, 10, 16, 10),
          decoration: BoxDecoration(
              border: Border(top: BorderSide(color: ink.line, width: 0.5))),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: ink.i0)),
            const SizedBox(height: 2),
            Text(sub, style: TextStyle(fontSize: 12.5, color: ink.i3, height: 1.5)),
          ]),
        );

    return Panel(
      child: Column(children: [
        InkWell(
          onTap: () {
            setState(() => _open = !_open);
            if (_open && _adv == null && !_computing) _compute();
          },
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
            child: Row(children: [
              Container(
                width: 28, height: 28,
                decoration: BoxDecoration(color: ink.tint, borderRadius: BorderRadius.circular(7)),
                child: const Icon(Icons.layers_outlined, size: 17, color: Colors.white),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text('고급 진단 — 구간 사고·연속 폐쇄·이중 고장',
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
        if (_open && _computing)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 14),
            child: Row(children: [
              SizedBox(width: 14, height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2, color: ink.tint)),
              const SizedBox(width: 9),
              Text('수백 가지 고장 조합을 탐색하는 중…',
                  style: TextStyle(fontSize: 12.5, color: ink.i3)),
            ]),
          ),
        if (_open && _adv != null) ...[
          () {
            final adv = _adv!;
            final dead = adv.cuts.where((c) => c.$3).toList();
            return item('구간 사고 (선로 단절)',
                dead.isNotEmpty
                    ? '경로 구간 ${widget.r.stops.length - 1}개 중 ${dead.length}개는 끊기면 우회가 없습니다 — '
                      '${dead.take(2).map((c) => '${g.stations[c.$1].name}↔${g.stations[c.$2].name}').join(', ')}'
                      '${dead.length > 2 ? ' 외' : ''}'
                    : '어느 한 구간이 끊겨도 실질적 우회가 존재합니다');
          }(),
          item('연속 폐쇄 (2~4역 동시)',
              _adv!.windows.isNotEmpty
                  ? '같은 노선 ${_adv!.windows.first.$1.length}개 역 연속 폐쇄 조합 ${_adv!.windows.length}개가 '
                    '경로를 사실상 끊습니다 — 예: '
                    '${_adv!.windows.first.$1.map((si) => g.stations[si].name).join('·')}'
                  : '단독 생존 구간은 4역 연속 폐쇄에도 실질 단절이 없습니다'),
          item('이중 고장 (k=2)',
              _adv!.pairCandidates < 2
                  ? '단독 생존 중간역이 2개 미만이라 해당 없음'
                  : _adv!.pairs.isNotEmpty
                      ? '단독으론 버티는 역 ${_adv!.pairCandidates}개 중 ${_adv!.pairs.length}쌍은 함께 멈추면 '
                        '경로가 사라집니다 — 예: ${g.stations[_adv!.pairs.first.$1].name} + '
                        '${g.stations[_adv!.pairs.first.$2].name}'
                      : '단독 생존 역 ${_adv!.pairCandidates}개는 어떤 두 개가 함께 멈춰도 경로가 남습니다'),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
            child: Text(
                '실제 운행중단 공지는 역이 아니라 "A역–B역 구간" 형식입니다. 이 진단은 그 형식과 같은 단위로 계산합니다.',
                style: TextStyle(fontSize: 12.5, color: ink.i3, height: 1.5)),
          ),
        ],
      ]),
    );
  }
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
