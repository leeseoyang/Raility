# -*- coding: utf-8 -*-
"""
지도 배경 경계 생성 — 시군구 경계를 권역 표시 범위로 잘라 단순화

원본(통계청 2018년 시군구 경계, 18MB)을 그대로 쓰면 저장소가 무거워지고 작도도
느리다. 각 권역의 네트워크 범위에 여유를 두고 잘라낸 뒤 폴리곤을 단순화하여
가벼운 GeoJSON 하나로 만든다.

원본 출처 : https://github.com/southkorea/southkorea-maps
            (kostat/2018/json/skorea-municipalities-2018-geo.json, 통계청 2018)
출력      : data/raw/basemap_municipalities.geojson
"""
import json
import os
import numpy as np
import pandas as pd
from shapely.geometry import shape, mapping, box
from shapely.ops import unary_union

SRC = "/tmp/skmaps/kostat/2018/json/skorea-municipalities-2018-geo.json"
OUT = "data/raw/basemap_municipalities.geojson"
RES = "results/"

TOL = 0.0012        # 약 100 m. 6쪽 인쇄 크기에서 구분되지 않는 굴곡은 버린다.
PAD = 0.40          # 권역 범위에 둘 여유(도). 종횡비 보정으로 축이 넓어지는 것까지 감안한다.


def region_boxes():
    d = pd.read_csv(RES + "edge_vulnerability_by_region.csv")
    out = {}
    for r, g in d.groupby("권역", sort=False):
        xs = pd.to_numeric(pd.concat([g["lonA"], g["lonB"]]), errors="coerce").dropna()
        ys = pd.to_numeric(pd.concat([g["latA"], g["latB"]]), errors="coerce").dropna()
        out[r] = box(xs.min() - PAD, ys.min() - PAD, xs.max() + PAD, ys.max() + PAD)
    return out


def main():
    if not os.path.exists(SRC):
        raise SystemExit(f"원본 경계 파일이 없습니다: {SRC}")
    src = json.load(open(SRC, encoding="utf-8"))
    boxes = region_boxes()
    envelope = unary_union(list(boxes.values()))

    feats, kept = [], 0
    for f in src["features"]:
        geom = shape(f["geometry"])
        if not geom.intersects(envelope):
            continue
        g = geom.intersection(envelope)
        if g.is_empty:
            continue
        g = g.simplify(TOL, preserve_topology=True)
        if g.is_empty or g.area <= 0:
            continue
        kept += 1
        feats.append({"type": "Feature",
                      "properties": {"name": f["properties"].get("name", ""),
                                     "name_eng": f["properties"].get("name_eng", "")},
                      "geometry": mapping(g)})

    fc = {"type": "FeatureCollection", "features": feats}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(fc, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    mb = os.path.getsize(OUT) / 1e6
    print(f"시군구 {len(src['features'])}개 중 {kept}개 유지 · "
          f"단순화 허용오차 {TOL}° (~{TOL*111000:.0f} m) · 출력 {mb:.1f} MB")
    for r, b in boxes.items():
        print(f"  {r:<8} bbox {b.bounds[0]:.2f},{b.bounds[1]:.2f} – "
              f"{b.bounds[2]:.2f},{b.bounds[3]:.2f}")


if __name__ == "__main__":
    main()
