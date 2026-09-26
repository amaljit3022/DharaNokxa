from __future__ import annotations

import math
import random
from collections import defaultdict

from .catalog import demo_hdpe_catalog
from .models import DesignRequest
from .road_inputs import load_approved_crossings, load_tentative_corridors, load_tentative_intersections
from .topology import validate_road_topology


ROAD_OFFSET_M = 4.0


def _unit(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    return dx / length, dy / length


def _offset_points(points: list[tuple[float, float]], side: int) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for index, point in enumerate(points):
        before = points[max(0, index - 1)]
        after = points[min(len(points) - 1, index + 1)]
        tangent = _unit(before, after)
        normal = (-tangent[1] * side, tangent[0] * side)
        result.append((point[0] + normal[0] * ROAD_OFFSET_M, point[1] + normal[1] * ROAD_OFFSET_M))
    return result


def _corridors(request: DesignRequest) -> dict[str, list[tuple[float, float]]]:
    """Straight road centerline segments with named intersections.

    Every hydraulic run pipe joins consecutive offset points. Turns occur only
    where two road segments meet. The lines are deliberately simple but follow
    the field convention of straight polyline features.
    """
    defaults = {
        "MAIN": [(0, 0), (0, 120), (0, 240), (0, 360), (0, 480)],
        "WEST": [(0, 120), (-140, 120), (-280, 120)],
        "EAST": [(0, 240), (150, 240), (300, 240)],
        "NORTH_WEST": [(0, 360), (-150, 360), (-300, 360)],
        "NORTH_EAST": [(0, 480), (160, 480), (320, 480)],
    }
    if request.road_corridors_path and request.road_corridors_path.exists():
        return load_tentative_corridors(request.road_corridors_path)
    return defaults


def _intersection_ids(request: DesignRequest, corridors: dict[str, list[tuple[float, float]]]) -> dict[str, list[str]]:
    if request.road_corridors_path and request.road_corridors_path.exists():
        return load_tentative_intersections(request.road_corridors_path)
    return {
        road_id: [f"I_{road_id}_{point_index:02d}" for point_index in range(len(points))]
        for road_id, points in corridors.items()
    }


ROAD_CODES = {"MAIN": "M", "WEST": "W", "EAST": "E", "NORTH_WEST": "NW", "NORTH_EAST": "NE"}


def generate_demo(request: DesignRequest) -> tuple[list[dict], list[dict], list[dict]]:
    """Create a road-corridor network with paired roadside pipes.

    The demo uses straight pipes between explicit road intersections, paired
    left/right roadside alignments, and road-bore links only at the approved
    intersection list. Training calibration is not exposed in a design result.
    """
    rng = random.Random(request.seed)
    corridors = _corridors(request)
    intersection_ids = _intersection_ids(request, corridors)
    road_codes = dict(ROAD_CODES)
    for index, road_id in enumerate(corridors):
        road_codes.setdefault(road_id, f"R{index + 1}")
    source_road = next(iter(corridors))
    nodes: list[dict] = []
    nodes_by_corridor_side: dict[tuple[str, str], list[str]] = {}
    positions: dict[str, tuple[float, float]] = {}

    for road_id, centerline in corridors.items():
        for side_name, side in (("LEFT", -1), ("RIGHT", 1)):
            side_points = _offset_points(centerline, side)
            ids: list[str] = []
            for point_index, (x, y) in enumerate(side_points):
                node_id = f"{road_codes[road_id]}_{side_name[:1]}_{point_index:02d}"
                ids.append(node_id)
                positions[node_id] = (x, y)
                latitude = request.source_latitude + y / 111_320.0
                longitude = request.source_longitude + x / (111_320.0 * math.cos(math.radians(request.source_latitude)))
                nodes.append({
                    "node_id": node_id, "latitude": latitude, "longitude": longitude,
                    "elevation_m": 104.0 + 0.0025 * math.hypot(x, y) + rng.uniform(-0.25, 0.25),
                    "elevation_source": "SYNTHETIC",
                    "endpoint": False, "road_id": road_id, "road_side": side_name,
                    "road_intersection_id": intersection_ids[road_id][point_index],
                })
            nodes_by_corridor_side[(road_id, side_name)] = ids

    pipes: list[dict] = []
    pipe_number = 1
    first = demo_hdpe_catalog()[0]

    def add_pipe(from_node: str, to_node: str, *, road_id: str, segment_id: str, alignment: str,
                 crossing_id: str | None = None, from_road_id: str | None = None,
                 to_road_id: str | None = None, from_road_side: str | None = None,
                 to_road_side: str | None = None) -> None:
        nonlocal pipe_number
        a, b = positions[from_node], positions[to_node]
        pipes.append({
            "pipe_id": f"P{pipe_number:03d}", "from_node": from_node, "to_node": to_node,
            "length_m": math.hypot(b[0] - a[0], b[1] - a[1]),
            "catalog_id": first.catalog_id, "initial_catalog_id": first.catalog_id,
            "reason_for_change": "Initial deliberately undersized demo configuration",
            "road_id": road_id, "road_segment_id": segment_id, "road_side": "BOTH" if alignment == "ROAD_BORE" else alignment,
            "alignment_type": alignment, "crossing_id": crossing_id,
            "approved_crossing": alignment == "ROAD_BORE",
            "from_road_id": from_road_id or road_id, "to_road_id": to_road_id or road_id,
            "from_road_side": from_road_side or alignment, "to_road_side": to_road_side or alignment,
        })
        pipe_number += 1

    # Straight roadside pipe runs: one on each side of every road segment.
    for road_id, centerline in corridors.items():
        for side_name in ("LEFT", "RIGHT"):
            ids = nodes_by_corridor_side[(road_id, side_name)]
            for segment_index, (from_node, to_node) in enumerate(zip(ids, ids[1:])):
                add_pipe(from_node, to_node, road_id=road_id, segment_id=f"{road_id}_{segment_index:02d}", alignment=side_name)

    # The only cross-road movements are explicitly approved boring points.
    # Source entry and corridor junctions are named in the tentative schema.
    crossing_pairs = [
        ("MAIN", 1, "WEST", 0, "X_MAIN_WEST"),
        ("MAIN", 2, "EAST", 0, "X_MAIN_EAST"),
        ("MAIN", 3, "NORTH_WEST", 0, "X_MAIN_NW"),
        ("MAIN", 4, "NORTH_EAST", 0, "X_MAIN_NE"),
    ]
    if request.road_corridors_path and request.road_corridors_path.exists():
        # For supplied tentative lines, shared endpoints are intersections. A
        # crossing is permitted only when both participating roads appear in
        # an approved crossing record.
        approved_crossings = load_approved_crossings(request.road_crossings_path) if request.road_crossings_path and request.road_crossings_path.exists() else {}
        shared: dict[tuple[float, float], list[tuple[str, int]]] = defaultdict(list)
        for road_id, points in corridors.items():
            for point_index, point in enumerate(points):
                shared[point].append((road_id, point_index))
        crossing_pairs = []
        for point, matches in shared.items():
            for left, right in zip(matches, matches[1:]):
                left_intersection = intersection_ids[left[0]][left[1]]
                right_intersection = intersection_ids[right[0]][right[1]]
                if left_intersection != right_intersection:
                    continue
                approved_roads = approved_crossings.get(left_intersection, set())
                if {left[0], right[0]} - approved_roads:
                    continue
                crossing_pairs.append((left[0], left[1], right[0], right[1], f"X_{left[0]}_{right[0]}_{int(point[0])}_{int(point[1])}"))
    for main_id, main_index, branch_id, branch_index, crossing_id in crossing_pairs:
        add_pipe(nodes_by_corridor_side[(main_id, "LEFT")][main_index], nodes_by_corridor_side[(branch_id, "LEFT")][branch_index], road_id=main_id, segment_id=f"{main_id}_{branch_id}", alignment="ROAD_BORE", crossing_id=crossing_id, from_road_id=main_id, to_road_id=branch_id, from_road_side="LEFT", to_road_side="LEFT")
        add_pipe(nodes_by_corridor_side[(main_id, "RIGHT")][main_index], nodes_by_corridor_side[(branch_id, "RIGHT")][branch_index], road_id=main_id, segment_id=f"{main_id}_{branch_id}", alignment="ROAD_BORE", crossing_id=crossing_id, from_road_id=main_id, to_road_id=branch_id, from_road_side="RIGHT", to_road_side="RIGHT")
    # ESR has a defined access crossing connecting both roadside runs.
    esr_left = nodes_by_corridor_side[(source_road, "LEFT")][0]
    esr_right = nodes_by_corridor_side[(source_road, "RIGHT")][0]
    positions["ESR"] = (0.0, 0.0)
    add_pipe("ESR", esr_left, road_id=source_road, segment_id=f"{source_road}_00", alignment="ROAD_BORE", crossing_id="X_ESR_ENTRY", from_road_id="ESR", to_road_id=source_road, from_road_side="LEFT", to_road_side="LEFT")
    add_pipe("ESR", esr_right, road_id=source_road, segment_id=f"{source_road}_00", alignment="ROAD_BORE", crossing_id="X_ESR_ENTRY", from_road_id="ESR", to_road_id=source_road, from_road_side="RIGHT", to_road_side="RIGHT")

    endpoints = {node_id for (road_id, side_name), ids in nodes_by_corridor_side.items() for node_id in (ids[-1],)}
    for node in nodes:
        node["endpoint"] = node["node_id"] in endpoints

    endpoint_nodes = [node for node in nodes if node["endpoint"]]
    households: list[dict] = []
    assigned: dict[str, list[dict]] = defaultdict(list)
    for index in range(1, request.household_count + 1):
        node = endpoint_nodes[(index - 1) % len(endpoint_nodes)]
        population = rng.choice((4, 4, 5, 5, 5, 6))
        household = {
            "household_id": f"HH{index:04d}",
            "latitude": node["latitude"] + rng.uniform(-0.00003, 0.00003),
            "longitude": node["longitude"] + rng.uniform(-0.00003, 0.00003),
            "population": population, "population_source": "SYNTHETIC",
            "demand_node_id": node["node_id"], "road_id": node["road_id"],
            "road_side": node["road_side"], "service_connection": "ROAD_SIDE_CONNECTION",
        }
        households.append(household)
        assigned[node["node_id"]].append(household)

    effective_lpcd = request.profile.effective_lpcd
    for node in nodes:
        served = assigned[node["node_id"]]
        population = sum(h["population"] for h in served)
        node["population_served"] = population
        node["households_served"] = len(served)
        node["base_demand_lps"] = population * effective_lpcd / 86_400.0
        node["design_demand_lps"] = node["base_demand_lps"] * request.profile.peak_factor
    for node in nodes:
        connected = [pipe for pipe in pipes if pipe["from_node"] == node["node_id"] or pipe["to_node"] == node["node_id"]]
        node["road_run_connections"] = sum(pipe["alignment_type"] in {"LEFT", "RIGHT"} for pipe in connected)
        node["approved_bore_connections"] = sum(pipe["alignment_type"] == "ROAD_BORE" for pipe in connected)
        node["hydraulic_degree"] = len(connected)
    validate_road_topology(nodes, pipes)
    return households, nodes, pipes
