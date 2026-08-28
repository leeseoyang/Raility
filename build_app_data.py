# -*- coding: utf-8 -*-
"""
모바일 앱(Raility)용 네트워크 데이터 번들 생성
- 입력: data/processed/*.csv, results/*.csv
- 출력: raility_app/assets/data.js  (window.NET = {...})
표준 라이브러리만 사용.
"""
import csv, json, os, io

ROOT = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(ROOT, *a)

def read(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

# ── 권역 판정 ──────────────────────────────────────────────
# 주소는 표기가 제각각(대구권은 시도 접두어 누락)이라 운영기관 → 좌표 순으로 판정한다.
REGION_BY_OP = [
    ("대전교통공사", "대전"),
    ("부산교통공사", "부산"), ("부산-김해", "부산"),
    ("대구교통공사", "대구"),
    ("광주교통공사", "광주"),
    ("서울교통공사", "수도권"), ("서울시메트로9", "수도권"), ("우이신설", "수도권"),
    ("남서울경전철", "수도권"), ("김포골드라인", "수도권"), ("인천교통공사", "수도권"),
    ("인천국제공항공사", "수도권"), ("공항철도", "수도권"), ("신분당선", "수도권"),
    ("용인경전철", "수도권"), ("의정부경량전철", "수도권"), ("남양주도시공사", "수도권"),
    ("구리도시공사", "수도권"), ("경기철도", "수도권"), ("네오트랜스", "수도권"),
]
# (lat_min, lat_max, lon_min, lon_max, 권역)
REGION_BOX = [
    (36.15, 36.52, 127.20, 127.62, "대전"),
    (36.42, 36.78, 127.12, 127.40, "세종"),
    (36.85, 38.35, 126.20, 127.95, "수도권"),
    (34.95, 35.45, 128.75, 129.45, "부산"),
    (35.65, 36.15, 128.35, 128.95, "대구"),
    (34.95, 35.35, 126.65, 127.05, "광주"),
]
def region_of(addr, line, op, lat, lon):
    for key, reg in REGION_BY_OP:
        if key in (op or ""):
            return reg
    for la0, la1, lo0, lo1, reg in REGION_BOX:
        if la0 <= lat <= la1 and lo0 <= lon <= lo1:
            return reg
    return "기타"

# ── 노드 ───────────────────────────────────────────────────
nodes = read(P("data", "processed", "nodes.csv"))
demand = {r["node_id"]: r for r in read(P("data", "processed", "node_demand.csv"))}

# 승강장 접근성 (build_accessibility.py 산출물). 아직 공공데이터가 없는 노선이
# 있으므로 없는 노드는 키를 아예 안 넣는다 — 0 으로 채우면 '장벽 없음'과
# '자료 없음'이 구분되지 않아 없는 안전을 있다고 보고하게 된다.
_ap = P("data", "processed", "accessibility.csv")
access = {r["node_id"]: r for r in read(_ap)} if os.path.exists(_ap) else {}

def fnum(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d

N = []
idx = {}
for r in nodes:
    nid = r["node_id"]
    dm = demand.get(nid)
    lat, lon = fnum(r["역위도"]), fnum(r["역경도"])
    idx[nid] = len(N)
    ac = access.get(nid)
    node = {
        "i": nid,
        "n": r["역사명"].replace("역", "") if len(r["역사명"]) > 2 and r["역사명"].endswith("역") else r["역사명"],
        "fn": r["역사명"],
        "l": r["노선명"],
        "o": r["운영기관명"],
        "la": round(lat, 6),
        "lo": round(lon, 6),
        "r": region_of(r.get("역사도로명주소", ""), r["노선명"], r["운영기관명"], lat, lon),
        "x": 1 if "환승" in (r.get("환승역구분") or "") else 0,
        "d": round(fnum(dm["일평균승하차_배분"]) if dm else 0.0),
        "ad": r.get("역사도로명주소", ""),
    }
    if ac:
        # [위험도, 안전발판없음, 승강장연결안됨, 스크린도어없음, 최대역층]
        node["ac"] = [int(fnum(ac["접근성위험도"])), int(fnum(ac["안전발판_없음"])),
                      int(fnum(ac["승강장연결_안됨"])), int(fnum(ac["스크린도어_없음"])),
                      int(fnum(ac["최대역층"]))]
    N.append(node)

# ── 엣지 ───────────────────────────────────────────────────
TRANSFER_SEC = 210          # 환승 도보+대기 가정
adj = read(P("data", "processed", "edges_adjacency.csv"))
xfr = read(P("data", "processed", "edges_transfer.csv"))

E = []
seen = set()
for r in adj:
    s, t = r["source"], r["target"]
    if s not in idx or t not in idx:
        continue
    k = tuple(sorted((s, t)))
    if k in seen:
        continue
    seen.add(k)
    sec = fnum(r.get("소요시간_s"), 0) or 0
    dist = fnum(r.get("거리_m"), 0) or 0
    if sec <= 0:                      # 소요시간 결측 → 표정속도 32km/h 가정
        sec = max(60, dist / 8.9)
    E.append([idx[s], idx[t], 0, int(round(sec)), int(round(dist)),
              int(round(fnum(r.get("평일운행횟수"), 0)))])

for r in xfr:
    s, t = r["source"], r["target"]
    if s not in idx or t not in idx:
        continue
    k = tuple(sorted((s, t)))
    if k in seen:
        continue
    seen.add(k)
    E.append([idx[s], idx[t], 1, TRANSFER_SEC, 0, 0])

# ── 고립 노드 제거 ─────────────────────────────────────────
# 짝이 되는 구간이 없는 역(예: 운행 중단된 인천공항 자기부상철도)은 검색에는 뜨지만
# 경로가 절대 나오지 않으므로 앱에서 빼고 인덱스를 다시 매긴다.
deg = [0] * len(N)
for e in E:
    deg[e[0]] += 1
    deg[e[1]] += 1
dropped = [i for i, d in enumerate(deg) if d == 0]
if dropped:
    names = ", ".join("%s(%s)" % (N[i]["fn"], N[i]["l"]) for i in dropped)
    keep = [i for i, d in enumerate(deg) if d > 0]
    remap = {old: new for new, old in enumerate(keep)}
    for nid, old in list(idx.items()):
        if old in remap:
            idx[nid] = remap[old]
        else:
            del idx[nid]
    N = [N[i] for i in keep]
    for e in E:
        e[0] = remap[e[0]]
        e[1] = remap[e[1]]
    print("고립 노드 %d개 제외: %s" % (len(dropped), names))

# ── 역 제거 영향(사전계산) ──────────────────────────────────
IMPACT = {}
for fn in ("single_removal_impact_metro.csv", "single_removal_impact_daejeon.csv"):
    p = P("results", fn)
    if not os.path.exists(p):
        continue
    for r in read(p):
        nid = r["node_id"]
        if nid not in idx:
            continue
        IMPACT[idx[nid]] = [
            round(fnum(r.get("효율저하율_%")), 3),
            round(fnum(r.get("승객가중효율저하율_%")), 3),
            int(fnum(r.get("최대연결요소감소"))),
            int(fnum(r.get("분리유발"))),
        ]

# ── 구간 취약성(사전계산) ───────────────────────────────────
SEG = []
p = P("results", "edge_vulnerability_by_region.csv")
if os.path.exists(p):
    key = {}
    for i, e in enumerate(E):
        key[tuple(sorted((e[0], e[1])))] = i
    name2ids = {}
    for i, n in enumerate(N):
        name2ids.setdefault((n["fn"], n["l"]), []).append(i)
        name2ids.setdefault((n["n"], n["l"]), []).append(i)
    for r in read(p):
        a = name2ids.get((r["역A"], r["노선A"]))
        b = name2ids.get((r["역B"], r["노선B"]))
        if not a or not b:
            continue
        k = tuple(sorted((a[0], b[0])))
        ei = key.get(k)
        if ei is None:
            continue
        SEG.append([ei,
                    round(fnum(r.get("효율저하율_%")), 3),
                    round(fnum(r.get("수요가중저하율_%")), 3),
                    int(fnum(r.get("단절유발"))),
                    int(fnum(r.get("분리규모")))])

# ── 우선보강 역 ─────────────────────────────────────────────
PRIO = []
p = P("results", "priority_stations.csv")
if os.path.exists(p):
    for r in read(p):
        if r["node_id"] in idx:
            PRIO.append([idx[r["node_id"]], r.get("구분", ""),
                         round(fnum(r.get("효율저하율_%")), 3),
                         int(fnum(r.get("분리규모")))])

summary = json.load(io.open(P("results", "summary.json"), encoding="utf-8"))

# ── 빠른환승 (국토교통부, 차량순서·출입문) ──────────────────
# 원본은 (운영기관, 노선명, 역명, 종착역명 → 환승선) 단위다. 노선명이 그래프
# 노선명과 다르므로("경의중앙" vs "경의중앙선", 코레일 "1호선" vs 경부/경인선…)
# 후보 집합으로 매핑해 앱에서 stop.fromLine/toLine 소속 검사로 조회한다.
import re as _re
import unicodedata as _ud

def _norm(s):
    s = _ud.normalize("NFC", str(s or ""))
    s = _re.sub(r"\(.*?\)", "", s)
    s = _re.sub(r"\s+", "", s)
    return s[:-1] if s.endswith("역") and len(s) > 1 else s

_KORAIL1 = ["경부선", "경인선", "경원선", "장항선"]
_FT_LINE = {
    ("코레일", "1호선"): _KORAIL1, ("코레일", "3호선"): ["일산선"],
    ("코레일", "4호선"): ["안산과천선"], ("코레일", "경강"): ["경강선"],
    ("코레일", "경의중앙"): ["경의중앙선", "경원선"], ("코레일", "경춘"): ["경춘선"],
    ("코레일", "동해"): ["동해선"], ("코레일", "수인분당"): ["수인선", "분당선"],
    ("공항철도주식회사", "공항철도"): ["인천국제공항선"],
    ("네오트랜스주식회사", "신분당선"): ["신분당선"],
    ("서울시메트로9호선주식회사", "9호선"): ["수도권  도시철도 9호선", "서울 도시철도 9호선"],
    ("우이신설경전철주식회사", "우이신설"): ["우이신설선"],
    ("의정부경량전철주식회사", "의정부경전철"): ["의정부"],
    ("용인경량전철주식회사", "용인에버라인"): ["에버라인"],
    ("부산김해경전철주식회사", "부산김해경전철"): ["부산김해경전철"],
    ("인천국제공항공사", "자기부상"): ["자기부상철도"],
    ("인천교통공사", "인천1호선"): ["인천지하철 1호선"],
    ("인천교통공사", "인천2호선"): ["인천지하철 2호선"],
    ("인천교통공사", "7호선"): ["도시철도 7호선"],
}
for _i in range(1, 9):
    _FT_LINE[("서울교통공사", "%d호선" % _i)] = ["%d호선" % _i]
for _i in (1, 2, 3):
    _FT_LINE[("대구교통공사", "%d호선" % _i)] = ["대구 도시철도 %d호선" % _i]
    _FT_LINE[("부산교통공사", "%d호선" % _i)] = ["부산 도시철도 %d호선" % _i]
_FT_LINE[("부산교통공사", "4호선")] = ["부산 경량도시철도 4호선"]
_FT_REGION = {"대구교통공사": "대구", "부산교통공사": "부산", "부산김해경전철주식회사": "부산"}

FT = {}
_ft_path = P("data", "raw", "빠른환승", "국토교통부_철도역_빠른환승정보_20251113.csv")
_ft_n = _ft_skip = 0
if os.path.exists(_ft_path):
    with io.open(_ft_path, encoding="cp949", newline="") as f:
        for r in csv.DictReader(f):
            op = (r.get("철도운영기관명") or "").strip()
            ln = (r.get("노선명") or "").strip()
            st = _norm(r.get("역명"))
            xop = (r.get("환승철도운영기관명") or "").strip()
            xln = (r.get("환승선") or "").strip()
            car = (r.get("차량순서") or "").strip()
            door = (r.get("차량출입문번호") or "").strip()
            fr = _FT_LINE.get((op, ln))
            to = _FT_LINE.get((xop, xln))
            if not (st and fr and to and car and door):
                _ft_skip += 1
                continue
            reg = _FT_REGION.get(op, "수도권")
            key = reg + "|" + st
            # [탈때노선 후보, 갈아탈노선 후보, 종착방면, 칸, 문, 환승이후역]
            # 환승이후역 = 갈아탄 뒤 첫 역. 경로의 다음 정차역과 직접 매칭돼
            # 새 노선의 방향(2호선 내선/외선 등)을 구분한다.
            FT.setdefault(key, []).append(
                [fr, to, _norm(r.get("종착역명")), int(car), int(door),
                 _norm(r.get("환승이후역명"))])
            _ft_n += 1
print("빠른환승: 채택 %d · 매핑불가 %d · 역 %d곳" % (_ft_n, _ft_skip, len(FT)))

# 노선색(기존 앱에서 추출한 실제 노선 고유색)
COLORS = {}
cp = P("raility_app", "assets", "_linecolors.json")
if os.path.exists(cp):
    raw = json.load(io.open(cp, encoding="utf-8-sig"))
    COLORS = {k: v for k, v in raw.items() if isinstance(v, str) and v.startswith("#")}
for n in N:                              # 누락 노선 기본색
    COLORS.setdefault(n["l"], "#6B7280")

bundle = {
    "nodes": N, "edges": E, "impact": IMPACT,
    "seg": SEG, "prio": PRIO, "summary": summary,
    "colors": COLORS, "transferSec": TRANSFER_SEC, "ft": FT,
}

out = P("raility_app", "assets", "data.js")
os.makedirs(os.path.dirname(out), exist_ok=True)
with io.open(out, "w", encoding="utf-8") as f:
    f.write("window.NET=")
    json.dump(bundle, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")

# Flutter 앱용 순수 JSON (같은 번들, 래퍼만 없음)
fout = P("raility_flutter", "assets", "network.json")
os.makedirs(os.path.dirname(fout), exist_ok=True)
with io.open(fout, "w", encoding="utf-8") as f:
    json.dump(bundle, f, ensure_ascii=False, separators=(",", ":"))

regions = {}
for n in N:
    regions[n["r"]] = regions.get(n["r"], 0) + 1
print("노드 %d / 엣지 %d (운행 %d, 환승 %d)" % (
    len(N), len(E), sum(1 for e in E if e[2] == 0), sum(1 for e in E if e[2] == 1)))
print("권역:", ", ".join("%s %d" % kv for kv in sorted(regions.items(), key=lambda x: -x[1])))
print("영향 사전계산 %d역 / 취약구간 %d / 우선보강 %d" % (len(IMPACT), len(SEG), len(PRIO)))
print("출력: %s (%.0f KB)" % (out, os.path.getsize(out) / 1024))
print("출력: %s (%.0f KB)" % (fout, os.path.getsize(fout) / 1024))
