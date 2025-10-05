# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
AIPerf Plugin System (AIP-001)

This module implements the AIPerf plugin architecture following the AIP-001 specification.

Plugin system features:
- Entry point based discovery (importlib.metadata)
- Lazy loading of plugins
- Type-safe plugin contracts
- Dependency injection support
- Zero-boilerplate authorship
- Minimal startup overhead

Supported plugin types (entry point groups):
- aiperf.metric - Performance metrics
- aiperf.endpoint - API format handlers
- aiperf.data_exporter - Data exporters
- aiperf.transport - Communication protocols
- aiperf.processor - Data processors
- aiperf.collector - Data collection

Example plugin registration in pyproject.toml:
    [project.entry-points."aiperf.metric"]
    my_metric = "my_plugin.my_metric:MyMetric"

See Also:
    - AIP-001 Specification: https://github.com/ai-dynamo/enhancements/pull/43
    - Developer's Guidebook: guidebook/chapter-47-extending-aiperf.md
"""

from aiperf.plugins.discovery import (
    PluginDiscovery,
    PluginLoader,
    PluginMetadata,
    discover_plugins,
    load_plugin,
)
from aiperf.plugins.protocols import (
    MetricPluginProtocol,
    EndpointPluginProtocol,
    DataExporterPluginProtocol,
    TransportPluginProtocol,
    ProcessorPluginProtocol,
    CollectorPluginProtocol,
)
from aiperf.plugins.registry import PluginRegistry

__all__ = [
    # Discovery
    "PluginDiscovery",
    "PluginLoader",
    "PluginMetadata",
    "discover_plugins",
    "load_plugin",
    # Protocols
    "MetricPluginProtocol",
    "EndpointPluginProtocol",
    "DataExporterPluginProtocol",
    "TransportPluginProtocol",
    "ProcessorPluginProtocol",
    "CollectorPluginProtocol",
    # Registry
    "PluginRegistry",
]
