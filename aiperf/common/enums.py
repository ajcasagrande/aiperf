from enum import Enum


class ServiceState(Enum):
    """Enum representing the possible states of a service."""

    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
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

    COMMAND = "command"
    RESPONSE = "response"
    DATA = "data"
    STATUS = "status"
    HEARTBEAT = "heartbeat"


class CommBackend(Enum):
    """Enum representing the different communication backends."""

    ZMQ = "zmq"
    # Add more backends here as they are implemented
