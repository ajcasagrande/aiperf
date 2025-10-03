#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Example script for processing raw AIPerf record exports.

This script demonstrates how to:
1. Load raw records from JSONL files
2. Filter records by various criteria
3. Compute custom metrics
4. Export consolidated results

Usage:
    python process_raw_records.py --artifact-dir ./artifacts
    python process_raw_records.py --artifact-dir ./artifacts --consolidate
    python process_raw_records.py --artifact-dir ./artifacts --phase profiling --output metrics.json
"""

import argparse
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import orjson


def load_raw_records(
    artifact_dir: Path, pattern: str = "profile_export_raw_*.jsonl"
) -> list[dict[str, Any]]:
    """Load all raw records from JSONL files in the artifact directory.

    Args:
        artifact_dir: Path to the artifacts directory
        pattern: Glob pattern for raw record files

    Returns:
        List of raw record dictionaries
    """
    records = []

    for jsonl_file in sorted(artifact_dir.glob(pattern)):
        print(f"Loading {jsonl_file.name}...")
        with open(jsonl_file, "rb") as f:
            for line in f:
                record = orjson.loads(line)
                records.append(record)

    return records


def filter_records(
    records: list[dict[str, Any]],
    phase: str | None = None,
    valid_only: bool = True,
) -> list[dict[str, Any]]:
    """Filter records by criteria.

    Args:
        records: List of raw records
        phase: Filter by credit phase ('warmup' or 'profiling')
        valid_only: Only include records without errors

    Returns:
        Filtered list of records
    """
    filtered = records

    if phase:
        filtered = [r for r in filtered if r.get("credit_phase") == phase]

    if valid_only:
        filtered = [r for r in filtered if not r.get("error")]

    return filtered


def compute_latency_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    """Compute latency metrics from raw records.

    Args:
        records: List of raw records

    Returns:
        Dictionary of latency metrics in seconds
    """
    latencies_ns = [
        r["end_perf_ns"] - r["start_perf_ns"]
        for r in records
        if r.get("end_perf_ns") and r.get("start_perf_ns")
    ]

    if not latencies_ns:
        return {}

    latencies_s = [lat / 1e9 for lat in latencies_ns]
    sorted_latencies = sorted(latencies_s)

    return {
        "count": len(latencies_s),
        "mean": statistics.mean(latencies_s),
        "median": statistics.median(latencies_s),
        "stdev": statistics.stdev(latencies_s) if len(latencies_s) > 1 else 0.0,
        "min": min(latencies_s),
        "max": max(latencies_s),
        "p50": sorted_latencies[int(len(sorted_latencies) * 0.50)],
        "p90": sorted_latencies[int(len(sorted_latencies) * 0.90)],
        "p95": sorted_latencies[int(len(sorted_latencies) * 0.95)],
        "p99": sorted_latencies[int(len(sorted_latencies) * 0.99)],
    }


def compute_throughput_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    """Compute throughput metrics from raw records.

    Args:
        records: List of raw records

    Returns:
        Dictionary of throughput metrics
    """
    if not records:
        return {}

    # Get time range
    start_times = [r["timestamp_ns"] for r in records if r.get("timestamp_ns")]
    end_times = [r["end_perf_ns"] for r in records if r.get("end_perf_ns")]

    if not start_times or not end_times:
        return {}

    duration_s = (max(end_times) - min(start_times)) / 1e9

    return {
        "total_requests": len(records),
        "duration_seconds": duration_s,
        "requests_per_second": len(records) / duration_s if duration_s > 0 else 0,
    }


def compute_error_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute error metrics from raw records.

    Args:
        records: List of raw records (including errors)

    Returns:
        Dictionary of error metrics
    """
    total = len(records)
    error_records = [r for r in records if r.get("error")]

    # Group errors by type
    errors_by_type = defaultdict(int)
    for record in error_records:
        error_type = record["error"].get("type", "Unknown")
        errors_by_type[error_type] += 1

    return {
        "total_records": total,
        "error_count": len(error_records),
        "error_rate": len(error_records) / total if total > 0 else 0,
        "success_rate": (total - len(error_records)) / total if total > 0 else 0,
        "errors_by_type": dict(errors_by_type),
    }


def consolidate_records(
    artifact_dir: Path, output_file: Path, pattern: str = "profile_export_raw_*.jsonl"
) -> int:
    """Consolidate per-processor raw records into a single file.

    Args:
        artifact_dir: Path to the artifacts directory
        output_file: Path to the consolidated output file
        pattern: Glob pattern for raw record files

    Returns:
        Number of records consolidated
    """
    record_count = 0

    with open(output_file, "wb") as out:
        for jsonl_file in sorted(artifact_dir.glob(pattern)):
            print(f"Consolidating {jsonl_file.name}...")
            with open(jsonl_file, "rb") as f:
                for line in f:
                    out.write(line)
                    record_count += 1

    return record_count


def main():
    parser = argparse.ArgumentParser(
        description="Process AIPerf raw record exports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("./artifacts"),
        help="Path to artifacts directory containing raw records",
    )
    parser.add_argument(
        "--phase",
        choices=["warmup", "profiling"],
        help="Filter by credit phase",
    )
    parser.add_argument(
        "--include-errors",
        action="store_true",
        help="Include error records in analysis",
    )
    parser.add_argument(
        "--consolidate",
        action="store_true",
        help="Consolidate per-processor files into a single file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for consolidated records or metrics (JSON)",
    )

    args = parser.parse_args()

    if not args.artifact_dir.exists():
        print(f"Error: Artifact directory not found: {args.artifact_dir}")
        return 1

    # Consolidate mode
    if args.consolidate:
        output_file = (
            args.output or args.artifact_dir / "profile_export_raw_consolidated.jsonl"
        )
        print(f"Consolidating raw records to {output_file}...")
        count = consolidate_records(args.artifact_dir, output_file)
        print(f"Consolidated {count} records")
        return 0

    # Analysis mode
    print(f"Loading raw records from {args.artifact_dir}...")
    all_records = load_raw_records(args.artifact_dir)
    print(f"Loaded {len(all_records)} raw records")

    # Filter records
    filtered_records = filter_records(
        all_records,
        phase=args.phase,
        valid_only=not args.include_errors,
    )
    print(f"Filtered to {len(filtered_records)} records")

    # Compute metrics
    print("\n=== Computing Metrics ===")

    latency_metrics = compute_latency_metrics(filtered_records)
    throughput_metrics = compute_throughput_metrics(filtered_records)
    error_metrics = compute_error_metrics(all_records)

    metrics = {
        "latency": latency_metrics,
        "throughput": throughput_metrics,
        "errors": error_metrics,
    }

    # Print results
    print("\n=== Latency Metrics (seconds) ===")
    for key, value in latency_metrics.items():
        if key == "count":
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: {value:.4f}")

    print("\n=== Throughput Metrics ===")
    for key, value in throughput_metrics.items():
        if isinstance(value, int):
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: {value:.2f}")

    print("\n=== Error Metrics ===")
    print(f"  total_records: {error_metrics['total_records']}")
    print(f"  error_count: {error_metrics['error_count']}")
    print(f"  error_rate: {error_metrics['error_rate']:.2%}")
    print(f"  success_rate: {error_metrics['success_rate']:.2%}")
    if error_metrics["errors_by_type"]:
        print("  errors_by_type:")
        for error_type, count in error_metrics["errors_by_type"].items():
            print(f"    {error_type}: {count}")

    # Save to file if requested
    if args.output:
        with open(args.output, "wb") as f:
            f.write(orjson.dumps(metrics, option=orjson.OPT_INDENT_2))
        print(f"\nMetrics saved to {args.output}")

    return 0


if __name__ == "__main__":
    exit(main())
