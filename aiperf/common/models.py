from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union
import time
from datetime import datetime
import uuid


class SystemState(Enum):
    """System state enum."""

    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()


class RequestType(Enum):
    """Request type enum."""

    TEXT = auto()
    IMAGE = auto()
    AUDIO = auto()
    VIDEO = auto()
    STREAMING_AUDIO = auto()
    STREAMING_VIDEO = auto()


class DistributionType(Enum):
    """Distribution type for timing and endpoint selection."""

    FIXED = auto()
    POISSON = auto()
    NORMAL = auto()
    UNIFORM = auto()
    ROUND_ROBIN = auto()
    WEIGHTED = auto()


@dataclass
class ConversationTurn:
    """Conversation turn class.

    Represents a single turn in a conversation between the system
    and an AI endpoint.
    """

    request: str
    response: str
    success: bool = True
    tokens: Dict[str, int] = field(default_factory=dict)
    latency: Optional[float] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    """Conversation class.

    Represents a multi-turn conversation with an AI endpoint.
    """

    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    turns: List[ConversationTurn] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimingCredit:
    """Timing credit class.

    Represents a credit issued by the timing manager that gives
    permission to a worker to issue a request.
    """

    credit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issued_time: float = field(default_factory=time.time)
    scheduled_time: Optional[float] = None
    consumed_time: Optional[float] = None
    expiration_time: Optional[float] = None
    worker_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_consumed: bool = False


@dataclass
class Metric:
    """Metric data point."""

    name: str
    value: Union[int, float, str, bool]
    timestamp: float = field(default_factory=time.time)
    unit: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "unit": self.unit,
            "labels": self.labels,
            "metadata": self.metadata,
        }


@dataclass
class Record:
    """Record of a request-response cycle."""

    record_id: str
    conversation: Conversation
    metrics: List[Metric] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def add_metric(self, metric: Metric) -> None:
        """Add a metric to this record."""
        self.metrics.append(metric)


@dataclass
class RequestRecord:
    """Request record class.

    Represents a record of a request to an AI endpoint.
    """

    conversation_id: str
    worker_id: str
    endpoint_name: str
    request_time: float
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    response_time: Optional[float] = None
    latency: Optional[float] = None
    success: bool = False
    tokens: Dict[str, int] = field(default_factory=dict)
    request_data: Dict[str, Any] = field(default_factory=dict)
    response_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """System metrics class.

    Represents a collection of system metrics.
    """

    timestamp: float = field(default_factory=time.time)
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    gpu_usage: Optional[List[Dict[str, Any]]] = None
    network_usage: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventRecord:
    """Event record class.

    Represents a record of an event in the system.
    """

    event_type: str
    component_id: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
