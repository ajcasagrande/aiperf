# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.logging_mixins import _NOTICE, _SUCCESS, _TRACE, AIPerfLogger


@pytest.mark.parametrize("level", [_TRACE, _NOTICE, _SUCCESS])
def test_logger(level):
    logger = AIPerfLogger("test_logger")
    logger.log(level, lambda: "Hello, world!")
    assert logger.is_enabled_for(level)


def test_logger_lazy_evaluation():
    logger = AIPerfLogger("test_logger")
    logger.info(lambda: "Hello, world!")
    assert logger.is_info_enabled()


def test_logger_is_enabled_for():
    logger = AIPerfLogger("test_logger")
    assert logger.is_enabled_for(_TRACE)
    assert logger.is_enabled_for(_NOTICE)
    assert logger.is_enabled_for(_SUCCESS)
