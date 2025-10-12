from enum import Enum
from typing import Any, Union


class StrEnum(str, Enum):
    """Base class for string-based enums.

    Using this as a base class allows enum values to be used directly as
    strings without having to use .value.
    """

    def __str__(self) -> str:
        return self.value

    def __contains__(self, item: Union[str, "StrEnum"]) -> bool:
        """Check if the item is in the enum."""
        if isinstance(item, str):
            return item in self.__class__.__members__.values()
        return super().__contains__(item)


class ServiceState(StrEnum):
    """Enum representing the possible states of a service."""

    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class MessageType(StrEnum):
    """Enum representing the types of messages that can be exchanged between services."""

    REGISTRATION = "registration"
    HEARTBEAT = "heartbeat"
    COMMAND = "command"
    RESPONSE = "response"
    STATUS = "status"
    DATA = "data"
    ERROR = "error"
    CREDIT = "credit"


class CommandType(StrEnum):
    """Enum representing the types of commands that can be sent to services."""

    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    CONFIGURE = "configure"
    PROFILE = "profile"
    SHUTDOWN = "shutdown"
    STATUS = "status"
    HEALTH_CHECK = "health_check"


class Topic(StrEnum):
    """Enum representing the different topics for communication between services."""

    REGISTRATION = "registration"
    COMMAND = "command"
    RESPONSE = "response"
    DATA = "data"
    STATUS = "status"
    HEARTBEAT = "heartbeat"


class CommBackend(StrEnum):
    """Enum representing the different communication backends."""

    ZMQ = "zmq"
    MEMORY = "memory"


class ServiceRunType(StrEnum):
    """Enum representing the different ways to run a service."""

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
