# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""DispatchFacts.turn_extra_headers construction at the InferenceClient chokepoint.

The facts must expose the dispatch turn's dataset-authored ``extra_headers`` as a
read-only ``MappingProxyType`` view: the underlying dict is a shared dataset
object under recycling, so a source or emitter must never be able to mutate it
through the facts object.
"""

from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest import param

from aiperf.common.enums import CreditPhase, ModelSelectionStrategy
from aiperf.common.models.dataset_models import Text, Turn
from aiperf.common.models.model_endpoint_info import (
    EndpointInfo,
    ModelEndpointInfo,
    ModelInfo,
    ModelListInfo,
)
from aiperf.common.models.record_models import RequestInfo, RequestRecord
from aiperf.plugin import plugins
from aiperf.plugin.enums import EndpointType, TransportType
from aiperf.workers.inference_client import InferenceClient
from aiperf.workers.session_routing import PlanEntry


@pytest.fixture
def mock_http_transport_entry():
    entry = MagicMock()
    entry.name = TransportType.HTTP.value
    entry.metadata = {"url_schemes": ["http", "https"]}
    return entry


def _build_client(mock_http_transport_entry) -> InferenceClient:
    """InferenceClient with a real header-emitting routing plan; endpoint and
    transport plugins mocked, session_routing resolved through the real registry."""
    model_endpoint = ModelEndpointInfo(
        models=ModelListInfo(
            models=[ModelInfo(name="test-model")],
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        ),
        endpoint=EndpointInfo(
            type=EndpointType.CHAT,
            base_url="http://localhost:8000/v1/test",
            session_routing_plan=[PlanEntry(preset="dynamo_headers")],
        ),
    )
    mock_transport = MagicMock()
    mock_endpoint = MagicMock()
    mock_endpoint.get_endpoint_headers.return_value = {}
    mock_endpoint.get_endpoint_params.return_value = {}
    mock_endpoint.format_payload.return_value = {
        "model": "test-model",
        "messages": [{"role": "user", "content": "hello"}],
    }

    real_get_class = plugins.get_class

    def mock_get_class(protocol, name):
        if protocol == "endpoint":
            return lambda **kwargs: mock_endpoint
        if protocol == "transport":
            return lambda **kwargs: mock_transport
        return real_get_class(protocol, name)

    with (
        patch(
            "aiperf.workers.inference_client.plugins.get_class",
            side_effect=mock_get_class,
        ),
        patch(
            "aiperf.workers.inference_client.plugins.list_entries",
            return_value=[mock_http_transport_entry],
        ),
    ):
        client = InferenceClient(
            model_endpoint=model_endpoint, service_id="test-service-id"
        )
    client.transport.send_request = AsyncMock(return_value=RequestRecord())
    return client


def _request_info(client, turns) -> RequestInfo:
    return RequestInfo(
        model_endpoint=client.model_endpoint,
        turns=turns,
        turn_index=0,
        credit_num=0,
        credit_phase=CreditPhase.PROFILING,
        x_request_id="req-1",
        x_correlation_id="corr-1",
        root_correlation_id="corr-1",
        conversation_id="conv-1",
    )


def _capture_facts(client):
    """Replace the plan's headers() with a spy recording the facts it receives."""
    captured = {}
    real_headers = client._routing_plan.headers

    def spy(facts):
        captured["facts"] = facts
        return real_headers(facts)

    client._routing_plan.headers = spy
    return captured


@pytest.mark.parametrize(
    "shared_headers, expected",
    [
        param({"X-Src-Id": "rec-1"}, {"X-Src-Id": "rec-1"}, id="dataset_headers_exposed"),
        param(None, {}, id="empty_when_turn_has_none"),
    ],
)  # fmt: skip
@pytest.mark.asyncio
async def test_facts_carry_readonly_view_of_turn_extra_headers(
    mock_http_transport_entry, shared_headers, expected
):
    client = _build_client(mock_http_transport_entry)
    turn_kwargs = {} if shared_headers is None else {"extra_headers": shared_headers}
    turn = Turn(role="user", texts=[Text(contents=["hi"])], **turn_kwargs)
    captured = _capture_facts(client)

    await client._send_request_to_transport(_request_info(client, [turn]))

    view = captured["facts"].turn_extra_headers
    assert isinstance(view, MappingProxyType)
    assert dict(view) == expected
    with pytest.raises(TypeError):
        view["X-Src-Id"] = "mutated"
    # Underlying dataset dict untouched through the read-only view.
    if shared_headers is not None:
        assert shared_headers == expected
