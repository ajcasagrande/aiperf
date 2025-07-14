#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import logging
import time
import timeit

import pytest

from aiperf.common.aiperf_logger import (
    _INFO,
    AIPerfLogger,
)
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums.timing import CreditPhase
from aiperf.common.record_models import RequestRecord, TextResponse


@pytest.fixture
def aiperf_logger():
    aiperf_logger = AIPerfLogger("test_aiperf_logger")
    aiperf_logger.set_level(_INFO)
    for handler in aiperf_logger.root.handlers[:]:
        aiperf_logger.root.removeHandler(handler)
    aiperf_logger.addHandler(logging.NullHandler())
    yield aiperf_logger


@pytest.fixture
def standard_logger():
    logger = logging.getLogger("test_standard_logger")
    logger.setLevel(_INFO)
    for handler in logger.root.handlers[:]:
        logger.root.removeHandler(handler)
    logger.addHandler(logging.NullHandler())
    yield logger


@pytest.fixture
def large_message():
    return RequestRecord(
        request={
            "id": "123",
            "url": "http://localhost:8080",
            "method": "GET",
            "headers": {
                "Content-Type": "application/json",
            },
        },
        timestamp_ns=time.time_ns(),
        start_perf_ns=time.perf_counter_ns(),
        end_perf_ns=time.perf_counter_ns() + (1_000_000_000 * 101),
        recv_start_perf_ns=time.perf_counter_ns() + 1_000_000_000,
        status=200,
        responses=[
            TextResponse(
                perf_ns=time.perf_counter_ns() + (i * 1_000_000_000),
                text="Hello, world!",
            )
            for i in range(1, 101)
        ],
        error=None,
        delayed_ns=None,
        credit_phase=CreditPhase.PROFILING,
    )


def compare_logger_performance(
    aiperf_logger_func,
    standard_logger_func,
    number=1_000,
    tries=3,
    min_speed_up=None,
    max_slow_down=None,
):
    aiperf_times = [
        timeit.timeit(aiperf_logger_func, number=number) for _ in range(tries)
    ]
    standard_times = [
        timeit.timeit(standard_logger_func, number=number) for _ in range(tries)
    ]

    aiperf_avg_time = sum(aiperf_times) / tries
    standard_avg_time = sum(standard_times) / tries
    slow_down = aiperf_avg_time / standard_avg_time
    speed_up = standard_avg_time / aiperf_avg_time
    func_name = aiperf_logger_func.__name__

    print(
        f"AIPerf logger time: {aiperf_avg_time:.5f} seconds (min: {min(aiperf_times):.5f}, max: {max(aiperf_times):.5f})"
    )
    print(
        f"Standard logger time: {standard_avg_time:.5f} seconds (min: {min(standard_times):.5f}, max: {max(standard_times):.5f})"
    )

    slow_down_msg = f"AIPerf logger is {slow_down:.2f}x slower than standard logger for {func_name} (expected at most {max_slow_down or 1 / (min_speed_up or 1):.2f}x)"
    speed_up_msg = f"AIPerf logger is {speed_up:.2f}x faster than standard logger for {func_name} (expected at least {min_speed_up or 1 / (max_slow_down or 1):.2f}x)"

    if slow_down > 1:
        print(slow_down_msg)
    else:
        print(speed_up_msg)

    if max_slow_down is not None:
        assert slow_down <= max_slow_down, slow_down_msg
    if min_speed_up is not None:
        assert speed_up >= min_speed_up, speed_up_msg


class TestAIPerfLogger:
    def test_aiperf_logger_with_lazy_evaluation_debug(
        self, aiperf_logger, standard_logger, capsys
    ):
        """
        Tests that the AIPerf logger is faster than the standard logger when lazy evaluation is used for
        f-string formatting when the log will NOT be printed.
        """

        def aiperf_lazy_evaluation():
            aiperf_logger.debug(lambda: f"Hello, world! {time.time_ns() ** 2}")

        def standard_f_string():
            standard_logger.debug(f"Hello, world! {time.time_ns() ** 2}")

        compare_logger_performance(
            aiperf_lazy_evaluation,
            standard_f_string,
            number=1_000,
            min_speed_up=1.5,
        )

    def test_plain_string_debug(self, aiperf_logger, standard_logger, capsys):
        """
        Tests that the AIPerf logger is not a lot slower than the standard logger when a plain string is used for
        logging both with and without lazy evaluation when the log will NOT be printed.
        """

        def aiperf_plain_string():
            aiperf_logger.debug(
                "Hello, world! This is a test of an example message that will NOT be printed."
            )

        def aiperf_plain_string_lazy():
            aiperf_logger.debug(
                lambda: "Hello, world! This is a test of an example message that will NOT be printed."
            )

        def standard_plain_string():
            standard_logger.debug(
                "Hello, world! This is a test of an example message that will NOT be printed."
            )

        compare_logger_performance(
            aiperf_plain_string,
            standard_plain_string,
            number=1_000,
            max_slow_down=1.5,
        )

        compare_logger_performance(
            aiperf_plain_string_lazy,
            standard_plain_string,
            number=1_000,
            max_slow_down=1.5,
        )

    def test_plain_string_info(self, aiperf_logger, standard_logger, capsys):
        """
        Tests that the AIPerf logger is not a lot slower than the standard logger when a plain string is used for
        logging both with and without lazy evaluation when the log will be printed.
        """

        def aiperf_plain_string():
            aiperf_logger.info(
                "Hello, world! This is a test of an example message that will be printed."
            )

        def aiperf_plain_string_lazy():
            aiperf_logger.info(
                lambda: "Hello, world! This is a test of an example message that will be printed."
            )

        def standard_plain_string():
            standard_logger.info(
                "Hello, world! This is a test of an example message that will be printed."
            )

        compare_logger_performance(
            aiperf_plain_string,
            standard_plain_string,
            number=1_000,
            max_slow_down=1.5,
        )

        compare_logger_performance(
            aiperf_plain_string_lazy,
            standard_plain_string,
            number=1_000,
            max_slow_down=1.5,
        )

    def test_formatting_info(self, aiperf_logger, standard_logger, capsys):
        """
        Tests that the AIPerf logger is not a lot slower than the standard logger when the message is formatted
        using %s and will be printed.
        """

        def aiperf_formatting():
            aiperf_logger.info(
                "Hello, world! This will be printed %s " * 100, *["test"] * 100
            )

        def standard_formatting():
            standard_logger.info(
                "Hello, world! This will be printed %s" * 100, *["test"] * 100
            )

        compare_logger_performance(
            aiperf_formatting,
            standard_formatting,
            number=1_000,
            max_slow_down=1.5,
        )

    def test_lazy_evaluation_and_formatting_debug(
        self, aiperf_logger, standard_logger, capsys
    ):
        """
        Tests that the AIPerf logger is faster than the standard logger when lazy evaluation is used for
        lazy %s formatting when the log will NOT be printed.
        """

        def aiperf_formatting_and_lazy_evaluation():
            aiperf_logger.debug(
                lambda: "Hello, world! This will NOT be printed %s "
                * 100
                % tuple([*["test"] * 100])
            )

        def standard_formatting_and_lazy_evaluation():
            standard_logger.debug(
                "Hello, world! This will NOT be printed %s " * 100, *["test"] * 100
            )

        compare_logger_performance(
            aiperf_formatting_and_lazy_evaluation,
            standard_formatting_and_lazy_evaluation,
            number=1_000,
            min_speed_up=2,
        )

    def test_lazy_evaluation_and_formatting_and_multiple_args_debug(
        self, aiperf_logger, standard_logger, capsys
    ):
        """
        Tests that the AIPerf logger is not a lot slower than the standard logger when the message is formatted
        using %s and will NOT be printed.
        """

        def aiperf_multiple_args():
            aiperf_logger.debug(
                lambda: f"Hello Mr {time.time_ns() ** 2} {time.time_ns() ** 2} This will NOT be printed"
            )

        def standard_multiple_args():
            standard_logger.debug(
                "Hello Mr %d %d This will NOT be printed",
                time.time_ns() ** 2,
                time.time_ns() ** 2,
            )

        compare_logger_performance(
            aiperf_multiple_args,
            standard_multiple_args,
            number=1_000,
            min_speed_up=2,
        )

    def test_message_formatting_info(self, aiperf_logger, standard_logger, capsys):
        """
        Tests that the AIPerf logger is not a lot slower than the standard logger when the message is formatted
        using %s and will be printed.
        """

        def aiperf_message_formatting():
            aiperf_logger.info(
                "Hello, world! This will be printed %s" * 100, *["test"] * 100
            )

        def standard_message_formatting():
            standard_logger.info(
                "Hello, world! This will be printed %s" * 100, *["test"] * 100
            )

        compare_logger_performance(
            aiperf_message_formatting,
            standard_message_formatting,
            number=1_000,
            max_slow_down=1.5,
        )

    def test_large_messages_debug(
        self, aiperf_logger, standard_logger, large_message, capsys
    ):
        """
        Tests that the AIPerf logger is faster than the standard logger when lazy evaluation is used for
        f-string formatting large messages when the log will NOT be printed.
        """

        def aiperf_f_string_message():
            aiperf_logger.debug(lambda: f"Got message: {large_message}")

        def standard_f_string_message():
            standard_logger.debug(f"Got message: {large_message}")

        def standard_fmt_message():
            standard_logger.debug("Got message: %s", large_message)

        # Should be incredibly fast
        compare_logger_performance(
            aiperf_f_string_message,
            standard_f_string_message,
            number=1_000,
            min_speed_up=10,
        )

        # Should be slower than %s, but not more than 1.5x
        compare_logger_performance(
            aiperf_f_string_message,
            standard_fmt_message,
            number=1_000,
            max_slow_down=1.5,
        )

    def test_large_messages_debug_math(
        self, aiperf_logger, standard_logger, large_message, capsys
    ):
        """
        Tests that the AIPerf logger is faster than the standard logger when lazy evaluation is used for simple math
        when the log will NOT be printed.
        """

        def aiperf_f_string_math():
            aiperf_logger.debug(
                lambda: f"Request time: {(large_message.end_perf_ns - large_message.start_perf_ns) / NANOS_PER_SECOND:.2f}"
            )

        def standard_f_string_math():
            standard_logger.debug(
                f"Request time: {(large_message.end_perf_ns - large_message.start_perf_ns) / NANOS_PER_SECOND:.2f}"
            )

        def standard_fmt_math():
            standard_logger.debug(
                "Request time: %.2f",
                (large_message.end_perf_ns - large_message.start_perf_ns)
                / NANOS_PER_SECOND,
            )

        # Should be decently faster
        compare_logger_performance(
            aiperf_f_string_math,
            standard_f_string_math,
            number=1_000,
            min_speed_up=1.5,
        )

        # Tests actually show this as being faster for AIPerf logger
        compare_logger_performance(
            aiperf_f_string_math,
            standard_fmt_math,
            number=1_000,
            max_slow_down=1.5,
        )
