# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum


class CommunicationBackend(CaseInsensitiveStrEnum):
    """Supported communication backends."""

    ZMQ_TCP = "zmq_tcp"
    """ZeroMQ backend using TCP sockets."""

    ZMQ_IPC = "zmq_ipc"
    """ZeroMQ backend using IPC sockets."""


class CommunicationClientType(CaseInsensitiveStrEnum):
    """Enum for specifying the communication client type for communication clients."""

    PUB = "pub"
    SUB = "sub"
    PUSH = "push"
    PULL = "pull"
    REQUEST = "request"
    REPLY = "reply"


class CommunicationClientAddressType(CaseInsensitiveStrEnum):
    """Enum for specifying the address type for communication clients.
    This is used to lookup the address in the communication config."""

    EVENT_BUS_PROXY_FRONTEND = "event_bus_proxy_frontend"
    """Frontend address for services to publish messages to."""

    EVENT_BUS_PROXY_BACKEND = "event_bus_proxy_backend"
    """Backend address for services to subscribe to messages."""

    CREDIT_DROP = "credit_drop"
    """Address to send CreditDrop messages from the TimingManager to the Worker."""

    CREDIT_RETURN = "credit_return"
    """Address to send CreditReturn messages from the Worker to the TimingManager."""

    RECORDS = "records"
    """Address to send parsed records from InferenceParser to RecordManager."""

    DATASET_MANAGER_PROXY_FRONTEND = "dataset_manager_proxy_frontend"
    """Frontend address for sending requests to the DatasetManager."""

    DATASET_MANAGER_PROXY_BACKEND = "dataset_manager_proxy_backend"
    """Backend address for the DatasetManager to receive requests from clients."""

    RAW_INFERENCE_PROXY_FRONTEND = "raw_inference_proxy_frontend"
    """Frontend address for sending raw inference messages to the InferenceParser from Workers."""

    RAW_INFERENCE_PROXY_BACKEND = "raw_inference_proxy_backend"
    """Backend address for the InferenceParser to receive raw inference messages from Workers."""


#     @classmethod
#     def from_message_type(cls, message_type: MessageType) -> "CommunicationClientAddressType":
#         """Get the address type for a given message type."""
#         if message_type in [MessageType.CONVERSATION_REQUEST, MessageType.CONVERSATION_TURN_REQUEST, MessageType.DATASET_TIMING_REQUEST]:
#             return cls.DATASET_MANAGER_PROXY_BACKEND
#         elif message_type in [MessageType.INFERENCE_RESULTS, MessageType.PARSED_INFERENCE_RESULTS]:
#             return cls.RAW_INFERENCE_PROXY_BACKEND
#         else:
#             raise ValueError(f"No address type found for message type: {message_type}")


# class PubClientType(CaseInsensitiveStrEnum):
#     """Types of pub clients."""
#     EVENT_BUS = "event_bus"
#     DATASET_MANAGER = "dataset_manager"
#     INFERENCE_PARSER = "inference_parser"
#     RECORD_MANAGER = "record_manager"
#     WORKER = "worker"


# class PullClientType(CaseInsensitiveStrEnum):
#     """Types of pull clients."""
#     EVENT_BUS = "event_bus"
#     DATASET_MANAGER = "dataset_manager"
#     INFERENCE_PARSER = "inference_parser"
#     RECORD_MANAGER = "record_manager"
#     WORKER = "worker"


class ZMQProxyType(CaseInsensitiveStrEnum):
    """Types of ZMQ proxies."""

    DEALER_ROUTER = "dealer_router"
    XPUB_XSUB = "xpub_xsub"
    PUSH_PULL = "push_pull"
