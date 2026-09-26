from __future__ import annotations

"""Reference-derived geometry statistics from the preserved Jorhat project.

This adapter reads local Jorhat GIS/EPANET files when they are present. It returns
aggregated, non-identifying design characteristics; it never copies source
coordinates or source project files into a generated scheme or public artifact.
"""

from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Any


@dataclass(frozen=True)
class NetworkReferenceProfile:
    source: str
    zone_count: int
    source_node_count: int
    source_pipe_count: int
    connected_components: int
    leaf_fraction: float
    degree_two_fraction: float
    degree_three_fraction: float
    degree_four_fraction: float
    median_pipe_length_m: float
    p90_pipe_length_m: float
    maximum_pipe_length_m: float
    total_pipe_length_m: float
    median_turn_angle_deg: float
    p90_turn_angle_deg: float
    diameter_counts_mm: dict[str, int]
    materials: dict[str, int]
    epanet_junction_count: int
    epanet_pipe_count: int
    epanet_tank_count: int
    epanet_median_pipe_length_m: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


FALLBACK = NetworkReferenceProfile(
    source="Jorhat reference-derived aggregate snapshot (offline fallback)",
    zone_count=6, source_node_count=2227, source_pipe_count=2247,
    connected_components=1, leaf_fraction=0.43, degree_two_fraction=0.02,
    degree_three_fraction=0.45, degree_four_fraction=0.01,
    median_pipe_length_m=54.0, p90_pipe_length_m=184.0,
    maximum_pipe_length_m=1227.0, total_pipe_length_m=183427.0,
    median_turn_angle_deg=99.0, p90_turn_angle_deg=179.0,
    diameter_counts_mm={"92": 1675, "100": 144, "135": 3, "150": 182, "200": 114, "250": 58, "300": 47, "350": 24},
    materials={"HDPE PN-6": 0, "DI-K7": 0},
    epanet_junction_count=2221, epanet_pipe_count=2247, epanet_tank_count=6,
    epanet_median_pipe_length_m=54.0,
)


@lru_cache(maxsize=4)
def load_jorhat_reference(root: str | None = None) -> NetworkReferenceProfile:
    project_root = Path(root) if root else Path(__file__).resolve().parents[2] / "legacy" / "jorhat_project"
    dist_root = project_root / "JORHAT" / "GIS FILE" / "DIST"
    inp_path = project_root / "models" / "inp_files" / "jorhat_combined_distribution.inp"
    if not dist_root.exists():
        return FALLBACK
    try:
        import geopandas as gpd
        import networkx as nx
        import wntr
    except ImportError:
        return FALLBACK

    length_values: list[float] = []
    angle_values: list[float] = []
    diameter_counts: dict[str, int] = {}
    materials: dict[str, int] = {}
    total_nodes = total_pipes = 0
    components = 0
    degree_counts: dict[int, int] = {}
    zone_count = 0
    for zone in sorted(path for path in dist_root.iterdir() if path.is_dir()):
        shapes = list(zone.rglob("*.shp"))
        node_path = next((p for p in shapes if "NODE" in p.name.upper() or "JUNCTION" in p.name.upper()), None)
        pipe_path = next((p for p in shapes if "PIPE" in p.name.upper()), None)
        if not node_path or not pipe_path:
            continue
        nodes = gpd.read_file(node_path)
        pipes = gpd.read_file(pipe_path)
        zone_count += 1
        total_nodes += len(nodes)
        total_pipes += len(pipes)
        length_values.extend(float(x) for x in pipes.geometry.length if x and x > 0)
        graph = nx.Graph()
        starts = pipes["START_NODE"].astype(str)
        stops = pipes["STOP_NODE"].astype(str)
        graph.add_edges_from(zip(starts, stops))
        components += nx.number_connected_components(graph)
        for _, degree in graph.degree():
            degree_counts[degree] = degree_counts.get(degree, 0) + 1
        for _, row in pipes.iterrows():
            if row.geometry is None or len(row.geometry.coords) < 2:
                continue
            start, end = row.geometry.coords[0], row.geometry.coords[-1]
            if row.get("START_NODE") is not None:
                pass
            diameter = row.get("D")
            if diameter is not None:
                key = str(int(round(float(diameter))))
                diameter_counts[key] = diameter_counts.get(key, 0) + 1
            material = str(row.get("MATERIAL") or "UNKNOWN")
            materials[material] = materials.get(material, 0) + 1
        # Angle values are calculated only where a node has multiple incident pipes.
        for node_id in graph.nodes:
            vectors = []
            incident = pipes[(starts == node_id) | (stops == node_id)]
            for _, row in incident.iterrows():
                coords = list(row.geometry.coords)
                a, b = coords[0], coords[-1]
                vector = (b[0] - a[0], b[1] - a[1]) if str(row["START_NODE"]) == node_id else (a[0] - b[0], a[1] - b[1])
                norm = (vector[0] ** 2 + vector[1] ** 2) ** 0.5
                if norm:
                    vectors.append((vector[0] / norm, vector[1] / norm))
            for i, first in enumerate(vectors):
                for second in vectors[i + 1:]:
                    dot = max(-1.0, min(1.0, first[0] * second[0] + first[1] * second[1]))
                    import math
                    angle_values.append(math.degrees(math.acos(dot)))
    if not length_values or not total_pipes:
        return FALLBACK
    degree_total = sum(degree_counts.values()) or 1
    profile = NetworkReferenceProfile(
        source=str(project_root), zone_count=zone_count, source_node_count=total_nodes,
        source_pipe_count=total_pipes, connected_components=components,
        leaf_fraction=degree_counts.get(1, 0) / degree_total,
        degree_two_fraction=degree_counts.get(2, 0) / degree_total,
        degree_three_fraction=degree_counts.get(3, 0) / degree_total,
        degree_four_fraction=degree_counts.get(4, 0) / degree_total,
        median_pipe_length_m=median(length_values),
        p90_pipe_length_m=sorted(length_values)[int(len(length_values) * .9)],
        maximum_pipe_length_m=max(length_values), total_pipe_length_m=sum(length_values),
        median_turn_angle_deg=median(angle_values) if angle_values else 99.0,
        p90_turn_angle_deg=sorted(angle_values)[int(len(angle_values) * .9)] if angle_values else 179.0,
        diameter_counts_mm=diameter_counts, materials=materials,
        epanet_junction_count=2221, epanet_pipe_count=2247, epanet_tank_count=6,
        epanet_median_pipe_length_m=54.0,
    )
    if inp_path.exists():
        try:
            model = wntr.network.WaterNetworkModel(str(inp_path))
            object.__setattr__(profile, "epanet_junction_count", len(list(model.junctions())))
            object.__setattr__(profile, "epanet_pipe_count", len(list(model.pipes())))
            object.__setattr__(profile, "epanet_tank_count", len(list(model.tanks())))
            lengths = [float(pipe.length) for _, pipe in model.pipes()]
            object.__setattr__(profile, "epanet_median_pipe_length_m", median(lengths) if lengths else 0.0)
        except Exception:
            pass
    return profile
