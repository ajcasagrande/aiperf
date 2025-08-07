#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0


from aiperf.common.enums import MetricFlags
from aiperf.common.enums.metric_enums import MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.base_record_metric import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class PreRequestLatencyMetric(BaseRecordMetric[int]):
    """
    Post-processor for calculating Pre-Request Latency metrics from records. This is an internal metric that is
    intended to be used for debugging and performance analysis of the AIPerf internal system.

    It exposes how long it took from when a credit was dropped, to when the actual request was sent. This will
    include the time it took to query the DatasetManager to get the Turn, as well as the time it took to format
    the request.

    Formula:
        Pre-Request Latency = Request Start Time - Credit Drop Time
    """

    tag = "pre_request_latency"
    header = "Pre-Request Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.INTERNAL
    required_metrics = None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        """
        This method extracts the pre-request latency from the record and returns it.

        Raises:
            ValueError: If the record does not have a pre-request latency.
        """
        if record.request.pre_request_latency is None:
            raise ValueError("Pre-Request Latency is not available for the record.")

        return record.request.pre_request_latency
