# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from importlib.metadata import entry_points
from typing import Any

import pluggy

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum
from aiperf.common.hookspecs import AIPerfSpecs
from aiperf.common.plugin_metadata import AIPerfPluginMetadata
from aiperf.common.protocols import AIPerfUIProtocol

AIPERF_PROJECT_NAME = "aiperf"


class AIPerfPluginType(CaseInsensitiveStrEnum):
    UI = "aiperf.ui"


class PluginNotFoundError(RuntimeError):
    """Exception raised when a plugin is not found."""

    def __init__(self, kind: str, name: str) -> None:
        super().__init__(f"class not found: {kind}:{name}")


class PluginFactory:
    def __init__(self) -> None:
        self.pm = pluggy.PluginManager(AIPERF_PROJECT_NAME)
        self.pm.add_hookspecs(AIPerfSpecs)
        self._plugin_classes: dict[str, dict[str, type[Any]]] = {
            kind: {} for kind in AIPerfPluginType
        }
        self._register_all()

    def _register_all(self) -> None:
        for kind, ep_group in AIPerfPluginType:
            for ep in entry_points(group=ep_group):
                factory_func: Any = ep.load()
                plugin_cls: type[Any] = factory_func()
                name: str = plugin_cls.get_metadata()["name"]
                self._plugin_classes[kind][name] = plugin_cls
                self.pm.register(plugin_cls, name=f"{kind}:{name}")

    def list_plugins(self, kind: str) -> list[str]:
        return list(self._plugin_classes[kind].keys())

    def get_metadata(self, kind: str, name: str) -> AIPerfPluginMetadata:
        cls = self._plugin_classes[kind].get(name)
        if not cls:
            raise PluginNotFoundError(kind, name)
        return cls.get_metadata()

    def _create_instance(self, kind: str, name: str, **kwargs: Any) -> Any:
        cls = self._plugin_classes[kind].get(name)
        if not cls:
            raise PluginNotFoundError(kind, name)
        return cls(**kwargs)

    def create_ui(
        self, name: str, service_config: ServiceConfig, user_config: UserConfig
    ) -> AIPerfUIProtocol:
        """Create a new UI instance based on the given name."""
        return self._create_instance(
            AIPerfPluginType.UI,
            name,
            service_config=service_config,
            user_config=user_config,
        )
