# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Pydantic-powered fluent API for validating AIPerf benchmark results."""

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from aiperf.common.config import UserConfig
from aiperf.common.models import ErrorDetailsCount, InputsFile, MetricResult


class BenchmarkResult:
    """Fluent API for validating AIPerf results using Pydantic models."""

    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = Path(artifacts_dir)
        self._records: dict[str, MetricResult] | None = None
        self._input_config: UserConfig | None = None
        self._error_summary: list[ErrorDetailsCount] | None = None
        self._was_cancelled: bool | None = None
        self._json_file: Path | None = None
        self._csv_file: Path | None = None
        self._csv_content: str | None = None
        self._log_file: Path | None = None
        self._inputs_file: InputsFile | None = None
        self._load_artifacts()

    @classmethod
    def from_directory(cls, artifacts_dir: Path) -> "BenchmarkResult":
        return cls(artifacts_dir)

    def _load_artifacts(self) -> None:
        """Load and parse all artifacts using Pydantic."""
        json_file = next(self.artifacts_dir.glob("**/*aiperf.json"), None)
        if json_file:
            self._json_file = json_file
            with open(json_file) as f:
                data = json.load(f)

            # Parse records into MetricResult models (skip invalid ones)
            if data.get("records"):
                self._records = {}
                for tag, metric_dict in data["records"].items():
                    try:
                        self._records[tag] = MetricResult(**metric_dict)
                    except ValidationError:
                        pass  # Skip timestamp metrics with datetime strings

            # Parse Pydantic models
            if data.get("input_config"):
                self._input_config = UserConfig(**data["input_config"])
            if data.get("error_summary"):
                self._error_summary = TypeAdapter(list[ErrorDetailsCount]).validate_python(data["error_summary"])
            self._was_cancelled = data.get("was_cancelled")

        # Load CSV
        csv_file = next(self.artifacts_dir.glob("**/*aiperf.csv"), None)
        if csv_file:
            self._csv_file = csv_file
            self._csv_content = csv_file.read_text()

        # Load log
        self._log_file = next(self.artifacts_dir.glob("**/logs/aiperf.log"), None)

        # Load and parse inputs.json
        inputs_file = next(self.artifacts_dir.glob("**/inputs.json"), None)
        if inputs_file:
            try:
                self._inputs_file = InputsFile(**json.loads(inputs_file.read_text()))
            except ValidationError:
                pass  # Some tests may not need inputs.json

    @property
    def records(self) -> dict[str, MetricResult]:
        assert self._records, "No records found"
        return self._records

    @property
    def input_config(self) -> UserConfig:
        assert self._input_config, "No input_config found"
        return self._input_config

    @property
    def error_summary(self) -> list[ErrorDetailsCount]:
        return self._error_summary or []

    @property
    def was_cancelled(self) -> bool:
        return self._was_cancelled or False

    @property
    def csv_content(self) -> str:
        assert self._csv_content, "No CSV found"
        return self._csv_content

    @property
    def inputs_file(self) -> InputsFile:
        assert self._inputs_file, "No inputs.json found"
        return self._inputs_file

    def assert_metric_exists(self, *metric_tags: str) -> "BenchmarkResult":
        for tag in metric_tags:
            assert tag in self.records, f"Metric '{tag}' not found"
        return self

    def assert_metric_value(
        self, metric_tag: str, stat: str, expected: float, tolerance: float = 0.01
    ) -> "BenchmarkResult":
        value = getattr(self.get_metric(metric_tag), stat)
        assert value, f"Metric '{metric_tag}.{stat}' missing"
        assert abs(value - expected) <= abs(expected * tolerance), \
            f"{metric_tag}.{stat}={value} not within {tolerance*100}% of {expected}"
        return self

    def assert_metric_in_range(
        self, metric_tag: str, stat: str = "avg", min_value: float | None = None, max_value: float | None = None
    ) -> "BenchmarkResult":
        value = getattr(self.get_metric(metric_tag), stat)
        assert value, f"Metric '{metric_tag}.{stat}' missing"
        if min_value is not None:
            assert value >= min_value, f"{metric_tag}.{stat}={value} < {min_value}"
        if max_value is not None:
            assert value <= max_value, f"{metric_tag}.{stat}={value} > {max_value}"
        return self

    def assert_request_count(
        self, min_count: int | None = None, max_count: int | None = None, exact: int | None = None
    ) -> "BenchmarkResult":
        count = self.get_metric("request_count").avg
        assert count, "request_count.avg is None"
        if exact is not None:
            assert count == exact, f"Expected {exact} requests, got {count}"
        if min_count is not None:
            assert count >= min_count, f"Count {count} < {min_count}"
        if max_count is not None:
            assert count <= max_count, f"Count {count} > {max_count}"
        return self

    def assert_csv_contains(self, *text_patterns: str) -> "BenchmarkResult":
        for pattern in text_patterns:
            assert pattern in self.csv_content, f"CSV missing '{pattern}'"
        return self

    def assert_inputs_json_exists(self) -> "BenchmarkResult":
        assert self._inputs_file, "inputs.json not found"
        return self

    def assert_inputs_json_has_sessions(self, min_sessions: int = 1) -> "BenchmarkResult":
        assert len(self.inputs_file.data) >= min_sessions, \
            f"Expected >={min_sessions} sessions, got {len(self.inputs_file.data)}"
        return self

    def assert_inputs_json_has_images(self) -> "BenchmarkResult":
        assert any(
            item.get("type") == "image_url"
            for s in self.inputs_file.data for p in s.payloads
            for msg in p.get("messages", []) for item in msg.get("content", [])
            if isinstance(item, dict)
        ), "No images in inputs.json"
        return self

    def assert_inputs_json_has_audio(self) -> "BenchmarkResult":
        assert any(
            item.get("type") == "input_audio"
            for s in self.inputs_file.data for p in s.payloads
            for msg in p.get("messages", []) for item in msg.get("content", [])
            if isinstance(item, dict)
        ), "No audio in inputs.json"
        return self

    def assert_all_artifacts_exist(self) -> "BenchmarkResult":
        assert self._json_file and self._json_file.exists(), "No JSON file"
        assert self._csv_file and self._csv_file.exists(), "No CSV file"
        assert self._log_file and self._log_file.exists(), "No log file"
        return self

    def assert_log_not_empty(self) -> "BenchmarkResult":
        assert self._log_file and self._log_file.stat().st_size > 0, "Log file empty"
        return self

    def assert_config_value(self, config_path: str, expected_value: Any) -> "BenchmarkResult":
        current = self.input_config
        for key in config_path.split("."):
            current = getattr(current, key)
        assert current == expected_value, f"{config_path}={current}, expected {expected_value}"
        return self

    def assert_no_errors(self) -> "BenchmarkResult":
        total = sum(e.count for e in self.error_summary)
        assert total == 0, f"Found {total} errors: {self.error_summary}"
        return self

    def assert_error_count(self, min_errors: int = 0, max_errors: int | None = None) -> "BenchmarkResult":
        total = sum(e.count for e in self.error_summary)
        if min_errors:
            assert total >= min_errors, f"Expected >={min_errors} errors, got {total}"
        if max_errors is not None:
            assert total <= max_errors, f"Expected <={max_errors} errors, got {total}"
        return self

    def assert_was_cancelled(self, expected: bool = True) -> "BenchmarkResult":
        assert self.was_cancelled == expected, f"was_cancelled={self.was_cancelled}, expected {expected}"
        return self

    def get_metric(self, metric_tag: str) -> MetricResult:
        metric = self.records.get(metric_tag)
        assert metric, f"Metric '{metric_tag}' not found"
        return metric


class ConsoleOutputValidator:
    """Validates console output text."""

    def __init__(self, output: str):
        self.output = output

    def assert_contains(self, *patterns: str) -> "ConsoleOutputValidator":
        for p in patterns:
            assert p in self.output, f"Console missing '{p}'"
        return self

    def assert_not_contains(self, *patterns: str) -> "ConsoleOutputValidator":
        for p in patterns:
            assert p not in self.output, f"Console has '{p}'"
        return self

    def assert_table_displayed(self) -> "ConsoleOutputValidator":
        assert any(p in self.output for p in ["┃", "Metric", "avg"]), "No table in output"
        return self
