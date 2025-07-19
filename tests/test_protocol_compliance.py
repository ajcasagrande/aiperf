# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest

from aiperf.clients.client_interfaces import (
    InferenceClientProtocol,
    RequestConverterProtocol,
    ResponseExtractorProtocol,
)
from aiperf.clients.openai.openai_aiohttp import OpenAIClientAioHttp
from aiperf.clients.openai.openai_chat import OpenAIChatCompletionRequestConverter
from aiperf.clients.openai.openai_completions import OpenAICompletionRequestConverter
from aiperf.clients.openai.openai_responses import OpenAIResponsesRequestConverter
from aiperf.common.comms.base_comms import (
    CommunicationClientProtocol,
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
from aiperf.services.timing_manager.credit_issuing_strategy import CreditManagerProtocol
from aiperf.services.timing_manager.timing_manager import TimingManager

################################################################################
# Protocol Compliance Tests
################################################################################


class TestProtocolCompliance:
    """Tests for protocol compliance across all implementations."""

    @pytest.mark.parametrize(
        "implementation,protocol",
        [
            #########################################################
            # Communication client protocols inherit from base protocol
            #########################################################
            (PushClientProtocol, CommunicationClientProtocol),
            (PullClientProtocol, CommunicationClientProtocol),
            (PubClientProtocol, CommunicationClientProtocol),
            (RequestClientProtocol, CommunicationClientProtocol),
            (ReplyClientProtocol, CommunicationClientProtocol),
            (SubClientProtocol, CommunicationClientProtocol),
            #########################################################
            # ZMQ implementations inherit from specific protocols
            #########################################################
            (ZMQPushClient, PushClientProtocol),
            (ZMQPullClient, PullClientProtocol),
            (ZMQPubClient, PubClientProtocol),
            (ZMQSubClient, SubClientProtocol),
            (ZMQDealerRequestClient, RequestClientProtocol),
            (ZMQRouterReplyClient, ReplyClientProtocol),
            #########################################################
            # Inference client implementations
            #########################################################
            (OpenAIClientAioHttp, InferenceClientProtocol),
            #########################################################
            # Request converter implementations
            #########################################################
            (OpenAIChatCompletionRequestConverter, RequestConverterProtocol),
            (OpenAICompletionRequestConverter, RequestConverterProtocol),
            (OpenAIResponsesRequestConverter, RequestConverterProtocol),
            #########################################################
            # Response extractor implementations
            #########################################################
            (OpenAIResponseExtractor, ResponseExtractorProtocol),
            #########################################################
            # Data exporter implementations
            #########################################################
            (ConsoleExporter, DataExporterProtocol),
            (ConsoleErrorExporter, DataExporterProtocol),
            (JsonExporter, DataExporterProtocol),
            #########################################################
            # Post processor implementations
            #########################################################
            (MetricSummary, PostProcessorProtocol),
            #########################################################
            # Credit manager protocol implementations
            #########################################################
            (TimingManager, CreditManagerProtocol),
        ],
    )
    def test_protocol_compliance(self, implementation, protocol) -> None:
        """Test that implementations properly inherit from their protocols."""
        assert issubclass(implementation, protocol)
