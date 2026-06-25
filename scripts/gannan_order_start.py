#!/usr/bin/env python3
"""Prepare a safe order-level verification workspace for the Gannan guide."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from check_gannan_inputs import RECOMMENDED_FIELDS, REQUIRED_FIELDS, get_value, is_filled
from gannan_reverification_schedule import build_schedule, parse_date, write_csv


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "甘南莲宝叶则_订单启动工作流.md"
DEFAULT_INPUT = ROOT / "data/gannan_order_inputs.json"

FILE_PAIRS = [
    ("出行信息", ROOT / "data/gannan_order_inputs.template.json", ROOT / "data/gannan_order_inputs.json"),
    ("大交通候选", ROOT / "data/gannan_flight_candidates.template.csv", ROOT / "data/gannan_flight_candidates.csv"),
    ("酒店候选", ROOT / "data/gannan_hotel_candidates.template.csv", ROOT / "data/gannan_hotel_candidates.csv"),
    ("车辆报价", ROOT / "data/gannan_transport_quotes.template.csv", ROOT / "data/gannan_transport_quotes.csv"),
    ("门票候选", ROOT / "data/gannan_ticket_candidates.template.csv", ROOT / "data/gannan_ticket_candidates.csv"),
]

LOG_TEMPLATE = ROOT / "data/gannan_reverification_log.template.csv"
LOG_OUTPUT = ROOT / "data/gannan_reverification_log.csv"

EVIDENCE_DIRS = [
    "flight",
    "hotel",
    "transport",
    "ticket",
    "route",
    "weather",
    "photo",
    "health",
    "drone",
    "insurance",
    "source",
    "daily",
]


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def md_cell(value: object) -> str:
    text = str(value).strip() if value is not None else "-"
    if not text:
        return "-"
    return text.replace("|", "\\|").replace("\n", " ")


def resolve_date(value: datetime | None, input_path: Path) -> datetime | None:
    if value is not None:
        return value
    data = read_json(input_path)
    raw = (((data.get("trip") or {}).get("departure_date")) or "").strip()
    if not raw:
        return None
    return parse_date(raw)


def input_missing_fields(input_path: Path) -> tuple[list[str], list[str]]:
    data = read_json(input_path)
    if not data:
        return [label for _, label in REQUIRED_FIELDS], [label for _, label in RECOMMENDED_FIELDS]

    missing_required = [
        label for field, label in REQUIRED_FIELDS if not is_filled(get_value(data, field))
    ]
    missing_recommended = [
        label for field, label in RECOMMENDED_FIELDS if not is_filled(get_value(data, field))
    ]
    return missing_required, missing_recommended


def file_state(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file() and path.stat().st_size == 0:
        return "empty"
    if path.suffix == ".csv":
        return f"present, {len(read_csv_rows(path))} row(s)"
    return "present"


def evidence_state() -> tuple[int, list[str]]:
    root = ROOT / "evidence/gannan"
    if not root.exists():
        return 0, []
    files = [path for path in root.glob("**/*") if path.is_file() and path.name != "README.md"]
    dirs = [name for name in EVIDENCE_DIRS if (root / name).is_dir()]
    return len(files), dirs


def schedule_preview(start_date: datetime | None) -> list[str]:
    if start_date is None:
        return [
            "| 轮次 | 复核日期 | 动作 |",
            "|---|---|---|",
            "| T-14 | 待出发日期 | 建立候选池、首次截图 |",
            "| T-7 | 待出发日期 | 短名单、电话确认、门票开放 |",
            "| T-3 | 待出发日期 | 天气/道路/开放范围改线判断 |",
            "| T-1 | 待出发日期 | 最终下单前截图和现场话术 |",
            "| D-day | 每天早上 | 路况、门票、机位和身体状态 |",
        ]

    rounds = [
        ("T-14", start_date - timedelta(days=14), "建立候选池、首次截图"),
        ("T-7", start_date - timedelta(days=7), "短名单、电话确认、门票开放"),
        ("T-3", start_date - timedelta(days=3), "天气/道路/开放范围改线判断"),
        ("T-1", start_date - timedelta(days=1), "最终下单前截图和现场话术"),
        ("D-day", start_date, "每天早上现场复核"),
    ]
    lines = ["| 轮次 | 复核日期 | 动作 |", "|---|---|---|"]
    for round_name, check_date, action in rounds:
        lines.append(f"| {round_name} | {check_date.strftime('%Y-%m-%d')} | {action} |")
    return lines


def render_status_table() -> list[str]:
    lines = [
        "| 工作文件 | 当前状态 | 作用 |",
        "|---|---|---|",
    ]
    for label, _, output in FILE_PAIRS:
        lines.append(f"| {label} | {file_state(output)} | {md_cell(rel(output))} |")
    lines.append(f"| 复核日志 | {file_state(LOG_OUTPUT)} | {md_cell(rel(LOG_OUTPUT))} |")
    evidence_count, evidence_dirs = evidence_state()
    dir_text = ", ".join(evidence_dirs) if evidence_dirs else "未建分类目录"
    lines.append(f"| 证据归档 | {evidence_count} file(s) | evidence/gannan/；{md_cell(dir_text)} |")
    return lines


def render_markdown(start_date: datetime | None, input_path: Path) -> str:
    missing_required, missing_recommended = input_missing_fields(input_path)
    ready_text = "可以开始真实比价" if not missing_required else "还缺必填信息，先不要宣称订单级完成"
    evidence_count, _ = evidence_state()
    lines = [
        "# 甘南 + 莲宝叶则订单启动工作流",
        "",
        f"更新日期：{datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        "对应目标审计：[甘南莲宝叶则_目标完成审计.md](甘南莲宝叶则_目标完成审计.md)  ",
        "订单复核报告：[甘南莲宝叶则_订单复核报告.md](甘南莲宝叶则_订单复核报告.md)",
        "",
        "这份工作流把“攻略包完成”推进到“真实订单可复核”：先收集出行信息，再初始化工作文件，再填候选、保存证据、生成复核日志，最后用 `--actual` 做阻塞检查。",
        "",
        "## 当前启动状态",
        "",
        f"结论：{ready_text}。",
        "",
        *render_status_table(),
        "",
        "## 必填信息缺口",
        "",
    ]

    if missing_required:
        lines.extend(f"- {label}" for label in missing_required)
    else:
        lines.append("- 必填信息已补齐。")

    lines.extend(["", "## 建议补充", ""])
    if missing_recommended:
        lines.extend(f"- {label}" for label in missing_recommended)
    else:
        lines.append("- 推荐信息已补齐。")

    lines.extend([
        "",
        "## 复核日程预览",
        "",
        *schedule_preview(start_date),
        "",
        "## 一键启动命令",
        "",
        "默认只生成这份报告，不创建真实订单文件：",
        "",
        "```bash",
        "python3 scripts/gannan_order_start.py",
        "```",
        "",
        "确认要进入真实订单阶段时，再初始化工作区：",
        "",
        "```bash",
        "python3 scripts/gannan_order_start.py --init-files --route-start-date YYYY-MM-DD",
        "```",
        "",
        "这会安全创建：",
        "",
        "- `data/gannan_order_inputs.json`",
        "- `data/gannan_flight_candidates.csv`",
        "- `data/gannan_hotel_candidates.csv`",
        "- `data/gannan_transport_quotes.csv`",
        "- `data/gannan_ticket_candidates.csv`",
        "- `data/gannan_reverification_log.csv`",
        "- `evidence/gannan/` 下的分类证据目录",
        "",
        "## 初始化后怎么验",
        "",
        "```bash",
        "python3 scripts/check_gannan_inputs.py data/gannan_order_inputs.json",
        "python3 scripts/check_gannan_order_candidates.py data/gannan_flight_candidates.csv data/gannan_hotel_candidates.csv data/gannan_transport_quotes.csv data/gannan_ticket_candidates.csv",
        "python3 scripts/check_gannan_reverification_log.py data/gannan_reverification_log.csv",
        "python3 scripts/run_gannan_checks.py --actual",
        "```",
        "",
        "## 安全边界",
        "",
        f"- 当前证据归档已有 {evidence_count} 个真实证据文件；没有截图/聊天记录/订单页证据时，不能把价格当作已验证。",
        "- `--init-files` 只创建工作文件，不代表机票、酒店、车辆或门票已经核验。",
        "- 已存在的真实工作文件默认不会覆盖；确实要重建时才加 `--force`。",
        "- 没有出发日期时，复核日志只能保留模板，不能生成 T-14/T-7/T-3/T-1 的具体日期。",
        "",
    ])
    return "\n".join(lines)


def copy_if_needed(source: Path, target: Path, *, force: bool, actions: list[str]) -> None:
    if target.exists() and not force:
        actions.append(f"kept existing {rel(target)}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    actions.append(f"created {rel(target)}")


def init_files(start_date: datetime | None, *, force: bool, owner: str) -> list[str]:
    actions: list[str] = []
    for _, source, target in FILE_PAIRS:
        copy_if_needed(source, target, force=force, actions=actions)

    LOG_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if LOG_OUTPUT.exists() and not force:
        actions.append(f"kept existing {rel(LOG_OUTPUT)}")
    elif start_date is not None:
        rows = build_schedule(start_date, owner)
        with LOG_OUTPUT.open("w", newline="", encoding="utf-8") as handle:
            write_csv(rows, handle)
        actions.append(f"created {rel(LOG_OUTPUT)} with {len(rows)} scheduled rows")
    else:
        shutil.copyfile(LOG_TEMPLATE, LOG_OUTPUT)
        actions.append(f"created empty {rel(LOG_OUTPUT)} from template")

    evidence_root = ROOT / "evidence/gannan"
    for dirname in EVIDENCE_DIRS:
        path = evidence_root / dirname
        path.mkdir(parents=True, exist_ok=True)
    actions.append(f"ensured {len(EVIDENCE_DIRS)} evidence subdirectories")
    return actions


def self_check(text: str) -> list[str]:
    errors: list[str] = []
    for phrase in [
        "当前启动状态",
        "必填信息缺口",
        "复核日程预览",
        "python3 scripts/gannan_order_start.py --init-files",
        "python3 scripts/run_gannan_checks.py --actual",
    ]:
        if phrase not in text:
            errors.append(f"missing phrase: {phrase}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--from-input", type=Path, default=DEFAULT_INPUT, help="read trip.departure_date and missing fields from this JSON")
    parser.add_argument("--route-start-date", type=parse_date, help="D1 date for the Lanzhou-to-Gannan route, in YYYY-MM-DD")
    parser.add_argument("--owner", default="待分配", help="owner value written to generated re-verification rows")
    parser.add_argument("--init-files", action="store_true", help="create actual order workspace files from templates")
    parser.add_argument("--force", action="store_true", help="overwrite existing actual files when used with --init-files")
    parser.add_argument("--check", action="store_true", help="run deterministic report self-check without writing files")
    args = parser.parse_args()

    input_path = args.from_input if args.from_input.is_absolute() else ROOT / args.from_input
    try:
        start_date = resolve_date(args.route_start_date, input_path)
    except argparse.ArgumentTypeError as error:
        print(error, file=sys.stderr)
        return 2

    if args.check:
        text = render_markdown(parse_date("2026-09-12"), ROOT / "data/gannan_order_inputs.template.json")
        errors = self_check(text)
        if errors:
            print("Gannan order start self-check failed:")
            for error in errors:
                print(f"- {error}")
            return 1
        print("Gannan order start self-check passed.")
        return 0

    actions: list[str] = []
    if args.init_files:
        actions = init_files(start_date, force=args.force, owner=args.owner)

    text = render_markdown(start_date, input_path)
    if actions:
        action_lines = ["", "## 本次初始化动作", ""]
        action_lines.extend(f"- {action}" for action in actions)
        text = text.rstrip() + "\n".join(action_lines) + "\n"

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.write_text(text, encoding="utf-8")
    print(f"Generated {rel(output)}")
    if actions:
        for action in actions:
            print(f"- {action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
