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
Shared fixtures for testing AIPerf services.

`conftest.py` is a special file that pytest automatically recognizes and
loads before running tests. The main purpose of is to define fixtures that
can be shared across multiple test files. Fixtures defined in this file
are automatically discovered by pytest and made available to test functions
in the same directory and subdirectories.

You can have multiple `conftest.py` files in different directories.
Each one affects tests in its directory and subdirectories.
"""

from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest

from aiperf.common.comms.base_communication import BaseCommunication
from aiperf.common.models.message_models import BaseMessage


@pytest.fixture
def mock_communication() -> AsyncMock:
    """Create a mock communication object with publishing and subscription tracking."""
    mock_comm = AsyncMock(spec=BaseCommunication)

    # Configure basic returns for methods
    mock_comm.initialize.return_value = True
    mock_comm.subscribe.return_value = True
    mock_comm.publish.return_value = True
    mock_comm.pull.return_value = True
    mock_comm.push.return_value = True
    mock_comm.shutdown.return_value = True
    mock_comm.is_initialized = True
    mock_comm.is_shutdown = False
    mock_comm.create_clients.return_value = True

    # Store published messages for verification
    mock_comm.published_messages: dict[Any, list[BaseMessage]] = {}

    async def mock_publish(topic: Any, message: BaseMessage) -> None:
        # Use the topic as the key, whether it's an enum or string
        topic_key = topic

        # Initialize list for this topic if needed
        if topic_key not in mock_comm.published_messages:
            mock_comm.published_messages[topic_key] = []

        # Store the response
        mock_comm.published_messages[topic_key].append(message)

    mock_comm.publish.side_effect = mock_publish

    # Store subscription callbacks
    mock_comm.subscriptions: dict[str, Callable] = {}

    async def mock_subscribe(topic: str, callback: Callable) -> None:
        mock_comm.subscriptions[topic] = callback

    mock_comm.subscribe.side_effect = mock_subscribe

    return mock_comm
