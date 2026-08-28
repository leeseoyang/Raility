/* Raility — 그래프 · 최단경로 · 단일고장점 판정
 *
 * UI와 분리해 두어 브라우저와 Node(테스트) 양쪽에서 동일한 코드를 검증할 수 있게 한다.
 * window.NET(data.js)을 입력으로 받아 window.RailGraph를 노출한다.
 */
(function (root) {
'use strict';

var NET = root.NET;
var NODES = NET.nodes, EDGES = NET.edges;

// 인접 리스트
var ADJ = NODES.map(function () { return []; });
EDGES.forEach(function (e, ei) {
  ADJ[e[0]].push({ to: e[1], w: e[3], type: e[2], ei: ei });
  ADJ[e[1]].push({ to: e[0], w: e[3], type: e[2], ei: ei });
});

// 같은 역사명 + 같은 권역 = 하나의 "역".
// 승강장 노드가 노선별로 쪼개져 있어, 실제로 "역이 멈춘다"를 모사하려면 묶어서 통째로 제거해야 한다.
//
// 주의: 원본 공공데이터는 같은 역을 "신도림"(2호선)과 "신도림역"(경부선)처럼 다르게 적는다.
// 이대로 두면 한 역이 둘로 쪼개져, 실제로는 불가능한 "닫힌 역에서의 환승"을 우회로로 인정해
// 취약성을 실제보다 낮게 보고하게 된다. 이름을 정규화해 병합하되,
// 이름만 닮은 다른 역이 잘못 합쳐지지 않도록 좌표 거리 조건을 함께 건다.
var MERGE_RADIUS_M = 1200;

function normName(n) { return n.length > 2 && n.charAt(n.length - 1) === '역' ? n.slice(0, -1) : n; }

function haversine(la1, lo1, la2, lo2) {
  var R = 6371000, t = Math.PI / 180;
  var dla = (la2 - la1) * t, dlo = (lo2 - lo1) * t;
  var a = Math.sin(dla / 2) * Math.sin(dla / 2) +
          Math.cos(la1 * t) * Math.cos(la2 * t) * Math.sin(dlo / 2) * Math.sin(dlo / 2);
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

var STATIONS = [];
var STA_OF = new Int32Array(NODES.length);
(function () {
  // 1단계: 표기 그대로 묶는다.
  var raw = [], map = {};
  NODES.forEach(function (n, i) {
    var key = n.r + '|' + n.fn;
    var s = map[key];
    if (!s) { s = map[key] = { names: {}, region: n.r, nodes: [], lines: [], demand: 0, addr: n.ad }; raw.push(s); }
    s.nodes.push(i);
    s.names[n.fn] = (s.names[n.fn] || 0) + 1;
    if (s.lines.indexOf(n.l) < 0) s.lines.push(n.l);
    s.demand += n.d;
  });
  raw.forEach(function (s) {
    var la = 0, lo = 0;
    s.nodes.forEach(function (i) { la += NODES[i].la; lo += NODES[i].lo; });
    s.lat = la / s.nodes.length; s.lon = lo / s.nodes.length;
  });

  // 2단계: 정규화 이름이 같고 서로 가까우면 하나로 합친다.
  var buckets = {};
  raw.forEach(function (s, i) {
    var k = s.region + '|' + normName(Object.keys(s.names)[0]);
    (buckets[k] = buckets[k] || []).push(i);
  });

  var parent = raw.map(function (_, i) { return i; });
  function find(x) { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; }
  function union(a, b) { a = find(a); b = find(b); if (a !== b) parent[b] = a; }

  Object.keys(buckets).forEach(function (k) {
    var g = buckets[k];
    for (var a = 0; a < g.length; a++) {
      for (var b = a + 1; b < g.length; b++) {
        var A = raw[g[a]], B = raw[g[b]];
        if (haversine(A.lat, A.lon, B.lat, B.lon) <= MERGE_RADIUS_M) union(g[a], g[b]);
      }
    }
  });

  var byRoot = {};
  raw.forEach(function (s, i) {
    var r = find(i);
    var m = byRoot[r];
    if (!m) {
      m = byRoot[r] = { names: {}, region: s.region, nodes: [], lines: [], demand: 0, addr: s.addr };
      STATIONS.push(m);
    }
    Object.keys(s.names).forEach(function (nm) { m.names[nm] = (m.names[nm] || 0) + s.names[nm]; });
    s.nodes.forEach(function (i2) { m.nodes.push(i2); });
    s.lines.forEach(function (l) { if (m.lines.indexOf(l) < 0) m.lines.push(l); });
    m.demand += s.demand;
  });

  STATIONS.forEach(function (s, si) {
    // 표시 이름: 노드가 많은 표기를 쓰고, 같으면 짧은(접미사 없는) 표기를 쓴다.
    var variants = Object.keys(s.names);
    variants.sort(function (a, b) {
      var d = s.names[b] - s.names[a];
      return d !== 0 ? d : a.length - b.length;
    });
    s.name = variants[0];
    s.short = normName(s.name);
    s.variants = variants;
    var la = 0, lo = 0;
    s.nodes.forEach(function (i) { la += NODES[i].la; lo += NODES[i].lo; STA_OF[i] = si; });
    s.lat = la / s.nodes.length; s.lon = lo / s.nodes.length;
    s.transfer = s.lines.length > 1;
    s.key = s.region + '|' + s.short;
  });
})();

/* ── 이진 힙 ─────────────────────────────────────────── */
function MinHeap() { this.a = []; }
MinHeap.prototype.push = function (k, v) {
  var a = this.a, i = a.length; a.push([k, v]);
  while (i > 0) { var p = (i - 1) >> 1; if (a[p][0] <= a[i][0]) break; var t = a[p]; a[p] = a[i]; a[i] = t; i = p; }
};
MinHeap.prototype.pop = function () {
  var a = this.a, top = a[0], last = a.pop();
  if (a.length) {
    a[0] = last; var i = 0, n = a.length;
    for (;;) {
      var l = 2 * i + 1, r = l + 1, m = i;
      if (l < n && a[l][0] < a[m][0]) m = l;
      if (r < n && a[r][0] < a[m][0]) m = r;
      if (m === i) break;
      var t = a[m]; a[m] = a[i]; a[i] = t; i = m;
    }
  }
  return top;
};

/* ── 최단경로 ────────────────────────────────────────── */
var INF = Infinity;
var _dist = new Float64Array(NODES.length);
var _prev = new Int32Array(NODES.length);
var _blocked = new Uint8Array(STATIONS.length);

/** 역 srcSta → 역 dstSta 최단경로. blockSta(역 인덱스 또는 배열)는 통과 불가. */
function shortest(srcSta, dstSta, blockSta) {
  if (srcSta === dstSta) return { time: 0, path: [STATIONS[srcSta].nodes[0]] };

  var i, n = NODES.length;
  for (i = 0; i < n; i++) { _dist[i] = INF; _prev[i] = -1; }

  var hasBlock = blockSta != null;
  if (hasBlock) {
    _blocked.fill(0);
    var arr = Array.isArray(blockSta) ? blockSta : [blockSta];
    for (i = 0; i < arr.length; i++) {
      if (arr[i] === srcSta || arr[i] === dstSta) return null;  // 출발/도착역 자체가 막히면 무의미
      _blocked[arr[i]] = 1;
    }
  }

  var h = new MinHeap();
  STATIONS[srcSta].nodes.forEach(function (i) { _dist[i] = 0; h.push(0, i); });

  var dstNodes = STATIONS[dstSta].nodes;
  var isDst = {};
  dstNodes.forEach(function (i) { isDst[i] = 1; });

  var endNode = -1;
  while (h.a.length) {
    var top = h.pop(), d = top[0], u = top[1];
    if (d > _dist[u]) continue;
    if (isDst[u]) { endNode = u; break; }
    var lst = ADJ[u];
    for (var k = 0; k < lst.length; k++) {
      var e = lst[k], v = e.to;
      if (hasBlock && _blocked[STA_OF[v]]) continue;
      var nd = d + e.w;
      if (nd < _dist[v]) { _dist[v] = nd; _prev[v] = u; h.push(nd, v); }
    }
  }
  if (endNode < 0) return null;

  var path = [], cur = endNode;
  while (cur >= 0) { path.push(cur); cur = _prev[cur]; }
  path.reverse();
  return { time: _dist[endNode], path: path };
}

function edgeBetween(a, b) {
  var lst = ADJ[a];
  for (var i = 0; i < lst.length; i++) if (lst[i].to === b) return lst[i];
  return null;
}

/** 경로 노드열 → 역 단위 정차 목록.
 *
 *  원본 데이터의 인접 엣지는 노선 라벨이 어긋난 경우가 있다(같은 이름의 다른 노선 노드에
 *  인접이 붙는다). 역 단위 위상 자체는 옳으므로, 타고 가는 노선은 노드 라벨 대신
 *  "양쪽 역이 공유하는 노선"에서 고른다. 이렇게 하면 직결 운행은 환승으로 세지 않고,
 *  실제로 갈아타는 지점만 환승으로 잡힌다.
 */
function toStops(path) {
  var stops = [];
  for (var i = 0; i < path.length; i++) {
    var si = STA_OF[path[i]];
    var last = stops[stops.length - 1];
    if (last && last.sta === si) { last.nodes.push(path[i]); continue; }
    stops.push({ sta: si, nodes: [path[i]], lines: [], transferHere: false });
  }

  // 구간별로 실제 타는 노선을 정한다.
  var prevLine = null;
  for (var k = 0; k + 1 < stops.length; k++) {
    var a = stops[k], b = stops[k + 1];
    var e = edgeBetween(a.nodes[a.nodes.length - 1], b.nodes[0]);
    var seg;
    if (e && e.type === 1) {
      seg = { transfer: true, line: null };
    } else {
      var la = STATIONS[a.sta].lines, lb = STATIONS[b.sta].lines;
      var shared = la.filter(function (x) { return lb.indexOf(x) >= 0; });
      var line = shared.length
        ? (prevLine && shared.indexOf(prevLine) >= 0 ? prevLine : shared[0])
        : NODES[b.nodes[0]].l;
      seg = { transfer: false, line: line };
    }
    a.rideLine = seg.line;
    a.segTransfer = seg.transfer;
    if (!seg.transfer) {
      if (prevLine && seg.line && seg.line !== prevLine) { a.transferHere = true; a.fromLine = prevLine; a.toLine = seg.line; }
      prevLine = seg.line;
    } else {
      a.transferHere = true;
      a.fromLine = prevLine;
      // 환승 뒤 첫 구간의 노선은 다음 루프에서 정해진다.
      var nb = stops[k + 2];
      if (nb) {
        var lb2 = STATIONS[b.sta].lines, lc = STATIONS[nb.sta].lines;
        var sh2 = lb2.filter(function (x) { return lc.indexOf(x) >= 0; });
        a.toLine = sh2.length ? sh2[0] : NODES[b.nodes[0]].l;
      } else {
        a.toLine = NODES[b.nodes[0]].l;
      }
      prevLine = a.toLine;
    }
  }
  // 마지막 정차역은 들어온 노선을 그대로 쓴다.
  if (stops.length) stops[stops.length - 1].rideLine = prevLine || NODES[stops[stops.length - 1].nodes[0]].l;
  stops.forEach(function (st) {
    if (!st.rideLine) st.rideLine = NODES[st.nodes[0]].l;
    st.lines = [st.rideLine];
    st.node = st.nodes[0];
  });
  return stops;
}

/** 경로 위 중간역을 하나씩 제거해 우회 가능 여부를 판정한다. */
function diagnose(srcSta, dstSta) {
  var base = shortest(srcSta, dstSta, null);
  if (!base) return { ok: false, reason: 'disconnected' };

  var stops = toStops(base.path);
  var mids = stops.slice(1, -1);
  var spof = [], detour = [], maxDelta = 0;

  mids.forEach(function (st) {
    var alt = shortest(srcSta, dstSta, st.sta);
    if (!alt) { st.spof = true; spof.push(st); return; }
    st.delta = alt.time - base.time;
    st.altTime = alt.time;
    if (st.delta > 60) { detour.push(st); if (st.delta > maxDelta) maxDelta = st.delta; }
  });

  var ratio = mids.length ? spof.length / mids.length : 0;
  var grade = ratio === 0 ? 'A' : ratio <= 0.15 ? 'B' : ratio <= 0.4 ? 'C' : ratio <= 0.75 ? 'D' : 'E';

  return {
    ok: true, base: base, stops: stops, mids: mids,
    spof: spof, detour: detour, maxDelta: maxDelta, ratio: ratio, grade: grade,
    transfers: stops.filter(function (s) { return s.transferHere; }).length,
    lines: stops.map(function (s) { return s.rideLine; })
      .filter(function (l, i, a) { return l && a.indexOf(l) === i; })
  };
}

/* ── 역 단위 인접 그래프 ─────────────────────────────── */
var STA_ADJ = STATIONS.map(function () { return []; });
(function () {
  var seen = {};
  EDGES.forEach(function (e) {
    var a = STA_OF[e[0]], b = STA_OF[e[1]];
    if (a === b) return;                       // 같은 역 안의 환승은 위상에 영향 없음
    var k = a < b ? a + ',' + b : b + ',' + a;
    if (seen[k]) return;
    seen[k] = 1;
    STA_ADJ[a].push(b); STA_ADJ[b].push(a);
  });
})();

/** 절점(articulation point): 제거하면 그래프가 분리되는 정점.
 *  Tarjan 알고리즘의 반복 구현(재귀 깊이 제한을 피한다). */
function articulationPoints(members) {
  var inSet = new Uint8Array(STATIONS.length);
  members.forEach(function (i) { inSet[i] = 1; });

  var disc = new Int32Array(STATIONS.length).fill(-1);
  var low = new Int32Array(STATIONS.length);
  var parent = new Int32Array(STATIONS.length).fill(-1);
  var isArt = new Uint8Array(STATIONS.length);
  var timer = 0;

  members.forEach(function (start) {
    if (disc[start] !== -1) return;
    var rootChildren = 0;
    var stack = [[start, 0]];
    disc[start] = low[start] = timer++;

    while (stack.length) {
      var top = stack[stack.length - 1];
      var u = top[0];
      if (top[1] < STA_ADJ[u].length) {
        var v = STA_ADJ[u][top[1]++];
        if (!inSet[v]) continue;
        if (disc[v] === -1) {
          parent[v] = u;
          if (u === start) rootChildren++;
          disc[v] = low[v] = timer++;
          stack.push([v, 0]);
        } else if (v !== parent[u]) {
          if (disc[v] < low[u]) low[u] = disc[v];
        }
      } else {
        stack.pop();
        var p = parent[u];
        if (p !== -1) {
          if (low[u] < low[p]) low[p] = low[u];
          if (p !== start && low[u] >= disc[p]) isArt[p] = 1;
        }
      }
    }
    if (rootChildren > 1) isArt[start] = 1;
  });

  return members.filter(function (i) { return isArt[i] === 1; });
}

/** 권역별 절점 비율 — "제거하면 망이 쪼개지는 역"의 비중 */
function regionFragility(region) {
  var members = [];
  STATIONS.forEach(function (s, i) { if (s.region === region) members.push(i); });
  if (members.length < 5) return null;
  var arts = articulationPoints(members);
  return { region: region, total: members.length, cuts: arts.length,
           ratio: arts.length / members.length, stations: arts };
}

/* ── 빠른환승 (국토교통부 차량순서·출입문) ─────────────────────
 * NET.ft: { "권역|역명": [[탈때노선 후보, 갈아탈노선 후보, 종착방면, 칸, 문], ...] }
 * 같은 환승쌍에 상·하행 두 레코드가 있으므로 진행 방향을 판정해야 한다.
 * 직전 역 P 에서 탄 열차는 S 를 지나 P 반대쪽으로 간다. 따라서 그 열차의 종착역 T 는
 * "같은 노선 부분그래프에서 P→T 최단경로가 S 를 지난다" — 홉수로 dP[T] = dP[S] + dS[T]. */
function pnorm(s) {
  s = String(s || '').normalize('NFC').replace(/\(.*?\)/g, '').replace(/\s+/g, '');
  return s.length > 1 && s.charAt(s.length - 1) === '역' ? s.slice(0, -1) : s;
}
function bfsLineHops(start, lineSet) {
  // lineSet: 같은 운행 계통으로 취급할 노선 집합. 코레일 1호선처럼 한 계통이
  // 여러 그래프 노선(경부·경인·경원·장항)으로 갈라져 있어 단일 노선으로는
  // 종착역(소요산 등)에 닿지 못한다.
  function onLine(si) {
    var ls = STATIONS[si].lines;
    for (var k = 0; k < ls.length; k++) if (lineSet.indexOf(ls[k]) >= 0) return true;
    return false;
  }
  var dist = {}; dist[start] = 0;
  var q = [start];
  while (q.length) {
    var u = q.shift();
    STA_ADJ[u].forEach(function (v) {
      if (dist[v] !== undefined) return;
      if (!onLine(v)) return;
      dist[v] = dist[u] + 1;
      q.push(v);
    });
  }
  return dist;
}
function fastTransferAt(r, i) {
  var st = r.stops[i];
  if (!st.transferHere || !st.fromLine || !st.toLine) return null;
  var s = STATIONS[st.sta];
  var recs = ((NET.ft || {})[s.region + '|' + pnorm(s.name)] || []).filter(function (rec) {
    return rec[0].indexOf(st.fromLine) >= 0 && rec[1].indexOf(st.toLine) >= 0;
  });
  if (!recs.length) return null;

  // 새 노선의 방향: 환승이후역(rec[5]) = 갈아탄 뒤 첫 역 = 경로의 다음 정차역
  if (i + 1 < r.stops.length) {
    var nextShort = pnorm(STATIONS[r.stops[i + 1].sta].name);
    var byNext = recs.filter(function (rec) { return rec[5] === nextShort; });
    if (byNext.length) recs = byNext;
  }

  var resolved = recs.length === 1;
  if (!resolved && i > 0) {
    // 계통 노선 집합 = 매칭된 레코드들의 '탈때노선 후보' 합집합
    var lineSet = [];
    recs.forEach(function (rec) {
      rec[0].forEach(function (l) { if (lineSet.indexOf(l) < 0) lineSet.push(l); });
    });
    var dS = bfsLineHops(st.sta, lineSet);
    var dP = bfsLineHops(r.stops[i - 1].sta, lineSet);
    var byShort = {};
    STATIONS.forEach(function (x, xi) {
      if (x.region !== s.region) return;
      for (var k = 0; k < x.lines.length; k++) {
        if (lineSet.indexOf(x.lines[k]) >= 0) { byShort[pnorm(x.name)] = xi; return; }
      }
    });
    // 각 레코드를 앞/뒤/불명으로 분류한다. 종착역명이 결측(10.5%)이면 불명.
    var ahead = [], unknown = [];
    recs.forEach(function (rec) {
      var t = byShort[rec[2]];
      if (t === undefined || dP[t] === undefined || dS[t] === undefined) { unknown.push(rec); return; }
      if (dP[t] === (dP[st.sta] || 1) + dS[t]) ahead.push(rec);
      // 나머지는 진행 방향 뒤 → 탈락
    });
    if (ahead.length) {
      ahead.sort(function (a, b) { return (dS[byShort[a[2]]] || 9e9) - (dS[byShort[b[2]]] || 9e9); });
      recs = [ahead[0]];
      resolved = true;
    } else if (unknown.length === 1) {
      // 방향이 확인된 레코드가 전부 '뒤'라면, 남은 불명 하나가 진행 방향이다(소거법).
      recs = unknown;
      resolved = true;
    }
  }
  return {
    resolved: resolved,
    list: recs.slice(0, 2).map(function (rec) { return { dir: rec[2], car: rec[3], door: rec[4] }; })
  };
}

root.RailGraph = {
  STA_ADJ: STA_ADJ, articulationPoints: articulationPoints, regionFragility: regionFragility,
  NODES: NODES, EDGES: EDGES, ADJ: ADJ,
  STATIONS: STATIONS, STA_OF: STA_OF,
  shortest: shortest, toStops: toStops, diagnose: diagnose, fastTransferAt: fastTransferAt
};

})(typeof window !== 'undefined' ? window : globalThis);
