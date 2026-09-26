from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SchemeConfig:
    config_path: Path
    project: dict[str, Any]
    paths: dict[str, Any]
    inputs: dict[str, Any]
    field_mapping: dict[str, Any] = field(default_factory=dict)
    units: dict[str, Any] = field(default_factory=dict)
    simulation: dict[str, Any] = field(default_factory=dict)
    mapping: dict[str, Any] = field(default_factory=dict)
    reporting: dict[str, Any] = field(default_factory=dict)


def load_scheme_config(path: str | Path) -> SchemeConfig:
    config_path = Path(path).resolve()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return SchemeConfig(
        config_path=config_path,
        project=data.get("project", {}),
        paths=data.get("paths", {}),
        inputs=data.get("inputs", {}),
        field_mapping=data.get("field_mapping", {}),
        units=data.get("units", {}),
        simulation=data.get("simulation", {}),
        mapping=data.get("mapping", {}),
        reporting=data.get("reporting", {}),
    )
