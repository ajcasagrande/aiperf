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
"""
Utilities for mocking messages and testing response handling.
"""

from typing import Any, Dict, List, Type, TypeVar
from unittest.mock import AsyncMock

from aiperf.common.enums import Topic
from aiperf.common.models.messages import BaseMessage

T = TypeVar("T", bound=BaseMessage)


class MessageTestUtils:
    """Utilities for testing response handling in services."""

    @staticmethod
    def create_mock_message(message_class: Type[T], **kwargs) -> T:
        """
        Create a response of the specified class with the given attributes.

        Args:
            message_class: The class of response to create
            **kwargs: Attributes to set on the response

        Returns:
            A response instance
        """
        return message_class(**kwargs)

    @staticmethod
    async def simulate_message_receive(
        service: Any, topic: Topic, message: BaseMessage
    ) -> None:
        """
        Simulate a service receiving a response on a specific topic.

        Args:
            service: The service that should receive the response
            topic: The topic the response is sent on
            message: The response to send
        """
        # Map topics to their corresponding handler method names
        handler_map = {
            Topic.REGISTRATION: "_process_registration_message",
            Topic.STATUS: "_process_status_message",
            Topic.HEARTBEAT: "_process_heartbeat_message",
            Topic.COMMAND: "_process_command_message",
        }

        if topic in handler_map and hasattr(service, handler_map[topic]):
            handler = getattr(service, handler_map[topic])
            await handler(message)
        else:
            raise AttributeError(
                f"Service does not have a handler for {topic} messages"
            )

    @staticmethod
    def verify_message_published(
        mock_communication: Any, topic: Topic, expected_fields: Dict[str, Any]
    ) -> bool:
        """
        Verify that a response with the expected fields was published to the given topic.

        Args:
            mock_communication: The mock communication object
            topic: The topic to check
            expected_fields: Dictionary of field names and values to check

        Returns:
            True if a matching response was found, False otherwise
        """
        if topic not in mock_communication.published_messages:
            return False

        for message in mock_communication.published_messages[topic]:
            # Check if all expected fields match
            if all(
                hasattr(message, field) and getattr(message, field) == value
                for field, value in expected_fields.items()
            ):
                return True

        return False


class MessageParamBuilder:
    """Builder for creating parameterized response tests."""

    @staticmethod
    def build_message_params(
        message_class: Type[BaseMessage],
        field_variations: Dict[str, List[Any]],
        required_fields: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build a list of parameter dictionaries for testing response handling with different field values.

        Args:
            message_class: The class of response to parameterize
            field_variations: Dictionary mapping field names to lists of possible values
            required_fields: Dictionary of fields that should be included in all parameter sets

        Returns:
            List of parameter dictionaries for use with pytest.mark.parametrize
        """
        required_fields = required_fields or {}

        # Start with a parameter set containing just the required fields
        param_sets = [required_fields.copy()]

        # For each field with variations, create new parameter sets
        for field, values in field_variations.items():
            param_sets = [
                {**param_set, field: value}
                for param_set in param_sets
                for value in values
            ]

        return param_sets


def message_handler_test(message_class: Type[BaseMessage], topic: Topic, **params):
    """
    Decorator for creating parameterized tests of response handlers.

    Args:
        message_class: The class of response to test
        topic: The topic the response is sent on
        **params: Parameters to use for the test

    Returns:
        A decorator function
    """

    def decorator(func):
        """Decorator function."""

        async def wrapper(self, service_under_test, mock_communication):
            # Create the response
            message = MessageTestUtils.create_mock_message(message_class, **params)

            # Simulate receiving the response
            await MessageTestUtils.simulate_message_receive(
                service_under_test, topic, message
            )

            # Call the actual test function
            await func(self, service_under_test, mock_communication, message)

        # Update the wrapper's metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        return wrapper

    return decorator


class AsyncMockWithTracking(AsyncMock):
    """
    An AsyncMock that tracks call history with parameters.
    This is useful for verifying complex interactions in tests.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_history: List[tuple] = []

    async def __call__(self, *args, **kwargs):
        self.call_history.append((args, kwargs))
        return await super().__call__(*args, **kwargs)
