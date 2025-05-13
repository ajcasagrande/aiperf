from pydantic import BaseModel, Field

from aiperf.common.enums import CommBackend, ServiceRunType


class ServiceConfig(BaseModel):
    """Base configuration for all services.

    This class provides the common configuration parameters needed by all services.
    """

    # TODO: this needs to be cleaned up and finalized

    comm_backend: CommBackend = Field(
        default=CommBackend.ZMQ_TCP,
        description="Communication backend to use",
    )
    service_run_type: ServiceRunType = Field(
        default=ServiceRunType.MULTIPROCESSING,
        description="Type of service run (MULTIPROCESSING, KUBERNETES)",
    )
    heartbeat_timeout: float = Field(
        default=60.0,
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
    heartbeat_interval: float = Field(
        default=10.0,
        description="Interval in seconds between heartbeat messages",
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
