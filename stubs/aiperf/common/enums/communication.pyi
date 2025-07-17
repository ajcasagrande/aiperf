#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums.base import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum

class CommunicationBackend(CaseInsensitiveStrEnum):
    ZMQ_TCP = "zmq_tcp"
    ZMQ_IPC = "zmq_ipc"

class CommunicationClientType(CaseInsensitiveStrEnum):
    PUB = "pub"
    SUB = "sub"
    PUSH = "push"
    PULL = "pull"
    REQUEST = "request"
    REPLY = "reply"

class CommunicationClientAddressType(CaseInsensitiveStrEnum):
    EVENT_BUS_PROXY_FRONTEND = "event_bus_proxy_frontend"
    EVENT_BUS_PROXY_BACKEND = "event_bus_proxy_backend"
    CREDIT_DROP = "credit_drop"
    CREDIT_RETURN = "credit_return"
    RECORDS = "records"
    DATASET_MANAGER_PROXY_FRONTEND = "dataset_manager_proxy_frontend"
    DATASET_MANAGER_PROXY_BACKEND = "dataset_manager_proxy_backend"
    RAW_INFERENCE_PROXY_FRONTEND = "raw_inference_proxy_frontend"
    RAW_INFERENCE_PROXY_BACKEND = "raw_inference_proxy_backend"

class ZMQProxyType(CaseInsensitiveStrEnum):
    DEALER_ROUTER = "dealer_router"
    XPUB_XSUB = "xpub_xsub"
    PUSH_PULL = "push_pull"
