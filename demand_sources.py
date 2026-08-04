# -*- coding: utf-8 -*-
"""
수요 지표 3종 교차검증 — 공급 프록시 · 기관 통계 · 교통카드 실측

취약성 분석에서 노드 가중치를 무엇으로 잡느냐가 결과를 좌우한다. 본 연구는 서로
독립적인 세 지표를 확보했다.

  ① 운행빈도 (공급)      : 국가철도공단 운행정보의 인접구간 평일 운행횟수 합
  ② 역별 승하차 (기관통계): KRIC 철도통계 19개 운영기관 연간 실적 (전국)
  ③ 교통카드 승하차 (실측): 서울시·한국스마트카드 역간 OD 7일치에서 집계 (수도권)

②와 ③은 수집 주체·집계 방식·기간이 모두 다르므로, 둘이 일치하면 수요 측정이
견고하다는 뜻이고, ①만 어긋나면 그것은 프록시 자체의 문제다. 이 삼각검증이
"프록시를 쓰면 안 된다"는 주장의 근거가 된다.

출력 : results/demand_source_agreement.csv
       results/demand_source_scatter.csv  (그림용)
"""
import numpy as np
import pandas as pd
import networkx as nx
from scipy.stats import spearmanr, pearsonr

from analyze import load_graph, Net

PROC, RES, OD = "data/processed/", "results/", "data/od/processed/"


def load_sources():
    G = load_graph()
    metro = sorted(max(nx.connected_components(G), key=len))
    net = Net(G, metro)

    kric = pd.read_csv(PROC + "node_demand.csv").set_index("node_id")["일평균승하차"]
    od = pd.read_csv(OD + "node_weights.csv").set_index("node_id")
    od_tot = (od["boarding_daily_avg"].fillna(0) + od["alighting_daily_avg"].fillna(0))
    od_src = od["weight_source"]

    df = pd.DataFrame({
        "node_id": net.nodes,
        "역사명": [G.nodes[n].get("역사명", "") for n in net.nodes],
        "노선명": [G.nodes[n].get("노선명", "") for n in net.nodes],
        "운행빈도": net.freq,
        "KRIC승하차": [kric.get(n, np.nan) for n in net.nodes],
        "카드승하차": [od_tot.get(n, np.nan) for n in net.nodes],
        "카드출처": [od_src.get(n, "none") for n in net.nodes],
    })
    # 교통카드 자료는 서울시 OD 기반이므로 seoul_od 출처만 유효 표본으로 본다
    df.loc[df["카드출처"] != "seoul_od", "카드승하차"] = np.nan
    return df


def main():
    d = load_sources()
    both = d.dropna(subset=["KRIC승하차", "카드승하차"])
    print(f"수도권 노드 {len(d)} · KRIC 매칭 {d['KRIC승하차'].notna().sum()} · "
          f"교통카드 매칭 {d['카드승하차'].notna().sum()} · 둘 다 {len(both)}")

    rows = []
    def add(name, a, b, sub):
        r, p = spearmanr(sub[a], sub[b])
        rp, _ = pearsonr(np.log1p(sub[a]), np.log1p(sub[b]))
        rows.append({"비교": name, "n": len(sub), "spearman_rho": round(r, 3),
                     "pearson_log_r": round(rp, 3), "p": f"{p:.2e}"})

    add("② KRIC 승하차 ↔ ③ 교통카드 승하차", "KRIC승하차", "카드승하차", both)
    add("① 운행빈도 ↔ ② KRIC 승하차", "운행빈도", "KRIC승하차",
        d.dropna(subset=["KRIC승하차"]))
    add("① 운행빈도 ↔ ③ 교통카드 승하차", "운행빈도", "카드승하차", both)
    out = pd.DataFrame(rows)
    out.to_csv(RES + "demand_source_agreement.csv", index=False, encoding="utf-8-sig")
    print("\n[수요 지표 3종 일치도]")
    print(out.to_string(index=False))

    r_kk = out.loc[0, "spearman_rho"]
    r_fk = out.loc[1, "spearman_rho"]
    print(f"\n  독립 수요 자료끼리는 ρ={r_kk} 로 일치하는 반면, 공급 프록시는 ρ={r_fk} 에 그친다.")
    print("  → 수요 측정 자체는 견고하며, 어긋나는 쪽은 프록시다.")

    # 불일치 상위: 두 수요 자료가 크게 다른 역 (자료 품질 점검용)
    b = both.copy()
    b["비율"] = b["카드승하차"] / b["KRIC승하차"].replace(0, np.nan)
    b = b[(b["KRIC승하차"] > 5000) | (b["카드승하차"] > 5000)]
    print("\n[두 수요 자료 불일치 상위 8]")
    print(b.reindex(b["비율"].sub(1).abs().sort_values(ascending=False).index)
          .head(8)[["역사명", "노선명", "KRIC승하차", "카드승하차", "비율"]]
          .to_string(index=False))

    d.to_csv(RES + "demand_source_scatter.csv", index=False, encoding="utf-8-sig")
    return out


if __name__ == "__main__":
    main()
