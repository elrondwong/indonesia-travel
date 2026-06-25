#!/usr/bin/env python3
"""Check local evidence files referenced by Gannan order verification data."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / "evidence" / "gannan"

ACTUAL_CANDIDATE_FILES = {
    "flight": ROOT / "data/gannan_flight_candidates.csv",
    "hotel": ROOT / "data/gannan_hotel_candidates.csv",
    "transport": ROOT / "data/gannan_transport_quotes.csv",
    "ticket": ROOT / "data/gannan_ticket_candidates.csv",
}

ACTUAL_LOG = ROOT / "data/gannan_reverification_log.csv"

ACTIVE_CANDIDATE_STATUSES = {"candidate", "shortlist", "booked", "watch", "backup"}
LOG_STATUSES_REQUIRING_EVIDENCE = {"pass", "watch", "fail", "blocked"}
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".heic", ".txt", ".md"}


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def clean(value: str | None) -> str:
    return (value or "").strip()


def split_refs(value: str) -> list[str]:
    refs: list[str] = []
    for chunk in value.replace(";", "|").split("|"):
        ref = chunk.strip()
        if ref:
            refs.append(ref)
    return refs


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}


def resolve_evidence_path(value: str) -> tuple[Path | None, str | None]:
    if is_url(value):
        return None, "evidence_file must point to a local archived file, not a URL"

    raw_path = Path(value)
    if raw_path.is_absolute():
        candidate = raw_path.resolve()
    elif raw_path.parts and raw_path.parts[0] == "evidence":
        candidate = (ROOT / raw_path).resolve()
    else:
        candidate = (EVIDENCE_ROOT / raw_path).resolve()

    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return candidate, "evidence path escapes the repository"
    return candidate, None


def check_ref(ref: str, context: str, warnings: list[str], errors: list[str], strict: bool) -> None:
    path, error = resolve_evidence_path(ref)
    if error:
        errors.append(f"{context}: {ref}: {error}")
        return
    assert path is not None

    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        warnings.append(f"{context}: {ref}: uncommon evidence extension {path.suffix or '(none)'}")

    if not path.exists() or not path.is_file():
        message = f"{context}: missing evidence file {path.relative_to(ROOT).as_posix()}"
        if strict:
            errors.append(message)
        else:
            warnings.append(message)


def check_candidate_rows(kind: str, rows: list[dict[str, str]], warnings: list[str], errors: list[str], strict: bool) -> int:
    checked = 0
    for index, row in enumerate(rows, start=2):
        status = clean(row.get("status"))
        option_id = clean(row.get("option_id")) or f"row {index}"
        context = f"{kind} candidate {option_id}"
        evidence = clean(row.get("evidence_file"))

        if status in ACTIVE_CANDIDATE_STATUSES and not evidence:
            message = f"{context}: active status {status} requires evidence_file"
            if strict:
                errors.append(message)
            else:
                warnings.append(message)
            continue

        for ref in split_refs(evidence):
            checked += 1
            check_ref(ref, context, warnings, errors, strict)
    return checked


def check_log_rows(rows: list[dict[str, str]], warnings: list[str], errors: list[str], strict: bool) -> int:
    checked = 0
    for index, row in enumerate(rows, start=2):
        status = clean(row.get("status"))
        item = clean(row.get("item")) or f"row {index}"
        round_value = clean(row.get("round")) or "round?"
        context = f"reverification {round_value} {item}"
        evidence = clean(row.get("evidence_file"))

        if status in LOG_STATUSES_REQUIRING_EVIDENCE and not evidence:
            message = f"{context}: status {status} requires evidence_file"
            if strict:
                errors.append(message)
            else:
                warnings.append(message)
            continue

        for ref in split_refs(evidence):
            checked += 1
            check_ref(ref, context, warnings, errors, strict)
    return checked


def main() -> int:
    global EVIDENCE_ROOT

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail when required or referenced evidence files are missing")
    parser.add_argument("--base", type=Path, default=EVIDENCE_ROOT, help="evidence archive root; defaults to evidence/gannan")
    args = parser.parse_args()

    EVIDENCE_ROOT = args.base if args.base.is_absolute() else ROOT / args.base

    warnings: list[str] = []
    errors: list[str] = []
    checked_refs = 0
    checked_rows = 0

    if not EVIDENCE_ROOT.exists():
        message = f"evidence root does not exist: {EVIDENCE_ROOT.relative_to(ROOT).as_posix()}"
        if args.strict:
            errors.append(message)
        else:
            warnings.append(message)

    for kind, path in ACTUAL_CANDIDATE_FILES.items():
        rows = read_rows(path)
        checked_rows += len(rows)
        checked_refs += check_candidate_rows(kind, rows, warnings, errors, args.strict)

    log_rows = read_rows(ACTUAL_LOG)
    checked_rows += len(log_rows)
    checked_refs += check_log_rows(log_rows, warnings, errors, args.strict)

    if errors:
        print("Gannan evidence checks failed:")
        for error in errors:
            print(f"- {error}")
        if warnings:
            print("\nWarnings:")
            for warning in warnings:
                print(f"- {warning}")
        return 1

    print("Gannan evidence checks passed.")
    print(f"Checked {checked_refs} evidence reference(s) across {checked_rows} actual data row(s).")
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
