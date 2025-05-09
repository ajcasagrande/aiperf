from enum import Enum


class ServiceState(Enum):
    """Enum representing the possible states of a service."""

    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class MessageType(Enum):
    """Enum representing the types of messages that can be exchanged between services."""

    REGISTRATION = "registration"
    HEARTBEAT = "heartbeat"
    COMMAND = "command"
    RESPONSE = "response"
    STATUS = "status"
    DATA = "data"
    ERROR = "error"
    CREDIT = "credit"


class CommandType(Enum):
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


class Topic(Enum):
    """Enum representing the different topics for communication between services."""

    REGISTRATION = "registration"
    COMMAND = "command"
    RESPONSE = "response"
    DATA = "data"
    STATUS = "status"
    HEARTBEAT = "heartbeat"


class CommBackend(Enum):
    """Enum representing the different communication backends."""

    ZMQ = "zmq"
    MEMORY = "memory"


class ServiceRunType(Enum):
    """Enum representing the different ways to run a service."""

    ASYNC = "async"
    MULTIPROCESSING = "process"
    KUBERNETES = "k8s"


class ServiceType(Enum):
    """Service type enum."""

    SYSTEM_CONTROLLER = "system_controller"
    DATASET_MANAGER = "dataset_manager"
    TIMING_MANAGER = "timing_manager"
    WORKER_MANAGER = "worker_manager"
    RECORDS_MANAGER = "records_manager"
    POST_PROCESSOR_MANAGER = "post_processor_manager"
    WORKER = "worker"
    TEST = "test_service"  # Used in tests
