#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Custom Record Metric Example

This example demonstrates how to create a custom per-request metric
that computes the ratio of output tokens to input tokens.

The metric is automatically registered and computed for every request.

Usage:
    python custom_record_metric.py

Expected Output:
    Your custom metric will appear in the benchmark results table.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.common.exceptions import NoMetricValue
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class OutputToInputRatioMetric(BaseRecordMetric[float]):
    """
    Compute the ratio of output tokens to input tokens.

    This metric helps understand how much output the model generates
    relative to the input prompt size.

    Formula:
        ratio = output_tokens / input_tokens
    """

    # Required: Unique identifier for this metric
    tag = "output_to_input_ratio"

    # Required: Display name shown in results
    header = "Output/Input Ratio"

    # Optional: Short name for compact displays (dashboards)
    short_header = "O/I Ratio"

    # Required: Unit of measurement
    unit = GenericMetricUnit.RATIO

    # Optional: Control display order (lower = earlier)
    display_order = 500

    # Required: Flags controlling when/how metric is computed
    flags = MetricFlags.PRODUCES_TOKENS_ONLY | MetricFlags.LARGER_IS_BETTER

    # Optional: Dependencies on other metrics (none in this case)
    required_metrics = None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> float:
        """
        Compute the metric value for a single record.

        Args:
            record: Parsed response record with token counts
            record_metrics: Previously computed metrics (for dependencies)

        Returns:
            The output/input ratio

        Raises:
            NoMetricValue: If token counts are not available
        """
        # Check if token counts are available
        if record.input_token_count is None or record.input_token_count == 0:
            raise NoMetricValue("Input token count not available or zero")

        if record.output_token_count is None:
            raise NoMetricValue("Output token count not available")

        # Compute ratio
        ratio = record.output_token_count / record.input_token_count

        return ratio


def main():
    """
    Run a benchmark with the custom metric.

    The metric is automatically registered when the class is defined,
    so we just need to run a normal benchmark.
    """
    from aiperf.cli_runner import run_system_controller
    from aiperf.common.config import (
        EndpointConfig,
        LoadGeneratorConfig,
        UserConfig,
        load_service_config,
    )
    from aiperf.common.enums import EndpointType

    print("Custom Metric Example: Output/Input Ratio")
    print("=" * 60)
    print("\nThis benchmark includes a custom metric that computes")
    print("the ratio of output tokens to input tokens.\n")

    # Configure endpoint
    endpoint_config = EndpointConfig(
        model_names=["Qwen/Qwen3-0.6B"],
        url="http://localhost:8000",
        type=EndpointType.CHAT,
        streaming=True,
    )

    # Configure load generation
    loadgen_config = LoadGeneratorConfig(
        request_count=50,
        concurrency=5,
    )

    # Create user configuration
    user_config = UserConfig(
        endpoint=endpoint_config,
        loadgen=loadgen_config,
    )

    # Load service configuration
    service_config = load_service_config()

    print("Starting benchmark with custom metric...")
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)
        print("\nLook for 'Output/Input Ratio' in the results above!")
    except KeyboardInterrupt:
        print("\nBenchmark cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # The metric is automatically registered when the class is defined
    # Verify it's registered
    from aiperf.metrics.metric_registry import MetricRegistry

    if "output_to_input_ratio" in MetricRegistry.all_tags():
        print(f"Custom metric registered: {OutputToInputRatioMetric.tag}")
        print(f"Display name: {OutputToInputRatioMetric.header}")
        print(f"Flags: {OutputToInputRatioMetric.flags}")
        print()

    main()
