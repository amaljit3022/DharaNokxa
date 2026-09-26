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


def load_tentative_intersections(path: str | Path) -> dict[str, list[str]]:
    """Load ordered intersection IDs parallel to ``load_tentative_corridors``."""
    roads: dict[str, list[str]] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            road_id = row["road_id"].strip()
            ids = roads.setdefault(road_id, [])
            start_id = row["intersection_from_id"].strip()
            end_id = row["intersection_to_id"].strip()
            if not ids:
                ids.append(start_id)
            elif ids[-1] != start_id:
                raise ValueError(f"Road {road_id} is not ordered at intersection {start_id}")
            if end_id not in ids:
                ids.append(end_id)
    if not roads:
        raise ValueError("No tentative road intersections found")
    return roads


def load_approved_crossings(path: str | Path) -> dict[str, set[str]]:
    """Return approved road IDs grouped by their explicit intersection ID."""
    crossings: dict[str, set[str]] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row.get("approved", "").strip().lower() not in {"true", "yes", "1"}:
                continue
            intersection_id = row["intersection_id"].strip()
            crossings.setdefault(intersection_id, set()).add(row["road_id"].strip())
    return crossings


def load_approved_road_ids(path: str | Path) -> set[str]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return {
            row["road_id"].strip()
            for row in csv.DictReader(handle)
            if row.get("approved", "").strip().lower() in {"true", "yes", "1"}
        }
