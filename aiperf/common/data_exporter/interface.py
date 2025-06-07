# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Protocol

from aiperf.common.data_exporter.record import Record


# TODO: This can be moved to common interface file
class DataExporterInterface(Protocol):
    def export(self, record: list[Record]) -> None: ...
