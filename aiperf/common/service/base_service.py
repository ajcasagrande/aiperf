# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import uuid
from abc import ABC
from collections.abc import Callable
from typing import Any, ClassVar

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import ServiceState
from aiperf.common.enums.service_enums import ServiceType
from aiperf.common.exceptions import (
    AIPerfError,
    InvalidOperationError,
    ServiceError,
)
from aiperf.common.factories import FactoryMixin
from aiperf.common.hooks import (
    AIPerfHook,
    AIPerfTaskHook,
    supports_hooks,
)
from aiperf.common.messages import Message
from aiperf.common.mixins import (
    AIPerfCommandMessageHandlerMixin,
    AIPerfLoggerMixin,
    AIPerfMessagePubSubMixin,
    CommunicationsMixin,
    EventBusClientMixin,
    ProcessHealthMixin,
)
from aiperf.common.service.base_service_interface import BaseServiceInterface


@supports_hooks(
    AIPerfHook.ON_INIT,
    AIPerfHook.ON_RUN,
    AIPerfHook.ON_CONFIGURE,
    AIPerfHook.ON_START,
    AIPerfHook.ON_STOP,
    AIPerfHook.ON_CLEANUP,
    AIPerfHook.ON_SET_STATE,
    AIPerfTaskHook.AIPERF_TASK,
)
class BaseService(
    BaseServiceInterface,
    CommunicationsMixin,
    EventBusClientMixin,
    AIPerfMessagePubSubMixin,
    AIPerfCommandMessageHandlerMixin,
    ProcessHealthMixin,
    AIPerfLoggerMixin,
    ABC,
):
    """Base class for all AIPerf services, providing common functionality for
    communication, state management, and lifecycle operations.

    This class provides the foundation for implementing the various services of the
    AIPerf system. Some of the abstract methods are implemented here, while others
    are still required to be implemented by derived classes.
    """

    # This gets set by the ServiceFactory.register decorator
    service_type: ClassVar[ServiceType]

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
        **kwargs,
    ) -> None:
        self.service_id: str = (
            service_id or f"{self.service_type}_{uuid.uuid4().hex[:8]}"
        )
        self.service_config = service_config
        self.user_config = user_config

        self._state: ServiceState = ServiceState.UNKNOWN

        super().__init__(
            service_id=service_id,
            service_config=service_config,
            user_config=user_config,
            logger_name=self.service_id,
            **kwargs,
        )

        self.debug(
            lambda: f"__init__ {self.service_type} service (id: {self.service_id})"
        )

        self.stop_event = asyncio.Event()
        self.initialized_event = asyncio.Event()

        try:
            import setproctitle

            setproctitle.setproctitle(f"aiperf {self.service_id}")
        except Exception:
            # setproctitle is not available on all platforms, so we ignore the error
            self.debug("Failed to set process title, ignoring")

        self.debug(
            lambda: f"BaseService._init__ finished for {self.__class__.__name__}"
        )

    @property
    def state(self) -> ServiceState:
        """The current state of the service."""
        return self._state

    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized.

        Returns:
            True if service is initialized, False otherwise
        """
        return self.initialized_event.is_set()

    def _service_error(self, message: str) -> ServiceError:
        return ServiceError(
            message=message,
            service_type=self.service_type,
            service_id=self.service_id,
        )

    # Note: Not using as a setter so it can be overridden by derived classes and still
    # be async
    async def set_state(self, state: ServiceState) -> None:
        """Set the state of the service. This method implements
        the `BaseServiceInterface.set_state` method.

        This method will:
        - Set the service state to the given state
        - Call all registered `AIPerfHook.ON_SET_STATE` hooks
        """
        self._state = state
        await self.run_hooks(AIPerfHook.ON_SET_STATE, state)

    async def initialize(self) -> None:
        """Initialize the service communication and signal handlers. This method implements
        the `BaseServiceInterface.initialize` method.

        This method will:
        - Set the service to `ServiceState.INITIALIZING` state
        - Initialize communication
        - Call all registered `AIPerfHook.ON_INIT` hooks
        - Set the service to `ServiceState.READY` state
        - Set the initialized asyncio event
        """
        self._state = ServiceState.INITIALIZING

        await self.comms.initialize()

        # Initialize any derived service components
        await self.run_hooks(AIPerfHook.ON_INIT)
        await self.set_state(ServiceState.READY)

        self.initialized_event.set()

    async def run_forever(self) -> None:
        """Run the service in a loop until the stop event is set. This method implements
        the `BaseServiceInterface.run_forever` method.

        This method will:
        - Call the initialize method to initialize the service
        - Call all registered `AIPerfHook.RUN` hooks
        - Wait for the stop event to be set
        - Shuts down the service when the stop event is set

        This method will be called as the main entry point for the service.
        """
        try:
            self.debug(
                lambda: f"Running {self.service_type} service (id: {self.service_id})"
            )

            await self.initialize()
            await self.run_hooks(AIPerfHook.ON_RUN)

        except asyncio.CancelledError:
            self.debug(lambda: f"Service {self.service_type} execution cancelled")
            return

        except AIPerfError:
            raise  # re-raise it up the stack

        except Exception as e:
            self.exception(f"Service {self.service_type} execution failed: {e}")
            _ = await self.set_state(ServiceState.ERROR)
            raise AIPerfError("Service execution failed") from e

        await self._forever_loop()

    async def _forever_loop(self) -> None:
        """
        This method will be called by the `run_forever` method to allow the service to run
        indefinitely. This method is not expected to be overridden by derived classes.

        This method will:
        - Wait for the stop event to be set
        - Shuts down the service when the stop event is set
        """
        while not self.stop_event.is_set():
            try:
                self.debug(
                    lambda: f"Service {self.service_type} waiting for stop event"
                )
                # Wait forever for the stop event to be set
                await self.stop_event.wait()

            except asyncio.CancelledError:
                self.debug(
                    lambda: f"Service {self.service_type} received CancelledError, exiting"
                )
                break

            except Exception as e:
                self.exception(
                    f"Caught unexpected exception {e} in service {self.service_type} execution"
                )

        # Shutdown the service
        try:
            await self.stop()
        except Exception as e:
            self.exception(
                f"Caught unexpected exception {e} in service {self.service_type} stop"
            )

    async def start(self) -> None:
        """Start the service and its components. This method implements
        the `BaseServiceInterface.start` method.

        This method should be called to start the service after it has been initialized
        and configured.

        This method will:
        - Set the service to `ServiceState.STARTING` state
        - Call all registered `AIPerfHook.ON_START` hooks
        - Set the service to `ServiceState.RUNNING` state
        """

        try:
            self.debug(
                lambda: f"Starting {self.service_type} service (id: {self.service_id})"
            )
            _ = await self.set_state(ServiceState.STARTING)

            await self.run_hooks(AIPerfHook.ON_START)

            _ = await self.set_state(ServiceState.RUNNING)

        except asyncio.CancelledError:
            self.debug(
                lambda: f"Service {self.service_id} received CancelledError, exiting"
            )
            return
        except AIPerfError:
            raise  # re-raise it up the stack
        except Exception as e:
            self._state = ServiceState.ERROR
            raise AIPerfError("Failed to start service") from e

    async def stop(self) -> None:
        """Stop the service and clean up its components. This method implements
        the `BaseServiceInterface.stop` method.

        This method will:
        - Set the service to `ServiceState.STOPPING` state
        - Call all registered `AIPerfHook.ON_STOP` hooks
        - Shutdown the service communication component
        - Call all registered `AIPerfHook.ON_CLEANUP` hooks
        - Set the service to `ServiceState.STOPPED` state
        """
        try:
            if self.state == ServiceState.STOPPED:
                self.warning(
                    f"Service {self.service_type} state {self.state} is already STOPPED, ignoring stop request"
                )
                return

            self._state = ServiceState.STOPPING

            # Signal the run method to exit if it hasn't already
            if not self.stop_event.is_set():
                self.stop_event.set()

            cancelled_error = None
            # Custom stop logic implemented by derived classes
            try:
                await self.run_hooks(AIPerfHook.ON_STOP)
            except asyncio.CancelledError as e:
                cancelled_error = e

            # Shutdown communication component
            if self.comms and not self.comms.stop_requested:
                try:
                    await self.comms.shutdown()
                except asyncio.CancelledError as e:
                    cancelled_error = e

            # Custom cleanup logic implemented by derived classes
            try:
                await self.run_hooks(AIPerfHook.ON_CLEANUP)
            except asyncio.CancelledError as e:
                cancelled_error = e

            # Set the state to STOPPED. Communications are shutdown, so we don't need to
            # publish a status message
            self._state = ServiceState.STOPPED

            self.debug(
                lambda: f"Service {self.service_type} (id: {self.service_id}) stopped"
            )

            # Re-raise the cancelled error if it was raised during the stop hooks
            if cancelled_error:
                raise cancelled_error

        except AIPerfError:
            raise  # re-raise it up the stack
        except Exception as e:
            self._state = ServiceState.ERROR
            raise AIPerfError("Failed to stop service") from e

    async def configure(self, message: Message) -> None:
        """Configure the service with the given configuration. This method implements
        the `BaseServiceInterface.configure` method.

        This method will:
        - Call all registered AIPerfHook.ON_CONFIGURE hooks
        """
        await self.run_hooks(AIPerfHook.ON_CONFIGURE, message)


class ServiceFactory(FactoryMixin[ServiceType, BaseService]):
    """Factory for registering and creating BaseService instances based on the specified service type.
    see: :class:`FactoryMixin` for more details.
    """

    @classmethod
    def register_all(
        cls, *class_types: ServiceType | str, override_priority: int = 0
    ) -> Callable[..., Any]:
        raise InvalidOperationError(
            "ServiceFactory.register_all is not supported. A single service can only be registered with a single type."
        )

    @classmethod
    def register(
        cls, class_type: ServiceType | str, override_priority: int = 0
    ) -> Callable[..., Any]:
        # Override the register method to set the service_type on the class
        original_decorator = super().register(class_type, override_priority)

        def decorator(class_cls: type[BaseService]) -> type[BaseService]:
            class_cls.service_type = class_type
            original_decorator(class_cls)
            return class_cls

        return decorator
