# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.cli_utils import raise_startup_error_and_exit
from aiperf.common.config import (
    NodeConfig,
    ServiceConfig,
    SystemControllerConfig,
    UserConfig,
)
from aiperf.common.enums import ServiceType
from aiperf.common.enums.ui_enums import AIPerfUIType


def run_system_controller(
    user_config: UserConfig,
    service_config: ServiceConfig,
    system_config: SystemControllerConfig | None = None,
) -> None:
    """Run the system controller with the given configuration."""

    from aiperf.common.aiperf_logger import AIPerfLogger
    from aiperf.common.bootstrap import bootstrap_and_run_service
    from aiperf.common.logging import get_global_log_queue
    from aiperf.controller import SystemController
    from aiperf.module_loader import ensure_modules_loaded

    logger = AIPerfLogger(__name__)

    log_queue = None
    if service_config.ui_type == AIPerfUIType.DASHBOARD:
        log_queue = get_global_log_queue()
    else:
        from aiperf.common.logging import setup_rich_logging

        setup_rich_logging(user_config, service_config)

    # Create and start the system controller
    logger.info("Starting AIPerf System")

    try:
        ensure_modules_loaded()
    except Exception as e:
        raise_startup_error_and_exit(
            f"Error loading modules: {e}",
            title="Error Loading Modules",
        )

    try:
        bootstrap_and_run_service(
            SystemController,
            service_id="system_controller",
            service_config=service_config,
            user_config=user_config,
            log_queue=log_queue,
            system_config=system_config or SystemControllerConfig(),
        )
    except Exception:
        logger.exception("Error running AIPerf System")
        raise
    finally:
        logger.debug("AIPerf System exited")


def run_individual_service(
    service_type: ServiceType,
    service_id: str | None,
    service_config: ServiceConfig,
    user_config: UserConfig | None,
) -> None:
    """Run an individual AIPerf service.

    This function is used to run a single service, typically in Kubernetes
    where each service runs in its own pod.

    Args:
        service_type: Type of service to run
        service_id: Unique ID for this service instance
        service_config: Service configuration
        user_config: User configuration (if needed for the service)
    """
    import uuid

    from aiperf.common.aiperf_logger import AIPerfLogger
    from aiperf.common.bootstrap import bootstrap_and_run_service
    from aiperf.common.factories import ServiceFactory
    from aiperf.common.logging import setup_rich_logging

    logger = AIPerfLogger(__name__)

    # Generate service ID if not provided
    if service_id is None:
        service_id = f"{service_type}_{uuid.uuid4().hex[:8]}"

    # Setup logging (individual services don't typically use dashboard UI)
    setup_rich_logging(user_config, service_config)

    logger.info(f"Starting individual {service_type} service with ID: {service_id}")

    # Get the service class for the given type
    try:
        service_class = ServiceFactory.get_class_from_type(service_type)
    except Exception as e:
        logger.error(f"Unknown service type: {service_type}")
        raise ValueError(f"Unknown service type: {service_type}") from e

    # Additional arguments based on service type
    additional_kwargs = {}

    # Some services require specific configuration
    if service_type == ServiceType.NODE_CONTROLLER:
        from aiperf.common.config import NodeConfig

        additional_kwargs["node_config"] = NodeConfig()
    elif service_type == ServiceType.SYSTEM_CONTROLLER:
        from aiperf.common.config.system_controller_config import SystemControllerConfig

        additional_kwargs["system_config"] = SystemControllerConfig()

    try:
        # Bootstrap and run the service
        bootstrap_and_run_service(
            service_class,
            service_id=service_id,
            service_config=service_config,
            user_config=user_config,
            log_queue=None,
            **additional_kwargs,
        )
    except Exception:
        logger.exception(f"Error running {service_type} service")
        raise
    finally:
        logger.debug(f"{service_type} service exited")


def run_node_controller(
    service_config: ServiceConfig,
    node_config: NodeConfig,
) -> None:
    """Run the node controller with the given configuration."""

    from aiperf.common.aiperf_logger import AIPerfLogger
    from aiperf.common.bootstrap import bootstrap_and_run_service
    from aiperf.common.config import EndpointConfig
    from aiperf.controller.node_controller import NodeController
    from aiperf.module_loader import ensure_modules_loaded

    logger = AIPerfLogger(__name__)

    log_queue = None
    from aiperf.common.logging import setup_rich_logging

    user_config = UserConfig(endpoint=EndpointConfig(model_names=["gpt-oss"]))

    setup_rich_logging(user_config, service_config)

    # Create and start the node controller
    logger.info(f"Starting AIPerf Node {node_config.node_id}")

    try:
        ensure_modules_loaded()
    except Exception as e:
        raise_startup_error_and_exit(
            f"Error loading modules: {e}",
            title="Error Loading Modules",
        )

    try:
        bootstrap_and_run_service(
            NodeController,
            service_id=f"node_controller_{node_config.node_id}",
            user_config=user_config,
            service_config=service_config,
            node_config=node_config,
            log_queue=log_queue,
        )
    except Exception:
        logger.exception("Error running AIPerf Node")
        raise
    finally:
        logger.debug("AIPerf Node exited")
