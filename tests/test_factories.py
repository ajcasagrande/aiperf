# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.clients.client_interfaces import (
    InferenceClientFactory,
    RequestConverterFactory,
    ResponseExtractorFactory,
)
from aiperf.clients.openai.openai_aiohttp import OpenAIClientAioHttp
from aiperf.clients.openai.openai_chat import OpenAIChatCompletionRequestConverter
from aiperf.clients.openai.openai_completions import OpenAICompletionRequestConverter
from aiperf.clients.openai.openai_responses import OpenAIResponsesRequestConverter
from aiperf.common.comms.base import (
    CommunicationClientFactory,
    CommunicationClientProtocolFactory,
    PubClientProtocol,
    PullClientProtocol,
    PushClientProtocol,
    ReplyClientProtocol,
    RequestClientProtocol,
    SubClientProtocol,
)
from aiperf.common.comms.zmq.dealer_request_client import ZMQDealerRequestClient
from aiperf.common.comms.zmq.pub_client import ZMQPubClient
from aiperf.common.comms.zmq.pull_client import ZMQPullClient
from aiperf.common.comms.zmq.push_client import ZMQPushClient
from aiperf.common.comms.zmq.router_reply_client import ZMQRouterReplyClient
from aiperf.common.comms.zmq.sub_client import ZMQSubClient
from aiperf.common.enums import (
    CommunicationClientType,
    DataExporterType,
    EndpointType,
    PostProcessorType,
)
from aiperf.common.factories import DataExporterFactory, PostProcessorFactory
from aiperf.data_exporter.console_error_exporter import ConsoleErrorExporter
from aiperf.data_exporter.console_exporter import ConsoleExporter
from aiperf.data_exporter.json_exporter import JsonExporter
from aiperf.services.inference_result_parser.openai_parsers import (
    OpenAIResponseExtractor,
)
from aiperf.services.records_manager.post_processors.metric_summary import MetricSummary

################################################################################
# Factory Registration Tests
################################################################################


class TestFactoryRegistrations:
    """Test that all expected classes are properly registered with their factories."""

    @pytest.mark.parametrize(
        "client_type,expected_class",
        [
            (CommunicationClientType.PUSH, ZMQPushClient),
            (CommunicationClientType.PULL, ZMQPullClient),
            (CommunicationClientType.PUB, ZMQPubClient),
            (CommunicationClientType.SUB, ZMQSubClient),
            (CommunicationClientType.REQUEST, ZMQDealerRequestClient),
            (CommunicationClientType.REPLY, ZMQRouterReplyClient),
        ],
    )
    def test_communication_client_factory_registrations(
        self, client_type, expected_class
    ) -> None:
        """Test that all ZMQ clients are registered with CommunicationClientFactory."""
        registered_class = CommunicationClientFactory.get_class_from_type(client_type)
        assert registered_class == expected_class

    @pytest.mark.parametrize(
        "client_type,expected_protocol",
        [
            (CommunicationClientType.PUSH, PushClientProtocol),
            (CommunicationClientType.PULL, PullClientProtocol),
            (CommunicationClientType.PUB, PubClientProtocol),
            (CommunicationClientType.SUB, SubClientProtocol),
            (CommunicationClientType.REQUEST, RequestClientProtocol),
            (CommunicationClientType.REPLY, ReplyClientProtocol),
        ],
    )
    def test_communication_client_protocol_factory_registrations(
        self, client_type, expected_protocol
    ) -> None:
        """Test that all client protocols are registered with CommunicationClientProtocolFactory."""
        registered_protocol = CommunicationClientProtocolFactory.get_class_from_type(
            client_type
        )
        assert registered_protocol == expected_protocol

    @pytest.mark.parametrize(
        "exporter_type,expected_class",
        [
            (DataExporterType.CONSOLE, ConsoleExporter),
            (DataExporterType.CONSOLE_ERROR, ConsoleErrorExporter),
            (DataExporterType.JSON, JsonExporter),
        ],
    )
    def test_data_exporter_factory_registrations(
        self, exporter_type, expected_class
    ) -> None:
        """Test that all data exporters are registered with DataExporterFactory."""
        registered_class = DataExporterFactory.get_class_from_type(exporter_type)
        assert registered_class == expected_class

    @pytest.mark.parametrize(
        "endpoint_type,inference_client_class",
        [
            (EndpointType.OPENAI_CHAT_COMPLETIONS, OpenAIClientAioHttp),
            (EndpointType.OPENAI_COMPLETIONS, OpenAIClientAioHttp),
            (EndpointType.OPENAI_RESPONSES, OpenAIClientAioHttp),
        ],
    )
    def test_inference_client_factory_registrations(
        self, endpoint_type, inference_client_class
    ) -> None:
        """Test that inference clients are registered with InferenceClientFactory."""
        registered_class = InferenceClientFactory.get_class_from_type(endpoint_type)
        assert registered_class == inference_client_class

    @pytest.mark.parametrize(
        "endpoint_type,converter_class",
        [
            (
                EndpointType.OPENAI_CHAT_COMPLETIONS,
                OpenAIChatCompletionRequestConverter,
            ),
            (EndpointType.OPENAI_COMPLETIONS, OpenAICompletionRequestConverter),
            (EndpointType.OPENAI_RESPONSES, OpenAIResponsesRequestConverter),
        ],
    )
    def test_request_converter_factory_registrations(
        self, endpoint_type, converter_class
    ) -> None:
        """Test that request converters are registered with RequestConverterFactory."""
        registered_class = RequestConverterFactory.get_class_from_type(endpoint_type)
        assert registered_class == converter_class

    @pytest.mark.parametrize(
        "endpoint_type,extractor_class",
        [
            (EndpointType.OPENAI_CHAT_COMPLETIONS, OpenAIResponseExtractor),
            (EndpointType.OPENAI_COMPLETIONS, OpenAIResponseExtractor),
            (EndpointType.OPENAI_RESPONSES, OpenAIResponseExtractor),
        ],
    )
    def test_response_extractor_factory_registrations(
        self, endpoint_type, extractor_class
    ) -> None:
        """Test that response extractors are registered with ResponseExtractorFactory."""
        registered_class = ResponseExtractorFactory.get_class_from_type(endpoint_type)
        assert registered_class == extractor_class

    @pytest.mark.parametrize(
        "endpoint_type,post_processor_class",
        [
            (PostProcessorType.METRIC_SUMMARY, MetricSummary),
        ],
    )
    def test_post_processor_factory_registrations(
        self, endpoint_type, post_processor_class
    ) -> None:
        """Test that post processors are registered with PostProcessorFactory."""
        registered_class = PostProcessorFactory.get_class_from_type(endpoint_type)
        assert registered_class == post_processor_class
