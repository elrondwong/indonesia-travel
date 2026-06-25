#!/usr/bin/env python3
"""Generate a readable Gannan order verification report from candidate CSVs."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from check_gannan_inputs import (
    RECOMMENDED_FIELDS,
    REQUIRED_FIELDS,
    get_value,
    is_filled,
)
from check_gannan_order_candidates import TEMPLATES, validate_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "甘南莲宝叶则_订单复核报告.md"

ACTUAL_CANDIDATE_FILES = {
    "flight": ROOT / "data/gannan_flight_candidates.csv",
    "hotel": ROOT / "data/gannan_hotel_candidates.csv",
    "transport": ROOT / "data/gannan_transport_quotes.csv",
    "ticket": ROOT / "data/gannan_ticket_candidates.csv",
}

ACTUAL_INPUT = ROOT / "data/gannan_order_inputs.json"
TEMPLATE_INPUT = ROOT / "data/gannan_order_inputs.template.json"
ACTUAL_LOG = ROOT / "data/gannan_reverification_log.csv"
TEMPLATE_LOG = ROOT / "data/gannan_reverification_log.template.csv"

KIND_LABELS = {
    "flight": "大交通",
    "hotel": "酒店",
    "transport": "包车/租车",
    "ticket": "门票",
}

STATUS_ORDER = ["booked", "shortlist", "watch", "backup", "candidate", "rejected"]
ACTIVE_STATUSES = {"booked", "shortlist", "watch", "backup", "candidate"}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def choose_candidate_file(kind: str) -> tuple[Path, str]:
    actual = ACTUAL_CANDIDATE_FILES[kind]
    if actual.exists():
        return actual, "actual"
    return TEMPLATES[kind]["path"], "template"


def price_field(kind: str) -> str:
    return "total_price_cny" if kind == "transport" else "final_price_cny"


def clean(value: str | None) -> str:
    return (value or "").strip()


def money(value: str | None) -> str:
    value = clean(value)
    if not value:
        return "-"
    try:
        number = float(value)
    except ValueError:
        return value
    if number.is_integer():
        return f"{int(number)}"
    return f"{number:.2f}"


def row_name(kind: str, row: dict[str, str]) -> str:
    if kind == "flight":
        carrier = clean(row.get("carrier_or_railway"))
        number = clean(row.get("flight_or_train_no"))
        route = f"{clean(row.get('origin'))}->{clean(row.get('destination'))}".strip("->")
        return " ".join(part for part in [carrier, number, route] if part) or clean(row.get("option_id")) or "-"
    if kind == "hotel":
        return clean(row.get("hotel_name")) or clean(row.get("area")) or clean(row.get("option_id")) or "-"
    if kind == "transport":
        supplier = clean(row.get("supplier_or_driver"))
        vehicle = clean(row.get("vehicle_model"))
        return " ".join(part for part in [supplier, vehicle] if part) or clean(row.get("option_id")) or "-"
    if kind == "ticket":
        scenic = clean(row.get("scenic_area"))
        ticket = clean(row.get("ticket_type"))
        return " ".join(part for part in [scenic, ticket] if part) or clean(row.get("option_id")) or "-"
    return clean(row.get("option_id")) or "-"


def row_context(kind: str, row: dict[str, str]) -> str:
    if kind == "flight":
        parts = [clean(row.get("direction")), clean(row.get("depart_date")), clean(row.get("depart_time"))]
    elif kind == "hotel":
        parts = [clean(row.get("stay_day")), clean(row.get("area")), f"{clean(row.get('check_in'))}->{clean(row.get('check_out'))}".strip("->")]
    elif kind == "transport":
        parts = [clean(row.get("type")), f"{clean(row.get('start_date'))}->{clean(row.get('end_date'))}".strip("->")]
    elif kind == "ticket":
        parts = [clean(row.get("target_date")), clean(row.get("platform_or_source"))]
    else:
        parts = []
    return " / ".join(part for part in parts if part) or "-"


def status_counts(rows: list[dict[str, str]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        status = clean(row.get("status")) or "blank"
        counts[status] += 1
    return counts


def price_range(kind: str, rows: list[dict[str, str]]) -> str:
    values: list[float] = []
    field = price_field(kind)
    for row in rows:
        value = clean(row.get(field))
        if not value:
            continue
        try:
            values.append(float(value))
        except ValueError:
            continue
    if not values:
        return "-"
    low = min(values)
    high = max(values)
    if low == high:
        return money(str(low))
    return f"{money(str(low))}-{money(str(high))}"


def count_missing(rows: list[dict[str, str]], field: str, *, active_only: bool = True) -> int:
    total = 0
    for row in rows:
        status = clean(row.get("status"))
        if active_only and status not in ACTIVE_STATUSES:
            continue
        if not clean(row.get(field)):
            total += 1
    return total


def collect_flags(kind: str, rows: list[dict[str, str]]) -> list[str]:
    flags: list[str] = []
    for row in rows:
        option_id = clean(row.get("option_id")) or row_name(kind, row)
        status = clean(row.get("status"))
        if status not in ACTIVE_STATUSES:
            continue

        if not clean(row.get("evidence_file")):
            flags.append(f"{KIND_LABELS[kind]} {option_id}: 缺证据截图或确认记录。")
        if not clean(row.get("next_action")) and status in {"candidate", "shortlist", "watch", "backup"}:
            flags.append(f"{KIND_LABELS[kind]} {option_id}: 缺下一步动作。")

        if kind == "flight":
            if not clean(row.get("baggage_or_luggage")):
                flags.append(f"大交通 {option_id}: 未确认行李/摄影器材口径。")
            if not clean(row.get("refund_change_policy")):
                flags.append(f"大交通 {option_id}: 未确认退改规则。")
        elif kind == "hotel":
            for field, label in [
                ("parking_confirmed", "停车"),
                ("hot_water_heating_confirmed", "热水/供暖"),
                ("early_departure_confirmed", "早出门"),
            ]:
                value = clean(row.get(field)).lower()
                if value in {"", "unknown", "no", "false"}:
                    flags.append(f"酒店 {option_id}: {label}未确认或为否。")
        elif kind == "transport":
            if not clean(row.get("insurance_confirmed")):
                flags.append(f"包车/租车 {option_id}: 未确认保险。")
            if not clean(row.get("night_drive_policy")):
                flags.append(f"包车/租车 {option_id}: 未写清夜路政策。")
        elif kind == "ticket":
            value = clean(row.get("open_scope_confirmed")).lower()
            if value in {"", "unknown", "no", "false"}:
                flags.append(f"门票 {option_id}: 开放范围未二次确认。")
            if not clean(row.get("refund_policy")):
                flags.append(f"门票 {option_id}: 未确认退改/取消规则。")
    return flags


def order_input_status() -> tuple[Path, str, list[str], list[str], dict[str, Any]]:
    path = ACTUAL_INPUT if ACTUAL_INPUT.exists() else TEMPLATE_INPUT
    mode = "actual" if ACTUAL_INPUT.exists() else "template"
    data = read_json(path)
    missing_required = [
        label for field, label in REQUIRED_FIELDS if not is_filled(get_value(data, field))
    ]
    missing_recommended = [
        label for field, label in RECOMMENDED_FIELDS if not is_filled(get_value(data, field))
    ]
    return path, mode, missing_required, missing_recommended, data


def log_status() -> tuple[Path, str, list[dict[str, str]], Counter[str], list[str]]:
    path = ACTUAL_LOG if ACTUAL_LOG.exists() else TEMPLATE_LOG
    mode = "actual" if ACTUAL_LOG.exists() else "template"
    _, rows = read_csv_rows(path)
    counts: Counter[str] = Counter(clean(row.get("status")) or "blank" for row in rows)
    next_dates = sorted({clean(row.get("next_check_date")) for row in rows if clean(row.get("next_check_date"))})
    return path, mode, rows, counts, next_dates


def candidate_sections(strict: bool) -> tuple[list[str], dict[str, Any], list[str], list[str]]:
    lines: list[str] = []
    data_by_kind: dict[str, Any] = {}
    all_flags: list[str] = []
    validation_errors: list[str] = []

    for kind in ["flight", "hotel", "transport", "ticket"]:
        path, mode = choose_candidate_file(kind)
        row_count, errors = validate_file(path, kind)
        if errors:
            validation_errors.extend(f"{KIND_LABELS[kind]} {error}" for error in errors)
        _, rows = read_csv_rows(path)
        counts = status_counts(rows)
        flags = collect_flags(kind, rows)
        all_flags.extend(flags)
        data_by_kind[kind] = {
            "path": path,
            "mode": mode,
            "rows": rows,
            "row_count": row_count,
            "counts": counts,
            "flags": flags,
        }

    if validation_errors and strict:
        return lines, data_by_kind, all_flags, validation_errors

    lines.append("## 候选数据概览")
    lines.append("")
    lines.append("| 类型 | 数据文件 | 模式 | 候选数 | 已订 | 短名单 | 观察 | 备份 | 淘汰 | 价格范围 | 缺证据 | 缺下一步 |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|")
    for kind in ["flight", "hotel", "transport", "ticket"]:
        item = data_by_kind[kind]
        rows = item["rows"]
        counts = item["counts"]
        lines.append(
            "| {label} | [{file}]({file}) | {mode} | {total} | {booked} | {shortlist} | {watch} | {backup} | {rejected} | {price} | {evidence} | {next_action} |".format(
                label=KIND_LABELS[kind],
                file=rel(item["path"]),
                mode="真实" if item["mode"] == "actual" else "模板",
                total=len(rows),
                booked=counts.get("booked", 0),
                shortlist=counts.get("shortlist", 0),
                watch=counts.get("watch", 0),
                backup=counts.get("backup", 0),
                rejected=counts.get("rejected", 0),
                price=price_range(kind, rows),
                evidence=count_missing(rows, "evidence_file"),
                next_action=count_missing(rows, "next_action"),
            )
        )
    lines.append("")

    lines.append("## 各类候选短名单")
    lines.append("")
    for kind in ["flight", "hotel", "transport", "ticket"]:
        item = data_by_kind[kind]
        rows = sorted(
            item["rows"],
            key=lambda row: (
                STATUS_ORDER.index(clean(row.get("status"))) if clean(row.get("status")) in STATUS_ORDER else 99,
                clean(row.get("option_id")),
            ),
        )
        lines.append(f"### {KIND_LABELS[kind]}")
        lines.append("")
        if not rows:
            lines.append("暂无真实候选。先复制模板并填入至少 2-3 个可比较方案。")
            lines.append("")
            continue
        lines.append("| 状态 | ID | 名称 | 日期/区域 | 价格 | 证据 | 下一步 |")
        lines.append("|---|---|---|---|---:|---|---|")
        for row in rows[:8]:
            lines.append(
                "| {status} | {option_id} | {name} | {context} | {price} | {evidence} | {next_action} |".format(
                    status=clean(row.get("status")) or "-",
                    option_id=clean(row.get("option_id")) or "-",
                    name=row_name(kind, row),
                    context=row_context(kind, row),
                    price=money(row.get(price_field(kind))),
                    evidence=clean(row.get("evidence_file")) or "-",
                    next_action=clean(row.get("next_action")) or "-",
                )
            )
        if len(rows) > 8:
            lines.append(f"| ... | ... | 另有 {len(rows) - 8} 条候选 | ... | ... | ... | ... |")
        lines.append("")

    return lines, data_by_kind, all_flags, validation_errors


def conclusion(
    missing_required: list[str],
    data_by_kind: dict[str, Any],
    all_flags: list[str],
    log_rows: list[dict[str, str]],
) -> list[str]:
    actual_candidate_kinds = [kind for kind, item in data_by_kind.items() if item["mode"] == "actual"]
    total_rows = sum(len(item["rows"]) for item in data_by_kind.values())
    booked_rows = sum(item["counts"].get("booked", 0) for item in data_by_kind.values())
    shortlist_rows = sum(item["counts"].get("shortlist", 0) for item in data_by_kind.values())

    lines = ["## 当前结论", ""]
    if missing_required:
        lines.append("- 订单级核验还未开始：出行信息必填项没有补齐，当前不能写死机票、酒店或门票成交价。")
    elif not actual_candidate_kinds:
        lines.append("- 出行信息已可用于比价，但还没有真实候选 CSV；下一步是复制模板并录入航班/酒店/车辆/门票候选。")
    elif total_rows == 0:
        lines.append("- 已进入真实候选文件阶段，但候选表仍为空；先每类录入 2-3 个方案。")
    elif booked_rows:
        lines.append(f"- 已有 {booked_rows} 个已订项目；继续检查证据截图、取消规则和下一轮复核日期。")
    elif shortlist_rows:
        lines.append(f"- 已有 {shortlist_rows} 个短名单项目；可以继续谈价、电话确认和准备下单。")
    else:
        lines.append("- 已有候选数据，但还没有短名单或已订项；先按红旗清单淘汰风险方案。")

    if total_rows == 0:
        lines.append("- 候选表目前为空，红旗检查只能覆盖模板结构；真实订单安全性还没有证据。")
    elif all_flags:
        lines.append(f"- 当前仍有 {len(all_flags)} 个复核红旗，尤其要补齐证据截图、下一步动作和开放/停车/热水等现场条件。")
    else:
        lines.append("- 当前候选数据没有触发结构化红旗；仍需按 T-14/T-7/T-3/T-1 继续复核动态价格和开放状态。")

    if not log_rows:
        lines.append("- 反复复核日志还没有真实记录；第一次人工查价后，把来源、截图和下一次复核日期写入 CSV。")
    return lines + [""]


def render_report(strict: bool) -> tuple[str, list[str]]:
    input_path, input_mode, missing_required, missing_recommended, input_data = order_input_status()
    candidate_lines, data_by_kind, all_flags, validation_errors = candidate_sections(strict=strict)
    log_path, log_mode, log_rows, log_counts, next_dates = log_status()

    lines: list[str] = [
        "# 甘南 + 莲宝叶则订单复核报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "候选评分卡：[甘南莲宝叶则_候选评分卡.md](甘南莲宝叶则_候选评分卡.md)  ",
        "订单覆盖闸门：[甘南莲宝叶则_订单覆盖率闸门.md](甘南莲宝叶则_订单覆盖率闸门.md)  ",
        "下单决策闸门：[甘南莲宝叶则_下单决策闸门.md](甘南莲宝叶则_下单决策闸门.md)",
        "",
        "这份报告把机票/高铁、酒店、包车/租车、门票候选和复核日志汇总成一张可读清单。它只报告当前 CSV 与 JSON 证据，不替代实际下单页、酒店电话、景区公告或现场牌示。",
        "",
    ]

    lines.extend(conclusion(missing_required, data_by_kind, all_flags, log_rows))

    lines.extend([
        "## 出行信息状态",
        "",
        f"- 输入文件：[{rel(input_path)}]({rel(input_path)})",
        f"- 模式：{'真实输入' if input_mode == 'actual' else '模板'}",
        f"- 路线版本：{clean(str(get_value(input_data, 'trip.route_version') or '')) or '-'}",
        f"- 出发城市：{clean(str(get_value(input_data, 'trip.origin_city') or '')) or '-'}",
        f"- 出发日期：{clean(str(get_value(input_data, 'trip.departure_date') or '')) or '-'}",
        f"- 返程日期：{clean(str(get_value(input_data, 'trip.return_date') or '')) or '-'}",
        f"- 人数/房间：{clean(str(get_value(input_data, 'trip.travelers') or '')) or '-'} / {clean(str(get_value(input_data, 'trip.rooms') or '')) or '-'}",
        "",
    ])

    if missing_required:
        lines.append("必填信息缺口：")
        lines.append("")
        for label in missing_required:
            lines.append(f"- {label}")
        lines.append("")
    else:
        lines.append("必填信息已具备，可以开始订单级比价。")
        lines.append("")

    if missing_recommended:
        lines.append("建议补充但不阻塞：")
        lines.append("")
        for label in missing_recommended:
            lines.append(f"- {label}")
        lines.append("")

    if validation_errors:
        lines.extend([
            "## 数据格式问题",
            "",
            "以下问题会影响候选表复核。使用 `--strict` 时会阻塞报告生成：",
            "",
        ])
        for error in validation_errors:
            lines.append(f"- {error}")
        lines.append("")

    lines.extend(candidate_lines)

    lines.extend([
        "## 红旗清单",
        "",
    ])
    if all_flags:
        for flag in all_flags[:40]:
            lines.append(f"- {flag}")
        if len(all_flags) > 40:
            lines.append(f"- 另有 {len(all_flags) - 40} 个红旗，详见候选 CSV。")
    else:
        lines.append("- 暂无结构化红旗。")
    lines.append("")

    lines.extend([
        "## 反复复核日志",
        "",
        f"- 日志文件：[{rel(log_path)}]({rel(log_path)})",
        f"- 模式：{'真实日志' if log_mode == 'actual' else '模板'}",
        f"- 记录数：{len(log_rows)}",
    ])
    if log_counts:
        summary = "，".join(f"{status}: {count}" for status, count in sorted(log_counts.items()))
        lines.append(f"- 状态分布：{summary}")
    if next_dates:
        lines.append(f"- 下一次复核日期：{', '.join(next_dates[:6])}")
    if not log_rows:
        lines.append("- 尚无真实复核记录。每次查价、电话确认、景区回复和天气改线都应新增一行。")
    lines.append("")

    lines.extend([
        "## 下一轮动作",
        "",
    ])
    if missing_required:
        lines.append("- 先用 `gannan-input-wizard.html` 生成 `data/gannan_order_inputs.json`，补齐出发城市、日期、人数、房间、交通偏好、酒店预算和摄影器材。")
    lines.extend([
        "- 每类至少录入 2-3 个候选，状态先用 `candidate`，淘汰原因写进 `notes`。",
        "- 候选表填好后用 `scripts/gannan_candidate_scorecard.py` 按证据、退改、价格和关键确认项排序。",
        "- 候选表填好后用 `scripts/check_gannan_order_coverage.py --strict` 检查去返程、D1-D8 酒店、车辆和核心门票是否完整。",
        "- 进入 `shortlist` 前必须有最终含税价、退改/取消规则、证据截图和下一步动作。",
        "- 酒店重点二次确认停车、热水/供暖、早出门；扎尕那和阿坝县不要只看平台图。",
        "- 门票重点二次确认扎尕那、莲宝叶则开放范围、观光车/扶梯/最晚离园和实名预约。",
        "- 每轮复核后追加 `data/gannan_reverification_log.csv`，并保留截图文件名。",
        "- 出发日期确定后先用 `scripts/gannan_reverification_schedule.py` 生成 T-14/T-7/T-3/T-1 待复核日志草稿。",
        "- 每轮查完后用 `scripts/gannan_reverification_diff.py --strict` 抓涨价、状态变坏和 blocked/fail。",
        "- 证据截图按 `甘南莲宝叶则_证据归档规范.md` 存入 `evidence/gannan/`，真实订单阶段用严格模式检查。",
        "- 所有订单下单前运行 `scripts/gannan_booking_gate.py --strict`，确认没有阻塞闸门。",
        "",
        "## 运行命令",
        "",
        "```bash",
        "python3 scripts/gannan_order_report.py",
        "python3 scripts/gannan_candidate_scorecard.py",
        "python3 scripts/gannan_booking_gate.py",
        "python3 scripts/gannan_reverification_schedule.py --route-start-date YYYY-MM-DD",
        "python3 scripts/gannan_reverification_diff.py --strict",
        "python3 scripts/check_gannan_order_coverage.py --strict",
        "python3 scripts/check_gannan_evidence.py --strict",
        "python3 scripts/check_gannan_order_candidates.py \\",
        "  data/gannan_flight_candidates.csv \\",
        "  data/gannan_hotel_candidates.csv \\",
        "  data/gannan_transport_quotes.csv \\",
        "  data/gannan_ticket_candidates.csv",
        "python3 scripts/run_gannan_checks.py --actual",
        "```",
        "",
    ])

    return "\n".join(lines), validation_errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Markdown report output path")
    parser.add_argument("--strict", action="store_true", help="fail when candidate CSV validation errors are present")
    args = parser.parse_args()

    output = args.output if args.output.is_absolute() else ROOT / args.output
    report, validation_errors = render_report(strict=args.strict)

    if args.strict and validation_errors:
        print("Gannan order report failed:")
        for error in validation_errors:
            print(f"- {error}")
        return 1

    output.write_text(report, encoding="utf-8")
    print(f"Generated {rel(output)}")
    if validation_errors:
        print(f"Included {len(validation_errors)} candidate validation warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
