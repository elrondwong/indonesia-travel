#!/usr/bin/env python3
"""Check whether Gannan order-level inputs are ready for booking research."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "gannan_order_inputs.template.json"

REQUIRED_FIELDS = [
    ("trip.origin_city", "出发城市"),
    ("trip.departure_date", "出发日期"),
    ("trip.return_date", "返程日期"),
    ("trip.travelers", "人数"),
    ("trip.rooms", "房间数"),
    ("trip.transport_preference", "交通偏好：包车/自驾/待比较"),
    ("trip.hotel_budget_per_room_night", "每间夜酒店预算"),
    ("preferences.camera_gear", "摄影器材"),
    ("preferences.max_daily_drive_hours", "可接受日均车程"),
]

RECOMMENDED_FIELDS = [
    ("trip.total_budget", "总预算"),
    ("constraints.luggage_needs", "行李/托运需求"),
    ("constraints.flight_refund_preference", "机票退改偏好"),
    ("constraints.latest_return_arrival_time", "返程最晚到达时间"),
    ("contacts.primary_contact", "主要联系人"),
]


def get_value(data: dict[str, Any], dotted: str) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float)):
        return value > 0
    return True


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"input file not found: {path}", file=sys.stderr)
        return 2

    data = json.loads(path.read_text(encoding="utf-8"))
    missing_required = [
        label for field, label in REQUIRED_FIELDS if not is_filled(get_value(data, field))
    ]
    missing_recommended = [
        label for field, label in RECOMMENDED_FIELDS if not is_filled(get_value(data, field))
    ]

    if missing_required:
        print("订单级核验还不能开始，缺少必填信息：")
        for label in missing_required:
            print(f"- {label}")
        if missing_recommended:
            print("\n建议也补充：")
            for label in missing_recommended:
                print(f"- {label}")
        return 1

    print("订单级核验输入已具备，可以开始比价：机票/高铁、酒店、包车/租车、门票预约。")
    if missing_recommended:
        print("\n建议补充但不阻塞：")
        for label in missing_recommended:
            print(f"- {label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
