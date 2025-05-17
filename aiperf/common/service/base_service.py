#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import asyncio
import contextlib
import logging
import signal
import uuid
from abc import ABC

import setproctitle

from aiperf.common.comms.base_communication import BaseCommunication
from aiperf.common.comms.communication_factory import CommunicationFactory
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceState
from aiperf.common.exceptions.comm_exceptions import (
    CommunicationClientCreationException,
    CommunicationCreateException,
)
from aiperf.common.exceptions.service_exceptions import (
    ServiceInitializationException,
    ServiceRunException,
    ServiceStartException,
    ServiceStopException,
)
from aiperf.common.models.message_models import BaseMessage
from aiperf.common.models.payload_models import PayloadType
from aiperf.common.service.abstract_base_service import AbstractBaseService


class BaseService(AbstractBaseService, ABC):
    """Base class for all AIPerf services, providing common functionality for
    communication, state management, and lifecycle operations.

    This class provides the foundation for implementing the various services of the
    AIPerf system. Some of the abstract methods are implemented here, while others
    are still required to be implemented by derived classes.
    """

    def __init__(self, service_config: ServiceConfig, service_id: str = None):
        self.service_id: str = (
            service_id or f"{self.service_type}_{uuid.uuid4().hex[:8]}"
        )
        self.service_config = service_config

        self.logger = logging.getLogger(self.service_type)
        self.logger.debug(
            f"Initializing {self.service_type} service (id: {self.service_id})"
        )

        self._state: ServiceState = ServiceState.UNKNOWN

        self._heartbeat_task = None
        self._heartbeat_interval = self.service_config.heartbeat_interval

        self.stop_event = asyncio.Event()
        self.comms: BaseCommunication | None = None

        # Set to store signal handler tasks
        self._signal_tasks = set()

        # noinspection PyBroadException
        try:
            setproctitle.setproctitle(f"aiperf {self.service_id}")
        except:  # noqa: E722
            # setproctitle is not available on all platforms, so we ignore the error
            self.logger.debug("Failed to set process title, ignoring")

    @property
    def state(self) -> ServiceState:
        """The current state of the service."""
        return self._state

    # Note: Not using as a setter so it can be overridden by derived classes and still
    # be async
    async def set_state(self, state: ServiceState) -> None:
        """Set the state of the service."""
        self._state = state

    async def initialize(self) -> None:
        """Initialize the service communication and signal handlers."""
        # Set up signal handlers for graceful shutdown
        self.setup_signal_handlers()

        # Allow time for the event loop to start
        await asyncio.sleep(0.1)

        self._state = ServiceState.INITIALIZING

        # Initialize communication
        try:
            self.comms = CommunicationFactory.create_communication(self.service_config)
        except Exception as e:
            self.logger.exception(
                "Failed to create communication for service %s (id: %s)",
                self.service_type,
                self.service_id,
            )
            raise CommunicationCreateException from e

        try:
            await self.comms.initialize()
        except Exception as e:
            self.logger.exception(
                "Failed to initialize communication for service %s (id: %s)",
                self.service_type,
                self.service_id,
            )
            raise ServiceInitializationException from e

        if len(self.required_clients) > 0:
            # Create the communication clients ahead of time
            self.logger.debug(
                "%s: Creating communication clients (%s)",
                self.service_type,
                self.required_clients,
            )

            try:
                await self.comms.create_clients(*self.required_clients)
            except Exception as e:
                self.logger.exception(
                    "Failed to create communication clients for service %s (id: %s)",
                    self.service_type,
                    self.service_id,
                )
                raise CommunicationClientCreationException from e

        # Initialize any derived service components
        try:
            await self._initialize()
        except Exception as e:
            self.logger.exception(
                "Failed to initialize service %s (id: %s)",
                self.service_type,
                self.service_id,
            )
            raise ServiceInitializationException from e

    async def _run(self) -> None:
        """Run the service."""
        try:
            await self.initialize()
            await self.set_state(ServiceState.READY)
            await self.start()
            await self.set_state(ServiceState.RUNNING)
        except Exception as e:
            self.logger.exception(
                "Failed to initialize service %s (id: %s)",
                self.service_type,
                self.service_id,
            )
            raise ServiceRunException from e

    async def run(self) -> None:
        """Run the service.

        This method will be called as the main entry point for the service. It will
        not return until the service is completely shutdown.
        """
        try:
            await self._run()

        except asyncio.CancelledError:
            self.logger.debug("Service %s execution cancelled", self.service_type)
            return

        except BaseException as e:  # noqa: E722
            self.logger.exception("Service %s execution failed:", self.service_type)
            _ = await self.set_state(ServiceState.ERROR)
            raise ServiceRunException(
                "Service %s execution failed", self.service_type
            ) from e

        # Run the service forever until the stop event is set
        return await self._forever_loop()

    async def _forever_loop(self) -> None:
        """Run the service in a loop until the stop event is set.

        This method will be called by the `run` method to allow the service to run
        indefinitely.
        """
        while not self.stop_event.is_set():
            try:
                # Wait forever for the stop event to be set
                await self.stop_event.wait()

            except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
                self.logger.debug("Service %s execution cancelled", self.service_type)
                self.stop_event.set()

            except Exception:
                self.logger.exception(
                    "Caught unexpected exception in service %s execution",
                    self.service_type,
                )
            finally:
                # Shutdown the service
                try:
                    await self.stop()
                except Exception as e:
                    self.logger.exception(
                        "Exception stopping service %s", self.service_type
                    )
                    raise ServiceStopException(
                        "Exception stopping service %s", self.service_type
                    ) from e

    async def start(self) -> None:
        """Start the service and its components.

        This method should be called to start the service after it has been initialized
        and configured.
        """

        try:
            self.logger.debug(
                "Starting %s service (id: %s)", self.service_type, self.service_id
            )
            _ = await self.set_state(ServiceState.STARTING)

            await self._on_start()

            _ = await self.set_state(ServiceState.RUNNING)

        except asyncio.CancelledError:
            self.logger.debug("Service %s execution cancelled", self.service_type)

        except BaseException as e:  # noqa: E722
            self.logger.exception(
                "Failed to start service %s (id: %s)",
                self.service_type,
                self.service_id,
            )
            self._state = ServiceState.ERROR

            raise ServiceStartException(
                "Failed to start service %s (id: %s)",
                self.service_type,
                self.service_id,
            ) from e

    async def stop(self) -> None:
        """Stop the service and clean up its components."""
        try:
            if self.state == ServiceState.STOPPED:
                self.logger.debug(
                    "Service %s state %s is already STOPPED, ignoring stop request",
                    self.service_type,
                    self.state,
                )
                return

            # ignore if we were unable to send the STOPPING state message
            _ = await self.set_state(ServiceState.STOPPING)

            # Signal the run method to exit if it hasn't already
            if not self.stop_event.is_set():
                self.stop_event.set()

            # Custom stop logic implemented by derived classes
            with contextlib.suppress(asyncio.CancelledError):
                await self._on_stop()

            # Shutdown communication component
            if self.comms and not self.comms.is_shutdown:
                await self.comms.shutdown()

            # Custom cleanup logic implemented by derived classes
            await self._cleanup()

            # Set the state to STOPPED. Communications are shutdown, so we don't need to
            # publish a status message
            self._state = ServiceState.STOPPED
            self.logger.debug(
                "Service %s (id: %s) stopped", self.service_type, self.service_id
            )

        except BaseException as e:  # noqa: E722
            self.logger.exception(
                "Failed to stop service %s (id: %s)",
                self.service_type,
                self.service_id,
            )
            self._state = ServiceState.ERROR
            raise ServiceStopException(
                "Failed to stop service %s (id: %s)",
                self.service_type,
                self.service_id,
            ) from e

    def create_message(
        self, payload: PayloadType, request_id: str | None = None
    ) -> BaseMessage:
        """Create a message of the given type, and pre-fill the service_id.

        Args:
            payload: The payload of the message
            Optional[request_id]: The request id of the message this is a response to

        Returns:
            A message of the given type
        """
        message = BaseMessage(
            service_id=self.service_id,
            request_id=request_id,
            payload=payload,
        )
        return message

    def setup_signal_handlers(self) -> None:
        """This method will set up signal handlers for the SIGTERM and SIGINT signals
        in order to trigger a graceful shutdown of the service.
        """
        loop = asyncio.get_running_loop()

        def signal_handler(sig: int) -> None:
            # Create a task and store it so it doesn't get garbage collected
            task = asyncio.create_task(self.handle_signal(sig))
            # Store the task somewhere to prevent it from being garbage collected
            # before it completes
            self._signal_tasks.add(task)
            task.add_done_callback(self._signal_tasks.discard)

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s))

    async def handle_signal(self, sig: int) -> None:
        """Handle received signals by triggering graceful shutdown.

        Args:
            sig: The signal number received
        """
        signal_name = signal.Signals(sig).name
        self.logger.debug(
            "%s: Received signal %s, initiating graceful shutdown",
            self.service_type,
            signal_name,
        )

        self.stop_event.set()
