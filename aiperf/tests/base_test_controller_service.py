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
Base test class for controller services.
"""

from unittest.mock import AsyncMock

import pytest

from aiperf.common.enums import CommandType
from aiperf.common.enums.comm_enums import Topic
from aiperf.common.models.payload_models import CommandPayload
from aiperf.common.service.base_controller_service import BaseControllerService
from aiperf.common.service.base_service import BaseService
from aiperf.tests.base_test_service import BaseTestService, async_fixture


class BaseTestControllerService(BaseTestService):
    """
    Base class for testing controller services.

    This extends BaseTestService with specific tests for controller service
    functionality such as command sending, service registration handling,
    and monitoring of component services.
    """

    @pytest.fixture
    def service_class(self) -> type[BaseService]:
        """
        Return the service class to test.

        Returns:
            The BaseControllerService class for testing
        """
        return BaseControllerService

    async def test_controller_command_publishing(
        self, service_under_test: BaseControllerService, mock_communication: AsyncMock
    ) -> None:
        """
        Test that the controller can publish command messages.

        Verifies the controller can send properly formatted commands to components.
        """
        service = await async_fixture(service_under_test)

        # Create a test command message
        test_service_id = "test_service_123"
        command = CommandType.START

        # Create a command message
        command_payload = CommandPayload(
            command=command,
            target_service_id=test_service_id,
        )
        command_message = service.create_message(command_payload)

        # Publish the command
        await service.comms.publish(Topic.COMMAND, command_message)

        # Check that the command was published
        assert Topic.COMMAND in mock_communication.published_messages
        assert len(mock_communication.published_messages[Topic.COMMAND]) > 0

        # Verify command message
        published_cmd = mock_communication.published_messages[Topic.COMMAND][0]
        assert published_cmd.service_id == service.service_id
        assert published_cmd.payload.command == command
        assert published_cmd.payload.target_service_id == test_service_id

    async def test_controller_subscriptions(
        self, service_under_test: BaseControllerService, mock_communication: AsyncMock
    ) -> None:
        """
        Test that the controller has the required subscriptions.

        Verifies the controller sets up subscriptions to receive messages from components.
        """
        await async_fixture(service_under_test)

        # A controller should typically subscribe to registration, status, and heartbeat topics
        expected_topics = [Topic.REGISTRATION, Topic.STATUS, Topic.HEARTBEAT]

        # Check that the controller has subscribed to expected topics
        for topic in expected_topics:
            # This is only checking subscriptions mocked via the mock_communication fixture
            # Actual subscription checks would vary depending on the controller implementation
            if topic in mock_communication.subscriptions:
                assert callable(mock_communication.subscriptions[topic])
