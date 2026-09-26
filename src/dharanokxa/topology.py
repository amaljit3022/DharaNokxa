from __future__ import annotations

from collections import defaultdict
from typing import Any

MAX_APPROVED_BORE_LENGTH_M = 50.0

def road_topology_violations(nodes: list[dict[str, Any]], pipes: list[dict[str, Any]]) -> list[str]:
    """Return construction-topology violations for a two-sided road network.

    A road has at most one longitudinal run on each side. Approved road
    intersections share one node per side; no extra road-to-road joint pipe is
    needed. Source-entry bores remain explicit hydraulic links.
    """
    violations: list[str] = []
    node_ids = {str(node["node_id"]) for node in nodes}
    incident: dict[str, list[dict[str, Any]]] = defaultdict(list)
    road_sides: dict[str, set[str]] = defaultdict(set)
    crossing_pipes: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for pipe in pipes:
        from_node = str(pipe["from_node"])
        to_node = str(pipe["to_node"])
        if from_node not in node_ids and from_node != "ESR":
            violations.append(f"Pipe {pipe['pipe_id']} references an unknown node")
        if to_node not in node_ids and to_node != "ESR":
            violations.append(f"Pipe {pipe['pipe_id']} references an unknown node")
        incident[from_node].append(pipe)
        incident[to_node].append(pipe)
        alignment = str(pipe.get("alignment_type", ""))
        if alignment in {"LEFT", "RIGHT"}:
            road_id = str(pipe.get("road_id", ""))
            road_sides[road_id].add(alignment)
            if pipe.get("from_road_id", road_id) != road_id or pipe.get("to_road_id", road_id) != road_id:
                violations.append(f"Run pipe {pipe['pipe_id']} changes road without a bore")
        elif alignment == "ROAD_BORE":
            crossing_id = pipe.get("crossing_id")
            if not crossing_id:
                violations.append(f"Road bore {pipe['pipe_id']} has no crossing ID")
            else:
                crossing_pipes[str(crossing_id)].append(pipe)
            if not pipe.get("approved_crossing"):
                violations.append(f"Road bore {pipe['pipe_id']} is not approved")
            if float(pipe.get("length_m", 0.0)) > MAX_APPROVED_BORE_LENGTH_M:
                violations.append(f"Road bore {pipe['pipe_id']} is longer than {MAX_APPROVED_BORE_LENGTH_M:g} m")

    for road_id, sides in road_sides.items():
        if len(sides) > 2:
            violations.append(f"Road {road_id} has more than two longitudinal lines: {sorted(sides)}")
        if sides != {"LEFT", "RIGHT"}:
            violations.append(f"Road {road_id} does not have exactly LEFT and RIGHT runs: {sorted(sides)}")

    for node_id, links in incident.items():
        if node_id == "ESR":
            continue
        runs = [link for link in links if link.get("alignment_type") in {"LEFT", "RIGHT"}]
        bores = [link for link in links if link.get("alignment_type") == "ROAD_BORE"]
        by_road: dict[str, int] = defaultdict(int)
        for link in runs:
            by_road[str(link.get("road_id", ""))] += 1
        if any(count > 2 for count in by_road.values()):
            violations.append(f"Node {node_id} has more than two run links on one road")
        if len(bores) > 1:
            violations.append(f"Node {node_id} has more than one road-bore link")
        if len(links) > 3:
            violations.append(f"Node {node_id} has more than two run links plus one approved bore")

    for node in nodes:
        connected_roads = set(node.get("connected_road_ids", [node.get("road_id", "")]))
        if len(connected_roads) > 1:
            if not node.get("approved_crossing"):
                violations.append(f"Intersection node {node['node_id']} joins roads without approval")
            if not node.get("crossing_ids"):
                violations.append(f"Intersection node {node['node_id']} has no crossing ID")

    for crossing_id, links in crossing_pipes.items():
        if len(links) != 2:
            violations.append(f"Crossing {crossing_id} must contain exactly two bore links")
            continue
        road_pairs = {
            (str(link.get("from_road_id", "")), str(link.get("to_road_id", "")))
            for link in links
        }
        if len({road for pair in road_pairs for road in pair}) != 2:
            violations.append(f"Crossing {crossing_id} must connect two distinct roads")
        side_pairs = {
            (str(link.get("from_road_side", "")), str(link.get("to_road_side", "")))
            for link in links
        }
        if side_pairs != {("LEFT", "LEFT"), ("RIGHT", "RIGHT")}:
            violations.append(f"Crossing {crossing_id} must connect matching roadside pairs")

    return violations


def validate_road_topology(nodes: list[dict[str, Any]], pipes: list[dict[str, Any]]) -> None:
    violations = road_topology_violations(nodes, pipes)
    if violations:
        raise ValueError("Invalid road topology: " + "; ".join(violations))
