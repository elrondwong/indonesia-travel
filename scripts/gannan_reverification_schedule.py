#!/usr/bin/env python3
"""Generate a date-driven Gannan re-verification schedule."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import TextIO

from check_gannan_reverification_log import REQUIRED_COLUMNS, VALID_CATEGORIES, VALID_ROUNDS, VALID_STATUSES


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/gannan_order_inputs.json"

ROUND_OFFSETS = {
    "T-14": -14,
    "T-7": -7,
    "T-3": -3,
    "T-1": -1,
}

ROUND_TASKS = {
    "T-14": [
        ("flight", "往返兰州大交通候选池", "航司 App / 12306 / OTA", "收集 2-3 个可比较候选，记录最终含税价、行李和退改。"),
        ("car", "包车/租车报价池", "包车司机 / 租车平台 / 旅行社", "至少回收 3 个报价，写清车型、费用包含项、保险和夜路政策。"),
        ("hotel", "夏河/扎尕那/阿坝县核心住宿", "OTA / 酒店电话 / 民宿微信", "先锁可取消房，要求真实房间、停车、热水/供暖和早出门确认。"),
        ("ticket", "扎尕那/莲宝叶则门票初查", "官方/OTA/酒店前台", "确认可预约日期、票价口径、观光车和开放范围是否有冲突。"),
        ("budget", "总预算和机动金", "预算工作台", "更新大交通、住宿、车辆、门票和 10%-15% 机动预算。"),
    ],
    "T-7": [
        ("flight", "大交通短名单", "航司 App / 12306 / OTA", "确认行李、退改和到达兰州时间；淘汰压缩 D1/D9 的方案。"),
        ("car", "包车/租车定稿前复核", "司机/门店文字确认", "二次确认路线经验、费用包含项、保险、取消规则和不赶夜路。"),
        ("hotel", "全程住宿电话确认", "酒店/民宿前台", "逐晚确认房型、取消规则、停车、热水/供暖、早餐和早出门。"),
        ("ticket", "核心景区预约和开放", "官方/OTA/景区电话/酒店前台", "复核扎尕那、花湖、黄河九曲、莲宝叶则门票和开放范围。"),
        ("insurance", "高原旅行保险", "保险平台/合同", "确认医疗、行李、取消、救援和高原目的地覆盖。"),
    ],
    "T-3": [
        ("route", "天气和道路风险", "中国天气 / 中央气象台 / 高德 / 百度 / 司机", "看降雨、雷暴、施工、落石和封路风险，准备砍点顺序。"),
        ("ticket", "莲宝叶则开放范围", "阿坝州文旅 / 景区 / 阿坝县酒店 / 司机", "确认景区交通、开放区域、最早入园、最晚离园和关闭条件。"),
        ("photo", "日出日落和机位窗口", "光线脚本 / 天气 / 机位索引", "生成光线表，确认扎尕那晨雾、黄河九曲日落、莲宝叶则蓝调可行性。"),
        ("drone", "无人机和现场禁飞风险", "UOM / 景区公告 / 酒店/司机", "确认实名、空域、景区禁飞和现场牌示优先级。"),
        ("health", "高原反应和药品", "个人状态 / 医生建议 / 装备清单", "确认慢病、药品、氧气、保暖、防晒和降低强度方案。"),
    ],
    "T-1": [
        ("route", "D1 出发时间和车程", "司机 / 导航 / 酒店", "确认集合点、油量、早餐、停车、路线和不夜间赶路边界。"),
        ("ticket", "次日景区门票/开放", "官方/OTA/酒店前台/景区电话", "确认拉卜楞寺、甘加或当日景区开放、预约和拍摄限制。"),
        ("photo", "次日主机位和替代拍法", "摄影手册 / 光线表 / 天气", "确定明天最重要的一张照片、硬截止和天气失败替代素材。"),
        ("hotel", "次日入住和早出门", "酒店/民宿", "确认入住、停车、热水/供暖、晚餐、早餐和次日早出门。"),
        ("health", "身体状态和装备", "个人状态 / 装备清单", "确认睡眠、补水、保暖、防雨、充电和存储卡备份。"),
    ],
}

ROUTE_DAYS = [
    ("D1", "兰州 -> 夏河/拉卜楞寺/桑科", "拉卜楞寺转经长廊和桑科草原日落"),
    ("D2", "夏河 -> 甘加/白石崖 -> 合作", "八角城、白石崖和米拉日巴佛阁蓝调"),
    ("D3", "合作 -> 扎尕那", "天黑前到扎尕那，只追一个日落机位"),
    ("D4", "扎尕那全天", "晨雾石城、村寨、仙女滩或安全栈道"),
    ("D5", "扎尕那 -> 郎木寺 -> 花湖 -> 唐克", "黄河九曲第一湾日落"),
    ("D6", "唐克/若尔盖 -> 阿坝县", "休整、补给、顺路草原和莲宝叶则开放初查"),
    ("D7", "莲宝叶则全天", "扎尕尔措、石山湖泊、倒影和蓝调"),
    ("D8", "阿坝县 -> 合作/临夏", "返程分段，不硬冲兰州"),
    ("D9", "合作/临夏 -> 兰州", "按航班/高铁倒推返程，只拍收尾纪实"),
]


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD") from error


def read_start_date_from_input(path: Path) -> datetime | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    value = (((data.get("trip") or {}).get("departure_date")) or "").strip()
    if not value:
        return None
    return parse_date(value)


def date_text(date_value: datetime) -> str:
    return date_value.strftime("%Y-%m-%d")


def next_round_date(round_name: str, start_date: datetime) -> str:
    order = ["T-14", "T-7", "T-3", "T-1"]
    if round_name not in order:
        return ""
    index = order.index(round_name)
    if index == len(order) - 1:
        return date_text(start_date)
    next_round = order[index + 1]
    return date_text(start_date + timedelta(days=ROUND_OFFSETS[next_round]))


def make_row(
    round_name: str,
    check_date: datetime,
    category: str,
    item: str,
    source: str,
    next_action: str,
    owner: str,
    next_check_date: str,
    notes: str = "",
) -> dict[str, str]:
    return {
        "round": round_name,
        "check_date": date_text(check_date),
        "category": category,
        "item": item,
        "source": source,
        "source_url_or_contact": "",
        "quoted_price_cny": "",
        "evidence_file": "",
        "status": "n/a",
        "decision": "待复核",
        "next_action": next_action,
        "owner": owner,
        "next_check_date": next_check_date,
        "notes": notes,
    }


def build_schedule(start_date: datetime, owner: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for round_name, offset in ROUND_OFFSETS.items():
        check_date = start_date + timedelta(days=offset)
        for category, item, source, next_action in ROUND_TASKS[round_name]:
            rows.append(make_row(
                round_name,
                check_date,
                category,
                item,
                source,
                next_action,
                owner,
                next_round_date(round_name, start_date),
            ))

    for index, (day_label, route, photo_goal) in enumerate(ROUTE_DAYS):
        check_date = start_date + timedelta(days=index)
        next_date = date_text(check_date + timedelta(days=1)) if index < len(ROUTE_DAYS) - 1 else ""
        rows.extend([
            make_row("D-day", check_date, "route", f"{day_label} 路线/路况现场复核", "司机 / 高德 / 百度 / 酒店前台", f"确认 {route} 的实际路况、停车、油量和最晚撤离时间。", owner, next_date, route),
            make_row("D-day", check_date, "ticket", f"{day_label} 门票/开放现场复核", "景区公告 / 售票处 / 酒店前台", "确认门票、预约、观光车、禁入/禁飞牌示和最晚离园。", owner, next_date, route),
            make_row("D-day", check_date, "photo", f"{day_label} 主机位和出片复核", "摄影手册 / 光线表 / 天气", f"优先保：{photo_goal}。天气失败时按替代拍法补素材。", owner, next_date, photo_goal),
            make_row("D-day", check_date, "health", f"{day_label} 身体状态和强度复核", "个人状态 / 司机 / 酒店", "头痛、恶心、胸闷或走路不稳时立即降强度，不追机位。", owner, next_date, route),
        ])

    return rows


def render_markdown(rows: list[dict[str, str]], start_date: datetime) -> str:
    lines = [
        "# 甘南 + 莲宝叶则复核日程",
        "",
        f"路线开始日期：{date_text(start_date)}",
        "",
        "这张表可以直接指导 T-14、T-7、T-3、T-1 和每天早上的反复核验。CSV 输出可作为 `data/gannan_reverification_log.csv` 的初始草稿，再逐行补证据、价格、决策和下一次复核日期。",
        "",
        "| 复核日期 | 轮次 | 分类 | 项目 | 来源 | 下一步 |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['check_date']} | {row['round']} | {row['category']} | {row['item']} | {row['source']} | {row['next_action']} |"
        )
    lines.extend([
        "",
        "## 使用命令",
        "",
        "```bash",
        "python3 scripts/gannan_reverification_schedule.py --route-start-date YYYY-MM-DD",
        "python3 scripts/gannan_reverification_schedule.py --route-start-date YYYY-MM-DD --format csv --output data/gannan_reverification_log.csv",
        "python3 scripts/check_gannan_reverification_log.py data/gannan_reverification_log.csv",
        "```",
        "",
    ])
    return "\n".join(lines)


def write_csv(rows: list[dict[str, str]], handle: TextIO) -> None:
    writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for index, row in enumerate(rows, start=2):
        if list(row.keys()) != REQUIRED_COLUMNS:
            errors.append(f"row {index}: columns do not match re-verification log template")
        if row["round"] not in VALID_ROUNDS:
            errors.append(f"row {index}: invalid round {row['round']}")
        if row["category"] not in VALID_CATEGORIES:
            errors.append(f"row {index}: invalid category {row['category']}")
        if row["status"] not in VALID_STATUSES:
            errors.append(f"row {index}: invalid status {row['status']}")
        for field in ["round", "check_date", "category", "item", "source", "status", "decision", "owner"]:
            if not row[field].strip():
                errors.append(f"row {index}: missing required field {field}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route-start-date", type=parse_date, help="D1 date for the Lanzhou-to-Gannan route, in YYYY-MM-DD")
    parser.add_argument("--from-input", type=Path, default=DEFAULT_INPUT, help="read trip.departure_date from this JSON when route-start-date is omitted")
    parser.add_argument("--owner", default="待分配", help="owner value written to generated CSV rows")
    parser.add_argument("--format", choices=["markdown", "csv"], default="markdown")
    parser.add_argument("--output", type=Path, help="write output to this file instead of stdout")
    parser.add_argument("--check", action="store_true", help="run a deterministic self-check with a sample date")
    args = parser.parse_args()

    start_date = args.route_start_date
    if args.check:
        start_date = parse_date("2026-09-12")
    elif start_date is None:
        input_path = args.from_input if args.from_input.is_absolute() else ROOT / args.from_input
        start_date = read_start_date_from_input(input_path)
        if start_date is None:
            print("route start date is required; pass --route-start-date YYYY-MM-DD or fill data/gannan_order_inputs.json", file=sys.stderr)
            return 2

    rows = build_schedule(start_date, args.owner)
    errors = validate_rows(rows)
    if errors:
        print("Gannan re-verification schedule failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.check:
        print("Gannan re-verification schedule passed.")
        print(f"Generated {len(rows)} schedule rows.")
        return 0

    if args.format == "csv":
        if args.output:
            output_path = args.output if args.output.is_absolute() else ROOT / args.output
            with output_path.open("w", newline="", encoding="utf-8") as handle:
                write_csv(rows, handle)
            print(f"Generated {rel(output_path)}")
        else:
            write_csv(rows, sys.stdout)
    else:
        text = render_markdown(rows, start_date)
        if args.output:
            output_path = args.output if args.output.is_absolute() else ROOT / args.output
            output_path.write_text(text, encoding="utf-8")
            print(f"Generated {rel(output_path)}")
        else:
            print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
