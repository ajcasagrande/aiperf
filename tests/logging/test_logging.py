# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.common.enums.service_enums import ServiceType
from aiperf.common.logging import _is_service_in_types, get_global_log_queue
from aiperf.module_loader import ensure_modules_loaded

ensure_modules_loaded()


class TestLogging:
    def test_global_log_queue_is_singleton(self) -> None:
        log_queue = get_global_log_queue()
        assert log_queue is not None
        for _ in range(10):
            assert log_queue == get_global_log_queue()

    @pytest.mark.parametrize(
        "service_id, service_types, expected",
        [
            ("system_controller", [ServiceType.SYSTEM_CONTROLLER], True),
            (
                "system_controller",
                [ServiceType.SYSTEM_CONTROLLER, ServiceType.DATASET_MANAGER],
                True,
            ),
            ("system_controller", [ServiceType.DATASET_MANAGER], False),
            ("worker_123456", [ServiceType.WORKER], True),
            ("worker_123456", [ServiceType.WORKER, ServiceType.WORKER_MANAGER], True),
            ("worker_123456", [ServiceType.WORKER_MANAGER], False),
            (
                "worker_manager_abcdef",
                [ServiceType.WORKER_MANAGER, ServiceType.DATASET_MANAGER],
                True,
            ),
            ("worker_manager_abcdef", [ServiceType.WORKER], False),
        ],
    )
    def test_is_service_in_types(self, service_id, service_types, expected) -> None:
        assert _is_service_in_types(service_id, service_types) == expected
