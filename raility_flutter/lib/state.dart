import 'package:flutter/widgets.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'graph.dart';

/// 앱 전역 상태. 출도착역·권역 선택과 마지막 진단 결과를 들고 있다.
class AppState extends ChangeNotifier {
  final RailGraph graph;
  AppState(this.graph);

  SharedPreferences? _prefs;

  String _region = '수도권';
  String _mapRegion = '수도권';
  int? _from, _to;
  Diagnosis? result;

  String get region => _region;
  set region(String v) {
    _region = v;
    _prefs?.setString('region', v);
    notifyListeners();
  }

  String get mapRegion => _mapRegion;
  set mapRegion(String v) {
    if (_mapRegion == v) return;
    _mapRegion = v;
    notifyListeners();
  }

  /// 권역 진단 탭의 선택 권역
  String? panelRegion;

  /// 배차 모드 등 그래프 가중치가 바뀐 뒤 현재 출도착으로 다시 진단한다.
  void rediagnose() => _run();

  int? get from => _from;
  int? get to => _to;

  Future<void> restore() async {
    _prefs = await SharedPreferences.getInstance();
    final r = _prefs!.getString('region');
    if (r != null && graph.regions.contains(r)) {
      _region = r;
      _mapRegion = r;
    }
    final f = _prefs!.getInt('from'), t = _prefs!.getInt('to');
    if (f != null && t != null && f < graph.stations.length && t < graph.stations.length && f != t) {
      _from = f;
      _to = t;
      _run();
    }
  }

  void setFrom(int i) {
    if (_to == i) return;
    _from = i;
    _persist();
    _run();
  }

  void setTo(int i) {
    if (_from == i) return;
    _to = i;
    _persist();
    _run();
  }

  void swap() {
    final t = _from;
    _from = _to;
    _to = t;
    _persist();
    _run();
  }

  void _persist() {
    if (_from != null) _prefs?.setInt('from', _from!);
    if (_to != null) _prefs?.setInt('to', _to!);
  }

  void _run() {
    if (_from != null && _to != null) {
      result = graph.diagnose(_from!, _to!);
    } else {
      result = null;
    }
    notifyListeners();
  }
}

class AppScope extends InheritedNotifier<AppState> {
  const AppScope({super.key, required AppState state, required super.child})
      : super(notifier: state);

  static AppState of(BuildContext c) =>
      c.dependOnInheritedWidgetOfExactType<AppScope>()!.notifier!;
}
