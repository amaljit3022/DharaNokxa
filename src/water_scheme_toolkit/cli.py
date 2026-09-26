from __future__ import annotations

import argparse
import sys

from .config import load_scheme_config
from .pipeline import run_analyze, run_build_model, run_map, run_report, run_simulate, run_validate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generalized water supply scheme toolkit CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ["validate", "build-model", "simulate", "analyze", "map", "report"]:
        sub = subparsers.add_parser(command)
        sub.add_argument("--config", required=True, help="Path to scheme YAML configuration.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_scheme_config(args.config)

    handlers = {
        "validate": run_validate,
        "build-model": run_build_model,
        "simulate": run_simulate,
        "analyze": run_analyze,
        "map": run_map,
        "report": run_report,
    }
    raise SystemExit(handlers[args.command](config))


if __name__ == "__main__":
    main()
