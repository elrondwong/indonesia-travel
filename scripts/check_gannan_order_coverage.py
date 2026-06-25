#!/usr/bin/env python3
"""Check whether filled Gannan order candidates cover the full trip scope."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ACTUAL_FILES = {
    "flight": ROOT / "data/gannan_flight_candidates.csv",
    "hotel": ROOT / "data/gannan_hotel_candidates.csv",
    "transport": ROOT / "data/gannan_transport_quotes.csv",
    "ticket": ROOT / "data/gannan_ticket_candidates.csv",
}

ACTIVE_STATUSES = {"candidate", "shortlist", "booked", "watch", "backup"}
BOOKING_READY_STATUSES = {"shortlist", "booked", "backup"}

REQUIRED_HOTEL_DAYS = [f"D{day}" for day in range(1, 9)]
CORE_HOTEL_AREAS = ["夏河", "合作", "扎尕那", "唐克", "若尔盖", "阿坝", "临夏"]
CORE_TICKETS = ["拉卜楞", "扎尕那", "花湖", "黄河", "莲宝"]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def clean(value: str | None) -> str:
    return (value or "").strip()


def active(rows: list[dict[str, str]], *, booking_ready: bool = False) -> list[dict[str, str]]:
    statuses = BOOKING_READY_STATUSES if booking_ready else ACTIVE_STATUSES
    return [row for row in rows if clean(row.get("status")) in statuses]


def contains_any(value: str, needles: list[str]) -> bool:
    return any(needle in value for needle in needles)


def count_matching(rows: list[dict[str, str]], field: str, needles: list[str]) -> int:
    count = 0
    for row in rows:
        value = clean(row.get(field))
        if contains_any(value, needles):
            count += 1
    return count


def check_flights(rows: list[dict[str, str]], errors: list[str], warnings: list[str], booking_ready: bool) -> None:
    active_rows = active(rows, booking_ready=booking_ready)
    directions = [clean(row.get("direction")).lower() for row in active_rows]
    outbound = [direction for direction in directions if direction in {"outbound", "train", "arrival", "to-lanzhou"}]
    returns = [direction for direction in directions if direction in {"return", "back", "from-lanzhou"}]

    if not outbound:
        errors.append("大交通缺少去程候选：direction 需要包含 outbound/train/arrival/to-lanzhou。")
    if not returns:
        errors.append("大交通缺少返程候选：direction 需要包含 return/back/from-lanzhou。")
    if len(active_rows) < 2:
        warnings.append("大交通活跃候选少于 2 个；建议至少保留去程和返程各 1 个备选。")


def check_hotels(rows: list[dict[str, str]], errors: list[str], warnings: list[str], booking_ready: bool) -> None:
    active_rows = active(rows, booking_ready=booking_ready)
    covered_days = {clean(row.get("stay_day")) for row in active_rows}
    missing_days = [day for day in REQUIRED_HOTEL_DAYS if day not in covered_days]
    if missing_days:
        errors.append(f"酒店缺少住宿日覆盖：{', '.join(missing_days)}。")

    areas = " / ".join(clean(row.get("area")) for row in active_rows)
    missing_core = [area for area in CORE_HOTEL_AREAS if area not in areas]
    if "唐克" in missing_core and "若尔盖" not in missing_core:
        missing_core.remove("唐克")
    if "若尔盖" in missing_core and "唐克" not in missing_core:
        missing_core.remove("若尔盖")
    if missing_core:
        warnings.append(f"酒店区域未完整覆盖核心中转：{', '.join(missing_core)}。")

    zhagana_count = count_matching(active_rows, "area", ["扎尕那"])
    aba_count = count_matching(active_rows, "area", ["阿坝"])
    if zhagana_count < 2:
        warnings.append("扎尕那住宿候选少于 2 个；旺季建议保留 2-3 个可取消备选。")
    if aba_count < 2:
        warnings.append("阿坝县住宿候选少于 2 个；莲宝叶则前夜建议保留 2-3 个可取消备选。")


def check_transport(rows: list[dict[str, str]], errors: list[str], warnings: list[str], booking_ready: bool) -> None:
    active_rows = active(rows, booking_ready=booking_ready)
    if not active_rows:
        errors.append("车辆缺少活跃候选：至少需要 1 个包车/租车/司导方案。")
        return
    if len(active_rows) < 3 and not booking_ready:
        warnings.append("车辆候选少于 3 个；询价阶段建议至少比较 3 家。")

    night_policy_missing = [clean(row.get("option_id")) or "未命名候选" for row in active_rows if not clean(row.get("night_drive_policy"))]
    if night_policy_missing:
        warnings.append(f"车辆夜路政策未写清：{', '.join(night_policy_missing)}。")


def check_tickets(rows: list[dict[str, str]], errors: list[str], warnings: list[str], booking_ready: bool) -> None:
    active_rows = active(rows, booking_ready=booking_ready)
    scenic_text = " / ".join(clean(row.get("scenic_area")) for row in active_rows)
    missing = [name for name in CORE_TICKETS if name not in scenic_text]
    if missing:
        errors.append(f"门票/开放缺少核心景区覆盖：{', '.join(missing)}。")

    for name in ["扎尕那", "莲宝"]:
        count = count_matching(active_rows, "scenic_area", [name])
        if count < 2:
            warnings.append(f"{name}门票/开放候选少于 2 个来源；建议官方/OTA/酒店或景区电话交叉确认。")


def validate_coverage(data: dict[str, list[dict[str, str]]], *, strict: bool, booking_ready: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for kind, rows in data.items():
        if strict and not rows:
            errors.append(f"{kind} 实际候选表为空或不存在。")

    check_flights(data.get("flight", []), errors, warnings, booking_ready)
    check_hotels(data.get("hotel", []), errors, warnings, booking_ready)
    check_transport(data.get("transport", []), errors, warnings, booking_ready)
    check_tickets(data.get("ticket", []), errors, warnings, booking_ready)
    return errors, warnings


def sample_rows() -> dict[str, list[dict[str, str]]]:
    return {
        "flight": [
            {"option_id": "F1", "direction": "outbound", "status": "shortlist"},
            {"option_id": "F2", "direction": "return", "status": "shortlist"},
        ],
        "hotel": [
            {"option_id": "H1", "stay_day": "D1", "area": "夏河", "status": "shortlist"},
            {"option_id": "H2", "stay_day": "D2", "area": "合作", "status": "shortlist"},
            {"option_id": "H3", "stay_day": "D3", "area": "扎尕那", "status": "shortlist"},
            {"option_id": "H4", "stay_day": "D4", "area": "扎尕那", "status": "backup"},
            {"option_id": "H5", "stay_day": "D5", "area": "唐克", "status": "shortlist"},
            {"option_id": "H6", "stay_day": "D6", "area": "阿坝县", "status": "shortlist"},
            {"option_id": "H7", "stay_day": "D7", "area": "阿坝县", "status": "backup"},
            {"option_id": "H8", "stay_day": "D8", "area": "合作/临夏", "status": "shortlist"},
        ],
        "transport": [
            {"option_id": "C1", "status": "shortlist", "night_drive_policy": "不赶夜路"},
        ],
        "ticket": [
            {"option_id": "T1", "scenic_area": "拉卜楞寺", "status": "shortlist"},
            {"option_id": "T2", "scenic_area": "扎尕那", "status": "shortlist"},
            {"option_id": "T3", "scenic_area": "扎尕那", "status": "backup"},
            {"option_id": "T4", "scenic_area": "若尔盖花湖", "status": "shortlist"},
            {"option_id": "T5", "scenic_area": "黄河九曲第一湾", "status": "shortlist"},
            {"option_id": "T6", "scenic_area": "莲宝叶则", "status": "shortlist"},
            {"option_id": "T7", "scenic_area": "莲宝叶则", "status": "backup"},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail when actual candidates do not cover required trip scope")
    parser.add_argument("--booking-ready", action="store_true", help="only count shortlist/booked/backup rows as covered")
    parser.add_argument("--check", action="store_true", help="run deterministic self-check with sample rows")
    args = parser.parse_args()

    if args.check:
        errors, warnings = validate_coverage(sample_rows(), strict=True, booking_ready=True)
        if errors:
            print("Gannan order coverage self-check failed:")
            for error in errors:
                print(f"- {error}")
            return 1
        print("Gannan order coverage self-check passed.")
        print(f"Warnings in sample: {len(warnings)}")
        return 0

    data = {kind: read_rows(path) for kind, path in ACTUAL_FILES.items()}
    actual_rows = sum(len(rows) for rows in data.values())
    if actual_rows == 0 and not args.strict:
        print("Gannan order coverage check skipped.")
        print("No actual candidate rows found; run with --strict after filling candidate CSV files.")
        return 0

    errors, warnings = validate_coverage(data, strict=args.strict, booking_ready=args.booking_ready)
    if errors:
        print("Gannan order coverage failed:")
        for error in errors:
            print(f"- {error}")
        if warnings:
            print("\nWarnings:")
            for warning in warnings:
                print(f"- {warning}")
        return 1

    print("Gannan order coverage passed.")
    print(f"Checked {actual_rows} actual candidate row(s).")
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
