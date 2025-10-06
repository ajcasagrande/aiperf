# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Pythonic validation for AIPerf results using natural Python syntax and Pydantic models."""

import json
from contextlib import suppress
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from aiperf.common.config import UserConfig
from aiperf.common.models import ErrorDetailsCount, InputsFile, MetricResult
from aiperf.exporters.json_exporter import JsonExportData

from .test_models import (
    AudioContent,
    ChatCompletionPayload,
    ImageContent,
    MessageContentItem,
)


class MetricsView:
    """View for metrics with natural Python protocol support."""

    def __init__(self, records: dict[str, MetricResult]):
        self._records = records

    def __contains__(self, metric_tag: str) -> bool:
        """Enable: 'ttft' in result.metrics"""
        return metric_tag in self._records

    def __getitem__(self, metric_tag: str) -> MetricResult:
        """Enable: result.metrics['ttft']"""
        if metric_tag not in self._records:
            raise KeyError(f"Metric '{metric_tag}' not found")
        return self._records[metric_tag]

    def __iter__(self):
        """Enable: for tag in result.metrics"""
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)

    def get(self, metric_tag: str, default=None) -> MetricResult | None:
        return self._records.get(metric_tag, default)


class BenchmarkResult:
    """Pythonic API for validating AIPerf results using properties and natural syntax."""

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

    def _load_artifacts(self) -> None:
        """Load and parse all artifacts using Pydantic."""
        json_file = next(self.artifacts_dir.glob("**/*aiperf.json"), None)
        if json_file:
            self._json_file = json_file
            with open(json_file) as f:
                json_data = json.load(f)

            # Parse entire JSON export structure using Pydantic model
            try:
                export_data = JsonExportData(**json_data)
                self._records = export_data.records or {}
                self._input_config = export_data.input_config
                self._error_summary = export_data.error_summary
                self._was_cancelled = export_data.was_cancelled
            except ValidationError:
                # Fallback to manual parsing if structure doesn't match
                # Parse records manually (skip invalid ones)
                if json_data.get("records"):
                    self._records = {}
                    for tag, metric_dict in json_data["records"].items():
                        with suppress(ValidationError):
                            self._records[tag] = MetricResult(**metric_dict)

                if json_data.get("input_config"):
                    self._input_config = UserConfig(**json_data["input_config"])
                if json_data.get("error_summary"):
                    self._error_summary = TypeAdapter(
                        list[ErrorDetailsCount]
                    ).validate_python(json_data["error_summary"])
                self._was_cancelled = json_data.get("was_cancelled")

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
            with suppress(ValidationError, json.JSONDecodeError):
                self._inputs_file = InputsFile(**json.loads(inputs_file.read_text()))

    @property
    def metrics(self) -> MetricsView:
        """Metrics with natural Python protocol support.

        Usage:
            assert "ttft" in result.metrics
            assert result.metrics["ttft"].avg >= 0
        """
        if not self._records:
            raise ValueError("No metrics found")
        return MetricsView(self._records)

    @property
    def config(self) -> UserConfig:
        """Input configuration Pydantic model.

        Usage:
            assert result.config.endpoint.streaming
        """
        if not self._input_config:
            raise ValueError("No config found")
        return self._input_config

    @property
    def error_summary(self) -> list[ErrorDetailsCount]:
        """List of errors with counts.

        Usage:
            for error in result.error_summary:
                print(error.message, error.count)
        """
        return self._error_summary or []

    @property
    def has_errors(self) -> bool:
        """Check if benchmark had any errors.

        Usage:
            assert not result.has_errors
        """
        return sum(e.count for e in self.error_summary) > 0

    @property
    def error_count(self) -> int:
        """Total number of errors.

        Usage:
            assert result.error_count == 0
            assert result.error_count <= 5
        """
        return sum(e.count for e in self.error_summary)

    @property
    def was_cancelled(self) -> bool:
        """Check if benchmark was cancelled.

        Usage:
            assert not result.was_cancelled
        """
        return self._was_cancelled or False

    @property
    def request_count(self) -> int:
        """Total completed requests.

        Usage:
            assert result.request_count >= 10
            assert 8 <= result.request_count <= 12
        """
        metric = self._records.get("request_count") if self._records else None
        return int(metric.avg) if metric and metric.avg else 0

    @property
    def csv(self) -> str:
        """CSV file content.

        Usage:
            assert "Request Latency" in result.csv
        """
        if not self._csv_content:
            raise ValueError("No CSV found")
        return self._csv_content

    @property
    def inputs(self) -> InputsFile:
        """Parsed inputs.json Pydantic model.

        Usage:
            assert len(result.inputs.data) >= 1
        """
        if not self._inputs_file:
            raise ValueError("No inputs.json found")
        return self._inputs_file

    @property
    def artifacts_exist(self) -> bool:
        """Check if all artifacts exist.

        Usage:
            assert result.artifacts_exist
        """
        return all(
            [
                self._json_file and self._json_file.exists(),
                self._csv_file and self._csv_file.exists(),
                self._log_file and self._log_file.exists(),
            ]
        )

    @property
    def has_images(self) -> bool:
        """Check if inputs.json contains images.

        Usage:
            assert result.has_images
        """
        return any(
            isinstance(item, ImageContent)
            or (hasattr(item, "type") and item.type == "image_url")
            for item in self._get_all_content_items()
        )

    @property
    def has_audio(self) -> bool:
        """Check if inputs.json contains audio.

        Usage:
            assert result.has_audio
        """
        return any(
            isinstance(item, AudioContent)
            or (hasattr(item, "type") and item.type == "input_audio")
            for item in self._get_all_content_items()
        )

    def _get_all_content_items(self) -> list[MessageContentItem]:
        """Extract all message content items from inputs.json using Pydantic parsing.

        Returns:
            List of all content items (text, image, audio) from all payloads.
        """
        content_items: list[MessageContentItem] = []
        for session in self.inputs.data:
            for payload_dict in session.payloads:
                try:
                    payload = ChatCompletionPayload(**payload_dict)
                    for message in payload.messages:
                        if isinstance(message.content, list):
                            content_items.extend(message.content)
                except (ValidationError, json.JSONDecodeError):
                    # Skip non-chat payloads (e.g., completions, embeddings)
                    continue
        return content_items


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
        assert any(p in self.output for p in ["┃", "Metric", "avg"]), (
            "No table in output"
        )
        return self
