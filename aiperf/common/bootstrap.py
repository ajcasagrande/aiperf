# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import multiprocessing

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.service.base_service import BaseService

__all__ = [
    "bootstrap_and_run_service",
]


def bootstrap_and_run_service(
    service_class: type[BaseService],
    service_config: ServiceConfig | None = None,
    log_queue: "multiprocessing.Queue | None" = None,
):
    """Bootstrap the service and run it.

    This function will load the service configuration,
    create an instance of the service, and run it.

    Args:
        service_class: The service class of the service to run
        service_config: The service configuration to use, if not provided, the service
            configuration will be loaded from the config file
        log_queue: Optional multiprocessing queue for child process logging

    """
    import uvloop

    # Set up child process logging if a log queue is provided
    if log_queue is not None:
        from aiperf.common.logging import setup_child_process_logging

        setup_child_process_logging(log_queue)

    # Load the service configuration
    if service_config is None:
        from aiperf.common.config.loader import load_service_config

        service_config = load_service_config()

    # Create the service instance and run it
    service = service_class(service_config=service_config)
    uvloop.run(service.run_forever())
