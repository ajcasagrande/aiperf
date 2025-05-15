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
Tests for the post processor manager service.
"""

import pytest

from aiperf.common.enums import ServiceType
from aiperf.services.post_processor_manager.post_processor_manager import (
    PostProcessorManager,
)
from aiperf.tests.base_test_component_service import BaseTestComponentService
from aiperf.tests.utils.async_test_utils import async_fixture


@pytest.mark.asyncio
class TestPostProcessorManager(BaseTestComponentService):
    """Tests for the post processor manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return PostProcessorManager

    async def test_post_processor_manager_initialization(self, service_under_test):
        """Test that the post processor manager initializes correctly."""
        service = await async_fixture(service_under_test)
        assert service.service_type == ServiceType.POST_PROCESSOR_MANAGER
        # Add post processor manager specific assertions here
