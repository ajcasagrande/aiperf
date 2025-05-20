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

This file contains fixtures that are automatically discovered by pytest
and made available to test functions in the same directory and subdirectories.
"""

# Now we can safely import the rest
from collections.abc import Callable, Coroutine  # noqa: E402
from typing import Any  # noqa: E402
from unittest.mock import MagicMock, patch

import pytest  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from aiperf.common.comms.zmq_comms.zmq_communication import ZMQCommunication
from aiperf.common.enums.comm_enums import Topic  # noqa: E402
from aiperf.common.models.message_models import Message  # noqa: E402
from aiperf.tests.mock_zmq import MockZMQContext, MockZMQSocket

# # Just in case, apply the patch again in the fixture to ensure it's maintained
# @pytest.fixture(scope="session", autouse=True)
# def patch_zmq():
#     """Patch ZMQ to prevent any actual network connections."""
#     with patch.dict("sys.modules", {"zmq": mock_zmq, "zmq.asyncio": mock_zmq.asyncio}):
#         yield


@pytest.fixture
def mock_zmq_socket():
    """Fixture to provide a mock ZMQ socket."""
    with patch("zmq.Socket", new_callable=MockZMQSocket):
        yield MockZMQSocket()


@pytest.fixture
def mock_zmq_context():
    """Fixture to provide a mock ZMQ context."""
    with patch("zmq.Context", new_callable=MockZMQContext):
        yield MockZMQContext()


class MockCommData(BaseModel):
    """Data structure to hold state for mock communication objects."""

    published_messages: dict[Topic, list[Message]] = Field(default_factory=dict)
    subscriptions: dict[str, Callable[[Message], Coroutine[Any, Any, None]]] = Field(
        default_factory=dict
    )
    is_initialized: bool = True
    is_shutdown: bool = False


@pytest.fixture
def mock_communication() -> MagicMock:
    """
    Create a mock communication object for testing service communication.

    This mock tracks published messages and subscriptions for verification in tests.

    Returns:
        An AsyncMock configured to behave like ZMQCommunication
    """
    mock_comm = MagicMock(spec=ZMQCommunication)

    # Configure basic behavior
    mock_comm.initialize.return_value = None
    mock_comm.pull.return_value = None
    mock_comm.push.return_value = None
    mock_comm.shutdown.return_value = None
    mock_comm.create_clients.return_value = None

    # Configure state properties
    # mock_comm.initialized_event.set()
    # mock_comm.shutdown_event.clear()

    # Store published messages for verification
    mock_comm.published_messages = {}

    async def mock_publish(topic: Topic, message: Message) -> None:
        """Mock implementation of publish that stores messages by topic."""
        if topic not in mock_comm.published_messages:
            mock_comm.published_messages[topic] = []

        mock_comm.published_messages[topic].append(message)

    mock_comm.publish.side_effect = mock_publish

    # Store subscription callbacks
    mock_comm.subscriptions = {}

    async def mock_subscribe(
        topic: str, callback: Callable[[Message], Coroutine[Any, Any, None]]
    ) -> None:
        """Mock implementation of subscribe that stores callbacks by topic."""
        mock_comm.subscriptions[topic] = callback

    mock_comm.subscribe.side_effect = mock_subscribe

    return mock_comm


# @pytest.fixture(autouse=True)
# def block_zmq_imports(monkeypatch):
#     """
#     Block imports of ZMQ and related modules during tests.

#     Some code might attempt to import ZMQ dynamically during test execution.
#     This fixture ensures those imports fail safely to prevent actual network connections.
#     """

#     def mock_import(name, *args, **kwargs):
#         if name.startswith("zmq"):
#             if name == "zmq":
#                 return MockZMQ()
#             elif name == "zmq.asyncio":
#                 return MockZMQ().asyncio
#             else:
#                 # For other zmq submodules, return an empty module
#                 import types

#                 return types.ModuleType(name)
#         return orig_import(name, *args, **kwargs)

#     orig_import = __import__
#     monkeypatch.setattr("builtins.__import__", mock_import)
