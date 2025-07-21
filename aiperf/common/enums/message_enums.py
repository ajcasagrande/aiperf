# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum


class MessageType(CaseInsensitiveStrEnum):
    """The various types of messages that can be sent between services.

    The message type is used to determine what Pydantic model the message maps to,
    based on the message_type field in the message model.
    """

    Test = "test"
    """A test message."""

    Error = "error"
    """A generic error message."""

    ########################################
    # Service messages
    ########################################

    Registration = "registration"
    """A message sent by a service to register itself with the SystemController."""

    Heartbeat = "heartbeat"
    """A message sent by a service to the SystemController to indicate it is still running."""

    Status = "status"
    """A notification sent by a service to the SystemController to report its status."""

    ServiceError = "service_error"
    """A message sent by a service to the SystemController to report an error."""

    ServiceHealth = "service_health"
    """A message sent by a service to the SystemController to report its health."""

    ########################################
    # Worker messages
    ########################################

    WorkerHealth = "worker_health"
    """A message sent by a worker to the WorkerManager to report its health."""

    ########################################
    # Sweep messages
    ########################################

    SweepConfigure = "sweep_configure"
    """A message sent to configure a sweep run."""

    SweepBegin = "sweep_begin"
    """A message sent to indicate that a sweep has begun."""

    SweepProgress = "sweep_progress"
    """A message containing sweep run progress."""

    SweepEnd = "sweep_end"
    """A message sent to indicate that a sweep has ended."""

    SweepResults = "sweep_results"
    """A message containing sweep run results."""

    SweepError = "sweep_error"
    """A message containing an error from a sweep run."""

    ########################################
    # Profile messages
    ########################################

    ProfileProgress = "profile_progress"
    """A message containing profile run progress."""

    ProcessingStats = "processing_stats"
    """A message containing processing stats from the RecordsManager."""

    ProfileResults = "profile_results"
    """A message containing profile run results."""

    ProfileError = "profile_error"
    """A message containing an error from a profile run."""

    ########################################
    # Credit messages
    ########################################

    CreditDrop = "credit_drop"
    """A message sent by the Timing Manager service to allocate credits
    for a worker."""

    CreditReturn = "credit_return"
    """A message sent by the Worker services to return credits to the credit pool."""

    CreditPhaseStart = "credit_phase_start"
    """A message sent by the TimingManager to report that a phase has started."""

    CreditPhaseProgress = "credit_phase_progress"
    """A message sent by the TimingManager to report the progress of a credit phase."""

    CreditPhaseSendingComplete = "credit_phase_sending_complete"
    """A message sent by the TimingManager to report that a phase has completed sending (but not necessarily all credits have been returned)."""

    CreditPhaseComplete = "credit_phase_complete"
    """A message sent by the TimingManager to report that a phase has completed."""

    CreditsComplete = "credits_complete"
    """A message sent by the Timing Manager services to signify all requests have completed."""

    FirstByteReceived = "first_byte_received"
    """A message sent by a worker to the TimingManager to indicate that the first byte of a credit has been received.
    This can be used to track the latency of the credit, or to perform various synchronizations."""

    ########################################
    # Dataset messages
    ########################################

    DatasetConfiguredNotification = "dataset_configured_notification"
    """A notification sent to notify other services that the dataset has been configured."""

    DatasetTimingRequest = "dataset_timing_request"
    """A message sent by a service to request timing information from a dataset."""

    DatasetTimingResponse = "dataset_timing_response"
    """A message sent by a service to respond to a dataset timing request."""

    ConversationRequest = "conversation_request"
    """A message sent by one service to the DatasetManager to request a conversation."""

    ConversationResponse = "conversation_response"
    """A message sent by the DatasetManager to a service, containing the requested conversation data."""

    ConversationTurnRequest = "conversation_turn_request"
    """A message sent by one service to the DatasetManager to request a single turn from a conversation."""

    ConversationTurnResponse = "conversation_turn_response"
    """A message sent by the DatasetManager to a service, containing the requested turn data."""

    ########################################
    # Inference messages
    ########################################

    InferenceResults = "inference_results"
    """A message containing inference results from a worker."""

    ParsedInferenceResults = "parsed_inference_results"
    """A message containing parsed inference results from a post processor."""

    ########################################
    # Command messages
    ########################################

    Command = "command"
    """A message sent to request that a service perform an action."""

    CommandResponse = "command_response"
    """A message sent to respond to a command request."""

    ProcessRecords = "process_records"
    """A message sent to request that a service process records."""

    ProfileConfigure = "profile_configure"
    """A message sent to configure a profile run."""

    ProfileStart = "profile_start"
    """A message sent to start a profile run."""

    ProfileCancel = "profile_cancel"
    """A message sent to cancel a profile run."""

    ProfileStop = "profile_stop"
    """A message sent to stop a profile run."""

    Shutdown = "shutdown"
    """A message sent by the SystemController to a service to request that it shutdown."""

    StartWorkers = "start_workers"
    """A message sent from the WorkerManager to the SystemController to start workers."""

    StopWorkers = "stop_workers"
    """A message sent from the WorkerManager to the SystemController to stop workers."""
