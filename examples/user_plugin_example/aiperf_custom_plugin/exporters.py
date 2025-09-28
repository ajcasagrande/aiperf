# SPDX-FileCopyrightText: Copyright (c) 2025 User Plugin Example
# SPDX-License-Identifier: Apache-2.0
"""Custom data exporters for AIPerf."""

from typing import Any, Dict
from aiperf.common.aiperf_logger import AIPerfLogger


class ElasticsearchExporter:
    """Export AIPerf results to Elasticsearch."""

    def __init__(self, host: str = "localhost", port: int = 9200, index: str = "aiperf-results"):
        self.host = host
        self.port = port
        self.index = index
        self.logger = AIPerfLogger(self.__class__.__name__)
        # In real implementation: self.client = Elasticsearch([{'host': host, 'port': port}])

    def export_data(self, data: Dict[str, Any]) -> None:
        """Export data to Elasticsearch."""
        self.logger.info(f"Exporting data to Elasticsearch at {self.host}:{self.port}")

        # Add timestamp and metadata
        export_data = {
            **data,
            "timestamp": "2025-01-01T00:00:00Z",  # In real implementation: datetime.utcnow().isoformat()
            "source": "aiperf"
        }

        # In real implementation:
        # self.client.index(index=self.index, body=export_data)

        self.logger.info(f"Successfully exported {len(data)} fields to Elasticsearch")


class PrometheusExporter:
    """Export AIPerf metrics to Prometheus."""

    def __init__(self, gateway_url: str = "http://localhost:9091", job_name: str = "aiperf"):
        self.gateway_url = gateway_url
        self.job_name = job_name
        self.logger = AIPerfLogger(self.__class__.__name__)

    def export_data(self, data: Dict[str, Any]) -> None:
        """Export metrics to Prometheus pushgateway."""
        self.logger.info(f"Exporting metrics to Prometheus at {self.gateway_url}")

        # Convert data to Prometheus format
        metrics = []
        for key, value in data.items():
            if isinstance(value, (int, float)):
                metric_name = key.replace(" ", "_").replace("-", "_").lower()
                metrics.append(f"aiperf_{metric_name} {value}")

        # In real implementation:
        # from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
        # registry = CollectorRegistry()
        # for metric in metrics:
        #     gauge = Gauge(metric_name, metric_description, registry=registry)
        #     gauge.set(value)
        # push_to_gateway(self.gateway_url, job=self.job_name, registry=registry)

        self.logger.info(f"Successfully exported {len(metrics)} metrics to Prometheus")
