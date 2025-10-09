# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Kubernetes pod and service template builders."""

from typing import Any

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceType


class PodTemplateBuilder:
    """Builds Kubernetes pod specifications for AIPerf services."""

    def __init__(
        self,
        namespace: str,
        image: str,
        image_pull_policy: str,
        service_account: str,
        system_controller_service: str,
    ):
        self.namespace = namespace
        self.image = image
        self.image_pull_policy = image_pull_policy
        self.service_account = service_account
        self.system_controller_service = system_controller_service

    def build_pod_spec(
        self,
        service_type: ServiceType,
        service_id: str,
        config_map_name: str,
        cpu: str = "1",
        memory: str = "1Gi",
    ) -> dict[str, Any]:
        """Build a pod specification for a service."""
        pod_spec = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": service_id,
                "namespace": self.namespace,
                "labels": {
                    "app": "aiperf",
                    "service-type": service_type.value,
                    "service-id": service_id,
                },
            },
            "spec": {
                "serviceAccountName": self.service_account,
                "restartPolicy": "OnFailure",
                "containers": [
                    {
                        "name": "aiperf",
                        "image": self.image,
                        "imagePullPolicy": "Never",
                        "command": ["python", "-m", "aiperf.kubernetes.entrypoint"],
                        "env": [
                            {
                                "name": "AIPERF_SERVICE_TYPE",
                                "value": service_type.value,
                            },
                            {
                                "name": "AIPERF_SERVICE_ID",
                                "value": service_id,
                            },
                            {
                                "name": "AIPERF_CONFIG_MAP",
                                "value": config_map_name,
                            },
                            {
                                "name": "AIPERF_NAMESPACE",
                                "value": self.namespace,
                            },
                            {
                                "name": "AIPERF_SYSTEM_CONTROLLER_SERVICE",
                                "value": self.system_controller_service,
                            },
                            {
                                "name": "AIPERF_IMAGE",
                                "value": self.image,
                            },
                        ],
                        "resources": {
                            "requests": {"cpu": cpu, "memory": memory},
                            "limits": {"cpu": cpu, "memory": memory},
                        },
                    }
                ],
            },
        }

        return pod_spec

    def build_system_controller_service(self) -> dict[str, Any]:
        """Build Kubernetes service for system controller ZMQ proxies."""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": self.system_controller_service,
                "namespace": self.namespace,
                "labels": {"app": "aiperf", "component": "system-controller"},
            },
            "spec": {
                "selector": {
                    "app": "aiperf",
                    "service-type": ServiceType.SYSTEM_CONTROLLER.value,
                },
                "type": "ClusterIP",
                "ports": [
                    # ZMQ proxy ports from ZMQTCPConfig
                    {"name": "credit-drop", "port": 5562, "targetPort": 5562},
                    {"name": "credit-return", "port": 5563, "targetPort": 5563},
                    {"name": "records", "port": 5557, "targetPort": 5557},
                    {
                        "name": "dataset-mgr-frontend",
                        "port": 5661,
                        "targetPort": 5661,
                    },
                    {
                        "name": "dataset-mgr-backend",
                        "port": 5662,
                        "targetPort": 5662,
                    },
                    {"name": "event-bus-frontend", "port": 5663, "targetPort": 5663},
                    {"name": "event-bus-backend", "port": 5664, "targetPort": 5664},
                    {
                        "name": "raw-inference-frontend",
                        "port": 5665,
                        "targetPort": 5665,
                    },
                    {
                        "name": "raw-inference-backend",
                        "port": 5666,
                        "targetPort": 5666,
                    },
                ],
            },
        }

    def build_timing_manager_service(self) -> dict[str, Any]:
        """Build Kubernetes service for timing manager (credit distribution)."""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "timing-manager",
                "namespace": self.namespace,
                "labels": {"app": "aiperf", "component": "timing-manager"},
            },
            "spec": {
                "selector": {
                    "app": "aiperf",
                    "service-type": ServiceType.TIMING_MANAGER.value,
                },
                "type": "ClusterIP",
                "ports": [
                    {"name": "credit-drop", "port": 5562, "targetPort": 5562},
                    {"name": "credit-return", "port": 5563, "targetPort": 5563},
                ],
            },
        }

    def build_records_manager_service(self) -> dict[str, Any]:
        """Build Kubernetes service for records manager (record collection)."""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "records-manager",
                "namespace": self.namespace,
                "labels": {"app": "aiperf", "component": "records-manager"},
            },
            "spec": {
                "selector": {
                    "app": "aiperf",
                    "service-type": ServiceType.RECORDS_MANAGER.value,
                },
                "type": "ClusterIP",
                "ports": [
                    {"name": "records", "port": 5557, "targetPort": 5557},
                ],
            },
        }

    def build_rbac_resources(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Build RBAC resources (ServiceAccount, ClusterRole, ClusterRoleBinding)."""
        service_account = {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": self.service_account,
                "namespace": self.namespace,
            },
        }

        cluster_role = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRole",
            "metadata": {"name": f"aiperf-role-{self.namespace}"},
            "rules": [
                {
                    "apiGroups": [""],
                    "resources": ["pods", "services", "configmaps", "pods/log"],
                    "verbs": [
                        "create",
                        "get",
                        "list",
                        "watch",
                        "update",
                        "patch",
                        "delete",
                    ],
                },
                {
                    "apiGroups": ["apps"],
                    "resources": ["deployments", "replicasets"],
                    "verbs": [
                        "create",
                        "get",
                        "list",
                        "watch",
                        "update",
                        "patch",
                        "delete",
                    ],
                },
            ],
        }

        cluster_role_binding = {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRoleBinding",
            "metadata": {"name": f"aiperf-binding-{self.namespace}"},
            "subjects": [
                {
                    "kind": "ServiceAccount",
                    "name": self.service_account,
                    "namespace": self.namespace,
                }
            ],
            "roleRef": {
                "kind": "ClusterRole",
                "name": f"aiperf-role-{self.namespace}",
                "apiGroup": "rbac.authorization.k8s.io",
            },
        }

        return service_account, cluster_role, cluster_role_binding
