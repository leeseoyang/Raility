import 'package:flutter/material.dart';

import 'state.dart';
import 'theme.dart';

/// 섹션 제목 (작은 대문자 느낌의 라벨)
class Eyebrow extends StatelessWidget {
  final String text;
  final EdgeInsets? padding;
  const Eyebrow(this.text, {super.key, this.padding});

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    return Padding(
      padding: padding ?? const EdgeInsets.fromLTRB(16, 26, 16, 9),
      child: Text(text,
          style: TextStyle(
              fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1.0, color: ink.i4)),
    );
  }
}

/// 테두리 있는 카드 (그림자 대신 얇은 선을 쓴다)
class Panel extends StatelessWidget {
  final Widget child;
  final EdgeInsets? padding, margin;
  const Panel({super.key, required this.child, this.padding, this.margin});

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    return Container(
      margin: margin ?? const EdgeInsets.symmetric(horizontal: 16),
      padding: padding,
      decoration: BoxDecoration(
        color: ink.surface,
        border: Border.all(color: ink.line),
        borderRadius: BorderRadius.circular(16),
      ),
      clipBehavior: Clip.antiAlias,
      child: child,
    );
  }
}

/// 목록 한 줄
class RowTile extends StatelessWidget {
  final String? rank, title, subtitle, value, valueLabel;
  final Widget? trailing, subWidget;
  final VoidCallback? onTap;
  final bool divider;
  const RowTile({
    super.key, this.rank, this.title, this.subtitle, this.value,
    this.valueLabel, this.trailing, this.subWidget, this.onTap, this.divider = true,
  });

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    return InkWell(
      onTap: onTap,
      child: Container(
        decoration: divider ? BoxDecoration(border: Border(top: BorderSide(color: ink.line))) : null,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            if (rank != null) ...[
              SizedBox(
                width: 18,
                child: Text(rank!,
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: ink.i4)),
              ),
              const SizedBox(width: 12),
            ],
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (title != null)
                    Text(title!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                            fontSize: 14.5, fontWeight: FontWeight.w600, color: ink.i0, letterSpacing: -0.2)),
                  if (subtitle != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 1),
                      child: Text(subtitle!, style: TextStyle(fontSize: 12, color: ink.i4)),
                    ),
                  ?subWidget,
                ],
              ),
            ),
            if (value != null) ...[
              const SizedBox(width: 10),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(value!,
                      style: TextStyle(
                          fontSize: 14, fontWeight: FontWeight.w700, color: ink.i1,
                          fontFeatures: const [FontFeature.tabularFigures()])),
                  if (valueLabel != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 1),
                      child: Text(valueLabel!,
                          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: ink.i4)),
                    ),
                ],
              ),
            ],
            if (trailing != null) ...[const SizedBox(width: 8), trailing!],
          ],
        ),
      ),
    );
  }
}

/// 가로 막대 게이지
class Gauge extends StatelessWidget {
  final double value; // 0..1
  final Color color;
  const Gauge({super.key, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: 7),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(3),
        child: LinearProgressIndicator(
          value: value.clamp(0.03, 1.0),
          minHeight: 5,
          backgroundColor: ink.i6,
          valueColor: AlwaysStoppedAnimation(color),
        ),
      ),
    );
  }
}

/// 본문 보조 설명
class Note extends StatelessWidget {
  final String text;
  final EdgeInsets? padding;
  const Note(this.text, {super.key, this.padding});

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    return Padding(
      padding: padding ?? const EdgeInsets.fromLTRB(18, 12, 18, 0),
      child: Text(text, style: TextStyle(fontSize: 12.5, color: ink.i3, height: 1.6)),
    );
  }
}

/// 역 상세 바텀시트
Future<void> showStationSheet(BuildContext context, int si) {
  final app = AppScope.of(context);
  final g = app.graph;
  final s = g.stations[si];
  final ink = Palette.of(context);

  List<num>? best;
  for (final n in s.nodes) {
    final im = g.impact[n];
    if (im != null && (best == null || im[0] > best[0])) best = im;
  }

  return showModalBottomSheet(
    context: context,
    backgroundColor: ink.surface,
    showDragHandle: true,
    shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18))),
    builder: (ctx) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(s.name,
                style: TextStyle(
                    fontSize: 24, fontWeight: FontWeight.w800, color: ink.i0, letterSpacing: -0.7)),
            const SizedBox(height: 5),
            Wrap(spacing: 6, children: [
              Text('${s.region} ·', style: TextStyle(fontSize: 13, color: ink.i3)),
              ...s.lines.map((l) => Text(l,
                  style: TextStyle(
                      fontSize: 13, fontWeight: FontWeight.w600, color: hexColor(g.colorOf(l))))),
            ]),
            const SizedBox(height: 16),
            _kv(ink, '일평균 승하차', '${comma(s.demand)}명'),
            _kv(ink, '연결 노선', '${s.lines.length}개'),
            if (best != null) ...[
              _kv(ink, '제거 시 효율 저하', '${best[0].toStringAsFixed(2)}%'),
              _kv(ink, '제거 시 고립 역 수', best[2] > 0 ? '${best[2]}개' : '없음'),
            ],
            if (s.addr.isNotEmpty) _kv(ink, '주소', s.addr),
          ],
        ),
      ),
    ),
  );
}

Widget _kv(InkPalette ink, String k, String v) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(k, style: TextStyle(fontSize: 13.5, color: ink.i4, fontWeight: FontWeight.w600)),
        const SizedBox(width: 16),
        Expanded(
          child: Text(v,
              textAlign: TextAlign.right,
              style: TextStyle(fontSize: 13.5, color: ink.i1, fontWeight: FontWeight.w600)),
        ),
      ]),
    );
