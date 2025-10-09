#!/usr/bin/env python3
# Get logs from service pods before they get deleted

import asyncio
import time

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config import EndpointConfig, LoadGeneratorConfig, ServiceConfig, UserConfig
from aiperf.common.config.input_config import InputConfig
from aiperf.common.config.zmq_config import ZMQTCPConfig
from aiperf.common.enums import ServiceRunType, ServiceType
from aiperf.kubernetes.config_serializer import ConfigSerializer
from aiperf.kubernetes.resource_manager import KubernetesResourceManager
from aiperf.kubernetes.templates import PodTemplateBuilder
from kubernetes import client

logger = AIPerfLogger(__name__)


async def debug_with_logs():
    """Deploy and capture logs before pods are killed."""
    test_namespace = f"aiperf-logs-{int(time.time())}"
    logger.info(f"Debug namespace: {test_namespace}")

    try:
        rm = KubernetesResourceManager(namespace=test_namespace)
        await rm.create_namespace()

        builder = PodTemplateBuilder(
            namespace=test_namespace,
            image="aiperf:k8s-new",
            image_pull_policy="Never",
            service_account="aiperf-service-account",
            system_controller_service="aiperf-system-controller",
        )

        sa, role, binding = builder.build_rbac_resources()
        await rm.create_rbac_resources(sa, role, binding)

        user_config = UserConfig(
            endpoint=EndpointConfig(
                url="http://mock-llm-service.default.svc.cluster.local:8000",
                model_names=["mock-model"],
                endpoint_type="chat",
                streaming=True,
            ),
            input=InputConfig(public_dataset="sharegpt"),
            load_generator=LoadGeneratorConfig(benchmark_duration=30, concurrency=5),
            gpu_telemetry=[],
        )

        service_config = ServiceConfig()
        service_config.service_run_type = ServiceRunType.KUBERNETES
        service_config.zmq_tcp = ZMQTCPConfig(host="0.0.0.0")
        service_config.zmq_ipc = None

        config_data = ConfigSerializer.serialize_to_configmap(user_config, service_config)
        await rm.create_configmap("aiperf-config", config_data)

        svc_spec = builder.build_system_controller_service()
        await rm.create_service(svc_spec)

        # Deploy system controller
        pod_spec = builder.build_pod_spec(
            service_type=ServiceType.SYSTEM_CONTROLLER,
            service_id="system-controller",
            config_map_name="aiperf-config",
            cpu="2",
            memory="2Gi",
        )
        await rm.create_pod(pod_spec)

        # Wait and periodically check for service pods
        logger.info("Waiting for service pods to be created...")
        await asyncio.sleep(15)

        # Try to get logs from service pods
        service_types = ["dataset-manager", "timing-manager", "worker-manager", "records-manager"]

        logger.info("\n=== Attempting to get service pod logs ===")
        for i in range(6):  # Check 6 times over 30 seconds
            await asyncio.sleep(5)
            logger.info(f"\n[Check {i+1}/6 at {(i+1)*5}s]")

            pods = rm.core_api.list_namespaced_pod(namespace=test_namespace)
            logger.info(f"Pods found: {len(pods.items)}")

            for pod in pods.items:
                pod_name = pod.metadata.name
                phase = pod.status.phase
                logger.info(f"  {pod_name}: {phase}")

                if pod_name != "system-controller" and phase in ["Running", "Failed", "Succeeded"]:
                    logs = await rm.get_pod_logs(pod_name, tail_lines=100)
                    if logs:
                        logger.info(f"\n=== Logs from {pod_name} ===")
                        logger.info(logs[-500:])  # Last 500 chars
                        logger.info("=== End logs ===\n")

        logger.info("\n=== Final check ===")
        await asyncio.sleep(10)
        pods = rm.core_api.list_namespaced_pod(namespace=test_namespace)
        for pod in pods.items:
            logger.info(f"{pod.metadata.name}: {pod.status.phase}")
            if pod.metadata.name != "system-controller":
                logs = await rm.get_pod_logs(pod.metadata.name, tail_lines=150)
                logger.info(f"\n=== Final logs from {pod.metadata.name} ===")
                logger.info(logs)
                logger.info("=== End ===\n")

        logger.info(f"\nNamespace {test_namespace} preserved for inspection")
        logger.info(f"To cleanup: kubectl delete namespace {test_namespace}")

    except Exception as e:
        logger.exception(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(debug_with_logs())
