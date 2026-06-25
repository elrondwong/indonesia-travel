#!/usr/bin/env python3
"""Rank Gannan order candidates by readiness, evidence, and booking safety."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from check_gannan_order_candidates import TEMPLATES, validate_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "甘南莲宝叶则_候选评分卡.md"

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

STATUS_POINTS = {
    "booked": 20,
    "shortlist": 18,
    "backup": 14,
    "watch": 10,
    "candidate": 10,
    "rejected": 0,
}

STATUS_SORT = {
    "booked": 0,
    "shortlist": 1,
    "backup": 2,
    "watch": 3,
    "candidate": 4,
    "rejected": 9,
}

ACTIVE_STATUSES = {"booked", "shortlist", "backup", "watch", "candidate"}

POLICY_FIELDS = {
    "flight": [
        ("baggage_or_luggage", "行李/摄影器材"),
        ("refund_change_policy", "退改规则"),
        ("arrival_transfer", "到达兰州后接驳"),
        ("booking_url", "下单入口"),
    ],
    "hotel": [
        ("cancel_deadline", "取消截止"),
        ("parking_confirmed", "停车"),
        ("hot_water_heating_confirmed", "热水/供暖"),
        ("early_departure_confirmed", "早出门"),
        ("breakfast_plan", "早餐"),
        ("real_photo_checked", "真实照片"),
        ("contact_or_url", "联系入口"),
    ],
    "transport": [
        ("includes_fuel", "油费"),
        ("includes_toll", "高速/过路费"),
        ("includes_parking", "停车费"),
        ("driver_meals_lodging", "司机食宿"),
        ("insurance_confirmed", "保险"),
        ("night_drive_policy", "夜路政策"),
        ("cancellation_policy", "取消规则"),
        ("contact_or_url", "联系入口"),
    ],
    "ticket": [
        ("refund_policy", "退改/取消"),
        ("open_hours", "开放时间"),
        ("latest_entry", "最晚入园"),
        ("latest_exit", "最晚离园"),
        ("open_scope_confirmed", "开放范围"),
        ("booking_url_or_contact", "预约/确认入口"),
    ],
}

PRICE_FIELDS = {
    "flight": "final_price_cny",
    "hotel": "final_price_cny",
    "transport": "total_price_cny",
    "ticket": "final_price_cny",
}

CONTACT_FIELDS = {
    "flight": "booking_url",
    "hotel": "contact_or_url",
    "transport": "contact_or_url",
    "ticket": "booking_url_or_contact",
}


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


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def choose_candidate_file(kind: str) -> tuple[Path, str]:
    actual = ACTUAL_CANDIDATE_FILES[kind]
    if actual.exists():
        return actual, "actual"
    return TEMPLATES[kind]["path"], "template"


def money(value: str | None) -> str:
    raw = clean(value)
    if not raw:
        return "-"
    try:
        number = float(raw)
    except ValueError:
        return raw
    if number.is_integer():
        return f"{int(number)}"
    return f"{number:.2f}"


def numeric_price(kind: str, row: dict[str, str]) -> float | None:
    raw = clean(row.get(PRICE_FIELDS[kind]))
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def row_name(kind: str, row: dict[str, str]) -> str:
    if kind == "flight":
        parts = [
            clean(row.get("carrier_or_railway")),
            clean(row.get("flight_or_train_no")),
            f"{clean(row.get('origin'))}->{clean(row.get('destination'))}".strip("->"),
        ]
    elif kind == "hotel":
        parts = [clean(row.get("hotel_name")), clean(row.get("area"))]
    elif kind == "transport":
        parts = [clean(row.get("supplier_or_driver")), clean(row.get("vehicle_model"))]
    elif kind == "ticket":
        parts = [clean(row.get("scenic_area")), clean(row.get("ticket_type"))]
    else:
        parts = []
    return " ".join(part for part in parts if part) or clean(row.get("option_id")) or "-"


def row_context(kind: str, row: dict[str, str]) -> str:
    if kind == "flight":
        parts = [clean(row.get("direction")), clean(row.get("depart_date")), clean(row.get("depart_time"))]
    elif kind == "hotel":
        parts = [clean(row.get("stay_day")), clean(row.get("check_in")), clean(row.get("check_out"))]
    elif kind == "transport":
        parts = [clean(row.get("type")), clean(row.get("start_date")), clean(row.get("end_date"))]
    elif kind == "ticket":
        parts = [clean(row.get("target_date")), clean(row.get("platform_or_source"))]
    else:
        parts = []
    return " / ".join(part for part in parts if part) or "-"


def value_is_confirmed(value: str | None) -> bool:
    raw = clean(value).lower()
    if not raw:
        return False
    return raw not in {"no", "false", "unknown", "待确认", "未知", "否", "不确定"}


def price_points(kind: str, row: dict[str, str], active_prices: list[float]) -> tuple[int, list[str]]:
    price = numeric_price(kind, row)
    if price is None:
        return 0, ["缺最终含税/总价"]

    points = 10
    if active_prices:
        low = min(active_prices)
        high = max(active_prices)
        if high == low:
            points += 5
        else:
            competitiveness = max(0.0, min(1.0, (high - price) / (high - low)))
            points += round(competitiveness * 5)
    return points, []


def policy_points(kind: str, row: dict[str, str]) -> tuple[int, list[str]]:
    fields = POLICY_FIELDS[kind]
    if not fields:
        return 35, []

    confirmed = 0
    missing: list[str] = []
    for field, label in fields:
        if value_is_confirmed(row.get(field)):
            confirmed += 1
        else:
            missing.append(label)
    points = round((confirmed / len(fields)) * 35)
    return points, [f"缺{label}" for label in missing]


def score_row(kind: str, row: dict[str, str], active_prices: list[float]) -> dict[str, object]:
    deductions: list[str] = []
    status = clean(row.get("status")) or "blank"
    score = STATUS_POINTS.get(status, 0)
    if status not in STATUS_POINTS:
        deductions.append("状态未识别")
    if status == "rejected":
        deductions.append("已淘汰")

    points, price_deductions = price_points(kind, row, active_prices)
    score += points
    deductions.extend(price_deductions)

    points, policy_deductions = policy_points(kind, row)
    score += points
    deductions.extend(policy_deductions[:4])
    if len(policy_deductions) > 4:
        deductions.append(f"另缺{len(policy_deductions) - 4}项确认")

    if value_is_confirmed(row.get("evidence_file")):
        score += 15
    else:
        deductions.append("缺证据截图/确认记录")

    decision = value_is_confirmed(row.get("decision"))
    next_action = value_is_confirmed(row.get("next_action"))
    if decision:
        score += 7
    else:
        deductions.append("缺决策")
    if next_action or status == "booked":
        score += 8
    else:
        deductions.append("缺下一步动作")

    if value_is_confirmed(row.get(CONTACT_FIELDS[kind])):
        score += 5
    else:
        deductions.append("缺联系/下单入口")

    score = max(0, min(100, score))
    return {
        "option_id": clean(row.get("option_id")) or "-",
        "name": row_name(kind, row),
        "context": row_context(kind, row),
        "status": status,
        "price": money(row.get(PRICE_FIELDS[kind])),
        "score": score,
        "grade": grade(score),
        "deductions": deductions,
        "next_action": clean(row.get("next_action")) or "-",
    }


def grade(score: int) -> str:
    if score >= 85:
        return "A 可进入下单候选"
    if score >= 70:
        return "B 可短名单观察"
    if score >= 50:
        return "C 继续补证据"
    return "D 暂缓"


def score_kind(kind: str, rows: list[dict[str, str]]) -> list[dict[str, object]]:
    active_prices = [
        price for row in rows
        if clean(row.get("status")) in ACTIVE_STATUSES
        for price in [numeric_price(kind, row)]
        if price is not None
    ]
    scored = [score_row(kind, row, active_prices) for row in rows]
    return sorted(
        scored,
        key=lambda item: (
            -int(item["score"]),
            STATUS_SORT.get(str(item["status"]), 9),
            str(item["option_id"]),
        ),
    )


def collect_data() -> tuple[dict[str, dict[str, object]], list[str]]:
    data: dict[str, dict[str, object]] = {}
    validation_errors: list[str] = []
    for kind in ["flight", "hotel", "transport", "ticket"]:
        path, mode = choose_candidate_file(kind)
        _, errors = validate_file(path, kind)
        validation_errors.extend(f"{KIND_LABELS[kind]} {error}" for error in errors)
        rows = read_csv_rows(path)
        data[kind] = {
            "path": path,
            "mode": mode,
            "rows": rows,
            "scores": score_kind(kind, rows),
        }
    return data, validation_errors


def render_summary(data: dict[str, dict[str, object]]) -> list[str]:
    total_rows = sum(len(item["rows"]) for item in data.values())  # type: ignore[arg-type]
    if total_rows == 0:
        conclusion = "暂无真实候选，不产生推荐排序；先复制候选模板并填入实际日期价格。"
    else:
        conclusion = "已按当前 CSV 生成候选排序；进入 shortlist/booked 前建议评分不低于 75，且必须有证据截图。"

    lines = [
        "## 当前结论",
        "",
        f"- {conclusion}",
        "- 评分卡只帮助排序，不替代真实下单页、酒店电话、司机文字确认、景区公告和现场牌示。",
        "",
        "| 类型 | 数据文件 | 模式 | 候选数 | 最高分 | 推荐状态 |",
        "|---|---|---|---:|---:|---|",
    ]
    for kind in ["flight", "hotel", "transport", "ticket"]:
        item = data[kind]
        scores: list[dict[str, object]] = item["scores"]  # type: ignore[assignment]
        top = scores[0] if scores else None
        lines.append(
            "| "
            + " | ".join([
                KIND_LABELS[kind],
                f"[{rel(item['path'])}]({rel(item['path'])})",  # type: ignore[arg-type]
                "真实" if item["mode"] == "actual" else "模板",
                str(len(item["rows"])),  # type: ignore[arg-type]
                str(top["score"]) if top else "-",
                str(top["grade"]) if top else "待填候选",
            ])
            + " |"
        )
    return lines


def render_score_tables(data: dict[str, dict[str, object]], limit: int) -> list[str]:
    lines: list[str] = []
    for kind in ["flight", "hotel", "transport", "ticket"]:
        item = data[kind]
        scores: list[dict[str, object]] = item["scores"]  # type: ignore[assignment]
        lines.extend(["", f"## {KIND_LABELS[kind]}评分", ""])
        if not scores:
            lines.append("暂无候选。")
            continue
        lines.extend([
            "| 排名 | 候选 | 场景 | 状态 | 价格 | 分数 | 等级 | 主要扣分 | 下一步 |",
            "|---:|---|---|---|---:|---:|---|---|---|",
        ])
        for index, score in enumerate(scores[:limit], start=1):
            deductions = score["deductions"]  # type: ignore[assignment]
            deduction_text = "无明显扣分" if not deductions else "；".join(str(item) for item in deductions[:5])
            if len(deductions) > 5:
                deduction_text += f"；另有 {len(deductions) - 5} 项"
            lines.append(
                "| "
                + " | ".join([
                    str(index),
                    md_cell(f"{score['option_id']} {score['name']}"),
                    md_cell(score["context"]),
                    md_cell(score["status"]),
                    md_cell(score["price"]),
                    md_cell(score["score"]),
                    md_cell(score["grade"]),
                    md_cell(deduction_text),
                    md_cell(score["next_action"]),
                ])
                + " |"
            )
    return lines


def render_markdown(
    data: dict[str, dict[str, object]],
    validation_errors: list[str],
    *,
    generated_at: str,
    limit: int,
) -> str:
    lines = [
        "# 甘南 + 莲宝叶则候选评分卡",
        "",
        f"生成时间：{generated_at}  ",
        "订单复核报告：[甘南莲宝叶则_订单复核报告.md](甘南莲宝叶则_订单复核报告.md)  ",
        "订单覆盖率闸门：[甘南莲宝叶则_订单覆盖率闸门.md](甘南莲宝叶则_订单覆盖率闸门.md)",
        "",
        "这份评分卡把机票/高铁、酒店、车辆和门票候选按状态、价格、关键确认项、证据和下一步动作排序。它回答“同一类候选里先推进哪一个”，不回答“是否已经完成真实下单验证”。",
        "",
        *render_summary(data),
    ]

    if validation_errors:
        lines.extend(["", "## CSV 结构问题", ""])
        lines.extend(f"- {error}" for error in validation_errors)

    lines.extend(render_score_tables(data, limit))
    lines.extend([
        "",
        "## 评分口径",
        "",
        "| 维度 | 分值 | 含义 |",
        "|---|---:|---|",
        "| 状态 | 20 | booked/shortlist/backup 优先，rejected 不再推进 |",
        "| 价格 | 15 | 必须有最终含税/总价，同类候选中更便宜略加分 |",
        "| 关键确认项 | 35 | 行李退改、酒店停车热水早出门、车辆保险夜路、门票开放范围等 |",
        "| 证据 | 15 | 订单页截图、电话/聊天确认、现场牌示或公告截图 |",
        "| 决策和下一步 | 15 | 已写清保留/淘汰原因和下一步复核动作 |",
        "| 联系/下单入口 | 5 | 可回到原始页面或联系人继续核验 |",
        "",
        "## 使用命令",
        "",
        "```bash",
        "python3 scripts/gannan_candidate_scorecard.py",
        "python3 scripts/gannan_candidate_scorecard.py --strict",
        "python3 scripts/gannan_candidate_scorecard.py --check",
        "```",
        "",
        "真实订单阶段建议同时跑：",
        "",
        "```bash",
        "python3 scripts/check_gannan_order_candidates.py data/gannan_flight_candidates.csv data/gannan_hotel_candidates.csv data/gannan_transport_quotes.csv data/gannan_ticket_candidates.csv",
        "python3 scripts/check_gannan_order_coverage.py --strict",
        "python3 scripts/check_gannan_evidence.py --strict",
        "python3 scripts/run_gannan_checks.py --actual",
        "```",
        "",
    ])
    return "\n".join(lines)


def sample_data() -> dict[str, dict[str, object]]:
    rows = {
        "flight": [
            {
                "option_id": "F1",
                "direction": "outbound",
                "platform": "航司App",
                "carrier_or_railway": "示例航司",
                "flight_or_train_no": "CA0001",
                "origin": "北京",
                "destination": "兰州",
                "depart_date": "2026-09-12",
                "depart_time": "08:00",
                "arrival_date": "2026-09-12",
                "arrival_time": "10:30",
                "final_price_cny": "980",
                "baggage_or_luggage": "含托运",
                "refund_change_policy": "可退改",
                "arrival_transfer": "机场取车",
                "booking_url": "app",
                "evidence_file": "evidence/gannan/flight/F1.png",
                "status": "shortlist",
                "decision": "保留",
                "next_action": "T-7 复核",
                "notes": "",
            }
        ],
        "hotel": [],
        "transport": [],
        "ticket": [],
    }
    data: dict[str, dict[str, object]] = {}
    for kind in ["flight", "hotel", "transport", "ticket"]:
        data[kind] = {
            "path": TEMPLATES[kind]["path"],
            "mode": "sample",
            "rows": rows[kind],
            "scores": score_kind(kind, rows[kind]),
        }
    return data


def self_check(text: str, data: dict[str, dict[str, object]]) -> list[str]:
    errors: list[str] = []
    for phrase in [
        "当前结论",
        "大交通评分",
        "评分口径",
        "python3 scripts/gannan_candidate_scorecard.py --strict",
    ]:
        if phrase not in text:
            errors.append(f"missing phrase: {phrase}")
    flight_scores: list[dict[str, object]] = data["flight"]["scores"]  # type: ignore[assignment]
    if not flight_scores or int(flight_scores[0]["score"]) < 85:
        errors.append("sample flight should be high scoring")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=8, help="max rows per kind in the rendered score table")
    parser.add_argument("--strict", action="store_true", help="fail when active actual candidates are below booking-ready threshold")
    parser.add_argument("--min-score", type=int, default=70, help="minimum score for strict active candidates")
    parser.add_argument("--check", action="store_true", help="run deterministic self-check without writing files")
    args = parser.parse_args()

    if args.check:
        data = sample_data()
        text = render_markdown(data, [], generated_at="2026-09-12 08:00", limit=args.limit)
        errors = self_check(text, data)
        if errors:
            print("Gannan candidate scorecard self-check failed:")
            for error in errors:
                print(f"- {error}")
            return 1
        print("Gannan candidate scorecard self-check passed.")
        return 0

    data, validation_errors = collect_data()
    text = render_markdown(
        data,
        validation_errors,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        limit=max(1, args.limit),
    )

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.write_text(text, encoding="utf-8")
    print(f"Generated {rel(output)}")

    strict_errors: list[str] = []
    if args.strict:
        strict_errors.extend(validation_errors)
        for kind, item in data.items():
            if item["mode"] != "actual":
                continue
            for score in item["scores"]:  # type: ignore[union-attr]
                status = str(score["status"])
                if status in ACTIVE_STATUSES and int(score["score"]) < args.min_score:
                    strict_errors.append(
                        f"{KIND_LABELS[kind]} {score['option_id']}: score {score['score']} below {args.min_score}"
                    )
        if strict_errors:
            print("Gannan candidate scorecard strict check failed:")
            for error in strict_errors:
                print(f"- {error}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
