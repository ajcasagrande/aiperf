# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import MagicMock, patch

import pytest

from aiperf.common.config import EndPointConfig, OutputConfig, UserConfig
from aiperf.common.enums import EndpointType
from aiperf.common.models import MetricResult
from aiperf.data_exporter.exporter_manager import ExporterManager


@pytest.fixture
def endpoint_config():
    return EndPointConfig(
        type=EndpointType.OPENAI_CHAT_COMPLETIONS,
        streaming=True,
        model_names=["test-model"],
    )


@pytest.fixture
def output_config(tmp_path):
    return OutputConfig(artifact_directory=tmp_path)


@pytest.fixture
def sample_records():
    return [
        MetricResult(
            tag="Latency",
            unit="ms",
            avg=10.0,
            header="test-header",
        )
    ]


@pytest.fixture
def mock_user_config(endpoint_config, output_config):
    return UserConfig(endpoint=endpoint_config, output=output_config)


class TestExporterManager:
    @pytest.mark.asyncio
    async def test_export(self, sample_records, mock_user_config):
        mock_exporter_instance = MagicMock()
        mock_exporter_class = MagicMock(return_value=mock_exporter_instance)

        with patch(
            "aiperf.common.factories.DataExporterFactory.get_all_classes",
            return_value=[mock_exporter_class],
        ):
            manager = ExporterManager(
                results=sample_records,
                input_config=mock_user_config,
            )
            await manager.export_all()
        mock_exporter_class.assert_called_once()
        mock_exporter_instance.export.assert_called_once()
