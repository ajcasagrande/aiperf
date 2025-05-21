#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import logging


class LoggerMixin:
    """
    Provides self.logger, defaulting to a logger named after the class's service_type
    (or class name if service_type isn't available yet).
    """

    def __init__(self, *args, **kwargs):
        # let other mixins initialize first
        super().__init__(*args, **kwargs)

        # prefer a .service_type attribute if present, else class name
        name = getattr(self, "service_type", None) or self.__class__.__name__
        self.logger = logging.getLogger(name)
