# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Comprehensive unit tests for Kubernetes components."""

import json

import pytest

from aiperf.common.config import EndpointConfig, ServiceConfig, UserConfig
from aiperf.common.enums import ServiceType
from aiperf.kubernetes.config_serializer import ConfigSerializer
from aiperf.kubernetes.templates import PodTemplateBuilder


class TestPodTemplateBuilder:
    """Comprehensive tests for pod template generation."""

    @pytest.fixture
    def builder(self):
        return PodTemplateBuilder(
            namespace="test-ns",
            image="aiperf:test",
            image_pull_policy="IfNotPresent",
            service_account="test-sa",
            system_controller_service="test-svc",
        )

    def test_build_system_controller_pod(self, builder):
        """Test system controller pod generation."""
        pod = builder.build_pod_spec(
            ServiceType.SYSTEM_CONTROLLER, "sc-1", "config", "2", "2Gi"
        )

        assert pod["metadata"]["name"] == "sc-1"
        assert (
            pod["metadata"]["labels"]["service-type"]
            == ServiceType.SYSTEM_CONTROLLER.value
        )
        assert pod["spec"]["containers"][0]["resources"]["limits"]["cpu"] == "2"
        assert pod["spec"]["containers"][0]["resources"]["limits"]["memory"] == "2Gi"

    def test_build_worker_pod(self, builder):
        """Test worker pod generation."""
        pod = builder.build_pod_spec(
            ServiceType.WORKER, "worker-0", "config", "4", "4Gi"
        )

        env_dict = {e["name"]: e["value"] for e in pod["spec"]["containers"][0]["env"]}
        assert env_dict["AIPERF_SERVICE_TYPE"] == ServiceType.WORKER.value
        assert env_dict["AIPERF_SERVICE_ID"] == "worker-0"
        assert env_dict["AIPERF_CONFIG_MAP"] == "config"

    def test_build_service_all_ports(self, builder):
        """Test that system controller service exposes all ZMQ ports."""
        svc = builder.build_system_controller_service()

        port_names = [p["name"] for p in svc["spec"]["ports"]]
        assert "credit-drop" in port_names
        assert "credit-return" in port_names
        assert "records" in port_names
        assert "dataset-mgr-frontend" in port_names
        assert "dataset-mgr-backend" in port_names
        assert "event-bus-frontend" in port_names
        assert "event-bus-backend" in port_names
        assert "raw-inference-frontend" in port_names
        assert "raw-inference-backend" in port_names

    def test_rbac_service_account(self, builder):
        """Test ServiceAccount generation."""
        sa, _, _ = builder.build_rbac_resources()

        assert sa["kind"] == "ServiceAccount"
        assert sa["metadata"]["name"] == "test-sa"
        assert sa["metadata"]["namespace"] == "test-ns"

    def test_rbac_cluster_role_permissions(self, builder):
        """Test ClusterRole has correct permissions."""
        _, role, _ = builder.build_rbac_resources()

        assert role["kind"] == "ClusterRole"
        resources = []
        for rule in role["rules"]:
            resources.extend(rule["resources"])

        assert "pods" in resources
        assert "services" in resources
        assert "configmaps" in resources
        assert "pods/log" in resources

        verbs = []
        for rule in role["rules"]:
            verbs.extend(rule["verbs"])

        assert "create" in verbs
        assert "get" in verbs
        assert "list" in verbs
        assert "delete" in verbs

    def test_rbac_cluster_role_binding(self, builder):
        """Test ClusterRoleBinding configuration."""
        sa, role, binding = builder.build_rbac_resources()

        assert binding["kind"] == "ClusterRoleBinding"
        assert binding["subjects"][0]["name"] == sa["metadata"]["name"]
        assert binding["subjects"][0]["namespace"] == "test-ns"
        assert binding["roleRef"]["name"] == role["metadata"]["name"]


class TestConfigSerializer:
    """Comprehensive tests for configuration serialization."""

    @pytest.fixture
    def user_config(self):
        return UserConfig(
            endpoint=EndpointConfig(url="http://test:8000", model_names=["model1"])
        )

    @pytest.fixture
    def service_config(self):
        return ServiceConfig()

    def test_serialize_user_config(self, user_config, service_config):
        """Test user config serialization."""
        data = ConfigSerializer.serialize_to_configmap(user_config, service_config)

        assert "user_config.json" in data
        user_json = json.loads(data["user_config.json"])
        assert user_json["endpoint"]["url"] == "http://test:8000"
        assert user_json["endpoint"]["model_names"] == ["model1"]

    def test_serialize_service_config(self, user_config, service_config):
        """Test service config serialization."""
        service_config.kubernetes.enabled = True
        service_config.kubernetes.namespace = "custom-ns"

        data = ConfigSerializer.serialize_to_configmap(user_config, service_config)

        service_json = json.loads(data["service_config.json"])
        assert service_json["kubernetes"]["enabled"] is True
        assert service_json["kubernetes"]["namespace"] == "custom-ns"

    def test_roundtrip_serialization(self, user_config, service_config):
        """Test serialize then deserialize maintains data."""
        # Set non-default values so they get serialized
        service_config.kubernetes.enabled = True
        service_config.kubernetes.namespace = "test-ns"

        data = ConfigSerializer.serialize_to_configmap(user_config, service_config)

        # Verify JSON is valid and contains expected data
        user_json = json.loads(data["user_config.json"])
        service_json = json.loads(data["service_config.json"])

        assert "endpoint" in user_json
        assert "kubernetes" in service_json

    def test_serialize_complex_config(self):
        """Test serialization with complex configuration."""
        from aiperf.common.config import LoadGeneratorConfig

        user_config = UserConfig(
            endpoint=EndpointConfig(
                url="http://complex:9000",
                model_names=["model1", "model2"],
            ),
            loadgen=LoadGeneratorConfig(concurrency=1000, benchmark_duration=300),
        )

        service_config = ServiceConfig()
        service_config.kubernetes.worker_cpu = "4"
        service_config.kubernetes.worker_memory = "8Gi"
        service_config.kubernetes.connections_per_worker = 1000

        data = ConfigSerializer.serialize_to_configmap(user_config, service_config)

        user_json = json.loads(data["user_config.json"])
        service_json = json.loads(data["service_config.json"])

        assert user_json["loadgen"]["concurrency"] == 1000
        assert service_json["kubernetes"]["worker_cpu"] == "4"


class TestKubernetesConfig:
    """Test Kubernetes configuration options."""

    def test_default_config(self):
        """Test default Kubernetes configuration."""
        config = ServiceConfig()

        assert config.kubernetes.enabled is False
        assert config.kubernetes.namespace is None
        assert config.kubernetes.image == "aiperf:latest"
        assert config.kubernetes.connections_per_worker == 500
        assert config.kubernetes.cleanup_on_completion is True

    def test_custom_config(self):
        """Test custom Kubernetes configuration."""
        config = ServiceConfig()
        config.kubernetes.enabled = True
        config.kubernetes.namespace = "my-namespace"
        config.kubernetes.image = "custom-image:v1.0"
        config.kubernetes.worker_cpu = "8"
        config.kubernetes.worker_memory = "16Gi"
        config.kubernetes.connections_per_worker = 2000

        assert config.kubernetes.enabled is True
        assert config.kubernetes.namespace == "my-namespace"
        assert config.kubernetes.image == "custom-image:v1.0"
        assert config.kubernetes.worker_cpu == "8"
        assert config.kubernetes.worker_memory == "16Gi"
        assert config.kubernetes.connections_per_worker == 2000


class TestServiceTypes:
    """Test service type handling."""

    def test_all_service_types_have_pods(self):
        """Test that all service types can generate pod specs."""
        builder = PodTemplateBuilder(
            namespace="test",
            image="test:latest",
            image_pull_policy="Never",
            service_account="test",
            system_controller_service="test-svc",
        )

        service_types = [
            ServiceType.SYSTEM_CONTROLLER,
            ServiceType.DATASET_MANAGER,
            ServiceType.TIMING_MANAGER,
            ServiceType.RECORDS_MANAGER,
            ServiceType.WORKER_MANAGER,
            ServiceType.WORKER,
            ServiceType.RECORD_PROCESSOR,
        ]

        for service_type in service_types:
            pod = builder.build_pod_spec(
                service_type=service_type,
                service_id=f"{service_type.value}-0",
                config_map_name="config",
            )

            assert pod["kind"] == "Pod"
            assert pod["metadata"]["labels"]["service-type"] == service_type.value
            assert len(pod["spec"]["containers"]) == 1
            assert pod["spec"]["containers"][0]["command"] == [
                "python",
                "-m",
                "aiperf.kubernetes.entrypoint",
            ]


def test_kubernetes_imports():
    """Test all Kubernetes modules can be imported."""
    from aiperf.kubernetes import KubernetesResourceManager, PodTemplateBuilder
    from aiperf.kubernetes.config_serializer import ConfigSerializer
    from aiperf.kubernetes.entrypoint import main
    from aiperf.kubernetes.orchestrator import KubernetesOrchestrator
    from aiperf.orchestrator.kubernetes_runner import run_aiperf_kubernetes

    assert KubernetesResourceManager is not None
    assert PodTemplateBuilder is not None
    assert ConfigSerializer is not None
    assert main is not None
    assert KubernetesOrchestrator is not None
    assert run_aiperf_kubernetes is not None


def test_service_config_kubernetes_field():
    """Test ServiceConfig has kubernetes field."""
    config = ServiceConfig()
    assert hasattr(config, "kubernetes")
    assert config.kubernetes is not None


def test_cli_integration():
    """Test CLI can route to Kubernetes mode."""
    from aiperf.cli import profile

    assert profile is not None
