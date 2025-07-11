# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.clients.client_interfaces import (
    InferenceClientFactory,
    InferenceClientProtocol,
    RequestConverterFactory,
    RequestConverterProtocol,
    ResponseExtractorFactory,
    ResponseExtractorProtocol,
)
from aiperf.clients.openai.openai_aiohttp import OpenAIClientAioHttp
from aiperf.clients.openai.openai_chat import OpenAIChatCompletionRequestConverter
from aiperf.clients.openai.openai_completions import OpenAICompletionRequestConverter
from aiperf.clients.openai.openai_responses import OpenAIResponsesRequestConverter
from aiperf.common.comms.base import (
    CommunicationClientFactory,
    CommunicationClientProtocol,
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
from aiperf.common.enums import CommunicationClientType, DataExporterType
from aiperf.common.factories import DataExporterFactory, PostProcessorFactory
from aiperf.common.interfaces import (
    DataExporterProtocol,
    PostProcessorProtocol,
)
from aiperf.data_exporter.console_error_exporter import ConsoleErrorExporter
from aiperf.data_exporter.console_exporter import ConsoleExporter
from aiperf.data_exporter.json_exporter import JsonExporter
from aiperf.services.inference_result_parser.openai_parsers import (
    OpenAIResponseExtractor,
)
from aiperf.services.records_manager.post_processors.metric_summary import MetricSummary

################################################################################
# Protocol Compliance Tests
################################################################################


class TestProtocolCompliance:
    """Tests for protocol compliance across all implementations."""

    @pytest.mark.parametrize(
        "implementation,protocol",
        [
            # Communication client protocols inherit from base protocol
            (PushClientProtocol, CommunicationClientProtocol),
            (PullClientProtocol, CommunicationClientProtocol),
            (PubClientProtocol, CommunicationClientProtocol),
            (RequestClientProtocol, CommunicationClientProtocol),
            (ReplyClientProtocol, CommunicationClientProtocol),
            (SubClientProtocol, CommunicationClientProtocol),
            # ZMQ implementations inherit from specific protocols
            (ZMQPushClient, PushClientProtocol),
            (ZMQPullClient, PullClientProtocol),
            (ZMQPubClient, PubClientProtocol),
            (ZMQSubClient, SubClientProtocol),
            (ZMQDealerRequestClient, RequestClientProtocol),
            (ZMQRouterReplyClient, ReplyClientProtocol),
            # Inference client implementations
            (OpenAIClientAioHttp, InferenceClientProtocol),
            # Request converter implementations
            (OpenAIChatCompletionRequestConverter, RequestConverterProtocol),
            (OpenAICompletionRequestConverter, RequestConverterProtocol),
            (OpenAIResponsesRequestConverter, RequestConverterProtocol),
            # Response extractor implementations
            (OpenAIResponseExtractor, ResponseExtractorProtocol),
            # Data exporter implementations
            (ConsoleExporter, DataExporterProtocol),
            (ConsoleErrorExporter, DataExporterProtocol),
            (JsonExporter, DataExporterProtocol),
            # Post processor implementations
            (MetricSummary, PostProcessorProtocol),
        ],
    )
    def test_protocol_compliance(self, implementation, protocol) -> None:
        """Test that implementations properly inherit from their protocols."""
        assert issubclass(implementation, protocol)


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

    def test_inference_client_factory_registrations(self) -> None:
        """Test that inference clients are registered with InferenceClientFactory."""
        registered_classes = InferenceClientFactory.get_all_classes()
        assert OpenAIClientAioHttp in registered_classes

    @pytest.mark.parametrize(
        "converter_class",
        [
            OpenAIChatCompletionRequestConverter,
            OpenAICompletionRequestConverter,
            OpenAIResponsesRequestConverter,
        ],
    )
    def test_request_converter_factory_registrations(self, converter_class) -> None:
        """Test that request converters are registered with RequestConverterFactory."""
        registered_classes = RequestConverterFactory.get_all_classes()
        assert converter_class in registered_classes

    def test_response_extractor_factory_registrations(self) -> None:
        """Test that response extractors are registered with ResponseExtractorFactory."""
        registered_classes = ResponseExtractorFactory.get_all_classes()
        assert OpenAIResponseExtractor in registered_classes

    def test_post_processor_factory_registrations(self) -> None:
        """Test that post processors are registered with PostProcessorFactory."""
        registered_classes = PostProcessorFactory.get_all_classes()
        assert MetricSummary in registered_classes
