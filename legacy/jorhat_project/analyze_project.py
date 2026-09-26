from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import wntr

matplotlib.use("Agg")


ROOT = Path(__file__).resolve().parent
GIS_ROOT = ROOT / "JORHAT" / "GIS FILE"
DIST_ROOT = GIS_ROOT / "DIST"
DESIGN_ROOT = ROOT / "JORHAT DESIGN FILE"
MODELS_DIR = ROOT / "models" / "inp_files"
RESULTS_DIR = ROOT / "results"


@dataclass
class ZoneSource:
    zone: str
    tank_label: str
    wntr_name: str
    head_m: float
    elevation_m: float
    init_level_m: float
    x: float
    y: float
    inferred_from: str


def ensure_dirs() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def safe_id(raw: object) -> str:
    text = str(raw).strip()
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
    return text.strip("_") or "NA"


def zone_code(path: Path) -> str:
    match = re.search(r"(\d+)", path.name)
    return match.group(1) if match else safe_id(path.name)


def list_data_sources() -> dict:
    tracked = [".shp", ".geojson", ".gpkg", ".inp", ".tif", ".tiff", ".asc", ".dem", ".xlsx", ".sqlite"]
    files = []
    for ext in tracked:
        for file in ROOT.rglob(f"*{ext}"):
            if "venv" in file.parts:
                continue
            if file.name.lower() == "temp.inp":
                continue
            files.append(
                {
                    "path": str(file.relative_to(ROOT)),
                    "extension": ext,
                    "parent": str(file.parent.relative_to(ROOT)),
                }
            )
    return {
        "files": sorted(files, key=lambda item: item["path"]),
        "counts_by_extension": pd.DataFrame(files)["extension"].value_counts().sort_index().to_dict() if files else {},
    }


def inventory_project_area_layers() -> dict:
    inventory: dict[str, list[dict]] = {"gis_layers": [], "esr_points": []}
    for shp in sorted(GIS_ROOT.rglob("*.shp")):
        if "DIST" in shp.parts:
            continue
        gdf = gpd.read_file(shp)
        inventory["gis_layers"].append(
            {
                "path": str(shp.relative_to(ROOT)),
                "rows": int(len(gdf)),
                "geometry_types": sorted({str(geom) for geom in gdf.geom_type}),
                "columns": list(gdf.columns),
            }
        )
        if shp.name.lower() == "existing & proposed esr.shp":
            subset = gdf[["Layer", "Elevation", "RefName"]].copy()
            subset = subset.fillna("")
            inventory["esr_points"] = subset.to_dict(orient="records")
    return inventory


def sqlite_counts(sqlite_path: Path) -> dict[str, int]:
    targets = [
        "IdahoJunction",
        "IdahoPipe",
        "IdahoReservoir",
        "IdahoTank",
        "ConventionalTank",
        "StandardPump",
        "IdahoPumpStation",
        "PRV",
        "PSV",
        "FCV",
        "TCV",
        "GPV",
        "PBV",
        "PressureValve",
    ]
    conn = sqlite3.connect(str(sqlite_path))
    cur = conn.cursor()
    counts: dict[str, int] = {}
    for table in targets:
        try:
            counts[table] = int(cur.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0])
        except sqlite3.DatabaseError:
            continue
    conn.close()
    return counts


def inventory_design_sources() -> list[dict]:
    items = []
    for path in sorted(DESIGN_ROOT.rglob("*")):
        if path.is_dir():
            continue
        if path.suffix.lower() not in {".xlsx", ".sqlite"}:
            continue
        item = {"path": str(path.relative_to(ROOT)), "type": path.suffix.lower()}
        if path.suffix.lower() == ".sqlite":
            item["counts"] = sqlite_counts(path)
        items.append(item)
    return items


def load_zone_layers() -> list[tuple[Path, Path, str]]:
    layers = []
    for zone_dir in sorted(DIST_ROOT.iterdir()):
        if not zone_dir.is_dir():
            continue
        node_shp = None
        pipe_shp = None
        for shp in zone_dir.rglob("*.shp"):
            upper = shp.name.upper()
            if "PIPE" in upper:
                pipe_shp = shp
            elif "NODE" in upper or "JUNCTION" in upper:
                node_shp = shp
        if node_shp and pipe_shp:
            layers.append((node_shp, pipe_shp, zone_code(zone_dir)))
    return layers


def source_endpoint_coords(geom, missing_at_start: bool) -> tuple[float, float]:
    coords = list(geom.coords)
    point = coords[0] if missing_at_start else coords[-1]
    return float(point[0]), float(point[1])


def build_model() -> tuple[wntr.network.WaterNetworkModel, dict, list[dict]]:
    wn = wntr.network.WaterNetworkModel()
    wn.options.time.duration = 0
    wn.options.time.hydraulic_timestep = 3600
    wn.options.time.report_timestep = 3600
    wn.options.hydraulic.headloss = "H-W"
    wn.options.hydraulic.demand_model = "PDD"
    wn.options.hydraulic.required_pressure = 15.0
    wn.options.hydraulic.minimum_pressure = 0.0
    wn.options.hydraulic.pressure_exponent = 0.5
    wn.options.hydraulic.inpfile_units = "LPS"

    inventory = {
        "nodes": [],
        "pipes": [],
        "tanks": [],
        "reservoirs": [],
        "pumps": [],
        "valves": [],
        "elevations": [],
    }
    assumptions: list[dict] = []

    for node_path, pipe_path, zone in load_zone_layers():
        nodes_gdf = gpd.read_file(node_path)
        pipes_gdf = gpd.read_file(pipe_path)
        nodes_gdf["LABEL"] = nodes_gdf["LABEL"].astype(str)
        pipes_gdf["START_NODE"] = pipes_gdf["START_NODE"].astype(str)
        pipes_gdf["STOP_NODE"] = pipes_gdf["STOP_NODE"].astype(str)

        node_map: dict[str, str] = {}
        hgl_map: dict[str, float] = {}
        elev_map: dict[str, float] = {}

        for row in nodes_gdf.itertuples(index=False):
            label = str(row.LABEL)
            node_name = f"Z{zone}_J_{safe_id(label)}"
            demand_m3s = max(float(row.DEMAND or 0.0), 0.0) / 1000.0
            elevation_m = float(row.ELEV or 0.0)
            x = float(row.geometry.x)
            y = float(row.geometry.y)
            wn.add_junction(node_name, base_demand=demand_m3s, demand_pattern=None, elevation=elevation_m)
            wn.get_node(node_name).coordinates = (x, y)
            node_map[label] = node_name
            hgl_map[label] = float(row.HGL or elevation_m)
            elev_map[label] = elevation_m
            inventory["nodes"].append(
                {
                    "zone": zone,
                    "node_name": node_name,
                    "original_label": label,
                    "demand_lps": float(row.DEMAND or 0.0),
                    "elevation_m": elevation_m,
                    "hgl_m": float(row.HGL or elevation_m),
                    "pressure_m": float(row.P or 0.0),
                    "x": x,
                    "y": y,
                }
            )
            inventory["elevations"].append(
                {
                    "zone": zone,
                    "node_name": node_name,
                    "elevation_m": elevation_m,
                    "source": str(node_path.relative_to(ROOT)),
                }
            )

        pipe_endpoints = set(pipes_gdf["START_NODE"]) | set(pipes_gdf["STOP_NODE"])
        missing_labels = sorted(pipe_endpoints - set(node_map))
        source_map: dict[str, ZoneSource] = {}

        for missing_label in missing_labels:
            linked = pipes_gdf[(pipes_gdf["START_NODE"] == missing_label) | (pipes_gdf["STOP_NODE"] == missing_label)].copy()
            coords: list[tuple[float, float]] = []
            neighbor_hgl: list[float] = []
            neighbor_labels: list[str] = []
            neighbor_elev: list[float] = []
            for prow in linked.itertuples(index=False):
                missing_at_start = str(prow.START_NODE) == missing_label
                coords.append(source_endpoint_coords(prow.geometry, missing_at_start))
                neighbor = str(prow.STOP_NODE if missing_at_start else prow.START_NODE)
                if neighbor in hgl_map:
                    neighbor_hgl.append(hgl_map[neighbor])
                    neighbor_elev.append(elev_map[neighbor])
                    neighbor_labels.append(neighbor)
            avg_x = sum(x for x, _ in coords) / len(coords)
            avg_y = sum(y for _, y in coords) / len(coords)
            source_head = sum(neighbor_hgl) / len(neighbor_hgl)
            source_elev = max(sum(neighbor_elev) / len(neighbor_elev), source_head - 10.0)
            init_level = max(source_head - source_elev, 0.1)
            tank_name = f"Z{zone}_T_{safe_id(missing_label)}"
            wn.add_tank(
                tank_name,
                elevation=source_elev,
                init_level=init_level,
                min_level=max(init_level - 5.0, 0.0),
                max_level=init_level + 10.0,
                diameter=10.0,
                min_vol=0.0,
            )
            wn.get_node(tank_name).coordinates = (avg_x, avg_y)
            source_map[missing_label] = ZoneSource(
                zone=zone,
                tank_label=missing_label,
                wntr_name=tank_name,
                head_m=source_head,
                elevation_m=source_elev,
                init_level_m=init_level,
                x=avg_x,
                y=avg_y,
                inferred_from=", ".join(sorted(set(neighbor_labels))),
            )
            inventory["tanks"].append(
                {
                    "zone": zone,
                    "tank_name": tank_name,
                    "original_label": missing_label,
                    "inferred_head_m": source_head,
                    "elevation_m": source_elev,
                    "init_level_m": init_level,
                    "diameter_m": 10.0,
                    "x": avg_x,
                    "y": avg_y,
                    "inferred_from_nodes": ", ".join(sorted(set(neighbor_labels))),
                }
            )
            assumptions.append(
                {
                    "zone": zone,
                    "category": "tank_source",
                    "attribute": missing_label,
                    "assumption": "Created a tank at the missing GIS endpoint and inferred its operating head from adjacent junction HGL values.",
                    "details": f"Connected junctions: {', '.join(sorted(set(neighbor_labels)))}",
                }
            )

        for row in pipes_gdf.itertuples(index=False):
            start_label = str(row.START_NODE)
            stop_label = str(row.STOP_NODE)
            start_name = node_map.get(start_label) or source_map[start_label].wntr_name
            stop_name = node_map.get(stop_label) or source_map[stop_label].wntr_name
            pipe_name = f"Z{zone}_P_{safe_id(row.LABEL)}_{int(row.ID)}"
            length_m = float(row.USER_L or row.L or 0.0)
            if length_m <= 0.0:
                length_m = float(row.geometry.length)
            diameter_m = max(float(row.D or 0.0) / 1000.0, 0.001)
            roughness = float(row.C or 130.0)
            wn.add_pipe(
                pipe_name,
                start_name,
                stop_name,
                length=length_m,
                diameter=diameter_m,
                roughness=roughness,
                minor_loss=0.0,
                initial_status="OPEN",
            )
            inventory["pipes"].append(
                {
                    "zone": zone,
                    "pipe_name": pipe_name,
                    "original_label": str(row.LABEL),
                    "start_node": start_name,
                    "end_node": stop_name,
                    "length_m": length_m,
                    "diameter_mm": float(row.D or 0.0),
                    "roughness": roughness,
                    "material": str(row.MATERIAL or ""),
                    "design_flow_lps": float(row.Q or 0.0),
                }
            )

    design_sources = inventory_design_sources()
    for source in design_sources:
        if source["type"] != ".sqlite":
            continue
        counts = source.get("counts", {})
        if counts.get("IdahoReservoir", 0):
            inventory["reservoirs"].append({"path": source["path"], "count": counts["IdahoReservoir"]})
        if counts.get("StandardPump", 0) or counts.get("IdahoPumpStation", 0):
            inventory["pumps"].append({"path": source["path"], "count": counts.get("StandardPump", 0) + counts.get("IdahoPumpStation", 0)})
        valve_count = sum(counts.get(name, 0) for name in ["PRV", "PSV", "FCV", "TCV", "GPV", "PBV", "PressureValve"])
        if valve_count:
            inventory["valves"].append({"path": source["path"], "count": valve_count})

    return wn, inventory, assumptions


def run_simulation(inp_path: Path) -> tuple[wntr.network.WaterNetworkModel, object]:
    model = wntr.network.WaterNetworkModel(str(inp_path))
    try:
        results = wntr.sim.EpanetSimulator(model).run_sim()
    except Exception:
        results = wntr.sim.WNTRSimulator(model).run_sim()
    return model, results


def build_multigraph(wn: wntr.network.WaterNetworkModel) -> nx.MultiGraph:
    graph = nx.MultiGraph()
    for node_name, node in wn.nodes():
        graph.add_node(node_name, node_type=node.node_type)
    for link_name, link in wn.pipes():
        graph.add_edge(link.start_node_name, link.end_node_name, key=link_name, link_name=link_name)
    return graph


def compute_pipe_criticality(wn: wntr.network.WaterNetworkModel) -> pd.DataFrame:
    graph = build_multigraph(wn)
    demand_map = {
        name: max(float(getattr(node, "base_demand", 0.0) or 0.0), 0.0)
        for name, node in wn.junctions()
    }
    total_demand = sum(demand_map.values()) or 1.0
    sources = [name for name, _ in wn.tanks()] + [name for name, _ in wn.reservoirs()]
    records = []
    for link_name, link in wn.pipes():
        test_graph = graph.copy()
        if test_graph.has_edge(link.start_node_name, link.end_node_name, key=link_name):
            test_graph.remove_edge(link.start_node_name, link.end_node_name, key=link_name)
        reachable = set()
        collapsed = nx.Graph(test_graph)
        for source in sources:
            if source in collapsed:
                reachable.update(nx.node_connected_component(collapsed, source))
        disconnected_demand = sum(demand for node, demand in demand_map.items() if node not in reachable)
        score = disconnected_demand / total_demand
        records.append(
            {
                "pipe_name": link_name,
                "start_node": link.start_node_name,
                "end_node": link.end_node_name,
                "criticality_score": score,
                "disconnected_demand_m3s": disconnected_demand,
            }
        )
    return pd.DataFrame(records).sort_values(["criticality_score", "pipe_name"], ascending=[False, True])


def compute_supply_redundancy(wn: wntr.network.WaterNetworkModel) -> float:
    graph = nx.Graph(build_multigraph(wn))
    super_source = "__super_source__"
    graph.add_node(super_source)
    sources = [name for name, _ in wn.tanks()] + [name for name, _ in wn.reservoirs()]
    for source in sources:
        graph.add_edge(super_source, source)
    values = []
    for node_name, _ in wn.junctions():
        try:
            values.append(nx.edge_connectivity(graph, super_source, node_name))
        except nx.NetworkXError:
            values.append(0)
    return float(sum(values) / len(values)) if values else 0.0


def save_plots(wn: wntr.network.WaterNetworkModel, node_results: pd.DataFrame, pipe_results: pd.DataFrame, criticality: pd.DataFrame) -> None:
    node_pressure = node_results.set_index("node_name")["pressure_m"]
    pipe_flow = pipe_results.set_index("pipe_name")["flow_lps"]
    critical_attr = criticality.set_index("pipe_name")["criticality_score"]

    fig, ax = plt.subplots(figsize=(14, 10))
    wntr.graphics.plot_network(wn, node_attribute=node_pressure.to_dict(), node_size=18, link_width=1.2, title="Pressure Map", ax=ax, show_plot=False)
    fig.savefig(RESULTS_DIR / "pressure_map.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(14, 10))
    wntr.graphics.plot_network(wn, link_attribute=pipe_flow.to_dict(), node_size=8, link_width=2.0, title="Pipe Flow Map", ax=ax, show_plot=False)
    fig.savefig(RESULTS_DIR / "pipe_flow_map.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(14, 10))
    wntr.graphics.plot_network(wn, link_attribute=critical_attr.to_dict(), node_size=8, link_width=2.5, title="Critical Pipes", ax=ax, show_plot=False)
    fig.savefig(RESULTS_DIR / "critical_pipes.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def write_outputs(
    wn: wntr.network.WaterNetworkModel,
    results,
    inventory: dict,
    assumptions: list[dict],
    project_layers: dict,
    data_sources: dict,
) -> None:
    pressure = results.node["pressure"].iloc[-1]
    head = results.node["head"].iloc[-1]
    demand = results.node["demand"].iloc[-1]
    flow = results.link["flowrate"].iloc[-1]
    velocity = results.link["velocity"].iloc[-1] if "velocity" in results.link else pd.Series(0.0, index=flow.index)
    if "headloss" in results.link:
        headloss = results.link["headloss"].iloc[-1]
    else:
        headloss = pd.Series(0.0, index=flow.index)

    node_records = []
    for node_name, node in wn.nodes():
        node_records.append(
            {
                "node_name": node_name,
                "node_type": node.node_type,
                "pressure_m": float(pressure.get(node_name, 0.0)),
                "head_m": float(head.get(node_name, 0.0)),
                "demand_lps": float(demand.get(node_name, 0.0) * 1000.0),
                "expected_demand_lps": float(getattr(node, "base_demand", 0.0) * 1000.0 if node.node_type == "Junction" else 0.0),
                "elevation_m": float(getattr(node, "elevation", 0.0)),
                "x": float(node.coordinates[0]) if node.coordinates else math.nan,
                "y": float(node.coordinates[1]) if node.coordinates else math.nan,
            }
        )
    node_df = pd.DataFrame(node_records).sort_values("node_name")

    pipe_records = []
    for pipe_name, pipe in wn.pipes():
        pipe_records.append(
            {
                "pipe_name": pipe_name,
                "start_node": pipe.start_node_name,
                "end_node": pipe.end_node_name,
                "flow_lps": float(flow.get(pipe_name, 0.0) * 1000.0),
                "velocity_mps": float(velocity.get(pipe_name, 0.0)),
                "headloss": float(headloss.get(pipe_name, 0.0)),
                "length_m": float(pipe.length),
                "diameter_mm": float(pipe.diameter * 1000.0),
                "roughness": float(pipe.roughness),
            }
        )
    pipe_df = pd.DataFrame(pipe_records).sort_values("pipe_name")

    criticality_df = compute_pipe_criticality(wn)
    pipe_df = pipe_df.merge(criticality_df[["pipe_name", "criticality_score"]], on="pipe_name", how="left")

    expected_total = node_df.loc[node_df["node_type"] == "Junction", "expected_demand_lps"].sum()
    delivered_total = node_df.loc[node_df["node_type"] == "Junction", "demand_lps"].clip(lower=0.0).sum()
    network_reliability = delivered_total / expected_total if expected_total else 0.0
    pressure_deficiency = (wn.options.hydraulic.required_pressure - node_df.loc[node_df["node_type"] == "Junction", "pressure_m"]).clip(lower=0.0).sum()
    supply_redundancy = compute_supply_redundancy(wn)
    max_criticality = float(criticality_df["criticality_score"].max()) if not criticality_df.empty else 0.0
    avg_criticality = float(criticality_df["criticality_score"].mean()) if not criticality_df.empty else 0.0

    metrics_df = pd.DataFrame(
        [
            {"metric": "network_reliability", "value": network_reliability, "definition": "Delivered demand / expected demand under PDD steady-state simulation."},
            {"metric": "pressure_deficiency", "value": pressure_deficiency, "definition": "Sum of junction deficits below required pressure of 15 m."},
            {"metric": "pipe_criticality_max", "value": max_criticality, "definition": "Maximum fraction of total demand disconnected by removing a single pipe."},
            {"metric": "pipe_criticality_mean", "value": avg_criticality, "definition": "Average fraction of total demand disconnected by removing each pipe individually."},
            {"metric": "supply_redundancy", "value": supply_redundancy, "definition": "Average edge connectivity from each junction to the set of source nodes."},
        ]
    )

    hydraulic_results = pd.DataFrame(
        [
            {
                "junction_count": sum(1 for _ in wn.junctions()),
                "tank_count": sum(1 for _ in wn.tanks()),
                "reservoir_count": sum(1 for _ in wn.reservoirs()),
                "pipe_count": sum(1 for _ in wn.pipes()),
                "expected_demand_lps": expected_total,
                "delivered_demand_lps": delivered_total,
                "min_pressure_m": node_df.loc[node_df["node_type"] == "Junction", "pressure_m"].min(),
                "max_pressure_m": node_df.loc[node_df["node_type"] == "Junction", "pressure_m"].max(),
                "min_flow_lps": pipe_df["flow_lps"].min(),
                "max_flow_lps": pipe_df["flow_lps"].max(),
                "total_headloss": pipe_df["headloss"].sum(),
            }
        ]
    )

    node_df.to_csv(RESULTS_DIR / "node_pressure.csv", index=False)
    pipe_df.to_csv(RESULTS_DIR / "pipe_flow.csv", index=False)
    hydraulic_results.to_csv(RESULTS_DIR / "hydraulic_results.csv", index=False)
    metrics_df.to_csv(RESULTS_DIR / "network_metrics.csv", index=False)

    inventory_payload = {
        "data_sources": data_sources,
        "project_layers": project_layers,
        "inventory": inventory,
        "assumptions": assumptions,
    }
    (RESULTS_DIR / "data_inventory.json").write_text(json.dumps(inventory_payload, indent=2), encoding="utf-8")
    inventory_summary = pd.DataFrame(
        [
            {"category": "nodes", "count": len(inventory["nodes"])},
            {"category": "pipes", "count": len(inventory["pipes"])},
            {"category": "tanks", "count": len(inventory["tanks"])},
            {"category": "reservoir_design_sources", "count": sum(item["count"] for item in inventory["reservoirs"])},
            {"category": "pump_design_sources", "count": sum(item["count"] for item in inventory["pumps"])},
            {"category": "valve_design_sources", "count": sum(item["count"] for item in inventory["valves"])},
            {"category": "elevation_records", "count": len(inventory["elevations"])},
        ]
    )
    inventory_summary.to_csv(RESULTS_DIR / "data_inventory_summary.csv", index=False)
    pd.DataFrame(data_sources["files"]).to_csv(RESULTS_DIR / "data_sources.csv", index=False)

    template_rows = [
        {
            "category": "reservoir",
            "attribute": "Explicit reservoir location and operating head",
            "required_for": "Integrating clear-water-main reservoirs into the converted EPANET distribution model",
            "status": "missing_in_gis_conversion",
            "notes": "Reservoirs exist in WaterGEMS SQLite files, but direct geometry/topology for merge into the GIS network was not available in the shapefiles.",
        },
        {
            "category": "tank",
            "attribute": "Tank operating levels and diameter",
            "required_for": "Replacing inferred source tanks with verified asset parameters",
            "status": "inferred_defaults_used",
            "notes": "Tank nodes were inferred from missing pipe endpoints; a 10 m diameter and HGL-based operating levels were used for conversion.",
        },
        {
            "category": "pumps_valves",
            "attribute": "Pump/valve geometry and connectivity in GIS or EPANET form",
            "required_for": "Adding active controls to the converted model",
            "status": "not_found_in_distribution_gis",
            "notes": "WaterGEMS databases can contain these elements, but no distribution GIS layers exposed them for direct conversion.",
        },
    ]
    pd.DataFrame(template_rows).to_csv(RESULTS_DIR / "data_template.csv", index=False)

    save_plots(wn, node_df, pipe_df, criticality_df)


def main() -> None:
    ensure_dirs()
    data_sources = list_data_sources()
    project_layers = inventory_project_area_layers()
    wn, inventory, assumptions = build_model()
    inp_path = MODELS_DIR / "jorhat_combined_distribution.inp"
    wntr.network.write_inpfile(wn, str(inp_path))
    loaded_wn, results = run_simulation(inp_path)
    write_outputs(loaded_wn, results, inventory, assumptions, project_layers, data_sources)
    temp_inp = ROOT / "temp.inp"
    if temp_inp.exists():
        temp_inp.unlink()
    print(f"INP: {inp_path}")
    print(f"Results: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
