# -*- coding: utf-8 -*-
"""
시각화 4종 생성 (논문 게재용, 300dpi)
  fig1_network.png     전국 도시철도 네트워크 그래프
  fig2_resilience.png  복원력 곡선 (표적 공격 vs 무작위 제거)
  fig3_top_stations.png 핵심 역사 랭킹 (제거 시 승객가중 효율 저하)
  fig4_daejeon.png     대전 도시철도 취약성 사례

색상: 검증된 범주형 팔레트(CVD 통과), 순차 스케일은 단일 색상 light→dark.
대비 경고 슬롯은 직접 라벨로 보완.
"""
import json
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D

GRAPH = "data/processed/network.graphml"
RES = "results/"
FIG = "figures/"

# ---- 한글 폰트 ----
for cand in ["Noto Sans CJK KR", "Noto Sans CJK JP", "NanumGothic", "Malgun Gothic"]:
    if any(cand in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = cand
        break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({
    "figure.dpi": 300, "savefig.dpi": 300,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#b8b7b0", "axes.labelcolor": "#0b0b0b",
    "text.color": "#0b0b0b", "xtick.color": "#52514e", "ytick.color": "#52514e",
    "grid.color": "#e3e2dc", "grid.linewidth": 0.6,
    "font.size": 9, "axes.titlesize": 11, "legend.frameon": False,
})

SURFACE = "#fcfcfb"
INK, INK2, INK3 = "#0b0b0b", "#52514e", "#8a8880"
# 검증 통과 범주형 팔레트 (고정 순서, 순환 금지)
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]


def region_of(op):
    op = str(op)
    if any(k in op for k in ["부산", "김해"]):
        return "부산·김해"
    if "대구" in op:
        return "대구"
    if "대전" in op:
        return "대전"
    if "광주" in op:
        return "광주"
    return "수도권"


def load():
    G = nx.read_graphml(GRAPH)
    for n, d in G.nodes(data=True):
        for k in ("lat", "lon"):
            try:
                d[k] = float(d.get(k, ""))
            except (TypeError, ValueError):
                d[k] = np.nan
    return G


# ------------------------------------------------------------------ fig 1
def fig_network(G):
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    comps = [c for c in comps if len(c) >= 5]
    reg_order, reg_nodes = [], {}
    for c in comps:
        r = pd.Series([region_of(G.nodes[n].get("운영기관", "")) for n in c]).mode()[0]
        if r not in reg_nodes:
            reg_nodes[r] = set(); reg_order.append(r)
        reg_nodes[r] |= set(c)
    color = {r: CAT[i % len(CAT)] for i, r in enumerate(reg_order)}

    fig, ax = plt.subplots(figsize=(7.2, 8.4))
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)

    for u, v, d in G.edges(data=True):
        x = [G.nodes[u]["lon"], G.nodes[v]["lon"]]
        y = [G.nodes[u]["lat"], G.nodes[v]["lat"]]
        if not np.all(np.isfinite(x + y)):
            continue
        if d.get("type") == "환승":
            ax.plot(x, y, color="#c9c8c1", lw=0.5, zorder=1)
        else:
            r = region_of(G.nodes[u].get("운영기관", ""))
            ax.plot(x, y, color=color.get(r, INK3), lw=0.9, alpha=0.75, zorder=2)

    deg = dict(G.degree())
    for r in reg_order:
        ns = [n for n in reg_nodes[r] if np.isfinite(G.nodes[n]["lat"])]
        ax.scatter([G.nodes[n]["lon"] for n in ns], [G.nodes[n]["lat"] for n in ns],
                   s=[6 + 7 * deg[n] for n in ns], c=color[r],
                   edgecolors=SURFACE, linewidths=0.4, zorder=3, label=f"{r} ({len(ns)})")

    # 직접 라벨 (대비 경고 보완)
    for r in reg_order:
        ns = [n for n in reg_nodes[r] if np.isfinite(G.nodes[n]["lat"])]
        cx = np.mean([G.nodes[n]["lon"] for n in ns])
        cy = max(G.nodes[n]["lat"] for n in ns)
        ax.annotate(f"{r}  {len(ns)}역", (cx, cy + 0.06), ha="center", fontsize=9.5,
                    color=INK, fontweight="bold")

    ax.set_xlabel("경도 (°E)", color=INK2); ax.set_ylabel("위도 (°N)", color=INK2)
    ax.set_title("전국 도시철도 네트워크 그래프\n노드 1,094 · 엣지 1,266 (운행 1,089 + 환승 177)",
                 loc="left", color=INK)
    ax.legend(loc="upper right", fontsize=8, labelcolor=INK2, handletextpad=0.4)
    ax.grid(True, alpha=0.5, lw=0.5); ax.set_axisbelow(True)
    ax.set_aspect(1.24)
    fig.tight_layout(); fig.savefig(FIG + "fig1_network.png", facecolor=SURFACE)
    plt.close(fig); print("saved fig1")


# ------------------------------------------------------------------ fig 2
def fig_resilience():
    spec = [("random", "무작위 제거", CAT[0]), ("degree", "연결중심성 표적", CAT[1]),
            ("betweenness", "매개중심성 표적", CAT[2]), ("adaptive", "적응형 표적(재계산)", CAT[3])]
    data = {k: pd.read_csv(f"{RES}resilience_{k}_metro.csv") for k, _, _ in spec}

    def destack(vals, gap=6.0):
        """끝단 직접 라벨 y좌표 충돌 방지(위→아래 순서 유지하며 최소 간격 확보)"""
        order = np.argsort(-np.asarray(vals))
        out = np.array(vals, dtype=float)
        prev = None
        for i in order:
            if prev is not None and prev - out[i] < gap:
                out[i] = prev - gap
            prev = out[i]
        return out

    fig, axes = plt.subplots(1, 2, figsize=(9.8, 4.4), sharex=True)
    fig.patch.set_facecolor(SURFACE)
    for ax, col, ttl in zip(axes, ["효율비율", "LCC비율"],
                            ["전역 효율 $E/E_0$", "최대연결요소 $S/S_0$"]):
        ax.set_facecolor(SURFACE)
        ends = [data[k][col].iloc[-1] * 100 for k, _, _ in spec]
        ypos = destack(ends)
        for (key, lab, c), ye in zip(spec, ypos):
            d = data[key]
            ax.plot(d["제거비율"] * 100, d[col] * 100, color=c, lw=2, label=lab,
                    solid_capstyle="round")
            ax.annotate(lab, (d["제거비율"].iloc[-1] * 100, ye),
                        xytext=(5, 0), textcoords="offset points", fontsize=7.4,
                        color=c, va="center")
        ax.axvline(10, color=INK3, lw=0.8, ls=":")
        ax.set_xlabel("제거된 역사 비율 (%)", color=INK2)
        ax.set_ylabel(f"{ttl} (%)", color=INK2)
        ax.set_title(ttl, loc="left", color=INK, pad=6)
        ax.grid(True, alpha=0.6, lw=0.5); ax.set_axisbelow(True)
        ax.set_xlim(0, 39); ax.set_ylim(0, 104)
    handles = [Line2D([], [], color=c, lw=2, label=l) for _, l, c in spec]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.925),
               ncol=4, fontsize=8.5, labelcolor=INK2, columnspacing=1.6)
    fig.suptitle("표적 공격 vs 무작위 제거에 대한 수도권 네트워크 복원력 곡선",
                 x=0.012, y=0.985, ha="left", color=INK, fontsize=11.5)
    fig.tight_layout(rect=[0, 0, 1, 0.885])
    fig.savefig(FIG + "fig2_resilience.png", facecolor=SURFACE)
    plt.close(fig); print("saved fig2")


# ------------------------------------------------------------------ fig 3
def fig_top_stations(k=15):
    d = pd.read_csv(RES + "single_removal_impact_metro.csv").head(k).iloc[::-1]
    lab = [f"{a}\n{b}" for a, b in zip(d["역사명"], d["노선명"])]
    fig, ax = plt.subplots(figsize=(7.6, 6.2))
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    y = np.arange(len(d))
    ax.barh(y, d["승객가중효율저하율_%"], height=0.62, color=CAT[0], zorder=2)
    for yi, v, cut in zip(y, d["승객가중효율저하율_%"], d["분리유발"]):
        ax.text(v + 0.06, yi, f"{v:.2f}%" + ("  ⚠ 단절" if cut else ""),
                va="center", fontsize=8, color=INK2)
    ax.set_yticks(y); ax.set_yticklabels(lab, fontsize=8, color=INK)
    ax.set_xlabel("운영 중단 시 승객가중 네트워크 효율 저하율 (%)", color=INK2)
    ax.set_title(f"수도권 핵심 역사 상위 {k}\n단일 역사 운영 중단의 승객 이동 영향도",
                 loc="left", color=INK)
    ax.set_xlim(0, d["승객가중효율저하율_%"].max() * 1.28)
    ax.grid(True, axis="x", alpha=0.6, lw=0.5); ax.set_axisbelow(True)
    ax.spines["left"].set_color("#b8b7b0")
    fig.tight_layout(); fig.savefig(FIG + "fig3_top_stations.png", facecolor=SURFACE)
    plt.close(fig); print("saved fig3")


# ------------------------------------------------------------------ fig 4
def fig_daejeon(G):
    d = pd.read_csv(RES + "single_removal_impact_daejeon.csv")
    imp = dict(zip(d["node_id"], d["승객가중효율저하율_%"]))
    nodes = [n for n in G.nodes if n in imp]
    xs = [G.nodes[n]["lon"] for n in nodes]; ys = [G.nodes[n]["lat"] for n in nodes]
    vals = np.array([imp[n] for n in nodes])

    fig, ax = plt.subplots(figsize=(8.4, 5.6))
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    order = sorted(nodes, key=lambda n: (G.nodes[n]["lon"]))
    for u, v in G.subgraph(nodes).edges():
        ax.plot([G.nodes[u]["lon"], G.nodes[v]["lon"]],
                [G.nodes[u]["lat"], G.nodes[v]["lat"]], color="#b8b7b0", lw=1.6, zorder=1)
    sc = ax.scatter(xs, ys, c=vals, cmap="Blues", vmin=0, s=190, zorder=3,
                    edgecolors=INK2, linewidths=0.7)
    for n, x, y in zip(nodes, xs, ys):
        ax.annotate(G.nodes[n]["역사명"], (x, y), xytext=(0, 11),
                    textcoords="offset points", ha="center", fontsize=7.2, color=INK)
        ax.annotate(f"{imp[n]:.1f}", (x, y), ha="center", va="center", fontsize=6.4,
                    color="white" if imp[n] > vals.max() * 0.55 else INK, zorder=4)
    cb = fig.colorbar(sc, ax=ax, pad=0.015, fraction=0.035)
    cb.set_label("운영 중단 시 승객가중 효율 저하율 (%)", color=INK2, fontsize=8.5)
    cb.outline.set_visible(False)
    ax.set_xlabel("경도 (°E)", color=INK2); ax.set_ylabel("위도 (°N)", color=INK2)
    ax.set_title("대전 도시철도 1호선 역사별 취약성\n중간부 역사 중단 시 네트워크 효율 24% 저하",
                 loc="left", color=INK)
    ax.grid(True, alpha=0.5, lw=0.5); ax.set_axisbelow(True)
    fig.tight_layout(); fig.savefig(FIG + "fig4_daejeon.png", facecolor=SURFACE)
    plt.close(fig); print("saved fig4")


if __name__ == "__main__":
    import os
    os.makedirs(FIG, exist_ok=True)
    G = load()
    fig_network(G)
    fig_resilience()
    fig_top_stations()
    fig_daejeon(G)
    print("완료 →", FIG)
