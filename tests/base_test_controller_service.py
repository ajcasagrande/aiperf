# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Base test class for controller services.
"""

from tests.base_test_service import BaseTestService


class BaseTestControllerService(BaseTestService):
    """
    Base class for testing controller services.

    This extends BaseTestService with specific tests for controller service
    functionality such as command sending, service registration handling,
    and monitoring of component services.
    """

    pass
