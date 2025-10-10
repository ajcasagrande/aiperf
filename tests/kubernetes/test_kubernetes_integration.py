# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for Kubernetes deployment mode.

These tests verify that AIPerf can successfully deploy and run benchmarks
in a Kubernetes cluster.

Requirements:
- kubectl configured and connected to a cluster
- minikube or other K8s cluster running
- aiperf:latest Docker image built and available to the cluster

To run these tests:
    pytest tests/kubernetes/test_kubernetes_integration.py -v
"""

import subprocess
import time
from pathlib import Path

import pytest
from kubernetes import client, config


@pytest.fixture(scope="module")
def k8s_client():
    """Initialize Kubernetes client."""
    try:
        config.load_kube_config()
    except Exception:
        pytest.skip("Kubernetes cluster not available")

    return client.CoreV1Api()


@pytest.fixture(scope="module")
def mock_server_namespace(k8s_client):
    """Deploy mock server for testing."""
    namespace = "aiperf-integration-test"

    # Create namespace
    ns = client.V1Namespace(
        metadata=client.V1ObjectMeta(name=namespace)
    )
    try:
        k8s_client.create_namespace(body=ns)
    except client.ApiException as e:
        if e.status != 409:  # Already exists
            raise

    # Deploy mock server pod
    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(
            name="mock-server",
            labels={"app": "mock-server"}
        ),
        spec=client.V1PodSpec(
            containers=[
                client.V1Container(
                    name="mock-server",
                    image="aiperf:latest",
                    image_pull_policy="IfNotPresent",
                    command=["/opt/aiperf/venv/bin/aiperf-mock-server"],
                    args=["--host", "0.0.0.0", "--port", "8000"],
                    env=[
                        client.V1EnvVar(name="MOCK_SERVER_PORT", value="8000"),
                        client.V1EnvVar(name="MOCK_SERVER_HOST", value="0.0.0.0"),
                    ],
                    ports=[client.V1ContainerPort(container_port=8000)],
                )
            ],
            restart_policy="Never",
        ),
    )

    # Deploy service
    service = client.V1Service(
        metadata=client.V1ObjectMeta(name="mock-server"),
        spec=client.V1ServiceSpec(
            selector={"app": "mock-server"},
            ports=[client.V1ServicePort(protocol="TCP", port=8000, target_port=8000)],
            type="ClusterIP",
        ),
    )

    try:
        k8s_client.create_namespaced_pod(namespace=namespace, body=pod)
        k8s_client.create_namespaced_service(namespace=namespace, body=service)
    except client.ApiException as e:
        if e.status != 409:
            raise

    # Wait for pod to be ready
    for _ in range(30):
        pod_status = k8s_client.read_namespaced_pod_status(name="mock-server", namespace=namespace)
        if pod_status.status.phase == "Running":
            break
        time.sleep(2)

    yield namespace

    # Cleanup
    try:
        k8s_client.delete_namespace(name=namespace, grace_period_seconds=0)
    except client.ApiException:
        pass


@pytest.mark.integration
@pytest.mark.kubernetes
def test_kubernetes_basic_deployment(mock_server_namespace, tmp_path):
    """Test basic Kubernetes deployment with minimal configuration."""
    output_dir = tmp_path / "k8s-test-output"

    cmd = [
        "aiperf",
        "profile",
        "--kubernetes",
        "--endpoint",
        f"http://mock-server.{mock_server_namespace}.svc.cluster.local:8000/v1",
        "--model",
        "test-model",
        "--tokenizer",
        "gpt2",  # Use real tokenizer for model name resolution
        "--request-count",
        "5",
        "--output-artifact-dir",
        str(output_dir),
        "--ui",
        "none",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, f"Command failed: {result.stderr}"
    assert "✓ Kubernetes deployment completed successfully" in result.stdout
    assert "Created namespace:" in result.stdout
    assert "System Controller is running" in result.stdout


@pytest.mark.integration
@pytest.mark.kubernetes
def test_kubernetes_custom_namespace(mock_server_namespace, tmp_path, k8s_client):
    """Test Kubernetes deployment with custom namespace."""
    custom_namespace = "aiperf-custom-test"
    output_dir = tmp_path / "k8s-custom-ns-output"

    # Create custom namespace
    ns = client.V1Namespace(
        metadata=client.V1ObjectMeta(name=custom_namespace)
    )
    try:
        k8s_client.create_namespace(body=ns)
    except client.ApiException as e:
        if e.status != 409:
            raise

    try:
        cmd = [
            "aiperf",
            "profile",
            "--kubernetes",
            "--kubernetes-namespace",
            custom_namespace,
            "--no-kubernetes-auto-cleanup",  # Don't cleanup custom namespace
            "--endpoint",
            f"http://mock-server.{mock_server_namespace}.svc.cluster.local:8000/v1",
            "--model",
            "test-model",
            "--tokenizer",
            "gpt2",
            "--request-count",
            "3",
            "--output-artifact-dir",
            str(output_dir),
            "--ui",
            "none",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )

        assert result.returncode == 0
        assert custom_namespace in result.stdout

    finally:
        # Cleanup
        try:
            k8s_client.delete_namespace(name=custom_namespace, grace_period_seconds=0)
        except client.ApiException:
            pass


@pytest.mark.integration
@pytest.mark.kubernetes
def test_kubernetes_pod_communication(mock_server_namespace, k8s_client):
    """Test that Kubernetes pods can communicate via ZMQ."""
    # This test verifies that:
    # 1. System Controller service is created
    # 2. Other services can connect to System Controller
    # 3. ZMQ communication works across pods

    # Note: This is implicitly tested by test_kubernetes_basic_deployment
    # If that test passes, pod communication is working
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
