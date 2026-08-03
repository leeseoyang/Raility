# -*- coding: utf-8 -*-
"""
환승 비용 민감도 분석

환승 1회를 거리 몇 m에 상당하는 비용으로 볼 것인가는 임의 가정이며, 이 값이
최단경로·매개중심성·취약성 순위를 흔들 수 있다. 기준값 200 m를 중심으로
50~1600 m를 훑어 결론의 안정성을 검증한다.

검증 지표
  · 매개중심성 순위의 스피어만 상관 (기준 대비)
  · 상위 20개 역 집합의 자카드 중첩도
  · 우선 보강 대상 19개 역의 영향도 순위 안정성

출력 : results/sensitivity_transfer_cost.csv
"""
import numpy as np
import pandas as pd
import networkx as nx
from scipy.stats import spearmanr

from analyze import (load_graph, Net, efficiency, lcc_size, denom_unweighted,
                     denom_weighted, TRANSFER_COST_M)
from demand_analysis import demand_vector

RES = "results/"
COSTS = [50, 100, 200, 400, 800, 1600]
BASE = 200


def rebuild_weights(G, cost):
    for u, v, d in G.edges(data=True):
        if d.get("type") == "환승":
            d["w"] = float(cost)
    return G


def main():
    G = load_graph()
    metro = sorted(max(nx.connected_components(G), key=len))
    pri = pd.read_csv(RES + "priority_stations.csv")["node_id"].tolist()

    btw, imp, rows = {}, {}, []
    for c in COSTS:
        rebuild_weights(G, c)
        net = Net(G, metro)
        dem, _ = demand_vector(net, G)
        H = G.subgraph(metro)
        b = nx.betweenness_centrality(H, weight="w")
        btw[c] = pd.Series(b)

        mat, _ = net.matrix()
        DU, DD = denom_unweighted(net.n), denom_weighted(dem)
        E0 = efficiency(mat, denom=DU)
        Ed0 = efficiency(mat, weights=dem, denom=DD)

        # 우선 보강 대상만 재계산(전수 스윕은 비용이 커서 대상 한정)
        vals = {}
        for n in pri:
            i = net.idx.get(n)
            if i is None:
                continue
            m = np.ones(net.n, dtype=bool); m[i] = False
            sub, keep = net.matrix(m)
            vals[n] = (Ed0 - efficiency(sub, weights=dem[keep], denom=DD)) / Ed0 * 100
        imp[c] = pd.Series(vals)
        rows.append({"환승비용_m": c, "전역효율": round(E0, 8),
                     "실수요가중효율": round(Ed0, 10)})
        print(f"  환승비용 {c:>5} m 계산 완료")

    base_b, base_i = btw[BASE], imp[BASE]
    out = []
    for r in rows:
        c = r["환승비용_m"]
        rho_b, _ = spearmanr(btw[c], base_b)
        top_c = set(btw[c].nlargest(20).index)
        top_b = set(base_b.nlargest(20).index)
        jac = len(top_c & top_b) / len(top_c | top_b)
        rho_i, _ = spearmanr(imp[c], base_i)
        out.append({**r,
                    "매개중심성_rho_vs기준": round(rho_b, 4),
                    "상위20_자카드": round(jac, 3),
                    "우선대상_영향도_rho": round(rho_i, 4)})
    df = pd.DataFrame(out)
    df.to_csv(RES + "sensitivity_transfer_cost.csv", index=False, encoding="utf-8-sig")
    print("\n[환승 비용 민감도]")
    print(df.to_string(index=False))
    lo = df[df["환승비용_m"] != BASE]
    print(f"\n  매개중심성 순위상관 최솟값 {lo['매개중심성_rho_vs기준'].min():.3f} · "
          f"상위20 자카드 최솟값 {lo['상위20_자카드'].min():.3f} · "
          f"우선대상 순위상관 최솟값 {lo['우선대상_영향도_rho'].min():.3f}")
    return df


if __name__ == "__main__":
    main()
