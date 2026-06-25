#!/usr/bin/env python3
"""Build all Pandoc-generated Gannan guide pages."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PAGES = [
    ("甘南莲宝叶则_完整攻略.md", "gannan.html", "兰州出发甘南 + 莲宝叶则摄影攻略"),
    ("甘南莲宝叶则_核验记录.md", "gannan-verification.html", "甘南 + 莲宝叶则核验记录"),
    ("甘南莲宝叶则_来源台账.md", "gannan-source-ledger.html", "甘南 + 莲宝叶则来源台账"),
    ("甘南莲宝叶则_来源健康报告.md", "gannan-source-health.html", "甘南 + 莲宝叶则来源健康报告"),
    ("甘南莲宝叶则_来源故障处理.md", "gannan-source-fallbacks.html", "甘南 + 莲宝叶则来源故障处理"),
    ("甘南莲宝叶则_证据归档规范.md", "gannan-evidence-archive.html", "甘南 + 莲宝叶则证据归档规范"),
    ("甘南莲宝叶则_反复核验SOP.md", "gannan-reverification-sop.html", "甘南 + 莲宝叶则反复核验 SOP"),
    ("甘南莲宝叶则_复核日程生成.md", "gannan-reverification-schedule.html", "甘南 + 莲宝叶则复核日程生成"),
    ("甘南莲宝叶则_复核日历导出.md", "gannan-reverification-calendar.html", "甘南 + 莲宝叶则复核日历导出"),
    ("甘南莲宝叶则_复核差异追踪.md", "gannan-reverification-diff.html", "甘南 + 莲宝叶则复核差异追踪"),
    ("甘南莲宝叶则_高原天气应急预案.md", "gannan-contingency-plan.html", "甘南 + 莲宝叶则高原天气应急预案"),
    ("甘南莲宝叶则_摄影手册.md", "gannan-photo-handbook.html", "甘南 + 莲宝叶则摄影手册"),
    ("甘南莲宝叶则_光线天象规划.md", "gannan-light-astro.html", "甘南 + 莲宝叶则光线天象规划"),
    ("甘南莲宝叶则_大片交付清单.md", "gannan-shot-list.html", "甘南 + 莲宝叶则大片交付清单"),
    ("甘南莲宝叶则_出片准备闸门.md", "gannan-photo-readiness.html", "甘南 + 莲宝叶则出片准备闸门"),
    ("甘南莲宝叶则_每日执行卡.md", "gannan-daily-cards.html", "甘南 + 莲宝叶则每日执行卡"),
    ("甘南莲宝叶则_机位地图索引.md", "gannan-photo-map.html", "甘南 + 莲宝叶则机位地图索引"),
    ("甘南莲宝叶则_机位核验表.md", "gannan-photo-spot-check.html", "甘南 + 莲宝叶则机位核验表"),
    ("甘南莲宝叶则_国内地图导航包.md", "gannan-china-map-pack.html", "甘南 + 莲宝叶则国内地图导航包"),
    ("甘南莲宝叶则_装备Checklist.md", "gannan-gear-checklist.html", "甘南 + 莲宝叶则装备 Checklist"),
    ("甘南莲宝叶则_沟通Checklist.md", "gannan-communication-checklist.html", "甘南 + 莲宝叶则沟通 Checklist"),
    ("甘南莲宝叶则_询价消息包.md", "gannan-quote-templates.html", "甘南 + 莲宝叶则询价消息包"),
    ("甘南莲宝叶则_预算与订单核验表.md", "gannan-order-workbench.html", "甘南 + 莲宝叶则预算与订单核验表"),
    ("甘南莲宝叶则_订单核验接力包.md", "gannan-order-handoff.html", "甘南 + 莲宝叶则订单核验接力包"),
    ("甘南莲宝叶则_订单启动工作流.md", "gannan-order-start.html", "甘南 + 莲宝叶则订单启动工作流"),
    ("甘南莲宝叶则_订单候选模板.md", "gannan-order-candidates.html", "甘南 + 莲宝叶则订单候选模板"),
    ("甘南莲宝叶则_候选评分卡.md", "gannan-candidate-scorecard.html", "甘南 + 莲宝叶则候选评分卡"),
    ("甘南莲宝叶则_订单覆盖率闸门.md", "gannan-order-coverage.html", "甘南 + 莲宝叶则订单覆盖率闸门"),
    ("甘南莲宝叶则_订单复核报告.md", "gannan-order-report.html", "甘南 + 莲宝叶则订单复核报告"),
    ("甘南莲宝叶则_下单决策闸门.md", "gannan-booking-gate.html", "甘南 + 莲宝叶则下单决策闸门"),
    ("甘南莲宝叶则_目标完成审计.md", "gannan-goal-audit.html", "甘南 + 莲宝叶则目标完成审计"),
    ("甘南莲宝叶则_最终核验矩阵.md", "gannan-final-audit.html", "甘南 + 莲宝叶则最终核验矩阵"),
]


def build_page(source: str, output: str, title: str) -> None:
    cmd = [
        "pandoc",
        source,
        "--from=gfm+task_lists",
        "--standalone",
        "--css=styles.css",
        "--css=gannan-page.css",
        "--include-before-body=gannan-nav.html",
        "--include-after-body=gannan-after-body.html",
        "--metadata",
        f"pagetitle={title}",
        "--metadata",
        f"title={title}",
        "-o",
        output,
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def selected_pages(only: list[str]) -> list[tuple[str, str, str]]:
    if not only:
        return PAGES
    wanted = set(only)
    pages = [
        page for page in PAGES
        if page[0] in wanted or page[1] in wanted
    ]
    missing = wanted - {source for source, _, _ in pages} - {output for _, output, _ in pages}
    if missing:
        raise ValueError("unknown page(s): " + ", ".join(sorted(missing)))
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", default=[], help="build only matching source Markdown or output HTML files")
    args = parser.parse_args()

    try:
        pages = selected_pages(args.only)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    missing = [source for source, _, _ in pages if not (ROOT / source).exists()]
    if missing:
        for source in missing:
            print(f"missing source: {source}", file=sys.stderr)
        return 1

    for source, output, title in pages:
        build_page(source, output, title)
        print(f"built {output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as error:
        print(f"build failed: {error}", file=sys.stderr)
        sys.exit(error.returncode)
