# -*- coding: utf-8 -*-
"""
역별 승하차 인원(실수요) 통합

KRIC 철도통계 '도시철도 역별 승강차실적(월)' 18개 운영기관 파일을 하나로 합치고,
그래프 노드(역×노선)에 매칭한다. 기존 '운행빈도 프록시'(공급 지표)를 실제 수요로 대체한다.

입력 : data/raw/승하차/2025년_*_역별 승강차실적.xls
출력 : data/processed/ridership.csv          역명·노선·연간 승하차
       data/processed/node_demand.csv        node_id별 일평균 승하차(그래프 결합용)
"""
import glob, os, re, unicodedata
import numpy as np
import pandas as pd

RAW, PROC = "data/raw/승하차/", "data/processed/"


def norm(s):
    if pd.isna(s):
        return ""
    s = unicodedata.normalize("NFC", str(s))
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"\s+", "", s)
    if s.endswith("역") and len(s) > 1:
        s = s[:-1]
    return s


def load_all():
    rows = []
    for f in sorted(glob.glob(RAW + "*.xls")):
        raw = pd.read_excel(f, header=None)
        # 헤더 2행(연도/기관/역명/호선/합계…) 뒤부터가 데이터
        hdr = raw.index[raw[0].astype(str).str.strip() == "연도"]
        start = (hdr[0] + 2) if len(hdr) else 3
        d = raw.iloc[start:, :6].copy()
        d.columns = ["연도", "기관", "역명", "호선", "승차인원", "하차인원"]
        d = d[d["역명"].notna()]
        d = d[~d["역명"].astype(str).str.replace(" ", "").isin(["합계", "합 계"])]
        for c in ("승차인원", "하차인원"):
            d[c] = pd.to_numeric(d[c], errors="coerce")
        d = d.dropna(subset=["승차인원", "하차인원"])
        d["출처파일"] = os.path.basename(f)
        if d["기관"].isna().all():
            d["기관"] = os.path.basename(f).split("_")[1]
        rows.append(d)
    # 코레일 광역철도(수도권전철 역별발착통과실적) — 월 단위, KRIC 광역철도여객수송
    kor = RAW + "2025_10_코레일광역_역별발착통과실적.csv"
    if os.path.exists(kor):
        k = pd.read_csv(kor)
        k = k.rename(columns={"노선": "호선", "승차인원": "승차인원", "강차인원": "하차인원"})
        k["연도"] = 2025
        k["기관"] = "한국철도공사"
        # 월(10월) 실적 → 연간 환산
        k["승차인원"] = pd.to_numeric(k["승차인원"], errors="coerce") * 12
        k["하차인원"] = pd.to_numeric(k["하차인원"], errors="coerce") * 12
        k["출처파일"] = os.path.basename(kor)
        rows.append(k[["연도", "기관", "역명", "호선", "승차인원", "하차인원", "출처파일"]])

    r = pd.concat(rows, ignore_index=True)
    r["기관"] = r["기관"].ffill()
    r["연간승하차"] = r["승차인원"] + r["하차인원"]
    r["일평균승하차"] = (r["연간승하차"] / 365).round(1)
    r["name_n"] = r["역명"].map(norm)
    return r


def attach_to_nodes(rid):
    """그래프 노드(역×노선)에 수요 결합.
    같은 역명이 여러 노선 노드로 분리돼 있으므로, 역명 단위 수요를 노드에 배분한다."""
    nodes = pd.read_csv(PROC + "nodes.csv")
    nodes["name_n"] = nodes["역사명"].map(norm)

    # 역명 기준 집계 (같은 역명이 여러 호선으로 나뉜 경우 합산)
    by_name = rid.groupby("name_n", as_index=False)["일평균승하차"].sum()
    m = nodes.merge(by_name, on="name_n", how="left")

    # 역명당 노드 수로 나눠 분배(환승역은 노선별 노드로 쪼개져 있음)
    cnt = m.groupby("name_n")["node_id"].transform("size")
    m["일평균승하차_배분"] = (m["일평균승하차"] / cnt).round(1)
    m["수요_매칭"] = m["일평균승하차"].notna().astype(int)
    out = m[["node_id", "역사명", "노선명", "운영기관명",
             "일평균승하차", "일평균승하차_배분", "수요_매칭"]]
    out.to_csv(PROC + "node_demand.csv", index=False, encoding="utf-8-sig")
    return out


def main():
    rid = load_all()
    rid.to_csv(PROC + "ridership.csv", index=False, encoding="utf-8-sig")
    print(f"승하차 원본 통합: {len(rid):,}행 · 기관 {rid['기관'].nunique()}개")
    print(f"  연간 총 승하차: {rid['연간승하차'].sum():,.0f}명")
    print(rid.groupby("기관")["연간승하차"].agg(["count", "sum"])
          .sort_values("sum", ascending=False).head(8).to_string())

    nd = attach_to_nodes(rid)
    cov = nd["수요_매칭"].mean() * 100
    print(f"\n그래프 노드 매칭: {nd['수요_매칭'].sum()}/{len(nd)} ({cov:.1f}%)")
    miss = nd[nd["수요_매칭"] == 0]
    print("미매칭 상위 운영기관:")
    print(miss["운영기관명"].value_counts().head(6).to_string())
    print("\n일평균 승하차 상위 10역:")
    print(nd.nlargest(10, "일평균승하차")[["역사명", "노선명", "일평균승하차"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
