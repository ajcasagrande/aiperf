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
import asyncio
import logging

import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.exceptions.comms import CommunicationError


class DealerRouterBroker:
    """
    A ZMQ Dealer Router Broker class.

    This class is responsible for creating the ZMQ clients and starting the proxy.
    It also handles the initialization and shutdown of the clients.

    The proxy is started in a separate thread using asyncio.to_thread.
    This is because the proxy is a blocking operation and we want to avoid blocking the main thread.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        router_address: str,
        dealer_address: str,
        control_address: str | None = None,
        capture_address: str | None = None,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Dealer Router Broker class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            router_address (str): The router address to bind to.
            dealer_address (str): The dealer address to bind to.
            control_address (str, optional): The control address to bind to.
            capture_address (str, optional): The capture address to bind to.
            socket_ops (dict, optional): Additional socket options to set.
        """
        self.logger = logging.getLogger(__name__)
        self.context = context
        self.logger.info(
            f"Initializing DealerRouterBroker with router_address: {router_address} and dealer_address: {dealer_address}"
        )
        self.router_address = router_address
        self.dealer_address = dealer_address
        self.control_address = control_address
        self.capture_address = capture_address
        self.socket_ops = socket_ops

        self.dealer_client = BaseZMQClient(
            self.context,
            SocketType.DEALER,
            self.dealer_address,
            bind=True,
            socket_ops=self.socket_ops,
        )
        self.router_client = BaseZMQClient(
            self.context,
            SocketType.ROUTER,
            self.router_address,
            bind=True,
            socket_ops=self.socket_ops,
        )
        if self.control_address:
            self.control_client = BaseZMQClient(
                self.context,
                SocketType.REP,
                self.control_address,
                bind=True,
                socket_ops=self.socket_ops,
            )
        if self.capture_address:
            self.capture_client = BaseZMQClient(
                self.context,
                SocketType.PUB,
                self.capture_address,
                bind=True,
                socket_ops=self.socket_ops,
            )

        self.proxy: zmq.asyncio.Socket | None = None

    async def _initialize(self) -> None:
        """Initialize and start the DealerRouterBroker."""

        await asyncio.gather(
            self.dealer_client.initialize(),
            self.router_client.initialize(),
            *[
                client.initialize()
                for client in [self.control_client, self.capture_client]
                if client
            ],
        )

    async def _shutdown(self) -> None:
        """Shutdown the DealerRouterBroker."""
        await asyncio.gather(
            self.dealer_client.shutdown(),
            self.router_client.shutdown(),
            *[
                client.shutdown()
                for client in [self.control_client, self.capture_client]
                if client
            ],
        )

    async def run(self) -> None:
        """Start the ZMQ Dealer Router Proxy.

        This method starts the proxy and waits for it to complete asynchronously.

        Raises:
            CommunicationError: If the proxy produces an error.
        """
        try:
            await self._initialize()

            await asyncio.to_thread(
                zmq.proxy_steerable,
                self.dealer_client.socket,
                self.router_client.socket,
                capture=self.capture_client.socket if self.capture_client else None,
                control=self.control_client.socket if self.control_client else None,
            )
        except Exception as e:
            self.logger.error("Exception in DealerRouterBroker: %s", e)
            raise CommunicationError from e
        finally:
            await self._shutdown()
