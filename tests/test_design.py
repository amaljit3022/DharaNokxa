from pathlib import Path

import pytest

from dharanokxa.catalog import demo_hdpe_catalog
from dharanokxa.demo import generate_demo
from dharanokxa.engine import design
from dharanokxa.hydraulics import status_for
from dharanokxa.models import DesignProfile, DesignRequest
from dharanokxa.reference import load_jorhat_reference
from dharanokxa.roads import load_jorhat_roads


@pytest.mark.parametrize(
    ("pressure", "expected"),
    [(6.99, "FAIL"), (7.0, "FAIL"), (7.01, "MARGINAL"), (7.99, "MARGINAL"), (8.0, "PASS")],
)
def test_exact_pressure_thresholds(pressure, expected):
    simulation = type("Simulation", (), {"minimum_endpoint_pressure_m": pressure})()
    assert status_for(simulation, DesignProfile()) == expected


def test_catalog_uses_internal_diameter():
    for entry in demo_hdpe_catalog():
        assert entry.internal_diameter_mm == pytest.approx(entry.outside_diameter_mm - 2 * entry.wall_thickness_mm)
        assert entry.internal_diameter_mm < entry.outside_diameter_mm


def test_demo_is_deterministic_and_conserves_demand():
    request = DesignRequest(household_count=100)
    first = generate_demo(request)
    second = generate_demo(request)
    assert first == second
    households, nodes, pipes = first
    assert len(households) == 100
    assert len(pipes) >= len(nodes)
    assert sum(n["population_served"] for n in nodes) == sum(h["population"] for h in households)
    assert sum(n["households_served"] for n in nodes) == 100
    assert max(sum(1 for p in pipes if p["from_node"] == n["node_id"] or p["to_node"] == n["node_id"]) for n in nodes) >= 3
    assert sum(n["endpoint"] for n in nodes) >= 5
    assert {p["alignment_type"] for p in pipes} == {"LEFT", "RIGHT", "ROAD_BORE"}
    assert all(p["approved_crossing"] for p in pipes if p["alignment_type"] == "ROAD_BORE")
    assert all(p["road_segment_id"] for p in pipes if p["alignment_type"] != "ROAD_BORE")


def test_jorhat_reference_profile_is_loaded_from_preserved_archive():
    profile = load_jorhat_reference()
    assert profile.source_node_count >= 2000
    assert profile.source_pipe_count >= 2000
    assert profile.connected_components == 6
    assert 0.35 < profile.leaf_fraction < 0.55
    assert profile.median_pipe_length_m == pytest.approx(48.0, abs=10.0)
    assert profile.diameter_counts_mm.get("92", 0) > 1000


def test_jorhat_road_layer_profile_is_loaded():
    profile = load_jorhat_roads()
    assert profile.road_feature_count >= 800
    assert profile.median_segment_length_m == pytest.approx(114.45, abs=2.0)
    assert profile.layer_counts.get("highway_-_primary", 0) >= 800


def test_tentative_road_schema_limits_crossings_to_approved_roads():
    request = DesignRequest(
        road_corridors_path=Path("templates/road_corridors.template.csv"),
        road_crossings_path=Path("templates/road_crossings.template.csv"),
    )
    _, nodes, pipes = generate_demo(request)
    assert len(nodes) == 10
    bores = [pipe for pipe in pipes if pipe["alignment_type"] == "ROAD_BORE"]
    assert bores
    assert all(pipe["approved_crossing"] for pipe in bores)
    assert all(pipe["road_id"] in {"MAIN", "BRANCH_A"} for pipe in bores)


def test_complete_demo_fails_then_optimizes_and_exports(tmp_path: Path):
    result = design(DesignRequest(output_dir=tmp_path / "demo"))
    assert result.iterations[0]["minimum_endpoint_pressure_m"] <= 7.0
    assert any(item["action"] == "UPSIZE" for item in result.iterations)
    assert result.status == "PASS"
    assert result.summary["minimum_endpoint_pressure_m"] >= 8.0
    assert all(node["pressure_m"] > 7.0 for node in result.nodes if node["endpoint"])
    assert result.summary["pdd_demand_delivery_pass"]
    assert Path(result.artifacts["epanet_inp"]).exists()
    assert Path(result.artifacts["report"]).exists()
    assert Path(result.artifacts["design_package"]).exists()
