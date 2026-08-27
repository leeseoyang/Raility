import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../graph.dart';
import '../state.dart';
import '../theme.dart';
import '../widgets.dart';

/// VWorld(국토교통부) 키. 발급받아 넣으면 국내 공공 지도로 바뀌고,
/// 비어 있거나 타일이 실패하면 CARTO 로 자동 전환된다.
/// 발급: https://www.vworld.kr → 오픈API → 인증키 발급
const vworldKey = String.fromEnvironment('VWORLD_KEY', defaultValue: '');

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});
  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  final _controller = MapController();
  String? _shownRegion;
  bool _vworldFailed = false;

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    final app = AppScope.of(context);
    final g = app.graph;
    final region = app.mapRegion;

    // 권역이 바뀌면 지도를 그 범위로 옮긴다.
    if (_shownRegion != region) {
      _shownRegion = region;
      WidgetsBinding.instance.addPostFrameCallback((_) => _fitRegion(g, region));
    }

    final members = <int>[];
    for (var i = 0; i < g.stations.length; i++) {
      if (g.stations[i].region == region) members.add(i);
    }
    final inSet = members.toSet();

    // 구간 취약성 조회표
    final segBy = <int, List<num>>{};
    for (final r in g.seg) {
      segBy[r[0].toInt()] = r;
    }

    final normal = <Polyline>[];
    final cuts = <Polyline>[];
    final transfers = <Polyline>[];
    var cutCount = 0;

    for (var ei = 0; ei < g.edges.length; ei++) {
      final e = g.edges[ei];
      final a = g.staOf[e[0]], b = g.staOf[e[1]];
      if (!inSet.contains(a) || !inSet.contains(b) || a == b) continue;
      final pts = [
        LatLng(g.stations[a].lat, g.stations[a].lon),
        LatLng(g.stations[b].lat, g.stations[b].lon),
      ];
      final sv = segBy[ei];
      final isCut = sv != null && sv[3] == 1;
      if (e[2] == 1) {
        transfers.add(Polyline(points: pts, color: ink.i5, strokeWidth: 1.4));
      } else if (isCut) {
        cutCount++;
        cuts.add(Polyline(points: pts, color: ink.risk3, strokeWidth: 4.2));
      } else {
        normal.add(Polyline(
            points: pts, color: hexColor(g.colorOf(g.nodes[e[0]].line)), strokeWidth: 3.2));
      }
    }

    var maxDemand = 1;
    for (final m in members) {
      if (g.stations[m].demand > maxDemand) maxDemand = g.stations[m].demand;
    }

    final markers = <Marker>[];
    for (final si in members) {
      final s = g.stations[si];
      List<num>? im;
      for (final n in s.nodes) {
        final v = g.impact[n];
        if (v != null && (im == null || v[0] > im[0])) im = v;
      }
      final separates = im != null && im[3] == 1;
      final r = 7.0 + (s.demand / maxDemand) * 9.0;
      markers.add(Marker(
        point: LatLng(s.lat, s.lon),
        width: r + 16,
        height: r + 16,
        child: GestureDetector(
          onTap: () => showStationSheet(context, si),
          child: Center(
            child: Container(
              width: r, height: r,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: separates ? ink.risk3 : ink.surface,
                border: Border.all(
                    color: separates
                        ? ink.risk3
                        : (s.isTransfer ? ink.i1 : hexColor(g.colorOf(s.lines.first))),
                    width: s.isTransfer ? 2.4 : 1.8),
              ),
            ),
          ),
        ),
      ));
    }

    final useVworld = vworldKey.isNotEmpty && !_vworldFailed;

    return Column(children: [
      const Eyebrow('취약구간 지도', padding: EdgeInsets.fromLTRB(16, 16, 16, 8)),
      SizedBox(
        height: 38,
        child: ListView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          children: [
            for (final r in g.regions)
              Padding(
                padding: const EdgeInsets.only(right: 6),
                child: _Chip(
                  label: r,
                  on: r == region,
                  onTap: () => setState(() => app.mapRegion = r),
                ),
              ),
          ],
        ),
      ),
      Padding(
        padding: const EdgeInsets.fromLTRB(18, 10, 18, 10),
        child: Row(children: [
          Text('역 ${members.length}개 · 단절 유발 구간 $cutCount개',
              style: TextStyle(fontSize: 12.5, color: ink.i3)),
          const Spacer(),
          Text(useVworld ? 'VWorld' : 'CARTO · OSM',
              style: TextStyle(fontSize: 10.5, color: ink.i4)),
        ]),
      ),
      Expanded(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: Container(
              decoration: BoxDecoration(border: Border.all(color: ink.line)),
              child: FlutterMap(
                mapController: _controller,
                options: MapOptions(
                  initialCenter: const LatLng(36.5, 127.5),
                  initialZoom: 10,
                  minZoom: 6,
                  maxZoom: 17,
                  interactionOptions: const InteractionOptions(
                      flags: InteractiveFlag.all & ~InteractiveFlag.rotate),
                ),
                children: [
                  if (useVworld)
                    TileLayer(
                      urlTemplate:
                          'https://api.vworld.kr/req/wmts/1.0.0/$vworldKey/Base/{z}/{y}/{x}.png',
                      userAgentPackageName: 'kr.raility.raility',
                      maxNativeZoom: 18,
                      errorTileCallback: (tile, error, stack) {
                        if (!_vworldFailed && mounted) {
                          // 키가 잘못됐거나 서비스가 막히면 한 번만 전환한다.
                          WidgetsBinding.instance.addPostFrameCallback(
                              (_) => setState(() => _vworldFailed = true));
                        }
                      },
                    )
                  else
                    TileLayer(
                      urlTemplate: Theme.of(context).brightness == Brightness.dark
                          ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
                          : 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
                      subdomains: const ['a', 'b', 'c', 'd'],
                      userAgentPackageName: 'kr.raility.raility',
                      maxNativeZoom: 19,
                      retinaMode: RetinaMode.isHighDensity(context),
                    ),
                  PolylineLayer(polylines: transfers),
                  PolylineLayer(polylines: normal),
                  PolylineLayer(polylines: cuts),
                  MarkerLayer(markers: markers),
                  RichAttributionWidget(
                    alignment: AttributionAlignment.bottomLeft,
                    attributions: [
                      TextSourceAttribution(useVworld ? 'VWorld' : 'OpenStreetMap · CARTO'),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
      Padding(
        padding: const EdgeInsets.fromLTRB(18, 10, 18, 12),
        child: Wrap(spacing: 14, runSpacing: 6, children: [
          _legend(ink, ink.risk3, '끊기면 망이 분리되는 구간·역'),
          _legend(ink, ink.surface, '환승역', border: ink.i1),
          _legend(ink, ink.i5, '환승 연결'),
        ]),
      ),
    ]);
  }

  Widget _legend(InkPalette ink, Color c, String label, {Color? border}) =>
      Row(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 9, height: 9,
          decoration: BoxDecoration(
              color: c, shape: BoxShape.circle,
              border: border != null ? Border.all(color: border, width: 2) : null),
        ),
        const SizedBox(width: 5),
        Text(label, style: TextStyle(fontSize: 11.5, color: ink.i3)),
      ]);

  void _fitRegion(RailGraph g, String region) {
    double? laMin, laMax, loMin, loMax;
    for (final s in g.stations) {
      if (s.region != region) continue;
      laMin = laMin == null ? s.lat : (s.lat < laMin ? s.lat : laMin);
      laMax = laMax == null ? s.lat : (s.lat > laMax ? s.lat : laMax);
      loMin = loMin == null ? s.lon : (s.lon < loMin ? s.lon : loMin);
      loMax = loMax == null ? s.lon : (s.lon > loMax ? s.lon : loMax);
    }
    if (laMin == null) return;
    _controller.fitCamera(CameraFit.bounds(
      bounds: LatLngBounds(LatLng(laMin, loMin!), LatLng(laMax!, loMax!)),
      padding: const EdgeInsets.all(28),
    ));
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final bool on;
  final VoidCallback onTap;
  const _Chip({required this.label, required this.on, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 7),
        decoration: BoxDecoration(
          color: on ? ink.i0 : Colors.transparent,
          border: Border.all(color: on ? ink.i0 : ink.lineStrong),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(label,
            style: TextStyle(
                fontSize: 12.5, fontWeight: FontWeight.w600, color: on ? ink.bg : ink.i3)),
      ),
    );
  }
}
