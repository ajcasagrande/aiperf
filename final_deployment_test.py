#!/usr/bin/env python3
# FINAL DEPLOYMENT TEST - This should work!

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

logger = AIPerfLogger(__name__)


async def final_test():
    """Run the final deployment test with all fixes."""
    test_namespace = f"aiperf-final-{int(time.time())}"
    logger.info("=" * 70)
    logger.info("AIPerf Kubernetes - FINAL DEPLOYMENT TEST")
    logger.info("=" * 70)
    logger.info(f"Namespace: {test_namespace}")

    try:
        rm = KubernetesResourceManager(namespace=test_namespace)
        await rm.create_namespace()
        logger.info("✓ Namespace created")

        builder = PodTemplateBuilder(
            namespace=test_namespace,
            image="aiperf:k8s-new",
            image_pull_policy="Never",
            service_account="aiperf-service-account",
            system_controller_service="aiperf-system-controller",
        )

        sa, role, binding = builder.build_rbac_resources()
        await rm.create_rbac_resources(sa, role, binding)
        logger.info("✓ RBAC created")

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
        logger.info("✓ ConfigMap created")

        svc_spec = builder.build_system_controller_service()
        await rm.create_service(svc_spec)
        logger.info("✓ Service created")

        pod_spec = builder.build_pod_spec(
            service_type=ServiceType.SYSTEM_CONTROLLER,
            service_id="system-controller",
            config_map_name="aiperf-config",
            cpu="2",
            memory="2Gi",
        )
        await rm.create_pod(pod_spec)
        logger.info("✓ System controller pod created")

        # Monitor progress
        logger.info("\nMonitoring deployment progress...")
        for i in range(24):  # Monitor for 2 minutes (5s intervals)
            await asyncio.sleep(5)

            pods = rm.core_api.list_namespaced_pod(namespace=test_namespace)
            running = sum(1 for p in pods.items if p.status.phase == "Running")
            completed = sum(1 for p in pods.items if p.status.phase == "Completed")
            failed = sum(1 for p in pods.items if p.status.phase == "Failed")

            logger.info(
                f"[{(i+1)*5}s] Pods: {len(pods.items)} total, {running} running, {completed} completed, {failed} failed"
            )

            # List pods
            for pod in pods.items:
                logger.info(f"  - {pod.metadata.name}: {pod.status.phase}")

            # Check system controller logs for key messages
            try:
                sc_logs = await rm.get_pod_logs("system-controller", tail_lines=50)
                if "PROFILING" in sc_logs:
                    logger.info("\n" + "=" * 70)
                    logger.info("✓✓✓ SUCCESS! BENCHMARK IS PROFILING! ✓✓✓")
                    logger.info("=" * 70)
                    break
                elif "CONFIGURED" in sc_logs:
                    logger.info("✓ Services configured, waiting for profiling to start...")
                elif "Registered" in sc_logs and i >= 3:
                    logger.info("✓ Services registering successfully...")
            except:
                pass

        logger.info(f"\nNamespace {test_namespace} preserved for inspection")
        logger.info(f"To view logs: kubectl logs <pod-name> -n {test_namespace}")
        logger.info(f"To cleanup: kubectl delete namespace {test_namespace}")

    except Exception as e:
        logger.exception(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(final_test())
