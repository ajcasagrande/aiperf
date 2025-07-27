# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from aiperf.common.enums.base_enums import CaseInsensitiveStrEnum


class PluginType(CaseInsensitiveStrEnum):
    UI = "ui"
    POST_PROCESSOR = "post_processor"
    DATA_EXPORTER = "data_exporter"
    DATA_LOADER = "data_loader"
    DATA_VALIDATOR = "data_validator"
    DATA_TRANSFORMER = "data_transformer"
    DATA_PREPROCESSOR = "data_preprocessor"
    DATA_POSTPROCESSOR = "data_postprocessor"
