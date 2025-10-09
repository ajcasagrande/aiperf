# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Kubernetes runner for AIPerf - deploys to K8s cluster."""

import asyncio
from pathlib import Path

from aiperf.cli_utils import raise_startup_error_and_exit
from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.kubernetes.orchestrator import KubernetesOrchestrator


async def run_kubernetes_deployment(
    user_config: UserConfig,
    service_config: ServiceConfig,
) -> int:
    """Run AIPerf on Kubernetes cluster with local CLI orchestrator.

    Architecture:
    - CLI Orchestrator: Runs LOCALLY (this process)
    - System Controller: Runs IN CLUSTER (Kubernetes pod)
    - Communication: CLI monitors via K8s API and optional ZMQ TCP
    - Results: Retrieved from cluster pods to local filesystem
    - UI: Runs locally, monitors cluster status

    Args:
        user_config: User configuration
        service_config: Service configuration with Kubernetes enabled

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = AIPerfLogger(__name__)

    try:
        # Import CLI orchestrator
        from aiperf.orchestrator import CLIOrchestrator

        # Create Kubernetes cluster orchestrator
        k8s_orchestrator = KubernetesOrchestrator(
            user_config=user_config,
            service_config=service_config,
        )

        # Deploy to cluster
        logger.info("Deploying AIPerf to Kubernetes cluster...")
        success = await k8s_orchestrator.deploy()

        if not success:
            logger.error("Deployment failed")
            return 1

        logger.info("✓ AIPerf deployed to cluster")

        # Create LOCAL CLI orchestrator to monitor and display UI
        # Note: We create a mock system controller reference since it's in the cluster
        from aiperf.orchestrator.kubernetes_cli_bridge import KubernetesCliBridge

        cli_bridge = KubernetesCliBridge(
            user_config=user_config,
            service_config=service_config,
            k8s_orchestrator=k8s_orchestrator,
        )

        # Initialize and start local CLI orchestrator with UI
        await cli_bridge.initialize()
        await cli_bridge.start()

        # Monitor cluster and wait for completion
        logger.info("Monitoring benchmark on cluster...")
        completed = await k8s_orchestrator.wait_for_completion(timeout=7200)

        if not completed:
            logger.error("Benchmark did not complete successfully")
            logs = await k8s_orchestrator.get_logs()
            for pod_name, pod_logs in list(logs.items())[:5]:
                logger.error(f"\n=== Logs from {pod_name} ===\n{pod_logs[-1000:]}")
            await cli_bridge.stop()
            await k8s_orchestrator.cleanup()
            return 1

        # Retrieve artifacts from cluster
        logger.info("Retrieving artifacts from cluster...")
        local_artifacts_dir = user_config.output.artifact_directory
        success = await k8s_orchestrator.retrieve_artifacts(local_artifacts_dir)

        if not success:
            logger.warning("Failed to retrieve some artifacts")

        # Stop CLI orchestrator (will display results)
        await cli_bridge.stop()

        # Cleanup cluster resources
        await k8s_orchestrator.cleanup()

        logger.info("Kubernetes deployment complete!")
        logger.info(f"Artifacts available at: {local_artifacts_dir}")

        return cli_bridge.get_exit_code()

    except Exception as e:
        logger.exception(f"Kubernetes deployment failed: {e}")
        return 1


def run_aiperf_kubernetes(
    user_config: UserConfig,
    service_config: ServiceConfig,
) -> None:
    """Entry point for Kubernetes deployment mode.

    Args:
        user_config: User configuration
        service_config: Service configuration
    """
    logger = AIPerfLogger(__name__)

    # Validate Kubernetes configuration
    if not service_config.kubernetes.enabled:
        raise_startup_error_and_exit(
            "Kubernetes mode not enabled. Use --kubernetes flag.",
            title="Configuration Error",
        )

    logger.info("AIPerf Kubernetes Deployment Mode")
    logger.info(f"Target namespace: {service_config.kubernetes.namespace or 'auto-generated'}")
    logger.info(f"Container image: {service_config.kubernetes.image}")

    # Run deployment
    try:
        exit_code = asyncio.run(
            run_kubernetes_deployment(
                user_config=user_config,
                service_config=service_config,
            )
        )

        import sys
        sys.exit(exit_code)

    except KeyboardInterrupt:
        logger.info("Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
