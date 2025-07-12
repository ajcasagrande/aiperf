# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
from collections.abc import Callable
from typing import Any

# Register custom log levels once at module import time
_TRACE = logging.DEBUG - 5
_NOTICE = logging.WARNING - 5
_SUCCESS = logging.WARNING + 1

logging.addLevelName(_TRACE, "TRACE")
logging.addLevelName(_NOTICE, "NOTICE")
logging.addLevelName(_SUCCESS, "SUCCESS")


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
                self.warning("Warning message: %s", "legacy support")
                self.exception(lambda e=e: f"Error: {e}")
                self.success(lambda: f"Benchmark completed successfully after {time.time() - start_time} seconds")
    """

    def __init__(self):
        super().__init__()
        self.logger: AIPerfLogger = AIPerfLogger(self.__class__.__name__)

    def trace(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a trace message with lazy evaluation."""
        self.logger.log(AIPerfLogger.TRACE, message, *args, **kwargs)

    def debug(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a debug message with lazy evaluation."""
        self.logger.log(AIPerfLogger.DEBUG, message, *args, **kwargs)

    def notice(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a notice message with lazy evaluation."""
        self.logger.log(AIPerfLogger.NOTICE, message, *args, **kwargs)

    def info(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log an info message with lazy evaluation."""
        self.logger.log(AIPerfLogger.INFO, message, *args, **kwargs)

    def warning(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a warning message with lazy evaluation."""
        self.logger.log(AIPerfLogger.WARNING, message, *args, **kwargs)

    def error(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log an error message with lazy evaluation."""
        self.logger.log(AIPerfLogger.ERROR, message, *args, **kwargs)

    def critical(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a critical message with lazy evaluation."""
        self.logger.log(AIPerfLogger.CRITICAL, message, *args, **kwargs)

    def success(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a success message with lazy evaluation."""
        self.logger.log(AIPerfLogger.SUCCESS, message, *args, **kwargs)

    def exception(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log an exception message with lazy evaluation."""
        self.logger.log(AIPerfLogger.ERROR, message, *args, exc_info=True, **kwargs)

    def log(
        self, level: int, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a message at a specified level with lazy evaluation."""
        self.logger.log(level, message, *args, **kwargs)


class AIPerfLogger:
    """Logger for AIPerf messages with lazy evaluation support for f-strings.

    This logger supports lazy evaluation of f-strings through lambdas to avoid
    expensive string formatting operations when the log level is not enabled.

    It also extends the standard logging module with additional log levels:
        - TRACE    (lower than DEBUG)
        - NOTICE   (lower than WARNING)
        - SUCCESS  (around WARNING)

    Usage:
        logger = AIPerfLogger("my_logger")
        logger.debug(lambda: f"Processing {item} with {count} items")
        logger.info("Simple string message")

        # Need to pass local variables to the lambda to avoid them going out of scope
        logger.exception(lambda e=e: f"Error: {e}")
    """

    # Custom log levels
    TRACE = _TRACE
    NOTICE = _NOTICE
    SUCCESS = _SUCCESS
    # Standard logging levels
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def log(
        self, level: int, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a message at a specified level with lazy evaluation support.

        Args:
            level: Log level.
            message: Message string or lambda returning message string.
            *args: Additional arguments for string formatting, or closure variables.
            **kwargs: Additional keyword arguments to pass to the logger.
        """
        # NOTE: Use as much internal logging methods as possible to avoid
        # unnecessary overhead.
        if self._logger.isEnabledFor(level):
            if callable(message):
                # Call the internal _log because we already checked if the level is enabled
                if args:
                    # Lazy evaluation of a message with arguments
                    self._logger._log(level, message(*args), args=(), **kwargs)
                else:
                    # Lazy evaluation of the message without arguments
                    self._logger._log(level, message(), args=(), **kwargs)
            else:
                # Direct string logging with % style formatting
                self._logger._log(level, message, args=args or (), **kwargs)

    @classmethod
    def is_valid_level(cls, level: int | str) -> bool:
        """Check if the given level is a valid level."""
        if isinstance(level, str):
            return level in [
                "TRACE",
                "NOTICE",
                "SUCCESS",
                "DEBUG",
                "INFO",
                "WARNING",
                "ERROR",
                "CRITICAL",
            ]
        else:
            return level in [
                cls.TRACE,
                cls.NOTICE,
                cls.SUCCESS,
                cls.DEBUG,
                cls.INFO,
                cls.WARNING,
                cls.ERROR,
                cls.CRITICAL,
            ]

    @classmethod
    def get_level_number(cls, level: int | str) -> int:
        """Get the numeric level for the given level."""
        if isinstance(level, str):
            return getattr(cls, level.upper())
        else:
            return level

    def get_level(self) -> int:
        """Get the numeric level for the logger."""
        return self._logger.getEffectiveLevel()

    def set_level(self, level: int | str) -> None:
        """Set the logging level for the logger."""
        self._logger.setLevel(self.get_level_number(level))

    def is_enabled_for(self, level: int) -> bool:
        """Check if logging is enabled for the given level."""
        return self._logger.isEnabledFor(level)

    def is_trace_enabled(self) -> bool:
        """Check if trace logging is enabled."""
        return self._logger.isEnabledFor(self.TRACE)

    def is_debug_enabled(self) -> bool:
        """Check if debug logging is enabled."""
        return self._logger.isEnabledFor(logging.DEBUG)

    def trace(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a trace message with lazy evaluation."""
        self.log(self.TRACE, message, *args, **kwargs)

    def debug(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a debug message with lazy evaluation."""
        self.log(logging.DEBUG, message, *args, **kwargs)

    def notice(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a notice message with lazy evaluation."""
        self.log(self.NOTICE, message, *args, **kwargs)

    def info(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log an info message with lazy evaluation."""
        self.log(logging.INFO, message, *args, **kwargs)

    def warning(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a warning message with lazy evaluation."""
        self.log(logging.WARNING, message, *args, **kwargs)

    def error(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log an error message with lazy evaluation."""
        self.log(logging.ERROR, message, *args, **kwargs)

    def critical(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a critical message with lazy evaluation."""
        self.log(logging.CRITICAL, message, *args, **kwargs)

    def success(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log a success message with lazy evaluation."""
        self.log(self.SUCCESS, message, *args, **kwargs)

    def exception(
        self, message: str | Callable[..., str], *args: Any, **kwargs: Any
    ) -> None:
        """Log an exception message with lazy evaluation."""
        self.log(logging.ERROR, message, *args, exc_info=True, **kwargs)

    # Legacy logging method compatibility
    isEnabledFor = is_enabled_for
    setLevel = set_level
    getEffectiveLevel = get_level
