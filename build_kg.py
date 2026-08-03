# -*- coding: utf-8 -*-
"""
도시철도 도메인 지식그래프(Knowledge Graph) 구축

물리 네트워크(역-역 단일 그래프)를 타입이 있는 이종(heterogeneous) 그래프로 재구성한다.
역이 어느 노선/기관/지역에 속하는지를 명시적 관계로 표현함으로써,
단일 그래프로는 불가능한 '노선 단위 통째 중단', '운영기관 전체 마비' 같은
계층적 장애 시나리오를 질의·시뮬레이션할 수 있다.

엔티티 : Station, Line, Operator, Region(시도), MetroArea(권역)
관계   : CONNECTS_TO, TRANSFERS_TO, ON_LINE, OPERATED_BY, LOCATED_IN,
         IN_METRO_AREA, LINE_OPERATED_BY

출력 : kg/kg_nodes.csv, kg/kg_edges.csv, kg/knowledge_graph.graphml,
       kg/raility.ttl (RDF Turtle), kg/kg_import.cypher (Neo4j)
"""
import os, re, json
import pandas as pd
import numpy as np
import networkx as nx

PROC = "data/processed/"
RAW = "data/raw/"
RES = "results/"
OUT = "kg/"
NS = "https://github.com/leeseoyang/Raility/ns#"

REGION_ALIAS = {"서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
                "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
                "울산": "울산광역시", "세종": "세종특별자치시", "경기": "경기도",
                "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
                "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도",
                "경남": "경상남도", "제주": "제주특별자치도"}


def slug(s):
    s = re.sub(r"\s+", "_", str(s).strip())
    return re.sub(r"[^0-9A-Za-z가-힣_\-]", "", s) or "UNK"


SIDO = set(REGION_ALIAS.values())
# 도로명주소가 시도로 시작하지 않는 표기(기초자치단체/동부터 시작) 보정용
CITY2SIDO = {"경산시": "경상북도"}
OP2SIDO = {"대구교통공사": "대구광역시", "구리도시공사": "경기도"}


def region_of_addr(addr, operator=""):
    """주소 → 시도. 원본 222건이 시도 없이 시작해(대구 구 단위, 구리 동 단위 등)
    ① 시도 약칭 매칭 → ② 기초자치단체 매핑 → ③ 운영기관 기본 시도 순으로 해석."""
    if pd.isna(addr) or not str(addr).strip():
        return None
    head = str(addr).split()[0]
    if head in SIDO:
        return head
    for k, v in REGION_ALIAS.items():
        if head.startswith(k):
            return v
    if head in CITY2SIDO:
        return CITY2SIDO[head]
    return OP2SIDO.get(str(operator).strip())


def metro_area(op):
    op = str(op)
    if any(k in op for k in ["부산", "김해"]):
        return "부산·김해권"
    for k, v in [("대구", "대구권"), ("대전", "대전권"), ("광주", "광주권")]:
        if k in op:
            return v
    return "수도권"


def main():
    os.makedirs(OUT, exist_ok=True)
    nodes = pd.read_csv(PROC + "nodes.csv")
    edges = pd.read_csv(PROC + "edges_adjacency.csv")
    trans = pd.read_csv(PROC + "edges_transfer.csv")
    for c in ["노선번호", "node_id", "운영기관명", "노선명"]:
        nodes[c] = nodes[c].astype(str).str.strip()

    # 분석 결과(있으면) 역 속성으로 병합 — KG를 '분석 결과까지 담은' 지식 자산으로
    cen = imp = None
    if os.path.exists(RES + "centrality_metro.csv"):
        cen = pd.read_csv(RES + "centrality_metro.csv").set_index("node_id")
    if os.path.exists(RES + "single_removal_impact_metro.csv"):
        imp = pd.read_csv(RES + "single_removal_impact_metro.csv").set_index("node_id")

    # 노선정보로 Line 엔티티 보강(노선명 일치분만)
    line_meta = {}
    lp = RAW + "전체_도시철도노선정보_20260630.xlsx"
    if os.path.exists(lp):
        li = pd.read_excel(lp)

        def f_or_none(v):
            try:
                x = float(v)
                return None if not np.isfinite(x) else x
            except (TypeError, ValueError):
                return None
        for _, r in li.iterrows():
            line_meta.setdefault(str(r["노선명"]).strip(), {
                "노선연장_m": f_or_none(r.get("노선연장")),
                "개통일자": "" if pd.isna(r.get("개통일자")) else str(r["개통일자"])[:10],
                "기점명": str(r.get("기점명", "")), "종점명": str(r.get("종점명", "")),
            })

    G = nx.MultiDiGraph()
    rows_n, rows_e = [], []

    def add_node(nid, ntype, label, **attrs):
        if nid in G:
            return
        a = {k: ("" if v is None or (isinstance(v, float) and np.isnan(v)) else v)
             for k, v in attrs.items()}
        G.add_node(nid, type=ntype, label=label, **a)
        rows_n.append({"id": nid, "type": ntype, "label": label,
                       **{k: a.get(k, "") for k in a}})

    def add_edge(s, p, o, **attrs):
        G.add_edge(s, o, key=p, predicate=p, **attrs)
        rows_e.append({"source": s, "predicate": p, "target": o, **attrs})

    # ---------- 엔티티 ----------
    for _, r in nodes.iterrows():
        sid = "Station:" + r["node_id"]
        lat = r["역위도"] if pd.notna(r["역위도"]) else ""
        lon = r["역경도"] if pd.notna(r["역경도"]) else ""
        attrs = dict(역사명=r["역사명"], 역번호=str(r["역번호"]), lat=lat, lon=lon,
                     환승역=str(r.get("환승역구분", "")),
                     주소="" if pd.isna(r.get("역사도로명주소")) else str(r["역사도로명주소"]))
        if cen is not None and r["node_id"] in cen.index:
            c = cen.loc[r["node_id"]]
            attrs.update(매개중심성=float(c["매개중심성"]), 연결중심성=int(c["연결중심성"]))
        if imp is not None and r["node_id"] in imp.index:
            i = imp.loc[r["node_id"]]
            attrs.update(효율저하율=float(i["효율저하율_%"]),
                         승객가중효율저하율=float(i["승객가중효율저하율_%"]),
                         단절유발=int(i["분리유발"]))
        add_node(sid, "Station", r["역사명"], **attrs)

    # Line 정체성은 노선번호 기준. 동일 노선번호에 노선명이 2개인 원본 이슈
    # (I4101=1호선/경부선 등 4건)는 최빈명을 대표명, 나머지를 altLabel로 보존.
    line_alias = {}
    for lnum, g in nodes.groupby("노선번호"):
        names = g["노선명"].value_counts()
        canon = names.index[0]
        alt = "; ".join(names.index[1:])
        line_alias[lnum] = canon
        m = line_meta.get(canon, {})
        add_node("Line:" + slug(lnum), "Line", canon, 노선번호=lnum, 역수=int(len(g)),
                 altLabel=alt, 노선연장_m=m.get("노선연장_m"),
                 개통일자=m.get("개통일자", ""))

    for op in sorted(nodes["운영기관명"].unique()):
        add_node("Operator:" + slug(op), "Operator", op,
                 역수=int((nodes["운영기관명"] == op).sum()))

    nodes["region"] = [region_of_addr(a, o) for a, o in
                       zip(nodes["역사도로명주소"], nodes["운영기관명"])]
    for rg in sorted(x for x in nodes["region"].dropna().unique()):
        add_node("Region:" + slug(rg), "Region", rg,
                 역수=int((nodes["region"] == rg).sum()))

    nodes["area"] = nodes["운영기관명"].map(metro_area)
    for ar in sorted(nodes["area"].unique()):
        add_node("MetroArea:" + slug(ar), "MetroArea", ar,
                 역수=int((nodes["area"] == ar).sum()))

    # ---------- 관계 ----------
    for _, r in nodes.iterrows():
        sid = "Station:" + r["node_id"]
        add_edge(sid, "ON_LINE", "Line:" + slug(r["노선번호"]))
        add_edge(sid, "OPERATED_BY", "Operator:" + slug(r["운영기관명"]))
        if pd.notna(r["region"]):
            add_edge(sid, "LOCATED_IN", "Region:" + slug(r["region"]))
        add_edge(sid, "IN_METRO_AREA", "MetroArea:" + slug(r["area"]))

    # Line -> Operator (해당 노선 역들의 최빈 운영기관)
    for lnum, g in nodes.groupby("노선번호"):
        add_edge("Line:" + slug(lnum), "LINE_OPERATED_BY",
                 "Operator:" + slug(g["운영기관명"].mode()[0]))

    def num(v):
        try:
            f = float(v)
            return "" if not np.isfinite(f) else f
        except (TypeError, ValueError):
            return ""

    for _, r in edges.iterrows():
        add_edge("Station:" + r["source"], "CONNECTS_TO", "Station:" + r["target"],
                 거리_m=num(r.get("거리_m")), 소요시간_s=num(r.get("소요시간_s")),
                 평일운행횟수=num(r.get("평일운행횟수")))
    for _, r in trans.iterrows():
        add_edge("Station:" + r["source"], "TRANSFERS_TO", "Station:" + r["target"])

    # ---------- 저장 ----------
    pd.DataFrame(rows_n).to_csv(OUT + "kg_nodes.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(rows_e).to_csv(OUT + "kg_edges.csv", index=False, encoding="utf-8-sig")
    nx.write_graphml(G, OUT + "knowledge_graph.graphml")

    # RDF Turtle
    def esc(s):
        return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    with open(OUT + "raility.ttl", "w", encoding="utf-8") as f:
        f.write(f"@prefix : <{NS}> .\n"
                "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
                "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
                "@prefix geo: <http://www.w3.org/2003/01/geo/wgs84_pos#> .\n\n")
        for n, d in G.nodes(data=True):
            iri = ":" + slug(n.replace(":", "_"))
            f.write(f'{iri} a :{d["type"]} ; rdfs:label "{esc(d["label"])}"')
            for k, v in d.items():
                if k in ("type", "label") or v == "":
                    continue
                if k == "lat":
                    f.write(f' ; geo:lat "{v}"^^xsd:double')
                elif k == "lon":
                    f.write(f' ; geo:long "{v}"^^xsd:double')
                elif isinstance(v, (int, float)) and not isinstance(v, bool):
                    f.write(f' ; :{slug(k)} {v}')
                else:
                    f.write(f' ; :{slug(k)} "{esc(v)}"')
            f.write(" .\n")
        for s, o, k, d in G.edges(keys=True, data=True):
            f.write(f'{":" + slug(s.replace(":", "_"))} :{k} '
                    f'{":" + slug(o.replace(":", "_"))} .\n')

    # Neo4j Cypher
    with open(OUT + "kg_import.cypher", "w", encoding="utf-8") as f:
        f.write("// 도시철도 지식그래프 Neo4j 임포트\n")
        for t in ["Station", "Line", "Operator", "Region", "MetroArea"]:
            f.write(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{t}) "
                    f"REQUIRE n.id IS UNIQUE;\n")
        f.write("\n")
        for n, d in G.nodes(data=True):
            props = [f'id:"{esc(n)}"', f'label:"{esc(d["label"])}"']
            for k, v in d.items():
                if k in ("type", "label") or v == "":
                    continue
                props.append(f'{slug(k)}:{v}' if isinstance(v, (int, float))
                             and not isinstance(v, bool) else f'{slug(k)}:"{esc(v)}"')
            f.write(f'MERGE (n:{d["type"]} {{id:"{esc(n)}"}}) SET n += {{{", ".join(props)}}};\n')
        f.write("\n")
        for s, o, k, d in G.edges(keys=True, data=True):
            pr = ", ".join(f"{slug(a)}:{b}" for a, b in d.items()
                           if a != "predicate" and b != "" and isinstance(b, (int, float)))
            pr = f" {{{pr}}}" if pr else ""
            f.write(f'MATCH (a {{id:"{esc(s)}"}}), (b {{id:"{esc(o)}"}}) '
                    f'MERGE (a)-[:{k}{pr}]->(b);\n')

    stats = {
        "총_노드": G.number_of_nodes(), "총_관계": G.number_of_edges(),
        "엔티티_타입별": pd.Series([d["type"] for _, d in G.nodes(data=True)])
                        .value_counts().to_dict(),
        "관계_타입별": pd.Series([k for _, _, k in G.edges(keys=True)])
                      .value_counts().to_dict(),
    }
    json.dump(stats, open(OUT + "_kg_stats.json", "w"), ensure_ascii=False, indent=2)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("\n저장 →", OUT)


if __name__ == "__main__":
    main()
