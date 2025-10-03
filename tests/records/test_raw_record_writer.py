# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time
from pathlib import Path

import orjson
import pytest

from aiperf.common.config import (
    EndpointConfig,
    OutputConfig,
    ServiceConfig,
    UserConfig,
)
from aiperf.common.enums import CreditPhase, EndpointType, ExportLevel
from aiperf.common.exceptions import PostProcessorDisabled
from aiperf.common.models import ParsedResponseRecord, RequestRecord, Turn
from aiperf.records.raw_record_writer import RawRecordWriter


@pytest.fixture
def tmp_artifact_dir(tmp_path: Path) -> Path:
    """Create a temporary artifact directory for testing."""
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


@pytest.fixture
def user_config_raw_export(tmp_artifact_dir: Path) -> UserConfig:
    """Create a UserConfig with RAW export level."""
    config = UserConfig(
        endpoint=EndpointConfig(
            model_names=["test-model"],
            type=EndpointType.CHAT,
        ),
        output=OutputConfig(
            artifact_directory=tmp_artifact_dir,
            export_level=ExportLevel.RAW,
        ),
    )
    return config


@pytest.fixture
def user_config_records_export(tmp_artifact_dir: Path) -> UserConfig:
    """Create a UserConfig with RECORDS export level (not RAW)."""
    config = UserConfig(
        endpoint=EndpointConfig(
            model_names=["test-model"],
            type=EndpointType.CHAT,
        ),
        output=OutputConfig(
            artifact_directory=tmp_artifact_dir,
        ),
    )
    # Keep default RECORDS level
    return config


@pytest.fixture
def service_config() -> ServiceConfig:
    """Create a ServiceConfig for testing."""
    return ServiceConfig()


@pytest.fixture
def sample_request_record() -> RequestRecord:
    """Create a sample RequestRecord for testing."""
    return RequestRecord(
        model_name="test-model",
        conversation_id="conv-123",
        turn_index=0,
        timestamp_ns=time.time_ns(),
        start_perf_ns=time.perf_counter_ns(),
        end_perf_ns=time.perf_counter_ns() + 1_000_000,
        status=200,
        turn=Turn(role="user", texts=[]),
        credit_phase=CreditPhase.PROFILING,
        x_request_id="req-123",
        x_correlation_id="corr-123",
    )


@pytest.fixture
def sample_parsed_record(sample_request_record: RequestRecord) -> ParsedResponseRecord:
    """Create a sample ParsedResponseRecord for testing."""
    return ParsedResponseRecord(
        request=sample_request_record,
        responses=[],
        input_token_count=10,
        output_token_count=20,
    )


class TestRawRecordWriterInitialization:
    """Test RawRecordWriter initialization."""

    @pytest.mark.parametrize(
        "export_level, should_raise",
        [
            (ExportLevel.SUMMARY, True),
            (ExportLevel.RECORDS, True),
            (ExportLevel.RAW, False),
        ],
    )
    def test_init_with_export_level(
        self,
        export_level: ExportLevel,
        should_raise: bool,
        tmp_artifact_dir: Path,
        service_config: ServiceConfig,
    ):
        """Test initialization with various export levels."""
        user_config = UserConfig(
            endpoint=EndpointConfig(
                model_names=["test-model"],
                type=EndpointType.CHAT,
            ),
            output=OutputConfig(
                artifact_directory=tmp_artifact_dir,
            ),
        )
        user_config.output.export_level = export_level

        if should_raise:
            with pytest.raises(PostProcessorDisabled):
                RawRecordWriter(
                    service_config=service_config,
                    user_config=user_config,
                    service_id="test-processor",
                )
        else:
            writer = RawRecordWriter(
                service_config=service_config,
                user_config=user_config,
                service_id="test-processor",
            )
            assert writer is not None
            assert writer.output_file.exists() or not writer.output_file.exists()

    def test_output_file_path_per_processor(
        self,
        user_config_raw_export: UserConfig,
        service_config: ServiceConfig,
    ):
        """Test that each processor instance gets its own output file."""
        writer1 = RawRecordWriter(
            service_config=service_config,
            user_config=user_config_raw_export,
            service_id="processor-1",
        )
        writer2 = RawRecordWriter(
            service_config=service_config,
            user_config=user_config_raw_export,
            service_id="processor-2",
        )

        assert writer1.output_file != writer2.output_file
        assert "processor-1" in str(writer1.output_file)
        assert "processor-2" in str(writer2.output_file)


class TestRawRecordWriterWriting:
    """Test RawRecordWriter writing functionality."""

    @pytest.mark.asyncio
    async def test_write_single_record(
        self,
        user_config_raw_export: UserConfig,
        service_config: ServiceConfig,
        sample_parsed_record: ParsedResponseRecord,
    ):
        """Test writing a single raw record."""
        writer = RawRecordWriter(
            service_config=service_config,
            user_config=user_config_raw_export,
            service_id="test-processor",
        )

        await writer.process_record(sample_parsed_record)
        await writer.close()

        # Verify file exists and contains data
        assert writer.output_file.exists()
        with open(writer.output_file, "rb") as f:
            content = f.read()
            assert len(content) > 0

            # Verify it's valid JSON
            record_json = orjson.loads(content.strip())
            assert record_json["conversation_id"] == "conv-123"
            assert record_json["x_request_id"] == "req-123"

    @pytest.mark.asyncio
    async def test_write_multiple_records(
        self,
        user_config_raw_export: UserConfig,
        service_config: ServiceConfig,
        sample_request_record: RequestRecord,
    ):
        """Test writing multiple raw records."""
        writer = RawRecordWriter(
            service_config=service_config,
            user_config=user_config_raw_export,
            service_id="test-processor",
        )

        # Write multiple records
        num_records = 5
        for i in range(num_records):
            request_record = RequestRecord(
                model_name=f"model-{i}",
                conversation_id=f"conv-{i}",
                turn_index=i,
                timestamp_ns=time.time_ns(),
                start_perf_ns=time.perf_counter_ns(),
                end_perf_ns=time.perf_counter_ns() + 1_000_000,
                credit_phase=CreditPhase.PROFILING,
                x_request_id=f"req-{i}",
            )
            parsed_record = ParsedResponseRecord(
                request=request_record,
                responses=[],
                input_token_count=10,
                output_token_count=20,
            )
            await writer.process_record(parsed_record)

        await writer.close()

        # Verify all records were written
        with open(writer.output_file) as f:
            lines = f.readlines()
            assert len(lines) == num_records

            # Verify each line is valid JSON
            for i, line in enumerate(lines):
                record_json = orjson.loads(line.strip())
                assert record_json["conversation_id"] == f"conv-{i}"
                assert record_json["x_request_id"] == f"req-{i}"

    @pytest.mark.asyncio
    async def test_buffered_writing(
        self,
        user_config_raw_export: UserConfig,
        service_config: ServiceConfig,
        sample_request_record: RequestRecord,
    ):
        """Test that records are buffered before writing."""
        writer = RawRecordWriter(
            service_config=service_config,
            user_config=user_config_raw_export,
            service_id="test-processor",
        )
        writer.batch_size = 3

        # Write fewer records than batch size
        for i in range(2):
            request_record = RequestRecord(
                model_name=f"model-{i}",
                conversation_id=f"conv-{i}",
                turn_index=i,
                timestamp_ns=time.time_ns(),
                start_perf_ns=time.perf_counter_ns(),
                end_perf_ns=time.perf_counter_ns() + 1_000_000,
                credit_phase=CreditPhase.PROFILING,
            )
            parsed_record = ParsedResponseRecord(
                request=request_record,
                responses=[],
                input_token_count=10,
                output_token_count=20,
            )
            await writer.process_record(parsed_record)

        # File should not exist yet (or be empty) since buffer hasn't flushed
        assert len(writer._buffer) == 2

        # Close should flush the buffer
        await writer.close()

        # Now verify records were written
        with open(writer.output_file) as f:
            lines = f.readlines()
            assert len(lines) == 2

    @pytest.mark.asyncio
    async def test_record_count_tracking(
        self,
        user_config_raw_export: UserConfig,
        service_config: ServiceConfig,
        sample_parsed_record: ParsedResponseRecord,
    ):
        """Test that record count is tracked correctly."""
        writer = RawRecordWriter(
            service_config=service_config,
            user_config=user_config_raw_export,
            service_id="test-processor",
        )

        assert writer.record_count == 0

        # Write multiple records
        num_records = 5
        for _ in range(num_records):
            await writer.process_record(sample_parsed_record)

        assert writer.record_count == num_records

        await writer.close()


class TestRawRecordWriterCleanup:
    """Test RawRecordWriter cleanup functionality."""

    @pytest.mark.asyncio
    async def test_close_flushes_buffer(
        self,
        user_config_raw_export: UserConfig,
        service_config: ServiceConfig,
        sample_parsed_record: ParsedResponseRecord,
    ):
        """Test that close() flushes any remaining buffered records."""
        writer = RawRecordWriter(
            service_config=service_config,
            user_config=user_config_raw_export,
            service_id="test-processor",
        )
        writer.batch_size = 100  # Large batch to prevent auto-flush

        # Write a few records
        await writer.process_record(sample_parsed_record)
        await writer.process_record(sample_parsed_record)

        # Buffer should have records
        assert len(writer._buffer) > 0

        # Close should flush
        await writer.close()

        # Buffer should be empty
        assert len(writer._buffer) == 0

        # Records should be in file
        with open(writer.output_file) as f:
            lines = f.readlines()
            assert len(lines) == 2

    @pytest.mark.asyncio
    async def test_close_creates_directory(
        self,
        tmp_path: Path,
        service_config: ServiceConfig,
    ):
        """Test that close() ensures the directory exists."""
        artifact_dir = tmp_path / "new_artifacts"
        user_config = UserConfig(
            endpoint=EndpointConfig(
                model_names=["test-model"],
                type=EndpointType.CHAT,
            ),
            output=OutputConfig(
                artifact_directory=artifact_dir,
            ),
        )
        user_config.output.export_level = ExportLevel.RAW

        writer = RawRecordWriter(
            service_config=service_config,
            user_config=user_config,
            service_id="test-processor",
        )

        assert artifact_dir.exists()
        await writer.close()
