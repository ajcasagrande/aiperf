# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Data Processing Engine for AIPerf Dashboard v3
Handles all data transformations, queries, and analytics
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np


class DataProcessor:
    """High-performance data processor for benchmark data"""

    def __init__(self, data_dir: str = "../data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache = {}
        self.benchmarks_index = {}
        self._load_index()

    def _load_index(self):
        """Load benchmark index"""
        index_file = self.data_dir / "index.json"
        if index_file.exists():
            with open(index_file) as f:
                self.benchmarks_index = json.load(f)

    def _save_index(self):
        """Save benchmark index"""
        index_file = self.data_dir / "index.json"
        with open(index_file, "w") as f:
            json.dump(self.benchmarks_index, f, indent=2)

    async def list_benchmarks(self) -> list[dict]:
        """List all available benchmarks"""
        benchmarks = []
        for benchmark_id, info in self.benchmarks_index.items():
            benchmarks.append(
                {
                    "id": benchmark_id,
                    "name": info.get("name", benchmark_id),
                    "timestamp": info.get("timestamp"),
                    "summary": info.get("summary", {}),
                }
            )
        return sorted(benchmarks, key=lambda x: x["timestamp"], reverse=True)

    async def get_benchmark_data(self, benchmark_id: str) -> dict:
        """Get complete benchmark data"""
        # Check cache
        if benchmark_id in self.cache:
            return self.cache[benchmark_id]

        # Load from disk
        benchmark_dir = self.data_dir / benchmark_id

        if not benchmark_dir.exists():
            raise FileNotFoundError(f"Benchmark {benchmark_id} not found")

        data = {
            "id": benchmark_id,
            "metadata": {},
            "records": [],
            "aggregate": {},
            "statistics": {},
        }

        # Load JSONL records
        jsonl_file = benchmark_dir / "records.jsonl"
        if jsonl_file.exists():
            records = []
            with open(jsonl_file, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError as e:
                        print(
                            f"Warning: Skipping malformed JSON at line {line_num} in {jsonl_file}: {e}"
                        )
                        continue
            data["records"] = records

        # Load aggregate data
        aggregate_file = benchmark_dir / "aggregate.json"
        if aggregate_file.exists():
            try:
                with open(aggregate_file, encoding="utf-8") as f:
                    data["aggregate"] = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse aggregate JSON file: {e}")
                data["aggregate"] = {}

        # Compute statistics (merging aggregate and record-level data)
        data["statistics"] = await self._compute_statistics(
            data["records"], data["aggregate"]
        )

        # Cache
        self.cache[benchmark_id] = data

        return data

    async def _compute_statistics(
        self, records: list[dict], aggregate: dict = None
    ) -> dict:
        """Compute comprehensive statistics from records and aggregate data"""
        if not records:
            return {}

        # Extract all metrics from records
        metrics = defaultdict(list)

        for record in records:
            if "metrics" in record:
                for metric_name, metric_data in record["metrics"].items():
                    value = metric_data.get("value")
                    if isinstance(value, (int, float)):
                        metrics[metric_name].append(value)
                    elif isinstance(value, list):
                        metrics[f"{metric_name}_list"] = value

        # Compute stats for each metric from records
        stats = {}
        for metric_name, values in metrics.items():
            if values:
                values_array = np.array(values)
                stats[metric_name] = {
                    "count": len(values),
                    "mean": float(np.mean(values_array)),
                    "std": float(np.std(values_array)),
                    "min": float(np.min(values_array)),
                    "max": float(np.max(values_array)),
                    "p1": float(np.percentile(values_array, 1)),
                    "p5": float(np.percentile(values_array, 5)),
                    "p25": float(np.percentile(values_array, 25)),
                    "p50": float(np.percentile(values_array, 50)),
                    "p75": float(np.percentile(values_array, 75)),
                    "p90": float(np.percentile(values_array, 90)),
                    "p95": float(np.percentile(values_array, 95)),
                    "p99": float(np.percentile(values_array, 99)),
                }

        # Merge in aggregate-level metrics if available
        if aggregate and "records" in aggregate:
            aggregate_metrics = aggregate["records"]
            print(
                f"📊 Merging {len(aggregate_metrics)} aggregate metrics into statistics"
            )
            for metric_name, metric_data in aggregate_metrics.items():
                # For aggregate-level metrics (throughput, goodput), use the aggregate values
                if metric_data.get("avg") is not None:
                    # Create or update the metric with aggregate data
                    if metric_name not in stats:
                        stats[metric_name] = {}

                    # Use aggregate values, especially for throughput and goodput
                    stats[metric_name].update(
                        {
                            "mean": float(metric_data["avg"]),
                            "min": float(metric_data["min"])
                            if metric_data["min"] is not None
                            else stats[metric_name].get("min", 0),
                            "max": float(metric_data["max"])
                            if metric_data["max"] is not None
                            else stats[metric_name].get("max", 0),
                            "p1": float(metric_data["p1"])
                            if metric_data["p1"] is not None
                            else stats[metric_name].get("p1", 0),
                            "p5": float(metric_data["p5"])
                            if metric_data["p5"] is not None
                            else stats[metric_name].get("p5", 0),
                            "p25": float(metric_data["p25"])
                            if metric_data["p25"] is not None
                            else stats[metric_name].get("p25", 0),
                            "p50": float(metric_data["p50"])
                            if metric_data["p50"] is not None
                            else stats[metric_name].get("p50", 0),
                            "p75": float(metric_data["p75"])
                            if metric_data["p75"] is not None
                            else stats[metric_name].get("p75", 0),
                            "p90": float(metric_data["p90"])
                            if metric_data["p90"] is not None
                            else stats[metric_name].get("p90", 0),
                            "p95": float(metric_data["p95"])
                            if metric_data["p95"] is not None
                            else stats[metric_name].get("p95", 0),
                            "p99": float(metric_data["p99"])
                            if metric_data["p99"] is not None
                            else stats[metric_name].get("p99", 0),
                            "std": float(metric_data["std"])
                            if metric_data["std"] is not None
                            else stats[metric_name].get("std", 0),
                            "count": int(metric_data["count"])
                            if metric_data["count"] is not None
                            else stats[metric_name].get("count", 0),
                        }
                    )

        # Log key metrics for debugging
        key_metrics = [
            "request_throughput",
            "output_token_throughput",
            "request_latency",
            "goodput",
            "ttft",
        ]
        print("✅ Statistics computed. Key metrics:")
        for metric in key_metrics:
            if metric in stats:
                print(f"   • {metric}: mean={stats[metric].get('mean', 0):.2f}")

        return stats

    async def process_upload(
        self, benchmark_id: str, jsonl_data: bytes, aggregate_data: bytes | None = None
    ) -> dict:
        """Process uploaded benchmark data"""
        benchmark_dir = self.data_dir / benchmark_id
        benchmark_dir.mkdir(parents=True, exist_ok=True)

        # Save JSONL
        jsonl_file = benchmark_dir / "records.jsonl"
        with open(jsonl_file, "wb") as f:
            f.write(jsonl_data)

        # Save aggregate if provided
        if aggregate_data:
            aggregate_file = benchmark_dir / "aggregate.json"
            with open(aggregate_file, "wb") as f:
                f.write(aggregate_data)

        # Parse and compute summary
        records = []
        for line_num, line in enumerate(jsonl_data.decode().split("\n"), 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping malformed JSON at line {line_num}: {e}")
                continue

        if not records:
            raise ValueError("No valid records found in JSONL file")

        # Parse aggregate data if provided
        aggregate = {}
        if aggregate_data:
            try:
                aggregate = json.loads(aggregate_data.decode())
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse aggregate JSON: {e}")

        # Compute statistics with aggregate data
        stats = await self._compute_statistics(records, aggregate)

        # Update index with better summary data
        self.benchmarks_index[benchmark_id] = {
            "name": benchmark_id,
            "timestamp": datetime.now().isoformat(),
            "record_count": len(records),
            "summary": {
                "total_requests": len(records),
                "avg_latency": stats.get("request_latency", {}).get("mean", 0),
                "throughput": stats.get("request_throughput", {}).get("mean", 0),
                "goodput": stats.get("goodput", {}).get("mean", 0),
            },
        }
        self._save_index()

        return {"records_processed": len(records), "statistics": stats}

    async def query_metrics(
        self,
        metric: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
        filters: dict | None = None,
    ) -> list[dict]:
        """Query metrics with filters"""
        # This would implement advanced filtering
        # For now, return placeholder
        return []

    async def compare_benchmarks(
        self, benchmark_ids: list[str], metrics: list[str]
    ) -> dict:
        """Compare multiple benchmarks"""
        comparison = {"benchmarks": benchmark_ids, "metrics": metrics, "data": {}}

        for benchmark_id in benchmark_ids:
            try:
                data = await self.get_benchmark_data(benchmark_id)
                stats = data.get("statistics", {})

                comparison["data"][benchmark_id] = {
                    metric: stats.get(metric, {}) for metric in metrics
                }
            except Exception as e:
                comparison["data"][benchmark_id] = {"error": str(e)}

        # Compute relative differences
        comparison["analysis"] = self._analyze_comparison(comparison["data"], metrics)

        return comparison

    def _analyze_comparison(self, data: dict, metrics: list[str]) -> dict:
        """Analyze comparison and generate insights"""
        analysis = {}

        for metric in metrics:
            values = {}
            for benchmark_id, benchmark_data in data.items():
                if metric in benchmark_data and "mean" in benchmark_data[metric]:
                    values[benchmark_id] = benchmark_data[metric]["mean"]

            if len(values) >= 2:
                sorted_values = sorted(values.items(), key=lambda x: x[1])
                best = sorted_values[0]
                worst = sorted_values[-1]

                analysis[metric] = {
                    "best": {"benchmark": best[0], "value": best[1]},
                    "worst": {"benchmark": worst[0], "value": worst[1]},
                    "spread": worst[1] - best[1],
                    "relative_diff": ((worst[1] - best[1]) / best[1] * 100)
                    if best[1] > 0
                    else 0,
                }

        return analysis

    async def export_benchmark(self, benchmark_id: str, format: str) -> dict:
        """Export benchmark data in specified format"""
        data = await self.get_benchmark_data(benchmark_id)

        if format == "json":
            return data
        elif format == "csv":
            # Convert to CSV format
            return {"message": "CSV export not yet implemented"}
        elif format == "parquet":
            return {"message": "Parquet export not yet implemented"}

        return {}

    async def get_summary_stats(self) -> dict:
        """Get summary statistics across all benchmarks"""
        summary = {
            "total_benchmarks": len(self.benchmarks_index),
            "recent_benchmarks": [],
            "aggregate_stats": {},
        }

        # Get 10 most recent benchmarks
        benchmarks = await self.list_benchmarks()
        summary["recent_benchmarks"] = benchmarks[:10]

        return summary

    async def get_leaderboard(self) -> list[dict]:
        """Get performance leaderboard"""
        leaderboard = []

        for benchmark_id in self.benchmarks_index.keys():
            try:
                data = await self.get_benchmark_data(benchmark_id)
                stats = data.get("statistics", {})

                # Calculate performance score
                score = self._calculate_performance_score(stats)

                leaderboard.append(
                    {
                        "benchmark_id": benchmark_id,
                        "score": score,
                        "key_metrics": {
                            "throughput": stats.get("request_throughput", {}).get(
                                "mean", 0
                            ),
                            "latency_p50": stats.get("request_latency", {}).get(
                                "p50", 0
                            ),
                            "latency_p99": stats.get("request_latency", {}).get(
                                "p99", 0
                            ),
                        },
                    }
                )
            except:
                pass

        # Sort by score
        leaderboard.sort(key=lambda x: x["score"], reverse=True)

        return leaderboard

    def _calculate_performance_score(self, stats: dict) -> float:
        """Calculate composite performance score"""
        # Simplified scoring algorithm
        score = 0.0

        throughput = stats.get("request_throughput", {}).get("mean", 0)
        latency = stats.get("request_latency", {}).get("p50", 1)

        # Higher throughput is better
        score += throughput * 10

        # Lower latency is better
        score += 1000000 / max(latency, 1)

        return score

    async def get_metric_trends(self, metric: str, window: int = 30) -> list[dict]:
        """Get historical trends for a metric"""
        trends = []

        for benchmark_id in self.benchmarks_index.keys():
            try:
                data = await self.get_benchmark_data(benchmark_id)
                stats = data.get("statistics", {})
                timestamp = self.benchmarks_index[benchmark_id].get("timestamp")

                if metric in stats:
                    trends.append(
                        {
                            "timestamp": timestamp,
                            "benchmark_id": benchmark_id,
                            "value": stats[metric].get("mean", 0),
                        }
                    )
            except:
                pass

        # Sort by timestamp
        trends.sort(key=lambda x: x["timestamp"])

        return trends[-window:]
