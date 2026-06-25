#!/usr/bin/env python3
"""Generate a readable source-health report for the Gannan guide."""

from __future__ import annotations

import argparse
import concurrent.futures
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import check_gannan_sources as source_check


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "甘南莲宝叶则_来源健康报告.md"

CATEGORY_ORDER = [
    "flight",
    "hotel",
    "car",
    "ticket",
    "route",
    "photo",
    "weather",
    "health",
    "drone",
    "insurance",
    "budget",
]

CATEGORY_LABELS = {
    "flight": "大交通",
    "hotel": "住宿",
    "car": "车辆",
    "ticket": "门票/景区",
    "route": "导航/路线",
    "photo": "光线/机位",
    "weather": "天气预警",
    "health": "高原健康",
    "drone": "无人机",
    "insurance": "保险",
    "budget": "预算锚点",
}

PRIORITY_LABELS = {
    "A": "每轮必查",
    "B": "交叉验证",
    "C": "补充参考",
}

ROUND_ORDER = ["T-14", "T-7", "T-3", "T-1", "D-day"]

ROUND_ACTIONS = {
    "T-14": "锁定候选入口，建立截图和复核日志。",
    "T-7": "确认票务、酒店、车辆、天气趋势和道路风险。",
    "T-3": "重点看开放范围、预警、路线耗时和改线触发器。",
    "T-1": "最终下单/出发前复核，截图归档。",
    "D-day": "当天早上确认景区、道路、天气和司机本地消息。",
}

PROBE_LABELS = {
    "pass": "可达",
    "manual": "需人工打开",
    "warn": "异常提醒",
    "fail": "失败",
}

PROBE_SORT = {"fail": 0, "manual": 1, "warn": 2, "pass": 3}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def md_cell(value: object) -> str:
    text = str(value).strip() if value is not None else "-"
    if not text:
        return "-"
    return text.replace("|", "\\|").replace("\n", " ")


def split_rounds(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()]


def ordered_categories(rows: list[dict[str, str]]) -> list[str]:
    present = {row["category"].strip() for row in rows}
    ordered = [category for category in CATEGORY_ORDER if category in present]
    ordered.extend(sorted(present - set(ordered)))
    return ordered


def count_by_priority(rows: list[dict[str, str]]) -> Counter[str]:
    return Counter(row["priority"].strip() for row in rows)


def count_by_round(rows: list[dict[str, str]]) -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = {round_name: Counter() for round_name in ROUND_ORDER}
    for row in rows:
        priority = row["priority"].strip()
        for round_name in split_rounds(row["rounds"]):
            if round_name not in counts:
                counts[round_name] = Counter()
            counts[round_name]["total"] += 1
            counts[round_name][priority] += 1
    return counts


def source_names(rows: list[dict[str, str]], limit: int = 4) -> str:
    names = [row["item"].strip() for row in rows if row["item"].strip()]
    if len(names) <= limit:
        return "、".join(names)
    return "、".join(names[:limit]) + f" 等 {len(names)} 项"


def probe_rows(rows: list[dict[str, str]], timeout: float, workers: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_to_row = {
            executor.submit(source_check.probe_url, row["url"].strip(), timeout): row
            for row in rows
        }
        for future in concurrent.futures.as_completed(future_to_row):
            row = future_to_row[future]
            status, detail = future.result()
            results.append({
                "id": row["id"].strip(),
                "category": row["category"].strip(),
                "item": row["item"].strip(),
                "priority": row["priority"].strip(),
                "status": status,
                "detail": detail,
                "url": row["url"].strip(),
            })
    return sorted(results, key=lambda item: (PROBE_SORT.get(item["status"], 9), item["priority"], item["id"]))


def render_category_table(rows: list[dict[str, str]]) -> list[str]:
    lines = [
        "| 分类 | 用途 | 来源数 | A | B | C | 覆盖轮次 | 代表项目 |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for category in ordered_categories(rows):
        category_rows = [row for row in rows if row["category"].strip() == category]
        priorities = count_by_priority(category_rows)
        rounds = sorted({round_name for row in category_rows for round_name in split_rounds(row["rounds"])}, key=lambda value: ROUND_ORDER.index(value) if value in ROUND_ORDER else 99)
        lines.append(
            "| "
            + " | ".join([
                md_cell(CATEGORY_LABELS.get(category, category)),
                md_cell(category),
                str(len(category_rows)),
                str(priorities.get("A", 0)),
                str(priorities.get("B", 0)),
                str(priorities.get("C", 0)),
                md_cell(", ".join(rounds)),
                md_cell(source_names(category_rows)),
            ])
            + " |"
        )
    return lines


def render_round_table(rows: list[dict[str, str]]) -> list[str]:
    counts = count_by_round(rows)
    lines = [
        "| 轮次 | 来源数 | A 级来源 | 重点动作 |",
        "|---|---:|---:|---|",
    ]
    for round_name in ROUND_ORDER:
        round_counts = counts.get(round_name, Counter())
        lines.append(
            f"| {round_name} | {round_counts.get('total', 0)} | {round_counts.get('A', 0)} | {md_cell(ROUND_ACTIONS[round_name])} |"
        )
    return lines


def render_priority_table(rows: list[dict[str, str]]) -> list[str]:
    counts = count_by_priority(rows)
    lines = [
        "| 优先级 | 含义 | 来源数 | 占比 |",
        "|---|---|---:|---:|",
    ]
    total = len(rows) or 1
    for priority in ["A", "B", "C"]:
        count = counts.get(priority, 0)
        ratio = f"{count / total:.0%}"
        lines.append(f"| {priority} | {PRIORITY_LABELS[priority]} | {count} | {ratio} |")
    return lines


def render_a_sources(rows: list[dict[str, str]]) -> list[str]:
    lines = [
        "| ID | 项目 | 来源 | 用途 | 轮次 | 备选入口 |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        if row["priority"].strip() != "A":
            continue
        lines.append(
            "| "
            + " | ".join([
                md_cell(row["id"]),
                md_cell(row["item"]),
                md_cell(row["source_name"]),
                md_cell(row["verify_use"]),
                md_cell(", ".join(split_rounds(row["rounds"]))),
                md_cell(row["fallback"]),
            ])
            + " |"
        )
    return lines


def render_online_section(probe_results: list[dict[str, str]] | None) -> list[str]:
    if probe_results is None:
        return [
            "## 联网探测结果",
            "",
            "本次未执行在线探测。默认报告只做离线结构和覆盖健康检查，避免把 OTA、地图或政务站的临时反爬当作攻略错误。",
            "",
            "需要复核外部入口可达性时运行：",
            "",
            "```bash",
            "python3 scripts/gannan_source_health_report.py --online",
            "python3 scripts/check_gannan_sources.py --online",
            "```",
        ]

    counts = Counter(result["status"] for result in probe_results)
    lines = [
        "## 联网探测结果",
        "",
        f"在线探测已执行：可达 {counts.get('pass', 0)}，需人工打开 {counts.get('manual', 0)}，异常提醒 {counts.get('warn', 0)}，失败 {counts.get('fail', 0)}。",
        "",
        "外链可达只说明入口当前能响应，不代表价格、房态、门票或开放范围已经完成订单级核验。",
        "",
    ]

    review_rows = [result for result in probe_results if result["status"] != "pass"]
    if not review_rows:
        lines.append("未发现需要人工处理的外链状态。")
        return lines

    lines.extend([
        "| 状态 | ID | 优先级 | 项目 | 详情 |",
        "|---|---|---|---|---|",
    ])
    for result in review_rows:
        lines.append(
            "| "
            + " | ".join([
                md_cell(PROBE_LABELS.get(result["status"], result["status"])),
                md_cell(result["id"]),
                md_cell(result["priority"]),
                md_cell(result["item"]),
                md_cell(result["detail"]),
            ])
            + " |"
        )
    return lines


def render_next_actions(rows: list[dict[str, str]]) -> list[str]:
    a_rows = [row for row in rows if row["priority"].strip() == "A"]
    ticket_a = [row for row in a_rows if row["category"].strip() == "ticket"]
    dynamic_a = [
        row for row in a_rows
        if row["category"].strip() in {"ticket", "weather", "route", "drone"}
    ]
    return [
        "## 下轮人工动作",
        "",
        f"- T-14：打开 {len(a_rows)} 个 A 级入口，建立第一轮截图和日志，不在没有日期时写死价格。",
        f"- T-7：重点复核 {len(ticket_a)} 个 A 级景区/门票入口，并同步酒店、司机、天气趋势。",
        f"- T-3/T-1：把 {len(dynamic_a)} 个高时效入口作为改线触发器，尤其莲宝叶则、扎尕那、天气和道路。",
        "- D-day：只信当天现场牌示、官方公告、酒店前台和司机本地消息；任何冲突都写进复核日志。",
        "- 每次人工打开来源后，把截图放入 `evidence/gannan/`，把结论写入 `data/gannan_reverification_log.csv`。",
    ]


def render_markdown(
    rows: list[dict[str, str]],
    *,
    generated_on: str,
    probe_results: list[dict[str, str]] | None,
) -> str:
    priorities = count_by_priority(rows)
    a_count = priorities.get("A", 0)
    lines = [
        "# 甘南 + 莲宝叶则来源健康报告",
        "",
        f"更新日期：{generated_on}  ",
        "来源台账：[甘南莲宝叶则_来源台账.md](甘南莲宝叶则_来源台账.md)  ",
        "来源 CSV：[data/gannan_source_ledger.csv](data/gannan_source_ledger.csv)  ",
        "来源故障处理：[甘南莲宝叶则_来源故障处理.md](甘南莲宝叶则_来源故障处理.md)",
        "",
        "这份报告把来源台账从“有哪些入口”进一步压成“入口是否覆盖够、哪些每轮必查、哪些需要人工打开”。它仍然不等于真实订单价格核验；机票、酒店、门票和车辆必须回到实际日期下单页和人工确认记录。",
        "",
        "## 健康摘要",
        "",
        f"- 台账来源总数：{len(rows)}",
        f"- A 级每轮必查来源：{a_count}",
        f"- 分类覆盖：{len(ordered_categories(rows))} 类",
        f"- 在线探测：{'已执行' if probe_results is not None else '未执行，默认离线'}",
        "- 结构检查：通过 `scripts/check_gannan_sources.py` 的 CSV 列、分类、优先级、轮次和 URL 规则。",
        "",
        "## 优先级结构",
        "",
        *render_priority_table(rows),
        "",
        "## 分类覆盖",
        "",
        *render_category_table(rows),
        "",
        "## 复核轮次覆盖",
        "",
        *render_round_table(rows),
        "",
        "## A 级必查来源",
        "",
        *render_a_sources(rows),
        "",
        *render_online_section(probe_results),
        "",
        *render_next_actions(rows),
        "",
        "## 使用命令",
        "",
        "```bash",
        "python3 scripts/gannan_source_health_report.py",
        "python3 scripts/gannan_source_health_report.py --online",
        "python3 scripts/gannan_source_health_report.py --check",
        "python3 scripts/check_gannan_sources.py --online",
        "```",
        "",
    ]
    return "\n".join(lines)


def self_check(text: str, rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for phrase in [
        "健康摘要",
        "分类覆盖",
        "复核轮次覆盖",
        "A 级必查来源",
        "python3 scripts/gannan_source_health_report.py --online",
    ]:
        if phrase not in text:
            errors.append(f"missing phrase: {phrase}")
    if f"台账来源总数：{len(rows)}" not in text:
        errors.append("source count missing from report")
    if not any(row["priority"].strip() == "A" for row in rows):
        errors.append("source ledger has no A-priority source")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", nargs="?", type=Path, default=source_check.DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--online", action="store_true", help="probe source URLs and include non-pass results")
    parser.add_argument("--strict-online", action="store_true", help="fail when an online probe cannot reach a source")
    parser.add_argument("--timeout", type=float, default=8.0, help="per-link timeout in seconds")
    parser.add_argument("--workers", type=int, default=8, help="number of concurrent online probes")
    parser.add_argument("--check", action="store_true", help="run deterministic report self-check without writing")
    args = parser.parse_args()

    rows, read_errors = source_check.read_rows(args.ledger)
    errors = read_errors + source_check.validate_rows(rows)
    if errors:
        print("Gannan source health report failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    probe_results = probe_rows(rows, args.timeout, args.workers) if args.online else None
    text = render_markdown(rows, generated_on=date.today().isoformat(), probe_results=probe_results)

    check_errors = self_check(text, rows)
    if check_errors:
        print("Gannan source health report self-check failed:")
        for error in check_errors:
            print(f"- {error}")
        return 1

    failed_probes = [result for result in probe_results or [] if result["status"] == "fail"]
    if args.check:
        print("Gannan source health report self-check passed.")
        print(f"Checked {len(rows)} sources across {len(ordered_categories(rows))} categories.")
        return 1 if args.strict_online and failed_probes else 0

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.write_text(text, encoding="utf-8")
    print(f"Generated {rel(output)}")

    if args.strict_online and failed_probes:
        print("Strict online source health failed:")
        for result in failed_probes:
            print(f"- {result['id']}: {result['detail']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
