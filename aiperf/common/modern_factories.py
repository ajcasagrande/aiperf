# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Modern factory implementations using dependency injection.

This module provides drop-in replacements for the existing AIPerf factories using
the modern dependency injection container with lazy loading and plugin support.
"""

from typing import TYPE_CHECKING, Any

from aiperf.common.di_container import ModernFactory, SingletonFactory, main_container
from aiperf.common.enums import (
    AIPerfUIType,
    CommClientType,
    CommunicationBackend,
    ComposerType,
    ConsoleExporterType,
    CustomDatasetType,
    DataExporterType,
    EndpointType,
    OpenAIObjectType,
    RecordProcessorType,
    RequestRateMode,
    ResultsProcessorType,
    ServiceRunType,
    ServiceType,
    ZMQProxyType,
)

if TYPE_CHECKING:
    from aiperf.clients.model_endpoint_info import ModelEndpointInfo
    from aiperf.common.config import (
        BaseZMQCommunicationConfig,
        BaseZMQProxyConfig,
        ServiceConfig,
        UserConfig,
    )
    from aiperf.common.protocols import (
        AIPerfUIProtocol,
        CommunicationClientProtocol,
        CommunicationProtocol,
        ConsoleExporterProtocol,
        DataExporterProtocol,
        InferenceClientProtocol,
        OpenAIObjectParserProtocol,
        RecordProcessorProtocol,
        RequestConverterProtocol,
        RequestRateGeneratorProtocol,
        ResponseExtractorProtocol,
        ResultsProcessorProtocol,
        ServiceManagerProtocol,
        ServiceProtocol,
    )
    from aiperf.dataset import CustomDatasetLoaderProtocol
    from aiperf.dataset.composer.base import BaseDatasetComposer
    from aiperf.exporters.exporter_config import ExporterConfig
    from aiperf.timing.config import TimingManagerConfig
    from aiperf.zmq.zmq_proxy_base import BaseZMQProxy


class AIPerfUIFactory(SingletonFactory[AIPerfUIType, "AIPerfUIProtocol"]):
    """Modern factory for AIPerfUI instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="ui",
            protocol=None,  # Will be imported when needed
            enum_type=AIPerfUIType
        )


class CommunicationClientFactory(ModernFactory[CommClientType, "CommunicationClientProtocol"]):
    """Modern factory for communication client instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="clients",
            protocol=None,  # Will be imported when needed
            enum_type=CommClientType
        )

    def create_instance(  # type: ignore[override]
        self,
        class_type: CommClientType | str,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
        **kwargs: Any,
    ) -> "CommunicationClientProtocol":
        return super().create_instance(
            class_type,
            address=address,
            bind=bind,
            socket_ops=socket_ops,
            **kwargs
        )


class CommunicationFactory(SingletonFactory[CommunicationBackend, "CommunicationProtocol"]):
    """Modern factory for communication backend instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="communication",
            protocol=None,  # Will be imported when needed
            enum_type=CommunicationBackend
        )

    def create_instance(  # type: ignore[override]
        self,
        class_type: CommunicationBackend | str,
        config: "BaseZMQCommunicationConfig",
        **kwargs: Any,
    ) -> "CommunicationProtocol":
        return super().create_instance(class_type, config=config, **kwargs)


class ComposerFactory(ModernFactory[ComposerType, "BaseDatasetComposer"]):
    """Modern factory for dataset composer instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="composers",
            protocol=None,  # Will be imported when needed
            enum_type=ComposerType
        )


class ConsoleExporterFactory(ModernFactory[ConsoleExporterType, "ConsoleExporterProtocol"]):
    """Modern factory for console exporter instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="console_exporters",
            protocol=None,  # Will be imported when needed
            enum_type=ConsoleExporterType
        )

    def create_instance(  # type: ignore[override]
        self,
        class_type: ConsoleExporterType | str,
        exporter_config: "ExporterConfig",
        **kwargs: Any,
    ) -> "ConsoleExporterProtocol":
        return super().create_instance(
            class_type, exporter_config=exporter_config, **kwargs
        )


class CustomDatasetFactory(ModernFactory[CustomDatasetType, "CustomDatasetLoaderProtocol"]):
    """Modern factory for custom dataset loader instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="datasets",
            protocol=None,  # Will be imported when needed
            enum_type=CustomDatasetType
        )


class DataExporterFactory(ModernFactory[DataExporterType, "DataExporterProtocol"]):
    """Modern factory for data exporter instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="exporters",
            protocol=None,  # Will be imported when needed
            enum_type=DataExporterType
        )

    def create_instance(  # type: ignore[override]
        self,
        class_type: DataExporterType | str,
        exporter_config: "ExporterConfig",
        **kwargs: Any,
    ) -> "DataExporterProtocol":
        return super().create_instance(
            class_type, exporter_config=exporter_config, **kwargs
        )


class InferenceClientFactory(ModernFactory[EndpointType, "InferenceClientProtocol"]):
    """Modern factory for inference client instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="inference_clients",
            protocol=None,  # Will be imported when needed
            enum_type=EndpointType
        )

    def create_instance(  # type: ignore[override]
        self,
        class_type: EndpointType | str,
        model_endpoint: "ModelEndpointInfo",
        **kwargs: Any,
    ) -> "InferenceClientProtocol":
        return super().create_instance(
            class_type, model_endpoint=model_endpoint, **kwargs
        )


class OpenAIObjectParserFactory(SingletonFactory[OpenAIObjectType, "OpenAIObjectParserProtocol"]):
    """Modern factory for OpenAI object parser instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="openai_parsers",
            protocol=None,  # Will be imported when needed
            enum_type=OpenAIObjectType
        )


class RequestConverterFactory(SingletonFactory[EndpointType, "RequestConverterProtocol"]):
    """Modern factory for request converter instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="request_converters",
            protocol=None,  # Will be imported when needed
            enum_type=EndpointType
        )


class ResponseExtractorFactory(ModernFactory[EndpointType, "ResponseExtractorProtocol"]):
    """Modern factory for response extractor instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="response_extractors",
            protocol=None,  # Will be imported when needed
            enum_type=EndpointType
        )

    def create_instance(  # type: ignore[override]
        self,
        class_type: EndpointType | str,
        model_endpoint: "ModelEndpointInfo",
        **kwargs: Any,
    ) -> "ResponseExtractorProtocol":
        return super().create_instance(
            class_type, model_endpoint=model_endpoint, **kwargs
        )


class ServiceFactory(ModernFactory[ServiceType, "ServiceProtocol"]):
    """Modern factory for service instances with enhanced features."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="services",
            protocol=None,  # Will be imported when needed
            enum_type=ServiceType
        )

    def create_instance(  # type: ignore[override]
        self,
        class_type: ServiceType | str,
        service_config: "ServiceConfig",
        user_config: "UserConfig",
        service_id: str | None = None,
        **kwargs: Any,
    ) -> "ServiceProtocol":
        return super().create_instance(
            class_type,
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            **kwargs
        )


class ServiceManagerFactory(ModernFactory[ServiceRunType, "ServiceManagerProtocol"]):
    """Modern factory for service manager instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="service_managers",
            protocol=None,  # Will be imported when needed
            enum_type=ServiceRunType
        )

    def create_instance(  # type: ignore[override]
        self,
        class_type: ServiceRunType | str,
        required_services: dict[ServiceType, int],
        service_config: "ServiceConfig",
        user_config: "UserConfig",
        **kwargs: Any,
    ) -> "ServiceManagerProtocol":
        return super().create_instance(
            class_type,
            required_services=required_services,
            service_config=service_config,
            user_config=user_config,
            **kwargs,
        )


class RecordProcessorFactory(ModernFactory[RecordProcessorType, "RecordProcessorProtocol"]):
    """Modern factory for record processor instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="processors",
            protocol=None,  # Will be imported when needed
            enum_type=RecordProcessorType
        )

    def create_instance(  # type: ignore[override]
        self,
        class_type: RecordProcessorType | str,
        service_config: "ServiceConfig",
        user_config: "UserConfig",
        **kwargs: Any,
    ) -> "RecordProcessorProtocol":
        return super().create_instance(
            class_type,
            service_config=service_config,
            user_config=user_config,
            **kwargs,
        )


class ResultsProcessorFactory(ModernFactory[ResultsProcessorType, "ResultsProcessorProtocol"]):
    """Modern factory for results processor instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="processors",
            protocol=None,  # Will be imported when needed
            enum_type=ResultsProcessorType
        )

    def create_instance(  # type: ignore[override]
        self,
        class_type: ResultsProcessorType | str,
        service_config: "ServiceConfig",
        user_config: "UserConfig",
        **kwargs: Any,
    ) -> "ResultsProcessorProtocol":
        return super().create_instance(
            class_type,
            service_config=service_config,
            user_config=user_config,
            **kwargs,
        )


class RequestRateGeneratorFactory(ModernFactory[RequestRateMode, "RequestRateGeneratorProtocol"]):
    """Modern factory for request rate generator instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="rate_generators",
            protocol=None,  # Will be imported when needed
            enum_type=RequestRateMode
        )

    def create_instance(  # type: ignore[override]
        self,
        config: "TimingManagerConfig",
        **kwargs: Any,
    ) -> "RequestRateGeneratorProtocol":
        return super().create_instance(config.request_rate_mode, config=config, **kwargs)


class ZMQProxyFactory(ModernFactory[ZMQProxyType, "BaseZMQProxy"]):
    """Modern factory for ZMQ proxy instances."""

    def __init__(self):
        super().__init__(
            container=main_container,
            plugin_type="zmq_proxies",
            protocol=None,  # Will be imported when needed
            enum_type=ZMQProxyType
        )

    def create_instance(  # type: ignore[override]
        self,
        class_type: ZMQProxyType | str,
        zmq_proxy_config: "BaseZMQProxyConfig",
        **kwargs: Any,
    ) -> "BaseZMQProxy":
        return super().create_instance(
            class_type, zmq_proxy_config=zmq_proxy_config, **kwargs
        )


# Create singleton instances for global use
ui_factory = AIPerfUIFactory()
communication_client_factory = CommunicationClientFactory()
communication_factory = CommunicationFactory()
composer_factory = ComposerFactory()
console_exporter_factory = ConsoleExporterFactory()
custom_dataset_factory = CustomDatasetFactory()
data_exporter_factory = DataExporterFactory()
inference_client_factory = InferenceClientFactory()
openai_object_parser_factory = OpenAIObjectParserFactory()
request_converter_factory = RequestConverterFactory()
response_extractor_factory = ResponseExtractorFactory()
service_factory = ServiceFactory()
service_manager_factory = ServiceManagerFactory()
record_processor_factory = RecordProcessorFactory()
results_processor_factory = ResultsProcessorFactory()
request_rate_generator_factory = RequestRateGeneratorFactory()
zmq_proxy_factory = ZMQProxyFactory()
