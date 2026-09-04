/// Raility · 도시철도 취약성 진단
///
/// 지도 앱은 "지금 다니는 길"을 알려준다.
/// 이 앱은 "그 길 위 어느 역 하나가 멈추면 돌아갈 수 있는지"를 계산한다.
library;

import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'graph.dart';
import 'theme.dart';
import 'screens/diagnose.dart';
import 'screens/map_screen.dart';
import 'screens/daejeon.dart';
import 'screens/data_screen.dart';
import 'state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // 번들 파싱(400KB JSON + 그래프 구축)을 main 에서 기다리면 그동안 네이티브
  // 스플래시에 머문다. 첫 프레임을 즉시 띄우고 파싱은 isolate 에서 한다.
  runApp(const _Boot());
}

/// isolate 진입점. 클로저가 아니라 톱레벨 함수여야 State 캡처가 없다.
RailGraph _parseGraph(Uint8List bytes) => RailGraph.parse(utf8.decode(bytes));

/// 부팅 화면 — 그래프가 준비되면 본 앱으로 교체된다.
class _Boot extends StatefulWidget {
  const _Boot();
  @override
  State<_Boot> createState() => _BootState();
}

class _BootState extends State<_Boot> {
  AppState? _app;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final bytes = await rootBundle.load('assets/network.json');
    // UTF-8 디코드와 그래프 구축 전부를 isolate 로. RailGraph 는 클로저·네이티브
    // 핸들이 없는 순수 자료구조라 isolate 경계를 그대로 건널 수 있다.
    // 주의: Isolate.run(() => ...) 클로저는 컨텍스트 체인을 타고 State(this)까지
    // 캡처해 릴리스에서 전송이 거부된다 — 반드시 톱레벨 함수 + compute 로 넘긴다.
    final graph = await compute(_parseGraph, bytes.buffer.asUint8List());
    final app = AppState(graph);
    await app.restore();
    if (mounted) setState(() => _app = app);
  }

  @override
  Widget build(BuildContext context) {
    final app = _app;
    if (app != null) return RailityApp(state: app);
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      home: Builder(builder: (context) {
        final dark = MediaQuery.platformBrightnessOf(context) == Brightness.dark;
        final ink = dark ? InkPalette.dark : InkPalette.light;
        return Scaffold(
          backgroundColor: ink.bg,
          body: Center(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Text('Raility',
                  style: TextStyle(
                      fontSize: 28, fontWeight: FontWeight.w700,
                      color: ink.i0, letterSpacing: -0.8)),
              const SizedBox(height: 6),
              Text('도시철도 취약성 진단',
                  style: TextStyle(fontSize: 13, color: ink.i3)),
              const SizedBox(height: 22),
              SizedBox(
                width: 20, height: 20,
                child: CircularProgressIndicator(strokeWidth: 2.4, color: ink.tint),
              ),
            ]),
          ),
        );
      }),
    );
  }
}

class RailityApp extends StatelessWidget {
  final AppState state;
  const RailityApp({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Raility',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      home: AppScope(state: state, child: const _Home()),
    );
  }
}

class _Home extends StatefulWidget {
  const _Home();
  @override
  State<_Home> createState() => _HomeState();
}

class _HomeState extends State<_Home> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final dark = MediaQuery.platformBrightnessOf(context) == Brightness.dark;
    final ink = dark ? InkPalette.dark : InkPalette.light;
    final app = AppScope.of(context);

    final pages = [
      const DiagnoseScreen(),
      const MapScreen(),
      const DaejeonScreen(),
      const DataScreen(),
    ];

    return Palette(
      ink: ink,
      child: AnnotatedRegion<SystemUiOverlayStyle>(
        value: dark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark,
        child: Scaffold(
          backgroundColor: ink.bg,
          appBar: _AppBar(showRegion: _tab == 0),
          body: IndexedStack(index: _tab, children: pages),
          bottomNavigationBar: _TabBar(
            index: _tab,
            onTap: (i) {
              // 지도 탭으로 갈 때는 방금 진단한 권역을 먼저 보여준다.
              if (i == 1 && app.from != null) {
                final r = app.graph.stations[app.from!].region;
                if (app.graph.regions.contains(r)) app.mapRegion = r;
              }
              setState(() => _tab = i);
            },
          ),
        ),
      ),
    );
  }
}

class _AppBar extends StatelessWidget implements PreferredSizeWidget {
  final bool showRegion;
  const _AppBar({required this.showRegion});

  @override
  Size get preferredSize => const Size.fromHeight(52);

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    final app = AppScope.of(context);
    return Container(
      decoration: BoxDecoration(
        color: ink.bg,
        border: Border(bottom: BorderSide(color: ink.line)),
      ),
      child: SafeArea(
        bottom: false,
        child: SizedBox(
          height: 51,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              children: [
                Text('Raility',
                    style: TextStyle(
                        fontSize: 17, fontWeight: FontWeight.w600, color: ink.i0, letterSpacing: -0.4)),
                const SizedBox(width: 9),
                Text('도시철도 취약성 진단',
                    style: TextStyle(fontSize: 12, color: ink.i3, height: 1)),
                const Spacer(),
                if (showRegion)
                  _RegionChip(
                    label: app.region,
                    onTap: () => _pickRegion(context, app),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// 검색 기준 권역을 리스트에서 고른다. 권역별 역 수를 함께 보여준다.
Future<void> _pickRegion(BuildContext context, AppState app) {
  final ink = Palette.of(context);
  final g = app.graph;
  final counts = <String, int>{};
  for (final s in g.stations) {
    counts[s.region] = (counts[s.region] ?? 0) + 1;
  }

  return showModalBottomSheet(
    context: context,
    backgroundColor: ink.surface,
    showDragHandle: true,
    shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(14))),
    builder: (ctx) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
            child: Text('검색 기준 권역',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: ink.i0)),
          ),
          for (final r in g.regions)
            InkWell(
              onTap: () {
                app.region = r;
                Navigator.pop(ctx);
              },
              child: Container(
                decoration: r == g.regions.first
                    ? null
                    : BoxDecoration(
                        border: Border(top: BorderSide(color: ink.line, width: 0.5))),
                margin: r == g.regions.first ? null : const EdgeInsets.only(left: 16),
                padding: EdgeInsets.fromLTRB(r == g.regions.first ? 16 : 0, 12, 16, 12),
                child: Row(children: [
                  Expanded(
                    child: Text(r,
                        style: TextStyle(
                            fontSize: 16,
                            fontWeight: r == app.region ? FontWeight.w600 : FontWeight.w400,
                            color: ink.i0)),
                  ),
                  Text('${counts[r] ?? 0}역',
                      style: TextStyle(fontSize: 13, color: ink.i3)),
                  if (r == app.region) ...[
                    const SizedBox(width: 10),
                    Icon(Icons.check, size: 19, color: ink.tint),
                  ],
                ]),
              ),
            ),
          const SizedBox(height: 6),
        ],
      ),
    ),
  );
}

class _RegionChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _RegionChip({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 5),
        decoration: BoxDecoration(
          color: ink.tintBg,
          borderRadius: BorderRadius.circular(999),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.place_outlined, size: 13, color: ink.tint),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: ink.tint)),
        ]),
      ),
    );
  }
}

class _TabBar extends StatelessWidget {
  final int index;
  final ValueChanged<int> onTap;
  const _TabBar({required this.index, required this.onTap});

  static const _items = [
    (Icons.monitor_heart_outlined, Icons.monitor_heart, '진단'),
    (Icons.map_outlined, Icons.map, '지도'),
    (Icons.bar_chart_outlined, Icons.bar_chart, '권역'),
    (Icons.storage_outlined, Icons.storage, '데이터'),
  ];

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    return Container(
      decoration: BoxDecoration(
        color: ink.surface,
        border: Border(top: BorderSide(color: ink.line)),
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 56,
          child: Row(
            children: List.generate(_items.length, (i) {
              final on = i == index;
              final (o, f, label) = _items[i];
              return Expanded(
                child: InkWell(
                  onTap: () => onTap(i),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(on ? f : o, size: 22, color: on ? ink.tint : ink.i4),
                      const SizedBox(height: 3),
                      Text(label,
                          style: TextStyle(
                              fontSize: 10.5,
                              fontWeight: on ? FontWeight.w600 : FontWeight.w500,
                              color: on ? ink.tint : ink.i4)),
                    ],
                  ),
                ),
              );
            }),
          ),
        ),
      ),
    );
  }
}
