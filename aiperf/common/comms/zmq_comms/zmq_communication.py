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
from typing import Callable, Optional, Dict

import zmq
import zmq.asyncio

from aiperf.common.comms.communication import BaseCommunication
from aiperf.common.enums import ClientType
from aiperf.common.models.comms import ZMQCommunicationConfig
from aiperf.common.models.messages import (
    BaseMessage,
    BaseRequestMessage,
    BaseResponseMessage,
)
from .base import ZmqSocketBase
from .pub import ZmqPublisher
from .pull import ZmqPullSocket
from .push import ZmqPushSocket
from .rep import ZmqRepSocket
from .req import ZmqReqSocket
from .sub import ZmqSubscriber

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

        self.context = zmq.asyncio.Context()

        self.clients: Dict[ClientType, ZmqSocketBase] = {}

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

        self._is_initialized = True
        return True

    async def create_clients(self, *types: ClientType) -> None:
        """Create ZMQ clients based on the provided types.

        Args:
            types: List of ZmqClientType enums indicating the types of clients to create
        """

        for client_type in types:
            if client_type in self.clients:
                continue

            match client_type:
                #### Controller ####
                case ClientType.CONTROLLER_PUB:
                    client = ZmqPublisher(
                        self.context,
                        self.config.controller_pub_sub_address,
                        bind=True,  # Controller is the publisher
                    )
                case ClientType.CONTROLLER_SUB:
                    client = ZmqSubscriber(
                        self.context,
                        self.config.controller_pub_sub_address,
                        bind=False,  # Component services are the subscribers
                    )

                #### Component ####
                case ClientType.COMPONENT_PUB:
                    client = ZmqPublisher(
                        self.context,
                        self.config.component_pub_sub_address,
                        bind=False,  # Component services are the publishers
                    )
                case ClientType.COMPONENT_SUB:
                    client = ZmqSubscriber(
                        self.context,
                        self.config.component_pub_sub_address,
                        bind=True,  # Controller is the subscriber
                    )

                #### Inference ####
                case ClientType.INFERENCE_RESULTS_PUSH:
                    client = ZmqPushSocket(
                        self.context,
                        self.config.inference_push_pull_address,
                        bind=False,  # Workers are the pushers
                    )
                case ClientType.INFERENCE_RESULTS_PULL:
                    client = ZmqPullSocket(
                        self.context,
                        self.config.inference_push_pull_address,
                        bind=True,  # Records manager is the pull
                    )

                #### Records ####
                case ClientType.RECORDS_PUSH:
                    client = ZmqPushSocket(
                        self.context,
                        self.config.records_address,
                        bind=True,  # Records manager is the pusher
                    )
                case ClientType.RECORDS_PULL:
                    client = ZmqPullSocket(
                        self.context,
                        self.config.records_address,
                        bind=True,  # Post processor is the puller
                    )

                #### Conversation ####
                case ClientType.CONVERSATION_DATA_REP:
                    client = ZmqRepSocket(
                        self.context,
                        self.config.conversation_data_address,
                        bind=True,  # Data manager is the reply
                    )
                case ClientType.CONVERSATION_DATA_REQ:
                    client = ZmqReqSocket(
                        self.context,
                        self.config.conversation_data_address,
                        bind=False,  # Worker manager is the request
                    )

                #### Credit Drop ####
                case ClientType.CREDIT_DROP_PUSH:
                    client = ZmqPushSocket(
                        self.context,
                        self.config.credit_drop_address,
                        bind=True,  # Timing manager is the push
                    )
                case ClientType.CREDIT_DROP_PULL:
                    client = ZmqPullSocket(
                        self.context,
                        self.config.credit_drop_address,
                        bind=False,  # Workers are the pullers
                    )

                #### Credit Return ####
                case ClientType.CREDIT_RETURN_PUSH:
                    client = ZmqPushSocket(
                        self.context,
                        self.config.credit_return_address,
                        bind=False,  # Workers are the pushers
                    )
                case ClientType.CREDIT_RETURN_PULL:
                    client = ZmqPullSocket(
                        self.context,
                        self.config.credit_return_address,
                        bind=True,  # Timing manager is the puller
                    )

                case _:
                    raise ValueError(f"Invalid client type: {client_type}")

            await client.initialize()
            self.clients[client_type] = client

    async def shutdown(self) -> bool:
        """Gracefully shutdown communication channels.

        Returns:
            True if shutdown was successful, False otherwise
        """
        if self._is_shutdown:
            return True

        return_val = False
        try:
            logger.info(
                f"Shutting down ZMQ communication for client {self.config.client_id}"
            )
            await asyncio.gather(
                *(client.shutdown() for client in self.clients.values())
            )
            self.context.term()
            self._is_shutdown = True
            logger.info("ZMQ communication shutdown successfully")
            return_val = True
        except Exception as e:
            logger.error(f"Error shutting down ZMQ communication: {e}")
            return_val = False
        finally:
            self._is_initialized = False
            self.clients = {}
            self.context = None
            return return_val

    async def publish(
        self, client_type: ClientType, topic: str, message: BaseMessage
    ) -> bool:
        logger.info(f"Publishing message to topic: {topic}")
        if client_type not in self.clients:
            await self.create_clients(client_type)
        try:
            return await self.clients[client_type].publish(topic, message)
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False

    async def subscribe(
        self,
        client_type: ClientType,
        topic: str,
        callback: Callable[[BaseMessage], None],
    ) -> bool:
        logger.info(f"Subscribing to topic: {topic}")
        if client_type not in self.clients:
            await self.create_clients(client_type)
        try:
            return await self.clients[client_type].subscribe(topic, callback)
        except Exception as e:
            logger.error(f"Error subscribing to topic: {e}")
            return False

    async def request(
        self,
        client_type: ClientType,
        target: str,
        request_data: BaseRequestMessage,
        timeout: float = 5,
    ) -> BaseResponseMessage:
        logger.info(f"Requesting from {target} with data: {request_data}")
        if client_type not in self.clients:
            await self.create_clients(client_type)
        try:
            return await self.clients[client_type].request(
                target, request_data, timeout
            )
        except Exception as e:
            logger.error(f"Error requesting from {target}: {e}")
            return False

    async def respond(
        self, client_type: ClientType, target: str, response: BaseResponseMessage
    ) -> bool:
        logger.info(f"Responding to {target} with data: {response}")
        if client_type not in self.clients:
            await self.create_clients(client_type)
        try:
            return await self.clients[client_type].respond(target, response)
        except Exception as e:
            logger.error(f"Error responding to {target}: {e}")
            return False

    async def push(self, client_type: ClientType, data: BaseMessage) -> bool:
        logger.info(f"Pushing data: {data}")
        if client_type not in self.clients:
            await self.create_clients(client_type)
        try:
            return await self.clients[client_type].push(data)
        except Exception as e:
            logger.error(f"Error pushing data: {e}")
            return False

    async def pull(
        self,
        client_type: ClientType,
        source: str,
        callback: Callable[[BaseMessage], None] | None = None,
    ) -> BaseMessage | bool:
        logger.info(f"Pulling data from {source}")
        if client_type not in self.clients:
            await self.create_clients(client_type)
        try:
            return await self.clients[client_type].pull(source, callback)
        except Exception as e:
            logger.error(f"Error pulling data from {source}: {e}")
            return False
