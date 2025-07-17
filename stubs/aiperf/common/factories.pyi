#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from collections.abc import Callable as Callable
from typing import Any, Generic, TypeVar

from _typeshed import Incomplete

from aiperf.common.enums import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum
from aiperf.common.enums import PromptSource as PromptSource
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.enums import ZMQProxyType as ZMQProxyType
from aiperf.common.exceptions import FactoryCreationError as FactoryCreationError

ClassEnumT = TypeVar("ClassEnumT", bound=CaseInsensitiveStrEnum)
ClassProtocolT = TypeVar("ClassProtocolT", bound=Any)

class FactoryMixin(Generic[ClassEnumT, ClassProtocolT]):
    logger: Incomplete
    def __init_subclass__(cls) -> None: ...
    @classmethod
    def register_all(
        cls, *class_types: ClassEnumT | str, override_priority: int = 0
    ) -> Callable: ...
    @classmethod
    def register(
        cls, class_type: ClassEnumT | str, override_priority: int = 0
    ) -> Callable: ...
    @classmethod
    def create_instance(
        cls, class_type: ClassEnumT | str, **kwargs: Any
    ) -> ClassProtocolT: ...
    @classmethod
    def get_class_from_type(
        cls, class_type: ClassEnumT | str
    ) -> type[ClassProtocolT]: ...
    @classmethod
    def get_all_classes(cls) -> list[type[ClassProtocolT]]: ...
    @classmethod
    def get_all_class_types(cls) -> list[ClassEnumT | str]: ...
    @classmethod
    def get_all_classes_and_types(
        cls,
    ) -> list[tuple[type[ClassProtocolT], ClassEnumT | str]]: ...

class InputConverterFactory(FactoryMixin[PromptSource, "InputConverterProtocol"]): ...
class ServiceFactory(FactoryMixin[ServiceType, "BaseService"]): ...
class DataExporterFactory(FactoryMixin["DataExporterType", "DataExporterProtocol"]): ...
class PostProcessorFactory(
    FactoryMixin["PostProcessorType", "PostProcessorProtocol"]
): ...
class ComposerFactory(FactoryMixin["ComposerType", "BaseDatasetComposer"]): ...
class CustomDatasetFactory(
    FactoryMixin["CustomDatasetType", "CustomDatasetLoaderProtocol"]
): ...
class ZMQProxyFactory(FactoryMixin[ZMQProxyType, "BaseZMQProxy"]): ...
