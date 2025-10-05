# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Test utilities for validating AIPerf benchmark results.

Provides easy-to-use helpers for test writers to validate:
- JSON export data (using Pydantic models)
- CSV export data
- Console output
- Metrics accuracy
- Artifact directory structure

All data is parsed using Pydantic models for type safety and validation.

Example usage:
    result = BenchmarkResult.from_directory(output_dir)
    result.assert_metric_exists("ttft", "inter_token_latency")
    result.assert_metric_in_range("ttft", min_value=0, max_value=1000)
    result.assert_csv_contains("Time to First Token")
    result.assert_inputs_json_has_images()
"""

import json
import re
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from aiperf.common.config import UserConfig
from aiperf.common.models import ErrorDetailsCount, InputsFile, MetricResult
from aiperf.common.types import MetricTagT


class BenchmarkResult:
    """Fluent API for validating benchmark results.

    Provides easy-to-use methods for validating AIPerf output files,
    metrics, and console output. All data is parsed using Pydantic models
    for type safety and validation.
    """

    def __init__(self, artifacts_dir: Path):
        """Initialize from artifacts directory.

        Args:
            artifacts_dir: Path to AIPerf artifacts directory
        """
        self.artifacts_dir = Path(artifacts_dir)
        self._records: dict[str, dict[str, Any]] | None = None  # Raw dict for flexibility
        self._input_config: UserConfig | None = None  # Pydantic model
        self._error_summary: list[ErrorDetailsCount] | None = None  # Pydantic models
        self._was_cancelled: bool | None = None
        self._json_file: Path | None = None
        self._csv_file: Path | None = None
        self._csv_content: str | None = None
        self._log_file: Path | None = None
        self._inputs_file: InputsFile | None = None
        self._inputs_json_file: Path | None = None
        self._load_artifacts()

    @classmethod
    def from_directory(cls, artifacts_dir: Path) -> "BenchmarkResult":
        """Create BenchmarkResult from artifacts directory.

        Args:
            artifacts_dir: Path to artifacts directory

        Returns:
            BenchmarkResult instance
        """
        return cls(artifacts_dir)

    def _load_artifacts(self) -> None:
        """Load all artifact files from directory using Pydantic models."""
        # Find and parse JSON file
        json_files = list(self.artifacts_dir.glob("**/*aiperf.json"))
        if json_files:
            self._json_file = json_files[0]
            with open(self._json_file) as f:
                json_dict = json.load(f)

            # Store records as raw dict (some metrics have non-standard types like datetime strings)
            if "records" in json_dict and json_dict["records"]:
                self._records = json_dict["records"]

            # Parse input_config
            if "input_config" in json_dict and json_dict["input_config"]:
                self._input_config = UserConfig(**json_dict["input_config"])

            # Parse error_summary
            if "error_summary" in json_dict and json_dict["error_summary"]:
                error_adapter = TypeAdapter(list[ErrorDetailsCount])
                self._error_summary = error_adapter.validate_python(json_dict["error_summary"])

            # Parse was_cancelled
            self._was_cancelled = json_dict.get("was_cancelled")

        # Find CSV file
        csv_files = list(self.artifacts_dir.glob("**/*aiperf.csv"))
        if csv_files:
            self._csv_file = csv_files[0]
            with open(self._csv_file) as f:
                self._csv_content = f.read()

        # Find log file
        log_files = list(self.artifacts_dir.glob("**/logs/aiperf.log"))
        if log_files:
            self._log_file = log_files[0]

        # Find and parse inputs.json
        inputs_files = list(self.artifacts_dir.glob("**/inputs.json"))
        if inputs_files:
            self._inputs_json_file = inputs_files[0]
            with open(self._inputs_json_file) as f:
                inputs_dict = json.load(f)
            try:
                self._inputs_file = InputsFile(**inputs_dict)
            except ValidationError as e:
                # Log warning but don't fail - some tests may not need strict validation
                import warnings
                warnings.warn(f"inputs.json validation failed: {e}")

    @property
    def records(self) -> dict[str, dict[str, Any]]:
        """Get metrics records dict.

        Returns raw dicts instead of Pydantic models because metric values
        can have varying types (floats, ints, datetime strings, etc.).
        """
        if self._records is None:
            raise AssertionError("No records found in JSON export")
        return self._records

    @property
    def input_config(self) -> UserConfig:
        """Get parsed input configuration (Pydantic model)."""
        if self._input_config is None:
            raise AssertionError("No input_config found in JSON export")
        return self._input_config

    @property
    def error_summary(self) -> list[ErrorDetailsCount]:
        """Get parsed error summary (Pydantic models)."""
        if self._error_summary is None:
            return []
        return self._error_summary

    @property
    def was_cancelled(self) -> bool:
        """Get cancellation status."""
        return self._was_cancelled or False

    @property
    def csv_content(self) -> str:
        """Get CSV file content."""
        if self._csv_content is None:
            raise AssertionError("No CSV export file found")
        return self._csv_content

    @property
    def inputs_file(self) -> InputsFile:
        """Get parsed inputs.json (Pydantic model)."""
        if self._inputs_file is None:
            raise AssertionError("No inputs.json file found or failed to parse")
        return self._inputs_file

    # Metric assertion methods

    def assert_metric_exists(self, *metric_tags: str) -> "BenchmarkResult":
        """Assert that specific metrics exist in results.

        Args:
            *metric_tags: Variable number of metric tags to check

        Returns:
            self for chaining

        Raises:
            AssertionError: If any metric is missing
        """
        for tag in metric_tags:
            assert tag in self.records, f"Metric '{tag}' not found in results"
        return self

    def assert_metric_value(
        self, metric_tag: str, stat: str, expected: float, tolerance: float = 0.01
    ) -> "BenchmarkResult":
        """Assert metric statistic matches expected value within tolerance.

        Args:
            metric_tag: Metric tag (e.g., "ttft")
            stat: Statistic name (e.g., "avg", "min", "max")
            expected: Expected value
            tolerance: Tolerance for comparison (default 1%)

        Returns:
            self for chaining
        """
        metric = self.records.get(metric_tag)
        assert metric is not None, f"Metric '{metric_tag}' not found"

        value = metric.get(stat)
        assert value is not None, f"Metric '{metric_tag}' missing '{stat}' statistic"

        diff = abs(value - expected)
        max_diff = abs(expected * tolerance)
        assert diff <= max_diff, (
            f"Metric '{metric_tag}.{stat}' value {value} not within {tolerance*100}% of {expected}"
        )
        return self

    def assert_metric_in_range(
        self, metric_tag: str, stat: str = "avg", min_value: float | None = None, max_value: float | None = None
    ) -> "BenchmarkResult":
        """Assert metric statistic is within range.

        Args:
            metric_tag: Metric tag
            stat: Statistic name (default "avg")
            min_value: Minimum allowed value (inclusive)
            max_value: Maximum allowed value (inclusive)

        Returns:
            self for chaining
        """
        metric = self.records.get(metric_tag)
        assert metric is not None, f"Metric '{metric_tag}' not found"

        value = metric.get(stat)
        assert value is not None, f"Metric '{metric_tag}' missing '{stat}' statistic"

        if min_value is not None:
            assert value >= min_value, (
                f"Metric '{metric_tag}.{stat}' value {value} below minimum {min_value}"
            )

        if max_value is not None:
            assert value <= max_value, (
                f"Metric '{metric_tag}.{stat}' value {value} above maximum {max_value}"
            )

        return self

    def assert_request_count(
        self, min_count: int | None = None, max_count: int | None = None, exact: int | None = None
    ) -> "BenchmarkResult":
        """Assert request count is within expected range.

        Args:
            min_count: Minimum requests (inclusive)
            max_count: Maximum requests (inclusive)
            exact: Exact request count (if specified, min/max ignored)

        Returns:
            self for chaining
        """
        count = self.records.get("request_count")
        assert count is not None, "request_count metric not found"

        avg_count = count.get("avg")
        assert avg_count is not None, "request_count.avg is None"

        if exact is not None:
            assert avg_count == exact, f"Expected exactly {exact} requests, got {avg_count}"
        else:
            if min_count is not None:
                assert avg_count >= min_count, (
                    f"Request count {avg_count} below minimum {min_count}"
                )
            if max_count is not None:
                assert avg_count <= max_count, (
                    f"Request count {avg_count} above maximum {max_count}"
                )

        return self

    # CSV assertion methods

    def assert_csv_contains(self, *text_patterns: str) -> "BenchmarkResult":
        """Assert CSV contains specific text patterns.

        Args:
            *text_patterns: Variable number of text patterns to find

        Returns:
            self for chaining
        """
        for pattern in text_patterns:
            assert pattern in self.csv_content, (
                f"CSV does not contain '{pattern}'"
            )
        return self

    def assert_csv_has_metric(self, metric_name: str) -> "BenchmarkResult":
        """Assert CSV contains a specific metric (human-readable name).

        Args:
            metric_name: Human-readable metric name (e.g., "Request Latency")

        Returns:
            self for chaining
        """
        return self.assert_csv_contains(metric_name)

    # Console output assertion methods

    @staticmethod
    def assert_console_output_contains(output: str, *patterns: str) -> None:
        """Assert console output contains specific patterns.

        Args:
            output: Console output text (stdout or stderr)
            *patterns: Variable number of patterns to find
        """
        for pattern in patterns:
            assert pattern in output, f"Console output does not contain '{pattern}'"

    @staticmethod
    def assert_console_metric_displayed(output: str, metric_name: str) -> None:
        """Assert metric is displayed in console output.

        Args:
            output: Console output text
            metric_name: Human-readable metric name
        """
        assert metric_name in output, (
            f"Metric '{metric_name}' not displayed in console output"
        )

    # Inputs.json assertion methods (using Pydantic InputsFile model)

    def assert_inputs_json_exists(self) -> "BenchmarkResult":
        """Assert inputs.json file exists and is parsed.

        Returns:
            self for chaining
        """
        assert self._inputs_file is not None, "inputs.json not found or failed to parse"
        return self

    def assert_inputs_json_has_sessions(self, min_sessions: int = 1) -> "BenchmarkResult":
        """Assert inputs.json has minimum number of sessions.

        Args:
            min_sessions: Minimum number of sessions expected

        Returns:
            self for chaining
        """
        num_sessions = len(self.inputs_file.data)
        assert num_sessions >= min_sessions, (
            f"Expected at least {min_sessions} sessions, got {num_sessions}"
        )
        return self

    def assert_inputs_json_has_images(self) -> "BenchmarkResult":
        """Assert inputs.json contains image content.

        Returns:
            self for chaining
        """
        self.assert_inputs_json_exists()

        has_image = False
        for session in self.inputs_file.data:
            for payload in session.payloads:
                for msg in payload.get("messages", []):
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "image_url":
                                has_image = True
                                break

        assert has_image, "No image content found in inputs.json"
        return self

    def assert_inputs_json_has_audio(self) -> "BenchmarkResult":
        """Assert inputs.json contains audio content.

        Returns:
            self for chaining
        """
        self.assert_inputs_json_exists()

        has_audio = False
        for session in self.inputs_file.data:
            for payload in session.payloads:
                for msg in payload.get("messages", []):
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "input_audio":
                                has_audio = True
                                break

        assert has_audio, "No audio content found in inputs.json"
        return self

    # File existence assertion methods

    def assert_all_artifacts_exist(self) -> "BenchmarkResult":
        """Assert all expected artifact files exist.

        Returns:
            self for chaining
        """
        assert self._json_file is not None, "JSON export file not found"
        assert self._json_file.exists(), f"JSON file does not exist: {self._json_file}"

        assert self._csv_file is not None, "CSV export file not found"
        assert self._csv_file.exists(), f"CSV file does not exist: {self._csv_file}"

        assert self._log_file is not None, "Log file not found"
        assert self._log_file.exists(), f"Log file does not exist: {self._log_file}"

        return self

    def assert_log_not_empty(self) -> "BenchmarkResult":
        """Assert log file has content.

        Returns:
            self for chaining
        """
        assert self._log_file is not None, "Log file not found"
        assert self._log_file.stat().st_size > 0, "Log file is empty"
        return self

    # Configuration assertion methods

    def assert_config_value(self, config_path: str, expected_value: Any) -> "BenchmarkResult":
        """Assert configuration value matches expected.

        Args:
            config_path: Dot-separated path to config (e.g., "endpoint.streaming")
            expected_value: Expected value

        Returns:
            self for chaining
        """
        # Navigate through Pydantic config model using dot notation
        current = self.input_config
        for key in config_path.split("."):
            if hasattr(current, key):
                current = getattr(current, key)
            else:
                raise AssertionError(f"Config path '{config_path}' not found (key: {key})")

        assert current == expected_value, (
            f"Config '{config_path}' is {current}, expected {expected_value}"
        )
        return self

    # Error summary assertion methods

    def assert_no_errors(self) -> "BenchmarkResult":
        """Assert no errors in error summary (using Pydantic models).

        Returns:
            self for chaining
        """
        if self.error_summary:
            total_errors = sum(err.count for err in self.error_summary)
            assert total_errors == 0, (
                f"Expected no errors, but found {total_errors}: {self.error_summary}"
            )
        return self

    def assert_error_count(self, min_errors: int = 0, max_errors: int | None = None) -> "BenchmarkResult":
        """Assert error count is within range (using Pydantic models).

        Args:
            min_errors: Minimum expected errors
            max_errors: Maximum allowed errors

        Returns:
            self for chaining
        """
        total_errors = sum(err.count for err in self.error_summary)

        assert total_errors >= min_errors, (
            f"Expected at least {min_errors} errors, got {total_errors}"
        )

        if max_errors is not None:
            assert total_errors <= max_errors, (
                f"Expected at most {max_errors} errors, got {total_errors}"
            )

        return self

    def assert_was_cancelled(self, expected: bool = True) -> "BenchmarkResult":
        """Assert benchmark was or was not cancelled.

        Args:
            expected: Whether benchmark should have been cancelled

        Returns:
            self for chaining
        """
        assert self.was_cancelled == expected, (
            f"Expected was_cancelled={expected}, got {self.was_cancelled}"
        )
        return self

    def get_metric(self, metric_tag: str) -> dict[str, Any]:
        """Get metric by tag (returns dict).

        Args:
            metric_tag: Metric tag

        Returns:
            Metric dict with stats (avg, min, max, etc.)

        Raises:
            AssertionError: If metric not found
        """
        metric = self.records.get(metric_tag)
        assert metric is not None, f"Metric '{metric_tag}' not found"
        return metric


class ConsoleOutputValidator:
    """Helper for validating console output text."""

    def __init__(self, output: str):
        """Initialize with console output.

        Args:
            output: Console output text (stdout or stderr)
        """
        self.output = output

    def assert_contains(self, *patterns: str) -> "ConsoleOutputValidator":
        """Assert output contains all patterns.

        Args:
            *patterns: Variable number of text patterns

        Returns:
            self for chaining
        """
        for pattern in patterns:
            assert pattern in self.output, (
                f"Console output does not contain '{pattern}'"
            )
        return self

    def assert_not_contains(self, *patterns: str) -> "ConsoleOutputValidator":
        """Assert output does not contain any patterns.

        Args:
            *patterns: Variable number of text patterns

        Returns:
            self for chaining
        """
        for pattern in patterns:
            assert pattern not in self.output, (
                f"Console output should not contain '{pattern}'"
            )
        return self

    def assert_metric_displayed(self, metric_name: str) -> "ConsoleOutputValidator":
        """Assert metric appears in console output.

        Args:
            metric_name: Human-readable metric name (e.g., "Request Latency")

        Returns:
            self for chaining
        """
        return self.assert_contains(metric_name)

    def assert_table_displayed(self) -> "ConsoleOutputValidator":
        """Assert a metrics table is displayed.

        Returns:
            self for chaining
        """
        # Look for table borders or common table patterns
        has_table = any(
            pattern in self.output
            for pattern in ["┃", "│", "─", "━", "Metric", "avg", "min", "max"]
        )
        assert has_table, "No metrics table found in console output"
        return self

    def assert_error_summary_displayed(self) -> "ConsoleOutputValidator":
        """Assert error summary is displayed.

        Returns:
            self for chaining
        """
        return self.assert_contains("Error Summary")

    def extract_metric_value(self, metric_name: str, stat: str = "avg") -> float | None:
        """Extract metric value from console output table.

        Args:
            metric_name: Human-readable metric name
            stat: Statistic name (avg, min, max, etc.)

        Returns:
            Extracted value or None if not found
        """
        # Try to find the metric line and extract the value
        # This is a simple regex-based extraction
        pattern = rf"{re.escape(metric_name)}.*?(\d+(?:\.\d+)?)"
        match = re.search(pattern, self.output)
        if match:
            return float(match.group(1))
        return None
