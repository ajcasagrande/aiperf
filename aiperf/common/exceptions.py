# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC
from typing import ClassVar, Protocol, runtime_checkable

from aiperf.common.enums import ServiceType


class AIPerfError(Exception):
    """Base class for all exceptions raised by AIPerf."""

    def raw_str(self) -> str:
        """Return the raw string representation of the exception."""
        return super().__str__()

    def __str__(self) -> str:
        """Return the string representation of the exception with the class name."""
        return (
            f"{self.__class__.__name__}: {self.raw_str()}"
            if not isinstance(super(), AIPerfError)
            else self.raw_str()
        )


class AIPerfMultiError(AIPerfError):
    """Exception raised when running multiple tasks and one or more fail."""

    def __init__(self, message: str, exceptions: list[Exception]) -> None:
        err_strings = [
            e.raw_str() if isinstance(e, AIPerfError) else str(e) for e in exceptions
        ]
        super().__init__(f"{message}: {','.join(err_strings)}")
        self.exceptions = exceptions


################################################################################
# HTTP Errors
################################################################################


@runtime_checkable
class HTTPErrorProtocol(Protocol):
    """Protocol for HTTP errors that have a code and reason."""

    code: int
    reason: str


class HTTPError(AIPerfError):
    """Generic exception raised when a HTTP error occurs. The code and reason are set by the caller."""

    def __init__(self, message: str, code: int, reason: str) -> None:
        super().__init__(message)
        self.code = code
        self.reason = reason


class HTTPErrorClass(AIPerfError, ABC):
    """A base class for static pre-defined HTTP errors with a code and reason."""

    code: ClassVar[int]
    reason: ClassVar[str]

    def __eq__(self, other: object) -> bool:
        """Check if an HTTPError is an instance of this class."""
        if isinstance(other, self.__class__):
            return True
        if not isinstance(other, HTTPError):
            return False
        return other.code == self.code and other.reason == self.reason


class BadRequestError(HTTPErrorClass):
    """Exception raised when a request is invalid."""

    code = 400
    reason = "Bad Request"


class NotFoundError(HTTPErrorClass):
    """Exception raised when a resource is not found."""

    code = 404
    reason = "Not Found"


class InternalServerError(HTTPErrorClass):
    """Exception raised when an internal server error occurs."""

    code = 500
    reason = "Internal Server Error"


################################################################################
# Service and Runtime Errors
################################################################################


class ServiceError(AIPerfError):
    """Generic service error."""

    def __init__(
        self,
        message: str,
        service_type: ServiceType,
        service_id: str,
    ) -> None:
        super().__init__(
            f"{message} for service of type {service_type} with id {service_id}"
        )
        self.service_type = service_type
        self.service_id = service_id


class CommandError(AIPerfError):
    """Exception raised when a command encounters an error."""


class InitializationError(AIPerfError):
    """Exception raised when something fails to initialize."""


class ConfigurationError(AIPerfError):
    """Exception raised when something fails to configure, or there is a configuration error."""


class NotInitializedError(AIPerfError):
    """Exception raised when something that should be initialized is not."""


class InvalidStateError(AIPerfError):
    """Exception raised when something is in an invalid state."""


class ValidationError(AIPerfError):
    """Exception raised when something fails validation."""


class CommunicationError(AIPerfError):
    """Generic communication error."""


class DatasetError(AIPerfError):
    """Generic dataset error."""


class DatasetGeneratorError(AIPerfError):
    """Generic dataset generator error."""


class InferenceClientError(AIPerfError):
    """Exception raised when a inference client encounters an error."""


class InvalidPayloadError(InferenceClientError):
    """Exception raised when a inference client receives an invalid payload."""


class UnsupportedHookError(AIPerfError):
    """Exception raised when a hook is defined on a class that does not support it."""


class FactoryCreationError(AIPerfError):
    """Exception raised when a factory encounters an error while creating a class."""


class MetricTypeError(AIPerfError):
    """Exception raised when a metric type encounters an error while creating a class."""


class ShutdownError(AIPerfError):
    """Exception raised when a service encounters an error while shutting down."""


class ProxyError(AIPerfError):
    """Exception raised when a proxy encounters an error."""


class ServiceTimeoutError(AIPerfError):
    """Exception raised when a service registration times out."""


class PluginError(AIPerfError):
    """Exception raised when a plugin encounters an error."""


class PluginNotFoundError(PluginError):
    """Exception raised when a plugin is not found."""
