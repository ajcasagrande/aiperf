#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums._base import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum

class ServiceRunType(CaseInsensitiveStrEnum):
    MULTIPROCESSING = "process"
    KUBERNETES = "k8s"

class ServiceState(CaseInsensitiveStrEnum):
    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    PENDING = "pending"
    CONFIGURING = "configuring"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    SHUTDOWN = "shutdown"
    ERROR = "error"

class ServiceType(CaseInsensitiveStrEnum):
    SYSTEM_CONTROLLER = "system_controller"
    DATASET_MANAGER = "dataset_manager"
    TIMING_MANAGER = "timing_manager"
    RECORDS_MANAGER = "records_manager"
    INFERENCE_RESULT_PARSER = "inference_result_parser"
    WORKER_MANAGER = "worker_manager"
    WORKER = "worker"
    TEST = "test_service"

class ServiceRegistrationStatus(CaseInsensitiveStrEnum):
    UNREGISTERED = "unregistered"
    WAITING = "waiting"
    REGISTERED = "registered"
    TIMEOUT = "timeout"
    ERROR = "error"
