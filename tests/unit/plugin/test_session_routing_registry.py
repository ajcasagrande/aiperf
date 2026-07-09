# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest
from pytest import param

from aiperf.plugin import plugins
from aiperf.plugin.enums import PluginType
from aiperf.workers.session_routing import SessionRoutingPreset

_PRESET_NAMES = [
    "dynamo_headers",
    "dynamo_nvext",
    "smg_routing_key",
    "session_id_header",
    "sglang_session",
    "url_index_header",
    "claude_code_headers",
    "custom",
]


@pytest.mark.parametrize(
    "name",
    [param(name, id=name) for name in _PRESET_NAMES],
)  # fmt: skip
def test_session_routing_presets_resolve(name):
    cls = plugins.get_class(PluginType.SESSION_ROUTING, name)
    assert issubclass(cls, SessionRoutingPreset)


def test_registry_lists_exactly_the_eight_presets():
    names = [e.name for e in plugins.list_entries(PluginType.SESSION_ROUTING)]
    assert names == _PRESET_NAMES


def test_session_routing_enum_generated():
    from aiperf.plugin.enums import SessionRoutingType

    assert SessionRoutingType.DYNAMO_HEADERS == "dynamo_headers"
    assert SessionRoutingType.CLAUDE_CODE_HEADERS == "claude_code_headers"
    assert SessionRoutingType.CUSTOM == "custom"
    assert not hasattr(SessionRoutingType, "IDENTITY_HEADERS")
