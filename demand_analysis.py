# -*- coding: utf-8 -*-
"""
실수요 기반 취약성 재분석

기존 분석은 OD 부재를 '운행빈도'(공급 지표)로 대체했다. 여기서는 KRIC 철도통계의
역별 승하차 실적(실수요)을 노드 가중치로 사용해 승객 영향을 다시 계산하고,
① 프록시가 실수요를 얼마나 잘 대리했는지 검증하고,
② 구조적 취약성(절점)과 수요를 교차해 '우선 보강 대상'을 도출한다.

구조적으로 취약해도 수요가 없으면 정책 우선순위가 낮고, 수요가 커도 우회로가 있으면
중단 영향이 제한된다. 두 축의 교집합이 실무적으로 의미 있는 대상이다.

출력 : results/criticality_metro.csv, results/priority_stations.csv,
       results/proxy_vs_demand.csv
"""
import numpy as np
import pandas as pd
import networkx as nx
from scipy.stats import spearmanr

from analyze import (load_graph, Net, efficiency, lcc_size,
                     denom_unweighted, denom_weighted)

PROC, RES = "data/processed/", "results/"


def demand_vector(net, G):
    """노드별 일평균 승하차. 미매칭은 해당 권역 하위 25% 값으로 보수적 대체."""
    nd = pd.read_csv(PROC + "node_demand.csv").set_index("node_id")
    d = np.array([nd["일평균승하차_배분"].get(n, np.nan) for n in net.nodes], dtype=float)
    matched = np.isfinite(d)
    fill = np.nanpercentile(d[matched], 25) if matched.any() else 1.0
    d[~matched] = fill
    return d, matched


def main():
    G = load_graph()
    metro = sorted(max(nx.connected_components(G), key=len))
    net = Net(G, metro)
    dem, matched = demand_vector(net, G)
    print(f"수도권 {net.n}개 노드 · 수요 매칭 {matched.sum()} ({matched.mean()*100:.1f}%)")

    mat, _ = net.matrix()
    DU = denom_unweighted(net.n)
    DD = denom_weighted(dem)          # 실수요 가중
    DF = denom_weighted(net.freq)     # 운행빈도 프록시
    E0 = efficiency(mat, denom=DU)
    Ed0 = efficiency(mat, weights=dem, denom=DD)
    Ef0 = efficiency(mat, weights=net.freq, denom=DF)
    S0 = lcc_size(mat)

    H = G.subgraph(net.nodes)
    arts = set(nx.articulation_points(H))

    print("단일 역사 제거 스윕(실수요 가중) 실행 중...")
    rows = []
    for i, node in enumerate(net.nodes):
        mask = np.ones(net.n, dtype=bool); mask[i] = False
        sub, keep = net.matrix(mask)
        E = efficiency(sub, denom=DU)
        Ed = efficiency(sub, weights=dem[keep], denom=DD)
        Ef = efficiency(sub, weights=net.freq[keep], denom=DF)
        rows.append({
            "node_id": node,
            "역사명": G.nodes[node].get("역사명", ""),
            "노선명": G.nodes[node].get("노선명", ""),
            "운영기관": G.nodes[node].get("운영기관", ""),
            "일평균승하차": round(dem[i], 1),
            "수요매칭": int(matched[i]),
            "절점": int(node in arts),
            "효율저하율_%": round((E0 - E) / E0 * 100, 4),
            "실수요가중_저하율_%": round((Ed0 - Ed) / Ed0 * 100, 4),
            "운행빈도가중_저하율_%": round((Ef0 - Ef) / Ef0 * 100, 4),
            "분리규모": int(S0 - 1 - lcc_size(sub)),
        })
    d = pd.DataFrame(rows)

    # ① 프록시 검증: 운행빈도 가중 vs 실수요 가중
    r_imp, p_imp = spearmanr(d["운행빈도가중_저하율_%"], d["실수요가중_저하율_%"])
    r_w, p_w = spearmanr(net.freq, dem)
    pd.DataFrame([
        {"비교": "노드가중치: 운행빈도 vs 실수요", "rho": round(r_w, 3), "p": f"{p_w:.2e}", "n": net.n},
        {"비교": "제거영향도: 프록시가중 vs 실수요가중", "rho": round(r_imp, 3),
         "p": f"{p_imp:.2e}", "n": len(d)},
    ]).to_csv(RES + "proxy_vs_demand.csv", index=False, encoding="utf-8-sig")
    print(f"\n[프록시 검증] 노드가중치 rho={r_w:.3f} · 제거영향도 rho={r_imp:.3f}")

    # ② 구조 × 수요 교차 → 우선 보강 대상
    q_dem = d["일평균승하차"].quantile(0.75)
    q_imp = d["실수요가중_저하율_%"].quantile(0.75)
    def quad(r):
        hi_d, hi_i = r["일평균승하차"] >= q_dem, r["실수요가중_저하율_%"] >= q_imp
        if hi_d and hi_i:
            return "1_최우선(고수요·고영향)"
        if hi_i:
            return "2_구조취약(저수요·고영향)"
        if hi_d:
            return "3_고수요(우회가능)"
        return "4_일반"
    d["구분"] = d.apply(quad, axis=1)
    d["우선보강"] = ((d["구분"] == "1_최우선(고수요·고영향)") & (d["절점"] == 1)).astype(int)
    d = d.sort_values("실수요가중_저하율_%", ascending=False)
    d.to_csv(RES + "criticality_metro.csv", index=False, encoding="utf-8-sig")

    print("\n[구분별 역 수]")
    print(d["구분"].value_counts().sort_index().to_string())

    pri = d[d["우선보강"] == 1].sort_values("실수요가중_저하율_%", ascending=False)
    pri.to_csv(RES + "priority_stations.csv", index=False, encoding="utf-8-sig")
    print(f"\n[우선 보강 대상 = 절점 ∩ 고수요 ∩ 고영향] {len(pri)}개")
    print(pri.head(15)[["역사명", "노선명", "일평균승하차",
                        "실수요가중_저하율_%", "분리규모"]].to_string(index=False))
    return d


if __name__ == "__main__":
    main()
