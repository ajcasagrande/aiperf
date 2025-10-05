# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Example Metric Plugin (AIP-001)

This is a complete example of an AIPerf metric plugin following AIP-001 specification.

To use this plugin:
1. Package it in a separate Python package
2. Add entry point in pyproject.toml:
   [project.entry-points."aiperf.metric"]
   response_size = "aiperf_response_size:ResponseSizeMetric"
3. Install the package: pip install aiperf-response-size
4. AIPerf automatically discovers and loads it

This example can serve as a template for creating your own metric plugins.
"""

from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.common.exceptions import NoMetricValue
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class ResponseSizeMetric(BaseRecordMetric[int]):
    """
    Response Size metric - measures response payload size in bytes.

    This is an AIPerf plugin that extends the metrics system.
    It demonstrates the AIP-001 plugin architecture.

    Formula:
        response_size = sum(len(response.text) for response in responses)
    """

    # Required metric metadata
    tag = "response_size"
    header = "Response Size"
    short_header = "Resp Size"
    unit = GenericMetricUnit.COUNT  # Using COUNT for bytes
    display_unit = None
    display_order = 600
    flags = MetricFlags.NONE
    required_metrics = None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """
        Compute response size in bytes.

        Args:
            record: Parsed response record
            record_metrics: Previously computed metrics

        Returns:
            Total response size in bytes

        Raises:
            NoMetricValue: If no responses available
        """
        if not record.responses:
            raise NoMetricValue("No responses available to measure")

        # Sum up all response text lengths
        total_size = 0
        for response in record.responses:
            if hasattr(response, 'data') and hasattr(response.data, 'content'):
                # Handle structured response data
                content = response.data.content
                if isinstance(content, str):
                    total_size += len(content.encode('utf-8'))
            elif hasattr(response, 'text'):
                # Handle simple text responses
                if response.text:
                    total_size += len(response.text.encode('utf-8'))

        return total_size


# AIP-001: Plugin metadata function
def plugin_metadata():
    """
    Return plugin metadata for AIPerf discovery.

    This function is required by AIP-001 for plugin validation.
    """
    return {
        "name": "response_size",
        "display_name": "Response Size Metric",
        "version": "1.0.0",
        "author": "AIPerf Team",
        "description": "Measures response payload size in bytes",
        "plugin_type": "metric",
        "aip_version": "001",  # AIP-001 compliant
        "license": "Apache-2.0",
        "requires": ["aiperf>=0.1.0"],
    }
