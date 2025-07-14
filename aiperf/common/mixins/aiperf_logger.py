# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable

from aiperf.common import aiperf_logger
from aiperf.common.aiperf_logger import (
    _CRITICAL,
    _DEBUG,
    _ERROR,
    _INFO,
    _NOTICE,
    _SUCCESS,
    _TRACE,
    _WARNING,
    AIPerfLogger,
)

# Add this file to the ignored files to avoid this file from being the source of the log messages
aiperf_logger._ignored_files.append(__file__)


class AIPerfLoggerMixin:
    """Mixin to provide lazy evaluated logging for f-strings.

    This mixin provides a logger with lazy evaluation support for f-strings,
    and direct log functions for all standard logging levels.

    see :class:`AIPerfLogger` for more details.

    Usage:
        class MyClass(AIPerfLoggerMixin):
            def __init__(self):
                super().__init__()
                self.trace(lambda: f"Processing {item} of {count} ({item / count * 100}% complete)")
                self.info("Simple string message")
                self.debug(lambda i=i: f"Processing {i}")
                self.warning("Warning message: %s", "legacy support")
                self.exception(f"Error: {e}")
                self.success(lambda: f"Benchmark completed successfully after {time.time() - start_time} seconds")
    """

    def __init__(self, logger_name: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.logger = AIPerfLogger(logger_name or self.__class__.__name__)
        self._log = self.logger._log
        self.is_enabled_for = self.logger.is_enabled_for
        self.is_trace_enabled = self.logger.is_trace_enabled
        self.is_debug_enabled = self.logger.is_debug_enabled
        self.is_info_enabled = self.logger.is_info_enabled
        self.is_notice_enabled = self.logger.is_notice_enabled
        self.is_warning_enabled = self.logger.is_warning_enabled
        self.is_success_enabled = self.logger.is_success_enabled
        self.is_error_enabled = self.logger.is_error_enabled
        self.is_critical_enabled = self.logger.is_critical_enabled

    def log(
        self, level: int, message: str | Callable[..., str], *args, **kwargs
    ) -> None:
        """Log a message at a specified level with lazy evaluation."""
        if self.is_enabled_for(level):
            self._log(level, message, *args, **kwargs)

    def trace(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a trace message with lazy evaluation."""
        if self.is_trace_enabled():
            self._log(_TRACE, message, *args, **kwargs)

    def debug(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a debug message with lazy evaluation."""
        if self.is_debug_enabled():
            self._log(_DEBUG, message, *args, **kwargs)

    def info(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log an info message with lazy evaluation."""
        if self.is_info_enabled():
            self._log(_INFO, message, *args, **kwargs)

    def notice(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a notice message with lazy evaluation."""
        if self.is_notice_enabled():
            self._log(_NOTICE, message, *args, **kwargs)

    def warning(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a warning message with lazy evaluation."""
        if self.is_warning_enabled():
            self._log(_WARNING, message, *args, **kwargs)

    def success(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a success message with lazy evaluation."""
        if self.is_success_enabled():
            self._log(_SUCCESS, message, *args, **kwargs)

    def error(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log an error message with lazy evaluation."""
        if self.is_error_enabled():
            self._log(_ERROR, message, *args, **kwargs)

    def exception(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log an exception message with lazy evaluation."""
        if self.is_error_enabled():
            self._log(_ERROR, message, *args, exc_info=True, **kwargs)

    def critical(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a critical message with lazy evaluation."""
        if self.is_critical_enabled():
            self._log(_CRITICAL, message, *args, **kwargs)
