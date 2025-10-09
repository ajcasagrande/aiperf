#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Debug Kubernetes deployment issues."""

import asyncio
import sys
import time

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config import EndpointConfig, LoadGeneratorConfig, ServiceConfig, UserConfig
from aiperf.common.config.input_config import InputConfig
from aiperf.common.enums import ServiceRunType, ServiceType
from aiperf.kubernetes.config_serializer import ConfigSerializer
from aiperf.kubernetes.resource_manager import KubernetesResourceManager
from aiperf.kubernetes.templates import PodTemplateBuilder

logger = AIPerfLogger(__name__)


async def debug_deployment():
    """Debug deployment step by step."""
    logger.info("=" * 70)
    logger.info("AIPerf Kubernetes Deployment Debug")
    logger.info("=" * 70)

    test_namespace = f"aiperf-debug-{int(time.time())}"
    logger.info(f"Debug namespace: {test_namespace} (will NOT auto-cleanup)")

    try:
        # Step 1: Create resource manager
        logger.info("\n[1] Creating resource manager...")
        rm = KubernetesResourceManager(namespace=test_namespace)
        logger.info("✓ Resource manager created")

        # Step 2: Create namespace
        logger.info("\n[2] Creating namespace...")
        await rm.create_namespace()
        logger.info(f"✓ Namespace {test_namespace} created")

        # Step 3: Create template builder
        logger.info("\n[3] Creating template builder...")
        builder = PodTemplateBuilder(
            namespace=test_namespace,
            image="aiperf:k8s-final",
            image_pull_policy="Never",
            service_account="aiperf-service-account",
            system_controller_service="aiperf-system-controller",
        )
        logger.info("✓ Template builder created")

        # Step 4: Create RBAC
        logger.info("\n[4] Creating RBAC resources...")
        sa, role, binding = builder.build_rbac_resources()
        await rm.create_rbac_resources(sa, role, binding)
        logger.info("✓ RBAC created")

        # Step 5: Create ConfigMap with correct configuration
        logger.info("\n[5] Creating ConfigMap...")
        from aiperf.common.config import TokenizerConfig

        user_config = UserConfig(
            endpoint=EndpointConfig(
                url="http://mock-llm-service.default.svc.cluster.local:8000",
                model_names=["gpt2"],  # Use real model for tokenizer
                endpoint_type="chat",
                streaming=True,
            ),
            input=InputConfig(public_dataset="sharegpt"),
            load_generator=LoadGeneratorConfig(benchmark_duration=30, concurrency=5),
            tokenizer=TokenizerConfig(name="gpt2"),  # Explicit tokenizer
            gpu_telemetry=[],
        )

        from aiperf.common.config.zmq_config import ZMQTCPConfig

        service_config = ServiceConfig()
        service_config.service_run_type = ServiceRunType.KUBERNETES
        # Set basic TCP config - entrypoint will modify based on service type
        service_config.zmq_tcp = ZMQTCPConfig(host="0.0.0.0")
        service_config.zmq_ipc = None

        config_data = ConfigSerializer.serialize_to_configmap(user_config, service_config)
        await rm.create_configmap("aiperf-config", config_data)
        logger.info("✓ ConfigMap created")

        # Step 6: Create Kubernetes services
        logger.info("\n[6] Creating Kubernetes services...")
        sc_svc = builder.build_system_controller_service()
        await rm.create_service(sc_svc)
        tm_svc = builder.build_timing_manager_service()
        await rm.create_service(tm_svc)
        rm_svc = builder.build_records_manager_service()
        await rm.create_service(rm_svc)
        logger.info("✓ Services created (system-controller, timing-manager, records-manager)")

        # Step 7: Deploy system controller pod
        logger.info("\n[7] Deploying system controller pod...")
        pod_spec = builder.build_pod_spec(
            service_type=ServiceType.SYSTEM_CONTROLLER,
            service_id="system-controller",
            config_map_name="aiperf-config",
            cpu="2",
            memory="2Gi",
        )

        logger.info(f"Pod spec: {pod_spec['metadata']['name']}")
        pod_name = await rm.create_pod(pod_spec)
        logger.info(f"✓ Pod {pod_name} created")

        # Step 8: Wait and check status
        logger.info("\n[8] Waiting for pod (30s max)...")
        for i in range(15):
            await asyncio.sleep(2)
            pod = rm.core_api.read_namespaced_pod(name=pod_name, namespace=test_namespace)
            phase = pod.status.phase
            logger.info(f"  [{i*2}s] Pod status: {phase}")

            if phase == "Running":
                logger.info("✓ Pod is running!")
                break
            elif phase == "Failed":
                logger.error(f"✗ Pod failed!")
                # Get logs
                logger.info("\nGetting pod logs...")
                logs = await rm.get_pod_logs(pod_name, tail_lines=50)
                logger.error(f"Pod logs:\n{logs}")

                # Get pod description
                logger.info("\nPod status details:")
                if pod.status.container_statuses:
                    for cs in pod.status.container_statuses:
                        logger.error(f"Container: {cs.name}")
                        if cs.state.terminated:
                            logger.error(f"  Exit code: {cs.state.terminated.exit_code}")
                            logger.error(f"  Reason: {cs.state.terminated.reason}")
                            logger.error(f"  Message: {cs.state.terminated.message}")
                        if cs.state.waiting:
                            logger.error(f"  Waiting reason: {cs.state.waiting.reason}")
                            logger.error(f"  Waiting message: {cs.state.waiting.message}")
                break

        logger.info("\n" + "=" * 70)
        logger.info("Debug session complete")
        logger.info(f"Namespace {test_namespace} preserved for inspection")
        logger.info(f"To cleanup: kubectl delete namespace {test_namespace}")
        logger.info("=" * 70)

        return 0 if phase == "Running" else 1

    except Exception as e:
        logger.error(f"Debug failed: {e}")
        logger.exception("Full traceback:")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(debug_deployment())
    sys.exit(exit_code)
