from pathlib import Path

import pytest

from dharanokxa.catalog import demo_hdpe_catalog
from dharanokxa.demo import generate_demo
from dharanokxa.engine import design
from dharanokxa.hydraulics import status_for
from dharanokxa.models import DesignProfile, DesignRequest


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
    assert len(pipes) == len(nodes)
    assert sum(n["population_served"] for n in nodes) == sum(h["population"] for h in households)
    assert sum(n["households_served"] for n in nodes) == 100


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
