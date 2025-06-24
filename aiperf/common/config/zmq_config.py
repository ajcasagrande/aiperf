# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, Field


class BaseZMQProxyConfig(BaseModel, ABC):
    """Configuration Protocol for ZMQ Proxy."""

    @property
    @abstractmethod
    def frontend_address(self) -> str: ...

    @property
    @abstractmethod
    def backend_address(self) -> str: ...

    @property
    @abstractmethod
    def control_address(self) -> str | None: ...

    @property
    @abstractmethod
    def capture_address(self) -> str | None: ...


class BaseZMQCommunicationConfig(BaseModel, ABC):
    """Configuration for ZMQ communication."""

    xpub_xsub_proxy_config: ClassVar[BaseZMQProxyConfig]
    dealer_router_broker_config: ClassVar[BaseZMQProxyConfig]

    @property
    @abstractmethod
    def controller_pub_sub_address(self) -> str:
        """Get the controller pub/sub address based on protocol configuration."""
        ...

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

    @property
    @abstractmethod
    def worker_manager_pub_sub_address(self) -> str:
        """Get the worker manager pub/sub address based on protocol configuration."""
        ...


class ZMQTCPProxyConfig(BaseZMQProxyConfig):
    """Configuration for TCP proxy."""

    host: str = Field(
        default="0.0.0.0",
        description="Host address for TCP connections",
    )
    frontend_port: int = Field(
        default=15555, description="Port for frontend address for proxy"
    )
    backend_port: int = Field(
        default=15556, description="Port for backend address for proxy"
    )
    control_port: int | None = Field(
        default=None, description="Port for control address for proxy"
    )
    capture_port: int | None = Field(
        default=None, description="Port for capture address for proxy"
    )

    @property
    def frontend_address(self) -> str:
        """Get the frontend address based on protocol configuration."""
        return f"tcp://{self.host}:{self.frontend_port}"

    @property
    def backend_address(self) -> str:
        """Get the backend address based on protocol configuration."""
        return f"tcp://{self.host}:{self.backend_port}"

    @property
    def control_address(self) -> str | None:
        """Get the control address based on protocol configuration."""
        return f"tcp://{self.host}:{self.control_port}" if self.control_port else None

    @property
    def capture_address(self) -> str | None:
        """Get the capture address based on protocol configuration."""
        return f"tcp://{self.host}:{self.capture_port}" if self.capture_port else None


class ZMQIPCProxyConfig(BaseZMQProxyConfig):
    """Configuration for IPC proxy."""

    path: str = Field(default="/tmp/aiperf", description="Path for IPC sockets")
    name: str = Field(default="proxy", description="Name for IPC sockets")
    enable_control: bool = Field(default=False, description="Enable control socket")
    enable_capture: bool = Field(default=False, description="Enable capture socket")

    @property
    def frontend_address(self) -> str:
        """Get the frontend address based on protocol configuration."""
        return f"ipc://{self.path}/{self.name}_frontend.ipc"

    @property
    def backend_address(self) -> str:
        """Get the backend address based on protocol configuration."""
        return f"ipc://{self.path}/{self.name}_backend.ipc"

    @property
    def control_address(self) -> str | None:
        """Get the control address based on protocol configuration."""
        return (
            f"ipc://{self.path}/{self.name}_control.ipc"
            if self.enable_control
            else None
        )

    @property
    def capture_address(self) -> str | None:
        """Get the capture address based on protocol configuration."""
        return (
            f"ipc://{self.path}/{self.name}_capture.ipc"
            if self.enable_capture
            else None
        )


class ZMQTCPTransportConfig(BaseZMQCommunicationConfig):
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
    worker_manager_pub_sub_port: int = Field(
        default=5564, description="Port for worker manager pub/sub messages"
    )
    dealer_router_broker_config: ZMQTCPProxyConfig = Field(
        default=ZMQTCPProxyConfig(),
        description="Configuration for the ZMQ Proxy. If provided, the proxy will be created and started.",
    )
    xpub_xsub_proxy_config: ZMQTCPProxyConfig = Field(
        default=ZMQTCPProxyConfig(),
        description="Configuration for the ZMQ Proxy. If provided, the proxy will be created and started.",
    )

    @property
    def controller_pub_sub_address(self) -> str:
        """Get the controller pub/sub address based on protocol configuration."""
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

    @property
    def worker_manager_pub_sub_address(self) -> str:
        """Get the worker manager pub/sub address based on protocol configuration."""
        return f"tcp://{self.host}:{self.worker_manager_pub_sub_port}"


class ZMQIPCConfig(BaseZMQCommunicationConfig):
    """Configuration for IPC transport."""

    path: str = Field(default="/tmp/aiperf", description="Path for IPC sockets")
    dealer_router_broker_config: ZMQIPCProxyConfig = Field(
        default=ZMQIPCProxyConfig(name="dealer_router_broker"),
        description="Configuration for the ZMQ Dealer Router Broker. If provided, the broker will be created and started.",
    )
    xpub_xsub_proxy_config: ZMQIPCProxyConfig = Field(
        default=ZMQIPCProxyConfig(name="xpub_xsub_proxy"),
        description="Configuration for the ZMQ XPUB/XSUB Proxy. If provided, the proxy will be created and started.",
    )

    @property
    def controller_pub_sub_address(self) -> str:
        """Get the controller pub/sub address based on protocol configuration."""
        return f"ipc://{self.path}/controller_pub_sub.ipc"

    @property
    def component_pub_sub_address(self) -> str:
        """Get the component pub/sub address based on protocol configuration."""
        return f"ipc://{self.path}/component_pub_sub.ipc"

    @property
    def inference_push_pull_address(self) -> str:
        """Get the inference push/pull address based on protocol configuration."""
        return f"ipc://{self.path}/inference_push_pull.ipc"

    @property
    def records_address(self) -> str:
        """Get the records address based on protocol configuration."""
        return f"ipc://{self.path}/records.ipc"

    @property
    def conversation_data_address(self) -> str:
        """Get the conversation data address based on protocol configuration."""
        return f"ipc://{self.path}/conversation_data.ipc"

    @property
    def credit_drop_address(self) -> str:
        """Get the credit drop address based on protocol configuration."""
        return f"ipc://{self.path}/credit_drop.ipc"

    @property
    def credit_return_address(self) -> str:
        """Get the credit return address based on protocol configuration."""
        return f"ipc://{self.path}/credit_return.ipc"

    @property
    def worker_manager_pub_sub_address(self) -> str:
        """Get the worker manager pub/sub address based on protocol configuration."""
        return f"ipc://{self.path}/worker_manager_pub_sub.ipc"


class ZMQInprocConfig(ZMQIPCConfig):
    """Configuration for in-process transport. Note that communications between workers
    is still done over IPC sockets."""

    name: str = Field(default="aiperf", description="Name for in-process sockets")

    @property
    def controller_pub_sub_address(self) -> str:
        """Get the controller pub/sub address based on protocol configuration."""
        return f"inproc://{self.name}_controller_pub_sub"

    @property
    def component_pub_sub_address(self) -> str:
        """Get the component pub/sub address based on protocol configuration."""
        return f"inproc://{self.name}_component_pub_sub"
