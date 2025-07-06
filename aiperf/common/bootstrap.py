# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import contextlib
import multiprocessing

from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.service.base_service import BaseService


def bootstrap_and_run_service(
    service_class: type[BaseService],
    service_config: ServiceConfig | None = None,
    user_config: UserConfig | None = None,
    service_id: str | None = None,
    log_queue: "multiprocessing.Queue | None" = None,
    **kwargs,
):
    """Bootstrap the service and run it.

    This function will load the service configuration,
    create an instance of the service, and run it.

    Args:
        service_class: The python class of the service to run. This should be a subclass of
            BaseService. This should be a type and not an instance.
        service_config: The service configuration to use. If not provided, the service
            configuration will be loaded from the environment variables.
        user_config: The user configuration to use. If not provided, the user configuration
            will be loaded from the environment variables.
        log_queue: Optional multiprocessing queue for child process logging. If provided,
            the child process logging will be set up.
        kwargs: Additional keyword arguments to pass to the service constructor.
    """

    # Load the service configuration``
    if service_config is None:
        from aiperf.common.config import load_service_config

        service_config = load_service_config()

    # Load the user configuration
    if user_config is None:
        print(
            f"No uiser configuration provided, {service_class.__name__} will use default user configuration."
        )

    async def _run_service():
        service = service_class(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            **kwargs,
        )

        # Set up child process logging if a log queue is provided
        if log_queue is not None:
            from aiperf.common.logging import setup_child_process_logging

            setup_child_process_logging(log_queue, service.service_id, service_config)

        await service.run_forever()

    # # Profile with yappi
    # TODO: Add yappi profiling support via ServiceConfig
    # import yappi
    # yappi.set_clock_type("wall")  # Use wall time for async code
    # yappi.start()

    # TODO: random seed configuration
    # random.seed(0)

    with contextlib.suppress(asyncio.CancelledError):
        if service_config.enable_uvloop:
            import uvloop

            uvloop.run(_run_service())
        else:
            asyncio.run(_run_service())

    # yappi.stop()

    # # Get and print stats
    # stats = yappi.get_func_stats()
    # # Save to file for later analysis
    # stats.save(f"aiperf_profile_{service.service_id}.prof", type="pstat")
