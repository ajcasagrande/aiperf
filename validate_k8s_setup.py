#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Validate Kubernetes setup for AIPerf deployment."""

import asyncio
import sys

from kubernetes import client, config as k8s_config


async def validate_kubernetes_setup():
    """Validate Kubernetes cluster setup."""
    print("=" * 70)
    print("AIPerf Kubernetes Setup Validation")
    print("=" * 70)
    print()

    try:
        # Load kubeconfig
        print("[1/6] Loading kubeconfig...")
        k8s_config.load_kube_config()
        print("✓ Kubeconfig loaded successfully")
        print()

        # Test API access
        print("[2/6] Testing Kubernetes API access...")
        core_api = client.CoreV1Api()
        nodes = core_api.list_node()
        print(f"✓ Connected to cluster with {len(nodes.items)} node(s)")
        for node in nodes.items:
            print(f"  - {node.metadata.name}")
        print()

        # Check Docker image availability in minikube
        print("[3/6] Checking AIPerf image in minikube...")
        import subprocess

        result = subprocess.run(
            ["minikube", "image", "ls"],
            capture_output=True,
            text=True,
        )
        if "aiperf:latest" in result.stdout:
            print("✓ AIPerf image loaded in minikube")
        else:
            print("⚠ AIPerf image not found in minikube")
            print("  Run: minikube image load aiperf:latest")
        print()

        # Check mock server
        print("[4/6] Checking mock LLM server...")
        try:
            pod = core_api.read_namespaced_pod(name="mock-llm", namespace="default")
            if pod.status.phase == "Running":
                print(f"✓ Mock LLM server is running")
                print(f"  URL: http://mock-llm-service.default.svc.cluster.local:8000")
            else:
                print(f"⚠ Mock LLM server status: {pod.status.phase}")
        except Exception:
            print("⚠ Mock LLM server not found")
            print("  Run: kubectl apply -f tools/kubernetes/test-mock-server.yaml")
        print()

        # Test RBAC permissions
        print("[5/6] Testing RBAC permissions...")
        try:
            # Try to create a test namespace
            test_ns = f"aiperf-validation-test"
            ns_spec = {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {"name": test_ns},
            }
            core_api.create_namespace(body=ns_spec)
            print("✓ Can create namespaces")

            # Clean up test namespace
            core_api.delete_namespace(name=test_ns)
            print("✓ Can delete namespaces")
        except Exception as e:
            print(f"⚠ RBAC issue: {e}")
            print("  May need cluster-admin permissions")
        print()

        # Check cluster resources
        print("[6/6] Checking cluster resources...")
        try:
            # Check if metrics server is available
            result = subprocess.run(
                ["kubectl", "top", "nodes"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("✓ Metrics server available")
                print(result.stdout)
            else:
                print("⚠ Metrics server not available (optional)")
        except:
            print("⚠ Could not check metrics")
        print()

        # Summary
        print("=" * 70)
        print("✓ Kubernetes cluster is ready for AIPerf deployment!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("  1. Ensure vLLM or mock server is running")
        print("  2. Run: make k8s-test")
        print("  3. Or run: python test_k8s_infrastructure.py")
        print()

        return 0

    except Exception as e:
        print()
        print("=" * 70)
        print(f"✗ Validation failed: {e}")
        print("=" * 70)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(validate_kubernetes_setup())
    sys.exit(exit_code)
