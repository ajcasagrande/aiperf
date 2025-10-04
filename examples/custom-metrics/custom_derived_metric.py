#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Custom Derived Metric Example

This example demonstrates creating a derived metric that computes
the average tokens per request.

Derived metrics are computed from other metrics after all records
are processed, and don't have access to individual request records.

Usage:
    python custom_derived_metric.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.common.exceptions import NoMetricValue
from aiperf.metrics import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict
from aiperf.metrics.types.output_sequence_length_metric import (
    OutputSequenceLengthMetric,
)
from aiperf.metrics.types.request_count_metric import RequestCountMetric


class AverageOutputTokensMetric(BaseDerivedMetric[float]):
    """
    Compute average output tokens per request.

    This is a simple derived metric that divides total output tokens
    by the number of requests.

    Formula:
        average = sum(output_tokens) / request_count
    """

    # Required: Unique identifier
    tag = "avg_output_tokens"

    # Required: Display name
    header = "Average Output Tokens"

    # Optional: Short name for dashboards
    short_header = "Avg Tokens"

    # Required: Unit
    unit = GenericMetricUnit.TOKENS

    # Optional: Display order
    display_order = 600

    # Required: Flags
    flags = MetricFlags.PRODUCES_TOKENS_ONLY | MetricFlags.LARGER_IS_BETTER

    # Required: Dependencies
    # This metric needs OutputSequenceLengthMetric and RequestCountMetric
    required_metrics = {
        OutputSequenceLengthMetric.tag,
        RequestCountMetric.tag,
    }

    def _derive_value(self, metric_results: MetricResultsDict) -> float:
        """
        Compute the metric value from other metrics.

        Args:
            metric_results: Dict containing all computed metrics

        Returns:
            Average output tokens per request

        Raises:
            NoMetricValue: If required metrics are missing or invalid
        """
        # Get request count (single value)
        request_count = metric_results.get_or_raise(RequestCountMetric)

        if request_count == 0:
            raise NoMetricValue("No requests processed")

        # Get output sequence length (this is a MetricArray for record metrics)
        output_length_array = metric_results.get_or_raise(OutputSequenceLengthMetric)

        # MetricArray has a .sum property for efficient aggregation
        total_output_tokens = output_length_array.sum

        # Compute average
        average = total_output_tokens / request_count

        return average


def main():
    """Run a benchmark with the custom derived metric."""
    from aiperf.cli_runner import run_system_controller
    from aiperf.common.config import (
        EndpointConfig,
        LoadGeneratorConfig,
        UserConfig,
        load_service_config,
    )
    from aiperf.common.enums import EndpointType

    print("Custom Derived Metric Example: Average Output Tokens")
    print("=" * 60)
    print("\nThis benchmark includes a custom derived metric that computes")
    print("the average number of output tokens per request.\n")
    print("The metric is computed AFTER all requests complete by dividing")
    print("the sum of all output tokens by the request count.\n")

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

    service_config = load_service_config()

    print("Starting benchmark with custom derived metric...")
    print("-" * 60)

    try:
        run_system_controller(user_config, service_config)
        print("\nLook for 'Average Output Tokens' in the results above!")

    except KeyboardInterrupt:
        print("\nBenchmark cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Verify metric is registered
    from aiperf.metrics.metric_registry import MetricRegistry

    if "avg_output_tokens" in MetricRegistry.all_tags():
        print(f"Custom derived metric registered: {AverageOutputTokensMetric.tag}")
        print(f"Dependencies: {AverageOutputTokensMetric.required_metrics}")
        print()

    main()
