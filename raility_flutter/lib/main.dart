/// Raility · 도시철도 취약성 진단
///
/// 지도 앱은 "지금 다니는 길"을 알려준다.
/// 이 앱은 "그 길 위 어느 역 하나가 멈추면 돌아갈 수 있는지"를 계산한다.
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'graph.dart';
import 'theme.dart';
import 'screens/diagnose.dart';
import 'screens/map_screen.dart';
import 'screens/daejeon.dart';
import 'screens/data_screen.dart';
import 'state.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final raw = await rootBundle.loadString('assets/network.json');
  final graph = RailGraph.parse(raw);
  final app = AppState(graph);
  await app.restore();
  runApp(RailityApp(state: app));
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
    (Icons.tram_outlined, Icons.tram, '대전'),
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
