# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import MagicMock, patch

import pytest

from aiperf.common.config import EndPointConfig
from aiperf.common.models import ProfileResultsMessage, ResultsRecord
from aiperf.data_exporter.exporter_manager import ExporterManager


@pytest.fixture
def endpoint_config():
    return EndPointConfig(type="llm", streaming=True)


@pytest.fixture
def sample_records():
    return ProfileResultsMessage(
        records=[ResultsRecord(name="Latency", unit="ms", avg=10.0)],
        service_id="test-service",
        total=100,
        completed=100,
    )


class TestExporterManager:
    async def test_export(self, endpoint_config, sample_records):
        mock_exporter_instance = MagicMock()
        mock_exporter_class = MagicMock(return_value=mock_exporter_instance)

        with patch(
            "aiperf.common.factories.DataExporterFactory.get_all_classes",
            return_value=[mock_exporter_class],
        ):
            manager = ExporterManager(endpoint_config)
            await manager.export(sample_records)

        mock_exporter_class.assert_called_once_with(endpoint_config)
        mock_exporter_instance.export.assert_called_once_with(sample_records)
