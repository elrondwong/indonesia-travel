# 旅行摄影攻略工作区

这个仓库目前包含两套摄影攻略：

- 印尼东爪哇 + 佩尼达：原始攻略站，入口是 [index.html](index.html)。
- 兰州出发甘南 + 莲宝叶则：新增完整攻略包，入口是 [gannan-dashboard.html](gannan-dashboard.html)。

## 甘南攻略怎么用

先打开 [gannan-dashboard.html](gannan-dashboard.html)。它是总控台，集中链接了：

| 页面 | 用途 |
|---|---|
| [gannan.html](gannan.html) | 主攻略：路线、每天时间线、住宿区域、车程边界 |
| [gannan-daily-cards.html](gannan-daily-cards.html) | 每日手机执行卡：当天目标、硬截止、主机位、砍点顺序 |
| [gannan-mobile-pack.html](gannan-mobile-pack.html) | 移动端离线速查包：每日硬截止、应急红线和常用话术 |
| [gannan-photo-handbook.html](gannan-photo-handbook.html) | 摄影手册：机位、光线、焦段、参数、放弃条件 |
| [gannan-light-astro.html](gannan-light-astro.html) | 光线天象规划：日出日落、蓝调、星空和离线光线表 |
| [gannan-shot-list.html](gannan-shot-list.html) | 大片交付清单：封面图、故事图、短视频和失败天气替代素材 |
| [gannan-photo-readiness.html](gannan-photo-readiness.html) | 出片准备闸门：合并机位、光线、每日卡、装备、天气开放和证据 |
| [gannan-photo-map.html](gannan-photo-map.html) | 机位地图索引：地图链接、搜索关键词、黄金时间 |
| [gannan-photo-spot-check.html](gannan-photo-spot-check.html) | 机位核验表：S/A/B 级机位、地图关键词、黄金时间和放弃条件 |
| [gannan-china-map-pack.html](gannan-china-map-pack.html) | 国内地图导航包：高德/百度搜索入口和司机定位确认 |
| [gannan-source-ledger.html](gannan-source-ledger.html) | 来源台账：机票/酒店/门票/地图/天气/无人机复核入口 |
| [gannan-source-health.html](gannan-source-health.html) | 来源健康报告：分类覆盖、A 级来源、复核轮次和联网探测提醒 |
| [gannan-source-fallbacks.html](gannan-source-fallbacks.html) | 来源故障处理：外链失败、403、超时时的备选入口和阻塞口径 |
| [gannan-evidence-archive.html](gannan-evidence-archive.html) | 证据归档规范：订单截图、聊天确认和现场牌示的保存规则 |
| [gannan-quote-templates.html](gannan-quote-templates.html) | 询价消息包：包车/租车/酒店/景区可复制模板 |
| [gannan-input-wizard.html](gannan-input-wizard.html) | 出行信息填写器：生成订单级核验 JSON |
| [gannan-order-workbench.html](gannan-order-workbench.html) | 预算与订单核验：机票/酒店/包车/门票候选表 |
| [gannan-order-handoff.html](gannan-order-handoff.html) | 订单核验接力包：真实订单阶段下一步、最低覆盖和命令顺序 |
| [gannan-order-start.html](gannan-order-start.html) | 订单启动工作流：初始化真实候选表、证据目录和复核日志 |
| [gannan-order-candidates.html](gannan-order-candidates.html) | 订单候选模板：机票/酒店/车辆/门票 CSV 和自动漏项检查 |
| [gannan-candidate-scorecard.html](gannan-candidate-scorecard.html) | 候选评分卡：按证据、退改、价格和关键确认项排序候选 |
| [gannan-order-coverage.html](gannan-order-coverage.html) | 订单覆盖率闸门：检查去返程、D1-D8 酒店、车辆和核心门票是否覆盖 |
| [gannan-order-report.html](gannan-order-report.html) | 订单复核报告：汇总候选 CSV、红旗、日志和下一步动作 |
| [gannan-booking-gate.html](gannan-booking-gate.html) | 下单决策闸门：合并评分、覆盖、证据、日志和来源故障判断能否下单 |
| [gannan-goal-audit.html](gannan-goal-audit.html) | 目标完成审计：从原始目标反查完成证据和真实订单缺口 |
| [gannan-reverification-sop.html](gannan-reverification-sop.html) | 反复核验 SOP：T-14/T-7/T-3/T-1 日志和改线规则 |
| [gannan-reverification-schedule.html](gannan-reverification-schedule.html) | 复核日程生成：按兰州出发日期生成每轮复核任务 |
| [gannan-reverification-calendar.html](gannan-reverification-calendar.html) | 复核日历导出：把复核任务导出为可导入日历的 ICS |
| [gannan-reverification-diff.html](gannan-reverification-diff.html) | 复核差异追踪：比较多轮日志里的涨价、状态变坏和 blocked/fail |
| [gannan-contingency-plan.html](gannan-contingency-plan.html) | 高原天气应急预案：高反、雷雨、封路、闭园和改线红线 |
| [gannan-gear-checklist.html](gannan-gear-checklist.html) | 装备 Checklist |
| [gannan-communication-checklist.html](gannan-communication-checklist.html) | 司机、酒店、景区沟通话术 |
| [gannan-verification.html](gannan-verification.html) | 来源与动态项核验记录 |
| [gannan-final-audit.html](gannan-final-audit.html) | 最终核验矩阵 |

## 当前状态

甘南攻略已经完成策略级和执行级交付：路线、摄影、机位、装备、沟通、门票核验框架、预算工作台、路线图和网页入口都已生成。

仍需实际出行信息后才能完成订单级核验：

```text
出发城市：
出发日期：
返程日期：
人数：
房间数 / 房型：
酒店预算：
是否自驾或包车：
是否带无人机：
是否有高原反应史：
```

## 维护命令

修改甘南 Markdown 后，推荐直接跑总核验：

```bash
python3 scripts/run_gannan_checks.py
```

如需同时检查外部来源入口可达性：

```bash
python3 scripts/run_gannan_checks.py --online-sources
```

实际订单信息、候选表和复核日志都填好后：

```bash
python3 scripts/run_gannan_checks.py --actual
```

也可以分开运行 HTML 构建和完整性检查：

```bash
python3 scripts/build_gannan.py
python3 scripts/verify_gannan.py
```

当前核验通过口径：

```text
Gannan guide verification passed.
```

## 订单级核验输入

可以先用网页填写器生成 JSON：[gannan-input-wizard.html](gannan-input-wizard.html)。

先复制并填写模板：

```bash
cp data/gannan_order_inputs.template.json data/gannan_order_inputs.json
```

检查信息是否足够开始比价：

```bash
python3 scripts/check_gannan_inputs.py data/gannan_order_inputs.json
```

生成订单启动工作流报告：

```bash
python3 scripts/gannan_order_handoff.py
python3 scripts/gannan_order_start.py
```

确认进入真实订单阶段后，初始化工作文件和证据目录：

```bash
python3 scripts/gannan_order_start.py --init-files --route-start-date YYYY-MM-DD
```

## 订单候选表

复制机票、酒店、车辆和门票候选模板：

```bash
cp data/gannan_flight_candidates.template.csv data/gannan_flight_candidates.csv
cp data/gannan_hotel_candidates.template.csv data/gannan_hotel_candidates.csv
cp data/gannan_transport_quotes.template.csv data/gannan_transport_quotes.csv
cp data/gannan_ticket_candidates.template.csv data/gannan_ticket_candidates.csv
```

检查候选表是否漏掉价格、退改、证据和状态：

```bash
python3 scripts/check_gannan_order_candidates.py \
  data/gannan_flight_candidates.csv \
  data/gannan_hotel_candidates.csv \
  data/gannan_transport_quotes.csv \
  data/gannan_ticket_candidates.csv
```

生成候选评分卡，判断先推进哪几个候选：

```bash
python3 scripts/gannan_candidate_scorecard.py
python3 scripts/gannan_candidate_scorecard.py --strict
```

检查真实候选是否覆盖完整行程：

```bash
python3 scripts/check_gannan_order_coverage.py --strict
```

## 反复核验日志

检查核心机位覆盖：

```bash
python3 scripts/check_gannan_photo_spots.py
python3 scripts/gannan_photo_readiness_gate.py
python3 scripts/gannan_photo_readiness_gate.py --check
```

准备下单或临近出发时，复制日志模板：

```bash
cp data/gannan_reverification_log.template.csv data/gannan_reverification_log.csv
```

检查复核日志格式：

```bash
python3 scripts/check_gannan_reverification_log.py data/gannan_reverification_log.csv
```

追踪多轮复核差异：

```bash
python3 scripts/gannan_reverification_diff.py --strict
```

按出发日期生成复核日程：

```bash
python3 scripts/gannan_reverification_schedule.py --route-start-date 2026-09-12
python3 scripts/gannan_reverification_schedule.py --route-start-date 2026-09-12 --format csv --output data/gannan_reverification_log.csv
```

导出复核日历提醒：

```bash
python3 scripts/gannan_reverification_calendar.py --route-start-date YYYY-MM-DD
```

生成订单复核报告：

```bash
python3 scripts/gannan_order_report.py
```

生成下单决策闸门：

```bash
python3 scripts/gannan_booking_gate.py
python3 scripts/gannan_booking_gate.py --strict
```

生成目标完成审计：

```bash
python3 scripts/audit_gannan_goal_completion.py
python3 scripts/audit_gannan_goal_completion.py --strict
```

检查订单证据文件是否存在：

```bash
python3 scripts/check_gannan_evidence.py
python3 scripts/check_gannan_evidence.py --strict
```

## 来源台账检查

检查来源 CSV 格式：

```bash
python3 scripts/check_gannan_sources.py
```

需要复核外部链接可达性时：

```bash
python3 scripts/check_gannan_sources.py --online
```

生成来源健康报告：

```bash
python3 scripts/gannan_source_health_report.py
python3 scripts/gannan_source_health_report.py --online
```

生成来源故障处理报告：

```bash
python3 scripts/gannan_source_fallbacks.py
python3 scripts/gannan_source_fallbacks.py --online
```

## 光线表生成

有出发日期后，生成 9 天路线光线窗口：

```bash
python3 scripts/gannan_light_windows.py --start 2026-09-12 --days 9
```
