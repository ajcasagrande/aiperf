# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import pluggy

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum
from aiperf.common.hookspecs import AIPerfSpecs


class AIPerfEntrypoint(CaseInsensitiveStrEnum):
    UI = "aiperf.ui"


class AIPerfPluginManager:
    def __init__(self):
        self.hookspec = AIPerfSpecs()
        self.hookimpl = pluggy.HookimplMarker("aiperf")
        self.pm = pluggy.PluginManager("aiperf")
        self.pm.add_hookspecs(self.hookspec)
        for entrypoint in AIPerfEntrypoint:
            self.pm.load_setuptools_entrypoints(entrypoint)

    def get_plugin(self, name: str) -> Any:
        return self.pm.get_plugin(name)
