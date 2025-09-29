# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Example demonstrating how to use the Dependency Injection Metric Registry.

This module shows various patterns for using the DI-based metric registry,
including custom services, metric composition, and advanced dependency injection patterns.
"""

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from dependency_injector import providers
from dependency_injector.wiring import Provide, inject

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums import MetricFlags, MetricType
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.types import MetricTagT
from aiperf.metrics import BaseRecordMetric, BaseDerivedMetric
from aiperf.metrics.dependency_injection_registry import (
    DIMetricRegistry,
    MetricContainer,
    inject_metric,
    inject_all_metrics,
)
from aiperf.metrics.metric_dicts import MetricRecordDict, MetricResultsDict

if TYPE_CHECKING:
    from aiperf.metrics.base_metric import BaseMetric

_logger = AIPerfLogger(__name__)


# Custom service that can be injected into metrics
class MetricCalculationService:
    """Service for complex metric calculations that can be shared across metrics."""

    def __init__(self, precision: int = 6):
        self.precision = precision
        _logger.info(f"MetricCalculationService initialized with precision={precision}")

    def calculate_percentile(self, values: list[float], percentile: float) -> float:
        """Calculate a percentile with the configured precision."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = (percentile / 100) * (len(sorted_values) - 1)

        if index.is_integer():
            result = sorted_values[int(index)]
        else:
            lower_index = int(index)
            upper_index = min(lower_index + 1, len(sorted_values) - 1)
            weight = index - lower_index
            result = sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight

        return round(result, self.precision)

    def calculate_moving_average(self, values: list[float], window_size: int) -> list[float]:
        """Calculate moving average with the configured precision."""
        if len(values) < window_size:
            return values

        moving_averages = []
        for i in range(len(values) - window_size + 1):
            window = values[i:i + window_size]
            avg = round(sum(window) / window_size, self.precision)
            moving_averages.append(avg)

        return moving_averages


class CacheService:
    """Caching service that can be injected into metrics for performance optimization."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: dict[str, any] = {}
        _logger.info(f"CacheService initialized with max_size={max_size}")

    def get(self, key: str) -> any:
        """Get a value from cache."""
        return self._cache.get(key)

    def set(self, key: str, value: any) -> None:
        """Set a value in cache with size management."""
        if len(self._cache) >= self.max_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[key] = value

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)


# Example custom metric that uses dependency injection
class EnhancedLatencyMetric(BaseRecordMetric[float]):
    """Enhanced latency metric that uses injected services for advanced calculations."""

    tag = "enhanced_latency"
    header = "Enhanced Request Latency"
    short_header = "Enh Latency"
    unit = "nanoseconds"
    display_order = 350
    flags = MetricFlags.NONE

    def __init__(self,
                 calculation_service: MetricCalculationService | None = None,
                 cache_service: CacheService | None = None):
        super().__init__()
        # Dependencies can be injected via constructor or set later
        self._calculation_service = calculation_service
        self._cache_service = cache_service
        self._latency_history: list[float] = []

    def _parse_record(self, record: ParsedResponseRecord, record_metrics: MetricRecordDict) -> float:
        """Parse record with enhanced calculation and caching."""
        request_ts = record.start_perf_ns
        final_response_ts = record.responses[-1].perf_ns

        if final_response_ts < request_ts:
            raise ValueError("Final response timestamp is less than request timestamp.")

        latency = float(final_response_ts - request_ts)

        # Use cache service if available
        if self._cache_service:
            cache_key = f"latency_{record.request_id}"
            cached_value = self._cache_service.get(cache_key)
            if cached_value is not None:
                return cached_value
            self._cache_service.set(cache_key, latency)

        # Store for moving average calculation
        self._latency_history.append(latency)
        if len(self._latency_history) > 100:  # Keep last 100 values
            self._latency_history.pop(0)

        return latency

    def get_percentile(self, percentile: float) -> float:
        """Get a percentile of recorded latencies."""
        if self._calculation_service and self._latency_history:
            return self._calculation_service.calculate_percentile(self._latency_history, percentile)
        return 0.0

    def get_moving_average(self, window_size: int = 10) -> list[float]:
        """Get moving average of latencies."""
        if self._calculation_service and self._latency_history:
            return self._calculation_service.calculate_moving_average(self._latency_history, window_size)
        return []


class CompositePerformanceMetric(BaseDerivedMetric[dict]):
    """Composite metric that aggregates multiple other metrics with dependency injection."""

    tag = "composite_performance"
    header = "Composite Performance Score"
    short_header = "Perf Score"
    unit = "score"
    display_order = 900
    flags = MetricFlags.LARGER_IS_BETTER
    required_metrics = {"request_latency", "output_token_throughput"}

    def __init__(self, calculation_service: MetricCalculationService | None = None):
        super().__init__()
        self._calculation_service = calculation_service

    def _derive_value(self, metric_results: MetricResultsDict) -> dict:
        """Derive a composite performance score from multiple metrics."""
        latency = metric_results.get("request_latency", 0)
        throughput = metric_results.get("output_token_throughput", 0)

        # Simple composite scoring algorithm
        # Lower latency is better, higher throughput is better
        latency_score = max(0, 100 - (latency / 1000000))  # Convert ns to ms for scoring
        throughput_score = min(100, throughput * 10)  # Scale throughput

        composite_score = (latency_score + throughput_score) / 2

        if self._calculation_service:
            composite_score = round(composite_score, self._calculation_service.precision)

        return {
            "composite_score": composite_score,
            "latency_score": latency_score,
            "throughput_score": throughput_score,
            "components": {
                "latency_ms": latency / 1000000,
                "throughput_tps": throughput
            }
        }


class MetricAnalysisService:
    """Service that demonstrates various ways to use the DI metric registry."""

    @inject
    def __init__(self,
                 enhanced_latency: "EnhancedLatencyMetric" = Provide["container.enhanced_latency"],
                 composite_perf: "CompositePerformanceMetric" = Provide["container.composite_performance"]):
        self.enhanced_latency = enhanced_latency
        self.composite_perf = composite_perf
        _logger.info("MetricAnalysisService initialized with injected metrics")

    def analyze_performance(self, records: list[ParsedResponseRecord]) -> dict:
        """Analyze performance using injected metrics."""
        results = {}

        # Process records with enhanced latency metric
        latencies = []
        for record in records:
            try:
                latency = self.enhanced_latency._parse_record(record, {})
                latencies.append(latency)
            except Exception as e:
                _logger.warning(f"Failed to process record {record.request_id}: {e}")

        results["latency_stats"] = {
            "count": len(latencies),
            "avg": sum(latencies) / len(latencies) if latencies else 0,
            "p95": self.enhanced_latency.get_percentile(95),
            "p99": self.enhanced_latency.get_percentile(99),
            "moving_avg": self.enhanced_latency.get_moving_average(5)
        }

        return results

    @inject_all_metrics()
    def get_all_metric_info(self, metrics: dict[MetricTagT, "BaseMetric"]) -> dict:
        """Get information about all available metrics."""
        return {
            tag: {
                "class": metric.__class__.__name__,
                "header": metric.header,
                "unit": str(metric.unit),
                "flags": str(metric.flags),
                "type": str(metric.type)
            }
            for tag, metric in metrics.items()
        }


class DIMetricRegistryExample:
    """Main example class demonstrating the DI metric registry usage."""

    def __init__(self):
        self.registry = DIMetricRegistry
        self._setup_custom_dependencies()

    def _setup_custom_dependencies(self):
        """Setup custom services and dependencies."""
        # Register custom services
        self.registry.register_singleton(
            "calculation_service",
            MetricCalculationService,
            precision=4
        )

        self.registry.register_singleton(
            "cache_service",
            CacheService,
            max_size=500
        )

        # Register custom metrics with dependency injection
        self.registry.register_metric(EnhancedLatencyMetric)
        self.registry.register_metric(CompositePerformanceMetric)

        # Register the analysis service
        self.registry.register_singleton(
            "analysis_service",
            MetricAnalysisService
        )

        _logger.info("Custom dependencies and metrics registered")

    def demonstrate_basic_usage(self):
        """Demonstrate basic metric registry usage."""
        _logger.info("=== Basic Usage Demo ===")

        # Get all available metric tags
        all_tags = self.registry.all_tags()
        _logger.info(f"Available metrics: {all_tags}")

        # Get specific metric instances
        try:
            enhanced_latency = self.registry.get_instance("enhanced_latency")
            _logger.info(f"Got enhanced latency metric: {enhanced_latency}")

            # Get multiple metrics at once
            metric_instances = self.registry.get_instances(["enhanced_latency", "composite_performance"])
            _logger.info(f"Got multiple metrics: {list(metric_instances.keys())}")

        except Exception as e:
            _logger.error(f"Error getting metric instances: {e}")

    def demonstrate_dependency_injection(self):
        """Demonstrate advanced dependency injection patterns."""
        _logger.info("=== Dependency Injection Demo ===")

        # Get services from container
        calculation_service = self.registry.container.calculation_service()
        cache_service = self.registry.container.cache_service()

        _logger.info(f"Calculation service precision: {calculation_service.precision}")
        _logger.info(f"Cache service max size: {cache_service.max_size}")

        # Test calculation service
        test_values = [10.5, 20.3, 15.7, 25.1, 18.9]
        p95 = calculation_service.calculate_percentile(test_values, 95)
        _logger.info(f"95th percentile of {test_values}: {p95}")

        # Test cache service
        cache_service.set("test_key", "test_value")
        cached_value = cache_service.get("test_key")
        _logger.info(f"Cached value: {cached_value}")

    def demonstrate_metric_analysis(self):
        """Demonstrate the metric analysis service."""
        _logger.info("=== Metric Analysis Demo ===")

        try:
            analysis_service = self.registry.container.analysis_service()

            # Get all metric info
            metric_info = analysis_service.get_all_metric_info()
            _logger.info(f"Available metrics info: {len(metric_info)} metrics")

            for tag, info in metric_info.items():
                _logger.info(f"  {tag}: {info['header']} ({info['type']})")

        except Exception as e:
            _logger.error(f"Error in metric analysis demo: {e}")

    def demonstrate_dependency_validation(self):
        """Demonstrate dependency validation features."""
        _logger.info("=== Dependency Validation Demo ===")

        try:
            # Validate all dependencies
            self.registry.validate_dependencies()
            _logger.info("All dependencies validated successfully")

            # Show dependency graph
            dep_graph = self.registry.get_dependency_graph()
            _logger.info("Dependency graph:")
            for metric, deps in dep_graph.items():
                if deps:
                    _logger.info(f"  {metric} depends on: {deps}")

            # Show resolution order
            resolution_order = self.registry.create_dependency_order()
            _logger.info(f"Metric resolution order: {resolution_order}")

        except Exception as e:
            _logger.error(f"Dependency validation error: {e}")

    async def demonstrate_async_usage(self):
        """Demonstrate async usage patterns."""
        _logger.info("=== Async Usage Demo ===")

        @asynccontextmanager
        async def metric_scope():
            """Async context manager for metric operations."""
            try:
                # Setup async resources
                _logger.info("Setting up async metric scope")
                yield
            finally:
                # Cleanup
                cache_service = self.registry.container.cache_service()
                cache_service.clear()
                _logger.info("Cleaned up async metric scope")

        async with metric_scope():
            # Simulate async metric processing
            await asyncio.sleep(0.1)
            enhanced_latency = self.registry.get_instance("enhanced_latency")
            _logger.info(f"Processed metrics asynchronously: {enhanced_latency.tag}")

    def run_all_demos(self):
        """Run all demonstration methods."""
        _logger.info("Starting DI Metric Registry demonstrations...")

        self.demonstrate_basic_usage()
        self.demonstrate_dependency_injection()
        self.demonstrate_metric_analysis()
        self.demonstrate_dependency_validation()

        # Run async demo
        asyncio.run(self.demonstrate_async_usage())

        _logger.info("All demonstrations completed!")


# Convenience function for easy usage
def create_example_with_custom_config() -> DIMetricRegistryExample:
    """Create an example instance with custom configuration."""
    example = DIMetricRegistryExample()

    # Add additional custom configuration
    example.registry.container.config.from_dict({
        "metrics": {
            "precision": 6,
            "cache_size": 1000,
            "enable_advanced_features": True
        }
    })

    return example


if __name__ == "__main__":
    # Run the example
    example = create_example_with_custom_config()
    example.run_all_demos()
