from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from shapely.geometry import LineString, Point

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
GIS = ROOT / "JORHAT" / "GIS FILE"


def load_distribution_layers() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    node_frames = []
    pipe_frames = []
    dist_root = GIS / "DIST"
    for zone_dir in sorted(dist_root.iterdir()):
        if not zone_dir.is_dir():
            continue
        zone = "".join(ch for ch in zone_dir.name if ch.isdigit())
        node_path = None
        pipe_path = None
        for shp in zone_dir.rglob("*.shp"):
            upper = shp.name.upper()
            if "PIPE" in upper:
                pipe_path = shp
            elif "NODE" in upper or "JUNCTION" in upper:
                node_path = shp
        if not node_path or not pipe_path:
            continue
        ngdf = gpd.read_file(node_path).copy()
        pgdf = gpd.read_file(pipe_path).copy()
        ngdf["zone"] = zone
        pgdf["zone"] = zone
        ngdf["LABEL"] = ngdf["LABEL"].astype(str)
        pgdf["LABEL"] = pgdf["LABEL"].astype(str)
        node_frames.append(ngdf)
        pipe_frames.append(pgdf)
    nodes = gpd.GeoDataFrame(pd.concat(node_frames, ignore_index=True), geometry="geometry")
    pipes = gpd.GeoDataFrame(pd.concat(pipe_frames, ignore_index=True), geometry="geometry")
    return nodes, pipes


def load_analysis_layers() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    node_df = pd.read_csv(RESULTS / "node_pressure.csv")
    pipe_df = pd.read_csv(RESULTS / "pipe_flow.csv")
    inventory = json.loads((RESULTS / "data_inventory.json").read_text(encoding="utf-8"))

    analysis_nodes = node_df.copy()
    analysis_nodes["zone"] = analysis_nodes["node_name"].str.extract(r"^Z(\d+)_")
    analysis_nodes = gpd.GeoDataFrame(
        analysis_nodes,
        geometry=gpd.points_from_xy(analysis_nodes["x"], analysis_nodes["y"]),
    )

    pipe_geoms = {}
    _, source_pipes = load_distribution_layers()
    for row in source_pipes.itertuples(index=False):
        zone = str(row.zone)
        key = (zone, str(row.LABEL))
        pipe_geoms[key] = row.geometry

    pipe_df["zone"] = pipe_df["pipe_name"].str.extract(r"^Z(\d+)_")
    pipe_df["orig_label"] = pipe_df["pipe_name"].str.extract(r"^Z\d+_P_(.+)_\d+$")[0]
    geometries = []
    for row in pipe_df.itertuples(index=False):
        geom = pipe_geoms.get((str(row.zone), str(row.orig_label)))
        if geom is None:
            start = analysis_nodes.loc[analysis_nodes["node_name"] == row.start_node, "geometry"]
            end = analysis_nodes.loc[analysis_nodes["node_name"] == row.end_node, "geometry"]
            if not start.empty and not end.empty:
                geometries.append(LineString([start.iloc[0], end.iloc[0]]))
            else:
                geometries.append(None)
        else:
            geometries.append(geom)
    analysis_pipes = gpd.GeoDataFrame(pipe_df, geometry=geometries)

    tanks = pd.DataFrame(inventory["inventory"]["tanks"])
    tank_gdf = gpd.GeoDataFrame(
        tanks,
        geometry=gpd.points_from_xy(tanks["x"], tanks["y"]),
    ) if not tanks.empty else gpd.GeoDataFrame(columns=["geometry"], geometry="geometry")
    return analysis_nodes, analysis_pipes, tank_gdf


def recommendation_points(analysis_nodes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    recs = [
        ("PT-01", "Z1_J_2", "Zone 1 source outlet"),
        ("PT-02", "Z1_J_335", "Zone 1 low-pressure hotspot"),
        ("PT-03", "Z1_J_340", "Zone 1 low-pressure branch"),
        ("PT-04", "Z1_J_66", "Zone 1 high-demand low-pressure node"),
        ("PT-05", "Z5_J_546", "Zone 5 source outlet"),
        ("PT-06", "Z2_J_2", "Zone 2 source outlet"),
        ("PT-07", "Z6_J_319", "Zone 6 source outlet"),
        ("PT-08", "Z3_J_J_1", "Zone 3 critical trunk"),
        ("PT-09", "Z7_J_95", "Zone 7 source outlet"),
    ]
    rows = []
    for code, node_name, reason in recs:
        match = analysis_nodes.loc[analysis_nodes["node_name"] == node_name]
        if match.empty:
            continue
        row = match.iloc[0]
        rows.append(
            {
                "code": code,
                "node_name": node_name,
                "zone": row["zone"],
                "pressure_m": row["pressure_m"],
                "reason": reason,
                "geometry": row.geometry,
            }
        )
    return gpd.GeoDataFrame(rows, geometry="geometry")


def add_north_arrow(ax, x, y, size):
    ax.annotate(
        "N",
        xy=(x, y),
        xytext=(x, y - size),
        arrowprops=dict(facecolor="black", width=3, headwidth=12),
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
    )


def add_scale_bar(ax, bounds):
    minx, miny, maxx, maxy = bounds
    length = 1000.0
    x0 = minx + 0.03 * (maxx - minx)
    y0 = miny + 0.04 * (maxy - miny)
    ax.plot([x0, x0 + length], [y0, y0], color="black", linewidth=3)
    ax.plot([x0, x0], [y0 - 20, y0 + 20], color="black", linewidth=2)
    ax.plot([x0 + length, x0 + length], [y0 - 20, y0 + 20], color="black", linewidth=2)
    ax.text(x0 + length / 2, y0 + 45, "1 km", ha="center", va="bottom", fontsize=10, fontweight="bold")


def create_map() -> None:
    dist_nodes, dist_pipes = load_distribution_layers()
    analysis_nodes, analysis_pipes, tanks = load_analysis_layers()
    recommendations = recommendation_points(analysis_nodes)

    ward = gpd.read_file(GIS / "Jorhat project area" / "Jorhat project area" / "Ward map.shp")
    zoning = gpd.read_file(GIS / "Jorhat project area" / "Jorhat project area" / "zoning.shp")
    esr = gpd.read_file(GIS / "Jorhat project area" / "Jorhat project area" / "Existing & Proposed ESR.shp")
    mains = gpd.read_file(GIS / "Jorhat project area" / "Jorhat project area" / "RWM_&_CWM.shp")

    low_pressure = analysis_nodes[(analysis_nodes["node_type"] == "Junction") & (analysis_nodes["pressure_m"] < 12)].copy()
    critical = analysis_pipes[analysis_pipes["criticality_score"] >= 0.05].copy()

    fig, ax = plt.subplots(figsize=(22, 18))
    fig.patch.set_facecolor("#f7f5ef")
    ax.set_facecolor("#f7f5ef")

    ward.plot(ax=ax, color="none", edgecolor="#9a9a9a", linewidth=1.2, linestyle="-", alpha=0.85, zorder=1)
    zoning.plot(ax=ax, color="none", edgecolor="#2f5d8a", linewidth=2.0, linestyle="--", alpha=0.9, zorder=2)
    mains.plot(ax=ax, color="#52796f", linewidth=2.2, alpha=0.8, zorder=3)
    dist_pipes.plot(ax=ax, color="#b5b5b5", linewidth=0.5, alpha=0.75, zorder=4)
    dist_nodes.plot(ax=ax, color="#6c757d", markersize=5, alpha=0.45, zorder=5)
    if not tanks.empty:
        tanks.plot(ax=ax, color="#1d4ed8", marker="s", markersize=80, edgecolor="white", linewidth=0.8, zorder=7)
    esr.plot(ax=ax, color="#0f766e", marker="s", markersize=110, edgecolor="black", linewidth=0.7, zorder=8)
    if not low_pressure.empty:
        low_pressure.plot(ax=ax, color="#f59e0b", markersize=20, alpha=0.9, zorder=9)
    if not critical.empty:
        critical.plot(ax=ax, column="criticality_score", cmap="Reds", linewidth=3.5, alpha=0.95, zorder=10)
    recommendations.plot(ax=ax, color="#7c3aed", marker="^", markersize=180, edgecolor="black", linewidth=0.8, zorder=11)

    for row in recommendations.itertuples(index=False):
        ax.annotate(
            f"{row.code}\n{row.node_name}",
            xy=(row.geometry.x, row.geometry.y),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=9,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#7c3aed", alpha=0.9),
            zorder=12,
        )

    for row in esr.itertuples(index=False):
        label = str(row.Layer)
        ax.annotate(
            label,
            xy=(row.geometry.x, row.geometry.y),
            xytext=(5, -8),
            textcoords="offset points",
            fontsize=8,
            color="#0f766e",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#0f766e", alpha=0.75),
            zorder=12,
        )

    for row in zoning.itertuples(index=False):
        centroid = row.geometry.centroid
        ax.text(
            centroid.x,
            centroid.y,
            str(row.Entity),
            fontsize=9,
            color="#1d3557",
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#1d3557", alpha=0.7),
            zorder=6,
        )

    minx, miny, maxx, maxy = dist_pipes.total_bounds
    pad_x = (maxx - minx) * 0.08
    pad_y = (maxy - miny) * 0.08
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)
    ax.set_title(
        "Jorhat Water Network: Critical Pipes, ESR/Tanks, Boundaries and Pressure Transmitter Recommendations",
        fontsize=18,
        fontweight="bold",
        pad=18,
    )
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.grid(color="#d9d9d9", linestyle=":", linewidth=0.6, alpha=0.8)

    add_scale_bar(ax, (minx - pad_x, miny - pad_y, maxx + pad_x, maxy + pad_y))
    add_north_arrow(ax, maxx + pad_x * 0.78, miny + pad_y * 1.9, pad_y * 0.45)

    legend_handles = [
        Patch(facecolor="none", edgecolor="#9a9a9a", label="Ward Boundaries"),
        Patch(facecolor="none", edgecolor="#2f5d8a", linestyle="--", label="Zone Boundaries"),
        Line2D([0], [0], color="#52796f", lw=2.2, label="RWM / CWM Pipelines"),
        Line2D([0], [0], color="#b5b5b5", lw=1.5, label="Distribution Pipes"),
        Line2D([0], [0], color="#d62828", lw=3.5, label="Critical Pipes (score >= 0.05)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#6c757d", markersize=6, label="Distribution Nodes"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#f59e0b", markersize=8, label="Low Pressure Nodes (<12 m)"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#0f766e", markeredgecolor="black", markersize=9, label="Existing / Proposed ESR"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="#1d4ed8", markeredgecolor="white", markersize=8, label="Converted Source Tanks"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor="#7c3aed", markeredgecolor="black", markersize=10, label="Recommended Pressure Transmitters"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", fontsize=10, frameon=True, facecolor="white", framealpha=0.95)

    inset = inset_axes(ax, width="34%", height="34%", loc="lower right", borderpad=2.0)
    inset.set_facecolor("white")
    ward.plot(ax=inset, color="none", edgecolor="#c3c3c3", linewidth=0.8, zorder=1)
    dist_pipes.plot(ax=inset, color="#cfcfcf", linewidth=0.4, alpha=0.7, zorder=2)
    low_pressure.plot(ax=inset, color="#f59e0b", markersize=14, zorder=3)
    recommendations[recommendations["zone"] == "1"].plot(ax=inset, color="#7c3aed", marker="^", markersize=70, edgecolor="black", linewidth=0.5, zorder=4)
    inset.set_title("Zone 1 Low-Pressure Focus", fontsize=10, fontweight="bold")
    z1 = analysis_nodes[analysis_nodes["zone"] == "1"]
    if not z1.empty:
        zx1, zy1, zx2, zy2 = z1.total_bounds
        padx = (zx2 - zx1) * 0.15
        pady = (zy2 - zy1) * 0.15
        inset.set_xlim(zx1 - padx, zx2 + padx)
        inset.set_ylim(zy1 - pady, zy2 + pady)
    inset.set_xticks([])
    inset.set_yticks([])

    out_png = RESULTS / "critical_pipe_comprehensive_map.png"
    out_pdf = RESULTS / "critical_pipe_comprehensive_map.pdf"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)

    recommendations.drop(columns="geometry").to_csv(RESULTS / "pressure_transmitter_recommendations.csv", index=False)


if __name__ == "__main__":
    create_map()
