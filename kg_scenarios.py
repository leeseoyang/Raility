# -*- coding: utf-8 -*-
"""
지식그래프 기반 계층적 장애 시나리오 분석

단일 역-역 그래프로는 '어느 역이 어느 노선/기관/지역에 속하는지'를 알 수 없어
개별 역 제거만 가능하다. KG의 타입 관계(ON_LINE, OPERATED_BY, LOCATED_IN)를
질의하면 상위 계층 단위의 동시 장애를 시뮬레이션할 수 있다.

  시나리오 A  노선 단위 통째 중단   (ON_LINE)
  시나리오 B  운영기관 전체 마비     (OPERATED_BY)
  시나리오 C  광역시도 단위 마비     (LOCATED_IN)

출력 : results/kg_scenario_{line,operator,region}.csv
"""
import numpy as np
import pandas as pd

from analyze import load_graph, Net, efficiency, lcc_size, denom_unweighted

KG = "kg/"
RES = "results/"


def kg_membership(kge, predicate):
    """KG 질의: predicate 관계로 묶인 Station 집합을 대상별로 반환"""
    d = kge[kge["predicate"] == predicate]
    out = {}
    for tgt, g in d.groupby("target"):
        out[tgt] = [s.split(":", 1)[1] for s in g["source"] if s.startswith("Station:")]
    return out


def run_scenarios():
    G = load_graph()
    kgn = pd.read_csv(KG + "kg_nodes.csv")
    kge = pd.read_csv(KG + "kg_edges.csv")
    label = dict(zip(kgn["id"], kgn["label"]))

    by_area = kg_membership(kge, "IN_METRO_AREA")
    scen = {"노선": kg_membership(kge, "ON_LINE"),
            "운영기관": kg_membership(kge, "OPERATED_BY"),
            "광역시도": kg_membership(kge, "LOCATED_IN")}

    # 권역별 기준 네트워크
    area_net = {}
    for area, members in by_area.items():
        ns = [n for n in members if n in G]
        if len(ns) < 5:
            continue
        net = Net(G, ns)
        mat, _ = net.matrix()
        du = denom_unweighted(net.n)   # 원 네트워크 크기로 고정 정규화
        area_net[area] = (net, efficiency(mat, denom=du), lcc_size(mat), du)

    results = {k: [] for k in scen}
    for kind, groups in scen.items():
        for gid, members in groups.items():
            ns = set(n for n in members if n in G)
            if not ns:
                continue
            # 이 그룹이 속한 권역(가장 많이 겹치는 곳)
            best = max(area_net, key=lambda a: len(ns & set(by_area[a])), default=None)
            if best is None:
                continue
            net, E0, S0, du = area_net[best]
            idx = [net.idx[n] for n in ns if n in net.idx]
            if not idx or len(idx) >= net.n - 2:
                continue
            mask = np.ones(net.n, dtype=bool)
            mask[idx] = False
            m, keep = net.matrix(mask)
            E, S = efficiency(m, denom=du), lcc_size(m)
            deg = m.getnnz(axis=1)
            results[kind].append({
                "권역": label.get(best, best), "대상": label.get(gid, gid),
                "제거역수": len(idx), "권역내비율_%": round(len(idx) / net.n * 100, 1),
                "효율저하율_%": round((E0 - E) / E0 * 100, 2),
                "LCC비율_%": round(S / S0 * 100, 1),
                "잔여고립역수": int((deg == 0).sum()),
                "효율저하_per_역": round((E0 - E) / E0 * 100 / len(idx), 3),
            })

    out = {}
    for kind, rows in results.items():
        df = pd.DataFrame(rows).sort_values("효율저하율_%", ascending=False)
        fn = {"노선": "line", "운영기관": "operator", "광역시도": "region"}[kind]
        df.to_csv(f"{RES}kg_scenario_{fn}.csv", index=False, encoding="utf-8-sig")
        out[kind] = df
        print(f"\n===== 시나리오: {kind} 단위 중단 (상위 8) =====")
        print(df.head(8).to_string(index=False))
    return out


if __name__ == "__main__":
    run_scenarios()
