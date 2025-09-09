# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Annotated

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from aiperf.common.config.base_config import BaseConfig


class KubernetesServiceConfig(BaseModel):
    """Configuration for individual service pods in Kubernetes."""

    cpu_request: str = Field(
        default="200m", description="CPU request for the service pod"
    )
    cpu_limit: str = Field(default="500m", description="CPU limit for the service pod")
    memory_request: str = Field(
        default="256Mi", description="Memory request for the service pod"
    )
    memory_limit: str = Field(
        default="512Mi", description="Memory limit for the service pod"
    )

    enable_health_checks: bool = Field(
        default=True, description="Enable health check probes"
    )
    health_check_port: int = Field(
        default=8080, description="Port for health check endpoints"
    )

    image_pull_policy: str = Field(
        default="IfNotPresent", description="Kubernetes image pull policy"
    )

    restart_policy: str = Field(
        default="Never", description="Kubernetes restart policy for AIPerf service pods"
    )


class KubernetesClusterConfig(BaseConfig):
    """Configuration for Kubernetes cluster integration."""

    _CLI_GROUP = None  # Don't expose in CLI for now

    namespace: Annotated[
        str | None,
        Field(
            description="Kubernetes namespace to deploy services in. "
            "If not specified, will use the current namespace or 'default'"
        ),
    ] = None

    container_image: Annotated[
        str | None,
        Field(
            description="Container image to use for AIPerf services. "
            "If not specified, will be constructed from registry/repository:tag"
        ),
    ] = None

    image_registry: Annotated[
        str, Field(description="Container registry for AIPerf images")
    ] = "docker.io"

    image_repository: Annotated[
        str, Field(description="Container repository for AIPerf images")
    ] = "nvidia/aiperf"

    image_tag: Annotated[
        str, Field(description="Container image tag for AIPerf services")
    ] = "latest"

    service_account_name: Annotated[
        str | None,
        Field(
            description="Service account name to use for pods. "
            "If not specified, will use the default service account"
        ),
    ] = None

    node_selector: Annotated[
        dict[str, str],
        Field(
            description="Node selector labels for pod scheduling", default_factory=dict
        ),
    ] = {}

    tolerations: Annotated[
        list[dict],
        Field(description="Pod tolerations for node scheduling", default_factory=list),
    ] = []

    security_context_run_as_user: Annotated[
        int, Field(description="User ID to run containers as")
    ] = 1000

    security_context_run_as_group: Annotated[
        int, Field(description="Group ID to run containers as")
    ] = 1000

    security_context_fs_group: Annotated[
        int, Field(description="File system group ID for volumes")
    ] = 1000

    pod_deletion_grace_period: Annotated[
        int, Field(description="Grace period in seconds for pod deletion", ge=0, le=300)
    ] = 30

    # Service-specific configurations
    system_controller: Annotated[
        KubernetesServiceConfig,
        Field(description="Configuration for System Controller service"),
    ] = KubernetesServiceConfig()

    dataset_manager: Annotated[
        KubernetesServiceConfig,
        Field(description="Configuration for Dataset Manager service"),
    ] = KubernetesServiceConfig(
        cpu_request="300m", memory_request="512Mi", memory_limit="2Gi"
    )

    timing_manager: Annotated[
        KubernetesServiceConfig,
        Field(description="Configuration for Timing Manager service"),
    ] = KubernetesServiceConfig()

    worker_manager: Annotated[
        KubernetesServiceConfig,
        Field(description="Configuration for Worker Manager service"),
    ] = KubernetesServiceConfig()

    worker: Annotated[
        KubernetesServiceConfig, Field(description="Configuration for Worker services")
    ] = KubernetesServiceConfig(
        cpu_request="500m", cpu_limit="1", memory_request="1Gi", memory_limit="2Gi"
    )

    records_manager: Annotated[
        KubernetesServiceConfig,
        Field(description="Configuration for Records Manager service"),
    ] = KubernetesServiceConfig(
        cpu_request="500m", cpu_limit="2", memory_request="1Gi", memory_limit="4Gi"
    )

    post_processor: Annotated[
        KubernetesServiceConfig,
        Field(description="Configuration for Post Processor service"),
    ] = KubernetesServiceConfig(
        cpu_request="300m", memory_request="512Mi", memory_limit="2Gi"
    )


class KubernetesConfig(BaseSettings):
    """Main Kubernetes configuration class."""

    model_config = SettingsConfigDict(
        env_prefix="AIPERF_K8S_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    enabled: Annotated[bool, Field(description="Enable Kubernetes integration")] = False

    cluster: Annotated[
        KubernetesClusterConfig, Field(description="Kubernetes cluster configuration")
    ] = KubernetesClusterConfig()

    service_discovery: Annotated[
        bool, Field(description="Use Kubernetes service discovery for ZMQ proxy")
    ] = True

    auto_scaling: Annotated[
        bool, Field(description="Enable automatic scaling of worker pods")
    ] = True

    monitoring: Annotated[
        bool, Field(description="Enable Kubernetes-native monitoring integration")
    ] = True

    rbac_enabled: Annotated[
        bool, Field(description="Enable RBAC for service accounts")
    ] = True

    network_policies_enabled: Annotated[
        bool, Field(description="Enable network policies for security")
    ] = False  # Optional as not all clusters support them

    debug: Annotated[
        bool, Field(description="Enable debug logging for Kubernetes operations")
    ] = False
