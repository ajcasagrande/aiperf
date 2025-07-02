# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

__all__ = [
    "ZMQClient",
    "BaseZMQClient",
    "ZMQPubClient",
    "ZMQPullClient",
    "ZMQPushClient",
    "ZMQRouterRepClient",
    "ZMQDealerReqClient",
    "ZMQSubClient",
    "ZMQDealerRouterProxy",
    "ZMQXPubXSubProxy",
    "ZMQPushPullProxy",
    "BaseZMQProxy",
]

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.comms.zmq.clients.base_zmq_proxy import BaseZMQProxy
from aiperf.common.comms.zmq.clients.dealer_req import ZMQDealerReqClient
from aiperf.common.comms.zmq.clients.pub import ZMQPubClient
from aiperf.common.comms.zmq.clients.pull import ZMQPullClient
from aiperf.common.comms.zmq.clients.push import ZMQPushClient
from aiperf.common.comms.zmq.clients.router_rep import ZMQRouterRepClient
from aiperf.common.comms.zmq.clients.sub import ZMQSubClient
from aiperf.common.comms.zmq.clients.zmq_proxies import (
    ZMQDealerRouterProxy,
    ZMQPushPullProxy,
    ZMQXPubXSubProxy,
)

# Union of all the possible ZMQ client types for type checking
ZMQClient = (
    ZMQPubClient
    | ZMQSubClient
    | ZMQPullClient
    | ZMQPushClient
    | ZMQRouterRepClient
    | ZMQDealerReqClient
)
