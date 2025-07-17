#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums.base import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum

class Modality(CaseInsensitiveStrEnum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    MULTIMODAL = "multimodal"
    CUSTOM = "custom"

class ModelSelectionStrategy(CaseInsensitiveStrEnum):
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    MODALITY_AWARE = "modality_aware"
