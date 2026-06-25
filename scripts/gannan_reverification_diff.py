#!/usr/bin/env python3
"""Detect changes and regressions across Gannan re-verification rounds."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from check_gannan_reverification_log import REQUIRED_COLUMNS


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "data/gannan_reverification_log.csv"

ROUND_ORDER = {"T-14": 0, "T-7": 1, "T-3": 2, "T-1": 3, "D-day": 4}
STATUS_RISK = {"n/a": 0, "pass": 1, "watch": 2, "blocked": 3, "fail": 4}
ACTION_REQUIRED_STATUSES = {"watch", "blocked", "fail"}


def clean(value: str | None) -> str:
    return (value or "").strip()


def parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return datetime.min


def parse_price(value: str) -> float | None:
    value = clean(value)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], [f"missing log file: {path}"]
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != REQUIRED_COLUMNS:
            expected = ",".join(REQUIRED_COLUMNS)
            found = ",".join(reader.fieldnames or [])
            return [], [f"CSV header mismatch; expected {expected}; found {found}"]
        return list(reader), []


def row_key(row: dict[str, str]) -> tuple[str, str]:
    return clean(row.get("category")), clean(row.get("item"))


def row_sort_key(row: dict[str, str]) -> tuple[datetime, int]:
    return (
        parse_date(clean(row.get("check_date"))),
        ROUND_ORDER.get(clean(row.get("round")), 99),
    )


def finding(kind: str, message: str, row: dict[str, str]) -> dict[str, str]:
    return {
        "kind": kind,
        "round": clean(row.get("round")),
        "check_date": clean(row.get("check_date")),
        "category": clean(row.get("category")),
        "item": clean(row.get("item")),
        "message": message,
    }


def analyze(rows: list[dict[str, str]], price_threshold: float) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row_key(row)].append(row)

    for grouped_rows in groups.values():
        ordered = sorted(grouped_rows, key=row_sort_key)
        latest = ordered[-1]
        latest_status = clean(latest.get("status"))

        if latest_status in {"blocked", "fail"}:
            findings.append(finding("error", f"最新状态为 {latest_status}，需要改线、淘汰或明确负责人。", latest))
        if latest_status in ACTION_REQUIRED_STATUSES and not clean(latest.get("next_action")):
            findings.append(finding("error", f"状态为 {latest_status} 但缺少 next_action。", latest))
        if latest_status in ACTION_REQUIRED_STATUSES and not clean(latest.get("next_check_date")):
            findings.append(finding("warning", f"状态为 {latest_status} 但缺少 next_check_date。", latest))

        for previous, current in zip(ordered, ordered[1:]):
            previous_status = clean(previous.get("status"))
            current_status = clean(current.get("status"))
            if STATUS_RISK.get(current_status, 0) > STATUS_RISK.get(previous_status, 0):
                findings.append(finding(
                    "error" if current_status in {"blocked", "fail"} else "warning",
                    f"状态从 {previous_status or '-'} 变为 {current_status or '-'}。",
                    current,
                ))

            previous_price = parse_price(previous.get("quoted_price_cny", ""))
            current_price = parse_price(current.get("quoted_price_cny", ""))
            if previous_price is not None and current_price is not None and previous_price > 0:
                change = (current_price - previous_price) / previous_price
                if change >= price_threshold:
                    findings.append(finding(
                        "error",
                        f"报价从 {previous_price:.0f} 涨到 {current_price:.0f}，涨幅 {change:.0%}。",
                        current,
                    ))
                elif change <= -price_threshold:
                    findings.append(finding(
                        "info",
                        f"报价从 {previous_price:.0f} 降到 {current_price:.0f}，降幅 {abs(change):.0%}。",
                        current,
                    ))

    return findings


def render_markdown(findings: list[dict[str, str]], rows: list[dict[str, str]]) -> str:
    lines = [
        "# 甘南 + 莲宝叶则复核差异追踪",
        "",
        f"复核记录数：{len(rows)}",
        f"差异/风险数：{len(findings)}",
        "",
    ]
    if not findings:
        lines.append("暂无跨轮差异或风险。")
        return "\n".join(lines)

    lines.extend([
        "| 等级 | 日期 | 轮次 | 分类 | 项目 | 变化/风险 |",
        "|---|---|---|---|---|---|",
    ])
    for item in findings:
        lines.append(
            f"| {item['kind']} | {item['check_date']} | {item['round']} | {item['category']} | {item['item']} | {item['message']} |"
        )
    return "\n".join(lines)


def sample_rows() -> list[dict[str, str]]:
    base = {field: "" for field in REQUIRED_COLUMNS}
    rows: list[dict[str, str]] = []
    for round_name, date, price, status in [
        ("T-14", "2026-08-29", "1200", "pass"),
        ("T-7", "2026-09-05", "1500", "watch"),
        ("T-3", "2026-09-09", "1500", "blocked"),
    ]:
        row = base.copy()
        row.update({
            "round": round_name,
            "check_date": date,
            "category": "hotel",
            "item": "扎尕那民宿 A",
            "source": "酒店微信",
            "quoted_price_cny": price,
            "status": status,
            "decision": "继续观察",
            "next_action": "" if status == "blocked" else "电话复核",
            "owner": "测试",
            "next_check_date": "2026-09-11",
        })
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--price-threshold", type=float, default=0.15, help="relative price change threshold, default 0.15")
    parser.add_argument("--strict", action="store_true", help="fail when errors are found or no real completed verification exists")
    parser.add_argument("--format", choices=["text", "markdown"], default="text")
    parser.add_argument("--check", action="store_true", help="run deterministic self-check")
    args = parser.parse_args()

    if args.check:
        findings = analyze(sample_rows(), args.price_threshold)
        has_price = any("涨幅" in item["message"] for item in findings)
        has_blocked = any("blocked" in item["message"] for item in findings)
        if not has_price or not has_blocked:
            print("Gannan re-verification diff self-check failed.")
            return 1
        print("Gannan re-verification diff self-check passed.")
        print(f"Detected {len(findings)} sample finding(s).")
        return 0

    path = args.path if args.path.is_absolute() else ROOT / args.path
    rows, read_errors = read_rows(path)
    if read_errors:
        if args.strict:
            print("Gannan re-verification diff failed:")
            for error in read_errors:
                print(f"- {error}")
            return 1
        print("Gannan re-verification diff skipped.")
        for error in read_errors:
            print(f"- {error}")
        return 0

    completed_rows = [row for row in rows if clean(row.get("status")) != "n/a"]
    if args.strict and not completed_rows:
        print("Gannan re-verification diff failed:")
        print("- no completed verification rows found; generated schedule rows still need real status, evidence, decision, and next action")
        return 1
    if not rows:
        print("Gannan re-verification diff skipped.")
        print("- no log rows found")
        return 0

    findings = analyze(rows, args.price_threshold)
    errors = [item for item in findings if item["kind"] == "error"]
    if args.format == "markdown":
        print(render_markdown(findings, rows))
    else:
        if findings:
            print("Gannan re-verification diff findings:")
            for item in findings:
                print(f"- [{item['kind']}] {item['check_date']} {item['round']} {item['category']} {item['item']}: {item['message']}")
        else:
            print("Gannan re-verification diff passed.")
            print(f"Checked {len(rows)} log rows with no cross-round findings.")

    if args.strict and errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
