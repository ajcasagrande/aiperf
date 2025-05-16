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

import logging

from aiperf.common.comms.base_communication import BaseCommunication
from aiperf.common.comms.zmq_comms.zmq_communication import ZMQCommunication
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import CommBackend
from aiperf.common.errors import Error
from aiperf.common.errors.comm_errors import (
    CommCreateError,
    CommTypeUnknownError,
)
from aiperf.common.models.comm_models import (
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
    _comm_types: dict[CommBackend, type[BaseCommunication]] = {
        CommBackend.ZMQ_TCP: ZMQCommunication,
    }

    @classmethod
    def register_comm_type(
        cls, comm_type: CommBackend, comm_class: type[BaseCommunication]
    ) -> None:
        """Register a new communication type.

        Args:
            comm_type: Communication type string
            comm_class: Communication class
        """
        cls._comm_types[comm_type] = comm_class
        logger.debug("Registered communication type: %s", comm_type)

    @classmethod
    def create_communication(
        cls, service_config: ServiceConfig, **kwargs
    ) -> tuple[BaseCommunication | None, Error | None]:
        """Create a communication instance.

        Args:
            service_config: Service configuration containing the communication type
            **kwargs: Additional arguments for the communication class

        Returns:
            tuple[
                BaseCommunication | None,  # Communication instance
                Error | None,  # Error if creation failed
            ]:
        """
        if service_config.comm_backend not in cls._comm_types:
            logger.error("Unknown communication type: %s", service_config.comm_backend)
            return None, CommTypeUnknownError(
                error_details=f"Unknown communication type: {service_config.comm_backend}"  # noqa: E501
            )

        try:
            comm_class = cls._comm_types[service_config.comm_backend]
            config = kwargs.get("config") or ZMQCommunicationConfig(
                protocol_config=ZMQTCPTransportConfig()
            )
            kwargs["config"] = config

            return comm_class(**kwargs), None
        except Exception as e:
            logger.error(
                "Error creating communication for type %s: %s",
                service_config.comm_backend,
                e,
            )
            return None, CommCreateError.from_exception(e)
