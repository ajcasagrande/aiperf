# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Self

import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.comms.zmq.clients.base_zmq_proxy import BaseZMQProxy
from aiperf.common.config.zmq_config import BaseZMQProxyConfig
from aiperf.common.enums import ZMQProxyType
from aiperf.common.factories import ZMQProxyFactory


def define_proxy_class(
    proxy_type: ZMQProxyType,
    frontend_socket_class: type[BaseZMQClient],
    backend_socket_class: type[BaseZMQClient],
) -> type[BaseZMQProxy]:
    """This function generates a ZMQ Proxy class definition for a given proxy type, frontend socket class, and backend socket class.
    It reduces the boilerplate code required to create a ZMQ Proxy class.

    Args:
        proxy_type: The type of proxy to generate.
        frontend_socket_class: The class of the frontend socket.
        backend_socket_class: The class of the backend socket.

    Returns:
        A ZMQ Proxy class.
    """

    @ZMQProxyFactory.register(proxy_type)
    class ZMQProxy(BaseZMQProxy):
        """
        A Generated ZMQ Proxy class.

        This class is responsible for creating the ZMQ proxy that forwards messages
        between frontend and backend sockets.
        """

        def __init__(
            self,
            context: zmq.asyncio.Context,
            zmq_proxy_config: BaseZMQProxyConfig,
            socket_ops: dict | None = None,
        ) -> None:
            super().__init__(
                frontend_socket_class=frontend_socket_class,
                backend_socket_class=backend_socket_class,
                context=context,
                zmq_proxy_config=zmq_proxy_config,
                socket_ops=socket_ops,
            )

        @classmethod
        def from_config(
            cls,
            config: BaseZMQProxyConfig | None,
            socket_ops: dict | None = None,
        ) -> Self | None:
            if config is None:
                return None
            return cls(
                context=zmq.asyncio.Context.instance(),
                zmq_proxy_config=config,
                socket_ops=socket_ops,
            )


################################################################################
# XPUB XSUB Proxy
################################################################################


class _ProxyFrontendXSubClient(BaseZMQClient):
    """
    An XSUB socket for the proxy's frontend.

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
        self.logger.debug(
            "Proxy frontend XSUB - Address: %s, Bind: %s",
            address,
            bind,
        )


class _ProxyBackendXPubClient(BaseZMQClient):
    """
    An XPUB socket for the proxy's backend.

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
        self.logger.debug(
            "Proxy backend XPUB - Address: %s, Bind: %s",
            address,
            bind,
        )


ZMQXPubXSubProxy = define_proxy_class(
    ZMQProxyType.XPUB_XSUB,
    _ProxyFrontendXSubClient,
    _ProxyBackendXPubClient,
)


################################################################################
# Dealer Router Proxy
################################################################################


class _ProxyFrontendRouterClient(BaseZMQClient):
    """
    A ROUTER socket for the proxy's frontend.

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
        self.logger.debug(
            "Proxy frontend ROUTER - Address: %s, Bind: %s",
            address,
            bind,
        )


class _ProxyBackendDealerClient(BaseZMQClient):
    """
    A DEALER socket for the proxy's backend.

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
        # NOTE: DO NOT set identity for backend DEALER in proxy configuration
        # The proxy needs this socket to be transparent for proper routing envelope forwarding

        super().__init__(context, SocketType.DEALER, address, bind, socket_ops)
        self.logger.debug(
            "Proxy backend DEALER - Address: %s, Bind: %s, Identity: None (transparent for proxy)",
            address,
            bind,
        )


ZMQDealerRouterProxy = define_proxy_class(
    ZMQProxyType.DEALER_ROUTER,
    _ProxyFrontendRouterClient,
    _ProxyBackendDealerClient,
)


################################################################################
# Push Pull Proxy
################################################################################


class _ProxyFrontendPullClient(BaseZMQClient):
    """PULL socket for the proxy's frontend."""

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ):
        super().__init__(context, zmq.SocketType.PULL, address, bind, socket_ops)
        self.logger.debug(
            "Proxy frontend PULL - Address: %s, Bind: %s",
            address,
            bind,
        )


class _ProxyBackendPushClient(BaseZMQClient):
    """PUSH socket for the proxy's backend."""

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ):
        super().__init__(context, zmq.SocketType.PUSH, address, bind, socket_ops)
        self.logger.debug(
            "Proxy backend PUSH - Address: %s, Bind: %s",
            address,
            bind,
        )


ZMQPushPullProxy = define_proxy_class(
    ZMQProxyType.PUSH_PULL,
    _ProxyFrontendPullClient,
    _ProxyBackendPushClient,
)
