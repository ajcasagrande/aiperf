# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import io
import logging
import os
import traceback
from collections.abc import Callable
from inspect import currentframe
from types import MethodType

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

_ignored_files = [logging._srcfile, utils._srcfile, __file__]


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

    def __init__(self, logger_name: str):
        self.logger_name = logger_name
        self._logger = logging.getLogger(logger_name)

        # Cache the internal logging module's _log method
        self._internal_log = self._logger._log

        # Forward the internal findCaller method to our custom method
        self._logger.findCaller = self.find_caller

        # Python style method names
        self.is_enabled_for = self._logger.isEnabledFor
        self.set_level = self._logger.setLevel
        self.get_effective_level = self._logger.getEffectiveLevel

        # Individual level enabled checks
        self.is_trace_enabled = MethodType(self._logger.isEnabledFor, _TRACE)
        self.is_debug_enabled = MethodType(self._logger.isEnabledFor, _DEBUG)
        self.is_info_enabled = MethodType(self._logger.isEnabledFor, _INFO)
        self.is_notice_enabled = MethodType(self._logger.isEnabledFor, _NOTICE)
        self.is_warning_enabled = MethodType(self._logger.isEnabledFor, _WARNING)
        self.is_success_enabled = MethodType(self._logger.isEnabledFor, _SUCCESS)
        self.is_error_enabled = MethodType(self._logger.isEnabledFor, _ERROR)
        self.is_critical_enabled = MethodType(self._logger.isEnabledFor, _CRITICAL)

        # Legacy logging method compatibility / passthrough
        self.isEnabledFor = self._logger.isEnabledFor
        self.setLevel = self._logger.setLevel
        self.getEffectiveLevel = self._logger.getEffectiveLevel
        self.handlers = self._logger.handlers
        self.removeHandler = self._logger.removeHandler
        self.addHandler = self._logger.addHandler
        self.hasHandlers = self._logger.hasHandlers
        self.getChild = self._logger.getChild
        self.callHandlers = self._logger.callHandlers
        self.handle = self._logger.handle
        self.makeRecord = self._logger.makeRecord

    def _log(self, level: int, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if callable(msg):
            if args:
                self._internal_log(level, msg(*args), (), **kwargs)
            else:
                self._internal_log(level, msg(), (), **kwargs)
        else:
            self._internal_log(level, msg, args, **kwargs)

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
                _TRACE,
                _NOTICE,
                _SUCCESS,
                _DEBUG,
                _INFO,
                _WARNING,
                _ERROR,
                _CRITICAL,
            ]

    @classmethod
    def get_level_number(cls, level: int | str) -> int:
        """Get the numeric level for the given level."""
        if isinstance(level, str):
            return getattr(cls, level.upper())
        else:
            return level

    def find_caller(
        self, stack_info=False, stacklevel=1
    ) -> tuple[str, int, str, str | None]:
        """
        NOTE: This is a modified version of the findCaller method in the logging module.

        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.

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
            if filename in _ignored_files:
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

    def log(self, level: int, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.is_enabled_for(level):
            self._log(level, msg, args, **kwargs)

    def trace(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.is_enabled_for(_TRACE):
            self._log(_TRACE, msg, *args, **kwargs)

    def debug(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.is_enabled_for(_DEBUG):
            self._log(_DEBUG, msg, *args, **kwargs)

    def info(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.is_enabled_for(_INFO):
            self._log(_INFO, msg, *args, **kwargs)

    def notice(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.is_enabled_for(_NOTICE):
            self._log(_NOTICE, msg, *args, **kwargs)

    def warning(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.is_enabled_for(_WARNING):
            self._log(_WARNING, msg, *args, **kwargs)

    def success(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.is_enabled_for(_SUCCESS):
            self._log(_SUCCESS, msg, *args, **kwargs)

    def error(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.is_enabled_for(_ERROR):
            self._log(_ERROR, msg, *args, **kwargs)

    def exception(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.is_enabled_for(_ERROR):
            self._log(_ERROR, msg, *args, exc_info=True, **kwargs)

    def critical(self, msg: str | Callable[..., str], *args, **kwargs) -> None:
        if self.is_enabled_for(_CRITICAL):
            self._log(_CRITICAL, msg, *args, **kwargs)
