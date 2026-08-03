# -*- coding: utf-8 -*-
"""
도시철도 네트워크 취약성 분석
  1) 중심성 분석 (연결·매개·근접·고유벡터)
  2) 단일 역사 제거 영향도 (전 역 전수 스윕) → 핵심 역사 도출
  3) 표적 공격 vs 무작위 제거 → 복원력 곡선
  4) 승객 이동 영향 (운행빈도 가중 효율, OD 프록시)
  5) 대전 사례 분석

입력 : data/processed/network.graphml   (build_graph.py 산출물)
출력 : results/*.csv
"""
import json, math, random
from collections import defaultdict

import numpy as np
import pandas as pd
import networkx as nx
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import shortest_path, connected_components

IN = "data/processed/network.graphml"
OUT = "results/"
SEED = 42
TRANSFER_COST_M = 200.0     # 환승 1회를 도보/대기 200m 상당으로 환산
DEFAULT_EDGE_M = 1000.0     # 거리 결측 시 대체값(중앙값 수준)

random.seed(SEED); np.random.seed(SEED)


# ---------------------------------------------------------------- 그래프 적재
def load_graph(path=IN):
    G = nx.read_graphml(path)
    for u, v, d in G.edges(data=True):
        w = d.get("거리_m", "")
        try:
            w = float(w)
        except (TypeError, ValueError):
            w = np.nan
        if d.get("type") == "환승":
            w = TRANSFER_COST_M
        elif not np.isfinite(w) or w <= 0:
            w = DEFAULT_EDGE_M
        d["w"] = float(max(w, 30.0))
        try:
            d["freq"] = float(d.get("평일운행횟수", "") or 0)
        except (TypeError, ValueError):
            d["freq"] = 0.0
    return G


def node_label(G, n):
    return f"{G.nodes[n].get('역사명','?')}({G.nodes[n].get('노선명','?')})"


# ------------------------------------------------------- 성능용 행렬 유틸리티
class Net:
    """노드 부분집합에 대한 최단경로 계산을 인덱스 마스킹으로 처리(고속)."""

    def __init__(self, G, nodes):
        self.nodes = list(nodes)
        self.idx = {n: i for i, n in enumerate(self.nodes)}
        ei, ej, ew = [], [], []
        for u, v, d in G.subgraph(self.nodes).edges(data=True):
            ei.append(self.idx[u]); ej.append(self.idx[v]); ew.append(d["w"])
        self.ei = np.asarray(ei, dtype=np.int64)
        self.ej = np.asarray(ej, dtype=np.int64)
        self.ew = np.asarray(ew, dtype=float)
        self.n = len(self.nodes)
        # 노드 강도(운행빈도 합) = 승객량 프록시
        self.freq = np.zeros(self.n)
        for u, v, d in G.subgraph(self.nodes).edges(data=True):
            self.freq[self.idx[u]] += d["freq"]; self.freq[self.idx[v]] += d["freq"]
        if self.freq.sum() == 0:
            self.freq = np.ones(self.n)

    def matrix(self, keep_mask=None):
        if keep_mask is None:
            return csr_matrix(
                (np.concatenate([self.ew, self.ew]),
                 (np.concatenate([self.ei, self.ej]), np.concatenate([self.ej, self.ei]))),
                shape=(self.n, self.n)), np.arange(self.n)
        keep_idx = np.flatnonzero(keep_mask)
        pos = np.full(self.n, -1, dtype=np.int64)
        pos[keep_idx] = np.arange(keep_idx.size)
        sel = keep_mask[self.ei] & keep_mask[self.ej]
        a, b, w = pos[self.ei[sel]], pos[self.ej[sel]], self.ew[sel]
        m = csr_matrix((np.concatenate([w, w]),
                        (np.concatenate([a, b]), np.concatenate([b, a]))),
                       shape=(keep_idx.size, keep_idx.size))
        return m, keep_idx


def efficiency(mat, weights=None, unweighted=False, denom=None):
    """전역 효율 E = (1/D) · Σ 1/d_ij.

    denom을 원 네트워크 기준값으로 고정하면(제거 분석의 표준 관행) 제거된 역은
    도달 불가로 0을 기여한다. denom을 주지 않으면 남은 노드로 재정규화되는데,
    이 경우 종단부 역을 제거하면 평균 거리가 짧아져 효율이 '증가'하는 artifact가
    생기므로, 제거 시뮬레이션에서는 반드시 denom을 고정해 호출한다.
    """
    n = mat.shape[0]
    if n < 2:
        return 0.0
    D = shortest_path(mat, method="D", directed=False, unweighted=unweighted)
    with np.errstate(divide="ignore"):
        inv = 1.0 / D
    inv[~np.isfinite(inv)] = 0.0
    np.fill_diagonal(inv, 0.0)
    if weights is None:
        den = denom if denom else (n * (n - 1))
        return float(inv.sum() / den)
    w = np.asarray(weights, dtype=float)
    num = float(w @ inv @ w)
    den = denom if denom else float(w.sum() ** 2 - (w ** 2).sum())
    return num / den if den > 0 else 0.0


def denom_unweighted(n):
    return n * (n - 1)


def denom_weighted(w):
    w = np.asarray(w, dtype=float)
    return float(w.sum() ** 2 - (w ** 2).sum())


def lcc_size(mat):
    ncomp, lab = connected_components(mat, directed=False)
    return int(np.bincount(lab).max()) if ncomp > 0 else 0


# ------------------------------------------------------------------ 중심성
def centralities(G, nodes):
    H = G.subgraph(nodes).copy()
    deg = dict(H.degree())
    btw = nx.betweenness_centrality(H, weight="w", normalized=True)
    clo = nx.closeness_centrality(H, distance="w")
    try:
        eig = nx.eigenvector_centrality(H, max_iter=1000, tol=1e-06)
    except nx.PowerIterationFailedConvergence:
        eig = {n: np.nan for n in H}
    rows = []
    for n in H:
        rows.append({
            "node_id": n,
            "역사명": G.nodes[n].get("역사명", ""),
            "노선명": G.nodes[n].get("노선명", ""),
            "운영기관": G.nodes[n].get("운영기관", ""),
            "환승역": G.nodes[n].get("환승역", ""),
            "연결중심성": deg[n],
            "매개중심성": round(btw[n], 6),
            "근접중심성": round(clo[n], 6),
            "고유벡터중심성": round(float(eig.get(n, np.nan)), 6),
        })
    return pd.DataFrame(rows)


# ------------------------------------------- 단일 역사 제거 영향도(전수 스윕)
def single_removal_sweep(G, nodes):
    """각 역을 하나씩 제거해 네트워크 효율·연결성 저하량을 실측"""
    net = Net(G, nodes)
    nodes = net.nodes
    freq_w = net.freq
    mat, _ = net.matrix()
    DU, DW = denom_unweighted(net.n), denom_weighted(freq_w)
    E0 = efficiency(mat, denom=DU)
    Ep0 = efficiency(mat, weights=freq_w, denom=DW)
    S0 = lcc_size(mat)

    rows = []
    for i, node in enumerate(nodes):
        mask = np.ones(net.n, dtype=bool); mask[i] = False
        sub, keep = net.matrix(mask)
        E = efficiency(sub, denom=DU)
        Ep = efficiency(sub, weights=freq_w[keep], denom=DW)
        S = lcc_size(sub)
        rows.append({
            "node_id": node,
            "역사명": G.nodes[node].get("역사명", ""),
            "노선명": G.nodes[node].get("노선명", ""),
            "운영기관": G.nodes[node].get("운영기관", ""),
            "환승역": G.nodes[node].get("환승역", ""),
            "효율저하율_%": round((E0 - E) / E0 * 100, 4),
            "승객가중효율저하율_%": round((Ep0 - Ep) / Ep0 * 100, 4),
            "최대연결요소감소": int(S0 - 1 - S),   # -1: 제거한 노드 자신
            "분리유발": int(S0 - 1 - S > 0),
        })
    df = pd.DataFrame(rows).sort_values("승객가중효율저하율_%", ascending=False)
    return df, {"E0": E0, "Ep0": Ep0, "S0": S0}


# ---------------------------------------------- 순차 제거(표적 vs 무작위)
def removal_curve(G, nodes, strategy, frac=0.25, step=1, runs=1, net=None):
    """strategy: 'random' | 'degree' | 'betweenness' | 'adaptive'"""
    net = net or Net(G, nodes)
    H = G.subgraph(net.nodes)
    n0, kmax = net.n, int(net.n * frac)
    mat0, _ = net.matrix()
    DU = denom_unweighted(net.n)
    E0, S0 = efficiency(mat0, denom=DU), lcc_size(mat0)

    def one_run(seed):
        if strategy == "random":
            rnd = random.Random(seed)
            order = list(range(n0)); rnd.shuffle(order)
        elif strategy == "degree":
            order = [net.idx[x] for x, _ in sorted(H.degree(), key=lambda t: -t[1])]
        elif strategy == "betweenness":
            b = nx.betweenness_centrality(H, weight="w")
            order = [net.idx[x] for x in sorted(b, key=b.get, reverse=True)]
        elif strategy == "adaptive":
            order = None
        else:
            raise ValueError(strategy)

        mask = np.ones(n0, dtype=bool)
        rec = [{"제거수": 0, "제거비율": 0.0, "LCC비율": 1.0, "효율비율": 1.0}]
        removed, ptr = 0, 0
        while removed < kmax and mask.sum() > 2:
            if strategy == "adaptive":
                alive = [net.nodes[i] for i in np.flatnonzero(mask)]
                sub = H.subgraph(alive)
                k = min(120, sub.number_of_nodes())      # 표본 근사(순위용)
                b = nx.betweenness_centrality(sub, k=k, weight="w", seed=SEED)
                tgt = [net.idx[x] for x in sorted(b, key=b.get, reverse=True)[:step]]
            else:
                tgt = []
                while ptr < n0 and len(tgt) < step:
                    if mask[order[ptr]]:
                        tgt.append(order[ptr])
                    ptr += 1
            if not tgt:
                break
            mask[tgt] = False
            removed += len(tgt)
            m, _ = net.matrix(mask)
            rec.append({
                "제거수": removed,
                "제거비율": round(removed / n0, 4),
                "LCC비율": round(lcc_size(m) / S0, 4),
                "효율비율": round(efficiency(m, denom=DU) / E0, 4),
            })
        return pd.DataFrame(rec)

    if strategy == "random" and runs > 1:
        dfs = [one_run(SEED + k) for k in range(runs)]
        base = dfs[0][["제거수", "제거비율"]].copy()
        base["LCC비율"] = np.mean([d["LCC비율"].values for d in dfs], axis=0).round(4)
        base["효율비율"] = np.mean([d["효율비율"].values for d in dfs], axis=0).round(4)
        return base
    return one_run(SEED)


# ------------------------------------------------------------------ 실행
def main():
    import os
    os.makedirs(OUT, exist_ok=True)
    G = load_graph()
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    metro = list(comps[0])                       # 최대 연결요소 = 수도권
    print(f"그래프: 노드 {G.number_of_nodes()} 엣지 {G.number_of_edges()} | 수도권 {len(metro)}")

    summary = {}

    # 1) 중심성
    cen = centralities(G, metro)
    cen.sort_values("매개중심성", ascending=False).to_csv(
        OUT + "centrality_metro.csv", index=False, encoding="utf-8-sig")
    print("\n[매개중심성 상위 10]")
    print(cen.nlargest(10, "매개중심성")[["역사명", "노선명", "매개중심성", "연결중심성"]]
          .to_string(index=False))

    # 2) 단일 제거 전수 스윕
    print("\n단일 역사 제거 전수 스윕 실행 중...")
    imp, base = single_removal_sweep(G, metro)
    imp.to_csv(OUT + "single_removal_impact_metro.csv", index=False, encoding="utf-8-sig")
    summary["수도권_기준효율"] = base
    print("[승객가중 영향도 상위 10]")
    print(imp.head(10)[["역사명", "노선명", "효율저하율_%", "승객가중효율저하율_%", "분리유발"]]
          .to_string(index=False))
    print("단절유발역 수:", int(imp["분리유발"].sum()))

    # 3) 복원력 곡선
    print("\n복원력 곡선 계산 중...")
    net_metro = Net(G, metro)
    curves = {}
    for st, runs in [("random", 10), ("degree", 1), ("betweenness", 1), ("adaptive", 1)]:
        curves[st] = removal_curve(G, metro, st, frac=0.25, step=4, runs=runs, net=net_metro)
        curves[st].to_csv(OUT + f"resilience_{st}_metro.csv", index=False, encoding="utf-8-sig")
        d = curves[st]
        at10 = d[d["제거비율"] >= 0.10].head(1)
        if len(at10):
            print(f"  {st:12s} 10% 제거 시 효율 {at10['효율비율'].iloc[0]*100:.1f}%, "
                  f"LCC {at10['LCC비율'].iloc[0]*100:.1f}%")
        summary[f"복원력_{st}_10%효율비율"] = float(at10["효율비율"].iloc[0]) if len(at10) else None

    # 4) 환승역 표적 제거
    trans = [n for n in metro if "환승" in str(G.nodes[n].get("환승역", ""))]
    b = nx.betweenness_centrality(G.subgraph(metro), weight="w")
    top_tr = sorted(trans, key=lambda x: b.get(x, 0), reverse=True)
    mat, _ = net_metro.matrix()
    DU = denom_unweighted(net_metro.n)
    E0, S0 = efficiency(mat, denom=DU), lcc_size(mat)
    rows = []
    for k in [1, 3, 5, 10, 15, 20, 30]:
        if k > len(top_tr):
            break
        mask = np.ones(net_metro.n, dtype=bool)
        mask[[net_metro.idx[x] for x in top_tr[:k]]] = False
        m, _ = net_metro.matrix(mask)
        e = efficiency(m, denom=DU) / E0
        rows.append({"제거환승역수": k, "효율비율": round(e, 4),
                     "효율저하_%": round((1 - e) * 100, 2),
                     "LCC비율": round(lcc_size(m) / S0, 4)})
    tr_df = pd.DataFrame(rows)
    tr_df.to_csv(OUT + "transfer_attack_metro.csv", index=False, encoding="utf-8-sig")
    print("\n[환승역 표적 마비]")
    print(tr_df.to_string(index=False))
    summary["환승역_상위N_마비"] = rows

    # 5) 대전 사례
    daejeon = None
    for c in comps:
        ops = [G.nodes[n].get("운영기관", "") for n in c]
        if any("대전" in str(o) for o in ops):
            daejeon = list(c); break
    if daejeon:
        dj_imp, dj_base = single_removal_sweep(G, daejeon)
        dj_imp.to_csv(OUT + "single_removal_impact_daejeon.csv", index=False, encoding="utf-8-sig")
        dj_cen = centralities(G, daejeon)
        dj_cen.sort_values("매개중심성", ascending=False).to_csv(
            OUT + "centrality_daejeon.csv", index=False, encoding="utf-8-sig")
        print(f"\n[대전 {len(daejeon)}개역 — 영향도 상위 5]")
        print(dj_imp.head(5)[["역사명", "효율저하율_%", "승객가중효율저하율_%"]].to_string(index=False))
        summary["대전_역수"] = len(daejeon)

    # 도시별 요약
    city_rows = []
    for c in comps:
        if len(c) < 5:
            continue
        sub = G.subgraph(c)
        m, _ = Net(G, list(c)).matrix()
        D = shortest_path(m, method="D", directed=False)
        finite = D[np.isfinite(D)]
        city_rows.append({
            "권역": pd.Series([G.nodes[n].get("운영기관", "") for n in c]).mode()[0],
            "역수": len(c), "엣지수": sub.number_of_edges(),
            "평균차수": round(2 * sub.number_of_edges() / len(c), 2),
            "평균최단거리_km": round(finite[finite > 0].mean() / 1000, 2),
            "전역효율": round(efficiency(m), 6),
        })
    pd.DataFrame(city_rows).to_csv(OUT + "city_summary.csv", index=False, encoding="utf-8-sig")

    json.dump(summary, open(OUT + "summary.json", "w"), ensure_ascii=False,
              indent=2, default=str)
    print("\n결과 저장 완료 →", OUT)


if __name__ == "__main__":
    main()
