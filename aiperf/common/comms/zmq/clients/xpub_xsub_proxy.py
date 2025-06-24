# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.comms.zmq.clients.base_zmq_proxy import BaseZMQProxy
from aiperf.common.config.zmq_config import BaseZMQProxyConfig
from aiperf.common.enums import ZMQProxyType
from aiperf.common.factories import ZMQProxyFactory


class _ProxyFrontendXSubClient(BaseZMQClient):
    """
    A XSUB socket for the proxy's frontend.

    This XSUB socket receives messages from PUB clients and forwards them
    through the proxy to XPUB services. The ZMQ proxy handles the message
    routing automatically.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        super().__init__(context, SocketType.XSUB, address, bind, socket_ops)
        self.logger.debug(f"PROXY FRONTEND XSUB - Address: {address}, Bind: {bind}")


class _ProxyBackendXPubClient(BaseZMQClient):
    """
    A XPUB socket for the proxy's backend.

    This XPUB socket forwards messages from the proxy to SUB services.
    The ZMQ proxy handles the message routing automatically.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        super().__init__(context, SocketType.XPUB, address, bind, socket_ops)
        self.logger.debug(f"PROXY BACKEND XPUB - Address: {address}, Bind: {bind}")


@ZMQProxyFactory.register(ZMQProxyType.XPUB_XSUB)
class ZMQXPubXSubProxy(BaseZMQProxy):
    """
    A ZMQ PubSub Proxy class.

    This class is responsible for creating the ZMQ proxy that forwards messages
    between PUB clients and SUB services.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        zmq_proxy_config: BaseZMQProxyConfig,
        socket_ops: dict | None = None,
    ) -> None:
        super().__init__(
            frontend_socket_class=_ProxyFrontendXSubClient,
            backend_socket_class=_ProxyBackendXPubClient,
            context=context,
            zmq_proxy_config=zmq_proxy_config,
            socket_ops=socket_ops,
        )

    @classmethod
    def from_config(
        cls,
        config: BaseZMQProxyConfig | None,
        socket_ops: dict | None = None,
    ) -> "ZMQXPubXSubProxy | None":
        if config is None:
            return None
        return cls(
            context=zmq.asyncio.Context.instance(),
            zmq_proxy_config=config,
            socket_ops=socket_ops,
        )
