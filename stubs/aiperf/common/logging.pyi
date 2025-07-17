#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import logging
import multiprocessing
from pathlib import Path

from _typeshed import Incomplete
from rich.logging import RichHandler

from aiperf.common.aiperf_logger import AIPerfLogger as AIPerfLogger
from aiperf.common.config._defaults import ServiceDefaults as ServiceDefaults
from aiperf.common.config._service import ServiceConfig as ServiceConfig
from aiperf.common.config._user import UserConfig as UserConfig
from aiperf.common.enums import ServiceType as ServiceType

LOG_QUEUE_MAXSIZE: int
logger: Incomplete

def get_global_log_queue() -> multiprocessing.Queue: ...
def setup_child_process_logging(
    log_queue: multiprocessing.Queue | None = None,
    service_id: str | None = None,
    service_config: ServiceConfig | None = None,
    user_config: UserConfig | None = None,
) -> None: ...
def setup_rich_logging(
    user_config: UserConfig, service_config: ServiceConfig
) -> None: ...
def create_file_handler(log_folder: Path, level: str | int) -> logging.FileHandler: ...

class MultiProcessLogHandler(RichHandler):
    log_queue: Incomplete
    service_id: Incomplete
    def __init__(
        self, log_queue: multiprocessing.Queue, service_id: str | None = None
    ) -> None: ...
    def emit(self, record: logging.LogRecord) -> None: ...
