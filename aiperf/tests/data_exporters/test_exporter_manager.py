# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiperf.common.config import EndPointConfig, OutputConfig, UserConfig
from aiperf.common.messages import ProfileResultsMessage
from aiperf.common.record_models import MetricResult
from aiperf.data_exporter.exporter_manager import ExporterManager


@pytest.fixture
def endpoint_config():
    return EndPointConfig(type="llm", streaming=True)


@pytest.fixture
def output_config(tmp_path):
    return OutputConfig(artifact_directory=tmp_path)


@pytest.fixture
def sample_results():
    return ProfileResultsMessage(
        start_ns=1000,
        end_ns=2000,
        records=[MetricResult(tag="Latency", unit="ms", avg=10.0)],
        service_id="test-service",
        total=100,
        completed=100,
    )


@pytest.fixture
def mock_user_config(endpoint_config, output_config):
    config = UserConfig()
    config.endpoint = endpoint_config
    config.output = output_config
    return config


class TestExporterManager:
    async def test_export_all(
        self, mock_user_config: UserConfig, sample_results: ProfileResultsMessage
    ):
        mock_exporter_instance = AsyncMock()
        mock_exporter_class = MagicMock(return_value=mock_exporter_instance)

        with patch(
            "aiperf.common.factories.DataExporterFactory.get_all_classes",
            return_value=[mock_exporter_class],
        ):
            manager = ExporterManager(
                results=sample_results,
                input_config=mock_user_config,
            )
            await manager.export_all()

        mock_exporter_class.assert_called_once()
        mock_exporter_instance.export.assert_called_once()
