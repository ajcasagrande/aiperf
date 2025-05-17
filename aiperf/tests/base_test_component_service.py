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
import pytest

from aiperf.app.service.base_component_service import BaseComponentService
from aiperf.common.enums.comm_enums import Topic
from aiperf.common.enums.service_enums import ServiceState
from aiperf.tests.base_test_service import BaseTestService, async_fixture


class BaseTestComponentService(BaseTestService):
    """Base class for testing component services."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return BaseComponentService

    async def test_service_heartbeat(self, service_under_test, mock_communication):
        """Test that the service sends heartbeat messages."""
        service = await async_fixture(service_under_test)

        # Directly send a heartbeat instead of waiting for the task
        await service.send_heartbeat()

        # Check that a heartbeat response was published
        assert Topic.HEARTBEAT in mock_communication.published_messages
        assert len(mock_communication.published_messages[Topic.HEARTBEAT]) > 0

    async def test_service_registration(self, service_under_test, mock_communication):
        """Test that the service registers with the system controller."""
        service = await async_fixture(service_under_test)

        # Register the service
        await service.register()

        # Check that a registration response was published
        assert Topic.REGISTRATION in mock_communication.published_messages

        # Verify registration response
        registration_msg = mock_communication.published_messages[Topic.REGISTRATION][0]
        assert registration_msg.service_id == service.service_id
        assert registration_msg.payload.service_type == service.service_type

    async def test_service_status_update(self, service_under_test, mock_communication):
        """Test that the service updates its status."""
        service = await async_fixture(service_under_test)

        # Update the service status
        await service.set_state(ServiceState.READY)

        # Check that a status response was published
        assert Topic.STATUS in mock_communication.published_messages

        # Verify status response
        status_msg = mock_communication.published_messages[Topic.STATUS][0]
        assert status_msg.service_id == service.service_id
        assert status_msg.payload.service_type == service.service_type
        assert status_msg.payload.state == ServiceState.READY
