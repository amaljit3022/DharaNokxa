from __future__ import annotations

from .catalog import PipeCatalogEntry
from .hydraulics import Simulation, simulate, source_path, status_for
from .models import DesignRequest


def optimize(request: DesignRequest, nodes: list[dict], pipes: list[dict], entries: list[PipeCatalogEntry]) -> tuple[Simulation, list[dict]]:
    catalog = {entry.catalog_id: entry for entry in entries}
    index = {entry.catalog_id: position for position, entry in enumerate(entries)}
    history: list[dict] = []
    current = simulate(request, nodes, pipes, catalog)
    history.append(_record(0, "INITIAL", current, None))

    for iteration in range(1, request.profile.maximum_iterations + 1):
        if status_for(current, request.profile) == "PASS":
            break
        path = source_path(pipes, current.critical_endpoint_id)
        candidates = [p for p in pipes if p["pipe_id"] in path and index[p["catalog_id"]] < len(entries) - 1]
        if not candidates:
            break
        bottleneck = max(candidates, key=lambda p: current.pipes[p["pipe_id"]]["headloss_m"])
        old_id = bottleneck["catalog_id"]
        new_id = entries[index[old_id] + 1].catalog_id
        before = current
        bottleneck["catalog_id"] = new_id
        current = simulate(request, nodes, pipes, catalog)
        bottleneck["reason_for_change"] = (
            f"Upsized on path to {before.critical_endpoint_id}; "
            f"headloss was {before.pipes[bottleneck['pipe_id']]['headloss_m']:.3f} m"
        )
        history.append(_record(iteration, "UPSIZE", current, {
            "pipe_id": bottleneck["pipe_id"], "from_catalog_id": old_id, "to_catalog_id": new_id,
            "pressure_before_m": before.minimum_endpoint_pressure_m,
            "pressure_after_m": current.minimum_endpoint_pressure_m,
        }))

    if status_for(current, request.profile) == "PASS":
        for pipe in reversed(pipes):
            current_index = index[pipe["catalog_id"]]
            if current_index <= 0:
                continue
            old_id = pipe["catalog_id"]
            trial_id = entries[current_index - 1].catalog_id
            pipe["catalog_id"] = trial_id
            trial = simulate(request, nodes, pipes, catalog)
            accepted = status_for(trial, request.profile) == "PASS"
            history.append(_record(len(history), "DOWNSIZE_ACCEPTED" if accepted else "DOWNSIZE_REJECTED", trial, {
                "pipe_id": pipe["pipe_id"], "from_catalog_id": old_id, "to_catalog_id": trial_id,
                "pressure_before_m": current.minimum_endpoint_pressure_m,
                "pressure_after_m": trial.minimum_endpoint_pressure_m,
            }))
            if accepted:
                current = trial
                pipe["reason_for_change"] = "Safe downsizing retained all mandatory constraints and target pressure"
            else:
                pipe["catalog_id"] = old_id
    return current, history


def _record(iteration: int, action: str, simulation: Simulation, change: dict | None) -> dict:
    return {
        "iteration": iteration,
        "action": action,
        "critical_endpoint_id": simulation.critical_endpoint_id,
        "minimum_endpoint_pressure_m": simulation.minimum_endpoint_pressure_m,
        "maximum_pressure_m": simulation.maximum_pressure_m,
        "demand_delivery_pass": simulation.all_demands_delivered,
        "change": change,
    }
