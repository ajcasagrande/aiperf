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
# Communication Client Protocol Tests
################################################################################


class TestCommunicationClientProtocol:
    """Tests for CommunicationClientProtocol implementations."""

    def test_protocol_compliance(self) -> None:
        """Test that all communication client protocols inherit from CommunicationClientProtocol."""
        assert issubclass(PushClientProtocol, CommunicationClientProtocol)
        assert issubclass(PullClientProtocol, CommunicationClientProtocol)
        assert issubclass(PubClientProtocol, CommunicationClientProtocol)
        assert issubclass(RequestClientProtocol, CommunicationClientProtocol)
        assert issubclass(ReplyClientProtocol, CommunicationClientProtocol)
        assert issubclass(SubClientProtocol, CommunicationClientProtocol)


class TestPushClientProtocol:
    """Tests for PushClientProtocol implementations."""

    def test_protocol_compliance(self) -> None:
        """Test that all classes implementing PushClientProtocol are compliant."""
        assert issubclass(ZMQPushClient, PushClientProtocol)
        assert issubclass(ZMQPushClient, CommunicationClientProtocol)


class TestPullClientProtocol:
    """Tests for PullClientProtocol implementations."""

    def test_protocol_compliance(self) -> None:
        """Test that all classes implementing PullClientProtocol are compliant."""
        assert issubclass(ZMQPullClient, PullClientProtocol)
        assert issubclass(ZMQPullClient, CommunicationClientProtocol)


class TestPubClientProtocol:
    """Tests for PubClientProtocol implementations."""

    def test_protocol_compliance(self) -> None:
        """Test that all classes implementing PubClientProtocol are compliant."""
        assert issubclass(ZMQPubClient, PubClientProtocol)
        assert issubclass(ZMQPubClient, CommunicationClientProtocol)


class TestSubClientProtocol:
    """Tests for SubClientProtocol implementations."""

    def test_protocol_compliance(self) -> None:
        """Test that all classes implementing SubClientProtocol are compliant."""
        assert issubclass(ZMQSubClient, SubClientProtocol)
        assert issubclass(ZMQSubClient, CommunicationClientProtocol)


class TestRequestClientProtocol:
    """Tests for RequestClientProtocol implementations."""

    def test_protocol_compliance(self) -> None:
        """Test that all classes implementing RequestClientProtocol are compliant."""
        assert issubclass(ZMQDealerRequestClient, RequestClientProtocol)
        assert issubclass(ZMQDealerRequestClient, CommunicationClientProtocol)


class TestReplyClientProtocol:
    """Tests for ReplyClientProtocol implementations."""

    def test_protocol_compliance(self) -> None:
        """Test that all classes implementing ReplyClientProtocol are compliant."""
        assert issubclass(ZMQRouterReplyClient, ReplyClientProtocol)
        assert issubclass(ZMQRouterReplyClient, CommunicationClientProtocol)


################################################################################
# Client Interface Protocol Tests
################################################################################


class TestInferenceClientProtocol:
    """Tests for InferenceClientProtocol implementations."""

    def test_protocol_compliance(self) -> None:
        """Test that all classes implementing InferenceClientProtocol are compliant."""
        assert issubclass(OpenAIClientAioHttp, InferenceClientProtocol)


class TestRequestConverterProtocol:
    """Tests for RequestConverterProtocol implementations."""

    def test_protocol_compliance(self) -> None:
        """Test that all classes implementing RequestConverterProtocol are compliant."""
        assert issubclass(
            OpenAIChatCompletionRequestConverter, RequestConverterProtocol
        )
        assert issubclass(OpenAICompletionRequestConverter, RequestConverterProtocol)
        assert issubclass(OpenAIResponsesRequestConverter, RequestConverterProtocol)


class TestResponseExtractorProtocol:
    """Tests for ResponseExtractorProtocol implementations."""

    def test_protocol_compliance(self) -> None:
        """Test that all classes implementing ResponseExtractorProtocol are compliant."""
        assert issubclass(OpenAIResponseExtractor, ResponseExtractorProtocol)


################################################################################
# Common Interface Protocol Tests
################################################################################


class TestDataExporterProtocol:
    """Tests for DataExporterProtocol implementations."""

    def test_protocol_compliance(self) -> None:
        """Test that all classes implementing DataExporterProtocol are compliant."""
        assert issubclass(ConsoleExporter, DataExporterProtocol)
        assert issubclass(ConsoleErrorExporter, DataExporterProtocol)
        assert issubclass(JsonExporter, DataExporterProtocol)


class TestPostProcessorProtocol:
    """Tests for PostProcessorProtocol implementations."""

    def test_protocol_compliance(self) -> None:
        """Test that all classes implementing PostProcessorProtocol are compliant."""
        assert issubclass(MetricSummary, PostProcessorProtocol)


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


################################################################################
# Protocol Inheritance Tests
################################################################################


class TestProtocolInheritance:
    """Test that protocol inheritance hierarchies are correctly established."""

    def test_communication_client_protocol_hierarchy(self) -> None:
        """Test that all communication client protocols inherit from the base protocol."""
        assert issubclass(PushClientProtocol, CommunicationClientProtocol)
        assert issubclass(PullClientProtocol, CommunicationClientProtocol)
        assert issubclass(PubClientProtocol, CommunicationClientProtocol)
        assert issubclass(SubClientProtocol, CommunicationClientProtocol)
        assert issubclass(RequestClientProtocol, CommunicationClientProtocol)
        assert issubclass(ReplyClientProtocol, CommunicationClientProtocol)

    def test_factory_registered_classes_implement_protocols(self) -> None:
        """Test that all factory-registered classes implement their respective protocols."""
        for client_class in CommunicationClientFactory.get_all_classes():
            assert issubclass(client_class, CommunicationClientProtocol)

        for exporter_class in DataExporterFactory.get_all_classes():
            assert issubclass(exporter_class, DataExporterProtocol)

        for processor_class in PostProcessorFactory.get_all_classes():
            assert issubclass(processor_class, PostProcessorProtocol)

        for client_class in InferenceClientFactory.get_all_classes():
            assert issubclass(client_class, InferenceClientProtocol)

        for converter_class in RequestConverterFactory.get_all_classes():
            assert issubclass(converter_class, RequestConverterProtocol)

        for extractor_class in ResponseExtractorFactory.get_all_classes():
            assert issubclass(extractor_class, ResponseExtractorProtocol)
