/// Raility 디자인 토큰
///
/// Apple iOS UI Kit(figma community/1247769024068708989) 문법을 따른다.
/// systemGroupedBackground 위 인셋 그룹 카드, 강조는 systemBlue 틴트 하나,
/// 위험 단계는 iOS 시스템 팔레트(green/yellow/orange/red). 웹판 app.css 와 같은 값이다.
library;

import 'package:flutter/material.dart';

class InkPalette {
  final Color i0, i1, i2, i3, i4, i5, i6, i7;
  final Color line, lineStrong, bg, surface, surface2;
  final Color tint, tintBg;
  final Color risk0, risk1, risk2, risk3;
  final Color risk1Bg, risk2Bg, risk3Bg;
  const InkPalette({
    required this.i0, required this.i1, required this.i2, required this.i3,
    required this.i4, required this.i5, required this.i6, required this.i7,
    required this.line, required this.lineStrong,
    required this.bg, required this.surface, required this.surface2,
    required this.tint, required this.tintBg,
    required this.risk0, required this.risk1, required this.risk2, required this.risk3,
    required this.risk1Bg, required this.risk2Bg, required this.risk3Bg,
  });

  /// iOS Light — label/separator 는 시스템 알파값 그대로
  static const light = InkPalette(
    i0: Color(0xFF000000), i1: Color(0xEB000000), i2: Color(0xC73C3C43), i3: Color(0x993C3C43),
    i4: Color(0x6B3C3C43), i5: Color(0x3D3C3C43), i6: Color(0x29787880), i7: Color(0x1A787880),
    line: Color(0x243C3C43), lineStrong: Color(0x3D3C3C43),
    bg: Color(0xFFF2F2F7), surface: Colors.white, surface2: Color(0x14787880),
    tint: Color(0xFF007AFF), tintBg: Color(0x1F007AFF),
    risk0: Color(0xFF34C759), risk1: Color(0xFFD6A900), risk2: Color(0xFFFF9500), risk3: Color(0xFFFF3B30),
    risk1Bg: Color(0x29FFCC00), risk2Bg: Color(0x21FF9500), risk3Bg: Color(0x1FFF3B30),
  );

  /// iOS Dark — 순검정 배경 + #1C1C1E 카드
  static const dark = InkPalette(
    i0: Color(0xFFFFFFFF), i1: Color(0xEBFFFFFF), i2: Color(0xB8EBEBF5), i3: Color(0x99EBEBF5),
    i4: Color(0x61EBEBF5), i5: Color(0x38EBEBF5), i6: Color(0x52787880), i7: Color(0x33787880),
    line: Color(0x80545458), lineStrong: Color(0xB8545458),
    bg: Color(0xFF000000), surface: Color(0xFF1C1C1E), surface2: Color(0x2E787880),
    tint: Color(0xFF0A84FF), tintBg: Color(0x330A84FF),
    risk0: Color(0xFF30D158), risk1: Color(0xFFE5C33B), risk2: Color(0xFFFF9F0A), risk3: Color(0xFFFF453A),
    risk1Bg: Color(0x29FFD60A), risk2Bg: Color(0x2EFF9F0A), risk3Bg: Color(0x33FF453A),
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
      seedColor: ink.tint,
      brightness: b,
      surface: ink.surface,
    ),
    splashFactory: InkSparkle.splashFactory,
    textTheme: TextTheme(
      bodyMedium: TextStyle(color: ink.i1, fontSize: 15, height: 1.47),
      bodySmall: TextStyle(color: ink.i3, fontSize: 13, height: 1.55),
      titleMedium: TextStyle(color: ink.i0, fontSize: 17, fontWeight: FontWeight.w600, letterSpacing: -0.3),
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

/// 승강장 장벽 라벨 — ac[1..3] 순서와 일치 (웹판 ACC_LABEL 과 동일)
const accLabels = ['안전발판 없음', '승강장 미연결', '스크린도어 없음'];

String comma(num n) => n.round().toString().replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');

int mins(double sec) => (sec / 60).round();
