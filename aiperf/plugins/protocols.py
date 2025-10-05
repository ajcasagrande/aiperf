# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Plugin Protocols (AIP-001)

Defines type-safe contracts for all AIPerf plugin types.
All protocols use structural subtyping (Protocol) for flexibility.
"""

from typing import Any, Dict, Optional, Protocol, runtime_checkable
from pathlib import Path

from aiperf.common.models import ParsedResponseRecord, ProfileResults
from aiperf.metrics.metric_dicts import MetricRecordDict, MetricResultsDict


@runtime_checkable
class PluginMetadataProtocol(Protocol):
    """
    Protocol for plugin metadata.

    All plugins should provide a plugin_metadata() function.
    """

    @staticmethod
    def plugin_metadata() -> Dict[str, Any]:
        """
        Return plugin metadata for discovery and validation.

        Returns:
            Dict with keys:
                - name: Plugin identifier
                - display_name: Human-readable name
                - version: Plugin version
                - plugin_type: Plugin type identifier
                - aip_version: AIP specification version ('001')
                - author: Plugin author (optional)
                - license: Plugin license (optional)
                - requires: List of required dependencies (optional)
        """
        ...


@runtime_checkable
class MetricPluginProtocol(Protocol):
    """
    Protocol for metric plugins (aiperf.metric).

    Metric plugins extend AIPerf's metrics system with custom calculations.

    Example:
        >>> class MyMetric:
        ...     tag = "my_metric"
        ...     header = "My Metric"
        ...     def _parse_record(self, record, record_metrics):
        ...         return compute_value(record)
        ...     @staticmethod
        ...     def plugin_metadata():
        ...         return {"name": "my_metric", "aip_version": "001"}
    """

    # Required class attributes
    tag: str
    header: str
    unit: Any
    flags: Any

    # Optional class attributes
    short_header: Optional[str]
    display_unit: Optional[Any]
    display_order: Optional[int]
    required_metrics: Optional[set]

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> Any:
        """Compute metric value for a record."""
        ...


@runtime_checkable
class EndpointPluginProtocol(Protocol):
    """
    Protocol for endpoint plugins (aiperf.endpoint).

    Endpoint plugins add support for new API formats and protocols.

    Example:
        >>> class CustomEndpoint:
        ...     @staticmethod
        ...     def endpoint_metadata():
        ...         return {"api_version": "v1", "supports_streaming": True}
        ...     async def send_request(self, endpoint_info, payload):
        ...         return await send_to_api(endpoint_info, payload)
    """

    @staticmethod
    def endpoint_metadata() -> Dict[str, Any]:
        """
        Return endpoint metadata.

        Returns:
            Dict with keys:
                - api_version: API version supported
                - supports_streaming: Boolean
                - supported_content_types: List of content types
        """
        ...

    async def send_request(
        self,
        endpoint_info: Any,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send request to endpoint.

        Args:
            endpoint_info: Endpoint configuration
            payload: Request payload

        Returns:
            Response data
        """
        ...


@runtime_checkable
class DataExporterPluginProtocol(Protocol):
    """
    Protocol for data exporter plugins (aiperf.data_exporter).

    Data exporter plugins add new export formats for benchmark results.

    Example:
        >>> class ParquetExporter:
        ...     def __init__(self, output_dir, config):
        ...         self.output_dir = output_dir
        ...     async def export(self, results):
        ...         # Export to parquet
        ...         return output_path
    """

    def __init__(self, output_dir: Path, config: Dict[str, Any]):
        """
        Initialize exporter.

        Args:
            output_dir: Directory for export files
            config: Exporter configuration
        """
        ...

    async def export(self, results: ProfileResults) -> Path:
        """
        Export benchmark results.

        Args:
            results: Benchmark results to export

        Returns:
            Path to exported file
        """
        ...

    @staticmethod
    def get_export_info() -> Dict[str, Any]:
        """
        Return export format metadata.

        Returns:
            Dict with keys:
                - format: Format identifier
                - display_name: Human-readable name
                - file_extension: File extension
                - description: Format description
        """
        ...


@runtime_checkable
class TransportPluginProtocol(Protocol):
    """
    Protocol for transport plugins (aiperf.transport).

    Transport plugins add new communication protocols beyond HTTP.

    Example:
        >>> class gRPCTransport:
        ...     async def connect(self, endpoint):
        ...         # Establish connection
        ...         pass
        ...     async def send(self, request):
        ...         # Send request
        ...         return response
    """

    async def connect(self, endpoint: str, **kwargs) -> None:
        """
        Establish connection to endpoint.

        Args:
            endpoint: Endpoint URL or identifier
            **kwargs: Additional connection parameters
        """
        ...

    async def send(self, request: Any) -> Any:
        """
        Send request via transport.

        Args:
            request: Request to send

        Returns:
            Response data
        """
        ...

    async def close(self) -> None:
        """Close connection."""
        ...


@runtime_checkable
class ProcessorPluginProtocol(Protocol):
    """
    Protocol for processor plugins (aiperf.processor).

    Processor plugins add custom data processing capabilities.

    Example:
        >>> class TokenNormalizer:
        ...     def process(self, data):
        ...         # Normalize tokens
        ...         return normalized_data
    """

    def process(self, data: Any) -> Any:
        """
        Process data.

        Args:
            data: Input data

        Returns:
            Processed data
        """
        ...


@runtime_checkable
class CollectorPluginProtocol(Protocol):
    """
    Protocol for collector plugins (aiperf.collector).

    Collector plugins add data collection integrations (Prometheus, etc.).

    Example:
        >>> class PrometheusCollector:
        ...     def collect(self, metrics):
        ...         # Push to Prometheus
        ...         pass
    """

    def collect(self, metrics: Dict[str, Any]) -> None:
        """
        Collect and send metrics.

        Args:
            metrics: Metrics data to collect
        """
        ...

    async def flush(self) -> None:
        """Flush buffered metrics."""
        ...
