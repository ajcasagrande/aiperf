# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Shared fixtures for testing AIPerf metrics.

"""

import logging
from abc import ABC, abstractmethod
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


class ParsedResponseRecordBuilder:
    """Builder class for creating ParsedResponseRecord instances with flexible configuration.

    Supports building single or multiple ParsedResponseRecord instances with custom
    requests and responses for comprehensive testing scenarios.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset the builder to default values."""
        self._records: list[dict[str, Any]] = []  # List of record configurations
        self._current_record: dict[str, Any] = self._new_record_config()
        return self

    def _new_record_config(self):
        """Create a new record configuration with default values."""
        return {
            "worker_id": "worker_1",
            "request_start_perf_ns": 100,
            "request_kwargs": {},
            "responses": [],
            "input_token_count": None,  # Will use default if not set
        }

    def with_worker_id(self, worker_id: str):
        """Set the worker ID for the current record."""
        self._current_record["worker_id"] = worker_id
        return self

    def with_request_start_time(self, timestamp_ns: int):
        """Set the request start time for the current record."""
        self._current_record["request_start_perf_ns"] = timestamp_ns
        self._current_record["request_kwargs"]["timestamp_ns"] = timestamp_ns
        return self

    def with_request_kwargs(self, **kwargs):
        """Add additional kwargs to the RequestRecord for the current record."""
        self._current_record["request_kwargs"].update(kwargs)
        return self

    def with_input_token_count(self, count: int | None):
        """Set the input token count for the current record."""
        self._current_record["input_token_count"] = count
        return self

    def add_response(
        self,
        perf_ns: int,
        raw_text: list[str] = None,
        parsed_text: list[str] = None,
        **kwargs,
    ):
        if raw_text is None:
            raw_text = []
        if parsed_text is None:
            parsed_text = []

        # Ensure token_count defaults to 1 if not provided
        if "token_count" not in kwargs:
            kwargs["token_count"] = 1

        response_data = ResponseData(
            perf_ns=perf_ns, raw_text=raw_text, parsed_text=parsed_text, **kwargs
        )
        self._current_record["responses"].append(response_data)
        return self

    def add_responses(self, *response_configs):
        """Add multiple responses to the current record. Each config should be a dict with response parameters."""
        for config in response_configs:
            self.add_response(**config)
        return self

    def new_record(self):
        """Finish the current record and start a new one. Returns self for chaining."""
        self._records.append(self._current_record.copy())
        self._current_record = self._new_record_config()
        return self

    def add_request(
        self,
        worker_id: str | None = None,
        start_perf_ns: int | None = None,
        **request_kwargs,
    ):
        """Add a new request record. Automatically starts a new record."""
        self.new_record()

        if worker_id is not None:
            self.with_worker_id(worker_id)
        if start_perf_ns is not None:
            self.with_request_start_time(start_perf_ns)
        if request_kwargs:
            self.with_request_kwargs(**request_kwargs)

        return self

    def build(self) -> ParsedResponseRecord:
        """Build and return a single ParsedResponseRecord (for backward compatibility)."""
        records = self.build_all()
        return records[0]

    def build_all(self) -> list[ParsedResponseRecord]:
        """Build and return all configured ParsedResponseRecord instances."""
        # Add the current record if it has content
        all_records = self._records.copy()
        all_records.append(self._current_record)

        parsed_records = []
        for record_config in all_records:
            request = RequestRecord(
                conversation_id="test-conversation",
                turn_index=0,
                model_name="test-model",
                start_perf_ns=record_config["request_start_perf_ns"],
                **record_config["request_kwargs"],
            )

            # Calculate token counts automatically if not already set
            output_token_count = (
                sum(
                    response.token_count
                    for response in record_config["responses"]
                    if hasattr(response, "token_count")
                    and response.token_count is not None
                )
                if record_config["responses"]
                else None
            )

            # Use configured input token count, or default to 5 if none set
            # If explicitly set to None, keep it None for testing missing scenarios
            if (
                "input_token_count" in record_config
                and record_config["input_token_count"] is None
            ):
                input_token_count = None
            else:
                input_token_count = (
                    record_config["input_token_count"]
                    if record_config["input_token_count"] is not None
                    else 5
                )

            parsed_record = ParsedResponseRecord(
                worker_id=record_config["worker_id"],
                request=request,
                responses=record_config["responses"].copy(),
                input_token_count=input_token_count,
                output_token_count=output_token_count,
            )
            parsed_records.append(parsed_record)

        return parsed_records


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
