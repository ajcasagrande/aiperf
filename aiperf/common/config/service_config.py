from typing import Optional

from pydantic import BaseModel, Field

from aiperf.common.enums import CommBackend


class ServiceConfig(BaseModel):
    """Base configuration for all services.

    This class provides the common configuration parameters needed by all services.
    """

    comm_backend: CommBackend = Field(
        default=CommBackend.ZMQ,
        description="Communication backend to use",
    )
    control_topic: str = Field(
        default="control",
        description="Topic for control messages",
    )
    status_topic: str = Field(
        default="status",
        description="Topic for status messages",
    )
    response_topic: str = Field(
        default="response",
        description="Topic for response messages",
    )
    heartbeat_interval: float = Field(
        default=5.0,
        description="Interval in seconds between heartbeat messages",
    )


class ControllerConfig(ServiceConfig):
    """Configuration for controller services.

    This class extends the base service configuration with controller-specific settings.
    """

    service_type: str = "controller"
    heartbeat_timeout: float = Field(
        default=15.0,
        description="Time in seconds after which a service is considered dead if no heartbeat received",
    )
    registration_timeout: float = Field(
        default=60.0,
        description="Time in seconds to wait for all required services to register",
    )
    command_timeout: float = Field(
        default=10.0,
        description="Default timeout for command responses",
    )
    process_backend: str = Field(
        default="multiprocessing",
        description="Process manager backend to use (multiprocessing or kubernetes)",
    )
    namespace: str = Field(
        default="default",
        description="Kubernetes namespace to use when running with Kubernetes backend",
    )
    workers: int = Field(
        default=1,
        description="Number of worker processes to start",
    )
    port: int = Field(
        default=8000,
        description="Port to run the service on",
    )


class DatasetServiceConfig(ServiceConfig):
    """Configuration for the Dataset Manager service."""

    service_type: str = "dataset_manager"
    data_topic: str = "dataset_data"


class TimingServiceConfig(ServiceConfig):
    """Configuration for the Timing Manager service."""

    service_type: str = "timing_manager"
    data_topic: str = "timing_data"
    credit_topic: str = Field(
        default="credit",
        description="Topic for credit messages",
    )


class RecordsServiceConfig(ServiceConfig):
    """Configuration for the Records Manager service."""

    service_type: str = "records_manager"
    data_topic: str = "records_data"
    results_topic: str = Field(
        default="results",
        description="Topic for results data",
    )


class WorkerServiceConfig(ServiceConfig):
    """Configuration for the Worker Manager service."""

    service_type: str = "worker_manager"
    data_topic: str = "worker_data"
    credit_topic: str = Field(
        default="credit",
        description="Topic for credit messages",
    )
    results_topic: str = Field(
        default="results",
        description="Topic for results data",
    )
    min_workers: int = Field(
        default=5,
        description="Minimum number of idle workers to maintain",
    )
    max_workers: int = Field(
        default=100,
        description="Maximum number of workers to create",
    )
    target_idle_workers: int = Field(
        default=10,
        description="Target number of idle workers to maintain",
    )


class WorkerConfig(BaseModel):
    """Configuration for Worker instances."""

    worker_id: Optional[str] = Field(
        default=None,
        description="Unique identifier for this worker",
    )
    manager_id: Optional[str] = Field(
        default=None,
        description="ID of the worker manager that created this worker",
    )
    comm_backend: CommBackend = Field(
        default=CommBackend.ZMQ,
        description="Communication backend to use",
    )
    manager_data_topic: str = Field(
        default="worker_data",
        description="Topic for communication with the worker manager",
    )


class PostProcessorConfig(ServiceConfig):
    """Configuration for Post Processor services."""

    service_type: str = "post_processor"
    data_topic: str = "post_processor_data"
    records_topic: str = Field(
        default="records_data",
        description="Topic for records data",
    )
    metrics_topic: str = Field(
        default="metrics",
        description="Topic for metrics data",
    )
