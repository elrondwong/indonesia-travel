#!/usr/bin/env python3
"""Export the Gannan re-verification schedule as an iCalendar file."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gannan_reverification_schedule import (
    ROOT,
    DEFAULT_INPUT,
    build_schedule,
    parse_date,
    read_start_date_from_input,
)


DEFAULT_ICS_OUTPUT = ROOT / "data/gannan_reverification_calendar.ics"
DEFAULT_MD_OUTPUT = ROOT / "甘南莲宝叶则_复核日历导出.md"

CATEGORY_LABELS = {
    "flight": "大交通",
    "hotel": "酒店",
    "car": "车辆",
    "ticket": "门票",
    "route": "路线",
    "photo": "机位",
    "drone": "无人机",
    "health": "健康",
    "insurance": "保险",
    "budget": "预算",
}

ROUND_START_TIMES = {
    "T-14": "20:00",
    "T-7": "20:00",
    "T-3": "20:00",
    "T-1": "20:00",
    "D-day": "07:00",
}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def date_text(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def parse_time(value: str) -> tuple[int, int]:
    hour, minute = value.split(":", 1)
    return int(hour), int(minute)


def event_datetime(check_date: str, round_name: str) -> datetime:
    hour, minute = parse_time(ROUND_START_TIMES.get(round_name, "20:00"))
    return datetime.strptime(check_date, "%Y-%m-%d").replace(hour=hour, minute=minute)


def ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def fold_line(line: str) -> list[str]:
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return [line]

    chunks: list[str] = []
    current = ""
    for char in line:
        candidate = current + char
        if len(candidate.encode("utf-8")) > 75:
            chunks.append(current)
            current = " " + char
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def uid_for(row: dict[str, str], start_date: datetime) -> str:
    raw = "|".join([
        date_text(start_date),
        row["round"],
        row["check_date"],
        row["category"],
        row["item"],
    ])
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{digest}@gannan-reverification.local"


def render_ics(rows: list[dict[str, str]], start_date: datetime, duration_minutes: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Codex//Gannan Reverification//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:甘南莲宝叶则复核日历",
        "X-WR-TIMEZONE:Asia/Shanghai",
    ]

    for row in rows:
        start = event_datetime(row["check_date"], row["round"])
        end = start + timedelta(minutes=duration_minutes)
        category_label = CATEGORY_LABELS.get(row["category"], row["category"])
        summary = f"{row['round']} {category_label}复核：{row['item']}"
        description = "\n".join([
            f"来源：{row['source']}",
            f"动作：{row['next_action']}",
            f"记录到：data/gannan_reverification_log.csv",
            "证据归档：evidence/gannan/",
        ])
        event_lines = [
            "BEGIN:VEVENT",
            f"UID:{uid_for(row, start_date)}",
            f"DTSTAMP:{now}",
            f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{ics_escape(summary)}",
            f"DESCRIPTION:{ics_escape(description)}",
            f"CATEGORIES:{ics_escape(category_label)}",
            "END:VEVENT",
        ]
        lines.extend(event_lines)
    lines.append("END:VCALENDAR")

    folded: list[str] = []
    for line in lines:
        folded.extend(fold_line(line))
    return "\r\n".join(folded) + "\r\n"


def render_markdown(rows: list[dict[str, str]], start_date: datetime, ics_path: Path) -> str:
    counts_by_round = Counter(row["round"] for row in rows)
    counts_by_category = Counter(row["category"] for row in rows)
    lines = [
        "# 甘南 + 莲宝叶则复核日历导出",
        "",
        f"路线开始日期：{date_text(start_date)}  ",
        f"ICS 文件：[data/gannan_reverification_calendar.ics]({rel(ics_path)})  ",
        "复核日程说明：[甘南莲宝叶则_复核日程生成.md](甘南莲宝叶则_复核日程生成.md)",
        "",
        "这份导出把 T-14、T-7、T-3、T-1 和 D-day 复核任务变成可导入日历的 `.ics` 文件。导入后仍要把实际结果写回 `data/gannan_reverification_log.csv`，日历只负责提醒，不代表复核已经完成。",
        "",
        "## 当前导出",
        "",
        f"- 事件总数：{len(rows)}",
        "- 默认时间：T-14/T-7/T-3/T-1 为 20:00，D-day 为 07:00。",
        "- 默认时长：45 分钟。",
        "- 日历时区：Asia/Shanghai。",
        "",
        "| 轮次 | 事件数 |",
        "|---|---:|",
    ]
    for round_name in ["T-14", "T-7", "T-3", "T-1", "D-day"]:
        lines.append(f"| {round_name} | {counts_by_round.get(round_name, 0)} |")

    lines.extend([
        "",
        "## 分类分布",
        "",
        "| 分类 | 事件数 |",
        "|---|---:|",
    ])
    for category, count in sorted(counts_by_category.items()):
        lines.append(f"| {CATEGORY_LABELS.get(category, category)} | {count} |")

    lines.extend([
        "",
        "## 使用命令",
        "",
        "```bash",
        "python3 scripts/gannan_reverification_calendar.py --route-start-date YYYY-MM-DD",
        "python3 scripts/gannan_reverification_calendar.py --route-start-date YYYY-MM-DD --ics-output data/gannan_reverification_calendar.ics",
        "python3 scripts/gannan_reverification_calendar.py --check",
        "```",
        "",
        "## 导入后怎么用",
        "",
        "1. 把 `data/gannan_reverification_calendar.ics` 导入手机或电脑日历。",
        "2. 每个提醒触发后，打开来源台账、来源故障处理和候选表做人工复核。",
        "3. 复核结果写回 `data/gannan_reverification_log.csv`，证据截图放入 `evidence/gannan/`。",
        "4. 下单前运行 `python3 scripts/gannan_booking_gate.py --strict`。",
        "",
    ])
    return "\n".join(lines)


def resolve_start_date(args: argparse.Namespace) -> datetime | None:
    if args.check:
        return parse_date("2026-09-12")
    if args.route_start_date is not None:
        return args.route_start_date
    input_path = args.from_input if args.from_input.is_absolute() else ROOT / args.from_input
    return read_start_date_from_input(input_path)


def self_check(ics_text: str, markdown: str, rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    if "BEGIN:VCALENDAR" not in ics_text or "END:VCALENDAR" not in ics_text:
        errors.append("ICS missing VCALENDAR wrapper")
    if ics_text.count("BEGIN:VEVENT") != len(rows):
        errors.append("ICS event count does not match schedule rows")
    for phrase in [
        "复核日历导出",
        "事件总数",
        "python3 scripts/gannan_reverification_calendar.py --route-start-date",
        "gannan_booking_gate.py --strict",
    ]:
        if phrase not in markdown:
            errors.append(f"markdown missing phrase: {phrase}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route-start-date", type=parse_date, help="D1 date for the Lanzhou-to-Gannan route, in YYYY-MM-DD")
    parser.add_argument("--from-input", type=Path, default=DEFAULT_INPUT, help="read trip.departure_date from this JSON when route-start-date is omitted")
    parser.add_argument("--owner", default="待分配", help="owner value used by the schedule builder")
    parser.add_argument("--ics-output", type=Path, default=DEFAULT_ICS_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD_OUTPUT)
    parser.add_argument("--duration-minutes", type=int, default=45)
    parser.add_argument("--check", action="store_true", help="run deterministic self-check without writing files")
    args = parser.parse_args()

    start_date = resolve_start_date(args)
    if start_date is None:
        print("route start date is required; pass --route-start-date YYYY-MM-DD or fill data/gannan_order_inputs.json", file=sys.stderr)
        return 2

    rows = build_schedule(start_date, args.owner)
    ics_output = args.ics_output if args.ics_output.is_absolute() else ROOT / args.ics_output
    md_output = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output
    ics_text = render_ics(rows, start_date, max(15, args.duration_minutes))
    markdown = render_markdown(rows, start_date, ics_output)

    errors = self_check(ics_text, markdown, rows)
    if errors:
        print("Gannan re-verification calendar self-check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.check:
        print("Gannan re-verification calendar self-check passed.")
        print(f"Generated {len(rows)} calendar event(s) in memory.")
        return 0

    ics_output.parent.mkdir(parents=True, exist_ok=True)
    ics_output.write_text(ics_text, encoding="utf-8", newline="")
    md_output.write_text(markdown, encoding="utf-8")
    print(f"Generated {rel(ics_output)}")
    print(f"Generated {rel(md_output)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
