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
from enum import StrEnum
from typing import Any, Generic, TypeVar

from aiperf.common.exceptions import FactoryCreationError

ClassNameT = TypeVar("ClassNameT", bound=Any, infer_variance=True)
ClassProtocolT = TypeVar("ClassProtocolT", bound=Any, infer_variance=True)

__all__ = [
    "GenericBaseFactory",
    "InputConverterFactory",
    "OutputConverterFactory",
    "CommunicationFactory",
    "BackendClientFactory",
    "ClassNameT",
    "ClassProtocolT",
]

################################################################################
# Generic Base Factory
################################################################################


class GenericBaseFactory(Generic[ClassNameT, ClassProtocolT]):
    """Defines a generic base class for all factories, which supports registering
    and creating instances of classes."""

    logger = logging.getLogger(__name__)

    _registry: dict[ClassNameT | StrEnum | str, type[ClassProtocolT]] = {}
    _override_priorities: dict[ClassNameT | StrEnum | str, int] = {}

    @classmethod
    def register(
        cls, class_type: ClassNameT | StrEnum | str, override_priority: int = 0
    ) -> Callable:
        """Register a new class type mapping to its corresponding class.

        Args:
            class_type: The type of class to register
            override_priority: The priority of the override. The higher the priority,
                the more precedence the override has when multiple classes are registered
                for the same class type. Built-in classes have a priority of 0.

        Returns:
            Decorator for the class that implements the class protocol
        """

        def decorator(class_cls: type[ClassProtocolT]) -> type[ClassProtocolT]:
            existing_priority = cls._override_priorities.get(class_type, -1)
            if class_type in cls._registry and existing_priority >= override_priority:
                # TODO: Will logging be initialized before this method is called?
                cls.logger.warning(
                    f"{class_type!r} class {cls._registry[class_type].__name__} already registered with same or higher priority "
                    f"({existing_priority}). The new registration of class {class_cls.__name__} with priority "
                    f"{override_priority} will be ignored."
                )
                return class_cls

            if class_type not in cls._registry:
                cls.logger.info(
                    f"{class_type!r} class {class_cls.__name__} registered with priority {override_priority}."
                )
            else:
                cls.logger.info(
                    f"{class_type!r} class {class_cls.__name__} with priority {override_priority} overrides "
                    f"already registered class {cls._registry[class_type].__name__} with lower priority ({existing_priority})."
                )
            cls._registry[class_type] = class_cls
            cls._override_priorities[class_type] = override_priority
            return class_cls

        return decorator

    @classmethod
    def create_instance(
        cls,
        class_type: ClassNameT | StrEnum | str,
        config: Any | None = None,
        **kwargs: Any,
    ) -> ClassProtocolT:
        """Create a new class instance.

        Args:
            class_type: The type of class to create
            config: The configuration for the class
            **kwargs: Additional arguments for the class

        Returns:
            The created class instance

        Raises:
            FactoryCreationError: If the class type is not registered or there is an error creating the instance
        """
        if class_type not in cls._registry:
            raise FactoryCreationError(f"No implementation found for {class_type!r}.")
        try:
            return cls._registry[class_type](config, **kwargs)
        except Exception as e:
            raise FactoryCreationError(
                f"Error creating {class_type!r} instance: {e}"
            ) from e


################################################################################
# Built-in Factories
################################################################################


class InputConverterFactory(
    GenericBaseFactory["PromptSource", "InputConverterProtocol"]
):
    """Factory for registering and creating InputConverterProtocol instances based on the specified prompt source.

    Example:
    ```python
        # Register a new input converter
        @InputConverterFactory.register(PromptSource.SYNTHETIC)
        class SyntheticInputConverter(InputConverterProtocol):
            pass

        # Create a new input converter instance
        input_converter = InputConverterFactory.create_instance(
            PromptSource.SYNTHETIC,
        )
        input_converter.convert(...)
    ```
    """


class OutputConverterFactory(
    GenericBaseFactory["OutputFormat", "OutputConverterProtocol"]
):
    """Factory for registering and creating OutputConverterProtocol instances based on the specified output format.

    Example:
    ```python
        # Register a new output converter
        @OutputConverterFactory.register(OutputFormat.OPENAI_CHAT_COMPLETIONS)
        class OpenAIChatCompletionsOutputConverter(OutputConverterProtocol):
            pass

        # Create a new output converter instance
        output_converter = OutputConverterFactory.create_instance(
            OutputFormat.OPENAI_CHAT_COMPLETIONS,
        )
        output_converter.convert(...)
    ```
    """


class CommunicationFactory(
    GenericBaseFactory["CommunicationBackend", "BaseCommunication"]
):
    """Factory for registering and creating BaseCommunication instances based on the specified communication backend.

    Example:
    ```python
        # Register a new communication backend
        @CommunicationFactory.register(CommunicationBackend.ZMQ_TCP)
        class ZMQCommunication(BaseCommunication):
            pass

        # Create a new communication instance
        communication = CommunicationFactory.create_instance(
            CommunicationBackend.ZMQ_TCP,
            config=ZMQTCPCommunicationConfig(
                host="localhost", port=5555, timeout=10.0),
        )
    """


class BackendClientFactory(
    GenericBaseFactory["BackendClientType", "BackendClientProtocol"]
):
    """Factory for registering and creating BackendClientProtocol instances based on the specified backend client type.

    Example:
    ```python
        # Register a new backend client
        @BackendClientFactory.register(BackendClientType.OPENAI)
        class OpenAIBackendClient(BackendClientProtocol):
            pass

        backend_client = BackendClientFactory.create_instance(
            BackendClientType.OPENAI,
            config=OpenAIBackendClientConfig(api_key="sk-1234567890"),
        )
        backend_client.send_request(...)
    ```
    """
