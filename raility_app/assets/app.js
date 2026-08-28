/* Raility — 도시철도 단일고장점(SPOF) 진단
 *
 * 핵심 아이디어: 지도 앱은 "지금 다니는 길"만 알려준다.
 * 이 앱은 "그 길 중 어느 역 하나가 멈추면 통째로 끊기는가"를 계산한다.
 *
 * 모든 계산은 클라이언트에서 수행한다(서버 없음).
 * 역 하나를 그래프에서 제거한 뒤 최단경로를 다시 구해, 경로가 사라지면 단일고장점으로 판정한다.
 */
(function () {
'use strict';

var NET = window.NET;
var G = window.RailGraph;
var NODES = G.NODES, EDGES = G.EDGES, ADJ = G.ADJ;
var STATIONS = G.STATIONS, STA_OF = G.STA_OF;
var shortest = G.shortest, diagnose = G.diagnose;
var COLORS = NET.colors;
var IMPACT = NET.impact || {}, SEG = NET.seg || [], PRIO = NET.prio || [];

/* 노드 집합의 승강장 접근성 요약. ac = [위험도, 안전발판없음, 승강장연결안됨, 스크린도어없음, 최대역층]
 * 자료가 있는 노드가 하나도 없으면 null — '자료 없음'은 '장벽 없음'과 다르므로 0으로 채우지 않는다. */
function accOf(nodeIdxs) {
  var best = null;
  (nodeIdxs || []).forEach(function (i) {
    var a = NODES[i] && NODES[i].ac;
    if (a && (!best || a[0] > best[0])) best = a;
  });
  return best;
}
var ACC_LABEL = ['안전발판 없음', '승강장 미연결', '스크린도어 없음'];

var GRADE_TEXT = {
  A: ['우회 가능', '경로 위 어느 역이 멈춰도 돌아갈 길이 있습니다.'],
  B: ['대체로 안전', '대부분 우회할 수 있지만 일부 역은 대체 경로가 없습니다.'],
  C: ['주의 필요', '경로의 상당 부분이 특정 역에 의존합니다.'],
  D: ['취약', '대부분의 역이 끊기면 우회할 수 없습니다.'],
  E: ['매우 취약', '사실상 모든 중간역이 단일고장점입니다. 대체 경로가 없습니다.']
};

/* ─────────────────────────────────────────────────────────────
 * 4. 유틸
 * ───────────────────────────────────────────────────────────── */

var $ = function (s, r) { return (r || document).querySelector(s); };
var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; }); }
function mins(sec) { return Math.round(sec / 60); }
function fmtMin(sec) { var m = Math.round(sec / 60); return m >= 60 ? (Math.floor(m / 60) + '시간 ' + (m % 60) + '분') : (m + '분'); }
function comma(n) { return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
function lineColor(l) { return COLORS[l] || '#6b7280'; }

var toastEl;
function toast(msg) {
  if (!toastEl) { toastEl = el('div', 'toast'); document.body.appendChild(toastEl); }
  toastEl.textContent = msg; toastEl.classList.add('on');
  clearTimeout(toastEl._t); toastEl._t = setTimeout(function () { toastEl.classList.remove('on'); }, 1900);
}

/* ─────────────────────────────────────────────────────────────
 * 5. 상태
 * ───────────────────────────────────────────────────────────── */

var state = {
  region: localStorage.getItem('rl.region') || '수도권',
  from: null, to: null, result: null,
  mapRegion: localStorage.getItem('rl.region') || '수도권'
};
try {
  var saved = JSON.parse(localStorage.getItem('rl.od') || 'null');
  if (saved && STATIONS[saved.f] && STATIONS[saved.t]) { state.from = saved.f; state.to = saved.t; }
} catch (e) {}

var REGIONS = (function () {
  var c = {};
  STATIONS.forEach(function (s) { c[s.region] = (c[s.region] || 0) + 1; });
  return Object.keys(c).filter(function (r) { return c[r] >= 10; })
    .sort(function (a, b) { return c[b] - c[a]; });
})();

/* ─────────────────────────────────────────────────────────────
 * 6. 검색 시트
 * ───────────────────────────────────────────────────────────── */

var sheet = { target: null };

function openSearch(which) {
  sheet.target = which;
  $('#sheetTitle').textContent = which === 'from' ? '출발역 선택' : '도착역 선택';
  var inp = $('#searchInput');
  inp.value = '';
  renderSearch('');
  $('#sheet').classList.add('on');
  setTimeout(function () { inp.focus(); }, 60);
}
function closeSearch() { $('#sheet').classList.remove('on'); $('#searchInput').blur(); }

function renderSearch(q) {
  var list = $('#sheetList');
  list.innerHTML = '';
  q = q.trim();

  var pool;
  if (!q) {
    pool = STATIONS.map(function (s, i) { return i; })
      .filter(function (i) { return STATIONS[i].region === state.region; })
      .sort(function (a, b) { return STATIONS[b].demand - STATIONS[a].demand; })
      .slice(0, 40);
    var hint = el('div', 'eyebrow', state.region + ' · 이용객 많은 역');
    hint.style.padding = '0 16px'; hint.style.margin = '4px 0 8px';
    list.appendChild(hint);
  } else {
    var scored = [];
    for (var i = 0; i < STATIONS.length; i++) {
      var s = STATIONS[i];
      var p = -1;
      // 표기 변형(예: "신도림" / "신도림역") 전부를 검색 대상으로 둔다.
      for (var vi = 0; vi < s.variants.length; vi++) {
        var hit = s.variants[vi].indexOf(q);
        if (hit >= 0 && (p < 0 || hit < p)) p = hit;
      }
      if (p < 0 && s.short.indexOf(q) === 0) p = 0;
      if (p < 0) continue;
      scored.push([i, (p === 0 ? 0 : 1) + (s.region === state.region ? 0 : 0.5) - Math.min(s.demand / 1e6, 0.4)]);
    }
    scored.sort(function (a, b) { return a[1] - b[1]; });
    pool = scored.slice(0, 60).map(function (x) { return x[0]; });
  }

  if (!pool.length) {
    list.appendChild(el('div', 'empty-hint', '"' + q + '" 과(와) 일치하는 역이 없습니다.'));
    return;
  }

  var frag = document.createDocumentFragment();
  pool.forEach(function (si) {
    var s = STATIONS[si];
    var b = el('button', 'row');
    var main = el('div', 'row-main');
    main.appendChild(el('div', 'row-name', s.name));
    var sub = el('div', 'row-sub');
    sub.textContent = s.region + ' · ' + s.lines.join(', ');
    main.appendChild(sub);
    b.appendChild(main);
    if (s.transfer) {
      var c = el('span', 'chip', '환승');
      c.style.background = 'var(--ink-3)';
      b.appendChild(c);
    }
    b.onclick = function () { pickStation(si); };
    frag.appendChild(b);
  });
  list.appendChild(frag);
}

function pickStation(si) {
  if (sheet.target === 'from') {
    if (state.to === si) { toast('출발역과 도착역이 같습니다'); return; }
    state.from = si;
  } else {
    if (state.from === si) { toast('출발역과 도착역이 같습니다'); return; }
    state.to = si;
  }
  closeSearch();
  syncOD();
  if (state.from != null && state.to != null) runDiagnose();
}

function syncOD() {
  var f = $('#odFrom'), t = $('#odTo');
  if (state.from != null) {
    var s = STATIONS[state.from];
    f.className = 'od-name';
    f.innerHTML = esc(s.name) + '<small>' + esc(s.lines[0]) + (s.lines.length > 1 ? ' 외 ' + (s.lines.length - 1) : '') + '</small>';
  } else { f.className = 'od-name empty'; f.textContent = '출발역 선택'; }
  if (state.to != null) {
    var s2 = STATIONS[state.to];
    t.className = 'od-name';
    t.innerHTML = esc(s2.name) + '<small>' + esc(s2.lines[0]) + (s2.lines.length > 1 ? ' 외 ' + (s2.lines.length - 1) : '') + '</small>';
  } else { t.className = 'od-name empty'; t.textContent = '도착역 선택'; }
  if (state.from != null && state.to != null) localStorage.setItem('rl.od', JSON.stringify({ f: state.from, t: state.to }));
}

/* ─────────────────────────────────────────────────────────────
 * 7. 진단 화면
 * ───────────────────────────────────────────────────────────── */

// 처음 열었을 때 바로 눌러볼 수 있는 대표 구간(권역 전 구간을 훑는 종단 경로).
var SUGGESTED = [
  ['대전', '판암', '반석'],
  ['수도권', '소사', '강남'],
  ['수도권', '인천', '청량리'],
  ['부산', '다대포해수욕장', '노포'],
  ['대구', '설화명곡', '하양(대구가톨릭대)'],
  ['광주', '평동', '녹동']
];

function renderSuggestions() {
  var out = $('#result');
  var found = [];
  SUGGESTED.forEach(function (s) {
    var a = lookupStation(s[1], s[0]), b = lookupStation(s[2], s[0]);
    if (a != null && b != null && a !== b) found.push([s[0], a, b]);
  });
  if (!found.length) return;

  found.sort(function (x, y) { return (x[0] === state.region ? -1 : 0) - (y[0] === state.region ? -1 : 0); });

  out.appendChild(sectionTitle('바로 살펴보기'));
  var rows = el('div', 'rows');
  found.forEach(function (f) {
    var a = STATIONS[f[1]], b = STATIONS[f[2]];
    var btn = el('button', 'row');
    var m = el('div', 'row-main');
    m.appendChild(el('div', 'row-name', a.name + ' → ' + b.name));
    m.appendChild(el('div', 'row-sub', f[0] + ' 종단 구간'));
    btn.appendChild(m);
    var chev = el('div', 'row-val');
    chev.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--ink-4)" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>';
    btn.appendChild(chev);
    btn.onclick = function () { state.from = f[1]; state.to = f[2]; syncOD(); runDiagnose(); };
    rows.appendChild(btn);
  });
  out.appendChild(rows);

  var n = el('p', 'note');
  n.style.margin = '12px 2px 0';
  n.textContent = '출발·도착역을 직접 고르면 내 통근 경로를 진단할 수 있습니다.';
  out.appendChild(n);
}

/** 이름으로 역 찾기(권역 우선, 표기 변형 허용) */
function lookupStation(name, region) {
  var any = null;
  for (var i = 0; i < STATIONS.length; i++) {
    var s = STATIONS[i];
    if (s.name !== name && s.short !== name && s.variants.indexOf(name) < 0) continue;
    if (!region || s.region === region) return i;
    if (any == null) any = i;
  }
  return any;
}

function runDiagnose() {
  var out = $('#result');
  out.innerHTML = '';
  if (state.from == null || state.to == null) { renderSuggestions(); return; }

  var t0 = performance.now();
  var r = diagnose(state.from, state.to);
  state.result = r;

  if (!r.ok) {
    var w = el('div', 'verdict');
    w.innerHTML = '<div class="verdict-head"><h2>연결된 경로가 없습니다</h2>' +
      '<p>두 역은 이 데이터셋의 철도망에서 서로 이어져 있지 않습니다. 같은 권역의 역을 선택해 보세요.</p></div>';
    out.appendChild(w);
    return;
  }

  var gt = GRADE_TEXT[r.grade];
  var v = el('div', 'verdict');
  v.innerHTML =
    '<div class="verdict-top">' +
      '<div class="grade" data-g="' + r.grade + '">' + r.grade + '</div>' +
      '<div class="verdict-head"><h2>' + gt[0] + '</h2><p>' + gt[1] + '</p></div>' +
    '</div>' +
    '<dl class="metrics">' +
      '<div class="metric"><dt>소요시간</dt><dd class="num">' + mins(r.base.time) + '<i>분</i></dd></div>' +
      '<div class="metric"><dt>정차역</dt><dd class="num">' + r.stops.length + '<i>개</i></dd></div>' +
      '<div class="metric"><dt>단일고장점</dt><dd class="num">' + r.spof.length + '<i>개</i></dd></div>' +
    '</dl>';
  out.appendChild(v);

  // 요약 문장
  var lead = el('p', 'note');
  lead.style.margin = '12px 2px 0';
  if (r.spof.length === 0) {
    lead.innerHTML = '이 경로의 중간역 <b>' + r.mids.length + '개</b>는 모두 우회 가능합니다. ' +
      (r.maxDelta > 0 ? '가장 불리한 경우에도 <b>' + mins(r.maxDelta) + '분</b>만 더 걸립니다.' : '');
  } else {
    lead.innerHTML = '중간역 <b>' + r.mids.length + '개</b> 중 <b>' + r.spof.length + '개</b>가 멈추면 ' +
      '<b>이 경로로는 목적지에 갈 수 없습니다.</b>' +
      (r.detour.length ? ' 나머지 ' + r.detour.length + '개 역은 우회 시 최대 ' + mins(r.maxDelta) + '분이 더 걸립니다.' : '');
  }
  out.appendChild(lead);

  // 교통약자 관점 — 경로 위 승강장 장벽 집계
  var accCnt = [0, 0, 0], accNone = 0;
  r.stops.forEach(function (st) {
    var a = accOf(st.nodes);
    if (!a) { accNone++; return; }
    for (var k = 0; k < 3; k++) if (a[k + 1]) accCnt[k]++;
  });
  if (accCnt[0] + accCnt[1] + accCnt[2] + accNone > 0) {
    out.appendChild(sectionTitle('교통약자 관점'));
    var card = el('div', 'acc-card');
    var ICONS = [svgRamp(), svgLink(), svgDoor()];
    ACC_LABEL.forEach(function (lb, k) {
      if (!accCnt[k]) return;
      var row = el('div', 'acc-row');
      var ic = el('div', 'ic'); ic.style.background = 'var(--risk-2)'; ic.innerHTML = ICONS[k];
      row.appendChild(ic);
      row.appendChild(el('div', 'tx', lb + ' 역'));
      var ct = el('div', 'ct');
      ct.innerHTML = '<span class="num">' + accCnt[k] + '</span><small>개</small>';
      row.appendChild(ct);
      card.appendChild(row);
    });
    if (accNone) {
      var row2 = el('div', 'acc-row');
      var ic2 = el('div', 'ic'); ic2.style.background = 'var(--ink-4)'; ic2.innerHTML = svgQ();
      row2.appendChild(ic2);
      row2.appendChild(el('div', 'tx', '승강장 정보 미공개 역'));
      var ct2 = el('div', 'ct');
      ct2.innerHTML = '<span class="num">' + accNone + '</span><small>개</small>';
      row2.appendChild(ct2);
      card.appendChild(row2);
    }
    out.appendChild(card);
    var accNote = el('p', 'note');
    accNote.style.margin = '8px 2px 0';
    accNote.textContent = '국가철도공단 승강장 정보 기준. 안전발판이 없으면 휠체어·유아차 단독 승하차가 어렵고, ' +
      '승강장이 미연결이면 반대 방향으로 가려면 개찰구를 나가야 합니다.';
    out.appendChild(accNote);
  }

  // 경로 스트립
  out.appendChild(sectionTitle('경로 상세'));
  out.appendChild(renderStrip(r));

  // 우선 대비 역
  if (r.spof.length) {
    out.appendChild(sectionTitle('먼저 대비해야 할 역'));
    var rows = el('div', 'rows');
    r.spof.slice()
      .sort(function (a, b) { return STATIONS[b.sta].demand - STATIONS[a.sta].demand; })
      .slice(0, 6)
      .forEach(function (st, k) {
        var s = STATIONS[st.sta];
        var b = el('button', 'row');
        b.appendChild(el('div', 'row-rank', String(k + 1)));
        var m = el('div', 'row-main');
        m.appendChild(el('div', 'row-name', s.name));
        m.appendChild(el('div', 'row-sub', s.lines.join(', ')));
        b.appendChild(m);
        var val = el('div', 'row-val');
        val.innerHTML = '<span class="num">' + comma(s.demand) + '</span><small>일평균 승하차</small>';
        b.appendChild(val);
        b.onclick = function () { openStation(st.sta); };
        rows.appendChild(b);
      });
    out.appendChild(rows);
  }

  var share = el('button', 'cta');
  share.style.marginTop = '20px';
  share.style.background = 'var(--surface)';
  share.style.color = 'var(--ink-1)';
  share.style.border = '1px solid var(--line-strong)';
  share.textContent = '이 진단 결과 공유하기';
  share.onclick = shareLink;
  out.appendChild(share);

  var el2 = el('p', 'note');
  el2.style.margin = '14px 2px 0';
  el2.textContent = '계산 ' + (performance.now() - t0).toFixed(0) + 'ms · 역 ' + STATIONS.length +
                    '개, 구간 ' + EDGES.length + '개 그래프에서 역별 재탐색으로 산출했습니다.';
  out.appendChild(el2);
}

function sectionTitle(t) { return el('div', 'eyebrow', t); }

function renderStrip(r) {
  var wrap = el('div', 'strip');
  r.stops.forEach(function (st, i) {
    var s = STATIONS[st.sta];
    var isEnd = i === 0 || i === r.stops.length - 1;
    var row = el('div', 'stop' + (st.spof ? ' spof' : '') + (isEnd ? ' terminal' : ''));

    var rail = el('div', 'stop-rail');
    var bar = el('div', 'bar');
    bar.style.background = lineColor(st.lines[0]);
    if (i === 0) bar.style.marginTop = '18px';
    if (i === r.stops.length - 1) bar.style.marginBottom = '18px';
    rail.appendChild(bar);
    var pt = el('div', 'pt');
    if (isEnd && !st.spof) pt.style.borderColor = lineColor(st.lines[0]);
    rail.appendChild(pt);
    row.appendChild(rail);

    var body = el('div', 'stop-body');
    var nm = el('div', 'stop-name');
    nm.innerHTML = esc(s.name) + '<span class="ln" style="color:' + lineColor(st.lines[0]) + '">' + esc(st.lines[0]) + '</span>';
    body.appendChild(nm);

    if (st.transferHere && st.fromLine && st.toLine) {
      body.appendChild(el('span', 'xfer-note', st.fromLine + ' → ' + st.toLine + ' 환승'));
      // 빠른환승: 내리는 열차의 몇 번째 칸·문이 환승 통로와 가장 가까운가
      var ft = G.fastTransferAt(r, i);
      if (ft) {
        var txt = ft.list.map(function (x) {
          // 종착역명 결측 레코드는 방면 라벨 없이 칸-문만 표시한다
          return x.car + '-' + x.door + (ft.resolved || !x.dir ? '' : ' (' + x.dir + ' 방면)');
        }).join(' · ');
        body.appendChild(el('span', 'ft-tag', '빠른 환승 ' + txt));
      }
    }

    if (st.spof) {
      var tag = el('span', 'spof-tag');
      tag.innerHTML = svgAlert() + ' 이 역이 멈추면 우회 불가';
      body.appendChild(tag);
    }
    // 승강장 장벽 — SPOF 와 별개 축이므로 함께 표시한다.
    var ac = accOf(st.nodes);
    if (ac) {
      ACC_LABEL.forEach(function (lb, k) {
        if (ac[k + 1]) body.appendChild(el('span', 'acc-tag', lb));
      });
    } else {
      body.appendChild(el('span', 'acc-tag none', '승강장 정보 없음'));
    }
    if (!st.spof && st.delta > 60) {
      // 같은 우회 시간이 연달아 나오면 첫 역에만 표시해 화면을 어지럽히지 않는다.
      var prev = r.stops[i - 1];
      var sameRun = prev && !prev.spof && prev.delta > 60 && mins(prev.delta) === mins(st.delta);
      if (!sameRun) {
        var d = el('span', 'detour-tag');
        d.textContent = '우회 시 +' + mins(st.delta) + '분';
        body.appendChild(d);
      }
    }
    row.appendChild(body);
    row.onclick = function () { openStation(st.sta); };
    wrap.appendChild(row);
  });
  return wrap;
}

function svgAlert() {
  return '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" ' +
    'stroke-linecap="round"><path d="M12 8v5"/><path d="M12 17h.01"/>' +
    '<path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>';
}
/* 접근성 카드 아이콘 — 휠체어(발판) / 연결(승강장) / 문(스크린도어) / 물음표(자료 없음) */
function svgRamp() {
  return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<circle cx="12" cy="4.5" r="1.8"/><path d="M11 7.5v5h5l2.5 6"/><path d="M11 9.5h4"/>' +
    '<path d="M9.5 11.5a5 5 0 1 0 6.4 6.9"/></svg>';
}
function svgLink() {
  return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">' +
    '<path d="M9 12h6"/><path d="M8.5 8.5H7a4 4 0 0 0 0 8h1.5" transform="translate(0 -0.5)"/>' +
    '<path d="M15.5 8.5H17a4 4 0 0 1 0 8h-1.5" transform="translate(0 -0.5)"/></svg>';
}
function svgDoor() {
  return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M12 3v18"/><path d="m8.5 9 1.5 3-1.5 3"/><path d="m15.5 9-1.5 3 1.5 3"/></svg>';
}
function svgQ() {
  return '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">' +
    '<path d="M9.3 9a2.8 2.8 0 1 1 3.9 2.6c-.9.4-1.2 1-1.2 1.9"/><path d="M12 17h.01"/></svg>';
}

/* ─────────────────────────────────────────────────────────────
 * 8. 역 상세
 * ───────────────────────────────────────────────────────────── */

function openStation(si, fromSearch) {
  var s = STATIONS[si];
  $('#sheetTitle').textContent = '역 정보';
  var list = $('#sheetList');
  list.innerHTML = '';
  $('#searchWrap').style.display = 'none';

  var hero = el('div', 'detail-hero');
  hero.innerHTML = '<h2>' + esc(s.name) + '</h2><div class="meta">' +
    esc(s.region) + ' · ' + s.lines.map(function (l) {
      return '<span style="color:' + lineColor(l) + ';font-weight:600">' + esc(l) + '</span>';
    }).join(' · ') + '</div>';
  list.appendChild(hero);

  // 이 역이 멈추면?
  var best = null;
  s.nodes.forEach(function (ni) { var im = IMPACT[ni]; if (im && (!best || im[0] > best[0])) best = im; });

  var kv = el('dl', 'kv');
  function add(k, v) { kv.appendChild(el('dt', null, k)); kv.appendChild(el('dd', null, v)); }
  add('일평균 승하차', comma(s.demand) + '명');
  add('연결 노선', s.lines.length + '개');
  if (best) {
    add('제거 시 효율 저하', best[0].toFixed(2) + '%');
    add('제거 시 고립 역 수', best[2] > 0 ? best[2] + '개' : '없음');
  }
  var ac = accOf(s.nodes);
  if (ac) {
    var bars = ACC_LABEL.filter(function (_, k) { return ac[k + 1]; });
    add('승강장 장벽', bars.length ? bars.join(' · ') : '확인된 장벽 없음');
    if (ac[4] > 0) add('승강장 층', '지하/지상 ' + ac[4] + '층');
  } else {
    add('승강장 장벽', '정보 미공개 노선');
  }
  if (s.addr) add('주소', s.addr);
  list.appendChild(kv);

  var back = el('div');
  back.style.padding = '14px 16px 20px';
  // 검색 도중 들어온 경우에만 검색으로 되돌린다. 경로·지도에서 들어왔으면 그냥 닫는다.
  var b = el('button', 'cta', fromSearch ? '역 검색으로 돌아가기' : '닫기');
  b.onclick = fromSearch
    ? function () { $('#searchWrap').style.display = ''; openSearch(sheet.target || 'from'); }
    : function () { closeSearch(); $('#searchWrap').style.display = ''; };
  back.appendChild(b);
  list.appendChild(back);

  $('#sheet').classList.add('on');
}

/* ─────────────────────────────────────────────────────────────
 * 9. SVG 지도 (외부 의존 없음)
 * ───────────────────────────────────────────────────────────── */

var mapView = { k: 1, x: 0, y: 0 };

function renderMap() {
  var host = $('#map');
  host.innerHTML = '';
  var reg = state.mapRegion;
  var idxs = [];
  NODES.forEach(function (n, i) { if (n.r === reg) idxs.push(i); });
  if (!idxs.length) { host.appendChild(el('div', 'empty-hint', '표시할 역이 없습니다.')); return; }

  var W = host.clientWidth || 360, H = host.clientHeight || 420, PAD = 26;
  var laMin = Infinity, laMax = -Infinity, loMin = Infinity, loMax = -Infinity;
  idxs.forEach(function (i) {
    var n = NODES[i];
    if (n.la < laMin) laMin = n.la; if (n.la > laMax) laMax = n.la;
    if (n.lo < loMin) loMin = n.lo; if (n.lo > loMax) loMax = n.lo;
  });
  // 위도에 따른 경도 축소 보정
  var midLa = (laMin + laMax) / 2, kx = Math.cos(midLa * Math.PI / 180);
  var spanX = (loMax - loMin) * kx, spanY = (laMax - laMin);
  var sc = Math.min((W - PAD * 2) / (spanX || 1e-6), (H - PAD * 2) / (spanY || 1e-6));
  var offX = (W - spanX * sc) / 2, offY = (H - spanY * sc) / 2;
  function px(n) { return offX + (n.lo - loMin) * kx * sc; }
  function py(n) { return offY + (laMax - n.la) * sc; }

  var NS = 'http://www.w3.org/2000/svg';
  var svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  svg.setAttribute('width', '100%'); svg.setAttribute('height', '100%');
  svg.style.display = 'block'; svg.style.touchAction = 'none';
  var g = document.createElementNS(NS, 'g');
  svg.appendChild(g);

  // 구간 취약성 조회표
  var segBy = {};
  SEG.forEach(function (r) { segBy[r[0]] = r; });

  var inSet = {};
  idxs.forEach(function (i) { inSet[i] = 1; });

  // 구간
  EDGES.forEach(function (e, ei) {
    if (!inSet[e[0]] || !inSet[e[1]]) return;
    var a = NODES[e[0]], b = NODES[e[1]];
    var ln = document.createElementNS(NS, 'line');
    ln.setAttribute('x1', px(a).toFixed(1)); ln.setAttribute('y1', py(a).toFixed(1));
    ln.setAttribute('x2', px(b).toFixed(1)); ln.setAttribute('y2', py(b).toFixed(1));
    var sv = segBy[ei];
    var cut = sv && sv[3] === 1;
    if (e[2] === 1) {                       // 환승
      ln.setAttribute('stroke', 'var(--ink-5)');
      ln.setAttribute('stroke-width', '1.2');
      ln.setAttribute('stroke-dasharray', '2 2.5');
    } else {
      ln.setAttribute('stroke', cut ? 'var(--risk-3)' : lineColor(a.l));
      ln.setAttribute('stroke-width', cut ? '3.4' : '2.4');
      ln.setAttribute('stroke-linecap', 'round');
      if (cut) ln.setAttribute('opacity', '.92');
    }
    g.appendChild(ln);
  });

  // 역
  var maxD = 1;
  idxs.forEach(function (i) { if (NODES[i].d > maxD) maxD = NODES[i].d; });
  var drawn = {};
  idxs.forEach(function (i) {
    var si = STA_OF[i];
    if (drawn[si]) return; drawn[si] = 1;
    var s = STATIONS[si], n = NODES[i];
    var im = null;
    s.nodes.forEach(function (k) { var m = IMPACT[k]; if (m && (!im || m[0] > im[0])) im = m; });
    var sep = im && im[3] === 1;
    var r = 2.4 + Math.sqrt(s.demand / maxD) * 4.4;
    var c = document.createElementNS(NS, 'circle');
    c.setAttribute('cx', px(n).toFixed(1)); c.setAttribute('cy', py(n).toFixed(1));
    c.setAttribute('r', r.toFixed(1));
    c.setAttribute('fill', sep ? 'var(--risk-3)' : 'var(--surface)');
    c.setAttribute('stroke', sep ? 'var(--risk-3)' : (s.transfer ? 'var(--ink-1)' : lineColor(n.l)));
    c.setAttribute('stroke-width', s.transfer ? '2' : '1.4');
    c.style.cursor = 'pointer';
    c.addEventListener('click', function (ev) { ev.stopPropagation(); showMapTip(si, px(n), py(n)); });
    g.appendChild(c);
  });

  host.appendChild(svg);

  // 팬/줌
  mapView = { k: 1, x: 0, y: 0 };
  function apply() { g.setAttribute('transform', 'translate(' + mapView.x + ',' + mapView.y + ') scale(' + mapView.k + ')'); }
  var pts = {};
  var startDist = 0, startK = 1, last = null;
  svg.addEventListener('pointerdown', function (e) { svg.setPointerCapture(e.pointerId); pts[e.pointerId] = { x: e.clientX, y: e.clientY }; last = { x: e.clientX, y: e.clientY }; startK = mapView.k; startDist = pinch(); });
  svg.addEventListener('pointermove', function (e) {
    if (!pts[e.pointerId]) return;
    pts[e.pointerId] = { x: e.clientX, y: e.clientY };
    var ids = Object.keys(pts);
    if (ids.length >= 2) {
      var d = pinch();
      if (startDist > 0) { mapView.k = Math.max(0.6, Math.min(9, startK * d / startDist)); apply(); }
    } else if (last) {
      mapView.x += e.clientX - last.x; mapView.y += e.clientY - last.y;
      last = { x: e.clientX, y: e.clientY }; apply();
    }
  });
  function endPt(e) { delete pts[e.pointerId]; last = null; startDist = pinch(); startK = mapView.k; }
  svg.addEventListener('pointerup', endPt);
  svg.addEventListener('pointercancel', endPt);
  svg.addEventListener('wheel', function (e) {
    e.preventDefault();
    mapView.k = Math.max(0.6, Math.min(9, mapView.k * (e.deltaY < 0 ? 1.12 : 0.89))); apply();
  }, { passive: false });
  function pinch() {
    var ids = Object.keys(pts); if (ids.length < 2) return 0;
    var a = pts[ids[0]], b = pts[ids[1]];
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  // 통계 줄
  var cuts = 0;
  EDGES.forEach(function (e, ei) { if (inSet[e[0]] && inSet[e[1]] && segBy[ei] && segBy[ei][3] === 1) cuts++; });
  $('#mapStat').innerHTML = '역 <b class="num">' + Object.keys(drawn).length + '</b>개 · ' +
    '단절 유발 구간 <b class="num">' + cuts + '</b>개';
}

function showMapTip(si) { openStation(si); }

/* ─────────────────────────────────────────────────────────────
 * 10. 대전 뷰
 * ───────────────────────────────────────────────────────────── */

function renderDaejeon() {
  var host = $('#viewDaejeon');
  host.innerHTML = '';

  var dj = [];
  STATIONS.forEach(function (s, i) { if (s.region === '대전') dj.push(i); });

  // 종점 두 곳을 찾아 그 사이 경로의 SPOF를 계산한다.
  var deg = {};
  dj.forEach(function (si) {
    var d = 0;
    STATIONS[si].nodes.forEach(function (n) { d += ADJ[n].filter(function (e) { return e.type === 0; }).length; });
    deg[si] = d;
  });
  var ends = dj.filter(function (si) { return deg[si] <= 1; });
  var a = ends[0] != null ? ends[0] : dj[0], b = ends[1] != null ? ends[1] : dj[dj.length - 1];
  var r = diagnose(a, b);

  var lead = el('div', 'stat-lead');
  var pct = r.ok && r.mids.length ? Math.round(r.spof.length / r.mids.length * 100) : 0;
  lead.innerHTML =
    '<div class="big num">' + pct + '<i>%</i></div>' +
    '<div class="cap">대전 도시철도 1호선 <b>' + esc(STATIONS[a].name) + ' → ' + esc(STATIONS[b].name) + '</b> 전 구간에서, ' +
    '중간역 ' + (r.ok ? r.mids.length : 0) + '개 중 <b>' + (r.ok ? r.spof.length : 0) + '개</b>가 ' +
    '멈추면 우회 경로가 존재하지 않습니다.</div>';
  host.appendChild(lead);

  var co = el('div', 'callout');
  co.style.marginTop = '12px';
  co.innerHTML = '대전은 운영 중인 도시철도가 <b>1호선 단일 노선</b>입니다. ' +
    '망에 순환이나 병렬 경로가 없어 중간역 어느 하나가 끊기면 그 지점을 우회할 방법이 구조적으로 없습니다. ' +
    '수도권처럼 노선이 겹치는 곳에서는 같은 사고가 나도 다른 노선으로 돌아갈 수 있습니다.';
  host.appendChild(co);

  // 권역 비교 — 절점(제거하면 망이 분리되는 역) 비율
  host.appendChild(sectionTitle('권역별 구조적 취약도'));
  var rows = el('div', 'rows');
  var comp = [];
  REGIONS.forEach(function (reg) {
    if (reg === '기타') return;
    var f = G.regionFragility(reg);
    if (f) comp.push(f);
  });
  comp.sort(function (x, y) { return y.ratio - x.ratio; });
  comp.forEach(function (c) {
    var pctv = Math.round(c.ratio * 100);
    var row = el('div', 'row');
    var m = el('div', 'row-main');
    m.appendChild(el('div', 'row-name', c.region));
    m.appendChild(el('div', 'row-sub', '역 ' + c.total + '개 중 절점 ' + c.cuts + '개'));
    var g = el('div', 'gauge');
    var bar = el('i');
    bar.style.width = Math.max(3, pctv) + '%';
    bar.style.background = pctv >= 75 ? 'var(--risk-3)' : pctv >= 40 ? 'var(--risk-2)' : 'var(--ink-3)';
    g.appendChild(bar); m.appendChild(g);
    row.appendChild(m);
    var v = el('div', 'row-val');
    v.innerHTML = '<span class="num">' + pctv + '%</span><small>절점 비율</small>';
    row.appendChild(v);
    rows.appendChild(row);
  });
  host.appendChild(rows);
  var n1 = el('p', 'note'); n1.style.margin = '9px 2px 0';
  n1.innerHTML = '<b>절점</b>은 그 역을 빼면 철도망이 둘 이상으로 쪼개지는 역입니다. ' +
    '비율이 높을수록 한 역의 사고가 망 전체를 끊을 가능성이 큽니다. ' +
    '권역 전체 위상을 한 번에 계산한 값이라 특정 경로 선택에 좌우되지 않습니다.';
  host.appendChild(n1);

  // 대전 역별
  host.appendChild(sectionTitle('대전 1호선 역별 이용 규모'));
  var rows2 = el('div', 'rows');
  dj.slice().sort(function (x, y) { return STATIONS[y].demand - STATIONS[x].demand; })
    .forEach(function (si, k) {
      var s = STATIONS[si];
      var isSpof = r.ok && r.spof.some(function (st) { return st.sta === si; });
      var btn = el('button', 'row');
      btn.appendChild(el('div', 'row-rank', String(k + 1)));
      var m = el('div', 'row-main');
      m.appendChild(el('div', 'row-name', s.name));
      m.appendChild(el('div', 'row-sub', isSpof ? '멈추면 노선이 양분됩니다' : '종점부'));
      btn.appendChild(m);
      var v = el('div', 'row-val');
      v.innerHTML = '<span class="num">' + comma(s.demand) + '</span><small>일평균</small>';
      btn.appendChild(v);
      btn.onclick = function () { openStation(si); };
      rows2.appendChild(btn);
    });
  host.appendChild(rows2);

  var n2 = el('p', 'note'); n2.style.margin = '14px 2px 0';
  n2.textContent = '대전 도시철도 2호선(트램)이 개통되면 이 지표가 어떻게 바뀌는지가 곧 투자 효과의 정량적 근거가 됩니다.';
  host.appendChild(n2);
}

/* ─────────────────────────────────────────────────────────────
 * 11. 데이터 뷰
 * ───────────────────────────────────────────────────────────── */

function renderData() {
  var host = $('#viewData');
  if (host.dataset.done) return;
  host.dataset.done = '1';

  host.appendChild(sectionTitle('활용한 공공데이터'));
  var src = el('div', 'src');
  [
    ['국가철도공단_전국 도시철도 역사정보', '역 위치·노선·환승 구분 · 공공데이터포털'],
    ['국가철도공단_전국 도시철도 노선정보', '노선별 정거장 구성'],
    ['국가철도공단_전국 도시철도 운행정보', '열차 운행 순서·소요시간·운행 횟수'],
    ['국가철도공단_노선별 역간거리', '구간 실측 거리 (18개 노선)'],
    ['국가철도공단_노선별 환승정보', '환승 연결 관계 (15개 기관)'],
    ['국가철도공단_노선별 승강장 정보', '역층·승강장연결·스크린도어·안전발판 (30개 노선, 5개 권역)'],
    ['국토교통부_철도역 빠른 환승 정보', '환승 통로와 가장 가까운 차량순서(칸)·출입문 (103개 환승역)'],
    ['각 도시철도 운영기관_역별 승하차실적', '역별 일평균 이용 규모']
  ].forEach(function (s) {
    var it = el('div', 'src-item');
    it.innerHTML = '<div class="t">' + esc(s[0]) + '</div><div class="d">' + esc(s[1]) + '</div>';
    src.appendChild(it);
  });
  host.appendChild(src);

  host.appendChild(sectionTitle('분석 방법'));
  var m = el('div', 'src');
  [
    ['그래프 구성', '역을 노드, 인접 운행구간과 환승을 엣지로 하는 무향 가중그래프를 만듭니다. 가중치는 실제 운행 소요시간이며, 환승은 ' + NET.transferSec + '초로 둡니다.'],
    ['단일고장점 판정', '출발–도착 최단경로를 구한 뒤, 경로 위의 역을 하나씩 그래프에서 제거하고 다시 탐색합니다. 경로가 사라지면 그 역을 단일고장점으로 판정합니다.'],
    ['우회 부담', '제거 후에도 경로가 남으면 늘어난 소요시간을 우회 비용으로 계산합니다.'],
    ['한계', '실시간 운행 상황·열차 시각표·버스 등 대체 수단은 반영하지 않습니다. 물리적 선로 연결 구조만으로 판단한 결과입니다.']
  ].forEach(function (s) {
    var it = el('div', 'src-item');
    it.innerHTML = '<div class="t">' + esc(s[0]) + '</div><div class="d">' + esc(s[1]) + '</div>';
    m.appendChild(it);
  });
  host.appendChild(m);

  host.appendChild(sectionTitle('분석 범위'));
  var st = el('div', 'src');
  var counts = {};
  STATIONS.forEach(function (s) { counts[s.region] = (counts[s.region] || 0) + 1; });
  var it2 = el('div', 'src-item');
  it2.innerHTML = '<div class="t">역 ' + STATIONS.length + '개 · 구간 ' + EDGES.length + '개</div>' +
    '<div class="d">' + Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; })
      .map(function (k) { return k + ' ' + counts[k]; }).join(' · ') + '</div>';
  st.appendChild(it2);
  host.appendChild(st);

  var f = el('p', 'note');
  f.style.margin = '18px 2px 0';
  f.textContent = '모든 계산은 사용자의 기기에서 수행되며, 어떤 정보도 외부로 전송되지 않습니다.';
  host.appendChild(f);
}

/* ─────────────────────────────────────────────────────────────
 * 12. 탭 · 초기화
 * ───────────────────────────────────────────────────────────── */

function showTab(name) {
  $$('.view').forEach(function (v) { v.classList.toggle('on', v.dataset.view === name); });
  $$('.tab').forEach(function (t) { t.setAttribute('aria-selected', String(t.dataset.tab === name)); });
  // 권역 버튼은 역 검색 기준을 바꾸는 것이라 진단 탭에서만 의미가 있다.
  $('#regionBtn').style.visibility = (name === 'diagnose') ? '' : 'hidden';
  window.scrollTo(0, 0);
  if (name === 'map') {
    // 방금 진단한 경로가 있으면 그 권역을 먼저 보여준다.
    if (state.from != null) {
      var reg = STATIONS[state.from].region;
      if (REGIONS.indexOf(reg) >= 0 && reg !== state.mapRegion) {
        state.mapRegion = reg;
        $$('.seg-btn', $('#mapRegions')).forEach(function (x) {
          x.setAttribute('aria-pressed', String(x.textContent === reg));
        });
      }
    }
    setTimeout(renderMap, 30);
  }
  if (name === 'daejeon') renderDaejeon();
  if (name === 'data') renderData();
}

function initRegionPicker() {
  var btn = $('#regionBtn');
  function label() { $('#regionLabel').textContent = state.region; }
  label();
  // 순환 토글이 아니라 리스트에서 고른다 — 권역이 6개라 순환은 최대 5번 눌러야 한다.
  btn.onclick = function () {
    var counts = {};
    STATIONS.forEach(function (s) { counts[s.region] = (counts[s.region] || 0) + 1; });
    $('#sheetTitle').textContent = '검색 기준 권역';
    $('#searchWrap').style.display = 'none';
    var list = $('#sheetList');
    list.innerHTML = '';
    var rows = el('div', 'rows');
    REGIONS.forEach(function (r) {
      var b = el('button', 'row');
      var m = el('div', 'row-main');
      var nm = el('div', 'row-name', r);
      if (r === state.region) nm.style.color = 'var(--tint)';
      m.appendChild(nm);
      b.appendChild(m);
      var val = el('div', 'row-val');
      val.innerHTML = '<small>' + (counts[r] || 0) + '역</small>' +
        (r === state.region
          ? '<span style="color:var(--tint);font-size:15px">✓</span>' : '');
      b.appendChild(val);
      b.onclick = function () {
        state.region = r;
        localStorage.setItem('rl.region', r);
        label();
        closeSearch();
        $('#searchWrap').style.display = '';
      };
      rows.appendChild(b);
    });
    list.appendChild(rows);
    $('#sheet').classList.add('on');
  };
}

function initMapFilter() {
  var bar = $('#mapRegions');
  REGIONS.forEach(function (r) {
    var b = el('button', 'seg-btn', r);
    b.setAttribute('aria-pressed', String(r === state.mapRegion));
    b.onclick = function () {
      state.mapRegion = r;
      $$('.seg-btn', bar).forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      renderMap();
    };
    bar.appendChild(b);
  });
}

/** ?from=판암&to=반석&tab=map 형태의 딥링크. 공유 링크와 동작 확인에 함께 쓴다. */
function applyDeepLink() {
  var q = new URLSearchParams(location.search);
  var f = q.get('from'), t = q.get('to'), reg = q.get('region');
  if (reg && REGIONS.indexOf(reg) >= 0) { state.region = reg; state.mapRegion = reg; }
  var fi = lookupStation(f, state.region), ti = lookupStation(t, state.region);
  if (f && t && fi != null && ti != null && fi !== ti) { state.from = fi; state.to = ti; }
  return q.get('tab');
}

function shareLink() {
  if (state.from == null || state.to == null) return;
  var a = STATIONS[state.from], b = STATIONS[state.to];
  var url = location.origin + location.pathname +
    '?from=' + encodeURIComponent(a.name) + '&to=' + encodeURIComponent(b.name) +
    '&region=' + encodeURIComponent(a.region);
  var title = a.name + ' → ' + b.name + ' 경로 취약성 진단';
  if (navigator.share) {
    navigator.share({ title: 'Raility', text: title, url: url }).catch(function () {});
  } else if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(function () { toast('링크를 복사했습니다'); },
                                            function () { toast('복사할 수 없습니다'); });
  } else { toast(url); }
}

function init() {
  $('#odFromBtn').onclick = function () { $('#searchWrap').style.display = ''; openSearch('from'); };
  $('#odToBtn').onclick = function () { $('#searchWrap').style.display = ''; openSearch('to'); };
  $('#odSwap').onclick = function (e) {
    e.stopPropagation();
    var t = state.from; state.from = state.to; state.to = t;
    syncOD(); if (state.from != null && state.to != null) runDiagnose();
  };
  $('#sheetClose').onclick = closeSearch;
  $('#sheetScrim').onclick = closeSearch;
  $('#searchInput').addEventListener('input', function () { renderSearch(this.value); });

  $$('.tab').forEach(function (t) { t.onclick = function () { showTab(t.dataset.tab); }; });

  var tab = applyDeepLink();

  initRegionPicker();
  initMapFilter();
  syncOD();

  runDiagnose();
  showTab(tab || 'diagnose');

  window.addEventListener('resize', function () {
    if ($('.view.on') && $('.view.on').dataset.view === 'map') renderMap();
  });

  if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
    navigator.serviceWorker.register('sw.js').catch(function () {});
  }
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();

})();
