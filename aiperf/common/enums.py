from enum import Enum, auto
from typing import Union


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

    REGISTRATION = "registration"
    HEARTBEAT = "heartbeat"
    COMMAND = "command"
    RESPONSE = "response"
    STATUS = "status"
    DATA = "data"
    ERROR = "error"
    CREDIT = "credit"


class PayloadType(StrEnum):
    """Types of payloads that can be included in messages."""

    RESPONSE = "response"
    CREDIT = "credit"
    CONVERSATION = "conversation"
    RESULT = "result"
    WORKER_REQUEST = "worker_request"


class CommandType(StrEnum):
    """Commands that can be sent to services."""

    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    CONFIGURE = "configure"
    PROFILE = "profile"
    SHUTDOWN = "shutdown"
    STATUS = "status"
    HEALTH_CHECK = "health_check"


# Communication-related enums
class Topic(StrEnum):
    """Communication topics for the main message bus."""

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

    ZMQ = "zmq"
    MEMORY = "memory"


# Service-related enums
class ServiceRunType(StrEnum):
    """Different ways to run a service."""

    ASYNC = "async"
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
