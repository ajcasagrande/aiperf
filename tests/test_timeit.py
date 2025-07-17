#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import logging
import sys
import timeit

sys.path.append("/home/anthony/nvidia/projects/aiperf3/aiperf")

from aiperf.common.aiperf_logger import AIPerfLogger2

standard_logger = logging.getLogger("test")
aiperf_logger = AIPerfLogger2("test")


test_value = "test_value"
iterations = 1000000


def expensive_operation():
    return "test"


def standard_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(f"Processing item {test_value}")


def aiperf_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_block_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(f"Processing item {test_value}")


def aiperf_block_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_lazy_block_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(lambda: f"Processing item {test_value}")


def aiperf_lazy_block_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_lazy_eager_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(f"Processing item {test_value}")


def aiperf_lazy_eager_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_expensive_logging():
    standard_logger.info(f"Processing item {test_value}")


def aiperf_expensive_logging():
    aiperf_logger.info(f"Processing item {test_value}")


def standard_lazy_expensive_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(lambda: f"Processing item {test_value}")


def aiperf_lazy_expensive_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_lazy_eager_expensive_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(lambda: f"Processing item {test_value}")


def aiperf_lazy_eager_expensive_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_lazy_eager_expensive_block_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(lambda: f"Processing item {test_value}")


def aiperf_lazy_eager_expensive_block_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_lazy_eager_expensive_block_eager_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(f"Processing item {test_value}")


def aiperf_lazy_eager_expensive_block_eager_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_lazy_eager_expensive_block_eager_lazy_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(lambda: f"Processing item {test_value}")


def aiperf_lazy_eager_expensive_block_eager_lazy_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_lazy_eager_expensive_block_eager_lazy_lazy_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(lambda: f"Processing item {test_value}")


def aiperf_lazy_eager_expensive_block_eager_lazy_lazy_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_lazy_eager_expensive_block_eager_lazy_lazy_lazy_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(lambda: f"Processing item {test_value}")


def aiperf_lazy_eager_expensive_block_eager_lazy_lazy_lazy_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_lazy_eager_expensive_block_eager_lazy_lazy_lazy_lazy_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(lambda: f"Processing item {test_value}")


def aiperf_lazy_eager_expensive_block_eager_lazy_lazy_lazy_lazy_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_lazy_eager_expensive_block_eager_lazy_lazy_lazy_lazy_lazy_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(lambda: f"Processing item {test_value}")


def aiperf_lazy_eager_expensive_block_eager_lazy_lazy_lazy_lazy_lazy_logging():
    aiperf_logger.info(lambda: f"Processing item {test_value}")


def standard_lazy_eager_expensive_block_eager_lazy_lazy_lazy_lazy_lazy_lazy_logging():
    if standard_logger.isEnabledFor(logging.INFO):
        standard_logger.info(lambda: f"Processing item {test_value}")


if __name__ == "__main__":
    print("standard_logging", timeit.timeit(standard_logging, number=iterations))
    print("aiperf_logging", timeit.timeit(aiperf_logging, number=iterations))
    print(
        "standard_block_logging",
        timeit.timeit(standard_block_logging, number=iterations),
    )
    print(
        "aiperf_block_logging", timeit.timeit(aiperf_block_logging, number=iterations)
    )
    print(
        "standard_lazy_block_logging",
        timeit.timeit(standard_lazy_block_logging, number=iterations),
    )
    print(
        "aiperf_lazy_block_logging",
        timeit.timeit(aiperf_lazy_block_logging, number=iterations),
    )
    print(
        "standard_lazy_eager_logging",
        timeit.timeit(standard_lazy_eager_logging, number=iterations),
    )
    print(
        "aiperf_lazy_eager_logging",
        timeit.timeit(aiperf_lazy_eager_logging, number=iterations),
    )
    print(
        "standard_expensive_logging",
        timeit.timeit(standard_expensive_logging, number=iterations),
    )
    print(
        "aiperf_expensive_logging",
        timeit.timeit(aiperf_expensive_logging, number=iterations),
    )
    print(
        "standard_lazy_expensive_logging",
        timeit.timeit(standard_lazy_expensive_logging, number=iterations),
    )
    print(
        "aiperf_lazy_expensive_logging",
        timeit.timeit(aiperf_lazy_expensive_logging, number=iterations),
    )
    print(
        "standard_lazy_eager_expensive_logging",
        timeit.timeit(standard_lazy_eager_expensive_logging, number=iterations),
    )
    print(
        "aiperf_lazy_eager_expensive_logging",
        timeit.timeit(aiperf_lazy_eager_expensive_logging, number=iterations),
    )
