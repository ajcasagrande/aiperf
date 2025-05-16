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

from aiperf.common.errors.base_error import Error


class CommError(Error):
    error_message: str = "An error occurred while communicating."


class CommTypeUnknownError(CommError):
    error_message: str = "The communication type is unknown."


class CommTimeoutError(CommError):
    error_message: str = "A timeout occurred while waiting for a response."


class CommDisconnectedError(CommError):
    error_message: str = "The communication instance is disconnected."


class CommShutdownError(CommError):
    error_message: str = "An error occurred while shutting down the communication."


class CommNotInitializedError(CommError):
    error_message: str = "The communication instance is not initialized."


class CommCreateError(CommError):
    error_message: str = "An error occurred while creating the communication instance."


class CommInitializationError(CommError):
    error_message: str = (
        "An error occurred while initializing the communication instance."
    )


class CommStartError(CommError):
    error_message: str = "An error occurred while starting the communication instance."


class CommStopError(CommError):
    error_message: str = "An error occurred while stopping the communication instance."


class CommPublishError(CommError):
    error_message: str = "An error occurred while publishing a message."


class CommSubscribeError(CommError):
    error_message: str = "An error occurred while subscribing to a topic."


class CommPullError(CommError):
    error_message: str = "An error occurred while pulling a message."


class CommPushError(CommError):
    error_message: str = "An error occurred while pushing a message."


class CommReqError(CommError):
    error_message: str = "An error occurred while sending or receiving a request."


class CommRepError(CommError):
    error_message: str = "An error occurred while sending or receiving a response."


class CommClientCreationError(CommError):
    error_message: str = "An error occurred while creating a communication client."


class CommClientNotFoundError(CommError):
    error_message: str = "A communication client was not found."
