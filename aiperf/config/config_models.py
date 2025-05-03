from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum, auto

class EndpointSelectionStrategy(Enum):
    """Strategy for selecting endpoints."""
    ROUND_ROBIN = auto()
    RANDOM = auto()
    WEIGHTED = auto()

@dataclass
class EndpointConfig:
    """Configuration for an endpoint."""
    name: str
    url: str
    api_type: str  # openai, huggingface_tgi, huggingface_tei, kserve, custom
    headers: Dict[str, str] = field(default_factory=dict)
    auth: Optional[Dict[str, str]] = None
    timeout: float = 30.0
    weight: float = 1.0  # For weighted selection
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DatasetConfig:
    """Configuration for dataset."""
    source_type: str  # synthetic, remote, local
    name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    cache_dir: Optional[str] = None
    synthetic_params: Optional[Dict[str, Any]] = None
    modality: str = "text"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TimingConfig:
    """Configuration for timing."""
    schedule_type: str  # fixed, poisson, normal, uniform
    parameters: Dict[str, Any] = field(default_factory=dict)
    concurrency: Optional[int] = None
    request_rate: Optional[float] = None
    duration: Optional[float] = None
    start_delay: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkerConfig:
    """Configuration for workers."""
    min_workers: int = 1
    max_workers: int = 10
    worker_startup_timeout: float = 30.0
    worker_idle_timeout: float = 300.0
    worker_keepalive_interval: float = 10.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MetricsConfig:
    """Configuration for metrics collection."""
    enabled_metrics: List[str] = field(default_factory=list)
    output_format: str = "json"
    output_path: Optional[str] = None
    live_metrics: bool = True
    server_metrics: bool = True
    gpu_telemetry: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CommunicationConfig:
    """Configuration for communication between components."""
    type: str = "memory"  # memory, zmq
    pub_address: Optional[str] = None
    sub_address: Optional[str] = None
    req_address: Optional[str] = None
    rep_address: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class KubernetesConfig:
    """Configuration for Kubernetes deployment."""
    enabled: bool = False
    namespace: str = "aiperf"
    service_account: Optional[str] = None
    image: str = "aiperf:latest"
    pull_policy: str = "IfNotPresent"
    resource_requests: Dict[str, str] = field(default_factory=lambda: {"cpu": "100m", "memory": "128Mi"})
    resource_limits: Dict[str, str] = field(default_factory=lambda: {"cpu": "1", "memory": "1Gi"})
    node_selector: Dict[str, str] = field(default_factory=dict)
    tolerations: List[Dict[str, Any]] = field(default_factory=list)
    controller_image: Optional[str] = None  # If None, use the same as 'image'
    worker_image: Optional[str] = None  # If None, use the same as 'image'
    use_config_map: bool = True  # Store config in ConfigMap
    use_secrets: bool = False  # Store sensitive data in Secrets
    persistent_volume_claim: Optional[str] = None  # For storing results
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AIperfConfig:
    """Main configuration for AIPerf."""
    profile_name: str
    endpoints: List[EndpointConfig] = field(default_factory=list)
    dataset: DatasetConfig = field(default_factory=lambda: DatasetConfig(source_type="synthetic", name="default"))
    timing: TimingConfig = field(default_factory=lambda: TimingConfig(schedule_type="fixed"))
    workers: WorkerConfig = field(default_factory=WorkerConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    communication: CommunicationConfig = field(default_factory=CommunicationConfig)
    kubernetes: KubernetesConfig = field(default_factory=KubernetesConfig)
    endpoint_selection: EndpointSelectionStrategy = EndpointSelectionStrategy.ROUND_ROBIN
    log_level: str = "INFO"
    debug_mode: bool = False
    deterministic: bool = True
    seed: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> List[str]:
        """Validate the configuration.
        
        Returns:
            List of validation errors, empty if valid
        """
        errors = []
        
        # Basic validation
        if not self.profile_name:
            errors.append("Profile name is required")
            
        if not self.endpoints:
            errors.append("At least one endpoint is required")
        
        # Validate communication config
        if self.communication.type not in ["memory", "zmq"]:
            errors.append(f"Invalid communication type: {self.communication.type}")
            
        if self.communication.type == "zmq":
            if not self.communication.pub_address:
                errors.append("ZMQ communication requires pub_address")
            if not self.communication.sub_address:
                errors.append("ZMQ communication requires sub_address")
            if not self.communication.req_address:
                errors.append("ZMQ communication requires req_address")
            if not self.communication.rep_address:
                errors.append("ZMQ communication requires rep_address")
        
        # Validate Kubernetes config if enabled
        if self.kubernetes.enabled:
            if self.communication.type == "memory":
                errors.append("Kubernetes deployment requires 'zmq' communication type, not 'memory'")
            
            if not self.kubernetes.namespace:
                errors.append("Kubernetes namespace is required when Kubernetes is enabled")
                
            if not self.kubernetes.image:
                errors.append("Kubernetes image is required when Kubernetes is enabled")
            
        # More validation rules can be added here
            
        return errors 