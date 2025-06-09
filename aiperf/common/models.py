# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from aiperf.common.enums import (
    ServiceRegistrationStatus,
    ServiceState,
    ServiceType,
)

################################################################################
# ZMQ Configuration Protocols
################################################################################


class BaseZMQDealerRouterBrokerConfig(BaseModel, ABC):
    """Configuration Protocol for ZMQ Dealer Router Broker."""

    @property
    @abstractmethod
    def router_address(self) -> str: ...

    @property
    @abstractmethod
    def dealer_address(self) -> str: ...

    @property
    @abstractmethod
    def control_address(self) -> str | None: ...

    @property
    @abstractmethod
    def capture_address(self) -> str | None: ...


class BaseZMQTransportConfig(BaseModel, ABC):
    """Configuration Protocol for ZMQ transport."""

    @property
    @abstractmethod
    def controller_pub_sub_address(self) -> str: ...

    @property
    @abstractmethod
    def component_pub_sub_address(self) -> str:
        """Get the component pub/sub address based on protocol configuration."""
        ...

    @property
    @abstractmethod
    def inference_push_pull_address(self) -> str:
        """Get the inference push/pull address based on protocol configuration."""
        ...

    @property
    @abstractmethod
    def records_address(self) -> str:
        """Get the records address based on protocol configuration."""
        ...

    @property
    @abstractmethod
    def conversation_data_address(self) -> str:
        """Get the conversation data address based on protocol configuration."""
        ...

    @property
    @abstractmethod
    def credit_drop_address(self) -> str:
        """Get the credit drop address based on protocol configuration."""
        ...

    @property
    @abstractmethod
    def credit_return_address(self) -> str:
        """Get the credit return address based on protocol configuration."""
        ...


################################################################################
# ZMQ Configuration Models
################################################################################


class ZMQTCPDealerRouterBrokerConfig(BaseZMQDealerRouterBrokerConfig):
    """Configuration for ZMQ Dealer Router Broker."""

    host: str = Field(
        default="0.0.0.0",
        description="Host address for TCP connections",
    )
    router_port: int = Field(
        default=5555, description="The port of the router (ROUTER)"
    )
    dealer_port: int = Field(
        default=5556, description="The port of the dealer (DEALER)"
    )

    control_port: int | None = Field(
        default=None, description="The port of the control (REP)"
    )
    capture_port: int | None = Field(
        default=None, description="The port of the capture (PUB)"
    )

    @property
    def router_address(self) -> str:
        """Get the router address for the given host."""
        return f"tcp://{self.host}:{self.router_port}"

    @property
    def dealer_address(self) -> str:
        """Get the dealer address for the given host."""
        return f"tcp://{self.host}:{self.dealer_port}"

    @property
    def control_address(self) -> str | None:
        """Get the control address for the given host."""
        return f"tcp://{self.host}:{self.control_port}"

    @property
    def capture_address(self) -> str | None:
        """Get the capture address for the given host."""
        return f"tcp://{self.host}:{self.capture_port}"


class ZMQTCPTransportConfig(BaseZMQTransportConfig):
    """Configuration for TCP transport."""

    host: str = Field(
        default="0.0.0.0",
        description="Host address for TCP connections",
    )
    controller_pub_sub_port: int = Field(
        default=5555, description="Port for controller pub/sub messages"
    )
    component_pub_sub_port: int = Field(
        default=5556, description="Port for component pub/sub messages"
    )
    inference_push_pull_port: int = Field(
        default=5557, description="Port for inference push/pull messages"
    )
    req_rep_port: int = Field(
        default=5558, description="Port for sending and receiving requests"
    )
    push_pull_port: int = Field(
        default=5559, description="Port for pushing and pulling data"
    )
    records_port: int = Field(default=5560, description="Port for record data")
    conversation_data_port: int = Field(
        default=5561, description="Port for conversation data"
    )
    credit_drop_port: int = Field(
        default=5562, description="Port for credit drop operations"
    )
    credit_return_port: int = Field(
        default=5563, description="Port for credit return operations"
    )
    dataset_broker_config: BaseZMQDealerRouterBrokerConfig | None = Field(
        default=None,
        description="Configuration for the ZMQ Dataset Broker. If provided, the broker will be created and started.",
    )
    credit_broker_config: BaseZMQDealerRouterBrokerConfig | None = Field(
        default=None,
        description="Configuration for the ZMQ Credit Broker. If provided, the broker will be created and started.",
    )

    @property
    def controller_pub_sub_address(self) -> str:
        return f"tcp://{self.host}:{self.controller_pub_sub_port}"

    @property
    def component_pub_sub_address(self) -> str:
        """Get the component pub/sub address based on protocol configuration."""
        return f"tcp://{self.host}:{self.component_pub_sub_port}"

    @property
    def inference_push_pull_address(self) -> str:
        """Get the inference push/pull address based on protocol configuration."""
        return f"tcp://{self.host}:{self.inference_push_pull_port}"

    @property
    def records_address(self) -> str:
        """Get the records address based on protocol configuration."""
        return f"tcp://{self.host}:{self.records_port}"

    @property
    def conversation_data_address(self) -> str:
        """Get the conversation data address based on protocol configuration."""
        return f"tcp://{self.host}:{self.conversation_data_port}"

    @property
    def credit_drop_address(self) -> str:
        """Get the credit drop address based on protocol configuration."""
        return f"tcp://{self.host}:{self.credit_drop_port}"

    @property
    def credit_return_address(self) -> str:
        """Get the credit return address based on protocol configuration."""
        return f"tcp://{self.host}:{self.credit_return_port}"


################################################################################
# Service Models
################################################################################


class ServiceRunInfo(BaseModel):
    """Base model for tracking service run information."""

    service_type: ServiceType = Field(
        ...,
        description="The type of service",
    )
    registration_status: ServiceRegistrationStatus = Field(
        ...,
        description="The registration status of the service",
    )
    service_id: str = Field(
        ...,
        description="The ID of the service",
    )
    first_seen: int | None = Field(
        default_factory=time.perf_counter_ns,
        description="The first time the service was seen",
    )
    last_seen: int | None = Field(
        default_factory=time.perf_counter_ns,
        description="The last time the service was seen",
    )
    state: ServiceState = Field(
        default=ServiceState.UNKNOWN,
        description="The current state of the service",
    )
