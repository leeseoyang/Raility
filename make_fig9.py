# -*- coding: utf-8 -*-
"""
그림 9 — 수요 지표 3원 교차검증 산점도 (논문 표 3의 시각적 근거)

왼쪽: 서로 독립인 두 수요 측정(기관통계 vs 교통카드 실측) → 강하게 정렬
오른쪽: 공급 프록시(운행빈도) vs 실수요 → 사실상 무관

두 패널을 나란히 두면 "어긋나는 쪽은 프록시"라는 주장이 한눈에 읽힌다.
축은 두 패널 모두 log 스케일 단일 축이며, 참조선은 y=x(왼쪽)만 둔다.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy.stats import spearmanr

RES, FIG = "results/", "figures/"

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
BLUE, ORANGE = "#2a78d6", "#eb6834"
LABEL = "#52514e"


def main():
    d = pd.read_csv(RES + "demand_source_scatter.csv")
    # 상관계수는 표 3과 동일한 전체 유효 표본에서 계산하고,
    # 로그축 표시를 위해 0 이하 값만 도시에서 제외한다.
    both_all = d.dropna(subset=["KRIC승하차", "카드승하차"])
    freq_all = d.dropna(subset=["KRIC승하차"])
    r1, _ = spearmanr(both_all["KRIC승하차"], both_all["카드승하차"])
    r2, _ = spearmanr(freq_all["운행빈도"], freq_all["KRIC승하차"])
    n1, n2 = len(both_all), len(freq_all)

    both = both_all[(both_all["KRIC승하차"] > 0) & (both_all["카드승하차"] > 0)]
    freq = freq_all[(freq_all["KRIC승하차"] > 0) & (freq_all["운행빈도"] > 0)]

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.3))

    # ── 왼쪽: 독립적인 두 수요 측정
    ax = axes[0]
    ax.grid(True, which="both", alpha=.5, zorder=0)
    ax.scatter(both["KRIC승하차"], both["카드승하차"], s=11, c=BLUE,
               alpha=.55, linewidths=0, zorder=3)
    lo = min(both["KRIC승하차"].min(), both["카드승하차"].min())
    hi = max(both["KRIC승하차"].max(), both["카드승하차"].max())
    ax.plot([lo, hi], [lo, hi], color=LABEL, lw=1, ls="--", zorder=2)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("기관 통계 승하차 (명/일)")
    ax.set_ylabel("교통카드 실측 승하차 (명/일)")
    ax.set_title("(a) 독립적인 두 수요 측정", loc="left")
    ax.text(.04, .94, f"ρ = {r1:.3f}   n = {n1:,}", transform=ax.transAxes,
            fontsize=10, fontweight="bold", color=BLUE, va="top")
    ax.text(.04, .86, "점선 = y=x", transform=ax.transAxes, fontsize=8,
            color=LABEL, va="top")

    # ── 오른쪽: 공급 프록시 vs 수요
    ax = axes[1]
    ax.grid(True, which="both", alpha=.5, zorder=0)
    ax.scatter(freq["운행빈도"], freq["KRIC승하차"], s=11, c=ORANGE,
               alpha=.55, linewidths=0, zorder=3)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("운행빈도 프록시 (평일 운행횟수 합)")
    ax.set_ylabel("기관 통계 승하차 (명/일)")
    ax.set_title("(b) 공급 프록시 vs 수요", loc="left")
    ax.text(.04, .94, f"ρ = {r2:.3f}   n = {n2:,}", transform=ax.transAxes,
            fontsize=10, fontweight="bold", color=ORANGE, va="top")

    fig.suptitle("수요 지표 3원 교차검증 — 어긋나는 쪽은 수요 측정이 아니라 프록시다",
                 x=.012, ha="left", fontsize=12, fontweight="bold")
    fig.text(.012, .015, "ρ는 전체 유효 표본 기준(표 3과 동일). 로그축 표시를 위해 값이 0인 노드만 "
             "산점도에서 제외했다.", fontsize=8, color=LABEL)
    fig.tight_layout(rect=[0, .035, 1, .94])
    fig.savefig(FIG + "fig9_demand_sources.png", bbox_inches="tight")
    print(f"saved fig9  (a) rho={r1:.3f} n={n1} · (b) rho={r2:.3f} n={n2}")


if __name__ == "__main__":
    main()
