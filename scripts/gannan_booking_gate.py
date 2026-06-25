#!/usr/bin/env python3
"""Generate a go/no-go booking decision gate for the Gannan trip."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from check_gannan_inputs import REQUIRED_FIELDS, get_value, is_filled
from check_gannan_order_candidates import validate_file
from check_gannan_order_coverage import validate_coverage
from gannan_candidate_scorecard import ACTIVE_STATUSES, collect_data as collect_score_data


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "甘南莲宝叶则_下单决策闸门.md"

ACTUAL_INPUT = ROOT / "data/gannan_order_inputs.json"
TEMPLATE_INPUT = ROOT / "data/gannan_order_inputs.template.json"
ACTUAL_LOG = ROOT / "data/gannan_reverification_log.csv"
SOURCE_FALLBACK_REPORT = ROOT / "甘南莲宝叶则_来源故障处理.md"

ACTUAL_CANDIDATE_FILES = {
    "flight": ROOT / "data/gannan_flight_candidates.csv",
    "hotel": ROOT / "data/gannan_hotel_candidates.csv",
    "transport": ROOT / "data/gannan_transport_quotes.csv",
    "ticket": ROOT / "data/gannan_ticket_candidates.csv",
}

KIND_LABELS = {
    "flight": "大交通",
    "hotel": "酒店",
    "transport": "包车/租车",
    "ticket": "门票",
}

READY_STATUSES = {"booked", "shortlist", "backup"}
LOG_EVIDENCE_STATUSES = {"pass", "watch", "fail", "blocked"}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def clean(value: str | None) -> str:
    return (value or "").strip()


def md_cell(value: object) -> str:
    text = str(value).strip() if value is not None else "-"
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


def gate_status(blocking: bool, warning: bool = False) -> str:
    if blocking:
        return "阻塞"
    if warning:
        return "需人工确认"
    return "通过"


def input_gate() -> dict[str, Any]:
    path = ACTUAL_INPUT if ACTUAL_INPUT.exists() else TEMPLATE_INPUT
    mode = "actual" if ACTUAL_INPUT.exists() else "template"
    data = read_json(path)
    missing = [label for field, label in REQUIRED_FIELDS if not is_filled(get_value(data, field))]
    return {
        "name": "出行信息",
        "status": gate_status(bool(missing)),
        "blocking": bool(missing),
        "detail": "必填信息已具备" if not missing else "缺：" + "、".join(missing),
        "path": path,
        "mode": mode,
        "data": data,
    }


def candidate_gate(score_data: dict[str, dict[str, object]], validation_errors: list[str]) -> dict[str, Any]:
    total_rows = sum(len(item["rows"]) for item in score_data.values())  # type: ignore[arg-type]
    actual_files = [path for path in ACTUAL_CANDIDATE_FILES.values() if path.exists()]
    blocking = bool(validation_errors) or not actual_files or total_rows == 0
    if validation_errors:
        detail = f"候选 CSV 有 {len(validation_errors)} 个结构问题"
    elif not actual_files:
        detail = "还没有真实候选 CSV"
    elif total_rows == 0:
        detail = "真实候选 CSV 仍为空"
    else:
        detail = f"已读取 {total_rows} 条候选"
    return {
        "name": "候选表结构",
        "status": gate_status(blocking),
        "blocking": blocking,
        "detail": detail,
        "validation_errors": validation_errors,
    }


def score_gate(score_data: dict[str, dict[str, object]], min_score: int) -> dict[str, Any]:
    blockers: list[str] = []
    top_by_kind: dict[str, dict[str, object] | None] = {}
    for kind, item in score_data.items():
        scores: list[dict[str, object]] = item["scores"]  # type: ignore[assignment]
        active_scores = [score for score in scores if str(score["status"]) in ACTIVE_STATUSES]
        top_by_kind[kind] = active_scores[0] if active_scores else None
        ready_scores = [
            score for score in active_scores
            if str(score["status"]) in READY_STATUSES and int(score["score"]) >= min_score
        ]
        if item["mode"] == "actual" and active_scores and not ready_scores:
            blockers.append(f"{KIND_LABELS[kind]}没有达到 {min_score} 分的 shortlist/booked/backup 候选")

    total_active = sum(
        1 for item in score_data.values() for score in item["scores"]  # type: ignore[union-attr]
        if str(score["status"]) in ACTIVE_STATUSES
    )
    blocking = bool(blockers) or total_active == 0
    detail = f"活跃候选 {total_active} 条" if total_active else "没有可评分的真实活跃候选"
    if blockers:
        detail = "；".join(blockers)
    return {
        "name": "候选评分",
        "status": gate_status(blocking),
        "blocking": blocking,
        "detail": detail,
        "top_by_kind": top_by_kind,
        "blockers": blockers,
    }


def coverage_gate(score_data: dict[str, dict[str, object]]) -> dict[str, Any]:
    rows_by_kind = {
        kind: item["rows"]  # type: ignore[assignment]
        for kind, item in score_data.items()
    }
    total_rows = sum(len(rows) for rows in rows_by_kind.values())
    if total_rows == 0:
        return {
            "name": "行程覆盖",
            "status": "阻塞",
            "blocking": True,
            "detail": "没有真实候选，无法证明去返程、D1-D8 酒店、车辆和核心门票覆盖",
            "errors": [],
            "warnings": [],
        }
    errors, warnings = validate_coverage(rows_by_kind, strict=True, booking_ready=True)
    return {
        "name": "行程覆盖",
        "status": gate_status(bool(errors), bool(warnings)),
        "blocking": bool(errors),
        "detail": "覆盖完整" if not errors else "；".join(errors[:4]),
        "errors": errors,
        "warnings": warnings,
    }


def evidence_gate() -> dict[str, Any]:
    missing: list[str] = []
    referenced = 0
    for kind, path in ACTUAL_CANDIDATE_FILES.items():
        for row in read_csv_rows(path):
            status = clean(row.get("status"))
            evidence = clean(row.get("evidence_file"))
            if status in ACTIVE_STATUSES and not evidence:
                missing.append(f"{KIND_LABELS[kind]} {clean(row.get('option_id')) or '未命名'} 缺 evidence_file")
            elif evidence:
                referenced += 1

    for row in read_csv_rows(ACTUAL_LOG):
        status = clean(row.get("status"))
        evidence = clean(row.get("evidence_file"))
        item = clean(row.get("item")) or "未命名复核项"
        if status in LOG_EVIDENCE_STATUSES and not evidence:
            missing.append(f"复核日志 {item} 缺 evidence_file")
        elif evidence:
            referenced += 1

    actual_rows = sum(len(read_csv_rows(path)) for path in ACTUAL_CANDIDATE_FILES.values()) + len(read_csv_rows(ACTUAL_LOG))
    blocking = bool(missing) or actual_rows == 0
    detail = f"引用证据 {referenced} 个" if referenced else "还没有真实证据引用"
    if missing:
        detail = f"{len(missing)} 个活跃/已复核项缺证据"
    return {
        "name": "证据归档",
        "status": gate_status(blocking),
        "blocking": blocking,
        "detail": detail,
        "missing": missing,
    }


def log_gate() -> dict[str, Any]:
    if not ACTUAL_LOG.exists():
        return {
            "name": "复核日志",
            "status": "阻塞",
            "blocking": True,
            "detail": "缺少 data/gannan_reverification_log.csv",
            "counts": Counter(),
        }
    rows = read_csv_rows(ACTUAL_LOG)
    counts: Counter[str] = Counter(clean(row.get("status")) or "blank" for row in rows)
    completed = [row for row in rows if clean(row.get("status")) != "n/a"]
    bad = counts.get("fail", 0) + counts.get("blocked", 0)
    blocking = not completed or bad > 0
    if not completed:
        detail = "复核日志还没有真实完成行"
    elif bad:
        detail = f"存在 fail/blocked 复核项 {bad} 个"
    else:
        detail = f"已记录 {len(completed)} 条真实复核"
    return {
        "name": "复核日志",
        "status": gate_status(blocking),
        "blocking": blocking,
        "detail": detail,
        "counts": counts,
    }


def source_gate() -> dict[str, Any]:
    if not SOURCE_FALLBACK_REPORT.exists():
        return {
            "name": "来源故障",
            "status": "需人工确认",
            "blocking": False,
            "detail": "缺少来源故障处理报告",
            "blocker_rows": [],
        }

    text = SOURCE_FALLBACK_REPORT.read_text(encoding="utf-8")
    if "本次未执行在线探测" in text:
        return {
            "name": "来源故障",
            "status": "需人工确认",
            "blocking": False,
            "detail": "未执行在线来源探测；下单前应运行 --online-sources",
            "blocker_rows": [],
        }

    blocker_rows: list[str] = []
    in_table = False
    for line in text.splitlines():
        if line.startswith("| ID | 项目 | 状态 | 必须补的证据 |"):
            in_table = True
            continue
        if in_table:
            if not line.strip():
                break
            if line.startswith("|---"):
                continue
            if line.startswith("|"):
                blocker_rows.append(line)

    blocking = bool(blocker_rows)
    detail = "无 A 级自动探测阻塞项" if not blocking else f"{len(blocker_rows)} 个 A 级来源需人工补证据"
    return {
        "name": "来源故障",
        "status": gate_status(blocking),
        "blocking": blocking,
        "detail": detail,
        "blocker_rows": blocker_rows,
    }


def build_gates(min_score: int) -> tuple[list[dict[str, Any]], dict[str, dict[str, object]]]:
    score_data, validation_errors = collect_score_data()
    gates = [
        input_gate(),
        candidate_gate(score_data, validation_errors),
        score_gate(score_data, min_score),
        coverage_gate(score_data),
        evidence_gate(),
        log_gate(),
        source_gate(),
    ]
    return gates, score_data


def overall_decision(gates: list[dict[str, Any]]) -> str:
    blockers = [gate for gate in gates if gate["blocking"]]
    if blockers:
        return "不能下单"
    if any(gate["status"] == "需人工确认" for gate in gates):
        return "可准备下单，但需人工确认"
    return "可以进入下单"


def render_gate_table(gates: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| 闸门 | 状态 | 说明 |",
        "|---|---|---|",
    ]
    for gate in gates:
        lines.append(f"| {gate['name']} | {gate['status']} | {md_cell(gate['detail'])} |")
    return lines


def render_top_candidates(score_data: dict[str, dict[str, object]]) -> list[str]:
    lines = [
        "## 分项下单候选",
        "",
        "| 类型 | 模式 | 候选数 | 当前最高分候选 | 分数 | 等级 |",
        "|---|---|---:|---|---:|---|",
    ]
    for kind in ["flight", "hotel", "transport", "ticket"]:
        item = score_data[kind]
        scores: list[dict[str, object]] = item["scores"]  # type: ignore[assignment]
        active_scores = [score for score in scores if str(score["status"]) in ACTIVE_STATUSES]
        top = active_scores[0] if active_scores else None
        lines.append(
            "| "
            + " | ".join([
                KIND_LABELS[kind],
                "真实" if item["mode"] == "actual" else "模板",
                str(len(item["rows"])),  # type: ignore[arg-type]
                md_cell(f"{top['option_id']} {top['name']}" if top else "待填"),
                md_cell(top["score"] if top else "-"),
                md_cell(top["grade"] if top else "待填候选"),
            ])
            + " |"
        )
    return lines


def render_action_list(gates: list[dict[str, Any]]) -> list[str]:
    lines = ["## 下一步动作", ""]
    action_map = {
        "出行信息": "先用 `gannan-input-wizard.html` 生成 `data/gannan_order_inputs.json`。",
        "候选表结构": "复制并填写四类真实候选 CSV，至少覆盖去返程、D1-D8 酒店、车辆和核心门票。",
        "候选评分": "运行 `python3 scripts/gannan_candidate_scorecard.py`，把低分候选补齐证据、退改/取消和关键确认。",
        "行程覆盖": "运行 `python3 scripts/check_gannan_order_coverage.py --strict`，补齐缺失夜晚、车辆或核心门票来源。",
        "证据归档": "把订单页截图、电话/聊天确认、公告截图和现场牌示存入 `evidence/gannan/` 并填回 CSV。",
        "复核日志": "按出发日期生成并填写 `data/gannan_reverification_log.csv`，每轮写清状态、决策和下一步。",
        "来源故障": "运行 `python3 scripts/run_gannan_checks.py --online-sources`，对 A 级失败来源按故障处理报告补人工证据。",
    }
    for gate in gates:
        if gate["blocking"] or gate["status"] == "需人工确认":
            lines.append(f"- {action_map.get(gate['name'], gate['detail'])}")
    if len(lines) == 2:
        lines.append("- 所有闸门已通过；下单前仍需保存最终订单页截图。")
    return lines


def render_markdown(gates: list[dict[str, Any]], score_data: dict[str, dict[str, object]], *, min_score: int) -> str:
    blockers = [gate for gate in gates if gate["blocking"]]
    lines = [
        "# 甘南 + 莲宝叶则下单决策闸门",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        "订单复核报告：[甘南莲宝叶则_订单复核报告.md](甘南莲宝叶则_订单复核报告.md)  ",
        "候选评分卡：[甘南莲宝叶则_候选评分卡.md](甘南莲宝叶则_候选评分卡.md)  ",
        "来源故障处理：[甘南莲宝叶则_来源故障处理.md](甘南莲宝叶则_来源故障处理.md)",
        "",
        "这份闸门把出行信息、候选评分、行程覆盖、证据、复核日志和来源故障合成一个下单前 go/no-go 判定。它不会替代人工下单，只负责防止缺证据、缺覆盖或来源冲突时误下单。",
        "",
        "## 当前结论",
        "",
        f"- 结论：{overall_decision(gates)}。",
        f"- 阻塞闸门：{len(blockers)} 个。",
        f"- 评分阈值：真实 shortlist/booked/backup 候选建议不低于 {min_score} 分。",
        "",
        *render_gate_table(gates),
        "",
        *render_top_candidates(score_data),
        "",
        *render_action_list(gates),
        "",
        "## 使用命令",
        "",
        "```bash",
        "python3 scripts/gannan_booking_gate.py",
        "python3 scripts/gannan_booking_gate.py --strict",
        "python3 scripts/gannan_booking_gate.py --check",
        "```",
        "",
        "真实订单阶段完整检查：",
        "",
        "```bash",
        "python3 scripts/run_gannan_checks.py --actual",
        "python3 scripts/run_gannan_checks.py --online-sources --actual",
        "```",
        "",
    ]
    return "\n".join(lines)


def self_check(text: str) -> list[str]:
    errors: list[str] = []
    for phrase in [
        "当前结论",
        "分项下单候选",
        "下一步动作",
        "python3 scripts/gannan_booking_gate.py --strict",
    ]:
        if phrase not in text:
            errors.append(f"missing phrase: {phrase}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-score", type=int, default=70, help="minimum score for booking-ready candidates")
    parser.add_argument("--strict", action="store_true", help="fail when any booking gate is blocking")
    parser.add_argument("--check", action="store_true", help="run deterministic report self-check without writing")
    args = parser.parse_args()

    gates, score_data = build_gates(args.min_score)
    text = render_markdown(gates, score_data, min_score=args.min_score)
    errors = self_check(text)
    if errors:
        print("Gannan booking gate self-check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    blockers = [gate for gate in gates if gate["blocking"]]
    if args.check:
        print("Gannan booking gate self-check passed.")
        print(f"Evaluated {len(gates)} gate(s); current blockers: {len(blockers)}.")
        return 0

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.write_text(text, encoding="utf-8")
    print(f"Generated {rel(output)}")

    if args.strict and blockers:
        print("Gannan booking gate failed:")
        for gate in blockers:
            print(f"- {gate['name']}: {gate['detail']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
