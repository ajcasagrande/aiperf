# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Container entrypoint for AIPerf services running in Kubernetes."""

import asyncio
import os
import sys

from kubernetes import client, config

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.enums import ServiceType
from aiperf.common.factories import ServiceFactory
from aiperf.kubernetes.config_serializer import ConfigSerializer

logger = AIPerfLogger(__name__)


def main():
    """Main entrypoint for Kubernetes pod services."""
    # Get environment variables
    service_type_str = os.getenv("AIPERF_SERVICE_TYPE")
    service_id = os.getenv("AIPERF_SERVICE_ID")
    config_map_name = os.getenv("AIPERF_CONFIG_MAP")
    namespace = os.getenv("AIPERF_NAMESPACE")

    if not all([service_type_str, service_id, config_map_name, namespace]):
        logger.error("Missing required environment variables")
        sys.exit(1)

    logger.info(f"Starting AIPerf service: {service_type_str} (ID: {service_id})")

    try:
        # Load in-cluster config
        config.load_incluster_config()

        # Read ConfigMap to get user and service config
        core_api = client.CoreV1Api()
        config_map = core_api.read_namespaced_config_map(
            name=config_map_name, namespace=namespace
        )

        # Deserialize configs
        user_config, service_config = ConfigSerializer.deserialize_from_configmap(
            config_map.data
        )

        # Get service type enum
        service_type = ServiceType(service_type_str)

        # Create FRESH ZMQ TCP config for each service based on its role
        # This ensures clean config without inherited/serialized values
        from aiperf.common.config.zmq_config import ZMQTCPConfig

        sc_dns = f"{os.getenv('AIPERF_SYSTEM_CONTROLLER_SERVICE', 'aiperf-system-controller')}.{namespace}.svc.cluster.local"
        tm_dns = f"timing-manager.{namespace}.svc.cluster.local"
        rm_dns = f"records-manager.{namespace}.svc.cluster.local"

        if service_type == ServiceType.SYSTEM_CONTROLLER:
            # System controller BINDS all proxies to 0.0.0.0
            service_config.zmq_tcp = ZMQTCPConfig(host="0.0.0.0")
            logger.info("SystemController: ZMQTCPConfig(host=0.0.0.0) - proxies will bind to all interfaces")

        elif service_type == ServiceType.TIMING_MANAGER:
            # TimingManager BINDS credits but CONNECTS to proxies
            # Create config with sc_dns so PROXIES point there, then override main host for binding
            service_config.zmq_tcp = ZMQTCPConfig(host=sc_dns)  # Proxies inherit this
            service_config.zmq_tcp.host = "0.0.0.0"  # But direct connections bind
            logger.info(f"TimingManager: direct=0.0.0.0 (bind), proxies={sc_dns} (connect)")

        elif service_type == ServiceType.RECORDS_MANAGER:
            # RecordsManager BINDS records but CONNECTS to proxies
            service_config.zmq_tcp = ZMQTCPConfig(host=sc_dns)  # Proxies inherit this
            service_config.zmq_tcp.host = "0.0.0.0"  # But direct connections bind
            logger.info(f"RecordsManager: direct=0.0.0.0 (bind), proxies={sc_dns} (connect)")

        elif service_type == ServiceType.WORKER:
            # Workers CONNECT to timing-manager for credits, system-controller for proxies
            service_config.zmq_tcp = ZMQTCPConfig(host=sc_dns)  # Proxies inherit
            service_config.zmq_tcp.host = tm_dns  # Override for direct connections
            logger.info(f"Worker: direct={tm_dns} (credits), proxies={sc_dns}")

        elif service_type == ServiceType.RECORD_PROCESSOR:
            # RecordProcessors CONNECT to records-manager for records, system-controller for proxies
            service_config.zmq_tcp = ZMQTCPConfig(host=sc_dns)  # Proxies inherit
            service_config.zmq_tcp.host = rm_dns  # Override for direct connections
            logger.info(f"RecordProcessor: direct={rm_dns} (records), proxies={sc_dns}")

        else:
            # Other services CONNECT to system controller for everything
            service_config.zmq_tcp = ZMQTCPConfig(host=sc_dns)
            logger.info(f"{service_type.value}: all={sc_dns}")

        # Load all service modules to ensure they're registered with ServiceFactory
        from aiperf import module_loader
        module_loader.ensure_modules_loaded()

        # Get the service class from factory registry
        logger.info(f"Looking up service class for {service_type.value}")
        from aiperf.common.factories import ServiceFactory

        if service_type not in ServiceFactory._registry:
            logger.error(f"Service type {service_type} not registered")
            logger.error(f"Available: {list(ServiceFactory._registry.keys())}")
            sys.exit(1)

        service_class = ServiceFactory._registry[service_type]
        logger.info(f"Found service class: {service_class.__name__}")

        # Use bootstrap_and_run_service for proper lifecycle management
        from aiperf.common.bootstrap import bootstrap_and_run_service

        bootstrap_and_run_service(
            service_class=service_class,
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )

    except Exception as e:
        logger.exception(f"Failed to start service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
