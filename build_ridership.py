# -*- coding: utf-8 -*-
"""
역별 승하차 인원(실수요) 통합 — 노선 단위 결합

KRIC 철도통계 '도시철도 역별 승강차실적' 18개 운영기관 파일 + 코레일 광역 실적을
그래프 노드(역×노선)에 **노선 단위로** 결합한다.

이전 판의 치명적 결함(2026-08-04 수정)
  ① 코레일 광역 파일을 역별 승하차로 취급했다. 실제로는 (노선, 역) 단위 발착·**통과**
     대장이라 그 역을 지나가기만 하는 열차의 승객까지 행으로 잡힌다. 역명 기준으로
     합산하면서 구일역에 경부선 통과 5,787만 명이 붙어 일평균 32만 명(실제 약 1.3만)이 됐다.
  ② '역명(2)' 형태의 인계 행은 다른 운영기관 실적을 중복으로 담고 있는데 그대로 더해졌다.
  ③ 역명만으로 묶어 서울 시청과 부산 시청(연제), 대구 중앙로와 대전 중앙로가 합산됐다.
  ④ 환승역 수요를 노선 수로 균등 분배해 사당 2호선과 4호선에 같은 값이 들어갔다.
  ⑤ 공항철도 14개 역의 하차인원이 원본에서 전부 0인데 그대로 사용해 수요가 절반이 됐다.

수정 방침
  · 노선 단위로 매칭한다. 그 역의 자기 노선 행만 채택하므로 통과·인계 행이 자동 배제된다.
  · 역명이 아니라 (운영기관, 노선, 역명)이 키다. 동명이역 오염이 원천 차단된다.
  · 환승역은 노선별 실적이 원본에 있으므로 균등 분배가 필요 없다.
  · 공항철도 하차 결측은 승차와 대칭이라 가정해 보정하고 플래그로 남긴다.

입력 : data/raw/승하차/2025년_*_역별 승강차실적.xls
       data/raw/승하차/2025_10_코레일광역_역별발착통과실적.csv
출력 : data/processed/ridership.csv    정제된 (기관·노선·역) 실적
       data/processed/node_demand.csv  node_id별 일평균 승하차
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


# ---------- 노선 정규화 ----------
# 실적 파일과 역사정보의 노선 표기가 달라(1호선 / 대구 도시철도 1호선 / 인천지하철 1호선 …)
# '권역 + 번호' 또는 고유 노선명으로 정규화한 뒤 맞춘다.
CITY_OF_OPER = [
    ("서울교통공사", "서울"), ("서울시메트로9", "서울"), ("서울메트로9", "서울"),
    ("부산-김해", "부산김해"), ("부산김해", "부산김해"), ("부산교통공사", "부산"),
    ("대구교통공사", "대구"), ("대전교통공사", "대전"), ("광주교통공사", "광주"),
    ("인천교통공사", "인천"), ("남양주", "수도권"), ("구리", "수도권"),
]
# 실적 파일의 노선 표기 → 역사정보 노선명(고유명 노선)
LINE_ALIAS = {
    "중앙선": "경의중앙선", "안산선": "안산과천선", "김포골드": "김포도시철도",
    "공항철도": "인천국제공항선", "우이신설": "우이신설선",
    "의정부경전철": "의정부", "용인경전철": "에버라인",
}
# 한 실적 노선이 여러 역사정보 노선에 걸치는 경우
LINE_SPLIT = {"분당선": {"분당선", "수인선"}, "경부선": {"경부선", "장항선"}}


def city_of(oper):
    for k, v in CITY_OF_OPER:
        if k in str(oper):
            return v
    return ""


def canon_line(oper, line):
    """(운영기관, 노선표기) → 정규화 노선키 집합"""
    s = re.sub(r"\s+", "", str(line))
    m = re.fullmatch(r"(\d+)호선", s) or re.fullmatch(r"(\d+)", s)
    if m:
        if "남양주" in str(oper) and m.group(1) == "4":
            return {"진접선"}
        return {f"{city_of(oper)}{m.group(1)}"}
    s = LINE_ALIAS.get(s, s)
    return LINE_SPLIT.get(s, {s})


def node_line_key(oper, line):
    """역사정보 (운영기관명, 노선명) → 정규화 노선키.

    '수도권 경량도시철도 신림선'처럼 수식어가 앞에 붙은 표기는 마지막 토큰만 취한다.
    """
    s0 = str(line).strip()
    s = re.sub(r"\s+", "", s0)
    m = re.search(r"(\d+)호선$", s)
    if m:
        return f"{city_of(oper)}{m.group(1)}"
    return s0.split()[-1] if s0.split() else s


# 역사정보 노선명과 실적 노선 표기가 corridor 단위로 어긋나는 경우
# (용산~왕십리 구간은 역사정보에서 '경원선', 실적에서 '중앙선'으로 표기된다)
NODE_LINE_FALLBACK = {
    "경원선": ["경의중앙선"], "경의중앙선": ["경원선"],
    "수인선": ["분당선"], "장항선": ["경부선"], "안산과천선": ["경부선"],
}

# 개칭 역 (실적 파일은 옛 이름, 역사정보는 새 이름)
STATION_ALIAS = {"불암산": "당고개", "자양": "뚝섬유원지", "능길": "신길온천",
                 "한국항공대": "화전"}

OPER_TOKENS = ["서울교통공사", "메트로9", "부산교통공사", "부산-김해", "부산김해",
               "대구교통공사", "대전교통공사", "광주교통공사", "인천교통공사",
               "한국철도공사", "공항철도", "김포골드", "김포도시철도", "남서울경전철",
               "우이신설", "의정부", "용인", "신분당", "남양주", "구리", "인천국제공항공사"]


def oper_key(oper):
    s = str(oper)
    for t in OPER_TOKENS:
        if t in s:
            return t
    return re.sub(r"\s+", "", s)


# ---------- 원본 로드 ----------
def load_xls():
    rows = []
    for f in sorted(glob.glob(RAW + "*.xls")):
        raw = pd.read_excel(f, header=None)
        hdr = raw.index[raw[0].astype(str).str.strip() == "연도"]
        start = (hdr[0] + 2) if len(hdr) else 3
        d = raw.iloc[start:, :6].copy()
        d.columns = ["연도", "기관", "역명", "호선", "승차인원", "하차인원"]
        d = d[d["역명"].notna()]
        d = d[~d["역명"].astype(str).str.replace(" ", "").isin(["합계", "합 계"])]
        for c in ("승차인원", "하차인원"):
            d[c] = pd.to_numeric(d[c], errors="coerce")
        d = d.dropna(subset=["승차인원"])
        d["출처파일"] = os.path.basename(f)
        if d["기관"].isna().all():
            d["기관"] = os.path.basename(f).split("_")[1]
        rows.append(d)
    r = pd.concat(rows, ignore_index=True)
    r["기관"] = r["기관"].ffill()
    return r


def load_korail():
    """코레일 광역 (노선, 역) 발착·통과 대장.

    '역명(n)' 인계 행은 타 기관 실적의 중복이므로 버린다. 통과 행은 노선 단위
    매칭 단계에서 자동 배제된다(그 역의 자기 노선이 아니므로).
    """
    fp = RAW + "2025_10_코레일광역_역별발착통과실적.csv"
    if not os.path.exists(fp):
        return None
    k = pd.read_csv(fp)
    k = k.rename(columns={"노선": "호선", "강차인원": "하차인원"})
    hand = k["역명"].astype(str).str.contains(r"\(\d+\)")
    print(f"  코레일 인계행(역명(n)) 제외: {int(hand.sum())}행")
    k = k[~hand].copy()
    k["연도"] = 2025
    k["기관"] = "한국철도공사"
    for c in ("승차인원", "하차인원"):
        k[c] = pd.to_numeric(k[c], errors="coerce") * 12      # 2025-10 월 실적 → 연 환산
    k["출처파일"] = os.path.basename(fp)
    return k[["연도", "기관", "역명", "호선", "승차인원", "하차인원", "출처파일"]]


def load_all():
    parts = [load_xls()]
    kr = load_korail()
    if kr is not None:
        parts.append(kr)
    r = pd.concat(parts, ignore_index=True)

    # 하차 결측·0 보정: 공항철도는 원본에 하차가 전부 0으로 들어온다. 승차와 대칭 가정.
    bad = r["하차인원"].isna() | (r["하차인원"] == 0)
    r["하차보정"] = bad.astype(int)
    r.loc[bad, "하차인원"] = r.loc[bad, "승차인원"]
    if bad.any():
        print(f"  하차 결측/0 보정(승차 대칭 가정): {int(bad.sum())}행 "
              f"· 기관 {sorted(set(r.loc[bad,'기관'].astype(str)))}")

    r["연간승하차"] = r["승차인원"] + r["하차인원"]
    r["일평균승하차"] = (r["연간승하차"] / 365).round(1)
    r["name_n"] = r["역명"].map(norm)
    return r


# ---------- 노드 결합 ----------
def attach_to_nodes(rid):
    nodes = pd.read_csv(PROC + "nodes.csv")
    nodes["name_n"] = nodes["역사명"].map(norm)
    nodes["lkey"] = [node_line_key(o, l) for o, l in zip(nodes["운영기관명"], nodes["노선명"])]

    idx = {}
    for r in rid.itertuples(index=False):
        for lk in canon_line(r.기관, r.호선):
            idx[(lk, r.name_n)] = idx.get((lk, r.name_n), 0.0) + r.일평균승하차
    names_by_line = {}
    for (lk, nm) in idx:
        names_by_line.setdefault(lk, []).append(nm)

    # 같은 (노선키)에 붙는 노드가 여럿이면 실적을 나눠 갖는다(지선 등 예외)
    nkey = nodes.groupby(["lkey", "name_n"])["node_id"].transform("size")
    vals, how, notes = [], [], []
    matched_keys = set()
    # 기관 단위 색인 (자기 노선에 실적이 없는 환승역 보완용)
    opidx = {}
    for r in rid.itertuples(index=False):
        opidx.setdefault((oper_key(r.기관), r.name_n), 0.0)
        opidx[(oper_key(r.기관), r.name_n)] += r.일평균승하차
    nodes["okey"] = nodes["운영기관명"].map(oper_key)
    ocnt = nodes.groupby(["okey", "name_n"])["node_id"].transform("size")

    for (_, r), cnt, oc in zip(nodes.iterrows(), nkey, ocnt):
        got, tag, note = None, "미매칭", ""
        nm0 = STATION_ALIAS.get(r["name_n"], r["name_n"])
        for lk in [r["lkey"]] + NODE_LINE_FALLBACK.get(r["lkey"], []):
            if (lk, nm0) in idx and nm0 != r["name_n"]:
                got, tag = idx[(lk, nm0)], "역명개칭"
                matched_keys.add((lk, nm0)); note = f"{lk}:{nm0}"
                break
            if (lk, r["name_n"]) in idx:
                got, tag = idx[(lk, r["name_n"])], ("노선일치" if lk == r["lkey"] else "노선별칭")
                matched_keys.add((lk, r["name_n"])); note = lk
                break
            # 역명 개칭(부산 남포동→남포, 구서동→구서, 교대앞→교대 등) 접두 일치
            cand = [x for x in names_by_line.get(lk, [])
                    if x != r["name_n"] and (x.startswith(r["name_n"]) or r["name_n"].startswith(x))]
            if len(cand) == 1:
                got, tag = idx[(lk, cand[0])], "역명개칭"
                matched_keys.add((lk, cand[0])); note = f"{lk}:{cand[0]}"
                break
        if got is None:
            # 자기 노선 실적이 없는 환승역(부산 수영·미남 등)은 같은 기관 안에서 보완하고
            # 그 역명을 공유하는 노드 수로 나눈다.
            v = opidx.get((r["okey"], nm0))
            if v is not None:
                got, tag, note = v / max(int(oc), 1), "기관보완", r["okey"]
        if got is None:
            vals.append(np.nan); how.append(tag); notes.append("")
        else:
            vals.append(round(got / (cnt if tag == "노선일치" else 1), 1))
            how.append(tag); notes.append(note)
    nodes["매칭근거"] = notes
    nodes["일평균승하차"] = vals
    nodes["매칭방식"] = how
    nodes["수요_매칭"] = nodes["일평균승하차"].notna().astype(int)
    # 하위호환 컬럼: 더 이상 균등 분배하지 않으므로 노선 단위 값 그대로
    nodes["일평균승하차_배분"] = nodes["일평균승하차"]
    out = nodes[["node_id", "역사명", "노선명", "운영기관명", "lkey", "매칭근거",
                 "일평균승하차", "일평균승하차_배분", "수요_매칭", "매칭방식"]]
    out.to_csv(PROC + "node_demand.csv", index=False, encoding="utf-8-sig")

    unused = [(k[0], k[1], round(v)) for k, v in idx.items() if k not in matched_keys]
    unused.sort(key=lambda x: -x[2])
    print(f"\n노드에 붙지 않은 실적키 {len(unused)}개 (상위 12):")
    for u in unused[:12]:
        print("   ", u)
    return out


def main():
    rid = load_all()
    rid.to_csv(PROC + "ridership.csv", index=False, encoding="utf-8-sig")
    print(f"\n승하차 정제 통합: {len(rid):,}행 · 기관 {rid['기관'].nunique()}개")
    print(f"  원본 합계 {rid['연간승하차'].sum()/1e8:.1f}억 명/년")

    nd = attach_to_nodes(rid)
    print(f"\n그래프 노드 매칭: {nd['수요_매칭'].sum()}/{len(nd)} "
          f"({nd['수요_매칭'].mean()*100:.1f}%)")
    miss = nd[nd["수요_매칭"] == 0]
    if len(miss):
        print("미매칭 노드:")
        print(miss[["역사명", "노선명", "운영기관명"]].head(30).to_string(index=False))

    m = nd[nd["수요_매칭"] == 1]
    print(f"\n결합된 일평균 승하차 총계: {m['일평균승하차'].sum()/1e4:.0f}만 명/일")
    print("\n운영기관별 일평균(만 명):")
    print((m.groupby("운영기관명")["일평균승하차"].sum() / 1e4).round(1)
          .sort_values(ascending=False).head(8).to_string())
    print("\n일평균 승하차 상위 12노드:")
    print(m.nlargest(12, "일평균승하차")[["역사명", "노선명", "일평균승하차"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
