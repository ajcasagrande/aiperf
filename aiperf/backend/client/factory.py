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

import logging
from collections.abc import Callable

from pyparsing import Any

from aiperf.backend.client.error import BackendClientError
from aiperf.backend.client.interface import BackendClientInterface
from aiperf.backend.client.model import BackendClientConfig
from aiperf.core.enum import BackendClientType

logger = logging.getLogger(__name__)


class BackendClientFactory:
    """Factory for creating backend client instances. Provides a registry of backend client types and
    methods for registering new backend client type and creating backend client instances from existing
    registered types.
    """

    # Registry of backend client types
    _backend_client_registry: dict[
        BackendClientType | str, type[BackendClientInterface]
    ] = {}

    @classmethod
    def register_backend_client_type(
        cls,
        backend_client_type: BackendClientType | str,
        backend_client_class: type[BackendClientInterface],
    ) -> None:
        """Register a new backend client type.

        Args:
            backend_client_type: String representation of the backend client type
            backend_client_class: The class that implements the backend client type
        """
        cls._backend_client_registry[backend_client_type] = backend_client_class
        logger.debug("Registered backend client type: %s", backend_client_type)

    @classmethod
    def register(cls, backend_client_type: BackendClientType | str) -> Callable:
        """Register a new backend client type.

        Args:
            backend_client_type: String representation of the backend client type

        Returns:
            Decorator for the communication class

        Raises:
            BackendClientTypeAlreadyRegisteredError: If the backend client type is already registered
        """

        def decorator(
            backend_client_cls: type[BackendClientInterface],
        ) -> type[BackendClientInterface]:
            if backend_client_type in cls._backend_client_registry:
                raise BackendClientError(
                    f"Backend client type {backend_client_type} already registered"
                )
            cls._backend_client_registry[backend_client_type] = backend_client_cls
            return backend_client_cls

        return decorator

    @classmethod
    def create_backend_client(
        cls,
        client_config: BackendClientConfig[Any],
    ) -> BackendClientInterface:
        """Create a backend client instance.

        Args:
            client_config: Configuration for the backend client

        Returns:
            BackendClientInterface instance

        Raises:
            BackendClientTypeUnknownError: If the backend client type is not registered
            BackendClientCreationError: If there was an error creating the backend client instance
        """
        if client_config.backend_client_type not in cls._backend_client_registry:
            logger.error(
                "Unknown backend client type: %s", client_config.backend_client_type
            )
            raise BackendClientTypeUnknownError(
                f"Unknown backend client type: {client_config.backend_client_type}"
            )

        try:
            backend_client_class = cls._backend_client_registry[
                client_config.backend_client_type
            ]
            return backend_client_class(client_config=client_config)

        except Exception as e:
            logger.error(
                "Exception creating backend client for type %s: %s",
                client_config.backend_client_type,
                e,
            )
            raise BackendClientCreationError from e
