#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import logging
from unittest.mock import Mock, patch

import pytest

from aiperf.common.logging_mixins import AIPerfLogger, AIPerfLoggerMixin


class MockClass(AIPerfLoggerMixin):
    """Mock class for testing the mixin."""

    def __init__(self):
        super().__init__()


@pytest.fixture
def logger():
    """Create a logger instance for testing."""
    return AIPerfLogger("test_logger")


@pytest.fixture
def mock_class():
    """Create a mock class instance for testing the mixin."""
    return MockClass()


@pytest.fixture
def mock_logging_logger():
    """Mock the underlying logging.Logger."""
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        yield mock_logger


class TestAIPerfLogger:
    """Test cases for AIPerfLogger class."""

    def test_logger_initialization(self, logger):
        """Test that logger initializes correctly."""
        assert logger._logger.name == "test_logger"

    @pytest.mark.parametrize(
        "level,level_name",
        [
            (AIPerfLogger.TRACE, "TRACE"),
            (AIPerfLogger.DEBUG, "DEBUG"),
            (AIPerfLogger.NOTICE, "NOTICE"),
            (AIPerfLogger.SUCCESS, "SUCCESS"),
        ],
    )
    def test_custom_log_levels_valid(self, level, level_name):
        """Test that all custom log levels are defined."""
        AIPerfLogger("test")  # Initialize the logger
        assert AIPerfLogger.is_valid_level(level)
        assert logging._levelToName[level] == level_name

    @pytest.mark.parametrize(
        "message,args,expected_msg,expected_args",
        [
            # String messages
            ("Test message", (), "Test message", ()),
            # String messages with args
            (
                "Message %s %s",
                ("arg1", "arg2"),
                "Message %s %s",
                ("arg1", "arg2"),
            ),
            # Callable without args
            (lambda: "Dynamic message", (), "Dynamic message", ()),
            # Callable with args
            (
                lambda x, y: f"Message {x} {y}",
                ("arg1", "arg2"),
                "Message arg1 arg2",
                (),
            ),
        ],
    )
    def test_logging_when_enabled(
        self,
        mock_logging_logger,
        message,
        args,
        expected_msg,
        expected_args,
    ):
        """Test logging with different message types when level is enabled."""
        mock_logging_logger.isEnabledFor.return_value = True
        logger = AIPerfLogger("test")

        logger.log(AIPerfLogger.INFO, message, *args)

        mock_logging_logger.isEnabledFor.assert_called_once_with(AIPerfLogger.INFO)
        mock_logging_logger._log.assert_called_once_with(
            AIPerfLogger.INFO, expected_msg, args=expected_args
        )

    def test_callable_not_executed_when_disabled(self, mock_logging_logger):
        """Test that callable is not executed when level is disabled."""
        mock_logging_logger.isEnabledFor.return_value = False
        logger = AIPerfLogger("test")
        logger.set_level(AIPerfLogger.INFO)

        message_lambda = Mock(return_value="Dynamic message")
        logger.debug(message_lambda)

        mock_logging_logger.isEnabledFor.assert_called_once_with(AIPerfLogger.DEBUG)
        mock_logging_logger._log.assert_not_called()
        message_lambda.assert_not_called()

    @pytest.mark.parametrize(
        "method_name,level",
        [
            ("trace", AIPerfLogger.TRACE),
            ("debug", AIPerfLogger.DEBUG),
            ("notice", AIPerfLogger.NOTICE),
            ("info", AIPerfLogger.INFO),
            ("warning", AIPerfLogger.WARNING),
            ("error", AIPerfLogger.ERROR),
            ("critical", AIPerfLogger.CRITICAL),
            ("success", AIPerfLogger.SUCCESS),
        ],
    )
    def test_convenience_methods(self, mock_logging_logger, method_name, level):
        """Test that convenience methods delegate to log method correctly."""
        mock_logging_logger.isEnabledFor.return_value = True
        logger = AIPerfLogger("test")

        method = getattr(logger, method_name)
        method("Test message")

        mock_logging_logger.isEnabledFor.assert_called_once_with(level)
        mock_logging_logger._log.assert_called_once_with(level, "Test message", args=())

    def test_exception_logging(self, mock_logging_logger):
        """Test exception logging includes exc_info."""
        mock_logging_logger.isEnabledFor.return_value = True
        logger = AIPerfLogger("test")

        logger.exception("Error occurred")

        mock_logging_logger._log.assert_called_once_with(
            AIPerfLogger.ERROR, "Error occurred", args=(), exc_info=True
        )

    @pytest.mark.parametrize(
        "level,expected",
        [
            # Real levels
            ("TRACE", True),
            ("DEBUG", True),
            ("NOTICE", True),
            ("INFO", True),
            ("WARNING", True),
            ("ERROR", True),
            ("CRITICAL", True),
            ("SUCCESS", True),
            (AIPerfLogger.TRACE, True),
            (AIPerfLogger.NOTICE, True),
            (AIPerfLogger.SUCCESS, True),
            # Fake levels
            ("INVALID", False),
            (999, False),
        ],
    )
    def test_is_valid_level(self, level, expected):
        """Test level validation."""
        assert AIPerfLogger.is_valid_level(level) == expected

    def test_legacy_methods(self):
        """Test that legacy methods delegate to the logger."""
        logger = AIPerfLogger("test")
        logger.setLevel(AIPerfLogger.WARNING)
        assert logger.getEffectiveLevel() == AIPerfLogger.WARNING
        assert logger.isEnabledFor(AIPerfLogger.WARNING)


class TestAIPerfLoggerMixin:
    """Test cases for AIPerfLoggerMixin class."""

    def test_mixin_initialization(self, mock_class):
        """Test that mixin initializes correctly."""
        assert isinstance(mock_class.logger, AIPerfLogger)
        assert mock_class.logger._logger.name == "MockClass"

    @pytest.mark.parametrize(
        "method_name,level",
        [
            ("trace", AIPerfLogger.TRACE),
            ("debug", AIPerfLogger.DEBUG),
            ("notice", AIPerfLogger.NOTICE),
            ("info", AIPerfLogger.INFO),
            ("warning", AIPerfLogger.WARNING),
            ("error", AIPerfLogger.ERROR),
            ("critical", AIPerfLogger.CRITICAL),
            ("success", AIPerfLogger.SUCCESS),
        ],
    )
    def test_mixin_convenience_methods(self, mock_class, method_name, level):
        """Test that mixin convenience methods delegate to logger."""
        with patch.object(mock_class.logger, "log") as mock_log:
            method = getattr(mock_class, method_name)
            method("Test message", "arg1", kwarg1="value1")

            mock_log.assert_called_once_with(
                level, "Test message", "arg1", kwarg1="value1"
            )

    def test_mixin_log_method(self, mock_class):
        """Test that mixin log method delegates to logger."""
        with patch.object(mock_class.logger, "log") as mock_log:
            mock_class.log(AIPerfLogger.INFO, "Test message", "arg1", kwarg1="value1")

            mock_log.assert_called_once_with(
                AIPerfLogger.INFO, "Test message", "arg1", kwarg1="value1"
            )

    def test_mixin_with_lazy_evaluation(self, mock_class):
        """Test that mixin supports lazy evaluation."""
        with patch.object(mock_class.logger, "log") as mock_log:

            def message_lambda():
                return "Dynamic message"

            mock_class.info(message_lambda)

            mock_log.assert_called_once_with(AIPerfLogger.INFO, message_lambda)


class TestIntegration:
    """Integration tests for logger and mixin together."""

    @pytest.mark.parametrize(
        "method_name,level,should_be_logged",
        [
            ("info", AIPerfLogger.INFO, True),
            ("notice", AIPerfLogger.NOTICE, True),
            ("success", AIPerfLogger.SUCCESS, True),
            ("error", AIPerfLogger.ERROR, True),
            ("critical", AIPerfLogger.CRITICAL, True),
            ("exception", AIPerfLogger.ERROR, True),
        ],
    )
    def test_end_to_end_logging(self, caplog, method_name, level, should_be_logged):
        """Test end-to-end logging functionality."""
        caplog.set_level(level)

        mock_class = MockClass()
        method = getattr(mock_class, method_name)
        method("Test message")

        assert "Test message" in caplog.text

    def test_lazy_evaluation_performance(self, caplog):
        """Test that lazy evaluation prevents expensive operations."""
        caplog.set_level(logging.WARNING)

        mock_class = MockClass()
        expensive_operation_called = False

        def expensive_operation():
            nonlocal expensive_operation_called
            expensive_operation_called = True
            return "Expensive result"

        mock_class.debug(expensive_operation)

        assert not expensive_operation_called
        assert "Expensive result" not in caplog.text
