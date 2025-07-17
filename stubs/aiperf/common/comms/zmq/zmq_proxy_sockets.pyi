#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete
from zmq import SocketType

from aiperf.common.comms.zmq.zmq_base_client import BaseZMQClient as BaseZMQClient
from aiperf.common.comms.zmq.zmq_proxy_base import BaseZMQProxy as BaseZMQProxy
from aiperf.common.comms.zmq.zmq_proxy_base import ProxyEndType as ProxyEndType
from aiperf.common.comms.zmq.zmq_proxy_base import (
    ProxySocketClient as ProxySocketClient,
)
from aiperf.common.comms.zmq.zmq_proxy_base import ZMQProxyFactory as ZMQProxyFactory
from aiperf.common.config._zmq import BaseZMQProxyConfig as BaseZMQProxyConfig
from aiperf.common.enums import ZMQProxyType as ZMQProxyType

def create_proxy_socket_class(
    socket_type: SocketType, end_type: ProxyEndType
) -> type[BaseZMQClient]: ...
def define_proxy_class(
    proxy_type: ZMQProxyType,
    frontend_socket_class: type[BaseZMQClient],
    backend_socket_class: type[BaseZMQClient],
) -> type[BaseZMQProxy]: ...

ZMQXPubXSubProxy: Incomplete
ZMQDealerRouterProxy: Incomplete
ZMQPushPullProxy: Incomplete
