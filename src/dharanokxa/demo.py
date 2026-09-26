from __future__ import annotations

import math
import random
from collections import defaultdict

from .catalog import demo_hdpe_catalog
from .models import DesignRequest
from .reference import load_jorhat_reference


def generate_demo(request: DesignRequest) -> tuple[list[dict], list[dict], list[dict]]:
    """Create a deterministic branching network shaped by Jorhat observations.

    The preserved project supplies topology statistics, not coordinates. The
    generated geometry is therefore synthetic, local, and reference-informed.
    It follows a rooted branching network with varied segment lengths instead of
    inventing a single zigzag chain.
    """
    rng = random.Random(request.seed)
    reference = load_jorhat_reference()
    node_count = max(31, min(60, int(request.household_count * 0.45)))
    nodes: list[dict] = []
    local_positions: dict[str, tuple[float, float]] = {}
    parent_by_node: dict[str, str] = {}
    children_by_node: dict[str, list[str]] = defaultdict(list)
    # Three primary corridors, then two-way side branches. This mirrors the
    # observed predominance of degree-3 nodes and terminal leaves.
    queue: list[tuple[str, float, float, float, int]] = [("ESR", 0.0, 0.0, math.pi / 2, 0)]
    for index in range(1, node_count + 1):
        parent, px, py, parent_heading, depth = queue.pop(0)
        spread = (-0.48, 0.0, 0.48)[(index - 1) % 3] if parent == "ESR" else rng.choice((-0.44, 0.44))
        heading = parent_heading + spread
        segment = max(12.0, rng.lognormvariate(math.log(reference.median_pipe_length_m), 0.48))
        segment = min(segment, reference.p90_pipe_length_m * 1.5)
        x, y = px + segment * math.cos(heading), py + segment * math.sin(heading)
        node_id = f"J{index:03d}"
        parent_by_node[node_id] = parent
        local_positions[node_id] = (x, y)
        if parent != "ESR":
            children_by_node[parent].append(node_id)
        if index < node_count:
            # Leave enough terminal nodes to approximate the reference leaf rate.
            child_count = 2 if (index < node_count * 0.55 and depth < 4) else (1 if index % 3 else 0)
            for child_offset in range(child_count):
                queue.append((node_id, x, y, heading + (0.18 if child_offset else -0.18), depth + 1))
        distance_m = (x * x + y * y) ** 0.5
        latitude = request.source_latitude + (y / 111_320.0)
        longitude = request.source_longitude + x / (111_320.0 * math.cos(math.radians(request.source_latitude)))
        nodes.append(
            {
                "node_id": node_id,
                "latitude": latitude,
                "longitude": longitude,
                "elevation_m": 104.0 + 0.003 * distance_m + 0.9 * math.sin(index / 3),
                "elevation_source": "SYNTHETIC",
                "endpoint": False,
                "reference_profile": "JORHAT_DERIVED_TOPOLOGY_AND_LENGTHS",
            }
        )
    for node in nodes:
        node["endpoint"] = not children_by_node.get(node["node_id"])

    households: list[dict] = []
    assigned: dict[str, list[dict]] = defaultdict(list)
    for index in range(1, request.household_count + 1):
        endpoint_nodes = [node for node in nodes if node["endpoint"]]
        node = endpoint_nodes[(index - 1) % len(endpoint_nodes)]
        population = rng.choice((4, 4, 5, 5, 5, 6))
        household = {
            "household_id": f"HH{index:04d}",
            "latitude": node["latitude"] + rng.uniform(-0.00012, 0.00012),
            "longitude": node["longitude"] + rng.uniform(-0.00012, 0.00012),
            "population": population,
            "population_source": "SYNTHETIC",
            "demand_node_id": node["node_id"],
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

    first = demo_hdpe_catalog()[0]
    pipes: list[dict] = []
    for index, node in enumerate(nodes, start=1):
        previous = parent_by_node[node["node_id"]]
        px, py = (0.0, 0.0) if previous == "ESR" else local_positions[previous]
        x, y = local_positions[node["node_id"]]
        length = math.hypot(x - px, y - py)
        pipes.append(
            {
                "pipe_id": f"P{index:03d}",
                "from_node": previous,
                "to_node": node["node_id"],
                "length_m": length,
                "catalog_id": first.catalog_id,
                "initial_catalog_id": first.catalog_id,
                "reason_for_change": "Initial deliberately undersized demo configuration",
            }
        )
    # The reference networks expose many terminals; keep all leaf nodes as
    # required endpoints so pressure is never reduced to an average check.
    return households, nodes, pipes
