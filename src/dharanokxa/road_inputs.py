from __future__ import annotations

import csv
from pathlib import Path


def load_tentative_corridors(path: str | Path) -> dict[str, list[tuple[float, float]]]:
    """Load the small field-official CSV schema into ordered straight segments."""
    roads: dict[str, list[tuple[float, float]]] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            road_id = row["road_id"].strip()
            points = roads.setdefault(road_id, [])
            start = (float(row["from_x_m"]), float(row["from_y_m"]))
            end = (float(row["to_x_m"]), float(row["to_y_m"]))
            if not points:
                points.append(start)
            elif points[-1] != start:
                raise ValueError(f"Road {road_id} is not ordered at segment {row.get('segment_id', '')}")
            if end not in points:
                points.append(end)
    if not roads:
        raise ValueError("No tentative road corridor rows found")
    return roads


def load_approved_road_ids(path: str | Path) -> set[str]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return {
            row["road_id"].strip()
            for row in csv.DictReader(handle)
            if row.get("approved", "").strip().lower() in {"true", "yes", "1"}
        }
