# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

from aiperf.common.config.cli_parameter import CLIParameter
from aiperf.common.config.groups import Groups


class KubernetesConfig(BaseModel):
    """Configuration for Kubernetes deployment mode."""

    _CLI_GROUP = Groups.SERVICE

    enable_kubernetes: Annotated[
        bool,
        Field(
            description="Enable Kubernetes deployment mode. When enabled, AIPerf will deploy services as Kubernetes pods instead of local processes.",
        ),
        CLIParameter(
            name=("--kubernetes",),
            group=_CLI_GROUP,
        ),
    ] = False

    kubernetes_namespace: Annotated[
        str | None,
        Field(
            description="Kubernetes namespace to use for deployment. If not specified, a unique namespace will be auto-generated (e.g., aiperf-<timestamp>) and automatically cleaned up after completion.",
        ),
        CLIParameter(
            name=("--kubernetes-namespace",),
            group=_CLI_GROUP,
        ),
    ] = None

    kubeconfig_path: Annotated[
        Path | None,
        Field(
            description="Path to Kubernetes configuration file. Defaults to ~/.kube/config if not specified.",
        ),
        CLIParameter(
            name=("--kubeconfig",),
            group=_CLI_GROUP,
        ),
    ] = None

    kubernetes_image: Annotated[
        str,
        Field(
            description="Container image to use for AIPerf service pods.",
        ),
        CLIParameter(
            name=("--kubernetes-image",),
            group=_CLI_GROUP,
        ),
    ] = "aiperf:latest"

    kubernetes_image_pull_policy: Annotated[
        str,
        Field(
            description="Image pull policy for Kubernetes pods. Options: Always, IfNotPresent, Never.",
        ),
        CLIParameter(
            name=("--kubernetes-image-pull-policy",),
            group=_CLI_GROUP,
        ),
    ] = "IfNotPresent"

    kubernetes_service_account: Annotated[
        str,
        Field(
            description="ServiceAccount name to use for AIPerf pods. Will be created if it doesn't exist.",
        ),
        CLIParameter(
            name=("--kubernetes-service-account",),
            group=_CLI_GROUP,
        ),
    ] = "aiperf-service-account"

    kubernetes_auto_cleanup: Annotated[
        bool,
        Field(
            description="Automatically cleanup Kubernetes resources (namespace, pods, services) after benchmark completion. Only applies to auto-generated namespaces.",
        ),
        CLIParameter(
            name=("--kubernetes-auto-cleanup/--no-kubernetes-auto-cleanup",),
            group=_CLI_GROUP,
        ),
    ] = True

    @property
    def should_auto_cleanup(self) -> bool:
        """Determine if resources should be auto-cleaned up.

        Auto-cleanup only happens for auto-generated namespaces.
        """
        return self.kubernetes_auto_cleanup and self.kubernetes_namespace is None
