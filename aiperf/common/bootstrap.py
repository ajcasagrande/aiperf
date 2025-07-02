# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import contextlib

from aiperf.common.config import ServiceConfig
from aiperf.common.service.base_service import BaseService


def bootstrap_and_run_service(
    service_class: type[BaseService],
    service_config: ServiceConfig | None = None,
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
        kwargs: Additional keyword arguments to pass to the service constructor.
    """

    # Load the service configuration
    if service_config is None:
        from aiperf.common.config import load_service_config

        service_config = load_service_config()

    # Create the service instance and run it
    service = service_class(service_config=service_config, **kwargs)

    with contextlib.suppress(asyncio.CancelledError):
        if service_config.enable_uvloop:
            import uvloop

            uvloop.run(service.run_forever())
        else:
            asyncio.run(service.run_forever())
