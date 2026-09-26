from __future__ import annotations

from pathlib import Path

from .config import SchemeConfig


def validate_config(config: SchemeConfig) -> list[str]:
    issues: list[str] = []

    if not config.project.get("name"):
        issues.append("Missing project.name in scheme config.")

    for key in ["raw_data_root", "processed_data_root", "model_output_root", "results_root"]:
        if key not in config.paths:
            issues.append(f"Missing paths.{key} in scheme config.")

    for key in ["junctions", "pipes"]:
        if key not in config.inputs:
            issues.append(f"Missing inputs.{key} section.")
            continue
        path = config.inputs[key].get("path")
        if not path:
            issues.append(f"Missing inputs.{key}.path value.")
            continue
        if not Path(path).exists():
            issues.append(f"Input path does not exist: {path}")

    return issues
