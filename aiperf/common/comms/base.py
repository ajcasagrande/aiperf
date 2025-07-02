# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
from abc import ABC, abstractmethod

from aiperf.common.comms.clients.base import (
    PubClient,
    PullClient,
    PushClient,
    RepClient,
    ReqClient,
    SubClient,
)
from aiperf.common.enums import ClientAddressType

logger = logging.getLogger(__name__)

################################################################################
# Base Communication Class
################################################################################


class BaseCommunication(ABC):
    """Base class for specifying the base communication layer for AIPerf components."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize communication channels."""
        pass

    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """Check if communication channels are initialized.

        Returns:
            True if communication channels are initialized, False otherwise
        """
        pass

    @property
    @abstractmethod
    def is_shutdown(self) -> bool:
        """Check if communication channels are shutdown.

        Returns:
            True if communication channels are shutdown, False otherwise
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully shutdown communication channels."""
        pass

    @abstractmethod
    def create_pub_client(
        self,
        address_type: ClientAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> PubClient:
        """Create a publish client.

        Args:
            address_type: The type of address to use when looking up in the communication config.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        pass

    @abstractmethod
    def create_sub_client(
        self,
        address_type: ClientAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> SubClient:
        """Create a subscribe client.

        Args:
            address_type: The type of address to use when looking up in the communication config.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        pass

    @abstractmethod
    def create_push_client(
        self,
        address_type: ClientAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> PushClient:
        """Create a push client.

        Args:
            address_type: The type of address to use when looking up in the communication config.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        pass

    @abstractmethod
    def create_pull_client(
        self,
        address_type: ClientAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> PullClient:
        """Create a pull client.

        Args:
            address_type: The type of address to use when looking up in the communication config.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        pass

    @abstractmethod
    def create_req_client(
        self,
        address_type: ClientAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> ReqClient:
        """Create a request client.

        Args:
            address_type: The type of address to use when looking up in the communication config.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        pass

    @abstractmethod
    def create_rep_client(
        self,
        address_type: ClientAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> RepClient:
        """Create a reply client.

        Args:
            address_type: The type of address to use when looking up in the communication config.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        pass
