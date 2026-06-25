#!/usr/bin/env python3
"""Estimate Gannan route sunrise, sunset, golden-hour, and blue-hour windows."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POINTS = ROOT / "data/gannan_light_points.csv"
ZENITH = math.radians(90.833)

ROUTE_POINT_IDS = [
    "lanzhou",
    "xiahe",
    "hezuo",
    "zhagana",
    "zhagana",
    "tangke",
    "aba",
    "lianbao",
    "hezuo",
]


@dataclass(frozen=True)
class LightPoint:
    point_id: str
    name: str
    latitude: float
    longitude: float
    tz_offset: float
    route_day: str
    main_use: str


def read_points(path: Path) -> dict[str, LightPoint]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    points: dict[str, LightPoint] = {}
    for row in rows:
        point = LightPoint(
            point_id=row["id"],
            name=row["name"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            tz_offset=float(row["tz_offset"]),
            route_day=row["route_day"],
            main_use=row["main_use"],
        )
        points[point.point_id] = point
    return points


def minutes_to_hhmm(minutes: float) -> str:
    minutes = minutes % (24 * 60)
    hour = int(minutes // 60)
    minute = int(round(minutes % 60))
    if minute == 60:
        hour = (hour + 1) % 24
        minute = 0
    return f"{hour:02d}:{minute:02d}"


def solar_events(day: date, point: LightPoint) -> tuple[float, float, float]:
    day_of_year = day.timetuple().tm_yday
    gamma = 2 * math.pi / 365 * (day_of_year - 1)
    equation_of_time = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    declination = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )

    latitude = math.radians(point.latitude)
    cos_hour_angle = (
        math.cos(ZENITH) / (math.cos(latitude) * math.cos(declination))
        - math.tan(latitude) * math.tan(declination)
    )
    cos_hour_angle = min(1.0, max(-1.0, cos_hour_angle))
    hour_angle = math.degrees(math.acos(cos_hour_angle))
    solar_noon = 720 - 4 * point.longitude - equation_of_time + point.tz_offset * 60
    sunrise = solar_noon - hour_angle * 4
    sunset = solar_noon + hour_angle * 4
    return sunrise, solar_noon, sunset


def build_route_rows(start: date, days: int, points: dict[str, LightPoint]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for offset in range(days):
        current_date = start + timedelta(days=offset)
        point_id = ROUTE_POINT_IDS[min(offset, len(ROUTE_POINT_IDS) - 1)]
        point = points[point_id]
        sunrise, _, sunset = solar_events(current_date, point)
        rows.append(
            {
                "day": f"D{offset}",
                "date": current_date.isoformat(),
                "place": point.name,
                "main_use": point.main_use,
                "morning_blue": f"{minutes_to_hhmm(sunrise - 40)}-{minutes_to_hhmm(sunrise - 10)}",
                "sunrise": minutes_to_hhmm(sunrise),
                "morning_gold": f"{minutes_to_hhmm(sunrise)}-{minutes_to_hhmm(sunrise + 60)}",
                "evening_gold": f"{minutes_to_hhmm(sunset - 60)}-{minutes_to_hhmm(sunset)}",
                "sunset": minutes_to_hhmm(sunset),
                "evening_blue": f"{minutes_to_hhmm(sunset + 10)}-{minutes_to_hhmm(sunset + 40)}",
            }
        )
    return rows


def print_csv(rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)


def print_markdown(rows: list[dict[str, str]]) -> None:
    print("| 天数 | 日期 | 地点 | 主用途 | 晨蓝调 | 日出 | 早黄金 | 晚黄金 | 日落 | 晚蓝调 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        print(
            "| {day} | {date} | {place} | {main_use} | {morning_blue} | {sunrise} | {morning_gold} | {evening_gold} | {sunset} | {evening_blue} |".format(
                **row
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", help="route start date in YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=9, help="number of route days to print")
    parser.add_argument("--points", type=Path, default=DEFAULT_POINTS)
    parser.add_argument("--format", choices=["markdown", "csv"], default="markdown")
    parser.add_argument("--check", action="store_true", help="run a deterministic smoke check")
    args = parser.parse_args()

    points = read_points(args.points)
    if args.check:
        rows = build_route_rows(date(2026, 9, 12), 2, points)
        if len(rows) != 2 or not rows[0]["sunrise"] or not rows[1]["sunset"]:
            print("Gannan light window calculator failed.", file=sys.stderr)
            return 1
        print("Gannan light window calculator passed.")
        print(f"Checked {len(points)} light points.")
        return 0

    if not args.start:
        print("missing --start YYYY-MM-DD", file=sys.stderr)
        return 2
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    rows = build_route_rows(start, args.days, points)
    if args.format == "csv":
        print_csv(rows)
    else:
        print_markdown(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
