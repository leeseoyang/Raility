/// 웹판 raility_app/test_graph.js 와 같은 기준으로 Dart 포팅을 검증한다.
/// 실행: flutter test
library;

import 'dart:io';
import 'dart:math' as math;
import 'package:flutter_test/flutter_test.dart';
import 'package:raility/graph.dart';

late RailGraph g;

void main() {
  setUpAll(() {
    g = RailGraph.parse(File('assets/network.json').readAsStringSync());
  });

  group('데이터 무결성', () {
    test('노드/엣지 규모', () {
      expect(g.nodes.length, greaterThan(1000));
      expect(g.edges.length, greaterThan(1200));
    });
    test('역 수 < 노드 수 (승강장 병합됨)', () {
      expect(g.stations.length, lessThan(g.nodes.length));
    });
    test('모든 엣지 소요시간 > 0', () {
      expect(g.edges.every((e) => e[3] > 0), isTrue);
    });
    test('고립 노드 없음', () {
      expect(g.adj.where((a) => a.isEmpty).length, 0);
    });
    test('모든 역이 노드를 1개 이상 보유', () {
      expect(g.stations.every((s) => s.nodes.isNotEmpty), isTrue);
    });
  });

  group('최단경로', () {
    test('서울역–강남 경로와 소요시간', () {
      final a = g.lookup('서울역', '수도권')!, b = g.lookup('강남', '수도권')!;
      final r = g.shortest(a, b);
      expect(r, isNotNull);
      final m = (r!.time / 60).round();
      expect(m, inInclusiveRange(10, 70));
    });

    test('경로가 실제 엣지로 연속', () {
      final a = g.lookup('소사', '수도권')!, b = g.lookup('강남', '수도권')!;
      final r = g.shortest(a, b)!;
      for (var i = 0; i + 1 < r.path.length; i++) {
        expect(g.adj[r.path[i]].any((e) => e.to == r.path[i + 1]), isTrue,
            reason: '${r.path[i]} → ${r.path[i + 1]} 사이에 엣지가 없다');
      }
    });

    test('시작·끝이 지정한 역', () {
      final a = g.lookup('소사', '수도권')!, b = g.lookup('강남', '수도권')!;
      final r = g.shortest(a, b)!;
      expect(g.staOf[r.path.first], a);
      expect(g.staOf[r.path.last], b);
    });

    test('대칭성: A→B 와 B→A 소요 동일', () {
      final a = g.lookup('서울역', '수도권')!, b = g.lookup('강남', '수도권')!;
      expect((g.shortest(a, b)!.time - g.shortest(b, a)!.time).abs(), lessThan(1e-6));
    });
  });

  group('역 차단', () {
    late int a, b;
    setUp(() {
      a = g.lookup('소사', '수도권')!;
      b = g.lookup('강남', '수도권')!;
    });

    test('차단한 역을 지나지 않는다', () {
      final base = g.shortest(a, b)!;
      final mid = g.staOf[base.path[base.path.length ~/ 2]];
      final blocked = g.shortest(a, b, block: [mid]);
      if (blocked != null) {
        expect(blocked.path.every((n) => g.staOf[n] != mid), isTrue);
      }
    });

    test('차단 후 소요시간은 줄어들 수 없다', () {
      final base = g.shortest(a, b)!;
      final mid = g.staOf[base.path[base.path.length ~/ 2]];
      final blocked = g.shortest(a, b, block: [mid]);
      if (blocked != null) expect(blocked.time, greaterThanOrEqualTo(base.time - 1e-6));
    });

    test('출발역 차단 시 null', () {
      expect(g.shortest(a, b, block: [a]), isNull);
    });
  });

  group('대전 1호선 — 단일 노선이라 전 중간역이 SPOF', () {
    test('대전 역 22개', () {
      expect(g.stations.where((s) => s.region == '대전').length, 22);
    });

    test('판암→반석 전 구간 진단', () {
      final a = g.lookup('판암', '대전')!, b = g.lookup('반석', '대전')!;
      final d = g.diagnose(a, b);
      expect(d.ok, isTrue);
      expect(d.stops.length, 22);
      expect(d.spof.length, d.mids.length, reason: '중간역 전부가 SPOF여야 한다');
      expect(d.grade, 'E');
      expect(d.transfers, 0, reason: '단일 노선이라 환승이 없다');
    });
  });

  group('수도권 — 우회 가능', () {
    test('신도림→홍대입구는 E등급이 아니다', () {
      final a = g.lookup('신도림', '수도권')!, b = g.lookup('홍대입구', '수도권')!;
      final d = g.diagnose(a, b);
      expect(d.ok, isTrue);
      expect(d.ratio, lessThan(1));
      expect(d.grade, isNot('E'));
    });
  });

  group('역 표기 병합', () {
    test('근접 동명역이 남아있지 않다', () {
      // 이름이 같아도 멀리 떨어져 있으면 다른 역이다(예: 양평 5호선 vs 경의중앙선 양평군).
      // 병합 실패로 볼 것은 "가까운데도 나뉜" 경우뿐이다.
      String norm(String n) => n.length > 2 && n.endsWith('역') ? n.substring(0, n.length - 1) : n;
      double metres(Station a, Station b) {
        const r = 6371000.0, t = math.pi / 180;
        final dla = (b.lat - a.lat) * t, dlo = (b.lon - a.lon) * t;
        final h = math.sin(dla / 2) * math.sin(dla / 2) +
            math.cos(a.lat * t) * math.cos(b.lat * t) * math.sin(dlo / 2) * math.sin(dlo / 2);
        return 2 * r * math.asin(math.min(1.0, math.sqrt(h)));
      }

      final seen = <String, Station>{};
      final split = <String>[];
      for (final s in g.stations) {
        final k = '${s.region}|${norm(s.name)}';
        final other = seen[k];
        if (other != null) {
          final d = metres(s, other);
          if (d <= RailGraph.mergeRadiusM) split.add('${norm(s.name)} (${d.round()}m)');
        }
        seen[k] = s;
      }
      expect(split, isEmpty, reason: '가까운데도 병합되지 않은 역: ${split.take(5)}');
    });

    test('신도림·서울역이 하나로 병합', () {
      expect(g.stations[g.lookup('신도림', '수도권')!].lines.length, greaterThanOrEqualTo(2));
      expect(g.stations[g.lookup('서울역', '수도권')!].lines.length, greaterThanOrEqualTo(3));
    });
  });

  group('환승 표기', () {
    test('소사→강남 환승 인식 및 구간 노선 실재', () {
      final a = g.lookup('소사', '수도권')!, b = g.lookup('강남', '수도권')!;
      final d = g.diagnose(a, b);
      expect(d.transfers, greaterThanOrEqualTo(1));
      expect(d.lines.length, greaterThanOrEqualTo(2));

      for (var i = 0; i < d.stops.length - 1; i++) {
        final st = d.stops[i];
        if (st.segTransfer) continue;
        final la = g.stations[st.station].lines;
        final lb = g.stations[d.stops[i + 1].station].lines;
        final shared = la.where(lb.contains).toList();
        if (shared.isNotEmpty) {
          expect(shared.contains(st.rideLine), isTrue,
              reason: '${g.stations[st.station].name} 구간 노선 ${st.rideLine} 이 양쪽에 없다');
        }
      }
    });

    test('환승 지점에 출발/도착 노선이 기록됨', () {
      final a = g.lookup('소사', '수도권')!, b = g.lookup('강남', '수도권')!;
      final d = g.diagnose(a, b);
      for (final s in d.stops.where((s) => s.transferHere)) {
        expect(s.fromLine, isNotNull);
        expect(s.toLine, isNotNull);
      }
    });
  });

  group('절점', () {
    test('대전 절점 = 중간역 20개', () {
      final f = g.regionFragility('대전')!;
      expect(f.cuts, 20);
      expect(f.total, 22);
    });

    test('수도권 절점 비율 < 대전', () {
      expect(g.regionFragility('수도권')!.ratio, lessThan(g.regionFragility('대전')!.ratio));
    });

    test('절점을 빼면 실제로 연결요소가 늘어난다', () {
      final members = <int>[];
      for (var i = 0; i < g.stations.length; i++) {
        if (g.stations[i].region == '수도권') members.add(i);
      }
      int components(int exclude) {
        final inSet = members.where((m) => m != exclude).toSet();
        final seen = <int>{};
        var c = 0;
        for (final s in inSet) {
          if (seen.contains(s)) continue;
          c++;
          final q = [s];
          seen.add(s);
          while (q.isNotEmpty) {
            final u = q.removeLast();
            for (final v in g.staAdj[u]) {
              if (inSet.contains(v) && seen.add(v)) q.add(v);
            }
          }
        }
        return c;
      }

      final base = components(-1);
      final arts = g.articulationPoints(members);
      for (final a in arts.take(15)) {
        expect(components(a), greaterThan(base),
            reason: '${g.stations[a].name} 은 절점으로 판정됐지만 제거해도 안 쪼개진다');
      }
      final nonArts =
          members.where((i) => !arts.contains(i) && g.staAdj[i].length >= 2).take(15);
      for (final a in nonArts) {
        expect(components(a), base,
            reason: '${g.stations[a].name} 은 절점이 아닌데 제거하니 쪼개진다');
      }
    });
  });

  group('권역 분류', () {
    test('대구 90개 이상 · 미분류 30개 미만', () {
      final c = <String, int>{};
      for (final s in g.stations) {
        c[s.region] = (c[s.region] ?? 0) + 1;
      }
      expect(c['대구'] ?? 0, greaterThanOrEqualTo(90));
      expect(c['기타'] ?? 0, lessThan(30));
    });
  });

  group('진단 일관성 (무작위 40쌍)', () {
    test('불변식 위반 없음', () {
      final metro = <int>[];
      for (var i = 0; i < g.stations.length; i++) {
        if (g.stations[i].region == '수도권') metro.add(i);
      }
      var seed = 12345;
      double rnd() {
        seed = (seed * 1103515245 + 12345) & 0x7fffffff;
        return seed / 0x7fffffff;
      }

      for (var t = 0; t < 40; t++) {
        final a = metro[(rnd() * metro.length).floor()];
        final b = metro[(rnd() * metro.length).floor()];
        if (a == b) continue;
        final r = g.diagnose(a, b);
        expect(r.ok, isTrue, reason: '${g.stations[a].name}→${g.stations[b].name} 도달 불가');
        expect(r.spof.length, lessThanOrEqualTo(r.mids.length));
        expect(r.ratio, inInclusiveRange(0, 1));
        expect(r.base!.time, greaterThan(0));
        for (final st in r.mids) {
          if (!st.spof) expect(st.delta, greaterThanOrEqualTo(-1e-6));
        }
      }
    });
  });

  // 웹판 test_graph.js 의 '승강장 접근성' 절과 같은 기준
  group('승강장 접근성', () {
    test('접근성 자료 보유 노드 800개 이상', () {
      expect(g.nodes.where((n) => n.ac != null).length, greaterThanOrEqualTo(800));
    });
    test('위험도 = 세 장벽 플래그의 합', () {
      for (final n in g.nodes) {
        final a = n.ac;
        if (a == null) continue;
        expect(a.length, 5);
        expect(a[0], a[1] + a[2] + a[3]);
      }
    });
    test('자료 없는 노선(9호선)은 ac 필드 자체가 없음', () {
      final line9 = g.nodes.where((n) => n.line.contains('9호선')).toList();
      expect(line9, isNotEmpty);
      expect(line9.every((n) => n.ac == null), isTrue);
    });
    test('대전 1호선 전 노드 접근성 자료 보유', () {
      final dj = g.nodes.where((n) => n.line == '대전 도시철도 1호선').toList();
      expect(dj, isNotEmpty);
      expect(dj.every((n) => n.ac != null), isTrue);
    });
    test('대전 안전발판 미설치 다수 (원본 80% 수준)', () {
      final dj = g.nodes.where((n) => n.line == '대전 도시철도 1호선').toList();
      final noPlate = dj.where((n) => n.ac![1] == 1).length;
      expect(noPlate, greaterThanOrEqualTo((dj.length * 0.6).floor()));
    });
    test('빠른환승 데이터 100역 이상 · 칸/문 범위', () {
      expect(g.ft.length, greaterThanOrEqualTo(100));
      for (final recs in g.ft.values) {
        for (final rec in recs) {
          final car = (rec[3] as num).toInt(), door = (rec[4] as num).toInt();
          expect(car, inInclusiveRange(1, 10));
          expect(door, inInclusiveRange(1, 4));
        }
      }
    });
    test('소사→강남 환승역에 빠른환승 안내 존재 · 비환승역은 null', () {
      final r = g.diagnose(g.lookup('소사', '수도권')!, g.lookup('강남', '수도권')!);
      var hits = 0;
      for (var i = 0; i < r.stops.length; i++) {
        final f = g.fastTransferAt(r, i);
        if (!r.stops[i].transferHere) {
          expect(f, isNull);
        } else if (f != null) {
          hits++;
          expect(f.list, isNotEmpty);
        }
      }
      expect(hits, greaterThanOrEqualTo(1));
    });
    test('accOf 는 자료 없음과 장벽 없음을 구분', () {
      final none = g.nodes.indexWhere((n) => n.ac == null);
      expect(g.accOf([none]), isNull);              // 자료 없음 → null
      final zero = g.nodes.indexWhere((n) => n.ac != null && n.ac![0] == 0);
      expect(g.accOf([zero]), isNotNull);           // 장벽 없음 → [0,...]
      expect(g.accOf([zero])![0], 0);
      expect(g.accOf([none, zero]), isNotNull);     // 혼합 → 자료 있는 쪽
    });
  });
}
