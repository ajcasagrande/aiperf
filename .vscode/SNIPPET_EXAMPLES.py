"""
AIPerf Snippet Examples

This file demonstrates the output of all major AIPerf snippets to help users
understand what each snippet generates.

DO NOT RUN THIS FILE - it's for reference only.
"""

# ============================================================================
# EXAMPLE 1: Record Metric (metric-record)
# ============================================================================
# Type: metric-record → Tab → Fill placeholders

from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.common.exceptions import NoMetricValue
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict


class OutputToInputRatioMetric(BaseRecordMetric[float]):
    """
    Compute the ratio of output tokens to input tokens.

    This metric is computed for each individual request independently.

    Formula:
        ratio = output_tokens / input_tokens
    """

    # Required: Unique identifier for this metric
    tag = "output_to_input_ratio"

    # Required: Display name shown in results
    header = "Output To Input Ratio"

    # Optional: Short name for compact displays (dashboards)
    short_header = "O/I Ratio"

    # Optional: Hide unit in short header
    short_header_hide_unit = False

    # Required: Unit of measurement
    unit = GenericMetricUnit.RATIO

    # Optional: Control display order (lower = earlier)
    display_order = 500

    # Required: Flags controlling when/how metric is computed
    flags = MetricFlags.LARGER_IS_BETTER | MetricFlags.PRODUCES_TOKENS_ONLY

    # Optional: Dependencies on other metrics
    required_metrics = None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> float:
        """
        Compute the metric value for a single record.

        Args:
            record: Parsed response record with request/response data
            record_metrics: Previously computed metrics (for dependencies)

        Returns:
            The computed metric value

        Raises:
            NoMetricValue: If metric cannot be computed for this record
        """
        # Check if required data is available
        if record.input_token_count is None or record.input_token_count == 0:
            raise NoMetricValue("Input token count not available or zero")

        if record.output_token_count is None:
            raise NoMetricValue("Output token count not available")

        # Compute the metric value
        ratio = record.output_token_count / record.input_token_count

        return ratio


# ============================================================================
# EXAMPLE 2: Aggregate Counter Metric (metric-counter)
# ============================================================================
# Type: metric-counter → Tab → Fill placeholders

from aiperf.metrics.base_aggregate_counter_metric import BaseAggregateCounterMetric


class ErrorRequestCountMetric(BaseAggregateCounterMetric[int]):
    """
    Count the number of requests that resulted in errors.

    This is a simple counter that increments for each error request.

    Formula:
        Count = Sum(1 for each error request)
    """

    tag = "error_request_count"
    header = "Error Request Count"
    short_header = "Errors"
    short_header_hide_unit = True
    unit = GenericMetricUnit.REQUESTS
    display_order = 1000
    flags = MetricFlags.SMALLER_IS_BETTER
    required_metrics = None


# ============================================================================
# EXAMPLE 3: Derived Metric (metric-derived)
# ============================================================================
# Type: metric-derived → Tab → Fill placeholders

from aiperf.common.enums import MetricOverTimeUnit
from aiperf.metrics import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict
from aiperf.metrics.types.benchmark_duration_metric import BenchmarkDurationMetric
from aiperf.metrics.types.request_count_metric import RequestCountMetric


class RequestThroughputMetric(BaseDerivedMetric[float]):
    """
    Compute requests per second throughput.

    This metric is computed from other metrics after all records are processed.

    Formula:
        throughput = request_count / benchmark_duration_seconds
    """

    # Required: Unique identifier
    tag = "request_throughput"

    # Required: Display name
    header = "Request Throughput"

    # Optional: Short name
    short_header = "Throughput"

    # Optional: Hide unit in short header
    short_header_hide_unit = False

    # Required: Unit
    unit = MetricOverTimeUnit.REQUESTS_PER_SECOND

    # Optional: Display order
    display_order = 1000

    # Required: Flags
    flags = MetricFlags.LARGER_IS_BETTER

    # Required: Dependencies (metrics this depends on)
    required_metrics = {
        RequestCountMetric.tag,
        BenchmarkDurationMetric.tag,
    }

    def _derive_value(self, metric_results: MetricResultsDict) -> float:
        """
        Compute the metric value from other metrics.

        Args:
            metric_results: Dictionary containing all computed metrics

        Returns:
            The derived metric value

        Raises:
            NoMetricValue: If required metrics are missing or invalid
        """
        # Get dependency metrics
        request_count = metric_results.get_or_raise(RequestCountMetric.tag)
        duration_seconds = metric_results.get_converted_or_raise(
            BenchmarkDurationMetric,
            unit.time_unit,
        )

        # Validate values
        if duration_seconds == 0:
            raise NoMetricValue("Cannot divide by zero duration")

        # Compute derived value
        throughput = request_count / duration_seconds

        return throughput


# ============================================================================
# EXAMPLE 4: Dataset Loader (dataset-loader)
# ============================================================================
# Type: dataset-loader → Tab → Fill placeholders

import uuid
from collections import defaultdict

from aiperf.common.enums import CustomDatasetType, MediaType
from aiperf.common.factories import CustomDatasetFactory
from aiperf.common.models import Conversation, Turn
from aiperf.dataset.loader.mixins import MediaConversionMixin
from aiperf.dataset.loader.models import SingleTurn


@CustomDatasetFactory.register(CustomDatasetType.CUSTOM_JSONL)
class CustomJSONLDatasetLoader(MediaConversionMixin):
    """
    Load custom JSONL format dataset.

    Expected Format:
    ```json
    {"text": "What is AI?", "timestamp": 0}
    {"text": "Explain ML", "timestamp": 1000}
    ```
    """

    def __init__(self, filename: str, encoding: str = "utf-8"):
        """
        Initialize the dataset loader.

        Args:
            filename: Path to the dataset file
            encoding: File encoding (default: utf-8)
        """
        self.filename = filename
        self.encoding = encoding

    def load_dataset(self) -> dict[str, list[SingleTurn]]:
        """
        Load dataset from file.

        Returns:
            Dictionary mapping session_id to list of turn data
        """
        data: dict[str, list[SingleTurn]] = defaultdict(list)

        with open(self.filename) as f:
            for line in f:
                if (line := line.strip()) == "":
                    continue  # Skip empty lines

                # Parse the line
                turn_data = SingleTurn.model_validate_json(line)

                # Generate or extract session ID
                session_id = str(uuid.uuid4())

                data[session_id].append(turn_data)

        return data

    def convert_to_conversations(
        self, data: dict[str, list[SingleTurn]]
    ) -> list[Conversation]:
        """
        Convert loaded data to conversation objects.

        Args:
            data: Dictionary mapping session_id to list of turns

        Returns:
            List of conversations ready for benchmarking
        """
        conversations = []

        for session_id, turns in data.items():
            conversation = Conversation(session_id=session_id)

            for turn in turns:
                # Convert media fields to media objects
                media = self.convert_to_media_objects(turn)

                conversation.turns.append(
                    Turn(
                        texts=media[MediaType.TEXT],
                        images=media[MediaType.IMAGE],
                        audios=media[MediaType.AUDIO],
                        timestamp=turn.timestamp,
                        delay=turn.delay,
                        role=turn.role,
                    )
                )

            conversations.append(conversation)

        return conversations


# ============================================================================
# EXAMPLE 5: Service (service)
# ============================================================================
# Type: service → Tab → Fill placeholders

from aiperf.common.base_service import BaseService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import MessageType, ServiceType
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import on_message, on_start, on_stop
from aiperf.common.messages import StatusMessage


@ServiceFactory.register(ServiceType.CUSTOM_MONITORING)
class MonitoringService(BaseService):
    """
    Service for monitoring system health and performance.

    Responsibilities:
    - Tracks system metrics
    - Monitors service health
    - Sends alerts on issues
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
        **kwargs,
    ) -> None:
        """
        Initialize the service.

        Args:
            service_config: Service-level configuration
            user_config: User-provided configuration
            service_id: Optional custom service ID
            **kwargs: Additional arguments
        """
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            **kwargs,
        )

        # Initialize service state
        self._health_status = {}
        self._metrics_buffer = []

        self.info(f"Initialized {self.__class__.__name__}")

    @on_start
    async def _on_start(self) -> None:
        """Initialize monitoring when service starts"""
        self.info("Starting monitoring service...")
        self._health_status = {}

    @on_stop
    async def _on_stop(self) -> None:
        """Clean up monitoring when service stops"""
        self.info("Stopping monitoring service...")
        self._health_status.clear()

    @on_message(MessageType.STATUS)
    async def _on_status(self, message: StatusMessage) -> None:
        """
        Handle status messages from services.

        Args:
            message: The status message
        """
        self.debug(f"Received status from {message.service_id}")

        # Update health status
        self._health_status[message.service_id] = message.status


# ============================================================================
# EXAMPLE 6: Unit Test (test-unit)
# ============================================================================
# Type: test-unit → Tab → Fill placeholders

import pytest
from pytest import approx

from aiperf.metrics.types.output_to_input_ratio_metric import OutputToInputRatioMetric


class TestOutputToInputRatioMetric:
    """Test suite for OutputToInputRatioMetric"""

    def test_basic_ratio_calculation(self):
        """Test that basic ratio calculation works correctly"""
        # Arrange
        metric = OutputToInputRatioMetric()
        record = create_record(
            input_token_count=10,
            output_token_count=20,
        )
        expected = 2.0

        # Act
        result = metric._parse_record(record, {})

        # Assert
        assert result == expected

    @pytest.mark.parametrize(
        "input_tokens,output_tokens,expected",
        [
            (10, 20, 2.0),
            (5, 10, 2.0),
            (100, 50, 0.5),
        ],
    )
    def test_various_ratios(self, input_tokens, output_tokens, expected):
        """Test ratio calculation with multiple inputs"""
        # Arrange
        metric = OutputToInputRatioMetric()
        record = create_record(
            input_token_count=input_tokens,
            output_token_count=output_tokens,
        )

        # Act
        result = metric._parse_record(record, {})

        # Assert
        assert result == approx(expected)

    def test_zero_input_tokens(self):
        """Test error handling for zero input tokens"""
        # Arrange
        metric = OutputToInputRatioMetric()
        record = create_record(
            input_token_count=0,
            output_token_count=20,
        )

        # Act & Assert
        with pytest.raises(
            NoMetricValue, match="Input token count not available or zero"
        ):
            metric._parse_record(record, {})


# ============================================================================
# EXAMPLE 7: Metric Test (test-metric)
# ============================================================================
# Type: test-metric → Tab → Fill placeholders

from tests.metrics.conftest import create_record, run_simple_metrics_pipeline


class TestRequestThroughputMetric:
    """Test suite for RequestThroughputMetric"""

    def test_no_records(self):
        """Test metric with no records"""
        metric_results = run_simple_metrics_pipeline(
            [],
            RequestThroughputMetric.tag,
        )
        assert RequestThroughputMetric.tag not in metric_results

    def test_single_record(self):
        """Test metric with a single record"""
        # Arrange
        record = create_record(
            request_start_ns=0,
            response_end_ns=1_000_000_000,  # 1 second
        )

        # Act
        metric_results = run_simple_metrics_pipeline(
            [record],
            RequestThroughputMetric.tag,
        )

        # Assert
        expected = 1.0  # 1 request / 1 second
        assert metric_results[RequestThroughputMetric.tag] == approx(expected)

    @pytest.mark.parametrize(
        "num_records",
        [1, 3, 10, 100, 1_000],
    )
    def test_multiple_records(self, num_records):
        """Test metric with multiple records"""
        # Arrange
        records = [
            create_record(
                start_ns=100 * i,
                duration_ns=1_000_000_000,  # 1 second each
            )
            for i in range(num_records)
        ]

        # Act
        metric_results = run_simple_metrics_pipeline(
            records,
            RequestThroughputMetric.tag,
        )

        # Assert - throughput should be num_records / total_duration
        expected = num_records / (num_records * 1.0)  # Parallel requests
        assert metric_results[RequestThroughputMetric.tag] == approx(expected)

    def test_missing_data(self):
        """Test metric behavior when required data is missing"""
        # Arrange
        record = create_record(
            request_start_ns=None,  # Missing required data
        )

        # Act
        metric_results = run_simple_metrics_pipeline(
            [record],
            RequestThroughputMetric.tag,
        )

        # Assert - metric should not be present
        assert RequestThroughputMetric.tag not in metric_results


# ============================================================================
# EXAMPLE 8: Config Class (config)
# ============================================================================
# Type: config → Tab → Fill placeholders

from typing import Annotated

from pydantic import Field, model_validator
from typing_extensions import Self

from aiperf.common.config.base_config import BaseConfig
from aiperf.common.config.cli_parameter import CLIParameter
from aiperf.common.config.config_defaults import MonitoringDefaults
from aiperf.common.config.groups import Groups


class MonitoringConfig(BaseConfig):
    """
    Configuration for system monitoring.

    This configuration controls health monitoring and alerting behavior.
    """

    _CLI_GROUP = Groups.ADVANCED

    @model_validator(mode="after")
    def validate_thresholds(self) -> Self:
        """Validate that warning threshold is less than critical threshold"""
        if self.warning_threshold > self.critical_threshold:
            raise ValueError("Warning threshold must be <= critical threshold")
        return self

    warning_threshold: Annotated[
        float,
        Field(
            description="Percentage threshold for warning alerts",
        ),
        CLIParameter(
            name=(
                "--warning-threshold",
                "--warn",  # Optional alias
            ),
            group=_CLI_GROUP,
        ),
    ] = MonitoringDefaults.WARNING_THRESHOLD

    critical_threshold: Annotated[
        float,
        Field(
            description="Percentage threshold for critical alerts",
        ),
        CLIParameter(
            name=("--critical-threshold",),
            group=_CLI_GROUP,
        ),
    ] = MonitoringDefaults.CRITICAL_THRESHOLD

    check_interval: Annotated[
        float,
        Field(
            description="Interval in seconds between health checks",
        ),
        CLIParameter(
            name=("--check-interval",),
            group=_CLI_GROUP,
        ),
    ] = MonitoringDefaults.CHECK_INTERVAL


# ============================================================================
# EXAMPLE 9: Mixin (mixin)
# ============================================================================
# Type: mixin → Tab → Fill placeholders

from aiperf.common.config import ServiceConfig
from aiperf.common.enums import MessageType
from aiperf.common.hooks import AIPerfHook, on_message, provides_hooks
from aiperf.common.messages import MetricsMessage
from aiperf.common.mixins.base_mixin import BaseMixin


@provides_hooks(AIPerfHook.ON_REALTIME_METRICS)
class MetricsTrackingMixin(BaseMixin):
    """
    Mixin for tracking real-time metrics.

    This mixin adds the following capabilities:
    - Collects metrics from services
    - Aggregates metrics in real-time
    - Provides hooks for metric consumers

    Hooks Provided:
    - ON_REALTIME_METRICS: Triggered when new metrics are available
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        **kwargs,
    ):
        """
        Initialize the mixin.

        Args:
            service_config: Service configuration
            **kwargs: Additional arguments
        """
        super().__init__(service_config=service_config, **kwargs)

        # Initialize mixin state
        self._metrics_buffer = []
        self._last_update_time = None

    @on_message(MessageType.METRICS)
    async def _on_metrics(self, message: MetricsMessage) -> None:
        """
        Handle metrics messages and trigger hook.

        Args:
            message: The metrics message
        """
        # Process the metrics
        processed_metrics = self._process_metrics(message)

        # Trigger hook for consumers
        await self.run_hooks(
            AIPerfHook.ON_REALTIME_METRICS,
            metrics=processed_metrics,
        )

    def _process_metrics(self, message: MetricsMessage) -> dict:
        """Process and aggregate metrics"""
        # Implementation details
        return {"processed": True, "count": len(message.metrics)}


# ============================================================================
# EXAMPLE 10: Lifecycle Hooks
# ============================================================================

# Example: on_start hook (hook-start)
from aiperf.common.hooks import on_start


@on_start
async def _initialize_resources(self) -> None:
    """Initialize resources when service starts"""
    self.info("Starting resource initialization...")
    self._connection_pool = await create_connection_pool()


# Example: on_stop hook (hook-stop)
from aiperf.common.hooks import on_stop


@on_stop
async def _cleanup_resources(self) -> None:
    """Clean up resources when service stops"""
    self.info("Cleaning up resources...")
    await self._connection_pool.close()


# Example: background_task hook (background-task)
from aiperf.common.hooks import background_task


@background_task(
    interval=5.0,  # seconds between executions
    immediate=True,  # run immediately on start
    stop_on_error=False,  # continue on error
)
async def _periodic_health_check(self) -> None:
    """
    Periodic health check task.

    This task runs every 5.0 second(s) while the service is running.
    """
    self.debug("Running health check")
    health_status = await self._check_system_health()
    await self._publish_health_status(health_status)


# ============================================================================
# EXAMPLE 11: Quick Utilities
# ============================================================================

# Example: SPDX header (spdx)
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


# Example: Logger (logger)
from aiperf.common.aiperf_logger import AIPerfLogger

_logger = AIPerfLogger(__name__)


# Example: Comprehensive docstring (docstring)
def calculate_throughput(requests: int, duration: float) -> float:
    """
    Calculate requests per second throughput.

    This function computes the throughput by dividing the total number of
    requests by the duration in seconds.

    Args:
        requests: Total number of requests processed
        duration: Time duration in seconds

    Returns:
        Throughput in requests per second

    Raises:
        ValueError: When duration is zero or negative

    Example:
        ```python
        >>> calculate_throughput(100, 10.0)
        10.0
        ```
    """
    if duration <= 0:
        raise ValueError("Duration must be positive")
    return requests / duration


# ============================================================================
# USAGE SUMMARY
# ============================================================================
"""
To use these snippets in VS Code:

1. Open a Python file in the aiperf project
2. Type one of the prefixes (e.g., "metric-record")
3. Press Tab to insert the snippet
4. Use Tab to navigate through placeholders
5. Press Shift+Tab to go back
6. For choice lists, use arrow keys and Enter
7. Edit the generated code as needed

Common Prefixes:
- metric-record       → Record metric
- metric-aggregate    → Aggregate metric
- metric-derived      → Derived metric
- metric-counter      → Counter metric
- dataset-loader      → Dataset loader
- service             → Service
- test-unit           → Unit test
- test-metric         → Metric test
- config              → Config class
- mixin               → Mixin class
- hook-start          → on_start hook
- hook-stop           → on_stop hook
- background-task     → Background task
- spdx                → SPDX header
- logger              → Logger instance
- docstring           → Docstring

For more information, see:
- .vscode/SNIPPETS.md                    → Complete guide
- .vscode/SNIPPETS_QUICK_REFERENCE.md   → Quick reference
"""
