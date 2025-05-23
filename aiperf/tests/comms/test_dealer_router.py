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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import zmq.asyncio

from aiperf.common.comms.zmq.clients.dealer_router import DealerRouterBroker
from aiperf.common.exceptions.comms import CommunicationError


@pytest.fixture
def zmq_context():
    return MagicMock(spec=zmq.asyncio.Context)


@pytest.fixture
def addresses():
    return {
        "router_address": "tcp://127.0.0.1:5555",
        "dealer_address": "tcp://127.0.0.1:5556",
        "control_address": "tcp://127.0.0.1:5557",
        "capture_address": "tcp://127.0.0.1:5558",
    }


@pytest.fixture
def broker(zmq_context, addresses):
    with patch(
        "aiperf.common.comms.zmq.clients.dealer_router.BaseZMQClient"
    ) as MockClient:
        # Mock all BaseZMQClient instances and their async methods
        mock_client = MagicMock()
        mock_client.initialize = AsyncMock()
        mock_client.shutdown = AsyncMock()
        mock_client.socket = MagicMock()
        MockClient.return_value = mock_client
        yield DealerRouterBroker(
            zmq_context,
            addresses["router_address"],
            addresses["dealer_address"],
            addresses["control_address"],
            addresses["capture_address"],
            socket_ops=None,
        )


@pytest.mark.asyncio
async def test_initialize_calls_all_clients(broker):
    await broker._initialize()
    assert broker.dealer_client.initialize.called
    assert broker.router_client.initialize.called
    assert broker.control_client.initialize.called
    assert broker.capture_client.initialize.called


@pytest.mark.asyncio
async def test_shutdown_calls_all_clients(broker):
    await broker._shutdown()
    assert broker.dealer_client.shutdown.called
    assert broker.router_client.shutdown.called
    assert broker.control_client.shutdown.called
    assert broker.capture_client.shutdown.called


@pytest.mark.asyncio
async def test_run_success(broker):
    with patch(
        "aiperf.common.comms.zmq.clients.dealer_router.zmq.proxy_steerable"
    ) as mock_proxy:
        mock_proxy.return_value = None
        with patch("asyncio.to_thread", new=AsyncMock()):
            await broker.run()
    assert broker.dealer_client.initialize.called
    assert broker.router_client.initialize.called
    assert broker.control_client.initialize.called
    assert broker.capture_client.initialize.called
    assert broker.dealer_client.shutdown.called
    assert broker.router_client.shutdown.called
    assert broker.control_client.shutdown.called
    assert broker.capture_client.shutdown.called


@pytest.mark.asyncio
async def test_run_raises_communication_error(broker):
    with (
        patch(
            "aiperf.common.comms.zmq.clients.dealer_router.zmq.proxy_steerable",
            side_effect=RuntimeError("fail"),
        ),
        patch("asyncio.to_thread", new=AsyncMock(side_effect=RuntimeError("fail"))),
        pytest.raises(CommunicationError),
    ):
        await broker.run()
    # Ensure shutdown is still called
    assert broker.dealer_client.shutdown.called
    assert broker.router_client.shutdown.called
    assert broker.control_client.shutdown.called
    assert broker.capture_client.shutdown.called


def test_broker_initialization_logs(addresses, zmq_context, caplog):
    with patch("aiperf.common.comms.zmq.clients.dealer_router.BaseZMQClient"):
        with caplog.at_level("INFO"):
            DealerRouterBroker(
                zmq_context,
                addresses["router_address"],
                addresses["dealer_address"],
                addresses["control_address"],
                addresses["capture_address"],
            )
        assert "Initializing DealerRouterBroker" in caplog.text
