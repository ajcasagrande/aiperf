import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType, ServiceRegistrationStatus, ServiceState
from aiperf.common.service.base import get_logger


class ServiceRunInfo(BaseModel):
    """Base model for tracking service run information."""

    service_type: ServiceType
    registration_status: ServiceRegistrationStatus = Field(
        default=ServiceRegistrationStatus.UNREGISTERED
    )
    service_id: str = Field(default="")
    first_seen: Optional[datetime] = Field(default=None)
    last_seen: Optional[datetime] = Field(default=None)
    state: ServiceState = Field(default=ServiceState.UNKNOWN)


class ServiceManagerBase(ABC):
    """
    Base class for service managers.
    """

    def __init__(
        self, required_service_types: List[ServiceType], config: ServiceConfig
    ):
        self.logger = get_logger(self.__class__.__name__)
        self.required_service_types = required_service_types
        self.config = config
        # Maps to track service information
        self.service_map: Dict[ServiceType, List[ServiceRunInfo]] = {}

        # Create service ID map for component lookups
        self.service_id_map: Dict[str, ServiceRunInfo] = {}

    def get(self, service_id: str) -> Optional[ServiceRunInfo]:
        """
        Get the service run information by service ID.
        """
        return self.service_id_map.get(service_id)

    @abstractmethod
    async def initialize_all_services(self) -> None:
        pass

    @abstractmethod
    async def stop_all_services(self) -> None:
        pass

    @abstractmethod
    async def wait_for_all_services_registration(
        self, stop_event: asyncio.Event, timeout_seconds: int = 30
    ) -> bool:
        pass

    @abstractmethod
    async def wait_for_all_services_start(self) -> bool:
        pass

    @abstractmethod
    async def wait_for_all_services_stop(self) -> bool:
        pass
