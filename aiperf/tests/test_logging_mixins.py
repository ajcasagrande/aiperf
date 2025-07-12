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


class TestPerformance:
    """Performance tests comparing AIPerfLogger vs standard logger."""

    @pytest.fixture
    def standard_logger(self):
        """Create a standard logger for comparison."""
        return logging.getLogger("test_standard")

    @pytest.fixture
    def aiperf_logger(self):
        """Create an AIPerfLogger for comparison."""
        return AIPerfLogger("test_aiperf")

    def test_performance_enabled_logging(self, standard_logger, aiperf_logger):
        """Test performance when logging is enabled."""
        import timeit

        # Set both loggers to INFO level
        standard_logger.setLevel(logging.INFO)
        aiperf_logger.set_level(logging.INFO)

        # Test data
        test_value = "test_value"
        iterations = 1000000

        # Test standard logger with % formatting
        def standard_logging():
            standard_logger.info("Processing item %s", test_value)

        # Test AIPerfLogger with % formatting
        def aiperf_logging():
            aiperf_logger.info("Processing item %s", test_value)

        # Test AIPerfLogger with lambda (should be slower when enabled)
        def aiperf_lazy_logging():
            aiperf_logger.info(lambda: f"Processing item {test_value}")

        def standard_block_logging():
            if standard_logger.isEnabledFor(logging.INFO):
                standard_logger.info(f"Processing item {test_value}")

        def aiperf_block_logging():
            aiperf_logger.info(lambda: f"Processing item {test_value}")

        # Measure performance
        standard_time = timeit.timeit(standard_logging, number=iterations)
        aiperf_time = timeit.timeit(aiperf_logging, number=iterations)
        aiperf_lazy_time = timeit.timeit(aiperf_lazy_logging, number=iterations)
        standard_block_time = timeit.timeit(standard_block_logging, number=iterations)
        aiperf_block_time = timeit.timeit(aiperf_block_logging, number=iterations)

        print(f"Standard logger time: {standard_time:.2f}s")
        print(f"AIPerfLogger time: {aiperf_time:.2f}s")
        print(f"AIPerfLogger lazy time: {aiperf_lazy_time:.2f}s")
        print(f"Standard block time: {standard_block_time:.2f}s")
        print(f"AIPerfLogger block time: {aiperf_block_time:.2f}s")

        # AIPerfLogger should be close to standard logger for % formatting
        overhead_ratio = aiperf_time / standard_time
        assert overhead_ratio < 2.0, (
            f"AIPerfLogger too slow: {overhead_ratio:.2f}x overhead"
        )

        # Lambda should be slower when enabled but not excessively
        lazy_overhead_ratio = aiperf_lazy_time / standard_time
        assert lazy_overhead_ratio < 5.0, (
            f"Lambda logging too slow: {lazy_overhead_ratio:.2f}x overhead"
        )

    def test_performance_disabled_logging(self):
        """Test performance when logging is disabled - lazy evaluation should shine."""
        import timeit

        standard_logger = logging.getLogger("standard_logger")
        aiperf_logger = AIPerfLogger("aiperf_logger")

        # Set both loggers to WARNING level (disabling INFO)
        standard_logger.setLevel(logging.WARNING)
        standard_logger.root.handlers = []
        for handler in standard_logger.handlers[:]:
            standard_logger.removeHandler(handler)

        aiperf_logger.set_level(logging.WARNING)
        aiperf_logger._logger.root.handlers = []
        for handler in aiperf_logger.handlers[:]:
            aiperf_logger.removeHandler(handler)

        # standard_logger.addHandler(logging.StreamHandler(sys.de))
        # aiperf_logger.addHandler(logging.StreamHandler(sys.stderr))

        # Test data
        test_value = "test_value"
        iterations = 10000

        # Test standard logger with % formatting
        def standard_logging():
            standard_logger.info("Processing item %s", test_value)

        # Test AIPerfLogger with % formatting
        def aiperf_logging():
            aiperf_logger.info("Processing item %s", test_value)

        # Test AIPerfLogger with lambda (should be fastest when disabled)
        def aiperf_lazy_logging():
            aiperf_logger.info(lambda: f"Processing item {test_value * 1000}")

        # Test expensive operation that should be skipped
        def expensive_operation():
            # Simulate expensive string formatting
            return "".join(
                [f"Processing item {test_value} {' ' * 1000}" for _ in range(10)]
            )

        def aiperf_expensive_lazy():
            aiperf_logger.info(lambda: expensive_operation())

        def aiperf_expensive_eager():
            aiperf_logger.info(expensive_operation())

        def standard_expensive_logging():
            standard_logger.info(
                "Processing item %s",
                " ".join(
                    [f"Processing item {test_value} {' ' * 1000}" for _ in range(10)]
                ),
            )

        def standard_lazy_logging():
            standard_logger.info(
                lambda: " ".join(
                    [f"Processing item {test_value} {' ' * 1000}" for _ in range(10)]
                )
            )

        def standard_lazy_eager_logging():
            standard_logger.warning(
                lambda: " ".join(
                    [f"Processing item {test_value} {' ' * 1000}" for _ in range(1000)]
                )
            )

        # Measure performance
        standard_time = timeit.timeit(standard_logging, number=iterations)
        aiperf_time = timeit.timeit(aiperf_logging, number=iterations)
        aiperf_lazy_time = timeit.timeit(aiperf_lazy_logging, number=iterations)
        aiperf_expensive_time = timeit.timeit(aiperf_expensive_lazy, number=iterations)
        aiperf_expensive_eager_time = timeit.timeit(
            aiperf_expensive_eager, number=iterations
        )
        standard_expensive_time = timeit.timeit(
            standard_expensive_logging, number=iterations
        )
        standard_lazy_time = timeit.timeit(standard_lazy_logging, number=iterations)
        standard_lazy_eager_time = timeit.timeit(
            standard_lazy_eager_logging, number=iterations
        )
        print(f"Standard logger time: {standard_time:.2f}s")
        print(f"AIPerfLogger time: {aiperf_time:.2f}s")
        print(f"AIPerfLogger lazy time: {aiperf_lazy_time:.2f}s")
        print(f"AIPerfLogger expensive time: {aiperf_expensive_time:.2f}s")
        print(f"AIPerfLogger expensive eager time: {aiperf_expensive_eager_time:.2f}s")
        print(f"Standard expensive time: {standard_expensive_time:.2f}s")
        print(f"Standard lazy time: {standard_lazy_time:.2f}s")
        print(f"Standard lazy eager time: {standard_lazy_eager_time:.2f}s")
        # Expensive operation should be skipped (very fast)
        expensive_ratio = aiperf_expensive_time / standard_time
        print(f"Expensive lambda not skipped: {expensive_ratio:.2f}x")
        assert expensive_ratio < 4.0, (
            f"Expensive lambda not skipped: {expensive_ratio:.2f}x"
        )
        assert aiperf_expensive_eager_time < aiperf_expensive_time, (
            "Eager evaluation should be faster than lazy evaluation"
        )

    def test_lazy_evaluation_benefit(self, aiperf_logger):
        """Test that lazy evaluation provides significant benefit for expensive operations."""
        import timeit

        # Test with logging disabled
        aiperf_logger.set_level(logging.WARNING)
        iterations = 1000

        # Expensive operation
        def expensive_operation():
            return "expensive " * 1000 + str(sum(range(100)))

        # Test lazy evaluation (should be fast)
        def lazy_logging():
            aiperf_logger.info(lambda: expensive_operation())

        # Test eager evaluation (should be slow)
        def eager_logging():
            aiperf_logger.info(expensive_operation())

        lazy_time = timeit.timeit(lazy_logging, number=iterations)
        eager_time = timeit.timeit(eager_logging, number=iterations)

        # Lazy should be significantly faster when logging is disabled
        speedup = eager_time / lazy_time
        assert speedup > 2.0, (
            f"Lazy evaluation benefit too small: {speedup:.2f}x speedup"
        )
