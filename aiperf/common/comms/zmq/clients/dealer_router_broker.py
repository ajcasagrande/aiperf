#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.comms.zmq.clients.base_zmq_broker import BaseZMQBroker
from aiperf.common.config.zmq_config import BaseZMQProxyConfig
from aiperf.common.enums import ZMQBrokerType
from aiperf.common.factories import ZMQBrokerFactory


class _BrokerFrontendRouterClient(BaseZMQClient):
    """
    A ROUTER socket for the broker's frontend.

    This ROUTER socket receives messages from DEALER clients and forwards them
    through the proxy to ROUTER services. The ZMQ proxy handles the message
    routing automatically.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        super().__init__(context, SocketType.ROUTER, address, bind, socket_ops)
        self.logger.debug(f"BROKER FRONTEND ROUTER - Address: {address}, Bind: {bind}")

    def send_message(self, message: str) -> None:
        self.socket.send_multipart([b"", message.encode()])


class _BrokerBackendDealerClient(BaseZMQClient):
    """
    A DEALER socket for the broker's backend.

    This DEALER socket forwards messages from the proxy to ROUTER services.
    The ZMQ proxy handles the message routing automatically.

    CRITICAL: This socket must NOT have an identity when used in a proxy
    configuration, as it needs to be transparent to preserve routing envelopes
    for proper response forwarding back to original DEALER clients.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        # DO NOT set identity for backend DEALER in proxy configuration
        # The proxy needs this socket to be transparent for proper routing envelope forwarding

        super().__init__(context, SocketType.DEALER, address, bind, socket_ops)
        self.logger.debug(
            f"BROKER BACKEND DEALER - Address: {address}, Bind: {bind}, Identity: None (transparent for proxy)"
        )


@ZMQBrokerFactory.register(ZMQBrokerType.DEALER_ROUTER)
class ZMQDealerRouterBroker(BaseZMQBroker):
    """
    A ZMQ Dealer Router Broker class.

    This class is responsible for creating the ZMQ proxy that forwards messages
    between DEALER clients and ROUTER services.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        zmq_proxy_config: BaseZMQProxyConfig,
        socket_ops: dict | None = None,
    ) -> None:
        super().__init__(
            frontend_socket_class=_BrokerFrontendRouterClient,
            backend_socket_class=_BrokerBackendDealerClient,
            context=context,
            zmq_proxy_config=zmq_proxy_config,
            socket_ops=socket_ops,
        )

    @classmethod
    def from_config(
        cls,
        config: BaseZMQProxyConfig | None,
        socket_ops: dict | None = None,
    ) -> "ZMQDealerRouterBroker | None":
        if config is None:
            return None
        return cls(
            context=zmq.asyncio.Context.instance(),
            zmq_proxy_config=config,
            socket_ops=socket_ops,
        )
