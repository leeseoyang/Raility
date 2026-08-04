# -*- coding: utf-8 -*-
"""
보충자료 그림 (저장소 공개용, 영문)

KITS 6쪽 제한으로 본문에 넣지 못한 결과를 저장소에서 볼 수 있게 그린다.
본문은 이 그림들을 URL로 참조한다(투고규정 18조 4항 웹페이지 인용).

  FigS1_segments_en.png   수도권 취약 구간·병목 상위
  FigS2_sensitivity_en.png 환승 비용 민감도
  FigS3_scenarios_en.png  노선·운영기관 단위 동시 장애 시나리오
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RES, FIG = "results/", "figures/"
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({
    "figure.dpi": 300, "savefig.dpi": 300,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#b8b7b0", "axes.labelcolor": "#0b0b0b",
    "text.color": "#0b0b0b", "xtick.color": "#52514e", "ytick.color": "#52514e",
    "grid.color": "#e3e2dc", "grid.linewidth": .6,
    "font.size": 8.6, "axes.titlesize": 10, "legend.frameon": False,
})
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#ffffff"

# 역명 로마자 (보충자료에 등장하는 것만)
RO = {"강동": "Gangdong", "길동": "Gildong", "도봉산역": "Dobongsan",
      "망월사역": "Mangwolsa", "회룡역": "Hoeryong", "정릉": "Jeongneung",
      "성신여대입구": "Seongsin Women's Univ.", "북한산보국문": "Bukhansan Bogungmun",
      "솔샘": "Solsaem", "화계": "Hwagye", "가오리": "Gaori", "4.19민주묘지": "4·19 Cemetery",
      "신도림역": "Sindorim", "구로역": "Guro", "구일역": "Guil", "개봉역": "Gaebong",
      "영등포역": "Yeongdeungpo", "신길역": "Singil", "신길": "Singil",
      "여의도": "Yeouido", "온수역": "Onsu", "역곡역": "Yeokgok", "오류동역": "Oryu-dong",
      "소사역": "Sosa", "부천역": "Bucheon", "의정부역": "Uijeongbu",
      "회룡": "Hoeryong", "범골": "Beomgol", "경전철의정부": "Uijeongbu LRT",
      "의정부시청": "Uijeongbu City Hall", "발곡": "Balgok", "탑석": "Tapseok",
      "고덕": "Godeok", "명일": "Myeongil", "굽은다리(강동구민회관앞)": "Gubeundari",
      "경복궁(정부서울청사)": "Gyeongbokgung", "안국": "Anguk", "종각": "Jonggak",
      "시청": "City Hall", "충정로(경기대입구)": "Chungjeongno",
      "고속터미널": "Express Bus Terminal", "동작(현충원)": "Dongjak",
      "구반포": "Gu-Banpo", "신반포": "Sinbanpo",
      "이촌(국립중앙박물관)": "Ichon", "상일동": "Sangil-dong", "상계": "Sanggye",
      "노원": "Nowon", "미금": "Migeum", "동천": "Dongcheon", "수원역": "Suwon",
      "세류역": "Seryu", "금정역": "Geumjeong", "범계역": "Beomgye",
      "평촌역": "Pyeongchon", "인덕원역": "Indeogwon", "검암": "Geomam",
      "계양": "Gyeyang", "청라국제도시": "Cheongna Int'l City"}


LINE_RO = {"5호선": "L5", "1호선": "L1", "2호선": "L2", "3호선": "L3", "4호선": "L4",
           "7호선": "L7", "9호선": "L9", "경부선": "Gyeongbu", "경인선": "Gyeongin",
           "경원선": "Gyeongwon", "서해선": "Seohae", "우이신설선": "Ui-Sinseol",
           "의정부": "Uijeongbu LRT", "수도권  도시철도 9호선": "L9",
           "서울 도시철도 9호선": "L9"}


def ro(n):
    return RO.get(str(n), str(n))


def pair_label(r):
    """역명이 로마자로 겹치면(신길 5호선 / 신길역 경부선) 노선을 덧붙여 구분한다."""
    a, b = ro(r["역A"]), ro(r["역B"])
    if a == b:
        la = LINE_RO.get(str(r.get("노선A", "")), str(r.get("노선A", "")))
        lb = LINE_RO.get(str(r.get("노선B", "")), str(r.get("노선B", "")))
        return f"{a} ({la}) – {b} ({lb})"
    return f"{a} – {b}"


def figS1():
    e = pd.read_csv(RES + "edge_removal_impact_metro.csv")
    ev = pd.read_csv(RES + "edge_vulnerability_by_region.csv")
    ev = ev[ev["권역"] == "수도권"]

    # (a)는 제목대로 '단절을 유발하는' 구간만 담는다.
    top = ev[ev["단절유발"] == 1].nlargest(12, "수요가중저하율_%")
    bot = e[e["단절유발"] == 0].nlargest(12, "구간매개중심성")

    fig, axes = plt.subplots(1, 2, figsize=(9.8, 4.6))
    fig.patch.set_facecolor(SURFACE)

    ax = axes[0]
    lab = [pair_label(r) for _, r in top.iterrows()][::-1]
    val = top["수요가중저하율_%"].to_numpy()[::-1]
    sep = top["분리규모"].to_numpy()[::-1]
    ax.barh(range(len(val)), val, color=CAT[0], height=.62)
    ax.set_yticks(range(len(val))); ax.set_yticklabels(lab, fontsize=7.4)
    for i, (v, s) in enumerate(zip(val, sep)):
        ax.annotate(f"{v:.2f}%  ({s} stations isolated)", (v, i), xytext=(4, 0),
                    textcoords="offset points", va="center", fontsize=7,
                    color=INK2)
    ax.set_xlim(0, val.max() * 1.62)
    ax.set_xlabel("Demand-weighted efficiency loss (%)", color=INK2)
    ax.set_title("(a) Segments whose failure disconnects the network",
                 loc="left", color=INK)
    ax.grid(True, axis="x", alpha=.5); ax.set_axisbelow(True)

    ax = axes[1]
    lab = [pair_label(r) for _, r in bot.iterrows()][::-1]
    val = bot["구간매개중심성"].to_numpy()[::-1]
    ax.barh(range(len(val)), val, color=CAT[1], height=.62)
    ax.set_yticks(range(len(val))); ax.set_yticklabels(lab, fontsize=7.4)
    for i, v in enumerate(val):
        ax.annotate(f"{v:.3f}", (v, i), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=7, color=INK2)
    ax.set_xlim(0, val.max() * 1.28)
    ax.set_xlabel("Edge betweenness centrality", color=INK2)
    ax.set_title("(b) Bottlenecks that carry flow but cause no disconnection",
                 loc="left", color=INK)
    ax.grid(True, axis="x", alpha=.5); ax.set_axisbelow(True)

    fig.tight_layout()
    fig.savefig(FIG + "FigS1_segments_en.png", facecolor=SURFACE,
                bbox_inches="tight")
    plt.close(fig); print("saved FigS1_segments_en")


def figS2():
    d = pd.read_csv(RES + "sensitivity_transfer_cost.csv")
    base = d[d["환승비용_m"] == 200]
    d = d[d["환승비용_m"] != 200]

    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    fig.patch.set_facecolor(SURFACE)
    spec = [("매개중심성_rho_vs기준", "Betweenness rank correlation", CAT[0]),
            ("우선대상_영향도_rho", "Priority-target impact rank correlation", CAT[2]),
            ("상위20_자카드", "Top-20 set overlap (Jaccard)", CAT[1])]
    for col, lab, c in spec:
        ax.plot(d["환승비용_m"], d[col], marker="o", ms=4.5, lw=1.8, color=c,
                label=lab)
    ax.axvline(200, color="#8a8984", lw=.9, ls=":")
    ax.annotate("baseline 200 m", (200, .40), rotation=90, fontsize=7.2,
                color=INK2, ha="right", va="bottom")
    ax.set_xscale("log")
    ax.set_xticks([50, 100, 200, 400, 800, 1600])
    ax.set_xticklabels(["50", "100", "200", "400", "800", "1600"])
    ax.set_xlabel("Transfer cost assumption (m of equivalent track distance)",
                  color=INK2)
    ax.set_ylabel("Agreement with the baseline solution", color=INK2)
    ax.set_ylim(.35, 1.04)
    ax.legend(loc="lower left", fontsize=7.8, labelcolor=INK2)
    ax.grid(True, alpha=.5); ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIG + "FigS2_sensitivity_en.png", facecolor=SURFACE,
                bbox_inches="tight")
    plt.close(fig); print("saved FigS2_sensitivity_en")


def figS3():
    ln = pd.read_csv(RES + "kg_scenario_line.csv")
    op = pd.read_csv(RES + "kg_scenario_operator.csv")
    ln = ln.nlargest(8, "효율저하_per_역")
    op = op.nlargest(6, "효율저하_per_역")

    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    fig.patch.set_facecolor(SURFACE)
    ax.scatter(ln["제거역수"], ln["효율저하율_%"], s=52, c=CAT[0],
               edgecolors=SURFACE, linewidths=.5, label="Line-level shutdown", zorder=3)
    ax.scatter(op["제거역수"], op["효율저하율_%"], s=52, c=CAT[1], marker="s",
               edgecolors=SURFACE, linewidths=.5, label="Operator-level shutdown",
               zorder=3)
    for _, r in pd.concat([ln, op]).iterrows():
        ax.annotate(f"{r['효율저하_per_역']:.2f}",
                    (r["제거역수"], r["효율저하율_%"]), xytext=(0, 7),
                    textcoords="offset points", fontsize=6.8, color=INK2,
                    ha="center")
    ax.set_xlabel("Stations removed simultaneously", color=INK2)
    ax.set_ylabel("Regional efficiency loss (%)", color=INK2)
    ax.set_title("Labels: impact per removed station", loc="left", color=INK2,
                 fontsize=8.4)
    ax.legend(loc="lower right", fontsize=8, labelcolor=INK2)
    ax.grid(True, alpha=.5); ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(FIG + "FigS3_scenarios_en.png", facecolor=SURFACE,
                bbox_inches="tight")
    plt.close(fig); print("saved FigS3_scenarios_en")


if __name__ == "__main__":
    figS1(); figS2(); figS3()
