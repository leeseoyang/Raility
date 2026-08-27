# -*- coding: utf-8 -*-
"""
서울시 실측 OD(교통카드) ↔ 도시철도 그래프 노드 연결 산출물 생성.

README '한계' 항목의 "실제 OD가 아닌 운행빈도 프록시 사용"을 해소하기 위한
독립 모듈. 기존 파이프라인(build_graph.py / analyze.py)은 수정하지 않으며,
산출물을 data/od/processed/ 에 따로 만든다. analyze.py 연계 방안은
docs/README_OD분석.md 참조.

실행:
    python od_analysis.py

입력
- data/processed/nodes.csv               : 그래프 노드 (node_id = "노선번호|역번호")
- data/od/seoul_역사마스터.csv            : 서울시 역사_ID(4자리) → 역사명·호선·좌표
- data/od/kscc_dx_ra_od_YYYYMMDD.zip     : 7일치 시간대별 OD (2026-07-22~28,
                                           data/od/README.md 안내대로 별도 다운로드)
- data/od/busan_시간대별_승하차인원.csv / daegu_… / daejeon_… : 지방 승하차

출력 (data/od/processed/)
- od_station_mapping.csv   : 역사_ID ↔ node_id 매핑 (매칭방법·좌표거리)
- od_station_unmatched.csv : 매칭 실패/제외 역사
- od_daily_avg.csv         : 노드쌍별 일평균 통행량 (7일/주중5일/주말2일) †
- od_peak.csv              : 주중 첨두(07~09시)·비첨두(11~13시) 일평균 통행량 †
- node_weights.csv         : 노드별 일평균 승차·하차 (weight_source 표시)

† 수십 MB — .gitignore 처리, 이 스크립트 실행으로 재생성.

정의
- 주중 = 07/22(수),23(목),24(금),27(월),28(화) / 주말 = 07/25(토),26(일)
- 첨두 = 승객_수_07시+08시 (07:00~09:00 승차 기준), 비첨두 = 11시+12시
- 지하철 역사 = OD ID 문자열 길이 4 (9자리 = 버스 정류장)
"""
import glob
import math
import os
import re
import unicodedata
import zipfile

import numpy as np
import pandas as pd

NODES_CSV = "data/processed/nodes.csv"

# OD 자료는 저장소에서 'OD+data/data/od' 아래에 있고, 작업 사본에 따라 'data/od' 인
# 경우도 있다. 있는 쪽을 쓴다 — 경로를 고정하면 한쪽에서 반드시 깨진다.
OD_DIR = next((p for p in ("data/od", "OD+data/data/od") if os.path.isdir(p)),
              "data/od")
OUT = os.path.join(OD_DIR, "processed")

DAYS = ["20260722", "20260723", "20260724", "20260725", "20260726",
        "20260727", "20260728"]
WEEKEND = {"20260725", "20260726"}
PEAK_COLS = ["승객_수_07시", "승객_수_08시"]        # 07:00~09:00
OFFPEAK_COLS = ["승객_수_11시", "승객_수_12시"]     # 11:00~13:00
COORD_MAX_M = 500.0  # name_coord / coord_only 허용 좌표거리

# ---------------------------------------------------------------------------
# 역명·노선명 정규화
# ---------------------------------------------------------------------------
# 역명 별칭 (정규화 후 적용). 서울시 마스터와 공단 역사정보의 개명·병기 차이 흡수.
ALIASES = {
    "신길온천": "능길",            # 2025년 개명
    "인천국제공항": "인천공항1터미널",  # 동일 역사(교통센터) 환승
    "지제": "평택지제",            # 2020년 개명
    "이수": "총신대입구",          # 7호선 이수 = 4호선 총신대입구(이수) 병기
}

_PAREN_RE = re.compile(r"[(（\[].*?[)）\]]")


def norm_name(raw):
    """괄호 병기 제거, 공백/특수문자 제거, 접미사 '역' 제거, 별칭 통일."""
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None
    s = unicodedata.normalize("NFC", str(raw)).strip()
    s = _PAREN_RE.sub("", s)
    s = re.sub(r"[\s·ㆍ‧・．\.\-]", "", s)
    if len(s) > 2 and s.endswith("역"):
        s = s[:-1]
    return ALIASES.get(s, s)


def canon_line(raw):
    """이 저장소 nodes.csv 의 노선명 → 정규 노선키.

    예: '수도권  도시철도 9호선'/'서울 도시철도 9호선' → '9호선',
        '부산 경량도시철도 4호선' → '부산4호선', '인천지하철 1호선' → '인천1호선',
        '수도권 경량도시철도 신림선' → '신림선', '김포도시철도' → '김포'.
    """
    s = re.sub(r"\s", "", unicodedata.normalize("NFC", str(raw)))
    for tok in ("경량도시철도", "광역철도", "도시철도", "지하철", "수도권"):
        s = s.replace(tok, "")
    if s.startswith("서울") and len(s) > 2 and s[2].isdigit():
        s = s[2:]
    return s


def region_of(canon):
    """정규 노선키 → 권역. 그래프에 region 컬럼이 없어 노선명으로 판정."""
    if canon.startswith("부산") or "김해" in canon or canon == "동해선":
        return "부산"
    if canon.startswith("대구") or canon == "대경선":
        return "대구"
    if canon.startswith("대전"):
        return "대전"
    if canon.startswith("광주"):
        return "광주"
    return "수도권"


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# 서울시 역사마스터 '호선' → 이 저장소 정규 노선키 후보.
# 이 저장소는 코레일 구간을 운영 노선(경부선·경인선·경원선·안산과천선 등)으로
# 나눠 두므로 마스터 호선을 해당 후보들로 넓게 매핑하고 좌표로 해소한다.
# 빈 리스트 = 그래프에 없는 노선(매칭 제외, 사유 기록).
LINE_MAP = {
    "1호선": ["1호선", "경부선", "경인선", "경원선"],
    "경부선": ["경부선", "1호선", "장항선"],
    "경인선": ["경인선", "1호선"],
    "장항선": ["장항선", "경부선"],
    "경원선": ["경원선", "경의중앙선", "경춘선", "1호선"],
    "2호선": ["2호선"],
    "3호선": ["3호선", "일산선"], "일산선": ["일산선", "3호선"],
    "4호선": ["4호선", "안산과천선", "진접선"],
    "과천선": ["안산과천선", "4호선"], "안산선": ["안산과천선"],
    "진접선": ["진접선", "4호선"],
    "5호선": ["5호선"], "6호선": ["6호선"],
    "7호선": ["7호선"], "7호선(인천)": ["7호선"],
    "8호선": ["8호선"], "별내선": ["8호선"],
    "9호선": ["9호선"], "9호선(연장)": ["9호선"],
    "경강선": ["경강선"],
    "경의중앙선": ["경의중앙선"], "중앙선": ["경의중앙선"],
    "경춘선": ["경춘선", "경의중앙선"],
    "공항철도1호선": ["인천국제공항선"],
    "김포골드라인": ["김포"],
    "분당선": ["분당선", "수인선"], "수인선": ["수인선", "분당선"],
    "서해선": ["서해선"],
    "신림선": ["신림선"],
    "신분당선": ["신분당선"], "신분당선(연장)": ["신분당선"],
    "신분당선(연장2)": ["신분당선"],
    "에버라인선": ["에버라인"],
    "우이신설선": ["우이신설선"],
    "의정부선": ["의정부"],
    "인천1호선": ["인천1호선"], "인천2호선": ["인천2호선"],
    "수도권 광역급행철도": [],  # GTX-A: 그래프(공단 역사정보 2026-06 기준) 미포함
}


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# 0. 노드 로드
# ---------------------------------------------------------------------------
def load_nodes(path=NODES_CSV):
    """nodes.csv → DataFrame(+ canon 노선키·권역·정규화 역명·좌표 float)."""
    nodes = pd.read_csv(path, encoding="utf-8-sig",
                        dtype={"역번호": str, "노선번호": str})
    nodes["canon"] = nodes["노선명"].map(canon_line)
    nodes["region"] = nodes["canon"].map(region_of)
    nodes["name_norm"] = nodes["역사명"].map(norm_name)
    nodes["_lat"] = pd.to_numeric(nodes["역위도"], errors="coerce")
    nodes["_lon"] = pd.to_numeric(nodes["역경도"], errors="coerce")
    return nodes


# ---------------------------------------------------------------------------
# 1. 매핑 테이블 — 서울시 역사_ID ↔ node_id
# ---------------------------------------------------------------------------
def build_mapping(nodes):
    master = pd.read_csv(os.path.join(OD_DIR, "seoul_역사마스터.csv"),
                         encoding="cp949", dtype={"역사_ID": str})
    cap = nodes[nodes.region == "수도권"].copy()
    by_name = {k: g for k, g in cap.groupby("name_norm")}

    rows, un = [], []
    for _, r in master.iterrows():
        sid, sname, sline = r["역사_ID"], str(r["역사명"]), str(r["호선"])
        lat, lon = float(r["위도"]), float(r["경도"])
        nm = norm_name(sname)
        line_cands = LINE_MAP.get(sline)
        if line_cands == []:
            un.append(dict(역사_ID=sid, 서울시_역명=sname, 서울시_호선=sline,
                           사유="그래프 미포함 노선(GTX-A)"))
            continue

        def nearest(df):
            d = df.apply(lambda x: haversine_km(lat, lon, x._lat, x._lon) * 1000
                         if pd.notna(x._lat) else np.inf, axis=1)
            i = d.idxmin()
            return df.loc[i], float(d.loc[i])

        cand = by_name.get(nm)
        method, node_id, dist_m = None, None, None
        if cand is not None:
            if line_cands:
                lc = cand[cand.canon.isin(line_cands)]
                if len(lc):
                    row, dist_m = nearest(lc)
                    method, node_id = "name_line", row.node_id
            if method is None:  # 역명은 일치하나 호선 매핑 실패 → 좌표로 확인
                row, dist_m = nearest(cand)
                if dist_m <= COORD_MAX_M:
                    method, node_id = "name_coord", row.node_id
        if method is None:  # 역명 불일치 → 좌표 최근접
            row, dist_m = nearest(cap)
            if dist_m <= COORD_MAX_M:
                method, node_id = "coord_only", row.node_id
        if method is None:
            un.append(dict(역사_ID=sid, 서울시_역명=sname, 서울시_호선=sline,
                           사유=f"역명 불일치·최근접 노드 {dist_m:.0f}m > {COORD_MAX_M:.0f}m"))
            continue
        rows.append(dict(역사_ID=sid, 서울시_역명=sname, 서울시_호선=sline,
                         node_id=node_id, 매칭방법=method,
                         좌표거리_m=round(dist_m, 1)))

    mp = pd.DataFrame(rows)
    unm = pd.DataFrame(un, columns=["역사_ID", "서울시_역명", "서울시_호선", "사유"])
    os.makedirs(OUT, exist_ok=True)
    mp.to_csv(os.path.join(OUT, "od_station_mapping.csv"),
              index=False, encoding="utf-8-sig")
    unm.to_csv(os.path.join(OUT, "od_station_unmatched.csv"),
               index=False, encoding="utf-8-sig")
    log(f"[mapping] master {len(master)}행 -> 매칭 {len(mp)} / 미매칭 {len(unm)} "
        f"(매칭률 {len(mp) / len(master) * 100:.1f}%)")
    return mp, unm, master


# ---------------------------------------------------------------------------
# 2. OD zip 7일치 집계
# ---------------------------------------------------------------------------
def od_zips_available():
    return sorted(glob.glob(os.path.join(OD_DIR, "kscc_dx_ra_od_*.zip")))


def aggregate_od():
    """일별 zip → 지하철(4자리 ID)만 (O,D) 집계. 반환: 일별 집계, 원본 합계."""
    daily, raw_totals = [], {}
    usecols = ["승차_정류장/역사_ID", "하차_정류장/역사_ID", "승객_수"] \
        + PEAK_COLS + OFFPEAK_COLS
    for day in DAYS:
        path = os.path.join(OD_DIR, f"kscc_dx_ra_od_{day}.zip")
        parts = []
        with zipfile.ZipFile(path) as z, z.open(z.namelist()[0]) as f:
            for chunk in pd.read_csv(
                    f, encoding="cp949", usecols=usecols, chunksize=500_000,
                    dtype={"승차_정류장/역사_ID": str, "하차_정류장/역사_ID": str}):
                chunk = chunk.rename(columns={"승차_정류장/역사_ID": "oid",
                                              "하차_정류장/역사_ID": "did"})
                chunk["oid"] = chunk.oid.str.strip()
                chunk["did"] = chunk.did.str.strip()
                sub = chunk[(chunk.oid.str.len() == 4)
                            & (chunk.did.str.len() == 4)].copy()
                if not len(sub):
                    continue
                for c in ["승객_수"] + PEAK_COLS + OFFPEAK_COLS:
                    sub[c] = pd.to_numeric(sub[c], errors="coerce").fillna(0)
                sub["peak"] = sub[PEAK_COLS].sum(axis=1)
                sub["offpeak"] = sub[OFFPEAK_COLS].sum(axis=1)
                parts.append(sub.groupby(["oid", "did"], as_index=False)
                             .agg(total=("승객_수", "sum"), peak=("peak", "sum"),
                                  offpeak=("offpeak", "sum")))
        g = (pd.concat(parts).groupby(["oid", "did"], as_index=False).sum()
             if parts else pd.DataFrame(columns=["oid", "did", "total",
                                                 "peak", "offpeak"]))
        g["day"] = day
        daily.append(g)
        raw_totals[day] = float(g.total.sum())
        log(f"[od] {day}: 지하철 OD쌍 {len(g):,} / 통행 {raw_totals[day]:,.0f}"
            f" ({'주말' if day in WEEKEND else '주중'})")
    return pd.concat(daily, ignore_index=True), raw_totals


def build_od_outputs(od, mapping):
    """OD 집계 → od_daily_avg.csv, od_peak.csv (data/od/processed/)."""
    id2node = dict(zip(mapping.역사_ID, mapping.node_id))
    od = od.copy()
    od["node_o"] = od.oid.map(id2node)
    od["node_d"] = od.did.map(id2node)
    raw_total = od.total.sum()
    mapped = od.dropna(subset=["node_o", "node_d"])
    kept_total = mapped.total.sum()
    log(f"[od] 총 통행 {raw_total:,.0f} -> 매핑 후 {kept_total:,.0f} "
        f"(보존율 {kept_total / raw_total * 100:.2f}%)")

    ids = pd.unique(pd.concat([od.oid, od.did]))
    lost_ids = sorted(set(ids) - set(id2node))
    lost_flow = od.loc[od.node_o.isna() | od.node_d.isna(), "total"].sum()

    mapped = mapped.copy()
    mapped["is_weekend"] = mapped.day.isin(WEEKEND)

    # 동일 node 쌍으로 합침 (복수 역사_ID → 동일 노드 가능) 후 일평균
    def avg(df, ndays, cols=("total",)):
        g = df.groupby(["node_o", "node_d"], as_index=False)[list(cols)].sum()
        for c in cols:
            g[c] = (g[c] / ndays).round(2)
        return g

    all_avg = avg(mapped, 7).rename(columns={"total": "trips_avg_daily"})
    wd = avg(mapped[~mapped.is_weekend], 5).rename(
        columns={"total": "trips_avg_weekday"})
    we = avg(mapped[mapped.is_weekend], 2).rename(
        columns={"total": "trips_avg_weekend"})
    daily_avg = (all_avg.merge(wd, on=["node_o", "node_d"], how="left")
                 .merge(we, on=["node_o", "node_d"], how="left")
                 .fillna({"trips_avg_weekday": 0, "trips_avg_weekend": 0}))
    daily_avg = daily_avg.sort_values("trips_avg_daily",
                                      ascending=False, ignore_index=True)
    daily_avg.to_csv(os.path.join(OUT, "od_daily_avg.csv"),
                     index=False, encoding="utf-8-sig")
    log(f"[out] od_daily_avg.csv: {len(daily_avg):,} 노드쌍")

    pk = avg(mapped[~mapped.is_weekend], 5, cols=("peak", "offpeak")).rename(
        columns={"peak": "trips_peak_am_0709", "offpeak": "trips_offpeak_1113"})
    pk = pk[(pk.trips_peak_am_0709 > 0) | (pk.trips_offpeak_1113 > 0)]
    pk = pk.sort_values("trips_peak_am_0709", ascending=False, ignore_index=True)
    pk.to_csv(os.path.join(OUT, "od_peak.csv"), index=False, encoding="utf-8-sig")
    log(f"[out] od_peak.csv: {len(pk):,} 노드쌍 (주중 5일 평균)")

    stats = dict(raw_total=float(raw_total), kept_total=float(kept_total),
                 lost_flow=float(lost_flow), lost_ids=lost_ids,
                 n_pairs=len(daily_avg))
    return daily_avg, pk, stats


# ---------------------------------------------------------------------------
# 3. 노드 가중치 (서울 OD의 O합/D합 + 부산·대구·대전 승하차)
# ---------------------------------------------------------------------------
def regional_weights(nodes):
    """부산/대구/대전 승하차 파일 → {node_id: (승차, 하차)} 일평균."""
    out = {}

    # 대구 원본 역명 보정: 개칭(2021 대공원→수성알파시티, 2022 어린이회관→어린이세상)
    ALIAS = {"대공원": "수성알파시티", "어린이회관": "어린이세상"}

    def put(canon, name, board, alight):
        nm = norm_name(name)
        nm = ALIAS.get(nm, nm)
        # 대구 환승역은 호선번호 접미 숫자(반월당1 등)가 붙음 → 제거 후보도 시도
        cand = [nm] + ([nm[:-1]] if nm[-1:].isdigit() else [])
        for c in cand:
            hit = nodes[(nodes.canon == canon) & (nodes.name_norm == c)]
            if len(hit):
                out[hit.iloc[0].node_id] = (round(board, 1), round(alight, 1))
                return True
        return False

    miss = []
    # 부산 (2026-01~06, 합계 컬럼 = 일별 총량, 역번호 백단위 = 호선)
    b = pd.read_csv(os.path.join(OD_DIR, "busan_시간대별_승하차인원.csv"),
                    encoding="cp949")
    b["canon"] = "부산" + (b.역번호 // 100).clip(lower=1).astype(str) + "호선"
    for (canon, name), g in b.groupby(["canon", "역명"]):
        board = g[g.구분 == "승차"].groupby("년월일")["합계"].sum().mean()
        alight = g[g.구분 == "하차"].groupby("년월일")["합계"].sum().mean()
        if not put(canon, name, board or 0, alight or 0):
            miss.append(("부산", canon, name))
    # 대구 (1~6월, 시간대 컬럼 합, 역번호 천단위 = 호선)
    d = pd.read_csv(os.path.join(OD_DIR, "daegu_역별일별시간별_승하차인원.csv"),
                    encoding="cp949")
    hour_cols = [c for c in d.columns if "시" in c and "-" in c]
    d["tot"] = d[hour_cols].sum(axis=1)
    d["canon"] = "대구" + (d.역번호 // 1000).astype(str) + "호선"
    for (canon, name), g in d.groupby(["canon", "역명"]):
        board = g[g.승하차 == "승차"].groupby(["월", "일"])["tot"].sum().mean()
        alight = g[g.승하차 == "하차"].groupby(["월", "일"])["tot"].sum().mean()
        if not put(canon, name, board or 0, alight or 0):
            miss.append(("대구", canon, name))
    # 대전 (2026-01~06)
    j = pd.read_csv(os.path.join(OD_DIR, "daejeon_시간대별_승하차인원.csv"),
                    encoding="cp949")
    hour_cols = [c for c in j.columns if "-" in c and "시" in c]
    j["tot"] = j[hour_cols].sum(axis=1)
    for name, g in j.groupby("역명"):
        board = g[g.구분 == "승차"].groupby("날짜")["tot"].sum().mean()
        alight = g[g.구분 == "하차"].groupby("날짜")["tot"].sum().mean()
        if not put("대전1호선", name, board or 0, alight or 0):
            miss.append(("대전", "대전1호선", name))
    if miss:
        log(f"[weights] 지방 승하차 역명 미매칭 {len(miss)}건: {miss}")
    return out


def build_node_weights(nodes, daily_avg, mapping):
    """노드별 일평균 승차·하차 → node_weights.csv. daily_avg=None 허용(zip 없음)."""
    if daily_avg is not None:
        boarding = daily_avg.groupby("node_o")["trips_avg_daily"].sum()
        alighting = daily_avg.groupby("node_d")["trips_avg_daily"].sum()
        seoul_nodes = set(mapping.node_id)
    else:
        boarding = alighting = pd.Series(dtype=float)
        seoul_nodes = set()
    reg = regional_weights(nodes)

    rows = []
    for _, n in nodes.iterrows():
        nid = n.node_id
        base = dict(node_id=nid, 역사명=n.역사명, 노선명=n.노선명, region=n.region)
        if nid in seoul_nodes:
            rows.append(dict(base,
                             boarding_daily_avg=round(float(boarding.get(nid, 0)), 2),
                             alighting_daily_avg=round(float(alighting.get(nid, 0)), 2),
                             weight_source="seoul_od"))
        elif nid in reg:
            bo, al = reg[nid]
            rows.append(dict(base, boarding_daily_avg=bo,
                             alighting_daily_avg=al,
                             weight_source="boarding_data"))
        else:
            rows.append(dict(base, boarding_daily_avg=None,
                             alighting_daily_avg=None, weight_source="none"))
    w = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    w.to_csv(os.path.join(OUT, "node_weights.csv"),
             index=False, encoding="utf-8-sig")
    cov = w.weight_source.value_counts().to_dict()
    log(f"[out] node_weights.csv: {len(w)} 노드, 커버리지 {cov}")
    return w


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------
def main():
    nodes = load_nodes()
    mapping, unmatched, master = build_mapping(nodes)
    if len(od_zips_available()) == len(DAYS):
        od, raw_totals = aggregate_od()
        daily_avg, pk, stats = build_od_outputs(od, mapping)
    else:
        log("[od] kscc_dx_ra_od_*.zip 미배치 — OD 집계 건너뜀 "
            "(data/od/README.md 안내대로 다운로드 후 재실행)")
        daily_avg = pk = stats = None
    weights = build_node_weights(nodes, daily_avg, mapping)
    rate = len(mapping) / len(master) * 100
    log(f"[done] 매칭률 {rate:.1f}%"
        + (f" / 통행량 보존율 {stats['kept_total'] / stats['raw_total'] * 100:.2f}%"
           if stats else ""))
    return dict(nodes=nodes, mapping=mapping, unmatched=unmatched,
                master=master, daily_avg=daily_avg, peak=pk, stats=stats,
                weights=weights)


if __name__ == "__main__":
    main()
