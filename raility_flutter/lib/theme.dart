/// Raility 디자인 토큰
///
/// 채도는 노선 고유색과 위험 단계에만 허용한다. 나머지는 무채색 잉크 스케일로 눌러
/// 데이터가 먼저 읽히게 한다. 웹판 app.css 와 같은 값이다.
library;

import 'package:flutter/material.dart';

class InkPalette {
  final Color i0, i1, i2, i3, i4, i5, i6, i7;
  final Color line, lineStrong, bg, surface, surface2;
  final Color risk0, risk1, risk2, risk3;
  final Color risk1Bg, risk2Bg, risk3Bg;
  const InkPalette({
    required this.i0, required this.i1, required this.i2, required this.i3,
    required this.i4, required this.i5, required this.i6, required this.i7,
    required this.line, required this.lineStrong,
    required this.bg, required this.surface, required this.surface2,
    required this.risk0, required this.risk1, required this.risk2, required this.risk3,
    required this.risk1Bg, required this.risk2Bg, required this.risk3Bg,
  });

  static const light = InkPalette(
    i0: Color(0xFF0C0E11), i1: Color(0xFF1B1F26), i2: Color(0xFF3D454F), i3: Color(0xFF6B7480),
    i4: Color(0xFF98A1AC), i5: Color(0xFFC9CFD6), i6: Color(0xFFE4E8EC), i7: Color(0xFFF1F4F6),
    line: Color(0xFFE2E6EA), lineStrong: Color(0xFFCFD5DB),
    bg: Color(0xFFFBFCFD), surface: Colors.white, surface2: Color(0xFFF6F8F9),
    risk0: Color(0xFF5B6572), risk1: Color(0xFF8A7A3E), risk2: Color(0xFFB4681D), risk3: Color(0xFFA32B1F),
    risk1Bg: Color(0xFFFAF8EE), risk2Bg: Color(0xFFFDF5EC), risk3Bg: Color(0xFFFDF0EE),
  );

  static const dark = InkPalette(
    i0: Color(0xFFF2F5F7), i1: Color(0xFFE2E7EC), i2: Color(0xFFB9C1CB), i3: Color(0xFF8B95A1),
    i4: Color(0xFF69737F), i5: Color(0xFF404853), i6: Color(0xFF2A313A), i7: Color(0xFF1D232B),
    line: Color(0xFF252C35), lineStrong: Color(0xFF333B45),
    bg: Color(0xFF0D1116), surface: Color(0xFF141920), surface2: Color(0xFF1A2029),
    risk0: Color(0xFF9AA4B0), risk1: Color(0xFFD0BC6A), risk2: Color(0xFFE0954A), risk3: Color(0xFFE9705C),
    risk1Bg: Color(0xFF232116), risk2Bg: Color(0xFF271F16), risk3Bg: Color(0xFF2A1A19),
  );
}

class Palette extends InheritedWidget {
  final InkPalette ink;
  const Palette({super.key, required this.ink, required super.child});

  static InkPalette of(BuildContext c) =>
      c.dependOnInheritedWidgetOfExactType<Palette>()?.ink ?? InkPalette.light;

  @override
  bool updateShouldNotify(Palette old) => old.ink != ink;
}

Color hexColor(String hex) {
  var h = hex.replaceAll('#', '');
  if (h.length == 6) h = 'FF$h';
  return Color(int.parse(h, radix: 16));
}

ThemeData buildTheme(Brightness b) {
  final ink = b == Brightness.dark ? InkPalette.dark : InkPalette.light;
  const family = 'Roboto';
  return ThemeData(
    useMaterial3: true,
    brightness: b,
    scaffoldBackgroundColor: ink.bg,
    fontFamily: family,
    colorScheme: ColorScheme.fromSeed(
      seedColor: ink.risk3,
      brightness: b,
      surface: ink.surface,
    ),
    splashFactory: InkSparkle.splashFactory,
    textTheme: TextTheme(
      bodyMedium: TextStyle(color: ink.i1, fontSize: 15, height: 1.5),
      bodySmall: TextStyle(color: ink.i3, fontSize: 12.5, height: 1.6),
      titleMedium: TextStyle(color: ink.i0, fontSize: 17, fontWeight: FontWeight.w700, letterSpacing: -0.3),
    ),
  );
}

/// 등급별 색
Color gradeColor(InkPalette ink, String g) => switch (g) {
      'A' => ink.risk0,
      'B' => ink.risk1,
      'C' => ink.risk2,
      _ => ink.risk3,
    };

const gradeText = <String, List<String>>{
  'A': ['우회 가능', '경로 위 어느 역이 멈춰도 돌아갈 길이 있습니다.'],
  'B': ['대체로 안전', '대부분 우회할 수 있지만 일부 역은 대체 경로가 없습니다.'],
  'C': ['주의 필요', '경로의 상당 부분이 특정 역에 의존합니다.'],
  'D': ['취약', '대부분의 역이 끊기면 우회할 수 없습니다.'],
  'E': ['매우 취약', '사실상 모든 중간역이 단일고장점입니다. 대체 경로가 없습니다.'],
};

String comma(num n) => n.round().toString().replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');

int mins(double sec) => (sec / 60).round();
