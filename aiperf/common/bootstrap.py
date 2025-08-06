# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import contextlib
import multiprocessing
import random
import signal
import sys

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.logging import AIPerfLogger
from aiperf.common.protocols import ServiceProtocol


def bootstrap_and_run_service(
    service_class: type[ServiceProtocol],
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

    # Load the service configuration
    if service_config is None:
        from aiperf.common.config import load_service_config

        service_config = load_service_config()

    # Load the user configuration
    if user_config is None:
        from aiperf.common.config import load_user_config

        # TODO: Add support for loading user config from a file/environment variables
        user_config = load_user_config()

    async def _run_service():
        profiling_started = False
        service = None
        shutdown_requested = False

        def signal_handler(signum, frame):
            """Handle termination signals to ensure profile export."""
            nonlocal shutdown_requested
            if not shutdown_requested:
                shutdown_requested = True
                _logger.info(
                    f"Received signal {signum}, initiating graceful shutdown for profile export..."
                )

                # Export profile before terminating
                if profiling_started and service_config.enable_yappi:
                    # Give the service a chance to stop gracefully
                    # if service:
                    #     asyncio.create_task(service.stop())

                    service_id_for_profiling = (
                        service.service_id
                        if service
                        else service_id or "unknown_service"
                    )
                    try:
                        _stop_realtime_profiling(service_id_for_profiling, user_config)
                        _logger.info(
                            f"Profile export completed for {service_id_for_profiling}"
                        )
                    except Exception as e:
                        _logger.error(
                            f"Failed to export profile during signal handling: {e}"
                        )

                # Exit gracefully
                sys.exit(0)

        # Set up signal handlers for graceful shutdown with profile export
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        try:
            if service_config.enable_yappi:
                _start_realtime_profiling()
                profiling_started = True

            service = service_class(
                service_config=service_config,
                user_config=user_config,
                service_id=service_id,
                **kwargs,
            )

            from aiperf.common.logging import setup_child_process_logging

            setup_child_process_logging(
                log_queue, service.service_id, service_config, user_config
            )

            if user_config.input.random_seed is not None:
                random.seed(user_config.input.random_seed)
                # Try and set the numpy random seed
                # https://numpy.org/doc/stable/reference/random/index.html#random-quick-start
                with contextlib.suppress(ImportError):
                    import numpy as np

                    np.random.seed(user_config.input.random_seed)

            try:
                await service.initialize()
                await service.start()
                await service.stopped_event.wait()
            except Exception as e:
                if (
                    not shutdown_requested
                ):  # Don't log error if we're shutting down due to signal
                    service.exception(f"Unhandled exception in service: {e}")
                raise  # Re-raise to ensure profiling cleanup happens

        except SystemExit:
            # Normal shutdown via signal handler
            pass
        finally:
            # Always try to stop profiling, even if service failed (but avoid double export)
            if (
                profiling_started
                and service_config.enable_yappi
                and not shutdown_requested
            ):
                service_id_for_profiling = (
                    service.service_id if service else service_id or "unknown_service"
                )
                _stop_realtime_profiling(service_id_for_profiling, user_config)

    with contextlib.suppress(asyncio.CancelledError):
        if service_config.enable_uvloop:
            import uvloop

            uvloop.run(_run_service())
        else:
            asyncio.run(_run_service())


# Global profiler instance for real-time data capture
_realtime_profiler = None
_logger = AIPerfLogger(__name__)


def _start_realtime_profiling() -> None:
    """Start real-time profiling with accurate data capture."""
    global _realtime_profiler

    try:
        from aiperf.common.speedscope_exporter import (
            FilterLevel,
            SamplingStrategy,
            SpeedscopeProfiler,
        )

        # Create profiler with production-ready settings
        _realtime_profiler = SpeedscopeProfiler(
            max_events=500_000,  # 500K events max (smaller for production)
            memory_limit_mb=150,  # 150MB memory limit (more conservative)
            sampling_strategy=SamplingStrategy.ADAPTIVE,  # Enable adaptive sampling
            filter_level=FilterLevel.AGGRESSIVE,  # Filter builtins to reduce noise
        )
        _realtime_profiler.start()
        _logger.info("Started real-time profiling with SpeedscopeProfiler")

    except Exception as e:
        from aiperf.common.exceptions import AIPerfError

        raise AIPerfError(f"Failed to start real-time profiler: {e}") from e


def _stop_realtime_profiling(service_id_: str, user_config: UserConfig) -> None:
    """Stop real-time profiling and save accurate execution data."""
    global _realtime_profiler

    if _realtime_profiler is None:
        _logger.warning(f"No active real-time profiler found for service {service_id_}")
        return

    try:
        # Create output directory
        realtime_dir = user_config.output.artifact_directory / "realtime"
        realtime_dir.mkdir(parents=True, exist_ok=True)
        _logger.debug(f"Created realtime directory: {realtime_dir}")

        # Export real-time data to speedscope with service name
        speedscope_path = realtime_dir / f"{service_id_}.speedscope.json"

        # Get memory stats before stopping
        stats = _realtime_profiler.get_memory_stats()
        _logger.info(
            f"Profiler stats for {service_id_}: {stats['events_captured']:,} events captured, "
            f"{stats['buffer_usage_pct']:.1f}% buffer usage"
        )

        # Stop profiling and export with real execution data
        _realtime_profiler.export(speedscope_path, f"AIPerf {service_id_}")

        # Verify file was created
        if speedscope_path.exists():
            file_size = speedscope_path.stat().st_size
            _logger.info(
                f"✓ Saved profile for {service_id_} to {speedscope_path} ({file_size:,} bytes)"
            )
            _logger.info(
                f"Open {speedscope_path} in https://speedscope.app for interactive visualization"
            )
        else:
            _logger.error(f"Profile file not created: {speedscope_path}")

    except Exception as e:
        _logger.exception(f"Error stopping real-time profiler for {service_id_}: {e}")
        # Try to get debug info even if export failed
        try:
            if _realtime_profiler:
                stats = _realtime_profiler.get_memory_stats()
                _logger.error(f"Debug info for failed export: {stats}")
        except Exception:
            pass

    finally:
        _realtime_profiler = None
