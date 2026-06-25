#!/usr/bin/env python3
"""Generate a handoff packet for real Gannan order verification."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from check_gannan_inputs import REQUIRED_FIELDS, get_value, is_filled


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "甘南莲宝叶则_订单核验接力包.md"

INPUT_FILE = ROOT / "data/gannan_order_inputs.json"
LOG_FILE = ROOT / "data/gannan_reverification_log.csv"
EVIDENCE_DIR = ROOT / "evidence/gannan"

CANDIDATE_FILES = {
    "大交通": ROOT / "data/gannan_flight_candidates.csv",
    "酒店": ROOT / "data/gannan_hotel_candidates.csv",
    "车辆": ROOT / "data/gannan_transport_quotes.csv",
    "门票/开放": ROOT / "data/gannan_ticket_candidates.csv",
}

TEMPLATE_FILES = {
    "大交通": ROOT / "data/gannan_flight_candidates.template.csv",
    "酒店": ROOT / "data/gannan_hotel_candidates.template.csv",
    "车辆": ROOT / "data/gannan_transport_quotes.template.csv",
    "门票/开放": ROOT / "data/gannan_ticket_candidates.template.csv",
}

MINIMUM_COVERAGE = [
    ("大交通", "去程 + 返程各至少 1 个 shortlist/booked/backup 候选"),
    ("酒店", "D1-D8 每晚至少 1 个候选；扎尕那、阿坝县必须确认热水/供暖/停车/早出门"),
    ("车辆", "至少 1 个可执行方案；建议 3 个包车/租车报价做价格和条款对比"),
    ("门票/开放", "拉卜楞寺、扎尕那、花湖、黄河九曲、莲宝叶则均要有门票/开放记录"),
    ("证据", "每条活跃候选和每轮复核都要填 evidence_file，并把截图/聊天记录放入 evidence/gannan/"),
    ("复核日志", "按 D1 日期生成 T-14/T-7/T-3/T-1/D-day 任务，完成后填 status/decision/next_action"),
]

INTAKE_FIELDS = [
    ("出发城市", "例如 深圳 / 广州 / 上海 / 北京 / 兰州"),
    ("D1 兰州出发日期", "YYYY-MM-DD"),
    ("D9 返程日期和最晚到站/到机场时间", "例如 2026-09-20，18:00 前到兰州中川机场"),
    ("人数、房间数、房型", "例如 2 人，1 间双床"),
    ("交通偏好", "包车 / 自驾 / 租车 / 待比较"),
    ("每间夜酒店预算", "例如 300-500 / 500-800 / 800+"),
    ("是否带无人机", "是 / 否；若是，需单独查禁飞和景区规则"),
    ("摄影器材", "机身、镜头、三脚架、无人机、备份设备"),
    ("高原反应史和健康限制", "是否需要更保守车程和住宿海拔"),
]


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def clean(value: object | None) -> str:
    return str(value or "").strip()


def md_cell(value: object | None) -> str:
    text = clean(value)
    if not text:
        return "-"
    return text.replace("|", "\\|").replace("\n", " ")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def file_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file() and path.stat().st_size == 0:
        return "empty"
    return "present"


def evidence_files() -> list[Path]:
    if not EVIDENCE_DIR.exists():
        return []
    return [
        path for path in EVIDENCE_DIR.glob("**/*")
        if path.is_file() and path.name != "README.md"
    ]


def missing_input_labels(data: dict[str, Any]) -> list[str]:
    return [
        label for field, label in REQUIRED_FIELDS
        if not is_filled(get_value(data, field))
    ]


def candidate_summary() -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    for label, path in CANDIDATE_FILES.items():
        rows = read_csv_rows(path)
        statuses: dict[str, int] = {}
        evidence_count = 0
        missing_next = 0
        for row in rows:
            status = clean(row.get("status")) or "blank"
            statuses[status] = statuses.get(status, 0) + 1
            if clean(row.get("evidence_file")):
                evidence_count += 1
            if status not in {"booked", "rejected", "closed", "skipped"} and not clean(row.get("next_action")):
                missing_next += 1
        summary.append({
            "label": label,
            "path": path,
            "status": file_status(path),
            "template": TEMPLATE_FILES[label],
            "rows": len(rows),
            "statuses": statuses,
            "evidence_count": evidence_count,
            "missing_next": missing_next,
        })
    return summary


def current_stage(data: dict[str, Any], candidates: list[dict[str, object]], log_rows: list[dict[str, str]], evidence_count: int) -> str:
    if missing_input_labels(data):
        return "等待出行信息"
    if any(item["status"] != "present" or item["rows"] == 0 for item in candidates):
        return "等待真实候选"
    if evidence_count == 0:
        return "等待证据归档"
    if not log_rows:
        return "等待复核日志"
    return "可以运行严格闸门"


def first_next_action(stage: str) -> str:
    if stage == "等待出行信息":
        return "先用 `gannan-input-wizard.html` 或下方表格补齐出发城市、日期、人数、预算和偏好。"
    if stage == "等待真实候选":
        return "运行 `python3 scripts/gannan_order_start.py --init-files --route-start-date YYYY-MM-DD`，然后填写四类真实候选 CSV。"
    if stage == "等待证据归档":
        return "把订单页、酒店/司机聊天确认、景区开放和天气截图放入 `evidence/gannan/`，并填回 CSV 的 `evidence_file`。"
    if stage == "等待复核日志":
        return "按真实 D1 日期生成并填写 `data/gannan_reverification_log.csv`，至少完成 T-14/T-7/T-3/T-1。"
    return "运行 `python3 scripts/run_gannan_checks.py --online-sources --actual`。"


def render_markdown() -> str:
    data = read_json(INPUT_FILE)
    candidates = candidate_summary()
    log_rows = read_csv_rows(LOG_FILE)
    ev_count = len(evidence_files())
    stage = current_stage(data, candidates, log_rows, ev_count)
    missing = missing_input_labels(data)

    lines = [
        "# 甘南 + 莲宝叶则订单核验接力包",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "这份接力包只做一件事：把“攻略包完成”接到“真实订单反复验证”上。它不会把模板当成已验证订单，也不会把 HTTP 可达当成价格或开放已确认。",
        "",
        "## 当前接力状态",
        "",
        f"- 当前阶段：{stage}",
        f"- 第一动作：{first_next_action(stage)}",
        f"- 真实证据文件：{ev_count} 个",
        f"- 复核日志行数：{len(log_rows)} 行",
        "",
        "| 工作文件 | 状态 | 行数 | 证据引用 | 缺下一步 |",
        "|---|---|---:|---:|---:|",
    ]
    for item in candidates:
        lines.append(
            "| {label} | {status} | {rows} | {evidence_count} | {missing_next} |".format(
                label=md_cell(item["label"]),
                status=md_cell(item["status"]),
                rows=item["rows"],
                evidence_count=item["evidence_count"],
                missing_next=item["missing_next"],
            )
        )

    lines.extend([
        "",
        "## 还需要用户给我的信息",
        "",
    ])
    if missing:
        lines.append("当前阻塞的必填项：" + "、".join(missing))
    else:
        lines.append("必填出行信息已具备；继续填候选和证据。")
    lines.extend([
        "",
        "| 信息 | 填写口径 |",
        "|---|---|",
    ])
    for label, example in INTAKE_FIELDS:
        lines.append(f"| {md_cell(label)} | {md_cell(example)} |")

    lines.extend([
        "",
        "## 真实候选最低覆盖",
        "",
        "| 类别 | 最低要求 |",
        "|---|---|",
    ])
    for label, requirement in MINIMUM_COVERAGE:
        lines.append(f"| {md_cell(label)} | {md_cell(requirement)} |")

    lines.extend([
        "",
        "## 文件接力顺序",
        "",
        "1. 生成或填写 `data/gannan_order_inputs.json`。",
        "2. 初始化四类候选 CSV、复核日志和证据目录。",
        "3. 每个候选先填价格、退改/取消、关键确认项和 `next_action`。",
        "4. 每轮复核截图或聊天记录先入 `evidence/gannan/`，再把相对路径填回候选 CSV 或复核日志。",
        "5. 用评分、覆盖、证据、差异和下单闸门逐级收口。",
        "",
        "## 推荐命令顺序",
        "",
        "```bash",
        "python3 scripts/gannan_order_start.py",
        "python3 scripts/gannan_order_start.py --init-files --route-start-date YYYY-MM-DD",
        "python3 scripts/check_gannan_inputs.py data/gannan_order_inputs.json",
        "python3 scripts/check_gannan_order_candidates.py data/gannan_flight_candidates.csv data/gannan_hotel_candidates.csv data/gannan_transport_quotes.csv data/gannan_ticket_candidates.csv",
        "python3 scripts/gannan_candidate_scorecard.py",
        "python3 scripts/check_gannan_order_coverage.py --strict",
        "python3 scripts/check_gannan_evidence.py --strict",
        "python3 scripts/gannan_reverification_diff.py --strict",
        "python3 scripts/gannan_booking_gate.py --strict",
        "python3 scripts/run_gannan_checks.py --online-sources --actual",
        "```",
        "",
        "## 接力完成定义",
        "",
        "只有 `python3 scripts/run_gannan_checks.py --online-sources --actual` 和 `python3 scripts/audit_gannan_goal_completion.py --strict` 都通过，才能说机票、酒店、车辆、门票、机位开放和证据已经完成订单级验证。",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="run deterministic structure check")
    args = parser.parse_args()

    report = render_markdown()
    if args.check:
        required = [
            "当前接力状态",
            "还需要用户给我的信息",
            "真实候选最低覆盖",
            "python3 scripts/run_gannan_checks.py --online-sources --actual",
        ]
        missing = [phrase for phrase in required if phrase not in report]
        if missing:
            print("Gannan order handoff self-check failed.")
            for phrase in missing:
                print(f"- missing phrase: {phrase}")
            return 1
        print("Gannan order handoff self-check passed.")
        print(f"Candidate files tracked: {len(CANDIDATE_FILES)}.")
        return 0

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.write_text(report, encoding="utf-8")
    print(f"Generated {rel(output)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
