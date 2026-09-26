from __future__ import annotations

import math
import tempfile
from dataclasses import dataclass
from pathlib import Path

import networkx as nx
import wntr

from .catalog import PipeCatalogEntry
from .models import DesignProfile, DesignRequest


@dataclass
class Simulation:
    nodes: dict[str, dict]
    pipes: dict[str, dict]
    minimum_endpoint_pressure_m: float
    critical_endpoint_id: str
    maximum_pressure_m: float
    all_demands_delivered: bool
    simulator: str


def build_model(request: DesignRequest, nodes: list[dict], pipes: list[dict], catalog: dict[str, PipeCatalogEntry]):
    wn = wntr.network.WaterNetworkModel()
    wn.options.time.duration = 0
    wn.options.hydraulic.headloss = "H-W"
    wn.options.hydraulic.inpfile_units = "LPS"
    wn.add_reservoir("ESR", base_head=request.source_head_m)
    wn.get_node("ESR").coordinates = (request.source_longitude, request.source_latitude)
    for node in nodes:
        wn.add_junction(
            node["node_id"],
            base_demand=node["design_demand_lps"] / 1000.0,
            elevation=node["elevation_m"],
        )
        wn.get_node(node["node_id"]).coordinates = (node["longitude"], node["latitude"])
    for pipe in pipes:
        entry = catalog[pipe["catalog_id"]]
        wn.add_pipe(
            pipe["pipe_id"], pipe["from_node"], pipe["to_node"],
            length=pipe["length_m"], diameter=entry.internal_diameter_mm / 1000.0,
            roughness=entry.roughness, minor_loss=0.0,
        )
    return wn


def simulate(request: DesignRequest, nodes: list[dict], pipes: list[dict], catalog: dict[str, PipeCatalogEntry], demand_model: str = "DDA") -> Simulation:
    wn = build_model(request, nodes, pipes, catalog)
    wn.options.hydraulic.demand_model = demand_model
    wn.options.hydraulic.required_pressure = request.profile.required_pressure_pdd_m
    wn.options.hydraulic.minimum_pressure = request.profile.minimum_pressure_pdd_m
    wn.options.hydraulic.pressure_exponent = 0.5
    simulator = "EPANET_2.2"
    with tempfile.TemporaryDirectory(prefix="dharanokxa-epanet-") as workdir:
        results = wntr.sim.EpanetSimulator(wn).run_sim(
            file_prefix=str(Path(workdir) / "simulation"), version=2.2
        )
    pressure = results.node["pressure"].iloc[-1]
    demand = results.node["demand"].iloc[-1]
    flow = results.link["flowrate"].iloc[-1]
    velocity = results.link["velocity"].iloc[-1]

    node_results: dict[str, dict] = {}
    required = {n["node_id"] for n in nodes if n["endpoint"]}
    for node in nodes:
        p = float(pressure[node["node_id"]])
        delivered = float(demand[node["node_id"]]) * 1000.0
        requested = node["design_demand_lps"]
        node_results[node["node_id"]] = {
            "pressure_m": p,
            "delivered_demand_lps": delivered,
            "requested_demand_lps": requested,
            "demand_delivery_ratio": 1.0 if requested == 0 else delivered / requested,
        }
    pipe_results: dict[str, dict] = {}
    for pipe in pipes:
        q = abs(float(flow[pipe["pipe_id"]]))
        v = abs(float(velocity[pipe["pipe_id"]]))
        start_head = float(results.node["head"].iloc[-1][pipe["from_node"]])
        end_head = float(results.node["head"].iloc[-1][pipe["to_node"]])
        loss = abs(start_head - end_head)
        pipe_results[pipe["pipe_id"]] = {
            "flow_lps": q * 1000.0,
            "velocity_mps": v,
            "headloss_m": loss,
            "headloss_m_per_km": loss * 1000.0 / pipe["length_m"],
        }
    critical = min(required, key=lambda name: node_results[name]["pressure_m"])
    all_delivered = all(v["demand_delivery_ratio"] >= 0.999 for v in node_results.values())
    return Simulation(
        nodes=node_results,
        pipes=pipe_results,
        minimum_endpoint_pressure_m=node_results[critical]["pressure_m"],
        critical_endpoint_id=critical,
        maximum_pressure_m=max(v["pressure_m"] for v in node_results.values()),
        all_demands_delivered=all_delivered,
        simulator=simulator,
    )


def source_path(pipe_rows: list[dict], endpoint: str) -> list[str]:
    graph = nx.Graph()
    for pipe in pipe_rows:
        graph.add_edge(pipe["from_node"], pipe["to_node"], pipe_id=pipe["pipe_id"])
    path = nx.shortest_path(graph, "ESR", endpoint)
    return [graph.edges[a, b]["pipe_id"] for a, b in zip(path, path[1:])]


def status_for(sim: Simulation, profile: DesignProfile) -> str:
    if sim.minimum_endpoint_pressure_m <= profile.hard_min_pressure_m:
        return "FAIL"
    if sim.minimum_endpoint_pressure_m < profile.target_pressure_m:
        return "MARGINAL"
    return "PASS"
