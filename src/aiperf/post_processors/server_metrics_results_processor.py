# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

from aiperf.common.config import UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ResultsProcessorType
from aiperf.common.exceptions import NoMetricValue
from aiperf.common.factories import ResultsProcessorFactory
from aiperf.common.models import MetricResult
from aiperf.common.models.server_metrics_models import (
    ServerMetricRecord,
    ServerMetricsHierarchy,
)
from aiperf.common.protocols import (
    ServerMetricsResultsProcessorProtocol,
)
from aiperf.exporters.display_units_utils import normalize_endpoint_display
from aiperf.post_processors.base_metrics_processor import BaseMetricsProcessor
from aiperf.server_metrics.constants import SERVER_METRICS_CONFIG


@implements_protocol(ServerMetricsResultsProcessorProtocol)
@ResultsProcessorFactory.register(ResultsProcessorType.SERVER_METRICS_RESULTS)
class ServerMetricsResultsProcessor(BaseMetricsProcessor):
    """Process individual ServerMetricRecord objects into hierarchical storage."""

    def __init__(self, user_config: UserConfig, **kwargs: Any):
        super().__init__(user_config=user_config, **kwargs)

        self._server_metrics_hierarchy = ServerMetricsHierarchy()

    def get_server_metrics_hierarchy(self) -> ServerMetricsHierarchy:
        """Get the accumulated server metrics hierarchy."""
        return self._server_metrics_hierarchy

    async def process_server_metric_record(self, record: ServerMetricRecord) -> None:
        """Process individual server metric record into hierarchical storage.

        Args:
            record: ServerMetricRecord containing server metrics and hierarchical metadata
        """
        self._server_metrics_hierarchy.add_record(record)

    async def summarize(self) -> list[MetricResult]:
        """Generate MetricResult list for real-time display and final export.

        This method is called by RecordsManager for:
        1. Final results generation when profiling completes
        2. Real-time dashboard updates (if implemented)

        Returns:
            List of MetricResult objects, one per server per metric type.
            Tags follow hierarchical naming pattern for dashboard filtering.
        """
        results = []

        for (
            server_url,
            server_data,
        ) in self._server_metrics_hierarchy.server_endpoints.items():
            endpoint_display = normalize_endpoint_display(server_url)

            for server_id, server_metrics_data in server_data.items():
                server_type = server_metrics_data.metadata.server_type or "server"
                hostname = server_metrics_data.metadata.hostname or "unknown"

                for (
                    metric_display,
                    metric_name,
                    unit_enum,
                ) in SERVER_METRICS_CONFIG:
                    try:
                        server_tag = (
                            server_url.replace(":", "_")
                            .replace("/", "_")
                            .replace(".", "_")
                        )
                        tag = f"{metric_name}_server_{server_tag}_{server_id}"

                        header = f"{metric_display} | {endpoint_display} | {server_type} | {hostname}"

                        unit = unit_enum.value

                        result = server_metrics_data.get_metric_result(
                            metric_name, tag, header, unit
                        )
                        results.append(result)
                    except NoMetricValue:
                        self.debug(
                            f"No data available for metric '{metric_name}' on server {server_id} from {server_url}"
                        )
                        continue
                    except Exception as e:
                        self.exception(
                            f"Unexpected error generating metric result for '{metric_name}' on server {server_id} from {server_url}: {e}"
                        )
                        continue

        return results
