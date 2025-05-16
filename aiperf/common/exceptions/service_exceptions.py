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

from aiperf.common.exceptions.base_exceptions import AIPerfException


class ServiceException(AIPerfException):
    """Base class for all exceptions raised by services."""

    # TODO: have the base exception class accept the service information
    #       and add it to the pre-defined messages for each exception
    message: str = "Service error"


class ServiceInitializationException(ServiceException):
    """Exception raised for service initialization errors."""

    message: str = "Failed to initialize service"


class ServiceStartException(ServiceException):
    """Exception raised for service start errors."""

    message: str = "Failed to start service"


class ServiceStopException(ServiceException):
    """Exception raised for service stop errors."""

    message: str = "Failed to stop service"


class ServiceCleanupException(ServiceException):
    """Exception raised for service cleanup errors."""

    message: str = "Failed to cleanup service"


class ServiceMessageProcessingException(ServiceException):
    """Exception raised for service message processing errors."""

    message: str = "Failed to process message"


class ServiceRegistrationException(ServiceException):
    """Exception raised for service registration errors."""

    message: str = "Failed to register service"


class ServiceStatusException(ServiceException):
    """Exception raised for service status errors."""

    message: str = "Failed to get service status"


class ServiceRunException(ServiceException):
    """Exception raised for service run errors."""

    message: str = "Failed to run service"


class ServiceConfigureException(ServiceException):
    """Exception raised for service configure errors."""

    message: str = "Failed to configure service"


class ServiceHeartbeatException(ServiceException):
    """Exception raised for service heartbeat errors."""

    message: str = "Failed to send heartbeat"
