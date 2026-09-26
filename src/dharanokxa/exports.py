from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import wntr
from matplotlib.backends.backend_pdf import PdfPages

from .catalog import PipeCatalogEntry
from .hydraulics import Simulation, build_model
from .models import DesignRequest, DesignResult
from .reference import load_jorhat_reference
from .roads import load_jorhat_roads


def create_artifacts(result: DesignResult, request: DesignRequest, simulation: Simulation, catalog: dict[str, PipeCatalogEntry]) -> dict[str, str]:
    root = result.output_dir
    folders = {name: root / name for name in ("inputs", "design", "model", "gis", "results", "maps", "reports")}
    for folder in folders.values():
        folder.mkdir(parents=True, exist_ok=True)

    _write_csv(folders["inputs"] / "households.csv", result.households)
    _write_csv(folders["inputs"] / "normalized_households.csv", result.households)
    _write_csv(folders["results"] / "nodes.csv", result.nodes)
    _write_csv(folders["results"] / "pipes.csv", result.pipes)
    (folders["design"] / "optimization_history.json").write_text(json.dumps(result.iterations, indent=2), encoding="utf-8")
    (folders["design"] / "design_basis.json").write_text(json.dumps(_design_basis(request), indent=2), encoding="utf-8")
    (folders["design"] / "run_summary.json").write_text(json.dumps(result.to_dict(), indent=2, default=str), encoding="utf-8")

    for name, rows, geom in (
        ("households", result.households, "Point"), ("nodes", result.nodes, "Point"), ("pipes", result.pipes, "LineString")
    ):
        (folders["gis"] / f"{name}.geojson").write_text(json.dumps(_geojson(name, rows, geom, request, result.nodes), indent=2), encoding="utf-8")

    model = build_model(request, result.nodes, result.pipes, catalog)
    inp_path = folders["model"] / "scheme.inp"
    wntr.network.write_inpfile(model, str(inp_path), units="LPS", version=2.2)

    xlsx_path = folders["results"] / "hydraulic_results.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        pd.DataFrame(result.nodes).to_excel(writer, sheet_name="Nodes", index=False)
        pd.DataFrame(result.pipes).to_excel(writer, sheet_name="Pipes", index=False)
        pd.DataFrame(result.iterations).to_excel(writer, sheet_name="Optimization", index=False)

    map_png = folders["maps"] / "standard_map.png"
    map_jpg = folders["maps"] / "standard_map.jpg"
    map_pdf = folders["maps"] / "standard_map.pdf"
    fig = _network_figure(result, request)
    fig.savefig(map_png, dpi=180, bbox_inches="tight")
    fig.savefig(map_jpg, dpi=180, bbox_inches="tight")
    fig.savefig(map_pdf, bbox_inches="tight")
    plt.close(fig)
    report_path = folders["reports"] / "Hydraulic_Design_Report.pdf"
    _report(report_path, result, request)

    manifest = {str(path.relative_to(root)).replace("\\", "/"): _size(path) for path in root.rglob("*") if path.is_file()}
    (root / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    zip_path = shutil.make_archive(str(root), "zip", root.parent, root.name)
    return {"design_package": zip_path, "report": str(report_path), "epanet_inp": str(inp_path), "map": str(map_png)}


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _design_basis(request: DesignRequest) -> dict:
    profile = request.profile
    reference = load_jorhat_reference()
    roads = load_jorhat_roads()
    return {
        "status": "DEMONSTRATION / SYNTHETIC DATA",
        "profile": profile.name,
        "geometry_reference": {
            "source": "Preserved local Jorhat GIS and EPANET aggregate statistics",
            "profile": reference.to_dict(),
            "use": "Reference-informed synthetic topology and segment lengths; source coordinates are not copied",
        },
        "road_corridor_reference": {
            "profile": roads.to_dict(),
            "alignment_rule": "Straight pipe segments between named road intersections",
            "crossing_rule": "Road boring only at approved crossing records",
            "parallel_side_rule": "Left and right roadside runs are modeled separately",
        },
        "parameters": [
            {"parameter": "Domestic demand", "value": profile.domestic_lpcd, "unit": "L/person/day", "source": "Supplied project brief", "confidence": "ASSUMED"},
            {"parameter": "Demand uplift", "value": profile.demand_uplift, "unit": "fraction", "source": "Supplied project brief", "confidence": "ASSUMED"},
            {"parameter": "Effective quantity", "value": profile.effective_lpcd, "unit": "L/person/day", "source": "55 × 1.15", "confidence": "DERIVED"},
            {"parameter": "Hard minimum endpoint pressure", "value": profile.hard_min_pressure_m, "unit": "m", "operator": ">", "source": "Supplied project brief", "confidence": "ASSUMED"},
            {"parameter": "Optimization target", "value": profile.target_pressure_m, "unit": "m", "operator": ">=", "source": "Hard minimum + configured margin", "confidence": "DERIVED"},
            {"parameter": "Synthetic source head", "value": request.source_head_m, "unit": "m", "source": "Offline demo fixture", "confidence": "SYNTHETIC"},
        ],
    }


def _geojson(name: str, rows: list[dict], geometry_type: str, request: DesignRequest, nodes: list[dict]) -> dict:
    locations = {"ESR": [request.source_longitude, request.source_latitude]}
    locations.update({n["node_id"]: [n["longitude"], n["latitude"]] for n in nodes})
    features = []
    for row in rows:
        props = dict(row)
        if geometry_type == "Point":
            coords = [row["longitude"], row["latitude"]]
        else:
            coords = [locations[row["from_node"]], locations[row["to_node"]]]
        features.append({"type": "Feature", "properties": props, "geometry": {"type": geometry_type, "coordinates": coords}})
    return {"type": "FeatureCollection", "name": name, "features": features}


def _network_figure(result: DesignResult, request: DesignRequest):
    fig, ax = plt.subplots(figsize=(9, 11))
    locations = {"ESR": (request.source_longitude, request.source_latitude)}
    locations.update({n["node_id"]: (n["longitude"], n["latitude"]) for n in result.nodes})
    widths = sorted({p["internal_diameter_mm"] for p in result.pipes})
    for pipe in result.pipes:
        a, b = locations[pipe["from_node"]], locations[pipe["to_node"]]
        width = 1.2 + 3.0 * widths.index(pipe["internal_diameter_mm"]) / max(len(widths) - 1, 1)
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#147d86", linewidth=width, zorder=2)
    ax.scatter([h["longitude"] for h in result.households], [h["latitude"] for h in result.households], s=7, color="#69747a", alpha=.65, label="Households")
    ax.scatter([request.source_longitude], [request.source_latitude], marker="s", s=100, color="#17324d", label="ESR", zorder=5)
    critical = next(n for n in result.nodes if n["node_id"] == result.summary["critical_endpoint_id"])
    ax.scatter([critical["longitude"]], [critical["latitude"]], marker="*", s=180, color="#c33d3d", label="Critical endpoint", zorder=6)
    ax.set_title(f"DharaNokxa — {result.scheme_name}\nDEMONSTRATION / SYNTHETIC DATA")
    ax.set_xlabel("Longitude (WGS 84)")
    ax.set_ylabel("Latitude (WGS 84)")
    ax.grid(alpha=.15)
    ax.legend(loc="best")
    ax.text(.02, .02, "N ↑   Pressure target ≥ 8 m   Preliminary candidate", transform=ax.transAxes, fontsize=8)
    return fig


def _report(path: Path, result: DesignResult, request: DesignRequest) -> None:
    with PdfPages(path) as pdf:
        fig = _network_figure(result, request)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(8.27, 11.69))
        ax.axis("off")
        lines = [
            "HYDRAULIC DESIGN REPORT", "DEMONSTRATION / SYNTHETIC DATA", "",
            f"Scheme: {result.scheme_name}", f"Run: {result.run_id}", f"Hydraulic status: {result.status}", "",
            f"Households: {result.summary['households']}", f"Population: {result.summary['population']}",
            f"Design demand: {result.summary['design_demand_lps']:.3f} L/s",
            f"Total pipe length: {result.summary['total_pipe_length_m']:.1f} m", "",
            f"Minimum endpoint pressure: {result.summary['minimum_endpoint_pressure_m']:.3f} m",
            f"Critical endpoint: {result.summary['critical_endpoint_id']}",
            f"Hard minimum: > {request.profile.hard_min_pressure_m:.2f} m",
            f"Optimization target: ≥ {request.profile.target_pressure_m:.2f} m",
            f"Achieved hard-minimum margin: {result.summary['achieved_pressure_margin_m']:.3f} m", "",
            "This candidate uses synthetic terrain, roads, population, source head, and a demonstration HDPE catalog.",
            "It is not a surveyed construction design or procurement schedule and awaits engineering review.",
        ]
        ax.text(.08, .94, "\n".join(lines), va="top", fontsize=11, linespacing=1.5)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def _size(path: Path) -> int:
    return path.stat().st_size
