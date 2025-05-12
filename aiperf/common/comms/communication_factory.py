import logging
from typing import Dict, Optional, Type

from aiperf.common.comms.communication import Communication
from aiperf.common.comms.zmq_comms.zmq_communication import ZMQCommunication
from aiperf.common.enums import CommBackend
from aiperf.common.models.comms import (
    ZMQCommunicationConfig,
    ZMQTCPTransportConfig,
)

logger = logging.getLogger(__name__)


class CommunicationFactory:
    """Factory for creating communication instances.

    Responsible for creating the appropriate communication implementation
    based on the communication type specified in the configuration.
    """

    # Registry of communication types
    _comm_types: Dict[CommBackend, Type[Communication]] = {
        CommBackend.ZMQ_TCP: ZMQCommunication,
    }

    @classmethod
    def register_comm_type(
        cls, comm_type: CommBackend, comm_class: Type[Communication]
    ) -> None:
        """Register a new communication type.

        Args:
            comm_type: Communication type string
            comm_class: Communication class
        """
        cls._comm_types[comm_type] = comm_class
        logger.info(f"Registered communication type: {comm_type}")

    @classmethod
    def create_communication(
        cls, comm_type: CommBackend, **kwargs
    ) -> Optional[Communication]:
        """Create a communication instance.

        Args:
            comm_type: Communication type string
            **kwargs: Additional arguments to pass to the communication constructor
                      For ZMQ:
                      - config (ZMQCommunicationConfig): Optional configuration

        Returns:
            Communication instance or None if creation failed
        """
        if comm_type not in cls._comm_types:
            logger.error(f"Unknown communication type: {comm_type}")
            return None

        try:
            comm_class = cls._comm_types[comm_type]
            config = kwargs.get("config") or ZMQCommunicationConfig(
                protocol_config=ZMQTCPTransportConfig()
            )
            kwargs["config"] = config

            return comm_class(**kwargs)
        except Exception as e:
            logger.error(f"Error creating communication for type {comm_type}: {e}")
            return None
