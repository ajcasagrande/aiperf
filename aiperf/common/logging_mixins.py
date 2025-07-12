# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import io
import logging
import os
import traceback
from collections.abc import Callable
from inspect import currentframe

from aiperf.common import utils

# Register custom log levels once at module import time
_TRACE = logging.DEBUG - 5
_DEBUG = logging.DEBUG
_INFO = logging.INFO
_NOTICE = logging.WARNING - 5
_WARNING = logging.WARNING
_SUCCESS = logging.WARNING + 1
_ERROR = logging.ERROR
_CRITICAL = logging.CRITICAL

logging.addLevelName(_TRACE, "TRACE")
logging.addLevelName(_NOTICE, "NOTICE")
logging.addLevelName(_SUCCESS, "SUCCESS")


class AIPerfLogger2:
    """Logger for AIPerf messages with lazy evaluation support for f-strings.

    This logger supports lazy evaluation of f-strings through lambdas to avoid
    expensive string formatting operations when the log level is not enabled.
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._internal_log = self.logger._log
        self.logger.findCaller = self.findCaller
        # Legacy logging method compatibility
        self.isEnabledFor = self.logger.isEnabledFor
        self.setLevel = self.logger.setLevel
        self.getEffectiveLevel = self.logger.getEffectiveLevel

    def _log(self, level: int, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if callable(msg):
            if args:
                self._internal_log(level, msg(*args), (), **kwargs)
            else:
                self._internal_log(level, msg(), (), **kwargs)
        else:
            self._internal_log(level, msg, args, **kwargs)

    def findCaller(
        self, stack_info=False, stacklevel=1
    ) -> tuple[str, int, str, str | None]:
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.

        This is a modified version of the findCaller method in the logging module.

        It is modified to skip the source file of the call_all_functions function
        and the current file, to find the actual caller.
        """
        f = currentframe()
        # On some versions of IronPython, currentframe() returns None if
        # IronPython isn't run with -X:Frames.
        if f is not None:
            f = f.f_back
        orig_f = f
        while f and stacklevel > 1:
            f = f.f_back
            stacklevel -= 1
        if not f:
            f = orig_f
        rv = "(unknown file)", 0, "(unknown function)", None
        while f and hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename in [logging._srcfile, utils._srcfile, __file__]:
                f = f.f_back
                continue
            sinfo = None
            if stack_info:
                sio = io.StringIO()
                sio.write("Stack (most recent call last):\n")
                traceback.print_stack(f, file=sio)
                sinfo = sio.getvalue()
                if sinfo[-1] == "\n":
                    sinfo = sinfo[:-1]
                sio.close()
            rv = (co.co_filename, f.f_lineno, co.co_name, sinfo)
            break
        return rv

    def trace(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.isEnabledFor(_TRACE):
            self._log(_TRACE, msg, *args, **kwargs)

    def debug(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.isEnabledFor(_DEBUG):
            self._log(_DEBUG, msg, *args, **kwargs)

    def info(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.isEnabledFor(_INFO):
            self._log(_INFO, msg, *args, **kwargs)

    def notice(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.isEnabledFor(_NOTICE):
            self._log(_NOTICE, msg, *args, **kwargs)

    def warning(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.isEnabledFor(_WARNING):
            self._log(_WARNING, msg, *args, **kwargs)

    def success(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.isEnabledFor(_SUCCESS):
            self._log(_SUCCESS, msg, *args, **kwargs)

    def error(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.isEnabledFor(_ERROR):
            self._log(_ERROR, msg, *args, **kwargs)

    def exception(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.isEnabledFor(_ERROR):
            self._log(_ERROR, msg, *args, exc_info=True, **kwargs)

    def critical(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.isEnabledFor(_CRITICAL):
            self._log(_CRITICAL, msg, *args, **kwargs)


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
        self.logger: AIPerfLogger2 = AIPerfLogger2(self.__class__.__name__)
        self._log = self.logger._log

    def log(
        self, level: int, message: str | Callable[..., str], *args, **kwargs
    ) -> None:
        """Log a message at a specified level with lazy evaluation."""
        if self.logger.isEnabledFor(level):
            self._log(level, message, *args, **kwargs)

    def trace(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a trace message with lazy evaluation."""
        if self.logger.isEnabledFor(_TRACE):
            self._log(_TRACE, message, *args, **kwargs)

    def debug(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a debug message with lazy evaluation."""
        if self.logger.isEnabledFor(_DEBUG):
            self._log(_DEBUG, message, *args, **kwargs)

    def info(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log an info message with lazy evaluation."""
        if self.logger.isEnabledFor(_INFO):
            self._log(_INFO, message, *args, **kwargs)

    def notice(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a notice message with lazy evaluation."""
        if self.logger.isEnabledFor(_NOTICE):
            self._log(_NOTICE, message, *args, **kwargs)

    def warning(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a warning message with lazy evaluation."""
        if self.logger.isEnabledFor(_WARNING):
            self._log(_WARNING, message, *args, **kwargs)

    def success(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a success message with lazy evaluation."""
        if self.logger.isEnabledFor(_SUCCESS):
            self._log(_SUCCESS, message, *args, **kwargs)

    def error(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log an error message with lazy evaluation."""
        if self.logger.isEnabledFor(_ERROR):
            self._log(_ERROR, message, *args, **kwargs)

    def exception(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log an exception message with lazy evaluation."""
        if self.logger.isEnabledFor(_ERROR):
            self._log(_ERROR, message, *args, exc_info=True, **kwargs)

    def critical(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a critical message with lazy evaluation."""
        if self.logger.isEnabledFor(_CRITICAL):
            self._log(_CRITICAL, message, *args, **kwargs)


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
        self._log = self._logger._log
        self._is_enabled_for = self._logger.isEnabledFor
        self.removeHandler = self._logger.removeHandler
        self.addHandler = self._logger.addHandler
        self.handlers = self._logger.handlers

    def log(
        self, level: int, message: str | Callable[..., str], *args, **kwargs
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
        if self._is_enabled_for(level):
            if callable(message):
                # Call the internal _log because we already checked if the level is enabled
                if args:
                    # Lazy evaluation of a message with arguments
                    self._log(level, message(*args), args=(), **kwargs)
                else:
                    # Lazy evaluation of the message without arguments
                    self._log(level, message(), args=(), **kwargs)
            else:
                # Direct string logging with % style formatting
                self._log(level, message, args=args or (), **kwargs)

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

    def trace(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a trace message with lazy evaluation."""
        self.log(self.TRACE, message, *args, **kwargs)

    def debug(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a debug message with lazy evaluation."""
        self.log(logging.DEBUG, message, *args, **kwargs)

    def notice(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a notice message with lazy evaluation."""
        self.log(self.NOTICE, message, *args, **kwargs)

    def info(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log an info message with lazy evaluation."""
        self.log(logging.INFO, message, *args, **kwargs)

    def warning(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a warning message with lazy evaluation."""
        self.log(logging.WARNING, message, *args, **kwargs)

    def error(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log an error message with lazy evaluation."""
        self.log(logging.ERROR, message, *args, **kwargs)

    def critical(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a critical message with lazy evaluation."""
        self.log(logging.CRITICAL, message, *args, **kwargs)

    def success(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log a success message with lazy evaluation."""
        self.log(self.SUCCESS, message, *args, **kwargs)

    def exception(self, message: str | Callable[..., str], *args, **kwargs) -> None:
        """Log an exception message with lazy evaluation."""
        self.log(logging.ERROR, message, *args, exc_info=True, **kwargs)

    # Legacy logging method compatibility
    isEnabledFor = is_enabled_for
    setLevel = set_level
    getEffectiveLevel = get_level
