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
from enum import Enum


class StrEnum(str, Enum):
    """Base class for string-based enums.

    Using this as a base class allows enum values to be used directly as
    strings without having to use .value.
    """

    def __str__(self) -> str:
        return self.value


class ServiceState(StrEnum):
    """States a service can be in throughout its lifecycle."""

    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


# Message-related enums
class MessageType(StrEnum):
    """Types of messages exchanged between services."""

    UNKNOWN = "unknown"
    REGISTRATION = "registration"
    HEARTBEAT = "heartbeat"
    COMMAND = "command"
    RESPONSE = "response"
    STATUS = "status"
    DATA = "data"
    ERROR = "error"
    CONVERSATION = "conversation"
    RESULT = "result"
    WORKER_REQUEST = "worker_request"
    WORKER_RESPONSE = "worker_response"
    CREDIT_DROP = "credit_drop"
    CREDIT_RETURN = "credit_return"


class CommandType(StrEnum):
    """Commands that can be sent to services."""

    START = "start"
    STOP = "stop"
    CONFIGURE = "configure"
    STATUS = "status"


# Communication-related enums
class Topic(StrEnum):
    """Communication topics for the main message bus."""

    CREDIT_DROP = "credit_drop"
    CREDIT_RETURN = "credit_return"
    REGISTRATION = "registration"
    COMMAND = "command"
    RESPONSE = "response"
    DATA = "data"
    STATUS = "status"
    HEARTBEAT = "heartbeat"


class DataTopic(StrEnum):
    """Specific data topics for different service domains."""

    DATASET = "dataset_data"
    TIMING = "timing_data"
    RECORDS = "records_data"
    WORKER = "worker_data"
    POST_PROCESSOR = "post_processor_data"
    CREDIT = "credit"
    RESULTS = "results"
    METRICS = "metrics"


class CommBackend(StrEnum):
    """Supported communication backends."""

    ZMQ_TCP = "zmq_tcp"


# Service-related enums
class ServiceRunType(StrEnum):
    """Different ways to run a service."""

    MULTIPROCESSING = "process"
    KUBERNETES = "k8s"


class ServiceType(StrEnum):
    """Types of services in the AIPerf system."""

    SYSTEM_CONTROLLER = "system_controller"
    DATASET_MANAGER = "dataset_manager"
    TIMING_MANAGER = "timing_manager"
    WORKER_MANAGER = "worker_manager"
    RECORDS_MANAGER = "records_manager"
    POST_PROCESSOR_MANAGER = "post_processor_manager"
    WORKER = "worker"
    TEST = "test_service"  # Used in tests


class ClientType(StrEnum):
    """Enum for communication client types based on service needs."""

    CONTROLLER_PUB = "controller_pub"
    CONTROLLER_SUB = "controller_sub"

    COMPONENT_PUB = "component_pub"
    COMPONENT_SUB = "component_sub"

    RECORDS_PUSH = "records_push"
    RECORDS_PULL = "records_pull"

    CONVERSATION_DATA_REP = "conversation_data_rep"
    CONVERSATION_DATA_REQ = "conversation_data_req"

    CREDIT_DROP_PUSH = "credit_drop_push"
    CREDIT_DROP_PULL = "credit_drop_pull"

    CREDIT_RETURN_PUSH = "credit_return_push"
    CREDIT_RETURN_PULL = "credit_return_pull"

    INFERENCE_RESULTS_PUSH = "inference_results_push"
    INFERENCE_RESULTS_PULL = "inference_results_pull"


class ServiceRegistrationStatus(Enum):
    """Status of service registration."""

    UNREGISTERED = "unregistered"
    WAITING = "waiting"
    REGISTERED = "registered"
    TIMEOUT = "timeout"
    ERROR = "error"
