# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import multiprocessing
import os

from aiperf.common.config import ServiceConfig
from aiperf.common.constants import EnvDefaults
from aiperf.common.service.base_service import BaseService


def bootstrap_and_run_service(
    service_class: type[BaseService],
    service_config: ServiceConfig | None = None,
    log_queue: "multiprocessing.Queue | None" = None,
    **kwargs,
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

    # Load the service configuration
    if service_config is None:
        from aiperf.common.config import load_service_config

        service_config = load_service_config()

    # Create the service instance and run it
    service = service_class(service_config=service_config, **kwargs)

    # # Profile with yappi
    # import yappi
    # yappi.set_clock_type("wall")  # Use wall time for async code
    # yappi.start()

    # TODO: random seed configuration
    # random.seed(0)

    # Set up child process logging if a log queue is provided
    if log_queue is not None:
        from aiperf.common.logging import setup_child_process_logging

        setup_child_process_logging(log_queue, service.service_id)

    if int(os.environ.get("AIPERF_UVLOOP", EnvDefaults.AIPERF_UVLOOP)) == 1:
        import uvloop

        uvloop.run(service.run_forever())
    else:
        import asyncio

        asyncio.run(service.run_forever())

    # yappi.stop()

    # # Get and print stats
    # stats = yappi.get_func_stats()
    # # Save to file for later analysis
    # stats.save(f"aiperf_profile_{service.service_id}.prof", type="pstat")
