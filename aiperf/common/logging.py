# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
import multiprocessing
import time
from pathlib import Path

import orjson
from rich.console import Console
from rich.logging import RichHandler

from aiperf.common.aiperf_logger import _DEBUG, _TRACE, AIPerfLogger
from aiperf.common.config import ServiceConfig, ServiceDefaults, UserConfig
from aiperf.common.config.config_defaults import OutputDefaults
from aiperf.common.constants import AIPERF_STRUCTURED_LOGGING
from aiperf.common.enums import ServiceType

_LOG_LEVEL_STYLES = {
    "TRACE": "dim",
    "DEBUG": "dim",
    "INFO": "cyan",
    "NOTICE": "blue",
    "WARNING": "yellow",
    "SUCCESS": "green",
    "ERROR": "red",
    "CRITICAL": "red",
}

_logger = AIPerfLogger(__name__)


def setup_logging(
    service_type: ServiceType,
    service_id: str | None = None,
    service_config: ServiceConfig | None = None,
    user_config: UserConfig | None = None,
) -> None:
    """Set up logging for a service.

    This should be called early in service initialization.

    Args:
        service_type: The type of the service to log under.
        service_id: The ID of the service to log under. If None, logs will be under the process name.
        service_config: The service configuration used to determine the log level.
        user_config: The user configuration used to determine the log folder.
    """
    root_logger = logging.getLogger()
    level = ServiceDefaults.LOG_LEVEL.upper()
    if service_config:
        level = service_config.log_level.upper()

        if service_id:
            # If the service is in the trace or debug services, set the level to trace or debug
            if (
                service_config.developer.trace_services
                and service_type in service_config.developer.trace_services
            ):
                level = _TRACE
            elif (
                service_config.developer.debug_services
                and service_type in service_config.developer.debug_services
            ):
                level = _DEBUG

    # Set the root logger level to ensure logs are passed to handlers
    root_logger.setLevel(level)

    # Remove all existing handlers to avoid duplicate logs
    for existing_handler in root_logger.handlers[:]:
        root_logger.removeHandler(existing_handler)

    if AIPERF_STRUCTURED_LOGGING:
        # Use structured format for subprocess output that will be parsed by parent process
        structured_handler = StructuredSubprocessLogHandler(service_id)
        structured_handler.setLevel(level)
        root_logger.addHandler(structured_handler)
    else:
        # For all other cases, set up rich logging to the console
        rich_handler = RichHandler(
            rich_tracebacks=True,
            show_path=True,
            console=Console(),
            show_time=True,
            show_level=True,
            tracebacks_show_locals=False,
            log_time_format="%H:%M:%S.%f",
            omit_repeated_times=False,
        )
        rich_handler.setLevel(level)
        root_logger.addHandler(rich_handler)

    if user_config and user_config.output.artifact_directory:
        file_handler = create_file_handler(
            user_config.output.artifact_directory / OutputDefaults.LOG_FOLDER, level
        )
        root_logger.addHandler(file_handler)


def create_file_handler(
    log_folder: Path,
    level: str | int,
) -> logging.FileHandler:
    """Configure a file handler for logging."""

    log_folder.mkdir(parents=True, exist_ok=True)
    log_file_path = log_folder / OutputDefaults.LOG_FILE

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    return file_handler


class StructuredSubprocessLogHandler(logging.Handler):
    """Custom logging handler that outputs structured JSON log format for subprocess parsing."""

    def __init__(self, service_id: str | None = None) -> None:
        super().__init__()
        self.service_id = service_id
        self.process_id = multiprocessing.current_process().pid
        self.process_name = multiprocessing.current_process().name

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record in structured JSON format using orjson."""
        try:
            log_data = {
                "created": record.created,
                "levelno": record.levelno,
                "levelname": record.levelname,
                "name": record.name,
                "process_name": self.process_name,
                "process_id": self.process_id,
                "service_id": self.service_id or "",
                "pathname": getattr(record, "pathname", ""),
                "lineno": getattr(record, "lineno", 0),
                "msg": record.getMessage(),
            }
            print(orjson.dumps(log_data).decode(), flush=True)
        except Exception:
            # Do not log to prevent recursion
            pass


def parse_subprocess_log_line(line: str) -> logging.LogRecord | None:
    """Parse a structured JSON log line from subprocess output.

    Args:
        line: The JSON log line to parse

    Returns:
        LogRecord with parsed log data or None if parsing fails
    """
    try:
        data = orjson.loads(line)
    except (orjson.JSONDecodeError, TypeError):
        return None

    # Create a LogRecord directly from parsed JSON data
    record = logging.LogRecord(
        name=data.get("name", ""),
        level=data.get("levelno", logging.INFO),
        pathname=data.get("pathname", ""),
        lineno=data.get("lineno", 0),
        msg=data.get("msg", ""),
        args=(),
        exc_info=None,
        func=None,
        sinfo=None,
    )

    # Set additional attributes from subprocess
    record.created = data.get("created", time.time())
    record.msecs = (record.created % 1) * 1000
    record.processName = data.get("process_name", "")
    record.process = data.get("process_id", 0)
    record.levelname = data.get("levelname", "INFO")

    # Store service_id as custom attribute
    record.service_id = data.get("service_id", "")

    return record


def handle_subprocess_log_line(line: str, fallback_service_id: str) -> None:
    """Handle a subprocess log line by parsing and forwarding to appropriate logger.

    This function handles both structured and unstructured log lines from subprocesses,
    parsing them and forwarding directly to the appropriate logger.

    Args:
        line: The log line from subprocess output
        fallback_service_id: Service ID to use if line is not structured
    """
    # Try structured parsing first
    parsed_record = parse_subprocess_log_line(line)

    if parsed_record:
        original_logger = logging.getLogger(parsed_record.name)
        if original_logger.isEnabledFor(parsed_record.levelno):
            original_logger.handle(parsed_record)
    else:
        fallback_logger = logging.getLogger(fallback_service_id)
        if fallback_logger.isEnabledFor(logging.WARNING):
            record = logging.LogRecord(
                name=fallback_service_id,
                level=logging.WARNING,
                pathname="<subprocess>",
                lineno=0,
                msg=line,
                args=(),
                exc_info=None,
                func=None,
                sinfo=None,
            )
            record.created = time.time()
            record.msecs = (record.created % 1) * 1000
            record.levelname = "WARNING"

            fallback_logger.handle(record)
