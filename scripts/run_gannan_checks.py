#!/usr/bin/env python3
"""Run the full local Gannan guide verification suite."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ACTUAL_CANDIDATE_FILES = [
    "data/gannan_flight_candidates.csv",
    "data/gannan_hotel_candidates.csv",
    "data/gannan_transport_quotes.csv",
    "data/gannan_ticket_candidates.csv",
]


def run_step(name: str, cmd: list[str], required: bool = True) -> bool:
    print(f"\n== {name} ==", flush=True)
    print("$ " + " ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=ROOT, text=True)
    if result.returncode == 0:
        return True

    if required:
        print(f"{name} failed with exit code {result.returncode}", file=sys.stderr)
        return False

    print(f"{name} skipped/failed without blocking: exit code {result.returncode}")
    return True


def existing_actual_candidates() -> bool:
    return all((ROOT / path).exists() for path in ACTUAL_CANDIDATE_FILES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="skip regenerating Pandoc HTML pages")
    parser.add_argument("--online-sources", action="store_true", help="probe source ledger URLs")
    parser.add_argument("--strict-online", action="store_true", help="fail when online source probes cannot reach a URL")
    parser.add_argument("--source-timeout", type=float, default=5.0, help="per-source online timeout in seconds")
    parser.add_argument("--source-workers", type=int, default=10, help="number of concurrent source probes")
    parser.add_argument("--actual", action="store_true", help="also validate filled order input, candidate, and re-verification files")
    args = parser.parse_args()

    source_health_cmd = ["python3", "scripts/gannan_source_health_report.py"]
    source_fallback_cmd = ["python3", "scripts/gannan_source_fallbacks.py"]
    if args.online_sources:
        source_health_cmd.extend([
            "--online",
            "--timeout",
            str(args.source_timeout),
            "--workers",
            str(args.source_workers),
        ])
        if args.strict_online:
            source_health_cmd.append("--strict-online")
        source_fallback_cmd.extend([
            "--online",
            "--timeout",
            str(args.source_timeout),
            "--workers",
            str(args.source_workers),
        ])
        if args.strict_online:
            source_fallback_cmd.append("--strict-online")

    steps: list[tuple[str, list[str], bool]] = [
        ("Generate order verification report", ["python3", "scripts/gannan_order_report.py"], True),
        ("Generate candidate scorecard", ["python3", "scripts/gannan_candidate_scorecard.py"], True),
        ("Generate order start workflow", ["python3", "scripts/gannan_order_start.py"], True),
        ("Generate source health report", source_health_cmd, True),
        ("Generate source fallback report", source_fallback_cmd, True),
        ("Generate photo readiness gate", ["python3", "scripts/gannan_photo_readiness_gate.py"], True),
        ("Generate order handoff packet", ["python3", "scripts/gannan_order_handoff.py"], True),
        ("Generate booking decision gate", ["python3", "scripts/gannan_booking_gate.py"], True),
    ]
    if not args.skip_build:
        steps.append(("Build Gannan pages", ["python3", "scripts/build_gannan.py"], True))
    steps.append(("Generate goal completion audit", ["python3", "scripts/audit_gannan_goal_completion.py"], True))
    if not args.skip_build:
        steps.append(("Build goal audit page", ["python3", "scripts/build_gannan.py", "--only", "gannan-goal-audit.html"], True))

    source_cmd = ["python3", "scripts/check_gannan_sources.py"]
    if args.online_sources:
        source_cmd.extend([
            "--online",
            "--timeout",
            str(args.source_timeout),
            "--workers",
            str(args.source_workers),
        ])
        if args.strict_online:
            source_cmd.append("--strict-online")

    steps.extend([
        ("Verify Gannan package", ["python3", "scripts/verify_gannan.py"], True),
        ("Check light window calculator", ["python3", "scripts/gannan_light_windows.py", "--check"], True),
        ("Check photo spot coverage", ["python3", "scripts/check_gannan_photo_spots.py"], True),
        ("Check photo readiness gate", ["python3", "scripts/gannan_photo_readiness_gate.py", "--check"], True),
        ("Check order handoff packet", ["python3", "scripts/gannan_order_handoff.py", "--check"], True),
        ("Check order candidate templates", ["python3", "scripts/check_gannan_order_candidates.py"], True),
        ("Check candidate scorecard", ["python3", "scripts/gannan_candidate_scorecard.py", "--check"], True),
        ("Check order start workflow", ["python3", "scripts/gannan_order_start.py", "--check"], True),
        ("Check booking decision gate", ["python3", "scripts/gannan_booking_gate.py", "--check"], True),
        ("Check order coverage gate", ["python3", "scripts/check_gannan_order_coverage.py", "--check"], True),
        ("Check evidence archive", ["python3", "scripts/check_gannan_evidence.py"], True),
        ("Check re-verification schedule generator", ["python3", "scripts/gannan_reverification_schedule.py", "--check"], True),
        ("Check re-verification calendar exporter", ["python3", "scripts/gannan_reverification_calendar.py", "--check"], True),
        ("Check re-verification diff tracker", ["python3", "scripts/gannan_reverification_diff.py", "--check"], True),
        ("Check source ledger", source_cmd, True),
        ("Check source health report", ["python3", "scripts/gannan_source_health_report.py", "--check"], True),
        ("Check source fallback report", ["python3", "scripts/gannan_source_fallbacks.py", "--check"], True),
        ("Check re-verification log template", ["python3", "scripts/check_gannan_reverification_log.py", "data/gannan_reverification_log.template.csv"], True),
    ])

    if args.actual:
        steps.append(("Check filled order input", ["python3", "scripts/check_gannan_inputs.py", "data/gannan_order_inputs.json"], True))
        steps.append(("Check filled order candidates", ["python3", "scripts/check_gannan_order_candidates.py", *ACTUAL_CANDIDATE_FILES], True))
        steps.append(("Check filled candidate scorecard", ["python3", "scripts/gannan_candidate_scorecard.py", "--strict"], True))
        steps.append(("Check filled order coverage", ["python3", "scripts/check_gannan_order_coverage.py", "--strict"], True))
        steps.append(("Check filled re-verification log", ["python3", "scripts/check_gannan_reverification_log.py", "data/gannan_reverification_log.csv"], True))
        steps.append(("Check filled re-verification changes", ["python3", "scripts/gannan_reverification_diff.py", "--strict"], True))
        steps.append(("Check filled evidence files", ["python3", "scripts/check_gannan_evidence.py", "--strict"], True))
        steps.append(("Check filled photo readiness gate", ["python3", "scripts/gannan_photo_readiness_gate.py", "--strict"], True))
        steps.append(("Check filled booking decision gate", ["python3", "scripts/gannan_booking_gate.py", "--strict"], True))
        steps.append(("Generate strict order verification report", ["python3", "scripts/gannan_order_report.py", "--strict"], True))
        steps.append(("Audit full goal completion", ["python3", "scripts/audit_gannan_goal_completion.py", "--strict"], True))
    elif (ROOT / "data/gannan_order_inputs.json").exists() or existing_actual_candidates() or (ROOT / "data/gannan_reverification_log.csv").exists():
        print("Actual order files detected. Run with --actual to validate them as blocking checks.")

    for name, cmd, required in steps:
        if not run_step(name, cmd, required=required):
            return 1

    print("\nAll requested Gannan checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
