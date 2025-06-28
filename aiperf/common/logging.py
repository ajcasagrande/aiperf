# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
import multiprocessing
import os
import queue

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
) -> None:
    """Set up logging for a child process to send logs to the main process.

    This should be called early in child process initialization.

    Args:
        log_queue: The multiprocessing queue to send logs to. If None, tries to get the global queue.
    """
    if log_queue is None:
        log_queue = get_global_log_queue()

    if log_queue is None:
        return

    # Set up handler for child process
    handler = MultiProcessLogHandler(log_queue)
    handler.setLevel(os.getenv("AIPERF_LOG_LEVEL", "WARNING"))

    # Add to root logger to capture all logs from this process
    root_logger = logging.getLogger()

    # Remove existing handlers to avoid duplicate logs
    for existing_handler in root_logger.handlers[:]:
        if isinstance(existing_handler, MultiProcessLogHandler):
            root_logger.removeHandler(existing_handler)

    root_logger.addHandler(handler)


class MultiProcessLogHandler(logging.Handler):
    """Custom logging handler that forwards log records to a multiprocessing queue."""

    def __init__(self, log_queue: multiprocessing.Queue) -> None:
        super().__init__()
        self.log_queue = log_queue

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
            }
            self.log_queue.put_nowait(log_data)
        except queue.Full:
            # Drop logs if queue is full to prevent blocking
            pass
        except Exception:
            # Ignore errors to prevent logging from breaking the application
            pass
