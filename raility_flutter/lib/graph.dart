/// Raility — 그래프 · 최단경로 · 단일고장점(SPOF) · 절점
///
/// 웹판 assets/graph.js 를 그대로 옮긴 것이다. 판정 규칙을 바꾸면 두 쪽이 어긋나므로
/// 변경 시 raility_app/test_graph.js 와 test/graph_test.dart 를 함께 손봐야 한다.
library;

import 'dart:convert';
import 'dart:math' as math;
import 'dart:typed_data';

class Station {
  final int index;
  String name;
  String short;
  final String region;
  final List<int> nodes = [];
  final List<String> lines = [];
  final List<String> variants = [];
  int demand = 0;
  double lat = 0, lon = 0;
  String addr;

  Station(this.index, this.region, this.addr) : name = '', short = '';

  bool get isTransfer => lines.length > 1;
}

class GEdge {
  final int to, weight, type, ei;
  const GEdge(this.to, this.weight, this.type, this.ei);
}

class NodeInfo {
  final String fullName, shortName, line, op, region, addr;
  final double lat, lon;
  final int demand, transfer;

  /// 승강장 접근성 [위험도, 안전발판없음, 승강장연결안됨, 스크린도어없음, 최대역층].
  /// null 은 '자료 없음' — '장벽 없음'(전부 0)과 다르므로 0 으로 채우지 않는다.
  final List<int>? ac;

  const NodeInfo(this.fullName, this.shortName, this.line, this.op, this.region,
      this.addr, this.lat, this.lon, this.demand, this.transfer, this.ac);
}

class PathResult {
  final double time;
  final List<int> path;
  const PathResult(this.time, this.path);
}

/// 경로 위의 한 정차역
class Stop {
  final int station;
  final List<int> nodes;
  String? rideLine;
  bool transferHere = false;
  bool segTransfer = false;
  String? fromLine, toLine;
  bool spof = false;
  bool practical = false;  // 실질적 단절 (경로 소멸 또는 +30분/2배 초과 우회)
  bool walkHere = false;   // 다음 역까지 도보 이동
  int walkM = 0;
  double delta = 0;
  Stop(this.station, this.nodes);
}

class Diagnosis {
  final bool ok;
  final PathResult? base;
  final List<Stop> stops, mids, spof, practical, detour;
  final double maxDelta, ratio;
  final String grade;
  final int transfers;
  final List<String> lines;

  const Diagnosis({
    required this.ok,
    this.base,
    this.stops = const [],
    this.mids = const [],
    this.spof = const [],
    this.practical = const [],
    this.detour = const [],
    this.maxDelta = 0,
    this.ratio = 0,
    this.grade = 'A',
    this.transfers = 0,
    this.lines = const [],
  });
}

class RegionFragility {
  final String region;
  final int total, cuts;
  final double ratio;
  final List<int> stations;
  const RegionFragility(this.region, this.total, this.cuts, this.ratio, this.stations);
}

/// 빠른환승 한 건 — 내리는 열차의 몇 번째 칸(car)·문(door)이 환승 통로와 가장 가까운가
class FastTransfer {
  final String dir; // 탄 열차의 종착 방면
  final int car, door;
  const FastTransfer(this.dir, this.car, this.door);
}

class FastTransferResult {
  final bool resolved; // 진행 방향이 판정돼 단일 안내인가
  final List<FastTransfer> list;
  const FastTransferResult(this.resolved, this.list);
}

/// 우선순위 큐 (최소 힙)
class _MinHeap {
  final List<double> _k = [];
  final List<int> _v = [];

  bool get isEmpty => _k.isEmpty;

  void push(double key, int val) {
    _k.add(key);
    _v.add(val);
    var i = _k.length - 1;
    while (i > 0) {
      final p = (i - 1) >> 1;
      if (_k[p] <= _k[i]) break;
      _swap(p, i);
      i = p;
    }
  }

  /// 최소 키의 값을 꺼낸다. 키는 [lastKey] 로 확인한다.
  double lastKey = 0;
  int pop() {
    final topK = _k[0], topV = _v[0];
    final lk = _k.removeLast(), lv = _v.removeLast();
    if (_k.isNotEmpty) {
      _k[0] = lk;
      _v[0] = lv;
      var i = 0;
      final n = _k.length;
      while (true) {
        final l = 2 * i + 1, r = l + 1;
        var m = i;
        if (l < n && _k[l] < _k[m]) m = l;
        if (r < n && _k[r] < _k[m]) m = r;
        if (m == i) break;
        _swap(m, i);
        i = m;
      }
    }
    lastKey = topK;
    return topV;
  }

  void _swap(int a, int b) {
    final tk = _k[a]; _k[a] = _k[b]; _k[b] = tk;
    final tv = _v[a]; _v[a] = _v[b]; _v[b] = tv;
  }
}

class RailGraph {
  late final List<NodeInfo> nodes;
  late final List<List<int>> edges;          // [a, b, type, sec, dist, freq]
  late final List<List<GEdge>> adj;
  late final List<Station> stations;
  late final Int32List staOf;
  late final List<List<int>> staAdj;
  late final Map<String, String> colors;
  late final Map<int, List<num>> impact;     // nodeIndex -> [eff, paxEff, lccDrop, separates]
  late final List<List<num>> seg;            // [edgeIndex, eff, demandEff, cut, size]
  late final int transferSec;

  /// "권역|역명" -> [[탈때노선 후보, 갈아탈노선 후보, 종착방면, 칸, 문], ...]
  late final Map<String, List<List<dynamic>>> ft;

  /// 노선 -> 기대 대기시간(초). 운행횟수에서 역산한 배차간격의 절반.
  late final Map<String, int> lineWait;

  // 다익스트라 작업 버퍼 (재할당 비용 회피)
  late final Float64List _dist;
  late final Int32List _prev;
  late final Uint8List _blocked;

  static const int mergeRadiusM = 1200;

  RailGraph.fromJson(Map<String, dynamic> j) {
    nodes = (j['nodes'] as List)
        .map((n) => NodeInfo(
              n['fn'] as String,
              n['n'] as String,
              n['l'] as String,
              n['o'] as String,
              n['r'] as String,
              (n['ad'] ?? '') as String,
              (n['la'] as num).toDouble(),
              (n['lo'] as num).toDouble(),
              (n['d'] as num).toInt(),
              (n['x'] as num).toInt(),
              (n['ac'] as List?)?.map((v) => (v as num).toInt()).toList(),
            ))
        .toList(growable: false);

    edges = (j['edges'] as List)
        .map((e) => (e as List).map((v) => (v as num).toInt()).toList())
        .toList();

    colors = (j['colors'] as Map).map((k, v) => MapEntry(k as String, v as String));
    transferSec = (j['transferSec'] as num?)?.toInt() ?? 210;

    impact = {};
    (j['impact'] as Map?)?.forEach((k, v) {
      impact[int.parse(k as String)] = (v as List).map((x) => x as num).toList();
    });

    seg = ((j['seg'] as List?) ?? [])
        .map((r) => (r as List).map((x) => x as num).toList())
        .toList();

    ft = {};
    (j['ft'] as Map?)?.forEach((k, v) {
      ft[k as String] = (v as List).map((r) => r as List<dynamic>).toList();
    });

    lineWait = {};
    (j['lineWait'] as Map?)?.forEach((k, v) {
      lineWait[k as String] = (v as num).toInt();
    });

    _buildAdjacency();
    _buildStations();
    _buildStationAdjacency();

    _dist = Float64List(nodes.length);
    _prev = Int32List(nodes.length);
    _blocked = Uint8List(stations.length);
  }

  static RailGraph parse(String jsonText) =>
      RailGraph.fromJson(json.decode(jsonText) as Map<String, dynamic>);

  void _buildAdjacency() {
    // 배차간격 반영: 환승(1)·도보(2) 엣지로 노선 ℓ에 '올라탈' 때 그 노선의
    // 기대 대기시간을 얹는다. 방향에 따라 도착 노선이 달라 가중치가 방향 의존.
    int boardWait(int nodeIdx) => lineWait[nodes[nodeIdx].line] ?? 0;
    adj = List.generate(nodes.length, (_) => <GEdge>[]);
    for (var ei = 0; ei < edges.length; ei++) {
      final e = edges[ei];
      var wa = e[3], wb = e[3];
      if (e[2] != 0) {
        wa += boardWait(e[1]);
        wb += boardWait(e[0]);
      }
      adj[e[0]].add(GEdge(e[1], wa, e[2], ei));
      adj[e[1]].add(GEdge(e[0], wb, e[2], ei));
    }
  }

  static String _normName(String n) =>
      n.length > 2 && n.endsWith('역') ? n.substring(0, n.length - 1) : n;

  static double _haversine(double la1, double lo1, double la2, double lo2) {
    const r = 6371000.0, t = math.pi / 180;
    final dla = (la2 - la1) * t, dlo = (lo2 - lo1) * t;
    final a = math.sin(dla / 2) * math.sin(dla / 2) +
        math.cos(la1 * t) * math.cos(la2 * t) * math.sin(dlo / 2) * math.sin(dlo / 2);
    return 2 * r * math.asin(math.min(1.0, math.sqrt(a)));
  }

  /// 승강장 노드를 실제 "역" 단위로 묶는다.
  ///
  /// 원본 공공데이터는 같은 역을 "신도림"(2호선)과 "신도림역"(경부선)처럼 다르게 적는다.
  /// 그대로 두면 한 역이 둘로 쪼개져, 실제로는 불가능한 *닫힌 역에서의 환승*을 우회로로
  /// 인정해 취약성을 실제보다 낮게 보고한다. 이름을 정규화해 병합하되 좌표 조건을 함께 건다.
  void _buildStations() {
    // 1단계: 표기 그대로 묶기
    final rawMap = <String, _Raw>{};
    final raws = <_Raw>[];
    for (var i = 0; i < nodes.length; i++) {
      final n = nodes[i];
      final key = '${n.region}|${n.fullName}';
      var r = rawMap[key];
      if (r == null) {
        r = _Raw(n.region, n.addr);
        rawMap[key] = r;
        raws.add(r);
      }
      r.nodes.add(i);
      r.names[n.fullName] = (r.names[n.fullName] ?? 0) + 1;
      if (!r.lines.contains(n.line)) r.lines.add(n.line);
      r.demand += n.demand;
    }
    for (final r in raws) {
      var la = 0.0, lo = 0.0;
      for (final i in r.nodes) {
        la += nodes[i].lat;
        lo += nodes[i].lon;
      }
      r.lat = la / r.nodes.length;
      r.lon = lo / r.nodes.length;
    }

    // 2단계: 정규화 이름이 같고 가까우면 union-find 로 합치기
    final parent = List<int>.generate(raws.length, (i) => i);
    int find(int x) {
      while (parent[x] != x) {
        parent[x] = parent[parent[x]];
        x = parent[x];
      }
      return x;
    }

    void union(int a, int b) {
      a = find(a);
      b = find(b);
      if (a != b) parent[b] = a;
    }

    final buckets = <String, List<int>>{};
    for (var i = 0; i < raws.length; i++) {
      final k = '${raws[i].region}|${_normName(raws[i].names.keys.first)}';
      buckets.putIfAbsent(k, () => []).add(i);
    }
    for (final g in buckets.values) {
      for (var a = 0; a < g.length; a++) {
        for (var b = a + 1; b < g.length; b++) {
          final A = raws[g[a]], B = raws[g[b]];
          if (_haversine(A.lat, A.lon, B.lat, B.lon) <= mergeRadiusM) union(g[a], g[b]);
        }
      }
    }

    final byRoot = <int, Station>{};
    stations = [];
    for (var i = 0; i < raws.length; i++) {
      final r = raws[i];
      final root = find(i);
      var s = byRoot[root];
      if (s == null) {
        s = Station(stations.length, r.region, r.addr);
        byRoot[root] = s;
        stations.add(s);
      }
      r.names.forEach((nm, c) {
        if (!s!.variants.contains(nm)) s.variants.add(nm);
        s.variants.sort();
      });
      s.nodes.addAll(r.nodes);
      for (final l in r.lines) {
        if (!s.lines.contains(l)) s.lines.add(l);
      }
      s.demand += r.demand;
    }

    // 표시 이름: 노드가 많은 표기를 쓰고, 같으면 짧은(접미사 없는) 표기를 쓴다.
    final counts = <Station, Map<String, int>>{};
    for (var i = 0; i < raws.length; i++) {
      final s = byRoot[find(i)]!;
      final m = counts.putIfAbsent(s, () => {});
      raws[i].names.forEach((nm, c) => m[nm] = (m[nm] ?? 0) + c);
    }

    staOf = Int32List(nodes.length);
    for (var si = 0; si < stations.length; si++) {
      final s = stations[si];
      final m = counts[s]!;
      final vs = m.keys.toList()
        ..sort((a, b) {
          final d = m[b]! - m[a]!;
          return d != 0 ? d : a.length - b.length;
        });
      s.name = vs.first;
      s.short = _normName(s.name);
      s.variants
        ..clear()
        ..addAll(vs);

      var la = 0.0, lo = 0.0;
      for (final i in s.nodes) {
        la += nodes[i].lat;
        lo += nodes[i].lon;
        staOf[i] = si;
      }
      s.lat = la / s.nodes.length;
      s.lon = lo / s.nodes.length;
    }
  }

  void _buildStationAdjacency() {
    staAdj = List.generate(stations.length, (_) => <int>[]);
    final seen = <int>{};
    for (final e in edges) {
      if (e[2] == 2) continue; // 도보 엣지는 경로 탐색 전용 — 철도망 위상에는 넣지 않는다
      final a = staOf[e[0]], b = staOf[e[1]];
      if (a == b) continue; // 같은 역 안의 환승은 위상에 영향 없음
      final k = a < b ? a * stations.length + b : b * stations.length + a;
      if (!seen.add(k)) continue;
      staAdj[a].add(b);
      staAdj[b].add(a);
    }
  }

  GEdge? _edgeBetween(int a, int b) {
    for (final e in adj[a]) {
      if (e.to == b) return e;
    }
    return null;
  }

  /// 역 [src] → 역 [dst] 최단경로. [block] 에 든 역은 통과 불가.
  PathResult? shortest(int src, int dst, {List<int>? block}) {
    if (src == dst) return PathResult(0, [stations[src].nodes.first]);

    for (var i = 0; i < nodes.length; i++) {
      _dist[i] = double.infinity;
      _prev[i] = -1;
    }

    final hasBlock = block != null && block.isNotEmpty;
    if (hasBlock) {
      _blocked.fillRange(0, _blocked.length, 0);
      for (final b in block) {
        if (b == src || b == dst) return null; // 출발/도착역 자체가 막히면 무의미
        _blocked[b] = 1;
      }
    }

    final h = _MinHeap();
    for (final i in stations[src].nodes) {
      _dist[i] = 0;
      h.push(0, i);
    }
    final dstNodes = stations[dst].nodes.toSet();

    var end = -1;
    while (!h.isEmpty) {
      final u = h.pop();
      final d = h.lastKey;
      if (d > _dist[u]) continue;
      if (dstNodes.contains(u)) {
        end = u;
        break;
      }
      for (final e in adj[u]) {
        if (hasBlock && _blocked[staOf[e.to]] == 1) continue;
        final nd = d + e.weight;
        if (nd < _dist[e.to]) {
          _dist[e.to] = nd;
          _prev[e.to] = u;
          h.push(nd, e.to);
        }
      }
    }
    if (end < 0) return null;

    final path = <int>[];
    var cur = end;
    while (cur >= 0) {
      path.add(cur);
      cur = _prev[cur];
    }
    return PathResult(_dist[end], path.reversed.toList());
  }

  /// 경로 노드열 → 역 단위 정차 목록.
  ///
  /// 원본 인접 엣지는 노선 라벨이 어긋난 경우가 있다(같은 이름의 다른 노선 노드에 인접이 붙는다).
  /// 역 단위 위상은 옳으므로, 타는 노선은 노드 라벨 대신 "양쪽 역이 공유하는 노선"에서 고른다.
  /// 이렇게 하면 직결 운행은 환승으로 세지 않고 실제 갈아타는 지점만 잡힌다.
  List<Stop> toStops(List<int> path) {
    final stops = <Stop>[];
    for (final n in path) {
      final si = staOf[n];
      if (stops.isNotEmpty && stops.last.station == si) {
        stops.last.nodes.add(n);
        continue;
      }
      stops.add(Stop(si, [n]));
    }

    String? prevLine;
    for (var k = 0; k + 1 < stops.length; k++) {
      final a = stops[k], b = stops[k + 1];
      final e = _edgeBetween(a.nodes.last, b.nodes.first);

      if (e != null && e.type == 1) {
        a.segTransfer = true;
        a.transferHere = true;
        a.fromLine = prevLine;
        if (k + 2 < stops.length) {
          final lb = stations[b.station].lines, lc = stations[stops[k + 2].station].lines;
          final sh = lb.where(lc.contains).toList();
          a.toLine = sh.isNotEmpty ? sh.first : nodes[b.nodes.first].line;
        } else {
          a.toLine = nodes[b.nodes.first].line;
        }
        prevLine = a.toLine;
      } else {
        if (e != null && e.type == 2) {  // 도보 환승 구간
          a.walkHere = true;
          a.walkM = edges[e.ei][4];
        }
        final la = stations[a.station].lines, lb = stations[b.station].lines;
        final shared = la.where(lb.contains).toList();
        final line = shared.isNotEmpty
            ? (prevLine != null && shared.contains(prevLine) ? prevLine : shared.first)
            : nodes[b.nodes.first].line;
        a.rideLine = line;
        if (prevLine != null && line != prevLine) {
          a.transferHere = true;
          a.fromLine = prevLine;
          a.toLine = line;
        }
        prevLine = line;
      }
    }
    if (stops.isNotEmpty) {
      stops.last.rideLine = prevLine ?? nodes[stops.last.nodes.first].line;
    }
    for (final s in stops) {
      s.rideLine ??= nodes[s.nodes.first].line;
    }
    return stops;
  }

  /// 실질적 단절 상한(초). 우회가 이보다 오래 걸리면 사실상 못 가는 것으로 본다.
  static const practicalCapS = 1800.0;

  /// 경로 위 중간역을 하나씩 제거해 우회 가능 여부를 판정한다.
  /// (판정 규칙은 웹판 graph.js diagnose 와 동일해야 한다)
  Diagnosis diagnose(int src, int dst) {
    final base = shortest(src, dst);
    if (base == null) return const Diagnosis(ok: false);

    final stops = toStops(base.path);
    final mids = stops.length > 2 ? stops.sublist(1, stops.length - 1) : <Stop>[];
    final spof = <Stop>[], practical = <Stop>[], detour = <Stop>[];
    var maxDelta = 0.0;

    for (final st in mids) {
      final alt = shortest(src, dst, block: [st.station]);
      if (alt == null) {
        st.spof = true;
        st.practical = true;
        spof.add(st);
        practical.add(st);
        continue;
      }
      st.delta = alt.time - base.time;
      // 실질적 단절: 경로가 남아도 +30분 이상이거나 원 소요시간의 2배를 넘으면
      // 통근자에겐 단절과 같다.
      if (st.delta > practicalCapS || st.delta > base.time) {
        st.practical = true;
        practical.add(st);
      }
      if (st.delta > 60) {
        detour.add(st);
        if (st.delta > maxDelta) maxDelta = st.delta;
      }
    }

    // 등급은 '실질적 단절' 비율. 짧은 경로의 요동은 라플라스 평활(α=1)로 억제.
    final ratio = practical.isEmpty
        ? 0.0
        : (practical.length + 1) / (mids.length + 2);
    final grade = ratio == 0
        ? 'A'
        : ratio <= 0.15
            ? 'B'
            : ratio <= 0.4
                ? 'C'
                : ratio <= 0.75
                    ? 'D'
                    : 'E';

    final lines = <String>[];
    for (final s in stops) {
      final l = s.rideLine;
      if (l != null && !lines.contains(l)) lines.add(l);
    }

    return Diagnosis(
      ok: true,
      base: base,
      stops: stops,
      mids: mids,
      spof: spof,
      practical: practical,
      detour: detour,
      maxDelta: maxDelta,
      ratio: ratio,
      grade: grade,
      transfers: stops.where((s) => s.transferHere).length,
      lines: lines,
    );
  }

  /// 절점(articulation point): 제거하면 그래프가 분리되는 정점. Tarjan 반복 구현.
  List<int> articulationPoints(List<int> members) {
    final inSet = Uint8List(stations.length);
    for (final m in members) {
      inSet[m] = 1;
    }
    final disc = Int32List(stations.length)..fillRange(0, stations.length, -1);
    final low = Int32List(stations.length);
    final parent = Int32List(stations.length)..fillRange(0, stations.length, -1);
    final isArt = Uint8List(stations.length);
    var timer = 0;

    for (final start in members) {
      if (disc[start] != -1) continue;
      var rootChildren = 0;
      disc[start] = low[start] = timer++;
      final stack = <List<int>>[
        [start, 0]
      ];

      while (stack.isNotEmpty) {
        final top = stack.last;
        final u = top[0];
        if (top[1] < staAdj[u].length) {
          final v = staAdj[u][top[1]++];
          if (inSet[v] == 0) continue;
          if (disc[v] == -1) {
            parent[v] = u;
            if (u == start) rootChildren++;
            disc[v] = low[v] = timer++;
            stack.add([v, 0]);
          } else if (v != parent[u]) {
            if (disc[v] < low[u]) low[u] = disc[v];
          }
        } else {
          stack.removeLast();
          final p = parent[u];
          if (p != -1) {
            if (low[u] < low[p]) low[p] = low[u];
            if (p != start && low[u] >= disc[p]) isArt[p] = 1;
          }
        }
      }
      if (rootChildren > 1) isArt[start] = 1;
    }
    return members.where((i) => isArt[i] == 1).toList();
  }

  /// 권역별 절점 비율 — "제거하면 망이 쪼개지는 역"의 비중
  RegionFragility? regionFragility(String region) {
    final members = <int>[];
    for (var i = 0; i < stations.length; i++) {
      if (stations[i].region == region) members.add(i);
    }
    if (members.length < 5) return null;
    final arts = articulationPoints(members);
    return RegionFragility(region, members.length, arts.length, arts.length / members.length, arts);
  }

  /// 빠른환승 이름 정규화 (괄호·공백 제거, 끝의 '역' 절단 — 번들 생성기와 동일)
  static String _pnorm(String s) {
    var t = s.replaceAll(RegExp(r'\(.*?\)'), '').replaceAll(RegExp(r'\s+'), '');
    return t.length > 1 && t.endsWith('역') ? t.substring(0, t.length - 1) : t;
  }

  /// 노선 계통 집합으로 제한한 역 단위 BFS 홉수. 코레일 1호선처럼 한 계통이
  /// 여러 그래프 노선(경부·경인·경원·장항)으로 갈라져 있어 단일 노선으로는
  /// 종착역에 닿지 못하므로 집합으로 걷는다.
  Map<int, int> _bfsLineHops(int start, Set<String> lineSet) {
    bool onLine(int si) => stations[si].lines.any(lineSet.contains);
    final dist = <int, int>{start: 0};
    final q = <int>[start];
    var head = 0;
    while (head < q.length) {
      final u = q[head++];
      for (final v in staAdj[u]) {
        if (dist.containsKey(v) || !onLine(v)) continue;
        dist[v] = dist[u]! + 1;
        q.add(v);
      }
    }
    return dist;
  }

  /// 경로 [r] 의 [i]번째 정차역이 환승이면 빠른환승(칸-문) 안내를 돌려준다.
  ///
  /// 같은 환승쌍에 상·하행 두 레코드가 있으므로 진행 방향을 판정한다:
  /// 직전 역 P 에서 탄 열차는 S 를 지나 P 반대쪽으로 가므로, 그 열차의 종착역 T 는
  /// 같은 계통 부분그래프에서 dP[T] == dP[S] + dS[T] 를 만족한다.
  FastTransferResult? fastTransferAt(Diagnosis r, int i) {
    final st = r.stops[i];
    if (!st.transferHere || st.fromLine == null || st.toLine == null) return null;
    final s = stations[st.station];
    final all = ft['${s.region}|${_pnorm(s.name)}'];
    if (all == null) return null;
    var recs = all.where((rec) {
      return (rec[0] as List).contains(st.fromLine) && (rec[1] as List).contains(st.toLine);
    }).toList();
    if (recs.isEmpty) return null;

    // 새 노선의 방향: 환승이후역(rec[5]) = 갈아탄 뒤 첫 역 = 경로의 다음 정차역
    if (i + 1 < r.stops.length) {
      final nextShort = _pnorm(stations[r.stops[i + 1].station].name);
      final byNext = recs.where((rec) => rec[5] as String == nextShort).toList();
      if (byNext.isNotEmpty) recs = byNext;
    }

    var resolved = recs.length == 1;
    if (!resolved && i > 0) {
      final lineSet = <String>{};
      for (final rec in recs) {
        lineSet.addAll((rec[0] as List).cast<String>());
      }
      final dS = _bfsLineHops(st.station, lineSet);
      final dP = _bfsLineHops(r.stops[i - 1].station, lineSet);
      final byShort = <String, int>{};
      for (var xi = 0; xi < stations.length; xi++) {
        final x = stations[xi];
        if (x.region == s.region && x.lines.any(lineSet.contains)) {
          byShort.putIfAbsent(_pnorm(x.name), () => xi);
        }
      }
      // 각 레코드를 앞/뒤/불명으로 분류. 종착역명 결측(10.5%)이면 불명.
      final ahead = <List<dynamic>>[], unknown = <List<dynamic>>[];
      for (final rec in recs) {
        final t = byShort[rec[2] as String];
        if (t == null || !dP.containsKey(t) || !dS.containsKey(t)) {
          unknown.add(rec);
        } else if (dP[t] == (dP[st.station] ?? 1) + dS[t]!) {
          ahead.add(rec);
        } // 나머지는 진행 방향 뒤 → 탈락
      }
      if (ahead.isNotEmpty) {
        ahead.sort((a, b) => (dS[byShort[a[2] as String]] ?? 1 << 30)
            .compareTo(dS[byShort[b[2] as String]] ?? 1 << 30));
        recs = [ahead.first];
        resolved = true;
      } else if (unknown.length == 1) {
        // 방향이 확인된 레코드가 전부 '뒤'라면 남은 불명 하나가 진행 방향(소거법)
        recs = unknown;
        resolved = true;
      }
    }
    return FastTransferResult(
      resolved,
      recs
          .take(2)
          .map((rec) => FastTransfer(
              rec[2] as String, (rec[3] as num).toInt(), (rec[4] as num).toInt()))
          .toList(),
    );
  }

  /// 노드 집합의 승강장 접근성 요약 — 자료가 있는 노드 중 위험도 최대치.
  /// 웹판 app.js accOf() 와 같은 규칙: 자료가 하나도 없으면 null.
  List<int>? accOf(Iterable<int> nodeIdxs) {
    List<int>? best;
    for (final i in nodeIdxs) {
      final a = nodes[i].ac;
      if (a != null && (best == null || a[0] > best[0])) best = a;
    }
    return best;
  }

  /// 이름으로 역 찾기(권역 우선, 표기 변형 허용)
  int? lookup(String name, [String? region]) {
    int? any;
    for (var i = 0; i < stations.length; i++) {
      final s = stations[i];
      if (s.name != name && s.short != name && !s.variants.contains(name)) continue;
      if (region == null || s.region == region) return i;
      any ??= i;
    }
    return any;
  }

  List<String> get regions {
    final c = <String, int>{};
    for (final s in stations) {
      c[s.region] = (c[s.region] ?? 0) + 1;
    }
    final ks = c.keys.where((k) => c[k]! >= 10).toList()
      ..sort((a, b) => c[b]!.compareTo(c[a]!));
    return ks;
  }

  String colorOf(String line) => colors[line] ?? '#6B7280';
}

class _Raw {
  final String region;
  final String addr;
  final List<int> nodes = [];
  final Map<String, int> names = {};
  final List<String> lines = [];
  int demand = 0;
  double lat = 0, lon = 0;
  _Raw(this.region, this.addr);
}
