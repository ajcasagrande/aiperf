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
from typing import Callable, Optional, Dict, Coroutine, Any

import zmq
import zmq.asyncio

from aiperf.common.comms.communication import BaseCommunication
from aiperf.common.enums import (
    ClientType,
    PubClientType,
    SubClientType,
    PushClientType,
    PullClientType,
    ReqClientType,
    RepClientType,
)
from aiperf.common.enums import TopicType
from aiperf.common.exceptions.comms import (
    CommunicationNotInitializedError,
    CommunicationShutdownError,
)
from aiperf.common.models.comms import ZMQCommunicationConfig
from aiperf.common.models.messages import BaseMessage
from aiperf.common.comms.zmq_comms.clients.base import BaseZMQClient
from aiperf.common.comms.zmq_comms.clients.pub import ZMQPubClient
from aiperf.common.comms.zmq_comms.clients.pull import ZMQPullClient
from aiperf.common.comms.zmq_comms.clients.push import ZMQPushClient
from aiperf.common.comms.zmq_comms.clients.rep import ZMQRepClient
from aiperf.common.comms.zmq_comms.clients.req import ZMQReqClient
from aiperf.common.comms.zmq_comms.clients.sub import ZMQSubClient

logger = logging.getLogger(__name__)


class ZMQCommunication(BaseCommunication):
    """ZeroMQ-based implementation of the Communication interface.

    Uses ZeroMQ for publish/subscribe and request/reply patterns to
    facilitate communication between AIPerf components.
    """

    def __init__(
        self,
        config: Optional[ZMQCommunicationConfig] = None,
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

        self.context: Optional[zmq.asyncio.Context] = None
        self.clients: Dict[ClientType, BaseZMQClient] = {}

        logger.info(
            f"ZMQ communication using protocol: {type(self.config.protocol_config).__name__} "
            f"with client ID: {self.config.client_id}"
        )

    async def initialize(self) -> bool:
        """Initialize communication channels.

        Returns:
            True if initialization was successful, False otherwise
        """
        if self._is_initialized:
            return True

        self.context = zmq.asyncio.Context()
        self._is_initialized = True
        return True

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

    async def shutdown(self) -> bool:
        """Gracefully shutdown communication channels.

        Returns:
            True if shutdown was successful, False otherwise
        """
        if self._is_shutdown:
            logger.debug("ZMQ communication already shutdown")
            return True

        return_val = False
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
            return_val = True
        except Exception as e:
            logger.error(f"Error shutting down ZMQ communication: {e}")
            return_val = False
        finally:
            self._is_initialized = False
            self.clients = {}
            self.context = None
            return return_val

    def _ensure_initialized(self) -> None:
        """Ensure the communication channels are initialized.

        Raises:
            RuntimeError: If the communication channels are not initialized
        """
        if not self.is_initialized:
            raise CommunicationNotInitializedError()
        if self.is_shutdown:
            raise CommunicationShutdownError()

    def _create_pub_client(self, client_type: PubClientType) -> ZMQPubClient:
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
                raise ValueError(f"Invalid client type: {client_type}")

    def _create_sub_client(self, client_type: SubClientType) -> ZMQSubClient:
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
                raise ValueError(f"Invalid client type: {client_type}")

    def _create_push_client(self, client_type: PushClientType) -> ZMQPushClient:
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
                raise ValueError(f"Invalid client type: {client_type}")

    def _create_pull_client(self, client_type: PullClientType) -> ZMQPullClient:
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
                raise ValueError(f"Invalid client type: {client_type}")

    def _create_req_client(self, client_type: ReqClientType) -> ZMQReqClient:
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
                raise ValueError(f"Invalid client type: {client_type}")

    def _create_rep_client(self, client_type: RepClientType) -> ZMQRepClient:
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
                raise ValueError(f"Invalid client type: {client_type}")

    async def create_clients(self, *types: ClientType) -> None:
        """Create and initialize ZMQ clients based on the client types.

        Args:
            types: List of ClientType enums indicating the types of clients to create and initialize
        """

        for client_type in types:
            if client_type in self.clients:
                continue

            if isinstance(client_type, PubClientType):
                client = self._create_pub_client(client_type)
            elif isinstance(client_type, SubClientType):
                client = self._create_sub_client(client_type)
            elif isinstance(client_type, PushClientType):
                client = self._create_push_client(client_type)
            elif isinstance(client_type, PullClientType):
                client = self._create_pull_client(client_type)
            elif isinstance(client_type, ReqClientType):
                client = self._create_req_client(client_type)
            elif isinstance(client_type, RepClientType):
                client = self._create_rep_client(client_type)
            else:
                raise ValueError(f"Invalid client type: {client_type}")

            await client.initialize()
            self.clients[client_type] = client

    async def publish(self, topic: TopicType, message: BaseMessage) -> bool:
        self._ensure_initialized()
        logger.debug(f"Publishing message to topic: {topic}")
        client_type = PubClientType.from_topic(topic)
        if client_type not in self.clients:
            logger.warning(
                "Client type %s not found for pub topic %s, creating client",
                client_type,
                topic,
            )
            await self.create_clients(client_type)
        try:
            return await self.clients[client_type].publish(topic, message)
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False

    async def subscribe(
        self,
        topic: TopicType,
        callback: Callable[[BaseMessage], Coroutine[Any, Any, None]] = None,
    ) -> bool:
        logger.debug(f"Subscribing to topic: {topic}")
        self._ensure_initialized()
        client_type = SubClientType.from_topic(topic)
        if client_type not in self.clients:
            logger.warning(
                "Client type %s not found for sub topic %s, creating client",
                client_type,
                topic,
            )
            await self.create_clients(client_type)
        try:
            return await self.clients[client_type].subscribe(topic, callback)
        except Exception as e:
            logger.error(f"Error subscribing to topic: {e}")
            return False

    async def request(
        self,
        target: str,
        request_data: BaseMessage,
        timeout: float = 5.0,
    ) -> BaseMessage:
        logger.debug(f"Requesting from {target} with data: {request_data}")
        self._ensure_initialized()
        client_type = ReqClientType.from_topic(target)
        if client_type not in self.clients:
            logger.warning(
                "Client type %s not found for req topic %s, creating client",
                client_type,
                target,
            )
            await self.create_clients(client_type)
        try:
            return await self.clients[client_type].request(
                target, request_data, timeout
            )
        except Exception as e:
            logger.error(f"Error requesting from {target}: {e}")
            return False

    async def respond(self, target: str, response: BaseMessage) -> bool:
        logger.debug(f"Responding to {target} with data: {response}")
        self._ensure_initialized()
        client_type = RepClientType.from_topic(target)
        if client_type not in self.clients:
            logger.warning(
                "Client type %s not found for rep topic %s, creating client",
                client_type,
                target,
            )
            await self.create_clients(client_type)
        try:
            return await self.clients[client_type].respond(target, response)
        except Exception as e:
            logger.error(f"Error responding to {target}: {e}")
            return False

    async def push(self, topic: TopicType, message: BaseMessage) -> bool:
        logger.debug(f"Pushing data: {message}")
        self._ensure_initialized()
        client_type = PushClientType.from_topic(topic)
        if client_type not in self.clients:
            logger.warning(
                "Client type %s not found for push, creating client",
                client_type,
            )
            await self.create_clients(client_type)
        try:
            return await self.clients[client_type].push(message)
        except Exception as e:
            logger.error(f"Error pushing data: {e}")
            return False

    async def pull(
        self,
        topic: TopicType,
        callback: Callable[[BaseMessage], None] | None = None,
    ) -> BaseMessage | bool:
        logger.debug(f"Pulling data from {topic}")
        self._ensure_initialized()
        client_type = PullClientType.from_topic(topic)
        if client_type not in self.clients:
            logger.warning(
                "Client type %s not found for pull, creating client",
                client_type,
            )
            await self.create_clients(client_type)
        try:
            return await self.clients[client_type].pull(topic, callback)
        except Exception as e:
            logger.error(f"Error pulling data from {topic}: {e}")
            return False
