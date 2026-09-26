from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PipeCatalogEntry:
    catalog_id: str
    material: str
    grade: str
    outside_diameter_mm: float
    sdr: float
    pressure_class: str
    wall_thickness_mm: float
    internal_diameter_mm: float
    roughness: float
    approval_status: str
    reference: str

    def to_dict(self) -> dict:
        return asdict(self)


def demo_hdpe_catalog() -> list[PipeCatalogEntry]:
    """Synthetic development catalog. It is not a procurement standard."""
    entries: list[PipeCatalogEntry] = []
    for od in (25.0, 32.0, 40.0, 50.0, 63.0, 75.0, 90.0, 110.0, 125.0):
        sdr = 11.0
        wall = od / sdr
        entries.append(
            PipeCatalogEntry(
                catalog_id=f"DEMO-HDPE-PE100-{int(od)}-SDR11",
                material="HDPE",
                grade="PE100",
                outside_diameter_mm=od,
                sdr=sdr,
                pressure_class="DEMO",
                wall_thickness_mm=wall,
                internal_diameter_mm=od - 2.0 * wall,
                roughness=140.0,
                approval_status="DEMONSTRATION_ONLY",
                reference="Synthetic catalog for software verification; not for procurement",
            )
        )
    return entries
