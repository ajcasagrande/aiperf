# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
import multiprocessing
import queue
from pathlib import Path

from rich.logging import RichHandler

from aiperf.common.config.config_defaults import ServiceDefaults
from aiperf.common.config.service_config import ServiceConfig

# Global log queue for multiprocessing
_GLOBAL_LOG_QUEUE: "multiprocessing.Queue | None" = None


def setup_global_log_queue() -> multiprocessing.Queue:
    """Set up a global log queue that can be used by all processes.

    Returns:
        The global multiprocessing queue for logging.
    """
    global _GLOBAL_LOG_QUEUE
    if _GLOBAL_LOG_QUEUE is None:
        _GLOBAL_LOG_QUEUE = multiprocessing.Queue(maxsize=1000)
    return _GLOBAL_LOG_QUEUE


def get_global_log_queue() -> "multiprocessing.Queue | None":
    """Get the global log queue if it exists.

    Returns:
        The global log queue or None if not set up.
    """
    return _GLOBAL_LOG_QUEUE


def setup_child_process_logging(
    log_queue: "multiprocessing.Queue | None" = None,
    service_id: str | None = None,
    service_config: "ServiceConfig | None" = None,
) -> None:
    """Set up logging for a child process to send logs to the main process.

    This should be called early in child process initialization.

    Args:
        log_queue: The multiprocessing queue to send logs to. If None, tries to get the global queue.
        service_id: The ID of the service to log under. If None, logs will be under the process name.
        service_config: The service configuration to log under. If None, logs will be under the process name.
    """
    if log_queue is None:
        log_queue = get_global_log_queue()

    if log_queue is None:
        return

    root_logger = logging.getLogger()
    level = (
        service_config.log_level.upper()
        if service_config
        else ServiceDefaults.LOG_LEVEL.upper()
    )
    # Set the root logger level to ensure logs are passed to handlers
    root_logger.setLevel(level)

    # Remove all existing handlers to avoid duplicate logs
    for existing_handler in root_logger.handlers[:]:
        root_logger.removeHandler(existing_handler)

    # Set up handler for child process
    queue_handler = MultiProcessLogHandler(log_queue, service_id)
    queue_handler.setLevel(level)
    root_logger.addHandler(queue_handler)

    # Enable file logging for services
    # TODO: Use config to determine if file logging is enabled and the folder path.
    log_folder = Path("artifacts/logs")
    log_folder.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_folder / "aiperf.log")
    file_handler.setLevel(level)
    file_handler.formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root_logger.addHandler(file_handler)


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
            # Ignore errors to prevent logging from breaking the application
            pass
