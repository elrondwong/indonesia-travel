#!/usr/bin/env python3
"""Validate a filled Gannan re-verification CSV log."""

from __future__ import annotations

import csv
import sys
from pathlib import Path


REQUIRED_COLUMNS = [
    "round",
    "check_date",
    "category",
    "item",
    "source",
    "source_url_or_contact",
    "quoted_price_cny",
    "evidence_file",
    "status",
    "decision",
    "next_action",
    "owner",
    "next_check_date",
    "notes",
]

REQUIRED_ROW_FIELDS = [
    "round",
    "check_date",
    "category",
    "item",
    "source",
    "status",
    "decision",
    "owner",
]

VALID_STATUSES = {"pass", "watch", "fail", "blocked", "n/a"}
VALID_ROUNDS = {"T-14", "T-7", "T-3", "T-1", "D-day"}
VALID_CATEGORIES = {"flight", "hotel", "car", "ticket", "route", "photo", "drone", "health", "insurance", "budget"}


def validate_price(value: str, row_number: int, errors: list[str]) -> None:
    if not value:
        return
    try:
        price = float(value)
    except ValueError:
        errors.append(f"row {row_number}: quoted_price_cny must be numeric or empty")
        return
    if price < 0:
        errors.append(f"row {row_number}: quoted_price_cny cannot be negative")


def validate(path: Path) -> int:
    if not path.exists():
        print(f"missing file: {path}", file=sys.stderr)
        return 1

    errors: list[str] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != REQUIRED_COLUMNS:
            print("Gannan re-verification log failed:")
            print("- CSV header does not match the template")
            print(f"- expected: {','.join(REQUIRED_COLUMNS)}")
            print(f"- found: {','.join(reader.fieldnames or [])}")
            return 1

        rows = list(reader)

    for index, row in enumerate(rows, start=2):
        for field in REQUIRED_ROW_FIELDS:
            if not (row.get(field) or "").strip():
                errors.append(f"row {index}: missing required field {field}")

        round_value = (row.get("round") or "").strip()
        if round_value and round_value not in VALID_ROUNDS:
            errors.append(f"row {index}: invalid round {round_value}")

        category = (row.get("category") or "").strip()
        if category and category not in VALID_CATEGORIES:
            errors.append(f"row {index}: invalid category {category}")

        status = (row.get("status") or "").strip()
        if status and status not in VALID_STATUSES:
            errors.append(f"row {index}: invalid status {status}")

        validate_price((row.get("quoted_price_cny") or "").strip(), index, errors)

    if errors:
        print("Gannan re-verification log failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Gannan re-verification log passed.")
    print(f"Checked {len(rows)} log rows.")
    return 0


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/gannan_reverification_log.csv")
    return validate(path)


if __name__ == "__main__":
    sys.exit(main())
