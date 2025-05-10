import asyncio
import logging
import uuid
from typing import Callable, Optional, List, Dict

import zmq
import zmq.asyncio

from aiperf.common.comms.communication import Communication
from aiperf.common.comms.zmq_comms.base import ZmqSocketBase
from aiperf.common.comms.zmq_comms.pub import ZmqPublisher
from aiperf.common.comms.zmq_comms.sub import ZmqSubscriber
from aiperf.common.comms.zmq_comms.rep import ZmqRepSocket
from aiperf.common.comms.zmq_comms.req import ZmqReqSocket
from aiperf.common.comms.zmq_comms.pull import ZmqPullSocket
from aiperf.common.comms.zmq_comms.push import ZmqPushSocket


from aiperf.common.enums import ZmqClientType
from aiperf.common.models.comms import ZMQCommunicationConfig
from aiperf.common.models.messages import BaseMessage
from aiperf.common.models.push_pull import PullData, PushData
from aiperf.common.models.request_response import RequestData, ResponseData

logger = logging.getLogger(__name__)


class ZMQCommunication(Communication):
    """ZeroMQ-based implementation of the Communication interface.

    Uses ZeroMQ for publish/subscribe and request/reply patterns to
    facilitate communication between AIPerf components.
    """

    def __init__(
        self,
        config: Optional[ZMQCommunicationConfig] = None,
        is_controller: bool = False,
    ):
        """Initialize ZMQ communication.

        Args:
            config: ZMQCommunicationConfig object with configuration parameters
            is_controller: Flag indicating if this is the system controller (which binds to sockets)
                           or a service (which connects to sockets)
        """
        self._is_initialized = False
        self._is_shutdown = False
        self.config = config or ZMQCommunicationConfig()
        self.is_controller = is_controller

        # Generate client_id if not provided
        if not self.config.client_id:
            self.config.client_id = f"client_{uuid.uuid4().hex[:8]}"

        self.context = zmq.asyncio.Context()

        self.sockets: Dict[ZmqClientType, ZmqSocketBase] = {}

        logger.info(
            f"ZMQ communication using protocol: {self.config.protocol} "
            f"with client ID: {self.config.client_id}"
        )

    async def initialize(self) -> bool:
        """Initialize communication channels.

        Returns:
            True if initialization was successful, False otherwise
        """
        if self._is_initialized:
            return True

        return True

    async def create_clients(self, *types: List[ZmqClientType]) -> bool:
        """Create ZMQ clients based on the provided types.

        Args:
            types: List of ZmqClientType enums indicating the types of clients to create
        """

        for client_type in types:
            match client_type:
                #### Controller ####
                case ZmqClientType.CONTROLLER_PUB:
                    client = ZmqPublisher(
                        self.context,
                        self.config.controller_pub_sub_address,
                        bind=True,  # Controller is the publisher
                    )
                case ZmqClientType.CONTROLLER_SUB:
                    client = ZmqSubscriber(
                        self.context,
                        self.config.controller_pub_sub_address,
                        bind=False,  # Services are the subscribers
                    )

                #### Component ####
                case ZmqClientType.COMPONENT_PUB:
                    client = ZmqPublisher(
                        self.context,
                        self.config.component_pub_sub_address,
                        bind=False,  # Services are the publishers
                    )
                case ZmqClientType.COMPONENT_SUB:
                    client = ZmqSubscriber(
                        self.context,
                        self.config.component_pub_sub_address,
                        bind=True,  # Controller is the subscriber
                    )

                #### Inference ####
                case ZmqClientType.INFERENCE_PUB:
                    client = ZmqPublisher(
                        self.context,
                        self.config.inference_pub_sub_address,
                        bind=False,  # Workers are the publishers
                    )
                case ZmqClientType.INFERENCE_SUB:
                    client = ZmqSubscriber(
                        self.context,
                        self.config.inference_pub_sub_address,
                        bind=True,  # Records manager is the subscriber
                    )

                #### Records ####
                case ZmqClientType.RECORDS_PUSH:
                    client = ZmqPushSocket(
                        self.context,
                        self.config.records_address,
                        bind=True,  # Records manager is the push
                    )
                case ZmqClientType.RECORDS_PULL:
                    client = ZmqPullSocket(
                        self.context,
                        self.config.records_address,
                        bind=True,  # Post processor is the pull
                    )

                #### Conversation ####
                case ZmqClientType.CONVERSATION_DATA_REP:
                    client = ZmqRepSocket(
                        self.context,
                        self.config.conversation_data_address,
                        bind=True,  # Data manager is the reply
                    )
                case ZmqClientType.CONVERSATION_DATA_REQ:
                    client = ZmqReqSocket(
                        self.context,
                        self.config.conversation_data_address,
                        bind=False,  # Worker manager is the request
                    )

                #### Credit Drop ####
                case ZmqClientType.CREDIT_DROP_PUSH:
                    client = ZmqPushSocket(
                        self.context,
                        self.config.credit_drop_address,
                        bind=True,  # Timing manager is the push
                    )
                case ZmqClientType.CREDIT_DROP_PULL:
                    client = ZmqPullSocket(
                        self.context,
                        self.config.credit_drop_address,
                        bind=False,  # Worker manager is the pull
                    )

                #### Credit Return ####
                case ZmqClientType.CREDIT_RETURN_PUSH:
                    client = ZmqPushSocket(
                        self.context,
                        self.config.credit_return_address,
                        bind=False,  # Workers are the push
                    )
                case ZmqClientType.CREDIT_RETURN_PULL:
                    client = ZmqPullSocket(
                        self.context,
                        self.config.credit_return_address,
                        bind=True,  # Timing manager is the pull
                    )

                case _:
                    raise ValueError(f"Invalid client type: {client_type}")

            await client.initialize()
            self.sockets[client_type] = client
        return True

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
                *(socket.shutdown() for socket in self.sockets.values())
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
            self.sockets = {}
            self.context = None
            return return_val

    async def publish(
        self, client_type: ZmqClientType, topic: str, message: BaseMessage
    ) -> bool:
        logger.info(f"Publishing message to topic: {topic}")
        if client_type not in self.sockets:
            await self.create_clients(client_type)
        try:
            return await self.sockets[client_type].publish(topic, message)
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False

    async def subscribe(
        self,
        client_type: ZmqClientType,
        topic: str,
        callback: Callable[[BaseMessage], None],
    ) -> bool:
        logger.info(f"Subscribing to topic: {topic}")
        if client_type not in self.sockets:
            await self.create_clients(client_type)
        try:
            return await self.sockets[client_type].subscribe(topic, callback)
        except Exception as e:
            logger.error(f"Error subscribing to topic: {e}")
            return False

    async def request(
        self,
        client_type: ZmqClientType,
        target: str,
        request_data: RequestData,
        timeout: float = 5,
    ) -> ResponseData:
        logger.info(f"Requesting from {target} with data: {request_data}")
        if client_type not in self.sockets:
            await self.create_clients(client_type)
        try:
            return await self.sockets[client_type].request(
                target, request_data, timeout
            )
        except Exception as e:
            logger.error(f"Error requesting from {target}: {e}")
            return False

    async def respond(
        self, client_type: ZmqClientType, target: str, response: ResponseData
    ) -> bool:
        logger.info(f"Responding to {target} with data: {response}")
        if client_type not in self.sockets:
            await self.create_clients(client_type)
        try:
            return await self.sockets[client_type].respond(target, response)
        except Exception as e:
            logger.error(f"Error responding to {target}: {e}")
            return False

    async def push(
        self, client_type: ZmqClientType, target: str, data: PushData
    ) -> bool:
        logger.info(f"Pushing data to {target} with data: {data}")
        if client_type not in self.sockets:
            await self.create_clients(client_type)
        try:
            return await self.sockets[client_type].push(target, data)
        except Exception as e:
            logger.error(f"Error pushing data to {target}: {e}")
            return False

    async def pull(
        self,
        client_type: ZmqClientType,
        source: str,
        callback: Callable[[PullData], None] | None = None,
    ) -> PullData | bool:
        logger.info(f"Pulling data from {source}")
        if client_type not in self.sockets:
            await self.create_clients(client_type)
        try:
            return await self.sockets[client_type].pull(source, callback)
        except Exception as e:
            logger.error(f"Error pulling data from {source}: {e}")
            return False
