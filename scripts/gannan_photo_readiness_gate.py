#!/usr/bin/env python3
"""Generate a photo-readiness gate for the Gannan route."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "甘南莲宝叶则_出片准备闸门.md"

PHOTO_SPOTS = ROOT / "data/gannan_photo_spots.csv"
LIGHT_POINTS = ROOT / "data/gannan_light_points.csv"
ORDER_INPUT = ROOT / "data/gannan_order_inputs.json"
REVERIFICATION_LOG = ROOT / "data/gannan_reverification_log.csv"
EVIDENCE_DIR = ROOT / "evidence/gannan"

REQUIRED_DOCS = {
    "每日执行卡": (
        ROOT / "甘南莲宝叶则_每日执行卡.md",
        ["扎尕那全天", "莲宝叶则全天", "每晚 5 分钟复盘", "不能压缩"],
    ),
    "大片交付清单": (
        ROOT / "甘南莲宝叶则_大片交付清单.md",
        ["封面级主图", "失败天气备选图", "短视频镜头", "每晚交付复盘"],
    ),
    "装备 Checklist": (
        ROOT / "甘南莲宝叶则_装备Checklist.md",
        ["备用电池", "存储卡", "移动硬盘", "相机雨罩", "三脚架"],
    ),
    "高原天气应急预案": (
        ROOT / "甘南莲宝叶则_高原天气应急预案.md",
        ["三条红线", "高原反应执行梯度", "天气和路况红旗", "景区闭园 / 开放范围变化"],
    ),
}

S_REQUIRED_FIELDS = [
    "search_keyword",
    "map_url",
    "golden_window",
    "primary_lens",
    "required_output",
    "verification_sources",
    "access_risk",
    "abort_condition",
]

LIGHT_WORDS = ["日出", "日落", "清晨", "傍晚", "上午", "下午", "蓝调", "黄金"]
ACTUAL_LOG_WORDS = ["天气", "开放", "闭园", "扎尕那", "莲宝", "观光车", "门票", "路况"]


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


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def dotted_value(data: dict[str, Any], dotted: str) -> Any:
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


def count_by_priority(rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        priority: sum(1 for row in rows if clean(row.get("priority")) == priority)
        for priority in ["S", "A", "B"]
    }


def make_gate(
    name: str,
    status: str,
    detail: str,
    evidence: str,
    *,
    strategy_blocking: bool = False,
    full_blocking: bool = False,
) -> dict[str, object]:
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "evidence": evidence,
        "strategy_blocking": strategy_blocking,
        "full_blocking": full_blocking,
    }


def spot_gate(rows: list[dict[str, str]]) -> dict[str, object]:
    if not rows:
        return make_gate(
            "S 级机位池",
            "阻塞",
            "没有读取到结构化机位表。",
            rel(PHOTO_SPOTS),
            strategy_blocking=True,
            full_blocking=True,
        )

    s_rows = [row for row in rows if clean(row.get("priority")) == "S"]
    joined_s = " / ".join(f"{clean(row.get('area'))} {clean(row.get('spot_name'))}" for row in s_rows)
    blockers: list[str] = []
    if len(s_rows) < 4:
        blockers.append(f"S 级机位只有 {len(s_rows)} 个")
    for required in ["扎尕那", "莲宝叶则"]:
        if required not in joined_s:
            blockers.append(f"S 级机位缺少 {required}")
    for row in s_rows:
        label = f"{clean(row.get('area'))}{clean(row.get('spot_name'))}"
        missing = [field for field in S_REQUIRED_FIELDS if not clean(row.get(field))]
        if missing:
            blockers.append(f"{label} 缺字段：{', '.join(missing)}")
        if not any(word in clean(row.get("golden_window")) for word in LIGHT_WORDS):
            blockers.append(f"{label} 光线窗口不明确")

    counts = count_by_priority(rows)
    detail = f"S={counts['S']}，A={counts['A']}，B={counts['B']}；扎尕那和莲宝叶则均有 S 级核心机位。"
    if blockers:
        detail = "；".join(blockers[:5])
    return make_gate(
        "S 级机位池",
        "通过" if not blockers else "阻塞",
        detail,
        f"{rel(PHOTO_SPOTS)} / scripts/check_gannan_photo_spots.py",
        strategy_blocking=bool(blockers),
        full_blocking=bool(blockers),
    )


def light_gate(input_data: dict[str, Any]) -> dict[str, object]:
    blockers: list[str] = []
    if not (ROOT / "scripts/gannan_light_windows.py").exists():
        blockers.append("缺少光线计算脚本")
    light_rows = read_csv_rows(LIGHT_POINTS)
    if len(light_rows) < 7:
        blockers.append(f"光线点只有 {len(light_rows)} 个")

    departure_date = clean(dotted_value(input_data, "trip.departure_date"))
    if blockers:
        return make_gate(
            "光线窗口",
            "阻塞",
            "；".join(blockers),
            "scripts/gannan_light_windows.py / data/gannan_light_points.csv",
            strategy_blocking=True,
            full_blocking=True,
        )
    if departure_date:
        detail = f"已具备 {len(light_rows)} 个光线点；可按 D1={departure_date} 生成每日黄金时段和蓝调窗口。"
        return make_gate("光线窗口", "通过", detail, "scripts/gannan_light_windows.py --start YYYY-MM-DD")
    return make_gate(
        "光线窗口",
        "需真实日期",
        f"已具备 {len(light_rows)} 个光线点和离线计算器；还需 D1 日期生成当季日出、日落、蓝调表。",
        "scripts/gannan_light_windows.py --start YYYY-MM-DD",
        full_blocking=True,
    )


def required_doc_gate(label: str, path: Path, phrases: list[str]) -> dict[str, object]:
    text = read_text(path)
    if not text:
        return make_gate(
            label,
            "阻塞",
            f"缺少 {rel(path)}",
            rel(path),
            strategy_blocking=True,
            full_blocking=True,
        )
    missing = [phrase for phrase in phrases if phrase not in text]
    if missing:
        return make_gate(
            label,
            "阻塞",
            "缺关键词：" + "、".join(missing),
            rel(path),
            strategy_blocking=True,
            full_blocking=True,
        )
    return make_gate(label, "通过", "关键执行内容已覆盖。", rel(path))


def actual_gate(input_data: dict[str, Any]) -> dict[str, object]:
    blockers: list[str] = []
    if not ORDER_INPUT.exists():
        blockers.append("缺 data/gannan_order_inputs.json")
    elif not is_filled(dotted_value(input_data, "trip.departure_date")):
        blockers.append("缺真实出发日期")

    log_rows = read_csv_rows(REVERIFICATION_LOG)
    completed_rows = [
        row for row in log_rows
        if clean(row.get("status")) in {"pass", "watch", "fail", "blocked"}
    ]
    actual_text = " ".join(
        f"{clean(row.get('category'))} {clean(row.get('item'))} {clean(row.get('notes'))}"
        for row in completed_rows
    )
    if not completed_rows:
        blockers.append("缺已完成的 T-3/T-1/当天复核日志")
    elif not any(word in actual_text for word in ACTUAL_LOG_WORDS):
        blockers.append("复核日志缺天气、开放、路况或核心景区记录")

    evidence_files = [
        path for path in EVIDENCE_DIR.glob("**/*")
        if path.is_file() and path.name != "README.md"
    ] if EVIDENCE_DIR.exists() else []
    if not evidence_files:
        blockers.append("缺本地证据截图/确认记录")

    if blockers:
        return make_gate(
            "真实日期、天气和开放",
            "待真实复核",
            "；".join(blockers),
            "data/gannan_order_inputs.json / data/gannan_reverification_log.csv / evidence/gannan/",
            full_blocking=True,
        )
    return make_gate(
        "真实日期、天气和开放",
        "通过",
        f"已读取 {len(completed_rows)} 条真实复核记录和 {len(evidence_files)} 个证据文件。",
        "data/gannan_reverification_log.csv / evidence/gannan/",
    )


def build_gates(rows: list[dict[str, str]], input_data: dict[str, Any]) -> list[dict[str, object]]:
    gates = [
        spot_gate(rows),
        light_gate(input_data),
    ]
    for label, (path, phrases) in REQUIRED_DOCS.items():
        gates.append(required_doc_gate(label, path, phrases))
    gates.append(actual_gate(input_data))
    return gates


def conclusion(gates: list[dict[str, object]]) -> str:
    strategy_blockers = [gate for gate in gates if gate["strategy_blocking"]]
    full_blockers = [gate for gate in gates if gate["full_blocking"]]
    if not full_blockers:
        return "完整可执行：策略、日期、天气/开放复核和证据均已闭环，可以按出片计划执行。"
    if not strategy_blockers:
        return "策略级可拍，真实出发前仍需复核：机位、光线工具、每日执行、装备和应急已经闭环；没有真实日期、天气/开放和证据前，不能宣称已保住大片。"
    return "出片策略未闭环：先修复阻塞项，再进入真实日期和天气复核。"


def s_spot_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if clean(row.get("priority")) == "S"]


def render_markdown(rows: list[dict[str, str]], gates: list[dict[str, object]]) -> str:
    lines = [
        "# 甘南 + 莲宝叶则出片准备闸门",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "对应机位表：[data/gannan_photo_spots.csv](data/gannan_photo_spots.csv)  ",
        "对应出片清单：[甘南莲宝叶则_大片交付清单.md](甘南莲宝叶则_大片交付清单.md)  ",
        "对应每日执行卡：[甘南莲宝叶则_每日执行卡.md](甘南莲宝叶则_每日执行卡.md)",
        "",
        "## 当前结论",
        "",
        conclusion(gates),
        "",
        "## 闸门总表",
        "",
        "| 闸门 | 状态 | 说明 | 证据 |",
        "|---|---|---|---|",
    ]
    for gate in gates:
        lines.append(
            "| {name} | {status} | {detail} | {evidence} |".format(
                name=md_cell(gate["name"]),
                status=md_cell(gate["status"]),
                detail=md_cell(gate["detail"]),
                evidence=md_cell(gate["evidence"]),
            )
        )

    lines.extend([
        "",
        "## S 级机位池",
        "",
        "| 天数 | 区域 | 机位 | 最佳窗口 | 主力镜头 | 必带回画面 | 放弃条件 |",
        "|---|---|---|---|---|---|---|",
    ])
    for row in s_spot_rows(rows):
        lines.append(
            "| {day} | {area} | {spot_name} | {golden_window} | {primary_lens} | {required_output} | {abort_condition} |".format(
                day=md_cell(row.get("day")),
                area=md_cell(row.get("area")),
                spot_name=md_cell(row.get("spot_name")),
                golden_window=md_cell(row.get("golden_window")),
                primary_lens=md_cell(row.get("primary_lens")),
                required_output=md_cell(row.get("required_output")),
                abort_condition=md_cell(row.get("abort_condition")),
            )
        )

    lines.extend([
        "",
        "## 出发前不能省的复核",
        "",
        "- D1 日期确定后，运行光线窗口脚本生成真实日出、日落、黄金时段和蓝调表。",
        "- T-3、T-1、当天早上分别确认扎尕那、莲宝叶则、花湖、黄河九曲的开放范围、观光车/栈道和天气。",
        "- 司机/酒店/景区确认结果必须写入复核日志，并把截图或聊天记录放进 `evidence/gannan/`。",
        "- 每晚按出片清单复盘：封面候选、故事图、短视频、安全图、失败天气替代素材和双备份。",
        "",
        "## 命令",
        "",
        "```bash",
        "python3 scripts/gannan_photo_readiness_gate.py",
        "python3 scripts/gannan_photo_readiness_gate.py --check",
        "python3 scripts/gannan_photo_readiness_gate.py --strict",
        "```",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--strict", action="store_true", help="fail unless the full photo-readiness gate is closed")
    parser.add_argument("--check", action="store_true", help="run a deterministic structure check")
    args = parser.parse_args()

    rows = read_csv_rows(PHOTO_SPOTS)
    input_data = read_json(ORDER_INPUT)
    gates = build_gates(rows, input_data)
    report = render_markdown(rows, gates)

    if args.check:
        required = ["策略级可拍", "真实出发前仍需复核", "S 级机位池", "python3 scripts/gannan_photo_readiness_gate.py --strict"]
        missing = [phrase for phrase in required if phrase not in report]
        if missing:
            print("Gannan photo readiness gate self-check failed.")
            for phrase in missing:
                print(f"- missing phrase: {phrase}")
            return 1
        print("Gannan photo readiness gate self-check passed.")
        print(f"Checked {len(rows)} photo spots and {len(gates)} readiness gates.")
        return 0

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.write_text(report, encoding="utf-8")
    print(f"Generated {rel(output)}")

    blockers = [gate for gate in gates if gate["full_blocking"]]
    if args.strict and blockers:
        print("Gannan photo readiness gate failed:")
        for gate in blockers:
            print(f"- {gate['name']}: {gate['detail']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
