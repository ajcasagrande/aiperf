# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.comms.base_comms import SubClientProtocol
from aiperf.common.enums import CommandType
from aiperf.common.hooks import AIPerfHook, AIPerfHookParams, on_init, supports_hooks
from aiperf.common.messages.commands import CommandMessage
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.types import MessageHandlerT


@supports_hooks(AIPerfHook.ON_COMMAND_MESSAGE)
class AIPerfCommandMessageHandlerMixin(AIPerfLifecycleMixin):
    """Mixin to automatically subscribe to messages based on the :meth:`AIPerfHook.ON_COMMAND_MESSAGE` hooks and @on_command_message decorators.

    Inherits from :class:`AIPerfLifecycleMixin` to provide lifecycle management, auto-tasks, and logging.
    """

    def __init__(self, sub_client: SubClientProtocol, **kwargs):
        self.sub_client = sub_client
        super().__init__(sub_client=sub_client, **kwargs)
        self._command_message_handlers: dict[
            CommandType,
            list[MessageHandlerT],
        ] = {}

        for hook in self.get_hooks(AIPerfHook.ON_COMMAND_MESSAGE):
            message_types = getattr(
                hook, AIPerfHookParams.ON_COMMAND_MESSAGE_MESSAGE_TYPES, []
            )
            for message_type in message_types:
                self._register_command_message_handler(
                    message_type, self._command_handler_wrapper(hook)
                )
                self.debug(
                    lambda typ=message_type: f"Registered command message handler for {typ}"
                )

    def _command_handler_wrapper(self, handler: MessageHandlerT) -> MessageHandlerT:
        """Wrapper to handle command messages and filter them based on their target service id and type."""

        async def handle(message: CommandMessage) -> None:
            if (
                message.target_service_id is not None
                and message.target_service_id != self.service_id
            ):
                self.trace(
                    lambda msg=message: f"Skipping command message for {msg.target_service_id} because it is not for this service {self.service_id}"
                )
                return
            if (
                message.target_service_type is not None
                and message.target_service_type != self.service_type
            ):
                self.trace(
                    lambda msg=message: f"Skipping command message for {msg.target_service_type} because it is not for this service {self.service_type}"
                )
                return
            await handler(message)

        return handle

    def _register_command_message_handler(
        self,
        message_type: CommandType,
        handler: MessageHandlerT,
    ) -> None:
        """Register a command message handler for a given message type."""
        if message_type in self._command_message_handlers:
            self._command_message_handlers[message_type].append(handler)
        else:
            self._command_message_handlers[message_type] = [handler]

    @on_init
    async def _initialize_command_message_handler_subscriptions(self) -> None:
        """Subscribe to all command message types that have handlers registered from the @on_command_message decorators."""
        await self.sub_client.subscribe_all(self._command_message_handlers)

    async def subscribe(
        self,
        message_type: CommandType,
        handler: MessageHandlerT,
    ) -> None:
        """Manually subscribe to a command message type. Prefer using the :meth:`AIPerfHook.ON_COMMAND_MESSAGE` hooks and @on_command_message decorators."""
        await self.sub_client.subscribe(message_type, handler)

    # TODO: Unsubscribe not yet supported in the sub client
    # @on_stop
    # async def _shutdown_message_handlers(self):
    #     for message_type, handlers in self._message_handlers.items():
    #         for handler in handlers:
    #             await self.sub_client.unsubscribe(message_type, handler)
