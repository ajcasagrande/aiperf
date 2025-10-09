# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json

import pytest

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import EndpointType, ExportLevel
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.metrics.types.request_latency_metric import RequestLatencyMetric
from aiperf.metrics.types.ttft_metric import TTFTMetric
from aiperf.post_processors.record_export_results_processor import (
    RecordExportResultsProcessor,
)


@pytest.fixture
def user_config_summary(tmp_path):
    """User config with summary export level (default)."""
    return UserConfig(
        endpoint={"model_names": ["test"], "type": EndpointType.CHAT},
        output={"artifact_directory": tmp_path, "export_level": ExportLevel.SUMMARY},
    )


@pytest.fixture
def user_config_records(tmp_path):
    """User config with records export level."""
    return UserConfig(
        endpoint={"model_names": ["test"], "type": EndpointType.CHAT},
        output={"artifact_directory": tmp_path, "export_level": ExportLevel.RECORDS},
    )


@pytest.fixture
def service_config():
    """Basic service config."""
    return ServiceConfig()


class TestRecordExportResultsProcessor:
    """Tests for RecordExportResultsProcessor."""

    def test_disabled_by_default(self, user_config_summary, service_config):
        """Test that processor is disabled with summary export level."""
        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config_summary,
        )

        assert not processor.enabled

    def test_enabled_with_records_level(self, user_config_records, service_config):
        """Test that processor is enabled with records export level."""
        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config_records,
        )

        assert processor.enabled
        assert processor.output_file.parent.exists()
        assert processor.output_file.name == "record_metrics.jsonl"

    async def test_process_result_writes_to_file(
        self, user_config_records, service_config
    ):
        """Test that process_result writes metrics to JSONL file."""
        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config_records,
        )

        # Create metric record dict
        metrics = MetricRecordDict()
        metrics[TTFTMetric.tag] = 20000000  # 20ms in ns
        metrics[RequestLatencyMetric.tag] = 500000000  # 500ms in ns

        # Process the result
        await processor.process_result(metrics)

        # Verify file was written
        assert processor.output_file.exists()
        assert processor.record_count == 1

        # Verify content
        with open(processor.output_file) as f:
            line = f.readline()
            data = json.loads(line)

        assert TTFTMetric.tag in data
        assert data[TTFTMetric.tag]["value"] == pytest.approx(20.0, rel=0.01)
        assert data[TTFTMetric.tag]["unit"] == "ms"

    async def test_multiple_records_written(self, user_config_records, service_config):
        """Test that multiple records are written as separate lines."""
        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config_records,
        )

        # Process multiple records
        for i in range(5):
            metrics = MetricRecordDict()
            metrics[TTFTMetric.tag] = 20000000 + (i * 1000000)
            await processor.process_result(metrics)

        assert processor.record_count == 5

        # Verify all lines
        with open(processor.output_file) as f:
            lines = f.readlines()

        assert len(lines) == 5
        for i, line in enumerate(lines):
            data = json.loads(line)
            expected_value = 20.0 + i
            assert data[TTFTMetric.tag]["value"] == pytest.approx(
                expected_value, rel=0.01
            )

    async def test_disabled_processor_does_nothing(
        self, user_config_summary, service_config, tmp_path
    ):
        """Test that disabled processor doesn't write files."""
        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config_summary,
        )

        metrics = MetricRecordDict()
        metrics[TTFTMetric.tag] = 20000000

        await processor.process_result(metrics)

        # No file should be created
        record_metrics_dir = tmp_path / "record_metrics"
        assert not record_metrics_dir.exists() or not list(record_metrics_dir.iterdir())

    async def test_empty_metrics_skipped(self, user_config_records, service_config):
        """Test that empty metric dicts don't write lines."""
        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config_records,
        )

        # Process empty metrics
        metrics = MetricRecordDict()
        await processor.process_result(metrics)

        # File should not be created for empty metrics
        assert not processor.output_file.exists()
        assert processor.record_count == 0

    async def test_error_handling_doesnt_break(
        self, user_config_records, service_config
    ):
        """Test that errors during export don't break the processor."""
        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config_records,
        )

        # Simulate an error by making output_file a directory (not a file)
        processor.output_file.parent.mkdir(parents=True, exist_ok=True)
        processor.output_file.mkdir()

        metrics = MetricRecordDict()
        metrics[TTFTMetric.tag] = 20000000

        # Should not raise exception
        await processor.process_result(metrics)

        # Record count should not increase due to error
        assert processor.record_count == 0

    async def test_shutdown_logs_statistics(self, user_config_records, service_config):
        """Test that shutdown logs final count."""
        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config_records,
        )

        # Write some records
        for _ in range(3):
            metrics = MetricRecordDict()
            metrics[TTFTMetric.tag] = 20000000
            await processor.process_result(metrics)

        # Shutdown should log count
        await processor._shutdown()
        assert processor.record_count == 3
