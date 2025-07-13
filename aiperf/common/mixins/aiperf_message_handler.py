# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable

from aiperf.common.enums import MessageType
from aiperf.common.hooks import AIPerfHook, AIPerfHookParams
from aiperf.common.mixins.event_bus_client import EventBusClientMixin
from aiperf.common.mixins.hooks import HooksMixin, supports_hooks


@supports_hooks(AIPerfHook.ON_MESSAGE)
class AIPerfMessageHandlerMixin(EventBusClientMixin, HooksMixin):
    """Mixin to handle messages."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._message_handlers: dict[MessageType, list[Callable]] = {}

        for hook in self.get_hooks(AIPerfHook.ON_MESSAGE):
            message_types = getattr(hook, AIPerfHookParams.ON_MESSAGE_MESSAGE_TYPES, [])
            for message_type in message_types:
                self._register_message_handler(message_type, hook)

    def _register_message_handler(self, message_type: MessageType, handler: Callable):
        """Register a message handler for a given message type."""
        if message_type in self._message_handlers:
            self._message_handlers[message_type].append(handler)
        else:
            self._message_handlers[message_type] = [handler]

    async def _initialize(self):
        await super()._initialize()

        for message_type, handlers in self._message_handlers.items():
            for handler in handlers:
                self.sub_client.subscribe(message_type, handler)

    # async def _shutdown(self):
    #     await super()._shutdown()

    #     for message_type, handlers in self._message_handlers.items():
    #         for handler in handlers:
    #             self.sub_client.unsubscribe(message_type, handler)
