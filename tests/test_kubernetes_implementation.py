# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for Kubernetes implementation components."""

import pytest

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceRunType, ServiceType
from aiperf.kubernetes.config_serializer import ConfigSerializer
from aiperf.kubernetes.templates import PodTemplateBuilder


class TestConfigSerializer:
    """Test configuration serialization for Kubernetes."""

    def test_serialize_and_deserialize(self):
        """Test that configs can be serialized and deserialized."""
        from aiperf.common.config import EndpointConfig

        user_config = UserConfig(
            endpoint=EndpointConfig(url="http://localhost:8000", model_names=["test-model"])
        )
        service_config = ServiceConfig()

        # Serialize
        config_data = ConfigSerializer.serialize_to_configmap(
            user_config, service_config
        )

        assert "user_config.json" in config_data
        assert "service_config.json" in config_data

        # Verify JSON is valid
        import json
        user_json = json.loads(config_data["user_config.json"])
        service_json = json.loads(config_data["service_config.json"])

        assert "endpoint" in user_json
        assert user_json["endpoint"]["url"] == "http://localhost:8000"


class TestPodTemplateBuilder:
    """Test Kubernetes pod template generation."""

    @pytest.fixture
    def template_builder(self):
        return PodTemplateBuilder(
            namespace="test-namespace",
            image="aiperf:test",
            image_pull_policy="IfNotPresent",
            service_account="test-sa",
            system_controller_service="test-controller",
        )

    def test_build_pod_spec(self, template_builder):
        """Test pod spec generation."""
        pod_spec = template_builder.build_pod_spec(
            service_type=ServiceType.WORKER,
            service_id="worker-0",
            config_map_name="test-config",
            cpu="2",
            memory="2Gi",
        )

        assert pod_spec["kind"] == "Pod"
        assert pod_spec["metadata"]["name"] == "worker-0"
        assert pod_spec["metadata"]["namespace"] == "test-namespace"
        assert pod_spec["spec"]["containers"][0]["image"] == "aiperf:test"

        # Check environment variables
        env_vars = pod_spec["spec"]["containers"][0]["env"]
        env_dict = {e["name"]: e["value"] for e in env_vars}
        assert env_dict["AIPERF_SERVICE_TYPE"] == ServiceType.WORKER.value
        assert env_dict["AIPERF_SERVICE_ID"] == "worker-0"

    def test_build_system_controller_service(self, template_builder):
        """Test system controller service generation."""
        service_spec = template_builder.build_system_controller_service()

        assert service_spec["kind"] == "Service"
        assert service_spec["spec"]["type"] == "ClusterIP"
        assert len(service_spec["spec"]["ports"]) >= 9  # All ZMQ ports

    def test_build_rbac_resources(self, template_builder):
        """Test RBAC resource generation."""
        sa, role, binding = template_builder.build_rbac_resources()

        assert sa["kind"] == "ServiceAccount"
        assert role["kind"] == "ClusterRole"
        assert binding["kind"] == "ClusterRoleBinding"

        # Check permissions
        assert len(role["rules"]) > 0
        assert "pods" in role["rules"][0]["resources"]


@pytest.mark.asyncio
class TestKubernetesIntegration:
    """Integration tests for Kubernetes deployment (requires cluster)."""

    @pytest.mark.skip(reason="Requires running Kubernetes cluster")
    async def test_full_deployment(self):
        """Test complete Kubernetes deployment flow."""
        # This would test actual deployment to cluster
        # Skipped by default, run manually with cluster access
        pass


def test_imports():
    """Test that all Kubernetes modules can be imported."""
    from aiperf.kubernetes import KubernetesResourceManager, PodTemplateBuilder
    from aiperf.kubernetes.config_serializer import ConfigSerializer
    from aiperf.kubernetes.entrypoint import main
    from aiperf.kubernetes.orchestrator import KubernetesOrchestrator

    assert KubernetesResourceManager is not None
    assert PodTemplateBuilder is not None
    assert ConfigSerializer is not None
    assert KubernetesOrchestrator is not None


def test_service_config_has_kubernetes():
    """Test that ServiceConfig includes kubernetes field."""
    config = ServiceConfig()
    assert hasattr(config, "kubernetes")
    assert config.kubernetes is not None
    assert hasattr(config.kubernetes, "enabled")
    assert hasattr(config.kubernetes, "namespace")
    assert hasattr(config.kubernetes, "image")
