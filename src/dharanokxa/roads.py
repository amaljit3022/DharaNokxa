from __future__ import annotations

"""Road-corridor reference and controlled-crossing primitives.

The hydraulic network is aligned to straight road segments between named
intersections. A road-bore link is created only from the approved crossing
list; it is never inferred from a household-to-household line.
"""

from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Any


@dataclass(frozen=True)
class RoadReferenceProfile:
    source: str
    road_feature_count: int
    median_segment_length_m: float
    p90_segment_length_m: float
    maximum_segment_length_m: float
    total_centerline_length_m: float
    layer_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ROAD_FALLBACK = RoadReferenceProfile(
    source="Jorhat ROAD layer aggregate snapshot (offline fallback)",
    road_feature_count=846,
    median_segment_length_m=114.45,
    p90_segment_length_m=495.82,
    maximum_segment_length_m=11797.71,
    total_centerline_length_m=277104.99,
    layer_counts={"highway_-_primary": 807, "COMMAND ARE": 19, "railway_-_rail": 13, "waterway_-_river": 7},
)


@lru_cache(maxsize=4)
def load_jorhat_roads(root: str | None = None) -> RoadReferenceProfile:
    project_root = Path(root) if root else Path(__file__).resolve().parents[2] / "legacy" / "jorhat_project"
    path = project_root / "JORHAT" / "GIS FILE" / "Jorhat project area" / "Jorhat project area" / "ROAD.shp"
    if not path.exists():
        return ROAD_FALLBACK
    try:
        import geopandas as gpd
        roads = gpd.read_file(path)
        lengths = [float(value) for value in roads.geometry.length if value and value > 0]
        if not lengths:
            return ROAD_FALLBACK
        return RoadReferenceProfile(
            source=str(path), road_feature_count=len(roads),
            median_segment_length_m=median(lengths),
            p90_segment_length_m=sorted(lengths)[int(len(lengths) * 0.9)],
            maximum_segment_length_m=max(lengths), total_centerline_length_m=sum(lengths),
            layer_counts={str(key): int(value) for key, value in roads["Layer"].value_counts().items()},
        )
    except Exception:
        return ROAD_FALLBACK

