# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging.handlers
import multiprocessing
import queue
from functools import lru_cache
from pathlib import Path

from rich.logging import RichHandler

from aiperf.common.config.config_defaults import ServiceDefaults
from aiperf.common.config.service_config import ServiceConfig

LOG_QUEUE_MAXSIZE = 1000
DEFAULT_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB per log file
DEFAULT_LOG_BACKUP_COUNT = 10  # Keep 10 backup files (total ~50MB)
# TODO: Use config to determine the log folder based on artifacts directory.
DEFAULT_LOG_FOLDER = Path("artifacts/logs")


@lru_cache(maxsize=1)
def get_global_log_queue() -> multiprocessing.Queue:
    """Get the global log queue. Will create a new queue if it doesn't exist."""
    return multiprocessing.Queue(maxsize=LOG_QUEUE_MAXSIZE)


def setup_child_process_logging(
    log_queue: "multiprocessing.Queue | None" = None,
    service_id: str | None = None,
    service_config: ServiceConfig | None = None,
) -> None:
    """Set up logging for a child process to send logs to the main process.

    This should be called early in child process initialization.

    Args:
        log_queue: The multiprocessing queue to send logs to. If None, tries to get the global queue.
        service_id: The ID of the service to log under. If None, logs will be under the process name.
        service_config: The service configuration used to determine the log level.
    """
    if log_queue is None:
        log_queue = get_global_log_queue()

    root_logger = logging.getLogger()
    level = ServiceDefaults.LOG_LEVEL.upper()
    if service_config:
        level = service_config.log_level.upper()

        if service_id:
            for service_type in service_config.debug_services or set():
                # for cases of service_id being "worker_xxxxxx" and service_type being "worker",
                # we want to set the log level to debug
                if service_id.startswith(service_type.value):
                    level = logging.DEBUG
                    break

    # Set the root logger level to ensure logs are passed to handlers
    root_logger.setLevel(level)

    # Remove all existing handlers to avoid duplicate logs
    for existing_handler in root_logger.handlers[:]:
        root_logger.removeHandler(existing_handler)

    # Set up handler for child process
    queue_handler = MultiProcessLogHandler(log_queue, service_id)
    queue_handler.setLevel(level)
    root_logger.addHandler(queue_handler)

    file_handler = create_rolling_file_handler(level)
    root_logger.addHandler(file_handler)


def create_rolling_file_handler(
    level: str | int,
    max_bytes: int = DEFAULT_LOG_MAX_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> logging.handlers.RotatingFileHandler:
    """Configure a rolling file handler for logging."""

    # TODO: Use config to determine if file logging is enabled and the folder path.
    log_folder = DEFAULT_LOG_FOLDER
    log_folder.mkdir(parents=True, exist_ok=True)
    log_file_path = log_folder / "aiperf.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    return file_handler


class MultiProcessLogHandler(RichHandler):
    """Custom logging handler that forwards log records to a multiprocessing queue."""

    def __init__(
        self, log_queue: multiprocessing.Queue, service_id: str | None = None
    ) -> None:
        super().__init__()
        self.log_queue = log_queue
        self.service_id = service_id

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the queue."""
        try:
            # Create a serializable log data structure
            log_data = {
                "name": record.name,
                "levelname": record.levelname,
                "levelno": record.levelno,
                "msg": record.getMessage(),
                "created": record.created,
                "process_name": multiprocessing.current_process().name,
                "process_id": multiprocessing.current_process().pid,
                "service_id": self.service_id,
            }
            self.log_queue.put_nowait(log_data)
        except queue.Full:
            # Drop logs if queue is full to prevent blocking
            pass
        except Exception:
            # Do not log to prevent recursion
            pass
