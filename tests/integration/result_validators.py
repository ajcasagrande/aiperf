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

from pydantic import ValidationError

from aiperf.common.models import MetricResult
from aiperf.exporters.json_exporter import JsonExportData


class BenchmarkResult:
    """Fluent API for validating benchmark results.

    Provides easy-to-use methods for validating AIPerf output files,
    metrics, and console output.
    """

    def __init__(self, artifacts_dir: Path):
        """Initialize from artifacts directory.

        Args:
            artifacts_dir: Path to AIPerf artifacts directory
        """
        self.artifacts_dir = Path(artifacts_dir)
        self._json_dict: dict[str, Any] | None = None
        self._json_file: Path | None = None
        self._csv_file: Path | None = None
        self._csv_content: str | None = None
        self._log_file: Path | None = None
        self._inputs_json: dict[str, Any] | None = None
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
        """Load all artifact files from directory."""
        # Find JSON file
        json_files = list(self.artifacts_dir.glob("**/*aiperf.json"))
        if json_files:
            self._json_file = json_files[0]
            with open(self._json_file) as f:
                self._json_dict = json.load(f)

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

        # Find inputs.json
        inputs_files = list(self.artifacts_dir.glob("**/inputs.json"))
        if inputs_files:
            self._inputs_json_file = inputs_files[0]
            with open(self._inputs_json_file) as f:
                self._inputs_json = json.load(f)

    @property
    def json_data(self) -> dict[str, Any]:
        """Get parsed JSON export data."""
        if self._json_dict is None:
            raise AssertionError("No JSON export file found")
        return self._json_dict

    @property
    def records(self) -> dict[str, Any]:
        """Get metrics records from JSON export."""
        if "records" not in self.json_data:
            raise AssertionError("JSON export has no records")
        return self.json_data["records"]

    @property
    def csv_content(self) -> str:
        """Get CSV file content."""
        if self._csv_content is None:
            raise AssertionError("No CSV export file found")
        return self._csv_content

    @property
    def inputs_json(self) -> dict[str, Any]:
        """Get inputs.json content."""
        if self._inputs_json is None:
            raise AssertionError("No inputs.json file found")
        return self._inputs_json

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

        value = metric.get(stat) if isinstance(metric, dict) else getattr(metric, stat, None)
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

        value = metric.get(stat) if isinstance(metric, dict) else getattr(metric, stat, None)
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

        avg_count = count.get("avg") if isinstance(count, dict) else getattr(count, "avg", None)
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

    # Inputs.json assertion methods

    def assert_inputs_json_exists(self) -> "BenchmarkResult":
        """Assert inputs.json file exists.

        Returns:
            self for chaining
        """
        assert self._inputs_json is not None, "inputs.json not found"
        return self

    def assert_inputs_json_has_sessions(self, min_sessions: int = 1) -> "BenchmarkResult":
        """Assert inputs.json has minimum number of sessions.

        Args:
            min_sessions: Minimum number of sessions expected

        Returns:
            self for chaining
        """
        self.assert_inputs_json_exists()
        assert "data" in self.inputs_json, "inputs.json missing 'data' field"
        assert isinstance(self.inputs_json["data"], list), "data should be list"
        num_sessions = len(self.inputs_json["data"])
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
        for session in self.inputs_json["data"]:
            for payload in session.get("payloads", []):
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
        for session in self.inputs_json["data"]:
            for payload in session.get("payloads", []):
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
        if "input_config" not in self.json_data:
            raise AssertionError("No input_config in JSON export")

        # Navigate through config using dot notation
        current = self.json_data["input_config"]
        for key in config_path.split("."):
            if isinstance(current, dict):
                if key in current:
                    current = current[key]
                else:
                    raise AssertionError(f"Config key '{key}' not found in path '{config_path}'")
            elif hasattr(current, key):
                current = getattr(current, key)
            else:
                raise AssertionError(f"Config path '{config_path}' not found")

        assert current == expected_value, (
            f"Config '{config_path}' is {current}, expected {expected_value}"
        )
        return self

    # Error summary assertion methods

    def assert_no_errors(self) -> "BenchmarkResult":
        """Assert no errors in error summary.

        Returns:
            self for chaining
        """
        error_summary = self.json_data.get("error_summary", [])
        if error_summary:
            total_errors = sum(err.get("count", 0) if isinstance(err, dict) else err.count for err in error_summary)
            assert total_errors == 0, (
                f"Expected no errors, but found {total_errors}: {error_summary}"
            )
        return self

    def assert_error_count(self, min_errors: int = 0, max_errors: int | None = None) -> "BenchmarkResult":
        """Assert error count is within range.

        Args:
            min_errors: Minimum expected errors
            max_errors: Maximum allowed errors

        Returns:
            self for chaining
        """
        total_errors = 0
        error_summary = self.json_data.get("error_summary", [])
        if error_summary:
            total_errors = sum(err.get("count", 0) if isinstance(err, dict) else err.count for err in error_summary)

        assert total_errors >= min_errors, (
            f"Expected at least {min_errors} errors, got {total_errors}"
        )

        if max_errors is not None:
            assert total_errors <= max_errors, (
                f"Expected at most {max_errors} errors, got {total_errors}"
            )

        return self


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
