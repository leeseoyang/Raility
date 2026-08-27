import 'package:flutter/material.dart';

import '../state.dart';
import '../theme.dart';
import '../widgets.dart';

/// 역 검색 바텀시트. 선택한 역 인덱스를 돌려준다.
Future<int?> pickStation(BuildContext context, String title) {
  final ink = Palette.of(context);
  return showModalBottomSheet<int>(
    context: context,
    isScrollControlled: true,
    backgroundColor: ink.surface,
    showDragHandle: true,
    shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18))),
    builder: (ctx) => _SearchSheet(title: title, app: AppScope.of(context)),
  );
}

class _SearchSheet extends StatefulWidget {
  final String title;
  final AppState app;
  const _SearchSheet({required this.title, required this.app});

  @override
  State<_SearchSheet> createState() => _SearchSheetState();
}

class _SearchSheetState extends State<_SearchSheet> {
  final _ctrl = TextEditingController();
  String _q = '';

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  List<int> _results() {
    final g = widget.app.graph;
    final q = _q.trim();

    if (q.isEmpty) {
      final pool = <int>[];
      for (var i = 0; i < g.stations.length; i++) {
        if (g.stations[i].region == widget.app.region) pool.add(i);
      }
      pool.sort((a, b) => g.stations[b].demand.compareTo(g.stations[a].demand));
      return pool.take(40).toList();
    }

    final scored = <(int, double)>[];
    for (var i = 0; i < g.stations.length; i++) {
      final s = g.stations[i];
      var p = -1;
      for (final v in s.variants) {
        final h = v.indexOf(q);
        if (h >= 0 && (p < 0 || h < p)) p = h;
      }
      if (p < 0 && s.short.startsWith(q)) p = 0;
      if (p < 0) continue;
      scored.add((
        i,
        (p == 0 ? 0 : 1) +
            (s.region == widget.app.region ? 0 : 0.5) -
            (s.demand / 1e6).clamp(0, 0.4)
      ));
    }
    scored.sort((a, b) => a.$2.compareTo(b.$2));
    return scored.take(60).map((e) => e.$1).toList();
  }

  @override
  Widget build(BuildContext context) {
    final ink = Palette.of(context);
    final g = widget.app.graph;
    final results = _results();
    final insets = MediaQuery.viewInsetsOf(context).bottom;

    return Padding(
      padding: EdgeInsets.only(bottom: insets),
      child: SizedBox(
        height: MediaQuery.sizeOf(context).height * 0.82,
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
            child: Row(children: [
              Expanded(
                child: Text(widget.title,
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: ink.i0)),
              ),
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text('닫기', style: TextStyle(fontSize: 13, color: ink.i3, fontWeight: FontWeight.w600)),
              ),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
            child: TextField(
              controller: _ctrl,
              autofocus: true,
              textInputAction: TextInputAction.search,
              onChanged: (v) => setState(() => _q = v),
              style: TextStyle(fontSize: 16, color: ink.i0),
              decoration: InputDecoration(
                hintText: '역 이름 검색',
                hintStyle: TextStyle(color: ink.i4, fontSize: 16),
                prefixIcon: Icon(Icons.search, size: 19, color: ink.i4),
                filled: true,
                fillColor: ink.surface2,
                contentPadding: const EdgeInsets.symmetric(vertical: 12),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(11),
                  borderSide: BorderSide(color: ink.line),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(11),
                  borderSide: BorderSide(color: ink.line),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(11),
                  borderSide: BorderSide(color: ink.lineStrong),
                ),
              ),
            ),
          ),
          if (_q.trim().isEmpty)
            Eyebrow('${widget.app.region} · 이용객 많은 역',
                padding: const EdgeInsets.fromLTRB(16, 2, 16, 6)),
          Expanded(
            child: results.isEmpty
                ? Center(
                    child: Text('"$_q" 과(와) 일치하는 역이 없습니다.',
                        style: TextStyle(fontSize: 13.5, color: ink.i4)))
                : ListView.builder(
                    keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
                    itemCount: results.length,
                    itemBuilder: (c, i) {
                      final s = g.stations[results[i]];
                      return RowTile(
                        title: s.name,
                        subtitle: '${s.region} · ${s.lines.join(', ')}',
                        trailing: s.isTransfer
                            ? Container(
                                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                                decoration: BoxDecoration(
                                    color: ink.i3, borderRadius: BorderRadius.circular(5)),
                                child: const Text('환승',
                                    style: TextStyle(
                                        fontSize: 11, fontWeight: FontWeight.w700, color: Colors.white)),
                              )
                            : null,
                        onTap: () => Navigator.pop(context, results[i]),
                      );
                    },
                  ),
          ),
        ]),
      ),
    );
  }
}
