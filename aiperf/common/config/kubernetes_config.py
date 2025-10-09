# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Annotated

from pydantic import Field

from aiperf.common.config.base_config import BaseConfig
from aiperf.common.config.cli_parameter import CLIParameter
from aiperf.common.config.groups import Groups


class KubernetesConfig(BaseConfig):
    """Kubernetes deployment configuration."""

    _CLI_GROUP = Groups.KUBERNETES

    enabled: Annotated[
        bool,
        Field(description="Enable Kubernetes deployment mode"),
        CLIParameter(name=("--kubernetes",), group=_CLI_GROUP),
    ] = False

    namespace: Annotated[
        str | None,
        Field(description="Kubernetes namespace to use (auto-generated if not specified)"),
        CLIParameter(name=("--kubernetes-namespace",), group=_CLI_GROUP),
    ] = None

    kubeconfig: Annotated[
        Path | None,
        Field(description="Path to kubeconfig file (defaults to ~/.kube/config)"),
        CLIParameter(name=("--kubeconfig",), group=_CLI_GROUP),
    ] = None

    image: Annotated[
        str,
        Field(description="Container image to use for AIPerf pods"),
        CLIParameter(name=("--kubernetes-image",), group=_CLI_GROUP),
    ] = "aiperf:latest"

    image_pull_policy: Annotated[
        str,
        Field(description="Image pull policy (Always, IfNotPresent, Never)"),
        CLIParameter(name=("--kubernetes-image-pull-policy",), group=_CLI_GROUP),
    ] = "IfNotPresent"

    service_account: Annotated[
        str,
        Field(description="Service account name for AIPerf pods"),
    ] = "aiperf-service-account"

    cleanup_on_completion: Annotated[
        bool,
        Field(description="Automatically cleanup resources after benchmark completion"),
        CLIParameter(name=("--kubernetes-cleanup",), group=_CLI_GROUP),
    ] = True

    worker_cpu: Annotated[
        str,
        Field(description="CPU request/limit for worker pods (e.g., '2' or '2000m')"),
        CLIParameter(name=("--kubernetes-worker-cpu",), group=_CLI_GROUP),
    ] = "2"

    worker_memory: Annotated[
        str,
        Field(description="Memory request/limit for worker pods (e.g., '2Gi')"),
        CLIParameter(name=("--kubernetes-worker-memory",), group=_CLI_GROUP),
    ] = "2Gi"

    connections_per_worker: Annotated[
        int,
        Field(description="Number of concurrent connections per worker pod"),
        CLIParameter(name=("--connections-per-worker",), group=_CLI_GROUP),
    ] = 500
