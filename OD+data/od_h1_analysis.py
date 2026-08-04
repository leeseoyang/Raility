# -*- coding: utf-8 -*-
"""
서울시 실측 OD 2026년 상반기(1/1~6/30) 집계 — od_analysis.py 의 기간 정합 확장판.

od_analysis.py(2026-07-22~28 7일치)는 계절·방학·휴가철 편차를 담지 못하고,
지방 승하차 데이터(부산·대구·대전 2026-01~06)와 기간이 어긋난다. 이 모듈은
**지방 데이터와 완전히 중첩되는 2026년 상반기 전체(181일)** 를 같은 방식으로
집계해 기간 정합 산출물을 새 파일(*_2026H1.csv)로 만든다. od_analysis.py 와
그 산출물(od_daily_avg.csv 등)은 건드리지 않는다.

실행:
    python od_h1_analysis.py        # 캐시 있으면 2~3분, 없으면 15~20분

입력
- data/processed/nodes.csv                    : 그래프 노드 (od_analysis.load_nodes)
- data/od/processed/od_station_mapping.csv    : 역사_ID ↔ node_id (od_analysis 산출물 재사용)
- data/od/kscc_dx_ra_od_2026MM.zip (6개)      : 서울 역간 OD 월별 아카이브 (내부에 일별 CSV,
                                                data/od/README.md 안내 참조)
- data/od/busan_시간대별_승하차인원.csv 등     : 부산·대구·대전 (od_analysis 와 동일)
- data/od/gwangju_역일시간대별_승하차량_202601-202606.csv : 광주 (신규, 2026-01~06)
- data/od/incheon_역별일별시간대별_이용인원_202501-202604.csv : 인천 (신규, 2026-01~04만 사용)

출력 (data/od/processed/)
- od_daily_avg_2026H1.csv   : 노드쌍별 상반기 일평균 통행량 (주중/주말 구분) †
- od_peak_2026H1.csv        : 주중 첨두(07~09시)·비첨두(11~13시) 일평균 †
- node_weights_2026H1.csv   : 노드별 일평균 승차·하차 (weight_source 에 기간 정합 상태 표시)

† 수십 MB — .gitignore 처리, 이 스크립트 실행으로 재생성.
중간 캐시 data/od/h1_cache/od_YYYYMMDD.csv.gz (역사_ID 수준 일별 집계, .gitignore 처리)
— 재실행 시 월별 zip 재파싱을 생략한다.

기간 정합성
- 서울/수도권 OD·부산·대구·대전·광주: 2026-01-01~06-30 **완전 중첩**
- 인천 1·2호선 승하차: 원본이 2026-04-30까지라 2026-01~04만 사용(**부분 중첩**,
  weight_source 에 명시). 7호선 인천 구간은 그래프 노선이 '7호선'이라 서울 OD 커버.
- 서울 OD 원천 결측 2일(2026-01-09, 05-16: 포털 zip 에 헤더만 있는 CSV) 은
  일평균 분모에서 제외 → 유효 179일.

정의 (od_analysis.py 와 동일)
- 주중 = 월~금(공휴일 미제외), 주말 = 토·일
- 첨두 = 승객_수_07시+08시, 비첨두 = 11시+12시
- 지하철 역사 = OD ID 문자열 길이 4
"""
import os
import re
import time
import zipfile

import pandas as pd

import od_analysis as oda
from od_analysis import log, norm_name

OD_DIR = oda.OD_DIR
OUT = oda.OUT
CACHE = os.path.join(OD_DIR, "h1_cache")

H1_START, H1_END = "2026-01-01", "2026-06-30"
MONTHS = ["202601", "202602", "202603", "202604", "202605", "202606"]
PEAK_COLS = oda.PEAK_COLS          # 07~09시
OFFPEAK_COLS = oda.OFFPEAK_COLS    # 11~13시

_cal = pd.date_range(H1_START, H1_END)
N_DAYS = len(_cal)  # 181


# ---------------------------------------------------------------------------
# 1. 월별 zip → 일별 집계 (역사_ID 수준, 캐시 지원)
# ---------------------------------------------------------------------------
USECOLS = ["승차_정류장/역사_ID", "하차_정류장/역사_ID", "승객_수"] \
    + PEAK_COLS + OFFPEAK_COLS


def detect_enc(zf, member):
    """파일별 인코딩 판별 — 대부분 cp949이나 일부 일자는 utf-8로 게시됨.
    utf-8은 자기검증적이므로 선두가 utf-8로 디코딩되면 utf-8."""
    with zf.open(member) as f:
        head = f.read(256)
    for k in range(len(head), len(head) - 4, -1):  # 멀티바이트 경계 보정
        try:
            head[:k].decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            continue
    return "cp949"


def _aggregate_member(zf, member):
    """zip 내부 일별 CSV 1개 → 지하철(4자리 ID)만 (oid,did) 집계."""
    parts = []
    enc = detect_enc(zf, member)
    if enc != "cp949":
        log(f"    (인코딩 예외: {member} -> {enc})")
    with zf.open(member) as f:
        for chunk in pd.read_csv(
                f, encoding=enc, usecols=USECOLS, chunksize=500_000,
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
    return (pd.concat(parts).groupby(["oid", "did"], as_index=False).sum()
            if parts else pd.DataFrame(columns=["oid", "did", "total",
                                                "peak", "offpeak"]))


def monthly_zips_available():
    return [m for m in MONTHS
            if os.path.exists(os.path.join(OD_DIR, f"kscc_dx_ra_od_{m}.zip"))]


def daily_subway_od():
    """상반기 181일 각각의 역사_ID 수준 집계를 (day, df, 출처) 로 순차 반환."""
    os.makedirs(CACHE, exist_ok=True)
    expected = {d.strftime("%Y%m%d") for d in _cal}
    seen = set()
    for month in MONTHS:
        zpath = os.path.join(OD_DIR, f"kscc_dx_ra_od_{month}.zip")
        # 해당 월 캐시가 완비되어 있으면 zip 을 열지 않는다 (zip 없이도 재현 가능)
        month_days = [d for d in sorted(expected) if d.startswith(month)]
        cached = {d: os.path.join(CACHE, f"od_{d}.csv.gz") for d in month_days}
        if all(os.path.exists(p) for p in cached.values()):
            for day, cpath in cached.items():
                seen.add(day)
                yield day, pd.read_csv(cpath, dtype={"oid": str, "did": str}), "cache"
            continue
        with zipfile.ZipFile(zpath) as zf:
            for m in sorted(m for m in zf.namelist() if m.endswith(".csv")):
                day = re.search(r"(\d{8})", m).group(1)
                if day not in expected:
                    continue
                seen.add(day)
                cpath = cached[day]
                if os.path.exists(cpath):
                    yield day, pd.read_csv(cpath, dtype={"oid": str,
                                                         "did": str}), "cache"
                else:
                    t0 = time.time()
                    g = _aggregate_member(zf, m)
                    g.to_csv(cpath, index=False, compression="gzip")
                    yield day, g, f"zip {time.time() - t0:.1f}s"
    missing = sorted(expected - seen)
    if missing:
        raise RuntimeError(f"누락된 날짜 {len(missing)}일: {missing[:5]}...")


def aggregate_h1(mapping):
    """181일 순차 집계 → 노드쌍 누적. 반환: (acc_all, acc_wd, acc_we, stats_df)."""
    id2node = dict(zip(mapping.역사_ID, mapping.node_id))
    acc_all = acc_wd = acc_we = None
    day_stats, lost_ids = [], set()
    t_start = time.time()
    for i, (day, g, src) in enumerate(daily_subway_od(), 1):
        is_weekend = pd.Timestamp(day).weekday() >= 5
        if not len(g):
            # 원천 결측일: 포털 zip 에 헤더만 있는 CSV(2026-01-09, 05-16 확인).
            log(f"[od] {i:3d}/{N_DAYS}일 ({day}) — **원천 결측(헤더만)** -> 제외")
            day_stats.append(dict(day=day, weekend=is_weekend,
                                  raw_total=0.0, mapped_total=0.0))
            continue
        g["node_o"] = g.oid.map(id2node)
        g["node_d"] = g.did.map(id2node)
        lost = g[g.node_o.isna() | g.node_d.isna()]
        lost_ids.update(lost.loc[lost.node_o.isna(), "oid"])
        lost_ids.update(lost.loc[lost.node_d.isna(), "did"])
        m = (g.dropna(subset=["node_o", "node_d"])
             .groupby(["node_o", "node_d"])[["total", "peak", "offpeak"]].sum())
        day_stats.append(dict(day=day, weekend=is_weekend,
                              raw_total=float(g.total.sum()),
                              mapped_total=float(m.total.sum())))
        acc_all = m[["total"]] if acc_all is None else acc_all.add(
            m[["total"]], fill_value=0)
        if is_weekend:
            acc_we = m[["total"]] if acc_we is None else acc_we.add(
                m[["total"]], fill_value=0)
        else:
            acc_wd = m if acc_wd is None else acc_wd.add(m, fill_value=0)
        if i % 20 == 0 or i == N_DAYS:
            log(f"[od] {i:3d}/{N_DAYS}일 ({day}, {src}) — "
                f"경과 {time.time() - t_start:.0f}s, 누적쌍 {len(acc_all):,}")
    stats = pd.DataFrame(day_stats)
    stats.attrs["lost_ids"] = sorted(lost_ids)
    return acc_all, acc_wd, acc_we, stats


def build_h1_outputs(acc_all, acc_wd, acc_we, stats):
    """누적 → od_daily_avg_2026H1.csv / od_peak_2026H1.csv (유효일 평균)."""
    nz = stats[stats.raw_total > 0]
    n_eff, n_wd, n_we = len(nz), int((~nz.weekend).sum()), int(nz.weekend.sum())
    empty = stats[stats.raw_total == 0].day.tolist()
    log(f"[od] 유효 {n_eff}일 (주중 {n_wd} / 주말 {n_we})"
        + (f" — 원천 결측 {len(empty)}일: {empty}" if empty else ""))
    raw, kept = stats.raw_total.sum(), stats.mapped_total.sum()
    log(f"[od] 상반기 총 통행 {raw:,.0f} -> 매핑 후 {kept:,.0f} "
        f"(보존율 {kept / raw * 100:.2f}%)")

    daily_avg = acc_all.rename(columns={"total": "trips_avg_daily"})
    daily_avg["trips_avg_daily"] = (daily_avg.trips_avg_daily / n_eff).round(2)
    wd = (acc_wd[["total"]] / n_wd).round(2).rename(
        columns={"total": "trips_avg_weekday"})
    we = (acc_we / n_we).round(2).rename(columns={"total": "trips_avg_weekend"})
    daily_avg = (daily_avg.join(wd, how="left").join(we, how="left")
                 .fillna({"trips_avg_weekday": 0, "trips_avg_weekend": 0})
                 .reset_index()
                 .sort_values("trips_avg_daily", ascending=False,
                              ignore_index=True))
    os.makedirs(OUT, exist_ok=True)
    daily_avg.to_csv(os.path.join(OUT, "od_daily_avg_2026H1.csv"),
                     index=False, encoding="utf-8-sig")
    log(f"[out] od_daily_avg_2026H1.csv: {len(daily_avg):,} 노드쌍")

    pk = (acc_wd[["peak", "offpeak"]] / n_wd).round(2).rename(
        columns={"peak": "trips_peak_am_0709", "offpeak": "trips_offpeak_1113"})
    pk = pk[(pk.trips_peak_am_0709 > 0) | (pk.trips_offpeak_1113 > 0)]
    pk = pk.reset_index().sort_values("trips_peak_am_0709",
                                      ascending=False, ignore_index=True)
    pk.to_csv(os.path.join(OUT, "od_peak_2026H1.csv"),
              index=False, encoding="utf-8-sig")
    log(f"[out] od_peak_2026H1.csv: {len(pk):,} 노드쌍 (주중 {n_wd}일 평균)")

    meta = dict(n_days_eff=n_eff, n_weekdays_eff=n_wd, n_weekends_eff=n_we,
                empty_days=empty, raw_total=float(raw), kept_total=float(kept),
                lost_ids=stats.attrs["lost_ids"])
    return daily_avg, pk, meta


# ---------------------------------------------------------------------------
# 2. 지방 승하차 → 노드별 일평균 (부산·대구·대전 = od_analysis 동일 /
#    광주·인천 = 신규)
# ---------------------------------------------------------------------------
def regional_weights_h1(nodes):
    """부산·대구·대전·광주 (2026-01~06 완전 중첩) 와
    인천 1·2호선 (2026-01~04 부분 중첩) 의 {node_id: (승차, 하차)} 일평균."""
    out, out_inc, miss = {}, {}, []

    def put(dst, canon, name, board, alight, alias=None):
        nm = norm_name(name)
        if alias:
            nm = alias.get(nm, nm)
        # 대구 환승역은 호선번호 접미 숫자(반월당1 등)가 붙음 → 제거 후보도 시도
        cand = [nm] + ([nm[:-1]] if nm[-1:].isdigit() else [])
        for c in cand:
            hit = nodes[(nodes.canon == canon) & (nodes.name_norm == c)]
            if len(hit):
                dst[hit.iloc[0].node_id] = (round(board, 1), round(alight, 1))
                return True
        miss.append((canon, name))
        return False

    # 부산 (2026-01~06, od_analysis.regional_weights 와 동일 방식)
    b = pd.read_csv(os.path.join(OD_DIR, "busan_시간대별_승하차인원.csv"),
                    encoding="cp949")
    b["canon"] = "부산" + (b.역번호 // 100).clip(lower=1).astype(str) + "호선"
    for (canon, name), g in b.groupby(["canon", "역명"]):
        board = g[g.구분 == "승차"].groupby("년월일")["합계"].sum().mean()
        alight = g[g.구분 == "하차"].groupby("년월일")["합계"].sum().mean()
        put(out, canon, name, board or 0, alight or 0)

    # 대구 (2026년 1~6월) — 2021·2022 개칭 별칭
    ALIAS_DG = {"대공원": "수성알파시티", "어린이회관": "어린이세상"}
    d = pd.read_csv(os.path.join(OD_DIR, "daegu_역별일별시간별_승하차인원.csv"),
                    encoding="cp949")
    hour_cols = [c for c in d.columns if "시" in c and "-" in c]
    d["tot"] = d[hour_cols].sum(axis=1)
    d["canon"] = "대구" + (d.역번호 // 1000).astype(str) + "호선"
    for (canon, name), g in d.groupby(["canon", "역명"]):
        board = g[g.승하차 == "승차"].groupby(["월", "일"])["tot"].sum().mean()
        alight = g[g.승하차 == "하차"].groupby(["월", "일"])["tot"].sum().mean()
        put(out, canon, name, board or 0, alight or 0, alias=ALIAS_DG)

    # 대전 (2026-01~06)
    j = pd.read_csv(os.path.join(OD_DIR, "daejeon_시간대별_승하차인원.csv"),
                    encoding="cp949")
    hour_cols = [c for c in j.columns if "-" in c and "시" in c]
    j["tot"] = j[hour_cols].sum(axis=1)
    for name, g in j.groupby("역명"):
        board = g[g.구분 == "승차"].groupby("날짜")["tot"].sum().mean()
        alight = g[g.구분 == "하차"].groupby("날짜")["tot"].sum().mean()
        put(out, "대전1호선", name, board or 0, alight or 0)

    # 광주 (2026-01~06, 신규 — od_analysis 에서는 승하차 미확보로 none 이었음)
    #   '컨벤션센터' = 그래프 노드 '김대중컨벤션센터(마륵)' 의 광주 파일 축약 표기,
    #   '학동증심사' = '학동·증심사입구' → 별칭 보정.
    ALIAS_GJ = {"컨벤션센터": "김대중컨벤션센터", "마륵": "김대중컨벤션센터",
                "학동증심사": "학동증심사입구"}
    gw = pd.read_csv(
        os.path.join(OD_DIR, "gwangju_역일시간대별_승하차량_202601-202606.csv"),
        encoding="cp949", thousands=",")  # 일부 값이 "1,031" 형태(천단위 콤마)
    hour_cols = [c for c in gw.columns if re.fullmatch(r"\d{2}_\d{2}", c)]
    gw["tot"] = gw[hour_cols].sum(axis=1)
    gw["구분"] = gw.구분.str.strip()
    for name, g in gw.groupby(gw.역명.str.strip()):
        board = g[g.구분 == "승차"].groupby("일자")["tot"].sum().mean()
        alight = g[g.구분 == "하차"].groupby("일자")["tot"].sum().mean()
        put(out, "광주1호선", name, board or 0, alight or 0, alias=ALIAS_GJ)

    # 인천 1·2호선 (2026-01-01~04-30 만 필터 — 부분 중첩, 잔여 불일치 5~6월)
    #   호선은 역번호 백단위(31xx=1호선, 32xx=2호선, 37xx=7호선)로 판별 —
    #   호선명 컬럼은 환승역 오표기 존재 (예: 인천시청 2호선 게이트 3221이 호선명=1).
    #   7호선(인천 구간) 행은 그래프 노선이 '7호선'(seoul_od 커버)이므로 제외.
    inc = pd.read_csv(
        os.path.join(OD_DIR, "incheon_역별일별시간대별_이용인원_202501-202604.csv"),
        encoding="cp949")
    inc = inc[(inc.수송일자 >= "2026-01-01") & (inc.수송일자 <= "2026-04-30")
              & (inc.역번호 // 100).isin([31, 32])].copy()
    hour_cols = [c for c in inc.columns if "시" in c and c != "수송일자"]
    inc["tot"] = inc[hour_cols].sum(axis=1)
    inc["canon"] = "인천" + (inc.역번호 // 100 - 30).astype(str) + "호선"
    log(f"[incheon] 2026-01~04 필터: {len(inc):,}행, "
        f"{inc.수송일자.min()} ~ {inc.수송일자.max()}, "
        f"1·2호선 {inc.역명.str.strip().nunique()}개 역")
    for (canon, name), g in inc.groupby(["canon", inc.역명.str.strip()]):
        board = g[g.승하차구분 == "승차"].groupby("수송일자")["tot"].sum().mean()
        alight = g[g.승하차구분 == "하차"].groupby("수송일자")["tot"].sum().mean()
        put(out_inc, canon, name, board or 0, alight or 0)

    if miss:
        log(f"[weights] 지방 승하차 역명 미매칭 {len(miss)}건: {miss}")
    log(f"[weights] 부산·대구·대전·광주 {len(out)}개 / 인천 1·2호선 {len(out_inc)}개 노드")
    return out, out_inc, miss


def build_node_weights_h1(nodes, daily_avg, mapping, reg, reg_inc):
    """노드별 일평균 승차·하차 → node_weights_2026H1.csv.

    weight_source (기간 정합 상태 표시):
    - seoul_od_2026H1                    : 서울 역간 OD 상반기 (완전 중첩)
    - boarding_data_2026H1               : 부산·대구·대전·광주 승하차 (완전 중첩)
    - incheon_boarding_202601-04_partial : 인천 1·2호선 승하차 (**부분 중첩**,
      운영기관 공식 승하차 우선 — 완전 중첩이 필요하면 od_daily_avg_2026H1 의
      OD 기반 값을 대안으로 사용 가능)
    - none                               : 가중치 없음
    """
    boarding = daily_avg.groupby("node_o")["trips_avg_daily"].sum()
    alighting = daily_avg.groupby("node_d")["trips_avg_daily"].sum()
    seoul_nodes = set(mapping.node_id)

    rows = []
    for _, n in nodes.iterrows():
        nid = n.node_id
        base = dict(node_id=nid, 역사명=n.역사명, 노선명=n.노선명, region=n.region)
        if nid in reg_inc:
            bo, al = reg_inc[nid]
            rows.append(dict(base, boarding_daily_avg=bo, alighting_daily_avg=al,
                             weight_source="incheon_boarding_202601-04_partial"))
        elif nid in reg:
            bo, al = reg[nid]
            rows.append(dict(base, boarding_daily_avg=bo, alighting_daily_avg=al,
                             weight_source="boarding_data_2026H1"))
        elif nid in seoul_nodes:
            rows.append(dict(
                base,
                boarding_daily_avg=round(float(boarding.get(nid, 0)), 2),
                alighting_daily_avg=round(float(alighting.get(nid, 0)), 2),
                weight_source="seoul_od_2026H1"))
        else:
            rows.append(dict(base, boarding_daily_avg=None,
                             alighting_daily_avg=None, weight_source="none"))
    w = pd.DataFrame(rows)
    w.to_csv(os.path.join(OUT, "node_weights_2026H1.csv"),
             index=False, encoding="utf-8-sig")
    cov = w.weight_source.value_counts().to_dict()
    log(f"[out] node_weights_2026H1.csv: {len(w)} 노드, 커버리지 {cov}")
    return w


# ---------------------------------------------------------------------------
# 3. 검증 — 7월 1주(od_analysis 산출물) 대비 순위 상관 (Spearman)
# ---------------------------------------------------------------------------
def validate_vs_july(daily_avg, weights_h1):
    """기간을 바꿔도 순위가 유지되는지(기간 강건성). scipy 없이 pandas 사용.
    od_daily_avg.csv(7월 1주, .gitignore 대상)가 없으면 노드 가중치 비교만 수행."""
    corrs = {}

    def rho(df, a, b):
        return float(df[[a, b]].corr(method="spearman").iloc[0, 1])

    w_jul = pd.read_csv(os.path.join(OUT, "node_weights.csv"))
    cmp = weights_h1.merge(w_jul[["node_id", "boarding_daily_avg",
                                  "alighting_daily_avg", "weight_source"]],
                           on="node_id", suffixes=("_h1", "_jul"))
    cmp = cmp.dropna(subset=["boarding_daily_avg_h1", "boarding_daily_avg_jul"])
    seoul = cmp[(cmp.weight_source_h1 == "seoul_od_2026H1")
                & (cmp.weight_source_jul == "seoul_od")]
    corrs["수도권(seoul_od, 동일 원천)"] = dict(
        n=len(seoul),
        boarding=rho(seoul, "boarding_daily_avg_h1", "boarding_daily_avg_jul"),
        alighting=rho(seoul, "alighting_daily_avg_h1", "alighting_daily_avg_jul"))
    inc = cmp[cmp.weight_source_h1 == "incheon_boarding_202601-04_partial"]
    if len(inc):
        corrs["인천 1·2호선(H1=운영기관 vs 7월=seoul_od, 원천 상이)"] = dict(
            n=len(inc),
            boarding=rho(inc, "boarding_daily_avg_h1", "boarding_daily_avg_jul"),
            alighting=rho(inc, "alighting_daily_avg_h1",
                          "alighting_daily_avg_jul"))
    corrs["전체(가중치 보유 공통 노드)"] = dict(
        n=len(cmp),
        boarding=rho(cmp, "boarding_daily_avg_h1", "boarding_daily_avg_jul"),
        alighting=rho(cmp, "alighting_daily_avg_h1", "alighting_daily_avg_jul"))

    jul_path = os.path.join(OUT, "od_daily_avg.csv")
    if os.path.exists(jul_path):
        od_jul = pd.read_csv(jul_path)
        pair = daily_avg.merge(od_jul[["node_o", "node_d", "trips_avg_daily"]],
                               on=["node_o", "node_d"], suffixes=("_h1", "_jul"))
        corrs["OD 노드쌍(공통쌍 통행량)"] = dict(
            n=len(pair),
            boarding=rho(pair, "trips_avg_daily_h1", "trips_avg_daily_jul"),
            alighting=None)
    for k, v in corrs.items():
        log(f"[spearman] {k}: n={v['n']:,} 승차 {v['boarding']:.4f}"
            + (f" / 하차 {v['alighting']:.4f}"
               if v.get("alighting") is not None else ""))
    return corrs


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------
def main():
    nodes = oda.load_nodes()
    mapping = pd.read_csv(os.path.join(OUT, "od_station_mapping.csv"),
                          dtype={"역사_ID": str})
    log(f"[mapping] od_station_mapping.csv 재사용: {len(mapping)}개 역사_ID")

    have_cache = os.path.isdir(CACHE) and len(
        [f for f in os.listdir(CACHE) if f.endswith(".csv.gz")]) == N_DAYS
    if not have_cache and len(monthly_zips_available()) != len(MONTHS):
        log("[od] kscc_dx_ra_od_2026MM.zip(월별 6개)·h1_cache 모두 미배치 — "
            "H1 집계 불가 (data/od/README.md 안내대로 배치 후 재실행)")
        return None

    acc_all, acc_wd, acc_we, stats = aggregate_h1(mapping)
    daily_avg, pk, meta = build_h1_outputs(acc_all, acc_wd, acc_we, stats)
    reg, reg_inc, miss = regional_weights_h1(nodes)
    weights_h1 = build_node_weights_h1(nodes, daily_avg, mapping, reg, reg_inc)
    corrs = validate_vs_july(daily_avg, weights_h1)
    log(f"[done] 2026H1 기간 정합 집계 완료 — 유효 {meta['n_days_eff']}일, "
        f"보존율 {meta['kept_total'] / meta['raw_total'] * 100:.2f}%")
    return dict(nodes=nodes, mapping=mapping, daily_avg=daily_avg, peak=pk,
                meta=meta, weights=weights_h1, corrs=corrs,
                regional_miss=miss)


if __name__ == "__main__":
    main()
