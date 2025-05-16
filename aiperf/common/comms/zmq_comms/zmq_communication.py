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
import asyncio
import logging
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import zmq.asyncio

from aiperf.common.comms.base_communication import BaseCommunication
from aiperf.common.comms.zmq_comms.clients import ZMQClient
from aiperf.common.comms.zmq_comms.clients.zmq_pub_client import ZMQPubClient
from aiperf.common.comms.zmq_comms.clients.zmq_pull_client import ZMQPullClient
from aiperf.common.comms.zmq_comms.clients.zmq_push_client import ZMQPushClient
from aiperf.common.comms.zmq_comms.clients.zmq_rep_client import ZMQRepClient
from aiperf.common.comms.zmq_comms.clients.zmq_req_client import ZMQReqClient
from aiperf.common.comms.zmq_comms.clients.zmq_sub_client import ZMQSubClient
from aiperf.common.enums import (
    ClientType,
    PubClientType,
    PullClientType,
    PushClientType,
    RepClientType,
    ReqClientType,
    SubClientType,
    TopicType,
)
from aiperf.common.errors.base_error import Error
from aiperf.common.errors.comm_errors import (
    CommClientCreationError,
    CommNotInitializedError,
    CommPublishError,
    CommPushError,
    CommRepError,
    CommReqError,
    CommShutdownError,
    CommSubscribeError,
)
from aiperf.common.models.comm_models import ZMQCommunicationConfig
from aiperf.common.models.message_models import BaseMessage

logger = logging.getLogger(__name__)


class ZMQCommunication(BaseCommunication):
    """ZeroMQ-based implementation of the Communication interface.

    Uses ZeroMQ for publish/subscribe and request/reply patterns to
    facilitate communication between AIPerf components.
    """

    def __init__(
        self,
        config: ZMQCommunicationConfig | None = None,
    ):
        """Initialize ZMQ communication.

        Args:
            config: ZMQCommunicationConfig object with configuration parameters
        """
        self._is_initialized = False
        self._is_shutdown = False
        self.config = config

        # Generate client_id if not provided
        if not self.config.client_id:
            self.config.client_id = f"client_{uuid.uuid4().hex[:8]}"

        self.context: zmq.asyncio.Context | None = None
        self.clients: dict[ClientType, ZMQClient] = {}

        logger.debug(
            "ZMQ communication using protocol: %s with client ID: %s",
            type(self.config.protocol_config).__name__,
            self.config.client_id,
        )

    async def initialize(self) -> Error | None:
        """Initialize communication channels.

        Returns:
            True if initialization was successful, False otherwise
        """
        if self._is_initialized:
            return None

        self.context = zmq.asyncio.Context()
        self._is_initialized = True
        return None

    @property
    def is_initialized(self) -> bool:
        """Check if communication channels are initialized.

        Returns:
            True if communication channels are initialized, False otherwise
        """
        return self._is_initialized

    @property
    def is_shutdown(self) -> bool:
        """Check if communication channels are shutdown.

        Returns:
            True if communication channels are shutdown, False otherwise
        """
        return self._is_shutdown

    async def shutdown(self) -> Error | None:
        """Gracefully shutdown communication channels.

        Returns:
            True if shutdown was successful, False otherwise
        """
        if self._is_shutdown:
            logger.debug("ZMQ communication already shutdown")
            return None

        try:
            logger.debug(
                f"Shutting down ZMQ communication for client {self.config.client_id}"
            )
            await asyncio.gather(
                *(client.shutdown() for client in self.clients.values())
            )
            if self.context:
                self.context.term()
            self._is_shutdown = True
            logger.debug("ZMQ communication shutdown successfully")
        except Exception as e:
            logger.error(f"Error shutting down ZMQ communication: {e}")
            return CommShutdownError.from_exception(e)
        finally:
            self._is_initialized = False
            self.clients = {}
            self.context = None
        return None

    def _ensure_initialized(self) -> Error | None:
        """Ensure the communication channels are initialized.

        Returns:
            Error object or None if the communication channels are initialized
        """
        if not self.is_initialized:
            return CommNotInitializedError()
        if self.is_shutdown:
            return CommShutdownError()
        return None

    def _create_pub_client(self, client_type: PubClientType) -> ZMQPubClient | Error:
        """Create a ZMQ publisher client based on the client type.

        Args:
            client_type: The type of client to create
        """
        match client_type:
            case PubClientType.CONTROLLER:
                return ZMQPubClient(
                    self.context,
                    self.config.controller_pub_sub_address,
                    bind=True,
                )

            case PubClientType.COMPONENT:
                return ZMQPubClient(
                    self.context,
                    self.config.component_pub_sub_address,
                    bind=False,
                )

            case _:
                return CommClientCreationError(
                    error_details=f"Invalid client type: {client_type}"
                )

    def _create_sub_client(self, client_type: SubClientType) -> ZMQSubClient | Error:
        """Create a ZMQ subscriber client based on the client type.

        Args:
            client_type: The type of client to create
        """
        match client_type:
            case SubClientType.CONTROLLER:
                return ZMQSubClient(
                    self.context,
                    self.config.controller_pub_sub_address,
                    bind=False,
                )

            case SubClientType.COMPONENT:
                return ZMQSubClient(
                    self.context,
                    self.config.component_pub_sub_address,
                    bind=True,
                )

            case _:
                return CommClientCreationError(
                    error_details=f"Invalid client type: {client_type}"
                )

    def _create_push_client(self, client_type: PushClientType) -> ZMQPushClient | Error:
        """Create a ZMQ push client based on the client type.

        Args:
            client_type: The type of client to create
        """
        match client_type:
            case PushClientType.INFERENCE_RESULTS:
                return ZMQPushClient(
                    self.context,
                    self.config.inference_push_pull_address,
                    bind=False,  # Workers are the pushers
                )

            case PushClientType.CREDIT_DROP:
                return ZMQPushClient(
                    self.context,
                    self.config.credit_drop_address,
                    bind=True,
                )

            case PushClientType.CREDIT_RETURN:
                return ZMQPushClient(
                    self.context,
                    self.config.credit_return_address,
                    bind=False,
                )

            case PushClientType.RECORDS:
                return ZMQPushClient(
                    self.context,
                    self.config.records_address,
                    bind=False,
                )

            case _:
                return CommClientCreationError(
                    error_details=f"Invalid client type: {client_type}"
                )

    def _create_pull_client(self, client_type: PullClientType) -> ZMQPullClient | Error:
        """Create a ZMQ pull client based on the client type.

        Args:
            client_type: The type of client to create
        """
        match client_type:
            case PullClientType.INFERENCE_RESULTS:
                return ZMQPullClient(
                    self.context,
                    self.config.inference_push_pull_address,
                    bind=True,  # Records manager is the pull
                )

            case PullClientType.CREDIT_DROP:
                return ZMQPullClient(
                    self.context,
                    self.config.credit_drop_address,
                    bind=False,
                )

            case PullClientType.CREDIT_RETURN:
                return ZMQPullClient(
                    self.context,
                    self.config.credit_return_address,
                    bind=True,
                )

            case PushClientType.RECORDS:
                return ZMQPullClient(
                    self.context,
                    self.config.records_address,
                    bind=True,
                )

            case _:
                return CommClientCreationError(
                    error_details=f"Invalid client type: {client_type}"
                )

    def _create_req_client(self, client_type: ReqClientType) -> ZMQReqClient | Error:
        """Create a ZMQ request client based on the client type.

        Args:
            client_type: The type of client to create
        """
        match client_type:
            case ReqClientType.CONVERSATION_DATA:
                return ZMQReqClient(
                    self.context,
                    self.config.conversation_data_address,
                    bind=False,  # Worker manager is the request
                )
            case _:
                return CommClientCreationError(
                    error_details=f"Invalid client type: {client_type}"
                )

    def _create_rep_client(self, client_type: RepClientType) -> ZMQRepClient | Error:
        """Create a ZMQ reply client based on the client type.

        Args:
            client_type: The type of client to create
        """
        match client_type:
            case RepClientType.CONVERSATION_DATA:
                return ZMQRepClient(
                    self.context,
                    self.config.conversation_data_address,
                    bind=True,  # Data manager is the reply
                )

            case _:
                return CommClientCreationError(
                    error_details=f"Invalid client type: {client_type}"
                )

    async def create_clients(self, *types: ClientType) -> Error | None:
        """Create and initialize ZMQ clients based on the client types.

        Args:
            types: List of ClientType enums indicating the types of clients to
            create and initialize

        Returns:
            Error if the clients were not created successfully, None otherwise
        """

        for client_type in types:
            if client_type in self.clients:
                continue

            if isinstance(client_type, PubClientType):
                result = self._create_pub_client(client_type)

            elif isinstance(client_type, SubClientType):
                result = self._create_sub_client(client_type)

            elif isinstance(client_type, PushClientType):
                result = self._create_push_client(client_type)

            elif isinstance(client_type, PullClientType):
                result = self._create_pull_client(client_type)

            elif isinstance(client_type, ReqClientType):
                result = self._create_req_client(client_type)

            elif isinstance(client_type, RepClientType):
                result = self._create_rep_client(client_type)

            else:
                result = CommClientCreationError(
                    error_details=f"Invalid client type: {client_type}"
                )

            if isinstance(result, Error):
                return result

            client = result
            if error := await client.initialize():
                return error

            self.clients[client_type] = client

        return None

    async def publish(self, topic: TopicType, message: BaseMessage) -> Error | None:
        if error := self._ensure_initialized():
            return error
        logger.debug("Publishing message to topic: %s, message: %s", topic, message)

        client_type, error = PubClientType.from_topic(topic)
        if error:
            return error

        if client_type not in self.clients:
            logger.warning(
                "Client type %s not found for pub topic %s, creating client",
                client_type,
                topic,
            )
            if error := await self.create_clients(client_type):
                return error

        try:
            return await self.clients[client_type].publish(topic, message)
        except Exception as e:
            logger.error(
                "Error publishing message to topic: %s, message: %s, error: %s",
                topic,
                message,
                e,
            )
            return CommPublishError.from_exception(e)

    async def subscribe(
        self,
        topic: TopicType,
        callback: Callable[[BaseMessage], Coroutine[Any, Any, Error | None]],
    ) -> Error | None:
        logger.debug(f"Subscribing to topic: {topic}")

        if error := self._ensure_initialized():
            return error

        client_type, error = SubClientType.from_topic(topic)
        if error:
            return error

        if client_type not in self.clients:
            logger.warning(
                "Client type %s not found for sub topic %s, creating client",
                client_type,
                topic,
            )
            if error := await self.create_clients(client_type):
                return error

        try:
            return await self.clients[client_type].subscribe(topic, callback)
        except Exception as e:
            logger.error(f"Error subscribing to topic: {e}")
            return CommSubscribeError.from_exception(e)

    async def request(
        self,
        target: str,
        request_data: BaseMessage,
        timeout: float = 5.0,
    ) -> BaseMessage | Error:
        logger.debug(f"Requesting from {target} with data: {request_data}")

        if error := self._ensure_initialized():
            return error

        client_type, error = ReqClientType.from_topic(target)
        if error:
            return error

        if client_type not in self.clients:
            logger.warning(
                "Client type %s not found for req topic %s, creating client",
                client_type,
                target,
            )
            if error := await self.create_clients(client_type):
                return error

        try:
            return await self.clients[client_type].request(
                target, request_data, timeout
            )
        except Exception as e:
            logger.error(f"Error requesting from {target}: {e}")
            return CommReqError.from_exception(e)

    async def respond(self, target: str, response: BaseMessage) -> Error | None:
        logger.debug(f"Responding to {target} with data: {response}")
        if error := self._ensure_initialized():
            return error

        client_type, error = RepClientType.from_topic(target)
        if error:
            return error

        if client_type not in self.clients:
            logger.warning(
                "Client type %s not found for rep topic %s, creating client",
                client_type,
                target,
            )
            if error := await self.create_clients(client_type):
                return error

        try:
            return await self.clients[client_type].respond(target, response)
        except Exception as e:
            logger.error(f"Error responding to {target}: {e}")
            return CommRepError.from_exception(e)

    async def push(self, topic: TopicType, message: BaseMessage) -> Error | None:
        logger.debug("Pushing data to topic: %s, message: %s", topic, message)
        if error := self._ensure_initialized():
            return error

        client_type, error = PushClientType.from_topic(topic)
        if error:
            return error

        if client_type not in self.clients:
            logger.warning(
                "Client type %s not found for push, creating client",
                client_type,
            )
            if error := await self.create_clients(client_type):
                return error

        try:
            return await self.clients[client_type].push(message)
        except Exception as e:
            logger.error(f"Error pushing data: {e}")
            return CommPushError.from_exception(e)

    async def pull(
        self,
        topic: TopicType,
        callback: Callable[[BaseMessage], None],
    ) -> Error | None:
        logger.debug(f"Pulling data from {topic}")

        if error := self._ensure_initialized():
            return error

        client_type, error = PullClientType.from_topic(topic)
        if error:
            return error

        if client_type not in self.clients:
            logger.warning(
                "Client type %s not found for pull, creating client",
                client_type,
            )
            if error := await self.create_clients(client_type):
                return error

        return await self.clients[client_type].pull(topic, callback)
