# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Shared fixtures for testing AIPerf metrics.

"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pytest

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.models import (
    ParsedResponseRecord,
    RequestRecord,
    ResponseData,
)
from aiperf.post_processors.metric_record_processor import MetricRecordProcessor
from aiperf.post_processors.metric_results_processor import MetricResultsProcessor

logging.basicConfig(level=logging.DEBUG)


@dataclass
class Response:
    """Type-safe configuration for a response in test records."""

    perf_ns: int
    token_count: int = 1
    raw_text: list[str] = field(default_factory=list)
    parsed_text: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_response_data(self) -> ResponseData:
        """Convert to ResponseData object."""
        return ResponseData(
            perf_ns=self.perf_ns,
            token_count=self.token_count,
            raw_text=self.raw_text,
            parsed_text=self.parsed_text,
            metadata=self.metadata,
        )


@dataclass
class ParsedRecord:
    """Type-safe configuration for a complete test record."""

    request_start_time: int = 100
    worker_id: str = "worker_1"
    input_token_count: int | None = 5
    responses: list[Response] = field(default_factory=lambda: [Response(perf_ns=150)])
    # Request-specific fields
    conversation_id: str = "test-conversation"
    turn_index: int = 0
    model_name: str = "test-model"
    # Additional request kwargs (for things like recv_start_perf_ns)
    request_kwargs: dict[str, Any] = field(default_factory=dict)


class ParsedResponseRecordBuilder:
    """Builder class for creating ParsedResponseRecord instances with type-safe dataclasses.

    Type-safe API using dataclasses:

    # Simple single response
    record = builder.create_record_from_config(ParsedRecord(
        request_start_time=100,
        responses=[Response(perf_ns=150, token_count=1)]
    ))

    # Multiple responses
    record = builder.create_record_from_config(ParsedRecord(
        request_start_time=100,
        responses=[
            Response(perf_ns=120, token_count=1),
            Response(perf_ns=140, token_count=2)
        ]
    ))

    # Multiple records
    records = builder.create_records_from_configs([
        ParsedRecord(request_start_time=10, responses=[Response(perf_ns=15)]),
        ParsedRecord(request_start_time=20, responses=[Response(perf_ns=25)])
    ])

    # Convenience method for simple cases
    record = builder.simple_record(request_start_time=100, response_perf_ns=150)
    """

    def simple_record(
        self,
        request_start_time: int = 100,
        response_perf_ns: int | None = None,
        token_count: int = 1,
        worker_id: str = "worker_1",
        input_token_count: int | None = 5,
        **request_kwargs,
    ) -> ParsedResponseRecord:
        """Create a simple single-response record with type-safe arguments."""
        if response_perf_ns is None:
            response_perf_ns = request_start_time + 50

        response = Response(perf_ns=response_perf_ns, token_count=token_count)

        return self.create_record_from_config(
            ParsedRecord(
                request_start_time=request_start_time,
                worker_id=worker_id,
                input_token_count=input_token_count,
                responses=[response],
                request_kwargs=request_kwargs,
            )
        )

    def create_record_from_config(self, config: ParsedRecord) -> ParsedResponseRecord:
        """Create a ParsedResponseRecord from a type-safe ParsedRecord config."""
        # Convert Response objects to ResponseData
        response_objects = [resp.to_response_data() for resp in config.responses]

        # Calculate output token count
        if not response_objects:
            output_token_count = None
        else:
            output_token_count = sum(
                resp.token_count for resp in response_objects if resp.token_count
            )

        # Create request with all config fields
        request = RequestRecord(
            conversation_id=config.conversation_id,
            turn_index=config.turn_index,
            model_name=config.model_name,
            start_perf_ns=config.request_start_time,
            timestamp_ns=config.request_start_time,
            **config.request_kwargs,
        )

        return ParsedResponseRecord(
            worker_id=config.worker_id,
            request=request,
            responses=response_objects,
            input_token_count=config.input_token_count,
            output_token_count=output_token_count,
        )

    def create_records_from_configs(
        self, configs: list[ParsedRecord]
    ) -> list[ParsedResponseRecord]:
        """Create multiple ParsedResponseRecord instances from type-safe ParsedRecord configs."""
        return [self.create_record_from_config(config) for config in configs]


class BaseMetricTest(ABC):
    """Base class for metric tests that provides common functionality.

    This class handles the common patterns found in all metric tests:
    - Setting up processors
    - Processing records through the pipeline
    - Finding and validating metric results
    - Common assertion patterns

    Subclasses only need to provide:
    - endpoint_config: EndpointConfig for the test
    - metric_tag: The tag of the metric being tested
    - Custom test methods that call the helper methods
    """

    _logger = AIPerfLogger(__name__)

    @property
    @abstractmethod
    def endpoint_config(self) -> EndpointConfig:
        """Return the endpoint configuration for this metric test."""
        pass

    @property
    @abstractmethod
    def metric_tag(self) -> str:
        """Return the tag of the metric being tested."""
        pass

    def get_user_config(self) -> UserConfig:
        """Get the user config for testing."""
        return UserConfig(endpoint=self.endpoint_config)

    async def process_records_and_get_summary(
        self, records: list[ParsedResponseRecord]
    ) -> list[Any]:
        """Process records through the metric pipeline and return the summary."""
        user_config = self.get_user_config()
        record_processor = MetricRecordProcessor(user_config=user_config)
        results_processor = MetricResultsProcessor(user_config=user_config)

        for record in records:
            record_metrics = await record_processor.process_record(record=record)
            await results_processor.process_result(record_metrics)

        return await results_processor.summarize()

    async def process_single_record_and_get_summary(
        self, record: ParsedResponseRecord
    ) -> list[Any]:
        """Process a single record and return the summary."""
        return await self.process_records_and_get_summary([record])

    def find_metric_result(self, summary: list[Any]) -> Any:
        """Find the metric result in the summary by tag."""
        for result in summary:
            if result.tag == self.metric_tag:
                self._logger.trace(f"Found metric result: {result}")
                return result

        available_tags = [result.tag for result in summary]
        raise AssertionError(
            f"Metric '{self.metric_tag}' not found in summary. Available metrics: {available_tags}"
        )

    def assert_metric_value(
        self, summary: list[Any], expected_value: float, tolerance: float = 0.01
    ):
        """Assert that the metric has the expected average value."""
        result = self.find_metric_result(summary)
        if isinstance(expected_value, float) and isinstance(result.avg, float):
            assert abs(result.avg - expected_value) < tolerance, (
                f"Expected {self.metric_tag} avg to be {expected_value}, got {result.avg}"
            )
        else:
            assert result.avg == expected_value, (
                f"Expected {self.metric_tag} avg to be {expected_value}, got {result.avg}"
            )

    async def assert_record_processing_raises(
        self,
        record: ParsedResponseRecord,
        expected_error: type = ValueError,
        match: str | None = None,
    ):
        """Assert that processing a record raises the expected error."""
        user_config = self.get_user_config()
        record_processor = MetricRecordProcessor(user_config=user_config)

        if match:
            with pytest.raises(expected_error, match=match):
                await record_processor.process_record(record=record)
        else:
            with pytest.raises(expected_error):
                await record_processor.process_record(record=record)

    async def assert_invalid_record_raises(
        self, expected_error: type | tuple[type, ...] = (ValueError, AttributeError)
    ):
        """Assert that processing None/invalid record raises an error."""
        user_config = self.get_user_config()
        record_processor = MetricRecordProcessor(user_config=user_config)

        with pytest.raises(expected_error):
            await record_processor.process_record(record=None)


@pytest.fixture
def parsed_response_record_builder():
    """Fixture that provides a builder for creating ParsedResponseRecord instances."""
    return ParsedResponseRecordBuilder()
