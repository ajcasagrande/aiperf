# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from collections.abc import Callable, Coroutine

from aiperf.common.comms.base_comms import (
    BaseCommunication,
    CommunicationFactory,
    PullClientProtocol,
    PushClientProtocol,
    ReplyClientProtocol,
    RequestClientProtocol,
)
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.communication_enums import CommunicationClientAddressType
from aiperf.common.enums.message_enums import MessageType
from aiperf.common.messages import (
    CommandMessage,
    CommandResponseMessage,
    CreditDropMessage,
    CreditReturnMessage,
    ErrorMessage,
    Message,
)
from aiperf.common.messages.dataset_messages import (
    ConversationRequest,
    ConversationResponse,
    ConversationTurnRequest,
    ConversationTurnResponse,
    DatasetTimingRequest,
    DatasetTimingResponse,
)
from aiperf.common.messages.inference_messages import (
    InferenceResultsMessage,
    ParsedInferenceResultsMessage,
)
from aiperf.common.models.error_models import ErrorDetails
from aiperf.common.types import (
    Any,
    MessageTypeT,
)
from aiperf.core.decorators import attrs
from aiperf.core.lifecycle import LifecycleMixin


class CommunicationMixin(LifecycleMixin):
    """Mixin that provides an interface to the communication layer."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        self.comms = comms
        super().__init__(comms=comms, **kwargs)

    async def _initialize(self) -> None:
        await super()._initialize()
        await self.comms.initialize()

    async def _stop(self) -> None:
        await super()._stop()
        await self.comms.shutdown()


class MessageBusMixin(CommunicationMixin):
    """Mixin that provide`s an interface to the message bus."""

    def __init__(
        self, service_config: ServiceConfig, user_config: UserConfig, **kwargs
    ) -> None:
        self.comms = CommunicationFactory.create_instance(
            service_config.comm_backend,
            config=service_config.comm_config,
        )
        self.sub_client = self.comms.create_sub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND
        )  # type: ignore
        self.pub_client = self.comms.create_pub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )  # type: ignore
        self.service_config = service_config
        self.user_config = user_config
        # Handler discovery and management
        setattr(self, attrs.message_handler_types, {})
        setattr(self, attrs.command_handler_types, {})

        # Pass through the comms and clients to base classes
        super().__init__(
            comms=self.comms,
            pub_client=self.pub_client,
            sub_client=self.sub_client,
            service_config=self.service_config,
            user_config=self.user_config,
            **kwargs,
        )

    async def publish(self, message: Message) -> None:
        await self.pub_client.publish(message)

    async def _initialize(self) -> None:
        await super()._initialize()
        self._discover_message_handlers()
        await self._register_message_handlers()

    def _discover_message_handlers(self) -> None:
        """Discover message and command handlers from decorators."""
        for name in dir(self):
            method = getattr(self, name)
            if not callable(method):
                continue

            # Message handlers (@message_handler)
            if hasattr(method, attrs.message_handler_types):
                for message_type in getattr(method, attrs.message_handler_types):
                    self.debug(
                        lambda type=message_type,
                        method=method: f"{self}: Registering message handler for {type}: {method}"
                    )
                    getattr(self, attrs.message_handler_types).setdefault(
                        message_type, []
                    ).append(method)

            # Command handlers (@command_handler)
            if hasattr(method, attrs.command_handler_types):
                for command_type in getattr(method, attrs.command_handler_types):
                    self.debug(
                        lambda type=command_type,
                        method=method: f"{self}: Registering command handler for {type}: {method}"
                    )
                    getattr(self, attrs.command_handler_types).setdefault(
                        command_type, []
                    ).append(method)

    async def _register_message_handlers(self) -> None:
        """Register all of the discovered message and command handlers."""
        # For basic messages, we can just subscribe to all of them
        await self.sub_client.subscribe_all(getattr(self, attrs.message_handler_types))

        # For commands, we forward to our internal handler for filtering and automatic
        # response handling.
        command_handlers_dict: dict[MessageTypeT, list[Callable]] = {}
        for typ, handlers in getattr(self, attrs.command_handler_types).items():
            command_handlers_dict[typ] = [
                self._create_command_handler(handler) for handler in handlers
            ]
        await self.sub_client.subscribe_all(command_handlers_dict)

    def _create_command_handler(
        self, handler: Callable[[CommandMessage], Coroutine[Any, Any, Any | None]]
    ) -> Callable[[CommandMessage], Coroutine[Any, Any, None]]:
        """Process a command message received from the controller.

        This method will process the command message and execute the appropriate action.
        """

        async def command_handler(message: CommandMessage) -> None:
            if (
                message.target_service_id is not None
                and message.target_service_id != self.id
            ):
                self.debug(
                    lambda: f"{self.id}: Ignoring command message from {message.target_service_id}: {message}"
                )
                return
                # Check service_type if it exists on this instance
            service_type = getattr(self, "service_type", None)
            if (
                message.target_service_type is not None
                and service_type is not None
                and service_type != message.target_service_type
            ):
                self.debug(
                    lambda: f"{self.id}: Ignoring command message from {message.target_service_type}: {message}"
                )
                return

            response_data: CommandResponseMessage | None = None
            try:
                response_data = await handler(message)

                # Publish the success response
                await self.publish(
                    CommandResponseMessage(
                        message_type=MessageType.CommandResponse,
                        request_id=message.request_id,
                        service_id=self.id,
                        origin_service_id=message.service_id,
                        data=response_data,
                    ),
                )

            except Exception as e:
                self.exception(
                    f"Error processing command message {message.message_type}: {e}"
                )
                # Publish the failure response
                await self.publish(
                    CommandResponseMessage(
                        message_type=MessageType.CommandResponse,
                        request_id=message.request_id,
                        service_id=self.id,
                        origin_service_id=message.service_id,
                        error=ErrorDetails.from_exception(e),
                    ),
                )

        return command_handler


class RequestHandlerMixin(CommunicationMixin):
    """Mixin that provides an interface to handle requests."""

    def __init__(
        self,
        comms: BaseCommunication,
        request_client_address_type: CommunicationClientAddressType,
        **kwargs,
    ) -> None:
        setattr(self, attrs.request_handler_types, {})
        self.router_reply_client: ReplyClientProtocol = comms.create_reply_client(
            request_client_address_type
        )  # type: ignore
        super().__init__(
            comms=comms, router_reply_client=self.router_reply_client, **kwargs
        )

    async def _initialize(self) -> None:
        await super()._initialize()
        self._discover_request_handlers()
        self._register_request_handlers()

    def _discover_request_handlers(self) -> None:
        """Discover request handlers from decorators."""
        for name in dir(self):
            method = getattr(self, name)
            if not callable(method):
                continue

            # Request handlers (@request_handler)
            if hasattr(method, attrs.request_handler_types):
                for message_type in getattr(method, attrs.request_handler_types):
                    getattr(self, attrs.request_handler_types).setdefault(
                        message_type, []
                    ).append(method)

    def _register_request_handlers(self) -> None:
        """Register all of the discovered request handlers."""
        for message_type, handlers in getattr(
            self, attrs.request_handler_types
        ).items():
            for handler in handlers:
                self.debug(
                    lambda type=message_type,
                    method=handler: f"{self}: Registering request handler for {type}: {method}"
                )
                # NOTE: The router reply client will handle errors and return a response message.
                self.router_reply_client.register_request_handler(
                    self.id, message_type, handler
                )


class DatasetRequestHandler(RequestHandlerMixin):
    """Mixin that provides an interface to handle dataset requests."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        super().__init__(
            comms=comms,
            request_client_address_type=CommunicationClientAddressType.DATASET_MANAGER_PROXY_BACKEND,
            **kwargs,
        )


class DatasetRequestClientMixin(CommunicationMixin):
    """Mixin that provides an interface make dataset requests."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        self.conversation_request_client: RequestClientProtocol = (
            comms.create_request_client(
                CommunicationClientAddressType.DATASET_MANAGER_PROXY_FRONTEND
            )
        )  # type: ignore
        super().__init__(
            comms=comms,
            conversation_request_client=self.conversation_request_client,
            **kwargs,
        )

    async def request_conversation(
        self, message: ConversationRequest
    ) -> ConversationResponse | ErrorMessage:
        return await self.conversation_request_client.request(message)

    async def request_conversation_turn(
        self, message: ConversationTurnRequest
    ) -> ConversationTurnResponse | ErrorMessage:
        return await self.conversation_request_client.request(message)

    async def request_dataset_timing(
        self, message: DatasetTimingRequest
    ) -> DatasetTimingResponse | ErrorMessage:
        return await self.conversation_request_client.request(message)


class PullHandlerMixin(CommunicationMixin):
    """Mixin that provides an interface to handle pull messages."""

    def __init__(
        self,
        comms: BaseCommunication,
        pull_client_address_type: CommunicationClientAddressType,
        pull_client_bind: bool = False,
        **kwargs,
    ) -> None:
        setattr(self, attrs.pull_handler_types, {})
        self.pull_client: PullClientProtocol = comms.create_pull_client(
            pull_client_address_type,
            bind=pull_client_bind,  # type: ignore
        )  # type: ignore
        super().__init__(comms=comms, pull_client=self.pull_client, **kwargs)

    async def _initialize(self) -> None:
        await super()._initialize()
        self._discover_pull_handlers()
        await self._register_pull_handlers()

    def _discover_pull_handlers(self) -> None:
        """Discover pull handlers from decorators."""
        for name in dir(self):
            method = getattr(self, name)
            if not callable(method):
                continue

            # Pull handlers (@pull_handler)
            if hasattr(method, attrs.pull_handler_types):
                for message_type in getattr(method, attrs.pull_handler_types):
                    getattr(self, attrs.pull_handler_types).setdefault(
                        message_type, []
                    ).append(method)

    async def _register_pull_handlers(self) -> None:
        """Register all of the discovered pull handlers."""
        for message_type, handlers in getattr(self, attrs.pull_handler_types).items():
            for handler in handlers:
                self.debug(
                    lambda type=message_type,
                    method=handler: f"{self}: Registering pull handler for {type}: {method}"
                )
                await self.pull_client.register_pull_callback(
                    self.id, message_type, handler
                )


class CreditDropPushClientMixin(CommunicationMixin):
    """Mixin that provides an interface to handle credit drop messages."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        self.credit_drop_client: PushClientProtocol = comms.create_push_client(
            CommunicationClientAddressType.CREDIT_DROP,
            bind=True,  # type: ignore
        )  # type: ignore
        super().__init__(
            comms=comms, credit_drop_client=self.credit_drop_client, **kwargs
        )

    async def push_credit_drop(self, message: CreditDropMessage) -> None:
        await self.credit_drop_client.push(message)


class CreditDropPullHandlerMixin(PullHandlerMixin):
    """Mixin that provides an interface to handle receiving credit drop messages from the TimingManager."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        super().__init__(
            comms=comms,
            pull_client_address_type=CommunicationClientAddressType.CREDIT_DROP,
            pull_client_bind=True,
            **kwargs,
        )


class CreditReturnPushClientMixin(CommunicationMixin):
    """Mixin that provides an interface to handle credit return messages."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        self.credit_return_client: PushClientProtocol = comms.create_push_client(
            CommunicationClientAddressType.CREDIT_RETURN
        )  # type: ignore
        super().__init__(
            comms=comms, credit_return_client=self.credit_return_client, **kwargs
        )

    async def push_credit_return(self, message: CreditReturnMessage) -> None:
        await self.credit_return_client.push(message)


class CreditReturnPullHandlerMixin(PullHandlerMixin):
    """Mixin that provides an interface to handle receiving credit return messages from the Worker."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        super().__init__(
            comms=comms,
            pull_client_address_type=CommunicationClientAddressType.CREDIT_RETURN,
            pull_client_bind=True,
            **kwargs,
        )


class RawInferencePushClientMixin(CommunicationMixin):
    """Mixin that provides an interface to push raw inference messages to the InferenceParser."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        self.raw_inference_push_client: PushClientProtocol = comms.create_push_client(
            CommunicationClientAddressType.RAW_INFERENCE_PROXY_FRONTEND
        )  # type: ignore
        super().__init__(
            comms=comms,
            raw_inference_push_client=self.raw_inference_push_client,
            **kwargs,
        )

    async def push_inference_results(self, message: InferenceResultsMessage) -> None:
        await self.raw_inference_push_client.push(message)


class RawInferencePullHandlerMixin(PullHandlerMixin):
    """Mixin that provides an interface to handle receiving raw inference messages from the Worker."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        super().__init__(
            comms=comms,
            pull_client_address_type=CommunicationClientAddressType.RAW_INFERENCE_PROXY_BACKEND,
            **kwargs,
        )


class ParsedInferencePushClientMixin(CommunicationMixin):
    """Mixin that provides an interface to push parsed inference messages to the RecordManager."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        self.parsed_inference_push_client: PushClientProtocol = (
            comms.create_push_client(CommunicationClientAddressType.PARSED_INFERENCE)
        )  # type: ignore
        super().__init__(
            comms=comms,
            parsed_inference_push_client=self.parsed_inference_push_client,
            **kwargs,
        )

    async def push_parsed_inference_results(
        self, message: ParsedInferenceResultsMessage
    ) -> None:
        await self.parsed_inference_push_client.push(message)


class ParsedInferencePullHandlerMixin(PullHandlerMixin):
    """Mixin that provides an interface to handle receiving parsed inference messages from the InferenceParser."""

    def __init__(self, comms: BaseCommunication, **kwargs) -> None:
        super().__init__(
            comms=comms,
            pull_client_address_type=CommunicationClientAddressType.PARSED_INFERENCE,
            pull_client_bind=True,
            **kwargs,
        )
