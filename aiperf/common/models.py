from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union
import time
from datetime import datetime

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
    """Single turn in a conversation."""
    turn_id: str
    request_data: Dict[str, Any]
    response_data: Optional[Dict[str, Any]] = None
    request_timestamp: float = field(default_factory=time.time)
    response_timestamp: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def latency(self) -> Optional[float]:
        """Calculate latency for this turn."""
        if self.response_timestamp is None:
            return None
        return self.response_timestamp - self.request_timestamp

@dataclass
class Conversation:
    """Multi-turn conversation."""
    conversation_id: str
    turns: List[ConversationTurn] = field(default_factory=list)
    start_timestamp: float = field(default_factory=time.time)
    end_timestamp: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_turn(self, turn: ConversationTurn) -> None:
        """Add a turn to the conversation."""
        self.turns.append(turn)
        
    @property
    def total_duration(self) -> Optional[float]:
        """Calculate total duration for this conversation."""
        if self.end_timestamp is None:
            return None
        return self.end_timestamp - self.start_timestamp

@dataclass
class TimingCredit:
    """Credit for issuing a request at a specific time."""
    credit_id: str
    target_timestamp: float
    credit_type: str = "request"
    parameters: Dict[str, Any] = field(default_factory=dict)
    issued_timestamp: float = field(default_factory=time.time)
    consumed_timestamp: Optional[float] = None
    
    @property
    def is_consumed(self) -> bool:
        """Check if this credit has been consumed."""
        return self.consumed_timestamp is not None
    
    def consume(self) -> None:
        """Mark this credit as consumed."""
        self.consumed_timestamp = time.time()

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
            "metadata": self.metadata
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