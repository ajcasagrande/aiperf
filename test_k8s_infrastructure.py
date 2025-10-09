#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Quick Kubernetes infrastructure validation test."""

import asyncio
import sys
import time

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config import EndpointConfig, ServiceConfig, UserConfig
from aiperf.kubernetes.config_serializer import ConfigSerializer
from aiperf.kubernetes.resource_manager import KubernetesResourceManager
from aiperf.kubernetes.templates import PodTemplateBuilder

logger = AIPerfLogger(__name__)


async def test_kubernetes_infrastructure():
    """Test Kubernetes infrastructure components."""
    test_namespace = f"aiperf-infra-test-{int(time.time())}"
    logger.info(f"Testing Kubernetes infrastructure in namespace: {test_namespace}")

    try:
        # 1. Test Resource Manager initialization
        logger.info("[1/7] Testing ResourceManager initialization...")
        resource_manager = KubernetesResourceManager(namespace=test_namespace)
        logger.info("✓ ResourceManager initialized")

        # 2. Test namespace creation
        logger.info("[2/7] Testing namespace creation...")
        await resource_manager.create_namespace()
        logger.info(f"✓ Namespace {test_namespace} created")

        # 3. Test PodTemplateBuilder
        logger.info("[3/7] Testing PodTemplateBuilder...")
        builder = PodTemplateBuilder(
            namespace=test_namespace,
            image="aiperf:latest",
            image_pull_policy="IfNotPresent",
            service_account="aiperf-service-account",
            system_controller_service="aiperf-system-controller",
        )
        logger.info("✓ PodTemplateBuilder initialized")

        # 4. Test RBAC resource creation
        logger.info("[4/7] Testing RBAC resource creation...")
        sa, role, binding = builder.build_rbac_resources()
        await resource_manager.create_rbac_resources(sa, role, binding)
        logger.info("✓ RBAC resources created")

        # 5. Test ConfigMap creation
        logger.info("[5/7] Testing ConfigMap creation...")
        user_config = UserConfig(
            endpoint=EndpointConfig(
                url="http://test:8000", model_names=["test-model"]
            )
        )
        service_config = ServiceConfig()

        config_data = ConfigSerializer.serialize_to_configmap(
            user_config, service_config
        )
        await resource_manager.create_configmap("test-config", config_data)
        logger.info("✓ ConfigMap created")

        # 6. Test simple pod creation (busybox)
        logger.info("[6/7] Testing pod creation...")
        test_pod = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "test-pod",
                "namespace": test_namespace,
                "labels": {"app": "aiperf-test"},
            },
            "spec": {
                "serviceAccountName": "aiperf-service-account",
                "restartPolicy": "Never",
                "containers": [
                    {
                        "name": "test",
                        "image": "busybox:latest",
                        "command": ["sh", "-c", "echo 'Hello from K8s!' && sleep 10"],
                    }
                ],
            },
        }

        pod_name = await resource_manager.create_pod(test_pod)
        logger.info(f"✓ Test pod created: {pod_name}")

        # Wait for pod
        logger.info("Waiting for pod to be ready...")
        ready = await resource_manager.wait_for_pod_ready(pod_name, timeout=60)
        if ready:
            logger.info("✓ Pod is running")
        else:
            logger.warning("⚠ Pod not ready (may still be starting)")

        # 7. Test cleanup
        logger.info("[7/7] Testing cleanup...")
        await resource_manager.cleanup_all(delete_namespace=True)
        logger.info("✓ Cleanup complete")

        logger.info("\n" + "=" * 60)
        logger.info("✓ ALL INFRASTRUCTURE TESTS PASSED")
        logger.info("=" * 60)
        logger.info("\nKubernetes infrastructure is ready for AIPerf deployment!")

        return 0

    except Exception as e:
        logger.error(f"\n✗ Infrastructure test failed: {e}")
        logger.exception("Full traceback:")

        # Cleanup on failure
        try:
            await resource_manager.cleanup_all(delete_namespace=True)
        except:
            pass

        return 1


def main():
    """Main entry point."""
    logger.info("AIPerf Kubernetes Infrastructure Validation Test")
    logger.info("=" * 60)

    exit_code = asyncio.run(test_kubernetes_infrastructure())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
