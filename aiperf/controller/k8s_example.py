#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Example demonstrating how to use the Kubernetes Service Manager.

This example shows how to configure and use the Kubernetes service manager
for running AIPerf services on Kubernetes clusters.
"""

import asyncio
import subprocess

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceRunType, ServiceType
from aiperf.common.factories import ServiceManagerFactory


async def example_kubernetes_usage():
    """Example showing how to use Kubernetes service manager."""

    # Example Kubernetes configuration
    k8s_config = {
        "k8s_namespace": "aiperf",  # Kubernetes namespace
        "kubeconfig_path": None,  # Use default kubeconfig
        "in_cluster": False,  # Set to True if running inside K8s
        "docker_image": "your-registry/aiperf:latest",  # Your AIPerf Docker image
        "image_pull_policy": "IfNotPresent",  # Image pull policy
        "service_account": "aiperf-service-account",  # Service account for pods
        "node_selector": {  # Node selector for pod placement
            "node-type": "compute",
            # "gpu": "true",  # Uncomment if you need GPU nodes
        },
        "resource_requests": {  # Resource requests
            "cpu": "0.5",
            "memory": "1Gi",
        },
        "resource_limits": {  # Resource limits
            "cpu": "2",
            "memory": "4Gi",
        },
        "pod_labels": {  # Additional labels for pods
            "app": "aiperf",
            "version": "v1.0",
        },
        "pod_annotations": {  # Additional annotations for pods
            "deployment.kubernetes.io/revision": "1",
        },
        "python_executable": "python3",  # Python executable in container
    }

    # Create service and user configs (you'd load these from your config files)
    service_config = ServiceConfig(
        service_run_type=ServiceRunType.KUBERNETES,
        # ... other service config options
    )

    user_config = UserConfig(
        # ... your user config options
    )

    # Define which services to run
    required_services = {
        ServiceType.DATASET_MANAGER: 1,
        ServiceType.TIMING_MANAGER: 1,
        ServiceType.WORKER_MANAGER: 1,
        ServiceType.RECORDS_MANAGER: 1,
        ServiceType.RECORD_PROCESSOR: 2,  # Run 2 record processors
        ServiceType.WORKER: 4,  # Run 4 workers
    }

    # Create Kubernetes service manager
    service_manager = ServiceManagerFactory.create_instance(
        ServiceRunType.KUBERNETES,
        required_services=required_services,
        service_config=service_config,
        user_config=user_config,
        **k8s_config,
    )

    try:
        # Initialize and start the service manager
        await service_manager.initialize()
        await service_manager.start()

        print("Kubernetes service manager started successfully!")
        print(f"Created {sum(required_services.values())} Kubernetes pods")

        # List the created pods
        print("\\nCreated pods:")
        for pod in service_manager.kubernetes_pods:
            print(
                f"  - {pod.pod_name} ({pod.service_type}) in namespace {pod.namespace}"
            )

        # Wait for services to register (in a real application, you'd handle this differently)
        stop_event = asyncio.Event()
        await service_manager.wait_for_all_services_registration(stop_event)
        print("\\nAll services registered!")

        # Wait for services to start
        await service_manager.wait_for_all_services_start(stop_event)
        print("All services started!")

        # In a real application, you would run your benchmark here
        # For this example, we'll just wait a bit
        print("\\nRunning benchmark simulation for 30 seconds...")
        await asyncio.sleep(30)

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Clean up - stop all services
        print("\\nStopping all Kubernetes pods...")
        try:
            await service_manager.shutdown_all_services()
            print("All Kubernetes pods stopped successfully")
        except Exception as e:
            print(f"Error stopping services: {e}")
            # Force kill if graceful shutdown fails
            await service_manager.kill_all_services()


def check_kubernetes_availability():
    """Check if Kubernetes is available on this system."""
    try:
        # Check if kubectl is available
        subprocess.run(
            ["kubectl", "version", "--client"], check=True, capture_output=True
        )

        # Check if we can connect to cluster
        result = subprocess.run(
            ["kubectl", "cluster-info"], check=True, capture_output=True, text=True
        )
        return True, result.stdout.strip()

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        return False, str(e)


def create_example_namespace():
    """Create example Kubernetes namespace and service account."""
    namespace_yaml = """
apiVersion: v1
kind: Namespace
metadata:
  name: aiperf
  labels:
    name: aiperf
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aiperf-service-account
  namespace: aiperf
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: aiperf-role
rules:
- apiGroups: [""]
  resources: ["pods", "services", "endpoints"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: aiperf-role-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: aiperf-role
subjects:
- kind: ServiceAccount
  name: aiperf-service-account
  namespace: aiperf
"""

    print("Example Kubernetes namespace and RBAC configuration:")
    print("=" * 60)
    print(namespace_yaml)
    print("=" * 60)
    print("Save this to 'aiperf-k8s-setup.yaml' and apply with:")
    print("kubectl apply -f aiperf-k8s-setup.yaml")
    return namespace_yaml


def create_example_dockerfile():
    """Create example Dockerfile for AIPerf services."""
    dockerfile_content = """
# Example Dockerfile for AIPerf services
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy AIPerf source code
COPY . .

# Install AIPerf in development mode
RUN pip install -e .

# Set default command (will be overridden by Kubernetes pod spec)
CMD ["python", "-m", "aiperf.controller.system_controller"]
"""

    print("\\nExample Dockerfile for AIPerf services:")
    print("=" * 60)
    print(dockerfile_content)
    print("=" * 60)
    print("Build with: docker build -t your-registry/aiperf:latest .")
    print("Push with: docker push your-registry/aiperf:latest")
    return dockerfile_content


if __name__ == "__main__":
    print("Kubernetes Service Manager Example")
    print("=" * 50)

    # Check if Kubernetes is available
    k8s_available, k8s_info = check_kubernetes_availability()

    if not k8s_available:
        print("WARNING: Kubernetes (kubectl) not found or not connected to cluster")
        print(f"Error: {k8s_info}")
        print("\\nThis example requires kubectl to be installed and configured")
        print("Please ensure you have access to a Kubernetes cluster")

        # Still show the configuration examples
        print("\\n" + "=" * 50)
        create_example_namespace()
        create_example_dockerfile()
        print("\\nOnce Kubernetes is set up, run this example again.")
        exit(1)

    print("✓ Kubernetes cluster detected:")
    print(k8s_info)

    # Show setup information
    print("\\n" + "=" * 50)
    create_example_namespace()
    create_example_dockerfile()

    print("\\n" + "=" * 50)
    print("Prerequisites:")
    print("1. Build and push your AIPerf Docker image")
    print("2. Apply the Kubernetes namespace and RBAC configuration")
    print("3. Update the docker_image in the configuration")
    print("\\nRunning example...")

    # Run the example
    try:
        asyncio.run(example_kubernetes_usage())
    except KeyboardInterrupt:
        print("\\nExample interrupted by user")
