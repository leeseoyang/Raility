# -*- coding: utf-8 -*-
"""
주장 검증 — 결과를 논문에 쓰기 전에 통계로 확인한다.

상위 N개 목록을 눈으로 비교해 "일치/불일치"를 주장하면 체리피킹이 된다.
전체 표본에 대한 순위상관과 위상 지표로 각 주장이 실제로 성립하는지 검증한다.

출력 : results/claim_validation.csv, results/topology_summary.csv
"""
import numpy as np
import pandas as pd
import networkx as nx
from scipy.stats import spearmanr

PROC, RES = "data/processed/", "results/"


def main():
    G = nx.read_graphml(PROC + "network.graphml")
    comps = sorted(nx.connected_components(G), key=len, reverse=True)

    # ---------- ① 중심성이 실제 제거 영향도를 예측하는가 ----------
    cen = pd.read_csv(RES + "centrality_metro.csv").set_index("node_id")
    imp = pd.read_csv(RES + "single_removal_impact_metro.csv").set_index("node_id")
    d = cen.join(imp[["효율저하율_%", "승객가중효율저하율_%"]], how="inner")
    rows = []
    for c in ["매개중심성", "연결중심성", "근접중심성", "고유벡터중심성"]:
        r1, p1 = spearmanr(d[c], d["효율저하율_%"])
        r2, p2 = spearmanr(d[c], d["승객가중효율저하율_%"])
        rows.append({"중심성": c, "n": len(d),
                     "vs_효율저하_rho": round(r1, 3), "vs_효율저하_p": f"{p1:.2e}",
                     "vs_승객가중_rho": round(r2, 3), "vs_승객가중_p": f"{p2:.2e}"})
    corr = pd.DataFrame(rows)
    corr.to_csv(RES + "claim_validation.csv", index=False, encoding="utf-8-sig")
    print("① 중심성 vs 실제 제거 영향도 (수도권 n=%d)" % len(d))
    print(corr.to_string(index=False))
    print("  → 매개중심성 rho=%.3f. 강한 양의 상관이므로 '중심성과 실제 영향도가"
          " 어긋난다'는 주장은 성립하지 않는다." % corr.loc[0, "vs_효율저하_rho"])

    # ---------- ② 위상 구조: 절점·다리 수는 희소성의 귀결인가 ----------
    trows = []
    for c in comps:
        if len(c) < 5:
            continue
        S = G.subgraph(c)
        N, E = S.number_of_nodes(), S.number_of_edges()
        ops = pd.Series([G.nodes[n].get("운영기관", "") for n in c]).mode()[0]
        names = {G.nodes[n].get("역사명", "") for n in c}
        trows.append({
            "권역대표기관": ops, "노드수": N, "물리적역수": len(names), "엣지수": E,
            "트리기준엣지수": N - 1, "순환수": E - N + 1,
            "순환밀도": round((E - N + 1) / N, 4),
            "절점수": len(list(nx.articulation_points(S))),
            "절점비율_%": round(len(list(nx.articulation_points(S))) / N * 100, 1),
            "다리수": len(list(nx.bridges(S))),
            "다리비율_%": round(len(list(nx.bridges(S))) / E * 100, 1),
            "평균차수": round(2 * E / N, 2),
        })
    topo = pd.DataFrame(trows).sort_values("노드수", ascending=False)
    topo.to_csv(RES + "topology_summary.csv", index=False, encoding="utf-8-sig")
    print("\n② 권역별 위상 구조")
    print(topo.to_string(index=False))
    print("  → 순환수가 노드수 대비 매우 작다(트리에 근접). 절점·다리가 많은 것은"
          " 발견이 아니라 희소한 위상의 구조적 귀결이다.")
    return corr, topo


if __name__ == "__main__":
    main()
