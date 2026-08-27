# -*- coding: utf-8 -*-
"""승강장 접근성 정보 결합 (국가철도공단 승강장_정보 30종 → 그래프 노드)

역간거리 파일과 같은 기관·같은 노선별 파일 구조여서 build_graph.py 의 결합 방식을
그대로 따른다. 노선 해석을 좌표가 아니라 (운영기관, 선명) 매핑으로 먼저 하는 것도 같다.

출력: data/processed/accessibility.csv  — 그래프 노드 1개 = 1행
  승강장수 / 스크린도어_없음 / 안전발판_없음 / 승강장연결_안됨 / 최대역층 / 접근성위험도

'안전발판'은 승강장과 열차 사이 틈을 메우는 발판이다. 없으면 휠체어·유아차가
혼자 승하차하기 어렵다. '승강장연결'이 N 이면 반대 방향으로 가려면 개찰구를
나갔다 다시 들어와야 하므로, 잘못 탄 교통약자는 사실상 갇힌다.
"""
import csv, io, glob, os, re, unicodedata
from collections import defaultdict

RAW = "data/raw/승강장/"
NODES = "data/processed/nodes.csv"
OUT = "data/processed/accessibility.csv"


def norm(s):
    """build_graph.py 와 동일한 역명 정규화 (괄호·공백 제거, 끝의 '역' 절단)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", str(s))
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\s+", "", s)
    if s.endswith("역") and len(s) > 1:
        s = s[:-1]
    return s


# 개명·표기 차이. 근거는 그래프 노드에 실재하는 이름과 대조해 확인했다.
ALIAS = {"신길온천": "능길", "당고개": "불암산"}    # 당고개→불암산: 4호선 2024 개명

# 노선을 가려야 하는 표기 차이. '총신대입구' 는 7호선에서만 '이수' 이고,
# 4호선 역명은 실제로 '총신대입구(이수)' 라 전역 치환하면 4호선이 깨진다.
ALIAS_BY_LINE = {("7호선", "총신대입구"): "이수"}

# 대구 2호선 '대공원', 에버라인 '운동장·송담대' 는 개명으로 보이나 확증이 없어 두었다.

SEOUL = {"서울교통공사": {"%d호선" % i: {"%d호선" % i} for i in range(1, 9)}}
KORAIL1 = {"경부선", "경인선", "경원선", "장항선"}

# (철도운영기관명, 선명) → nodes.csv 의 노선명 후보. 선명이 "1호선"처럼 지역 간
# 중복되므로 운영기관을 반드시 함께 본다.
LINE_MAP = {
    ("공항철도주식회사", "공항"): {"인천국제공항선"},
    ("광주교통공사", "1호선"): {"광주도시철도 1호선"},
    ("네오트랜스주식회사", "신분당"): {"신분당선"},
    ("대전교통공사", "1호선"): {"대전 도시철도 1호선"},
    ("부산김해경전철주식회사", "부산김해경전철"): {"부산김해경전철"},
    ("용인경량전철주식회사", "에버라인"): {"에버라인"},
    ("인천교통공사", "7호선"): {"도시철도 7호선"},
    ("인천교통공사", "인천1호선"): {"인천지하철 1호선"},
    ("인천교통공사", "인천2호선"): {"인천지하철 2호선"},
    ("코레일", "1호선"): KORAIL1,
    ("코레일", "3호선"): {"일산선"},
    ("코레일", "4호선"): {"안산과천선"},
    ("코레일", "경강"): {"경강선"},
    ("코레일", "경의중앙"): {"경의중앙선", "경원선"},
    # 경춘선 열차는 청량리~광운대 구간에서 경원선·경의중앙선 선로를 함께 쓴다.
    # 그래프에는 그 구간 역이 경춘선 노드로 따로 있지 않으므로 후보를 넓힌다.
    ("코레일", "경춘"): {"경춘선", "경원선", "경의중앙선"},
    ("코레일", "대경선"): {"대경선"},
    ("코레일", "동해"): {"동해선"},
    ("코레일", "서해"): {"서해선"},
    ("코레일", "수인분당"): {"수인선", "분당선"},
}
for i in (1, 2, 3):
    LINE_MAP[("대구교통공사", "%d호선" % i)] = {"대구 도시철도 %d호선" % i}
for i in (1, 2, 3):
    LINE_MAP[("부산교통공사", "%d호선" % i)] = {"부산 도시철도 %d호선" % i}
LINE_MAP[("부산교통공사", "4호선")] = {"부산 경량도시철도 4호선"}
for i in range(1, 9):
    LINE_MAP[("서울교통공사", "%d호선" % i)] = {"%d호선" % i}


def read_csv(path):
    for enc in ("cp949", "utf-8-sig", "euc-kr"):
        try:
            with io.open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except Exception:
            continue
    return []


def col(row, key):
    """'상하행' / '상하행구분' 처럼 파일마다 다른 컬럼명을 흡수한다."""
    return next((c for c in row if key in c), None)


def yn(v):
    v = (v or "").strip().upper()
    return v if v in ("Y", "N") else ""


def main():
    nodes = list(csv.DictReader(io.open(NODES, encoding="utf-8-sig")))
    by_name = defaultdict(list)
    for r in nodes:
        by_name[norm(r["역사명"])].append(r)

    # ---- 적재 + 중복 제거 -------------------------------------------------
    # 집계 파일(대구교통공사 등)이 노선별 파일과 같은 행을 담고 있어 그대로 세면 2배가 된다.
    seen = set()
    plats = []
    for fp in sorted(glob.glob(RAW + "*.csv")):
        rows = read_csv(fp)
        if not rows:
            print("  읽기 실패:", os.path.basename(fp))
            continue
        r0 = rows[0]
        c_ud, c_gr = col(r0, "상하행"), col(r0, "지상구분")
        c_fl, c_cn = col(r0, "역층"), col(r0, "승강장연결")
        c_sd, c_sp = col(r0, "스크린도어"), col(r0, "안전발판")
        for r in rows:
            op = (r.get("철도운영기관명") or "").strip()
            ln = (r.get("선명") or "").strip()
            nm = (r.get("역명") or "").strip()
            key = (op, ln, nm, (r.get("승강장번호") or "").strip(), (r.get(c_ud) or "").strip())
            if key in seen:
                continue
            seen.add(key)
            plats.append({"op": op, "line": ln, "name": nm,
                          "floor": (r.get(c_fl) or "").strip(),
                          "ground": (r.get(c_gr) or "").strip(),
                          "conn": yn(r.get(c_cn)), "sd": yn(r.get(c_sd)), "sp": yn(r.get(c_sp))})
    print("승강장 행: %d (중복 제거 후)" % len(plats))

    # ---- 노드 결합 -------------------------------------------------------
    agg = defaultdict(lambda: {"n": 0, "sd_n": 0, "sp_n": 0, "conn_n": 0,
                               "sd_k": 0, "sp_k": 0, "conn_k": 0, "floor": 0})
    unmatched = defaultdict(int)
    for p in plats:
        allow = LINE_MAP.get((p["op"], p["line"]))
        nm = norm(p["name"])
        nm = ALIAS_BY_LINE.get((p["line"], nm), ALIAS.get(nm, nm))
        cands = by_name.get(nm, [])
        if allow:
            cands = [c for c in cands if c["노선명"] in allow]
        if len(cands) != 1:
            # 코레일 1호선처럼 후보 노선이 여럿인 역은 그래프에 실재하는 쪽으로 좁힌다.
            if not cands:
                unmatched[(p["op"], p["line"], p["name"])] += 1
                continue
        for c in cands:                      # 다중 후보는 해당 노드 전부에 반영
            a = agg[c["node_id"]]
            a["n"] += 1
            for k, f in (("sd", "sd"), ("sp", "sp"), ("conn", "conn")):
                v = p[f]
                if v:
                    a[k + "_k"] += 1
                    if v == "N":
                        a[k + "_n"] += 1
            try:
                a["floor"] = max(a["floor"], int(p["floor"]))
            except ValueError:
                pass

    print("결합된 노드: %d / %d (%.1f%%)" % (len(agg), len(nodes), len(agg) / len(nodes) * 100))
    if unmatched:
        print("미매칭 %d종 (상위 10):" % len(unmatched))
        for k, v in sorted(unmatched.items(), key=lambda x: -x[1])[:10]:
            print("   %s %s %s (%d행)" % k[:2] + (k[2], v) if False else "   %s / %s / %s  %d행" % (k[0], k[1], k[2], v))

    # ---- 위험도 산출 -----------------------------------------------------
    # 세 항목은 서로 다른 장벽이라 합산하지 않고 각각 센다.
    #   안전발판 없음  → 혼자 승하차 곤란
    #   승강장연결 안됨 → 반대 방향 가려면 역 밖으로
    #   스크린도어 없음 → 추락 위험
    out = []
    nodeinfo = {r["node_id"]: r for r in nodes}
    for nid, a in agg.items():
        r = nodeinfo[nid]
        sp_bad = a["sp_k"] and a["sp_n"] == a["sp_k"]        # 전 승강장 미설치
        cn_bad = a["conn_k"] and a["conn_n"] == a["conn_k"]
        sd_bad = a["sd_k"] and a["sd_n"] == a["sd_k"]
        risk = int(sp_bad) + int(cn_bad) + int(sd_bad)
        out.append({
            "node_id": nid, "역사명": r["역사명"], "노선명": r["노선명"],
            "운영기관": r["운영기관명"], "승강장수": a["n"],
            "안전발판_없음": int(sp_bad), "승강장연결_안됨": int(cn_bad),
            "스크린도어_없음": int(sd_bad), "최대역층": a["floor"],
            "접근성위험도": risk,
        })
    out.sort(key=lambda x: (-x["접근성위험도"], x["역사명"]))
    with io.open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print("저장:", OUT)

    cross_summary(nodes, {r["node_id"]: r for r in out})
    return out


# ---------------------------------------------------------------- 교차 분석
# 절점(끊기면 망이 갈라지는 역)이면서 접근성 위험인 역 = '이중취약'.
# 구조적으로 우회가 없는데 승강장 장벽까지 있으면 교통약자에겐 통행 불가에 가깝다.
REGION_BY_OP = {"대전교통공사": "대전", "광주교통공사": "광주", "대구교통공사": "대구",
                "부산광역시 부산교통공사": "부산", "부산-김해경전철㈜": "부산"}
SUMMARY = "results/accessibility_summary.csv"
DOUBLE = "results/accessibility_double_risk.csv"


def articulation_points(adj, members):
    """Tarjan 절점 탐색(반복형). 재귀는 800역 넘는 권역에서 스택을 넘긴다."""
    disc, low, ap, t = {}, {}, set(), [0]
    for root in sorted(members):
        if root in disc:
            continue
        disc[root] = low[root] = t[0]; t[0] += 1
        stack = [(root, None, iter(sorted(adj[root] & members)))]
        rootkids = 0
        while stack:
            u, par, it = stack[-1]
            descended = False
            for v in it:
                if v not in disc:
                    disc[v] = low[v] = t[0]; t[0] += 1
                    if u == root:
                        rootkids += 1
                    stack.append((v, u, iter(sorted(adj[v] & members))))
                    descended = True
                    break
                if v != par:
                    low[u] = min(low[u], disc[v])
            if descended:
                continue
            stack.pop()
            if stack:
                p = stack[-1][0]
                low[p] = min(low[p], low[u])
                if p != root and low[u] >= disc[p]:
                    ap.add(p)
        if rootkids > 1:
            ap.add(root)
    return ap


def cross_summary(nodes, acc):
    adj = defaultdict(set)
    for fn in ("data/processed/edges_adjacency.csv", "data/processed/edges_transfer.csv"):
        for r in csv.DictReader(io.open(fn, encoding="utf-8-sig")):
            adj[r["source"]].add(r["target"])
            adj[r["target"]].add(r["source"])

    info = {r["node_id"]: r for r in nodes}
    by_region = defaultdict(set)
    for r in nodes:
        by_region[REGION_BY_OP.get(r["운영기관명"], "수도권")].add(r["node_id"])

    rows, dbl = [], []
    for reg in ("수도권", "부산", "대구", "대전", "광주"):
        mem = by_region[reg]
        ap = articulation_points(adj, mem)
        have = [n for n in mem if n in acc]
        risky = {n for n in have if int(acc[n]["접근성위험도"]) >= 1}
        both = ap & risky
        for n in sorted(both):
            dbl.append({"권역": reg, "역사명": info[n]["역사명"], "노선명": info[n]["노선명"],
                        "안전발판_없음": acc[n]["안전발판_없음"],
                        "승강장연결_안됨": acc[n]["승강장연결_안됨"],
                        "스크린도어_없음": acc[n]["스크린도어_없음"]})
        rows.append({"권역": reg, "역수": len(mem), "절점수": len(ap),
                     "접근성자료보유": len(have),
                     "자료커버리지_%": round(len(have) / len(mem) * 100, 1),
                     "접근성위험역": len(risky), "이중취약": len(both),
                     "이중취약비율_%": round(len(both) / len(mem) * 100, 1)})

    for path, data in ((SUMMARY, rows), (DOUBLE, dbl)):
        with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            w.writeheader(); w.writerows(data)

    print("\n권역   역수  절점  자료  위험  이중취약   비율")
    for r in rows:
        print("  %-4s %4d %5d %5d %5d %7d %7.1f%%"
              % (r["권역"], r["역수"], r["절점수"], r["접근성자료보유"],
                 r["접근성위험역"], r["이중취약"], r["이중취약비율_%"]))
    print("저장:", SUMMARY, "/", DOUBLE)


if __name__ == "__main__":
    main()
