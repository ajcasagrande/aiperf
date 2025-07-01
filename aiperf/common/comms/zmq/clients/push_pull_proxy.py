#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import zmq.asyncio

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.comms.zmq.clients.base_zmq_proxy import BaseZMQProxy
from aiperf.common.config.zmq_config import BaseZMQProxyConfig
from aiperf.common.enums import ZMQProxyType
from aiperf.common.factories import ZMQProxyFactory


class _ProxyFrontendPullClient(BaseZMQClient):
    """PULL socket for the proxy's frontend - receives from workers."""

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ):
        super().__init__(context, zmq.SocketType.PULL, address, bind, socket_ops)
        self.logger.debug(f"PROXY FRONTEND PULL - Address: {address}, Bind: {bind}")


class _ProxyBackendPushClient(BaseZMQClient):
    """PUSH socket for the proxy's backend - sends to RecordsManagers."""

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ):
        super().__init__(context, zmq.SocketType.PUSH, address, bind, socket_ops)
        self.logger.debug(f"PROXY BACKEND PUSH - Address: {address}, Bind: {bind}")


@ZMQProxyFactory.register(ZMQProxyType.PUSH_PULL)
class ZMQPushPullProxy(BaseZMQProxy):
    """ZMQ Push-Pull Proxy for load balancing inference results."""

    def __init__(
        self,
        context: zmq.asyncio.Context,
        zmq_proxy_config: BaseZMQProxyConfig,
        socket_ops: dict | None = None,
    ) -> None:
        super().__init__(
            context=context,
            frontend_socket_class=_ProxyFrontendPullClient,
            backend_socket_class=_ProxyBackendPushClient,
            zmq_proxy_config=zmq_proxy_config,
            socket_ops=socket_ops,
        )

    @classmethod
    def from_config(
        cls,
        config: BaseZMQProxyConfig | None,
        socket_ops: dict | None = None,
    ) -> "ZMQPushPullProxy | None":
        if config is None:
            return None
        return cls(
            context=zmq.asyncio.Context.instance(),
            zmq_proxy_config=config,
            socket_ops=socket_ops,
        )
