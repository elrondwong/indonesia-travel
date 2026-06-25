# 甘南订单复核证据归档

这个目录用于保存机票/高铁、酒店、包车/租车、门票、景区开放、天气、路线、无人机和保险的截图或确认记录。

建议文件名：

```text
YYYYMMDD_T-14_flight_outbound_option-a_price-policy.png
YYYYMMDD_T-7_hotel_zhagana_option-b_parking-hotwater.jpg
YYYYMMDD_T-3_ticket_lianbao_open-scope.png
YYYYMMDD_T-1_route_zhagana_lianbao_weather-road.png
YYYYMMDD_D-day_ticket_zhagana_gate-notice.jpg
```

字段填写规则：

- 候选 CSV 的 `evidence_file` 可以写 `20260901_T-14_flight_a.png`，脚本会默认到本目录查找。
- 也可以写完整相对路径，例如 `evidence/gannan/20260901_T-14_flight_a.png`。
- 多个证据用 `|` 分隔，例如 `flight_price.png|flight_policy.png`。
- 不建议只写网址；下单页、聊天记录、酒店确认和景区公告都要另存为本地截图或文本。

检查命令：

```bash
python3 scripts/check_gannan_evidence.py
python3 scripts/check_gannan_evidence.py --strict
```
