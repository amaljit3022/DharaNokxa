from __future__ import annotations

from pathlib import Path

from .config import SchemeConfig
from .validation import validate_config


def ensure_output_dirs(config: SchemeConfig) -> None:
    for key in ["processed_data_root", "model_output_root", "results_root"]:
        path = config.paths.get(key)
        if path:
            Path(path).mkdir(parents=True, exist_ok=True)


def run_validate(config: SchemeConfig) -> int:
    issues = validate_config(config)
    if issues:
        print("Validation failed:")
        for issue in issues:
            print(f" - {issue}")
        return 1
    print(f"Validation passed for scheme: {config.project.get('name', 'unnamed_scheme')}")
    return 0


def run_build_model(config: SchemeConfig) -> int:
    ensure_output_dirs(config)
    print("Build-model scaffold ready.")
    print("Next implementation step: convert config-driven inputs into a canonical network schema and EPANET/WNTR model.")
    return 0


def run_simulate(config: SchemeConfig) -> int:
    ensure_output_dirs(config)
    print("Simulate scaffold ready.")
    print("Next implementation step: load generated model and execute hydraulic simulation.")
    return 0


def run_analyze(config: SchemeConfig) -> int:
    ensure_output_dirs(config)
    print("Analyze scaffold ready.")
    print("Next implementation step: compute reliability, pressure deficiency, criticality, and redundancy metrics.")
    return 0


def run_map(config: SchemeConfig) -> int:
    ensure_output_dirs(config)
    print("Map scaffold ready.")
    print("Next implementation step: render generalized scheme maps from configured GIS/context layers.")
    return 0


def run_report(config: SchemeConfig) -> int:
    ensure_output_dirs(config)
    print("Report scaffold ready.")
    print("Next implementation step: compile markdown and CSV deliverables for the configured scheme.")
    return 0
