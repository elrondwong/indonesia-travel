#!/usr/bin/env python3
"""Validate the Gannan source ledger and optionally check URL reachability."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "data/gannan_source_ledger.csv"

REQUIRED_COLUMNS = [
    "id",
    "category",
    "item",
    "source_name",
    "priority",
    "url",
    "verify_use",
    "rounds",
    "fallback",
    "notes",
]

VALID_CATEGORIES = {"flight", "hotel", "car", "ticket", "route", "photo", "drone", "health", "insurance", "budget", "weather"}
VALID_PRIORITIES = {"A", "B", "C"}
VALID_ROUNDS = {"T-14", "T-7", "T-3", "T-1", "D-day"}
SOFT_HTTP_STATUSES = {403, 405, 429}


def read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    if not path.exists():
        return [], [f"missing file: {path}"]

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != REQUIRED_COLUMNS:
            found = ",".join(reader.fieldnames or [])
            expected = ",".join(REQUIRED_COLUMNS)
            return [], [f"CSV header does not match template; expected {expected}; found {found}"]
        rows = list(reader)

    return rows, errors


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()

    for index, row in enumerate(rows, start=2):
        source_id = row["id"].strip()
        if not source_id:
            errors.append(f"row {index}: missing id")
        elif source_id in seen_ids:
            errors.append(f"row {index}: duplicate id {source_id}")
        seen_ids.add(source_id)

        for field in REQUIRED_COLUMNS:
            if field != "notes" and not row[field].strip():
                errors.append(f"row {index}: missing {field}")

        category = row["category"].strip()
        if category and category not in VALID_CATEGORIES:
            errors.append(f"row {index}: invalid category {category}")

        priority = row["priority"].strip()
        if priority and priority not in VALID_PRIORITIES:
            errors.append(f"row {index}: invalid priority {priority}")

        parsed = urlparse(row["url"].strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"row {index}: invalid url {row['url']}")

        for round_value in row["rounds"].split("|"):
            round_value = round_value.strip()
            if round_value and round_value not in VALID_ROUNDS:
                errors.append(f"row {index}: invalid round {round_value}")

    return errors


def probe_url(url: str, timeout: float) -> tuple[str, str]:
    cmd = [
        "curl",
        "--location",
        "--head",
        "--silent",
        "--show-error",
        "--output",
        "/dev/null",
        "--write-out",
        "%{http_code}",
        "--connect-timeout",
        str(timeout),
        "--max-time",
        str(timeout),
        "--user-agent",
        "Mozilla/5.0 GannanGuideSourceChecker/1.0",
        url,
    ]
    try:
        result = subprocess.run(
            cmd,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout + 2,
        )
    except subprocess.TimeoutExpired:
        return "fail", "timeout"
    except OSError as error:
        return "fail", str(error)

    http_code = (result.stdout or "").strip()[-3:]
    if not http_code.isdigit():
        return "fail", (result.stderr or "no HTTP status").strip()

    code = int(http_code)
    if 200 <= code < 400:
        return "pass", http_code
    if code in SOFT_HTTP_STATUSES:
        return "manual", http_code
    if code == 404:
        return "fail", "404"
    if code == 0:
        return "fail", (result.stderr or "curl returned HTTP 000").strip()
    return "warn", http_code


def check_online(rows: list[dict[str, str]], timeout: float, workers: int) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_row = {
            executor.submit(probe_url, row["url"].strip(), timeout): row
            for row in rows
        }
        completed = concurrent.futures.as_completed(future_to_row)
        for future in completed:
            row = future_to_row[future]
            status, detail = future.result()
            if status == "fail":
                errors.append(f"{row['id']}: {detail} ({row['url']})")
            elif status in {"warn", "manual"}:
                warnings.append(f"{row['id']}: HTTP {detail}; open manually if needed")
    return warnings, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", nargs="?", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--online", action="store_true", help="probe external URLs and report manual-review warnings")
    parser.add_argument("--strict-online", action="store_true", help="fail when an online probe cannot reach a source")
    parser.add_argument("--timeout", type=float, default=8.0, help="per-link timeout in seconds")
    parser.add_argument("--workers", type=int, default=8, help="number of concurrent online probes")
    args = parser.parse_args()

    rows, read_errors = read_rows(args.ledger)
    errors = read_errors + validate_rows(rows)
    warnings: list[str] = []

    if not errors and args.online:
        online_warnings, online_errors = check_online(rows, args.timeout, max(1, args.workers))
        warnings.extend(online_warnings)
        if args.strict_online:
            errors.extend(online_errors)
        else:
            warnings.extend(online_errors)

    if errors:
        print("Gannan source ledger failed:")
        for error in errors:
            print(f"- {error}")
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"- {warning}")
        return 1

    print("Gannan source ledger passed.")
    print(f"Checked {len(rows)} sources.")
    if warnings:
        print("Manual review warnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
