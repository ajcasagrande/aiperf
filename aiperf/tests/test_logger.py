# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.logging_mixins import AIPerfLogger


@pytest.mark.parametrize(
    "level", [AIPerfLogger.TRACE, AIPerfLogger.NOTICE, AIPerfLogger.SUCCESS]
)
def test_logger(level):
    logger = AIPerfLogger("test_logger")
    logger.log(level, lambda: "Hello, world!")


def test_logger_lazy_evaluation():
    logger = AIPerfLogger("test_logger")
    logger.info(lambda: "Hello, world!")
