#!/usr/bin/env python3
"""Validate structured Gannan photo spot coverage."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data/gannan_photo_spots.csv"

COLUMNS = [
    "spot_id",
    "day",
    "priority",
    "area",
    "spot_name",
    "search_keyword",
    "map_url",
    "golden_window",
    "primary_lens",
    "required_output",
    "verification_sources",
    "access_risk",
    "abort_condition",
    "status",
    "notes",
]

REQUIRED_FIELDS = [
    "spot_id",
    "day",
    "priority",
    "area",
    "spot_name",
    "search_keyword",
    "golden_window",
    "primary_lens",
    "required_output",
    "verification_sources",
    "access_risk",
    "abort_condition",
    "status",
]

VALID_PRIORITIES = {"S", "A", "B"}
VALID_STATUSES = {"planned", "verified", "watch", "closed", "skipped", "backup"}
REQUIRED_S_SPOTS = ["扎尕那", "莲宝叶则"]
REQUIRED_A_SPOTS = ["拉卜楞", "白石崖", "黄河九曲"]
REQUIRED_DAYS = {"D1", "D2", "D3", "D4", "D5", "D7"}


def clean(value: str | None) -> str:
    return (value or "").strip()


def day_tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    for part in value.replace("，", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = [piece.strip() for piece in part.split("-", 1)]
            if left.startswith("D") and right.startswith("D"):
                try:
                    start = int(left[1:])
                    end = int(right[1:])
                except ValueError:
                    tokens.add(part)
                else:
                    for day in range(start, end + 1):
                        tokens.add(f"D{day}")
            else:
                tokens.add(part)
        else:
            tokens.add(part)
    return tokens


def validate_url(value: str, row_number: int, errors: list[str]) -> None:
    if not value:
        return
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        errors.append(f"row {row_number}: map_url must be http(s) when present")


def read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], [f"missing file: {path}"]
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            expected = ",".join(COLUMNS)
            found = ",".join(reader.fieldnames or [])
            return [], [f"CSV header mismatch; expected {expected}; found {found}"]
        return list(reader), []


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    covered_days: set[str] = set()

    for index, row in enumerate(rows, start=2):
        spot_id = clean(row.get("spot_id"))
        if spot_id:
            if spot_id in seen_ids:
                errors.append(f"row {index}: duplicate spot_id {spot_id}")
            seen_ids.add(spot_id)

        for field in REQUIRED_FIELDS:
            if not clean(row.get(field)):
                errors.append(f"row {index}: missing required field {field}")

        priority = clean(row.get("priority"))
        if priority and priority not in VALID_PRIORITIES:
            errors.append(f"row {index}: invalid priority {priority}")

        status = clean(row.get("status"))
        if status and status not in VALID_STATUSES:
            errors.append(f"row {index}: invalid status {status}")

        validate_url(clean(row.get("map_url")), index, errors)
        covered_days.update(day_tokens(clean(row.get("day"))))

    text = " / ".join(f"{clean(row.get('area'))} {clean(row.get('spot_name'))}" for row in rows)
    for required in REQUIRED_S_SPOTS:
        if not any(clean(row.get("priority")) == "S" and required in f"{clean(row.get('area'))} {clean(row.get('spot_name'))}" for row in rows):
            errors.append(f"missing S-level photo spot for {required}")
    for required in REQUIRED_A_SPOTS:
        if not any(clean(row.get("priority")) in {"S", "A"} and required in f"{clean(row.get('area'))} {clean(row.get('spot_name'))}" for row in rows):
            errors.append(f"missing A-level or better photo spot for {required}")

    missing_days = sorted(REQUIRED_DAYS - covered_days, key=lambda item: int(item[1:]))
    if missing_days:
        errors.append(f"missing photo spot day coverage: {', '.join(missing_days)}")
    if "扎尕那" not in text or "莲宝叶则" not in text:
        errors.append("missing core area text for 扎尕那 or 莲宝叶则")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()

    path = args.path if args.path.is_absolute() else ROOT / args.path
    rows, errors = read_rows(path)
    if not errors:
        errors = validate_rows(rows)

    if errors:
        print("Gannan photo spot checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    counts = {priority: sum(1 for row in rows if clean(row.get("priority")) == priority) for priority in sorted(VALID_PRIORITIES)}
    print("Gannan photo spot checks passed.")
    print(f"Checked {len(rows)} photo spots: S={counts['S']}, A={counts['A']}, B={counts['B']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
