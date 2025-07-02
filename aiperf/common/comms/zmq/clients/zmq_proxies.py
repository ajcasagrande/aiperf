# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Generic, Self, TypeVar

import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.comms.zmq.clients.base_zmq_proxy import BaseZMQProxy
from aiperf.common.config.zmq_config import BaseZMQProxyConfig
from aiperf.common.enums import ZMQProxyType
from aiperf.common.factories import ZMQProxyFactory

################################################################################
# Proxy Sockets
################################################################################

SocketT = TypeVar("SocketT", bound=SocketType)
"""The type of the socket to use for the proxy."""


class ProxyBackendSocket(BaseZMQClient, Generic[SocketT]):
    """A base class for all proxy backend sockets."""

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ):
        super().__init__(context, SocketT, address, bind, socket_ops)
        self.logger.debug(
            "Proxy backend %s - Address: %s, Bind: %s",
            SocketT,
            address,
            bind,
        )


class ProxyFrontendSocket(BaseZMQClient, Generic[SocketT]):
    """A base class for all proxy frontend sockets."""

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ):
        super().__init__(context, SocketT, address, bind, socket_ops)
        self.logger.debug(
            "Proxy frontend %s - Address: %s, Bind: %s",
            SocketT,
            address,
            bind,
        )


def define_proxy_class(
    proxy_type: ZMQProxyType,
    frontend_socket_class: type[ProxyFrontendSocket[SocketT]],
    backend_socket_class: type[ProxyBackendSocket[SocketT]],
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
# XPUB/XSUB Proxy
################################################################################

ZMQXPubXSubProxy = define_proxy_class(
    ZMQProxyType.XPUB_XSUB,
    ProxyFrontendSocket[SocketType.XSUB],
    ProxyBackendSocket[SocketType.XPUB],
)
"""
An XSUB socket for the proxy's frontend and an XPUB socket for the proxy's backend.

ASCII Diagram:
┌───────────┐    ┌─────────────────────────────────┐    ┌───────────┐
│    PUB    │───>│              PROXY              │───>│    SUB    │
│  Client 1 │    │ ┌──────────┐       ┌──────────┐ │    │ Service 1 │
└───────────┘    │ │   XSUB   │──────>│   XPUB   │ │    └───────────┘
┌───────────┐    │ │ Frontend │       │ Backend  │ │    ┌───────────┐
│    PUB    │───>│ └──────────┘       └──────────┘ │───>│    SUB    │
│  Client N │    └─────────────────────────────────┘    │ Service N │
└───────────┘                                           └───────────┘

The XSUB socket receives messages from PUB clients and forwards them
through the proxy to XPUB services. The ZMQ proxy handles the message
routing automatically.

The XPUB socket forwards messages from the proxy to SUB services.
The ZMQ proxy handles the message routing automatically.
"""

################################################################################
# ROUTER/DEALER Proxy
################################################################################

ZMQRouterDealerProxy = define_proxy_class(
    ZMQProxyType.ROUTER_DEALER,
    ProxyFrontendSocket[SocketType.ROUTER],
    ProxyBackendSocket[SocketType.DEALER],
)
"""
A ROUTER socket for the proxy's frontend and a DEALER socket for the proxy's backend.

ASCII Diagram:
┌───────────┐     ┌──────────────────────────────────┐      ┌───────────┐
│  DEALER   │<───>│              PROXY               │<────>│  ROUTER   │
│  Client 1 │     │ ┌──────────┐        ┌──────────┐ │      │ Service 1 │
└───────────┘     │ │  ROUTER  │<─────> │  DEALER  │ │      └───────────┘
┌───────────┐     │ │ Frontend │        │ Backend  │ │      ┌───────────┐
│  DEALER   │<───>│ └──────────┘        └──────────┘ │<────>│  ROUTER   │
│  Client N │     └──────────────────────────────────┘      │ Service N │
└───────────┘                                               └───────────┘

The ROUTER socket receives messages from DEALER clients and forwards them
through the proxy to ROUTER services. The ZMQ proxy handles the message
routing automatically.

CRITICAL: This socket must NOT have an identity when used in a proxy
configuration, as it needs to be transparent to preserve routing envelopes
for proper response forwarding back to original DEALER clients.
"""


################################################################################
# PUSH/PULL Proxy
################################################################################

ZMQPushPullProxy = define_proxy_class(
    ZMQProxyType.PUSH_PULL,
    ProxyFrontendSocket[SocketType.PULL],
    ProxyBackendSocket[SocketType.PUSH],
)
"""
A PULL socket for the proxy's frontend and a PUSH socket for the proxy's backend.

ASCII Diagram:
┌───────────┐      ┌─────────────────────────────────┐      ┌───────────┐
│   PUSH    │─────>│              PROXY              │─────>│   PULL    │
│  Client 1 │      │ ┌──────────┐       ┌──────────┐ │      │ Service 1 │
└───────────┘      │ │   PULL   │──────>│   PUSH   │ │      └───────────┘
┌───────────┐      │ │ Frontend │       │ Backend  │ │      ┌───────────┐
│   PUSH    │─────>│ └──────────┘       └──────────┘ │─────>│   PULL    │
│  Client N │      └─────────────────────────────────┘      │ Service N │
└───────────┘                                               └───────────┘

The PULL socket receives messages from PUSH clients and forwards them
through the proxy to PUSH services. The ZMQ proxy handles the message
routing automatically.

The PUSH socket forwards messages from the proxy to PULL services.
The ZMQ proxy handles the message routing automatically.
"""
