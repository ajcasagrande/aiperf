#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""
Tests for the dataset manager service.
"""

import pytest

from aiperf.common.enums import ServiceType
from aiperf.services.dataset_manager.dataset_manager import DatasetManager
from aiperf.tests.base_test_service import BaseServiceTest, async_fixture


@pytest.mark.asyncio
class TestDatasetManager(BaseServiceTest):
    """Tests for the dataset manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return DatasetManager

    async def test_dataset_manager_initialization(self, service_under_test):
        """Test that the dataset manager initializes correctly."""
        service = await async_fixture(service_under_test)
        assert service.service_type == ServiceType.DATASET_MANAGER
        # Add dataset manager specific assertions here
