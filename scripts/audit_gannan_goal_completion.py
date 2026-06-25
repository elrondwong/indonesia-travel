#!/usr/bin/env python3
"""Audit completion of the full Gannan travel-guide goal."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "甘南莲宝叶则_目标完成审计.md"

REQUIRED_STRATEGY_FILES = [
    "gannan-dashboard.html",
    "gannan.html",
    "gannan-photo-handbook.html",
    "gannan-photo-spot-check.html",
    "gannan-shot-list.html",
    "gannan-photo-readiness.html",
    "gannan-daily-cards.html",
    "gannan-light-astro.html",
    "gannan-order-workbench.html",
    "gannan-order-handoff.html",
    "gannan-order-start.html",
    "gannan-order-candidates.html",
    "gannan-candidate-scorecard.html",
    "gannan-order-coverage.html",
    "gannan-order-report.html",
    "gannan-booking-gate.html",
    "gannan-reverification-sop.html",
    "gannan-reverification-schedule.html",
    "gannan-reverification-calendar.html",
    "gannan-reverification-diff.html",
    "gannan-evidence-archive.html",
    "gannan-contingency-plan.html",
    "gannan-source-fallbacks.html",
]

REQUIRED_ACTUAL_FILES = [
    "data/gannan_order_inputs.json",
    "data/gannan_flight_candidates.csv",
    "data/gannan_hotel_candidates.csv",
    "data/gannan_transport_quotes.csv",
    "data/gannan_ticket_candidates.csv",
    "data/gannan_reverification_log.csv",
]

REQUIRED_ACTUAL_INPUTS = [
    ("trip.origin_city", "出发城市"),
    ("trip.departure_date", "出发日期"),
    ("trip.return_date", "返程日期"),
    ("trip.travelers", "人数"),
    ("trip.rooms", "房间数"),
    ("trip.transport_preference", "交通偏好"),
    ("trip.hotel_budget_per_room_night", "每间夜酒店预算"),
    ("preferences.camera_gear", "摄影器材"),
    ("preferences.max_daily_drive_hours", "可接受日均车程"),
]

ACTUAL_CANDIDATE_FILES = [
    "data/gannan_flight_candidates.csv",
    "data/gannan_hotel_candidates.csv",
    "data/gannan_transport_quotes.csv",
    "data/gannan_ticket_candidates.csv",
]


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(rel_path: str) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def read_json(rel_path: str) -> dict[str, Any]:
    path = ROOT / rel_path
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(rel_path: str) -> list[dict[str, str]]:
    path = ROOT / rel_path
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def get_value(data: dict[str, Any], dotted: str) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float)):
        return value > 0
    return True


def file_status(rel_path: str) -> str:
    path = ROOT / rel_path
    if not path.exists():
        return "missing"
    if path.is_file() and path.stat().st_size == 0:
        return "empty"
    return "present"


def audit_strategy() -> tuple[str, list[str]]:
    missing = [path for path in REQUIRED_STRATEGY_FILES if file_status(path) != "present"]
    main_text = read_text("甘南莲宝叶则_完整攻略.md")
    required_phrases = ["兰州", "甘南", "莲宝叶则", "9 天 8 晚", "扎尕那"]
    phrase_missing = [phrase for phrase in required_phrases if phrase not in main_text]

    issues = [f"缺少策略文件：{path}" for path in missing]
    issues.extend(f"主攻略缺少关键词：{phrase}" for phrase in phrase_missing)
    status = "proved" if not issues else "incomplete"
    return status, issues


def audit_photo_system() -> tuple[str, list[str]]:
    issues: list[str] = []
    photo_rows = read_csv_rows("data/gannan_photo_spots.csv")
    s_text = " / ".join(f"{row.get('priority', '')} {row.get('area', '')} {row.get('spot_name', '')}" for row in photo_rows)
    for required in ["S 扎尕那", "S 莲宝叶则"]:
        if required not in s_text:
            issues.append(f"机位 CSV 缺少 {required}")
    if len(photo_rows) < 10:
        issues.append("机位 CSV 少于 10 条，覆盖不足")

    shot_text = read_text("甘南莲宝叶则_大片交付清单.md")
    for phrase in ["封面级主图", "扎尕那", "莲宝叶则", "失败天气"]:
        if phrase not in shot_text:
            issues.append(f"出片清单缺少关键词：{phrase}")
    readiness_text = read_text("甘南莲宝叶则_出片准备闸门.md")
    for phrase in ["策略级可拍", "真实出发前仍需复核", "S 级机位池"]:
        if phrase not in readiness_text:
            issues.append(f"出片准备闸门缺少关键词：{phrase}")
    return ("proved" if not issues else "incomplete"), issues


def audit_verification_system() -> tuple[str, list[str]]:
    required_scripts = [
        "scripts/check_gannan_order_candidates.py",
        "scripts/check_gannan_order_coverage.py",
        "scripts/check_gannan_evidence.py",
        "scripts/gannan_reverification_schedule.py",
        "scripts/gannan_reverification_calendar.py",
        "scripts/gannan_reverification_diff.py",
        "scripts/gannan_order_report.py",
        "scripts/gannan_order_start.py",
        "scripts/gannan_candidate_scorecard.py",
        "scripts/gannan_order_handoff.py",
        "scripts/gannan_booking_gate.py",
        "scripts/gannan_photo_readiness_gate.py",
        "scripts/check_gannan_sources.py",
        "scripts/gannan_source_health_report.py",
        "scripts/gannan_source_fallbacks.py",
    ]
    issues = [f"缺少核验脚本：{path}" for path in required_scripts if file_status(path) != "present"]
    return ("proved" if not issues else "incomplete"), issues


def audit_actual_order_data() -> tuple[str, list[str]]:
    issues: list[str] = []
    for path in REQUIRED_ACTUAL_FILES:
        if file_status(path) != "present":
            issues.append(f"缺少真实订单文件：{path}")

    data = read_json("data/gannan_order_inputs.json")
    if data:
        for field, label in REQUIRED_ACTUAL_INPUTS:
            if not is_filled(get_value(data, field)):
                issues.append(f"出行信息未填：{label}")

    for path in ACTUAL_CANDIDATE_FILES:
        rows = read_csv_rows(path)
        if (ROOT / path).exists() and not rows:
            issues.append(f"真实候选表为空：{path}")

    log_rows = read_csv_rows("data/gannan_reverification_log.csv")
    if (ROOT / "data/gannan_reverification_log.csv").exists():
        completed = [row for row in log_rows if (row.get("status") or "").strip() != "n/a"]
        if not completed:
            issues.append("复核日志没有真实完成行，只有待复核任务不算订单级验证")

    evidence_files = [
        path for path in (ROOT / "evidence/gannan").glob("**/*")
        if path.is_file() and path.name != "README.md"
    ]
    if any((ROOT / path).exists() for path in REQUIRED_ACTUAL_FILES) and not evidence_files:
        issues.append("真实订单阶段缺少本地证据截图/确认记录")

    return ("proved" if not issues else "missing_actual_data"), issues


def build_audit() -> list[dict[str, Any]]:
    audits: list[dict[str, Any]] = []
    for requirement, checker in [
        ("参照印尼攻略形成甘南攻略包", audit_strategy),
        ("拍大片机位和交付体系", audit_photo_system),
        ("反复验证机制", audit_verification_system),
        ("机票/酒店/车辆/门票订单级验证", audit_actual_order_data),
    ]:
        status, issues = checker()
        audits.append({
            "requirement": requirement,
            "status": status,
            "issues": issues,
        })
    return audits


def render_markdown(audits: list[dict[str, Any]]) -> str:
    complete = all(item["status"] == "proved" for item in audits)
    lines = [
        "# 甘南 + 莲宝叶则目标完成审计",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "这份审计从原始目标出发，只判断当前证据是否足以证明完成。它不会因为页面存在就把动态机票、酒店、门票价格判定为已完成。",
        "",
        f"总体结论：{'已全部证明完成' if complete else '未全部完成，订单级验证仍缺真实数据'}",
        "",
        "| 要求 | 审计状态 | 证据/缺口 |",
        "|---|---|---|",
    ]
    for item in audits:
        if item["issues"]:
            detail = "<br>".join(item["issues"][:8])
            if len(item["issues"]) > 8:
                detail += f"<br>另有 {len(item['issues']) - 8} 项缺口"
        else:
            detail = "当前工作树证据足够。"
        lines.append(f"| {item['requirement']} | {item['status']} | {detail} |")

    lines.extend([
        "",
        "## 严格完成口径",
        "",
        "只有下面命令在真实订单文件存在时通过，才可以说完整目标已经完成：",
        "",
        "```bash",
        "python3 scripts/run_gannan_checks.py --actual",
        "python3 scripts/audit_gannan_goal_completion.py --strict",
        "```",
        "",
        "当前如果没有 `data/gannan_order_inputs.json`、真实候选 CSV、复核日志和证据截图，就只能判定为“攻略包和核验框架完成”，不能判定为“机票/酒店/门票已完成订单级验证”。",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--strict", action="store_true", help="fail unless every audited requirement is proved")
    parser.add_argument("--check", action="store_true", help="run deterministic structure check")
    args = parser.parse_args()

    audits = build_audit()
    if args.check:
        names = {item["requirement"] for item in audits}
        required = {"参照印尼攻略形成甘南攻略包", "拍大片机位和交付体系", "反复验证机制", "机票/酒店/车辆/门票订单级验证"}
        if names != required:
            print("Gannan goal audit self-check failed.")
            return 1
        print("Gannan goal audit self-check passed.")
        print(f"Audited {len(audits)} requirement groups.")
        return 0

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.write_text(render_markdown(audits), encoding="utf-8")
    print(f"Generated {rel(output)}")

    incomplete = [item for item in audits if item["status"] != "proved"]
    if args.strict and incomplete:
        print("Gannan goal completion audit failed:")
        for item in incomplete:
            print(f"- {item['requirement']}: {len(item['issues'])} issue(s)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
