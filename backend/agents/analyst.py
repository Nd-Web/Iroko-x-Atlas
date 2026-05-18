"""
Analyst Agent
Performs quantitative analysis, pattern detection, and chart generation.
"""
import json
import logging
from typing import Optional, List, Annotated
from datetime import datetime, timedelta
from agents._compat import kernel_function, Kernel

logger = logging.getLogger(__name__)


class AnalystAgent:
    """
    The Analyst specialises in numbers. Given raw data from documents,
    it finds patterns, computes statistics, detects anomalies,
    and generates charts for the dashboard.
    """

    @kernel_function(
        description="""Analyse a list of data points and return statistics including
        total, average, trend direction, and any anomalies detected.
        Use this when you have numerical data that needs to be summarised."""
    )
    async def compute_statistics(
        self,
        data: Annotated[str, "JSON string of data points: [{date, value, label}]"],
        metric_name: Annotated[str, "What is being measured e.g. 'customer complaints'"],
    ) -> str:
        try:
            points = json.loads(data) if isinstance(data, str) else data
            if not points:
                return json.dumps({"error": "No data provided"})

            values = [p.get("value", 0) for p in points if isinstance(p.get("value"), (int, float))]
            if not values:
                return json.dumps({"error": "No numeric values found in data"})

            total = sum(values)
            average = total / len(values)
            minimum = min(values)
            maximum = max(values)
            latest = values[-1] if values else 0
            previous = values[-2] if len(values) > 1 else latest
            change_pct = ((latest - previous) / previous * 100) if previous != 0 else 0

            # Detect anomalies — values more than 2 standard deviations from mean
            mean = average
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            std_dev = variance ** 0.5
            anomalies = [
                {"index": i, "value": v, "deviation": round((v - mean) / std_dev, 2)}
                for i, v in enumerate(values)
                if abs(v - mean) > 2 * std_dev
            ]

            # Trend direction
            if len(values) >= 3:
                first_half_avg = sum(values[:len(values)//2]) / (len(values)//2)
                second_half_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
                trend = "increasing" if second_half_avg > first_half_avg * 1.05 else \
                        "decreasing" if second_half_avg < first_half_avg * 0.95 else "stable"
            else:
                trend = "insufficient data"

            return json.dumps({
                "metric": metric_name,
                "summary": {
                    "total": round(total, 2),
                    "average": round(average, 2),
                    "minimum": round(minimum, 2),
                    "maximum": round(maximum, 2),
                    "latest_value": latest,
                    "change_from_previous": f"{change_pct:+.1f}%",
                    "trend": trend,
                    "data_points": len(values),
                },
                "anomalies": anomalies,
                "insight": self._generate_insight(metric_name, trend, change_pct, anomalies),
            })

        except Exception as e:
            logger.error(f"Analyst compute_statistics failed: {e}")
            return json.dumps({"error": str(e)})

    @kernel_function(
        description="""Find time-based patterns in data — peak hours, busiest days,
        seasonal trends. Use this for complaint data, usage data, or any
        time-series information."""
    )
    async def find_time_patterns(
        self,
        data: Annotated[str, "JSON string of timestamped events: [{timestamp, value, category}]"],
        metric_name: Annotated[str, "What is being measured"],
    ) -> str:
        try:
            from collections import defaultdict

            events = json.loads(data) if isinstance(data, str) else data
            if not events:
                return json.dumps({"patterns": {}, "message": "No data provided"})

            hour_counts: dict = defaultdict(float)
            day_counts: dict = defaultdict(float)
            month_counts: dict = defaultdict(float)
            parsed = 0

            for event in events:
                ts_str = (
                    event.get("timestamp")
                    or event.get("date")
                    or event.get("created_at")
                )
                val = event.get("value", 1)
                weight = val if isinstance(val, (int, float)) else 1

                if not ts_str:
                    continue

                dt = None
                for fmt in (
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%d",
                ):
                    try:
                        dt = datetime.strptime(str(ts_str)[:19], fmt)
                        break
                    except ValueError:
                        continue

                if dt is None:
                    continue

                hour_counts[dt.hour] += weight
                day_counts[dt.strftime("%A")] += weight
                month_counts[dt.strftime("%B")] += weight
                parsed += 1

            if parsed == 0:
                return json.dumps({
                    "metric": metric_name,
                    "events_analysed": 0,
                    "patterns": {},
                    "key_finding": "No parseable timestamps found in data.",
                })

            # Peak hours — top 3 by volume
            peak_hours = [
                f"{h:02d}:00-{(h + 1) % 24:02d}:00"
                for h, _ in sorted(hour_counts.items(), key=lambda x: -x[1])[:3]
            ]

            # Busiest / quietest day
            sorted_days = sorted(day_counts.items(), key=lambda x: -x[1])
            busiest_day = sorted_days[0][0] if sorted_days else "N/A"
            quietest_day = sorted_days[-1][0] if sorted_days else "N/A"

            # Weekday vs weekend comparison
            weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            weekend_names = ["Saturday", "Sunday"]
            weekday_total = sum(day_counts.get(d, 0) for d in weekday_names)
            weekend_total = sum(day_counts.get(d, 0) for d in weekend_names)
            weekday_avg = weekday_total / 5
            weekend_avg = weekend_total / 2

            if weekend_avg > 0:
                diff_pct = (weekday_avg - weekend_avg) / weekend_avg * 100
                weekday_vs_weekend = (
                    f"Weekdays average {diff_pct:+.0f}% vs weekends"
                )
            elif weekday_avg > 0:
                weekday_vs_weekend = "Activity concentrated on weekdays only"
            else:
                weekday_vs_weekend = "Insufficient data for weekday/weekend split"

            # Monthly trend (compare first and last observed months)
            month_values = list(month_counts.values())
            if len(month_values) >= 2:
                first_v = month_values[0]
                last_v = month_values[-1]
                if first_v > 0:
                    change = (last_v - first_v) / first_v * 100
                    monthly_trend = (
                        f"{abs(change):.0f}% {'increase' if change >= 0 else 'decrease'} "
                        f"over observed period"
                    )
                else:
                    monthly_trend = "Trend unclear (zero baseline)"
            else:
                monthly_trend = f"{parsed} events across a single month"

            key_finding = (
                f"Peak {metric_name} occurs at {peak_hours[0] if peak_hours else 'N/A'} "
                f"on {busiest_day}s. {weekday_vs_weekend}."
            )

            return json.dumps({
                "metric": metric_name,
                "events_analysed": parsed,
                "patterns": {
                    "peak_hours": peak_hours,
                    "busiest_day": busiest_day,
                    "quietest_day": quietest_day,
                    "weekday_vs_weekend": weekday_vs_weekend,
                    "monthly_trend": monthly_trend,
                },
                "key_finding": key_finding,
            })

        except Exception as e:
            return json.dumps({"error": str(e)})

    @kernel_function(
        description="""Detect anomalies or unusual spikes in a dataset.
        Use this when you need to find out if something unusual is happening
        compared to historical norms."""
    )
    async def detect_anomalies(
        self,
        current_value: Annotated[float, "The current observed value"],
        historical_average: Annotated[float, "The historical average for comparison"],
        metric_name: Annotated[str, "What is being measured"],
        threshold_pct: Annotated[float, "Percentage increase considered anomalous (default 50%)"] = 50.0,
    ) -> str:
        try:
            if historical_average == 0:
                return json.dumps({
                    "is_anomaly": True,
                    "message": f"No historical baseline for {metric_name}",
                })

            change_pct = ((current_value - historical_average) / historical_average) * 100
            is_anomaly = abs(change_pct) >= threshold_pct
            severity = "critical" if abs(change_pct) >= threshold_pct * 2 else \
                       "warning" if is_anomaly else "normal"

            return json.dumps({
                "metric": metric_name,
                "is_anomaly": is_anomaly,
                "severity": severity,
                "current_value": current_value,
                "historical_average": historical_average,
                "change_percent": round(change_pct, 1),
                "interpretation": (
                    f"{metric_name} is {abs(change_pct):.1f}% {'above' if change_pct > 0 else 'below'} "
                    f"historical average. {'This is a significant anomaly requiring attention.' if is_anomaly else 'This is within normal range.'}"
                ),
            })

        except Exception as e:
            return json.dumps({"error": str(e)})

    @kernel_function(
        description="""Compare two values or datasets and return a clear comparison summary.
        Use this when asked to compare periods, departments, or metrics."""
    )
    async def compare_metrics(
        self,
        value_a: Annotated[float, "First value"],
        value_b: Annotated[float, "Second value"],
        label_a: Annotated[str, "Label for first value e.g. 'This month'"],
        label_b: Annotated[str, "Label for second value e.g. 'Last month'"],
        metric_name: Annotated[str, "What is being compared"],
    ) -> str:
        try:
            if value_b != 0:
                change_pct = ((value_a - value_b) / value_b) * 100
                direction = "increase" if change_pct > 0 else "decrease"
            else:
                change_pct = 100
                direction = "increase"

            return json.dumps({
                "metric": metric_name,
                "comparison": {
                    label_a: value_a,
                    label_b: value_b,
                    "change": f"{change_pct:+.1f}%",
                    "direction": direction,
                    "absolute_difference": round(value_a - value_b, 2),
                },
                "summary": (
                    f"{metric_name}: {label_a} shows {abs(change_pct):.1f}% {direction} "
                    f"compared to {label_b} ({value_b} → {value_a})."
                ),
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _generate_insight(
        self, metric: str, trend: str, change_pct: float, anomalies: list
    ) -> str:
        parts = []
        if trend == "increasing":
            parts.append(f"{metric} is trending upward.")
        elif trend == "decreasing":
            parts.append(f"{metric} is trending downward.")
        else:
            parts.append(f"{metric} is stable.")

        if abs(change_pct) > 20:
            parts.append(
                f"Recent period shows a significant {change_pct:+.1f}% change."
            )
        if anomalies:
            parts.append(
                f"{len(anomalies)} anomalous data point(s) detected that warrant investigation."
            )
        return " ".join(parts)
