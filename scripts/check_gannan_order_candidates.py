#!/usr/bin/env python3
"""Validate Gannan order candidate CSV files."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TEMPLATES = {
    "flight": {
        "path": ROOT / "data/gannan_flight_candidates.template.csv",
        "columns": [
            "option_id",
            "direction",
            "platform",
            "carrier_or_railway",
            "flight_or_train_no",
            "origin",
            "destination",
            "depart_date",
            "depart_time",
            "arrival_date",
            "arrival_time",
            "final_price_cny",
            "baggage_or_luggage",
            "refund_change_policy",
            "arrival_transfer",
            "booking_url",
            "evidence_file",
            "status",
            "decision",
            "next_action",
            "notes",
        ],
        "required": [
            "option_id",
            "direction",
            "platform",
            "origin",
            "destination",
            "depart_date",
            "depart_time",
            "arrival_time",
            "final_price_cny",
            "baggage_or_luggage",
            "refund_change_policy",
            "status",
            "decision",
        ],
        "price_fields": ["final_price_cny"],
        "date_fields": ["depart_date", "arrival_date"],
        "time_fields": ["depart_time", "arrival_time"],
    },
    "hotel": {
        "path": ROOT / "data/gannan_hotel_candidates.template.csv",
        "columns": [
            "option_id",
            "stay_day",
            "area",
            "hotel_name",
            "platform_or_contact",
            "check_in",
            "check_out",
            "room_type",
            "rooms",
            "final_price_cny",
            "cancel_deadline",
            "parking_confirmed",
            "hot_water_heating_confirmed",
            "early_departure_confirmed",
            "breakfast_plan",
            "real_photo_checked",
            "contact_or_url",
            "evidence_file",
            "status",
            "decision",
            "next_action",
            "notes",
        ],
        "required": [
            "option_id",
            "stay_day",
            "area",
            "hotel_name",
            "check_in",
            "check_out",
            "room_type",
            "rooms",
            "final_price_cny",
            "cancel_deadline",
            "parking_confirmed",
            "hot_water_heating_confirmed",
            "early_departure_confirmed",
            "status",
            "decision",
        ],
        "price_fields": ["final_price_cny"],
        "date_fields": ["check_in", "check_out"],
        "time_fields": [],
    },
    "transport": {
        "path": ROOT / "data/gannan_transport_quotes.template.csv",
        "columns": [
            "option_id",
            "type",
            "supplier_or_driver",
            "vehicle_model",
            "seats",
            "luggage_capacity",
            "start_date",
            "end_date",
            "days",
            "total_price_cny",
            "includes_fuel",
            "includes_toll",
            "includes_parking",
            "driver_meals_lodging",
            "insurance_confirmed",
            "night_drive_policy",
            "cancellation_policy",
            "contact_or_url",
            "evidence_file",
            "status",
            "decision",
            "next_action",
            "notes",
        ],
        "required": [
            "option_id",
            "type",
            "supplier_or_driver",
            "vehicle_model",
            "seats",
            "luggage_capacity",
            "start_date",
            "end_date",
            "days",
            "total_price_cny",
            "insurance_confirmed",
            "night_drive_policy",
            "cancellation_policy",
            "status",
            "decision",
        ],
        "price_fields": ["total_price_cny"],
        "date_fields": ["start_date", "end_date"],
        "time_fields": [],
    },
    "ticket": {
        "path": ROOT / "data/gannan_ticket_candidates.template.csv",
        "columns": [
            "option_id",
            "scenic_area",
            "target_date",
            "platform_or_source",
            "ticket_type",
            "final_price_cny",
            "includes_shuttle_or_lift",
            "real_name_required",
            "refund_policy",
            "open_hours",
            "latest_entry",
            "latest_exit",
            "open_scope_confirmed",
            "booking_url_or_contact",
            "evidence_file",
            "status",
            "decision",
            "next_action",
            "notes",
        ],
        "required": [
            "option_id",
            "scenic_area",
            "target_date",
            "platform_or_source",
            "ticket_type",
            "final_price_cny",
            "refund_policy",
            "open_scope_confirmed",
            "status",
            "decision",
        ],
        "price_fields": ["final_price_cny"],
        "date_fields": ["target_date"],
        "time_fields": ["latest_entry", "latest_exit"],
    },
}

VALID_STATUSES = {"candidate", "shortlist", "booked", "watch", "rejected", "backup"}


def is_blank(value: str | None) -> bool:
    return not (value or "").strip()


def validate_date(value: str, field: str, row_number: int, errors: list[str]) -> None:
    if not value:
        return
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        errors.append(f"row {row_number}: {field} must be YYYY-MM-DD")


def validate_time(value: str, field: str, row_number: int, errors: list[str]) -> None:
    if not value:
        return
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        errors.append(f"row {row_number}: {field} must be HH:MM")


def validate_price(value: str, field: str, row_number: int, errors: list[str]) -> None:
    if not value:
        return
    try:
        price = float(value)
    except ValueError:
        errors.append(f"row {row_number}: {field} must be numeric")
        return
    if price < 0:
        errors.append(f"row {row_number}: {field} cannot be negative")


def infer_kind(path: Path) -> str | None:
    name = path.name
    if "flight" in name:
        return "flight"
    if "hotel" in name:
        return "hotel"
    if "transport" in name:
        return "transport"
    if "ticket" in name:
        return "ticket"
    return None


def validate_file(path: Path, kind: str) -> tuple[int, list[str]]:
    spec = TEMPLATES[kind]
    if not path.exists():
        return 0, [f"{path}: missing file"]

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != spec["columns"]:
            found = ",".join(reader.fieldnames or [])
            expected = ",".join(spec["columns"])
            return 0, [f"{path}: CSV header mismatch; expected {expected}; found {found}"]
        rows = list(reader)

    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=2):
        option_id = (row.get("option_id") or "").strip()
        if option_id:
            if option_id in seen_ids:
                errors.append(f"row {index}: duplicate option_id {option_id}")
            seen_ids.add(option_id)

        for field in spec["required"]:
            if is_blank(row.get(field)):
                errors.append(f"row {index}: missing required field {field}")

        status = (row.get("status") or "").strip()
        if status and status not in VALID_STATUSES:
            errors.append(f"row {index}: invalid status {status}")

        for field in spec["price_fields"]:
            validate_price((row.get(field) or "").strip(), field, index, errors)
        for field in spec["date_fields"]:
            validate_date((row.get(field) or "").strip(), field, index, errors)
        for field in spec["time_fields"]:
            validate_time((row.get(field) or "").strip(), field, index, errors)

    return len(rows), errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="candidate CSV files; defaults to all templates")
    args = parser.parse_args()

    targets: list[tuple[Path, str]] = []
    if args.paths:
        for path in args.paths:
            kind = infer_kind(path)
            if not kind:
                print(f"cannot infer candidate type from filename: {path}", file=sys.stderr)
                return 2
            targets.append((path if path.is_absolute() else ROOT / path, kind))
    else:
        targets = [(spec["path"], kind) for kind, spec in TEMPLATES.items()]

    total_rows = 0
    all_errors: list[str] = []
    for path, kind in targets:
        row_count, errors = validate_file(path, kind)
        total_rows += row_count
        all_errors.extend(f"{kind}: {error}" for error in errors)

    if all_errors:
        print("Gannan order candidate checks failed:")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print("Gannan order candidate checks passed.")
    print(f"Checked {len(targets)} files and {total_rows} candidate rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
