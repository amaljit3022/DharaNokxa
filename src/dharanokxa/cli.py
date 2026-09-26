from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import design
from .models import DesignRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dharanokxa", description="Automated candidate water distribution network design")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Run the complete deterministic offline demonstration")
    demo.add_argument("--output", type=Path, default=Path("results/demo_jjm_scheme"))
    demo.add_argument("--households", type=int, default=100)
    demo.add_argument("--seed", type=int, default=20260926)
    demo.add_argument("--road-corridors", type=Path, default=None, help="Optional ordered road corridor CSV")
    demo.add_argument("--road-crossings", type=Path, default=None, help="Optional approved road crossing CSV")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "demo":
        result = design(DesignRequest(
            output_dir=args.output, household_count=args.households, seed=args.seed,
            road_corridors_path=args.road_corridors, road_crossings_path=args.road_crossings,
        ))
        print(json.dumps({"run_id": result.run_id, "status": result.status, **result.summary, "artifacts": result.artifacts}, indent=2))
        raise SystemExit(0 if result.status == "PASS" else 2)


if __name__ == "__main__":
    main()
