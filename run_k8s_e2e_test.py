#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Run end-to-end Kubernetes deployment test."""

import asyncio
import sys
import time

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config import EndpointConfig, LoadGeneratorConfig, ServiceConfig, UserConfig
from aiperf.common.config.input_config import InputConfig
from aiperf.common.enums import ServiceRunType
from aiperf.kubernetes.orchestrator import KubernetesOrchestrator

logger = AIPerfLogger(__name__)


async def run_e2e_test():
    """Run complete end-to-end test."""
    logger.info("=" * 70)
    logger.info("AIPerf Kubernetes End-to-End Test")
    logger.info("=" * 70)

    # Configuration
    test_namespace = f"aiperf-e2e-{int(time.time())}"
    logger.info(f"Test namespace: {test_namespace}")

    user_config = UserConfig(
        endpoint=EndpointConfig(
            url="http://mock-llm-service.default.svc.cluster.local:8000",
            model_names=["mock-model"],
            endpoint_type="chat",
            streaming=True,
        ),
        input=InputConfig(public_dataset="sharegpt"),
        load_generator=LoadGeneratorConfig(
            benchmark_duration=30,
            concurrency=5,
        ),
    )

    service_config = ServiceConfig()
    service_config.service_run_type = ServiceRunType.KUBERNETES
    service_config.kubernetes.enabled = True
    service_config.kubernetes.namespace = test_namespace
    service_config.kubernetes.image = "aiperf:latest"
    service_config.kubernetes.image_pull_policy = "IfNotPresent"
    service_config.kubernetes.cleanup_on_completion = True

    try:
        logger.info("\n[1/5] Creating Kubernetes orchestrator...")
        orchestrator = KubernetesOrchestrator(
            user_config=user_config,
            service_config=service_config,
        )
        logger.info("✓ Orchestrator created")

        logger.info("\n[2/5] Deploying AIPerf to cluster...")
        success = await orchestrator.deploy()

        if not success:
            logger.error("✗ Deployment failed")
            return 1

        logger.info("✓ AIPerf deployed successfully")

        # Check pods
        logger.info("\n[3/5] Verifying pods...")
        pods = orchestrator.resource_manager.core_api.list_namespaced_pod(
            namespace=test_namespace
        )
        logger.info(f"Pods in namespace: {len(pods.items)}")
        for pod in pods.items:
            logger.info(f"  - {pod.metadata.name}: {pod.status.phase}")

        logger.info("\n[4/5] Waiting for benchmark to complete...")
        completed = await orchestrator.wait_for_completion(timeout=300)

        if not completed:
            logger.error("✗ Benchmark did not complete successfully")
            # Get logs
            logs = await orchestrator.get_logs()
            for pod_name, pod_logs in list(logs.items())[:3]:  # Show first 3
                logger.error(f"\nLogs from {pod_name}:")
                logger.error(pod_logs[-500:])  # Last 500 chars
            return 1

        logger.info("✓ Benchmark completed")

        logger.info("\n[5/5] Retrieving artifacts...")
        from pathlib import Path

        artifacts_dir = Path("./artifacts-k8s-test")
        success = await orchestrator.retrieve_artifacts(artifacts_dir)

        if success:
            logger.info(f"✓ Artifacts retrieved to {artifacts_dir}")
        else:
            logger.warning("⚠ Artifact retrieval had issues")

        # Cleanup
        logger.info("\nCleaning up...")
        await orchestrator.cleanup()
        logger.info("✓ Cleanup complete")

        logger.info("\n" + "=" * 70)
        logger.info("✓✓✓ END-TO-END TEST PASSED ✓✓✓")
        logger.info("=" * 70)
        logger.info("\nKubernetes deployment is fully functional!")

        return 0

    except Exception as e:
        logger.error(f"\n✗ Test failed with error: {e}")
        logger.exception("Full traceback:")

        # Attempt cleanup
        try:
            from aiperf.kubernetes.resource_manager import KubernetesResourceManager

            rm = KubernetesResourceManager(namespace=test_namespace)
            await rm.cleanup_all(delete_namespace=True)
        except:
            pass

        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_e2e_test())
    sys.exit(exit_code)
