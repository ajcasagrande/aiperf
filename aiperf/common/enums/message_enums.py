# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum


class MessageType(CaseInsensitiveStrEnum):
    """The various types of messages that can be sent between services.

    The message type is used to determine what Pydantic model the message maps to,
    based on the message_type field in the message model.
    """

    TEST = "test"
    """A test message."""

    ERROR = "error"
    """A generic error message."""

    ########################################
    # Service messages
    ########################################

    REGISTRATION = "registration"
    """A message sent by a service to register itself with the SystemController."""

    HEARTBEAT = "heartbeat"
    """A message sent by a service to the SystemController to indicate it is still running."""

    STATUS = "status"
    """A notification sent by a service to the SystemController to report its status."""

    SERVICE_ERROR = "service_error"
    """A message sent by a service to the SystemController to report an error."""

    SERVICE_HEALTH = "service_health"
    """A message sent by a service to the SystemController to report its health."""

    ########################################
    # Worker messages
    ########################################

    WORKER_HEALTH = "worker_health"
    """A message sent by a worker to the WorkerManager to report its health."""

    ########################################
    # Sweep messages
    ########################################

    SWEEP_CONFIGURE = "sweep_configure"
    """A message sent to configure a sweep run."""

    SWEEP_BEGIN = "sweep_begin"
    """A message sent to indicate that a sweep has begun."""

    SWEEP_PROGRESS = "sweep_progress"
    """A message containing sweep run progress."""

    SWEEP_END = "sweep_end"
    """A message sent to indicate that a sweep has ended."""

    SWEEP_RESULTS = "sweep_results"
    """A message containing sweep run results."""

    SWEEP_ERROR = "sweep_error"
    """A message containing an error from a sweep run."""

    ########################################
    # Profile messages
    ########################################

    PROFILE_PROGRESS = "profile_progress"
    """A message containing profile run progress."""

    PROCESSING_STATS = "processing_stats"
    """A message containing processing stats from the RecordsManager."""

    PROFILE_RESULTS = "profile_results"
    """A message containing profile run results."""

    PROFILE_ERROR = "profile_error"
    """A message containing an error from a profile run."""

    ########################################
    # Credit messages
    ########################################

    CREDIT_DROP = "credit_drop"
    """A message sent by the Timing Manager service to allocate credits
    for a worker."""

    CREDIT_RETURN = "credit_return"
    """A message sent by the Worker services to return credits to the credit pool."""

    CREDIT_PHASE_START = "credit_phase_start"
    """A message sent by the TimingManager to report that a phase has started."""

    CREDIT_PHASE_PROGRESS = "credit_phase_progress"
    """A message sent by the TimingManager to report the progress of a credit phase."""

    CREDIT_PHASE_SENDING_COMPLETE = "credit_phase_sending_complete"
    """A message sent by the TimingManager to report that a phase has completed sending (but not necessarily all credits have been returned)."""

    CREDIT_PHASE_COMPLETE = "credit_phase_complete"
    """A message sent by the TimingManager to report that a phase has completed."""

    CREDITS_COMPLETE = "credits_complete"
    """A message sent by the Timing Manager services to signify all requests have completed."""

    FIRST_BYTE_RECEIVED = "first_byte_received"
    """A message sent by a worker to the TimingManager to indicate that the first byte of a credit has been received.
    This can be used to track the latency of the credit, or to perform various synchronizations."""

    ########################################
    # Dataset messages
    ########################################

    DATASET_CONFIGURED_NOTIFICATION = "dataset_configured_notification"
    """A notification sent to notify other services that the dataset has been configured."""

    DATASET_TIMING_REQUEST = "dataset_timing_request"
    """A message sent by a service to request timing information from a dataset."""

    DATASET_TIMING_RESPONSE = "dataset_timing_response"
    """A message sent by a service to respond to a dataset timing request."""

    CONVERSATION_REQUEST = "conversation_request"
    """A message sent by one service to the DatasetManager to request a conversation."""

    CONVERSATION_RESPONSE = "conversation_response"
    """A message sent by the DatasetManager to a service, containing the requested conversation data."""

    CONVERSATION_TURN_REQUEST = "conversation_turn_request"
    """A message sent by one service to the DatasetManager to request a single turn from a conversation."""

    CONVERSATION_TURN_RESPONSE = "conversation_turn_response"
    """A message sent by the DatasetManager to a service, containing the requested turn data."""

    ########################################
    # Inference messages
    ########################################

    INFERENCE_RESULTS = "inference_results"
    """A message containing inference results from a worker."""

    PARSED_INFERENCE_RESULTS = "parsed_inference_results"
    """A message containing parsed inference results from a post processor."""

    ########################################
    # Worker Manager messages
    ########################################

    SPAWN_WORKERS = "spawn_workers"
    """A message sent by the WorkerManager to the SystemController to spawn workers."""

    SPAWN_WORKERS_RESPONSE = "spawn_workers_response"
    """A message sent by the SystemController to the WorkerManager to respond to a spawn workers request."""

    STOP_WORKERS = "stop_workers"
    """A message sent by the WorkerManager to the SystemController to stop workers."""

    STOP_WORKERS_RESPONSE = "stop_workers_response"
    """A message sent by the SystemController to the WorkerManager to respond to a stop workers request."""

    STOP_ALL_WORKERS = "stop_all_workers"
    """A message sent by the WorkerManager to the SystemController to stop all workers."""

    STOP_ALL_WORKERS_RESPONSE = "stop_all_workers_response"
    """A message sent by the SystemController to the WorkerManager to respond to a stop all workers request."""


class CommandType(CaseInsensitiveStrEnum):
    """The various types of command messages that can be sent between services."""

    PROCESS_RECORDS = "process_records"
    """A message sent to request that a service process records."""

    PROCESS_RECORDS_RESPONSE = "process_records_response"
    """A message sent to respond to a process records command."""

    PROFILE_CONFIGURE = "profile_configure"
    """A message sent to configure a profile run."""

    PROFILE_CONFIGURE_RESPONSE = "profile_configure_response"
    """A message sent to respond to a profile configure request."""

    PROFILE_START = "profile_start"
    """A message sent to start a profile run."""

    PROFILE_START_RESPONSE = "profile_start_response"
    """A message sent to respond to a profile start request."""

    PROFILE_CANCEL = "profile_cancel"
    """A message sent to cancel a profile run."""

    PROFILE_CANCEL_RESPONSE = "profile_cancel_response"
    """A message sent to respond to a profile cancel request."""

    PROFILE_STOP = "profile_stop"
    """A message sent to stop a profile run."""

    PROFILE_STOP_RESPONSE = "profile_stop_response"
    """A message sent to respond to a profile stop request."""

    SHUTDOWN = "shutdown"
    """A message sent by the SystemController to a service to request that it shutdown."""

    SHUTDOWN_RESPONSE = "shutdown_response"
    """A message sent by a service to the SystemController to respond to a shutdown request."""

    START_WORKERS = "start_workers"
    """A message sent from the WorkerManager to the SystemController to start workers."""

    START_WORKERS_RESPONSE = "start_workers_response"
    """A message sent to respond to a start workers request."""

    STOP_WORKERS = "stop_workers"
    """A message sent from the WorkerManager to the SystemController to stop workers."""

    STOP_WORKERS_RESPONSE = "stop_workers_response"
    """A message sent to respond to a stop workers request."""


def determine_message_type(value: object) -> MessageType | CommandType:
    try:
        return MessageType(value)
    except ValueError:
        return CommandType(value)
