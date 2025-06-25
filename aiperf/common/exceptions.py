# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

################################################################################
# Base Exceptions
################################################################################


from aiperf.common.enums import CaseInsensitiveStrEnum, ServiceType


class AIPerfError(Exception):
    """Base class for all exceptions raised by AIPerf."""

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {super().__str__()}"


class AIPerfMultiError(AIPerfError):
    """Exception raised when running multiple tasks and one or more fail."""

    def __init__(self, message: str, exceptions: list[Exception]) -> None:
        super().__init__(f"{message}: {','.join([str(e) for e in exceptions])}")
        self.exceptions = exceptions


################################################################################
# Communication Exceptions
################################################################################


class CommunicationErrorReason(CaseInsensitiveStrEnum):
    CLIENT_NOT_FOUND = "client_not_found"
    PUBLISH_ERROR = "publish_error"
    SUBSCRIBE_ERROR = "subscribe_error"
    REQUEST_ERROR = "request_error"
    RESPONSE_ERROR = "response_error"
    SHUTDOWN_ERROR = "shutdown_error"
    INITIALIZATION_ERROR = "initialization_error"
    NOT_INITIALIZED_ERROR = "not_initialized_error"
    CLEANUP_ERROR = "cleanup_error"
    PUSH_ERROR = "push_error"
    PULL_ERROR = "pull_error"
    PROXY_ERROR = "proxy_error"


class CommunicationError(AIPerfError):
    """Base class for all communication exceptions."""

    def __init__(self, reason: CommunicationErrorReason, message: str) -> None:
        super().__init__(f"Communication Error {reason.name}: {message}")
        self.reason = reason


################################################################################
# Configuration Exceptions
################################################################################


class ConfigErrorReason(CaseInsensitiveStrEnum):
    LOAD_ERROR = "load_error"
    PARSE_ERROR = "parse_error"
    VALIDATION_ERROR = "validation_error"
    UNSUPPORTED_RUN_TYPE = "unsupported_run_type"


class ConfigError(AIPerfError):
    """Base class for all exceptions raised by configuration errors."""

    def __init__(self, reason: ConfigErrorReason, message: str) -> None:
        super().__init__(f"Configuration Error {reason.name}: {message}")
        self.reason = reason


################################################################################
# Dataset Generator Exceptions
################################################################################


class GeneratorErrorReason(CaseInsensitiveStrEnum):
    INITIALIZATION_ERROR = "initialization_error"
    CONFIGURATION_ERROR = "configuration_error"
    PREFIX_PROMPTS_POOL_EMPTY = "prefix_prompts_pool_empty"


class GeneratorError(AIPerfError):
    """Base class for all exceptions raised by data generator modules."""

    def __init__(self, reason: GeneratorErrorReason, message: str) -> None:
        super().__init__(f"Generator Error {reason.name}: {message}")
        self.reason = reason


################################################################################
# Service Exceptions
################################################################################


class ServiceErrorType(CaseInsensitiveStrEnum):
    INITIALIZATION_ERROR = "initialization_error"
    CONFIGURATION_ERROR = "configuration_error"
    START_ERROR = "start_error"
    SHUTDOWN_ERROR = "shutdown_error"
    REGISTRATION_ERROR = "registration_error"
    HEARTBEAT_ERROR = "heartbeat_error"
    CLIENT_NOT_AVAILABLE = "client_not_available"
    WORKER_TIMEOUT = "worker_timeout"
    SEND_CONFIGURE_COMMAND_ERROR = "send_configure_command_error"
    MISSING_REQUIRED_SERVICES = "missing_required_services"
    INITIALIZE_SERVICES_ERROR = "initialize_services_error"
    SUBSCRIBE_COMMAND_TOPIC_ERROR = "subscribe_command_topic_error"
    REGISTER_SERVICE_ERROR = "register_service_error"
    UNKNOWN_COMMAND = "unknown_command"


class ServiceError(AIPerfError):
    """Base class for all exceptions raised by services."""

    def __init__(
        self,
        reason: ServiceErrorType,
        message: str,
        service_type: ServiceType,
        service_id: str,
    ) -> None:
        super().__init__(
            f"Service Error {reason.name}: {message} for service of type {service_type} with id {service_id}"
        )
        self.reason = reason
        self.service_type = service_type
        self.service_id = service_id


################################################################################
# Tokenizer Exceptions
################################################################################


class TokenizerErrorReason(CaseInsensitiveStrEnum):
    INITIALIZATION_ERROR = "initialization_error"
    CONFIGURATION_ERROR = "configuration_error"


class TokenizerError(AIPerfError):
    """Base class for tokenizer exceptions."""

    def __init__(self, reason: TokenizerErrorReason, message: str) -> None:
        super().__init__(f"Tokenizer Error {reason.name}: {message}")
        self.reason = reason


################################################################################
# Inference Client Exceptions
################################################################################


class InferenceClientError(AIPerfError):
    """Exception raised when a inference client encounters an error."""


class InvalidPayloadError(InferenceClientError):
    """Exception raised when a inference client receives an invalid payload."""


################################################################################
# Hook Exceptions
################################################################################


class UnsupportedHookError(AIPerfError):
    """Exception raised when a hook is defined on a class that does not support it."""


################################################################################
# Factory Exceptions
################################################################################


class FactoryCreationError(AIPerfError):
    """Exception raised when a factory encounters an error while creating a class."""


################################################################################
# Metric Exceptions
################################################################################


class MetricTypeError(AIPerfError):
    """Exception raised when a metric type encounters an error while creating a class."""
