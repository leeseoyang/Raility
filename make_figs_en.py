# -*- coding: utf-8 -*-
"""
KITS 투고용 영문 그림 4종 (규정 15: 그림의 제목·내용을 모두 영문으로 작성)

  Fig1_network_en.png      전국 네트워크 지도 + 권역별 순환밀도 (발견 ①)
  Fig2_resilience_en.png   제거 전략별 복원력 곡선 (발견 ②)
  Fig3_demand_en.png       수요 지표 3원 교차검증 산점도 (발견 ③)
  Fig4_criticality_en.png  구조 취약성 × 수요 사분면 (정책 결론)

그림 제목은 원고에서 그림 하단에 <Fig. n> 형식으로 붙이므로, 이미지 안에는
설명 문구를 최소화하고 축·범례·주석만 영문으로 둔다.
6쪽 지면을 고려해 폭 기준 단단(單段) 배치를 가정한 크기로 저장한다.
"""
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.stats import spearmanr

GRAPH, RES, FIG = "data/processed/network.graphml", "results/", "figures/"

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({
    "figure.dpi": 300, "savefig.dpi": 300,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#b8b7b0", "axes.labelcolor": "#0b0b0b",
    "text.color": "#0b0b0b", "xtick.color": "#52514e", "ytick.color": "#52514e",
    "grid.color": "#e3e2dc", "grid.linewidth": 0.6,
    "font.size": 9, "axes.titlesize": 10.5, "legend.frameon": False,
})
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
SURFACE, INK, INK2, INK3 = "#ffffff", "#0b0b0b", "#52514e", "#8a8984"

REGION_EN = {"수도권": "Seoul Metropolitan Area", "부산·김해": "Busan–Gimhae",
             "대구": "Daegu", "대전": "Daejeon", "광주": "Gwangju"}
REGION_SHORT = {"수도권": "SMA", "부산·김해": "Busan–Gimhae", "대구": "Daegu",
                "대전": "Daejeon", "광주": "Gwangju"}
OPER_EN = {"한국철도공사": "수도권", "부산광역시 부산교통공사": "부산·김해",
           "대구교통공사": "대구", "대전교통공사": "대전", "광주교통공사": "광주"}
STATION_EN = {"강동": "Gangdong", "수원역": "Suwon", "회룡역": "Hoeryong",
              "노원": "Nowon", "검암": "Geomam", "상계": "Sanggye",
              "의정부역": "Uijeongbu", "홍대입구": "Hongik Univ.", "서울역": "Seoul Stn.",
              "강남": "Gangnam", "청량리역": "Cheongnyangni", "잠실(송파구청)": "Jamsil",
              "도봉산역": "Dobongsan", "망월사역": "Mangwolsa", "신도림": "Sindorim"}


def region_of(op):
    op = str(op)
    if any(k in op for k in ["부산", "김해"]):
        return "부산·김해"
    for k in ("대구", "대전", "광주"):
        if k in op:
            return k
    return "수도권"


def load_graph():
    G = nx.read_graphml(GRAPH)
    for n, d in G.nodes(data=True):
        for k in ("lat", "lon"):
            try:
                d[k] = float(d.get(k, ""))
            except (TypeError, ValueError):
                d[k] = np.nan
    return G


# ------------------------------------------------------------------ Fig 1
def fig1(G):
    """지도이면서 발견 ①(권역별 순환밀도 격차)을 함께 전달한다."""
    topo = pd.read_csv(RES + "topology_summary.csv")
    topo["region"] = topo["권역대표기관"].map(lambda o: OPER_EN.get(str(o), region_of(o)))
    tmap = topo.set_index("region")

    comps = [c for c in sorted(nx.connected_components(G), key=len, reverse=True)
             if len(c) >= 5]
    reg_order, reg_nodes = [], {}
    for c in comps:
        r = pd.Series([region_of(G.nodes[n].get("운영기관", "")) for n in c]).mode()[0]
        if r not in reg_nodes:
            reg_nodes[r] = set(); reg_order.append(r)
        reg_nodes[r] |= set(c)
    color = {r: CAT[i % len(CAT)] for i, r in enumerate(reg_order)}
    # 권역은 운영기관이 아니라 '연결성분'으로 정한다. 대경선·동해선은 운영기관이
    # 한국철도공사라 기관 기준으로 칠하면 대구·부산 노선이 수도권 색으로 나온다.
    node_region = {n: r for r, ns in reg_nodes.items() for n in ns}

    fig, ax = plt.subplots(figsize=(7.0, 8.2))
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)

    for u, v, d in G.edges(data=True):
        x = [G.nodes[u]["lon"], G.nodes[v]["lon"]]
        y = [G.nodes[u]["lat"], G.nodes[v]["lat"]]
        if not np.all(np.isfinite(x + y)):
            continue
        if d.get("type") == "환승":
            ax.plot(x, y, color="#c9c8c1", lw=0.5, zorder=1)
        else:
            ax.plot(x, y, color=color.get(node_region.get(u), INK3), lw=0.9,
                    alpha=.75, zorder=2)

    deg = dict(G.degree())
    for r in reg_order:
        ns = [n for n in reg_nodes[r] if np.isfinite(G.nodes[n]["lat"])]
        cd = tmap["순환밀도"].get(r, np.nan)
        ax.scatter([G.nodes[n]["lon"] for n in ns], [G.nodes[n]["lat"] for n in ns],
                   s=[6 + 7 * deg[n] for n in ns], c=color[r], edgecolors=SURFACE,
                   linewidths=.4, zorder=3,
                   label=f"{REGION_EN[r]}  (n={len(ns)}, α={cd:.3f})")

    for r in reg_order:
        ns = [n for n in reg_nodes[r] if np.isfinite(G.nodes[n]["lat"])]
        cx = np.mean([G.nodes[n]["lon"] for n in ns])
        cy = max(G.nodes[n]["lat"] for n in ns)
        cd = tmap["순환밀도"].get(r, np.nan)
        ax.annotate(f"{REGION_SHORT[r]}\nα = {cd:.3f}", (cx, cy + .05), ha="center",
                    va="bottom", fontsize=8.6, color=INK, fontweight="bold",
                    linespacing=1.25)

    ax.set_xlabel("Longitude (°E)", color=INK2)
    ax.set_ylabel("Latitude (°N)", color=INK2)
    ax.legend(loc="upper right", fontsize=7.6, labelcolor=INK2, handletextpad=.4,
              title="Region  (nodes, cyclomatic density)", title_fontsize=7.6)
    ax.grid(True, alpha=.5, lw=.5); ax.set_axisbelow(True)
    ax.set_aspect(1.24)
    fig.tight_layout()
    fig.savefig(FIG + "Fig1_network_en.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig); print("saved Fig1_network_en")


# ------------------------------------------------------------------ Fig 2
def fig2():
    spec = [("random", "Random failure", CAT[0]),
            ("degree", "Degree-targeted", CAT[1]),
            ("betweenness", "Betweenness-targeted (static)", CAT[2]),
            ("adaptive", "Adaptive targeted (recomputed)", CAT[3])]
    data = {k: pd.read_csv(f"{RES}resilience_{k}_metro.csv") for k, _, _ in spec}

    def destack(vals, gap=6.0):
        order = np.argsort(-np.asarray(vals))
        out = np.array(vals, dtype=float); prev = None
        for i in order:
            if prev is not None and prev - out[i] < gap:
                out[i] = prev - gap
            prev = out[i]
        return out

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.2), sharex=True)
    fig.patch.set_facecolor(SURFACE)
    for ax, col, ttl in zip(axes, ["효율비율", "LCC비율"],
                            ["Global efficiency  $E/E_0$",
                             "Largest connected component  $S/S_0$"]):
        ax.set_facecolor(SURFACE)
        ypos = destack([data[k][col].iloc[-1] * 100 for k, _, _ in spec])
        for (key, lab, c), ye in zip(spec, ypos):
            d = data[key]
            ax.plot(d["제거비율"] * 100, d[col] * 100, color=c, lw=2, label=lab,
                    solid_capstyle="round")
            ax.annotate(lab, (d["제거비율"].iloc[-1] * 100, ye), xytext=(5, 0),
                        textcoords="offset points", fontsize=7.0, color=c, va="center")
        ax.axvline(10, color=INK3, lw=.8, ls=":")
        ax.annotate("10%", (10, 96), fontsize=7.2, color=INK3, ha="center")
        ax.set_xlabel("Stations removed (%)", color=INK2)
        ax.set_ylabel(f"{ttl.split('  ')[0]} (%)", color=INK2)
        ax.set_title(ttl, loc="left", color=INK, pad=6)
        ax.grid(True, alpha=.6, lw=.5); ax.set_axisbelow(True)
        ax.set_xlim(0, 34); ax.set_ylim(0, 104)
    handles = [Line2D([], [], color=c, lw=2, label=l) for _, l, c in spec]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, 1.0),
               ncol=4, fontsize=8.2, labelcolor=INK2, columnspacing=1.4)
    fig.tight_layout(rect=[0, 0, 1, .92])
    fig.savefig(FIG + "Fig2_resilience_en.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig); print("saved Fig2_resilience_en")


# ------------------------------------------------------------------ Fig 3
def fig3():
    d = pd.read_csv(RES + "demand_source_scatter.csv")
    both_all = d.dropna(subset=["KRIC승하차", "카드승하차"])
    freq_all = d.dropna(subset=["KRIC승하차"])
    r1, _ = spearmanr(both_all["KRIC승하차"], both_all["카드승하차"])
    r2, _ = spearmanr(freq_all["운행빈도"], freq_all["KRIC승하차"])
    n1, n2 = len(both_all), len(freq_all)
    both = both_all[(both_all["KRIC승하차"] > 0) & (both_all["카드승하차"] > 0)]
    freq = freq_all[(freq_all["KRIC승하차"] > 0) & (freq_all["운행빈도"] > 0)]

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.2))
    fig.patch.set_facecolor(SURFACE)

    ax = axes[0]; ax.set_facecolor(SURFACE)
    ax.grid(True, which="both", alpha=.5, zorder=0)
    ax.scatter(both["KRIC승하차"], both["카드승하차"], s=10, c=CAT[0], alpha=.55,
               linewidths=0, zorder=3)
    lo = min(both["KRIC승하차"].min(), both["카드승하차"].min())
    hi = max(both["KRIC승하차"].max(), both["카드승하차"].max())
    ax.plot([lo, hi], [lo, hi], color=INK2, lw=1, ls="--", zorder=2)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Agency ridership statistics (pax/day)", color=INK2)
    ax.set_ylabel("Smart-card measurement (pax/day)", color=INK2)
    ax.set_title("(a) Two independent demand measurements", loc="left", color=INK)
    ax.text(.04, .95, f"$\\rho$ = {r1:.3f}   n = {n1:,}", transform=ax.transAxes,
            fontsize=10, fontweight="bold", color=CAT[0], va="top")
    ax.text(.04, .87, "dashed line: y = x", transform=ax.transAxes, fontsize=7.6,
            color=INK2, va="top")

    ax = axes[1]; ax.set_facecolor(SURFACE)
    ax.grid(True, which="both", alpha=.5, zorder=0)
    ax.scatter(freq["운행빈도"], freq["KRIC승하차"], s=10, c=CAT[1], alpha=.55,
               linewidths=0, zorder=3)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Service-frequency proxy (weekday train counts)", color=INK2)
    ax.set_ylabel("Agency ridership statistics (pax/day)", color=INK2)
    ax.set_title("(b) Supply proxy vs. demand", loc="left", color=INK)
    ax.text(.04, .95, f"$\\rho$ = {r2:.3f}   n = {n2:,}", transform=ax.transAxes,
            fontsize=10, fontweight="bold", color=CAT[1], va="top")

    fig.text(.005, .01, "Spearman $\\rho$ computed on the full valid sample; "
             "zero-valued nodes are omitted from the log-scaled plots only.",
             fontsize=7.2, color=INK2)
    fig.tight_layout(rect=[0, .04, 1, 1])
    fig.savefig(FIG + "Fig3_demand_en.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig); print("saved Fig3_demand_en")


# ------------------------------------------------------------------ Fig 4
def fig4():
    d = pd.read_csv(RES + "criticality_metro.csv")
    qd = d["일평균승하차"].quantile(.75)
    qi = d["실수요가중_저하율_%"].quantile(.75)

    fig, ax = plt.subplots(figsize=(8.8, 5.8))
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    ax.axvline(qd, color=INK3, lw=.9, ls=":")
    ax.axhline(qi, color=INK3, lw=.9, ls=":")

    for is_art, lab, c, z in [(0, "Ordinary station", "#c9c8c1", 2),
                              (1, "Cut vertex (removal disconnects network)", CAT[1], 3)]:
        s = d[d["절점"] == is_art]
        ax.scatter(s["일평균승하차"], s["실수요가중_저하율_%"], s=24, c=c,
                   edgecolors=SURFACE, linewidths=.4, label=lab, zorder=z, alpha=.9)

    pri = d[d["우선보강"] == 1]
    ax.scatter(pri["일평균승하차"], pri["실수요가중_저하율_%"], s=62, facecolors="none",
               edgecolors=CAT[0], linewidths=1.6, zorder=4,
               label=f"Priority reinforcement target (n={len(pri)})")
    # 우선 보강 대상이 좁은 구간에 몰려 있어 라벨이 겹친다. 지시선을 달고
    # y좌표를 최소 간격으로 밀어 배치한다.
    lab = pri.sort_values("실수요가중_저하율_%", ascending=False)
    ys = lab["실수요가중_저하율_%"].to_numpy(dtype=float)
    gap = (ys.max() - ys.min()) * 0.16 + 0.06
    ty = ys.copy()
    for i in range(1, len(ty)):
        if ty[i - 1] - ty[i] < gap:
            ty[i] = ty[i - 1] - gap
    for (_, r), y_t in zip(lab.iterrows(), ty):
        nm = STATION_EN.get(r["역사명"], r["역사명"])
        ax.annotate(nm, xy=(r["일평균승하차"], r["실수요가중_저하율_%"]),
                    xytext=(r["일평균승하차"] * 2.6, y_t), textcoords="data",
                    fontsize=7.8, color=INK, ha="left", va="center",
                    arrowprops=dict(arrowstyle="-", color=INK3, lw=.6,
                                    shrinkA=0, shrinkB=3))

    ax.set_xscale("log")
    ax.set_xlim(left=6e2)
    ax.set_xlabel("Average daily boardings and alightings (log scale)", color=INK2)
    ax.set_ylabel("Demand-weighted efficiency loss on closure (%)", color=INK2)
    ymax = d["실수요가중_저하율_%"].max()
    ax.annotate("Quadrant I\nhigh demand · high impact", (qd * 1.15, ymax * .98),
                fontsize=8.4, color=INK2, ha="left", va="top", linespacing=1.3)
    ax.annotate("Quadrant II\nlow demand · high impact", (qd * .85, ymax * .98),
                fontsize=8.4, color=INK3, ha="right", va="top", linespacing=1.3)
    ax.set_ylim(-.25, ymax * 1.08)
    ax.legend(loc="upper left", fontsize=8.2, labelcolor=INK2)
    ax.grid(True, alpha=.5, lw=.5); ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIG + "Fig4_criticality_en.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig); print("saved Fig4_criticality_en")


if __name__ == "__main__":
    G = load_graph()
    fig1(G); fig2(); fig3(); fig4()
