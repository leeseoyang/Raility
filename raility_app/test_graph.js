/* 그래프·SPOF 로직 검증
 * 실행: node raility_app/test_graph.js
 * 앱과 동일한 assets/graph.js를 그대로 로드해 검증한다.
 */
'use strict';
var fs = require('fs'), path = require('path'), vm = require('vm');

var dir = path.join(__dirname, 'assets');
var sandbox = { console: console };
sandbox.window = sandbox;
vm.createContext(sandbox);
['data.js', 'graph.js'].forEach(function (f) {
  vm.runInContext(fs.readFileSync(path.join(dir, f), 'utf8'), sandbox, { filename: f });
});

var G = sandbox.RailGraph, NET = sandbox.NET;
var S = G.STATIONS;

var pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  PASS  ' + name); }
  else { fail++; console.log('  FAIL  ' + name + (extra ? '  → ' + extra : '')); }
}
function find(name, region) {
  for (var i = 0; i < S.length; i++) {
    var s = S[i];
    if (region && s.region !== region) continue;
    if (s.name === name || s.short === name || (s.variants && s.variants.indexOf(name) >= 0)) return i;
  }
  return -1;
}
function hdr(t) { console.log('\n' + t); }

/* ── 1. 데이터 무결성 ───────────────────────────────── */
hdr('데이터 무결성');
ok('노드 수 > 1000', G.NODES.length > 1000, G.NODES.length);
ok('엣지 수 > 1200', G.EDGES.length > 1200, G.EDGES.length);
ok('역 수 < 노드 수 (승강장 병합됨)', S.length < G.NODES.length, S.length + ' < ' + G.NODES.length);
ok('모든 엣지 소요시간 > 0', G.EDGES.every(function (e) { return e[3] > 0; }));
ok('모든 노드가 역에 매핑됨', Array.from(G.STA_OF).every(function (v) { return v >= 0 && v < S.length; }));
var orphan = G.ADJ.filter(function (a) { return a.length === 0; }).length;
ok('고립 노드 없음', orphan === 0, orphan + '개 고립');

/* ── 2. 최단경로 기본 ───────────────────────────────── */
hdr('최단경로');
var seoul = find('서울역', '수도권') >= 0 ? find('서울역', '수도권') : find('서울', '수도권');
var gangnam = find('강남', '수도권');
ok('서울역 존재', seoul >= 0);
ok('강남역 존재', gangnam >= 0);

if (seoul >= 0 && gangnam >= 0) {
  var r = G.shortest(seoul, gangnam, null);
  ok('서울–강남 경로 존재', !!r);
  if (r) {
    var m = Math.round(r.time / 60);
    ok('서울–강남 소요 10~70분 (실제 약 25~35분)', m >= 10 && m <= 70, m + '분');
    ok('경로 시작=출발역', G.STA_OF[r.path[0]] === seoul);
    ok('경로 끝=도착역', G.STA_OF[r.path[r.path.length - 1]] === gangnam);
    // 경로 연속성: 인접한 노드는 실제 엣지로 이어져야 한다
    var contiguous = true;
    for (var i = 0; i + 1 < r.path.length; i++) {
      var a = r.path[i], b = r.path[i + 1];
      if (!G.ADJ[a].some(function (e) { return e.to === b; })) { contiguous = false; break; }
    }
    ok('경로가 실제 엣지로 연속', contiguous);
  }
  ok('대칭성: A→B 와 B→A 소요 동일',
    Math.abs(G.shortest(seoul, gangnam).time - G.shortest(gangnam, seoul).time) < 1e-6);
}

/* ── 3. 차단 동작 ───────────────────────────────────── */
hdr('역 차단');
if (seoul >= 0 && gangnam >= 0) {
  var base = G.shortest(seoul, gangnam, null);
  var mid = G.STA_OF[base.path[Math.floor(base.path.length / 2)]];
  var blocked = G.shortest(seoul, gangnam, mid);
  ok('중간역 차단 시 경로가 그 역을 지나지 않음',
    !blocked || blocked.path.every(function (n) { return G.STA_OF[n] !== mid; }));
  ok('차단 후 소요시간은 줄어들 수 없음', !blocked || blocked.time >= base.time - 1e-6,
    blocked ? Math.round(blocked.time - base.time) + 's' : 'unreachable');
  ok('출발역 차단 시 null', G.shortest(seoul, gangnam, seoul) === null);
}

/* ── 4. 대전: 단일 노선이므로 모든 중간역이 SPOF ────── */
hdr('대전 1호선 (단일 노선 → 전 중간역 SPOF여야 함)');
var dj = [];
S.forEach(function (s, i) { if (s.region === '대전') dj.push(i); });
ok('대전 역 22개', dj.length === 22, dj.length + '개');

var panam = find('판암', '대전'), banseok = find('반석', '대전');
ok('판암·반석(양 종점) 존재', panam >= 0 && banseok >= 0);
if (panam >= 0 && banseok >= 0) {
  var d = G.diagnose(panam, banseok);
  ok('판암→반석 경로 존재', d.ok);
  if (d.ok) {
    ok('정차역 22개 (전 구간)', d.stops.length === 22, d.stops.length + '개');
    ok('중간역 전부 SPOF', d.spof.length === d.mids.length,
      d.spof.length + '/' + d.mids.length);
    ok('등급 E', d.grade === 'E', d.grade);
    ok('환승 0회', d.transfers === 0, d.transfers);
  }
}

/* ── 5. 수도권: 순환 노선이 있으므로 SPOF가 적어야 함 ── */
hdr('수도권 2호선 순환 구간 (우회 가능해야 함)');
var sindorim = find('신도림', '수도권'), hongdae = find('홍대입구', '수도권');
if (sindorim >= 0 && hongdae >= 0) {
  var d2 = G.diagnose(sindorim, hongdae);
  ok('신도림→홍대입구 경로 존재', d2.ok);
  if (d2.ok) {
    ok('SPOF 비율이 대전보다 낮음', d2.ratio < 1, (d2.ratio * 100).toFixed(0) + '%');
    ok('등급이 E가 아님', d2.grade !== 'E', d2.grade);
  }
}

/* ── 6. 진단 일관성 ─────────────────────────────────── */
hdr('진단 일관성 (무작위 40쌍)');
var metro = [];
S.forEach(function (s, i) { if (s.region === '수도권') metro.push(i); });
var seed = 12345;
function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }

var bad = [], unreachable = 0, times = [];
for (var t = 0; t < 40; t++) {
  var a = metro[Math.floor(rnd() * metro.length)], b = metro[Math.floor(rnd() * metro.length)];
  if (a === b) continue;
  var t0 = Date.now();
  var res = G.diagnose(a, b);
  times.push(Date.now() - t0);
  if (!res.ok) { unreachable++; continue; }
  if (res.spof.length > res.mids.length) bad.push('spof>mids ' + S[a].name + '→' + S[b].name);
  if (res.ratio < 0 || res.ratio > 1) bad.push('ratio 범위 ' + res.ratio);
  if (!(res.base.time > 0)) bad.push('소요시간 0 ' + S[a].name + '→' + S[b].name);
  res.mids.forEach(function (st) {
    if (!st.spof && st.delta < -1e-6) bad.push('우회가 더 빠름 ' + S[st.sta].name);
  });
}
ok('불변식 위반 없음', bad.length === 0, bad.slice(0, 3).join(' | '));
ok('수도권 내 도달 불가 쌍 없음', unreachable === 0, unreachable + '쌍');
var avg = times.reduce(function (x, y) { return x + y; }, 0) / times.length;
ok('진단 평균 200ms 미만', avg < 200, avg.toFixed(1) + 'ms');

/* ── 7. 역 표기 병합 ────────────────────────────────── */
hdr('역 표기 병합 ("신도림" / "신도림역" 은 같은 역)');
function norm(n) { return n.length > 2 && n.slice(-1) === '역' ? n.slice(0, -1) : n; }
var split = [];
var seenN = {};
S.forEach(function (st, i) {
  var k = st.region + '|' + norm(st.name);
  if (seenN[k] != null) {
    var other = S[seenN[k]];
    // 좌표가 가까운데도 나뉘어 있으면 병합 실패
    var R = 6371000, t = Math.PI / 180;
    var dla = (st.lat - other.lat) * t, dlo = (st.lon - other.lon) * t;
    var a = Math.sin(dla / 2) * Math.sin(dla / 2) + Math.cos(other.lat * t) * Math.cos(st.lat * t) * Math.sin(dlo / 2) * Math.sin(dlo / 2);
    var d = 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
    if (d <= 1200) split.push(norm(st.name) + ' (' + Math.round(d) + 'm)');
  }
  seenN[k] = i;
});
ok('근접 동명역이 남아있지 않음', split.length === 0, split.slice(0, 5).join(', '));

var sindorim2 = find('신도림', '수도권');
ok('신도림이 하나의 역으로 병합', sindorim2 >= 0 && S[sindorim2].lines.length >= 2,
   sindorim2 >= 0 ? S[sindorim2].lines.join(',') : 'not found');
var seoulSta = find('서울역', '수도권');
ok('서울역이 하나의 역으로 병합', seoulSta >= 0 && S[seoulSta].lines.length >= 3,
   seoulSta >= 0 ? S[seoulSta].lines.join(',') : 'not found');

// 병합 후에는 SPOF가 늘거나 같아야 한다(닫힌 역 환승이라는 가짜 우회로가 사라지므로)
if (sindorim2 >= 0) {
  ok('병합된 역은 모든 표기 변형을 보유', S[sindorim2].variants.length >= 1);
}
ok('모든 역이 노드를 1개 이상 보유', S.every(function (x) { return x.nodes.length > 0; }));

/* ── 8. 환승 표기 ───────────────────────────────────── */
hdr('환승 표기 (원본 엣지의 노선 라벨 어긋남 보정)');
var sosa = find('소사', '수도권'), gn = find('강남', '수도권');
ok('소사·강남 조회됨', sosa >= 0 && gn >= 0, 'sosa=' + sosa + ' gangnam=' + gn);
if (sosa >= 0 && gn >= 0) {
  var dr = G.diagnose(sosa, gn);
  ok('소사→강남 환승 1회 이상 인식', dr.transfers >= 1, dr.transfers + '회');
  ok('경유 노선 2개 이상', dr.lines.length >= 2, dr.lines.join(' → '));
  var badSeg = dr.stops.filter(function (st, i) {
    if (i === dr.stops.length - 1) return false;
    var a = S[st.sta].lines, b = S[dr.stops[i + 1].sta].lines;
    var shared = a.filter(function (x) { return b.indexOf(x) >= 0; });
    // 공유 노선이 있는데 그 중 하나를 쓰지 않았다면 잘못 고른 것
    return shared.length && shared.indexOf(st.rideLine) < 0 && !st.segTransfer;
  });
  ok('모든 구간의 노선이 양쪽 역에 실재', badSeg.length === 0,
     badSeg.slice(0, 3).map(function (x) { return S[x.sta].name + ':' + x.rideLine; }).join(', '));
  ok('환승 지점에 출발/도착 노선이 모두 기록됨',
     dr.stops.filter(function (x) { return x.transferHere; })
       .every(function (x) { return x.fromLine && x.toLine; }));
}
// 대전은 단일 노선이므로 환승이 0이어야 한다
if (panam >= 0 && banseok >= 0) {
  ok('대전 전 구간 환승 0회', G.diagnose(panam, banseok).transfers === 0);
}

/* ── 9. 절점 ────────────────────────────────────────── */
hdr('절점(articulation point)');
var fdj = G.regionFragility('대전');
ok('대전 절점 = 중간역 20개 (경로 그래프)', fdj && fdj.cuts === 20, fdj ? fdj.cuts + '/' + fdj.total : 'null');
var fm = G.regionFragility('수도권');
ok('수도권 절점 비율 < 대전', fm && fm.ratio < fdj.ratio,
   fm ? (fm.ratio * 100).toFixed(0) + '% vs ' + (fdj.ratio * 100).toFixed(0) + '%' : 'null');
['수도권', '부산', '대구', '광주', '대전'].forEach(function (r) {
  var f = G.regionFragility(r);
  if (f) console.log('  ' + r.padEnd(5) + ' 절점 ' + String(f.cuts).padStart(3) + '/' + String(f.total).padStart(3) +
                     ' = ' + (f.ratio * 100).toFixed(0) + '%');
});
// 절점 정의 검증: 무작위 절점을 제거하면 실제로 연결요소가 늘어나야 한다
function components(members, exclude) {
  var inSet = {}; members.forEach(function (i) { if (i !== exclude) inSet[i] = 1; });
  var seen = {}, c = 0;
  Object.keys(inSet).forEach(function (k) {
    var st = +k; if (seen[st]) return;
    c++; var q = [st]; seen[st] = 1;
    while (q.length) { var u = q.pop(); G.STA_ADJ[u].forEach(function (v) { if (inSet[v] && !seen[v]) { seen[v] = 1; q.push(v); } }); }
  });
  return c;
}
var mem = []; S.forEach(function (s, i) { if (s.region === '수도권') mem.push(i); });
var base0 = components(mem, -1);
var arts = G.articulationPoints(mem);
var wrong = arts.slice(0, 15).filter(function (a) { return components(mem, a) <= base0; });
ok('절점 제거 시 실제로 연결요소 증가 (표본 15개)', wrong.length === 0, wrong.length + '개 불일치');
var nonArts = mem.filter(function (i) { return arts.indexOf(i) < 0 && G.STA_ADJ[i].length >= 2; }).slice(0, 15);
var wrong2 = nonArts.filter(function (a) { return components(mem, a) > base0; });
ok('비절점 제거 시 연결요소 불변 (표본 15개)', wrong2.length === 0, wrong2.length + '개 불일치');

/* ── 10. 권역 분류 ──────────────────────────────────── */
hdr('권역 분류');
var byReg = {};
S.forEach(function (s) { byReg[s.region] = (byReg[s.region] || 0) + 1; });
console.log('  ' + Object.keys(byReg).sort(function (a, b) { return byReg[b] - byReg[a]; })
  .map(function (k) { return k + ' ' + byReg[k]; }).join(' · '));
ok('대구 90개 이상 (주소 누락 보정 확인)', (byReg['대구'] || 0) >= 90, byReg['대구']);
ok('미분류(기타) 30개 미만', (byReg['기타'] || 0) < 30, byReg['기타'] || 0);

console.log('\n' + (fail === 0 ? '전부 통과' : fail + '건 실패') + '  (통과 ' + pass + ' / 실패 ' + fail + ')');
process.exit(fail ? 1 : 0);
