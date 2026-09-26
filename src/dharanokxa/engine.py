from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .catalog import demo_hdpe_catalog
from .demo import generate_demo
from .exports import create_artifacts
from .hydraulics import simulate, status_for
from .models import DesignRequest, DesignResult
from .optimizer import optimize
from .topology import road_topology_violations


def design(request: DesignRequest) -> DesignResult:
    """Generate, simulate, correct, verify, and package one candidate design."""
    run_key = f"{request.scheme_name}|{request.seed}|{request.household_count}|{request.source_head_m}"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + hashlib.sha256(run_key.encode()).hexdigest()[:8]
    output_dir = request.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    households, nodes, pipes = generate_demo(request)
    entries = demo_hdpe_catalog()
    catalog = {entry.catalog_id: entry for entry in entries}
    final_sim, iterations = optimize(request, nodes, pipes, entries)
    final_dda = simulate(request, nodes, pipes, catalog, "DDA")
    final_pdd = simulate(request, nodes, pipes, catalog, "PDD")
    pressure_status = status_for(final_dda, request.profile)
    status = "PASS" if pressure_status == "PASS" and final_pdd.all_demands_delivered else "FAIL"

    node_lookup = final_dda.nodes
    for node in nodes:
        node.update(node_lookup[node["node_id"]])
        node["critical"] = node["node_id"] == final_dda.critical_endpoint_id
        p = node["pressure_m"]
        node["compliance"] = "FAIL" if p <= request.profile.hard_min_pressure_m else ("MARGINAL" if p < request.profile.target_pressure_m else "PASS")
        node["pressure_requirement"] = f"> {request.profile.hard_min_pressure_m:.2f} m; target >= {request.profile.target_pressure_m:.2f} m"
        node["safety_margin_m"] = p - request.profile.hard_min_pressure_m
    for pipe in pipes:
        entry = catalog[pipe["catalog_id"]]
        initial = catalog[pipe["initial_catalog_id"]]
        pipe.update(final_dda.pipes[pipe["pipe_id"]])
        pipe.update({
            "material": entry.material, "grade": entry.grade, "outside_diameter_mm": entry.outside_diameter_mm,
            "sdr": entry.sdr, "wall_thickness_mm": entry.wall_thickness_mm,
            "internal_diameter_mm": entry.internal_diameter_mm, "initial_internal_diameter_mm": initial.internal_diameter_mm,
            "final_catalog_id": entry.catalog_id, "approval_status": entry.approval_status,
        })

    road_violations = road_topology_violations(nodes, pipes)
    road_line_counts = {
        road_id: len({pipe["alignment_type"] for pipe in pipes if pipe.get("road_id") == road_id and pipe["alignment_type"] in {"LEFT", "RIGHT"}})
        for road_id in {pipe.get("road_id") for pipe in pipes if pipe["alignment_type"] in {"LEFT", "RIGHT"}}
    }
    summary = {
        "data_quality": "SYNTHETIC", "review_status": "AWAITING_ENGINEER_REVIEW",
        "households": len(households), "population": sum(h["population"] for h in households),
        "design_demand_lps": sum(n["design_demand_lps"] for n in nodes),
        "total_pipe_length_m": sum(p["length_m"] for p in pipes), "hydraulic_nodes": len(nodes),
        "minimum_endpoint_pressure_m": final_dda.minimum_endpoint_pressure_m,
        "critical_endpoint_id": final_dda.critical_endpoint_id,
        "maximum_pressure_m": final_dda.maximum_pressure_m,
        "configured_pressure_margin_m": request.profile.target_pressure_m - request.profile.hard_min_pressure_m,
        "achieved_pressure_margin_m": final_dda.minimum_endpoint_pressure_m - request.profile.hard_min_pressure_m,
        "optimization_iterations": len(iterations) - 1,
        "dda_status": pressure_status, "pdd_demand_delivery_pass": final_pdd.all_demands_delivered,
        "simulator": final_dda.simulator,
        "geometry_reference": "ROAD_CORRIDOR_CONSTRAINTS",
        "road_alignment_rule": "STRAIGHT_SEGMENTS_BETWEEN_NAMED_INTERSECTIONS_WITH_APPROVED_ROAD_BORE_CROSSINGS",
        "road_topology_status": "PASS" if not road_violations else "FAIL",
        "road_topology_violations": road_violations,
        "max_longitudinal_lines_per_road": max(road_line_counts.values(), default=0),
        "max_road_run_connections_per_node": max((n.get("road_run_connections", 0) for n in nodes), default=0),
        "max_approved_bore_connections_per_node": max((n.get("approved_bore_connections", 0) for n in nodes), default=0),
    }
    result = DesignResult(run_id, request.scheme_name, status, output_dir, summary, households, nodes, pipes, iterations)
    result.artifacts = create_artifacts(result, request, final_sim, catalog)
    (output_dir / "design_result.json").write_text(json.dumps(result.to_dict(), indent=2, default=str), encoding="utf-8")
    return result
