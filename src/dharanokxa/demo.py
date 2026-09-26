from __future__ import annotations

import math
import random
from collections import defaultdict

from .catalog import demo_hdpe_catalog
from .models import DesignRequest


def generate_demo(request: DesignRequest) -> tuple[list[dict], list[dict], list[dict]]:
    """Create a deterministic, offline, branching rural network."""
    rng = random.Random(request.seed)
    node_count = 15
    nodes: list[dict] = []
    for index in range(1, node_count + 1):
        branch = -1 if index % 2 else 1
        distance_m = index * 150.0
        latitude = request.source_latitude + (distance_m / 111_320.0)
        longitude = request.source_longitude + branch * (40.0 + index * 5.0) / (
            111_320.0 * math.cos(math.radians(request.source_latitude))
        )
        nodes.append(
            {
                "node_id": f"J{index:03d}",
                "latitude": latitude,
                "longitude": longitude,
                "elevation_m": 104.0 + index * 0.18 + 0.7 * math.sin(index / 2),
                "elevation_source": "SYNTHETIC",
                "endpoint": index in {5, 10, 15},
            }
        )

    households: list[dict] = []
    assigned: dict[str, list[dict]] = defaultdict(list)
    for index in range(1, request.household_count + 1):
        node_index = 1 + ((index - 1) * node_count // request.household_count)
        node = nodes[min(node_index - 1, node_count - 1)]
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
    previous = "ESR"
    previous_lat = request.source_latitude
    previous_lon = request.source_longitude
    for index, node in enumerate(nodes, start=1):
        dy = (node["latitude"] - previous_lat) * 111_320.0
        dx = (node["longitude"] - previous_lon) * 111_320.0 * math.cos(math.radians(request.source_latitude))
        length = math.hypot(dx, dy) * 1.08
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
        previous = node["node_id"]
        previous_lat = node["latitude"]
        previous_lon = node["longitude"]
    nodes[-1]["endpoint"] = True
    return households, nodes, pipes
