# -*- coding: utf-8 -*-
"""Notion 커버용 와이드 배너 — 5개 권역을 한 줄로 늘어놓는다."""
import json, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

RAMP = LinearSegmentedColormap.from_list("v", ["#dbe7f6","#9cc0ea","#4f92dd","#2a78d6","#12457f"])
VMAX = 30.0
d = pd.read_csv("results/edge_vulnerability_by_region.csv")
order = ["수도권","부산·김해","대구","대전","광주"]
EN = {"수도권":"Seoul Metropolitan","부산·김해":"Busan–Gimhae","대구":"Daegu","대전":"Daejeon","광주":"Gwangju"}

fig, axes = plt.subplots(1, 5, figsize=(15, 2.3), dpi=100)
fig.patch.set_facecolor("#f7f6f2")
for ax, r in zip(axes, order):
    g = d[d["권역"] == r]
    ax.set_facecolor("#f7f6f2")
    segs = []
    for _, row in g.iterrows():
        try: xa,ya,xb,yb = (float(row["lonA"]),float(row["latA"]),float(row["lonB"]),float(row["latB"]))
        except (TypeError, ValueError): continue
        segs.append((xa,ya,xb,yb,row["구간유형"],float(row["수요가중저하율_%"])))
    xs = [s[0] for s in segs]+[s[2] for s in segs]; ys = [s[1] for s in segs]+[s[3] for s in segs]
    lat0 = float(np.mean(ys))
    for xa,ya,xb,yb,typ,_ in segs:
        ax.plot([xa,xb],[ya,yb], color="#b9b8b1" if typ=="환승" else "#8d8c86", lw=.45 if typ=="환승" else .8, zorder=1)
    for xa,ya,xb,yb,typ,val in sorted(segs, key=lambda s: s[5]):
        if typ == "환승": continue
        t = min(max(val,0)/VMAX, 1.0)
        if t < .02: continue
        ax.plot([xa,xb],[ya,yb], color=RAMP(max(t,.12)), lw=.8+4.4*t, solid_capstyle="round", zorder=3+t)
    mx = (max(xs)-min(xs))*.08+1e-3; my = (max(ys)-min(ys))*.10+1e-3
    ax.set_xlim(min(xs)-mx, max(xs)+mx); ax.set_ylim(min(ys)-my, max(ys)+my)
    ax.set_aspect(1/np.cos(np.radians(lat0)), adjustable="datalim")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.annotate(EN[r], xy=(0.5, 0.0), xycoords="axes fraction", xytext=(0, -11),
                textcoords="offset points", ha="center", va="top",
                fontsize=8.6, color="#52514e", fontfamily="DejaVu Sans")
fig.subplots_adjust(left=.005, right=.995, top=.97, bottom=.13, wspace=.04)
fig.savefig("figures/banner_notion.png", facecolor="#f7f6f2")
print("saved")
