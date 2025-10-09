# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for the record export feature."""

import json

import pytest

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import EndpointType, ExportLevel
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.metrics.types.inter_token_latency_metric import InterTokenLatencyMetric
from aiperf.metrics.types.output_sequence_length_metric import (
    OutputSequenceLengthMetric,
)
from aiperf.metrics.types.request_latency_metric import RequestLatencyMetric
from aiperf.metrics.types.ttft_metric import TTFTMetric
from aiperf.post_processors.record_export_results_processor import (
    RecordExportResultsProcessor,
)


class TestRecordExportIntegration:
    """Integration tests for complete record export workflow."""

    @pytest.fixture
    def user_config(self, tmp_path):
        """User config with records export level."""
        return UserConfig(
            endpoint={"model_names": ["test-model"], "type": EndpointType.CHAT},
            output={
                "artifact_directory": tmp_path,
                "export_level": ExportLevel.RECORDS,
            },
        )

    @pytest.fixture
    def service_config(self):
        """Service config."""
        return ServiceConfig()

    async def test_complete_workflow(self, user_config, service_config):
        """Test complete workflow from metric creation to file export."""
        processor = RecordExportResultsProcessor(
            service_id="test-processor",
            service_config=service_config,
            user_config=user_config,
        )

        await processor._initialize()

        # Simulate benchmark with 10 requests
        for i in range(10):
            metrics = MetricRecordDict()
            # Add streaming metrics
            metrics[TTFTMetric.tag] = 15000000 + (i * 1000000)  # 15-24ms
            metrics[RequestLatencyMetric.tag] = 400000000 + (i * 10000000)  # 400-490ms
            metrics[InterTokenLatencyMetric.tag] = 11000000  # 11ms
            metrics[OutputSequenceLengthMetric.tag] = 40 + i  # 40-49 tokens

            await processor.process_result(metrics)

        await processor._shutdown()

        # Verify file exists
        assert processor.output_file.exists()
        assert processor.record_count == 10

        # Verify file content
        records = []
        with open(processor.output_file) as f:
            for line in f:
                records.append(json.loads(line))

        assert len(records) == 10

        # Verify first record
        first = records[0]
        assert TTFTMetric.tag in first
        assert first[TTFTMetric.tag]["value"] == pytest.approx(15.0)
        assert first[TTFTMetric.tag]["unit"] == "ms"
        assert first[RequestLatencyMetric.tag]["value"] == pytest.approx(400.0)

        # Verify last record
        last = records[9]
        assert last[TTFTMetric.tag]["value"] == pytest.approx(24.0)
        assert last[RequestLatencyMetric.tag]["value"] == pytest.approx(490.0)

    async def test_output_directory_created(self, tmp_path, service_config):
        """Test that output directory is created if it doesn't exist."""
        output_dir = tmp_path / "custom" / "nested" / "path"
        user_config = UserConfig(
            endpoint={"model_names": ["test"], "type": EndpointType.CHAT},
            output={
                "artifact_directory": output_dir,
                "export_level": ExportLevel.RECORDS,
            },
        )

        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config,
        )

        # Directory should be created
        assert processor.output_file.parent.exists()
        assert processor.output_file.parent.name == "record_metrics"

    async def test_file_format_is_valid_jsonl(self, user_config, service_config):
        """Test that output file is valid JSONL format."""
        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config,
        )

        # Write multiple records
        for i in range(5):
            metrics = MetricRecordDict()
            metrics[TTFTMetric.tag] = 20000000
            await processor.process_result(metrics)

        # Verify each line is valid JSON
        with open(processor.output_file) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    data = json.loads(line)
                    assert isinstance(data, dict)
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON on line {line_num}: {e}")

    async def test_metrics_have_required_fields(self, user_config, service_config):
        """Test that exported metrics have value, unit, and header fields."""
        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config,
        )

        metrics = MetricRecordDict()
        metrics[TTFTMetric.tag] = 20000000
        await processor.process_result(metrics)

        with open(processor.output_file) as f:
            data = json.loads(f.readline())

        ttft = data[TTFTMetric.tag]
        assert "value" in ttft
        assert "unit" in ttft
        assert "header" in ttft
        assert ttft["header"] == "Time to First Token"

    async def test_values_converted_to_display_units(self, user_config, service_config):
        """Test that values are properly converted from internal to display units."""
        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config,
        )

        metrics = MetricRecordDict()
        # Internal: nanoseconds, Display: milliseconds
        metrics[TTFTMetric.tag] = 18260000  # 18.26 ms
        metrics[RequestLatencyMetric.tag] = 487300000  # 487.3 ms

        await processor.process_result(metrics)

        with open(processor.output_file) as f:
            data = json.loads(f.readline())

        assert data[TTFTMetric.tag]["value"] == pytest.approx(18.26)
        assert data[TTFTMetric.tag]["unit"] == "ms"
        assert data[RequestLatencyMetric.tag]["value"] == pytest.approx(487.3)
        assert data[RequestLatencyMetric.tag]["unit"] == "ms"

    async def test_summarize_returns_empty(self, user_config, service_config):
        """Test that summarize returns empty dict (not applicable for this processor)."""
        processor = RecordExportResultsProcessor(
            service_id="test",
            service_config=service_config,
            user_config=user_config,
        )

        result = await processor.summarize()
        assert result == {}
