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

from pydantic import Field

from aiperf.common.enums.service_enums import ServiceType
from aiperf.common.errors.base_error import Error


class ServiceError(Error):
    error_message: str = "A generic service error occurred."

    service_id: str | None = Field(
        default=None,
        description="Optional ID of the service that encountered the error",
    )
    service_type: ServiceType | None = Field(
        default=None,
        description="Optional type of the service that encountered the error",
    )


class ServiceInitializationError(ServiceError):
    error_message: str = "An error occurred while initializing the service."


class ServiceStartError(ServiceError):
    error_message: str = "An error occurred while starting the service."


class ServiceRunError(ServiceError):
    error_message: str = "An error occurred while attempting to run the service."


class ServiceStopError(ServiceError):
    error_message: str = "An error occurred while stopping the service."


class ServiceCleanupError(ServiceError):
    error_message: str = "An error occurred while cleaning up the service."


class ServiceMessageProcessingError(ServiceError):
    error_message: str = "An error occurred while processing a message."


class ServiceRegistrationError(ServiceError):
    error_message: str = "An error occurred while registering the service."


class ServiceStatusError(ServiceError):
    error_message: str = "An error occurred while getting the service status."
