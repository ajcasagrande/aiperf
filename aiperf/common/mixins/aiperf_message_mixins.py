# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing_extensions import Protocol

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.comms.base_comms import PubClientProtocol, SubClientProtocol
from aiperf.common.hooks import AIPerfHook, AIPerfHookParams, on_init, supports_hooks
from aiperf.common.messages import Message
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.types import MessageHandlerT, MessageTypeT

_logger = AIPerfLogger(__name__)
import logging

logging.basicConfig(level=logging.INFO)


@supports_hooks(AIPerfHook.ON_MESSAGE)
class AIPerfMessageHandlerMixin(AIPerfLifecycleMixin):
    """Mixin to automatically subscribe to messages based on the :meth:`AIPerfHook.ON_MESSAGE` hooks and @on_message decorators.

    Inherits from :class:`AIPerfLifecycleMixin` to provide lifecycle management, auto-tasks, and logging.
    """

    def __init__(self, sub_client: SubClientProtocol, **kwargs):
        _logger.info(
            lambda: f"AIPerfMessageHandlerMixin __init__ for {self.__class__.__name__}"
        )
        self.sub_client = sub_client
        super().__init__(sub_client=sub_client, **kwargs)

        self._message_handlers: dict[MessageTypeT, list[MessageHandlerT]] = {}

        # Process hooks at instance level to avoid sharing across classes
        for hook in self.get_hooks(AIPerfHook.ON_MESSAGE):
            message_types = getattr(hook, AIPerfHookParams.ON_MESSAGE_MESSAGE_TYPES, [])
            for message_type in message_types:
                self.debug(
                    lambda typ=message_type,
                    hook=hook: f"Registering message handler for '{typ}': {self.__class__.__name__}.{hook.__name__}"
                )
                self._register_message_handler(message_type, hook)

    def _register_message_handler(
        self,
        message_type: MessageTypeT,
        handler: MessageHandlerT,
    ) -> None:
        """Register a message handler for a given message type."""
        if message_type in self._message_handlers:
            self._message_handlers[message_type].append(handler)
        else:
            self._message_handlers[message_type] = [handler]

    @on_init
    async def _initialize_message_handler_subscriptions(self) -> None:
        """Subscribe to all message types that have handlers registered from the @on_message decorators."""
        self.info(
            lambda: f"Subscribing to {self._message_handlers} message types for {self.__class__.__name__}"
        )
        await self.sub_client.subscribe_all(self._message_handlers)

    async def subscribe(
        self,
        message_type: MessageTypeT,
        handler: MessageHandlerT,
    ) -> None:
        """Manually subscribe to a message type. Prefer using the :meth:`AIPerfHook.ON_MESSAGE` hooks and @on_message decorators."""
        await self.sub_client.subscribe(message_type, handler)

    # TODO: Unsubscribe not yet supported in the sub client
    # @on_stop
    # async def _shutdown_message_handlers(self):
    #     for message_type, handlers in self._message_handlers.items():
    #         for handler in handlers:
    #             await self.sub_client.unsubscribe(message_type, handler)


class AIPerfMessagePublisherMixin(AIPerfLifecycleMixin):
    """Mixin to provide an interface to publish messages to the event bus.

    Inherits from :class:`AIPerfLifecycleMixin` to provide lifecycle management, auto-tasks, and logging.
    """

    def __init__(self, pub_client: PubClientProtocol, **kwargs):
        self.pub_client = pub_client
        super().__init__(**kwargs)

    async def publish(self, message: Message) -> None:
        """Publish a message to the event bus."""
        await self.pub_client.publish(message)


class AIPerfMessagePubSubMixin(AIPerfMessageHandlerMixin, AIPerfMessagePublisherMixin):
    """Mixin to provide an interface to publish and subscribe to messages over the event bus.

    This mixin is a convenience mixin that combines the :class:`AIPerfMessageHandlerMixin` and :class:`AIPerfMessagePublisherMixin` mixins.

    Inherits from :class:`AIPerfLifecycleMixin` to provide lifecycle management, auto-tasks, and logging.
    """

    def __init__(
        self, sub_client: SubClientProtocol, pub_client: PubClientProtocol, **kwargs
    ) -> None:
        self.sub_client = sub_client
        self.pub_client = pub_client
        super().__init__(sub_client=sub_client, pub_client=pub_client, **kwargs)


class AIPerfMessageHandlerProtocol(Protocol):
    """Protocol for message handlers."""

    async def subscribe(
        self,
        message_type: MessageTypeT,
        handler: MessageHandlerT,
    ) -> None:
        """Subscribe to a message type."""
        ...


class AIPerfMessagePublisherProtocol(Protocol):
    """Protocol for message publishers."""

    async def publish(self, message: Message) -> None:
        """Publish a message to the event bus."""
        ...


class AIPerfMessagePubSubProtocol(
    AIPerfMessageHandlerProtocol, AIPerfMessagePublisherProtocol
):
    """Protocol for messaging over the event bus.

    This protocol is a convenience protocol that combines the :class:`AIPerfMessageHandlerProtocol` and :class:`AIPerfMessagePublisherProtocol` protocols.
    """
