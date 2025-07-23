# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod

from aiperf.common.enums import ServiceType
from aiperf.common.enums.service_enums import LifecycleState


class BaseServiceInterface(ABC):
    """Base interface for all services.

    This class provides the base foundation for which every service should provide. Some
    methods are required to be implemented by derived classes, while others are
    meant to be implemented by the base class.
    """

    @property
    @abstractmethod
    def service_type(self) -> ServiceType:
        """The type/name of the service.

        This property should be implemented by derived classes to specify the
        type/name of the service."""
        # TODO: We can do this better by using a decorator to set the service type
        pass

    @property
    @abstractmethod
    def state(self) -> LifecycleState:
        """The state of the service."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the service.

        This method will be implemented by the base class.
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """Start the service. It should be called after the service has been initialized
        and configured.

        This method will be implemented by the base class, and extra
        functionality can be added by derived classes via the `@on_start`
        decorator.
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the service.

        This method will be implemented by the base class, and extra
        functionality can be added by derived classes via the `@on_stop`
        decorator.
        """
        pass
