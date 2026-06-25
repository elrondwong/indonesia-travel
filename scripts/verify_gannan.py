#!/usr/bin/env python3
"""Verify the Gannan travel guide package.

Checks are intentionally local and deterministic:
- required Markdown, HTML, style, and route files exist
- key sections/phrases are present in the core documents
- local href/src targets in Gannan pages resolve to existing files
- Indonesia pages expose the Gannan dashboard entry point
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "data/gannan_order_inputs.template.json",
    "data/gannan_light_points.csv",
    "data/gannan_photo_spots.csv",
    "data/gannan_flight_candidates.template.csv",
    "data/gannan_hotel_candidates.template.csv",
    "data/gannan_transport_quotes.template.csv",
    "data/gannan_ticket_candidates.template.csv",
    "data/gannan_source_ledger.csv",
    "data/gannan_reverification_log.template.csv",
    "evidence/gannan/README.md",
    "gannan-dashboard.html",
    "gannan-input-wizard.html",
    "gannan-mobile-pack.html",
    "gannan.html",
    "gannan-verification.html",
    "gannan-source-ledger.html",
    "gannan-source-health.html",
    "gannan-source-fallbacks.html",
    "gannan-evidence-archive.html",
    "gannan-reverification-sop.html",
    "gannan-reverification-schedule.html",
    "gannan-reverification-calendar.html",
    "gannan-reverification-diff.html",
    "gannan-contingency-plan.html",
    "gannan-photo-handbook.html",
    "gannan-light-astro.html",
    "gannan-shot-list.html",
    "gannan-photo-readiness.html",
    "gannan-daily-cards.html",
    "gannan-photo-map.html",
    "gannan-photo-spot-check.html",
    "gannan-china-map-pack.html",
    "gannan-gear-checklist.html",
    "gannan-communication-checklist.html",
    "gannan-quote-templates.html",
    "gannan-order-workbench.html",
    "gannan-order-handoff.html",
    "gannan-order-start.html",
    "gannan-order-candidates.html",
    "gannan-candidate-scorecard.html",
    "gannan-order-coverage.html",
    "gannan-order-report.html",
    "gannan-booking-gate.html",
    "gannan-goal-audit.html",
    "gannan-final-audit.html",
    "gannan-page.css",
    "gannan-nav.html",
    "gannan-after-body.html",
    "gannan-app.js",
    "scripts/build_gannan.py",
    "scripts/run_gannan_checks.py",
    "scripts/gannan_light_windows.py",
    "scripts/check_gannan_photo_spots.py",
    "scripts/gannan_photo_readiness_gate.py",
    "scripts/check_gannan_inputs.py",
    "scripts/check_gannan_order_candidates.py",
    "scripts/gannan_candidate_scorecard.py",
    "scripts/gannan_order_handoff.py",
    "scripts/gannan_order_start.py",
    "scripts/check_gannan_order_coverage.py",
    "scripts/gannan_order_report.py",
    "scripts/gannan_booking_gate.py",
    "scripts/audit_gannan_goal_completion.py",
    "scripts/check_gannan_evidence.py",
    "scripts/gannan_reverification_schedule.py",
    "scripts/gannan_reverification_calendar.py",
    "scripts/gannan_reverification_diff.py",
    "scripts/check_gannan_sources.py",
    "scripts/gannan_source_health_report.py",
    "scripts/gannan_source_fallbacks.py",
    "scripts/check_gannan_reverification_log.py",
    "assets/route/gannan_route_overview.svg",
    "甘南莲宝叶则_完整攻略.md",
    "甘南莲宝叶则_核验记录.md",
    "甘南莲宝叶则_来源台账.md",
    "甘南莲宝叶则_来源健康报告.md",
    "甘南莲宝叶则_来源故障处理.md",
    "甘南莲宝叶则_证据归档规范.md",
    "甘南莲宝叶则_反复核验SOP.md",
    "甘南莲宝叶则_复核日程生成.md",
    "甘南莲宝叶则_复核日历导出.md",
    "甘南莲宝叶则_复核差异追踪.md",
    "甘南莲宝叶则_高原天气应急预案.md",
    "甘南莲宝叶则_摄影手册.md",
    "甘南莲宝叶则_光线天象规划.md",
    "甘南莲宝叶则_大片交付清单.md",
    "甘南莲宝叶则_出片准备闸门.md",
    "甘南莲宝叶则_每日执行卡.md",
    "甘南莲宝叶则_机位地图索引.md",
    "甘南莲宝叶则_机位核验表.md",
    "甘南莲宝叶则_国内地图导航包.md",
    "甘南莲宝叶则_装备Checklist.md",
    "甘南莲宝叶则_沟通Checklist.md",
    "甘南莲宝叶则_询价消息包.md",
    "甘南莲宝叶则_预算与订单核验表.md",
    "甘南莲宝叶则_订单核验接力包.md",
    "甘南莲宝叶则_订单启动工作流.md",
    "甘南莲宝叶则_订单候选模板.md",
    "甘南莲宝叶则_候选评分卡.md",
    "甘南莲宝叶则_订单覆盖率闸门.md",
    "甘南莲宝叶则_订单复核报告.md",
    "甘南莲宝叶则_下单决策闸门.md",
    "甘南莲宝叶则_目标完成审计.md",
    "甘南莲宝叶则_最终核验矩阵.md",
]

KEY_PHRASES = {
    "甘南莲宝叶则_完整攻略.md": [
        "9 天 8 晚推荐路线",
        "独立文档入口",
        "莲宝叶则全天",
        "扎尕那全天",
        "不赶夜路",
    ],
    "甘南莲宝叶则_核验记录.md": [
        "门票和开放信息复核表",
        "动态项冲突处理",
        "扎尕那门票",
        "机票和到达兰州核验",
        "酒店核验",
    ],
    "甘南莲宝叶则_来源台账.md": [
        "来源 CSV",
        "分类口径",
        "必查优先级",
        "订单级使用边界",
        "python3 scripts/check_gannan_sources.py",
    ],
    "甘南莲宝叶则_来源健康报告.md": [
        "健康摘要",
        "分类覆盖",
        "复核轮次覆盖",
        "A 级必查来源",
        "python3 scripts/gannan_source_health_report.py --online",
    ],
    "甘南莲宝叶则_来源故障处理.md": [
        "下单阻塞口径",
        "故障处理矩阵",
        "现场处理顺序",
        "python3 scripts/gannan_source_fallbacks.py --online",
    ],
    "甘南莲宝叶则_证据归档规范.md": [
        "先看结论",
        "目录和命名",
        "CSV 怎么填",
        "严格检查规则",
        "python3 scripts/check_gannan_evidence.py",
    ],
    "甘南莲宝叶则_反复核验SOP.md": [
        "复核日志",
        "复核时间轴",
        "分项复核清单",
        "改线触发器",
        "最终下单口径",
    ],
    "甘南莲宝叶则_复核日程生成.md": [
        "先看结论",
        "日期口径",
        "生成内容",
        "CSV 怎么用",
        "python3 scripts/gannan_reverification_schedule.py",
    ],
    "甘南莲宝叶则_复核日历导出.md": [
        "先看结论",
        "事件分布",
        "导出命令",
        "python3 scripts/gannan_reverification_calendar.py --route-start-date",
        "gannan_booking_gate.py --strict",
    ],
    "甘南莲宝叶则_复核差异追踪.md": [
        "先看结论",
        "会抓什么",
        "日志分组口径",
        "真实订单阶段",
        "python3 scripts/gannan_reverification_diff.py",
    ],
    "甘南莲宝叶则_高原天气应急预案.md": [
        "三条红线",
        "高原反应执行梯度",
        "天气和路况红旗",
        "景区闭园 / 开放范围变化",
        "CDC Travelers' Health",
    ],
    "甘南莲宝叶则_摄影手册.md": [
        "大片优先级",
        "扎尕那晨雾石城",
        "莲宝叶则石山湖泊",
        "天气失败时怎么拍",
    ],
    "甘南莲宝叶则_光线天象规划.md": [
        "先看结论",
        "离线生成光线表",
        "每日光线策略",
        "星空和银河判断",
        "python3 scripts/gannan_light_windows.py",
    ],
    "甘南莲宝叶则_大片交付清单.md": [
        "最终交付目标",
        "封面级主图池",
        "每日交付清单",
        "短视频镜头清单",
        "每晚交付复盘",
    ],
    "甘南莲宝叶则_出片准备闸门.md": [
        "当前结论",
        "闸门总表",
        "策略级可拍",
        "真实出发前仍需复核",
        "python3 scripts/gannan_photo_readiness_gate.py --strict",
    ],
    "甘南莲宝叶则_机位核验表.md": [
        "先看结论",
        "状态口径",
        "核心覆盖",
        "data/gannan_photo_spots.csv",
        "python3 scripts/check_gannan_photo_spots.py",
    ],
    "甘南莲宝叶则_每日执行卡.md": [
        "全程三条铁律",
        "扎尕那全天",
        "莲宝叶则全天",
        "每晚 5 分钟复盘",
    ],
    "甘南莲宝叶则_国内地图导航包.md": [
        "每日导航顺序",
        "核心点位搜索入口",
        "高德",
        "百度",
        "发给司机的定位确认话术",
    ],
    "甘南莲宝叶则_预算与订单核验表.md": [
        "外部价格锚点",
        "预算警戒线",
        "包车 / 租车询价表",
        "门票下单表",
        "四次复核记录",
    ],
    "甘南莲宝叶则_订单核验接力包.md": [
        "当前接力状态",
        "还需要用户给我的信息",
        "真实候选最低覆盖",
        "推荐命令顺序",
        "python3 scripts/run_gannan_checks.py --online-sources --actual",
    ],
    "甘南莲宝叶则_订单启动工作流.md": [
        "当前启动状态",
        "必填信息缺口",
        "复核日程预览",
        "python3 scripts/gannan_order_start.py --init-files",
        "python3 scripts/run_gannan_checks.py --actual",
    ],
    "甘南莲宝叶则_订单候选模板.md": [
        "大交通候选表",
        "酒店候选表",
        "包车 / 租车候选表",
        "门票候选表",
        "python3 scripts/check_gannan_order_candidates.py",
    ],
    "甘南莲宝叶则_候选评分卡.md": [
        "当前结论",
        "大交通评分",
        "评分口径",
        "python3 scripts/gannan_candidate_scorecard.py --strict",
    ],
    "甘南莲宝叶则_订单覆盖率闸门.md": [
        "先看结论",
        "覆盖规则",
        "状态口径",
        "什么时候会失败",
        "python3 scripts/check_gannan_order_coverage.py",
    ],
    "甘南莲宝叶则_订单复核报告.md": [
        "当前结论",
        "出行信息状态",
        "候选数据概览",
        "红旗清单",
        "python3 scripts/gannan_order_report.py",
    ],
    "甘南莲宝叶则_下单决策闸门.md": [
        "当前结论",
        "分项下单候选",
        "下一步动作",
        "python3 scripts/gannan_booking_gate.py --strict",
    ],
    "甘南莲宝叶则_目标完成审计.md": [
        "总体结论",
        "严格完成口径",
        "机票/酒店/车辆/门票订单级验证",
        "python3 scripts/audit_gannan_goal_completion.py --strict",
    ],
    "甘南莲宝叶则_询价消息包.md": [
        "包车 / 司导询价",
        "酒店 / 民宿询价",
        "景区 / 前台开放询问",
        "报价回收表",
        "红旗和淘汰规则",
    ],
    "甘南莲宝叶则_最终核验矩阵.md": [
        "完成度总表",
        "不能提前写死的项目",
        "出行信息收集表",
        "当前结论",
    ],
    "gannan-dashboard.html": [
        "甘南 + 莲宝叶则摄影攻略总控台",
        "订单级核验还缺什么",
        "打开移动速查",
        "打开填写器",
        "打开国内导航",
        "打开光线规划",
        "打开出片闸门",
        "打开来源台账",
        "打开来源健康",
        "打开故障处理",
        "打开证据归档",
        "打开出片清单",
        "打开机位核验",
        "打开询价消息",
        "打开复核 SOP",
        "打开复核日程",
        "打开复核日历",
        "打开差异追踪",
        "打开应急预案",
        "打开预算工作台",
        "打开订单接力",
        "打开订单启动",
        "打开候选模板",
        "打开候选评分",
        "打开覆盖闸门",
        "打开复核报告",
        "打开下单闸门",
        "打开目标审计",
        "打开最终核验",
    ],
    "README.md": [
        "兰州出发甘南 + 莲宝叶则",
        "gannan-dashboard.html",
        "gannan-input-wizard.html",
        "scripts/run_gannan_checks.py",
        "维护命令",
    ],
    "gannan-input-wizard.html": [
        "甘南 + 莲宝叶则订单输入填写器",
        "生成 JSON",
        "订单级核验状态",
        "trip.origin_city",
        "preferences.camera_gear",
    ],
    "gannan-mobile-pack.html": [
        "甘南 + 莲宝叶则移动端速查",
        "每日执行",
        "应急红线",
        "每晚 5 分钟",
        "离线入口",
    ],
    "gannan.html": [
        "gannan-topbar",
        "gannan-dashboard.html",
        "gannan-app.js",
    ],
    "gannan-photo-handbook.html": [
        "gannan-topbar",
        "gannan-dashboard.html",
        "gannan-app.js",
    ],
    "gannan-gear-checklist.html": [
        "gannan-topbar",
        "gannan-app.js",
        "checkbox",
    ],
}

GANNAN_PAGES = [
    "gannan-dashboard.html",
    "gannan-input-wizard.html",
    "gannan-mobile-pack.html",
    "gannan.html",
    "gannan-verification.html",
    "gannan-source-ledger.html",
    "gannan-source-health.html",
    "gannan-source-fallbacks.html",
    "gannan-evidence-archive.html",
    "gannan-reverification-sop.html",
    "gannan-reverification-schedule.html",
    "gannan-reverification-calendar.html",
    "gannan-reverification-diff.html",
    "gannan-contingency-plan.html",
    "gannan-photo-handbook.html",
    "gannan-light-astro.html",
    "gannan-shot-list.html",
    "gannan-photo-readiness.html",
    "gannan-daily-cards.html",
    "gannan-photo-map.html",
    "gannan-photo-spot-check.html",
    "gannan-china-map-pack.html",
    "gannan-gear-checklist.html",
    "gannan-communication-checklist.html",
    "gannan-quote-templates.html",
    "gannan-order-workbench.html",
    "gannan-order-handoff.html",
    "gannan-order-start.html",
    "gannan-order-candidates.html",
    "gannan-candidate-scorecard.html",
    "gannan-order-coverage.html",
    "gannan-order-report.html",
    "gannan-booking-gate.html",
    "gannan-goal-audit.html",
    "gannan-final-audit.html",
    "甘南莲宝叶则_完整攻略.md",
    "甘南莲宝叶则_核验记录.md",
    "甘南莲宝叶则_来源台账.md",
    "甘南莲宝叶则_来源健康报告.md",
    "甘南莲宝叶则_来源故障处理.md",
    "甘南莲宝叶则_证据归档规范.md",
    "甘南莲宝叶则_反复核验SOP.md",
    "甘南莲宝叶则_复核日程生成.md",
    "甘南莲宝叶则_复核日历导出.md",
    "甘南莲宝叶则_复核差异追踪.md",
    "甘南莲宝叶则_高原天气应急预案.md",
    "甘南莲宝叶则_摄影手册.md",
    "甘南莲宝叶则_光线天象规划.md",
    "甘南莲宝叶则_大片交付清单.md",
    "甘南莲宝叶则_出片准备闸门.md",
    "甘南莲宝叶则_每日执行卡.md",
    "甘南莲宝叶则_机位地图索引.md",
    "甘南莲宝叶则_机位核验表.md",
    "甘南莲宝叶则_国内地图导航包.md",
    "甘南莲宝叶则_装备Checklist.md",
    "甘南莲宝叶则_沟通Checklist.md",
    "甘南莲宝叶则_询价消息包.md",
    "甘南莲宝叶则_预算与订单核验表.md",
    "甘南莲宝叶则_订单核验接力包.md",
    "甘南莲宝叶则_订单启动工作流.md",
    "甘南莲宝叶则_订单候选模板.md",
    "甘南莲宝叶则_候选评分卡.md",
    "甘南莲宝叶则_订单覆盖率闸门.md",
    "甘南莲宝叶则_订单复核报告.md",
    "甘南莲宝叶则_下单决策闸门.md",
    "甘南莲宝叶则_目标完成审计.md",
    "甘南莲宝叶则_最终核验矩阵.md",
]

INDONESIA_ENTRY_PAGES = [
    "index.html",
    "verification.html",
    "photo-handbook.html",
    "gear-checklist.html",
    "guide-checklist.html",
    "astro.html",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def is_external(target: str) -> bool:
    parsed = urlparse(target)
    return bool(parsed.scheme) or target.startswith("#") or target.startswith("mailto:")


def strip_fragment_and_query(target: str) -> str:
    parsed = urlparse(target)
    path = unquote(parsed.path)
    return path


def collect_local_targets(text: str, suffix: str) -> list[str]:
    targets: list[str] = []
    if suffix == ".html":
        patterns = [
            r'href=["\']([^"\']+)["\']',
            r'src=["\']([^"\']+)["\']',
        ]
    else:
        patterns = [
            r'!?\[[^\]]*\]\(([^)]+)\)',
        ]

    for pattern in patterns:
        for raw in re.findall(pattern, text):
            target = raw.strip()
            if not target or is_external(target):
                continue
            local = strip_fragment_and_query(target)
            if not local:
                continue
            targets.append(local)
    return targets


def main() -> int:
    errors: list[str] = []

    for rel in REQUIRED_FILES:
        path = ROOT / rel
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"missing or empty required file: {rel}")

    for rel, phrases in KEY_PHRASES.items():
        path = ROOT / rel
        if not path.exists():
            continue
        text = read_text(path)
        for phrase in phrases:
            if phrase not in text:
                errors.append(f"missing phrase in {rel}: {phrase}")

    for rel in INDONESIA_ENTRY_PAGES:
        path = ROOT / rel
        if not path.exists():
            errors.append(f"missing navigation page: {rel}")
            continue
        text = read_text(path)
        if 'href="gannan-dashboard.html">甘南攻略' not in text:
            errors.append(f"missing Gannan dashboard link in {rel}")

    for rel in GANNAN_PAGES:
        path = ROOT / rel
        if not path.exists():
            continue
        text = read_text(path)
        suffix = path.suffix.lower()
        for target in collect_local_targets(text, suffix):
            target_path = (path.parent / target).resolve()
            try:
                target_path.relative_to(ROOT)
            except ValueError:
                errors.append(f"link escapes repository in {rel}: {target}")
                continue
            if not target_path.exists():
                errors.append(f"broken local link in {rel}: {target}")

    if errors:
        print("Gannan guide verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Gannan guide verification passed.")
    print(f"Checked {len(REQUIRED_FILES)} required files, {len(GANNAN_PAGES)} guide pages, and {len(INDONESIA_ENTRY_PAGES)} site entry pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
