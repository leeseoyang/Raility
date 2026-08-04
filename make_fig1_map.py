# -*- coding: utf-8 -*-
"""
Fig. 1 — 권역별 구간 취약성 지도 (small multiples)

권역 간 비교가 이 연구의 축이므로, 단일 도시 지도가 아니라 5개 권역을 나란히 놓고
같은 색·굵기 척도로 그린다. 척도를 공유해야 "수도권은 최악 구간도 1.25%인데
대전은 28.5%"라는 대비가 그림 자체로 읽힌다.

인코딩
  · 선 굵기·색  = 해당 구간 단절 시 권역 전역 효율의 수요가중 저하율 (공통 척도 0~30%)
  · 점          = 역사 (환승 엣지는 회색 실선)
  · 패널 주석   = 순환밀도 α, 단절 유발 구간 비율, 최대 저하율

각 패널은 위도에 맞춰 종횡비를 보정하고 축척 막대를 둔다.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.cm import ScalarMappable
from matplotlib.lines import Line2D

RES, FIG, RAW = "results/", "figures/", "data/raw/"
BASEMAP = RAW + "basemap_municipalities.geojson"
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({"figure.dpi": 300, "savefig.dpi": 300, "font.size": 8.5,
                     "legend.frameon": False})
INK, INK2, INK3, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#ffffff"

# 크기(magnitude) 인코딩이므로 단일 색상 light→dark 램프를 쓴다.
RAMP = LinearSegmentedColormap.from_list(
    "vuln", ["#dbe7f6", "#9cc0ea", "#4f92dd", "#2a78d6", "#12457f"])
VMAX = 30.0

REGION_EN = {"수도권": "Seoul Metropolitan Area", "부산·김해": "Busan–Gimhae",
             "대구": "Daegu", "대전": "Daejeon", "광주": "Gwangju"}
ALPHA = {"수도권": 0.284, "부산·김해": 0.133, "대구": 0.088,
         "대전": 0.000, "광주": 0.000}


def load_basemap():
    """시군구 경계(단순화본). 없으면 배경 없이 그린다."""
    import json, os
    if not os.path.exists(BASEMAP):
        print("  (배경 경계 파일 없음 — 배경 생략)")
        return []
    fc = json.load(open(BASEMAP, encoding="utf-8"))
    polys = []
    for f in fc["features"]:
        g = f["geometry"]
        parts = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for part in parts:
            for ring_i, ring in enumerate(part):
                polys.append((np.asarray(ring, dtype=float), ring_i == 0))
    return polys


def draw_basemap(ax, polys):
    """행정 경계를 옅게 깔아 지도임을 드러내되, 취약성 선을 가리지 않게 한다."""
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    for ring, outer in polys:
        if ring[:, 0].max() < x0 or ring[:, 0].min() > x1: continue
        if ring[:, 1].max() < y0 or ring[:, 1].min() > y1: continue
        ax.fill(ring[:, 0], ring[:, 1],
                facecolor="#f4f3ee" if outer else SURFACE,
                edgecolor="#dedcd4", linewidth=.45, zorder=0)


def scalebar(ax, km, lat0):
    """위경도 축에 km 축척 막대를 그린다."""
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    dlon = km / (111.32 * np.cos(np.radians(lat0)))
    bx = x0 + (x1 - x0) * 0.06
    by = y0 + (y1 - y0) * 0.055
    ax.plot([bx, bx + dlon], [by, by], color=INK2, lw=1.6,
            solid_capstyle="butt", zorder=6)
    ax.annotate(f"{km} km", ((bx + bx + dlon) / 2, by), xytext=(0, 3),
                textcoords="offset points", ha="center", fontsize=6.8, color=INK2)


def draw_panel(ax, g, region, polys):
    ax.set_facecolor(SURFACE)
    v = g["수요가중저하율_%"].to_numpy(dtype=float)
    order = np.argsort(v)                       # 큰 값이 위로 오게
    gg = g.iloc[order]; vv = v[order]

    pts = pd.concat([gg[["lonA", "latA"]].rename(columns={"lonA": "x", "latA": "y"}),
                     gg[["lonB", "latB"]].rename(columns={"lonB": "x", "latB": "y"})],
                    ignore_index=True)
    pts["x"] = pd.to_numeric(pts["x"], errors="coerce")
    pts["y"] = pd.to_numeric(pts["y"], errors="coerce")
    pts = pts.dropna().drop_duplicates()

    lat0 = float(pts["y"].mean())
    mx = (pts["x"].max() - pts["x"].min()) * .06 + 1e-3
    my = (pts["y"].max() - pts["y"].min()) * .10 + 1e-3
    ax.set_xlim(pts["x"].min() - mx, pts["x"].max() + mx)
    ax.set_ylim(pts["y"].min() - my * 2.6, pts["y"].max() + my * .6)
    ax.set_aspect(1 / np.cos(np.radians(lat0)), adjustable="datalim")

    draw_basemap(ax, polys)

    # 공통 척도를 쓰면 수도권 구간은 색 농도가 0.04 이하라 사실상 보이지 않는다.
    # 위상 구조는 항상 읽혀야 하므로, 모든 구간을 중립 회색으로 먼저 깔고
    # 그 위에 취약성 색·굵기를 덧그린다.
    segs = []
    for (_, r), val in zip(gg.iterrows(), vv):
        try:
            xa, ya, xb, yb = (float(r["lonA"]), float(r["latA"]),
                              float(r["lonB"]), float(r["latB"]))
        except (TypeError, ValueError):
            continue
        segs.append((xa, ya, xb, yb, r["구간유형"], val))

    for xa, ya, xb, yb, typ, _ in segs:
        if typ == "환승":
            ax.plot([xa, xb], [ya, yb], color="#c3c2bb", lw=.5, zorder=1)
        else:
            ax.plot([xa, xb], [ya, yb], color="#8d8c86", lw=.85,
                    solid_capstyle="round", zorder=2)

    for xa, ya, xb, yb, typ, val in segs:
        if typ == "환승":
            continue
        t = min(max(val, 0) / VMAX, 1.0)
        if t < .02:                      # 회색 기저선만으로 충분
            continue
        ax.plot([xa, xb], [ya, yb], color=RAMP(max(t, .12)), lw=.85 + 5.0 * t,
                solid_capstyle="round", zorder=3 + t)

    ax.scatter(pts["x"], pts["y"], s=2.3, c="#5a5955", zorder=5, linewidths=0)

    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color("#d9d8d2"); sp.set_linewidth(.7)

    cut = g["단절유발"].mean() * 100
    ax.set_title(f"\u03b1 = {ALPHA[region]:.3f}  \u00b7  bridges {cut:.0f}%  \u00b7  "
                 f"worst segment {v.max():.1f}%",
                 loc="left", fontsize=8.2, color=INK2, pad=5)
    ax.annotate(REGION_EN[region], xy=(0, 1.0), xycoords="axes fraction",
                xytext=(0, 20), textcoords="offset points", fontsize=9.6,
                color=INK, fontweight="bold", va="bottom", ha="left")
    return lat0


def main():
    d = pd.read_csv(RES + "edge_vulnerability_by_region.csv")
    order = ["수도권", "부산·김해", "대구", "대전", "광주"]

    fig = plt.figure(figsize=(9.2, 6.6))
    fig.patch.set_facecolor(SURFACE)
    # 수도권·부산·대구는 세로로 긴 형상, 대전·광주는 가로로 납작해 행을 나눈다.
    gs = GridSpec(2, 3, figure=fig, height_ratios=[1, .40],
                  hspace=.52, wspace=.16,
                  left=.03, right=.985, top=.90, bottom=.11)

    axes = {r: fig.add_subplot(gs[0, i])
            for i, r in enumerate(["수도권", "부산·김해", "대구"])}
    axes["대전"] = fig.add_subplot(gs[1, 0])
    axes["광주"] = fig.add_subplot(gs[1, 1])
    cax = fig.add_subplot(gs[1, 2]); cax.set_axis_off()

    polys = load_basemap()
    for r in order:
        lat0 = draw_panel(axes[r], d[d["권역"] == r], r, polys)
        km = 10 if r in ("대전", "광주") else (20 if r in ("대구", "부산·김해") else 30)
        scalebar(axes[r], km, lat0)

    sm = ScalarMappable(norm=Normalize(0, VMAX), cmap=RAMP); sm.set_array([])
    cb = fig.colorbar(sm, ax=cax, orientation="horizontal", fraction=.20,
                      pad=.02, aspect=13, location="top")
    cb.set_label("Demand-weighted efficiency loss if the segment is severed (%)",
                 fontsize=7.6, color=INK2, labelpad=6)
    cb.ax.tick_params(labelsize=7, colors=INK2)
    cb.outline.set_visible(False)
    cax.legend(handles=[Line2D([], [], color="#8d8c86", lw=1.0, label="Track segment"),
                        Line2D([], [], color="#c3c2bb", lw=1.0, label="Transfer link"),
                        Line2D([], [], color="#5a5955", marker="o", lw=0,
                               markersize=3.4, label="Station")],
               loc="upper center", fontsize=7.6, labelcolor=INK2, ncol=3,
               bbox_to_anchor=(.5, .42), columnspacing=1.3, handlelength=1.4)

    fig.text(.03, .022,
             "All panels share one colour and line-width scale; panel extents and "
             "scale bars differ.  α: cyclomatic density (independent cycles ÷ nodes).  "
             "Base map: municipal boundaries, Statistics Korea (2018).",
             fontsize=7.2, color=INK2)
    fig.savefig(FIG + "Fig1_vulnmap_en.png", facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig); print("saved Fig1_vulnmap_en")


if __name__ == "__main__":
    main()
