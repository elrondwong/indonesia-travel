#!/usr/bin/env python3
"""Generate fallback actions for unreachable or manual-review Gannan sources."""

from __future__ import annotations

import argparse
import concurrent.futures
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import check_gannan_sources as source_check


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "甘南莲宝叶则_来源故障处理.md"

STATUS_LABELS = {
    "pass": "可达",
    "manual": "需人工打开",
    "warn": "异常提醒",
    "fail": "失败",
    "not_probed": "未探测",
}

ACTION_BY_CATEGORY = {
    "flight": "改用航司 App、航旅纵横、12306 或 OTA 实际日期下单页；截图必须含日期、行李和退改。",
    "hotel": "改用携程/飞猪/美团/酒店电话；电话确认停车、热水/供暖、早餐、早出门和取消规则。",
    "ticket": "改看官方公告、OTA 详情页、景区电话、酒店前台和司机当地消息；开放范围冲突时不提前买死。",
    "route": "改用高德/百度中文地名搜索，并让司机确认实际路况、施工、停车和最晚撤离时间。",
    "photo": "改用天气 App、摄影 App 或手机日出日落工具；山体遮挡必须现场加余量。",
    "weather": "改用中国天气、中央气象台、天气 App 和司机本地消息；雷雨/大风/降雪优先触发砍点。",
    "health": "改看 CDC/旅行医学资料并咨询医生；个人用药和慢病不由攻略替代。",
    "drone": "改看 UOM、景区公告和现场禁飞牌；现场工作人员口径优先。",
    "insurance": "改看保险条款和人工客服，确认高原、医疗、救援和取消覆盖。",
    "budget": "改用旅行社/包车报价/Klook 等价格锚点；只作为预算参考，不替代成交价。",
}

BLOCKING_CATEGORIES = {"flight", "hotel", "ticket", "route", "weather", "drone"}
STATUS_SORT = {"fail": 0, "manual": 1, "warn": 2, "not_probed": 3, "pass": 4}
PRIORITY_SORT = {"A": 0, "B": 1, "C": 2}


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


def probe_rows(rows: list[dict[str, str]], timeout: float, workers: int) -> dict[str, tuple[str, str]]:
    results: dict[str, tuple[str, str]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_to_row = {
            executor.submit(source_check.probe_url, row["url"].strip(), timeout): row
            for row in rows
        }
        for future in concurrent.futures.as_completed(future_to_row):
            row = future_to_row[future]
            results[row["id"].strip()] = future.result()
    return results


def source_status(row: dict[str, str], probe_map: dict[str, tuple[str, str]] | None) -> tuple[str, str]:
    if probe_map is None:
        return "not_probed", "默认离线"
    return probe_map.get(row["id"].strip(), ("fail", "missing probe result"))


def severity(row: dict[str, str], status: str) -> str:
    priority = row["priority"].strip()
    category = row["category"].strip()
    if status == "pass":
        return "正常"
    if priority == "A" and category in BLOCKING_CATEGORIES:
        return "阻塞下单，需人工复核"
    if priority == "A":
        return "关键人工复核"
    if category in {"route", "photo", "budget"}:
        return "备选入口复核"
    return "人工确认"


def next_action(row: dict[str, str], status: str) -> str:
    category = row["category"].strip()
    base = ACTION_BY_CATEGORY.get(category, "按台账 fallback 字段改用备选入口，并把结果写入复核日志。")
    if status == "pass":
        return "入口可达；仍需打开实际日期/页面内容截图，不能只以 HTTP 可达当作已核验。"
    return base


def tracked_rows(rows: list[dict[str, str]], probe_map: dict[str, tuple[str, str]] | None) -> list[tuple[dict[str, str], str, str]]:
    tracked: list[tuple[dict[str, str], str, str]] = []
    for row in rows:
        status, detail = source_status(row, probe_map)
        priority = row["priority"].strip()
        category = row["category"].strip()
        if status != "pass" or priority == "A" or category in {"route", "photo", "weather", "budget"}:
            tracked.append((row, status, detail))
    return sorted(
        tracked,
        key=lambda item: (
            STATUS_SORT.get(item[1], 9),
            PRIORITY_SORT.get(item[0]["priority"].strip(), 9),
            item[0]["category"].strip(),
            item[0]["id"].strip(),
        ),
    )


def render_probe_summary(probe_map: dict[str, tuple[str, str]] | None) -> list[str]:
    if probe_map is None:
        return [
            "## 探测状态",
            "",
            "本次未执行在线探测。默认报告按台账中的 A 级和高时效来源生成故障处理手册；如需把当前外链状态写进报告，运行：",
            "",
            "```bash",
            "python3 scripts/gannan_source_fallbacks.py --online",
            "```",
        ]

    counts = Counter(status for status, _ in probe_map.values())
    return [
        "## 探测状态",
        "",
        f"在线探测已执行：可达 {counts.get('pass', 0)}，需人工打开 {counts.get('manual', 0)}，异常提醒 {counts.get('warn', 0)}，失败 {counts.get('fail', 0)}。",
        "",
        "非通过状态不等于来源内容错误；它只说明自动探测无法替代人工打开、截图和交叉验证。",
    ]


def render_matrix(rows: list[dict[str, str]], probe_map: dict[str, tuple[str, str]] | None) -> list[str]:
    lines = [
        "| 状态 | 严重性 | ID | 优先级 | 项目 | 自动详情 | 备选入口 | 人工动作 | 轮次 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row, status, detail in tracked_rows(rows, probe_map):
        lines.append(
            "| "
            + " | ".join([
                md_cell(STATUS_LABELS.get(status, status)),
                md_cell(severity(row, status)),
                md_cell(row["id"]),
                md_cell(row["priority"]),
                md_cell(row["item"]),
                md_cell(detail),
                md_cell(row["fallback"]),
                md_cell(next_action(row, status)),
                md_cell(", ".join(split_rounds(row["rounds"]))),
            ])
            + " |"
        )
    return lines


def render_blockers(rows: list[dict[str, str]], probe_map: dict[str, tuple[str, str]] | None) -> list[str]:
    blockers: list[tuple[dict[str, str], str, str]] = []
    for row in rows:
        status, detail = source_status(row, probe_map)
        if status != "pass" and row["priority"].strip() == "A" and row["category"].strip() in BLOCKING_CATEGORIES:
            blockers.append((row, status, detail))

    lines = ["## 下单阻塞口径", ""]
    if not blockers:
        lines.append("当前没有自动识别出的 A 级阻塞项；但所有 A 级来源仍要人工截图复核。")
        return lines

    lines.extend([
        "下面这些 A 级来源如果没有人工复核证据，不能进入对应订单下单：",
        "",
        "| ID | 项目 | 状态 | 必须补的证据 |",
        "|---|---|---|---|",
    ])
    for row, status, _ in blockers:
        lines.append(
            f"| {md_cell(row['id'])} | {md_cell(row['item'])} | {md_cell(STATUS_LABELS.get(status, status))} | {md_cell(row['fallback'])} + 复核日志 + 截图/聊天记录 |"
        )
    return lines


def render_playbook() -> list[str]:
    return [
        "## 现场处理顺序",
        "",
        "1. 先判断是不是 A 级来源；A 级票务、天气、路线、无人机失败时，先暂停对应下单或当日进入。",
        "2. 按 `fallback` 字段打开备选入口，不只换一个页面，要做至少两个来源交叉验证。",
        "3. 保存证据：订单页/公告页截图、酒店或司机聊天记录、现场牌示照片。",
        "4. 在 `data/gannan_reverification_log.csv` 里写清状态、决策、下一步和下一次复核日期。",
        "5. 若官方、OTA、酒店/司机三方冲突，以更保守的口径执行：少买死、少赶路、保留改线。",
    ]


def render_markdown(
    rows: list[dict[str, str]],
    *,
    generated_on: str,
    probe_map: dict[str, tuple[str, str]] | None,
) -> str:
    lines = [
        "# 甘南 + 莲宝叶则来源故障处理",
        "",
        f"更新日期：{generated_on}  ",
        "来源台账：[甘南莲宝叶则_来源台账.md](甘南莲宝叶则_来源台账.md)  ",
        "来源健康报告：[甘南莲宝叶则_来源健康报告.md](甘南莲宝叶则_来源健康报告.md)",
        "",
        "这份报告回答一个很现实的问题：外链打不开、被 403、超时或只能人工打开时，下一步该找谁、怎么交叉验证、哪些项目必须暂停下单。",
        "",
        *render_probe_summary(probe_map),
        "",
        *render_blockers(rows, probe_map),
        "",
        "## 故障处理矩阵",
        "",
        *render_matrix(rows, probe_map),
        "",
        *render_playbook(),
        "",
        "## 使用命令",
        "",
        "```bash",
        "python3 scripts/gannan_source_fallbacks.py",
        "python3 scripts/gannan_source_fallbacks.py --online",
        "python3 scripts/gannan_source_fallbacks.py --check",
        "```",
        "",
    ]
    return "\n".join(lines)


def self_check(text: str) -> list[str]:
    errors: list[str] = []
    for phrase in [
        "下单阻塞口径",
        "故障处理矩阵",
        "现场处理顺序",
        "python3 scripts/gannan_source_fallbacks.py --online",
    ]:
        if phrase not in text:
            errors.append(f"missing phrase: {phrase}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", nargs="?", type=Path, default=source_check.DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--online", action="store_true", help="probe source URLs and include current non-pass states")
    parser.add_argument("--strict-online", action="store_true", help="fail when an A-priority blocking source is not pass")
    parser.add_argument("--timeout", type=float, default=8.0, help="per-link timeout in seconds")
    parser.add_argument("--workers", type=int, default=8, help="number of concurrent online probes")
    parser.add_argument("--check", action="store_true", help="run deterministic self-check without writing")
    args = parser.parse_args()

    rows, read_errors = source_check.read_rows(args.ledger)
    errors = read_errors + source_check.validate_rows(rows)
    if errors:
        print("Gannan source fallback report failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    probe_map = probe_rows(rows, args.timeout, args.workers) if args.online else None
    text = render_markdown(rows, generated_on=date.today().isoformat(), probe_map=probe_map)
    check_errors = self_check(text)
    if check_errors:
        print("Gannan source fallback self-check failed:")
        for error in check_errors:
            print(f"- {error}")
        return 1

    blockers = []
    if probe_map is not None:
        for row in rows:
            status, _ = source_status(row, probe_map)
            if status != "pass" and row["priority"].strip() == "A" and row["category"].strip() in BLOCKING_CATEGORIES:
                blockers.append(row["id"].strip())

    if args.check:
        print("Gannan source fallback self-check passed.")
        print(f"Prepared fallback handling for {len(rows)} source(s).")
        return 1 if args.strict_online and blockers else 0

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.write_text(text, encoding="utf-8")
    print(f"Generated {rel(output)}")

    if args.strict_online and blockers:
        print("Strict source fallback check failed:")
        for source_id in blockers:
            print(f"- blocking source requires manual fallback: {source_id}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
