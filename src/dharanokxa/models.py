from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DesignProfile:
    name: str = "JJM_2_0_ASSAM_DEMO"
    domestic_lpcd: float = 55.0
    demand_uplift: float = 0.15
    peak_factor: float = 3.0
    hard_min_pressure_m: float = 7.0
    target_pressure_m: float = 8.0
    maximum_pressure_m: float = 60.0
    maximum_velocity_mps: float = 2.0
    maximum_headloss_m_per_km: float = 15.0
    required_pressure_pdd_m: float = 8.0
    minimum_pressure_pdd_m: float = 0.0
    maximum_iterations: int = 80

    @property
    def effective_lpcd(self) -> float:
        return self.domestic_lpcd * (1.0 + self.demand_uplift)


@dataclass(frozen=True)
class DesignRequest:
    scheme_name: str = "Demo JJM 2.0 Rural Scheme"
    output_dir: Path = Path("results/demo_jjm_scheme")
    seed: int = 20260926
    household_count: int = 100
    source_latitude: float = 26.182145
    source_longitude: float = 91.743281
    source_head_m: float = 119.0
    profile: DesignProfile = field(default_factory=DesignProfile)


@dataclass
class DesignResult:
    run_id: str
    scheme_name: str
    status: str
    output_dir: Path
    summary: dict[str, Any]
    households: list[dict[str, Any]]
    nodes: list[dict[str, Any]]
    pipes: list[dict[str, Any]]
    iterations: list[dict[str, Any]]
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["output_dir"] = str(self.output_dir)
        return value
