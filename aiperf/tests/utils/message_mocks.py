"""
Utilities for mocking messages and testing message handling.
"""

from typing import Any, Dict, List, Type
from unittest.mock import AsyncMock

from aiperf.common.enums import Topic
from aiperf.common.models.messages import BaseMessage


class MessageTestUtils:
    """Utilities for testing message handling in services."""

    @staticmethod
    def create_mock_message(message_class: Type[BaseMessage], **kwargs) -> BaseMessage:
        """
        Create a mock message of the specified class with the given attributes.

        Args:
            message_class: The class of message to create
            **kwargs: Attributes to set on the message

        Returns:
            A mock message instance
        """
        # Create a new instance of the message class
        message = message_class(**kwargs)
        return message

    @staticmethod
    async def simulate_message_receive(
        service, topic: Topic, message: BaseMessage
    ) -> None:
        """
        Simulate a service receiving a message on a specific topic.

        Args:
            service: The service that should receive the message
            topic: The topic the message is sent on
            message: The message to send
        """
        await service._process_message(topic, message)

    @staticmethod
    def verify_message_published(
        mock_communication, topic: Topic, expected_fields: Dict[str, Any]
    ) -> bool:
        """
        Verify that a message with the expected fields was published to the given topic.

        Args:
            mock_communication: The mock communication object
            topic: The topic to check
            expected_fields: Dictionary of field names and values to check

        Returns:
            True if a matching message was found, False otherwise
        """
        topic_str = topic.value
        if topic_str not in mock_communication.published_messages:
            return False

        for message in mock_communication.published_messages[topic_str]:
            matches = True
            for field, value in expected_fields.items():
                if not hasattr(message, field) or getattr(message, field) != value:
                    matches = False
                    break

            if matches:
                return True

        return False


class MessageParamBuilder:
    """Builder for creating parameterized message tests."""

    @staticmethod
    def build_message_params(
        message_class: Type[BaseMessage],
        field_variations: Dict[str, List[Any]],
        required_fields: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build a list of parameter dictionaries for testing message handling with different field values.

        Args:
            message_class: The class of message to parameterize
            field_variations: Dictionary mapping field names to lists of possible values
            required_fields: Dictionary of fields that should be included in all parameter sets

        Returns:
            List of parameter dictionaries for use with pytest.mark.parametrize
        """
        if required_fields is None:
            required_fields = {}

        # Start with a parameter set containing just the required fields
        param_sets = [required_fields.copy()]

        # For each field with variations, create new parameter sets
        for field, values in field_variations.items():
            new_param_sets = []
            for param_set in param_sets:
                for value in values:
                    new_set = param_set.copy()
                    new_set[field] = value
                    new_param_sets.append(new_set)
            param_sets = new_param_sets

        return param_sets


def message_handler_test(message_class, topic, **params):
    """
    Decorator for creating parameterized tests of message handlers.

    Args:
        message_class: The class of message to test
        topic: The topic the message is sent on
        **params: Parameters to use for the test

    Returns:
        A decorator function
    """

    def decorator(func):
        """Decorator function."""

        # Create a wrapper that sets up the test environment
        async def wrapper(self, service_under_test, mock_communication):
            # Create the message
            message = MessageTestUtils.create_mock_message(message_class, **params)

            # Simulate receiving the message
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
        self.call_history = []

    async def __call__(self, *args, **kwargs):
        self.call_history.append((args, kwargs))
        return await super().__call__(*args, **kwargs)
